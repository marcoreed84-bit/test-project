"""
"Does price respect a moving average as dynamic support/resistance" -
tested directly, for the first time in this project. Distinct from the two
MA-based constructions already tried on BTC:
  - btc_ema_cross_resplit.py: a CROSSOVER signal (fast crosses slow), hold
    to reversal. DOES NOT SURVIVE.
  - Meridian (research/aurelius/meridian_silver_btc_output_2026-09-27.txt):
    the user's literal 21/50 EMA pair, but as a cross + VWAP + 250-period
    confirm filter, using FROZEN Gold-tuned parameters (never re-searched
    for BTC). Net loser on BTC (%PF=0.795), and even its marginal timing
    signal doesn't survive at its own honest K=15.

Neither of those tests whether price BOUNCES OFF a single MA line acting as
support/resistance - which is the actual "respects" claim. This script
does, across a real swept range of periods/types instead of assuming 21/50
specifically.

SIGNAL (long; short is the mirror):
  * bar i-1's close was at least APPROACH_ATR x ATR14 away from MA(PERIOD,
    TYPE) on one side (a genuine prior trend/approach, not chop sitting on
    the line) - this also guarantees bar i-1 itself wasn't already touching;
  * bar i's range [low, high] contains the MA line (an actual touch);
  * direction = continuation with the prior side (price was above and
    pulled back down to touch -> long on the bounce; mirror for short).
ENTRY: next bar's open + real spread. EXIT: STOP_ATR x ATR14 initial stop,
TARGET_R=2.0 fixed R-multiple target, max_hold=96 M15 bars (24h) backstop,
no trail - self-contained so random-timing entries reuse the identical
exit. One position at a time (repo convention via sim_signals).

GRID (K=24, literal, declared before running):
  MA_PERIOD in {20, 21, 50, 100, 150, 200} x MA_TYPE in {ema, sma}
  x STOP_ATR in {1.5, 3.0}
APPROACH_ATR fixed at 1.5 (not searched, to keep K honest and small).
21 and 50 are both literally in the period grid (the user's specific claim,
not excluded or substituted), tested with no special treatment vs the
other 4 periods.

Run on GOLD/SILVER/BTCUSD for cross-instrument context (same convention as
every other script in this folder) - if this construction only "works" on
BTC, that's meaningful; if it works identically on all three or none, that
also says something about whether it's a BTC-specific effect.

Splits / cost / null / K machinery: see common.py (BTC IS 2021-01-01 ->
2024-01-01, OOS 2024-01-01 -> end, avoiding the pre-2021 zero-spread/
expensive-regime era documented there).
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

MA_PERIODS = [20, 21, 50, 100, 150, 200]
MA_TYPES = ["ema", "sma"]
STOP_ATRS = [1.5, 3.0]
APPROACH_ATR = 1.5
TARGET_R = 2.0
MAX_HOLD = 96


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    c, atr = b.close, b.atr

    ma_cache = {}
    for period, mtype in itertools.product(MA_PERIODS, MA_TYPES):
        ma_cache[(period, mtype)] = C.ema(c, period) if mtype == "ema" else C.sma(c, period)

    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        period, mtype, stop_mult = cfg
        ma = ma_cache[(period, mtype)]
        valid = ~np.isnan(ma) & ~np.isnan(atr) & (atr > 0)
        dist_atr = np.where(valid, (c - ma) / np.where(atr > 0, atr, np.nan), np.nan)
        prior_dist = np.concatenate(([np.nan], dist_atr[:-1]))
        approach_long = prior_dist >= APPROACH_ATR
        approach_short = prior_dist <= -APPROACH_ATR
        touch = valid & (b.low <= ma) & (b.high >= ma)
        L = touch & approach_long
        S = touch & approach_short
        il = np.where(L)[0]
        is_ = np.where(S)[0]
        bars_ = np.concatenate((il, is_))
        dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        o = np.argsort(bars_, kind="stable")
        bars_, dirs = bars_[o].astype(np.int64), dirs[o]
        dist = stop_mult * atr[bars_]
        return bars_, dirs, dist

    def exit_fn(cfg):
        return dict(target_r=TARGET_R, max_hold=MAX_HOLD, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(MA_PERIODS, MA_TYPES, STOP_ATRS))
    return C.full_evaluation(b, f"{symbol} M15 -- MA bounce/respect (MA_PERIOD, MA_TYPE, STOP_ATR) "
                                f"[APPROACH_ATR={APPROACH_ATR} fixed, TARGET_R={TARGET_R} fixed]",
                             grid, signal_fn, exit_fn, min_is_n=100, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/ma_bounce_respect_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
