"""
Per direct feedback that the exit mechanism (not just the entry) might be
the wrong piece - tests several genuinely different exit ideas on the SAME
entry (Scenario A: 21/50 cross confirmed above VWAP and 200-EMA, buy only -
the least-bad entry of everything tried tonight). Isolates the exit as the
only variable, same discipline as the earlier VWAP-open research line's
exit comparison.

Four exits compared, all real-time valid (no lookahead):
  1. ATR trailing stop on CLOSE (already tested - the baseline/reference).
  2. Momentum-loss: close back below the 21-EMA (the faster MA) - exit
     immediately, no trailing distance at all.
  3. Momentum-loss: close back below the 50-EMA (slower, already used
     elsewhere in this project as a stable trail reference).
  4. Chandelier-style trailing stop on the HIGHEST HIGH since entry (not
     highest close) minus ATR*mult - gives the trade more room on wicks,
     tighter on the close-based measure that drove the baseline.

Same real GOLD_M15_native.csv, real spread, IS/OOS split. New file -
honest K tracked independently per exit variant.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, session_vwap, GOLD_POINT

TIME_CAP_BARS = 200


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results, n_days=None):
    if not results:
        print(f"  {label}: n=0")
        return
    arr = np.array([r["pnl_pct"] for r in results])
    holds = np.array([r["hold_bars"] for r in results]) * 0.25
    reasons = {}
    for r in results:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    rtxt = ", ".join(f"{k}:{v}" for k, v in reasons.items())
    pm = f"  (~{len(results)/(n_days/30.44):.1f}/mo)" if n_days else ""
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  %PF={pct_pf(results):6.3f}  "
          f"net%={100*arr.sum():7.2f}  avg_hold={holds.mean():5.1f}h  [{rtxt}]{pm}")


def _entries(df):
    """Shared Scenario A entry list: (entry_i, fill_i) pairs."""
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)
    n = len(df)
    out = []
    i = 210
    while i < n - 1:
        if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(m200[i]) or np.isnan(vwap[i])
                or np.isnan(m21[i - 1]) or np.isnan(m50[i - 1])):
            i += 1
            continue
        crossed_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
        if crossed_up and close[i] > vwap[i] and m21[i] > vwap[i] and m50[i] > vwap[i] and close[i] > m200[i]:
            fill_i = i + 1
            if fill_i < n and not np.isnan(atr[fill_i]) and atr[fill_i] > 0:
                out.append((i, fill_i))
        i += 1
    return out, close, high, low, m21, m50, atr


def classify_ema_exit(df, which_ma, point=GOLD_POINT):
    entries, close, high, low, m21, m50, atr = _entries(df)
    ma = m21 if which_ma == 21 else m50
    spread = df["spread"].values
    n = len(df)
    results = []
    for entry_i, fill_i in entries:
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + sc
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)
        exit_i, exit_px, reason = None, None, None
        for k in range(fill_i + 1, hard_limit + 1):
            if np.isnan(ma[k]):
                continue
            if close[k] < ma[k]:
                exit_i, exit_px, reason = k, close[k], f"EMA{which_ma}"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
        pnl_pct = (exit_px - entry_px) / entry_px
        results.append(dict(entry_i=entry_i, exit_i=exit_i, pnl_pct=pnl_pct, reason=reason,
                             hold_bars=exit_i - fill_i))
    return results


def classify_chandelier_exit(df, trail_atr_mult, point=GOLD_POINT):
    entries, close, high, low, m21, m50, atr = _entries(df)
    spread = df["spread"].values
    n = len(df)
    results = []
    for entry_i, fill_i in entries:
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + sc
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)
        highest_high = high[fill_i]
        exit_i, exit_px, reason = None, None, None
        for k in range(fill_i, hard_limit + 1):
            if np.isnan(atr[k]) or atr[k] <= 0:
                continue
            if high[k] > highest_high:
                highest_high = high[k]
            trail = highest_high - trail_atr_mult * atr[k]
            if low[k] <= trail and k > fill_i:
                exit_i, exit_px, reason = k, trail, "CHAND"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
        pnl_pct = (exit_px - entry_px) / entry_px
        results.append(dict(entry_i=entry_i, exit_i=exit_i, pnl_pct=pnl_pct, reason=reason,
                             hold_bars=exit_i - fill_i))
    return results


if __name__ == "__main__":
    df = load_gold_m15()
    n = len(df)
    print(f"GOLD M15 real: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    print(f"{'#'*100}\nEXIT 2: close back below 21-EMA (fast momentum loss)\n{'#'*100}")
    is_res = classify_ema_exit(df_is, 21)
    report("IS", is_res, is_days)
    oos_res = classify_ema_exit(df_oos, 21)
    report("OOS", oos_res, oos_days)
    full_res = classify_ema_exit(df, 21)
    report("FULL", full_res, full_days)

    print(f"\n{'#'*100}\nEXIT 3: close back below 50-EMA (slower momentum loss)\n{'#'*100}")
    is_res = classify_ema_exit(df_is, 50)
    report("IS", is_res, is_days)
    oos_res = classify_ema_exit(df_oos, 50)
    report("OOS", oos_res, oos_days)
    full_res = classify_ema_exit(df, 50)
    report("FULL", full_res, full_days)

    print(f"\n{'#'*100}\nEXIT 4: chandelier trail on highest HIGH (not close) since entry\n{'#'*100}")
    grid = []
    for trail_m in (1.0, 1.5, 2.0, 2.5, 3.0):
        res = classify_chandelier_exit(df_is, trail_m)
        net = sum(r["pnl_pct"] for r in res) if res else -999
        grid.append((trail_m, len(res), net, pct_pf(res)))
        print(f"  trail={trail_m}:  n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}", flush=True)
    best = max(grid, key=lambda g: g[2])
    print(f"  IS winner: trail={best[0]}  (K={len(grid)})")
    oos_res = classify_chandelier_exit(df_oos, best[0])
    report("OOS", oos_res, oos_days)
    full_res = classify_chandelier_exit(df, best[0])
    report("FULL", full_res, full_days)

    print(f"\n\n  Honest K note: EMA21 exit=0 free params (K=1), EMA50 exit=0 free params (K=1),")
    print(f"  chandelier exit K={len(grid)}. Total K for this file: {len(grid)+2}. Same entry as")
    print(f"  Scenario A throughout - only the exit mechanism changes between these three tests.")


#+--------------------------------------------------------------------+
# EXIT 5 (added per direct request): Stochastic(21,5,5) momentum
# exhaustion. Entry still Scenario A (buy only). Exit when the
# stochastic, having reached overbought territory, rolls over - %K
# crosses back below %D after both were above the overbought threshold.
# This is the "leg wants to turn to come down again" signal described
# directly - not a price-level or MA-based exit at all, a momentum
# oscillator reading instead.
#+--------------------------------------------------------------------+
def stochastic(high, low, close, k_period=21, k_slow=5, d_period=5):
    n = len(close)
    lowest = pd.Series(low).rolling(k_period, min_periods=k_period).min().values
    highest = pd.Series(high).rolling(k_period, min_periods=k_period).max().values
    raw_k = np.full(n, np.nan)
    rng = highest - lowest
    valid = rng > 0
    raw_k[valid] = 100.0 * (close[valid] - lowest[valid]) / rng[valid]
    k_smoothed = pd.Series(raw_k).rolling(k_slow, min_periods=k_slow).mean().values
    d = pd.Series(k_smoothed).rolling(d_period, min_periods=d_period).mean().values
    return k_smoothed, d


def classify_stoch_exit(df, overbought_level, point=GOLD_POINT):
    entries, close, high, low, m21, m50, atr = _entries(df)
    spread = df["spread"].values
    n = len(df)
    stoch_k, stoch_d = stochastic(high, low, close, 21, 5, 5)
    results = []
    for entry_i, fill_i in entries:
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + sc
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)
        exit_i, exit_px, reason = None, None, None
        reached_overbought = False
        for k in range(fill_i, hard_limit + 1):
            if np.isnan(stoch_k[k]) or np.isnan(stoch_d[k]):
                continue
            if stoch_k[k] >= overbought_level:
                reached_overbought = True
            if reached_overbought and k > fill_i and stoch_k[k] < stoch_d[k]:
                exit_i, exit_px, reason = k, close[k], "STOCH"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
        pnl_pct = (exit_px - entry_px) / entry_px
        results.append(dict(entry_i=entry_i, exit_i=exit_i, pnl_pct=pnl_pct, reason=reason,
                             hold_bars=exit_i - fill_i))
    return results


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--stoch":
    df = load_gold_m15()
    n = len(df)
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    print(f"{'#'*100}\nEXIT 5: Stochastic(21,5,5) momentum exhaustion - exit when %K rolls\nover below %D after reaching overbought\n{'#'*100}")
    grid = []
    for ob in (70, 75, 80, 85):
        res = classify_stoch_exit(df_is, ob)
        net = sum(r["pnl_pct"] for r in res) if res else -999
        grid.append((ob, len(res), net, pct_pf(res)))
        print(f"  overbought={ob}:  n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}", flush=True)
    best = max(grid, key=lambda g: g[2])
    print(f"  IS winner: overbought={best[0]}  (K={len(grid)})")
    oos_res = classify_stoch_exit(df_oos, best[0])
    report("OOS", oos_res, oos_days)
    full_res = classify_stoch_exit(df, best[0])
    report("FULL", full_res, full_days)
