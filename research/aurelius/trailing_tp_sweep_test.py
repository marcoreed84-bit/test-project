"""
User's follow-up (2026-09-25): "or the trailing tp" - instead of a flat $
bracket (dollar_exit_sweep_test.py, ten_dollar_exit_compare_test.py:
smaller targets $5-7 were flat/negative, edge only appears >= $8 and grows
with distance), trail a stop behind the trade once it's favorably extended
by some trigger distance, giving back only a fixed amount from the peak -
keeps the "lock something in" behavior without capping the upside the way
a flat TP does. Initial hard stop is fixed at $10 (today's baseline) until
the trigger is reached.

Same real entries (Aurelius: sim.py EA-faithful simulator; Meridian:
msim.py EA-faithful simulator), real spread already in entry_px, same
single-position sequencing (skip an entry that starts before the prior
trade's exit).
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "../meridian")
import numpy as np
import engine as E
from sim import simulate as aurelius_simulate
import msim

np.random.seed(42)

INIT_SL = 10.0
MAXHOLD = 2880
GRID = [(trig, give) for trig in (5.0, 8.0, 10.0, 15.0) for give in (3.0, 5.0, 8.0)]


def apply_trailing(entries, high, low, n, init_sl, trigger, giveback, maxhold):
    trades, last_exit, open_n = [], -1, 0
    for entry_i, d, entry_px in entries:
        if entry_i < last_exit:
            continue
        sl = entry_px - init_sl if d > 0 else entry_px + init_sl
        peak = entry_px
        trailing = False
        eb, pnl = None, None
        for k in range(entry_i, min(entry_i + maxhold, n)):
            hi, lo = high[k], low[k]
            fav = (hi - entry_px) if d > 0 else (entry_px - lo)
            if d > 0:
                if lo <= sl:
                    eb, pnl = k, sl - entry_px; break
                peak = max(peak, hi)
            else:
                if hi >= sl:
                    eb, pnl = k, entry_px - sl; break
                peak = min(peak, lo)
            prof_peak = (peak - entry_px) if d > 0 else (entry_px - peak)
            if prof_peak >= trigger:
                trailing = True
                new_sl = peak - giveback if d > 0 else peak + giveback
                if d > 0:
                    sl = max(sl, new_sl)
                else:
                    sl = min(sl, new_sl)
        if eb is None:
            open_n += 1
            continue
        trades.append((entry_i, eb, pnl))
        last_exit = eb
    return trades, open_n


def row(trades, trig, give):
    if len(trades) < 8:
        return f"    trig=${trig:>4.0f} give=${give:>3.0f}: only {len(trades)} resolved - too few"
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    win_pct = 100 * (pnls > 0).mean()
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    cutoff = entries.min() + (entries.max() - entries.min()) * 0.7
    is_p = pnls[entries < cutoff]; oos_p = pnls[entries >= cutoff]
    is_net = is_p.sum() if len(is_p) >= 8 else float("nan")
    oos_net = oos_p.sum() if len(oos_p) >= 8 else float("nan")
    return (f"    trig=${trig:>4.0f} give=${give:>3.0f}: n={len(trades):>4} win%={win_pct:5.1f}  "
            f"pf={pf:.3f}  net=${pnls.sum():7.0f}  IS net=${is_net:7.0f}  OOS net=${oos_net:7.0f}")


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    a_trades_real = aurelius_simulate(ctx, params=E.P)
    a_entries = [(t["entry_i"], t["dir"], t["entry_px"]) for t in a_trades_real]
    a_n = ctx["n"]

    mctx = msim.build_ctx()
    win_start = mctx["t64"].min(); win_end = mctx["t64"].max()
    m_trades_real, _ = msim.simulate(mctx, start=win_start, end=win_end)
    m_entries = [(t["entry_i"], t["dir"], t["entry"]) for t in m_trades_real]
    m_n = len(mctx["c"])

    print("=" * 95)
    print(f"AURELIUS real entries, trailing stop (init SL=${INIT_SL:.0f}, trigger/giveback grid)")
    print(f"baseline for comparison: flat $10 bracket was win%=53.9 pf=1.171 net=$540")
    print("=" * 95)
    for trig, give in GRID:
        trades, open_n = apply_trailing(a_entries, ctx["high"], ctx["low"], a_n, INIT_SL, trig, give, MAXHOLD)
        print(row(trades, trig, give))

    print()
    print("=" * 95)
    print(f"MERIDIAN real entries, trailing stop (init SL=${INIT_SL:.0f}, trigger/giveback grid)")
    print(f"baseline for comparison: flat $10 bracket was win%=52.4 pf=1.100 net=$740")
    print("=" * 95)
    for trig, give in GRID:
        trades, open_n = apply_trailing(m_entries, mctx["h"], mctx["l"], m_n, INIT_SL, trig, give, MAXHOLD)
        print(row(trades, trig, give))
