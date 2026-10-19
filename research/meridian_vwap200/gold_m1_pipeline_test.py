"""
M1 pipeline - per direct request, since the user has actually been
watching the live chart on M1 (the three annotated screenshots tonight
were all M1), not M15 where every construction so far has been tested.

DATA GOTCHA (new, not in CLAUDE.md yet): GOLD_M1_full.csv is
CONTINUOUS only from 2014-06-13 to 2021-12-31 - there is a ~4-year gap
with NO M1 data for 2022-2024, then a second continuous chunk starting
2025-11-19 through the present. This script uses ONLY the first,
larger continuous window (2014-06-13 .. 2021-12-31, ~7.5 years) so
every bar-to-bar calculation (EMA, stochastic, swing stops) is
genuinely continuous - mixing across the gap would silently corrupt
every rolling calculation at the seam.

Re-tests the TWO constructions already validated/tested on M15, on M1
instead, to see if the M1 timeframe (what's actually being watched
live) behaves differently from M15 (what's been tested all night):
  (1) baseline zone-cross stochastic entry (same K/D/zone settings used
      all night) - swing-stop/1:2RR/opposite-cross exit.
  (2) pure EMA21/50 crossover (the one validated M15 construction
      tonight - Gold longs %PF=1.031) - hold to next opposite cross.

Honest K=1 per construction on M1 (first time either has been tested
on this timeframe).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from vwap_open_scenarios_test import ema

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST, EMA_SLOW = 21, 50
TIME_CAP_BARS = 300
#--- per direct request, re-pointed at the RECENT continuous chunk instead of
#--- the older 2014-2021 one - closer to current market conditions, and the
#--- one actually relevant to live trading now
M1_WINDOW_START = pd.Timestamp("2025-11-19")
M1_WINDOW_END   = pd.Timestamp("2026-09-25 20:52:00")


def load_m1_gold():
    path = os.path.join(DATA_DIR, "GOLD_M1_full.csv")
    with open(path) as f:
        header1 = f.readline()
    # GOLD_M1_full.csv has NO meta-header line (unlike the M15 files) - point
    # size must come from the M15 file's own header instead, same instrument
    m15_path = os.path.join(DATA_DIR, "GOLD_M15_native.csv")
    with open(m15_path) as f:
        m15_header1 = f.readline()
    point = float(m15_header1.split("meta_point,")[1].split(",")[0])

    df = pd.read_csv(path) if "meta_point" not in header1 else pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    df = df[(df["time"] >= M1_WINDOW_START) & (df["time"] <= M1_WINDOW_END)].reset_index(drop=True)
    if "spread" not in df.columns:
        df["spread"] = 20  # fallback typical Gold spread in points if the column is missing
    return df, point


def build_trades_stoch(df, point):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        trig_dir = 0
        if crossUp[i] and k[i] < ZONE_LOW:
            trig_dir = 1
        elif crossDown[i] and k[i] > ZONE_HIGH:
            trig_dir = -1
        if trig_dir == 0:
            i += 1
            continue

        dir_ = trig_dir
        swing = min(low[i - SWING_BARS:i]) if dir_ > 0 else max(high[i - SWING_BARS:i])
        risk = dir_ * (close[i] - swing)
        if risk <= 0.0:
            i += 1
            continue
        fill_i = i + 1
        if fill_i >= n:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
        stop_px = swing
        target_px = entry_px + dir_ * RR * risk
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if dir_ > 0 else (high[j] >= stop_px)
            target_hit = (high[j] >= target_px) if dir_ > 0 else (low[j] <= target_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if target_hit:
                exit_i, exit_px, reason = j, target_px, "TARGET"
                break
            if valid[j] and valid[j - 1]:
                opposite = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                if opposite:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-STOCH"
                    break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def build_trades_emacross(df, point):
    close_a, spread_a = df["close"].values, df["spread"].values
    n = len(df)
    e21_a = ema(close_a, EMA_FAST)
    e50_a = ema(close_a, EMA_SLOW)

    close, spread = close_a.tolist(), spread_a.tolist()
    e21, e50 = e21_a.tolist(), e50_a.tolist()
    valid = [not (np.isnan(e21[i]) or np.isnan(e50[i])) for i in range(n)]

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = e21[i - 1] <= e50[i - 1] and e21[i] > e50[i]
            crossDown[i] = e21[i - 1] >= e50[i - 1] and e21[i] < e50[i]

    results = []
    start = EMA_SLOW + 5
    i = start
    posDir, open_fill_i, open_entry_px = 0, None, None
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 1 if crossUp[i] else (-1 if crossDown[i] else 0)

        if posDir != 0 and dir_ != 0 and dir_ != posDir:
            fill_i = i + 1
            if fill_i < n:
                sc = spread[fill_i] * point
                exit_px = close[fill_i] - (sc if posDir > 0 else -sc)
                pnl_pct = ((exit_px - open_entry_px) / open_entry_px) * posDir
                results.append(dict(entry_i=open_fill_i, exit_i=fill_i, pnl_pct=pnl_pct, dir=posDir,
                                     reason="EXIT-EMA-CROSS", hold_bars=fill_i - open_fill_i))
            posDir, open_fill_i, open_entry_px = 0, None, None

        if dir_ != 0 and posDir == 0:
            fill_i = i + 1
            if fill_i < n:
                sc = spread[fill_i] * point
                entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
                posDir, open_fill_i, open_entry_px = dir_, fill_i, entry_px

        i += 1

    return results


if __name__ == "__main__":
    df, point = load_m1_gold()
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\nGOLD M1 pipeline - RECENT continuous window (2025-11-19 onward)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")

    print(f"\n  --- (1) baseline zone-cross stochastic entry, on M1 ---")
    trades1 = build_trades_stoch(df, point)
    report("GOLD M1 - baseline zone-cross stochastic", trades1, full_days, split_dir=True)

    print(f"\n  --- (2) pure EMA21/50 crossover, on M1 ---")
    trades2 = build_trades_emacross(df, point)
    report("GOLD M1 - pure EMA21/50 crossover", trades2, full_days, split_dir=True)

    print(f"\n\n  Honest K=1 per construction on M1 (first time tested on this timeframe).")
    print(f"  Using the RECENT continuous chunk (2025-11-19 onward) per direct request -")
    print(f"  not the older 2014-2021 data. GOLD M1 has a ~4yr gap (2022-2024) between them.")
