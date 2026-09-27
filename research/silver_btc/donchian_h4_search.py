"""
Donchian channel breakout / time-series momentum on H4 - SILVER and BTCUSD.

WHY: every intraday construction in this folder and in research/aurelius/
dies on cost + noise at the M15/H1 scale. The single best-documented
anomaly in crypto (and a long-standing one in commodities) is SLOW
time-series momentum: trend-following on multi-day/multi-week horizons
(turtle-style channel breakouts). The prior BTC/Silver EMA-cross searches
topped out at SLOW=300 M15 bars (~3 days) - this probes the genuinely
slower horizon (entry channels of ~3 to ~20 trading days) where spread is a
small fraction of the typical move. Distinct mechanism from the EMA cross:
entry on a NEW N-bar extreme (price-level breakout), exit on an opposite
shorter-channel break (turtle exit), not on an MA re-cross.

SIGNAL: long when close[i] > highest high of bars i-N..i-1 (short mirror,
lowest low). EXIT: close beyond the opposite EXIT_N = N/2 channel (turtle
convention, fixed ratio - not tuned), plus an initial catastrophe stop of
STOP_ATR x ATR14(H4), max hold 1500 H4 bars (effectively unbounded). The
channel-exit arrays are precomputed from price alone, so random entries run
the identical exit.

TIMEFRAME: H4 resampled from real native M15 (lossless, common.resample).

GRID (declared before running, K = 8 per instrument):
  ENTRY_N in {20, 40, 80, 160} H4 bars x STOP_ATR in {3, 6}
Trade counts are necessarily small at this frequency: IS n floor is 30
(not 100 as for the intraday searches) - declared here, and it makes the
evidence weaker, not stronger; the random null handles that honestly since
it is calibrated to the same n.

Splits / cost / null / K: see common.py.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

ENTRY_NS = [20, 40, 80, 160]
STOP_ATRS = [3.0, 6.0]
MAX_HOLD = 1500


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    df = C.resample(df15, "4h")
    b = C.Bars(df, point, symbol)
    hh = {}; ll = {}
    for N in set(ENTRY_NS) | {n // 2 for n in ENTRY_NS}:
        hh[N] = pd.Series(b.high).rolling(N, min_periods=N).max().shift(1).values
        ll[N] = pd.Series(b.low).rolling(N, min_periods=N).min().shift(1).values

    def signal_fn(cfg):
        N, stop = cfg
        L = (b.close > hh[N]) & ~np.isnan(b.atr)
        S = (b.close < ll[N]) & ~np.isnan(b.atr)
        il = np.where(L)[0]; is_ = np.where(S)[0]
        bars_ = np.concatenate((il, is_)); dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        o = np.argsort(bars_, kind="stable")
        bars_, dirs = bars_[o].astype(np.int64), dirs[o]
        return bars_, dirs, stop * b.atr[bars_]

    def exit_fn(cfg):
        X = cfg[0] // 2
        ex_l = np.nan_to_num(b.close < ll[X], nan=0).astype(np.bool_)
        ex_s = np.nan_to_num(b.close > hh[X], nan=0).astype(np.bool_)
        return dict(target_r=0.0, max_hold=MAX_HOLD, trail_atr=0.0, exit_long=ex_l, exit_short=ex_s)

    grid = list(itertools.product(ENTRY_NS, STOP_ATRS))
    return C.full_evaluation(b, f"{symbol} H4 -- Donchian breakout, turtle N/2 exit (ENTRY_N, STOP_ATR)",
                             grid, signal_fn, exit_fn, min_is_n=30, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/donchian_h4_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
