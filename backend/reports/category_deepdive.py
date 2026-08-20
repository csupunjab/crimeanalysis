# -*- coding: utf-8 -*-
"""One page per headline crime category: weekly trend, top-3 divisions,
top-5/bottom-5 districts, and an auto-generated narrative summary. Closes
with an overall (all real crime combined) min/max page."""
from reports.common import (
    HEADLINE_CATEGORIES, DISTRICT_FILTER_SQL, REAL_CRIME_COLUMNS, FOOTER,
    masthead, wrap_pages, render_pdf, save_html, real_crime_sum_sql,
)
import db

COLORS = ["crimson", "amber", "violet", "crimson", "violet", "teal"]


def _weekly(col, start_date, end_date):
    sql = f"""
        SELECT FLOOR((c.report_date - %(d0)s::date) / 7) + 1 AS week_num,
          MIN(c.report_date) week_start, MAX(c.report_date) week_end,
          COUNT(DISTINCT c.report_date) n_days, COALESCE(SUM(c.{col}),0) AS total
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %(d0)s AND %(d1)s
        GROUP BY week_num ORDER BY week_num
    """
    return db.query(sql, dict(d0=start_date, d1=end_date))


def _divisions(col, start_date, end_date):
    sql = f"""
        SELECT dv.name_en division, COALESCE(SUM(c.{col}),0) AS v
        FROM crime_daily c JOIN districts d ON d.id=c.district_id JOIN divisions dv ON dv.id=d.division_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY dv.name_en ORDER BY v DESC LIMIT 3
    """
    return db.query(sql, (start_date, end_date))


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


def _change_badge(cur, prev):
    if prev == 0:
        return ""
    d = cur - prev
    pctv = d / prev * 100
    if abs(pctv) < 1.5:
        return '<span class="badge flat">flat</span>'
    if d > 0:
        return f'<span class="badge up">up {pctv:.0f}%</span>'
    return f'<span class="badge down">down {abs(pctv):.0f}%</span>'


def _category_page(col, label, color, idx, total_n, start_date, end_date, reporting_day, data_period, header_note):
    weekly = _weekly(col, start_date, end_date)
    divisions = _divisions(col, start_date, end_date)
    maxrows, minrows = _minmax5(col, start_date, end_date)
    total = sum(w["total"] for w in weekly) or 0
    n_days_total = sum(w["n_days"] for w in weekly) or 1
    avg_day = total / n_days_total

    avgs = [round(w["total"] / w["n_days"], 1) if w["n_days"] else 0 for w in weekly]
    week_rows = ""
    for i, w in enumerate(weekly):
        badge = _change_badge(avgs[i], avgs[i-1]) if i > 0 else '<span class="badge flat">start</span>'
        partial = " *" if w["n_days"] < 7 else ""
        week_rows += (
            f'<tr><td><b>Wk {int(w["week_num"])}</b>{partial}</td><td>{w["week_start"]} &ndash; {w["week_end"]}</td>'
            f'<td class="num tnum">{w["total"]}</td><td class="num tnum">{avgs[i]}</td><td>{badge}</td></tr>'
        )

    div_rows = "".join(
        f'<tr><td><span class="rank {color}">{i+1}</span></td><td><b>{d["division"]}</b></td>'
        f'<td class="num tnum">{d["v"]}</td><td class="num tnum">{(d["v"]/total*100 if total else 0):.1f}%</td></tr>'
        for i, d in enumerate(divisions)
    )
    max_rows = "".join(
        f'<tr><td><span class="rank crimson">{i+1}</span></td><td><b>{r["name_en"]}</b></td><td class="num tnum">{r["v"]}</td></tr>'
        for i, r in enumerate(maxrows)
    )
    min_rows = "".join(
        f'<tr><td><span class="rank teal">{i+1}</span></td><td><b>{r["name_en"]}</b></td><td class="num tnum">{r["v"]}</td></tr>'
        for i, r in enumerate(minrows)
    )

    top_div = divisions[0] if divisions else None
    top_district = maxrows[0] if maxrows else None
    story = "Not enough data in this period to summarise a pattern."
    if top_div and top_district:
        div_share = top_div["v"] / total * 100 if total else 0
        story = (
            f'{top_div["division"]} division carries the heaviest {label.lower()} load '
            f'({top_div["v"]} cases, {div_share:.1f}% of the province this period), and '
            f'{top_district["name_en"]} district has the single highest count of any district ({top_district["v"]} cases). '
        )
        if len(weekly) >= 2:
            first_avg, last_avg = avgs[0], avgs[-1]
            if last_avg > first_avg * 1.1:
                story += "The weekly pattern is trending upward over the period."
            elif last_avg < first_avg * 0.9:
                story += "The weekly pattern is trending downward over the period."
            else:
                story += "The weekly pattern has stayed roughly flat over the period."

    return masthead("Deep Analysis", f"{label}: Trend, Divisions &amp; Districts ({idx} of {total_n})",
                     reporting_day, data_period, header_note) + f"""
  <div class="stat-grid n3">
    <div class="stat-card c-{color}">
      <div class="n tnum">{total:,}</div>
      <div class="l">Total {label} Cases</div>
      <div class="d">This period, {avg_day:.1f} cases/day province-wide.</div>
    </div>
    <div class="stat-card c-{color}">
      <div class="n tnum">{top_div["division"] if top_div else "&mdash;"}</div>
      <div class="l">Top Division</div>
      <div class="d">{(top_div["v"] if top_div else 0)} cases this period.</div>
    </div>
    <div class="stat-card c-{color}">
      <div class="n tnum">{top_district["name_en"] if top_district else "&mdash;"}</div>
      <div class="l">Most Affected District</div>
      <div class="d">{(top_district["v"] if top_district else 0)} cases, the highest of any district.</div>
    </div>
  </div>

  <div class="section-block">
    <span class="sec-tag {color}">Week By Week</span>
    <p class="sec-note">* = partial week (fewer than 7 days on file).</p>
    <div class="table-wrap">
      <table>
        <thead class="{color}"><tr><th>Week</th><th>Dates</th><th class="num">Total</th><th class="num">Avg/Day</th><th>Change</th></tr></thead>
        <tbody>{week_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="section-block">
    <span class="sec-tag {color}">Top 3 Divisions</span>
    <div class="table-wrap">
      <table>
        <thead class="{color}"><tr><th>#</th><th>Division</th><th class="num">Cases</th><th class="num">Share Of Province</th></tr></thead>
        <tbody>{div_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="section-block">
    <span class="sec-tag {color}">Highest &amp; Lowest 5 Districts</span>
    <div class="two-col" style="margin-bottom:0">
      <div class="table-wrap">
        <table>
          <thead class="crimson"><tr><th>#</th><th>Most Cases</th><th class="num">Cases</th></tr></thead>
          <tbody>{max_rows}</tbody>
        </table>
      </div>
      <div class="table-wrap">
        <table>
          <thead class="teal"><tr><th>#</th><th>Fewest Cases</th><th class="num">Cases</th></tr></thead>
          <tbody>{min_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="callout {color}">
    <b>What This Means</b>
    <p style="margin-top:4px">{story}</p>
  </div>
""" + FOOTER


def _overall_page(start_date, end_date, reporting_day, data_period, header_note):
    sql = f"""
        SELECT d.name_en, COALESCE(SUM({real_crime_sum_sql('c')}),0) AS total
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en ORDER BY total ASC
    """
    rows = db.query(sql, (start_date, end_date))
    grand_total = sum(r["total"] for r in rows) or 1
    best10, worst10 = rows[:10], list(reversed(rows[-10:]))

    def rows_html(items, color):
        return "".join(
            f'<tr><td><span class="rank {color}">{i+1}</span></td><td><b>{r["name_en"]}</b></td>'
            f'<td class="num tnum">{r["total"]}</td><td class="num tnum">{r["total"]/grand_total*100:.1f}%</td></tr>'
            for i, r in enumerate(items)
        )

    return masthead("Deep Analysis", "Overall Min &amp; Max: All Crime Combined",
                     reporting_day, data_period, header_note) + f"""
  <div class="stat-grid">
    <div class="stat-card c-teal">
      <div class="n tnum">{grand_total:,}</div>
      <div class="l">Total Real Crime, Period</div>
      <div class="d">All crime districts. Excludes Road Accidents and Religious Issues.</div>
    </div>
    <div class="stat-card c-crimson">
      <div class="n tnum">{worst10[0]["name_en"]} ({worst10[0]["total"]})</div>
      <div class="l">Highest Overall Total</div>
      <div class="d">{worst10[0]["total"]/grand_total*100:.1f}% of every crime case this period.</div>
    </div>
    <div class="stat-card c-teal">
      <div class="n tnum">{best10[0]["name_en"]} ({best10[0]["total"]})</div>
      <div class="l">Lowest Overall Total</div>
      <div class="d">The safest district in the province across all crime types.</div>
    </div>
  </div>

  <div class="two-col">
    <div>
      <span class="sec-tag teal">10 Safest Districts, Overall</span>
      <div class="table-wrap">
        <table>
          <thead class="teal"><tr><th>#</th><th>District</th><th class="num">Total</th><th class="num">Share</th></tr></thead>
          <tbody>{rows_html(best10, "teal")}</tbody>
        </table>
      </div>
    </div>
    <div>
      <span class="sec-tag crimson">10 Highest Districts, Overall</span>
      <div class="table-wrap">
        <table>
          <thead class="crimson"><tr><th>#</th><th>District</th><th class="num">Total</th><th class="num">Share</th></tr></thead>
          <tbody>{rows_html(worst10, "crimson")}</tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="callout">
    <b>Reading This Report</b>
    <p style="margin-top:5px">Talagang and Tonsa are excluded from every page in this report due to incomplete reporting. All figures count real crime only.</p>
  </div>
""" + FOOTER


def generate(start_date, end_date, reporting_day, header_note=None, output="pdf", **_):
    data_period = f"{start_date} to {end_date}"
    cats = HEADLINE_CATEGORIES
    pages = [
        _category_page(col, label, COLORS[i], i + 1, len(cats), start_date, end_date, reporting_day, data_period, header_note)
        for i, (col, label) in enumerate(cats)
    ]
    pages.append(_overall_page(start_date, end_date, reporting_day, data_period, header_note))
    html = wrap_pages(*pages, title="Category Deep Dive Analysis", editable=(output == "html"))
    return save_html(html) if output == "html" else render_pdf(html)
