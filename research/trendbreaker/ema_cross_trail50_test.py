"""
NEW CANDIDATE (2026-10-12, user's own chart observation): a pure 21/50 EMA
cross entry, with NO fixed target - just trail the exit under/over the
50-EMA (checked on CLOSE, not the wick, same tolerance-buffer convention
used throughout this project) until price genuinely closes back through
it. User's framing: "the first circle they cross, price went up for
hours, if trailing tp under the 50ema, trade would have closed way up top
relative to the time [price] obviously crossed again to cross again and
come down" - i.e. a pure trend-following exit should capture much more of
an extended move than whatever a pattern-specific system's own exit does.

This is a brand-new, standalone construction (not a modification of H&S
or Aurelius - just the 21/50 cross + 50-EMA trail concept on its own),
tested with full rigor since nothing about it has been validated before:
real spread, walk-forward split, random-timing null. Restricted to the
CLEAN 2014-2025 window (the 2026 portion of this project's own
SILVER_M15_native.csv was found earlier tonight to have a severe
data-quality problem - 328 bars with >2% single-bar range in 9 months vs
29 in all of 2025).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from aurelius_m15_silver_test import load_m15_silver

CLEAN_END = pd.Timestamp("2025-12-31")
TRAIL_BUFFER_ATR = 0.15
SILVER_POINT = 0.001


def ema(arr, period):
    out = np.full(len(arr), np.nan)
    alpha = 2.0 / (period + 1)
    out[period - 1] = np.mean(arr[:period])
    for i in range(period, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def wilder_atr(h, l, c, n=14):
    tr = np.zeros(len(c))
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    out = np.full(len(c), np.nan)
    out[n] = tr[1:n + 1].mean()
    for i in range(n + 1, len(c)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def simulate(close, high, low, spread, m21, m50, atr, entry_mask=None):
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
            if np.isnan(m50[kk]) or np.isnan(a) or a <= 0:
                continue
            buf = TRAIL_BUFFER_ATR * a
            c = close[kk]
            broke = (c < m50[kk] - buf) if is_buy else (c > m50[kk] + buf)
            if broke:
                exit_i, exit_px, reason = kk, c, "TRAIL50"
                break
        if exit_i is None:
            exit_i, exit_px, reason = n - 1, close[n - 1], "EOD"
        pnl = (exit_px - entry_px) * (1 if is_buy else -1)
        trades.append(dict(entry_i=i, exit_i=exit_i, pnl=pnl, dir=1 if is_buy else -1, reason=reason))
        i = exit_i + 1
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
          f"net={pnl.sum():9.3f}  avg={pnl.mean():7.4f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    for r, cnt in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


if __name__ == "__main__":
    df = load_m15_silver()
    df = df[df["time"] <= CLEAN_END].reset_index(drop=True)
    close, high, low, spread = df["close"].values, df["high"].values, df["low"].values, df["spread"].values
    n = len(df)
    print(f"SILVER M15, clean window only: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")

    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)

    trades = simulate(close, high, low, spread, m21, m50, atr)
    cutoff_i = int(n * 0.70)
    print(f"{'='*92}\n21/50 EMA cross entry + pure 50-EMA trail exit (buffer={TRAIL_BUFFER_ATR} ATR), K=1\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", trades)

    print(f"\n{'='*92}\nHold-time check (does this actually let winners run for hours, as observed?)\n{'='*92}")
    bars_held = np.array([t["exit_i"] - t["entry_i"] for t in trades])
    hours_held = bars_held * 15 / 60.0
    print(f"  median hold: {np.median(hours_held):.2f}h   mean: {hours_held.mean():.2f}h   "
          f"p90: {np.percentile(hours_held,90):.2f}h   max: {hours_held.max():.2f}h")

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws - matched trade count/direction,\n"
          f"SAME trail-50 exit machinery and real spread\n{'='*92}")
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
            ntrades = simulate(close, high, low, spread, m21, m50, atr, entry_mask=bar_to_dir)
            # restrict null trades to only those whose entry bar was chosen (direction override)
            ntrades = [t for t in ntrades if t["entry_i"] in bar_to_dir]
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null PF: median={np.median(null_pfs):.3f}  p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")
