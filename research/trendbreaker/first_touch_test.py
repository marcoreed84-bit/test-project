"""
"Option 2" from the drawdown/trendline discussion (2026-09-26): the prior
h4_touch_reaction_test.py showed that requiring a line to prove itself with
3+ touches before trading it is too strict to ever fire - only 1 valid line
on H4 in 25 years, only 2 on M15 in ~3.5 years. The user's own question was
whether price reacts to a fresh, BOS-anchored diagonal line on its very
FIRST touch after being built, without waiting for it to already earn
"valid" status. That moves the tradable signal earlier and should fire far
more often, IF the reaction is real.

Reuses the exact same construction as h4_touch_reaction_test.py
(find_swings/bos_ok/build_line - unmodified, same constants) so this is an
apples-to-apples extension, not a new pattern definition. The only change:
instead of only using lines with touches>=TOUCHES_TO_VALIDATE and then
walking EVERY touch over the line's life (mixing early and late touches),
this test takes ALL built candidate lines (touches>=2, i.e. just the two
anchors, no interior touch required yet) and looks at ONLY the FIRST touch
after the line is built (q > ib). Stratified by how many interior touches
the line already had baked in at construction time (2 = truly fresh, never
touched since existing; 3+ = already met the old validation bar) to check
for a dose-response - if 3+-touch lines react better than 2-touch lines,
that's evidence the "wait for validation" rule is actually buying you
something, not just filtering away tradable setups.

Also runs on M15 (resampled 1:1 from real M5 data - GOLD has no native M15
export, see engine.resample_m15_from_m5) to directly answer the follow-up
question: does moving to a lower timeframe give the trendline construction
enough candidate frequency for shorter trades? Reports raw candidate/event
counts per year on both timeframes so frequency and reaction quality are
both on the table together, not just reaction quality in isolation.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import (
    find_swings, bos_ok, build_line, sma_atr,
    PIVOT_STRENGTH, ATR_PERIOD, TOUCH_TOL_ATR, BREAK_TOL_ATR,
    BREAK_CONFIRM_CLOSES, REACT_BARS, REACT_ATR, LOOKBACK_BARS, TOUCHES_TO_VALIDATE,
    ext_px,
)

np.random.seed(42)


def build_all_lines(o, h, l, c, atr, n):
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    lines = []
    for dir_, want in ((1, 1), (-1, -1)):
        anchors = [zIdx[m] for m in range(len(zIdx))
                   if zType[m] == want and bos_ok(m, zIdx, zType, zPx, o, h, l, c, n, False)]
        for ai in range(len(anchors)):
            for bi in range(ai + 1, len(anchors)):
                a, b = anchors[ai], anchors[bi]
                if b - a < PIVOT_STRENGTH or b - a > LOOKBACK_BARS:
                    continue
                L = build_line(o, h, l, c, atr, n, a, b, dir_, False)
                if L is not None:
                    lines.append(L)
    return lines, zIdx


def forward_outcome(o, h, l, c, atr, n, dir_, p1, slope, ia, q):
    """Same bounce(+1)/break(-1)/inconclusive(0) test as h4_touch_reaction_test.py's Q1."""
    outcome = 0
    closes_beyond = 0
    for k in range(q + 1, min(q + 1 + REACT_BARS, n)):
        lvk = p1 + slope * (k - ia)
        penCk = (c[k] - lvk) if dir_ < 0 else (lvk - c[k])
        if penCk > BREAK_TOL_ATR * atr[k]:
            closes_beyond += 1
            if closes_beyond >= BREAK_CONFIRM_CLOSES:
                outcome = -1
                break
        else:
            closes_beyond = 0
        away = (lvk - c[k]) if dir_ < 0 else (c[k] - lvk)
        if away > REACT_ATR * atr[k]:
            outcome = 1
            break
    return outcome


def shadow_outcome(o, h, l, c, atr, n, dir_, q):
    """Same fixed shadow control as Q1: a FLAT line drawn through price at q."""
    lv_s0 = c[q]
    outcome_s = 0
    closes_beyond_s = 0
    for k in range(q + 1, min(q + 1 + REACT_BARS, n)):
        penCk_s = (c[k] - lv_s0) if dir_ < 0 else (lv_s0 - c[k])
        if penCk_s > BREAK_TOL_ATR * atr[k]:
            closes_beyond_s += 1
            if closes_beyond_s >= BREAK_CONFIRM_CLOSES:
                outcome_s = -1
                break
        else:
            closes_beyond_s = 0
        away_s = (lv_s0 - c[k]) if dir_ < 0 else (c[k] - lv_s0)
        if away_s > REACT_ATR * atr[k]:
            outcome_s = 1
            break
    return outcome_s


def first_touch_events(o, h, l, c, atr, n, lines):
    """For each candidate line, find only its FIRST post-construction touch
    and evaluate it. Returns list of dicts: outcome, shadow, touches_at_build."""
    events = []
    gap = max(2, PIVOT_STRENGTH)
    for L in lines:
        dir_, ia, ib, p1, slope, body = L["dir"], L["ia"], L["ib"], L["p1"], L["slope"], L["body"]
        last_touch = ib
        for q in range(ib + 1, min(n - REACT_BARS, ib + LOOKBACK_BARS)):
            a = atr[q]
            lv = p1 + slope * (q - ia)
            pe_ = ext_px(o[q], h[q], l[q], c[q], dir_, body)
            pen = (pe_ - lv) if dir_ < 0 else (lv - pe_)
            if pen >= -TOUCH_TOL_ATR * a and pen <= TOUCH_TOL_ATR * a and q - last_touch >= gap:
                out = forward_outcome(o, h, l, c, atr, n, dir_, p1, slope, ia, q)
                if out != 0:
                    sh = shadow_outcome(o, h, l, c, atr, n, dir_, q)
                    events.append(dict(q=q, outcome=out, shadow=sh, touches_at_build=L["touches"]))
                break   # FIRST touch only - stop walking this line
    return events


def summarize(outcomes, label):
    n_ = len(outcomes)
    if n_ == 0:
        print(f"    {label}: 0 definitive outcomes")
        return
    outcomes = np.array(outcomes)
    bounce = (outcomes == 1).sum()
    brk = (outcomes == -1).sum()
    print(f"    {label}: n={n_} bounce={bounce} ({100*bounce/n_:.1f}%) break={brk} ({100*brk/n_:.1f}%)")


def run_timeframe(name, df):
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    n = len(c)
    atr = sma_atr(h, l, o, ATR_PERIOD)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    print("\n" + "=" * 78)
    print(f"{name}: n={n} bars, {df['time'].min()} -> {df['time'].max()} ({years:.2f} yrs)")
    print("=" * 78)

    lines, zIdx = build_all_lines(o, h, l, c, atr, n)
    fresh = [L for L in lines if L["touches"] == 2]
    prevalidated = [L for L in lines if L["touches"] >= TOUCHES_TO_VALIDATE]
    print(f"  swings={len(zIdx)}  candidate lines={len(lines)}  "
          f"(fresh/2-touch={len(fresh)}, already-3+={len(prevalidated)})")
    print(f"  candidate lines/year = {len(lines)/years:.1f}")

    events = first_touch_events(o, h, l, c, atr, n, lines)
    print(f"  first-touch definitive events: {len(events)}  ({len(events)/years:.1f}/year)")

    all_real = [e["outcome"] for e in events]
    all_shadow = [e["shadow"] for e in events]
    summarize(all_real, "ALL first touches (any candidate line, 2+ touches)")
    summarize(all_shadow, "  shadow control")

    fresh_ev = [e["outcome"] for e in events if e["touches_at_build"] == 2]
    fresh_sh = [e["shadow"] for e in events if e["touches_at_build"] == 2]
    pre_ev = [e["outcome"] for e in events if e["touches_at_build"] >= TOUCHES_TO_VALIDATE]
    pre_sh = [e["shadow"] for e in events if e["touches_at_build"] >= TOUCHES_TO_VALIDATE]
    print("  -- dose-response: fresh (2-touch) vs already-validated (3+) at their OWN first touch --")
    summarize(fresh_ev, "fresh (touches_at_build==2)")
    summarize(fresh_sh, "  shadow")
    summarize(pre_ev, "already 3+ at build")
    summarize(pre_sh, "  shadow")

    if len(all_real) > 8 and len(all_shadow) > 8:
        from scipy import stats
        real_b = (np.array(all_real) == 1).astype(int)
        sh_b = (np.array(all_shadow) == 1).astype(int)
        table = [[real_b.sum(), len(real_b) - real_b.sum()],
                 [sh_b.sum(), len(sh_b) - sh_b.sum()]]
        odds, p = stats.fisher_exact(table, alternative="greater")
        print(f"  Fisher exact (real bounce% > shadow bounce%): odds={odds:.2f} p={p:.4f}")

    return dict(name=name, years=years, lines=lines, events=events)


if __name__ == "__main__":
    h4 = E.load_h4()
    res_h4 = run_timeframe("H4", h4)

    m5 = E.load_m5()
    m15 = E.resample_m15_from_m5(m5)
    res_m15 = run_timeframe("M15 (resampled from real M5)", m15)

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    print("Frequency (does a lower timeframe fix the 'almost never fires' problem?):")
    print(f"  H4:  {len(res_h4['lines'])/res_h4['years']:.1f} candidate lines/yr, "
          f"{len(res_h4['events'])/res_h4['years']:.1f} first-touch events/yr")
    print(f"  M15: {len(res_m15['lines'])/res_m15['years']:.1f} candidate lines/yr, "
          f"{len(res_m15['events'])/res_m15['years']:.1f} first-touch events/yr")
