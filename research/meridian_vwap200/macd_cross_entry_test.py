"""
MACD(12,26,9) signal-line crossover entry - a different mechanism from
everything tried tonight (stochastic %K/%D cross, EMA21/50 price
cross, RSI divergence). MACD line = EMA12-EMA26, signal = EMA9 of the
MACD line. Entry: MACD line crosses above/below its own signal line,
direction matches the cross. Exit: hold until the NEXT opposite MACD
cross - same "hold to next opposite cross" convention validated for
the EMA21/50 construction tonight (not a fixed stop/target only,
testing the trend-following version first since that's the one that
actually worked earlier).

Tested on GOLD, SILVER, BTCUSD M15. Honest K=1 per instrument - first
MACD construction tonight.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report
from vwap_open_scenarios_test import ema

FAST, SLOW, SIGNAL = 12, 26, 9
GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")


def load_m15(symbol_file, trim_gold=False):
    path = os.path.join(DATA_DIR, symbol_file)
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    if trim_gold:
        df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df, point


def build_trades(df, point):
    close_a, spread_a = df["close"].values, df["spread"].values
    n = len(df)
    e_fast = ema(close_a, FAST)
    e_slow = ema(close_a, SLOW)
    macd_line = e_fast - e_slow
    valid_macd = ~np.isnan(macd_line)
    signal_line = np.full(n, np.nan)
    # signal EMA seeded only once the MACD line itself becomes valid (NaN-safe EMA)
    first_valid = np.argmax(valid_macd) if valid_macd.any() else n
    if first_valid + SIGNAL <= n:
        seed_start = first_valid
        seed_end = seed_start + SIGNAL
        signal_line[seed_end - 1] = macd_line[seed_start:seed_end].mean()
        alpha = 2.0 / (SIGNAL + 1.0)
        for i in range(seed_end, n):
            signal_line[i] = signal_line[i - 1] + alpha * (macd_line[i] - signal_line[i - 1])

    close, spread = close_a.tolist(), spread_a.tolist()
    macd, sig = macd_line.tolist(), signal_line.tolist()
    valid = [not (np.isnan(macd[i]) or np.isnan(sig[i])) for i in range(n)]

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = macd[i - 1] <= sig[i - 1] and macd[i] > sig[i]
            crossDown[i] = macd[i - 1] >= sig[i - 1] and macd[i] < sig[i]

    results = []
    start = SLOW + SIGNAL + 5
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
                                     reason="EXIT-MACD-CROSS", hold_bars=fill_i - open_fill_i))
            posDir, open_fill_i, open_entry_px = 0, None, None

        if dir_ != 0 and posDir == 0:
            fill_i = i + 1
            if fill_i < n:
                sc = spread[fill_i] * point
                entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
                posDir, open_fill_i, open_entry_px = dir_, fill_i, entry_px

        i += 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - MACD(12,26,9) signal-line crossover, hold to next opposite cross\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - MACD cross", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - first MACD construction tonight.")
