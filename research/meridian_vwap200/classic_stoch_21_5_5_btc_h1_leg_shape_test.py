"""
Two more candidate features for the BTC H1 Stoch(21,5,5) + swing stop/
1:2RR + grace=10 trail construction, per direct request - does the SHAPE
of the stochastic's prior leg into the zone (before the signal cross)
say anything about trade quality:

  - leg_efficiency: Kaufman-style efficiency ratio of PRICE over the same
    SWING_BARS lookback window used for the stop (10 bars ending at the
    signal bar) - |net price move| / (sum of bar-to-bar |price changes|).
    1.0 = a perfectly clean, one-directional move into the signal; near
    0 = a choppy, back-and-forth leg that happened to end up in the zone.
  - bars_since_50: how many bars ago %K last sat on the FAR side of 50
    (>=50 for a buy setup being built from oversold, <=50 for a sell)
    before diving/rising into the zone - a fast dive (few bars) vs a
    slow grind (many bars) into oversold/overbought, per direct request.
    Capped/NaN if no such bar exists within a 60-bar lookback (session
    just started, or %K has been pinned in the zone that whole window).

Same IN-SAMPLE-ONLY (first 70%), exploratory-only discipline as
classic_stoch_21_5_5_btc_h1_feature_exploration.py - correlation against
raw trade pnl_pct, not a built filter. This is the 37th configuration
tested against this project's BTC H1 Stoch(21,5,5) line (K=37 - 36
before this file, +1 for this pair of features tested together as one
new exploratory pass).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH, RR
from classic_stoch_21_5_5_btc_h1_test import load_btc_h1

TIME_CAP_BARS = 300
GRACE_BARS = 10
BARS_SINCE_50_LOOKBACK = 60


def build_trades_with_features(df, point):
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
    start = K_PERIOD + SLOWING + D_PERIOD + max(SWING_BARS, BARS_SINCE_50_LOOKBACK) + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 0
        if crossUp[i] and k[i] < ZONE_LOW:
            dir_ = 1
        elif crossDown[i] and k[i] > ZONE_HIGH:
            dir_ = -1
        if dir_ == 0:
            i += 1
            continue

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

        pending_exit_bar = None
        exit_i, exit_px = None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if dir_ > 0 else (high[j] >= stop_px)
            target_hit = (high[j] >= target_px) if dir_ > 0 else (low[j] <= target_px)
            if stop_hit:
                exit_i, exit_px = j, stop_px
                break
            if target_hit:
                exit_i, exit_px = j, target_px
                break
            if valid[j] and valid[j - 1]:
                favorable = (dir_ > 0 and crossUp[j]) or (dir_ < 0 and crossDown[j])
                opposite  = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                if pending_exit_bar is not None and favorable:
                    new_swing = min(low[j - SWING_BARS:j]) if dir_ > 0 else max(high[j - SWING_BARS:j])
                    if dir_ > 0 and new_swing > stop_px:
                        stop_px = new_swing
                    elif dir_ < 0 and new_swing < stop_px:
                        stop_px = new_swing
                    pending_exit_bar = None
                if pending_exit_bar is None and opposite:
                    pending_exit_bar = j + GRACE_BARS
                if pending_exit_bar is not None and j >= pending_exit_bar:
                    scj = spread[j] * point
                    exit_i, exit_px = j, close[j] - (scj if dir_ > 0 else -scj)
                    break
        if exit_i is None:
            exit_i, exit_px = hard_limit, close[hard_limit]

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_

        # --- leg_efficiency: Kaufman-style, over the same SWING_BARS window
        window_px = close[i - SWING_BARS:i + 1]
        net_move = abs(window_px[-1] - window_px[0])
        path_len = sum(abs(window_px[j] - window_px[j - 1]) for j in range(1, len(window_px)))
        leg_efficiency = (net_move / path_len) if path_len > 0 else np.nan

        # --- bars_since_50: walk back from i-1 to find the last bar where
        # %K was on the FAR side of 50 (>=50 for a buy, <=50 for a sell),
        # i.e. the start of the dive/rise into the zone that just crossed.
        bars_since_50 = np.nan
        lookback_start = max(0, i - BARS_SINCE_50_LOOKBACK)
        for j in range(i - 1, lookback_start - 1, -1):
            if not valid[j]:
                break
            on_far_side = (k[j] >= 50.0) if dir_ > 0 else (k[j] <= 50.0)
            if on_far_side:
                bars_since_50 = i - j
                break

        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             leg_efficiency=leg_efficiency, bars_since_50=bars_since_50))
        i = exit_i + 1

    return results


def run():
    df, point = load_btc_h1()
    n = len(df)
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)

    trades = build_trades_with_features(df_is, point)
    print(f"IN-SAMPLE trades: {len(trades)}  ({df_is['time'].iloc[0]} .. {df_is['time'].iloc[-1]})")
    pf = pd.DataFrame(trades)

    print(f"\n{'Feature':<18} {'corr w/ pnl%':>14} {'n (non-NaN)':>13}")
    print("-" * 48)
    for col in ["leg_efficiency", "bars_since_50"]:
        sub = pf[[col, "pnl_pct"]].dropna()
        c = sub[col].corr(sub["pnl_pct"]) if len(sub) > 10 else np.nan
        print(f"{col:<18} {c:14.4f} {len(sub):13d}")

    # Quartile breakdown - sometimes a real effect is non-linear and corr hides it
    for col in ["leg_efficiency", "bars_since_50"]:
        sub = pf[[col, "pnl_pct"]].dropna().copy()
        if len(sub) < 40:
            continue
        sub["q"] = pd.qcut(sub[col], 4, labels=["Q1(low)", "Q2", "Q3", "Q4(high)"], duplicates="drop")
        print(f"\n{col} quartile breakdown (in-sample):")
        def pct_pf(g):
            gw = g[g["pnl_pct"] > 0]["pnl_pct"].sum()
            gl = -g[g["pnl_pct"] <= 0]["pnl_pct"].sum()
            return gw / gl if gl > 0 else np.inf
        qb = sub.groupby("q", observed=True).apply(lambda g: pd.Series({
            "n": len(g), "win%": 100 * (g["pnl_pct"] > 0).mean(), "%PF": pct_pf(g)
        }))
        print(qb.round(3))

    print(f"\n  Honest K: this project's BTC H1 Stoch(21,5,5) line is now at K=37")
    print(f"  (36 before this file, +1 for this pair of leg-shape features tested")
    print(f"  together as one new exploratory pass).")


if __name__ == "__main__":
    run()
