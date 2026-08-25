#!/usr/bin/env python3
"""Enumerate Wayback captures that can reconstruct Kabu-Sokuhou attention rankings."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

UA = "Mozilla/5.0 (compatible; KabuPrimeBacktest/1.0; research-only)"
CDX = "https://web.archive.org/cdx/search/cdx"
OUT = Path("out")


def get_json(params: dict[str, str], retries: int = 4):
    url = CDX + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return url, json.load(resp)
        except Exception as exc:  # pragma: no cover - network reconnaissance
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"CDX failed after {retries} attempts: {url}: {last}")


def rows_from(data):
    if not data or len(data) < 2:
        return []
    header = data[0]
    return [dict(zip(header, row)) for row in data[1:]]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    queries = {
        "prefix_home": {
            "url": "kabu-sokuhou.com/home/index/",
            "matchType": "prefix",
            "from": "20220404",
            "to": "20260825",
            "output": "json",
            "filter": "statuscode:200",
            "fl": "timestamp,original,statuscode,digest,mimetype",
            "collapse": "timestamp:8,original",
            "limit": "50000",
        },
        "root": {
            "url": "kabu-sokuhou.com/",
            "matchType": "exact",
            "from": "20220404",
            "to": "20260825",
            "output": "json",
            "filter": "statuscode:200",
            "fl": "timestamp,original,statuscode,digest,mimetype",
            "collapse": "timestamp:8,original",
            "limit": "50000",
        },
        "www_root": {
            "url": "www.kabu-sokuhou.com/",
            "matchType": "exact",
            "from": "20220404",
            "to": "20260825",
            "output": "json",
            "filter": "statuscode:200",
            "fl": "timestamp,original,statuscode,digest,mimetype",
            "collapse": "timestamp:8,original",
            "limit": "50000",
        },
    }

    all_rows: list[dict[str, str]] = []
    report = {}
    for name, params in queries.items():
        url, data = get_json(params)
        rows = rows_from(data)
        report[name] = {"query": url, "rows": len(rows)}
        (OUT / f"cdx-{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        all_rows.extend(rows)
        time.sleep(1)

    # Keep pages whose content normally contains the general 2ch ranking table.
    def relevant(original: str) -> bool:
        u = urllib.parse.urlsplit(original)
        path = u.path.rstrip("/")
        if path == "":
            return True
        if not path.startswith("/home/index"):
            return False
        # Exclude category/theme filtered pages. Keep default, ranking time windows and pagination.
        blocked = ("/cate___", "/theme___", "/ca___")
        if any(x in path for x in blocked):
            return False
        if "isort___" in path and "isort___2ch" not in path:
            return False
        return True

    unique = {}
    for row in all_rows:
        if not relevant(row.get("original", "")):
            continue
        key = (row.get("timestamp"), row.get("original"), row.get("digest"))
        unique[key] = row
    selected = sorted(unique.values(), key=lambda r: (r["timestamp"], r["original"]))

    by_year = Counter(r["timestamp"][:4] for r in selected)
    by_path = Counter(urllib.parse.urlsplit(r["original"]).path for r in selected)
    report["selected"] = {
        "rows": len(selected),
        "unique_dates": len({r["timestamp"][:8] for r in selected}),
        "by_year": dict(sorted(by_year.items())),
        "top_paths": by_path.most_common(30),
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
