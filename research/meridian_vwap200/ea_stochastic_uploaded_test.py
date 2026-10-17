"""
Real backtest of the uploaded EA_Stochastic.mq5 (Mamedov Sergey) -
user asked "will this one work" after I reviewed the code for two
real problems: (1) fixed SL=50pt/TP=150pt is calibrated for a 5-digit
forex pair, not Gold/Silver (50 points = $0.50 on Gold, where a
single M15 bar routinely moves several dollars - that alone would
sink any entry logic), and (2) the buy/sell conditions can both be
true simultaneously (array[0]<80 for buy, array[0]>20 for sell - both
true whenever %K is between 20-80, i.e. most of the time), which the
real EA would fire as two separate orders on the same tick.

This keeps the EA's ACTUAL entry condition faithfully - single
Stochastic(5,3,3), Low/High price field, SMA smoothing (MT5's own
defaults, NOT this project's usual Close/Close+Smoothed convention -
deliberately kept different here to match what's actually in the
uploaded file) - and resolves problem (2) by giving BUY priority
when both conditions are true (an interpretation choice, documented
because it matters: both ARE true on most bars given how loose this
condition is, so which one "wins" determines most of the trade
count). Problem (1) is fixed by replacing the fixed-point SL/TP/
trailing with ATR-scaled equivalents at roughly the same ratios as
the original (1:3 R:R, trailing ~0.3x of stop, 0.1x step) - same
fix-the-real-bug-then-test approach as every other construction
tonight, not a different standard.

Tested on Gold AND Silver M15, full history + walk-forward split +
random-timing null, same rigor as everything else. Honest K: 1 (one
fixed construction - the EA's own stated defaults/ratios, ATR-scaled,
not swept/tuned).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import load_m15, pct_pf, report, TIME_CAP_BARS
from vwap_open_scenarios_test import wilder_atr

K_PERIOD, D_PERIOD, SLOWING = 5, 3, 3
COMPARED_BAR = 3
LEVEL_UP, LEVEL_DOWN = 80.0, 20.0

# ATR-scaled replacements for the EA's fixed 50/150/15/5 points,
# kept at the same ratios (SL:TP = 1:3, trailing = 0.3x SL, step = 0.1x SL)
SL_ATR = 0.5
TP_ATR = 1.5
TRAIL_ATR = 0.15
TRAIL_STEP_ATR = 0.05


def stochastic_lowhigh_sma(high, low, close, k_period, slowing, d_period):
    """MT5's own default Stochastic: Low/High price field, SMA smoothing -
    deliberately NOT this project's Close/Close+Smoothed convention, to
    match what the uploaded EA actually specifies."""
    lowest = pd.Series(low).rolling(k_period, min_periods=k_period).min().values
    highest = pd.Series(high).rolling(k_period, min_periods=k_period).max().values
    rng = highest - lowest
    raw_k = np.full(len(close), np.nan)
    valid = rng > 0
    raw_k[valid] = 100.0 * (close[valid] - lowest[valid]) / rng[valid]
    k = pd.Series(raw_k).rolling(slowing, min_periods=slowing).mean().values
    d = pd.Series(k).rolling(d_period, min_periods=d_period).mean().values
    return k, d


def build_trades(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    atr = wilder_atr(high, low, close, 14)
    k, _ = stochastic_lowhigh_sma(high, low, close, K_PERIOD, SLOWING, D_PERIOD)

    results = []
    i = COMPARED_BAR + 20
    while i < n - 1:
        if np.isnan(k[i]) or np.isnan(k[i - COMPARED_BAR + 1]) or np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        buy_cond = k[i] < LEVEL_UP and k[i - COMPARED_BAR + 1] < LEVEL_UP
        sell_cond = k[i] > LEVEL_DOWN and k[i - COMPARED_BAR + 1] > LEVEL_DOWN
        # buy priority when both true (the real bug's resolution - see
        # module docstring; both ARE usually true given how loose this
        # condition is)
        direction = 1 if buy_cond else (-1 if sell_cond else 0)
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

        a = atr[i]
        stop_px = entry_px - direction * SL_ATR * a
        target_px = entry_px + direction * TP_ATR * a
        trail_dist = TRAIL_ATR * a
        trail_step = TRAIL_STEP_ATR * a

        exit_i, exit_px, reason = None, None, None
        best = entry_px
        cur_stop = stop_px
        for j in range(fill_i + 1, hard_limit + 1):
            px = close[j]
            if direction > 0:
                if px > best:
                    best = px
                    if best - entry_px > trail_dist + trail_step:
                        new_stop = best - trail_dist
                        if new_stop > cur_stop:
                            cur_stop = new_stop
                stop_hit = low[j] <= cur_stop
                target_hit = high[j] >= target_px
            else:
                if px < best:
                    best = px
                    if entry_px - best > trail_dist + trail_step:
                        new_stop = best + trail_dist
                        if new_stop < cur_stop:
                            cur_stop = new_stop
                stop_hit = high[j] >= cur_stop
                target_hit = low[j] <= target_px
            if stop_hit:
                exit_i, exit_px, reason = j, cur_stop, "STOP"
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
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    atr = wilder_atr(high, low, close, 14)
    valid_mask = ~(np.isnan(atr) | (atr <= 0))
    valid_idx = np.where(valid_mask)[0]
    valid_idx = valid_idx[(valid_idx >= 30) & (valid_idx < n - time_cap_bars - 2)]

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
            if fill_i >= n:
                continue
            sc = spread[fill_i] * point
            entry_px = close[fill_i] + (sc if direction > 0 else -sc)
            hard_limit = min(fill_i + time_cap_bars, n - 1)
            a = atr[idx]
            stop_px = entry_px - direction * SL_ATR * a
            target_px = entry_px + direction * TP_ATR * a
            trail_dist = TRAIL_ATR * a
            trail_step = TRAIL_STEP_ATR * a
            best = entry_px
            cur_stop = stop_px
            exit_px = close[hard_limit]
            for j in range(fill_i + 1, hard_limit + 1):
                px = close[j]
                if direction > 0:
                    if px > best:
                        best = px
                        if best - entry_px > trail_dist + trail_step:
                            new_stop = best - trail_dist
                            if new_stop > cur_stop:
                                cur_stop = new_stop
                    stop_hit = low[j] <= cur_stop
                    target_hit = high[j] >= target_px
                else:
                    if px < best:
                        best = px
                        if entry_px - best > trail_dist + trail_step:
                            new_stop = best + trail_dist
                            if new_stop < cur_stop:
                                cur_stop = new_stop
                    stop_hit = high[j] >= cur_stop
                    target_hit = low[j] <= target_px
                if stop_hit:
                    exit_px = cur_stop
                    break
                if target_hit:
                    exit_px = target_px
                    break
            total += ((exit_px - entry_px) / entry_px) * direction
        net_pcts.append(total)
    net_pcts = np.array(net_pcts)
    real_net = sum(r["pnl_pct"] for r in real_trades)
    p = (np.sum(net_pcts >= real_net) + 1) / (n_draws + 1)
    return real_net, net_pcts, p


def run_symbol(symbol):
    df, point = load_m15(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} M15 - EA_Stochastic.mq5 entry logic (ATR-scaled SL/TP/trail, buy-priority fix)\n{'#'*100}")
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

    if len(full_res) >= 10:
        real_net, null_dist, p = random_timing_null(df, point, full_res)
        print(f"\n  Random-timing null (full history, n=500 draws): real net%={100*real_net:.2f}  "
              f"null mean%={100*null_dist.mean():.2f}  null std%={100*null_dist.std():.2f}  p-value={p:.4f}")
    return full_res


if __name__ == "__main__":
    run_symbol("GOLD")
    run_symbol("SILVER")
    print(f"\n\n  Honest K: 1 per symbol (EA's own stated ratios, ATR-scaled, not swept).")
