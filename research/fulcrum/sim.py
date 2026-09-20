"""
Fulcrum simulator - ports OnTick()/ProcessNewBar()/CheckForEntry() and the
native-SL/TP exit from Fulcrum_EA.mq5 (v2.13). The M15 file's trading code is
CHARACTER-IDENTICAL to the M5 file's (verified by diffing lines 1216-1320 /
1703-1912 against 1034-1138 / 1521-1730 - the only differences anywhere in the
logic are the input VALUES, the selectable InpM* MA methods, and two Print
strings), so one simulator serves both: pass P or P15.

EVENT ORDER, taken from the real OnTick (Fulcrum_EA.mq5:1660). For each new
bar b, with the decision bar i = b-1 (MQL5 shift=1):

  1. WeekendStillOpen() - tick-level, evaluated BEFORE the new-bar gate, so
     it acts at bar b's OPEN.
  2. stale-ticket cleanup (resets the cooldown clock).
  3. ProcessNewBar: UpdateATRManual, g_barsSinceClose++, then either
     ManageOpenPosition() (a no-op in this EA - the header is explicit that
     the weekend flatten is the only active management) or CheckForEntry().
  4. The broker's native SL/TP sit on the order and are live for the whole
     of bar b, INCLUDING the entry bar itself.

FILL CONVENTION: decisions from bar i fill at bar b's OPEN - the real open
column, not a close[i] proxy. (research/aurelius/sim.py uses close[i] as a
proxy because its ctx never kept `open`; Fulcrum's stop is a ~1.9 x ATR
structural distance rather than a 2.5 x ATR volatility stop, so that proxy's
error is not negligible here and the real open is used instead.)

SPREAD: charged once per round trip, from the entry bar's own real spread
column. The EA enters a buy at the ASK and a sell at the BID, and the broker
triggers a buy's SL/TP on the BID and a sell's on the ASK. Working in the
CSV's bid OHLC:
    buy : entry_px = open+s ; stop level = stopPx        ; tgt level = entry_px + tgtDist
    sell: entry_px = open-s ; stop level = stopPx - s    ; tgt level = entry_px - tgtDist
APPROXIMATION: the exit-side spread is assumed equal to the entry-side one.

BOTH-HIT BARS: when a single bar's range spans both the stop and the target,
the stop is taken (conservative). simulate() reports how many bars were
ambiguous so the sensitivity is measurable, not assumed away.
"""
import numpy as np

from engine import P, POINT

# GOLD# contract facts from the CSV's own meta header
# (meta_digits=2, meta_point=0.01, meta_contract_size=100):
TICK_SIZE = 0.01
TICK_VALUE = 1.00        # $ per TICK_SIZE per 1.00 lot = point * contract_size
VOL_MIN, VOL_STEP = 0.01, 0.01


def lot_size(p, stop_distance):
    """LotSize() (Fulcrum_EA.mq5:1344)."""
    lots = p["lots"]
    if p["lot_mode"] == "LOT_RISK_PCT" and stop_distance > 0.0:
        risk_cash = p.get("balance", 10000.0) * p.get("risk_pct", 1.0) / 100.0
        loss_per_lot = (stop_distance / TICK_SIZE) * TICK_VALUE
        if loss_per_lot > 0.0:
            lots = risk_cash / loss_per_lot
    lots = np.floor(lots / VOL_STEP) * VOL_STEP
    lots = max(VOL_MIN, min(p["max_lots"], lots))
    return round(lots, 2)


def target_distance(p, lots):
    """TargetDistance() (Fulcrum_EA.mq5:1390). Note the 1/lots factor: this is
    a PRICE distance that shrinks as size grows, so InpFixedTargetUSD keeps its
    dollar meaning - and so the reward:risk GEOMETRY changes with lot size,
    because the stop is not lot-scaled. At the shipped LOT_FIXED/0.01 this
    returns exactly InpFixedTargetUSD as a price distance."""
    if lots <= 0.0:
        return p["fixed_target_usd"]
    return p["fixed_target_usd"] * TICK_SIZE / (TICK_VALUE * lots)


def simulate(ctx, extra_filter=None, params=None, both_hit="stop", report=None):
    """extra_filter(ctx, i, is_buy) -> bool: an EXTRA entry gate applied on top
    of the real shipped ones (never in place of them), for candidate testing.
    `report` (optional dict) receives diagnostic counters."""
    p = params or P
    n = ctx["n"]
    o, c, h, l = ctx["open"], ctx["close"], ctx["high"], ctx["low"]
    atr, m50 = ctx["atr"], ctx["m50"]
    spread, times = ctx["spread"], ctx["time"]
    fri_deadline = ctx["fri_deadline"]

    trades = []
    in_pos = 0
    entry_px = stop_lvl = tgt_lvl = 0.0
    entry_atr = 0.0
    entry_i = -1
    entry_time = None
    bars_since_close = 10 ** 9      # nothing has closed yet -> cooldown satisfied
    both_hit_bars = 0

    # --- consecutive-loss circuit breaker: a CANDIDATE, OFF by default, so
    # every baseline above is byte-identical with it absent. Same mechanism
    # already tested and rejected for Aurelius (research/aurelius/sim.py:46,
    # ported there from Zenith_EA.mq5's real InpMaxConsecLosses/InpPauseBars):
    # a closed trade with pnl <= 0 increments the streak, any win resets it,
    # and on reaching max_consec_losses NEW ENTRIES are blocked for pause_bars
    # bars. It never touches an open position. `breaker_rule` is a RESEARCH
    # HOOK ONLY (never part of any EA) so a permutation null can fire the same
    # number of pauses from a rule that carries no information.
    consec_breaker = bool(p.get("use_consec_breaker"))
    max_consec = int(p.get("max_consec_losses", 0))
    pause_bars = int(p.get("pause_bars", 0))
    breaker_rule = p.get("breaker_rule")
    consec_losses = 0
    paused_until = -1

    warmup = max(p["p2400"], p["p600"], p["vol_avg_bars"]) + 60

    def close_trade(exit_i, exit_px, reason):
        nonlocal in_pos, bars_since_close, consec_losses, paused_until
        pnl = (exit_px - entry_px) * in_pos
        trades.append(dict(entry_i=entry_i, exit_i=exit_i, dir=in_pos,
                           entry_px=entry_px, exit_px=exit_px,
                           entry_atr=entry_atr, entry_time=entry_time,
                           exit_time=times[exit_i], reason=reason,
                           stop0=stop_lvl, tgt0=tgt_lvl))
        in_pos = 0
        bars_since_close = 0
        if consec_breaker and max_consec > 0:
            consec_losses = consec_losses + 1 if pnl <= 0 else 0
            if breaker_rule is not None:
                if breaker_rule(consec_losses, pnl, exit_i):
                    paused_until = exit_i + pause_bars
            elif pnl <= 0 and consec_losses >= max_consec:
                paused_until = exit_i + pause_bars

    for b in range(warmup + 1, n):
        i = b - 1

        # --- 1. WeekendStillOpen(): tick-level, acts at bar b's open ---
        if in_pos != 0 and entry_time < fri_deadline[b]:
            # exit at bar b's open; the round-trip spread was already charged
            # at entry, consistent with the convention documented above.
            close_trade(b, o[b], "FRIDAY")

        # --- 3. ProcessNewBar: the cooldown clock ticks every new bar ---
        if bars_since_close < 100000:
            bars_since_close += 1

        # --- CheckForEntry (Fulcrum_EA.mq5:1521), gates in the real order ---
        if in_pos == 0:
            ok = True
            if p["max_daily_loss_pct"] > 0.0:
                pass                                   # off by default; no equity model here
            if consec_breaker and max_consec > 0 and b < paused_until:
                ok = False
            if bars_since_close < p["cooldown_bars"]:
                ok = False
            if ok and ctx["friday_no_entry"][b]:
                ok = False
            if ok and ctx["is_market_holiday"][b]:
                ok = False
            if ok and spread[b] > p["max_spread_points"]:
                ok = False
            if ok:
                up = bool(ctx["aligned_buy"][i])
                dn = bool(ctx["aligned_sell"][i])
                if not up and not dn:
                    ok = False
                else:
                    is_buy = up
            if ok:
                cc = ctx["crisscross"][i]
                if np.isnan(cc) or cc > p["max_crosses"]:
                    ok = False                         # CrissCross() returns 999 on a failed read
            if ok:
                sl = ctx["slope_buy"][i] if is_buy else ctx["slope_sell"][i]
                if np.isnan(sl):
                    sl = 0.0                           # SlopeATR() returns 0.0 on a failed read
                if sl < p["min_slope_atr"] or (p["max_slope_atr"] > 0.0 and sl > p["max_slope_atr"]):
                    ok = False
            if ok and not (ctx["pullback_ok_buy"][i] if is_buy else ctx["pullback_ok_sell"][i]):
                ok = False
            if ok and (np.isnan(atr[i]) or atr[i] <= 0.0):
                ok = False
            if ok and p["use_volume"]:
                vr = ctx["vol_ratio"][i]
                if not np.isnan(vr) and vr < p["min_vol_ratio"]:
                    ok = False                         # VolumeRatio() returns -1.0 -> gate passes
            if ok and p["use_sr_dist"]:
                sd = ctx["sr_dist_buy"][i] if is_buy else ctx["sr_dist_sell"][i]
                if not np.isnan(sd) and sd < p["min_sr_dist_atr"]:
                    ok = False                         # SRDistanceATR() returns -1.0 -> gate passes
            if ok and np.isnan(m50[i]):
                ok = False
            if ok and extra_filter is not None and not extra_filter(ctx, i, is_buy):
                ok = False

            if ok:
                s = spread[b] * POINT
                ref_px = o[b] + s if is_buy else o[b]          # ASK for a buy, BID for a sell
                stop_px = (m50[i] - p["stop_buffer_atr"] * atr[i]) if is_buy \
                    else (m50[i] + p["stop_buffer_atr"] * atr[i])
                # the bounce MA must sit on the protective side of the fill
                if (is_buy and stop_px >= ref_px) or ((not is_buy) and stop_px <= ref_px):
                    ok = False
                else:
                    if p["min_stop_atr"] > 0.0:
                        min_dist = p["min_stop_atr"] * atr[i]
                        if abs(ref_px - stop_px) < min_dist:
                            stop_px = ref_px - min_dist if is_buy else ref_px + min_dist
                    lots = lot_size(p, abs(ref_px - stop_px))
                    if lots <= 0.0:
                        ok = False
                    else:
                        tgt_dist = target_distance(p, lots)
                        in_pos = 1 if is_buy else -1
                        entry_i = b
                        entry_time = times[b]
                        entry_atr = atr[i]
                        if is_buy:
                            entry_px = ref_px
                            stop_lvl = stop_px
                            tgt_lvl = ref_px + tgt_dist
                        else:
                            entry_px = ref_px - s
                            stop_lvl = stop_px - s
                            tgt_lvl = entry_px - tgt_dist

        # --- 4. native SL/TP, live for the whole of bar b (entry bar included) ---
        if in_pos != 0:
            is_buy = in_pos > 0
            if is_buy:
                s_hit, t_hit = l[b] <= stop_lvl, h[b] >= tgt_lvl
            else:
                s_hit, t_hit = h[b] >= stop_lvl, l[b] <= tgt_lvl
            if s_hit and t_hit:
                both_hit_bars += 1
            if s_hit and (both_hit == "stop" or not t_hit):
                # gap-through fills at the market, never at the stop level
                px = min(stop_lvl, o[b]) if is_buy else max(stop_lvl, o[b])
                close_trade(b, px, "STOP")
            elif t_hit:
                px = max(tgt_lvl, o[b]) if is_buy else min(tgt_lvl, o[b])
                close_trade(b, px, "TARGET")

    if report is not None:
        report["both_hit_bars"] = both_hit_bars
        report["warmup"] = warmup
    return trades


# ---------------------------------------------------------------------------
# Rigor helpers - the project's standing battery. Same construction as
# research/aurelius/sr_reject_test.py:68-101; reproduced here (they are 30
# lines and self-contained) rather than imported, because that module executes
# `import engine, sim` against whatever is first on sys.path, which would
# resolve to this package and re-enter it.
# ---------------------------------------------------------------------------
from engine import stats, risk_stats            # noqa: E402  (re-export)


def split_stats(trades, n_total, is_frac=0.7):
    """Chronological 70/30 in-sample / out-of-sample split by entry bar."""
    if not trades:
        return None, None
    cutoff = int(n_total * is_frac)
    return (stats([t for t in trades if t["entry_i"] < cutoff]),
            stats([t for t in trades if t["entry_i"] >= cutoff]))


def tail_concentration(trades, k=5):
    """How much of net comes from the top k trades - the ex-top-5 honesty check."""
    if not trades:
        return None
    pnl = sorted([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades], reverse=True)
    net = sum(pnl)
    top = sum(pnl[:k])
    return dict(net=net, topk_pct=100 * top / net if net else float("nan"),
                ex_topk_net=net - top)


def permutation_test(base_trades, candidate_trades, n_draws=800, seed=0):
    """Null: random same-size subsets of the BASE model's OWN trades. Tests
    whether the filtered subset beats an equal-size random draw from the same
    trade population - the strict null for an ADDED filter."""
    rng = np.random.default_rng(seed)
    k = len(candidate_trades)
    pnl_all = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in base_trades])
    real_net = sum((t["exit_px"] - t["entry_px"]) * t["dir"] for t in candidate_trades)
    if k == 0 or k > len(pnl_all):
        return None
    draws = np.array([pnl_all[rng.choice(len(pnl_all), size=k, replace=False)].sum()
                      for _ in range(n_draws)])
    return dict(percentile=100 * (draws < real_net).mean(), real_net=real_net,
                null_mean=float(draws.mean()), null_std=float(draws.std()))


def max_dd(pnl):
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(eq)
    return float((peak - eq).max()) if len(eq) else 0.0


def neg_years(trades):
    yb = yearly(trades)
    return sum(1 for v in yb.values() if v[0] < 0), len(yb)


def permutation_test_bestofN(base_trades, cand_trade_sets, n_draws=2000, seed=0):
    """Best-of-many-cells correction (same construction as
    research/ichimoku/sim.py:179): if N variants were searched and the best
    kept, the null must also be best-of-N."""
    if not base_trades:
        return None
    rng = np.random.default_rng(seed)
    allp = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in base_trades])
    sets = [ts for ts in cand_trade_sets if ts and len(ts) <= len(allp)]
    if not sets:
        return None
    ks = [len(ts) for ts in sets]
    real_best = max(sum((t["exit_px"] - t["entry_px"]) * t["dir"] for t in ts) for ts in sets)
    draws = np.array([max(allp[rng.choice(len(allp), k, replace=False)].sum() for k in ks)
                      for _ in range(n_draws)])
    return dict(percentile=round(100 * float((draws < real_best).mean()), 1),
                real_best=round(real_best, 2), n_cells=len(ks),
                null_mean=round(float(draws.mean()), 2))


def yearly(trades):
    """Net by calendar year - the disguised-date-filter check."""
    import collections
    out = collections.defaultdict(float)
    cnt = collections.Counter()
    for t in trades:
        y = int(str(t["entry_time"])[:4])
        out[y] += (t["exit_px"] - t["entry_px"]) * t["dir"]
        cnt[y] += 1
    return {y: (round(out[y], 1), cnt[y]) for y in sorted(out)}
