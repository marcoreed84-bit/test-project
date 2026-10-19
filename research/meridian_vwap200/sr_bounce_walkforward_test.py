"""
Walk-forward check for GOLD SR_BOUNCE before trusting it further.
SR_BOUNCE has NO tuned parameters that were searched against this data
(pivot 5/5, TOL=0.3 ATR, RR=2.0, SWING_BARS=10 - all carried over
unchanged from constructions used identically all night, never fit to
this specific pattern), so this isn't a classic "in-sample search vs
out-of-sample" overfitting check the way Vanguard's filter search was -
it's a genuine regime-stability check: does the edge found on the FULL
history actually hold up when split into two honest, non-overlapping
halves, or is it concentrated in one unusual period?

Split: IN-SAMPLE = 2014-06-13 .. 2020-12-31 (~6.5 years), OUT-OF-SAMPLE
= 2021-01-01 .. end of history (~5.75 years) - each computed and
reported completely independently (levels/pivots/trades are all
recomputed fresh within each half, no information crosses the split).
"""
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from smc_concepts_batch_test import load_m15, signals_sr_bounce, build_trades, ATR_PERIOD, PIVOT_LEFT, PIVOT_RIGHT
from stoch_ma_stack_gap_filter_test import wilder_atr
from rsi_divergence_entry_test import find_pivots
from dual_stoch_cross_200ema_test import report

SPLIT_DATE = pd.Timestamp("2021-01-01")


def run_window(label, df, point):
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    atr = wilder_atr(h, l, c, ATR_PERIOD)
    pivot_lows = find_pivots(l, PIVOT_LEFT, PIVOT_RIGHT, is_low=True)
    pivot_highs = find_pivots(h, PIVOT_LEFT, PIVOT_RIGHT, is_low=False)
    dirs = signals_sr_bounce(o, h, l, c, atr, n, pivot_lows, pivot_highs)
    trades = build_trades(df, point, dirs)
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({n} bars)")
    report(label, trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    df, point = load_m15("GOLD_M15_native.csv", trim_gold=True)

    df_is = df[df["time"] < SPLIT_DATE].reset_index(drop=True)
    df_oos = df[df["time"] >= SPLIT_DATE].reset_index(drop=True)

    print(f"\n{'#'*100}\nGOLD M15 - SR_BOUNCE walk-forward split at {SPLIT_DATE.date()}\n{'#'*100}")

    print(f"\n  --- IN-SAMPLE (2014-06-13 .. 2020-12-31) ---")
    run_window("GOLD M15 - SR_BOUNCE IN-SAMPLE", df_is, point)

    print(f"\n  --- OUT-OF-SAMPLE (2021-01-01 .. end) ---")
    run_window("GOLD M15 - SR_BOUNCE OUT-OF-SAMPLE", df_oos, point)

    print(f"\n\n  Full-history reference (already null-tested): n=6764  PF=1.044  net%=56.94")
    print(f"  No parameters were tuned on either half - same construction used throughout.")
