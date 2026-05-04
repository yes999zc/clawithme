#!/usr/bin/env python3
"""Verify a single site's detection rule by probing known accounts.

Usage: python scripts/verify_site.py <site_id>
       python scripts/verify_site.py --all
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clawithme.engine.engines import Engine
from clawithme.engine.http_client import HttpClient, HttpResponse
from clawithme.engine.loader import get_engine_for_site, load_engines
from clawithme.logging import get_logger, setup_logging


def load_site(site_id: str) -> dict:
    """Find and load a site JSON by id."""
    data_dir = Path(__file__).resolve().parent.parent / "data" / "sites"
    for json_file in data_dir.rglob("*.json"):
        if json_file.name == f"{site_id}.json":
            return json.loads(json_file.read_text())
    raise FileNotFoundError(f"Site '{site_id}' not found in data/sites/")


def _classify_response(
    resp: HttpResponse, check: dict, engine: Engine
) -> bool:
    """Check if response matches the site's classification rule.

    Uses Engine._classify() logic for status_code, message, and headers classifiers.
    """
    classifier = engine.classifier

    if classifier == "status_code":
        expected = check.get("expected", 200)
        return resp.status_code == expected

    if classifier == "message":
        presence_strs = check.get("presence_strs", [])
        absence_strs = check.get("absence_strs", [])
        body = resp.text
        has_presence = not presence_strs or all(s in body for s in presence_strs)
        has_absence = not absence_strs or all(s not in body for s in absence_strs)
        return has_presence and has_absence

    if classifier == "headers":
        expected_headers = check.get("expected_headers", {})
        return all(
            resp.headers.get(k) == v
            for k, v in expected_headers.items()
        )

    # Unknown classifier — fall back to status_code
    return resp.status_code == check.get("expected", 200)


def verify_site(site: dict, engines: dict[str, Engine] | None = None) -> dict:
    """Probe a site's known accounts and report results."""
    logger = get_logger(site_id=site["id"])
    client = HttpClient(timeout_ms=8000)
    check = site["check"]
    engine_ref = site["engine_ref"]

    # Load engine for classification
    if engines is None:
        engines = load_engines()
    engine = get_engine_for_site(site, engines)

    result = {
        "site_id": site["id"],
        "site_name": site["name"],
        "engine": engine_ref,
        "classifier": engine.classifier if engine else "unknown",
        "deprecated": site.get("deprecated", False),
        "checks": [],
    }

    # Probe known accounts (positive cases)
    for account in check.get("known_accounts", []):
        url = Engine._substitute(check["probe_url"], check, account)
        try:
            resp = client.get(url)
            ok = _classify_response(resp, check, engine) if engine else (
                resp.status_code == check.get("expected", 200)
            )
            result["checks"].append({
                "account": account,
                "type": "known_existing",
                "url": url,
                "status": resp.status_code,
                "classifier": engine.classifier if engine else "status_code",
                "pass": ok,
                "body_len": len(resp.text) if resp.text else 0,
            })
            logger.debug("probe_known", account=account, status=resp.status_code)
        except (OSError, ValueError, TimeoutError) as e:
            result["checks"].append({
                "account": account, "type": "known_existing",
                "url": url, "error": str(e), "pass": False,
            })

    # Probe unclaimed accounts (negative cases)
    for account in check.get("known_unclaimed", []):
        url = Engine._substitute(check["probe_url"], check, account)
        try:
            resp = client.get(url)
            ok = not _classify_response(resp, check, engine) if engine else (
                resp.status_code != check.get("expected", 200)
            )
            result["checks"].append({
                "account": account,
                "type": "known_unclaimed",
                "url": url,
                "status": resp.status_code,
                "classifier": engine.classifier if engine else "status_code",
                "pass": ok,
                "body_len": len(resp.text) if resp.text else 0,
            })
            logger.debug("probe_unclaimed", account=account, status=resp.status_code)
        except (OSError, ValueError, TimeoutError) as e:
            result["checks"].append({
                "account": account, "type": "known_unclaimed",
                "url": url, "error": str(e), "pass": False,
            })

    # Compute summary
    all_checks = result["checks"]
    passed = sum(1 for c in all_checks if c["pass"])
    result["summary"] = {
        "total": len(all_checks),
        "passed": passed,
        "failed": len(all_checks) - passed,
        "healthy": passed == len(all_checks) and len(all_checks) > 0,
    }

    return result


def format_result(result: dict) -> str:
    """Pretty-print a verification result."""
    s = result["summary"]
    status = "✅ HEALTHY" if s["healthy"] else "❌ DEGRADED"
    if result["deprecated"]:
        status = "⚠️ DEPRECATED (skip)"

    lines = [
        f"{status}  {result['site_name']} ({result['site_id']})  "
        f"engine={result['engine']}  classifier={result['classifier']}",
        f"         {s['passed']}/{s['total']} checks passed",
    ]

    for check in result["checks"]:
        icon = "✅" if check["pass"] else "❌"
        lines.append(
            f"  {icon} {check['type']}: {check['account']} "
            f"→ {check.get('status', 'ERR')}"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Verify site detection rules")
    parser.add_argument("site_id", nargs="?", help="Site ID to verify")
    parser.add_argument("--all", action="store_true", help="Verify all sites")
    args = parser.parse_args()

    setup_logging()
    engines = load_engines()

    if args.all:
        data_dir = Path(__file__).resolve().parent.parent / "data" / "sites"
        all_results = []
        for json_file in sorted(data_dir.rglob("*.json")):
            if "migrated" in json_file.parts:
                continue
            site = json.loads(json_file.read_text())
            result = verify_site(site, engines)
            print(format_result(result))
            print()
            all_results.append(result)

        # Summary
        healthy = sum(1 for r in all_results if r["summary"]["healthy"])
        deprecated = sum(1 for r in all_results if r["deprecated"])
        print(
            f"---\nTotal: {len(all_results)} sites | "
            f"{healthy} healthy | {deprecated} deprecated"
        )
    else:
        if not args.site_id:
            parser.error("Must specify site_id or --all")
        site = load_site(args.site_id)
        result = verify_site(site, engines)
        print(format_result(result))


if __name__ == "__main__":
    main()
