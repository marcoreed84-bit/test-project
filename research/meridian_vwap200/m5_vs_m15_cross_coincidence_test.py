"""
User's question: "if the 21ema and 50 cross on the 5min is the 15min also
likely to cross or is this sometimes for the most part noise?"

Method: find every M5 21/50 cross event. For each one, check whether an
M15 21/50 cross in the SAME direction happens within a short window
afterward (0 to W M15 bars, i.e. roughly "soon"). Compare that hit rate
against the BASE RATE - how often an M15 cross in a given direction
happens in a random W-bar window regardless of any M5 event - to see
whether an M5 cross is actually informative about an upcoming M15 cross,
or just coincides about as often as chance would predict.

Only overlapping period available: GOLD M5 data starts 2022-07-04, so M15
is restricted to the same window for a fair, matched comparison (using
M15's full 2014+ history for the base rate would use a different, longer
sample than the M5-cross-conditioned sample, biasing the comparison).
"""
import os
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema

EMA_FAST, EMA_SLOW = 21, 50


def load(fname):
    path = os.path.join(os.path.dirname(__file__), "..", "data", fname)
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    return df, point


def crosses(c):
    e21 = ema(c, EMA_FAST)
    e50 = ema(c, EMA_SLOW)
    n = len(c)
    up = np.zeros(n, dtype=bool)
    down = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(e21[i - 1]) or np.isnan(e50[i - 1]):
            continue
        up[i] = e21[i - 1] <= e50[i - 1] and e21[i] > e50[i]
        down[i] = e21[i - 1] >= e50[i - 1] and e21[i] < e50[i]
    return up, down


if __name__ == "__main__":
    df5, _ = load("GOLD_M5_native.csv")
    df15, _ = load("GOLD_M15_native.csv")

    m5_start = df5["time"].iloc[0]
    df15 = df15[df15["time"] >= m5_start].reset_index(drop=True)
    print(f"Matched window: {m5_start} .. {df5['time'].iloc[-1]}")
    print(f"  M5: {len(df5)} bars, M15: {len(df15)} bars\n")

    up5, down5 = crosses(df5["close"].values)
    up15, down15 = crosses(df15["close"].values)
    t5 = df5["time"].values
    t15 = df15["time"].values

    n5_up, n5_down = int(up5.sum()), int(down5.sum())
    n15_up, n15_down = int(up15.sum()), int(down15.sum())
    print(f"M5 crosses: {n5_up} up, {n5_down} down  (total {n5_up+n5_down})")
    print(f"M15 crosses: {n15_up} down... wait up={n15_up} down={n15_down}  (total {n15_up+n15_down})\n")

    m15_up_times = t15[up15]
    m15_down_times = t15[down15]

    for W_minutes in (15, 30, 45, 60, 90):
        W = pd.Timedelta(minutes=W_minutes)
        hits_up, hits_down = 0, 0
        for t in t5[up5]:
            win = (m15_up_times >= t) & (m15_up_times <= t + W)
            if win.any():
                hits_up += 1
        for t in t5[down5]:
            win = (m15_down_times >= t) & (m15_down_times <= t + W)
            if win.any():
                hits_down += 1
        hit_rate_up = hits_up / n5_up if n5_up else float("nan")
        hit_rate_down = hits_down / n5_down if n5_down else float("nan")

        # base rate: for N random M5-timestamps (not conditioned on a cross),
        # how often does an M15 cross (same direction) fall in the next W?
        rng = np.random.default_rng(3)
        rand_idx_up = rng.choice(len(t5), size=n5_up, replace=False)
        rand_idx_down = rng.choice(len(t5), size=n5_down, replace=False)
        base_hits_up = sum(1 for t in t5[rand_idx_up] if ((m15_up_times >= t) & (m15_up_times <= t + W)).any())
        base_hits_down = sum(1 for t in t5[rand_idx_down] if ((m15_down_times >= t) & (m15_down_times <= t + W)).any())
        base_rate_up = base_hits_up / n5_up if n5_up else float("nan")
        base_rate_down = base_hits_down / n5_down if n5_down else float("nan")

        print(f"Window = next {W_minutes} min ({W_minutes//15} M15 bars):")
        print(f"  UP:   M5-cross -> M15-up-cross-soon hit rate = {hit_rate_up:5.1%}   "
              f"vs base rate (random M5 timestamp) = {base_rate_up:5.1%}   "
              f"lift = {hit_rate_up/base_rate_up:.2f}x" if base_rate_up > 0 else "")
        print(f"  DOWN: M5-cross -> M15-down-cross-soon hit rate = {hit_rate_down:5.1%}   "
              f"vs base rate (random M5 timestamp) = {base_rate_down:5.1%}   "
              f"lift = {hit_rate_down/base_rate_down:.2f}x" if base_rate_down > 0 else "")
        print()
