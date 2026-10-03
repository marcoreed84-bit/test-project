"""
3-MA trend-alignment stack + RSI/Bollinger regime filter - inspired by the
top SHAP-important features in Parente & Rizzuti, "Trading strategy for
Bitcoin and Ethereum by neural network model" (Soft Computing, 2026): their
NN's three most important features were EMA crossover RATIOS across three
pairs simultaneously (EmaCross1_21, EmaCross21_50, EmaCross50_100), plus
Bollinger and RSI. That is a full TREND-ALIGNMENT stack across three MA
pairs at once, not a single crossover event - distinct from both MA
constructions already tried and failed on BTC in this project
(btc_ema_cross_resplit.py: one fast/slow pair; ma_bounce_respect_search.py:
single-MA touch/bounce). Their paper's own backtest can't be replicated
directly (it cross-sectionally trains on 400+ other coins we don't have
data for, and uses a 0.1%-fee/10%-stop/buy-only framework instead of real
spread) - this is a hand-coded version of the SAME predictive features,
tested honestly on our own data/cost/null pipeline instead of borrowing
their claimed ROI.

SIGNAL (long; short is the mirror), causal, no lookahead:
  * STACK ALIGNMENT: close > EMA(21) > EMA(50) > EMA(100) (full bullish
    stack) on bar i, and this alignment was NOT already true on bar i-1
    (fresh alignment, not mid-trend re-entry - avoids counting one trend
    as dozens of overlapping signals).
  * RSI(14) FILTER: RSI in RSI_BAND (healthy trend momentum, not already
    exhausted) - RSI_BAND in {(40,70), (30,80)}.
  * BOLLINGER FILTER (optional, BB_FILTER in {on, off} - tests whether this
    filter actually helps, since the source paper's own beeswarm plot
    describes a "counter-intuitive" Bollinger relationship, not a clean
    "stay inside the bands" rule): if on, requires close inside the
    Bollinger(20, 2.0) bands (not already overextended at the moment the
    stack aligns).
ENTRY: next bar's open + real spread. EXIT: STOP_ATR x ATR14 initial stop,
TARGET_R=2.5 fixed R-multiple target OR TRAIL_ATR chandelier trail
(TRAIL_ATR in {0 (fixed target only), 2.0}), max_hold=96 M15 bars (24h)
backstop. One position at a time (sim_signals).

GRID (K=16, literal): RSI_BAND in {(40,70),(30,80)} x BB_FILTER in
{off,on} x STOP_ATR in {1.5,3.0} x TRAIL_ATR in {0.0,2.0}.

Run on GOLD/SILVER/BTCUSD (this folder's standard cross-instrument
convention). Splits/cost/null: common.py.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

RSI_BANDS = [(40.0, 70.0), (30.0, 80.0)]
BB_FILTERS = [False, True]
STOP_ATRS = [1.5, 3.0]
TRAIL_ATRS = [0.0, 2.0]
TARGET_R = 2.5
MAX_HOLD = 96
BB_N, BB_DEV = 20, 2.0


def wilder_rsi(c, period=14):
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    n = len(c)
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)
    if n <= period:
        return np.full(n, np.nan)
    avg_gain[period] = gain[1:period + 1].mean()
    avg_loss[period] = loss[1:period + 1].mean()
    for i in range(period + 1, n):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period
    rs = np.where(avg_loss > 0, avg_gain / np.where(avg_loss > 0, avg_loss, np.nan), np.inf)
    return 100.0 - 100.0 / (1.0 + rs)


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    c, atr = b.close, b.atr

    ema21, ema50, ema100 = C.ema(c, 21), C.ema(c, 50), C.ema(c, 100)
    rsi = wilder_rsi(c, 14)
    mid, up, lo = C.bollinger(c, BB_N, BB_DEV)

    bull_now = (c > ema21) & (ema21 > ema50) & (ema50 > ema100)
    bear_now = (c < ema21) & (ema21 < ema50) & (ema50 < ema100)
    bull_prev = np.concatenate(([False], bull_now[:-1]))
    bear_prev = np.concatenate(([False], bear_now[:-1]))
    fresh_bull = bull_now & ~bull_prev
    fresh_bear = bear_now & ~bear_prev
    valid = ~np.isnan(atr) & (atr > 0) & ~np.isnan(ema100) & ~np.isnan(rsi) & ~np.isnan(mid)

    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        (rsi_lo, rsi_hi), bb_filter, stop_mult, trail = cfg
        rsi_ok_long = (rsi >= rsi_lo) & (rsi <= rsi_hi)
        rsi_ok_short = (rsi >= (100 - rsi_hi)) & (rsi <= (100 - rsi_lo))
        bb_ok = (c >= lo) & (c <= up) if bb_filter else np.ones(b.n, dtype=np.bool_)
        L = valid & fresh_bull & rsi_ok_long & bb_ok
        S = valid & fresh_bear & rsi_ok_short & bb_ok
        il = np.where(L)[0]
        is_ = np.where(S)[0]
        bars_ = np.concatenate((il, is_))
        dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        o = np.argsort(bars_, kind="stable")
        bars_, dirs = bars_[o].astype(np.int64), dirs[o]
        dist = stop_mult * atr[bars_]
        return bars_, dirs, dist

    def exit_fn(cfg):
        (rsi_lo, rsi_hi), bb_filter, stop_mult, trail = cfg
        target_r = 0.0 if trail > 0 else TARGET_R
        return dict(target_r=target_r, max_hold=MAX_HOLD, trail_atr=trail, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(RSI_BANDS, BB_FILTERS, STOP_ATRS, TRAIL_ATRS))
    return C.full_evaluation(b, f"{symbol} M15 -- 3-MA stack alignment (21/50/100) + RSI/Bollinger regime filter "
                                f"(RSI_BAND, BB_FILTER, STOP_ATR, TRAIL_ATR)", grid, signal_fn, exit_fn,
                             min_is_n=50, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/ma_stack_regime_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
