"""
NEW STANDALONE CANDIDATE (2026-10-05, user's own idea, following the
stochastic_time_of_day_analysis.py descriptive finding): a continuation bet
on real GOLD M5 - buy a fresh overbought cross, sell a fresh oversold
cross, but ONLY during the hours-of-day the descriptive analysis flagged
as high-dwell-time hours (i.e. hours where an extreme tends to persist
rather than immediately mean-revert).

WALK-FORWARD DISCIPLINE (done correctly this time - this project already
caught itself picking a regime threshold using data that included the test
half once before, 2026-10-04's Vanguard low-vol-regime attempt, and that
invalidated the result): the "favorable hours" are chosen using ONLY the
in-sample 70% of the data, then FROZEN before touching the out-of-sample
30% at all. The OOS number is the one that counts; IS is reported only for
transparency, never as the verdict.

Construction (fixed a priori, no threshold sweep - honest K=1):
  - Stochastic: Ratchet's own K=5/slowing=3/D=3 (bars.mt5_stoch_signal).
  - Hour gate: top 6 of 24 hours (a plain pre-specified quartile, not
    cherry-picked post-hoc) by IS-only OB-dwell-rate for buys, OS-dwell-
    rate for sells.
  - Entry: a FRESH cross into OB (>=80) during a gated buy-hour -> buy; a
    FRESH cross into OS (<=20) during a gated sell-hour -> sell. "Fresh"
    = main crossed the threshold this bar, not just sitting past it
    already (one entry per excursion, not re-entering every bar while
    still extended).
  - Stop: entry -/+ 2.0xATR against the trade (a plain, un-tuned round
    default - this project's typical sane starting point, not swept).
  - Exit (continuation thesis invalidated): close when the oscillator
    crosses back through the 50 midline against the trade, or the stop,
    whichever comes first. A max-bars safety cap (200 bars, ~16.7h) stops
    a pathological hang; it is a safety cap, not a tuned exit rule.
  - Real spread cost from the data, same GOLD M5 POINT as every other
    script in this project.
"""
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B  # noqa: E402

POINT = B.POINT
ATR_STOP = 2.0
HOUR_QUARTILE = 6   # top 6 of 24 hours - a plain pre-specified fraction
MAX_BARS = 200


def wilder_atr(h, l, c, period=14):
    return B.wilder_atr(h, l, c, period)


def pick_favorable_hours(hour, ob, os_, n=HOUR_QUARTILE):
    """IS-only: top n hours by OB-dwell rate (for buys), top n by OS-dwell
    rate (for sells). Computed ONCE on in-sample data, then frozen."""
    df = pd.DataFrame(dict(hour=hour, ob=ob, os=os_))
    rates = df.groupby("hour").mean()
    buy_hours = set(rates["ob"].sort_values(ascending=False).head(n).index.tolist())
    sell_hours = set(rates["os"].sort_values(ascending=False).head(n).index.tolist())
    return buy_hours, sell_hours


def simulate(df, main, atr, buy_hours, sell_hours, start_i, end_i, entry_mask=None, entry_dirs=None):
    """entry_mask/entry_dirs: optional override for the random-timing null
    (bar indices -> direction), bypassing the real signal but reusing the
    SAME exit machinery (ATR stop, 50-midline-cross exit, real spread)."""
    o, h, l, c, sp_pts = df["open"].values, df["high"].values, df["low"].values, df["close"].values, df["spread"].values
    hour = df["time"].dt.hour.values
    trades = []
    pos = None
    for t in range(start_i, end_i):
        sp = sp_pts[t] * POINT
        if pos is not None:
            d = pos["dir"]
            hit_sl = (l[t] <= pos["sl"]) if d > 0 else (h[t] + sp >= pos["sl"])
            if hit_sl:
                px = pos["sl"]
                trades.append(dict(entry_i=pos["entry_i"], dir=d, entry=pos["entry"], exit=px,
                                    pnl=(px - pos["entry"]) * d, reason="SL"))
                pos = None
                continue
            faded = (main[t] <= 50.0) if d > 0 else (main[t] >= 50.0)
            timed_out = (t - pos["entry_i"]) >= MAX_BARS
            if faded or timed_out:
                px = o[t] if d > 0 else o[t] + sp
                trades.append(dict(entry_i=pos["entry_i"], dir=d, entry=pos["entry"], exit=px,
                                    pnl=(px - pos["entry"]) * d, reason="FADE" if faded else "TIMEOUT"))
                pos = None
                continue
        if pos is None:
            a = atr[t - 1]
            if not (a > 0):
                continue
            if entry_mask is not None:
                d = entry_dirs.get(t, 0)
                if d == 0:
                    continue
            else:
                s = t - 1
                fresh_ob = main[s] >= 80.0 and main[s - 1] < 80.0
                fresh_os = main[s] <= 20.0 and main[s - 1] > 20.0
                if fresh_ob and hour[t] in buy_hours:
                    d = 1
                elif fresh_os and hour[t] in sell_hours:
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


def random_entry_matched(hour, start_i, end_i, n_target, long_frac, seed):
    rng = np.random.default_rng(seed)
    eligible = np.arange(start_i + 1, end_i)
    chosen = rng.choice(eligible, size=min(n_target, len(eligible)), replace=False)
    return {int(t): (1 if rng.random() < long_frac else -1) for t in chosen}


if __name__ == "__main__":
    m5 = B.load_m5()
    h, l, c = m5["high"].values, m5["low"].values, m5["close"].values
    main, _ = B.mt5_stoch_signal(h, l, c, 5, 3, 3)
    atr = wilder_atr(h, l, c, 14)
    hour_all = m5["time"].dt.hour.values
    n_bars = len(m5)
    cutoff = int(n_bars * 0.70)
    cutoff_time = m5["time"].iloc[cutoff]
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {cutoff_time}")

    valid = ~np.isnan(main)
    is_mask = valid & (np.arange(n_bars) < cutoff)
    ob_is = main[is_mask] >= 80.0
    os_is = main[is_mask] <= 20.0
    buy_hours, sell_hours = pick_favorable_hours(hour_all[is_mask], ob_is, os_is)
    print(f"\nFavorable hours picked from IN-SAMPLE ONLY (frozen before touching OOS):")
    print(f"  buy_hours (top {HOUR_QUARTILE} by IS OB-dwell rate):  {sorted(buy_hours)}")
    print(f"  sell_hours (top {HOUR_QUARTILE} by IS OS-dwell rate): {sorted(sell_hours)}")

    print(f"\n{'='*92}\nIN-SAMPLE (first 70%) - reported for transparency only, NOT the verdict\n{'='*92}")
    is_trades = simulate(m5, main, atr, buy_hours, sell_hours, 20, cutoff)
    report("time-gated continuation", is_trades)

    print(f"\n{'='*92}\nOUT-OF-SAMPLE (last 30%, genuinely untouched) - this is the verdict\n{'='*92}")
    oos_trades = simulate(m5, main, atr, buy_hours, sell_hours, cutoff, n_bars)
    report("time-gated continuation", oos_trades)
    n_oos = len(oos_trades)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only): same exits/stop/spread, entry count matched,")
    print(f"entries placed uniformly at random in the OOS window (2000 draws)")
    print(f"{'='*92}")
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few to run a meaningful null")
    else:
        real_pf = pf([t["pnl"] for t in oos_trades])
        long_frac = np.mean([t["dir"] > 0 for t in oos_trades])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}, long_frac={long_frac:.2f}")
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            dirs = random_entry_matched(hour_all, cutoff, n_bars, n_oos, long_frac, seed)
            ntrades = simulate(m5, main, atr, buy_hours, sell_hours, cutoff, n_bars,
                                entry_mask=True, entry_dirs=dirs)
            pnl = np.array([t["pnl"] for t in ntrades])
            null_pfs.append(pf(pnl) if len(pnl) else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value (P[null PF >= real PF]) = {p_value:.4f}  "
              f"{'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K for this idea: 1 (fixed hour-quartile/stop/exit, no sweep run).")
