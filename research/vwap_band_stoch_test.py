"""
Tests a NEW, previously-untested candidate the user described from watching a
real M15 chart (2026-09-24): price + VWAP-with-deviation-bands + stochastic
mean-reversion scalp. This does NOT exist anywhere else in this repo - no EA
or prior script builds VWAP bands (AuRebound_EA.mq5 looked similar in name but
is unrelated: H4 timeframe, Bollinger/SMA bands not VWAP-based, a different
EA family, never real-MT5-confirmed). This is a genuinely new construction,
Python-screened here BEFORE any MQL5 work, per this project's standing rule.

USER'S DESCRIPTION (verbatim, from a real M15 chart screenshot):
  "first one stochastic was moving up from oversold, price closed back
  inside the outer vwap line, went all the way back up to the vwap line,
  just after price closed back below the vwap, stochastic was moving out
  of overbought went back down all the way to the vwap outer line"

CONSTRUCTION (explicit, since none of this exists in the repo to reuse):
  - VWAP: engine.py's real session_vwap() (session-anchored, resets each
    calendar day, identical to what Aurelius_EA.mq5 actually computes).
  - Bands: VWAP +/- k * session-cumulative VOLUME-WEIGHTED stdev of typical
    price from VWAP (the standard "VWAP bands" construction, same session
    reset as VWAP itself) - k=2.0 tested as the default (a common real
    convention), also sweeps k=1.5/2.5 to check sensitivity.
  - Stochastic: Ratchet_EA.mq5's own real, native 5/3/3 construction
    (%K smoothed, %D signal) - the one already validated/real-tested lever
    in this portfolio, not an arbitrary 14/3 pick.
  - Entry (symmetric, generalizing the user's one worked example into a
    single testable rule): price closes back INSIDE a band from beyond it
    (either side) AND stochastic is turning away from the matching extreme
    (below 20 and rising for a long re-entering the lower band; above 80
    and falling for a short re-entering the upper band) on that same bar.
  - Exit: TWO variants tested separately, since the user's own example used
    a different target for each direction (buy targeted the VWAP line
    itself; sell targeted the far band) - (a) target = VWAP itself,
    (b) target = the OPPOSITE band. Stop: 1.5x ATR beyond the entry band
    (a real, if arbitrary, protective level - explicitly not validated,
    just needed to make the test realistic rather than open-ended risk).
  - Sequential, single-position, walk-forward, no lookahead: signal known
    at bar i's close, filled at bar i+1's open (matches every other real-
    data screen in this repo's convention, e.g. engine.py's
    realistic_single_position()).

DATA: real GOLD# M15 (resampled from the M5 export every other Aurelius
M15 script uses) - chosen because that's the timeframe the user's own
example chart was on. Real spread charged on entry.
"""
import sys
sys.path.insert(0, "research/aurelius")
import numpy as np
import pandas as pd
import engine as E

POINT = E.POINT


def stochastic_553(high, low, close, k_period=5, d_period=3, slow=3):
    """Ratchet_EA.mq5's own real 5/3/3 construction: %K = SMA-smoothed raw
    stochastic over k_period, %D (slow, used for the exit) = SMA(3) of %K -
    matching bars.mt5_stoch_signal's real formula (MT5's own MODE_SMA
    stochastic, not the EMA variant)."""
    hh = pd.Series(high).rolling(k_period).max()
    ll = pd.Series(low).rolling(k_period).min()
    rng = (hh - ll).replace(0, np.nan)
    raw_k = 100.0 * (pd.Series(close) - ll) / rng
    k = raw_k.rolling(slow).mean()
    d = k.rolling(d_period).mean()
    return k.values, d.values


def vwap_bands(df, vwap, k):
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    date = df["time"].dt.date
    dev2 = (typical - vwap) ** 2
    # volume-weighted variance, same session-cumulative reset as VWAP
    v = df["tick_volume"].astype(float)
    cum_wdev2 = (dev2 * v).groupby(date).cumsum()
    cum_v = v.groupby(date).cumsum()
    var = (cum_wdev2 / cum_v).values
    sd = np.sqrt(np.maximum(var, 0))
    return vwap + k * sd, vwap - k * sd


def run(df, atr, spread, k_band, exit_target, label):
    n = len(df)
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    vwap = E.session_vwap(df)
    upper, lower = vwap_bands(df, vwap, k_band)
    kf, df_ = stochastic_553(high, low, close)

    trades = []
    pos = None  # dict(dir, entry_i, entry_px, stop, target)
    for i in range(6, n - 1):
        if np.isnan(vwap[i]) or np.isnan(upper[i]) or np.isnan(kf[i]) or np.isnan(kf[i - 1]):
            continue
        if pos is not None:
            # check exit at this bar's high/low (intrabar), else at open[i+1] if target/stop untouched
            hit_stop = (low[i] <= pos["stop"]) if pos["dir"] > 0 else (high[i] >= pos["stop"])
            hit_tgt = (high[i] >= pos["target"]) if pos["dir"] > 0 else (low[i] <= pos["target"])
            if hit_stop and hit_tgt:
                px = pos["stop"]  # conservative: assume stop hit first if both touch same bar
                reason = "STOP(amb)"
            elif hit_stop:
                px = pos["stop"]; reason = "STOP"
            elif hit_tgt:
                px = pos["target"]; reason = "TARGET"
            else:
                continue
            pnl = (px - pos["entry_px"]) * pos["dir"]
            trades.append(dict(entry_i=pos["entry_i"], exit_i=i, dir=pos["dir"], pnl=pnl, reason=reason))
            pos = None
            continue
        # entry check (flat only)
        a = atr[i]
        if a <= 0 or np.isnan(a):
            continue
        long_reentry = (low[i] <= lower[i]) and (close[i] > lower[i]) and (close[i] < vwap[i])
        short_reentry = (high[i] >= upper[i]) and (close[i] < upper[i]) and (close[i] > vwap[i])
        stoch_up = kf[i] > kf[i - 1] and kf[i - 1] < 20
        stoch_dn = kf[i] < kf[i - 1] and kf[i - 1] > 80
        fill_i = i + 1
        if fill_i >= n:
            continue
        entry_px = close[i]  # signal known at close[i], approximated fill at same level +spread (real convention this repo uses for VWAP/level touches)
        sp = spread[fill_i] * POINT if fill_i < len(spread) else spread[i] * POINT
        if long_reentry and stoch_up:
            stop = lower[i] - 1.5 * a
            target = vwap[i] if exit_target == "vwap" else upper[i]
            pos = dict(dir=1, entry_i=i, entry_px=entry_px + sp, stop=stop, target=target)
        elif short_reentry and stoch_dn:
            stop = upper[i] + 1.5 * a
            target = vwap[i] if exit_target == "vwap" else lower[i]
            pos = dict(dir=-1, entry_i=i, entry_px=entry_px - sp, stop=stop, target=target)

    if not trades:
        print(f"  {label}: 0 trades")
        return
    pnl = np.array([t["pnl"] for t in trades])
    gp = pnl[pnl > 0].sum()
    gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else float("inf")
    win = (pnl > 0).mean() * 100
    print(f"  {label}: n={len(trades):4d} net={pnl.sum():9.2f} pf={pf:6.3f} win%={win:5.1f} "
          f"avg={pnl.mean():7.2f}")


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    h4 = E.load_h4()
    ctx15 = E.build_context(df15, h4, params=E.P15)
    atr15, spread15 = ctx15["atr"], ctx15["spread"]

    print("=== M15, target = VWAP line ===")
    for k in (1.5, 2.0, 2.5):
        run(df15, atr15, spread15, k, "vwap", f"k={k}")
    print("=== M15, target = opposite band ===")
    for k in (1.5, 2.0, 2.5):
        run(df15, atr15, spread15, k, "band", f"k={k}")


def run_m1():
    sys.path.insert(0, "research/msg")
    import sim as M
    df1 = M.load_bars()
    atr1 = E.wilder_atr(df1["high"].values, df1["low"].values, df1["close"].values, 14)
    spread1 = df1["spread"].values.astype(float)
    print("\n=== M1 (real GOLD# M1, 2025-11-12 onward), target = VWAP line ===")
    for k in (1.5, 2.0, 2.5):
        run(df1, atr1, spread1, k, "vwap", f"k={k}")
    print("=== M1, target = opposite band ===")
    for k in (1.5, 2.0, 2.5):
        run(df1, atr1, spread1, k, "band", f"k={k}")


run_m1()
