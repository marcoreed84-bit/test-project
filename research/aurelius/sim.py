"""
Aurelius M5 simulator - ports the entry-gate combination and exit-priority
order from OnTick() (Aurelius_EA.mq5 line ~2713). See engine.py for the
precomputed per-bar arrays this consumes.

Fill convention: a decision computed from bar i's close fills at bar i+1's
OPEN (matching the real EA sending a market order on the tick that starts
the new bar). The stop-loss is a resting order, checked against the fill
bar's own high/low - including the entry bar itself (an Opus audit found
this file's own prior docstring claimed that was handled but the code
only ever checked the NEXT bar after entry, missing 7/971 same-bar stops
in the baseline run - fixed below, checked explicitly right after entry).
Spread is charged once per round trip, at entry, using the real per-bar
spread column (an Opus audit found this wasn't modeled at all, biasing
PF optimistic - confirmed: adding it moved baseline PF from 1.71 to 1.64
on the true v1.46 defaults).
"""
import numpy as np

from engine import P, POINT


def simulate(ctx, extra_filter=None, params=None):
    """extra_filter(ctx, i, is_buy) -> bool, optional additional entry gate
    (e.g. the S&R touch-and-reject condition), applied on top of the real
    shipped gates below - used to test a candidate filter against the
    already-validated base gate, not in place of it."""
    p = params or P
    n = ctx["n"]
    close, high, low = ctx["close"], ctx["high"], ctx["low"]
    atr = ctx["atr"]

    trades = []  # dicts: entry_i, entry_time, exit_i, exit_time, dir, entry_px, exit_px, reason

    in_pos = 0          # 0 flat, +1 long, -1 short
    entry_px = 0.0
    entry_atr = 0.0
    stop_px = 0.0
    entry_i = -1
    bars_since_close = 10 ** 9
    price21_bad = 0
    vwap_bad = 0
    be_done = False
    peak_fav_px = 0.0

    # --- consecutive-loss circuit breaker (candidate, OFF by default -
    # p["use_consec_breaker"] absent/False leaves every existing baseline
    # byte-identical). Ported from Zenith_EA.mq5's real mechanism
    # (InpMaxConsecLosses / InpPauseBars, OnTradeTransaction ~2252 +
    # AdvanceWatchAndOrders ~1946): every closed trade with profit <= 0
    # increments the streak, any win resets it to 0, and once the streak
    # reaches max_consec_losses NEW ENTRIES are blocked for pause_bars bars
    # from that close. Like Zenith's, it never touches an already-open
    # position - exits, breakeven, trail and the stop all run untouched
    # during a pause.
    #
    # APPROXIMATION vs the real EA: "loss" here is price-unit pnl <= 0 with
    # the entry spread already charged, but with NO swap or commission,
    # which the MQL5 version does include. A handful of near-scratch trades
    # would therefore be classified win-here / loss-there. Zenith's pause is
    # also wall-clock seconds (pause_bars * PeriodSeconds) where this is a
    # bar count, so the real EA's pause is ~30% shorter than the tested one
    # across any span containing a weekend - the same known imprecision
    # documented in Zenith's own entry gate.
    consec_breaker = bool(p.get("use_consec_breaker"))
    max_consec = int(p.get("max_consec_losses", 0))
    pause_bars = int(p.get("pause_bars", 0))
    consec_losses = 0
    paused_until = -1   # bar index; new entries blocked while i < paused_until

    def register_close(trade_pnl, exit_i):
        """mirrors OnTradeTransaction's DEAL_ENTRY_OUT branch"""
        nonlocal consec_losses, paused_until
        if not consec_breaker or max_consec <= 0:
            return
        # p["breaker_rule"] is a RESEARCH HOOK ONLY, never part of the EA:
        # it replaces the "streak has reached max_consec" trigger with an
        # arbitrary callable, so a permutation null can fire the SAME number
        # of pauses of the SAME length at trade closes chosen by a rule that
        # carries no information. Absent (the normal case) the real
        # consecutive-loss test is used.
        rule = p.get("breaker_rule")
        if rule is not None:
            if trade_pnl <= 0:
                consec_losses += 1
            else:
                consec_losses = 0
            if rule(consec_losses, trade_pnl, exit_i):
                paused_until = exit_i + pause_bars
            return
        if trade_pnl <= 0:
            consec_losses += 1
            if consec_losses >= max_consec:
                paused_until = exit_i + pause_bars
        else:
            consec_losses = 0

    warmup = max(p["p2400"], p["p600"]) + 50

    for i in range(warmup, n - 1):
        fill_i = i + 1  # decisions from bar i fill at bar i+1's open... open not
        # stored in ctx (only close/high/low kept) - close[i] is used as a
        # deliberately conservative same-bar-decision proxy for "essentially the
        # opening tick price of the very next bar" on M5 gold (5-minute
        # open-to-prior-close gap is negligible next to this system's ATR-scaled
        # thresholds) - see README note in this dir for why open wasn't kept.
        px_fill = close[i]

        if in_pos != 0:
            is_buy = in_pos > 0
            # --- exit priority: daily/Friday flatten > Price21 > VWAP > ALIGN_BREAK ---
            fired = None
            if ctx["near_daily_close"][i] or ctx["friday_flatten"][i]:
                fired = "SESSION_CLOSE"
            if fired is None and p["use_price21_exit"]:
                m21 = ctx["m21"][i]
                if not np.isnan(m21) and atr[i] > 0:
                    buf = p["price21_buffer_atr"] * atr[i]
                    bad = (close[i] < m21 - buf) if is_buy else (close[i] > m21 + buf)
                    price21_bad = price21_bad + 1 if bad else 0
                else:
                    price21_bad = 0
                if price21_bad >= p["price21_confirm_bars"]:
                    fired = "PRICE21"
            if fired is None and p["use_vwap_exit"]:
                vw = ctx["vwap"][i]
                if vw > 0 and atr[i] > 0:
                    buf = p["vwap_buffer_atr"] * atr[i]
                    bad = (close[i] < vw - buf) if is_buy else (close[i] > vw + buf)
                    vwap_bad = vwap_bad + 1 if bad else 0
                else:
                    vwap_bad = 0
                if vwap_bad >= p["vwap_confirm_bars"]:
                    fired = "VWAP"
            if fired is None:
                still_aligned = ctx["aligned_buy"][i] if is_buy else ctx["aligned_sell"][i]
                if not still_aligned:
                    fired = "ALIGN_BREAK"

            # --- stale losing trade (InpUseStaleExit, Aurelius_EA.mq5 ~2899).
            # Real EA order: this sits AFTER the ALIGN_BREAK check and after
            # ManageBreakeven/scale/bank/MAXBARS, and closes at market - i.e.
            # it fills at the open of bar fill_i, which is BEFORE the resting
            # stop can be hit anywhere inside fill_i, so it belongs in this
            # `fired` chain (last) rather than after the stop block below.
            # Bar count: the EA's g_entryBarCount is incremented once per new
            # bar while a position is open and zeroed on the entry tick, so at
            # the moment it decides from bar i (shift=1) it equals
            # i - entry_i + 1 - reproduced exactly here, not approximated.
            if fired is None and p.get("use_stale_exit") and entry_atr > 0:
                bars_open = i - entry_i + 1
                if bars_open >= p.get("stale_bars", 48):
                    prof = (close[i] - entry_px) * (1 if is_buy else -1)
                    # p["stale_rule"] is a RESEARCH HOOK ONLY, never part of
                    # the EA: it replaces the still-losing condition with an
                    # arbitrary callable so a permutation null can fire the
                    # same number of stale exits on the same eligible bars
                    # by a rule that carries no information. Absent (the
                    # normal case) the real InpStaleMinLossATR test is used.
                    rule = p.get("stale_rule")
                    hit = (rule(bars_open, prof, entry_atr) if rule is not None
                           else prof < -p.get("stale_min_loss_atr", 0.5) * entry_atr)
                    if hit:
                        fired = "STALE"

            if fired is not None:
                trades.append(dict(entry_i=entry_i, exit_i=fill_i, dir=in_pos,
                                    entry_px=entry_px, exit_px=px_fill,
                                    entry_atr=entry_atr, reason=fired))
                register_close((px_fill - entry_px) * in_pos, fill_i)
                in_pos = 0
                bars_since_close = 0
                price21_bad = 0
                vwap_bad = 0
                be_done = False
                continue

            # --- breakeven / trail (ManageBreakeven, Aurelius_EA.mq5 ~2325) -
            # only reached when the position survives this bar's signal exits,
            # uses bar i's close as "shift=1", moves stop_px (never loosens) ---
            if p["use_breakeven"] and entry_atr > 0:
                prof = (close[i] - entry_px) * (1 if is_buy else -1)
                if not be_done:
                    if prof >= p["breakeven_atr"] * entry_atr:
                        lock = p["breakeven_lock_atr"] * entry_atr
                        new_sl = entry_px + lock if is_buy else entry_px - lock
                        stop_px = new_sl
                        be_done = True
                        peak_fav_px = close[i]
                elif p["use_trail_after_be"]:
                    if (is_buy and close[i] > peak_fav_px) or ((not is_buy) and close[i] < peak_fav_px):
                        peak_fav_px = close[i]
                    give = p["trail_give_back_atr"] * entry_atr
                    trail_sl = peak_fav_px - give if is_buy else peak_fav_px + give
                    if (is_buy and trail_sl > stop_px) or ((not is_buy) and trail_sl < stop_px):
                        stop_px = trail_sl

            # --- stop-loss: resting order, checked against the NEXT bar's
            # (fill_i's) own high/low, which is why this runs after the
            # signal-exit check above (that one is decided from bar i, before
            # fill_i's intrabar path exists) ---
            if p["use_stop"] and stop_px > 0:
                hit = (low[fill_i] <= stop_px) if is_buy else (high[fill_i] >= stop_px)
                if hit:
                    trades.append(dict(entry_i=entry_i, exit_i=fill_i, dir=in_pos,
                                        entry_px=entry_px, exit_px=stop_px,
                                        entry_atr=entry_atr, reason="STOP"))
                    register_close((stop_px - entry_px) * in_pos, fill_i)
                    in_pos = 0
                    bars_since_close = 0
                    price21_bad = 0
                    vwap_bad = 0
                    be_done = False
            continue

        # --- flat: entry gates, in the real OnTick's order ---
        bars_since_close += 1
        # circuit-breaker pause gate. Position matches Zenith's real gate
        # (Zenith_EA.mq5 ~1946): checked before the cooldown/spread/session
        # gates, and only ever blocks a NEW entry - nothing else in this
        # loop is skipped by it. Order within this gate chain cannot change
        # the outcome here (none of these gates has a side effect), only
        # which reason a rejected bar would be attributed to.
        if consec_breaker and max_consec > 0 and i < paused_until:
            continue
        if bars_since_close < p["cooldown_bars"]:
            continue
        if ctx["no_entry_near_close"][i] or ctx["friday_no_entry"][i]:
            continue
        if ctx["is_market_holiday"][fill_i]:
            continue
        if ctx["spread"][i] > 60:  # InpMaxSpreadPoints, points == this column's own units
            continue
        if atr[i] <= 0 or np.isnan(atr[i]):
            continue

        up = bool(ctx["aligned_buy"][i])
        dn = bool(ctx["aligned_sell"][i])
        if not up and not dn:
            continue
        is_buy = up
        if is_buy and not p["allow_buys"]:
            continue
        if (not is_buy) and not p["allow_sells"]:
            continue

        if p["use_cross_filter"]:
            cc = ctx["crisscross"][i]
            if np.isnan(cc) or cc > p["max_crosses"]:
                continue
        sl = ctx["slope_buy"][i] if is_buy else ctx["slope_sell"][i]
        if np.isnan(sl):
            continue
        if p["use_slope"] and sl < p["min_slope_atr"]:
            continue
        if p["max_slope_atr"] > 0 and sl > p["max_slope_atr"]:
            continue

        pb_ok = ctx["pullback_ok_buy"][i] if is_buy else ctx["pullback_ok_sell"][i]
        if not pb_ok:
            continue

        # --- momentum shift (InpUseMomentum / MomentumShiftOK(),
        # Aurelius_EA.mq5 ~1905): MACD histogram at shifts 1/2/3 - i.e.
        # bars i, i-1, i-2 - must have just turned in the trade's favour.
        # Placed here to match the real OnTick order (after PullbackOK,
        # before the volume filter); order doesn't change the outcome,
        # only which reason a rejected bar is attributed to. A bar whose
        # MACD is unreadable is rejected, matching MomentumShiftOK()'s
        # own `return(false)` on a failed BufVal read. ---
        if p.get("use_momentum"):
            hist = ctx["macd_hist"]
            h0, h1, h2 = hist[i], hist[i - 1], hist[i - 2]
            if np.isnan(h0) or np.isnan(h1) or np.isnan(h2):
                continue
            ok_mom = (h0 > h1 and h1 <= h2) if is_buy else (h0 < h1 and h1 >= h2)
            if not ok_mom:
                continue

        if p["use_volume"]:
            vr = ctx["vol_ratio"][i]
            if not np.isnan(vr) and vr < p["min_vol_ratio"]:
                continue
        if p["use_sr_dist"]:
            sd = ctx["sr_dist_buy"][i] if is_buy else ctx["sr_dist_sell"][i]
            if not np.isnan(sd) and sd < p["min_sr_dist_atr"]:
                continue

        # --- combined slope x S/R block (M15 only, InpUseSlopeSRBlock -
        # Aurelius_M15_EA.mq5 ~3209): blocks when slope is steep AND far
        # from the nearest S/R level, simultaneously - neither threshold
        # alone catches this, checked with the SAME sd/sl already computed
        # above rather than InpMaxSlopeATR's own gate ---
        if p.get("use_slope_sr_block"):
            sd2 = ctx["sr_dist_buy"][i] if is_buy else ctx["sr_dist_sell"][i]
            if (not np.isnan(sd2)) and sl >= p["slope_sr_block_slope"] and sd2 >= p["slope_sr_block_sr"]:
                continue

        if extra_filter is not None and not extra_filter(ctx, i, is_buy):
            continue

        # --- enter at fill_i's open (proxied by close[i], see note above),
        # spread charged once round-trip at entry (worse fill in the trade's
        # direction) ---
        spread_cost = ctx["spread"][fill_i] * POINT
        in_pos = 1 if is_buy else -1
        entry_px = px_fill + spread_cost if is_buy else px_fill - spread_cost
        entry_atr = atr[i]
        entry_i = fill_i
        stop_px = (entry_px - p["stop_atr"] * entry_atr) if is_buy else (entry_px + p["stop_atr"] * entry_atr)
        # --- candidate (OFF by default, p.get(...) leaves every existing
        # baseline byte-identical): widen the stop to sit just beyond VWAP
        # when VWAP is further from entry than the normal ATR stop would be
        # - never tightens it. User's own idea: don't get stopped out by
        # noise while price is still on the trade's side of VWAP. ---
        if p.get("stop_beyond_vwap"):
            vw = ctx["vwap"][i]
            if not np.isnan(vw) and vw > 0:
                vwap_buf = p.get("vwap_stop_buffer_atr", 0.1) * entry_atr
                stop_px = min(stop_px, vw - vwap_buf) if is_buy else max(stop_px, vw + vwap_buf)
        price21_bad = 0
        vwap_bad = 0
        be_done = False
        peak_fav_px = entry_px

        # --- stop-loss checked on the ENTRY bar's own high/low too - a
        # position opened at fill_i's open can still be stopped within that
        # same bar if price runs that far before the next new-bar decision.
        # Previously missed entirely (see module docstring). ---
        if p["use_stop"] and stop_px > 0:
            hit = (low[fill_i] <= stop_px) if is_buy else (high[fill_i] >= stop_px)
            if hit:
                trades.append(dict(entry_i=entry_i, exit_i=fill_i, dir=in_pos,
                                    entry_px=entry_px, exit_px=stop_px,
                                    entry_atr=entry_atr, reason="STOP"))
                register_close((stop_px - entry_px) * in_pos, fill_i)
                in_pos = 0
                bars_since_close = 0
                price21_bad = 0
                vwap_bad = 0
                be_done = False

    return trades


def stats(trades):
    if not trades:
        return dict(n=0)
    pnl = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades])
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    gross_win = wins.sum() if len(wins) else 0.0
    gross_loss = -losses.sum() if len(losses) else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else np.inf
    return dict(
        n=len(trades), net=pnl.sum(), pf=pf, win_rate=len(wins) / len(trades),
        avg_win=wins.mean() if len(wins) else 0.0,
        avg_loss=losses.mean() if len(losses) else 0.0,
        gross_win=gross_win, gross_loss=gross_loss,
    )


def risk_stats(trades, ctx):
    """The drawdown side, which stats() above cannot see at all (it only
    reads closed entry/exit prices). Three separate numbers, because the
    real MT5 report that started this whole line of work had a 9.76%
    BALANCE drawdown next to a 27.69% EQUITY drawdown - i.e. the closed-
    trade curve was NOT where the risk was:

      closed_dd   - max drawdown of the closed-trade equity curve, in
                    price units. The BALANCE-drawdown analogue.
      float_dd    - max drawdown of a bar-by-bar equity curve that marks
                    the open position to each bar's own adverse/favourable
                    extreme. The EQUITY-drawdown analogue, and the number
                    InpUseStaleExit is actually aimed at.
      worst_mae   - worst single-trade adverse excursion (price, and in
                    units of that trade's entry ATR). The "~$1,184
                    underwater" incident, per-trade.

    APPROXIMATION: MT5 computes equity drawdown tick by tick; this uses one
    adverse and one favourable extreme per M5 bar, and assumes the bar's
    favourable extreme precedes its adverse one when setting the running
    peak (the conservative ordering). It is a like-for-like comparison
    between baseline and candidate, not a reproduction of MT5's own number.
    Everything is in price units (1 lot-equivalent, no compounding), so
    percentages of an account balance are not comparable to a real report.
    """
    if not trades:
        return dict(closed_dd=0.0, float_dd=0.0, worst_mae=0.0, worst_mae_atr=0.0)
    high, low = ctx["high"], ctx["low"]

    # --- closed-trade curve ---
    eq = 0.0
    peak = 0.0
    closed_dd = 0.0
    for t in trades:
        eq += (t["exit_px"] - t["entry_px"]) * t["dir"]
        peak = max(peak, eq)
        closed_dd = max(closed_dd, peak - eq)

    # --- bar-marked curve (trades are non-overlapping: one position at a
    # time, enforced by simulate()) ---
    eq = 0.0
    peak = 0.0
    float_dd = 0.0
    worst_mae = 0.0
    worst_mae_atr = 0.0
    for t in trades:
        d = t["dir"]
        a, b = t["entry_i"], t["exit_i"]
        mae = 0.0
        # Bars a..b-1 are held in full. Bar b is NOT: every exit either
        # fills at that bar's OPEN (every signal/session/stale exit) or at
        # the resting stop inside it, so the position is gone before the
        # rest of bar b happens. Counting bar b's full range here credited
        # the trade with excursion it was never exposed to - which on the
        # first bar back after the daily settlement break (a real gap on
        # this broker's data) produced single "excursions" of 60+ price
        # units on trades whose stop was 9 units wide. Bar b contributes
        # exactly the realized exit instead.
        for k in range(a, b):
            # d=+1: fav=high-entry, adv=low-entry;  d=-1: fav=entry-low, adv=entry-high
            fav = ((high[k] if d > 0 else low[k]) - t["entry_px"]) * d
            adv = ((low[k] if d > 0 else high[k]) - t["entry_px"]) * d
            peak = max(peak, eq + fav)
            float_dd = max(float_dd, peak - (eq + adv))
            mae = min(mae, adv)
        realized = (t["exit_px"] - t["entry_px"]) * d
        mae = min(mae, realized)
        float_dd = max(float_dd, peak - (eq + realized))
        eq += realized
        peak = max(peak, eq)
        float_dd = max(float_dd, peak - eq)
        worst_mae = min(worst_mae, mae)
        atr0 = t.get("entry_atr", 0.0)
        if atr0 > 0:
            worst_mae_atr = min(worst_mae_atr, mae / atr0)
    return dict(closed_dd=closed_dd, float_dd=float_dd,
                worst_mae=worst_mae, worst_mae_atr=worst_mae_atr)
