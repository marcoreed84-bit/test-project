"""
Follow-up to vanguard_winner_signature_test.py's finding: raw entry
ATR clearly separates top-20 winners (mean 7.99) from losers (mean
2.80) - but that's mostly just re-encoding "this system does better in
2025-2026's higher-volatility regime" (gold's own ATR grew ~5.7x over
the period, already established). A raw ATR threshold would just trade
less in 2023-24 and more in 2025-26, worsening the year-dependency
concern rather than fixing anything new.

Tests the causally-fair version instead: ROLLING ATR percentile (is
current ATR elevated relative to its own trailing history, not an
absolute level) - adapts locally to whatever regime is current, so it
isn't just a disguised "trade more in recent years" filter. A near-
identical idea (atr_percentile_filter) was already tried and rejected
on Meridian's construction this session - not yet verified on
Vanguard's, tested directly here rather than assumed to transfer.

Explicitly checks the real top-20 trades are preserved before trusting
any net/PF number, per the user's own direct ask.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered
from meridian_dd_confluence_test import drawdown_stats

FRACTAL_K = 100
SAFETY_SL = 4.0
MIN_SR = 0.50
N_RANDOM_SEEDS = 300


def rolling_percentile(x, window):
    """Causal: percentile rank of x[i] within x[i-window:i] only (no
    lookahead) - the trailing window is fully in the past relative to i."""
    s = pd.Series(x)
    return s.rolling(window).apply(lambda w: (w < w.iloc[-1]).mean(), raw=False).values


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < MIN_SR)
    vwap_sr_ok = vwap_ok & sr_ok

    baseline_trades, _ = sim_trendline_filtered(events, vwap_sr_ok, close, high, low, spread, atr, n)
    baseline_top20 = sorted(baseline_trades, key=lambda t: -t[2])[:20]
    top20_entries = set(t[0] for t in baseline_top20)
    print(f"BASELINE +VWAP+S/R: n={len(baseline_trades)} net={sum(t[2] for t in baseline_trades):.2f}")
    print(f"top20 entry bar indices flagged for preservation check: {len(top20_entries)}\n")

    for window in (2000, 5000, 10000):   # ~7, ~17, ~35 trading days at M5
        atr_pctl = rolling_percentile(atr, window)
        for min_pctl in (0.3, 0.5, 0.7):
            atr_ok = np.zeros(n, dtype=bool)
            for i, d in events:
                if not np.isnan(atr_pctl[i]):
                    atr_ok[i] = atr_pctl[i] >= min_pctl
            combo = vwap_sr_ok & atr_ok
            trades, _ = sim_trendline_filtered(events, combo, close, high, low, spread, atr, n)
            if not trades:
                print(f"  window={window} min_pctl={min_pctl}: 0 trades"); continue
            pnls = np.array([t[2] for t in trades])
            gw = pnls[pnls>0].sum(); gl=-pnls[pnls<=0].sum()
            pf = gw/gl if gl>0 else float('inf')
            net = pnls.sum()
            kept_entries = set(t[0] for t in trades)
            top20_kept = len(top20_entries & kept_entries)
            print(f"  window={window:5d} min_pctl={min_pctl}: n={len(trades):4d} net={net:9.2f} pf={pf:.3f} "
                  f"win%={100*(pnls>0).mean():.1f}  top20_preserved={top20_kept}/20")

print("\n" + "=" * 70)
print("gentler thresholds - looking for a setting that preserves ALL 20:")
window = 10000
atr_pctl = rolling_percentile(atr, window)
for min_pctl in (0.0, 0.05, 0.1, 0.15, 0.2, 0.25):
    atr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        if not np.isnan(atr_pctl[i]):
            atr_ok[i] = atr_pctl[i] >= min_pctl
    combo = vwap_sr_ok & atr_ok
    trades, _ = sim_trendline_filtered(events, combo, close, high, low, spread, atr, n)
    pnls = np.array([t[2] for t in trades])
    gw = pnls[pnls>0].sum(); gl=-pnls[pnls<=0].sum()
    pf = gw/gl if gl>0 else float('inf')
    kept_entries = set(t[0] for t in trades)
    top20_kept = len(top20_entries & kept_entries)
    print(f"  min_pctl={min_pctl:.2f}: n={len(trades):4d} net={pnls.sum():9.2f} pf={pf:.3f} "
          f"win%={100*(pnls>0).mean():.1f}  top20_preserved={top20_kept}/20")

# which top-20 trades get cut at the first threshold that loses any?
print("\nwhich top-20 trades get excluded first (window=10000, min_pctl=0.3)?")
atr_ok = np.zeros(n, dtype=bool)
for i, d in events:
    if not np.isnan(atr_pctl[i]):
        atr_ok[i] = atr_pctl[i] >= 0.3
combo = vwap_sr_ok & atr_ok
trades, _ = sim_trendline_filtered(events, combo, close, high, low, spread, atr, n)
kept_entries = set(t[0] for t in trades)
for t in baseline_top20:
    status = "KEPT" if t[0] in kept_entries else "EXCLUDED"
    print(f"  entry_bar={t[0]} pnl={t[2]:8.2f} pctl_at_entry={atr_pctl[t[0]]:.3f}  {status}")

print("\n" + "=" * 70)
print("HONESTY CHECK: how much of the min_pctl=0.05/0.10 'improvement' is just")
print("the rolling window's warmup dropping the first ~35 days, vs a real")
print("volatility-floor effect? Compare against min_pctl=0.00 (pure warmup, no")
print("real filtering) as the true baseline for the marginal contribution.")

def get_result(min_pctl):
    atr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        if not np.isnan(atr_pctl[i]):
            atr_ok[i] = atr_pctl[i] >= min_pctl
    combo = vwap_sr_ok & atr_ok
    trades, _ = sim_trendline_filtered(events, combo, close, high, low, spread, atr, n)
    return trades

warmup_only = get_result(0.0)
cand_05 = get_result(0.05)
cand_10 = get_result(0.10)
print(f"  warmup-only (min_pctl=0.00): n={len(warmup_only)} net={sum(t[2] for t in warmup_only):.2f}")
print(f"  min_pctl=0.05:               n={len(cand_05)} net={sum(t[2] for t in cand_05):.2f}")
print(f"  min_pctl=0.10:               n={len(cand_10)} net={sum(t[2] for t in cand_10):.2f}")

print("\npermutation test (candidate's net vs random same-size draws from the")
print("WARMUP-ONLY population's own trades - the fair baseline, not the raw")
print("+VWAP+S/R baseline, since that still includes the pre-warmup trades)")
def perm_test(base_trades, cand_trades, n_draws=2000, seed=0):
    rng = np.random.default_rng(seed)
    pnl_all = np.array([t[2] for t in base_trades])
    k = len(cand_trades)
    cand_net = sum(t[2] for t in cand_trades)
    if k == 0 or k > len(pnl_all):
        return None
    draws = np.array([pnl_all[rng.choice(len(pnl_all), size=k, replace=False)].sum() for _ in range(n_draws)])
    return 100 * (draws < cand_net).mean(), draws.mean()

for label, cand in [("min_pctl=0.05", cand_05), ("min_pctl=0.10", cand_10)]:
    pct, null_mean = perm_test(warmup_only, cand)
    print(f"  {label}: percentile={pct:.1f}  null_mean={null_mean:.2f}")
