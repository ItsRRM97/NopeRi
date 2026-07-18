"""Persist Naukri search API variations tried across NopeRi runs."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STATE_VERSION = 1
DEFAULT_STATE_PATH = Path(__file__).resolve().parents[1] / "search_variation_state.json"


def state_path() -> Path:
    override = os.getenv("SEARCH_VARIATION_STATE_PATH", "").strip()
    return Path(override).expanduser() if override else DEFAULT_STATE_PATH


def variation_key(keyword: str, city: str, exp: int, job_age: int, page: int) -> str:
    return f"{keyword}|{city}|exp{exp}|age{job_age}|p{page}"


def _empty_state() -> dict:
    return {
        "version": STATE_VERSION,
        "updated_at": None,
        "tried": {},
        "runs": [],
    }


def load_state() -> dict:
    path = state_path()
    if not path.exists():
        return _empty_state()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty_state()
    if not isinstance(data, dict):
        return _empty_state()
    data.setdefault("version", STATE_VERSION)
    data.setdefault("tried", {})
    data.setdefault("runs", [])
    return data


def save_state(state: dict) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state["version"] = STATE_VERSION
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def is_tried(state: dict, key: str) -> bool:
    return key in state.get("tried", {})


def record_variation(
    state: dict,
    key: str,
    *,
    keyword: str,
    city: str,
    exp: int,
    job_age: int,
    page: int,
    fetched: int,
    new: int,
    keep_going: bool,
    status: str = "ok",
    search_round: int | None = None,
) -> None:
    state.setdefault("tried", {})[key] = {
        "keyword": keyword,
        "city": city,
        "exp": exp,
        "job_age": job_age,
        "page": page,
        "search_round": search_round,
        "fetched": fetched,
        "new": new,
        "keep_going": keep_going,
        "status": status,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)


def start_run(state: dict) -> dict:
    run = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stopped_at": None,
        "stopped_reason": None,
        "variations_tried_this_run": 0,
        "variations_skipped_resume": 0,
    }
    state.setdefault("runs", []).append(run)
    save_state(state)
    return run


def finish_run(
    state: dict,
    run: dict,
    *,
    stopped_reason: str,
    tried_this_run: int,
    skipped_resume: int,
) -> None:
    run["stopped_at"] = datetime.now(timezone.utc).isoformat()
    run["stopped_reason"] = stopped_reason
    run["variations_tried_this_run"] = tried_this_run
    run["variations_skipped_resume"] = skipped_resume
    save_state(state)


def reset_state() -> None:
    path = state_path()
    if path.exists():
        path.unlink()
    save_state(_empty_state())


def estimate_variation_space(
    *,
    titles: int,
    cities: int,
    exp_levels: int,
    age_levels: int,
    max_pages: int,
) -> int:
    return titles * cities * exp_levels * age_levels * max_pages


def summarize(state: dict, *, space_estimate: int | None = None) -> dict:
    tried = len(state.get("tried", {}))
    summary = {"tried": tried}
    if space_estimate:
        summary["space_estimate"] = space_estimate
        summary["remaining_estimate"] = max(0, space_estimate - tried)
    return summary
