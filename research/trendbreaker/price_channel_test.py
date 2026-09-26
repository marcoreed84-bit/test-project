"""
Price Channel / Linear Regression Channel (user's 2026-09-26 textbook,
Errante Academy "The Art of Trend Analysis and Chart Mastery") - standalone
test on real H4 and real native M15, full random-timing + best-of-K
pipeline (pattern_rigor_common.py).

CONSTRUCTION - the objective, non-hand-drawn version of the textbook's
"trendline + parallel return line" channel: a rolling ordinary-least-squares
line fitted to the last W closes (bars t-W+1..t, so the channel at bar t
uses ONLY data up to t's close - no pivots, so no pivot-confirmation lag is
needed; nothing here can see the future), midline = the fitted value at
bar t, bands = midline +/- BAND_K x sigma(residuals). A channel counts as an
ESTABLISHED TREND channel only when R^2 >= MIN_R2 (0.50) - up-channel if the
slope is positive, down-channel if negative; otherwise no signal (ranging
market, the textbook's channels are trend tools). W=100 / BAND_K=2 /
MIN_R2=0.50 are the conventional defaults, fixed a priori; W=50 and W=200
are reported as the only sensitivity checks (and counted in K).

STRATEGIES (decision on bar t's close, filled at c[t] - same convention as
every pattern here; every signal goes through the same single-position
eval_book_pct):
 (a) BOUNCE, with-trend: in an up-channel, the bar's low touches the lower
     band and the bar closes back inside (first touch - previous bar's low
     was above its lower band) -> BUY; stop = lower band - 1.0xATR, target =
     midline (the channel's mean - the textbook "trade the channel back to
     the middle"). Mirror in a down-channel at the upper band -> SELL.
 (a') BOUNCE, counter-trend: the return-line side - up-channel, first touch
     of the UPPER band that closes back inside -> SELL toward the midline
     (stop = upper band + 1.0xATR). Mirror for down-channels.
 (b) BREAKOUT, with-trend (trend acceleration): up-channel, first close
     beyond the upper band by BREAK_TOL_ATR x ATR -> BUY; stop = midline,
     target = entry + one full channel width (upper - lower, ~2R). Mirror
     for down-channels.

K floor: 3 strategies x 3 windows x 2 timeframes = 18 variants in this
file; the channel/regression idea also sits next to this session's many
MA-slope / VWAP-band / S-R distance screens (research/aurelius). K=30 is
the decision threshold, 50/100 shown.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import pattern_rigor_common as R

BAND_K = 2.0
MIN_R2 = 0.50
WINDOWS = (100, 50, 200)
DECISION_K = 30


def rolling_lr(y, W):
    """Rolling OLS of y on x=0..W-1 over bars t-W+1..t. Returns mid (fitted
    value at x=W-1, i.e. bar t), slope per bar, sigma of residuals, R^2 -
    all NaN for t < W-1."""
    n = len(y)
    x = np.arange(W, dtype=float)
    Sx, Sxx = x.sum(), (x * x).sum()
    Sy = pd.Series(y).rolling(W).sum().values
    Syy = pd.Series(y * y).rolling(W).sum().values
    Sxy = np.full(n, np.nan)
    Sxy[W - 1:] = np.convolve(y, x[::-1], mode="valid")
    den = W * Sxx - Sx * Sx
    b = (W * Sxy - Sx * Sy) / den
    a = (Sy - b * Sx) / W
    mid = a + b * (W - 1)
    ss_res = np.maximum(Syy - a * Sy - b * Sxy, 0.0)
    ss_tot = Syy - Sy * Sy / W
    with np.errstate(invalid="ignore", divide="ignore"):
        r2 = 1.0 - ss_res / ss_tot
    sigma = np.sqrt(ss_res / W)
    return mid, b, sigma, r2


def lr_context(c, W, band_k=BAND_K, min_r2=MIN_R2):
    mid, slope, sigma, r2 = rolling_lr(c, W)
    up = (slope > 0) & (r2 >= min_r2)
    dn = (slope < 0) & (r2 >= min_r2)
    return dict(mid=mid, slope=slope, sigma=sigma, r2=r2,
                upper=mid + band_k * sigma, lower=mid - band_k * sigma, up=up, dn=dn)


def detect(h, l, c, atr, ctx):
    n = len(c)
    up, dn, lo_b, hi_b, mid = ctx["up"], ctx["dn"], ctx["lower"], ctx["upper"], ctx["mid"]
    out = dict(bounce_with=[], bounce_counter=[], breakout=[])
    tol = R.BREAK_TOL_ATR
    for t in range(1, n):
        if np.isnan(mid[t]) or np.isnan(mid[t - 1]):
            continue
        a = atr[t]
        entry = c[t]
        width = hi_b[t] - lo_b[t]
        # lower-band first touch, closed back inside
        if l[t] <= lo_b[t] < c[t] and l[t - 1] > lo_b[t - 1]:
            tr = R.make_trade(False, t, entry, lo_b[t] - R.STOP_BUFFER * a, mid[t], n)
            if tr is not None:
                if up[t]:
                    out["bounce_with"].append(tr)
                elif dn[t]:
                    out["bounce_counter"].append(tr)
        # upper-band first touch, closed back inside
        if h[t] >= hi_b[t] > c[t] and h[t - 1] < hi_b[t - 1]:
            tr = R.make_trade(True, t, entry, hi_b[t] + R.STOP_BUFFER * a, mid[t], n)
            if tr is not None:
                if dn[t]:
                    out["bounce_with"].append(tr)
                elif up[t]:
                    out["bounce_counter"].append(tr)
        # with-trend breakout beyond the return line
        if up[t] and c[t] > hi_b[t] + tol * a and not (c[t - 1] > hi_b[t - 1] + tol * atr[t - 1]):
            tr = R.make_trade(False, t, entry, mid[t], entry + width, n)
            if tr is not None:
                out["breakout"].append(tr)
        if dn[t] and c[t] < lo_b[t] - tol * a and not (c[t - 1] < lo_b[t - 1] - tol * atr[t - 1]):
            tr = R.make_trade(True, t, entry, mid[t], entry - width, n)
            if tr is not None:
                out["breakout"].append(tr)
    return out


def run(name, df):
    o, h, l, c, atr = R.arrays(df)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    t = df["time"].values
    summ = []
    for W in WINDOWS:
        ctx = lr_context(c, W)
        sig = detect(h, l, c, atr, ctx)
        print("\n" + "=" * 100)
        print(f"{name}: n={len(c)} bars, {years:.2f} yrs, LR window W={W}  (trend-channel bars: "
              f"{100*np.mean(ctx['up']|ctx['dn']):.0f}%)  raw signals: "
              + ", ".join(f"{k}={len(v)}" for k, v in sig.items()))
        print("=" * 100)
        for key, label in (("bounce_with", "bounce off band, with-trend -> midline"),
                           ("bounce_counter", "bounce off return line, counter-trend -> midline"),
                           ("breakout", "breakout beyond return line (acceleration)")):
            res = R.eval_book_pct(sig[key], h, l, c, times=t)
            summ.append(R.rigor_report(f"{name} W={W} {label}", res, h, l, c))
    return summ


if __name__ == "__main__":
    summ = []
    summ += run("H4", R.load_h4_real())
    summ += run("M15", R.load_m15_real())
    R.verdict_table(summ, DECISION_K)
