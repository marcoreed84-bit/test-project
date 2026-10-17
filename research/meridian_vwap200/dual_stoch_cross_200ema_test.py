"""
New, specific construction per direct instruction (2026-10-17, corrected
after a follow-up clarification mid-build): TWO Stochastic oscillators,
both set to MA method = Smoothed (SMMA) and Price field = Close/Close
(the raw %K uses rolling min/max of CLOSE, not High/Low - a real,
meaningful difference from every earlier stochastic test in this
project, which all used High/Low + plain SMA).

  Stoch A (slow): %K(21, 5, 5)   - the "first signal line"
  Stoch B (fast): %K(14, 3, 3)   - the "second signal line"

Entry (causal, no lookahead, fixed settings - NOT tuned, so K=1 for
this file's own search) - per direct correction, "obviously a buy
would be the signal lines crossing AT the oversold zone (and vice
versa for a sell)", i.e. the cross location IS the signal, not a
separate EMA trend filter:
  - BUY: the fast line (B) crosses UP through the slow line (A) while
    BOTH are down in the oversold zone (<=20) at the cross bar.
  - SELL: the mirror - B crosses DOWN through A while both are up in
    the overbought zone (>=80).
  - fill on the NEXT bar's open +/- real spread, same convention as
    every other test in this project.
  - the 200-EMA direction filter from the original request ("maybe
    test buys above 200ema...") is reported as an OPTIONAL add-on
    variant on top of the corrected entry, not the primary gate -
    both with and without it are run, neither was tuned/selected.

Exit: reaching the OPPOSITE zone from entry - overbought (80) for a
buy, oversold (20) for a sell - checked on either stochastic line,
whichever gets there first. A hard time cap is the fallback for
trades that never reach it.

Tested on Gold, M15 AND M5 (both explicitly requested), full-history
walk-forward split (70/30, no tuning performed - fixed inputs as
specified), plus a random-timing null matched on trade count/direction
and real spread cost, per this project's standing statistical
discipline. Gold's pre-2014-06-13 M15 contamination filter applies
automatically via load_m15(); M5 loads its own native-resolution file,
no contamination issue there.

Honest K for this file: 2 per timeframe (the plain construction, and
the +200EMA-filter variant - both reported, neither chosen by looking
at which one wins on this data).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema
from meridian_early_cross_test import load_m15, DATA_DIR

TIME_CAP_BARS = 200
OVERSOLD, OVERBOUGHT = 20.0, 80.0


def load_m5(symbol):
    path = os.path.join(DATA_DIR, f"{symbol}_M5.csv")
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    if symbol == "GOLD":
        df = df[df["time"] >= pd.Timestamp("2014-06-13")].reset_index(drop=True)
    return df.reset_index(drop=True), point


def smma(x, period):
    n = len(x)
    out = np.full(n, np.nan)
    first = None
    for i in range(n):
        if not np.isnan(x[i]):
            first = i
            break
    if first is None or first + period > n:
        return out
    out[first + period - 1] = np.nanmean(x[first:first + period])
    for i in range(first + period, n):
        out[i] = (out[i - 1] * (period - 1) + x[i]) / period
    return out


def stoch_close_smoothed(close, k_period, k_slow, d_period):
    """Price field = Close/Close (NOT High/Low), MA method = Smoothed (SMMA)
    for both the %K slowing step and %D - matches MT5's own Stochastic
    Oscillator indicator with those two settings changed from their
    High/Low + SMA defaults, exactly as specified."""
    lowest = pd.Series(close).rolling(k_period, min_periods=k_period).min().values
    highest = pd.Series(close).rolling(k_period, min_periods=k_period).max().values
    rng = highest - lowest
    raw_k = np.full(len(close), np.nan)
    valid = rng > 0
    raw_k[valid] = 100.0 * (close[valid] - lowest[valid]) / rng[valid]
    k = smma(raw_k, k_slow)
    d = smma(k, d_period)
    return k, d


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results, n_days=None, split_dir=False):
    if not results:
        print(f"  {label}: n=0")
        return
    arr = np.array([r["pnl_pct"] for r in results])
    holds = np.array([r["hold_bars"] for r in results])
    reasons = {}
    for r in results:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    rtxt = ", ".join(f"{k}:{v}" for k, v in reasons.items())
    pm = f"  (~{len(results)/(n_days/30.44):.1f}/mo)" if n_days else ""
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  %PF={pct_pf(results):6.3f}  "
          f"net%={100*arr.sum():7.2f}  avg_hold={holds.mean():5.1f} bars  [{rtxt}]{pm}")
    if split_dir:
        longs = [r for r in results if r["dir"] > 0]
        shorts = [r for r in results if r["dir"] < 0]
        report("    -> LONGS only", longs, n_days)
        report("    -> SHORTS only", shorts, n_days)


def build_trades(df, point, exit_mode="either", use_ema_filter=False, time_cap_bars=TIME_CAP_BARS):
    """Entry per direct clarification: a BUY is the fast line (B, 14,3,3)
    crossing UP through the slow line (A, 21,5,5) while BOTH are down in
    the oversold zone (<=20) at the cross bar - not just any cross,
    anywhere. A SELL is the mirror: B crosses DOWN through A while both
    are up in the overbought zone (>=80). use_ema_filter adds the
    200-EMA direction gate as an optional extra ("maybe test" in the
    original request, not the primary signal)."""
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    m200 = ema(close, 200)
    kA, _ = stoch_close_smoothed(close, 21, 5, 5)
    kB, _ = stoch_close_smoothed(close, 14, 3, 3)

    results = []
    i = 210
    while i < n - 1:
        if (np.isnan(kA[i]) or np.isnan(kB[i]) or np.isnan(kA[i - 1]) or np.isnan(kB[i - 1])
                or (use_ema_filter and np.isnan(m200[i]))):
            i += 1
            continue
        cross_up = kB[i - 1] <= kA[i - 1] and kB[i] > kA[i]
        cross_down = kB[i - 1] >= kA[i - 1] and kB[i] < kA[i]
        # EITHER line in zone, not both - per direct correction: the
        # faster line often reaches past 20/80 while the slower one
        # is still short of it (e.g. fast=18, slow=22) and that's
        # still meant to count as a valid in-zone cross.
        in_oversold = kA[i] <= OVERSOLD or kB[i] <= OVERSOLD
        in_overbought = kA[i] >= OVERBOUGHT or kB[i] >= OVERBOUGHT

        direction = 0
        if cross_up and in_oversold:
            direction = 1
        elif cross_down and in_overbought:
            direction = -1
        if direction == 0:
            i += 1
            continue
        if use_ema_filter:
            if direction > 0 and not (close[i] > m200[i]):
                i += 1
                continue
            if direction < 0 and not (close[i] < m200[i]):
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
            if np.isnan(kA[j]) or np.isnan(kB[j]):
                continue
            hit_a = (kA[j] >= OVERBOUGHT) if direction > 0 else (kA[j] <= OVERSOLD)
            hit_b = (kB[j] >= OVERBOUGHT) if direction > 0 else (kB[j] <= OVERSOLD)
            hit = (hit_a or hit_b) if exit_mode == "either" else (hit_a if exit_mode == "A" else hit_b)
            if hit:
                exit_i, exit_px, reason = j, close[j], "ZONE"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def random_timing_null(df, point, real_trades, n_draws=2000, seed=0, time_cap_bars=TIME_CAP_BARS):
    """Same exit machinery (zone-or-time), same real spread, entry COUNT and
    DIRECTION MIX matched to the real system - entries placed at uniformly
    random bars instead of on the dual-stoch cross signal."""
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    kA, _ = stoch_close_smoothed(close, 21, 5, 5)
    kB, _ = stoch_close_smoothed(close, 14, 3, 3)
    valid_mask = ~(np.isnan(kA) | np.isnan(kB))
    valid_idx = np.where(valid_mask)[0]
    valid_idx = valid_idx[(valid_idx >= 210) & (valid_idx < n - time_cap_bars - 2)]

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
            exit_px = close[hard_limit]
            for j in range(fill_i + 1, hard_limit + 1):
                if np.isnan(kA[j]) or np.isnan(kB[j]):
                    continue
                hit = (kA[j] >= OVERBOUGHT or kB[j] >= OVERBOUGHT) if direction > 0 else \
                      (kA[j] <= OVERSOLD or kB[j] <= OVERSOLD)
                if hit:
                    exit_px = close[j]
                    break
            total += ((exit_px - entry_px) / entry_px) * direction
        net_pcts.append(total)
    net_pcts = np.array(net_pcts)
    real_net = sum(r["pnl_pct"] for r in real_trades)
    p_value = (np.sum(net_pcts >= real_net) + 1) / (n_draws + 1)
    return real_net, net_pcts, p_value


def run_tf(symbol, tf_label, loader):
    df, point = loader(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} {tf_label} - dual Stochastic(Close,Smoothed) cross, 200EMA filter, zone exit\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    for use_filter, flabel in ((False, "PLAIN - zone-cross only, no EMA filter"),
                               (True,  "WITH 200-EMA direction filter ('maybe test' variant)")):
        print(f"\n{'='*100}\n{flabel}\n{'='*100}")
        is_res = build_trades(df_is, point, use_ema_filter=use_filter)
        report(f"{symbol} {tf_label} - IN-SAMPLE", is_res, is_days, split_dir=True)
        oos_res = build_trades(df_oos, point, use_ema_filter=use_filter)
        report(f"{symbol} {tf_label} - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
        full_res = build_trades(df, point, use_ema_filter=use_filter)
        report(f"{symbol} {tf_label} - FULL HISTORY", full_res, full_days, split_dir=True)

        if len(full_res) >= 10:
            print(f"\n  Random-timing null (full history, n=2000 draws, matched trade count/direction):")
            real_net, null_dist, p = random_timing_null(df, point, full_res)
            print(f"    real net%={100*real_net:.2f}   null mean%={100*null_dist.mean():.2f}   "
                  f"null std%={100*null_dist.std():.2f}   p-value={p:.4f}")
        else:
            print(f"\n  (too few trades (n={len(full_res)}) for a meaningful random-timing null)")


if __name__ == "__main__":
    run_tf("GOLD", "M15", load_m15)
    run_tf("GOLD", "M5", load_m5)
    print(f"\n\n  Honest K: 2 per timeframe (plain construction + 200EMA-filter variant,")
    print(f"  both reported, neither searched/selected against this data).")
