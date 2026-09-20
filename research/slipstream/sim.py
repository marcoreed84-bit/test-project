"""
Event-driven, strictly single-position replica of Slipstream_EA.mq5's OnTick().

Exact ordering ported from the real source (mq5 1531-1567 OnTick,
1240-1315 ManageOpenPosition, 1352-1529 CheckForEntry):

  per new bar j (first tick of bar j, price = open[j]):
    A. ManageOpenPosition() - runs EVERY tick, so it runs first:
         - g_ticket==0 -> returns immediately WITHOUT calling IsNewBar()
         - MFE-lock update from the current price
         - InpCloseBeforeWeekend force-close (default OFF)
         - IsNewBar() gate, then trend-break (close[j-1] vs EMA50[j-1]) or
           max-hold timeout -> PositionClose at market (= open[j]),
           g_cooldownUntilBar = g_barsSeen + InpCooldown
    B. OnTick()'s own IsNewBar():
         *** IMPORTANT, and easy to get wrong: IsNewBar() latches
         g_lastBarTime on its FIRST success in a bar. If a position was open
         at the first tick of bar j, ManageOpenPosition() already consumed
         that bar's IsNewBar(), so OnTick()'s call returns false and
         CheckForEntry() is NOT reached on bar j - even if the position was
         just closed by the trend-break branch. A new entry is therefore
         impossible on the same bar an existing position is closed by the EA.
    C. CheckForEntry() - only reached when flat at the first tick of bar j.
         gates: cooldown (g_barsSeen <= g_cooldownUntilBar), news (a no-op
         under MQL_TESTER, mq5 1337), history depth, session filter on the
         SIGNAL bar's time (shift 1, mq5 1376), Friday cutoff, Saturday.
         Fill at market = open[j]. SL = structural extreme over
         low/high[j-1 .. j-1-InpLookback] +/- InpSLBuffer*ATR[j-1].

  The broker-side SL is live from the instant of the fill, so it is checked
  intra-bar ON THE ENTRY BAR TOO (the 'stop not checked on entry bar' bug
  class is explicitly avoided here).

Spread: charged ONCE at entry, from the CSV's own per-bar `spread` column on
the FILL bar - identical convention to research/ichimoku/cloud_stoch_test.py
and research/aurelius/battery3.py (entry_buy = raw + spread*POINT,
entry_sell = raw - spread*POINT; exits priced raw).

P&L unit: price difference. At 0.01 lots on GOLD# (contract size 100) a $1
price move is exactly $1, which is the unit every other sim in this project
reports "net=$" in.

Intrabar ordering: with only OHLC we cannot know whether a bar's favourable
extreme came before its adverse extreme. Two explicit conventions, both
reported:
  intrabar="stop_first"  (default) - the stop in force at the bar's start is
      tested against the adverse extreme first; only if it survives does the
      MFE-lock tighten from the bar's favourable extreme (effective next bar).
  intrabar="lock_first"  - the lock tightens from the favourable extreme
      first, then the (tighter) stop is tested against the same bar's adverse
      extreme. A strict lower bound on the same trade sequence.
"""
import importlib.util
import os

import numpy as np

# Same module-cache hazard as research/ichimoku/cloud_stoch_test.py documents:
# research/aurelius/engine.py, research/ichimoku/engine.py and this directory's
# engine.py are all literally "engine". Load ours under an explicit distinct
# name so a plain `import engine` anywhere else can never shadow it.
_spec = importlib.util.spec_from_file_location(
    "engine_slipstream",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.py"))
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)


def simulate(ctx, p, sig=None, intrabar="stop_first", require_confluence=None,
             include_forming_bar=True, symmetric_touch=False, conf_cache=None,
             entry_on_close_bar=False, fill="open", charge_spread=True):
    """entry_on_close_bar / fill / charge_spread are NOT the EA's behaviour -
    they exist only to bound how much of the gap to the header's claimed
    numbers is attributable to a different modelling convention in whatever
    replica produced them. The EA's real behaviour is the default
    (entry_on_close_bar=False, fill="open", charge_spread=True)."""
    if sig is None:
        sig, warm = E.base_signals(ctx, p, symmetric_touch=symmetric_touch)
    else:
        sig, warm = sig
    if require_confluence is None:
        require_confluence = p["require_confluence"]
    if conf_cache is None:
        conf_cache = {}

    o, h, l, c = ctx["open"], ctx["high"], ctx["low"], ctx["close"]
    atr, e50 = ctx["atr"], ctx["ema50"]
    spread, dow, hour = ctx["spread"], ctx["dow"], ctx["hour"]
    n = ctx["n"]
    lb, tol = p["lookback"], p["touch_tol"]
    POINT = E.POINT

    # EA history gate: Bars() < need+20 -> return, need = max(200,14,20)+20
    need = max(p["ema200"], p["bb_period"],
               p["stoch_k"] + p["stoch_d"] + p["stoch_slow"]) + 20
    start = max(warm, need + 20, 60)

    trades = []
    pos = 0
    entry_i = -1
    entry_px = 0.0
    entry_atr = 0.0
    best_fav = 0.0
    sl = np.nan
    bars_seen = 0
    cooldown_until = -1

    def _lock(price):
        """MFE-lock (mq5 1257-1282). Only ever tightens."""
        nonlocal best_fav, sl
        fav = (price - entry_px) if pos > 0 else (entry_px - price)
        if fav > best_fav:
            best_fav = fav
        if not p["use_mfe_lock"] or entry_atr <= 0:
            return
        if best_fav < p["mfe_lock_trigger"] * entry_atr:
            return
        lock = entry_px + (1 if pos > 0 else -1) * best_fav * p["mfe_lock_frac"]
        if pos > 0:
            if not np.isfinite(sl) or lock > sl:
                sl = lock
        else:
            if not np.isfinite(sl) or lock < sl:
                sl = lock

    def _close(j, px, reason, bars_in):
        nonlocal pos, sl, best_fav, cooldown_until
        trades.append(dict(entry_i=entry_i, entry_px=entry_px, exit_i=j,
                           exit_px=px, dir=pos, reason=reason, bars=bars_in,
                           pnl=(px - entry_px) * pos,
                           entry_t=ctx["time"][entry_i], exit_t=ctx["time"][j],
                           year=ctx["year"][entry_i]))
        pos = 0
        sl = np.nan
        best_fav = 0.0
        cooldown_until = bars_seen + p["cooldown"]

    for j in range(start, n):
        bars_seen += 1                       # exactly one IsNewBar() success/bar
        pos_at_open = pos != 0

        # ---------------- A. ManageOpenPosition (first tick of bar j)
        if pos != 0:
            _lock(o[j])
            bars_held = j - entry_i
            tb = (c[j - 1] < e50[j - 1]) if pos > 0 else (c[j - 1] > e50[j - 1])
            if tb or bars_held >= p["max_hold_bars"]:
                _close(j, o[j], "TREND" if tb else "TIME", bars_held)

        # ---------------- B/C. CheckForEntry - unreachable if a position was
        # open at the first tick of this bar (IsNewBar() already consumed).
        if pos == 0 and (entry_on_close_bar or not pos_at_open) and bars_seen > cooldown_until:
            d = sig[j]
            if d != 0:
                i = j - 1
                # session filter is applied to the SIGNAL bar's time (mq5 1376)
                blocked = False
                if p["use_session_filter"] and (hour[i] == p["blocked_hour1"]
                                                or hour[i] == p["blocked_hour2"]):
                    blocked = True
                if p["block_friday_close"] and dow[i] == 5 and hour[i] >= p["friday_cutoff_hour"]:
                    blocked = True
                if p["block_friday_close"] and dow[i] == 6:
                    blocked = True
                if not blocked and require_confluence:
                    key = (j, d, include_forming_bar)
                    if key not in conf_cache:
                        conf_cache[key] = E.confluence_ok(
                            ctx, j, d, p, include_forming_bar=include_forming_bar)
                    if not conf_cache[key]:
                        blocked = True
                if not blocked:
                    a = atr[i]
                    if d > 0:
                        extreme = np.min(l[i - lb:i + 1])
                    else:
                        extreme = np.max(h[i - lb:i + 1])
                    sc = spread[j] * POINT if charge_spread else 0.0
                    raw = o[j] if fill == "open" else c[j - 1]
                    px = raw + sc if d > 0 else raw - sc
                    sl_dist = abs(px - extreme) + p["sl_buffer"] * a
                    if sl_dist > 0:
                        pos = d
                        entry_i = j
                        entry_px = px
                        entry_atr = a
                        best_fav = 0.0
                        sl = px - sl_dist if d > 0 else px + sl_dist
                        # MinStopDistance() clamp (mq5 1497-1499): floor is
                        # (ask-bid)*1.5. Only ever widens a too-close stop.
                        md = sc * 1.5
                        if d > 0:
                            sl = min(sl, px - md)
                        else:
                            sl = max(sl, px + md)

        # ---------------- intrabar remainder of bar j
        if pos != 0:
            bars_held = j - entry_i
            if intrabar == "stop_first":
                if pos > 0 and l[j] <= sl:
                    _close(j, sl, "STOP", bars_held)
                elif pos < 0 and h[j] >= sl:
                    _close(j, sl, "STOP", bars_held)
                else:
                    _lock(h[j] if pos > 0 else l[j])
            else:  # lock_first
                _lock(h[j] if pos > 0 else l[j])
                if pos > 0 and l[j] <= sl:
                    _close(j, sl, "STOP", bars_held)
                elif pos < 0 and h[j] >= sl:
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
                gw=round(gw, 2), gl=round(gl, 2),
                worst=round(p.min(), 2), maxdd=round(max_dd(p), 2))


def max_dd(pnl):
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(eq)
    return float((peak - eq).max()) if len(eq) else 0.0


def fmt(s):
    if s["n"] == 0:
        return "n=0"
    return (f"n={s['n']:4d} PF={s['pf']:.3f} net=${s['net']:9.2f} "
            f"win={s['win']:4.1f}% maxDD=${s['maxdd']:7.2f}")


def split_stats(trades, i0, n_total, is_frac=0.7):
    """Chronological 70/30 on BAR index within the traded window [i0, n_total),
    the same convention as research/ichimoku/sim.py's split_stats()."""
    cut = i0 + int((n_total - i0) * is_frac)
    return (stats([t for t in trades if t["entry_i"] < cut]),
            stats([t for t in trades if t["entry_i"] >= cut]), cut)


def year_breakdown(trades):
    ys = {}
    for t in trades:
        ys.setdefault(int(t["year"]), []).append(t["pnl"])
    return {y: round(sum(v), 2) for y, v in sorted(ys.items())}
