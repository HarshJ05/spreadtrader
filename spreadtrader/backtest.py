"""Walk-forward spread-trading backtest.

How one pair is traded
----------------------
1. Walk forward through time in blocks. For each block, look back over a
   *formation* window (default 2 years) and test whether the pair was
   cointegrated (Engle-Granger p < 0.05) with a sensible half-life. Only if it
   passes may the pair be traded in the next *trading* window (default 6 months).
   Every trade therefore happens on data the selection step never saw.
2. Turn the spread into a z-score:
     * "kalman": Kalman-filter prediction error divided by its predicted
       standard deviation (hedge ratio adapts every day);
     * "static": classic approach, OLS hedge ratio and mean/std frozen from the
       formation window.
3. Rules, decided at today's close and applied to tomorrow's return:
     * z < -entry  -> buy the spread  (long y, short beta * x)
     * z > +entry  -> sell the spread (short y, long beta * x)
     * exit when z comes back inside +/- exit, or
       stop out if |z| > stop, or after max_hold days, or when the pair stops
       being eligible.
   The hedge ratio is locked at entry, as a trader would do.
4. Each unit of position has gross notional 1, split between the legs in
   proportion 1 : |beta|. Costs are charged on every change in position.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

from .kalman import kalman_hedge
from .stats import engle_granger_pvalue, half_life, ols_hedge


@dataclass
class Config:
    formation_days: int = 504     # ~2 years of trading days
    trading_days: int = 126       # ~6 months
    max_pvalue: float = 0.05
    min_half_life: float = 1.0
    max_half_life: float = 60.0
    entry_z: float = 2.0
    exit_z: float = 0.5
    stop_z: float = 4.0
    max_hold_mult: float = 3.0    # time stop = max_hold_mult * half-life (days)
    cost_bps: float = 3.0         # cost per unit of gross notional traded, incl. slippage
    kalman_delta: float = 1e-3

    def to_dict(self):
        return asdict(self)


@dataclass
class Window:
    start: pd.Timestamp
    end: pd.Timestamp
    pvalue: float
    half_life: float
    eligible: bool
    a: float
    b: float
    mean: float
    std: float


@dataclass
class PairResult:
    method: str
    frame: pd.DataFrame                     # daily series
    trades: list = field(default_factory=list)
    windows: list = field(default_factory=list)


def formation_windows(ly: pd.Series, lx: pd.Series, cfg: Config) -> list[Window]:
    n = len(ly)
    out = []
    idx = ly.index
    for i in range(cfg.formation_days, n, cfg.trading_days):
        fy = ly.values[i - cfg.formation_days:i]
        fx = lx.values[i - cfg.formation_days:i]
        a, b = ols_hedge(fy, fx)
        resid = fy - a - b * fx
        p = engle_granger_pvalue(fy, fx)
        hl = half_life(resid)
        ok = (p < cfg.max_pvalue) and (cfg.min_half_life <= hl <= cfg.max_half_life)
        j = min(i + cfg.trading_days, n) - 1
        out.append(Window(idx[i], idx[j], p, hl, bool(ok), a, b,
                          float(resid.mean()), float(resid.std(ddof=1))))
    return out


def _signals(ly: pd.Series, lx: pd.Series, windows: list[Window], method: str,
             cfg: Config) -> pd.DataFrame:
    """Daily z-score, hedge ratio, and whether trading is allowed."""
    n = len(ly)
    df = pd.DataFrame(index=ly.index)
    df["tradable"] = False
    df["window_hl"] = np.nan
    for w in windows:
        m = (df.index >= w.start) & (df.index <= w.end)
        df.loc[m, "tradable"] = w.eligible
        df.loc[m, "window_hl"] = w.half_life

    if method == "kalman":
        first = windows[0] if windows else None
        f = cfg.formation_days
        a0, b0 = ols_hedge(ly.values[:f], lx.values[:f])
        resid0 = ly.values[:f] - a0 - b0 * lx.values[:f]
        k = kalman_hedge(ly.values, lx.values, delta=cfg.kalman_delta,
                         obs_var=float(np.var(resid0)), init_alpha=a0, init_beta=b0)
        df["beta"] = k.beta
        df["z"] = k.zscore
    elif method == "static":
        df["beta"] = np.nan
        df["z"] = np.nan
        for w in windows:
            m = (df.index >= w.start) & (df.index <= w.end)
            s = ly[m] - w.a - w.b * lx[m]
            df.loc[m, "beta"] = w.b
            df.loc[m, "z"] = (s - w.mean) / w.std
    else:
        raise ValueError(f"unknown method {method!r}")
    return df


def run_pair(py: pd.Series, px: pd.Series, cfg: Config = Config(),
             method: str = "kalman") -> PairResult:
    """Backtest one pair. py, px are positive prices on the same dates."""
    both = pd.concat([py, px], axis=1, keys=["y", "x"]).dropna()
    ly, lx = np.log(both["y"]), np.log(both["x"])
    ry = both["y"].pct_change().fillna(0.0).values
    rx = both["x"].pct_change().fillna(0.0).values

    windows = formation_windows(ly, lx, cfg)
    sig = _signals(ly, lx, windows, method, cfg)
    z = sig["z"].values
    beta = sig["beta"].values
    tradable = sig["tradable"].values
    hl = sig["window_hl"].values
    n = len(both)

    pos = np.zeros(n)          # position decided at close of day t
    hedge = np.zeros(n)        # beta locked for the open position
    reason = [""] * n
    cur, cur_b, held, cooldown = 0.0, 0.0, 0, False

    for t in range(n):
        zt = z[t]
        if cur != 0:
            held += 1
            max_hold = cfg.max_hold_mult * hl[t] if np.isfinite(hl[t]) else np.inf
            why = ""
            if not tradable[t] or np.isnan(zt):
                why = "window end"
            elif abs(zt) > cfg.stop_z:
                why = "stop"
                cooldown = True
            elif (cur > 0 and zt >= -cfg.exit_z) or (cur < 0 and zt <= cfg.exit_z):
                why = "reverted"
            elif held >= max_hold:
                why = "time"
            if why:
                cur, cur_b, held = 0.0, 0.0, 0
                reason[t] = why
        elif tradable[t] and not np.isnan(zt):
            if cooldown and abs(zt) < cfg.entry_z:
                cooldown = False
            if not cooldown and abs(zt) <= cfg.stop_z:
                if zt < -cfg.entry_z:
                    cur, cur_b, held = 1.0, beta[t], 0
                elif zt > cfg.entry_z:
                    cur, cur_b, held = -1.0, beta[t], 0
        pos[t], hedge[t] = cur, cur_b

    # Apply yesterday's decision to today's returns (no look-ahead).
    p_prev = np.concatenate([[0.0], pos[:-1]])
    b_prev = np.concatenate([[0.0], hedge[:-1]])
    gross = np.where(p_prev != 0, 1.0 + np.abs(b_prev), 1.0)
    gross_ret = p_prev * (ry - b_prev * rx) / gross
    turnover = np.abs(np.diff(np.concatenate([[0.0], pos])))
    cost = np.concatenate([[0.0], turnover[:-1]]) * cfg.cost_bps / 1e4
    net = gross_ret - cost

    frame = pd.DataFrame({
        "y": both["y"], "x": both["x"], "z": z, "beta": beta,
        "tradable": tradable, "position": pos, "net": net,
    }, index=both.index)
    trades = _trade_log(frame, reason)
    return PairResult(method, frame, trades, windows)


def _trade_log(frame: pd.DataFrame, reason: list[str]) -> list[dict]:
    pos = frame["position"].values
    net = frame["net"].values
    dates = frame.index
    trades, start, side = [], None, 0
    for t in range(len(pos)):
        prev = pos[t - 1] if t else 0.0
        if prev == 0 and pos[t] != 0:
            start, side = t, pos[t]
        elif prev != 0 and pos[t] == 0 and start is not None:
            # P&L accrues from the day after entry through the day after exit decision.
            end = min(t + 1, len(pos) - 1)
            pnl = float(np.prod(1 + net[start + 1:end + 1]) - 1)
            trades.append({"entry": str(dates[start].date()), "exit": str(dates[t].date()),
                           "side": "long spread" if side > 0 else "short spread",
                           "days": int(t - start), "return": pnl, "reason": reason[t]})
            start = None
    if start is not None:
        pnl = float(np.prod(1 + net[start + 1:]) - 1)
        trades.append({"entry": str(dates[start].date()), "exit": None,
                       "side": "long spread" if side > 0 else "short spread",
                       "days": int(len(pos) - 1 - start), "return": pnl, "reason": "open"})
    return trades
