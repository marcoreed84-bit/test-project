"""
"Silver Always Long + Macro Exit + Flush Protection v2" (CuriousMacroX) -
the user's fifth pasted script in this batch, EXPLICITLY named/tuned for
Silver (honored as this file's primary test). A long-only, mostly-always-
in-market POSITION system on DAILY bars (EMA(150)/EMA(75), 4.5%/8.0% one-
/two-day move thresholds - all clearly daily-bar-scale parameters, same
precedent as Golden Trident's D1 test): stay long unless (a) price falls
below a slow EMA ("trend exit"), (b) a "macro stress" filter derived from
DXY/US10Y breaking out above their own EMAs persists for N bars, or (c)
a "flush shock" (>4.5% one-day drop, >8% two-day drop, or an ATR-relative
range spike on a down day) fires - after a flush, re-entry is blocked
until price recovers above a faster EMA AND volatility calms down.

DISCLOSED LIMITATION (not silently dropped): this project's dataset has
NO DXY or US10Y series, so the (b) macro-stress filter CANNOT be tested
at all - useDxyExit is already False in the script's own defaults, and
useUs10yExit (default True) is forced OFF here for lack of data. Every
other rule (silver trend exit, flush-shock exit, flush-recovery re-entry
gate) uses only OHLC and is ported faithfully. This means the tested
system is strictly "always long silver except during a confirmed
downtrend or right after a volatility flush" - a smaller, purely price-
based subset of the original, not the full macro-aware system.

PORTED FAITHFULLY (on D1, resampled from M15 - lossless OHLC agg per
common.resample): the EMA(150) trend-exit test with its buffer, the exact
one-day/two-day move-percent flush thresholds and the ATR-relative range-
shock condition (rangePct > ATR% x mult AND close<open), the
barssince-flush cooldown + recovery-EMA-and-vol-calm re-entry gate
(f_persist ported as a rolling all-true window), and "enter only while
flat, exit closes the whole position" (naturally reproduced: sim_signals
already enforces one-trade-at-a-time, so passing every bar where the
state-independent part of entryCondition holds as a candidate signal and
letting the engine pick the first one after each exit is exactly
equivalent to Pine's own position_size==0 gating). No stop-loss/take-
profit anywhere in the original beyond the exit rules themselves -
modeled the same way as this session's other hold-until-exit-signal
systems (unreachable 50x-ATR safety stop, target_r=0).

GRID (K=27, literal): SILVER_SLOW_LEN in {100,150,200} x ONE_DAY_FLUSH_PCT
in {3.5,4.5,6.0} x ATR_SHOCK_MULT in {1.4,1.8,2.5}. recoveryLen=75,
twoDayFlushPct=8.0, flushCooldownBars=3, volCalmBars=2, atrLen=14 are the
script's own defaults, fixed to keep K honest. Long-only by construction.
Trade-count floors lowered to IS n>=15 / OOS n>=8 (Golden-Trident
precedent) since this is a low-frequency daily position system, not an
intraday one - flagged the same way, sample sizes will be small.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

SILVER_SLOW_LENS = [100, 150, 200]
ONE_DAY_FLUSH_PCTS = [3.5, 4.5, 6.0]
ATR_SHOCK_MULTS = [1.4, 1.8, 2.5]
RECOVERY_LEN = 75
TWO_DAY_FLUSH_PCT = 8.0
FLUSH_COOLDOWN_BARS = 3
VOL_CALM_BARS = 2
ATR_LEN = 14
NO_STOP_ATR_MULT = 50.0
MIN_IS_N, MIN_OOS_N = 15, 8


def rolling_all_true(cond, bars):
    """f_persist: True on bar i iff cond true on bars i, i-1, ..., i-bars+1."""
    c = cond.astype(np.int64)
    s = pd.Series(c).rolling(bars, min_periods=bars).sum().values
    return s == bars


def bars_since(cond):
    n = len(cond)
    out = np.full(n, np.inf)
    last = -1
    for i in range(n):
        if cond[i]:
            last = i
        out[i] = (i - last) if last >= 0 else np.inf
    return out


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    dfd = C.resample(df15, "1D")
    close, open_, high, low = dfd["close"].values, dfd["open"].values, dfd["high"].values, dfd["low"].values
    n = len(dfd)
    time_d = pd.to_datetime(dfd["time"]).values

    is_start, is_end = C.SPLITS[symbol]
    is_lo = int(np.searchsorted(time_d, np.datetime64(is_start)))
    is_hi = int(np.searchsorted(time_d, np.datetime64(is_end)))
    oos_lo, oos_hi = is_hi, n

    atr = C.wilder_atr(high, low, close, ATR_LEN)
    atr_pct = np.divide(atr, close, out=np.zeros(n), where=close != 0) * 100.0
    range_pct = np.divide(high - low, close, out=np.zeros(n), where=close != 0) * 100.0
    close_prev1 = np.concatenate(([np.nan], close[:-1]))
    close_prev2 = np.concatenate(([np.nan, np.nan], close[:-2]))
    one_day_move = np.divide(close, close_prev1, out=np.full(n, np.nan), where=close_prev1 != 0) - 1.0
    one_day_move *= 100.0
    two_day_move = np.divide(close, close_prev2, out=np.full(n, np.nan), where=close_prev2 != 0) - 1.0
    two_day_move *= 100.0

    recovery_ema = C.ema(close, RECOVERY_LEN)

    ema_cache = {sl: C.ema(close, sl) for sl in SILVER_SLOW_LENS}

    open_a = np.concatenate((open_, np.full(1, np.nan)))  # placeholder alignment guard (unused, kept simple)

    log(f"\n{'='*90}\n{symbol} D1 (resampled) -- Silver Always Long + Flush Protection (macro filter OMITTED: no "
        f"DXY/US10Y data) (SILVER_SLOW_LEN, ONE_DAY_FLUSH_PCT, ATR_SHOCK_MULT)\n"
        f"n={n} bars {pd.Timestamp(time_d[0])} -> {pd.Timestamp(time_d[-1])} | IS {pd.Timestamp(time_d[is_lo])} -> "
        f"{pd.Timestamp(time_d[is_hi-1])} ({is_hi-is_lo} bars) | OOS {pd.Timestamp(time_d[oos_lo])} -> "
        f"{pd.Timestamp(time_d[-1])} ({n-oos_lo} bars, untouched)")

    grid = list(itertools.product(SILVER_SLOW_LENS, ONE_DAY_FLUSH_PCTS, ATR_SHOCK_MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>={MIN_IS_N}\n{'='*90}")

    o_arr, h_arr, l_arr, c_arr = open_, high, low, close
    sp_arr = np.zeros(n)  # daily spread not tracked separately; use real spread via point-scaled M15 spread avg
    # use average M15 spread resampled to daily, already computed by common.resample as 'spread' mean (points)
    sp_pts = dfd["spread"].values if "spread" in dfd.columns else np.zeros(n)
    sp_arr = sp_pts * point

    rows = []
    cache = {}
    for cfg in grid:
        slow_len, flush_pct, shock_mult = cfg
        ema_slow = ema_cache[slow_len]
        below_slow = close < ema_slow
        one_day_flush = one_day_move <= -flush_pct
        two_day_flush = two_day_move <= -TWO_DAY_FLUSH_PCT
        atr_shock = (range_pct > atr_pct * shock_mult) & (close < open_)
        flush_now = np.nan_to_num(one_day_flush.astype(float) + two_day_flush.astype(float) + atr_shock.astype(float), nan=0.0) > 0

        bsf = bars_since(flush_now)
        flush_recently = bsf <= FLUSH_COOLDOWN_BARS
        vol_calm_now = range_pct <= atr_pct * shock_mult
        vol_calm_persist = rolling_all_true(vol_calm_now, VOL_CALM_BARS)
        flush_recovery_ready = (~flush_recently) | ((close > recovery_ema) & vol_calm_persist)

        exit_cond = np.nan_to_num(below_slow.astype(float), nan=0.0).astype(bool) | flush_now
        entry_cand = (~below_slow) & flush_recovery_ready

        il = np.where(entry_cand)[0]
        valid = ~np.isnan(atr[il]) & (atr[il] > 0)
        il = il[valid]
        dist_l = NO_STOP_ATR_MULT * atr[il]
        ex = dict(target_r=0.0, max_hold=100000, trail_atr=0.0, exit_long=exit_cond,
                  exit_short=np.zeros(n, dtype=np.bool_))
        exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
        r = C.sim_signals(il.astype(np.int64), np.ones(len(il)), dist_l, o_arr, h_arr, l_arr, c_arr, sp_arr, atr,
                          *exargs, is_lo, is_hi)
        n_tr, pnl = len(r[3]), r[3]
        cache[cfg] = (il, dist_l, ex)
        if n_tr < MIN_IS_N:
            continue
        rows.append(dict(cfg=cfg, n=n_tr, pf=C.pct_pf(pnl)))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>={MIN_IS_N}. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    il, dist_l, ex = cache[best["cfg"]]
    exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    r = C.sim_signals(il.astype(np.int64), np.ones(len(il)), dist_l, o_arr, h_arr, l_arr, c_arr, sp_arr, atr,
                      *exargs, oos_lo, oos_hi)
    oos_pnl, oos_dist = r[3], r[4]
    n_oos = len(oos_pnl)
    if n_oos == 0:
        log("No OOS trades."); return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (0 OOS trades)")
    oos_pf = C.pct_pf(oos_pnl)
    log(f"OOS (untouched): n={n_oos}  win%={100*(oos_pnl>0).mean():.1f}  %PF={oos_pf:.3f}  sum%={100*oos_pnl.sum():.1f}")
    if n_oos < MIN_OOS_N:
        log(f"Too few OOS trades (n<{MIN_OOS_N}) -> DOES NOT SURVIVE (insufficient evidence).")
        return dict(label=symbol, K=K, verdict=f"DOES NOT SURVIVE (n<{MIN_OOS_N})")

    class FakeBars:
        pass
    fb = FakeBars()
    fb.open, fb.high, fb.low, fb.close, fb.spread_px, fb.atr = o_arr, h_arr, l_arr, c_arr, sp_arr, atr
    fb.n = n
    allowed = np.ones(n, dtype=np.bool_)
    pool, p_fire, mean_n = C.random_pool(fb, oos_dist, n_oos, *exargs, oos_lo, oos_hi, allowed, p_long=1.0)
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = C.best_of_k_p(pool, oos_pf, K)
    log(f"random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={mean_n:.0f}): "
        f"median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{C.verdict(pK)}]")
    return dict(label=symbol, K=K, cfg=best["cfg"], is_n=best["n"], is_pf=best["pf"], oos_n=n_oos, oos_pf=oos_pf,
                pctile=pctile, p1=p1, pK=pK, verdict=C.verdict(pK) if p1 < 0.05 else C.verdict(max(p1, pK)))


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/silver_always_long_macro_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
