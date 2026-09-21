"""
Structural lever #2: partial scale-out. Take a fraction of the position
off at a profit target, let the REMAINDER ride fully uncapped to the
normal exit (reversal or safety stop) - unlike fixed TP (rejected:
caps the ENTIRE position, destroying the payoff asymmetry this system
depends on), this only caps part of it.

Directly informed by what meridian_position_sizing_test.py just found:
only 20 of 2537 trades (0.8%) generate 97% of total net profit, and
those trades occur at a median entry ATR of 6.26 vs 1.83 overall (~3.4x
more volatile than typical). Any mechanism that reduces exposure during
exactly those trades will hurt badly - partial scale-out risks the same
problem, just less severely than a full TP since half the position
still rides uncapped. Tested honestly rather than assumed either way.

Exposure-aware drawdown: reusing the existing drawdown_stats function
would overstate floating risk once the scaled-out leg has already been
banked (it assumes full size the whole way to the final exit bar) - this
tracks both legs' exit bars/prices separately and builds the mark-to-
market curve with the REAL size at each bar (1.0 before leg A exits,
scaleout_frac remaining after).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E

POINT = E.POINT
SAFETY_SL = 2.5
MIN_SR = 0.50


def sim_partial_scaleout(raw_events, entry_ok, close, high, low, spread, atr, n,
                          safety_sl_atr, tp_atr, scaleout_frac):
    """Returns list of (entry_i, legA_exit_bar, legA_pnl, legB_exit_bar, legB_pnl, is_buy).
    legA is the scaleout_frac-sized leg that takes the TP; legB is the
    (1-scaleout_frac)-sized leg that rides uncapped to reversal/stop."""
    trades = []
    for k in range(len(raw_events) - 1):
        i, d = raw_events[k]
        if not entry_ok[i]:
            continue
        i_next, _ = raw_events[k + 1]
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        is_buy = d > 0
        entry = raw + sc if is_buy else raw - sc
        sl = entry - safety_sl_atr * atr[i] if is_buy else entry + safety_sl_atr * atr[i]
        tp = entry + tp_atr * atr[i] if is_buy else entry - tp_atr * atr[i]
        cap = min(i_next + 1, n)

        legA_closed = False
        legA_exit_bar, legA_pnl = None, None
        legB_exit_bar, legB_pnl = None, None

        for kk in range(fill_i, cap):
            stop_hit = (is_buy and low[kk] <= sl) or ((not is_buy) and high[kk] >= sl)
            if stop_hit:
                if not legA_closed:
                    legA_exit_bar, legA_pnl = kk, ((sl - entry) if is_buy else (entry - sl))
                    legA_closed = True
                legB_exit_bar, legB_pnl = kk, ((sl - entry) if is_buy else (entry - sl))
                break
            if not legA_closed:
                tp_hit = (is_buy and high[kk] >= tp) or ((not is_buy) and low[kk] <= tp)
                if tp_hit:
                    legA_exit_bar, legA_pnl = kk, ((tp - entry) if is_buy else (entry - tp))
                    legA_closed = True

        if legB_pnl is None:  # never hit stop within the cap window
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
            legB_exit_bar = exit_bar
            legB_pnl = (exit_px - entry) if is_buy else (entry - exit_px)
            if not legA_closed:
                legA_exit_bar, legA_pnl = exit_bar, legB_pnl

        trades.append((i, legA_exit_bar, legA_pnl, legB_exit_bar, legB_pnl, is_buy))
    return trades


def exposure_aware_drawdown(trades, close, spread, n, scaleout_frac):
    combined_pnls = np.array([scaleout_frac * t[2] + (1 - scaleout_frac) * t[4] for t in trades])
    closed_equity = np.cumsum(combined_pnls)
    closed_dd = (np.maximum.accumulate(closed_equity) - closed_equity).max()

    eq_prior = np.concatenate(([0.0], closed_equity[:-1]))
    mtm = np.full(n, np.nan)
    last_eq, prev_exit = 0.0, -1
    for idx, (i, legA_exit, legA_pnl, legB_exit, legB_pnl, is_buy) in enumerate(trades):
        fill_i = i + 1
        if prev_exit + 1 <= fill_i - 1:
            mtm[prev_exit + 1:fill_i] = last_eq
        entry = close[i] + spread[fill_i] * POINT if is_buy else close[i] - spread[fill_i] * POINT
        # full size until legA exits
        seg1 = close[fill_i:legA_exit + 1]
        floating1 = ((seg1 - entry) if is_buy else (entry - seg1))
        mtm[fill_i:legA_exit + 1] = last_eq + floating1
        # after legA banks its share, only (1-scaleout_frac) remains exposed
        banked = scaleout_frac * legA_pnl
        if legB_exit > legA_exit:
            seg2 = close[legA_exit + 1:legB_exit + 1]
            floating2 = ((seg2 - entry) if is_buy else (entry - seg2)) * (1 - scaleout_frac)
            mtm[legA_exit + 1:legB_exit + 1] = last_eq + banked + floating2
        last_eq = eq_prior[idx] + scaleout_frac * legA_pnl + (1 - scaleout_frac) * legB_pnl
        prev_exit = legB_exit
    mtm[prev_exit + 1:] = last_eq
    if trades:
        mtm[:trades[0][0] + 1] = 0.0
    valid = ~np.isnan(mtm)
    mtm_v = mtm[valid]
    float_dd = (np.maximum.accumulate(mtm_v) - mtm_v).max() if len(mtm_v) else 0.0
    final_net = closed_equity[-1] if len(closed_equity) else 0.0
    return closed_dd, float_dd, final_net


def evaluate(label, trades, close, spread, n, scaleout_frac):
    print(f"\n--- {label} ---")
    if not trades:
        print("  0 trades"); return None
    combined_pnls = np.array([scaleout_frac * t[2] + (1 - scaleout_frac) * t[4] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = combined_pnls[combined_pnls > 0].sum(); gl = -combined_pnls[combined_pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = exposure_aware_drawdown(trades, close, spread, n, scaleout_frac)
    print(f"  n={len(trades)} net={net:.2f} win%={100*(combined_pnls>0).mean():.1f} pf={pf:.3f}")
    if net > 0:
        print(f"  closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")
    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        if m.sum() == 0: continue
        if combined_pnls[m].sum() > 0: pos += 1
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

    print("=" * 70)
    print("shipped v1.02 baseline (no scale-out) for reference: net=3432.72 pf=1.357 "
          "floatDD%=11.1 walk-forward=5/5\n")

    for scaleout_frac, tp_atr in ((0.25, 1.0), (0.25, 2.0), (0.5, 1.0), (0.5, 1.5), (0.5, 2.0), (0.75, 1.0), (0.75, 2.0)):
        trades = sim_partial_scaleout(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL, tp_atr, scaleout_frac)
        evaluate(f"scaleout={scaleout_frac} at TP={tp_atr}xATR, remainder uncapped", trades, close, spread, n, scaleout_frac)
