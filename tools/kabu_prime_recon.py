#!/usr/bin/env python3
"""Enumerate Wayback captures that can reconstruct Kabu-Sokuhou attention rankings."""
from __future__ import annotations

import json
import subprocess
import time
import urllib.parse
from collections import Counter
from pathlib import Path

UA = "Mozilla/5.0 (compatible; KabuPrimeBacktest/1.0; research-only)"
CDX = "https://web.archive.org/cdx/search/cdx"
OUT = Path("out")


def get_json(params: dict[str, str], retries: int = 5):
    url = CDX + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        proc = subprocess.run(
            [
                "curl", "-A", UA, "-L", "--retry", "4", "--retry-all-errors",
                "--retry-delay", "2", "--connect-timeout", "20", "--max-time", "120",
                "-fsS", url,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            try:
                return url, json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                last = RuntimeError(f"invalid JSON: {exc}; head={proc.stdout[:200]!r}")
        else:
            last = RuntimeError(f"curl rc={proc.returncode}: {proc.stderr[-500:]}")
        time.sleep(2 ** attempt)
    raise RuntimeError(f"CDX failed after {retries} attempts: {url}: {last}")


def rows_from(data):
    if not data or len(data) < 2:
        return []
    header = data[0]
    return [dict(zip(header, row)) for row in data[1:]]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    paths = [
        "/",
        "/home/index/",
        "/home/index/isort___2ch/",
        "/home/index/isort___2ch/ilimit___1/",
        "/home/index/isort___2ch/ilimit___3/",
        "/home/index/isort___2ch/ilimit___6/",
        "/home/index/isort___2ch/ilimit___12/",
        "/home/index/isort___2ch/ilimit___24/",
        "/home/index/isort___2ch/ilimit___48/",
        "/home/index/page___1/isort___2ch/ilimit___12/",
    ]
    queries: dict[str, dict[str, str]] = {}
    for host in ("kabu-sokuhou.com", "www.kabu-sokuhou.com"):
        for index, path in enumerate(paths):
            key = f"{host.split('.')[0]}_{index:02d}"
            queries[key] = {
                "url": host + path,
                "matchType": "exact",
                "from": "20220404",
                "to": "20260825",
                "output": "json",
                "filter": "statuscode:200",
                "fl": "timestamp,original,statuscode,digest,mimetype",
                "collapse": "digest",
                "limit": "10000",
            }

    all_rows: list[dict[str, str]] = []
    report = {}
    for name, params in queries.items():
        try:
            url, data = get_json(params)
            rows = rows_from(data)
            report[name] = {"query": url, "rows": len(rows), "ok": True}
            (OUT / f"cdx-{name}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            all_rows.extend(rows)
        except Exception as exc:
            report[name] = {"rows": 0, "ok": False, "error": str(exc)}
        time.sleep(1)

    # One representative capture per calendar date and ranking window.
    candidates = {}
    for row in all_rows:
        original = row.get("original", "")
        path = urllib.parse.urlsplit(original).path
        window = 12
        for h in (1, 3, 6, 12, 24, 48):
            if f"ilimit___{h}" in path:
                window = h
                break
        key = (row.get("timestamp", "")[:8], window)
        previous = candidates.get(key)
        # Prefer the latest capture on that date for a complete window.
        if previous is None or row.get("timestamp", "") > previous.get("timestamp", ""):
            row = dict(row)
            row["window_hours"] = str(window)
            candidates[key] = row
    selected = sorted(candidates.values(), key=lambda r: (r["timestamp"], int(r["window_hours"])))

    by_year = Counter(r["timestamp"][:4] for r in selected)
    by_window = Counter(r["window_hours"] for r in selected)
    report["selected"] = {
        "rows": len(selected),
        "unique_dates": len({r["timestamp"][:8] for r in selected}),
        "by_year": dict(sorted(by_year.items())),
        "by_window_hours": dict(sorted(by_window.items(), key=lambda x: int(x[0]))),
    }
    (OUT / "captures-selected.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "recon-summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
