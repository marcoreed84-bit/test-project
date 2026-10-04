"""
Bar-match: Python simulator (+H4 filter) vs the REAL MT5 backtest of
Meridian_EA.mq5 v1.09 the user just ran (2026.01.01-2026.09.25,
InpUseH4TrendFilter=true, InpH4EMAPeriod=50, 255 real trades, PF=1.360577,
net 13359.76).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/silver_btc")
sys.path.insert(0, "/home/user/test-project/research/meridian")
sys.path.insert(1, "/home/user/test-project/research/aurelius")
from dataclasses import replace
import numpy as np
import pandas as pd
import msim as M
import engine as E
import meridian_msim_transfer_test as T

START = pd.Timestamp("2026-01-01")
END = pd.Timestamp("2026-09-26")
H4_EMA_PERIOD = 50


def ema(x, period):
    return pd.Series(x).ewm(alpha=2.0 / (period + 1.0), adjust=False).mean().values


def build_h4_trend_up(m5_time, h4):
    h4_ema = ema(h4["close"].values, H4_EMA_PERIOD)
    h4_trend_up = h4["close"].values > h4_ema
    h4_time = h4["time"].values
    # CORRECTED 2026-10-04 (Opus-audit finding) - see vanguard_m5_h4_trend_filter_oos_test.py's header
    h4_idx = np.searchsorted(h4_time, m5_time + np.timedelta64(5, "m"), side="right") - 2
    h4_idx = np.clip(h4_idx, 0, len(h4) - 1)
    valid = h4_idx >= 1
    return h4_trend_up[h4_idx], valid


G = {}


def h4_filter(ctx, t, d):
    up, valid = G["h4_up"], G["h4_valid"]
    if not valid[t]:
        return False
    return up[t] if d > 0 else (not up[t])


if __name__ == "__main__":
    m5x = E.load_m5_extended()
    df = m5x[(m5x.time >= START) & (m5x.time < END)][["time", "open", "high", "low", "close", "tick_volume", "spread"]].reset_index(drop=True)
    ctx = M.build_ctx(df)
    h4 = E.load_h4()

    h4_up, h4_valid = build_h4_trend_up(ctx["t64"], h4)
    G["h4_up"], G["h4_valid"] = h4_up, h4_valid
    p_h4 = replace(M.V102, entry_filter=h4_filter)
    trades, _ = M.simulate(ctx, p_h4, START, END)
    pn = T.pct(trades)
    print(f"PYTHON: n={len(trades)}  win%={100*(pn>0).mean():.1f}  %PF={T.pct_pf(pn):.3f}  net%={100*pn.sum():.1f}")

    rows = []
    for t in trades:
        rows.append(dict(sig_time=df["time"].iloc[t["entry_i"]], fill_time=t["entry_time"],
                          dir="buy" if t["dir"] > 0 else "sell", entry=round(t["entry"], 2)))
    py_df = pd.DataFrame(rows)
    py_df.to_csv("/tmp/meridian_python_trades_2026.csv", index=False)

    real = pd.read_csv("/tmp/meridian_real_entries.csv", parse_dates=["Time"])
    real["Type"] = real["Type"].str.lower()
    real["matched"] = False
    py_df["matched"] = False
    for pi, prow in py_df.iterrows():
        cand = real[(~real["matched"]) & (real["Type"] == prow["dir"]) &
                    ((real["Time"] - prow["fill_time"]).abs() <= pd.Timedelta(minutes=10))]
        if len(cand):
            ri = cand.index[0]
            real.loc[ri, "matched"] = True
            py_df.loc[pi, "matched"] = True

    print(f"Python trades matched: {py_df['matched'].sum()} / {len(py_df)} ({100*py_df['matched'].mean():.1f}%)")
    print(f"Real trades matched:   {real['matched'].sum()} / {len(real)} ({100*real['matched'].mean():.1f}%)")
