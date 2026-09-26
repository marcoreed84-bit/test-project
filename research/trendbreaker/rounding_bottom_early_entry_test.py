"""
User's redirect (2026-09-26, with a "Cup" pattern reference image): don't
wait for the full rim breakout - enter during the cup's own ASCENDING
second half, closer to the bottom, instead of waiting for price to climb
all the way back up to the rim and confirm a breakout there.

WHY THIS IS STRUCTURALLY DIFFERENT, NOT JUST "EARLIER": find_rounding()'s
own CENTER_TOL=0.25 requirement already means the window's bottom sits
somewhere in the middle 50% of the window, so by the time a 60-bar window
is even CONFIRMED as a good quadratic fit (at the window's own last bar,
`end`), price has typically already climbed for 25-75% of the window's
length since the true bottom - i.e. the shape is only ever recognized
partway up the right side of the cup, never at the bottom itself. The
CURRENT (v1.03) construction then makes things worse by waiting ADDITIONAL
bars after `end` for price to climb the REST of the way back up to the rim
and confirm a breakout there - throwing away most of the cup's own
right-side move as unrealized profit before ever entering.

THIS TEST: enter at the window's own completion bar (`end`) instead - i.e.
right when the shape is first confirmed, still partway up from the bottom,
never waiting for a rim breakout at all. Two real, favourable side effects
of entering this early, not just "more of the move captured":
  1. The stop can go back to being anchored at the cup's own bottom
     (extreme_px) instead of the rim - Backtest 1's real problem (rim-vs-
     bottom stop distance being too close to the whole reward) was
     specifically a symptom of entering too LATE (at the rim); entering
     near the bottom instead makes a bottom-anchored stop tight and
     sensible again.
  2. No breakout-confirmation delay to survive - fewer bars of exposure to
     a failed continuation before the trade is even open.
The real risk, tested honestly rather than assumed: without a rim-breakout
confirmation, MANY shape-passing windows might not actually continue
rising (a "cup" that quietly rolls back over) - this construction has no
mechanism to filter those out except the entry stop itself.

Same rigor discipline as everything else this session: %PF (not raw
points), AND the random-timing baseline BEFORE reporting this as
promising, given RoundingBottom's existing rim-breakout construction just
failed the multiple-testing correction.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, ATR_PERIOD
from rounding_cup_handle_test import find_rounding
from hs_next_round_test import walk, pnl_of, report

np.random.seed(42)
N_RANDOM = 1500
WINDOW = 60
MAX_HORIZON_CAP = 300


def build_early_entry_trades(cands, h, l, c, atr, n, stop_buffer, target_mode, confirm_bars=0):
    """confirm_bars=0: enter immediately at the window's own last close.
    confirm_bars>0: wait that many bars past `end` and require price to
    have made a higher close each time (a light momentum confirmation,
    the middle ground between immediate entry and a full rim breakout)."""
    out = []
    for cd in cands:
        end, rim, extreme_px = cd["end"], cd["rim"], cd["extreme_px"]
        height = abs(rim - extreme_px)
        if height <= 0:
            continue
        entry_q = end
        if confirm_bars > 0:
            ok = True
            for k in range(1, confirm_bars + 1):
                if end + k >= n or c[end + k] <= c[end + k - 1]:
                    ok = False
                    break
            if not ok:
                continue
            entry_q = end + confirm_bars
        if entry_q >= n:
            continue
        entry_price = c[entry_q]
        atr_e = atr[entry_q]
        stop = extreme_px - stop_buffer * atr_e
        if stop >= entry_price:
            continue
        target = (rim + height) if target_mode == "rim_plus_height" else (entry_price + height)
        if target <= entry_price:
            continue
        max_horizon = min(n - 1, entry_q + MAX_HORIZON_CAP)
        out.append(dict(top=False, brk_q=entry_q, brk_price=entry_price, target=target,
                         stop=stop, max_horizon=max_horizon))
    return out


def eval_book_pct(trades, h, l, c):
    trades = sorted(trades, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in trades:
        if b["brk_q"] < last_exit:
            continue
        outcome, exit_bar = walk(h, l, False, b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        pnl = pnl_of(outcome, b["brk_price"], b["stop"], b["target"], c, exit_bar, False)
        pnl_pct = pnl / b["brk_price"]
        results.append(dict(brk_q=b["brk_q"], outcome=outcome, pnl=pnl, pnl_pct=pnl_pct,
                             stop_pct=(b["brk_price"] - b["stop"]) / b["brk_price"],
                             target_pct=(b["target"] - b["brk_price"]) / b["brk_price"]))
        last_exit = exit_bar
    return results


def pct_pf(results):
    arr = np.array([r["pnl_pct"] for r in results])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_timing_baseline(real_results, h, l, c, n, rng, n_runs=N_RANDOM):
    pfs = []
    lo, hi = MAX_HORIZON_CAP, n - MAX_HORIZON_CAP - 1
    for _ in range(n_runs):
        pcts = []
        for r in real_results:
            q0 = int(rng.integers(lo, hi))
            entry = c[q0]
            stop = entry * (1 - r["stop_pct"])
            target = entry * (1 + r["target_pct"])
            max_horizon = min(n - 1, q0 + MAX_HORIZON_CAP)
            outcome, exit_bar = walk(h, l, False, q0, max_horizon, stop, target)
            pnl = pnl_of(outcome, entry, stop, target, c, exit_bar, False)
            pcts.append(pnl / entry)
        arr = np.array(pcts)
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        pfs.append(gw / gl if gl > 0 else np.nan)
    return np.array(pfs)


if __name__ == "__main__":
    h4 = E.load_h4()
    o = h4["open"].values; h = h4["high"].values; l = h4["low"].values; c = h4["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    print(f"H4 data: n={n} bars, {h4['time'].min()} -> {h4['time'].max()}\n")

    cands = find_rounding(c, atr, n, WINDOW, top=False)
    print(f"{len(cands)} shape-confirmed candidates (unchanged from v1.03's own detection)\n")

    print("=" * 95)
    print("IMMEDIATE ENTRY at window completion (confirm_bars=0) - stop x ATR sweep, both target modes")
    print("=" * 95)
    for target_mode in ("rim_plus_height", "entry_plus_height"):
        print(f"  -- target = {target_mode} --")
        for sb in (0.5, 1.0, 1.5, 2.0):
            trades = build_early_entry_trades(cands, h, l, c, atr, n, sb, target_mode, confirm_bars=0)
            res = eval_book_pct(trades, h, l, c)
            if len(res) >= 8:
                report(res, f"    stop={sb}xATR")
                print(f"      %PF={pct_pf(res):.3f}")
            else:
                print(f"    stop={sb}xATR: only {len(res)} trades - too few")

    print("\n" + "=" * 95)
    print("LIGHT CONFIRMATION (a few bars of continued rise after window completion) - stop=1.0xATR fixed")
    print("=" * 95)
    for cb in (0, 1, 2, 3, 5):
        trades = build_early_entry_trades(cands, h, l, c, atr, n, 1.0, "rim_plus_height", confirm_bars=cb)
        res = eval_book_pct(trades, h, l, c)
        if len(res) >= 8:
            report(res, f"  confirm_bars={cb}")
            print(f"    %PF={pct_pf(res):.3f}")
        else:
            print(f"  confirm_bars={cb}: only {len(res)} trades - too few")

    # pick the best-looking config from above for the rigor checks (disclosed,
    # not cherry-picked past this point - whatever wins above is what gets
    # stress-tested, same as every other pattern this session)
    print("\n" + "=" * 95)
    print("RIGOR CHECK on stop=1.0xATR / target=rim_plus_height / confirm_bars=0 (the direct 'no waiting' version)")
    print("=" * 95)
    trades = build_early_entry_trades(cands, h, l, c, atr, n, 1.0, "rim_plus_height", confirm_bars=0)
    real = eval_book_pct(trades, h, l, c)
    real_pct_pf = pct_pf(real)
    report(real, f"early-entry RoundingBottom (n={len(real)})")
    print(f"  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(42)
    print(f"\nRunning {N_RANDOM} random-timing baselines...")
    rand_pfs = random_timing_baseline(real, h, l, c, n, rng)
    rand_pfs = rand_pfs[~np.isnan(rand_pfs)]
    pctile = 100 * (rand_pfs < real_pct_pf).mean()
    p_val = (rand_pfs >= real_pct_pf).mean()
    print(f"  random-timing %PF distribution: median={np.median(rand_pfs):.3f}  "
          f"p95={np.percentile(rand_pfs,95):.3f}")
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.3f})")
