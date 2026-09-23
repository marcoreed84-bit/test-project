"""
v1.17 research: does an Aurelius M5 trend gate on MSG entries survive FULL
SEQUENTIAL, cascade-aware simulation?

Idea under test (from a static classification of the 93 real v1.15 trades in
Backtest_Final): only let CheckSessionSetups' signal place a trade when the
real Aurelius_EA.mq5 Aligned() state (M5, shipped v1.46 defaults, most recent
CLOSED M5 bar) agrees with the trade direction.  NEUTRAL and AGAINST touches
are rejected InRiskDeadZone-style (`continue`: range not retired, a later
touch may still fire).

Baseline = v1.16 = v1.14 entry logic + v1.15 small-risk sizing (sizing is
cascade-free, so it is applied to both arms identically).  Windows/symbols
exactly as search.py.

Sections:
  0. static re-check of the real Backtest_Final list (fixes the stale-M5 issue)
  1. sequential sim: v1.16 vs gate "with" / "not_against" / "with"+kill
  2. cascade anatomy per window, by calendar day (MSG3-only => one frozen
     range per day): identical / re-timed / flipped / genuinely skipped /
     new day, plus how many differing days had NO gate rejection on their own
     range (the pure cross-day cascade)
  3. rejection anatomy: how many touches/ranges the gate rejects, and how
     many rejected ranges re-time vs die
  4. null: the same gate driven by the real Aurelius state series circularly
     time-shifted (same base rates and regime persistence, timing broken)
  4b. count-matched null: since section 2 shows the gate does not cascade,
     dropping N random baseline trades is a fair comparison for "keep the
     same number of trades the real gate keeps" - is the WITH subset better
     than a random subset of the same size?
  5. cascade-free control: SHRINK non-WITH setups to 0.01 instead of skipping
     (v1.15-style), sequential sim + re-derivation on the real Final list
  6. GOLD vs GOLD# jitter sensitivity of the alignment itself

Run:  python3 run_aurelius_gate.py [--null N]     (--null 200: ~6 min)

RESULT (2026-09-23, recorded in MSG_Trader_EA.mq5's header): NOT ADOPTED.
  - It does not cascade: 0 differing days without a gate rejection on their
    own range, 0 new days (median hold 0.51h - only 1 of 96 baseline trades is
    still open at the next day's range freeze).
  - It KILLS rather than re-times: GOLD 2026, 2053 rejected touches on 60
    ranges -> 56 never trade, 1 re-timed, 3 flip direction.  The M5 stack is
    persistent across the 4.25h watch, so one rejection means all of them.
  - Net falls in HOLDOUT, IS and 2026 on both symbols (GOLD 2026 -331.38 USD,
    96 -> 40 trades) because the NEUTRAL bucket it removes is net POSITIVE
    (sim +394.06 USD; real Final list +5,469.36 ZAR).  PF/DD improve, but
    the WITH subset is not significantly better than a random same-size subset
    (p 0.07-0.63), and the cascade-free shrink version loses too.
"""
import sys
import collections
import datetime as dt
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/msg")
from sim import load_bars, simulate, stats, aurelius_alignment  # noqa: E402
from search import base_params, PERIODS  # noqa: E402
from final_candidate import v115_size  # noqa: E402
from report import load_deals, round_trips, entry_orders  # noqa: E402

UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
FINAL = UP + "6552888b-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_Final.xlsx"
SYMS = ("GOLD", "GOLD#")
PER_ORDER = ("HOLDOUT", "IS", "OOS", "2026")


def cls(st, d):
    return "WITH" if st == d else ("AGAINST" if st == -d else "NEUTRAL")


def day(t):
    return dt.datetime.utcfromtimestamp(t).date()


def minute(t):
    return t - t % 60


TREND = None   # set in __main__; baseline runs carry it too (gate "off") so every trade records its state


def run(bars, sym, per, **kw):
    a, b = PERIODS[per]
    kw.setdefault("trend_arr", TREND)
    kw.setdefault("size_fn", v115_size)
    rej = []
    tr, _ = simulate(bars, base_params(sym, start=a, end=b, **kw), rej=rej)
    return tr, rej


# --------------------------------------------------------------- 0. static
def static_final(trend, bars):
    T = round_trips(load_deals(FINAL))
    tb = bars["time"].values
    rows = []
    for t in T:
        m = np.datetime64(t["entry_time"].replace(second=0))
        k = int(np.searchsorted(tb, m))
        assert tb[k] == m
        rows.append(dict(c=cls(int(trend[k]), t["side"]), usd=t["pnl_usd"], zar=t["profit_ccy"]))
    df = pd.DataFrame(rows)
    print("0) STATIC, real Backtest_Final (v1.15, GOLD, 93 trades), Aurelius state on the spliced M5 series")
    for c, g in df.groupby("c"):
        z = g["zar"]
        pf = z[z > 0].sum() / -z[z < 0].sum()
        print(f"   {c:8s} n={len(g):3d} win={100*(z>0).mean():5.1f}%  net {z.sum():10.2f} ZAR  PF {pf:.2f}")
    keep = df[df.c == "WITH"]["zar"]
    z = df["zar"]
    print(f"   all       n={len(df)} net {z.sum():.2f} ZAR PF {z[z>0].sum()/-z[z<0].sum():.2f}   ->  WITH-only (static) "
          f"n={len(keep)} net {keep.sum():.2f} ZAR PF {keep[keep>0].sum()/-keep[keep<0].sum():.2f}")


# --------------------------------------------------------------- 2. cascade anatomy
def anatomy(base, cand, rej):
    """Per calendar day (= per MSG3 range).  Entry minute is exact in the sim
    (no tick jitter), and matching is by day + minute, like v1.14's
    corrected header diff."""
    bd = collections.defaultdict(list)
    cd = collections.defaultdict(list)
    for t in base:
        bd[day(t["range_end"])].append(t)
    for t in cand:
        cd[day(t["range_end"])].append(t)
    rej_days = {day(r["range_end"]) for r in rej}
    cat = collections.defaultdict(lambda: [0, 0.0, 0.0, 0, 0])  # n_days, base net, cand net, n base trades, n cand trades
    no_rej_diff = []
    for d in sorted(set(bd) | set(cd)):
        b, c = bd.get(d, []), cd.get(d, [])
        if b and c:
            bk = [(minute(x["t"]), x["dir"]) for x in b]
            ck = [(minute(x["t"]), x["dir"]) for x in c]
            if bk == ck:
                k = "identical"
            elif [x["dir"] for x in b] == [x["dir"] for x in c]:
                k = "re-timed (same dir)"
            else:
                k = "flipped dir"
        elif b:
            k = "skipped (no trade that day)"
        else:
            k = "new day"
        if k != "identical" and d not in rej_days:
            no_rej_diff.append((d, k))
        e = cat[k]
        e[0] += 1; e[1] += sum(x["pnl"] for x in b); e[2] += sum(x["pnl"] for x in c)
        e[3] += len(b); e[4] += len(c)
    return cat, no_rej_diff


def show_anatomy(cat, no_rej):
    tot_b = sum(v[1] for v in cat.values())
    tot_c = sum(v[2] for v in cat.values())
    for k in ("identical", "re-timed (same dir)", "flipped dir", "skipped (no trade that day)", "new day"):
        if k in cat:
            n, b, c, nb, nc = cat[k]
            print(f"        {k:28s} days {n:3d}  base {nb:3d} tr {b:+9.2f}  ->  cand {nc:3d} tr {c:+9.2f}   delta {c-b:+8.2f}")
    print(f"        total delta {tot_c - tot_b:+.2f};  differing days with NO gate rejection on their own range "
          f"(pure slot cascade): {len(no_rej)} {[str(d) + ' ' + k for d, k in no_rej][:6]}")


# --------------------------------------------------------------- 3. rejection anatomy
def rej_anatomy(rej, cand, base):
    ranges = collections.defaultdict(list)
    for r in rej:
        ranges[r["range_end"]].append(r)
    traded = {t["range_end"] for t in cand}
    base_r = {t["range_end"]: t for t in base}
    n_touch = len(rej)
    by_state = collections.Counter("NEUTRAL" if r["trend"] == 0 else "AGAINST" for r in rej)
    retimed = sum(1 for re in ranges if re in traded)
    died = len(ranges) - retimed
    died_base = [base_r[re]["pnl"] for re in ranges if re not in traded and re in base_r]
    # which baseline entries does the gate reject at their own entry bar?
    bs = collections.defaultdict(list)
    for t in base:
        bs[cls(t["trend"], t["dir"])].append(t["pnl"])
    bstr = ", ".join(f"{k} n={len(v)} win={100*np.mean(np.array(v) > 0):.0f}% net {sum(v):+.2f}" for k, v in sorted(bs.items()))
    return (f"rejected touches {n_touch} ({dict(by_state)}) on {len(ranges)} ranges -> {retimed} later traded, "
            f"{died} never traded (of those, {len(died_base)} were baseline trades worth {sum(died_base):+.2f})\n"
            f"        baseline entries by own-bar state (sim-static buckets): {bstr}")


# --------------------------------------------------------------- 5. cascade-free control
def shrink_non_with(ctx):
    base = v115_size(ctx)
    return 0.01 if ctx["trend"] != ctx["dir"] else base


def real_shrink(trend, bars):
    """Re-derive the real Final list (already at v1.15 sizing) with non-WITH
    trades at 0.01, using real_resize.py's leg arithmetic: a 0.01 trade = the
    final leg's move x 1 unit.  Trades already at 0.01 are unchanged."""
    T = round_trips(load_deals(FINAL))
    tb = bars["time"].values
    usd0 = usd1 = zar0 = zar1 = 0.0
    e0, e1 = [], []
    for t in T:
        k = int(np.searchsorted(tb, np.datetime64(t["entry_time"].replace(second=0))))
        c = cls(int(trend[k]), t["side"])
        u, z = t["pnl_usd"], t["profit_ccy"]
        if c != "WITH" and t["vol"] > 0.015:
            fl = t["legs"][-1]
            units = round(fl["vol"] / 0.01)
            u = (fl["price"] - t["entry"]) * t["side"]
            z = fl["profit"] / units
        usd0 += t["pnl_usd"]; zar0 += t["profit_ccy"]; usd1 += u; zar1 += z
        e0.append(t["profit_ccy"]); e1.append(z)

    def pf(x):
        x = np.array(x); return x[x > 0].sum() / -x[x < 0].sum()

    def dd(x):
        e = np.cumsum(x); return (np.maximum.accumulate(np.concatenate([[0], e]))[1:] - e).max()
    print(f"   real Final list re-derived: net {zar0:.2f} -> {zar1:.2f} ZAR ({zar1-zar0:+.2f}), USD {usd0:.2f} -> {usd1:.2f}, "
          f"PF {pf(e0):.3f} -> {pf(e1):.3f}, closed-trade maxDD {dd(e0):.0f} -> {dd(e1):.0f} ZAR")


# --------------------------------------------------------------- 6. jitter sensitivity
def jitter(trend_info, bars, trend, base_by_sym):
    ctx = trend_info["ctx"]
    m5 = trend_info["m5"]
    c = ctx["close"]
    gaps = np.vstack([c - ctx["m2400"], ctx["m21"] - ctx["m50"], ctx["m50"] - ctx["m150"], ctx["m150"] - ctx["m600"]])
    with np.errstate(invalid="ignore"), __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore")
        mingap = np.nanmin(np.abs(gaps), axis=0)
    idx = trend_info["idx"]
    for sym, tr in base_by_sym.items():
        ks = [int(np.searchsorted(bars["time"].values.astype("datetime64[s]").astype(np.int64), t["t"])) for t in tr]
        close = [mingap[idx[k]] for k in ks]
        print(f"   {sym}: baseline entries whose M5 decision bar has any MA/price gap < 0.05 (could flip on the "
              f"GOLD/GOLD# +-0.02 offset jitter): {sum(x < 0.05 for x in close)} of {len(ks)}")


if __name__ == "__main__":
    n_null = int(sys.argv[sys.argv.index("--null") + 1]) if "--null" in sys.argv else 0
    bars = load_bars()
    trend, info = aurelius_alignment(bars, return_m5=True)
    TREND = trend
    static_final(trend, bars)

    print("\n1-3) SEQUENTIAL sim, baseline v1.16 (v1.15 sizing) vs Aurelius gate  (USD, 0.03/0.01 lots, slippage on)")
    base_all = {}
    for sym in SYMS:
        for per in PER_ORDER:
            base, _ = run(bars, sym, per)
            if per == "2026":
                base_all[sym] = base
            sb = stats(base)
            print(f"\n== {sym} {per}: BASE n={sb['n']} net {sb['net']:.2f} PF {sb['pf']:.2f} win {sb['win']}% DD {sb['maxdd']:.0f}")
            for label, kw in (("WITH only", dict(trend_gate="with")),
                              ("not AGAINST", dict(trend_gate="not_against")),
                              ("WITH only + KILL range", dict(trend_gate="with", trend_kill=True))):
                cand, rej = run(bars, sym, per, trend_arr=trend, **kw)
                sc = stats(cand)
                same = [(x["t"], x["dir"]) for x in base] == [(x["t"], x["dir"]) for x in cand]
                print(f"   {label:24s} n={sc['n']:3d} net {sc['net']:8.2f} ({sc['net']-sb['net']:+8.2f}) PF {sc['pf']:.2f} "
                      f"win {sc['win']}% DD {sc['maxdd']:.0f}  same sequence: {same}")
                if label != "WITH only + KILL range":
                    cat, no_rej = anatomy(base, cand, rej)
                    show_anatomy(cat, no_rej)
                    print("        " + rej_anatomy(rej, cand, base))

    print("\n4b) COUNT-MATCHED NULL (valid only because the gate does not cascade - section 2): "
          "random same-size subsets of the baseline trades, 20,000 draws")
    rng0 = np.random.default_rng(7)
    for sym in SYMS:
        for per in PER_ORDER:
            base, _ = run(bars, sym, per)
            keep = np.array([t["trend"] == t["dir"] for t in base])
            pn = np.array([t["pnl"] for t in base])
            obs = pn[keep].sum()
            pos = lambda x: x[x > 0].sum() / max(1e-9, -x[x < 0].sum())
            draws = [rng0.choice(len(pn), keep.sum(), replace=False) for _ in range(20000)]
            nul = np.array([pn[d].sum() for d in draws])
            nul_pf = np.array([pos(pn[d]) for d in draws])
            print(f"   {sym:5s} {per:7s} WITH subset {keep.sum():2d}/{len(pn)}: net {obs:+8.2f} PF {pos(pn[keep]):.2f} | random same-size: "
                  f"net mean {nul.mean():+8.2f}, p(random net >= WITH) = {(nul >= obs).mean():.3f}, "
                  f"p(random PF >= WITH) = {(nul_pf >= pos(pn[keep])).mean():.3f}")

    print("\n5) CASCADE-FREE CONTROL: shrink non-WITH setups to 0.01 (on top of v1.15), sequential")
    for sym in SYMS:
        cells = []
        for per in PER_ORDER:
            base, _ = run(bars, sym, per)
            cand, _ = run(bars, sym, per, trend_arr=trend, size_fn=shrink_non_with)
            assert [x["t"] for x in base] == [x["t"] for x in cand]
            sb, sc = stats(base), stats(cand)
            cells.append(f"{per} {sc['net']-sb['net']:+7.2f} (PF {sb['pf']:.2f}->{sc['pf']:.2f}, DD {sb['maxdd']:.0f}->{sc['maxdd']:.0f})")
        print(f"   {sym:5s} " + " | ".join(cells))
    real_shrink(trend, bars)

    print("\n6) GOLD vs GOLD# alignment jitter")
    jitter(info, bars, trend, base_all)

    if n_null:
        print(f"\n4) NULL: WITH-only gate driven by the real state series circularly shifted by a random offset "
              f"(>= 5 trading days), {n_null} draws, GOLD")
        rng = np.random.default_rng(20260923)
        for per in PER_ORDER:
            base, _ = run(bars, "GOLD", per)
            sb = stats(base)
            sr = stats(run(bars, "GOLD", per, trend_gate="with")[0])
            obs, obs_pf = sr["net"] - sb["net"], sr["pf"]
            null, null_pf, null_n = [], [], []
            for _ in range(n_null):
                sh = int(rng.integers(7200, len(trend) - 7200))
                s = stats(run(bars, "GOLD", per, trend_arr=np.roll(trend, sh), trend_gate="with")[0])
                null.append(s["net"] - sb["net"]); null_pf.append(s["pf"]); null_n.append(s["n"])
            null, null_pf = np.array(null), np.array(null_pf)
            print(f"   {per:7s}: real gate keeps {sr['n']}/{sb['n']} trades, net delta {obs:+8.2f} PF {obs_pf:.2f} | shifted gates keep "
                  f"{np.mean(null_n):.1f} on average, delta mean {null.mean():+8.2f} "
                  f"[5..95%: {np.percentile(null, 5):+.2f} .. {np.percentile(null, 95):+.2f}], PF median {np.median(null_pf):.2f} | "
                  f"p(shifted net >= real) = {(null >= obs).mean():.3f}, p(shifted PF >= real) = {(null_pf >= obs_pf).mean():.3f}")
