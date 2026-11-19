"""Kalman filter that tracks a time-varying hedge ratio.

Model (both legs in log prices):

    y_t = alpha_t + beta_t * x_t + e_t,        e_t ~ N(0, Ve)     (observation)
    [alpha_t, beta_t] = [alpha_{t-1}, beta_{t-1}] + w_t,  w_t ~ N(0, Vw)   (random walk)

Each day the filter first *predicts* today's y from yesterday's alpha and beta,
then updates alpha and beta using today's price. The prediction error and its
variance are what the strategy trades on, so the signal for day t only ever uses
information up to day t.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class KalmanResult:
    alpha: np.ndarray       # alpha_{t|t-1}: intercept used to predict day t
    beta: np.ndarray        # beta_{t|t-1}: hedge ratio used to predict day t
    error: np.ndarray       # y_t - prediction (the spread "surprise")
    error_var: np.ndarray   # predicted variance of that error
    zscore: np.ndarray      # error / sqrt(error_var)


def kalman_hedge(y: np.ndarray, x: np.ndarray, delta: float = 1e-3,
                 obs_var: float = 1e-3, init_beta: float = 1.0,
                 init_alpha: float = 0.0) -> KalmanResult:
    """Run the filter over two aligned arrays of log prices.

    obs_var : variance of the spread around its fair value (Ve).
    delta   : how fast alpha and beta may drift, *relative to obs_var*.
              Each day alpha may move by about sqrt(delta * obs_var), and beta
              by the amount that moves y equally much. With delta = 1e-3 the
              fair value drifts about 3% of one spread standard deviation per
              day: slow enough that a stretched spread still shows up as a
              signal, fast enough to follow real changes in the relationship.
    """
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    n = len(y)
    if len(x) != n:
        raise ValueError("y and x must have the same length")

    x_scale = abs(x[~np.isnan(x)][0]) if np.any(~np.isnan(x)) else 1.0
    x_scale = max(x_scale, 1e-6)
    Vw = delta * obs_var * np.diag([1.0, 1.0 / x_scale ** 2])
    theta = np.array([init_alpha, init_beta], dtype=float)
    P = obs_var * np.diag([1.0, 1.0 / x_scale ** 2])   # starting uncertainty about theta

    alpha = np.full(n, np.nan)
    beta = np.full(n, np.nan)
    err = np.full(n, np.nan)
    evar = np.full(n, np.nan)

    for t in range(n):
        # Predict: theta follows a random walk, so uncertainty grows by Vw.
        R = P + Vw
        alpha[t], beta[t] = theta
        if np.isnan(y[t]) or np.isnan(x[t]):
            P = R                        # no observation today: carry forward
            continue
        F = np.array([1.0, x[t]])
        y_hat = F @ theta
        Q = F @ R @ F + obs_var          # variance of the prediction error
        e = y[t] - y_hat
        K = R @ F / Q                    # Kalman gain
        theta = theta + K * e
        P = R - np.outer(K, F) @ R
        err[t], evar[t] = e, Q

    z = err / np.sqrt(evar)
    return KalmanResult(alpha, beta, err, evar, z)
