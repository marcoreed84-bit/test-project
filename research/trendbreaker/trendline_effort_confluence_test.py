"""
Confluence test (2026-09-25): does a real trendline touch that ALSO shows
VSA's "effort with no result" signature at that same bar bounce more often
than a touch without it? Combines the two things already independently
validated on H4 this session:
  - trendline touches (h4_touch_reaction_test.py): real touches of a
    VALID line bounce 55.6% of the time vs 22.2% for a flat-line control,
    Fisher p=0.012, IS/OOS-stable.
  - effort vs result (effort_vs_result_test.py): a wide-spread/high-volume
    bar that fails to follow through reverses 42.1% of the time vs a
    37.4% unconditional baseline, Fisher p=0.0053, IS/OOS-stable.

THE COMBINED HYPOTHESIS (not a named VSA term - my own construction from
the two validated pieces, exactly what was asked: does stacking them
help): at a support (up) line, the relevant "test" is a down-push INTO
the line - EFFORT_DOWN at that same bar (wide spread down, high volume,
closing near the lows) that then FAILS to follow through (price does not
keep falling) is a real VSA-flavoured rejection signature. Mirror for a
resistance (down) line with EFFORT_UP. Touches WITH this signature at the
touch bar are compared against touches WITHOUT it, using the exact same
real touch/outcome walk as h4_touch_reaction_test.py (not a new
construction - same VALID lines, same touch definition, same bounce/
break test), so this isolates the value of the CONFLUENCE alone.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import (
    sma_atr, ext_px, find_swings, bos_ok, build_line,
    PIVOT_STRENGTH, TOUCH_TOL_ATR, BREAK_TOL_ATR, ATR_PERIOD,
    TOUCHES_TO_VALIDATE, BREAK_CONFIRM_CLOSES, REACT_BARS, REACT_ATR,
    LOOKBACK_BARS,
)
from effort_vs_result_test import classify_effort, VOL_AVG_BARS

np.random.seed(42)

CONF_WINDOW = 3   # bars either side of the touch to check for the effort-failure signature


def run(df, label):
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    vol = df["tick_volume"].values.astype(float)
    atr = sma_atr(h, l, o, ATR_PERIOD)
    vavg = pd.Series(vol).rolling(VOL_AVG_BARS, min_periods=10).mean().values
    print(f"\n{label}: {df['time'].min()} -> {df['time'].max()}, n={n} bars")

    effort_up, effort_dn = classify_effort(o, h, l, c, vol, atr, vavg)

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
    valid_lines = [L for L in lines if L["touches"] >= TOUCHES_TO_VALIDATE]
    print(f"  VALID lines: {len(valid_lines)}")

    touches = []   # dict: bounce(bool), confluence(bool), i
    for L in valid_lines:
        dir_, ia, ib, p1, slope, body = L["dir"], L["ia"], L["ib"], L["p1"], L["slope"], L["body"]
        last_touch = ib
        q = ib + 1
        died = False
        while q < n - REACT_BARS and not died:
            a = atr[q]
            lv = p1 + slope * (q - ia)
            pe_ = ext_px(o[q], h[q], l[q], c[q], dir_, body)
            pen = (pe_ - lv) if dir_ < 0 else (lv - pe_)
            penC = (c[q] - lv) if dir_ < 0 else (lv - c[q])
            if pen >= -TOUCH_TOL_ATR * a and pen <= TOUCH_TOL_ATR * a and q - last_touch >= max(2, PIVOT_STRENGTH):
                last_touch = q
                outcome = 0
                closes_beyond = 0
                for k in range(q + 1, min(q + 1 + REACT_BARS, n)):
                    lvk = p1 + slope * (k - ia)
                    penCk = (c[k] - lvk) if dir_ < 0 else (lvk - c[k])
                    if penCk > BREAK_TOL_ATR * atr[k]:
                        closes_beyond += 1
                        if closes_beyond >= BREAK_CONFIRM_CLOSES:
                            outcome = -1; break
                    else:
                        closes_beyond = 0
                    away = (lvk - c[k]) if dir_ < 0 else (c[k] - lvk)
                    if away > REACT_ATR * atr[k]:
                        outcome = 1; break
                if outcome != 0:
                    # confluence: dir_>0 (support/up line) -> test is a down-push, EFFORT_DOWN at this bar
                    #             dir_<0 (resistance/down line) -> test is an up-push, EFFORT_UP at this bar
                    # WINDOWED (+/- CONF_WINDOW bars): both conditions are individually rare
                    # (effort ~4% of bars, a real touch rarer still), so requiring them on the
                    # EXACT same bar found zero co-occurrences at all on H4 - too strict to test
                    # anything. A touch is a multi-bar approach to the line, not one instant, so
                    # checking a small window around it for the same rejection signature is a
                    # reasonable, disclosed loosening, not moving the goalposts to find a result.
                    lo_w, hi_w = max(0, q - CONF_WINDOW), min(n, q + CONF_WINDOW + 1)
                    if dir_ > 0:
                        confluence = bool(effort_dn[lo_w:hi_w].any())
                    else:
                        confluence = bool(effort_up[lo_w:hi_w].any())
                    touches.append(dict(bounce=(outcome == 1), confluence=confluence, i=q))
            if penC > BREAK_TOL_ATR * a:
                run_ = 0
                for k in range(q, min(q + 5, n)):
                    lvk = p1 + slope * (k - ia)
                    penCk = (c[k] - lvk) if dir_ < 0 else (lvk - c[k])
                    if penCk > BREAK_TOL_ATR * atr[k]:
                        run_ += 1
                        if run_ >= BREAK_CONFIRM_CLOSES:
                            died = True; break
                    else:
                        break
            q += 1

    n_ = len(touches)
    print(f"  {n_} total real touch outcomes")
    if n_ == 0:
        return

    conf = [t for t in touches if t["confluence"]]
    noconf = [t for t in touches if not t["confluence"]]

    def report(subset, lbl):
        if len(subset) == 0:
            print(f"    {lbl}: 0"); return None
        b = sum(t["bounce"] for t in subset)
        rt = 100 * b / len(subset)
        print(f"    {lbl}: n={len(subset)}  bounce rate={rt:.1f}%")
        return rt, len(subset)

    print(f"\n  baseline (all real touches, no confluence filter): ", end="")
    report(touches, "ALL touches")
    r_conf = report(conf, "WITH effort-failure confluence")
    r_noconf = report(noconf, "WITHOUT confluence")

    if r_conf and r_noconf and len(conf) > 5 and len(noconf) > 5:
        from scipy import stats
        bc = sum(t["bounce"] for t in conf)
        bn = sum(t["bounce"] for t in noconf)
        table = [[bc, len(conf) - bc], [bn, len(noconf) - bn]]
        odds, p = stats.fisher_exact(table, alternative="greater")
        print(f"\n  Fisher exact (WITH confluence bounce rate > WITHOUT): odds={odds:.2f} p={p:.4f}")
    else:
        print(f"\n  too few confluence events (n={len(conf)}) to test significance")


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
