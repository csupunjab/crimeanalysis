# -*- coding: utf-8 -*-
"""Crime Analytics Punjab: same report as crime_analytics, with one
deliberate change. Section 1 there shows a single day (today vs the usual
30-day range) — useful for a daily briefing, but not for a report meant
to hold up over a longer horizon. Here, section 1 instead shows total
cases per week for every category, across the full data history, with a
"Typical" baseline (the average of every complete week) and a rising /
falling / stable read on the most recent complete week against it.
Everything else (weekly trend chart, detail of each crime, composition,
key insights) is identical to crime_analytics, and the week-by-week
findings feed into Key Insights too, since this section is the most
important one here.

Methodology note (why "complete week" matters): the most recent week in
any live dataset is usually still in progress — right now the latest
week has 2 of 7 days on file. Comparing that partial week's low total
directly against older full weeks would make every category look like
it's falling, which is a data-completeness artifact, not a real trend.
So the trailing partial week is shown (marked *) but excluded from both
the Typical baseline and the trend comparison; the comparison uses the
most recent *complete* week instead.
"""
import json
from datetime import date, timedelta

import db
from reports.common import (
    CSS as BASE_CSS, CSU_LOGO, GOVT_LOGO, EDIT_TOOLBAR, DISTRICT_FILTER_SQL,
    esc, save_html, render_pdf, all_crime_sum_sql,
)
from reports.crime_analytics import (
    ALL_CATEGORIES, OTHER_COLUMNS, PAGE_MARGIN, EXTRA_CSS,
    _date_bounds, _to_date,
    _weekly_trend, _change_badge, _typical_vs_latest,
    _minmax5, _chronic5,
    _build_default_insights, _executive_summary_section, _strip_tags,
)

BASELINE = "Comparative Analysis"

# Scoped to the Week-By-Week table only (class="wk-table"), kept local to this
# file rather than common.py/crime_analytics.py's shared CSS. The base .compact
# table style (6.3px numbers, 800-weight navy header) reads too small and too
# heavy for print/mobile at old-age-readable sizes, so this overrides both:
# bigger, calmer header, bigger tabular numbers, thin column rules so the eye
# can track a row across 20+ week columns, and a wider bold label column.
WK_TABLE_CSS = """
  .wk-table{border-collapse:collapse}
  .wk-table thead th{font-size:7.8px;font-weight:600;letter-spacing:.01em;text-transform:none;background:#2f2a6b;color:#fff;border-right:1px solid rgba(255,255,255,.18)}
  .wk-table thead th:last-child{border-right:none}
  .wk-table tbody td{font-size:8.4px;border-right:1px solid #E7E6F0}
  .wk-table tbody td:last-child{border-right:none}
  .wk-table tbody td:first-child{font-size:9.4px;font-weight:700;white-space:normal;line-height:1.22}
  .wk-table tbody tr:nth-child(even){background:#F6F5FB}
  .wk-table td.num, .wk-table th.num{text-align:center}
"""

# Scoped to this report's own "Detail Of Each Crime" section (section 3):
# per-category weekly line chart, a rising/falling colour cue on the
# category heading, and a rising-districts chip list under the existing
# three tables. Kept local since crime_analytics.py's own Detail section
# (used by the primary report) stays exactly as it was.
DETAIL_CSS = """
  .cat-chart-wrap{margin:1mm 0 3mm}
  .rising-label{font-size:9px;font-weight:800;color:#211d50;text-transform:uppercase;letter-spacing:.02em;margin:3mm 0 1.5mm}
  .dist-rise-wrap{display:flex;flex-wrap:wrap;gap:5px}
  .dist-rise-chip{display:inline-flex;align-items:center;gap:3px;font-size:8.4px;font-weight:700;padding:3px 9px;border-radius:11px;background:#FBE7EC;color:#9F1239;border:1px solid #F3C6D1;white-space:nowrap}
  .dist-rise-empty{font-size:9px;color:var(--muted);font-style:italic}
"""


# This report's own header/footer builders (deliberately not shared with
# crime_analytics.py, so changes here never touch that file): "Reporting
# Period" comes right after the title, the baseline label below it, and
# "Issue Date" (today, when the report was generated) last.
def _pdf_header_footer(reporting_day, data_period, header_note, baseline=BASELINE):
    note_html = (
        f'<div style="margin-top:3px;font-size:9px;font-style:italic;color:#1c1d29;background:#FBEEE0;'
        f'display:inline-block;padding:2px 9px;border-radius:9px;">{esc(header_note)}</div>'
        if header_note else ""
    )
    header_tpl = f"""
<div style="width:100%;font-family:Arial,Helvetica,sans-serif;padding:8px 10mm 4px;box-sizing:border-box;-webkit-print-color-adjust:exact;">
  <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid #211d50;padding-bottom:6px;">
    <img src="{CSU_LOGO}" style="height:44px;width:auto;"/>
    <div style="text-align:center;flex:1;">
      <div style="font-size:16px;font-weight:800;color:#211d50;">Crime Analytics Punjab</div>
      <div style="font-size:11px;color:#6c7080;margin-top:4px;">Reporting Period: <b style="color:#1c1d29">{esc(data_period)}</b></div>
      <div style="margin-top:4px;font-size:10px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#2f2a6b;">{esc(baseline)}</div>
      <div style="font-size:11px;color:#6c7080;margin-top:4px;">Issue Date: <b style="color:#1c1d23">{esc(reporting_day)}</b></div>
      {note_html}
    </div>
    <div style="display:flex;flex-direction:column;align-items:center;text-align:center;gap:3px;">
      <img src="{GOVT_LOGO}" style="height:40px;width:auto;"/>
      <div style="font-size:7.4px;font-weight:800;letter-spacing:.02em;color:#211d50;line-height:1.25;text-transform:uppercase;white-space:nowrap;">Chief Minister's Office<span style="display:block;font-weight:600;color:#6c7080;text-transform:none;font-size:7.2px;">Additional Secretary<br/>(Law &amp; Order)</span></div>
    </div>
  </div>
</div>
"""
    footer_tpl = """
<div style="width:100%;font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#9aa0b0;padding:4px 10mm 6px;box-sizing:border-box;border-top:1px solid #e3e5ee;display:flex;justify-content:space-between;-webkit-print-color-adjust:exact;">
  <span>Data source: Punjab Police</span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>
"""
    return header_tpl, footer_tpl


def _preview_chrome(reporting_day, data_period, header_note, baseline=BASELINE):
    """Visible only when the raw HTML is opened in a browser (Preview & Edit)."""
    note_html = f'<div class="note">{esc(header_note)}</div>' if header_note else ""
    mast = f"""
<div class="preview-mast">
  <img class="logo" src="{CSU_LOGO}"/>
  <div class="center">
    <div class="title">Crime Analytics Punjab</div>
    <div class="meta">Reporting Period: <b>{esc(data_period)}</b></div>
    <div class="baseline">{esc(baseline)}</div>
    <div class="meta">Issue Date: <b>{esc(reporting_day)}</b></div>
    {note_html}
  </div>
  <div class="right">
    <img class="logo" src="{GOVT_LOGO}"/>
    <div class="office">Chief Minister's Office<span>Additional Secretary<br/>(Law &amp; Order)</span></div>
  </div>
</div>
"""
    foot = """
<div class="preview-foot">Data source: Punjab Police</div>
"""
    return mast, foot


def _week_template(end_date):
    """Every calendar-month-locked week slot from 01 May of the reporting
    year through the week containing end_date, whether or not any data
    exists yet for a given slot (May/June currently have none)."""
    template = []
    yr, mo = end_date.year, 5
    while (yr, mo) <= (end_date.year, end_date.month):
        next_month = date(yr + 1, 1, 1) if mo == 12 else date(yr, mo + 1, 1)
        days_in_month = (next_month - timedelta(days=1)).day
        max_week = ((days_in_month - 1) // 7) + 1
        if (yr, mo) == (end_date.year, end_date.month):
            max_week = ((end_date.day - 1) // 7) + 1
        for wk in range(1, max_week + 1):
            week_start_day = (wk - 1) * 7 + 1
            week_end_day = min(wk * 7, days_in_month)
            expected_days = week_end_day - week_start_day + 1
            template.append(dict(
                yr=yr, mo=mo, wk=wk, label=f'{date(yr, mo, 1).strftime("%b")} Wk{wk}',
                expected_days=expected_days,
            ))
        mo += 1
    return template


def _weekly_by_category_data(start_date, end_date):
    """Buckets days into calendar-month-locked weeks (days 1-7 = Week 1,
    8-14 = Week 2, ...), the way the source cards number weeks, rather
    than a rolling 7-day window from an arbitrary start date. Weeks before
    the data actually begins (May, June) are included as empty columns."""
    cols = [c for c, _ in ALL_CATEGORIES]
    sql = f"""
        SELECT EXTRACT(YEAR FROM c.report_date)::int yr, EXTRACT(MONTH FROM c.report_date)::int mo,
          ((EXTRACT(DAY FROM c.report_date)::int - 1) / 7 + 1)::int wk,
          COUNT(DISTINCT c.report_date) days,
          {",".join(f"COALESCE(SUM(c.{col}),0) AS {col}" for col in cols)}
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY yr, mo, wk ORDER BY yr, mo, wk
    """
    rows = db.query(sql, (start_date, end_date))
    data_by_key = {(r["yr"], r["mo"], r["wk"]): r for r in rows}

    weeks = []
    per_category = {col: [] for col in cols}
    for t in _week_template(end_date):
        r = data_by_key.get((t["yr"], t["mo"], t["wk"]))
        has_data = r is not None
        days = r["days"] if has_data else 0
        weeks.append(dict(
            label=t["label"], days=days, expected_days=t["expected_days"],
            is_complete=has_data and days >= t["expected_days"], has_data=has_data,
        ))
        for col in cols:
            per_category[col].append(r[col] if has_data else None)

    return weeks, per_category


def _week_trend_badge(latest_val, typical):
    if not typical:
        return "fl", "&#9668;&#9658; n/a"
    pct = (latest_val - typical) / typical * 100
    if abs(pct) < 3:
        return "fl", "&#9668;&#9658; 0%"
    if pct > 0:
        return "up", f"&#9650;{pct:.0f}%"
    return "dn", f"&#9660;{abs(pct):.0f}%"


def _cal_week_label(d):
    """'Jun Wk1' style label for a date, matching the Week-By-Week Case
    Count table above it, so the two sections read as the same weeks
    instead of two different numbering schemes ("Week 1" vs "Jun Wk1")."""
    wk = ((d.day - 1) // 7) + 1
    return f'{d.strftime("%b")} Wk{wk}'


def _weekly_trend_section(start_date, end_date):
    """Local copy of crime_analytics._weekly_section(), swapping its plain
    "Week N" labels for calendar month+week labels ("Jun Wk1") so this
    section lines up with the Week-By-Week Case Count table above it. Kept
    local rather than editing the shared function, since crime_analytics.py
    uses the plain "Week N" labelling for its own (unrelated) section 1."""
    weekly = _weekly_trend(start_date, end_date)
    if not weekly:
        return ""
    avgs = [round(w["week_total"] / w["n_days"], 1) if w["n_days"] else 0 for w in weekly]

    CW, CH = 660, 170
    PAD_L, PAD_R, PAD_T, PAD_B = 42, 20, 16, 26
    plot_w, plot_h = CW - PAD_L - PAD_R, CH - PAD_T - PAD_B
    lo_v, hi_v = (min(avgs) * 0.85 if avgs else 0), (max(avgs) * 1.1 if avgs else 1)

    def xy(i, v):
        x = PAD_L + (plot_w * i / max(len(avgs) - 1, 1))
        y = PAD_T + plot_h * (1 - (v - lo_v) / (hi_v - lo_v if hi_v != lo_v else 1))
        return x, y

    pts = [xy(i, v) for i, v in enumerate(avgs)]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = path_d + f" L {pts[-1][0]:.1f},{PAD_T+plot_h} L {pts[0][0]:.1f},{PAD_T+plot_h} Z"
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#211d50"/>' for x, y in pts)
    labels = "".join(
        f'<text x="{pts[i][0]:.1f}" y="{CH-6}" font-size="8" fill="#6c7080" text-anchor="middle">{_cal_week_label(w["week_start"])}{"*" if w["n_days"]<7 else ""}</text>'
        f'<text x="{pts[i][0]:.1f}" y="{pts[i][1]-7:.1f}" font-size="8" fill="#211d50" font-weight="700" text-anchor="middle">{avgs[i]}</text>'
        for i, w in enumerate(weekly)
    )
    chart_svg = f'<svg viewBox="0 0 {CW} {CH}" width="100%" height="{CH}"><path d="{area_d}" fill="#211d50" opacity="0.06"/><path d="{path_d}" fill="none" stroke="#211d50" stroke-width="2.2"/>{dots}{labels}</svg>'

    week_rows = ""
    for i, w in enumerate(weekly):
        badge = _change_badge(avgs[i], avgs[i-1]) if i > 0 else '<span class="trend-fl">start</span>'
        partial = " *" if w["n_days"] < 7 else ""
        week_rows += (
            f'<tr><td><b>{_cal_week_label(w["week_start"])}</b>{partial}</td><td>{w["week_start"]} to {w["week_end"]}</td>'
            f'<td class="num tnum">{w["week_total"]}</td><td class="num tnum">{avgs[i]}</td><td>{badge}</td></tr>'
        )

    typical_avg, latest_avg, overall_pct, direction = _typical_vs_latest(weekly)

    return f"""
  <div class="flow-section">
    <div class="section-heading avoid-orphan"><span class="bar"></span><h2>Is Crime Rising Or Falling: Week By Week</h2></div>
    <div class="section-sub">Average cases per day, every recorded category combined. * marks a partial week (fewer than 7 days on file).</div>
    <div class="keep">{chart_svg}</div>
    <div class="table-wrap keep" style="margin-top:4mm">
      <table>
        <thead class="amber"><tr><th>Week</th><th>Dates</th><th class="num">Total</th><th class="num">Avg/Day</th><th>Change</th></tr></thead>
        <tbody>{week_rows}</tbody>
      </table>
    </div>
    <div class="callout amber keep" style="margin-top:3mm">
      <b>Overall direction.</b> The most recent complete week averaged {latest_avg} cases per day, against a typical week of {typical_avg}. The province is {direction} ({overall_pct:+.0f}% vs typical).
    </div>
  </div>
"""


def _weekly_category_section(start_date, end_date):
    weeks, per_category = _weekly_by_category_data(start_date, end_date)
    if not weeks:
        return ""

    complete_idxs = [i for i, w in enumerate(weeks) if w["is_complete"]]
    latest_idx = complete_idxs[-1] if complete_idxs else None

    HDR = 'padding:4px 2px;white-space:normal;line-height:1.25;word-break:keep-all'
    week_headers = "".join(
        f'<th class="num" style="{HDR}">{esc(w["label"]).replace(" ", "<br/>")}{"" if w["is_complete"] or not w["has_data"] else " *"}</th>'
        for w in weeks
    )

    PAD = 'padding:3px 2px;white-space:nowrap'
    LABEL_PAD = 'padding:3px 5px;white-space:normal'
    trs = ""
    for col, label in ALL_CATEGORIES:
        series = per_category[col]
        complete_vals = [series[i] for i in complete_idxs]
        typical = sum(complete_vals) / len(complete_vals) if complete_vals else 0
        if latest_idx is not None:
            trend_cls, trend_label = _week_trend_badge(series[latest_idx], typical)
        else:
            trend_cls, trend_label = "fl", "&#9668;&#9658; n/a"
        badge_css = {"up": "trend-up", "dn": "trend-dn", "fl": "trend-fl"}[trend_cls]
        # The latest *complete* week is the one the Typical/trend comparison
        # is actually based on, so its own cell in the week columns gets the
        # same red/green (rising/falling) colour as the trend badge, instead
        # of looking like every other plain number in the row.
        cell_parts = []
        for i, v in enumerate(series):
            val_str = "-" if v is None else str(v)
            if i == latest_idx:
                cell_parts.append(f'<td class="num tnum {badge_css}" style="{PAD}"><b>{val_str}</b></td>')
            else:
                cell_parts.append(f'<td class="num tnum" style="{PAD}">{val_str}</td>')
        cells = "".join(cell_parts)
        trs += (
            f'<tr><td style="{LABEL_PAD}">{label}</td>{cells}'
            f'<td class="num tnum" style="{PAD}"><b>{typical:.1f}</b></td>'
            f'<td class="num tnum {badge_css}" style="{PAD}"><b>{trend_label}</b></td></tr>'
        )

    latest_label = weeks[latest_idx]["label"] if latest_idx is not None else "n/a"

    # This table can grow to 20+ columns (every week from May onward), so it
    # gets its own fixed-width layout rather than the shared .compact style:
    # a wide label column plus every remaining column sized equally, however
    # many there are, so it always fills the page width without overflowing.
    n_data_cols = len(weeks) + 2  # weeks + Typical + vs-latest
    label_w, total_w = 27, 182
    col_w = (total_w - label_w) / n_data_cols
    colgroup = f'<col style="width:{label_w}mm">' + f'<col style="width:{col_w:.2f}mm">' * n_data_cols

    return f"""
  <div class="flow-section keep">
    <div class="section-heading avoid-orphan"><span class="bar"></span><h2>Week-By-Week Case Count</h2></div>
    <div class="section-sub">Typical is the average of every complete week on file. We compare the most recent complete week against Typical to decide whether each crime is rising or falling.</div>
    <div class="table-wrap keep">
      <table class="wk-table" style="table-layout:fixed;width:{total_w}mm">
        <colgroup>{colgroup}</colgroup>
        <thead class="navy"><tr><th style="padding:4px 5px;white-space:normal;font-weight:600">Crime Category</th>{week_headers}<th class="num" style="{HDR}">Typical</th><th class="num" style="{HDR}">vs<br/>{esc(latest_label).replace(" ", "<br/>")}</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
    </div>
  </div>
"""


# ═══════════════════════════════════════════════════════════════════════
# Section 3 (local): Detail Of Each Crime, redesigned for this report only.
# Per category: a red/blue heading (rising vs not, same >=3% rule used
# everywhere else in this report), a weekly line chart, the same three
# most-cases/chronic/fewest-cases tables as crime_analytics.py's version,
# and a list of districts driving the rise for that category.
# ═══════════════════════════════════════════════════════════════════════
RISE_COLOR = "#9F1239"   # red - a category trending up
FALL_COLOR = "#1D4ED8"   # blue - flat or falling
MIN_DISTRICT_TOTAL = 3   # ignore districts too quiet to call a real "rise"


def _category_chart_svg(weeks, series):
    idxs = [i for i, w in enumerate(weeks) if w["has_data"]]
    if not idxs:
        return '<div class="dist-rise-empty">No data yet for this category.</div>'
    vals = [series[i] for i in idxs]
    labels = [weeks[i]["label"] for i in idxs]
    partial = [not weeks[i]["is_complete"] for i in idxs]

    CW, CH = 660, 118
    PAD_L, PAD_R, PAD_T, PAD_B = 20, 20, 16, 22
    plot_w, plot_h = CW - PAD_L - PAD_R, CH - PAD_T - PAD_B
    lo_v, hi_v = min(vals) * 0.85, max(vals) * 1.15
    if hi_v == lo_v:
        hi_v = lo_v + 1

    def xy(i, v):
        x = PAD_L + (plot_w * i / max(len(vals) - 1, 1))
        y = PAD_T + plot_h * (1 - (v - lo_v) / (hi_v - lo_v))
        return x, y

    pts = [xy(i, v) for i, v in enumerate(vals)]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = path_d + f" L {pts[-1][0]:.1f},{PAD_T+plot_h} L {pts[0][0]:.1f},{PAD_T+plot_h} Z"
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#211d50"/>' for x, y in pts)
    lbls = "".join(
        f'<text x="{pts[i][0]:.1f}" y="{CH-5}" font-size="7.2" fill="#6c7080" text-anchor="middle">{esc(labels[i])}{"*" if partial[i] else ""}</text>'
        f'<text x="{pts[i][0]:.1f}" y="{pts[i][1]-6:.1f}" font-size="7.4" fill="#211d50" font-weight="700" text-anchor="middle">{vals[i]}</text>'
        for i in range(len(vals))
    )
    return (
        f'<svg viewBox="0 0 {CW} {CH}" width="100%" height="{CH}">'
        f'<path d="{area_d}" fill="#211d50" opacity="0.06"/>'
        f'<path d="{path_d}" fill="none" stroke="#211d50" stroke-width="2"/>{dots}{lbls}</svg>'
    )


def _district_weekly_totals(col, start_date, end_date, template):
    sql = f"""
        SELECT d.name_en district,
          EXTRACT(YEAR FROM c.report_date)::int yr, EXTRACT(MONTH FROM c.report_date)::int mo,
          ((EXTRACT(DAY FROM c.report_date)::int - 1) / 7 + 1)::int wk,
          COALESCE(SUM(c.{col}),0) v
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en, yr, mo, wk
    """
    rows = db.query(sql, (start_date, end_date))
    by_key = {(r["district"], r["yr"], r["mo"], r["wk"]): r["v"] for r in rows}
    districts = sorted({r["district"] for r in rows})
    return {
        district: [by_key.get((district, t["yr"], t["mo"], t["wk"]), 0) for t in template]
        for district in districts
    }


def _rising_districts(col, complete_idxs, latest_idx, template, start_date, end_date):
    if latest_idx is None:
        return []
    district_series = _district_weekly_totals(col, start_date, end_date, template)
    rising = []
    for district, series in district_series.items():
        complete_vals = [series[i] for i in complete_idxs]
        typical = sum(complete_vals) / len(complete_vals) if complete_vals else 0
        latest_val = series[latest_idx]
        if (latest_val + sum(complete_vals)) < MIN_DISTRICT_TOTAL:
            continue
        pct = ((latest_val - typical) / typical * 100) if typical else (100.0 if latest_val else 0.0)
        if pct >= 3 and latest_val > 0:
            rising.append((district, latest_val, pct, typical))
    rising.sort(key=lambda x: (-x[2], -x[1]))
    return rising[:6]


def _detail_section_local(start_date, end_date):
    weeks, per_category = _weekly_by_category_data(start_date, end_date)
    complete_idxs = [i for i, w in enumerate(weeks) if w["is_complete"]]
    latest_idx = complete_idxs[-1] if complete_idxs else None
    template = _week_template(end_date)

    blocks = ""
    for col, label in ALL_CATEGORIES:
        series = per_category[col]
        complete_vals = [series[i] for i in complete_idxs]
        typical = sum(complete_vals) / len(complete_vals) if complete_vals else 0
        if latest_idx is not None:
            latest_val = series[latest_idx]
            pct = ((latest_val - typical) / typical * 100) if typical else (100.0 if latest_val else 0.0)
        else:
            pct = 0.0
        heading_color = RISE_COLOR if pct >= 3 else FALL_COLOR

        chart_svg = _category_chart_svg(weeks, series)

        maxrows, minrows = _minmax5(col, start_date, end_date)
        chronicrows = _chronic5(col, start_date, end_date)
        max_html = "".join(
            f'<tr><td><span class="rank crimson">{i+1}</span></td><td><b>{r["name_en"]}</b></td><td class="num tnum">{r["v"]}</td></tr>'
            for i, r in enumerate(maxrows)
        )
        min_html = "".join(
            f'<tr><td><span class="rank teal">{i+1}</span></td><td><b>{r["name_en"]}</b></td><td class="num tnum">{r["v"]}</td></tr>'
            for i, r in enumerate(minrows)
        )
        chronic_html = "".join(
            f'<tr><td><span class="rank violet">{i+1}</span></td><td><b>{r["name_en"]}</b></td><td class="num tnum">{r["days_with_cases"]}</td></tr>'
            for i, r in enumerate(chronicrows)
        ) or '<tr><td colspan="3" style="text-align:center;color:#9aa0b0">No days with cases</td></tr>'

        rising_districts = _rising_districts(col, complete_idxs, latest_idx, template, start_date, end_date)
        if rising_districts:
            chips = "".join(
                f'<span class="dist-rise-chip">{esc(dname)} &middot; Typical <b>{dtyp:.1f}</b> '
                f'&rarr; <b>{dval}</b> cases ({dpct:+.0f}%)</span>'
                for dname, dval, dpct, dtyp in rising_districts
            )
            rising_html = f'<div class="dist-rise-wrap">{chips}</div>'
        else:
            rising_html = '<div class="dist-rise-empty">No district shows a meaningful rise in this category for the latest complete week.</div>'

        blocks += f"""
  <div class="cat-block keep">
    <h3 style="color:{heading_color}">{label}</h3>
    <div class="cat-chart-wrap">{chart_svg}</div>
    <div class="three-col">
      <div class="table-wrap"><table><thead class="crimson"><tr><th>#</th><th>Most Cases</th><th class="num">Cases</th></tr></thead><tbody>{max_html}</tbody></table></div>
      <div class="table-wrap"><table><thead class="violet"><tr><th>#</th><th>Chronic (Most Days)</th><th class="num">Days</th></tr></thead><tbody>{chronic_html}</tbody></table></div>
      <div class="table-wrap"><table><thead class="teal"><tr><th>#</th><th>Fewest Cases</th><th class="num">Cases</th></tr></thead><tbody>{min_html}</tbody></table></div>
    </div>
    <div class="rising-label">Rising Districts (latest complete week vs. typical)</div>
    {rising_html}
  </div>
"""

    return f"""
  <div class="flow-section">
    <div class="keep avoid-orphan">
      <div class="section-heading"><span class="bar"></span><h2>Detail Of Each Crime</h2></div>
      <div class="section-sub">Category name is red when it is rising and blue otherwise. Weekly trend, highest/lowest/most chronic districts, and which districts are driving the rise, for every recorded category.</div>
    </div>
    {blocks}
  </div>
"""


# Local copy of crime_analytics._composition_section(), wrapped in a single
# "keep" block so the whole district-mix table (heading, intro text, all 39
# rows) lands together on one page instead of the browser stranding a
# handful of rows on the current page and pushing the rest to the next.
# The table itself comfortably fits one page's height, so "keep" just needs
# to push the whole section as a unit rather than let it split awkwardly.
def _composition_section_local(start_date, end_date):
    other_sql = "+".join(f"c.{c}" for c in OTHER_COLUMNS)
    sql = f"""
        SELECT d.name_en,
          COALESCE(SUM(c.murder),0) AS murder, COALESCE(SUM(c.robbery),0) AS robbery,
          COALESCE(SUM(c.child_abuse),0) AS child_abuse, COALESCE(SUM(c.rape),0) AS rape,
          COALESCE(SUM(c.gang_rape),0) AS gang_rape, COALESCE(SUM(c.snatching_jhappata),0) AS snatching,
          COALESCE(SUM({other_sql}),0) AS other,
          COALESCE(SUM({all_crime_sum_sql('c')}),0) AS total
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en ORDER BY total DESC
    """
    rows = db.query(sql, (start_date, end_date))
    grand_total = sum(r["total"] for r in rows) or 1

    trs = ""
    for i, r in enumerate(rows):
        t = r["total"] or 1
        trs += (
            f'<tr><td>{i+1}</td><td><b>{r["name_en"]}</b></td>'
            f'<td class="num tnum">{r["murder"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["robbery"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["child_abuse"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["rape"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["gang_rape"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["snatching"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["other"]/t*100:.1f}%</td>'
            f'<td class="num tnum"><b>{r["total"]}</b></td>'
            f'<td class="num tnum" style="color:#211d50;font-weight:800">{r["total"]/grand_total*100:.1f}%</td></tr>'
        )

    return f"""
  <div class="flow-section keep">
    <div class="section-heading"><span class="bar"></span><h2>Each District's Crime Mix And Contribution To Punjab</h2></div>
    <div class="section-sub">The first seven columns break each district's own total into categories and add up to 100% per row. Other covers every remaining category including Road Accident Casualties and Religious Issues. The last column is each district's share of every case reported anywhere in Punjab this period.</div>
    <div class="table-wrap">
      <table class="compact" style="font-size:8px">
        <thead class="navy"><tr><th>#</th><th>District</th><th class="num">Murder</th><th class="num">Robbery</th><th class="num">Child Abuse</th><th class="num">Rape</th><th class="num">Gang Rape</th><th class="num">Snatching</th><th class="num">Other</th><th class="num">Total</th><th class="num">Contribution To Punjab</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
    </div>
  </div>
"""


def _weekly_context(start_date, end_date):
    """Facts about the latest complete week vs. its typical baseline, plus
    which districts are driving the Murder and Robbery rises specifically --
    everything crime_analytics._build_default_insights() needs for the
    "Crimes Showing Increase/Decline" and "Emerging District Trends" points,
    which depend on this report's calendar-locked week/typical machinery and
    so have no equivalent in the primary report. Returns None when there
    isn't yet a second complete week to compare against."""
    weeks, per_category = _weekly_by_category_data(start_date, end_date)
    complete_idxs = [i for i, w in enumerate(weeks) if w["is_complete"]]
    if len(complete_idxs) < 2:
        return None
    latest_idx = complete_idxs[-1]
    latest_label = weeks[latest_idx]["label"]

    MIN_MEANINGFUL_TOTAL = 20
    changes = []
    for col, label in ALL_CATEGORIES:
        series = per_category[col]
        complete_vals = [series[i] for i in complete_idxs]
        typical = sum(complete_vals) / len(complete_vals)
        latest_val = series[latest_idx]
        pct = ((latest_val - typical) / typical * 100) if typical else (100.0 if latest_val else 0.0)
        if (latest_val + sum(complete_vals)) >= MIN_MEANINGFUL_TOTAL:
            changes.append((label, pct))
    rising = sorted([c for c in changes if c[1] >= 3], key=lambda c: -c[1])
    falling = sorted([c for c in changes if c[1] <= -3], key=lambda c: c[1])

    template = _week_template(end_date)
    murder_rising = _rising_districts("murder", complete_idxs, latest_idx, template, start_date, end_date)
    robbery_rising = _rising_districts("robbery", complete_idxs, latest_idx, template, start_date, end_date)

    return dict(
        latest_label=latest_label, rising=rising, falling=falling,
        murder_rising=murder_rising, robbery_rising=robbery_rising,
    )


def default_insights(start_date=None, end_date=None, **_):
    """Public entry point for the report-generation form -- see
    crime_analytics.default_insights() for the general shape; this variant
    also includes the weekly rising/falling facts specific to this report."""
    earliest, latest = _date_bounds()
    start_date = _to_date(start_date) if start_date else earliest
    end_date = _to_date(end_date) if end_date else latest
    weekly_context = _weekly_context(start_date, end_date)
    items = _build_default_insights(start_date, end_date, weekly_context=weekly_context)
    return [dict(color=color, tag=tag, text=_strip_tags(text)) for color, tag, text in items]


def generate(start_date=None, end_date=None, reporting_day=None, header_note=None, output="pdf",
             custom_insights=None, override_defaults=False, **_):
    earliest, latest = _date_bounds()
    start_date = _to_date(start_date) if start_date else earliest
    end_date = _to_date(end_date) if end_date else latest
    reporting_day = reporting_day or date.today().strftime("%d/%m/%Y")
    n_days = (end_date - start_date).days + 1
    data_period = f"{start_date} to {end_date} ({n_days} day{'s' if n_days != 1 else ''})"

    weekly_context = None if override_defaults else _weekly_context(start_date, end_date)

    sections = (
        _executive_summary_section(start_date, end_date, weekly_context=weekly_context,
                                    custom_insights=custom_insights, override_defaults=override_defaults)
        + _weekly_category_section(start_date, end_date)
        + _weekly_trend_section(start_date, end_date)
        + _detail_section_local(start_date, end_date)
        + _composition_section_local(start_date, end_date)
    )

    header_tpl, footer_tpl = _pdf_header_footer(reporting_day, data_period, header_note, baseline=BASELINE)
    preview_mast, preview_foot = _preview_chrome(reporting_day, data_period, header_note, baseline=BASELINE)
    pdf_config = json.dumps(dict(
        headerTemplate=header_tpl, footerTemplate=footer_tpl, margin=PAGE_MARGIN,
    ))

    toolbar = EDIT_TOOLBAR if output == "html" else ""
    html = f"""<!doctype html>
<html><head><meta charset="utf-8" /><title>Crime Analytics Punjab</title><style>{BASE_CSS}{EXTRA_CSS}{WK_TABLE_CSS}{DETAIL_CSS}</style></head>
<body>{toolbar}
<div class="flow-body">
{preview_mast}
{sections}
{preview_foot}
</div>
<script type="application/json" id="pdf-header-footer">{pdf_config}</script>
</body></html>
"""
    return save_html(html) if output == "html" else render_pdf(html)
