"""
The Aurelius battery, adapted to Ichimoku/H4.

Every candidate is tested as an ADDED ENTRY GATE on top of the shipped-
documented-best config (PLAIN + ADX(14)>20 + MinHoldBars=8 + 2.5xATR stop +
Friday flatten), and judged against the STRICTER null the project adopted
later: random equal-size subsets of that same config's OWN trades. Beating
random bars is not the question; beating the base signal is.

Reported for every cell: n, PF, net, maxDD, negative years, 70/30 IS/OOS,
ex-top-5 net, and the trade-subset permutation percentile. Any family where a
grid was searched also gets a best-of-N corrected percentile.
"""
import numpy as np, pandas as pd
import engine as E, sim as S

d = E.load_h4("2013-01-01")
P = E.P_BEST_PLAIN_ADX
CTX = E.build_context(d, P)
BASE = S.simulate(CTX, P)
N = CTX["n"]
C = CTX["close"]; H = CTX["high"]; L = CTX["low"]; O = CTX["open"]


# ---------------------------------------------------------- indicators
def efficiency_ratio(c, n):
    ch = np.abs(pd.Series(c).diff(n).values)
    vol = pd.Series(np.abs(np.diff(c, prepend=c[0]))).rolling(n).sum().values
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(vol > 0, ch/vol, np.nan)

def rsq_trend(c, n):
    """R^2 of an OLS fit of close on bar index over the last n bars - a
    trend-QUALITY read independent of ADX's DI construction."""
    s = pd.Series(c)
    x = np.arange(n)
    xm = x.mean(); sxx = ((x-xm)**2).sum()
    ym = s.rolling(n).mean()
    sxy = sum((x[k]-xm)*s.shift(n-1-k) for k in range(n))
    syy = s.rolling(n).var(ddof=0)*n
    with np.errstate(divide="ignore", invalid="ignore"):
        r2 = (sxy**2)/(sxx*syy.replace(0, np.nan))
    return r2.values

def choppiness(h, l, c, n):
    tr = pd.Series(E.true_range(h, l, c))
    num = np.log10(tr.rolling(n).sum() /
                   (pd.Series(h).rolling(n).max() - pd.Series(l).rolling(n).min()).replace(0, np.nan))
    return (100*num/np.log10(n)).values

def stoch(h, l, c, k=14, dsm=3):
    hh = pd.Series(h).rolling(k).max(); ll = pd.Series(l).rolling(k).min()
    raw = 100*(pd.Series(c)-ll)/(hh-ll).replace(0, np.nan)
    return raw.rolling(dsm).mean().values

def roll_pct(x, win=500):
    """Rolling percentile rank of x within its own trailing `win` bars.
    Scale-free BY CONSTRUCTION - the discipline that stops a volatility read
    from silently becoming a date filter on a series whose level has trended."""
    s = pd.Series(x)
    return s.rolling(win).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True).values


# ------------------------------------------------------------- harness
def evaluate(label, filt, base=BASE, quiet=False, n_draws=2000):
    tr = S.simulate(CTX, P, extra_filter=filt)
    if len(tr) < 15:
        if not quiet: print(f"  {label:34s} n={len(tr)} - too few to judge")
        return None
    st = S.stats(tr); ny, ty = S.neg_years(tr)
    i_, o_ = S.split_stats(tr, N)
    tc = S.tail_concentration(tr)
    pm = S.permutation_test(base, tr, n_draws=n_draws)
    row = dict(label=label, trades=tr, st=st, ny=ny, ty=ty, IS=i_, OOS=o_, tc=tc, pm=pm)
    if not quiet:
        print(f"  {label:34s} n={st['n']:4d} PF={st['pf']:5.3f} net=${st['net']:8.2f} "
              f"DD={st['maxdd']:7.2f} negyr={ny}/{ty} "
              f"IS_PF={i_['pf']:5.3f} OOS_PF={o_['pf']:5.3f} "
              f"exT5=${tc['ex_top5_net']:8.2f} perm={pm['percentile']:5.1f}")
    return row


def header(t):
    print("\n" + "="*118); print(t); print("="*118)


def base_line():
    st = S.stats(BASE); ny, ty = S.neg_years(BASE)
    i_, o_ = S.split_stats(BASE, N); tc = S.tail_concentration(BASE)
    print(f"  {'BASE (PLAIN+ADX, shipped-best)':34s} n={st['n']:4d} PF={st['pf']:5.3f} "
          f"net=${st['net']:8.2f} DD={st['maxdd']:7.2f} negyr={ny}/{ty} "
          f"IS_PF={i_['pf']:5.3f} OOS_PF={o_['pf']:5.3f} exT5=${tc['ex_top5_net']:8.2f} perm=  -  ")
