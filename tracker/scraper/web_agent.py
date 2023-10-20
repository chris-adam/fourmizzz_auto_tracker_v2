from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
import requests
from bs4 import BeautifulSoup

from time import sleep
from typing import List, Tuple


def wait_for_elem(driver, elem, by, timeout=5, max_retries=5):
    for i in range(max_retries):
        try:
            return WebDriverWait(driver, timeout).until(ec.presence_of_element_located((by, elem)))
        except (StaleElementReferenceException, TimeoutException):
            sleep(2)
    raise TimeoutException()


def validate_fourmizzz_credentials(server: str, username: str, password: str, cookie_session: str) -> bool:
    url = f"http://{server}.fourmizzz.fr"

    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    try:
        driver = webdriver.Chrome(options=options)
    except OSError:
        driver = webdriver.Chrome("/usr/lib/chromium-browser/chromedriver", options=options)

    try:
        driver.get(url)
        driver.add_cookie({'name': "PHPSESSID", 'value': cookie_session})

        # Type username
        wait_for_elem(driver, "//*[@id='loginForm']/table/tbody/tr[2]/td[2]/input", By.XPATH).click()
        wait_for_elem(driver, "//*[@id='loginForm']/table/tbody/tr[2]/td[2]/input", By.XPATH).send_keys(username)

        # Type password
        wait_for_elem(driver, "//*[@id='loginForm']/table/tbody/tr[3]/td[2]/input", By.XPATH).click()
        wait_for_elem(driver, "//*[@id='loginForm']/table/tbody/tr[3]/td[2]/input", By.XPATH).send_keys(password)

        wait_for_elem(driver, "//*[@id='loginForm']/input[2]", By.XPATH).click()

        wait_for_elem(driver, "/html/body/div[4]/table/tbody/tr[1]/td[4]/form/table/tbody/tr/td[1]/div[1]/input",
                      By.XPATH, timeout=3, max_retries=1)
    except TimeoutException:
        return False
    finally:
        driver.quit()

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


def get_player_alliance(server: str, player_name: str, cookie_session: str) -> str:
    """
    Returns the alliance in which the player is
    """
    cookies = {'PHPSESSID': cookie_session}
    url = f"http://{server}.fourmizzz.fr/Membre.php?Pseudo={player_name}"
    r = requests.get(url, cookies=cookies)
    soup = BeautifulSoup(r.text, "html.parser")
    return soup.find("div", {"class": "boite_membre"}).find("table").find("tr").find_all("td")[1].find("a").text
