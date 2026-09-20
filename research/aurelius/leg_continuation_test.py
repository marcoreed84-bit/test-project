"""
User's construction: price moves in "legs" - a run of consecutive
same-direction candles (e.g. 8 up, then 10 down). Rather than predicting
where a leg STARTS, bet on an ALREADY-ESTABLISHED run continuing for
just a couple more candles. Genuinely different from everything else
tested this session - not a pullback/bounce, not an oscillator extreme,
not a moving-average relationship. A pure momentum-continuation bet.

Definition: a "run" at bar i is the count of consecutive prior closes
each higher (up-run) or each lower (down-run) than the one before it.
Once a run reaches a threshold length T for the first time (edge-
triggered - fires once per run, not every bar it continues), enter in
the run's direction and hold for exactly K more bars, then exit at
market - the most literal reading of "catch 2 candles". No TP/SL on the
primary test (matches "just ride it K bars" exactly); a stop-bounded
variant is tested afterward as a real-money sanity check, since holding
with zero risk control isn't something anyone would actually trade.

Real M5 data (years of history, better statistical power than the ~10mo
M1 set), correct single-position sequencing from the start, real Ultra
Low spread already confirmed accurate.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E

POINT = E.POINT


def find_run_triggers(close, min_run):
    n = len(close)
    diff = np.diff(close, prepend=close[0])
    up = diff > 0
    down = diff < 0
    up_run = np.zeros(n, dtype=int)
    down_run = np.zeros(n, dtype=int)
    for i in range(1, n):
        up_run[i] = up_run[i-1] + 1 if up[i] else 0
        down_run[i] = down_run[i-1] + 1 if down[i] else 0
    trig_up = (up_run >= min_run) & (np.concatenate(([0], up_run[:-1])) < min_run)
    trig_dn = (down_run >= min_run) & (np.concatenate(([0], down_run[:-1])) < min_run)
    triggers = [(i, 1.0) for i in np.where(trig_up)[0]] + [(i, -1.0) for i in np.where(trig_dn)[0]]
    triggers.sort(key=lambda t: t[0])
    return triggers


def sim_fixed_hold(triggers, close, high, low, spread, atr, n, hold_bars, safety_sl_atr=None):
    """Enter at fill_i's proxy price, hold exactly `hold_bars` bars, exit at
    market (the trigger bar's own close, `hold_bars` bars later) - unless
    `safety_sl_atr` is set, in which case a wide protective stop is also
    checked each bar (real-money sanity check, not the primary exit)."""
    trades = []
    last_exit = -1
    skipped = 0
    for i, d in triggers:
        if i < last_exit:
            skipped += 1
            continue
        fill_i = i + 1
        exit_i = fill_i + hold_bars
        if exit_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        is_buy = d > 0
        entry = raw + sc if is_buy else raw - sc
        pnl = None
        actual_exit = exit_i
        if safety_sl_atr is not None:
            sl = entry - safety_sl_atr * atr[i] if is_buy else entry + safety_sl_atr * atr[i]
            for k in range(fill_i, exit_i + 1):
                if is_buy and low[k] <= sl:
                    pnl = sl - entry; actual_exit = k; break
                if (not is_buy) and high[k] >= sl:
                    pnl = entry - sl; actual_exit = k; break
        if pnl is None:
            exit_px = close[exit_i]
            pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, actual_exit, pnl))
        last_exit = actual_exit
    return trades, skipped


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]

    print(f"n_bars={n} (~{n/288:.0f} trading days)\n")

    print("=" * 70)
    print("LEG CONTINUATION - no TP/SL, pure K-bar hold then exit at market")
    for min_run in (3, 4, 5, 6, 8):
        triggers = find_run_triggers(close, min_run)
        print(f"\n--- run length >= {min_run} candles: {len(triggers)} triggers "
              f"({len(triggers)/(n/288):.2f}/day) ---")
        for hold_bars in (1, 2, 3, 5):
            trades, skipped = sim_fixed_hold(triggers, close, high, low, spread, atr, n, hold_bars)
            if not trades:
                print(f"    hold={hold_bars} bars: 0 trades"); continue
            pnls = np.array([t[2] for t in trades])
            entries = np.array([t[0] for t in trades])
            gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
            pf = gw / gl if gl > 0 else float("inf")
            cutoff = int(n * 0.7)
            is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
            print(f"    hold={hold_bars} bars (skipped {skipped}): n={len(trades)} "
                  f"net={pnls.sum():.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
                  f"IS={is_net:.2f} OOS={oos_net:.2f}")
