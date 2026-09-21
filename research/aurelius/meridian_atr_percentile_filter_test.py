"""
Direct follow-up to the concentration finding (top 20 of 637 winners =
97% of net; entry ATR of those top 20 is ~3.4x the typical entry's).
User's ask: can we filter OUT the "noise" trades in advance, i.e. can
entry-time ATR level predict which crosses become the big winners
rather than ordinary trades.

Different test from the already-rejected ADX regime filter
(adx_regime_filter_test.py): ADX measures trend STRENGTH/directional
efficiency: this measures raw volatility LEVEL. Correlation between
entry ATR and trade PnL was only 0.195 (weak) - honest expectation
going in is that this likely doesn't cleanly separate winners from
noise, but it deserves its own test rather than assumed to fail by
analogy to ADX.

Uses a ROLLING percentile of ATR (trailing ~60 trading days, i.e.
60*288 M5 bars) rather than a full-history percentile - the honest,
deployable version (a live EA can't know the full future distribution
of its own ATR at any past point). Requires atr[i] to be at/above the
given rolling percentile to take the entry at all, layered on top of
the shipped v1.02 base (21/50 cross, 250 SMA + VWAP + S/R confirm).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m5_stack_variants_fixed_test import sim_filtered_entries
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
SAFETY_SL = 2.5
MIN_SR = 0.50
ROLL_BARS = 60 * 288  # ~60 trading days of M5 bars


def rolling_percentile_rank(x, window):
    s = pd.Series(x)
    def pct_of_last(w):
        if np.isnan(w[-1]):
            return np.nan
        return (w < w[-1]).mean()
    return s.rolling(window, min_periods=window // 4).apply(pct_of_last, raw=True).values


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

    m21 = E.ma(close, 21, "ema")
    m50 = E.ma(close, 50, "ema")
    m_confirm = E.ma(close, 250, "sma")

    above = m21 > m50
    above_prev = np.concatenate(([False], above[:-1]))
    raw_events = sorted([(i, 1.0) for i in np.where(above & ~above_prev)[0]] +
                         [(i, -1.0) for i in np.where((~above) & above_prev)[0]], key=lambda e: e[0])

    cond_confirm = close > m_confirm
    cond_vwap = close > vwap
    base_ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        cc = cond_confirm[i] if d > 0 else (not cond_confirm[i])
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if np.isnan(m_confirm[i]) or not (cc and cv):
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        base_ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    print("computing rolling ATR percentile (60 trading days)...")
    atr_pct = rolling_percentile_rank(atr, ROLL_BARS)

    print("=" * 70)
    print("shipped v1.02 baseline for reference: net=3432.72 pf=1.357 floatDD%=11.1 walk-forward=5/5\n")

    for thresh in (0.0, 0.3, 0.5, 0.7, 0.8, 0.9):
        ok = np.zeros(n, dtype=bool)
        for i in np.where(base_ok)[0]:
            ok[i] = base_ok[i] and (not np.isnan(atr_pct[i])) and atr_pct[i] >= thresh
        trades = sim_filtered_entries(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL)
        print(f"\n--- ATR rolling-percentile >= {thresh} ({ok.sum()} entries, "
              f"{100*ok.sum()/base_ok.sum():.0f}% of baseline kept) ---")
        if not trades:
            print("  0 trades"); continue
        pnls = np.array([t[2] for t in trades])
        entries = np.array([t[0] for t in trades])
        gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
        pf = gw / gl if gl > 0 else float("inf")
        closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
        print(f"  n={len(trades)} net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f}")
        if net > 0:
            print(f"  closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")
        edges = np.linspace(0, n, 6).astype(int)
        pos = 0
        for b in range(5):
            lo, hi = edges[b], edges[b + 1]
            m = (entries >= lo) & (entries < hi)
            if m.sum() == 0: continue
            if pnls[m].sum() > 0: pos += 1
        print(f"  walk-forward: {pos}/5 blocks positive")
