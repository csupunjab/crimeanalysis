# -*- coding: utf-8 -*-
"""Top-5 highest / lowest districts, per headline crime category."""
import db
from reports.common import (
    HEADLINE_CATEGORIES, DISTRICT_FILTER_SQL, CSS, FOOTER,
    masthead, wrap_pages, render_pdf, save_html,
)


def _category_minmax(col, start_date, end_date):
    max_sql = f"""
        SELECT d.name_en, SUM(c.{col}) AS v
        FROM crime_daily c JOIN districts d ON d.id=c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en ORDER BY v DESC, d.name_en ASC LIMIT 5
    """
    min_sql = f"""
        SELECT d.name_en, SUM(c.{col}) AS v
        FROM crime_daily c JOIN districts d ON d.id=c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en ORDER BY v ASC, d.name_en ASC LIMIT 5
    """
    maxrows = db.query(max_sql, (start_date, end_date))
    minrows = db.query(min_sql, (start_date, end_date))
    return maxrows, minrows


def _block(label, maxrows, minrows, color="crimson"):
    max_html = "".join(
        f'<tr><td><span class="rank crimson">{i+1}</span></td><td><b>{r["name_en"]}</b></td><td class="num tnum">{r["v"]}</td></tr>'
        for i, r in enumerate(maxrows)
    )
    min_html = "".join(
        f'<tr><td><span class="rank teal">{i+1}</span></td><td><b>{r["name_en"]}</b></td><td class="num tnum">{r["v"]}</td></tr>'
        for i, r in enumerate(minrows)
    )
    return f"""
  <span class="sec-tag {color}" style="margin-bottom:2mm">{label} &mdash; Highest &amp; Lowest 5 Districts</span>
  <div class="two-col" style="margin-bottom:5mm">
    <div class="table-wrap">
      <table>
        <thead class="crimson"><tr><th>#</th><th>Most Cases</th><th class="num">Cases</th></tr></thead>
        <tbody>{max_html}</tbody>
      </table>
    </div>
    <div class="table-wrap">
      <table>
        <thead class="teal"><tr><th>#</th><th>Fewest Cases</th><th class="num">Cases</th></tr></thead>
        <tbody>{min_html}</tbody>
      </table>
    </div>
  </div>
"""


def generate(start_date, end_date, reporting_day, header_note=None, output="pdf", **_):
    data_period = f"{start_date} to {end_date}"
    cats = HEADLINE_CATEGORIES
    blocks = []
    for col, label in cats:
        maxrows, minrows = _category_minmax(col, start_date, end_date)
        blocks.append(_block(label, maxrows, minrows))

    page1 = masthead("Max &amp; Min Districts By Category", "Top 5 Highest &amp; Lowest, Every Crime Type (1 of 2)",
                      reporting_day, data_period, header_note)
    for b in blocks[:3]:
        page1 += b
    page1 += FOOTER

    page2 = masthead("Max &amp; Min Districts By Category", "Top 5 Highest &amp; Lowest, Every Crime Type (2 of 2)",
                      reporting_day, data_period, header_note)
    for b in blocks[3:]:
        page2 += b
    page2 += """
  <div class="callout">
    <b>Reading This Report</b>
    <p style="margin-top:5px">Talagang and Tonsa are excluded from every table in this report due to incomplete reporting. All figures cover the selected date range across the same 39 crime districts.</p>
  </div>
""" + FOOTER

    html = wrap_pages(page1, page2, title="Max & Min Districts By Category", editable=(output == "html"))
    return save_html(html) if output == "html" else render_pdf(html)
