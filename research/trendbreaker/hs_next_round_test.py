"""
User: "test everything that can be tested" on HeadShoulders_EA. Three real
tests, all single-position sequenced (the exact lesson from today's giveback-
exit mistake - a change that alters how long a trade stays open changes which
LATER patterns get traded at all, so every test below processes breakouts in
true chronological order with last_exit_bar gating, not independently).

All on M15 (868 confirmed breakouts, the EA's own real-tested timeframe),
using the already-validated 1.0xATR stop (research/trendbreaker/
hs_stop_loss_test.py's real finding) as the baseline to beat, not the
original 0.3xATR - no point re-deriving a worse baseline.

1. PULLBACK ENTRY: wait for a retest of the neckline after confirmation
   instead of entering at market on the confirming close - the classic real
   H&S refinement, and untested until now.
2. THRESHOLD SWEEP: SHOULDER_TOL_ATR (how level the shoulders must be) and
   BREAK_TOL_ATR/BREAK_CONFIRM_CLOSES (how the breakout gets confirmed) -
   carried over from the original design, never independently optimized.
3. RUNNER PAST TARGET: trail a stop behind price once the measured target is
   reached, instead of closing 100% there - tested on MSG's TP3 (real
   result: negative, but only 19 samples) and never tested on H&S's own,
   structurally different, measured-move target.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_CONFIRM_CLOSES as DEFAULT_BCC
from head_shoulders_target_test import find_hs_patterns, SHOULDER_TOL_ATR as DEFAULT_STOL, \
    BREAK_TOL_ATR as DEFAULT_BTOL, MAX_HORIZON_MULT, MAX_HORIZON_CAP

np.random.seed(42)
STOP_BUFFER = 1.0   # already-validated real finding, used as baseline everywhere below


def find_breakouts_full(df, shoulder_tol=DEFAULT_STOL, break_tol=DEFAULT_BTOL, break_confirm=DEFAULT_BCC,
                        causal=True):
    """BUG FIX (2026-09-26, same lookahead class as the Wolfe Wave CONFIRM_LAG
    and Bump-and-Run fixes - see hs_causal_detection_check.py for the full
    write-up and before/after numbers): the original implementation (kept
    below as find_breakouts_full_lookahead, reachable with causal=False to
    reproduce old results) counted neckline-break closes from i_s2+1 even
    though the right shoulder is a PIVOT_STRENGTH-bar fractal not knowable
    until i_s2+PIVOT_STRENGTH (26% of 2022-26 M15 breakouts confirmed before
    the shape could exist), and ran on the FINAL zigzag (hindsight about
    which provisional right shoulder survived). HeadShoulders_EA.mq5 itself
    was always causal (Recompute() queues a shape only once FindSwings()
    confirms it; AdvancePending() counts closes from then on) - only this
    Python EVIDENCE was affected. Default is now the EA-faithful causal
    detector. Effect: IS 2022-26 %PF 2.014 -> 1.961 (still 100th pct);
    real-M15 OOS 2014-06 -> 2022-07 %PF 1.490 -> 1.442 (99.9th pct,
    survives K=27, borderline K=50)."""
    if causal:
        return find_breakouts_causal(df, shoulder_tol, break_tol, break_confirm)
    return find_breakouts_full_lookahead(df, shoulder_tol, break_tol, break_confirm)


def find_breakouts_causal(df, shoulder_tol=DEFAULT_STOL, break_tol=DEFAULT_BTOL, break_confirm=DEFAULT_BCC):
    """EA-faithful: every shape HeadShoulders_EA's per-bar Recompute() would
    ever queue (found on causal_swing_events() snapshots, deduped by its
    s1/head/s2 anchors like AlreadyKnown()), closes counted only from the bar
    the shape became knowable (right shoulder + PIVOT_STRENGTH, inclusive -
    that close is known at the same moment as the pivot, matching
    AdvancePending's order). Everything else identical to the original."""
    import pattern_rigor_common as R
    from h4_touch_reaction_test import PIVOT_STRENGTH
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    events, _ = R.causal_swing_events(o, h, l, c, atr, tail=12)
    seen = set()
    breakouts = []
    for known, snap in events:
        types = [s[1] for s in snap]
        for m in range(len(snap) - 4):
            seq = types[m:m + 5]
            if seq == [1, -1, 1, -1, 1]:
                top = True
            elif seq == [-1, 1, -1, 1, -1]:
                top = False
            else:
                continue
            (i1, _, p1), (it1, _, t1), (i2, _, p2), (it2, _, t2), (i3, _, p3) = snap[m:m + 5]
            if top and not (p2 > p1 and p2 > p3):
                continue
            if (not top) and not (p2 < p1 and p2 < p3):
                continue
            key = (i1, i2, i3, top)
            if key in seen:
                continue
            seen.add(key)
            if abs(p1 - p3) > shoulder_tol * atr[i2]:
                continue
            neck_slope = (t2 - t1) / (it2 - it1) if it2 != it1 else 0.0

            def neckline_at(q, ia=it1, neck_slope=neck_slope, p_t1=t1):
                return p_t1 + neck_slope * (q - ia)

            head_height = abs(p2 - neckline_at(i2))
            if head_height <= 0:
                continue
            pattern_len = i3 - i1
            horizon_end = min(n - 1, i3 + int(min(pattern_len * MAX_HORIZON_MULT, MAX_HORIZON_CAP)))
            q_from = max(known, i3 + PIVOT_STRENGTH)
            brk_q, run_ = -1, 0
            for q in range(q_from, horizon_end):
                nl = neckline_at(q)
                beyond = (nl - c[q]) if top else (c[q] - nl)
                if beyond > break_tol * atr[q]:
                    run_ += 1
                    if run_ >= break_confirm:
                        brk_q = q; break
                else:
                    run_ = 0
            if brk_q < 0:
                continue
            brk_price = c[brk_q]
            target = (brk_price - head_height) if top else (brk_price + head_height)
            shoulder_ext = max(p1, p3) if top else min(p1, p3)
            breakouts.append(dict(top=top, brk_q=brk_q, brk_price=brk_price, target=target,
                                  i_s1=i1, i_head=i2, i_s2=i3, p_s1=p1, p_head=p2, p_s2=p3,
                                  i_t1=it1, i_t2=it2, head_height=head_height, shoulder_ext=shoulder_ext,
                                  atr_at_brk=atr[brk_q], max_horizon=min(n - 1, brk_q + MAX_HORIZON_CAP),
                                  neckline_at=neckline_at, known=known))
    return sorted(breakouts, key=lambda x: x["brk_q"]), h, l, c, atr


def find_breakouts_full_lookahead(df, shoulder_tol=DEFAULT_STOL, break_tol=DEFAULT_BTOL, break_confirm=DEFAULT_BCC):
    """ORIGINAL (pre-2026-09-26) implementation - has the lookahead described
    in find_breakouts_full()'s docstring. Kept only to reproduce old numbers."""
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)

    breakouts = []
    for top in (True, False):
        pats = find_hs_patterns(zIdx, zType, zPx, top)
        shoulder_ok = [p for p in pats
                       if abs(p["p_s1"] - p["p_s2"]) <= shoulder_tol * atr[p["i_head"]]]
        for p in shoulder_ok:
            ia, ib = p["i_t1"], p["i_t2"]
            neck_slope = (p["p_t2"] - p["p_t1"]) / (ib - ia) if ib != ia else 0.0

            def neckline_at(q, ia=ia, neck_slope=neck_slope, p_t1=p["p_t1"]):
                return p_t1 + neck_slope * (q - ia)

            head_height = abs(p["p_head"] - neckline_at(p["i_head"]))
            if head_height <= 0:
                continue
            pattern_len = p["i_s2"] - p["i_s1"]
            horizon_end = min(n - 1, p["i_s2"] + int(min(pattern_len * MAX_HORIZON_MULT, MAX_HORIZON_CAP)))

            brk_q, run_ = -1, 0
            for q in range(p["i_s2"] + 1, horizon_end):
                nl = neckline_at(q)
                beyond = (nl - c[q]) if top else (c[q] - nl)
                if beyond > break_tol * atr[q]:
                    run_ += 1
                    if run_ >= break_confirm:
                        brk_q = q; break
                else:
                    run_ = 0
            if brk_q < 0:
                continue

            brk_price = c[brk_q]
            target = (brk_price - head_height) if top else (brk_price + head_height)
            shoulder_ext = max(p["p_s1"], p["p_s2"]) if top else min(p["p_s1"], p["p_s2"])
            max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
            breakouts.append(dict(top=top, brk_q=brk_q, brk_price=brk_price, target=target,
                                   i_s1=p["i_s1"], i_head=p["i_head"], i_s2=p["i_s2"],
                                   p_s1=p["p_s1"], p_head=p["p_head"], p_s2=p["p_s2"],
                                   i_t1=p["i_t1"], i_t2=p["i_t2"],
                                   head_height=head_height, shoulder_ext=shoulder_ext,
                                   atr_at_brk=atr[brk_q], max_horizon=max_horizon,
                                   neckline_at=neckline_at))
    return sorted(breakouts, key=lambda x: x["brk_q"]), h, l, c, atr


def eval_market_entry(breakouts, h, l, c, stop_buffer):
    results, last_exit = [], -1
    for b in breakouts:
        top, brk_q, entry, target = b["top"], b["brk_q"], b["brk_price"], b["target"]
        if brk_q < last_exit:
            continue
        stop = (b["shoulder_ext"] + stop_buffer * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - stop_buffer * b["atr_at_brk"])
        if (top and stop <= entry) or ((not top) and stop >= entry):
            continue
        outcome, exit_bar = walk(h, l, top, brk_q, b["max_horizon"], stop, target)
        pnl = pnl_of(outcome, entry, stop, target, c, exit_bar, top)
        results.append(dict(brk_q=brk_q, outcome=outcome, pnl=pnl))
        last_exit = exit_bar
    return results


def eval_pullback_entry(breakouts, h, l, c, stop_buffer, retest_tol_atr, retest_window):
    """Wait for the FIRST bar after confirmation where price returns to
    within retest_tol_atr*ATR of the neckline (a real throwback), enter
    there instead of at market on the confirm bar. Skip (miss) the trade if
    no retest happens within retest_window bars."""
    results, last_exit, missed = [], -1, 0
    for b in breakouts:
        top, brk_q, target = b["top"], b["brk_q"], b["target"]
        if brk_q < last_exit:
            continue
        tol = retest_tol_atr * b["atr_at_brk"]
        entry_bar, entry = None, None
        for q in range(brk_q + 1, min(brk_q + 1 + retest_window, b["max_horizon"])):
            nl = b["neckline_at"](q)
            touched = (h[q] >= nl - tol) if top else (l[q] <= nl + tol)
            if touched:
                entry_bar, entry = q, nl
                break
        if entry_bar is None:
            missed += 1
            continue
        stop = (b["shoulder_ext"] + stop_buffer * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - stop_buffer * b["atr_at_brk"])
        if (top and stop <= entry) or ((not top) and stop >= entry):
            continue
        outcome, exit_bar = walk(h, l, top, entry_bar, b["max_horizon"], stop, target)
        pnl = pnl_of(outcome, entry, stop, target, c, exit_bar, top)
        results.append(dict(brk_q=entry_bar, outcome=outcome, pnl=pnl))
        last_exit = exit_bar
    return results, missed


def eval_runner(breakouts, h, l, c, stop_buffer, trail_atr_mult):
    """Once the real target is reached, instead of closing, trail a stop
    behind price by trail_atr_mult x ATR and keep riding until stopped or
    horizon runs out."""
    results, last_exit = [], -1
    for b in breakouts:
        top, brk_q, entry, target = b["top"], b["brk_q"], b["brk_price"], b["target"]
        if brk_q < last_exit:
            continue
        stop = (b["shoulder_ext"] + stop_buffer * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - stop_buffer * b["atr_at_brk"])
        if (top and stop <= entry) or ((not top) and stop >= entry):
            continue
        atrv = b["atr_at_brk"]
        cur_stop = stop
        outcome, exit_bar, exit_px = None, None, None
        reached_target = False
        peak = entry
        for k in range(brk_q + 1, b["max_horizon"] + 1):
            hit_stop = (h[k] >= cur_stop) if top else (l[k] <= cur_stop)
            if hit_stop:
                outcome, exit_bar, exit_px = ("TARGET_TRAIL" if reached_target else "STOP"), k, cur_stop
                break
            hit_target = (l[k] <= target) if top else (h[k] >= target)
            if hit_target and not reached_target:
                reached_target = True
                peak = target
            if reached_target:
                if top:
                    peak = min(peak, l[k])
                    cur_stop = min(cur_stop, peak + trail_atr_mult * atrv)
                else:
                    peak = max(peak, h[k])
                    cur_stop = max(cur_stop, peak - trail_atr_mult * atrv)
        if outcome is None:
            outcome, exit_bar, exit_px = "HORIZON", b["max_horizon"], c[min(b["max_horizon"], len(c) - 1)]
        pnl = (entry - exit_px) if top else (exit_px - entry)
        results.append(dict(brk_q=brk_q, outcome=outcome, pnl=pnl))
        last_exit = exit_bar
    return results


def walk(h, l, top, start_bar, max_horizon, stop, target):
    for k in range(start_bar + 1, max_horizon + 1):
        hit_stop = (h[k] >= stop) if top else (l[k] <= stop)
        hit_target = (l[k] <= target) if top else (h[k] >= target)
        if hit_stop and hit_target:
            return "STOP", k
        if hit_stop:
            return "STOP", k
        if hit_target:
            return "TARGET", k
    return "HORIZON", max_horizon


def pnl_of(outcome, entry, stop, target, c, exit_bar, top):
    if outcome == "TARGET":
        return abs(target - entry)
    if outcome == "STOP":
        return -abs(entry - stop)
    final_px = c[min(exit_bar, len(c) - 1)]
    return (entry - final_px) if top else (final_px - entry)


def report(results, label, missed=None):
    n = len(results)
    if n < 8:
        print(f"  {label}: only {n} trades - too few"); return
    pnl = np.array([r["pnl"] for r in results])
    wins = sum(1 for r in results if r["pnl"] > 0)
    gw = pnl[pnl > 0].sum(); gl = -pnl[pnl <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    brk = np.array([r["brk_q"] for r in results])
    order = np.argsort(brk)
    cutoff = brk[order][int(n * 0.7)]
    is_m = brk < cutoff; oos_m = brk >= cutoff
    is_win = 100 * np.mean([results[i]["pnl"] > 0 for i in np.where(is_m)[0]]) if is_m.sum() >= 8 else float("nan")
    oos_win = 100 * np.mean([results[i]["pnl"] > 0 for i in np.where(oos_m)[0]]) if oos_m.sum() >= 8 else float("nan")
    miss_str = f"  (missed {missed})" if missed is not None else ""
    print(f"  {label}: n={n}{miss_str}  win%={100*wins/n:.1f}  net={pnl.sum():.2f}  pf={pf:.3f}  "
          f"IS win%={is_win:.1f} n={is_m.sum()}  OOS win%={oos_win:.1f} n={oos_m.sum()}")


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)

    print("=" * 95)
    print("BASELINE (market entry, 1.0xATR stop - already-validated finding, used as the bar to beat)")
    print("=" * 95)
    breakouts, h, l, c, atr = find_breakouts_full(df15)
    baseline = eval_market_entry(breakouts, h, l, c, STOP_BUFFER)
    report(baseline, "market entry")

    print("\n" + "=" * 95)
    print("TEST 1: PULLBACK/RETEST ENTRY (wait for a throwback to the neckline instead of entering at market)")
    print("=" * 95)
    for tol, window in ((0.15, 10), (0.25, 15), (0.35, 20), (0.5, 30)):
        res, missed = eval_pullback_entry(breakouts, h, l, c, STOP_BUFFER, tol, window)
        report(res, f"retest_tol={tol:.2f}xATR window={window}bars", missed=missed)

    print("\n" + "=" * 95)
    print("TEST 2: THRESHOLD SWEEP (shoulder tolerance, break confirmation)")
    print("=" * 95)
    for stol in (1.0, 1.5, 2.0, 2.5):
        b2, h2, l2, c2, _ = find_breakouts_full(df15, shoulder_tol=stol)
        res = eval_market_entry(b2, h2, l2, c2, STOP_BUFFER)
        tag = "  <-- current default" if stol == DEFAULT_STOL else ""
        report(res, f"SHOULDER_TOL_ATR={stol:.1f}{tag}")
    for bcc in (1, 2, 3, 4, 5):
        b2, h2, l2, c2, _ = find_breakouts_full(df15, break_confirm=bcc)
        res = eval_market_entry(b2, h2, l2, c2, STOP_BUFFER)
        tag = "  <-- current default" if bcc == DEFAULT_BCC else ""
        report(res, f"BREAK_CONFIRM_CLOSES={bcc}{tag}")
    for btol in (0.05, 0.10, 0.20, 0.35):
        b2, h2, l2, c2, _ = find_breakouts_full(df15, break_tol=btol)
        res = eval_market_entry(b2, h2, l2, c2, STOP_BUFFER)
        tag = "  <-- current default" if btol == DEFAULT_BTOL else ""
        report(res, f"BREAK_TOL_ATR={btol:.2f}{tag}")

    print("\n" + "=" * 95)
    print("TEST 3: RUNNER PAST THE MEASURED TARGET (trail instead of closing 100% at target)")
    print("=" * 95)
    for trail_mult in (0.5, 1.0, 1.5, 2.0, 3.0):
        res = eval_runner(breakouts, h, l, c, STOP_BUFFER, trail_mult)
        report(res, f"trail={trail_mult:.1f}xATR after target")


def eval_pullback_and_runner(breakouts, h, l, c, stop_buffer, retest_tol_atr, retest_window, trail_atr_mult):
    """Combines TEST 1 (pullback/retest entry) with TEST 3 (runner past
    target) - single-position sequenced, using find_breakouts_full's own
    break_tol setting (TEST 2's finding) already baked into `breakouts`."""
    results, last_exit, missed = [], -1, 0
    for b in breakouts:
        top, brk_q, target = b["top"], b["brk_q"], b["target"]
        if brk_q < last_exit:
            continue
        tol = retest_tol_atr * b["atr_at_brk"]
        entry_bar, entry = None, None
        for q in range(brk_q + 1, min(brk_q + 1 + retest_window, b["max_horizon"])):
            nl = b["neckline_at"](q)
            touched = (h[q] >= nl - tol) if top else (l[q] <= nl + tol)
            if touched:
                entry_bar, entry = q, nl
                break
        if entry_bar is None:
            missed += 1
            continue
        stop = (b["shoulder_ext"] + stop_buffer * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - stop_buffer * b["atr_at_brk"])
        if (top and stop <= entry) or ((not top) and stop >= entry):
            continue
        atrv = b["atr_at_brk"]
        cur_stop = stop
        outcome, exit_bar, exit_px = None, None, None
        reached_target = False
        peak = entry
        for k in range(entry_bar + 1, b["max_horizon"] + 1):
            hit_stop = (h[k] >= cur_stop) if top else (l[k] <= cur_stop)
            if hit_stop:
                outcome, exit_bar, exit_px = ("TARGET_TRAIL" if reached_target else "STOP"), k, cur_stop
                break
            hit_target = (l[k] <= target) if top else (h[k] >= target)
            if hit_target and not reached_target:
                reached_target = True
                peak = target
            if reached_target:
                if top:
                    peak = min(peak, l[k])
                    cur_stop = min(cur_stop, peak + trail_atr_mult * atrv)
                else:
                    peak = max(peak, h[k])
                    cur_stop = max(cur_stop, peak - trail_atr_mult * atrv)
        if outcome is None:
            outcome, exit_bar, exit_px = "HORIZON", b["max_horizon"], c[min(b["max_horizon"], len(c) - 1)]
        pnl = (entry - exit_px) if top else (exit_px - entry)
        results.append(dict(brk_q=entry_bar, outcome=outcome, pnl=pnl))
        last_exit = exit_bar
    return results, missed


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "stacked":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)

    print("=" * 95)
    print("STACKED: pullback entry (0.50xATR/30bar) + BREAK_TOL_ATR=0.35 + runner (0.5xATR trail)")
    print("=" * 95)
    breakouts035, h, l, c, atr = find_breakouts_full(df15, break_tol=0.35)
    res, missed = eval_pullback_and_runner(breakouts035, h, l, c, STOP_BUFFER, 0.50, 30, 0.5)
    report(res, "STACKED (all three)", missed=missed)

    print("\nfor comparison, individual results (break_tol=0.35 breakout set used throughout):")
    baseline035 = eval_market_entry(breakouts035, h, l, c, STOP_BUFFER)
    report(baseline035, "market entry, break_tol=0.35 alone")
    pullback_only, missed_p = eval_pullback_entry(breakouts035, h, l, c, STOP_BUFFER, 0.50, 30)
    report(pullback_only, "+ pullback entry (break_tol=0.35, no runner)", missed=missed_p)
    runner_only = eval_runner(breakouts035, h, l, c, STOP_BUFFER, 0.5)
    report(runner_only, "+ runner only (break_tol=0.35, market entry)")

    print("\nrobustness check - nearby settings on the stacked combo:")
    for tol, window, trail in ((0.35, 20, 0.5), (0.50, 30, 1.0), (0.50, 20, 0.5), (0.75, 30, 0.5)):
        res2, missed2 = eval_pullback_and_runner(breakouts035, h, l, c, STOP_BUFFER, tol, window, trail)
        report(res2, f"retest={tol:.2f}xATR/{window}bar trail={trail:.1f}xATR", missed=missed2)
