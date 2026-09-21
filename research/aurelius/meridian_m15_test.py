"""
User's ask: has Meridian been tried on M15 instead of M5 - noting that
Aurelius itself turned out to be better suited on M15 than M5
originally (Aurelius_M15_EA.mq5 exists as its own tuned variant, not
just Aurelius run on a different chart).

First pass: the LITERAL port - same nominal periods (21/50 EMA cross,
250 SMA + VWAP + S/R confirm, safety_sl=2.5xATR, hold-to-reversal exit)
on M15 bars instead of M5, exactly as if the same EA were just attached
to an M15 chart with default inputs unchanged. This is the honest
starting point before any M15-specific tuning - same question Aurelius
was asked before Aurelius_M15 was built as a separately-tuned system.

M15 built via engine.resample_m15_from_m5() (lossless, exact 3-bar
aggregation - no new data export needed). VWAP/ATR/S-R distance all
recomputed on the M15 bars directly (VWAP resets per calendar day
either way; S/R still uses the same H4-derived daily levels, which
don't depend on the entry timeframe). Same rigor: real spread, correct
single-position sequencing, drawdown (closed + floating), walk-forward,
random-direction control.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m5_stack_variants_fixed_test import sim_filtered_entries
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
N_RANDOM_SEEDS = 300
SAFETY_SL = 2.5
MIN_SR = 0.50
SR_DAYS = 3


def build_sr_distance(df, h4):
    daily = E.derive_d1_from_h4(h4).sort_values("date").reset_index(drop=True)
    daily["roll_hi"] = daily["high"].rolling(SR_DAYS).max().shift(1)
    daily["roll_lo"] = daily["low"].rolling(SR_DAYS).min().shift(1)
    date_map_hi = dict(zip(daily["date"], daily["roll_hi"]))
    date_map_lo = dict(zip(daily["date"], daily["roll_lo"]))
    bar_date = df["time"].dt.date
    sr_hi = bar_date.map(date_map_hi).values.astype(float)
    sr_lo = bar_date.map(date_map_lo).values.astype(float)
    return sr_hi, sr_lo


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    df15 = E.resample_m15_from_m5(df5)
    n = len(df15)
    close = df15["close"].values.astype(float)
    high = df15["high"].values.astype(float)
    low = df15["low"].values.astype(float)
    spread = df15["spread"].values.astype(float)
    time = df15["time"].values
    print(f"M15 (resampled from real M5): n={n} bars (~{n/96:.0f} trading days)\n")

    atr = E.wilder_atr(high, low, close, 14)
    m21 = E.ma(close, 21, "ema")
    m50 = E.ma(close, 50, "ema")
    m_confirm = E.ma(close, 250, "sma")
    vwap = E.session_vwap(df15)

    sr_hi, sr_lo = build_sr_distance(df15, h4)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr_dist_buy = np.abs(sr_hi - close) / atr
        sr_dist_sell = np.abs(close - sr_lo) / atr

    above = m21 > m50
    above_prev = np.concatenate(([False], above[:-1]))
    raw_events = sorted([(i, 1.0) for i in np.where(above & ~above_prev)[0]] +
                         [(i, -1.0) for i in np.where((~above) & above_prev)[0]], key=lambda e: e[0])

    cond_confirm = close > m_confirm
    cond_vwap = close > vwap
    ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        cc = cond_confirm[i] if d > 0 else (not cond_confirm[i])
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if np.isnan(m_confirm[i]) or not (cc and cv):
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    print(f"raw 21/50 crosses: {len(raw_events)} -> {len(raw_events)/(n/96):.2f}/day, "
          f"{ok.sum()} pass confirm+VWAP+S/R\n")

    trades = sim_filtered_entries(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL)
    print("=" * 70)
    if not trades:
        print("0 trades"); sys.exit(0)
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    holds = np.array([t[1] - t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
    print(f"n={len(trades)} net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
          f"median_hold={np.median(holds)*15:.0f}min mean_hold={holds.mean()*15/60:.1f}h")
    if net > 0:
        print(f"closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")

    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    print("\nwalk-forward:")
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        if nb == 0:
            print(f"  block {b+1}: 0 trades"); continue
        netb = pnls[m].sum()
        if netb > 0: pos += 1
        t0 = pd.to_datetime(time[lo]).date(); t1 = pd.to_datetime(time[min(hi, n-1)]).date()
        print(f"  block {b+1} [{t0}->{t1}]: n={nb} net={netb:.2f} win%={100*(pnls[m]>0).mean():.1f}")
    print(f"  -> positive in {pos}/5 blocks")

    print(f"\nrandom-direction control (real net={net:.2f}):")
    rng = np.random.default_rng(0)
    random_nets = []
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(raw_events))
        rev = [(i, d) for (i, _), d in zip(raw_events, rdirs)]
        rev.sort(key=lambda e: e[0])
        ok_r = np.zeros(n, dtype=bool)
        for i, d in rev:
            cc = cond_confirm[i] if d > 0 else (not cond_confirm[i])
            cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
            if np.isnan(m_confirm[i]) or not (cc and cv):
                continue
            sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
            ok_r[i] = not (sr >= 0.0 and sr < MIN_SR)
        trades_r = sim_filtered_entries(rev, ok_r, close, high, low, spread, atr, n, SAFETY_SL)
        random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < net).mean()
    print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")

    print(f"\nfor reference, M5 v1.02 (same construction, M5 bars): net=3432.72 pf=1.357 "
          f"floatDD%=11.1 walk-forward=5/5 random-pct=100.0")
