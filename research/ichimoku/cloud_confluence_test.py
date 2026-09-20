"""
Same cloud touch-and-reject construction as cloud_stoch_test.py (Stochastic
oversold/overbought, already REJECTED via walk-forward), swapping the
confirmation indicator for four others: MACD, Bollinger Bands, Fair Value
Gap, and liquidity sweep OF THE CLOUD EDGE ITSELF. RSI/VWAP/moving-averages
excluded - already covered elsewhere this session.

WALK-FORWARD BUILT IN FROM THE START this time - the Stochastic candidate's
lesson: a single 70/30 split hid a dead-in-recent-data signal behind a
strong middle period. Every construction below reports both the aggregate
IS/OOS AND the 5-independent-block breakdown together, not as a follow-up.

Same base cloud definition as cloud_stoch_test.py (bullish cloud = Senkou A
> Senkou B, touch tolerance/reject margin both 0.30xATR, 8-bar lookback for
the touch) - only the confirmation signal changes per construction, so any
difference in results is attributable to the new indicator, not a changed
cloud definition.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E

POINT = 0.01
LOOKBACK = 8
TOL_ATR = 0.30
REJECT_ATR = 0.30
N_RANDOM_SEEDS = 2000
N_BLOCKS = 5
MAXHOLD = 12


def tp_sl_outcomes(ctx, triggers, tp_atr, sl_atr, maxhold=MAXHOLD):
    close, high, low, atr, spread, n = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"], ctx["n"]
    out, dropped = [], 0
    for i, real_dir in triggers:
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        entry_buy, entry_sell = raw + sc, raw - sc
        tp_buy, sl_buy = entry_buy + tp_atr * atr[i], entry_buy - sl_atr * atr[i]
        tp_sell, sl_sell = entry_sell - tp_atr * atr[i], entry_sell + sl_atr * atr[i]
        pnl_buy = pnl_sell = None
        for k in range(fill_i, min(fill_i + maxhold, n)):
            if pnl_buy is None:
                ht, hs = high[k] >= tp_buy, low[k] <= sl_buy
                if ht or hs: pnl_buy = (sl_buy - entry_buy) if hs else (tp_buy - entry_buy)
            if pnl_sell is None:
                ht, hs = low[k] <= tp_sell, high[k] >= sl_sell
                if ht or hs: pnl_sell = (entry_sell - sl_sell) if hs else (entry_sell - tp_sell)
            if pnl_buy is not None and pnl_sell is not None:
                break
        if pnl_buy is None or pnl_sell is None:
            dropped += 1; continue
        out.append((pnl_buy, pnl_sell, i, real_dir))
    return out, dropped


def report_and_walkforward(label, out, ctx, dropped, n_trig, n_blocks=N_BLOCKS):
    n = ctx["n"]
    if not out:
        print(f"  {label}: 0 resolved, skip")
        return
    pnl_buy = np.array([o[0] for o in out]); pnl_sell = np.array([o[1] for o in out])
    entry_i = np.array([o[2] for o in out]); real_dir = np.array([o[3] for o in out])
    real_pnl = np.where(real_dir > 0, pnl_buy, pnl_sell)
    net = real_pnl.sum()
    rng = np.random.default_rng(0)
    rdir = rng.integers(0, 2, size=(N_RANDOM_SEEDS, len(out)))
    rn = np.where(rdir == 1, pnl_buy, pnl_sell).sum(axis=1)
    pct = 100 * (rn < net).mean()
    cutoff = int(n * 0.7)
    ism = entry_i < cutoff
    print(f"  {label} (dropped={dropped}/{n_trig}): n={len(out)} net={net:.2f} "
          f"win%={100*(real_pnl>0).mean():.1f} IS={real_pnl[ism].sum():.2f} "
          f"OOS={real_pnl[~ism].sum():.2f} agg-random-dir%ile={pct:.1f}")
    if len(out) < 20:
        print(f"    (n<20, skipping block breakdown - too few for 5 blocks to mean anything)")
        return
    edges = np.linspace(0, n, n_blocks + 1).astype(int)
    pos = 0
    for b in range(n_blocks):
        lo, hi = edges[b], edges[b+1]
        m = (entry_i >= lo) & (entry_i < hi)
        nb = m.sum()
        if nb == 0:
            print(f"    block {b+1}: 0 trades"); continue
        netb = real_pnl[m].sum()
        rngb = np.random.default_rng(100+b)
        rdb = rngb.integers(0, 2, size=(2000, nb))
        rnb = np.where(rdb == 1, pnl_buy[m], pnl_sell[m]).sum(axis=1)
        pctb = 100 * (rnb < netb).mean()
        t0 = pd.to_datetime(ctx["time"][lo]).date(); t1 = pd.to_datetime(ctx["time"][min(hi, n-1)]).date()
        if netb > 0: pos += 1
        print(f"    block {b+1} [{t0}->{t1}]: n={nb} net={netb:.2f} random-dir%ile={pctb:.1f}")
    print(f"    -> positive in {pos}/{n_blocks} blocks")


def edge_trigger(sig_buy, sig_sell):
    tb = sig_buy & ~np.concatenate(([False], sig_buy[:-1]))
    ts = sig_sell & ~np.concatenate(([False], sig_sell[:-1]))
    trig = [(i, 1.0) for i in np.where(tb)[0]] + [(i, -1.0) for i in np.where(ts)[0]]
    trig.sort(key=lambda t: t[0])
    return trig


if __name__ == "__main__":
    d = E.load_h4()
    p = E.params()
    ctx = E.build_context(d, p)
    n = ctx["n"]
    high, low, close, atr = ctx["high"], ctx["low"], ctx["close"], ctx["atr"]
    cloud_top, cloud_bot = ctx["cloud_top"], ctx["cloud_bot"]
    ctx["spread"] = d["spread"].values.astype(float)

    D = p["displacement"]
    sa_sh = pd.Series(ctx["sa_raw"]).shift(D).values
    sb_sh = pd.Series(ctx["sb_raw"]).shift(D).values
    is_bull_cloud = sa_sh > sb_sh
    is_bear_cloud = sb_sh > sa_sh

    print(f"n_bars={n} (H4, ~{n/6:.0f} trading days)\n")

    def touch_reject(bull_confirm_fn, bear_confirm_fn):
        """bull_confirm_fn(j) / bear_confirm_fn(j) -> bool, checked over the
        same LOOKBACK window as the touch, exactly like cloud_stoch_test's
        oversold/overbought slot."""
        bull_sig = np.zeros(n, dtype=bool); bear_sig = np.zeros(n, dtype=bool)
        for i in range(LOOKBACK, n):
            if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(cloud_top[i]) or np.isnan(cloud_bot[i]):
                continue
            tol, rej = TOL_ATR * atr[i], REJECT_ATR * atr[i]
            win = range(max(0, i - LOOKBACK + 1), i + 1)
            if is_bull_cloud[i]:
                touched = any(low[j] <= cloud_top[i] + tol for j in win)
                confirmed = any(bull_confirm_fn(j) for j in win)
                rejected = close[i] - cloud_top[i] >= rej
                bull_sig[i] = touched and confirmed and rejected
            if is_bear_cloud[i]:
                touched = any(high[j] >= cloud_bot[i] - tol for j in win)
                confirmed = any(bear_confirm_fn(j) for j in win)
                rejected = cloud_bot[i] - close[i] >= rej
                bear_sig[i] = touched and confirmed and rejected
        return edge_trigger(bull_sig, bear_sig)

    def run(name, triggers):
        print("=" * 70)
        print(f"{name}: {len(triggers)} triggers -> {len(triggers)/(n/6):.3f}/day")
        if len(triggers) < 10:
            print("  too few triggers, skipping"); return
        for tp_atr, sl_atr in ((1.0, 1.0), (2.0, 1.5), (2.5, 1.5)):
            out, dropped = tp_sl_outcomes(ctx, triggers, tp_atr, sl_atr)
            report_and_walkforward(f"tp={tp_atr}xATR sl={sl_atr}xATR", out, ctx, dropped, len(triggers))

    # ============================================================ MACD
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd_line = ema12 - ema26
    macd_sig = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    macd_hist = macd_line - macd_sig
    run("CLOUD + MACD (histogram > 0 in window = bull confirm)",
        touch_reject(lambda j: (not np.isnan(macd_hist[j])) and macd_hist[j] > 0,
                     lambda j: (not np.isnan(macd_hist[j])) and macd_hist[j] < 0))

    # ============================================================ BOLLINGER
    BB_PERIOD, BB_MULT = 20, 2.0
    sma = pd.Series(close).rolling(BB_PERIOD).mean().values
    std = pd.Series(close).rolling(BB_PERIOD).std().values
    bb_lower = sma - BB_MULT * std
    bb_upper = sma + BB_MULT * std
    run("CLOUD + BOLLINGER (price also touched lower/upper band in window)",
        touch_reject(lambda j: (not np.isnan(bb_lower[j])) and low[j] <= bb_lower[j],
                     lambda j: (not np.isnan(bb_upper[j])) and high[j] >= bb_upper[j]))

    # ============================================================ FVG
    bull_fvg_at = np.zeros(n, dtype=bool)
    bear_fvg_at = np.zeros(n, dtype=bool)
    bull_fvg_at[2:] = low[2:] > high[:-2]
    bear_fvg_at[2:] = high[2:] < low[:-2]
    run("CLOUD + FVG (a same-direction Fair Value Gap formed in window)",
        touch_reject(lambda j: bull_fvg_at[j], lambda j: bear_fvg_at[j]))

    # ============================================================ LIQUIDITY SWEEP OF THE CLOUD EDGE
    # Different construction (no separate confirmation slot needed): a
    # genuine WICK beyond the cloud edge (not just a touch within
    # tolerance), then close back inside - the cloud edge itself as the
    # liquidity level being swept, arguably the most literal "liquidity +
    # cloud" reading.
    SWEEP_ATR = 0.15  # how far beyond the edge counts as a real sweep, not just a touch
    bull_sig = np.zeros(n, dtype=bool); bear_sig = np.zeros(n, dtype=bool)
    for i in range(n):
        if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(cloud_top[i]) or np.isnan(cloud_bot[i]):
            continue
        if is_bull_cloud[i]:
            swept = low[i] <= cloud_top[i] - SWEEP_ATR * atr[i]
            rejected = close[i] > cloud_top[i]
            bull_sig[i] = swept and rejected
        if is_bear_cloud[i]:
            swept = high[i] >= cloud_bot[i] + SWEEP_ATR * atr[i]
            rejected = close[i] < cloud_bot[i]
            bear_sig[i] = swept and rejected
    trig = edge_trigger(bull_sig, bear_sig)
    run("CLOUD EDGE LIQUIDITY SWEEP (wick through the cloud, close back inside, same bar)", trig)
