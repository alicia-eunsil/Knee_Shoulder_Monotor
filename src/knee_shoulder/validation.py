from __future__ import annotations

from pathlib import Path

import pandas as pd

from .storage import load_existing_history


def _forward_return(prices: pd.Series, entry_index: int, forward_days: int) -> float | None:
    target = entry_index + forward_days
    if target >= len(prices):
        return None
    entry = prices.iloc[entry_index]
    future = prices.iloc[target]
    if not entry:
        return None
    return round(((future / entry) - 1.0) * 100.0, 2)


def _forward_path_stats(prices: pd.Series, entry_index: int, forward_days: int) -> dict[str, float | None]:
    target = entry_index + forward_days
    if target >= len(prices):
        return {"max_upside_pct": None, "max_drawdown_pct": None}

    entry = prices.iloc[entry_index]
    if not entry:
        return {"max_upside_pct": None, "max_drawdown_pct": None}

    window = prices.iloc[entry_index + 1 : target + 1].astype(float)
    if window.empty:
        return {"max_upside_pct": None, "max_drawdown_pct": None}

    rel = ((window / float(entry)) - 1.0) * 100.0
    return {
        "max_upside_pct": round(float(rel.max()), 2),
        "max_drawdown_pct": round(float(rel.min()), 2),
    }


def _build_market_regime_map(raw_dir: str, benchmark_symbol: str) -> tuple[dict[str, str], pd.Series]:
    benchmark_path = Path(raw_dir) / f"{benchmark_symbol}.csv"
    benchmark = load_existing_history(benchmark_path)
    if benchmark.empty:
        return {}, pd.Series(dtype=float)

    benchmark = benchmark.sort_values("date").reset_index(drop=True)
    benchmark["close"] = pd.to_numeric(benchmark["close"], errors="coerce")
    benchmark["ma_20"] = benchmark["close"].rolling(20).mean()
    benchmark["ret_20d"] = ((benchmark["close"] / benchmark["close"].shift(20)) - 1.0) * 100.0

    def classify(row: pd.Series) -> str:
        if pd.isna(row["ma_20"]) or pd.isna(row["ret_20d"]):
            return "Unknown"
        if row["close"] >= row["ma_20"] and row["ret_20d"] >= 0:
            return "Bull"
        if row["close"] < row["ma_20"] and row["ret_20d"] < 0:
            return "Bear"
        return "Sideways"

    benchmark["market_regime"] = benchmark.apply(classify, axis=1)
    regime_map = dict(zip(benchmark["date"].astype(str), benchmark["market_regime"]))
    close_map = benchmark.set_index(benchmark["date"].astype(str))["close"]
    return regime_map, close_map


def build_validation_rows(
    signals: pd.DataFrame,
    raw_dir: str,
    forward_days: list[int],
    benchmark_symbol: str = "005930",
) -> pd.DataFrame:
    rows = []
    regime_map, benchmark_close = _build_market_regime_map(raw_dir, benchmark_symbol)

    for signal in signals.itertuples(index=False):
        history_path = Path(raw_dir) / f"{signal.symbol}.csv"
        history = load_existing_history(history_path)
        if history.empty:
            continue
        history = history.sort_values("date").reset_index(drop=True)
        matches = history.index[history["date"] == signal.date].tolist()
        if not matches:
            continue
        idx = matches[0]
        close_series = history["close"].astype(float)
        row = {
            "signal_date": signal.date,
            "symbol": signal.symbol,
            "name": signal.name,
            "knee_score": signal.knee_score,
            "shoulder_score": signal.shoulder_score,
            "market_regime": regime_map.get(str(signal.date), "Unknown"),
        }
        future_returns = {}
        for days in forward_days:
            future_returns[f"ret_{days}d"] = _forward_return(close_series, idx, days)
        row.update(future_returns)

        stats_5d = _forward_path_stats(close_series, idx, 5)
        row["max_up_5d"] = stats_5d["max_upside_pct"]
        row["max_dd_5d"] = stats_5d["max_drawdown_pct"]

        benchmark_ret_5d = None
        if str(signal.date) in benchmark_close.index:
            benchmark_dates = benchmark_close.index.tolist()
            b_idx = benchmark_dates.index(str(signal.date))
            benchmark_ret_5d = _forward_return(benchmark_close.reset_index(drop=True), b_idx, 5)
        row["benchmark_ret_5d"] = benchmark_ret_5d

        row["knee_success"] = int((future_returns.get("ret_5d") or -999) >= 3.0)
        row["shoulder_success"] = int((future_returns.get("ret_5d") or 999) <= -3.0)
        rows.append(row)
    return pd.DataFrame(rows)
