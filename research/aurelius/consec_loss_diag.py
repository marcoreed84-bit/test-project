"""
Diagnostic (NOT the candidate test): does a run of consecutive losses carry
any information about Aurelius's NEXT trade, on either timeframe?

This has to come first. A consecutive-loss circuit breaker is only a regime
detector if "k losses in a row" actually shifts the conditional expectancy of
what follows. Aurelius is a low-win-rate / high-payoff trend follower (M5 win
rate ~31%, M15 ~38%), so long losing runs are its NORMAL operating mode, not
an anomaly - the run-length distribution below is compared against the
i.i.d. (memoryless) expectation from the same win rate to see whether the
streaks are even clustered at all.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
import sim as S


def pnl_of(t):
    return (t["exit_px"] - t["entry_px"]) * t["dir"]


def run_lengths(losses):
    """lengths of maximal runs of True in a bool sequence"""
    out, cur = [], 0
    for x in losses:
        if x:
            cur += 1
        elif cur:
            out.append(cur); cur = 0
    if cur:
        out.append(cur)
    return out


def report(name, trades, ctx):
    p = np.array([pnl_of(t) for t in trades])
    loss = p <= 0
    wr = 1 - loss.mean()
    print(f"\n===== {name} =====")
    print(f"n={len(p)}  win_rate={wr:.4f}  net={p.sum():.1f}  mean/trade={p.mean():.3f}")

    # --- conditional expectancy given the preceding run of losses ---
    streak = np.zeros(len(p), dtype=int)
    s = 0
    for i in range(len(p)):
        streak[i] = s
        s = s + 1 if loss[i] else 0
    print("\n  next-trade expectancy conditional on preceding consecutive-loss count:")
    print("   k   n_next   mean_pnl   win_rate   net")
    for k in range(0, 8):
        sel = (streak == k) if k < 7 else (streak >= 7)
        if sel.sum() == 0:
            continue
        lbl = str(k) if k < 7 else "7+"
        print(f"  {lbl:>3} {sel.sum():>7}  {p[sel].mean():>9.3f}  "
              f"{(p[sel] > 0).mean():>8.3f}  {p[sel].sum():>8.1f}")

    # a cleaner version of the same question: everything AT OR ABOVE k
    print("\n  'trades taken while streak >= k' (what a breaker at k would remove):")
    print("   k   n_removed  net_removed  mean   |  n_kept   net_kept")
    for k in range(2, 7):
        sel = streak >= k
        print(f"  {k:>3} {sel.sum():>10} {p[sel].sum():>12.1f} {p[sel].mean() if sel.sum() else 0:>6.2f}"
              f"  | {(~sel).sum():>7} {p[~sel].sum():>10.1f}")

    # --- clustering check: observed run lengths vs i.i.d. expectation ---
    rl = run_lengths(loss)
    q = loss.mean()
    n = len(p)
    print(f"\n  loss-run lengths: observed vs i.i.d. expectation (loss prob q={q:.3f})")
    print("   len  observed  expected(iid)")
    obs = pd.Series(rl).value_counts().sort_index()
    for L in range(1, 13):
        # expected number of maximal runs of exactly length L in n Bernoulli trials
        exp = (n - L + 1) * (q ** L) * ((1 - q) ** 2) if L < n - 1 else 0
        o = int(obs.get(L, 0))
        if o == 0 and exp < 0.5:
            continue
        print(f"  {L:>4} {o:>9} {exp:>14.1f}")
    print(f"  longest observed loss run: {max(rl) if rl else 0}")

    # --- time structure: how long is a streak-triggered pause worth in bars? ---
    gaps = []
    for a, b in zip(trades[:-1], trades[1:]):
        gaps.append(b["entry_i"] - a["exit_i"])
    gaps = np.array(gaps)
    print(f"\n  bars between one exit and the next entry: median={np.median(gaps):.0f} "
          f"mean={gaps.mean():.0f} p90={np.percentile(gaps,90):.0f}")
    hold = np.array([t["exit_i"] - t["entry_i"] for t in trades])
    print(f"  bars held per trade: median={np.median(hold):.0f} mean={hold.mean():.0f}")


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()

    ctx5 = E.build_context(df, h4, E.P)
    report("M5 (v1.46 defaults)", S.simulate(ctx5, params=E.P), ctx5)

    d15 = E.resample_m15_from_m5(df)
    ctx15 = E.build_context(d15, h4, E.P15)
    report("M15 (v1.51 defaults)", S.simulate(ctx15, params=E.P15), ctx15)
