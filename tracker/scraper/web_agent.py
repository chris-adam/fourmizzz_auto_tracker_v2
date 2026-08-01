import datetime
import logging
from typing import Dict
from typing import List
from typing import NoReturn
from typing import Optional
from typing import Union

import requests
from bs4 import BeautifulSoup
from django.db import transaction
from django.utils import timezone
from scraper.utils import send_error

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
# Per login attempt, and _login makes at most two. Both happen while the row lock is held, so the
# worst case (2 x 8s) has to stay clear of CELERY_TASK_TIME_LIMIT (30s) for the tasks queueing
# behind it. A healthy login answers in well under a second.
LOGIN_TIMEOUT = 8
# Do not attempt a login more often than this, so bad credentials cannot turn into a login flood
# against the game server (tasks run as often as every 3 seconds).
LOGIN_COOLDOWN = datetime.timedelta(minutes=1)
# Text the game shows instead of the page content once the session is gone
SESSION_EXPIRED_MARKER = "Session expirée"


class SessionExpired(Exception):
    """
    The game session is gone and this request cannot be served.

    Raised quietly: an expiry hits every running task at once, so only the task that actually
    owned the login attempt reports to Discord.
    """

    def __init__(self, server, reason: str = ""):
        self.server = server
        self.reason = reason
        super().__init__(
            f"Session expired on server '{server.name}'{f': {reason}' if reason else ''}"
        )


class LoginFailed(Exception):
    """A login attempt we owned could not be carried out. Worth reporting."""


class LoginRefused(LoginFailed):
    """The game answered, but would not log us in. Almost always wrong credentials."""


class LoginUnreachable(LoginFailed):
    """The login request could not be completed at all: timeout, DNS, connection refused."""


def _url(server, path: str) -> str:
    return f"http://{server.name}.fourmizzz.fr/{path.lstrip('/')}"


def _get(server, path: str, cookies: Dict[str, str]) -> BeautifulSoup:
    r = requests.get(_url(server, path), cookies=cookies, timeout=REQUEST_TIMEOUT)
    return BeautifulSoup(r.text, "html.parser")


def _session_expired(soup: BeautifulSoup) -> bool:
    """
    Whether this page is the game telling us we are logged out.

    Deliberately narrow: only an explicit expiry notice or the login form counts. An
    unrecognisable page (game down, HTTP 500, network hiccup) must NOT be read as an expiry,
    otherwise an outage would turn into a login storm.
    """
    if soup.find(id="loginForm") is not None:
        return True
    centre = soup.find(id="centre")
    return centre is not None and SESSION_EXPIRED_MARKER in centre.text


def _post_login(server, jar: Dict[str, str]) -> Dict[str, str]:
    # A short lived Session, so cookies set across the login redirects are all collected.
    with requests.Session() as session:
        session.cookies.update(jar)
        session.post(
            _url(server, "index.php?connexion=1"),
            data={
                "serveur": f"{server.name}.fourmizzz.fr",
                "pseudo": server.username,
                "mot_passe": server.password,
                "souvenir": "on",  # "remember me", yields a long lived cookie
                "connexion": "Connexion",
            },
            timeout=LOGIN_TIMEOUT,
        )
        return requests.utils.dict_from_cookiejar(session.cookies)


def _login(server, jar: Dict[str, str]) -> Dict[str, str]:
    """
    Log in and return the resulting cookie jar.

    The current jar is sent along with the login POST on purpose. The game runs PHP 5.3, which
    predates `session.use_strict_mode`, so it accepts a client-supplied PHPSESSID and rebinds the
    login to the session id we already hold instead of issuing a new one. That keeps this session
    shared with the browser session it was seeded from. If the game does hand out a new id, we
    simply store that instead -- nothing here depends on the id staying the same.

    Reusing the id has a cost, though: PHP serialises every request that shares a session id on the
    session file lock, and this tracker keeps that id busy (a ranking sweep is ~100 requests a
    minute, the MV check runs every 3 seconds). So the login can end up queued behind our own
    scraping and time out. If that happens we log in again with no cookies at all, which starts a
    private session that nothing else is holding. Sharing is a nice-to-have; logging in is not.
    """
    if not server.username or not server.password:
        raise LoginFailed(f"no credentials configured for server '{server.name}'")

    logger.info("Logging in to %s as '%s'", server.name, server.username)
    try:
        new_jar = _post_login(server, jar)
    except requests.Timeout:
        if not jar:
            raise LoginUnreachable(
                f"login to server '{server.name}' timed out after {LOGIN_TIMEOUT}s"
            )
        logger.warning(
            "Login to %s timed out while reusing the current session id (most likely queued "
            "behind our own requests on the PHP session lock); retrying with a fresh session",
            server.name,
        )
        try:
            # No cookies: the game issues a brand new session id, uncontended.
            return _post_login(server, {})
        except requests.RequestException as e:
            raise LoginUnreachable(f"login to server '{server.name}' failed: {e}")
    except requests.RequestException as e:
        raise LoginUnreachable(f"login to server '{server.name}' failed: {e}")

    # Merge rather than replace: the game only re-sends the cookies it wants to change.
    return {**jar, **new_jar}


def refresh_cookies(server) -> bool:
    """
    Renew `server.cookies` in place.

    An expiry hits every running task at once (up to ~100 ranking pages per server per minute), so
    exactly one of them must log in. There is no shared cache to coordinate through -- the broker
    is RabbitMQ and CACHES is unconfigured, so Django's LocMemCache is per process -- hence a
    Postgres row lock.

    Returns True if this call performed the login, and is therefore the one responsible for
    reporting a failure; False if it adopted a jar another process had just obtained.
    """
    if server.pk is None:
        # Not saved yet (admin form validation): no row to lock, nothing to share.
        server.cookies = _login(server, server.cookies or {})
        return True

    try:
        with transaction.atomic():
            # `server.__class__` instead of importing FourmizzzServer: models.py imports this
            # module, so a module level import of models would be circular.
            locked = server.__class__.objects.select_for_update().get(pk=server.pk)

            # Compare-and-swap on the timestamp rather than on the cookie value: a successful
            # login usually returns the *same* PHPSESSID (see _login), so the cookie cannot tell
            # us whether a peer already refreshed. The timestamp always changes.
            if locked.last_login_attempt != server.last_login_attempt:
                logger.info(
                    "Another process just refreshed the %s session, reusing it", server.name
                )
                server.cookies = locked.cookies
                server.last_login_attempt = locked.last_login_attempt
                return False

            if (
                locked.last_login_attempt is not None
                and timezone.now() - locked.last_login_attempt < LOGIN_COOLDOWN
            ):
                raise SessionExpired(server, "a login was just attempted, backing off")

            # The login runs while the row is still locked, so the new jar and its timestamp
            # become visible together. Tasks queueing behind us then adopt a jar that actually
            # works; releasing the lock first would let them adopt the stale one and fail.
            jar = _login(locked, locked.cookies)

            now = timezone.now()
            locked.cookies = jar
            locked.last_login_attempt = now
            locked.save(update_fields=["cookies", "last_login_attempt"])

            server.cookies = jar
            server.last_login_attempt = now
            return True
    except LoginFailed:
        # The transaction above rolled back, so nothing recorded the attempt. Stamp it separately,
        # or the cooldown could never back off a login that keeps failing.
        now = timezone.now()
        server.__class__.objects.filter(pk=server.pk).update(last_login_attempt=now)
        server.last_login_attempt = now
        raise


def fetch(server, path: str) -> BeautifulSoup:
    """
    Fetch a game page, logging back in once if the session has expired.

    Every request to the game goes through here, so an expiry is caught before the HTML reaches
    any parsing code.
    """
    soup = _get(server, path, server.cookies)
    if not _session_expired(soup):
        return soup

    logger.info("Session expired on %s while fetching %s", server.name, path)
    try:
        we_logged_in = refresh_cookies(server)
    except LoginFailed as e:
        # We owned the attempt, so we are the one that reports it. The cooldown recorded by
        # _claim_login keeps this to one report per minute per server.
        logger.error("%s", e)
        send_error(
            category=server.name,
            thread="login",
            title=f"Could not log in to server '{server.name}': {e}",
        )
        raise SessionExpired(server, str(e))

    soup = _get(server, path, server.cookies)
    if not _session_expired(soup):
        return soup

    if we_logged_in:
        # The login went through but the game still treats us as logged out: almost always a wrong
        # username or password. Report it, or the tracker would die silently.
        send_error(
            category=server.name,
            thread="login",
            title=f"Logged in to server '{server.name}' but the game still refuses the session. "
            f"Check the username and password in the admin.",
        )
    raise SessionExpired(server, "still logged out after logging in again")


def login_and_validate(server) -> Dict[str, str]:
    """
    Log in and confirm we reach a page that requires being logged in, returning the cookie jar.

    Used to check credentials from the admin form, where the server may not be saved yet, so this
    deliberately touches neither the row lock nor the database.
    """
    jar = _login(server, server.cookies or {})
    if _session_expired(_get(server, "alliance.php", jar)):
        raise LoginRefused("the game refused these credentials")
    return jar


def player_exists(server, player_name: str) -> bool:
    soup = fetch(server, f"Membre.php?Pseudo={player_name}")
    if "Aucun joueurs avec le pseudo" in soup.find(id="centre").text:
        return False
    return True


def get_alliance_members(server, alliance: str) -> List[str]:
    soup = fetch(server, f"classementAlliance.php?alliance={alliance}")
    table = soup.find(id="tabMembresAlliance")
    if table is None:
        return []
    rows = table.find_all("tr")[1:]
    member_list = list(row.find_all("td")[2].text for row in rows)

    return member_list


def get_player_alliance(server, player_name: str) -> Union[Optional[str], NoReturn]:
    """
    Returns the alliance in which the player is, or None if the player has no alliance
    """
    soup = fetch(server, f"Membre.php?Pseudo={player_name}")
    try:
        boite_membre = soup.find("div", {"class": "boite_membre"}).find("table")
        if "Alliance" in boite_membre.find_all("tr")[0].text:
            alliance_tr = boite_membre.find_all("tr")[0]
        else:
            alliance_tr = boite_membre.find_all("tr")[1]
        alliance_td = alliance_tr.find_all("td")[1].find("a")
        return None if not alliance_td else alliance_td.text
    except Exception:
        send_error(
            category=server.name,
            thread="get_player_alliance",
            title=f"Alliance not found for player '{player_name}' on server '{server.name}'",
        )
        raise
