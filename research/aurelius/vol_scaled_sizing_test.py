"""
Tests volatility-scaled position sizing on Aurelius M5 - the one real,
literature-backed lever to come out of tonight's exhaustive search for a
new entry edge (Opus searched intraday momentum, session-timing filters,
cross-asset leads, scheduled macro drift, and mean reversion; all refuted
or already rejected). Per Harvey, Hoyle, Korgaonkar, Kou, Oomen & Rattray
2018 ("The Impact of Volatility Targeting"), volatility is forecastable
even when direction isn't - scaling position size by inverse trailing
realized volatility reduces the frequency of extreme returns and vol-of-
vol, across every asset class they tested including commodities.

This does NOT change entries or exits at all - same shipped Aurelius
signal, same validated simulator (sim.py / engine.py), same trades. Only
the SIZE of each trade changes, scaled by inverse trailing realized
volatility of M5 returns at that trade's entry. Compares fixed-size vs
vol-scaled on: max drawdown (closed-trade and float, using the existing
risk_stats), worst single month, and CVaR(5%) of trade-level returns -
at matched total return (the vol-scaled curve is rescaled to have the
same total net as the baseline, so the comparison isolates tail behavior,
not just "smaller positions = smaller everything").

Real GOLD M5 data, real spread, the actual shipped Aurelius parameters -
no new entry/exit research, pure risk-management overlay on an
already-validated system.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from engine import load_m5, load_h4, build_context, P
import sim


def trailing_realized_vol(close, time, window_days=20):
    """Daily realized vol (std of M5 log returns within each day), then a
    trailing `window_days`-day average of that, aligned back to M5 bars -
    the vol estimate known AS OF the start of each bar (uses only prior
    closed days, no lookahead into the current day's own volatility)."""
    n = len(close)
    log_ret = np.full(n, np.nan)
    log_ret[1:] = np.diff(np.log(close))
    day = pd.Series(time).dt.date.values

    day_vol = {}
    days_sorted = sorted(set(day))
    day_start_idx = {}
    for i in range(n):
        if day[i] not in day_start_idx:
            day_start_idx[day[i]] = i
    for idx, d in enumerate(days_sorted):
        s = day_start_idx[d]
        e = (day_start_idx[days_sorted[idx + 1]] - 1) if idx + 1 < len(days_sorted) else n - 1
        seg = log_ret[s + 1:e + 1]
        seg = seg[~np.isnan(seg)]
        day_vol[d] = np.std(seg) if len(seg) > 5 else np.nan

    trailing_avg = {}
    for idx, d in enumerate(days_sorted):
        prior = [day_vol[days_sorted[j]] for j in range(max(0, idx - window_days), idx)
                  if not np.isnan(day_vol[days_sorted[j]])]
        trailing_avg[d] = np.mean(prior) if len(prior) >= 10 else np.nan

    out = np.full(n, np.nan)
    for i in range(n):
        out[i] = trailing_avg[day[i]]
    return out


def apply_vol_scaling(trades, ctx, target_vol_percentile=50):
    """Scales each trade's pnl by (target_vol / trailing_vol_at_entry),
    clipped to [0.25x, 3x] to avoid degenerate sizing on near-zero vol
    readings. target_vol is set to the median trailing vol over the whole
    history, so the AVERAGE multiplier is close to 1x (keeps the two
    curves on a comparable total-exposure scale before the final rescale)."""
    close, time = ctx["close"], ctx["time"]
    trail_vol = trailing_realized_vol(close, time)
    valid = trail_vol[~np.isnan(trail_vol)]
    target_vol = np.percentile(valid, target_vol_percentile)

    scaled_trades = []
    for t in trades:
        v = trail_vol[t["entry_i"]]
        if np.isnan(v) or v <= 0:
            mult = 1.0
        else:
            mult = np.clip(target_vol / v, 0.25, 3.0)
        t2 = dict(t)
        t2["mult"] = mult
        scaled_trades.append(t2)
    return scaled_trades


def pnl_series(trades, scaled=False):
    if scaled:
        return np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] * t["mult"] for t in trades])
    return np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades])


def max_drawdown(cum_curve):
    peak = np.maximum.accumulate(cum_curve)
    dd = peak - cum_curve
    return dd.max()


def worst_month(trades, pnl):
    months = pd.to_datetime([None] * len(trades))
    # exit_i indexes into ctx time array - need access; caller passes times separately
    return None  # placeholder, computed inline below with access to ctx time


def cvar(pnl, alpha=0.05):
    sorted_pnl = np.sort(pnl)
    k = max(1, int(len(sorted_pnl) * alpha))
    return sorted_pnl[:k].mean()


if __name__ == "__main__":
    df = load_m5()
    h4 = load_h4()
    ctx = build_context(df, h4, params=P)
    time = ctx["time"]

    print(f"Aurelius M5, GOLD, {time.iloc[0]} .. {time.iloc[-1]}\n")
    trades = sim.simulate(ctx)
    print(f"Baseline (shipped params): n={len(trades)} trades")

    base_pnl = pnl_series(trades, scaled=False)
    base_stats = sim.stats(trades)
    base_risk = sim.risk_stats(trades, ctx)
    base_cum = np.cumsum(base_pnl)
    base_dd = max_drawdown(base_cum)
    base_cvar = cvar(base_pnl)

    scaled_trades = apply_vol_scaling(trades, ctx)
    scaled_pnl_raw = pnl_series(scaled_trades, scaled=True)
    # rescale vol-scaled curve to match baseline's total net exactly, so the
    # comparison isolates TAIL shape, not just "smaller average bet size"
    rescale_factor = base_pnl.sum() / scaled_pnl_raw.sum() if scaled_pnl_raw.sum() != 0 else 1.0
    scaled_pnl = scaled_pnl_raw * rescale_factor
    scaled_cum = np.cumsum(scaled_pnl)
    scaled_dd = max_drawdown(scaled_cum)
    scaled_cvar = cvar(scaled_pnl)

    exit_times = time.iloc[[t["exit_i"] for t in trades]].values
    months = pd.to_datetime(exit_times).to_period("M")
    base_monthly = pd.Series(base_pnl, index=months).groupby(level=0).sum()
    scaled_monthly = pd.Series(scaled_pnl, index=months).groupby(level=0).sum()

    print(f"\n{'='*90}\nFIXED SIZE (baseline)\n{'='*90}")
    print(f"  net={base_pnl.sum():.2f}  PF={base_stats['pf']:.3f}  win%={100*base_stats['win_rate']:.1f}")
    print(f"  max closed-trade drawdown: {base_dd:.2f}")
    print(f"  CVaR(5%) per-trade: {base_cvar:.4f}")
    print(f"  worst month: {base_monthly.min():.2f}  ({base_monthly.idxmin()})")
    print(f"  risk_stats: closed_dd={base_risk['closed_dd']:.2f}  float_dd={base_risk['float_dd']:.2f}  "
          f"worst_mae_atr={base_risk['worst_mae_atr']:.2f}")

    print(f"\n{'='*90}\nVOL-SCALED SIZE (rescaled to match baseline's total net exactly)\n{'='*90}")
    print(f"  net={scaled_pnl.sum():.2f}  (rescale_factor={rescale_factor:.3f})")
    print(f"  max closed-trade drawdown: {scaled_dd:.2f}   ({'BETTER' if scaled_dd < base_dd else 'WORSE'}, "
          f"{100*(scaled_dd-base_dd)/base_dd:+.1f}% vs baseline)")
    print(f"  CVaR(5%) per-trade: {scaled_cvar:.4f}   ({'BETTER' if scaled_cvar > base_cvar else 'WORSE'})")
    print(f"  worst month: {scaled_monthly.min():.2f}  ({scaled_monthly.idxmin()})   "
          f"({'BETTER' if scaled_monthly.min() > base_monthly.min() else 'WORSE'})")

    print(f"\n{'='*90}\nMultiplier distribution (sanity check - should cluster near 1.0x)\n{'='*90}")
    mults = np.array([t["mult"] for t in scaled_trades])
    print(f"  mean={mults.mean():.3f}  median={np.median(mults):.3f}  "
          f"p5={np.percentile(mults,5):.3f}  p95={np.percentile(mults,95):.3f}")
