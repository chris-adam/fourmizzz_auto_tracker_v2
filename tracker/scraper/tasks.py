from typing import Tuple, Dict
import datetime

from celery import group, chain
import requests
from bs4 import BeautifulSoup

from tracker.celery import app
from scraper.models import FourmizzzCredentials, PlayerTarget, PrecisionSnapshot, RankingSnapshot


@app.task
def take_player_precision_snapshot(server: str, player_name: str) -> Tuple[int, int]:
    credentials = FourmizzzCredentials.objects.filter(server="s1").first()
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
def take_page_ranking_snapshot(server: str, page: int) -> Tuple[int, int]:
    credentials = FourmizzzCredentials.objects.filter(server="s1").first()
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
def process_precision_snapshots() -> Dict:
    # TODO split this in a bunch of tasks, one per unprocessed snapshot
    unprocessed_snapshots = PrecisionSnapshot.objects.filter(processed=False)
    matched_moves = dict()
    for unprocessed_snapshot in unprocessed_snapshots:
        player_target = unprocessed_snapshot.player

        last_player_ranking_snapshot_time = RankingSnapshot.objects.filter(server=player_target.server, player=player_target.name).last().time
        last_player_ranking_snapshot_time -= datetime.timedelta(seconds=last_player_ranking_snapshot_time.second, microseconds=last_player_ranking_snapshot_time.microsecond)
        if last_player_ranking_snapshot_time+datetime.timedelta(minutes=1) < unprocessed_snapshot.time:
            continue

        simultaneous_snapshots = RankingSnapshot.objects.filter(time__gt=last_player_ranking_snapshot_time, time__lt=last_player_ranking_snapshot_time+datetime.timedelta(minutes=1))

        # TODO handle both hunting field and trophies
        matching_simultaneous_snapshots = simultaneous_snapshots.filter(hunting_field_diff=-unprocessed_snapshot.hunting_field_diff)
        matched_moves[unprocessed_snapshot] = matching_simultaneous_snapshots
        unprocessed_snapshot.processed = True
        unprocessed_snapshot.save()

    # TODO return list of moves and send to notification system
    # return matched_moves  # Broken right now as celery can't save this type of object


@app.task
def take_snapshot() -> None:
    server_values = FourmizzzCredentials.objects.values_list('server', flat=True)
    player_targets = PlayerTarget.objects.filter(server__in=server_values)

    subtasks = []

    for player_target in player_targets:
        server = player_target.server
        player_name = player_target.name
        subtask = take_player_precision_snapshot.si(server, player_name)
        subtasks.append(subtask)

    for server in server_values:
        subtasks.extend([take_page_ranking_snapshot.si(server, i_page) for i_page in range(1, 101)])

    chain(group(subtasks), process_precision_snapshots.si()).delay()


# TODO add scheduled task to keep TargetPlayer.alliance synced
