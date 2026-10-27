# Tofu (2026-10-27): this file is Tofu's addition; it is not part of upstream VoucherVault.
#
# Settings for Tofu's app gallery copy of VoucherVault (see TOFU.md at the repository root): upstream's settings.py,
# then what a copy on Tofu needs. The image sets DJANGO_SETTINGS_MODULE=myproject.tofu_settings; without it,
# manage.py and the WSGI module still use upstream's myproject.settings unchanged. Where upstream reads an
# environment variable, a value the owner saves on the app's Keys & settings page still wins over the defaults below.
import hashlib
import os
import pwd
from urllib.parse import parse_qsl, unquote, urlsplit

from .settings import *  # noqa: F401,F403


def _flag(name, default):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("true", "1", "yes")


# The database. Tofu saves DATABASE_URL (postgresql://user:password@host:6543/postgres?sslmode=require), which goes
# through a transaction pooler. Upstream reads DB_ENGINE and POSTGRES_* instead, and falls back to a SQLite file a
# copy could not keep: a copy has no lasting disk, so every restart would lose it.
_database_url = os.environ.get("DATABASE_URL", "")
# The libpq connection parameters a URL's query may carry; anything else (another tool's own flag) is left out,
# because libpq refuses a parameter it does not know.
_LIBPQ_PARAMS = {
    "sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl", "connect_timeout", "application_name", "options",
    "target_session_attrs", "keepalives", "keepalives_idle", "keepalives_interval", "keepalives_count",
}


# Whenever libpq opens a TLS connection (sslmode=require makes every one TLS), it first looks for a client
# certificate: the file sslcert or PGSSLCERT names, or else ~/.postgresql/postgresql.crt, with ~ taken from HOME. It
# goes on without one when that file does not exist, but any other error, such as "Permission denied", stops the
# connection. uWSGI's workers run as www-data while HOME is still /root, which www-data cannot search (the same trap
# tofu-gallery/linkding met on Tofu: every page that read the database answered 500). So unless a certificate is
# named, or this process finds one at the default place, sslcert names a file that does not exist in this folder,
# which every process that runs the app can search, and libpq goes on without a client certificate, exactly as when
# the default file is absent. TLS itself is unchanged: sslmode and the server's certificate checks stay as they are.
def _client_certificate_options():
    if os.environ.get("PGSSLCERT"):
        return {}
    try:
        home = os.environ.get("HOME") or pwd.getpwuid(os.geteuid()).pw_dir
        os.stat(os.path.join(home, ".postgresql", "postgresql.crt"))
        return {}
    except (KeyError, OSError):
        here = os.path.dirname(os.path.abspath(__file__))
        return {"sslcert": os.path.join(here, "tofu-no-client-certificate.crt")}


if _database_url and os.environ.get("DB_ENGINE") in (None, "", "postgres"):
    _url = urlsplit(_database_url)
    if _url.scheme in ("postgres", "postgresql"):
        _options = {k: v for k, v in parse_qsl(_url.query) if k in _LIBPQ_PARAMS}
        _options.setdefault("connect_timeout", "10")
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": unquote(_url.path.lstrip("/")) or "postgres",
                "USER": unquote(_url.username or ""),
                "PASSWORD": unquote(_url.password or ""),
                "HOST": _url.hostname or "",
                "PORT": str(_url.port or ""),
                "OPTIONS": {**_client_certificate_options(), **_options},
                # A transaction pooler keeps no server-side cursor from one transaction to the next (psycopg2 never
                # prepares statements, so nothing else needs turning off).
                "DISABLE_SERVER_SIDE_CURSORS": True,
                # Each worker thread keeps its connection for a minute, checked before reuse, instead of opening a new
                # TLS connection to the pooler for every request.
                "CONN_MAX_AGE": 60,
                "CONN_HEALTH_CHECKS": True,
            }
        }
        DB_ENGINE = "postgres"

# Upstream makes a random SECRET_KEY in every process when none is set, and Tofu runs several processes, so a
# session made by one would be refused by the next. A copy derives its key from DATABASE_URL, which Tofu keeps as a
# hidden value: the SHA-256 of "vouchervault-secret-key:" and the whole URL. Changing DATABASE_URL later changes the
# key, which signs everyone out. A SECRET_KEY the owner saves as a hidden value always wins.
if os.environ.get("SECRET_KEY"):
    SECRET_KEY = os.environ["SECRET_KEY"]
elif _database_url:
    SECRET_KEY = hashlib.sha256(("vouchervault-secret-key:" + _database_url).encode()).hexdigest()

# Tofu serves the copy over HTTPS at its own address, through Tofu's proxy, which says in X-Forwarded-Proto and
# X-Forwarded-Host which scheme and address the visitor used.
#
# Any Host header is answered. Before Tofu puts a new deployment online, it opens the deployment's home page at that
# deployment's own address, which is neither the copy's address nor one DOMAIN names, and it refuses a deployment that
# answers 400 there. Upstream's ALLOWED_HOSTS, made from DOMAIN, answered that request 400 (DisallowedHost), so a copy's
# first deployment was refused and never went online. tofu-gallery/babybuddy and linkding answer any host on Tofu too.
# What the check guarded stays guarded: nothing in the app builds a link from the Host header but Django's
# password-reset email, which names DOMAIN's address instead (myproject/tofu_urls.py), and Django's CSRF check still
# refuses a form posted from another site. Upstream's DOMAIN (which a gallery copy sets to its own address) still makes
# CSRF_TRUSTED_ORIGINS in settings.py; a domain connected later is added to DOMAIN, comma-separated.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
ALLOWED_HOSTS = ["*"]

# The copy's own address, the first of DOMAIN's (read as upstream reads it), which Django's password-reset email names
# in its link and its text in place of the request's Host header: myproject/tofu_urls.py puts that page in front of
# upstream's URLs.
_address = DOMAIN.split(",")[0].strip().rstrip("/").replace("http://", "").replace("https://", "") or "localhost"
TOFU_EMAIL_ADDRESS = {"protocol": "https", "domain": _address, "site_name": _address}
ROOT_URLCONF = "myproject.tofu_urls"

# Cookies only over HTTPS, which a copy always has; SECURE_COOKIES=false (upstream's setting) turns it off.
SECURE_COOKIES = _flag("SECURE_COOKIES", True)
SESSION_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SECURE = SECURE_COOKIES
if SECURE_COOKIES:
    # One year of HSTS for the copy's own address, but not preloaded and not for every subdomain: a domain connected
    # later may have other subdomains that are not this app's.
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_PRELOAD = False
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
else:
    SECURE_HSTS_SECONDS = 0

# A wallet is opened at the till on a phone, so upstream's 30 minutes (and a session that ends with the browser) would
# ask for the password nearly every time. A copy keeps a session for 14 days unless the owner saves
# SESSION_COOKIE_AGE (minutes) or SESSION_EXPIRE_AT_BROWSER_CLOSE, upstream's own settings.
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE") or 14 * 24 * 60) * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = _flag("SESSION_EXPIRE_AT_BROWSER_CLOSE", False)

# Upstream's default time zone is Europe/Berlin; a copy's owner can be anywhere, so it is UTC unless TZ is saved
# (a public setting such as America/New_York).
TIME_ZONE = os.environ.get("TZ") or "UTC"

# Expiry notifications are sent by Celery's worker and beat, which need Redis and a process that runs all the time.
# Tofu runs request-driven apps that scale to zero, so a copy starts neither, and django_celery_beat (the schedule's
# tables) is left out. The notification page says so (TOFU_EXPIRY_ALERTS_OFF); its test button still sends.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django_celery_beat"]
TOFU_EXPIRY_ALERTS_OFF = True

# A copy has no lasting disk: an attached file would be written to the server's disk, lost at the next restart while
# the database still names it. So attachments stay off (the item forms have no file field; myapp/tofu.py).
VOUCHERVAULT_UPLOADS = False

# Upstream's pages loaded shop logos from logo.dev with the upstream author's own token, committed in the templates. A
# copy shows logos only once its owner saves their own logo.dev publishable key as LOGO_DEV_TOKEN.
LOGO_DEV_TOKEN = os.environ.get("LOGO_DEV_TOKEN", "").strip()

# VoucherVault is GPL-3.0: every page, the sign-in page included, links to the copy's own source. A gallery copy sets
# SOURCE_URL to the exact commit it holds; without it, the fork.
SOURCE_URL = os.environ.get("SOURCE_URL", "").strip() or "https://github.com/tofu-gallery/VoucherVault"

# The first account: while the copy has none, a start makes the administrator "admin" with the password the owner
# saves as the hidden value VOUCHERVAULT_ADMIN_PASSWORD (myapp/tofu_schema.py); the sign-in page says how until then.
TOFU_ADMIN_USERNAME = "admin"
TOFU_ADMIN_PASSWORD_SETTING = "VOUCHERVAULT_ADMIN_PASSWORD"
TOFU_ADMIN_PASSWORD_MIN_LENGTH = 8

TEMPLATES[0]["OPTIONS"]["context_processors"].append("myapp.tofu.context")

# Django's warnings and errors go to the app's runtime log (standard error), where the owner can read them on Tofu: a
# form the CSRF check refused, with the reason, a host not in ALLOWED_HOSTS, a request's server error.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"django": {"handlers": ["console"], "level": "WARNING"}},
}
