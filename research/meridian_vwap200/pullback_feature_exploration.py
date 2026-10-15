"""
Takes every pullback-to-21/50-EMA trade from the already-tested bidirectional
construction (meridian_pullback_bidir_test.py - confirmed net loser, full
history PF=0.789) and asks the same question the earlier cross feature
scan asked: what, if anything, separates the winning pullback trades from
the losing ones? Correlates candidate features (measured AT the pullback/
touch bar, causally) against the trade's actual realized outcome.

Features:
  - h4_trend_aligned: last closed H4 bar's trend vs the pullback direction
    (corrected lookup convention)
  - dist_200ema_atr: distance from the 200-EMA at the touch, signed
  - pullback_depth_atr: how far price dipped below (or above, for shorts)
    the reference MA relative to the MA itself, in ATR units
  - prior_trend_strength_atr: how far price had travelled from the 200-EMA
    before the pullback started (a proxy for "how established" the trend
    was when the pullback happened)
  - adx14: Wilder ADX at the touch bar
  - vol_ratio: relative volume at the touch bar
  - confirm_bars_used: how many bars the bounce took to confirm (fast vs
    slow confirmation)

Target: the trade's actual realized pnl_pct from the real backtest (EMA50-
anchored trail exit, same as the bidirectional test), not just raw forward
return - so this directly explains the already-known losing result, not a
different hypothetical measure.

IS/OOS discipline: exploration on Gold IS only.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema, wilder_atr, session_vwap
from meridian_early_cross_test import load_m15, DATA_DIR

TIME_CAP_BARS = 200


def load_h4(symbol):
    path = os.path.join(DATA_DIR, f"{symbol}_H4.csv")
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    close = df["close"].values
    ema50_h4 = ema(close, 50)
    return df["time"].values.astype("datetime64[s]").astype(np.int64), ema50_h4, close


def wilder_adx(high, low, close, period=14):
    n = len(close)
    up_move = np.zeros(n)
    down_move = np.zeros(n)
    up_move[1:] = high[1:] - high[:-1]
    down_move[1:] = low[:-1] - low[1:]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = np.full(n, np.nan)
    tr[0] = high[0] - low[0]
    tr[1:] = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))

    def smma(x, p):
        out = np.full(len(x), np.nan)
        if len(x) < p:
            return out
        out[p - 1] = np.nanmean(x[:p])
        for i in range(p, len(x)):
            out[i] = (out[i - 1] * (p - 1) + x[i]) / p
        return out

    atr_s, plus_s, minus_s = smma(tr, period), smma(plus_dm, period), smma(minus_dm, period)
    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di = 100.0 * plus_s / atr_s
        minus_di = 100.0 * minus_s / atr_s
        dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = np.full(n, np.nan)
    valid = ~np.isnan(dx)
    if valid.any():
        first = int(np.argmax(valid))
        adx[first:] = smma(dx[first:], period)
    return adx


def build_pullback_dataset(df, symbol, touch_atr_mult=0.25, confirm_bars=5):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    tick_vol = df["tick_volume"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)
    adx14 = wilder_adx(high, low, close, 14)
    n = len(df)
    vol_avg20 = pd.Series(tick_vol).rolling(20, min_periods=20).mean().values

    h4_time, h4_ema50, h4_close = load_h4(symbol)
    bar_times = df["time"].values.astype("datetime64[s]").astype(np.int64)
    h4_idx = np.searchsorted(h4_time, bar_times + 15 * 60, side="right") - 2
    h4_idx = np.clip(h4_idx, 0, len(h4_time) - 1)
    h4_trend_up = h4_close[h4_idx] > h4_ema50[h4_idx]

    GOLD_POINT_placeholder = None
    _, point = load_m15(symbol)

    rows = []
    i = 210
    while i < n - 1:
        if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(m200[i]) or np.isnan(vwap[i])
                or np.isnan(atr[i]) or atr[i] <= 0):
            i += 1
            continue
        above200 = close[i] > m200[i]
        below200 = close[i] < m200[i]
        direction = 0
        if above200 and vwap[i] > m200[i] and m21[i] > vwap[i] and m50[i] > vwap[i]:
            direction = 1
        elif below200 and vwap[i] < m200[i] and m21[i] < vwap[i] and m50[i] < vwap[i]:
            direction = -1
        if direction == 0:
            i += 1
            continue

        tol = touch_atr_mult * atr[i]
        touched_21 = abs(close[i] - m21[i]) <= tol
        touched_50 = abs(close[i] - m50[i]) <= tol
        if not (touched_21 or touched_50):
            i += 1
            continue
        ref_ma = m21 if touched_21 else m50

        resolve_i = None
        for j in range(i + 1, min(i + confirm_bars + 1, n)):
            if np.isnan(atr[j]) or atr[j] <= 0:
                continue
            if direction > 0 and close[j] > ref_ma[j] + 0.1 * atr[j]:
                resolve_i = j
                break
            if direction < 0 and close[j] < ref_ma[j] - 0.1 * atr[j]:
                resolve_i = j
                break
        if resolve_i is None:
            i += 1
            continue

        fill_i = resolve_i + 1
        if fill_i >= n or np.isnan(atr[fill_i]) or atr[fill_i] <= 0:
            i += 1
            continue

        # features at the touch bar i
        pullback_depth_atr = abs(close[i] - ref_ma[i]) / atr[i]
        prior_trend_strength_atr = direction * (close[i] - m200[i]) / atr[i]
        dist_200ema_atr = direction * (close[i] - m200[i]) / atr[i]
        h4_aligned = 1 if (h4_trend_up[i] == (direction > 0)) else 0
        adx_val = adx14[i]
        vol_ratio = tick_vol[i] / vol_avg20[i] if not np.isnan(vol_avg20[i]) and vol_avg20[i] > 0 else np.nan
        confirm_bars_used = resolve_i - i

        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)
        best = entry_px
        exit_i, exit_px = None, None
        for k in range(fill_i, hard_limit + 1):
            if np.isnan(atr[k]) or atr[k] <= 0:
                continue
            if direction > 0:
                if close[k] > best:
                    best = close[k]
                trail = best - 2.0 * atr[k]
                if low[k] <= trail and k > fill_i:
                    exit_i, exit_px = k, trail
                    break
            else:
                if close[k] < best:
                    best = close[k]
                trail = best + 2.0 * atr[k]
                if high[k] >= trail and k > fill_i:
                    exit_i, exit_px = k, trail
                    break
        if exit_i is None:
            exit_i, exit_px = hard_limit, close[hard_limit]
        pnl_pct = ((exit_px - entry_px) / entry_px) * direction * 100

        rows.append(dict(i=i, dir=direction, pullback_depth_atr=pullback_depth_atr,
                          prior_trend_strength_atr=prior_trend_strength_atr,
                          dist_200ema_atr=dist_200ema_atr, h4_trend_aligned=h4_aligned,
                          adx14=adx_val, vol_ratio=vol_ratio, confirm_bars_used=confirm_bars_used,
                          pnl_pct=pnl_pct))
        i = exit_i + 1

    return pd.DataFrame(rows)


def report_feature(dfc, feature, target="pnl_pct", n_bins=5):
    sub = dfc[[feature, target]].dropna()
    if len(sub) < 50:
        print(f"  {feature}: insufficient data (n={len(sub)})")
        return
    corr = sub[feature].corr(sub[target])
    try:
        sub = sub.copy()
        sub["bin"] = pd.qcut(sub[feature], n_bins, duplicates="drop")
        grouped = sub.groupby("bin", observed=True)[target].agg(["mean", "count"])
    except Exception:
        grouped = None
    print(f"\n  {feature}  (corr with {target} = {corr:+.4f}, n={len(sub)})")
    if grouped is not None:
        for b, row in grouped.iterrows():
            print(f"    {str(b):28s}  avg_pnl%={row['mean']:7.3f}  n={int(row['count'])}")


if __name__ == "__main__":
    df, point = load_m15("GOLD")
    n = len(df)
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    print(f"GOLD M15 IN-SAMPLE only: {df_is['time'].iloc[0]} .. {df_is['time'].iloc[-1]}")

    dfc = build_pullback_dataset(df_is, "GOLD")
    print(f"\nTotal pullback trades: {len(dfc)}")
    print(f"Baseline avg pnl%: {dfc['pnl_pct'].mean():.3f}%   win rate: {100*(dfc['pnl_pct']>0).mean():.1f}%")

    print(f"\n{'='*100}\nFEATURE BREAKDOWN (quintiles, target = realized trade pnl%)\n{'='*100}")
    for feat in ["pullback_depth_atr", "prior_trend_strength_atr", "dist_200ema_atr",
                 "adx14", "vol_ratio", "confirm_bars_used"]:
        report_feature(dfc, feat)

    print(f"\n{'='*100}\nH4 TREND ALIGNMENT (binary)\n{'='*100}")
    aligned = dfc[dfc["h4_trend_aligned"] == 1]["pnl_pct"]
    not_aligned = dfc[dfc["h4_trend_aligned"] == 0]["pnl_pct"]
    print(f"  aligned avg={aligned.mean():.3f}% (n={len(aligned)})   not-aligned avg={not_aligned.mean():.3f}% (n={len(not_aligned)})")

    print(f"\n{'='*100}\nLONG vs SHORT\n{'='*100}")
    print(f"  longs avg={dfc[dfc['dir']>0]['pnl_pct'].mean():.3f}% (n={(dfc['dir']>0).sum()})")
    print(f"  shorts avg={dfc[dfc['dir']<0]['pnl_pct'].mean():.3f}% (n={(dfc['dir']<0).sum()})")
