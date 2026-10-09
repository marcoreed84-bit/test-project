"""
NEW CANDIDATE (2026-10-09, user's own platform observation): on Aurelius
M5, a max-spread filter of 55 "tests better" than 60 - less drawdown.
sim.py already HAS a max_spread_points filter built in, defaulting to 60
via p.get("max_spread_points", 60) when the key isn't set in params (and
E.P does NOT set it, confirmed - so 60 is the real current shipped
behavior, not a theoretical default). This tests 55 vs the real shipped
60, honestly: walk-forward split, random-timing null, AND max drawdown
(the specific metric the user is citing), since "less drawdown" on its
own needs the same scrutiny as any other filter claim tonight.
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


def max_drawdown(pnl):
    equity = np.cumsum(pnl)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    return dd.max() if len(dd) else 0.0


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  max_dd={max_drawdown(pnl):8.2f}")


def random_timing_null(ctx, params, trades, start_i, end_i, ndraws=2000):
    dirs = [t["dir"] for t in trades]
    n_real = len(dirs)
    if n_real < 5:
        return None
    pnl_real = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades])
    real_pf = pf(pnl_real)
    eligible = np.arange(start_i + 1, end_i)
    null_pfs = []
    for seed in range(ndraws):
        rng = np.random.default_rng(seed)
        chosen = rng.choice(eligible, size=n_real, replace=False)
        order = rng.permutation(n_real)
        bar_to_dir = {int(b): dirs[o] for b, o in zip(chosen, order)}

        def entry_fn(ctx_, i, bar_to_dir=bar_to_dir):
            return bar_to_dir.get(i, 0)
        ntrades = S.simulate(ctx, params=params, entry_fn=entry_fn, start_i=start_i, end_i=end_i)
        pnl = [(t["exit_px"] - t["entry_px"]) * t["dir"] for t in ntrades]
        null_pfs.append(pf(pnl) if pnl else 0.0)
    null_pfs = np.array(null_pfs)
    p_value = (null_pfs >= real_pf).mean()
    pct = 100 * (null_pfs < real_pf).mean()
    return real_pf, null_pfs, p_value, pct


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    print(f"Real GOLD M5: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({len(df)} bars)")
    ctx = E.build_context(df, h4, E.P)
    n_bars = len(df)
    cutoff_i = int(n_bars * 0.70)
    print(f"Walk-forward cutoff (70%): {df['time'].iloc[cutoff_i]}\n")

    for max_spread in (60, 55):
        label = f"max_spread_points={max_spread}" + ("  (current shipped default)" if max_spread == 60 else "")
        params = dict(E.P, max_spread_points=max_spread)
        trades = S.simulate(ctx, params=params)
        print(f"{'='*92}\n{label}\n{'='*92}")
        is_trades = [t for t in trades if t["entry_i"] < cutoff_i]
        oos_trades = [t for t in trades if t["entry_i"] >= cutoff_i]
        report("IN-SAMPLE (first 70%)", is_trades)
        report("OUT-OF-SAMPLE (last 30%)", oos_trades)
        report("FULL HISTORY", trades)
        print()

    print(f"{'='*92}\nRANDOM-TIMING NULLS (OOS only), 2000 draws each - matched trade count/direction,\n"
          f"same real exit machinery, same max_spread_points filter applied to null draws too\n{'='*92}")
    for max_spread in (60, 55):
        params = dict(E.P, max_spread_points=max_spread)
        trades = S.simulate(ctx, params=params)
        oos_trades = [t for t in trades if t["entry_i"] >= cutoff_i]
        result = random_timing_null(ctx, params, oos_trades, cutoff_i, n_bars - 1)
        if result is None:
            print(f"  max_spread_points={max_spread}: too few OOS trades")
            continue
        real_pf, null_pfs, p_value, pct = result
        print(f"  max_spread_points={max_spread}: real PF={real_pf:.3f}  null median={np.median(null_pfs):.3f}  "
              f"percentile={pct:.1f}th  p={p_value:.4f}  {'[SURVIVES]' if p_value < 0.05 else '[does not beat random]'}")

    print(f"\n  Honest K=1 for this specific comparison (55 vs the current shipped 60, user-specified).")
