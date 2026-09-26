"""
Follow-up to first_touch_test.py: that test showed relaxing the "wait for
3+ touches" validation rule doesn't help, because H4/M15 only ever produce
2-4 CANDIDATE lines in the first place (touches>=2, before validation is
even considered) - matching h4_touch_reaction_test.py's own "candidate
lines: 2" baseline. The real bottleneck isn't the touch-count gate at all;
it's PIERCE_TOL_ATR=0.35 (the .mq5 file's own InpPierceTolATR default) -
between the two BOS-anchored pivots, price is allowed to poke through the
fitted line by at most 0.35x ATR at ANY single bar, or the whole candidate
is thrown out. That is an extremely strict "did price travel in a nearly
perfectly straight diagonal for weeks/months" requirement.

Quick sensitivity check (see chat) confirmed this directly: candidate line
count on H4 over 25 years goes 2 -> 7 -> 26 -> 43 -> 127 -> 295 as
PIERCE_TOL_ATR is relaxed from 0.35 to 0.5/0.75/1.0/1.5/2.0. This script
answers the next real question: once you have ENOUGH candidates to test
(loosen PIERCE_TOL_ATR rather than the touch count), does first-touch
reaction quality survive, or was the strict pierce tolerance actually
doing useful work (i.e. only very clean lines are worth trading)?

Also runs on M15 (resampled from real M5) to fold in the "does a lower
timeframe give enough setups for shorter trades" question on the same
loosened construction - the axis that actually controls frequency here is
PIERCE_TOL_ATR, not the bar timeframe, so this checks whether that holds
on M15 too.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
import h4_touch_reaction_test as M
from h4_touch_reaction_test import find_swings, bos_ok, build_line, sma_atr, ATR_PERIOD, PIVOT_STRENGTH
from first_touch_test import first_touch_events, summarize

np.random.seed(42)
PIERCE_LEVELS = (0.35, 0.5, 0.75, 1.0, 1.5, 2.0)


def build_lines_at_pierce(o, h, l, c, atr, n, pierce, lookback):
    orig = M.PIERCE_TOL_ATR
    M.PIERCE_TOL_ATR = pierce
    try:
        zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
        lines = []
        for dir_, want in ((1, 1), (-1, -1)):
            anchors = [zIdx[m] for m in range(len(zIdx))
                       if zType[m] == want and bos_ok(m, zIdx, zType, zPx, o, h, l, c, n, False)]
            for ai in range(len(anchors)):
                for bi in range(ai + 1, len(anchors)):
                    a, b = anchors[ai], anchors[bi]
                    if b - a < PIVOT_STRENGTH or b - a > lookback:
                        continue
                    L = build_line(o, h, l, c, atr, n, a, b, dir_, False)
                    if L is not None:
                        lines.append(L)
        return lines
    finally:
        M.PIERCE_TOL_ATR = orig


def run_timeframe(name, df):
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    n = len(c)
    atr = sma_atr(h, l, o, ATR_PERIOD)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    print("\n" + "=" * 90)
    print(f"{name}: n={n} bars, {years:.2f} yrs")
    print("=" * 90)

    for pierce in PIERCE_LEVELS:
        lines = build_lines_at_pierce(o, h, l, c, atr, n, pierce, M.LOOKBACK_BARS)
        events = first_touch_events(o, h, l, c, atr, n, lines)
        real = [e["outcome"] for e in events]
        shadow = [e["shadow"] for e in events]
        n_ev = len(real)
        if n_ev == 0:
            print(f"  PIERCE_TOL_ATR={pierce}: lines={len(lines)} ({len(lines)/years:.1f}/yr)  events=0")
            continue
        real = np.array(real); shadow = np.array(shadow)
        rb = (real == 1).sum(); sb = (shadow == 1).sum()
        line = (f"  PIERCE_TOL_ATR={pierce}: lines={len(lines)} ({len(lines)/years:.1f}/yr)  "
                f"events={n_ev} ({n_ev/years:.1f}/yr)  "
                f"real bounce={100*rb/n_ev:.1f}%  shadow bounce={100*sb/n_ev:.1f}%")
        if n_ev >= 15:
            from scipy import stats
            table = [[rb, n_ev - rb], [sb, n_ev - sb]]
            odds, p = stats.fisher_exact(table, alternative="greater")
            line += f"  Fisher p={p:.4f}"
        print(line)

        if pierce in (1.0, 1.5) and n_ev >= 15:
            half_q = np.median([e["q"] for e in events])
            is_ev = [e for e in events if e["q"] < half_q]
            oos_ev = [e for e in events if e["q"] >= half_q]
            for tag, split in (("IS", is_ev), ("OOS", oos_ev)):
                if len(split) >= 5:
                    r = np.array([e["outcome"] for e in split])
                    s = np.array([e["shadow"] for e in split])
                    print(f"      {tag} (n={len(split)}): real bounce={100*(r==1).mean():.1f}%  "
                          f"shadow bounce={100*(s==1).mean():.1f}%")


if __name__ == "__main__":
    h4 = E.load_h4()
    run_timeframe("H4", h4)

    m5 = E.load_m5()
    m15 = E.resample_m15_from_m5(m5)
    run_timeframe("M15 (resampled from real M5)", m15)

    print("\n" + "=" * 90)
    print("VERDICT: printed above per PIERCE_TOL_ATR level - see chat for interpretation.")
    print("=" * 90)
