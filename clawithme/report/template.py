"""Phase 5 — Report HTML template.

Self-contained Geist-style HTML template. Uses .format() placeholders
for dynamic content injection. CSS braces are escaped as {{/}}.
"""

from __future__ import annotations

_HTML = """\
<!DOCTYPE html>
<html lang="{html_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
/* ── Design Tokens ─────────────────────────── */
:root {{
  --accent: #1e293b;
  --accent-subtle: #475569;
  --accent-bg: rgba(30, 41, 59, 0.04);
  --bg-warm: #fafaf8;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  color: #171717; background: var(--bg-warm); line-height: 1.6;
}}
.container {{ max-width: 780px; margin: 0 auto; padding: 48px 24px 56px; }}

/* ── Brand header ───────────────────────────── */
.brand-header {{
  display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px;
}}
.brand-wordmark {{
  font: 700 14px/1 'Inter', sans-serif; color: #171717;
  letter-spacing: 1.5px; text-transform: uppercase;
}}
.brand-wordmark-me {{
  color: #16a34a;
}}
.brand-slogan {{
  font: 400 13px/1 'JetBrains Mono', ui-monospace, monospace; color: #b0b0b0;
}}

h1 {{ font-size: 36px; font-weight: 700; letter-spacing: -0.8px; margin: 0 0 4px; }}
h2 {{ font-size: 20px; font-weight: 600; color: #171717; letter-spacing: -0.3px; margin: 0; }}
h3 {{ font-size: 14px; font-weight: 500; color: #4d4d4d; letter-spacing: 0.02em; margin: 0; }}
.meta {{ color: #808080; font-size: 12px; }}
.section {{ margin-top: 48px; }}
.section + .section {{ margin-top: 56px; }}
.summary-hero + .section {{ margin-top: 36px; }}
.divider {{ border: 0; border-top: 1px solid #e5e5e5; margin: 20px 0 24px; }}

/* ── Section header ────────────────────────── */
.section-header {{
  display: flex; align-items: center; gap: 12px;
  padding: 14px 20px; margin: -28px -28px 0 -28px;
  border-bottom: 1px solid #e5e5e5; background: #fafafa;
}}
.section-header .badge {{
  font: 500 11px/1 'JetBrains Mono', ui-monospace, monospace;
  padding: 2px 8px; border-radius: 999px;
  background: var(--accent); color: white; flex-shrink: 0;
}}
.section-header h2 {{ font: 600 15px/1.3 'Inter', sans-serif; color: #171717; }}
.section-explain {{
  font-size: 13px; color: #808080; line-height: 1.6; margin: 20px 0 0; max-width: 600px;
}}
.section-container {{
  padding: 28px; border-radius: 8px;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.08), 0px 2px 2px rgba(0,0,0,0.04);
  overflow: hidden; margin-bottom: 8px;
}}

/* ── Summary hero (namecard) ───────────────── */
.summary-hero {{
  background: #fff; border-radius: 10px;
  padding: 36px 36px 28px;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.08), 0px 2px 2px rgba(0,0,0,0.04);
}}
.hero-card {{
  display: flex; align-items: flex-start; gap: 24px;
}}
.hero-avatar-wrap {{
  width: 72px; height: 72px; border-radius: 50%; flex-shrink: 0;
  overflow: hidden; background: #f0f0f0;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.06);
}}
.hero-avatar-wrap img {{
  width: 100%; height: 100%; object-fit: cover;
}}
.hero-avatar-fallback {{
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 30px; font-weight: 600; color: #fff;
}}
.hero-info {{ flex: 1; min-width: 0; }}
.hero-info h1 {{
  font-size: 28px; font-weight: 700; letter-spacing: -0.5px;
  color: #171717; margin: 0 0 2px;
}}
.hero-username {{
  font-size: 15px; color: #808080; margin-bottom: 14px;
}}
.hero-identity {{
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
}}
.hero-identity-badge {{
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: #e8f5e9; color: #2e7d32; font-weight: 500;
}}
.hero-summary {{
  font-size: 14px; color: #4d4d4d; line-height: 1.7; margin-bottom: 16px; max-width: 600px;
}}
.hero-stats {{
  display: flex; gap: 24px; flex-wrap: wrap;
}}
.hero-stat {{
  display: flex; align-items: baseline; gap: 5px;
}}
.hero-stat-value {{
  font-size: 24px; font-weight: 600; color: #171717;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-variant-numeric: tabular-nums; line-height: 1;
}}
.hero-stat-label {{
  font-size: 12px; color: #808080; text-transform: uppercase; letter-spacing: 0.5px;
}}
.hero-meta {{
  margin-top: 16px; font-size: 12px; color: #b0b0b0;
}}
.hero-divider {{
  height: 1px; background: #e5e5e5; margin: 20px 0 24px;
}}
.fp-note {{
  font-size: 12px; color: #b0b0b0; cursor: help;
  border-bottom: 1px dotted #b0b0b0;
  text-transform: none; letter-spacing: normal;
}}

/* ── Uncertain sites details ──────────────────── */
.uncertain-summary {{
  cursor: pointer; font-size: 13px; color: #808080;
  padding: 8px 12px; border-radius: 6px;
  background: #fafafa; border: 1px solid #e5e5e5;
}}

/* ── Status badges ────────────────────────────── */
.status-ok {{ color: #2e7d32; font-family: 'JetBrains Mono', monospace; font-size: 12px; }}
.status-warn {{ color: #b8860b; font-family: 'JetBrains Mono', monospace; font-size: 12px; }}

/* ── Site icons ─────────────────────────────── */
.site-icon {{
  width: 16px; height: 16px; border-radius: 3px;
  vertical-align: middle; margin-right: 8px; flex-shrink: 0;
}}
.site-icon-lg {{
  width: 24px; height: 24px; border-radius: 4px;
  vertical-align: middle; margin-right: 8px; flex-shrink: 0;
}}
.site-favicon {{
  width: 44px; height: 44px; border-radius: 8px; background: #f8f8f8;
  flex-shrink: 0; object-fit: contain; padding: 4px;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.06);
}}
.site-name-cell {{
  display: flex; align-items: center; gap: 8px;
}}

/* ── Cluster site pills ─────────────────────── */
.cluster-site-pill {{
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; padding: 3px 10px 3px 5px;
  background: #f5f5f5; border-radius: 6px;
  color: #4d4d4d; margin: 2px 2px;
}}
.cluster-site-pill img {{
  width: 14px; height: 14px; border-radius: 2px;
}}
.cluster-list-pills {{
  display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px;
}}

/* ── Table site cell ────────────────────────── */
.site-table td:first-child {{
  display: flex; align-items: center; gap: 8px;
}}
.site-table td.url {{
  font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11px; color: #808080; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.site-table td.url a {{
  color: #475569; text-decoration: none;
}}
.site-table td.url a:hover {{
  color: #1e293b; text-decoration: underline;
}}
.site-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.site-table th {{ text-align: left; padding: 10px 12px; border-bottom: 2px solid #e5e5e5; color: #4d4d4d; font-weight: 500; }}
.site-table td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
.cat-label {{
  font-size: 13px; font-weight: 500; color: #808080;
  margin-top: 20px; text-transform: uppercase; letter-spacing: 0.5px;
}}

/* ── Confidence badge & wrong-person warning ─── */
.conf-badge {{
  display: inline-block; font-size: 10px; font-weight: 600;
  padding: 2px 6px; border-radius: 3px; margin-left: 6px;
  text-transform: uppercase; letter-spacing: 0.3px;
}}
.conf-badge.badge-ok {{ background: #e8f5e9; color: #2e7d32; }}
.conf-badge.badge-warn {{ background: #fff8e1; color: #b8860b; }}
.conf-badge.badge-low {{ background: #fce4ec; color: #c62828; }}
.wp-warn {{
  display: inline-block; font-size: 11px; color: #c62828;
  margin-left: 6px; font-weight: 500;
}}

/* ── Cluster cards ──────────────────────────── */
.cluster-hd {{
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
}}
.cluster-hd strong {{
  font-size: 14px; font-weight: 600; color: #171717;
}}
.cluster-conf-bar {{
  height: 6px; background: #f0f0f0; border-radius: 3px;
  overflow: hidden; margin: 0 0 8px; flex: 1;
}}
.cluster-conf-fill {{
  height: 100%; border-radius: 3px; transition: width 0.3s;
}}
.cluster-conf-label {{
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  font-weight: 600; margin-left: 8px;
}}

/* ── Profile cards ──────────────────────────── */
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; margin-top: 4px; }}
.card {{
  background: #fff; border-radius: 8px; padding: 20px;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.08), 0px 2px 2px rgba(0,0,0,0.04);
  transition: box-shadow 0.15s;
}}
.card:hover {{ box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.12), 0px 4px 8px rgba(0,0,0,0.06); }}
.card-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
.card-avatar {{
  width: 44px; height: 44px; border-radius: 50%; background: #f0f0f0;
  flex-shrink: 0; object-fit: cover;
}}
.card-site {{ font-size: 11px; color: #808080; text-transform: uppercase; letter-spacing: 0.5px; }}
.card-name {{ font-size: 15px; font-weight: 600; color: #171717; }}
.card-bio {{ font-size: 13px; color: #4d4d4d; margin-top: 8px; line-height: 1.5; }}
.card-meta {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; font-size: 12px; color: #808080; }}
.card-extras {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
.card-extra-tag {{
  font-size: 11px; padding: 2px 8px; background: #f5f5f5;
  border-radius: 4px; color: #4d4d4d; font-family: 'JetBrains Mono', monospace;
}}
.card-completeness {{ display: flex; align-items: center; gap: 0; margin-top: 12px; }}

/* ── Donut ring ─────────────────────────────── */
.cc-donut {{
  width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
  background: conic-gradient(
    var(--donut-color, #171717) 0deg calc(var(--pct) * 3.6deg),
    #f0f0f0 calc(var(--pct) * 3.6deg) 360deg
  );
  position: relative;
}}
.cc-donut::after {{
  content: attr(data-pct);
  position: absolute; inset: 4px; border-radius: 50%;
  background: #fff;
  display: flex; align-items: center; justify-content: center;
  font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600; color: #171717;
}}
.completeness-label {{
  font-size: 9px; color: #b0b0b0; cursor: help;
  font-family: 'JetBrains Mono', monospace; text-align: center;
  border-bottom: 1px dotted transparent;
}}
.completeness-label:hover {{ border-bottom-color: #b0b0b0; }}

/* ── Profile detail table ───────────────────── */
.field-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
.field-table td {{ padding: 4px 8px; border-bottom: 1px solid #f5f5f5; vertical-align: top; }}
.field-table td:first-child {{ border-bottom: none; }}
.field-label {{
  font-family: 'JetBrains Mono', monospace; color: #808080; width: 100px;
  font-size: 11px; padding-top: 6px !important; white-space: nowrap;
}}
.field-value {{
  color: #4d4d4d; line-height: 1.5; word-break: break-word;
  padding: 6px 8px !important;
}}

/* ── Clusters ────────────────────────────────── */
.cluster {{
  background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.08), 0px 2px 2px rgba(0,0,0,0.04);
}}
.cluster-hd {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
.cluster-hd strong {{ font-size: 15px; }}
/* ── Cluster explanation ─────────────────────── */
.cluster-signals {{ display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }}
.signal-tag {{
  font-size: 11px; padding: 2px 8px; background: #f5f5f5;
  border-radius: 4px; color: #4d4d4d; font-family: 'JetBrains Mono', monospace;
}}
.cluster-list {{ font-size: 14px; display: flex; flex-wrap: wrap; gap: 6px; }}
.cluster-site {{ font-size: 12px; padding: 2px 8px; background: #f5f5f5; border-radius: 4px; }}
.cluster-evidence {{ font-size: 12px; color: #4d4d4d; margin-top: 4px; padding: 2px 0; }}
.cluster-identity {{
  margin-top: 12px; padding: 8px 12px; background: #e8f5e9;
  border-radius: 4px; font-size: 13px; color: #2e7d32;
}}

/* ── Cluster Assessment ────────────────────── */
.cluster-assessment {{
  background: #fafafa; border: 1px solid #e5e5e5;
  border-radius: 6px; padding: 14px 16px; margin-bottom: 20px;
}}
.cluster-assessment-title {{
  font: 600 13px/1.4 'Inter', sans-serif; color: #171717;
  margin-bottom: 6px;
}}
.cluster-assessment-body {{
  font-size: 13px; line-height: 1.5; color: #4d4d4d;
}}
.cluster-assessment-note {{
  font-size: 11px; color: #b0b0b0; margin-top: 6px;
}}

/* ── Footer ──────────────────────────────────── */
.footer {{ margin-top: 56px; padding-top: 16px; border-top: 1px solid #e5e5e5; font-size: 12px; color: #b0b0b0; }}

.action-items {{ margin-top: 40px; }}
.action-items h2 {{ font-size: 16px; font-weight: 600; margin-bottom: 12px; color: var(--accent); }}
.action-item {{ display: flex; gap: 10px; padding: 12px 16px; margin-bottom: 8px; border-radius: 8px; background: #fff; box-shadow: 0 0 0 1px rgba(0,0,0,0.06); font-size: 14px; }}
.action-icon {{ font-size: 18px; flex-shrink: 0; }}
.action-item .action-body {{ flex: 1; }}
.action-item .action-title {{ font-weight: 600; margin-bottom: 2px; }}
.action-item .action-detail {{ font-size: 12px; color: #808080; }}
.action-item.warn {{ border-left: 3px solid var(--amber); }}
.action-item.info {{ border-left: 3px solid var(--accent); }}
.action-item.danger {{ border-left: 3px solid var(--red); }}

/* ── Timeline ───────────────────────────────── */
.timeline {{ overflow-x: auto; padding: 16px 0; }}
.timeline-track {{ display: flex; align-items: flex-end; gap: 0; min-height: 80px; position: relative; }}
.timeline-track::before {{
  content: ''; position: absolute; bottom: 28px; left: 0; right: 0;
  height: 2px; background: #e5e5e5;
}}
.timeline-dot {{ text-align: center; min-width: 100px; flex-shrink: 0; position: relative; }}
.timeline-dot::before {{
  content: ''; display: block; width: 8px; height: 8px;
  background: #171717; border-radius: 50%;
  margin: 0 auto 8px; position: relative; z-index: 1;
}}
.timeline-date {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #808080; display: block; }}

/* ── Charts ──────────────────────────────────── */
.chart-row {{ display: flex; gap: 32px; flex-wrap: wrap; }}
.chart-col {{ flex: 1; min-width: 280px; }}
.chart-title {{ font-size: 14px; font-weight: 600; color: #171717; margin-bottom: 2px; letter-spacing: -0.2px; }}
.chart-subtitle {{ font-size: 12px; color: #808080; margin: 0 0 16px; line-height: 1.4; }}
.chart-summary {{
  display: flex; align-items: baseline; gap: 6px;
  font-size: 12px; color: #808080; margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}}
.chart-summary-num {{
  font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 600; color: var(--accent);
  font-variant-numeric: tabular-nums; line-height: 1;
}}
.chart-bar-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
.chart-bar-label {{ font-size: 12px; color: #4d4d4d; min-width: 80px; text-align: right; flex-shrink: 0; }}
.chart-bar-track {{ flex: 1; height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden; }}
.chart-bar-fill {{ height: 100%; border-radius: 4px; background: var(--accent); opacity: var(--bar-opacity, 1); }}
.chart-bar-count {{
  font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #808080; min-width: 24px;
}}

/* ── Radar chart ─────────────────────────────── */
.chart-col-radar {{
  min-width: 300px; max-width: 360px;
}}
.radar-chart {{
  display: flex; justify-content: center; margin-top: 8px;
}}
.radar-svg {{
  width: 100%; max-width: 270px; height: auto;
}}
.radar-label {{
  font-family: 'Inter', sans-serif; font-size: 11px; fill: #4d4d4d; font-weight: 500;
}}
.radar-score {{
  font-family: 'JetBrains Mono', monospace; font-size: 10px; fill: var(--accent); font-weight: 600;
}}

/* ── Mobile ─────────────────────────────────── */
@media (max-width: 480px) {{
  .container {{ padding: 24px 16px 32px; }}
  .card-grid {{ grid-template-columns: 1fr; }}
  h1 {{ font-size: 24px; }}
  .summary-hero {{ padding: 24px; }}
  .hero-stat-value {{ font-size: 22px; }}
  .hero-stats {{ gap: 20px; }}
  .section-container {{ padding: 20px 16px; }}
  .section-header {{ margin: -20px -16px 0 -16px; padding: 12px 16px; }}
}}
</style>
</head>
<body>
<div class="container">

{summary_hero}

<div class="section"><div class="section-container">
<div class="section-header"><span class="badge">01</span><h2>{sec_sites}</h2></div>
{confirmed_table}
{uncertain_section}
{dropped_note}
</div></div>

<div class="section"><div class="section-container">
<div class="section-header"><span class="badge">02</span><h2>{sec_profiles}</h2></div>
{profile_cards}
</div></div>

<div class="section"><div class="section-container">
<div class="section-header"><span class="badge">03</span><h2>{sec_clusters}</h2></div>
<p class="section-explain">{cluster_explain}</p>
{cluster_section}
</div></div>

{timeline_section}

<div class="section"><div class="section-container">
<div class="section-header"><span class="badge">04</span><h2>{sec_analytics}</h2></div>
{chart_section}
</div></div>

{actions_section}

<div class="footer">
  <p><strong>CLAWITHME</strong> &mdash; {footer_brand_line}</p>
  <p>{footer_generated} {timestamp} &middot; trace: {trace_id}</p>
  <p style="margin-top:12px;font-size:11px">
    <span class="fp-note" style="font-size:11px">{footer_hover_hint}</span>
    &middot; {footer_spa}
    &middot; {footer_completeness}
    &middot; {footer_cluster}
  </p>
</div>

</div>
</body>
</html>"""


def _fmt_esc(s: str) -> str:
    """Escape curly braces for .format() — prevents CSS { from being parsed as template."""
    return s.replace("{", "{{").replace("}", "}}")
