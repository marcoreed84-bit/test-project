"""Reproduce the header's own claimed numbers before trusting anything else."""
import numpy as np, engine as E, sim as S

d = E.load_h4("2013-01-01")
print(f"bars={len(d)}  {d.time.iloc[0]} .. {d.time.iloc[-1]}   (header claims 20,571)")

def run(label, p, fill="open", data=None):
    dd = d if data is None else data
    ctx = E.build_context(dd, p)
    tr = S.simulate(ctx, p, fill=fill)
    st = S.stats(tr)
    ny, ty = S.neg_years(tr)
    print(f"{label:52s} {S.fmt(st)} negyr={ny}/{ty}")
    return ctx, tr, st

print("\n=== A. PLAIN + ADX, Friday flatten + 2.5x stop (SHIPPED-BEST config) ===")
print("    header v1.02 claim @3.5x stop: n=190, PF 2.055, net $1262.31")
for sm in (3.5, 2.5, 0.0):
    for fl in ("open", "close"):
        run(f"PLAIN+ADX stop={sm}x fill={fl}", E.params(entry_mode="PLAIN", use_adx=True,
            min_hold_bars=0, safety_stop_atr=sm, close_friday=True), fill=fl)

print("\n=== B. same + InpMinHoldBars=8 (v1.03) ===")
for mh in (0, 4, 8):
    run(f"PLAIN+ADX minhold={mh} stop=2.5", E.params(entry_mode="PLAIN", use_adx=True,
        min_hold_bars=mh, safety_stop_atr=2.5, close_friday=True))

print("\n=== C. PLAIN unfiltered baseline (header v1.00: n=318, PF 1.817, win 43.4) ===")
run("PLAIN no-ADX, no flatten, no stop, no minhold", E.params(entry_mode="PLAIN",
    use_adx=False, min_hold_bars=0, safety_stop_atr=0.0, close_friday=False))
run("PLAIN no-ADX + flatten + 3.5x stop", E.params(entry_mode="PLAIN",
    use_adx=False, min_hold_bars=0, safety_stop_atr=3.5, close_friday=True))

print("\n=== D. BREAKOUT_FULL (header v1.00: n=53, PF 2.474, win 37.7, IS 2.736/OOS 2.181) ===")
run("BF un-flattened, no stop, no minhold", E.P_BREAKOUT_VALIDATED)
run("BF + flatten + 2.5x stop + minhold8 (FILE DEFAULT)", E.P_FILE_DEFAULT)

print("\n=== E. 2022-01..2026-09 window (the real MT5 run window) ===")
d22 = d[d.time >= "2022-01-01"].reset_index(drop=True)
print("    header claim: PLAIN+ADX n=56 PF 1.856 ; unfiltered baseline PF 1.543")
for lbl, p in [("PLAIN+ADX stop3.5 minhold0", E.params(entry_mode="PLAIN", use_adx=True, min_hold_bars=0, safety_stop_atr=3.5)),
               ("PLAIN+ADX stop2.5 minhold8", E.P_BEST_PLAIN_ADX),
               ("PLAIN unfiltered stop3.5", E.params(entry_mode="PLAIN", use_adx=False, min_hold_bars=0, safety_stop_atr=3.5))]:
    run(lbl + " [2022+]", p, data=d22)
