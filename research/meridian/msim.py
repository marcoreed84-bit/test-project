"""
Sequential, single-position bar-level simulator of Meridian_EA.mq5 (v1.02),
ported from the EA's own OnTick()/ManageOpenPosition()/CheckForEntry() - NOT
from the research/aurelius Python model, which differs from the EA in ways
that matter here:

  * The EA runs EITHER ManageOpenPosition() OR CheckForEntry() on a new bar
    (`if(g_ticket != 0) ManageOpenPosition(); else CheckForEntry();`), so the
    21/50 cross that closes a trade on REVERSAL can never also open the
    opposite trade - by the next bar that cross is no longer "fresh"
    (DetectCross compares shift 1 vs shift 2 only). The EA is NOT
    stop-and-reverse. research/aurelius/m5_stack_variants_fixed_test.py's
    sim_filtered_entries() IS (it opens a new trade at the same raw event
    that closed the previous one) - every Python Meridian number to date
    carries that difference.
  * Friday flatten at 22:00 server time (tick-level, first tick at/after
    22:00 -> that bar's open) and no entries from then on; the Python model
    has neither.
  * InpMaxSpreadPoints=60 entry block; the Python model has none.

Event order per M5 bar t (index t = bar that just opened; shift 1 = t-1):
  1. tick-level Friday check (before the new-bar gate): position open and
     Fri >= 22:00 -> close at this bar's open.
  2. UpdateVWAP() - calendar-day cumulative typical*tick_volume through t-1.
  3. position open -> Friday -> DetectCross(): a cross against the position
     closes it at this bar's open (REVERSAL). No entry this bar.
     flat -> Friday, spread, DetectCross, close[t-1] vs confirm-MA and VWAP,
     Wilder ATR(14), S/R distance to the last InpSRDays completed D1 bars'
     high/low (x ATR) -> market entry at the open, SL = 2.5 x ATR.
  4. intrabar resting SL (long: bid low <= SL; short: high+spread >= SL).

STALE-TICKET QUIRK (found by bar-matching Backtest_2 - every one of the sim's
16 extra entries sat on the bar right after an intrabar SL fill): the EA
only re-syncs g_ticket inside ManageOpenPosition()/CheckForEntry(), so after
the broker's SL closes the trade mid-bar, the NEXT new bar still sees
g_ticket != 0, calls ManageOpenPosition() (which syncs to flat and returns)
instead of CheckForEntry(), and by the bar after that the cross is no longer
fresh. Net effect: a 21/50 cross on the first bar after an SL stop-out is
never traded. Modeled by stale_ticket_bar=True (the EA's real behavior).

P/L is USD per 0.01 lot (1 oz).
"""
import sys
from dataclasses import dataclass, replace
from typing import Callable, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B  # noqa: E402

POINT = B.POINT
WIN_START = pd.Timestamp("2026-01-01")
WIN_END = pd.Timestamp("2026-09-21")


@dataclass
class MP:
    p21: int = 21
    p50: int = 50
    fast: str = "ema"
    pconf: int = 250
    conf: str = "sma"
    use_sr: bool = True
    sr_days: int = 3
    min_sr: float = 0.50
    stop_atr: float = 2.5
    max_spread: int = 60
    fri_close: int = 22
    use_vwap: bool = True
    entry_from_min: int = 65            # no real entry in any of the four reports before 01:05 server time -
                                        # hour-0 bars (DST-gap weeks only) sit outside the broker session table
    stale_ticket_bar: bool = True       # EA quirk (see module docstring): no entry on the bar after an SL fill
    sl_cooldown: int = 1                # bars after an SL fill with no entry (1 = exactly the quirk above)
    stop_and_reverse: bool = False      # True = the Python model's behavior, for comparison only
    no_friday: bool = False             # True = the Python model's behavior (no Friday flatten)
    # execution model
    entry_noise: Optional[np.ndarray] = None
    sl_slip: Optional[np.ndarray] = None
    noise_in_atr: bool = True
    seed: int = 0
    # candidate hooks
    entry_filter: Optional[Callable] = None     # f(ctx, t, dir) -> bool
    exit_fn: Optional[Callable] = None          # f(ctx, t, pos) -> reason or None (checked at bar open)
    manage_fn: Optional[Callable] = None        # f(ctx, t, pos) -> None (may move pos['sl'])


V102 = MP()                                           # shipped v1.02 = Backtest_2
BT1_BINARY = MP(pconf=150, conf="ema", use_sr=False)  # what Backtest_1's stale binary actually ran (see validate.py)


def _ma(x, n, kind):
    return B.ema(x, n) if kind == "ema" else B.sma(x, n)


def build_ctx(df=None):
    df = B.load_m5() if df is None else df
    o, h, l, c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
    v = df["tick_volume"].values.astype(float)
    tm = df["time"]
    ctx = dict(df=df, t64=tm.values, o=o, h=h, l=l, c=c, spread=df["spread"].values.astype(float), v=v)
    ctx["atr"] = B.wilder_atr(h, l, c, 14)
    date = tm.dt.date
    typ = (h + l + c) / 3.0
    ctx["vwap"] = (pd.Series(typ * v).groupby(date.values).cumsum() /
                   pd.Series(v).groupby(date.values).cumsum()).values
    daily = pd.DataFrame(dict(date=date, h=h, l=l)).groupby("date").agg(h=("h", "max"), l=("l", "min"))
    ctx["daily"] = daily
    ctx["date"] = date.values
    ctx["dow"] = ((tm.dt.dayofweek + 1) % 7).values
    ctx["hour"] = tm.dt.hour.values
    ctx["mod"] = (tm.dt.hour * 60 + tm.dt.minute).values
    ctx["_ma"] = {}
    ctx["_sr"] = {}
    return ctx


def ma(ctx, n, kind):
    k = (n, kind)
    if k not in ctx["_ma"]:
        ctx["_ma"][k] = _ma(ctx["c"], n, kind)
    return ctx["_ma"][k]


def sr_arrays(ctx, days):
    """Per-bar highest high / lowest low of the `days` COMPLETED D1 bars before
    each bar's own day (EA: iHigh/iLow(PERIOD_D1, 1..InpSRDays))."""
    if days not in ctx["_sr"]:
        d = ctx["daily"]
        hi = d["h"].rolling(days).max().shift(1)
        lo = d["l"].rolling(days).min().shift(1)
        idx = pd.Index(d.index)
        pos = idx.get_indexer(ctx["date"])
        ctx["_sr"][days] = (hi.values[pos], lo.values[pos])
    return ctx["_sr"][days]


def simulate(ctx, p=V102, start=WIN_START, end=WIN_END):
    t64 = ctx["t64"]
    i0 = int(np.searchsorted(t64, np.datetime64(start)))
    i1 = int(np.searchsorted(t64, np.datetime64(end)))
    o, h, l, c, spread, atr, vwap = ctx["o"], ctx["h"], ctx["l"], ctx["c"], ctx["spread"], ctx["atr"], ctx["vwap"]
    m21, m50, mc = ma(ctx, p.p21, p.fast), ma(ctx, p.p50, p.fast), ma(ctx, p.pconf, p.conf)
    srh, srl = sr_arrays(ctx, p.sr_days)
    above = m21 > m50
    rng = np.random.default_rng(p.seed)
    trades, pos = [], None
    since_sl = 10 ** 9
    stats = dict(crosses=0, blk_conf=0, blk_sr=0, blk_filter=0, blk_spread=0, blk_reverse_bar=0)

    def fri(t):
        return (not p.no_friday) and ctx["dow"][t] == 5 and ctx["hour"][t] >= p.fri_close

    def close(t, px, reason):
        nonlocal pos
        pos.update(exit_i=t, exit=px, pnl=(px - pos["entry"]) * pos["dir"], reason=reason, exit_time=t64[t])
        trades.append(pos)
        pos = None

    def try_entry(t, sp):
        nonlocal pos
        s = t - 1
        if above[s] == above[s - 1]:
            return
        if ctx["mod"][t] < p.entry_from_min:
            stats["blk_session"] = stats.get("blk_session", 0) + 1
            return
        d = 1 if above[s] else -1
        stats["crosses"] += 1
        if p.max_spread > 0 and spread[t] > p.max_spread:
            stats["blk_spread"] += 1
            return
        if np.isnan(mc[s]):
            return
        ok = (c[s] > mc[s]) if d > 0 else (c[s] < mc[s])
        if p.use_vwap:
            ok = ok and ((c[s] > vwap[s]) if d > 0 else (c[s] < vwap[s]))
        if not ok:
            stats["blk_conf"] += 1
            return
        a = atr[s]
        if not (a > 0):
            return
        if p.use_sr and not np.isnan(srh[t]):
            sr = abs(srh[t] - c[s]) / a if d > 0 else abs(c[s] - srl[t]) / a
            if sr < p.min_sr:
                stats["blk_sr"] += 1
                return
        if p.entry_filter is not None and not p.entry_filter(ctx, t, d):
            stats["blk_filter"] += 1
            return
        entry = o[t] + sp if d > 0 else o[t]
        if p.entry_noise is not None:
            entry = round(entry + d * float(rng.choice(p.entry_noise)) * (a if p.noise_in_atr else 1.0), 2)
        sl = entry - d * p.stop_atr * a
        pos = dict(entry_i=t, entry_time=t64[t], dir=d, entry=entry, sl=sl, sl0=sl, atr=a, peak=entry,
                   bars=0)

    for t in range(i0, i1):
        sp = spread[t] * POINT
        if pos is not None and fri(t):
            close(t, o[t] if pos["dir"] > 0 else o[t] + sp, "FRIDAY")
        if pos is not None:
            pos["bars"] += 1
            d = pos["dir"]
            s = t - 1
            if above[s] != above[s - 1] and (1 if above[s] else -1) != d and ctx["hour"][t] == 0:
                stats["lost_reversal"] = stats.get("lost_reversal", 0) + 1   # close rejected, cross stale next bar
            elif above[s] != above[s - 1] and (1 if above[s] else -1) != d:
                close(t, o[t] if d > 0 else o[t] + sp, "REVERSAL")
                if p.stop_and_reverse and not fri(t):
                    try_entry(t, sp)
                else:
                    stats["blk_reverse_bar"] += 1
            else:
                if p.exit_fn is not None:
                    r = p.exit_fn(ctx, t, pos)
                    if r:
                        close(t, o[t] if d > 0 else o[t] + sp, r)
                if pos is not None and p.manage_fn is not None:
                    p.manage_fn(ctx, t, pos)
        elif not fri(t):
            if p.stale_ticket_bar and since_sl < p.sl_cooldown:
                stats["blk_stale_ticket"] = stats.get("blk_stale_ticket", 0) + 1
            else:
                try_entry(t, sp)
        since_sl += 1
        if pos is not None:
            d = pos["dir"]
            cur_hi = h[t] if d > 0 else l[t]
            pos["peak"] = max(pos["peak"], cur_hi) if d > 0 else min(pos["peak"], cur_hi)
            slip = (float(rng.choice(p.sl_slip)) * (pos["atr"] if p.noise_in_atr else 1.0)
                    if p.sl_slip is not None else 0.0)
            if d > 0 and l[t] <= pos["sl"]:
                close(t, min(pos["sl"], o[t]) + slip, "SL")
                since_sl = 0
            elif d < 0 and h[t] + sp >= pos["sl"]:
                close(t, max(pos["sl"], o[t] + sp) - slip, "SL")
                since_sl = 0
    if pos is not None:
        close(i1 - 1, c[i1 - 1], "END")
    return trades, stats


def stats_of(trades):
    pn = np.array([x["pnl"] for x in trades]) if trades else np.zeros(0)
    gp, gl = pn[pn > 0].sum(), -pn[pn < 0].sum()
    eq = np.cumsum(pn)
    dd = (np.maximum.accumulate(np.concatenate(([0.0], eq)))[1:] - eq).max() if len(pn) else 0.0
    return dict(n=len(pn), net=round(float(pn.sum()), 2), pf=round(gp / gl, 3) if gl > 0 else float("inf"),
                win=round(100.0 * (pn > 0).mean(), 1) if len(pn) else 0.0, closed_dd=round(float(dd), 2))
