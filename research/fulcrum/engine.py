"""
Fulcrum M5 / M15 real-gate engine - a direct port of Fulcrum_EA.mq5 (v2.13)
and Fulcrum_M15_EA.mq5, built to the same standard as research/aurelius/.

Fulcrum's ENTRY gate is structurally the Aurelius alignment stack, but the
values are NOT the same and two of the MA METHODS are not the same either
(read from the real `input` declarations / iMA() calls, never assumed):

    leg      Fulcrum M5           Aurelius M5        Fulcrum M15
    21       21  EMA              21  EMA            30  EMA
    50       50  EMA              50  EMA            50  EMA
    150      150 EMA              250 SMA            150 EMA
    600      600 SMA  (!)         500 SMMA           200 SMMA (!)
    2400     2400 EMA             2400 EMA           1200 EMA
    slope    0.50 .. 1.00         0.40 .. 1.00       0.50 .. 1.00
    volume   1.30                 1.25               1.30
    sr_dist  0.50      (!)        1.50               0.50      (!)

Fulcrum's slope MA and pullback MA are HARDCODED to the 50 leg (no
InpSlopeMA/InpPullbackMA inputs exist in either file), unlike Aurelius.

Fulcrum's EXIT is completely different and much simpler: a native broker
SL at the 50 EMA's value at entry -/+ InpStopBufferATR x ATR, and a native
broker TP at a fixed DOLLAR distance (TargetDistance()). There is no
Price21/VWAP/align-break/stale chain, no breakeven, no trailing, and no
daily-session flatten at all - only the Friday/weekend flatten
(WeekendStillOpen, tick-level).

Shared primitives (MA/ATR math, the US holiday calendar, the DST-gap
adjustment, D1-from-H4 reconstruction, the M5->M15 resample, the CSV
loaders) are IMPORTED from research/aurelius/engine.py rather than
re-derived - they are byte-for-byte the same MQL5 helpers in both EAs
(ComputeWilderATR in Fulcrum_EA.mq5:991 is character-identical to
Aurelius's, likewise EasterSunday/NthWeekdayOfMonth/LastWeekdayOfMonth/
ObservedFixedHoliday/IsMarketHoliday/DSTGapHourAdjustment).
"""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

AURELIUS_DIR = "/home/user/test-project/research/aurelius"


def _load(name, path, engine_alias=None):
    """Load a sibling research module under its OWN module name, so
    research/aurelius/engine.py and research/fulcrum/engine.py can coexist
    in one process without either shadowing the other. `engine_alias`
    temporarily satisfies a module whose own source does
    `from engine import ...` (aurelius/sim.py does)."""
    saved = sys.modules.get("engine")
    if engine_alias is not None:
        sys.modules["engine"] = engine_alias
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    finally:
        if engine_alias is not None:
            if saved is not None:
                sys.modules["engine"] = saved
            else:
                sys.modules.pop("engine", None)
    return mod


AE = _load("aurelius_engine", os.path.join(AURELIUS_DIR, "engine.py"))
AS = _load("aurelius_sim", os.path.join(AURELIUS_DIR, "sim.py"), engine_alias=AE)

# --- reused verbatim from the Aurelius rebuild (same MQL5 source in both EAs) ---
POINT = AE.POINT
ema, sma, smma, ma = AE.ema, AE.sma, AE.smma, AE.ma
wilder_atr = AE.wilder_atr
load_m5, load_h4 = AE.load_m5, AE.load_h4
resample_m15_from_m5 = AE.resample_m15_from_m5
derive_d1_from_h4 = AE.derive_d1_from_h4
market_holiday_mask = AE.market_holiday_mask
dst_gap_adjustment = AE.dst_gap_adjustment
stats, risk_stats = AS.stats, AS.risk_stats


# ---------------------------------------------------------------------------
# TRUE shipped defaults, read from the real `input` declarations.
# M5:  Fulcrum_EA.mq5:394-455 (+ the hardcoded iMA() methods at :625-629)
# M15: Fulcrum_M15_EA.mq5:525-570 (+ the InpM* method inputs at :538-547)
# ---------------------------------------------------------------------------
P = dict(
    tf="M5",
    p21=21, p50=50, p150=150, p600=600, p2400=2400,
    m21="ema", m50="ema", m150="ema", m600="sma", m2400="ema",   # hardcoded in iMA() calls
    min_slope_atr=0.50, max_slope_atr=1.00, slope_bars=20,
    cross_window=10, max_crosses=1,
    pullback_tol_atr=0.25, pullback_bars=10,
    use_volume=True, vol_avg_bars=100, min_vol_ratio=1.30,
    use_sr_dist=True, sr_days=3, min_sr_dist_atr=0.50,
    cooldown_bars=5,
    stop_buffer_atr=0.15, fixed_target_usd=45.0, min_stop_atr=0.0,
    lot_mode="LOT_FIXED", lots=0.01, max_lots=1.0,
    max_daily_loss_pct=0.0, max_spread_points=60,
    friday_no_entry_hour=20, friday_close_hour=22,
)

P15 = dict(P)
P15.update(
    tf="M15",
    p21=30, p50=50, p150=150, p600=200, p2400=1200,
    m21="ema", m50="ema", m150="ema", m600="smma", m2400="ema",   # InpM600 = MODE_SMMA here
)


# ---------------------------------------------------------------------------
def friday_deadline(times, close_hour, dst_adj):
    """Vectorized WeekendStillOpen() (Fulcrum_EA.mq5:1161) deadline: the most
    recent Friday `close_hour`:00 (DST-gap-corrected against THAT Friday's own
    date, not `now`'s) at or before each bar's time. The EA flattens as soon
    as a position whose open time precedes that deadline sees any tick at or
    after it - which is why this is a per-bar deadline, not a day_of_week
    test: a holiday that removes every bar near the cutoff hour cannot make
    the check silently never fire."""
    idx = pd.DatetimeIndex(times)
    days_since_friday = (idx.dayofweek - 4) % 7      # pandas Fri=4; Fri=0,Sat=1,...,Thu=6
    friday = idx.normalize() - pd.to_timedelta(days_since_friday, unit="D")
    fri_dst = dst_gap_adjustment(friday.values)
    deadline = friday + pd.to_timedelta(close_hour + fri_dst, unit="h")
    late = deadline > idx
    deadline = deadline.where(~late, deadline - pd.Timedelta(days=7))
    return deadline.values.astype("datetime64[ns]")


def build_context(df, h4, params=None):
    """Every per-bar array the Fulcrum gate/exit needs. `params` is REQUIRED
    in practice - pass P for M5 or P15 for M15; the same value must be passed
    to sim.simulate(). (research/aurelius/engine.py once silently ignored its
    own params argument and always built off P - that bug cost a whole
    debugging cycle there, so this file takes it seriously.)"""
    p = params or P
    o = df["open"].values.astype(float)
    c = df["close"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    v = df["tick_volume"].values.astype(float)
    n = len(df)

    m21 = ma(c, p["p21"], p["m21"])
    m50 = ma(c, p["p50"], p["m50"])
    m150 = ma(c, p["p150"], p["m150"])
    m600 = ma(c, p["p600"], p["m600"])
    m2400 = ma(c, p["p2400"], p["m2400"])
    # ComputeWilderATR (Fulcrum_EA.mq5:991) - NOT MT5's iATR, which this
    # broker computes as a plain SMA(14) of TR (EA's own v2.02 note).
    atr = wilder_atr(h, l, c, 14)

    # --- Aligned(1, isBuy), ALIGN_MID (Fulcrum_EA.mq5:1034) ---
    aligned_buy = (c > m2400) & (m21 > m50) & (m50 > m150) & (m150 > m600)
    aligned_sell = (c < m2400) & (m21 < m50) & (m50 < m150) & (m150 < m600)

    # --- SlopeATR (Fulcrum_EA.mq5:1054): ALWAYS the 50 leg, no input ---
    sb = p["slope_bars"]
    slope_raw = np.full(n, np.nan)
    slope_raw[sb:] = (m50[sb:] - m50[:-sb]) / atr[sb:]
    slope_buy, slope_sell = slope_raw, -slope_raw

    # --- CrissCross (Fulcrum_EA.mq5:1062): sign flips of (m21-m50) over the
    # cross_window pairs (shift j vs shift j+1, j=1..cw) ending at bar i ---
    sign = np.sign(m21 - m50)
    changed = (sign[1:] != sign[:-1]).astype(float)
    cw = p["cross_window"]
    changed_cum = np.concatenate(([0.0], np.cumsum(changed)))
    crisscross = np.full(n, np.nan)
    crisscross[cw:] = changed_cum[cw:n] - changed_cum[0:n - cw]

    # --- PullbackOK (Fulcrum_EA.mq5:1074): ALWAYS the 50 leg. tol is computed
    # ONCE from the decision bar's own ATR (`double tol = atr * InpPullbackTolATR`
    # before the loop) and applied to every bar in the lookback - so this is a
    # rolling MIN of the raw distance against a single per-decision-bar
    # threshold, not a per-historical-bar ATR. Same shape as the (fixed)
    # Aurelius port; the MQL5 loop runs j=1..InpPullbackBars, i.e. the
    # pullback_bars bars ending at the decision bar inclusive. ---
    pb = p["pullback_bars"]
    roll_min_buy = pd.Series(l - m50).rolling(pb, min_periods=1).min().values
    roll_min_sell = pd.Series(m50 - h).rolling(pb, min_periods=1).min().values
    tol_i = p["pullback_tol_atr"] * atr
    pullback_ok_buy = (c > m50) & (roll_min_buy <= tol_i)
    pullback_ok_sell = (c < m50) & (roll_min_sell <= tol_i)

    # --- VolumeRatio (Fulcrum_EA.mq5:1094): v[0] (=shift 1, the decision bar)
    # over the mean of v[1..InpVolAvgBars] (the PRECEDING bars, excluded) ---
    vab = p["vol_avg_bars"]
    prev_avg = pd.Series(v).shift(1).rolling(vab, min_periods=vab).mean().values
    with np.errstate(invalid="ignore", divide="ignore"):
        vol_ratio = v / prev_avg

    # --- SRLevels/SRDistanceATR (Fulcrum_EA.mq5:1116/1131): the previous
    # InpSRDays COMPLETED D1 bars (i=1..nDays, so shift 1 = yesterday) ---
    daily = derive_d1_from_h4(h4).sort_values("date").reset_index(drop=True)
    sd = p["sr_days"]
    daily["roll_hi"] = daily["high"].rolling(sd).max().shift(1)
    daily["roll_lo"] = daily["low"].rolling(sd).min().shift(1)
    bar_date = df["time"].dt.date
    sr_hi = bar_date.map(dict(zip(daily["date"], daily["roll_hi"]))).values.astype(float)
    sr_lo = bar_date.map(dict(zip(daily["date"], daily["roll_lo"]))).values.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr_dist_buy = np.abs(sr_hi - c) / atr
        sr_dist_sell = np.abs(c - sr_lo) / atr

    # --- session/holiday gating. NOTE: Fulcrum has NO daily-close flatten and
    # NO "no entry near daily close" input at all (Aurelius's InpCloseMinsBefore/
    # InpNoEntryMinsBefore do not exist in either Fulcrum file) - positions are
    # deliberately held overnight, average time-to-target ~17h on M5. ---
    times = df["time"].values
    dow = df["time"].dt.dayofweek.values          # Mon=0 .. Fri=4
    hour = df["time"].dt.hour.values
    dst_adj = dst_gap_adjustment(times)
    friday_no_entry = (dow == 4) & (hour >= p["friday_no_entry_hour"] + dst_adj)
    is_market_holiday = market_holiday_mask(times)
    fri_deadline = friday_deadline(times, p["friday_close_hour"], dst_adj)

    return dict(
        n=n, open=o, close=c, high=h, low=l, time=times,
        m21=m21, m50=m50, m150=m150, m600=m600, m2400=m2400, atr=atr,
        aligned_buy=aligned_buy, aligned_sell=aligned_sell,
        slope_buy=slope_buy, slope_sell=slope_sell, crisscross=crisscross,
        pullback_ok_buy=pullback_ok_buy, pullback_ok_sell=pullback_ok_sell,
        vol_ratio=vol_ratio, sr_dist_buy=sr_dist_buy, sr_dist_sell=sr_dist_sell,
        sr_hi=sr_hi, sr_lo=sr_lo,
        spread=df["spread"].values.astype(float),
        is_market_holiday=is_market_holiday, friday_no_entry=friday_no_entry,
        fri_deadline=fri_deadline,
    )


def build_all(params=None):
    """Convenience: load real data once and build the matching context."""
    p = params or P
    df5 = load_m5()
    h4 = load_h4()
    df = df5 if p["tf"] == "M5" else resample_m15_from_m5(df5)
    return df, h4, build_context(df, h4, p)
