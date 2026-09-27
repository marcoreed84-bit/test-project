"""
Meridian RECONCILIATION + corrected cross-asset transfer test.

WHICH MODEL IS FAITHFUL TO Meridian_EA.mq5 (v1.07, the current shipped file)?
Read directly off the .mq5 (ManageOpenPosition / CheckForEntry / OnTick):
  entry : fresh 21/50 EMA cross on the just-closed M5 bar, close vs 250 SMA
          and vs the calendar-day VWAP both on the trade side, >= 0.50xATR from
          the 3 completed D1 bars' high/low, spread <= InpMaxSpreadPoints=60
          (RAW GOLD POINTS), market fill at the next bar's open, resting SL at
          2.5 x Wilder ATR(14).
  exit  : the next opposite 21/50 cross (REVERSAL, market at next open), the
          resting SL, or the Friday 22:00 flatten (tick-level). There is NO
          trailing stop, NO breakeven and NO take-profit in the shipped EA -
          InpUseGivebackExit exists but ships false (rejected 2026-09-25).
  order : `if(g_ticket != 0) ManageOpenPosition(); else CheckForEntry();` -
          NOT stop-and-reverse, and the bar after a broker-side SL fill is
          consumed by ManageOpenPosition (stale ticket), so a cross there is
          never traded.
research/meridian/msim.py models all of that and was bar-matched against the
EA's REAL MT5 reports (research/meridian/validate.py, ea_vs_python.py: full
history v1.00 msim 2546 trades / PF 1.244 vs REAL 2512 / PF 1.2437).
research/aurelius/m5_stack_variants_fixed_test.py's sim_filtered_entries()
(used by the earlier research/aurelius/meridian_silver_btc_test.py and
meridian_random_timing_test.py) is the pre-EA research model: stop-and-
reverse, no Friday flatten, no spread gate, no stale-ticket bar, fills at the
signal bar's close, shorts never pay the exit-side spread. msim.py is the
authoritative one. (Neither has a trailing stop or breakeven - the EA has
none to model.)

WHAT THIS FILE DOES - the same question the earlier file asked, on msim.py:
  1. GOLD  : msim V102 on the full GOLD M5 export, random-timing null,
             best-of-K with Meridian's own K=15 (the 15 meridian_*.py files
             the earlier gold test counted), K=30/50 also shown.
  2. SILVER: frozen V102, unchanged, on SILVER_M5.csv (2022-07 -> 2026-09).
  3. BTCUSD: frozen V102, unchanged, on BTCUSD_M5.csv (2023-11 -> 2026-09).
No parameter is searched anywhere in this file, so every Silver/BTC bar is
untouched out-of-sample for this construction (walk-forward trivially
satisfied: IS = gold, OOS = the other instrument).

INSTRUMENT PORTING (the bugs this project has already paid for):
  * point read from each CSV's own meta_point and asserted (SILVER 0.001,
    BTCUSD 0.01); msim.MP.point carries it (msim's module POINT is GOLD's).
  * InpMaxSpreadPoints=60 is a RAW GOLD-POINTS gate (= 2.0x GOLD M5's median
    spread of 30 pts). Left at 60 it would block most Silver entries and EVERY
    BTC entry (median 6000 pts). Primary run scales it to 2.0x the
    instrument's own median spread; a gate-OFF sensitivity is also shown.
  * Session quirks: Silver shares GOLD#'s broker session (hour-0 bars are
    rare DST-gap bars on both), so the 01:05 entry gate and hour-0 rejected-
    close quirk are kept. BTCUSD trades 24/7 (hour-0 is a normal hour), so
    both are switched off there.

RANDOM-TIMING NULL: msim.MP.entry_fn replaces the cross+confirm+VWAP+S/R
decision with a calibrated coin-flip entry; spread gate, Friday no-entry,
stale-ticket bar, 01:05 gate, the 2.5xATR stop, the REVERSAL exit on any
opposite 21/50 cross, and the Friday flatten are the identical msim code.
%PF = pnl / entry_price throughout (never raw points). A construction whose
own %PF is <= 1.0 is reported as DOES NOT SURVIVE even if it beats the random
null - on a high-cost instrument the null can be so cost-crushed that a
money-losing system still "beats random", which is not a tradeable edge.
"""
import sys
from dataclasses import replace
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/meridian")
sys.path.insert(0, "/home/user/test-project/research/ratchet")
import msim as M  # noqa: E402

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
EXPECTED_POINT = {"GOLD": 0.01, "SILVER": 0.001, "BTCUSD": 0.01}
GOLD_GATE_MULT = 60.0 / 30.0      # InpMaxSpreadPoints / GOLD M5 median spread
K_REAL = 15
N_RANDOM = 1000
A, B = pd.Timestamp("2000-01-01"), pd.Timestamp("2030-01-01")

_G = {}


def load_m5(sym):
    path = f"{DATA_DIR}/{sym}_M5.csv"
    with open(path) as f:
        meta = f.readline().strip().split(",")
    meta = {meta[i]: meta[i + 1] for i in range(0, len(meta) - 1, 2)}
    point = float(meta["meta_point"])
    assert abs(point - EXPECTED_POINT[sym]) < 1e-12, (sym, point)
    df = pd.read_csv(path, skiprows=1)
    df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]].copy()
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True), point


def params_for(sym, point, med_spread, gate="scaled"):
    if sym == "GOLD":
        return replace(M.V102)
    ms = 0 if gate == "off" else int(round(GOLD_GATE_MULT * med_spread))
    p = replace(M.V102, point=point, max_spread=ms)
    if sym == "BTCUSD":
        p = replace(p, entry_from_min=0, hour0_reject=False)
    return p


def pct(trades):
    return np.array([t["pnl"] / t["entry"] for t in trades])


def pct_pf(a):
    if len(a) == 0:
        return float("nan")
    gw = a[a > 0].sum(); gl = -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def _rand_run(args):
    seed, p_fire, p_long = args
    ctx, p = _G["ctx"], _G["p"]
    rng = np.random.default_rng(seed)
    n = len(ctx["c"])
    fire = rng.random(n) < p_fire
    dirs = np.where(rng.random(n) < p_long, 1, -1)
    ef = lambda c, t: int(dirs[t]) if fire[t] else 0  # noqa: E731
    tr, _ = M.simulate(ctx, replace(p, entry_fn=ef), A, B)
    return pct(tr), np.array([t["entry_i"] for t in tr])


def _init(ctx, p):
    _G["ctx"], _G["p"] = ctx, p


def verdict(p):
    return "SURVIVES" if p < 0.05 else ("borderline" if p < 0.15 else "DOES NOT SURVIVE")


def best_of_k(pool, real, K, seed=7):
    rng = np.random.default_rng(seed)
    b = pool[rng.integers(0, len(pool), size=(5000, K))].max(axis=1)
    return float((b >= real).mean()), float(np.median(b))


def evaluate(sym, gate="scaled", n_random=N_RANDOM, workers=3):
    df, point = load_m5(sym)
    med = float(df["spread"].median())
    p = params_for(sym, point, med, gate)
    ctx = M.build_ctx(df)
    n = len(df); cut = int(n * 0.7)
    print("=" * 96)
    print(f"{sym} M5 {df['time'].iloc[0]} -> {df['time'].iloc[-1]} ({n} bars) point={point} median spread={med:.0f} pts "
          f"({1e4 * np.median(df['spread'] * point / df['close']):.2f} bp of price)")
    print(f"  msim V102 frozen: max_spread={p.max_spread} pts (gate={gate}), entry_from_min={p.entry_from_min}, "
          f"hour0_reject={p.hour0_reject}, stop={p.stop_atr}xATR, Friday flatten {p.fri_close}:00")
    real, st = M.simulate(ctx, p, A, B)
    ra = pct(real); ei = np.array([t["entry_i"] for t in real])
    if len(ra) < 20:
        print(f"  n={len(ra)} trades - too few to evaluate. blocks: {st}")
        return dict(sym=sym, gate=gate, n=len(ra), verdict="DOES NOT SURVIVE (n<20)")
    real_pf = pct_pf(ra)
    from collections import Counter
    reasons = Counter(t["reason"] for t in real)
    print(f"  REAL: n={len(ra)} win%={100*(ra>0).mean():.1f} sum%={100*ra.sum():.1f} %PF={real_pf:.3f} | "
          f"first70% n={int((ei<cut).sum())} %PF={pct_pf(ra[ei<cut]):.3f} | last30% n={int((ei>=cut).sum())} "
          f"%PF={pct_pf(ra[ei>=cut]):.3f} | exits {dict(reasons)} | spread-blocked crosses {st['blk_spread']}")

    with Pool(workers, initializer=_init, initargs=(ctx, p)) as pool_:
        p_fire = len(ra) / n * 1.3
        for _ in range(8):
            ms = np.mean([len(x[0]) for x in pool_.map(_rand_run, [(10_000 + _ * 10 + r, p_fire, 0.5) for r in range(6)])])
            if ms <= 0:
                p_fire *= 3; continue
            if abs(ms - len(ra)) / len(ra) < 0.03:
                break
            p_fire = min(0.5, p_fire * len(ra) / ms)
        out = pool_.map(_rand_run, [(s, p_fire, 0.5) for s in range(n_random)])
        longf = float(np.mean([t["dir"] > 0 for t in real]))
        dout = pool_.map(_rand_run, [(900_000 + s, p_fire, longf) for s in range(n_random // 2)])
    pool = np.array([pct_pf(a) for a, _ in out]); ns = [len(a) for a, _ in out]
    pool = pool[np.isfinite(pool)]
    dpool = np.array([pct_pf(a) for a, _ in dout]); dpool = dpool[np.isfinite(dpool)]
    pctile = 100 * (pool < real_pf).mean(); p1 = float((pool >= real_pf).mean())
    print(f"  random-timing null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={np.mean(ns):.0f} vs real {len(ra)}): "
          f"median={np.median(pool):.3f} p95={np.percentile(pool, 95):.3f}")
    print(f"  REAL %PF={real_pf:.3f} -> {pctile:.1f}th percentile, p(K=1)={p1:.4f}")
    print(f"  (supplementary) direction-matched null p_long={longf:.2f}: median={np.median(dpool):.3f} "
          f"p(K=1)={float((dpool >= real_pf).mean()):.4f}")
    res = dict(sym=sym, gate=gate, n=len(ra), pf=real_pf, pctile=pctile, p1=p1)
    for K in (1, K_REAL, 30, 50):
        pk, mk = best_of_k(pool, real_pf, K)
        res[f"p{K}"] = pk
        print(f"    K={K:>3}: best-of-K median={mk:.3f} p={pk:.4f} [{verdict(pk)}]")
    res["verdict"] = verdict(max(p1, res[f"p{K_REAL}"]))
    if real_pf <= 1.0:
        # beating a cost-crushed random null is not survival for a system that loses money
        res["verdict"] = "DOES NOT SURVIVE (net loser, %PF<=1" + (", though it beats random timing)" if p1 < 0.05 else ")")
    print(f"  VERDICT: {res['verdict']}")
    return res


if __name__ == "__main__":
    which = sys.argv[1:] or ["GOLD", "SILVER", "BTCUSD", "SILVER:off", "BTCUSD:off"]
    rows = []
    for w in which:
        sym, _, gate = w.partition(":")
        rows.append(evaluate(sym, gate or "scaled", n_random=N_RANDOM if not gate else 500))
    print("\nSUMMARY (msim.py = the EA-faithful Meridian model; K_REAL=15)")
    for r in rows:
        if "pf" in r:
            print(f"  {r['sym']:<7} gate={r['gate']:<6} n={r['n']:>5} %PF={r['pf']:.3f} pctile={r['pctile']:.1f} "
                  f"p(K=1)={r['p1']:.4f} p(K=15)={r['p15']:.4f} -> {r['verdict']}")
        else:
            print(f"  {r['sym']:<7} gate={r['gate']:<6} n={r['n']} -> {r['verdict']}")
