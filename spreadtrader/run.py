"""Run the full study and write results for the dashboard.

    python -m spreadtrader.run --prices data/prices.csv --out site/data
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import Config, run_pair
from .data import clean, load
from .metrics import summarize
from .universe import FUTURES, PAIRS

METHODS = ("kalman", "static")
BENCHMARK = "ES=F"


def _num(v, nd=5):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        return None if not math.isfinite(v) else round(float(v), nd)
    return v


def _clean_dict(d):
    if isinstance(d, dict):
        return {k: _clean_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_clean_dict(v) for v in d]
    return _num(d)


def portfolio(results: dict, method: str) -> pd.Series:
    """Equal capital in every pair; idle capital earns nothing."""
    rets = pd.concat({pid: r[method].frame["net"] for pid, r in results.items()}, axis=1)
    return rets.fillna(0.0).mean(axis=1)


def run_all(prices: pd.DataFrame, cfg: Config) -> dict:
    results = {}
    for pair in PAIRS:
        results[pair.id] = {m: run_pair(prices[pair.y], prices[pair.x], cfg, m) for m in METHODS}
    return results


def first_trade_date(results: dict) -> pd.Timestamp:
    starts = [w.start for r in results.values() for w in r["kalman"].windows]
    return min(starts)


def sensitivity(prices: pd.DataFrame, base: Config) -> list[dict]:
    """Same study with nearby entry/exit thresholds: are results robust or lucky?"""
    rows = []
    for entry in (1.5, 2.0, 2.5):
        for exit_ in (0.0, 0.5, 1.0):
            cfg = Config(**{**base.to_dict(), "entry_z": entry, "exit_z": exit_})
            res = {p.id: {"kalman": run_pair(prices[p.y], prices[p.x], cfg, "kalman")} for p in PAIRS}
            port = portfolio(res, "kalman")
            port = port[port.index >= first_trade_date(res)]
            s = summarize(port)
            rows.append({"entry_z": entry, "exit_z": exit_, "sharpe": s["sharpe"],
                         "cagr": s["cagr"], "max_drawdown": s["max_drawdown"]})
    return rows


def cost_sensitivity(results_prices: pd.DataFrame, base: Config) -> list[dict]:
    rows = []
    for c in (0.0, 3.0, 6.0, 10.0):
        cfg = Config(**{**base.to_dict(), "cost_bps": c})
        res = {p.id: {"kalman": run_pair(results_prices[p.y], results_prices[p.x], cfg, "kalman")} for p in PAIRS}
        port = portfolio(res, "kalman")
        port = port[port.index >= first_trade_date(res)]
        s = summarize(port)
        rows.append({"cost_bps": c, "sharpe": s["sharpe"], "cagr": s["cagr"]})
    return rows


def _series(s: pd.Series, nd=4):
    return [None if not np.isfinite(v) else round(float(v), nd) for v in s.values]


def write_outputs(prices: pd.DataFrame, clean_report: dict, cfg: Config, out: Path,
                  with_sensitivity: bool = True) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "pairs").mkdir(exist_ok=True)
    results = run_all(prices, cfg)
    start = first_trade_date(results)

    # ---- portfolio ------------------------------------------------------------
    ports = {m: portfolio(results, m) for m in METHODS}
    ports = {m: s[s.index >= start] for m, s in ports.items()}
    bench = prices[BENCHMARK].pct_change()
    bench = bench[bench.index >= start].reindex(ports["kalman"].index).fillna(0.0)

    port_summary = {m: summarize(s) for m, s in ports.items()}
    port_summary["buy_and_hold_sp500"] = summarize(bench)
    corr = float(ports["kalman"].corr(bench))

    weekly = lambda s: (1 + s).cumprod().resample("W-FRI").last()
    eq = pd.concat({"kalman": weekly(ports["kalman"]), "static": weekly(ports["static"]),
                    "sp500": weekly(bench)}, axis=1).dropna()

    # Year-by-year returns of the main strategy.
    yearly = (1 + ports["kalman"]).groupby(ports["kalman"].index.year).prod() - 1

    # ---- pairs ----------------------------------------------------------------
    pair_rows = []
    for pair in PAIRS:
        r = results[pair.id]
        row = {"id": pair.id, "label": pair.label, "y": pair.y, "x": pair.x,
               "y_name": FUTURES[pair.y].name, "x_name": FUTURES[pair.x].name,
               "group": FUTURES[pair.y].group, "why": pair.why}
        for m in METHODS:
            f = r[m].frame
            f = f[f.index >= start]
            row[m] = summarize(f["net"], r[m].trades, f["position"])
        w = r["kalman"].windows
        row["windows_eligible"] = int(sum(x.eligible for x in w))
        row["windows_total"] = len(w)
        pair_rows.append(row)

        f = r["kalman"].frame
        f = f[f.index >= start - pd.Timedelta(days=30)]
        detail = {
            "id": pair.id, "label": pair.label, "why": pair.why,
            "y_name": FUTURES[pair.y].name, "x_name": FUTURES[pair.x].name,
            "dates": [d.strftime("%Y-%m-%d") for d in f.index],
            "y_norm": _series(100 * f["y"] / f["y"].iloc[0], 2),
            "x_norm": _series(100 * f["x"] / f["x"].iloc[0], 2),
            "z": _series(f["z"], 3),
            "beta": _series(f["beta"], 4),
            "position": [int(v) for v in f["position"].values],
            "tradable": [bool(v) for v in f["tradable"].values],
            "equity_kalman": _series((1 + f["net"]).cumprod(), 4),
            "windows": [{"start": str(x.start.date()), "end": str(x.end.date()),
                         "pvalue": x.pvalue, "half_life": x.half_life,
                         "eligible": x.eligible} for x in r["kalman"].windows],
            "trades": r["kalman"].trades,
        }
        (out / "pairs" / f"{pair.id}.json").write_text(json.dumps(_clean_dict(detail)))

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "data": clean_report,
        "out_of_sample_start": str(start.date()),
        "config": cfg.to_dict(),
        "portfolio": port_summary,
        "correlation_with_sp500": corr,
        "equity": {"dates": [d.strftime("%Y-%m-%d") for d in eq.index],
                   "kalman": _series(eq["kalman"]), "static": _series(eq["static"]),
                   "sp500": _series(eq["sp500"])},
        "yearly": {str(k): float(v) for k, v in yearly.items()},
        "pairs": pair_rows,
    }
    if with_sensitivity:
        summary["sensitivity"] = sensitivity(prices, cfg)
        summary["cost_sensitivity"] = cost_sensitivity(prices, cfg)
    (out / "summary.json").write_text(json.dumps(_clean_dict(summary), indent=1))
    return summary


def report_markdown(s: dict) -> str:
    pct = lambda v: "n/a" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v*100:.1f}%"
    num = lambda v: "n/a" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v:.2f}"
    lines = [f"# Backtest results", "",
             f"Generated {s['generated_at']}. Data {s['data']['first_date']} to {s['data']['last_date']}; "
             f"all trading is out-of-sample from {s['out_of_sample_start']}.", "",
             "| Portfolio | CAGR | Volatility | Sharpe | Max drawdown |", "|---|---|---|---|---|"]
    names = {"kalman": "Spread engine (Kalman hedge)", "static": "Spread engine (static OLS hedge)",
             "buy_and_hold_sp500": "Buy & hold S&P 500 futures"}
    for k, label in names.items():
        p = s["portfolio"][k]
        lines.append(f"| {label} | {pct(p['cagr'])} | {pct(p['volatility'])} | {num(p['sharpe'])} | {pct(p['max_drawdown'])} |")
    lines += ["", f"Correlation of daily returns with the S&P 500: {num(s['correlation_with_sp500'])}", "",
              "| Pair | Eligible windows | Trades | Win rate | Sharpe (Kalman) | Sharpe (static) |",
              "|---|---|---|---|---|---|"]
    for p in s["pairs"]:
        k = p["kalman"]
        lines.append(f"| {p['label']} | {p['windows_eligible']}/{p['windows_total']} | {k.get('trades')} | "
                     f"{pct(k.get('win_rate'))} | {num(k['sharpe'])} | {num(p['static']['sharpe'])} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", default="data/prices.csv")
    ap.add_argument("--out", default="site/data")
    ap.add_argument("--report", default="results/RESULTS.md")
    ap.add_argument("--no-sensitivity", action="store_true")
    args = ap.parse_args()
    prices, rep = clean(load(args.prices))
    s = write_outputs(prices, rep, Config(), Path(args.out), not args.no_sensitivity)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(report_markdown(s))
    print(report_markdown(s))


if __name__ == "__main__":
    main()
