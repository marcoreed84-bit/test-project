"""
Follow-up to cloud_stoch_test.py: sweeps Stochastic period AND
oversold/overbought threshold to check whether the single (14,3,3)/20-80
setting's rejection was a parameter-choice artifact or genuine. Reuses
that file's stochastic()/tp_sl_outcomes()/report_outcome_set() (same
directory, no engine.py collision risk since only one exists here).

Kept deliberately narrower than a full grid: 3 stochastic periods x 3
threshold pairs x 3 TP:SL ratios x ONE hold length (12 H4 bars, the
better-performing of the two tested previously) = 27 cells. The base
trigger population here is already small (a few hundred at most, often
far fewer at tighter thresholds) - a wider sweep would just inflate
best-of-N risk against results this project's own rigor already can't
support at this n. Total cell count is reported at the end explicitly
for that correction.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from cloud_stoch_test import (stochastic, tp_sl_outcomes, report_outcome_set,
                               LOOKBACK, TOL_ATR, REJECT_ATR)

MAXHOLD = 12  # ~2 days H4 - the better of the two hold lengths tested previously


def build_triggers(high, low, close, atr, cloud_top, cloud_bot, is_bull_cloud, is_bear_cloud,
                    k, os_thresh, ob_thresh, n):
    bull_sig = np.zeros(n, dtype=bool)
    bear_sig = np.zeros(n, dtype=bool)
    for i in range(LOOKBACK, n):
        if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(cloud_top[i]) or np.isnan(cloud_bot[i]):
            continue
        tol, rej = TOL_ATR * atr[i], REJECT_ATR * atr[i]
        win = range(max(0, i - LOOKBACK + 1), i + 1)
        if is_bull_cloud[i]:
            touched = any(low[j] <= cloud_top[i] + tol for j in win)
            oversold = any((not np.isnan(k[j])) and k[j] <= os_thresh for j in win)
            rejected = close[i] - cloud_top[i] >= rej
            bull_sig[i] = touched and oversold and rejected
        if is_bear_cloud[i]:
            touched = any(high[j] >= cloud_bot[i] - tol for j in win)
            overbought = any((not np.isnan(k[j])) and k[j] >= ob_thresh for j in win)
            rejected = cloud_bot[i] - close[i] >= rej
            bear_sig[i] = touched and overbought and rejected
    trig_bull = bull_sig & ~np.concatenate(([False], bull_sig[:-1]))
    trig_bear = bear_sig & ~np.concatenate(([False], bear_sig[:-1]))
    triggers = [(i, 1.0) for i in np.where(trig_bull)[0]] + [(i, -1.0) for i in np.where(trig_bear)[0]]
    triggers.sort(key=lambda t: t[0])
    return triggers


if __name__ == "__main__":
    d = E.load_h4()
    p = E.params()
    ctx = E.build_context(d, p)
    n = ctx["n"]
    high, low, close, atr = ctx["high"], ctx["low"], ctx["close"], ctx["atr"]
    cloud_top, cloud_bot = ctx["cloud_top"], ctx["cloud_bot"]
    ctx["spread"] = d["spread"].values.astype(float)

    D = p["displacement"]
    sa_sh = pd.Series(ctx["sa_raw"]).shift(D).values
    sb_sh = pd.Series(ctx["sb_raw"]).shift(D).values
    is_bull_cloud = sa_sh > sb_sh
    is_bear_cloud = sb_sh > sa_sh

    print(f"n_bars={n} (H4, ~{n/6:.0f} trading days), max hold fixed at {MAXHOLD} bars\n")

    total_cells = 0
    best_pct = -1.0
    best_label = None
    for period in (9, 14, 21):
        k, _ = stochastic(high, low, close, period=period)
        for os_t, ob_t in ((20.0, 80.0), (25.0, 75.0), (30.0, 70.0)):
            triggers = build_triggers(high, low, close, atr, cloud_top, cloud_bot,
                                       is_bull_cloud, is_bear_cloud, k, os_t, ob_t, n)
            print("=" * 70)
            print(f"Stochastic({period},3,3), oversold<={os_t}/overbought>={ob_t}: "
                  f"{len(triggers)} triggers -> {len(triggers)/(n/6):.3f}/day")
            if len(triggers) < 20:
                print("  too few triggers (<20), skipping TP/SL grid")
                continue
            for tp_atr, sl_atr in ((1.0, 1.0), (2.0, 1.5), (2.5, 1.5)):
                out, dropped = tp_sl_outcomes(ctx, triggers, tp_atr, sl_atr, maxhold=MAXHOLD)
                total_cells += 1
                if not out:
                    continue
                pnl_buy = np.array([o[0] for o in out]); pnl_sell = np.array([o[1] for o in out])
                real_dir = np.array([o[3] for o in out])
                real_pnl = np.where(real_dir > 0, pnl_buy, pnl_sell)
                rng = np.random.default_rng(0)
                rdir = rng.integers(0, 2, size=(2000, len(out)))
                random_nets = np.where(rdir == 1, pnl_buy, pnl_sell).sum(axis=1)
                pct = 100 * (random_nets < real_pnl.sum()).mean()
                label = f"period={period} os={os_t}/ob={ob_t} tp={tp_atr} sl={sl_atr}"
                report_outcome_set(f"tp={tp_atr}xATR sl={sl_atr}xATR (dropped={dropped}/{len(triggers)})", out, n)
                if pct > best_pct:
                    best_pct = pct
                    best_label = label

    print("\n" + "=" * 70)
    print(f"TOTAL CELLS TESTED THIS SWEEP: {total_cells} (+ 8 from the earlier single-setting test "
          f"= {total_cells + 8} total across both scripts)")
    print(f"Best single random-direction percentile seen: {best_pct:.1f} ({best_label}) - "
          f"judge this against a best-of-{total_cells + 8} correction, not at face value.")
