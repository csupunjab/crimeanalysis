# -*- coding: utf-8 -*-
"""Safest districts per headline category, lowest total first, with a
Days-On-File caveat so a thin-reporting district isn't mistaken for safe."""
from datetime import date

import db
from reports.common import (
    HEADLINE_CATEGORIES, DISTRICT_FILTER_SQL, FOOTER,
    masthead, wrap_pages, render_pdf, save_html,
)


def _category_safe(col, start_date, end_date, total_days):
    sql = f"""
        SELECT d.name_en,
          COALESCE(SUM(c.{col}), 0) AS total,
          COUNT(*) FILTER (WHERE c.{col} > 0) AS days_with_cases,
          COUNT(DISTINCT c.report_date) AS days_on_file
        FROM districts d
        LEFT JOIN crime_daily c ON c.district_id = d.id
          AND c.report_date BETWEEN %s AND %s
        WHERE {DISTRICT_FILTER_SQL}
        GROUP BY d.name_en
        ORDER BY total ASC, days_with_cases ASC, d.name_en ASC
        LIMIT 10
    """
    return db.query(sql, (start_date, end_date))


def _province_total(col, start_date, end_date):
    sql = f"""
        SELECT COALESCE(SUM(c.{col}), 0) AS total
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
    """
    return db.query_one(sql, (start_date, end_date))["total"]


def _page(col, label, start_date, end_date, total_days, reporting_day, data_period, header_note):
    rows = _category_safe(col, start_date, end_date, total_days)
    prov_total = _province_total(col, start_date, end_date)
    avg_day = prov_total / total_days if total_days else 0

    zero_count = sum(1 for r in rows if r["total"] == 0)
    rows_html = "".join(
        f'<tr><td><span class="rank teal">{i+1}</span></td><td><b>{r["name_en"]}</b></td>'
        f'<td class="num tnum">{r["total"]}</td><td class="num tnum">{r["days_with_cases"]}</td>'
        f'<td class="num tnum">{r["days_on_file"]}/{total_days}</td></tr>'
        for i, r in enumerate(rows)
    )
    flagship = rows[0]
    flagship_note = (
        f'{flagship["days_on_file"]} of {total_days} days on file, {flagship["total"]} case(s) recorded'
    )

    return masthead(f"{label} Safest Districts", f"{label}, Districts With Minimum Reports",
                     reporting_day, data_period, header_note) + f"""
  <div class="stat-grid n3">
    <div class="stat-card c-teal">
      <div class="n tnum">{zero_count}</div>
      <div class="l">Districts With Zero Reports</div>
      <div class="d">Out of the ranked list below, this many recorded no cases at all in the selected period.</div>
    </div>
    <div class="stat-card c-crimson">
      <div class="n tnum" style="font-size:16px;line-height:1.3">{flagship["name_en"]}</div>
      <div class="l">Lowest Recorded</div>
      <div class="d">{flagship_note}.</div>
    </div>
    <div class="stat-card c-amber">
      <div class="n tnum">{prov_total}</div>
      <div class="l">Province Total, Period</div>
      <div class="d">{avg_day:.1f} cases/day average across Punjab.</div>
    </div>
  </div>

  <span class="sec-tag teal">Lowest Reported Districts</span>
  <p class="sec-note">Districts ranked from lowest to higher total cases. "Days on file" shows how complete that district's reporting history is for this period.</p>
  <div class="table-wrap" style="margin-bottom:4mm">
    <table>
      <thead class="teal"><tr><th>#</th><th>District</th><th class="num">Total</th><th class="num">Days With Cases</th><th class="num">Days On File</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <div class="callout">
    <b>Reading This Page</b>
    <p style="margin-top:5px">A district showing "0" total is not automatically confirmed safe &mdash; check its "Days on file" column first. A zero with near-complete reporting for the period is a genuinely verified low-crime finding; a zero with very few days on file simply means that district has thin reporting history, and the true picture is still unknown.</p>
  </div>
""" + FOOTER


def generate(start_date, end_date, reporting_day, header_note=None, output="pdf", **_):
    data_period = f"{start_date} to {end_date}"
    total_days = (date.fromisoformat(str(end_date)) - date.fromisoformat(str(start_date))).days + 1

    pages = [
        _page(col, label, start_date, end_date, total_days, reporting_day, data_period, header_note)
        for col, label in HEADLINE_CATEGORIES
    ]
    html = wrap_pages(*pages, title="Safest Districts By Category", editable=(output == "html"))
    return save_html(html) if output == "html" else render_pdf(html)
