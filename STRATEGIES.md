# Trading Strategies — Detailed Reference

This document explains every strategy implemented in the backtesting engine, including the mathematical logic, parameters, entry/exit rules, and which instruments they work best with.

---

## 1. SMA Crossover (`sma_crossover`)

**Type:** Trend-following  
**Timeframe:** Daily  
**Best for:** Equities, Indices, ETFs, Commodities

### How It Works

Uses two Simple Moving Averages (SMA) of different periods. When the shorter-period SMA crosses above the longer-period SMA, it signals the start of an uptrend. When it crosses below, the trend has reversed.

### Math

```
SMA(period) = (P_1 + P_2 + ... + P_n) / n
```

Where `P_i` is the closing price on day `i` and `n` is the period length.

### Entry / Exit Rules

| Condition | Action |
|---|---|
| SMA(short) > SMA(long) | **BUY** (signal = 1) |
| SMA(short) < SMA(long) | **EXIT** (signal = 0) |

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `short_window` | 20 | Short SMA period (days) |
| `long_window` | 50 | Long SMA period (days) |

### Strengths & Weaknesses

- **Strengths:** Simple to understand, works well in strong trending markets, no overfitting risk.
- **Weaknesses:** Lags behind the market (reactive, not predictive). Generates frequent false signals (whipsaws) in range-bound/sideways markets. The longer the SMA periods, the fewer false signals but also the later the entries.

### Best Applied To

Large-cap equities (RELIANCE, TCS, HDFC Bank), broad indices (NIFTY 50, SENSEX), commodity futures (Gold, Crude Oil) where trends tend to persist.

---

## 2. Opening Range Breakout (`orb`)

**Type:** Intraday momentum  
**Timeframe:** Intraday (1m, 5m, 15m)  
**Best for:** Index Futures (Nifty, BankNifty), liquid Stock Futures

### How It Works

The first N minutes of trading (default: 15 minutes, i.e., 9:15 AM to 9:30 AM) establish the "opening range." The high and low of this period form a support/resistance channel. A breakout above the range signals bullish momentum; a breakdown below signals bearish momentum.

### Entry / Exit Rules

| Condition | Action |
|---|---|
| Close > ORB_High x (1 + buffer%) | **BUY** (signal = 1) |
| Close < ORB_Low x (1 - buffer%) | **SHORT** (signal = -1) |
| Time >= 15:15 (Square-off) | **EXIT** (signal = 0) |

**Constraint:** Only one trade per day. Once a signal fires, no reversals.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `orb_window_minutes` | 15 | Duration of the opening range (minutes from 9:15 AM) |
| `buffer_pct` | 0.001 | Buffer above/below the range to confirm breakout (0.1%) |
| `stop_pct` | 0.003 | Stop loss at opposite end of the range |
| `target_multiplier` | 1.0 | Target = range size x multiplier |

### How the Opening Range is Built

```
ORB_High = max(High) for all candles in [9:15, 9:30)
ORB_Low  = min(Low)  for all candles in [9:15, 9:30)
```

### Strengths & Weaknesses

- **Strengths:** Captures the first strong directional move of the day. Defined risk (stop at opposite end of range). Forced square-off prevents overnight risk.
- **Weaknesses:** Fails in low-volatility, choppy markets. The opening range can be artificially wide on gap-up/gap-down days, making the breakout threshold too distant. Requires intraday data (1m or 5m candles).

### Best Applied To

NIFTY Futures, BankNifty Futures, liquid stock futures (RELIANCE, TCS, SBIN). Not suitable for commodities or forex (different market hours).

---

## 3. Bollinger Band Mean Reversion (`bollinger_mean_reversion`)

**Type:** Mean reversion  
**Timeframe:** Daily or Intraday  
**Best for:** Range-bound equities, Indices, Forex (USDINR)

### How It Works

Bollinger Bands create an envelope around a moving average using standard deviations. When price touches the lower band AND RSI confirms oversold conditions, it's likely to revert to the mean. When price touches the upper band AND RSI confirms overbought, it's likely to fall back.

### Math

```
Middle Band = SMA(close, window)
Upper Band  = Middle + (num_std x StdDev(close, window))
Lower Band  = Middle - (num_std x StdDev(close, window))

RSI = 100 - (100 / (1 + RS))
RS  = Average Gain / Average Loss  (over rsi_period)
```

### Entry / Exit Rules

| Condition | Action |
|---|---|
| Close < Lower Band AND RSI < 30 | **BUY** (signal = 1) |
| Close > Upper Band AND RSI > 70 | **SHORT** (signal = -1) |
| Close crosses Middle Band (from long) | **EXIT long** (signal = 0) |
| Close crosses Middle Band (from short) | **EXIT short** (signal = 0) |

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `window` | 20 | Bollinger Band lookback period |
| `num_std` | 2.0 | Number of standard deviations for bands |
| `rsi_period` | 14 | RSI calculation period |
| `rsi_oversold` | 30 | RSI threshold for oversold (buy) |
| `rsi_overbought` | 70 | RSI threshold for overbought (sell) |

### Why RSI Confirmation Matters

Without RSI, a price touching the lower band in a strong downtrend (like a crash) would trigger a buy — which would be catastrophic. RSI < 30 confirms that selling pressure is exhausted and a bounce is likely, not just that the price has fallen.

### Strengths & Weaknesses

- **Strengths:** Works well in range-bound markets. Dual confirmation (price + RSI) reduces false signals. Clear exit (middle band).
- **Weaknesses:** Fails in trending markets where price "walks the bands." Can generate long periods with no signals in trending conditions.

### Best Applied To

Large-cap equities in consolidation phases, USDINR (tends to mean-revert), Bank NIFTY during non-event weeks.

---

## 4. VWAP Mean Reversion (`vwap_mean_reversion`)

**Type:** Intraday mean reversion  
**Timeframe:** Intraday (1m, 5m, 15m)  
**Best for:** Stock Futures, Index Futures

### How It Works

Volume Weighted Average Price (VWAP) represents the "fair price" of the day. Institutional algorithms benchmark against VWAP, so price tends to revert to it. When price deviates significantly below VWAP with a volume spike, it's a buying opportunity. The opposite signals a short.

### Math

```
VWAP = Cumulative(Typical_Price x Volume) / Cumulative(Volume)
Typical_Price = (High + Low + Close) / 3

Standard Deviation = sqrt(variance of intraday closes)

Upper Bound = VWAP + (multiplier x StdDev)
Lower Bound = VWAP - (multiplier x StdDev)
```

### Entry / Exit Rules

| Condition | Action |
|---|---|
| Close < Lower Bound AND Volume > avg_volume x 1.2 | **BUY** |
| Close > Upper Bound AND Volume > avg_volume x 1.2 | **SHORT** |
| Close returns to VWAP (from long) | **EXIT long** |
| Close returns to VWAP (from short) | **EXIT short** |

**Important:** VWAP resets every day at 9:15 AM. Positions also reset daily.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `vwap_std_multiplier` | 1.5 | How many standard deviations from VWAP to trigger entry |
| `min_volume_ratio` | 1.2 | Minimum volume spike ratio vs. average |

### Why Volume Confirmation Matters

A price deviation from VWAP without volume is noise. A deviation WITH a volume spike means a large participant (institutional order) pushed the price, and the market is likely to absorb and revert.

### Strengths & Weaknesses

- **Strengths:** Institutional-grade signal. Very effective for liquid instruments. Clear target (VWAP).
- **Weaknesses:** Only works intraday (VWAP resets daily). Requires volume data. Less effective for illiquid stocks.

### Best Applied To

NIFTY Futures, BankNifty Futures, top F&O stocks (RELIANCE, SBIN, ICICIBANK).

---

## 5. Cross-Sectional Momentum (`cross_sectional_momentum`)

**Type:** Multi-stock momentum / factor-based  
**Timeframe:** Daily (rebalances every 21 days)  
**Best for:** Portfolio of NIFTY 50 or NIFTY 500 stocks

### How It Works

Ranks all stocks in a universe by their past 6-month return (excluding the most recent month to avoid short-term reversal). Goes long the top 20% performers and short the bottom 20%. Rebalances every 21 trading days.

### Math

```
Momentum(stock) = (Price[t - skip_days] / Price[t - lookback_days]) - 1

Skip last 21 days to avoid short-term reversal effect.
Rank all stocks by momentum score.
Long top 20%, Short bottom 20%.
```

### Entry / Exit Rules

| Condition | Action |
|---|---|
| Stock in top 20% by momentum | **LONG** (signal = 1) |
| Stock in bottom 20% by momentum | **SHORT** (signal = -1) |
| Stock in middle 60% | **FLAT** (signal = 0) |
| Every 21 days | **REBALANCE** |

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `lookback_days` | 126 | Momentum lookback (6 months) |
| `skip_days` | 21 | Skip recent month (reversal avoidance) |
| `top_percentile` | 0.2 | % of stocks to go long (20%) |
| `bottom_percentile` | 0.2 | % of stocks to go short (20%) |
| `rebalance_frequency` | 21 | Rebalance every N trading days |

### Why Skip the Last Month?

Academic research (Jegadeesh & Titman, 1993) shows that stocks exhibit short-term reversal (1-month) but intermediate-term momentum (3-12 months). Skipping the most recent month avoids buying into short-term overbought conditions.

### Strengths & Weaknesses

- **Strengths:** Well-documented academic factor. Market-neutral (long + short). Diversified across many stocks. Low turnover (monthly rebalance).
- **Weaknesses:** Requires a large stock universe (10+ stocks minimum). Momentum crashes during market regime changes (e.g., COVID crash). Short selling constraints in Indian markets for retail traders.

### Best Applied To

NIFTY 50 universe, NIFTY 500 universe. Not applicable to single instruments.

---

## 6. Pairs Trading (`pairs_trading`)

**Type:** Statistical arbitrage  
**Timeframe:** Daily  
**Best for:** Correlated stock pairs (e.g., SBIN/ICICIBANK, TATASTEEL/JSWSTEEL)

### How It Works

Finds two stocks that move together (cointegrated). Calculates the "spread" between them using a hedge ratio. When the spread deviates too far from its mean, it's expected to revert. Enter at extreme deviations, exit when spread returns to normal.

### Math

```
Step 1: OLS Regression over formation_window
    Stock_A = alpha + beta x Stock_B + epsilon
    beta = Cov(A, B) / Var(B)

Step 2: Spread = Stock_A - beta x Stock_B

Step 3: Z-Score = (Current_Spread - Mean_Spread) / StdDev_Spread

Step 4: Simplified ADF test for cointegration
    diff(spread) = rho x lag(spread) + noise
    t-statistic = rho / SE(rho)
    Cointegrated if: rho < 0 AND t-stat < -2.86
```

### Entry / Exit Rules

| Condition | Action |
|---|---|
| Z-score > +2.0 (spread too wide) | **SHORT A, LONG B** |
| Z-score < -2.0 (spread too narrow) | **LONG A, SHORT B** |
| |Z-score| < 0.5 | **EXIT** (mean reversion achieved) |
| |Z-score| > 3.0 | **STOP LOSS** (cointegration may have broken) |

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `formation_window` | 252 | Lookback for hedge ratio estimation (1 year) |
| `entry_z` | 2.0 | Z-score threshold to enter |
| `exit_z` | 0.5 | Z-score threshold to exit |
| `stop_z` | 3.0 | Z-score threshold for stop loss |

### Strengths & Weaknesses

- **Strengths:** Market-neutral (hedged against market direction). Profits from mean reversion of the spread, not from market direction. Statistically grounded.
- **Weaknesses:** Cointegration can break permanently (structural change). Requires constant monitoring and re-estimation. Hard to find truly cointegrated pairs. Needs simultaneous long + short execution.

### Best Applied To

Indian banking pairs (SBIN/ICICIBANK, HDFCBANK/KOTAKBANK), steel pairs (TATASTEEL/JSWSTEEL), IT pairs (TCS/INFY), auto pairs (MARUTI/M&M).

---

## 7. RSI Divergence (`rsi_divergence`)

**Type:** Reversal detection  
**Timeframe:** Daily  
**Best for:** Equities, Indices

### How It Works

Detects divergences between price action and the RSI indicator. When price makes a new low but RSI makes a higher low, selling momentum is weakening — a bullish reversal is likely. The opposite (price higher high, RSI lower high) signals a bearish reversal.

### Math

```
RSI = 100 - (100 / (1 + RS))
RS = EMA(gains, period) / EMA(losses, period)

Bullish Divergence:
    Price: lower low (P[idx2] < P[idx1])
    RSI:   higher low (RSI[idx2] > RSI[idx1])

Bearish Divergence:
    Price: higher high (P[idx2] > P[idx1])
    RSI:   lower high (RSI[idx2] < RSI[idx1])
```

### Detection Algorithm

1. Scan a 20-bar lookback window
2. Find local minima (for bullish) and maxima (for bearish) in price
3. Compare the two most recent minima/maxima in price and RSI
4. If they diverge, generate a signal

### Entry / Exit Rules

| Condition | Action |
|---|---|
| Bullish divergence detected | **BUY** (signal = 1) |
| Bearish divergence detected | **SHORT** (signal = -1) |

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `rsi_period` | 14 | RSI calculation period |
| `lookback` | 20 | Window to search for divergence patterns |

### Strengths & Weaknesses

- **Strengths:** Catches reversals before they happen. Works at major turning points (market tops/bottoms). Combines price structure with momentum.
- **Weaknesses:** Divergences can persist for a long time before resolving. In strong trends, divergence signals can be premature (fighting the trend). Requires discretion on which divergences to act on.

### Best Applied To

NIFTY 50 index, large-cap stocks at support/resistance levels, Bank NIFTY. Less effective on volatile mid/small-caps.

---

## 8. Gap Fill (`gap_fill`)

**Type:** Intraday reversal  
**Timeframe:** Daily  
**Best for:** Liquid equities, Index futures

### How It Works

When a stock opens significantly higher or lower than the previous day's close (a "gap"), the gap tends to fill — meaning the price reverts back toward the previous close. This strategy fades the gap by taking the opposite position.

### Math

```
Gap Up:   Open > Previous_Close x (1 + min_gap_pct)
          AND Open < Previous_Close x (1 + max_gap_pct)

Gap Down: Open < Previous_Close x (1 - min_gap_pct)
          AND Open > Previous_Close x (1 - max_gap_pct)
```

### Entry / Exit Rules

| Condition | Action |
|---|---|
| Gap Up (0.3% to 2%) | **SHORT** (signal = -1) — expecting gap fill |
| Gap Down (0.3% to 2%) | **LONG** (signal = 1) — expecting gap fill |
| No significant gap | **FLAT** (signal = 0) |
| Held for 1 day | **EXIT** (reset next day) |

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `min_gap_pct` | 0.003 | Minimum gap size to trigger (0.3%) |
| `max_gap_pct` | 0.02 | Maximum gap size (2%) — gaps beyond this may not fill |

### Why Max Gap Matters

Very large gaps (>2%) are often caused by fundamental news (earnings, corporate actions) and are less likely to fill. These are "breakaway gaps" and should be respected, not faded.

### Strengths & Weaknesses

- **Strengths:** High win rate (gaps fill ~70% of the time for small gaps). Simple, mechanical rules. Short holding period (1 day).
- **Weaknesses:** When gaps don't fill, losses can be large (risk/reward asymmetry). Requires screening for fundamental catalysts. Works better on indices than individual stocks.

### Best Applied To

NIFTY 50 index, BankNifty, large-cap stocks (RELIANCE, HDFCBANK, TCS). Avoid using on stocks with pending results or corporate actions.

---

## 9. Donchian Breakout (`donchian_breakout`)

**Type:** Trend-following breakout  
**Timeframe:** Daily  
**Best for:** Commodities (Gold, Crude Oil), Indices, Forex (USDINR)

### How It Works

The Donchian Channel is formed by the highest high and lowest low over a lookback period. A close above the upper channel signals a new uptrend; a close below the lower channel signals a new downtrend. This is the strategy used by the famous "Turtle Traders."

### Math

```
Upper Channel = max(High[i-window : i])  — highest high of last N days
Lower Channel = min(Low[i-window : i])   — lowest low of last N days
```

### Entry / Exit Rules

| Condition | Action |
|---|---|
| Close > Upper Channel | **BUY** (signal = 1) |
| Close < Lower Channel | **SHORT** (signal = -1) |

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `window` | 20 | Lookback period for channel (20 days = Turtle system) |

### Strengths & Weaknesses

- **Strengths:** Captures major trends. Very simple and mechanical. Historically profitable in trending markets (commodities, forex). No curve fitting.
- **Weaknesses:** High drawdowns during sideways markets. Many false breakouts. Late entry (waits for new highs/lows).

### Best Applied To

MCX Gold, MCX Crude Oil, USDINR, NIFTY 50 on longer timeframes. The original Turtle system used 20-day and 55-day channels.

---

## 10. BankNifty Short Straddle (`straddle`)

**Type:** Options selling / theta decay  
**Timeframe:** Weekly (Thursday expiry)  
**Best for:** BankNifty index options

### How It Works

Sells an ATM (at-the-money) Call and ATM Put on BankNifty every weekly expiry day (Thursday). Profits from theta (time) decay if BankNifty stays near the strike price. Skips high-risk days (RBI policy, elections, budget) and high-VIX environments.

### Math (Black Model for Index Options)

```
Call = e^(-rT) x [F x N(d1) - K x N(d2)]
Put  = e^(-rT) x [K x N(-d2) - F x N(-d1)]

d1 = [ln(F/K) + 0.5 x sigma^2 x T] / (sigma x sqrt(T))
d2 = d1 - sigma x sqrt(T)

Where:
  F     = Futures price (NOT spot — important for NSE index options)
  K     = Strike price (ATM, rounded to nearest 100)
  T     = Time to expiry in years
  r     = Risk-free rate (91-day T-Bill, ~6.5%)
  sigma = Implied volatility (from India VIX / 100)
```

### Entry / Exit Rules

| Condition | Action |
|---|---|
| Thursday (expiry day), 9:20 AM, VIX < 18, not high-risk day | **SELL ATM Call + ATM Put** |
| 2:45 PM or premium loss > 100% | **EXIT** (buy back both legs) |

### Risk Filters

- **VIX Filter:** Skip if India VIX > 18 (high volatility = high risk for sellers)
- **High-Risk Days:** Skip RBI monetary policy days, Union Budget, election results
- **Max Loss:** Exit if combined premium loss exceeds 100% of collected premium

### Greeks Calculated

| Greek | Meaning |
|---|---|
| Delta | Price sensitivity (near 0 for ATM straddle) |
| Gamma | Delta's rate of change (highest ATM — this is the risk) |
| Theta | Daily time decay (this is the profit source) |
| Vega | Volatility sensitivity (short vega = profits when IV drops) |

### Strengths & Weaknesses

- **Strengths:** High win rate (~60-70% of weeks are low-volatility). Theta works in your favor every second. Well-defined weekly cycle.
- **Weaknesses:** Unlimited risk on both sides. A single large move (>2%) can wipe out weeks of profits. Gamma risk is highest on expiry day. Requires margin (~Rs 1.5-2L per lot).

### Best Applied To

BankNifty weekly options. Can also be adapted for NIFTY weekly options (lot size 25).

---

## 11. Iron Condor (available in options engine)

**Type:** Defined-risk options selling  
**Timeframe:** Weekly  
**Best for:** BankNifty, NIFTY options

### How It Works

Like a short straddle but with protection. Sells OTM Call + OTM Put (short strangle) and buys further OTM Call + Put as wings. Maximum profit is the net premium collected. Maximum loss is the wing width minus premium.

```
Sell Call @ K1, Buy Call @ K2 (K2 > K1)  — Bear Call Spread
Sell Put  @ K3, Buy Put  @ K4 (K4 < K3)  — Bull Put Spread

Max Profit = Net Premium Collected
Max Loss   = (K2 - K1) - Net Premium  (per lot)
```

### Best Applied To

BankNifty options in low-VIX weeks (VIX < 15).

---

## 12. Long Straddle (available in options engine)

**Type:** Volatility buying / event play  
**Timeframe:** Event-driven  
**Best for:** Before RBI policy, Union Budget, election results

### How It Works

Buys ATM Call + ATM Put. Profits if BankNifty/NIFTY moves significantly in either direction. Loses money from theta decay if the market stays flat.

```
Max Loss = Total Premium Paid
Breakeven = Strike +/- Total Premium
Profit = Unlimited (on either side)
```

### Best Applied To

Enter 1-2 days before major events. Exit immediately after the event move. Best when IV is low before the event and expected to spike.

---

## Strategy Selection Guide

| Market Condition | Best Strategy | Avoid |
|---|---|---|
| Strong uptrend | SMA Crossover, Donchian Breakout | Bollinger Mean Reversion |
| Strong downtrend | SMA Crossover (short), Donchian | Gap Fill |
| Sideways / range-bound | Bollinger Mean Reversion, VWAP | SMA Crossover, Donchian |
| High volatility (VIX > 20) | Long Straddle, Donchian | Short Straddle, Iron Condor |
| Low volatility (VIX < 15) | Short Straddle, Iron Condor | Long Straddle |
| Intraday | ORB, VWAP Mean Reversion | Cross-Sectional Momentum |
| Multi-stock portfolio | Cross-Sectional Momentum | ORB, VWAP |
| Correlated pairs | Pairs Trading | Single-stock strategies |
| Pre-event (RBI, Budget) | Long Straddle | Short Straddle |
| Commodity trending | Donchian Breakout, SMA Crossover | Mean reversion |

---

## Instrument-Strategy Compatibility Matrix

| Strategy | NSE Equity | Index F&O | MCX Commodities | Forex (CDS) | ETFs | Mutual Funds |
|---|---|---|---|---|---|---|
| SMA Crossover | Yes | Yes | Yes | Yes | Yes | No |
| ORB | Intraday only | Yes | No | No | No | No |
| Bollinger Mean Reversion | Yes | Yes | Yes | Yes | Yes | No |
| VWAP Mean Reversion | Intraday only | Yes | No | No | No | No |
| Cross-Sectional Momentum | Yes (portfolio) | No | No | No | No | No |
| Pairs Trading | Yes (2 stocks) | No | No | No | No | No |
| RSI Divergence | Yes | Yes | Yes | Yes | Yes | No |
| Gap Fill | Yes | Yes | No | No | No | No |
| Donchian Breakout | Yes | Yes | Yes | Yes | Yes | No |
| Short Straddle | No | BankNifty/Nifty | No | No | No | No |
| Iron Condor | No | BankNifty/Nifty | No | No | No | No |
| Long Straddle | No | BankNifty/Nifty | No | No | No | No |

> **Note:** Mutual funds are NAV-based (single daily price) and don't generate intraday signals. They're included for performance comparison benchmarking only.
