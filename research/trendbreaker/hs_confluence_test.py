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


def classify_effort(o, h, l, c, vol, atr, vavg,
                     range_atr=1.3, vol_ratio=1.5, close_pct=0.25):
    """Port of effort_vs_result_test.py's classify_effort - VSA "Effort vs
    Result" (Tom Williams, Master the Markets), real-validated on H4 this
    session (42.1% reversal vs 37.4% baseline, p=0.0053, stable IS/OOS) -
    never tested against H&S specifically until now."""
    rng = h - l
    close_pos = np.where(rng > 0, (c - l) / np.maximum(rng, 1e-9), 0.5)
    wide = rng >= range_atr * atr
    hi_vol = vol >= vol_ratio * np.maximum(vavg, 1e-9)
    up = wide & hi_vol & (close_pos >= 1 - close_pct)
    dn = wide & hi_vol & (close_pos <= close_pct)
    return up, dn


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "effort":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    o15 = df15["open"].values
    vol15 = df15["tick_volume"].values.astype(float)
    breakouts, h, l, c, atr = find_breakouts_full(df15, break_tol=BREAK_TOL)
    n15 = len(df15)

    vavg = np.convolve(vol15, np.ones(50) / 50, mode="same")
    up_eff, dn_eff = classify_effort(o15, h, l, c, vol15, atr, vavg)
    RESULT_BARS, RESULT_MIN_ATR = 3, 0.30

    def failed_effort_at(i, want_up):
        """True if bar i is an EFFORT bar in `want_up` direction that then
        failed to follow through within RESULT_BARS - the VSA "effort with
        no result" signature, checked at bar i."""
        if i + RESULT_BARS >= n15:
            return False
        is_eff = up_eff[i] if want_up else dn_eff[i]
        if not is_eff:
            return False
        move = (c[i + RESULT_BARS] - c[i]) * (1 if want_up else -1)
        success = move >= RESULT_MIN_ATR * atr[i]
        return not success

    print("=" * 95)
    print("BASELINE (current best construction, no effort-vs-result filter)")
    print("=" * 95)
    base_res, _, _ = eval_filtered(breakouts, h, l, c, lambda b: True)
    report(base_res, "no confluence filter")

    print("\n" + "=" * 95)
    print("TEST 5: VSA EFFORT-VS-RESULT FAILURE AT THE RIGHT SHOULDER")
    print("(shoulder shows wide-range/high-volume/closes-on-the-extreme in the PRIOR trend's")
    print(" direction, but price does NOT follow through - a real exhaustion signature)")
    print("=" * 95)
    def allow_effort(b):
        # top pattern: right shoulder is a high in an uptrend - want a failed EFFORT_UP there.
        # inverse: right shoulder is a low in a downtrend - want a failed EFFORT_DOWN there.
        i_s2 = b["i_s2"]
        want_up = b["top"]
        # check the shoulder bar itself and the couple of bars right around its formation
        return any(failed_effort_at(k, want_up) for k in range(max(0, i_s2 - 2), i_s2 + 1))
    res, missed, fo = eval_filtered(breakouts, h, l, c, allow_effort)
    report(res, "failed-effort at right shoulder", filtered_out=fo)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "savin":
    # Savin, Weller & Zvingelis (2003), "The Predictive Power of Head-and-
    # Shoulders Price Patterns in the U.S. Stock Market" - real academic
    # study, independently confirms H&S predictive power (7-9%/year real
    # risk-adjusted excess returns, S&P500/Russell2000, robust to Fama-
    # French+momentum controls). Their restrictions (R6)-(R9), calibrated
    # against real Bulkowski examples, are genuinely different filters from
    # anything tested on this project's H&S construction so far:
    #   R6/R7: shoulder height (from neckline) as a fraction of head height
    #          must be between 0.25 and 0.70 - not too small, not too close
    #          to the head's own height.
    #   R8:    head height (from neckline) must be >= 3% of the head's own
    #          price - filters out insignificant/noise-scale patterns.
    #   R9:    horizontal (time) symmetry - no single gap between
    #          consecutive extrema may exceed 1.2x the average gap.
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    breakouts, h, l, c, atr = find_breakouts_full(df15, break_tol=BREAK_TOL)

    print("=" * 95)
    print("BASELINE (current best construction, no Savin/Weller/Zvingelis filter)")
    print("=" * 95)
    base_res, _, _ = eval_filtered(breakouts, h, l, c, lambda b: True)
    report(base_res, "no confluence filter")

    def avg_shoulder_frac(b):
        """Mean of the two shoulders' height from the (sloped) neckline at
        their own time, as a fraction of the head's own height - this
        project's neckline convention substituted for R6/R7's flat E2/E4
        average, since our neckline is deliberately sloped (through the two
        troughs) rather than flat."""
        nl_s1 = b["neckline_at"](b["i_s1"])
        nl_s2 = b["neckline_at"](b["i_s2"])
        sh1 = abs(b["p_s1"] - nl_s1)
        sh2 = abs(b["p_s2"] - nl_s2)
        return 0.5 * (sh1 + sh2) / b["head_height"] if b["head_height"] > 0 else None

    print("\n" + "=" * 95)
    print("TEST 6: R6/R7 - SHOULDER HEIGHT AS FRACTION OF HEAD HEIGHT, 0.25-0.70")
    print("=" * 95)
    def allow_r67(b):
        frac = avg_shoulder_frac(b)
        return frac is not None and 0.25 <= frac <= 0.70
    res, missed, fo = eval_filtered(breakouts, h, l, c, allow_r67)
    report(res, "R6/R7 shoulder-fraction 0.25-0.70", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 7: R8 - HEAD HEIGHT >= 3% OF THE HEAD'S OWN PRICE")
    print("=" * 95)
    for min_pct in (0.01, 0.02, 0.03):
        def allow_r8(b, min_pct=min_pct):
            return b["head_height"] / b["p_head"] >= min_pct if b["p_head"] > 0 else False
        res, missed, fo = eval_filtered(breakouts, h, l, c, allow_r8)
        tag = "  <-- Savin et al.'s own R8" if min_pct == 0.03 else ""
        report(res, f"R8 head height >= {100*min_pct:.0f}% of price{tag}", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 8: R9 - HORIZONTAL (TIME) SYMMETRY, NO GAP > 1.2x THE AVERAGE GAP")
    print("=" * 95)
    def allow_r9(b):
        gaps = [b["i_t1"] - b["i_s1"], b["i_head"] - b["i_t1"],
                b["i_t2"] - b["i_head"], b["i_s2"] - b["i_t2"]]
        avg_gap = sum(gaps) / 4.0
        if avg_gap <= 0:
            return False
        return max(abs(g - avg_gap) for g in gaps) <= 1.2 * avg_gap
    res, missed, fo = eval_filtered(breakouts, h, l, c, allow_r9)
    report(res, "R9 time symmetry <= 1.2x avg gap", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 9: ALL THREE SAVIN/WELLER/ZVINGELIS FILTERS COMBINED (R6/R7 + R8[3%] + R9)")
    print("=" * 95)
    def allow_all_savin(b):
        frac = avg_shoulder_frac(b)
        if frac is None or not (0.25 <= frac <= 0.70):
            return False
        if b["p_head"] <= 0 or b["head_height"] / b["p_head"] < 0.03:
            return False
        gaps = [b["i_t1"] - b["i_s1"], b["i_head"] - b["i_t1"],
                b["i_t2"] - b["i_head"], b["i_s2"] - b["i_t2"]]
        avg_gap = sum(gaps) / 4.0
        if avg_gap <= 0 or max(abs(g - avg_gap) for g in gaps) > 1.2 * avg_gap:
            return False
        return True
    res, missed, fo = eval_filtered(breakouts, h, l, c, allow_all_savin)
    report(res, "all three combined", filtered_out=fo)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "trendline":
    # Trendline confluence, built PROPERLY this time - reuses the real,
    # already-validated trendline construction from h4_touch_reaction_
    # test.py (find_swings/bos_ok/build_line, full anchor-pair search,
    # LOOKBACK_BARS=300) rather than a quick bolt-on. Run on H4, not M15:
    # earlier research (m15_touch_reaction_walkforward.py) already found
    # M15 barely produces any VALID (3+ touch) lines at all - not enough
    # "memory" in a 300-bar window for M15's noise level - so testing
    # confluence there would just re-confirm a known dead end, not answer
    # anything new. H4 is where the underlying trendline construction is
    # itself real-validated (55.6% bounce vs 22.2% shadow control,
    # p=0.012-0.014, stable IS/OOS).
    #
    # Question: does an H&S breakout that ALSO coincides with a validated
    # trendline break (same direction, within a real time window) perform
    # better than one that doesn't?
    import h4_touch_reaction_test as LT

    h4 = E.load_h4()
    o4 = h4["open"].values; h4h = h4["high"].values; l4 = h4["low"].values; c4 = h4["close"].values
    atr4 = LT.sma_atr(h4h, l4, o4, LT.ATR_PERIOD)
    n4 = len(h4)
    print(f"H4 data: {h4['time'].min()} -> {h4['time'].max()}, n={n4} bars")

    zIdx, zType, zPx = LT.find_swings(o4, h4h, l4, c4, atr4, body=False)
    lines = []
    for dir_, want in ((1, 1), (-1, -1)):
        anchors = [zIdx[m] for m in range(len(zIdx))
                   if zType[m] == want and LT.bos_ok(m, zIdx, zType, zPx, o4, h4h, l4, c4, n4, False)]
        for ai in range(len(anchors)):
            for bi in range(ai + 1, len(anchors)):
                a, b = anchors[ai], anchors[bi]
                if b - a < LT.PIVOT_STRENGTH or b - a > LT.LOOKBACK_BARS:
                    continue
                L = LT.build_line(o4, h4h, l4, c4, atr4, n4, a, b, dir_, False)
                if L is not None:
                    lines.append(L)
    valid_lines = [L for L in lines if L["touches"] >= LT.TOUCHES_TO_VALIDATE]
    print(f"candidate lines: {len(lines)}, VALID (3+ touches): {len(valid_lines)}")

    breakouts, hh, ll, cc, atr = find_breakouts_full(h4, break_tol=0.10)   # H4's own base default, not the M15-tuned 0.35
    print(f"H&S confirmed breakouts (H4, base construction): {len(breakouts)}\n")

    CONFLUENCE_WINDOW = 15   # bars either side of the H&S breakout - a real, disclosed choice, not swept

    def line_broke_near(brk_q, want_dir):
        """True if a VALID line of `want_dir` (matches H&S breakout direction:
        top/bearish needs a broken DOWN line, inverse/bullish needs a broken
        UP line) has a confirmed break (BREAK_CONFIRM_CLOSES closes beyond,
        same definition as h4_touch_reaction_test.py's own line-death check)
        landing within CONFLUENCE_WINDOW bars of brk_q."""
        for L in valid_lines:
            if L["dir"] != want_dir:
                continue
            if L["ib"] >= brk_q + CONFLUENCE_WINDOW:
                continue   # line didn't even exist yet
            run_ = 0
            for q in range(max(L["ib"] + 1, brk_q - CONFLUENCE_WINDOW), min(brk_q + CONFLUENCE_WINDOW, n4 - 1) + 1):
                lv = L["p1"] + L["slope"] * (q - L["ia"])
                penC = (cc[q] - lv) if L["dir"] < 0 else (lv - cc[q])
                if penC > LT.BREAK_TOL_ATR * atr4[q]:
                    run_ += 1
                    if run_ >= LT.BREAK_CONFIRM_CLOSES and abs(q - brk_q) <= CONFLUENCE_WINDOW:
                        return True
                else:
                    run_ = 0
        return False

    def allow_confluent(b):
        # H&S top (bearish, needs price breaking DOWN through the neckline) confluent
        # with a validated line breaking DOWN too (dir_=-1, an "up" trendline broken downward)
        want_dir = -1 if b["top"] else 1
        return line_broke_near(b["brk_q"], want_dir)

    confluent = [b for b in breakouts if allow_confluent(b)]
    non_confluent = [b for b in breakouts if not allow_confluent(b)]
    print(f"confluent with a validated trendline break: {len(confluent)}  |  not: {len(non_confluent)}\n")

    def report_h4(bset, label):
        if len(bset) < 8:
            print(f"  {label}: only {len(bset)} - too few"); return
        res = eval_market_entry_h4(bset, hh, ll, cc)
        report(res, label)

    def eval_market_entry_h4(bset, h, l, c, stop_buffer=1.0):
        results, last_exit = [], -1
        for b in sorted(bset, key=lambda x: x["brk_q"]):
            top, brk_q, entry, target = b["top"], b["brk_q"], b["brk_price"], b["target"]
            if brk_q < last_exit:
                continue
            stop = (b["shoulder_ext"] + stop_buffer * b["atr_at_brk"]) if top else \
                   (b["shoulder_ext"] - stop_buffer * b["atr_at_brk"])
            if (top and stop <= entry) or ((not top) and stop >= entry):
                continue
            outcome, exit_bar = None, None
            for k in range(brk_q + 1, b["max_horizon"] + 1):
                hit_stop = (h[k] >= stop) if top else (l[k] <= stop)
                hit_target = (l[k] <= target) if top else (h[k] >= target)
                if hit_stop:
                    outcome, exit_bar = "STOP", k; break
                if hit_target:
                    outcome, exit_bar = "TARGET", k; break
            if outcome is None:
                outcome, exit_bar = "HORIZON", b["max_horizon"]
            if outcome == "TARGET":
                pnl = abs(target - entry)
            elif outcome == "STOP":
                pnl = -abs(entry - stop)
            else:
                final_px = c[min(exit_bar, len(c) - 1)]
                pnl = (entry - final_px) if top else (final_px - entry)
            results.append(dict(brk_q=brk_q, pnl=pnl))
            last_exit = exit_bar
        return results

    print("=" * 95)
    report_h4(breakouts, "ALL H&S breakouts (H4, no trendline filter)")
    report_h4(confluent, "CONFLUENT with a validated trendline break")
    report_h4(non_confluent, "NOT confluent")
