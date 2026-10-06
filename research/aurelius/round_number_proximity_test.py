"""
NEW CANDIDATE (2026-10-06, user's own observation): Aurelius M5 live has
not won a single trade while price has stayed below the alignment gate
(InpAlignMode's "c vs 2400 EMA" check) during the current stretch near
Gold's $4000 level. Hypothesis: this isn't really a DIRECTIONAL problem
(the long/short split already checked found shorts are actually the
STRONGER historical side for Aurelius M5, not weaker) - it's a PROXIMITY
problem. Price consolidating right at a major round-number support/
resistance zone can whipsaw a trend-follower regardless of direction,
because the zone itself keeps rejecting and re-testing rather than
letting a real trend develop.

Tests this on Aurelius M5's own REAL, validated trades (v1.46 shipped,
unmodified) - not a new construction, a descriptive split by distance
from the nearest round-number level at entry. ROUND_STEP=50 (gold's
own psychological level spacing - $4000, $4050, $4100 etc, matching
exactly the level the user flagged) with a secondary check at
ROUND_STEP=100 for robustness. Only the full-history TREND of win%%/PF
vs distance matters here (does proximity predict worse outcomes AT ALL,
historically, not just in the current stretch) - this doesn't have
access to live-only trades to test the CURRENT stretch specifically,
only whether the mechanism is real in the available history.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def nearest_round_dist(price, step):
    return min(price % step, step - (price % step))


def report_buckets(label, dists_atr, pnl, edges):
    print(f"\n{label}")
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (dists_atr >= lo) & (dists_atr < hi)
        p = np.asarray(pnl)[mask]
        if len(p) == 0:
            print(f"    [{lo:.2f},{hi:.2f}) ATR: n=0")
            continue
        print(f"    [{lo:.2f},{hi:.2f}) ATR: n={len(p):4d}  win%={100*(p>0).mean():5.1f}  "
              f"PF={pf(p):6.3f}  net={p.sum():9.2f}  avg={p.mean():7.3f}")


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    print(f"Real GOLD M5: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({len(df)} bars)")
    ctx = E.build_context(df, h4, E.P)

    trades = S.simulate(ctx, params=E.P)
    print(f"Real Aurelius M5 v1.46 trades: n={len(trades)}")

    c, atr = ctx["close"], ctx["atr"]
    pnl = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades])

    for step in (50, 100):
        entry_px = np.array([t["entry_px"] for t in trades])
        entry_atr = np.array([atr[t["entry_i"]] for t in trades])
        valid = entry_atr > 0
        dist_price = np.array([nearest_round_dist(p, step) for p in entry_px])
        dist_atr = np.where(valid, dist_price / np.where(valid, entry_atr, 1.0), np.nan)

        print(f"\n{'='*92}\nDistance from nearest ${step} round-number level at entry (x ATR) - "
              f"closer to 0 = right at the level\n{'='*92}")
        max_possible = (step / 2) / np.median(entry_atr[valid])
        edges = [0.0, 0.5, 1.0, 2.0, max(3.0, max_possible)]
        report_buckets(f"${step} round-number proximity buckets", dist_atr, pnl, edges)

        near = dist_atr < 1.0
        far = dist_atr >= 1.0
        print(f"\n  NEAR (<1.0 ATR from a ${step} level): n={near.sum()}  win%={100*(pnl[near]>0).mean():.1f}  "
              f"PF={pf(pnl[near]):.3f}  net={pnl[near].sum():.2f}")
        print(f"  FAR  (>=1.0 ATR from a ${step} level): n={far.sum()}  win%={100*(pnl[far]>0).mean():.1f}  "
              f"PF={pf(pnl[far]):.3f}  net={pnl[far].sum():.2f}")

    print(f"\n{'='*92}\nSPECIFIC TO THE CURRENT $4000 ZONE: every real trade whose entry fell\n"
          f"within 1.0xATR of a $4000-aligned level ($3950-4050, $3900-4100 wider band)\n{'='*92}")
    entry_px = np.array([t["entry_px"] for t in trades])
    near_4000 = (entry_px >= 3900) & (entry_px <= 4100)
    if near_4000.sum() == 0:
        print("  no real trades have occurred in this price zone yet in the available history - "
              "gold has mostly traded at other price levels across this dataset (2022-2026 move "
              "roughly $1700->$4000+), so the CURRENT live stretch near $4000 is largely untested "
              "territory for this specific EA/instrument, not just unlucky.")
    else:
        p = pnl[near_4000]
        print(f"  n={near_4000.sum()}  win%={100*(p>0).mean():.1f}  PF={pf(p):.3f}  net={p.sum():.2f}")
