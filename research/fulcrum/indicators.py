"""Candidate-regime indicators for the Fulcrum battery. Same constructions
already used against Aurelius and Ichimoku this session (research/ichimoku/
battery.py, research/aurelius/atr_pct_regime_test.py) - lifted into their own
module so battery.py and confirm.py share one definition instead of two."""
import numpy as np
import pandas as pd


def true_range(h, l, c):
    tr = np.empty(len(h))
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    return tr


def efficiency_ratio(c, n):
    """Kaufman ER: |net move over n bars| / |total path over n bars|.
    1.0 = perfectly efficient trend, 0.0 = pure chop."""
    ch = np.abs(pd.Series(c).diff(n).values)
    vol = pd.Series(np.abs(np.diff(c, prepend=c[0]))).rolling(n).sum().values
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(vol > 0, ch / vol, np.nan)


def adx(h, l, c, n=14):
    """Wilder ADX - the same smoothing the EA's own ATR already uses."""
    up = np.diff(h, prepend=h[0])
    dn = -np.diff(l, prepend=l[0])
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(h, l, c)

    def wilder(x):
        out = np.full(len(x), np.nan)
        if len(x) <= n:
            return out
        out[n] = x[1:n + 1].sum()
        for i in range(n + 1, len(x)):
            out[i] = out[i - 1] - out[i - 1] / n + x[i]
        return out

    atr_s, pdm_s, mdm_s = wilder(tr), wilder(plus_dm), wilder(minus_dm)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * pdm_s / atr_s
        mdi = 100 * mdm_s / atr_s
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    out = np.full(len(c), np.nan)
    first = int(np.argmax(np.isfinite(dx)))
    if first + n < len(dx):
        out[first + n] = np.nanmean(dx[first:first + n])
        for i in range(first + n + 1, len(dx)):
            out[i] = (out[i - 1] * (n - 1) + dx[i]) / n
    return out


def roll_pct(x, win):
    """Rolling percentile RANK of x within its own trailing window. Scale-free
    BY CONSTRUCTION - the discipline that stops a volatility read from
    silently becoming a date filter on a series whose level has trended
    (GOLD's median M5 ATR runs $1.02 in 2023 and $5.40 in 2026 on this very
    sample, so any ABSOLUTE ATR cutoff here is a disguised date filter)."""
    return pd.Series(x).rolling(win).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True).values
