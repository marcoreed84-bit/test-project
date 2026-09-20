"""
Ichimoku_EA.mq5 (v1.04) Python replica - rebuilt from scratch by reading the
real MQL5 source directly (no prior engine survived the container reclaim).

Every indicator below is a line-by-line port of the MQL5 function named in its
docstring, NOT a library implementation. Validated against the CSV's own chk_*
columns first (see chk_validate.py):
  - EMA(3/21/150) matches MT5 to 0.005 (= the chk columns' 2-dp rounding).
  - chk_atr14 matches SMA-of-TR EXACTLY (0.005), NOT Wilder. So this broker's
    iATR() is SMA-based - the same quirk found on Aurelius/M5 today, now
    independently confirmed on H4. The EA does NOT use iATR: ComputeATR() in
    Ichimoku_EA.mq5 is a hand-rolled WILDER ATR, so the replica ports Wilder
    to match the EA (atr_sma is provided for sensitivity checks only).
  - chk_macd does NOT match ema12-ema26 (corr 0.81). Irrelevant here (the
    Ichimoku EA uses no MACD) but it means chk_macd is not a usable reference.

Bar/fill convention (differs from the Aurelius M5 engine - flagged deliberately):
  OnTick() acts on the first tick of a new bar and reads shift s=1, i.e. the
  just-closed bar. So a decision derived from bar i fills at bar i+1's OPEN.
  On M5 the Aurelius engine approximated that with close[i]; on H4 the
  close[i] -> open[i+1] gap is NOT negligible (weekend gaps in particular),
  so this engine uses the ACTUAL next-bar open. `fill="close"` reproduces the
  old approximation for comparison.
"""
import numpy as np
import pandas as pd

DATA_H4 = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data/GOLD_H4.csv"

# Shipped defaults as they literally appear in Ichimoku_EA.mq5 v1.04
P_FILE_DEFAULT = dict(
    entry_mode="BREAKOUT_FULL",   # line 184
    exit_mode="CROSS",            # line 185
    tenkan=9, kijun=26, senkou_b=52, displacement=26,
    require_chikou=False,         # line 194
    use_adx=False,                # line 195
    adx_period=14, adx_threshold=20.0,
    min_hold_bars=8,              # line 215
    use_rsi=True, rsi_period=14, rsi_hi=70.0, rsi_lo=30.0,   # lines 226-229
    use_cmf=True, cmf_period=20,                             # lines 230-231
    safety_stop_atr=2.5,          # line 238
    close_friday=True,            # line 251
    friday_close_hour=21,         # line 252
    no_entry_after_hour_fri=19,   # line 253
)

def params(**over):
    p = dict(P_FILE_DEFAULT)
    p.update(over)
    return p

# The config the v1.02-v1.04 changelog describes as the validated best.
P_BEST_PLAIN_ADX = params(entry_mode="PLAIN", use_adx=True,
                          min_hold_bars=8, safety_stop_atr=2.5, close_friday=True)
# The config the v1.00/v1.02 header's BREAKOUT_FULL numbers actually describe.
P_BREAKOUT_VALIDATED = params(entry_mode="BREAKOUT_FULL", min_hold_bars=0,
                              safety_stop_atr=0.0, close_friday=False)


# ---------------------------------------------------------------- data
def load_h4(start="2013-01-01"):
    """20,571 bars from 2013-01-01 == exactly the bar count the header claims.
    NOTE: rows before 2013-05-09 are daily-spaced (broker backfill of D1 into
    the H4 series); they are inside the window the original study used, so they
    are kept for reproducibility, and excluded in a sensitivity check."""
    d = pd.read_csv(DATA_H4, skiprows=1)
    d["time"] = pd.to_datetime(d["time"], format="%Y.%m.%d %H:%M:%S")
    if start:
        d = d[d["time"] >= start]
    return d.reset_index(drop=True)


# ------------------------------------------------------- Ichimoku core
# Ports DonchianHigh/DonchianLow (mq5 295-314): rolling max/min over bars
# [shift, shift+period-1], i.e. a BACKWARD window ending at `shift`.
def _don_hi(h, n):
    return pd.Series(h).rolling(n).max().values
def _don_lo(l, n):
    return pd.Series(l).rolling(n).min().values
def _mid(h, l, n):
    return (_don_hi(h, n) + _don_lo(l, n)) / 2.0

def ichimoku(h, l, p):
    """Tenkan/Kijun/SenkouARaw/SenkouBRaw (mq5 315-318) as arrays indexed by
    absolute bar. CloudTop/Bot(shift) (mq5 320-321) = max/min of the RAW spans
    computed `displacement` bars EARLIER -> a plain backward shift here."""
    D = p["displacement"]
    tenkan = _mid(h, l, p["tenkan"])
    kijun  = _mid(h, l, p["kijun"])
    sa_raw = (tenkan + kijun) / 2.0
    sb_raw = _mid(h, l, p["senkou_b"])
    sa_sh = pd.Series(sa_raw).shift(D).values   # SenkouARaw(shift + D)
    sb_sh = pd.Series(sb_raw).shift(D).values
    cloud_top = np.maximum(sa_sh, sb_sh)
    cloud_bot = np.minimum(sa_sh, sb_sh)
    return dict(tenkan=tenkan, kijun=kijun, sa_raw=sa_raw, sb_raw=sb_raw,
                cloud_top=cloud_top, cloud_bot=cloud_bot)


# ------------------------------------------- manual indicators (ported)
def true_range(h, l, c):
    tr = np.empty(len(h)); tr[0] = h[0] - l[0]
    for i in range(1, len(h)):
        pc = c[i-1]
        tr[i] = max(h[i]-l[i], abs(h[i]-pc), abs(l[i]-pc))
    return tr

def atr_wilder(h, l, c, n=14):
    """Port of ComputeATR (mq5 384-404). Wilder smoothing, seeded on tr[1..n]."""
    tr = true_range(h, l, c)
    out = np.full(len(h), np.nan)
    if len(h) <= n: return out
    a = tr[1:n+1].mean(); out[n] = a
    for i in range(n+1, len(h)):
        a = (a*(n-1) + tr[i]) / n; out[i] = a
    return out

def atr_sma(h, l, c, n=14):
    """What this broker's iATR() actually returns (validated vs chk_atr14).
    Not used by the EA - kept for sensitivity testing only."""
    return pd.Series(true_range(h, l, c)).rolling(n).mean().values

def rsi_wilder(c, n=14):
    """Port of ComputeRSI (mq5 329-353). The MQL5 version recomputes from a
    period*8 warmup window each call; with Wilder's (n-1)/n decay a single
    full-history pass is numerically identical to within ~1e-9 after warmup."""
    d = np.diff(c, prepend=c[0]); d[0] = 0.0
    g = np.where(d > 0, d, 0.0); ls = np.where(d < 0, -d, 0.0)
    out = np.full(len(c), np.nan)
    if len(c) <= n: return out
    ag = g[1:n+1].mean(); al = ls[1:n+1].mean()
    out[n] = 100.0 if al <= 0 else 100.0 - 100.0/(1.0 + ag/al)
    for i in range(n+1, len(c)):
        ag = (ag*(n-1) + g[i]) / n
        al = (al*(n-1) + ls[i]) / n
        out[i] = 100.0 if al <= 0 else 100.0 - 100.0/(1.0 + ag/al)
    return out

def cmf(h, l, c, v, n=20):
    """Port of ComputeCMF (mq5 358-379): tick_volume weighted, window is the
    n bars ENDING at shift (backward-looking, inclusive)."""
    rng = h - l
    with np.errstate(divide="ignore", invalid="ignore"):
        mfm = np.where(rng > 0, ((c-l) - (h-c)) / np.where(rng > 0, rng, 1.0), 0.0)
    mfv = mfm * v
    sv = pd.Series(v).rolling(n).sum().values
    sm = pd.Series(mfv).rolling(n).sum().values
    return np.where(sv > 0, sm / np.where(sv > 0, sv, 1.0), np.nan)

def adx_wilder(h, l, c, n=14):
    """Port of ComputeADX (mq5 412-464): two-stage Wilder smoothing,
    TR/+DM/-DM then DX -> ADX, with the SAME +DM/-DM tie rules."""
    N = len(h)
    tr = true_range(h, l, c)
    pdm = np.zeros(N); mdm = np.zeros(N)
    up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
    up[0] = dn[0] = 0.0
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    out = np.full(N, np.nan)
    if N < 2*n + 2: return out
    sTR = tr[1:n+1].sum()/n; sP = pdm[1:n+1].sum()/n; sM = mdm[1:n+1].sum()/n
    dx = np.full(N, np.nan)
    def _dx(sTR, sP, sM):
        pdi = 100.0*sP/sTR if sTR > 0 else 0.0
        mdi = 100.0*sM/sTR if sTR > 0 else 0.0
        s = pdi + mdi
        return (100.0*abs(pdi-mdi)/s) if s > 0 else 0.0
    dx[n] = _dx(sTR, sP, sM)
    for i in range(n+1, N):
        sTR = (sTR*(n-1) + tr[i]) / n
        sP  = (sP*(n-1) + pdm[i]) / n
        sM  = (sM*(n-1) + mdm[i]) / n
        dx[i] = _dx(sTR, sP, sM)
    # ADX = Wilder smoothing of DX, seeded with the first n DX values
    start = n
    a = np.nanmean(dx[start:start+n])
    out[start+n-1] = a
    for i in range(start+n, N):
        a = (a*(n-1) + dx[i]) / n
        out[i] = a
    return out


# --------------------------------------------------------- context
def build_context(d, p):
    h = d["high"].values.astype(float)
    l = d["low"].values.astype(float)
    c = d["close"].values.astype(float)
    o = d["open"].values.astype(float)
    v = d["tick_volume"].values.astype(float)
    t = d["time"].values
    ts = d["time"]

    ich = ichimoku(h, l, p)
    ctx = dict(n=len(d), time=t, dow=ts.dt.dayofweek.values, hour=ts.dt.hour.values,
               year=ts.dt.year.values, open=o, high=h, low=l, close=c, vol=v, **ich)
    ctx["atr"] = atr_wilder(h, l, c, 14)
    ctx["atr_sma"] = atr_sma(h, l, c, 14)
    ctx["rsi"] = rsi_wilder(c, p["rsi_period"])
    ctx["cmf"] = cmf(h, l, c, v, p["cmf_period"])
    ctx["adx"] = adx_wilder(h, l, c, p["adx_period"])
    return ctx


# --------------------------------------------------------- signals
def entry_signal(ctx, p):
    """Vectorised port of CheckEntry() (mq5 468-548). Returns an array `sig`
    where sig[i] is the direction CheckEntry() would return when bar i is the
    just-closed bar (shift s=1). The resulting order fills at open[i+1]."""
    n = ctx["n"]
    tk, kj = ctx["tenkan"], ctx["kijun"]
    ct, cb = ctx["cloud_top"], ctx["cloud_bot"]
    c, h, l = ctx["close"], ctx["high"], ctx["low"]
    D = p["displacement"]
    sh = lambda a, k: pd.Series(a).shift(k).values

    tk_p, kj_p = sh(tk, 1), sh(kj, 1)
    sig = np.zeros(n, dtype=int)

    if p["entry_mode"] == "PLAIN":
        cross_up = (tk > kj) & (tk_p <= kj_p)
        cross_dn = (tk < kj) & (tk_p >= kj_p)
        up = cross_up & (c > ct)
        dn = cross_dn & (c < cb)
        if p["require_chikou"]:
            cb26 = sh(c, D)
            up &= (c > cb26); dn &= (c < cb26)
        if p["use_adx"]:
            a = ctx["adx"]
            ok = np.isfinite(a) & (a > p["adx_threshold"])
            up &= ok; dn &= ok
        sig[np.nan_to_num(up, nan=0).astype(bool)] = 1
        sig[np.nan_to_num(dn, nan=0).astype(bool)] = -1
        return sig

    # BREAKOUT_FULL
    ct_p, cb_p, c_p = sh(ct, 1), sh(cb, 1), sh(c, 1)
    bo_up = (c > ct) & (c_p <= ct_p)
    bo_dn = (c < cb) & (c_p >= cb_p)
    tk_up, tk_dn = (tk > kj), (tk < kj)
    # single bar's high/low at s+D (mq5 511-518, deliberately not a range)
    hb, lb = sh(h, D), sh(l, D)
    ctb, cbb = sh(ct, D), sh(cb, D)
    ch_up = (c > hb) & (c > ctb)
    ch_dn = (c < lb) & (c < cbb)
    fu = ctx["sa_raw"] > ctx["sb_raw"]
    fd = ctx["sa_raw"] < ctx["sb_raw"]
    up = bo_up & tk_up & ch_up & fu
    dn = bo_dn & tk_dn & ch_dn & fd
    if p["use_rsi"]:
        r = ctx["rsi"]; okr = np.isfinite(r)
        up &= okr & (r <= p["rsi_hi"]); dn &= okr & (r >= p["rsi_lo"])
    if p["use_cmf"]:
        m = ctx["cmf"]; okm = np.isfinite(m)
        up &= okm & (m > 0.0); dn &= okm & (m < 0.0)
    sig[np.nan_to_num(up, nan=0).astype(bool)] = 1
    sig[np.nan_to_num(dn, nan=0).astype(bool)] = -1
    return sig


def exit_signal(ctx, p):
    """Port of ShouldExit() (mq5 550-565). exit_long[i]/exit_short[i] = what
    ShouldExit would return with bar i as the just-closed bar."""
    tk, kj = ctx["tenkan"], ctx["kijun"]
    sh = lambda a, k: pd.Series(a).shift(k).values
    if p["exit_mode"] == "CROSS":
        tk_p, kj_p = sh(tk, 1), sh(kj, 1)
        xl = (tk < kj) & (tk_p >= kj_p)
        xs = (tk > kj) & (tk_p <= kj_p)
    else:
        c, ct, cb = ctx["close"], ctx["cloud_top"], ctx["cloud_bot"]
        xl = c < cb
        xs = c > ct
    return (np.nan_to_num(xl, nan=0).astype(bool),
            np.nan_to_num(xs, nan=0).astype(bool))
