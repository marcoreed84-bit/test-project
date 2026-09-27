"""
Plain horizontal support/resistance bounce (mean reversion), on SILVER and
BTCUSD M15 - the one genuinely untested idea out of the user's pasted list
of generic silver-strategy write-ups. Distinct from everything tried so
far in this folder: every earlier construction was either a continuation/
breakout (trendline, EMA cross, Bollinger breakout, opening-range, Donchian,
liquidity-sweep+BOS) or a reversal FROM AN OSCILLATOR EXTREME (Stochastic
cross, Bollinger climax-volume fade) - this is "price returns to a level
that mattered before and bounces off it", the plainest textbook S/R trade,
which RoundingBottom/Rectangle (specific CHART PATTERNS built around S/R,
tested on gold earlier this session and already rejected there) never
actually tested in this bare form.

CONSTRUCTION (long; short is the mirror):
  * support[i] = the most recently CONFIRMED N-bar fractal pivot low
    (common.pivots() - already causal/no-lookahead), forward-filled;
    resistance[i] = same for pivot highs.
  * touch: rolling-5-bar min of (low - support) <= TOL x ATR (price dipped
    into the zone recently) - the same "touched recently" construction
    already used and reviewed for Aurelius/H&S pullback logic.
  * bounce trigger (edge, fires once): close now sits back above
    support + TOL x ATR (rejected the level on the close).
  * stop = support - 0.25 x ATR (fixed buffer, not tuned - same convention
    as the ADX-pullback script's STOP_BUF_ATR); target = TARGET_R x that
    same distance (fixed R-multiple, matching the user's own "target
    minimum 1:2 risk-reward" framing - 1.5/2.0/3.0 are all tried); max
    hold 80 M15 bars (~20h) since a mean-reversion bounce that hasn't
    resolved in that time isn't the setup that was traded.

GRID (K=27, honest/literal): K_PIVOT in {5,10,20} x TOL in {0.15,0.25,0.35}
x TARGET_R in {1.5,2.0,3.0}. Touch window (5 bars) and stop buffer (0.25
ATR) are fixed textbook defaults, not searched, to keep K honest.

Splits / cost model / null / K-correction: see common.py (unchanged).
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

K_PIVOTS = [5, 10, 20]
TOLS = [0.15, 0.25, 0.35]
TARGET_RS = [1.5, 2.0, 3.0]
TOUCH_WINDOW = 5
STOP_BUF_ATR = 0.25
MAX_HOLD = 80


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    no_exit = np.zeros(b.n, dtype=np.bool_)

    piv_cache = {}
    for k in K_PIVOTS:
        ph, pl = C.pivots(b.high, b.low, k)
        support = pd.Series(pl).ffill().values
        resistance = pd.Series(ph).ffill().values
        diff_low = b.low - support
        diff_high = b.high - resistance
        roll_min_low = pd.Series(diff_low).rolling(TOUCH_WINDOW, min_periods=1).min().values
        roll_max_high = pd.Series(diff_high).rolling(TOUCH_WINDOW, min_periods=1).max().values
        piv_cache[k] = (support, resistance, roll_min_low, roll_max_high)

    def signal_fn(cfg):
        k, tol, _ = cfg
        support, resistance, roll_min_low, roll_max_high = piv_cache[k]
        tolv = tol * b.atr
        valid = ~np.isnan(support) & ~np.isnan(resistance) & ~np.isnan(b.atr)

        touched_s = roll_min_low <= tolv
        bounce_l = touched_s & (b.close > support + tolv) & valid
        bounce_l_prev = np.concatenate(([False], bounce_l[:-1]))
        long_edge = bounce_l & ~bounce_l_prev

        touched_r = roll_max_high >= -tolv
        bounce_s = touched_r & (b.close < resistance - tolv) & valid
        bounce_s_prev = np.concatenate(([False], bounce_s[:-1]))
        short_edge = bounce_s & ~bounce_s_prev

        il = np.where(long_edge)[0]
        is_ = np.where(short_edge)[0]
        dl = b.close[il] - (support[il] - STOP_BUF_ATR * b.atr[il])
        ds = (resistance[is_] + STOP_BUF_ATR * b.atr[is_]) - b.close[is_]
        bars_ = np.concatenate((il, is_))
        dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        dist = np.concatenate((dl, ds))
        o = np.argsort(bars_, kind="stable")
        return bars_[o].astype(np.int64), dirs[o], dist[o]

    def exit_fn(cfg):
        target_r = cfg[2]
        return dict(target_r=target_r, max_hold=MAX_HOLD, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(K_PIVOTS, TOLS, TARGET_RS))
    return C.full_evaluation(b, f"{symbol} M15 -- horizontal S/R bounce (K_PIVOT, TOL_ATR, TARGET_R)",
                             grid, signal_fn, exit_fn, min_is_n=100, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/sr_bounce_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
