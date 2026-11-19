# Backtest results

Generated 2026-11-19 14:31 UTC. Data 2010-01-04 to 2026-11-19; all trading is out-of-sample from 2012-01-03.

| Portfolio | CAGR | Volatility | Sharpe | Max drawdown |
|---|---|---|---|---|
| Spread engine (Kalman hedge) | 0.2% | 0.3% | 0.53 | -0.8% |
| Spread engine (static OLS hedge) | 0.0% | 0.4% | 0.08 | -1.6% |
| Buy & hold S&P 500 futures | 12.7% | 16.7% | 0.80 | -34.4% |

Correlation of daily returns with the S&P 500: 0.01

| Pair | Eligible windows | Trades | Win rate | Sharpe (Kalman) | Sharpe (static) |
|---|---|---|---|---|---|
| WTI crude oil vs Brent crude oil | 11/30 | 22 | 77.3% | 0.57 | 0.30 |
| Heating oil vs RBOB gasoline | 1/30 | 5 | 80.0% | 0.53 | -0.56 |
| Gold vs Silver | 1/30 | 2 | 0.0% | -0.35 | -0.22 |
| Gold vs Platinum | 2/30 | 8 | 87.5% | 0.73 | 0.03 |
| US 5-year Treasury note vs US 10-year Treasury note | 4/30 | 7 | 28.6% | 0.03 | -0.24 |
| US 2-year Treasury note vs US 5-year Treasury note | 5/30 | 11 | 27.3% | -0.65 | -0.51 |
| US 10-year Treasury note vs US 30-year Treasury bond | 3/30 | 6 | 50.0% | 0.10 | -0.25 |
| S&P 500 E-mini vs Dow Jones E-mini | 4/30 | 6 | 50.0% | 0.04 | 0.23 |
| S&P 500 E-mini vs Nasdaq-100 E-mini | 3/30 | 3 | 33.3% | -0.26 | -0.04 |
| Soybeans vs Soybean meal | 4/30 | 8 | 50.0% | -0.01 | -0.34 |
| Corn vs Wheat | 4/30 | 4 | 50.0% | -0.05 | 0.28 |

Signal sanity check (eligible days only): a z-score should have a standard deviation
near 1 and spend a few percent of days beyond the entry level.

| Pair | z std (Kalman) | days beyond entry (Kalman) | z std (static) | days beyond entry (static) |
|---|---|---|---|---|
| WTI crude oil vs Brent crude oil | 1.03 | 5.1% | 1.28 | 9.1% |
| Heating oil vs RBOB gasoline | 1.14 | 7.1% | 3.20 | 63.5% |
| Gold vs Silver | 1.31 | 15.9% | 1.41 | 73.8% |
| Gold vs Platinum | 1.31 | 9.9% | 2.35 | 45.6% |
| US 5-year Treasury note vs US 10-year Treasury note | 1.02 | 5.2% | 2.11 | 31.5% |
| US 2-year Treasury note vs US 5-year Treasury note | 1.42 | 12.2% | 3.41 | 47.5% |
| US 10-year Treasury note vs US 30-year Treasury bond | 1.08 | 6.9% | 1.29 | 44.2% |
| S&P 500 E-mini vs Dow Jones E-mini | 1.17 | 6.0% | 1.39 | 14.1% |
| S&P 500 E-mini vs Nasdaq-100 E-mini | 1.50 | 11.4% | 5.26 | 33.9% |
| Soybeans vs Soybean meal | 1.20 | 7.1% | 2.53 | 44.4% |
| Corn vs Wheat | 1.14 | 7.1% | 4.04 | 24.2% |
