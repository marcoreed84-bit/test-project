"""
User's exact framing, 2026-10-12: "catching the trend with silver, with
the 21/50ema cross this morning would have been running in profit all
day, still going down, staying below the 21ema" - a detail never
isolated before. Every prior standalone-cross test this session used the
50-EMA as BOTH the entry trigger (half of the cross) AND the trail/exit
reference. This is the one piece not yet tried on its own: same 21/50
cross entry, unchanged, but the trail/exit reference swapped to the
21-EMA (the faster line) instead of the 50-EMA - tighter, more reactive,
matches the user's literal description of "staying below the 21ema" as
the thing that would have kept the trade open/correctly flagged exit.

Direct mirror of ema_cross_trail50_test.py's structure and rigor (same
entry, same clean 2014-2025 Silver window, same real spread, same
walk-forward split, same random-timing null) - only the trail reference
changes. No assumption this does better than the already-rejected
50-EMA version; that's the actual question being asked.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
from aurelius_m15_silver_test import load_m15_silver
from ema_cross_trail50_test import ema, wilder_atr, pf, report, CLEAN_END, SILVER_POINT

TRAIL_BUFFER_ATR = 0.15


def simulate21(close, high, low, spread, m21, m50, atr, entry_mask=None):
    n = len(close)
    trades = []
    sign = np.sign(m21 - m50)
    i = 51
    while i < n - 1:
        if entry_mask is not None:
            fire = i in entry_mask
            d = entry_mask.get(i) if fire else None
        else:
            fire = (not np.isnan(sign[i]) and not np.isnan(sign[i - 1]) and sign[i] != 0
                    and sign[i] != sign[i - 1] and sign[i - 1] != 0)
            d = 1 if sign[i] > 0 else -1
        if not fire:
            i += 1
            continue
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        is_buy = d > 0
        sc = spread[fill_i] * SILVER_POINT
        entry_px = close[i] + sc if is_buy else close[i] - sc
        exit_i, exit_px, reason = None, None, None
        for kk in range(fill_i, n):
            a = atr[kk]
            if np.isnan(m21[kk]) or np.isnan(a) or a <= 0:
                continue
            buf = TRAIL_BUFFER_ATR * a
            c = close[kk]
            broke = (c < m21[kk] - buf) if is_buy else (c > m21[kk] + buf)
            if broke:
                exit_i, exit_px, reason = kk, c, "TRAIL21"
                break
        if exit_i is None:
            exit_i, exit_px, reason = n - 1, close[n - 1], "EOD"
        pnl = (exit_px - entry_px) * (1 if is_buy else -1)
        trades.append(dict(entry_i=i, exit_i=exit_i, pnl=pnl, dir=1 if is_buy else -1, reason=reason))
        i = exit_i + 1
    return trades


if __name__ == "__main__":
    df = load_m15_silver()
    df = df[df["time"] <= CLEAN_END].reset_index(drop=True)
    close, high, low, spread = df["close"].values, df["high"].values, df["low"].values, df["spread"].values
    n = len(df)
    print(f"SILVER M15, clean window only: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")

    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)

    trades = simulate21(close, high, low, spread, m21, m50, atr)
    cutoff_i = int(n * 0.70)
    print(f"{'='*92}\n21/50 EMA cross entry + 21-EMA trail exit (buffer={TRAIL_BUFFER_ATR} ATR), K=1\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", trades)

    print(f"\n{'='*92}\nHold-time check\n{'='*92}")
    bars_held = np.array([t["exit_i"] - t["entry_i"] for t in trades])
    hours_held = bars_held * 15 / 60.0
    print(f"  median hold: {np.median(hours_held):.2f}h   mean: {hours_held.mean():.2f}h   "
          f"p90: {np.percentile(hours_held,90):.2f}h   max: {hours_held.max():.2f}h")

    print(f"\n{'='*92}\nDirect comparison vs already-rejected 50-EMA trail version (same entries)\n{'='*92}")
    from ema_cross_trail50_test import simulate as simulate50
    trades50 = simulate50(close, high, low, spread, m21, m50, atr)
    report("50-EMA trail - FULL HISTORY", trades50)
    report("21-EMA trail - FULL HISTORY", trades)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws - matched trade count/direction,\n"
          f"SAME trail-21 exit machinery and real spread\n{'='*92}")
    oos_trades = [t for t in trades if t["entry_i"] >= cutoff_i]
    n_oos = len(oos_trades)
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few for a meaningful null")
    else:
        real_pf = pf([t["pnl"] for t in oos_trades])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}")
        dirs = [t["dir"] for t in oos_trades]
        eligible = np.arange(cutoff_i + 1, n - 1)
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            rng = np.random.default_rng(seed)
            chosen = rng.choice(eligible, size=n_oos, replace=False)
            order = rng.permutation(n_oos)
            bar_to_dir = {int(b): dirs[o] for b, o in zip(chosen, order)}
            ntrades = simulate21(close, high, low, spread, m21, m50, atr, entry_mask=bar_to_dir)
            ntrades = [t for t in ntrades if t["entry_i"] in bar_to_dir]
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null PF: median={np.median(null_pfs):.3f}  p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")
