"""Trace: for real BT1 (EA v1.00) Gold trades with NO same-direction HS.DEFAULTS sim trade within 24h,
identify the pattern v1.00 traded (via a v1.00-configured, look-ahead-fixed sim that bar-matches 99%)
and report what the HS.DEFAULTS (v1.08) sim did with that SAME pattern."""
import sys, types
sys.path.insert(0, "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad")
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
import engine as E
from hs_gold_rootcause import load_real, UP, REPORTS


def instrumented(strict):
    src = open("/home/user/test-project/research/trendbreaker/hs_sim.py").read()
    reps = [
        ('known_keys = set()  #', 'allpats = []; simulate.allpats = allpats\n    known_keys = set()  #'),
        ('pending.append(P)', 'pending.append(P); P["disc_k"] = k; P["fate"] = "never_confirmed"; allpats.append(P)'),
        ('confirmed.append(P)', 'confirmed.append(P); P["fate"] = "confirmed_no_trigger"'),
        ('if age_bars > params["pullback_window_bars"]:\n                        P["traded"] = True',
         'if age_bars > params["pullback_window_bars"]:\n                        P["traded"] = True; P["fate"] = "retest_window_expired"'),
        ('if not can_open:\n                    P["traded"] = True',
         'if not can_open:\n                    P["fate"] = "trigger_while_busy" if pos is not None else "spread_block"; P["trig_k"] = k\n                    P["traded"] = True'),
        ('P["traded"] = True\n                tp = None', 'P["traded"] = True; P["fate"] = "ENTERED"; P["trig_k"] = k\n                tp = None'),
        ('pos = dict(dir=d, entry_px=entry, stop=P["stop"], tp=tp, fill_i=k + 1)',
         'pos = dict(dir=d, entry_px=entry, stop=P["stop"], tp=tp, fill_i=k + 1, key=(P["t_s1"], P["t_head"], P["t_s2"], P["top"]))'),
        ('pnl=pnl, pnl_pct=pnl / pos["entry_px"], reason=reason))', 'pnl=pnl, pnl_pct=pnl / pos["entry_px"], reason=reason, key=pos["key"]))'),
    ]
    for a, b in reps:
        assert a in src, a
        src = src.replace(a, b)
    src = src.replace('P["traded"] = True\n                    continue\n                if (not is_buy)', 'P["traded"] = True; P["fate"] = "invalid_tp_sl"\n                    continue\n                if (not is_buy)')
    src = src.replace('P["traded"] = True\n                    continue\n                P["traded"] = True; P["fate"]', 'P["traded"] = True; P["fate"] = "invalid_tp_sl"\n                    continue\n                P["traded"] = True; P["fate"]')
    if strict:
        o = 'find_swings_window(cand_idx, isH, isL, h, l, atr, params["swing_min_atr"], win_start, k)'
        src = src.replace(o, o.replace('win_start, k)', 'win_start + N, k - N)'))
    m = types.ModuleType("hsi"); exec(compile(src, "hsi", "exec"), m.__dict__)
    return m


lo, hi = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-09-25")
df = E.load_m15_native()
df = df[(df.time >= lo - pd.Timedelta(days=90)) & (df.time <= hi + pd.Timedelta(days=1))].reset_index(drop=True)[["time", "open", "high", "low", "close", "spread"]]
k0 = int(np.searchsorted(df.time.values, np.datetime64(lo)))
T = df.time.values

H1 = instrumented(True)
v100 = dict(H1.DEFAULTS, point=0.01, start_k=k0, lookback_bars=3000, recompute_every_bars=1, break_tol_atr=0.10,
            stop_buffer_atr=0.3, use_pullback_entry=False, use_runner=False)
tr_v100 = H1.simulate(df, v100)
v100_by_bar = {pd.Timestamp(T[t["entry_i"]]).floor("15min"): t for t in tr_v100}
v100_pats = {(P["t_s1"], P["t_head"], P["t_s2"], P["top"]): P for P in H1.simulate.allpats}

H2 = instrumented(False)   # exactly what hs_gold_bar_match_check.py ran (HS.DEFAULTS, original window)
tr_def = H2.simulate(df, dict(H2.DEFAULTS, point=0.01, start_k=k0))
def_pats = {(P["t_s1"], P["t_head"], P["t_s2"], P["top"]): P for P in H2.simulate.allpats}
def_t = np.array(sorted(T[t["entry_i"]] for t in tr_def))
def_dir = {pd.Timestamp(T[t["entry_i"]]): t["dir"] for t in tr_def}

real = [r for r in load_real(UP + REPORTS["bt1"], "GOLD") if lo <= r["time"] <= hi]
unmatched = []
for r in real:
    a = np.searchsorted(def_t, np.datetime64(r["time"] - pd.Timedelta(hours=24)))
    b = np.searchsorted(def_t, np.datetime64(r["time"] + pd.Timedelta(hours=24)), side="right")
    if not any(def_dir[pd.Timestamp(x)] == r["side"] for x in def_t[a:b]):
        unmatched.append(r)
print(f"real BT1 trades with no same-dir HS.DEFAULTS sim trade within 24h: {len(unmatched)}/{len(real)}")

from collections import Counter
fates = Counter(); rows = []
ts = lambda s: pd.Timestamp(int(s), unit="s")
for r in unmatched:
    tv = v100_by_bar.get(r["time"].floor("15min"))
    if tv is None:
        fates["(no exact v1.00-sim match)"] += 1; continue
    key = tv["key"]
    P = def_pats.get(key)
    if P is None:
        f = "pattern never discovered by DEFAULTS sim"
    else:
        f = P["fate"]
        if f == "never_confirmed":
            # would it have confirmed at v1.00's 0.10 ATR tolerance? (the v1.00 sim says yes - it traded it)
            f = "discovered, never confirmed at 0.35xATR break-tol (confirmed at 0.10 in v1.00)"
    fates[f] += 1
    rows.append((r, key, f, v100_pats[key], P))
print("\nFate, in the HS.DEFAULTS (v1.08-config) sim, of the SAME pattern the real v1.00 EA traded:")
for f, c in fates.most_common():
    print(f"  {c:4d}  {f}")

print("\nSample traces (first 10, spread across the window):")
idx = np.linspace(0, len(rows) - 1, 10).astype(int)
for i in idx:
    r, key, f, Pv, Pd = rows[i]
    side = "BUY " if r["side"] > 0 else "SELL"
    print(f"\n REAL {side} {r['time']} @ {r['price']:.2f}  pattern {'top' if key[3] else 'inverse'}: "
          f"S1 {ts(key[0])}  head {ts(key[1])}  S2 {ts(key[2])}")
    print(f"   v1.00 sim: discovered {pd.Timestamp(T[Pv['disc_k']])}, break confirmed {pd.Timestamp(T[Pv['brk_i']])} "
          f"(0.10xATR, 3 closes) -> immediate market entry next bar open (= real fill bar)")
    if Pd is None:
        print("   DEFAULTS sim: pattern never discovered")
    else:
        extra = ""
        if Pd.get("brk_i", -1) >= 0:
            extra += f", confirmed {pd.Timestamp(T[Pd['brk_i']])} (0.35xATR)"
        if "trig_k" in Pd:
            extra += f", retest trigger bar {pd.Timestamp(T[Pd['trig_k']])}"
        print(f"   DEFAULTS sim: discovered {pd.Timestamp(T[Pd['disc_k']])}{extra} -> {Pd['fate']}")
