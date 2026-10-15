"""
Tests a published finding against tonight's own data: intraday momentum
literature reports the effect is STRONGER on low-volume days (counter to
the naive "more volume = more conviction" assumption) - and this project's
own exploratory scan already showed vol_ratio negatively correlated with
forward return (-0.0285), i.e. lower relative volume at the cross did
better, just not yet tested as an actual filter threshold.

Combines this with the one thing that survived the lookahead-bug fix:
H4-trend-alignment (corrected lookup). Entry: 21/50 cross, H4-aligned,
AND relative volume (tick volume at the cross bar vs trailing 20-bar
average) below a threshold. EMA50 exit. Gold and Silver tested together
from the start, real spread, gross-vs-net reported.

Honest K tracked independently, starting fresh for this file.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema, wilder_atr
from meridian_early_cross_test import load_m15
from h4_alignment_backtest import load_h4

TIME_CAP_BARS = 200


def pct_pf(results, key="pnl_pct"):
    if not results:
        return float("nan")
    arr = np.array([r[key] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results, n_days=None, split_dir=False):
    if not results:
        print(f"  {label}: n=0")
        return
    arr = np.array([r["pnl_pct"] for r in results])
    gross_arr = np.array([r["gross_pnl_pct"] for r in results])
    holds = np.array([r["hold_bars"] for r in results]) * 0.25
    reasons = {}
    for r in results:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    rtxt = ", ".join(f"{k}:{v}" for k, v in reasons.items())
    pm = f"  (~{len(results)/(n_days/30.44):.1f}/mo)" if n_days else ""
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  %PF={pct_pf(results):6.3f}  "
          f"net%={100*arr.sum():7.2f}  GROSS%={100*gross_arr.sum():7.2f}  gross_PF={pct_pf(results,'gross_pnl_pct'):6.3f}  "
          f"avg_hold={holds.mean():5.1f}h  [{rtxt}]{pm}")
    if split_dir:
        longs = [r for r in results if r["dir"] > 0]
        shorts = [r for r in results if r["dir"] < 0]
        report("    -> LONGS only", longs, n_days)
        report("    -> SHORTS only", shorts, n_days)


def classify_h4_lowvol(df, symbol, point, max_vol_ratio):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    tick_vol = df["tick_volume"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)
    n = len(df)
    vol_avg20 = pd.Series(tick_vol).rolling(20, min_periods=20).mean().values

    h4_time, h4_ema50, h4_close = load_h4(symbol)
    bar_times = df["time"].values.astype("datetime64[s]").astype(np.int64)
    m15_bar_len = 15 * 60
    h4_idx = np.searchsorted(h4_time, bar_times + m15_bar_len, side="right") - 2
    h4_idx = np.clip(h4_idx, 0, len(h4_time) - 1)
    h4_trend_up = h4_close[h4_idx] > h4_ema50[h4_idx]

    results = []
    for i in range(215, n - 1):
        if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(atr[i]) or atr[i] <= 0
                or np.isnan(m21[i - 1]) or np.isnan(m50[i - 1]) or np.isnan(vol_avg20[i]) or vol_avg20[i] <= 0):
            continue
        cross_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
        cross_down = m21[i - 1] >= m50[i - 1] and m21[i] < m50[i]
        if not (cross_up or cross_down):
            continue
        direction = 1 if cross_up else -1
        if h4_trend_up[i] != (direction > 0):
            continue
        vol_ratio = tick_vol[i] / vol_avg20[i]
        if vol_ratio > max_vol_ratio:
            continue

        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[fill_i]) or atr[fill_i] <= 0:
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)
        gross_entry_px = close[fill_i]
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
        gross_pnl_pct = ((exit_px - gross_entry_px) / gross_entry_px) * direction
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, gross_pnl_pct=gross_pnl_pct,
                             dir=direction, reason=reason, hold_bars=exit_i - fill_i))
    return results


def run_symbol(symbol):
    df, point = load_m15(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} M15 - H4-aligned cross, low relative-volume filter, EMA50 exit\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    print(f"\n{'='*100}\nIN-SAMPLE grid (max relative volume allowed at the cross)\n{'='*100}")
    grid = []
    for max_vr in (0.5, 0.75, 1.0, 1.5, 999.0):
        res = classify_h4_lowvol(df_is, symbol, point, max_vr)
        net = sum(r["pnl_pct"] for r in res) if res else -999
        grid.append((max_vr, len(res), net, pct_pf(res)))
        tag = "no cap (H4-align alone)" if max_vr == 999.0 else f"<={max_vr}x avg"
        print(f"  vol {tag}:  n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  "
              f"~{len(res)/(is_days/30.44):.1f}/mo", flush=True)

    best = max(grid, key=lambda g: g[2])
    print(f"\n  IS winner: max_vol_ratio={best[0]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oos_res = classify_h4_lowvol(df_oos, symbol, point, best[0])
    report(f"{symbol} - OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_h4_lowvol(df, symbol, point, best[0])
    report(f"{symbol} - FULL", full_res, full_days, split_dir=True)
    return best, grid


if __name__ == "__main__":
    bestG, gridG = run_symbol("GOLD")
    bestS, gridS = run_symbol("SILVER")
    print(f"\n\n  Honest K note: GOLD searched {len(gridG)}, SILVER searched {len(gridS)}.")
