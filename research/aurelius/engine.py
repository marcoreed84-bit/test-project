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
