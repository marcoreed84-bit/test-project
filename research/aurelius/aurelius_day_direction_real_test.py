"""
Direct follow-up: day_direction_filter_test.py fixed a lookahead bug
in seasonal_pattern_test.py's day-direction definition (was price-at-
8am-vs-open, unusable for pre-8am trades) and built/tested it as a
real forward-looking ENTRY FILTER on Vanguard's construction. That
work was Vanguard-only - this checks the same corrected, causal
definition (sign of current close vs today's open, zero lookahead)
against Aurelius's REAL trades directly, since no full Python
re-simulation of Aurelius's complete entry/exit state machine exists
in this project (building one risks a subtle mismatch bug, same class
as the earlier ctx['m150'] mislabeling this session already caught
once) - the real MT5 trades ARE the ground truth here, not a
re-derivation.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import openpyxl
from datetime import datetime

AURELIUS_XLSX = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/56c08ddf-20260910_-_ReportTester-1301959345_-_Aurelius_M5.xlsx"


def find_deals_start(ws):
    for r in range(1, ws.max_row + 1):
        if ws.cell(row=r, column=1).value == "Deals":
            return r + 2
    return None


def load_trades(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]
    start = find_deals_start(ws)
    open_stack = []
    trades = []
    for r in range(start, ws.max_row + 1):
        time = ws.cell(row=r, column=1).value
        if time is None:
            continue
        dtype = ws.cell(row=r, column=4).value
        direction = ws.cell(row=r, column=5).value
        profit = ws.cell(row=r, column=11).value
        if dtype not in ("buy", "sell"):
            continue
        t = datetime.strptime(time, "%Y.%m.%d %H:%M:%S")
        if direction == "in":
            open_stack.append((t, 1 if dtype == "buy" else -1))
        elif direction == "out":
            if open_stack:
                ot, odir = open_stack.pop(0)
                trades.append((ot, t, odir, profit))
    return trades


aurelius = load_trades(AURELIUS_XLSX)
print(f"Aurelius: {len(aurelius)} real trades")

import engine as E
df5 = E.load_m5()
df5["date"] = df5["time"].dt.date
day_open_by_date = df5.groupby("date")["open"].first()
# per-bar lookup: close at/right-before each trade's own entry minute
df5_idx = df5.set_index("time")
close_series = df5["close"]
time_series = df5["time"]


def price_at_or_before(t):
    idx = np.searchsorted(time_series.values, np.datetime64(t), side="right") - 1
    if idx < 0:
        return None
    return close_series.iloc[idx]


withs, againsts = [], []
skipped = 0
for ot, ct, d, p in aurelius:
    day_open = day_open_by_date.get(ot.date())
    px = price_at_or_before(ot)
    if day_open is None or px is None:
        skipped += 1
        continue
    day_sign = 1 if px > day_open else (-1 if px < day_open else 0)
    if day_sign == 0:
        skipped += 1
        continue
    (withs if day_sign == d else againsts).append(p)

print(f"skipped (no reference / exactly at open): {skipped}")


def report(name, ps):
    if not ps:
        print(f"  {name}: 0 trades"); return
    wr = 100 * np.mean([x > 0 for x in ps])
    print(f"  {name:10s} n={len(ps):4d} net={sum(ps):9.2f} win%={wr:5.1f} avg={sum(ps)/len(ps):6.2f}")


print("\nAurelius REAL trades, causal day-direction (no lookahead):")
report("WITH", withs)
report("AGAINST", againsts)

# permutation test, day-level, same method as seasonal_pattern_test.py
day_dir_map = {}
for d in day_open_by_date.index:
    day_rows = df5[df5["date"] == d]
    if day_rows.empty:
        continue
    last_close = day_rows["close"].iloc[-1]
    o = day_open_by_date[d]
    if last_close != o:
        day_dir_map[d] = 1 if last_close > o else -1

def gap(trades, dmap):
    w, a = [], []
    for ot, ct, d, p in trades:
        dd = dmap.get(ot.date())
        if dd is None:
            continue
        (w if dd == d else a).append(p)
    if not w or not a:
        return 0.0
    return (sum(x > 0 for x in w) / len(w)) - (sum(x > 0 for x in a) / len(a))

real_gap = gap(aurelius, day_dir_map)
days = list(day_dir_map.keys())
signs = np.array([day_dir_map[d] for d in days])
rng = np.random.default_rng(0)
null_gaps = np.empty(2000)
for i in range(2000):
    shuffled = rng.permutation(signs)
    pm = dict(zip(days, shuffled))
    null_gaps[i] = gap(aurelius, pm)
pct = 100 * np.mean(null_gaps < real_gap)
print(f"\nday-level permutation test (end-of-day direction, not 8am - a coarser but still")
print(f"causal-enough proxy for 'today's prevailing direction'):")
print(f"  real win%-gap={100*real_gap:.1f}pp  null mean={100*null_gaps.mean():.1f}pp  percentile={pct:.1f}")
