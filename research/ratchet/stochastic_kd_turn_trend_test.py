"""
NEW CANDIDATE (2026-10-05, user's own idea, single construction, own
K=1 - distinct from stochastic_timegate_search.py's K=40 grid, which is
a separate, unrelated in-flight test): trend-filtered Stochastic %K/%D
turn in the extreme zone.

  - Trend: close vs the 150-EMA (Ratchet's own InpP150 period, reused for
    consistency, not a new free choice) - uptrend if close > ema150,
    downtrend if close < ema150. Buys only in an uptrend, sells only in a
    downtrend.
  - Setup: %K must have touched oversold (<=20) within the last
    SETUP_LOOKBACK=10 bars for a buy setup (mirror: overbought >=80 for a
    sell setup) - this is the "coming FROM oversold/overbought" part.
  - Trigger: %K comes near or touches its OWN %D line (|%K-%D| <=
    TOUCH_TOL=3 points - %D is literally a moving average of %K in MT5's
    Stochastic, so "near a moving average" = near %D) while still turning
    back toward the trend direction (%K[s] > %K[s-1] for a buy, < for a
    sell) - this is the "touching a moving average and turning" part.
  - Target: ride the move through to the OPPOSITE extreme (>=80 for a
    buy, <=20 for a sell) - completing the stated "oversold to
    overbought" swing. ATR stop (2.0x, this project's plain round
    default) protects against it not completing; 200-bar timeout is a
    safety cap, not a tuned exit.

Single, fully pre-specified construction - no threshold sweep run.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B  # noqa: E402

POINT = B.POINT
ATR_STOP = 2.0
SETUP_LOOKBACK = 10
TOUCH_TOL = 3.0
MAX_BARS = 200


def simulate(df, main, sig, ema150, atr, start_i, end_i, entry_dirs=None):
    o, h, l, sp_pts = df["open"].values, df["high"].values, df["low"].values, df["spread"].values
    c = df["close"].values
    n = len(df)
    trades = []
    pos = None
    was_os = pd.Series(main <= 20.0).rolling(SETUP_LOOKBACK, min_periods=1).max().values.astype(bool)
    was_ob = pd.Series(main >= 80.0).rolling(SETUP_LOOKBACK, min_periods=1).max().values.astype(bool)
    for t in range(start_i, end_i):
        sp = sp_pts[t] * POINT
        if pos is not None:
            d = pos["dir"]
            hit_sl = (l[t] <= pos["sl"]) if d > 0 else (h[t] + sp >= pos["sl"])
            if hit_sl:
                px = pos["sl"]
                trades.append(dict(entry_i=pos["entry_i"], dir=d, pnl=(px - pos["entry"]) * d, reason="SL"))
                pos = None
                continue
            reached = (main[t] >= 80.0) if d > 0 else (main[t] <= 20.0)
            timed_out = (t - pos["entry_i"]) >= MAX_BARS
            if reached or timed_out:
                px = o[t] if d > 0 else o[t] + sp
                trades.append(dict(entry_i=pos["entry_i"], dir=d, pnl=(px - pos["entry"]) * d,
                                    reason="TARGET" if reached else "TIMEOUT"))
                pos = None
                continue
        if pos is None:
            a = atr[t - 1]
            if not (a > 0):
                continue
            if entry_dirs is not None:
                d = entry_dirs.get(t, 0)
                if d == 0:
                    continue
            else:
                s = t - 1
                if s < 1 or np.isnan(ema150[s]):
                    continue
                uptrend = c[s] > ema150[s]
                downtrend = c[s] < ema150[s]
                near_d = abs(main[s] - sig[s]) <= TOUCH_TOL
                turning_up = main[s] > main[s - 1]
                turning_down = main[s] < main[s - 1]
                if uptrend and was_os[s] and near_d and turning_up:
                    d = 1
                elif downtrend and was_ob[s] and near_d and turning_down:
                    d = -1
                else:
                    continue
            entry = o[t] + sp if d > 0 else o[t]
            sl = entry - d * ATR_STOP * a
            pos = dict(entry_i=t, dir=d, entry=entry, sl=sl)
    return trades


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
    for r in ("TARGET", "SL", "TIMEOUT"):
        cnt = sum(1 for t in trades if t["reason"] == r)
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


def random_entry_matched(start_i, end_i, n_target, long_frac, seed):
    rng = np.random.default_rng(seed)
    eligible = np.arange(start_i + 1, end_i)
    chosen = rng.choice(eligible, size=min(n_target, len(eligible)), replace=False)
    return {int(t): (1 if rng.random() < long_frac else -1) for t in chosen}


if __name__ == "__main__":
    m5 = B.load_m5()
    h, l, c = m5["high"].values, m5["low"].values, m5["close"].values
    main, sig = B.mt5_stoch_signal(h, l, c, 5, 3, 3)
    atr = B.wilder_atr(h, l, c, 14)
    ema150 = B.ema(c, 150)
    n_bars = len(m5)
    cutoff = int(n_bars * 0.70)
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {m5['time'].iloc[cutoff]}")
    print(f"Construction: trend(150EMA)-filtered, %K touches %D (tol={TOUCH_TOL}) after recent "
          f"{SETUP_LOOKBACK}-bar OS/OB, turning, target = opposite extreme, stop={ATR_STOP}xATR")

    print(f"\n{'='*92}\nIN-SAMPLE (first 70%) - transparency only\n{'='*92}")
    is_trades = simulate(m5, main, sig, ema150, atr, 160, cutoff)
    report("trend+K/D-turn", is_trades)

    print(f"\n{'='*92}\nOUT-OF-SAMPLE (last 30%, untouched) - this is the verdict\n{'='*92}")
    oos_trades = simulate(m5, main, sig, ema150, atr, cutoff, n_bars)
    report("trend+K/D-turn", oos_trades)
    n_oos = len(oos_trades)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws\n{'='*92}")
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few to run a meaningful null")
    else:
        real_pf = pf([t["pnl"] for t in oos_trades])
        long_frac = np.mean([t["dir"] > 0 for t in oos_trades])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}, long_frac={long_frac:.2f}")
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            dirs = random_entry_matched(cutoff, n_bars, n_oos, long_frac, seed)
            ntrades = simulate(m5, main, sig, ema150, atr, cutoff, n_bars, entry_dirs=dirs)
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K for this idea: 1 (single pre-specified construction, no sweep run).")
