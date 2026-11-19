import numpy as np
import pandas as pd
import pytest

from spreadtrader.backtest import Config, run_pair
from spreadtrader.data import clean
from spreadtrader.kalman import kalman_hedge
from spreadtrader.metrics import max_drawdown, summarize
from spreadtrader.stats import engle_granger_pvalue, half_life, ols_hedge
from tests.synthetic import cointegrated_pair, random_walk


# ---- statistics -----------------------------------------------------------------

def test_ols_recovers_hedge_ratio():
    y, x = cointegrated_pair(beta=0.8)
    a, b = ols_hedge(np.log(y.values), np.log(x.values))
    assert b == pytest.approx(0.8, abs=0.05)


def test_cointegration_detects_real_pair_and_rejects_random_walks():
    y, x = cointegrated_pair()
    assert engle_granger_pvalue(np.log(y.values), np.log(x.values)) < 0.01
    a = np.log(random_walk(1500, seed=1))
    b = np.log(random_walk(1500, seed=2))
    assert engle_granger_pvalue(a, b) > 0.05


def test_half_life_matches_known_speed():
    rng = np.random.default_rng(0)
    kappa, s = 0.1, np.zeros(5000)
    for t in range(1, len(s)):
        s[t] = (1 - kappa) * s[t - 1] + rng.normal(0, 0.01)
    assert half_life(s) == pytest.approx(np.log(2) / kappa, rel=0.2)


def test_half_life_infinite_for_trending_series():
    assert half_life(np.arange(100, dtype=float) ** 1.5) == float("inf")


# ---- Kalman filter -----------------------------------------------------------------

def test_kalman_tracks_a_changing_hedge_ratio():
    rng = np.random.default_rng(3)
    n = 2000
    x = np.log(random_walk(n, seed=4))
    true_beta = np.where(np.arange(n) < n // 2, 0.5, 1.5)
    y = true_beta * x + rng.normal(0, 0.005, n)
    k = kalman_hedge(y, x, delta=1e-2, obs_var=0.005 ** 2, init_beta=0.5)
    # The hedge ratio moves up after the break...
    assert np.mean(k.beta[1800:2000]) > np.mean(k.beta[800:1000]) + 0.3
    # ...and the filter re-learns the relationship: prediction errors shrink
    # back to the size of the noise instead of staying huge.
    assert np.mean(np.abs(k.error[1800:2000])) < 3 * 0.005 * 4


def test_kalman_signal_uses_only_past_data():
    y, x = cointegrated_pair()
    ly, lx = np.log(y.values), np.log(x.values)
    full = kalman_hedge(ly, lx)
    cut = 700
    partial = kalman_hedge(ly[:cut], lx[:cut])
    np.testing.assert_allclose(full.zscore[:cut], partial.zscore, rtol=1e-12)
    np.testing.assert_allclose(full.beta[:cut], partial.beta, rtol=1e-12)


def test_kalman_zscore_is_roughly_standard_normal():
    y, x = cointegrated_pair(n=3000)
    ly, lx = np.log(y.values), np.log(x.values)
    a, b = ols_hedge(ly[:500], lx[:500])
    spread_var = np.var(ly[:500] - a - b * lx[:500])
    k = kalman_hedge(ly, lx, obs_var=spread_var, init_alpha=a, init_beta=b)
    z = k.zscore[500:]
    assert abs(np.nanmean(z)) < 0.2
    assert 0.6 < np.nanstd(z) < 1.6


# ---- backtest -----------------------------------------------------------------------

@pytest.mark.parametrize("method", ["kalman", "static"])
def test_strategy_makes_money_on_a_truly_mean_reverting_pair(method):
    y, x = cointegrated_pair(n=2000, seed=11)
    res = run_pair(y, x, Config(cost_bps=0.0), method)
    traded = res.frame[res.frame["position"] != 0]
    assert len(traded) > 0
    assert res.frame["net"].sum() > 0


def test_random_walks_are_rarely_eligible():
    a = pd.Series(random_walk(2000, seed=21), pd.bdate_range("2015-01-01", periods=2000))
    b = pd.Series(random_walk(2000, seed=22), a.index)
    res = run_pair(a, b, Config())
    eligible = sum(w.eligible for w in res.windows)
    assert eligible <= 2


def test_no_look_ahead_future_prices_do_not_change_past_positions():
    y, x = cointegrated_pair(n=2000, seed=5)
    base = run_pair(y, x, Config(), "kalman")
    y2, x2 = y.copy(), x.copy()
    y2.iloc[1500:] *= 1.5               # wreck the future
    shocked = run_pair(y2, x2, Config(), "kalman")
    cutoff = y.index[1500]
    windows_before = [w for w in base.windows if w.end < cutoff]
    last_safe = windows_before[-1].end
    np.testing.assert_array_equal(base.frame.loc[:last_safe, "position"].values,
                                  shocked.frame.loc[:last_safe, "position"].values)


def test_position_is_applied_to_next_day_return():
    y, x = cointegrated_pair(n=2000, seed=5)
    res = run_pair(y, x, Config(cost_bps=0.0), "kalman")
    f = res.frame
    first = int(np.argmax(f["position"].values != 0))
    assert f["net"].iloc[first] == 0.0      # entry day earns nothing yet
    assert f["position"].iloc[first] != 0


def test_costs_reduce_returns():
    y, x = cointegrated_pair(n=2000, seed=5)
    free = run_pair(y, x, Config(cost_bps=0.0)).frame["net"].sum()
    costly = run_pair(y, x, Config(cost_bps=20.0)).frame["net"].sum()
    assert costly < free


def test_only_trades_inside_eligible_windows():
    y, x = cointegrated_pair(n=2000, seed=5)
    f = run_pair(y, x, Config()).frame
    assert not ((f["position"] != 0) & (~f["tradable"])).any()


def test_trade_log_is_consistent():
    y, x = cointegrated_pair(n=2000, seed=5)
    res = run_pair(y, x, Config())
    assert res.trades
    for t in res.trades:
        assert t["side"] in ("long spread", "short spread")
        assert t["reason"] in ("reverted", "stop", "time", "window end", "open")
        assert t["days"] >= 1 or t["reason"] == "open"


# ---- data cleaning & metrics ------------------------------------------------------

def test_clean_drops_negative_oil_price():
    idx = pd.bdate_range("2020-04-16", periods=5)
    df = pd.DataFrame({"CL=F": [19.9, 18.3, -37.6, 10.0, 13.8], "BZ=F": [27.8, 28.1, 25.6, 19.3, 20.4]}, idx)
    out, rep = clean(df, max_gap=0)
    assert np.isnan(out.loc[idx[2], "CL=F"])
    assert rep["non_positive_removed"] == {"CL=F": 1}


def test_metrics_on_known_series():
    r = pd.Series([0.1, -0.5, 0.2])
    assert max_drawdown(r) == pytest.approx(-0.5)
    s = summarize(pd.Series([0.001] * 252))
    assert s["total_return"] == pytest.approx(1.001 ** 252 - 1)
    assert s["max_drawdown"] == 0.0


def test_summary_counts_trades_and_win_rate():
    trades = [{"exit": "x", "return": 0.02, "days": 3, "reason": "reverted"},
              {"exit": "x", "return": -0.01, "days": 5, "reason": "stop"},
              {"exit": None, "return": 0.0, "days": 1, "reason": "open"}]
    s = summarize(pd.Series([0.0, 0.01]), trades)
    assert s["trades"] == 2
    assert s["win_rate"] == 0.5
    assert s["exit_reasons"] == {"reverted": 1, "stop": 1}
