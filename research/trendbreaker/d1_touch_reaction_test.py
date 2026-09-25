"""
Same real construction (FindSwings/BOSOk/BuildLine, ported from the actual
.mq5 file, LOOKBACK_BARS=300 fidelity fix included) tested on D1 - the
opposite tradeoff from the M15 scale-up: far FEWER total bars, but each
one is coarser, so a straight-line fit should survive noise much more
easily (the same reason H4 already worked far better than M15 did).

D1 bars are reconstructed from the real H4 export via engine.py's own
derive_d1_from_h4() (already validated there to reproduce a native D1
export's H/L exactly - H4 bars tile exactly 00/04/08/12/16/20 server time
within a day on this broker).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import (
    sma_atr, ext_px, wick_len, find_swings, bos_ok, build_line,
    PIVOT_STRENGTH, TOUCH_TOL_ATR, BREAK_TOL_ATR, ATR_PERIOD,
    TOUCHES_TO_VALIDATE, BREAK_CONFIRM_CLOSES, REACT_BARS, REACT_ATR,
    LOOKBACK_BARS,
)

np.random.seed(42)


def run(df, label):
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    print(f"{label}: {df['time'].min()} -> {df['time'].max()}, n={n} bars")

    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    print(f"  swings found: {len(zIdx)}")

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
    print(f"  candidate lines: {len(lines)}, VALID (3+ touches): {len(valid_lines)}")

    real_outcomes, shadow_outcomes, touch_bar = [], [], []
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
                    real_outcomes.append(outcome)
                    touch_bar.append(q)
                    lv_s0 = c[q]
                    outcome_s = 0
                    closes_beyond_s = 0
                    for k in range(q + 1, min(q + 1 + REACT_BARS, n)):
                        lvk_s = lv_s0
                        penCk_s = (c[k] - lvk_s) if dir_ < 0 else (lvk_s - c[k])
                        if penCk_s > BREAK_TOL_ATR * atr[k]:
                            closes_beyond_s += 1
                            if closes_beyond_s >= BREAK_CONFIRM_CLOSES:
                                outcome_s = -1; break
                        else:
                            closes_beyond_s = 0
                        away_s = (lvk_s - c[k]) if dir_ < 0 else (c[k] - lvk_s)
                        if away_s > REACT_ATR * atr[k]:
                            outcome_s = 1; break
                    shadow_outcomes.append(outcome_s)
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

    return (np.array(real_outcomes), np.array(shadow_outcomes), np.array(touch_bar), n)


def summarize(outcomes, label):
    n_ = len(outcomes)
    if n_ == 0:
        print(f"    {label}: 0 definitive outcomes"); return None
    bounce = int((outcomes == 1).sum())
    print(f"    {label}: n={n_} bounce={bounce} ({100*bounce/n_:.1f}%) break={n_-bounce} ({100*(n_-bounce)/n_:.1f}%)")
    return bounce, n_


if __name__ == "__main__":
    h4 = E.load_h4()
    d1 = E.derive_d1_from_h4(h4)
    d1["time"] = pd.to_datetime(d1["date"])
    real, shadow, touch_bar, n = run(d1, "D1 (reconstructed from real GOLD# H4)")

    print(f"\n  total definitive real touch outcomes: {len(real)}\n")

    print("=" * 70)
    print("POOLED")
    r_all = summarize(real, "REAL")
    s_all = summarize(shadow, "SHADOW (flat line through price, same bars)")
    if r_all and s_all:
        from scipy import stats
        table = [[r_all[0], r_all[1] - r_all[0]], [s_all[0], s_all[1] - s_all[0]]]
        odds, p = stats.fisher_exact(table, alternative="greater")
        print(f"    Fisher exact (real > shadow): odds={odds:.2f} p={p:.4f}")

    print("\n" + "=" * 70)
    print("WALK-FORWARD SPLIT (chronological 70% IS / 30% OOS, by TOUCH bar time)")
    cutoff = int(n * 0.7)
    is_mask = touch_bar < cutoff
    oos_mask = ~is_mask
    cutoff_date = d1["time"].iloc[cutoff] if cutoff < n else d1["time"].iloc[-1]
    print(f"  IS/OOS cutoff: bar {cutoff} ({cutoff_date})\n")

    print("  --- IN-SAMPLE (earlier 70%) ---")
    r_is = summarize(real[is_mask], "REAL")
    s_is = summarize(shadow[is_mask], "SHADOW")
    if r_is and s_is and r_is[1] > 5 and s_is[1] > 5:
        from scipy import stats
        table = [[r_is[0], r_is[1] - r_is[0]], [s_is[0], s_is[1] - s_is[0]]]
        odds, p = stats.fisher_exact(table, alternative="greater")
        print(f"    Fisher exact (real > shadow): odds={odds:.2f} p={p:.4f}")

    print("\n  --- OUT-OF-SAMPLE (later 30%, untouched by anything above) ---")
    r_oos = summarize(real[oos_mask], "REAL")
    s_oos = summarize(shadow[oos_mask], "SHADOW")
    if r_oos and s_oos and r_oos[1] > 5 and s_oos[1] > 5:
        from scipy import stats
        table = [[r_oos[0], r_oos[1] - r_oos[0]], [s_oos[0], s_oos[1] - s_oos[0]]]
        odds, p = stats.fisher_exact(table, alternative="greater")
        print(f"    Fisher exact (real > shadow): odds={odds:.2f} p={p:.4f}")

    print("\n" + "=" * 70)
    if r_is and r_oos and r_all:
        is_rate = r_is[0] / r_is[1] if r_is[1] else float("nan")
        oos_rate = r_oos[0] / r_oos[1] if r_oos[1] else float("nan")
        print(f"VERDICT INPUTS: pooled bounce rate {100*r_all[0]/r_all[1]:.1f}%, "
              f"IS {100*is_rate:.1f}%, OOS {100*oos_rate:.1f}% "
              f"(a stable effect should show both IS and OOS clearly above their own shadow rates)")
