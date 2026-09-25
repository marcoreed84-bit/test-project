"""
User's exact described construction (2026-09-25, with a real annotated M1
chart): VWAP outer bands FLARING OPEN (width expanding = volatility
entering an active/trending phase) + the 21 SMMA crossing the 50 SMMA
(MT5 MODE_SMMA - Wilder smoothing, same recursion as engine.py's own
smma(), NOT the EMA used everywhere else in this repo's Aurelius-based
work) as the entry trigger, targeting the NEXT VWAP/band level in the
cross's direction - not a reversion trade, a continuation/expansion
trade. This is genuinely different from every VWAP-band construction
tested so far this session (all of which were reversion-at-the-band
fades or fixed-width breakout continuations) - the trigger here is the
MA cross, gated by band expansion, not a band touch itself.

Two target modes tested:
  'next_level': the nearest untouched level in the cross's direction
    (VWAP if price hasn't reached it yet, else the far band) - the
    literal "target the next level/levels" wording.
  'opposite_band': the full round-trip move the user's own annotated
    chart showed (bottom outer band -> top outer band) - a bigger,
    more ambitious target.

"Flared open" = current band width (upper-lower) vs its own value
InpFlareLookback bars ago, ratio >= InpFlareRatio (band actively
widening, not just wide).

Real GOLD# M1 data, same sequential single-position walk-forward
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
    cross_dn = cross_dn & valid
    return cross_up, cross_dn


def walk(df, atr, spread, ma21, ma50, vwap, upper, lower, width,
         flare_lookback, flare_ratio, target_mode, stop_atr, maxhold):
    n = len(df)
    close = df["close"].values
    cross_up, cross_dn = find_crosses(ma21, ma50)

    trades = []
    pos = None
    last_exit = -1
    for i in range(flare_lookback + 5, n - 1):
        if i < last_exit:
            continue
        if pos is not None:
            high_i, low_i = df["high"].values[i], df["low"].values[i]
            hit_stop = (low_i <= pos["stop"]) if pos["dir"] > 0 else (high_i >= pos["stop"])
            hit_tgt = (high_i >= pos["target"]) if pos["dir"] > 0 else (low_i <= pos["target"])
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
        if a <= 0 or np.isnan(a) or np.isnan(width[i]) or np.isnan(width[i - flare_lookback]) or width[i - flare_lookback] <= 0:
            continue
        flaring = (width[i] / width[i - flare_lookback]) >= flare_ratio
        if not flaring:
            continue
        fill_i = i + 1
        if fill_i >= n:
            continue
        entry_px = close[i]
        sp = spread[fill_i] * POINT if fill_i < len(spread) else spread[i] * POINT
        if cross_up[i]:
            if target_mode == "opposite_band":
                target = upper[i]
            else:
                target = vwap[i] if entry_px < vwap[i] else upper[i]
            stop = entry_px - stop_atr * a
            if target > entry_px + sp:
                pos = dict(dir=1, entry_i=i, entry_px=entry_px + sp, stop=stop, target=target)
        elif cross_dn[i]:
            if target_mode == "opposite_band":
                target = lower[i]
            else:
                target = vwap[i] if entry_px > vwap[i] else lower[i]
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
    print(f"M1 data: n={n1} bars (~{days} days)\n")

    ma21 = E.smma(close1, 21)
    ma50 = E.smma(close1, 50)
    cross_up, cross_dn = find_crosses(ma21, ma50)
    print(f"raw 21/50 SMMA crosses: {cross_up.sum()} up, {cross_dn.sum()} down "
          f"({(cross_up.sum()+cross_dn.sum())/days:.2f}/day)\n")

    vwap1 = E.session_vwap(df1)

    print("=" * 78)
    print("Grid: k_band x flare_lookback x flare_ratio x target_mode x stop_atr")
    best = None
    for k_band in (1.5, 2.0, 2.5):
        upper, lower = vwap_bands(df1, vwap1, k_band)
        width = upper - lower
        for flare_lookback in (10, 20, 40):
            for flare_ratio in (1.1, 1.3, 1.5):
                flaring_count = 0
                for target_mode in ("next_level", "opposite_band"):
                    for stop_atr in (1.0, 1.5):
                        for maxhold in (120, 240):
                            trades = walk(df1, atr1, spread1, ma21, ma50, vwap1, upper, lower, width,
                                          flare_lookback, flare_ratio, target_mode, stop_atr, maxhold)
                            label = (f"k={k_band} flare_lb={flare_lookback} flare_r={flare_ratio} "
                                     f"tgt={target_mode} stop={stop_atr} hold<={maxhold}")
                            res = report(label, trades, n1, days)
                            if res:
                                pnl, entries = res
                                net = pnl.sum()
                                if len(trades) >= 20 and (best is None or net > best[0]):
                                    best = (net, label, pnl, entries)

    print("\n" + "=" * 78)
    if best is None:
        print("no cell with >=20 trades found anywhere in the grid")
    else:
        net, label, pnl, entries = best
        print(f"BEST (n>=20 trades): {label} net={net:.2f} n={len(pnl)}")
        block_check(pnl, entries, n1, df1)
