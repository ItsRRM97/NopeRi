#!/usr/bin/env python3
"""Backfill search_variation_state.json from NopeRi run logs (tee output).

Parses progress lines like:
  [Product Manager              | Hyderabad    | exp=4 | age=5 | p3]   20 fetched   12 new

Usage:
  python3 scripts/backfill_search_variations.py runs/20260709-175613-noperi-quota.log
  python3 scripts/backfill_search_variations.py runs/*-noperi-*.log
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.search_variation_state import load_state, record_variation, save_state, variation_key

PROGRESS_RE = re.compile(
    r"\[(?P<keyword>[^|]+?)\s*\|\s*(?P<city>[^|]+?)\s*\|\s*exp=(?P<exp>\d+)\s*\|\s*age=(?P<age>\d+)\s*\|\s*p(?P<page>\d+)\]"
    r"\s+(?P<fetched>\d+)\s+fetched\s+(?P<new>\d+)\s+new"
)
END_RE = re.compile(
    r"\[END\]\s+(?P<keyword>.+?)\s*\|\s*(?P<city>[^|]+?)\s*\|\s*exp=(?P<exp>\d+)\s*\|\s*age=(?P<age>\d+)\s*\|\s*p(?P<page>\d+)"
)
FAIL_RE = re.compile(
    r"\[FAIL\]\s+(?P<keyword>.+?)\s*\|\s*(?P<city>[^|]+?)\s*\|\s*exp=(?P<exp>\d+)\s*\|\s*age=(?P<age>\d+)\s*\|\s*p(?P<page>\d+)"
)


def _clean_keyword(text: str) -> str:
    return text.strip()


def _clean_city(text: str) -> str:
    city = text.strip()
    return "" if city == "All India" else city


def backfill_log(path: Path, state: dict) -> int:
    added = 0
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        for regex, status, fetched_default in (
            (PROGRESS_RE, "ok", None),
            (END_RE, "end_of_pages", 0),
            (FAIL_RE, "error", 0),
        ):
            m = regex.search(line)
            if not m:
                continue
            keyword = _clean_keyword(m.group("keyword"))
            city = _clean_city(m.group("city"))
            exp = int(m.group("exp"))
            job_age = int(m.group("age"))
            page = int(m.group("page"))
            key = variation_key(keyword, city, exp, job_age, page)
            if key in state.get("tried", {}):
                break
            fetched = int(m.group("fetched")) if fetched_default is None and "fetched" in m.groupdict() else fetched_default
            new = int(m.group("new")) if status == "ok" and "new" in m.groupdict() else 0
            keep_going = status == "ok" and fetched is not None and fetched >= 20
            record_variation(
                state,
                key,
                keyword=keyword,
                city=city,
                exp=exp,
                job_age=job_age,
                page=page,
                fetched=fetched or 0,
                new=new,
                keep_going=keep_going,
                status=status,
                search_round=None,
            )
            added += 1
            break
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill search variation state from NopeRi logs")
    parser.add_argument("logs", nargs="+", type=Path, help="Run log files (tee output)")
    args = parser.parse_args()

    state = load_state()
    before = len(state.get("tried", {}))
    for log_path in args.logs:
        if not log_path.exists():
            print(f"skip missing: {log_path}", file=sys.stderr)
            continue
        added = backfill_log(log_path, state)
        print(f"{log_path.name}: +{added} variations")
    after = len(state.get("tried", {}))
    save_state(state)
    print(f"state total: {before} -> {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
