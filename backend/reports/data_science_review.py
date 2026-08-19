# -*- coding: utf-8 -*-
"""Comprehensive Crime Data Review — prepared by the CSU Data Analysis
Committee (five coordinating desks: Population & Demographics, Statistical
Methods & Anomaly Detection, Comparative & International Benchmarking,
District Risk Profiling, and Data Quality & Methodology). Content-first,
unstyled-by-design report: every finding is backed by either our own
crime_daily records or an explicitly-cited official external source. No
figure in this report is estimated, interpolated, or invented — where
official data was not available for a comparison, that comparison is
omitted rather than approximated.

WHY THIS REPORT EXISTS
Every other report in this system ranks districts by raw case counts. Raw
counts systematically favour large-population districts (Lahore, Faisalabad,
Multan) as "worst" purely because more people live there — they say nothing
about risk *per resident*, which is what a policy-maker actually needs to
compare Kot Addu against Multan on equal footing. This report adds the
population-adjusted layer that has been missing, plus statistical outlier
detection, international benchmarking, and a composite priority list.

DATA SOURCES (full provenance — see the Methodology section for the
rendered version of this list)
  1. Crime counts: crime_daily table, sourced from Punjab Police daily
     returns via the CSU control room. Internal, primary source.
  2. District/tehsil population, 2023 and 2017: Pakistan Bureau of
     Statistics, 7th Population & Housing Census 2023, Provincial Census
     Report — Punjab, District/Tehsil population table.
     https://www.pbs.gov.pk/wp-content/uploads/census_tables/tables/table_1_punjab_districts.pdf
     Retrieved 19 Aug 2026. Official Government of Pakistan source.
  3. International intentional-homicide benchmark: World Bank Open Data,
     indicator VC.IHR.PSRC.P5 ("Intentional homicides, per 100,000 people"),
     built from UNODC Global Study on Homicide research data.
     https://data.worldbank.org/indicator/VC.IHR.PSRC.P5
     Pakistan and world-average figures, 2023 (latest year published at
     time of writing). Homicide is the only crime category with a
     sufficiently consistent legal definition and reporting standard to be
     meaningfully compared across countries, so international benchmarking
     in this report is restricted to Murder only — Robbery, Snatching,
     Child Abuse etc. are NOT compared internationally, since what counts
     as each of those varies too much by country's legal code to be a fair
     comparison.

Five CSU reporting units (Wazirabad, Kot Addu, Murree, Talagang, Tonsa)
are tehsils, not top-level census districts — the 2023 census still counts
them inside their parent district (Gujranwala, Muzaffargarh, Rawalpindi,
Chakwal, Dera Ghazi Khan respectively). Their population below is taken
from the tehsil-level rows of the same official table and subtracted from
the parent district's total, so no resident is double-counted. Talagang and
Tonsa are excluded from this report's per-capita analysis for the same
reason they are excluded from every other report (see
DISTRICT_FILTER_SQL / exclude_from_analysis) — kept here only for the
population reference table.
"""
import json
from datetime import date

import db
from reports.common import (
    HEADLINE_CATEGORIES, DISTRICT_FILTER_SQL, CSS as BASE_CSS, EDIT_TOOLBAR,
    render_pdf, save_html, real_crime_sum_sql, esc,
)

# ═══════════════════════════════════════════════════════════════════════
# OFFICIAL DATA — Population & Housing Census 2023, Pakistan Bureau of
# Statistics, Provincial Census Report – Punjab (see module docstring for
# full citation). Figures are "ALL SEXES" district/tehsil population.
# Five districts are split to match CSU's own reporting units (parent
# district total minus the tehsil that CSU reports separately).
# ═══════════════════════════════════════════════════════════════════════
POPULATION_2023 = {
    "Lahore": 13004135, "Sheikhupura": 4049418, "Nankana Sahib": 1634871,
    "Kasur": 4084286, "Gujranwala": 4966338, "Sialkot": 4499394,
    "Narowal": 1950954, "Gujrat": 3219375, "Hafizabad": 1319909,
    "Mandi Bahauddin": 1829486, "Faisalabad": 9075819, "Toba Tek Singh": 2524044,
    "Jhang": 3065639, "Chiniot": 1563024, "Rawalpindi": 5866385,
    "Attock": 2170423, "Chakwal": 1277219, "Jhelum": 1382308,
    "Sargodha": 4334448, "Khushab": 1501089, "Bhakkar": 1957470,
    "Mianwali": 1798268, "Multan": 5362305, "Khanewal": 3364077,
    "Lodhran": 1928299, "Vehari": 3430421, "Muzaffargarh": 3943145,
    "Layyah": 2102386, "Sahiwal": 2881811, "Okara": 3515490,
    "Pakpattan": 2136170, "Bahawalpur": 4284964, "Bahawalnagar": 3550342,
    "Rahim Yar Khan": 5564703, "D.G. Khan": 2596928, "Rajanpur": 2381049,
    "Kot Addu": 1072180, "Murree": 252526, "Talagang": 457635,
    "Tonsa": 796777, "Wazirabad": 993412,
}
POPULATION_2017 = {
    "Lahore": 11119985, "Sheikhupura": 3460004, "Nankana Sahib": 1354986,
    "Kasur": 3454881, "Gujranwala": 4180794, "Sialkot": 3894938,
    "Narowal": 1707575, "Gujrat": 2756289, "Hafizabad": 1156954,
    "Mandi Bahauddin": 1594039, "Faisalabad": 7882444, "Toba Tek Singh": 2190602,
    "Jhang": 2743526, "Chiniot": 1368659, "Rawalpindi": 5169363,
    "Attock": 1886378, "Chakwal": 1085636, "Jhelum": 1222403,
    "Sargodha": 3696212, "Khushab": 1280372, "Bhakkar": 1647852,
    "Mianwali": 1542601, "Multan": 4746166, "Khanewal": 2920233,
    "Lodhran": 1699693, "Vehari": 2902081, "Muzaffargarh": 3346762,
    "Layyah": 1823995, "Sahiwal": 2513011, "Okara": 3040826,
    "Pakpattan": 1824228, "Bahawalpur": 3669176, "Bahawalnagar": 2975656,
    "Rahim Yar Khan": 4807762, "D.G. Khan": 2194846, "Rajanpur": 1996039,
    "Kot Addu": 981787, "Murree": 233017, "Talagang": 409827,
    "Tonsa": 677785, "Wazirabad": 830272,
}
AREA_SQKM = {
    "Lahore": 1772, "Sheikhupura": 3744, "Nankana Sahib": 2216, "Kasur": 3995,
    "Gujranwala": 2426, "Sialkot": 3016, "Narowal": 2337, "Gujrat": 3192,
    "Hafizabad": 2367, "Mandi Bahauddin": 2673, "Faisalabad": 5857,
    "Toba Tek Singh": 3252, "Jhang": 6166, "Chiniot": 2643, "Rawalpindi": 4851,
    "Attock": 6857, "Chakwal": 4503, "Jhelum": 3587, "Sargodha": 5856,
    "Khushab": 6511, "Bhakkar": 8153, "Mianwali": 5840, "Multan": 3720,
    "Khanewal": 4349, "Lodhran": 2778, "Vehari": 4364, "Muzaffargarh": 6563,
    "Layyah": 6289, "Sahiwal": 3201, "Okara": 4377, "Pakpattan": 2724,
    "Bahawalpur": 24830, "Bahawalnagar": 8878, "Rahim Yar Khan": 11880,
    "D.G. Khan": 9153, "Rajanpur": 12318, "Kot Addu": 1686, "Murree": 434,
    "Talagang": 2022, "Tonsa": 2769, "Wazirabad": 1196,
}

# World Bank Open Data, indicator VC.IHR.PSRC.P5 (UNODC-sourced), 2023.
# https://data.worldbank.org/indicator/VC.IHR.PSRC.P5
INTL_HOMICIDE_RATE_2023 = dict(pakistan=4.3, world=5.2, asia=2.0)

REAL_CRIME_LABEL = "All Real Crime (12 categories, excl. Road Accidents & Religious Issues)"

PAGE_MARGIN = dict(top="34mm", right="13mm", bottom="16mm", left="13mm")

EXTRA_CSS = """
  @page{size:A4;margin:__PAGE_MARGIN__}
  body{background:#fff}
  @media screen{ body{background:#DDD} }
  .flow-body{max-width:800px;margin:0 auto;padding:0 0 10mm;background:#fff}
  @media screen{ .flow-body{padding:16mm 13mm 20mm;box-shadow:0 4px 24px rgba(0,0,0,.12);margin:14px auto} }
  .flow-section{margin-bottom:8mm}
  .keep{break-inside:avoid;page-break-inside:avoid}
  table tr{break-inside:avoid;page-break-inside:avoid}
  .section-heading{display:flex;align-items:center;gap:9px;margin:0 0 2mm;padding-bottom:2mm;border-bottom:2px solid var(--line)}
  .section-heading .num-badge{flex:0 0 auto;display:inline-block;min-width:24px;height:24px;line-height:24px;padding:0 4px;border-radius:12px;background:var(--navy);color:#fff;font-size:11px;font-weight:800;text-align:center;white-space:nowrap}
  .section-heading h2{font-size:13.5px;font-weight:900;color:var(--navy);text-transform:uppercase;letter-spacing:.03em}
  .desk-tag{font-size:9px;font-weight:800;letter-spacing:.03em;text-transform:uppercase;color:var(--navy-2);background:#F1F0FA;border-radius:20px;padding:3px 10px;margin:0 0 3mm 31px;display:inline-block}
  .section-sub{font-size:10px;color:var(--muted);margin:0 0 3mm 31px;line-height:1.5}
  p.body-text{font-size:10.8px;color:var(--ink);line-height:1.65;margin:0 0 3mm}
  ul.body-list{margin:0 0 3mm 18px;font-size:10.8px;color:var(--ink);line-height:1.65}
  ul.body-list li{margin-bottom:1.5mm}
  .cover-title{font-size:26px;font-weight:900;color:var(--navy);letter-spacing:-.01em;line-height:1.2;margin-top:6mm}
  .cover-sub{font-size:13px;color:var(--navy-2);font-weight:700;margin-top:3mm}
  .cover-meta{font-size:10.5px;color:var(--muted);margin-top:8mm;line-height:1.7}
  .committee-grid{display:grid;grid-template-columns:1fr 1fr;gap:3mm;margin-top:6mm}
  .committee-card{border:1px solid var(--line);border-left:3px solid var(--navy);border-radius:6px;background:#FBFAF7;padding:7px 11px}
  .committee-card .role{font-size:10px;font-weight:800;color:var(--navy)}
  .committee-card .scope{font-size:9px;color:var(--muted);margin-top:2px;line-height:1.4}
  table.tight{font-size:9.3px}
  table.tight th,table.tight td{padding:4.5px 7px}
  td.flag-hi{color:var(--crimson);font-weight:800}
  td.flag-lo{color:var(--teal);font-weight:800}
  .src-note{font-size:8.7px;color:var(--faint);line-height:1.5;padding:6px 10px;background:#FBFAF7;border-top:1px solid var(--line);white-space:normal}
  .bench-bar-row{display:flex;align-items:center;gap:8px;margin-bottom:4px}
  .bench-bar-label{flex:0 0 130px;font-size:9.5px;font-weight:700;color:var(--ink);text-align:right}
  .bench-bar-track{flex:1;background:#F1F0EB;border-radius:4px;height:14px;position:relative}
  .bench-bar-fill{height:100%;border-radius:4px;background:var(--navy)}
  .bench-bar-val{margin-left:8px;font-size:9.5px;font-weight:800;color:var(--ink);flex:0 0 46px}
"""
EXTRA_CSS = EXTRA_CSS.replace(
    "__PAGE_MARGIN__",
    f'{PAGE_MARGIN["top"]} {PAGE_MARGIN["right"]} {PAGE_MARGIN["bottom"]} {PAGE_MARGIN["left"]}',
)

COMMITTEE_DESKS = [
    ("Population & Demographics Desk",
     "Sources and validates official population figures; computes per-capita rates."),
    ("Statistical Methods & Anomaly Detection Desk",
     "Z-score outlier detection across districts; flags statistically unusual concentrations."),
    ("Comparative & International Benchmarking Desk",
     "Places Punjab's homicide rate against Pakistan and global official figures."),
    ("District Risk Profiling Desk",
     "Combines raw-count and per-capita signals into a single priority list."),
    ("Data Quality & Methodology Desk",
     "Checks reporting completeness and states this report's limitations plainly."),
]


# ═══════════════════════════════════════════════════════════════════════
# Data helpers
# ═══════════════════════════════════════════════════════════════════════
def _to_date(d):
    return d if isinstance(d, date) else date.fromisoformat(str(d))


def _district_data(start_date, end_date):
    """Per district: each headline category total, total real crime, and
    days on file, for districts included in every other report."""
    cols_sql = ",".join(f"COALESCE(SUM(c.{c}),0) AS {c}" for c, _ in HEADLINE_CATEGORIES)
    sql = f"""
        SELECT d.name_en, {cols_sql}, COALESCE(SUM({real_crime_sum_sql('c')}),0) AS total_real,
          COUNT(DISTINCT c.report_date) AS days_on_file
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en
    """
    rows = db.query(sql, (start_date, end_date))
    out = []
    for r in rows:
        pop = POPULATION_2023.get(r["name_en"])
        out.append(dict(r, population=pop))
    return out


def _rate_per_100k(count, population):
    if not population:
        return None
    return count / population * 100000.0


def _mean_std(values):
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return mean, var ** 0.5


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return None
    return cov / (sx * sy)


def _bar(label, value, max_value, suffix=""):
    pct = min(value / max_value * 100, 100) if max_value else 0
    return (
        f'<div class="bench-bar-row"><div class="bench-bar-label">{esc(label)}</div>'
        f'<div class="bench-bar-track"><div class="bench-bar-fill" style="width:{pct:.1f}%"></div></div>'
        f'<div class="bench-bar-val">{value:.1f}{suffix}</div></div>'
    )


# ═══════════════════════════════════════════════════════════════════════
# Sections
# ═══════════════════════════════════════════════════════════════════════
def _cover(reporting_day, data_period, header_note):
    committee_html = "".join(
        f'<div class="committee-card"><div class="role">{esc(role)}</div><div class="scope">{esc(scope)}</div></div>'
        for role, scope in COMMITTEE_DESKS
    )
    return f"""
  <div class="flow-section keep">
    <div class="cover-title">Comprehensive Crime Data Review</div>
    <div class="cover-sub">Population-Adjusted Risk, Statistical Outliers &amp; International Benchmarking</div>
    <div class="cover-meta">
      Prepared by the CSU Data Analysis Committee for the Chief Minister's Office (Law &amp; Order)<br/>
      Reporting Day: <b>{esc(reporting_day)}</b> &nbsp;|&nbsp; Data Period: <b>{esc(data_period)}</b>
      {f'<br/><i>{esc(header_note)}</i>' if header_note else ""}
    </div>
    <div class="committee-grid">{committee_html}</div>
  </div>
"""


def _purpose_section():
    return """
  <div class="flow-section keep">
    <div class="section-heading"><span class="num-badge">1</span><h2>Purpose &amp; Why This Report Exists</h2></div>
    <p class="body-text">Every recurring report this office currently produces ranks districts by <b>raw case counts</b>.
    Raw counts are the right number for operational deployment (more cases in Lahore genuinely means more casework
    in Lahore), but they are the wrong number for judging <b>relative risk to an individual resident</b>, because
    they mechanically favour whichever districts have the most people. A district of 13 million and a district of
    1.3 million will never look comparable on a raw-count table, even if the smaller one is, resident for resident,
    the more dangerous place to live.</p>
    <p class="body-text">This report adds the layer that has been missing: every headline crime category expressed as
    a rate <b>per 100,000 residents</b>, using official 2023 census population. It also adds three things no other
    report in this system currently does — statistical outlier detection (which districts are genuine anomalies, not
    just "highest"), an international benchmark for Murder against Pakistan's and the world's official homicide
    rate, and a single composite list of the districts and crime types that most need careful, individual review.</p>
    <p class="body-text">This is a content-first draft. Tables, figures and structure only — visual design is intentionally
    left for a later pass.</p>
  </div>
"""


def _methodology_section(data_period, n_days):
    return f"""
  <div class="flow-section keep">
    <div class="section-heading"><span class="num-badge">2</span><h2>Data Sources &amp; Methodology</h2></div>
    <div class="desk-tag">Data Quality &amp; Methodology Desk</div>
    <ul class="body-list">
      <li><b>Crime counts.</b> The crime_daily table, sourced from Punjab Police daily returns via the CSU control
      room. Data period for this report: <b>{esc(data_period)}</b>.</li>
      <li><b>District population.</b> Pakistan Bureau of Statistics, 7th Population &amp; Housing Census 2023,
      Provincial Census Report&nbsp;&mdash; Punjab, official district/tehsil population table (2023 and 2017 figures),
      retrieved 19&nbsp;Aug&nbsp;2026 from pbs.gov.pk. Five CSU reporting units (Wazirabad, Kot&nbsp;Addu, Murree,
      Talagang, Tonsa) are census tehsils, not top-level census districts; their population is taken from the
      tehsil-level rows of the same table and subtracted from their parent district so no resident is
      double-counted. Talagang and Tonsa are excluded from per-capita analysis below, matching this office's
      standard exclusion list used in every other report.</li>
      <li><b>International homicide benchmark.</b> World Bank Open Data, indicator VC.IHR.PSRC.P5
      ("Intentional homicides, per 100,000 people"), built from UNODC Global Study on Homicide research data,
      2023 figures. Homicide is the only category compared internationally in this report, because it is the only
      one with a sufficiently consistent legal definition and reporting standard across countries &mdash; comparing
      categories like Robbery or Snatching across national legal systems would not be a fair or meaningful
      comparison, so this report does not attempt it.</li>
      <li><b>Rates.</b> Crime rate per 100,000 = (case count &divide; population) &times; 100,000, for the data
      period stated above. Where a rate is compared to an <i>annual</i> international benchmark, it is separately
      annualised: annualised rate = period rate &times; (365 &divide; {n_days}), and is labelled as such wherever
      shown.</li>
      <li><b>Outlier detection.</b> For each headline category, a district is flagged as a statistical outlier if
      its per-100,000 rate exceeds the province-wide mean rate for that category by more than two standard
      deviations (a standard, conservative threshold — roughly the top 2&ndash;3% of a normal distribution).</li>
      <li><b>What this report does not claim.</b> Reported crime is not the same as actual crime incidence, and
      differences in policing intensity, public willingness to report, or record-keeping practice between districts
      can affect counts independently of true risk. Census population is a mid-2023 snapshot; current populations
      will have grown since, at each district's own historical rate (shown in Appendix&nbsp;A) — this report does not
      project forward. No figure in this report has been estimated or interpolated; where an official comparison
      figure was not available, the comparison is simply not made.</li>
    </ul>
  </div>
"""


def _per_capita_section(district_rows, n_days):
    rows_sorted = sorted(
        [r for r in district_rows if r["population"]], key=lambda r: -r["total_real"]
    )
    for i, r in enumerate(rows_sorted):
        r["raw_rank"] = i + 1
        r["rate"] = _rate_per_100k(r["total_real"], r["population"])
    by_rate = sorted(rows_sorted, key=lambda r: -r["rate"])
    for i, r in enumerate(by_rate):
        r["rate_rank"] = i + 1

    trs = "".join(
        f'<tr><td>{r["raw_rank"]}</td><td><b>{esc(r["name_en"])}</b></td>'
        f'<td class="num tnum">{r["population"]:,}</td>'
        f'<td class="num tnum">{r["total_real"]}</td>'
        f'<td class="num tnum"><b>{r["rate"]:.1f}</b></td>'
        f'<td class="num tnum">{r["rate_rank"]}</td></tr>'
        for r in sorted(by_rate, key=lambda r: -r["rate"])
    )
    return f"""
  <div class="flow-section">
    <div class="section-heading"><span class="num-badge">3</span><h2>Population-Adjusted Crime Rates — All Real Crime</h2></div>
    <div class="desk-tag">Population &amp; Demographics Desk</div>
    <div class="section-sub">{esc(REAL_CRIME_LABEL)}, all districts, ranked by rate per 100,000 residents (highest first). Rate uses official 2023 census population.</div>
    <div class="table-wrap keep">
      <table class="tight">
        <thead class="navy"><tr><th>Raw Rank</th><th>District</th><th class="num">Population (2023)</th><th class="num">Case Count</th><th class="num">Rate / 100,000</th><th class="num">Rate Rank</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
      <div class="tbl-note">Raw Rank is the district's position by case count alone (1 = most cases) — the number every other report in this system shows. Rate Rank is its position once population is accounted for. Where Rate Rank is a much lower number than Raw Rank, the district is more dangerous per resident than its case count alone suggests; see Section 4.</div>
    </div>
  </div>
"""


def _hidden_risk_section(district_rows):
    candidates = [r for r in district_rows if r["population"] and r["raw_rank"] > 15 and r["rate_rank"] <= 12]
    candidates.sort(key=lambda r: r["rate_rank"])
    if not candidates:
        body = '<p class="body-text">No district met the hidden-risk threshold (top-12 by rate, outside the top 15 by raw count) for this period.</p>'
    else:
        rows_html = "".join(
            f'<tr><td><b>{esc(r["name_en"])}</b></td><td class="num tnum">{r["raw_rank"]}</td>'
            f'<td class="num tnum flag-hi">{r["rate_rank"]}</td><td class="num tnum">{r["rate"]:.1f}</td>'
            f'<td class="num tnum">{r["population"]:,}</td></tr>'
            for r in candidates
        )
        body = f"""
    <div class="table-wrap keep">
      <table class="tight">
        <thead class="crimson"><tr><th>District</th><th class="num">Raw Rank</th><th class="num">Rate Rank</th><th class="num">Rate / 100,000</th><th class="num">Population</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div class="tbl-note">These districts do not appear in the "worst 10-15" of any raw-count report, yet rank in the top 12 provincially by population-adjusted rate. Their smaller population means the same case count that would look unremarkable in Lahore represents a much higher chance of a resident being affected here.</div>
    </div>
"""
    return f"""
  <div class="flow-section">
    <div class="section-heading"><span class="num-badge">4</span><h2>Hidden-Risk Districts</h2></div>
    <div class="desk-tag">District Risk Profiling Desk</div>
    <div class="section-sub">Districts whose per-capita rank is far worse than their raw-count rank — the ones invisible to every raw-count report this office produces.</div>
    {body}
  </div>
"""


def _outlier_section(start_date, end_date):
    blocks = []
    for col, label in HEADLINE_CATEGORIES:
        sql = f"""
            SELECT d.name_en, COALESCE(SUM(c.{col}),0) AS v
            FROM crime_daily c JOIN districts d ON d.id = c.district_id
            WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
            GROUP BY d.name_en
        """
        rows = db.query(sql, (start_date, end_date))
        rated = []
        for r in rows:
            pop = POPULATION_2023.get(r["name_en"])
            if not pop:
                continue
            rated.append((r["name_en"], r["v"], _rate_per_100k(r["v"], pop)))
        rates = [x[2] for x in rated]
        mean, std = _mean_std(rates)
        threshold = mean + 2 * std
        outliers = sorted([x for x in rated if std > 0 and x[2] > threshold], key=lambda x: -x[2])
        if outliers:
            rows_html = "".join(
                f'<tr><td><b>{esc(name)}</b></td><td class="num tnum">{count}</td>'
                f'<td class="num tnum flag-hi">{rate:.1f}</td><td class="num tnum">{mean:.1f}</td>'
                f'<td class="num tnum">+{(rate - mean) / std:.1f}&sigma;</td></tr>'
                for name, count, rate in outliers
            )
            blocks.append(f"""
    <div class="table-wrap keep" style="margin-bottom:4mm">
      <table class="tight">
        <thead class="violet"><tr><th colspan="5">{esc(label)} — statistical outliers (rate &gt; mean + 2&sigma;, province mean {mean:.1f}/100k)</th></tr></thead>
        <thead class="navy"><tr><th>District</th><th class="num">Cases</th><th class="num">Rate / 100,000</th><th class="num">Province Mean</th><th class="num">Deviation</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
""")
    if not blocks:
        blocks_html = '<p class="body-text">No district exceeded the 2-standard-deviation outlier threshold in any headline category for this period.</p>'
    else:
        blocks_html = "".join(blocks)
    return f"""
  <div class="flow-section">
    <div class="section-heading"><span class="num-badge">5</span><h2>Statistical Outlier Detection</h2></div>
    <div class="desk-tag">Statistical Methods &amp; Anomaly Detection Desk</div>
    <div class="section-sub">Per headline category, districts whose population-adjusted rate is a genuine statistical outlier (more than two standard deviations above the province mean), not simply the numerical "highest."</div>
    {blocks_html}
  </div>
"""


def _benchmark_section(district_rows, n_days):
    total_murder = sum(r["murder"] for r in district_rows)
    total_pop = sum(r["population"] for r in district_rows if r["population"])
    punjab_period_rate = _rate_per_100k(total_murder, total_pop) or 0
    punjab_annual_rate = punjab_period_rate * (365 / n_days)

    bench_html = (
        _bar("Punjab (annualised)", punjab_annual_rate, max(punjab_annual_rate, INTL_HOMICIDE_RATE_2023["world"]) * 1.15)
        + _bar("Pakistan (2023, national)", INTL_HOMICIDE_RATE_2023["pakistan"], max(punjab_annual_rate, INTL_HOMICIDE_RATE_2023["world"]) * 1.15)
        + _bar("Asia average (2023)", INTL_HOMICIDE_RATE_2023["asia"], max(punjab_annual_rate, INTL_HOMICIDE_RATE_2023["world"]) * 1.15)
        + _bar("World average (2023)", INTL_HOMICIDE_RATE_2023["world"], max(punjab_annual_rate, INTL_HOMICIDE_RATE_2023["world"]) * 1.15)
    )

    district_murder = []
    for r in district_rows:
        if not r["population"]:
            continue
        rate = _rate_per_100k(r["murder"], r["population"]) or 0
        annual = rate * (365 / n_days)
        district_murder.append((r["name_en"], r["murder"], annual))
    district_murder.sort(key=lambda x: -x[2])
    above_world = [x for x in district_murder if x[2] > INTL_HOMICIDE_RATE_2023["world"]]

    rows_html = "".join(
        f'<tr><td><b>{esc(name)}</b></td><td class="num tnum">{count}</td>'
        f'<td class="num tnum {"flag-hi" if rate > INTL_HOMICIDE_RATE_2023["world"] else ""}">{rate:.1f}</td></tr>'
        for name, count, rate in district_murder[:10]
    )

    return f"""
  <div class="flow-section">
    <div class="section-heading"><span class="num-badge">6</span><h2>International Benchmarking — Murder Only</h2></div>
    <div class="desk-tag">Comparative &amp; International Benchmarking Desk</div>
    <div class="section-sub">Murder rate per 100,000 population, annualised for fair comparison against annual international figures. See Section 2 for why only Murder is benchmarked internationally.</div>
    <div class="keep" style="margin:3mm 0 4mm">{bench_html}</div>
    <p class="body-text">Punjab's province-wide annualised Murder rate for this period is <b>{punjab_annual_rate:.1f} per 100,000</b>,
    compared with Pakistan's official 2023 national rate of <b>{INTL_HOMICIDE_RATE_2023["pakistan"]:.1f}</b>, the Asia average of
    <b>{INTL_HOMICIDE_RATE_2023["asia"]:.1f}</b>, and the world average of <b>{INTL_HOMICIDE_RATE_2023["world"]:.1f}</b> (all per 100,000, World Bank/UNODC 2023).
    {len(above_world)} of {len(district_murder)} districts individually exceed the world average when annualised.</p>
    <div class="table-wrap keep">
      <table class="tight">
        <thead class="navy"><tr><th>District</th><th class="num">Murder Cases (period)</th><th class="num">Annualised Rate / 100,000</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div class="tbl-note">Top 10 districts by annualised Murder rate. Highlighted cells exceed the {INTL_HOMICIDE_RATE_2023["world"]:.1f}/100,000 world average. Annualising a short data period amplifies small counts, so this table is a screening signal for further review, not a final verdict on any one district.</div>
    </div>
  </div>
"""


def _density_section(district_rows):
    pairs = [
        (r["name_en"], AREA_SQKM.get(r["name_en"]), r["population"], r["total_real"])
        for r in district_rows if AREA_SQKM.get(r["name_en"]) and r["population"]
    ]
    densities = [pop / area for _, area, pop, _ in pairs]
    crime_rates = [_rate_per_100k(total, pop) for _, _, pop, total in pairs]
    corr = _pearson(densities, crime_rates)
    corr_text = (
        f'a Pearson correlation coefficient of <b>{corr:+.2f}</b>' if corr is not None
        else "not enough data to compute a correlation"
    )
    direction = ""
    if corr is not None:
        if corr > 0.3:
            direction = "a meaningful positive relationship — denser districts tend to show higher per-capita crime rates."
        elif corr < -0.3:
            direction = "a meaningful negative relationship — denser districts tend to show lower per-capita crime rates."
        else:
            direction = "no meaningful relationship — population density alone does not explain per-capita crime rate variation across Punjab."

    ranked = sorted(zip([p[0] for p in pairs], densities, crime_rates), key=lambda x: -x[1])[:8]
    rows_html = "".join(
        f'<tr><td><b>{esc(name)}</b></td><td class="num tnum">{dens:.0f}</td><td class="num tnum">{rate:.1f}</td></tr>'
        for name, dens, rate in ranked
    )
    return f"""
  <div class="flow-section">
    <div class="section-heading"><span class="num-badge">7</span><h2>Population Density vs. Crime Rate</h2></div>
    <div class="desk-tag">Population &amp; Demographics Desk</div>
    <div class="section-sub">Official 2023 census area and population used to compute density (residents / sq km); tested against this period's per-capita crime rate.</div>
    <p class="body-text">Across the {len(pairs)} districts with both official area and population on file, density and per-capita crime rate show {corr_text}, indicating {direction}</p>
    <div class="table-wrap keep">
      <table class="tight">
        <thead class="navy"><tr><th>District</th><th class="num">Density (residents/km&sup2;)</th><th class="num">Crime Rate / 100,000</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div class="tbl-note">8 highest-density districts shown, for reference alongside their crime rate.</div>
    </div>
  </div>
"""


def _completeness_section(district_rows, n_days):
    thin = [r for r in district_rows if r["days_on_file"] < n_days * 0.9]
    if thin:
        rows_html = "".join(
            f'<tr><td><b>{esc(r["name_en"])}</b></td><td class="num tnum">{r["days_on_file"]}</td>'
            f'<td class="num tnum">{n_days}</td></tr>'
            for r in sorted(thin, key=lambda r: r["days_on_file"])
        )
        body = f"""
    <div class="table-wrap keep">
      <table class="tight">
        <thead class="amber"><tr><th>District</th><th class="num">Days On File</th><th class="num">Days In Period</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div class="tbl-note">These districts have below-90% reporting coverage for this period; their rates and rankings above should be read with that gap in mind.</div>
    </div>
"""
    else:
        min_days = min(r["days_on_file"] for r in district_rows) if district_rows else 0
        body = f'<p class="body-text">All {len(district_rows)} districts have at least 90% day-coverage for this {n_days}-day period (minimum {min_days} of {n_days} days on file). No completeness caveat applies to the rankings above.</p>'
    return f"""
  <div class="flow-section">
    <div class="section-heading"><span class="num-badge">8</span><h2>Data Completeness Check</h2></div>
    <div class="desk-tag">Data Quality &amp; Methodology Desk</div>
    {body}
  </div>
"""


def _priority_section(district_rows, outlier_names):
    scored = []
    for r in district_rows:
        if not r["population"]:
            continue
        score = 0
        reasons = []
        if r["raw_rank"] <= 10:
            score += 1
            reasons.append("top-10 raw count")
        if r["rate_rank"] <= 10:
            score += 1
            reasons.append("top-10 per-capita rate")
        if r["raw_rank"] > 15 and r["rate_rank"] <= 12:
            score += 2
            reasons.append("hidden-risk (rate rank far above raw rank)")
        if r["name_en"] in outlier_names:
            score += 2
            reasons.append(f'statistical outlier in {", ".join(sorted(outlier_names[r["name_en"]]))}')
        if score > 0:
            scored.append((r["name_en"], score, reasons))
    scored.sort(key=lambda x: -x[1])
    rows_html = "".join(
        f'<tr><td><b>{esc(name)}</b></td><td class="num tnum"><b>{score}</b></td><td>{esc("; ".join(reasons))}</td></tr>'
        for name, score, reasons in scored[:15]
    )
    return f"""
  <div class="flow-section">
    <div class="section-heading"><span class="num-badge">9</span><h2>Priority Review Matrix</h2></div>
    <div class="desk-tag">District Risk Profiling Desk — synthesis of Sections 3–6</div>
    <div class="section-sub">Composite score combining raw-count ranking, per-capita ranking, hidden-risk status, and statistical outlier flags. This is the single list this office should start from for district-level follow-up.</div>
    <div class="table-wrap keep">
      <table class="tight">
        <thead class="navy"><tr><th>District</th><th class="num">Priority Score</th><th>Why It's Flagged</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div class="tbl-note">Score is additive across four independent signals (see Methodology); it is a screening tool to focus attention, not a ranking of blame.</div>
    </div>
  </div>
"""


def _recommendations_section():
    return """
  <div class="flow-section">
    <div class="section-heading"><span class="num-badge">10</span><h2>Committee Recommendations</h2></div>
    <ul class="body-list">
      <li>Adopt population-adjusted rate (per 100,000) as a standard second column alongside raw counts in future
      executive reports, so smaller districts are not systematically invisible in "worst district" findings.</li>
      <li>Treat the Priority Review Matrix (Section 9) as the working list for district-level follow-up meetings,
      rather than the raw top-10 case-count table alone.</li>
      <li>Districts newly visible under "Hidden-Risk" (Section 4) warrant a resourcing review even where absolute
      case counts appear modest, since their residents currently face materially higher risk than the raw number
      suggests.</li>
      <li>Where a district's Murder rate individually exceeds the world average (Section 6), a targeted case-file
      review is warranted before drawing conclusions — a short reporting period can amplify a small number of
      cases into a large annualised rate, so this is a screening flag, not a finding on its own.</li>
      <li>Revisit district population figures once the next official census or Bureau of Statistics update is
      published; until then, all per-capita figures in this report use the 2023 census as the most recent official
      source available.</li>
    </ul>
  </div>
"""


def _population_appendix():
    rows_html = "".join(
        f'<tr><td><b>{esc(name)}</b></td><td class="num tnum">{POPULATION_2023[name]:,}</td>'
        f'<td class="num tnum">{POPULATION_2017.get(name, 0):,}</td>'
        f'<td class="num tnum">{((POPULATION_2023[name] / POPULATION_2017[name]) ** (1/6) - 1) * 100:.2f}%</td>'
        f'<td class="num tnum">{AREA_SQKM.get(name, 0):,}</td></tr>'
        for name in sorted(POPULATION_2023)
        if name in POPULATION_2017 and POPULATION_2017[name]
    )
    return f"""
  <div class="flow-section">
    <div class="section-heading"><span class="num-badge">A</span><h2>Appendix A — Full Population Reference Table</h2></div>
    <div class="section-sub">Pakistan Bureau of Statistics, Population &amp; Housing Census 2023, Provincial Census Report — Punjab. All 39 districts covered by this system, plus Talagang and Tonsa for reference (excluded from analysis elsewhere in this system). Annual growth rate is the compound annual rate implied by the 2017-2023 intercensal change.</div>
    <div class="table-wrap keep">
      <table class="tight">
        <thead class="navy"><tr><th>District</th><th class="num">Population 2023</th><th class="num">Population 2017</th><th class="num">Annual Growth Rate</th><th class="num">Area (km&sup2;)</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div class="src-note">Source: Pakistan Bureau of Statistics, 7th Population &amp; Housing Census 2023, Provincial Census Report — Punjab. pbs.gov.pk/wp-content/uploads/census_tables/tables/table_1_punjab_districts.pdf — retrieved 19 Aug 2026. Wazirabad, Kot Addu, Murree, Talagang and Tonsa figures are tehsil-level rows from the same table, with their population subtracted from their parent district (Gujranwala, Muzaffargarh, Rawalpindi, Chakwal, Dera Ghazi Khan respectively) to avoid double-counting.</div>
    </div>
  </div>
"""


# ═══════════════════════════════════════════════════════════════════════
# Assemble
# ═══════════════════════════════════════════════════════════════════════
def generate(start_date, end_date, reporting_day=None, header_note=None, output="pdf", **_):
    start_date = _to_date(start_date)
    end_date = _to_date(end_date)
    reporting_day = reporting_day or date.today().strftime("%d/%m/%Y")
    n_days = (end_date - start_date).days + 1
    data_period = f"{start_date} to {end_date} ({n_days} day{'s' if n_days != 1 else ''})"

    district_rows = _district_data(start_date, end_date)

    # Pre-compute outlier district names per category, for the priority matrix.
    outlier_names = {}
    for col, label in HEADLINE_CATEGORIES:
        sql = f"""
            SELECT d.name_en, COALESCE(SUM(c.{col}),0) AS v
            FROM crime_daily c JOIN districts d ON d.id = c.district_id
            WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
            GROUP BY d.name_en
        """
        rows = db.query(sql, (start_date, end_date))
        rated = [(r["name_en"], _rate_per_100k(r["v"], POPULATION_2023.get(r["name_en"])))
                 for r in rows if POPULATION_2023.get(r["name_en"])]
        rates = [x[1] for x in rated]
        mean, std = _mean_std(rates)
        if std > 0:
            for name, rate in rated:
                if rate > mean + 2 * std:
                    outlier_names.setdefault(name, set()).add(label)

    sections = (
        _cover(reporting_day, data_period, header_note)
        + _purpose_section()
        + _methodology_section(data_period, n_days)
        + _per_capita_section(district_rows, n_days)
        + _hidden_risk_section(district_rows)
        + _outlier_section(start_date, end_date)
        + _benchmark_section(district_rows, n_days)
        + _density_section(district_rows)
        + _completeness_section(district_rows, n_days)
        + _priority_section(district_rows, outlier_names)
        + _recommendations_section()
        + _population_appendix()
    )

    header_tpl = f"""
<div style="width:100%;font-family:Arial,Helvetica,sans-serif;padding:8px 10mm 4px;box-sizing:border-box;-webkit-print-color-adjust:exact;">
  <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid #211d50;padding-bottom:6px;">
    <div style="font-size:15px;font-weight:800;color:#211d50;">Comprehensive Crime Data Review — CSU Data Analysis Committee</div>
  </div>
</div>
"""
    footer_tpl = """
<div style="width:100%;font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#9aa0b0;padding:4px 10mm 6px;box-sizing:border-box;border-top:1px solid #e3e5ee;display:flex;justify-content:space-between;-webkit-print-color-adjust:exact;">
  <span>Data: CSU / Punjab Police (crime counts); Pakistan Bureau of Statistics Census 2023 (population); World Bank / UNODC (international benchmark)</span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>
"""
    pdf_config = json.dumps(dict(headerTemplate=header_tpl, footerTemplate=footer_tpl, margin=PAGE_MARGIN))
    toolbar = EDIT_TOOLBAR if output == "html" else ""

    html = f"""<!doctype html>
<html><head><meta charset="utf-8" /><title>Comprehensive Crime Data Review</title><style>{BASE_CSS}{EXTRA_CSS}</style></head>
<body>{toolbar}
<div class="flow-body">
{sections}
</div>
<script type="application/json" id="pdf-header-footer">{pdf_config}</script>
</body></html>
"""
    return save_html(html) if output == "html" else render_pdf(html)
