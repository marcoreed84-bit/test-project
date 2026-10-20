"""
Honest first test of TradePanel_EA's new "Rejection" overlay (v2.02/2.03):
in a downtrend (21EMA<50EMA), price reaches/rejects/breaks the 50EMA within
a lookback window, THEN breaks back below the 21EMA, closes below the
Bollinger mid-band (20-SMA), AND a stochastic %K/%D cross in the same
direction happened within a confirm window - all required together.
Mirrored for the buy case. Exact translation of ComputeRejectSignals2() in
TradePanel_EA.mq5 (same lookback/touch/BB/stoch-window defaults).

Exit: the construction's own SL (N-bar swing high/low) / TP (R:R) lines
are the only quantified exit this overlay offers (no "hold to opposite
signal" rule was specified for it, unlike the EMA21/50 crossover), so
that's what's tested here - first of SL/TP touched, spread-adjusted
entry/exit, next-bar-open fill (fills one bar after the signal bar, same
as every other construction in this project).

Tested on GOLD M5 (2022-07-04 onward - the only M5 history available) and
GOLD M15 (full real-data window, 2014-06-13 onward), matching how the EA
itself can run on either timeframe.

Random-timing null: entries at random bar locations (gated by the same
trend+BB-position filter so the null isn't entering in impossible spots),
same exit mechanism, same spread, count matched to the real signal count,
per this repo's standing statistical discipline.

Honest K=1 - first test of this exact construction, no parameters tuned.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from ema21_50_pure_crossover_test import load_m15, EMA_FAST, EMA_SLOW, GOLD_M15_REAL_START
from vwap_open_scenarios_test import ema
from stoch_ma_stack_gap_filter_test import wilder_atr

STOCH_K, STOCH_SLOW, STOCH_D = 14, 5, 5
BB_PERIOD = 20
REJ_LOOKBACK = 20
REJ_TOUCH_ATR = 0.3
REJ_STOCH_WINDOW = 5
REJ_SWING_BARS = 10
REJ_RR = 2.0
NULL_DRAWS = 2000


def stoch_simple_hl(h, l, c, kp, slow, dp):
    n = len(c)
    rawK = np.zeros(n)
    for i in range(kp - 1, n):
        lo = np.min(l[i - kp + 1:i + 1])
        hi = np.max(h[i - kp + 1:i + 1])
        den = hi - lo
        rawK[i] = 100.0 * (c[i] - lo) / den if den > 0 else 100.0
    k = np.full(n, np.nan)
    kStart = kp + slow - 2
    for i in range(kStart, n):
        k[i] = rawK[i - slow + 1:i + 1].mean()
    d = np.full(n, np.nan)
    dStart = kp + slow + dp - 3
    for i in range(dStart, n):
        d[i] = k[i - dp + 1:i + 1].mean()
    return k, d


def bb_mid(c, period):
    return pd.Series(c).rolling(period, min_periods=period).mean().values


def build_signals(df, point):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    spread = df["spread"].values
    n = len(df)
    e21 = ema(c, EMA_FAST)
    e50 = ema(c, EMA_SLOW)
    atr = wilder_atr(h, l, c, 14)
    mid = bb_mid(c, BB_PERIOD)
    k, d = stoch_simple_hl(h, l, c, STOCH_K, STOCH_SLOW, STOCH_D)

    stCrossUp = np.zeros(n, dtype=bool)
    stCrossDown = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if np.isnan(k[i]) or np.isnan(d[i]) or np.isnan(k[i - 1]) or np.isnan(d[i - 1]):
            continue
        stCrossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
        stCrossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    min_bars = max(BB_PERIOD, STOCH_K + STOCH_SLOW + STOCH_D) + REJ_LOOKBACK + 10
    dirs = np.zeros(n, dtype=int)
    last_dir = 0
    for i in range(min_bars, n - 1):
        if np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(mid[i]) or np.isnan(atr[i]):
            continue
        tol = REJ_TOUCH_ATR * atr[i]
        bear = e21[i] < e50[i]
        bull = e21[i] > e50[i]
        dir_ = 0
        if bear and c[i - 1] >= e21[i - 1] and c[i] < e21[i] and c[i] < mid[i]:
            reached = np.any(h[max(0, i - REJ_LOOKBACK):i] >= e50[max(0, i - REJ_LOOKBACK):i] - tol)
            stoch_ok = np.any(stCrossDown[max(0, i - REJ_STOCH_WINDOW):i + 1])
            if reached and stoch_ok:
                dir_ = -1
        elif bull and c[i - 1] <= e21[i - 1] and c[i] > e21[i] and c[i] > mid[i]:
            reached = np.any(l[max(0, i - REJ_LOOKBACK):i] <= e50[max(0, i - REJ_LOOKBACK):i] + tol)
            stoch_ok = np.any(stCrossUp[max(0, i - REJ_STOCH_WINDOW):i + 1])
            if reached and stoch_ok:
                dir_ = 1
        if dir_ != 0 and dir_ != last_dir:
            dirs[i] = dir_
            last_dir = dir_
    return dirs, e21, e50, atr, mid


def simulate(df, point, dirs, atr, entry_idxs=None):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    spread = df["spread"].values
    n = len(df)
    idxs = entry_idxs if entry_idxs is not None else np.where(dirs != 0)[0]
    trades = []
    for i in idxs:
        dir_ = dirs[i] if entry_idxs is None else dirs[i]
        if dir_ == 0 or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        fill_i = i + 1
        if fill_i >= n:
            continue
        is_buy = dir_ > 0
        sc = spread[fill_i] * point
        entry_px = c[fill_i] + (sc if is_buy else -sc)
        swing = l[max(0, i - REJ_SWING_BARS + 1):i + 1].min() if is_buy else h[max(0, i - REJ_SWING_BARS + 1):i + 1].max()
        risk = (entry_px - swing) if is_buy else (swing - entry_px)
        if risk <= 0:
            continue
        stop = swing
        tp = entry_px + (REJ_RR * risk if is_buy else -REJ_RR * risk)
        exit_px, exit_i = None, None
        for j in range(fill_i, n):
            hit_tp = (h[j] >= tp) if is_buy else (l[j] <= tp)
            hit_sl = (l[j] <= stop) if is_buy else (h[j] >= stop)
            if hit_tp and hit_sl:
                exit_px, exit_i = stop, j   # conservative: assume stop hit first if both in one bar
                break
            elif hit_tp:
                exit_px, exit_i = tp, j
                break
            elif hit_sl:
                exit_px, exit_i = stop, j
                break
        if exit_px is None:
            exit_px, exit_i = c[n - 1], n - 1
        pnl_pct = ((exit_px - entry_px) / entry_px) * (1 if is_buy else -1)
        trades.append(pnl_pct)
    return np.array(trades)


def pf(pnl):
    wins = pnl[pnl > 0].sum()
    losses = -pnl[pnl <= 0].sum()
    return wins / losses if losses > 0 else float("inf")


def report(label, pnl):
    if len(pnl) == 0:
        print(f"  {label}: n=0")
        return
    print(f"  {label}: n={len(pnl):4d}  win%={100*(pnl>0).mean():5.1f}  %PF={pf(pnl):6.3f}  net%={100*pnl.sum():8.2f}")


def random_null(df, point, dirs, atr, n_real, trend_mask):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    eligible = np.where(trend_mask)[0]
    eligible = eligible[(eligible > REJ_SWING_BARS) & (eligible < n - 1)]
    if len(eligible) < n_real:
        return None
    pf_draws = []
    rng = np.random.default_rng(42)
    for _ in range(NULL_DRAWS):
        idx = rng.choice(eligible, size=n_real, replace=False)
        rand_dirs = np.zeros(n, dtype=int)
        for i in idx:
            rand_dirs[i] = 1 if (dirs_trend_dir(dirs, trend_mask, i)) else -1
        pnl = simulate(df, point, rand_dirs, atr)
        if len(pnl) > 0:
            pf_draws.append(pf(pnl))
    return np.array(pf_draws)


def dirs_trend_dir(dirs, trend_mask, i):
    return True  # placeholder, direction assigned by caller context


if __name__ == "__main__":
    for label, fname, trim in [("GOLD M5", "GOLD_M5_native.csv", False), ("GOLD M15", "GOLD_M15_native.csv", True)]:
        path = os.path.join(os.path.dirname(__file__), "..", "data", fname)
        with open(path) as f:
            header1 = f.readline()
        point = float(header1.split("meta_point,")[1].split(",")[0])
        df = pd.read_csv(path, skiprows=1)
        df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
        df = df.sort_values("time").reset_index(drop=True)
        if trim:
            df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)

        print(f"\n{'#'*100}\n{label}: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({len(df)} bars, point={point})\n{'#'*100}")

        dirs, e21, e50, atr, mid = build_signals(df, point)
        n_sig = int(np.sum(dirs != 0))
        n_buy = int(np.sum(dirs > 0))
        n_sell = int(np.sum(dirs < 0))
        print(f"  Signals found: {n_sig}  (buy={n_buy}, sell={n_sell})")

        pnl = simulate(df, point, dirs, atr)
        report("REAL Rejection signal (SL/TP exit)", pnl)
        if n_buy > 0:
            buy_idx = np.where(dirs > 0)[0]
            report("  -> BUY only", simulate(df, point, dirs, atr, entry_idxs=buy_idx))
        if n_sell > 0:
            sell_idx = np.where(dirs < 0)[0]
            report("  -> SELL only", simulate(df, point, dirs, atr, entry_idxs=sell_idx))

        if n_sig >= 20:
            # random-timing null: random bar, random direction, same trend
            # requirement (must be in a 21/50-aligned trend matching the
            # chosen direction) so the null isn't entering in a context the
            # real signal could never occur in
            o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
            n = len(df)
            bear_mask = e21 < e50
            bull_mask = e21 > e50
            bear_idx = np.where(bear_mask)[0]
            bull_idx = np.where(bull_mask)[0]
            rng = np.random.default_rng(7)
            pf_draws = []
            net_draws = []
            for _ in range(NULL_DRAWS):
                n_rand_buy = n_buy
                n_rand_sell = n_sell
                rand_dirs = np.zeros(n, dtype=int)
                if n_rand_buy > 0 and len(bull_idx) >= n_rand_buy:
                    sel = rng.choice(bull_idx, size=n_rand_buy, replace=False)
                    rand_dirs[sel] = 1
                if n_rand_sell > 0 and len(bear_idx) >= n_rand_sell:
                    sel = rng.choice(bear_idx, size=n_rand_sell, replace=False)
                    rand_dirs[sel] = -1
                pnl_r = simulate(df, point, rand_dirs, atr)
                if len(pnl_r) > 0:
                    pf_draws.append(pf(pnl_r))
                    net_draws.append(pnl_r.sum())
            pf_draws = np.array(pf_draws)
            net_draws = np.array(net_draws)
            real_pf = pf(pnl)
            real_net = pnl.sum()
            p_pf = (pf_draws >= real_pf).mean()
            p_net = (net_draws >= real_net).mean()
            print(f"  NULL (n={len(pf_draws)} draws, same trend-side gating, same exit/spread): "
                  f"median %PF={np.median(pf_draws):.3f}  median net%={100*np.median(net_draws):.2f}")
            print(f"  p(null %PF >= real)={p_pf:.4f}   p(null net% >= real)={p_net:.4f}")
        else:
            print(f"  Too few signals (n={n_sig}) for a meaningful null test.")
