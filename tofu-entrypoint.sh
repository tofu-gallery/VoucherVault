#!/bin/sh
# Tofu (2026-10-27): this file is Tofu's addition; it is not part of upstream VoucherVault.
#
# Starts a copy of VoucherVault on Tofu (the Dockerfile's CMD, run through /bin/sh, since Tofu's build keeps no file
# modes). In place of upstream's docker/entrypoint.sh:
#   1. `manage.py tofu_schema` brings the database's schema up to date, one start at a time, since Tofu can start
#      several instances at once, and makes the first account once the owner has saved VOUCHERVAULT_ADMIN_PASSWORD
#      (myapp/tofu_schema.py and TOFU.md say how). Tofu's database is new on the first start, so a failure is retried a
#      few times before the container gives up. Upstream ran makemigrations, migrate, collectstatic (now in the
#      Dockerfile) and printed a random admin password to the log; it also waited for the database with nc and psql.
#   2. Upstream's Celery worker and beat (expiry notifications, through Redis) are not started: Tofu runs
#      request-driven apps that scale to zero, with no process that runs all the time and no Redis.
#   3. uWSGI serves the app on PORT, which Tofu sets (80 without it). Started as root, it binds PORT and then runs the
#      app as www-data, as upstream's image did (myproject/tofu_settings.py names a missing client certificate for
#      libpq, which www-data would otherwise look for under HOME, /root).
# Settings come from myproject.tofu_settings (DJANGO_SETTINGS_MODULE in the Dockerfile).
set -eu

cd "$(dirname "$0")"

PORT="${PORT:-80}"
export PORT

attempt=1
until python manage.py tofu_schema; do
	if [ "$attempt" -ge 5 ]; then
		echo "tofu-entrypoint: the schema step failed $attempt times, giving up" >&2
		exit 1
	fi
	echo "tofu-entrypoint: the schema step failed (attempt $attempt of 5), retrying in 5 seconds" >&2
	attempt=$((attempt + 1))
	sleep 5
done

if [ "$(id -u)" = "0" ]; then
	# uWSGI reads UWSGI_* variables as options: the master binds PORT as root, then drops to www-data before it loads
	# the app (the order tofu-gallery/linkding uses on Tofu).
	UWSGI_UID=www-data
	UWSGI_GID=www-data
	UWSGI_DROP_AFTER_INIT=true
	export UWSGI_UID UWSGI_GID UWSGI_DROP_AFTER_INIT
fi

exec uwsgi --ini tofu-uwsgi.ini
