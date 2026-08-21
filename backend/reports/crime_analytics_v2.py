# -*- coding: utf-8 -*-
"""Crime Analytics Punjab (New Design) — a brand-new report entry with its
own file, registered separately in app.py. The two existing Crime Analytics
reports (crime_analytics.py, crime_analytics_monthly.py) are NOT modified;
this module only imports their already-tested data functions (weekly trend,
per-category min/max/chronic, rising-district detection, the Key Insights
builder) and renders them in the dark-navy/gold executive design supplied
2026-08-19, matching the reference PDF/HTML pixel-for-pixel where practical.

One thing was added that the supplied design didn't have: a line chart for
the week-by-week "Is Crime Rising or Falling" trend, in Section 02 — every
other weekly-average table in this project has a chart next to it; this
design's table didn't, so one was added in the same visual language
(navy line, gold markers) with its own legend.

Fonts: Playfair Display is embedded as a base64 @font-face (see
render/assets/playfair.txt) rather than linked from Google Fonts, so PDF
generation never depends on outbound network access at render time — the
same reasoning this project already applies to the CSU/Government logos.
"""
import json
from datetime import date

import db
import config
from reports.common import (
    DISTRICT_FILTER_SQL, CSU_LOGO, GOVT_LOGO, esc, save_html, render_pdf,
    real_crime_sum_sql, all_crime_sum_sql,
)
from reports.crime_analytics import (
    ALL_CATEGORIES, HEADLINE_CATEGORIES, OTHER_COLUMNS,
    _date_bounds, _to_date, _weekly_trend, _change_badge, _typical_vs_latest, _minmax5, _chronic5,
    _build_default_insights, _highlight_keywords,
)
from reports.crime_analytics_monthly import (
    _week_template, _weekly_by_category_data, _week_trend_badge, _cal_week_label,
    _rising_districts, _weekly_context,
)

with open(config.ASSETS_DIR / "playfair.txt", "r", encoding="utf-8") as f:
    PLAYFAIR_FONT = f.read().strip()
with open(config.ASSETS_DIR / "csu_building_sketch.txt", "r", encoding="utf-8") as f:
    _CSU_BUILDING_SKETCH_SRC = f.read().strip()

# Abbreviated labels for the wide Week-by-Week table only (18 columns of
# weeks + Typ. + Trend leave very little room per category name); full
# names (from ALL_CATEGORIES) are used everywhere else, including the
# per-crime detail card headings.
SHORT_LABELS = {
    "murder": "Murder", "dacoity": "Dacoity", "robbery": "Robbery",
    "dacoity_robbery_murder": "D/R – Murder", "dacoity_robbery_injury": "D/R – Injury",
    "dacoity_robbery_rape": "D/R – Rape", "snatching_jhappata": "Snatching/<br/>Jhappata",
    "child_abuse": "Child Abuse", "rape": "Rape", "gang_rape": "Gang Rape",
    "sodomy": "Sodomy", "road_accident_casualties": "Road Accident<br/>Cas.",
    "acid_attack": "Acid Attack", "religious_issues": "Religious<br/>Issues",
}
# Categories with their own detail card. Dacoity/Robbery with Rape is
# excluded (0-1 cases/week all period, per the supplied design's own note)
# and only shown in the Week-by-Week table.
CARD_CATEGORIES = [(c, l) for c, l in ALL_CATEGORIES if c != "dacoity_robbery_rape"]

# Cover page icons (calendar x2, shield-lock), line icons drawn from
# primitives so they render identically regardless of installed fonts.
_ICON_CALENDAR = (
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3.5" y="5" width="17" height="15" rx="2"/>'
    '<line x1="3.5" y1="9.5" x2="20.5" y2="9.5"/>'
    '<line x1="8" y1="3" x2="8" y2="6.5"/><line x1="16" y1="3" x2="16" y2="6.5"/>'
    '<rect x="7.6" y="12.6" width="2.6" height="2.6" fill="currentColor" stroke="none"/>'
    '</svg>'
)

# Faded office-building line-art watermark on the cover, used exactly as
# supplied by the developer, but re-embedded as a plain <img> instead of
# the original nested SVG <mask>/<filter> construct. That construct
# rendered fine in Chromium (used to generate the PDF) but produced a
# broken/partial render in iOS's PDF viewer (Preview, Files, Mail, Safari) --
# a known compatibility gap for PDF soft-masks combined with color-matrix
# filters. The source PNG already has the fade and transparency baked in,
# so a plain <img> reproduces the same look with no vector-effect risk.
_CSU_SKETCH = f'<img src="{_CSU_BUILDING_SKETCH_SRC}" width="1060" height="403" style="display:block;width:100%;height:auto">'
_ICON_SHIELD = (
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 3 L20 6 V11 C20 16.5 16.5 20.2 12 21.5 C7.5 20.2 4 16.5 4 11 V6 Z"/>'
    '<rect x="9.3" y="11.4" width="5.4" height="4.6" rx="1"/>'
    '<path d="M10.3 11.4 V9.7 A1.7 1.7 0 0 1 13.7 9.7 V11.4"/>'
    '</svg>'
)

# Cover page bottom accent: a plain navy/gold diagonal bar spanning the full
# page width. Used alone (no building illustration -- dropped per feedback
# that the line-art building didn't read well) on both the front and back
# cover, so the two pages bookend each other with the same quiet motif.
# Cover corner dot pattern -- previously a CSS background radial-gradient
# combined with mask-image for the diagonal fade. mask-image is another
# procedural/vector effect (like the building sketch's old SVG mask) that
# iOS's PDF renderer doesn't reproduce reliably, even though Chromium
# renders it correctly when the PDF is generated. Replaced with a plain
# SVG of individually-opacitied circles -- the same fade, precomputed once,
# with no masking at render time for any viewer to get wrong.
_COVER_DOTS_SVG = (
    '<svg width="260" height="260" viewBox="0 0 260 260" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="6" cy="6" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="6" cy="18" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="6" cy="30" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="6" cy="42" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="6" cy="54" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="6" cy="66" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="6" cy="78" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="6" cy="90" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="6" cy="102" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="6" cy="114" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="6" cy="126" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="6" cy="138" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="18" cy="6" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="18" cy="18" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="18" cy="30" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="18" cy="42" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="18" cy="54" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="18" cy="66" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="18" cy="78" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="18" cy="90" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="18" cy="102" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="18" cy="114" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="18" cy="126" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="18" cy="138" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="18" cy="150" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="30" cy="6" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="30" cy="18" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="30" cy="30" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="30" cy="42" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="30" cy="54" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="30" cy="66" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="30" cy="78" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="30" cy="90" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="30" cy="102" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="30" cy="114" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="30" cy="126" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="30" cy="138" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="30" cy="150" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="30" cy="162" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="42" cy="6" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="42" cy="18" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="42" cy="30" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="42" cy="42" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="42" cy="54" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="42" cy="66" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="42" cy="78" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="42" cy="90" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="42" cy="102" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="42" cy="114" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="42" cy="126" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="42" cy="138" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="42" cy="150" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="42" cy="162" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="42" cy="174" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="54" cy="6" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="54" cy="18" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="54" cy="30" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="54" cy="42" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="54" cy="54" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="54" cy="66" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="54" cy="78" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="54" cy="90" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="54" cy="102" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="54" cy="114" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="54" cy="126" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="54" cy="138" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="54" cy="150" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="54" cy="162" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="54" cy="174" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="54" cy="186" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="66" cy="6" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="66" cy="18" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="66" cy="30" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="66" cy="42" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="66" cy="54" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="66" cy="66" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="66" cy="78" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="66" cy="90" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="66" cy="102" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="66" cy="114" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="66" cy="126" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="66" cy="138" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="66" cy="150" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="66" cy="162" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="66" cy="174" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="66" cy="186" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="66" cy="198" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="78" cy="6" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="78" cy="18" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="78" cy="30" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="78" cy="42" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="78" cy="54" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="78" cy="66" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="78" cy="78" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="78" cy="90" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="78" cy="102" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="78" cy="114" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="78" cy="126" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="78" cy="138" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="78" cy="150" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="78" cy="162" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="78" cy="174" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="78" cy="186" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="78" cy="198" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="78" cy="210" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="90" cy="6" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="90" cy="18" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="90" cy="30" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="90" cy="42" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="90" cy="54" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="90" cy="66" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="90" cy="78" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="90" cy="90" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="90" cy="102" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="90" cy="114" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="90" cy="126" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="90" cy="138" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="90" cy="150" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="90" cy="162" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="90" cy="174" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="90" cy="186" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="90" cy="198" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="90" cy="210" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="90" cy="222" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="102" cy="6" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="102" cy="18" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="102" cy="30" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="102" cy="42" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="102" cy="54" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="102" cy="66" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="102" cy="78" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="102" cy="90" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="102" cy="102" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="102" cy="114" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="102" cy="126" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="102" cy="138" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="102" cy="150" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="102" cy="162" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="102" cy="174" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="102" cy="186" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="102" cy="198" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="102" cy="210" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="102" cy="222" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="102" cy="234" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="114" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="114" cy="18" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="114" cy="30" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="114" cy="42" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="114" cy="54" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="114" cy="66" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="114" cy="78" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="114" cy="90" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="114" cy="102" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="114" cy="114" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="114" cy="126" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="114" cy="138" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="114" cy="150" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="114" cy="162" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="114" cy="174" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="114" cy="186" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="114" cy="198" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="114" cy="210" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="114" cy="222" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="114" cy="234" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="114" cy="246" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="126" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="126" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="126" cy="30" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="126" cy="42" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="126" cy="54" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="126" cy="66" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="126" cy="78" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="126" cy="90" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="126" cy="102" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="126" cy="114" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="126" cy="126" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="126" cy="138" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="126" cy="150" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="126" cy="162" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="126" cy="174" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="126" cy="186" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="126" cy="198" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="126" cy="210" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="126" cy="222" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="126" cy="234" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="126" cy="246" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="126" cy="258" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="138" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="138" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="138" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="138" cy="42" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="138" cy="54" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="138" cy="66" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="138" cy="78" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="138" cy="90" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="138" cy="102" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="138" cy="114" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="138" cy="126" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="138" cy="138" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="138" cy="150" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="138" cy="162" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="138" cy="174" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="138" cy="186" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="138" cy="198" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="138" cy="210" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="138" cy="222" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="138" cy="234" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="138" cy="246" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="138" cy="258" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="138" cy="270" r="1.7" fill="currentColor" opacity="0.033"/><circle cx="150" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="150" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="150" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="150" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="150" cy="54" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="150" cy="66" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="150" cy="78" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="150" cy="90" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="150" cy="102" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="150" cy="114" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="150" cy="126" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="150" cy="138" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="150" cy="150" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="150" cy="162" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="150" cy="174" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="150" cy="186" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="150" cy="198" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="150" cy="210" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="150" cy="222" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="150" cy="234" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="150" cy="246" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="150" cy="258" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="150" cy="270" r="1.7" fill="currentColor" opacity="0.062"/><circle cx="162" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="162" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="162" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="162" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="162" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="162" cy="66" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="162" cy="78" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="162" cy="90" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="162" cy="102" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="162" cy="114" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="162" cy="126" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="162" cy="138" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="162" cy="150" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="162" cy="162" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="162" cy="174" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="162" cy="186" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="162" cy="198" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="162" cy="210" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="162" cy="222" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="162" cy="234" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="162" cy="246" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="162" cy="258" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="162" cy="270" r="1.7" fill="currentColor" opacity="0.09"/><circle cx="174" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="174" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="174" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="174" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="174" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="174" cy="66" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="174" cy="78" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="174" cy="90" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="174" cy="102" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="174" cy="114" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="174" cy="126" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="174" cy="138" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="174" cy="150" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="174" cy="162" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="174" cy="174" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="174" cy="186" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="174" cy="198" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="174" cy="210" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="174" cy="222" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="174" cy="234" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="174" cy="246" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="174" cy="258" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="174" cy="270" r="1.7" fill="currentColor" opacity="0.119"/><circle cx="186" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="186" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="186" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="186" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="186" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="186" cy="66" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="186" cy="78" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="186" cy="90" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="186" cy="102" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="186" cy="114" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="186" cy="126" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="186" cy="138" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="186" cy="150" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="186" cy="162" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="186" cy="174" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="186" cy="186" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="186" cy="198" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="186" cy="210" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="186" cy="222" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="186" cy="234" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="186" cy="246" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="186" cy="258" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="186" cy="270" r="1.7" fill="currentColor" opacity="0.148"/><circle cx="198" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="198" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="198" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="198" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="198" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="198" cy="66" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="198" cy="78" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="198" cy="90" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="198" cy="102" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="198" cy="114" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="198" cy="126" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="198" cy="138" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="198" cy="150" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="198" cy="162" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="198" cy="174" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="198" cy="186" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="198" cy="198" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="198" cy="210" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="198" cy="222" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="198" cy="234" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="198" cy="246" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="198" cy="258" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="198" cy="270" r="1.7" fill="currentColor" opacity="0.177"/><circle cx="210" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="210" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="210" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="210" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="210" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="210" cy="66" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="210" cy="78" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="210" cy="90" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="210" cy="102" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="210" cy="114" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="210" cy="126" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="210" cy="138" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="210" cy="150" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="210" cy="162" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="210" cy="174" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="210" cy="186" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="210" cy="198" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="210" cy="210" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="210" cy="222" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="210" cy="234" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="210" cy="246" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="210" cy="258" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="210" cy="270" r="1.7" fill="currentColor" opacity="0.206"/><circle cx="222" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="66" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="78" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="90" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="102" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="114" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="222" cy="126" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="222" cy="138" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="222" cy="150" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="222" cy="162" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="222" cy="174" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="222" cy="186" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="222" cy="198" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="222" cy="210" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="222" cy="222" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="222" cy="234" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="222" cy="246" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="222" cy="258" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="222" cy="270" r="1.7" fill="currentColor" opacity="0.235"/><circle cx="234" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="66" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="78" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="90" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="102" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="114" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="126" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="234" cy="138" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="234" cy="150" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="234" cy="162" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="234" cy="174" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="234" cy="186" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="234" cy="198" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="234" cy="210" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="234" cy="222" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="234" cy="234" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="234" cy="246" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="234" cy="258" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="234" cy="270" r="1.7" fill="currentColor" opacity="0.263"/><circle cx="246" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="66" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="78" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="90" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="102" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="114" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="126" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="138" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="246" cy="150" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="246" cy="162" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="246" cy="174" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="246" cy="186" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="246" cy="198" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="246" cy="210" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="246" cy="222" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="246" cy="234" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="246" cy="246" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="246" cy="258" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="246" cy="270" r="1.7" fill="currentColor" opacity="0.292"/><circle cx="258" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="66" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="78" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="90" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="102" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="114" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="126" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="138" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="150" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="258" cy="162" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="258" cy="174" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="258" cy="186" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="258" cy="198" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="258" cy="210" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="258" cy="222" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="258" cy="234" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="258" cy="246" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="258" cy="258" r="1.7" fill="currentColor" opacity="0.35"/><circle cx="258" cy="270" r="1.7" fill="currentColor" opacity="0.321"/><circle cx="270" cy="6" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="18" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="30" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="42" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="54" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="66" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="78" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="90" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="102" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="114" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="126" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="138" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="150" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="162" r="1.7" fill="currentColor" opacity="0.6"/><circle cx="270" cy="174" r="1.7" fill="currentColor" opacity="0.581"/><circle cx="270" cy="186" r="1.7" fill="currentColor" opacity="0.552"/><circle cx="270" cy="198" r="1.7" fill="currentColor" opacity="0.523"/><circle cx="270" cy="210" r="1.7" fill="currentColor" opacity="0.494"/><circle cx="270" cy="222" r="1.7" fill="currentColor" opacity="0.465"/><circle cx="270" cy="234" r="1.7" fill="currentColor" opacity="0.437"/><circle cx="270" cy="246" r="1.7" fill="currentColor" opacity="0.408"/><circle cx="270" cy="258" r="1.7" fill="currentColor" opacity="0.379"/><circle cx="270" cy="270" r="1.7" fill="currentColor" opacity="0.35"/>'
    '</svg>'
)

_COVER_BOTTOM_BAR_SVG = """
<svg viewBox="0 0 900 60" width="100%" height="60" preserveAspectRatio="none" style="display:block">
  <polygon points="0,26 900,4 900,60 0,60" fill="#162D45"/>
  <polygon points="660,60 900,14 900,60" fill="#C8A45C"/>
</svg>
"""

# Plain-language methodology note per Key Insights card -- how that
# specific finding is computed, shown as a small gray-background box under
# each card's text so the number isn't just asserted, it's explained.
# Small "i" info-circle icon, drawn from primitives rather than a font glyph
# so it renders identically regardless of what's installed on the machine
# doing the PDF render.
_METHOD_ICON = (
    '<svg width="11" height="11" viewBox="0 0 16 16" style="flex:0 0 auto;margin-top:2px">'
    '<circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.4"/>'
    '<circle cx="8" cy="4.7" r="1.1" fill="currentColor"/>'
    '<rect x="7" y="7" width="2" height="5.6" rx="0.7" fill="currentColor"/>'
    '</svg>'
)

INSIGHT_METHODOLOGY = {
    "Overall Crime Trend": (
        "Most recent complete week's daily average, compared against Typical "
        "(the average of every complete week on file). The trailing partial week is left out of both sides."
    ),
    "Crimes Showing Increase": (
        "Each crime type's latest complete week compared against its own "
        "Typical week. Only listed if the change is 3% or more and the category has at least 20 combined cases, "
        "so a small category swinging from 1 case to 2 doesn't get reported as a headline jump."
    ),
    "Crimes Showing Decline": (
        "Each crime type's latest complete week compared against its own "
        "Typical week. Only listed if the change is 3% or more and the category has at least 20 combined cases, "
        "so a small category isn't reported as a false swing."
    ),
    "High-Incidence Districts": (
        "Every district's own case count as a share of every case reported anywhere "
        "in Punjab this period, ranked highest first."
    ),
    "Persistent Crime Pattern": (
        "Districts that rank among the most chronic (most days with at least one case, "
        "not just the highest total) in 3 or more of the 6 headline crime categories."
    ),
    "Snatching Concentration": (
        "The 3 districts with the highest raw Snatching/Jhappata case count this period."
    ),
    "Sensitive Crime Concerns": (
        "The top 3 districts by Child Abuse case count, and separately the top 3 "
        "districts by Rape case count, this period."
    ),
    "Emerging District Trends": (
        "Districts driving the sharpest rise in Murder and Robbery specifically, "
        "comparing each district's latest complete week against its own Typical week."
    ),
    "Provincial Crime Concentration": (
        "The 5 districts with the largest share of every case reported anywhere in "
        "Punjab this period, combined."
    ),
}


# ═══════════════════════════════════════════════════════════════════════
# CSS — translated from the supplied design 1:1 (colours, type scale,
# component shapes); .trend-up/.trend-dn added so the imported
# _highlight_keywords() word-colouring (built for the other two reports)
# renders correctly here too, using this design's own red/green tokens.
# ═══════════════════════════════════════════════════════════════════════
CSS = f"""
@font-face{{font-family:'Playfair Display';font-weight:600 800;font-style:normal;font-display:swap;src:url({PLAYFAIR_FONT}) format('woff2')}}
:root{{--dk:#0c1b2a;--dk2:#162d45;--accent:#c8a45c;--accent2:#d4b76a;--red:#c0392b;--green:#27854a;--orange:#d9720a;--gray:#64748b;--line:#e2e0db}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'Segoe UI',system-ui,sans-serif;color:#1e293b;line-height:1.5;background:#fff}}
@page{{size:A4;margin:0}}
.page{{width:210mm;height:297mm;display:flex;flex-direction:column;padding:13mm 15mm 11mm 28mm;overflow:hidden;break-after:page;page-break-after:always;background:#fff}}
.page:last-child{{break-after:auto;page-break-after:auto}}
@media screen{{ body{{background:#DDD}} .page{{margin:14px auto;box-shadow:0 4px 24px rgba(0,0,0,.15)}} }}
.ph{{flex:0 0 auto;display:flex;align-items:center;gap:9px;padding-bottom:8px;border-bottom:2px solid var(--dk);margin-bottom:14px}}
.ph img.ph-csu{{height:34px;width:auto}}
.ph-spacer{{flex:1}}
.ph-right{{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;gap:2px}}
.ph-right img{{height:34px;width:auto}}
.ph-right .office{{text-align:center}}
.ph-right .office b{{display:block;font-size:7.2px;font-weight:800;color:var(--dk);letter-spacing:.2px;white-space:nowrap;line-height:1.15}}
.ph-right .office span{{display:block;font-size:6.4px;color:var(--gray);letter-spacing:.3px;text-transform:uppercase;white-space:nowrap;line-height:1.25}}
.pc{{flex:1 1 auto;overflow:hidden}}
.pf{{flex:0 0 auto;display:flex;justify-content:space-between;align-items:center;padding-top:7px;margin-top:10px;border-top:1px solid #cbd5e1;font-size:7.3px;color:var(--gray);letter-spacing:.3px;text-transform:uppercase}}
.pf b{{color:var(--dk);font-weight:700}}
.page.cover{{padding:0}}
.cover{{width:210mm;height:297mm;background:#fff;color:var(--dk);display:flex;flex-direction:column;position:relative;overflow:hidden}}
.cover-dots{{position:absolute;top:0;right:0;width:260px;height:260px;color:var(--accent);line-height:0}}
.cover-main{{flex:1;display:flex;flex-direction:column;align-items:center;text-align:center;justify-content:center;padding:30mm 10mm 5mm 20mm;position:relative;z-index:1}}
.cover-label{{font-size:10.5px;letter-spacing:2.6px;text-transform:uppercase;color:var(--accent);font-weight:700}}
.cover h1{{font-family:'Playfair Display',Georgia,serif;font-size:44px;font-weight:800;line-height:1.15;color:var(--dk);margin-bottom:18px}}
.cover-line{{width:160px;height:8px;background:var(--accent);margin:0 0 22px}}
.cover .subtitle{{font-size:13.5px;font-weight:700;color:var(--dk);opacity:.72;max-width:480px;line-height:1.55;margin-bottom:36px}}
.cover-meta{{display:flex;align-items:stretch;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:var(--gray)}}
.cover-meta .item{{display:flex;flex-direction:column;align-items:center;gap:9px;padding:0 28px}}
.cover-meta .div{{width:1px;background:var(--line);align-self:stretch;margin:3px 0}}
.cover-meta .icon-badge{{width:44px;height:44px;border-radius:50%;border:1.6px solid var(--accent);color:var(--accent);display:flex;align-items:center;justify-content:center}}
.cover-meta strong{{display:block;color:var(--dk);font-weight:800;font-size:12.5px;letter-spacing:.2px;text-transform:uppercase;white-space:nowrap;margin-bottom:2px}}
.cover-illustration{{flex:0 0 auto;position:relative;width:100%;z-index:0;line-height:0}}
.sec-title{{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:3px}}
.sec-title h2{{font-family:'Playfair Display',Georgia,serif;font-size:17px;font-weight:700;color:var(--dk)}}
.sec-title span{{font-size:9px;letter-spacing:2px;text-transform:uppercase;color:var(--gray)}}
.sec-desc{{font-size:10.5px;color:var(--gray);margin-bottom:4px;line-height:1.5}}
.insights-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:2px}}
.insight-card{{border:1px solid var(--line);border-radius:6px;padding:7px 15px 2px;display:flex;flex-direction:column;min-height:104px}}
.insight-card-head{{display:flex;align-items:center;gap:9px;margin-bottom:6px}}
.insight-num{{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;width:25px;height:25px;background:var(--dk);color:var(--accent);font-size:11.5px;font-weight:700;border-radius:50%}}
.insight-card h3{{font-size:13.5px;font-weight:700;color:var(--dk)}}
.insight-card p{{font-size:11px;color:#475569;line-height:1.44}}
.insight-method{{display:flex;gap:6px;align-items:flex-start;margin-top:auto;background:#F1F0EB;border-radius:5px;padding:6px 9px;font-size:8.4px;color:#64748b;line-height:1.38;color:var(--gray);height:80px;box-sizing:border-box}}
.insight-method.on-dark{{background:rgba(255,255,255,.08);color:rgba(255,255,255,.6)}}
.method-label{{font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:#475569;font-size:8.1px;margin-right:4px}}
.insight-method.on-dark .method-label{{color:rgba(255,255,255,.85)}}
.tag-up,.trend-up{{color:var(--red);font-weight:700}}
.tag-down,.trend-dn{{color:var(--green);font-weight:700}}
.tag-district{{font-weight:600;color:var(--dk)}}
.summary-box{{background:var(--dk);color:#fff;padding:12px 16px;border-radius:6px;font-size:12px;line-height:1.48;margin-bottom:14px}}
.summary-box strong{{color:var(--accent)}}
.summary-box strong.dir-up{{color:#e5605a}}
.summary-box strong.dir-dn{{color:#4ade80}}
.summary-box strong.dir-fl{{color:var(--accent)}}
table{{width:100%;border-collapse:collapse;font-size:10px;table-layout:fixed}}
thead{{background:var(--dk);color:#fff}}
th{{padding:4px 3px;font-weight:600;text-align:left;font-size:8px;letter-spacing:.3px;text-transform:uppercase;line-height:1.2}}
td{{padding:4px 3px;border-bottom:1px solid #eee;vertical-align:top}}
tbody tr:nth-child(even){{background:#faf9f7}}
.wk-count-tbl{{font-size:7.8px;table-layout:fixed}}
.wk-count-tbl th{{padding:6px 2px;font-size:7px;white-space:normal;line-height:1.25;position:relative}}
.wk-count-tbl td{{padding:6.5px 2px;color:#1e2126;position:relative}}
.wk-count-tbl .month-hdr{{text-align:center}}
.wk-count-tbl .month-split::before{{content:"";position:absolute;left:0;top:50%;transform:translateY(-50%);height:12px;width:1px;background:rgba(255,255,255,.35)}}
.wk-count-tbl tbody tr:hover{{background:#f1f0ea}}
.wk-count-tbl .wk-label{{font-weight:600;text-align:left;white-space:normal;line-height:1.22;font-size:7.8px;padding-right:4px;color:var(--dk)}}
.wk-count-tbl td.num{{font-variant-numeric:tabular-nums}}
.wk-count-tbl td.typ-col{{font-weight:700;color:var(--dk)}}
.wk-count-tbl td.tag-up{{color:var(--red)}}
.wk-count-tbl td.tag-down{{color:var(--green)}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.tbl-block{{margin-bottom:14px}}
.tbl-h{{font-size:11.5px;font-weight:700;color:var(--dk);margin-bottom:2px}}
.tbl-d{{font-size:9px;color:var(--gray);margin-bottom:6px}}
.an-block{{margin-top:16px;padding-top:14px;border-top:1px solid var(--line)}}
.an-title{{font-family:'Playfair Display',Georgia,serif;font-size:15px;font-weight:700;color:var(--dk);margin-bottom:10px}}
.an-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.an-card{{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--line);border-radius:7px;padding:12px 14px;background:#fbfaf7}}
.an-icon{{flex:0 0 auto;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff}}
.an-card.an-up .an-icon{{background:var(--red)}}
.an-card.an-dn .an-icon{{background:var(--green)}}
.an-card.an-vol .an-icon{{background:var(--dk)}}
.an-card.an-mix .an-icon{{background:var(--accent)}}
.an-h{{font-size:11px;font-weight:800;color:var(--dk);text-transform:uppercase;letter-spacing:.03em;margin-bottom:3px}}
.an-card p{{font-size:10.3px;color:#475569;line-height:1.48}}
.an-red{{color:var(--red)}}
.an-green{{color:var(--green)}}
.ra-page{{display:flex;flex-direction:column;height:100%}}
.ra-wrap{{flex:1;display:flex;align-items:center;border-top:3px solid var(--red);padding-top:22px;margin-top:6px}}
.ra-grid{{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.ra-card{{display:flex;flex-direction:column;border:1px solid var(--line);border-left:4px solid var(--line);border-radius:9px;padding:22px 24px;background:#fbfaf7}}
.ra-card.crit{{border-left-color:var(--red)}}
.ra-card.high{{border-left-color:var(--orange)}}
.ra-card-head{{display:flex;align-items:flex-start;gap:13px;margin-bottom:12px}}
.ra-icon{{flex:0 0 auto;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff}}
.ra-icon.crit{{background:var(--red)}}
.ra-icon.high{{background:var(--orange)}}
.ra-head-text{{flex:1;display:flex;flex-direction:column;gap:6px}}
.ra-head-text h4{{font-size:13.5px;font-weight:800;color:var(--dk);line-height:1.3}}
.ra-badge{{align-self:flex-start;font-size:7.6px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;padding:3.5px 9px;border-radius:10px;color:#fff;white-space:nowrap}}
.ra-badge.crit{{background:var(--red)}}
.ra-badge.high{{background:var(--orange)}}
.ra-card p{{font-size:10.8px;color:#475569;line-height:1.65;margin-bottom:14px}}
.ra-card p b{{color:var(--dk)}}
.ra-bars{{margin-top:auto;padding-top:14px}}
.ra-bar-row{{display:flex;align-items:center;gap:9px;margin-bottom:8px}}
.ra-bar-row:last-child{{margin-bottom:0}}
.ra-bar-label{{width:88px;flex:0 0 auto;font-size:9px;font-weight:700;color:var(--dk);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ra-bar-track{{flex:1;height:6.5px;background:#e9e7e1;border-radius:4px;overflow:hidden}}
.ra-bar-fill{{display:block;height:100%;border-radius:4px}}
.ra-bar-fill.crit{{background:var(--red)}}
.ra-bar-fill.high{{background:var(--orange)}}
.ra-bar-val{{width:42px;flex:0 0 auto;text-align:right;font-size:9px;color:var(--gray);font-variant-numeric:tabular-nums;font-weight:600}}
.chart-wrap{{border:1px solid var(--line);border-radius:6px;padding:8px 10px 4px;margin-bottom:20px}}
.chart-legend{{display:flex;align-items:center;gap:6px;font-size:8.3px;color:var(--gray);margin-top:2px}}
.chart-legend .dot{{width:7px;height:7px;border-radius:50%;display:inline-block}}
.crime-grid{{display:flex;flex-direction:column;gap:12px}}
.col-legend{{display:flex;gap:20px;flex-wrap:wrap;font-size:9px;color:var(--gray);margin-bottom:10px;padding:7px 11px;background:#faf9f7;border:1px solid var(--line);border-radius:5px}}
.col-legend b{{font-weight:700;color:var(--dk)}}
.col-legend .lg-dot{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle}}
.col-legend .lg-most .lg-dot{{background:var(--orange)}}
.col-legend .lg-chronic .lg-dot{{background:var(--red)}}
.col-legend .lg-fewest .lg-dot{{background:var(--green)}}
.crime-card{{border:1px solid var(--line);border-radius:6px;overflow:hidden}}
.crime-head{{display:flex;align-items:center;gap:10px;padding:9px 14px;background:#faf9f7;border-bottom:1px solid var(--line)}}
.crime-head h3{{font-size:13.5px;font-weight:700}}
.badge{{font-size:9.5px;font-weight:700;padding:3px 10px;border-radius:10px}}
.badge-up{{background:rgba(192,57,43,.1);color:var(--red)}}
.badge-down{{background:rgba(39,133,74,.1);color:var(--green)}}
.badge-flat{{background:rgba(100,116,139,.1);color:var(--gray)}}
.crime-body{{padding:11px 14px 13px}}
.crime-stats{{display:flex;gap:16px;font-size:9.3px;color:var(--gray);margin-bottom:9px;padding-bottom:8px;border-bottom:1px solid var(--line)}}
.crime-stats b{{color:var(--dk);font-weight:700}}
.cat-chart{{margin-bottom:9px}}
.crime-districts{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0;font-size:10px;margin-bottom:9px}}
.dist-col{{padding:0 12px}}
.dist-col:first-child{{padding-left:0}}
.dist-col:last-child{{padding-right:0}}
.dist-col+.dist-col{{border-left:1px solid var(--line)}}
.dist-col h4{{font-size:7.6px;text-transform:uppercase;letter-spacing:.4px;color:#fff;margin:0 0 6px;font-weight:700;padding:3px 7px;border-radius:4px;display:inline-block}}
.dist-col.most h4{{background:var(--orange)}}
.dist-col.chronic h4{{background:var(--red)}}
.dist-col.fewest h4{{background:var(--green)}}
.dist-row{{display:flex;justify-content:space-between;padding:1.5px 0}}
.dist-col.most .dist-row strong{{color:var(--orange)}}
.dist-col.chronic .dist-row strong{{color:var(--red)}}
.dist-col.fewest .dist-row strong{{color:var(--green)}}
.rising{{font-size:9.8px;color:#475569;line-height:1.5}}
.rising b{{color:var(--dk)}}
.district-tbl th{{font-size:7px;padding:6px 3px;white-space:normal;line-height:1.3;vertical-align:middle}}
.district-tbl td{{font-size:8px;padding:3px 2px}}
.district-tbl td.num, .district-tbl th.num{{text-align:center}}
.district-tbl .dn{{font-weight:600;color:var(--dk)}}
.district-tbl .pct-max{{background:rgba(192,57,43,.12);color:var(--red);font-weight:800;border-radius:3px}}
"""


# ═══════════════════════════════════════════════════════════════════════
# Small helpers
# ═══════════════════════════════════════════════════════════════════════
def _page_header():
    return (
        f'<div class="ph"><img class="ph-csu" src="{CSU_LOGO}"><div class="ph-spacer"></div>'
        f'<div class="ph-right"><img src="{GOVT_LOGO}"><div class="office">'
        f"<b>Chief Minister's Office</b><span>Additional Secretary<br/>(Law &amp; Order)</span></div></div></div>"
    )


def _page_footer(page_num):
    return (
        f'<div class="pf"><span><b>Crime Analytics Punjab</b></span>'
        f'<span>Page {page_num} of __TOTAL__</span></div>'
    )


def _wrap(content_html, page_num):
    return f'<section class="page">{_page_header()}<div class="pc">{content_html}</div>{_page_footer(page_num)}</section>'


def _trend_chart_svg(weekly):
    """Line chart for the overall daily-average weekly trend.

    Safely handles empty weekly data so PDF generation does not fail
    when there are no trend points for the selected date range.
    """
    CW, CH = 700, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 8, 8, 16, 22
    plot_w = CW - PAD_L - PAD_R
    plot_h = CH - PAD_T - PAD_B

    # ---------------------------------------------------------
    # No weekly data
    # ---------------------------------------------------------
    if not weekly:
        return (
            f'<svg viewBox="0 0 {CW} {CH}" width="100%" height="{CH}" '
            f'xmlns="http://www.w3.org/2000/svg">'
            f'<text x="{CW / 2:.1f}" y="{CH / 2:.1f}" '
            f'font-size="12" fill="#64748b" text-anchor="middle">'
            f'No trend data available'
            f'</text>'
            f'</svg>'
        )

    # ---------------------------------------------------------
    # Calculate daily averages
    # ---------------------------------------------------------
    avgs = [
        round(
            w.get("week_total", 0) / w.get("n_days", 0),
            1
        )
        if w.get("n_days")
        else 0
        for w in weekly
    ]

    # ---------------------------------------------------------
    # Calculate chart range
    # ---------------------------------------------------------
    lo_v = min(avgs) * 0.85 if avgs else 0
    hi_v = max(avgs) * 1.15 if avgs else 1

    # Avoid zero-height range when all values are identical.
    if hi_v == lo_v:
        hi_v = lo_v + 1

    # ---------------------------------------------------------
    # Convert data point to SVG coordinates
    # ---------------------------------------------------------
    def xy(i, v):
        x = PAD_L + (
            plot_w * i / max(len(avgs) - 1, 1)
        )

        y = PAD_T + plot_h * (
            1 - (v - lo_v) / (hi_v - lo_v)
        )

        return x, y

    # ---------------------------------------------------------
    # Generate points
    # ---------------------------------------------------------
    pts = [
        xy(i, v)
        for i, v in enumerate(avgs)
    ]

    # Extra safety
    if not pts:
        return (
            f'<svg viewBox="0 0 {CW} {CH}" width="100%" height="{CH}" '
            f'xmlns="http://www.w3.org/2000/svg">'
            f'<text x="{CW / 2:.1f}" y="{CH / 2:.1f}" '
            f'font-size="12" fill="#64748b" text-anchor="middle">'
            f'No trend data available'
            f'</text>'
            f'</svg>'
        )

    # ---------------------------------------------------------
    # Line path
    # ---------------------------------------------------------
    path_d = (
        "M "
        + " L ".join(
            f"{x:.1f},{y:.1f}"
            for x, y in pts
        )
    )

    # ---------------------------------------------------------
    # Filled area under line
    # ---------------------------------------------------------
    baseline_y = PAD_T + plot_h

    area_d = (
        path_d
        + f" L {pts[-1][0]:.1f},{baseline_y}"
        + f" L {pts[0][0]:.1f},{baseline_y}"
        + " Z"
    )

    # ---------------------------------------------------------
    # Gold data-point markers
    # ---------------------------------------------------------
    dots = "".join(
        f'<circle '
        f'cx="{x:.1f}" '
        f'cy="{y:.1f}" '
        f'r="3.1" '
        f'fill="#c8a45c" '
        f'stroke="#0c1b2a" '
        f'stroke-width="1"/>'
        for x, y in pts
    )

    # ---------------------------------------------------------
    # Week labels + values
    # ---------------------------------------------------------
    labels = "".join(
        f'<text '
        f'x="{pts[i][0]:.1f}" '
        f'y="{CH - 6}" '
        f'font-size="7" '
        f'fill="#64748b" '
        f'text-anchor="middle">'
        f'W{int(w.get("week_num", i + 1))}'
        f'{"*" if w.get("n_days", 0) < 7 else ""}'
        f'</text>'

        f'<text '
        f'x="{pts[i][0]:.1f}" '
        f'y="{pts[i][1] - 8:.1f}" '
        f'font-size="7.3" '
        f'fill="#0c1b2a" '
        f'font-weight="700" '
        f'text-anchor="middle">'
        f'{avgs[i]}'
        f'</text>'

        for i, w in enumerate(weekly)
    )

    # ---------------------------------------------------------
    # Final SVG
    # ---------------------------------------------------------
    return (
        f'<svg '
        f'viewBox="0 0 {CW} {CH}" '
        f'width="100%" '
        f'height="{CH}" '
        f'xmlns="http://www.w3.org/2000/svg">'

        f'<path '
        f'd="{area_d}" '
        f'fill="#0c1b2a" '
        f'opacity="0.07"/>'

        f'<path '
        f'd="{path_d}" '
        f'fill="none" '
        f'stroke="#0c1b2a" '
        f'stroke-width="2"/>'

        f'{dots}'
        f'{labels}'

        f'</svg>'
    )

# ═══════════════════════════════════════════════════════════════════════
# Page 1: Cover
# ═══════════════════════════════════════════════════════════════════════
def _cover_page(data_period, reporting_day, n_days):
    return f"""
<section class="page cover">
<div class="cover-dots">{_COVER_DOTS_SVG}</div>
<div class="cover-main">
<div style="display:flex;align-items:center;gap:18px;margin-bottom:10px">
<img src="{GOVT_LOGO}" style="height:85px;width:auto">
<div style="width:1px;height:70px;background:var(--line)"></div>
<img src="{CSU_LOGO}" style="height:70px;width:auto;object-fit:contain">
</div>
<div class="cover-label" style="margin-top:25px;margin-bottom:0px;">Chief Minister's Crime Surveillance Unit</div>
<div class="cover-label" style="margin-bottom:20px;">Government of the Punjab</div>
<h1 style="margin-top:50px;">Crime Analytics Punjab</h1>
<div class="cover-line"></div>
<p class="subtitle">Comparative Analysis of Provincial Crime Data</p>
<div class="cover-meta">
<div class="item"><div class="icon-badge">{_ICON_CALENDAR}</div><span><strong>{esc(data_period)}</strong>Reporting Period ({n_days} days)</span></div>
<div class="div"></div>
<div class="item"><div class="icon-badge">{_ICON_CALENDAR}</div><span><strong>{esc(reporting_day)}</strong>Issue Date</span></div>
<div class="div"></div>
<div class="item"><div class="icon-badge">{_ICON_SHIELD}</div><span><strong>Restricted</strong>Classification</span></div>
</div>
</div>
<div>{_CSU_SKETCH}</div>
<div class="cover-illustration">{_COVER_BOTTOM_BAR_SVG}</div>
</section>
"""


def _back_cover_page():
    """Closing bookend to the front cover -- same quiet visual language
    (dot pattern, navy/gold bottom bar), no page content repeated, just the
    issuing body and data-source attribution."""
    return f"""
<section class="page cover">
<div class="cover-dots">{_COVER_DOTS_SVG}</div>
<div class="cover-main">
<div style="display:flex;align-items:center;gap:18px;margin-bottom:22px">
<img src="{GOVT_LOGO}" style="height:66px;width:auto">
<div style="width:1px;height:48px;background:var(--line)"></div>
<img src="{CSU_LOGO}" style="height:48px;width:auto;object-fit:contain">
</div>
<div class="cover-label" style="font-size:16px;font-weight:bold;letter-spacing:0px;">Chief Minister's</div>
<div class="cover-label" style="font-size:26px;font-weight:bold;letter-spacing:0px;">Crime Surveillance Unit</div>
<p style="font-size:20px; margin-top:30px;">Government of the Punjab</p>
<div class="cover-line" style="margin-top:20px;width:100px;"></div>
<p class="subtitle" style="font-size:12px;max-width:400px"></p>
</div>
<div class="cover-illustration" >{_COVER_BOTTOM_BAR_SVG}</div>
</section>
"""


# ═══════════════════════════════════════════════════════════════════════
# Page 2: Key Insights — same data/logic as the other two Crime Analytics
# reports (imported), rendered as the numbered card grid + closing summary
# box from the supplied design instead of the callout-list style.
# ═══════════════════════════════════════════════════════════════════════
def _key_insights_page(start_date, end_date, weekly_context, page_num):
    insights = _build_default_insights(start_date, end_date, weekly_context)
    grid_items, closing = (insights[:-1], insights[-1]) if insights else ([], None)

    def method_box(tag, on_dark=False):
        note = INSIGHT_METHODOLOGY.get(tag)
        if not note:
            return ""
        cls = "insight-method on-dark" if on_dark else "insight-method"
        return (
            f'<div class="{cls}">{_METHOD_ICON}'
            f'<div><span class="method-label">Methodology</span>{note}</div></div>'
        )

    cards = "".join(
        f'<div class="insight-card"><div class="insight-card-head"><div class="insight-num">{i + 1}</div>'
        f'<h3>{esc(tag)}</h3></div><p style="margin-bottom:10px">{_highlight_keywords(text)}</p>{method_box(tag)}</div>'
        for i, (color, tag, text) in enumerate(grid_items)
    )
    summary = ""
    if closing:
        _, tag, text = closing
        summary = f'<div class="summary-box"><strong>{esc(tag)}:</strong> {_highlight_keywords(text)}</div>'

    content = f"""
<div class="sec-title"><h2>Key Insights</h2><span>Section 01</span></div>
<p class="sec-desc">Crime situation at a glance</p>
<div class="insights-grid">{cards}</div>
{summary}
"""
    return _wrap(content, page_num)


# ═══════════════════════════════════════════════════════════════════════
# Page 3: Crime Trend Overview — Week-by-Week Case Count (all 14
# categories, calendar-locked weeks) + the weekly rising/falling table,
# now WITH the line chart the supplied design was missing.
# ═══════════════════════════════════════════════════════════════════════
# The simple 5-column rising/falling table is still capped to a trailing
# window -- it's a fixed one-page section with no doc-page.js
# auto-pagination, and would eventually overflow as weeks keep
# accumulating for years. The Week-by-Week Case Count table below is NOT
# capped: every week from the start of the data period is shown, with
# column widths computed to fit however many there are (see colgroup in
# _weekly_case_count_page), since the whole point of that table is to see
# the complete May-onward history at a glance.
MAX_WEEKS_SHOWN = 20


def _week_num_label(label):
    """'May Wk1' -> 'Week 1' -- the month itself is shown once in its own
    header row (grouped via colspan), so the per-column label only needs
    the week number, not a repeat of the month name."""
    return label.split(" ")[1].replace("Wk", "Week ")


# Portrait page, same as every other page in the report -- no rotation.
# Full month/week labels still fit because the month name is shown ONCE
# per month (spanning that month's weeks via colspan) instead of being
# repeated in every single week column.
CONTENT_W = 210 - 28 - 15  # mm -- 210mm page - 28mm left (binding) - 15mm right margin


def _weekly_case_count_page(start_date, end_date, page_num):
    weeks, per_category = _weekly_by_category_data(start_date, end_date)
    complete_idxs = [i for i, w in enumerate(weeks) if w["is_complete"]]
    latest_idx = complete_idxs[-1] if complete_idxs else None

    LABEL_W = 20
    n_data_cols = len(weeks) + 2  # weeks + Typical + Trend
    col_w = (CONTENT_W - LABEL_W) / max(n_data_cols, 1)
    colgroup = f'<col style="width:{LABEL_W}mm">' + f'<col style="width:{col_w:.2f}mm">' * n_data_cols

    # Group consecutive weeks by month so each month name is written once,
    # spanning its own weeks, instead of being repeated in every column.
    month_groups = []
    month_start_idxs = set()
    for i, w in enumerate(weeks):
        month = w["label"].split(" ")[0]
        if month_groups and month_groups[-1][0] == month:
            month_groups[-1][1] += 1
        else:
            month_groups.append([month, 1])
            if i > 0:
                month_start_idxs.add(i)
    month_header = "".join(
        f'<th colspan="{count}" class="month-hdr{" month-split" if gi > 0 else ""}">{month}</th>'
        for gi, (month, count) in enumerate(month_groups)
    )
    week_num_header = "".join(
        f'<th class="num{" month-split" if i in month_start_idxs else ""}">{_week_num_label(w["label"])}</th>'
        for i, w in enumerate(weeks)
    )

    trs = ""
    cat_stats = []
    for col, label in ALL_CATEGORIES:
        series = per_category[col]
        complete_vals = [series[i] for i in complete_idxs]
        typical = sum(complete_vals) / len(complete_vals) if complete_vals else 0
        total = sum(v for v in series if v is not None)
        if latest_idx is not None:
            trend_cls, trend_label = _week_trend_badge(series[latest_idx], typical)
            latest_val = series[latest_idx]
            pct = (latest_val - typical) / typical * 100 if typical else 0
        else:
            trend_cls, trend_label, pct = "fl", "&#9668;&#9658;0%", 0
        badge_css = {"up": "tag-up", "dn": "tag-down", "fl": ""}[trend_cls]
        cells = "".join(f'<td class="num">{"-" if v is None else v}</td>' for v in series)
        trs += (
            f'<tr><td class="wk-label">{SHORT_LABELS[col]}</td>{cells}'
            f'<td class="num typ-col">{typical:.1f}</td><td class="num {badge_css}">{trend_label}</td></tr>'
        )
        cat_stats.append(dict(label=label, total=total, typical=typical, pct=pct, trend_cls=trend_cls))

    analysis_html = _weekly_case_count_analysis()

    content = f"""
<div class="sec-title"><h2>Crime Trend Overview</h2><span>Section 02</span></div>
<p class="sec-desc">Typical is the average of every complete week on file. We compare the most recent complete week against Typical to decide whether each crime is rising or falling.</p>
<div class="tbl-block">
<div class="tbl-h">Week-by-Week Case Count</div>
<div class="tbl-d">Every calendar-month week from the start of the data period (week 1 = days 1&ndash;7, etc). * marks a partial week (fewer than 7 days on file).</div>
<table class="wk-count-tbl">
<colgroup>{colgroup}</colgroup>
<thead>
<tr><th rowspan="2">Crime Category</th>{month_header}<th rowspan="2" class="num typ-col">Typ.</th><th rowspan="2" class="num">Trend</th></tr>
<tr>{week_num_header}</tr>
</thead>
<tbody>{trs}</tbody>
</table>
</div>
{analysis_html}
"""
    return _wrap(content, page_num)


def _weekly_case_count_analysis():
    """Four-point read of the Week-by-Week table above, filling what would
    otherwise be blank space at the bottom of the page. Hand-authored by the
    data analyst each reporting cycle rather than computed -- a human read of
    which moves actually matter reads better than a purely statistical pick
    (e.g. Dacoity's drop from a small base still counts as a genuine, worth-
    noting improvement)."""
    bullets = [
        (
            "up",
            "Emerging Concern",
            '<b>Snatching/Jhappata</b>: 160 cases, <b class="an-red">5.9% higher</b> than Week-2 '
            'and <b class="an-red">22.7% above</b> the typical level.'
        ),
        (
            "dn",
            "Improving Trend",
            '<b>Dacoity</b>: 2 cases, <b class="an-green">47.4% below</b> the typical weekly level.'
        ),
        (
            "vol",
            "Highest Reporting",
            '<b>Robbery</b>: 339 cases; <b class="an-green">9.1% lower</b> than Week-2 but '
            '<b class="an-red">18.4% above</b> the typical level.'
        ),
        (
            "mix",
            "Overall Trend",
            '<b class="an-red">7</b> categories remained above typical levels, '
            '<b class="an-green">6</b> below, while <b>Rape</b> remained stable.'
        ),
    ]

    icons = {
        "up": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17 L10 11 L14 15 L20 7"/><path d="M14 7 H20 V13"/></svg>',
        "dn": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7 L10 13 L14 9 L20 17"/><path d="M14 17 H20 V11"/></svg>',
        "vol": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="4" height="10"/><rect x="10" y="5" width="4" height="15"/><rect x="16" y="13" width="4" height="7"/></svg>',
        "mix": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5 V12 L15 14.5"/></svg>',
    }
    cards = "".join(
        f'<div class="an-card an-{kind}"><div class="an-icon">{icons[kind]}</div>'
        f'<div><div class="an-h">{esc(title)}</div><p>{body}</p></div></div>'
        for kind, title, body in bullets
    )
    return f"""
<div class="an-block">
<div class="an-title">Quick Analysis</div>
<div class="an-grid">{cards}</div>
</div>
"""


def _rising_falling_page(start_date, end_date, page_num):
    weekly_full = _weekly_trend(start_date, end_date)
    truncated = len(weekly_full) > MAX_WEEKS_SHOWN
    weekly = weekly_full[-MAX_WEEKS_SHOWN:] if truncated else weekly_full
    avgs_full = [round(w["week_total"] / w["n_days"], 1) if w["n_days"] else 0 for w in weekly_full]
    avgs = avgs_full[-MAX_WEEKS_SHOWN:] if truncated else avgs_full
    offset = len(weekly_full) - len(weekly)

    week_rows = ""
    for i, w in enumerate(weekly):
        full_i = i + offset
        badge = _change_badge(avgs_full[full_i], avgs_full[full_i - 1]) if full_i > 0 else '<span style="color:var(--gray)">start</span>'
        badge = badge.replace('class="trend-up"', 'class="tag-up"').replace('class="trend-dn"', 'class="tag-down"').replace('class="trend-fl"', '')
        partial = "*" if w["n_days"] < 7 else ""
        week_rows += (
            f'<tr><td style="font-weight:600">Week {int(w["week_num"])}{partial}</td><td>{w["week_start"].strftime("%d-%m-%Y")} to {w["week_end"].strftime("%d-%m-%Y")}</td>'
            f'<td class="num">{w["week_total"]}</td><td class="num">{avgs[i]}</td><td class="num">{badge}</td></tr>'
        )
    typical_avg, latest_avg, overall_pct, direction = _typical_vs_latest(weekly_full)
    dir_cls = {"climbing": "dir-up", "falling": "dir-dn"}.get(direction, "dir-fl")
    complete_weeks = [w for w in weekly_full if w["n_days"] >= 7]
    latest_label = f'Week {int(complete_weeks[-1]["week_num"])}' if complete_weeks else "n/a"
    note = f' Showing the most recent {MAX_WEEKS_SHOWN} of {len(weekly_full)} weeks on file.' if truncated else ""

    chart_svg = _trend_chart_svg(weekly)

    content = f"""
<div class="sec-title"><h2>Crime Trend Overview</h2><span>Section 02 (cont.)</span></div>
<div class="tbl-block">
<div class="tbl-h">Is Crime Rising or Falling: Daily Average</div>
<div class="tbl-d">Average cases per day, every recorded category combined, vs the previous complete week.{note}</div>
<div class="chart-wrap">{chart_svg}<div class="chart-legend"><span class="dot" style="background:#c8a45c"></span>Daily average, all categories combined. Gold marker = week value; label = weeks from data start (Week 1 onward)</div></div>
<table style="font-size:8.7px">
<thead><tr><th>Week</th><th>Dates</th><th class="num">Total</th><th class="num">Avg/Day</th><th class="num">Change</th></tr></thead>
<tbody>{week_rows}</tbody>
</table>
</div>
<div class="summary-box"><strong>Overall Direction:</strong> The most recent complete week on file ({latest_label}) averaged {latest_avg} cases per day, against a typical week of {typical_avg}. The province is <strong class="{dir_cls}">{direction} ({overall_pct:+.0f}% vs typical)</strong>.</div>
"""
    return _wrap(content, page_num)


# ═══════════════════════════════════════════════════════════════════════
# Pages 4+: Detail of Each Crime — 3 cards per page, same data as
# crime_analytics_monthly.py's per-category rising-district detection.
# ═══════════════════════════════════════════════════════════════════════
def _category_chart_svg(weeks, series, trend_cls, typical):
    """Compact sparkline-style weekly trend for one crime category, shown
    inside its detail card -- the per-crime chart the supplied design
    didn't have, alongside the province-wide one added to Section 02. A
    dashed reference line marks the typical (average) weekly level so the
    average is visible on the chart itself, not just in the table below."""
    idxs = [i for i, w in enumerate(weeks) if w["has_data"]]
    if len(idxs) < 2:
        return ""
    vals = [series[i] for i in idxs]
    labels = [weeks[i]["label"] for i in idxs]
    line_color = {"up": "#c0392b", "dn": "#27854a", "fl": "#0c1b2a"}[trend_cls]

    CW, CH = 700, 96
    PAD_L, PAD_R, PAD_T, PAD_B = 22, 46, 18, 16
    plot_w, plot_h = CW - PAD_L - PAD_R, CH - PAD_T - PAD_B
    # Typical is folded into the range so the average line is never clipped
    # even if it falls outside the visible (has_data) weeks' own min/max.
    range_vals = vals + [typical]
    lo_v, hi_v = min(range_vals) * 0.85, max(range_vals) * 1.15
    if hi_v == lo_v:
        hi_v = lo_v + 1

    def xy(i, v):
        x = PAD_L + (plot_w * i / max(len(vals) - 1, 1))
        y = PAD_T + plot_h * (1 - (v - lo_v) / (hi_v - lo_v))
        return x, y

    pts = [xy(i, v) for i, v in enumerate(vals)]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = path_d + f" L {pts[-1][0]:.1f},{PAD_T+plot_h} L {pts[0][0]:.1f},{PAD_T+plot_h} Z"
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="{line_color}"/>' for x, y in pts)
    # Numeric value above every point (matches the Section 02 province-wide
    # chart's style), clamped so it never renders above the SVG's own top edge.
    value_labels = "".join(
        f'<text x="{pts[i][0]:.1f}" y="{max(pts[i][1] - 7, 8):.1f}" font-size="6.6" fill="{line_color}" '
        f'font-weight="700" text-anchor="middle">{vals[i]:,}</text>'
        for i in range(len(idxs))
    )
    # Full week label under every point -- no abbreviating into a single
    # dot-joined word and no skipping alternate weeks.
    tick_labels = "".join(
        f'<text x="{pts[i][0]:.1f}" y="{CH-4}" font-size="6" fill="#000" font-weight="bold" text-anchor="middle">{esc(labels[i])}</text>'
        for i in range(len(idxs))
    )
    avg_y = PAD_T + plot_h * (1 - (typical - lo_v) / (hi_v - lo_v))
    # The last point's own value label sits right where the "Avg N" label
    # starts (same right-hand edge of the chart) -- nudge the avg label
    # vertically clear of it whenever the two would otherwise land on the
    # same row.
    last_value_y = pts[-1][1] - 7
    avg_text_y = avg_y + 3
    if abs(avg_text_y - last_value_y) < 10:
        avg_text_y = last_value_y + 10 if avg_y >= pts[-1][1] else last_value_y - 10
    avg_line = (
        f'<line x1="{PAD_L}" y1="{avg_y:.1f}" x2="{CW-PAD_R}" y2="{avg_y:.1f}" '
        f'stroke="#94a3b8" stroke-width="1" stroke-dasharray="3,3"/>'
        f'<text x="{CW-PAD_R+5}" y="{avg_text_y:.1f}" font-size="9" fill="#64748b" font-weight="700">Avg {typical:.0f}</text>'
    )
    return (
        f'<svg viewBox="0 0 {CW} {CH}" width="100%" height="{CH}">'
        f'<path d="{area_d}" fill="{line_color}" opacity="0.06"/>'
        f'{avg_line}'
        f'<path d="{path_d}" fill="none" stroke="{line_color}" stroke-width="1.6"/>{dots}{value_labels}{tick_labels}</svg>'
    )


def _crime_card(col, label, start_date, end_date, weeks, per_category, complete_idxs, latest_idx, template):
    maxrows, minrows = _minmax5(col, start_date, end_date)
    chronicrows = _chronic5(col, start_date, end_date)

    series = per_category[col]
    complete_vals = [series[i] for i in complete_idxs]
    typical = sum(complete_vals) / len(complete_vals) if complete_vals else 0
    total = sum(v for v in series if v is not None)
    n_days = (end_date - start_date).days + 1
    if latest_idx is not None:
        trend_cls, trend_label = _week_trend_badge(series[latest_idx], typical)
    else:
        trend_cls, trend_label = "fl", "&#9668;&#9658; 0%"
    badge_css = {"up": "badge-up", "dn": "badge-down", "fl": "badge-flat"}[trend_cls]
    heading_color = "style=\"color:var(--red)\"" if trend_cls == "up" else ("style=\"color:var(--green)\"" if trend_cls == "dn" else "")

    def col3(rows, value_key, suffix=""):
        return "".join(f'<div class="dist-row"><span>{esc(r["name_en"])}</span><strong>{r[value_key]:,}{suffix}</strong></div>' for r in rows[:3])

    rising = _rising_districts(col, complete_idxs, latest_idx, template, start_date, end_date)
    if rising:
        rising_text = ", ".join(f"{esc(dname)} (+{dpct:.0f}%)" for dname, dval, dpct, dtyp in rising[:5])
    else:
        rising_text = "No district shows a meaningful rise in this category for the latest complete week."

    stats_html = (
        '<div class="crime-stats">'
        f'<span>Total: <b>{total:,}</b> cases over <b>{n_days}</b> days</span>'
        f'<span>Weekly average: <b>{typical:.1f}</b> cases</span>'
        '</div>'
    )
    chart_svg = _category_chart_svg(weeks, series, trend_cls, typical)
    chart_html = f'<div class="cat-chart">{chart_svg}</div>' if chart_svg else ""

    return f"""
<div class="crime-card"><div class="crime-head"><h3 {heading_color}>{esc(label)}</h3><span class="badge {badge_css}">{trend_label}</span></div><div class="crime-body">
{stats_html}
{chart_html}
<div class="crime-districts">
<div class="dist-col most"><h4>Most Cases</h4>{col3(maxrows, "v")}</div>
<div class="dist-col chronic"><h4>Chronic</h4>{col3(chronicrows, "days_with_cases", " days")}</div>
<div class="dist-col fewest"><h4>Fewest</h4>{col3(minrows, "v")}</div>
</div>
<div class="rising"><b>Rising:</b> {rising_text}</div>
</div></div>
"""


def _detail_pages(start_date, end_date, first_page_num):
    weeks, per_category = _weekly_by_category_data(start_date, end_date)
    complete_idxs = [i for i, w in enumerate(weeks) if w["is_complete"]]
    latest_idx = complete_idxs[-1] if complete_idxs else None
    template = _week_template(end_date)

    cards = [
        _crime_card(col, label, start_date, end_date, weeks, per_category, complete_idxs, latest_idx, template)
        for col, label in CARD_CATEGORIES
    ]

    note = (
        '<div style="margin-top:16px" class="summary-box"><strong>Note:</strong> '
        "Dacoity/Robbery with Rape is not shown as its own card (0&ndash;1 cases per week throughout the period); "
        "it is reported in the Week-by-Week Case Count table only.</div>"
    )
    legend = (
        '<div class="col-legend">'
        '<span class="lg-most"><span class="lg-dot"></span><b>Most Cases</b> highest total reported this period</span>'
        '<span class="lg-chronic"><span class="lg-dot"></span><b>Chronic</b> most distinct days with at least one case reported</span>'
        '<span class="lg-fewest"><span class="lg-dot"></span><b>Fewest</b> lowest total reported this period</span>'
        '</div>'
    )

    pages = []
    CARDS_PER_PAGE = 2
    groups = [cards[i:i + CARDS_PER_PAGE] for i in range(0, len(cards), CARDS_PER_PAGE)]
    for gi, group in enumerate(groups):
        is_last = gi == len(groups) - 1
        content = (
            f'<div class="sec-title"><h2>Detail of Each Crime</h2><span>Section 03{" (cont.)" if gi > 0 else ""}</span></div>'
            + ('<p class="sec-desc">Weekly trend, highest/lowest/most chronic districts, and which districts are driving the rise, for every recorded category.</p>' if gi == 0 else "")
            + legend
            + f'<div class="crime-grid">{"".join(group)}</div>'
            + (note if is_last else "")
        )
        pages.append(_wrap(content, first_page_num + gi))
    return "".join(pages), len(groups)


# ═══════════════════════════════════════════════════════════════════════
# Final page: Each District's Crime Mix & Contribution to Punjab
# ═══════════════════════════════════════════════════════════════════════
def _composition_page(start_date, end_date, page_num):
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
    # "Other" is built from every category outside the 6 headline ones, which
    # includes Road Accident Casualties and Religious Issues -- so Total here
    # has to count all 14 categories too (all_crime_sum_sql), not just the 12
    # "real crime" ones, or the seven columns would add up to more than 100%.
    rows = db.query(sql, (start_date, end_date))
    grand_total = sum(r["total"] for r in rows) or 1

    # Per-column percentage first, so the highest-percentage district in each
    # of the four sensitive categories can be picked out and highlighted --
    # a district can be small in raw terms yet still be where that crime is
    # most concentrated relative to its own caseload.
    pct_rows = []
    for r in rows:
        t = r["total"] or 1
        pct_rows.append(dict(
            r, t=t,
            murder_pct=r["murder"] / t * 100, robbery_pct=r["robbery"] / t * 100,
            child_abuse_pct=r["child_abuse"] / t * 100, rape_pct=r["rape"] / t * 100,
            gang_rape_pct=r["gang_rape"] / t * 100, snatching_pct=r["snatching"] / t * 100,
            other_pct=r["other"] / t * 100,
        ))
    HIGHLIGHT_COLS = ("murder_pct", "rape_pct", "gang_rape_pct", "child_abuse_pct")
    max_idx = {col: max(range(len(pct_rows)), key=lambda i: pct_rows[i][col]) for col in HIGHLIGHT_COLS} if pct_rows else {}

    def cell(i, col, label_pct):
        cls = "num pct-max" if max_idx.get(col) == i else "num"
        return f'<td class="{cls}">{label_pct:.1f}%</td>'

    trs = ""
    for i, r in enumerate(pct_rows):
        trs += (
            f'<tr><td>{i+1}</td><td class="dn">{esc(r["name_en"])}</td>'
            f'{cell(i, "murder_pct", r["murder_pct"])}'
            f'<td class="num">{r["robbery_pct"]:.1f}%</td>'
            f'{cell(i, "child_abuse_pct", r["child_abuse_pct"])}'
            f'{cell(i, "rape_pct", r["rape_pct"])}'
            f'{cell(i, "gang_rape_pct", r["gang_rape_pct"])}'
            f'<td class="num">{r["snatching_pct"]:.1f}%</td>'
            f'<td class="num">{r["other_pct"]:.1f}%</td>'
            f'<td class="num" style="font-weight:700">{r["total"]}</td>'
            f'<td class="num" style="font-weight:700">{r["total"]/grand_total*100:.1f}%</td></tr>'
        )

    content = f"""
<div class="sec-title"><h2>Each District's Crime Mix And Contribution To Punjab</h2><span>Section 04</span></div>
<p class="sec-desc">The first seven columns show the category-wise composition of each district's reported cases, with each row totaling 100%. "Other" includes all remaining categories, including Road Accident Casualties and Religious Issues. The final column shows each district's share of total reported cases across Punjab. Highlighted cells identify the district with the highest proportion of its own caseload attributed to Murder, Rape, Gang Rape or Child Abuse.</p>
<table class="district-tbl">
<thead><tr><th style="width:4%">#</th><th style="width:18%">District</th><th class="num" style="width:8%">Murder</th><th class="num" style="width:8%">Robbery</th><th class="num" style="width:8%">Child<br/>Abuse</th><th class="num" style="width:8%">Rape</th><th class="num" style="width:8%">Gang<br/>Rape</th><th class="num" style="width:8%">Snatching/<br/>Jhappata</th><th class="num" style="width:8%">Other</th><th class="num" style="width:10%">Total</th><th class="num" style="width:12%">% of<br/>Punjab</th></tr></thead>
<tbody>{trs}</tbody>
</table>
"""
    return _wrap(content, page_num)


# ═══════════════════════════════════════════════════════════════════════
# Final page: Requires Attention — 4 CM-level priority callouts, computed
# from the period's own case totals, trend concentration and which
# districts are driving each one (unlike the hand-authored Quick Analysis
# section on page 3, these are derived straight from the DB every run).
# ═══════════════════════════════════════════════════════════════════════
def _requires_attention_page(start_date, end_date, page_num):
    n_days = (end_date - start_date).days + 1

    totals = db.query(f"""
        SELECT
          COALESCE(SUM(c.child_abuse),0) AS child_abuse,
          COALESCE(SUM(c.rape),0) AS rape, COALESCE(SUM(c.gang_rape),0) AS gang_rape,
          COALESCE(SUM(c.snatching_jhappata),0) AS snatching,
          COALESCE(SUM(c.robbery),0) AS robbery
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
    """, (start_date, end_date))[0]

    ca_chronic = _chronic5("child_abuse", start_date, end_date)[:3]

    caw_rows = db.query(f"""
        SELECT d.name_en, SUM(c.rape + c.gang_rape) v
        FROM crime_daily c JOIN districts d ON d.id = c.district_id
        WHERE {DISTRICT_FILTER_SQL} AND c.report_date BETWEEN %s AND %s
        GROUP BY d.name_en ORDER BY v DESC, d.name_en ASC LIMIT 3
    """, (start_date, end_date))

    sn_max, _ = _minmax5("snatching_jhappata", start_date, end_date)
    rb_max, _ = _minmax5("robbery", start_date, end_date)
    rb_days_by_name = {r["name_en"]: r["days_with_cases"] for r in _chronic5("robbery", start_date, end_date)}

    caw_total = totals["rape"] + totals["gang_rape"]
    sn_top3 = sn_max[:3]
    sn_top3_pct = sum(r["v"] for r in sn_top3) / totals["snatching"] * 100 if totals["snatching"] else 0
    rb_top3 = rb_max[:3]
    rb_top3_pct = sum(r["v"] for r in rb_top3) / totals["robbery"] * 100 if totals["robbery"] else 0
    rb_top3_min_days = min((rb_days_by_name.get(r["name_en"], 0) for r in rb_top3), default=0)

    def dl(rows):
        return ", ".join(f'<b>{esc(r["name_en"])}</b> ({r["v"]:,})' for r in rows)

    def cl(rows):
        return ", ".join(f'<b>{esc(r["name_en"])}</b> ({r["days_with_cases"]} days, {r["total"]:,} cases)' for r in rows)

    def bars(rows, value_key, sev):
        max_v = rows[0][value_key] if rows else 1
        rows_html = "".join(
            f'<div class="ra-bar-row"><span class="ra-bar-label">{esc(r["name_en"])}</span>'
            f'<span class="ra-bar-track"><span class="ra-bar-fill {sev}" '
            f'style="width:{(r[value_key] / max_v * 100 if max_v else 0):.0f}%"></span></span>'
            f'<span class="ra-bar-val">{r[value_key]:,}</span></div>'
            for r in rows
        )
        return f'<div class="ra-bars">{rows_html}</div>'

    icons = {
        "shield": '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 L20 6 V11 C20 16.5 16.5 20.5 12 22 C7.5 20.5 4 16.5 4 11 V6 Z"/><path d="M12 8 V13"/><path d="M12 16.3 V16.4"/></svg>',
        "alert": '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 L22.5 21 H1.5 Z"/><path d="M12 9.5 V14.5"/><path d="M12 17.7 V17.8"/></svg>',
        "up": '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17 L10 11 L14 15 L20 7"/><path d="M14 7 H20 V13"/></svg>',
        "vol": '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="4" height="10"/><rect x="10" y="5" width="4" height="15"/><rect x="16" y="13" width="4" height="7"/></svg>',
    }

    items = [
        (
            "crit", "shield", "Persistent Child Abuse Cases",
            f'<b>{totals["child_abuse"]:,} child abuse cases</b> were reported over the {n_days}-day period. '
            f'The most chronic recurrence was in {cl(ca_chronic)} &mdash; near-daily occurrence rather than '
            f'isolated incidents, calling for sustained protective and preventive measures in these districts.',
            bars(ca_chronic, "total", "crit"),
        ),
        (
            "crit", "alert", "Crime Against Women",
            f'Rape and gang rape together account for <b>{caw_total:,} reported cases</b> this period. '
            f'{dl(caw_rows)} recorded the highest combined caseloads, underscoring the need for stronger '
            f'oversight, victim protection and enforcement in these districts.',
            bars(caw_rows, "v", "crit"),
        ),
        (
            "high", "up", "Sustained Snatching/Jhappata Surge",
            f'Snatching/Jhappata recorded <b>{totals["snatching"]:,} cases</b> this period, with '
            f'{dl(sn_top3)} alone accounting for <b>{sn_top3_pct:.0f}%</b> of the provincial total. '
            f'Enhanced hotspot patrolling in these districts would address the bulk of the problem.',
            bars(sn_top3, "v", "high"),
        ),
        (
            "high", "vol", "Heavy Robbery Concentration",
            f'Robbery is the single largest category in this report at <b>{totals["robbery"]:,} cases</b>. '
            f'{dl(rb_top3)} &mdash; <b>{rb_top3_pct:.0f}%</b> of the provincial total &mdash; are the most '
            f'persistent hotspots, each logging cases on {rb_top3_min_days}+ of the {n_days} days on file.',
            bars(rb_top3, "v", "high"),
        ),
    ]

    badge_label = {"crit": "Critical", "high": "High"}
    cards = "".join(
        f'<div class="ra-card {sev}"><div class="ra-card-head"><div class="ra-icon {sev}">{icons[icon]}</div>'
        f'<div class="ra-head-text"><h4>{esc(title)}</h4>'
        f'<span class="ra-badge {sev}">{badge_label[sev]}</span></div></div>'
        f'<p>{body}</p>{bar_html}</div>'
        for sev, icon, title, body, bar_html in items
    )

    content = f"""
<div class="ra-page">
<div class="sec-title"><h2>Requires Attention</h2><span>Section 05</span></div>
<p class="sec-desc">The following areas warrant the Chief Minister's direct attention this reporting period, based on case volume, trend, and district concentration.</p>
<div class="ra-wrap">
<div class="ra-grid">{cards}</div>
</div>
</div>
"""
    return _wrap(content, page_num)


# ═══════════════════════════════════════════════════════════════════════
# Assemble
# ═══════════════════════════════════════════════════════════════════════
def generate(start_date=None, end_date=None, reporting_day=None, header_note=None, output="pdf", **_):
    earliest, latest = _date_bounds()
    start_date = _to_date(start_date) if start_date else earliest
    end_date = _to_date(end_date) if end_date else latest
    reporting_day = reporting_day or date.today().strftime("%d %b %Y")
    n_days = (end_date - start_date).days + 1
    data_period = f'{start_date.strftime("%d %b").lstrip("0")} – {end_date.strftime("%d %B %Y").lstrip("0")}'

    weekly_context = _weekly_context(start_date, end_date)

    # Page 1 = front cover, so numbered content starts at page 2.
    page_num = 2
    p_insights = _key_insights_page(start_date, end_date, weekly_context, page_num)
    page_num += 1
    p_case_count = _weekly_case_count_page(start_date, end_date, page_num)
    page_num += 1
    p_rising_falling = _rising_falling_page(start_date, end_date, page_num)
    page_num += 1
    p_detail, n_detail_pages = _detail_pages(start_date, end_date, page_num)
    page_num += n_detail_pages
    p_composition = _composition_page(start_date, end_date, page_num)
    page_num += 1
    p_attention = _requires_attention_page(start_date, end_date, page_num)
    page_num += 1  # back cover

    total_pages = page_num
    p_cover = _cover_page(data_period, reporting_day, n_days)
    p_back_cover = _back_cover_page()

    all_html = (
        p_cover + p_insights + p_case_count + p_rising_falling
        + p_detail + p_composition + p_attention + p_back_cover
    )
    all_html = all_html.replace("__TOTAL__", str(total_pages))

    html = f"""<!doctype html>
<html><head><meta charset="utf-8" /><title>Crime Analytics Punjab</title><style>{CSS}</style></head>
<body>
{all_html}
</body></html>
"""
    return save_html(html) if output == "html" else render_pdf(html)
