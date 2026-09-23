"""
Real GOLD# bar data for the Ratchet/Meridian 2026-09-23 validation work.

Both files are real XM Global GOLD# exports (ExportBarData.mq5), read straight
from the uploaded zips so nothing depends on a /tmp copy surviving:

  M5: 12668308-GOLD_PERIOD_M5.zip  2022-06-27 04:30 .. 2026-09-18 23:55
      (covers the whole 2026.01.01-2026.09.21 Strategy Tester window - the
      tester's last trading day with bars is Fri 2026-09-18 - plus 3.5 years
      of warm-up, so a 2400-EMA / 600-SMA / 250-SMA is fully converged by Jan)
  M1: cb108a55-GOLD_PERIOD_M1.zip  2025-11-12 10:50 .. 2026-09-18 23:57
      (used only for intrabar mark-to-market in the equity-drawdown
      reconstruction - every trading DECISION in both EAs is made on M5)

Time is broker server time throughout (same clock the reports use).
"""
import zipfile

import numpy as np
import pandas as pd

UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
M5_ZIP = UP + "12668308-GOLD_PERIOD_M5.zip"
M1_ZIP = UP + "cb108a55-GOLD_PERIOD_M1.zip"
POINT = 0.01
CONTRACT = 100.0

_cache = {}


def _read(zpath):
    with zipfile.ZipFile(zpath) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            df = pd.read_csv(f, skiprows=1, usecols=range(8))
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True)


def load_m5():
    if "m5" not in _cache:
        _cache["m5"] = _read(M5_ZIP)
    return _cache["m5"].copy()


def load_m1():
    if "m1" not in _cache:
        _cache["m1"] = _read(M1_ZIP)
    return _cache["m1"].copy()


# ------------------------------------------------------------------ MT5 indicator ports

def ema(x, period):
    """MT5 iMA MODE_EMA (converged - the warm-up here is years long)."""
    return pd.Series(x).ewm(alpha=2.0 / (period + 1.0), adjust=False).mean().values


def sma(x, period):
    return pd.Series(x).rolling(period, min_periods=period).mean().values


def mt5_atr(h, l, c, period=14):
    """MT5's built-in iATR: a plain SMA(period) of true range (this broker's
    iATR is NOT Wilder - see Meridian_EA.mq5 / Aurelius v1.36). Ratchet reads
    iATR directly, so this is the right port for Ratchet."""
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    return sma(tr, period)


def wilder_atr(h, l, c, period=14):
    """Meridian's ComputeWilderATR (SMA-seeded Wilder recursion), converged."""
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    out = np.full(len(c), np.nan)
    out[period] = tr[1:period + 1].mean()
    a = 1.0 / period
    for i in range(period + 1, len(c)):
        out[i] = out[i - 1] + a * (tr[i] - out[i - 1])
    return out


def mt5_stoch_signal(h, l, c, k=5, slowing=3, d=3):
    """MT5 Stochastic.mq5, STO_LOWHIGH, MODE_SMA: main = 100*sum(c-LL)/sum(HH-LL)
    over `slowing` bars, signal = SMA(d) of main. Returns (main, signal)."""
    ll = pd.Series(l).rolling(k, min_periods=k).min().values
    hh = pd.Series(h).rolling(k, min_periods=k).max().values
    num = pd.Series(c - ll).rolling(slowing, min_periods=slowing).sum().values
    den = pd.Series(hh - ll).rolling(slowing, min_periods=slowing).sum().values
    with np.errstate(invalid="ignore", divide="ignore"):
        main = np.where(den == 0.0, 100.0, 100.0 * num / den)
    sig = sma(main, d)
    return main, sig


def mt5_bands(c, period=20, dev=2.0):
    mid = sma(c, period)
    sd = pd.Series(c).rolling(period, min_periods=period).std(ddof=0).values
    return mid, mid + dev * sd, mid - dev * sd


# ------------------------------------------------------------------ calendar ports (Ratchet_EA.mq5)

def _easter(year):
    a = year % 19; b = year // 100; c = year % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3; h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4; l_ = (32 + 2 * e + 2 * i - h - k) % 7; m = (a + 11 * h + 22 * l_) // 451
    return pd.Timestamp(year=year, month=(h + l_ - 7 * m + 114) // 31, day=((h + l_ - 7 * m + 114) % 31) + 1)


def _nth(year, month, weekday_mql, n):
    first = pd.Timestamp(year=year, month=month, day=1)
    fd = (first.dayofweek + 1) % 7
    return first + pd.Timedelta(days=(weekday_mql - fd + 7) % 7 + (n - 1) * 7)


def _last(year, month, weekday_mql):
    nm, ny = (1, year + 1) if month == 12 else (month + 1, year)
    ld = pd.Timestamp(year=ny, month=nm, day=1) - pd.Timedelta(days=1)
    back = (((ld.dayofweek + 1) % 7) - weekday_mql + 7) % 7
    return ld - pd.Timedelta(days=back)


def _observed(year, month, day):
    d = pd.Timestamp(year=year, month=month, day=day)
    if d.dayofweek == 5:
        return d - pd.Timedelta(days=1)
    if d.dayofweek == 6:
        return d + pd.Timedelta(days=1)
    return d


def holidays(year):
    return {x.date() for x in [
        _observed(year, 1, 1), _nth(year, 1, 1, 3), _nth(year, 2, 1, 3), _easter(year) - pd.Timedelta(days=2),
        _last(year, 5, 1), _observed(year, 6, 19), _observed(year, 7, 4), _nth(year, 9, 1, 1),
        _nth(year, 11, 4, 4), _observed(year, 12, 25)]}


def dst_gap_adj(ts):
    y = ts.year
    one = pd.Timedelta(days=1)
    if _nth(y, 3, 0, 2) + one <= ts < _last(y, 3, 0) + one:
        return -1
    if _last(y, 10, 0) + one <= ts < _nth(y, 11, 0, 1) + one:
        return -1
    return 0
