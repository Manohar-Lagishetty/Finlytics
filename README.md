# Finlytics

A practical expense tracker: manual expense/income logging, category
budgets with alerts, a spending dashboard, exports, and an installable PWA.

## Stack

Django 6.1 (server-rendered templates) · PostgreSQL · Tailwind CSS (CDN) ·
Alpine.js (dropdowns/menus) · Three.js (landing hero animation) ·
django-allauth (Google sign-in only — email/password auth is custom).

## Run it

```bash
source ../myenv/bin/activate   # already has all dependencies installed
python manage.py runserver
```

Visit http://127.0.0.1:8000/

## Project layout

- `accounts/`, `core/`, `dashboard/`, `expenses/` — the web app: models,
  server-rendered views/templates.

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

No app restart config needed beyond editing `.env` (settings load it via
`django-environ`), just restart `runserver`.

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
