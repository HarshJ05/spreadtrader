"""Statistical tests used to decide whether a pair is worth trading."""
from __future__ import annotations

import numpy as np
from statsmodels.tsa.stattools import coint


def ols_hedge(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    """Least-squares fit y = a + b*x. Returns (a, b)."""
    X = np.column_stack([np.ones_like(x), x])
    a, b = np.linalg.lstsq(X, y, rcond=None)[0]
    return float(a), float(b)


def engle_granger_pvalue(y: np.ndarray, x: np.ndarray) -> float:
    """Engle-Granger cointegration test.

    Small p-value = the spread y - b*x looks stationary (it keeps returning to
    its average), which is what a spread trade needs.
    """
    return float(coint(y, x, trend="c", autolag="AIC")[1])


def half_life(spread: np.ndarray) -> float:
    """How many days the spread takes to close half of a gap to its mean.

    Fits the discrete Ornstein-Uhlenbeck form  d(s_t) = k * s_{t-1} + c + noise.
    Mean-reverting spreads have k < 0 and half-life = -ln(2) / k.
    """
    s = np.asarray(spread, dtype=float)
    s = s[~np.isnan(s)]
    lag, diff = s[:-1], np.diff(s)
    X = np.column_stack([np.ones_like(lag), lag])
    _, k = np.linalg.lstsq(X, diff, rcond=None)[0]
    if k >= 0:
        return float("inf")
    return float(-np.log(2) / k)
