"""Phase 5 — Panorama report generator.

Produces a self-contained HTML report from search results.
Geist-style grayscale design.

v3 improvements (2026-05-05):
- Geist font loaded from CDN
- Color tokens aligned to Geist spec (#171717/#4d4d4d/#808080/#b0b0b0)
- h2 section headers, proper heading hierarchy
- Hero stats: big numbers + labels
- Donut ring completeness on profile cards
- Single-hue chart bars (opacity-scaled)
- Vertical rhythm spacing
- Human-readable summary auto-generated from profile data
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from clawithme.signals.correlation import Cluster


# ── Known false-positive sites ──
_SPA_SITES = frozenset({"sspai", "twitch", "twitter", "weibo", "instagram", "slideshare"})


def _is_false_positive(site_id: str) -> bool:
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
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    safe_username = _fmt_esc(username)

    true_hits = [h for h in hits if not _is_false_positive(_hit_site_id(h))]
    fp_hits = [h for h in hits if _is_false_positive(_hit_site_id(h))]

    true_hit_count = len(true_hits)
    fp_count = len(fp_hits)
    profile_count = len(profiles)
    cluster_count = len(clusters)
    leak_count = len(breach_dates or [])

    disp_names = {p.get("display_name") for p in profiles if p.get("display_name")}
    name_consensus = len(disp_names) == 1 and profile_count >= 2
    consensus_name = next(iter(disp_names)) if name_consensus else None

    # Auto-summary paragraph
    auto_summary = _compose_summary(profiles)

    return _HTML.format(
        title=f"clawithme: {safe_username}",
        username=safe_username,
        timestamp=now,
        summary_hero=_render_summary(
            safe_username, true_hit_count, fp_count,
            profile_count, cluster_count, leak_count,
            consensus_name, auto_summary,
        ),
        sites_table=_render_sites(true_hits, fp_hits),
        profile_cards=_render_profiles(profiles),
        cluster_section=_render_clusters(clusters, consensus_name),
        timeline_section=_render_timeline(breach_dates or []),
        chart_section=_render_charts(true_hits, clusters),
        trace_id=_fmt_esc(trace_id),
    )


def _hit_site_id(hit: dict) -> str:
    return hit.get("site_def", {}).get("id", "")


def export_json(
    hits: list[dict], profiles: list[dict], clusters: list,
    username: str, *, trace_id: str = "",
) -> str:
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
            {"profiles": [asdict(p) for p in c.profiles], "confidence": c.confidence, "signals": c.signals}
            if isinstance(c, Cluster) else c for c in clusters
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Auto-summary composition ──────────────────────────────────

def _compose_summary(profiles: list[dict]) -> str:
    """Compose a human-readable paragraph from profile data."""
    if not profiles:
        return "No public profiles found."

    parts = []

    # Name
    names = [p.get("display_name") for p in profiles if p.get("display_name")]
    name = max(set(names), key=names.count) if names else "This person"
    parts.append(_esc(name))

    # Bio/role
    bios = [p.get("bio", "") for p in profiles if p.get("bio") and len(p.get("bio", "")) > 5]
    if bios:
        snippet = _truncate_sentence(bios[0], 120)
        parts.append(f"is {snippet}")
    else:
        for p in profiles:
            role = (p.get("extra", {}) or {}).get("role") or (p.get("extra", {}) or {}).get("title")
            if role:
                parts.append(f"is {_esc(str(role)[:80])}")
                break

    # Location
    locs = [p.get("location") for p in profiles if p.get("location")]
    if locs:
        parts.append(f"based in {_esc(locs[0])}")

    parts[-1] = parts[-1] + "."

    # Platforms
    platform_ids = list(dict.fromkeys(p.get("site_id", "?") for p in profiles))
    if platform_ids:
        names = ", ".join(_esc(pid) for pid in platform_ids)
        parts.append(f"Active on: {names}.")

    # Contact
    emails = [p.get("email") for p in profiles if p.get("email")]
    phones = [p.get("phone") for p in profiles if p.get("phone")]
    if emails or phones:
        contact = []
        if emails:
            contact.append(f"Email: {_esc(emails[0])}")
        if phones:
            contact.append(f"Phone: {_esc(phones[0])}")
        parts.append("Contact: " + ", ".join(contact) + ".")
    else:
        parts.append("No email or phone found in public profiles.")

    return " ".join(parts)


def _truncate_sentence(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rstrip()
    # Try to cut at last sentence break
    for sep in (". ", "! ", "? ", ".", "!", "?"):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:
            return cut[:idx + len(sep.rstrip())]
    return cut + "…"


# ── Summary hero ─────────────────────────────────────────────

def _render_summary(
    username: str, true_hits: int, fp_count: int,
    profiles: int, clusters: int, leaks: int,
    consensus_name: str | None, auto_summary: str,
) -> str:
    identity_line = ""
    if consensus_name:
        identity_line = (
            f'<div class="hero-identity">'
            f'<span class="hero-identity-name">{_esc(consensus_name)}</span>'
            f'<span class="hero-identity-badge">✓ Confirmed across {profiles} platforms</span>'
            f'</div>'
        )

    fp_note = ""
    if fp_count > 0:
        fp_note = f' +{fp_count} SPA hidden'

    items = []
    if true_hits:
        items.append(f'<div class="hero-stat"><span class="hero-stat-value">{true_hits}</span><span class="hero-stat-label">Sites</span></div>')
    if profiles:
        items.append(f'<div class="hero-stat"><span class="hero-stat-value">{profiles}</span><span class="hero-stat-label">Profiles</span></div>')
    if clusters:
        items.append(f'<div class="hero-stat"><span class="hero-stat-value">{clusters}</span><span class="hero-stat-label">Clusters</span></div>')
    if leaks:
        items.append(f'<div class="hero-stat"><span class="hero-stat-value">{leaks}</span><span class="hero-stat-label">Leaks</span></div>')
    stats_html = f'<div class="hero-stats">{"".join(items)}</div>' if items else ""

    return (
        f'<div class="summary-hero">'
        f'<h1>{_esc(username)}</h1>'
        f'{identity_line}'
        f'<p class="hero-summary">{auto_summary}</p>'
        f'{stats_html}'
        f'<div class="meta">{fp_note}</div>'
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
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link href="https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/font.min.css" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Geist', 'Geist Fallback', system-ui, -apple-system, sans-serif;
  color: #171717; background: #fafafa; line-height: 1.6;
}}
.container {{ max-width: 780px; margin: 0 auto; padding: 48px 24px 56px; }}

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
  font: 500 11px/1 'Geist Mono', ui-monospace, monospace;
  padding: 2px 8px; border-radius: 999px;
  background: #171717; color: white; flex-shrink: 0;
}}
.section-header h2 {{ font: 600 15px/1.3 'Geist', sans-serif; color: #171717; }}
.section-container {{
  padding: 28px; border-radius: 8px;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.08), 0px 2px 2px rgba(0,0,0,0.04);
  overflow: hidden; margin-bottom: 8px;
}}

/* ── Summary hero ───────────────────────────── */
.summary-hero {{
  background: #fff; border-radius: 10px;
  padding: 36px 36px 28px;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.08), 0px 2px 2px rgba(0,0,0,0.04);
}}
.hero-summary {{
  font-size: 15px; color: #4d4d4d; line-height: 1.7; margin-top: 12px; max-width: 640px;
}}
.hero-identity {{
  display: flex; align-items: center; gap: 10px; margin-top: 12px;
}}
.hero-identity-name {{ font-size: 18px; font-weight: 600; color: #171717; }}
.hero-identity-badge {{
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: #e8f5e9; color: #2e7d32;
}}
.hero-stats {{
  display: flex; gap: 28px; flex-wrap: wrap; margin-top: 20px;
}}
.hero-stat {{
  display: flex; align-items: baseline; gap: 6px;
}}
.hero-stat-value {{
  font-size: 28px; font-weight: 600; color: #171717;
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-variant-numeric: tabular-nums; line-height: 1;
}}
.hero-stat-label {{
  font-size: 12px; color: #808080; text-transform: uppercase; letter-spacing: 0.5px;
}}

/* ── Sites table ────────────────────────────── */
.site-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.site-table th {{ text-align: left; padding: 10px 12px; border-bottom: 2px solid #e5e5e5; color: #4d4d4d; font-weight: 500; }}
.site-table td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
.site-table .url {{ color: #808080; font-size: 13px; word-break: break-all; }}
.status-ok {{ color: #171717; font-weight: 500; font-family: 'Geist Mono', monospace; font-size: 13px; }}
.status-fp {{ color: #b0b0b0; font-style: italic; }}
.cat-label {{
  font-size: 13px; font-weight: 500; color: #808080;
  margin-top: 20px; text-transform: uppercase; letter-spacing: 0.5px;
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
  border-radius: 4px; color: #4d4d4d; font-family: 'Geist Mono', monospace;
}}
.card-completeness {{ display: flex; align-items: center; gap: 0; margin-top: 12px; }}

/* ── Donut ring ─────────────────────────────── */
.cc-donut {{
  width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
  background: conic-gradient(
    #171717 0deg calc(var(--pct) * 3.6deg),
    #f0f0f0 calc(var(--pct) * 3.6deg) 360deg
  );
  position: relative;
}}
.cc-donut::after {{
  content: attr(data-pct);
  position: absolute; inset: 4px; border-radius: 50%;
  background: #fff;
  display: flex; align-items: center; justify-content: center;
  font-family: 'Geist Mono', monospace; font-size: 10px; font-weight: 600; color: #171717;
}}

/* ── Clusters ────────────────────────────────── */
.cluster {{
  background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.08), 0px 2px 2px rgba(0,0,0,0.04);
}}
.cluster-hd {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
.cluster-hd strong {{ font-size: 15px; }}
.cluster-badge {{ font-size: 12px; padding: 2px 8px; border-radius: 4px; }}
.badge-high {{ background: #e8f5e9; color: #2e7d32; }}
.badge-mid {{ background: #fff3e0; color: #e65100; }}
.badge-low {{ background: #fce4ec; color: #c62828; }}
.cluster-signals {{ display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }}
.signal-tag {{
  font-size: 11px; padding: 2px 8px; background: #f5f5f5;
  border-radius: 4px; color: #4d4d4d; font-family: 'Geist Mono', monospace;
}}
.cluster-list {{ font-size: 14px; display: flex; flex-wrap: wrap; gap: 6px; }}
.cluster-site {{ font-size: 12px; padding: 2px 8px; background: #f5f5f5; border-radius: 4px; }}
.cluster-evidence {{ font-size: 12px; color: #4d4d4d; margin-top: 4px; padding: 2px 0; }}
.cluster-identity {{
  margin-top: 12px; padding: 8px 12px; background: #e8f5e9;
  border-radius: 4px; font-size: 13px; color: #2e7d32;
}}

/* ── Footer ──────────────────────────────────── */
.footer {{ margin-top: 56px; padding-top: 16px; border-top: 1px solid #e5e5e5; font-size: 12px; color: #b0b0b0; }}

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
.timeline-date {{ font-family: 'Geist Mono', monospace; font-size: 11px; color: #808080; display: block; }}

/* ── Charts ──────────────────────────────────── */
.chart-row {{ display: flex; gap: 24px; flex-wrap: wrap; }}
.chart-col {{ flex: 1; min-width: 280px; }}
.chart-title {{ font-size: 13px; font-weight: 500; color: #4d4d4d; margin-bottom: 12px; letter-spacing: 0.02em; }}
.chart-bar-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
.chart-bar-label {{ font-size: 12px; color: #4d4d4d; min-width: 80px; text-align: right; flex-shrink: 0; }}
.chart-bar-track {{ flex: 1; height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden; }}
.chart-bar-fill {{ height: 100%; border-radius: 4px; background: #171717; opacity: var(--bar-opacity, 1); }}
.chart-bar-count {{
  font-family: 'Geist Mono', monospace; font-size: 11px; color: #808080; min-width: 24px;
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
<div class="section-header"><span class="badge">01</span><h2>Discovered Sites</h2></div>
{sites_table}
</div></div>

<div class="section"><div class="section-container">
<div class="section-header"><span class="badge">02</span><h2>Extracted Profiles</h2></div>
{profile_cards}
</div></div>

<div class="section"><div class="section-container">
<div class="section-header"><span class="badge">03</span><h2>Identity Clusters</h2></div>
{cluster_section}
</div></div>

{timeline_section}

<div class="section"><div class="section-container">
<div class="section-header"><span class="badge">04</span><h2>Analytics</h2></div>
{chart_section}
</div></div>

<div class="footer">
  clawithme &middot; trace: {trace_id}
</div>

</div>
</body>
</html>"""


# ── Render helpers ──────────────────────────────────────────────

def _render_sites(true_hits: list[dict], fp_hits: list[dict]) -> str:
    if not true_hits and not fp_hits:
        return '<p style="color:#808080">No sites found.</p>'

    parts = []

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
            '<div class="cluster-signals" style="margin:20px 0 0">'
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
                f'<div class="cat-label">{name}</div>'
                f'<table class="site-table">'
                f'<thead><tr><th>Site</th><th>URL</th><th>Status</th></tr></thead>'
                f'<tbody>' + "".join(rows) + "</tbody></table>"
            )

    if fp_hits:
        fp_names = ", ".join(_esc(h.get("site_name", "?")) for h in fp_hits)
        parts.append(
            f'<details style="margin-top:16px;font-size:12px;color:#b0b0b0">'
            f'<summary style="cursor:pointer">'
            f'+ {len(fp_hits)} SPA/redirect hits hidden</summary>'
            f'<p style="margin-top:4px">{fp_names} &mdash; '
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


_EXTRA_LABELS: dict[str, str] = {
    "reputation": "Rep", "badges": "Badges",
    "twitter": "Twitter", "github": "GitHub", "linkedin": "LinkedIn",
    "website": "Website", "gender": "Gender", "verified": "Verified",
}


def _render_profiles(profiles: list[dict]) -> str:
    if not profiles:
        return '<p style="color:#808080;margin-top:20px">No profiles extracted.</p>'

    _PROFILE_FIELDS = ["display_name", "bio", "location", "avatar_url", "followers"]
    cards = []
    for p in profiles:
        site_id = p.get("site_id", "?")
        name = p.get("display_name") or site_id
        bio = p.get("bio", "") or ""
        location = p.get("location", "") or ""

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

        # Meta
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

        # Extra fields
        extra = p.get("extra", {})
        extra_tags = []
        if extra:
            for key, label in _EXTRA_LABELS.items():
                val = extra.get(key)
                if val is None or val == "":
                    continue
                if isinstance(val, dict):
                    parts_list = []
                    for bk, bv in val.items():
                        parts_list.append(f"{bk}:{bv:,}" if isinstance(bv, int) else f"{bk}:{bv}")
                    display = " ".join(parts_list)
                    extra_tags.append(f'<span class="card-extra-tag">{_esc(display)}</span>')
                elif isinstance(val, bool):
                    if val:
                        extra_tags.append(f'<span class="card-extra-tag">✓ {label}</span>')
                else:
                    extra_tags.append(f'<span class="card-extra-tag">{label}: {_esc(str(val)[:50])}</span>')
        extra_html = f'<div class="card-extras">{"".join(extra_tags)}</div>' if extra_tags else ""

        # Donut ring completeness
        filled = sum(1 for f in _PROFILE_FIELDS if p.get(f))
        pct = int(filled / len(_PROFILE_FIELDS) * 100)
        donut_html = (
            f'<div class="cc-donut" style="--pct:{pct}" data-pct="{pct}%"></div>'
        )

        cards.append(
            f'<div class="card">'
            f'<div class="card-header">'
            f'{avatar_html}'
            f'<div style="flex:1"><div class="card-name">{_esc(name)}</div>'
            f'<div class="card-site">{_esc(site_id)}</div></div>'
            f'{donut_html}'
            f'</div>'
            f'{bio_html}{extra_html}{meta_html}'
            f'</div>'
        )
    return '<div class="card-grid">' + "".join(cards) + "</div>"


def _render_clusters(clusters: list, consensus_name: str | None = None) -> str:
    if not clusters:
        return '<p style="color:#808080;margin-top:20px">No identity clusters found.</p>'
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
            f'<span class="signal-tag">{_esc(s)}</span>' for s in c.signals
        )

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
    return '<div style="margin-top:20px">' + "".join(blocks) + "</div>"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_esc(s: str) -> str:
    return s.replace("{", "{{").replace("}", "}}")


def _redact_evidence(signal: str, detail: str) -> str:
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
        '<div class="section"><div class="section-container">'
        '<div class="section-header"><span class="badge">05</span><h2>Breach Timeline</h2></div>'
        f'<div class="timeline"><div class="timeline-track">{"".join(dots)}</div></div>'
        '</div></div>'
    )


def _render_charts(true_hits: list[dict], clusters: list) -> str:
    if not true_hits and not clusters:
        return '<p style="color:#808080;margin-top:20px">No analytics data.</p>'

    sections: list[str] = []

    # Platform distribution chart
    if true_hits:
        cat_counts: dict[str, int] = {}
        for h in true_hits:
            cat = _hit_category(h)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        sorted_cats = sorted(cat_counts.items(), key=lambda x: -x[1])
        max_count = max(c for _, c in sorted_cats) if sorted_cats else 1

        bars = []
        for cat, count in sorted_cats:
            pct = int(count / max_count * 100)
            opacity = 0.35 + 0.65 * (count / max_count)
            name = _CAT_NAMES.get(cat, cat.title())
            bars.append(
                f'<div class="chart-bar-row">'
                f'<span class="chart-bar-label">{_esc(name)}</span>'
                f'<span class="chart-bar-track">'
                f'<span class="chart-bar-fill" style="width:{pct}%;--bar-opacity:{opacity:.2f}"></span>'
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
            for sig, count in sorted_sigs:
                pct = int(count / max_sig * 100)
                opacity = 0.35 + 0.65 * (count / max_sig)
                bars.append(
                    f'<div class="chart-bar-row">'
                    f'<span class="chart-bar-label">{_esc(sig)}</span>'
                    f'<span class="chart-bar-track">'
                    f'<span class="chart-bar-fill" style="width:{pct}%;--bar-opacity:{opacity:.2f}"></span>'
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
        return '<p style="color:#808080;margin-top:20px">No analytics data.</p>'

    return (
        f'<div class="chart-row" style="margin-top:20px">{"".join(sections)}</div>'
    )
