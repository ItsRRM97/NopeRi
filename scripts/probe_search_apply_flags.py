#!/usr/bin/env python3
"""Sample Naukri search payloads and report Easy Apply vs external signals."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from src.client.apply_mode import classify_search_apply_mode
from src.client.job_client import JOB_SEARCH_URL, NaukriJobClient
from src.client.naukri_client import NaukriLoginClient

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(ROOT / ".env")
    username = os.environ["USERNAME"]
    password = os.environ["PASSWORD"]

    client = NaukriLoginClient(username, password)
    client.login()
    jc = NaukriJobClient(client)

    seo_key = jc._build_seo_key("Product Manager", "Hyderabad", 1)
    params = {
        "noOfResults": 20,
        "urlType": "search_by_keyword",
        "searchType": "adv",
        "keyword": "Product Manager",
        "k": "Product Manager",
        "pageNo": 1,
        "experience": 5,
        "jobAge": 5,
        "nignbevent_src": "jobsearchDeskGNB",
        "seoKey": seo_key,
        "src": "jobsearchDesk",
        "latLong": "",
    }
    res = jc._session.get(JOB_SEARCH_URL, headers=jc._search_headers(), params=params)
    res.raise_for_status()
    raw_jobs = res.json().get("jobDetails") or []

    counts: Counter[str] = Counter()
    flag_keys: set[str] = set()
    samples: dict[str, list] = {"easy": [], "external": [], "unknown": []}

    for raw in raw_jobs:
        mode = classify_search_apply_mode(raw)
        label = "easy" if mode is True else "external" if mode is False else "unknown"
        counts[label] += 1
        for key in raw:
            kl = key.lower()
            if any(x in kl for x in ("apply", "flag", "response", "mode", "easy")):
                flag_keys.add(key)
        if len(samples[label]) < 3:
            samples[label].append(
                {
                    "jobId": raw.get("jobId"),
                    "title": raw.get("title"),
                    "jobTypeFlags": raw.get("jobTypeFlags"),
                    "responseManager": raw.get("responseManager"),
                    "mode": raw.get("mode"),
                    "showMultipleApply": raw.get("showMultipleApply"),
                }
            )

    print(json.dumps({"counts": dict(counts), "interesting_keys": sorted(flag_keys), "samples": samples}, indent=2))


if __name__ == "__main__":
    main()
