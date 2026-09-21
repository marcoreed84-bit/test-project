"""
User's ask: find a confluence signal that agrees with (doesn't remove)
Vanguard's real top-20 winning trades, but would cut some of the
LOSING trades - i.e., something that separates "this will be a huge
trend-catch" from "this will be noise" without being confused with
things already tried (VWAP/S-R/Aurelius bias/Aurelius position/day-
direction - all already in the baseline or already tested and
rejected/modest).

Data-driven: pulls real engine.py feature values (entry ATR, ATR as a
% of price, H4 trend state, distance from S/R in ATR, day-direction,
hour of day, day of week) at the EXACT bar of each of Vanguard's real
top-20 winning trades (from its real MT5 deals) and of its real
LOSING trades, and compares the distributions - looking for something
that's consistently true for the winners and less true for the losers.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import openpyxl
from datetime import datetime
import engine as E

VANGUARD_XLSX = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/10ce4f5a-20260921_-_ReportTester-1301959345_-_Vanguard_-_Backtest_1.xlsx"


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
        if time is None: continue
        dtype = ws.cell(row=r, column=4).value
        direction = ws.cell(row=r, column=5).value
        profit = ws.cell(row=r, column=11).value
        if dtype not in ("buy", "sell"): continue
        t = datetime.strptime(time, "%Y.%m.%d %H:%M:%S")
        if direction == "in":
            open_stack.append((t, 1 if dtype == "buy" else -1))
        elif direction == "out":
            if open_stack:
                ot, odir = open_stack.pop(0)
                trades.append((ot, t, odir, profit))
    return trades


vanguard = load_trades(VANGUARD_XLSX)
df5 = E.load_m5()
h4 = E.load_h4()
ctx = E.build_context(df5, h4, params=E.P)
atr = ctx["atr"]
close = ctx["close"]
vwap = ctx["vwap"]
sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
times = df5["time"].values

dates = df5["time"].dt.date.values
day_open = pd.Series(close).groupby(pd.Series(dates)).transform("first").values
day_dir_sign = np.sign(close - day_open)

# H4 trend: is H4 close above/below its own 50-period MA (a genuinely
# different, higher-timeframe signal not yet tried on Vanguard)
h4 = h4.reset_index(drop=True)
h4_ma50 = h4["close"].rolling(50).mean()
h4_trend = np.sign(h4["close"] - h4_ma50)
h4_times = h4["time"].values


def nearest_bar(t):
    idx = np.searchsorted(times, np.datetime64(t), side="right") - 1
    return idx if idx >= 0 else None


def nearest_h4_trend(t):
    idx = np.searchsorted(h4_times, np.datetime64(t), side="right") - 1
    if idx < 0 or idx >= len(h4_trend) or pd.isna(h4_trend.iloc[idx]):
        return 0
    return h4_trend.iloc[idx]


rows = []
for ot, ct, d, p in vanguard:
    i = nearest_bar(ot)
    if i is None or np.isnan(atr[i]) or atr[i] <= 0:
        continue
    vwap_dist_atr = (close[i] - vwap[i]) / atr[i] * d   # +ve = with-trade side, further = more confirmation
    sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
    h4t = nearest_h4_trend(ot)
    h4_agree = 1 if h4t == d else (0 if h4t == 0 else -1)
    day_agree = 1 if day_dir_sign[i] == d else -1
    rows.append(dict(time=ot, dir=d, profit=p, atr=atr[i], vwap_dist_atr=vwap_dist_atr,
                      sr_dist=sr, h4_agree=h4_agree, day_agree=day_agree, hour=ot.hour))

df = pd.DataFrame(rows)
top20 = df.nlargest(20, "profit")
losers = df[df["profit"] < 0]
print(f"n trades with features: {len(df)}  top20 sum={top20['profit'].sum():.2f}  "
      f"losers n={len(losers)} sum={losers['profit'].sum():.2f}")

print("\nfeature comparison: top20 winners vs real losers vs all trades")
for col in ("vwap_dist_atr", "sr_dist", "h4_agree", "day_agree", "atr", "hour"):
    print(f"  {col:16s} top20 mean={top20[col].mean():8.3f}  losers mean={losers[col].mean():8.3f}  "
          f"all mean={df[col].mean():8.3f}")

print("\nh4_agree distribution (1=H4 trend agrees, 0=H4 flat/no data, -1=H4 disagrees):")
print("  top20:  ", top20["h4_agree"].value_counts().to_dict())
print("  losers: ", losers["h4_agree"].value_counts().to_dict())
print("  all:    ", df["h4_agree"].value_counts().to_dict())

print("\nvwap_dist_atr distribution (how far price is beyond VWAP in the TRADE's own direction):")
print(f"  top20:   min={top20['vwap_dist_atr'].min():.2f} 25%={top20['vwap_dist_atr'].quantile(.25):.2f} "
      f"median={top20['vwap_dist_atr'].median():.2f}")
print(f"  losers:  min={losers['vwap_dist_atr'].min():.2f} 25%={losers['vwap_dist_atr'].quantile(.25):.2f} "
      f"median={losers['vwap_dist_atr'].median():.2f}")
