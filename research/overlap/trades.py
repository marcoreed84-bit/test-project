"""
Trade-list construction for the six-system portfolio overlap study
(see overlap_test.py for the actual analysis and the full write-up).

This file does ONE job: for each of Aurelius_EA.mq5 (M5), Aurelius_M15_EA.mq5,
Vanguard_EA.mq5 (M5), Vanguard_M15_EA.mq5, Meridian_EA.mq5 and Ratchet_EA.mq5,
produce a real trade list (entry_time, exit_time, dir, pnl) using its OWN
current shipped-default parameters and its OWN existing, already-validated
Python simulator - nothing here re-derives any EA's entry/exit logic from
scratch. Every simulator is imported from its home research/ directory and
used exactly as its own test scripts already use it:

  Aurelius M5    research/aurelius/engine.py (P)   + sim.py simulate()
  Aurelius M15   research/aurelius/engine.py (P15) + sim.py simulate()
  Vanguard M5    research/aurelius/trendline_break_test.py (breakout events)
                 + vanguard_m5_joint_sweep_test.sim_full() (the joint sl x
                 stale_bars simulator that produced Vanguard's current
                 shipped InpSafetyStopATR/InpStaleBars values)
  Vanguard M15   same construction, M15 fractal_k/params
  Meridian       research/meridian/msim.py (V102)
  Ratchet        research/ratchet/sim.py (SHIPPED)

SHIPPED-DEFAULT PARAMETERS - verified against the .mq5 files' current `input`
defaults directly (Aurelius_EA.mq5/Aurelius_M15_EA.mq5/Ratchet_EA.mq5 were
read-only per this task's scope guard; Vanguard_EA.mq5/Vanguard_M15_EA.mq5/
Meridian_EA.mq5 were read freely):

  Aurelius M5  (Aurelius_EA.mq5,  v1.46 logic): engine.P  - unchanged.
  Aurelius M15 (Aurelius_M15_EA.mq5, v1.5x logic): engine.P15 - unchanged.
  Vanguard M5  (Vanguard_EA.mq5): InpFractalK=100, InpSRDays=3,
    InpMinSRDistATR=0.50, InpSafetyStopATR=4.0, InpUseStaleExit=true,
    InpStaleBars=225, InpStaleMinProfitATR=0.0. VWAP/S&R agreement are not
    inputs at all - CheckForEntry() hard-codes both (the confirmVWAP check
    and the SRDistance() call) as unconditional gates, confirmed by reading
    Vanguard_EA.mq5's CheckForEntry() directly (~line 1392-1429).
  Vanguard M15 (Vanguard_M15_EA.mq5): InpFractalK=33, InpSRDays=3,
    InpMinSRDistATR=0.50, InpSafetyStopATR=3.0, InpUseStaleExit=true,
    InpStaleBars=75, InpStaleMinProfitATR=0.0.
  Meridian (Meridian_EA.mq5 v1.03, cosmetic-only bump over v1.02 - no logic
    change per its own header): msim.V102 verified field-by-field against
    Meridian_EA.mq5's current `input` defaults (InpP21=21/InpP50=50/EMA,
    InpPConfirm=250/SMA, InpSRDays=3/InpMinSRDistATR=0.50,
    InpSafetyStopATR=2.5, InpMaxSpreadPoints=60, InpFridayCloseHour=22) -
    matches exactly.
  Ratchet (Ratchet_EA.mq5 v3.30): sim.py's SHIPPED = RP() (all defaults)
    matches every current `input` default EXCEPT ONE KNOWN GAP, disclosed
    here rather than silently carried: Ratchet_EA.mq5 v3.30 shipped
    InpTrailRunnerATR=6.0 / InpTrailRunnerKeep=0.60 (real-MT5-confirmed,
    2026-09-23) as an unconditional trail-tightening rule for trades whose
    best favourable move reaches 6x entry ATR, but sim.py's RP dataclass has
    no dedicated field for it - the only way to reproduce it in this
    simulator is a `keep_fn` override (see candidates.py's keep_prog()),
    which SHIPPED does NOT apply (keep_fn=None). This file follows this
    repo's own most recent precedent on exactly this question -
    research/ratchet/divergence_exit_test.py, written the same day as the
    v3.30 confirmation, explicitly labels `S.SHIPPED` unmodified as "the
    real shipped v3.30 baseline (SHIPPED, InpTrailRunnerATR=6.0)" and uses
    it as-is - so this file does too, for consistency with the rest of the
    codebase rather than inventing a special-cased config used nowhere else.
    Effect of the gap: only trades whose peak favourable excursion reaches
    6x entry ATR are affected (a minority - Ratchet's median hold is short),
    and only their EXIT (a slightly wider give-back before the trail locks
    in) - entries, non-runner trades, and every other system are unaffected.
    Flagged, not hidden.

COMMON DATA WINDOW - the two data sources behind these six simulators do NOT
cover identical ranges, so this is stated explicitly rather than picked
silently:
  - Aurelius/Vanguard (M5 and M15) read research/aurelius/engine.py's
    GOLD# M5 CSV export: 2023-01-03 01:00 .. 2026-08-14 23:55 (256,320 M5
    bars). No pre-history before 2023-01-03 is available from this export,
    so each system's own internal warm-up (Aurelius needs
    max(p2400,p600)+50 bars; Vanguard's own construction has none beyond
    its trendline fractal) eats into the first ~1-2 weeks of the window
    itself, exactly as every other Python test in research/aurelius/
    already accepts for this same file.
  - Meridian/Ratchet read research/ratchet/bars.py's GOLD# M5 zip export:
    2022-06-27 04:30 .. 2026-09-18 23:55 (a DIFFERENT export of the same
    broker/symbol feed, confirmed by reading both CSV headers directly:
    both say `meta_symbol,GOLD#`, so this is not the GOLD-vs-GOLD# data
    mismatch flagged in this repo's 2026-09-23 Meridian full-history note -
    that note is about a real MT5 report run on a DIFFERENT account/symbol,
    not about either of these two Python bar exports). This export starts
    ~6 months before 2023-01-03, which is far more than any indicator here
    needs to converge (the longest lookback in play, Aurelius/Ratchet's
    2400-period MA, is 2400 M5 bars =~ 8.3 days of trading) - so Meridian
    and Ratchet's trades are fully converged, not warm-up-degraded, over
    the whole common window used below.

  COMMON WINDOW USED THROUGHOUT THIS STUDY: 2023-01-03 01:00:00 to
  2026-08-14 23:55:00 (broker server time) - the INTERSECTION of the two
  data sources, i.e. bounded by the narrower one (Aurelius/Vanguard's own
  export, both ends). Meridian and Ratchet's simulators default to their
  own real-MT5-validation window (2026-01-01..2026-09-21, sim.py/msim.py's
  own WIN_START/WIN_END) - both accept explicit start/end overrides, so
  this file passes the common window above instead, which their own
  underlying data fully supports (see above). Aurelius/Vanguard's trade
  lists are generated over their full data range and then entries outside
  the common window are dropped (their simulators don't take a start/end
  argument the way Meridian/Ratchet's do; the effective dropped region is
  a few trades before 2023-01-03's warm-up period, and nothing at the
  right edge since the file itself ends exactly at the common window's end).

VANGUARD'S LIVE AURELIUS FILTER (InpUseAureliusFilter, default TRUE on both
Vanguard_EA.mq5 and Vanguard_M15_EA.mq5): generate_vanguard_m5/m15() below
build the RAW, UNFILTERED trade list (VWAP+S/R gates only, filter OFF) as
the default/primary output - see overlap_test.py's module docstring for why
(short version: the whole point of this study is to measure the portfolio's
NATURAL overlap/agreement structure, including for the other 14 pairs that
have no such filter at all; running Vanguard's current shipped config WITH
the filter already on would make Aurelius-vs-Vanguard's opposite-direction
overlap near-zero by construction and tell us nothing about whether that
filter is earning its keep). vanguard_m5_with_aurelius_filter() below is a
SEPARATE, explicit function that reproduces the live filter's exact rule
(AureliusBlocksEntry(): block only if Aurelius is ALREADY open AGAINST this
direction at the exact entry bar) using this file's own Python-simulated
Aurelius M5 trade list as the "real position" ground truth - NOT the real
MT5 deals research/aurelius/vanguard_aurelius_position_filter_test.py used,
a deliberate, disclosed method difference: that file had one real MT5
Aurelius report available for one specific account/period; this study
needs the SAME construction (Python-simulated, same data window) applied
uniformly across all 15 pairs, so it uses the Python-simulated Aurelius
trade list here too, for internal consistency, rather than mixing sources
mid-analysis.
"""
import os
import sys
import importlib.util

import numpy as np
import pandas as pd

ROOT = "/home/user/test-project"
AURELIUS_DIR = os.path.join(ROOT, "research/aurelius")
MERIDIAN_DIR = os.path.join(ROOT, "research/meridian")
RATCHET_DIR = os.path.join(ROOT, "research/ratchet")
for _d in (AURELIUS_DIR, RATCHET_DIR, MERIDIAN_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

# research/aurelius/sim.py and research/ratchet/sim.py are BOTH literally
# named sim.py, and with all three research dirs on sys.path a plain
# "import sim" would silently resolve to whichever directory happens to sit
# first on sys.path (found the hard way: RATCHET_DIR ended up before
# AURELIUS_DIR after the insert(0, ...) loop above, so a plain "import sim"
# here silently loaded Ratchet's simulate(), which has a different
# signature - TypeError caught it, but only because the signatures differ;
# it would NOT have been caught if they matched). Both are loaded explicitly
# via importlib under distinct registered names instead, so neither depends
# on sys.path search order. Each file's own internal imports (Aurelius
# sim.py -> "from engine import P, POINT"; Ratchet sim.py ->
# "import bars as B") still resolve fine via the normal sys.path search,
# since "engine" and "bars" are unique names.
def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


import engine as E                              # research/aurelius/engine.py
aurelius_sim = _load_module(os.path.join(AURELIUS_DIR, "sim.py"), "aurelius_sim_mod")
import trendline_break_test as TBT              # research/aurelius/trendline_break_test.py
import vanguard_m5_joint_sweep_test as VJS       # research/aurelius/vanguard_m5_joint_sweep_test.py (sim_full)

ratchet_sim = _load_module(os.path.join(RATCHET_DIR, "sim.py"), "ratchet_sim_mod")
import msim as meridian_sim                      # research/meridian/msim.py

COMMON_START = pd.Timestamp("2023-01-03 01:00:00")
COMMON_END = pd.Timestamp("2026-08-14 23:55:00")

VANGUARD_M5_FRACTAL_K = 100
VANGUARD_M5_SAFETY_SL = 4.0
VANGUARD_M5_STALE_BARS = 225
VANGUARD_M15_FRACTAL_K = 33
VANGUARD_M15_SAFETY_SL = 3.0
VANGUARD_M15_STALE_BARS = 75
VANGUARD_MIN_SR = 0.50


def _clip(trades, start=COMMON_START, end=COMMON_END):
    return [t for t in trades if start <= t["entry_time"] <= end]


def load_common_data():
    """Loads the Aurelius/Vanguard M5 CSV once and builds both the M5 and
    M15 engine contexts (build_context is where the per-bar MA/ATR/VWAP/S&R
    arrays used by BOTH Aurelius's own signal and Vanguard's trendline
    filters live - reused for both, see Vanguard construction below)."""
    df5 = E.load_m5()
    h4 = E.load_h4()
    df15 = E.resample_m15_from_m5(df5)
    ctx5 = E.build_context(df5, h4, params=E.P)
    ctx15 = E.build_context(df15, h4, params=E.P15)
    return dict(df5=df5, h4=h4, df15=df15, ctx5=ctx5, ctx15=ctx15)


# --------------------------------------------------------------- Aurelius

def aurelius_m5_trades(data):
    ctx = data["ctx5"]
    raw = aurelius_sim.simulate(ctx, params=E.P)
    time = ctx["time"]
    out = []
    for t in raw:
        out.append(dict(
            entry_time=pd.Timestamp(time[t["entry_i"]]),
            exit_time=pd.Timestamp(time[t["exit_i"]]),
            dir=int(t["dir"]),
            pnl=float((t["exit_px"] - t["entry_px"]) * t["dir"]),
            system="Aurelius_M5",
        ))
    return _clip(out)


def aurelius_m15_trades(data):
    ctx = data["ctx15"]
    raw = aurelius_sim.simulate(ctx, params=E.P15)
    time = ctx["time"]
    out = []
    for t in raw:
        out.append(dict(
            entry_time=pd.Timestamp(time[t["entry_i"]]),
            exit_time=pd.Timestamp(time[t["exit_i"]]),
            dir=int(t["dir"]),
            pnl=float((t["exit_px"] - t["entry_px"]) * t["dir"]),
            system="Aurelius_M15",
        ))
    return _clip(out)


# --------------------------------------------------------------- Vanguard

def _vanguard_entry_gates(ctx, fractal_k, min_sr):
    """VWAP + S/R gates, byte-identical to CheckForEntry()'s unconditional
    confirmVWAP/SRDistance checks - shared by M5 and M15 (both engine
    contexts carry the same-shaped vwap/sr_dist_buy/sr_dist_sell arrays,
    verified equivalent to meridian_m15_test.build_sr_distance() for the M15
    case by direct code comparison: identical rolling(sr_days).max/min().
    shift(1) construction off the same derive_d1_from_h4(h4).)"""
    close, high, low = ctx["close"], ctx["high"], ctx["low"]
    n = ctx["n"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    desc_line, asc_line = TBT.build_trendline_values(high, low, n, fractal_k=fractal_k)
    events = TBT.build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        entry_ok[i] = not (sr >= 0.0 and sr < min_sr)
    return events, entry_ok


def _vanguard_sim_to_trades(events, entry_ok, ctx, safety_sl, stale_bars, system_label):
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    n, time = ctx["n"], ctx["time"]
    raw = VJS.sim_full(events, entry_ok, close, high, low, spread, atr, n,
                        safety_sl, stale_bars=stale_bars, stale_min_profit_atr=0.0)
    out = []
    for (i, exit_bar, pnl, is_buy) in raw:
        fill_i = min(i + 1, n - 1)   # position actually opens at the NEXT bar's open, matching every
        # other simulator in this file (sim_full's own tuple records the signal bar i, not the fill bar)
        out.append(dict(
            entry_time=pd.Timestamp(time[fill_i]),
            exit_time=pd.Timestamp(time[min(exit_bar, n - 1)]),
            dir=1 if is_buy else -1,
            pnl=float(pnl),
            system=system_label,
            signal_i=i,   # the entry-DECISION bar (before the +1 fill shift) - kept only so
                           # overlap_test.py's Aurelius-filter validation check can look up
                           # Aurelius's own position at the exact bar AureliusBlocksEntry()
                           # would have checked it at; unused elsewhere.
        ))
    return out


def vanguard_m5_trades(data):
    ctx = data["ctx5"]
    events, entry_ok = _vanguard_entry_gates(ctx, VANGUARD_M5_FRACTAL_K, VANGUARD_MIN_SR)
    out = _vanguard_sim_to_trades(events, entry_ok, ctx, VANGUARD_M5_SAFETY_SL,
                                   VANGUARD_M5_STALE_BARS, "Vanguard_M5")
    return _clip(out)


def vanguard_m15_trades(data):
    ctx = data["ctx15"]
    events, entry_ok = _vanguard_entry_gates(ctx, VANGUARD_M15_FRACTAL_K, VANGUARD_MIN_SR)
    out = _vanguard_sim_to_trades(events, entry_ok, ctx, VANGUARD_M15_SAFETY_SL,
                                   VANGUARD_M15_STALE_BARS, "Vanguard_M15")
    return _clip(out)


def aurelius_m5_position_state(data):
    """Aurelius M5's own simulated position direction (+1/-1/0) on the M5
    bar grid - used ONLY to reproduce InpUseAureliusFilter's real rule
    (AureliusBlocksEntry) in Python, for the one validation check in
    overlap_test.py that asks whether the live filter is earning its keep.
    Not used anywhere else in this file."""
    ctx = data["ctx5"]
    n = ctx["n"]
    raw = aurelius_sim.simulate(ctx, params=E.P)
    state = np.zeros(n, dtype=np.int8)
    for t in raw:
        state[t["entry_i"]:t["exit_i"]] = t["dir"]
    return state


def aurelius_m15_position_state(data):
    """M15 analogue of aurelius_m5_position_state() - Vanguard_M15_EA.mq5
    reads Aurelius_M15_EA.mq5's own M15-chart position (a SEPARATE terminal
    global variable, AURELIUS_POSDIR_M15_+Symbol, from the M5 one), so this
    is the correct state array for that specific live filter, not the M5
    one reused."""
    ctx = data["ctx15"]
    n = ctx["n"]
    raw = aurelius_sim.simulate(ctx, params=E.P15)
    state = np.zeros(n, dtype=np.int8)
    for t in raw:
        state[t["entry_i"]:t["exit_i"]] = t["dir"]
    return state


def vanguard_m15_trades_with_aurelius_filter(data, aur_state15):
    ctx = data["ctx15"]
    events, entry_ok = _vanguard_entry_gates(ctx, VANGUARD_M15_FRACTAL_K, VANGUARD_MIN_SR)
    for i, d in events:
        a = aur_state15[i]
        if a != 0 and a != d:
            entry_ok[i] = False
    out = _vanguard_sim_to_trades(events, entry_ok, ctx, VANGUARD_M15_SAFETY_SL,
                                   VANGUARD_M15_STALE_BARS, "Vanguard_M15_filtered")
    return _clip(out)


def vanguard_m5_trades_with_aurelius_filter(data, aur_state):
    """Reproduces AureliusBlocksEntry() exactly: block a breakout only if
    Aurelius's OWN simulated position at that exact entry-decision bar (i,
    not the fill bar) is already open in the OPPOSITE direction; flat or
    same-direction never blocks. This is InpUseAureliusFilter=true (the
    current shipped default on both Vanguard EAs)."""
    ctx = data["ctx5"]
    events, entry_ok = _vanguard_entry_gates(ctx, VANGUARD_M5_FRACTAL_K, VANGUARD_MIN_SR)
    for i, d in events:
        a = aur_state[i]
        if a != 0 and a != d:
            entry_ok[i] = False
    out = _vanguard_sim_to_trades(events, entry_ok, ctx, VANGUARD_M5_SAFETY_SL,
                                   VANGUARD_M5_STALE_BARS, "Vanguard_M5_filtered")
    return _clip(out)


# --------------------------------------------------------------- Meridian

def meridian_trades():
    ctx = meridian_sim.build_ctx()
    raw, _stats = meridian_sim.simulate(ctx, p=meridian_sim.V102, start=COMMON_START, end=COMMON_END)
    out = []
    for t in raw:
        out.append(dict(
            entry_time=pd.Timestamp(t["entry_time"]),
            exit_time=pd.Timestamp(t["exit_time"]),
            dir=int(t["dir"]),
            pnl=float(t["pnl"]),
            system="Meridian",
        ))
    return out


# --------------------------------------------------------------- Ratchet

def ratchet_trades():
    ctx = ratchet_sim.build_ctx()
    raw, _stats = ratchet_sim.simulate(ctx, p=ratchet_sim.SHIPPED, start=COMMON_START, end=COMMON_END)
    out = []
    for t in raw:
        out.append(dict(
            entry_time=pd.Timestamp(t["entry_time"]),
            exit_time=pd.Timestamp(t["exit_time"]),
            dir=int(t["dir"]),
            pnl=float(t["pnl"]),
            system="Ratchet",
        ))
    return out


# --------------------------------------------------------------- convenience

def build_all_systems():
    """Returns (systems, data) where systems is an ordered dict-like list of
    (name, trades) for all six, and data is load_common_data()'s dict (kept
    around for the Aurelius-filter validation check, which needs ctx5
    again)."""
    data = load_common_data()
    systems = [
        ("Aurelius_M5", aurelius_m5_trades(data)),
        ("Aurelius_M15", aurelius_m15_trades(data)),
        ("Vanguard_M5", vanguard_m5_trades(data)),
        ("Vanguard_M15", vanguard_m15_trades(data)),
        ("Meridian", meridian_trades()),
        ("Ratchet", ratchet_trades()),
    ]
    return systems, data


if __name__ == "__main__":
    systems, data = build_all_systems()
    print(f"common window: {COMMON_START} .. {COMMON_END}\n")
    for name, trades in systems:
        if not trades:
            print(f"{name:14s} 0 trades")
            continue
        pnl = np.array([t["pnl"] for t in trades])
        longs = sum(1 for t in trades if t["dir"] > 0)
        print(f"{name:14s} n={len(trades):5d}  long={longs:5d} short={len(trades)-longs:5d}  "
              f"net={pnl.sum():12.2f}  win%={100*(pnl>0).mean():5.1f}  "
              f"first={trades[0]['entry_time']}  last={trades[-1]['entry_time']}")
