"""Phase 5 — Panorama report generator.

Produces a self-contained HTML report from search results.
Geist-style grayscale design, no external dependencies.

v2 improvements (2026-05-05):
- Avatar images from actual URLs
- Profile card extras (reputation, badges, cross-site links, verified)
- Cluster display_name consistency highlight
- Summary hero box at top
- Site hit quality: flag SPA/redirect false positives
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from clawithme.signals.correlation import Cluster


# ── Known false-positive sites (SPA shells, login redirects) ──
_SPA_SITES = frozenset({"sspai", "twitch", "twitter", "weibo", "instagram", "slideshare"})


def _is_false_positive(site_id: str) -> bool:
    """Return True if this site hit is a known SPA/redirect false positive."""
    return site_id in _SPA_SITES


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
    safe_username = _fmt_esc(username)

    # Separate true hits from false positives
    true_hits = [h for h in hits if not _is_false_positive(_hit_site_id(h))]
    fp_hits = [h for h in hits if _is_false_positive(_hit_site_id(h))]

    # Compute summary stats
    true_hit_count = len(true_hits)
    fp_count = len(fp_hits)
    profile_count = len(profiles)
    cluster_count = len(clusters)
    leak_count = len(breach_dates or [])

    # Display name consistency across profiles
    disp_names = {p.get("display_name") for p in profiles if p.get("display_name")}
    name_consensus = len(disp_names) == 1 and profile_count >= 2
    consensus_name = next(iter(disp_names)) if name_consensus else None

    return _HTML.format(
        title=f"clawithme: {safe_username}",
        username=safe_username,
        timestamp=now,
        summary_hero=_render_summary(
            safe_username, true_hit_count, fp_count,
            profile_count, cluster_count, leak_count,
            consensus_name,
        ),
        sites_table=_render_sites(true_hits, fp_hits),
        profile_cards=_render_profiles(profiles),
        cluster_section=_render_clusters(clusters, consensus_name),
        timeline_section=_render_timeline(breach_dates or []),
        chart_section=_render_charts(true_hits, clusters),
        trace_id=_fmt_esc(trace_id),
    )


def _hit_site_id(hit: dict) -> str:
    """Extract site id from a hit dict."""
    return hit.get("site_def", {}).get("id", "")


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


# ── Summary hero ─────────────────────────────────────────────

def _render_summary(
    username: str, true_hits: int, fp_count: int,
    profiles: int, clusters: int, leaks: int,
    consensus_name: str | None,
) -> str:
    """Render the top hero summary box."""
    identity_line = ""
    if consensus_name:
        identity_line = (
            f'<div style="margin-top:16px;font-size:16px;font-weight:500;color:#111">'
            f'Identity: {_esc(consensus_name)}  '
            f'<span style="font-size:12px;color:#2e7d32;background:#e8f5e9;padding:2px 8px;border-radius:4px">'
            f'✓ Confirmed across {profiles} platforms'
            f'</span></div>'
        )

    fp_note = ""
    if fp_count > 0:
        fp_note = (
            f'<span style="color:#b0b0b0;font-size:12px">'
            f' + {fp_count} SPA/redirect false positives hidden'
            f'</span>'
        )

    stats = []
    if true_hits:
        stats.append(f"{true_hits} sites")
    if profiles:
        stats.append(f"{profiles} profiles")
    if clusters:
        stats.append(f"{clusters} clusters")
    if leaks:
        stats.append(f"{leaks} leaks")

    return (
        f'<div class="summary-hero">'
        f'<h1>{_esc(username)}</h1>'
        f'{identity_line}'
        f'<div class="meta" style="margin-top:12px">'
        f'{" · ".join(stats)} &middot; {fp_note}'
        f'</div>'
        f'</div>'
    )


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
.container {{ max-width: 780px; margin: 0 auto; padding: 48px 24px; }}

h1 {{ font-size: 32px; font-weight: 700; letter-spacing: -0.6px; }}
h2 {{ font-size: 18px; font-weight: 600; color: #333; }}
h3 {{ font-size: 14px; font-weight: 500; color: #555; }}
.meta {{ color: #888; font-size: 13px; margin-top: 4px; }}
.section {{ margin-top: 40px; }}
.divider {{ border: 0; border-top: 1px solid #e5e5e5; margin: 24px 0; }}

/* ── Summary hero ───────────────────────────── */
.summary-hero {{
  background: #fff; border: 1px solid #e5e5e5; border-radius: 8px;
  padding: 32px;
}}

/* ── Sites table ────────────────────────────── */
.site-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.site-table th {{ text-align: left; padding: 10px 12px; border-bottom: 2px solid #e5e5e5; color: #555; font-weight: 500; }}
.site-table td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
.site-table .url {{ color: #555; font-size: 13px; word-break: break-all; }}
.status-ok {{ color: #0a0; font-weight: 500; }}
.status-fp {{ color: #b0b0b0; font-style: italic; }}

/* ── Profile cards ──────────────────────────── */
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }}
.card {{
  background: #fff; border: 1px solid #e5e5e5; border-radius: 8px;
  padding: 20px; transition: box-shadow 0.15s;
}}
.card:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
.card-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
.card-avatar {{
  width: 44px; height: 44px; border-radius: 50%; background: #eee;
  flex-shrink: 0; object-fit: cover;
}}
.card-site {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }}
.card-name {{ font-size: 15px; font-weight: 600; }}
.card-bio {{ font-size: 13px; color: #555; margin-top: 8px; line-height: 1.5; }}
.card-meta {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; font-size: 12px; color: #888; }}
.card-extras {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
.card-extra-tag {{
  font-size: 11px; padding: 2px 8px; background: #f5f5f5;
  border-radius: 4px; color: #555; font-family: monospace;
}}
.card-completeness {{ display: flex; align-items: center; gap: 8px; margin-top: 12px; }}
.cc-pct {{ font-family: monospace; font-size: 11px; min-width: 28px; }}
.cc-bar {{ display: inline-block; width: 60px; height: 4px; background: #f0f0f0; border-radius: 2px; overflow: hidden; }}
.cc-fill {{ display: block; height: 100%; border-radius: 2px; background: #d0d0d0; }}

/* ── Clusters ────────────────────────────────── */
.cluster {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
.cluster-hd {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
.cluster-badge {{ font-size: 12px; padding: 2px 8px; border-radius: 4px; }}
.badge-high {{ background: #e8f5e9; color: #2e7d32; }}
.badge-mid {{ background: #fff3e0; color: #e65100; }}
.badge-low {{ background: #fce4ec; color: #c62828; }}
.cluster-signals {{ display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }}
.signal-tag {{ font-size: 11px; padding: 2px 8px; background: #f5f5f5; border-radius: 4px; color: #666; font-family: monospace; }}
.cluster-list {{ font-size: 14px; display: flex; flex-wrap: wrap; gap: 6px; }}
.cluster-site {{ font-size: 12px; padding: 2px 8px; background: #f5f5f5; border-radius: 4px; }}
.cluster-evidence {{ font-size: 12px; color: #666; margin-top: 4px; padding: 2px 0; }}
.cluster-identity {{ margin-top: 12px; padding: 8px 12px; background: #e8f5e9; border-radius: 4px; font-size: 13px; color: #2e7d32; }}

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
  h1 {{ font-size: 24px; }}
}}
</style>
</head>
<body>
<div class="container">

{summary_hero}

<!-- SITES -->
<div class="section">
<h3>Discovered Sites</h3>
<hr class="divider">
{sites_table}
</div>

<!-- PROFILES -->
<div class="section">
<h3>Extracted Profiles</h3>
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

def _render_sites(true_hits: list[dict], fp_hits: list[dict]) -> str:
    """Render grouped site tables. FP hits shown collapsed with explanation."""
    if not true_hits and not fp_hits:
        return '<p style="color:#888">No sites found.</p>'

    parts = []

    # ── True hits table ──
    if true_hits:
        groups: dict[str, list[dict]] = {}
        for h in true_hits:
            cat = _hit_category(h)
            groups.setdefault(cat, []).append(h)

        cat_names = _CAT_NAMES
        summary_parts = []
        for cat in sorted(groups.keys()):
            name = cat_names.get(cat, cat.title())
            count = len(groups[cat])
            summary_parts.append(f'<span class="signal-tag">{name} {count}</span>')
        parts.append(
            '<div class="cluster-signals" style="margin-bottom:16px">'
            + "".join(summary_parts) + '</div>'
        )

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
            parts.append(
                f'<h4 style="margin-top:16px;font-size:13px;color:#666;font-weight:500">'
                f'{name}</h4>'
                f'<table class="site-table">'
                f'<thead><tr><th>Site</th><th>URL</th><th>Status</th></tr></thead>'
                f'<tbody>' + "".join(rows) + "</tbody></table>"
            )

    # ── False-positive note ──
    if fp_hits:
        fp_names = ", ".join(_esc(h.get("site_name", "?")) for h in fp_hits)
        parts.append(
            f'<details style="margin-top:16px;font-size:12px;color:#999">'
            f'<summary style="cursor:pointer">'
            f'+ {len(fp_hits)} SPA/redirect hits hidden</summary>'
            f'<p style="margin-top:4px">{fp_names} — '
            f'These sites return HTTP 200 for all usernames (SPA shell / login redirect). '
            f'Manual verification needed.</p>'
            f'</details>'
        )

    return "".join(parts)


_CAT_NAMES = {
    "social": "Social", "devtools": "Dev Tools", "forum": "Forums",
    "media": "Media", "blog": "Blogs", "gaming": "Gaming",
    "music": "Music", "ecommerce": "E-Commerce",
}


def _hit_category(hit: dict) -> str:
    return hit.get("site_def", {}).get("classification", {}).get("primary", "other")


# ── Extra field labels for profile cards ──
_EXTRA_LABELS: dict[str, str] = {
    "reputation": "Rep", "badges": "Badges",
    "twitter": "Twitter", "github": "GitHub", "linkedin": "LinkedIn",
    "website": "Website", "gender": "Gender", "verified": "Verified",
}


def _render_profiles(profiles: list[dict]) -> str:
    if not profiles:
        return '<p style="color:#888">No profiles extracted.</p>'

    _PROFILE_FIELDS = ["display_name", "bio", "location", "avatar_url", "followers"]
    cards = []
    for p in profiles:
        site_id = p.get("site_id", "?")
        name = p.get("display_name") or site_id
        bio = p.get("bio", "") or ""
        location = p.get("location", "") or ""

        # Bio
        bio_html = f'<div class="card-bio">{_esc(bio[:200])}</div>' if bio.strip() else ""

        # Avatar
        avatar_url = p.get("avatar_url", "")
        if avatar_url:
            avatar_html = (
                f'<img class="card-avatar" src="{_esc(avatar_url)}"'
                f' alt="" loading="lazy">'
            )
        else:
            avatar_html = '<div class="card-avatar"></div>'

        # Meta (location, followers, following, joined)
        meta_parts = []
        if location:
            meta_parts.append(f"📍 {_esc(location)}")
        followers = p.get("follower_count")
        if followers is not None:
            meta_parts.append(f"👥 {followers:,}" if isinstance(followers, int) else f"👥 {followers}")
        following = p.get("following_count")
        if following is not None:
            meta_parts.append(f"↗ {following:,}" if isinstance(following, int) else f"↗ {following}")
        joined = p.get("joined_date")
        if joined:
            meta_parts.append(f"📅 {joined}")
        meta_html = f'<div class="card-meta">{" · ".join(meta_parts)}</div>' if meta_parts else ""

        # Extra fields (reputation, badges, links, gender, verified)
        extra = p.get("extra", {})
        extra_tags = []
        if extra:
            for key, label in _EXTRA_LABELS.items():
                val = extra.get(key)
                if val is None or val == "":
                    continue
                if isinstance(val, dict):
                    # badges: {bronze: 9355, silver: 9316, gold: 895}
                    parts = []
                    for bk, bv in val.items():
                        parts.append(f"{bk}:{bv:,}" if isinstance(bv, int) else f"{bk}:{bv}")
                    display = " ".join(parts)
                    extra_tags.append(f'<span class="card-extra-tag">{_esc(display)}</span>')
                elif isinstance(val, bool):
                    if val:
                        extra_tags.append(f'<span class="card-extra-tag">✓ {label}</span>')
                else:
                    extra_tags.append(f'<span class="card-extra-tag">{label}: {_esc(str(val)[:50])}</span>')
        extra_html = f'<div class="card-extras">{"".join(extra_tags)}</div>' if extra_tags else ""

        # Completeness
        filled = sum(1 for f in _PROFILE_FIELDS if p.get(f))
        pct = int(filled / len(_PROFILE_FIELDS) * 100)
        pct_color = "#171717" if pct >= 60 else ("#808080" if pct >= 30 else "#b0b0b0")
        completeness_html = (
            f'<div class="card-completeness">'
            f'<span class="cc-pct" style="color:{pct_color}">{pct}%</span>'
            f'<span class="cc-bar"><span class="cc-fill" style="width:{pct}%"></span></span>'
            f'</div>'
        )

        cards.append(
            f'<div class="card">'
            f'<div class="card-header">'
            f'{avatar_html}'
            f'<div><div class="card-name">{_esc(name)}</div>'
            f'<div class="card-site">{_esc(site_id)}</div></div>'
            f'</div>'
            f'{bio_html}{extra_html}{completeness_html}{meta_html}'
            f'</div>'
        )
    return '<div class="card-grid">' + "".join(cards) + "</div>"


def _render_clusters(clusters: list, consensus_name: str | None = None) -> str:
    if not clusters:
        return '<p style="color:#888">No identity clusters found.</p>'
    blocks = []
    for i, c in enumerate(clusters, 1):
        sites = ", ".join(_esc(p.site_id) for p in c.profiles)

        # Confidence badge
        conf = c.confidence
        if conf >= 0.9:
            badge_cls = "badge-high"
        elif conf >= 0.7:
            badge_cls = "badge-mid"
        else:
            badge_cls = "badge-low"

        sig_tags = "".join(
            f'<span class="signal-tag">{_esc(s)}</span>' for s in c.signals
        )

        # Identity consensus highlight
        identity_html = ""
        if consensus_name and len(c.profiles) >= 2:
            identity_html = (
                f'<div class="cluster-identity">'
                f'✓ Identity confirmed: all profiles share name "{_esc(consensus_name)}"'
                f'</div>'
            )

        evidence_lines = []
        if c.evidence:
            for sig, details in c.evidence.items():
                for d in details[:3]:
                    evidence_lines.append(
                        f'<div class="cluster-evidence">'
                        f'<span class="signal-tag">{_esc(sig)}</span> '
                        f'{_esc(_redact_evidence(sig, d))}'
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
            f'{identity_html}'
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
    """Redact PII in cluster evidence details."""
    if signal == "email":
        if "@" in detail:
            local, domain = detail.split("@", 1)
            return f"{local[0]}***@{domain}" if local else "***@…"
        return "***"
    if signal == "phone":
        return f"***{detail[-4:]}" if len(detail) >= 4 else "***"
    return detail


def _render_timeline(dates: list[str]) -> str:
    if not dates:
        return ""
    unique_dates = sorted(set(dates), reverse=True)[:20]
    dots = []
    for d in unique_dates:
        label = d if len(d) <= 10 else d[:10]
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


def _render_charts(true_hits: list[dict], clusters: list) -> str:
    if not true_hits and not clusters:
        return ""

    sections: list[str] = []

    # Platform distribution
    if true_hits:
        cat_counts: dict[str, int] = {}
        for h in true_hits:
            cat = _hit_category(h)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        sorted_cats = sorted(cat_counts.items(), key=lambda x: -x[1])
        max_count = max(c for _, c in sorted_cats) if sorted_cats else 1

        bars = []
        for i, (cat, count) in enumerate(sorted_cats):
            pct = int(count / max_count * 100)
            color = _CHART_COLORS[i % len(_CHART_COLORS)]
            name = _CAT_NAMES.get(cat, cat.title())
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

    # Correlation signals
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
