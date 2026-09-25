"""
Same construction as m1_vwap_smma_cross_test.py (21/50 SMMA cross +
VWAP-band flare, target = next level / opposite band), re-tested on
real GOLD# M5 data (2023-01-03 -> 2026-08-14, ~3.5yrs, 256k bars) -
checking whether the pattern "should be more or less the same" across
timeframes, as directly asked (2026-09-25). Trimmed grid (the configs
that looked least-bad on M1) rather than the full sweep, to get a
same-session answer - full grid available on request.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E

POINT = E.POINT


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


def find_crosses(ma21, ma50):
    above = ma21 > ma50
    valid = ~np.isnan(ma21) & ~np.isnan(ma50)
    cross_up = above & ~np.concatenate(([False], above[:-1])) & valid
    cross_dn = (~above) & np.concatenate(([True], above[:-1])) & valid
    return cross_up, cross_dn


def walk(df, atr, spread, cross_up, cross_dn, vwap, upper, lower, width,
         flare_lookback, flare_ratio, target_mode, stop_atr, maxhold):
    n = len(df)
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    trades = []
    pos = None
    last_exit = -1
    for i in range(flare_lookback + 5, n - 1):
        if i < last_exit:
            continue
        if pos is not None:
            hit_stop = (low[i] <= pos["stop"]) if pos["dir"] > 0 else (high[i] >= pos["stop"])
            hit_tgt = (high[i] >= pos["target"]) if pos["dir"] > 0 else (low[i] <= pos["target"])
            timed_out = i >= pos["entry_i"] + maxhold
            if hit_stop:
                px, reason = pos["stop"], "STOP"
            elif hit_tgt:
                px, reason = pos["target"], "TARGET"
            elif timed_out:
                px, reason = close[i], "TIME"
            else:
                continue
            pnl = (px - pos["entry_px"]) * pos["dir"]
            trades.append(dict(entry_i=pos["entry_i"], exit_i=i, dir=pos["dir"], pnl=pnl))
            pos = None
            last_exit = i
            continue
        a = atr[i]
        if a <= 0 or np.isnan(a) or np.isnan(width[i]) or np.isnan(width[i - flare_lookback]) or width[i - flare_lookback] <= 0:
            continue
        if (width[i] / width[i - flare_lookback]) < flare_ratio:
            continue
        fill_i = i + 1
        if fill_i >= n:
            continue
        entry_px = close[i]
        sp = spread[fill_i] * POINT if fill_i < len(spread) else spread[i] * POINT
        if cross_up[i]:
            target = (upper[i] if target_mode == "opposite_band"
                      else (vwap[i] if entry_px < vwap[i] else upper[i]))
            stop = entry_px - stop_atr * a
            if target > entry_px + sp:
                pos = dict(dir=1, entry_i=i, entry_px=entry_px + sp, stop=stop, target=target)
        elif cross_dn[i]:
            target = (lower[i] if target_mode == "opposite_band"
                      else (vwap[i] if entry_px > vwap[i] else lower[i]))
            stop = entry_px + stop_atr * a
            if target < entry_px - sp:
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


if __name__ == "__main__":
    df = E.load_m5()
    n = len(df)
    days = (df["time"].max() - df["time"].min()).days
    atr = E.wilder_atr(df["high"].values, df["low"].values, df["close"].values, 14)
    spread = df["spread"].values.astype(float)
    close = df["close"].values
    print(f"M5 data: n={n} bars (~{days} days)\n")

    ma21 = E.smma(close, 21)
    ma50 = E.smma(close, 50)
    cross_up, cross_dn = find_crosses(ma21, ma50)
    print(f"raw 21/50 SMMA crosses: {cross_up.sum()} up, {cross_dn.sum()} down "
          f"({(cross_up.sum()+cross_dn.sum())/days:.2f}/day)\n")

    vwap = E.session_vwap(df)

    print("Trimmed grid (configs that looked least-bad on M1)")
    for k_band in (1.5, 2.0):
        upper, lower = vwap_bands(df, vwap, k_band)
        width = upper - lower
        for flare_lookback in (20, 40):
            for flare_ratio in (1.1, 1.3):
                for target_mode in ("next_level", "opposite_band"):
                    for stop_atr in (1.0, 1.5):
                        trades = walk(df, atr, spread, cross_up, cross_dn, vwap, upper, lower, width,
                                      flare_lookback, flare_ratio, target_mode, stop_atr, 48)
                        label = (f"k={k_band} flare_lb={flare_lookback} flare_r={flare_ratio} "
                                 f"tgt={target_mode} stop={stop_atr}")
                        report(label, trades, n, days)
