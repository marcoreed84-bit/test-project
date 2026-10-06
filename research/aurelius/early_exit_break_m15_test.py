"""
Aurelius M15 version of the early-exit-on-break test (research/aurelius/
early_exit_break_test.py = Aurelius M5, research/meridian/
early_exit_break_test.py = Meridian) - per the user's request to check
every EA. Same engine.py/sim.py code as Aurelius M5, just E.P15 params on
E.load_m15_native() real M15 data - the same construction
aurelius_m15_v160_bar_match_check.py already validated this pairing with.

RULE: identical to the other three (Meridian/Aurelius M5/Ratchet) -
same 0.30xATR touch tolerance, same "next bar must bounce back above/
below BOTH EMAs or exit now" logic, no re-tuning per EA/timeframe.
"""
import sys

sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from engine import P15
from sim import simulate

RETEST_TOL_ATR = 0.30


def make_early_exit_fn(ctx):
    c, m21, m50, atr = ctx["close"], ctx["m21"], ctx["m50"], ctx["atr"]

    def fn(ctx_, i, is_buy, entry_i, entry_px):
        d = 1 if is_buy else -1
        touched_i = None
        for k in range(entry_i + 1, i + 1):
            a = atr[k]
            if not (a > 0):
                continue
            if touched_i is None:
                tol = RETEST_TOL_ATR * a
                if (abs(c[k] - m21[k]) <= tol) or (abs(c[k] - m50[k]) <= tol):
                    touched_i = k
                continue
            bounced = (c[k] > m21[k] and c[k] > m50[k]) if d > 0 else (c[k] < m21[k] and c[k] < m50[k])
            broke = (c[k] < m21[k] and c[k] < m50[k]) if d > 0 else (c[k] > m21[k] and c[k] > m50[k])
            if bounced:
                return False
            if broke:
                return k == i
        return False
    return fn


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([t["pnl"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  avg={pnl.mean():7.3f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    for r, cnt in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


if __name__ == "__main__":
    df = E.load_m15_native()
    h4 = E.load_h4()
    print(f"Real GOLD M15: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({len(df)} bars)")
    ctx = E.build_context(df, h4, P15)
    cutoff_i = int(len(df) * 0.70)
    print(f"Walk-forward cutoff (70%): {df['time'].iloc[cutoff_i]}\n")

    real_trades = simulate(ctx, params=P15)
    cand_trades = simulate(ctx, params=P15, extra_exit=make_early_exit_fn(ctx), extra_exit_reason="EARLY_EXIT_BROKE")
    for t in real_trades + cand_trades:
        if "pnl" not in t:
            t["pnl"] = (t["exit_px"] - t["entry_px"]) * t["dir"]

    print(f"{'='*92}\nCANDIDATE: shipped Aurelius M15 + early-exit-on-break rule\n{'='*92}")
    for label, trs in (("IN-SAMPLE (first 70%)", [t for t in cand_trades if t["entry_i"] < cutoff_i]),
                        ("OUT-OF-SAMPLE (last 30%)", [t for t in cand_trades if t["entry_i"] >= cutoff_i])):
        report(label, trs)

    print(f"\n{'='*92}\nFor reference: shipped Aurelius M15 (no early-exit rule)\n{'='*92}")
    for label, trs in (("IN-SAMPLE (first 70%)", [t for t in real_trades if t["entry_i"] < cutoff_i]),
                        ("OUT-OF-SAMPLE (last 30%)", [t for t in real_trades if t["entry_i"] >= cutoff_i])):
        report(label, trs)
