"""Consecutive-loss circuit breaker (Zenith_EA.mq5 reference: InpMaxConsecLosses
/InpPauseBars, OnTradeTransaction increments g_consecLosses on a losing close and
resets on a win; the entry gate blocks while TimeCurrent() < g_pausedUntil).
On Aurelius this BACKFIRED. Do not assume it carries over - check Ichimoku's own
loss-streak structure first."""
import numpy as np, engine as E, sim as S
from battery import *

pnl = np.array([t["pnl"] for t in BASE]); wins = pnl > 0
print(f"=== A. Is the win/loss sequence distinguishable from a coin flip? (n={len(pnl)}, win%={100*wins.mean():.1f}) ===")
runs = 1 + int((wins[1:] != wins[:-1]).sum())
nw, nl = int(wins.sum()), int((~wins).sum())
mu = 2*nw*nl/(nw+nl) + 1
sd = np.sqrt(2*nw*nl*(2*nw*nl-nw-nl)/((nw+nl)**2*(nw+nl-1)))
print(f"   Wald-Wolfowitz runs test: runs={runs} expected={mu:.1f} sd={sd:.1f}  z={(runs-mu)/sd:+.2f}")
print("   (|z| < 1.96 => streaks are indistinguishable from independent coin flips)")
rng = np.random.default_rng(0)
maxstreak = lambda w: max((len(list(g)) for k,g in __import__('itertools').groupby(w) if not k), default=0)
real_ms = maxstreak(wins)
sim_ms = np.array([maxstreak(rng.permutation(wins)) for _ in range(5000)])
print(f"   longest real losing streak={real_ms}, shuffled mean={sim_ms.mean():.2f}, "
      f"P(shuffled >= real)={100*(sim_ms>=real_ms).mean():.1f}%")

print("\n=== B. Expectancy CONDITIONAL on the preceding consecutive-loss count ===")
streak = 0; buckets = {}
for t in BASE:
    buckets.setdefault(min(streak,4), []).append(t["pnl"])
    streak = streak + 1 if t["pnl"] <= 0 else 0
for k in sorted(buckets):
    a = np.array(buckets[k])
    lbl = f">={k}" if k == 4 else f"={k}"
    print(f"   after {lbl} consecutive losses: n={len(a):4d} mean=${a.mean():+7.2f} "
          f"win%={100*(a>0).mean():4.1f} net=${a.sum():+8.2f}")

print("\n=== C. Simulate the real Zenith-style rule on Ichimoku (grid + best-of-N) ===")
base_line()
cells = []
for mx in (2,3,4):
    for pb in (6,12,30,60,120):   # H4 bars: 1d, 2d, 5d, 10d, 20d
        def rule(trades, j, mx=mx, pb=pb):
            s = 0; last = None
            for t in trades:
                if t["pnl"] <= 0:
                    s += 1; last = t["exit_i"]
                else:
                    s = 0; last = None
                if s >= mx: break
            return s >= mx and last is not None and j < last + pb
        tr = S.simulate(CTX, P, pause_rule=rule)
        st = S.stats(tr); ny,ty = S.neg_years(tr)
        blocked = len(BASE) - len(tr)
        pm = S.permutation_test(BASE, tr, n_draws=1500) if 15 <= len(tr) <= len(BASE) else None
        cells.append(tr)
        print(f"   max={mx} pause={pb:3d}bars ({pb*4//24:2d}d): {S.fmt(st)} negyr={ny}/{ty} "
              f"blocked={blocked:3d} perm={pm['percentile'] if pm else '-'}")
print("   best-of-N corrected over the 15 breaker cells:",
      S.permutation_test_bestofN(BASE, cells, n_draws=2000))
