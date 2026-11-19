"""Download and clean daily futures prices.

Downloading needs internet access to Yahoo Finance; the GitHub Action in
.github/workflows/backtest.yml does it. Everything else works from the saved CSV.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .universe import TICKERS

DEFAULT_PATH = Path("data/prices.csv")


def download(tickers=TICKERS, start="2010-01-01", end=None) -> pd.DataFrame:
    import yfinance as yf  # only needed for downloading

    raw = yf.download(list(tickers), start=start, end=end, auto_adjust=False,
                      progress=False, group_by="column", threads=True)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close.index.name = "date"
    return close.sort_index()


def clean(prices: pd.DataFrame, max_gap: int = 3) -> tuple[pd.DataFrame, dict]:
    """Make prices safe for log-price modelling and report what was changed.

    * Non-positive prices are removed. WTI crude settled at -$37.63 on
      20 April 2020; a log price does not exist there, so that day is dropped.
    * Short gaps (holidays on one exchange only) are forward-filled, at most
      `max_gap` days, so both legs of a pair share the same dates.
    """
    report = {}
    p = prices.copy().astype(float)
    nonpos = (p <= 0).sum()
    report["non_positive_removed"] = {k: int(v) for k, v in nonpos.items() if v}
    p = p.where(p > 0)
    if max_gap > 0:
        p = p.ffill(limit=max_gap)
    report["rows"] = int(len(p))
    report["first_date"] = str(p.index.min().date()) if len(p) else None
    report["last_date"] = str(p.index.max().date()) if len(p) else None
    return p, report


def load(path: Path | str = DEFAULT_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index.name = "date"
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description="Download daily futures prices from Yahoo Finance")
    ap.add_argument("--start", default="2010-01-01")
    ap.add_argument("--out", default=str(DEFAULT_PATH))
    args = ap.parse_args()
    prices = download(start=args.start)
    missing = [t for t in TICKERS if t not in prices.columns or prices[t].notna().sum() == 0]
    if missing:
        raise SystemExit(f"No data returned for: {missing}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(args.out, float_format="%.6f")
    print(f"Saved {prices.shape[0]} rows x {prices.shape[1]} tickers to {args.out}")
    print(prices.notna().sum().to_string())


if __name__ == "__main__":
    main()
