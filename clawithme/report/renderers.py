"""Phase 5 — Report render helpers.

All _render_*() functions extracted from generator.py to keep the
module hierarchy clean.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import UTC, datetime
from urllib.parse import urlparse

from clawithme.report.i18n import (
    L,
    _STRINGS,
    _CONFIDENCE_THRESHOLDS,
    _SPA_SITES,
    _DROPPED_STATUSES,
    _GENERIC_NAMES as _GENERIC_NAMES_I18N,
    _EXTRA_LABELS,
)
from clawithme.report.template import _fmt_esc
from clawithme.signals.correlation import Cluster


def _username_similarity(a: str, b: str) -> float:
    """Levenshtein-based similarity. 1.0 = identical, 0.0 = completely different."""
    if not a or not b:
        return 0.0
    a, b = a.strip().lower(), b.strip().lower()
    if a == b:
        return 1.0
    if len(a) < 3 or len(b) < 3:
        return 1.0 if a[0] == b[0] else 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 1 if ca != cb else 0
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    dist = prev[-1]
    return max(0.0, 1.0 - dist / max(len(a), len(b)))


def _compute_hit_confidence(
    hit: dict,
    profile_by_site: dict[str, dict],
    username: str,
) -> float:
    """Compute confidence score 0.0-1.0 for a hit."""
    site_id = _hit_site_id(hit)
    status = hit.get("status", 0)
    has_profile = site_id in profile_by_site
    is_spa = site_id in _SPA_SITES

    if status in _DROPPED_STATUSES:
        return 0.0

    if status == 200 and not is_spa:
        base = 0.85
    elif status == 200 and is_spa and has_profile:
        base = 0.80
    elif status == 200 and is_spa and not has_profile:
        base = 0.40
    elif status == 0:
        base = 0.30
    else:
        base = 0.20

    if has_profile:
        profile = profile_by_site[site_id]
        display_name = profile.get("display_name", "")
        if display_name and username.lower() in display_name.lower():
            base += 0.10
        filled = sum(1 for f in ("bio", "location", "avatar_url", "email") if profile.get(f))
        base += filled * 0.03

    return min(base, 1.0)


def _is_wrong_person(
    hit: dict,
    profile_by_site: dict[str, dict],
    username: str,
) -> bool:
    """Check if hit's extracted profile clearly belongs to a different person."""
    site_id = _hit_site_id(hit)
    profile = profile_by_site.get(site_id)
    if not profile:
        return False
    display_name = profile.get("display_name", "")
    if not display_name:
        return False
    if display_name.strip() in _GENERIC_NAMES_I18N:
        return False
    dl = display_name.lower()
    ul = username.lower()
    if ul in dl or dl in ul:
        return False
    if any(ul == t or ul in t or t in ul for t in dl.split()):
        return False

    def _has_cjk(s: str) -> bool:
        return any("一" <= c <= "鿿" or "぀" <= c <= "ヿ" for c in s)
    if _has_cjk(display_name) != _has_cjk(ul):
        return False
    sim = _username_similarity(username, display_name)
    return sim < 0.3


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _redact_evidence(signal: str, detail: str) -> str:
    # Strip optional "siteA ↔ siteB: " prefix before redacting
    prefix = ""
    rest = detail
    if ": " in detail and " ↔ " in detail:
        idx = detail.index(": ")
        prefix = detail[: idx + 2]
        rest = detail[idx + 2 :]

    if signal == "email":
        if "@" in rest:
            local, domain = rest.split("@", 1)
            redacted = f"{local[0]}***@{domain}" if local else "***@..."
        else:
            redacted = "***"
    elif signal == "phone":
        redacted = f"***{rest[-4:]}" if len(rest) >= 4 else "***"
    else:
        redacted = rest
    return prefix + redacted


def _hit_site_id(hit: dict) -> str:
    return hit.get("site_def", {}).get("id", "")


def _hit_category(hit: dict) -> str:
    return hit.get("site_def", {}).get("classification", {}).get("primary", "other")


def _site_favicon_url(hit: dict, size: int = 16) -> str:
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


def _truncate_sentence(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rstrip()
    for sep in (". ", "! ", "? ", ".", "!", "?"):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:
            return cut[:idx + len(sep.rstrip())]
    return cut + "…"


def _compose_summary(profiles: list[dict], lang: str = "zh") -> str:
    """Compose a human-readable paragraph from profile data."""
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    if not profiles:
        return LANG["summary_no_profiles"]

    parts = []
    _GENERIC_NAMES = frozenset({"用户分享", "用户", "user", "anonymous", "unknown", "Level"})
    names = [
        p.get("display_name") for p in profiles
        if p.get("display_name") and p.get("display_name") not in _GENERIC_NAMES
    ]
    if names:
        from collections import Counter
        name_counts = Counter(names)
        most_common = name_counts.most_common()
        max_freq = most_common[0][1]
        tied = [n for n, c in most_common if c == max_freq]
        name = max(tied, key=len)
    else:
        name = LANG["summary_hero_unknown"]
    parts.append(_esc(name))

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

    locs = [p.get("location") for p in profiles if p.get("location")]
    if locs:
        parts.append(LANG["summary_located_in"].format(location=_esc(locs[0])))

    parts[-1] = parts[-1] + "."

    platform_ids = list(dict.fromkeys(p.get("site_id", "?") for p in profiles))
    if platform_ids:
        names = ", ".join(_esc(pid) for pid in platform_ids)
        parts.append(LANG["summary_active_on"].format(platforms=names) + ".")

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


def _pick_display_name(profiles: list[dict], username: str) -> str:
    """Pick the best display name for the report title."""
    names = [p.get("display_name") for p in profiles if p.get("display_name")]
    if not names:
        return username.title()
    counts = Counter(names)
    most_common, freq = counts.most_common(1)[0]
    if freq >= len(profiles) * 0.5:
        return most_common
    return username.title()


# ── Summary hero ─────────────────────────────────────────────

def _render_summary(
    lang: str, display_title: str, username: str,
    true_hits: int, fp_count: int,
    profiles: int, clusters: int, leaks: int,
    consensus_name: str | None, auto_summary: str,
    avatar_url: str = "", avatar_fallback: str = "", avatar_color: str = "",
) -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])

    # ── Avatar ──
    if avatar_url:
        avatar_html = (
            f'<div class="hero-avatar-wrap">'
            f'<img src="{_esc(avatar_url)}" alt="" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'<div class="hero-avatar-fallback" style="display:none;background:{avatar_color}">'
            f'{_esc(avatar_fallback)}</div>'
            f'</div>'
        )
    else:
        avatar_html = (
            f'<div class="hero-avatar-wrap">'
            f'<div class="hero-avatar-fallback" style="background:{avatar_color}">'
            f'{_esc(avatar_fallback)}</div>'
            f'</div>'
        )

    identity_line = ""
    if consensus_name:
        identity_line = (
            f'<div class="hero-identity">'
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
        f'<hr class="hero-divider">'
        f'<div class="hero-card">'
        f'{avatar_html}'
        f'<div class="hero-info">'
        f'<h1>{_esc(display_title)}</h1>'
        f'<div class="hero-username">@{_esc(username)}</div>'
        f'{identity_line}'
        f'<p class="hero-summary">{auto_summary}</p>'
        f'{stats_html}'
        f'<div class="hero-meta">{fp_note}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


# ── Render helpers ──────────────────────────────────────────────

def _render_sites(lang: str, hits_list: list[dict], tier: str,
                  wrong_person_ids: set[str] | None = None,
                  profile_by_site: dict[str, dict] | None = None,
                  username: str = "") -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    CATS = LANG["categories"]
    if not hits_list:
        return ""

    pbs = profile_by_site or {}
    _BADGE_LABELS = {
        "confirmed": LANG.get("badge_confirmed", "Confirmed"),
        "uncertain": LANG.get("badge_uncertain", "Uncertain"),
        "low": LANG.get("badge_low", "Low"),
    }
    _BADGE_CLS = {
        "confirmed": "badge-ok",
        "uncertain": "badge-warn",
        "low": "badge-low",
    }

    def _badge(h: dict) -> str:
        if not pbs:
            return ""
        c = _compute_hit_confidence(h, pbs, username.replace("&amp;", "&") if "&amp;" in username else username)
        if c >= _CONFIDENCE_THRESHOLDS["confirmed"]:
            level, label = "confirmed", _BADGE_LABELS["confirmed"]
        elif c >= _CONFIDENCE_THRESHOLDS["uncertain"]:
            level, label = "uncertain", _BADGE_LABELS["uncertain"]
        else:
            level, label = "low", _BADGE_LABELS["low"]
        cls = _BADGE_CLS.get(level, "badge-warn")
        return f'<span class="conf-badge {cls}">{_esc(label)}</span>'

    def _wrong_person_warning(site_id: str) -> str:
        if wrong_person_ids and site_id in wrong_person_ids:
            warn = LANG.get("badge_wrong_person", "Likely wrong person")
            return f'<span class="wp-warn">⚠ {_esc(warn)}</span>'
        return ""

    parts = []
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
            sid = _hit_site_id(h)
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
            badge_html = _badge(h)
            wp_html = _wrong_person_warning(sid)
            extra_col = badge_html + wp_html if (badge_html or wp_html) else ""
            rows.append(
                f'<tr>'
                f'<td>{favicon_html}<span>{_esc(site_name)}</span></td>'
                f'<td class="url">{url_html}</td>'
                f'<td class="{status_cls}">{status}</td>'
                f'<td style="text-align:right;white-space:nowrap">{extra_col}</td>'
                f'</tr>'
            )
        parts.append(
            f'<div class="cat-label">{name}</div>'
            f'<table class="site-table">'
            f'<thead><tr><th>{LANG["th_site"]}</th><th>{LANG["th_url"]}</th><th>{LANG["th_status"]}</th><th></th></tr></thead>'
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
    if not count:
        return ""
    note = f"另有 {count} 个站点因服务器错误或反爬机制未能完成检测。" if lang == "zh" else f"{count} site(s) skipped due to server errors or anti-bot protection."
    return f'<p style="margin-top:12px;font-size:12px;color:#b0b0b0">{note}</p>'


def _render_profiles(lang: str, profiles: list[dict], hits: list[dict]) -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    if not profiles:
        return f'<p style="color:#808080;margin-top:20px">{LANG["no_profiles"]}</p>'

    _PROFILE_FIELDS = ["display_name", "bio", "location", "avatar_url", "follower_count"]
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

        avatar_url = p.get("avatar_url", "")
        if avatar_url:
            avatar_html = (
                f'<img class="card-avatar" src="{_esc(avatar_url)}"'
                f' alt="" loading="lazy">'
            )
        else:
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
            if field_key == "avatar_url" and len(display) > 60:
                display = display[:57] + "..."
            if field_key == "bio" and len(display) > 300:
                display = display[:297] + "..."
            full_rows.append(
                f'<tr><td class="field-label">{field_label}</td>'
                f'<td class="field-value">{display}</td></tr>'
            )
        if extra:
            for ek, ev in extra.items():
                if ek in _EXTRA_LABELS:
                    continue
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


def _render_cluster_assessment(clusters: list, total_profiles: int, lang: str) -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    multi = [c for c in clusters if len(c.profiles) >= 2]
    has_signals = any(c.signals for c in clusters)

    if total_profiles <= 1:
        text = LANG["cluster_assessment_singleton"].format(n=total_profiles)
    elif not multi and not has_signals:
        text = LANG["cluster_assessment_dispersed"]
    elif has_signals and total_profiles >= 3:
        text = LANG["cluster_assessment_partial"].format(n=len(multi))
    else:
        text = LANG["cluster_assessment_dispersed"]

    return (
        '<div class="cluster-assessment">'
        f'<div class="cluster-assessment-title">{_esc(LANG["cluster_assessment_title"])}</div>'
        f'<div class="cluster-assessment-body">{_esc(text)}</div>'
        f'<div class="cluster-assessment-note">{_esc(LANG["cluster_assessment_note"])}</div>'
        '</div>'
    )


def _render_clusters(lang: str, clusters: list, consensus_name: str | None = None,
                      hits: list[dict] | None = None) -> str:
    LANG = _STRINGS.get(lang, _STRINGS["en"])
    if not clusters:
        return f'<p style="color:#808080;margin-top:20px">{LANG["no_clusters"]}</p>'
    total_profiles = sum(len(c.profiles) for c in clusters)
    assessment_html = _render_cluster_assessment(clusters, total_profiles, lang)
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

        identity_html = ""
        if consensus_name and len(c.profiles) >= 2:
            identity_html = (
                '<div class="cluster-identity">'
                + LANG['cluster_identity_confirmed'].format(name=_esc(consensus_name))
                + '</div>'
            )

        # ── Condense evidence into readable summaries ──
        evidence_lines = []
        if c.evidence:
            for sig, details in c.evidence.items():
                if not details:
                    continue

                # Parse evidence: "siteA ↔ siteB: value" or just "value"
                parsed = []
                for d in details:
                    colon = d.find(": ")
                    if colon > 0 and " ↔ " in d:
                        parsed.append((d[:colon].strip(), d[colon + 2 :].strip()))
                    else:
                        parsed.append(("", d))

                # Deduplicate by signal type
                if sig == "username":
                    seen_pairs: set[str] = set()
                    uniq = []
                    for pair, val in parsed:
                        # Key on username values + sim score
                        sim_m = re.search(r"sim=([\d.]+)", val)
                        name_m = re.search(r"(.+?) ↔ (.+?) \(sim=", val)
                        if name_m:
                            k = f"{name_m[1].lower()}|{name_m[2].lower()}|{sim_m[1] if sim_m else ''}"
                        else:
                            k = val
                        if k not in seen_pairs:
                            seen_pairs.add(k)
                            uniq.append((pair, val))

                    site_count = len(c.profiles)
                    if len(uniq) == 1 and site_count > 2:
                        name_m = re.search(r"^(.+?) ↔", uniq[0][1])
                        name_val = name_m[1].strip() if name_m else ""
                        line = f"All {site_count} profiles share the same username &#39;{_esc(name_val)}&#39;"
                        evidence_lines.append(
                            f'<div class="cluster-evidence">'
                            f'<span class="signal-tag">{_esc(sig)}</span> {line}</div>'
                        )
                    else:
                        for pair, val in uniq:
                            display = f"{pair}: {val}" if pair else val
                            evidence_lines.append(
                                f'<div class="cluster-evidence">'
                                f'<span class="signal-tag">{_esc(sig)}</span> '
                                f'{_esc(_redact_evidence(sig, display))}'
                                f'</div>'
                            )
                else:
                    # email, phone, avatar, etc.: dedup by value
                    seen_vals: set[str] = set()
                    uniq = []
                    for pair, val in parsed:
                        norm = val.strip().lower()
                        if norm not in seen_vals:
                            seen_vals.add(norm)
                            uniq.append((pair, val))

                    site_count = len(c.profiles)
                    if len(uniq) == 1 and site_count > 2 and sig in ("email", "phone"):
                        evidence_lines.append(
                            f'<div class="cluster-evidence">'
                            f'<span class="signal-tag">{_esc(sig)}</span> '
                            f'Shared across all {site_count} profiles</div>'
                        )
                    else:
                        for pair, val in uniq:
                            display = f"{pair}: {val}" if pair else val
                            evidence_lines.append(
                                f'<div class="cluster-evidence">'
                                f'<span class="signal-tag">{_esc(sig)}</span> '
                                f'{_esc(_redact_evidence(sig, display))}'
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
    return '<div style="margin-top:20px">' + assessment_html + "".join(blocks) + "</div>"


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

    if true_hits or profiles:
        radar = _render_radar(lang, true_hits, clusters, profiles or [])
        if radar:
            sections.append(radar)

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
    if not true_hits:
        return ""

    LANG = _STRINGS.get(lang, _STRINGS["en"])
    CATS = LANG["categories"]

    cat_counts: dict[str, int] = {}
    for h in true_hits:
        cat = _hit_category(h)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    sorted_cats = sorted(cat_counts.items(), key=lambda x: -x[1])[:5]
    n = len(sorted_cats)
    if n < 3:
        return ""

    max_val = max(c for _, c in sorted_cats)
    axes = [(CATS.get(cat, cat.title()), count) for cat, count in sorted_cats]

    cx, cy, r = 130, 130, 100
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]

    def _point(i: int, dist_ratio: float) -> str:
        x = cx + r * dist_ratio * math.cos(angles[i])
        y = cy + r * dist_ratio * math.sin(angles[i])
        return f"{x:.1f},{y:.1f}"

    grid_lines = []
    for level in (0.2, 0.4, 0.6, 0.8, 1.0):
        pts = " ".join(_point(i, level) for i in range(n))
        grid_lines.append(
            f'<polygon points="{pts}" fill="none" stroke="#e8e8e8" stroke-width="1"/>'
        )
    grid_axes = []
    for i in range(n):
        x2, y2 = _point(i, 1.0).split(",")
        grid_axes.append(
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" '
            f'x2="{x2}" y2="{y2}" '
            f'stroke="#e8e8e8" stroke-width="1"/>'
        )

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


# ── Action Items ───────────────────────────────────────────────


def _compute_actions(
    profiles: list[dict],
    leak_records: list,
    clusters: list,
    true_hits: list[dict],
    lang: str = "zh",
) -> list[dict]:
    """Compute actionable recommendations based on search results.

    Returns a list of action dicts with keys: icon, type (warn/info/danger),
    title, detail.
    """
    LANG = _STRINGS.get(lang, _STRINGS["zh"])
    actions: list[dict] = []

    # 1. Leaked credentials → suggest password changes
    leak_emails = set()
    for r in leak_records:
        email = getattr(r, "email", "")
        if email:
            leak_emails.add(email[:3] + "***@" + email.split("@")[-1] if "@" in email else email[:3] + "***")
    if leak_emails:
        actions.append({
            "icon": "🔓",
            "type": "danger",
            "title": LANG.get("action_leak_title", "数据泄露预警"),
            "detail": LANG.get("action_leak_detail",
                               "你的邮箱出现在 {n} 次数据泄露中。建议立即修改相关平台密码，"
                               "并开启双因素认证（2FA）。")
                     .format(n=len(leak_emails))
                     + " " + ", ".join(leak_emails),
        })

    # 2. Avatar reuse across platforms → privacy risk
    avatar_sites = [p for p in profiles if p.get("avatar_url")]
    if len(avatar_sites) >= 3:
        sites = [p.get("site_id", "") for p in avatar_sites][:5]
        actions.append({
            "icon": "🖼️",
            "type": "warn",
            "title": LANG.get("action_avatar_title", "头像跨平台复用"),
            "detail": LANG.get("action_avatar_detail",
                               "你的头像在 {n} 个平台相同或高度相似，"
                               "容易被跨平台关联追踪。建议为不同平台使用不同头像。")
                     .format(n=len(avatar_sites))
                     + " (" + ", ".join(sites) + ")",
        })

    # 3. Many sites found → high digital exposure
    if len(true_hits) >= 8:
        actions.append({
            "icon": "📡",
            "type": "warn",
            "title": LANG.get("action_exposure_title", "数字足迹较广"),
            "detail": LANG.get("action_exposure_detail",
                               "你在 {n} 个平台有公开账号。建议定期审查，"
                               "注销不再使用的账号以降低信息泄露面。")
                     .format(n=len(true_hits)),
        })

    # 4. Empty profiles → delete or update
    empty_profiles = [p for p in profiles if not p.get("display_name") and not p.get("bio")]
    if empty_profiles:
        e_sites = [p.get("site_id", "") for p in empty_profiles]
        actions.append({
            "icon": "👻",
            "type": "info",
            "title": LANG.get("action_empty_title", "空白/僵尸账号"),
            "detail": LANG.get("action_empty_detail",
                               "以下平台存在您的账号但无公开资料：{sites}。"
                               "建议注销或补充隐私设置。")
                     .format(sites=", ".join(e_sites)),
        })

    # 5. Same username everywhere → easy to track
    if len(true_hits) >= 5:
        actions.append({
            "icon": "🎯",
            "type": "info",
            "title": LANG.get("action_username_title", "用户名一致暴露关联"),
            "detail": LANG.get("action_username_detail",
                               "你在 {n} 个平台使用相同或相似用户名，"
                               "陌生人可以通过用户名搜索到你的全部网络身份。"
                               "考虑在不同平台使用不同用户名以增强隐私。")
                     .format(n=len(true_hits)),
        })

    return actions


def _render_actions(actions: list[dict], lang: str = "zh") -> str:
    """Render action items section."""
    if not actions:
        return ""

    LANG = _STRINGS.get(lang, _STRINGS["zh"])
    items_html = ""
    for a in actions:
        items_html += (
            f'<div class="action-item {a["type"]}">'
            f'<div class="action-icon">{a["icon"]}</div>'
            f'<div class="action-body">'
            f'<div class="action-title">{_esc(a["title"])}</div>'
            f'<div class="action-detail">{_esc(a["detail"])}</div>'
            f'</div></div>'
        )

    return (
        '<div class="section"><div class="section-card">'
        '<div class="section-header">'
        '<span class="badge">建议</span>'
        f'<h2>{LANG.get("actions_heading", "可操作建议")}</h2>'
        '</div>'
        f'<p class="section-explain">{LANG.get("actions_explain", "基于搜索结果自动生成的安全和隐私建议。")}</p>'
        f'<div class="action-items">{items_html}</div>'
        '</div></div>'
    )
