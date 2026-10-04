"""
Event-driven, bar-by-bar, EA-faithful replica of HeadShoulders_EA.mq5 -
same quality bar as research/msg/sim.py, built because the earlier
"causal" Python construction (find_breakouts_causal, via
pattern_rigor_common.causal_swing_events) only matched 3% of real trades
on a 3.75yr Silver run (see hs_silver_real_vs_sim.py). Root cause: that
construction discovers a completed 5-swing shape THE INSTANT it's
knowable, scanning the WHOLE history every bar. The real EA does neither:

  - Recompute() (new pattern DISCOVERY) is throttled to every
    InpRecomputeEveryBars=5 new bars, not every bar.
  - Each Recompute() call only sees the most recent InpLookbackBars=800
    bars (CopyRates(0, InpLookbackBars)) - a swing point older than that
    relative to "now" can never be part of a newly-found pattern, even if
    the whole 5-swing sequence would fit within 800 bars of EACH OTHER.
  - AdvancePending() (breakout confirmation/expiry) and CheckForEntry()
    (pullback-retest trigger + single-position gating) DO run every bar -
    only shape DISCOVERY is throttled/windowed.

This file ports Recompute/AdvancePending/CheckForEntry/ManageRunner
line-for-line, including the exact FindSwings/AddSwing tie-break rules
(isH: strictly > the N bars before, >= the N bars after; isL: mirrored),
the AlreadyKnown dedup by (t_s1, t_head, t_s2, top), and the real
single-position "a trigger that fires while a position is open is
permanently marked traded=true, never retried" rule.

REAL BUG FOUND BUILDING THIS (2026-09-27): the first working version still
only matched 1-3% of real trades even with the throttle/window modelled
correctly - CheckForEntry() was reading the WRONG bar. The real EA's
CheckForEntry() runs inside the SAME IsNewBar() block as AdvancePending(),
both reading shift=1 (the bar that JUST closed) - only the fill price
looks at the live ask/bid one bar ahead (~ the new bar's own open). The
first draft evaluated the pullback-retest trigger (h1/l1 vs the neckline)
against the NEXT bar instead of the one AdvancePending just confirmed
against - a full-bar timing misalignment. Fixing it (trigger on bar k,
fill at bar k+1's open) took the real-trade entry-minute match on the
user's real Silver Backtest 2 (2023-2026, 162 real trades) from 1% to
81% (132/162), with the SAME direction on every single matched entry.
NOTE (2026-09-28): that 81% figure was measured with a since-fixed
look-ahead bug in the Recompute() window bound still present (see the
comment at its call site) - re-measured post-fix at 84.6% on the same
report, so the number only improved; not a retraction.
Cold-starting the EA's own state fresh at the tester's start date
(matching MT5 OnInit(), vs. running continuously from 2014) made no
measurable difference - Recompute() is a stateless full-window rescan,
so warm vs. cold priors converge fast.

STILL OPEN: sim finds 349 entries vs. real's 162 in that same window -
132 match, ~217 are extra shapes the real EA never confirmed/traded.
Checked whether these are near-duplicate echoes of matched trades (same
setup, slightly different window-rescan timing) - only 29% land within 2
days of a matched trade, so most are genuinely different pattern
instances, not an artifact of re-discovery. Root cause not yet found;
next place to look is spread-filter fidelity (real InpMaxSpreadPoints=60
vs. this file's per-bar spread column) or a remaining edge case in the
AddSwing merge/dedup logic at window boundaries.

PERFORMANCE: raw pivot candidacy (isH/isL) only depends on a fixed
2N+1-bar local neighbourhood, so it's identical whether computed by a
continuous scan or a windowed one (except within N bars of a window's own
edge) - precomputed once, vectorized. Only the AddSwing merge/dedup pass
(sequential, stateful) is genuinely re-run at every Recompute() checkpoint,
over the sparse list of raw candidates in the current window (tens, not
hundreds of bars) - cheap enough to actually re-run ~1/5 of all bars.
"""
import numpy as np


def build_atr(high, low, close, period, point):
    n = len(high)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    pc = close[:-1]
    tr[1:] = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - pc), np.abs(low[1:] - pc)))
    atr = np.empty(n)
    s = 0.0
    for i in range(n):
        s += tr[i]
        if i >= period:
            s -= tr[i - period]
        cnt = min(i + 1, period)
        atr[i] = max(s / cnt, point)
    return atr


def raw_pivot_candidates(high, low, N):
    """isH[i]/isL[i] exactly as FindSwings: strictly beats the N bars
    before, ties allowed against the N bars after (only a strictly
    greater/lesser later bar invalidates)."""
    n = len(high)
    isH = np.zeros(n, dtype=bool)
    isL = np.zeros(n, dtype=bool)
    for i in range(N, n - N):
        hi, lo = high[i], low[i]
        h_left = high[i - N:i]
        h_right = high[i + 1:i + N + 1]
        l_left = low[i - N:i]
        l_right = low[i + 1:i + N + 1]
        isH[i] = np.all(h_left < hi) and np.all(h_right <= hi)
        isL[i] = np.all(l_left > lo) and np.all(l_right >= lo)
    return isH, isL


def add_swing(typ, idx, px, min_leg, zIdx, zType, zPx):
    if zType and zType[-1] == typ:
        more = (px > zPx[-1]) if typ == 1 else (px < zPx[-1])
        if more:
            zIdx[-1] = idx
            zPx[-1] = px
        return
    if zType and abs(px - zPx[-1]) < min_leg:
        return
    zIdx.append(idx)
    zType.append(typ)
    zPx.append(px)


def find_swings_window(cand_idx, isH, isL, high, low, atr, swing_min_atr, start, end):
    """FindSwings() re-run from scratch over candidates i in [start, end]
    (inclusive) - matches CopyRates(0, InpLookbackBars) + the i=N..lastClosed-N
    loop bound, just restricted to this window's own raw-pivot candidates.
    cand_idx: sorted array of every i where isH[i] or isL[i] - sliced via
    binary search instead of scanning all `lookback_bars` bars every call
    (this runs ~1/5 of all bars, so the difference matters at real scale)."""
    lo = np.searchsorted(cand_idx, start, side="left")
    hi = np.searchsorted(cand_idx, end, side="right")
    zIdx, zType, zPx = [], [], []
    for i in cand_idx[lo:hi]:
        min_leg = swing_min_atr * atr[i]
        if isH[i] and isL[i]:
            if zType and zType[-1] == 1:
                add_swing(-1, i, low[i], min_leg, zIdx, zType, zPx)
                add_swing(1, i, high[i], min_leg, zIdx, zType, zPx)
            else:
                add_swing(1, i, high[i], min_leg, zIdx, zType, zPx)
                add_swing(-1, i, low[i], min_leg, zIdx, zType, zPx)
        elif isH[i]:
            add_swing(1, i, high[i], min_leg, zIdx, zType, zPx)
        elif isL[i]:
            add_swing(-1, i, low[i], min_leg, zIdx, zType, zPx)
    return zIdx, zType, zPx


def find_hs_patterns(zIdx, zType, zPx, atr, shoulder_tol_atr, times):
    """FindHSPatterns() port - 5-swing shape scan on this window's own
    swing chain."""
    out = []
    zc = len(zIdx)
    for m in range(zc - 4):
        seq = zType[m:m + 5]
        if seq == [1, -1, 1, -1, 1]:
            top = True
        elif seq == [-1, 1, -1, 1, -1]:
            top = False
        else:
            continue
        p1, pt1, phead, pt2, p2 = zPx[m:m + 5]
        if top and not (phead > p1 and phead > p2):
            continue
        if (not top) and not (phead < p1 and phead < p2):
            continue
        i_head = zIdx[m + 2]
        if abs(p1 - p2) > shoulder_tol_atr * atr[i_head]:
            continue
        i_s1, i_t1, i_t2, i_s2 = zIdx[m], zIdx[m + 1], zIdx[m + 3], zIdx[m + 4]
        t_t1, t_t2 = times[i_t1], times[i_t2]
        # EA v1.13: per-BAR slope, exactly head_shoulders_target_test.py:95 /
        # hs_next_round_test.py:95,144 - (p_t2 - p_t1) / (i_t2 - i_t1). Was per
        # wall-clock second (t_t2 - t_t1) up to EA v1.12, which over-extended
        # the neckline across weekend/session gaps.
        d_bars = i_t2 - i_t1
        neck_slope = (pt2 - pt1) / d_bars if d_bars != 0 else 0.0
        out.append(dict(top=top, i_s1=i_s1, p_s1=p1, i_t1=i_t1, p_t1=pt1, t_t1=t_t1,
                         i_head=i_head, p_head=phead, i_t2=i_t2, p_t2=pt2, t_t2=t_t2,
                         i_s2=i_s2, p_s2=p2, t_s2=times[i_s2], t_s1=times[i_s1], t_head=times[i_head],
                         neck_slope=neck_slope, brk_t=None, brk_i=-1, traded=False, run=0))
    return out


def neckline_at_bar(P, q):
    """EA v1.13 NecklineAtTime(): p_t1 + slope * (bars from i_t1 to q). The EA
    gets that bar count from iBarShift(t_t1) - iBarShift(t); here it's the
    positional index difference (q - i_t1), identical on the same bar series."""
    return P["p_t1"] + P["neck_slope"] * (q - P["i_t1"])


def simulate(m15, params):
    """m15: DataFrame with time/open/high/low/close/spread (seconds
    resolution not required - times used as integer bar indices via
    to_datetime -> int64 seconds, matching the real EA's datetime
    arithmetic). params: dict with pivot_strength, swing_min_atr,
    atr_period, lookback_bars, recompute_every_bars, shoulder_tol_atr,
    break_tol_atr, break_confirm_closes, max_horizon_mult, stop_buffer_atr,
    use_pullback_entry, pullback_tol_atr, pullback_window_bars,
    use_runner, runner_trail_atr, point, max_spread_points, spread_points
    (array, points -> price via `point`)."""
    t = m15["time"].values.astype("datetime64[s]").astype(np.int64)
    o = m15["open"].values
    h = m15["high"].values
    l = m15["low"].values
    c = m15["close"].values
    sp = m15["spread"].values * params["point"] if "spread" in m15 else np.zeros(len(m15))
    n = len(m15)
    N = params["pivot_strength"]

    atr = build_atr(h, l, c, params["atr_period"], params["point"])
    isH, isL = raw_pivot_candidates(h, l, N)
    cand_idx = np.nonzero(isH | isL)[0]

    pending = []      # list of pattern dicts, not yet confirmed
    confirmed = []     # list of pattern dicts, confirmed, maybe not yet traded
    known_keys = set()  # (t_s1, t_head, t_s2, top) already in pending or confirmed

    trades = []
    pos = None   # dict: dir, entry_px, stop, target(=None if runner), fill_i
    runner = None  # dict: armed, reached_target, peak, target, atr, is_buy, stop, just_armed

    lookback = params["lookback_bars"]
    recompute_every = params["recompute_every_bars"]
    bar_counter = 0

    def finish(exit_i, exit_px, reason):
        nonlocal pos
        d = pos["dir"]
        pnl = (exit_px - pos["entry_px"]) * d
        trades.append(dict(entry_i=pos["fill_i"], entry_t=int(t[pos["fill_i"]]), dir=d,
                            entry_px=pos["entry_px"], exit_i=exit_i, exit_px=exit_px,
                            pnl=pnl, pnl_pct=pnl / pos["entry_px"], reason=reason))
        pos = None

    loop_start = max(2 * N + 1 + params["atr_period"] + 20, 1, params.get("start_k", 0))
    for k in range(loop_start, n - 1):
        # bar k just closed (matches OnTick's IsNewBar block reading shift=1 = bar k)
        t1, c1, h1, l1 = t[k], c[k], h[k], l[k]

        # ---- 1. position management: stop-loss (broker-side, intrabar) ----
        if pos is not None:
            d = pos["dir"]
            hit_sl = (l1 <= pos["stop"]) if d > 0 else (h1 >= pos["stop"])
            hit_tp = (pos["tp"] is not None) and ((h1 >= pos["tp"]) if d > 0 else (l1 <= pos["tp"]))
            if hit_sl and hit_tp:
                first_sl = abs(o[k] - pos["stop"]) <= abs(pos["tp"] - o[k])
            else:
                first_sl = hit_sl
            if hit_sl and first_sl:
                finish(k, pos["stop"], "SL")
                runner = None
            elif hit_tp:
                finish(k, pos["tp"], "TP")
                runner = None

        # ---- 2. ManageRunner (once per bar, skips the bar it was armed on) ----
        if pos is not None and runner is not None and runner["armed"]:
            if runner["just_armed"]:
                runner["just_armed"] = False
            else:
                rh, rl = h1, l1
                if not runner["reached_target"]:
                    hit = (rh >= runner["target"]) if runner["is_buy"] else (rl <= runner["target"])
                    if hit:
                        runner["reached_target"] = True
                        runner["peak"] = runner["target"]
                if runner["reached_target"]:
                    runner["peak"] = max(runner["peak"], rh) if runner["is_buy"] else min(runner["peak"], rl)
                    new_stop = (runner["peak"] - params["runner_trail_atr"] * runner["atr"]) if runner["is_buy"] \
                        else (runner["peak"] + params["runner_trail_atr"] * runner["atr"])
                    improves = (new_stop > runner["stop"]) if runner["is_buy"] else (new_stop < runner["stop"])
                    if improves:
                        runner["stop"] = new_stop
                        pos["stop"] = new_stop

        # ---- 3. Recompute (throttled shape discovery) ----
        bar_counter += 1
        if recompute_every <= 1 or bar_counter % recompute_every == 0:
            win_start = max(0, k - lookback + 2)
            if win_start < k - 4 * N - params["atr_period"] - 20:
                # LOOK-AHEAD FIX (found 2026-09-28 during the H&S-on-Gold bar-match
                # investigation): the real EA's FindSwings only confirms a pivot at
                # shift=N once N bars have closed AFTER it, i.e. only turning points
                # in [win_start+N, k-N] are actually knowable at bar k - the un-
                # clamped end bound let this search "discover" pivots up to N bars
                # into the future. Fixing this makes H&S's untouched-Gold verdict
                # WEAKER (p 0.18 -> 0.30), not stronger - the bug had been flattering
                # it, not hiding a real edge. See GOLD_AUDIT_2026-09-28.md follow-up.
                zIdx, zType, zPx = find_swings_window(cand_idx, isH, isL, h, l, atr, params["swing_min_atr"],
                                                      win_start + N, k - N)
                if len(zIdx) >= 5:
                    found = find_hs_patterns(zIdx, zType, zPx, atr, params["shoulder_tol_atr"], t)
                    for P in found:
                        # v1.11 EA dedup key is head+direction only (AddSwing() can merge a
                        # later, more extreme same-type pivot into s1/s2, re-queuing the same
                        # head as a "new" pattern under the old t_s1/t_s2-inclusive key) -
                        # ported here 2026-10-04 so this sim's dedup matches the EA exactly.
                        key = (P["t_head"], P["top"])
                        if key in known_keys:
                            continue
                        known_keys.add(key)
                        pending.append(P)

        # ---- 4. AdvancePending (breakout confirm / expiry, every bar) ----
        atr_now = atr[k]
        still_pending = []
        for P in pending:
            if t1 <= P["t_s2"]:
                still_pending.append(P)
                continue
            nl = neckline_at_bar(P, k)
            beyond = (nl - c1) if P["top"] else (c1 - nl)
            confirmed_now = False
            if beyond > params["break_tol_atr"] * atr_now:
                P["run"] += 1
                if P["run"] >= params["break_confirm_closes"]:
                    head_height = abs(P["p_head"] - neckline_at_bar(P, P["i_head"]))
                    if head_height > 0.0:
                        P["brk_t"] = t1
                        P["brk_i"] = k
                        P["brk_price"] = c1
                        P["atr_at_brk"] = atr_now
                        P["target"] = (c1 - head_height) if P["top"] else (c1 + head_height)
                        shoulder_ext = max(P["p_s1"], P["p_s2"]) if P["top"] else min(P["p_s1"], P["p_s2"])
                        P["stop"] = (shoulder_ext + params["stop_buffer_atr"] * atr_now) if P["top"] \
                            else (shoulder_ext - params["stop_buffer_atr"] * atr_now)
                        confirmed.append(P)
                        confirmed_now = True
            else:
                P["run"] = 0

            # EA v1.12 bar-count expiry (was wall-clock seconds, which aged a
            # pattern by dead weekend time): patLenBars = shift_s1 - shift_s2,
            # ageBars = shift_s2 - 1, horizonBars = (long)(max(patLenBars,1) * mult).
            # With shift 1 = bar k: shift_s2 - 1 = k - i_s2. The EA's v1.13
            # iBarShift()==-1 drop path has no analogue here (full history is
            # always in memory).
            pat_len_bars = P["i_s2"] - P["i_s1"]
            age_bars_p = k - P["i_s2"]
            horizon_bars = int(max(pat_len_bars, 1) * params["max_horizon_mult"])
            expired = (not confirmed_now) and (age_bars_p > horizon_bars)
            if not (confirmed_now or expired):
                still_pending.append(P)
        pending = still_pending

        # ---- 5. CheckForEntry: trigger evaluated on the SAME just-closed bar
        # k (shift=1) that AdvancePending used - NOT the next bar. Real EA:
        # CheckForEntry() reads iHigh/iLow/iTime(...,1) inside the SAME
        # IsNewBar() block as AdvancePending, both on the bar that just
        # closed. Only the FILL price (current live ask/bid at the moment
        # OnTick fires, i.e. the new/forming bar k+1's own open) looks ahead
        # one bar - the trigger condition itself must not. ----
        if k + 1 < n:
            spread_ok = params["max_spread_points"] <= 0 or (sp[k + 1] / params["point"]) <= params["max_spread_points"]
            can_open = (pos is None) and spread_ok
            o_next = o[k + 1]
            for P in confirmed:
                if P["traded"]:
                    continue
                is_buy = not P["top"]
                if not params["use_pullback_entry"]:
                    trigger = (P["brk_t"] == t1)
                else:
                    if t1 <= P["brk_t"]:
                        continue
                    # EA: brkShift = iBarShift(..., P.brk_t, false); ageBars = brkShift - 1
                    # = k - brk_i (one more retest bar allowed than this sim used to give it -
                    # fixed 2026-10-04, this sim previously computed k - brk_i - 1).
                    age_bars = k - P["brk_i"]
                    if age_bars > params["pullback_window_bars"]:
                        P["traded"] = True
                        continue
                    nl = neckline_at_bar(P, k)
                    tol = params["pullback_tol_atr"] * P["atr_at_brk"]
                    trigger = (h1 >= nl - tol) if P["top"] else (l1 <= nl + tol)
                if not trigger:
                    continue
                if not can_open:
                    P["traded"] = True
                    continue
                ask = o_next + sp[k + 1]
                bid = o_next
                entry = ask if is_buy else bid
                d = 1 if is_buy else -1
                if is_buy and (P["target"] <= entry or P["stop"] >= entry):
                    P["traded"] = True
                    continue
                if (not is_buy) and (P["target"] >= entry or P["stop"] <= entry):
                    P["traded"] = True
                    continue
                P["traded"] = True
                tp = None if params["use_runner"] else P["target"]
                pos = dict(dir=d, entry_px=entry, stop=P["stop"], tp=tp, fill_i=k + 1)
                if params["use_runner"]:
                    runner = dict(armed=True, reached_target=False, peak=0.0, target=P["target"],
                                  atr=P["atr_at_brk"], is_buy=is_buy, stop=P["stop"], just_armed=True)
                else:
                    runner = None
                break

    if pos is not None:
        finish(n - 1, c[n - 1], "EOD")
    return trades


DEFAULTS = dict(
    pivot_strength=5, swing_min_atr=1.0, atr_period=14, lookback_bars=800, recompute_every_bars=5,
    shoulder_tol_atr=1.5, break_tol_atr=0.35, break_confirm_closes=3, max_horizon_mult=4.0,
    stop_buffer_atr=1.0, use_pullback_entry=True, pullback_tol_atr=0.75, pullback_window_bars=30,
    use_runner=True, runner_trail_atr=0.5, max_spread_points=60,
)
