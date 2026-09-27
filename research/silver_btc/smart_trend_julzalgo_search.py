"""
"Smart Trend Strategy | julzALGO" - a script the earlier conversation
summary MISSED (found by re-checking the pre-compaction transcript; it
was pasted between "UT Bot v2" and "XAUUSD 15m UT Bot+ADX" in this same
batch). The most elaborate construction in this batch: KAMA (Kaufman
Adaptive MA, ER length 20/fast 5/slow 30) smoothed further by a scalar
Kalman filter (process noise 1e-4, measurement noise 1e-2) for direction
(signalTrend flips on the Kalman line's own up/down tick), gated by
BOS/CHoCH market structure (pivot length 10, "Close" break mode, a
pivot level can only be broken ONCE - "highTaken"/"lowTaken" - until a
fresh pivot replaces it) that must be "recent" (within syncBars=10 bars
of the KAMA/Kalman flip, entryConfirm="BOS or CHoCH" default). Stop-loss
mode="ATR" (close -/+ 3x ATR(14)), and a STRUCTURALLY ASYMMETRIC risk:
reward - longRR=2.0, shortRR=1.0 (both script defaults, not a mistake).

DROPPED, DISCLOSED, OUT OF SCOPE: useBacktestWindow=true / backtestDays=7
filters entries to `time >= timenow - 7 days` - i.e. the last 7 days of
REAL WALL-CLOCK time from whenever the indicator happens to be evaluated,
not a trading rule at all (a TradingView "don't replay the whole chart"
convenience toggle). Reproducing it literally would exclude virtually
this entire historical dataset for reasons that have nothing to do with
the strategy's logic; forced OFF here (inBacktestWindow=True always).

DISCLOSED SIMPLIFICATION (structural, not optional): longRR != shortRR
means a single combined trade sequence would need a PER-TRADE target_r,
which this engine's sim_signals doesn't support (target_r is one scalar
per simulation call). Long and short trades are therefore simulated
SEPARATELY (their own one-at-a-time sequences, own target_r, own
"opposite valid signal closes this side" exit array - exactly reproducing
closeOnOppositeSignal via exit_long=validShortSignal / exit_short=
validLongSignal) and their P&L arrays are POOLED afterward for %PF - the
same statistic, at the cost of not reproducing the exact instant a
long-side close triggered by a fresh short signal precedes that short's
own fill (a second-order timing detail, not an economics difference).
The random-timing null is pooled the identical way (a long-only draw at
target_r=2.0 concatenated with an independent short-only draw at
target_r=1.0, trade counts calibrated to each side's own real count).

PORTED FAITHFULLY: the exact KAMA/Kalman recursion (both are pure
state recursions - the Kalman gain sequence k[i] does not even depend on
price, only on the two noise constants, so it's precomputed once), the
BOS/CHoCH pivot-break/one-shot-per-pivot logic, and the sync-window
entry-confirmation modes.

GRID (K=27, literal): STOP_ATR_MULT in {1.5,3.0,4.5} x SYNC_BARS in
{5,10,20} x ENTRY_CONFIRM in {"BOS or CHoCH","BOS Only","CHoCH Only"}.
KAMA/Kalman params, pivotLen=10, breakMode="Close", slMode="ATR",
longRR=2.0/shortRR=1.0 are the script's own defaults, fixed to keep K
honest.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

STOP_ATR_MULTS = [1.5, 3.0, 4.5]
SYNC_BARS_LIST = [5, 10, 20]
ENTRY_CONFIRMS = ["bos_or_choch", "bos_only", "choch_only"]
ER_LEN, FAST_LEN, SLOW_LEN = 20, 5, 30
PROCESS_NOISE, MEAS_NOISE = 0.0001, 0.01
PIVOT_LEN = 10
ATR_LEN = 14
LONG_RR, SHORT_RR = 2.0, 1.0
MIN_IS_N, MIN_OOS_N = 100, 20


def compute_kama(src, er_len, fast_len, slow_len):
    n = len(src)
    diff1 = np.abs(np.diff(src, prepend=src[0]))
    volatility = pd.Series(diff1).rolling(er_len, min_periods=er_len).sum().values
    change = np.abs(src - np.concatenate((np.full(er_len, np.nan), src[:-er_len])))
    with np.errstate(invalid="ignore", divide="ignore"):
        er = np.where(volatility != 0, change / volatility, 0.0)
    fast_sc = 2.0 / (fast_len + 1.0)
    slow_sc = 2.0 / (slow_len + 1.0)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    sc = np.nan_to_num(sc, nan=slow_sc ** 2)
    kama = np.empty(n)
    kama[0] = src[0]
    for i in range(1, n):
        kama[i] = kama[i - 1] + sc[i] * (src[i] - kama[i - 1])
    return kama


def compute_kalman(kama, process_noise, meas_noise):
    n = len(kama)
    p = 1.0
    k_seq = np.empty(n)
    for i in range(n):
        p += process_noise
        k = p / (p + meas_noise)
        k_seq[i] = k
        p = (1.0 - k) * p
    kalman = np.empty(n)
    kalman[0] = kama[0]
    for i in range(1, n):
        kalman[i] = kalman[i - 1] + k_seq[i] * (kama[i] - kalman[i - 1])
    return kalman


def compute_structure(close, ph, pl, pivot_len):
    n = len(close)
    bull_break = np.zeros(n, dtype=np.bool_)
    bear_break = np.zeros(n, dtype=np.bool_)
    bull_choch = np.zeros(n, dtype=np.bool_)
    bear_choch = np.zeros(n, dtype=np.bool_)
    bull_bos = np.zeros(n, dtype=np.bool_)
    bear_bos = np.zeros(n, dtype=np.bool_)

    last_high, last_low = np.nan, np.nan
    high_taken, low_taken = False, False
    structure_trend = 0

    for i in range(n):
        if not np.isnan(ph[i]):
            last_high = ph[i]; high_taken = False
        if not np.isnan(pl[i]):
            last_low = pl[i]; low_taken = False

        prev_close = close[i - 1] if i > 0 else close[i]
        bb = (not np.isnan(last_high)) and (not high_taken) and close[i] > last_high and prev_close <= last_high
        rb = (not np.isnan(last_low)) and (not low_taken) and close[i] < last_low and prev_close >= last_low

        bc = bb and structure_trend == -1
        rc = rb and structure_trend == 1
        bos_b = bb and not bc
        bos_r = rb and not rc

        bull_break[i], bear_break[i] = bb, rb
        bull_choch[i], bear_choch[i] = bc, rc
        bull_bos[i], bear_bos[i] = bos_b, bos_r

        if bb:
            high_taken = True
            structure_trend = 1
        if rb:
            low_taken = True
            structure_trend = -1

    return bull_break, bear_break, bull_choch, bear_choch, bull_bos, bear_bos


def last_event_bar(event):
    n = len(event)
    idx = np.arange(n)
    val = np.where(event, idx, -1)
    return np.maximum.accumulate(val)


def combined_random_pool(b, dist_pool_l, n_l, exargs_l, dist_pool_s, n_s, exargs_s, lo, hi, allowed,
                          n_draws=1000, seed0=0):
    def calibrate(p_long, dist_pool, target_n, exargs, seed_base):
        if target_n <= 0 or len(dist_pool) == 0:
            return 0.0
        args = (b.open, b.high, b.low, b.close, b.spread_px, b.atr, *exargs, lo, hi, allowed)
        p_fire = min(0.5, max(1e-6, target_n / max(1, allowed[lo:hi].sum()) * 3))
        for it in range(8):
            counts = [len(C.sim_random(seed_base + 10_000 + it * 10 + r, p_fire, p_long, dist_pool, *args))
                      for r in range(5)]
            m = np.mean(counts)
            if m <= 0:
                p_fire = min(0.5, p_fire * 3); continue
            if abs(m - target_n) / target_n < 0.03:
                break
            p_fire = min(0.5, max(1e-7, p_fire * target_n / m))
        return p_fire

    p_fire_l = calibrate(1.0, dist_pool_l, n_l, exargs_l, seed0 + 1_000_000)
    p_fire_s = calibrate(0.0, dist_pool_s, n_s, exargs_s, seed0 + 2_000_000)
    pool = []
    for r in range(n_draws):
        trl = (C.sim_random(seed0 + r, p_fire_l, 1.0, dist_pool_l, b.open, b.high, b.low, b.close, b.spread_px,
                            b.atr, *exargs_l, lo, hi, allowed) if n_l > 0 else np.array([]))
        trs = (C.sim_random(seed0 + 500_000 + r, p_fire_s, 0.0, dist_pool_s, b.open, b.high, b.low, b.close,
                            b.spread_px, b.atr, *exargs_s, lo, hi, allowed) if n_s > 0 else np.array([]))
        combined = np.concatenate([trl, trs])
        if len(combined) > 0:
            pool.append(C.pct_pf(combined))
    pool = np.array(pool)
    return pool[np.isfinite(pool)]


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    kama = compute_kama(b.close, ER_LEN, FAST_LEN, SLOW_LEN)
    kalman = compute_kalman(kama, PROCESS_NOISE, MEAS_NOISE)
    kalman_prev = np.concatenate(([kalman[0]], kalman[:-1]))
    trend_tick = np.where(kalman > kalman_prev, 1, np.where(kalman < kalman_prev, -1, 0))
    signal_trend = np.zeros(b.n, dtype=np.int64)
    cur = 0
    for i in range(b.n):
        if trend_tick[i] != 0:
            cur = trend_tick[i]
        signal_trend[i] = cur
    st_prev = np.concatenate(([0], signal_trend[:-1]))
    bull_flip = (signal_trend == 1) & (st_prev != 1)
    bear_flip = (signal_trend == -1) & (st_prev != -1)

    ph, pl = C.pivots(b.high, b.low, PIVOT_LEN)
    bull_break, bear_break, bull_choch, bear_choch, bull_bos, bear_bos = compute_structure(b.close, ph, pl, PIVOT_LEN)

    last_bull_flip_bar = last_event_bar(bull_flip)
    last_bear_flip_bar = last_event_bar(bear_flip)
    last_bull_bos_bar = last_event_bar(bull_bos)
    last_bear_bos_bar = last_event_bar(bear_bos)
    last_bull_choch_bar = last_event_bar(bull_choch)
    last_bear_choch_bar = last_event_bar(bear_choch)

    long_trigger = bull_flip | bull_bos | bull_choch
    short_trigger = bear_flip | bear_bos | bear_choch

    log(f"\n{'='*90}\n{symbol} M15 -- Smart Trend Strategy julzALGO, KAMA/Kalman+BOS/CHoCH, long RR=2.0/short RR=1.0 "
        f"pooled (STOP_ATR_MULT, SYNC_BARS, ENTRY_CONFIRM)\n{b.describe()}")

    grid = list(itertools.product(STOP_ATR_MULTS, SYNC_BARS_LIST, ENTRY_CONFIRMS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>={MIN_IS_N}\n{'='*90}")

    def build(cfg):
        stop_mult, sync_bars, econfirm = cfg
        rbb = (last_bull_flip_bar >= 0) & (last_bull_bos_bar >= 0) & (np.abs(last_bull_flip_bar - last_bull_bos_bar) <= sync_bars)
        rbc = (last_bull_flip_bar >= 0) & (last_bull_choch_bar >= 0) & (np.abs(last_bull_flip_bar - last_bull_choch_bar) <= sync_bars)
        rbb_s = (last_bear_flip_bar >= 0) & (last_bear_bos_bar >= 0) & (np.abs(last_bear_flip_bar - last_bear_bos_bar) <= sync_bars)
        rbc_s = (last_bear_flip_bar >= 0) & (last_bear_choch_bar >= 0) & (np.abs(last_bear_flip_bar - last_bear_choch_bar) <= sync_bars)
        if econfirm == "bos_only":
            long_ok, short_ok = rbb, rbb_s
        elif econfirm == "choch_only":
            long_ok, short_ok = rbc, rbc_s
        else:
            long_ok, short_ok = (rbb | rbc), (rbb_s | rbc_s)

        valid_long = (signal_trend == 1) & long_ok & long_trigger & ~np.isnan(b.atr) & (b.atr > 0)
        valid_short = (signal_trend == -1) & short_ok & short_trigger & ~np.isnan(b.atr) & (b.atr > 0)

        il = np.where(valid_long)[0]
        is_ = np.where(valid_short)[0]
        dist_l = stop_mult * b.atr[il]
        dist_s = stop_mult * b.atr[is_]
        exargs_l = (LONG_RR, 2000, 0.0, valid_short, np.zeros(b.n, dtype=np.bool_))
        exargs_s = (SHORT_RR, 2000, 0.0, np.zeros(b.n, dtype=np.bool_), valid_long)
        return il, dist_l, exargs_l, is_, dist_s, exargs_s

    rows = []
    cache = {}
    for cfg in grid:
        il, dist_l, exargs_l, is_, dist_s, exargs_s = build(cfg)
        rl = C.sim_signals(il.astype(np.int64), np.ones(len(il)), dist_l, b.open, b.high, b.low, b.close,
                           b.spread_px, b.atr, *exargs_l, b.is_lo, b.is_hi)
        rs = C.sim_signals(is_.astype(np.int64), -np.ones(len(is_)), dist_s, b.open, b.high, b.low, b.close,
                           b.spread_px, b.atr, *exargs_s, b.is_lo, b.is_hi)
        pnl = np.concatenate([rl[3], rs[3]])
        cache[cfg] = (il, dist_l, exargs_l, is_, dist_s, exargs_s)
        if len(pnl) < MIN_IS_N:
            continue
        rows.append(dict(cfg=cfg, n=len(pnl), pf=C.pct_pf(pnl)))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>={MIN_IS_N}. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    il, dist_l, exargs_l, is_, dist_s, exargs_s = cache[best["cfg"]]
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    rl = C.sim_signals(il.astype(np.int64), np.ones(len(il)), dist_l, b.open, b.high, b.low, b.close, b.spread_px,
                       b.atr, *exargs_l, b.oos_lo, b.oos_hi)
    rs = C.sim_signals(is_.astype(np.int64), -np.ones(len(is_)), dist_s, b.open, b.high, b.low, b.close, b.spread_px,
                       b.atr, *exargs_s, b.oos_lo, b.oos_hi)
    oos_pnl = np.concatenate([rl[3], rs[3]])
    n_oos_l, n_oos_s = len(rl[3]), len(rs[3])
    n_oos = n_oos_l + n_oos_s
    if n_oos == 0:
        log("No OOS trades."); return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (0 OOS trades)")
    oos_pf = C.pct_pf(oos_pnl)
    log(f"OOS (untouched): n={n_oos} (long={n_oos_l}, short={n_oos_s})  win%={100*(oos_pnl>0).mean():.1f}  "
        f"%PF={oos_pf:.3f}  sum%={100*oos_pnl.sum():.1f}")
    if n_oos < MIN_OOS_N:
        log(f"Too few OOS trades (n<{MIN_OOS_N}) -> DOES NOT SURVIVE (insufficient evidence).")
        return dict(label=symbol, K=K, verdict=f"DOES NOT SURVIVE (n<{MIN_OOS_N})")

    allowed = np.ones(b.n, dtype=np.bool_)
    pool = combined_random_pool(b, rl[4], n_oos_l, exargs_l, rs[4], n_oos_s, exargs_s, b.oos_lo, b.oos_hi, allowed)
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = C.best_of_k_p(pool, oos_pf, K)
    log(f"random-timing OOS null (pooled long+short, {len(pool)} draws): median={np.median(pool):.3f}  "
        f"p95={np.percentile(pool,95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{C.verdict(pK)}]")
    return dict(label=symbol, K=K, cfg=best["cfg"], is_n=best["n"], is_pf=best["pf"], oos_n=n_oos, oos_pf=oos_pf,
                pctile=pctile, p1=p1, pK=pK, verdict=C.verdict(pK) if p1 < 0.05 else C.verdict(max(p1, pK)))


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/smart_trend_julzalgo_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
