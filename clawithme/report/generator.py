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
from urllib.parse import urlparse

from clawithme.signals.correlation import Cluster

# ── i18n strings ────────────────────────────────────────────────
_STRINGS = {
    "zh": {
        "title": "CLAWITHME 身份报告：{username}",
        "sec_sites": "发现站点",
        "sec_profiles": "提取资料",
        "sec_clusters": "身份关联",
        "sec_analytics": "分析",
        "sec_timeline": "泄露时间线",
        "cluster_explain": "通过用户名相似度、共享邮箱、电话或头像哈希等匹配信号，将可能属于同一人的资料分组。置信度越高，单一身份的证据越强。",
        "stat_sites": "站点",
        "stat_profiles": "资料",
        "stat_clusters": "群集",
        "stat_leaks": "泄露",
        "identity_confirmed_across": "✓ 已在 {n} 个平台确认",
        "cluster_identity_confirmed": '✓ 身份确认：所有资料共享名称 "{name}"',
        "th_site": "站点",
        "th_url": "URL",
        "th_status": "状态",
        "no_sites": "未发现站点。",
        "no_profiles": "未提取到资料。",
        "no_clusters": "未发现身份关联。",
        "no_analytics": "无分析数据。",
        "fp_hits_summary": "+ {n} 未验证命中 — 这是什么？",
        "field_username": "用户名",
        "field_display_name": "显示名称",
        "field_joined_date": "加入时间",
        "field_post_count": "帖子",
        "field_follower_count": "粉丝",
        "field_following_count": "关注",
        "field_avatar_url": "头像链接",
        "field_bio": "简介",
        "field_location": "位置",
        "field_email": "邮箱",
        "field_phone": "电话",
        "completeness_pct": "{pct}% 完整度",
        "completeness_title": "资料完整度 — 填充的关键身份字段 (名称, 简介, 位置, 头像, 粉丝) 百分比",
        "full_profile_data": "完整资料",
        "chart_platform_dist": "平台分布",
        "chart_platform_dist_sub": "按类别分布的发现站点",
        "chart_correlation": "关联信号",
        "chart_correlation_sub": "用于关联身份资料匹配的信号",
        "chart_radar": "分类覆盖雷达",
        "chart_radar_sub": "按站点分类评估身份数字足迹分布",
        "chart_summary_sites": "{total} 站点，分布在 {cats} 个类别",
        "footer_brand": "CLAWITHME — OSINT 身份全景",
        "footer_generated": "报告生成时间",
        "footer_hover_hint": "悬停虚线下划线查看说明。",
        "footer_spa": "SPA = 单页应用，需浏览器渲染。",
        "footer_completeness": "资料完整度 = 关键身份字段填充百分比。",
        "footer_cluster": "身份关联 = 通过共享信号分组的资料。",
        "summary_no_profiles": "未发现公开资料。",
        "summary_hero_unknown": "该用户",
        "summary_located_in": "位于 {location}",
        "summary_active_on": "活跃于： {platforms}",
        "summary_contact_header": "联系方式： {contact}",
        "summary_no_contact": "公开资料中未发现邮箱或电话。",
        "spa_explanation": "{sites} — 这些是单页应用 (SPA) 站点，对所有用户名返回 HTTP 200，自动检测不可靠。默认隐藏，点击链接手动验证。",
        "categories": {
            "social": "社交", "devtools": "开发工具", "forum": "论坛",
            "media": "媒体", "blog": "博客", "gaming": "游戏",
            "music": "音乐", "ecommerce": "电商",
        },
    },
    "en": {
        "title": "CLAWITHME Identity Report: {username}",
        "sec_sites": "Sites Found",
        "sec_profiles": "Profiles Extracted",
        "sec_clusters": "Identity Clusters",
        "sec_analytics": "Analytics",
        "sec_timeline": "Breach Timeline",
        "cluster_explain": "Profiles that may belong to the same person are grouped by matching signals — username similarity, shared email, phone, or avatar hash. Higher confidence means stronger evidence of a single identity.",
        "stat_sites": "Sites",
        "stat_profiles": "Profiles",
        "stat_clusters": "Clusters",
        "stat_leaks": "Leaks",
        "identity_confirmed_across": "✓ Confirmed across {n} platforms",
        "cluster_identity_confirmed": '✓ Identity confirmed: all profiles share name "{name}"',
        "th_site": "Site",
        "th_url": "URL",
        "th_status": "Status",
        "no_sites": "No sites found.",
        "no_profiles": "No profiles extracted.",
        "no_clusters": "No identity clusters found.",
        "no_analytics": "No analytics data.",
        "fp_hits_summary": "+ {n} unverified hits — what are these?",
        "field_username": "Username",
        "field_display_name": "Display Name",
        "field_joined_date": "Joined",
        "field_post_count": "Posts",
        "field_follower_count": "Followers",
        "field_following_count": "Following",
        "field_avatar_url": "Avatar URL",
        "field_bio": "Bio",
        "field_location": "Location",
        "field_email": "Email",
        "field_phone": "Phone",
        "completeness_pct": "{pct}% complete",
        "completeness_title": "Profile completeness — percentage of key fields (name, bio, location, avatar, followers) populated on this profile",
        "full_profile_data": "Full Profile Data",
        "chart_platform_dist": "Platform Distribution",
        "chart_platform_dist_sub": "Sites found by category",
        "chart_correlation": "Correlation Signals",
        "chart_correlation_sub": "Signals used to match and group identity profiles",
        "chart_radar": "Category Coverage Radar",
        "chart_radar_sub": "Assess identity digital footprint distribution by site category",
        "chart_summary_sites": "{total} sites across {cats} categories",
        "footer_brand": "CLAWITHME — OSINT Identity Panorama",
        "footer_generated": "Report generated",
        "footer_hover_hint": "Hover dotted underlines for details.",
        "footer_spa": "SPA = Single-Page Application, requires browser rendering.",
        "footer_completeness": "Completeness = percentage of key identity fields populated.",
        "footer_cluster": "Clusters = profiles grouped by shared signals.",
        "summary_no_profiles": "No public profiles found.",
        "summary_hero_unknown": "this user",
        "summary_located_in": "located in {location}",
        "summary_active_on": "active on {platforms}",
        "summary_contact_header": "Contact: {contact}",
        "summary_no_contact": "No email or phone found in public profiles.",
        "spa_explanation": "{sites} — These are Single-Page Application (SPA) sites that return HTTP 200 for all usernames, making automated detection unreliable. They are hidden by default. Click the links to manually verify.",
        "categories": {
            "social": "Social", "devtools": "Dev Tools", "forum": "Forums",
            "media": "Media", "blog": "Blogs", "gaming": "Gaming",
            "music": "Music", "ecommerce": "E-Commerce",
        },
    },
}


def L(lang, key):
    """Look up a string for the given language; fallback to 'en'."""
    return _STRINGS.get(lang, _STRINGS["en"]).get(key, _STRINGS["en"].get(key, key))


# ── Known false-positive sites ──
_SPA_SITES = frozenset({"sspai", "twitch", "twitter", "weibo", "instagram", "slideshare"})
_DROPPED_STATUSES = frozenset({403, 500, 502, 503})


def _is_false_positive(site_id: str) -> bool:
    return site_id in _SPA_SITES


def _classify_hit(hit: dict) -> str:
    """Classify a hit into 'confirmed', 'uncertain', or 'dropped'.

    - confirmed: HTTP 200, non-SPA site — reliable hit
    - uncertain: SPA site (always 200) or engine-detected (non-200 but body match)
    - dropped: 403/502/500 — anti-bot or server error, not meaningful
    """
    site_id = _hit_site_id(hit)
    status = hit.get("status", 0)
    if status in _DROPPED_STATUSES:
        return "dropped"
    if site_id in _SPA_SITES:
        return "uncertain"
    if status == 200:
        return "confirmed"
    return "uncertain"


def generate_report(  # noqa: PLR0913
    hits: list[dict],
    profiles: list[dict],
    clusters: list,
    username: str,
    *,
    trace_id: str = "",
    breach_dates: list[str] | None = None,
    lang: str = "zh",
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
    auto_summary = _compose_summary(profiles, lang=lang)

    # Pick best display name for title
    display_title = _pick_display_name(profiles, safe_username)

    # Three-tier classification for site display
    confirmed_hits = [h for h in hits if _classify_hit(h) == "confirmed"]
    uncertain_hits = [h for h in hits if _classify_hit(h) == "uncertain"]
    dropped_count = sum(1 for h in hits if _classify_hit(h) == "dropped")

    confirmed_table = _render_sites(lang, confirmed_hits, "confirmed")
    uncertain_section = _render_sites(lang, uncertain_hits, "uncertain")
    dropped_note = _render_dropped_note(lang, dropped_count)

    # Fallback for empty results
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
        ),
        confirmed_table=confirmed_table,
        uncertain_section=uncertain_section,
        dropped_note=dropped_note,
        profile_cards=_render_profiles(lang, profiles, true_hits),
        cluster_section=_render_clusters(lang, clusters, consensus_name, true_hits),
        timeline_section=_render_timeline(lang, breach_dates or []),
        chart_section=_render_charts(lang, true_hits, clusters, profiles),
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


# ── Auto-summary composition ──────────────────────────────────

def _compose_summary(profiles: list[dict], lang: str = "zh") -> str:
    """Compose a human-readable paragraph from profile data."""
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    if not profiles:
        return LANG["summary_no_profiles"]

    parts = []

    # Name — filter out generic/default placeholder display names
    _GENERIC_NAMES = frozenset({"用户分享", "用户", "user", "anonymous", "unknown"})
    names = [
        p.get("display_name") for p in profiles
        if p.get("display_name") and p.get("display_name") not in _GENERIC_NAMES
    ]
    if names:
        # Prefer the most common name; if tie, pick the longest (most informative)
        from collections import Counter
        name_counts = Counter(names)
        most_common = name_counts.most_common()
        max_freq = most_common[0][1]
        tied = [n for n, c in most_common if c == max_freq]
        name = max(tied, key=len)
    else:
        name = LANG["summary_hero_unknown"]
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
        parts.append(LANG["summary_located_in"].format(location=_esc(locs[0])))

    parts[-1] = parts[-1] + "."

    # Platforms
    platform_ids = list(dict.fromkeys(p.get("site_id", "?") for p in profiles))
    if platform_ids:
        names = ", ".join(_esc(pid) for pid in platform_ids)
        parts.append(LANG["summary_active_on"].format(platforms=names) + ".")

    # Contact
    emails = [p.get("email") for p in profiles if p.get("email")]
    phones = [p.get("phone") for p in profiles if p.get("phone")]
    if emails or phones:
        contact = []
        if emails:
            contact.append(f"Email: {_esc(emails[0])}")
        if phones:
            contact.append(f"Phone: {_esc(phones[0])}")
        parts.append(LANG["summary_contact_header"].format(contact=", ".join(contact)) + ".")
    else:
        parts.append(LANG["summary_no_contact"])

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


def _pick_display_name(profiles: list[dict], username: str) -> str:
    """Pick the best display name for the report title.

    Priority: most common display_name (≥50% of profiles), else username.title().
    """
    names = [p.get("display_name") for p in profiles if p.get("display_name")]
    if not names:
        return username.title()
    # Count occurrences
    from collections import Counter
    counts = Counter(names)
    most_common, freq = counts.most_common(1)[0]
    if freq >= len(profiles) * 0.5:  # at least 50% of profiles
        return most_common
    return username.title()


# ── Summary hero ─────────────────────────────────────────────

def _render_summary(
    lang: str, display_title: str, username: str,
    true_hits: int, fp_count: int,
    profiles: int, clusters: int, leaks: int,
    consensus_name: str | None, auto_summary: str,
) -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    # Pick best display name
    identity_line = ""
    if consensus_name:
        identity_line = (
            f'<div class="hero-identity">'
            f'<span class="hero-identity-name">{_esc(consensus_name)}</span>'
            f'<span class="hero-identity-badge">{LANG["identity_confirmed_across"].format(n=profiles)}</span>'
            f'</div>'
        )

    fp_note = ""
    if fp_count > 0:
        fp_note = (
            f'<span class="fp-note" title="{LANG["spa_explanation"].format(sites="")}">'
            f' {LANG["fp_hits_summary"].format(n=fp_count)}</span>'
        )

    items = []
    if true_hits:
        items.append(f"<div class=\"hero-stat\"><span class=\"hero-stat-value\">{true_hits}</span><span class=\"hero-stat-label\">{LANG['stat_sites']}</span></div>")
    if profiles:
        items.append(f"<div class=\"hero-stat\"><span class=\"hero-stat-value\">{profiles}</span><span class=\"hero-stat-label\">{LANG['stat_profiles']}</span></div>")
    if clusters:
        items.append(f"<div class=\"hero-stat\"><span class=\"hero-stat-value\">{clusters}</span><span class=\"hero-stat-label\">{LANG['stat_clusters']}</span></div>")
    if leaks:
        items.append(f"<div class=\"hero-stat\"><span class=\"hero-stat-value\">{leaks}</span><span class=\"hero-stat-label\">{LANG['stat_leaks']}</span></div>")
    stats_html = f'<div class="hero-stats">{"".join(items)}</div>' if items else ""

    return (
        f'<div class="summary-hero">'
        f'<div class="brand-header">'
        f'<span class="brand-wordmark">'
        f'CLAWITH<span class="brand-wordmark-me">ME</span>'
        f'</span>'
        f'<span class="brand-slogan">OSINT Identity Panorama</span>'
        f'</div>'
        f'<h1>{_esc(display_title)}</h1>'
        f'{identity_line}'
        f'<p class="hero-summary">{auto_summary}</p>'
        f'{stats_html}'
        f'<div class="meta">{fp_note}</div>'
        f'</div>'
    )


# ── HTML template ──────────────────────────────────────────────

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

/* ── Summary hero ───────────────────────────── */
.summary-hero {{
  background: #fff; border-radius: 10px; border-left: 4px solid var(--accent);
  padding: 36px 36px 28px;
  box-shadow: 0px 0px 0px 1px rgba(0,0,0,0.08), 0px 2px 2px rgba(0,0,0,0.04);
}}
.summary-hero h1 {{ color: var(--accent); }}
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
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-variant-numeric: tabular-nums; line-height: 1;
}}
.hero-stat-label {{
  font-size: 12px; color: #808080; text-transform: uppercase; letter-spacing: 0.5px;
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


# ── Render helpers ──────────────────────────────────────────────

def _render_sites(lang: str, hits_list: list[dict], tier: str) -> str:
    """Render a list of hits as categorized site tables.

    tier='confirmed': expanded table with category grouping.
    tier='uncertain': collapsed details, same table format.
    """
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    CATS = LANG["categories"]
    if not hits_list:
        return ""

    parts = []

    # Category summary tags
    groups: dict[str, list[dict]] = {}
    for h in hits_list:
        cat = _hit_category(h)
        groups.setdefault(cat, []).append(h)

    cat_names = CATS
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
            favicon = _site_favicon_url(h)
            favicon_html = (
                '<img class="site-icon" src="' + _esc(favicon) + '" alt=""'
                ' loading="lazy" onerror="this.style.display=\'none\'">'
            ) if favicon else ""
            site_name = _site_name_from_hit(h)
            status = h.get("status", "")
            status_cls = "status-ok" if status == 200 else "status-warn"
            url_html = (
                f'<a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(url)}</a>'
                if url else ""
            )
            rows.append(
                f'<tr>'
                f'<td>{favicon_html}<span>{_esc(site_name)}</span></td>'
                f'<td class="url">{url_html}</td>'
                f'<td class="{status_cls}">{status}</td>'
                f'</tr>'
            )
        parts.append(
            f'<div class="cat-label">{name}</div>'
            f'<table class="site-table">'
            f'<thead><tr><th>{LANG["th_site"]}</th><th>{LANG["th_url"]}</th><th>{LANG["th_status"]}</th></tr></thead>'
            f'<tbody>' + "".join(rows) + "</tbody></table>"
        )

    content = "".join(parts)

    if tier == "uncertain":
        return (
            '<details style="margin-top:16px">'
            '<summary class="uncertain-summary">'
            + LANG['fp_hits_summary'].format(n=len(hits_list)) + '</summary>'
            + content
            + '</details>'
        )

    return content


def _render_dropped_note(lang: str, count: int) -> str:
    """Render a note about dropped sites (anti-bot, server errors)."""
    if not count:
        return ""
    note = f"另有 {count} 个站点因服务器错误或反爬机制未能完成检测。" if lang == "zh" else f"{count} site(s) skipped due to server errors or anti-bot protection."
    return f'<p style="margin-top:12px;font-size:12px;color:#b0b0b0">{note}</p>'


def _hit_category(hit: dict) -> str:
    return hit.get("site_def", {}).get("classification", {}).get("primary", "other")


def _site_favicon_url(hit: dict, size: int = 16) -> str:
    """Return Google Favicon API URL for a site from its canonical URL."""
    url = hit.get("site_def", {}).get("canonical_url", "") or hit.get("url", "")
    if not url:
        return ""
    try:
        domain = urlparse(url).netloc
        if not domain:
            return ""
        return f"https://www.google.com/s2/favicons?domain={domain}&sz={size}"
    except Exception:
        return ""


def _site_name_from_hit(hit: dict) -> str:
    return hit.get("site_name", "") or hit.get("site_def", {}).get("name", "?")


_EXTRA_LABELS: dict[str, str] = {
    "reputation": "Rep", "badges": "Badges",
    "twitter": "Twitter", "github": "GitHub", "linkedin": "LinkedIn",
    "website": "Website", "gender": "Gender", "verified": "Verified",
}


def _render_profiles(lang: str, profiles: list[dict], hits: list[dict]) -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    if not profiles:
        return f'<p style="color:#808080;margin-top:20px">{LANG["no_profiles"]}</p>'

    _PROFILE_FIELDS = ["display_name", "bio", "location", "avatar_url", "follower_count"]
    # Build site_id to hit mapping for favicon lookup
    hit_map: dict[str, dict] = {}
    for h in hits:
        sid = _hit_site_id(h)
        if sid:
            hit_map[sid] = h

    cards = []
    for p in profiles:
        site_id = p.get("site_id", "?")
        display_name = p.get("display_name") or ""
        _GENERIC_NAMES = frozenset({"用户分享", "用户", "user", "anonymous", "unknown", "Level", "None"})
        name = p.get("username") or site_id
        if display_name and display_name not in _GENERIC_NAMES:
            name = display_name
        bio = p.get("bio", "") or ""
        location = p.get("location", "") or ""

        bio_html = f'<div class="card-bio">{_esc(bio[:200])}</div>' if bio.strip() else ""

        # Avatar: real photo if available, site favicon as fallback
        avatar_url = p.get("avatar_url", "")
        if avatar_url:
            avatar_html = (
                f'<img class="card-avatar" src="{_esc(avatar_url)}"'
                f' alt="" loading="lazy">'
            )
        else:
            # Fallback to site favicon
            site_hit = hit_map.get(site_id)
            favicon = _site_favicon_url(site_hit, size=64) if site_hit else ""
            if favicon:
                avatar_html = (
                    '<img class="site-favicon" src="' + _esc(favicon) + '"'
                    ' alt="" loading="lazy"'
                    ' onerror="this.style.display=\'none\';'
                    'this.insertAdjacentHTML(\'afterend\',\'<div class=card-avatar></div>\')">'
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

        # Donut ring completeness — accent for high, grayscale for low
        filled = sum(1 for f in _PROFILE_FIELDS if p.get(f))
        pct = int(filled / len(_PROFILE_FIELDS) * 100)
        donut_color = "var(--accent)" if pct >= 60 else "#171717"
        donut_html = (
            f'<div class="cc-donut" style="--pct:{pct};--donut-color:{donut_color}" data-pct="{pct}%"></div>'
        )
        completeness_label = (
            f'<span class="completeness-label" title="{LANG["completeness_title"]}">'
            + LANG['completeness_pct'].format(pct=pct) + '</span>'
        )

        # ── Full profile data (collapsible) ──
        full_rows = []
        _PROFILE_DETAIL_FIELDS = [
            ("username", LANG["field_username"]),
            ("display_name", LANG["field_display_name"]),
            ("bio", LANG["field_bio"]),
            ("location", LANG["field_location"]),
            ("email", LANG["field_email"]),
            ("phone", LANG["field_phone"]),
            ("joined_date", LANG["field_joined_date"]),
            ("post_count", LANG["field_post_count"]),
            ("follower_count", LANG["field_follower_count"]),
            ("following_count", LANG["field_following_count"]),
            ("avatar_url", LANG["field_avatar_url"]),
        ]
        for field_key, field_label in _PROFILE_DETAIL_FIELDS:
            val = p.get(field_key)
            if val is None or val == "":
                continue
            if isinstance(val, int):
                display = f"{val:,}"
            else:
                display = _esc(str(val))
            # Truncate long URLs
            if field_key == "avatar_url" and len(display) > 60:
                display = display[:57] + "..."
            if field_key == "bio" and len(display) > 300:
                display = display[:297] + "..."
            full_rows.append(
                f'<tr><td class="field-label">{field_label}</td>'
                f'<td class="field-value">{display}</td></tr>'
            )
        # Extra dict
        if extra:
            for ek, ev in extra.items():
                if ek in _EXTRA_LABELS:
                    continue  # already shown as tags
                if isinstance(ev, dict):
                    ev_display = ", ".join(
                        f"{k}:{v:,}" if isinstance(v, int) else f"{k}:{v}"
                        for k, v in ev.items()
                    )
                elif isinstance(ev, list):
                    ev_display = ", ".join(_esc(str(x)[:60]) for x in ev[:10])
                elif isinstance(ev, bool):
                    ev_display = "Yes" if ev else "No"
                else:
                    ev_display = _esc(str(ev)[:200])
                full_rows.append(
                    f'<tr><td class="field-label">{_esc(ek)}</td>'
                    f'<td class="field-value">{ev_display}</td></tr>'
                )

        full_html = ""
        if full_rows:
            full_html = (
                '<details class="profile-details" style="margin-top:16px">'
                '<summary style="cursor:pointer;font-size:12px;color:#808080">'
                + LANG['full_profile_data'] + '</summary>'
                + f'<table class="field-table" style="margin-top:8px">'
                f'{"".join(full_rows)}'
                f'</table>'
                f'</details>'
            )

        cards.append(
            f'<div class="card">'
            f'<div class="card-header">'
            f'{avatar_html}'
            f'<div style="flex:1"><div class="card-name">{_esc(name)}</div>'
            f'<div class="card-site">{_esc(site_id)}</div></div>'
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px">'
            f'{donut_html}{completeness_label}'
            f'</div>'
            f'</div>'
            f'{bio_html}{extra_html}{meta_html}'
            f'{full_html}'
            f'</div>'
        )
    return '<div class="card-grid">' + "".join(cards) + "</div>"


def _render_clusters(lang: str, clusters: list, consensus_name: str | None = None,
                      hits: list[dict] | None = None) -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    if not clusters:
        return f'<p style="color:#808080;margin-top:20px">{LANG["no_clusters"]}</p>'
    # Build site_id -> favicon mapping
    favicon_map: dict[str, str] = {}
    if hits:
        for h in hits:
            sid = _hit_site_id(h)
            if sid and sid not in favicon_map:
                fav = _site_favicon_url(h, size=32)
                if fav:
                    favicon_map[sid] = fav
    blocks = []
    for i, c in enumerate(clusters, 1):
        # Site pills with favicons
        site_pills = []
        for p in c.profiles:
            sid = p.site_id
            fav = favicon_map.get(sid, "")
            if fav:
                site_pills.append(
                    '<span class="cluster-site-pill">'
                    '<img src="' + _esc(fav) + '" alt="" loading="lazy"'
                    ' onerror="this.style.display=\'none\'">'
                    + _esc(sid) + '</span>'
                )
            else:
                site_pills.append(
                    '<span class="cluster-site-pill">' + _esc(sid) + '</span>'
                )
        sites_pills_html = (
            '<div class="cluster-list-pills">' + "".join(site_pills) + '</div>'
        ) if site_pills else ""

        # Confidence bar
        conf = c.confidence
        pct = int(conf * 100)
        bar_color = "#2e7d32" if conf >= 0.9 else "#b8860b" if conf >= 0.7 else "#b0b0b0"
        conf_html = (
            f'<div class="cluster-conf-bar">'
            f'<div class="cluster-conf-fill" style="width:{pct}%;background:{bar_color}"></div>'
            f'</div>'
            f'<span class="cluster-conf-label" style="color:{bar_color}">{pct}%</span>'
        )

        sig_tags = "".join(
            f'<span class="signal-tag">{_esc(s)}</span>' for s in c.signals
        )

        # Identity confirmation
        identity_html = ""
        if consensus_name and len(c.profiles) >= 2:
            identity_html = (
                '<div class="cluster-identity">'
                + LANG['cluster_identity_confirmed'].format(name=_esc(consensus_name))
                + '</div>'
            )

        # Deduplicate evidence lines
        evidence_lines = []
        seen_evidence: set[str] = set()
        if c.evidence:
            for sig, details in c.evidence.items():
                for d in details:
                    if d not in seen_evidence:
                        seen_evidence.add(d)
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
            f'<strong>Profile set {i}</strong>'
            f'</div>'
            f'{conf_html}'
            f'{sites_pills_html}'
            f'<div class="cluster-signals">{sig_tags}</div>'
            f'{evidence_html}'
            f'{identity_html}'
            f'</div>'
        )
    return '<div style="margin-top:20px">' + "".join(blocks) + "</div>"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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


def _render_timeline(lang: str, dates: list[str]) -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])
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
        f'<div class=\"section-header\"><span class=\"badge\">05</span><h2>{LANG["sec_timeline"]}</h2></div>'
        f'<div class="timeline"><div class="timeline-track">{"".join(dots)}</div></div>'
        '</div></div>'
    )


def _render_charts(lang: str, true_hits: list[dict], clusters: list,
                   profiles: list[dict] | None = None) -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    if not true_hits and not clusters:
        return f'<p style="color:#808080;margin-top:20px">{LANG["no_analytics"]}</p>'

    sections: list[str] = []

    # ── Radar chart: Identity Footprint ──
    if true_hits or profiles:
        radar = _render_radar(lang, true_hits, clusters, profiles or [])
        if radar:
            sections.append(radar)

    # Platform distribution chart
    if true_hits:
        cat_counts: dict[str, int] = {}
        for h in true_hits:
            cat = _hit_category(h)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        sorted_cats = sorted(cat_counts.items(), key=lambda x: -x[1])
        max_count = max(c for _, c in sorted_cats) if sorted_cats else 1
        total = sum(c for _, c in sorted_cats)

        bars = []
        for cat, count in sorted_cats:
            pct = int(count / max_count * 100)
            opacity = 0.30 + 0.70 * (count / max_count)
            name = LANG["categories"].get(cat, cat.title())
            bars.append(
                f'<div class="chart-bar-row">'
                f'<span class="chart-bar-label">{_esc(name)}</span>'
                f'<span class="chart-bar-track">'
                f'<span class="chart-bar-fill" style="width:{pct}%;--bar-opacity:{opacity:.2f}"></span>'
                f'</span>'
                f'<span class="chart-bar-count">{count}</span>'
                f'</div>'
            )
        summary_line = LANG['chart_summary_sites'].format(total=total, cats=len(sorted_cats))
        summary_html = f'<div class="chart-summary"><span class="chart-summary-num">{total}</span> {summary_line}</div>'
        sections.append(
            '<div class="chart-col">'
            f'<div class="chart-title">{LANG["chart_platform_dist"]}</div>'
            f'<p class="chart-subtitle">{LANG["chart_platform_dist_sub"]}</p>'
            + summary_html
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
                opacity = 0.30 + 0.70 * (count / max_sig)
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
                f'<div class="chart-title">{LANG["chart_correlation"]}</div>'
                f'<p class="chart-subtitle">{LANG["chart_correlation_sub"]}</p>'
                + "".join(bars) +
                '</div>'
            )

    if not sections:
        return f'<p style="color:#808080;margin-top:20px">{LANG["no_analytics"]}</p>'

    return (
        f'<div class="chart-row" style="margin-top:20px">{"".join(sections)}</div>'
    )


def _render_radar(lang: str, true_hits: list[dict], clusters: list,
                  profiles: list[dict]) -> str:
    """Render SVG radar chart using site categories as axes."""
    import math

    if not true_hits:
        return ""

    LANG = _STRINGS.get(lang, _STRINGS["en"])
    CATS = LANG["categories"]

    # Count hits per category, pick top 5
    cat_counts: dict[str, int] = {}
    for h in true_hits:
        cat = _hit_category(h)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    sorted_cats = sorted(cat_counts.items(), key=lambda x: -x[1])[:5]
    n = len(sorted_cats)
    if n < 3:
        return ""  # need at least 3 axes

    max_val = max(c for _, c in sorted_cats)
    axes = [(CATS.get(cat, cat.title()), count) for cat, count in sorted_cats]

    cx, cy, r = 130, 130, 100
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]

    def _point(i: int, dist_ratio: float) -> str:
        x = cx + r * dist_ratio * math.cos(angles[i])
        y = cy + r * dist_ratio * math.sin(angles[i])
        return f"{x:.1f},{y:.1f}"

    # Grid rings
    grid_lines = []
    for level in (0.2, 0.4, 0.6, 0.8, 1.0):
        pts = " ".join(_point(i, level) for i in range(n))
        grid_lines.append(
            f'<polygon points="{pts}" fill="none" stroke="#e8e8e8" stroke-width="1"/>'
        )
    grid_axes = []
    for i in range(n):
        grid_axes.append(
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" '
            f'x2="{_point(i, 1.0).split(",")[0]}" '
            f'y2="{_point(i, 1.0).split(",")[1]}" '
            f'stroke="#e8e8e8" stroke-width="1"/>'
        )

    # Data polygon
    data_pts = " ".join(
        _point(i, count / max_val) for i, (_, count) in enumerate(axes)
    )
    data_poly = (
        f'<polygon points="{data_pts}" fill="var(--accent)" '
        f'fill-opacity="0.12" stroke="var(--accent)" stroke-width="2" '
        f'stroke-linejoin="round"/>'
    )
    dots = []
    for i, (_, count) in enumerate(axes):
        x, y = _point(i, count / max_val).split(",")
        dots.append(f'<circle cx="{x}" cy="{y}" r="3" fill="var(--accent)"/>')

    # Labels
    labels = []
    for i, (cat_name, count) in enumerate(axes):
        x, y = _point(i, 1.18).split(",")
        display_name = cat_name if len(cat_name) <= 12 else cat_name[:11] + "…"
        labels.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" '
            f'class="radar-label">{display_name}</text>'
        )
        sx, sy = _point(i, 1.07).split(",")
        labels.append(
            f'<text x="{sx}" y="{sy}" text-anchor="middle" '
            f'class="radar-score">{count}</text>'
        )

    svg = (
        '<div class="radar-chart">'
        '<svg viewBox="0 0 260 260" class="radar-svg">'
        + "".join(grid_lines) + "".join(grid_axes) +
        data_poly + "".join(dots) + "".join(labels) +
        '</svg>'
        '</div>'
    )

    return (
        '<div class="chart-col chart-col-radar">'
        f'<div class="chart-title">{LANG["chart_radar"]}</div>'
        f'<p class="chart-subtitle">{LANG["chart_radar_sub"]}</p>'
        + svg +
        '</div>'
    )
