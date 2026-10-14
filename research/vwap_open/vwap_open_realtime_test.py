"""
Corrected, real-time-valid version of Pattern 1 ("clean break") from
vwap_open_scenarios_test.py. Two things fixed after the user caught a real
flaw in the first pass:

1. ENTRY unchanged and was always causal/real-time-valid: the first bar
   where price, 21-EMA and 50-EMA are ALL beyond buffer*ATR on the same
   side of session VWAP, after having started the session clustered near
   it. Nothing here required future information.

2. EXIT was the actual problem. The first version used "price never closes
   back through VWAP for the rest of the session" as a FILTER on which
   commitment-crosses counted as trades at all - that's lookahead, since in
   live trading you can't know in advance whether a break will hold. Fixed:
   every commitment-cross is now taken as a trade. The hold-then-see-if-it-
   was-good approach is replaced with a real exit rule evaluated bar by bar
   after entry: close on the 6-hour time limit, OR immediately if price
   closes back through the 50-EMA (not VWAP - VWAP is a noisy running
   average price oscillates through constantly; the 50-EMA was already
   established earlier this session as the more stable trail/exit
   reference between the two, found directly, not assumed).

Same real GOLD_M15_native.csv, same clean 2014-06-13 window, real spread,
same IS/OOS split and grid search discipline as the original file.
"""
import numpy as np
import pandas as pd
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, session_vwap, WINDOW_BARS, HOLD_BARS, GOLD_POINT


def classify_and_test_realtime(df, cluster_atr_mult, buffer_atr_mult, point=GOLD_POINT):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)

    day = df["time"].dt.date.values
    n = len(df)

    day_start_idx = {}
    for i in range(n):
        if day[i] not in day_start_idx:
            day_start_idx[day[i]] = i

    results = []
    for d, start_i in day_start_idx.items():
        end_i = min(start_i + WINDOW_BARS, n)
        if end_i - start_i < 10:
            continue
        cluster_i = None
        for i in range(start_i, end_i):
            if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(vwap[i]) or np.isnan(m21[i]) or np.isnan(m50[i]):
                continue
            tol = cluster_atr_mult * atr[i]
            if (abs(close[i] - vwap[i]) <= tol and abs(m21[i] - vwap[i]) <= tol
                    and abs(m50[i] - vwap[i]) <= tol):
                cluster_i = i
                break
        if cluster_i is None:
            continue

        resolve_i, direction = None, None
        for i in range(cluster_i + 1, end_i):
            if np.isnan(atr[i]) or atr[i] <= 0:
                continue
            buf = buffer_atr_mult * atr[i]
            above = (close[i] > vwap[i] + buf and m21[i] > vwap[i] + buf and m50[i] > vwap[i] + buf)
            below = (close[i] < vwap[i] - buf and m21[i] < vwap[i] - buf and m50[i] < vwap[i] - buf)
            if above or below:
                resolve_i, direction = i, (1 if above else -1)
                break
        if resolve_i is None:
            continue

        # entry fills at the NEXT bar's open-equivalent (we only have OHLC,
        # so use next bar's close + spread, same convention as the rest of
        # this project's simpler research scripts)
        fill_i = resolve_i + 1
        if fill_i >= n:
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)

        # real-time exit: walk forward bar by bar, stop on 50-EMA close-back
        # or the time limit, whichever comes first
        exit_i, exit_px, reason = None, None, None
        hard_limit = min(fill_i + HOLD_BARS, n - 1)
        for j in range(fill_i, hard_limit + 1):
            if np.isnan(m50[j]):
                continue
            broke = (close[j] < m50[j]) if direction > 0 else (close[j] > m50[j])
            if broke:
                exit_i, exit_px, reason = j, close[j], "EMA50"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(day=d, entry_i=resolve_i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction, reason=reason))

    return results


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results):
    if not results:
        print(f"  {label}: n=0")
        return
    arr = np.array([r["pnl_pct"] for r in results])
    reasons = {}
    for r in results:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    rtxt = ", ".join(f"{k}:{v}" for k, v in reasons.items())
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  "
          f"%PF={pct_pf(results):6.3f}  net%={100*arr.sum():7.2f}  avg%={100*arr.mean():6.3f}  [{rtxt}]")


if __name__ == "__main__":
    df = load_gold_m15()
    n = len(df)
    print(f"GOLD M15 real: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)

    print(f"{'='*100}\nIN-SAMPLE grid search (real-time entry, 50-EMA/time exit)\n{'='*100}")
    grid = []
    for cluster_m in (0.3, 0.5, 0.7):
        for buf_m in (0.15, 0.25):
            res = classify_and_test_realtime(df_is, cluster_m, buf_m)
            net = sum(r["pnl_pct"] for r in res) if res else -999
            grid.append((cluster_m, buf_m, len(res), net, pct_pf(res)))
            print(f"  cluster={cluster_m} buf={buf_m}:  n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}")

    best = max(grid, key=lambda g: g[3])
    print(f"\n  IS winner: cluster={best[0]} buf={best[1]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oos_res = classify_and_test_realtime(df_oos, best[0], best[1])
    report("Real-time Pattern 1 - OOS", oos_res)

    full_res = classify_and_test_realtime(df, best[0], best[1])
    report("Real-time Pattern 1 - FULL", full_res)
