"""
"Scalp Signal Bot - 5 min v3.0.1" - the user's tenth pasted script in
this batch, the largest of the 12 (39KB, mostly HUD/label/probability-
display code). Core mechanism: a rolling N-bar (sweepLookback=60)
lowest-low / highest-high "liquidity sweep" detector, structure breaks
of the last confirmed swing pivot (pivotLen=3, wicks by default) gate
entries, with several optional risk filters this script's OWN defaults
turn on: a sweep-cluster-aware "reclaim suppression" (if >=2 low-sweeps
clustered in the last 20 bars AND a reclaim just printed, SHORTS are
suppressed for sweepMaxAgeBars=12 bars - mirrored for longs on a high-
sweep cluster+reclaim) and a 1-bar post-sweep entry delay (anti-
fakeout). A REAL, FAITHFULLY-PRESERVED ASYMMETRY: enterLongRaw requires
the low-sweep gate (sweepGate/sweepConfirmed); enterShortRaw does NOT
require the equivalent high-sweep gate at all - shorts only need a plain
structure break. Stop-loss = the swept level (or, for shorts with no
prior high sweep, the last swing high) +/- a small tick buffer; target
is a pure R-multiple of that stop distance (riskR=1.0 default - a true
scalp, matching the name).

DROPPED, DISCLOSED, OUT OF SCOPE (same reasoning as julzALGO's script in
this same batch): useWindow=true/backtestHours=168 filters trading to
the last 7 days of REAL wall-clock time from whenever the indicator is
evaluated - a TradingView replay-limiting convenience, not a strategy
rule. Forced off (windowOK=True always). cooldownBars=0 (script's own
default) is already a no-op. volMode="Off" (script's own default) is
already a no-op. useSweepClustering=false (script's own default) means
the cluster-count itself doesn't directly BLOCK entries (clusterBlock*),
but the cluster count still feeds reclaim-suppression (useReclaimLogic=
true, NOT gated by useSweepClustering) - that part is live by default
and is ported faithfully. trendMode="CHOP" (default) disables the EMA
filter entirely - kept off, matching the default.

PORTED FAITHFULLY, FULLY VECTORIZED (every piece of state here - last
swing pivot, last sweep price/bar, the cluster ring-buffer count, the
reclaim-suppression timer, the sweep-entry-delay timer - only ever
"holds its last value until a new trigger," so each is computed as a
forward-fill or rolling-sum over the trigger array rather than a bar-by-
bar loop): the low/high sweep detection (strictly new N-bar extreme),
the two-bar "close back above/below with buffer" reclaim confirmation
(script's own default confirm mode), the 20-bar rolling sweep-cluster
count feeding reclaim-suppression, the 1-bar sweep-entry delay, and the
raw/padded stop asymmetry described above.

GRID (K=27, literal): RISK_R in {0.75,1.0,1.5} x SWEEP_MAX_AGE_BARS in
{6,12,24} x PIVOT_LEN in {2,3,5}. sweepLookback=60, clusterLookback=20,
minSweepCluster=2, sweepDelayBars=1, tickBuffer=10 are the script's own
defaults, fixed to keep K honest.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

RISK_RS = [0.75, 1.0, 1.5]
SWEEP_MAX_AGE_BARS_LIST = [6, 12, 24]
PIVOT_LENS = [2, 3, 5]
SWEEP_LOOKBACK = 60
CLUSTER_LOOKBACK = 20
MIN_SWEEP_CLUSTER = 2
SWEEP_DELAY_BARS = 1
TICK_BUFFER = 10


def ffill_at(trigger_mask, values):
    arr = np.where(trigger_mask, values, np.nan)
    return pd.Series(arr).ffill().values


def last_event_bar(event):
    n = len(event)
    idx = np.arange(n)
    val = np.where(event, idx, -1)
    return np.maximum.accumulate(val)


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    buf = TICK_BUFFER * point

    roll_min60 = pd.Series(b.low).rolling(SWEEP_LOOKBACK, min_periods=SWEEP_LOOKBACK).min().values
    roll_max60 = pd.Series(b.high).rolling(SWEEP_LOOKBACK, min_periods=SWEEP_LOOKBACK).max().values
    prior_lowest = np.concatenate(([np.nan], roll_min60[:-1]))
    prior_highest = np.concatenate(([np.nan], roll_max60[:-1]))
    is_new_lowest = b.low < prior_lowest
    is_new_highest = b.high > prior_highest

    sweep_price = ffill_at(is_new_lowest, b.low)
    sweep_bar = last_event_bar(is_new_lowest)
    high_sweep_price = ffill_at(is_new_highest, b.high)
    high_sweep_bar = last_event_bar(is_new_highest)

    close_prev = np.concatenate(([b.close[0]], b.close[:-1]))
    with np.errstate(invalid="ignore"):
        reclaim_ok = (~np.isnan(sweep_price)) & (close_prev <= sweep_price + buf) & (b.close > sweep_price + buf)
        high_reclaim_ok = ((~np.isnan(high_sweep_price)) & (close_prev >= high_sweep_price - buf)
                           & (b.close < high_sweep_price - buf))

    down_count = pd.Series(is_new_lowest.astype(np.int64)).rolling(CLUSTER_LOOKBACK, min_periods=1).sum().values
    up_count = pd.Series(is_new_highest.astype(np.int64)).rolling(CLUSTER_LOOKBACK, min_periods=1).sum().values
    cluster_down = down_count >= MIN_SWEEP_CLUSTER
    cluster_up = up_count >= MIN_SWEEP_CLUSTER

    last_reclaim_flip_down = last_event_bar(cluster_down & reclaim_ok)
    last_reclaim_flip_up = last_event_bar(cluster_up & high_reclaim_ok)

    any_sweep = is_new_lowest | is_new_highest
    last_any_sweep_bar = last_event_bar(any_sweep)
    idx = np.arange(b.n)
    bars_since_any_sweep = np.where(last_any_sweep_bar >= 0, idx - last_any_sweep_bar, 10 ** 9)
    sweep_delay_ok = bars_since_any_sweep > SWEEP_DELAY_BARS

    grid = list(itertools.product(RISK_RS, SWEEP_MAX_AGE_BARS_LIST, PIVOT_LENS))
    pivot_cache = {pl: C.pivots(b.high, b.low, pl) for pl in PIVOT_LENS}

    def signal_fn(cfg):
        risk_r, max_age, pivot_len = cfg
        ph, pl_ = pivot_cache[pivot_len]
        last_swing_high = ffill_at(~np.isnan(ph), ph)
        last_swing_low = ffill_at(~np.isnan(pl_), pl_)

        sweep_recent = np.where(sweep_bar >= 0, idx - sweep_bar, 10 ** 9) <= max_age
        high_sweep_recent = np.where(high_sweep_bar >= 0, idx - high_sweep_bar, 10 ** 9) <= max_age
        sweep_confirmed = sweep_recent & reclaim_ok
        reclaim_suppress_short = (last_reclaim_flip_down >= 0) & (idx - last_reclaim_flip_down <= max_age)
        reclaim_suppress_long = (last_reclaim_flip_up >= 0) & (idx - last_reclaim_flip_up <= max_age)

        with np.errstate(invalid="ignore"):
            enter_long = (~np.isnan(last_swing_high)) & (b.close > last_swing_high) & sweep_confirmed
            enter_short = (~np.isnan(last_swing_low)) & (b.close < last_swing_low)
        enter_long = enter_long & sweep_delay_ok & ~reclaim_suppress_long
        enter_short = enter_short & sweep_delay_ok & ~reclaim_suppress_short

        long_sl = sweep_price - buf
        short_sl = np.where(~np.isnan(high_sweep_price), high_sweep_price + buf, last_swing_high + buf)

        il = np.where(enter_long)[0]
        is_ = np.where(enter_short)[0]
        dist_l = b.close[il] - long_sl[il]
        dist_s = short_sl[is_] - b.close[is_]
        valid_l = ~np.isnan(dist_l) & (dist_l > 0)
        valid_s = ~np.isnan(dist_s) & (dist_s > 0)
        il, dist_l = il[valid_l], dist_l[valid_l]
        is_, dist_s = is_[valid_s], dist_s[valid_s]

        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        return sig_bar[order], sig_dir[order], sig_dist[order]

    def exit_fn(cfg):
        risk_r, max_age, pivot_len = cfg
        no_exit = np.zeros(b.n, dtype=np.bool_)
        return dict(target_r=risk_r, max_hold=2000, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    return C.full_evaluation(b, f"{symbol} M15 -- Scalp Signal Bot 5min (RISK_R, SWEEP_MAX_AGE_BARS, PIVOT_LEN)",
                              grid, signal_fn, exit_fn, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/scalp_signal_bot_5min_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
