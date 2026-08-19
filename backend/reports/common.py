# -*- coding: utf-8 -*-
"""Shared building blocks for every report: brand CSS, masthead, category
catalog, district-exclusion helper, and the PDF render bridge to Puppeteer.
"""
import html as html_lib
import os
import subprocess
import uuid
from pathlib import Path

import config

with open(config.ASSETS_DIR / "logo.txt", "r", encoding="utf-8") as f:
    CSU_LOGO = f.read().strip()
with open(config.ASSETS_DIR / "govlogo.txt", "r", encoding="utf-8") as f:
    GOVT_LOGO = f.read().strip()

# All 14 recorded categories, and the 12 that count as "real crime"
# (Road Accident Casualties and Religious Issues are excluded from crime totals).
ALL_CATEGORIES = [
    ("murder", "Murder"),
    ("dacoity", "Dacoity"),
    ("robbery", "Robbery"),
    ("dacoity_robbery_murder", "Dacoity/Robbery with Murder"),
    ("dacoity_robbery_injury", "Dacoity/Robbery with Injury"),
    ("dacoity_robbery_rape", "Dacoity/Robbery with Rape"),
    ("snatching_jhappata", "Snatching/Jhappata"),
    ("child_abuse", "Child Abuse"),
    ("rape", "Rape"),
    ("gang_rape", "Gang Rape"),
    ("sodomy", "Sodomy"),
    ("road_accident_casualties", "Road Accident Casualties"),
    ("acid_attack", "Acid Attack"),
    ("religious_issues", "Religious Issues"),
]
NON_CRIME_COLUMNS = ("road_accident_casualties", "religious_issues")
REAL_CRIME_COLUMNS = [c for c, _ in ALL_CATEGORIES if c not in NON_CRIME_COLUMNS]

# The six headline categories used across every category-level report.
HEADLINE_CATEGORIES = [
    ("murder", "Murder"),
    ("robbery", "Robbery"),
    ("child_abuse", "Child Abuse"),
    ("rape", "Rape"),
    ("gang_rape", "Gang Rape"),
    ("snatching_jhappata", "Snatching / Jhappata"),
]

DISTRICT_FILTER_SQL = "d.exclude_from_analysis = FALSE"


def real_crime_sum_sql(alias="c"):
    return "+".join(f"{alias}.{col}" for col in REAL_CRIME_COLUMNS)


def all_crime_sum_sql(alias="c"):
    return "+".join(f"{alias}.{col}" for col in [c for c, _ in ALL_CATEGORIES])


CSS = """
  :root{
    --ink:#1c1d29; --muted:#6c7080; --faint:#9aa0b0; --line:#e3e5ee;
    --navy:#211d50; --navy-2:#2f2a6b;
    --crimson:#9F1239; --crimson-bg:#FBE7EC;
    --amber:#B45309;  --amber-bg:#FBEEE0;
    --teal:#0F766E;   --teal-bg:#E4F3F0;
    --violet:#6D28D9; --violet-bg:#EFE7FC;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,'Segoe UI',system-ui,sans-serif;color:var(--ink);background:#DDD}
  .tnum{font-variant-numeric:tabular-nums}
  @page{size:A4;margin:0}
  .page{width:210mm;height:297mm;background:#fff;padding:12mm 13mm 10mm;position:relative;overflow:hidden;break-after:page;page-break-after:always}
  .page:last-child{break-after:auto;page-break-after:auto}
  @media screen{ .page{margin:14px auto;box-shadow:0 4px 24px rgba(0,0,0,.15)} }

  .masthead{display:grid;grid-template-columns:120px 1fr 120px;align-items:center;gap:12px;padding-bottom:8px;margin-bottom:4mm;border-bottom:2.5px solid var(--navy)}
  .mast-left img{height:52px;width:auto;display:block}
  .mast-center{text-align:center;min-width:0}
  .mast-title{font-size:16px;font-weight:800;color:var(--navy);letter-spacing:-.01em;line-height:1.15}
  .mast-meta{margin-top:5px;font-size:11px;color:var(--muted);display:flex;gap:9px;justify-content:center;align-items:center;flex-wrap:wrap;white-space:normal}
  .mast-meta b{color:var(--ink);font-weight:700}
  .mast-meta .sep{color:var(--line)}
  .baseline-note{margin-top:4px;font-size:10px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:var(--navy-2)}
  .custom-note{margin-top:4px;font-size:10.5px;font-style:italic;color:var(--ink);background:var(--amber-bg);display:inline-block;padding:2px 10px;border-radius:10px}
  .mast-right{display:flex;flex-direction:column;align-items:center;text-align:center;gap:3px}
  .mast-right img{height:48px;width:auto;display:block}
  .mast-right .office{font-size:7.4px;font-weight:800;letter-spacing:.02em;color:var(--navy);line-height:1.25;text-transform:uppercase}
  .mast-right .office span{display:block;font-weight:600;color:var(--muted);text-transform:none;font-size:7.2px}

  .stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:6mm}
  .stat-grid.n3{grid-template-columns:repeat(3,1fr)}
  .stat-card{border:1px solid var(--line);border-radius:8px;padding:11px 12px;background:#FBFAF7}
  .stat-card .n{font-size:21px;font-weight:900;letter-spacing:-.02em;color:var(--ink)}
  .stat-card .l{margin-top:3px;font-size:9.5px;font-weight:800;letter-spacing:.03em;text-transform:uppercase;color:var(--muted)}
  .stat-card .d{margin-top:6px;font-size:9.7px;color:var(--muted);line-height:1.36}
  .stat-card.c-crimson{border-left:4px solid var(--crimson)}
  .stat-card.c-amber{border-left:4px solid var(--amber)}
  .stat-card.c-violet{border-left:4px solid var(--violet)}
  .stat-card.c-teal{border-left:4px solid var(--teal)}
  .stat-card.c-navy{border-left:4px solid var(--navy)}

  .sec-tag{display:inline-flex;align-items:center;gap:6px;font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:4px 11px;border-radius:20px;margin-bottom:7px}
  .sec-tag.crimson{background:var(--crimson-bg);color:var(--crimson)}
  .sec-tag.violet{background:var(--violet-bg);color:var(--violet)}
  .sec-tag.amber{background:var(--amber-bg);color:var(--amber)}
  .sec-tag.teal{background:var(--teal-bg);color:var(--teal)}

  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:9mm;margin-bottom:6mm}

  .table-wrap{border:1px solid var(--line);border-radius:8px;overflow:hidden}
  table{width:100%;border-collapse:collapse;font-size:10.5px}
  table.compact{font-size:8.3px}
  thead th{padding:6px 9px;text-align:left;font-size:8.6px;font-weight:800;letter-spacing:.03em;text-transform:uppercase;color:#fff;white-space:nowrap}
  table.compact thead th{padding:4px 6px;font-size:7.2px}
  thead.crimson th{background:var(--crimson)}
  thead.violet th{background:var(--violet)}
  thead.amber th{background:var(--amber)}
  thead.teal th{background:var(--teal)}
  thead.navy th{background:var(--navy)}
  tbody td{padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:middle;white-space:nowrap}
  table.compact tbody td{padding:2.5px 6px}
  tbody tr:last-child td{border-bottom:none}
  tbody tr:nth-child(even){background:#FBFAF7}
  td.num, th.num{text-align:right}
  .rank{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:4px;font-size:8.6px;font-weight:800;color:#fff}
  .rank.crimson{background:var(--crimson)} .rank.violet{background:var(--violet)} .rank.amber{background:var(--amber)} .rank.teal{background:var(--teal)} .rank.navy{background:var(--navy)}

  p.sec-note{font-size:10px;color:var(--muted);line-height:1.38;margin-bottom:6px}
  .tbl-note{font-size:9.3px;color:var(--muted);line-height:1.4;padding:8px 10px;background:#FBFAF7;border-top:1px solid var(--line);white-space:normal}
  .tbl-note b{color:var(--ink);font-weight:800}

  .callout{border:1px solid var(--line);border-left:4px solid var(--navy);border-radius:0 8px 8px 0;padding:10px 13px;margin-top:2mm;font-size:10.5px;color:var(--ink);line-height:1.42;background:#FBFAF7}
  .callout b{font-weight:800}
  .callout.crimson{border-left-color:var(--crimson)}
  .callout.teal{border-left-color:var(--teal)}
  .callout.amber{border-left-color:var(--amber)}
  .callout.violet{border-left-color:var(--violet)}

  .badge{display:inline-block;font-size:9px;font-weight:800;padding:2px 7px;border-radius:10px;white-space:nowrap}
  .badge.up{background:var(--crimson-bg);color:var(--crimson)}
  .badge.down{background:var(--teal-bg);color:var(--teal)}
  .badge.flat{background:var(--amber-bg);color:var(--amber)}

  .footer{position:absolute;left:13mm;right:13mm;bottom:6mm;display:flex;justify-content:space-between;font-size:7.5px;color:var(--faint);border-top:1px solid var(--line);padding-top:4px}
  .section-block{margin-bottom:4mm}

  .meth h2{font-size:15px;font-weight:900;color:var(--navy);margin-bottom:3mm;letter-spacing:-.01em}
  .meth h3{font-size:11px;font-weight:800;color:var(--navy-2);text-transform:uppercase;letter-spacing:.04em;margin:5mm 0 2mm}
  .meth p{font-size:10.5px;color:var(--ink);line-height:1.6;margin-bottom:2mm}
  .meth .formula{background:#FBFAF7;border:1px solid var(--line);border-left:4px solid var(--navy);border-radius:0 8px 8px 0;padding:9px 12px;margin:2mm 0;font-size:10.5px;line-height:1.55}
  .meth .formula code{font-family:'Courier New',monospace;font-weight:700;color:var(--navy)}
"""

FOOTER = '<div class="footer"><span>Crime Surveillance Unit</span><span>Data Source: Punjab Police</span></div>'


def esc(s):
    return html_lib.escape(str(s), quote=True)


def masthead(title, baseline, reporting_day, data_period, custom_note=None):
    """custom_note is the free-text header note a user can attach to any
    report from the frontend before generating it (e.g. "Prepared for the
    15 Aug CM Security Briefing")."""
    note_html = f'<div class="custom-note">{esc(custom_note)}</div>' if custom_note else ""
    return f"""
  <div class="masthead">
    <div class="mast-left"><img src="{CSU_LOGO}" alt="CSU" /></div>
    <div class="mast-center">
      <div class="mast-title">{title}</div>
      <div class="mast-meta"><span>Reporting Day: <b>{esc(reporting_day)}</b></span><span class="sep">|</span><span>Data Period: <b>{esc(data_period)}</b></span></div>
      <div class="baseline-note">{baseline}</div>
      {note_html}
    </div>
    <div class="mast-right">
      <img src="{GOVT_LOGO}" alt="Government of Punjab" />
      <div class="office">Chief Minister's Office<span>Additional Secretary <br /> (Law &amp; Order)</span></div>
    </div>
  </div>
"""


# Floating toolbar injected into every previewable report: lets a reviewer
# switch on Edit Mode (contentEditable), click into any heading/paragraph/cell
# and retype it, then export the *edited* DOM straight to PDF via the backend.
EDIT_TOOLBAR = """
<div id="csu-toolbar" style="position:fixed;top:14px;right:14px;z-index:9999;display:flex;gap:8px;align-items:center;background:#211d50;padding:8px 10px;border-radius:10px;box-shadow:0 4px 18px rgba(0,0,0,.25);font-family:-apple-system,'Segoe UI',system-ui,sans-serif;">
  <button id="csu-edit-btn" style="cursor:pointer;border:none;border-radius:6px;padding:7px 12px;font-size:12px;font-weight:700;background:#2f2a6b;color:#fff;">&#9998; Edit Text</button>
  <button id="csu-export-btn" style="cursor:pointer;border:none;border-radius:6px;padding:7px 12px;font-size:12px;font-weight:700;background:#0F766E;color:#fff;">&#8681; Export PDF</button>
  <span id="csu-status" style="font-size:11px;color:#c9c6e8;min-width:80px;"></span>
</div>
<style>
  .csu-editing [contenteditable="true"]:hover{outline:1.5px dashed #6D28D9;cursor:text}
  @media print{ #csu-toolbar{display:none !important} }
</style>
<script>
(function(){
  // This page is always served from .../<api-base>/reports/download/<file>,
  // so the API base (which varies by deployment -- "/api" locally, e.g.
  // "/CrimeAnalysis/api" behind a reverse-proxy path prefix) can be derived
  // from the page's own URL rather than hardcoded, so this static HTML
  // keeps working no matter where the app is deployed.
  var apiBase = location.pathname.replace(/\/reports\/download\/.*$/, '');
  var editing = false;
  var editableSelectors = '.mast-title,.baseline-note,.custom-note,.sec-tag,.sec-note,.stat-card .n,.stat-card .l,.stat-card .d,.callout,.tbl-note,td,th,.meth p,.meth h2,.meth h3,li';
  function toggleEdit(){
    editing = !editing;
    document.querySelectorAll(editableSelectors).forEach(function(el){
      el.setAttribute('contenteditable', editing ? 'true' : 'false');
    });
    document.body.classList.toggle('csu-editing', editing);
    document.getElementById('csu-edit-btn').textContent = editing ? '\\u2713 Done Editing' : '\\u270E Edit Text';
    document.getElementById('csu-status').textContent = editing ? 'Click any text to edit' : '';
  }
  document.getElementById('csu-edit-btn').addEventListener('click', toggleEdit);
  document.getElementById('csu-export-btn').addEventListener('click', function(){
    var status = document.getElementById('csu-status');
    status.textContent = 'Exporting...';
    if (editing) toggleEdit();
    var toolbar = document.getElementById('csu-toolbar');
    toolbar.style.display = 'none';
    var htmlContent = '<!doctype html>' + document.documentElement.outerHTML;
    toolbar.style.display = 'flex';
    fetch(apiBase + '/reports/export_html', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ html: htmlContent })
    }).then(function(r){ return r.json(); }).then(function(data){
      if (data.url) {
        status.textContent = 'Done';
        window.open(apiBase + data.url, '_blank');
      } else {
        status.textContent = 'Error: ' + (data.error || 'failed');
      }
    }).catch(function(e){ status.textContent = 'Error: ' + e.message; });
  });
})();
</script>
"""


def wrap_pages(*page_bodies, title="Report", editable=False):
    pages = "".join(f'<section class="page">{p}</section>' for p in page_bodies)
    toolbar = EDIT_TOOLBAR if editable else ""
    return f"""<!doctype html>
<html><head><meta charset="utf-8" /><title>{esc(title)}</title><style>{CSS}</style></head>
<body>{toolbar}{pages}</body></html>
"""


def save_html(html_content, out_name=None):
    """Write HTML to generated/ and return its filename (no PDF render)."""
    uid = out_name or f"report-{uuid.uuid4().hex[:10]}"
    html_path = config.GENERATED_DIR / f"{uid}.html"
    html_path.write_text(html_content, encoding="utf-8")
    return html_path.name


def render_pdf_from_file(html_filename):
    """Render an already-saved HTML file (by filename in generated/) to PDF.
    Returns the PDF filename."""
    stem = Path(html_filename).stem
    html_path = config.GENERATED_DIR / html_filename
    pdf_path = config.GENERATED_DIR / f"{stem}.pdf"

    # When this whole process is itself managed by PM2, PM2 injects
    # NODE_CHANNEL_FD (Node's child_process.fork() IPC handle) into our own
    # environment even though we're a Python process, not a Node one. If
    # that var leaks into this "node render.mjs" subprocess, Node tries to
    # open an IPC channel on a file descriptor that was never actually
    # passed down, and aborts (SIGABRT) right at exit — after the PDF has
    # already rendered successfully, which is why it's easy to miss. Strip
    # it so the child starts with no dangling IPC expectations.
    child_env = {k: v for k, v in os.environ.items() if k != "NODE_CHANNEL_FD"}
    result = subprocess.run(
        ["node", str(config.RENDER_DIR / "render.mjs"), str(html_path), str(pdf_path)],
        capture_output=True, text=True, cwd=str(config.RENDER_DIR), env=child_env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PDF render failed: {result.stderr or result.stdout}")
    return pdf_path.name


def render_pdf(html_content, out_name=None):
    """Write HTML to the generated/ folder and shell out to the Puppeteer
    renderer to produce a PDF. Returns the PDF filename."""
    html_name = save_html(html_content, out_name)
    return render_pdf_from_file(html_name)
