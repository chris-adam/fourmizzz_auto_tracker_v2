from typing import Tuple, List
import datetime
import itertools
import pytz

from django.db.models import Func, F
from django.utils import timezone
from celery import group, chain
import requests
from bs4 import BeautifulSoup

from tracker.settings import TIME_ZONE
from tracker.celery import app
from scraper.models import FourmizzzCredentials, PlayerTarget, PrecisionSnapshot, RankingSnapshot
from scraper.web_agent import get_player_alliance
from discord_bot.bot import send_message


@app.task
def take_player_precision_snapshot(server: str, player_name: str) -> Tuple[int, int]:
    credentials = FourmizzzCredentials.objects.filter(server=server).first()
    if not credentials:
        raise ValueError(f"No Fourmizzz credentials for sever {server}")

    cookies = {'PHPSESSID': credentials.cookie_session}
    url = f"http://{server}.fourmizzz.fr/Membre.php?Pseudo={player_name}"

    try:
        r = requests.get(url, cookies=cookies)
    except requests.exceptions.ConnectionError:
        raise requests.exceptions.ConnectionError(f"Could not open player profile: {player_name}")
    soup = BeautifulSoup(r.text, "html.parser")
    hunting_field = int(soup.find("table", {"class": "tableau_score"}).find_all("tr")[1].find_all("td")[1].text.replace(" ", ""))
    trophies = int(soup.find("table", {"class": "tableau_score"}).find_all("tr")[4].find_all("td")[1].text.replace(" ", ""))

    player = PlayerTarget.objects.filter(name=player_name, server=server).first()
    last_player_snapshot = PrecisionSnapshot.objects.filter(player=player).last()
    # If this is the first player snapshot
    if last_player_snapshot is None:
        PrecisionSnapshot(hunting_field=hunting_field, trophies=trophies, player=player, processed=True).save()
    # If the player has a different hunting_field or trophies, save an unprocessed snapshot
    elif last_player_snapshot.hunting_field != hunting_field or last_player_snapshot.trophies != trophies:
        PrecisionSnapshot(hunting_field=hunting_field,
                          hunting_field_diff=hunting_field-last_player_snapshot.hunting_field,
                          trophies=trophies,
                          trophies_diff=trophies-last_player_snapshot.trophies,
                          player=player).save()

    return server, player_name, hunting_field, trophies


@app.task
def take_page_ranking_snapshot(server: str, page: int) -> None:
    credentials = FourmizzzCredentials.objects.filter(server=server).first()
    if not credentials:
        raise ValueError(f"No Fourmizzz credentials for sever {server}")

    cookies = {'PHPSESSID': credentials.cookie_session}
    url = f"http://{server}.fourmizzz.fr/classement2.php?page={page}&typeClassement=terrain"

    try:
        r = requests.get(url, cookies=cookies)
    except requests.exceptions.ConnectionError:
        raise requests.exceptions.ConnectionError(f"Could not open ranking page {page}")

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"class": "tab_triable"})
    for row in table.find_all("tr")[1:]:
        _, player_name, hunting_field, _, _, trophies = row.find_all("td")
        player_name = player_name.find("a").text
        hunting_field = int(hunting_field.text.replace(" ", ""))
        trophies = int(trophies.text.replace(" ", ""))

        last_player_snapshot = RankingSnapshot.objects.filter(server=server, player=player_name).last()
        if last_player_snapshot is None:
            RankingSnapshot(server=server, player=player_name, hunting_field=hunting_field, trophies=trophies).save()
        elif last_player_snapshot.hunting_field != hunting_field or last_player_snapshot.trophies != trophies:
            RankingSnapshot(server=server,
                            player=player_name,
                            hunting_field=hunting_field,
                            hunting_field_diff=hunting_field-last_player_snapshot.hunting_field,
                            trophies=trophies,
                            trophies_diff=trophies-last_player_snapshot.trophies).save()


@app.task
def process_player_precision_snapshots(unprocessed_player_snapshot_pk: List[int]) -> Tuple[List, List]:
    """
    Return a tuple of two list
    - First list: pk's of newly processed PrecisionSnapshot of the same PlayerTarget
    - Second list: Most probable list of RankingSnapshot pk's that has interacted with the specified PlayerTarget
    """
    def format_move(server, player_name, snapshot):
        credentials = FourmizzzCredentials.objects.filter(server=server).first()
        alliance_name = get_player_alliance(server, player_name, credentials.cookie_session)
        alliance = '-' if alliance_name is None else f"[{alliance_name}](http://{server}.fourmizzz.fr/classementAlliance.php?alliance={alliance_name})"
        hunting_field_before = '{:,}'.format(snapshot.hunting_field-snapshot.hunting_field_diff).replace(",", " ")
        hunting_field_after = '{:,}'.format(snapshot.hunting_field).replace(",", " ")
        hunting_field_diff = '{:+,}'.format(snapshot.hunting_field_diff).replace(",", " ")
        snapshot_time = timezone.localtime(snapshot.time, pytz.timezone(TIME_ZONE))
        return f"{snapshot_time.strftime('%d/%m/%Y %H:%M')} [{player_name}](http://{server}.fourmizzz.fr/Membre.php?Pseudo={player_name})({alliance}): {hunting_field_before} -> {hunting_field_after} ({hunting_field_diff})\n"

    # TODO handle both hunting field and trophies
    matched_simultaneous_snapshots_pk = list()

    unprocessed_player_snapshots = PrecisionSnapshot.objects.filter(pk__in=unprocessed_player_snapshot_pk)
    player_target = unprocessed_player_snapshots.last().player

    last_player_ranking_snapshot = RankingSnapshot.objects.filter(server=player_target.server, player=player_target.name).last()
    last_player_ranking_snapshot_time = last_player_ranking_snapshot.time
    last_player_ranking_snapshot_time -= datetime.timedelta(seconds=last_player_ranking_snapshot_time.second, microseconds=last_player_ranking_snapshot_time.microsecond)
    # TODO send error message if a precision snapshot is older than penultimate ranking snapshot
    if last_player_ranking_snapshot_time+datetime.timedelta(minutes=1) < unprocessed_player_snapshots.last().time:
        return unprocessed_player_snapshot_pk, matched_simultaneous_snapshots_pk

    # Get simultaneous ranking snapshots
    simultaneous_snapshots = RankingSnapshot.objects.filter(server=player_target.server, time__gt=last_player_ranking_snapshot_time, time__lt=last_player_ranking_snapshot_time+datetime.timedelta(minutes=1))
    simultaneous_snapshots = simultaneous_snapshots.exclude(pk=last_player_ranking_snapshot.pk)
    # Annotate with absolute value
    simultaneous_snapshots = simultaneous_snapshots.annotate(abs_hunting_field_diff=Func(F('hunting_field_diff'), function='ABS'))
    # Desc order by absolute value
    simultaneous_snapshots = simultaneous_snapshots.order_by("hunting_field").order_by("abs_hunting_field_diff").reverse()

    # Look for combinations explanation this snapshot change
    r = 1
    while not matched_simultaneous_snapshots_pk and r <= len(simultaneous_snapshots) and r < 4:
        for simultaneous_snapshots_pk in itertools.combinations(simultaneous_snapshots.values_list("pk", flat=True), r):
            simultaneous_snapshots_values = simultaneous_snapshots.filter(pk__in=simultaneous_snapshots_pk).values_list("hunting_field_diff", flat=True)
            if sum(simultaneous_snapshots_values) == -last_player_ranking_snapshot.hunting_field_diff:
                matched_simultaneous_snapshots_pk.extend(simultaneous_snapshots_pk)
                break
        r += 1

    notification_message = "Mouvements de la cible:\n"
    for precision_snapshot in unprocessed_player_snapshots:
        notification_message += format_move(precision_snapshot.player.server, precision_snapshot.player.name, precision_snapshot)

    notification_message += "\nMouvements correspondants:\n"
    for ranking_snapshot_pk in matched_simultaneous_snapshots_pk:
        ranking_snapshot = RankingSnapshot.objects.get(pk=ranking_snapshot_pk)
        notification_message += f"{format_move(ranking_snapshot.server, ranking_snapshot.player, ranking_snapshot)}\n"

    send_message(f"Mouvement de Tdc {player_target.server}", notification_message)
    unprocessed_player_snapshots.update(processed=True)

    return unprocessed_player_snapshot_pk, matched_simultaneous_snapshots_pk


@app.task
def take_snapshot() -> None:
    server_values = FourmizzzCredentials.objects.values_list('server', flat=True)
    player_targets = PlayerTarget.objects.filter(server__in=server_values)

    # Take both precision and ranking snapshots
    take_snapshot_subtasks = []
    for player_target in player_targets:
        server = player_target.server
        player_name = player_target.name
        subtask = take_player_precision_snapshot.si(server, player_name)
        take_snapshot_subtasks.append(subtask)
    for server in server_values:
        take_snapshot_subtasks.extend([take_page_ranking_snapshot.si(server, i_page) for i_page in range(1, 101)])

    # Process pending precison snapshots
    process_snapshot_subtasks = list()
    unprocessed_snapshots = PrecisionSnapshot.objects.filter(processed=False)
    unique_player_targets = PlayerTarget.objects.filter(pk__in=unprocessed_snapshots.distinct("player").values_list("player__pk", flat=True))
    for unique_player_target in unique_player_targets:
        unique_player_unprocessed_snapshots_pk = list(unprocessed_snapshots.filter(player=unique_player_target).values_list("pk", flat=True))
        process_snapshot_subtasks.append(process_player_precision_snapshots.si(unique_player_unprocessed_snapshots_pk))

    return chain(group(take_snapshot_subtasks), group(process_snapshot_subtasks)).delay()


# TODO add scheduled task to keep TargetPlayer.alliance synced
