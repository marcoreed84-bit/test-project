"""
Divergence-exit screen (2026-09-23) for Aurelius_EA.mq5 (M5) and
Aurelius_M15_EA.mq5 (M15) - see research/divergence.py's module docstring for
the full construction (swing-pivot definition, RSI/MACD/Stochastic
constructions, why each oscillator is built the way it is).

Tests each of RSI(14), MACD histogram (reusing engine.py's own InpUseMomentum
construction via ctx["macd_hist"]) and Stochastic(14,3) (reusing
stoch_speed_test.py's stochastic()) as an OPTIONAL EARLY-EXIT trigger layered
on top of each file's real, currently-shipped baseline (engine.P / engine.P15,
same defaults candidate_ablation_test.py used) - via sim.py's new extra_exit
hook, checked first in the exit-priority chain (before Price21/VWAP/
ALIGN_BREAK), matching the user's own framing: does this catch the reversal
BEFORE the slower existing exits would. No entry logic, no other exit, and no
input default is touched - this only adds a same-position-only, non-lookahead
extra exit trigger to sim.py's already-validated OnTick port.

IS/OOS split: same 70/30 convention as stoch_speed_test.py's own run()
(cutoff = int(n*0.7) on bar index, i.e. calendar-ordered, no shuffling).

Data/caveats: identical to candidate_ablation_test.py - real GOLD# M5 export
(2023.01.03-2026.08.14), M15 resampled losslessly from it, price-unit net (no
compounding, no account currency), NOT the live GOLD account any real MT5
confirmation in this file's header ran on.
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "..")
import numpy as np
import engine as E
import sim as S
import divergence as D


def run(ctx, params, label, extra_exit=None):
    trades = S.simulate(ctx, params=params, extra_exit=extra_exit)
    n = ctx["n"]
    cutoff = int(n * 0.7)
    full = S.stats(trades)
    rk = S.risk_stats(trades, ctx)
    is_trades = [t for t in trades if t["entry_i"] < cutoff]
    oos_trades = [t for t in trades if t["entry_i"] >= cutoff]
    ist = S.stats(is_trades)
    oost = S.stats(oos_trades)
    n_div_exits = sum(1 for t in trades if t["reason"] == "DIVERGENCE")

    def pf_str(st):
        return f"{st['pf']:.4f}" if st.get("n") and st["pf"] != float("inf") else ("inf" if st.get("n") else "n/a")

    print(f"  {label}")
    print(f"    FULL n={full.get('n',0):4d} net=${full.get('net',0):10.2f} pf={pf_str(full):>7s} "
          f"closedDD=${rk['closed_dd']:8.2f} floatDD=${rk['float_dd']:8.2f} div_exits={n_div_exits}")
    print(f"    IS   n={ist.get('n',0):4d} net=${ist.get('net',0):10.2f} pf={pf_str(ist):>7s}   "
          f"OOS  n={oost.get('n',0):4d} net=${oost.get('net',0):10.2f} pf={pf_str(oost):>7s}")
    return full, rk


def make_exit(bear, bull):
    def f(ctx, i, is_buy, entry_i, entry_px):
        return bool(bear[i]) if is_buy else bool(bull[i])
    return f


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    print(f"M5 bars: {len(df5)}  range {df5['time'].iloc[0]} .. {df5['time'].iloc[-1]}")

    # ================= M5 (Aurelius_EA.mq5) =================
    print("\n=== M5 (Aurelius_EA.mq5) divergence-exit screen ===")
    ctx5 = E.build_context(df5, h4, params=E.P)
    sigs5 = D.all_divergence_signals(ctx5["high"], ctx5["low"], ctx5["close"], n=5,
                                      macd_hist=ctx5["macd_hist"])

    run(ctx5, E.P, "baseline (no divergence exit, shipped v1.46)")
    for name in ("rsi", "macd", "stoch"):
        bear, bull = sigs5[name]
        run(ctx5, E.P, f"+ {name.upper()} regular-divergence exit (n=5 pivot)", extra_exit=make_exit(bear, bull))

    # ================= M15 (Aurelius_M15_EA.mq5) =================
    print("\n=== M15 (Aurelius_M15_EA.mq5) divergence-exit screen ===")
    df15 = E.resample_m15_from_m5(df5)
    print(f"M15 bars (resampled): {len(df15)}  range {df15['time'].iloc[0]} .. {df15['time'].iloc[-1]}")
    ctx15 = E.build_context(df15, h4, params=E.P15)
    sigs15 = D.all_divergence_signals(ctx15["high"], ctx15["low"], ctx15["close"], n=5,
                                       macd_hist=ctx15["macd_hist"])

    run(ctx15, E.P15, "baseline (no divergence exit, shipped v1.52)")
    for name in ("rsi", "macd", "stoch"):
        bear, bull = sigs15[name]
        run(ctx15, E.P15, f"+ {name.upper()} regular-divergence exit (n=5 pivot)", extra_exit=make_exit(bear, bull))
