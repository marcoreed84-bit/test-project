"""
Shared regular-divergence detection (RSI / MACD-histogram / Stochastic vs
price), used to screen an EARLY-EXIT candidate - "close the open position on
the first confirmed divergence signal against it" - on top of each EA's own
real baseline strategy, in research/aurelius, research/meridian and
research/ratchet.

USER'S IDEA (2026-09-23), prompted by a real chart of a short trade that
entered very late in an already-extended downtrend: while a position is open,
if price prints a fresh local extreme in the trade's OWN favour but the
oscillator does NOT confirm it (a "regular"/"classic" divergence - the
textbook reversal warning), exit early - potentially before the EA's own
slower exits (Aurelius's alignment-break/Price21Exit/VwapExit/stop, Meridian's
21/50 reversal cross, Ratchet's stochastic-signal exit/trail/stop) catch the
same reversal. Genuinely new construction: a full-repo grep before this file
was written confirmed RSI/MACD/Stochastic price-divergence has never been
tested anywhere in this repo, as either an entry or an exit signal, on any EA.
Two adjacent things exist but are NOT this: stoch_speed_test.py / mtf_stoch_
test.py (stochastic extremes/speed as an ENTRY filter) and Aurelius's own
InpUseMomentum (MACD histogram TURNING in the trade's favor at entry -
momentum shift, not price/oscillator divergence).

  regular BEARISH divergence: price makes a HIGHER high, oscillator makes a
    LOWER high -> reversal warning against an open LONG.
  regular BULLISH divergence: price makes a LOWER low, oscillator makes a
    HIGHER low -> reversal warning against an open SHORT.

SWING-PIVOT DEFINITION (a real design choice, stated explicitly because it
drives every result below - not the only reasonable choice): a fractal-style
N-bar pivot. Bar j is a swing high if high[j] equals the maximum of the
(2N+1)-bar window centered on j, [j-N, j+N]; a swing low is the symmetric
minimum-of-low case. Like every pivot definition of this kind, a pivot at
index j is NOT knowable until N bars after j - price has to fail to make a
new extreme for N more bars before j can be confirmed as the local extreme.
So a pivot found at j only becomes usable to a causal, walk-forward sim at
bar j+N (the CONFIRMATION bar), never earlier - no lookahead. N=5 is used
everywhere in this module, on every timeframe (M5/M15) tested, for
consistency and comparability across the four EAs rather than rescaled per
timeframe - no run in this session established a rescaled N, and picking one
after seeing results would be exactly the kind of post-hoc tuning this
project's own screening discipline warns against. This also means a
divergence exit only ever fires a MINIMUM of N=5 bars after the actual price
extreme it's reacting to - it is a lagging-but-still-early warning by
construction, not a same-bar one.

Regular divergence is then: compare the newest CONFIRMED pivot of a type to
the immediately preceding confirmed pivot of the SAME type. If price and
oscillator disagree on direction (price higher-high / osc lower-high, or
price lower-low / osc higher-low), the divergence signal fires AT the
confirmation bar of the newer pivot - the earliest point it is actually
knowable in a causal simulation.

KNOWN ARTIFACT, not corrected for: a flat/tied high or low across more than
one bar within a window makes every tied bar its own pivot (the `==` test
below), which can put two pivots only a few bars apart. This affects a small
minority of pivots on real gold bar data (prices are 2-decimal, exact ties
are uncommon but not impossible) and applies identically to baseline and
candidate runs, so it is not expected to bias the exit-trigger comparison.

Every oscillator here either IS or directly mirrors a construction that
already exists and is validated elsewhere in this repo, so a "MACD
divergence" or "stochastic divergence" result is comparing like for like with
what's already used for other purposes on the same EAs, not a brand-new,
unvalidated oscillator build:
  - RSI(14): standard Wilder RSI, same SMA-seeded Wilder-recursion shape as
    engine.py's wilder_atr()/smma() (and Ratchet/Meridian's bars.py ports),
    applied to signed up/down closes instead of true range. Genuinely new to
    this repo - no RSI existed anywhere in it before this file.
  - MACD histogram: reuses Aurelius's OWN construction from InpUseMomentum's
    Python validation (engine.py build_context(): iMACD(12,26,9,PRICE_CLOSE)
    style, buffer 0 = EMA(fast)-EMA(slow), buffer 1 = SMA(signal) of that,
    assuming MT5's bundled MACD's SMA-smoothed signal line per that file's own
    documented assumption) - ctx["macd_hist"] is used directly for Aurelius.
    Meridian/Ratchet have no MACD of their own, so macd_histogram() below
    reproduces the identical formula using each folder's own ema()/sma() (in
    practice byte-identical to engine.py's, since MT5's EMA/SMA are what
    every one of these ports is reproducing).
  - Stochastic(14,3): reuses research/aurelius/stoch_speed_test.py's own
    stochastic() function verbatim (rolling %K over `period`, SMA-smoothed by
    `smooth`) - deliberately NOT Ratchet's native 5/3/3 MT5 Stochastic
    construction (bars.mt5_stoch_signal), which is a different, already-used
    lever (Ratchet's real InpUseStochExit) tested at different periods; the
    task asked for Stochastic(14,3) specifically, applied uniformly.
"""
import numpy as np
import pandas as pd


# ---------------------------- oscillators ----------------------------

def rsi_wilder(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder RSI(14) - SMA-seeded recursive (Wilder/SMMA-style) average
    gain/loss of the bar-to-bar close change, matching MT5's iRSI. Same
    smoothing shape as engine.py's wilder_atr()/smma(), applied to signed
    up/down moves instead of true range."""
    close = np.asarray(close, dtype=float)
    n = len(close)
    out = np.full(n, np.nan)
    if n <= period:
        return out
    diff = np.diff(close)  # diff[i] = close[i+1] - close[i], length n-1
    gain = np.where(diff > 0, diff, 0.0)
    loss = np.where(diff < 0, -diff, 0.0)
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    with np.errstate(invalid="ignore", divide="ignore"):
        out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i + 1] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def _ema(x, period):
    return pd.Series(x, dtype=float).ewm(alpha=2.0 / (period + 1.0), adjust=False).mean().values


def _sma(x, period):
    return pd.Series(x, dtype=float).rolling(period, min_periods=period).mean().values


def macd_histogram(close, fast=12, slow=26, signal=9):
    """Standalone 12/26/9 MACD histogram (EMA fast - EMA slow, signal =
    SMA of that main line, matching MT5's bundled-indicator convention per
    engine.py's own documented assumption). For Meridian/Ratchet, which have
    no MACD of their own; Aurelius uses ctx["macd_hist"] directly instead,
    for byte-identical consistency with InpUseMomentum's validation."""
    main = _ema(close, fast) - _ema(close, slow)
    sig = _sma(main, signal)
    return main - sig


def stochastic(high, low, close, period=14, smooth=3):
    """Verbatim copy of research/aurelius/stoch_speed_test.py's stochastic()
    - kept identical (not imported cross-folder, matching this repo's
    existing convention of self-contained research scripts) so a "stochastic
    divergence" result is directly comparable to that file's own findings."""
    hh = pd.Series(high).rolling(period).max().values
    ll = pd.Series(low).rolling(period).min().values
    rng = hh - ll
    with np.errstate(divide="ignore", invalid="ignore"):
        k_raw = np.where(rng > 0, 100.0 * (close - ll) / np.where(rng > 0, rng, 1.0), np.nan)
    k = pd.Series(k_raw).rolling(smooth).mean().values
    return k


# ---------------------------- swing pivots + divergence ----------------------------

def swing_pivots(high: np.ndarray, low: np.ndarray, n: int = 5):
    """Fractal-style N-bar pivot (see module docstring). Returns
    (pivot_high, pivot_low) bool arrays, True at the PIVOT bar's own index j -
    not yet usable there; see regular_divergence_signals()'s confirm_i=j+n
    for the causal, no-lookahead index this actually becomes knowable at."""
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    win = 2 * n + 1
    roll_max = pd.Series(high).rolling(win, center=True, min_periods=win).max().values
    roll_min = pd.Series(low).rolling(win, center=True, min_periods=win).min().values
    pivot_high = (~np.isnan(roll_max)) & (high == roll_max)
    pivot_low = (~np.isnan(roll_min)) & (low == roll_min)
    return pivot_high, pivot_low


def regular_divergence_signals(price_high, price_low, oscillator, n: int = 5):
    """Returns (bearish_confirmed, bullish_confirmed) bool arrays, same
    length as the inputs.

    bearish_confirmed[i] is True at exactly the bar i where a newly confirmed
    swing HIGH (pivot index i-n) is a higher price high than the immediately
    PRECEDING confirmed swing high, AND has a LOWER oscillator value than that
    preceding pivot - i.e. i is the earliest bar this divergence is actually
    knowable, causally. bullish_confirmed is the symmetric swing-LOW case
    (lower price low, higher oscillator low).
    """
    price_high = np.asarray(price_high, dtype=float)
    price_low = np.asarray(price_low, dtype=float)
    oscillator = np.asarray(oscillator, dtype=float)
    n_bars = len(price_high)
    pivot_high, pivot_low = swing_pivots(price_high, price_low, n)
    bearish = np.zeros(n_bars, dtype=bool)
    bullish = np.zeros(n_bars, dtype=bool)

    prev_high_idx = None
    for j in np.where(pivot_high)[0]:
        confirm_i = j + n
        if confirm_i >= n_bars:
            break
        if prev_high_idx is not None:
            osc_j, osc_prev = oscillator[j], oscillator[prev_high_idx]
            if not (np.isnan(osc_j) or np.isnan(osc_prev)):
                if price_high[j] > price_high[prev_high_idx] and osc_j < osc_prev:
                    bearish[confirm_i] = True
        prev_high_idx = j

    prev_low_idx = None
    for j in np.where(pivot_low)[0]:
        confirm_i = j + n
        if confirm_i >= n_bars:
            break
        if prev_low_idx is not None:
            osc_j, osc_prev = oscillator[j], oscillator[prev_low_idx]
            if not (np.isnan(osc_j) or np.isnan(osc_prev)):
                if price_low[j] < price_low[prev_low_idx] and osc_j > osc_prev:
                    bullish[confirm_i] = True
        prev_low_idx = j

    return bearish, bullish


def all_divergence_signals(high, low, close, n: int = 5, macd_hist=None):
    """Convenience wrapper: builds all three oscillator constructions (RSI14,
    MACD hist - reused if the caller already has one, e.g. Aurelius's
    ctx["macd_hist"] - and Stochastic(14,3)) and returns a dict of
    {name: (bearish_confirmed, bullish_confirmed)}."""
    rsi = rsi_wilder(close, 14)
    macd = macd_hist if macd_hist is not None else macd_histogram(close)
    sto = stochastic(high, low, close, 14, 3)
    return dict(
        rsi=regular_divergence_signals(high, low, rsi, n),
        macd=regular_divergence_signals(high, low, macd, n),
        stoch=regular_divergence_signals(high, low, sto, n),
    )
