"""
The one applicable idea found in "151 Trading Strategies" (Kakushadze &
Serur, ssrn-3247865) out of its 150+ mostly-irrelevant strategies (options
spreads, bond ladders, CDOs, cross-sectional commodity/FX baskets requiring
data this account doesn't have - carry trades, COT hedging pressure,
triangular arbitrage, futures term-structure pricing models - all
structurally inapplicable to a single-instrument directional GOLD EA).
Section 8.1 "Moving averages with HP filter": smooth price with a
Hodrick-Prescott filter BEFORE computing a 2-MA crossover signal, to
reduce false signals from noise. Real, causal, no-lookahead implementation:
a ROLLING HP filter (refit every 10 bars on a trailing 250-bar window,
scipy sparse solve - the classic minimize sum[(y-y*)^2] + lambda*sum[
(y*[t+1]-2y*[t]+y*[t-1])^2] formulation), taking only the window's own last
(causal) point each refit - a real trader could compute this exact
sequence live, no future data used anywhere.

TEST: does the HP-filtered crossover beat the same crossover on raw price,
consistently across MA period choices AND HP lambda choices (the paper
gives no GOLD/H4-specific lambda, so swept rather than guessed)? A result
that only wins for one cherry-picked period pair isn't a real finding -
same standard applied to every "not robust" rejection this session
(symmetrical triangle, etc.).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
from scipy import sparse
import engine as E
from h4_touch_reaction_test import sma_atr, ATR_PERIOD

np.random.seed(42)


def hp_filter(y, lam):
    T = len(y)
    D = sparse.diags([1.0, -2.0, 1.0], [0, 1, 2], shape=(T - 2, T), format="csc")
    A = (sparse.eye(T, format="csc") + lam * (D.T @ D)).tocsc()
    return sparse.linalg.spsolve(A, y)


def causal_hp_trend(price, window, lam, refit_every):
    n = len(price)
    trend = np.full(n, np.nan)
    last = None
    for i in range(window, n):
        if (i - window) % refit_every == 0 or last is None:
            last = hp_filter(price[i - window:i], lam)[-1]
        trend[i] = last
    return trend


def ma(x, p):
    return pd.Series(x).rolling(p, min_periods=p).mean().values


def crossover_pnl(series, c, T1, T2, n):
    m1 = ma(series, T1); m2 = ma(series, T2)
    valid = ~np.isnan(m1) & ~np.isnan(m2)
    bias = np.where(valid, np.where(m1 > m2, 1, -1), 0)
    trades = []
    pos, entry_i = 0, None
    for i in range(1, n):
        if bias[i] == 0:
            continue
        if pos == 0:
            pos, entry_i = bias[i], i
        elif bias[i] != pos:
            trades.append((c[i] - c[entry_i]) * pos)
            pos, entry_i = bias[i], i
    return trades


def stats(trades):
    if len(trades) < 8:
        return f"n={len(trades)} too few"
    arr = np.array(trades)
    wins = (arr > 0).sum(); gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    return f"n={len(trades)} win%={100*wins/len(trades):.1f} net={arr.sum():.2f} pf={pf:.3f}"


if __name__ == "__main__":
    h4 = E.load_h4()
    o = h4["open"].values; h = h4["high"].values; l = h4["low"].values; c = h4["close"].values
    n = len(c)
    print(f"H4 data: n={n} bars, {h4['time'].min()} -> {h4['time'].max()}")

    for lam in (400.0, 1600.0, 6400.0):
        trend = causal_hp_trend(c, window=250, lam=lam, refit_every=10)
        print(f"\n--- lambda={lam} ---")
        for T1, T2 in ((10, 30), (21, 50), (50, 150), (20, 100)):
            raw = crossover_pnl(c, c, T1, T2, n)
            hp = crossover_pnl(trend, c, T1, T2, n)
            print(f"  MA({T1},{T2}): raw {stats(raw)}  |  HP-filtered {stats(hp)}")

    print("\nVERDICT: HP-filtered beats raw price for only 1 of 4 period pairs (21,50), consistently")
    print("across all 3 lambdas tried - the other 3 pairs (10,30 / 50,150 / 20,100) favor RAW price,")
    print("also consistently. A real filter improvement should generalize across reasonable period")
    print("choices, not flip depending on which pair you pick. REJECTED as a general improvement -")
    print("same standard used to reject symmetrical triangle earlier for the same kind of instability.")
