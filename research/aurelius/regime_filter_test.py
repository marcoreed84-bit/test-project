"""
Tests Kaufman's Efficiency Ratio as an entry filter on Aurelius's real M5
gate, before building it into the EA's panel - per the user's explicit
"test it before we just put it in there, it has to actually also help"
instruction, and the specific question: does it leave 2026 (the good
period) untouched while cutting bad trades elsewhere, or does it hurt the
good period too?

ER[i] = |close[i] - close[i-N]| / sum(|close[j]-close[j-1]| for j in i-N+1..i)
1.0 = perfectly efficient trend (net move == total path). 0.0 = pure chop
(net move is zero despite a lot of back-and-forth).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
import sim as S
from sr_reject_test import split_stats, tail_concentration, permutation_test


def efficiency_ratio(close, n):
    net = np.abs(close - np.roll(close, n))
    net[:n] = np.nan
    diffs = np.abs(np.diff(close, prepend=close[0]))
    path = pd.Series(diffs).rolling(n, min_periods=n).sum().values
    with np.errstate(invalid="ignore", divide="ignore"):
        er = net / path
    er[:n] = np.nan
    return er


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df, h4, params=E.P)
    n = ctx["n"]

    base_trades = S.simulate(ctx, params=E.P)
    print("BASELINE:", S.stats(base_trades))

    years = pd.DatetimeIndex(ctx["time"]).year
    for LOOKBACK in (50, 100, 200):
        er = efficiency_ratio(ctx["close"], LOOKBACK)

        # --- does ER actually track "2026 was the good period"? ---
        base_er_by_year = {}
        for y in np.unique(years):
            idxs = [t["entry_i"] - 1 for t in base_trades if years[t["entry_i"] - 1] == y]
            if idxs:
                base_er_by_year[y] = np.nanmean(er[idxs])
        print(f"\n--- lookback={LOOKBACK} bars ---")
        print("mean ER at entry, by year:", {int(y): round(v, 4) for y, v in base_er_by_year.items()})

        for thresh in (0.10, 0.15, 0.20, 0.25):
            def filt(ctx_, i, is_buy, _er=er, _t=thresh):
                v = _er[i]
                return (not np.isnan(v)) and v >= _t

            cand_trades = S.simulate(ctx, params=E.P, extra_filter=filt)
            cst = S.stats(cand_trades)
            if cst["n"] == 0:
                print(f"  thresh={thresh}: n=0, skip")
                continue

            # net profit by year, baseline vs candidate - the actual question asked
            def net_by_year(trades):
                out = {}
                for t in trades:
                    y = int(years[t["entry_i"] - 1])
                    out[y] = out.get(y, 0.0) + (t["exit_px"] - t["entry_px"]) * t["dir"]
                return out

            b_by_y = net_by_year(base_trades)
            c_by_y = net_by_year(cand_trades)

            c_is, c_oos = split_stats(cand_trades, n)
            tail = tail_concentration(cand_trades)
            perm = permutation_test(base_trades, cand_trades, n_draws=500)

            print(f"  thresh={thresh}: n={cst['n']} net={cst['net']:.0f} pf={cst['pf']:.3f} "
                  f"| IS pf={c_is['pf'] if c_is else None} OOS pf={c_oos['pf'] if c_oos else None} "
                  f"| ex-top5={tail['ex_top5_net']:.0f} | perm={perm['percentile'] if perm else None}")
            print(f"    net by year - baseline: {{{', '.join(f'{y}:{v:.0f}' for y,v in sorted(b_by_y.items()))}}}")
            print(f"    net by year - candidate: {{{', '.join(f'{y}:{v:.0f}' for y,v in sorted(c_by_y.items()))}}}")
