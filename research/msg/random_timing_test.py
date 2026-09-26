"""
Random-timing baseline + best-of-K multiple-testing correction for MSG3,
same rigor already applied to Ratchet/Meridian/Aurelius/Vanguard - answers
the user's direct question ("does this version meet K=100").

IMPORTANT FRAMING DIFFERENCE (see MSG_Trader_EA.mq5's own header and the
2026-09-26 conversation): MSG is a RECONSTRUCTION of a real, already-live EA
built from real MT5 reports, not a discretionary signal discovered by
searching many candidate constructions - its primary evidence is the
trade-by-trade real-vs-sim match (validate_all.py, v118_fresh_validate.py:
97-100% entry-minute match against real reports). This test answers a
DIFFERENT, narrower question: even granting the reconstruction is faithful,
does MSG3's own entry timing (the session-range retracement/OTE zone logic)
add value beyond what the SAME risk-sized bracket would have made fired at
a random time in the same market? K here is counted from the real, disclosed
version history in MSG_Trader_EA.mq5's header (v1.00-v1.18: 19 dated
entries, of which v1.06/v1.16/v1.17-comment-only are pure cosmetic/no-op -
16 logic-affecting versions is the floor used below), same "floor not
precise audit" caveat as every other K figure in this project.

METHOD: extract simulate()'s own ManageOpenPosition + intrabar SL/TP3 state
machine into a standalone walk_bracket() (bar_open mode only, matching the
default manage_mode), so real and random trades are managed by IDENTICAL
code. For each real MSG3 trade, replay its OWN risk (R, in price terms) as
a same-direction bracket at a uniformly random entry bar in the SAME
segment, TP1/TP2/TP3 at the same 1.0/1.5/2.0 R, same static post-TP2 lock,
same 48h max hold. Outcome metric: R-multiple (pnl_usd / (risk*units0*
LOT_STEP*CONTRACT)) rather than %PF - MSG's own TP levels are already
defined in R, InpSmallRiskSizing varies position size by setup, so R-multiple
is the scale-neutral measure here (analogous to why %PF replaces raw points
elsewhere: avoids overweighting by position size/price level).
"""
import sys
sys.path.insert(0, ".")
import glob
import numpy as np
import pandas as pd
from sim import Params, simulate, load_bars, M1_CHUNK_DIR, lot_round, LOT_STEP, CONTRACT, PT

RNG_SEED = 42
N_RANDOM = 400
K_LIST = (1, 16, 30, 50, 100)


def bracket_arrays(bars, p):
    o = bars["open"].values + p.bid_off
    h = bars["high"].values + p.bid_off
    l = bars["low"].values + p.bid_off
    c = bars["close"].values + p.bid_off
    sp = bars["spread"].values * PT - p.bid_off + p.ask_extra
    t_arr = bars["time"].values.astype("datetime64[s]").astype(np.int64)
    dows = bars["time"].dt.dayofweek.values
    mins = (bars["time"].dt.hour * 60 + bars["time"].dt.minute).values
    return o, h, l, c, sp, t_arr, dows, mins


def walk_bracket(k0, d, entry_px, risk, units0, arrs, p, k1):
    """Manage a single bracket (TP1/TP2/TP3 in R, static post-TP2 lock,
    structural-equivalent fixed SL) from bar k0 forward - bar_open mode,
    line-for-line the same logic as simulate()'s ManageOpenPosition +
    intrabar SL/TP3 block, just entered synthetically instead of via
    check_setups(). Returns pnl_usd (None if it never resolves before k1)."""
    o, h, l, c, sp, t_arr, dows, mins = arrs
    fri_close_min = p.friday_close[0] * 60 + p.friday_close[1]
    sl = entry_px - d * risk
    tp1 = entry_px + d * p.tp1 * risk
    tp2 = entry_px + d * p.tp2 * risk
    tp3 = entry_px + d * p.tp3 * risk
    units = units0
    tp1done = tp2done = False
    t0 = int(t_arr[k0])
    legs = []

    def close_leg(px, u, reason, k):
        legs.append((px, u))
        return u

    for k in range(k0 + 1, k1):
        bid = o[k]; ask = o[k] + sp[k]
        if p.max_hold_h > 0 and t_arr[k] - t0 >= p.max_hold_h * 3600:
            close_leg(bid if d > 0 else ask, units, "maxhold", k)
            units = 0
            break
        if (p.weekend_guard_mode == "intended" and p.weekend_guard_min > 0 and dows[k] == 4
                and 0 <= fri_close_min - mins[k] <= p.weekend_guard_min):
            close_leg(bid if d > 0 else ask, units, "weekend", k)
            units = 0
            break
        price = bid if d > 0 else ask
        if not tp1done and (price - tp1) * d >= 0:
            u = round(lot_round(units * LOT_STEP / 3.0) / LOT_STEP)
            if u > 0 and units - u >= 1:
                close_leg(price, u, "tp1", k); units -= u
            tp1done = True
            sl = entry_px
        if tp1done and not tp2done and (price - tp2) * d >= 0:
            u = round(lot_round(units * LOT_STEP / 2.0) / LOT_STEP)
            if u > 0 and units - u >= 1:
                close_leg(price, u, "tp2", k); units -= u
            tp2done = True
        if tp2done:
            lock = entry_px + d * p.trail * risk
            if (sl - lock) * d < -PT * 0.5:
                sl = lock
        # intrabar SL / TP3 (bar_open mode: TP1/TP2 only at bar open, SL/TP3 intrabar)
        if d > 0:
            hit_sl, hit_tp = l[k] <= sl, h[k] >= tp3
            if hit_sl and hit_tp:
                first_sl = (o[k] - sl) <= (tp3 - o[k])
            else:
                first_sl = hit_sl
            if hit_sl and first_sl:
                close_leg(min(sl, o[k]), units, "sl", k); units = 0; break
            elif hit_tp:
                close_leg(max(tp3, o[k]), units, "tp", k); units = 0; break
        else:
            ah, al, ao = h[k] + sp[k], l[k] + sp[k], o[k] + sp[k]
            hit_sl, hit_tp = ah >= sl, al <= tp3
            if hit_sl and hit_tp:
                first_sl = (sl - ao) <= (ao - tp3)
            else:
                first_sl = hit_sl
            if hit_sl and first_sl:
                close_leg(max(sl, ao), units, "sl", k); units = 0; break
            elif hit_tp:
                close_leg(min(tp3, ao), units, "tp", k); units = 0; break
    else:
        return None   # ran off the end of this segment before resolving
    pnl = sum((px - entry_px) * d * u * LOT_STEP * CONTRACT for px, u in legs)
    return pnl


def real_trades_r(bars, p):
    arrs = bracket_arrays(bars, p)
    o, h, l, c, sp, t_arr, dows, mins = arrs
    trades, _ = simulate(bars, p)
    out = []
    for tr in trades:
        k0 = int(np.searchsorted(t_arr, tr["t"]))
        risk_usd = tr["risk"] * tr["units0"] * LOT_STEP * CONTRACT
        r = tr["pnl"] / risk_usd if risk_usd > 0 else 0.0
        out.append(dict(k0=k0, dir=tr["dir"], entry_px=tr["fill"], risk=tr["risk"],
                         units0=tr["units0"], r=r))
    return out, arrs


def random_pool(real, arrs, p, rng, n_runs, k1, k_lo=200, k_hi_margin=3000):
    """One %-R-PF per run: for EACH real trade, draw ONE random k0 (same
    direction, own risk/size) and re-walk; aggregate that run's R-multiples
    into a single PF-style ratio (gross +R / gross -R)."""
    n = len(arrs[5])
    hi = min(k1, n) - k_hi_margin
    pool = []
    for _ in range(n_runs):
        rs = []
        for tr in real:
            k0 = int(rng.integers(k_lo, max(k_lo + 1, hi)))
            pnl = walk_bracket(k0, tr["dir"], arrs[0][k0] if tr["dir"] < 0 else arrs[0][k0] + arrs[4][k0],
                                tr["risk"], tr["units0"], arrs, p, min(k1, n))
            if pnl is None:
                continue
            risk_usd = tr["risk"] * tr["units0"] * LOT_STEP * CONTRACT
            rs.append(pnl / risk_usd if risk_usd > 0 else 0.0)
        if len(rs) < 5:
            continue
        arr = np.array(rs)
        gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
        pool.append(gw / gl if gl > 0 else np.nan)
    return np.array(pool)


def r_pf(rs):
    arr = np.array(rs)
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


if __name__ == "__main__":
    segments = []
    chunk_files = sorted(glob.glob(f"{M1_CHUNK_DIR}/*.csv"))
    if chunk_files:
        old_bars = pd.concat([load_bars(f) for f in chunk_files], ignore_index=True)
        old_bars = old_bars.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
        segments.append(("2014-2021", old_bars))
    segments.append(("2025-11 - 2026-09", load_bars()))

    all_r, all_pools = [], []
    rng = np.random.default_rng(RNG_SEED)
    for label, bars in segments:
        p = Params(start=str(bars["time"].min().date()), end=str((bars["time"].max() + pd.Timedelta(days=1)).date()))
        real, arrs = real_trades_r(bars, p)
        n = len(arrs[5])
        k1 = n
        seg_r = [tr["r"] for tr in real]
        all_r.extend(seg_r)
        print(f"{label}: n={len(real)} real trades, R-PF={r_pf(seg_r):.3f}, mean R={np.mean(seg_r):.3f}")
        pool = random_pool(real, arrs, p, rng, N_RANDOM, k1)
        pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
        all_pools.append(pool)
        print(f"  segment random-timing pool: n={len(pool)} runs, median R-PF={np.median(pool):.3f}")

    real_pf = r_pf(all_r)
    print(f"\nCOMBINED real MSG3 trades: n={len(all_r)}  R-PF={real_pf:.3f}")

    # pool single-draw R-PFs across segments (weighted by trade count, same
    # bootstrap-pool convention as every other K-correction test this project)
    pool = np.concatenate(all_pools)
    print(f"Combined random-timing pool: n={len(pool)}  median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pf).mean()
    p_val = (pool >= real_pf).mean()
    print(f"\nREAL R-PF={real_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.4f})")

    print(f"\nMultiple-testing correction (best-of-K; K floor from the real, disclosed")
    print(f"v1.00-v1.18 version history in MSG_Trader_EA.mq5's own header):")
    boot_rng = np.random.default_rng(RNG_SEED + 1)
    for K in K_LIST:
        boots = boot_rng.choice(pool, size=(2000, K), replace=True).max(axis=1)
        med, p95 = np.median(boots), np.percentile(boots, 95)
        p = (boots >= real_pf).mean()
        verdict = "SURVIVES" if p < 0.05 else "fails"
        print(f"  K={K:4d}: best-of-K median={med:.3f}  p95={p95:.3f}  p={p:.4f}  [{verdict}]")
