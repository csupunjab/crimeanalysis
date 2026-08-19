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
| Deep Analysis | PDF | Performance ranking, per-district crime-mix composition (rows sum to 100%), week-by-week trend |
| Category Deep Dive | PDF | One page per crime type: weekly trend, top divisions, top/bottom 5 districts, closing overall min/max page |
| Crime Pattern Analysis | PDF | Chronic districts / biggest one-day jumps / rising-fast districts, per crime type |
| Safest Districts | PDF | Lowest-crime districts per crime type, with a Days-On-File caveat |
| Max & Min Districts | PDF | Top 5 highest and lowest districts side by side, per crime type |
| District-Wise Total Crime | CSV | All districts x all 14 recorded categories, grand total row |

All figures on every report count **real crime only** — Road Accident
Casualties and Religious Issues are not crime categories and are excluded
from every total.

## Running locally

**Backend** (first time: `python -m venv venv` then install requirements —
already done if you're reading this after initial setup):

```
cd backend
venv\Scripts\python.exe app.py
```

Runs on `http://localhost:5050`.

**Frontend**:

```
cd frontend
npm run dev
```

Runs on `http://localhost:5173` and proxies `/api/*` to the backend.

## Configuration

`backend/.env` holds the Postgres connection (same production database used
throughout this project — `103.111.160.131` / `csu_control_room`) and the
Flask port. Generated PDFs/CSVs land in `backend/generated/` (gitignored).

## Adding a new report type

1. Add a module in `backend/reports/` with a `generate(start_date, end_date,
   reporting_day, header_note=None, **_)` function that returns either a PDF
   filename (via `reports.common.render_pdf`) or CSV text.
2. Register it in `REPORT_MODULES` and `REPORT_CATALOG` in `backend/app.py`.
3. It appears in the frontend's report gallery automatically — no frontend
   changes needed.
