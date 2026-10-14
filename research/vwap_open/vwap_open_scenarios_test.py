"""
User's real observation (2026-10-14), formalized into two testable patterns:
not entering after a move is already overextended (the shared complaint about
every other system in this project) but trying to catch the move at the
moment price/21-EMA/50-EMA COMMIT relative to the session VWAP, early in the
session.

PATTERN 1 - "clean break, no lookback": price, 21-EMA and 50-EMA start
clustered near VWAP after the session reset, then all three separate to one
side beyond a buffer and never close back through VWAP for the rest of the
session.

PATTERN 2 - "pull away, snap back, cross together": an initial partial lean
to one side, then a reversal where price, 21-EMA AND 50-EMA all cross back
through VWAP to the OTHER side within a few bars of each other - the
"together" part is what's being tested as the real signal, not either line
alone.

Honest from the start: these thresholds (cluster distance, buffer, "within N
bars of each other") are design choices, not laws of nature - swept over a
small grid on IS only, the winning combination is then confirmed on
untouched OOS, exactly like every other search in this project. K = however
many combinations get checked, tracked honestly in the final report.

Session = midnight-reset window, matching SessionVWAP()'s own day-start
convention used throughout this project. "Early morning" = first 8 hours
(32 M15 bars) after reset - adjustable, this was a design choice made to
get a first result, not something the user specified down to the minute.

Real GOLD_M15_native.csv, clean-data window only (2014-06-13 onward - real
M15 data gotcha), real spread.
"""
import numpy as np
import pandas as pd

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")
GOLD_POINT = 0.01

WINDOW_BARS = 32          # 8h on M15 - "early morning hours"
HOLD_HOURS = 6            # how far forward we measure the outcome
HOLD_BARS = HOLD_HOURS * 4


def load_gold_m15():
    df = pd.read_csv(f"{DATA_DIR}/GOLD_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df


def ema(arr, period):
    out = np.full(len(arr), np.nan)
    alpha = 2.0 / (period + 1)
    out[period - 1] = np.mean(arr[:period])
    for i in range(period, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def wilder_atr(h, l, c, n=14):
    tr = np.zeros(len(c))
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    out = np.full(len(c), np.nan)
    out[n] = tr[1:n + 1].mean()
    for i in range(n + 1, len(c)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def session_vwap(df):
    """Vectorized, resets at each local-midnight day boundary - same
    construction as SessionVWAP() in the live EAs, just batch-computed."""
    typical = (df["high"].values + df["low"].values + df["close"].values) / 3.0
    vol = df["tick_volume"].values.astype(float) if "tick_volume" in df.columns else df["volume"].values.astype(float)
    day = df["time"].dt.date.values
    pv = typical * vol
    cum_pv = np.zeros(len(df))
    cum_v = np.zeros(len(df))
    run_pv, run_v, cur_day = 0.0, 0.0, None
    for i in range(len(df)):
        if day[i] != cur_day:
            cur_day = day[i]
            run_pv, run_v = 0.0, 0.0
        run_pv += pv[i]
        run_v += vol[i]
        cum_pv[i], cum_v[i] = run_pv, run_v
    vwap = np.where(cum_v > 0, cum_pv / cum_v, np.nan)
    return vwap


def classify_and_test(df, cluster_atr_mult, buffer_atr_mult, together_tol_bars):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)

    day = df["time"].dt.date.values
    minute_of_day = (df["time"].dt.hour * 60 + df["time"].dt.minute).values
    n = len(df)

    # index of each day's first bar (session start)
    day_start_idx = {}
    for i in range(n):
        if day[i] not in day_start_idx:
            day_start_idx[day[i]] = i

    results_p1, results_p2 = [], []

    for d, start_i in day_start_idx.items():
        end_i = min(start_i + WINDOW_BARS, n)
        if end_i - start_i < 10:
            continue
        # find the "clustered" bar: first bar in window where price/21/50 all
        # within cluster_atr_mult*ATR of VWAP
        cluster_i = None
        for i in range(start_i, end_i):
            if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(vwap[i]) or np.isnan(m21[i]) or np.isnan(m50[i]):
                continue
            tol = cluster_atr_mult * atr[i]
            if (abs(close[i] - vwap[i]) <= tol and abs(m21[i] - vwap[i]) <= tol
                    and abs(m50[i] - vwap[i]) <= tol):
                cluster_i = i
                break
        if cluster_i is None:
            continue

        # ---- PATTERN 1: clean break, no lookback ----
        resolve_i, direction = None, None
        for i in range(cluster_i + 1, end_i):
            if np.isnan(atr[i]) or atr[i] <= 0:
                continue
            buf = buffer_atr_mult * atr[i]
            above = (close[i] > vwap[i] + buf and m21[i] > vwap[i] + buf and m50[i] > vwap[i] + buf)
            below = (close[i] < vwap[i] - buf and m21[i] < vwap[i] - buf and m50[i] < vwap[i] - buf)
            if above or below:
                resolve_i, direction = i, (1 if above else -1)
                break
        if resolve_i is not None:
            # check no lookback through end of window
            no_lookback = True
            for j in range(resolve_i + 1, end_i):
                if direction > 0 and close[j] < vwap[j]:
                    no_lookback = False
                    break
                if direction < 0 and close[j] > vwap[j]:
                    no_lookback = False
                    break
            if no_lookback:
                exit_i = min(resolve_i + HOLD_BARS, n - 1)
                sc = spread[resolve_i + 1] * GOLD_POINT if resolve_i + 1 < n else 0
                entry_px = close[resolve_i] + (sc if direction > 0 else -sc)
                exit_px = close[exit_i]
                pnl_pct = ((exit_px - entry_px) / entry_px) * direction
                results_p1.append(dict(day=d, i=resolve_i, pnl_pct=pnl_pct, dir=direction))

        # ---- PATTERN 2: pull away, snap back, cross together ----
        # find first partial lean (one side, not all three required) after cluster
        lean_i, lean_dir = None, None
        for i in range(cluster_i + 1, end_i):
            if np.isnan(atr[i]) or atr[i] <= 0:
                continue
            buf = buffer_atr_mult * atr[i]
            if close[i] > vwap[i] + buf:
                lean_i, lean_dir = i, 1
                break
            if close[i] < vwap[i] - buf:
                lean_i, lean_dir = i, -1
                break
        if lean_i is None:
            continue
        # find the bar where ALL THREE have crossed to the OPPOSITE side,
        # each within together_tol_bars of the first of them to cross
        opp = -lean_dir
        cross_bars = {}
        for i in range(lean_i + 1, end_i):
            if np.isnan(atr[i]) or atr[i] <= 0:
                continue
            buf = buffer_atr_mult * atr[i]
            if "price" not in cross_bars and ((opp > 0 and close[i] > vwap[i] + buf) or
                                               (opp < 0 and close[i] < vwap[i] - buf)):
                cross_bars["price"] = i
            if "m21" not in cross_bars and ((opp > 0 and m21[i] > vwap[i] + buf) or
                                             (opp < 0 and m21[i] < vwap[i] - buf)):
                cross_bars["m21"] = i
            if "m50" not in cross_bars and ((opp > 0 and m50[i] > vwap[i] + buf) or
                                             (opp < 0 and m50[i] < vwap[i] - buf)):
                cross_bars["m50"] = i
            if len(cross_bars) == 3:
                break
        if len(cross_bars) == 3:
            bars = list(cross_bars.values())
            together_i = max(bars)
            if together_i - min(bars) <= together_tol_bars:
                exit_i = min(together_i + HOLD_BARS, n - 1)
                sc = spread[together_i + 1] * GOLD_POINT if together_i + 1 < n else 0
                entry_px = close[together_i] + (sc if opp > 0 else -sc)
                exit_px = close[exit_i]
                pnl_pct = ((exit_px - entry_px) / entry_px) * opp
                results_p2.append(dict(day=d, i=together_i, pnl_pct=pnl_pct, dir=opp))

    return results_p1, results_p2


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results):
    if not results:
        print(f"  {label}: n=0")
        return
    arr = np.array([r["pnl_pct"] for r in results])
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  "
          f"%PF={pct_pf(results):6.3f}  net%={100*arr.sum():7.2f}  avg%={100*arr.mean():6.3f}")


if __name__ == "__main__":
    df = load_gold_m15()
    n = len(df)
    print(f"GOLD M15 real: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()

    # ---- IS-only grid search over the design thresholds ----
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    print(f"{'='*100}\nIN-SAMPLE grid search (cluster tol / buffer / together-tolerance)\n{'='*100}")
    grid = []
    for cluster_m in (0.3, 0.5):
        for buf_m in (0.15, 0.25):
            for tol_bars in (2, 4):
                p1, p2 = classify_and_test(df_is, cluster_m, buf_m, tol_bars)
                net1 = sum(r["pnl_pct"] for r in p1) if p1 else -999
                net2 = sum(r["pnl_pct"] for r in p2) if p2 else -999
                grid.append((cluster_m, buf_m, tol_bars, len(p1), net1, pct_pf(p1), len(p2), net2, pct_pf(p2)))
                print(f"  cluster={cluster_m} buf={buf_m} tol={tol_bars}:  "
                      f"P1 n={len(p1):3d} net%={100*net1:7.2f} PF={pct_pf(p1):5.2f}   |   "
                      f"P2 n={len(p2):3d} net%={100*net2:7.2f} PF={pct_pf(p2):5.2f}")

    best_p1 = max(grid, key=lambda g: g[4])
    best_p2 = max(grid, key=lambda g: g[7])
    print(f"\n  IS winner for Pattern 1: cluster={best_p1[0]} buf={best_p1[1]} tol={best_p1[2]}")
    print(f"  IS winner for Pattern 2: cluster={best_p2[0]} buf={best_p2[1]} tol={best_p2[2]}")
    print(f"  Honest K = {len(grid)} combinations searched per pattern (8 each, 16 total)")

    # ---- confirm on untouched OOS ----
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation (last 30%, {df_oos['time'].iloc[0]} .. {df_oos['time'].iloc[-1]})\n{'='*100}")
    p1_oos, _ = classify_and_test(df_oos, best_p1[0], best_p1[1], best_p1[2])
    _, p2_oos = classify_and_test(df_oos, best_p2[0], best_p2[1], best_p2[2])
    report("Pattern 1 (clean break, no lookback) - OOS", p1_oos)
    report("Pattern 2 (pull away, snap back, cross together) - OOS", p2_oos)

    # also show each pattern's full-history number at its own IS-winning params
    p1_full, _ = classify_and_test(df, best_p1[0], best_p1[1], best_p1[2])
    _, p2_full = classify_and_test(df, best_p2[0], best_p2[1], best_p2[2])
    print(f"\n{'='*100}\nFull history at IS-winning params (for reference only, NOT the verdict)\n{'='*100}")
    report("Pattern 1 - FULL", p1_full)
    report("Pattern 2 - FULL", p2_full)
