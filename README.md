# SpreadTrader: walk-forward spread trading on futures

[![tests](https://github.com/HarshJ05/spreadtrader/actions/workflows/tests.yml/badge.svg)](https://github.com/HarshJ05/spreadtrader/actions/workflows/tests.yml)
[![backtest](https://github.com/HarshJ05/spreadtrader/actions/workflows/backtest.yml/badge.svg)](https://github.com/HarshJ05/spreadtrader/actions/workflows/backtest.yml)

**Live dashboard:** https://harshj05.github.io/spreadtrader/

Instead of betting on whether oil or gold goes up, this engine trades the **gap between two related futures**:
WTI vs Brent crude, gold vs silver, 5-year vs 10-year Treasury notes, soybeans vs soybean meal and more. When a
gap stretches unusually far from normal, it bets the gap will close.

- **Pairs chosen for an economic reason**, not by searching for the best backtest (11 pairs, 18 futures).
- **Walk-forward selection:** every 6 months, an Engle-Granger cointegration test and a half-life estimate on the
  previous 2 years decide which pairs may trade. All trades are out-of-sample.
- **Kalman-filter hedge ratio** updated daily, compared with a classic static (OLS) hedge.
- **Realistic backtest:** decisions at today's close earn tomorrow's return, 3 bp costs, stop loss, time stop.
- **Robustness checks:** 9 entry/exit settings and 4 cost levels.
- **Self-updating:** a GitHub Action downloads fresh prices every week, re-runs everything and redeploys the
  dashboard.

## Results

Daily data from Jan 2010 to Nov 2026; trading out-of-sample from Jan 2012. Portfolio = equal capital in each pair.
Full table: [results/RESULTS.md](results/RESULTS.md) (regenerated weekly).

| Strategy | Sharpe | Annual return | Max drawdown | Correlation with S&P 500 |
|---|---|---|---|---|
| Spread engine, Kalman hedge | **0.53** | 0.2% | −0.8% | 0.01 |
| Spread engine, static OLS hedge | 0.08 | 0.0% | −1.6% | |
| Buy & hold S&P 500 futures | 0.80 | 12.7% | −34.4% | 1 |

- 82 trades, 56% winners. Best pairs: gold vs platinum (Sharpe 0.73), WTI vs Brent (0.57, 22 trades).
  Weakest: 2-year vs 5-year Treasuries (−0.65).
- Sharpe stays positive for all 9 entry/exit settings tested (0.05 to 0.68) and falls from 0.63 to 0.30 as costs
  rise from 0 to 10 bp.
- **Why the static hedge loses:** out of sample its z-score had a standard deviation of 2 to 5 instead of about 1.
  The hedge ratio and average measured over the previous two years went stale, so the spread looked stretched for
  weeks and the strategy held losing trades. The Kalman version stays calibrated.
- **What this does not show:** absolute returns are tiny because capital is idle about 97% of the time and there is
  no leverage. On Sharpe it does not beat holding the S&P 500; its value is that it is uncorrelated with it.

*Numbers above are from the run on 19 Nov 2026 and move slightly with each weekly update.*

## How it works

```
prices ──► log prices ──► every 6 months: cointegration test + half-life on previous 2 years
                                   │ pass?
                                   ▼
            Kalman filter: daily hedge ratio and fair value ──► spread ──► z-score vs trailing 6 months
                                   │
                                   ▼
        z < −2: buy spread · z > +2: sell spread · exit inside ±0.5 · stop at ±4 · time stop at 3 half-lives
                                   │
                                   ▼
               next-day returns − 3 bp costs ──► per-pair and portfolio metrics ──► dashboard
```

| File | Purpose |
|---|---|
| `spreadtrader/universe.py` | Futures and pairs, with the economic reason for each |
| `spreadtrader/data.py` | Download (Yahoo Finance) and cleaning |
| `spreadtrader/stats.py` | OLS hedge, Engle-Granger test, half-life |
| `spreadtrader/kalman.py` | Kalman filter for the time-varying hedge ratio |
| `spreadtrader/backtest.py` | Walk-forward windows, trading rules, costs, trade log |
| `spreadtrader/metrics.py` | Sharpe, drawdown, win rate, Calmar |
| `spreadtrader/run.py` | Runs the study and writes `site/data` |
| `site/index.html` | Dashboard (static, Plotly) |
| `GUIDE.md` | Plain-language explanation of every concept |

## Run it yourself

```bash
pip install -r requirements.txt yfinance pytest
python -m spreadtrader.data --start 2010-01-01          # downloads data/prices.csv
python -m spreadtrader.run                              # writes site/data and results/RESULTS.md
pytest -q                                               # 19 tests
python -m http.server -d site 8000                      # open http://localhost:8000
```

## Tests

19 tests on synthetic data where the right answer is known: the cointegration test accepts a truly
mean-reverting pair and rejects random walks, the half-life matches a known speed, the Kalman filter adapts after
a structural break, **future prices cannot change past positions**, trades only happen inside eligible windows,
costs reduce returns, and WTI's negative price on 20 April 2020 is removed.

## A bug found along the way

The first version scaled the Kalman spread by a size measured once in 2010–2011. Volatility changed later, so the
z-score almost never reached the entry level and most pairs made zero trades. A sanity check (standard deviation
of z should be near 1) exposed it; the spread is now scaled by its trailing 6-month size, still using past data
only. The trading rules and thresholds were not changed.

## Limitations

- Yahoo Finance continuous front-month prices jump on roll days; no back-adjustment.
- Daily closes only, and exchanges close at different times (e.g. Brent on ICE, WTI on CME).
- Notional sizing, no whole-contract rounding, no margin or leverage.
- One historical period. This is a research backtest, not trading advice.

## License

MIT
