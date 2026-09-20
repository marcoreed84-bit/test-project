"""
Walk-forward validation for the cloud-reject + Stochastic candidate
(cloud_stoch_test.py / cloud_stoch_sweep.py). A single 70/30 IS/OOS split
is one draw; this checks temporal stability across FIVE independent,
non-overlapping chronological blocks instead - a real edge should hold up
across most of them, not just exist in aggregate.

No re-optimization per block: these are fixed trading rules (not fitted
parameters), so "walk-forward" here means testing STABILITY of a fixed
rule across time, not re-fitting per fold - re-optimizing on ~130-trade
blocks would just be a faster route to overfitting, not less of one.

Two rule sets tested, both at the TP:SL ratio (2.5xATR/1.5xATR) that
showed cross-parameter consistency in the sweep:
  A) the CLASSIC/default Stochastic(14,3,3), 20/80 - chosen on principled
     grounds (standard textbook setting), not because it scored highest,
     to avoid compounding the sweep's own best-of-N selection.
  B) the SWEEP'S single best cell (Stochastic(9,3,3), 20/80) - included
     for comparison, with the explicit caveat that it was the best-of-35
     pick and is more likely to regress toward the mean out of sample.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from cloud_stoch_test import stochastic, tp_sl_outcomes
from cloud_stoch_sweep import build_triggers

N_BLOCKS = 5


def block_report(label, ctx, triggers, tp_atr, sl_atr, n_blocks=N_BLOCKS, seed=0):
    n = ctx["n"]
    out, dropped = tp_sl_outcomes(ctx, triggers, tp_atr, sl_atr, maxhold=12)
    if not out:
        print(f"  {label}: no resolved trades")
        return
    pnl_buy = np.array([o[0] for o in out]); pnl_sell = np.array([o[1] for o in out])
    entry_i = np.array([o[2] for o in out]); real_dir = np.array([o[3] for o in out])
    real_pnl = np.where(real_dir > 0, pnl_buy, pnl_sell)

    print(f"\n  === {label} === (n={len(out)} total, dropped={dropped}, "
          f"aggregate net=${real_pnl.sum():.2f}, win%={100*(real_pnl>0).mean():.1f})")
    edges = np.linspace(0, n, n_blocks + 1).astype(int)
    n_positive_blocks = 0
    n_beat_random_blocks = 0
    for b in range(n_blocks):
        lo, hi = edges[b], edges[b + 1]
        mask = (entry_i >= lo) & (entry_i < hi)
        n_b = mask.sum()
        if n_b == 0:
            print(f"    block {b+1}/{n_blocks} [{lo}:{hi}]: 0 trades")
            continue
        net_b = real_pnl[mask].sum()
        win_b = 100 * (real_pnl[mask] > 0).mean()
        pf_num = real_pnl[mask][real_pnl[mask] > 0].sum()
        pf_den = -real_pnl[mask][real_pnl[mask] <= 0].sum()
        pf_b = pf_num / pf_den if pf_den > 0 else np.inf
        rng = np.random.default_rng(seed + b)
        rdir = rng.integers(0, 2, size=(2000, n_b))
        random_nets = np.where(rdir == 1, pnl_buy[mask], pnl_sell[mask]).sum(axis=1)
        pct = 100 * (random_nets < net_b).mean()
        if net_b > 0:
            n_positive_blocks += 1
        if pct >= 75:
            n_beat_random_blocks += 1
        t0 = pd.to_datetime(ctx["time"][lo]).date()
        t1 = pd.to_datetime(ctx["time"][min(hi, n - 1)]).date()
        print(f"    block {b+1}/{n_blocks} [{t0} -> {t1}]: n={n_b} net=${net_b:.2f} "
              f"win%={win_b:.1f} pf={pf_b:.3f} random-dir%ile={pct:.1f}")
    print(f"    -> positive in {n_positive_blocks}/{n_blocks} blocks, "
          f"beat random (>=75th pct) in {n_beat_random_blocks}/{n_blocks} blocks")


if __name__ == "__main__":
    d = E.load_h4()
    p = E.params()
    ctx = E.build_context(d, p)
    n = ctx["n"]
    high, low, close, atr = ctx["high"], ctx["low"], ctx["close"], ctx["atr"]
    cloud_top, cloud_bot = ctx["cloud_top"], ctx["cloud_bot"]
    ctx["spread"] = d["spread"].values.astype(float)

    D = p["displacement"]
    sa_sh = pd.Series(ctx["sa_raw"]).shift(D).values
    sb_sh = pd.Series(ctx["sb_raw"]).shift(D).values
    is_bull_cloud = sa_sh > sb_sh
    is_bear_cloud = sb_sh > sa_sh

    print(f"n_bars={n} (H4, ~{n/6:.0f} trading days), {N_BLOCKS} non-overlapping "
          f"chronological blocks (~{n/6/N_BLOCKS:.0f} trading days each)\n")

    print("=" * 70)
    print("RULE A: Stochastic(14,3,3), 20/80 - classic/principled choice")
    k14, _ = stochastic(high, low, close, period=14)
    trig_a = build_triggers(high, low, close, atr, cloud_top, cloud_bot,
                             is_bull_cloud, is_bear_cloud, k14, 20.0, 80.0, n)
    print(f"{len(trig_a)} triggers total")
    block_report("tp=2.5xATR sl=1.5xATR", ctx, trig_a, 2.5, 1.5)
    block_report("tp=2.0xATR sl=1.5xATR (for comparison)", ctx, trig_a, 2.0, 1.5)

    print("\n" + "=" * 70)
    print("RULE B: Stochastic(9,3,3), 20/80 - sweep's single best cell (best-of-35 caveat applies)")
    k9, _ = stochastic(high, low, close, period=9)
    trig_b = build_triggers(high, low, close, atr, cloud_top, cloud_bot,
                             is_bull_cloud, is_bear_cloud, k9, 20.0, 80.0, n)
    print(f"{len(trig_b)} triggers total")
    block_report("tp=2.0xATR sl=1.5xATR (the sweep's best cell)", ctx, trig_b, 2.0, 1.5)
    block_report("tp=2.5xATR sl=1.5xATR (for comparison)", ctx, trig_b, 2.5, 1.5)
