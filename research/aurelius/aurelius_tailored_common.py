"""
Shared machinery for the per-instrument TAILORED Aurelius walk-forward
(aurelius_silver_tailored_test.py / aurelius_btc_tailored_test.py),
2026-09-27.

WHY THIS EXISTS: the frozen-gold-parameter transfer of Aurelius to SILVER
and BTCUSD failed, and two single-dimension diagnostic sweeps on Silver
(stop_atr, MA-period scale) were flat. The fair objection: nobody had ever
JOINTLY retuned slope / S-R distance / volume / pullback / VWAP exit /
spread gate per instrument. This module lets that be tried properly -
joint search on an in-sample slice only, the IS winner frozen and run on
the later out-of-sample slice, then the project's standard random-timing
+ best-of-K pipeline on the OOS result.

TWO REAL BUGS FOUND BUILDING THIS (both fixed via opt-in hooks in sim.py /
aurelius_random_timing_test.py, gold defaults byte-identical):

 1. POINT. sim.py charged spread as spread_points * engine.POINT, and
    engine.POINT is GOLD's 0.01. SILVER's real point is 0.001 (CSV header
    meta_point), so aurelius_m15_silver_test.py charged every Silver trade
    10x its real spread: median 33 points = $0.033 real, charged $0.33 -
    ~1.7% of a ~$20 price per round trip, several M15 ATRs. That alone
    explains the "win rate 1.16%, %PF 0.042, every exit pathway loses"
    result - a spread that large makes every trade start deep underwater.
    The random baseline shared the bug, so its percentile was less wrong
    than its %PF, but the %PF itself was not a real number. BTCUSD's point
    (0.01) happens to equal gold's, so BTC's spread CHARGE was right there
    (its spread GATE was the problem, below). Params now carry "point".

 2. SPREAD GATE in raw points (the one already known this session - 60
    gold points blocked 99.3% of BTC entries). Replaced here by a gate that
    is scaled to each instrument's OWN spread distribution, as asked - but
    NOT a fixed points percentile of the whole IS history, because the
    real per-year medians below show that would be fragile across eras:
        BTCUSD median spread (points): 2018 6086, 2019-21 ~12600,
               2022-23 ~3100, 2024 9275, 2025 6000, 2026 5000
        SILVER median spread (points): 2014 64, 2016-17 44, 2018-25 ~33,
               2026 60
    An IS-calibrated fixed threshold would pass everything in one era and
    block everything in another (Silver's IS p90 of ~48 would block
    essentially all of 2026). So the gate is the CAUSAL ROLLING version of
    "the instrument's own 80th-97th percentile": block bar i if its spread
    exceeds the q-quantile of the preceding SPREAD_WIN bars (shift(1), no
    lookahead) - i.e. only genuinely abnormal moments relative to that
    instrument's recent norm, exactly the role gold's 60 plays
    incidentally. A second, optional cap blocks when the spread COST is
    large relative to volatility (spread*point / ATR > cap) - the
    quantity that actually decides whether a trade can pay for itself.
    Both are searched; "off" is a legal value of each. Whatever the gate,
    the REAL per-bar spread is always CHARGED in the P&L (never zeroed).

OUTCOME (2026-09-27, details in the two per-instrument files): no
tailored config survives OOS at the search's real K (~550-570) or at the
family-level K=4 (2 instruments x 2 timeframes). Silver M15 and BTC M15
fail outright (OOS %PF 0.740 / 1.003); Silver M5 (1.624, n=37, p K=1
0.021) and BTC M5 (1.305, n=114, p K=1 0.067) are positive OOS but not
significant beyond K=1-2 and depend on a few trades. A general caveat for
reading "beats random timing" off gold: at these instruments' spread/ATR,
the random-entry baseline is cost-crushed (medians 0.07-0.7), so beating
it is a far lower bar than being profitable - both are required.

Everything else reuses engine.build_context() and sim.simulate()
unchanged. Indicators are built once on the FULL series (all causal:
MAs, Wilder ATR, prior-day S/R, same-day VWAP, trailing-window spread
gate) and the context is then SLICED at the split, so IS and OOS runs see
exactly the indicator values the live EA would have had at that bar.
The OOS slice starts `warmup` bars before the split date so the first
tradable bar is exactly the split (those warmup bars are IS bars, never
traded).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import itertools
import numpy as np
import pandas as pd
import engine as E
from sim import simulate
import aurelius_random_timing_test as A

DATA_DIR = E.DATA_DIR
SPREAD_WIN = {"M15": 1920, "M5": 5760}   # ~20 trading days of bars, both TFs

INSTRUMENTS = {
    "SILVER": dict(point=0.001,
                   M15="SILVER_M15_native.csv", M15_start="2014-06-12",
                   M5="SILVER_M5.csv", M5_start="2022-07-04"),
    "BTCUSD": dict(point=0.01,
                   M15="BTCUSD_M15_native.csv", M15_start="2017-07-03",
                   M5="BTCUSD_M5.csv", M5_start="2023-11-17"),
}

# ---- the joint search space. Every dimension the user asked for, plus
# the M15-only slope x S/R block on/off. None = that filter/exit OFF.
# ma_scale multiplies ALL FIVE MA periods of the timeframe's gold dict,
# keeping gold's period RATIOS (the earlier Silver scale sweep's
# convention). ----
SPACE = dict(
    ma_scale=[0.5, 0.75, 1.0, 1.5, 2.0, 3.0],
    min_slope_atr=[0.0, 0.1, 0.2, 0.35, 0.5, 0.75],
    max_slope_atr=[0.8, 1.25, 2.0, None],
    min_sr_dist_atr=[None, 0.5, 1.0, 1.5, 2.5],
    min_vol_ratio=[None, 1.0, 1.3, 1.6],
    pullback_tol_atr=[0.1, 0.25, 0.5, 1.0],
    stop_atr=[1.5, 2.5, 4.0, 6.0],
    vwap_buffer_atr=[None, 0.1, 0.2, 0.5, 1.0],
    spread_q=[None, 0.8, 0.9, 0.97],
    spread_cost_atr_cap=[None, 0.1, 0.2, 0.4],
    slope_sr_block=[False, True],
)
GRID_SIZE = int(np.prod([len(v) for v in SPACE.values()]))


# ------------------------------- data -------------------------------

def load(inst, tf):
    meta = INSTRUMENTS[inst]
    df = pd.read_csv(f"{DATA_DIR}/{meta[tf]}", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    return df[df["time"] >= meta[f"{tf}_start"]].reset_index(drop=True)


def resample_h4(df):
    """Same aggregation as aurelius_m15_silver_test.resample_h4_from_m15 -
    only used for derive_d1_from_h4()'s prior-day high/low."""
    d = df.set_index("time")
    out = pd.DataFrame(dict(
        open=d["open"].resample("4h").first(), high=d["high"].resample("4h").max(),
        low=d["low"].resample("4h").min(), close=d["close"].resample("4h").last(),
        tick_volume=d["tick_volume"].resample("4h").sum(),
        spread=d["spread"].resample("4h").mean())).dropna()
    return out.reset_index()


# ---------------------------- params ----------------------------

def base_params(tf):
    return dict(E.P15) if tf == "M15" else dict(E.P)


def make_params(tf, cfg, point):
    """cfg (one point of SPACE) -> a full sim.simulate() params dict, built
    from dict(E.P15)/dict(E.P) with overrides - never the frozen dict."""
    p = base_params(tf)
    s = cfg["ma_scale"]
    for k in ("p21", "p50", "p150", "p600", "p2400"):
        p[k] = max(2, int(round(p[k] * s)))
    p["min_slope_atr"] = cfg["min_slope_atr"]
    p["max_slope_atr"] = 0 if cfg["max_slope_atr"] is None else cfg["max_slope_atr"]
    p["use_sr_dist"] = cfg["min_sr_dist_atr"] is not None
    p["min_sr_dist_atr"] = cfg["min_sr_dist_atr"] or 0.0
    p["use_volume"] = cfg["min_vol_ratio"] is not None
    p["min_vol_ratio"] = cfg["min_vol_ratio"] or 0.0
    p["pullback_tol_atr"] = cfg["pullback_tol_atr"]
    p["stop_atr"] = cfg["stop_atr"]
    p["use_vwap_exit"] = cfg["vwap_buffer_atr"] is not None
    p["vwap_buffer_atr"] = cfg["vwap_buffer_atr"] or 0.0
    p["use_slope_sr_block"] = bool(cfg["slope_sr_block"])
    p["point"] = point
    return p


def gold_frozen_cfg(tf):
    """The frozen gold defaults expressed as a SPACE point (spread gate
    'off' in the rolling sense - see gold_points_gate_block for the literal
    60-point version, reported separately for reference)."""
    b = base_params(tf)
    return dict(ma_scale=1.0, min_slope_atr=b["min_slope_atr"], max_slope_atr=b["max_slope_atr"],
                min_sr_dist_atr=b["min_sr_dist_atr"], min_vol_ratio=b["min_vol_ratio"],
                pullback_tol_atr=b["pullback_tol_atr"], stop_atr=b["stop_atr"],
                vwap_buffer_atr=b["vwap_buffer_atr"], spread_q=None, spread_cost_atr_cap=None,
                slope_sr_block=b.get("use_slope_sr_block", False))


def sample_configs(n, seed):
    rng = np.random.default_rng(seed)
    keys = list(SPACE)
    seen, out = set(), []
    while len(out) < n:
        cfg = {k: SPACE[k][rng.integers(len(SPACE[k]))] for k in keys}
        sig = tuple(cfg[k] for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(cfg)
    return out


def cfg_key(cfg):
    return tuple(cfg[k] for k in SPACE)


def cfg_str(cfg):
    ab = dict(ma_scale="ma", min_slope_atr="slo", max_slope_atr="shi", min_sr_dist_atr="sr",
              min_vol_ratio="vol", pullback_tol_atr="pb", stop_atr="stop", vwap_buffer_atr="vwap",
              spread_q="spq", spread_cost_atr_cap="spc", slope_sr_block="ssb")
    return " ".join(f"{ab[k]}={'off' if v is None else v}" for k, v in cfg.items())


# ---------------------------- context ----------------------------

def rolling_spread_quantiles(spread, win, qs):
    s = pd.Series(spread).shift(1)
    return {q: s.rolling(win, min_periods=win // 4).quantile(q).values for q in qs}


def recompute_pullback(ctx, p):
    """engine.build_context()'s PullbackOK block, re-run for a different
    pullback_tol_atr without rebuilding every MA (identical formula)."""
    line = {"21": ctx["m21"], "50": ctx["m50"], "150": ctx["m150"]}[p["pullback_ma"]]
    c, h, l, atr = ctx["close"], ctx["high"], ctx["low"], ctx["atr"]
    pb = p["pullback_bars"]
    rb = pd.Series(l - line).rolling(pb, min_periods=1).min().values
    rs = pd.Series(line - h).rolling(pb, min_periods=1).min().values
    tol = p["pullback_tol_atr"] * atr
    return (c > line) & (rb <= tol), (c < line) & (rs <= tol)


def spread_block(ctx, cfg, point, spread_q_arrays):
    n = ctx["n"]
    blk = np.zeros(n, dtype=bool)
    sp = ctx["spread"]
    if cfg["spread_q"] is not None:
        thr = spread_q_arrays[cfg["spread_q"]]
        blk |= (~np.isnan(thr)) & (sp > thr)
    if cfg["spread_cost_atr_cap"] is not None:
        with np.errstate(invalid="ignore", divide="ignore"):
            blk |= (sp * point / ctx["atr"]) > cfg["spread_cost_atr_cap"]
    return blk


def config_ctx(base_ctx, cfg, p, point, spread_q_arrays):
    """Shallow copy of the per-ma_scale base context with this config's
    pullback arrays and spread-gate mask swapped in."""
    ctx = dict(base_ctx)
    ctx["pullback_ok_buy"], ctx["pullback_ok_sell"] = recompute_pullback(base_ctx, p)
    ctx["spread_block"] = spread_block(base_ctx, cfg, point, spread_q_arrays)
    return ctx


def slice_ctx(ctx, a, b):
    n = ctx["n"]
    out = {}
    for k, v in ctx.items():
        if isinstance(v, np.ndarray) and len(v) == n:
            out[k] = v[a:b]
        else:
            out[k] = v
    out["n"] = b - a
    return out


def warmup_of(p):
    return max(p["p2400"], p["p600"]) + 50


def part_slice(ctx, p, split, part):
    """IS = [0, split); OOS = [split - warmup, end) so the first tradable
    bar is exactly the split; ALL = whole history (reporting only)."""
    if part == "IS":
        return slice_ctx(ctx, 0, split)
    if part == "OOS":
        return slice_ctx(ctx, max(0, split - warmup_of(p)), ctx["n"])
    return ctx


# ---------------------------- metrics ----------------------------

def trade_pct(trades):
    return np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] / t["entry_px"] for t in trades])


def summarize(trades):
    if not trades:
        return dict(n=0, pf=float("nan"), win=float("nan"), net_pct=0.0, long_share=float("nan"))
    r = trade_pct(trades)
    gw, gl = r[r > 0].sum(), -r[r <= 0].sum()
    return dict(n=len(trades), pf=(gw / gl if gl > 0 else float("inf")), win=(r > 0).mean(),
                net_pct=100 * r.sum(), long_share=np.mean([t["dir"] > 0 for t in trades]))


# ------------------------ random timing + best-of-K ------------------------

def random_pool(ctx, p, real_trades, n_draws, seed=42):
    """Random-entry baseline (A.simulate_random_entry: every exit rule and
    the same spread gate + real spread charge kept, only the entry signal
    replaced), trade count calibrated to the real run, direction a
    CALIBRATED coin flip at the real run's own long share (so a long-biased
    config on a drifting asset like BTC isn't credited with the drift)."""
    q = dict(p)
    q["random_p_buy"] = float(np.mean([t["dir"] > 0 for t in real_trades]))
    rng = np.random.default_rng(1)
    p_fire = A.calibrate_p_fire(ctx, q, rng, len(real_trades))
    rng = np.random.default_rng(seed)
    pfs, ns = [], []
    for _ in range(n_draws):
        tr = A.simulate_random_entry(ctx, q, rng, p_fire)
        ns.append(len(tr))
        pfs.append(A.pct_pf(tr))
    pfs = np.array(pfs)
    return pfs[~np.isnan(pfs) & ~np.isinf(pfs)], float(np.mean(ns)), p_fire, q["random_p_buy"]


def best_of_k(pool, real_pf, ks, n_boot=4000, seed=7):
    rng = np.random.default_rng(seed)
    out = []
    for K in ks:
        best = pool[rng.integers(0, len(pool), size=(n_boot, K))].max(axis=1)
        out.append((K, float(np.median(best)), float((best >= real_pf).mean())))
    return out


def verdict(p):
    return "SURVIVES" if p < 0.05 else ("borderline" if p < 0.15 else "FAILS")


# ============================ walk-forward driver ============================
# Module-level state so multiprocessing (fork) workers inherit the big
# arrays without pickling them per task.
_G = {}


def _eval_cfg(args):
    cfg, part = args
    tf, point, split = _G["tf"], _G["point"], _G["split"]
    p = make_params(tf, cfg, point)
    ctx = config_ctx(_G["base"][cfg["ma_scale"]], cfg, p, point, _G["sq"])
    c = part_slice(ctx, p, split, part)
    s = summarize(simulate(c, params=p))
    return cfg_key(cfg), part, s


def _ensure_base(scales):
    for s in scales:
        if s not in _G["base"]:
            p = make_params(_G["tf"], dict(gold_frozen_cfg(_G["tf"]), ma_scale=s), _G["point"])
            _G["base"][s] = E.build_context(_G["df"], _G["h4"], p)


def _score(s, min_n):
    return s["pf"] if (s["n"] >= min_n and np.isfinite(s["pf"])) else -1.0


def _rand_chunk(args):
    part, cfg, real_n, p_buy, p_fire, n, seed = args
    tf, point, split = _G["tf"], _G["point"], _G["split"]
    p = make_params(tf, cfg, point)
    p["random_p_buy"] = p_buy
    ctx = config_ctx(_G["base"][cfg["ma_scale"]], cfg, p, point, _G["sq"])
    c = part_slice(ctx, p, split, part)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        out.append(A.pct_pf(A.simulate_random_entry(c, p, rng, p_fire)))
    return out


def _real_trades(cfg, part):
    tf, point, split = _G["tf"], _G["point"], _G["split"]
    p = make_params(tf, cfg, point)
    ctx = config_ctx(_G["base"][cfg["ma_scale"]], cfg, p, point, _G["sq"])
    c = part_slice(ctx, p, split, part)
    return c, p, simulate(c, params=p)


def random_test(pool_exec, cfg, part, n_draws, ks):
    c, p, real = _real_trades(cfg, part)
    real_pf = A.pct_pf(real)
    p_buy = float(np.mean([t["dir"] > 0 for t in real])) if real else 0.5
    q = dict(p); q["random_p_buy"] = p_buy
    p_fire = A.calibrate_p_fire(c, q, np.random.default_rng(1), len(real))
    per = n_draws // 4
    chunks = pool_exec.map(_rand_chunk, [(part, cfg, len(real), p_buy, p_fire, per, 100 + j) for j in range(4)])
    pool = np.array([x for ch in chunks for x in ch])
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    pct = 100 * (pool < real_pf).mean()
    return dict(real_pf=real_pf, n=len(real), p_buy=p_buy, pool=pool, pctile=pct,
                ladder=best_of_k(pool, real_pf, ks))


def setup(inst, tf, split_frac=0.6):
    """Populate the module state for inst/tf without running the search
    (used by aurelius_tailored_extra_checks.py). Returns (df, split)."""
    point = INSTRUMENTS[inst]["point"]
    df = load(inst, tf)
    split = int(len(df) * split_frac)
    _G.clear()
    _G.update(tf=tf, point=point, split=split, df=df, h4=resample_h4(df), base={})
    _ensure_base(SPACE["ma_scale"])
    _G["sq"] = rolling_spread_quantiles(df["spread"].values.astype(float), SPREAD_WIN[tf],
                                        [q for q in SPACE["spread_q"] if q is not None])
    return df, split


def run_walkforward(inst, tf, split_frac=0.6, n_stage1=500, seed=2026, n_random=600, log=print):
    """Full pipeline for one instrument/timeframe. Returns a results dict;
    everything is also logged."""
    import multiprocessing as mp
    point = INSTRUMENTS[inst]["point"]
    df = load(inst, tf)
    h4 = resample_h4(df)
    split = int(len(df) * split_frac)
    t0, ts, t1 = df["time"].iloc[0], df["time"].iloc[split], df["time"].iloc[-1]
    is_yrs = (ts - t0).days / 365.25
    oos_yrs = (t1 - ts).days / 365.25
    min_n = int(max(50, 12 * is_yrs))
    _G.clear()
    _G.update(tf=tf, point=point, split=split, df=df, h4=h4, base={})
    log(f"=== {inst} {tf}: {len(df)} bars {t0} -> {t1}; point={point}")
    log(f"    chronological split {split_frac:.0%}/{1-split_frac:.0%} at bar {split} = {ts}")
    log(f"    IS  {t0.date()} -> {ts.date()} ({is_yrs:.1f} yrs)   OOS {ts.date()} -> {t1.date()} ({oos_yrs:.1f} yrs)")
    log(f"    IS selection: max IS %PF subject to n_IS >= {min_n} (~12 trades/yr floor)")
    sp_is = df["spread"].values[:split]
    log(f"    IS spread (points) p50/p80/p90/p97: {np.percentile(sp_is,[50,80,90,97]).round(0)}; "
        f"OOS p50/p90: {np.percentile(df['spread'].values[split:],[50,90]).round(0)}")

    _ensure_base(SPACE["ma_scale"])
    _G["sq"] = rolling_spread_quantiles(df["spread"].values.astype(float), SPREAD_WIN[tf],
                                        [q for q in SPACE["spread_q"] if q is not None])

    gold_cfg = gold_frozen_cfg(tf)
    stage1 = sample_configs(n_stage1, seed)
    evaluated = {}      # cfg_key -> (cfg, IS summary)
    with mp.get_context("fork").Pool(4) as pool_exec:
        # reference rows (NOT counted in K - not candidates for selection)
        ref = {}
        for label, cfg in [("gold frozen, real point, no gate", gold_cfg)]:
            ref[label] = {part: _eval_cfg((cfg, part))[2] for part in ("IS", "OOS")}
        # literal gold 60-point gate (spread_block absent -> sim's raw points path)
        pg = make_params(tf, gold_cfg, point)
        cg = dict(_G["base"][1.0]); cg["pullback_ok_buy"], cg["pullback_ok_sell"] = recompute_pullback(cg, pg)
        ref["gold frozen, real point, gold 60-pt gate"] = {
            "IS": summarize(simulate(slice_ctx(cg, 0, split), params=pg)),
            "OOS": summarize(simulate(slice_ctx(cg, split - warmup_of(pg), cg["n"]), params=pg))}
        pg_bug = dict(pg); pg_bug["point"] = E.POINT
        ref["gold frozen, GOLD point (old bug), 60-pt gate"] = {
            "IS": summarize(simulate(slice_ctx(cg, 0, split), params=pg_bug)),
            "OOS": summarize(simulate(slice_ctx(cg, split - warmup_of(pg), cg["n"]), params=pg_bug))}
        log("\n  reference (not part of the search):")
        for label, r in ref.items():
            log(f"    {label:<46} IS n={r['IS']['n']:>5} %PF={r['IS']['pf']:.3f} win={r['IS']['win']:.3f} | "
                f"OOS n={r['OOS']['n']:>5} %PF={r['OOS']['pf']:.3f} win={r['OOS']['win']:.3f}")

        # ---- stage 1: random search, IS only ----
        res = list(pool_exec.map(_eval_cfg, [(c, "IS") for c in stage1], chunksize=4))
        by_key = {cfg_key(c): c for c in stage1}
        for key, part, s in res:
            evaluated[key] = (by_key[key], s)
        n_stage1_eval = len(res)
        ok = [(k, v) for k, v in evaluated.items() if v[1]["n"] >= min_n]
        pfs = np.array([v[1]["pf"] for _, v in ok])
        log(f"\n  stage 1: {n_stage1_eval} random configs (of {GRID_SIZE:,} grid points), "
            f"{len(ok)} meet n>={min_n}; IS %PF among those: median={np.median(pfs):.3f} "
            f"p90={np.percentile(pfs,90):.3f} max={pfs.max():.3f}; "
            f"{(pfs > 1).sum()} of {len(pfs)} have IS %PF > 1")
        best_key = max(evaluated, key=lambda k: _score(evaluated[k][1], min_n))
        best_cfg, best_s = evaluated[best_key]
        log(f"  stage-1 IS winner: %PF={best_s['pf']:.3f} n={best_s['n']}  [{cfg_str(best_cfg)}]")

        # ---- stage 2: coordinate ascent from the stage-1 winner, IS only ----
        n_stage2_eval = 0
        for sweep in range(2):
            improved = False
            for dim, vals in SPACE.items():
                cands = [dict(best_cfg, **{dim: v}) for v in vals if v != best_cfg[dim]]
                cands = [c for c in cands if cfg_key(c) not in evaluated]
                if cands:
                    for key, part, s in pool_exec.map(_eval_cfg, [(c, "IS") for c in cands]):
                        evaluated[key] = (next(c for c in cands if cfg_key(c) == key), s)
                    n_stage2_eval += len(cands)
                cur = max([cfg_key(dict(best_cfg, **{dim: v})) for v in vals],
                          key=lambda k: _score(evaluated[k][1], min_n))
                if _score(evaluated[cur][1], min_n) > _score(best_s, min_n) + 1e-12:
                    best_cfg, best_s = evaluated[cur]
                    improved = True
            if not improved:
                break
        K_search = n_stage1_eval + n_stage2_eval
        log(f"  stage 2: coordinate ascent ({sweep+1} pass(es)), {n_stage2_eval} more configs -> "
            f"TOTAL configs evaluated on IS = K_search = {K_search}")
        log(f"  FINAL IS winner: %PF={best_s['pf']:.3f} n={best_s['n']} win={best_s['win']:.3f} "
            f"long={best_s['long_share']:.2f}\n    [{cfg_str(best_cfg)}]")

        # ---- frozen winner on OOS ----
        _, _, oos_s = _eval_cfg((best_cfg, "OOS"))
        log(f"  FROZEN winner on OOS: %PF={oos_s['pf']:.3f} n={oos_s['n']} win={oos_s['win']:.3f} "
            f"net={oos_s['net_pct']:+.1f}% (sum of per-trade % returns)")

        # ---- diagnostic: does IS rank predict OOS at all? (every IS-eligible
        # stage-1 config run on OOS - REPORTING ONLY, nothing is selected on it) ----
        elig = [evaluated[k][0] for k, _ in ok]
        oos_all = {key: s for key, part, s in pool_exec.map(_eval_cfg, [(c, "OOS") for c in elig], chunksize=4)}
        is_v = np.array([evaluated[cfg_key(c)][1]["pf"] for c in elig])
        oos_v = np.array([oos_all[cfg_key(c)]["pf"] for c in elig])
        m = np.isfinite(oos_v)
        rho = pd.Series(is_v[m]).rank().corr(pd.Series(oos_v[m]).rank())
        order = np.argsort(-is_v)
        top10 = [(is_v[j], oos_v[j], oos_all[cfg_key(elig[j])]["n"]) for j in order[:10]]
        log(f"  diagnostic (reporting only): IS-vs-OOS Spearman rank corr across {m.sum()} eligible "
            f"stage-1 configs = {rho:+.3f}; OOS %PF of ALL of them: median={np.nanmedian(oos_v):.3f}, "
            f"{(oos_v > 1).sum()} of {m.sum()} > 1")
        log("    top-10 by IS %PF -> OOS %PF (n): " +
            ", ".join(f"{a:.2f}->{b:.2f}({c})" for a, b, c in top10))

        # ---- random timing + best-of-K, IS (for contrast) and OOS (the answer) ----
        ks = sorted(set([1, 10, 30, 50, 100, K_search]))
        out = dict(inst=inst, tf=tf, split=str(ts), is_yrs=is_yrs, oos_yrs=oos_yrs, K=K_search,
                   best_cfg=best_cfg, is_s=best_s, oos_s=oos_s, rho=rho, ref=ref)
        for part in ("IS", "OOS"):
            rt = random_test(pool_exec, best_cfg, part, n_random, ks)
            out[f"rt_{part}"] = rt
            log(f"\n  random timing on {part} ({len(rt['pool'])} draws, calibrated coin p_buy={rt['p_buy']:.2f}): "
                f"real %PF={rt['real_pf']:.3f} (n={rt['n']}); random median={np.median(rt['pool']):.3f} "
                f"p95={np.percentile(rt['pool'],95):.3f}; real at {rt['pctile']:.1f}th pct")
            for K, med, pk in rt["ladder"]:
                tag = "  <- this search's real K" if K == K_search else ""
                log(f"    K={K:>4}: best-of-K median={med:.3f}  p={pk:.4f}  [{verdict(pk)}]{tag}")
    return out
