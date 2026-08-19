# -*- coding: utf-8 -*-
"""District-wise total crime CSV export, all 14 recorded categories."""
import csv
import io

import db
from reports.common import ALL_CATEGORIES, DISTRICT_FILTER_SQL


def generate(start_date, end_date, **_):
    cols_sql = ",".join(f"SUM(c.{col}) AS {col}" for col, _ in ALL_CATEGORIES)
    grand_sql = "+".join(f"c.{col}" for col, _ in ALL_CATEGORIES)
    sql = f"""
        SELECT d.name_en, {cols_sql}, SUM({grand_sql}) AS grand_total
        FROM crime_daily c
        JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en
        ORDER BY grand_total DESC
    """
    rows = db.query(sql, (start_date, end_date))

    buf = io.StringIO()
    writer = csv.writer(buf)
    header = ["District"] + [label for _, label in ALL_CATEGORIES] + ["Grand Total"]
    writer.writerow(header)
    totals = [0] * (len(ALL_CATEGORIES) + 1)
    for r in rows:
        vals = [r[col] or 0 for col, _ in ALL_CATEGORIES] + [r["grand_total"] or 0]
        writer.writerow([r["name_en"]] + vals)
        for i, v in enumerate(vals):
            totals[i] += v
    writer.writerow(["GRAND TOTAL"] + totals)
    return buf.getvalue()
