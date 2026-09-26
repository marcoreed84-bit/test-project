"""
Rectangle never got the random-timing/same-bracket baseline that Wolfe Wave,
RoundingBottom and H&S's stacked combo already went through - Opus's web
review flagged this gap directly. Same method: real trades' own %-sized
stop/target distances, replayed at random M15 bars with the same direction,
compared against the real result.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD
from hs_next_round_test import walk, pnl_of, report
from rectangle_flag_test import find_rectangles, STOP_BUFFER, MAX_HORIZON_CAP

np.random.seed(42)
N_RANDOM = 1500


def build_real_trades_pct(rects, h, l, c, atr, n, break_tol, break_confirm):
    out = []
    for p in rects:
        i_end = p["i_end"]
        horizon_end = min(n - 1, i_end + MAX_HORIZON_CAP)
        brk_q, brk_dir, run_up, run_dn = -1, None, 0, 0
        for q in range(i_end + 1, horizon_end):
            hv, lv = p["hi_at"](q), p["lo_at"](q)
            if c[q] - hv > break_tol * atr[q]:
                run_up += 1; run_dn = 0
            elif lv - c[q] > break_tol * atr[q]:
                run_dn += 1; run_up = 0
            else:
                run_up = run_dn = 0
            if run_up >= break_confirm:
                brk_q, brk_dir = q, "up"; break
            if run_dn >= break_confirm:
                brk_q, brk_dir = q, "down"; break
        if brk_q < 0:
            continue
        top = (brk_dir == "down")
        brk_price = c[brk_q]
        target = (brk_price - p["base_height"]) if top else (brk_price + p["base_height"])
        other_line = p["lo_at"](brk_q) if brk_dir == "up" else p["hi_at"](brk_q)
        atr_brk = atr[brk_q]
        stop = (other_line - STOP_BUFFER * atr_brk) if brk_dir == "up" else (other_line + STOP_BUFFER * atr_brk)
        if (top and stop <= brk_price) or ((not top) and stop >= brk_price):
            continue
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
        out.append(dict(top=top, brk_q=brk_q, brk_price=brk_price, target=target, stop=stop,
                         max_horizon=max_horizon))
    return out


def eval_book_pct(trades, h, l, c):
    trades = sorted(trades, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in trades:
        if b["brk_q"] < last_exit:
            continue
        outcome, exit_bar = walk(h, l, b["top"], b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        pnl = pnl_of(outcome, b["brk_price"], b["stop"], b["target"], c, exit_bar, b["top"])
        pnl_pct = pnl / b["brk_price"]
        results.append(dict(brk_q=b["brk_q"], top=b["top"], pnl=pnl, pnl_pct=pnl_pct,
                             stop_pct=abs(b["brk_price"] - b["stop"]) / b["brk_price"],
                             target_pct=abs(b["target"] - b["brk_price"]) / b["brk_price"]))
        last_exit = exit_bar
    return results


def pct_pf(results):
    arr = np.array([r["pnl_pct"] for r in results])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def replay_bracket_at(h, l, c, n, q0, top, stop_pct, target_pct, max_horizon_cap):
    entry = c[q0]
    stop = entry * (1 + stop_pct) if top else entry * (1 - stop_pct)
    target = entry * (1 - target_pct) if top else entry * (1 + target_pct)
    max_horizon = min(n - 1, q0 + max_horizon_cap)
    outcome, exit_bar = walk(h, l, top, q0, max_horizon, stop, target)
    pnl = pnl_of(outcome, entry, stop, target, c, exit_bar, top)
    return pnl / entry


def random_timing_baseline(real_results, h, l, c, n, rng, n_runs=N_RANDOM):
    pfs = []
    lo, hi = MAX_HORIZON_CAP, n - MAX_HORIZON_CAP - 1
    for _ in range(n_runs):
        pcts = []
        for r in real_results:
            q0 = int(rng.integers(lo, hi))
            pcts.append(replay_bracket_at(h, l, c, n, q0, r["top"], r["stop_pct"], r["target_pct"], MAX_HORIZON_CAP))
        arr = np.array(pcts)
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        pfs.append(gw / gl if gl > 0 else np.nan)
    return np.array(pfs)


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    o = df15["open"].values; h = df15["high"].values; l = df15["low"].values; c = df15["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    print(f"M15 data: n={n} bars\n")

    from h4_touch_reaction_test import BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES
    rects = find_rectangles(zIdx, zType, zPx, atr)
    trades = build_real_trades_pct(rects, h, l, c, atr, n, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES)
    real = eval_book_pct(trades, h, l, c)
    real_pct_pf = pct_pf(real)
    report(real, f"REAL rectangle ({len(rects)} candidates)")
    print(f"  %PF={real_pct_pf:.3f}  n={len(real)}")

    rng = np.random.default_rng(42)
    print(f"\nRunning {N_RANDOM} random-timing baselines...")
    rand_pfs = random_timing_baseline(real, h, l, c, n, rng)
    rand_pfs = rand_pfs[~np.isnan(rand_pfs)]
    pctile = 100 * (rand_pfs < real_pct_pf).mean()
    p_val = (rand_pfs >= real_pct_pf).mean()
    print(f"  random-timing %PF distribution: median={np.median(rand_pfs):.3f}  "
          f"p10={np.percentile(rand_pfs,10):.3f}  p90={np.percentile(rand_pfs,90):.3f}  "
          f"p95={np.percentile(rand_pfs,95):.3f}")
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.3f})")
