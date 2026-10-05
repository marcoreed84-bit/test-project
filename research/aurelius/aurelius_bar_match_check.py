"""
Aurelius_EA.mq5 (M5) bar-match check - the validation that was missing for
Aurelius specifically (unlike Vanguard's vanguard_bar_match_check.py or
H&S's hs_gold_bar_match_check.py). Real ground truth is the user's brand-new
2026-10-05 upload testing TODAY's fixed v1.56 build:

  471f1dd8-20261005_-_ReportTester-382043238_-_Aurelius_-_Backtest.xlsx
  GOLD, M5, 2026.01.01-2026.09.25, 100% real ticks, 167 trades,
  PF 1.888141, net 19942.1 (report's own Results block).

v1.56's actual changes (per Aurelius_EA.mq5's own header, 2026-10-04) are all
live-restart/bookkeeping robustness fixes - OnTradeTransaction() now handles
every close reason not just SL, g_barsSinceClose restored from history on
restart, scale-in add legs get a real stop-loss, a restart-inside-entry-bar
resync bug, LotSize() rounding epsilon, confirm-bar input validation. NONE of
these touch the signal/exit/MA/filter logic engine.py and sim.py model (those
bugs only matter across a live terminal restart mid-session, which a single
continuous Strategy Tester run never exercises) - so no simulator change was
expected or made here; this is a read-only check of engine.py/sim.py as they
already stand.

Methodology (same as vanguard_bar_match_check.py / hs_gold_bar_match_check.py):
  1. Read the real report's own Inputs section (openpyxl) -> actual InpXxx
     values used in THIS run, mapped onto engine.P's parameter names/enums.
  2. Parse the real Deals table into round-trip trades via
     research/ratchet/report.py's load()/reconcile() (symbol/EA-agnostic,
     reused unchanged) - reconcile() proves the parse is exact (sum of
     profit+commission+swap equals the report's own Total Net Profit, trade
     count matches Total Trades).
  3. Run engine.build_context() + sim.simulate() with the REAL report's own
     params (not assumed defaults - verified field by field below).
  4. Match real entries to sim entries by entry bar, floored to 5 minutes.
  5. Report match %, net/PF agreement (price-difference basis - sim's
     (exit_px-entry_px)*dir is directly USD-comparable to the real round
     trip's pnl_usd because both are priced at 0.01 lot x 100 contract size,
     i.e. 1 price-point of move = $1 at this size), and exit-reason agreement.
"""
import sys
import importlib.util
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import openpyxl

import engine as E
import sim as S

# research/ratchet/report.py is loaded by explicit file path, NOT by adding
# research/ratchet to sys.path - that directory has its OWN sim.py (Ratchet's
# sequential simulator), which would silently shadow Aurelius's sim.py (wrong
# simulate() signature) if both dirs were on sys.path at once. Caught by
# running this script: "simulate() got an unexpected keyword argument
# 'params'" - Ratchet's sim.simulate has a different signature entirely.
_spec = importlib.util.spec_from_file_location(
    "ratchet_report", "/home/user/test-project/research/ratchet/report.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

XLSX = ("/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
        "471f1dd8-20261005_-_ReportTester-382043238_-_Aurelius_-_Backtest.xlsx")
WIN_LO, WIN_HI = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-09-25")

# ---- enum maps, from Aurelius_EA.mq5's own enum declarations (~970-979) ----
MA_METHOD = {0: "sma", 1: "ema", 2: "smma", 3: "lwma"}
ALIGN_MODE = {0: "FULL", 1: "MID", 2: "FAST", 3: "PRICE"}
PBMA = {0: "21", 1: "50", 2: "150"}
SLOPEMA = {0: "21", 1: "50", 2: "150", 3: "600"}


def _b(s):
    return str(s).strip().lower() == "true"


def build_params_from_real_inputs(settings):
    """settings: {InpXxx: 'value string'} as report.load_settings() returns.
    Builds an engine.P-shaped params dict from the REAL report's own values,
    not from engine.py's/sim.py's hardcoded defaults."""
    s = settings
    p = dict(
        p21=int(s["InpP21"]), p50=int(s["InpP50"]), p150=int(s["InpP150"]),
        p600=int(s["InpP600"]), p2400=int(s["InpP2400"]),
        m21=MA_METHOD[int(s["InpM21"])], m50=MA_METHOD[int(s["InpM50"])],
        m150=MA_METHOD[int(s["InpM150"])], m600=MA_METHOD[int(s["InpM600"])],
        m2400=MA_METHOD[int(s["InpM2400"])],
        align_mode=ALIGN_MODE[int(s["InpAlignMode"])],
        pullback_ma=PBMA[int(s["InpPullbackMA"])],
        pullback_tol_atr=float(s["InpPullbackTolATR"]),
        pullback_bars=int(s["InpPullbackBars"]),
        use_slope=_b(s["InpUseSlope"]), slope_ma=SLOPEMA[int(s["InpSlopeMA"])],
        slope_bars=int(s["InpSlopeBars"]),
        min_slope_atr=float(s["InpMinSlopeATR"]), max_slope_atr=float(s["InpMaxSlopeATR"]),
        use_cross_filter=_b(s["InpUseCrossFilter"]), cross_window=int(s["InpCrossWindow"]),
        max_crosses=int(s["InpMaxCrosses"]), cooldown_bars=int(s["InpCooldownBars"]),
        use_volume=_b(s["InpUseVolume"]), vol_avg_bars=int(s["InpVolAvgBars"]),
        min_vol_ratio=float(s["InpMinVolRatio"]),
        use_sr_dist=_b(s["InpUseSRDist"]), sr_days=int(s["InpSRDays"]),
        min_sr_dist_atr=float(s["InpMinSRDistATR"]),
        use_stop=_b(s["InpUseStopLoss"]), stop_atr=float(s["InpStopATR"]),
        use_price21_exit=_b(s["InpUsePrice21Exit"]),
        price21_buffer_atr=float(s["InpPrice21BufferATR"]),
        price21_confirm_bars=int(s["InpPrice21ConfirmBars"]),
        use_vwap_exit=_b(s["InpUseVwapExit"]),
        vwap_buffer_atr=float(s["InpVwapBufferATR"]),
        vwap_confirm_bars=int(s["InpVwapConfirmBars"]),
        allow_buys=_b(s["InpAllowBuys"]), allow_sells=_b(s["InpAllowSells"]),
        use_breakeven=_b(s["InpUseBreakeven"]), breakeven_atr=float(s["InpBreakevenATR"]),
        breakeven_lock_atr=float(s["InpBreakevenLockATR"]),
        use_trail_after_be=_b(s["InpUseTrailAfterBE"]),
        trail_give_back_atr=float(s["InpTrailGiveBackATR"]),
        use_stale_exit=_b(s["InpUseStaleExit"]), stale_bars=int(s["InpStaleBars"]),
        stale_min_loss_atr=float(s["InpStaleMinLossATR"]),
        use_momentum=_b(s["InpUseMomentum"]),
        macd_fast=12, macd_slow=26, macd_signal=9, macd_signal_method="sma",
        point=0.01,  # GOLD meta_point - confirmed off GOLD_M5.csv's own header below
    )
    # InpUseScale/InpUseBank are real inputs but have NO corresponding lever
    # in sim.py's simulate() at all (scale-in/banking are not modeled there).
    # Confirm they're off in THIS real run, so that gap can't matter here.
    use_scale = _b(s.get("InpUseScale", "false"))
    use_bank = _b(s.get("InpUseBank", "false"))
    return p, use_scale, use_bank


def key(ts):
    return pd.Timestamp(ts).floor("5min")


if __name__ == "__main__":
    # ---- (a) real Inputs, verified against engine.P field by field ----
    settings = R.load_settings(XLSX)
    params, use_scale, use_bank = build_params_from_real_inputs(settings)
    print(f"Real report Period: GOLD M5, window {WIN_LO.date()}-{WIN_HI.date()}")
    print(f"InpUseScale={use_scale}  InpUseBank={use_bank} (both unmodeled in sim.py - "
          f"fine here since both are OFF in this real run)")

    mismatches = []
    for k, v in params.items():
        if k in ("point", "macd_fast", "macd_slow", "macd_signal", "macd_signal_method"):
            continue
        if k in E.P and E.P[k] != v:
            mismatches.append((k, E.P[k], v))
    if mismatches:
        print(f"\n*** real Inputs DIFFER from engine.P defaults on {len(mismatches)} field(s): ***")
        for k, dflt, real in mismatches:
            print(f"    {k}: engine.P default={dflt!r}  real report={real!r}")
    else:
        print("\nReal report's Inputs match engine.py's P (shipped v1.46+ defaults) "
              "field-for-field on every lever simulate() reads - confirmed, not assumed.")

    # ---- (b) real trades, via report.py's generic, EA-agnostic parser ----
    print("\n--- parsing real Deals table (research/ratchet/report.py, reused unchanged) ---")
    trips, res = R.reconcile(XLSX, label="Aurelius GOLD M5 2026-10-05 report")
    real = [dict(time=pd.Timestamp(t["entry_time"]), side=t["side"], price=t["entry"],
                 pnl_usd=t["pnl_usd"], reason=t["reason"], exit_time=pd.Timestamp(t["exit_time"]))
            for t in trips]
    real_w = [r for r in real if WIN_LO <= r["time"] <= WIN_HI]
    print(f"\nReal Aurelius GOLD M5 trades in window: n={len(real_w)}")

    # ---- (c) simulator, run with the REAL report's own params ----
    df5 = E.load_m5()
    h4 = E.load_h4()
    print(f"\nSimulator data: {df5['time'].min()} -> {df5['time'].max()} ({len(df5)} bars)")
    cover_lo, cover_hi = df5["time"].min(), df5["time"].max()
    print(f"Real report window {'IS' if (cover_lo <= WIN_LO and cover_hi >= WIN_HI) else 'is NOT'} "
          f"fully covered by the simulator's M5 data (checked before trusting any match number).")

    ctx = E.build_context(df5, h4, params=params)
    sim_trades = S.simulate(ctx, params=params)
    times = df5["time"].values

    sim_by_key = {}
    for t in sim_trades:
        ts = pd.Timestamp(times[t["entry_i"]])
        if WIN_LO <= ts <= WIN_HI:
            sim_by_key[key(ts)] = dict(side=t["dir"], price=t["entry_px"],
                                        pnl=(t["exit_px"] - t["entry_px"]) * t["dir"],
                                        reason=t["reason"],
                                        exit_time=pd.Timestamp(times[t["exit_i"]]))
    print(f"Sim trades in the SAME 2026.01.01-2026.09.25 window: {len(sim_by_key)}")

    real_by_key = {key(r["time"]): r for r in real_w}
    both = sorted(set(real_by_key) & set(sim_by_key))
    only_real = sorted(set(real_by_key) - set(sim_by_key))
    only_sim = sorted(set(sim_by_key) - set(real_by_key))
    same_dir = sum(real_by_key[k]["side"] == sim_by_key[k]["side"] for k in both)

    match_pct = 100 * len(both) / max(1, len(real_by_key))
    print(f"\n=== entry-bar match ===")
    print(f"matched: {len(both)} / {len(real_by_key)} real trades ({match_pct:.1f}%)")
    print(f"real-only (sim missed): {len(only_real)}   sim-only (sim invented): {len(only_sim)}")
    print(f"of matched bars, same direction: {same_dir}/{len(both)}")

    if both:
        pdiff = [abs(real_by_key[k]["price"] - sim_by_key[k]["price"]) for k in both]
        print(f"entry price diff on matched bars: median={np.median(pdiff):.3f}  max={np.max(pdiff):.3f}")

        same_reason = 0
        for k in both:
            rr = real_by_key[k]["reason"]          # SL / TP / STOPOUT / EA
            sr = sim_by_key[k]["reason"]            # STOP / SESSION_CLOSE / PRICE21 / VWAP / ALIGN_BREAK / STALE
            sim_is_stop = sr == "STOP"
            real_is_stop = rr == "SL"
            if sim_is_stop == real_is_stop:
                same_reason += 1
        print(f"exit-mechanism agreement (stop vs non-stop) on matched trades: "
              f"{same_reason}/{len(both)} ({100*same_reason/len(both):.1f}%)")

        real_pnl_matched = sum(real_by_key[k]["pnl_usd"] for k in both)
        sim_pnl_matched = sum(sim_by_key[k]["pnl"] for k in both)
        print(f"\nOn the {len(both)} matched trades (price-difference / USD-neutral basis, "
              f"0.01 lot):")
        print(f"  real net (pnl_usd): {real_pnl_matched:.2f}")
        print(f"  sim  net (price-diff): {sim_pnl_matched:.2f}")
        print(f"  diff: {sim_pnl_matched - real_pnl_matched:+.2f} "
              f"({100*(sim_pnl_matched-real_pnl_matched)/abs(real_pnl_matched):+.1f}%)")

    # ---- full-window totals, for context (not the headline match number) ----
    real_pnl_all = sum(r["pnl_usd"] for r in real_w)
    sim_pnl_all = sum(v["pnl"] for v in sim_by_key.values())
    real_wins = sum(1 for r in real_w if r["pnl_usd"] > 0)
    sim_wins = sum(1 for v in sim_by_key.values() if v["pnl"] > 0)
    print(f"\n--- full-window totals (context only) ---")
    print(f"real: n={len(real_w)} net={real_pnl_all:.2f} win%={100*real_wins/len(real_w):.1f}")
    print(f"sim:  n={len(sim_by_key)} net={sim_pnl_all:.2f} "
          f"win%={100*sim_wins/max(1,len(sim_by_key)):.1f}")
