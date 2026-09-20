"""
Tests ATR-as-%-of-price (normalized, NOT an absolute dollar threshold -
see SESSION_NOTES.md's Ratchet ATR<2.0 "disguised date filter" precedent
for why an absolute ATR cutoff on gold is a known trap) as an entry
filter on Aurelius's real M5 gate. Uses a ROLLING PERCENTILE of ATR/price
over a long lookback, not a fixed number, so the rule stays meaningful
regardless of gold's future price level.

Motivation: year-by-year real-R (ATR-normalized) edge climbs monotonically
2023->2026 (PF 1.154->2.110, win rate 23.4%->37.9%) alongside ATR/price%
(0.45%->1.07%) - not a raw-dollar scaling artifact since both are already
normalized. Tests whether gating entries on relative-volatility level
captures this relationship as an actual, usable filter.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
import sim as S
from sr_reject_test import split_stats, tail_concentration, permutation_test


def atr_pct_rolling_percentile(close, atr, lookback_bars):
    """rolling percentile RANK of today's ATR/price within its own trailing
    `lookback_bars` window - 1.0 = highest relative volatility seen in that
    window, 0.0 = lowest. Self-adapting, not an absolute cutoff. Uses
    pandas' native rolling rank (fast, C-level) rather than a raw Python
    apply, which is O(n*lookback) and too slow at 6-month M5 windows."""
    atr_pct = atr / close
    s = pd.Series(atr_pct)
    return s.rolling(lookback_bars, min_periods=lookback_bars).rank(pct=True).values


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df, h4, params=E.P)
    n = ctx["n"]

    base_trades = S.simulate(ctx, params=E.P)
    print("BASELINE:", S.stats(base_trades))

    # M5 bars: 1 month ~ 8640 bars (24*12*30), 3 months ~ 25920, 6 months ~ 51840
    for LOOKBACK, label in [(8640, "1mo"), (25920, "3mo"), (51840, "6mo")]:
        pct_rank = atr_pct_rolling_percentile(ctx["close"], ctx["atr"], LOOKBACK)

        years = pd.DatetimeIndex(ctx["time"]).year
        by_year = {}
        for y in np.unique(years):
            idxs = [t["entry_i"] - 1 for t in base_trades if years[t["entry_i"] - 1] == y]
            if idxs:
                by_year[y] = np.nanmean(pct_rank[idxs])
        print(f"\n--- lookback={label} ({LOOKBACK} bars) ---")
        print("mean ATR%-percentile-rank at entry, by year:", {int(y): round(v, 3) for y, v in by_year.items()})

        for thresh in (0.3, 0.4, 0.5, 0.6):
            def filt(ctx_, i, is_buy, _pr=pct_rank, _t=thresh):
                v = _pr[i]
                return (not np.isnan(v)) and v >= _t

            cand_trades = S.simulate(ctx, params=E.P, extra_filter=filt)
            cst = S.stats(cand_trades)
            if cst["n"] == 0:
                print(f"  thresh={thresh}: n=0, skip")
                continue

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

            is_pf = f"{c_is['pf']:.3f}" if c_is else "None"
            oos_pf = f"{c_oos['pf']:.3f}" if c_oos else "None"
            print(f"  thresh={thresh}: n={cst['n']} net={cst['net']:.0f} pf={cst['pf']:.3f} "
                  f"| IS pf={is_pf} OOS pf={oos_pf} "
                  f"| ex-top5={tail['ex_top5_net']:.0f} | perm={perm['percentile'] if perm else None}")
            print(f"    net by year - baseline: {{{', '.join(f'{y}:{v:.0f}' for y,v in sorted(b_by_y.items()))}}}")
            print(f"    net by year - candidate: {{{', '.join(f'{y}:{v:.0f}' for y,v in sorted(c_by_y.items()))}}}")
