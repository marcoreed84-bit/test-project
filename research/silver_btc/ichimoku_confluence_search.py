"""
"Ichimoku Confluence Strategy" (the user's twelfth pasted Pine v6
strategy) - genuinely different from the real Ichimoku_EA.mq5 already
audited this session (research/ichimoku/, a PLAIN+ADX construction that
DOES NOT SURVIVE gold's own K=20 correction - see ichimoku_random_
timing_test.py). This one is a Tenkan/Kijun cross TIERED by where the
cross happens relative to the (displaced) cloud - strong (beyond the
cloud, trading with the dominant trend), neutral (inside the cloud),
weak (against the cloud) - plus a higher-timeframe (Daily) Tenkan/Kijun
agreement filter, ATR stop/target, and a bearish-cross exit independent
of P&L. LONG-ONLY BY DEFAULT (tradingMode="Long", the script's own
default and this file's primary test, same precedent as Golden Trident).

PORTED FAITHFULLY: the donchian-midpoint Tenkan(9)/Kijun(26)/SenkouB(52)
construction (canonical Ichimoku, not tuned), the displaced-cloud-under-
the-current-bar lookup (cloudNow = senkouA/B computed `displacement-1`
bars ago - exactly reproduces what request.security-free Pine code
does here, a pure historical offset, no lookahead), the strong/neutral/
weak tier classification at the cross bar's own Tenkan level vs cloud
top/bottom, the tier-selection logic (entry defaults to "Strong +
Neutral", exit defaults to "All" - which collapses to "any bearish
cross, unconditionally" since strong+neutral+weak exhaustively partition
every bearCross), and the HTF Daily Tenkan/Kijun agreement filter (built
from real D1-resampled data, using the PREVIOUS completed daily bar's
value for any M15 bar during the current day - matching request.
security's lookahead=off behavior, same causal convention already used
for the ICT Liquidity Sweep script's previous-day levels).

GRID (K=27, literal): ATR_MULT_SL in {1.0,1.5,2.5} x ATR_MULT_TP in
{2.0,3.0,4.0} x ENTRY_TIER in {"Strong Only","Strong + Neutral","All"}.
Tenkan/Kijun/SenkouB/displacement (9/26/52/26) and the HTF filter (Daily,
ON) are the script's own canonical/default values, fixed to keep K
honest; exit tier stays at the default "All".
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

ATR_MULT_SLS = [1.0, 1.5, 2.5]
ATR_MULT_TPS = [2.0, 3.0, 4.0]
ENTRY_TIERS = ["strong", "strong_neutral", "all"]
TENKAN_LEN, KIJUN_LEN, SENKOU_LEN, DISPLACEMENT = 9, 26, 52, 26
ATR_LEN = 14


def donchian(h, l, period):
    hh = pd.Series(h).rolling(period, min_periods=period).max().values
    ll = pd.Series(l).rolling(period, min_periods=period).min().values
    return (hh + ll) / 2.0


def cross_edges(a, b):
    above = a > b
    above_prev = np.concatenate(([False], above[:-1]))
    valid = ~np.isnan(a) & ~np.isnan(b)
    valid_prev = np.concatenate(([False], valid[:-1]))
    up = above & ~above_prev & valid & valid_prev
    dn = (~above) & above_prev & valid & valid_prev
    return up, dn


def tier_match(tier, strong, neutral, weak):
    if tier == "strong":
        return strong
    if tier == "strong_neutral":
        return strong | neutral
    return strong | neutral | weak


def build_htf_filter(df15, b):
    df1d = C.resample(df15, "1D")
    tenkan_d1 = donchian(df1d["high"].values, df1d["low"].values, TENKAN_LEN)
    kijun_d1 = donchian(df1d["high"].values, df1d["low"].values, KIJUN_LEN)
    htf_bull_d1 = tenkan_d1 > kijun_d1
    d1_dates = pd.to_datetime(df1d["time"]).dt.date.values
    daily_series = pd.Series(htf_bull_d1, index=d1_dates)
    daily_shifted = daily_series.shift(1)  # only the PREVIOUS completed day is visible intraday
    htf_map = daily_shifted.to_dict()
    m15_dates = pd.to_datetime(b.time).normalize()
    m15_dates = m15_dates.date if hasattr(m15_dates, "date") else pd.DatetimeIndex(m15_dates).date
    mtf_ok_long = pd.Series(m15_dates).map(htf_map).fillna(False).values.astype(bool)
    return mtf_ok_long


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- Ichimoku Confluence, long-only (ATR_MULT_SL, ATR_MULT_TP, ENTRY_TIER)\n{b.describe()}")

    tenkan = donchian(b.high, b.low, TENKAN_LEN)
    kijun = donchian(b.high, b.low, KIJUN_LEN)
    senkou_a = (tenkan + kijun) / 2.0
    senkou_b = donchian(b.high, b.low, SENKOU_LEN)

    shift = DISPLACEMENT - 1
    cloud_now_a = np.concatenate((np.full(shift, np.nan), senkou_a[:-shift]))
    cloud_now_b = np.concatenate((np.full(shift, np.nan), senkou_b[:-shift]))
    with np.errstate(invalid="ignore"):
        cloud_top = np.maximum(cloud_now_a, cloud_now_b)
        cloud_bot = np.minimum(cloud_now_a, cloud_now_b)

    bull_cross, bear_cross = cross_edges(tenkan, kijun)
    cross_level = tenkan

    with np.errstate(invalid="ignore"):
        strong_bull = bull_cross & (cross_level > cloud_top)
        neutral_bull = bull_cross & (cross_level <= cloud_top) & (cross_level >= cloud_bot)
        weak_bull = bull_cross & (cross_level < cloud_bot)
    long_exit_sig = bear_cross  # "All" tier default = unconditional on any bear cross

    mtf_ok_long = build_htf_filter(df15, b)

    atr = C.wilder_atr(b.high, b.low, b.close, ATR_LEN)

    grid = list(itertools.product(ATR_MULT_SLS, ATR_MULT_TPS, ENTRY_TIERS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    no_exit = np.zeros(b.n, dtype=np.bool_)
    rows = []
    for cfg in grid:
        sl_mult, tp_mult, tier = cfg
        long_entry_sig = tier_match(tier, strong_bull, neutral_bull, weak_bull) & mtf_ok_long

        il = np.where(long_entry_sig)[0]
        valid_l = ~np.isnan(atr[il]) & (atr[il] > 0)
        il = il[valid_l]
        dist_l = sl_mult * atr[il]
        target_r = tp_mult / sl_mult

        ex = dict(target_r=target_r, max_hold=2000, trail_atr=0.0, exit_long=long_exit_sig, exit_short=no_exit)
        r = C.sim_signals(il.astype(np.int64), np.ones(len(il)), dist_l, b.open, b.high, b.low, b.close, b.spread_px,
                          b.atr, ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"],
                          b.is_lo, b.is_hi)
        n_tr, pnl = len(r[3]), r[3]
        if n_tr < 100:
            continue
        rows.append(dict(cfg=cfg, n=n_tr, pf=C.pct_pf(pnl), il=il, target_r=target_r, ex=ex))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>=100. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    sl_mult, tp_mult, tier = best["cfg"]
    il = best["il"]
    dist_l = sl_mult * atr[il]
    ex = best["ex"]
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
    r = C.sim_signals(il.astype(np.int64), np.ones(len(il)), dist_l, b.open, b.high, b.low, b.close, b.spread_px,
                      b.atr, *exargs, b.oos_lo, b.oos_hi)
    oos_pnl, oos_dir, oos_dist = r[3], r[2], r[4]
    n_oos = len(oos_pnl)
    if n_oos == 0:
        log("No OOS trades."); return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (0 OOS trades)")
    oos_pf = C.pct_pf(oos_pnl)
    log(f"OOS (untouched): n={n_oos}  win%={100*(oos_pnl>0).mean():.1f}  %PF={oos_pf:.3f}  sum%={100*oos_pnl.sum():.1f}")
    if n_oos < 20:
        log("Too few OOS trades -> DOES NOT SURVIVE (insufficient evidence).")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (n<20)")

    allowed = mtf_ok_long
    pool, p_fire, mean_n = C.random_pool(b, oos_dist, n_oos, *exargs, b.oos_lo, b.oos_hi, allowed, p_long=1.0)
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = C.best_of_k_p(pool, oos_pf, K)
    log(f"random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={mean_n:.0f}, "
        f"restricted to HTF-bullish bars like the real system): median={np.median(pool):.3f}  "
        f"p95={np.percentile(pool,95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{C.verdict(pK)}]")
    return dict(label=symbol, K=K, cfg=best["cfg"], is_n=best["n"], is_pf=best["pf"], oos_n=n_oos, oos_pf=oos_pf,
                pctile=pctile, p1=p1, pK=pK, verdict=C.verdict(pK) if p1 < 0.05 else C.verdict(max(p1, pK)))


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/ichimoku_confluence_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
