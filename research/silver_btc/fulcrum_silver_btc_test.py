"""
Cross-asset transfer of Fulcrum (FROZEN gold parameters) to SILVER and BTCUSD.

Why this exists: research/fulcrum/fulcrum_random_timing_test.py gave Fulcrum
its first-ever rigor test on gold. Fulcrum_M15_EA.mq5 SURVIVED its own
file-count K=7 there (%PF 1.461, p(K=1)=0.004, p(K=7)=0.028; borderline at
K=30); Fulcrum_EA.mq5 (M5) was borderline at K=7 (p=0.055). So, as with
Vanguard/Ratchet/Meridian, the frozen shipped construction is run unchanged
on each other instrument. Nothing is searched in this file, so every Silver/
BTC bar is untouched by this construction; results are also reported on
research/silver_btc/common.py's fixed OOS windows (SILVER 2021+, BTCUSD 2024+
- BTC's 2018-2020 broker spread was 3-5x an M15 bar's median range, see
common.py), which is where the verdict is taken.

CONSTRUCTION: research/fulcrum/engine.py build_context + sim.simulate, the
same validated replica the gold test used (Aurelius-style ALIGN_MID gate, 50-
EMA structural stop +0.15xATR, fixed target, Friday 22:00 flatten, 5-bar
cooldown, US-holiday/DST-gap calendar exactly as the EA computes it).

INSTRUMENT PORTING - every gold-only constant found and handled:
  * POINT: sim.py reads module-global POINT (GOLD's 0.01) for spread-to-price
    conversion; it is set from each CSV's own meta_point (SILVER 0.001,
    BTCUSD 0.01, asserted by common.load_m15 / load_m5 here).
  * InpMaxSpreadPoints=60 is RAW GOLD POINTS (2.0x GOLD's median spread of
    30). Scaled to 2.0x the instrument's own median spread.
  * InpFixedTargetUSD=45 is a GOLD PRICE DISTANCE ($45 at 0.01 lots) -
    meaningless on Silver ($20-60/oz: bigger than the whole price) or BTC
    (0.05% of price). Re-expressed two ways, both derived ONLY from the gold
    trades (no Silver/BTC fitting):
      primary  target_pct = 45 / median gold entry price of the real gold
                            trades (M15: 1.72% of price; M5: 1.86%)
      sensitivity target_atr = median(45 / entry ATR) of the gold trades
                            (M15: 10.9 x ATR; M5: 22.5 x ATR)
  * D1 S/R levels come from H4 resampled from the same instrument's bars.

RANDOM NULL: fulcrum_random_timing_test.random_ctx - coin-flip direction at a
calibrated rate, all signal filters pass, stop placed at a D x ATR distance
drawn from the real trades' own stop distribution; target, stop handling,
Friday flatten and practical gates identical. %PF = pnl / entry_price.
K = 7 (Fulcrum's gold K - frozen transfer adds no search); K=30 also shown.
A system whose own %PF <= 1 does NOT survive regardless of the null.
"""
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/fulcrum")
sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import engine as E  # noqa: E402
import sim as S     # noqa: E402
import fulcrum_random_timing_test as FR  # noqa: E402
import common as C  # noqa: E402

TARGETS = {"M15": dict(pct=45.0 / 2612.34, atr=10.8776), "M5": dict(pct=45.0 / 2413.47, atr=22.4757)}
K_REAL = 7
N_RANDOM = 600
_G = {}


def load(sym, tf):
    if tf == "M15":
        return C.load_m15(sym)
    path = f"{C.DATA_DIR}/{sym}_M5.csv"
    point = float(C.read_meta(path)["meta_point"])
    assert abs(point - C.EXPECTED_POINT[sym]) < 1e-12, (sym, point)
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True), point


def pct(tr, lo, hi):
    tr = [t for t in tr if lo <= t["entry_i"] < hi]
    return FR.pct_arr(tr), tr


def _rand(args):
    seed, p_fire, lo, hi = args
    ctx, P, pool = _G["ctx"], _G["P"], _G["dist"]
    rng = np.random.default_rng(seed)
    return pct(FR.run_random(ctx, P, rng, p_fire, pool), lo, hi)[0]


def _init(ctx, P, dist, point):
    _G.update(ctx=ctx, P=P, dist=dist)
    S.POINT = point


def evaluate(sym, tf, tmode, workers=3):
    df, point = load(sym, tf)
    S.POINT = point
    h4 = C.resample(df, "4h")
    med = float(df["spread"].median())
    P = dict(E.P15 if tf == "M15" else E.P)
    P["max_spread_points"] = int(round(2.0 * med))
    P["target_pct" if tmode == "pct" else "target_atr"] = TARGETS[tf][tmode]
    ctx = E.build_context(df, h4, P)
    n = ctx["n"]
    oos_lo = int(np.searchsorted(df["time"].values, np.datetime64(C.SPLITS[sym][1])))
    real = S.simulate(ctx, params=P)
    tag = f"{sym} {tf} target={tmode}({TARGETS[tf][tmode]:.4f})"
    print("=" * 100)
    print(f"{tag}: {df['time'].iloc[0]} -> {df['time'].iloc[-1]} n={n}, point={point}, median spread {med:.0f} pts "
          f"-> max_spread gate {P['max_spread_points']} pts; OOS window from {df['time'].iloc[min(oos_lo, n-1)]}")
    rows = []
    for wname, lo in (("FULL", 0), ("OOS", oos_lo)):
        ra, rt = pct(real, lo, n)
        if len(ra) < 20:
            print(f"  [{wname}] n={len(ra)} - too few trades -> DOES NOT SURVIVE (insufficient evidence)")
            rows.append(dict(tag=tag, w=wname, n=len(ra), verdict="DOES NOT SURVIVE (n<20)"))
            continue
        rpf = FR.pct_pf(ra)
        longf = float(np.mean([t["dir"] > 0 for t in rt]))
        reasons = pd.Series([t["reason"] for t in rt]).value_counts().to_dict()
        dist = np.array([abs(t["entry_px"] - t["stop0"]) / t["entry_atr"] for t in rt])
        with Pool(workers, initializer=_init, initargs=(ctx, P, dist, point)) as pp:
            p_fire = 3.0 * len(ra) / (n - lo)
            for it in range(8):
                m = np.mean([len(x) for x in pp.map(_rand, [(10_000 + it * 10 + r, p_fire, lo, n) for r in range(6)])])
                if m <= 0:
                    p_fire *= 3; continue
                if abs(m - len(ra)) / len(ra) < 0.03:
                    break
                p_fire = min(0.95, p_fire * len(ra) / m)
            outs = pp.map(_rand, [(s, p_fire, lo, n) for s in range(N_RANDOM)])
        pool = np.array([FR.pct_pf(a) for a in outs]); pool = pool[np.isfinite(pool)]
        p1 = float((pool >= rpf).mean())
        pK, _ = FR.best_of_k(pool, rpf, K_REAL)
        p30, _ = FR.best_of_k(pool, rpf, 30)
        v = FR.verdict(max(p1, pK))
        if rpf <= 1.0:
            v = "DOES NOT SURVIVE (net loser" + (", beats random)" if p1 < 0.05 else ")")
        print(f"  [{wname}] n={len(ra)} win%={100*(ra>0).mean():.1f} sum%={100*ra.sum():.1f} %PF={rpf:.3f} "
              f"long%={100*longf:.0f} exits={reasons}")
        print(f"         null ({len(pool)} draws, mean n={np.mean([len(a) for a in outs]):.0f}): median="
              f"{np.median(pool):.3f} p95={np.percentile(pool, 95):.3f} -> {100*(pool<rpf).mean():.1f}th pct; "
              f"p(K=1)={p1:.4f} p(K={K_REAL})={pK:.4f} p(K=30)={p30:.4f}  => {v}")
        rows.append(dict(tag=tag, w=wname, n=len(ra), pf=rpf, pct=100 * (pool < rpf).mean(), p1=p1, pK=pK,
                         p30=p30, verdict=v))
    return rows


if __name__ == "__main__":
    tfs = sys.argv[1:] or ["M15", "M5"]
    allrows = []
    for tf in tfs:
        for sym in ("SILVER", "BTCUSD"):
            for tmode in ("pct", "atr"):
                allrows += evaluate(sym, tf, tmode)
    print("\nSUMMARY (verdict taken on the OOS window; FULL shown for context)")
    for r in allrows:
        if "pf" in r:
            print(f"  {r['tag']:<42} {r['w']:<4} n={r['n']:>5} %PF={r['pf']:.3f} pct={r['pct']:.1f} "
                  f"p1={r['p1']:.4f} p7={r['pK']:.4f} p30={r['p30']:.4f} -> {r['verdict']}")
        else:
            print(f"  {r['tag']:<42} {r['w']:<4} n={r['n']:>5} -> {r['verdict']}")
