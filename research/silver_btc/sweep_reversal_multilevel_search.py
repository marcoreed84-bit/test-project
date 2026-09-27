"""
"Liquidity Sweep Reversal Strategy" (the user's eighth pasted Pine v6
strategy): maintains a LIVE LIST of unswept swing-pivot highs/lows (not
just the most recent one, and not a fixed session range) - each new
confirmed pivot becomes a watched level (deduped against nearby existing
levels), aged out after MAX_AGE bars if never swept. A level is "swept"
when a bar wicks through it and closes back on the other side, with
optional wick:body-ratio and volume-spike filters, and an optional
one-extra-bar confirmation (price must continue past the sweep bar's
own midpoint before entering - reduces whipsaws). Stop = the swept
wick's own extreme +/- an ATR buffer (not the entry price), R:R target,
with an ATR minimum-risk floor (rejects trades whose structural stop
would be unrealistically tight) and a breakeven-move once price gets
partway to target. Genuinely more elaborate than the earlier sweep
constructions (Liquidity Sweep+Reclaim used 4 fixed level TYPES with no
filters or confirmation; Opening-Range Sweep+Return used one session-
anchored range) - a real multi-level watchlist with quality filters is
a mechanically distinct bet on the same underlying idea, worth testing
on its own rather than assuming the prior verdicts carry over.

PORTED FAITHFULLY: pivot-based level creation/dedup/aging (common.
pivots() for the swing detection, matching ta.pivothigh/low(len,len)),
the wick-through-and-close-back sweep test with wick:body and volume
filters, the aggregated-wick-extreme-across-multiple-simultaneously-
swept-levels behavior, the next-bar confirmation state machine, the ATR-
buffer-beyond-the-wick stop with the minimum-risk-ATR floor, the R:R
target, and the breakeven-at-X%%-to-target stop move.

SIMPLIFIED, disclosed: (1) the original only evaluates new entries/
confirmation while flat (`strategy.position_size == 0`), and any sweep
that happens during an open trade is simply dropped, never queued -
here, level tracking and sweep-signal generation run unconditionally
(matching the original) but position-gating is done afterward via the
standard "skip a signal whose bar falls before the last trade's exit"
convention already used throughout this folder - slightly MORE
permissive than the original (a sweep during an open trade can still
be traded once flat again here, rather than being lost), a
conservative direction to simplify in. (2) SESSION TIMEZONE: no
confirmed "exchange time" offset exists for this broker's Gold/Silver/
BTC feeds, so the 12:00-16:00 session window is applied to each bar's
own timestamp hour directly (broker server time) - the same
approximation already disclosed for the two earlier session-based
scripts this session.

GRID (K=27, literal): SL_ATR_MULT in {0.8,1.2,1.8} x RR_RATIO in
{1.0,1.5,2.5} x PIVOT_LEN in {5,7,10}. MAX_AGE=150, MIN_GAP_ATR=0.25,
MIN_RISK_ATR=0.5, VOL_MULT=1.3, MIN_WICK_RATIO=1.5, BE_PCT=50 are the
script's own defaults, fixed to keep K honest. Volume filter, wick
filter, next-bar confirmation, session restriction, and breakeven are
all left ON, matching the script's own defaults; both directions allowed.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

SL_ATR_MULTS = [0.8, 1.2, 1.8]
RR_RATIOS = [1.0, 1.5, 2.5]
PIVOT_LENS = [5, 7, 10]
MAX_AGE = 150
MIN_GAP_ATR = 0.25
MIN_RISK_ATR = 0.5
VOL_MULT = 1.3
MIN_WICK_RATIO = 1.5
BE_PCT = 50.0
VOL_SMA_LEN = 20
SESS_START_MIN, SESS_END_MIN = 12 * 60, 16 * 60
MAX_HOLD = 500
N_RANDOM = 1000


def detect_events(o, h, l, c, vol, vol_sma, atr, ph, pl, session_mask):
    n = len(c)
    highs, lows = [], []
    events = []  # (bar, dir, wick_level)
    pending_long = pending_short = False
    pending_wick = pending_mid = np.nan

    for i in range(n):
        sweep_high, wick_h = False, np.nan
        keep = []
        for price, bar in highs:
            wicked = h[i] > price and c[i] < price
            body = abs(c[i] - o[i])
            wsz = h[i] - max(c[i], o[i])
            wick_ok = (body > 0 and wsz / body >= MIN_WICK_RATIO) or (body == 0 and wsz > 0)
            vol_ok = vol[i] > vol_sma[i] * VOL_MULT if not np.isnan(vol_sma[i]) else False
            if wicked and vol_ok and wick_ok:
                sweep_high = True
                wick_h = h[i] if np.isnan(wick_h) else max(wick_h, h[i])
            elif (i - bar) > MAX_AGE:
                pass
            else:
                keep.append((price, bar))
        highs = keep

        sweep_low, wick_l = False, np.nan
        keep = []
        for price, bar in lows:
            wicked = l[i] < price and c[i] > price
            body = abs(c[i] - o[i])
            wsz = min(c[i], o[i]) - l[i]
            wick_ok = (body > 0 and wsz / body >= MIN_WICK_RATIO) or (body == 0 and wsz > 0)
            vol_ok = vol[i] > vol_sma[i] * VOL_MULT if not np.isnan(vol_sma[i]) else False
            if wicked and vol_ok and wick_ok:
                sweep_low = True
                wick_l = l[i] if np.isnan(wick_l) else min(wick_l, l[i])
            elif (i - bar) > MAX_AGE:
                pass
            else:
                keep.append((price, bar))
        lows = keep

        a = atr[i] if not np.isnan(atr[i]) else 0.0
        if not np.isnan(ph[i]):
            px = ph[i]
            if not any(abs(pp - px) < a * MIN_GAP_ATR for pp, _ in highs):
                highs.append((px, i))
        if not np.isnan(pl[i]):
            px = pl[i]
            if not any(abs(pp - px) < a * MIN_GAP_ATR for pp, _ in lows):
                lows.append((px, i))

        sess_ok = session_mask[i]
        if pending_long and c[i] > pending_mid and sess_ok:
            events.append((i, 1, pending_wick))
        if pending_short and c[i] < pending_mid and sess_ok:
            events.append((i, -1, pending_wick))
        pending_long = False
        pending_short = False
        if sweep_low:
            pending_long = True
            pending_wick = wick_l
            pending_mid = (wick_l + c[i]) / 2.0
        if sweep_high:
            pending_short = True
            pending_wick = wick_h
            pending_mid = (wick_h + c[i]) / 2.0
    return events


def calc_levels(is_long, wick_lvl, entry, atr_i, sl_mult, rr_ratio):
    sl = wick_lvl - sl_mult * atr_i if is_long else wick_lvl + sl_mult * atr_i
    risk = entry - sl if is_long else sl - entry
    qualifies = risk >= MIN_RISK_ATR * atr_i and risk > 0
    tp = (entry + risk * rr_ratio) if (qualifies and is_long) else (entry - risk * rr_ratio) if qualifies else np.nan
    return qualifies, sl, tp


def sim_events(events, b, sl_mult, rr_ratio):
    trades = []
    last_exit = -1
    for (i, d, wick_lvl) in events:
        if i <= last_exit or i + 1 >= b.n:
            continue
        fill = i + 1
        atr_i = b.atr[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue
        cost = b.spread_px[fill]
        raw = b.close[i]
        entry = raw + cost if d > 0 else raw - cost
        qualifies, sl, tp = calc_levels(d > 0, wick_lvl, entry, atr_i, sl_mult, rr_ratio)
        if not qualifies:
            continue
        be_trig = entry + (tp - entry) * (BE_PCT / 100.0) if d > 0 else entry - (entry - tp) * (BE_PCT / 100.0)
        cur_stop = sl
        be_done = False
        last = min(b.n - 1, fill + MAX_HOLD)
        exit_bar, exit_px = None, None
        for k in range(fill, last + 1):
            if d > 0:
                if not be_done and b.high[k] >= be_trig:
                    be_done = True; cur_stop = entry
                if b.low[k] <= cur_stop:
                    exit_bar, exit_px = k, cur_stop; break
                if b.high[k] >= tp:
                    exit_bar, exit_px = k, tp; break
            else:
                if not be_done and b.low[k] <= be_trig:
                    be_done = True; cur_stop = entry
                if b.high[k] >= cur_stop:
                    exit_bar, exit_px = k, cur_stop; break
                if b.low[k] <= tp:
                    exit_bar, exit_px = k, tp; break
        if exit_bar is None:
            exit_bar, exit_px = last, b.close[last]
        pnl = (exit_px - entry) / entry if d > 0 else (entry - exit_px) / entry
        trades.append((i, exit_bar, d, pnl, abs(entry - sl)))
        last_exit = exit_bar
    return trades


def sim_random(b, seed, p_fire, dist_pool, rr_ratio, lo, hi):
    rng = np.random.default_rng(seed)
    trades = []
    last_exit = max(lo, -1)
    for i in range(lo, min(hi, b.n - 1)):
        if i <= last_exit or rng.random() >= p_fire:
            continue
        d = 1 if rng.random() < 0.5 else -1
        fill = i + 1
        if fill >= b.n:
            continue
        cost = b.spread_px[fill]
        raw = b.close[i]
        entry = raw + cost if d > 0 else raw - cost
        risk = dist_pool[rng.integers(0, len(dist_pool))]
        sl = entry - risk if d > 0 else entry + risk
        tp = entry + risk * rr_ratio if d > 0 else entry - risk * rr_ratio
        be_trig = entry + (tp - entry) * (BE_PCT / 100.0) if d > 0 else entry - (entry - tp) * (BE_PCT / 100.0)
        cur_stop = sl
        be_done = False
        last = min(b.n - 1, fill + MAX_HOLD)
        exit_bar, exit_px = None, None
        for k in range(fill, last + 1):
            if d > 0:
                if not be_done and b.high[k] >= be_trig:
                    be_done = True; cur_stop = entry
                if b.low[k] <= cur_stop:
                    exit_bar, exit_px = k, cur_stop; break
                if b.high[k] >= tp:
                    exit_bar, exit_px = k, tp; break
            else:
                if not be_done and b.low[k] <= be_trig:
                    be_done = True; cur_stop = entry
                if b.high[k] >= cur_stop:
                    exit_bar, exit_px = k, cur_stop; break
                if b.low[k] <= tp:
                    exit_bar, exit_px = k, tp; break
        if exit_bar is None:
            exit_bar, exit_px = last, b.close[last]
        pnl = (exit_px - entry) / entry if d > 0 else (entry - exit_px) / entry
        trades.append(pnl)
        last_exit = exit_bar
    return np.array(trades)


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- Multi-Level Sweep Reversal (SL_ATR_MULT, RR_RATIO, PIVOT_LEN)\n{b.describe()}")

    vol_sma = C.sma(b.vol, VOL_SMA_LEN)
    time_idx = pd.to_datetime(b.time)
    minute_of_day = (time_idx.hour * 60 + time_idx.minute).values
    session_mask = (minute_of_day >= SESS_START_MIN) & (minute_of_day < SESS_END_MIN)

    piv_cache = {}
    for pl_len in PIVOT_LENS:
        ph, pl = C.pivots(b.high, b.low, pl_len)
        events = detect_events(b.open, b.high, b.low, b.close, b.vol, vol_sma, b.atr, ph, pl, session_mask)
        piv_cache[pl_len] = events
        log(f"  pivot_len={pl_len}: {len(events)} raw confirmed events")

    grid = list(itertools.product(SL_ATR_MULTS, RR_RATIOS, PIVOT_LENS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    for cfg in grid:
        sl_mult, rr_ratio, pl_len = cfg
        events = piv_cache[pl_len]
        is_events = [e for e in events if b.is_lo <= e[0] < b.is_hi]
        tr = sim_events(is_events, b, sl_mult, rr_ratio)
        if len(tr) < 100:
            continue
        pnl = np.array([t[3] for t in tr])
        rows.append(dict(cfg=cfg, n=len(tr), pf=C.pct_pf(pnl)))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>=100. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    sl_mult, rr_ratio, pl_len = best["cfg"]
    events = piv_cache[pl_len]
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    oos_events = [e for e in events if b.oos_lo <= e[0] < b.oos_hi]
    oos_tr = sim_events(oos_events, b, sl_mult, rr_ratio)
    if not oos_tr:
        log("No OOS trades."); return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (0 OOS trades)")
    n_oos = len(oos_tr)
    pnl = np.array([t[3] for t in oos_tr])
    dist_pool = np.array([t[4] for t in oos_tr])
    oos_pf = C.pct_pf(pnl)
    log(f"OOS (untouched): n={n_oos}  win%={100*(pnl>0).mean():.1f}  %PF={oos_pf:.3f}  sum%={100*pnl.sum():.1f}")
    if n_oos < 20:
        log("Too few OOS trades -> DOES NOT SURVIVE (insufficient evidence).")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (n<20)")

    p_fire = min(0.5, max(1e-6, n_oos / max(1, b.oos_hi - b.oos_lo) * 3))
    for _ in range(8):
        counts = [len(sim_random(b, 10_000 + it, p_fire, dist_pool, rr_ratio, b.oos_lo, b.oos_hi)) for it in range(5)]
        m = np.mean(counts)
        if m <= 0:
            p_fire = min(0.5, p_fire * 3); continue
        if abs(m - n_oos) / n_oos < 0.03:
            break
        p_fire = min(0.5, max(1e-7, p_fire * n_oos / m))
    pool = np.array([C.pct_pf(sim_random(b, r, p_fire, dist_pool, rr_ratio, b.oos_lo, b.oos_hi)) for r in range(N_RANDOM)])
    pool = pool[np.isfinite(pool)]
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = C.best_of_k_p(pool, oos_pf, K)
    log(f"random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}): median={np.median(pool):.3f}  "
        f"p95={np.percentile(pool,95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{C.verdict(pK)}]")
    return dict(label=symbol, K=K, cfg=best["cfg"], is_n=best["n"], is_pf=best["pf"], oos_n=n_oos, oos_pf=oos_pf,
                pctile=pctile, p1=p1, pK=pK, verdict=C.verdict(pK) if p1 < 0.05 else C.verdict(max(p1, pK)))


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/sweep_reversal_multilevel_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
