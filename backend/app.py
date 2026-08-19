# -*- coding: utf-8 -*-
from datetime import date, datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

import config
import db
from reports.common import HEADLINE_CATEGORIES, ALL_CATEGORIES, DISTRICT_FILTER_SQL, save_html, render_pdf_from_file
from reports import (
    district_csv, maxmin, safest_districts, pattern_analysis, deep_analysis,
    category_deepdive, crime_analytics, crime_analytics_monthly, data_science_review,
    crime_analytics_v2,
)

app = Flask(__name__)
CORS(app)

# Production build of the React frontend (npm run build), served from this
# same Flask process/port so the whole app is one deployable service under
# PM2 rather than a separate Vite dev server.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

REPORT_CATALOG = [
    dict(id="crime_analytics", name="Crime Analytics Punjab", format="pdf",
         description="The combined report for major meetings: comparative today-vs-usual analysis, weekly up/down trend, per-crime detail, full crime-mix composition, and key insights. Always covers 01 July through the latest day on file, and counts every category including Road Accidents and Religious Issues."),
    dict(id="crime_analytics_monthly", name="Crime Analytics Punjab (Monthly Trend)", format="pdf",
         description="Same report as Crime Analytics Punjab, but section 1 shows total cases per calendar month for every crime type and whether each is rising, falling, or steady month over month, instead of a single day's snapshot. Built for a longer-horizon view; the monthly findings also feed into Key Insights."),
    dict(id="crime_analytics_v2", name="Crime Analytics Punjab (New Design)", format="pdf",
         description="Same Key Insights, weekly trend, per-crime detail, and district composition as Crime Analytics Punjab, in the new dark-navy/gold executive cover-page design. Includes a weekly trend line chart. Always covers the full data history through the latest day on file."),
    dict(id="deep_analysis", name="Deep Analysis", format="pdf",
         description="Performance ranking, each district's crime-mix composition (sums to 100%), and week-by-week trend. Real crime only, crime districts only."),
    dict(id="category_deepdive", name="Category Deep Dive", format="pdf",
         description="One page per crime type (Murder, Robbery, Child Abuse, Rape, Gang Rape, Snatching): weekly trend, top divisions, top/bottom 5 districts, plus an overall min/max page."),
    dict(id="pattern_analysis", name="Crime Pattern Analysis", format="pdf",
         description="Chronic districts, biggest one-day jumps, and rising-fast districts, one page per crime type."),
    dict(id="safest_districts", name="Safest Districts", format="pdf",
         description="Lowest-crime districts per crime type, with a Days-On-File caveat for thin-reporting districts."),
    dict(id="maxmin", name="Max & Min Districts", format="pdf",
         description="Top 5 highest and top 5 lowest districts, side by side, for every crime type."),
    dict(id="district_csv", name="District-Wise Total Crime (CSV)", format="csv",
         description="All districts x all 14 recorded categories, with a grand total row."),
    dict(id="data_science_review", name="Comprehensive Crime Data Review (Data Science Committee)", format="pdf",
         description="Population-adjusted crime rates using official 2023 census data, hidden-risk districts, statistical outlier detection, international homicide-rate benchmarking (World Bank/UNODC), density analysis, and a composite priority list. Content-first draft, tables and figures only."),
]

REPORT_MODULES = {
    "crime_analytics": crime_analytics,
    "crime_analytics_monthly": crime_analytics_monthly,
    "crime_analytics_v2": crime_analytics_v2,
    "deep_analysis": deep_analysis,
    "category_deepdive": category_deepdive,
    "pattern_analysis": pattern_analysis,
    "safest_districts": safest_districts,
    "maxmin": maxmin,
    "district_csv": district_csv,
    "data_science_review": data_science_review,
}


@app.get("/api/health")
def health():
    return jsonify(status="ok", time=datetime.now().isoformat())


@app.get("/api/meta/districts")
def meta_districts():
    rows = db.query("""
        SELECT d.id, d.name_en, d.exclude_from_analysis, dv.name_en AS division
        FROM districts d LEFT JOIN divisions dv ON dv.id = d.division_id
        ORDER BY dv.name_en, d.name_en
    """)
    return jsonify(rows)


@app.get("/api/meta/divisions")
def meta_divisions():
    rows = db.query("SELECT id, name_en FROM divisions ORDER BY name_en")
    return jsonify(rows)


@app.get("/api/meta/categories")
def meta_categories():
    return jsonify(dict(
        headline=[dict(key=k, label=l) for k, l in HEADLINE_CATEGORIES],
        all=[dict(key=k, label=l) for k, l in ALL_CATEGORIES],
    ))


@app.get("/api/meta/date_bounds")
def meta_date_bounds():
    row = db.query_one(f"""
        SELECT MIN(c.report_date) AS earliest, MAX(c.report_date) AS latest
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL}
    """)
    return jsonify(dict(
        earliest=row["earliest"].isoformat() if row and row["earliest"] else None,
        latest=row["latest"].isoformat() if row and row["latest"] else None,
    ))


@app.post("/api/query")
def ad_hoc_query():
    """Flexible filter-driven query: date range + optional district/category
    subset. Returns a per-district matrix for the selected categories."""
    body = request.get_json(force=True) or {}
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    district_ids = body.get("district_ids") or []
    categories = body.get("categories") or [k for k, _ in HEADLINE_CATEGORIES]

    if not start_date or not end_date:
        return jsonify(error="start_date and end_date are required"), 400

    valid_cols = {k for k, _ in ALL_CATEGORIES}
    categories = [c for c in categories if c in valid_cols] or [k for k, _ in HEADLINE_CATEGORIES]

    cols_sql = ",".join(f"COALESCE(SUM(c.{col}),0) AS {col}" for col in categories)
    total_sql = "+".join(f"c.{col}" for col in categories)

    params = [start_date, end_date]
    district_filter = ""
    if district_ids:
        placeholders = ",".join(["%s"] * len(district_ids))
        district_filter = f" AND d.id IN ({placeholders})"
        params += list(district_ids)

    sql = f"""
        SELECT d.id, d.name_en, {cols_sql}, COALESCE(SUM({total_sql}),0) AS total
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s{district_filter}
        GROUP BY d.id, d.name_en
        ORDER BY total DESC
    """
    rows = db.query(sql, params)

    totals = {col: sum(r[col] for r in rows) for col in categories}
    totals["total"] = sum(r["total"] for r in rows)

    return jsonify(dict(rows=rows, totals=totals, categories=categories))


@app.get("/api/reports/catalog")
def reports_catalog():
    return jsonify(REPORT_CATALOG)


@app.post("/api/reports/generate")
def reports_generate():
    """output='pdf' (default) renders straight to PDF. output='html' saves
    the editable preview instead — the returned page has a floating toolbar
    that lets you edit any heading/text inline and export to PDF from there
    (see /api/reports/export_html)."""
    body = request.get_json(force=True) or {}
    report_type = body.get("report_type")
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    header_note = (body.get("header_note") or "").strip() or None
    reporting_day = body.get("reporting_day") or date.today().strftime("%d/%m/%Y")
    output = body.get("output") or "pdf"
    # Only crime_analytics/crime_analytics_monthly read these (their
    # Executive Summary page); every other report just ignores them via **_.
    custom_insights = body.get("custom_insights") or None
    override_defaults = bool(body.get("override_defaults"))

    if report_type not in REPORT_MODULES:
        return jsonify(error=f"unknown report_type '{report_type}'"), 400

    module = REPORT_MODULES[report_type]
    # crime_analytics and its two variants all default to their own full
    # date range; every other report needs an explicit range from the caller.
    if report_type not in ("crime_analytics", "crime_analytics_monthly", "crime_analytics_v2") and (not start_date or not end_date):
        return jsonify(error="start_date and end_date are required"), 400

    try:
        if report_type == "district_csv":
            csv_text = module.generate(start_date, end_date, reporting_day=reporting_day, header_note=header_note)
            fname = f"district-wise-crime-{start_date}-to-{end_date}.csv"
            return Response(
                csv_text, mimetype="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{fname}"'},
            )
        else:
            filename = module.generate(
                start_date, end_date, reporting_day=reporting_day,
                header_note=header_note, output=output, custom_insights=custom_insights,
                override_defaults=override_defaults,
            )
            return jsonify(dict(url=f"/reports/download/{filename}", filename=filename, output=output))
    except Exception as e:
        app.logger.exception("report generation failed")
        return jsonify(error=str(e)), 500


@app.get("/api/reports/default_insights")
def reports_default_insights():
    """The Executive Summary's automatic findings for a given date range,
    unrendered (plain text + colour + tag), so the generation form can show
    them pre-filled and editable instead of the user only finding out what
    they say once the PDF is already produced."""
    report_type = request.args.get("report_type")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    if report_type not in ("crime_analytics", "crime_analytics_monthly"):
        return jsonify(error=f"unsupported report_type '{report_type}'"), 400
    try:
        insights = REPORT_MODULES[report_type].default_insights(start_date, end_date)
        return jsonify(insights)
    except Exception as e:
        app.logger.exception("default_insights failed")
        return jsonify(error=str(e)), 500


@app.post("/api/reports/export_html")
def reports_export_html():
    """Takes the (possibly hand-edited) full HTML of a previewed report and
    renders it to PDF. This is what the in-page 'Export PDF' button calls."""
    body = request.get_json(force=True) or {}
    html_content = body.get("html")
    if not html_content:
        return jsonify(error="html is required"), 400
    try:
        html_name = save_html(html_content)
        pdf_name = render_pdf_from_file(html_name)
        return jsonify(dict(url=f"/reports/download/{pdf_name}", filename=pdf_name))
    except Exception as e:
        app.logger.exception("export_html failed")
        return jsonify(error=str(e)), 500


@app.get("/api/reports/download/<path:filename>")
def reports_download(filename):
    return send_from_directory(config.GENERATED_DIR, filename, as_attachment=False)


@app.get("/")
def frontend_index():
    return send_from_directory(FRONTEND_DIST, "index.html")


@app.get("/assets/<path:filename>")
def frontend_assets(filename):
    return send_from_directory(FRONTEND_DIST / "assets", filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.FLASK_PORT, debug=True)
