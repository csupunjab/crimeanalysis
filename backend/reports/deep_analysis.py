# -*- coding: utf-8 -*-
"""Deep Analysis: performance ranking, each district's own crime-mix
composition (rows sum to 100%), and the week-by-week pattern. Real crime
only — Road Accident Casualties and Religious Issues are excluded."""
from datetime import date, timedelta

import db
from reports.common import (
    HEADLINE_CATEGORIES, DISTRICT_FILTER_SQL, REAL_CRIME_COLUMNS, FOOTER,
    masthead, wrap_pages, render_pdf, save_html, real_crime_sum_sql,
)

OTHER_COLUMNS = [c for c in REAL_CRIME_COLUMNS if c not in
                 ("murder", "robbery", "child_abuse", "rape", "gang_rape", "snatching_jhappata")]


def _district_breakdown(start_date, end_date):
    other_sql = "+".join(f"c.{c}" for c in OTHER_COLUMNS)
    sql = f"""
        SELECT d.name_en,
          COALESCE(SUM(c.murder),0) AS murder, COALESCE(SUM(c.robbery),0) AS robbery,
          COALESCE(SUM(c.child_abuse),0) AS child_abuse, COALESCE(SUM(c.rape),0) AS rape,
          COALESCE(SUM(c.gang_rape),0) AS gang_rape, COALESCE(SUM(c.snatching_jhappata),0) AS snatching,
          COALESCE(SUM({other_sql}),0) AS other,
          COALESCE(SUM({real_crime_sum_sql('c')}),0) AS total
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en
    """
    return db.query(sql, (start_date, end_date))


def _weekly_trend(start_date, end_date):
    sql = f"""
        SELECT
          FLOOR((c.report_date - %(d0)s::date) / 7) + 1 AS week_num,
          MIN(c.report_date) week_start, MAX(c.report_date) week_end,
          COUNT(DISTINCT c.report_date) n_days,
          COALESCE(SUM({real_crime_sum_sql('c')}),0) AS week_total
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %(d0)s AND %(d1)s
        GROUP BY week_num ORDER BY week_num
    """
    return db.query(sql, dict(d0=start_date, d1=end_date))


def _category_minmax(col, start_date, end_date):
    max_row = db.query_one(f"""
        SELECT d.name_en, SUM(c.{col}) v FROM crime_daily c JOIN districts d ON d.id=c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en ORDER BY v DESC, d.name_en ASC LIMIT 1
    """, (start_date, end_date))
    min_row = db.query_one(f"""
        SELECT d.name_en, SUM(c.{col}) v FROM crime_daily c JOIN districts d ON d.id=c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en ORDER BY v ASC, d.name_en ASC LIMIT 1
    """, (start_date, end_date))
    return min_row, max_row


def _change_badge(cur, prev):
    if prev == 0:
        return ""
    d = cur - prev
    pctv = d / prev * 100
    if abs(pctv) < 1.5:
        return '<span class="badge flat">about the same</span>'
    if d > 0:
        return f'<span class="badge up">up {pctv:.0f}%</span>'
    return f'<span class="badge down">down {abs(pctv):.0f}%</span>'


def generate(start_date, end_date, reporting_day, header_note=None, output="pdf", **_):
    data_period = f"{start_date} to {end_date}"
    rows = _district_breakdown(start_date, end_date)
    grand_total = sum(r["total"] for r in rows) or 1
    by_total_asc = sorted(rows, key=lambda r: r["total"])
    best5, worst5 = by_total_asc[:5], list(reversed(by_total_asc[-5:]))

    # ---- Page 1: performance ranking ----
    def rank_rows(items, color):
        return "".join(
            f'<tr><td><span class="rank {color}">{i+1}</span></td><td><b>{r["name_en"]}</b></td>'
            f'<td class="num tnum">{r["total"]}</td><td class="num tnum">{r["total"]/grand_total*100:.2f}%</td></tr>'
            for i, r in enumerate(items)
        )
    multiple = round(worst5[0]["total"] / best5[0]["total"]) if best5[0]["total"] else 0

    page1 = masthead("Deep Analysis", "Performance Ranking: Crime Districts Only",
                      reporting_day, data_period, header_note) + f"""
  <div class="stat-grid">
    <div class="stat-card c-navy">
      <div class="n tnum">{grand_total:,}</div>
      <div class="l">Total Crime Cases, Period</div>
      <div class="d">Real crime only, all crime districts. Road Accidents and Religious Issues excluded.</div>
    </div>
    <div class="stat-card c-crimson">
      <div class="n tnum">{worst5[0]["name_en"]} ({worst5[0]["total"]})</div>
      <div class="l">Most Cases, Single District</div>
      <div class="d">{worst5[0]["total"]/grand_total*100:.1f}% of the whole province this period.</div>
    </div>
    <div class="stat-card c-teal">
      <div class="n tnum">{best5[0]["name_en"]} ({best5[0]["total"]})</div>
      <div class="l">Fewest Cases, Single District</div>
      <div class="d">The lowest total of any district this period.</div>
    </div>
    <div class="stat-card c-amber">
      <div class="n tnum">{len(rows)} Districts</div>
      <div class="l">Included In This Report</div>
      <div class="d">Talagang and Tonsa excluded due to incomplete reporting.</div>
    </div>
  </div>

  <span class="sec-tag teal">Best Performing Districts, Fewest Cases Reported</span>
  <div class="table-wrap" style="margin-bottom:6mm">
    <table>
      <thead class="teal"><tr><th>#</th><th>District</th><th class="num">Total Cases</th><th class="num">Share Of Province</th></tr></thead>
      <tbody>{rank_rows(best5, "teal")}</tbody>
    </table>
  </div>

  <span class="sec-tag crimson">Districts With The Most Cases Reported</span>
  <div class="table-wrap" style="margin-bottom:6mm">
    <table>
      <thead class="crimson"><tr><th>#</th><th>District</th><th class="num">Total Cases</th><th class="num">Share Of Province</th></tr></thead>
      <tbody>{rank_rows(worst5, "crimson")}</tbody>
    </table>
  </div>

  <div class="callout">
    <b>The Simple Comparison</b>
    <p style="margin-top:5px">{worst5[0]["name_en"]} recorded {worst5[0]["total"]} cases this period, {best5[0]["name_en"]} recorded {best5[0]["total"]},
    a {multiple}x difference over the exact same dates.</p>
  </div>
""" + FOOTER

    # ---- Page 2: composition table ----
    by_total_desc = sorted(rows, key=lambda r: -r["total"])
    comp_rows = ""
    for i, r in enumerate(by_total_desc):
        t = r["total"] or 1
        comp_rows += (
            f'<tr><td>{i+1}</td><td><b>{r["name_en"]}</b></td>'
            f'<td class="num tnum">{r["murder"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["robbery"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["child_abuse"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["rape"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["gang_rape"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["snatching"]/t*100:.1f}%</td>'
            f'<td class="num tnum">{r["other"]/t*100:.1f}%</td>'
            f'<td class="num tnum"><b>{r["total"]}</b></td></tr>'
        )
    page2 = masthead("Deep Analysis", "Each District's Own Crime Mix: Adds Up To 100%",
                      reporting_day, data_period, header_note) + f"""
  <p class="sec-note" style="font-size:10.8px;margin-bottom:4mm">This table breaks each district's own total crime into categories, so every row adds up to <b>100%</b>. <b>Other</b> covers the smaller real-crime categories (Dacoity, Dacoity/Robbery variants, Sodomy, Acid Attack). Road Accident Casualties and Religious Issues are not crime and are left out entirely. Ranked by total case count, highest first.</p>
  <div class="table-wrap">
    <table class="compact">
      <thead class="navy"><tr><th>#</th><th>District</th><th class="num">Murder</th><th class="num">Robbery</th><th class="num">Child Abuse</th><th class="num">Rape</th><th class="num">Gang Rape</th><th class="num">Snatching</th><th class="num">Other</th><th class="num">Total</th></tr></thead>
      <tbody>{comp_rows}</tbody>
    </table>
  </div>
""" + FOOTER

    # ---- Page 3: weekly trend + category min/max summary ----
    weekly = _weekly_trend(start_date, end_date)
    avg_per_day = [round(w["week_total"] / w["n_days"], 1) if w["n_days"] else 0 for w in weekly]
    week_rows = ""
    for i, w in enumerate(weekly):
        avg = avg_per_day[i]
        badge = _change_badge(avg, avg_per_day[i-1]) if i > 0 else '<span class="badge flat">start</span>'
        partial = " *" if w["n_days"] < 7 else ""
        week_rows += (
            f'<tr><td><b>Week {int(w["week_num"])}</b>{partial}</td>'
            f'<td>{w["week_start"]} &ndash; {w["week_end"]}</td>'
            f'<td class="num tnum">{w["week_total"]}</td><td class="num tnum">{avg}</td><td>{badge}</td></tr>'
        )

    minmax_rows = ""
    for col, label in HEADLINE_CATEGORIES:
        minr, maxr = _category_minmax(col, start_date, end_date)
        minmax_rows += (
            f'<tr><td><b>{label}</b></td><td>{minr["name_en"]}</td><td class="num tnum">{minr["v"]}</td>'
            f'<td>{maxr["name_en"]}</td><td class="num tnum">{maxr["v"]}</td></tr>'
        )

    page3 = masthead("Deep Analysis", "Week-By-Week Pattern &amp; Safest Districts",
                      reporting_day, data_period, header_note) + f"""
  <span class="sec-tag amber">Is Crime Going Up Or Down? Week By Week</span>
  <p class="sec-note">Average real-crime cases per day, all crime districts, 7-day weeks from the start of the period. * = partial week.</p>
  <div class="table-wrap" style="margin-bottom:5mm">
    <table>
      <thead class="amber"><tr><th>Week</th><th>Dates</th><th class="num">Total</th><th class="num">Avg/Day</th><th>Change</th></tr></thead>
      <tbody>{week_rows}</tbody>
    </table>
  </div>

  <span class="sec-tag teal">Safest &amp; Most Affected District, By Crime Type</span>
  <div class="table-wrap" style="margin-bottom:4mm">
    <table>
      <thead class="teal"><tr><th>Crime Type</th><th>Safest District</th><th class="num">Cases</th><th>Most Affected District</th><th class="num">Cases</th></tr></thead>
      <tbody>{minmax_rows}</tbody>
    </table>
  </div>
""" + FOOTER

    html = wrap_pages(page1, page2, page3, title="Deep Analysis", editable=(output == "html"))
    return save_html(html) if output == "html" else render_pdf(html)
