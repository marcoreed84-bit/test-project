"""
Per direct request: "is there no way of knowing if more sellers are
stepping in or more buyers stepping in" - this project has NO real
order-flow/Level2 data (XM is a dealt CFD feed, not an exchange order
book), only tick_volume per bar (count of price changes, not actual
traded size). The best available proxy: aggregate the real M1 bars
inside each M15 window and split their tick_volume by whether each M1
bar closed up or down - an "up-tick-volume vs down-tick-volume"
pressure read, built from GENUINE tick_volume data (not synthetic).

PRESSURE = (up_vol - down_vol) / (up_vol + down_vol) over the M15 bar's
own M1 window, range [-1, +1]. Filter: require PRESSURE to agree with
the stochastic zone-cross signal's own direction (buy needs positive
pressure >= THRESH, sell needs negative pressure <= -THRESH) at the
signal bar itself.

GOLD ONLY - only GOLD has real M1 history loaded in this project
(GOLD_M1_full.csv); Silver/BTC M1 history isn't available, so this
can't be tested on them.

Same validated swing-stop/1:2RR/opposite-stoch-cross exit used
throughout tonight.

Honest K=1 for this exact construction (first VOLUME-based idea
tonight - everything before this was purely price/EMA-based).
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

GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")
K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
PRESSURE_THRESH = 0.15
TIME_CAP_BARS = 300


def load_m15():
    path = os.path.join(DATA_DIR, "GOLD_M15_native.csv")
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df, point


def load_m1_pressure():
    """Build per-M15-bar (up_vol - down_vol)/(up_vol + down_vol) from real M1 bars."""
    path = os.path.join(DATA_DIR, "GOLD_M1_full.csv")
    m1 = pd.read_csv(path)
    m1["time"] = pd.to_datetime(m1["time"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    m1 = m1.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    m1 = m1[m1["time"] >= GOLD_M15_REAL_START]

    up_vol = np.where(m1["close"].values > m1["open"].values, m1["tick_volume"].values, 0)
    down_vol = np.where(m1["close"].values < m1["open"].values, m1["tick_volume"].values, 0)
    m15_bucket = m1["time"].dt.floor("15min")

    g = pd.DataFrame({"bucket": m15_bucket, "up": up_vol, "down": down_vol}).groupby("bucket").sum()
    denom = (g["up"] + g["down"]).replace(0, np.nan)
    g["pressure"] = (g["up"] - g["down"]) / denom
    return g["pressure"]


def build_trades(df, point, pressure_map, use_filter):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    time_a = df["time"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    pressure = pressure_map.reindex(pd.to_datetime(time_a)).values

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    n_candidates, n_pass = 0, 0
    start = max(K_PERIOD + SLOWING + D_PERIOD, SWING_BARS + 5)
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
        n_candidates += 1

        if use_filter:
            p = pressure[i]
            if np.isnan(p):
                i += 1
                continue
            if trig_dir > 0 and p < PRESSURE_THRESH:
                i += 1
                continue
            if trig_dir < 0 and p > -PRESSURE_THRESH:
                i += 1
                continue
        n_pass += 1

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

    print(f"  candidates={n_candidates}  pass={n_pass}  (filter={'ON, thresh='+str(PRESSURE_THRESH) if use_filter else 'OFF (baseline)'})")
    return results


if __name__ == "__main__":
    df, point = load_m15()
    pressure_map = load_m1_pressure()
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\nGOLD M15 - tick-volume pressure filter on zone-cross stochastic entry\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    print(f"  M1 pressure coverage: {pressure_map.notna().sum()} of {len(pressure_map)} M15 windows have data")

    print(f"\n  --- BASELINE (no volume filter) ---")
    trades_base = build_trades(df, point, pressure_map, use_filter=False)
    report("GOLD M15 - baseline zone-cross (no volume filter)", trades_base, full_days, split_dir=True)

    print(f"\n  --- WITH tick-volume pressure filter ---")
    trades_filt = build_trades(df, point, pressure_map, use_filter=True)
    report("GOLD M15 - zone-cross + tick-volume pressure filter", trades_filt, full_days, split_dir=True)

    print(f"\n\n  Honest K=1 for this construction - first volume-based idea tonight.")
    print(f"  GOLD ONLY - no M1 history loaded for Silver/BTC in this project.")
