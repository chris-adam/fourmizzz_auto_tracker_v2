from bs4 import BeautifulSoup
from celery import chain
from celery import group
from django.db.models import F
from django.db.models import Func
from django.db.models import QuerySet
from django.utils import timezone
from scraper.models import FourmizzzServer
from scraper.models import PlayerTarget
from scraper.models import PrecisionSnapshot
from scraper.models import RankingSnapshot
from scraper.web_agent import get_player_alliance
from tracker.celery import app
from tracker.settings import TIME_ZONE
from typing import List
from typing import Literal
from typing import Tuple
from typing import Union

import datetime
import itertools
import pytz
import requests


# --- MV


@app.task
def check_mv_players():
    mv_players = PlayerTarget.objects.filter(mv=True)
    subtasks = [
        check_mv_player.si(pk) for pk in mv_players.values_list("pk", flat=True)
    ]
    return group(subtasks).delay()


@app.task
def check_mv_player(mv_player_pk: int):
    mv_player = PlayerTarget.objects.get(pk=mv_player_pk)
    cookies = {"PHPSESSID": mv_player.server.cookie_session}
    url = f"http://{mv_player.server.name}.fourmizzz.fr/Membre.php?Pseudo={mv_player.name}"

    try:
        r = requests.get(url, cookies=cookies)
    except requests.exceptions.ConnectionError:
        raise requests.exceptions.ConnectionError(
            f"Could not open player profile: {mv_player.name}"
        )
    soup = BeautifulSoup(r.text, "html.parser")
    mv = "Joueur en vacances" in soup.find("div", {"class": "boite_membre"}).text
    if mv_player.mv and not mv:
        mv_player.mv = False
        mv_player.save()
        send_message(
            category=mv_player.server.name,
            forum=mv_player.alliance.name or mv_player.name,
            thread=mv_player.name,
            title=f"{mv_player.name} n'est plus en vacances !!!",
            description=datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            color="03b2f8",
        )


# --- Precision snapshots


@app.task
def take_player_precision_snapshot(player_pk: int) -> Tuple[int, int]:
    player = PlayerTarget.objects.get(pk=player_pk)
    cookies = {"PHPSESSID": player.server.cookie_session}
    url = f"http://{player.server.name}.fourmizzz.fr/Membre.php?Pseudo={player.name}"

    try:
        r = requests.get(url, cookies=cookies)
    except requests.exceptions.ConnectionError:
        raise requests.exceptions.ConnectionError(
            f"Could not open player profile: {player.name}"
        )
    soup = BeautifulSoup(r.text, "html.parser")
    hunting_field = int(
        soup.find("table", {"class": "tableau_score"})
        .find_all("tr")[1]
        .find_all("td")[1]
        .text.replace(" ", "")
    )
    trophies = int(
        soup.find("table", {"class": "tableau_score"})
        .find_all("tr")[4]
        .find_all("td")[1]
        .text.replace(" ", "")
    )
    mv = "Joueur en vacances" in soup.find("div", {"class": "boite_membre"}).text
    if not player.mv and mv:
        player.mv = True
        player.save()
        send_message(
            category=player.server.name,
            forum=player.alliance.name or player.name,
            thread=player.name,
            title=f"{player.name} est en vacances",
            description=datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            color="03b2f8",
        )

    last_player_snapshot = PrecisionSnapshot.objects.filter(player=player).last()
    # If this is the first player snapshot
    if last_player_snapshot is None:
        PrecisionSnapshot(
            hunting_field=hunting_field,
            trophies=trophies,
            player=player,
            processed=True,
        ).save()
    # If the player has a different hunting_field or trophies, save an unprocessed snapshot
    elif (
        last_player_snapshot.hunting_field != hunting_field
        or last_player_snapshot.trophies != trophies
    ):
        PrecisionSnapshot(
            hunting_field=hunting_field,
            hunting_field_diff=hunting_field - last_player_snapshot.hunting_field,
            trophies=trophies,
            trophies_diff=trophies - last_player_snapshot.trophies,
            player=player,
        ).save()


@app.task
def take_precision_snapshots() -> None:
    # Take both precision and ranking snapshots
    take_snapshot_subtasks = []
    for player_target in PlayerTarget.objects.iterator():
        take_snapshot_subtasks.append(
            take_player_precision_snapshot.si(player_target.pk)
        )

    return group(take_snapshot_subtasks).delay()


# --- Ranking snapshots


@app.task
def take_page_ranking_snapshot(server_pk: int, page: int) -> Tuple[int, int, int, int]:
    server = FourmizzzServer.objects.get(pk=server_pk)
    cookies = {"PHPSESSID": server.cookie_session}
    url = f"http://{server.name}.fourmizzz.fr/classement2.php?page={page}&typeClassement=terrain"

    try:
        r = requests.get(url, cookies=cookies)
    except requests.exceptions.ConnectionError:
        raise requests.exceptions.ConnectionError(f"Could not open ranking page {page}")

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"class": "tab_triable"})
    if table is None:  # Page does not exist
        return {"server_pk": server_pk, "page": page, "hunting_field": 0, "trophies": 0}
    ranking_snapshots = list()
    for row in table.find_all("tr")[1:]:
        _, player_name, hunting_field, _, _, trophies = row.find_all("td")
        player_name = player_name.find("a").text
        hunting_field = int(hunting_field.text.replace(" ", ""))
        trophies = int(trophies.text.replace(" ", ""))

        last_player_snapshot = RankingSnapshot.objects.filter(
            server=server, player_name=player_name
        ).last()
        if last_player_snapshot is None:
            ranking_snapshots.append(
                RankingSnapshot(
                    server=server,
                    player_name=player_name,
                    hunting_field=hunting_field,
                    trophies=trophies,
                )
            )
        elif (
            last_player_snapshot.hunting_field != hunting_field
            or last_player_snapshot.trophies != trophies
        ):
            ranking_snapshots.append(
                RankingSnapshot(
                    server=server,
                    player_name=player_name,
                    hunting_field=hunting_field,
                    hunting_field_diff=hunting_field
                    - last_player_snapshot.hunting_field,
                    trophies=trophies,
                    trophies_diff=trophies - last_player_snapshot.trophies,
                )
            )

    RankingSnapshot.objects.bulk_create(ranking_snapshots)

    return {
        "server_pk": server_pk,
        "page": page,
        "hunting_field": hunting_field,
        "trophies": trophies,
    }


@app.task
def update_n_scanned_pages(ranking_snapshot_results: List[List]):
    server_pk = ranking_snapshot_results[0]["server_pk"]
    server = FourmizzzServer.objects.get(pk=server_pk)
    lowest_current_hunting_field = min(
        PrecisionSnapshot.objects.filter(player__server=server)
        .order_by("player", "-time")
        .distinct("player")
        .values_list("hunting_field", flat=True)
    )

    last_page = ranking_snapshot_results[-1]["page"]
    penultimate_page = ranking_snapshot_results[-2]["page"]
    current_lowest_hunting_field_from_ranking_page = ranking_snapshot_results[-1][
        "hunting_field"
    ]

    # We should increase the number of scanned ranking pages
    if (
        current_lowest_hunting_field_from_ranking_page
        > lowest_current_hunting_field // 3
    ):
        return chain(
            group(
                [
                    take_page_ranking_snapshot.si(server_pk, i_page)
                    for i_page in (last_page, 2 * last_page)
                ]
            ),
            update_n_scanned_pages.s(),
        ).delay()
    # We're already in the process of increasing the number of pages
    elif last_page - penultimate_page != 1:
        penultimate_current_lowest_hunting_field_from_ranking_page = (
            ranking_snapshot_results[-2]["hunting_field"]
        )
        # The target page amount is in between our two limits
        if (
            penultimate_current_lowest_hunting_field_from_ranking_page
            > lowest_current_hunting_field // 3
        ):
            return chain(
                group(
                    [
                        take_page_ranking_snapshot.si(server_pk, i_page)
                        for i_page in ((last_page + penultimate_page) // 2, last_page)
                    ]
                ),
                update_n_scanned_pages.s(),
            ).delay()
        # We overshoot the limit and should lower our limits
        else:
            return chain(
                group(
                    [
                        take_page_ranking_snapshot.si(server_pk, i_page)
                        for i_page in (
                            penultimate_page - (last_page - penultimate_page) // 2,
                            penultimate_page,
                        )
                    ]
                ),
                update_n_scanned_pages.s(),
            ).delay()

    # We should decrease the number of scanned ranking pages
    new_page = last_page
    for ranking_page_result in ranking_snapshot_results[::-1]:
        lowest_hunting_field_from_ranking_page = ranking_page_result["hunting_field"]
        if lowest_hunting_field_from_ranking_page < lowest_current_hunting_field // 3:
            new_page -= 1

    # Set hard limit to 150 pages because of hardware limitations
    new_page = max(1, min(150, new_page))
    server.n_scanned_pages = new_page
    server.save()

    return new_page


@app.task
def take_ranking_snapshots() -> None:
    # Take both precision and ranking snapshots
    take_snapshot_subtasks = []
    for server in FourmizzzServer.objects.iterator():
        take_snapshot_subtasks.append(
            chain(
                group(
                    [
                        take_page_ranking_snapshot.si(server.pk, i_page)
                        for i_page in range(1, server.n_scanned_pages + 1)
                    ]
                ),
                update_n_scanned_pages.s(),
            )
        )
    return group(take_snapshot_subtasks).delay()


# --- Process snapshots


def send_message(
    category: str,
    forum: str,
    thread: str,
    title: str,
    description: str,
    color: str = "",
    silent: bool = False,
) -> None:
    data = {
        "category": category,
        "forum": forum,
        "thread": thread,
        "title": title,
        "description": description,
        "silent": silent,
    }

    if color:
        data["color"] = color

    r = requests.post("http://discord:5000/post", json=data)
    if r.status_code != 200:
        raise Exception(f"Failed to send message: {r.text}")


@app.task
def process_player_precision_snapshots(
    unprocessed_player_snapshot_pk: List[int],
) -> None:
    def format_move(
        server: FourmizzzServer,
        player_name: str,
        snapshot: Union[PrecisionSnapshot, RankingSnapshot],
        field_name: Literal["hunting_field", "trophies"],
        timestamp: bool = True,
    ):
        alliance_name = get_player_alliance(
            server.name, player_name, server.cookie_session
        )
        alliance = (
            ""
            if alliance_name is None
            else f"([{alliance_name}](http://{server.name}.fourmizzz.fr/classementAlliance.php?alliance={alliance_name}))"
        )
        field_before = "{:,}".format(
            getattr(snapshot, field_name) - getattr(snapshot, f"{field_name}_diff")
        ).replace(",", " ")
        field_after = "{:,}".format(getattr(snapshot, field_name)).replace(",", " ")
        field_diff = "{:+,}".format(getattr(snapshot, f"{field_name}_diff")).replace(
            ",", " "
        )
        snapshot_time = timezone.localtime(snapshot.time, pytz.timezone(TIME_ZONE))
        message = f"[{player_name}](http://{server.name}.fourmizzz.fr/Membre.php?Pseudo={player_name}){alliance}: {field_before} -> {field_after} ({field_diff})\n"
        if timestamp:
            message = snapshot_time.strftime("%d/%m/%Y %H:%M \n") + message
        return message

    def find_matched_snapshots(
        last_player_ranking_snapshot: RankingSnapshot,
        snapshots: QuerySet[RankingSnapshot],
        field_name: Literal["hunting_field", "trophies"],
    ):
        # Annotate with absolute value
        snapshots = snapshots.annotate(
            abs_diff=Func(F(f"{field_name}_diff"), function="ABS")
        )
        # Desc order by absolute value
        snapshots = snapshots.order_by(field_name).order_by("abs_diff").reverse()

        # Look for combinations explanation this snapshot change
        r = 1
        matched_snapshots_pk = list()
        while not matched_snapshots_pk and r <= len(snapshots) and r < 4:
            for snapshots_pk in itertools.combinations(
                snapshots.values_list("pk", flat=True), r
            ):
                snapshots_values = snapshots.filter(pk__in=snapshots_pk).values_list(
                    f"{field_name}_diff", flat=True
                )
                if sum(snapshots_values) == -getattr(
                    last_player_ranking_snapshot, f"{field_name}_diff"
                ):
                    matched_snapshots_pk.extend(snapshots_pk)
                    break
            r += 1

        notification_message = "Mouvements de la cible:\n"
        for precision_snapshot in unprocessed_player_snapshots:
            if getattr(precision_snapshot, f"{field_name}_diff") != 0:
                notification_message += format_move(
                    precision_snapshot.player.server,
                    precision_snapshot.player.name,
                    precision_snapshot,
                    field_name=field_name,
                )

        notification_message += "\nMouvements correspondants:\n"
        for ranking_snapshot_pk in matched_snapshots_pk:
            ranking_snapshot = RankingSnapshot.objects.get(pk=ranking_snapshot_pk)
            notification_message += f"{format_move(ranking_snapshot.server, ranking_snapshot.player_name, ranking_snapshot, field_name=field_name, timestamp=False,)}\n"

        category = player_target.server.name
        forum = player_target.alliance.name or player_target.name
        title = (
            "Mouvement de Tdc"
            if field_name == "hunting_field"
            else "Mouvement de Trophées"
        )
        color = "80ff00" if field_name == "hunting_field" else "ffd700"
        silent = field_name == "hunting_field"
        send_message(
            category,
            forum,
            player_target.name,
            title,
            notification_message,
            color=color,
            silent=silent,
        )

    unprocessed_player_snapshots = PrecisionSnapshot.objects.filter(
        pk__in=unprocessed_player_snapshot_pk
    )
    player_target = unprocessed_player_snapshots.last().player

    last_player_ranking_snapshot = RankingSnapshot.objects.filter(
        server=player_target.server, player_name=player_target.name
    ).last()
    last_player_ranking_snapshot_time = last_player_ranking_snapshot.time.replace(
        second=0,
        microsecond=0,
    )

    if (
        last_player_ranking_snapshot_time + datetime.timedelta(minutes=1)
        < unprocessed_player_snapshots.last().time
    ):
        # FIXME: This error message is not working as expected
        # send_message(
        #     player_target.server.name,
        #     "errors",
        #     f"Erreur: PrecisionSnapshot trop vieux pour {player_target.server}",
        #     f"Le precision snapshot de {player_target.name} est trop vieux. Il a été pris à {unprocessed_player_snapshots.last().time.strftime('%d/%m/%Y %H:%M')} et le dernier ranking snapshot est à {last_player_ranking_snapshot_time.strftime('%d/%m/%Y %H:%M')}.",
        #     color="bb0000",
        # )
        return

    # Get simultaneous ranking snapshots
    simultaneous_snapshots = RankingSnapshot.objects.filter(
        server=player_target.server,
        time__gt=last_player_ranking_snapshot_time,
        time__lt=last_player_ranking_snapshot_time + datetime.timedelta(minutes=1),
    )
    simultaneous_snapshots = simultaneous_snapshots.exclude(
        pk=last_player_ranking_snapshot.pk
    )

    hf_simultaneous_snapshots = simultaneous_snapshots.exclude(hunting_field_diff=0)
    if (
        hf_simultaneous_snapshots
        and last_player_ranking_snapshot.hunting_field_diff != 0
    ):
        find_matched_snapshots(
            last_player_ranking_snapshot,
            hf_simultaneous_snapshots,
            "hunting_field",
        )

    trophies_simultaneous_snapshots = simultaneous_snapshots.exclude(trophies_diff=0)
    if (
        trophies_simultaneous_snapshots
        and last_player_ranking_snapshot.trophies_diff != 0
    ):
        find_matched_snapshots(
            last_player_ranking_snapshot,
            trophies_simultaneous_snapshots,
            "trophies",
        )

    unprocessed_player_snapshots.update(processed=True)


@app.task
def process_snapshots() -> None:
    # Process pending precison snapshots
    process_snapshot_subtasks = list()
    unprocessed_snapshots = PrecisionSnapshot.objects.filter(processed=False)
    unique_player_targets_pk = PlayerTarget.objects.filter(
        pk__in=unprocessed_snapshots.distinct("player").values_list(
            "player__pk", flat=True
        )
    )
    for unique_player_target_pk in unique_player_targets_pk:
        unique_player_unprocessed_snapshots_pk = list(
            unprocessed_snapshots.filter(player=unique_player_target_pk).values_list(
                "pk", flat=True
            )
        )
        process_snapshot_subtasks.append(
            process_player_precision_snapshots.si(
                unique_player_unprocessed_snapshots_pk
            )
        )

    return group(process_snapshot_subtasks).delay()


@app.task
def clean_old_snapshots() -> None:
    PrecisionSnapshot.objects.filter(
        time__lt=datetime.datetime.now() - datetime.timedelta(days=3)
    ).delete()
    RankingSnapshot.objects.filter(
        time__lt=datetime.datetime.now() - datetime.timedelta(days=3)
    ).delete()
