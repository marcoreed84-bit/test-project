"""
Tests VSA's "Effort versus Results" (Tom Williams, Master the Markets,
p.38-39), quoted precisely (2026-09-25): "Effort to go up is usually seen
as a wide spread up-bar, closing on the highs, with increased volume...
if there has been an effort to move, then there should be a result...
Frequently, you will see effort with no result... This is an indication
of weakness." The mirror case (effort to go down with no result) is
stated as a sign of strength (bullish).

FALSIFIABLE DEFINITION, built directly from the quoted text (nothing
invented beyond turning "wide spread", "increased volume", "closing on
the highs/lows" into concrete ATR/ratio thresholds):
  EFFORT_UP bar i:  range[i] >= EFFORT_RANGE_ATR * atr[i]  (wide spread)
                     AND vol[i] >= EFFORT_VOL_RATIO * avg_vol[i]  (increased volume)
                     AND close position in the top EFFORT_CLOSE_PCT of the
                     bar's own range  (closing on the highs)
  EFFORT_DOWN: the exact mirror (closing near the lows).

  RESULT, over the next RESULT_BARS bars: SUCCESS if price actually
  followed through (closed RESULT_MIN_ATR x ATR further in the effort's
  own direction); otherwise FAILURE ("effort with no result").

  THE CORE, SPECIFIC VSA CLAIM under test: an EFFORT bar that FAILS to
  produce a result should show ELEVATED reversal probability afterward
  (a "sign of weakness"/"sign of strength"), compared to (a) EFFORT bars
  that DID succeed, and (b) an unconditional baseline (does ANY bar show
  this much reversal over the same horizon, chosen at random) - so the
  test isolates whether "effort without result" specifically carries
  information, not just "prices revert sometimes".

Real GOLD H4 and D1 data, same ATR/volume conventions as every other
real-data screen in this repo, chronological 70/30 walk-forward split.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import sma_atr, ATR_PERIOD

np.random.seed(42)

EFFORT_RANGE_ATR   = 1.3    # "wide spread" - bar range vs its own ATR
EFFORT_VOL_RATIO   = 1.5    # "increased volume" - vs recent average
EFFORT_CLOSE_PCT   = 0.25   # "closing on the highs/lows" - top/bottom quartile of the bar's own range
VOL_AVG_BARS       = 50
RESULT_BARS        = 3      # how soon a real "result" should show up
RESULT_MIN_ATR     = 0.30   # how much follow-through counts as a real result
REACT_BARS         = 10     # horizon to test for the reversal ("sign of weakness/strength") after a FAILURE
REVERSAL_MIN_ATR   = 0.50   # how much of a move counts as "reversed"


def classify_effort(o, h, l, c, vol, atr, vavg):
    n = len(c)
    rng = h - l
    close_pos = np.where(rng > 0, (c - l) / np.maximum(rng, 1e-9), 0.5)
    wide = rng >= EFFORT_RANGE_ATR * atr
    hi_vol = vol >= EFFORT_VOL_RATIO * np.maximum(vavg, 1e-9)
    up = wide & hi_vol & (close_pos >= 1 - EFFORT_CLOSE_PCT)
    dn = wide & hi_vol & (close_pos <= EFFORT_CLOSE_PCT)
    return up, dn


def run(df, label):
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    vol = df["tick_volume"].values.astype(float)
    atr = sma_atr(h, l, o, ATR_PERIOD)
    vavg = pd.Series(vol).rolling(VOL_AVG_BARS, min_periods=10).mean().values
    print(f"\n{label}: {df['time'].min()} -> {df['time'].max()}, n={n} bars")

    up, dn = classify_effort(o, h, l, c, vol, atr, vavg)
    print(f"  EFFORT_UP bars: {up.sum()}   EFFORT_DOWN bars: {dn.sum()}")

    records = []   # dict: dir(+1/-1), i, success(bool), reversed(bool, only meaningful if not success), i_react_start
    for i in range(VOL_AVG_BARS, n - RESULT_BARS - REACT_BARS):
        for d, flag in ((1, up[i]), (-1, dn[i])):
            if not flag or np.isnan(atr[i]) or atr[i] <= 0:
                continue
            move = (c[i + RESULT_BARS] - c[i]) * d
            success = move >= RESULT_MIN_ATR * atr[i]
            reac_start = i + RESULT_BARS
            reac_end = min(n - 1, reac_start + REACT_BARS)
            net_after = (c[reac_end] - c[reac_start]) * d   # positive = continued own direction, negative = reversed
            reversed_ = net_after <= -REVERSAL_MIN_ATR * atr[i]
            records.append(dict(dir=d, i=i, success=success, reversed=reversed_))

    # UNCONDITIONAL baseline: same reversal test, applied to ALL bars regardless
    # of effort classification - "how often does a random bar see this much of
    # a move against a random direction over the same horizon anyway"
    base_reversed = []
    rand_dirs = np.random.choice([1, -1], size=n)
    for i in range(VOL_AVG_BARS, n - RESULT_BARS - REACT_BARS, 3):   # every 3rd bar - plenty of samples, avoids near-total overlap
        d = rand_dirs[i]
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue
        reac_start = i + RESULT_BARS
        reac_end = min(n - 1, reac_start + REACT_BARS)
        net_after = (c[reac_end] - c[reac_start]) * d
        base_reversed.append(net_after <= -REVERSAL_MIN_ATR * a)
    base_rate = 100 * np.mean(base_reversed) if base_reversed else float("nan")

    n_ = len(records)
    print(f"  {n_} total EFFORT bars (both directions) with a usable forward window")
    print(f"  UNCONDITIONAL baseline reversal rate (random direction, any bar, same horizon): "
          f"{base_rate:.1f}% (n={len(base_reversed)})")

    def report(subset, label):
        if len(subset) < 8:
            print(f"    {label}: only {len(subset)} - too few"); return None
        rev = sum(r["reversed"] for r in subset)
        rt = 100 * rev / len(subset)
        print(f"    {label}: n={len(subset)}  reversal rate={rt:.1f}%")
        return rt, len(subset)

    fail = [r for r in records if not r["success"]]
    succ = [r for r in records if r["success"]]
    print(f"\n  effort SUCCESS (real result followed): n={len(succ)}")
    print(f"  effort FAILURE (no result - VSA's 'sign of weakness/strength'): n={len(fail)}")
    r_fail = report(fail, "FAILURE reversal rate")
    r_succ = report(succ, "SUCCESS reversal rate (should be LOWER if the theory holds)")

    if r_fail and len(fail) > 8:
        from scipy import stats
        rev_ct = sum(r["reversed"] for r in fail)
        table = [[rev_ct, len(fail) - rev_ct],
                 [int(round(base_rate / 100 * len(base_reversed))), len(base_reversed) - int(round(base_rate / 100 * len(base_reversed)))]]
        odds, p = stats.fisher_exact(table, alternative="greater")
        print(f"\n  Fisher exact (FAILURE reversal rate > unconditional baseline): odds={odds:.2f} p={p:.4f}")

    # walk-forward
    order = sorted(range(len(fail)), key=lambda k: fail[k]["i"])
    cutoff = int(len(fail) * 0.7)
    print("\n  WALK-FORWARD on FAILURE reversal rate (chronological 70/30):")
    report([fail[k] for k in order[:cutoff]], "  IN-SAMPLE")
    report([fail[k] for k in order[cutoff:]], "  OUT-OF-SAMPLE")


if __name__ == "__main__":
    h4 = E.load_h4()
    run(h4, "H4 (real GOLD# export)")

    d1 = E.derive_d1_from_h4(h4)
    d1["time"] = pd.to_datetime(d1["date"])
    dvol = h4.copy()
    dvol["date"] = dvol["time"].dt.date
    dvol_daily = dvol.groupby("date")["tick_volume"].sum().reset_index()
    d1 = d1.merge(dvol_daily, on="date", how="left")
    run(d1, "D1 (reconstructed from real GOLD# H4, real daily-summed volume)")
