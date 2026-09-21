"""
Follow-up to bos_confirm_test.py, which found BOS-confirmed structure
entries (k=5 fractal window) work but only match, not beat, the plain
21/50 cross - largely because both were tested with the SAME exit
(hold until the opposite signal fires). Holding to the opposite signal
means giving back a real chunk of every leg: the trend has to fully
reverse and get re-confirmed before you're out, well after the actual
peak.

This keeps the k=5 BOS entries fixed (the best entry config from the
prior sweep) and replaces the exit with a trailing stop off the
running peak (longs) / trough (shorts) since entry - the standard
"chandelier exit" used specifically to get out close to a leg's high
point without needing to predict it: as long as price keeps making new
highs the stop trails up and you stay in; the first real pullback of
size trail_atr*ATR takes you out, which is by definition close to
wherever the peak actually was. ATR is fixed at the entry bar's value
(same convention as every other exit in this project) so the trail
distance doesn't drift as a trade runs long.

Sweeps trail_atr (how far behind the peak the stop trails) since that
is now the only free parameter - this IS the "get out at the peak"
parameter sweep the user asked for, replacing the old safety_sl grid
from the cross/BOS-hold tests (that grid was about the SAME exit type
as here, so keeping it would be redundant - the trail distance itself
already spans "tight" to "wide").

Same rigor: real M5 data, real spread, correct single-position
sequencing (a trade in progress blocks any new entry event, same as
every other construction today), random-direction control from the
start, walk-forward blocks alongside the aggregate. Directly comparable
to bos_confirm_test.py's k=5 numbers since the entries are identical -
only the exit changed.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from bos_confirm_test import bos_confirmed_events

POINT = E.POINT
N_RANDOM_SEEDS = 300
MAX_HOLD = 5000  # safety cap (~17 trading days on M5) - trailing normally exits well before this


def sim_trailing_peak_exit(events, close, high, low, spread, atr, n, trail_atr, max_hold=MAX_HOLD):
    """Entries fixed by `events` (already alternating buy/sell). Exit is a
    trailing stop off the running peak (long) / trough (short) since
    entry, distance = trail_atr * ATR-at-entry. No opposite-signal exit
    at all - purely the trail. Correct single-position sequencing: any
    entry event firing while a trade is still open is skipped.

    IMPORTANT (found via the 0.5xATR cell's suspiciously 1-bar median
    hold + 100th-percentile score - the same shape as the earlier
    stochastic lookahead bug): a bar's own high and low have unknown
    intrabar order, so the stop level checked against bar k's low/high
    must be based on the peak/trough as of the END of bar k-1 only -
    NEVER updated with bar k's own high/low before that same bar's
    check. Updating-then-checking-same-bar silently assumes the
    extreme-setting tick happened before the stop-breaching tick,
    which is exactly the kind of unearned information the earlier bug
    smuggled in. Peak/trough is updated with bar k's high/low only
    AFTER bar k's check, so it only affects bar k+1 onward."""
    trades = []
    last_exit = -1
    skipped = 0
    for i, d in events:
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
        trail_dist = trail_atr * atr[i]
        exit_bar, exit_px = None, None
        if is_buy:
            peak = entry
            for k in range(fill_i, min(fill_i + max_hold, n)):
                stop = peak - trail_dist
                if low[k] <= stop:
                    exit_bar, exit_px = k, stop
                    break
                peak = max(peak, high[k])
        else:
            trough = entry
            for k in range(fill_i, min(fill_i + max_hold, n)):
                stop = trough + trail_dist
                if high[k] >= stop:
                    exit_bar, exit_px = k, stop
                    break
                trough = min(trough, low[k])
        if exit_bar is None:
            exit_bar = min(fill_i + max_hold, n) - 1
            exit_px = close[exit_bar]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
        last_exit = exit_bar
    return trades, skipped


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    time = df5["time"].values

    events = bos_confirmed_events(close, high, low, k=5)
    print(f"n_bars={n} (~{n/288:.0f} trading days), {len(events)} BOS-confirmed (k=5) entries "
          f"-> {len(events)/(n/288):.3f}/day\n")

    print("=" * 70)
    print("trailing-stop-from-peak exit sweep (BOS k=5 entries fixed)")
    overall_best = None
    for trail_atr in (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
        trades, skipped = sim_trailing_peak_exit(events, close, high, low, spread, atr, n, trail_atr)
        if not trades:
            print(f"  trail={trail_atr}xATR: 0 trades"); continue
        pnls = np.array([t[2] for t in trades])
        entries = np.array([t[0] for t in trades])
        holds = np.array([t[1] - t[0] for t in trades])
        gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
        pf = gw / gl if gl > 0 else float("inf")
        cutoff = int(n * 0.7)
        is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
        print(f"  trail={trail_atr}xATR (skipped {skipped} overlaps): n={len(trades)} "
              f"net={pnls.sum():.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
              f"IS={is_net:.2f} OOS={oos_net:.2f} median_hold={np.median(holds):.0f}bars")
        if overall_best is None or pnls.sum() > overall_best[0]:
            overall_best = (pnls.sum(), trail_atr, trades)

    print("\n" + "=" * 70)
    if overall_best is None:
        print("no trades resolved anywhere in the grid")
        sys.exit(0)

    best_net, best_trail, best_trades = overall_best
    print(f"best cell: trail={best_trail}xATR net={best_net:.2f} n={len(best_trades)}")

    print(f"\nrandom-direction control (best cell, real net={best_net:.2f}):")
    rng = np.random.default_rng(0)
    random_nets = []
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(events))
        rev = [(i, d) for (i, _), d in zip(events, rdirs)]
        rev.sort(key=lambda e: e[0])
        trades_r, _ = sim_trailing_peak_exit(rev, close, high, low, spread, atr, n, best_trail)
        random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < best_net).mean()
    print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")

    pnls = np.array([t[2] for t in best_trades])
    entries = np.array([t[0] for t in best_trades])
    edges = np.linspace(0, n, 6).astype(int)
    print(f"\n5-block walk-forward (trail={best_trail}xATR):")
    pos = 0
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        if nb == 0:
            print(f"  block {b+1}: 0 trades"); continue
        netb = pnls[m].sum()
        if netb > 0: pos += 1
        t0 = pd.to_datetime(time[lo]).date(); t1 = pd.to_datetime(time[min(hi, n-1)]).date()
        print(f"  block {b+1} [{t0}->{t1}]: n={nb} net={netb:.2f} win%={100*(pnls[m]>0).mean():.1f}")
    print(f"  -> positive in {pos}/5 blocks")

    # direct comparison line vs the hold-to-opposite-cross exit from bos_confirm_test.py
    print(f"\nfor reference, bos_confirm_test.py k=5 hold-to-opposite-BOS exit best cell was "
          f"net=1446.78 (safety_sl=3.0xATR, 78.3th percentile vs random, 3/5 blocks positive)")
