"""
The standing regime/edge-test battery, applied to Fulcrum's real baseline
signal. Deliberately the SAME candidate families already run (and rejected)
for Aurelius and Ichimoku this session - Kaufman Efficiency Ratio, ADX,
ATR-as-%-of-price rolling percentile, and a consecutive-loss circuit
breaker - plus the one Fulcrum-specific parameter question: Aurelius's
InpMinSRDistATR turned out to be improvable 0.50 -> 1.50 (real-MT5
confirmed); Fulcrum still ships 0.50 on BOTH timeframes, so that value is
tested against its own neighbours here rather than assumed to transfer.

Rigor per cell: n / PF / net / maxDD / win%, negative years, chronological
70/30 IS/OOS, ex-top-5 net (tail concentration), and a permutation
percentile against random equal-size draws from the BASELINE's own trades.
Any family where a grid was searched also gets a best-of-N corrected
percentile, because keeping the best of N cells needs a best-of-N null.

Usage:  python3 battery.py m5 | m15
"""
import sys

import numpy as np
import pandas as pd

import engine as E
import sim as S

WHICH = (sys.argv[1] if len(sys.argv) > 1 else "m5").lower()
P = E.P if WHICH == "m5" else E.P15
DF, H4, CTX = E.build_all(P)
BASE = S.simulate(CTX, params=P)
N = CTX["n"]
C, H, L, O = CTX["close"], CTX["high"], CTX["low"], CTX["open"]
YEAR = pd.DatetimeIndex(CTX["time"]).year.values


from indicators import true_range, efficiency_ratio, adx, roll_pct


# ---------------------------------------------------------------- harness
def _row(label, tr, base=BASE, n_draws=2000, quiet=False):
    if len(tr) < 15:
        if not quiet:
            print(f"  {label:38s} n={len(tr)} - too few to judge")
        return None
    st = S.stats(tr)
    pnl = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in tr])
    ny, ty = S.neg_years(tr)
    i_, o_ = S.split_stats(tr, N)
    tc = S.tail_concentration(tr)
    pm = S.permutation_test(base, tr, n_draws=n_draws) if tr is not base else None
    if not quiet:
        print(f"  {label:38s} n={st['n']:4d} PF={st['pf']:5.3f} net=${st['net']:8.1f} "
              f"win={100*st['win_rate']:4.1f}% DD={S.max_dd(pnl):6.1f} negyr={ny}/{ty} "
              f"IS_PF={i_['pf']:5.3f} OOS_PF={o_['pf']:5.3f} exT5=${tc['ex_topk_net']:7.1f} "
              f"perm={('%5.1f' % pm['percentile']) if pm else '  -  '}")
    return dict(label=label, trades=tr, st=st, ny=ny, ty=ty, IS=i_, OOS=o_, tc=tc, pm=pm)


def evaluate(label, filt, **kw):
    return _row(label, S.simulate(CTX, params=P, extra_filter=filt), **kw)


def header(t):
    print("\n" + "=" * 130)
    print(f"{t}   [{WHICH.upper()}]")
    print("=" * 130)


def base_line():
    _row(f"BASE (shipped defaults, {WHICH.upper()})", BASE, base=BASE, quiet=False)


def bestofN(cells, label="best-of-N corrected"):
    sets = [c["trades"] for c in cells if c]
    print(f"  {label} ({len(sets)} cells searched): {S.permutation_test_bestofN(BASE, sets)}")


# ================================================================= TEST 0
header("TEST 0 - InpMinSRDistATR: does Fulcrum's shipped 0.50 transfer to "
       "Aurelius's confirmed 1.50, or is 0.50 already right here?")
base_line()
print("  (a) TRUE parameter sweep - re-runs the whole sim with the input changed, "
      "so cooldown/occupancy effects are real, not a post-hoc filter)")
cells0 = []
for v in (0.00, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00):
    p = dict(P)
    p["min_sr_dist_atr"] = v
    p["use_sr_dist"] = v > 0.0
    r = _row(f"min_sr_dist_atr = {v:.2f}" + ("  <- SHIPPED" if abs(v - P["min_sr_dist_atr"]) < 1e-9 else ""),
             S.simulate(CTX, params=p))
    if r and abs(v - P["min_sr_dist_atr"]) > 1e-9:
        cells0.append(r)
bestofN(cells0)

# ================================================================= TEST 1
header("TEST 1 - Kaufman EFFICIENCY RATIO as an added regime gate")
base_line()
cells1 = []
for n_er in (20, 50, 100):
    er = efficiency_ratio(C, n_er)
    erp = roll_pct(er, 500)
    for thr in (0.10, 0.15, 0.20, 0.25):
        f = (lambda a, t: (lambda ctx, i, b: np.isfinite(a[i]) and a[i] >= t))(er, thr)
        cells1.append(evaluate(f"ER({n_er}) >= {thr} absolute", f))
    for q in (0.3, 0.5, 0.7):
        f = (lambda a, t: (lambda ctx, i, b: np.isfinite(a[i]) and a[i] >= t))(erp, q)
        cells1.append(evaluate(f"ER({n_er}) rollpct >= {q}", f))
bestofN(cells1)

# ================================================================= TEST 2
header("TEST 2 - ADX(14) as an added regime gate")
base_line()
ADX = adx(H, L, C, 14)
print(f"  ADX(14) at baseline entries: median={np.nanmedian([ADX[t['entry_i']-1] for t in BASE]):.1f}")
cells2 = []
for th in (15, 18, 20, 22, 25, 30, 35):
    f = (lambda t: (lambda ctx, i, b: np.isfinite(ADX[i]) and ADX[i] > t))(th)
    cells2.append(evaluate(f"ADX(14) > {th}", f))
for lb in (3, 6):
    rise = ADX - pd.Series(ADX).shift(lb).values
    f = (lambda a: (lambda ctx, i, b: np.isfinite(a[i]) and a[i] > 0))(rise)
    cells2.append(evaluate(f"ADX(14) rising vs {lb} bars ago", f))
bestofN(cells2)

# ================================================================= TEST 3
header("TEST 3 - ATR-as-%-of-price, ROLLING PERCENTILE (disguised-date-filter check)")
atrp = CTX["atr"] / C
for y in np.unique(YEAR):
    m = YEAR == y
    print(f"    {y}: median ATR%/price = {np.nanmedian(atrp[m]):.5f}   "
          f"median ATR = ${np.nanmedian(CTX['atr'][m]):.2f}")
print("  -> an ABSOLUTE ATR or ATR% cutoff on this series is a disguised date filter; "
      "only the rolling-percentile form is tested.")
base_line()
cells3 = []
win = 8640 if WHICH == "m5" else 2880      # ~1 month of bars on each timeframe
for w, wl in ((win, "1mo"), (3 * win, "3mo")):
    ap = roll_pct(atrp, w)
    for lo, hi in ((0.0, 0.5), (0.5, 1.0), (0.0, 0.33), (0.33, 0.67), (0.67, 1.0)):
        f = (lambda a, l_, h_: (lambda ctx, i, b: np.isfinite(a[i]) and l_ <= a[i] < h_))(ap, lo, hi)
        cells3.append(evaluate(f"ATR% rollpct({wl}) in [{lo},{hi})", f))
bestofN(cells3)

# ================================================================= TEST 4
header("TEST 4 - consecutive-loss circuit breaker (Zenith's real mechanism)")
base_line()
# diagnostic: is there any streak structure to exploit at all?
pnl = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in BASE])
streak = 0
after = {}
for k in range(len(pnl) - 1):
    streak = streak + 1 if pnl[k] <= 0 else 0
    after.setdefault(min(streak, 12), []).append(pnl[k + 1])
print("  next-trade mean pnl given the current loss streak (a real breaker needs this to FALL):")
print("   ", {k: (len(v), round(float(np.mean(v)), 2)) for k, v in sorted(after.items())})
cells4 = []
bar_per_day = 288 if WHICH == "m5" else 96
for mc in (3, 4, 5, 6, 8):
    for pb_days in (1, 3, 5):
        p = dict(P)
        p.update(use_consec_breaker=True, max_consec_losses=mc, pause_bars=pb_days * bar_per_day)
        cells4.append(_row(f"breaker: {mc} losses -> pause {pb_days}d", S.simulate(CTX, params=p)))
bestofN(cells4)
# information-free control: same number of pauses, fired at uninformative closes
best4 = max((c for c in cells4 if c), key=lambda c: c["st"]["net"], default=None)
if best4:
    mc, pbd = [int(x) for x in (best4["label"].split(":")[1].split("losses")[0].strip(),
                                best4["label"].split("pause ")[1].rstrip("d"))]
    n_real_pauses = None
    rng = np.random.default_rng(7)
    nets = []
    for s in range(40):
        rr = np.random.default_rng(100 + s)
        p = dict(P)
        p.update(use_consec_breaker=True, max_consec_losses=mc, pause_bars=pbd * bar_per_day,
                 breaker_rule=(lambda cl, pnl_, ei, _r=rr: _r.random() < 0.06))
        nets.append(S.stats(S.simulate(CTX, params=p))["net"])
    nets = np.array(nets)
    print(f"  information-free control (pause at random closes at a similar rate, 40 seeds): "
          f"net mean={nets.mean():.1f} sd={nets.std():.1f} | real best={best4['st']['net']:.1f} "
          f"| baseline={S.stats(BASE)['net']:.1f}")
