import numpy as np, engine as E, sim as S
d = E.load_h4("2013-01-01")

p = E.params(entry_mode="PLAIN", use_adx=False, min_hold_bars=0, safety_stop_atr=0.0, close_friday=False)
ctx = E.build_context(d, p)
tr = S.simulate(ctx, p)
st = S.stats(tr)
print("PLAIN raw:", S.fmt(st), "avg_win", st["avg_win"], "avg_loss", st["avg_loss"])
print("  header:  n=318 PF=1.817 win=43.4 avg_win=43.95 avg_loss=-18.55")
rev = sum(1 for a,b in zip(tr, tr[1:]) if a["exit_i"] == b["entry_i"])
print(f"  same-bar reversals: {rev} of {len(tr)}  -> no-reversal count would be ~{len(tr)-0}")
sig = E.entry_signal(ctx, p)
print("  raw signal bars:", int((sig!=0).sum()), " long", int((sig==1).sum()), " short", int((sig==-1).sum()))

# how many signals are consumed vs skipped because already in a position
print("\n-- sensitivity: exclude the daily-spaced pre-2013-05 backfill --")
d2 = E.load_h4("2013-05-09")
ctx2 = E.build_context(d2, p); tr2 = S.simulate(ctx2, p)
print("  from 2013-05-09:", S.fmt(S.stats(tr2)))

print("\n-- sensitivity: SMA-ATR (broker iATR) instead of Wilder for the stop --")
pa = E.P_BEST_PLAIN_ADX
ctxa = E.build_context(d, pa)
tra = S.simulate(ctxa, pa); print("  Wilder ATR:", S.fmt(S.stats(tra)))
ctxb = dict(ctxa); ctxb["atr"] = ctxa["atr_sma"]
trb = S.simulate(ctxb, pa); print("  SMA ATR   :", S.fmt(S.stats(trb)))

print("\n-- the v1.04 'worst loss' trade: 2026-05-05 short --")
for sm in (3.5, 2.5):
    pp = E.params(entry_mode="PLAIN", use_adx=True, min_hold_bars=0, safety_stop_atr=sm)
    cc = E.build_context(d, pp); tt = S.simulate(cc, pp)
    w = min(tt, key=lambda t: t["pnl"])
    m = [t for t in tt if str(t["entry_t"])[:10].startswith("2026-05")]
    print(f"  stop={sm}x worst: {str(w['entry_t'])[:16]} dir={w['dir']} pnl={w['pnl']:.2f} reason={w['reason']}")
    for t in m: print(f"        2026-05 trade {str(t['entry_t'])[:16]} dir={t['dir']} pnl={t['pnl']:.2f} {t['reason']}")

print("\n-- v1.04 stop sweep reproduction (PLAIN+ADX, minhold=8, flatten on) --")
for sm in (0.0,1.0,1.5,2.0,2.5,3.0,3.5,5.0):
    pp = E.params(entry_mode="PLAIN", use_adx=True, min_hold_bars=8, safety_stop_atr=sm)
    cc = E.build_context(d, pp); tt = S.simulate(cc, pp)
    ny,ty = S.neg_years(tt)
    print(f"  {sm:4.1f}x  {S.fmt(S.stats(tt))} negyr={ny}/{ty} stops={sum(1 for t in tt if t['reason']=='STOP')}")

print("\n-- exit-reason mix on the shipped-best config (header: flatten is dominant) --")
from collections import Counter
print(" ", Counter(t["reason"] for t in tra))
