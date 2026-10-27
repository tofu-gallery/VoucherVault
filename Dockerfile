# Tofu (2026-10-27): this file is Tofu's addition; it is not part of upstream VoucherVault.
#
# The image Tofu builds and runs for a copy of VoucherVault (framework preset `container`; see TOFU.md). It follows
# upstream's docker/Dockerfile, which stays as upstream wrote it. ghostscript draws the 1D barcodes (treepoem); gcc
# and libc6-dev build uWSGI. Upstream's cron, netcat, psql and unzip are left out: a copy starts no cron or Celery,
# and its start does not wait for the database with nc and psql. The image starts as root (Tofu's default port is
# 80); tofu-entrypoint.sh runs the app as www-data once uWSGI has bound the port. Every script runs through its
# interpreter, because Tofu's build keeps no file modes.
FROM python:3.12.13-slim

# The version upstream's footer shows (package.json).
ARG VERSION=1.30.5
# LANG: uWSGI's embedded Python takes its default text encoding from the locale, and django-pwa reads the service
# worker (which holds non-ASCII characters) with that default: under an ASCII locale /serviceworker.js answered
# 500. The base image sets C.UTF-8 too; saying it here keeps it whatever the base image does.
ENV VERSION=$VERSION \
    LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    DJANGO_SETTINGS_MODULE=myproject.tofu_settings

RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    gcc \
    libc6-dev \
    media-types && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

COPY requirements.txt /opt/app/requirements.txt
RUN pip install -r requirements.txt

COPY myproject /opt/app/myproject
COPY myapp /opt/app/myapp
COPY locale /opt/app/locale
COPY manage.py tofu-entrypoint.sh tofu-uwsgi.ini /opt/app/

# Upstream collected the static files at every start; once in the image is enough. www-data (uWSGI's workers) reads
# the app's files.
RUN python manage.py collectstatic --no-input --verbosity=0 && \
    chown -R www-data:www-data /opt/app

EXPOSE 80
STOPSIGNAL SIGTERM
CMD ["/bin/sh", "/opt/app/tofu-entrypoint.sh"]
