"""Validate Python indicator math against MT5's own chk_* columns in GOLD_H4.csv
before trusting anything downstream. Same discipline as the Aurelius rebuild."""
import numpy as np, pandas as pd

DATA = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data/GOLD_H4.csv"

def load_raw():
    d = pd.read_csv(DATA, skiprows=1)
    d["time"] = pd.to_datetime(d["time"], format="%Y.%m.%d %H:%M:%S")
    return d

def ema(x, n):
    a = 2.0/(n+1.0); out = np.full(len(x), np.nan); out[0] = x[0]
    for i in range(1, len(x)): out[i] = a*x[i] + (1-a)*out[i-1]
    return out

def true_range(h,l,c):
    tr = np.empty(len(h)); tr[0] = h[0]-l[0]
    for i in range(1,len(h)):
        tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    return tr

def atr_wilder(h,l,c,n=14):
    tr = true_range(h,l,c); out = np.full(len(h), np.nan)
    if len(h) <= n: return out
    out[n] = tr[1:n+1].mean()
    for i in range(n+1, len(h)): out[i] = (out[i-1]*(n-1)+tr[i])/n
    return out

def atr_sma(h,l,c,n=14):
    tr = true_range(h,l,c); out = np.full(len(h), np.nan)
    s = pd.Series(tr).rolling(n).mean().values
    out[:] = s; out[0:n-1] = np.nan
    return out

if __name__ == "__main__":
    d = load_raw()
    c = d["close"].values.astype(float)
    h = d["high"].values.astype(float); l = d["low"].values.astype(float)
    ok = d.index >= 400   # skip warmup / DBL_MAX garbage
    for n, col in [(3,"chk_ema3"),(21,"chk_ema21"),(150,"chk_ema150")]:
        mine = ema(c, n); ref = d[col].values.astype(float)
        m = ok & np.isfinite(ref) & (np.abs(ref) < 1e6)
        diff = np.abs(mine[m]-ref[m])
        print(f"EMA{n:4d}: n={m.sum()} maxdiff={diff.max():.6f} meandiff={diff.mean():.6f}")
    ref = d["chk_atr14"].values.astype(float)
    m = ok & np.isfinite(ref) & (np.abs(ref) < 1e6)
    for name, f in [("Wilder", atr_wilder), ("SMA", atr_sma)]:
        mine = f(h,l,c,14); dd = np.abs(mine[m]-ref[m])
        print(f"ATR14 {name:7s}: n={m.sum()} maxdiff={dd.max():.6f} meandiff={dd.mean():.6f} "
              f"corr={np.corrcoef(mine[m],ref[m])[0,1]:.6f}")
    # MACD (12,26,9) main line
    macd = ema(c,12)-ema(c,26)
    ref = d["chk_macd"].values.astype(float)
    m = ok & np.isfinite(ref) & (np.abs(ref) < 1e6)
    dd = np.abs(macd[m]-ref[m])
    print(f"MACD main: n={m.sum()} maxdiff={dd.max():.6f} meandiff={dd.mean():.6f}")
