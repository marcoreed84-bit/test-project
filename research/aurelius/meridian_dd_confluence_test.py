"""
CORRECTION (found via meridian_ma_variant_test.py): this file's ctx['m150']
is Aurelius's real p150=250/m150=sma default (a 250-period SMA), NOT a
150-period EMA, despite the variable name and this file's own comments
describing it as "150 EMA" throughout. Meridian_EA.mq5 itself is
unaffected (its real MQL5 code genuinely uses InpP150=150 with
MODE_EMA), and the real MT5 Strategy Tester results are real, ground-
truth numbers unaffected by this. Only the specific dollar/percentage
figures reported FROM THIS FILE don't correspond exactly to what's
shipped - re-verified directionally correct (S/R filter + tighter stop
still help) against the TRUE 150 EMA in meridian_ma_variant_test.py,
but treat any exact number from this file with that caveat in mind.
"""
"""
User's ask after the real MT5 Strategy Tester run exposed a 36.78%
equity drawdown (17-month underwater stretch, Jun 2023-Nov 2024) on
Meridian's raw 21/50+150+VWAP construction: can more confluence before
entry cut the losers that drive that drawdown down.

Rather than inventing new filters, this tests the ones Aurelius_EA.mq5
ALREADY has validated (momentum/MACD agreement, pullback-to-the-50
confirmation, volume ratio, S/R distance, MA slope strength, criss-
cross/choppiness count) - all already computed by engine.build_context()
exactly as the real EA does - layered on top of Meridian's existing
150+VWAP-confirmed 21/50 cross entries. Exit stays the corrected design
from m5_stack_variants_fixed_test.py (next RAW reversal or safety stop -
filters gate entry only).

Every variant reports net/PF/win%/walk-forward AND, for the first time
this session on this construction, real drawdown: closed-trade max DD
and bar-by-bar mark-to-market floating max DD, both in $ and as % of
final net - since cutting drawdown, not raising net, is the actual goal
here. Individual filters tested first, then the best-looking ones
combined.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m5_stack_variants_fixed_test import sim_filtered_entries

POINT = E.POINT
N_RANDOM_SEEDS = 300
SAFETY_SL = 3.0


def drawdown_stats(trades, close, spread, n):
    pnls = np.array([t[2] for t in trades])
    closed_equity = np.cumsum(pnls)
    closed_dd = (np.maximum.accumulate(closed_equity) - closed_equity).max()

    eq_prior = np.concatenate(([0.0], closed_equity[:-1]))
    mtm = np.full(n, np.nan)
    last_eq, prev_exit = 0.0, -1
    for idx, (i, exit_bar, pnl, is_buy) in enumerate(trades):
        fill_i = i + 1
        if prev_exit + 1 <= fill_i - 1:
            mtm[prev_exit + 1:fill_i] = last_eq
        entry = close[i] + spread[fill_i] * POINT if is_buy else close[i] - spread[fill_i] * POINT
        seg = close[fill_i:exit_bar + 1]
        floating = (seg - entry) if is_buy else (entry - seg)
        mtm[fill_i:exit_bar + 1] = last_eq + floating
        last_eq = eq_prior[idx] + pnl
        prev_exit = exit_bar
    mtm[prev_exit + 1:] = last_eq
    if trades:
        mtm[:trades[0][0] + 1] = 0.0
    valid = ~np.isnan(mtm)
    mtm_v = mtm[valid]
    float_dd = (np.maximum.accumulate(mtm_v) - mtm_v).max() if len(mtm_v) else 0.0
    final_net = closed_equity[-1] if len(closed_equity) else 0.0
    return closed_dd, float_dd, final_net


def evaluate(label, raw_events, entry_ok, close, high, low, spread, atr, n, time, run_control=False):
    trades = sim_filtered_entries(raw_events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL)
    print(f"\n--- {label} ---")
    if not trades:
        print("  0 trades"); return None
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
    print(f"  n={len(trades)} net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f}")
    print(f"  closed DD={closed_dd:.2f} ({100*closed_dd/net:.1f}% of net)  "
          f"floating DD={float_dd:.2f} ({100*float_dd/net:.1f}% of net)" if net > 0 else
          f"  closed DD={closed_dd:.2f}  floating DD={float_dd:.2f}  (net<=0, no % shown)")

    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    line = "  walk-forward: "
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        if nb == 0:
            line += f"[b{b+1}: 0] "; continue
        netb = pnls[m].sum()
        if netb > 0: pos += 1
        line += f"[b{b+1}: {netb:+.0f}] "
    print(line + f"-> {pos}/5 positive")

    if run_control:
        rng = np.random.default_rng(0)
        random_nets = []
        for s in range(N_RANDOM_SEEDS):
            entry_bars = [t[0] for t in trades]
            rdirs = rng.choice([1.0, -1.0], size=len(entry_bars))
            # random-direction control needs its own raw-event cap structure;
            # approximate here using the same filtered entry bars with random
            # direction, capped by the NEXT entry bar in this same list (a
            # fair like-for-like null, consistent with earlier sessions' method)
            rev = sorted(zip(entry_bars, rdirs), key=lambda e: e[0])
            rtrades_pnl = []
            for kk in range(len(rev)):
                i, d = rev[kk]
                fill_i = i + 1
                if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
                    continue
                cap = min(rev[kk + 1][0] + 1, n) if kk + 1 < len(rev) else n
                raw = close[i]
                sc = spread[fill_i] * POINT
                is_buy = d > 0
                entry = raw + sc if is_buy else raw - sc
                sl = entry - SAFETY_SL * atr[i] if is_buy else entry + SAFETY_SL * atr[i]
                exit_bar, exit_px = None, None
                for k2 in range(fill_i, cap):
                    if is_buy and low[k2] <= sl: exit_bar, exit_px = k2, sl; break
                    if (not is_buy) and high[k2] >= sl: exit_bar, exit_px = k2, sl; break
                if exit_bar is None:
                    exit_bar = cap - 1 if cap > fill_i else fill_i
                    exit_px = close[min(exit_bar, n - 1)]
                pnl = (exit_px - entry) if is_buy else (entry - exit_px)
                rtrades_pnl.append(pnl)
            random_nets.append(sum(rtrades_pnl) if rtrades_pnl else 0.0)
        random_nets = np.array(random_nets)
        pct = 100 * (random_nets < net).mean()
        print(f"  random-direction percentile={pct:.1f} (null mean={random_nets.mean():.2f})")
    return dict(label=label, n=len(trades), net=net, pf=pf, closed_dd=closed_dd, float_dd=float_dd)


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    m21, m50, m150, vwap = ctx["m21"], ctx["m50"], ctx["m150"], ctx["vwap"]
    macd_hist = ctx["macd_hist"]
    pullback_ok_buy, pullback_ok_sell = ctx["pullback_ok_buy"], ctx["pullback_ok_sell"]
    vol_ratio = ctx["vol_ratio"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    slope_buy, slope_sell = ctx["slope_buy"], ctx["slope_sell"]
    crisscross = ctx["crisscross"]
    time = df5["time"].values

    above = m21 > m50
    above_prev = np.concatenate(([False], above[:-1]))
    raw_events = sorted([(i, 1.0) for i in np.where(above & ~above_prev)[0]] +
                         [(i, -1.0) for i in np.where((~above) & above_prev)[0]], key=lambda e: e[0])

    cond_150 = close > m150
    cond_vwap = close > vwap
    base_ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        base_ok[i] = (cond_150[i] and cond_vwap[i]) if d > 0 else ((not cond_150[i]) and (not cond_vwap[i]))

    def masked(extra_pass):
        """extra_pass(i,d)->bool, AND-ed onto base_ok."""
        ok = np.zeros(n, dtype=bool)
        for i, d in raw_events:
            ok[i] = base_ok[i] and extra_pass(i, d)
        return ok

    print("=" * 70)
    results = []
    results.append(evaluate("BASELINE (150+VWAP only, already committed/real-tested)",
                             raw_events, base_ok, close, high, low, spread, atr, n, time, run_control=True))

    f_momentum = masked(lambda i, d: (macd_hist[i] * d) > 0)
    results.append(evaluate("+MOMENTUM (MACD hist agrees with direction)",
                             raw_events, f_momentum, close, high, low, spread, atr, n, time))

    f_pullback = masked(lambda i, d: pullback_ok_buy[i] if d > 0 else pullback_ok_sell[i])
    results.append(evaluate("+PULLBACK (recent touch of the 50, Aurelius default window)",
                             raw_events, f_pullback, close, high, low, spread, atr, n, time))

    MIN_VOL_RATIO = 1.30
    f_volume = masked(lambda i, d: not (vol_ratio[i] >= 0.0 and vol_ratio[i] < MIN_VOL_RATIO))
    results.append(evaluate(f"+VOLUME (ratio >= {MIN_VOL_RATIO}, Aurelius default)",
                             raw_events, f_volume, close, high, low, spread, atr, n, time))

    MIN_SR_ATR = 0.50
    f_sr = masked(lambda i, d: not ((sr_dist_buy[i] if d > 0 else sr_dist_sell[i]) >= 0.0 and
                                     (sr_dist_buy[i] if d > 0 else sr_dist_sell[i]) < MIN_SR_ATR))
    results.append(evaluate(f"+S/R DISTANCE (>= {MIN_SR_ATR}xATR from the nearest level, Aurelius default)",
                             raw_events, f_sr, close, high, low, spread, atr, n, time))

    MIN_SLOPE_ATR = 0.50
    f_slope = masked(lambda i, d: (slope_buy[i] if d > 0 else slope_sell[i]) >= MIN_SLOPE_ATR)
    results.append(evaluate(f"+SLOPE (50 EMA slope >= {MIN_SLOPE_ATR}xATR/20bars, Aurelius default)",
                             raw_events, f_slope, close, high, low, spread, atr, n, time))

    MAX_CROSSES = 1
    f_crisscross = masked(lambda i, d: crisscross[i] <= MAX_CROSSES)
    results.append(evaluate(f"+CRISSCROSS (<= {MAX_CROSSES} 21x50 flips in the last 10 bars, Aurelius default)",
                             raw_events, f_crisscross, close, high, low, spread, atr, n, time))

    print("\n" + "=" * 70)
    print("SUMMARY (sorted by floating-DD % of net, best first):")
    valid_results = [r for r in results if r and r["net"] > 0]
    valid_results.sort(key=lambda r: r["float_dd"] / r["net"])
    for r in valid_results:
        print(f"  {r['label']:<65} net={r['net']:8.2f} pf={r['pf']:.3f} "
              f"floatDD%={100*r['float_dd']/r['net']:5.1f}  n={r['n']}")
