"""Persist Naukri external-apply skips for Notion sync and browser apply queue."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NOPERI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSONL = NOPERI_ROOT / "external_jobs.jsonl"
DEFAULT_CSV = NOPERI_ROOT / "external_jobs.csv"
SOURCE_TAG = "Naukri (external apply)"

CSV_FIELDS = [
    "job_id",
    "title",
    "company",
    "naukri_url",
    "external_apply_url",
    "skipped_at",
    "source",
    "ai_score",
]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def naukri_job_url(job_id: str) -> str:
    return f"https://www.naukri.com/job-listings-{job_id}"


def external_jobs_jsonl_path() -> Path:
    raw = (os.getenv("EXTERNAL_JOBS_JSONL") or "").strip()
    return Path(raw) if raw else DEFAULT_JSONL


def external_jobs_csv_path() -> Path:
    raw = (os.getenv("EXTERNAL_JOBS_CSV") or "").strip()
    return Path(raw) if raw else DEFAULT_CSV


def load_external_job_ids(path: Path | None = None) -> set[str]:
    review_path = path or external_jobs_jsonl_path()
    if not review_path.exists():
        return set()
    ids: set[str] = set()
    with review_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            job_id = str(record.get("job_id") or "").strip()
            if job_id:
                ids.add(job_id)
    return ids


def load_external_jobs(path: Path | None = None) -> list[dict[str, Any]]:
    review_path = path or external_jobs_jsonl_path()
    if not review_path.exists():
        return []
    by_job: dict[str, dict[str, Any]] = {}
    with review_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            job_id = str(record.get("job_id") or "").strip()
            if job_id:
                by_job[job_id] = record
    return list(by_job.values())


def _append_csv_row(record: dict[str, Any], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow({field: record.get(field, "") for field in CSV_FIELDS})


def build_external_record(
    *,
    job_id: str,
    title: str,
    company: str,
    external_apply_url: str | None = None,
    ai_score: int | float | None = None,
    skipped_at: str | None = None,
    source_run: str | None = None,
    job_description: str | None = None,
) -> dict[str, Any]:
    naukri_url = naukri_job_url(job_id)
    record: dict[str, Any] = {
        "job_id": job_id,
        "title": title,
        "company": company,
        "naukri_url": naukri_url,
        "external_apply_url": external_apply_url or naukri_url,
        "skipped_at": skipped_at or utcnow_iso(),
        "source": SOURCE_TAG,
        "ai_score": ai_score,
        "source_run": source_run,
    }
    if job_description:
        record["job_description"] = job_description.strip()
    return record


def log_external_skip(
    *,
    job_id: str,
    title: str,
    company: str,
    external_apply_url: str | None = None,
    ai_score: int | float | None = None,
    source_run: str | None = None,
    job_description: str | None = None,
    jsonl_path: Path | None = None,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    """Append one external skip if job_id is not already logged."""
    jsonl = jsonl_path or external_jobs_jsonl_path()
    csv_out = csv_path or external_jobs_csv_path()
    seen = load_external_job_ids(jsonl)
    record = build_external_record(
        job_id=job_id,
        title=title,
        company=company,
        external_apply_url=external_apply_url,
        ai_score=ai_score,
        source_run=source_run,
        job_description=job_description,
    )
    if job_id in seen:
        record["action"] = "skipped_duplicate"
        return record

    jsonl.parent.mkdir(parents=True, exist_ok=True)
    with jsonl.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    _append_csv_row(record, csv_out)
    record["action"] = "logged"
    return record
