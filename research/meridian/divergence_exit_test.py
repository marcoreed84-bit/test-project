"""
Divergence-exit screen (2026-09-23) for Meridian_EA.mq5 (v1.03) - see
research/divergence.py's module docstring for the full construction
(swing-pivot definition, RSI/MACD/Stochastic constructions).

Tests each of RSI(14), MACD histogram (standalone 12/26/9, since Meridian has
no MACD of its own - see divergence.py's macd_histogram()) and Stochastic
(14,3) (stoch_speed_test.py's own construction) as an OPTIONAL EARLY-EXIT
trigger layered on top of the real, currently-shipped v1.02 baseline (M.V102),
via msim.py's existing exit_fn hook (f(ctx, t, pos) -> reason or None,
checked at bar open, ahead of TrailStop/breakeven manage_fn and right after
the REVERSAL-cross/Friday-flatten checks - i.e. as early as this simulator's
event order allows a signal-based exit to run). No entry logic, no other
exit, and no input default is touched.

Periods: same four-period convention as candidates.py (2023/2024/2025/2026,
2026 = the real-report window) - single DETERMINISTIC run per period (no
entry_noise/sl_slip), NOT candidates.py's full 24-seed Monte Carlo, given the
time budget for this screen; noted explicitly as a simplification, not hidden.
If a candidate here looks promising enough to pursue, it should get the full
MC treatment candidates.py's own adoption bar requires before being taken
seriously - this is a first-pass screen only, and none of the three below
survives even this simpler pass (see the .mq5 header note this script's
results feed).

Data/caveats: identical to candidates.py / msim.py's own docstrings - real
GOLD# M5 export (2022-06-27..2026-09-18), price-unit net.
"""
import sys
from dataclasses import replace

import pandas as pd

sys.path.insert(0, "/home/user/test-project/research")
sys.path.insert(0, "/home/user/test-project/research/meridian")
import divergence as D   # noqa: E402
import msim as M         # noqa: E402

PERIODS = [("2023", "2023-01-02", "2024-01-01"), ("2024", "2024-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01"), ("2026", "2026-01-01", "2026-09-21")]
BASE = M.V102


def make_exit(bear, bull):
    def f(ctx, t, pos):
        i = t - 1
        if i < 0:
            return None
        sig = bear[i] if pos["dir"] > 0 else bull[i]
        return "DIVERGENCE" if sig else None
    return f


if __name__ == "__main__":
    ctx = M.build_ctx()
    h, l, c = ctx["h"], ctx["l"], ctx["c"]
    print(f"M5 bars: {len(c)}  range {ctx['t64'][0]} .. {ctx['t64'][-1]}")

    sigs = D.all_divergence_signals(h, l, c, n=5)  # macd_hist=None -> standalone 12/26/9 build

    cands = {"baseline (v1.02, no divergence exit)": BASE}
    for name in ("rsi", "macd", "stoch"):
        bear, bull = sigs[name]
        cands[f"+ {name.upper()} divergence exit (n=5 pivot)"] = replace(BASE, exit_fn=make_exit(bear, bull))

    res = {}
    for label, p in cands.items():
        rows = []
        for per, a, b in PERIODS:
            trades, _stats = M.simulate(ctx, p, start=pd.Timestamp(a), end=pd.Timestamp(b))
            st = M.stats_of(trades)
            n_div = sum(1 for t in trades if t.get("reason") == "DIVERGENCE")
            rows.append((per, st["n"], st["net"], st["pf"], st["closed_dd"], n_div))
        res[label] = rows
        base_rows = res["baseline (v1.02, no divergence exit)"]
        line = " | ".join(
            f"{r[0]} n{r[1]:4d} ${r[2]:8.2f} PF{(r[3] if r[3] != float('inf') else 99.0):.3f} DD{r[4]:6.2f}"
            + ("" if label.startswith("baseline") else f" ({r[2]-br[2]:+.2f}, div_exits={r[5]})")
            for r, br in zip(rows, base_rows)
        )
        tot = sum(r[2] for r in rows)
        btot = sum(r[2] for r in base_rows)
        print(f"{label:<44} {line}")
        if not label.startswith("baseline"):
            wins = sum(r[2] > br[2] for r, br in zip(rows, base_rows))
            print(f"{'':<44} -> 4-period net {tot-btot:+.2f}, periods better {wins}/4")
