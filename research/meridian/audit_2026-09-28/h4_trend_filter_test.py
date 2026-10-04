"""
Does the SAME H4 trend-alignment entry filter that just fixed Vanguard
M5 (vanguard_m5_h4_trend_filter_oos_test.py: baseline p=0.12 -> +filter
p=0.0000 on genuinely untouched data) also help Meridian_EA.mq5's
21/50 EMA-cross entry, or is it redundant with the InpPConfirm=250 SMA
Meridian already uses?

Not assumed - tested the same way, on the same untouched
2014-07-01->2022-07-04 GOLD M5 window meridian_untouched_msim.py and
trend_exhaustion_exit_test.py already use (msim.py's own canonical
untouched window). Uses msim.py's existing `entry_filter` hook
(f(ctx, t, dir) -> bool), an AND-gate on top of the real cross+confirm
+VWAP+S/R decision - doesn't touch msim.py itself.

H4 trend state: last CLOSED H4 bar's close vs its own 50-period EMA,
same construction as Vanguard's filter. K=1 - one pre-specified filter,
not swept, matching this project's no-overfitting-risk discipline.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/silver_btc")
sys.path.insert(0, "/home/user/test-project/research/meridian")
sys.path.insert(1, "/home/user/test-project/research/aurelius")
from dataclasses import replace
from multiprocessing import Pool
import numpy as np
import pandas as pd
import msim as M
import engine as E
import meridian_msim_transfer_test as T

CUT = pd.Timestamp("2022-07-04")
START = pd.Timestamp("2014-07-01")
H4_EMA_PERIOD = 50

G = {}


def ema(x, period):
    return pd.Series(x).ewm(alpha=2.0 / (period + 1.0), adjust=False).mean().values


def build_h4_trend_up(m5_time, h4):
    h4_ema = ema(h4["close"].values, H4_EMA_PERIOD)
    h4_trend_up = h4["close"].values > h4_ema
    h4_time = h4["time"].values
    # side="left"-1: strictly the last COMPLETED H4 bar before this M5 bar's
    # time (the Vanguard test's own lookahead bug used side="right" here -
    # fixed there, applying the fix from day one here instead of repeating it).
    h4_idx = np.searchsorted(h4_time, m5_time, side="left") - 1
    h4_idx = np.clip(h4_idx, 0, len(h4) - 1)
    valid = h4_idx >= 1
    return h4_trend_up[h4_idx], valid


def h4_filter(ctx, t, d):
    up, valid = G["h4_up"], G["h4_valid"]
    if not valid[t]:
        return False
    return up[t] if d > 0 else (not up[t])


def rrun(args):
    seed, pf_, pl = args
    cx = G["cx"]
    rng = np.random.default_rng(seed)
    n = len(cx["c"])
    fire = rng.random(n) < pf_
    dirs = np.where(rng.random(n) < pl, 1, -1)
    tr, _ = M.simulate(cx, replace(M.V102, entry_fn=lambda c, t: int(dirs[t]) if fire[t] else 0), START, CUT)
    return T.pct(tr), None


if __name__ == "__main__":
    m5x = E.load_m5_extended()
    df = m5x[m5x.time < CUT][["time", "open", "high", "low", "close", "tick_volume", "spread"]].reset_index(drop=True)
    ctx = M.build_ctx(df)
    h4 = E.load_h4()
    h4 = h4[h4["time"] < CUT].reset_index(drop=True)

    print(f"{'='*90}\nMeridian H4 trend-alignment entry filter, untouched {START.date()}->{CUT.date()} GOLD M5\n{'='*90}")

    real_base, _ = M.simulate(ctx, M.V102, START, CUT)
    rb = T.pct(real_base)
    print(f"BASELINE (shipped v1.02, no H4 filter): n={len(rb)} win%={100*(rb>0).mean():.1f} "
          f"%PF={T.pct_pf(rb):.3f} net%={100*rb.sum():.1f}")

    h4_up, h4_valid = build_h4_trend_up(ctx["t64"], h4)
    G["h4_up"], G["h4_valid"] = h4_up, h4_valid
    p_h4 = replace(M.V102, entry_filter=h4_filter)
    real_h4, _ = M.simulate(ctx, p_h4, START, CUT)
    rh = T.pct(real_h4)
    print(f"+ H4 trend filter: n={len(rh)} win%={100*(rh>0).mean():.1f} "
          f"%PF={T.pct_pf(rh):.3f} net%={100*rh.sum():.1f}")

    if len(rh) < 20:
        print("Too few trades to run a meaningful random-timing null.")
        sys.exit(0)

    G["cx"] = ctx
    target = len(rh)
    tpf = T.pct_pf(rh)
    with Pool(4) as pool_:
        pf_ = target / len(df) * 1.3
        for it in range(8):
            ms = np.mean([len(x[0]) for x in pool_.map(rrun, [(10_000 + it * 10 + r, pf_, 0.5) for r in range(4)])])
            if abs(ms - target) / target < 0.03:
                break
            pf_ = min(0.5, pf_ * target / ms)
        out = pool_.map(rrun, [(s, pf_, 0.5) for s in range(600)])
    pool = np.array([T.pct_pf(a) for a, _ in out])
    ns = np.mean([len(a) for a, _ in out])
    pool = pool[np.isfinite(pool)]
    pctile = 100 * (pool < tpf).mean()
    p1 = (pool >= tpf).mean()
    print(f"\nrandom-timing null (600, mean n={ns:.0f} vs {target}): median={np.median(pool):.3f} "
          f"p95={np.percentile(pool,95):.3f}")
    print(f"REAL %PF={tpf:.3f} -> {pctile:.1f}th percentile, p={p1:.4f} (K=1, one pre-specified filter)")
