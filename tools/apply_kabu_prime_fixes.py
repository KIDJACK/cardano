#!/usr/bin/env python3
"""Apply audited execution/point-in-time safeguards to the embedded Prime backtest."""
from __future__ import annotations

import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_kabu_prime_fixes.py PATH")
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''    df = pd.DataFrame(parsed)\n    # Combine multiple ranking windows on the same site date into one ticker-day event.\n    df = df.sort_values(["signal_date", "code", "window_hours", "rank", "capture_timestamp"])\n    grouped = []\n    for (_, _), g in df.groupby(["signal_date", "code"], sort=True):\n        first = g.iloc[0].to_dict()\n        first["rank"] = int(g["rank"].min())\n        first["window_hours"] = int(g["window_hours"].min())\n        first["res_count"] = int(g["res_count"].max())\n        first["yahoo_topics"] = int(g["yahoo_topics"].max())\n        first["quality_tag"] = bool(g["quality_tag"].any())\n        first["themes"] = " | ".join(sorted({x for x in g["themes"].astype(str) if x}))\n        grouped.append(first)\n    events = pd.DataFrame(grouped).sort_values(["signal_date", "rank", "code"]).reset_index(drop=True)\n''',
        '''    df = pd.DataFrame(parsed)\n    # Keep each archived snapshot/window as an actual observed event.  Combining the\n    # best rank from one window with the shortest window from another would create a\n    # synthetic signal that never appeared on the site.  Duplicate rows from an exact\n    # replay are removed, while same-day observations from different snapshots remain.\n    events = (\n        df.sort_values(["signal_date", "capture_timestamp", "window_hours", "rank", "code"])\n        .drop_duplicates(["capture_timestamp", "signal_date", "code", "window_hours", "rank"])\n        .reset_index(drop=True)\n    )\n''',
        "actual_snapshot_events",
    )

    text = replace_once(
        text,
        '''        signal_ts = pd.Timestamp(event["signal_date"])\n        found = row_on_or_before(df, signal_ts)\n        bench_found = row_on_or_before(bench, signal_ts)\n''',
        '''        signal_ts = pd.Timestamp(event["signal_date"])\n        # Conservative point-in-time rule: ranking-day OHLC is never used as a feature,\n        # even when the archived snapshot happened after the close.  This removes any\n        # ambiguity about intraday capture time and prevents same-day-close look-ahead.\n        feature_cutoff = signal_ts - pd.Timedelta(days=1)\n        found = row_on_or_before(df, feature_cutoff)\n        bench_found = row_on_or_before(bench, feature_cutoff)\n''',
        "prior_close_features",
    )

    text = replace_once(
        text,
        '''    entry_idx = start_idx\n    entry_raw: float | None = None\n    if rule.entry_mode == "next_open":\n        entry_raw = float(df.iloc[entry_idx]["open"])\n    elif rule.entry_mode == "pullback3":\n        limit_price = float(event["feature_close"]) * 1.005\n        entry_raw = None\n        for idx in range(start_idx, min(start_idx + 3, len(df))):\n            bar = df.iloc[idx]\n            if float(bar["open"]) <= limit_price:\n                entry_idx = idx\n                entry_raw = float(bar["open"])\n                break\n            if float(bar["low"]) <= limit_price:\n                entry_idx = idx\n                entry_raw = limit_price\n                break\n''',
        '''    entry_idx = start_idx\n    entry_raw: float | None = None\n    entry_intraday_limit = False\n    if rule.entry_mode == "next_open":\n        entry_raw = float(df.iloc[entry_idx]["open"])\n    elif rule.entry_mode == "pullback3":\n        limit_price = float(event["feature_close"]) * 1.005\n        entry_raw = None\n        for idx in range(start_idx, min(start_idx + 3, len(df))):\n            bar = df.iloc[idx]\n            if float(bar["open"]) <= limit_price:\n                entry_idx = idx\n                entry_raw = float(bar["open"])\n                break\n            if float(bar["low"]) <= limit_price:\n                entry_idx = idx\n                entry_raw = limit_price\n                entry_intraday_limit = True\n                break\n''',
        "intraday_limit_flag",
    )

    text = replace_once(
        text,
        '''    entry_exec = entry_raw * (1 + slippage)\n    stop = entry_raw * (1 - rule.stop_pct) if rule.stop_pct else None\n    target = entry_raw * (1 + rule.target_pct) if rule.target_pct else None\n    last_idx = min(entry_idx + rule.hold_days - 1, len(df) - 1)\n    exit_idx = last_idx\n''',
        '''    # Require the complete planned holding horizon.  Truncating a 10/20-session\n    # strategy at the current data boundary would mix censored one-day trades into the\n    # holdout and can materially bias the result.\n    planned_last_idx = entry_idx + rule.hold_days - 1\n    if planned_last_idx >= len(df):\n        return None\n    entry_exec = entry_raw * (1 + slippage)\n    stop = entry_raw * (1 - rule.stop_pct) if rule.stop_pct else None\n    target = entry_raw * (1 + rule.target_pct) if rule.target_pct else None\n    last_idx = planned_last_idx\n    exit_idx = last_idx\n''',
        "complete_holding_horizon",
    )

    text = replace_once(
        text,
        '''    for idx in range(entry_idx, last_idx + 1):\n        bar = df.iloc[idx]\n        o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])\n        if stop is not None and o <= stop:\n''',
        '''    for idx in range(entry_idx, last_idx + 1):\n        bar = df.iloc[idx]\n        o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])\n        if idx == entry_idx and entry_intraday_limit:\n            # The daily high/open can occur before an intraday buy-limit fill.  To avoid\n            # an impossible same-day target profit, only a subsequent adverse excursion\n            # is recognized on the fill day; targets start from the following session.\n            if stop is not None and l <= stop:\n                exit_idx, exit_raw, reason = idx, float(stop), "stop_on_limit_fill_day"\n                break\n            continue\n        if stop is not None and o <= stop:\n''',
        "intraday_limit_execution_order",
    )

    text = replace_once(
        text,
        '''def bootstrap_mean_ci(values: np.ndarray, seed: int = 20260826, draws: int = 3000) -> tuple[float, float]:\n    if len(values) < 2:\n        return (math.nan, math.nan)\n    rng = np.random.default_rng(seed)\n    means = np.empty(draws)\n    for i in range(draws):\n        means[i] = rng.choice(values, size=len(values), replace=True).mean()\n    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))\n\n\ndef metrics(trades: list[Trade], with_ci: bool = False) -> dict[str, Any]:\n    arr = np.array([t.return_net for t in trades], dtype=float)\n''',
        '''def bootstrap_mean_ci_by_signal_date(trades: list[Trade], seed: int = 20260826, draws: int = 3000) -> tuple[float, float]:\n    # Trades triggered by the same archived date share the same market shock.  Resample\n    # whole signal-date clusters rather than pretending that those trades are independent.\n    if len(trades) < 2:\n        return (math.nan, math.nan)\n    grouped: dict[str, list[float]] = defaultdict(list)\n    for trade in trades:\n        grouped[trade.signal_date].append(trade.return_net)\n    clusters = list(grouped.values())\n    if len(clusters) < 2:\n        return (math.nan, math.nan)\n    rng = np.random.default_rng(seed)\n    means = np.empty(draws)\n    for i in range(draws):\n        sampled = rng.integers(0, len(clusters), size=len(clusters))\n        values = [value for idx in sampled for value in clusters[int(idx)]]\n        means[i] = float(np.mean(values))\n    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))\n\n\ndef metrics(trades: list[Trade], with_ci: bool = False) -> dict[str, Any]:\n    arr = np.array([t.return_net for t in trades], dtype=float)\n''',
        "cluster_bootstrap",
    )

    text = replace_once(
        text,
        '''    ci = bootstrap_mean_ci(arr) if with_ci else (math.nan, math.nan)\n''',
        '''    ci = bootstrap_mean_ci_by_signal_date(trades) if with_ci else (math.nan, math.nan)\n''',
        "cluster_bootstrap_call",
    )

    text = replace_once(
        text,
        '''        min_train = 20\n        min_val = 8\n''',
        '''        min_train = 30\n        min_val = 15\n''',
        "minimum_samples",
    )

    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
