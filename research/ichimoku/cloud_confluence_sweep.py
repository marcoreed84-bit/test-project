"""
Parameter-robustness sweep for the two candidates that passed the cloud-
confluence walk-forward (MACD, FVG) - the step that should have come
BEFORE calling them promising, not after (see conversation: this was
skipped the first time, called out, and is being done properly now,
matching how the Stochastic candidate was swept before its own
walk-forward later killed it).

MACD: 3 period-sets (12/26/9 classic, 5/13/6 fast, 19/39/9 slow).
FVG: 3 confirmation-window lengths (4, 8, 16 bars - how recently the gap
must have formed relative to the cloud touch).

Reuses tp_sl_outcomes/report_and_walkforward/edge_trigger from
cloud_confluence_test.py unchanged (same directory, safe import).
touch_reject() is re-implemented here with LOOKBACK as a parameter
(it was a closure over a fixed constant in the original file).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from cloud_confluence_test import tp_sl_outcomes, report_and_walkforward, edge_trigger, TOL_ATR, REJECT_ATR


def touch_reject(n, atr, cloud_top, cloud_bot, is_bull_cloud, is_bear_cloud,
                  low, high, close, lookback, bull_confirm_fn, bear_confirm_fn):
    bull_sig = np.zeros(n, dtype=bool); bear_sig = np.zeros(n, dtype=bool)
    for i in range(lookback, n):
        if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(cloud_top[i]) or np.isnan(cloud_bot[i]):
            continue
        tol, rej = TOL_ATR * atr[i], REJECT_ATR * atr[i]
        win = range(max(0, i - lookback + 1), i + 1)
        if is_bull_cloud[i]:
            touched = any(low[j] <= cloud_top[i] + tol for j in win)
            confirmed = any(bull_confirm_fn(j) for j in win)
            rejected = close[i] - cloud_top[i] >= rej
            bull_sig[i] = touched and confirmed and rejected
        if is_bear_cloud[i]:
            touched = any(high[j] >= cloud_bot[i] - tol for j in win)
            confirmed = any(bear_confirm_fn(j) for j in win)
            rejected = cloud_bot[i] - close[i] >= rej
            bear_sig[i] = touched and confirmed and rejected
    return edge_trigger(bull_sig, bear_sig)


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

    print(f"n_bars={n} (H4, ~{n/6:.0f} trading days)\n")
    total_cells = 0

    print("=" * 70)
    print("MACD ROBUSTNESS SWEEP - 3 period-sets x 2 TP:SL ratios, LOOKBACK=8 fixed")
    for fast, slow, sig_p, tag in ((12, 26, 9, "classic"), (5, 13, 6, "fast"), (19, 39, 9, "slow")):
        ema_f = pd.Series(close).ewm(span=fast, adjust=False).mean().values
        ema_s = pd.Series(close).ewm(span=slow, adjust=False).mean().values
        macd_line = ema_f - ema_s
        macd_sig = pd.Series(macd_line).ewm(span=sig_p, adjust=False).mean().values
        hist = macd_line - macd_sig
        trig = touch_reject(n, atr, cloud_top, cloud_bot, is_bull_cloud, is_bear_cloud,
                             low, high, close, 8,
                             lambda j: (not np.isnan(hist[j])) and hist[j] > 0,
                             lambda j: (not np.isnan(hist[j])) and hist[j] < 0)
        print(f"\n--- MACD({fast},{slow},{sig_p}) [{tag}]: {len(trig)} triggers -> {len(trig)/(n/6):.3f}/day ---")
        if len(trig) < 20:
            print("  too few triggers, skipping"); continue
        for tp_atr, sl_atr in ((2.0, 1.5), (2.5, 1.5)):
            out, dropped = tp_sl_outcomes(ctx, trig, tp_atr, sl_atr)
            total_cells += 1
            report_and_walkforward(f"tp={tp_atr}xATR sl={sl_atr}xATR", out, ctx, dropped, len(trig))

    print("\n" + "=" * 70)
    print("FVG ROBUSTNESS SWEEP - 3 confirmation-window lengths x 2 TP:SL ratios")
    bull_fvg_at = np.zeros(n, dtype=bool); bear_fvg_at = np.zeros(n, dtype=bool)
    bull_fvg_at[2:] = low[2:] > high[:-2]
    bear_fvg_at[2:] = high[2:] < low[:-2]
    for lookback in (4, 8, 16):
        trig = touch_reject(n, atr, cloud_top, cloud_bot, is_bull_cloud, is_bear_cloud,
                             low, high, close, lookback,
                             lambda j: bull_fvg_at[j], lambda j: bear_fvg_at[j])
        print(f"\n--- FVG confirm-window={lookback} bars: {len(trig)} triggers -> {len(trig)/(n/6):.3f}/day ---")
        if len(trig) < 20:
            print("  too few triggers, skipping"); continue
        for tp_atr, sl_atr in ((2.0, 1.5), (2.5, 1.5)):
            out, dropped = tp_sl_outcomes(ctx, trig, tp_atr, sl_atr)
            total_cells += 1
            report_and_walkforward(f"tp={tp_atr}xATR sl={sl_atr}xATR", out, ctx, dropped, len(trig))

    print(f"\n\nTOTAL CELLS THIS SWEEP: {total_cells} (+ earlier cloud-confluence cells this session "
          f"for the running best-of-N total)")
