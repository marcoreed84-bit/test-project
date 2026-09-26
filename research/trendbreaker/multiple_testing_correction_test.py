"""
Opus's web review (2026-09-26) flagged the most important gap in this
session's whole random-timing-baseline discipline: it's a sound SINGLE-
hypothesis test, but this session tried roughly a dozen pattern families,
each with several parameter/combo variants, before landing on the ones
that survived (H&S stacked combo, RoundingBottom, Rectangle). Picking the
best result out of many tries is itself a source of false positives - the
exact mechanism behind Aronson's finding that ~6,400 technical rules
collapsed to nothing once data-mining bias was corrected for. Proper
corrections exist (Deflated Sharpe Ratio, Harvey-Liu haircut Sharpes with
Holm/BHY adjustment, CSCV/probability-of-backtest-overfitting) but all
assume a single continuous "try many parameter combos on one system, pick
the best" pipeline - this repo instead has several DISTINCT pattern-
detection systems, each tuned separately across several files over many
messages, so a literal CSCV isn't a clean fit.

PRACTICAL PROXY, per Opus's own suggestion #1c: "rerun the whole combo-
selection step" in the null and keep the "best-of-N null" - i.e., instead
of comparing the real result against ONE random-timing draw, compare it
against the BEST of K random-timing draws, where K approximates how many
distinct variants were actually tried for that pattern before the shipped
default was chosen. If the real result still clearly beats "the best of K
random tries," that's real evidence it survives multiple-testing scrutiny,
not just single-hypothesis testing.

K ESTIMATES (counted from this session's own test files/history - a
disclosed, honest approximation, not a precise audit; sensitivity to K
reported alongside so the reader isn't relying on getting K exactly right):
  - H&S stacked combo: SHOULDER_TOL_ATR sweep (4) + BREAK_CONFIRM_CLOSES
    sweep (5) + BREAK_TOL_ATR sweep (4) + pullback retest tol/window
    combos (4) + runner trail_mult sweep (5) + the stacked combo itself
    (1) + its own nearby-settings robustness check (4) = 27, from
    hs_next_round_test.py alone. Several OTHER hs_*.py files this session
    (confluence, candlestick confirmation, MA/VWAP exits, volume
    confirmation, a dedicated stop-loss sweep) tried more variants on top
    of this before arriving at v1.08 - not exhaustively recounted here, so
    K=27 is a FLOOR, not a ceiling. Also reported at K=50/100 to show how
    fast significance erodes if the true count is higher.
  - RoundingBottom: window sweep x direction (3x2=6) + handle-required
    on/off (2) + stop-anchor K sweep (6) + height-fraction alternative
    tried and rejected (~5) = 19. Also reported at K=30/50.
  - Rectangle: stop-buffer sweep (5) - it needed much less searching to
    look good than the other two, which is itself informative. Also
    reported at K=10/20.

METHOD: build a big pool of independent single random-timing %PF draws
(reusing each pattern's own already-built random_timing_baseline()), then
bootstrap the "best of K" null by repeatedly sampling K values from that
pool (with replacement) and taking the max - cheap and statistically valid
under the simplifying assumption that each "thing tried" would have had
i.i.d.-like random-timing performance under the null (a reasonable proxy,
disclosed as a simplification rather than a rigorous CSCV).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES

POOL_SIZE = 4000
N_BOOTSTRAP = 5000


def best_of_k_test(pattern_name, real_pct_pf, pool, k_values):
    print(f"\n{'='*90}\n{pattern_name}: real %PF={real_pct_pf:.3f}, pool of {len(pool)} single random-timing draws\n{'='*90}")
    rng = np.random.default_rng(7)
    for k in k_values:
        best_of_k = pool[rng.integers(0, len(pool), size=(N_BOOTSTRAP, k))].max(axis=1)
        pctile = 100 * (best_of_k < real_pct_pf).mean()
        p_val = (best_of_k >= real_pct_pf).mean()
        verdict = "SURVIVES" if p_val < 0.05 else ("borderline" if p_val < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={k:>4}: best-of-K median={np.median(best_of_k):.3f}  p95={np.percentile(best_of_k,95):.3f}  "
              f"real sits at {pctile:5.1f}th pct  p={p_val:.3f}   [{verdict}]")


if __name__ == "__main__":
    # ---------------- H&S stacked combo ----------------
    from hs_stacked_random_baseline_test import (
        find_breakouts_full, eval_pullback_and_runner_pct, pct_pf as hs_pct_pf,
        random_timing_baseline as hs_rtb, STOP_BUFFER as HS_SB, RETEST_TOL, RETEST_WINDOW, TRAIL_MULT
    )
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    breakouts, h15, l15, c15, atr15 = find_breakouts_full(df15, break_tol=0.35)
    n15 = len(c15)
    hs_real, _ = eval_pullback_and_runner_pct(breakouts, h15, l15, c15, HS_SB, RETEST_TOL, RETEST_WINDOW, TRAIL_MULT)
    hs_real_pf = hs_pct_pf(hs_real)
    print(f"Building H&S random-timing pool (n_runs={POOL_SIZE})...")
    rng = np.random.default_rng(1)
    hs_pool = hs_rtb(hs_real, h15, l15, c15, n15, rng, n_runs=POOL_SIZE)
    hs_pool = hs_pool[~np.isnan(hs_pool)]
    best_of_k_test("H&S STACKED COMBO", hs_real_pf, hs_pool, [1, 27, 50, 100])

    # ---------------- RoundingBottom ----------------
    import rounding_bottom_random_baseline_test as RB
    from rounding_cup_handle_test import find_rounding
    h4 = E.load_h4()
    o4 = h4["open"].values; h4a = h4["high"].values; l4 = h4["low"].values; c4 = h4["close"].values
    atr4 = sma_atr(h4a, l4, o4, ATR_PERIOD)
    n4 = len(c4)
    rb_cands = find_rounding(c4, atr4, n4, RB.WINDOW, top=False)
    rb_trades = RB.build_real_trades(rb_cands, h4a, l4, c4, atr4, n4)
    rb_real = RB.eval_book(rb_trades, h4a, l4, c4)
    rb_real_pf = RB.pct_pf(rb_real)
    print(f"\nBuilding RoundingBottom random-timing pool (n_runs={POOL_SIZE})...")
    rng = np.random.default_rng(2)
    rb_pool = RB.random_timing_baseline(rb_real, h4a, l4, c4, atr4, n4, rng, n_runs=POOL_SIZE)
    rb_pool = rb_pool[~np.isnan(rb_pool)]
    best_of_k_test("ROUNDINGBOTTOM", rb_real_pf, rb_pool, [1, 19, 30, 50])

    # ---------------- Rectangle ----------------
    from rectangle_flag_test import find_rectangles
    import rectangle_random_baseline_test as RECT
    o15b = df15["open"].values
    atr15b = sma_atr(h15, l15, o15b, ATR_PERIOD)
    zIdx, zType, zPx = find_swings(o15b, h15, l15, c15, atr15b, body=False)
    rects = find_rectangles(zIdx, zType, zPx, atr15b)
    rect_trades = RECT.build_real_trades_pct(rects, h15, l15, c15, atr15b, n15, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES)
    rect_real = RECT.eval_book_pct(rect_trades, h15, l15, c15)
    rect_real_pf = RECT.pct_pf(rect_real)
    print(f"\nBuilding Rectangle random-timing pool (n_runs={POOL_SIZE})...")
    rng = np.random.default_rng(3)
    rect_pool = RECT.random_timing_baseline(rect_real, h15, l15, c15, n15, rng, n_runs=POOL_SIZE)
    rect_pool = rect_pool[~np.isnan(rect_pool)]
    best_of_k_test("RECTANGLE", rect_real_pf, rect_pool, [1, 5, 10, 20])

    print("\n" + "=" * 90)
    print("VERDICT: printed above per pattern/K - see chat for interpretation.")
    print("=" * 90)
