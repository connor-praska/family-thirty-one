# 31 — The Family Table

The Family Table home page at `/` is the game collection. Thirty-One lives at `/games/31/`, with its rules and create/join forms. The home page also accepts 31 room codes. Existing `/room/<code>/` invites and create/join endpoints continue to work. Only Thirty-One is playable today; other games can be added later.

A Django card game for 2–6 family members playing on separate devices. Private invite-only tables, session-based seats, server-owned hands and rules, three lives, knocking, instant 31, round results, and rematches. Other browsers receive updates every 1.5 seconds. No paid services or frontend build step.

Rooms include table chat and clearly marked Server game announcements. Public moves show deck/discard choices and visible cards; deck draws stay hidden. The knock button sits beneath the piles, with a persistent final-turn notice and a brief animation (disabled for reduced-motion preferences). Chat works in lobbies, during games, and between rounds, including for eliminated players. Messages are plain text, limited to 300 characters and one message per player every two seconds. The latest 80 messages are shown; storage is capped at 100 per room. Server is a reserved name. All chat is temporary along with its room on free Render. Existing rooms work with the update after running `python manage.py migrate`; no rules reset is required by the code, although a Render deployment resets its temporary database.

## Run on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

Open http://127.0.0.1:8000. Create a table, copy the invite link, and have others join with their names. To test alone, use a second browser or private window; tabs in the same browser share a seat. Refreshing preserves a seat. Clearing cookies loses that seat. The host should remain available to deal. Rooms cannot accept new players after starting; create a new room to change the group.

## House rules

- Three cards; best sum in a single suit. Ace 11, faces 10, others their number.
- Draw from deck or discard, then discard one. Picking up and returning a discard is allowed.
- Knock at the start of your turn instead of drawing. Every other active player gets one final turn.
- A 31 on the deal or after discarding ends the round; every player without 31 loses one life.
- Otherwise all players tied for lowest lose one life. Three of a kind has no bonus.
- Three lives; no extra free life. Zero lives means watching. Last remaining player wins; simultaneous elimination can produce a shared finish.
- The starting player rotates each round among active players. The host starts each round and may start a rematch.

## Verification

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test
```

Tests cover scoring, deck integrity, knock order, 31, elimination, move validation, host permissions, session privacy, stale requests, and CSRF. `game/engine.py` is the rules layer; `game/views.py` handles HTTP, sessions, and persistence; `game/models.py` stores room snapshots with optimistic version checks. Templates and static files provide the interface. SQLite transactions plus conditional version updates prevent stale snapshots overwriting newer moves. SQLite is deliberately a single-instance starting point.

## Playing across the country

For the free Render service with temporary SQLite, follow [the complete Render instructions](RENDER.md). That option automatically recreates the database at startup and accepts losing games and seats on restarts. The persistent-storage instructions below describe a different hosting option.

Localhost links only work on your computer. You must deploy this Django service to an HTTPS Python host before your grandparents can use it remotely. Sites' Worker hosting cannot run this conventional Python service.

Use Python 3.12+ on the host, install requirements, and configure:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<a long randomly generated secret>
DJANGO_ALLOWED_HOSTS=your-domain.example
DATABASE_PATH=/persistent-storage/31.sqlite3
```

Then run `python manage.py migrate`, `python manage.py collectstatic --noinput`, and `python manage.py check --deploy`. Start `waitress-serve --listen=0.0.0.0:8000 thirtyone.wsgi:application`, with the host's HTTPS proxy routing to port 8000. The Dockerfile uses this layout and a persistent `/data` volume. Set the host's health check to `/`. Keep one application instance with SQLite, attach persistent storage, and back up the database. A deployment without persistence loses rooms and sessions on restart. Cookies require HTTPS in production. Never use Django's development server for public hosting.

For a larger commercial product, move persistence to PostgreSQL and use row locks or equivalent atomic version checks; add room expiry and cleanup, abuse controls, recovery/host transfer, monitoring, and account/billing features as requirements emerge. This app is a family-game MVP, without account recovery or a SaaS billing system.

The interface uses optional Google Fonts with local fallbacks; gameplay works if those fonts are unavailable.
