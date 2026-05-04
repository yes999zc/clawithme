"""Engine runner — executes detection logic defined in engines.json.

Key design decisions:
- Template variables use manual dict replacement (no Jinja2) for sandbox safety.
- Variable whitelist: only {username}, {e_code}, {e_string}, {m_string},
  {e_headers}, {probe_url}, {url_subpath} are allowed.
- Detection type (status_code / message / headers) is determined by
  engine.classifier — sites never declare their own type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clawithme.engine.http_client import HttpClient, HttpResponse
from clawithme.logging import get_logger

logger = get_logger()

# Allowed template variables (whitelist) — enforced in _substitute()
_ALLOWED_VARS = {
    "{username}", "{e_code}", "{e_string}", "{m_string}",
    "{probe_url}", "{url_subpath}",
}


@dataclass
class EngineResult:
    """Result of a single site probe."""

    site_id: str
    site_name: str
    url_probed: str
    status_code: int
    exists: bool
    engine: str
    classifier: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Engine:
    """Detection engine — knows 'how to check', receives 'what to check'."""

    def __init__(self, engine_def: dict, http_client: HttpClient | None = None):
        self._def = engine_def
        self._http = http_client or HttpClient()
        self._log = get_logger(engine=engine_def.get("name", "?"))

    @property
    def name(self) -> str:
        return self._def.get("name", "?")

    @property
    def classifier(self) -> str:
        """Detection type: status_code | message | headers."""
        return self._def["classifier"]

    @property
    def params(self) -> dict:
        return self._def.get("params", {})

    def probe(self, site: dict, username: str) -> EngineResult:
        """Probe a site for a given username."""
        check = site.get("check", {})
        probe_template = check.get("probe_url", site.get("canonical_url", ""))
        url = self._substitute(probe_template, check, username)

        try:
            resp = self._http.get(url, headers=check.get("headers"))
            exists = self._classify(resp, check)
            return EngineResult(
                site_id=site["id"],
                site_name=site["name"],
                url_probed=url,
                status_code=resp.status_code,
                exists=exists,
                engine=self.name,
                classifier=self.classifier,
                details={"body_len": len(resp.text) if resp.text else 0},
            )
        except (OSError, ValueError, TimeoutError) as e:
            self._log.error("probe_failed", site_id=site["id"], error=str(e))
            return EngineResult(
                site_id=site["id"],
                site_name=site["name"],
                url_probed=url,
                status_code=0,
                exists=False,
                engine=self.name,
                classifier=self.classifier,
                error=str(e),
            )

    def _classify(self, resp: HttpResponse, check: dict) -> bool:
        """Classify response as 'account exists' or not."""
        if self.classifier == "status_code":
            expected = check.get("expected", 200)
            return resp.status_code == expected

        if self.classifier == "message":
            text = resp.text or ""
            presence = check.get("presence_strs", [])
            absence = check.get("absence_strs", [])
            has_presence = any(s in text for s in presence) if presence else True
            has_absence = any(s in text for s in absence)
            return has_presence and not has_absence

        if self.classifier == "headers":
            expected_headers = check.get("expected_headers", {})
            return all(
                resp.headers.get(k) == v
                for k, v in expected_headers.items()
            )

        # Unknown classifier — fall back to status_code
        expected = check.get("expected", 200)
        return resp.status_code == expected

    @staticmethod
    def _substitute(template: str, check: dict, username: str) -> str:
        """Safely substitute template variables. Whitelist enforced.

        Raises ValueError if template contains unknown {variable} patterns.
        """
        # Validate: no unknown template variables
        import re
        found = set(re.findall(r"\{(\w+)\}", template))
        allowed_names = {v.strip("{}") for v in _ALLOWED_VARS}
        unknown = found - allowed_names
        if unknown:
            raise ValueError(
                f"Unknown template variable(s): {unknown}. "
                f"Allowed: {allowed_names}"
            )

        subs = {
            "{username}": username,
            "{e_code}": str(check.get("expected", 200)),
            "{e_string}": (
                str(check.get("presence_strs", [""])[0])
                if check.get("presence_strs") else ""
            ),
            "{m_string}": (
                str(check.get("absence_strs", [""])[0])
                if check.get("absence_strs") else ""
            ),
            "{probe_url}": check.get("probe_url", template),
            "{url_subpath}": check.get("subpath", ""),
        }
        result = template
        for var, val in subs.items():
            result = result.replace(var, val)
        return result
