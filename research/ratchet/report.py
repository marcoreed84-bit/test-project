"""
Parse a real MT5 Strategy Tester .xlsx report into round-trip trades.

Same methodology MSG_Trader_EA.mq5's version history uses (research/msg/
report.py): walk the Deals table in order, open a round-trip on an 'in' deal,
close it once cumulative 'out' volume equals the 'in' volume. Nothing assumes
1 deal = 1 trade - a scale-out would show up as nlegs > 1 (neither Ratchet nor
Meridian scales out, and the parse proves it rather than assuming it: every
round-trip in all four 2026-09-23 reports has exactly one out-leg).

Profit is in the ACCOUNT currency (ZAR on account 1301959345). Each round-trip
also carries a currency-neutral P/L in USD (price move x volume x contract
size 100), which is what a Python simulator produces and what real-vs-sim
comparisons should use, plus the implied ZAR/USD rate of that trade (needed to
mark open positions to market in ZAR for the equity-drawdown reconstruction).

reconcile() proves the parse is exact: sum(profit+commission+swap) over all
round-trips must equal the report's own "Total Net Profit" to the cent.

Shared by research/meridian/ (imported via sys.path) so both EAs' real reports
go through exactly the same parser.
"""
import datetime as dt
import re
import warnings

import openpyxl

warnings.filterwarnings("ignore", module="openpyxl")

CONTRACT = 100.0
UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
RATCHET_BT1 = UP + "c3f1d872-20260923_-_ReportTester-1301959345_-_Ratchet_-_Backtest_1.xlsx"
RATCHET_BT2 = UP + "b4c1149c-20260923_-_ReportTester-1301959345_-_Ratchet_-_Backtest_2.xlsx"
MERIDIAN_BT1 = UP + "6ea4682d-20260923_-_ReportTester-1301959345_-_Meridian_-_Backtest_1.xlsx"
MERIDIAN_BT2 = UP + "5d7f93bd-20260923_-_ReportTester-1301959345_-_Meridian_-_Backtest_2.xlsx"


def _f(x):
    if x is None or x == "":
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    return float(str(x).replace(" ", "").replace("\xa0", ""))


def _rows(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    return list(wb.worksheets[0].iter_rows(values_only=True))


def load_settings(path):
    out = {}
    for r in _rows(path):
        for c in r:
            if isinstance(c, str) and "=" in c and c.startswith("Inp"):
                k, v = c.split("=", 1)
                out[k] = v
    return out


def load_results(path):
    """Header stats block ('Results' .. 'Orders') as a flat {label: value} dict."""
    rows = _rows(path)
    s = next(i for i, r in enumerate(rows) if r[0] == "Results")
    o = next(i for i, r in enumerate(rows) if r[0] == "Orders")
    out = {}
    for r in rows[s:o]:
        cells = [c for c in r if c is not None]
        for k, v in zip(cells[0::2], cells[1::2]):
            if isinstance(k, str) and k.endswith(":"):
                out[k[:-1]] = v
    return out


def load_deals(path):
    rows = _rows(path)
    start = next(i for i, r in enumerate(rows) if r[0] == "Deals") + 2
    deals = []
    for r in rows[start:]:
        if r[0] is None or r[3] in (None, "balance"):
            continue
        if r[4] not in ("in", "out"):
            continue
        deals.append(dict(
            time=dt.datetime.strptime(r[0], "%Y.%m.%d %H:%M:%S"),
            deal=r[1], type=r[3], dir=r[4], vol=_f(r[5]), price=_f(r[6]),
            commission=_f(r[8]), swap=_f(r[9]), profit=_f(r[10]),
            balance=_f(r[11]), comment=r[12] or ""))
    return deals


def load_entry_orders(path):
    """Entry orders (comment == the EA's own comment, not 'sl ...'):
    {open_time: SL} - the stop the EA attached at entry."""
    rows = _rows(path)
    a = next(i for i, r in enumerate(rows) if r[0] == "Orders") + 2
    b = next(i for i, r in enumerate(rows) if r[0] == "Deals")
    out = {}
    for r in rows[a:b]:
        if r[0] and r[11] == "filled" and isinstance(r[12], str) and not r[12].startswith(("sl ", "tp ", "so ")):
            out[dt.datetime.strptime(r[0], "%Y.%m.%d %H:%M:%S")] = _f(r[7]) if r[7] else 0.0
    return out


def exit_reason(comment):
    c = (comment or "").lower()
    if c.startswith("sl "):
        return "SL"
    if c.startswith("tp "):
        return "TP"
    if c.startswith("so "):
        return "STOPOUT"
    return "EA"


def round_trips(deals, entry_sl=None):
    trips, cur = [], None
    for d in deals:
        if d["dir"] == "in":
            assert cur is None, "overlapping positions - not single-slot"
            cur = dict(entry_time=d["time"], side=1 if d["type"] == "buy" else -1,
                       entry=d["price"], vol=d["vol"], legs=[], out_vol=0.0,
                       profit_ccy=d["profit"] + d["commission"] + d["swap"])
        else:
            cur["legs"].append(d)
            cur["out_vol"] += d["vol"]
            cur["profit_ccy"] += d["profit"] + d["commission"] + d["swap"]
            if abs(cur["out_vol"] - cur["vol"]) < 1e-9:
                last = cur["legs"][-1]
                cur["exit_time"] = last["time"]
                cur["exit"] = last["price"]
                cur["pnl_usd"] = sum((l["price"] - cur["entry"]) * cur["side"] * l["vol"] * CONTRACT
                                     for l in cur["legs"])
                cur["move"] = (last["price"] - cur["entry"]) * cur["side"]
                cur["nlegs"] = len(cur["legs"])
                cur["last_comment"] = last["comment"]
                cur["reason"] = exit_reason(last["comment"])
                cur["zar_per_usd"] = (cur["profit_ccy"] / cur["pnl_usd"]) if abs(cur["pnl_usd"]) > 0.05 else None
                cur["balance_after"] = last["balance"]
                cur["hold_min"] = (cur["exit_time"] - cur["entry_time"]).total_seconds() / 60.0
                if entry_sl is not None:
                    cur["sl0"] = entry_sl.get(cur["entry_time"], 0.0)
                trips.append(cur)
                cur = None
    assert cur is None, "report ends with an open position"
    return trips


def load(path):
    return round_trips(load_deals(path), load_entry_orders(path))


def summary(pnls):
    gp = sum(p for p in pnls if p > 0)
    gl = -sum(p for p in pnls if p < 0)
    return dict(n=len(pnls), net=round(sum(pnls), 2),
                pf=round(gp / gl, 3) if gl > 0 else float("inf"),
                win=round(100.0 * sum(1 for p in pnls if p > 0) / max(1, len(pnls)), 1))


def closed_dd(pnls, start=0.0):
    """Closed-trade (balance) max drawdown: absolute, and % of the running peak."""
    eq, peak, dd, ddp = start, start, 0.0, 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        if peak > 0:
            ddp = max(ddp, (peak - eq) / peak)
    return dd, ddp


def _pct(s):
    m = re.search(r"\(([\d.]+)%\)", str(s))
    return float(m.group(1)) if m else None


def reconcile(path, label=""):
    trips = load(path)
    res = load_results(path)
    tot = round(sum(t["profit_ccy"] for t in trips), 2)
    rep = float(res["Total Net Profit"])
    legs = {t["nlegs"] for t in trips}
    dep = 10000.0
    bdd, bddp = closed_dd([t["profit_ccy"] for t in trips], dep)
    print(f"== {label}: {len(trips)} round-trips (report Total Trades {int(res['Total Trades'])}), "
          f"out-legs per trip {sorted(legs)}")
    print(f"   sum(profit+comm+swap) = {tot:.2f}   report Total Net Profit = {rep:.2f}   "
          f"diff = {tot - rep:+.2f}")
    print(f"   rebuilt balance DD max = {bdd:.2f} ({100 * bddp:.2f}%)   report Balance DD Maximal = "
          f"{res['Balance Drawdown Maximal']}")
    s = summary([t["profit_ccy"] for t in trips])
    print(f"   PF {s['pf']} (report {res['Profit Factor']:.6f})  win {s['win']}%")
    assert abs(tot - rep) < 0.005, "parse does not reconcile to the report"
    assert len(trips) == int(res["Total Trades"])
    return trips, res


if __name__ == "__main__":
    for p, lbl in [(RATCHET_BT1, "Ratchet BT1"), (RATCHET_BT2, "Ratchet BT2"),
                   (MERIDIAN_BT1, "Meridian BT1"), (MERIDIAN_BT2, "Meridian BT2")]:
        reconcile(p, lbl)
