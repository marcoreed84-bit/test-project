"""
Random-timing null for Pattern 1 ("clean break, no lookback"), OOS only -
same question this project always asks before trusting a result: does
catching the move at the VWAP-commitment point actually beat just entering
at a random early-session bar and holding the same 6 hours with the same
real spread? Pattern 2 is already dead (OOS PF=0.195) and isn't tested here.

Matched: same OOS window, same HOLD_BARS exit, same real spread, same
COUNT of entries as the real Pattern 1 OOS result (n=51), and the SAME mix
of long/short directions drawn from the real trades (not a free 50/50 - a
null that got to pick its own direction mix would have an unfair
advantage on a trending instrument like Gold over this period).
"""
import numpy as np
import pandas as pd
from vwap_open_scenarios_test import (
    load_gold_m15, classify_and_test, pct_pf, report, HOLD_BARS, GOLD_POINT
)

NDRAWS = 3000


if __name__ == "__main__":
    df = load_gold_m15()
    n = len(df)
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    n_oos = len(df_oos)

    # IS-winning params from vwap_open_scenarios_test.py's own search
    CLUSTER, BUF, TOL = 0.5, 0.25, 2
    real_p1, _ = classify_and_test(df_oos, CLUSTER, BUF, TOL)
    report("Pattern 1 - REAL OOS", real_p1)
    real_pf = pct_pf(real_p1)
    real_n = len(real_p1)
    real_dirs = [r["dir"] for r in real_p1]

    close = df_oos["close"].values
    spread = df_oos["spread"].values
    # eligible entry bars: anywhere HOLD_BARS before the end, matching the
    # same "exit HOLD_BARS later" mechanism Pattern 1 itself uses
    eligible = np.arange(0, n_oos - HOLD_BARS - 1)

    null_pfs = []
    for seed in range(NDRAWS):
        rng = np.random.default_rng(seed)
        chosen = rng.choice(eligible, size=real_n, replace=False)
        dirs = rng.permutation(real_dirs)  # same direction MIX as the real trades, reshuffled
        pnl = []
        for bar_i, d in zip(chosen, dirs):
            sc = spread[bar_i + 1] * GOLD_POINT if bar_i + 1 < n_oos else 0
            entry_px = close[bar_i] + (sc if d > 0 else -sc)
            exit_px = close[bar_i + HOLD_BARS]
            pnl.append(((exit_px - entry_px) / entry_px) * d)
        pnl = np.array(pnl)
        gw, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
        null_pfs.append(gw / gl if gl > 0 else float("inf"))

    null_pfs = np.array(null_pfs)
    finite = null_pfs[np.isfinite(null_pfs)]
    p_value = (null_pfs >= real_pf).mean()
    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), {NDRAWS} draws - matched n={real_n}, matched\n"
          f"direction mix, same {HOLD_BARS}-bar hold, real spread\n{'='*92}")
    print(f"  real Pattern 1 PF: {real_pf:.3f}")
    print(f"  null PF: median={np.median(finite):.3f}  p95={np.percentile(finite,95):.3f}  "
          f"p99={np.percentile(finite,99):.3f}")
    print(f"  real PF sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
    print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K note: 16 total combinations were searched across both patterns in the")
    print(f"  prior IS grid search (8 per pattern). A Bonferroni/Sidak correction against K=16")
    print(f"  would require roughly p<0.05/16 = p<0.0031 to survive at the conventional 0.05 level.")
