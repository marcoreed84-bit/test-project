"""
Per direct request: use the TradePanel signals together to try to
separate real stochastic signals from fake ones, instead of testing
each idea in isolation (every single-condition filter tonight failed:
MA stack x4 variants, reject, snapback, BB-width, tick-volume
pressure - this tries COMBINATIONS of them, since a single condition
failing doesn't rule out a combination working).

Four binary conditions computed at each baseline zone-cross stochastic
signal bar (GOLD M15, the richest/most-tested instrument tonight):
  A = EMA21/50/200 STACKED in the signal's own direction (not just a
      fresh transition - any bar where the stack already agrees)
  B = EMA21 REJECT in the signal's own direction within the last
      REJECT_LOOKBACK bars (price touched EMA21 and closed back on the
      signal's side - the chart-annotated idea)
  C = price (close) on the signal's own side of EMA21 (simple trend
      position, cheaper/different from A)
  D = Bollinger Band width in the top 40% of its own trailing
      distribution (the "bands further apart" idea)

Tests ALL 15 non-empty AND-combinations of {A,B,C,D} (4 singles + 6
pairs + 4 triples + 1 quad), reports %PF for each, with an HONEST
Sidak multiple-testing correction applied to whichever one looks best
(K=15, the actual number of combinations tried here - on top of
everything already tried tonight, this round's K is scoped to these
15 combos only, reported separately per CLAUDE.md's "K = the literal
number of configurations actually searched" rule for THIS search).

Same baseline zone-cross entry + validated swing-stop/1:2RR/opposite-
stoch-cross exit used throughout tonight. GOLD M15 only.
"""
import sys
import os
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from vwap_open_scenarios_test import ema
from stoch_ma_stack_gap_filter_test import wilder_atr
from stoch_bbwidth_filter_test import bollinger_width, rolling_percentile_rank, BB_PERIOD, BB_STD, BBWIDTH_LOOKBACK, BBWIDTH_PCTL_MIN

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST, EMA_MID, EMA_SLOW = 21, 50, 200
ATR_PERIOD = 14
REJECT_LOOKBACK = 5
TIME_CAP_BARS = 300
GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")


def load_m15():
    path = os.path.join(DATA_DIR, "GOLD_M15_native.csv")
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df, point


def build_trades(df, point, conds, which):
    """which: tuple of condition-name letters to require (AND), e.g. ('A','B')."""
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW, ATR_PERIOD + 1, BB_PERIOD + BBWIDTH_LOOKBACK) + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        trig_dir = 0
        if crossUp[i] and k[i] < ZONE_LOW:
            trig_dir = 1
        elif crossDown[i] and k[i] > ZONE_HIGH:
            trig_dir = -1
        if trig_dir == 0:
            i += 1
            continue

        ok = True
        for letter in which:
            if not conds[letter][i](trig_dir):
                ok = False
                break
        if not ok:
            i += 1
            continue

        dir_ = trig_dir
        swing = min(low[i - SWING_BARS:i]) if dir_ > 0 else max(high[i - SWING_BARS:i])
        risk = dir_ * (close[i] - swing)
        if risk <= 0.0:
            i += 1
            continue
        fill_i = i + 1
        if fill_i >= n:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
        stop_px = swing
        target_px = entry_px + dir_ * RR * risk
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if dir_ > 0 else (high[j] >= stop_px)
            target_hit = (high[j] >= target_px) if dir_ > 0 else (low[j] <= target_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if target_hit:
                exit_i, exit_px, reason = j, target_px, "TARGET"
                break
            if valid[j] and valid[j - 1]:
                opposite = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                if opposite:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-STOCH"
                    break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def pf_of(trades):
    if not trades:
        return 0.0, 0
    pnl = np.array([t["pnl_pct"] for t in trades])
    wins = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    return (wins / losses if losses > 0 else float("inf")), len(trades)


if __name__ == "__main__":
    df, point = load_m15()
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values

    e21_a = ema(close_a, EMA_FAST)
    e50_a = ema(close_a, EMA_MID)
    e200_a = ema(close_a, EMA_SLOW)
    atr_a = wilder_atr(high_a, low_a, close_a, ATR_PERIOD)
    width = bollinger_width(close_a, BB_PERIOD, BB_STD)
    pctl_rank = rolling_percentile_rank(width, BBWIDTH_LOOKBACK)

    def cond_A(i):
        def f(dir_):
            if np.isnan(e21_a[i]) or np.isnan(e50_a[i]) or np.isnan(e200_a[i]):
                return False
            return (e21_a[i] > e50_a[i] > e200_a[i]) if dir_ > 0 else (e21_a[i] < e50_a[i] < e200_a[i])
        return f

    def cond_B(i):
        def f(dir_):
            if np.isnan(e21_a[i]):
                return False
            lo = max(0, i - REJECT_LOOKBACK)
            for j in range(lo, i + 1):
                if np.isnan(e21_a[j]):
                    continue
                if dir_ > 0 and low_a[j] <= e21_a[j] and close_a[j] > e21_a[j]:
                    return True
                if dir_ < 0 and high_a[j] >= e21_a[j] and close_a[j] < e21_a[j]:
                    return True
            return False
        return f

    def cond_C(i):
        def f(dir_):
            if np.isnan(e21_a[i]):
                return False
            return (close_a[i] > e21_a[i]) if dir_ > 0 else (close_a[i] < e21_a[i])
        return f

    def cond_D(i):
        def f(dir_):
            pr = pctl_rank[i]
            return (not np.isnan(pr)) and pr >= BBWIDTH_PCTL_MIN
        return f

    # per-bar closures built once, indexed by i - cheap wrapper, actual
    # condition bodies above only read precomputed arrays, O(1)/O(lookback) per call
    conds = {
        "A": [cond_A(i) for i in range(n)],
        "B": [cond_B(i) for i in range(n)],
        "C": [cond_C(i) for i in range(n)],
        "D": [cond_D(i) for i in range(n)],
    }

    letters = ["A", "B", "C", "D"]
    combos = []
    for r in range(1, len(letters) + 1):
        combos.extend(itertools.combinations(letters, r))

    print(f"\n{'#'*100}\nGOLD M15 - combination filter search on zone-cross stochastic entry\n{'#'*100}")
    print(f"  A=EMA-stack-agrees  B=EMA21-reject-within-{REJECT_LOOKBACK}bars  C=price-on-trend-side-of-EMA21  D=BB-width-top40pct")
    print(f"  Testing all {len(combos)} non-empty AND-combinations. Honest K={len(combos)} for this search.\n")

    base_trades = build_trades(df, point, conds, ())
    base_pf, base_n = pf_of(base_trades)
    print(f"  BASELINE (no filter): n={base_n}  PF={base_pf:.3f}\n")

    rows = []
    for combo in combos:
        trades = build_trades(df, point, conds, combo)
        pf, cnt = pf_of(trades)
        rows.append((combo, pf, cnt))

    rows.sort(key=lambda r: -r[1])
    print(f"  {'combo':<10}{'n':>8}{'PF':>10}")
    for combo, pf, cnt in rows:
        print(f"  {'+'.join(combo):<10}{cnt:>8}{pf:>10.3f}")

    best_combo, best_pf, best_n = rows[0]
    print(f"\n  Best: {'+'.join(best_combo)}  n={best_n}  PF={best_pf:.3f}")
    print(f"  Honest K={len(combos)} for this combination search (on top of everything")
    print(f"  else tried tonight) - any claim of significance on the best result here")
    print(f"  needs its own random-timing null test at that K, not just a high PF.")
