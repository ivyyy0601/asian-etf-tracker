"""Monthly SSE emerging ETF roster refresh; failures preserve the last snapshot.

SSE publishes SCALE in 100 million CNY. Store scale_billion_cny = SCALE / 10.
The source does not publish a valuation date in this response; retrieval time
must never be presented as the scale's valuation date.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import re
import tempfile

import requests

SOURCE = "https://etf.sse.com.cn/fundlist/"
ENDPOINT = "https://query.sse.com.cn/commonQuery.do"
# Confirmed against SSE's COMMON_JJZWZ_JJLB_JJLX_C category tree.
ETF_CATEGORIES = {"F111", "F112", "F113", "F114", "F115", "F121", "F122", "F123", "F131", "F141", "F150"}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def fetch_roster():
    response = requests.get(ENDPOINT, params={
        "sqlId": "COMMON_JJZWZ_JJLB_L", "isPagination": "true",
        "pageHelp.pageSize": "10000", "pageHelp.pageNo": "1",
    }, headers={"Referer": SOURCE, "User-Agent": "Mozilla/5.0"}, timeout=(10, 40))
    response.raise_for_status()
    return response.json()


def build_roster(payload, previous, now):
    rows = payload["result"]
    total = int(payload["pageHelp"]["total"])
    if not rows or len(rows) != total or total < 100:
        raise ValueError("Incomplete source list; previous roster retained")
    old = {e["code"]: (industry, e) for industry, entries in previous["industries"].items() for e in entries}
    industries = {}
    seen = set()
    eligible = 0
    for row in rows:
        code = str(row["FUND_CODE"])
        if not re.fullmatch(r"\d{6}", code) or code in seen:
            raise ValueError("Invalid or duplicate source code")
        seen.add(code)
        category = row["CATEGORY"]
        if category.startswith("F1") and category not in ETF_CATEGORIES:
            raise ValueError("Unknown SSE ETF category; review required")
        if category not in ETF_CATEGORIES:
            continue
        listed = date.fromisoformat(row["LISTING_DATE"])
        if listed < date(2025, 1, 1) or listed > now.date():
            continue
        # Reject missing size rather than silently dropping an existing ETF.
        scale = float(row["SCALE"])
        if not math.isfinite(scale) or scale < 0:
            raise ValueError("Invalid fund scale")
        if scale < 10:
            continue
        eligible += 1
        industry = old[code][0] if code in old else "unclassified"
        entry = {
            "code": code, "name": row["FUND_ABBR"],
            "listing_date": listed.isoformat(), "scale_billion_cny": round(scale / 10, 6),
            "index": row["INDEX_NAME"], "currency": "CNY",
        }
        industries.setdefault(industry, []).append(entry)
    if not eligible or eligible < len(old) * 0.5:
        raise ValueError("Unexpected roster shrink; review required")
    for entries in industries.values():
        entries.sort(key=lambda e: (-e["scale_billion_cny"], e["code"]))
    return {
        "description": "Shanghai-listed ETFs listed since 2025-01-01 with scale >= CNY 1 billion; Shenzhen is not covered.",
        "generated_date": now.date().isoformat(), "refreshed_at": now.isoformat(),
        "source_url": SOURCE, "source_total": total, "scope": "Shanghai Stock Exchange",
        "scale_unit": "billion CNY", "scale_as_of": None,
        "industries": industries,
    }


def refresh(config_path, status_path, force=False, fetch=fetch_roster, now=None):
    now = now or datetime.now(timezone.utc)
    config_path, status_path = Path(config_path), Path(status_path)
    previous = json.loads(config_path.read_text(encoding="utf-8"))
    # Only our verified successful refresh metadata can suppress another refresh.
    if not force and previous.get("refreshed_at", "")[:7] == now.strftime("%Y-%m"):
        return True
    try:
        updated = build_roster(fetch(), previous, now)
        backup = status_path.parent / "roster_backups" / f"emerging-{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        atomic_json(backup, previous)
        atomic_json(config_path, updated)
    except Exception as exc:
        logging.warning("Emerging ETF roster refresh failed: %s", exc)
        atomic_json(status_path, {"status": "failed", "attempted_at": now.isoformat(),
                                 "last_success_at": previous.get("refreshed_at"), "error": str(exc)})
        return False
    atomic_json(status_path, {"status": "ok", "attempted_at": now.isoformat(),
                             "last_success_at": now.isoformat(), "count": sum(map(len, updated["industries"].values()))})
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    success = refresh(root / "a_share_etf_emerging.json",
                      Path(os.getenv("DATA_ROOT", str(root))) / "emerging_refresh_status.json", args.force)
    raise SystemExit(0 if success else 1)
