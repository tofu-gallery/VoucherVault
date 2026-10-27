# VoucherVault on Tofu

This branch (`tofu`) is Tofu's copy of [VoucherVault](https://github.com/l4rm4nd/VoucherVault) by l4rm4nd (LRVT),
changed only as far as running in Tofu's app gallery needs. The branch `main` follows upstream untouched. A gallery
copy takes the commit tagged `pin/<date>` on this branch.

## What it is

A wallet for loyalty cards, gift cards, vouchers and coupons, made for phones. Each item keeps its code and shows it
as a QR code or a barcode at the till (EAN-13, Code 128, Code 39, UPC, PDF417, Data Matrix, Aztec and more), with its
PIN behind a tap, its balance and expiry date, a history of what was spent, and a camera scanner to read a card's code
in. Items can be shared with the other people who have an account in the same copy (a family), and the dashboard adds
up what is left. It installs on a phone's home screen (a PWA) and can keep pages for offline use.

## How Tofu runs it

| | |
|---|---|
| Preset | `container` (the root `Dockerfile`) |
| Root folder | the repository root |
| Build | `Dockerfile`: Python 3.12 with ghostscript (treepoem draws the 1D barcodes with it), `pip install -r requirements.txt` (uWSGI is compiled, hence gcc), then `manage.py collectstatic` once |
| Start | `CMD ["/bin/sh", "/opt/app/tofu-entrypoint.sh"]`: `manage.py tofu_schema`, then uWSGI on `PORT` (Tofu sets 80) with `tofu-uwsgi.ini` |
| Settings module | `myproject.tofu_settings` (`DJANGO_SETTINGS_MODULE` in the Dockerfile), which imports upstream's `myproject/settings.py` and changes what a copy needs |
| Database | yes: Tofu's managed PostgreSQL. Tofu saves `DATABASE_URL` (the transaction pooler, `?sslmode=require`); the app reads it in `myproject/tofu_settings.py` |
| Migrations | the app makes its schema at start, not at build: no `supabase/migrations` files (see *Start-up when several starts run at once*) |
| Public settings a copy gets | `DOMAIN` = the copy's own address (addressEnv); `SOURCE_URL` = this pin's source on GitHub (sourceEnv) |
| Hidden values only the owner can save | `VOUCHERVAULT_ADMIN_PASSWORD` (makes the first account; see below), `LOGO_DEV_TOKEN` (optional: shop logos) |
| Runs as | the image starts as root; uWSGI binds `PORT`, then drops to `www-data` before it loads the app, as upstream's image ran it as `www-data` |

Every file runs through its interpreter (`/bin/sh tofu-entrypoint.sh`, `python manage.py`), because Tofu's build
gives every file of a copy the mode 0644: nothing in the repository needs to be executable.

Optional public settings the owner can save on the app's Keys & settings page (upstream's own names):
`SESSION_COOKIE_AGE` (minutes; a copy's default is 14 days), `SESSION_EXPIRE_AT_BROWSER_CLOSE`, `TZ` (a copy's default
is UTC, for example `America/New_York`), `EXPIRY_THRESHOLD_DAYS` (what "expiring soon" means; 30 by default),
`CSP_FRAME_ANCESTORS`. Upstream's OIDC single sign-on (`OIDC_ENABLED` and the `OIDC_*` settings, with
`OIDC_RP_CLIENT_SECRET` saved hidden) still works for an owner who runs an identity provider.

### The first account

VoucherVault has no sign-up page: the administrator adds every other person. Upstream made an administrator `admin`
with a random password and printed it to the container's log at the first start, which a copy's owner never reads,
and a new copy is online at a public address before its owner first opens it. So a copy has no account at first, and
its sign-in page says so: *"This VoucherVault has no account yet. Nobody can sign in until its owner makes the first
one. On Tofu, open this app's Keys & settings page, add VOUCHERVAULT_ADMIN_PASSWORD with the password you want (at
least 8 characters) and turn on Hide this value after saving. Then deploy the app again and sign in here with the
username admin."*

At the next start, while the database has no account at all, `myapp/tofu_schema.py` makes the superuser `admin` with
that password. Once any account exists, the setting changes nothing: the owner changes the password inside the app
(user menu, Change Password). A password shorter than 8 characters makes no account, and the sign-in page says that
instead. Nobody else can take a new copy first: there is no sign-up and no setup page.

To add a family member, the owner opens Admin Settings (user menu) or `/admin/`, Users, Add user, and tells them
their username and password; items are shared from an item's Share button. Only an administrator can add people.

### Start-up when several starts run at once

Tofu can start several instances of a new deployment within a second or two, all against the same new, empty
database. Upstream's start ran `makemigrations` and `migrate` in each. `manage.py tofu_schema` (`myapp/tofu_schema.py`,
which follows tofu-gallery/babybuddy's, checked on Tofu) instead:

1. opens a connection of its own and takes `pg_advisory_xact_lock` as the first statement of a transaction that stays
   open for the whole step, so one start at a time does the schema work and the others wait for it (through the
   transaction pooler an open transaction keeps one server connection, and the lock ends with the transaction, also
   when a start dies; a session-level lock would not hold through the pooler);
2. on an empty database, applies `myapp/tofu_schema.sql` in one statement: the schema and the rows `migrate` leaves
   on a new database (content types and permissions), with `django_migrations` filled in. It is used only while every
   migration file it was made from is unchanged (their SHA-256 sums are in its first line); otherwise, and for
   migrations newer than it, `migrate` runs as upstream's start did. A database that is up to date skips `migrate`;
3. turns row-level security on, with no policy, for every table of the app that lacks it, when the database has
   Supabase's Data API roles (`anon`, `authenticated`): every database Tofu makes today opens new tables in `public`
   to those roles. The app's own connection owns the tables and is not limited by it;
4. makes the first account (above).

The snapshot is remade from an empty scratch database after a change to the models' migrations:
`DJANGO_SETTINGS_MODULE=myproject.tofu_settings DATABASE_URL=... python manage.py tofu_schema --make-snapshot`
(needs `pg_dump`). `tofu-entrypoint.sh` retries a failed step up to five times, 5 seconds apart.

## What we changed, and why

Every commit on `tofu` says why in its message. In short:

- **Root `Dockerfile`, `tofu-entrypoint.sh`, `tofu-uwsgi.ini`** (new): upstream's image from `docker/Dockerfile`
  (which stays as upstream wrote it), listening on `PORT` and started as root so it can bind port 80; no cron,
  netcat, psql or unzip; static files collected once at build; no wait loop for the database (`nc`, `psql`) and no
  Celery worker or beat; a UTF-8 locale (`LANG=C.UTF-8`), without which django-pwa answered 500 for the service worker.
- **`myproject/tofu_settings.py`** (new): the database from `DATABASE_URL` (TLS as the URL says, no server-side
  cursors, connections kept a minute and checked before reuse); a `sslcert` that does not exist, so libpq does not
  stop at `/root/.postgresql/postgresql.crt` ("Permission denied") in uWSGI's `www-data` workers, whose `HOME` is
  still `/root`; a `SECRET_KEY` derived from `DATABASE_URL` (the SHA-256 of `vouchervault-secret-key:` and the URL)
  instead of upstream's random one per process, which would sign people out between Tofu's processes, so changing
  `DATABASE_URL` signs everyone out, and a `SECRET_KEY` the owner saves as a hidden value wins; the proxy's scheme and
  host (`X-Forwarded-Proto`, `X-Forwarded-Host`); secure cookies and one year of HSTS without `includeSubDomains` or
  preload; sessions of 14 days (upstream: 30 minutes, ended with the browser) for a wallet opened at the till; UTC;
  no `django_celery_beat`; Django's warnings in the runtime log.
- **`myapp/tofu_schema.py`, `myapp/management/commands/tofu_schema.py`, `myapp/tofu_schema.sql`** (new): the schema
  step and the first account (above).
- **`myapp/tofu.py`** (new): what the pages read (the source link, the owner's logo key, the sign-in notice).
- **Shop logos**: `inventory.html`, `sharing_center.html` and `view-item.html` loaded logos from logo.dev with the
  upstream author's own token written into the templates. They now use `LOGO_DEV_TOKEN`, the owner's own logo.dev
  publishable key, and show none without it (the code's own picture stands in, as for an item without a logo); the
  item forms say where the key goes.
- **Attachments are off**: a file attached to an item was written to the server's disk, which a copy does not keep
  (the next restart loses it while the database still names it). The item forms have no file field and the views
  store none; the form says so.
- **Expiry notifications**: the notification page says they do not go out from a copy; its Test button still sends one.
- **Source code (GPL-3.0)**: the sign-in page, the signed-out page and every page's footer link to `SOURCE_URL` (a
  gallery copy's is this pin's tree on GitHub; without it, this fork).
- **Upstream issue #119** (a shared browser could show the previous person's cached pages): the signed-out page
  answers `Clear-Site-Data: "cache", "storage"` and, like the sign-in page, clears the service worker's caches, the
  offline database and the offline timestamp in the page itself.
- **Sign-in page**: the notice while there is no account, and "didn't match" after a wrong password (upstream showed
  the empty form again).
- **A fix**: deleting a transaction looked it up by id alone, so any signed-in person who knew an id could delete
  another person's; it now needs the item's owner.
- **Removed**: three `.pyc` files upstream committed in `myapp/management/commands/__pycache__`.

Files of upstream's that we changed carry a dated "Modified by Tofu (2026-10-27)" notice at their top, as the GPL asks.

## What works differently on Tofu

- **No expiry notifications.** Upstream sends them from Celery's worker and beat through Redis, and Tofu runs
  request-driven apps that scale to zero, with no process that runs all the time and no Redis. Check the inventory's
  "Expiring Soon" filter instead. Apprise's Test button works (it sends at once).
- **No email.** VoucherVault sends none (no password reset by email): the administrator sets a forgotten password in
  the Admin Settings.
- **No attachments** (above), and **no shop logos** until the owner saves `LOGO_DEV_TOKEN`.
- **Other phones see a change on their next page load.** Nothing is pushed live between devices; a page kept for
  offline use shows what it had when it was cached, until "Cache for Offline" is pressed again.
- **A domain connected later** has to be added to `DOMAIN` (comma-separated, as upstream reads it), then deploy again:
  Django answers 400 to a host it was not told about.
- **Time zone** is UTC unless `TZ` is saved.

## Keep a copy private

VoucherVault keeps gift card codes and PINs in the database in plain text, as upstream does, and anyone signed in as
the administrator can read every person's items in the Admin Settings. The app's own sign-in protects the data, but
its sign-in page is open to anyone who has the address. Keeping the copy private on Tofu (only people you choose)
puts Tofu's own sign-in in front of it as well. The stats API (`/api/get/stats`) answers only with the API token an
administrator creates in the Admin Settings, and it lists every code and PIN: create one only if you need it.

## Upstream, licence and caveats

- Upstream: https://github.com/l4rm4nd/VoucherVault, commit `e944abfc6e9d1cd84093a8e17ad35f6b9d2f2190`
  (2026-10-27, release v1.30.5).
- Licence: GPL-3.0 (`LICENSE.md`, unchanged). A copy offers its own source to everyone who opens it (the "Source code"
  links above), and our changes are under the same licence.
- The page design is BootstrapMade's NiceAdmin template, whose licence asks for its footer credit, which stays.
  Vendored libraries under `myapp/static/assets/vendor` keep their own licences (Bootstrap, Bootstrap Icons, Boxicons,
  Remix Icon, ApexCharts, Chart.js, ECharts, Quill, Simple-DataTables, TinyMCE, BootstrapMade's form script), and
  so does ZXing (`myapp/static/assets/js/zxing.js`, the camera scanner).
- The signed-in pages load the Open Sans, Nunito and Poppins fonts from Google Fonts, as upstream's template does, so a
  browser that opens them asks Google's servers for the fonts.
- "VoucherVault" and its logo are upstream's. A copy's sample items in Tofu's gallery pictures name no real shop.

## Verification (2026-10-27, on this Mac, without Docker)

- **Rule 1 (no file modes):** `git archive tofu | tar -x -C tree`, `find tree -type f -exec chmod a-x {} +`, then the
  Dockerfile's steps from that tree: `pip install -r requirements.txt` (Python 3.12.13; uWSGI 2.0.31 compiled),
  `python manage.py collectstatic --no-input`, and the start as the image runs it: `/bin/sh tofu-entrypoint.sh` with
  `PORT`, `DATABASE_URL` and `DJANGO_SETTINGS_MODULE=myproject.tofu_settings`. ghostscript 10.08 came from a local
  conda-forge prefix (the image installs Debian's).
- **Database:** a scratch PostgreSQL 14 cluster that refuses connections without TLS (`hostnossl ... reject`), with
  the roles `anon` and `authenticated`, and `DATABASE_URL=postgresql://vv:...@127.0.0.1:55432/...?sslmode=require`.
  `manage.py check`: no issues; `makemigrations --check --dry-run`: no changes (so upstream's `makemigrations` at
  start was not needed).
- **Rule 4 (five starts at once)** on a fresh empty database, five `tofu-entrypoint.sh` at the same moment on five
  ports: all five came up and answered 200 (`/` -> `/en/accounts/login/?next=/en/`); one start logged *"empty
  database: applied the snapshot of 48 migrations; turned on row-level security on 16 tables"* (0.07 s), the other
  four logged *"up to date"* after waiting 0.07-0.12 s for the lock; `django_migrations` held 48 rows, the database 16
  tables, none without row-level security, and no log held an error.
- **Rule 5 (libpq's client certificate):** with `HOME` a `chmod 000` folder, a plain `psycopg2.connect(...)` failed:
  *could not open certificate file ".../.postgresql/postgresql.crt": Permission denied* (psycopg2-binary's libpq
  17.6); the app's start and its sign-in page (which reads the database) with the same `HOME` worked, over TLS.
- **Core use:** with `VOUCHERVAULT_ADMIN_PASSWORD` saved, the start made `admin`; signed in through the form; made a
  loyalty card (EAN-13, drawn by treepoem and ghostscript) and a gift card (QR code), read both back in the inventory
  and on their pages, spent 7.50 of 50.00 and read 42.50 back; the dashboard, the sharing center (an item shared from
  a second account), preferences, notifications (with its notice) and the Admin Settings answered 200; signing out
  answered `Clear-Site-Data`.
- **Phone and desktop** (headless Chromium, 390x844 touch and 1200x750): the sign-in page, inventory, dashboard,
  sharing center, new-item form, notifications and three item pages: no page error, no console error, nothing wider
  than the screen.
- **`live-check.py`** (kept beside this fork, not in it): RESULT PASS against a fresh copy and against one whose
  owner saved the password.
- **Found and fixed on the way:** `/serviceworker.js` answered 500 under an ASCII locale (django-pwa reads it with
  the default encoding); the image now sets `LANG=C.UTF-8`.

## What only a real deploy can verify

- that Tofu's container build installs ghostscript and compiles uWSGI within its build limits, and that uWSGI binds
  port 80 as root and drops to `www-data` (here it ran as an ordinary user);
- the schema step through Tofu's transaction pooler and its first-start time, against the 4-10 starts Tofu makes;
- `DOMAIN` with the proxy's `X-Forwarded-Host`, Django's CSRF check from the copy's own address, and the secure
  cookies over HTTPS;
- the service worker, offline cache and `Clear-Site-Data` in a real phone browser, and the camera scanner (it needs
  HTTPS and a camera).
