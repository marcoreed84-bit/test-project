"""AUDIT: EA-faithful hs_sim.py (market fill at next open + spread) on Gold IS and untouched OOS,
vs a random-timing null that replays each real trade's own %-bracket with the SAME fill/management
convention as hs_sim (fill at next open, spread, SL checked from the fill bar, runner skip on fill bar)."""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius"); sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np, pandas as pd, engine as E, pattern_rigor_common as R, hs_sim as HS
CUT = pd.Timestamp("2022-07-04")
def replay(o, h, l, c, sp, q, d, stop_pct, target_pct, trail_pct, cap=3000):
    n = len(c); f = q + 1
    entry = o[f] + (sp[f] if d > 0 else 0.0)
    stop = entry * (1 - d * stop_pct); target = entry * (1 + d * target_pct); trail = trail_pct * entry
    reached = False; peak = 0.0
    for k in range(f, min(n, f + cap)):
        if (d > 0 and l[k] <= stop) or (d < 0 and h[k] >= stop):
            return (stop - entry) * d / entry
        if k == f: continue
        if not reached and ((d > 0 and h[k] >= target) or (d < 0 and l[k] <= target)):
            reached = True; peak = target
        if reached:
            peak = max(peak, h[k]) if d > 0 else min(peak, l[k])
            ns = peak - d * trail
            if (ns - stop) * d > 0: stop = ns
    k = min(n - 1, f + cap - 1)
    return (c[k] - entry) * d / entry
def pf(a):
    a = np.asarray(a); gw = a[a > 0].sum(); gl = -a[a <= 0].sum(); return gw / gl if gl > 0 else np.inf
def study(label, df, ndraw=300):
    p = dict(HS.DEFAULTS, point=0.01)
    tr = HS.simulate(df, p)
    a = np.array([t["pnl_pct"] for t in tr]); rpf = pf(a)
    # zero-spread gross
    d0 = df.copy(); d0["spread"] = 0
    g = np.array([t["pnl_pct"] for t in HS.simulate(d0, p)])
    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close")); sp = df["spread"].values * 0.01
    # bracket per trade from the real hs_sim trade (need stop/target: recompute from exit logic not stored) ->
    # use repo convention: stop_pct = |entry - initial stop|/entry etc. hs_sim doesn't store them, so re-derive
    print(f"\n{label}: hs_sim n={len(a)} win%={100*(a>0).mean():.1f} %PF(net, spread)={rpf:.3f} net%={100*a.sum():.1f} | zero-spread n={len(g)} %PF={pf(g):.3f}")
    et = pd.to_datetime(df["time"].values[[t['entry_i'] for t in tr]])
    for y0, y1 in (("2014","2016-07"),("2016-07","2018-07"),("2018-07","2020-07"),("2020-07","2022-07"),("2022-07","2024-07"),("2024-07","2027")):
        m = (et >= y0) & (et < y1)
        if m.sum(): print(f"   {y0}..{y1}: n={m.sum()} %PF={pf(a[m]):.3f}")
    return tr, a, rpf
if __name__ == "__main__":
    which = sys.argv[1]
    if which == "is":
        df = E.resample_m15_from_m5(E.load_m5())
    else:
        m15 = E.load_m15_native(); df = m15[(m15.time >= R.REAL_M15_START) & (m15.time < CUT)].reset_index(drop=True)
    df = df[["time","open","high","low","close","spread"]].reset_index(drop=True)
    # patch hs_sim to also record the bracket: wrap finish via monkeypatch is awkward -> recompute from pos dict
    import types
    src = open("/home/user/test-project/research/trendbreaker/hs_sim.py").read()
    src = src.replace('pos = dict(dir=d, entry_px=entry, stop=P["stop"], tp=tp, fill_i=k + 1)',
                      'pos = dict(dir=d, entry_px=entry, stop=P["stop"], tp=tp, fill_i=k + 1, stop0=P["stop"], target0=P["target"], atr0=P["atr_at_brk"])')
    src = src.replace('pnl=pnl, pnl_pct=pnl / pos["entry_px"], reason=reason))',
                      'pnl=pnl, pnl_pct=pnl / pos["entry_px"], reason=reason, stop0=pos["stop0"], target0=pos["target0"], atr0=pos["atr0"]))')
    import os
    if os.environ.get('STRICT')=='1':
        _o='zIdx, zType, zPx = find_swings_window(cand_idx, isH, isL, h, l, atr, params["swing_min_atr"], win_start, k)'
        assert _o in src
        src = src.replace(_o, _o.replace('win_start, k)', 'win_start + N, k - N)'))
        print('STRICT (no look-ahead) window')
    mod = types.ModuleType("hs_sim_rec"); exec(compile(src, "hs_sim_rec", "exec"), mod.__dict__); HS = mod
    tr, a, rpf = study(("IN-SAMPLE 2022-07..2026-09" if which == "is" else "UNTOUCHED 2014-06..2022-07") + " (Gold M15)", df)
    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close")); sp = df["spread"].values * 0.01
    br = [(t["dir"], abs(t["entry_px"] - t["stop0"]) / t["entry_px"], abs(t["target0"] - t["entry_px"]) / t["entry_px"],
           0.5 * t["atr0"] / t["entry_px"]) for t in tr]
    rng = np.random.default_rng(42); n = len(c); pool = []
    for _ in range(300):
        qs = rng.integers(400, n - 400, size=len(br))
        pool.append(pf([replay(o, h, l, c, sp, int(q), *b) for q, b in zip(qs, br)]))
    pool = np.array(pool); pool = pool[np.isfinite(pool)]
    print(f"  random-timing null (same brackets/direction, same fill+spread convention, 300 draws): median={np.median(pool):.3f} "
          f"p95={np.percentile(pool,95):.3f} -> REAL at {100*(pool<rpf).mean():.1f}th pct, p={(pool>=rpf).mean():.3f}")
    rows = R.best_of_k(rpf, pool, (1, 27, 50))
    print("  " + " ".join(f"K={r['K']}:p={r['p']:.3f}" for r in rows))
