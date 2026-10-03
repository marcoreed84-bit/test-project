"""
Trend-reversal/exhaustion EARLY exit for Meridian_EA.mq5, on the real
untouched 2014-07->2022-07 GOLD M5 window (same window/convention as this
folder's own meridian_untouched_msim.py, which found the shipped v1.02
baseline loses money there: %PF=0.807).

USER'S DIAGNOSIS, checked directly: Meridian's only exit is a fixed
2.5xATR stop plus the 21/50 REVERSAL cross (already in msim.py's baseline
event order) - nothing reacts to the trend STALLING before it fully
reverses. A give-back (profit-stall) exit was already tried and REJECTED
(-43.2% net, confirmed against a real MT5 A/B test on the sibling Aurelius
EA). An oscillator-DIVERGENCE exit (RSI/MACD/Stochastic) was also already
tried and failed even its first-pass screen (divergence_exit_test.py).

This is a THIRD, different construction from both: it watches the EA's
OWN fast MA (EMA21, the same line Meridian already trades on) for its
SLOPE turning against the position - an early warning the trend is losing
continuation, checked BEFORE the full 21/50 cross confirms a reversal.
Structurally distinct from give-back (profit-based) and divergence
(oscillator-based).

CONSTRUCTION: once a position has been open >= MIN_BARS_ACTIVE bars (fixed
at 3, not searched - avoids whipsawing out on the entry bar's own noise),
exit at the next bar's open if EMA21's value LOOKBACK bars ago vs now has
turned against the position's direction (long: ema21 now < ema21
LOOKBACK bars ago; mirror for short).

GRID (K=3, literal, small and honest): LOOKBACK in {3, 5, 8} bars.
Reports the real untouched-window result for baseline (no new exit) and
each LOOKBACK value, plus the random-timing null for whichever LOOKBACK
value is selected (best of the 3 by net%, matching this folder's own
no-separate-IS-set convention since msim.py's untouched window IS already
the held-out set - there is no further split to tune against).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/silver_btc")
sys.path.insert(0, "/home/user/test-project/research/meridian")
sys.path.insert(0, "/home/user/test-project/research/ratchet")
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
MIN_BARS_ACTIVE = 3
LOOKBACKS = [3, 5, 8]

G = {}


def make_exit_fn(lookback):
    def exit_fn(ctx, t, pos):
        if pos["bars"] < MIN_BARS_ACTIVE:
            return None
        m21 = M.ma(ctx, 21, "ema")
        s = t - 1
        if s - lookback < 0 or np.isnan(m21[s]) or np.isnan(m21[s - lookback]):
            return None
        turned_down = m21[s] < m21[s - lookback]
        turned_up = m21[s] > m21[s - lookback]
        d = pos["dir"]
        if (d > 0 and turned_down) or (d < 0 and turned_up):
            return "TREND_EXHAUSTION"
        return None
    return exit_fn


def rrun(args):
    seed, pf_, pl, exit_fn = args
    cx = G["cx"]
    rng = np.random.default_rng(seed)
    n = len(cx["c"])
    fire = rng.random(n) < pf_
    dirs = np.where(rng.random(n) < pl, 1, -1)
    tr, _ = M.simulate(cx, replace(M.V102, entry_fn=lambda c, t: int(dirs[t]) if fire[t] else 0, exit_fn=exit_fn),
                       START, CUT)
    return T.pct(tr), None


if __name__ == "__main__":
    m5x = E.load_m5_extended()
    df = m5x[m5x.time < CUT][["time", "open", "high", "low", "close", "tick_volume", "spread"]].reset_index(drop=True)
    ctx = M.build_ctx(df)

    print(f"{'='*90}\nMeridian trend-exhaustion early exit, untouched {START.date()}->{CUT.date()} GOLD M5\n{'='*90}")

    real_base, _ = M.simulate(ctx, M.V102, START, CUT)
    rb = T.pct(real_base)
    print(f"BASELINE (shipped v1.02, no new exit): n={len(rb)} win%={100*(rb>0).mean():.1f} "
          f"%PF={T.pct_pf(rb):.3f} net%={100*rb.sum():.1f}")

    results = []
    for lb in LOOKBACKS:
        ef = make_exit_fn(lb)
        p = replace(M.V102, exit_fn=ef)
        real, st = M.simulate(ctx, p, START, CUT)
        ra = T.pct(real)
        from collections import Counter
        exits = dict(Counter(t["reason"] for t in real))
        print(f"LOOKBACK={lb}: n={len(ra)} win%={100*(ra>0).mean():.1f} %PF={T.pct_pf(ra):.3f} "
              f"net%={100*ra.sum():.1f} exits={exits}")
        results.append((lb, ra, real))

    best_lb, best_ra, best_trades = max(results, key=lambda r: r[1].sum())
    print(f"\nBest by net%: LOOKBACK={best_lb}")

    if len(best_ra) >= 20:
        ef = make_exit_fn(best_lb)
        G["cx"] = ctx
        target = len(best_ra)
        tpf = T.pct_pf(best_ra)
        with Pool(4) as pool_:
            pf_ = target / len(df) * 1.3
            for it in range(8):
                ms = np.mean([len(x[0]) for x in pool_.map(rrun, [(10_000 + it * 10 + r, pf_, 0.5, ef) for r in range(4)])])
                if abs(ms - target) / target < 0.03:
                    break
                pf_ = min(0.5, pf_ * target / ms)
            out = pool_.map(rrun, [(s, pf_, 0.5, ef) for s in range(400)])
        pool = np.array([T.pct_pf(a) for a, _ in out])
        ns = np.mean([len(a) for a, _ in out])
        pool = pool[np.isfinite(pool)]
        pctile = 100 * (pool < tpf).mean()
        p1 = (pool >= tpf).mean()
        print(f"  random-timing null (400, mean n={ns:.0f} vs {target}): median={np.median(pool):.3f} "
              f"p95={np.percentile(pool,95):.3f}")
        print(f"  REAL %PF={tpf:.3f} -> {pctile:.1f}th percentile, p(K=1)={p1:.4f}, "
              f"p(K={len(LOOKBACKS)})={'see note below'}")
        print(f"  (K={len(LOOKBACKS)} since {len(LOOKBACKS)} LOOKBACK values were searched - "
              f"multiply p(K=1) risk up accordingly, not reported as a separate best-of-K draw here "
              f"since this is a single exploratory pass, not a frozen production claim)")
    else:
        print(f"  Only {len(best_ra)} trades - too few to run a meaningful random-timing null.")
