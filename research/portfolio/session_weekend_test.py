"""
Opus's items #4 (session attribution) and #5 (weekend exposure), combined
into one review pass over the real MT5 trade data already assembled by
combine_all7_real.py (2026-01-01 onward, 7 systems) - no new signal, just
tagging existing REAL trades by entry session / day-of-week and reporting
what's there. Same server=ET+7h convention as news_blackout_test.py.

SESSION BUCKETS (ET, standard coarse convention - Asia/London overlap
folded into whichever opens first): Asia 19:00-03:00 ET, London 03:00-08:00
ET, NY 08:00-17:00 ET (includes the London/NY overlap, deliberately not
split further - splitting the overlap out needs a 4th bucket and this
session's per-bucket trade counts are already thin at 7-system-combined
~1300 trades over 9 months).

WEEKEND GAP CHECK: reuses RoundingBottom's own real H4 construction
(rounding_bottom_random_baseline_test.py, v1.03 rim-anchored stop) since
that's the system with an actual documented gap-risk history (Backtest 1's
45% equity DD, traced partly to weekend gaps against long-held positions) -
flags every real trade whose [entry, exit) interval spans a Friday-close-
to-Monday-open weekend and compares its outcome to non-weekend-spanning
trades.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/portfolio")
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import combine_all7_real as C
import engine as E
from h4_touch_reaction_test import sma_atr, ATR_PERIOD
from rounding_cup_handle_test import find_rounding
from hs_next_round_test import walk
import rounding_bottom_random_baseline_test as RB

SERVER_TZ_OFFSET_HOURS = 7


def session_of(et_hour):
    if et_hour >= 19 or et_hour < 3:
        return "Asia"
    if 3 <= et_hour < 8:
        return "London"
    return "NY"


def tag_and_report(all_systems):
    flat = []
    for name, trades in all_systems:
        for t in trades:
            flat.append(t)
    df = pd.DataFrame(flat)
    et = pd.to_datetime(df["entry_time"]) - pd.Timedelta(hours=SERVER_TZ_OFFSET_HOURS)
    df["session"] = et.dt.hour.map(session_of)
    df["dow"] = et.dt.day_name()

    print("=" * 90)
    print("SESSION BREAKDOWN (all 7 real systems combined, entry time)")
    print("=" * 90)
    for s in ("Asia", "London", "NY"):
        sub = df[df["session"] == s]
        if len(sub) < 5:
            continue
        pnl = sub["pnl"].values
        gw = pnl[pnl > 0].sum(); gl = -pnl[pnl <= 0].sum()
        pf = gw / gl if gl > 0 else float("inf")
        print(f"  {s:8s}: n={len(sub):4d}  win%={100*(pnl>0).mean():.1f}  net={pnl.sum():9.2f}  pf={pf:.3f}")

    print("\n" + "=" * 90)
    print("DAY-OF-WEEK BREAKDOWN (entry time)")
    print("=" * 90)
    for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
        sub = df[df["dow"] == d]
        if len(sub) < 5:
            continue
        pnl = sub["pnl"].values
        gw = pnl[pnl > 0].sum(); gl = -pnl[pnl <= 0].sum()
        pf = gw / gl if gl > 0 else float("inf")
        print(f"  {d:10s}: n={len(sub):4d}  win%={100*(pnl>0).mean():.1f}  net={pnl.sum():9.2f}  pf={pf:.3f}")


def weekend_gap_check():
    print("\n" + "=" * 90)
    print("WEEKEND GAP CHECK: RoundingBottom_EA v1.03 real construction (H4)")
    print("=" * 90)
    h4 = E.load_h4()
    o = h4["open"].values; h = h4["high"].values; l = h4["low"].values; c = h4["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    times = h4["time"].values

    cands = find_rounding(c, atr, n, RB.WINDOW, top=False)
    trades = RB.build_real_trades(cands, h, l, c, atr, n)
    trades_sorted = sorted(trades, key=lambda b: b["brk_q"])
    real, spans_weekend, last_exit = [], [], -1
    for b in trades_sorted:
        if b["brk_q"] < last_exit:
            continue
        outcome, exit_bar = walk(h, l, False, b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        from hs_next_round_test import pnl_of
        pnl = pnl_of(outcome, b["brk_price"], b["stop"], b["target"], c, exit_bar, False)
        real.append(dict(brk_q=b["brk_q"], exit_bar=exit_bar, pnl=pnl))
        last_exit = exit_bar
        entry_t = pd.Timestamp(times[b["brk_q"]])
        exit_t = pd.Timestamp(times[min(exit_bar, n - 1)])
        span = pd.date_range(entry_t, exit_t, freq="D") if exit_t > entry_t else pd.DatetimeIndex([entry_t])
        spans_weekend.append(any(d.weekday() == 5 for d in span))  # crosses a Saturday

    n_weekend = sum(spans_weekend)
    print(f"  n={len(real)} real trades, {n_weekend} ({100*n_weekend/max(1,len(real)):.1f}%) span at least one weekend")
    if n_weekend >= 3:
        wk = np.array([r["pnl"] for r, sw in zip(real, spans_weekend) if sw])
        nwk = np.array([r["pnl"] for r, sw in zip(real, spans_weekend) if not sw])
        print(f"  weekend-spanning:  n={len(wk)}  win%={100*(wk>0).mean():.1f}  mean_pnl={wk.mean():.2f}")
        print(f"  non-weekend:       n={len(nwk)} win%={100*(nwk>0).mean():.1f}  mean_pnl={nwk.mean():.2f}")


if __name__ == "__main__":
    all_systems, _ = C.build_portfolio()
    tag_and_report(all_systems)
    weekend_gap_check()
