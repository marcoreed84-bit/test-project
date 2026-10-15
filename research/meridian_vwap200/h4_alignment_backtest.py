"""
Proper backtest of the one feature that showed a real, clean separation in
tonight's exploratory scan: H4 trend alignment. Entry is simply the 21/50
EMA cross (any location, any time of day - not restricted to near-VWAP or
early-session, matching how the exploration itself was built), filtered to
only take crosses where the last fully CLOSED H4 bar's close agrees with
the cross direction relative to its own 50-period H4 EMA.

Uses this project's own corrected H4-bar lookup (searchsorted +bar_len,
side="right", -2) - the same convention already fixed elsewhere in this
project after a real lookahead bug was found in a naive version of this
exact lookup.

Two exits tested: the 50-EMA close-back (parameter-free, the one exit that
looked real earlier tonight before failing its K-corrected null) and an
ATR trailing stop (reference). Real spread, real fills, honest IS/OOS
split. If either survives OOS cleanly, follow up with a random-timing null
before trusting it - not done in this file.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema, wilder_atr
from meridian_early_cross_test import load_m15, DATA_DIR

TIME_CAP_BARS = 200


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def pct_pf_gross(results):
    if not results:
        return float("nan")
    arr = np.array([r["gross_pnl_pct"] for r in results])
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
          f"net%={100*arr.sum():7.2f}  GROSS%={100*gross_arr.sum():7.2f}  gross_PF={pct_pf_gross(results):6.3f}  "
          f"avg_hold={holds.mean():5.1f}h  [{rtxt}]{pm}")
    if split_dir:
        longs = [r for r in results if r["dir"] > 0]
        shorts = [r for r in results if r["dir"] < 0]
        report("    -> LONGS only", longs, n_days)
        report("    -> SHORTS only", shorts, n_days)


def load_h4(symbol):
    path = os.path.join(DATA_DIR, f"{symbol}_H4.csv")
    if os.path.exists(path):
        df = pd.read_csv(path, skiprows=1)
        df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
        close = df["close"].values
    else:
        # no native H4 file for this symbol (SILVER) - derive H4 bars by
        # standard OHLC resampling from the M15 data itself, 4h UTC buckets
        m15, _ = load_m15(symbol)
        m15 = m15.set_index("time")
        h4 = m15["close"].resample("4h", origin="epoch").last().dropna()
        df = pd.DataFrame({"time": h4.index, "close": h4.values})
        close = df["close"].values
    ema50_h4 = ema(close, 50)
    return df["time"].values.astype("datetime64[s]").astype(np.int64), ema50_h4, close


def classify_h4_filtered(df, symbol, point, exit_mode, trail_atr_mult=2.0):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)
    n = len(df)

    h4_time, h4_ema50, h4_close = load_h4(symbol)
    bar_times = df["time"].values.astype("datetime64[s]").astype(np.int64)
    # FIX (Opus audit caught this): must add the M15 BAR'S OWN length (15 min),
    # not h4_bar_len (4h) - adding 4h pushed the lookup into a later, still-
    # forming H4 candle for ~90% of bars, reintroducing the exact lookahead
    # bug this project already fixed once (see
    # research/aurelius/vanguard_m15_h4_trend_filter_oos_test.py:71).
    m15_bar_len = 15 * 60
    h4_idx = np.searchsorted(h4_time, bar_times + m15_bar_len, side="right") - 2
    h4_idx = np.clip(h4_idx, 0, len(h4_time) - 1)
    h4_trend_up = h4_close[h4_idx] > h4_ema50[h4_idx]

    results = []
    for i in range(215, n - 1):
        if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(atr[i]) or atr[i] <= 0
                or np.isnan(m21[i - 1]) or np.isnan(m50[i - 1])):
            continue
        cross_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
        cross_down = m21[i - 1] >= m50[i - 1] and m21[i] < m50[i]
        if not (cross_up or cross_down):
            continue
        direction = 1 if cross_up else -1
        if h4_trend_up[i] != (direction > 0):
            continue   # H4 filter - cross must agree with the H4 trend

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
        else:
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
        # gross pnl (no spread) - reported alongside net, per Opus audit:
        # Silver's spread is ~9x Gold's as a fraction of price, large enough
        # to swamp the underlying directional signal on its own
        gross_entry_px = close[fill_i]
        gross_pnl_pct = ((exit_px - gross_entry_px) / gross_entry_px) * direction
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, gross_pnl_pct=gross_pnl_pct,
                             dir=direction, reason=reason, hold_bars=exit_i - fill_i))
    return results


def run_symbol(symbol):
    df, point = load_m15(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} M15 - 21/50 cross, H4-trend-aligned filter only\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    print(f"\n{'='*100}\nEMA50 EXIT (parameter-free)\n{'='*100}")
    is_res = classify_h4_filtered(df_is, symbol, point, "ema50")
    report("IS", is_res, is_days, split_dir=True)
    oos_res = classify_h4_filtered(df_oos, symbol, point, "ema50")
    report("OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_h4_filtered(df, symbol, point, "ema50")
    report("FULL", full_res, full_days, split_dir=True)

    print(f"\n{'='*100}\nATR TRAILING STOP (reference)\n{'='*100}")
    grid = []
    for trail_m in (1.5, 2.0, 2.5):
        res = classify_h4_filtered(df_is, symbol, point, "trail", trail_m)
        net = sum(r["pnl_pct"] for r in res) if res else -999
        grid.append((trail_m, len(res), net, pct_pf(res)))
        print(f"  trail={trail_m}:  n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}", flush=True)
    best = max(grid, key=lambda g: g[2])
    print(f"  IS winner: trail={best[0]}  (K={len(grid)})")
    oos_res = classify_h4_filtered(df_oos, symbol, point, "trail", best[0])
    report("OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_h4_filtered(df, symbol, point, "trail", best[0])
    report("FULL", full_res, full_days, split_dir=True)


if __name__ == "__main__":
    run_symbol("GOLD")
    run_symbol("SILVER")
    print(f"\n\n  Honest K note: EMA50 exit=0 free params (K=1) per symbol. ATR trail grid K=3 per symbol.")
    print(f"  Total K this file: (1+3)*2 symbols = 8. New construction - tracked independently.")
