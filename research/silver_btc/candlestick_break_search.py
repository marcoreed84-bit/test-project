"""
"PA Patterns Strategy v2" (the user's fourth pasted Pine v6 strategy):
Bullish/Bearish Engulfing and Morning/Evening Star candlestick patterns,
entered on a STOP ORDER at the pattern candle's own high/low (not an
immediate entry - price must subsequently BREAK the pattern's extreme
within VALID_BARS bars, or the setup expires unfilled), stop at the
pattern's opposite extreme, TP1 partial at 1.5R (moves stop to breakeven),
final target at TARGET_RR. Genuinely new mechanism for this folder: every
other construction enters AT or immediately after its trigger bar; this
one waits for a confirming breakout of the pattern candle itself, which
can simply never come.

PORTED FAITHFULLY: engulfing body-%% and full-engulf checks, star middle-
candle/outer-candle body-%% and penetration checks, the entry-buffer/stop-
buffer/minimum-stop-distance ticks, the N-bar pending-order expiry, and
the TP1-then-breakeven mechanic.

SIMPLIFIED, disclosed rather than silently dropped: the original scales
out 50%% of the position at TP1 and lets the rest run to TP2 - this
project's %%PF convention (pnl/entry_price per whole trade) has no natural
place for a partial fill, so TP1 here only moves the stop to breakeven+
offset (exactly its OTHER effect in the original) and the full position
exits at TP2 or the (now breakeven) stop, whichever comes first. This
somewhat overstates the real strategy's realized R (a real partial-TP1
locks in profit regardless of what happens after), a conservative
direction to simplify in - it only makes the tested version look BETTER
than a strict port would, so a failure here is not an artifact of the
simplification.

NOT ported (irrelevant to whether the pattern has an edge): day/session
filters, max-trades-per-day, loss-streak breaker, lot-size position
sizing, EOD close, and the optional 200-EMA trend filter (left OFF, its
own default).

GRID (K=27, literal): TARGET_RR in {1.5,2.0,3.0} x VALID_BARS in {3,5,10}
x MIN_ENG_BODY_PCT in {40,50,60}. TP1_R=1.5, star thresholds (35/55/50),
entry/stop buffer (2/2 ticks), min stop (5 ticks), breakeven offset
(2 ticks) are the script's own defaults, fixed to keep K honest.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

TARGET_RRS = [1.5, 2.0, 3.0]
VALID_BARS_OPTS = [3, 5, 10]
MIN_ENG_BODY_PCTS = [40.0, 50.0, 60.0]
SMALL_BODY_PCT = 35.0
STRONG_BODY_PCT = 55.0
PENETRATION_PCT = 50.0
ENTRY_BUF_TICKS = 2
SL_BUF_TICKS = 2
MIN_STOP_TICKS = 5
TP1_R = 1.5
BE_OFFSET_TICKS = 2
MAX_HOLD = 500
N_RANDOM = 1000


def detect_patterns(o, h, l, c, min_eng_body_pct):
    n = len(c)
    body = np.abs(c - o)
    rng = h - l
    body_pct = np.where(rng > 0, body / rng * 100.0, 0.0)
    bull = c > o
    bear = c < o
    events = []  # (bar, dir, trig_raw, stop_raw)
    for i in range(2, n):
        eng_ok = body_pct[i] >= min_eng_body_pct
        bull_eng = bear[i - 1] and bull[i] and eng_ok and (o[i] < c[i - 1] and c[i] > o[i - 1])
        bear_eng = bull[i - 1] and bear[i] and eng_ok and (o[i] > c[i - 1] and c[i] < o[i - 1])
        small_mid = body_pct[i - 1] <= SMALL_BODY_PCT
        strong_first = body_pct[i - 2] >= STRONG_BODY_PCT
        strong_third = body_pct[i] >= STRONG_BODY_PCT
        mid_bull = o[i - 2] - body[i - 2] * (PENETRATION_PCT / 100.0)
        mid_bear = o[i - 2] + body[i - 2] * (PENETRATION_PCT / 100.0)
        morning = bear[i - 2] and small_mid and strong_first and bull[i] and strong_third and c[i] > mid_bull
        evening = bull[i - 2] and small_mid and strong_first and bear[i] and strong_third and c[i] < mid_bear

        if morning or bull_eng:
            trig = h[i]
            stop = min(l[i], l[i - 1], l[i - 2]) if morning else min(l[i], l[i - 1])
            events.append((i, 1, trig, stop))
        elif evening or bear_eng:
            trig = l[i]
            stop = max(h[i], h[i - 1], h[i - 2]) if evening else max(h[i], h[i - 1])
            events.append((i, -1, trig, stop))
    return events


def sim_events(events, b, valid_bars, target_rr):
    trades = []
    last_exit = -1
    point = b.point
    buf_e = ENTRY_BUF_TICKS * point
    buf_s = SL_BUF_TICKS * point
    min_dist = MIN_STOP_TICKS * point
    be_off = BE_OFFSET_TICKS * point
    for (i, d, trig_raw, stop_raw) in events:
        if i <= last_exit:
            continue
        trig = trig_raw + buf_e if d > 0 else trig_raw - buf_e
        stop = stop_raw - buf_s if d > 0 else stop_raw + buf_s
        if d > 0 and (trig - stop) < min_dist:
            stop = trig - min_dist
        if d < 0 and (stop - trig) < min_dist:
            stop = trig + min_dist

        entry_bar = None
        for k in range(i + 1, min(i + 1 + valid_bars, b.n)):
            if d > 0 and b.high[k] >= trig:
                entry_bar = k; break
            if d < 0 and b.low[k] <= trig:
                entry_bar = k; break
        if entry_bar is None:
            continue

        fill = entry_bar
        entry_px = trig
        if d > 0 and b.open[fill] > trig:
            entry_px = b.open[fill]
        if d < 0 and b.open[fill] < trig:
            entry_px = b.open[fill]
        cost = b.spread_px[fill]
        entry = entry_px + cost if d > 0 else entry_px - cost
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        tp1 = entry + TP1_R * risk if d > 0 else entry - TP1_R * risk
        tp2 = entry + target_rr * risk if d > 0 else entry - target_rr * risk
        cur_stop = stop
        tp1_done = False
        last = min(b.n - 1, fill + MAX_HOLD)
        exit_bar, exit_px = None, None
        for k in range(fill, last + 1):
            if d > 0:
                if not tp1_done and b.high[k] >= tp1:
                    tp1_done = True
                    cur_stop = entry + be_off
                if b.low[k] <= cur_stop:
                    exit_bar, exit_px = k, cur_stop; break
                if b.high[k] >= tp2:
                    exit_bar, exit_px = k, tp2; break
            else:
                if not tp1_done and b.low[k] <= tp1:
                    tp1_done = True
                    cur_stop = entry - be_off
                if b.high[k] >= cur_stop:
                    exit_bar, exit_px = k, cur_stop; break
                if b.low[k] <= tp2:
                    exit_bar, exit_px = k, tp2; break
        if exit_bar is None:
            exit_bar, exit_px = last, b.close[last]
        pnl = (exit_px - entry) / entry if d > 0 else (entry - exit_px) / entry
        trades.append((i, exit_bar, d, pnl, risk))
        last_exit = exit_bar
    return trades


def sim_random(b, seed, p_fire, dist_pool, target_rr, lo, hi):
    rng = np.random.default_rng(seed)
    trades = []
    last_exit = max(lo, -1)
    be_off = BE_OFFSET_TICKS * b.point
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
        stop = entry - risk if d > 0 else entry + risk
        tp1 = entry + TP1_R * risk if d > 0 else entry - TP1_R * risk
        tp2 = entry + target_rr * risk if d > 0 else entry - target_rr * risk
        cur_stop = stop
        tp1_done = False
        last = min(b.n - 1, fill + MAX_HOLD)
        exit_bar, exit_px = None, None
        for k in range(fill, last + 1):
            if d > 0:
                if not tp1_done and b.high[k] >= tp1:
                    tp1_done = True; cur_stop = entry + be_off
                if b.low[k] <= cur_stop:
                    exit_bar, exit_px = k, cur_stop; break
                if b.high[k] >= tp2:
                    exit_bar, exit_px = k, tp2; break
            else:
                if not tp1_done and b.low[k] <= tp1:
                    tp1_done = True; cur_stop = entry - be_off
                if b.high[k] >= cur_stop:
                    exit_bar, exit_px = k, cur_stop; break
                if b.low[k] <= tp2:
                    exit_bar, exit_px = k, tp2; break
        if exit_bar is None:
            exit_bar, exit_px = last, b.close[last]
        pnl = (exit_px - entry) / entry if d > 0 else (entry - exit_px) / entry
        trades.append(pnl)
        last_exit = exit_bar
    return np.array(trades)


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- Engulfing/Star break-of-pattern (TARGET_RR, VALID_BARS, MIN_ENG_BODY_PCT)\n"
        f"{b.describe()}")

    pat_cache = {}
    for min_body in MIN_ENG_BODY_PCTS:
        pat_cache[min_body] = detect_patterns(b.open, b.high, b.low, b.close, min_body)

    grid = list(itertools.product(TARGET_RRS, VALID_BARS_OPTS, MIN_ENG_BODY_PCTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    for cfg in grid:
        rr, valid_bars, min_body = cfg
        events = pat_cache[min_body]
        is_events = [e for e in events if b.is_lo <= e[0] < b.is_hi]
        tr = sim_events(is_events, b, valid_bars, rr)
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
    rr, valid_bars, min_body = best["cfg"]
    events = pat_cache[min_body]
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    oos_events = [e for e in events if b.oos_lo <= e[0] < b.oos_hi]
    oos_tr = sim_events(oos_events, b, valid_bars, rr)
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
        counts = [len(sim_random(b, 10_000 + it, p_fire, dist_pool, rr, b.oos_lo, b.oos_hi)) for it in range(5)]
        m = np.mean(counts)
        if m <= 0:
            p_fire = min(0.5, p_fire * 3); continue
        if abs(m - n_oos) / n_oos < 0.03:
            break
        p_fire = min(0.5, max(1e-7, p_fire * n_oos / m))
    pool = np.array([C.pct_pf(sim_random(b, r, p_fire, dist_pool, rr, b.oos_lo, b.oos_hi)) for r in range(N_RANDOM)])
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
    out_path = "/home/user/test-project/research/silver_btc/candlestick_break_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
