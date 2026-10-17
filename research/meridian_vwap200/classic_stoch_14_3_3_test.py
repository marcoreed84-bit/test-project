"""
Exact backtest of the "classic/textbook" construction now drawn on
TradePanel_EA v1.20's chart overlay, per direct request - the PDF
articles' described rule, NOT this project's own researched
Close/Close+Smoothed 21,5,5 convention used everywhere else tonight.

Construction (matches SigClassicStoch() in TradePanel_EA.mq5 exactly):
  - Stochastic(14,3,3), Low/High price field, SMA smoothing (MT5's own
    native default).
  - Entry: %K crosses %D WHILE STILL INSIDE the zone - buy when
    cross-up happens with %K<20, sell when cross-down happens with
    %K>80. Not a zone-exit rule.
  - Stop: the lowest low / highest high of the preceding 10 closed
    bars (SIG_SWING_BARS in the EA).
  - Target: fixed 1:2 risk:reward off that stop distance (SIG_RR=2.0
    in the EA - the EA's own comment calls this "a representative
    example, not validated").
  - Fill on the next bar's close +/- real spread, same convention as
    every other test tonight.

Tested Gold + Silver M15, full rigor (walk-forward IS/OOS split,
random-timing null matched on trade count/direction and real spread
cost).

2026-10-17 update: swing-stop lookback changed from 10 to 20 bars per
direct request (wider stop, same everything else) after the 10-bar
version lost on both symbols with 75-85% of trades hitting the stop -
testing whether a less noise-sensitive stop changes that. Honest K: 2
per symbol now (10-bar and 20-bar swing both tried against this same
Gold+Silver M15 history - this is a real second look, not a free
retune, and should be reported as such regardless of outcome).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import load_m15
from dual_stoch_cross_200ema_test import pct_pf, report, TIME_CAP_BARS

K_PERIOD, SLOWING, D_PERIOD = 14, 3, 3
SWING_BARS = 20
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0


def stochastic_lowhigh_sma(high, low, close, k_period, slowing, d_period):
    """MT5's own default Stochastic: Low/High price field, SMA smoothing -
    same formula as SigClassicStoch() in the EA (slowing = SMA of the
    numerator/denominator sums, not an SMA of raw %K - matches MT5's
    actual iStochastic(STO_LOWHIGH, MODE_SMA) behavior)."""
    n = len(close)
    lowest = pd.Series(low).rolling(k_period, min_periods=k_period).min().values
    highest = pd.Series(high).rolling(k_period, min_periods=k_period).max().values
    num_raw = close - lowest
    den_raw = highest - lowest
    num_slow = pd.Series(num_raw).rolling(slowing, min_periods=slowing).sum().values
    den_slow = pd.Series(den_raw).rolling(slowing, min_periods=slowing).sum().values
    k = np.full(n, np.nan)
    valid = den_slow > 0
    k[valid] = 100.0 * num_slow[valid] / den_slow[valid]
    k[den_slow == 0] = 100.0
    d = pd.Series(k).rolling(d_period, min_periods=d_period).mean().values
    return k, d


def build_trades(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    k, d = stochastic_lowhigh_sma(high, low, close, K_PERIOD, SLOWING, D_PERIOD)

    results = []
    i = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
    while i < n - 1:
        if np.isnan(k[i]) or np.isnan(d[i]) or np.isnan(k[i - 1]) or np.isnan(d[i - 1]):
            i += 1
            continue
        cross_up = k[i - 1] <= d[i - 1] and k[i] > d[i]
        cross_down = k[i - 1] >= d[i - 1] and k[i] < d[i]

        direction = 0
        if cross_up and k[i] < ZONE_LOW:
            direction = 1
        elif cross_down and k[i] > ZONE_HIGH:
            direction = -1
        if direction == 0:
            i += 1
            continue

        fill_i = i + 1
        if fill_i >= n:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)
        hard_limit = min(fill_i + time_cap_bars, n - 1)

        swing_low = low[i - SWING_BARS:i].min()
        swing_high = high[i - SWING_BARS:i].max()
        if direction > 0:
            stop_px = swing_low
            risk = entry_px - stop_px
        else:
            stop_px = swing_high
            risk = stop_px - entry_px
        if risk <= 0:
            i += 1
            continue
        target_px = entry_px + direction * RR * risk

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if direction > 0 else (high[j] >= stop_px)
            target_hit = (high[j] >= target_px) if direction > 0 else (low[j] <= target_px)
            if stop_hit and target_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if target_hit:
                exit_i, exit_px, reason = j, target_px, "TARGET"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def random_timing_null(df, point, real_trades, n_draws=500, seed=0, time_cap_bars=TIME_CAP_BARS):
    """Same exit machinery (swing stop + 1:2RR target + time cap), same real
    spread cost, entry count/direction mix matched to the real system -
    entries placed at uniformly random bars instead of on the classic
    stoch cross-in-zone signal."""
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    k, d = stochastic_lowhigh_sma(high, low, close, K_PERIOD, SLOWING, D_PERIOD)
    valid_mask = ~(np.isnan(k) | np.isnan(d))
    valid_idx = np.where(valid_mask)[0]
    lo = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
    valid_idx = valid_idx[(valid_idx >= lo) & (valid_idx < n - time_cap_bars - 2)]

    n_long = sum(1 for r in real_trades if r["dir"] > 0)
    n_short = sum(1 for r in real_trades if r["dir"] < 0)
    rng = np.random.default_rng(seed)

    net_pcts = []
    for _ in range(n_draws):
        total = 0.0
        picks = rng.choice(valid_idx, size=n_long + n_short, replace=False)
        dirs = [1] * n_long + [-1] * n_short
        rng.shuffle(dirs)
        for idx, direction in zip(picks, dirs):
            fill_i = idx + 1
            sc = spread[fill_i] * point
            entry_px = close[fill_i] + (sc if direction > 0 else -sc)
            hard_limit = min(fill_i + time_cap_bars, n - 1)
            swing_low = low[idx - SWING_BARS:idx].min()
            swing_high = high[idx - SWING_BARS:idx].max()
            if direction > 0:
                stop_px = swing_low
                risk = entry_px - stop_px
            else:
                stop_px = swing_high
                risk = stop_px - entry_px
            if risk <= 0:
                continue
            target_px = entry_px + direction * RR * risk
            exit_px = close[hard_limit]
            for j in range(fill_i + 1, hard_limit + 1):
                stop_hit = (low[j] <= stop_px) if direction > 0 else (high[j] >= stop_px)
                target_hit = (high[j] >= target_px) if direction > 0 else (low[j] <= target_px)
                if stop_hit:
                    exit_px = stop_px
                    break
                if target_hit:
                    exit_px = target_px
                    break
            total += ((exit_px - entry_px) / entry_px) * direction
        net_pcts.append(total)
    net_pcts = np.array(net_pcts)
    real_net = sum(r["pnl_pct"] for r in real_trades)
    p_value = (np.sum(net_pcts >= real_net) + 1) / (n_draws + 1)
    return real_net, net_pcts, p_value


def run_symbol(symbol):
    df, point = load_m15(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} M15 - classic Stochastic(14,3,3) Low/High+SMA, cross-in-zone, "
          f"{SWING_BARS}-bar swing stop, 1:{RR:.0f} R:R target\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point)
    report(f"{symbol} M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point)
    report(f"{symbol} M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point)
    report(f"{symbol} M15 - FULL HISTORY", full_res, full_days, split_dir=True)

    full_pf = pct_pf(full_res)
    if len(full_res) < 10:
        print(f"\n  (too few trades (n={len(full_res)}) for a meaningful random-timing null)")
    elif full_pf < 1.0:
        print(f"\n  (skipping random-timing null - full-history %PF={full_pf:.3f} is already a clear")
        print(f"   net loser on {len(full_res)} real trades)")
    else:
        print(f"\n  Random-timing null (full history, n=500 draws, matched trade count/direction):")
        real_net, null_dist, p = random_timing_null(df, point, full_res)
        print(f"    real net%={100*real_net:.2f}   null mean%={100*null_dist.mean():.2f}   "
              f"null std%={100*null_dist.std():.2f}   p-value={p:.4f}")
    return full_res


if __name__ == "__main__":
    run_symbol("GOLD")
    run_symbol("SILVER")
    print(f"\n\n  Honest K: 2 per symbol (classic Stoch(14,3,3) Low/High+SMA cross-in-zone,")
    print(f"  10-bar AND {SWING_BARS}-bar swing stop both tried against this same history,")
    print(f"  fixed 1:{RR:.0f} R:R - a real second look, not a free retune).")
