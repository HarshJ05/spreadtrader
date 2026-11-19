"""Synthetic prices with known properties, so tests can check the right answer."""
import numpy as np
import pandas as pd

from spreadtrader.universe import PAIRS, TICKERS


def random_walk(n, seed, vol=0.01, start=100.0):
    rng = np.random.default_rng(seed)
    return start * np.exp(np.cumsum(rng.normal(0, vol, n)))


def cointegrated_pair(n=1500, beta=0.8, kappa=0.1, noise=0.01, seed=0):
    """log y = 0.2 + beta * log x + s, where s mean-reverts (half-life ~ ln2/kappa)."""
    rng = np.random.default_rng(seed)
    lx = np.log(random_walk(n, seed + 1))
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = (1 - kappa) * s[t - 1] + rng.normal(0, noise)
    ly = 0.2 + beta * lx + s
    idx = pd.bdate_range("2015-01-01", periods=n)
    return pd.Series(np.exp(ly), idx), pd.Series(np.exp(lx), idx)


def universe_prices(n=1500):
    """Prices for every ticker; the first pair in PAIRS is cointegrated."""
    idx = pd.bdate_range("2015-01-01", periods=n)
    df = pd.DataFrame(index=idx)
    for i, t in enumerate(TICKERS):
        df[t] = random_walk(n, seed=100 + i)
    y, x = cointegrated_pair(n, seed=7)
    p = PAIRS[0]
    df[p.y], df[p.x] = y.values, x.values
    return df
