"""Phase 5 — Panorama report generator.

Produces a self-contained HTML report from search results.
Geist-style grayscale design.

This module is a thin coordinator — the heavy lifting is in:
    report/i18n.py       — bilingual strings and constants
    report/template.py   — Geist HTML template
    report/renderers.py  — all _render_*() helper functions
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from clawithme.report.i18n import _STRINGS, _CONFIDENCE_THRESHOLDS
from clawithme.report.template import _HTML, _fmt_esc
from clawithme.report.renderers import (
    _compute_actions,
    _compute_hit_confidence,
    _compose_summary,
    _hit_site_id,
    _is_wrong_person,
    _pick_display_name,
    _render_actions,
    _render_charts,
    _render_clusters,
    _render_dropped_note,
    _render_profiles,
    _render_sites,
    _render_summary,
    _render_timeline,
)
from clawithme.signals.correlation import Cluster

# Avatar fallback color palette (Vercel-friendly, muted)
_AVATAR_COLORS = [
    "#1e293b", "#334155", "#475569", "#64748b",
    "#0f172a", "#3b82f6", "#6366f1", "#059669",
    "#0891b2", "#2563eb", "#7c3aed", "#db2777",
    "#ea580c", "#65a30d", "#0d9488", "#9333ea",
]


def generate_report(  # noqa: PLR0913
    hits: list[dict],
    profiles: list[dict],
    clusters: list,
    username: str,
    *,
    trace_id: str = "",
    breach_dates: list[str] | None = None,
    leak_records: list | None = None,
    lang: str = "zh",
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    safe_username = _fmt_esc(username)

    profile_by_site: dict[str, dict] = {}
    for p in profiles:
        sid = p.get("site_id")
        if sid:
            profile_by_site[sid] = p

    hit_data = []
    for h in hits:
        c = _compute_hit_confidence(h, profile_by_site, username)
        wp = _is_wrong_person(h, profile_by_site, username)
        hit_data.append((h, c, wp))

    confirmed_hits = [h for h, c, wp in hit_data if c >= _CONFIDENCE_THRESHOLDS["confirmed"]]
    uncertain_hits = [h for h, c, wp in hit_data if _CONFIDENCE_THRESHOLDS["uncertain"] <= c < _CONFIDENCE_THRESHOLDS["confirmed"]]
    dropped_hits = [h for h, c, wp in hit_data if c == 0]
    true_hits = confirmed_hits + uncertain_hits

    true_hit_count = len(true_hits)
    fp_count = sum(1 for h, c, wp in hit_data if c == 0)
    profile_count = len(profiles)
    # Only count multi-profile clusters (real cross-platform matches)
    cluster_count = sum(1 for c in clusters if hasattr(c, 'profiles') and len(c.profiles) >= 2)
    leak_count = len(breach_dates or [])

    wrong_person_ids: set[str] = {_hit_site_id(h) for h, c, wp in hit_data if wp}

    disp_names = {p.get("display_name") for p in profiles if p.get("display_name")}
    name_consensus = len(disp_names) == 1 and profile_count >= 2
    consensus_name = next(iter(disp_names)) if name_consensus else None

    auto_summary = _compose_summary(profiles, lang=lang)
    display_title = _pick_display_name(profiles, safe_username)

    # ── Avatar: use first profile's avatar_url, fallback to initials ──
    avatar_url = ""
    for p in profiles:
        if p.get("avatar_url"):
            avatar_url = p["avatar_url"]
            break
    fallback_text = display_title[0].upper() if display_title else safe_username[0].upper()
    color_idx = sum(ord(c) for c in username) % len(_AVATAR_COLORS)
    avatar_color = _AVATAR_COLORS[color_idx]

    confirmed_table = _render_sites(lang, confirmed_hits, "confirmed",
                                    wrong_person_ids=wrong_person_ids,
                                    profile_by_site=profile_by_site,
                                    username=safe_username)
    uncertain_section = _render_sites(lang, uncertain_hits, "uncertain",
                                      wrong_person_ids=wrong_person_ids,
                                      profile_by_site=profile_by_site,
                                      username=safe_username)
    dropped_note = _render_dropped_note(lang, len(dropped_hits))

    LANG = _STRINGS.get(lang, _STRINGS["en"])
    if not confirmed_table and not uncertain_section:
        confirmed_table = f'<p style="color:#808080">{LANG["no_sites"]}</p>'

    return _HTML.format(
        title=LANG["title"].format(username=safe_username),
        html_lang="zh" if lang == "zh" else "en",
        sec_sites=LANG["sec_sites"],
        sec_profiles=LANG["sec_profiles"],
        sec_clusters=LANG["sec_clusters"],
        sec_analytics=LANG["sec_analytics"],
        cluster_explain=LANG["cluster_explain"],
        footer_brand_line=LANG["footer_brand"],
        footer_generated=LANG["footer_generated"],
        footer_hover_hint=LANG["footer_hover_hint"],
        footer_spa=LANG["footer_spa"],
        footer_completeness=LANG["footer_completeness"],
        footer_cluster=LANG["footer_cluster"],
        username=safe_username,
        timestamp=now,
        summary_hero=_render_summary(lang,
            display_title, safe_username, true_hit_count, fp_count,
            profile_count, cluster_count, leak_count,
            consensus_name, auto_summary,
            avatar_url=avatar_url,
            avatar_fallback=fallback_text,
            avatar_color=avatar_color,
        ),
        confirmed_table=confirmed_table,
        uncertain_section=uncertain_section,
        dropped_note=dropped_note,
        profile_cards=_render_profiles(lang, profiles, true_hits),
        cluster_section=_render_clusters(lang, clusters, consensus_name, true_hits),
        timeline_section=_render_timeline(lang, breach_dates or []),
        chart_section=_render_charts(lang, true_hits, clusters, profiles),
        actions_section=_render_actions(
            _compute_actions(profiles, leak_records or [], clusters, true_hits, lang=lang),
            lang=lang,
        ),
        trace_id=_fmt_esc(trace_id),
    )


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
            "clusters": sum(1 for c in clusters if len(getattr(c, 'profiles', [])) >= 2),
        },
        "hits": hits,
        "profiles": profiles,
        "clusters": [
            {"profiles": [asdict(p) for p in c.profiles], "confidence": c.confidence, "signals": c.signals}
            if isinstance(c, Cluster) else c for c in clusters
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def export_pdf(
    hits: list[dict], profiles: list[dict], clusters: list,
    username: str, *, trace_id: str = "", breach_dates: list[str] | None = None,
) -> bytes:
    """Generate a self-contained PDF report via WeasyPrint.

    Renders the same Geist HTML as generate_report() and converts to PDF.
    Returns raw PDF bytes — caller writes to file.

    Raises ImportError if weasyprint is not installed.
    Raises OSError if WeasyPrint system libraries (Pango, GObject) are missing.
    """
    from weasyprint import HTML

    html = generate_report(
        hits, profiles, clusters, username,
        trace_id=trace_id, breach_dates=breach_dates or [],
    )
    return HTML(string=html).write_pdf()


def export_markdown(
    hits: list[dict], profiles: list[dict], clusters: list,
    username: str, *, trace_id: str = "", breach_dates: list[str] | None = None,
    lang: str = "zh",
) -> str:
    """Generate a plain Markdown report."""
    from clawithme.report.i18n import L

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    _sep = lambda: lines.append("")

    # ── Header ──
    lines.append(f"# clawithme Report: {username}")
    _sep()
    lines.append(f"Generated: {now}  |  trace: {trace_id}")
    _sep()
    lines.append("---")
    _sep()

    # ── Summary ──
    leak_count = len(breach_dates or [])
    lines.append("## Summary")
    _sep()
    lines.append(f"- **Sites found:** {len(hits)}")
    lines.append(f"- **Profiles extracted:** {len(profiles)}")
    lines.append(f"- **Cross-platform matches:** {sum(1 for c in clusters if len(getattr(c, 'profiles', [])) >= 2)}")
    lines.append(f"- **Leak records:** {leak_count}")
    _sep()
    lines.append("---")
    _sep()

    # ── Sites Found ──
    lines.append("## Sites Found")
    _sep()
    if hits:
        lines.append("| Site | URL | Status |")
        lines.append("|------|-----|--------|")
        for h in hits:
            sid = h.get("site_name", h.get("site_id", "?"))
            url = h.get("url", "")
            status = h.get("status", "")
            status_str = f"{status} ✅" if status == 200 else str(status)
            lines.append(f"| {sid} | {url} | {status_str} |")
    else:
        lines.append("No sites found.")
    _sep()
    lines.append("---")
    _sep()

    # ── Profiles ──
    lines.append("## Profiles")
    _sep()
    if profiles:
        for p in profiles:
            sid = p.get("site_id", "?")
            uname = p.get("username", "")
            dname = p.get("display_name") or ""
            lines.append(f"### {sid}" + (f" — {dname}" if dname else ""))
            _sep()
            if uname:
                lines.append(f"- **Username:** {uname}")
            if dname:
                lines.append(f"- **Display name:** {dname}")
            if p.get("location"):
                lines.append(f"- **Location:** {p['location']}")
            if p.get("bio"):
                bio = p["bio"][:200]
                lines.append(f"- **Bio:** {bio}")
            if p.get("email"):
                lines.append(f"- **Email:** {p['email']}")
            if p.get("phone"):
                lines.append(f"- **Phone:** {p['phone']}")
            if p.get("joined_date"):
                lines.append(f"- **Joined:** {p['joined_date']}")
            if p.get("follower_count") is not None:
                lines.append(f"- **Followers:** {p['follower_count']}")
            if p.get("following_count") is not None:
                lines.append(f"- **Following:** {p['following_count']}")
            if p.get("post_count") is not None:
                lines.append(f"- **Posts:** {p['post_count']}")
            _sep()
    else:
        lines.append("No profiles extracted.")
        _sep()
    lines.append("---")
    _sep()

    # ── Identity Clusters ──
    lines.append("## Identity Clusters")
    _sep()
    if clusters:
        for i, c in enumerate(clusters, 1):
            pct = int(c.confidence * 100)
            site_names = ", ".join(p.site_id for p in c.profiles)
            lines.append(f"### Cluster {i}: {site_names}")
            lines.append(f"- **Confidence:** {pct}%")
            if c.signals:
                sig_list = ", ".join(c.signals)
                lines.append(f"- **Signals:** {sig_list}")
            if c.evidence:
                lines.append("- **Evidence:**")
                for sig, details in c.evidence.items():
                    for det in details:
                        # Strip siteA ↔ siteB: prefix for cleaner markdown
                        display = det
                        if ": " in det and " ↔ " in det:
                            display = det.split(": ", 1)[1]
                        # Redact emails
                        if sig == "email" and "@" in display:
                            local, domain = display.split("@", 1)
                            display = f"{local[0]}***@{domain}" if local else display
                        elif sig == "phone":
                            display = f"***{display[-4:]}" if len(display) >= 4 else display
                        lines.append(f"  - {sig}: {display}")
            _sep()
    else:
        lines.append("No identity clusters found.")
        _sep()
    lines.append("---")
    _sep()

    # ── Leak Records ──
    lines.append("## Leak Records")
    _sep()
    if breach_dates:
        lines.append(f"Total breach events: {len(breach_dates)}")
        _sep()
        # Collect unique dates for timeline
        unique_dates = sorted(set(breach_dates), reverse=True)[:20]
        if unique_dates:
            lines.append("### Breach Timeline")
            for d in unique_dates:
                lines.append(f"- {d}")
            _sep()
    else:
        lines.append("No leak records found.")
        _sep()

    lines.append("---")
    _sep()
    lines.append(f"*Report generated by clawithme at {now}*")

    return "\n".join(lines)


# Re-export helpers for other modules (e.g. web/app.py)
__all__ = [
    "generate_report",
    "export_json",
    "export_pdf",
    "export_markdown",
    "_compute_hit_confidence",
    "_is_wrong_person",
    "_hit_site_id",
]
