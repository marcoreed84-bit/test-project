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

            if fired is not None:
                trades.append(dict(entry_i=entry_i, exit_i=fill_i, dir=in_pos,
                                    entry_px=entry_px, exit_px=px_fill, reason=fired))
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
                                        entry_px=entry_px, exit_px=stop_px, reason="STOP"))
                    in_pos = 0
                    bars_since_close = 0
                    price21_bad = 0
                    vwap_bad = 0
                    be_done = False
            continue

        # --- flat: entry gates, in the real OnTick's order ---
        bars_since_close += 1
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
                                    entry_px=entry_px, exit_px=stop_px, reason="STOP"))
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
