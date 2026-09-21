"""
Event-driven, strictly single-position replica of Tailwind_EA.mq5's OnTick().

Exact ordering ported from the real source (mq5 1436-1467 OnTick,
1217-1264 ManageOpenPosition, 1302-1434 CheckForEntry):

  per new bar j (first tick of bar j, price = open[j]):
    A. ManageOpenPosition() - runs EVERY tick, so it runs first:
         - g_ticket==0 -> returns immediately WITHOUT calling IsNewBar()
         - optional partial close (InpUsePartialClose, OFF by default)
         - IsNewBar() gate, then midline break (close[j-1] vs BBmid[j-1])
           or max-hold timeout -> PositionClose at market (= open[j]);
           cooldown is set from OnTradeTransaction (mq5 816-817) as
           g_cooldownUntilBar = g_barsSeen + InpCooldown.
    B. OnTick()'s own IsNewBar():
         *** IsNewBar() latches g_lastBarTime on its FIRST success in a bar.
         If a position was open at the first tick of bar j, ManageOpenPosition()
         already consumed that bar's flag, so OnTick()'s call returns false and
         CheckForEntry() is NOT reached on bar j. Modelled by `pos_at_open`.
         (This is the same double-IsNewBar() bug Slipstream_EA.mq5 v1.08 fixed;
          set double_isnewbar=False to model the fixed behaviour.)
    C. CheckForEntry() - only reached when flat at the first tick of bar j.
         gates: g_ticket re-sync, cooldown (g_barsSeen <= g_cooldownUntilBar),
         news (a no-op under MQL_TESTER, mq5 v1.03), history depth, session
         filter on the SIGNAL bar's time (shift 1), Friday cutoff, Saturday,
         then the MinRun band-walk crossing, indecision, entry-distance and
         ShadowOpposing (InpAvoidOpposing).
         Fill at market = open[j]. SL = entryPx -/+ InpSLBuffer_ATR*ATR[j-1]
         (a pure ATR distance - Tailwind does NOT use a structural extreme,
          unlike Slipstream/AuRebound).

  The broker-side SL is live from the instant of the fill, so it is checked
  intra-bar ON THE ENTRY BAR TOO ('stop not checked on entry bar' avoided).

Spread: charged ONCE at entry from the CSV's own per-bar `spread` column on
the FILL bar - identical convention to research/slipstream/sim.py
(entry_buy = raw + spread*POINT, entry_sell = raw - spread*POINT; exits raw).

P&L unit: price difference. At 0.01 lots on GOLD# (contract size 100) a $1
price move is exactly $1 - the unit every other sim in this project reports.

Intrabar ordering (only matters once a stop and a partial-close trigger can
both be hit on the same bar):
  intrabar="stop_first" (default) - adverse extreme tested against the stop
      first; only if it survives does the partial-close trigger fire.
  intrabar="fav_first"  - the favourable extreme is tested first.
"""
import importlib.util
import os

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "engine_tailwind",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.py"))
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)


def simulate(ctx, p, sig=None, intrabar="stop_first", avoid_opposing=None,
             shadow_cache=None, double_isnewbar=True, wallclock_maxhold=False,
             fill="open", charge_spread=True, record_shadow=False):
    """fill / charge_spread exist only to bound how much of any gap to the
    header's claimed numbers is a modelling-convention difference. The EA's
    real behaviour is the default."""
    if sig is None:
        sig, warm = E.base_signals(ctx, p)
    else:
        sig, warm = sig
    if avoid_opposing is None:
        avoid_opposing = p["avoid_opposing"]
    if shadow_cache is None:
        shadow_cache = {}

    o, h, l, c = ctx["open"], ctx["high"], ctx["low"], ctx["close"]
    atr, mid = ctx["atr"], ctx["bbmid"]
    spread, epoch = ctx["spread"], ctx["epoch"]
    n = ctx["n"]
    POINT = E.POINT
    start = max(warm, E.SHADOW_DEPTH + 2, 60)

    trades = []
    pos = 0
    entry_i = -1
    entry_px = 0.0
    entry_atr = 0.0
    sl = np.nan
    part_done = True
    part_pnl = 0.0
    part_frac = 0.0
    entry_shadow = None
    bars_seen = 0
    cooldown_until = -1

    def _close(j, px, reason, bars_in):
        nonlocal pos, sl, cooldown_until, part_pnl, part_frac
        pnl = part_pnl + (1.0 - part_frac) * (px - entry_px) * pos
        trades.append(dict(entry_i=entry_i, entry_px=entry_px, exit_i=j,
                           exit_px=px, dir=pos, reason=reason, bars=bars_in,
                           pnl=pnl, part_frac=part_frac,
                           entry_t=ctx["time"][entry_i], exit_t=ctx["time"][j],
                           year=ctx["year"][entry_i], shadow=entry_shadow))
        pos = 0
        sl = np.nan
        part_pnl = 0.0
        part_frac = 0.0
        cooldown_until = bars_seen + p["cooldown"]

    for j in range(start, n):
        bars_seen += 1                       # exactly one IsNewBar() success/bar
        pos_at_open = pos != 0

        # ---------------- A. ManageOpenPosition (first tick of bar j)
        if pos != 0:
            # partial close is checked every tick; at the first tick the price
            # is open[j].  (Default OFF.)
            if p["use_partial_close"] and not part_done and entry_atr > 0:
                fav = (o[j] - entry_px) * pos
                if fav >= p["partial_trigger_atr"] * entry_atr:
                    part_frac = p["partial_frac"]
                    part_pnl = part_frac * (o[j] - entry_px) * pos
                    part_done = True
            bars_held = j - entry_i
            if wallclock_maxhold:
                bars_held = int((epoch[j] - epoch[entry_i]) // (4 * 3600))
            mb = (c[j - 1] < mid[j - 1]) if pos > 0 else (c[j - 1] > mid[j - 1])
            if mb or bars_held >= p["max_hold_bars"]:
                _close(j, o[j], "MID" if mb else "TIME", j - entry_i)

        # ---------------- B/C. CheckForEntry
        gate = (pos == 0) and (bars_seen > cooldown_until)
        if double_isnewbar and pos_at_open:
            gate = False
        if gate:
            d = sig[j]
            if d != 0:
                blocked = False
                sh = None
                if avoid_opposing:
                    sh = E.shadow_dirs(ctx, j) if j not in shadow_cache else shadow_cache[j]
                    shadow_cache[j] = sh
                    if sh[0] == -d or sh[1] == -d:
                        blocked = True
                elif record_shadow:
                    if j not in shadow_cache:
                        shadow_cache[j] = E.shadow_dirs(ctx, j)
                    sh = shadow_cache[j]
                if not blocked:
                    a = atr[j - 1]
                    sl_dist = p["sl_buffer_atr"] * a
                    if sl_dist > 0:
                        sc = spread[j] * POINT if charge_spread else 0.0
                        raw = o[j] if fill == "open" else c[j - 1]
                        px = raw + sc if d > 0 else raw - sc
                        pos = d
                        entry_i = j
                        entry_px = px
                        entry_atr = a
                        sl = px - sl_dist if d > 0 else px + sl_dist
                        # MinStopDistance() clamp (mq5 965-974): floor is
                        # (ask-bid)*1.5; never binds at 1.5xATR, modelled anyway
                        md = sc * 1.5
                        sl = min(sl, px - md) if d > 0 else max(sl, px + md)
                        part_done = not p["use_partial_close"]
                        part_pnl = 0.0
                        part_frac = 0.0
                        entry_shadow = sh

        # ---------------- intrabar remainder of bar j
        if pos != 0:
            bars_held = j - entry_i
            hit = (l[j] <= sl) if pos > 0 else (h[j] >= sl)
            fav_ext = h[j] if pos > 0 else l[j]
            trig = (p["use_partial_close"] and not part_done and entry_atr > 0
                    and (fav_ext - entry_px) * pos >= p["partial_trigger_atr"] * entry_atr)
            if intrabar == "stop_first":
                if hit:
                    _close(j, sl, "STOP", bars_held)
                elif trig:
                    tp = entry_px + pos * p["partial_trigger_atr"] * entry_atr
                    part_frac = p["partial_frac"]
                    part_pnl = part_frac * (tp - entry_px) * pos
                    part_done = True
            else:  # fav_first
                if trig:
                    tp = entry_px + pos * p["partial_trigger_atr"] * entry_atr
                    part_frac = p["partial_frac"]
                    part_pnl = part_frac * (tp - entry_px) * pos
                    part_done = True
                if hit:
                    _close(j, sl, "STOP", bars_held)

    return trades


# ------------------------------------------------------------------- stats
def stats(trades):
    if not trades:
        return dict(n=0, pf=float("nan"), net=0.0, win=float("nan"), maxdd=0.0)
    p = np.array([t["pnl"] for t in trades])
    gw = p[p > 0].sum()
    gl = -p[p < 0].sum()
    return dict(n=len(p), pf=(gw / gl if gl > 0 else float("inf")),
                net=round(p.sum(), 2), win=round(100 * (p > 0).mean(), 1),
                gw=round(gw, 2), gl=round(gl, 2), nloss=int((p < 0).sum()),
                worst=round(p.min(), 2), maxdd=round(max_dd(p), 2))


def max_dd(pnl):
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(eq)
    return float((peak - eq).max()) if len(eq) else 0.0


def fmt(s):
    if s["n"] == 0:
        return "n=0"
    return (f"n={s['n']:4d} PF={s['pf']:.3f} net=${s['net']:9.2f} "
            f"win={s['win']:4.1f}% losses={s['nloss']:4d} maxDD=${s['maxdd']:7.2f}")


def split_stats(trades, i0, n_total, is_frac=0.7):
    """Chronological 70/30 on BAR index within the traded window [i0, n_total),
    the same convention as research/slipstream/sim.py + ichimoku/sim.py."""
    cut = i0 + int((n_total - i0) * is_frac)
    return (stats([t for t in trades if t["entry_i"] < cut]),
            stats([t for t in trades if t["entry_i"] >= cut]), cut)


def year_breakdown(trades):
    ys = {}
    for t in trades:
        ys.setdefault(int(t["year"]), []).append(t["pnl"])
    return {y: round(sum(v), 2) for y, v in sorted(ys.items())}
