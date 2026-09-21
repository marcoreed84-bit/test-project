"""
User's construction: M15 stochastic provides the broader context (e.g.
still oversold), M5 stochastic provides the precise entry timing (a
local turn), rather than picking one timeframe to "trust." This directly
resolves "which stochastic" by using both together - M15 as filter,
M5 as trigger.

Time-alignment done via real timestamps (pd.merge_asof), not bar-
position arithmetic, to avoid any lookahead or misalignment risk: each
M5 bar is matched to the most recently CLOSED M15 bar as of that
moment (M15 bar's close time <= M5 bar's own time), never the still-
forming M15 bar.

Real M5/M15 data (M15 resampled from the same validated M5 CSV), real
spread, correct single-position sequencing and walk-forward from the
start.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m15_light_stack_test import realistic_single_position, block_report
from stoch_speed_test import stochastic

if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    time5 = df5["time"].values

    k5 = stochastic(high, low, close, period=14, smooth=3)

    df15 = E.resample_m15_from_m5(df5)
    c15, h15, l15 = df15["close"].values, df15["high"].values, df15["low"].values
    k15 = stochastic(h15, l15, c15, period=14, smooth=3)
    # M15 bar's "time" column = its OPEN time (pandas resample default,
    # left-labeled) - the value becomes SAFE TO USE only once that bar
    # has fully CLOSED, i.e. at open_time + 15min
    m15_close_time = df15["time"] + pd.Timedelta(minutes=15)
    m15_lookup = pd.DataFrame({"close_time": m15_close_time, "k15": k15}).sort_values("close_time")

    m5_times = pd.DataFrame({"time": df5["time"].values})
    merged = pd.merge_asof(m5_times, m15_lookup, left_on="time", right_on="close_time", direction="backward")
    k15_at_m5 = merged["k15"].values   # the most recently CLOSED M15 stochastic, as of each M5 bar - no lookahead

    print(f"n_bars={n} M5 (~{n/288:.0f} trading days)\n")
    print(f"sanity check - first valid M15-at-M5 alignment: "
          f"{merged.dropna().iloc[0]['time']} -> M15 close_time {merged.dropna().iloc[0]['close_time']}\n")

    # M5 local-turn trigger: %K makes a local trough (buy) or local peak (sell)
    k5_trough = (k5[1:-1] < k5[:-2]) & (k5[1:-1] <= k5[2:])
    k5_peak = (k5[1:-1] > k5[:-2]) & (k5[1:-1] >= k5[2:])
    k5_trough_full = np.concatenate(([False], k5_trough, [False]))
    k5_peak_full = np.concatenate(([False], k5_peak, [False]))

    def run(name, buy_mask, sell_mask, holds=((12, "1h"), (48, "4h"), (144, "12h")),
            ratios=((0.5, 0.5), (1.0, 0.75), (1.5, 1.0))):
        trig = [(i, 1.0) for i in np.where(buy_mask)[0]] + [(i, -1.0) for i in np.where(sell_mask)[0]]
        trig.sort(key=lambda t: t[0])
        print("=" * 70)
        print(f"{name}: {len(trig)} triggers -> {len(trig)/(n/288):.2f}/day")
        if len(trig) < 20:
            print("  too few"); return
        best = None
        for maxhold, label in holds:
            print(f"  --- max hold {maxhold} bars ({label}) ---")
            for tp_atr, sl_atr in ratios:
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
            block_report(trades, n, 5, time5)

    for m15_thresh in (30.0, 20.0):
        buy = k5_trough_full & (k15_at_m5 <= m15_thresh)
        sell = k5_peak_full & (k15_at_m5 >= 100 - m15_thresh)
        run(f"M15 context <= {m15_thresh}/>={100-m15_thresh} (oversold/overbought) + M5 local turn trigger", buy, sell)
