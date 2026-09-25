"""
M1-native re-tune of the VWAP-band + stochastic reversal idea
(research/vwap_band_stoch_test.py), which failed cleanly on M15/M1 with WIDE
parameters (k=1.5-2.5 bands, 1.5xATR stop, VWAP/opposite-band target, PF
0.78-0.88 across all 12 configs). That test used the same band width and
stop/target distances regardless of timeframe - appropriate for M15's slower
character, but almost certainly far too wide for a true M1 scalp hold.

This script re-tunes the SAME construction (same VWAP-band definition, same
Ratchet-real stochastic(5,3,3), same entry rule: band re-entry + stoch
turning from the matching extreme) specifically for M1 noise:
  - tighter bands (k = 0.5, 0.75, 1.0, 1.25 - M1 range is much smaller bar-
    to-bar than M15, so k=1.5-2.5 rarely even gets touched intraday)
  - tighter stop (0.5x / 0.75x / 1.0x ATR beyond the band, not 1.5x)
  - a genuinely short scalp hold cap (5/10/15 minutes = bars, not "run to
    target/stop with no cap")
  - target = VWAP line only (the user's own worked example used VWAP as the
    target on both legs' first move; "opposite band" is a much bigger move,
    already shown weak)

Also reports raw trigger frequency (band-touch + stoch-turn coincidence) so
we know whether this construction can even reach the 5-15 trades/day the
user asked for BEFORE looking at whether it's profitable - a cheap way to
reject it early if frequency alone rules it out.

Sequential, single-position, walk-forward, no lookahead - same discipline as
every other real-data screen in this repo.
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


def count_triggers(df, atr, k_band):
    n = len(df)
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    vwap = E.session_vwap(df)
    upper, lower = vwap_bands(df, vwap, k_band)
    kf, _ = stochastic_553(high, low, close)
    n_long = n_short = 0
    for i in range(6, n - 1):
        if np.isnan(vwap[i]) or np.isnan(kf[i]) or np.isnan(kf[i - 1]):
            continue
        long_reentry = (low[i] <= lower[i]) and (close[i] > lower[i]) and (close[i] < vwap[i])
        short_reentry = (high[i] >= upper[i]) and (close[i] < upper[i]) and (close[i] > vwap[i])
        stoch_up = kf[i] > kf[i - 1] and kf[i - 1] < 20
        stoch_dn = kf[i] < kf[i - 1] and kf[i - 1] > 80
        if long_reentry and stoch_up:
            n_long += 1
        elif short_reentry and stoch_dn:
            n_short += 1
    return n_long, n_short


def run(df, atr, spread, k_band, stop_atr, maxhold_bars, label):
    n = len(df)
    close, high, low = df["close"].values, df["high"].values, df["low"].values
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
            timed_out = i >= pos["entry_i"] + maxhold_bars
            if hit_stop and hit_tgt:
                px, reason = pos["stop"], "STOP(amb)"
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
        long_reentry = (low[i] <= lower[i]) and (close[i] > lower[i]) and (close[i] < vwap[i])
        short_reentry = (high[i] >= upper[i]) and (close[i] < upper[i]) and (close[i] > vwap[i])
        stoch_up = kf[i] > kf[i - 1] and kf[i - 1] < 20
        stoch_dn = kf[i] < kf[i - 1] and kf[i - 1] > 80
        fill_i = i + 1
        if fill_i >= n:
            continue
        entry_px = close[i]
        sp = spread[fill_i] * POINT if fill_i < len(spread) else spread[i] * POINT
        if long_reentry and stoch_up:
            stop = lower[i] - stop_atr * a
            target = vwap[i]
            pos = dict(dir=1, entry_i=i, entry_px=entry_px + sp, stop=stop, target=target)
        elif short_reentry and stoch_dn:
            stop = upper[i] + stop_atr * a
            target = vwap[i]
            pos = dict(dir=-1, entry_i=i, entry_px=entry_px - sp, stop=stop, target=target)

    if not trades:
        print(f"  {label}: 0 trades")
        return None
    pnl = np.array([t["pnl"] for t in trades])
    entries = np.array([t["entry_i"] for t in trades])
    gp = pnl[pnl > 0].sum()
    gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else float("inf")
    win = (pnl > 0).mean() * 100
    cutoff = int(n * 0.7)
    is_net = pnl[entries < cutoff].sum()
    oos_net = pnl[entries >= cutoff].sum()
    print(f"  {label}: n={len(trades):4d} net={pnl.sum():9.2f} pf={pf:6.3f} win%={win:5.1f} "
          f"avg={pnl.mean():6.3f} IS={is_net:8.2f} OOS={oos_net:8.2f}")
    return dict(trades=trades, pnl=pnl, entries=entries)


if __name__ == "__main__":
    df1 = M.load_bars()
    df1["time"] = pd.to_datetime(df1["time"])
    n1 = len(df1)
    days = (df1["time"].max() - df1["time"].min()).days
    print(f"M1 data: {df1['time'].min()} -> {df1['time'].max()}, n={n1} bars (~{days} real days)\n")
    atr1 = E.wilder_atr(df1["high"].values, df1["low"].values, df1["close"].values, 14)
    spread1 = df1["spread"].values.astype(float)

    print("=" * 78)
    print("STEP 1: raw trigger frequency by band width (before profitability)")
    for k in (0.5, 0.75, 1.0, 1.25, 1.5):
        nl, ns = count_triggers(df1, atr1, k)
        total = nl + ns
        print(f"  k={k}: {total} triggers over ~{days} days -> {total/max(1,days):.2f}/day "
              f"({nl} long, {ns} short)")

    print("\n" + "=" * 78)
    print("STEP 2: PF grid, target=VWAP, tight stop, short hold cap")
    best = None
    for k in (0.5, 0.75, 1.0, 1.25):
        for stop_atr in (0.5, 0.75, 1.0):
            for maxhold, hlabel in ((5, "5min"), (10, "10min"), (15, "15min")):
                label = f"k={k} stop={stop_atr}xATR hold<={hlabel}"
                res = run(df1, atr1, spread1, k, stop_atr, maxhold, label)
                if res is not None:
                    net = res["pnl"].sum()
                    if best is None or net > best[0]:
                        best = (net, k, stop_atr, maxhold, res)

    if best is None:
        print("\nno trades resolved anywhere in the grid")
    else:
        net, k, stop_atr, maxhold, res = best
        print(f"\nbest cell: k={k} stop={stop_atr}xATR maxhold={maxhold} net={net:.2f} n={len(res['trades'])}")
        pnl, entries = res["pnl"], res["entries"]
        edges = np.linspace(0, n1, 5).astype(int)
        pos_blocks = 0
        for b in range(4):
            lo, hi = edges[b], edges[b + 1]
            m = (entries >= lo) & (entries < hi)
            nb = m.sum()
            if nb == 0:
                print(f"  block {b+1}: 0 trades")
                continue
            netb = pnl[m].sum()
            t0 = df1["time"].iloc[lo]
            t1 = df1["time"].iloc[min(hi, n1 - 1)]
            if netb > 0:
                pos_blocks += 1
            print(f"  block {b+1} [{t0.date()}->{t1.date()}]: n={nb} net={netb:.2f} win%={100*(pnl[m]>0).mean():.1f}")
        print(f"  -> positive in {pos_blocks}/4 blocks")
