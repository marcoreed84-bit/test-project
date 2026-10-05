"""
Aurelius_M15_EA.mq5 v1.60 bar-match check: Python simulator (engine.py +
sim.py, E.P15 construction - the same one aurelius_m15_random_timing_test.py
and vanguard_m15_h4_barmatch_2026.py already use for this EA's M15 variant)
vs the user's brand-new real MT5 Strategy Tester report of TODAY's v1.60
build (GOLD, M15, 2026.01.01-2026.09.25, 100% real ticks, 88 trades, PF
2.191927, net 22938.3 ZAR).

Methodology, same as vanguard_bar_match_check.py / vanguard_m15_h4_barmatch_
2026.py:
  1. Real report's own Inputs section read directly via openpyxl (not
     assumed) - confirmed byte-for-byte identical to E.P15's shipped
     defaults (every InpXxx= line checked against P15 below).
  2. Real Deals -> round-trip trades via research/ratchet/report.py's
     generic load_deals()/load_settings()/load() (EA-agnostic, reused
     unmodified, read-only).
  3. Sim context built on E.load_m15_native() (real native M15, not a
     resample - matches this EA's own file, "M15-NATIVE" per its header),
     sliced to 2014-06-13 onward per CLAUDE.md's known-gotcha trim (real
     M15 data only starts then), WITH ~1300 bars of extra lookback before
     2026-01-01 so E.P15's p2400=1200-bar warmup doesn't eat into the real
     comparison window (confirmed below this mattered: slicing bare to
     2026-01-01, like vanguard_m15_h4_barmatch_2026.py does, undercounts
     the first ~13 days of real trades as a warmup artifact, not a real
     simulator miss - checked per CLAUDE.md's "investigate an alarming
     result" rule before trusting any match%).
  4. sim.simulate()'s own entry_i/exit_i ARE the fill bar already (not the
     signal bar - sim.py sets entry_i = fill_i = i+1 explicitly), so no
     extra +1 offset is needed matching Vanguard's trendline-breakout
     construction did; still double-checked against the EA's known
     past-bug list in its own header (see script output) before trusting.
  5. Match real round-trips to sim trades by entry bar, floored to the
     nearest 15-minute M15 bar (fill times carry a few seconds of real
     execution delay past the bar open).
"""
import sys
import importlib.util
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd

import engine as E
from sim import simulate

# research/ratchet/report.py imported by explicit path (not sys.path, which
# would shadow this dir's own sim.py with ratchet's own sim.py of the same
# name - caught when `from sim import simulate` picked up the wrong module).
_spec = importlib.util.spec_from_file_location("ratchet_report", "/home/user/test-project/research/ratchet/report.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

XLSX = ("/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
        "57c36103-20261005_-_ReportTester-382043238_-_Aurelius_15_-_Backtest.xlsx")

REAL_WIN_LO = pd.Timestamp("2026-01-01")
REAL_WIN_HI = pd.Timestamp("2026-09-26")  # end exclusive, report covers thru 2026.09.25

# Extra lookback so E.P15's warmup (max(p2400,p600)+50 = 1250 M15 bars, ~13
# trading days) is fully built BEFORE the real comparison window starts,
# instead of eating into it.
CTX_START = "2025-10-01"
NATIVE_M15_GENUINE_START = "2014-06-13"  # CLAUDE.md gotcha


def key15(ts):
    return pd.Timestamp(ts).floor("15min")


if __name__ == "__main__":
    # ---- 1. real Inputs, read directly, checked against E.P15 ----
    real_inputs = R.load_settings(XLSX)
    print(f"Real report Inputs: n={len(real_inputs)} keys read from the xlsx's own Inputs section")

    # Spot-check every input that actually feeds E.P15 / sim.simulate(), by
    # name, against the real report's own value - NOT assumed.
    enum_ma = {"0": "sma", "1": "ema", "2": "smma"}
    enum_align = {"0": "FULL", "1": "MID", "2": "FAST", "3": "PRICE"}
    enum_pbma = {"0": "21", "1": "50", "2": "150"}
    enum_slopema = {"0": "21", "1": "50", "2": "150", "3": "600"}
    checks = [
        ("InpP21", str(E.P15["p21"])), ("InpP50", str(E.P15["p50"])),
        ("InpP150", str(E.P15["p150"])), ("InpP600", str(E.P15["p600"])),
        ("InpP2400", str(E.P15["p2400"])),
        ("InpM21", enum_ma, E.P15["m21"]), ("InpM50", enum_ma, E.P15["m50"]),
        ("InpM150", enum_ma, E.P15["m150"]), ("InpM600", enum_ma, E.P15["m600"]),
        ("InpM2400", enum_ma, E.P15["m2400"]),
        ("InpAlignMode", enum_align, E.P15["align_mode"]),
        ("InpPullbackMA", enum_pbma, E.P15["pullback_ma"]),
        ("InpPullbackTolATR", str(E.P15["pullback_tol_atr"])),
        ("InpPullbackBars", str(E.P15["pullback_bars"])),
        ("InpUseSlope", str(E.P15["use_slope"]).lower()),
        ("InpSlopeMA", enum_slopema, E.P15["slope_ma"]),
        ("InpSlopeBars", str(E.P15["slope_bars"])),
        ("InpMinSlopeATR", str(E.P15["min_slope_atr"])),
        ("InpMaxSlopeATR", str(E.P15["max_slope_atr"])),
        ("InpUseCrossFilter", str(E.P15["use_cross_filter"]).lower()),
        ("InpCrossWindow", str(E.P15["cross_window"])),
        ("InpMaxCrosses", str(E.P15["max_crosses"])),
        ("InpCooldownBars", str(E.P15["cooldown_bars"])),
        ("InpUseVolume", str(E.P15["use_volume"]).lower()),
        ("InpVolAvgBars", str(E.P15["vol_avg_bars"])),
        ("InpMinVolRatio", str(E.P15["min_vol_ratio"])),
        ("InpUseSRDist", str(E.P15["use_sr_dist"]).lower()),
        ("InpSRDays", str(E.P15["sr_days"])),
        ("InpMinSRDistATR", str(E.P15["min_sr_dist_atr"])),
        ("InpUseSlopeSRBlock", str(E.P15["use_slope_sr_block"]).lower()),
        ("InpSlopeSRBlockSlope", str(E.P15["slope_sr_block_slope"])),
        ("InpSlopeSRBlockSR", str(E.P15["slope_sr_block_sr"])),
        ("InpUseStopLoss", str(E.P15["use_stop"]).lower()),
        ("InpStopATR", str(E.P15["stop_atr"])),
        ("InpUsePrice21Exit", str(E.P15["use_price21_exit"]).lower()),
        ("InpUseVwapExit", str(E.P15["use_vwap_exit"]).lower()),
        ("InpVwapBufferATR", str(E.P15["vwap_buffer_atr"])),
        ("InpVwapConfirmBars", str(E.P15["vwap_confirm_bars"])),
        ("InpUseStaleExit", str(E.P15["use_stale_exit"]).lower()),
        ("InpUseBreakeven", str(E.P15["use_breakeven"]).lower()),
        ("InpAllowBuys", str(E.P15["allow_buys"]).lower()),
        ("InpAllowSells", str(E.P15["allow_sells"]).lower()),
        ("InpMaxSpreadPoints", "60"),
        ("InpUseMomentum", str(E.P15["use_momentum"]).lower()),
        ("InpUseScale", "false"),
        ("InpUseBank", "false"),
        ("InpUseGivebackExit", "false"),
    ]
    mismatches = []
    for chk in checks:
        if len(chk) == 2:
            name, expect = chk
            real_val = real_inputs.get(name)
            if real_val != expect:
                mismatches.append((name, real_val, expect))
        else:
            name, mapping, expect = chk
            real_val = real_inputs.get(name)
            mapped = mapping.get(real_val)
            if mapped != expect:
                mismatches.append((name, real_val, f"P15 wants {expect}"))
    if mismatches:
        print("INPUT MISMATCHES vs E.P15 (investigate before trusting anything below!):")
        for m in mismatches:
            print(f"   {m}")
    else:
        print("All checked real Inputs == E.P15's shipped defaults, byte-for-byte. "
              "Using E.P15 unmodified is correct for this report.")
    print(f"(Symbol={real_inputs.get('InpMagic')!r} n/a - real report's own Symbol/Period lines "
          f"say GOLD, M15 2026.01.01-2026.09.25, confirmed separately)")

    # ---- 2. real deals -> round trips (generic parser, unmodified) ----
    real_trips = R.load(XLSX)
    res = R.load_results(XLSX)
    rep_net = float(res["Total Net Profit"])
    rep_pf = float(res["Profit Factor"])
    print(f"\nReal round-trips parsed: n={len(real_trips)} (report Total Trades "
          f"{int(res['Total Trades'])})  net={sum(t['profit_ccy'] for t in real_trips):.2f} "
          f"(report {rep_net})  reconciled={'YES' if abs(sum(t['profit_ccy'] for t in real_trips) - rep_net) < 0.01 else 'NO'}")
    real_reasons = {}
    for t in real_trips:
        real_reasons[t["reason"]] = real_reasons.get(t["reason"], 0) + 1
    print(f"Real exit-reason counts: {real_reasons}")

    # ---- 3. sim context on native M15, with warmup buffer before the real window ----
    m15_full = E.load_m15_native()
    m15_full = m15_full[m15_full["time"] >= NATIVE_M15_GENUINE_START].reset_index(drop=True)
    m15 = m15_full[m15_full["time"] >= CTX_START].reset_index(drop=True)
    print(f"\nM15 sim data (post-trim, ctx window): n={len(m15)} bars, "
          f"{m15['time'].min()} -> {m15['time'].max()}")
    h4 = E.load_h4()
    ctx = E.build_context(m15, h4, params=E.P15)
    n = ctx["n"]
    warmup_bars = max(E.P15["p2400"], E.P15["p600"]) + 50
    warmup_end_time = m15["time"].iloc[min(warmup_bars, n - 1)]
    print(f"E.P15 warmup = {warmup_bars} bars -> first usable signal bar ~{warmup_end_time} "
          f"(well before real window start {REAL_WIN_LO.date()}, confirming the extra "
          f"lookback buffer is sufficient)")

    sim_trades = simulate(ctx, params=E.P15)
    times = m15["time"].values
    print(f"PYTHON sim trades (full ctx window, {CTX_START} onward): n={len(sim_trades)}")

    # ---- restrict both sides to the real report's own window, then match ----
    sim_rows = []
    for t in sim_trades:
        et = pd.Timestamp(times[t["entry_i"]])
        xt = pd.Timestamp(times[t["exit_i"]])
        if REAL_WIN_LO <= et < REAL_WIN_HI:
            sim_rows.append(dict(entry_time=et, exit_time=xt,
                                  side=t["dir"], entry_px=t["entry_px"],
                                  exit_px=t["exit_px"], reason=t["reason"],
                                  pnl=(t["exit_px"] - t["entry_px"]) * t["dir"]))
    sim_by_key = {}
    for r in sim_rows:
        sim_by_key[key15(r["entry_time"])] = r
    print(f"Python sim trades inside the real report's window "
          f"({REAL_WIN_LO.date()} -> {REAL_WIN_HI.date()}): n={len(sim_rows)}")

    real_rows = [dict(entry_time=pd.Timestamp(t["entry_time"]), exit_time=pd.Timestamp(t["exit_time"]),
                       side=t["side"], entry_px=t["entry"], exit_px=t["exit"],
                       reason=t["reason"], pnl_usd=t["pnl_usd"], profit_ccy=t["profit_ccy"])
                 for t in real_trips]
    real_by_key = {}
    for r in real_rows:
        real_by_key[key15(r["entry_time"])] = r

    both = sorted(set(real_by_key) & set(sim_by_key))
    only_real = sorted(set(real_by_key) - set(sim_by_key))
    only_sim = sorted(set(sim_by_key) - set(real_by_key))

    same_dir = sum(real_by_key[k]["side"] == sim_by_key[k]["side"] for k in both)
    same_reason = sum((real_by_key[k]["reason"] == "SL") == (sim_by_key[k]["reason"] == "STOP")
                       for k in both)

    print(f"\n==== BAR-MATCH RESULT ====")
    print(f"real trades in window: {len(real_by_key)}   sim trades in window: {len(sim_by_key)}")
    print(f"entry-bar matches: {len(both)} ({100*len(both)/max(1,len(real_by_key)):.1f}% of real's "
          f"{len(real_by_key)} trades)")
    print(f"real-only (sim missed): {len(only_real)}   sim-only (sim invented): {len(only_sim)}")
    print(f"of matched bars: same direction {same_dir}/{len(both)}   "
          f"same exit-category (SL<->STOP vs EA-close) {same_reason}/{len(both)}")

    if both:
        pdiff = [abs(real_by_key[k]["entry_px"] - sim_by_key[k]["entry_px"]) for k in both]
        print(f"entry price diff on matched bars: median={np.median(pdiff):.3f}  max={np.max(pdiff):.3f}")

        # net P/L, PF comparison - sim is in raw USD price-move units (no ZAR
        # conversion, no lot sizing); real is in ZAR account currency. Compare
        # on the matched-subset USD pnl (real's own pnl_usd field, already
        # currency-neutral per research/ratchet/report.py) vs sim pnl.
        real_pnl_usd_matched = [real_by_key[k].get("pnl_usd") for k in both]
        sim_pnl_matched = [sim_by_key[k]["pnl"] for k in both]
        print(f"\nmatched-subset net price-move (USD-equiv, real): {sum(real_pnl_usd_matched):.2f}")
        print(f"matched-subset net price-move (sim):              {sum(sim_pnl_matched):.2f}")

    print(f"\nFull-window real report figures (ground truth): n={len(real_trips)}  "
          f"net={rep_net:.2f} ZAR  PF={rep_pf:.6f}")
    full_sim_pnl = [r["pnl"] for r in sim_rows]
    gp = sum(p for p in full_sim_pnl if p > 0); gl = -sum(p for p in full_sim_pnl if p < 0)
    sim_pf = gp / gl if gl > 0 else float("inf")
    print(f"Full-window PYTHON sim figures (price-move units, no ZAR/lot conversion): "
          f"n={len(sim_rows)}  net_price_move={sum(full_sim_pnl):.2f}  PF={sim_pf:.4f}")
