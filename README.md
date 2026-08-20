# CSU Crime Analysis Portal

A local tool for generating the daily/weekly crime analysis reports on
demand, instead of building them by hand each time. Two pieces:

- **backend/** — Flask API. Queries the live `csu_control_room` Postgres
  database, builds the same branded HTML report layouts used throughout
  this project, and renders them to PDF via a headless-Chromium (Puppeteer)
  script. Talagang and Tonsa are excluded from every report automatically
  (`districts.exclude_from_analysis`).
- **frontend/** — React (Vite) single page. Left panel: date range,
  crime-category and district filters, plus an ad-hoc "Run Query" table.
  Right panel: a gallery of report types; picking one opens a form for the
  date range and an optional **header note** — free text that gets printed
  at the top of every page of that report (e.g. "Prepared for the CM
  Weekly Security Briefing").

## Report types

| Report | Format | What it does |
|---|---|---|
| Crime Analytics Punjab (Monthly Trend) | PDF | Key Insights, month-over-month weekly trend, per-crime detail, district composition |
| Crime Analytics Punjab (New Design) | PDF | Same content, dark-navy/gold executive cover design, full data history |
| Category Deep Dive | PDF | One page per crime type: weekly trend, top divisions, top/bottom 5 districts, closing overall min/max page |
| Crime Pattern Analysis | PDF | Chronic districts / biggest one-day jumps / rising-fast districts, per crime type |
| Safest Districts | PDF | Lowest-crime districts per crime type, with a Days-On-File caveat |
| District-Wise Total Crime | CSV | All districts x all 14 recorded categories, grand total row |
| Comprehensive Crime Data Review | PDF | Population-adjusted rates, outlier detection, international benchmarking (Data Science Committee) |

All figures on every report count **real crime only** — Road Accident
Casualties and Religious Issues are not crime categories and are excluded
from every total.

## First-time setup (new developer)

Prerequisites: Python 3.11+, Node 18+, PostgreSQL (local server for dev —
see below), git.

```
git clone https://github.com/csupunjab/crimeanalysis.git
cd crimeanalysis

# Backend
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
cd render
npm install
cd ..

# Frontend
cd ..\frontend
npm install
```

### Local database

Production points at the live `csu_control_room` Postgres database, which
you won't have credentials for as a new developer. Instead, set up a local
Postgres database with the same 3 tables this app actually queries
(`districts`, `divisions`, `crime_daily`), loaded with **synthetic** sample
data (randomly generated — not real crime figures) so every report renders
correctly against realistic-looking numbers:

```
createdb -U postgres csu_control_room
psql -U postgres -d csu_control_room -f db/schema.sql
psql -U postgres -d csu_control_room -f db/seed.sql
```

`backend/.env.example` already points at `127.0.0.1` / `postgres` /
`postgres` / `csu_control_room` to match this. Copy it to `.env` (done
above) and adjust if your local Postgres user/password differ.

Want more synthetic days of data, or different date range? Edit the
`START` / `END` constants in `db/generate_synthetic_crime.py` and rerun it
(it appends to `db/seed.sql`) — the `divisions`/`districts` inserts above it
in that file are real reference data (district names/codes only, not crime
data) and don't need regenerating.

## Running locally

**Backend**:

```
cd backend
venv\Scripts\python.exe app.py
```

Runs on `http://localhost:8050` (or whatever `FLASK_PORT` is set to in
`.env`).

**Frontend**:

```
cd frontend
npm run dev
```

Runs on `http://localhost:5173` and proxies `/api/*` to the backend.

## Configuration

`backend/.env` (gitignored — copy from `.env.example`) holds the Postgres
connection and the Flask port. In production this points at the live
`103.111.160.131` / `csu_control_room` database; locally it points at your
own Postgres instance seeded per above. Generated PDFs/CSVs land in
`backend/generated/` (gitignored).

## Adding a new report type

1. Add a module in `backend/reports/` with a `generate(start_date, end_date,
   reporting_day, header_note=None, **_)` function that returns either a PDF
   filename (via `reports.common.render_pdf`) or CSV text.
2. Register it in `REPORT_MODULES` and `REPORT_CATALOG` in `backend/app.py`.
3. It appears in the frontend's report gallery automatically — no frontend
   changes needed.
