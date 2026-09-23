"""
Ablation of the currently-SHIPPED-but-individually-unconfirmed candidate
flags in Aurelius_EA.mq5 (M5) and Aurelius_M15_EA.mq5 (M15), run after two
fresh real MT5 confirmations (2026-09-22, live GOLD 382043238, 2023.01.01-
2026.09.21, 20000 ZAR) of the FULL current input stack on both files. Those
real runs confirm the stack works together; they say nothing about which
individual still-Python-only lever inside that stack is earning its keep.
This isolates each one against engine.py/sim.py, the existing direct port
of Aurelius_EA.mq5's OnTick()/CheckForEntry() gates (see those files'
module docstrings) - NOT the simplified trendline-breakout research
simulator used by the various vanguard_*_test.py scripts in this directory.

DATA CAVEAT (matches msim.py's own GOLD# vs GOLD caveat for Meridian): the
only bar data available in this container is the real GOLD# (demo account)
M5 export engine.py already documents (2023.01.03 - 2026.08.14, tick_volume
real). This is NOT the live GOLD account the two new real confirmations
ran on, and it does not reach 2026.09.21. Every net/PF/drawdown number below
is therefore useful for RANKING which of these levers helps, hurts, or does
nothing relative to the others - not for predicting the live-GOLD ZAR
magnitude of any of them. All figures are also in raw price-unit terms (one
0.01-lot-equivalent, no compounding, no account currency conversion) per
sim.py's own risk_stats() docstring, matching the "$" convention already
used by every other CANDIDATE UNDER TEST entry in both .mq5 headers.

Window actually used: the full available GOLD# M5 range after warmup,
2023.03 (warmup ~2450 bars into 2023.01.03) - 2026.08.14. This undershoots
the real confirmations' 2023.01.01-2026.09.21 window by about 5 weeks at the
end and excludes ~2 months of 2023 for indicator warmup; it is used as-is
rather than padded or extrapolated.

IMPORTANT CORRECTION vs the brief that requested this ablation: the brief
listed Aurelius_M15_EA.mq5's InpStopATR (2.5->1.5) as an unconfirmed-but-
shipped candidate. It is not - Aurelius_M15_EA.mq5's own header (v1.47/
v1.48) shows this was already proposed, real MT5 tested, and REJECTED
(reverted 1.5->2.5) on 2026-09-09; InpStopATR=2.5 is real-tested and left
out of this ablation for exactly that reason. The three M15 candidates
actually still Python-only per the header (CANDIDATE UNDER TEST /
"Python-only so far") are InpPullbackMA (PB_50->PB_21, v1.50),
InpMaxSlopeATR (1.00->1.25, v1.49), and InpUseSlopeSRBlock (true, v1.51) -
those three are what's ablated below.
"""
import sys
sys.path.insert(0, ".")
import engine as E
import sim as S


def run(ctx, params, label):
    trades = S.simulate(ctx, params=params)
    st = S.stats(trades)
    rk = S.risk_stats(trades, ctx)
    pf = st["pf"]
    pf_str = f"{pf:.4f}" if pf != float("inf") else "inf"
    print(f"  {label:52s} n={st['n']:4d} net=${st['net']:10.2f} pf={pf_str:>7s} "
          f"closedDD=${rk['closed_dd']:8.2f} floatDD=${rk['float_dd']:8.2f}")
    return st, rk


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()

    print(f"M5 bars: {len(df5)}  range {df5['time'].iloc[0]} .. {df5['time'].iloc[-1]}")
    print(f"H4 bars: {len(h4)}  range {h4['time'].iloc[0]} .. {h4['time'].iloc[-1]}")

    # ================= M5 (Aurelius_EA.mq5) =================
    # None of the three M5 candidates (min_slope_atr, use_price21_exit,
    # use_vwap_exit) feed build_context() - all three are read only inside
    # sim.simulate()'s gate/exit chain - so one context build covers every
    # cell below.
    print("\n=== M5 (Aurelius_EA.mq5) candidate ablation ===")
    ctx5 = E.build_context(df5, h4, params=E.P)

    base5 = dict(E.P)
    run(ctx5, base5, "baseline (shipped: slope=0.40, P21exit=on, VWAPexit=on)")

    v = dict(base5); v["min_slope_atr"] = 0.50
    run(ctx5, v, "revert InpMinSlopeATR only  (0.40 -> 0.50)")

    v = dict(base5); v["use_price21_exit"] = False
    run(ctx5, v, "revert InpUsePrice21Exit only (on -> off)")

    v = dict(base5); v["use_vwap_exit"] = False
    run(ctx5, v, "revert InpUseVwapExit only (on -> off)")

    v = dict(base5)
    v["min_slope_atr"] = 0.50
    v["use_price21_exit"] = False
    v["use_vwap_exit"] = False
    run(ctx5, v, "revert ALL THREE (pre-candidate v1.45 baseline)")

    # ================= M15 (Aurelius_M15_EA.mq5) =================
    # InpPullbackMA feeds build_context() (selects which MA the pullback
    # touch/tolerance test reads) - two context builds needed, one per
    # pullback_ma value. InpMaxSlopeATR and InpUseSlopeSRBlock are both
    # sim.simulate()-only gates and share whichever context matches their
    # cell's pullback_ma value.
    print("\n=== M15 (Aurelius_M15_EA.mq5) candidate ablation ===")
    df15 = E.resample_m15_from_m5(df5)
    print(f"M15 bars (resampled): {len(df15)}  range {df15['time'].iloc[0]} .. {df15['time'].iloc[-1]}")

    base15 = dict(E.P15)
    ctx15_pb21 = E.build_context(df15, h4, params=base15)          # pullback_ma="21" (shipped)
    pb50 = dict(base15); pb50["pullback_ma"] = "50"
    ctx15_pb50 = E.build_context(df15, h4, params=pb50)             # pullback_ma="50" (reverted)

    run(ctx15_pb21, base15,
        "baseline (shipped: PB_21, maxslope=1.25, slopeSRblock=on)")

    run(ctx15_pb50, pb50,
        "revert InpPullbackMA only (PB_21 -> PB_50)")

    v = dict(base15); v["max_slope_atr"] = 1.00
    run(ctx15_pb21, v, "revert InpMaxSlopeATR only (1.25 -> 1.00)")

    v = dict(base15); v["use_slope_sr_block"] = False
    run(ctx15_pb21, v, "revert InpUseSlopeSRBlock only (on -> off)")

    # interaction cell: InpMaxSlopeATR and InpUseSlopeSRBlock both read the
    # same per-bar slope/SR-distance values (slope_sr_block's own gate is
    # "slope >= 1.00 AND sr_dist >= 6.00", independent of InpMaxSlopeATR's
    # own single threshold, but a wider InpMaxSlopeATR admits more
    # high-slope candidates for slope_sr_block to then evaluate) - run both
    # reverted together and compare against the sum of the two solo deltas
    # to check additivity explicitly rather than assume it.
    v = dict(base15); v["max_slope_atr"] = 1.00; v["use_slope_sr_block"] = False
    run(ctx15_pb21, v, "revert MaxSlopeATR + SlopeSRBlock together (interaction check)")

    v = dict(base15)
    v["pullback_ma"] = "50"
    v["max_slope_atr"] = 1.00
    v["use_slope_sr_block"] = False
    run(ctx15_pb50, v, "revert ALL THREE (pre-candidate v1.48 baseline)")
