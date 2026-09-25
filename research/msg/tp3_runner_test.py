"""
User's real chart observation (2026-09-25): a real MSG sell trade closed
its final leg at TP3, but price kept running far beyond that (the
screenshot shows a large continued decline after TP3, a classic "the
runner would have made much more" complaint) - and specifically flagged
that TP3 looks like it's set close to the session box's own range, not
sized for a real trend continuation.

Checked against the code first: TP3 (sim.py Params.tp3=2.0, matching
MSG_Trader_EA.mq5's real InpTP3_RR=2.0) is a fixed 2.0x-risk BROKER TP
order that closes the ENTIRE remaining position (the last third, after
TP1/TP2) the moment price reaches it - there is no runner concept in the
current EA. The user's read of the mechanism is correct.

This test: for every real trade whose final leg actually reason=="tp"
(reached TP3), re-walk the SAME M1 bars forward from the TP3 fill,
holding those same final-leg units instead of closing them, with a
trailing stop at trail_r x risk behind the peak (same "trail" convention
sim.py already uses post-TP2, just continued past TP3 instead of stopping
there), until stopped out or InpMaxHoldHours more elapses. Compares real
PnL for that leg (already realized at TP3) vs the runner variant, for a
few trail widths - same walk-forward discipline as every other test this
session.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from sim import Params, simulate, load_bars, PT, CONTRACT, LOT_STEP

np.random.seed(42)

TRAIL_WIDTHS = (0.5, 1.0, 1.5, 2.0, 3.0)
MAX_EXTRA_HOLD_H = 48.0   # matches Params.max_hold_h - same real cap, not unlimited


def run_runner(bars, trades, trail_r, max_extra_hold_h):
    t_arr = bars["time"].values.astype("datetime64[s]").astype(np.int64)
    h_arr = bars["high"].values
    l_arr = bars["low"].values
    o_arr = bars["open"].values
    n = len(bars)

    real_leg_pnls = []
    runner_pnls = []
    for tr in trades:
        legs = tr["legs"]
        last = legs[-1]
        if last[3] != "tp":
            continue
        exit_t, exit_px, units, _ = last
        d = tr["dir"]
        risk = tr["risk"]
        real_pnl = (exit_px - tr["fill"]) * d * units * LOT_STEP * CONTRACT
        # note: this is NOT the same as the leg's own marginal pnl vs tp2 -
        # it's vs entry, matching how `finish()` sums every leg - but for
        # the RUNNER comparison what matters is the price path AFTER TP3,
        # so we hold `units` from the TP3 fill price forward.
        real_leg_pnls.append(real_pnl)

        k0 = int(np.searchsorted(t_arr, exit_t))
        if k0 >= n - 1:
            runner_pnls.append(real_pnl)  # no bars left to test, can't improve or worsen
            continue
        entry_r = exit_px
        peak = entry_r
        sl = entry_r - d * trail_r * risk
        deadline = exit_t + max_extra_hold_h * 3600
        out_px = None
        for k in range(k0 + 1, n):
            if t_arr[k] > deadline:
                out_px = o_arr[k]; break
            fav_hi = h_arr[k] if d > 0 else l_arr[k]
            if d > 0:
                peak = max(peak, fav_hi)
                new_sl = peak - trail_r * risk
                sl = max(sl, new_sl)
                if l_arr[k] <= sl:
                    out_px = sl; break
            else:
                peak = min(peak, fav_hi)
                new_sl = peak + trail_r * risk
                sl = min(sl, new_sl)
                if h_arr[k] >= sl:
                    out_px = sl; break
        if out_px is None:
            out_px = o_arr[n - 1]
        runner_pnl = (out_px - exit_px) * d * units * LOT_STEP * CONTRACT + real_pnl
        runner_pnls.append(runner_pnl)

    return np.array(real_leg_pnls), np.array(runner_pnls)


if __name__ == "__main__":
    bars = load_bars()
    p = Params()
    trades, stats_ = simulate(bars, p)
    tp3_trades = [t for t in trades if t["legs"] and t["legs"][-1][3] == "tp"]
    print(f"Real MSG3 trades (default Params, {p.start}->{p.end}): n={len(trades)}")
    print(f"  of those, final leg reached TP3: {len(tp3_trades)}\n")

    for trail_r in TRAIL_WIDTHS:
        real_pnls, runner_pnls = run_runner(bars, tp3_trades, trail_r, MAX_EXTRA_HOLD_H)
        diff = runner_pnls - real_pnls
        print(f"  trail={trail_r:.1f}R: real_leg_net=${real_pnls.sum():8.2f}  "
              f"runner_net=${runner_pnls.sum():8.2f}  diff=${diff.sum():8.2f}  "
              f"(runner better on {100*(diff>0).mean():.1f}% of these {len(diff)} legs, "
              f"worse on {100*(diff<0).mean():.1f}%)")

    # walk-forward: split by TP3 exit time, chronological 70/30
    exit_times = np.array([t["legs"][-1][0] for t in tp3_trades])
    order = np.argsort(exit_times)
    cutoff = exit_times[order][int(len(order) * 0.7)]
    print(f"\n  walk-forward (chronological 70/30 by TP3 exit time) at trail=1.0R:")
    real_pnls, runner_pnls = run_runner(bars, tp3_trades, 1.0, MAX_EXTRA_HOLD_H)
    is_m = exit_times < cutoff
    oos_m = exit_times >= cutoff
    print(f"    IS : real=${real_pnls[is_m].sum():.2f}  runner=${runner_pnls[is_m].sum():.2f}  "
          f"diff=${(runner_pnls[is_m]-real_pnls[is_m]).sum():.2f}  n={is_m.sum()}")
    print(f"    OOS: real=${real_pnls[oos_m].sum():.2f}  runner=${runner_pnls[oos_m].sum():.2f}  "
          f"diff=${(runner_pnls[oos_m]-real_pnls[oos_m]).sum():.2f}  n={oos_m.sum()}")
