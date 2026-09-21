"""
Event-driven, strictly SINGLE-POSITION replica of AuRebound_EA.mq5's OnTick().

This is NOT an independent-trigger-evaluation shortcut.  Exactly one position
can exist at a time, and the next entry can only be considered once the
current one has really closed, in bar order - the same discipline that
changed another candidate's reported net from +$1,204 to -$760 this session
when it was (correctly) enforced.

REAL ORDERING, ported from the source
-------------------------------------
OnTick() (mq5 1113-1131) does, in order:
  1. TryFulfillPending()      - only for orders queued on a broker rejection;
                                unreachable in an offline backtest, see note.
  2. HandleExternalClose()    - EVERY tick: notices the broker-side SL having
                                fired and resets to flat + starts the cooldown.
  3. `if(iTime(...,0) == g_lastBarTime) return;` then ProcessNewBar().
     *** There is no IsNewBar() FUNCTION in this file at all - the latch is
     inline and evaluated exactly once per OnTick.  The double-IsNewBar()
     bug found in Slipstream_EA.mq5 this session CANNOT occur here. ***

ProcessNewBar() (mq5 1174-1223), with i = copied-2 = last CLOSED bar:
     g_barCounter++
     if(posOpen)            ManageOpenPosition(i)
     else if(!g_pendingOrder) CheckForEntry(i)
  -> note the `else if`: Manage and Check are MUTUALLY EXCLUSIVE on a bar, so
     a position closed by the EA's own timeout/band-reject on bar j can never
     be replaced by a new entry on that same bar j.

So, per bar j (the forming bar; all market actions fill at open[j]):

  A. if flat at the start of bar j because the broker SL fired somewhere
     inside bar j-1 -> that was already handled intrabar (step 2 above), with
     g_cooldownUntilBar set while g_barCounter was still bar (j-1)'s value.
  B. g_barCounter += 1
  C. if in a position: ManageOpenPosition(j-1)
        barsInTrade++;  timeout (>=MaxHoldBars) -> close at open[j]
        bestFav = max(bestFav, high[j-1]-entry | entry-low[j-1])
        stage2 (breakeven snap): first bar whose CLOSE clears the BB midline
                                 in the trade's favour -> newSL = entryPx
        MFE lock: once bestFav >= 1.0*entryATR ->
                  newSL = max/min(newSL, entryPx + dir*bestFav*MFELockFrac)
        clamp (mq5 1267-1278): minDist = max(stops/freeze level, spread*1.5);
                  long  newSL = max(min(newSL, bid-minDist), entrySL)
                  short newSL = min(max(newSL, ask+minDist), entrySL)
                  -> monotone tightening only, and never placed through the
                     market.  This clamp is modelled, because a stale MFE-lock
                     target CAN land past price and the clamp is what decides
                     where the stop actually ends up.
        band-reject (stage2 only): opposite-band touch within the last
                  min(Lookback, barsInTrade) bars AND an opposite %D turn
                  -> close at open[j]
     else: CheckForEntry(j-1) -> may fill at open[j]
  D. intrabar of bar j: the broker-side SL is a REAL order, live from the
     instant of the fill, so it is checked against bar j's low/high INCLUDING
     ON THE ENTRY BAR ITSELF (the 'stop not checked on entry bar' bug class is
     explicitly avoided).

SPREAD: charged ONCE at entry, from the CSV's own per-bar `spread` column on
the FILL bar.  long fills at open+spread (ask), short at open (bid); all exits
priced raw.  Same convention as research/slipstream/sim.py and
research/ichimoku/cloud_stoch_test.py.  The stop level itself is derived from
the spread-adjusted fill price exactly as SendOrder() does (mq5 1654-1655), so
a stopped-out long loses exactly slDist, which is the real behaviour.

P&L unit: price difference.  At InpLots=0.01 on GOLD# (contract size 100) a
$1 price move is exactly $1 - the unit every other sim in this project reports.

NOT MODELLED, and why:
  * InpUseNewsFilter  - live Economic Calendar only; NewsBlackoutActive()
    itself returns false under MQL_TESTER (mq5 1484).  Inert in any backtest,
    so there is nothing to model and no backtest P&L claim attaches to it.
  * InpUseSessionScheduleFilter / the pending-order queue - depends on the
    broker's published SymbolInfoSessionTrade schedule and on live order
    rejections.  Both only ever DELAY or DROP an entry at a moment the market
    is closed; H4 bars in this CSV only exist when the market was open.
  * Swap/commission - not in the CSV, and not in any sibling EA's sim either.

INTRABAR ORDERING - AuRebound needs NO convention here, unlike Slipstream.
ManageOpenPosition() has exactly ONE call site in the whole file (mq5 1217,
inside ProcessNewBar), so the protective stop is repositioned only at a bar
boundary and is then FIXED for the whole of that bar.  There is therefore no
"did the favourable extreme come first?" ambiguity to resolve:
  intrabar="stop_first" (default) is the EXACT model, not a convention.
  intrabar="lock_first" is kept only as a counterfactual - "what if this EA
      trailed intrabar the way Slipstream_EA.mq5 does?" - and is NOT a bound
      on the shipped behaviour.  Reported for contrast only.
"""
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# Explicit distinct module name - research/{aurelius,ichimoku,slipstream}/
# engine.py are all also called "engine" and would collide in sys.modules.
_spec = importlib.util.spec_from_file_location(
    "aurebound_engine", os.path.join(HERE, "engine.py"))
aeng = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aeng)


def simulate(ctx, p, i0=None, intrabar="stop_first"):
    n = ctx["n"]
    start = max(aeng.first_tradable(ctx, p), 1)
    if i0 is not None:
        start = max(start, i0)

    o, h, l, c = ctx["o"], ctx["h"], ctx["l"], ctx["c"]
    spread = ctx["spread"]
    atr, mid = ctx["atr"], ctx["bb_mid"]

    trades = []
    pos = 0                 # 0 flat, +1 long, -1 short
    entry_px = entry_sl = entry_atr = 0.0
    stage2 = False
    best_fav = 0.0
    bars_in = 0
    entry_i = -1
    bar_counter = 0
    cooldown_until = -1

    def close_trade(j, px, reason):
        nonlocal pos, stage2, best_fav, bars_in, entry_px, entry_sl, entry_atr
        nonlocal cooldown_until, entry_i
        pnl = (px - entry_px) * pos
        trades.append(dict(entry_i=entry_i, exit_i=j, dir=pos,
                           entry=round(entry_px, 4), exit=round(px, 4),
                           bars=bars_in, pnl=round(pnl, 4), reason=reason,
                           year=int(ctx["year"][entry_i]),
                           t_entry=ctx["t"][entry_i], t_exit=ctx["t"][j]))
        # FinalizeClosedTrade() (mq5 1352-1359): cooldown is measured off
        # g_barCounter AT THE MOMENT OF THE CLOSE.
        cooldown_until = bar_counter + p["Cooldown"]
        pos = 0; stage2 = False; best_fav = 0.0; bars_in = 0
        entry_px = entry_sl = entry_atr = 0.0; entry_i = -1

    for j in range(start, n):
        bar_counter += 1

        if pos != 0:
            # ---------------- ManageOpenPosition(i = j-1) at open[j] -------
            i = j - 1
            bars_in += 1

            if bars_in >= p["MaxHoldBars"]:
                close_trade(j, o[j], "timeout")
                continue

            cur_fav = (h[i] - entry_px) if pos > 0 else (entry_px - l[i])
            best_fav = max(best_fav, cur_fav)

            new_sl = entry_sl
            if not stage2 and not np.isnan(mid[i]):
                cleared = (c[i] > mid[i]) if pos > 0 else (c[i] < mid[i])
                if cleared:
                    stage2 = True
                    new_sl = entry_px

            if best_fav >= 1.0 * entry_atr:
                lock = entry_px + pos * best_fav * p["MFELockFrac"]
                new_sl = max(new_sl, lock) if pos > 0 else min(new_sl, lock)

            # clamp against the live market (mq5 1267-1278). bid=open[j],
            # ask=open[j]+spread[j]; broker stops/freeze level unknown offline
            # so the floor is the spread*1.5 term the code always includes.
            bid = o[j]
            ask = o[j] + spread[j]
            min_dist = max(spread[j] * 1.5, 0.0)
            if pos > 0:
                new_sl = max(min(new_sl, bid - min_dist), entry_sl)
            else:
                new_sl = min(max(new_sl, ask + min_dist), entry_sl)
            entry_sl = new_sl

            if stage2 and aeng.band_exit(ctx, i, pos, entry_atr, bars_in, p):
                close_trade(j, o[j], "band-reject")
                continue
        else:
            # ---------------- CheckForEntry(i = j-1) ----------------------
            i = j - 1
            if bar_counter > cooldown_until:
                d = aeng.raw_signal(ctx, i, p)
                if d != 0 and not np.isnan(atr[i]) and atr[i] > 0.0:
                    px = o[j] + spread[j] if d > 0 else o[j]   # ask / bid
                    sl_dist, a = aeng.compute_sl_dist(ctx, i, d, px, p)
                    sl_dist = max(sl_dist, spread[j] * 1.5)    # mq5 1626
                    if sl_dist > 0:
                        pos = d
                        entry_px = px
                        entry_sl = px - sl_dist if d > 0 else px + sl_dist
                        entry_atr = a
                        stage2 = False
                        best_fav = 0.0
                        bars_in = 0
                        entry_i = j

        # ------------- intrabar of bar j: broker-side SL is live -----------
        if pos != 0:
            if intrabar == "lock_first" and j > entry_i:
                cur_fav = (h[j] - entry_px) if pos > 0 else (entry_px - l[j])
                bf = max(best_fav, cur_fav)
                if bf >= 1.0 * entry_atr:
                    lock = entry_px + pos * bf * p["MFELockFrac"]
                    cand = max(entry_sl, lock) if pos > 0 else min(entry_sl, lock)
                    bid, ask = o[j], o[j] + spread[j]
                    md = max(spread[j] * 1.5, 0.0)
                    entry_sl = (max(min(cand, bid - md), entry_sl) if pos > 0
                                else min(max(cand, ask + md), entry_sl))
            if pos > 0 and l[j] <= entry_sl:
                close_trade(j, entry_sl, "stop")
            elif pos < 0 and h[j] >= entry_sl:
                close_trade(j, entry_sl, "stop")

    return trades


# ------------------------------------------------------------------ stats
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
            f"win={s['win']:4.1f}% maxDD=${s['maxdd']:8.2f}")


def split_stats(trades, i0, n_total, is_frac=0.7):
    """Chronological 70/30 on BAR index within the traded window [i0, n_total)
    - the same convention as research/slipstream/sim.py::split_stats()."""
    cut = i0 + int((n_total - i0) * is_frac)
    return (stats([t for t in trades if t["entry_i"] < cut]),
            stats([t for t in trades if t["entry_i"] >= cut]), cut)


def reason_breakdown(trades):
    out = {}
    for t in trades:
        r = out.setdefault(t["reason"], [0, 0.0])
        r[0] += 1
        r[1] += t["pnl"]
    return {k: (v[0], round(v[1], 2)) for k, v in sorted(out.items())}


def year_breakdown(trades):
    ys = {}
    for t in trades:
        ys.setdefault(int(t["year"]), []).append(t["pnl"])
    return {y: (len(v), round(sum(v), 2)) for y, v in sorted(ys.items())}
