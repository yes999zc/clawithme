"""Phase 5 — Panorama report generator.

Produces a self-contained HTML report from search results.
Single function: generate_report(hits, profiles, clusters, username) -> str.
Geist-style grayscale design, no external dependencies.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from clawithme.signals.correlation import Cluster


def generate_report(  # noqa: PLR0913
    hits: list[dict],
    profiles: list[dict],
    clusters: list,
    username: str,
    *,
    trace_id: str = "",
    breach_dates: list[str] | None = None,
) -> str:
    """Return a complete HTML document as a string."""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    # Escape { } in user-supplied strings to prevent str.format() crashes
    safe_username = _fmt_esc(username)
    return _HTML.format(
        title=f"clawithme: {safe_username}",
        username=safe_username,
        timestamp=now,
        hit_count=f"{len(hits)} sites found",
        profile_count=f"{len(profiles)} profiles",
        cluster_count=f"{len(clusters)} clusters",
        sites_table=_render_sites(hits),
        profile_cards=_render_profiles(profiles),
        cluster_section=_render_clusters(clusters),
        timeline_section=_render_timeline(breach_dates or []),
        chart_section=_render_charts(hits, clusters),
        trace_id=_fmt_esc(trace_id),
    )


def export_json(
    hits: list[dict],
    profiles: list[dict],
    clusters: list,
    username: str,
    *,
    trace_id: str = "",
) -> str:
    """Return a JSON report as a string."""
    data = {
        "tool": "clawithme",
        "username": username,
        "timestamp": datetime.now(UTC).isoformat(),
        "trace_id": trace_id,
        "summary": {
            "sites_found": len(hits),
            "profiles_extracted": len(profiles),
            "clusters": len(clusters),
        },
        "hits": hits,
        "profiles": profiles,
        "clusters": [
            {
                "profiles": [asdict(p) for p in c.profiles],
                "confidence": c.confidence,
                "signals": c.signals,
            }
            if isinstance(c, Cluster) else c
            for c in clusters
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── HTML template ──────────────────────────────────────────────

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  color: #111; background: #fafafa; line-height: 1.6;
}}
.container {{ max-width: 720px; margin: 0 auto; padding: 48px 24px; }}

h1 {{ font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }}
h2 {{ font-size: 18px; font-weight: 600; color: #333; }}
h3 {{ font-size: 14px; font-weight: 500; color: #555; }}
.meta {{ color: #888; font-size: 13px; margin-top: 4px; }}
.section {{ margin-top: 40px; }}
.divider {{ border: 0; border-top: 1px solid #e5e5e5; margin: 24px 0; }}

/* ── Sites table ────────────────────────────── */
.site-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.site-table th {{ text-align: left; padding: 10px 12px; border-bottom: 2px solid #e5e5e5; color: #555; font-weight: 500; }}
.site-table td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
.site-table .url {{ color: #555; font-size: 13px; word-break: break-all; }}
.status-ok {{ color: #0a0; font-weight: 500; }}

/* ── Profile cards ──────────────────────────── */
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }}
.card {{
  background: #fff; border: 1px solid #e5e5e5; border-radius: 8px;
  padding: 20px; transition: box-shadow 0.15s;
}}
.card:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
.card-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
.card-avatar {{ width: 40px; height: 40px; border-radius: 50%; background: #eee; flex-shrink: 0; }}
.card-site {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }}
.card-name {{ font-size: 15px; font-weight: 600; }}
.card-bio {{ font-size: 13px; color: #555; margin-top: 8px; line-height: 1.5; }}
.card-meta {{ display: flex; gap: 16px; margin-top: 12px; font-size: 12px; color: #888; }}
.card-completeness {{ display: flex; align-items: center; gap: 8px; margin-top: 10px; }}
.cc-pct {{ font-family: monospace; font-size: 11px; min-width: 28px; }}
.cc-bar {{ display: inline-block; width: 60px; height: 4px; background: #f0f0f0; border-radius: 2px; overflow: hidden; }}
.cc-fill {{ display: block; height: 100%; border-radius: 2px; background: #d0d0d0; }}
.card-phash {{ font-family: monospace; font-size: 11px; color: #aaa; margin-top: 8px; word-break: break-all; }}

/* ── Clusters ────────────────────────────────── */
.cluster {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
.cluster-hd {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
.cluster-badge {{ font-size: 12px; padding: 2px 8px; border-radius: 4px; }}
.badge-high {{ background: #e8f5e9; color: #2e7d32; }}
.badge-mid {{ background: #fff3e0; color: #e65100; }}
.badge-low {{ background: #fce4ec; color: #c62828; }}
.cluster-signals {{ display: flex; gap: 6px; margin-top: 12px; }}
.signal-tag {{ font-size: 11px; padding: 2px 8px; background: #f5f5f5; border-radius: 4px; color: #666; font-family: monospace; }}
.cluster-list {{ font-size: 14px; display: flex; flex-wrap: wrap; gap: 6px; }}
.cluster-site {{ font-size: 12px; padding: 2px 8px; background: #f5f5f5; border-radius: 4px; }}
.cluster-evidence {{ font-size: 12px; color: #666; margin-top: 4px; padding: 2px 0; }}

/* ── Footer ──────────────────────────────────── */
.footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid #e5e5e5; font-size: 12px; color: #aaa; }}

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
.timeline-date {{ font-family: monospace; font-size: 11px; color: #555; display: block; }}

/* ── Charts ──────────────────────────────────── */
.chart-row {{ display: flex; gap: 24px; flex-wrap: wrap; }}
.chart-col {{ flex: 1; min-width: 280px; }}
.chart-title {{ font-size: 13px; font-weight: 500; color: #555; margin-bottom: 12px; }}
.chart-bar-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
.chart-bar-label {{ font-size: 12px; color: #666; min-width: 80px; text-align: right; flex-shrink: 0; }}
.chart-bar-track {{ flex: 1; height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden; }}
.chart-bar-fill {{ height: 100%; border-radius: 4px; }}
.chart-bar-count {{ font-family: monospace; font-size: 11px; color: #999; min-width: 24px; }}

/* ── Mobile ─────────────────────────────────── */
@media (max-width: 480px) {{
  .container {{ padding: 24px 16px; }}
  .card-grid {{ grid-template-columns: 1fr; }}
  h1 {{ font-size: 22px; }}
}}
</style>
</head>
<body>
<div class="container">

<h1>clawithme Report</h1>
<h2>{username}</h2>
<div class="meta">{hit_count} &middot; {profile_count} &middot; {cluster_count} &middot; {timestamp}</div>

<!-- SITES -->
<div class="section">
<h3>Discovered Sites</h3>
<hr class="divider">
{sites_table}
</div>

<!-- PROFILES -->
<div class="section">
<h3>Profiles</h3>
<hr class="divider">
{profile_cards}
</div>

<!-- CLUSTERS -->
<div class="section">
<h3>Identity Clusters</h3>
<hr class="divider">
{cluster_section}
</div>

<!-- TIMELINE -->
{timeline_section}

<!-- CHARTS -->
{chart_section}

<div class="footer">
  clawithme &middot; trace: {trace_id}
</div>

</div>
</body>
</html>"""


# ── Render helpers ──────────────────────────────────────────────

def _render_sites(hits: list[dict]) -> str:
    if not hits:
        return '<p style="color:#888">No sites found.</p>'

    # Group by classification.primary
    groups: dict[str, list[dict]] = {}
    for h in hits:
        site_def = h.get("site_def", {})
        classification = site_def.get("classification", {})
        primary = classification.get("primary", "other")
        groups.setdefault(primary, []).append(h)

    # Category display names
    cat_names = {
        "social": "Social", "devtools": "Dev Tools", "forum": "Forums",
        "media": "Media", "blog": "Blogs", "gaming": "Gaming",
        "music": "Music", "ecommerce": "E-Commerce",
    }

    # Summary bar
    summary_parts = []
    for cat in sorted(groups.keys()):
        name = cat_names.get(cat, cat.title())
        count = len(groups[cat])
        summary_parts.append(f'<span class="signal-tag">{name} {count}</span>')
    summary_html = '<div class="cluster-signals" style="margin-bottom:16px">' + "".join(summary_parts) + '</div>'

    # Grouped tables
    sections = []
    for cat in sorted(groups.keys()):
        cat_hits = groups[cat]
        name = cat_names.get(cat, cat.title())
        rows = []
        for h in cat_hits:
            url = h.get("url", "")
            rows.append(
                f'<tr>'
                f'<td>{_esc(h.get("site_name", ""))}</td>'
                f'<td class="url">{_esc(url)}</td>'
                f'<td class="status-ok">{h.get("status", "")}</td>'
                f'</tr>'
            )
        sections.append(
            f'<h4 style="margin-top:16px;font-size:13px;color:#666;font-weight:500">{name}</h4>'
            f'<table class="site-table">'
            f'<thead><tr><th>Site</th><th>URL</th><th>Status</th></tr></thead>'
            f'<tbody>' + "".join(rows) + "</tbody></table>"
        )

    return summary_html + "".join(sections)


def _render_profiles(profiles: list[dict]) -> str:
    if not profiles:
        return '<p style="color:#888">No profiles extracted.</p>'

    _PROFILE_FIELDS = ["display_name", "bio", "location", "avatar_url", "followers"]
    cards = []
    for p in profiles:
        bio = p.get("bio", "") or ""
        bio_html = f'<div class="card-bio">{_esc(bio[:200])}</div>' if bio.strip() else ""
        location = p.get("location", "") or ""
        followers = p.get("followers")
        meta_parts = []
        if location:
            meta_parts.append(f"📍 {_esc(location)}")
        if followers is not None:
            meta_parts.append(f"👥 {followers}")
        # Completeness score
        filled = sum(1 for f in _PROFILE_FIELDS if p.get(f))
        pct = int(filled / len(_PROFILE_FIELDS) * 100)
        pct_color = "#171717" if pct >= 60 else ("#808080" if pct >= 30 else "#b0b0b0")
        completeness_html = (
            f'<div class="card-completeness">'
            f'<span class="cc-pct" style="color:{pct_color}">{pct}%</span>'
            f'<span class="cc-bar"><span class="cc-fill" style="width:{pct}%"></span></span>'
            f'</div>'
        )
        meta_html = f'<div class="card-meta">{" · ".join(meta_parts)}</div>' if meta_parts else ""
        site_id = p.get("site_id", "?")
        name = p.get("display_name") or site_id
        cards.append(
            f'<div class="card">'
            f'<div class="card-header">'
            f'<div class="card-avatar"></div>'
            f'<div><div class="card-name">{_esc(name)}</div>'
            f'<div class="card-site">{_esc(site_id)}</div></div>'
            f'</div>'
            f'{bio_html}{completeness_html}{meta_html}'
            f'</div>'
        )
    return '<div class="card-grid">' + "".join(cards) + "</div>"


def _render_clusters(clusters: list) -> str:
    if not clusters:
        return '<p style="color:#888">No identity clusters.</p>'
    blocks = []
    for i, c in enumerate(clusters, 1):
        sites = ", ".join(_esc(p.site_id) for p in c.profiles)
        conf = c.confidence
        if conf >= 0.9:
            badge_cls = "badge-high"
        elif conf >= 0.7:
            badge_cls = "badge-mid"
        else:
            badge_cls = "badge-low"
        sig_tags = "".join(
            f'<span class="signal-tag">{s}</span>' for s in c.signals
        )
        evidence_lines = []
        if c.evidence:
            for sig, details in c.evidence.items():
                for d in details[:3]:  # max 3 per signal
                    evidence_lines.append(
                        f'<div class="cluster-evidence">'
                        f'<span class="signal-tag">{sig}</span> {_esc(_redact_evidence(sig, d))}'
                        f'</div>'
                    )
        evidence_html = "".join(evidence_lines) if evidence_lines else ""
        blocks.append(
            f'<div class="cluster">'
            f'<div class="cluster-hd">'
            f'<strong>Cluster {i}</strong>'
            f'<span class="cluster-badge {badge_cls}">{conf:.0%}</span>'
            f'</div>'
            f'<div class="cluster-list">{sites}</div>'
            f'<div class="cluster-signals">{sig_tags}</div>'
            f'{evidence_html}'
            f'</div>'
        )
    return "".join(blocks)


def _esc(s: str) -> str:
    """Minimal HTML escape."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_esc(s: str) -> str:
    """Escape curly braces for str.format() safety."""
    return s.replace("{", "{{").replace("}", "}}")


def _redact_evidence(signal: str, detail: str) -> str:
    """Redact PII in cluster evidence details.

    Email: 'alice@gmail.com' → 'a***@gmail.com'
    Phone: '13800001234' → '***1234'
    Other signals pass through unchanged.
    """
    if signal == "email":
        if "@" in detail:
            local, domain = detail.split("@", 1)
            return f"{local[0]}***@{domain}" if local else "***@…"
        return "***"
    if signal == "phone":
        return f"***{detail[-4:]}" if len(detail) >= 4 else "***"
    return detail


def _render_timeline(dates: list[str]) -> str:
    """Render horizontal timeline from breach dates. Empty if no dates."""
    if not dates:
        return ""
    unique_dates = sorted(set(dates), reverse=True)[:20]  # max 20
    dots = []
    for d in unique_dates:
        label = d if len(d) <= 10 else d[:10]  # YYYY-MM-DD
        dots.append(
            f'<div class="timeline-dot">'
            f'<span class="timeline-date">{_esc(label)}</span>'
            f'</div>'
        )
    return (
        '<div class="section">'
        '<h3>Breach Timeline</h3>'
        '<hr class="divider">'
        f'<div class="timeline"><div class="timeline-track">{"".join(dots)}</div></div>'
        '</div>'
    )


_CHART_COLORS = ["#171717", "#4d4d4d", "#808080", "#b0b0b0", "#d0d0d0"]


def _render_charts(hits: list[dict], clusters: list) -> str:
    """Render platform distribution + correlation signal charts."""
    if not hits and not clusters:
        return ""

    sections: list[str] = []

    # Platform distribution by classification
    if hits:
        cat_counts: dict[str, int] = {}
        for h in hits:
            site_def = h.get("site_def", {})
            cat = site_def.get("classification", {}).get("primary", "other")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        cat_names = {
            "social": "Social", "devtools": "Dev Tools", "forum": "Forums",
            "media": "Media", "blog": "Blogs", "gaming": "Gaming",
            "music": "Music", "ecommerce": "E-Commerce",
        }
        sorted_cats = sorted(cat_counts.items(), key=lambda x: -x[1])
        max_count = max(c for _, c in sorted_cats) if sorted_cats else 1

        bars = []
        for i, (cat, count) in enumerate(sorted_cats):
            pct = int(count / max_count * 100)
            color = _CHART_COLORS[i % len(_CHART_COLORS)]
            name = cat_names.get(cat, cat.title())
            bars.append(
                f'<div class="chart-bar-row">'
                f'<span class="chart-bar-label">{_esc(name)}</span>'
                f'<span class="chart-bar-track">'
                f'<span class="chart-bar-fill" style="width:{pct}%;background:{color}"></span>'
                f'</span>'
                f'<span class="chart-bar-count">{count}</span>'
                f'</div>'
            )

        sections.append(
            '<div class="chart-col">'
            '<div class="chart-title">Platform Distribution</div>'
            + "".join(bars) +
            '</div>'
        )

    # Correlation signal distribution
    if clusters:
        sig_counts: dict[str, int] = {}
        for c in clusters:
            for sig in c.signals:
                sig_counts[sig] = sig_counts.get(sig, 0) + 1
        if sig_counts:
            sorted_sigs = sorted(sig_counts.items(), key=lambda x: -x[1])
            max_sig = max(c for _, c in sorted_sigs)
            bars = []
            for i, (sig, count) in enumerate(sorted_sigs):
                pct = int(count / max_sig * 100)
                color = _CHART_COLORS[i % len(_CHART_COLORS)]
                bars.append(
                    f'<div class="chart-bar-row">'
                    f'<span class="chart-bar-label">{_esc(sig)}</span>'
                    f'<span class="chart-bar-track">'
                    f'<span class="chart-bar-fill" style="width:{pct}%;background:{color}"></span>'
                    f'</span>'
                    f'<span class="chart-bar-count">{count}</span>'
                    f'</div>'
                )
            sections.append(
                '<div class="chart-col">'
                '<div class="chart-title">Correlation Signals</div>'
                + "".join(bars) +
                '</div>'
            )

    if not sections:
        return ""

    return (
        '<div class="section">'
        '<h3>Analytics</h3>'
        '<hr class="divider">'
        f'<div class="chart-row">{"".join(sections)}</div>'
        '</div>'
    )
