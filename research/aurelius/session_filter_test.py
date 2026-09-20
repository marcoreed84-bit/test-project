"""
Session/liquidity-window filter - the one candidate this session hadn't
tested on its own merits (only the existing Friday-cutoff/near-close
LOGIC, which is session-AVOIDANCE, not session-SELECTION).

Empirically identified high-liquidity window from the real M5 data
(mean tick_volume and mean bar range by hour-of-day, broker server time):
hours 15-18 run ~2x the rest of the day (1094-1427 mean tick_volume vs a
600-800 baseline; 3.5-4.7 mean bar range vs 2-3). Hour 0 also spikes in
range but not volume - almost certainly the daily settlement gap, not
real intrabar liquidity, so excluded from the window rather than assumed.

Two tests, both using Aurelius's own REAL simulator (sim.py's simulate())
which has ALWAYS correctly enforced single-position-at-a-time - no repeat
of the overlap flaw that undermined the cloud-confluence candidates:

  A) FILTER on Aurelius's real validated M5 system - does restricting its
     existing real entries to the high-liquidity window improve it
     further? Permutation-null against random same-size draws from
     baseline's own trades (sr_reject_test.py's established pattern).
  B) Does session restriction RESCUE the trend+MA-bounce scalp
     construction that failed at every hold length tested earlier
     (scalp_bounce_test.py)? Same trigger (Aurelius's real trend+50MA-
     bounce arrays), same scalp TP/SL grid, restricted to the
     high-liquidity window only.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S
from sr_reject_test import split_stats, tail_concentration, permutation_test

HIGH_LIQ_HOURS = set(range(15, 19))  # 15,16,17,18


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df, h4, params=E.P)
    n = ctx["n"]
    hour = df["time"].dt.hour.values

    base_trades = S.simulate(ctx, params=E.P)
    print("BASELINE (Aurelius's real full system, all hours):", S.stats(base_trades))
    print(f"n_bars={n}\n")

    # ================= TEST A: session filter on Aurelius's real gate =================
    print("=" * 70)
    print(f"TEST A: restrict Aurelius's real entries to hours {sorted(HIGH_LIQ_HOURS)} (high-liquidity window)")

    def session_filter(ctx_, i, is_buy, _hour=hour):
        return int(_hour[i]) in HIGH_LIQ_HOURS

    cand_trades = S.simulate(ctx, params=E.P, extra_filter=session_filter)
    cst = S.stats(cand_trades)
    print("CANDIDATE (session-restricted):", cst)
    c_is, c_oos = split_stats(cand_trades, n)
    tail = tail_concentration(cand_trades)
    perm = permutation_test(base_trades, cand_trades, n_draws=800)
    print(f"IS: {c_is}")
    print(f"OOS: {c_oos}")
    print(f"tail: {tail}")
    print(f"permutation vs baseline's own trades: {perm}")

    # ================= TEST B: does session restriction rescue the scalp bounce? =================
    print("\n" + "=" * 70)
    print("TEST B: trend+MA-bounce SCALP construction, restricted to the same high-liquidity window")
    print("(same trigger as scalp_bounce_test.py, which failed at every setting tested unrestricted)")

    trend_buy = ctx["aligned_buy"]; trend_sell = ctx["aligned_sell"]
    bounce_buy = ctx["pullback_ok_buy"]; bounce_sell = ctx["pullback_ok_sell"]
    sig_buy = trend_buy & bounce_buy
    sig_sell = trend_sell & bounce_sell
    trig_buy = sig_buy & ~np.concatenate(([False], sig_buy[:-1]))
    trig_sell = sig_sell & ~np.concatenate(([False], sig_sell[:-1]))
    triggers_all = [(i, 1.0) for i in np.where(trig_buy)[0]] + [(i, -1.0) for i in np.where(trig_sell)[0]]
    triggers_all.sort(key=lambda t: t[0])
    triggers = [(i, d) for i, d in triggers_all if int(hour[i]) in HIGH_LIQ_HOURS]
    print(f"{len(triggers_all)} total triggers -> {len(triggers)} inside the high-liquidity window "
          f"({100*len(triggers)/len(triggers_all):.1f}%)")

    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    POINT = E.POINT

    def realistic_single_position_sim(triggers, tp_atr, sl_atr, maxhold):
        """Correct sequential simulator - only one position at a time,
        skips any trigger that fires while still in a trade. This is the
        lesson from the cloud-confluence overlap bug: no repeat here."""
        trades = []
        last_exit = -1
        skipped = 0
        for i, d in triggers:
            if i < last_exit:
                skipped += 1
                continue
            fill_i = i + 1
            if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
                continue
            raw = close[i]
            sc = spread[fill_i] * POINT
            is_buy = d > 0
            entry = raw + sc if is_buy else raw - sc
            tp = entry + tp_atr * atr[i] if is_buy else entry - tp_atr * atr[i]
            sl = entry - sl_atr * atr[i] if is_buy else entry + sl_atr * atr[i]
            exit_bar, pnl = None, None
            for k in range(fill_i, min(fill_i + maxhold, n)):
                if is_buy:
                    if high[k] >= tp: exit_bar, pnl = k, tp - entry; break
                    if low[k] <= sl: exit_bar, pnl = k, sl - entry; break
                else:
                    if low[k] <= tp: exit_bar, pnl = k, entry - tp; break
                    if high[k] >= sl: exit_bar, pnl = k, entry - sl; break
            if exit_bar is None:
                continue
            trades.append((i, exit_bar, pnl))
            last_exit = exit_bar
        return trades, skipped

    for maxhold, label in ((6, "~30min"), (12, "~1h"), (24, "~2h")):
        print(f"\n  --- max hold = {maxhold} bars ({label}) ---")
        for tp_atr, sl_atr in ((0.5, 0.5), (0.5, 0.75), (0.75, 0.75)):
            trades, skipped = realistic_single_position_sim(triggers, tp_atr, sl_atr, maxhold)
            if not trades:
                print(f"    tp={tp_atr} sl={sl_atr}: 0 trades"); continue
            pnls = np.array([t[2] for t in trades])
            gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
            pf = gw / gl if gl > 0 else float("inf")
            cutoff = int(n * 0.7)
            entries = np.array([t[0] for t in trades])
            is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
            print(f"    tp={tp_atr} sl={sl_atr} (skipped {skipped} overlaps): n={len(trades)} "
                  f"net={pnls.sum():.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
                  f"IS={is_net:.2f} OOS={oos_net:.2f}")
