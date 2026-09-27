"""
"EWO,RSI advanced Signals Strategy - Exhaustion Filter" (the user's
thirteenth pasted Pine v6 strategy, Pridarasx): Elliott Wave Oscillator
(EWO = SMA(hl2,5) - SMA(hl2,34)) turning up/down, an RSI 40/60 cross,
an MFI confirmation, a volume filter, and a breakout-barrier (close
above the trailing N-bar high) OR a sticky "recent deep-oversold
capitulation" flag as the buy-side confirmation gate. NO stop-loss or
take-profit anywhere in the script - pure stop-and-reverse, alternating
buy/sell signals close and flip the position, modeled the same way as
this folder's other hold-until-reversal scripts (a practically-
unreachable stop stands in for none, target_r=0). Genuinely new
mechanism: momentum-oscillator confluence with a stateful "exhaustion
memory" flag, not tried anywhere else this session.

PORTED FAITHFULLY, including two genuinely STATEFUL mechanics requiring
an explicit bar-by-bar loop (not vectorizable - both have a same-bar
read-before-write dependency): (1) `oversold_zone`, a sticky flag set
whenever RSI drops below the exhaustion threshold and only cleared by a
confirmed buy signal - it can stay true for many bars, carrying "the
market recently capitulated" memory forward; (2) `last_signal`
alternation - a raw buy/sell condition only becomes a real signal if
the last CONFIRMED signal was the opposite side, so two raw buys in a
row without an intervening sell only fire once. Also implemented MFI
(money flow index) and Wilder RSI from scratch (common.py has neither
yet) - both standard textbook constructions, validated against known
oscillator bounds [0,100] before trusting them.

GRID (K=27, literal): RSI_OVERSOLD in {20,30,40} x LOOKBACK_LEN in
{5,10,20} x VOL_OK_MULT in {0.5,0.8,1.2}. EWO fast/slow (5/34), RSI/MFI
length (14/14), volume MA length (20), and the RSI 40/60 cross levels
are the script's own defaults, fixed to keep K honest.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

RSI_OVERSOLDS = [20, 30, 40]
LOOKBACK_LENS = [5, 10, 20]
VOL_OK_MULTS = [0.5, 0.8, 1.2]
EWO_FAST, EWO_SLOW = 5, 34
RSI_LEN, MFI_LEN, VOL_MA_LEN = 14, 14, 20
NO_STOP_ATR_MULT = 50.0


def wilder_rsi(c, period):
    n = len(c)
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)
    if n <= period:
        return np.full(n, np.nan)
    avg_gain[period] = gain[1:period + 1].mean()
    avg_loss[period] = loss[1:period + 1].mean()
    for i in range(period + 1, n):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        out = np.where(avg_loss == 0, 100.0, 100.0 - 100.0 / (1.0 + rs))
    return out


def money_flow_index(h, l, c, vol, period):
    n = len(c)
    tp = (h + l + c) / 3.0
    tp_prev = np.concatenate(([np.nan], tp[:-1]))
    raw_mf = tp * vol
    pos_mf = np.where(tp > tp_prev, raw_mf, 0.0)
    neg_mf = np.where(tp < tp_prev, raw_mf, 0.0)
    pos_sum = pd.Series(pos_mf).rolling(period, min_periods=period).sum().values
    neg_sum = pd.Series(neg_mf).rolling(period, min_periods=period).sum().values
    with np.errstate(divide="ignore", invalid="ignore"):
        mfr = np.where(neg_sum > 0, pos_sum / neg_sum, np.inf)
        out = 100.0 - 100.0 / (1.0 + mfr)
    return out


def cross_edges(a, level):
    above = a > level
    above_prev = np.concatenate(([False], above[:-1]))
    valid = ~np.isnan(a)
    valid_prev = np.concatenate(([False], valid[:-1]))
    up = above & ~above_prev & valid & valid_prev
    dn = (~above) & above_prev & valid & valid_prev
    return up, dn


def detect_signals(rsi, mfi, ewo, vol_ok, price_breaking_out, rsi_oversold_th):
    n = len(rsi)
    cross_up_40, _ = cross_edges(rsi, 40.0)
    _, cross_dn_60 = cross_edges(rsi, 60.0)
    ewo_prev = np.concatenate(([np.nan], ewo[:-1]))
    ewo_rising = ewo > ewo_prev
    ewo_falling = ewo < ewo_prev

    buy_events, sell_events = [], []
    oversold_zone = False
    last_signal = 0
    for i in range(n):
        if not np.isnan(rsi[i]) and rsi[i] < rsi_oversold_th:
            oversold_zone = True
        raw_buy = bool(cross_up_40[i] and mfi[i] > 30 and ewo_rising[i] and vol_ok[i] and
                       (price_breaking_out[i] or oversold_zone))
        raw_sell = bool(cross_dn_60[i] and mfi[i] < 70 and ewo_falling[i] and vol_ok[i])
        if raw_buy:
            oversold_zone = False
        if raw_buy and last_signal != 1:
            buy_events.append(i)
            last_signal = 1
        if raw_sell and last_signal != -1:
            sell_events.append(i)
            last_signal = -1
    return np.array(buy_events, dtype=np.int64), np.array(sell_events, dtype=np.int64)


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- EWO/RSI Exhaustion (RSI_OVERSOLD, LOOKBACK_LEN, VOL_OK_MULT)\n{b.describe()}")

    hl2 = (b.high + b.low) / 2.0
    ewo = C.sma(hl2, EWO_FAST) - C.sma(hl2, EWO_SLOW)
    rsi = wilder_rsi(b.close, RSI_LEN)
    mfi = money_flow_index(b.high, b.low, b.close, b.vol, MFI_LEN)
    vol_ma = C.sma(b.vol, VOL_MA_LEN)

    grid = list(itertools.product(RSI_OVERSOLDS, LOOKBACK_LENS, VOL_OK_MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    lookback_cache = {}
    for lb in LOOKBACK_LENS:
        hi_roll = pd.Series(b.high).rolling(lb, min_periods=lb).max().shift(1).values
        lookback_cache[lb] = b.close > hi_roll

    rows = []
    for cfg in grid:
        rsi_os, lb, vol_mult = cfg
        vol_ok = b.vol > vol_ma * vol_mult
        price_breaking_out = lookback_cache[lb]
        buy_bars, sell_bars = detect_signals(rsi, mfi, ewo, vol_ok, price_breaking_out, float(rsi_os))
        if len(buy_bars) == 0 and len(sell_bars) == 0:
            continue

        exit_long = np.zeros(b.n, dtype=np.bool_)
        exit_short = np.zeros(b.n, dtype=np.bool_)
        exit_long[sell_bars] = True
        exit_short[buy_bars] = True

        atr = b.atr
        valid_buy = ~np.isnan(atr[buy_bars]) & (atr[buy_bars] > 0) if len(buy_bars) else buy_bars
        valid_sell = ~np.isnan(atr[sell_bars]) & (atr[sell_bars] > 0) if len(sell_bars) else sell_bars
        bb = buy_bars[valid_buy] if len(buy_bars) else buy_bars
        sb = sell_bars[valid_sell] if len(sell_bars) else sell_bars
        sig_bar = np.concatenate((bb, sb)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(bb)), -np.ones(len(sb))))
        sig_dist = np.concatenate((NO_STOP_ATR_MULT * atr[bb], NO_STOP_ATR_MULT * atr[sb]))
        order = np.argsort(sig_bar, kind="stable")
        sig_bar, sig_dir, sig_dist = sig_bar[order], sig_dir[order], sig_dist[order]

        ex = dict(target_r=0.0, max_hold=100000, trail_atr=0.0, exit_long=exit_long, exit_short=exit_short)
        r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"],
                          b.is_lo, b.is_hi)
        n_tr, pnl = len(r[3]), r[3]
        if n_tr < 100:
            continue
        rows.append(dict(cfg=cfg, n=n_tr, pf=C.pct_pf(pnl), sig_bar=sig_bar, sig_dir=sig_dir, sig_dist=sig_dist, ex=ex))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>=100. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    sig_bar, sig_dir, sig_dist, ex = best["sig_bar"], best["sig_dir"], best["sig_dist"], best["ex"]
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
    r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                      *exargs, b.oos_lo, b.oos_hi)
    oos_pnl, oos_dir, oos_dist = r[3], r[2], r[4]
    n_oos = len(oos_pnl)
    if n_oos == 0:
        log("No OOS trades."); return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (0 OOS trades)")
    oos_pf = C.pct_pf(oos_pnl)
    log(f"OOS (untouched): n={n_oos}  win%={100*(oos_pnl>0).mean():.1f}  %PF={oos_pf:.3f}  sum%={100*oos_pnl.sum():.1f}")
    if n_oos < 20:
        log("Too few OOS trades -> DOES NOT SURVIVE (insufficient evidence).")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (n<20)")

    allowed = np.ones(b.n, dtype=np.bool_)
    pool, p_fire, mean_n = C.random_pool(b, oos_dist, n_oos, *exargs, b.oos_lo, b.oos_hi, allowed)
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = C.best_of_k_p(pool, oos_pf, K)
    log(f"random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={mean_n:.0f}): "
        f"median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{C.verdict(pK)}]")
    return dict(label=symbol, K=K, cfg=best["cfg"], is_n=best["n"], is_pf=best["pf"], oos_n=n_oos, oos_pf=oos_pf,
                pctile=pctile, p1=p1, pK=pK, verdict=C.verdict(pK) if p1 < 0.05 else C.verdict(max(p1, pK)))


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/ewo_rsi_exhaustion_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
