"""
Bump and Run Reversal (BARR) - Thomas Bulkowski's real, documented pattern
(Encyclopedia of Chart Patterns), from the user's uploaded "42 Chart
Patterns" poster. Genuinely different construction from everything else
tested this session: not swing-pivot-based, it's TWO ROLLING LINEAR
REGRESSIONS compared against each other.

CONSTRUCTION (bearish BARR - a topping reversal after an uptrend):
  1. LEAD-IN phase: a LEAD_BARS-bar window with a real, sustained trend -
     fit a straight line (linear regression) through the closes.
  2. BUMP phase: the following BUMP_BARS-bar window, immediately after the
     lead-in - fit its own regression line. Bulkowski's own real rule:
     the bump's slope must be at least BUMP_MULT (1.5x, his own published
     threshold) steeper than the lead-in slope, same direction - a
     genuine, real acceleration beyond the established trend, not just
     "still going up."
  3. CONFIRMATION: after the bump's own peak, price must close back BELOW
     the lead-in trendline (extended forward from the lead-in phase) by
     BREAK_TOL_ATR for BREAK_CONFIRM_CLOSES closes - same convention used
     everywhere else in this repo.
  4. Entry short at the confirm bar. Stop above the bump's own peak
     (buffered by ATR). Target = measured move: height = bump peak minus
     the lead-in trendline's own value at the bump's start, target =
     entry - height (Bulkowski's own claim is the "run" phase tends to at
     least retrace the "bump").
Bullish mirror (BARR bottom): lead-in downtrend, bump a steep decline,
confirm a close back above the lead-in trendline, target = entry + height.

Same rigor discipline as everything since the Wolfe Wave lesson: %PF (not
raw points), and the random-timing baseline run immediately, on both H4
and M15 GOLD.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, ATR_PERIOD, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES
from hs_next_round_test import walk, pnl_of, report

np.random.seed(42)
LEAD_BARS = 50
BUMP_BARS = 25
BUMP_MULT = 1.5
STRIDE = 5
MAX_HORIZON_CAP = 400
STOP_BUFFER = 1.0


def slope_of(c, i0, i1):
    """Linear regression slope of closes over [i0, i1) - price per bar."""
    seg = c[i0:i1]
    x = np.arange(len(seg), dtype=float)
    if len(seg) < 3:
        return 0.0, 0.0, 0.0
    a, b = np.polyfit(x, seg, 1)
    return a, b, seg[0]   # slope, intercept, value at start


def find_candidates(c, atr, n, top):
    out = []
    for bump_end in range(LEAD_BARS + BUMP_BARS, n - 1, STRIDE):
        bump_start = bump_end - BUMP_BARS
        lead_start = bump_start - LEAD_BARS
        if lead_start < 0:
            continue
        lead_slope, lead_b, lead_v0 = slope_of(c, lead_start, bump_start)
        bump_slope, bump_b, bump_v0 = slope_of(c, bump_start, bump_end)

        if top:
            lead_ok = lead_slope > 0
            bump_steep = bump_slope > 0 and bump_slope >= BUMP_MULT * max(lead_slope, 1e-9)
        else:
            lead_ok = lead_slope < 0
            bump_steep = bump_slope < 0 and bump_slope <= BUMP_MULT * min(lead_slope, -1e-9)
        if not (lead_ok and bump_steep):
            continue

        def lead_at(q, i0=lead_start, s=lead_slope, v0=lead_v0):
            return v0 + s * (q - i0)

        seg = c[bump_start:bump_end]
        extreme_i = bump_start + (int(np.argmax(seg)) if top else int(np.argmin(seg)))
        extreme_px = c[extreme_i]
        out.append(dict(bump_end=bump_end, extreme_i=extreme_i, extreme_px=extreme_px, lead_at=lead_at))
    # de-dup heavily overlapping candidates (same underlying bump found at
    # several nearby strides) - keep the first (earliest) in any cluster
    out.sort(key=lambda d: d["bump_end"])
    accepted, last_end = [], -10**9
    for cd in out:
        if cd["extreme_i"] <= last_end:
            continue
        accepted.append(cd)
        last_end = cd["bump_end"]
    return accepted


def build_trades(cands, h, l, c, atr, n, top):
    out = []
    for cd in cands:
        extreme_i, extreme_px, lead_at = cd["extreme_i"], cd["extreme_px"], cd["lead_at"]
        # LOOKAHEAD FIX (same class as the Wolfe Wave CONFIRM_LAG bug): the
        # bump's own extreme can fall anywhere inside [bump_start, bump_end),
        # but the bump isn't actually CONFIRMED (slope >= BUMP_MULT x lead-in
        # slope, computed over the WHOLE window) until bar bump_end-1 has
        # closed. Scanning for breakout starting right after extreme_i alone
        # could start before that - scan must not begin before bump_end.
        scan_start = max(extreme_i + 1, cd["bump_end"])
        horizon_end = min(n - 1, extreme_i + MAX_HORIZON_CAP)
        brk_q, run_ = -1, 0
        for q in range(scan_start, horizon_end):
            lv = lead_at(q)
            beyond = (lv - c[q]) if top else (c[q] - lv)
            if beyond > BREAK_TOL_ATR * atr[q]:
                run_ += 1
                if run_ >= BREAK_CONFIRM_CLOSES:
                    brk_q = q; break
            else:
                run_ = 0
        if brk_q < 0:
            continue
        entry = c[brk_q]
        height = abs(extreme_px - lead_at(cd["bump_end"] - BUMP_BARS))
        if height <= 0:
            continue
        target = (entry - height) if top else (entry + height)
        stop = extreme_px + STOP_BUFFER * atr[brk_q] if top else extreme_px - STOP_BUFFER * atr[brk_q]
        if (top and stop <= entry) or ((not top) and stop >= entry):
            continue
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
        out.append(dict(top=top, brk_q=brk_q, brk_price=entry, target=target, stop=stop, max_horizon=max_horizon))
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
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_timing_baseline(real_results, h, l, c, n, rng, n_runs=1500):
    pfs = []
    lo, hi = MAX_HORIZON_CAP, n - MAX_HORIZON_CAP - 1
    for _ in range(n_runs):
        pcts = []
        for r in real_results:
            q0 = int(rng.integers(lo, hi))
            entry = c[q0]
            top = r["top"]
            stop = entry * (1 + r["stop_pct"]) if top else entry * (1 - r["stop_pct"])
            target = entry * (1 - r["target_pct"]) if top else entry * (1 + r["target_pct"])
            max_horizon = min(n - 1, q0 + MAX_HORIZON_CAP)
            outcome, exit_bar = walk(h, l, top, q0, max_horizon, stop, target)
            pnl = pnl_of(outcome, entry, stop, target, c, exit_bar, top)
            pcts.append(pnl / entry)
        arr = np.array(pcts)
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        pfs.append(gw / gl if gl > 0 else np.nan)
    return np.array(pfs)


def run(name, df):
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    print(f"\n{'='*92}\n{name}: n={n} bars, {years:.2f} yrs\n{'='*92}")

    all_res = []
    for top, label in ((True, "bearish BARR (topping)"), (False, "bullish BARR (bottoming)")):
        cands = find_candidates(c, atr, n, top)
        trades = build_trades(cands, h, l, c, atr, n, top)
        res = eval_book_pct(trades, h, l, c)
        print(f"  {label}: {len(cands)} raw candidates -> {len(res)} trades ({len(res)/years:.1f}/yr)")
        if len(res) >= 8:
            report(res, f"    {label}")
            print(f"      %PF={pct_pf(res):.3f}")
        all_res.extend(res)

    if len(all_res) >= 8:
        real_pf = pct_pf(all_res)
        print(f"\n  COMBINED (both directions): n={len(all_res)}  %PF={real_pf:.3f}")
        rng = np.random.default_rng(42)
        rand_pfs = random_timing_baseline(all_res, h, l, c, n, rng)
        rand_pfs = rand_pfs[~np.isnan(rand_pfs)]
        pctile = 100 * (rand_pfs < real_pf).mean()
        p_val = (rand_pfs >= real_pf).mean()
        print(f"  random-timing median={np.median(rand_pfs):.3f}  p95={np.percentile(rand_pfs,95):.3f}")
        print(f"  REAL sits at {pctile:.1f}th percentile (one-sided p={p_val:.3f})")
    else:
        print(f"\n  only {len(all_res)} combined trades - too few for a random-timing check")


if __name__ == "__main__":
    h4 = E.load_h4()
    run("H4", h4)

    m5 = E.load_m5()
    m15 = E.resample_m15_from_m5(m5)
    run("M15 (resampled from real M5)", m15)
