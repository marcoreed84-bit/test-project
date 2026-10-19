"""
Consolidated M5 / M15 / H1 table for the externally-claimed stochastic
zone-cross settings (Gold, Silver, BTC), each with a RISK-MATCHED
random-timing null - and a correction to the risk-matching itself.

AUDIT of stoch_table_claims_null_risk_matched_test.py (the first fix):
its core idea is right (borrow risk sizing from the real trades so a
signal bar's naturally-tight swing stop can't masquerade as timing
skill), and its bar-by-bar stop/target/opposite-cross loop is
identical to build_trades(). But it borrowed the WRONG quantity:
  - real trades measure risk = |close[signal] - swing| at the SIGNAL
    bar, then anchor the stop at the swing PRICE and the target at
    entry_px + RR*risk, where entry_px = close[signal+1] +/- spread.
  - the first fix put the null stop at entry_px*(1 -/+ risk_pct), i.e.
    it dropped the signal->fill drift and the spread from the stop
    distance. Real effective stop distance from the fill price is
    risk + drift + spread, which on M5 (tight stops, spread a sizeable
    fraction of risk) is systematically WIDER than what the null got.
  So the null and real trades still did not share a stop/target
  geometry. Fix here: borrow each real trade's EFFECTIVE
  (dir, stop distance from entry, target distance from entry) as a
  tuple, shuffled - identical stop/target geometry AND identical
  direction mix by construction. Entry timing is the only thing left.

Built-in self-check (identity test): replaying the REAL signal bars
through the null's exit machinery with their own borrowed geometry
must reproduce the real net% exactly. If it doesn't, the null's loop
is not the real loop and the p-value is meaningless - the script
asserts on this.

No lookahead: the geometry pool is a whole-sample property of the real
trades, used only to size random trades (a null-construction choice,
not a trading decision). Entry fills on bar i+1's close, exits only
look at bars after the fill, same as the real build_trades().

H1: resampled from each instrument's M15_native feed (same approach as
classic_stoch_21_5_5_btc_h1_test.load_btc_h1: OHLC aggregated, spread =
max of constituent M15 spreads - conservative). Gold trimmed to
2014-06-13+ BEFORE resampling (pre-2014 "M15" is mislabeled coarser
bars). Gold/Silver H1 reuse that instrument's M15 claimed config
(no H1-specific claim exists; K=1 each, no sweep).

Point size read from each CSV header (verified: GOLD 0.01, SILVER 0.001,
BTCUSD 0.01). M5 files are a recent slice only, not 2014+ (noted).

RESULT CAVEAT (read before citing): this null returned all 9 rows at the
p floor - a uniform result, investigated in
stoch_table_claims_cross_conditioned_control.py. Most of the gap is the
entry-on-fresh-cross / exit-on-opposite-cross coupling, not zone timing
skill: against random same-direction crosses Gold H1 p=0.12 and BTC H1
p=1.0. Do NOT read these p-values as "beats random timing".

Honest K: 9 rows. NEW %PF tests here = 2 (Gold H1, Silver H1). BTC M15
and BTC H1 %PF are re-computed only to confirm the cited numbers (0.201,
0.388), not counted as new. Null tests: 9 risk-matched nulls, each
the first CORRECT timing test of its config (earlier nulls retracted).
Across the 9-row table, any single p must clear Sidak 1-(0.95)^(1/9)
~= 0.0057 to count as significant at the family level.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from dual_stoch_cross_200ema_test import pct_pf
from stoch_table_claims_verify_test import load, build_trades, SWING_BARS, RR, TIME_CAP_BARS

N_DRAWS = 1000
SIDAK_9 = 1 - 0.95 ** (1 / 9)


def load_h1(m15_file, trim_gold):
    df15, point = load(m15_file, trim_gold=trim_gold)
    h1 = df15.set_index("time").resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "spread": "max"}
    ).dropna()
    return h1.reset_index(), point


def effective_geometry(df, point, real_trades):
    """(dir, stop_dist_frac, target_dist_frac) measured from the real
    fill price - exactly what build_trades() enforced."""
    close, high, low, spread = df["close"].values, df["high"].values, df["low"].values, df["spread"].values
    geo = []
    for t in real_trades:
        i, d = t["entry_i"], t["dir"]
        swing = low[i - SWING_BARS:i].min() if d > 0 else high[i - SWING_BARS:i].max()
        risk = d * (close[i] - swing)
        sc = spread[i + 1] * point
        entry = close[i + 1] + (sc if d > 0 else -sc)
        stop_px, tgt_px = swing, entry + d * RR * risk
        geo.append((d, d * (entry - stop_px) / entry, d * (tgt_px - entry) / entry))
    return geo


class Machine:
    def __init__(self, df, point, kp, sl, dp):
        c, h, l = df["close"].values, df["high"].values, df["low"].values
        k, d = stochastic_lowhigh_sma(h, l, c, kp, sl, dp)
        self.n = len(df)
        self.close, self.high, self.low = c.tolist(), h.tolist(), l.tolist()
        self.spread = df["spread"].values.tolist()
        self.point = point
        v = ~(np.isnan(k) | np.isnan(d))
        vv = np.zeros(self.n, bool); vv[1:] = v[1:] & v[:-1]
        self.up = (vv & np.r_[False, k[:-1] <= d[:-1]] & (k > d)).tolist()
        self.dn = (vv & np.r_[False, k[:-1] >= d[:-1]] & (k < d)).tolist()
        self.start = kp + sl + dp + SWING_BARS + 5
        self.valid_idx = np.array([i for i in range(self.start, self.n - TIME_CAP_BARS - 2) if v[i]])

    def trade(self, i, d, stop_frac, tgt_frac):
        fill = i + 1
        sc = self.spread[fill] * self.point
        entry = self.close[fill] + (sc if d > 0 else -sc)
        stop_px = entry - d * stop_frac * entry
        tgt_px = entry + d * tgt_frac * entry
        lim = min(fill + TIME_CAP_BARS, self.n - 1)
        hi, lo = self.high, self.low
        for j in range(fill + 1, lim + 1):
            if (lo[j] <= stop_px) if d > 0 else (hi[j] >= stop_px):
                return j, d * (stop_px - entry) / entry
            if (hi[j] >= tgt_px) if d > 0 else (lo[j] <= tgt_px):
                return j, d * (tgt_px - entry) / entry
            if (d > 0 and self.dn[j]) or (d < 0 and self.up[j]):
                scj = self.spread[j] * self.point
                px = self.close[j] - (scj if d > 0 else -scj)
                return j, d * (px - entry) / entry
        return lim, d * (self.close[lim] - entry) / entry


def null_test(df, point, kp, sl, dp, real_trades, n_draws=N_DRAWS, seed=0):
    m = Machine(df, point, kp, sl, dp)
    geo = effective_geometry(df, point, real_trades)
    real_net = sum(t["pnl_pct"] for t in real_trades)
    # identity self-check: real bars through the null machinery
    replay = sum(m.trade(t["entry_i"], *g)[1] for t, g in zip(real_trades, geo))
    assert abs(replay - real_net) < 1e-9, f"null machinery != real build_trades ({replay} vs {real_net})"
    rng = np.random.default_rng(seed)
    nt = len(real_trades)
    nets = np.empty(n_draws)
    for k in range(n_draws):
        order = rng.permutation(nt)
        total, nxt, taken, pool, pp = 0.0, m.start, 0, [], 0
        while taken < nt:
            if pp >= len(pool):
                pool = sorted(int(x) for x in rng.choice(m.valid_idx, size=max(nt * 3, 200)) if x >= nxt)
                pp = 0
                if not pool:
                    break
            i = pool[pp]; pp += 1
            if i < nxt:
                continue
            ex, pnl = m.trade(i, *geo[order[taken]])
            total += pnl; nxt = ex + 1; taken += 1
        nets[k] = total
    p = (np.sum(nets >= real_net) + 1) / (n_draws + 1)
    return real_net, nets, p, taken


CONFIGS = [
    # instrument, tf, file, gold_trim, h1?, K, slow, D, zone_lo, zone_hi
    ("GOLD",   "M5",  "GOLD_M5.csv",            True,  False, 8,  3, 3, 15.0, 85.0),
    ("GOLD",   "M15", "GOLD_M15_native.csv",    True,  False, 14, 3, 3, 20.0, 80.0),
    ("GOLD",   "H1",  "GOLD_M15_native.csv",    True,  True,  14, 3, 3, 20.0, 80.0),
    ("SILVER", "M5",  "SILVER_M5.csv",          False, False, 14, 3, 3, 10.0, 90.0),
    ("SILVER", "M15", "SILVER_M15_native.csv",  False, False, 21, 3, 3, 15.0, 85.0),
    ("SILVER", "H1",  "SILVER_M15_native.csv",  False, True,  21, 3, 3, 15.0, 85.0),
    ("BTCUSD", "M5",  "BTCUSD_M5.csv",          False, False, 14, 3, 3, 20.0, 80.0),
    ("BTCUSD", "M15", "BTCUSD_M15_native.csv",  False, False, 21, 5, 5, 20.0, 80.0),
    ("BTCUSD", "H1",  "BTCUSD_M15_native.csv",  False, True,  21, 5, 5, 20.0, 80.0),
]


def verdict(pf, net, real_net, nets, p):
    prof = "profitable" if pf > 1.0 else "net loser"
    if real_net < np.median(nets):
        t = "timing worse than random"
    elif p <= SIDAK_9:
        t = "beats random timing (survives K=9)"
    elif p <= 0.05:
        t = "beats random at raw p<0.05 only (fails K=9)"
    else:
        t = "no timing edge"
    return f"{prof}, {t}"


if __name__ == "__main__":
    rows = []
    for inst, tf, f, trim, h1, kp, sl, dp, zl, zh in CONFIGS:
        df, point = load_h1(f, trim) if h1 else load(f, trim_gold=trim)
        tr = build_trades(df, point, kp, sl, dp, zl, zh)
        real_net, nets, p, taken = null_test(df, point, kp, sl, dp, tr)
        pf = pct_pf(tr)
        geo = effective_geometry(df, point, tr)
        v = verdict(pf, real_net, real_net, nets, p)
        print(f"{inst} {tf} ({kp},{sl},{dp}) {zl:.0f}/{zh:.0f}  {df['time'].iloc[0].date()}..{df['time'].iloc[-1].date()} "
              f"point={point}  n={len(tr)}  %PF={pf:.3f}  net%={100*real_net:.2f}  "
              f"null mean={100*nets.mean():.2f} [5%={100*np.percentile(nets,5):.2f}, 95%={100*np.percentile(nets,95):.2f}]  "
              f"p={p:.4f}  mean stop%={100*np.mean([g[1] for g in geo]):.3f}  -> {v}", flush=True)
        rows.append((inst, tf, f"{kp}/{sl}/{dp}", f"{zl:.0f}/{zh:.0f}", len(tr), pf, 100 * real_net, p, v))
    print("\n| Instrument | TF | K/Slow/D | Zone | n | %PF | net% | p (risk-matched) | Verdict |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]:.3f} | {r[6]:.1f} | {r[7]:.4f} | {r[8]} |")
    print(f"\nHonest K: 9-row family, Sidak per-test bar = {SIDAK_9:.4f}. New %PF configs = 2 (Gold H1, Silver H1).")
