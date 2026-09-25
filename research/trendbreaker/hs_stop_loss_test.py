"""
HeadShoulders_EA.mq5's real backtest (2026-09-25, M15 GOLD, 2023.01-2026.09,
InpLookbackBars=3000, pre-speed-fix but trading logic untouched by that fix):
599 trades, net $13,999 (+70%), PF 1.161, win 44.57%, equity DD 22.93%,
11-trade losing streak -$4,313. Real, profitable, but thin - and there's a
big gap against the standalone pattern research: the H&S measured-move
target itself gets HIT 75.2% of the time on M15 (m15_head_shoulders_
target_test.py, 868 confirmed breakouts, no stop-loss in that test at all,
just target-or-horizon). The EA's own header discloses its stop as NOT
validated: InpStopBufferATR=0.3, SL = the worse of the two shoulders +/-
0.3xATR (HeadShoulders_EA.mq5 ~403-405: shoulderExt = MAX(p_s1,p_s2) for a
top / MIN(p_s1,p_s2) for inverse).

This test: reuses find_hs_patterns/find_swings/shoulder-tolerance/breakout-
confirmation EXACTLY as head_shoulders_target_test.py (same real construction
behind the 75.2% figure), then adds the EA's REAL stop calculation and walks
forward bar-by-bar checking whichever comes first - stop or target. Two
questions:
  1. How much of the 75.2%->44.57% gap does the current 0.3xATR stop alone
     explain (i.e. of the trades that get stopped, how many would have gone
     on to reach the original target anyway - a "premature stop" rate)?
  2. Does a different stop buffer (swept 0.3-2.0xATR) produce better real
     economics (win rate AND $ net, not just win rate alone - a wider stop
     avoids being premature but risks larger losses on the ones that really
     do fail), with a chronological 70/30 walk-forward check?
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_CONFIRM_CLOSES
from head_shoulders_target_test import find_hs_patterns, SHOULDER_TOL_ATR, BREAK_TOL_ATR, \
    MAX_HORIZON_MULT, MAX_HORIZON_CAP

np.random.seed(42)

STOP_BUFFERS = (0.3, 0.5, 0.75, 1.0, 1.5, 2.0)


def find_breakouts(df):
    """Identical construction to head_shoulders_target_test.py's run(), up to
    and including breakout confirmation - returns one dict per confirmed
    breakout with everything needed to test different stops."""
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)

    breakouts = []
    for top in (True, False):
        pats = find_hs_patterns(zIdx, zType, zPx, top)
        shoulder_ok = [p for p in pats
                       if abs(p["p_s1"] - p["p_s2"]) <= SHOULDER_TOL_ATR * atr[p["i_head"]]]
        for p in shoulder_ok:
            ia, ib = p["i_t1"], p["i_t2"]
            neck_slope = (p["p_t2"] - p["p_t1"]) / (ib - ia) if ib != ia else 0.0

            def neckline_at(q, ia=ia, neck_slope=neck_slope):
                return p["p_t1"] + neck_slope * (q - ia)

            head_height = abs(p["p_head"] - neckline_at(p["i_head"]))
            if head_height <= 0:
                continue
            pattern_len = p["i_s2"] - p["i_s1"]
            horizon_end = min(n - 1, p["i_s2"] + int(min(pattern_len * MAX_HORIZON_MULT, MAX_HORIZON_CAP)))

            brk_q, run_ = -1, 0
            for q in range(p["i_s2"] + 1, horizon_end):
                nl = neckline_at(q)
                beyond = (nl - c[q]) if top else (c[q] - nl)
                if beyond > BREAK_TOL_ATR * atr[q]:
                    run_ += 1
                    if run_ >= BREAK_CONFIRM_CLOSES:
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
                                   head_height=head_height, shoulder_ext=shoulder_ext,
                                   atr_at_brk=atr[brk_q], max_horizon=max_horizon))
    return breakouts, h, l, c


def evaluate(breakouts, h, l, c, stop_buffer_atr):
    """For each breakout, walk forward checking stop-or-target (whichever
    first). Also checks, for stopped trades only, whether the ORIGINAL
    target still gets hit later (within the same overall horizon) - the
    "premature stop" diagnostic.

    SINGLE-POSITION SEQUENCED (2026-09-25 fix - the exact cascade mistake
    just caught and fixed for the giveback-exit research applies here too:
    HeadShoulders_EA.mq5 is single-position (CheckForEntry: `if(g_ticket !=
    0) return`), so a WIDER stop keeps a trade open longer, which blocks
    OTHER confirmed patterns that form while it's still open from ever being
    traded at all - exactly the mechanism that made the giveback Python
    estimate wrong. Breakouts are processed in chronological order (already
    guaranteed by find_breakouts' forward scan) and any breakout whose entry
    bar falls before the previous trade's real exit bar is skipped, not
    independently evaluated - so different stop widths now produce genuinely
    different, properly comparable trade COUNTS, not just different outcomes
    on the same fixed list."""
    results = []
    last_exit_bar = -1
    # find_breakouts() appends ALL top-pattern breakouts then ALL inverse-
    # pattern breakouts (two separate forward scans) - sort by brk_q here so
    # the single-position sequencing above walks true chronological order
    # across BOTH pattern types combined, not top-then-inverse.
    for b in sorted(breakouts, key=lambda x: x["brk_q"]):
        top, brk_q, entry, target = b["top"], b["brk_q"], b["brk_price"], b["target"]
        if brk_q < last_exit_bar:
            continue
        stop = (b["shoulder_ext"] + stop_buffer_atr * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - stop_buffer_atr * b["atr_at_brk"])
        # a stop that's already past entry (shoulder too close) can't be traded - matches
        # the EA's own real rejection (CheckForEntry: "if isBuy && P.stop >= entry: skip")
        if top and stop <= entry:
            continue
        if (not top) and stop >= entry:
            continue

        outcome, exit_bar = None, None
        for k in range(brk_q + 1, b["max_horizon"] + 1):
            hit_stop = (h[k] >= stop) if top else (l[k] <= stop)
            hit_target = (l[k] <= target) if top else (h[k] >= target)
            if hit_stop and hit_target:
                # same-bar ambiguity - conservative: assume the worse outcome (stop) fired first,
                # matching this project's usual "ambiguous -> logged, assume adverse" convention
                outcome, exit_bar = "STOP", k
                break
            if hit_stop:
                outcome, exit_bar = "STOP", k
                break
            if hit_target:
                outcome, exit_bar = "TARGET", k
                break
        if outcome is None:
            outcome, exit_bar = "HORIZON", b["max_horizon"]

        pnl = None
        if outcome == "TARGET":
            pnl = abs(target - entry)
        elif outcome == "STOP":
            pnl = -abs(entry - stop)
        else:
            final_px = c[min(exit_bar, len(c) - 1)]
            pnl = (entry - final_px) if top else (final_px - entry)

        # premature-stop diagnostic: for STOP outcomes, does price still reach
        # the original target later in the SAME horizon?
        reached_target_after_stop = False
        if outcome == "STOP":
            for k in range(exit_bar + 1, b["max_horizon"] + 1):
                if (l[k] <= target) if top else (h[k] >= target):
                    reached_target_after_stop = True
                    break

        results.append(dict(top=top, brk_q=brk_q, outcome=outcome, pnl=pnl,
                             reached_target_after_stop=reached_target_after_stop,
                             risk=abs(entry - stop)))
        last_exit_bar = exit_bar
    return results


def report(results, label):
    n = len(results)
    if n < 8:
        print(f"  {label}: only {n} trades - too few"); return
    pnl = np.array([r["pnl"] for r in results])
    wins = sum(1 for r in results if r["outcome"] == "TARGET")
    stops = sum(1 for r in results if r["outcome"] == "STOP")
    horizon = n - wins - stops
    gw = pnl[pnl > 0].sum(); gl = -pnl[pnl <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    premature = [r for r in results if r["outcome"] == "STOP" and r["reached_target_after_stop"]]
    print(f"  {label}: n={n}  win%={100*wins/n:.1f} (target={wins}, stop={stops}, horizon-cap={horizon})  "
          f"net={pnl.sum():.2f}  pf={pf:.3f}")
    if stops:
        print(f"    of {stops} stopped trades, {len(premature)} ({100*len(premature)/stops:.1f}%) "
              f"still reached the original target later - premature stop")

    brk = np.array([r["brk_q"] for r in results])
    order = np.argsort(brk)
    cutoff = brk[order][int(n * 0.7)]
    is_m = brk < cutoff; oos_m = brk >= cutoff
    if is_m.sum() >= 8 and oos_m.sum() >= 8:
        print(f"    IS  n={is_m.sum()} net={pnl[is_m].sum():.2f} win%={100*np.mean([results[i]['outcome']=='TARGET' for i in np.where(is_m)[0]]):.1f}")
        print(f"    OOS n={oos_m.sum()} net={pnl[oos_m].sum():.2f} win%={100*np.mean([results[i]['outcome']=='TARGET' for i in np.where(oos_m)[0]]):.1f}")


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()

    print("=" * 90)
    print("M15 (real EA's own tested timeframe)")
    print("=" * 90)
    df15 = E.resample_m15_from_m5(df5)
    breakouts15, h15, l15, c15 = find_breakouts(df15)
    print(f"confirmed breakouts: {len(breakouts15)}\n")
    for buf in STOP_BUFFERS:
        res = evaluate(breakouts15, h15, l15, c15, buf)
        tag = "  <-- EA's shipped default" if buf == 0.3 else ""
        report(res, f"stop_buffer={buf:.2f}xATR{tag}")

    print("\n" + "=" * 90)
    print("H4 (cross-validation)")
    print("=" * 90)
    breakouts4, h4a, l4a, c4a = find_breakouts(h4)
    print(f"confirmed breakouts: {len(breakouts4)}\n")
    for buf in STOP_BUFFERS:
        res = evaluate(breakouts4, h4a, l4a, c4a, buf)
        tag = "  <-- EA's shipped default" if buf == 0.3 else ""
        report(res, f"stop_buffer={buf:.2f}xATR{tag}")
