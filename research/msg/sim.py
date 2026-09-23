"""
Event-driven, strictly SINGLE-POSITION bar-by-bar replica of
MSG_Trader_EA.mq5 (v1.14 logic) on real GOLD# M1 bars.

This is NOT a vectorised / per-setup approximation.  It walks bars forward in
time order and holds exactly one position slot (the EA's g_ticket), so that
skipping, resizing or re-timing an entry changes which LATER setups can fire -
the single-position cascade that a static trade-level permutation test cannot
see (the lesson of v1.13 -> v1.14).

REAL ORDERING, ported from OnTick() (mq5 ~1854):
  OnTick only does work on the FIRST tick of a new bar (IsNewBar).  At the
  open of bar k (bar 1 = k-1 is the bar that just closed):
    1. UpdateSessionRanges(time[k-1], high[k-1], low[k-1])  - EVERY bar,
       flat or not.  A session window closing freezes the range, resets
       g_sesBiasDir/ext and g_sesRangeTraded.
    2. if g_ticket != 0: ManageOpenPosition()
         - SyncPositionState(): if the broker SL/TP closed the position
           intrabar earlier, g_ticket -> 0 and return.
         - max hold: TimeCurrent()-POSITION_TIME >= InpMaxHoldHours*3600 ->
           PositionClose at the market, return (g_ticket stays non-zero until
           the NEXT bar's Sync, so no re-entry on this same tick).
         - weekend guard (MinutesToFridayClose) - see WEEKEND GUARD below.
         - TP1 / TP2 partials are evaluated ONLY HERE, i.e. only against the
           bar-open price (Bid for a buy, Ask for a sell), never intrabar.
           TP1: close vol/3, SL -> entry.  TP2: close half the remainder.
           post-TP2: SL -> entry +/- InpTrailRR*risk, static (v1.11).
    3. if g_ticket == 0: CheckForEntry()
         - spread gate (SYMBOL_SPREAD at this tick > InpMaxSpreadPoints ->
           return BEFORE CheckSessionSetups, so no setup-state update).
         - CheckSessionSetups(close1, high1, low1) - NOTE this (and therefore
           every bias/extension/watch-expiry state update) only runs while
           FLAT.  A breakout that happens while a position is open is simply
           never seen; that is part of the real cascade and is reproduced.
         - fill at this tick: Ask = open[k] + spread for a buy, Bid = open[k]
           for a sell.  SL from StructuralOrFibSL, TP3 = px +/- 2R broker TP.
  Intrabar of bar k (INCLUDING the entry bar): the broker SL and TP3 are real
  orders.  Buy: SL if Bid low <= SL, TP if Bid high >= TP.  Sell: SL if
  Ask high (high + spread) >= SL, TP if Ask low <= TP.  Fills at the level
  (or at the open if the bar gapped through it).  If both are inside one bar
  the one nearer the open is assumed first (logged as `ambiguous`).

SERVER TIME == GMT for session hours: in the MT5 Strategy Tester
TimeGMT() == TimeTradeServer(), so BrokerGMTOffsetHours() is 0 and MSG3
09:00-12:00 GMT is 09:00-12:00 of the CSV's own (server) timestamps.  Real
Backtest_1 entries (13:50-16:16) are consistent with that.

WEEKEND GUARD: real Backtest_1 (v1.12, guard=30) still contains the 80.8h
2026-03-19 -> 2026-03-23 01:02 trade the guard was written to kill, closed by
the 48h timer on Monday - so in the real tester MinutesToFridayClose() never
returned a value in [0,30].  `weekend_guard_mode="as_observed"` (default)
therefore reproduces the REAL behaviour (a no-op); "intended" models what the
v1.12 code was meant to do (flatten from Friday 23:28, close 23:58).

Money is in USD (0.01 lot = 1 oz, contract 100): pnl = move * lots * 100.
Real reports are in ZAR; compare against report.round_trips()'s pnl_usd.

AURELIUS M5 TREND GATE (research for v1.17 - Params.trend_gate / trend_arr):
  optional, default "off" (= exact v1.14/v1.15/v1.16 behaviour).  trend_arr[k]
  is the real Aurelius_EA.mq5 Aligned(shift=1) state (+1 buy / -1 sell / 0
  neither) of the most recent CLOSED GOLD# M5 bar at the open of M1 bar k -
  exactly what iMA(_Symbol, PERIOD_M5, ..., shift=1) returns on the first tick
  of that M1 bar (see aurelius_alignment()).  "with" rejects a zone touch
  unless trend == trade dir; "not_against" rejects only trend == -dir.  A
  rejection `continue`s inside check_setups exactly like InRiskDeadZone: the
  range is NOT retired and bias/extension keep updating, so a later touch can
  still fire (re-timing).  Every rejection is logged (simulate(..., rej=[])).
"""
import datetime as dt
import math
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

import numpy as np
import pandas as pd

CSV = "/tmp/m1data/GOLD#_PERIOD_M1.csv"
PT = 0.01
CONTRACT = 100.0
LOT_STEP = 0.01


def load_bars(path=CSV):
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df


AURELIUS = "/home/user/test-project/research/aurelius"
M5_SWITCH = pd.Timestamp("2026-08-15")   # first M5 bar NOT in the real GOLD# M5 export


def load_m5_spliced(m1=None):
    """GOLD# M5 bars 2023-01-03 .. 2026-09-18 for the Aurelius gate.

    research/aurelius/engine.py's GOLD_M5.csv is (despite its file name) a real
    GOLD# export - its own header says meta_symbol=GOLD# - and it ENDS
    2026-08-14 23:55, five weeks before the M1 sim data does.  Resampling the
    GOLD# M1 CSV to 5 minutes reproduces that export EXACTLY on all 53,187
    overlapping bars (open/high/low/close/tick_volume, max |diff| 0.00, same bar
    set), so bars from M5_SWITCH on are appended from the M1 resample with no
    loss.  The export (not the resample) is kept before the switch because it
    starts in 2023: the 2400-EMA / 500-SMMA need that warm-up, and the M1 CSV
    only starts 2025-11-12 10:50 (the first HOLDOUT day)."""
    import sys
    if AURELIUS not in sys.path:
        sys.path.insert(0, AURELIUS)
    import engine as E
    m5 = E.load_m5()
    m1 = load_bars() if m1 is None else m1
    d = m1.set_index("time")
    r = pd.DataFrame(dict(open=d["open"].resample("5min").first(), high=d["high"].resample("5min").max(),
                          low=d["low"].resample("5min").min(), close=d["close"].resample("5min").last(),
                          tick_volume=d["tick_volume"].resample("5min").sum(),
                          real_volume=d["real_volume"].resample("5min").sum(),
                          spread=d["spread"].resample("5min").min())).dropna().reset_index()
    tail = r[r["time"] >= M5_SWITCH]
    out = pd.concat([m5[m5["time"] < M5_SWITCH][tail.columns], tail], ignore_index=True)
    return out.sort_values("time").reset_index(drop=True)


def aurelius_alignment(bars, m5=None, params=None, return_m5=False):
    """Per-M1-bar Aurelius trend state: +1 Aligned(buy), -1 Aligned(sell), 0 neither.

    Computed with research/aurelius/engine.py's own build_context() and its
    shipped v1.46 M5 defaults P (EMA21 > EMA50 > SMA250 > SMMA500, close vs
    EMA2400, ALIGN_MID - note engine.P's 'p150'/'p600' keys are 250/500, the
    real Aurelius_EA.mq5 inputs; the 150/600 names are legacy labels).

    Time basis: both series are GOLD# on the same server clock.  At the open of
    M1 bar k (time T, the tick CheckForEntry runs on), iMA(..PERIOD_M5.., shift=1)
    is the M5 bar BEFORE the one containing T, i.e. the last M5 bar whose open
    time is < floor(T, 5 min) - fully closed, 3-8 minutes old.

    GOLD vs GOLD#: every MA here is a normalised linear filter of close, so a
    constant bid offset (GOLD = GOLD# - 0.12, sim.Params docstring) shifts price
    and all five MAs by the same amount and leaves every comparison unchanged.
    Only the +-0.02 jitter in that offset could flip a near-tie; see
    run_aurelius_gate.py for how often that can matter."""
    import sys
    if AURELIUS not in sys.path:
        sys.path.insert(0, AURELIUS)
    import engine as E
    m5 = load_m5_spliced(bars) if m5 is None else m5
    ctx = E.build_context(m5, E.load_h4(), params or E.P)
    st5 = np.where(ctx["aligned_buy"], 1, np.where(ctx["aligned_sell"], -1, 0)).astype(np.int8)
    t5 = m5["time"].values.astype("datetime64[s]").astype(np.int64)
    t1 = bars["time"].values.astype("datetime64[s]").astype(np.int64)
    cur5 = (t1 // 300) * 300                       # open time of the M5 bar containing T
    j = np.searchsorted(t5, cur5, side="left") - 1  # last M5 bar with open < cur5 (shift 1)
    out = np.where(j >= 0, st5[np.clip(j, 0, None)], 0).astype(np.int8)
    if return_m5:
        return out, dict(m5=m5, ctx=ctx, idx=j)
    return out


@dataclass
class Params:
    lots: float = 0.03
    zone_top: float = 50.0
    zone_bot: float = 78.6
    range_risk: float = 30.8
    min_ext: float = 10.0
    watch_h: float = 4.25
    max_hold_h: float = 48.0
    tp1: float = 1.0
    tp2: float = 1.5
    tp3: float = 2.0
    trail: float = 1.0
    max_spread: float = 60.0
    sessions: tuple = ((9, 12),)          # MSG3 only - every real comparison run
    skip_dead: bool = False
    dz_min: float = 0.18
    dz_max: float = 0.26
    weekend_guard_min: int = 30
    weekend_guard_mode: str = "as_observed"   # or "intended"
    friday_close: tuple = (23, 58)
    # research hooks (None = exact v1.14 behaviour)
    entry_filter: Optional[Callable] = None   # ctx -> True to REJECT (like InRiskDeadZone: `continue`)
    size_fn: Optional[Callable] = None        # ctx -> lots
    # GOLD vs GOLD#: every real comparison report ran on symbol "GOLD", but the
    # only M1 bar export is "GOLD#".  Measured from the real Backtest_1/_2 order
    # tickets (requested px reconstructed exactly as (TP+2*SL)/3): GOLD's bid is
    # a near-constant 0.12 below GOLD#'s bar open (59/59 sells, -0.10..-0.14) and
    # GOLD's ask is 0.16 above GOLD#'s ask (34 buys, IQR tight) - i.e. GOLD is the
    # same mid with ~0.28 more spread.  0/0 reproduces GOLD# itself.
    # post-TP2 stop: "static" = v1.11+ (entry +/- trail*risk, set once),
    # "ratchet" = v1.09/v1.10 (bar-open price -/+ trail*risk, only tightens),
    # "none" = v1.07/v1.08 (breakeven at TP1 only).
    lock_mode: str = "static"
    # "bar_open" = v1.14 (OnTick returns unless IsNewBar, so TP1/TP2/BE/lock are
    # only evaluated on the first tick of each bar); "tick" = ManageOpenPosition()
    # on EVERY tick, modelled on the M1 OHLC path (see intrabar_tick()).
    manage_mode: str = "bar_open"
    fixed_fib_sl: bool = False           # InpFixedFibSL
    fib_sl_pct: float = 78.6             # InpFibSLPct
    # Tester fill slippage, measured on real Backtest_1 (93 entries, 74 stop exits):
    # entry mean +0.083 adverse, stop exits mean +0.223 adverse.  P/L only - SL/TP
    # levels are computed from the REQUESTED price, exactly as the EA does.
    slip_entry: float = 0.0
    slip_sl: float = 0.0
    bid_off: float = -0.12
    ask_extra: float = 0.16
    start: str = "2026-01-01"
    end: str = "2026-09-22"
    # Aurelius M5 trend gate - see module docstring and aurelius_alignment()
    trend_gate: str = "off"              # "off" | "with" | "not_against"
    trend_arr: Optional[np.ndarray] = None
    trend_kill: bool = False             # sensitivity only: a rejection RETIRES the range (not the EA's semantics)


def lot_round(v):
    # LotStep(): MathRound(v/step)*step, MathRound = half away from zero
    n = math.floor(v / LOT_STEP + 0.5 + 1e-9)
    return n * LOT_STEP


def hour_in_window(h, s, e):
    if s == e:
        return False
    if s < e:
        return s <= h < e
    return h >= s or h < e


class Sess:
    def __init__(self, s, e):
        self.s, self.e = s, e
        self.was_in = False
        self.fh = self.fl = 0.0
        self.H = self.L = 0.0
        self.valid = False
        self.start_t = self.end_t = None
        self.bias = 0
        self.ext_h = self.ext_l = 0.0
        self.ext_t = None
        self.traded = False
        self.gate_rej = 0       # trend-gate rejections on the CURRENT frozen range


def simulate(bars, p: Params = Params(), log=False, rej=None):
    if p.trend_gate != "off":
        assert p.trend_arr is not None and len(p.trend_arr) == len(bars), "trend_arr must be aurelius_alignment(bars)"
    t_arr = bars["time"].values.astype("datetime64[s]").astype(np.int64)
    o = bars["open"].values + p.bid_off
    h = bars["high"].values + p.bid_off
    l = bars["low"].values + p.bid_off
    c = bars["close"].values + p.bid_off
    sp = bars["spread"].values * PT - p.bid_off + p.ask_extra   # ask = bid + sp
    bars_spread_pts = bars["spread"].values + (p.ask_extra - p.bid_off) / PT
    hours = bars["time"].dt.hour.values
    dows = bars["time"].dt.dayofweek.values
    mins = (bars["time"].dt.hour * 60 + bars["time"].dt.minute).values

    t0 = int(pd.Timestamp(p.start).timestamp())
    t1 = int(pd.Timestamp(p.end).timestamp())
    k0 = int(np.searchsorted(t_arr, t0))
    k1 = int(np.searchsorted(t_arr, t1))

    sess = [Sess(s, e) for s, e in p.sessions]
    watch_s = p.watch_h * 3600.0
    fri_close_min = p.friday_close[0] * 60 + p.friday_close[1]

    trades = []
    pos = None                  # dict while the slot is occupied
    ticket_stale = False        # EA closed it itself this tick -> g_ticket still set until next Sync
    ambiguous = 0

    def close_leg(px, units, reason, k):
        pos["legs"].append((int(t_arr[k]), px, units, reason))
        pos["units"] -= units

    def finish(k):
        nonlocal pos
        legs = pos["legs"]
        pnl = sum((px - pos["fill"]) * pos["dir"] * u * LOT_STEP * CONTRACT for _, px, u, _ in legs)
        pos.update(exit_t=legs[-1][0], pnl=pnl, nlegs=len(legs), reason=legs[-1][3])
        trades.append(pos)
        pos = None

    for k in range(max(k0, 1), k1):
        # ---- 1. UpdateSessionRanges(bar 1) --------------------------------
        b = k - 1
        hr = hours[b]
        for S in sess:
            inw = hour_in_window(hr, S.s, S.e)
            if inw:
                if not S.was_in:
                    S.fh, S.fl, S.start_t = h[b], l[b], t_arr[b]
                else:
                    S.fh = max(S.fh, h[b]); S.fl = min(S.fl, l[b])
            elif S.was_in:
                S.H, S.L = S.fh, S.fl
                S.valid = S.H > S.L
                S.end_t = t_arr[b]
                S.bias = 0
                S.ext_h = S.ext_l = 0.0
                S.traded = False
                S.gate_rej = 0
            S.was_in = inw

        now = t_arr[k]
        bid = o[k]
        ask = o[k] + sp[k]
        acted_close = False

        # ---- 2. ManageOpenPosition ----------------------------------------
        if ticket_stale:
            ticket_stale = False          # this tick's Sync clears g_ticket
        elif pos is not None:
            if p.max_hold_h > 0 and now - pos["t"] >= p.max_hold_h * 3600:
                close_leg(bid if pos["dir"] > 0 else ask, pos["units"], "maxhold", k)
                finish(k); ticket_stale = True; acted_close = True
            elif (p.weekend_guard_mode == "intended" and p.weekend_guard_min > 0 and dows[k] == 4
                  and 0 <= fri_close_min - mins[k] <= p.weekend_guard_min):
                close_leg(bid if pos["dir"] > 0 else ask, pos["units"], "weekend", k)
                finish(k); ticket_stale = True; acted_close = True
            else:
                d = pos["dir"]
                price = bid if d > 0 else ask
                if not pos["tp1done"] and (price - pos["tp1"]) * d >= 0:
                    u = round(lot_round(pos["units"] * LOT_STEP / 3.0) / LOT_STEP)
                    if u > 0 and pos["units"] - u >= 1:
                        close_leg(price, u, "tp1", k)
                    pos["tp1done"] = True
                    pos["sl"] = pos["px"]
                if pos["tp1done"] and not pos["tp2done"] and (price - pos["tp2"]) * d >= 0:
                    u = round(lot_round(pos["units"] * LOT_STEP / 2.0) / LOT_STEP)
                    if u > 0 and pos["units"] - u >= 1:
                        close_leg(price, u, "tp2", k)
                    pos["tp2done"] = True
                if pos["tp2done"] and p.lock_mode == "static":
                    lock = pos["px"] + d * p.trail * pos["risk"]
                    if (pos["sl"] - lock) * d < -PT * 0.5:
                        pos["sl"] = lock
                elif pos["tp2done"] and p.lock_mode == "ratchet":
                    lock = price - d * p.trail * pos["risk"]
                    if (lock - pos["sl"]) * d > 0:
                        pos["sl"] = lock

        # ---- 3. CheckForEntry ---------------------------------------------
        if pos is None and not ticket_stale and not acted_close:
            if bars_spread_ok(bars_spread_pts[k], p):
                sig = check_setups(sess, c[b], h[b], l[b], t_arr[b], watch_s, p, k, bars, ask, bid, rej)
                if sig is not None:
                    d, si, sl, ctx = sig
                    px = ask if d > 0 else bid
                    risk = (px - sl) * d
                    if risk > 0:
                        lots = p.lots if p.size_fn is None else p.size_fn(ctx)
                        units = int(round(lot_round(lots) / LOT_STEP))
                        S = sess[si]
                        S.bias = 0
                        S.traded = True
                        if units >= 1:
                            pos = dict(t=int(now), dir=d, px=px, fill=px + d * p.slip_entry, sl=sl, risk=risk,
                                       tp1=px + d * p.tp1 * risk, tp2=px + d * p.tp2 * risk,
                                       tp3=px + d * p.tp3 * risk, units=units, units0=units,
                                       tp1done=False, tp2done=False, legs=[],
                                       H=S.H, L=S.L, rng=S.H - S.L, ext=ctx["ext_pct"],
                                       risk_pct=risk / px * 100.0, sig_close=c[b],
                                       range_end=int(S.end_t), spread=sp[k],
                                       trend=ctx["trend"], gate_rej=S.gate_rej)

        # ---- intrabar broker SL / TP3 on bar k ------------------------------
        if pos is not None and p.manage_mode == "tick":
            if intrabar_tick(pos, o[k], h[k], l[k], c[k], sp[k], p, lambda px, u, r: close_leg(px, u, r, k)):
                finish(k)
        elif pos is not None:
            d = pos["dir"]
            if d > 0:
                hit_sl = l[k] <= pos["sl"]
                hit_tp = h[k] >= pos["tp3"]
                if hit_sl and hit_tp:
                    ambiguous += 1
                    first_sl = (o[k] - pos["sl"]) <= (pos["tp3"] - o[k])
                else:
                    first_sl = hit_sl
                if hit_sl and first_sl:
                    close_leg(min(pos["sl"], o[k]) - p.slip_sl, pos["units"], "sl", k); finish(k)
                elif hit_tp:
                    close_leg(max(pos["tp3"], o[k]), pos["units"], "tp", k); finish(k)
            else:
                ah, al, ao = h[k] + sp[k], l[k] + sp[k], o[k] + sp[k]
                hit_sl = ah >= pos["sl"]
                hit_tp = al <= pos["tp3"]
                if hit_sl and hit_tp:
                    ambiguous += 1
                    first_sl = (pos["sl"] - ao) <= (ao - pos["tp3"])
                else:
                    first_sl = hit_sl
                if hit_sl and first_sl:
                    close_leg(max(pos["sl"], ao) + p.slip_sl, pos["units"], "sl", k); finish(k)
                elif hit_tp:
                    close_leg(min(pos["tp3"], ao), pos["units"], "tp", k); finish(k)

    if pos is not None:   # still open at end of data: mark at last close
        close_leg(c[k1 - 1] if pos["dir"] > 0 else c[k1 - 1] + sp[k1 - 1], pos["units"], "eod", k1 - 1)
        finish(k1 - 1)
    for tr in trades:
        tr["entry_time"] = dt.datetime.utcfromtimestamp(tr["t"])
        tr["exit_time"] = dt.datetime.utcfromtimestamp(tr["exit_t"])
    return trades, dict(ambiguous=ambiguous)


def intrabar_tick(pos, o, h, l, c, sp, p, close_leg):
    """Per-tick ManageOpenPosition() + broker SL/TP3 inside one M1 bar.

    Tick order inside the bar is unknown from OHLC, so the standard OHLC path
    is assumed (the same convention as MT5's own "1 minute OHLC" modelling):
    bullish bar open->low->high->close, bearish bar open->high->low->close,
    price moving monotonically between those points.  A buy is tracked on
    Bid, a sell on Ask (= Bid + this bar's spread).  Levels are handled in the
    order the path reaches them, so e.g. a bar that first dips to the stop and
    then spikes to TP1 is a stop-out, while one that spikes to TP1 first and
    then dips to entry is a TP1 partial followed by a breakeven exit.
    Returns True if the position closed inside this bar."""
    d = pos["dir"]
    add = 0.0 if d > 0 else sp
    pts = [o, l, h, c] if c >= o else [o, h, l, c]
    pts = [(x + add) * d for x in pts]          # "d-space": favourable = up
    px0 = pos["px"] * d
    for a, b in zip(pts[:-1], pts[1:]):
        if b < a:                                # adverse leg: only the stop can fire
            sl = pos["sl"] * d
            if b <= sl < a or a <= sl:
                fill = min(sl, a)
                close_leg(fill * d - d * p.slip_sl, pos["units"], "sl")
                return True
        elif b > a:                              # favourable leg: TP1, TP2, TP3 in order
            if not pos["tp1done"] and a < pos["tp1"] * d <= b:
                u = round(lot_round(pos["units"] * LOT_STEP / 3.0) / LOT_STEP)
                if u > 0 and pos["units"] - u >= 1:
                    close_leg(pos["tp1"], u, "tp1")
                pos["tp1done"] = True
                pos["sl"] = pos["px"]
            if pos["tp1done"] and not pos["tp2done"] and a < pos["tp2"] * d <= b:
                u = round(lot_round(pos["units"] * LOT_STEP / 2.0) / LOT_STEP)
                if u > 0 and pos["units"] - u >= 1:
                    close_leg(pos["tp2"], u, "tp2")
                pos["tp2done"] = True
                if p.lock_mode == "static":
                    pos["sl"] = pos["px"] + d * p.trail * pos["risk"]
                elif p.lock_mode == "ratchet":
                    raise NotImplementedError("ratchet + tick management not modelled")
            if a < pos["tp3"] * d <= b or pos["tp3"] * d <= a:
                close_leg(pos["tp3"], pos["units"], "tp")
                return True
    return False


def bars_spread_ok(spread_pts, p):
    return spread_pts <= p.max_spread


def structural_sl(isbuy, S, entry, rng, p):
    if p.fixed_fib_sl:
        swing = (S.ext_h - S.L) if isbuy else (S.H - S.ext_l)
        return (S.ext_h - (p.fib_sl_pct / 100.0) * swing) if isbuy else (S.ext_l + (p.fib_sl_pct / 100.0) * swing)
    off = (p.range_risk / 100.0) * rng
    sl = S.L + off if isbuy else S.H - off
    min_risk = 0.05 * rng
    if isbuy and sl >= entry - min_risk:
        sl = entry - min_risk
    if not isbuy and sl <= entry + min_risk:
        sl = entry + min_risk
    return sl


def trend_gate_rejects(p, d, k):
    """Aurelius M5 gate: True -> this touch is rejected (InRiskDeadZone-style `continue`)."""
    if p.trend_gate == "off":
        return False
    tr = int(p.trend_arr[k])
    if p.trend_gate == "with":
        return tr != d
    if p.trend_gate == "not_against":
        return tr == -d
    raise ValueError(p.trend_gate)


def check_setups(sess, close1, high1, low1, bar_t, watch_s, p, k, bars, ask, bid, rej=None):
    """CheckSessionSetups(), line for line.  NB the SL candidate is computed
    from close1 (as in the mq5), while the order fills at the live Ask/Bid."""
    for i, S in enumerate(sess):
        if not S.valid or S.traded:
            continue
        if bar_t - S.end_t > watch_s:
            S.bias = 0
            continue
        H, L = S.H, S.L
        rng = H - L
        if rng <= 0:
            continue
        if S.bias == 0:
            if close1 > H:
                S.bias, S.ext_h, S.ext_t = 1, high1, bar_t
            elif close1 < L:
                S.bias, S.ext_l, S.ext_t = -1, low1, bar_t
            continue
        if S.bias == 1:
            S.ext_h = max(S.ext_h, high1)
            if close1 < L:
                S.bias = 0
                continue
            swing = S.ext_h - L
            if swing <= 0:
                continue
            ztop = S.ext_h - (p.zone_top / 100.0) * swing
            zbot = S.ext_h - (p.zone_bot / 100.0) * swing
            ext_pct = (S.ext_h - H) / rng * 100.0
            if zbot <= close1 <= ztop and ext_pct >= p.min_ext:
                sl = structural_sl(True, S, close1, rng, p)
                ctx = dict(dir=1, S=S, close1=close1, sl=sl, rng=rng, ext_pct=ext_pct,
                           risk_pct=abs(close1 - sl) / close1 * 100.0, bar_t=bar_t, k=k,
                           fill=ask, zone_pos=(S.ext_h - close1) / swing * 100.0,
                           trend=None if p.trend_arr is None else int(p.trend_arr[k]))
                if p.skip_dead and p.dz_min <= ctx["risk_pct"] <= p.dz_max:
                    continue
                if p.entry_filter is not None and p.entry_filter(ctx):
                    continue
                if trend_gate_rejects(p, 1, k):
                    S.gate_rej += 1
                    if rej is not None:
                        rej.append(dict(k=k, dir=1, trend=ctx["trend"], range_end=int(S.end_t),
                                        risk_pct=ctx["risk_pct"]))
                    if p.trend_kill:
                        S.traded = True; S.bias = 0
                    continue
                return 1, i, sl, ctx
        else:
            S.ext_l = low1 if S.ext_l == 0.0 else min(S.ext_l, low1)
            if close1 > H:
                S.bias = 0
                continue
            swing = H - S.ext_l
            if swing <= 0:
                continue
            zbot = S.ext_l + (p.zone_top / 100.0) * swing
            ztop = S.ext_l + (p.zone_bot / 100.0) * swing
            ext_pct = (L - S.ext_l) / rng * 100.0
            if zbot <= close1 <= ztop and ext_pct >= p.min_ext:
                sl = structural_sl(False, S, close1, rng, p)
                ctx = dict(dir=-1, S=S, close1=close1, sl=sl, rng=rng, ext_pct=ext_pct,
                           risk_pct=abs(close1 - sl) / close1 * 100.0, bar_t=bar_t, k=k,
                           fill=bid, zone_pos=(close1 - S.ext_l) / swing * 100.0,
                           trend=None if p.trend_arr is None else int(p.trend_arr[k]))
                if p.skip_dead and p.dz_min <= ctx["risk_pct"] <= p.dz_max:
                    continue
                if p.entry_filter is not None and p.entry_filter(ctx):
                    continue
                if trend_gate_rejects(p, -1, k):
                    S.gate_rej += 1
                    if rej is not None:
                        rej.append(dict(k=k, dir=-1, trend=ctx["trend"], range_end=int(S.end_t),
                                        risk_pct=ctx["risk_pct"]))
                    if p.trend_kill:
                        S.traded = True; S.bias = 0
                    continue
                return -1, i, sl, ctx
    return None


def stats(trades, key="pnl"):
    pn = np.array([t[key] for t in trades]) if trades else np.zeros(0)
    gp, gl = pn[pn > 0].sum(), -pn[pn < 0].sum()
    eq = np.cumsum(pn)
    dd = float((np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max()) if len(pn) else 0.0
    return dict(n=len(pn), net=round(float(pn.sum()), 2), pf=round(gp / gl, 3) if gl > 0 else float("inf"),
                win=round(100.0 * (pn > 0).mean(), 1) if len(pn) else 0.0, maxdd=round(dd, 2),
                ret_dd=round(float(pn.sum()) / dd, 2) if dd > 0 else float("inf"))


if __name__ == "__main__":
    bars = load_bars()
    tr, info = simulate(bars)
    print(stats(tr), info)
