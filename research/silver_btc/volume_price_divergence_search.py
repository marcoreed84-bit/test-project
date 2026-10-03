"""
Volume/price DIVERGENCE on BTC - distinct from every volume construction
already tried in this project. bb_volume_breakout_search.py and
ma_stack_regime_search.py both used volume (or indicators) as a
CONFIRMATION filter (price breaks out AND volume agrees -> trade with the
breakout). This tests the opposite, classic technical-analysis claim:
price makes a new local extreme WITHOUT volume confirming it - a "weak
breakout," commonly read as an early reversal warning - i.e. volume
DISAGREEING with price, not agreeing.

SIGNAL (short; long is the mirror), causal, no lookahead:
  * close[i] is a new LOOKBACK-bar high (highest close in [i-LOOKBACK, i])
  * tick_volume[i] is BELOW its own VOL_MULT x rolling-mean of the prior
    20 bars (the breakout happened on weak participation)
  * direction = FADE the new extreme (short a weak new high, long a weak
    new low) - the reversal read, not continuation.
ENTRY: next bar's open + real spread. EXIT: STOP_ATR x ATR14 stop,
TARGET_R=2.0 fixed target, max_hold=96 M15 bars (24h) backstop, no trail.

GRID (K=12, literal): LOOKBACK in {20, 50} x VOL_MULT in {0.5, 0.7, 0.9}
(how weak the volume must be, as a fraction of its recent average) x
STOP_ATR in {1.5, 3.0}.

Run on GOLD/SILVER/BTCUSD (standard cross-instrument convention).
Splits/cost/null: common.py.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

LOOKBACKS = [20, 50]
VOL_MULTS = [0.5, 0.7, 0.9]
STOP_ATRS = [1.5, 3.0]
TARGET_R = 2.0
MAX_HOLD = 96


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    c, atr, vol = b.close, b.atr, b.vol

    vol_avg_prev = np.concatenate(([np.nan], pd.Series(vol).rolling(20, min_periods=20).mean().values[:-1]))
    vol_ratio = vol / np.where(vol_avg_prev > 0, vol_avg_prev, np.nan)

    hi_cache, lo_cache = {}, {}
    for lb in LOOKBACKS:
        roll_max_prev = pd.Series(c).rolling(lb, min_periods=lb).max().shift(1).values
        roll_min_prev = pd.Series(c).rolling(lb, min_periods=lb).min().shift(1).values
        hi_cache[lb] = c > roll_max_prev   # fresh new LOOKBACK-bar high on bar i (vs prior lb bars, excludes i)
        lo_cache[lb] = c < roll_min_prev

    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        lb, vol_mult, stop_mult = cfg
        new_hi = hi_cache[lb]
        new_lo = lo_cache[lb]
        weak_vol = vol_ratio < vol_mult
        valid = ~np.isnan(atr) & (atr > 0) & ~np.isnan(vol_ratio)
        S = valid & new_hi & weak_vol   # weak new high -> fade short
        L = valid & new_lo & weak_vol   # weak new low -> fade long
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

    grid = list(itertools.product(LOOKBACKS, VOL_MULTS, STOP_ATRS))
    return C.full_evaluation(b, f"{symbol} M15 -- volume/price divergence fade (LOOKBACK, VOL_MULT, STOP_ATR)",
                             grid, signal_fn, exit_fn, min_is_n=50, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/volume_price_divergence_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
