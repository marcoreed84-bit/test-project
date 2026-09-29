"""
H&S on GOLD, "immediate chase" variant (use_pullback_entry=False) - same
EA-faithful hs_sim.py and exact same random-timing null methodology as
hs_gold_full_history_check.py (the script that confirmed the shipped
pullback-entry default survives: %PF=1.283, p(K=1)=0.01). This asks the
direct follow-up: the deterministic comparison showed immediate chase
makes MORE raw money on Gold (net +113.2% vs +77.8%) - does it actually
survive the same random-timing correction, or is that extra return just
noise from taking ~1.6x more trades?

Full real Gold history (2014-06-13 onward, the only real M15 data - see
CLAUDE.md's Gold contamination note), frozen defaults except
use_pullback_entry=False - not tuned, the direct mirror of the shipped
config with exactly one switch flipped.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import hs_sim as HS

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
POINT = 0.01
GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")


def load_gold_m15():
    df = pd.read_csv(f"{DATA_DIR}/GOLD_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df[["time", "open", "high", "low", "close", "spread"]]


def pf(a):
    a = np.asarray(a)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def replay(o, h, l, c, sp, q, d, stop_pct, target_pct, trail_pct, cap=3000):
    n = len(c); f = q + 1
    if f >= n - 1:
        return None
    entry = o[f] + (sp[f] if d > 0 else 0.0)
    stop = entry * (1 - d * stop_pct); target = entry * (1 + d * target_pct); trail = trail_pct * entry
    reached, peak = False, 0.0
    for k in range(f, min(n, f + cap)):
        if (d > 0 and l[k] <= stop) or (d < 0 and h[k] >= stop):
            return (stop - entry) * d / entry
        if k == f:
            continue
        if not reached and ((d > 0 and h[k] >= target) or (d < 0 and l[k] <= target)):
            reached, peak = True, target
        if reached:
            peak = max(peak, h[k]) if d > 0 else min(peak, l[k])
            ns = peak - d * trail
            if (ns - stop) * d > 0:
                stop = ns
    k = min(n - 1, f + cap - 1)
    return (c[k] - entry) * d / entry


if __name__ == "__main__":
    df = load_gold_m15()
    print(f"GOLD M15: {df['time'].iloc[0]} -> {df['time'].iloc[-1]} ({len(df)} bars), immediate-chase variant "
          f"(use_pullback_entry=False, all else = hs_sim.DEFAULTS)")

    p = dict(HS.DEFAULTS, point=POINT, use_pullback_entry=False)

    import types
    src = open("/home/user/test-project/research/trendbreaker/hs_sim.py").read()
    src = src.replace('pos = dict(dir=d, entry_px=entry, stop=P["stop"], tp=tp, fill_i=k + 1)',
                      'pos = dict(dir=d, entry_px=entry, stop=P["stop"], tp=tp, fill_i=k + 1, stop0=P["stop"], target0=(tp if tp is not None else P["stop"]), atr0=P.get("atr_at_brk", 0.0))')
    src = src.replace('pnl=pnl, pnl_pct=pnl / pos["entry_px"], reason=reason))',
                      'pnl=pnl, pnl_pct=pnl / pos["entry_px"], reason=reason, stop0=pos["stop0"], target0=pos["target0"]))')
    mod = types.ModuleType("hs_sim_rec")
    exec(compile(src, "hs_sim_rec", "exec"), mod.__dict__)
    HSR = mod

    tr = HSR.simulate(df, p)
    a = np.array([t["pnl_pct"] for t in tr])
    rpf = pf(a)
    print(f"\nREAL (hs_sim, EA-faithful fills, real spread, immediate chase): n={len(a)}  win%={100*(a>0).mean():.1f}  "
          f"%PF={rpf:.3f}  net%={100*a.sum():.1f}")

    if len(tr) < 20:
        print(f"\nOnly {len(tr)} trades -> DOES NOT SURVIVE (insufficient evidence).")
        sys.exit(0)

    et = pd.to_datetime(df["time"].values[[t["entry_i"] for t in tr]])
    for y0, y1 in (("2014", "2016-07"), ("2016-07", "2018-07"), ("2018-07", "2020-07"), ("2020-07", "2022-07"),
                   ("2022-07", "2024-07"), ("2024-07", "2027")):
        m = (et >= y0) & (et < y1)
        if m.sum():
            print(f"   {y0}..{y1}: n={m.sum()} %PF={pf(a[m]):.3f}")

    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close"))
    sp = df["spread"].values * POINT
    br = []
    for t in tr:
        d = t["dir"]; entry = t["entry_px"]
        stop_pct = abs(entry - t["stop0"]) / entry
        target_pct = abs(t["target0"] - entry) / entry if t["target0"] else stop_pct * 2.0
        trail_pct = 0.5 * p["runner_trail_atr"] * (stop_pct)
        br.append((d, stop_pct, target_pct, trail_pct))

    rng = np.random.default_rng(42)
    n = len(c)
    pool = []
    for _ in range(300):
        qs = rng.integers(400, n - 400, size=len(br))
        draw = [replay(o, h, l, c, sp, int(q), *b) for q, b in zip(qs, br)]
        draw = [x for x in draw if x is not None]
        if draw:
            pool.append(pf(draw))
    pool = np.array(pool)
    pool = pool[np.isfinite(pool)]
    pctile = 100 * (pool < rpf).mean()
    p1 = (pool >= rpf).mean()
    print(f"\nrandom-timing null (same brackets/direction, same fill+spread convention, {len(pool)} draws): "
          f"median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    print(f"REAL %PF={rpf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} "
          f"[{'SURVIVES' if p1 < 0.05 else ('borderline' if p1 < 0.15 else 'DOES NOT SURVIVE')}]")
