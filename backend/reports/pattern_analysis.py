# -*- coding: utf-8 -*-
"""Chronic / Biggest Jumps / Rising Fast pattern analysis, per headline
crime category. Fully dynamic — narrative sentences are generated from
the computed numbers, nothing is hand-written per run."""
from datetime import date, timedelta

import db
from reports.common import (
    HEADLINE_CATEGORIES, DISTRICT_FILTER_SQL, FOOTER,
    masthead, wrap_pages, render_pdf, save_html,
)


def _chronic(col, start_date, end_date):
    sql = f"""
        SELECT d.name_en,
          COUNT(*) FILTER (WHERE c.{col} > 0) AS days_with_cases,
          COALESCE(SUM(c.{col}), 0) AS total,
          COALESCE(AVG(c.{col}), 0) AS avg_day
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en
        ORDER BY days_with_cases DESC, total DESC
        LIMIT 6
    """
    return db.query(sql, (start_date, end_date))


def _jumps(col, start_date, end_date):
    sql = f"""
        WITH agg AS (
          SELECT d.name_en, COALESCE(AVG(c.{col}), 0) AS typical, COALESCE(MAX(c.{col}), 0) AS worst
          FROM crime_daily c JOIN districts d ON d.id = c.district_id
          WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
          GROUP BY d.name_en
        ),
        worst_date AS (
          SELECT DISTINCT ON (d.name_en) d.name_en, c.report_date AS when_date
          FROM crime_daily c JOIN districts d ON d.id = c.district_id
          WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
          ORDER BY d.name_en, c.{col} DESC, c.report_date DESC
        )
        SELECT a.name_en, a.typical, a.worst, w.when_date
        FROM agg a JOIN worst_date w ON w.name_en = a.name_en
        WHERE a.worst > 0
        ORDER BY a.worst DESC, a.typical ASC
        LIMIT 5
    """
    return db.query(sql, (start_date, end_date, start_date, end_date))


def _rising(col, end_date):
    end = date.fromisoformat(str(end_date))
    last7_start, last7_end = end - timedelta(days=6), end
    prior7_start, prior7_end = end - timedelta(days=13), end - timedelta(days=7)
    sql = f"""
        SELECT d.name_en,
          COALESCE(SUM(c.{col}) FILTER (WHERE c.report_date BETWEEN %(l0)s AND %(l1)s), 0) AS last7,
          COALESCE(SUM(c.{col}) FILTER (WHERE c.report_date BETWEEN %(p0)s AND %(p1)s), 0) AS prior7
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %(p0)s AND %(l1)s
        GROUP BY d.name_en
        HAVING COALESCE(SUM(c.{col}) FILTER (WHERE c.report_date BETWEEN %(l0)s AND %(l1)s), 0)
             > COALESCE(SUM(c.{col}) FILTER (WHERE c.report_date BETWEEN %(p0)s AND %(p1)s), 0)
           AND COALESCE(SUM(c.{col}) FILTER (WHERE c.report_date BETWEEN %(l0)s AND %(l1)s), 0) >= 2
        ORDER BY (
          COALESCE(SUM(c.{col}) FILTER (WHERE c.report_date BETWEEN %(l0)s AND %(l1)s), 0)
          - COALESCE(SUM(c.{col}) FILTER (WHERE c.report_date BETWEEN %(p0)s AND %(p1)s), 0)
        ) DESC
        LIMIT 5
    """
    return db.query(sql, dict(l0=last7_start, l1=last7_end, p0=prior7_start, p1=prior7_end))


def _page(col, label, start_date, end_date, reporting_day, data_period, header_note):
    chronic = _chronic(col, start_date, end_date)
    jumps = _jumps(col, start_date, end_date)
    rising = _rising(col, end_date)

    chronic_rows = "".join(
        f'<tr><td><span class="rank crimson">{i+1}</span></td><td><b>{r["name_en"]}</b></td>'
        f'<td class="num tnum">{r["days_with_cases"]}</td><td class="num tnum">{r["total"]}</td>'
        f'<td class="num tnum">{r["avg_day"]:.2f}</td></tr>'
        for i, r in enumerate(chronic)
    )
    jumps_rows = "".join(
        f'<tr><td><span class="rank violet">{i+1}</span></td><td><b>{r["name_en"]}</b></td>'
        f'<td class="num tnum">{r["typical"]:.2f}</td><td class="num tnum">{r["worst"]}</td>'
        f'<td>{r["when_date"]}</td></tr>'
        for i, r in enumerate(jumps)
    )
    rising_rows = "".join(
        f'<tr><td><span class="rank amber">{i+1}</span></td><td><b>{r["name_en"]}</b></td>'
        f'<td class="num tnum">{r["last7"]}</td></tr>'
        for i, r in enumerate(rising)
    )

    chronic_note = (
        f'{chronic[0]["name_en"]} is the most consistent, cases on {chronic[0]["days_with_cases"]} days, '
        f'ahead of {chronic[1]["name_en"]} ({chronic[1]["days_with_cases"]}).' if len(chronic) >= 2
        else "Not enough data in this period to compare districts."
    )
    jumps_note = (
        f'Sudden one-day spikes happened in {", ".join(r["name_en"] for r in jumps[:3])}. '
        f'Largest: {jumps[0]["name_en"]}, {jumps[0]["worst"]} cases on {jumps[0]["when_date"]}.'
        if jumps else "No single-day spikes stood out in this period."
    )
    rising_note = (
        f'{", ".join(r["name_en"] for r in rising[:3])} all saw more cases in the most recent 7 days than the 7 before it.'
        if rising else "No district showed a clear rising pattern in the most recent 7 days versus the week before."
    )

    return masthead(f"{label} Pattern Analysis", f"{label} Focused Analysis", reporting_day, data_period, header_note) + f"""
  <div class="two-col">
    <div>
      <span class="sec-tag crimson">Chronic Districts</span>
      <p class="sec-note">Districts reporting cases almost every day, not one-off spikes.</p>
      <div class="table-wrap">
        <table>
          <thead class="crimson"><tr><th>#</th><th>District</th><th class="num">Days</th><th class="num">Total</th><th class="num">Avg/day</th></tr></thead>
          <tbody>{chronic_rows}</tbody>
        </table>
        <div class="tbl-note"><b>In short:</b> {chronic_note}</div>
      </div>
    </div>
    <div>
      <span class="sec-tag violet">Biggest One-Day Jumps</span>
      <p class="sec-note">Districts with a sudden one-day spike in cases.</p>
      <div class="table-wrap">
        <table>
          <thead class="violet"><tr><th>#</th><th>District</th><th class="num">Normal/day</th><th class="num">Worst day</th><th>When</th></tr></thead>
          <tbody>{jumps_rows}</tbody>
        </table>
        <div class="tbl-note"><b>In short:</b> {jumps_note}</div>
      </div>
    </div>
  </div>

  <span class="sec-tag amber">Rising Fast, Most Recent 7 Days</span>
  <p class="sec-note">Districts with more cases in the last 7 days of the period than the 7 days before that.</p>
  <div class="table-wrap" style="margin-bottom:4mm">
    <table>
      <thead class="amber"><tr><th>#</th><th>District</th><th class="num">Last 7 Days</th></tr></thead>
      <tbody>{rising_rows or '<tr><td colspan="3" style="text-align:center;color:#9aa0b0">No districts met the rising-fast threshold this period</td></tr>'}</tbody>
    </table>
  </div>

  <div class="callout">
    <b>Pattern Summary</b>
    <p style="margin-top:5px">{rising_note}</p>
  </div>
""" + FOOTER


def generate(start_date, end_date, reporting_day, header_note=None, output="pdf", **_):
    data_period = f"{start_date} to {end_date}"
    pages = [
        _page(col, label, start_date, end_date, reporting_day, data_period, header_note)
        for col, label in HEADLINE_CATEGORIES
    ]
    html = wrap_pages(*pages, title="Crime Pattern Analysis By Category", editable=(output == "html"))
    return save_html(html) if output == "html" else render_pdf(html)
