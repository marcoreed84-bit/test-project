"""
New construction per direct chart annotation (2026-10-17): entry is the
dual-stoch cross-in-zone (unchanged, already-audited mechanism) PLUS the
200-EMA direction filter (buys only above it, sells only below it - the
chart shows only buy examples, both with price clearly above the purple
200-EMA line). The EXIT is different from everything tested so far in
this line: not the stochastic reaching the opposite zone, but PRICE
itself touching/reaching the opposite Bollinger Band (20, 2) - a price
target, not an oscillator signal. Both annotated examples on the chart
show the exit circled exactly where price tags the upper band.

Mirrored for shorts (price below 200-EMA, cross in overbought, exit at
the LOWER band) for the same reason every other test in this project
checks both directions rather than just the one shown.

Honest K for this addition: 1 (one specific construction, not swept).
Cumulative honest K for 'dual-stoch-in-zone' line: 5 (plain, +200EMA,
+BB-touch-entry-filter, +reverse-cross-exit, +BB-target-exit).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from dual_stoch_cross_200ema_test import (
    stoch_close_smoothed, load_m15, load_m5, pct_pf, report, ema, OVERSOLD, OVERBOUGHT, TIME_CAP_BARS
)
from dual_stoch_bb_filter_test import bollinger


def build_trades_bb_target(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    m200 = ema(close, 200)
    kA, _ = stoch_close_smoothed(close, 21, 5, 5)
    kB, _ = stoch_close_smoothed(close, 14, 3, 3)
    bb_upper, bb_mid, bb_lower = bollinger(close, 20, 2.0)

    results = []
    i = 210
    while i < n - 1:
        if (np.isnan(kA[i]) or np.isnan(kB[i]) or np.isnan(kA[i - 1]) or np.isnan(kB[i - 1])
                or np.isnan(m200[i]) or np.isnan(bb_upper[i]) or np.isnan(bb_lower[i])):
            i += 1
            continue
        cross_up = kB[i - 1] <= kA[i - 1] and kB[i] > kA[i]
        cross_down = kB[i - 1] >= kA[i - 1] and kB[i] < kA[i]
        in_oversold = kA[i] <= OVERSOLD or kB[i] <= OVERSOLD
        in_overbought = kA[i] >= OVERBOUGHT or kB[i] >= OVERBOUGHT

        direction = 0
        if cross_up and in_oversold and close[i] > m200[i]:
            direction = 1
        elif cross_down and in_overbought and close[i] < m200[i]:
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

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            if np.isnan(bb_upper[j]) or np.isnan(bb_lower[j]):
                continue
            hit = (high[j] >= bb_upper[j]) if direction > 0 else (low[j] <= bb_lower[j])
            if hit:
                exit_i = j
                exit_px = bb_upper[j] if direction > 0 else bb_lower[j]
                reason = "BB_TARGET"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run_tf(symbol, tf_label, loader):
    df, point = loader(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} {tf_label} - dual-stoch cross-in-zone + 200EMA filter, BB-band TARGET exit\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_bb_target(df_is, point)
    report(f"{symbol} {tf_label} - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades_bb_target(df_oos, point)
    report(f"{symbol} {tf_label} - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades_bb_target(df, point)
    report(f"{symbol} {tf_label} - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    run_tf("GOLD", "M15", load_m15)
    run_tf("GOLD", "M5", load_m5)
    print(f"\n\n  Cumulative honest K for 'dual-stoch-in-zone' research line: 5")
    print(f"  (plain, +200EMA, +BB-touch-entry, +reverse-cross-exit, +BB-target-exit).")


def random_timing_null_bb(df, point, real_trades, direction, n_draws=300, seed=0, time_cap_bars=TIME_CAP_BARS):
    """Longs-only (or shorts-only) null: same BB-target/time-cap exit
    machinery, same real spread, entry COUNT matched to the real
    system's count for that direction - entries at uniformly random
    bars (no 200EMA requirement either - the null doesn't need to
    mimic the filter, only the exit mechanics and cost) instead of on
    the dual-stoch-cross-in-zone signal. Tests whether the ENTRY
    TIMING itself has skill, separate from "does the system make
    money" (already reported above)."""
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    bb_upper, bb_mid, bb_lower = bollinger(close, 20, 2.0)
    valid_mask = ~(np.isnan(bb_upper) | np.isnan(bb_lower))
    valid_idx = np.where(valid_mask)[0]
    valid_idx = valid_idx[(valid_idx >= 210) & (valid_idx < n - time_cap_bars - 2)]

    n_trades = len(real_trades)
    rng = np.random.default_rng(seed)

    net_pcts = []
    for _ in range(n_draws):
        total = 0.0
        picks = rng.choice(valid_idx, size=n_trades, replace=False)
        for idx in picks:
            fill_i = idx + 1
            sc = spread[fill_i] * point
            entry_px = close[fill_i] + (sc if direction > 0 else -sc)
            hard_limit = min(fill_i + time_cap_bars, n - 1)
            exit_px = close[hard_limit]
            for j in range(fill_i + 1, hard_limit + 1):
                if np.isnan(bb_upper[j]) or np.isnan(bb_lower[j]):
                    continue
                hit = (high[j] >= bb_upper[j]) if direction > 0 else (low[j] <= bb_lower[j])
                if hit:
                    exit_px = bb_upper[j] if direction > 0 else bb_lower[j]
                    break
            total += ((exit_px - entry_px) / entry_px) * direction
        net_pcts.append(total)
    net_pcts = np.array(net_pcts)
    real_net = sum(r["pnl_pct"] for r in real_trades)
    p_value = (np.sum(net_pcts >= real_net) + 1) / (n_draws + 1)
    return real_net, net_pcts, p_value


def run_longs_null(symbol, tf_label, loader):
    df, point = loader(symbol)
    full_res = build_trades_bb_target(df, point)
    longs = [r for r in full_res if r["dir"] > 0]
    print(f"\n{symbol} {tf_label} LONGS-ONLY random-timing null (n_real={len(longs)}, n_draws=300):")
    real_net, null_dist, p = random_timing_null_bb(df, point, longs, direction=1)
    print(f"  real net%={100*real_net:.2f}   null mean%={100*null_dist.mean():.2f}   "
          f"null std%={100*null_dist.std():.2f}   p-value={p:.4f}")


if __name__ == "__main__":
    run_longs_null("GOLD", "M15", load_m15)
    run_longs_null("GOLD", "M5", load_m5)
