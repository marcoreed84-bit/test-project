"""
Same realistic (0.01-floor, 0.01-step) ATR-inverse sizing check as
atr_sizing_final_validate.py, run on M15's own validated construction
(k=33, sl=3.0xATR) instead of M5's - required because this session has
already learned once (Meridian) that an M5 finding doesn't
automatically transfer to M15.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered
from meridian_m15_test import build_sr_distance
from atr_sizing_dd_fix import drawdown_stats_scaled
from atr_sizing_realistic_lots import realistic_lots

N_RANDOM_SEEDS = 300
MIN_SR = 0.50
FRACTAL_K = 33
SAFETY_SL = 3.0

if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    df15 = E.resample_m15_from_m5(df5)
    n = len(df15)
    close = df15["close"].values.astype(float)
    high = df15["high"].values.astype(float)
    low = df15["low"].values.astype(float)
    spread = df15["spread"].values.astype(float)
    time = df15["time"].values
    years = np.array([str(t)[:4] for t in time])

    atr = E.wilder_atr(high, low, close, 14)
    vwap = E.session_vwap(df15)
    sr_hi, sr_lo = build_sr_distance(df15, h4)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr_dist_buy = np.abs(sr_hi - close) / atr
        sr_dist_sell = np.abs(close - sr_lo) / atr

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)

    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        entry_ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    trades_fixed, _ = sim_trendline_filtered(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL)
    mean_atr = np.mean([atr[i] for i, ex, pnl, isbuy in trades_fixed])
    print(f"M15 mean entry ATR = {mean_atr:.4f}")

    def scaled_trades(tr):
        scale = np.array([realistic_lots(mean_atr, atr[i], 0.01) / 0.01 for i, ex, pnl, isbuy in tr])
        out = [(i, ex, pnl * s, isbuy) for (i, ex, pnl, isbuy), s in zip(tr, scale)]
        return out, scale

    trades, scale = scaled_trades(trades_fixed)
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats_scaled(trades, scale, close, spread, n)

    print(f"\nATR-SIZED (realistic lots): n={len(trades)} net={net:.2f} pf={pf:.3f} win%={100*(pnls>0).mean():.1f}")
    print(f"  closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")

    fixed_net = sum(t[2] for t in trades_fixed)
    print(f"  (for reference, FIXED-LOT net={fixed_net:.2f})")

    by_year = {}
    for (i, ex, pnl, isbuy), s in zip(trades_fixed, scale):
        by_year.setdefault(years[i], []).append(pnl * s)
    by_year_fixed = {}
    for i, ex, pnl, isbuy in trades_fixed:
        by_year_fixed.setdefault(years[i], []).append(pnl)
    print("\nyear-by-year:  FIXED-LOT  ->  ATR-SIZED")
    for y in sorted(by_year):
        print(f"  {y}: {sum(by_year_fixed[y]):9.2f}  ->  {sum(by_year[y]):9.2f}")

    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    for b in range(5):
        lo, hi = edges[b], edges[b+1]
        m = (entries >= lo) & (entries < hi)
        if m.sum() == 0: continue
        if pnls[m].sum() > 0: pos += 1
    print(f"\nwalk-forward: {pos}/5 blocks positive")

    rng = np.random.default_rng(0)
    random_nets = []
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(events))
        rev = [(i, d) for (i, _), d in zip(events, rdirs)]
        rev.sort(key=lambda e: e[0])
        trades_r, _ = sim_trendline_filtered(rev, entry_ok, close, high, low, spread, atr, n, SAFETY_SL)
        trades_r_scaled, _ = scaled_trades(trades_r)
        random_nets.append(sum(t[2] for t in trades_r_scaled) if trades_r_scaled else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < net).mean()
    print(f"random-direction percentile={pct:.1f} (null mean={random_nets.mean():.2f})")
