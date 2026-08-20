# -*- coding: utf-8 -*-
"""Crime Analytics Punjab: the combined report for major meetings.
Defaults to the full data history (01 July onward, through the latest day
on file) but the date range can be overridden like any other report.
Counts ALL 14 recorded categories, including Road Accident Casualties and
Religious Issues, per explicit instruction.

Unlike every other report in this project, this one uses a flowing layout
(no one-section-per-fixed-page), with a masthead and footer that repeat on
every physical PDF page via Puppeteer's header/footer templates. See
render/render.mjs for the mechanism.
"""
import json
import re
from datetime import date, timedelta

import db
from reports.common import (
    ALL_CATEGORIES, HEADLINE_CATEGORIES, DISTRICT_FILTER_SQL, CSS as BASE_CSS,
    CSU_LOGO, GOVT_LOGO, EDIT_TOOLBAR, esc, save_html, render_pdf, all_crime_sum_sql,
)

OTHER_COLUMNS = [c for c, _ in ALL_CATEGORIES if c not in
                 ("murder", "robbery", "child_abuse", "rape", "gang_rape", "snatching_jhappata")]

_TAG_RE = re.compile(r"<[^>]+>")

# Single source of truth for the reserved header/footer space, used both in
# the @page CSS rule and the Puppeteer page.pdf() margin option below. They
# must match: common.CSS declares "@page{margin:0}" for the other reports'
# fixed-page-per-section layout, and that rule otherwise wins over the JS
# margin option in this Chromium build regardless of what page.pdf() is told.
PAGE_MARGIN = dict(top="36mm", right="13mm", bottom="16mm", left="13mm")

# Labels matched word-for-word to the production Daily Crime & Situation
# Analytics report so this section reads identically to it.
COMPARATIVE_LABELS = {
    "murder": "Murder", "dacoity": "Dacoity", "robbery": "Robbery",
    "dacoity_robbery_murder": "Dacoity with Murder",
    "dacoity_robbery_injury": "Dacoity/Robbery with Injury",
    "dacoity_robbery_rape": "Dacoity/Robbery with Rape",
    "snatching_jhappata": "Snatching Jhappata", "child_abuse": "Child Abuse",
    "rape": "Rape", "gang_rape": "Gang Rape", "sodomy": "Sodomy",
    "road_accident_casualties": "Road Accident Casualties",
    "acid_attack": "Acid Attack", "religious_issues": "Religious issues",
}


# ═══════════════════════════════════════════════════════════════════════
# Report-specific CSS: flowing layout instead of one-page-per-section
# ═══════════════════════════════════════════════════════════════════════
EXTRA_CSS = """
  @page{size:A4;margin:__PAGE_MARGIN__}
  body{background:#fff}
  @media screen{ body{background:#DDD} }
  .flow-body{max-width:800px;margin:0 auto;padding:0 0 10mm;background:#fff}
  @media screen{ .flow-body{padding:16mm 13mm 20mm;box-shadow:0 4px 24px rgba(0,0,0,.12);margin:14px auto} }
  .flow-section{margin-bottom:7mm}
  .keep{break-inside:avoid;page-break-inside:avoid}
  table tr{break-inside:avoid;page-break-inside:avoid}
  .avoid-orphan{break-after:avoid;page-break-after:avoid}
  .section-heading{display:flex;align-items:center;gap:8px;margin:0 0 3mm;padding-bottom:2mm;border-bottom:2px solid var(--line)}
  .section-heading .bar{width:4px;height:13px;background:var(--navy);border-radius:2px;flex:0 0 auto}
  .section-heading h2{font-size:12.5px;font-weight:900;color:var(--navy);text-transform:uppercase;letter-spacing:.03em}
  .section-heading .diamond{color:var(--navy);font-size:12px}
  .section-sub{font-size:9.5px;color:var(--muted);margin:0 0 3mm 12px}

  .preview-mast{display:none}
  .preview-foot{display:none}
  @media screen{
    .preview-mast{display:grid;grid-template-columns:100px 1fr 100px;align-items:center;gap:10px;padding-bottom:8px;margin-bottom:8mm;border-bottom:2.5px solid var(--navy)}
    .preview-mast img.logo{height:44px;width:auto}
    .preview-mast .center{text-align:center}
    .preview-mast .title{font-size:15px;font-weight:800;color:var(--navy)}
    .preview-mast .meta{font-size:10.5px;color:var(--muted);margin-top:4px}
    .preview-mast .baseline{margin-top:4px;font-size:10px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:var(--navy-2)}
    .preview-mast .note{margin-top:4px;font-size:10px;font-style:italic;background:var(--amber-bg);display:inline-block;padding:2px 10px;border-radius:10px}
    .preview-mast .right{display:flex;flex-direction:column;align-items:center;text-align:center;gap:3px}
    .preview-mast .office{font-size:7.4px;font-weight:800;letter-spacing:.02em;color:var(--navy);line-height:1.25;text-transform:uppercase}
    .preview-mast .office span{display:block;font-weight:600;color:var(--muted);text-transform:none;font-size:7.2px}
    .preview-foot{margin-top:10mm;padding-top:5px;border-top:1px solid var(--line);font-size:8px;color:var(--faint)}
  }

  .cmp-table{font-size:9px}
  .cmp-table th, .cmp-table td{padding:5px 7px}
  .trend-up{color:var(--crimson);font-weight:800}
  .trend-dn{color:var(--teal);font-weight:800}
  .trend-fl{color:var(--muted);font-weight:700}
  .status-chip{display:inline-block;font-size:8px;font-weight:800;padding:2px 8px;border-radius:10px}
  .status-normal{background:var(--teal-bg);color:var(--teal)}
  .status-above{background:var(--amber-bg);color:var(--amber)}
  .status-spike{background:var(--crimson-bg);color:var(--crimson)}
  .legend-row{display:flex;flex-wrap:wrap;gap:14px;align-items:center;font-size:9px;color:var(--muted);margin-bottom:6px}
  .legend-row .chip{display:inline-block;width:12px;height:8px;border-radius:3px;margin-right:4px;vertical-align:middle}

  .insights-box{display:flex;flex-direction:column;gap:2mm}
  .insight-card{border:1px solid var(--line);border-left:4px solid var(--navy);border-radius:8px;background:#F5F5F8;padding:8px 15px 9px}
  .insight-card.crimson{border-left-color:var(--crimson)}
  .insight-card.violet{border-left-color:var(--violet)}
  .insight-card.teal{border-left-color:var(--teal)}
  .insight-card.amber{border-left-color:var(--amber)}
  .insight-card-head{display:flex;align-items:center;gap:8px;margin-bottom:3px}
  .insight-num{flex:0 0 auto;width:19px;height:19px;border-radius:50%;background:var(--navy);color:#fff;font-size:9.6px;font-weight:800;display:flex;align-items:center;justify-content:center}
  .insight-card .subhead{font-size:13px;font-weight:800;color:var(--navy);text-transform:uppercase;letter-spacing:.02em}
  .insight-card p{font-size:13.5px;line-height:1.5;color:var(--ink);margin:0}

  .cat-block{margin-bottom:5mm}
  .cat-block h3{font-size:10.5px;font-weight:800;color:var(--crimson);text-transform:uppercase;letter-spacing:.02em;margin-bottom:2mm}
  .three-col{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6mm;margin-bottom:0}
  .three-col .table-wrap table{font-size:8.6px}
  .three-col .table-wrap th, .three-col .table-wrap td{padding:4px 6px}
"""
EXTRA_CSS = EXTRA_CSS.replace(
    "__PAGE_MARGIN__",
    f'{PAGE_MARGIN["top"]} {PAGE_MARGIN["right"]} {PAGE_MARGIN["bottom"]} {PAGE_MARGIN["left"]}',
)


# ═══════════════════════════════════════════════════════════════════════
# Data helpers
# ═══════════════════════════════════════════════════════════════════════
def _date_bounds():
    row = db.query_one(f"""
        SELECT MIN(c.report_date) AS earliest, MAX(c.report_date) AS latest
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL}
    """)
    return row["earliest"], row["latest"]


def _to_date(d):
    return d if isinstance(d, date) else date.fromisoformat(str(d))


def _daily_sums_sql(categories, alias="c"):
    return ",".join(f"COALESCE(SUM({alias}.{col}),0) AS {col}" for col in categories)


def _classify(today_v, q3, max_v):
    if not q3 and not max_v:
        return "normal", "Normal"
    if today_v > (max_v or 0):
        return "spike", "Spike"
    if today_v > (q3 or 0):
        return "above", "Above"
    return "normal", "Normal"


def _trend(today_v, med):
    if not med:
        return "fl", "&#9668;&#9658; 0%"
    pct = (today_v - med) / med * 100
    if abs(pct) < 3:
        return "fl", "&#9668;&#9658; 0%"
    if pct > 0:
        return "up", f"&#9650;{pct:.0f}%"
    return "dn", f"&#9660;{abs(pct):.0f}%"


def _comparative_data(today_date):
    cols = [c for c, _ in ALL_CATEGORIES]
    today = _to_date(today_date)
    year = today.year

    today_row = db.query_one(f"""
        SELECT {_daily_sums_sql(cols)}
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date = %(today)s
    """, dict(today=today))

    stat_exprs = ",".join(
        f"percentile_cont(0.5) WITHIN GROUP (ORDER BY {col}) AS {col}_med,"
        f"percentile_cont(0.75) WITHIN GROUP (ORDER BY {col}) AS {col}_q3,"
        f"MAX({col}) AS {col}_max, MIN({col}) AS {col}_lo"
        for col in cols
    )
    baseline_row = db.query_one(f"""
        WITH daily AS (
          SELECT c.report_date, {_daily_sums_sql(cols)}
          FROM crime_daily c JOIN districts d ON d.id = c.district_id
          WHERE {DISTRICT_FILTER_SQL}
            AND c.report_date >= %(today)s::date - INTERVAL '30 days'
            AND c.report_date < %(today)s::date
          GROUP BY c.report_date
        )
        SELECT COUNT(*) AS days_of_data, {stat_exprs} FROM daily
    """, dict(today=today))

    def month_avg(month):
        return db.query_one(f"""
            WITH daily AS (
              SELECT c.report_date, {_daily_sums_sql(cols)}
              FROM crime_daily c JOIN districts d ON d.id = c.district_id
              WHERE {DISTRICT_FILTER_SQL}
                AND EXTRACT(YEAR FROM c.report_date) = %(year)s
                AND EXTRACT(MONTH FROM c.report_date) = %(month)s
              GROUP BY c.report_date
            )
            SELECT {",".join(f"COALESCE(AVG({col}),0) AS {col}" for col in cols)} FROM daily
        """, dict(year=year, month=month))

    july_row = month_avg(7)
    aug_row = month_avg(8)

    out = []
    for col, _ in ALL_CATEGORIES:
        today_v = today_row[col] or 0
        med = baseline_row[f"{col}_med"] or 0
        q3 = baseline_row[f"{col}_q3"] or 0
        max_v = baseline_row[f"{col}_max"] or 0
        status_cls, status_label = _classify(today_v, q3, max_v)
        trend_cls, trend_label = _trend(today_v, med)
        out.append(dict(
            col=col, label=COMPARATIVE_LABELS[col], today=today_v, med=med, q3=q3, max=max_v,
            avg_july=round(july_row[col] or 0, 1), avg_aug=round(aug_row[col] or 0, 1),
            status_cls=status_cls, status_label=status_label,
            trend_cls=trend_cls, trend_label=trend_label,
        ))
    return out, baseline_row["days_of_data"]


def _bar_svg(row):
    q3, med, max_v, today_v = row["q3"], row["med"], row["max"], row["today"]
    scale_max = max(max_v, today_v, 1) * 1.15
    W, H = 90, 13
    def x(v):
        return min(v / scale_max, 1) * W
    q3_x, med_x, today_x = x(q3), x(med), x(today_v)
    dot_color = {"normal": "#0F766E", "above": "#B45309", "spike": "#9F1239"}[row["status_cls"]]
    return f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
      <rect x="0" y="3.5" width="{q3_x:.1f}" height="6" fill="#E4F3F0" rx="2"/>
      <rect x="{q3_x:.1f}" y="3.5" width="{max(x(max_v)-q3_x,0):.1f}" height="6" fill="#FBEEE0" rx="1"/>
      <rect x="{x(max_v):.1f}" y="3.5" width="{max(W-x(max_v),0):.1f}" height="6" fill="#FBE7EC" rx="1"/>
      <line x1="{med_x:.1f}" y1="0.5" x2="{med_x:.1f}" y2="12.5" stroke="#211d50" stroke-width="1.2"/>
      <circle cx="{today_x:.1f}" cy="6.5" r="3" fill="{dot_color}" stroke="#fff" stroke-width="0.8"/>
    </svg>"""


# ═══════════════════════════════════════════════════════════════════════
# Section 1: comparative analysis
# ═══════════════════════════════════════════════════════════════════════
def _comparative_section(today_date):
    rows, days_of_data = _comparative_data(today_date)
    trs = ""
    for r in rows:
        chip_cls = {"normal": "status-normal", "above": "status-above", "spike": "status-spike"}[r["status_cls"]]
        trend_cls = {"up": "trend-up", "dn": "trend-dn", "fl": "trend-fl"}[r["trend_cls"]]
        trs += f"""<tr>
          <td><b>{r['label']}</b></td>
          <td class="num tnum">{r['today']:.0f}</td>
          <td>{_bar_svg(r)}</td>
          <td class="num tnum">{r['med']:.0f}</td>
          <td class="num tnum">{r['avg_july']:.1f}</td>
          <td class="num tnum">{r['avg_aug']:.1f}</td>
          <td class="num tnum {trend_cls}">{r['trend_label']}</td>
          <td><span class="status-chip {chip_cls}">{r['status_label'].upper()}</span></td>
        </tr>"""

    today_str = _to_date(today_date).strftime("%d/%m/%Y")
    return f"""
  <div class="flow-section">
    <div class="section-heading avoid-orphan"><span class="bar"></span><h2>Daily Crime: Today vs Usual 30-Day Range</h2></div>
    <div class="section-sub">Reporting Period {today_str} (00:00 to 23:59)</div>
    <div class="legend-row">
      <span><span class="chip" style="background:#E4F3F0"></span><span class="chip" style="background:#FBEEE0"></span><span class="chip" style="background:#FBE7EC"></span>Where today sits vs the usual 30-day range</span>
      <span><span class="chip" style="background:#E4F3F0"></span>Normal</span>
      <span><span class="chip" style="background:#FBEEE0"></span>Higher than usual</span>
      <span><span class="chip" style="background:#FBE7EC"></span>Well above usual</span>
    </div>
    <div class="table-wrap keep">
      <table class="cmp-table">
        <thead class="navy"><tr><th>Crime Category</th><th class="num">Today</th><th>Today vs Usual Range (Last 30 Days)</th><th class="num">Typical</th><th class="num">Avg July</th><th class="num">Avg Aug</th><th class="num">7-Day</th><th>Status</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
      <div class="tbl-note">Typical is the median of the {days_of_data} days before today. Avg July and Avg Aug are the average cases per day for each of those months.</div>
    </div>
  </div>
"""


# ═══════════════════════════════════════════════════════════════════════
# Alternate section 1: month-over-month totals and trend (all categories).
# Used by the "Crime Analytics Punjab (Monthly Trend)" report instead of
# the single-day comparative section above. Fully dynamic: however many
# calendar months fall inside the selected range, that many columns appear.
# ═══════════════════════════════════════════════════════════════════════
def _monthly_trend_data(start_date, end_date):
    cols = [c for c, _ in ALL_CATEGORIES]
    sql = f"""
        SELECT EXTRACT(YEAR FROM c.report_date)::int AS yr, EXTRACT(MONTH FROM c.report_date)::int AS mo,
          COUNT(DISTINCT c.report_date) AS days, {_daily_sums_sql(cols)}
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY yr, mo ORDER BY yr, mo
    """
    rows = db.query(sql, (start_date, end_date))
    months = [dict(yr=r["yr"], mo=r["mo"], label=date(r["yr"], r["mo"], 1).strftime("%b %Y"),
                    days=r["days"]) for r in rows]

    per_category = {}
    for col, label in ALL_CATEGORIES:
        series = []
        for r in rows:
            total = r[col] or 0
            avg = total / r["days"] if r["days"] else 0
            series.append(dict(total=total, avg=avg))
        per_category[col] = series

    overall = []
    for i, r in enumerate(rows):
        total = sum(r[c] or 0 for c in cols)
        overall.append(dict(total=total, avg=total / r["days"] if r["days"] else 0))

    return months, per_category, overall


def _month_trend_badge(cur_avg, prev_avg):
    if not prev_avg:
        return "fl", "&#9668;&#9658; n/a"
    pct = (cur_avg - prev_avg) / prev_avg * 100
    if abs(pct) < 3:
        return "fl", "&#9668;&#9658; 0%"
    if pct > 0:
        return "up", f"&#9650;{pct:.0f}%"
    return "dn", f"&#9660;{abs(pct):.0f}%"


def _monthly_section(start_date, end_date):
    months, per_category, overall = _monthly_trend_data(start_date, end_date)
    if len(months) < 2:
        note = ('<div class="callout">Only one month of data is available in this range, so a month-over-month '
                'trend cannot be computed yet. Widen the date range to compare months.</div>')
        return f"""
  <div class="flow-section">
    <div class="section-heading avoid-orphan"><span class="bar"></span><h2>Monthly Totals And Trend</h2></div>
    {note}
  </div>
"""

    # Rank categories by month-over-month % change (last two months, by avg/day).
    # A tiny category (say 2 cases -> 4 cases) can post a huge percentage that
    # isn't a meaningful trend, so the "fastest rising/falling" headline only
    # draws from categories with enough combined volume to mean something;
    # the full table below still shows every category's real number either way.
    MIN_MEANINGFUL_TOTAL = 20
    changes = []
    for col, label in ALL_CATEGORIES:
        series = per_category[col]
        prev_avg, cur_avg = series[-2]["avg"], series[-1]["avg"]
        pct = ((cur_avg - prev_avg) / prev_avg * 100) if prev_avg else (100.0 if cur_avg else 0.0)
        combined_total = series[-1]["total"] + series[-2]["total"]
        changes.append((label, pct, series[-1]["total"], series[-2]["total"], combined_total))
    meaningful = [c for c in changes if c[4] >= MIN_MEANINGFUL_TOTAL]
    rising = sorted([c for c in meaningful if c[1] >= 3], key=lambda c: -c[1])
    falling = sorted([c for c in meaningful if c[1] <= -3], key=lambda c: c[1])

    overall_prev, overall_cur = overall[-2]["avg"], overall[-1]["avg"]
    overall_pct = ((overall_cur - overall_prev) / overall_prev * 100) if overall_prev else 0

    # Stat cards
    top_rise = rising[0] if rising else None
    top_fall = falling[0] if falling else None
    cards = f"""
  <div class="stat-grid" style="margin-bottom:5mm">
    <div class="stat-card c-navy">
      <div class="n tnum">{len(months)}</div>
      <div class="l">Months In This Report</div>
      <div class="d">{months[0]["label"]} through {months[-1]["label"]}.</div>
    </div>
    <div class="stat-card c-crimson">
      <div class="n tnum" style="font-size:16px">{top_rise[0] if top_rise else "None"}</div>
      <div class="l">Fastest Rising</div>
      <div class="d">{f"Up {top_rise[1]:.0f}% from {months[-2]['label']} to {months[-1]['label']}." if top_rise else "No category rose 3% or more."}</div>
    </div>
    <div class="stat-card c-teal">
      <div class="n tnum" style="font-size:16px">{top_fall[0] if top_fall else "None"}</div>
      <div class="l">Fastest Falling</div>
      <div class="d">{f"Down {abs(top_fall[1]):.0f}% from {months[-2]['label']} to {months[-1]['label']}." if top_fall else "No category fell 3% or more."}</div>
    </div>
    <div class="stat-card c-amber">
      <div class="n tnum">{overall_pct:+.0f}%</div>
      <div class="l">Overall Province Change</div>
      <div class="d">All categories combined, {months[-2]["label"]} to {months[-1]["label"]}, average cases per day.</div>
    </div>
  </div>
"""

    # Overall-crime-by-month line chart (reuses the same visual language as
    # the weekly trend chart elsewhere in this report)
    avgs = [m["avg"] for m in overall]
    CW, CH = 660, 160
    PAD_L, PAD_R, PAD_T, PAD_B = 42, 20, 16, 26
    plot_w, plot_h = CW - PAD_L - PAD_R, CH - PAD_T - PAD_B
    lo_v, hi_v = min(avgs) * 0.85, max(avgs) * 1.1
    def xy(i, v):
        x = PAD_L + (plot_w * i / max(len(avgs) - 1, 1))
        y = PAD_T + plot_h * (1 - (v - lo_v) / (hi_v - lo_v if hi_v != lo_v else 1))
        return x, y
    pts = [xy(i, v) for i, v in enumerate(avgs)]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = path_d + f" L {pts[-1][0]:.1f},{PAD_T+plot_h} L {pts[0][0]:.1f},{PAD_T+plot_h} Z"
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="#211d50"/>' for x, y in pts)
    labels = "".join(
        f'<text x="{pts[i][0]:.1f}" y="{CH-6}" font-size="8.5" fill="#6c7080" text-anchor="middle">{m["label"]}</text>'
        f'<text x="{pts[i][0]:.1f}" y="{pts[i][1]-8:.1f}" font-size="8.6" fill="#211d50" font-weight="700" text-anchor="middle">{round(avgs[i],1)}</text>'
        for i, m in enumerate(months)
    )
    chart_svg = f'<svg viewBox="0 0 {CW} {CH}" width="100%" height="{CH}"><path d="{area_d}" fill="#211d50" opacity="0.06"/><path d="{path_d}" fill="none" stroke="#211d50" stroke-width="2.3"/>{dots}{labels}</svg>'

    # Main table
    month_headers = "".join(f'<th class="num">{m["label"]}</th>' for m in months)
    trs = ""
    for col, label in ALL_CATEGORIES:
        series = per_category[col]
        cells = "".join(f'<td class="num tnum">{s["total"]}</td>' for s in series)
        prev_avg, cur_avg = series[-2]["avg"], series[-1]["avg"]
        trend_cls, trend_label = _month_trend_badge(cur_avg, prev_avg)
        badge_css = {"up": "trend-up", "dn": "trend-dn", "fl": "trend-fl"}[trend_cls]
        status = {"up": ("status-above", "RISING"), "dn": ("status-normal", "FALLING"), "fl": ("status-normal", "STABLE")}[trend_cls]
        trs += (
            f'<tr><td><b>{label}</b></td>{cells}'
            f'<td class="num tnum {badge_css}">{trend_label}</td>'
            f'<td><span class="status-chip {status[0]}">{status[1]}</span></td></tr>'
        )

    partial_note = ""
    if months[-1]["days"] < 25:
        partial_note = f' {months[-1]["label"]} has only {months[-1]["days"]} days on file so far; the change column compares average cases per day, not raw totals, so this is still a fair comparison.'

    return f"""
  <div class="flow-section">
    <div class="section-heading avoid-orphan"><span class="bar"></span><h2>Monthly Totals And Trend</h2></div>
    <div class="section-sub">Total cases per calendar month, every recorded category, whole data period.{partial_note}</div>
    {cards}
    <div class="keep">{chart_svg}</div>
    <div class="table-wrap keep" style="margin-top:4mm">
      <table class="cmp-table">
        <thead class="navy"><tr><th>Crime Category</th>{month_headers}<th class="num">Change</th><th>Trend</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
      <div class="tbl-note">Change compares average cases per day between the last two months on file, not raw totals, so a partial month is judged fairly against a complete one.</div>
    </div>
  </div>
"""


# ═══════════════════════════════════════════════════════════════════════
# Section 2: weekly up/down trend (all categories)
# ═══════════════════════════════════════════════════════════════════════
def _weekly_trend(start_date, end_date):
    sql = f"""
        SELECT FLOOR((c.report_date - %(d0)s::date) / 7) + 1 AS week_num,
          MIN(c.report_date) week_start, MAX(c.report_date) week_end,
          COUNT(DISTINCT c.report_date) n_days,
          COALESCE(SUM({all_crime_sum_sql('c')}),0) AS week_total
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %(d0)s AND %(d1)s
        GROUP BY week_num ORDER BY week_num
    """
    return db.query(sql, dict(d0=start_date, d1=end_date))


def _typical_vs_latest(weekly):
    """(typical_avg, latest_avg, pct, direction) for the province-wide daily
    average -- the latest COMPLETE week vs. the average of every complete
    week on file (the trailing partial week is excluded from both sides, same
    rule used everywhere else in this report). Replaces the older first-
    week-vs-last-week comparison: that was a two-point comparison, so the
    whole headline rode on how typical those two specific weeks happened to
    be, and it didn't match the more robust "vs Typical" method already used
    for every individual crime category."""
    complete = [w for w in weekly if w["n_days"] >= 7]
    if not complete:
        return 0.0, 0.0, 0.0, "holding steady"
    avgs = [round(w["week_total"] / w["n_days"], 1) for w in complete]
    typical_avg = round(sum(avgs) / len(avgs), 1)
    latest_avg = avgs[-1]
    pct = ((latest_avg - typical_avg) / typical_avg * 100) if typical_avg else 0.0
    direction = "climbing" if pct > 3 else ("falling" if pct < -3 else "holding steady")
    return typical_avg, latest_avg, pct, direction


def _change_badge(cur, prev):
    if prev == 0:
        return ""
    d = cur - prev
    pctv = d / prev * 100
    if abs(pctv) < 1.5:
        return '<span class="trend-fl">about the same</span>'
    if d > 0:
        return f'<span class="trend-up">&#9650; {pctv:.0f}%</span>'
    return f'<span class="trend-dn">&#9660; {abs(pctv):.0f}%</span>'


def _weekly_section(start_date, end_date):
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
        f'<text x="{pts[i][0]:.1f}" y="{CH-6}" font-size="8" fill="#6c7080" text-anchor="middle">Wk {int(w["week_num"])}{"*" if w["n_days"]<7 else ""}</text>'
        f'<text x="{pts[i][0]:.1f}" y="{pts[i][1]-7:.1f}" font-size="8" fill="#211d50" font-weight="700" text-anchor="middle">{avgs[i]}</text>'
        for i, w in enumerate(weekly)
    )
    chart_svg = f'<svg viewBox="0 0 {CW} {CH}" width="100%" height="{CH}"><path d="{area_d}" fill="#211d50" opacity="0.06"/><path d="{path_d}" fill="none" stroke="#211d50" stroke-width="2.2"/>{dots}{labels}</svg>'

    week_rows = ""
    for i, w in enumerate(weekly):
        badge = _change_badge(avgs[i], avgs[i-1]) if i > 0 else '<span class="trend-fl">start</span>'
        partial = " *" if w["n_days"] < 7 else ""
        week_rows += (
            f'<tr><td><b>Week {int(w["week_num"])}</b>{partial}</td><td>{w["week_start"]} to {w["week_end"]}</td>'
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


# ═══════════════════════════════════════════════════════════════════════
# Section 3: detail of each crime
# ═══════════════════════════════════════════════════════════════════════
def _minmax5(col, start_date, end_date):
    maxrows = db.query(f"""
        SELECT d.name_en, SUM(c.{col}) v FROM crime_daily c JOIN districts d ON d.id=c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en ORDER BY v DESC, d.name_en ASC LIMIT 5
    """, (start_date, end_date))
    minrows = db.query(f"""
        SELECT d.name_en, SUM(c.{col}) v FROM crime_daily c JOIN districts d ON d.id=c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en ORDER BY v ASC, d.name_en ASC LIMIT 5
    """, (start_date, end_date))
    return maxrows, minrows


def _chronic5(col, start_date, end_date):
    """Districts reporting cases on the most distinct days: an ongoing,
    everyday problem rather than one big total driven by a single spike."""
    return db.query(f"""
        SELECT d.name_en,
          COUNT(*) FILTER (WHERE c.{col} > 0) AS days_with_cases,
          COALESCE(SUM(c.{col}), 0) AS total
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en
        HAVING COUNT(*) FILTER (WHERE c.{col} > 0) > 0
        ORDER BY days_with_cases DESC, total DESC, d.name_en ASC
        LIMIT 5
    """, (start_date, end_date))


def _minmax_block(label, maxrows, minrows, chronicrows):
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
    return f"""
  <div class="cat-block keep">
    <h3>{label}</h3>
    <div class="three-col">
      <div class="table-wrap"><table><thead class="crimson"><tr><th>#</th><th>Most Cases</th><th class="num">Cases</th></tr></thead><tbody>{max_html}</tbody></table></div>
      <div class="table-wrap"><table><thead class="violet"><tr><th>#</th><th>Chronic (Most Days)</th><th class="num">Days</th></tr></thead><tbody>{chronic_html}</tbody></table></div>
      <div class="table-wrap"><table><thead class="teal"><tr><th>#</th><th>Fewest Cases</th><th class="num">Cases</th></tr></thead><tbody>{min_html}</tbody></table></div>
    </div>
  </div>
"""


def _detail_section(start_date, end_date):
    blocks = ""
    for col, label in ALL_CATEGORIES:
        maxrows, minrows = _minmax5(col, start_date, end_date)
        chronicrows = _chronic5(col, start_date, end_date)
        blocks += _minmax_block(label, maxrows, minrows, chronicrows)

    return f"""
  <div class="flow-section">
    <div class="section-heading"><span class="bar"></span><h2>Detail Of Each Crime</h2></div>
    <div class="section-sub">Highest, lowest, and most chronic (cases on the most days) 5 districts for every recorded category, whole period.</div>
    {blocks}
  </div>
"""


# ═══════════════════════════════════════════════════════════════════════
# Section 4: composition and contribution to Punjab
# ═══════════════════════════════════════════════════════════════════════
def _composition_section(start_date, end_date):
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
  <div class="flow-section">
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


# ═══════════════════════════════════════════════════════════════════════
# Section 0 (first page): executive summary. Text-only, colour-coded key
# insight cards. The full list this function would generate automatically
# can be fetched up front (see default_insights() below) and edited in the
# report-generation form -- add, edit, remove, recolour -- before the report
# is actually produced; whatever list is submitted as custom_insights then
# renders here instead of being computed fresh, so what the user sees in the
# form is exactly what prints. Only skips the automatic computation when
# override_defaults is set; otherwise custom_insights are added on top, for
# any caller (e.g. a script) that doesn't go through that editing flow.
# ═══════════════════════════════════════════════════════════════════════
CALLOUT_COLORS = ("crimson", "violet", "teal", "amber", "navy")


def _strip_tags(html_text):
    return _TAG_RE.sub("", html_text)


# Word/phrase-level colour-coding for insight text: red for the bad-news
# phrase in a sentence, teal for the good-news one, using the same
# trend-up/trend-dn classes (and crimson/teal colours) as every up/down
# arrow elsewhere in this report. Applied at render time, after custom
# insights are already plain-escaped text, so this survives the edit-window
# round trip (which strips all HTML for editing) and also lights up if a
# user's own added note happens to use one of these phrases.
_HIGHLIGHT_PATTERNS = [
    (re.compile(r"\bmost affected\b", re.I), "trend-up"),
    (re.compile(r"\bworst affected\b", re.I), "trend-up"),
    (re.compile(r"\bhighest count\b", re.I), "trend-up"),
    (re.compile(r"\bmost concentrated\b", re.I), "trend-up"),
    (re.compile(r"\bneed(?:s)? attention\b", re.I), "trend-up"),
    (re.compile(r"\bchronic\b", re.I), "trend-up"),
    (re.compile(r"\bpersistent\b", re.I), "trend-up"),
    (re.compile(r"\bleading\b", re.I), "trend-up"),
    (re.compile(r"\bhighest\b", re.I), "trend-up"),
    (re.compile(r"\bnotable increase(?:s)?\b", re.I), "trend-up"),
    (re.compile(r"\bup \d+(?:\.\d+)?%", re.I), "trend-up"),
    (re.compile(r"\+\d+(?:\.\d+)?%"), "trend-up"),
    (re.compile(r"\d+(?:\.\d+)?% increase\b", re.I), "trend-up"),
    (re.compile(r"\d+(?:\.\d+)?% above\b", re.I), "trend-up"),
    (re.compile(r"\bsafest\b", re.I), "trend-dn"),
    (re.compile(r"\bfewest cases\b", re.I), "trend-dn"),
    (re.compile(r"\bfavourable\b", re.I), "trend-dn"),
    (re.compile(r"\bdown \d+(?:\.\d+)?%", re.I), "trend-dn"),
    (re.compile(r"-\d+(?:\.\d+)?%"), "trend-dn"),
    (re.compile(r"\d+(?:\.\d+)?% decrease\b", re.I), "trend-dn"),
    (re.compile(r"\d+(?:\.\d+)?% below\b", re.I), "trend-dn"),
]


def _highlight_keywords(text):
    for pattern, css_class in _HIGHLIGHT_PATTERNS:
        text = pattern.sub(lambda m: f'<span class="{css_class}">{m.group(0)}</span>', text)
    return text


def _district_crime_share(start_date, end_date):
    """Each district's share of every case reported anywhere in Punjab this
    period -- the same figure as the Composition section's last column."""
    sum_expr = all_crime_sum_sql("c")
    rows = db.query(f"""
        SELECT d.name_en, SUM({sum_expr}) v FROM crime_daily c JOIN districts d ON d.id=c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en
    """, (start_date, end_date))
    grand_total = sum(r["v"] for r in rows) or 1
    return {r["name_en"]: r["v"] / grand_total * 100 for r in rows}


def _build_default_insights(start_date, end_date, weekly_context=None):
    """Returns [(color, subheading, html_text), ...] in a fixed editorial
    order -- the automatic Key Insights, unrendered, so both the PDF section
    and the JSON preview for the generation form can be built from the exact
    same list. weekly_context, when supplied, is a dict of pre-computed
    rising/falling category and district facts that only crime_analytics_
    monthly.py can produce (it needs the calendar-locked week/typical
    machinery that lives there); the primary report has no equivalent
    "typical week" concept, so the three points that depend on it are simply
    absent when weekly_context is None."""
    points = []

    # 1. Overall Crime Trend -- latest complete week vs the typical week
    # (average of every complete week on file), not first-week-vs-last-week:
    # a two-point comparison rides entirely on how typical those two specific
    # weeks happened to be, and this way matches the same "vs Typical" method
    # already used for every individual crime category below.
    weekly = _weekly_trend(start_date, end_date)
    if weekly:
        typical_avg, latest_avg, overall_pct, _ = _typical_vs_latest(weekly)
        word = "above" if overall_pct >= 0 else "below"
        points.append(("navy", "Overall Crime Trend", (
            f'Provincial daily average is running at {latest_avg:.1f} cases per day for the most recent complete '
            f'week, {abs(overall_pct):.0f}% {word} the typical week ({typical_avg:.1f} cases per day).'
        )))

    if weekly_context:
        rising, falling = weekly_context.get("rising") or [], weekly_context.get("falling") or []
        if rising:
            parts = [f'<b>{label}</b> ({pct:+.0f}%)' for label, pct in rising]
            joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
            points.append(("navy", "Crimes Showing Increase", (
                f'{joined} remained above {"its" if len(parts) == 1 else "their"} respective baseline '
                f'level{"" if len(parts) == 1 else "s"}.'
            )))
        if falling:
            parts = [f'<b>{label}</b> ({pct:+.0f}%)' for label, pct in falling]
            joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
            points.append(("navy", "Crimes Showing Decline", (
                f'{joined} remained below baseline level{"" if len(parts) == 1 else "s"}, reflecting a '
                f'comparatively favourable trend.'
            )))

    # 4. High-Incidence Districts -- top 2 by share of total reported crime.
    district_pct = _district_crime_share(start_date, end_date)
    ranked = sorted(district_pct.items(), key=lambda kv: -kv[1])
    if len(ranked) >= 2:
        (d1, p1), (d2, p2) = ranked[0], ranked[1]
        points.append(("navy", "High-Incidence Districts", (
            f'<b>{d1}</b> and <b>{d2}</b> remained the leading districts in overall reported crime, '
            f'contributing {p1:.1f}% and {p2:.1f}%, respectively, of the provincial total.'
        )))

    # 5. Persistent Crime Pattern -- districts chronic (most days-with-cases)
    # across 3+ of the 6 headline categories.
    chronic_counter = {}
    for col, _ in HEADLINE_CATEGORIES:
        for r in _chronic5(col, start_date, end_date):
            chronic_counter[r["name_en"]] = chronic_counter.get(r["name_en"], 0) + 1
    chronic_districts = sorted([d for d, n in chronic_counter.items() if n >= 3], key=lambda d: -chronic_counter[d])[:3]
    if chronic_districts:
        names = [f'<b>{d}</b>' for d in chronic_districts]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        points.append(("navy", "Persistent Crime Pattern", (
            f'{joined} demonstrated persistent reporting across multiple major crime categories, requiring '
            f'continued supervisory oversight.'
        )))

    # 6. Snatching Concentration -- top 3 districts by raw case count.
    snatch_max, _ = _minmax5("snatching_jhappata", start_date, end_date)
    if snatch_max:
        parts = [f'<b>{r["name_en"]}</b> ({r["v"]})' for r in snatch_max[:3]]
        joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        points.append(("navy", "Snatching Concentration", (
            f'{joined} recorded the highest Snatching/Jhappatta cases, indicating the need for focused '
            f'preventive policing.'
        )))

    # 7. Sensitive Crime Concerns -- top 3 districts for Child Abuse and Rape.
    ca_max, _ = _minmax5("child_abuse", start_date, end_date)
    rape_max, _ = _minmax5("rape", start_date, end_date)
    if ca_max and rape_max:
        ca_names = [f'<b>{r["name_en"]}</b>' for r in ca_max[:3]]
        rape_names = [f'<b>{r["name_en"]}</b>' for r in rape_max[:3]]
        ca_joined = ca_names[0] if len(ca_names) == 1 else ", ".join(ca_names[:-1]) + " and " + ca_names[-1]
        rape_joined = rape_names[0] if len(rape_names) == 1 else ", ".join(rape_names[:-1]) + " and " + rape_names[-1]
        points.append(("navy", "Sensitive Crime Concerns", (
            f'{ca_joined} recorded the highest Child Abuse cases, while {rape_joined} recorded the highest '
            f'Rape incidence.'
        )))

    # 8. Emerging District Trends -- districts driving the latest rise in
    # Murder and Robbery specifically (weekly_context only).
    if weekly_context:
        murder_rising = weekly_context.get("murder_rising") or []
        robbery_rising = weekly_context.get("robbery_rising") or []
        if murder_rising or robbery_rising:
            bits = []
            if murder_rising:
                m_names = [f'<b>{d}</b>' for d, *_ in murder_rising[:3]]
                bits.append((m_names[0] if len(m_names) == 1 else ", ".join(m_names[:-1]) + " and " + m_names[-1]) + " for Murder")
            if robbery_rising:
                r_names = [f'<b>{d}</b>' for d, *_ in robbery_rising[:3]]
                bits.append((r_names[0] if len(r_names) == 1 else ", ".join(r_names[:-1]) + " and " + r_names[-1]) + " for Robbery")
            joined_bits = bits[0] if len(bits) == 1 else f'{bits[0]}, and {bits[1]}'
            points.append(("navy", "Emerging District Trends", (
                f'Notable increases were observed in {joined_bits}, requiring district-level review.'
            )))

    # 9. Provincial Crime Concentration -- top 5 by share of total reported crime.
    if len(ranked) >= 5:
        names = [f'<b>{d}</b>' for d, _ in ranked[:5]]
        joined = ", ".join(names[:-1]) + " and " + names[-1]
        points.append(("navy", "Provincial Crime Concentration", (
            f'{joined} recorded the highest volumes of reported crime.'
        )))

    return points


def default_insights(start_date=None, end_date=None, **_):
    """Public entry point for the report-generation form: the automatic
    findings as plain-text (HTML tags stripped) dicts, ready to prefill an
    editable list. Used by /api/reports/default_insights."""
    earliest, latest = _date_bounds()
    start_date = _to_date(start_date) if start_date else earliest
    end_date = _to_date(end_date) if end_date else latest
    items = _build_default_insights(start_date, end_date)
    return [dict(color=color, tag=tag, text=_strip_tags(text)) for color, tag, text in items]


def _executive_summary_section(start_date, end_date, weekly_context=None, custom_insights=None, override_defaults=False):
    insights = [] if override_defaults else _build_default_insights(start_date, end_date, weekly_context)

    # custom_insights carries whatever the user submitted from the
    # generation form: the (possibly edited) defaults plus anything they
    # added, each with its own colour and, where it came from a default,
    # its original subheading. Unrecognised colours fall back to navy (the
    # same neutral used for every automatic point); a missing subheading
    # falls back to a generic label.
    if custom_insights:
        for ci in custom_insights:
            text = (ci.get("text") or "").strip()
            if not text:
                continue
            color = ci.get("color") if ci.get("color") in CALLOUT_COLORS else "navy"
            tag = (ci.get("tag") or "Additional Note").strip()[:60]
            points_tag = esc(tag)
            insights.append((color, points_tag, esc(text)))

    rows_html = "".join(
        f'<div class="insight-card {color if color != "navy" else ""} keep">'
        f'<div class="insight-card-head"><span class="insight-num">{i + 1}</span><span class="subhead">{tag}</span></div>'
        f'<p>{_highlight_keywords(text)}</p>'
        f'</div>'
        for i, (color, tag, text) in enumerate(insights)
    )

    return f"""
  <div class="flow-section keep">
    <div class="section-heading"><span class="diamond">&#9670;</span><h2>Key Insights</h2></div>
    <div class="section-sub">At a glance: the state of crime across Punjab for this reporting period.</div>
    <div class="insights-box">{rows_html}</div>
  </div>
"""


# ═══════════════════════════════════════════════════════════════════════
# Puppeteer repeating header/footer templates
# ═══════════════════════════════════════════════════════════════════════
def _pdf_header_footer(reporting_day, data_period, header_note, baseline="Comparative Analysis"):
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
      <div style="font-size:11px;color:#6c7080;margin-top:4px;">Reporting Day: <b style="color:#1c1d29">{esc(reporting_day)}</b> &nbsp;|&nbsp; Data Period: <b style="color:#1c1d29">{esc(data_period)}</b></div>
      <div style="margin-top:4px;font-size:10px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#2f2a6b;">{esc(baseline)}</div>
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
  <span>Data sources: Special Branch Punjab &middot; Provincial Control Room (Home Department) &middot; Emergency Services Department (Rescue 1122) &middot; Punjab Police &middot; Traffic Police</span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>
"""
    return header_tpl, footer_tpl


def _preview_chrome(reporting_day, data_period, header_note, baseline="Comparative Analysis"):
    """Visible only when the raw HTML is opened in a browser (Preview & Edit).
    Hidden in the actual PDF, which gets the real repeating header/footer
    from Puppeteer instead, so nothing is duplicated."""
    note_html = f'<div class="note">{esc(header_note)}</div>' if header_note else ""
    mast = f"""
<div class="preview-mast">
  <img class="logo" src="{CSU_LOGO}"/>
  <div class="center">
    <div class="title">Crime Analytics Punjab</div>
    <div class="meta">Reporting Day: <b>{esc(reporting_day)}</b> | Data Period: <b>{esc(data_period)}</b></div>
    <div class="baseline">{esc(baseline)}</div>
    {note_html}
  </div>
  <div class="right">
    <img class="logo" src="{GOVT_LOGO}"/>
    <div class="office">Chief Minister's Office<span>Additional Secretary<br/>(Law &amp; Order)</span></div>
  </div>
</div>
"""
    foot = """
<div class="preview-foot">Data sources: Special Branch Punjab &middot; Provincial Control Room (Home Department) &middot; Emergency Services Department (Rescue 1122) &middot; Punjab Police &middot; Traffic Police</div>
"""
    return mast, foot


# ═══════════════════════════════════════════════════════════════════════
# Assemble
# ═══════════════════════════════════════════════════════════════════════
def generate(start_date=None, end_date=None, reporting_day=None, header_note=None, output="pdf",
             custom_insights=None, override_defaults=False, **_):
    earliest, latest = _date_bounds()
    start_date = _to_date(start_date) if start_date else earliest
    end_date = _to_date(end_date) if end_date else latest
    reporting_day = reporting_day or date.today().strftime("%d/%m/%Y")
    n_days = (end_date - start_date).days + 1
    data_period = f"{start_date} to {end_date} ({n_days} day{'s' if n_days != 1 else ''})"

    sections = (
        _executive_summary_section(start_date, end_date, custom_insights=custom_insights, override_defaults=override_defaults)
        + _weekly_section(start_date, end_date)
        + _comparative_section(latest)
        + _detail_section(start_date, end_date)
        + _composition_section(start_date, end_date)
    )

    header_tpl, footer_tpl = _pdf_header_footer(reporting_day, data_period, header_note)
    preview_mast, preview_foot = _preview_chrome(reporting_day, data_period, header_note)
    pdf_config = json.dumps(dict(
        headerTemplate=header_tpl, footerTemplate=footer_tpl,
        margin=PAGE_MARGIN,
    ))

    toolbar = EDIT_TOOLBAR if output == "html" else ""
    html = f"""<!doctype html>
<html><head><meta charset="utf-8" /><title>Crime Analytics Punjab</title><style>{BASE_CSS}{EXTRA_CSS}</style></head>
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
