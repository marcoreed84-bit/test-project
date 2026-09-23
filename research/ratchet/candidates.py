"""
Step 6: candidate improvements, judged ONLY by the sequential simulator.

Base = the momentum-OFF / wick-ON corner (the momentum verdict, see
momentum_test.py). Every candidate runs through sim.py's full single-position
state machine (cooldown, 3-loss breaker, session/Friday rules), so any
cascade - a skipped entry freeing the slot for a later, different setup, or
changing the breaker's loss streak - is part of the result, not ignored.

Adoption bar, fixed BEFORE running (same discipline as MSG v1.15):
  * mean net (24 ATR-scaled noise seeds) better than base in at least 3 of
    the 4 periods (2023, 2024, 2025 - all out-of-sample for the simulator -
    and the 2026 real-report window), AND
  * better than base in 2026 under ALL THREE execution models
    ('none', 'usd', 'atr'), AND
  * closed-trade drawdown not worse on the 4-period total.
Anything short of that is reported, not shipped.

Candidates:
  atrpct<q  - skip an entry when ATR(14) sits below its own q-th percentile
              of the trailing 2,000 bars (~7 trading days). Only feature in
              features.py whose weakest bucket is weakest-or-2nd-weakest in
              all four periods AND in the real 2026 pullback trades.
              Mechanism: spread + slippage are ~fixed dollars, so in a quiet
              tape they are a bigger fraction of the ATR-scaled trail/BE
              geometry every exit here is built from.
  keep_prog - give-back trail keeps 0.30 of the peak until the peak reaches
              X ATR, then keeps Y. Aimed straight at paradox.py's finding
              that ~54% of BOTH real max-equity-drawdowns is one trade handing
              back 70% of a +4,200 ZAR float. NOT the v3.18 rejected cap
              (a hard max give-back DISTANCE, which also bit small moves) -
              this only changes behavior on the rare runners.
  brk48     - consecutive-loss breaker sits out 48 bars instead of 24 (the
              rest of paradox.py's episode is 6 weeks of Feb-Mar chop).
"""
import sys
from dataclasses import replace
from functools import partial

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import noise as N   # noqa: E402
import sim as S     # noqa: E402

PERIODS = [("2023", "2023-01-02", "2024-01-01"), ("2024", "2024-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01"), ("2026", "2026-01-01", "2026-09-21")]


def _atr_pct(ctx, win=2000):
    if "atr_pct" not in ctx:
        ctx["atr_pct"] = pd.Series(ctx["atr"]).rolling(win, min_periods=200).rank(pct=True).values
    return ctx["atr_pct"]


def f_atrpct(ctx, t, d, kind, q):
    v = _atr_pct(ctx)[t - 1]
    return not (v < q)


def keep_prog(pos, x_atr, keep_hi):
    pf = (pos["peak"] - pos["entry"]) * pos["dir"]
    return keep_hi if pf >= x_atr * pos["atr"] else 0.30


BASE = replace(S.SHIPPED, momentum=False)
CANDS = {
    "base (mom OFF, wick ON)": BASE,
    "atrpct<0.25": replace(BASE, entry_filter=partial(f_atrpct, q=0.25)),
    "atrpct<0.15": replace(BASE, entry_filter=partial(f_atrpct, q=0.15)),
    "keep_prog 3ATR->0.50": replace(BASE, keep_fn=partial(keep_prog, x_atr=3.0, keep_hi=0.50)),
    "keep_prog 5ATR->0.60": replace(BASE, keep_fn=partial(keep_prog, x_atr=5.0, keep_hi=0.60)),
    "brk48": replace(BASE, breaker_bars=48),
}


if __name__ == "__main__":
    only = sys.argv[1:] or list(CANDS)
    res = {}
    for name in ["base (mom OFF, wick ON)"] + [c for c in only if c != "base (mom OFF, wick ON)"]:
        p = CANDS[name]
        rows = []
        for per, a, b in PERIODS:
            df = N.mc(p, start=pd.Timestamp(a), end=pd.Timestamp(b))
            rows.append((per, df.n.mean(), df.net.mean(), df.pf.mean(), df.closed_dd.mean()))
        for mode in ("none", "usd"):
            df = N.mc(p, mode=mode)
            rows.append((f"2026/{mode}", df.n.mean(), df.net.mean(), df.pf.mean(), df.closed_dd.mean()))
        res[name] = rows
        b = res["base (mom OFF, wick ON)"]
        line = " | ".join(f"{r[0]} n{r[1]:5.0f} ${r[2]:6.1f} PF{r[3]:.2f} DD{r[4]:5.1f}"
                          + ("" if name.startswith("base") else f" ({r[2]-br[2]:+.1f})")
                          for r, br in zip(rows, b))
        tot = sum(r[2] for r in rows[:4]); btot = sum(r[2] for r in b[:4])
        dd = sum(r[4] for r in rows[:4]); bdd = sum(r[4] for r in b[:4])
        wins = sum(r[2] > br[2] for r, br in zip(rows[:4], b[:4]))
        allm = all(r[2] > br[2] for r, br in zip(rows[3:], b[3:]))
        verdict = "" if name.startswith("base") else (
            f"  -> periods better {wins}/4, 2026 all 3 exec models better: {allm}, 4-period net {tot-btot:+.1f}, "
            f"DD {dd-bdd:+.1f}  => {'PASS' if (wins >= 3 and allm and dd <= bdd * 1.02) else 'FAIL'}")
        print(f"{name:<24} {line}{verdict}", flush=True)
