"""
Honest real-data backtest of the uploaded Gold_Stoch_200EMA EA_Script.txt
(2026-10-09) - user asked to "run your tests and fix it" after I reviewed
the code for bugs. The code fixes (scoped position check, spread filter,
min-stop-distance, order-result logging, the rates[1].close compile bug)
are separate from whether the STRATEGY ITSELF has any real edge - this is
a brand-new, never-before-tested-in-this-project candidate, so full rigor
applies: walk-forward split (no tuning - using the script's own stated
default inputs verbatim, K=1), random-timing null with matched trade
count/direction, same real spread cost. Buy-only, matching the real
script's actual (unfixed, by design) structure - no short side invented.

Strategy as coded: close[1] > EMA200[1], Stochastic(21,5,5) %K crosses
above %D on the closed bar with %K < 30, ATR(14)*2.0 stop, 2.5R target,
breakeven once price has moved 100% of initial risk. Entry/exit strictly
on M5 bar close (matches the script's IsNewBar gating), single position
at a time (its own symbol+magic only, per the fix).
"""
import sys

sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E

STOCH_K, STOCH_D, STOCH_SLOW = 21, 5, 5
EMA_PERIOD = 200
ATR_PERIOD = 14
ATR_MULT = 2.0
RR = 2.5
POINT = E.POINT


def ema(arr, period):
    out = np.full(len(arr), np.nan)
    alpha = 2.0 / (period + 1)
    out[period - 1] = np.mean(arr[:period])
    for i in range(period, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def atr(high, low, close, period):
    n = len(close)
    tr = np.zeros(n)
    tr[1:] = np.maximum(high[1:] - low[1:],
                         np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    out = np.full(n, np.nan)
    out[period] = tr[1:period + 1].mean()
    for i in range(period + 1, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def stochastic(high, low, close, k_period, d_period, slow_period):
    n = len(close)
    raw_k = np.full(n, np.nan)
    for i in range(k_period - 1, n):
        hh = high[i - k_period + 1:i + 1].max()
        ll = low[i - k_period + 1:i + 1].min()
        raw_k[i] = 100.0 * (close[i] - ll) / (hh - ll) if hh > ll else 50.0
    k = pd.Series(raw_k).rolling(slow_period).mean().values   # MODE_SMA slowing
    d = pd.Series(k).rolling(d_period).mean().values
    return k, d


def simulate(close, high, low, spread, k, d, ema200, atrv, entry_mask=None):
    n = len(close)
    trades = []
    i = max(EMA_PERIOD, ATR_PERIOD + STOCH_K + STOCH_SLOW + STOCH_D) + 2
    while i < n - 1:
        if entry_mask is not None:
            fire = entry_mask[i]
        else:
            c1, e1, a1 = close[i], ema200[i], atrv[i]
            k1, d1, k0, d0 = k[i], d[i], k[i - 1], d[i - 1]
            fire = (not np.isnan(e1) and not np.isnan(a1) and not np.isnan(k1) and not np.isnan(k0)
                    and c1 > e1 and k0 <= d0 and k1 > d1 and k1 < 30)
        if not fire:
            i += 1
            continue
        fill_i = i + 1
        sc = spread[fill_i] * POINT
        entry_px = close[i] + sc
        sl_dist = atrv[i] * ATR_MULT
        sl = entry_px - sl_dist
        tp = entry_px + sl_dist * RR
        be_armed = False
        exit_i, exit_px, reason = None, None, None
        for kk in range(fill_i, n):
            if not be_armed and (high[kk] - entry_px) >= sl_dist:
                sl = entry_px + 5 * POINT * 10   # breakeven, matches script's buffer
                be_armed = True
            if low[kk] <= sl:
                exit_i, exit_px, reason = kk, sl, ("BE" if be_armed else "SL")
                break
            if high[kk] >= tp:
                exit_i, exit_px, reason = kk, tp, "TP"
                break
        if exit_i is None:
            exit_i, exit_px, reason = n - 1, close[n - 1], "EOD"
        pnl = exit_px - entry_px
        trades.append(dict(entry_i=i, exit_i=exit_i, entry_px=entry_px, exit_px=exit_px,
                            pnl=pnl, pnl_pct=pnl / entry_px, reason=reason))
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
    pnl = np.array([t["pnl_pct"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  %PF={pf(pnl):6.3f}  "
          f"net%={100*pnl.sum():7.2f}  avg%={100*pnl.mean():.4f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    for r, cnt in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


if __name__ == "__main__":
    df = E.load_m5()
    print(f"Real GOLD M5: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({len(df)} bars)")
    close, high, low, spread = df["close"].values, df["high"].values, df["low"].values, df["spread"].values
    n = len(df)
    cutoff_i = int(n * 0.70)
    print(f"Walk-forward cutoff (70%): {df['time'].iloc[cutoff_i]}\n")

    ema200 = ema(close, EMA_PERIOD)
    atrv = atr(high, low, close, ATR_PERIOD)
    k, d = stochastic(high, low, close, STOCH_K, STOCH_D, STOCH_SLOW)

    trades = simulate(close, high, low, spread, k, d, ema200, atrv)
    print(f"{'='*92}\nGold_Stoch_200EMA - script's own default inputs, verbatim, K=1 (no tuning)\n{'='*92}")
    for label, trs in (("IN-SAMPLE (first 70%)", [t for t in trades if t["entry_i"] < cutoff_i]),
                        ("OUT-OF-SAMPLE (last 30%)", [t for t in trades if t["entry_i"] >= cutoff_i]),
                        ("FULL HISTORY", trades)):
        report(label, trs)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws - matched trade count, same real\n"
          f"exit machinery (SL/breakeven/TP/EOD) and spread cost, entries restricted to the\n"
          f"same eligible-bar window\n{'='*92}")
    oos_trades = [t for t in trades if t["entry_i"] >= cutoff_i]
    n_oos = len(oos_trades)
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few for a meaningful null")
    else:
        real_pf = pf([t["pnl_pct"] for t in oos_trades])
        print(f"  real: n={n_oos}, %PF={real_pf:.3f}")
        warmup = max(EMA_PERIOD, ATR_PERIOD + STOCH_K + STOCH_SLOW + STOCH_D) + 2
        eligible = np.arange(max(cutoff_i, warmup), n - 1)
        NDRAWS = 2000
        null_pfs = []
        rng_master = np.random.default_rng(42)
        for seed in range(NDRAWS):
            rng = np.random.default_rng(seed)
            chosen = rng.choice(eligible, size=n_oos, replace=False)
            mask = np.zeros(n, dtype=bool)
            mask[chosen] = True
            ntrades = simulate(close, high, low, spread, k, d, ema200, atrv, entry_mask=mask)
            pnl = [t["pnl_pct"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null %PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real %PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K=1 (script's stated default inputs, no parameter search).")
    print(f"  Structural note: buy-only by the script's own design - no short side exists to test.")
