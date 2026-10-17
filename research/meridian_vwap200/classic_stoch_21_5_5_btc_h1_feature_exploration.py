"""
Feature-correlation exploration for the BTC H1 Stoch(21,5,5) + swing
stop/1:2RR + grace=10 trail construction, per direct request: is there
ANY feature at the signal bar that actually separates winning trades
from losing ones, rather than testing one hypothesis (volume, trend,
chop) at a time in isolation.

IN-SAMPLE ONLY (first 70% of history) - this is exploratory, not a
built/tested filter. Any lead found here still needs to be built into
an actual filter and checked out-of-sample before it means anything -
this file only ranks candidate features by how much they correlate
with trade outcome, nothing more. Same project pattern/caveat as the
dual_stoch_feature_exploration.py work done earlier this session on
a different construction (which found weak leads that built into a
filter, looked very promising in-sample, and then failed completely
on cross-instrument replication - that same "found a lead, verify
before trusting" discipline applies here too).

Candidate features (all computed causally from data up to and
including the signal bar - no lookahead):
  - atr_pctile: trailing-100-bar percentile rank of ATR(14) at the
    signal bar (volatility regime - high/low vol environment)
  - dist_ema21/50/200_atr: distance of close from each EMA, in ATR
    multiples (trend extension/pullback depth)
  - hour_utc: hour of day (0-23) the signal fired in
  - candle_range_atr: the signal bar's own high-low range, in ATR
    multiples (how "big" a bar the cross happened on)
  - body_ratio: |close-open| / (high-low) on the signal bar (strong
    directional close vs indecisive doji-like bar)
  - wick_ratio: the wick on the SIGNAL'S side (lower wick for a buy,
    upper wick for a sell) / (high-low) - rejection-wick depth
  - vol_ratio: tick_volume / its trailing 20-bar average (already
    tested as a standalone filter - included here for completeness)
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH, RR
from classic_stoch_21_5_5_btc_h1_volume_test import load_btc_h1_with_volume
from vwap_open_scenarios_test import ema, wilder_atr

TIME_CAP_BARS = 300
GRACE_BARS = 10


def build_trades_with_features(df, point):
    close_a, high_a, low_a, open_a = df["close"].values, df["high"].values, df["low"].values, df["open"].values
    spread_a = df["spread"].values
    vol_a = df["tick_volume"].values.astype(float)
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    atr_a = wilder_atr(high_a, low_a, close_a, 14)
    m21, m50, m200 = ema(close_a, 21), ema(close_a, 50), ema(close_a, 200)
    vol_avg_a = pd.Series(vol_a).rolling(20, min_periods=20).mean().shift(1).values
    atr_pctile_a = pd.Series(atr_a).rolling(100, min_periods=100).apply(
        lambda w: (w < w[-1]).mean(), raw=True).values
    hour_a = pd.to_datetime(df["time"]).dt.hour.values

    close, high, low, open_, spread = (close_a.tolist(), high_a.tolist(), low_a.tolist(),
                                        open_a.tolist(), spread_a.tolist())
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 100 + 5
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

        atr_i = atr_a[i]
        feats = dict(
            atr_pctile=atr_pctile_a[i],
            dist_ema21_atr=dir_ * (close[i] - m21[i]) / atr_i if atr_i > 0 else np.nan,
            dist_ema50_atr=dir_ * (close[i] - m50[i]) / atr_i if atr_i > 0 else np.nan,
            dist_ema200_atr=dir_ * (close[i] - m200[i]) / atr_i if atr_i > 0 else np.nan,
            hour_utc=hour_a[i],
            candle_range_atr=(high[i] - low[i]) / atr_i if atr_i > 0 else np.nan,
            body_ratio=abs(close[i] - open_[i]) / (high[i] - low[i]) if (high[i] - low[i]) > 0 else np.nan,
            # lower wick for a buy = min(open,close) - low (was low - min(...), always <= 0)
            wick_ratio=((min(open_[i], close[i]) - low[i]) if dir_ > 0 else (high[i] - max(open_[i], close[i])))
                       / (high[i] - low[i]) if (high[i] - low[i]) > 0 else np.nan,
            vol_ratio=(vol_a[i] / vol_avg_a[i]) if (vol_avg_a[i] and vol_avg_a[i] > 0) else np.nan,
        )
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_, **feats))
        i = exit_i + 1

    return results


def run():
    df, point = load_btc_h1_with_volume()
    n = len(df)
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)

    trades = build_trades_with_features(df_is, point)
    print(f"IN-SAMPLE trades: {len(trades)}  ({df_is['time'].iloc[0]} .. {df_is['time'].iloc[-1]})")
    pf = pd.DataFrame(trades)

    feature_cols = ["atr_pctile", "dist_ema21_atr", "dist_ema50_atr", "dist_ema200_atr",
                     "hour_utc", "candle_range_atr", "body_ratio", "wick_ratio", "vol_ratio"]
    print(f"\n{'Feature':<20} {'corr w/ pnl%':>14} {'n (non-NaN)':>13}")
    print("-" * 50)
    corrs = []
    for col in feature_cols:
        sub = pf[[col, "pnl_pct"]].dropna()
        c = sub[col].corr(sub["pnl_pct"]) if len(sub) > 10 else np.nan
        corrs.append((col, c, len(sub)))
    for col, c, nn in sorted(corrs, key=lambda x: -abs(x[1]) if not np.isnan(x[1]) else 0):
        print(f"{col:<20} {c:14.4f} {nn:13d}")

    print(f"\nHour-of-day breakdown (win% and %PF per UTC hour, in-sample):")
    def pct_pf(g):
        gw = g[g["pnl_pct"] > 0]["pnl_pct"].sum()
        gl = -g[g["pnl_pct"] <= 0]["pnl_pct"].sum()
        return gw / gl if gl > 0 else np.inf
    hourly = pf.groupby("hour_utc").apply(lambda g: pd.Series({
        "n": len(g), "win%": 100 * (g["pnl_pct"] > 0).mean(), "%PF": pct_pf(g)
    }))
    print(hourly.round(3))


if __name__ == "__main__":
    run()
