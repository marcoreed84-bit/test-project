"""
Combines the two most promising signals from the exploratory scan, both
consistent with the user's own standing observation that overextended
crosses (ones happening after the day has already moved) are the bad
ones, not the good ones:

  1. Only the FIRST 21/50 cross of the day (later crosses on the same day
     averaged worse forward returns in the exploratory scan).
  2. Only when the day hasn't already moved far in that direction before
     the cross (day_directionality / day_open_to_cross_pct both showed
     the LAST quintile - crosses after a big pre-move - as the worst
     performers).

Entry: first cross of the day, with net move so far today (direction-
signed) capped below max_premove_atr (in ATR units, causal). Exit: 50-EMA
close-back (same parameter-free exit used throughout tonight). Real
spread, real fills.

Cross-instrument check done FROM THE START this time (both Gold and
Silver tested together, not as an afterthought) - per the hard lesson
from the H4-alignment result, which looked excellent on Gold alone and
then failed badly on Silver.

Honest K tracked independently, starting fresh for this file.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema, wilder_atr
from meridian_early_cross_test import load_m15

TIME_CAP_BARS = 200


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


def classify_first_cross(df, point, max_premove_atr):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)
    day = df["time"].dt.date.values
    n = len(df)

    day_start_idx = {}
    for i in range(n):
        if day[i] not in day_start_idx:
            day_start_idx[day[i]] = i

    results = []
    for d, start_i in day_start_idx.items():
        end_i = n
        day_open_px = close[start_i]
        found_first = False
        for i in range(max(start_i + 1, 60), n):
            if day[i] != d:
                break
            if found_first:
                break
            if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(atr[i]) or atr[i] <= 0
                    or np.isnan(m21[i - 1]) or np.isnan(m50[i - 1])):
                continue
            cross_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
            cross_down = m21[i - 1] >= m50[i - 1] and m21[i] < m50[i]
            if not (cross_up or cross_down):
                continue
            found_first = True   # first cross of the day found - take or reject, don't look further

            direction = 1 if cross_up else -1
            net_move_atr = direction * (close[i] - day_open_px) / atr[i]
            if net_move_atr > max_premove_atr:
                continue   # day already ran too far in this direction before the cross - skip

            fill_i = i + 1
            if fill_i >= n or np.isnan(atr[fill_i]) or atr[fill_i] <= 0:
                continue
            sc = spread[fill_i] * point
            entry_px = close[fill_i] + (sc if direction > 0 else -sc)
            hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

            exit_i, exit_px, reason = None, None, None
            for k in range(fill_i + 1, hard_limit + 1):
                if np.isnan(m50[k]):
                    continue
                broke = (close[k] < m50[k]) if direction > 0 else (close[k] > m50[k])
                if broke:
                    exit_i, exit_px, reason = k, close[k], "EMA50"
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
    print(f"\n{'#'*100}\n{symbol} M15 - first cross of day, capped pre-move, EMA50 exit\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    print(f"\n{'='*100}\nIN-SAMPLE grid (max allowed pre-move before the cross, ATR units)\n{'='*100}")
    grid = []
    for premove in (0.0, 0.3, 0.5, 1.0, 2.0, 999.0):   # 999 = no cap, i.e. just "first cross" alone
        res = classify_first_cross(df_is, point, premove)
        net = sum(r["pnl_pct"] for r in res) if res else -999
        grid.append((premove, len(res), net, pct_pf(res)))
        tag = "no cap" if premove == 999.0 else f"<={premove} ATR"
        print(f"  premove {tag}:  n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  "
              f"~{len(res)/(is_days/30.44):.1f}/mo", flush=True)

    best = max(grid, key=lambda g: g[2])
    print(f"\n  IS winner: premove<={best[0]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oos_res = classify_first_cross(df_oos, point, best[0])
    report(f"{symbol} - OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_first_cross(df, point, best[0])
    report(f"{symbol} - FULL", full_res, full_days, split_dir=True)
    return best, grid


if __name__ == "__main__":
    bestG, gridG = run_symbol("GOLD")
    bestS, gridS = run_symbol("SILVER")
    print(f"\n\n  Honest K note: GOLD searched {len(gridG)}, SILVER searched {len(gridS)}.")
    print(f"  Cross-instrument check done from the start this time - both run together.")
