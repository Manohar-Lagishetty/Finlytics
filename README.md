# Finlytics

A practical expense tracker: manual expense/income logging, category
budgets with alerts, a spending dashboard, exports, an installable PWA,
and a JSON API for a companion Flutter mobile app with offline-first sync.

## Stack

Django 6.1 (server-rendered templates) · PostgreSQL · Tailwind CSS (CDN) ·
Alpine.js (dropdowns/menus) · Three.js (landing hero animation) ·
django-allauth (Google sign-in only — email/password auth is custom) ·
Django REST Framework + SimpleJWT (mobile API) · google-auth (verifies
Google id tokens from both the web and mobile sign-in flows).

## Run it

```bash
source ../myenv/bin/activate   # already has all dependencies installed
python manage.py runserver
```

Visit http://127.0.0.1:8000/

## Project layout

- `accounts/`, `core/`, `dashboard/`, `expenses/` — the web app: models,
  server-rendered views/templates, and (for `expenses`) the tombstone
  signal that also backs the mobile sync feed.
- `Mobile_application/` — all logic/routing for the Flutter app's JSON API
  (`/api/v1/...`): serializers, views, urls, the `purge_tombstones`
  command, and their tests. Kept separate from the web app's views, but it
  imports and operates on the *same* models/database as the apps above —
  one shared `User` table means an account created via either surface can
  log into both.

## What's built

**Web app**
- `/` — landing page (hero, 3D animated backdrop, tilt cards)
- `/accounts/signup/` — email/password signup → `/accounts/signup/verify/` (6-digit email OTP, 10 min expiry, resend with 30s cooldown)
- `/accounts/login/` — email/password login; Google sign-in button on both pages (`/accounts/google/login/`) skips OTP, since Google already verifies the email
- `/dashboard/` — spend totals/trend/category breakdown for a selectable date range, this-month balance (income − expenses vs. a low-balance threshold), budget progress cards
- `/expenses/` — add/edit/delete expenses, nested categories (unlimited depth), toggleable columns, CSV/XLSX/PDF export
- `/expenses/income/` — ad-hoc income + recurring income schedules (salary, retainer, ...), which materialize into dated income rows automatically
- `/expenses/budgets/` — per-category monthly caps with near/over status
- `/expenses/settings/` — low-balance threshold
- Installable as a PWA (manifest + service worker at `/sw.js`, scoped to `/` so it can control the whole app)

**Mobile API** (`/api/v1/...`, JWT-auth via SimpleJWT, for a local-first Flutter app)
- `auth/signup/`, `verify-otp/`, `resend-otp/`, `login/`, `google/` (Google id-token exchange), `token/refresh/`, `me/`, `logout/`
- `categories/`, `expenses/`, `income/`, `recurring-incomes/`, `budgets/` — full CRUD, looked up by client-stable `uuid` rather than internal id
- `settings/`, `columns/` — finance settings and column preferences
- `sync/` — single delta-sync endpoint: client pushes local changes (`upserts`/`deletes` per model) and gets back everything changed server-side since its last checkpoint, including tombstones for rows deleted elsewhere (web app, admin, cascade deletes). Conflicts resolve last-write-wins by `updated_at`.
- `dashboard/summary/` — same aggregates as the web dashboard

## Before this works for real: replace the placeholders in `.env`

`.env` currently has **fake** values for two things:

**1. Email (OTP delivery)** — create a Gmail App Password (Google Account →
Security → 2-Step Verification → App passwords) and set:
```
EMAIL_HOST_USER=your-real-address@gmail.com
EMAIL_HOST_PASSWORD=the-16-char-app-password
DEFAULT_FROM_EMAIL=Finlytics <your-real-address@gmail.com>
```
Until then, signup still works, but you'll see a "couldn't send the
verification email" message — grab the code straight from the DB
(`accounts_otp` table) or the Django admin at `/admin/` while testing.

**2. Google Sign-In** — create an OAuth client at
https://console.cloud.google.com → APIs & Services → Credentials →
"OAuth client ID" (type: Web application). Add this Authorized redirect URI:
```
http://127.0.0.1:8000/accounts/google/login/callback/
```
Then set in `.env`:
```
GOOGLE_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
```
The same `GOOGLE_CLIENT_ID` doubles as the audience for the mobile API's
`auth/google/` endpoint — configure the Flutter app's `google_sign_in` with
this value as `serverClientId` so the id_token it returns is verifiable here.

No app restart config needed beyond editing `.env` (settings load it via
`django-environ`), just restart `runserver`.

## Housekeeping: purge_tombstones

Deleted rows leave a `SyncTombstone` behind for 90 days
(`SyncTombstone.RETENTION_DAYS`) so mobile clients can catch up on deletes
during their next sync, then age out. Nothing runs this automatically yet —
wire it into whatever scheduler the deploy host uses, once there is one.
Manually:

```bash
python manage.py purge_tombstones
```

Daily cron entry:
```
0 3 * * * cd /path/to/Expense_Tracker && /path/to/myenv/bin/python manage.py purge_tombstones >> /var/log/finlytics-purge.log 2>&1
```

Or a systemd timer — `finlytics-purge.service`:
```ini
[Unit]
Description=Purge expired Finlytics sync tombstones

[Service]
Type=oneshot
WorkingDirectory=/path/to/Expense_Tracker
ExecStart=/path/to/myenv/bin/python manage.py purge_tombstones
```
paired with `finlytics-purge.timer`:
```ini
[Unit]
Description=Run finlytics-purge.service daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```
enabled with `systemctl enable --now finlytics-purge.timer`.

## Tests

```bash
python manage.py test
```

## Notes / things intentionally left out so far

- No password-reset flow yet.
- The date-range filter and dashboard don't yet expose custom Panic Mode /
  narrative-insight screens, predictive low-balance warnings, or partner
  sharing — see the product roadmap for what's still ahead of the current
  build (auth, logging, dashboard, budgets, reports/export are the phase-1
  slice that's done; Android UPI auto-detection and narrative insights are
  explicitly later-phase).
- `purge_tombstones` (above) needs a scheduler wired up on the actual deploy
  host — there's no deployment config in this repo yet (dev-only so far).
