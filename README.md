# Counterpoint

**Walk-up queue and desk tools for the USask IT Support desk at Murray Library.**
CMPT 370 · We'll Study It Later (Team 8) · Fall 2026

## Five features, one owner each

| Feature | Owner | Folder | Screens |
|---|---|---|---|
| 1 · Walk-up queue | Mohit Sawant | `app/queue` | Kiosk, lobby screen, counter panel |
| 2 · Ticket drafts & shift handover | Hetank Patel | `app/tickets` | Tickets, Handover |
| 3 · Fix guides | Priyesh Patel | `app/guides` | Fix guides |
| 4 · Weekly report & trends | Haryan Patel | `app/report` | Weekly report |
| 5 · Desk coverage + supervisor notifications + time away | Aarya Patel (lead) | `app/coverage` | Coverage, Time away, Notifications, public "Is the IT desk covered?" page |

## Product v1 (Deliverable 2): 17 stories, 41 of 82 points

Each member builds the first epic of their feature. The rest comes in Product v2 (Deliverable 3) and the final product.

| Owner | Product v1 (this release) | Points | Product v2 | Final |
|---|---|---|---|---|
| Aarya | Shared base (settings, CI) + E9 · Keep the desk covered: US-26, 27, 28, 29 + US-33 supervisor notifications | 12 | E10 · US-30 to 32 | E11 · US-34 to 37 |
| Mohit | E1 · Get in line and know my wait: US-01, 02, 03 | 8 | E2 · US-04 to 06 | |
| Hetank | E3 · Write tickets while they're fresh: US-07, 08, 09 | 7 | E4 · US-10 to 13 | |
| Priyesh | E5 · Find the right fix fast: US-14, 15, 16 | 7 | E6 · US-17 to 19 | |
| Haryan | E7 · Weekly desk report: US-20, 21, 22 | 7 | E8 · US-23 to 25 | |

Screens and buttons for stories that aren't built yet stay hidden: each feature's JavaScript lists its stories
(`export const stories = [...]`) and `index.html` marks each part of the page with `data-story="US-xx"`.

**Shared infrastructure** (owned by no feature, built by all five of us: settings and CI by Aarya; database, live updates and `main.py` by Mohit; clock and Dashboard by Haryan; sign-in by Hetank; front-end shell and demo data by Priyesh): `app/core` (settings, database, clock, live updates), `app/auth` (staff sign-in), and the app shell: sidebar, top bar, **Dashboard** (`static/js/dashboard.js`, which only reads each feature's own API) and **Settings** (`static/js/settings.js`: accent colour and light/dark theme, saved on this device).

Each feature's frontend is in `static/js/<feature>.js` and its tests in `tests/test_feature<N>_*.py`. Every test is named after the acceptance test it checks (e.g. `test_us04_never_called_twice`).

## Project structure

Every folder has one owner. Only the owner changes the files in it; the shared base belongs to no feature.

```
counterpoint/
├── app/                      Python backend (FastAPI)
│   ├── main.py               starts the app and plugs in each feature        · shared base (Mohit)
│   ├── core/                 settings (Aarya) · clock (Haryan) · database, live updates (Mohit)
│   ├── auth/                 staff sign-in and roles                          · shared base (Hetank)
│   ├── queue/                Feature 1 · Walk-up queue                         · Mohit
│   ├── tickets/              Feature 2 · Ticket drafts & shift handover        · Hetank
│   ├── guides/               Feature 3 · Fix guides                            · Priyesh
│   ├── report/               Feature 4 · Weekly report & trends                · Haryan
│   └── coverage/             Feature 5 · Desk coverage                         · Aarya
├── static/                   the web pages
│   ├── index.html, css/, img/                                                  · shared base (Priyesh)
│   └── js/                   api, auth, ui, main, settings (Priyesh) · dashboard (Haryan)
│                             queue.js · tickets.js · guides.js · report.js · coverage.js  · each feature's owner
├── tests/                    conftest.py (shared) + test_feature<N>_*.py, one file per feature
├── scripts/                  demo data (Priyesh) · staff accounts (Hetank) · email setup (Aarya)
├── requirements.txt · .gitlab-ci.yml · .gitignore · .env.example              · shared base (Aarya)
└── README.md
```

A feature folder that is still empty is skipped when the app starts, so features can be merged in any order once the shared base is on `main`.

## Run it

Needs Python 3.11 or newer.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed_demo          # demo staff, two weeks of visits, guides, drafts, today's shift
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

- **Assistants:** `aarya`, `priyesh`, `mohit`, `nate`, `rurik`, `palak`, `laaiba`, `oliver`
- **Supervisors** (unread notifications and Mark all as read): `chewy`, `tom`
- The password for every demo account is `counterpoint`.
- **No sign-in needed:** `/#kiosk` (check-in). The lobby screen (US-05) and the public coverage page (US-30) arrive in Product v2.
- In Product v1 guides are added by the demo data; writing them in the app comes with US-17.
- **API docs:** every endpoint, grouped by feature, at http://127.0.0.1:8000/docs.

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Run the tests

```bash
pytest -q
```

## Supervisor notifications (US-33)

Every time an assistant checks in, goes on break or to lunch, steps away, comes back or checks out, Counterpoint records it with the time and shows it on the **Notifications** screen, live.

Every staff member can read **Notifications**. Only supervisors and shift leads get the unread count on the bell and can mark them as read. Sign in as `chewy` or `tom` to see that.

**To also email the supervisor** for each change:

1. Copy `.env.example` to `.env` in the project folder and fill it in. With Gmail, turn on 2-Step Verification, create an **App password** at https://myaccount.google.com/apppasswords, and paste it as `SMTP_PASSWORD`.
2. Give the supervisor an email address and send a test email:
   ```bash
   python -m scripts.email_setup chewy your.email@gmail.com
   ```
3. Restart the server. From now on, every check-in, break, lunch, return and check-out emails the supervisor, for example "Counterpoint: Nate went on break at 2:05 p.m.", with the date and time in the body. On the Notifications screen, each entry that was emailed says "emailed".

| Setting in `.env` | Gmail example |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `you@gmail.com` |
| `SMTP_PASSWORD` | the 16-letter App password |
| `SMTP_FROM` | `you@gmail.com` |

`.env` is never committed, because it holds a password. If `SMTP_HOST` is empty, notifications are in-app only. If the mail server is down, status changes still work and the error is logged. The tests never send real email.

## Create real staff accounts

```bash
python -m scripts.create_staff chewy "Chewy" supervisor --email chewy@usask.ca
```

## How we work

- Nobody pushes to `main`. Each epic gets its own branch, e.g. `feature-1/e1-get-in-line`.
- A merge request needs its tests passing (GitLab CI runs `pytest`) and a review from another member. Aarya merges.
- Cards move across the board: Open → Doing → Closed.

## Privacy

Counterpoint never stores an NSID, student number or email for students: only a first name, which the kiosk refuses if it contains digits. Live-update messages never contain names. (Later releases keep the same rule: the lobby screen shows only ticket numbers and counters, the public coverage page only counts and times, and the CSV export no names or ticket numbers.)

## AI use

The first version of this code was generated with Claude (Anthropic) from our Deliverable 1 requirements. Each file says so at the top. Each owner must read, test and be able to explain their feature's code, and edit it as needed.
