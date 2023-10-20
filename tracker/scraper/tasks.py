from tracker.celery import app
from celery import group, shared_task, chain
import requests
from bs4 import BeautifulSoup

from typing import List, Tuple

from scraper.models import FourmizzzCredentials, PlayerTarget, PrecisionSnapshot


@shared_task
def add(x, y):
    return x + y


@app.task
def get_player_hunting_field_and_trophies(server: str, player_name: str) -> Tuple[int, int]:
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

    return server, player_name, hunting_field, trophies


@app.task
def save_get_player_hunting_field_and_trophies(player_hunting_field_and_trophies: List[List]) -> List[List]:
    for player_snapshot in player_hunting_field_and_trophies:
        server, player_name, hunting_field, trophies = player_snapshot
        player = PlayerTarget.objects.filter(name=player_name, server=server).first()
        last_player_snapshot = PrecisionSnapshot.objects.filter(player=player).last()
        if last_player_snapshot is None or last_player_snapshot.hunting_field != hunting_field or last_player_snapshot.trophies != trophies:
            PrecisionSnapshot(hunting_field=hunting_field, trophies=trophies, player=player).save()
            # TODO create entry in queue model

    return player_hunting_field_and_trophies


def take_precision_snapshot():
    server_values = FourmizzzCredentials.objects.values_list('server', flat=True)
    player_targets = PlayerTarget.objects.filter(server__in=server_values)

    subtasks = []

    for player_target in player_targets:
        server = player_target.server
        player_name = player_target.name
        subtask = get_player_hunting_field_and_trophies.s(server, player_name)
        subtasks.append(subtask)

    return chain(group(subtasks), save_get_player_hunting_field_and_trophies.s()).delay().get()
