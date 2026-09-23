"""
Validate the simulator's EXIT engine in isolation, per management mode, by
replaying real entries (exact time, requested price, SL, side from the real
order tickets) forward on the real M1 bars and comparing the simulated legs
with the real report's legs.

The real T1 EA's own report is the only real data that is managed on every
tick (its partial exits land at uniform seconds, median 1.005R), so it is the
ground truth for manage_mode="tick".  This reconstruction's own reports are
managed on the first tick of each bar only, so they are the ground truth for
manage_mode="bar_open".  Each engine should match its own kind of report
clearly better than it matches the other kind.

The rest of the entry bar after a mid-bar fill is not modelled (its tick order
is unknowable from OHLC); management starts at the next bar's open.
"""
import sys
import datetime as dt
from dataclasses import replace

import numpy as np

sys.path.insert(0, "/home/user/test-project/research/msg")
from report import load_deals, round_trips, entry_orders       # noqa: E402
from sim import load_bars, Params, intrabar_tick, lot_round, LOT_STEP, PT  # noqa: E402

UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
T1 = UP + "2160b5b6-20260922_-_ReportTester-382043238_-_MSG_-_Backtest_1_Original_1Min.xlsx"
BT1 = UP + "28855db1-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_1.xlsx"


def replay(bars, trade, order, p):
    t_arr = bars["time"].values.astype("datetime64[s]").astype(np.int64)
    o = bars["open"].values + p.bid_off
    h = bars["high"].values + p.bid_off
    l = bars["low"].values + p.bid_off
    c = bars["close"].values + p.bid_off
    sp = bars["spread"].values * PT - p.bid_off + p.ask_extra
    d = 1 if order["side"] == "buy" else -1
    px, sl = order["px"], order["sl"]
    risk = (px - sl) * d
    pos = dict(dir=d, px=px, sl=sl, risk=risk, tp1=px + d * p.tp1 * risk, tp2=px + d * p.tp2 * risk,
               tp3=px + d * p.tp3 * risk, units=3, tp1done=False, tp2done=False, legs=[])
    t0 = int(trade["entry_time"].replace(tzinfo=dt.timezone.utc).timestamp())
    k = int(np.searchsorted(t_arr, t0, side="right"))       # next bar after the fill

    def close_leg(pr, u, r):
        pos["legs"].append((pr, u, r))
        pos["units"] -= u

    while pos["units"] > 0 and k < len(t_arr):
        if t_arr[k] - t0 >= p.max_hold_h * 3600:
            close_leg(o[k] if d > 0 else o[k] + sp[k], pos["units"], "maxhold")
            break
        price = o[k] if d > 0 else o[k] + sp[k]
        if (price - pos["sl"]) * d <= 0:                       # gapped through the stop
            close_leg(price, pos["units"], "sl"); break
        if (price - pos["tp3"]) * d >= 0:
            close_leg(price, pos["units"], "tp"); break
        if not pos["tp1done"] and (price - pos["tp1"]) * d >= 0:
            close_leg(price, 1, "tp1"); pos["tp1done"] = True; pos["sl"] = px
        if pos["tp1done"] and not pos["tp2done"] and (price - pos["tp2"]) * d >= 0:
            close_leg(price, 1, "tp2"); pos["tp2done"] = True
        if pos["tp2done"]:
            pos["sl"] = px + d * p.trail * risk
        if p.manage_mode == "tick":
            if intrabar_tick(pos, o[k], h[k], l[k], c[k], sp[k], p, close_leg):
                break
        else:
            lo, hi = (l[k], h[k]) if d > 0 else (l[k] + sp[k], h[k] + sp[k])
            adverse, fav = (lo, hi) if d > 0 else (hi, lo)
            if (adverse - pos["sl"]) * d <= 0:
                close_leg(pos["sl"], pos["units"], "sl"); break
            if (fav - pos["tp3"]) * d >= 0:
                close_leg(pos["tp3"], pos["units"], "tp"); break
        k += 1
    pnl = sum((pr - trade["entry"]) * d * u for pr, u, _ in pos["legs"])   # USD at 0.01/unit
    return pos["legs"], pnl


def compare(bars, path, p, label):
    trips = round_trips(load_deals(path))
    orders = {x["time"]: x for x in entry_orders(path)}
    same_legs = same_out = 0
    rs, ss = [], []
    for t in trips:
        legs, pnl = replay(bars, t, orders[t["entry_time"]], p)
        if len(legs) == t["nlegs"]:
            same_legs += 1
        if abs(pnl - t["pnl_usd"]) <= max(2.0, 0.1 * abs(t["pnl_usd"])):
            same_out += 1
        rs.append(t["pnl_usd"]); ss.append(pnl)
    n = len(trips)
    print(f"{label:44s} n={n}  same #legs {same_legs:3d} ({100*same_legs/n:.0f}%)  same P/L {same_out:3d} "
          f"({100*same_out/n:.0f}%)  real sum ${sum(rs):8.2f}  replay sum ${sum(ss):8.2f}  corr {np.corrcoef(rs, ss)[0,1]:.3f}")


if __name__ == "__main__":
    bars = load_bars()
    gold = dict(bid_off=-0.12, ask_extra=0.16)
    for mode in ("bar_open", "tick"):
        p = Params(manage_mode=mode, **gold)
        compare(bars, T1, p, f"REAL T1 EA (tick-managed)  vs engine={mode}")
        compare(bars, BT1, p, f"recon Backtest_1 (bar-open) vs engine={mode}")
