"""
User's new observation: the SPEED at which stochastic reaches an extreme,
relative to how far price actually moved to get there, carries real
information - a slow stochastic on a big price move (the range keeps
expanding faster than the oscillator can saturate) suggests a genuine,
strong trend; a fast stochastic on a small move suggests a tight,
choppy range. Genuinely new construction, not tested today.

For each excursion into oversold/overbought: measure bars_to_extreme
(how long it took) and price_distance (ATR-normalized, how far price
moved to get there). speed = price_distance / bars_to_extreme - a
directly literal "ATR per bar" measure of conviction. Tested as a
confirmation filter on the same stochastic-extreme-exit trigger used
in earlier constructions (Aurelius's own real M5 signal doesn't use
stochastic at all - this is a standalone oscillator construction).

Real M5 data (this chart's own timeframe), real spread, correct
single-position sequencing and walk-forward from the start.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m15_light_stack_test import realistic_single_position, block_report


def stochastic(high, low, close, period=14, smooth=3):
    hh = pd.Series(high).rolling(period).max().values
    ll = pd.Series(low).rolling(period).min().values
    rng = hh - ll
    with np.errstate(divide="ignore", invalid="ignore"):
        k_raw = np.where(rng > 0, 100.0 * (close - ll) / np.where(rng > 0, rng, 1.0), np.nan)
    k = pd.Series(k_raw).rolling(smooth).mean().values
    return k


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    time = df5["time"].values

    k = stochastic(high, low, close, period=14, smooth=3)
    OS, OB = 20.0, 80.0

    # find each excursion: the bar it FIRST enters oversold/overbought,
    # and the bar just before it started dropping/rising into it
    in_os = k <= OS
    in_ob = k >= OB
    enter_os = in_os & ~np.concatenate(([False], in_os[:-1]))
    enter_ob = in_ob & ~np.concatenate(([False], in_ob[:-1]))
    exit_os = (k > OS) & (np.concatenate(([np.nan], k[:-1])) <= OS)
    exit_ob = (k < OB) & (np.concatenate(([np.nan], k[:-1])) >= OB)

    LOOKBACK_START = 60  # how far back to search for where THIS excursion began (k last NOT extreme)

    def compute_speed(enter_mask, was_falling):
        speeds = np.full(n, np.nan)
        idxs = np.where(enter_mask)[0]
        for i in idxs:
            # find the most recent bar before i where k was on the "normal" side (not already extreme)
            start = None
            for j in range(i - 1, max(0, i - LOOKBACK_START) - 1, -1):
                if was_falling and k[j] > OS + 20:   # comfortably not oversold, e.g. >40
                    start = j; break
                if (not was_falling) and k[j] < OB - 20:  # comfortably not overbought, e.g. <60
                    start = j; break
            if start is None or np.isnan(atr[start]) or atr[start] <= 0:
                continue
            bars = i - start
            dist = abs(close[i] - close[start]) / atr[start]
            speeds[i] = dist / max(bars, 1)
        return speeds

    speed_os = compute_speed(enter_os, was_falling=True)
    speed_ob = compute_speed(enter_ob, was_falling=False)

    valid_os = speed_os[~np.isnan(speed_os)]
    valid_ob = speed_ob[~np.isnan(speed_ob)]
    print(f"n_bars={n} (~{n/288:.0f} trading days)")
    print(f"oversold entries with valid speed: {len(valid_os)}, median speed={np.median(valid_os):.4f} ATR/bar")
    print(f"overbought entries with valid speed: {len(valid_ob)}, median speed={np.median(valid_ob):.4f} ATR/bar\n")

    # attach the speed value (computed at ENTRY into the extreme) forward to
    # the EXIT bar (where the actual trade trigger fires), via the most
    # recent enter_os/enter_ob speed value seen
    speed_at_exit_os = np.full(n, np.nan)
    speed_at_exit_ob = np.full(n, np.nan)
    last_os, last_ob = np.nan, np.nan
    for i in range(n):
        if not np.isnan(speed_os[i]):
            last_os = speed_os[i]
        if not np.isnan(speed_ob[i]):
            last_ob = speed_ob[i]
        if exit_os[i]:
            speed_at_exit_os[i] = last_os
        if exit_ob[i]:
            speed_at_exit_ob[i] = last_ob

    def run(name, buy_mask, sell_mask):
        trig = [(i, 1.0) for i in np.where(buy_mask)[0]] + [(i, -1.0) for i in np.where(sell_mask)[0]]
        trig.sort(key=lambda t: t[0])
        print("=" * 70)
        print(f"{name}: {len(trig)} triggers -> {len(trig)/(n/288):.2f}/day")
        if len(trig) < 20:
            print("  too few"); return
        best = None
        for maxhold, label in ((48, "4h"), (144, "12h"), (288, "1day")):
            print(f"  --- max hold {maxhold} bars ({label}) ---")
            for tp_atr, sl_atr in ((1.0, 1.0), (1.5, 1.0), (2.0, 1.5)):
                trades, skipped = realistic_single_position(trig, close, high, low, spread, atr, n, tp_atr, sl_atr, maxhold)
                if not trades:
                    print(f"    tp={tp_atr} sl={sl_atr}: 0 trades"); continue
                pnls = np.array([t[2] for t in trades])
                entries = np.array([t[0] for t in trades])
                gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
                pf = gw / gl if gl > 0 else float("inf")
                cutoff = int(n * 0.7)
                is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
                print(f"    tp={tp_atr} sl={sl_atr} (skipped {skipped}): n={len(trades)} net={pnls.sum():.2f} "
                      f"win%={100*(pnls>0).mean():.1f} pf={pf:.3f} IS={is_net:.2f} OOS={oos_net:.2f}")
                if best is None or pnls.sum() > best[0]:
                    best = (pnls.sum(), maxhold, tp_atr, sl_atr, trades)
        if best:
            net, maxhold, tp_atr, sl_atr, trades = best
            print(f"  walk-forward on best cell: maxhold={maxhold} tp={tp_atr} sl={sl_atr} net={net:.2f} n={len(trades)}")
            block_report(trades, n, 5, time)

    # baseline: all oversold/overbought exits, no speed filter (reversal trade)
    run("BASELINE reversal (no speed filter): buy on oversold-exit, sell on overbought-exit",
        exit_os, exit_ob)

    # SLOW stochastic (big move, slow saturation) = strong trend -> trade the CONTINUATION
    # (i.e. sell after a SLOW overbought (trend was strong up, now reversing hard),
    # buy after a SLOW oversold) - testing the reversal trade filtered to slow/strong moves only
    med_os = np.nanmedian(speed_os)
    med_ob = np.nanmedian(speed_ob)
    slow_buy = exit_os & (speed_at_exit_os < med_os)
    slow_sell = exit_ob & (speed_at_exit_ob < med_ob)
    run(f"SLOW stochastic only (speed < median, big move / strong trend): reversal trade",
        slow_buy, slow_sell)

    fast_buy = exit_os & (speed_at_exit_os >= med_os)
    fast_sell = exit_ob & (speed_at_exit_ob >= med_ob)
    run(f"FAST stochastic only (speed >= median, small move / choppy): reversal trade",
        fast_buy, fast_sell)
