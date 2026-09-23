"""
Step 5 (2026-09-23, later the same day): the REAL full-history v1.02 run came
back WORSE than v1.00 and v1.01's real full-history runs on net and PF -
30,957.06 ZAR / PF 1.195 vs 44,899.83 / 1.244 (v1.00) and 51,394.84 / 1.282
(v1.01). This script finds out why, from the three reports' own deals, the two
same-window 2026 reports, and the validated simulator (msim.py).

The three full-history reports (all parsed by research/ratchet/report.py,
reconciled to the cent):

  v1.00  1800d618 ... Backtest_1.xlsx      acct 1301959345  XMGlobal-MT5 6   GOLD#  1:100  84% real ticks
  v1.01  0cf718a8 ... Backtest_2_2.5.xlsx  acct 1301959345  XMGlobal-MT5 6   GOLD#  1:100  84% real ticks
  v1.02  5dd2e535 ... Backtest_23_09_23    acct 382043238   XMGlobal-MT5 13  GOLD   1:500  62% real ticks

The first two ARE the source of the header's v1.00/v1.01 figures (every
headline number matches to the cent). The third is NOT like-for-like with
them: different account, server and SYMBOL. GOLD is not GOLD#: it charges
swap (every GOLD report in the uploads folder does; every GOLD# report on
either GOLD# account is exactly 0.00) and quotes a wider spread.

Sections (run the whole file; each prints its own block):
  A  settings/reconciliation              F  2023-2025: which v1.02 change did what
  B  per-year P/L and swap                G  the entries GOLD missed - what they are
  C  2026 real chain: logic vs symbol     H  drawdown with and without swap
  D  GOLD vs GOLD# spread from fills      I  tick-quality proxy by half-year
  E  msim vs all three real runs          J  EA structural rules per config
                                          K  prediction for the missing like-for-like run
P/L in USD per 0.01 lot (price move x 1 oz) unless marked ZAR.
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/meridian")
sys.path.insert(0, "/home/user/test-project/research/ratchet")
import msim as M    # noqa: E402
import report as R  # noqa: E402

UP = R.UP
FULL = {
    "v1.00": UP + "1800d618-20260921_-_ReportTester-1301959345_-_Meridian_-_Backtest_1.xlsx",
    "v1.01": UP + "0cf718a8-20260921_-_ReportTester-1301959345_-_Meridian_-_Backtest_2_2.5.xlsx",
    "v1.02": UP + "5dd2e535-20260923_-_ReportTester-382043238_-_Meridian_-_Backtest_23_09_23_-_date.xlsx",
}
A, B = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-09-21")
W26, E26 = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-09-19")   # common 2026 span of all five reports
YEARS = [2023, 2024, 2025, 2026]
V100 = replace(M.BT1_BINARY, stop_atr=3.0)
V101 = replace(M.BT1_BINARY, use_sr=True)
CFG = {"v1.00": V100, "v1.01": V101, "v1.02": M.V102}


def header_rows(path):
    out = {}
    for r in R._rows(path)[:130]:
        c = [x for x in r if x is not None]
        if c and isinstance(c[0], str) and c[0].endswith(":") and len(c) >= 2:
            out[c[0][:-1]] = c[1]
        if r[0] == "Results":
            pass
    return out


def trips(path):
    df = pd.DataFrame(R.load(path))
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["k"] = df["entry_time"].dt.floor("5min")
    df["xk"] = pd.to_datetime(df["exit_time"]).dt.floor("5min")
    df["y"] = df["k"].dt.year
    return df


def sim_df(ctx, p, a=A, b=B):
    s = pd.DataFrame(M.simulate(ctx, p, a, b)[0])
    s["k"] = pd.to_datetime(s["entry_time"]).dt.floor("5min")
    s["xk"] = pd.to_datetime(s["exit_time"]).dt.floor("5min")
    s["y"] = s["k"].dt.year
    return s


def win(df, a=W26, b=E26):
    return df[(df.entry_time >= a) & (df.entry_time < b)]


def pair(a, b):
    """Match two real trade lists by entry bar + direction."""
    m = a.merge(b, on="k", suffixes=("_a", "_b"))
    m = m[m.side_a == m.side_b]
    return m, a[~a.k.isin(m.k)], b[~b.k.isin(m.k)]


def usd(x):
    return round(float(x), 1)


if __name__ == "__main__":
    T = {k: trips(p) for k, p in FULL.items()}
    BT1, BT2 = trips(R.MERIDIAN_BT1), trips(R.MERIDIAN_BT2)

    print("=== A. settings + reconciliation")
    for k, p in FULL.items():
        h = header_rows(p)
        d = R.load_deals(p)
        res = R.load_results(p)
        sw = sum(x["swap"] for x in d)
        pr = sum(x["profit"] for x in d)
        print(f"  {k}: {h['Symbol']:<6} {h['Leverage']:<6} {res['History Quality']:<16} trips {len(T[k])} "
              f"profit {pr:10.2f} swap {sw:9.2f} -> net {pr + sw:10.2f} (report {res['Total Net Profit']}) "
              f"PF {res['Profit Factor']:.4f}  balDD {res['Balance Drawdown Maximal']}  "
              f"eqDD {res['Equity Drawdown Maximal']}")

    print("\n=== B. per-year (USD by ENTRY year; ZAR net by CLOSE year, as the tester books it)")
    for k, p in FULL.items():
        d = pd.DataFrame(R.load_deals(p))
        d["y"] = d.time.dt.year
        zar = (d.profit + d.swap + d.commission).groupby(d.y).sum()
        sw = d.swap.groupby(d.y).sum()
        u = T[k].groupby("y").pnl_usd.sum()
        print(f"  {k}: " + " | ".join(f"{y} ${u.get(y, 0):7.1f} ZAR {zar.get(y, 0):9.2f} swap {sw.get(y, 0):8.2f}"
                                       for y in YEARS))

    print("\n=== C. 2026, real vs real (entries 2026-01-01..09-18, all at 100%-real-tick quality in 2026)")
    c = {"v1.01 GOLD# (150 EMA+S/R)": win(T["v1.01"]), "BT1 GOLD# (150 EMA, no S/R)": win(BT1),
         "BT2 GOLD# v1.02": win(BT2), "full-run GOLD v1.02": win(T["v1.02"])}
    for k, v in c.items():
        s = R.summary(list(v.pnl_usd))
        print(f"  {k:<28} n={s['n']} ${s['net']:8.2f} PF {s['pf']} win {s['win']}%")
    lg = c["BT2 GOLD# v1.02"].pnl_usd.sum() - c["v1.01 GOLD# (150 EMA+S/R)"].pnl_usd.sum()
    sr = c["v1.01 GOLD# (150 EMA+S/R)"].pnl_usd.sum() - c["BT1 GOLD# (150 EMA, no S/R)"].pnl_usd.sum()
    sy = c["full-run GOLD v1.02"].pnl_usd.sum() - c["BT2 GOLD# v1.02"].pnl_usd.sum()
    print(f"  S/R filter (BT1 -> v1.01, same symbol)          : {sr:+8.1f}")
    print(f"  250 SMA swap (v1.01 -> BT2, same symbol)        : {lg:+8.1f}")
    print(f"  symbol GOLD# -> GOLD (BT2 -> GOLD, same logic)  : {sy:+8.1f}")
    m, ao, bo = pair(c["BT2 GOLD# v1.02"], c["full-run GOLD v1.02"])
    se = m[m.xk_a == m.xk_b]
    de = m[m.xk_a != m.xk_b]
    print(f"    matched {len(m)}/{len(c['full-run GOLD v1.02'])} GOLD entries to the bar; same exit bar {len(se)}: "
          f"${se.pnl_usd_b.sum() - se.pnl_usd_a.sum():+.1f} (fills); different exit {len(de)}: "
          f"${de.pnl_usd_b.sum() - de.pnl_usd_a.sum():+.1f}; GOLD#-only {len(ao)}: ${ao.pnl_usd.sum():+.1f} "
          f"(missed by GOLD); GOLD-only {len(bo)}: ${bo.pnl_usd.sum():+.1f}")
    big = de.assign(g=de.pnl_usd_b - de.pnl_usd_a).sort_values("g").head(1)
    for _, r in big.iterrows():
        print(f"    largest exit divergence: {r.k} GOLD# {r.reason_a} {r.pnl_usd_a:+.2f} vs GOLD {r.reason_b} "
              f"{r.pnl_usd_b:+.2f} (GOLD SL {r.sl0_b} vs GOLD# SL {r.sl0_a})")
    for _, r in ao.iterrows():
        print(f"    missed: {r.k} {'BUY ' if r.side > 0 else 'SELL'} {r.pnl_usd:+8.2f} {r.reason}")

    print("\n=== D. GOLD vs GOLD# spread gap, from real fills on the same entry bar + direction")
    mm = pd.concat([pair(T["v1.01"], T["v1.02"])[0], pair(BT2, T["v1.02"])[0]]).drop_duplicates("k")
    mm["d"] = mm.entry_b - mm.entry_a
    for y in YEARS:
        q = mm[mm.y_a == y]
        bu, sl = q[q.side_a > 0].d.median(), q[q.side_a < 0].d.median()
        print(f"  {y}: n={len(q):4d} GOLD buy fill {bu:+.2f}, sell fill {sl:+.2f} vs GOLD# -> spread gap "
              f"~{100 * (bu - sl):.0f} pts")

    print("\n=== E. msim (GOLD# bars) vs each real run, by year - entry-bar matches and USD over-prediction")
    ctx = M.build_ctx()
    S = {k: sim_df(ctx, p) for k, p in CFG.items()}
    over = {}
    for k in CFG:
        r, s = T[k], S[k]
        m = r.merge(s, on="k", suffixes=("_r", "_s"))
        m = m[m.side == m.dir]
        row = []
        for y in YEARS:
            ry, sy = r[r.y == y], s[s.y == y]
            o = sy.pnl.sum() - ry.pnl_usd.sum()
            over[(k, y)] = o
            row.append(f"{y} match {100 * (m.y_r == y).sum() / len(ry):5.1f}% real ${ry.pnl_usd.sum():7.1f} "
                       f"sim ${sy.pnl.sum():7.1f}")
        print(f"  {k} ({'GOLD' if k == 'v1.02' else 'GOLD#'}): " + " | ".join(row) +
              f" | sim over-predicts by ${sum(over[(k, y)] for y in YEARS):+.0f}")

    print("\n=== F. v1.01 -> v1.02 (the 250 SMA swap; S/R is in both) like-for-like, by year")
    for y in YEARS:
        dm = S["v1.02"][S["v1.02"].y == y].pnl.sum() - S["v1.01"][S["v1.01"].y == y].pnl.sum()
        m, ao, bo = pair(T["v1.01"][T["v1.01"].y == y], T["v1.02"][T["v1.02"].y == y])
        print(f"  {y}: msim (GOLD# bars) {dm:+7.1f} | real v1.01 GOLD# -> real v1.02 GOLD: total "
              f"{T['v1.02'][T['v1.02'].y == y].pnl_usd.sum() - T['v1.01'][T['v1.01'].y == y].pnl_usd.sum():+7.1f} = "
              f"shared trades (symbol only) {m.pnl_usd_b.sum() - m.pnl_usd_a.sum():+7.1f} + unique trades "
              f"(logic, + symbol-missed) {bo.pnl_usd.sum() - ao.pnl_usd.sum():+7.1f}")

    print("\n=== G. msim v1.02 entries (GOLD# bars) the real GOLD run did not take")
    t64, c_, atr, vw = ctx["t64"], ctx["c"], ctx["atr"], ctx["vwap"]
    m21, m50 = M.ma(ctx, 21, "ema"), M.ma(ctx, 50, "ema")
    atr_med = pd.Series(atr).rolling(288 * 20, min_periods=100).median().values
    s = S["v1.02"].copy()
    idx = np.searchsorted(t64, s.k.values.astype("datetime64[ns]")) - 1
    s["hour"] = s.k.dt.hour
    s["atr_rel"] = atr[idx] / atr_med[idx]
    s["cross"] = np.minimum(abs(m21[idx] - m50[idx]), abs(m21[idx - 1] - m50[idx - 1])) / atr[idx]
    s["missed"] = ~s.k.isin(set(T["v1.02"].k))
    ms, tk = s[s.missed], s[~s.missed]
    print(f"  {len(ms)} of {len(s)} missed. session-open (01:xx) {100 * (ms.hour == 1).mean():.0f}% vs "
          f"{100 * (tk.hour == 1).mean():.1f}% of taken; ATR >1.5x its 20-day median {100 * (ms.atr_rel > 1.5).mean():.0f}% "
          f"vs {100 * (tk.atr_rel > 1.5).mean():.0f}%; 21/50 cross margin median {ms.cross.median():.3f} vs "
          f"{tk.cross.median():.3f} ATR")
    print("  missed by year (n, sim $): " + ", ".join(
        f"{y} {int((ms.y == y).sum())} ${ms[ms.y == y].pnl.sum():+.0f}" for y in YEARS))
    print(f"  expected cost of {len(ms)} random v1.02 trades at the run's mean ${s.pnl.mean():.2f}/trade: "
          f"${len(ms) * s.pnl.mean():.0f}; realized ${ms.pnl.sum():.0f}")
    base = ctx["spread"].copy()
    for gap in (0, 15, 20):
        ctx["spread"] = base + gap
        q = sim_df(ctx, M.V102)
        print(f"  msim v1.02 with spread +{gap:2d} pts: " +
              " | ".join(f"{y} ${q[q.y == y].pnl.sum():7.1f}" for y in YEARS) +
              f"   (real GOLD: " + " | ".join(f"{y} ${T['v1.02'][T['v1.02'].y == y].pnl_usd.sum():.1f}"
                                            for y in YEARS) + ")")
    ctx["spread"] = base

    print("\n=== H. balance drawdown, with and without swap (ZAR, 20,000 deposit)")
    for k, p in FULL.items():
        d = pd.DataFrame(R.load_deals(p))
        for lbl, v in [("as booked", d.profit + d.swap + d.commission), ("swap removed", d.profit + d.commission)]:
            if lbl == "swap removed" and d.swap.abs().sum() == 0:
                continue
            bal = 20000 + v.cumsum()
            pk = bal.cummax()
            dd = pk - bal
            i = dd.idxmax()
            j = bal[:i + 1].idxmax()
            w = d[(d.index > j) & (d.index <= i)]
            print(f"  {k} {lbl:<12}: max {dd.max():8.2f} ({100 * dd.max() / pk[i]:.2f}%) peak {d.time[j]:%Y-%m-%d} "
                  f"trough {d.time[i]:%Y-%m-%d}; swap inside window {w.swap.sum():.2f}")

    print("\n=== I. tick-quality proxy: share of SL exits filled EXACTLY at the SL price (generated ticks fill "
          "exactly; real ticks slip), by half-year")
    for k, df in [("v1.00", T["v1.00"]), ("v1.01", T["v1.01"]), ("v1.02 GOLD", T["v1.02"]), ("BT2 (100%)", BT2)]:
        q = df[df.reason == "SL"].copy()
        q["h"] = q.entry_time.dt.year.astype(str) + "H" + ((q.entry_time.dt.month > 6) + 1).astype(str)
        q["ex"] = (q.exit - q.last_comment.str[3:].astype(float)).abs() < 0.005
        print(f"  {k:<11} " + " ".join(f"{h}:{100 * g.ex.mean():3.0f}%" for h, g in q.groupby("h")))
    for k in ("v1.01", "v1.02"):
        m = T[k].merge(S[k], on="k", suffixes=("_r", "_s"))
        m = m[m.side == m.dir]
        dx = m[m.xk_r != m.xk_s]
        print(f"  {k}: matched trades exiting on a different bar than msim, by year: " +
              ", ".join(f"{y} {int((dx.y_r == y).sum())} (${(dx[dx.y_r == y].pnl_usd - dx[dx.y_r == y].pnl).sum():+.0f})"
                        for y in YEARS))

    print("\n=== J. EA structural rules (present in EVERY real run), effect per config, msim full history")
    for rule, kw in [("Friday 22:00 flatten", dict(no_friday=True)),
                     ("not stop-and-reverse", dict(stop_and_reverse=True)),
                     ("stale-ticket bar", dict(stale_ticket_bar=False))]:
        for k in ("v1.01", "v1.02"):
            base_n = S[k].pnl.sum()
            alt = sim_df(ctx, replace(CFG[k], **kw)).pnl.sum()
            print(f"  {rule:<21} {k}: {base_n - alt:+7.1f} ({100 * (base_n - alt) / base_n:+.1f}% of the EA's net)")

    print("\n=== K. prediction for the like-for-like run still missing (v1.02, GOLD#, 2023.01.01-2026.09.19, 20000)")
    s2 = S["v1.02"]
    b1 = sum(over[("v1.01", y)] for y in YEARS)
    b0 = sum(over[("v1.00", y)] for y in YEARS)
    rate = 51394.84 / T["v1.01"].pnl_usd.sum()
    lo, hi = s2.pnl.sum() - b1, s2.pnl.sum() - b0
    print(f"  msim ${s2.pnl.sum():.0f} ({len(s2)} trades) less msim's own measured over-prediction on the two real "
          f"GOLD# runs (${b0:.0f}..${b1:.0f}) = ${lo:.0f}..${hi:.0f} ~ {lo * rate:,.0f}..{hi * rate:,.0f} ZAR "
          f"at v1.01's realized {rate:.2f} ZAR/$")
