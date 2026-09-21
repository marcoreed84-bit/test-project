"""
Structural lever #1 (distinct from every exit-timing idea already
rejected this session): scale position size inversely with ATR at
entry, so dollar risk per trade stays roughly constant instead of
growing whenever the safety stop (2.5xATR, a FIXED multiple) happens
to fall in an elevated-volatility period. This targets the real MT5
equity drawdown directly (a dollar-risk problem) without touching
entry/exit timing at all - PnL is linear in position size, so each
already-validated v1.02 trade's raw price-difference PnL is simply
rescaled by size_mult[i] = clip(atr_ref / atr[i], lo, hi), computed
from that trade's OWN entry-bar ATR. atr_ref = the dataset's median
ATR (a fixed, non-lookahead-safe reference - a trader could reasonably
use this project's own multi-year historical median as a fixed baseline
rather than needing full-sample knowledge at trade time, though a
rolling version would be the honest live implementation; this Python
check uses the full-sample median purely to see whether the IDEA has
any merit before building the (harder) rolling version).

Same v1.02 entries, same drawdown methodology, but the equity curve
is rebuilt from the SCALED per-trade PnL, not the raw one.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m5_stack_variants_fixed_test import sim_filtered_entries

POINT = E.POINT
SAFETY_SL = 2.5
MIN_SR = 0.50


def drawdown_stats_scaled(trades, mults, close, spread, n):
    """Same mark-to-market logic as meridian_dd_confluence_test.drawdown_stats,
    but every trade's realized AND floating PnL is scaled by its own
    size_mult - the position genuinely is bigger/smaller, not just the
    reported number."""
    pnls_raw = np.array([t[2] for t in trades])
    pnls = pnls_raw * mults
    closed_equity = np.cumsum(pnls)
    closed_dd = (np.maximum.accumulate(closed_equity) - closed_equity).max()

    eq_prior = np.concatenate(([0.0], closed_equity[:-1]))
    mtm = np.full(n, np.nan)
    last_eq, prev_exit = 0.0, -1
    for idx, (i, exit_bar, pnl, is_buy) in enumerate(trades):
        mult = mults[idx]
        fill_i = i + 1
        if prev_exit + 1 <= fill_i - 1:
            mtm[prev_exit + 1:fill_i] = last_eq
        entry = close[i] + spread[fill_i] * POINT if is_buy else close[i] - spread[fill_i] * POINT
        seg = close[fill_i:exit_bar + 1]
        floating = ((seg - entry) if is_buy else (entry - seg)) * mult
        mtm[fill_i:exit_bar + 1] = last_eq + floating
        last_eq = eq_prior[idx] + pnl * mult
        prev_exit = exit_bar
    mtm[prev_exit + 1:] = last_eq
    if trades:
        mtm[:trades[0][0] + 1] = 0.0
    valid = ~np.isnan(mtm)
    mtm_v = mtm[valid]
    float_dd = (np.maximum.accumulate(mtm_v) - mtm_v).max() if len(mtm_v) else 0.0
    final_net = closed_equity[-1] if len(closed_equity) else 0.0
    return closed_dd, float_dd, final_net


def evaluate(label, trades, mults, close, spread, n):
    print(f"\n--- {label} ---")
    if not trades:
        print("  0 trades"); return None
    pnls_raw = np.array([t[2] for t in trades])
    pnls = pnls_raw * mults
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats_scaled(trades, mults, close, spread, n)
    print(f"  n={len(trades)} net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
          f"avg_mult={mults.mean():.2f} mult_range=[{mults.min():.2f},{mults.max():.2f}]")
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
    return dict(label=label, n=len(trades), net=net, pf=pf, closed_dd=closed_dd, float_dd=float_dd)


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
    ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        cc = cond_confirm[i] if d > 0 else (not cond_confirm[i])
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if np.isnan(m_confirm[i]) or not (cc and cv):
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    trades = sim_filtered_entries(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL)
    atr_ref = np.nanmedian(atr)
    print(f"reference (median) ATR over full dataset: {atr_ref:.3f}")
    print("shipped v1.02 baseline (fixed size, mult=1.0 always): net=3432.72 pf=1.357 "
          "floatDD%=11.1 walk-forward=5/5\n")

    entry_atrs = np.array([atr[t[0]] for t in trades])
    print("=" * 70)
    for lo_clip, hi_clip in ((0.5, 2.0), (0.3, 3.0), (0.7, 1.5), (0.5, 1.0), (1.0, 2.0)):
        raw_mult = atr_ref / entry_atrs
        mults = np.clip(raw_mult, lo_clip, hi_clip)
        evaluate(f"vol-scaled size, clip=[{lo_clip},{hi_clip}]", trades, mults, close, spread, n)
