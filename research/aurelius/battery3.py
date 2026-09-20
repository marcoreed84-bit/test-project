"""
Tests Supertrend, Parabolic SAR, and a tick-volume-proxy Volume Profile
POC against Aurelius's real M5 gold data - forwarded from a message that
predates the data-loss incident, not scoped to Aurelius specifically but
tested here since this is the only EA with a validated Python engine.

Three constructions per indicator, all against the SAME real baseline
(Aurelius's actual v1.46 shipped signal) or the SAME real cost model
(spread charged once at entry, same as sim.py):

  FILTER   - only take Aurelius's real entries when the indicator agrees
             with the trade direction. Rigor: permutation-null against
             random same-size draws from the baseline's OWN trades
             (sr_reject_test.py's established pattern).
  FLIP-HOLD- trade the indicator's own flip as entry, hold until the next
             opposite flip (pure trend-following, no separate TP/SL).
  TP/SL    - trade the indicator's own flip/trigger as entry, small fixed
             ATR-multiple TP, wide ATR-multiple SL (the "small TP, wide
             SL" construction this project's rigor rule exists BECAUSE OF:
             that structure alone tends to look profitable regardless of
             real signal, which is exactly what the random-direction
             control below is for).

Random-direction control (both FLIP-HOLD and TP/SL): at every real
trigger bar, computes what BOTH a buy and a sell would have done from
that exact bar with the exact same TP/SL/hold structure, then compares
the real indicator's own direction choice against many random 50/50
direction draws over the same trigger set. This isolates whether the
indicator's DIRECTION carries information, separate from whether its
trigger frequency / TP-SL structure alone would look profitable.

VOLUME PROFILE CAVEAT: GOLD's real_volume column is 100% zero in this
dataset (checked directly). volume_poc() uses tick_volume (quote count)
as a proxy - NOT a genuine traded-size profile. Treat POC results with
extra skepticism versus Supertrend/PSAR, which are pure price/ATR and
have no such data gap.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
import sim as S
from engine import POINT
from indicators2 import supertrend, parabolic_sar, volume_poc
from sr_reject_test import split_stats, tail_concentration, permutation_test

N_RANDOM_SEEDS = 2000
MAXHOLD_BARS = 500  # ~1.7 days on M5 - bounded lookahead for the TP/SL construction


def find_flips(trend):
    idx = np.where((trend[1:] != trend[:-1]) & ~np.isnan(trend[1:]) & ~np.isnan(trend[:-1]))[0] + 1
    return idx


def flip_hold_outcomes(ctx, trend, flips):
    """For each flip k (except the last, which has no next flip to exit
    at), computes what a BUY and a SELL would each have earned holding
    from this flip to the next one - same raw price path, cost charged
    against whichever direction is actually chosen."""
    close, spread, n = ctx["close"], ctx["spread"], ctx["n"]
    out = []
    for k in range(len(flips) - 1):
        i, i_next = flips[k], flips[k + 1]
        fill_i, fill_next = i + 1, i_next + 1
        if fill_next >= n:
            continue
        sc = spread[fill_i] * POINT
        raw_entry, raw_exit = close[i], close[i_next]
        pnl_buy = (raw_exit - (raw_entry + sc))
        pnl_sell = ((raw_entry - sc) - raw_exit)
        out.append((pnl_buy, pnl_sell, i, trend[i]))
    return out


def tp_sl_outcomes(ctx, triggers_with_dir, tp_atr, sl_atr, maxhold=MAXHOLD_BARS):
    """triggers_with_dir: list of (i, real_dir) - real_dir used only to
    report the real-direction pick later, not to bias the forward scan.
    Both hypothetical outcomes (buy/sell) are resolved in ONE forward
    pass per trigger. Triggers that don't resolve within `maxhold` bars
    (either side) are dropped (rare truncation, not silently biased)."""
    close, high, low, atr, spread, n = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"], ctx["n"]
    out = []
    dropped = 0
    for i, real_dir in triggers_with_dir:
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        entry_buy, entry_sell = raw + sc, raw - sc
        tp_buy, sl_buy = entry_buy + tp_atr * atr[i], entry_buy - sl_atr * atr[i]
        tp_sell, sl_sell = entry_sell - tp_atr * atr[i], entry_sell + sl_atr * atr[i]
        pnl_buy = pnl_sell = None
        for k in range(fill_i, min(fill_i + maxhold, n)):
            if pnl_buy is None:
                hit_tp, hit_sl = high[k] >= tp_buy, low[k] <= sl_buy
                if hit_tp or hit_sl:
                    pnl_buy = (sl_buy - entry_buy) if hit_sl else (tp_buy - entry_buy)
            if pnl_sell is None:
                hit_tp, hit_sl = low[k] <= tp_sell, high[k] >= sl_sell
                if hit_tp or hit_sl:
                    pnl_sell = (entry_sell - sl_sell) if hit_sl else (entry_sell - tp_sell)
            if pnl_buy is not None and pnl_sell is not None:
                break
        if pnl_buy is None or pnl_sell is None:
            dropped += 1
            continue
        out.append((pnl_buy, pnl_sell, i, real_dir))
    return out, dropped


def report_outcome_set(label, outcomes, n_total, seed=0):
    if not outcomes:
        print(f"  {label}: 0 resolved trades, skip")
        return
    pnl_buy = np.array([o[0] for o in outcomes])
    pnl_sell = np.array([o[1] for o in outcomes])
    entry_i = np.array([o[2] for o in outcomes])
    real_dir = np.array([o[3] for o in outcomes])
    real_pnl = np.where(real_dir > 0, pnl_buy, pnl_sell)
    real_net = real_pnl.sum()
    n_tr = len(outcomes)
    wins = (real_pnl > 0).sum()
    pf = real_pnl[real_pnl > 0].sum() / -real_pnl[real_pnl <= 0].sum() if (real_pnl <= 0).any() and real_pnl[real_pnl <= 0].sum() < 0 else np.inf

    rng = np.random.default_rng(seed)
    rdir = rng.integers(0, 2, size=(N_RANDOM_SEEDS, n_tr))
    random_nets = np.where(rdir == 1, pnl_buy, pnl_sell).sum(axis=1)
    pct = 100 * (random_nets < real_net).mean()

    cutoff = int(n_total * 0.7)
    is_mask = entry_i < cutoff
    is_net, oos_net = real_pnl[is_mask].sum(), real_pnl[~is_mask].sum()
    is_n, oos_n = is_mask.sum(), (~is_mask).sum()

    pnl_sorted = np.sort(real_pnl)[::-1]
    top5 = pnl_sorted[:5].sum()
    ex_top5 = real_net - top5

    print(f"  {label}: n={n_tr} net={real_net:.2f} win%={100*wins/n_tr:.1f} pf={pf:.3f} "
          f"| IS(n={is_n})={is_net:.2f} OOS(n={oos_n})={oos_net:.2f} "
          f"| ex-top5={ex_top5:.2f} "
          f"| random-dir percentile={pct:.1f} (null mean={random_nets.mean():.2f} std={random_nets.std():.2f})")


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df, h4, params=E.P)
    n = ctx["n"]
    atr = ctx["atr"]
    tick_vol = df["tick_volume"].values.astype(float)

    base_trades = S.simulate(ctx, params=E.P)
    print("BASELINE (Aurelius v1.46 real signal):", S.stats(base_trades))
    print(f"n_bars={n}\n")

    total_tests = 0

    # ================= SUPERTREND =================
    print("=" * 70)
    print("SUPERTREND")
    for mult in (2.0, 3.0):
        print(f"\n--- mult={mult} (ATR14, same array as Aurelius's own gate) ---")
        trend, line = supertrend(ctx["high"], ctx["low"], ctx["close"], atr, 14, mult)

        # FILTER
        def filt(ctx_, i, is_buy, _tr=trend):
            v = _tr[i]
            return (not np.isnan(v)) and (v == (1.0 if is_buy else -1.0))
        cand = S.simulate(ctx, params=E.P, extra_filter=filt)
        cst = S.stats(cand)
        perm = permutation_test(base_trades, cand, n_draws=800)
        print(f"  FILTER: n={cst.get('n',0)} net={cst.get('net',0):.0f} pf={cst.get('pf',float('nan')):.3f} "
              f"| perm_percentile={perm['percentile'] if perm else None}")
        total_tests += 1

        # FLIP-HOLD
        flips = find_flips(trend)
        fh_out = flip_hold_outcomes(ctx, trend, flips)
        report_outcome_set(f"FLIP-HOLD", fh_out, n)
        total_tests += 1

        # TP/SL
        triggers = [(i, trend[i]) for i in flips]
        for tp_atr in (0.5, 1.0):
            out, dropped = tp_sl_outcomes(ctx, triggers, tp_atr, sl_atr=3.0)
            report_outcome_set(f"TP/SL tp={tp_atr}xATR sl=3.0xATR (dropped={dropped})", out, n)
            total_tests += 1

    # ================= PARABOLIC SAR =================
    print("\n" + "=" * 70)
    print("PARABOLIC SAR")
    for step, maxaf in ((0.02, 0.2), (0.01, 0.15)):
        print(f"\n--- step={step} max={maxaf} ---")
        trend, sar = parabolic_sar(ctx["high"], ctx["low"], ctx["close"], step, maxaf)

        def filt(ctx_, i, is_buy, _tr=trend):
            v = _tr[i]
            return (not np.isnan(v)) and (v == (1.0 if is_buy else -1.0))
        cand = S.simulate(ctx, params=E.P, extra_filter=filt)
        cst = S.stats(cand)
        perm = permutation_test(base_trades, cand, n_draws=800)
        print(f"  FILTER: n={cst.get('n',0)} net={cst.get('net',0):.0f} pf={cst.get('pf',float('nan')):.3f} "
              f"| perm_percentile={perm['percentile'] if perm else None}")
        total_tests += 1

        flips = find_flips(trend)
        fh_out = flip_hold_outcomes(ctx, trend, flips)
        report_outcome_set(f"FLIP-HOLD", fh_out, n)
        total_tests += 1

        triggers = [(i, trend[i]) for i in flips]
        for tp_atr in (0.5, 1.0):
            out, dropped = tp_sl_outcomes(ctx, triggers, tp_atr, sl_atr=3.0)
            report_outcome_set(f"TP/SL tp={tp_atr}xATR sl=3.0xATR (dropped={dropped})", out, n)
            total_tests += 1

    # ================= VOLUME PROFILE POC (tick-volume proxy) =================
    print("\n" + "=" * 70)
    print("VOLUME PROFILE POC (tick-volume proxy - real_volume is 0 for GOLD)")
    TOUCH_TOL_ATR = 0.30
    REJECT_ATR = 0.30
    LOOKBACK_BARS = 12
    for window, refresh in ((576, 12), (1728, 24)):
        print(f"\n--- window={window} bars refresh={refresh} bars ---")
        poc = volume_poc(ctx["high"], ctx["low"], ctx["close"], tick_vol, window, refresh)

        low, high, close = ctx["low"], ctx["high"], ctx["close"]

        def touch_reject_dir(i):
            """Returns +1 (buy: bounced up off POC), -1 (sell: bounced down
            off POC), or None (no touch-and-reject at i)."""
            lvl = poc[i]
            if np.isnan(lvl) or np.isnan(atr[i]) or atr[i] <= 0:
                return None
            tol, rej = TOUCH_TOL_ATR * atr[i], REJECT_ATR * atr[i]
            touched_below = any(low[j] <= lvl + tol for j in range(max(0, i - LOOKBACK_BARS + 1), i + 1))
            touched_above = any(high[j] >= lvl - tol for j in range(max(0, i - LOOKBACK_BARS + 1), i + 1))
            if touched_below and (close[i] - lvl >= rej):
                return 1
            if touched_above and (lvl - close[i] >= rej):
                return -1
            return None

        # FILTER: only take Aurelius's real entries at a real touch-reject of the POC
        def filt(ctx_, i, is_buy, _tr=touch_reject_dir):
            d = _tr(i)
            return d is not None and d == (1 if is_buy else -1)
        cand = S.simulate(ctx, params=E.P, extra_filter=filt)
        cst = S.stats(cand)
        perm = permutation_test(base_trades, cand, n_draws=800)
        print(f"  FILTER: n={cst.get('n',0)} net={cst.get('net',0):.0f} pf={cst.get('pf',float('nan')):.3f} "
              f"| perm_percentile={perm['percentile'] if perm else None}")
        total_tests += 1

        # TP/SL standalone on touch-reject triggers only (no flip-hold construction -
        # POC has no continuous "trend" state to hold through)
        triggers = []
        for i in range(window, n - 1):
            d = touch_reject_dir(i)
            if d is not None:
                triggers.append((i, float(d)))
        for tp_atr in (0.5, 1.0):
            out, dropped = tp_sl_outcomes(ctx, triggers, tp_atr, sl_atr=3.0)
            report_outcome_set(f"TP/SL tp={tp_atr}xATR sl=3.0xATR (dropped={dropped}, n_triggers={len(triggers)})", out, n)
            total_tests += 1

    print(f"\n\nTOTAL INDEPENDENT TESTS RUN THIS BATTERY: {total_tests} "
          f"(best-of-{total_tests} correction applies to whichever single result looks best)")
