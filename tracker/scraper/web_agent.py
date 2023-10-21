import requests
from bs4 import BeautifulSoup

from time import sleep
from typing import List, Union, NoReturn


def player_exists(server: str, player_name: str, cookie_session: str) -> bool:
    cookies = {'PHPSESSID': cookie_session}
    url = f"http://{server}.fourmizzz.fr/Membre.php?Pseudo={player_name}"
    r = requests.get(url, cookies=cookies)
    soup = BeautifulSoup(r.text, "html.parser")
    if "Aucun joueurs avec le pseudo" in soup.find(id="centre").text:
        return False
    return True


def validate_fourmizzz_cookie_session(server: str, cookie_session: str) -> bool:
    url = f"http://{server}.fourmizzz.fr/alliance.php"
    cookies = {'PHPSESSID': cookie_session}
    r = requests.get(url, cookies=cookies)
    soup = BeautifulSoup(r.text, "html.parser")
    menu = soup.find(id="centre")
    text = menu.find("p").text
    return "Session expirée, Merci de vous reconnecterRetour" not in text


def get_alliance_members(server: str, alliance: str, cookie_session: str) -> List[str]:
    url = f"http://{server}.fourmizzz.fr/classementAlliance.php?alliance={alliance}"
    cookies = {'PHPSESSID': cookie_session}

    r = requests.get(url, cookies=cookies)
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find(id="tabMembresAlliance")
    rows = table.find_all("tr")[1:]
    member_list = list(row.find_all("td")[2].text for row in rows)

    return member_list


def get_player_alliance(server: str, player_name: str, cookie_session: str) -> Union[str, NoReturn]:
    """
    Returns the alliance in which the player is
    """
    cookies = {'PHPSESSID': cookie_session}
    url = f"http://{server}.fourmizzz.fr/Membre.php?Pseudo={player_name}"
    r = requests.get(url, cookies=cookies)
    soup = BeautifulSoup(r.text, "html.parser")
    try:
        return soup.find("div", {"class": "boite_membre"}).find("table").find("tr").find_all("td")[1].find("a").text
    except AttributeError:
        return
