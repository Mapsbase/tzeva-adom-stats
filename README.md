# redalert

Simple rebuild from scratch:

- Django + DRF
- historical importer from archive JSON
- realtime fetch from Oref-style polling endpoints
- live feed page that polls every 2 seconds
- one row per city per alert event

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
```

## Live source configuration

The live polling source is configured from undocumented Oref-style endpoints.

Example `.env` values:

```env
REALTIME_SOURCE_URL=https://www.oref.org.il/warningMessages/alert/Alerts.json
OREF_REALTIME_URLS=https://www.oref.org.il/warningMessages/alert/Alerts.json,https://www.oref.org.il/WarningMessages/alert/alerts.json
REALTIME_REFERER=https://www.oref.org.il/
```

The app tries the configured Oref URLs in order and accepts that these endpoints can change without notice.

Live ingestion can also use backup providers and compare all providers in one cycle:

- `OREF_REALTIME_URLS` (primary)
- `LIVE_BACKUP_NOTIFICATIONS_URL`
- `LIVE_BACKUP_HISTORY_URL`
- `LIVE_EXTRA_URLS` (optional comma-separated extra endpoints)

The app merges provider outputs by `(occurred_at, category, city)` and stores only one canonical row per event-city (source is set to `live_consensus`).
To keep the live feed truly live, events older than `LIVE_MAX_EVENT_AGE_MINUTES` are dropped from realtime ingestion.
Live feed responses now include source health fields:

- `source_status` (`ok`, `empty`, `error`, `disabled`)
- `source_url`
- `source_event_count`
- `refresh_error`
- `source_details` (per-provider status and event counts)

## Import history

```powershell
.\.venv\Scripts\python.exe manage.py fetch_history --start 2026-02-27T00:00:00Z
```

## Run web server

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

## Run realtime loop

In another terminal:

```powershell
.\.venv\Scripts\python.exe manage.py run_live_poller
```

## Manual commands

```powershell
.\.venv\Scripts\python.exe manage.py fetch_realtime
.\.venv\Scripts\python.exe manage.py fetch_history
```

## API

- `GET /api/alerts/latest?limit=50`
- `GET /api/alerts/feed?limit=50&refresh=1&since_id=123`
- `POST /api/alerts/pull-realtime`
- `POST /api/alerts/pull-history`
- `GET /api/stats/top-cities?limit=20`

## UI

Open:

- `http://127.0.0.1:8000/`

The page:

- polls live feed every 2 seconds
- prepends newly seen alerts from the Oref polling source
- has buttons to pull realtime and history immediately

## Deploy on Render

- This repo now includes [`render.yaml`](./render.yaml) with build/start commands.
- Required Render environment variables:
  - `SECRET_KEY`
  - `DATABASE_URL` (Render Postgres)
  - `ALLOWED_HOSTS` (for example: `.onrender.com`)
  - `CSRF_TRUSTED_ORIGINS` (for example: `https://your-service.onrender.com`)
  - live source envs as needed (`OREF_REALTIME_URLS`, `LIVE_BACKUP_NOTIFICATIONS_URL`, etc.)

Important: `/map-lab/` now polls `/api/alerts/feed` with `refresh=0` to avoid triggering upstream fetch/write on every client poll. Run a worker/cron (`fetch_realtime` or `run_live_poller`) for continuous ingestion.

Startup now includes `python manage.py bootstrap_data`, which ingests history only when `alerts_alert` is empty. Default bootstrap start is `2026-02-27T00:00:00Z`.
