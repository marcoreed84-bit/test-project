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

# ---- shipped defaults (Aurelius_EA.mq5, M5) - originally snapshotted at
# v1.46, updated here to v1.52's real, current default for use_price21_exit
# (found stale during a 2026-09-26 audit prompted by the user's "if you got
# Ratchet wrong, what else is wrong" question): the real EA REVERTED this to
# false in v1.48 after its own real MT5 A/B test failed both pre-written
# PASS conditions (PF only -0.84%, Balance DD actually IMPROVED with it
# off). Re-running the Aurelius M5 random-timing test with this corrected -
# real %PF barely moved (1.423->1.424) and the "survives K=100" verdict is
# unchanged, so this particular drift didn't matter, but it was real and
# is now fixed rather than left stale. No other real-confirmed change
# between v1.46 and v1.52 affects a parameter this dict controls. ----
P = dict(
    p21=21, p50=50, p150=250, p600=500, p2400=2400,
    m21="ema", m50="ema", m150="sma", m600="smma", m2400="ema",
    align_mode="MID",         # ALIGN_MID: 21>50>150>600 + price vs 2400
    pullback_ma="50", pullback_tol_atr=0.25, pullback_bars=10,
    use_slope=True, slope_ma="50", slope_bars=20, min_slope_atr=0.40, max_slope_atr=1.00,
    use_cross_filter=True, cross_window=10, max_crosses=1,
    cooldown_bars=5,
    use_volume=True, vol_avg_bars=100, min_vol_ratio=1.25,
    use_sr_dist=True, sr_days=3, min_sr_dist_atr=1.50,
    use_stop=True, stop_atr=2.5,
    use_price21_exit=False, price21_buffer_atr=0.7, price21_confirm_bars=8,
    use_vwap_exit=True, vwap_buffer_atr=0.2, vwap_confirm_bars=8,
    allow_buys=True, allow_sells=True,
    use_breakeven=False, breakeven_atr=2.0, breakeven_lock_atr=0.1, use_trail_after_be=False,
    trail_give_back_atr=3.0,
    use_slope_sr_block=False, slope_sr_block_slope=1.00, slope_sr_block_sr=6.00,
    use_stale_exit=False, stale_bars=48, stale_min_loss_atr=0.5,
    use_momentum=False, macd_fast=12, macd_slow=26, macd_signal=9, macd_signal_method="sma",
)

# ---- Aurelius_M15_EA.mq5 shipped defaults - originally snapshotted at
# v1.51, use_price21_exit corrected to match v1.54's real, current default
# (same audit as the M5 dict above - Aurelius_M15_EA.mq5's own header
# explicitly notes this "matches Aurelius_EA.mq5's (M5) own rejection of
# this same lever"). Genuinely different from M5 beyond that, not just
# rescaled periods: different pullback MA (21, not 50), much stricter S/R
# distance (1.50 ATR vs M5's 0.50, real-MT5-confirmed), and a filter that
# doesn't exist in the M5 file at all (InpUseSlopeSRBlock, Python-only per
# its own header, NOT yet real-tested). ----
P15 = dict(
    p21=30, p50=50, p150=150, p600=200, p2400=1200,
    m21="ema", m50="ema", m150="ema", m600="smma", m2400="ema",
    align_mode="MID",
    pullback_ma="21", pullback_tol_atr=0.25, pullback_bars=10,
    use_slope=True, slope_ma="50", slope_bars=20, min_slope_atr=0.20, max_slope_atr=1.25,
    use_cross_filter=True, cross_window=10, max_crosses=1,
    cooldown_bars=5,
    use_volume=True, vol_avg_bars=100, min_vol_ratio=1.30,
    use_sr_dist=True, sr_days=3, min_sr_dist_atr=1.50,
    use_slope_sr_block=True, slope_sr_block_slope=1.00, slope_sr_block_sr=6.00,
    use_stop=True, stop_atr=2.5,
    use_price21_exit=False, price21_buffer_atr=0.7, price21_confirm_bars=8,
    use_vwap_exit=True, vwap_buffer_atr=0.2, vwap_confirm_bars=8,
    allow_buys=True, allow_sells=True,
    use_breakeven=False, breakeven_atr=2.0, breakeven_lock_atr=0.1, use_trail_after_be=False,
    trail_give_back_atr=3.0,
    use_stale_exit=False, stale_bars=48, stale_min_loss_atr=0.5,
    use_momentum=False, macd_fast=12, macd_slow=26, macd_signal=9, macd_signal_method="sma",
)


def resample_m15_from_m5(df5):
    """M15 = exactly 3 M5 bars - lossless resample, no new MT5 export needed.
    tick_volume/spread aggregated the natural way (sum volume, mean spread);
    spread is only used as a >60-points entry-block check either way."""
    d = df5.set_index("time")
    o = d["open"].resample("15min").first()
    h = d["high"].resample("15min").max()
    l = d["low"].resample("15min").min()
    c = d["close"].resample("15min").last()
    v = d["tick_volume"].resample("15min").sum()
    sp = d["spread"].resample("15min").mean()
    out = pd.DataFrame(dict(open=o, high=h, low=l, close=c, tick_volume=v, spread=sp)).dropna()
    out = out.reset_index()
    return out

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


def easter_sunday(year):
    """Anonymous Gregorian algorithm (Meeus/Jones/Butcher), ported verbatim
    from EasterSunday() (Aurelius_EA.mq5 ~2130)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return pd.Timestamp(year=year, month=month, day=day)


def nth_weekday_of_month(year, month, weekday, n):
    """weekday: 0=Sunday..6=Saturday (MQL5 day_of_week convention), matching
    NthWeekdayOfMonth() (~2159)."""
    first = pd.Timestamp(year=year, month=month, day=1)
    first_dow = (first.dayofweek + 1) % 7  # pandas Mon=0 -> MQL5 Sun=0 convention
    offset = (weekday - first_dow + 7) % 7
    return first + pd.Timedelta(days=offset + (n - 1) * 7)


def last_weekday_of_month(year, month, weekday):
    nm, ny = (1, year + 1) if month == 12 else (month + 1, year)
    last_day = pd.Timestamp(year=ny, month=nm, day=1) - pd.Timedelta(days=1)
    last_dow = (last_day.dayofweek + 1) % 7
    back = (last_dow - weekday + 7) % 7
    return last_day - pd.Timedelta(days=back)


def observed_fixed_holiday(year, month, day):
    d = pd.Timestamp(year=year, month=month, day=day)
    dow = (d.dayofweek + 1) % 7  # MQL5 convention: Sun=0..Sat=6
    if dow == 6:
        return d - pd.Timedelta(days=1)  # Saturday -> observed Friday
    if dow == 0:
        return d + pd.Timedelta(days=1)  # Sunday -> observed Monday
    return d


def us_market_holidays(year):
    """Ports IsMarketHoliday() (~2193) - every date self-computed, no table."""
    dates = [
        observed_fixed_holiday(year, 1, 1),
        nth_weekday_of_month(year, 1, 1, 3),      # MLK: 3rd Mon Jan
        nth_weekday_of_month(year, 2, 1, 3),      # Presidents: 3rd Mon Feb
        easter_sunday(year) - pd.Timedelta(days=2),  # Good Friday
        last_weekday_of_month(year, 5, 1),        # Memorial: last Mon May
        observed_fixed_holiday(year, 6, 19),      # Juneteenth
        observed_fixed_holiday(year, 7, 4),       # Independence Day
        nth_weekday_of_month(year, 9, 1, 1),      # Labor: 1st Mon Sep
        nth_weekday_of_month(year, 11, 4, 4),     # Thanksgiving: 4th Thu Nov
        observed_fixed_holiday(year, 12, 25),     # Christmas
    ]
    return {d.date() for d in dates}


def market_holiday_mask(times):
    """Per-bar bool array - is this bar's own calendar date a US market
    holiday, per IsMarketHoliday()."""
    dates = pd.DatetimeIndex(times).date
    years = pd.DatetimeIndex(times).year
    holiday_by_year = {y: us_market_holidays(int(y)) for y in np.unique(years)}
    return np.array([d in holiday_by_year[y] for d, y in zip(dates, years)])


def dst_gap_adjustment(times):
    """Per-bar int array (-1 during a DST-gap week, 0 otherwise), ports
    DSTGapHourAdjustment() (~2239) - this broker's server clock follows EU
    DST dates while gold's true session follows US DST dates."""
    idx = pd.DatetimeIndex(times)
    years = np.unique(idx.year)
    out = np.zeros(len(idx), dtype=int)
    for y in years:
        y = int(y)
        us_spring = nth_weekday_of_month(y, 3, 0, 2) + pd.Timedelta(days=1)
        eu_spring = last_weekday_of_month(y, 3, 0) + pd.Timedelta(days=1)
        eu_autumn = last_weekday_of_month(y, 10, 0) + pd.Timedelta(days=1)
        us_autumn = nth_weekday_of_month(y, 11, 0, 1) + pd.Timedelta(days=1)
        in_spring_gap = (idx >= us_spring) & (idx < eu_spring)
        in_autumn_gap = (idx >= eu_autumn) & (idx < us_autumn)
        out[np.asarray(in_spring_gap | in_autumn_gap)] = -1
    return out


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

    # --- Aligned(shift=1, isBuy) - direct port of Aurelius_EA.mq5's Aligned()
    # (~1913): PRICE = c vs 2400 + 21>50; FAST = + 50>150; MID (default,
    # matches the shipped EA) = + 150>600; FULL = replaces "c vs 2400" with
    # "600 vs 2400" instead of adding another leg. align_mode defaults to
    # "MID" so every existing caller (P/P15 both ship align_mode="MID") gets
    # byte-identical behavior to before this was parameterized - only a
    # caller that explicitly passes a different align_mode sees anything
    # different.
    align_mode = p.get("align_mode", "MID")
    price_ok_buy  = (m600 > m2400) if align_mode == "FULL" else (c > m2400)
    price_ok_sell = (m600 < m2400) if align_mode == "FULL" else (c < m2400)
    aligned_buy  = price_ok_buy  & (m21 > m50)
    aligned_sell = price_ok_sell & (m21 < m50)
    if align_mode != "PRICE":
        aligned_buy  = aligned_buy  & (m50 > m150)
        aligned_sell = aligned_sell & (m50 < m150)
        if align_mode != "FAST":
            aligned_buy  = aligned_buy  & (m150 > m600)
            aligned_sell = aligned_sell & (m150 < m600)

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

    # --- MACD histogram, for InpUseMomentum / MomentumShiftOK()
    # (Aurelius_EA.mq5 ~1905). The EA reads iMACD(_Symbol, PERIOD_CURRENT,
    # 12, 26, 9, PRICE_CLOSE): buffer 0 = MAIN = EMA(fast) - EMA(slow),
    # buffer 1 = SIGNAL. NOTE/ASSUMPTION: MetaTrader's own bundled MACD
    # smooths the signal line with a SIMPLE MA of the main buffer, not an
    # EMA (unlike most non-MT platforms) - macd_signal_method="sma"
    # reproduces that, "ema" is kept as a sensitivity check since this is
    # a platform convention, not something verifiable from the CSV data. ---
    macd_main = ma(c, p.get("macd_fast", 12), "ema") - ma(c, p.get("macd_slow", 26), "ema")
    valid = ~np.isnan(macd_main)
    macd_sig = np.full(n, np.nan)
    if valid.any():
        first = int(np.argmax(valid))
        macd_sig[first:] = ma(macd_main[first:], p.get("macd_signal", 9),
                              p.get("macd_signal_method", "sma"))
    macd_hist = macd_main - macd_sig

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

    # --- DST-gap adjustment (DSTGapHourAdjustment, ~2239) and US market
    # holiday block (IsMarketHoliday, ~2193) - real, purpose-built EA logic,
    # ported exactly rather than left out as "approximation noise". DST
    # only corrects the FIXED Friday-hour thresholds in the real code (the
    # daily near-close check above uses SymbolInfoSessionTrade() dynamically,
    # which doesn't need it). ---
    dst_adj = dst_gap_adjustment(df["time"].values)
    friday_flatten = (dow == 4) & (hour >= 22 + dst_adj)    # InpFridayCloseHour
    friday_no_entry = (dow == 4) & (hour >= 20 + dst_adj)   # InpNoEntryAfterHourFri
    is_market_holiday = market_holiday_mask(df["time"].values)

    return dict(
        n=n, close=c, high=h, low=l, time=df["time"].values,
        m21=m21, m50=m50, m150=m150, m600=m600, m2400=m2400, atr=atr,
        aligned_buy=aligned_buy, aligned_sell=aligned_sell,
        slope_buy=slope_buy, slope_sell=slope_sell, crisscross=crisscross,
        pullback_ok_buy=pullback_ok_buy, pullback_ok_sell=pullback_ok_sell,
        vol_ratio=vol_ratio, sr_dist_buy=sr_dist_buy, sr_dist_sell=sr_dist_sell,
        sr_hi=sr_hi, sr_lo=sr_lo,
        vwap=vwap, spread=spread, macd_hist=macd_hist,
        near_daily_close=near_daily_close, no_entry_near_close=no_entry_near_close,
        is_market_holiday=is_market_holiday,
        friday_flatten=friday_flatten, friday_no_entry=friday_no_entry,
    )
