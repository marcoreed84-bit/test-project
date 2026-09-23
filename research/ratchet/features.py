"""
Step 5 (exploration only - nothing here is a verdict): which entry-time
features separate Ratchet's good and bad pullback entries CONSISTENTLY across
years, rather than in one window? Candidates are only promoted to candidates.py
(the sequential-simulator test) if the sign holds in every period.

Trade lists: the momentum-OFF / wick-ON config (the best corner in
decompose.py/momentum_test.py), deterministic execution ('none' mode), each
calendar year 2023/2024/2025 + the 2026 window. For 2026 the REAL Backtest_2
pullback trades (bar-matched kind) are shown alongside.

Features (all known at the entry bar's open, shift 1 = the signal bar):
  age     - bars the full 21>50>150>600 + price-vs-2400 stack has been
            continuously aligned (momentum entries are by construction age<=8,
            and real momentum entries lost at PF 0.44 - is "young alignment"
            the real culprit, for pullback entries too?)
  atr_pct - ATR percentile vs its own trailing 2,000 bars
  dist21  - |close - EMA21| / ATR at the signal bar
  hour    - server hour
  prev    - previous trade's P/L sign
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import noise as N   # noqa: E402
import report as R  # noqa: E402
import sim as S     # noqa: E402

PERIODS = [("2023", "2023-01-02", "2024-01-01"), ("2024", "2024-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01"), ("2026", "2026-01-01", "2026-09-21")]


def align_age(ctx):
    out = {}
    for k in ("al_up", "al_dn"):
        a = ctx[k]
        age = np.zeros(len(a), dtype=int)
        run = 0
        for i in range(len(a)):
            run = run + 1 if a[i] else 0
            age[i] = run
        out[k] = age
    return out


def atr_pct(ctx, win=2000):
    s = pd.Series(ctx["atr"])
    return s.rolling(win, min_periods=200).rank(pct=True).values


def features(ctx, trades, ages, ap):
    rows = []
    prev = 0.0
    for x in trades:
        t = x["entry_i"]
        s = t - 1
        d = x["dir"]
        rows.append(dict(pnl=x["pnl"], age=(ages["al_up"] if d > 0 else ages["al_dn"])[s],
                         atr_pct=ap[s], dist21=abs(ctx["c"][s] - ctx["m21"][s]) / ctx["atr"][s],
                         hour=ctx["hour"][t], prev=np.sign(prev), kind=x.get("kind")))
        prev = x["pnl"]
    return pd.DataFrame(rows)


def bucket_table(df, col, bins, label):
    df = df.copy()
    df["b"] = pd.cut(df[col], bins)
    g = df.groupby("b", observed=True).pnl
    out = pd.DataFrame(dict(n=g.size(), net=g.sum().round(1),
                            pf=g.apply(lambda p: p[p > 0].sum() / max(1e-9, -p[p < 0].sum())).round(2)))
    return out.rename(columns=lambda c: f"{label}_{c}")


if __name__ == "__main__":
    ctx, noise = N.get_ctx()
    ages, ap = align_age(ctx), atr_pct(ctx)
    p = replace(S.SHIPPED, momentum=False, sl_slip=np.array([noise["usd"][1].mean()]), noise_in_atr=False)
    sets = {}
    for name, a, b in PERIODS:
        tr, _ = S.simulate(ctx, p, start=pd.Timestamp(a), end=pd.Timestamp(b))
        sets[name] = features(ctx, tr, ages, ap)
    # real Backtest_2, pullback-kind trades, real P/L (USD)
    simt, _ = S.simulate(ctx, S.SHIPPED)
    sk = {N.key(t["entry_time"]): t for t in simt}
    rr = []
    for r in R.load(R.RATCHET_BT2):
        s = sk.get(N.key(r["entry_time"]))
        if s is not None:
            rr.append(dict(s, pnl=r["pnl_usd"]))
    real = features(ctx, rr, ages, ap)
    sets["REAL26 all"] = real
    sets["REAL26 pb"] = real[real.kind == "pullback"]
    sets["REAL26 mom"] = real[real.kind == "momentum"]

    for col, bins in [("age", [0, 8, 24, 72, 288, 100000]), ("atr_pct", [0, .25, .5, .75, 1.0]),
                      ("dist21", [0, .25, .5, .75, 1.0, 10]), ("hour", [0, 7, 12, 16, 20, 24]),
                      ("prev", [-2, -0.5, 0.5, 2])]:
        print(f"\n===== {col}")
        tabs = [bucket_table(df, col, bins, k.replace(' ', '')) for k, df in sets.items()]
        print(pd.concat(tabs, axis=1).to_string())
