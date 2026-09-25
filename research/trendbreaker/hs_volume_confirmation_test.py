"""
Tests the volume-confirmation rules from the Dr Wealth "Price Action
Trading Guide" (2026-09-25) as a FILTER on the already-tested H&S
measured-move target (head_shoulders_target_test.py: 69.1% H4 / 74.6% D1
hit rate, stable IS/OOS). Question: does having the "textbook" volume
signature actually discriminate between H&S patterns that hit their
target and ones that don't - not just "is it true on average", but does
it carry real information.

TEXTBOOK SIGNATURES, taken directly from the guide (top and bottom are
explicitly DIFFERENT, not mirror images - the guide says so):
  TOP: right shoulder volume < left shoulder volume AND < head volume
       ("Volume is lesser in the right shoulder formation compared to
       the left shoulder and the head formation.")
  BOTTOM: head volume > left shoulder volume ("a recovery move follows
       that is marked by somewhat more volume" for the head vs the
       left shoulder's own rise)
  BOTH: breakout should happen on above-average volume ("Volume
       confirmation on price breakout... you want the volume to be
       higher than normal as the breakout happened").

Reuses the exact same pattern detection, breakout confirmation and
target-hit logic as head_shoulders_target_test.py - not a new
construction, the same confirmed breakouts, with volume signature
computed and cross-tabulated against the real hit/miss outcome already
established there.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_CONFIRM_CLOSES
from head_shoulders_target_test import find_hs_patterns, SHOULDER_TOL_ATR, BREAK_TOL_ATR, MAX_HORIZON_MULT, MAX_HORIZON_CAP

np.random.seed(42)

VOL_AVG_BARS = 50   # recent-average window for the breakout-volume check, matching VolumeRatioAt's own convention size class


def peak_volume(vol, atr_i, idx, window=2):
    """Volume right around a swing point (a few bars either side, since the
    real extreme tick/bar and the recorded swing bar can differ by 1-2 bars
    in resampled/H4-derived data) - mean, not just the single bar, to avoid
    one noisy bar deciding the whole signature."""
    lo = max(0, idx - window)
    hi = min(len(vol), idx + window + 1)
    return vol[lo:hi].mean()


def run(df, label):
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    vol = df["tick_volume"].values.astype(float)
    atr = sma_atr(h, l, o, ATR_PERIOD)
    print(f"\n{label}: {df['time'].min()} -> {df['time'].max()}, n={n} bars")

    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)

    results = []   # dict per confirmed breakout: hit, top, sig_ok (textbook volume match), brk_vol_ok
    for top in (True, False):
        pats = find_hs_patterns(zIdx, zType, zPx, top)
        shoulder_ok = [p for p in pats
                       if abs(p["p_s1"] - p["p_s2"]) <= SHOULDER_TOL_ATR * atr[p["i_head"]]]

        for p in shoulder_ok:
            ia, ib = p["i_t1"], p["i_t2"]
            neck_slope = (p["p_t2"] - p["p_t1"]) / (ib - ia) if ib != ia else 0.0

            def neckline_at(q):
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
            hit = False
            for k in range(brk_q + 1, min(brk_q + 1 + MAX_HORIZON_CAP, n)):
                reached = (l[k] <= target) if top else (h[k] >= target)
                if reached:
                    hit = True; break

            v_s1 = peak_volume(vol, atr, p["i_s1"])
            v_head = peak_volume(vol, atr, p["i_head"])
            v_s2 = peak_volume(vol, atr, p["i_s2"])
            if top:
                sig_ok = (v_s2 < v_s1) and (v_s2 < v_head)
            else:
                sig_ok = (v_head > v_s1)

            vavg_lo = max(0, brk_q - VOL_AVG_BARS)
            vavg = vol[vavg_lo:brk_q].mean() if brk_q > vavg_lo else np.nan
            brk_vol = vol[max(0, brk_q - 1):brk_q + 2].mean()
            brk_vol_ok = (not np.isnan(vavg)) and vavg > 0 and (brk_vol > vavg)

            results.append(dict(hit=hit, top=top, sig_ok=sig_ok, brk_vol_ok=brk_vol_ok, brk_q=brk_q))

    n_ = len(results)
    print(f"  {n_} confirmed H&S/inverse breakouts (same set as head_shoulders_target_test.py)")
    if n_ == 0:
        return

    def rate(subset):
        if len(subset) == 0:
            return None, 0
        return 100 * sum(r["hit"] for r in subset) / len(subset), len(subset)

    overall_rate, _ = rate(results)
    print(f"  overall full-target hit rate (baseline): {overall_rate:.1f}% (n={n_})")

    print("\n  --- shoulder/head volume signature (textbook shape) ---")
    for flag, label in ((True, "signature MATCHES textbook"), (False, "signature does NOT match")):
        sub = [r for r in results if r["sig_ok"] == flag]
        rt, cnt = rate(sub)
        if rt is not None:
            print(f"    {label}: n={cnt}  hit rate={rt:.1f}%")

    print("\n  --- breakout volume (above vs below its own {}-bar average) ---".format(VOL_AVG_BARS))
    for flag, label in ((True, "breakout volume ABOVE average"), (False, "breakout volume at/below average")):
        sub = [r for r in results if r["brk_vol_ok"] == flag]
        rt, cnt = rate(sub)
        if rt is not None:
            print(f"    {label}: n={cnt}  hit rate={rt:.1f}%")

    print("\n  --- both textbook signals present ---")
    for flag, label in ((True, "BOTH shape signature AND breakout volume confirm"), (False, "at least one does NOT confirm")):
        sub = [r for r in results if (r["sig_ok"] and r["brk_vol_ok"]) == flag]
        rt, cnt = rate(sub)
        if rt is not None:
            print(f"    {label}: n={cnt}  hit rate={rt:.1f}%")

    # significance check on the main shape-signature split
    sig_yes = [r["hit"] for r in results if r["sig_ok"]]
    sig_no = [r["hit"] for r in results if not r["sig_ok"]]
    if len(sig_yes) > 5 and len(sig_no) > 5:
        from scipy import stats
        table = [[sum(sig_yes), len(sig_yes) - sum(sig_yes)],
                 [sum(sig_no), len(sig_no) - sum(sig_no)]]
        odds, p = stats.fisher_exact(table, alternative="two-sided")
        print(f"\n  Fisher exact (shape signature vs hit rate): odds={odds:.2f} p={p:.4f}")

    # significance + walk-forward check on the breakout-volume split (the one that looked real)
    bv_yes = [r["hit"] for r in results if r["brk_vol_ok"]]
    bv_no = [r["hit"] for r in results if not r["brk_vol_ok"]]
    if len(bv_yes) > 5 and len(bv_no) > 5:
        from scipy import stats
        table = [[sum(bv_yes), len(bv_yes) - sum(bv_yes)],
                 [sum(bv_no), len(bv_no) - sum(bv_no)]]
        odds, p = stats.fisher_exact(table, alternative="greater")
        print(f"  Fisher exact (breakout volume ABOVE avg > hit rate): odds={odds:.2f} p={p:.4f}")

    order = sorted(range(n_), key=lambda i: results[i]["brk_q"])
    cutoff = int(n_ * 0.7)
    is_r = [results[i] for i in order[:cutoff]]
    oos_r = [results[i] for i in order[cutoff:]]
    print("\n  WALK-FORWARD on breakout-volume split (chronological 70/30 by breakout bar):")
    for half_r, half_label in ((is_r, "IN-SAMPLE"), (oos_r, "OUT-OF-SAMPLE")):
        yes = [r["hit"] for r in half_r if r["brk_vol_ok"]]
        no = [r["hit"] for r in half_r if not r["brk_vol_ok"]]
        ry = 100 * sum(yes) / len(yes) if yes else float("nan")
        rn = 100 * sum(no) / len(no) if no else float("nan")
        print(f"    {half_label}: above-avg n={len(yes)} hit={ry:.1f}%   at/below-avg n={len(no)} hit={rn:.1f}%")


if __name__ == "__main__":
    h4 = E.load_h4()
    run(h4, "H4 (real GOLD# export)")

    d1 = E.derive_d1_from_h4(h4)
    d1["time"] = pd.to_datetime(d1["date"])
    # derive_d1_from_h4 doesn't carry tick_volume - sum real H4 tick_volume per day to get a real D1 volume series
    dvol = h4.copy()
    dvol["date"] = dvol["time"].dt.date
    dvol_daily = dvol.groupby("date")["tick_volume"].sum().reset_index()
    d1 = d1.merge(dvol_daily, on="date", how="left")
    run(d1, "D1 (reconstructed from real GOLD# H4, real daily-summed volume)")
