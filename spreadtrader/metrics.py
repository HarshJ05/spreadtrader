"""Performance numbers a trading desk looks at."""
from __future__ import annotations

import numpy as np
import pandas as pd

DAYS = 252


def max_drawdown(returns: pd.Series) -> float:
    equity = (1 + returns.fillna(0)).cumprod()
    peak = equity.cummax()
    return float((equity / peak - 1).min())


def summarize(returns: pd.Series, trades: list[dict] | None = None,
              position: pd.Series | None = None) -> dict:
    r = returns.fillna(0.0)
    years = len(r) / DAYS if len(r) else np.nan
    total = float((1 + r).prod() - 1)
    cagr = float((1 + total) ** (1 / years) - 1) if years and total > -1 else np.nan
    vol = float(r.std(ddof=1) * np.sqrt(DAYS)) if len(r) > 1 else np.nan
    sharpe = float(r.mean() / r.std(ddof=1) * np.sqrt(DAYS)) if r.std(ddof=1) > 0 else np.nan
    mdd = max_drawdown(r)
    out = {
        "total_return": total,
        "cagr": cagr,
        "volatility": vol,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "calmar": float(cagr / abs(mdd)) if mdd < 0 else np.nan,
        "years": float(years),
    }
    if position is not None:
        out["time_in_market"] = float((position != 0).mean())
    if trades is not None:
        closed = [t for t in trades if t["exit"] is not None]
        out["trades"] = len(closed)
        out["win_rate"] = float(np.mean([t["return"] > 0 for t in closed])) if closed else np.nan
        out["avg_trade"] = float(np.mean([t["return"] for t in closed])) if closed else np.nan
        out["avg_days_held"] = float(np.mean([t["days"] for t in closed])) if closed else np.nan
        reasons = {}
        for t in closed:
            reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
        out["exit_reasons"] = reasons
    return out
