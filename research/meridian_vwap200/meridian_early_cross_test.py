"""
Final, most specific construction per direct clarification of what
Meridian's live code gets wrong: it currently buys when the 21/50 cross
happens ABOVE VWAP (already overextended by then). The better entries
happen when the cross itself occurs BELOW VWAP (for buys - mirrored above
VWAP for sells), catching the move near its start - specifically in the
first couple hours of the session, while the MAs are still clustered
close to VWAP (not yet stretched away from it).

Entry (causal, no lookahead):
  - Within early_window_bars of the session's first bar (the "first couple
    hours" window, same local-midnight VWAP reset convention as the rest
    of this project).
  - At the cross bar: 21-EMA crosses 50-EMA, AND both MAs are within
    cluster_atr_mult*ATR of VWAP (still close to it, not overextended).
  - BUY: cross is 21-up-through-50, with both MAs below VWAP at that bar.
  - SELL: cross is 21-down-through-50, with both MAs above VWAP at that bar.
  - Entry fills the NEXT bar after the cross - no waiting for any later
    VWAP break confirmation, per direct correction that the cross itself
    (while still below/above VWAP) is the trigger, not a later event.

Exit: 50-EMA close-back (the one exit that showed a real, if not-yet-
K-survived, signal tonight) - tested here as the primary exit since it's
parameter-free. ATR trailing stop included as a reference comparison.

Tested on BOTH Gold and Silver M15, per direct instruction - separate
point sizes read from each CSV's own header (never hardcoded, per this
project's established convention), Gold's clean-data filter applied
(>=2014-06-13), Silver uses its full history (no contamination issue).

New construction - honest K tracked independently, starting fresh.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema, wilder_atr, session_vwap

TIME_CAP_BARS = 200
#--- committed into the repo (research/data/) after a container restart twice
#--- wiped the old /tmp scratchpad copy - see the "Commit GOLD M5/M15 market
#--- data into the repo" commit. Relative to this file so it works from any
#--- checkout path, not just this one container's.
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_m15(symbol):
    path = os.path.join(DATA_DIR, f"{symbol}_M15_native.csv")
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    if symbol == "GOLD":
        df = df[df["time"] >= pd.Timestamp("2014-06-13")].reset_index(drop=True)
    return df.reset_index(drop=True), point


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results, n_days=None, split_dir=False):
    if not results:
        print(f"  {label}: n=0")
        return
    arr = np.array([r["pnl_pct"] for r in results])
    holds = np.array([r["hold_bars"] for r in results]) * 0.25
    reasons = {}
    for r in results:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    rtxt = ", ".join(f"{k}:{v}" for k, v in reasons.items())
    pm = f"  (~{len(results)/(n_days/30.44):.1f}/mo)" if n_days else ""
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  %PF={pct_pf(results):6.3f}  "
          f"net%={100*arr.sum():7.2f}  avg_hold={holds.mean():5.1f}h  [{rtxt}]{pm}")
    if split_dir:
        longs = [r for r in results if r["dir"] > 0]
        shorts = [r for r in results if r["dir"] < 0]
        report("    -> LONGS only", longs, n_days)
        report("    -> SHORTS only", shorts, n_days)


def classify_early_cross(df, point, early_window_bars, cluster_atr_mult, exit_mode, trail_atr_mult=2.0):
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
        end_i = min(start_i + early_window_bars, n)
        if end_i - start_i < 5:
            continue
        for i in range(max(start_i + 1, 60), end_i):
            if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(vwap[i]) or np.isnan(atr[i]) or atr[i] <= 0
                    or np.isnan(m21[i - 1]) or np.isnan(m50[i - 1])):
                continue
            tol = cluster_atr_mult * atr[i]
            clustered = abs(m21[i] - vwap[i]) <= tol and abs(m50[i] - vwap[i]) <= tol
            if not clustered:
                continue
            cross_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
            cross_down = m21[i - 1] >= m50[i - 1] and m21[i] < m50[i]
            direction = 0
            if cross_up and m21[i] < vwap[i] and m50[i] < vwap[i]:
                direction = 1
            elif cross_down and m21[i] > vwap[i] and m50[i] > vwap[i]:
                direction = -1
            if direction == 0:
                continue

            fill_i = i + 1
            if fill_i >= n or np.isnan(atr[fill_i]) or atr[fill_i] <= 0:
                continue
            sc = spread[fill_i] * point
            entry_px = close[fill_i] + (sc if direction > 0 else -sc)
            hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

            exit_i, exit_px, reason = None, None, None
            if exit_mode == "ema50":
                for k in range(fill_i + 1, hard_limit + 1):
                    if np.isnan(m50[k]):
                        continue
                    broke = (close[k] < m50[k]) if direction > 0 else (close[k] > m50[k])
                    if broke:
                        exit_i, exit_px, reason = k, close[k], "EMA50"
                        break
            else:  # trail
                best = entry_px
                for k in range(fill_i, hard_limit + 1):
                    if np.isnan(atr[k]) or atr[k] <= 0:
                        continue
                    if direction > 0:
                        if close[k] > best:
                            best = close[k]
                        trail = best - trail_atr_mult * atr[k]
                        if low[k] <= trail and k > fill_i:
                            exit_i, exit_px, reason = k, trail, "TRAIL"
                            break
                    else:
                        if close[k] < best:
                            best = close[k]
                        trail = best + trail_atr_mult * atr[k]
                        if high[k] >= trail and k > fill_i:
                            exit_i, exit_px, reason = k, trail, "TRAIL"
                            break
            if exit_i is None:
                exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

            pnl_pct = ((exit_px - entry_px) / entry_px) * direction
            results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                                 reason=reason, hold_bars=exit_i - fill_i))
    return results


def run_symbol(symbol):
    df, point = load_m15(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} M15 - early-session cross below/above VWAP, MAs clustered close to VWAP\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})\n")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    print(f"{'='*100}\nIN-SAMPLE grid (EMA50 exit, parameter-free - only entry params searched)\n{'='*100}")
    grid = []
    for window_b in (8, 12, 16):
        for cluster_m in (0.3, 0.5, 0.7):
            res = classify_early_cross(df_is, point, window_b, cluster_m, "ema50")
            net = sum(r["pnl_pct"] for r in res) if res else -999
            grid.append((window_b, cluster_m, len(res), net, pct_pf(res)))
            print(f"  window={window_b*0.25:.0f}h cluster={cluster_m}:  n={len(res):4d}  net%={100*net:7.2f}  "
                  f"PF={pct_pf(res):5.2f}  ~{len(res)/(is_days/30.44):.1f}/mo", flush=True)

    best = max(grid, key=lambda g: g[3])
    print(f"\n  IS winner: window={best[0]*0.25:.0f}h cluster={best[1]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation (pooled, then split long/short)\n{'='*100}")
    oos_res = classify_early_cross(df_oos, point, best[0], best[1], "ema50")
    report(f"{symbol} - OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_early_cross(df, point, best[0], best[1], "ema50")
    report(f"{symbol} - FULL", full_res, full_days, split_dir=True)
    return best, grid


if __name__ == "__main__":
    bestG, gridG = run_symbol("GOLD")
    bestS, gridS = run_symbol("SILVER")

    print(f"\n\n  Honest K note: GOLD searched {len(gridG)} combinations, SILVER searched {len(gridS)}.")
    print(f"  New construction - tracked independently from everything else tonight.")
