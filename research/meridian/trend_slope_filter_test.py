"""
NEW CANDIDATE (2026-10-05, user's own idea, separate from and NOT combined
with vwap_cross_entry_test.py's idea - each counted as its own attempt, own
honest K): the user's complaint is that Meridian's shipped 21/50 EMA cross
can fire on a weak/shallow cross while the short-term trend is still
clearly pointing the other way - i.e. betting on a reversal rather than
trading with the move. Tested here as a single boolean gate added ON TOP
of the shipped signal: require the 50-EMA's OWN slope over the prior
InpSlopeLookback=20 bars (100 min on M5 - a plain round number, not swept)
to already agree with the trade direction before the cross is allowed to
fire. If the slower MA itself hasn't turned yet, skip the trade.

This is implemented via msim.py's own entry_filter hook (f(ctx, t, dir) ->
bool), which is designed for exactly this: an ADDITIONAL confirmation gate
on top of the normal cross+250SMA+VWAP+S/R logic, unlike entry_fn (which
REPLACES that logic and is reserved for the random-timing null). No other
EA/filter from this project was touched or reused incorrectly.

Honest K for this idea: 1 (one fixed lookback, chosen a priori, no sweep).
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(0, "/home/user/test-project/research/meridian")
import msim as M   # noqa: E402

SLOPE_LOOKBACK = 20   # bars (100 min on M5) - plain round number, not tuned


def trend_slope_filter(ctx, t, d):
    m50 = M.ma(ctx, 50, "ema")
    s = t - 1
    if s - SLOPE_LOOKBACK < 0:
        return False
    slope = m50[s] - m50[s - SLOPE_LOOKBACK]
    return (slope > 0) if d > 0 else (slope < 0)


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([t["pnl"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  avg={pnl.mean():7.3f}")


def random_entry_fn_matched(ctx, i0, i1, n_target, entry_from_min, long_frac, seed=0):
    rng = np.random.default_rng(seed)
    eligible = [t for t in range(i0 + 1, i1) if ctx["mod"][t] >= entry_from_min and
                not (ctx["dow"][t] == 5 and ctx["hour"][t] >= 22)]
    chosen = rng.choice(eligible, size=min(n_target, len(eligible)), replace=False)
    dirs = {int(t): (1 if rng.random() < long_frac else -1) for t in chosen}

    def fn(ctx2, t):
        return dirs.get(t, 0)
    return fn


if __name__ == "__main__":
    ctx = M.build_ctx()
    n_bars = len(ctx["t64"])
    cutoff = int(n_bars * 0.70)
    cutoff_time = pd.Timestamp(ctx["t64"][cutoff])
    full_start, full_end = pd.Timestamp(ctx["t64"][0]), pd.Timestamp(ctx["t64"][-1])
    print(f"GOLD M5 real data: {full_start} .. {full_end}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {cutoff_time}")

    filtered_params = replace(M.V102, entry_filter=trend_slope_filter)

    print("\n" + "=" * 90)
    print(f"NEW FILTER: require 50-EMA's own {SLOPE_LOOKBACK}-bar slope to already agree with the")
    print("trade direction before the shipped 21/50 cross is allowed to fire")
    print("=" * 90)
    for label, start, end in (("FULL HISTORY", full_start, full_end),
                               ("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                               ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
        base_trades, base_stats = M.simulate(ctx, M.V102, start=start, end=end)
        filt_trades, filt_stats = M.simulate(ctx, filtered_params, start=start, end=end)
        report(f"{label:28s} shipped (no filter)", base_trades)
        report(f"{label:28s} +trend-slope filter", filt_trades)
        blocked = filt_stats.get("blk_filter", 0)
        print(f"    (filter blocked {blocked} of {base_stats['crosses']} crosses that otherwise reached it)")

    print("\n" + "=" * 90)
    print("RANDOM-TIMING NULL for the FILTERED signal: same exits/spread/stop, entry count matched")
    print("to the filtered signal's own trade count, entries placed uniformly at random (2000 draws)")
    print("=" * 90)
    i0_full = int(np.searchsorted(ctx["t64"], np.datetime64(full_start)))
    i1_full = int(np.searchsorted(ctx["t64"], np.datetime64(full_end)))
    real_trades, _ = M.simulate(ctx, filtered_params, start=full_start, end=full_end)
    n_real = len(real_trades)
    long_frac = np.mean([t["dir"] > 0 for t in real_trades]) if real_trades else 0.5
    real_pf = pf([t["pnl"] for t in real_trades])
    print(f"  real +trend-slope-filter: n={n_real}, PF={real_pf:.3f}, long_frac={long_frac:.2f}")

    NDRAWS = 2000
    null_pfs = []
    for seed in range(NDRAWS):
        efn = random_entry_fn_matched(ctx, i0_full, i1_full, n_real, M.V102.entry_from_min, long_frac, seed=seed)
        null_p = replace(M.V102, entry_fn=efn)
        ntrades, _ = M.simulate(ctx, null_p, start=full_start, end=full_end)
        pnl = np.array([t["pnl"] for t in ntrades])
        null_pfs.append(pf(pnl))
    null_pfs = np.array(null_pfs)
    p_value = (null_pfs >= real_pf).mean()
    print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
          f"p95={np.percentile(null_pfs,95):.3f}")
    print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} "
          f"random-timing draws with matched trade count/spread/exits")
    print(f"  p-value (P[null PF >= real PF]) = {p_value:.4f}  "
          f"{'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")
    print(f"\n  Honest K for this idea: 1 (fixed {SLOPE_LOOKBACK}-bar lookback, no sweep run).")
