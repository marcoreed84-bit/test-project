"""
Aurelius M5 real-gate engine - rebuilt from Aurelius_EA.mq5 (v1.46) after the
prior Python research container was lost. Every function here is a direct
port of the corresponding MQL5 function; see Aurelius_EA.mq5 for the
authoritative source and line references noted in comments below.

Data: real GOLD# M5 export (2023-01-03 .. 2026-08-14, tick_volume real,
real_volume always 0 on this broker) and GOLD# H4 export (2001-06 .. 2026-08,
used only to derive D1 high/low for the S/R filter, since no native D1 export
exists).
"""
import numpy as np
import pandas as pd

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
POINT = 0.01  # GOLD# meta_point from the CSV header (meta_digits=2)

# ---- shipped v1.46 defaults (Aurelius_EA.mq5, M5) ----
P = dict(
    p21=21, p50=50, p150=250, p600=500, p2400=2400,
    m21="ema", m50="ema", m150="sma", m600="smma", m2400="ema",
    align_mode="MID",         # ALIGN_MID: 21>50>150>600 + price vs 2400
    pullback_ma="50", pullback_tol_atr=0.25, pullback_bars=10,
    use_slope=True, slope_ma="50", slope_bars=20, min_slope_atr=0.40, max_slope_atr=1.00,
    use_cross_filter=True, cross_window=10, max_crosses=1,
    cooldown_bars=5,
    use_volume=True, vol_avg_bars=100, min_vol_ratio=1.25,
    use_sr_dist=True, sr_days=3, min_sr_dist_atr=0.50,
    use_stop=True, stop_atr=2.5,
    use_price21_exit=True, price21_buffer_atr=0.7, price21_confirm_bars=8,
    use_vwap_exit=True, vwap_buffer_atr=0.2, vwap_confirm_bars=8,
    allow_buys=True, allow_sells=True,
    use_breakeven=False, breakeven_atr=2.0, breakeven_lock_atr=0.1, use_trail_after_be=False,
    trail_give_back_atr=3.0,
)

# ---- exact settings actually used in the 2026-09-10 M5 real report
# (Aurelius_M5.xlsx) before the caching bug was caught and fixed - kept
# here so that report can still be used as a real validation target for
# the simulator's mechanics, even though these are NOT the true v1.46
# shipped defaults (see SESSION_NOTES.md 2026-09-19 incident / chat record
# of the caching bug catch). ----
STALE_M5_REPORT_PARAMS = dict(P)
STALE_M5_REPORT_PARAMS.update(
    p150=150, p600=600,
    m21="ema", m50="ema", m150="ema", m600="ema", m2400="ema",
    min_slope_atr=0.5, min_vol_ratio=1.3,
    use_breakeven=True, breakeven_atr=2.0, breakeven_lock_atr=0.1, use_trail_after_be=False,
)


def load_m5():
    df = pd.read_csv(f"{DATA_DIR}/GOLD_M5.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    return df


def load_h4():
    df = pd.read_csv(f"{DATA_DIR}/GOLD_H4.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    return df


def derive_d1_from_h4(h4):
    """D1 OHLC reconstructed from H4 bars grouped by calendar date - H4 bars
    tile exactly 00/04/08/12/16/20 server time within a day on this broker,
    so this reproduces a native D1 export's H/L exactly (O/C too, unused here)."""
    d = h4.copy()
    d["date"] = d["time"].dt.date
    daily = d.groupby("date").agg(open=("open", "first"), high=("high", "max"),
                                   low=("low", "min"), close=("close", "last")).reset_index()
    return daily


# ---------------------------- MA / ATR construction ----------------------------

def ema(x: np.ndarray, period: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    k = 2.0 / (period + 1.0)
    if len(x) < period:
        return out
    seed = np.mean(x[:period])
    out[period - 1] = seed
    for i in range(period, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def sma(x: np.ndarray, period: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    c = np.cumsum(np.insert(x, 0, 0.0))
    for i in range(period - 1, len(x)):
        out[i] = (c[i + 1] - c[i + 1 - period]) / period
    return out


def smma(x: np.ndarray, period: int) -> np.ndarray:
    """MT5 MODE_SMMA - same recursion as Wilder smoothing, SMA-seeded."""
    out = np.full(len(x), np.nan)
    if len(x) < period:
        return out
    seed = np.mean(x[:period])
    out[period - 1] = seed
    for i in range(period, len(x)):
        out[i] = (out[i - 1] * (period - 1) + x[i]) / period
    return out


def wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Ports ComputeWilderATR (Aurelius_EA.mq5 line ~1671): SMA seed of the
    first `period` true ranges landing at index `period` (0-indexed here at
    `period`, matching the EA's out[period]=seed since arr there is 0-indexed
    too), then Wilder recursive smoothing. NOT MT5's built-in iATR - the EA's
    own v1.36 note found this broker's iATR is a plain SMA(period) of TR."""
    n = len(close)
    tr = np.full(n, np.nan)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    out = np.full(n, np.nan)
    if n <= period:
        return out
    seed = np.mean(tr[1:period + 1])
    out[period] = seed
    for i in range(period + 1, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def ma(x: np.ndarray, period: int, method: str) -> np.ndarray:
    if method == "ema":
        return ema(x, period)
    if method == "sma":
        return sma(x, period)
    if method == "smma":
        return smma(x, period)
    raise ValueError(method)


# ---------------------------- signal construction ----------------------------
# Every function below mirrors the real function of the same intent in
# Aurelius_EA.mq5 (M5, v1.46). Index i throughout means "bar i has just
# closed" - i.e. exactly what MQL5 shift=1 means at the moment OnTick sees a
# new bar open. Trade actions (entries/exits) fill at bar i+1's OPEN, except
# the stop-loss, which is a resting order checked against bar i+1's own
# high/low (see simulate.py). This matches the real EA's own event order:
# OnTick's new-bar block computes from shift=1 and sends a market order
# essentially at the new bar's open tick.

def session_vwap(df):
    """Cumulative typical-price*volume from each bar's own calendar-day start,
    matching SessionVWAP() (Aurelius_EA.mq5 line ~1756)."""
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["tick_volume"]
    date = df["time"].dt.date
    cum_pv = pv.groupby(date).cumsum()
    cum_v = df["tick_volume"].groupby(date).cumsum()
    return (cum_pv / cum_v).values


def build_context(df, h4, params=None):
    """Precomputes every array the signal/exit/filter functions need, once,
    vectorized. Returns a dict of aligned numpy arrays, one value per M5 bar.

    params defaults to the module-global P (true v1.46 shipped defaults) -
    MUST be passed explicitly (and match whatever's passed to sim.simulate())
    when testing a different parameter set, e.g. STALE_M5_REPORT_PARAMS.
    Previously this silently ignored its params argument entirely and always
    built off P regardless of what simulate() was called with - found by an
    Opus audit; that bug was the actual cause of the earlier 911-vs-1098
    (83%) trade-count mismatch against the real stale-params report, not a
    genuine Python/MT5 fidelity gap. Fixed."""
    p = params or P
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    v = df["tick_volume"].values.astype(float)
    n = len(df)

    m21 = ma(c, p["p21"], p["m21"])
    m50 = ma(c, p["p50"], p["m50"])
    m150 = ma(c, p["p150"], p["m150"])
    m600 = ma(c, p["p600"], p["m600"])
    m2400 = ma(c, p["p2400"], p["m2400"])
    atr = wilder_atr(h, l, c, 14)

    # --- Aligned(shift=1, isBuy) - ALIGN_MID: c vs 2400, 21>50>150>600 ---
    aligned_buy = (c > m2400) & (m21 > m50) & (m50 > m150) & (m150 > m600)
    aligned_sell = (c < m2400) & (m21 < m50) & (m50 < m150) & (m150 < m600)

    # --- SlopeATR(isBuy) - SLOPE_50 default ---
    slope_ma_arr = {"21": m21, "50": m50, "150": m150, "600": m600}[p["slope_ma"]]
    sb = p["slope_bars"]
    slope_raw = np.full(n, np.nan)
    slope_raw[sb:] = (slope_ma_arr[sb:] - slope_ma_arr[:-sb]) / atr[sb:]
    slope_buy = slope_raw
    slope_sell = -slope_raw

    # --- CrissCross(): count of sign changes of (m21-m50) over the trailing
    # cross_window+1 bars (shifts 1..cross_window vs shifts 2..cross_window+1) ---
    sign = np.sign(m21 - m50)
    changed = (sign[1:] != sign[:-1]).astype(float)
    cw = p["cross_window"]
    crisscross = np.full(n, np.nan)
    # crisscross[i] counts changes over the cw pairs ending at i (i.e. changed[i-cw:i])
    changed_cum = np.concatenate(([0.0], np.cumsum(changed)))  # changed_cum[k] = sum(changed[:k])
    for i in range(cw, n):
        crisscross[i] = changed_cum[i] - changed_cum[i - cw]

    # --- PullbackOK(isBuy) - PB_50 default. Real MQL5 (Aurelius_EA.mq5:1877)
    # computes tol ONCE from the DECISION bar's own ATR and applies it across
    # the whole lookback window - NOT a per-historical-bar ATR (an Opus audit
    # caught this file previously using tol=pullback_tol_atr*atr[k] for each
    # historical bar k, a regime-dependent bias). Fixed via a rolling-min of
    # the raw (low - line) / (line - high) distance, compared against a
    # single per-decision-bar threshold atr[i]*pullback_tol_atr. ---
    pb_ma_arr = {"21": m21, "50": m50, "150": m150}[p["pullback_ma"]]
    pb = p["pullback_bars"]
    diff_buy = l - pb_ma_arr    # touch condition: diff_buy[k] <= tol_i for some k in window
    diff_sell = pb_ma_arr - h   # touch condition: diff_sell[k] <= tol_i for some k in window
    roll_min_buy = pd.Series(diff_buy).rolling(pb, min_periods=1).min().values
    roll_min_sell = pd.Series(diff_sell).rolling(pb, min_periods=1).min().values
    tol_i = p["pullback_tol_atr"] * atr
    touched_recently_buy = roll_min_buy <= tol_i
    touched_recently_sell = roll_min_sell <= tol_i
    pullback_ok_buy = (c > pb_ma_arr) & touched_recently_buy
    pullback_ok_sell = (c < pb_ma_arr) & touched_recently_sell

    # --- VolumeRatio(): current bar's tick_volume vs the mean of the PRECEDING
    # vol_avg_bars bars (excludes the current bar itself) ---
    vab = p["vol_avg_bars"]
    prev_avg = pd.Series(v).shift(1).rolling(vab, min_periods=vab).mean().values
    vol_ratio = v / prev_avg

    # --- SRDistanceATR(isBuy): previous InpSRDays completed D1 bars' hi/lo ---
    daily = derive_d1_from_h4(h4).sort_values("date").reset_index(drop=True)
    sd = p["sr_days"]
    daily["roll_hi"] = daily["high"].rolling(sd).max().shift(1)
    daily["roll_lo"] = daily["low"].rolling(sd).min().shift(1)
    date_map_hi = dict(zip(daily["date"], daily["roll_hi"]))
    date_map_lo = dict(zip(daily["date"], daily["roll_lo"]))
    bar_date = df["time"].dt.date
    sr_hi = bar_date.map(date_map_hi).values.astype(float)
    sr_lo = bar_date.map(date_map_lo).values.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr_dist_buy = np.abs(sr_hi - c) / atr
        sr_dist_sell = np.abs(c - sr_lo) / atr

    # --- session VWAP + spread (real column) ---
    vwap = session_vwap(df)
    spread = df["spread"].values.astype(float)

    # --- time features, derived from real gap structure in the data (the
    # broker's actual daily settlement break lands at the 00:00 calendar-day
    # boundary - bars run up to 23:55 and resume 01:00 every weekday; the
    # weekend gap is the same boundary, just longer on Fridays because
    # InpFridayCloseHour=22 cuts Friday earlier). Approximates
    # NearSessionClose/FridayCutoff without SymbolInfoSessionTrade(), which
    # isn't available outside MT5 - close enough for filter-on-filter testing
    # since both thresholds are being applied consistently to baseline and
    # candidate alike. ---
    dow = df["time"].dt.dayofweek.values  # Mon=0 .. Fri=4
    hour = df["time"].dt.hour.values
    minute = df["time"].dt.minute.values
    mins_to_midnight = (23 - hour) * 60 + (60 - minute)
    near_daily_close = mins_to_midnight <= 5           # InpCloseMinsBefore
    no_entry_near_close = mins_to_midnight <= 30        # InpNoEntryMinsBefore
    friday_flatten = (dow == 4) & (hour >= 22)          # InpFridayCloseHour
    friday_no_entry = (dow == 4) & (hour >= 20)         # InpNoEntryAfterHourFri

    return dict(
        n=n, close=c, high=h, low=l, time=df["time"].values,
        m21=m21, m50=m50, m150=m150, m600=m600, m2400=m2400, atr=atr,
        aligned_buy=aligned_buy, aligned_sell=aligned_sell,
        slope_buy=slope_buy, slope_sell=slope_sell, crisscross=crisscross,
        pullback_ok_buy=pullback_ok_buy, pullback_ok_sell=pullback_ok_sell,
        vol_ratio=vol_ratio, sr_dist_buy=sr_dist_buy, sr_dist_sell=sr_dist_sell,
        sr_hi=sr_hi, sr_lo=sr_lo,
        vwap=vwap, spread=spread,
        near_daily_close=near_daily_close, no_entry_near_close=no_entry_near_close,
        friday_flatten=friday_flatten, friday_no_entry=friday_no_entry,
    )
