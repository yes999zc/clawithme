#!/usr/bin/env python3
"""Verify a single site's detection rule by probing known accounts.

Usage: python scripts/verify_site.py <site_id>
       python scripts/verify_site.py --all
"""

import json, sys, os, argparse
from pathlib import Path
from jsonschema import validate

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clawithme.engine.http_client import HttpClient
from clawithme.logging import setup_logging, new_trace_id, get_logger


def load_site(site_id: str) -> dict:
    """Find and load a site JSON by id."""
    data_dir = Path(__file__).resolve().parent.parent / "data" / "sites"
    for json_file in data_dir.rglob("*.json"):
        if json_file.name == f"{site_id}.json":
            return json.loads(json_file.read_text())
    raise FileNotFoundError(f"Site '{site_id}' not found in data/sites/")


def verify_site(site: dict) -> dict:
    """Probe a site's known accounts and report results."""
    logger = get_logger(site_id=site["id"])
    client = HttpClient(timeout_ms=8000)
    check = site["check"]
    probe_url = check["probe_url"]
    engine_ref = site["engine_ref"]

    result = {
        "site_id": site["id"],
        "site_name": site["name"],
        "engine": engine_ref,
        "deprecated": site.get("deprecated", False),
        "checks": [],
    }

    # Probe known accounts (positive cases)
    for account in check.get("known_accounts", []):
        url = probe_url.replace("{username}", account)
        try:
            resp = client.get(url)
            ok = resp.status_code == check.get("expected", 200)
            result["checks"].append({
                "account": account,
                "type": "known_existing",
                "url": url,
                "status": resp.status_code,
                "expected": check.get("expected", 200),
                "pass": ok,
                "body_len": len(resp.text) if resp.text else 0,
            })
            logger.debug("probe_known", account=account, status=resp.status_code, pass_=ok)
        except Exception as e:
            result["checks"].append({
                "account": account, "type": "known_existing",
                "url": url, "error": str(e), "pass": False,
            })

    # Probe unclaimed accounts (negative cases)
    for account in check.get("known_unclaimed", []):
        url = probe_url.replace("{username}", account)
        try:
            resp = client.get(url)
            ok = resp.status_code != check.get("expected", 200)
            result["checks"].append({
                "account": account,
                "type": "known_unclaimed",
                "url": url,
                "status": resp.status_code,
                "not_expected": check.get("expected", 200),
                "pass": ok,
                "body_len": len(resp.text) if resp.text else 0,
            })
            logger.debug("probe_unclaimed", account=account, status=resp.status_code, pass_=ok)
        except Exception as e:
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
        f"{status}  {result['site_name']} ({result['site_id']})  engine={result['engine']}",
        f"         {s['passed']}/{s['total']} checks passed",
    ]

    for check in result["checks"]:
        icon = "✅" if check["pass"] else "❌"
        lines.append(f"  {icon} {check['type']}: {check['account']} → {check.get('status', 'ERR')}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Verify site detection rules")
    parser.add_argument("site_id", nargs="?", help="Site ID to verify")
    parser.add_argument("--all", action="store_true", help="Verify all sites")
    args = parser.parse_args()

    setup_logging()

    if args.all:
        data_dir = Path(__file__).resolve().parent.parent / "data" / "sites"
        all_results = []
        for json_file in sorted(data_dir.rglob("*.json")):
            site = json.loads(json_file.read_text())
            result = verify_site(site)
            print(format_result(result))
            print()
            all_results.append(result)

        # Summary
        healthy = sum(1 for r in all_results if r["summary"]["healthy"])
        deprecated = sum(1 for r in all_results if r["deprecated"])
        print(f"---\nTotal: {len(all_results)} sites | {healthy} healthy | {deprecated} deprecated")
    else:
        if not args.site_id:
            parser.error("Must specify site_id or --all")
        site = load_site(args.site_id)
        result = verify_site(site)
        print(format_result(result))


if __name__ == "__main__":
    main()
