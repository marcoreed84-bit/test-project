"""
Volatility-regime (Bollinger width) + volume-confirmed breakout search on
SILVER and BTCUSD - a concrete, testable version of the web-sourced claim
that combining Bollinger Bands + volume + moving averages materially
improves risk-adjusted returns on Bitcoin. Never tried before in this
project (the only Bollinger use so far was gold-side VWAP-band work).

TIMEFRAME: H1, resampled losslessly from each instrument's own real native
M15 (common.resample - open=first/high=max/low=min/close=last/vol=sum/
spread=mean). H1 rather than M15 because (a) the published BB+volume BTC
work is on hourly/daily bars and (b) a 20-bar band on M15 is only 5 hours
of data, which is mostly intraday noise. Fixed up front, not searched.

SIGNAL (long; short is the mirror):
  * close[i] breaks ABOVE the upper Bollinger(20, 2.0) band on bar i (it was
    at/below the band on bar i-1) - textbook band settings, not tuned;
  * volatility regime: BB width (upper-lower)/mid on bar i is at or above
    its own rolling 500-bar percentile WPCT AND rising vs bar i-1
    (WPCT=0 -> filter off);
  * volume: tick_volume[i] > VOL_MULT x SMA20(tick_volume) of bars i-20..i-1
    (VOL_MULT=0 -> filter off). A RATIO to its own rolling mean, so the
    large level shifts in broker tick volume over the years (BTC tick volume
    median 226 in 2017, 1837 in 2023, 337 in 2026) do not matter;
  * MA trend: close > EMA(TREND) (TREND=0 -> filter off).
EXIT: initial stop STOP_ATR x ATR14(H1), then a chandelier trail at the
same multiple (trail from the best close since entry), max hold 240 H1 bars
(10 days). Self-contained, so random entries run the literal same exit.

GRID (declared before running, K = 36 per instrument):
  WPCT in {0, 50, 80} x VOL_MULT in {0, 1.5} x TREND in {0, 200}
  x STOP_ATR in {2, 3, 4}
The "all filters off" rows are included on purpose: they are the plain
band-breakout baseline, so the filters have to earn their place in the IS
selection rather than being assumed.

Splits / cost / null / K: see common.py. Point from CSV header (SILVER
0.001, BTC 0.01); resampled spread is the mean of the M15 spreads in the
hour, converted to price.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

WPCTS = [0, 50, 80]
VOL_MULTS = [0.0, 1.5]
TRENDS = [0, 200]
STOP_ATRS = [2.0, 3.0, 4.0]
BB_N, BB_DEV = 20, 2.0
WIDTH_LOOKBACK = 500
MAX_HOLD = 240


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    df = C.resample(df15, "1h")
    b = C.Bars(df, point, symbol)
    c = b.close
    mid, up, lo = C.bollinger(c, BB_N, BB_DEV)
    width = (up - lo) / mid
    wrank = pd.Series(width).rolling(WIDTH_LOOKBACK, min_periods=WIDTH_LOOKBACK).rank(pct=True).values * 100
    wprev = np.concatenate(([np.nan], width[:-1]))
    vavg_prev = np.concatenate(([np.nan], C.sma(b.vol, 20)[:-1]))
    vratio = b.vol / vavg_prev
    emas = {t: C.ema(c, t) for t in TRENDS if t}
    cprev = np.concatenate(([np.nan], c[:-1]))
    upprev = np.concatenate(([np.nan], up[:-1]))
    loprev = np.concatenate(([np.nan], lo[:-1]))
    brk_up = (c > up) & (cprev <= upprev)
    brk_dn = (c < lo) & (cprev >= loprev)
    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        wpct, vm, tr, stop = cfg
        okw = np.ones(b.n, bool) if wpct == 0 else ((wrank >= wpct) & (width > wprev))
        okv = np.ones(b.n, bool) if vm == 0 else (vratio > vm)
        if tr:
            okl = c > emas[tr]; oks = c < emas[tr]
        else:
            okl = oks = np.ones(b.n, bool)
        L = brk_up & okw & okv & okl
        S = brk_dn & okw & okv & oks
        L &= ~np.isnan(b.atr); S &= ~np.isnan(b.atr)
        il = np.where(L)[0]; is_ = np.where(S)[0]
        bars_ = np.concatenate((il, is_)); dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        o = np.argsort(bars_, kind="stable")
        bars_, dirs = bars_[o].astype(np.int64), dirs[o]
        dist = stop * b.atr[bars_]
        return bars_, dirs, dist

    def exit_fn(cfg):
        return dict(target_r=0.0, max_hold=MAX_HOLD, trail_atr=cfg[3], exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(WPCTS, VOL_MULTS, TRENDS, STOP_ATRS))
    return C.full_evaluation(b, f"{symbol} H1 -- Bollinger(20,2) breakout + width-regime + volume + EMA trend "
                                f"(WPCT, VOL_MULT, TREND, STOP_ATR)", grid, signal_fn, exit_fn,
                             min_is_n=100, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/bb_volume_breakout_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
