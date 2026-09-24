"""
DIVERGENCE AS A STANDALONE SYSTEM - not bolted onto Aurelius/Meridian/Ratchet.

User's ask: does classic RSI / MACD-histogram / Stochastic divergence work as
a complete trading system on its own - divergence decides BOTH the entry AND
the exit, nothing else (no MA stack, no S/R filter, no ATR stop borrowed from
the shipped EAs). This is deliberately separate from the sibling research
that bolts divergence onto an existing EA's entries as an early-exit trigger
(see git history around this commit for that work, touching Aurelius_EA.mq5 /
Aurelius_M15_EA.mq5 / Meridian_EA.mq5 / Ratchet_EA.mq5 and research/
divergence.py) - none of those files are read or touched from here.

================================ CONSTRUCTION ================================

Swing-pivot definition (this materially affects results, so stated exactly):
a standard 5-bar ("N=2") fractal, the same pivot definition as the classic
Bill Williams Fractals indicator. Bar i is a swing HIGH iff
    high[i] > high[i-1], high[i-2]  AND  high[i] > high[i+1], high[i+2]
(strict inequality both sides; a swing LOW is the mirror image on `low`).
Because it needs 2 bars to its right, a pivot at bar i is only KNOWN once bar
i+2 has closed - that bar (i+2) is the pivot's "confirm bar". No pivot is
used before its confirm bar; this is the no-lookahead boundary for the whole
system.

Divergence (regular/classic divergence only, not hidden divergence):
  - Bullish: at a new confirmed swing-LOW pivot, price makes a LOWER low than
    the immediately preceding swing-low pivot, while the oscillator's value
    at the new pivot bar is HIGHER than at the preceding swing-low pivot
    bar. -> ENTRY signal: LONG.
  - Bearish: at a new confirmed swing-HIGH pivot, price makes a HIGHER high
    than the immediately preceding swing-high pivot, while the oscillator is
    LOWER than at the preceding swing-high pivot bar. -> ENTRY signal: SHORT.
Comparison is always against the immediately preceding pivot of the SAME
type (the standard textbook definition) - not against some N-bar lookback
window, and not against "any lower low in the recent past".

Exit rule (identical across all three oscillators, deliberately structural,
not borrowed from any shipped EA's exit machinery):
  Exit at the next confirmed swing pivot of the OPPOSITE type from the one
  that opened the trade - a long (opened at a swing LOW) exits at the next
  confirmed swing HIGH; a short (opened at a swing HIGH) exits at the next
  confirmed swing LOW. This fires regardless of whether that opposing pivot
  itself carries a confirming divergence. This is a hybrid of the two
  structural options named in the task brief: when the opposing pivot DOES
  show divergence, this is exactly "exit on the first opposing divergence
  signal" (and immediately re-opens in the new direction, since the same
  event is also an entry trigger); when it does NOT, this is exactly "a
  simple invalidation - a new extreme against the position with no
  confirming divergence". Using one pivot-stream for both entry and exit
  keeps the whole system self-consistent (same pivot machinery, no borrowed
  ATR stop, no arbitrary opposite-signal wait) and guarantees the position
  is flat before the next entry can fire, so single-position sequencing is
  automatic. One consequence, reported honestly below: with no time or
  price stop, a trade can run a long time (and lose a lot) before an
  opposing pivot ever confirms - this is exactly the whipsaw/no-stop risk a
  pure divergence system carries with no trend filter, not a bug being
  hidden.

Execution / realism (matches this repo's existing Python-research
convention, see research/aurelius/engine.py and .../stoch_speed_test.py):
  - Data: real GOLD# M5 export via engine.load_m5() (2023-01-03..2026-08-14)
    and M15 via engine.resample_m15_from_m5() (lossless 3-bar M5 resample,
    same convention Aurelius_M15's own research uses).
  - Real per-bar spread (real `spread` column, POINT=0.01), charged on BOTH
    entry and exit. This differs from the TP/SL-limit-order convention used
    elsewhere in this repo (spread charged once, at entry, since a limit
    order fills at its exact level) because every exit here is an ACTIVE,
    signal-driven market exit, not a resting order - a real market exit
    genuinely crosses the spread a second time, so charging it once would
    understate cost.
  - Fill convention: signal confirmed at bar i's close -> filled at bar i+1
    (using close[i] as the fill reference, same approximation engine.py's
    realistic_single_position() uses, justified there as "essentially the
    new bar's open tick" for continuous GOLD trading).
  - One open position at a time, no pyramiding: a same-type pivot while
    already in a same-direction trade is ignored; only the opposite-type
    pivot can end a trade, and a new entry can only open while flat.
  - Walk-forward from the start of the real data; this repo's existing
    scripts commonly also report a 70/30 in-sample/out-of-sample split
    (e.g. stoch_speed_test.py, m15_light_stack_test.py) - reported here too.
  - A position still open at the very end of the data (no opposing pivot
    ever confirmed) is dropped from the trade list, same convention as
    engine.py's realistic_single_position() dropping trades that never
    resolve within their hold window. This affects at most one trade per
    run.

Oscillators tested (all computed on CLOSE, standard settings):
  - RSI(14), Wilder smoothing (reuses engine.smma(), the same recursive
    Wilder smoothing engine.py validates for ATR - RSI's avg-gain/avg-loss
    use the identical recursion).
  - MACD histogram (12/26/9): MACD main = EMA(12)-EMA(26), signal = SMA(9)
    of the main line - the same "MT5 bundled indicator" convention
    engine.py's build_context() documents and uses (MT5's own MACD smooths
    the signal line with a simple MA, not an EMA).
  - Stochastic(14,3): reused verbatim, read-only import, from
    research/aurelius/stoch_speed_test.py's stochastic() helper.

=================================== RESULTS ====================================
Real run, GOLD# M5 (256,318 bars, 2023-01-03..2026-08-14) and the lossless
M15 resample (85,445 bars). Net in raw GOLD price points per 1.0 notional
lot - this repo's existing Python-research convention (see engine.py /
meridian_dd_confluence_test.py), NOT multiplied by contract size. IS/OOS =
first-70%/last-30% of bars by entry time, this repo's standard split.

  System                    TF   Trades   Net       PF     Win%   ClosedDD  FloatDD   IS net    OOS net
  RSI(14) divergence        M5    7193   -2199.30  0.789   35.2   2291.06   2292.59  -1487.31   -711.99
  MACD-hist(12,26,9) div.   M5    9198   -3384.96  0.756   35.2   3399.12   3404.31  -1952.34  -1432.62
  Stochastic(14,3) div.     M5    7983   -2538.03  0.794   35.9   2591.51   2600.75  -1656.13   -881.90
  RSI(14) divergence        M15   2500    -934.68  0.855   37.8    960.43    978.51   -744.60   -190.09
  MACD-hist(12,26,9) div.   M15   3169   -1499.69  0.826   37.7   1534.44   1549.00  -1019.94   -479.75
  Stochastic(14,3) div.     M15   2774   -1854.78  0.779   37.9   1854.11   1857.01   -896.20   -958.58

Every one of the six system/timeframe combinations loses money net of real
spread, with PF < 1 and both the in-sample AND out-of-sample legs negative
(not just one bad sub-period dragging a decent one down - both halves lose
independently in all six cases). Win rate clusters 35-38% everywhere.

================================== VERDICT =====================================
None of the three oscillators stand on their own as a viable standalone
system on GOLD M5 or M15, under this construction. This is a real, honest
negative result, not a marginal one dressed up - PF is below 1.0 in all six
cells, by a similar margin M5 and M15, and the loss is consistent across
both the walk-forward IS and OOS halves rather than concentrated in one
period (which would suggest bad luck / a regime shift rather than a
structural flaw). GOLD 2023-2026 spent long stretches in a strong sustained
uptrend; a pure regular-divergence entry with no trend/alignment filter
fires repeatedly INTO that trend on both sides (bearish divergence -> short
against a strong uptrend is exactly the classic divergence failure mode the
task called out up front), and the "exit on next opposing pivot" rule, with
no time or hard-stop, lets those counter-trend trades run against the
position for a long time before finally closing - which is exactly why
floatDD tracks closedDD closely everywhere above (positions were often
marked down hard while open, not just realized-losers after the fact).
Faster oscillators (RSI/Stochastic) fire slightly less often than MACD-hist
divergence and lose somewhat less in absolute terms, but the difference is
one of degree, not of viability - all three are negative-expectancy here.
This matches, rather than contradicts, this repo's own experience with
Aurelius/Meridian/Ratchet: divergence alone, with no broader trend/alignment
context, is a classic false-signal-prone construction, and these numbers
are consistent with treating it as an ADD-ON confirmation/exit signal
layered onto an already-trend-aligned entry (the sibling work in this
branch) rather than a source of standalone entries. No parameter or filter
sweep was run to try to rescue any of the six cells - the brief asked for
the standalone system as specified, reported honestly, not an optimized
variant of it.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "aurelius"))
import numpy as np
import pandas as pd
import engine as E
from stoch_speed_test import stochastic

POINT = E.POINT


# ------------------------------ oscillators --------------------------------

def wilder_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Classic Wilder RSI: avg gain/loss use the exact same SMA-seed-then-
    recursive-Wilder-smoothing construction as engine.wilder_atr() (seed =
    mean of the first `period` REAL deltas, i.e. indices 1..period, output
    starts at index `period` - deliberately NOT engine.smma(), whose seed
    window would include the fake index-0 "delta" and be off by one bar
    versus textbook Wilder RSI)."""
    n = len(close)
    delta = np.zeros(n)
    delta[1:] = close[1:] - close[:-1]
    gain = np.maximum(delta, 0.0)
    loss = np.maximum(-delta, 0.0)
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)
    if n > period:
        avg_gain[period] = np.mean(gain[1:period + 1])
        avg_loss[period] = np.mean(loss[1:period + 1])
        for i in range(period + 1, n):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = np.where((avg_loss == 0) & (avg_gain == 0), 50.0, rsi)
    rsi = np.where((avg_loss == 0) & (avg_gain > 0), 100.0, rsi)
    return rsi


def macd_histogram(close: np.ndarray, fast=12, slow=26, signal=9) -> np.ndarray:
    """MACD main = EMA(fast)-EMA(slow); signal = SMA(signal) of main - the
    same MT5-bundled-indicator convention engine.build_context() uses."""
    n = len(close)
    main = E.ma(close, fast, "ema") - E.ma(close, slow, "ema")
    valid = ~np.isnan(main)
    sig = np.full(n, np.nan)
    if valid.any():
        first = int(np.argmax(valid))
        sig[first:] = E.ma(main[first:], signal, "sma")
    return main - sig


# ------------------------------ swing pivots --------------------------------

def swing_pivots(high: np.ndarray, low: np.ndarray, left: int = 2, right: int = 2):
    """Standard N=2 (5-bar) fractal pivot, i.e. the classic Bill Williams
    Fractals definition: strictly the highest high / lowest low of the
    `left`+1+`right` bar window centered on i. Vectorized via shifted
    comparisons. Returns two bool arrays; pivot at i is only KNOWN at bar
    i+right (its confirm bar) - callers must not use it before then."""
    n = len(high)
    is_high = np.ones(n, dtype=bool)
    is_low = np.ones(n, dtype=bool)
    for k in list(range(1, left + 1)) + [-j for j in range(1, right + 1)]:
        shifted_h = np.roll(high, k)
        shifted_l = np.roll(low, k)
        cmp_h = high > shifted_h
        cmp_l = low < shifted_l
        if k > 0:
            cmp_h[:k] = False
            cmp_l[:k] = False
        else:
            cmp_h[k:] = False
            cmp_l[k:] = False
        is_high &= cmp_h
        is_low &= cmp_l
    is_high[:left] = False
    is_high[n - right:] = False
    is_low[:left] = False
    is_low[n - right:] = False
    return is_high, is_low


# --------------------------- divergence events ------------------------------

def build_events(is_high, is_low, high, low, osc, right):
    """One event per confirmed pivot, in confirm-bar order:
    (confirm_bar, ptype in {'high','low'}, divergence bool, pivot_bar, pivot_price)."""
    events = []
    prev_low_bar = None
    for i in np.where(is_low)[0]:
        if np.isnan(osc[i]):
            continue
        div = False
        if prev_low_bar is not None and not np.isnan(osc[prev_low_bar]):
            div = (low[i] < low[prev_low_bar]) and (osc[i] > osc[prev_low_bar])
        events.append((i + right, "low", div, i, low[i]))
        prev_low_bar = i
    prev_high_bar = None
    for i in np.where(is_high)[0]:
        if np.isnan(osc[i]):
            continue
        div = False
        if prev_high_bar is not None and not np.isnan(osc[prev_high_bar]):
            div = (high[i] > high[prev_high_bar]) and (osc[i] < osc[prev_high_bar])
        events.append((i + right, "high", div, i, high[i]))
        prev_high_bar = i
    events.sort(key=lambda e: (e[0], e[3]))
    return events


# ------------------------------- simulation ----------------------------------

def simulate(events, close, spread, n):
    """Entry AND exit both driven by `events` (see module docstring for the
    exact rule). Spread charged on both legs (active market exits, not
    resting limit orders). Single position at a time. Returns
    [(entry_fill_bar, exit_fill_bar, pnl, is_buy, entry_price), ...]."""
    trades = []
    pos = None  # dict(is_buy, entry_fill, entry_price)
    for confirm_bar, ptype, div, pivot_bar, pivot_price in events:
        fill_bar = confirm_bar + 1
        if fill_bar >= n or np.isnan(close[confirm_bar]) or np.isnan(spread[fill_bar]):
            continue
        sc = spread[fill_bar] * POINT
        raw = close[confirm_bar]

        if pos is not None:
            opposite = "high" if pos["is_buy"] else "low"
            if ptype == opposite:
                exit_price = raw - sc if pos["is_buy"] else raw + sc
                pnl = (exit_price - pos["entry_price"]) if pos["is_buy"] else (pos["entry_price"] - exit_price)
                trades.append((pos["entry_fill"], fill_bar, pnl, pos["is_buy"], pos["entry_price"]))
                pos = None

        if pos is None and div:
            is_buy = (ptype == "low")
            entry_price = raw + sc if is_buy else raw - sc
            pos = dict(is_buy=is_buy, entry_fill=fill_bar, entry_price=entry_price)

    # unresolved final position dropped (matches engine.py's convention of
    # dropping trades that never resolve within the data available)
    return trades


def drawdown_stats(trades, close, spread, n):
    """Closed-equity max DD + bar-by-bar mark-to-market floating max DD,
    same construction as research/aurelius/meridian_dd_confluence_test.py's
    drawdown_stats() (reimplemented locally here, not imported, to keep this
    standalone module free of any dependency on files the sibling divergence
    work might be touching)."""
    if not trades:
        return 0.0, 0.0
    pnls = np.array([t[2] for t in trades])
    closed_equity = np.cumsum(pnls)
    closed_dd = (np.maximum.accumulate(closed_equity) - closed_equity).max()

    eq_prior = np.concatenate(([0.0], closed_equity[:-1]))
    mtm = np.full(n, np.nan)
    last_eq, prev_exit = 0.0, -1
    for idx, (entry_fill, exit_fill, pnl, is_buy, entry_price) in enumerate(trades):
        if prev_exit + 1 <= entry_fill - 1:
            mtm[prev_exit + 1:entry_fill] = last_eq
        seg = close[entry_fill:exit_fill + 1]
        floating = (seg - entry_price) if is_buy else (entry_price - seg)
        mtm[entry_fill:exit_fill + 1] = last_eq + floating
        last_eq = eq_prior[idx] + pnl
        prev_exit = exit_fill
    mtm[prev_exit + 1:] = last_eq
    if trades:
        mtm[:trades[0][0] + 1] = 0.0
    valid = ~np.isnan(mtm)
    mtm_v = mtm[valid]
    float_dd = (np.maximum.accumulate(mtm_v) - mtm_v).max() if len(mtm_v) else 0.0
    return closed_dd, float_dd


def report(label, trades, n, time, close, spread):
    print("=" * 78)
    if not trades:
        print(f"{label}: 0 trades")
        return
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum()
    gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    win_pct = 100.0 * (pnls > 0).mean()
    closed_dd, float_dd = drawdown_stats(trades, close, spread, n)
    cutoff = int(n * 0.7)
    is_net = pnls[entries < cutoff].sum()
    oos_net = pnls[entries >= cutoff].sum()
    t0 = pd.to_datetime(time[trades[0][0]]).date()
    t1 = pd.to_datetime(time[min(trades[-1][1], n - 1)]).date()
    print(f"{label}")
    print(f"  n={len(trades):4d}  net={pnls.sum():9.2f}  pf={pf:7.3f}  win%={win_pct:5.1f}  "
          f"closedDD={closed_dd:8.2f}  floatDD={float_dd:8.2f}")
    print(f"  IS(<70%)={is_net:9.2f}  OOS(>=70%)={oos_net:9.2f}  span=[{t0} -> {t1}]")
    return dict(label=label, n=len(trades), net=pnls.sum(), pf=pf, win_pct=win_pct,
                closed_dd=closed_dd, float_dd=float_dd, is_net=is_net, oos_net=oos_net)


def run_timeframe(tf_label, close, high, low, spread, time, n):
    print("\n" + "#" * 78)
    print(f"# {tf_label}: n={n} bars")
    print("#" * 78)

    is_high, is_low = swing_pivots(high, low, left=2, right=2)
    n_piv_h, n_piv_l = is_high.sum(), is_low.sum()
    print(f"fractal pivots (N=2, 5-bar): {n_piv_h} swing highs, {n_piv_l} swing lows")

    rsi = wilder_rsi(close, 14)
    macd_h = macd_histogram(close, 12, 26, 9)
    stoch_k = stochastic(high, low, close, period=14, smooth=3)

    results = []
    for osc_name, osc in (("RSI(14)", rsi), ("MACD-hist(12,26,9)", macd_h), ("Stochastic(14,3)", stoch_k)):
        events = build_events(is_high, is_low, high, low, osc, right=2)
        n_div = sum(1 for e in events if e[2])
        trades = simulate(events, close, spread, n)
        r = report(f"{osc_name} divergence [{tf_label}]  ({n_div} raw divergence signals)",
                   trades, n, time, close, spread)
        if r:
            results.append(r)
    return results


if __name__ == "__main__":
    df5 = E.load_m5()
    close5 = df5["close"].values.astype(float)
    high5 = df5["high"].values.astype(float)
    low5 = df5["low"].values.astype(float)
    spread5 = df5["spread"].values.astype(float)
    time5 = df5["time"].values
    n5 = len(df5)

    df15 = E.resample_m15_from_m5(df5)
    close15 = df15["close"].values.astype(float)
    high15 = df15["high"].values.astype(float)
    low15 = df15["low"].values.astype(float)
    spread15 = df15["spread"].values.astype(float)
    time15 = df15["time"].values
    n15 = len(df15)

    all_results = []
    all_results += run_timeframe("M5", close5, high5, low5, spread5, time5, n5)
    all_results += run_timeframe("M15", close15, high15, low15, spread15, time15, n15)

    print("\n" + "=" * 78)
    print("SUMMARY (all 6 system/timeframe combinations)")
    print("=" * 78)
    for r in all_results:
        print(f"  {r['label']:55s} n={r['n']:4d} net={r['net']:9.2f} pf={r['pf']:7.3f} "
              f"win%={r['win_pct']:5.1f} closedDD={r['closed_dd']:8.2f} floatDD={r['float_dd']:8.2f}")
