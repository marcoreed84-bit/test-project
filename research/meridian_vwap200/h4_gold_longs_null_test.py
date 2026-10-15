"""
Random-timing null for the one thing that survived the lookahead-bug fix:
Gold longs only, 21/50 cross filtered by H4 trend alignment (corrected
lookup), 50-EMA exit. Full history: n=1290, PF=1.179, net%=+30.66%,
gross_PF=1.360. Given how much this exact construction's headline number
already moved once from a real bug, this needs the null test before being
treated as anything more than a candidate.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema, wilder_atr, GOLD_POINT
from meridian_early_cross_test import load_m15
from h4_alignment_backtest import load_h4

np.random.seed(20261015)

df, point = load_m15("GOLD")
close, high, low = df["close"].values, df["high"].values, df["low"].values
spread = df["spread"].values
m21 = ema(close, 21)
m50 = ema(close, 50)
atr = wilder_atr(high, low, close, 14)
n = len(df)

h4_time, h4_ema50, h4_close = load_h4("GOLD")
bar_times = df["time"].values.astype("datetime64[s]").astype(np.int64)
m15_bar_len = 15 * 60
h4_idx = np.searchsorted(h4_time, bar_times + m15_bar_len, side="right") - 2
h4_idx = np.clip(h4_idx, 0, len(h4_time) - 1)
h4_trend_up = h4_close[h4_idx] > h4_ema50[h4_idx]

TIME_CAP = 200

def ema50_exit_pnl(fill_i, direction):
    entry_px = close[fill_i] + spread[fill_i] * point * direction
    hard_limit = min(fill_i + TIME_CAP, n - 1)
    for k in range(fill_i + 1, hard_limit + 1):
        if np.isnan(m50[k]):
            continue
        broke = (close[k] < m50[k]) if direction > 0 else (close[k] > m50[k])
        if broke:
            return (close[k] - entry_px) / entry_px * direction
    return (close[hard_limit] - entry_px) / entry_px * direction

real_pnls = []
for i in range(215, n - 1):
    if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(atr[i]) or atr[i] <= 0
            or np.isnan(m21[i - 1]) or np.isnan(m50[i - 1])):
        continue
    cross_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
    if not cross_up:
        continue
    if not h4_trend_up[i]:
        continue
    fill_i = i + 1
    if fill_i >= n or np.isnan(atr[fill_i]) or atr[fill_i] <= 0:
        continue
    real_pnls.append(ema50_exit_pnl(fill_i, 1))

real_arr = np.array(real_pnls)
gw, gl = real_arr[real_arr > 0].sum(), -real_arr[real_arr <= 0].sum()
real_pf = gw / gl if gl > 0 else float("inf")
real_net = real_arr.sum()
n_trades = len(real_pnls)
print(f"REAL: n={n_trades}  PF={real_pf:.3f}  net%={100*real_net:.2f}")

valid_idx = np.array([i for i in range(215, n - 1) if not np.isnan(atr[i]) and atr[i] > 0])

N_DRAWS = 2000
null_pfs, null_nets = [], []
for d in range(N_DRAWS):
    picks = np.random.choice(valid_idx, size=n_trades, replace=False)
    pnls = [ema50_exit_pnl(i + 1, 1) for i in picks if i + 1 < n and not np.isnan(atr[i+1]) and atr[i+1] > 0]
    arr = np.array(pnls)
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    null_pfs.append(pf)
    null_nets.append(arr.sum())
    if (d + 1) % 500 == 0:
        print(f"  {d+1}/{N_DRAWS} draws done", flush=True)

null_pfs = np.array(null_pfs)
null_nets = np.array(null_nets)
pctile_net = (null_nets < real_net).mean() * 100
p_value = 1 - pctile_net / 100

print(f"\nRANDOM-TIMING NULL ({N_DRAWS} draws), same 50-EMA exit, real spread, matched n={n_trades}, longs only")
print(f"  null PF:  median={np.median(null_pfs):.3f}  p95={np.percentile(null_pfs,95):.3f}  p99={np.percentile(null_pfs,99):.3f}")
print(f"  null net%: median={100*np.median(null_nets):.2f}  p95={100*np.percentile(null_nets,95):.2f}  p99={100*np.percentile(null_nets,99):.2f}")
print(f"  real PF {real_pf:.3f}, net% {100*real_net:.2f} sits at the {pctile_net:.1f}th percentile of {N_DRAWS} draws")
print(f"  p-value (net%) = {p_value:.4f}")
