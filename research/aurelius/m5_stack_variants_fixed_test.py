"""
BUG FOUND AND FIXED in m5_stack_variants_test.py's winning "21/50 +150+
VWAP" result (net=3114.71, reported to the user as the best-of-session
candidate). apply_filter() removed raw 21/50-cross events that didn't
have 150/VWAP confirmation, then passed the resulting SUBSET straight
to sim_cross_to_cross(), which exits every trade at "the next event in
the list" WITHOUT checking that event's direction. Since filtering can
remove the genuine opposite-direction reversal while keeping a later
same-direction re-confirmation, 52.6% of the filtered event pairs
turned out to be consecutive SAME-direction events - meaning over half
of the reported "exits" were computed against a same-direction
re-entry signal, not an actual trend reversal. That's not a valid exit
condition in any real trading system and inflates/distorts the number
in an unknown direction.

Correct design (matches how this would actually run live): the 150/
VWAP filter gates ENTRY only. Once in a trade, the exit is the next
RAW 21/50 cross in the opposite direction - regardless of whether that
specific reversal happens to also satisfy the 150/VWAP filter - because
requiring re-confirmation to exit would mean holding through an
already-signaled reversal waiting for extra confirmation that may never
come, which is a different (and untested) design choice, not what was
originally described or reported.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E

POINT = E.POINT
N_RANDOM_SEEDS = 300
SAFETY_SL = 3.0


def sim_filtered_entries(raw_events, entry_ok_mask, close, high, low, spread, atr, n, safety_sl_atr):
    """raw_events: the FULL alternating 21/50-cross event list (guarantees
    correct reversal-based exits). entry_ok_mask[i] gates whether a trade
    is actually OPENED at that raw event - if not, it's simply skipped as
    an entry, but the raw event still exists as the exit boundary for
    whatever trade (if any) preceded it. Single-position sequencing is
    automatic here since raw_events already strictly alternate direction
    and skipped entries don't create positions to overlap."""
    trades = []
    for k in range(len(raw_events) - 1):
        i, d = raw_events[k]
        if not entry_ok_mask[i]:
            continue
        i_next, _ = raw_events[k + 1]
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        is_buy = d > 0
        entry = raw + sc if is_buy else raw - sc
        sl = entry - safety_sl_atr * atr[i] if is_buy else entry + safety_sl_atr * atr[i]
        exit_bar, exit_px = None, None
        cap = min(i_next + 1, n)
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
    return trades


def report(label, trades, n, time):
    print(f"\n--- {label} ---")
    if not trades:
        print("  0 trades"); return
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    cutoff = int(n * 0.7)
    is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
    print(f"  n={len(trades)} net={pnls.sum():.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
          f"IS={is_net:.2f} OOS={oos_net:.2f}")

    rng = np.random.default_rng(0)
    random_nets = []
    dirs = [1.0 if t[3] else -1.0 for t in trades]
    entry_bars = [t[0] for t in trades]
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(entry_bars))
        rev = sorted(zip(entry_bars, rdirs), key=lambda e: e[0])
        # re-simulate with random directions on the SAME entry bars, same
        # exit-boundary logic (next entry bar in this trade list, or the
        # existing safety stop) - the fairest like-for-like null
        rtrades = []
        for kk in range(len(rev)):
            i, d = rev[kk]
            fill_i = i + 1
            if fill_i >= n or np.isnan(atr_g[i]) or atr_g[i] <= 0:
                continue
            cap = rev[kk + 1][0] + 1 if kk + 1 < len(rev) else n
            cap = min(cap, n)
            raw = close_g[i]
            sc = spread_g[fill_i] * POINT
            is_buy = d > 0
            entry = raw + sc if is_buy else raw - sc
            sl = entry - SAFETY_SL * atr_g[i] if is_buy else entry + SAFETY_SL * atr_g[i]
            exit_bar, exit_px = None, None
            for k2 in range(fill_i, cap):
                if is_buy and low_g[k2] <= sl:
                    exit_bar, exit_px = k2, sl; break
                if (not is_buy) and high_g[k2] >= sl:
                    exit_bar, exit_px = k2, sl; break
            if exit_bar is None:
                exit_bar = cap - 1 if cap > fill_i else fill_i
                exit_px = close_g[min(exit_bar, n - 1)]
            pnl = (exit_px - entry) if is_buy else (entry - exit_px)
            rtrades.append(pnl)
        random_nets.append(sum(rtrades) if rtrades else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < pnls.sum()).mean()
    print(f"  random-direction percentile={pct:.1f} (null mean={random_nets.mean():.2f})")

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


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close_g, high_g, low_g, atr_g, spread_g = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    close, high, low, atr, spread = close_g, high_g, low_g, atr_g, spread_g
    m21, m50, m150, vwap = ctx["m21"], ctx["m50"], ctx["m150"], ctx["vwap"]
    time = df5["time"].values

    above = m21 > m50
    above_prev = np.concatenate(([False], above[:-1]))
    raw_events = sorted([(i, 1.0) for i in np.where(above & ~above_prev)[0]] +
                         [(i, -1.0) for i in np.where((~above) & above_prev)[0]], key=lambda e: e[0])

    cond_150 = close > m150
    cond_vwap = close > vwap

    def entry_mask(conds):
        ok = np.zeros(n, dtype=bool)
        for i, d in raw_events:
            agree = all((c[i] if d > 0 else (not c[i])) for c in conds)
            ok[i] = agree
        return ok

    print("=" * 70)
    print(f"raw 21/50 cross events: {len(raw_events)} (baseline, no filter - matches "
          f"the already-committed, correctly-simulated ema21_50_cross_hold_test.py)")

    trades_base = sim_filtered_entries(raw_events, np.ones(n, dtype=bool),
                                        close, high, low, spread, atr, n, SAFETY_SL)
    report("baseline 21/50 (sanity check vs original committed result)", trades_base, n, time)

    m150_only = entry_mask([cond_150])
    trades_150 = sim_filtered_entries(raw_events, m150_only, close, high, low, spread, atr, n, SAFETY_SL)
    report("21/50 entries +150-confirmed (exit = next RAW reversal, corrected)", trades_150, n, time)

    both = entry_mask([cond_150, cond_vwap])
    trades_both = sim_filtered_entries(raw_events, both, close, high, low, spread, atr, n, SAFETY_SL)
    report("21/50 entries +150+VWAP-confirmed (exit = next RAW reversal, corrected)", trades_both, n, time)
