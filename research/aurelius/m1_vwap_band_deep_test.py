"""
Deeper VWAP-band M1 retest, pushed back on directly (2026-09-25: "there
must be a way to scalp gold even on the 1minute between the vwap and the
outer bands"). The two prior VWAP-band+stochastic sweeps (wide k=1.5-2.5,
then M1-tight k=0.5-1.25 - 48 configs total) were both clean rejections,
but both used the SAME hypothesis (pure mean-reversion, no session filter,
no bigger-trend context). This tests four things not yet tried:

  A) High-liquidity-hour filter (hours 4,16,17,18 by real M1 tick_volume,
     the same filter that helped m1_scalp_test.py's trend+bounce signal)
     applied to the existing VWAP-band+stochastic re-entry construction.
  B) Trading WITH the bigger trend instead of blind reversion: only take
     a long band re-entry when a 600-period EMA (~10h on M1) is sloping
     up, short only when sloping down - i.e. use the band touch as a
     PULLBACK entry in the direction of the dominant trend (this project's
     "one bull market, one instrument" framing means blind mean-reversion
     fights that trend on the long side of the data by construction).
  C) Pure band-touch fade, NO stochastic requirement - isolates whether
     the stochastic filter itself was ever the problem.
  D) The OPPOSITE hypothesis: trade the BREAKOUT beyond a band as
     continuation/momentum (not the reversion back in) - gold trending
     hard could mean breakouts through the band keep going, not revert.

Same real GOLD# M1 data, same sequential single-position walk-forward
discipline, real spread on entry, as every other screen this session.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/msg")
import numpy as np
import pandas as pd
import engine as E
import sim as M

POINT = E.POINT


def stochastic_553(high, low, close, k_period=5, d_period=3, slow=3):
    hh = pd.Series(high).rolling(k_period).max()
    ll = pd.Series(low).rolling(k_period).min()
    rng = (hh - ll).replace(0, np.nan)
    raw_k = 100.0 * (pd.Series(close) - ll) / rng
    k = raw_k.rolling(slow).mean()
    d = k.rolling(d_period).mean()
    return k.values, d.values


def vwap_bands(df, vwap, k):
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    date = df["time"].dt.date
    dev2 = (typical - vwap) ** 2
    v = df["tick_volume"].astype(float)
    cum_wdev2 = (dev2 * v).groupby(date).cumsum()
    cum_v = v.groupby(date).cumsum()
    var = (cum_wdev2 / cum_v).values
    sd = np.sqrt(np.maximum(var, 0))
    return vwap + k * sd, vwap - k * sd


def walk(df, atr, spread, k_band, stop_atr, tp_atr, maxhold, target_mode,
         require_stoch, mode, hour_filter, trend_ema, trend_dir):
    """mode: 'reentry' (fade back toward VWAP) or 'breakout' (continuation).
    target_mode: 'vwap' or 'atr' (k_band's ATR multiple from entry).
    trend_dir: None, or +1/-1 slope array requiring alignment."""
    n = len(df)
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    hour = df["time"].dt.hour.values
    vwap = E.session_vwap(df)
    upper, lower = vwap_bands(df, vwap, k_band)
    kf, _ = stochastic_553(high, low, close)

    trades = []
    pos = None
    last_exit = -1
    for i in range(6, n - 1):
        if i < last_exit:
            continue
        if np.isnan(vwap[i]) or np.isnan(upper[i]) or np.isnan(kf[i]) or np.isnan(kf[i - 1]):
            continue
        if pos is not None:
            hit_stop = (low[i] <= pos["stop"]) if pos["dir"] > 0 else (high[i] >= pos["stop"])
            hit_tgt = (high[i] >= pos["target"]) if pos["dir"] > 0 else (low[i] <= pos["target"])
            timed_out = i >= pos["entry_i"] + maxhold
            if hit_stop and hit_tgt:
                px, reason = pos["stop"], "STOP"
            elif hit_stop:
                px, reason = pos["stop"], "STOP"
            elif hit_tgt:
                px, reason = pos["target"], "TARGET"
            elif timed_out:
                px, reason = close[i], "TIME"
            else:
                continue
            pnl = (px - pos["entry_px"]) * pos["dir"]
            trades.append(dict(entry_i=pos["entry_i"], exit_i=i, dir=pos["dir"], pnl=pnl, reason=reason))
            pos = None
            last_exit = i
            continue
        a = atr[i]
        if a <= 0 or np.isnan(a):
            continue
        if hour_filter is not None and int(hour[i]) not in hour_filter:
            continue
        if mode == "reentry":
            long_sig = (low[i] <= lower[i]) and (close[i] > lower[i]) and (close[i] < vwap[i])
            short_sig = (high[i] >= upper[i]) and (close[i] < upper[i]) and (close[i] > vwap[i])
        else:  # breakout continuation
            long_sig = (close[i] > upper[i]) and (close[i - 1] <= upper[i - 1])
            short_sig = (close[i] < lower[i]) and (close[i - 1] >= lower[i - 1])
        if require_stoch:
            stoch_up = kf[i] > kf[i - 1] and kf[i - 1] < 20
            stoch_dn = kf[i] < kf[i - 1] and kf[i - 1] > 80
            long_sig = long_sig and (stoch_up if mode == "reentry" else True)
            short_sig = short_sig and (stoch_dn if mode == "reentry" else True)
        if trend_dir is not None:
            td = trend_dir[i]
            if np.isnan(td):
                continue
            long_sig = long_sig and td > 0
            short_sig = short_sig and td < 0
        fill_i = i + 1
        if fill_i >= n:
            continue
        entry_px = close[i]
        sp = spread[fill_i] * POINT if fill_i < len(spread) else spread[i] * POINT
        if long_sig:
            stop = (lower[i] - stop_atr * a) if mode == "reentry" else (entry_px - stop_atr * a)
            target = vwap[i] if target_mode == "vwap" else entry_px + sp + tp_atr * a
            pos = dict(dir=1, entry_i=i, entry_px=entry_px + sp, stop=stop, target=target)
        elif short_sig:
            stop = (upper[i] + stop_atr * a) if mode == "reentry" else (entry_px + stop_atr * a)
            target = vwap[i] if target_mode == "vwap" else entry_px - sp - tp_atr * a
            pos = dict(dir=-1, entry_i=i, entry_px=entry_px - sp, stop=stop, target=target)

    return trades


def report(label, trades, n, days):
    if not trades:
        print(f"    {label}: 0 trades"); return None
    pnl = np.array([t["pnl"] for t in trades])
    entries = np.array([t["entry_i"] for t in trades])
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else float("inf")
    win = (pnl > 0).mean() * 100
    cutoff = int(n * 0.7)
    is_net = pnl[entries < cutoff].sum(); oos_net = pnl[entries >= cutoff].sum()
    print(f"    {label}: n={len(trades):4d} ({len(trades)/days:.2f}/day) net={pnl.sum():9.2f} pf={pf:6.3f} "
          f"win%={win:5.1f} IS={is_net:8.2f} OOS={oos_net:8.2f}")
    return pnl, entries


def block_check(pnl, entries, n, df):
    edges = np.linspace(0, n, 5).astype(int)
    pos = 0
    parts = []
    for b in range(4):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        netb = pnl[m].sum() if nb else 0.0
        if netb > 0: pos += 1
        parts.append(f"b{b+1}:{netb:.0f}({nb})")
    print(f"      blocks: {' '.join(parts)} -> {pos}/4 positive")


if __name__ == "__main__":
    df1 = M.load_bars()
    df1["time"] = pd.to_datetime(df1["time"])
    n1 = len(df1)
    days = (df1["time"].max() - df1["time"].min()).days
    atr1 = E.wilder_atr(df1["high"].values, df1["low"].values, df1["close"].values, 14)
    spread1 = df1["spread"].values.astype(float)
    close1 = df1["close"].values
    hour1 = df1["time"].dt.hour.values
    tick_vol1 = df1["tick_volume"].values.astype(float)
    print(f"M1 data: n={n1} bars (~{days} days)\n")

    by_hour = pd.Series(tick_vol1).groupby(hour1).mean()
    HIGH_LIQ = set(by_hour.sort_values(ascending=False).index[:4])
    print(f"high-liq hours: {sorted(HIGH_LIQ)}\n")

    ema600 = E.ema(close1, 600)
    trend_slope = pd.Series(ema600).diff(30).values / np.where(atr1 > 0, atr1, np.nan)
    trend_dir = np.where(trend_slope > 0.05, 1, np.where(trend_slope < -0.05, -1, np.nan))
    print(f"600-EMA trend filter: {np.sum(trend_dir==1)} up bars, {np.sum(trend_dir==-1)} down bars, "
          f"{np.sum(np.isnan(trend_dir))} flat/nan\n")

    print("=" * 78)
    print("A) reentry + stoch, HIGH-LIQ HOURS ONLY (k=0.75/1.0, stop=0.5-1.0xATR, target=VWAP)")
    for k in (0.75, 1.0, 1.25):
        for stop_atr in (0.5, 1.0):
            trades = walk(df1, atr1, spread1, k, stop_atr, 0.0, 15, "vwap", True, "reentry",
                          HIGH_LIQ, None, None)
            res = report(f"k={k} stop={stop_atr}", trades, n1, days)
            if res: block_check(*res, n1, df1)

    print("\n" + "=" * 78)
    print("B) reentry + stoch, WITH bigger-trend filter (600-EMA slope), no hour filter")
    for k in (0.75, 1.0, 1.25):
        for stop_atr in (0.5, 1.0):
            trades = walk(df1, atr1, spread1, k, stop_atr, 0.0, 15, "vwap", True, "reentry",
                          None, None, trend_dir)
            res = report(f"k={k} stop={stop_atr}", trades, n1, days)
            if res: block_check(*res, n1, df1)

    print("\n" + "=" * 78)
    print("B2) reentry + stoch, trend filter AND high-liq hours combined")
    for k in (0.75, 1.0, 1.25):
        for stop_atr in (0.5, 1.0):
            trades = walk(df1, atr1, spread1, k, stop_atr, 0.0, 15, "vwap", True, "reentry",
                          HIGH_LIQ, None, trend_dir)
            res = report(f"k={k} stop={stop_atr}", trades, n1, days)
            if res: block_check(*res, n1, df1)

    print("\n" + "=" * 78)
    print("C) pure band-touch fade, NO stochastic requirement, target=VWAP")
    for k in (0.75, 1.0, 1.25):
        for stop_atr in (0.5, 1.0):
            trades = walk(df1, atr1, spread1, k, stop_atr, 0.0, 15, "vwap", False, "reentry",
                          None, None, None)
            res = report(f"k={k} stop={stop_atr}", trades, n1, days)
            if res: block_check(*res, n1, df1)

    print("\n" + "=" * 78)
    print("D) BREAKOUT continuation (opposite hypothesis) - target = k x ATR beyond band")
    for k in (1.0, 1.5, 2.0):
        for stop_atr in (0.5, 1.0):
            for tp_atr in (0.5, 1.0, 1.5):
                trades = walk(df1, atr1, spread1, k, stop_atr, tp_atr, 15, "atr", False, "breakout",
                              None, None, None)
                res = report(f"k={k} stop={stop_atr} tp={tp_atr}xATR", trades, n1, days)
                if res: block_check(*res, n1, df1)
