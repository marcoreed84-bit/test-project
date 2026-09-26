"""
User's third pattern-deck upload (2026-09-26): "Three Valleys and a River"
(bullish; mirror is "Three Hills and a River", bearish). My reading of the
card's own text + diagram (disclosed explicitly since this is a small image
of someone else's proprietary-sounding pattern, not a textbook definition
I can cross-check the way the Wolfe Wave rules were web-verified):

  - A a swing HIGH, then three successive HIGHER LOWS (valleys 1/2/3,
    L1<L2<L3 - a "rounding out", waning-decline bottoming shape), with a
    high between each pair of valleys (H1 between valley1/2, H2 between
    valley2/3).
  - NECKLINE = the line through H1 and H2 (mirrors H&S's own neckline
    treatment already used elsewhere in this repo - same BREAK_TOL_ATR/
    BREAK_CONFIRM_CLOSES breakout-confirm convention).
  - TRADE 1: long on the confirmed neckline breakout (point "B" on the
    card). HEIGHT = neckline value at breakout minus valley 1's own low
    (the deepest valley - same "head height" idea as H&S). Target =
    breakout price + FRAC*HEIGHT for FRAC in {0.62, 0.70, 0.78} (the
    card's own "62% to 78% of the AB range" - tested across that range,
    not just one cherry-picked point). Stop = valley 3's own low (the most
    recent invalidation level), buffered by ATR.
  - TRADE 2 ("point C", after trade 1's target zone is reached): a SECOND
    long at that same price level, target = entry + HEIGHT (a full
    "AB=CD" equal-leg extension - the card's own explicit "AB=CD"/"100%"
    annotation), stop = the same trade-1 target/entry level, buffered by
    ATR (this is the card's own "if price closes below the 'C' level,
    close the trade" rule).

Same rigor as every pattern tested since the Wolfe Wave lesson: %PF (not
raw points) AND the random-timing baseline BEFORE calling anything
promising, on both H4 and M15 GOLD.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES, PIVOT_STRENGTH
from hs_next_round_test import walk, pnl_of, report

np.random.seed(42)
MAX_HORIZON_CAP = 400
STOP_BUFFER = 1.0
CONFIRM_LAG = PIVOT_STRENGTH + 1   # same lookahead fix learned from Wolfe Wave


def find_candidates(zIdx, zType, zPx):
    """6-point windows: high-low-high-low-high-low (bullish: A,L1,H1,L2,H2,L3)."""
    out = []
    for m in range(len(zIdx) - 5):
        seq = zType[m:m + 6]
        if seq != [1, -1, 1, -1, 1, -1]:
            continue
        iA, iL1, iH1, iL2, iH2, iL3 = zIdx[m:m + 6]
        pA, pL1, pH1, pL2, pH2, pL3 = zPx[m:m + 6]
        if not (pL1 < pL2 < pL3):   # three successively higher lows
            continue
        neck_slope = (pH2 - pH1) / (iH2 - iH1) if iH2 != iH1 else 0.0

        def neck_at(q, i0=iH1, s=neck_slope, p0=pH1):
            return p0 + s * (q - i0)

        height = neck_at(iL3) - pL1
        if height <= 0:
            continue
        out.append(dict(iL1=iL1, iL3=iL3, pL1=pL1, pL3=pL3, neck_at=neck_at, height=height))
    return out


def build_trade1(cands, h, l, c, atr, n, frac):
    out = []
    for cd in cands:
        iL3 = cd["iL3"]
        scan_start = iL3 + CONFIRM_LAG
        horizon_end = min(n - 1, iL3 + MAX_HORIZON_CAP)
        brk_q, run_ = -1, 0
        for q in range(scan_start, horizon_end):
            nl = cd["neck_at"](q)
            beyond = c[q] - nl
            if beyond > BREAK_TOL_ATR * atr[q]:
                run_ += 1
                if run_ >= BREAK_CONFIRM_CLOSES:
                    brk_q = q; break
            else:
                run_ = 0
        if brk_q < 0:
            continue
        entry = c[brk_q]
        target = entry + frac * cd["height"]
        stop = cd["pL3"] - STOP_BUFFER * atr[brk_q]
        if stop >= entry or target <= entry:
            continue
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
        out.append(dict(top=False, brk_q=brk_q, brk_price=entry, target=target, stop=stop,
                         max_horizon=max_horizon, height=cd["height"]))
    return out


def eval_book_twostage(trade1s, h, l, c, n):
    """Sequences trade 1s; once one reaches its target (a genuine TARGET
    outcome, not stop/horizon), opens trade 2 at that same price with a
    full-height (AB=CD) target. Stop for trade 2 (the card's own "close
    below the C level" rule) uses the SAME price-unit stop distance trade 1
    itself used, anchored below the new entry instead of below valley 3."""
    trade1s = sorted(trade1s, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in trade1s:
        if b["brk_q"] < last_exit:
            continue
        outcome1, exit1 = walk(h, l, False, b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        pnl1 = pnl_of(outcome1, b["brk_price"], b["stop"], b["target"], c, exit1, False)
        results.append(dict(brk_q=b["brk_q"], stage=1, pnl=pnl1, pnl_pct=pnl1 / b["brk_price"],
                             stop_pct=(b["brk_price"] - b["stop"]) / b["brk_price"],
                             target_pct=(b["target"] - b["brk_price"]) / b["brk_price"]))
        last_exit = exit1
        if outcome1 == "TARGET":
            entry2 = b["target"]
            target2 = entry2 + b["height"]
            stop2 = entry2 - (b["brk_price"] - b["stop"])
            max_horizon2 = min(n - 1, exit1 + MAX_HORIZON_CAP)
            if stop2 < entry2 < target2 and exit1 < n - 1:
                outcome2, exit2 = walk(h, l, False, exit1, max_horizon2, stop2, target2)
                pnl2 = pnl_of(outcome2, entry2, stop2, target2, c, exit2, False)
                results.append(dict(brk_q=exit1, stage=2, pnl=pnl2, pnl_pct=pnl2 / entry2,
                                     stop_pct=(entry2 - stop2) / entry2,
                                     target_pct=(target2 - entry2) / entry2))
                last_exit = exit2
    return results


def pct_pf(results):
    arr = np.array([r["pnl_pct"] for r in results])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_timing_baseline(real_results, h, l, c, n, rng, n_runs=1000):
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


def run(name, df):
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    cands = find_candidates(zIdx, zType, zPx)
    print(f"\n{'='*90}\n{name}: n={n} bars, {years:.2f} yrs, {len(cands)} raw 3-valley shapes ({len(cands)/years:.1f}/yr)\n{'='*90}")

    for frac in (0.62, 0.70, 0.78):
        trade1s = build_trade1(cands, h, l, c, atr, n, frac)
        res = eval_book_twostage(trade1s, h, l, c, n)
        stage1 = [r for r in res if r["stage"] == 1]
        stage2 = [r for r in res if r["stage"] == 2]
        if len(res) >= 8:
            report(res, f"  frac={frac}: ALL stages combined")
            real_pf = pct_pf(res)
            print(f"    %PF={real_pf:.3f}  (stage1 n={len(stage1)}, stage2 n={len(stage2)})")
            rng = np.random.default_rng(42)
            rand_pfs = random_timing_baseline(res, h, l, c, n, rng, n_runs=1000)
            rand_pfs = rand_pfs[~np.isnan(rand_pfs)]
            pctile = 100 * (rand_pfs < real_pf).mean()
            print(f"    random-timing median={np.median(rand_pfs):.3f} p95={np.percentile(rand_pfs,95):.3f}  "
                  f"real sits at {pctile:.1f}th percentile")
        else:
            print(f"  frac={frac}: only {len(res)} trade-legs - too few")

    return cands


if __name__ == "__main__":
    h4 = E.load_h4()
    run("H4", h4)

    m5 = E.load_m5()
    m15 = E.resample_m15_from_m5(m5)
    run("M15 (resampled from real M5)", m15)
