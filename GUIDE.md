# SpreadTrader: the guide to explaining this project in an interview

This file explains every idea in the project in plain language, in the order
an interviewer is likely to ask about them. Read it top to bottom once, then
use the "Questions you will get" section to practise out loud.

---

## 1. The one-minute pitch

> "I built a spread trading engine for futures. Instead of betting on whether
> oil or gold goes up, it trades the *gap* between two related futures, like
> WTI vs Brent crude or 5-year vs 10-year Treasury notes. When the gap
> stretches unusually far from normal, it bets the gap will close.
>
> Every six months it re-tests which pairs are really tied together using a
> cointegration test, tracks the hedge ratio daily with a Kalman filter, and
> only trades on data the model has not seen. I backtested it on 11 futures
> pairs from 2010 with trading costs and compared it with a classic static
> hedge and with buying the S&P 500."

Then give the real numbers (from the run on 19 Nov 2026, data 2010 to Nov
2026, trading out-of-sample from 2012):

- **Sharpe 0.53** for the portfolio, after 3 bp costs, vs **0.08** with a
  static hedge. Buying and holding S&P 500 futures: 0.80.
- **Correlation with the S&P 500: 0.01**, so it is genuinely market-neutral.
- **Max drawdown −0.8%** (the S&P 500 fell 34% at its worst).
- **82 trades, 56% winners.** Best pairs: gold vs platinum (Sharpe 0.73) and
  WTI vs Brent (0.57, 22 trades, 77% winners). Worst: 2-year vs 5-year
  Treasuries (−0.65).
- Positive Sharpe for **all 9** entry/exit settings tried (0.05 to 0.68).

And **one honest weakness**: the returns are tiny in absolute terms (about
0.2% a year) because each pair holds 1/11 of the capital and is only in a
trade about 3% of the time, with no leverage. See section 10.

Numbers change slightly every week because the GitHub Action re-runs the study
with new data; check the dashboard before an interview.

---

## 2. Futures basics you must know

- **A futures contract** is an agreement to buy or sell something (oil, gold,
  a bond, a stock index) at a fixed price on a future date. Traders rarely hold
  them to delivery; they trade them for price moves.
- **Margin and leverage.** You only put down a small deposit (margin), so a
  small price move is a big gain or loss on your money. That is why risk
  control matters so much.
- **Long** = you profit if the price rises. **Short** = you profit if it falls.
- **Front month / roll.** The nearest contract is the "front month". Before it
  expires, traders "roll" into the next one. The free data used here glues
  front months together, so prices jump a little on roll days. (A known
  limitation; see section 9.)
- **Tick size.** The smallest price step. Trading costs are often measured in
  ticks.

## 3. What a spread trade is

A **spread** is the difference between two related prices. You buy one and
sell the other at the same time.

Example: WTI and Brent are both crude oil. If WTI suddenly gets very cheap
compared with Brent, you **buy WTI and sell Brent**. You do not care whether
oil as a whole goes up or down; you only care that the gap closes.

- **Long the spread** = buy the first leg (y), sell the second (x).
- **Short the spread** = sell y, buy x.
- Because you are long one and short the other, most of the market's moves
  cancel out. That is why the strategy should have **low correlation with the
  stock market** (the dashboard shows this number).

Desks call related trades by name: the **crack spread** (crude oil vs refined
products like heating oil and gasoline), the **crush spread** (soybeans vs
soybean meal and oil), **curve trades** (one Treasury maturity vs another).

## 4. Why the pairs were chosen in advance

The 11 pairs (in `spreadtrader/universe.py`) each have an economic reason to
move together: same commodity, one is made from the other, neighbouring points
on the yield curve, overlapping stock indices.

If you instead tried every possible pair and kept the ones with the best
backtest, you would find pairs that worked *by luck*. That is called **data
mining** or **overfitting**. Saying "I chose pairs before looking at results"
is a strong interview answer.

## 5. Cointegration: "do these two really move together?"

Two prices can both go up over time without being linked (ice cream sales and
shark attacks both rise in summer). **Correlation is not enough.**

**Cointegration** asks a stronger question: is there a combination
`y − beta × x` that keeps coming back to its average? If yes, the spread is
**mean-reverting** and tradeable.

- The **Engle-Granger test** fits `y = a + beta × x`, takes the leftover
  (the spread), and tests whether it is stationary (keeps returning to its
  mean). It gives a **p-value**.
- **p-value < 0.05** means "if these prices were *not* linked, a spread this
  well-behaved would happen less than 5% of the time by chance". Small = good.
- We work with **log prices**, so beta means "a 1% move in x matches a beta %
  move in y".

## 6. Half-life: "how fast does the gap close?"

The **half-life** is how many days the spread takes to close half of a gap.
It comes from fitting an Ornstein-Uhlenbeck (mean-reversion) model:

    change in spread today = k × (yesterday's spread) + noise
    half-life = −ln(2) / k            (k must be negative)

- Half-life of 5 days: gaps close fast, many short trades.
- Half-life of 200 days: too slow, your money is stuck and the link may break.
- The engine only trades pairs with a half-life between **1 and 60 days**, and
  closes any trade still open after **3 half-lives** (a "time stop").

## 7. The Kalman filter: a hedge ratio that updates every day

The relationship between two futures drifts over time (for example, after the
2014 oil crash or the 2022 rate hikes). A beta fixed two years ago goes stale.

A **Kalman filter** keeps a running best guess of the intercept and the hedge
ratio, and how unsure it is about them. Each day it:

1. **Predicts** today's y from today's x using yesterday's guess.
2. **Measures the error**: actual y minus predicted y.
3. **Updates** the guess a little, by how much it trusts the new data (the
   "Kalman gain").

The prediction error is the spread: how far y is from where the filter says it
should be. To turn it into a **z-score**, the engine compares today's spread
with its average and standard deviation over the **previous 6 months**. z = 2
means "two normal-sized moves away from fair value". Because the filter uses
yesterday's guess and the 6-month window ends yesterday, **the signal never
uses future data**.

**A bug worth talking about.** The first version measured the spread's normal
size once, in 2010–2011, and kept it fixed. Volatility changed later, so the
z-score almost never reached 2 and the Kalman version made **zero trades** on
most pairs. The sanity check now in the results (the standard deviation of z
should be near 1) caught it. Measuring the size over a trailing window fixed
it. This is a good story for "tell me about a mistake you found".

One setting matters: `delta`, how fast the hedge ratio is allowed to drift. Too
fast and the filter chases noise (the spread never looks stretched); too slow
and it is just a fixed hedge again.

## 8. The trading rules and the backtest

Decided at today's closing price and applied to **tomorrow's** return:

| Signal | Action |
|---|---|
| z < −2 | Buy the spread (it is unusually cheap) |
| z > +2 | Sell the spread (it is unusually expensive) |
| z back inside ±0.5 | Take profit, close |
| \|z\| > 4 | Stop loss: the relationship may have broken |
| held > 3 half-lives | Time stop |
| pair fails its next cointegration test | Close at the window end |

**Walk-forward testing.** Look back 2 years → decide which pairs to trade →
trade them for the next 6 months → move forward 6 months and repeat. Every
trade happens on data the selection step never saw. That is what
**out-of-sample** means.

**Costs.** 3 basis points (0.03%) of notional per trade, including slippage.
The dashboard shows what happens at 0, 6 and 10 bp too.

**Look-ahead bias** is the biggest backtest mistake: using information you
would not have had at the time (for example, today's close to decide a trade
at today's open). The project has tests that prove future prices cannot
change past positions (`tests/test_engine.py`).

## 9. The numbers on the dashboard

- **Annual return (CAGR):** average yearly growth.
- **Volatility:** how much returns swing, annualised.
- **Sharpe ratio:** return divided by volatility (×√252 for daily data). Return
  per unit of risk. Above 1 is good for a single strategy; above 2 is rare and
  should make you suspicious.
- **Max drawdown:** the worst fall from a peak to a low. What it would have
  felt like to hold the strategy at its worst.
- **Calmar ratio:** annual return ÷ max drawdown.
- **Win rate:** share of trades that made money. Mean-reversion strategies
  often win often but lose big on the few trades where the link breaks, which
  is why the stop loss exists.
- **Correlation with the S&P 500:** close to 0 means the strategy makes or loses
  money independently of the stock market.

Why returns look small: each pair gets 1/11 of the capital and sits in cash
when not trading, with no leverage. A real desk would use futures margin to
scale up. Sharpe does not change with leverage, so compare strategies by
Sharpe.

## 10. Honest limitations (say one of these before they ask)

0. **Small absolute returns.** Capital sits idle about 97% of the time and there
   is no leverage. A desk would size positions to a risk target and use margin;
   the Sharpe ratio is the fair comparison. It also does not beat simply
   holding the S&P 500 on Sharpe (0.53 vs 0.80); its value is that it is
   uncorrelated with it.

1. **Roll jumps.** Continuous front-month data jumps on roll days. Proper
   back-adjusted data from a paid source would fix it.
2. **Daily closes only.** Real spread traders work intraday and care about
   bid-ask spreads and queue position.
3. **Exchange hours differ.** Brent (ICE) and WTI (CME) "closes" are not at the
   same moment, which adds a little noise to the spread.
4. **Contract sizes ignored.** The backtest trades notional amounts; real
   trading uses whole contracts with fixed multipliers (e.g. 1,000 barrels for
   CL), so the hedge ratio has to be rounded.
5. **One set of thresholds.** The robustness table shows nearby settings, but
   it is still one study on one period.

## 11. Questions you will get, and short answers

**Why not just use correlation?** Two prices can be highly correlated in daily
moves and still drift apart forever. Cointegration checks that the *level* of
the gap returns to normal, which is what a spread trade needs.

**What if the relationship breaks?** Three defences: the stop loss at |z| > 4,
the time stop at 3 half-lives, and re-testing every 6 months so broken pairs
stop being traded.

**Kalman vs static hedge: which was better and why?** The Kalman version
(portfolio Sharpe 0.53 vs 0.08). The reason is visible in the sanity check: the
static hedge's z-score had a standard deviation of 2 to 5 out of sample
instead of about 1. Its hedge ratio and average were measured on the previous
2 years and went stale, so the spread looked "stretched" for weeks at a time
and the strategy held losing trades. The Kalman version keeps updating, so its
z-score stays near the right scale.

**How would you improve it?** Back-adjusted contract data, intraday data,
real contract sizes, a volatility-targeted position size, and testing more
pairs with a correction for testing many at once.

**What did the WTI negative price in April 2020 teach you?** The May 2020 WTI
contract settled at −$37.63 because storage at Cushing ran out and holders had
to pay to get rid of oil. Models built on log prices break there, so the data
cleaning step removes that day, and it is a reminder that futures are about
physical delivery, not just numbers.

**Quick maths they may throw at you:** if a spread has a half-life of 10 days,
how much of a gap is left after 20 days? A quarter (½ × ½). After 30? An eighth.

---

## Where things are in the code

| File | What it does |
|---|---|
| `spreadtrader/universe.py` | The 18 futures and 11 pairs, with the reason for each pair |
| `spreadtrader/data.py` | Downloads prices from Yahoo Finance, cleans them |
| `spreadtrader/stats.py` | OLS hedge ratio, Engle-Granger test, half-life |
| `spreadtrader/kalman.py` | Kalman filter for the daily hedge ratio and z-score |
| `spreadtrader/backtest.py` | Walk-forward windows, trading rules, costs, trade log |
| `spreadtrader/metrics.py` | Sharpe, drawdown, win rate and so on |
| `spreadtrader/run.py` | Runs everything and writes the dashboard data |
| `site/index.html` | The dashboard |
| `tests/` | Tests on synthetic data where the right answer is known |
| `.github/workflows/backtest.yml` | Weekly job: download data, re-run, publish |
