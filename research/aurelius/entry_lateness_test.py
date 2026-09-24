"""
Tests the user's real, live-trading observation (2026-09-24): watching Aurelius
M15 in real time, by the time it fires, the trend already looks over, and price
often reverses right after entry. Four real M15 trades in a row (2026-09-14 to
2026-09-24) were all stop-outs, price moving straight against the position from
entry. That alone isn't proof of anything - it's also just what every losing
trade in a ~40%-win-rate system looks like. This script asks the real, testable
version: across ALL 428 real M15 trades (shipped v1.54 config), do LOSING
trades enter systematically later in the trend / after more of the move has
already happened than WINNING trades do?

Two "lateness" measures, both computed causally (no lookahead) at the entry
bar using engine.py's own aligned_buy/aligned_sell arrays:
  1. Alignment age: how many consecutive bars (including the entry bar) the
     trade's own direction has already been continuously aligned - a fresh
     cross has age 1, a stale, long-confirmed trend has a large age.
  2. Price already covered: ATR-normalized distance from where the CURRENT
     aligned run started to the entry price - how much of the move already
     happened by the time this trade got in, relative to that bar's own ATR.

Real GOLD# M15 data (resampled from the same M5 export every other Aurelius
M15 script uses), shipped v1.54 defaults (E.P15), same simulator as every
other real-vs-Python comparison this session.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S

df5 = E.load_m5()
h4 = E.load_h4()
df15 = E.resample_m15_from_m5(df5)
ctx = E.build_context(df15, h4, params=E.P15)
trades = S.simulate(ctx, params=E.P15)

aligned_buy = ctx["aligned_buy"]
aligned_sell = ctx["aligned_sell"]
atr = ctx["atr"]
close = ctx["close"]

n = ctx["n"]


def run_start(aligned, i):
    """Index of the first bar of the CURRENT unbroken aligned run ending at i."""
    j = i
    while j > 0 and aligned[j - 1]:
        j -= 1
    return j


ages = []
covered = []
pnls = []
dirs = []
for t in trades:
    i = t["entry_i"]
    d = t["dir"]
    al = aligned_buy if d > 0 else aligned_sell
    if not al[i]:
        continue  # shouldn't happen, entry requires alignment, but guard anyway
    start = run_start(al, i)
    age = i - start + 1
    a = atr[i]
    if a <= 0 or np.isnan(a):
        continue
    dist = (close[i] - close[start]) * d / a  # +ve = already moved favorably by this much (xATR)
    pnl = (t["exit_px"] - t["entry_px"]) * d
    ages.append(age)
    covered.append(dist)
    pnls.append(pnl)
    dirs.append(d)

ages = np.array(ages)
covered = np.array(covered)
pnls = np.array(pnls)
win = pnls > 0
lose = ~win

print(f"trades analyzed: {len(pnls)} (of {len(trades)} total)  win={win.sum()} lose={lose.sum()}")
print()
print("ALIGNMENT AGE (bars the trend was already confirmed before entry, M15 bars):")
print(f"  winners: mean={ages[win].mean():.1f}  median={np.median(ages[win]):.1f}")
print(f"  losers:  mean={ages[lose].mean():.1f}  median={np.median(ages[lose]):.1f}")
print()
print("PRICE ALREADY COVERED since the alignment run started (x ATR at entry):")
print(f"  winners: mean={covered[win].mean():.2f}  median={np.median(covered[win]):.2f}")
print(f"  losers:  mean={covered[lose].mean():.2f}  median={np.median(covered[lose]):.2f}")
print()

# correlation: does entering later (higher age / more covered) predict a worse outcome?
from numpy import corrcoef
print(f"correlation(age, pnl):      {corrcoef(ages, pnls)[0,1]:+.3f}")
print(f"correlation(covered, pnl):  {corrcoef(covered, pnls)[0,1]:+.3f}")

# quartile split: does the "latest" quartile of entries (by covered-distance) underperform?
q75 = np.percentile(covered, 75)
q25 = np.percentile(covered, 25)
late = covered >= q75
early = covered <= q25
print()
print(f"LATEST quartile entries (covered >= {q75:.2f}x ATR already moved): n={late.sum()}  "
      f"win%={100*win[late].mean():.1f}  avg pnl={pnls[late].mean():.2f}")
print(f"EARLIEST quartile entries (covered <= {q25:.2f}x ATR already moved): n={early.sum()}  "
      f"win%={100*win[early].mean():.1f}  avg pnl={pnls[early].mean():.2f}")
