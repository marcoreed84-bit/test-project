"""
Step 3: candidate improvements, every one evaluated by FULL SEQUENTIAL
re-simulation (single position slot, real bar order) - never by removing or
re-weighting trades from a fixed baseline list.

Periods:
  HOLDOUT  2025-11-12 .. 2025-12-31  never used by ANY calibration in this
                                     project (every real report starts 2026-01-01)
  IS       2026-01-01 .. 2026-05-31
  OOS      2026-06-01 .. 2026-09-18
Symbols: GOLD (what account 382043238 tests on - primary) and GOLD# (robustness).
"""
import sys
import random
from dataclasses import replace

import numpy as np

sys.path.insert(0, "/home/user/test-project/research/msg")
from sim import load_bars, simulate, stats, Params  # noqa: E402

SLIP = dict(slip_entry=0.083, slip_sl=0.223)
SYM = {"GOLD": dict(bid_off=-0.12, ask_extra=0.16), "GOLD#": dict(bid_off=0.0, ask_extra=0.04)}
PERIODS = {"HOLDOUT": ("2025-11-12", "2026-01-01"), "IS": ("2026-01-01", "2026-06-01"),
           "OOS": ("2026-06-01", "2026-09-22"), "2026": ("2026-01-01", "2026-09-22")}


def base_params(sym="GOLD", **kw):
    return Params(**SYM[sym], **SLIP, **kw)


def evaluate(bars, cand_kw, sym="GOLD", base_kw=None):
    base_kw = base_kw or {}
    out = {}
    for per, (a, b) in PERIODS.items():
        tb, _ = simulate(bars, base_params(sym, start=a, end=b, **base_kw))
        tc, _ = simulate(bars, base_params(sym, start=a, end=b, **cand_kw))
        out[per] = (stats(tb), stats(tc))
    return out


def show(label, res):
    cells = []
    for per in ("HOLDOUT", "IS", "OOS", "2026"):
        b, c = res[per]
        cells.append(f"{per}: {c['net'] - b['net']:+8.2f} (PF {b['pf']:.2f}->{c['pf']:.2f}, n {b['n']}->{c['n']}, DD {b['maxdd']:.0f}->{c['maxdd']:.0f})")
    print(f"{label:34s} " + " | ".join(cells))


# ------------------------------------------------------------------ candidates
def dz(ctx, lo=0.18, hi=0.26):
    return lo <= ctx["risk_pct"] <= hi


def size_deadzone(lots_in):
    return lambda ctx: lots_in if dz(ctx) else 0.03


def min_range_filter(pct):
    # reject when the frozen session range is < pct % of price
    return lambda ctx: ctx["rng"] / ctx["close1"] * 100.0 < pct


def min_hours_after(hours):
    return lambda ctx: (ctx["bar_t"] - ctx["S"].end_t) / 3600.0 < hours


def risk_prop_size(target_risk_usd):
    # constant $ risk per trade: lots = target / (risk_points * 100), floored at 0.01
    def f(ctx):
        risk_pts = abs(ctx["fill"] - ctx["sl"])
        return max(0.01, round(target_risk_usd / (risk_pts * 100.0), 2))
    return f


CANDIDATES = {
    "A dead-zone SKIP (v1.13)": dict(skip_dead=True),
    "B dead-zone size 0.02": dict(size_fn=size_deadzone(0.02)),
    "B dead-zone size 0.01": dict(size_fn=size_deadzone(0.01)),
    "C min range 0.30%": dict(entry_filter=min_range_filter(0.30)),
    "C min range 0.40%": dict(entry_filter=min_range_filter(0.40)),
    "C min range 0.50%": dict(entry_filter=min_range_filter(0.50)),
    "E entry >= 1h after range": dict(entry_filter=min_hours_after(1.0)),
    "E entry >= 2h after range": dict(entry_filter=min_hours_after(2.0)),
    "G weekend guard as intended": dict(weekend_guard_mode="intended"),
    "I lock 0.5R": dict(trail=0.5),
    "I lock 1.25R": dict(trail=1.25),
    "I TP3 2.5R": dict(tp3=2.5),
    "I no post-TP2 lock": dict(lock_mode="none"),
}


if __name__ == "__main__":
    bars = load_bars()
    sym = sys.argv[1] if len(sys.argv) > 1 else "GOLD"
    print(f"=== symbol {sym}: net delta vs v1.14 baseline, per period (USD at 0.03 lots)")
    for name, kw in CANDIDATES.items():
        show(name, evaluate(bars, kw, sym))
