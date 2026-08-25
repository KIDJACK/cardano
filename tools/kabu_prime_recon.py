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
                "--retry-delay", "2", "--connect-timeout", "20", "--max-time", "180",
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
    queries: dict[str, dict[str, str]] = {}
    for year in range(2022, 2027):
        queries[f"prefix_home_{year}"] = {
            "url": "kabu-sokuhou.com/home/index/",
            "matchType": "prefix",
            "from": f"{year}0404" if year == 2022 else str(year),
            "to": "20260825" if year == 2026 else str(year),
            "output": "json",
            "filter": "statuscode:200",
            "fl": "timestamp,original,statuscode,digest,mimetype",
            "collapse": "timestamp:8,original",
            "limit": "10000",
        }
    for host_name, host in (("root", "kabu-sokuhou.com/"), ("www_root", "www.kabu-sokuhou.com/")):
        queries[host_name] = {
            "url": host,
            "matchType": "exact",
            "from": "20220404",
            "to": "20260825",
            "output": "json",
            "filter": "statuscode:200",
            "fl": "timestamp,original,statuscode,digest,mimetype",
            "collapse": "timestamp:8,original",
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
        except Exception as exc:  # retain other successful query results
            report[name] = {"rows": 0, "ok": False, "error": str(exc)}
        time.sleep(2)

    def relevant(original: str) -> bool:
        u = urllib.parse.urlsplit(original)
        path = u.path.rstrip("/")
        if path == "":
            return True
        if not path.startswith("/home/index"):
            return False
        blocked = ("/cate___", "/theme___", "/ca___")
        if any(x in path for x in blocked):
            return False
        if "/page___" in path and "/page___1" not in path:
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
