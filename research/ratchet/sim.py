"""
Sequential, single-position bar-level simulator of Ratchet_EA.mq5 (v3.28).

Why a SEQUENTIAL simulator and not a static trade-level filter: Ratchet's
OnTick() returns before the entry block whenever one of its own positions is
open ("return; // one position at a time"), and every exit feeds three pieces
of state that gate the NEXT entry - InpCooldown (g_barsSinceClose), and the
consecutive-loss breaker (g_consecLosses -> g_breakerBarsLeft=24 after 3
losses). So removing or adding a single entry changes which later setups are
even allowed to fire. That is exactly the cascade MSG_Trader_EA.mq5's v1.13 ->
v1.15 history learned the hard way; any candidate filter here is only judged
through this simulator, never by deleting rows from a real trade list.

Event order per M5 bar t (index t = the bar that just OPENED; MQL shift 1 =
bar t-1), ported line-by-line from OnTick():
  1. WeekendStillOpen (tick-level, BEFORE the new-bar gate): once server time
     is past Fri InpFridayCloseHour(+DST adj) and the trade opened before it,
     close at the first tick = this bar's open.
  2. new bar: g_barsSinceClose++, g_breakerBarsLeft--, g_entryBarCount++.
  3. position open -> NearSessionClose(5) flatten, TailLossHit, TrailStop
     (peak tracked ONLY at bar-open prices - TrailStop runs once per bar, so
     g_peakFavPx is the best bar-open bid/ask, not the intrabar extreme),
     Stochastic signal-line exit, MAXBARS; then return (no entry).
  4. flat -> cooldown, breaker, NearSessionClose(30), FridayCutoff(true),
     IsMarketHoliday, spread, Aligned, Touched21 / FreshAligned (momentum),
     candle, slope, Bollinger, max-dist, wick-reject -> market entry at the
     open (buy at ask = open+spread, sell at bid = open), SL = 1.75 x iATR.
  5. intrabar: the resting broker SL (long: bid low <= SL; short: ask high =
     high+spread >= SL), filled at the SL or at the open if gapped through.

All P/L is USD per 0.01 lot (1 oz): price move x 1.0.
"""
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

import numpy as np
import pandas as pd

import bars as B

POINT = B.POINT
WIN_START = pd.Timestamp("2026-01-01")
WIN_END = pd.Timestamp("2026-09-21")


@dataclass
class RP:
    touch_atr: float = 0.20
    touch_bars: int = 4
    need_candle: bool = True
    need_slope: bool = True
    min_slope: float = 0.05
    use_bands: bool = True
    bb_max_pos: float = 1.00
    max_dist_atr: float = 0.0
    wick: bool = True
    wick_ratio: float = 1.5
    momentum: bool = True
    mom_run: int = 8
    cooldown: int = 1
    max_consec: int = 3
    breaker_bars: int = 24
    klevel: float = 95.0
    stop_atr: float = 1.75
    trail: bool = True
    trail_trig: float = 0.5
    keep: float = 0.30
    trail_runner_atr: float = 0.0    # v3.30 InpTrailRunnerATR (0=off, matches v3.28/v3.29 byte-for-byte)
    trail_runner_keep: float = 0.60  # v3.30 InpTrailRunnerKeep
    be: bool = True
    be_trig: float = 0.3
    be_buf: float = 0.0
    max_bars: int = 80
    max_spread: int = 60
    tail_atr: float = 2.5
    no_entry_mins: int = 30
    close_mins: int = 5
    close_before_break: bool = True
    fri_close: int = 22
    fri_noentry: int = 20
    min_dist_pts: int = 0
    entry_from_min: int = 65                     # no real entry in any of the four reports before 01:05 server time
    # execution model (see noise.py): empirical real-vs-bar-open entry
    # offsets (tester random execution delay) and SL-fill slippage, both
    # measured on the 1,353 bar-matched trades of the two real reports
    entry_noise: Optional[np.ndarray] = None     # per-trade draws (x ATR), +ve = worse fill
    sl_slip: Optional[np.ndarray] = None         # per-SL-fill draws (x ATR at entry), <=0 (worse)
    noise_in_atr: bool = True                    # False = draws are raw USD (the 2026-only model)
    seed: int = 0
    # candidate hooks (None = shipped behavior)
    entry_filter: Optional[Callable] = None      # f(ctx, t, dir, kind) -> bool (True = allow)
    stop_mult_fn: Optional[Callable] = None      # f(ctx, t, dir, kind) -> stop_atr override
    keep_fn: Optional[Callable] = None           # f(trade_state) -> keep fraction override
    exit_fn: Optional[Callable] = None           # f(ctx, t, pos) -> reason or None, RESEARCH HOOK
                                                  # ONLY (never part of the real EA) - checked right
                                                  # after SESSION_CLOSE and before TAILCAP/trail/STOCH/
                                                  # MAXBARS, e.g. a divergence-exit candidate
                                                  # (research/divergence.py + divergence_exit_test.py).
                                                  # None (default) leaves every baseline byte-identical.


BASELINE = RP(wick=False, momentum=False)        # Backtest_1's config
V328 = RP()                                      # v3.28 defaults = Backtest_2's config (kept for history)
SHIPPED = RP(momentum=False, trail_runner_atr=6.0, trail_runner_keep=0.60)
# v3.30 real shipped defaults (Ratchet_EA.mq5 InpUseMomentumEntry=false
# real-confirmed v3.29; InpTrailRunnerATR=6.0/InpTrailRunnerKeep=0.60 real-
# confirmed v3.30). SHIPPED previously pointed at the stale v3.28 config
# (momentum=True, no trail-runner) - fixed here so every file that imports
# S.SHIPPED gets the CURRENT real defaults on its next run, not v3.28's.


def build_ctx(df=None):
    df = B.load_m5() if df is None else df
    o, h, l, c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
    ctx = dict(df=df, time=df["time"], t64=df["time"].values, o=o, h=h, l=l, c=c,
               spread=df["spread"].values.astype(float))
    ctx["m21"], ctx["m50"], ctx["m150"] = B.ema(c, 21), B.ema(c, 50), B.ema(c, 150)
    ctx["m600"], ctx["m2400"] = B.sma(c, 600), B.ema(c, 2400)
    ctx["atr"] = B.mt5_atr(h, l, c, 14)
    ctx["sto_main"], ctx["sto"] = B.mt5_stoch_signal(h, l, c, 5, 3, 3)
    ctx["bb_mid"], ctx["bb_up"], ctx["bb_lo"] = B.mt5_bands(c, 20, 2.0)
    m21, m50, m150, m600, m2400 = ctx["m21"], ctx["m50"], ctx["m150"], ctx["m600"], ctx["m2400"]
    ctx["al_up"] = (c > m2400) & (m21 > m50) & (m50 > m150) & (m150 > m600)
    ctx["al_dn"] = (c < m2400) & (m21 < m50) & (m50 < m150) & (m150 < m600)
    tm = df["time"]
    ctx["hour"] = tm.dt.hour.values
    ctx["minute"] = tm.dt.minute.values
    ctx["mod"] = ctx["hour"] * 60 + ctx["minute"]
    ctx["dow"] = ((tm.dt.dayofweek + 1) % 7).values          # MQL: Sun=0 .. Sat=6
    ctx["date"] = tm.dt.date.values
    hol = set()
    for y in range(tm.dt.year.min(), tm.dt.year.max() + 1):
        hol |= B.holidays(y)
    ctx["holiday"] = np.array([d in hol for d in ctx["date"]])
    ctx["dst"] = np.array([B.dst_gap_adj(pd.Timestamp(d)) for d in ctx["date"]])
    # minutes to the 24:00 session close (the broker session table; the real
    # reports' EA-initiated closes cluster at exactly the 23:55 bar open)
    ctx["mins_to_close"] = 24 * 60 - (ctx["hour"] * 60 + ctx["minute"])
    # Friday weekend-flatten deadline per bar (ns), evaluated like WeekendStillOpen
    days_since_fri = (ctx["dow"] - 5 + 7) % 7
    fri = (tm.dt.normalize() - pd.to_timedelta(days_since_fri, unit="D"))
    fri_adj = np.array([B.dst_gap_adj(pd.Timestamp(x)) for x in fri.dt.date.values])
    ctx["fri_date"] = fri.values
    ctx["fri_adj"] = fri_adj
    return ctx


def weekend_deadline(ctx, t, p):
    """Most recent Friday InpFridayCloseHour(+adj):00 at or before bar t."""
    dl = ctx["fri_date"][t] + np.timedelta64(int(p.fri_close + ctx["fri_adj"][t]), "h")
    if dl > ctx["t64"][t]:
        dl = dl - np.timedelta64(7, "D")
    return dl


def touched21(ctx, t, up, p):
    s = t - 1
    c, m21, atr = ctx["c"], ctx["m21"], ctx["atr"]
    if up and c[s] <= m21[s]:
        return False
    if (not up) and c[s] >= m21[s]:
        return False
    tol = atr[s] * p.touch_atr
    for j in range(1, p.touch_bars + 1):
        k = t - j
        if up and ctx["l"][k] <= m21[k] + tol:
            return True
        if (not up) and ctx["h"][k] >= m21[k] - tol:
            return True
    return False


def fresh_aligned(ctx, t, up, p):
    al = ctx["al_up"] if up else ctx["al_dn"]
    return bool(al[t - 1]) and not bool(al[t - 1 - p.mom_run])


def entry_signal(ctx, t, p, stats=None):
    """Everything from `bool up = Aligned(1,true)` down to the wick check.
    Returns (dir, kind) or None. kind = 'pullback' | 'momentum'."""
    up = bool(ctx["al_up"][t - 1])
    dn = bool(ctx["al_dn"][t - 1])
    if not up and not dn:
        return None
    kind = None
    if touched21(ctx, t, up, p):
        kind = "pullback"
    elif p.momentum and fresh_aligned(ctx, t, up, p):
        kind = "momentum"
    if kind is None:
        return None
    s = t - 1
    atr = ctx["atr"][s]
    if not (atr > 0):
        return None
    d = 1 if up else -1
    o1, c1, h1, l1 = ctx["o"][s], ctx["c"][s], ctx["h"][s], ctx["l"][s]
    if p.need_candle and (c1 - o1) * d <= 0.0:
        return None
    if p.need_slope and ((ctx["m21"][s] - ctx["m21"][s - 1]) * d) / atr < p.min_slope:
        return None
    if p.use_bands:
        up_b, lo_b = ctx["bb_up"][s], ctx["bb_lo"][s]
        if up_b - lo_b > 0:
            bp = (c1 - lo_b) / (up_b - lo_b)
            bp = bp if up else 1.0 - bp
            if bp > p.bb_max_pos:
                return None
    if p.max_dist_atr > 0 and abs(c1 - ctx["m21"][s]) / atr > p.max_dist_atr:
        return None
    if p.wick:
        body = abs(c1 - o1)
        wick = (min(o1, c1) - l1) if up else (h1 - max(o1, c1))
        if body <= 0.0 or wick < p.wick_ratio * body:
            if stats is not None:
                stats["blk_wick"] += 1
            return None
    return d, kind


def simulate(ctx, p=SHIPPED, start=WIN_START, end=WIN_END, record_signals=False):
    t64 = ctx["t64"]
    i0 = int(np.searchsorted(t64, np.datetime64(start)))
    i1 = int(np.searchsorted(t64, np.datetime64(end)))
    o, h, l, spread, atr, sto = ctx["o"], ctx["h"], ctx["l"], ctx["spread"], ctx["atr"], ctx["sto"]
    trades = []
    stats = dict(blk_wick=0, blk_filter=0, blk_breaker=0, signals=0)
    rng = np.random.default_rng(p.seed)
    pos = None
    bars_since_close = 9999
    breaker_left = 0
    consec = 0

    def close(t, px, reason, when=None):
        nonlocal pos, bars_since_close, breaker_left, consec
        pnl = (px - pos["entry"]) * pos["dir"]
        pos.update(exit_i=t, exit=px, pnl=pnl, reason=reason,
                   exit_time=when if when is not None else t64[t])
        trades.append(pos)
        if pnl >= 0.0:
            consec = 0
        else:
            consec += 1
            if p.max_consec > 0 and consec >= p.max_consec:
                breaker_left = p.breaker_bars
                consec = 0
        bars_since_close = 0
        pos = None

    for t in range(i0, i1):
        sp = spread[t] * POINT
        bid, ask = o[t], o[t] + sp
        # 1. weekend flatten (tick-level, ahead of the new-bar gate)
        if pos is not None:
            dl = weekend_deadline(ctx, t, p)
            if t64[t] >= dl and pos["entry_time"] < dl:
                close(t, bid if pos["dir"] > 0 else ask, "FRIDAY")
        # 2. new-bar counters
        if bars_since_close < 100000:
            bars_since_close += 1
        if breaker_left > 0:
            breaker_left -= 1
        if pos is not None:
            pos["bars"] += 1
        # 3. manage
        if pos is not None and ctx["hour"][t] == 0:
            pass    # outside the session table: EA-initiated closes/modifies are rejected; only the resting SL works
        elif pos is not None:
            d = pos["dir"]
            cur = bid if d > 0 else ask
            if p.close_before_break and 0 <= ctx["mins_to_close"][t] <= p.close_mins:
                close(t, cur, "SESSION_CLOSE"); continue
            if p.exit_fn is not None:
                r = p.exit_fn(ctx, t, pos)
                if r:
                    close(t, cur, r); continue
            if p.tail_atr > 0 and (pos["entry"] - cur) * d >= p.tail_atr * pos["atr"]:
                close(t, cur, "TAILCAP"); continue
            # TrailStop
            if d > 0:
                pos["peak"] = max(pos["peak"], cur)
            else:
                pos["peak"] = min(pos["peak"], cur)
            fav = (cur - pos["entry"]) * d
            best, have = pos["sl"], False
            keep = p.keep if p.keep_fn is None else p.keep_fn(pos)
            if p.trail and fav >= p.trail_trig * pos["atr"]:
                pf = (pos["peak"] - pos["entry"]) * d
                keep_eff = max(0.0, min(1.0, keep))
                # v3.30 InpTrailRunnerATR: once the best favorable move
                # reaches trail_runner_atr x entry ATR, lock in the (larger)
                # trail_runner_keep fraction instead - monotonic (MAX), so
                # this can only ever tighten, never loosen, the trail.
                if p.trail_runner_atr > 0.0 and pf >= p.trail_runner_atr * pos["atr"]:
                    keep_eff = max(keep_eff, max(0.0, min(1.0, p.trail_runner_keep)))
                cand = pos["entry"] + d * keep_eff * pf
                if (cand - best) * d > 0:
                    best, have = cand, True
            if p.be and fav >= p.be_trig * pos["atr"]:
                cand = pos["entry"] + d * p.be_buf * pos["atr"]
                if (cand - best) * d > 0:
                    best, have = cand, True
            if have:
                md = max(p.min_dist_pts, 1) * POINT
                best = min(best, cur - md) if d > 0 else max(best, cur + md)
                best = round(best, 2)
                if (best - pos["sl"]) * d > 0:
                    pos["sl"] = best
                    pos["trail_moves"] += 1
            sv = sto[t - 1]
            if not np.isnan(sv) and ((d > 0 and sv >= p.klevel) or (d < 0 and sv <= 100.0 - p.klevel)):
                close(t, cur, "STOCH"); continue
            if pos["bars"] >= p.max_bars:
                close(t, cur, "MAXBARS"); continue
        else:
            # 4. entry gates
            ok = True
            if bars_since_close < p.cooldown:
                ok = False
            elif p.max_consec > 0 and breaker_left > 0:
                stats["blk_breaker"] += 1
                ok = False
            elif 0 <= ctx["mins_to_close"][t] <= p.no_entry_mins:
                ok = False
            elif ctx["dow"][t] == 5 and ctx["hour"][t] >= p.fri_noentry + ctx["dst"][t]:
                ok = False
            elif ctx["holiday"][t]:
                ok = False
            elif ctx["mod"][t] < p.entry_from_min:
                ok = False
            elif p.max_spread > 0 and spread[t] > p.max_spread:
                ok = False
            if ok:
                sig = entry_signal(ctx, t, p, stats)
                if sig is not None:
                    d, kind = sig
                    stats["signals"] += 1
                    if p.entry_filter is not None and not p.entry_filter(ctx, t, d, kind):
                        stats["blk_filter"] += 1
                    else:
                        a = atr[t - 1]
                        sm = p.stop_atr if p.stop_mult_fn is None else p.stop_mult_fn(ctx, t, d, kind)
                        entry = ask if d > 0 else bid
                        if p.entry_noise is not None:
                            entry = round(entry + d * float(rng.choice(p.entry_noise)) * (a if p.noise_in_atr else 1.0), 2)
                        sl = round(entry - d * sm * a, 2)
                        pos = dict(entry_i=t, entry_time=t64[t], dir=d, kind=kind, entry=entry, sl=sl,
                                   sl0=sl, atr=a, peak=entry, bars=0, trail_moves=0)
        # 5. intrabar resting SL
        if pos is not None:
            d = pos["dir"]
            slip = (float(rng.choice(p.sl_slip)) * (pos["atr"] if p.noise_in_atr else 1.0)
                    if p.sl_slip is not None else 0.0)
            if d > 0 and l[t] <= pos["sl"]:
                close(t, (min(pos["sl"], o[t]) if pos["entry_i"] != t else pos["sl"]) + slip, "SL")
            elif d < 0 and h[t] + sp >= pos["sl"]:
                close(t, (max(pos["sl"], ask) if pos["entry_i"] != t else pos["sl"]) - slip, "SL")
    if pos is not None:
        close(i1 - 1, ctx["c"][i1 - 1], "END")
    return trades, stats


def stats_of(trades):
    pn = np.array([x["pnl"] for x in trades]) if trades else np.zeros(0)
    gp, gl = pn[pn > 0].sum(), -pn[pn < 0].sum()
    eq = np.cumsum(pn)
    dd = (np.maximum.accumulate(np.concatenate(([0.0], eq)))[1:] - eq).max() if len(pn) else 0.0
    return dict(n=len(pn), net=round(float(pn.sum()), 2), pf=round(gp / gl, 3) if gl > 0 else float("inf"),
                win=round(100.0 * (pn >= 0).mean(), 1) if len(pn) else 0.0, closed_dd=round(float(dd), 2))
