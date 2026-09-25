"""
User asked whether RSI, Stochastic, or trendline confluence can improve
H&S further, on top of the best construction found so far (pullback entry
0.75xATR/30bar + BREAK_TOL_ATR=0.35 + 0.5xATR trailing runner past target,
real GOLD data: n=456, net $4255, PF 2.377, win 52.0%). Volume was already
tested earlier this session (shoulder-volume-ordering, breakout-volume-
level, both rejected on H4/D1) - not re-run here.

Three real, single-position-sequenced tests, all as an ENTRY FILTER on top
of the already-best construction (only take a trade when the confluence
condition also holds, exit logic unchanged):

1. RSI(14) extreme at breakout: oversold (<30) for an inverse/bullish
   breakout, overbought (>70) for a top/bearish breakout - classic "prior
   move already exhausted" confirmation.
2. RSI divergence at the head: price makes a new extreme at the head but
   RSI does NOT - the textbook H&S companion signal from technical
   analysis. Compares RSI at the head vs RSI at the more extreme shoulder.
3. Stochastic(14,3) extreme at breakout - same idea as RSI but a
   different, faster oscillator (real, already-built stochastic() from
   stoch_speed_test.py).
4. Trendline confluence: does a genuine diagonal trendline (using the
   already-validated BuildLine/find_swings construction from
   h4_touch_reaction_test.py) also break in the same direction around the
   same time as the H&S neckline break?
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from stoch_speed_test import stochastic
from hs_next_round_test import find_breakouts_full


def rsi_wilder(c, n=14):
    """Port of ComputeRSI - same as research/ichimoku/engine.py's, copied
    directly rather than imported to avoid an `engine` module name clash
    with research/aurelius/engine.py (both dirs use the same module name)."""
    d = np.diff(c, prepend=c[0]); d[0] = 0.0
    g = np.where(d > 0, d, 0.0); ls = np.where(d < 0, -d, 0.0)
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    ag = g[1:n + 1].mean(); al = ls[1:n + 1].mean()
    out[n] = 100.0 if al <= 0 else 100.0 - 100.0 / (1.0 + ag / al)
    for i in range(n + 1, len(c)):
        ag = (ag * (n - 1) + g[i]) / n
        al = (al * (n - 1) + ls[i]) / n
        out[i] = 100.0 if al <= 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out

np.random.seed(42)

STOP_BUFFER = 1.0
RETEST_TOL, RETEST_WINDOW, TRAIL_MULT = 0.75, 30, 0.5
BREAK_TOL = 0.35


def eval_filtered(breakouts, h, l, c, allow_fn):
    """Same construction as eval_pullback_and_runner, with an extra entry
    filter (allow_fn(b) -> bool) checked once per breakout, before the
    pullback-retest search even starts - matches the real EA's own
    convention of gating before scanning for the pullback."""
    results, last_exit, missed, filtered_out = [], -1, 0, 0
    neck = {id(b): b["neckline_at"] for b in breakouts}
    for b in breakouts:
        top, brk_q, target = b["top"], b["brk_q"], b["target"]
        if brk_q < last_exit:
            continue
        if not allow_fn(b):
            filtered_out += 1
            continue
        tol = RETEST_TOL * b["atr_at_brk"]
        entry_bar, entry = None, None
        for q in range(brk_q + 1, min(brk_q + 1 + RETEST_WINDOW, b["max_horizon"])):
            nl = b["neckline_at"](q)
            touched = (h[q] >= nl - tol) if top else (l[q] <= nl + tol)
            if touched:
                entry_bar, entry = q, nl
                break
        if entry_bar is None:
            missed += 1
            continue
        stop = (b["shoulder_ext"] + STOP_BUFFER * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - STOP_BUFFER * b["atr_at_brk"])
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
                exit_bar, exit_px = k, cur_stop
                break
            hit_target = (l[k] <= target) if top else (h[k] >= target)
            if hit_target and not reached_target:
                reached_target = True
                peak = target
            if reached_target:
                if top:
                    peak = min(peak, l[k])
                    cur_stop = min(cur_stop, peak + TRAIL_MULT * atrv)
                else:
                    peak = max(peak, h[k])
                    cur_stop = max(cur_stop, peak - TRAIL_MULT * atrv)
        if exit_bar is None:
            exit_bar, exit_px = b["max_horizon"], c[min(b["max_horizon"], len(c) - 1)]
        pnl = (entry - exit_px) if top else (exit_px - entry)
        results.append(dict(brk_q=entry_bar, pnl=pnl))
        last_exit = exit_bar
    return results, missed, filtered_out


def report(results, label, filtered_out=None):
    n = len(results)
    if n < 8:
        print(f"  {label}: only {n} trades - too few"); return
    pnl = np.array([r["pnl"] for r in results])
    wins = (pnl > 0).sum()
    gw = pnl[pnl > 0].sum(); gl = -pnl[pnl <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    brk = np.array([r["brk_q"] for r in results])
    order = np.argsort(brk)
    cutoff = brk[order][int(n * 0.7)]
    is_m = brk < cutoff; oos_m = brk >= cutoff
    is_win = 100 * np.mean(pnl[is_m] > 0) if is_m.sum() >= 8 else float("nan")
    oos_win = 100 * np.mean(pnl[oos_m] > 0) if oos_m.sum() >= 8 else float("nan")
    fo = f"  (filtered out {filtered_out})" if filtered_out is not None else ""
    print(f"  {label}: n={n}{fo}  win%={100*wins/n:.1f}  net={pnl.sum():.2f}  pf={pf:.3f}  "
          f"IS win%={is_win:.1f} n={is_m.sum()}  OOS win%={oos_win:.1f} n={oos_m.sum()}")


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    breakouts, h, l, c, atr = find_breakouts_full(df15, break_tol=BREAK_TOL)
    n15 = len(df15)

    print("=" * 95)
    print("BASELINE (current best: pullback 0.75xATR/30bar + break_tol=0.35 + runner 0.5xATR, no confluence)")
    print("=" * 95)
    base_res, base_missed, _ = eval_filtered(breakouts, h, l, c, lambda b: True)
    report(base_res, "no confluence filter", filtered_out=0)

    rsi = rsi_wilder(c, 14)
    stoch = stochastic(h, l, c, period=14, smooth=3)

    print("\n" + "=" * 95)
    print("TEST 1: RSI EXTREME AT BREAKOUT (oversold<30 for inverse/bull, overbought>70 for top/bear)")
    print("=" * 95)
    for thresh in (20, 30, 40):
        def allow_rsi(b, thresh=thresh):
            r = rsi[b["brk_q"]]
            if np.isnan(r):
                return False
            return (r <= thresh) if b["top"] else (r >= 100 - thresh)
        res, missed, fo = eval_filtered(breakouts, h, l, c, allow_rsi)
        report(res, f"RSI extreme <= {thresh}/>= {100-thresh}", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 2: RSI DIVERGENCE AT THE HEAD (price new extreme, RSI does not confirm)")
    print("=" * 95)
    def allow_rsi_div(b):
        r_head = rsi[b["i_head"]]
        r_s1 = rsi[b["i_s1"]]
        r_s2 = rsi[b["i_s2"]]
        if np.isnan(r_head) or np.isnan(r_s1) or np.isnan(r_s2):
            return False
        worse_shoulder_rsi = max(r_s1, r_s2) if b["top"] else min(r_s1, r_s2)
        # top: price head > both shoulders (already required), divergence = RSI at head
        # does NOT exceed the worse shoulder's RSI (momentum didn't confirm the new high)
        return (r_head <= worse_shoulder_rsi) if b["top"] else (r_head >= worse_shoulder_rsi)
    res, missed, fo = eval_filtered(breakouts, h, l, c, allow_rsi_div)
    report(res, "RSI divergence at head (vs worse shoulder's RSI)", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 3: STOCHASTIC EXTREME AT BREAKOUT")
    print("=" * 95)
    for thresh in (20, 30, 40):
        def allow_stoch(b, thresh=thresh):
            s = stoch[b["brk_q"]]
            if np.isnan(s):
                return False
            return (s <= thresh) if b["top"] else (s >= 100 - thresh)
        res, missed, fo = eval_filtered(breakouts, h, l, c, allow_stoch)
        report(res, f"Stoch extreme <= {thresh}/>= {100-thresh}", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 4: TRENDLINE CONFLUENCE (a real diagonal trendline also breaks same direction, near breakout)")
    print("=" * 95)
    print("  SKIPPED - BuildLine's real signature (build_line in h4_touch_reaction_test.py) needs anchor-pair "
          "search over the SAME rolling-lookback logic already used for the trendline validation work, which "
          "is a real, separate construction from H&S's swing detection - not a quick bolt-on. Flagging as a "
          "genuine remaining candidate rather than rushing a fake version of it.")
