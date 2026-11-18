"""
EMA(84) / EMA(200) CROSSOVER - literal mechanical test of the user's visual
claim, 2026-11-18: "what i can see the crossing of the 200ema and the 84ema
do work".

THE ONE HYPOTHESIS (stated before any result was looked at):
  On the CLOSED bar i, if EMA(84) of close crosses ABOVE EMA(200) of close
  (EMA84[i] > EMA200[i] and EMA84[i-1] <= EMA200[i-1]) -> go LONG; if it
  crosses BELOW -> go SHORT. Exit on the OPPOSITE crossover, which is also
  the entry of the reverse trade (stop-and-reverse, always in the market).
  No other filter. EMA periods are the user's exact numbers, 84 and 200 -
  NOT swept (K=1 for the periods). EMA = standard exponential average,
  alpha = 2/(p+1), on close (common.ema; checked below against an explicit
  recursion and an MT5-style SMA-seeded EMA).

WHY THIS NEEDS AN OBJECTIVE TEST: the claim is visual/discretionary. On a
chart the crossovers that start a big trend are memorable and the many
whipsaw crosses in a range are not, so "I can see it works" is exactly the
kind of claim this project's discipline exists to check. Also: the user has
presumably been looking at RECENT charts, i.e. (part of) the 2021-2026 OOS
window. That window is untouched by THIS script's choices, but the
hypothesis itself may have been formed by eyeballing it - so the IS window
(Gold 2014-06-13 -> 2021, BTC 2021 -> 2024) is reported with its own null
too, and is if anything the cleaner blind test for Gold.

PRIOR WORK CHECKED FIRST (not duplicated):
  - Gold_Stoch_200EMA_EA.mq5 (+ research/gold_stoch_200ema/): 200 EMA used
    only as a buy-only trend FILTER (close > EMA200) for a Stochastic entry
    on the chart timeframe (M5) - no EMA-vs-EMA crossover anywhere in it.
  - btc_ema_cross_resplit.py: bare EMA cross on BTCUSD M15, grid FAST
    {10,20,30,50} x SLOW {100,150,200,300} x stop {2,3,4,5} ATR (K=64):
    DOES NOT SURVIVE (OOS %PF 0.92, p(K=1)=0.62). 84 was never in that grid,
    so the user's exact 84/200 pair is new; but "EMA-cross trend following
    on BTC M15" as a FAMILY has already failed once - noted, not re-used to
    tune anything here.
  - sma_20_200_bot_search.py: SMA20/200 regime + pullback entry, not a cross.
  No real MT5 ReportTester exists for any 84/200 crossover EA (no such EA
  exists), so there is nothing to bar-match: every number below is a
  SIMULATOR HYPOTHESIS TEST, not a verified-against-real-fills verdict.

TIMEFRAMES (pre-specified): the user named no timeframe. EMA(200)/EMA(84)
are commonly read on H1/H4 charts as "slow trend" lines, but nothing in the
claim pins it, so the test does not assume one: M15 (native), H1 and H4
(both resampled from M15, closed bars only - same resample_closed logic as
elliott_wave_mechanical_htf_search.py, generalised to H1). D1 is NOT tested
for performance: an 84/200 cross on D1 happens a couple of times a year, so
IS n>=100 is impossible; only its crossover COUNTS are printed (no %PF
looked at), and it is not counted in K.

EXIT VARIANTS (pre-specified, never tuned):
  E1 "SAR": exit = opposite crossover only (pure stop-and-reverse). PRIMARY.
  E2 "SAR+2ATR": same, plus an initial stop at 2.0 x ATR(14) from the
     signal-bar close - 2.0 copied from Gold_Stoch_200EMA_EA.mq5's own
     default AtrMultiplier, the repo's existing EMA-200 EA. After a stop-out
     the system is flat until the next crossover.

HONEST K: per instrument 3 timeframes x 2 exits = 6 literal configurations
(all six are reported - there is no "pick the best" step, so p(K=6) is the
correction for "does it work in ANY of the six forms on this instrument").
Across Gold + BTC, 12. p(K=1), p(K=6), p(K=12) (best-of-K bootstrap from the
null pool, common.best_of_k_p) and Sidak 1-(1-p1)^K are all printed.

DATA: point read from each CSV's own meta header (common.load_m15, asserted
GOLD=0.01, BTCUSD=0.01). GOLD_M15_native.csv trimmed at 2014-06-13 01:30
(EW.GOLD_REAL_M15_START) BEFORE any EMA or resample: the pre-2014 rows are
daily/hourly bars mislabeled as M15 with spread=0. SILVER: no Silver data of
any timeframe exists in this environment -> NOT RUN, no verdict.
Splits = common.SPLITS (fixed long before this script): GOLD IS
2014-06-13 -> 2021-01-01, OOS 2021-01-01 -> end; BTCUSD IS 2021-01-01 ->
2024-01-01, OOS 2024-01-01 -> end (pre-2021 BTC bars = EMA warm-up only).
EMA warm-up: no signal before bar 600 (3 x 200) of each series.

EXECUTION (common.py convention): signal on closed bar i fills at close[i]
+/- spread[i+1]*point (one spread per round trip, at entry); exits on the
opposite cross fill at that bar's close; the reverse trade enters on the
SAME bar's close (sim_trades allows i == last_exit, which common.sim_signals
does not - it would silently skip every reversal). %PF on pnl/entry_price.

NULLS (both with real spread, both matched on trade count):
  A. folder-standard random timing (common.random_pool): random bar, random
     direction, IDENTICAL exit machinery (exit on the next opposite cross /
     same 2-ATR stop), p_fire calibrated to the real OOS trade count.
     Supplementary: direction mix matched to the real trades.
  B. segment permutation (exposure-matched, the natural null for an
     always-in-market system): take the real trades' (gap-before, hold
     length, direction) triples, shuffle their ORDER, lay them back-to-back
     from the first real entry bar and price each with the identical
     _run_one (same stop for E2). Exactly the same trade count, the same
     hold-length distribution, the same long/short time exposure (so gold's
     2021-2026 drift cannot masquerade as timing skill) - only the
     alignment of the flips with price is destroyed.
  Verdict per config = C.verdict(max(p_A(K), p_B(K))) at K=6, OOS n>=20
  required (folder floor, not lowered). OOS n < 50 is flagged LOW POWER.
  FOUND ON FIRST RUN (disclosed, rule fixed before the verdict text was
  written; it does not change any verdict): for E1 (pure SAR) null A CANNOT
  be count-matched - a random-direction entry on the "wrong" side of the
  EMAs holds through TWO crossovers before its exit fires, so even at the
  p_fire cap the random count stays ~1/3 below the real one (e.g. 291 vs
  438). A null with fewer trades is more dispersed, i.e. too EASY to pass
  against. CLAUDE.md requires a count-matched null, so null A is excluded
  from the verdict whenever its mean count misses the real count by >10%
  (flagged "A n-MISMATCH"); null B is exactly count-matched by construction
  and carries the verdict alone in that case. For E2 null A matches
  (within ~5%) and the worse of A/B is used.

LOOKAHEAD / CORRECTNESS AUDIT (run before any verdict is trusted):
  (1) EMA check: common.ema vs an explicit recursion (max abs diff) and vs
      an MT5-style SMA-seeded EMA (share of crossover bars identical after
      the warm-up).
  (2) TRUNCATION: for up to 300 signals per series, recompute EMAs and
      crosses on close[:i+1] only; every signal prefix must be identical.
  (3) POSITIVE CONTROL: a deliberately leaky detector (EMAs shifted one bar
      into the future, i.e. "the still-forming bar's close") must FAIL (2)
      and shows what a leak does to IS %PF.
  (4) HTF RESAMPLE truncation: cut the M15 frame at the signal bar's close
      clock, rebuild H1/H4 bars from that alone, recompute; bars and signal
      prefix must be identical. Forming-bar positive control: clock inside
      bar i without the completeness filter must be DETECTED, and with the
      filter on, bar i must be absent.
  (5) Gold H4 vs native GOLD_H4.csv OHLC alignment over its overlap.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C
from common import _run_one, njit
import elliott_wave_mechanical_search as EW
import elliott_wave_mechanical_htf_search as EWH

FAST, SLOW = 84, 200
WARM = 3 * SLOW
TFS = {"M15": 15, "H1": 60, "H4": 240}
FLOOR = {"H1": "1h", "H4": "4h", "D1": "D"}
EXITS = {"E1_SAR": 0.0, "E2_SAR+2ATR": 2.0}     # initial stop in ATR(14) units; 0 = none
HUGE = 1e9                                        # "no stop" distance in ATR units
K_INSTR = len(TFS) * len(EXITS)                   # 6
K_ALL = 2 * K_INSTR                               # 12 (Gold + BTC)
OOS_MIN_N, LOW_POWER_N = 20, 50
N_AUDIT = 300
M15 = pd.Timedelta(minutes=15)


# ------------------------------------------------------------------ data

def load(symbol, log):
    df15, point = C.load_m15(symbol)
    if symbol == "GOLD":
        n0 = len(df15)
        df15 = df15[df15["time"] >= EW.GOLD_REAL_M15_START].reset_index(drop=True)
        log(f"[GOLD contamination filter] dropped {n0 - len(df15)} pre-{EW.GOLD_REAL_M15_START} rows "
            f"(daily/hourly bars mislabeled M15, spread=0) BEFORE any EMA/resample")
    return df15, point


def resample_closed(df15, tf, clock=None, drop_partial=True):
    """Same logic as EWH.resample_closed, generalised to H1. A window [T, T+L) is kept only if
    T+L <= clock (fully closed). drop_partial=False = the deliberate forming-bar BUG."""
    L = pd.Timedelta(minutes={"H1": 60, "H4": 240, "D1": 1440}[tf])
    if clock is None:
        clock = df15["time"].iloc[-1] + M15
    t = df15["time"]
    g = df15.groupby(t.dt.floor(FLOOR[tf]).values)
    out = pd.DataFrame(dict(open=g["open"].first(), high=g["high"].max(), low=g["low"].min(),
                            close=g["close"].last(), tick_volume=g["tick_volume"].sum(),
                            spread=g["spread"].mean()))
    out.index.name = "time"
    out = out.reset_index()
    if drop_partial:
        out = out[out["time"] + L <= clock]
    if len(out) and out["time"].iloc[0] < t.iloc[0]:
        out = out.iloc[1:]
    return out.reset_index(drop=True)


# ------------------------------------------------------------------ signal

def crosses(close, leaky=False):
    """up[i]/dn[i]: EMA84 crossed above/below EMA200 on CLOSED bar i, using only close[:i+1].
    leaky=True is the deliberate bug (EMAs one bar in the future) for the positive control."""
    ef, es = C.ema(close, FAST), C.ema(close, SLOW)
    if leaky:
        ef = np.append(ef[1:], np.nan); es = np.append(es[1:], np.nan)
    above = ef > es
    valid = np.isfinite(ef) & np.isfinite(es)
    prev_above = np.concatenate(([False], above[:-1]))
    prev_valid = np.concatenate(([False], valid[:-1]))
    ok = valid & prev_valid & (np.arange(len(close)) >= WARM)
    return (above & ~prev_above & ok), (~above & prev_above & ok)


def ema_loop(x, p):
    a = 2.0 / (p + 1.0); out = np.empty(len(x)); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def ema_mt5(x, p):
    a = 2.0 / (p + 1.0); out = np.full(len(x), np.nan); out[p - 1] = x[:p].mean()
    for i in range(p, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


# ------------------------------------------------------------------ simulation

@njit(cache=True)
def sim_trades(sig_bar, sig_dir, sig_dist, o, h, l, c, sp, atr, exl, exs, lo, hi):
    """Like common.sim_signals but a new entry is allowed ON the previous trade's exit bar
    (stop-and-reverse). Returns entry, exit, dir, pnl_pct."""
    n = len(c); m = len(sig_bar)
    eb = np.empty(m, np.int64); xb = np.empty(m, np.int64); dd = np.empty(m); pp = np.empty(m)
    cnt = 0; last_exit = -1
    for s in range(m):
        i = sig_bar[s]
        if i < lo or i >= hi or i < last_exit or i + 1 >= n:
            continue
        if not (atr[i] > 0):
            continue
        x, pnl = _run_one(i, sig_dir[s], sig_dist[s], o, h, l, c, sp, atr, n, 0.0, 10 ** 9, 0.0, exl, exs)
        eb[cnt] = i; xb[cnt] = x; dd[cnt] = sig_dir[s]; pp[cnt] = pnl
        cnt += 1; last_exit = x
    return eb[:cnt], xb[:cnt], dd[:cnt], pp[:cnt]


@njit(cache=True)
def sim_perm(seed, start, gaps, durs, dirs, stop_atr, o, h, l, c, sp, atr, nofire):
    """Null B: shuffle the real trades' (gap, hold, dir) triples, lay them out from `start`."""
    np.random.seed(seed)
    n = len(c); m = len(durs)
    order = np.random.permutation(m)
    out = np.empty(m); cnt = 0; pos = start
    for jj in range(m):
        j = order[jj]
        i = pos + gaps[j]
        if i + 1 >= n:
            break
        a = atr[i] if atr[i] > 0 else 1.0
        dist = stop_atr * a
        x, pnl = _run_one(i, dirs[j], dist, o, h, l, c, sp, atr, n, 0.0, max(1, durs[j]), 0.0, nofire, nofire)
        out[cnt] = pnl; cnt += 1; pos = x
    return out[:cnt]


def perm_pool(b, eb, xb, dd, stop_atr, n_draws=C.N_RANDOM, seed0=300_000):
    gaps = np.empty(len(eb), np.int64); gaps[0] = 0
    gaps[1:] = eb[1:] - xb[:-1]
    durs = (xb - eb).astype(np.int64)
    nofire = np.zeros(b.n, dtype=np.bool_)
    pool = np.array([C.pct_pf(sim_perm(seed0 + r, int(eb[0]), gaps, durs, dd.astype(np.float64), stop_atr,
                                       b.open, b.high, b.low, b.close, b.spread_px, b.atr, nofire))
                     for r in range(n_draws)])
    return pool[np.isfinite(pool)]


def p_block(pool, real):
    p1 = float((pool >= real).mean())
    out = dict(p1=p1, pct=100 * float((pool < real).mean()), med=float(np.median(pool)))
    for K in (K_INSTR, K_ALL):
        out[f"p{K}"], out[f"med{K}"] = C.best_of_k_p(pool, real, K)
        out[f"sidak{K}"] = 1 - (1 - p1) ** K
    return out


# ------------------------------------------------------------------ audits

def ema_check(close, log, tag):
    e1 = C.ema(close, SLOW); e2 = ema_loop(close, SLOW)
    up, dn = crosses(close)
    ef, es = ema_mt5(close, FAST), ema_mt5(close, SLOW)
    ab = ef > es; pa = np.concatenate(([False], ab[:-1]))
    idx = np.arange(len(close)) >= WARM
    up2, dn2 = ab & ~pa & idx, ~ab & pa & idx
    sig1 = set(np.where(up | dn)[0]); sig2 = set(np.where(up2 | dn2)[0])
    agree = len(sig1 & sig2) / max(1, len(sig1 | sig2))
    log(f"  [{tag}] EMA check: common.ema vs explicit recursion max|diff|={np.nanmax(np.abs(e1 - e2)):.2e}; "
        f"crossover bars identical to an MT5-style SMA-seeded EMA after warm-up: {100 * agree:.2f}% "
        f"({len(sig1)} vs {len(sig2)} crosses)")
    return agree > 0.99


def truncation_audit(close, up, dn, log, tag, leaky=False, seed=11):
    sig = np.where(up | dn)[0]
    rng = np.random.default_rng(seed)
    pick = rng.choice(sig, size=min(N_AUDIT, len(sig)), replace=False) if len(sig) else []
    bad = 0
    for i in pick:
        u, d = crosses(close[:i + 1], leaky=leaky)
        if not (np.array_equal(u, up[:i + 1]) and np.array_equal(d, dn[:i + 1])):
            bad += 1
    log(f"  [{tag}] truncation test on {len(pick)} signals (EMAs+crosses recomputed on close[:i+1] only): "
        f"mismatches={bad} -> {'PASS - no future dependence' if bad == 0 else 'FAIL - LOOKAHEAD'}")
    return bad == 0


def resample_audit(df15, tf, b, up, dn, log, seed=23):
    L = pd.Timedelta(minutes=TFS[tf])
    sig = np.where(up | dn)[0]
    rng = np.random.default_rng(seed)
    pick = rng.choice(sig, size=min(N_AUDIT, len(sig)), replace=False)
    t15 = df15["time"].values
    htime = pd.to_datetime(b.time)
    full = dict(open=b.open, high=b.high, low=b.low, close=b.close)
    fb = fs = det = nctl = absent = 0
    for i in pick:
        clock = htime[i] + L
        cut = int(np.searchsorted(t15, np.datetime64(clock), side="left"))
        h = resample_closed(df15.iloc[:cut], tf, clock=clock)
        if len(h) != i + 1 or not all(np.array_equal(h[c].values.astype(float), full[c][:i + 1]) for c in full):
            fb += 1; fs += 1; continue
        u, d = crosses(h["close"].values.astype(float))
        fs += not (np.array_equal(u, up[:i + 1]) and np.array_equal(d, dn[:i + 1]))
        lo15 = int(np.searchsorted(t15, np.datetime64(htime[i]), side="left"))
        inside = df15.iloc[lo15:cut]
        if len(inside) >= 2:
            kk = int(rng.integers(1, len(inside)))
            clock_in = inside["time"].iloc[kk]
            d_in = df15.iloc[:lo15 + kk]
            bug = resample_closed(d_in, tf, clock=clock_in, drop_partial=False)
            good = resample_closed(d_in, tf, clock=clock_in)
            nctl += 1
            det += len(bug) == i + 1 and not all(np.isclose(bug[c].iloc[i], full[c][i]) for c in ("high", "low", "close"))
            absent += len(good) == i
    ok = fb == 0 and fs == 0
    log(f"  [{tf}] RESAMPLE truncation: {len(pick)} signals, M15 cut at the signal bar's close clock, bars rebuilt -> "
        f"bar mismatches={fb}, signal mismatches={fs} ({'PASS' if ok else 'FAIL - LOOKAHEAD'}); forming-bar positive "
        f"control detected in {det}/{nctl}, bar correctly ABSENT with the filter on in {absent}/{nctl}")
    return ok


# ------------------------------------------------------------------ pipeline

def make_bars(df15, point, symbol, tf):
    if tf == "M15":
        return C.Bars(df15, point, symbol)
    return C.Bars(resample_closed(df15, tf), point, symbol)


def drift(b, lo, hi):
    return 100 * (b.close[hi - 1] / b.close[lo] - 1)


def run_config(b, up, dn, exit_name, log):
    stop_atr = EXITS[exit_name]
    sb = np.where(up | dn)[0].astype(np.int64)
    sd = np.where(up[sb], 1.0, -1.0)
    s_atr = HUGE if stop_atr == 0 else stop_atr
    sdist = s_atr * np.nan_to_num(b.atr[sb], nan=0.0)
    allowed = (np.arange(b.n) >= WARM) & np.isfinite(b.atr)
    pool_atr = np.array([s_atr])
    exl, exs = dn.astype(np.bool_), up.astype(np.bool_)
    res = dict(exit=exit_name)
    for side, lo, hi in (("IS", b.is_lo, b.is_hi), ("OOS", b.oos_lo, b.oos_hi)):
        eb, xb, dd, pnl = sim_trades(sb, sd, sdist, b.open, b.high, b.low, b.close, b.spread_px, b.atr, exl, exs, lo, hi)
        n = len(pnl); pf = C.pct_pf(pnl)
        res[f"{side}_n"], res[f"{side}_pf"] = n, pf
        if n == 0:
            log(f"   {exit_name} {side}: 0 trades"); continue
        hold = xb - eb
        long_time = hold[dd > 0].sum() / max(1, hold.sum())
        by_cross = sum(1 for e, x, d in zip(eb, xb, dd) if (exl[x] if d > 0 else exs[x]))
        lp, sp_ = pnl[dd > 0], pnl[dd < 0]
        log(f"   {exit_name} {side}: n={n}  win%={100 * (pnl > 0).mean():.1f}  %PF={pf:.3f}  sum%={100 * pnl.sum():.1f}  "
            f"long %PF={C.pct_pf(lp):.3f} (n={len(lp)}) short %PF={C.pct_pf(sp_):.3f} (n={len(sp_)}); median hold="
            f"{np.median(hold):.0f} bars; time long={100 * long_time:.0f}%; exits by opposite cross={by_cross}/{n}; "
            f"buy&hold over window={drift(b, lo, hi):+.1f}%")
        if n < OOS_MIN_N:
            log(f"   {exit_name} {side}: n={n} < {OOS_MIN_N} -> INSUFFICIENT DATA for a null comparison")
            res[f"{side}_verdict"] = "INSUFFICIENT DATA"; continue
        seed0 = 0 if side == "OOS" else 500_000
        poolA, p_fire, mean_n = C.random_pool(b, pool_atr, n, 0.0, 10 ** 9, 0.0, exl, exs, lo, hi, allowed, seed0=seed0)
        poolAd, _, _ = C.random_pool(b, pool_atr, n, 0.0, 10 ** 9, 0.0, exl, exs, lo, hi, allowed,
                                     p_long=float((dd > 0).mean()), seed0=seed0 + 900_000)
        poolB = perm_pool(b, eb, xb, dd, s_atr, seed0=seed0 + 300_000)
        A, B = p_block(poolA, pf), p_block(poolB, pf)
        pAd = float((poolAd >= pf).mean())
        log(f"      null A (random timing, same exit, real spread; {len(poolA)} draws, mean n={mean_n:.0f} vs {n}): "
            f"median={A['med']:.3f} p95={np.percentile(poolA, 95):.3f} -> real at {A['pct']:.1f}th pct; "
            f"p(K=1)={A['p1']:.4f} p(K={K_INSTR})={A[f'p{K_INSTR}']:.4f} p(K={K_ALL})={A[f'p{K_ALL}']:.4f} "
            f"[Sidak K={K_INSTR}: {A[f'sidak{K_INSTR}']:.4f}]; direction-matched p(K=1)={pAd:.4f}")
        log(f"      null B (segment permutation: same n, holds, directions, long-exposure; {len(poolB)} draws): "
            f"median={B['med']:.3f} p95={np.percentile(poolB, 95):.3f} -> real at {B['pct']:.1f}th pct; "
            f"p(K=1)={B['p1']:.4f} p(K={K_INSTR})={B[f'p{K_INSTR}']:.4f} p(K={K_ALL})={B[f'p{K_ALL}']:.4f} "
            f"[Sidak K={K_INSTR}: {B[f'sidak{K_INSTR}']:.4f}]")
        a_ok = abs(mean_n - n) / n <= 0.10
        if not a_ok:
            log(f"      NOTE: null A mean n={mean_n:.0f} misses real n={n} by >10% (structural for pure SAR) -> "
                f"A n-MISMATCH, excluded from the verdict; null B (exactly count-matched) carries it")
        pk = max(A[f"p{K_INSTR}"], B[f"p{K_INSTR}"]) if a_ok else B[f"p{K_INSTR}"]
        res[f"{side}_Aok"] = "ok" if a_ok else "MISM"
        res.update({f"{side}_pA1": A["p1"], f"{side}_pB1": B["p1"], f"{side}_pA6": A[f"p{K_INSTR}"],
                    f"{side}_pB6": B[f"p{K_INSTR}"], f"{side}_pA12": A[f"p{K_ALL}"], f"{side}_pB12": B[f"p{K_ALL}"],
                    f"{side}_pctA": A["pct"], f"{side}_pctB": B["pct"],
                    f"{side}_verdict": C.verdict(pk) + (" (LOW POWER)" if n < LOW_POWER_N else "")})
    return res


def run_symbol(symbol, log):
    df15, point = load(symbol, log)
    out = []
    audit_ok = True
    for tf in TFS:
        b = make_bars(df15, point, symbol, tf)
        up, dn = crosses(b.close)
        log(f"\n{'=' * 100}\n{symbol} {tf}{'' if tf == 'M15' else ' (resampled from M15, closed bars only)'} -- "
            f"EMA({FAST}) x EMA({SLOW}) crossover, stop-and-reverse\n{b.describe()}\npoint={point} (CSV meta header); "
            f"crosses IS={int((up | dn)[b.is_lo:b.is_hi].sum())} OOS={int((up | dn)[b.oos_lo:].sum())}; honest K: "
            f"{K_INSTR} per instrument, {K_ALL} across Gold+BTC\n{'=' * 100}")
        # ---- audits first
        ok = ema_check(b.close, log, tf)
        ok &= truncation_audit(b.close, up, dn, log, f"{tf} REAL")
        lu, ld = crosses(b.close, leaky=True)
        truncation_audit(b.close, lu, ld, log, f"{tf} LEAKY control (must FAIL)")
        lb = np.where(lu | ld)[0].astype(np.int64)
        lr = sim_trades(lb, np.where(lu[lb], 1.0, -1.0), HUGE * np.nan_to_num(b.atr[lb], nan=0.0), b.open, b.high,
                        b.low, b.close, b.spread_px, b.atr, ld, lu, b.is_lo, b.is_hi)
        log(f"  [{tf}] leaky positive control IS: n={len(lr[3])} %PF={C.pct_pf(lr[3]):.3f}  <- what a one-bar "
            f"forming-bar leak would look like (E1)")
        if tf != "M15":
            ok &= resample_audit(df15, tf, b, up, dn, log)
            if symbol == "GOLD" and tf == "H4":
                EWH.check_vs_native_h4(resample_closed(df15, "H4"), log)
        if not ok:
            log("  AUDIT FAILED -> results for this series NOT trustworthy")
            audit_ok = False
        for ex in EXITS:
            r = run_config(b, up, dn, ex, log)
            r.update(symbol=symbol, tf=tf, audit="PASS" if ok else "FAIL")
            out.append(r)
    # D1: crossover counts only (no performance looked at, not in K)
    d1 = C.Bars(resample_closed(df15, "D1"), point, symbol)
    u, d = crosses(d1.close)
    log(f"\n{symbol} D1 (count only, not tested, not in K): crosses IS={int((u | d)[d1.is_lo:d1.is_hi].sum())} "
        f"OOS={int((u | d)[d1.oos_lo:].sum())} -> far below any usable sample size")
    return out, audit_ok


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/ema84_200_crossover_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    allres = []
    for sym in ("GOLD", "SILVER", "BTCUSD"):
        if not os.path.exists(f"{C.DATA_DIR}/{sym}_M15_native.csv"):
            log(f"\n{'=' * 100}\n{sym}: no {sym} data of any timeframe in this environment -> NOT RUN (no verdict).")
            continue
        res, _ = run_symbol(sym, log)
        allres += res
    log(f"\n{'=' * 100}\nSUMMARY  (verdict = worse of null A / null B at honest K={K_INSTR} per instrument, null B alone where null A is "
        f"count-MISMATCHED; p at K={K_ALL} across both instruments also shown)\n{'=' * 100}")
    log(f"{'config':<28}{'audit':>6}{'IS n':>7}{'IS %PF':>8}{'IS pA1':>8}{'IS pB1':>8}{'OOS n':>7}{'OOS %PF':>9}"
        f"{'pA1':>8}{'pB1':>8}{'pA6':>8}{'pB6':>8}{'pA12':>8}{'pB12':>8}{'A n':>6}  OOS verdict")
    for r in allres:
        g = lambda k, f="{:.3f}": (f.format(r[k]) if k in r and r[k] == r[k] else "-")
        log(f"{r['symbol'] + ' ' + r['tf'] + ' ' + r['exit']:<28}{r['audit']:>6}{r['IS_n']:>7}{g('IS_pf'):>8}"
            f"{g('IS_pA1'):>8}{g('IS_pB1'):>8}{r['OOS_n']:>7}{g('OOS_pf'):>9}{g('OOS_pA1'):>8}{g('OOS_pB1'):>8}"
            f"{g('OOS_pA6'):>8}{g('OOS_pB6'):>8}{g('OOS_pA12'):>8}{g('OOS_pB12'):>8}{r.get('OOS_Aok', '-'):>6}  "
            f"{r.get('OOS_verdict', 'INSUFFICIENT DATA')}")
    log("SILVER: NOT RUN (no data in this environment).")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
