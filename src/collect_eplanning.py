#!/usr/bin/env python3
"""
Tradiesignal :: NSW ePlanning open-data collector
=================================================
Pulls Development Applications (DA), Complying Development Certificates (CDC)
and Construction Certificates (CC) from the NSW Planning Portal open data API
for the Hunter councils, and writes raw JSON snapshots to data/raw/.

Source ...... NSW Department of Planning, Housing and Infrastructure, ePlanning
              "Online DA Data API" family.
Endpoint .... GET https://api.apps1.nsw.gov.au/eplanning/data/v0/{service}
Auth ........ none (open data; no subscription key required for the v0 data feed)
Method ...... GET, with pagination + filter JSON passed as HTTP HEADERS
Licence ..... Creative Commons Attribution (CC-BY). Attribution required.
Cadence ..... upstream refreshes daily.

Verified live 2026-09-10.

Usage:
    python3 src/collect_eplanning.py --days 90
    python3 src/collect_eplanning.py --days 400 --out data/raw
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator

API_ROOT = "https://api.apps1.nsw.gov.au/eplanning/data/v0"

# Services confirmed live on the open v0 feed.
#   OnlineDA  - development applications (the pipeline: 6-24 months out)
#   OnlineCDC - complying development certificates (fast-track: weeks out)
#   OnlineCC  - construction certificates (imminent: work about to start)
SERVICES = ("OnlineDA", "OnlineCDC", "OnlineCC")

# Council names must match the API's Appendix 1 list exactly.
HUNTER_COUNCILS = [
    "Newcastle City Council",
    "Lake Macquarie City Council",
    "Maitland City Council",
    "Port Stephens Council",
    "Cessnock City Council",
]

PAGE_SIZE = 100
MAX_RETRIES = 4
THROTTLE_SECONDS = 0.35  # be a polite API citizen


def _request(service: str, filters: dict, page: int, page_size: int) -> dict:
    """One page of one service. Filters and pagination travel as headers."""
    url = f"{API_ROOT}/{service}"
    req = urllib.request.Request(
        url,
        headers={
            "PageSize": str(page_size),
            "PageNumber": str(page),
            "filters": json.dumps({"filters": filters}),
            "Accept": "application/json",
            "User-Agent": "Tradiesignal/1.0 (+https://tradiesignal.com.au) open-data collector",
        },
        method="GET",
    )

    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as err:
            last_err = err
            code = getattr(err, "code", None)
            # 4xx other than 429 will not fix themselves on retry
            if code and code != 429 and 400 <= code < 500:
                raise
            backoff = 2**attempt
            print(
                f"    ! {service} p{page} attempt {attempt}/{MAX_RETRIES} failed "
                f"({err}); retrying in {backoff}s",
                file=sys.stderr,
            )
            time.sleep(backoff)
    raise RuntimeError(f"{service} page {page} failed after {MAX_RETRIES} attempts") from last_err


def fetch_all(service: str, filters: dict, page_size: int = PAGE_SIZE) -> Iterator[dict]:
    """Yield every application record matching filters, following pagination."""
    page = 1
    total_pages = 1
    seen = 0
    while page <= total_pages:
        payload = _request(service, filters, page, page_size)
        total_pages = int(payload.get("TotalPages") or 0)
        total_count = int(payload.get("TotalCount") or 0)
        if page == 1:
            print(f"    {service}: {total_count} records across {total_pages} pages")
            if total_count == 0:
                return
        records = payload.get("Application") or []
        for record in records:
            seen += 1
            yield record
        page += 1
        time.sleep(THROTTLE_SECONDS)
    print(f"    {service}: pulled {seen}")


def collect(days: int, out_dir: Path, councils: list[str]) -> dict[str, Any]:
    """Pull every service for every council over the trailing `days` window."""
    out_dir.mkdir(parents=True, exist_ok=True)
    date_from = (date.today() - timedelta(days=days)).isoformat()
    stamp = date.today().isoformat()

    manifest: dict[str, Any] = {
        "collected_at": stamp,
        "window_days": days,
        "lodgement_date_from": date_from,
        "source": "NSW Planning Portal ePlanning open data API",
        "licence": "CC-BY (NSW Department of Planning, Housing and Infrastructure)",
        "endpoint_root": API_ROOT,
        "councils": councils,
        "counts": {},
        "files": {},
    }

    for service in SERVICES:
        rows: list[dict] = []
        print(f"[{service}]")
        for council in councils:
            print(f"  {council}")
            filters = {
                "CouncilName": [council],
                "LodgementDateFrom": date_from,
            }
            try:
                for record in fetch_all(service, filters):
                    record["_service"] = service
                    record["_council_query"] = council
                    rows.append(record)
            except Exception as err:  # keep going; log the gap
                print(f"    !! {council} / {service} aborted: {err}", file=sys.stderr)
                manifest.setdefault("errors", []).append(
                    {"service": service, "council": council, "error": str(err)}
                )

        path = out_dir / f"{service}_{stamp}.json"
        path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        manifest["counts"][service] = len(rows)
        manifest["files"][service] = str(path)
        print(f"  -> {len(rows)} records written to {path}\n")

    (out_dir / f"manifest_{stamp}.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect NSW ePlanning open data for the Hunter.")
    parser.add_argument("--days", type=int, default=90, help="trailing lodgement window in days")
    parser.add_argument("--out", default="data/raw", help="output directory")
    parser.add_argument(
        "--councils",
        nargs="*",
        default=HUNTER_COUNCILS,
        help="council names exactly as the API spells them",
    )
    args = parser.parse_args()

    manifest = collect(args.days, Path(args.out), args.councils)
    print("=" * 60)
    print(json.dumps(manifest["counts"], indent=2))
    if manifest.get("errors"):
        print(f"WARNING: {len(manifest['errors'])} source gaps — see manifest.", file=sys.stderr)


if __name__ == "__main__":
    main()
