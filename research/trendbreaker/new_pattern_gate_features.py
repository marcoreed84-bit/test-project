"""
Part B of the 2026-09-26 textbook batch: can any of the four new
constructions (fan / LR channel / pitchfork / diamond) IMPROVE the four KEPT
EAs (H&S, Ratchet, Aurelius M5+M15, Meridian) as an extra entry GATE -
entries/exits otherwise unchanged? Same structure as the MSG Aurelius
trend-gate research (research/msg/sim.py trend_gate + run_aurelius_gate.py):
the gate is wired INTO each EA's own sequential simulator (a rejected signal
is simply not taken, so a freed position slot can change which later
signals fire - never "delete rows from a finished trade list"), judged on a
genuine IS/OOS split, with a count-matched random-rejection null.

This file only builds the gate FEATURES and the shared walk-forward harness;
each EA has its own runner (the EAs' simulators live in different dirs and
share module names like sim.py/bars.py, so they can't share one process):
  research/trendbreaker/hs_new_pattern_gate_test.py
  research/ratchet/new_pattern_gate_test.py
  research/aurelius/aurelius_new_pattern_gate_test.py   (M5 + M15)
  research/aurelius/meridian_new_pattern_gate_test.py

CONTEXT TIMEFRAME: the structure features are computed on real H4
(load_h4_real) - the natural "higher-timeframe confluence" use the textbook
describes - and mapped onto the EA's own bars CAUSALLY: an EA decision taken
at the close of its bar i may only see H4 bars whose own close (open + 4h)
is <= that moment. The own-timeframe LR slope (G4) is computed directly on
the EA's bars (rolling OLS through bar i only).

GATES (d = +1 long / -1 short; each returns True = allow). Eight, fixed
BEFORE looking at any result; the diamond is NOT used as a gate - it fires
~3/yr on H4 (see diamond_reversal_test.py), far too rarely to filter anything.
  G1 lr_h4_slope_with        H4 LR(100) slope sign == d
  G2 lr_h4_side_with         EA price on the trade's side of the H4 LR(100)
                             midline (the user's own example: "only take H&S
                             trades when price is also above the LR median")
  G3 lr_h4_chan_not_against  block only if an ESTABLISHED H4 channel (R^2>=0.5)
                             points against d
  G4 lr_own_slope_with       own-timeframe LR(100) slope sign == d
  G5 fork_h4_with            newest live H4 Andrews pitchfork points with d
                             (user's example: "only take Ratchet trades where a
                             pitchfork median line agrees with trade direction")
  G6 fork_h4_not_against     block only if the live H4 fork points against d
  G7 fan_h4_no_recent_opp    block if an opposite-direction H4 fan 3rd-line
                             break (the fan's reversal signal) completed within
                             the last 30 H4 bars (~5 trading days)
  G8 lr_h4_not_overextended  block longs above the H4 upper band / shorts below
                             the lower band (don't chase outside the channel)

WALK-FORWARD RULE (fixed up front): pick, on IS only, the gate with the best
IS %PF among gates that keep >= 40% of IS trades; adopt it only if it beats
the ungated IS %PF. Then report that ONE gate's OOS %PF vs ungated OOS, per
OOS half, and against a count-matched null (the same EA with signals rejected
at random at the SAME rate the chosen gate rejects on OOS, N_NULL runs). All
eight gates' IS/OOS numbers are printed too, so nothing is hidden, but only
the IS-selected gate is a real out-of-sample test - the rest is in-sample
browsing of 8 options and is labelled as such.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import pattern_rigor_common as R
from price_channel_test import lr_context
import andrews_pitchfork_test as AP
import fan_principle_test as FP

LR_W = 100
FAN_RECENT_BARS = 30
MIN_RETENTION = 0.40
N_NULL = 200
GATE_NAMES = ("G1 lr_h4_slope_with", "G2 lr_h4_side_with", "G3 lr_h4_chan_not_against",
              "G4 lr_own_slope_with", "G5 fork_h4_with", "G6 fork_h4_not_against",
              "G7 fan_h4_no_recent_opp", "G8 lr_h4_not_overextended")

_H4_CACHE = {}


def h4_features():
    """Per-H4-bar feature arrays (real H4 only), cached."""
    if "f" in _H4_CACHE:
        return _H4_CACHE["f"]
    h4 = R.load_h4_real()
    o, h, l, c, atr = R.arrays(h4)
    n = len(c)
    lr = lr_context(c, LR_W)
    chan = np.where(lr["up"], 1, np.where(lr["dn"], -1, 0))
    events, _ = R.causal_swing_events(o, h, l, c, atr)
    fork = np.zeros(n, dtype=int)
    AP.detect(h, l, c, atr, events, state=fork)
    fan_sig, _ = FP.detect(h4)
    last_bull = np.full(n, -10 ** 9); last_bear = np.full(n, -10 ** 9)
    for tr in fan_sig[3]:
        q = tr["brk_q"]
        if tr["top"]:
            last_bear[q] = q
        else:
            last_bull[q] = q
    last_bull = np.maximum.accumulate(last_bull)
    last_bear = np.maximum.accumulate(last_bear)
    close_time = (h4["time"] + pd.Timedelta(hours=4)).values
    f = dict(close_time=close_time, slope=np.sign(np.nan_to_num(lr["slope"])).astype(int),
             mid=lr["mid"], upper=lr["upper"], lower=lr["lower"], chan=chan, fork=fork,
             last_bull_fan=last_bull, last_bear_fan=last_bear)
    _H4_CACHE["f"] = f
    return f


def map_features(times, closes, bar_minutes):
    """Map H4 features onto an EA's own bars. times = EA bar OPEN times,
    closes = EA closes. Feature row i = what is knowable at the close of EA
    bar i. Returns dict of per-EA-bar arrays."""
    f = h4_features()
    decision = pd.to_datetime(times) + pd.Timedelta(minutes=bar_minutes)
    j = np.searchsorted(f["close_time"], decision.values, side="right") - 1
    valid = j >= 0
    jj = np.where(valid, j, 0)
    own_slope = np.sign(np.nan_to_num(lr_context(np.asarray(closes, float), LR_W)["slope"])).astype(int)
    out = dict(valid=valid, close=np.asarray(closes, float),
               h4_slope=np.where(valid, f["slope"][jj], 0),
               h4_mid=np.where(valid, f["mid"][jj], np.nan),
               h4_upper=np.where(valid, f["upper"][jj], np.nan),
               h4_lower=np.where(valid, f["lower"][jj], np.nan),
               h4_chan=np.where(valid, f["chan"][jj], 0),
               h4_fork=np.where(valid, f["fork"][jj], 0),
               bars_since_bull_fan=np.where(valid, jj - f["last_bull_fan"][jj], 10 ** 9),
               bars_since_bear_fan=np.where(valid, jj - f["last_bear_fan"][jj], 10 ** 9),
               own_slope=own_slope)
    return out


def make_gates(F):
    """dict name -> gate(i, d) -> bool (True = allow), i = EA decision bar."""
    c = F["close"]

    def g1(i, d): return F["h4_slope"][i] == d
    def g2(i, d):
        m = F["h4_mid"][i]
        return (not np.isnan(m)) and ((c[i] > m) if d > 0 else (c[i] < m))
    def g3(i, d): return F["h4_chan"][i] != -d
    def g4(i, d): return F["own_slope"][i] == d
    def g5(i, d): return F["h4_fork"][i] == d
    def g6(i, d): return F["h4_fork"][i] != -d
    def g7(i, d):
        since = F["bars_since_bear_fan"][i] if d > 0 else F["bars_since_bull_fan"][i]
        return since > FAN_RECENT_BARS
    def g8(i, d):
        u, lo = F["h4_upper"][i], F["h4_lower"][i]
        if np.isnan(u):
            return True
        return not ((d > 0 and c[i] > u) or (d < 0 and c[i] < lo))
    return dict(zip(GATE_NAMES, (g1, g2, g3, g4, g5, g6, g7, g8)))


class Counted:
    """Wraps a gate to count how many signals it saw / rejected."""
    def __init__(self, fn):
        self.fn, self.seen, self.rej = fn, 0, 0

    def __call__(self, i, d):
        self.seen += 1
        ok = bool(self.fn(i, d))
        if not ok:
            self.rej += 1
        return ok


def random_gate(rate, rng):
    return lambda i, d: rng.random() >= rate


def pf_of(pcts):
    return R.pct_pf_list(pcts)


def fmt(pcts):
    arr = np.asarray(pcts, float)
    if len(arr) == 0:
        return "n=0"
    return f"n={len(arr):4d} win%={100*(arr>0).mean():5.1f} %PF={pf_of(arr):.3f} net%={100*arr.sum():7.2f}"


def walk_forward(name, run_is, run_oos, F_is, F_oos, oos_half_split=None, n_null=N_NULL, seed=11):
    """run_is/run_oos(gate) -> list of (entry_time, pnl_pct) trades from the
    EA's OWN sequential simulator with `gate` (callable(i, d) or None)
    applied at each would-be entry. Prints the full study, returns a
    summary dict."""
    print("\n" + "#" * 110)
    print(f"# {name}: gate walk-forward (IS = the EA's own build/tuning window, OOS = untouched older data)")
    print("#" * 110)
    base_is = run_is(None); base_oos = run_oos(None)
    bis = [p for _, p in base_is]; boos = [p for _, p in base_oos]
    print(f"  UNGATED  IS : {fmt(bis)}")
    print(f"  UNGATED  OOS: {fmt(boos)}")
    g_is, g_oos = make_gates(F_is), make_gates(F_oos)
    rows = []
    print(f"\n  {'gate':<28} {'IS n':>5} {'keep':>5} {'IS %PF':>7} {'dIS':>7} | {'OOS n':>5} {'OOS %PF':>7} {'dOOS':>7}")
    for gname in GATE_NAMES:
        ti = [p for _, p in run_is(g_is[gname])]
        to = [p for _, p in run_oos(g_oos[gname])]
        r = dict(gate=gname, n_is=len(ti), keep=len(ti) / max(len(bis), 1), pf_is=pf_of(ti),
                 n_oos=len(to), pf_oos=pf_of(to))
        rows.append(r)
        print(f"  {gname:<28} {r['n_is']:>5} {r['keep']:>5.2f} {r['pf_is']:>7.3f} {r['pf_is']-pf_of(bis):>+7.3f} | "
              f"{r['n_oos']:>5} {r['pf_oos']:>7.3f} {r['pf_oos']-pf_of(boos):>+7.3f}")
    n_oos_better = sum(1 for r in rows if r["pf_oos"] > pf_of(boos))
    print(f"  (in-sample browsing only: {n_oos_better}/8 gates show a higher OOS %PF than ungated)")

    cands = [r for r in rows if r["keep"] >= MIN_RETENTION and r["pf_is"] > pf_of(bis)]
    summary = dict(name=name, base_is=pf_of(bis), base_oos=pf_of(boos), n_is=len(bis), n_oos=len(boos),
                   selected=None, n_oos_better=n_oos_better)
    if not cands:
        print("\n  WALK-FORWARD: no gate keeps >=40% of IS trades AND beats ungated IS %PF - nothing to adopt.")
        return summary
    best = max(cands, key=lambda r: r["pf_is"])
    gname = best["gate"]
    cg = Counted(g_oos[gname])
    gated_oos = run_oos(cg)
    go = [p for _, p in gated_oos]
    rate = cg.rej / max(cg.seen, 1)
    print(f"\n  WALK-FORWARD: IS selects [{gname}] (IS %PF {pf_of(bis):.3f} -> {best['pf_is']:.3f}, keeps {100*best['keep']:.0f}%)")
    print(f"    OOS ungated: {fmt(boos)}")
    print(f"    OOS gated  : {fmt(go)}   (gate rejected {cg.rej}/{cg.seen} = {100*rate:.1f}% of signals)")
    if oos_half_split is not None:
        for lbl, sel in (("OOS 1st half", lambda t: t < oos_half_split), ("OOS 2nd half", lambda t: t >= oos_half_split)):
            a = [p for t, p in base_oos if sel(t)]; b = [p for t, p in gated_oos if sel(t)]
            print(f"    {lbl}: ungated %PF={pf_of(a):.3f} (n={len(a)})  gated %PF={pf_of(b):.3f} (n={len(b)})")
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(n_null):
        tr = run_oos(random_gate(rate, rng))
        null.append(pf_of([p for _, p in tr]))
    null = np.array(null); null = null[~np.isnan(null) & ~np.isinf(null)]
    gpf = pf_of(go)
    p = (null >= gpf).mean()
    print(f"    count-matched random-rejection null ({len(null)} runs, same {100*rate:.1f}% rejection rate, same simulator):")
    print(f"      null %PF median={np.median(null):.3f}  p95={np.percentile(null,95):.3f}  -> gated OOS %PF {gpf:.3f} "
          f"at {100*(null<gpf).mean():.1f}th pct (p={p:.3f})")
    helps = gpf > pf_of(boos) and p < 0.05
    print(f"    VERDICT: {'gate HELPS out-of-sample (beats ungated AND the random-rejection null)' if helps else 'gate does NOT measurably help out-of-sample'}")
    summary.update(selected=gname, sel_is=best["pf_is"], sel_oos=gpf, sel_n_oos=len(go), rate=rate, p_null=p,
                   helps=helps, null_med=float(np.median(null)))
    return summary
