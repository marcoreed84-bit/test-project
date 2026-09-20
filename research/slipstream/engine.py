"""
Slipstream_EA.mq5 Python replica - built by reading the real MQL5 source
directly (Slipstream_EA.mq5, 1567 lines, v1.07), not from its header comment.

Every indicator below is a port of the MT5 built-in the EA actually creates a
handle for in OnInit() (mq5 411-425), NOT a library/"textbook" version:

  hEMA50  = iMA(..., 50, 0, MODE_EMA, PRICE_CLOSE)
  hEMA200 = iMA(..., 200, 0, MODE_EMA, PRICE_CLOSE)
  hATR    = iATR(..., 14)
  hStoch  = iStochastic(..., 14, 3, 3, MODE_SMA, STO_LOWHIGH)   -> SIGNAL_LINE
  hStochConf = iStochastic(..., 21, 5, 5, MODE_SMA, STO_LOWHIGH) -> SIGNAL_LINE
  hBBMid  = iMA(..., InpBBPeriod=14, 0, MODE_SMA, PRICE_CLOSE)

chk_* validation (see chk_check.py in this directory):
  - EMA(3/21/150) recursion seeded at close[0] matches chk_ema* to the chk
    columns' own 2-dp rounding. Confirms the EMA50/EMA200 port.
  - chk_atr14 matches a SIMPLE moving average of true range EXACTLY, not
    Wilder - independently re-confirmed here, and it matters much more for
    Slipstream than it did for Ichimoku: Ichimoku_EA hand-rolls a Wilder ATR,
    but Slipstream reads MT5's own iATR() handle, so the SMA-of-TR form is
    the one that reproduces this EA. (MT5's own ATR.mq5 is indeed a rolling
    SMA of TR - this is not a broker quirk, it is what iATR returns.)
  - SMA14 (the BB midline) has no chk column, but an SMA is trivially
    verifiable and the EMA ports validating means the close series is right.
  - Stochastic has NO chk reference column at all. Ported per MT5's own
    Stochastic.mq5 algorithm (ratio-of-sums slowing, then SimpleMA for the
    signal line) and left flagged as unverifiable against MT5 output.

Bar/fill convention (same as research/ichimoku/engine.py + sim.py):
  OnTick() acts on the first tick of a new bar j and CheckForEntry() reads
  shift i=1 = bar j-1. So a decision derived from bar j-1 fills at bar j's
  OPEN. The forming bar (shift 0) at that instant has O=H=L=C=open[j].
  That matters here: CheckConfluenceDir() deliberately starts its loop at
  k=0, i.e. it DOES read the forming bar. Modelled explicitly below.
"""
import importlib.util
import os

import numpy as np
import pandas as pd

# --- reuse the already-validated ichimoku primitives WITHOUT the module-cache
# --- collision `import engine` causes (research/aurelius/engine.py and
# --- research/ichimoku/engine.py are both literally "engine"): load it under
# --- an explicit distinct module name.
_ICHI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "ichimoku", "engine.py")
_spec = importlib.util.spec_from_file_location("ichimoku_engine", _ICHI_PATH)
ichi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ichi)

true_range = ichi.true_range        # validated
atr_wilder = ichi.atr_wilder        # validated (not used by Slipstream)
DATA_H4 = ichi.DATA_H4
POINT = 0.01                        # meta_point from the CSV header line

# ---------------------------------------------------------------------------
# Shipped defaults, read from the literal `input` declarations in
# Slipstream_EA.mq5 (line numbers in comments). NOT from the header comment.
# ---------------------------------------------------------------------------
P_SHIPPED = dict(
    bb_period=14,            # 211  InpBBPeriod
    ema50=50,                # 212
    ema200=200,              # 213
    trend_slope_bars=10,     # 214  InpTrendSlopeBars
    touch_tol=1.25,          # 217  InpTouchTol
    atr_period=14,           # 218
    stoch_k=14, stoch_d=3, stoch_slow=3,        # 219-221
    signal_line_mode=True,   # 222  InpSignalLineMode
    lookback=3,              # 223  InpLookback
    block_indecision=True,   # 224
    use_trendline=False,     # 225  InpUseTrendlineConfirm
    swing_lag=3,             # 228
    require_confluence=True, # 229  InpRequireConfluence
    confluence_window=2,     # 235
    sl_buffer=0.75,          # 238  InpSLBuffer
    max_hold_bars=200,       # 239
    cooldown=2,              # 240
    use_mfe_lock=True,       # 241
    mfe_lock_trigger=1.0,    # 242
    mfe_lock_frac=0.70,      # 243
    use_session_filter=True, # 246
    blocked_hour1=0,         # 247
    blocked_hour2=12,        # 248
    block_friday_close=True, # 249
    friday_cutoff_hour=16,   # 250
    close_before_weekend=False,  # 251
    allow_shorts=True, allow_longs=True,        # 275-276
    # not modelled: InpUseNewsFilter (line 254) - NewsBlackoutActive() returns
    # false unconditionally under MQL_TESTER (mq5 1337), so it is a no-op in
    # any backtest, exactly as this replica treats it.
)

# The pre-sweep "original" the header says was beaten on both halves.
P_ORIGINAL = dict(P_SHIPPED, bb_period=20, touch_tol=1.0, sl_buffer=0.5)


def params(**over):
    p = dict(P_SHIPPED)
    p.update(over)
    return p


# ------------------------------------------------------------------ data
def load_h4(start="2013-01-01", warmup_from_full=True):
    """Same loader/window as research/ichimoku/engine.py's load_h4().

    warmup_from_full: keep the pre-`start` history for indicator warmup
    (EMA200 seeded at close[0] is still carrying ~13% seed weight 200 bars
    in, so warming from 2001 is what MT5 would actually do with full chart
    history). Returns (df_full, first_tradable_index).
    """
    d = pd.read_csv(DATA_H4, skiprows=1)
    d["time"] = pd.to_datetime(d["time"], format="%Y.%m.%d %H:%M:%S")
    d = d.reset_index(drop=True)
    if start is None:
        return d, 0
    if warmup_from_full:
        i0 = int(np.searchsorted(d["time"].values,
                                 np.datetime64(pd.Timestamp(start))))
        return d, i0
    d = d[d["time"] >= start].reset_index(drop=True)
    return d, 0


# ------------------------------------------------------- MT5 indicator ports
def ema_mt5(x, n):
    """iMA(..., MODE_EMA): ExponentialMAOnBuffer seeds out[0]=x[0] then
    out[i] = a*x[i] + (1-a)*out[i-1], a = 2/(n+1)."""
    return pd.Series(x).ewm(alpha=2.0 / (n + 1.0), adjust=False).mean().values


def sma(x, n):
    return pd.Series(x).rolling(n).mean().values


def tr_mt5(h, l, c):
    """ATR.mq5's TR: max(high,close_prev) - min(low,close_prev); TR[0]=0."""
    tr = np.empty(len(h))
    tr[0] = 0.0
    pc = c[:-1]
    tr[1:] = np.maximum(h[1:], pc) - np.minimum(l[1:], pc)
    return tr


def atr_mt5(h, l, c, n=14):
    """What iATR(n) actually returns: a rolling SMA of TR, first valid at
    index n (ATR.mq5 seeds ExtATRBuffer[n] = mean(TR[1..n]) then rolls)."""
    tr = tr_mt5(h, l, c)
    out = np.array(pd.Series(tr).rolling(n).mean().values, dtype=float)
    out[:n] = np.nan          # ATR.mq5 leaves 0..n-1 uncalculated
    return out


def stoch_mt5(h, l, c, kper, dper, slowing):
    """Port of MT5's own Stochastic.mq5 (MODE_SMA, STO_LOWHIGH):
       LL[i]=min(low[i-k+1..i]), HH[i]=max(high[i-k+1..i])
       main[i] = 100 * sum(c-LL over `slowing` bars) / sum(HH-LL over same)
       signal[i] = SimpleMA(main, dper)
    Returns (main, signal). NOTE: unlike EMA/ATR this has NO chk_* column in
    the CSV, so it is 'implemented per the MQL5 spec', not MT5-verified."""
    ll = pd.Series(l).rolling(kper).min().values
    hh = pd.Series(h).rolling(kper).max().values
    num = pd.Series(c - ll).rolling(slowing).sum().values
    den = pd.Series(hh - ll).rolling(slowing).sum().values
    with np.errstate(divide="ignore", invalid="ignore"):
        main = np.where(den == 0.0, 100.0, 100.0 * num / np.where(den == 0.0, 1.0, den))
    main = np.where(np.isnan(num) | np.isnan(den), np.nan, main)
    signal = pd.Series(main).rolling(dper).mean().values
    return main, signal


def ema21_trunc(c, kf=2.0 / 22.0, steps=40):
    """CheckConfluenceDir()'s hand-rolled EMA21 (mq5 1152-1154), ported
    exactly - it is NOT a full-history EMA21: it seeds at close[b-40] ("oldest
    available close in the EMA window") and then runs `steps` recursion steps
    forward.  ema = c[b-40]; for m in 39..0: ema = c[b-m]*kf + ema*(1-kf)."""
    n = len(c)
    out = np.full(n, np.nan)
    w = kf * (1.0 - kf) ** np.arange(steps)          # weight on c[b-m], m=0..39
    seedw = (1.0 - kf) ** steps                      # weight on c[b-40]
    # np.convolve with reversed weights == sum_m w[m]*c[b-m]
    conv = np.convolve(c, w[::-1], mode="full")[: n]
    # conv[b] = sum_{m=0..steps-1} w[m]*c[b-m], valid for b >= steps-1
    out[steps:] = conv[steps:] + seedw * c[: n - steps]
    out[:steps] = np.nan
    return out


def _popstd(x, n):
    """Population stddev over a backward window of n (mq5 1168 divides by 20)."""
    s = pd.Series(x)
    m = s.rolling(n).mean()
    m2 = (s * s).rolling(n).mean()
    return np.sqrt(np.maximum(m2 - m * m, 0.0)).values


# ---------------------------------------------------------------- context
def build_context(d, p):
    o = d["open"].values.astype(float)
    h = d["high"].values.astype(float)
    l = d["low"].values.astype(float)
    c = d["close"].values.astype(float)
    ts = d["time"]
    n = len(d)

    ctx = dict(n=n, time=d["time"].values, open=o, high=h, low=l, close=c,
               spread=d["spread"].values.astype(float),
               year=ts.dt.year.values, hour=ts.dt.hour.values,
               # MqlDateTime.day_of_week: 0=Sun..6=Sat; pandas: 0=Mon..6=Sun
               dow=((ts.dt.dayofweek.values + 1) % 7))

    ctx["ema50"] = ema_mt5(c, p["ema50"])
    ctx["ema200"] = ema_mt5(c, p["ema200"])
    ctx["atr"] = atr_mt5(h, l, c, p["atr_period"])
    ctx["bbmid"] = sma(c, p["bb_period"])
    _, ctx["stD"] = stoch_mt5(h, l, c, p["stoch_k"], p["stoch_d"], p["stoch_slow"])

    # --- confluence-side series (all fixed/internal in the EA, mq5 1132-1178)
    cmain, csig = stoch_mt5(h, l, c, 21, 5, 5)
    ctx["conf_main"] = cmain
    ctx["conf_sig"] = csig
    ctx["conf_ema21"] = ema21_trunc(c)
    ctx["conf_sma20"] = sma(c, 20)
    sd20 = _popstd(c, 20)
    ctx["conf_bb_up"] = ctx["conf_sma20"] + 2.0 * sd20
    ctx["conf_bb_lo"] = ctx["conf_sma20"] - 2.0 * sd20
    # cumulative TR, for rebuilding ATR on the forming bar
    tr = tr_mt5(h, l, c)
    ctx["tr"] = tr
    ctx["cumtr"] = np.concatenate(([0.0], np.cumsum(tr)))   # cumtr[b+1]=sum TR[0..b]
    ctx["cumc"] = np.concatenate(([0.0], np.cumsum(c)))
    ctx["cumc2"] = np.concatenate(([0.0], np.cumsum(c * c)))
    ctx["roll_lo21"] = pd.Series(l).rolling(21).min().values
    ctx["roll_hi21"] = pd.Series(h).rolling(21).max().values
    return ctx


# --------------------------------------------------- forming-bar confluence
def _forming(ctx, j):
    """Values CheckConfluenceDir() sees at series index k=0 on decision bar j,
    i.e. the FORMING bar, which in MT5 at the first tick of bar j has
    O=H=L=C=open[j]. Returns dict of the k=0 quantities."""
    o = ctx["open"][j]
    c = ctx["close"]
    # ATR14 on the modified series
    tr_form = abs(o - c[j - 1])
    s = ctx["cumtr"][j] - ctx["cumtr"][j - 13]        # TR[j-13..j-1]
    atr0 = (s + tr_form) / 14.0
    # SMA20 / BB20 with close[j] -> open[j]
    sc = ctx["cumc"][j] - ctx["cumc"][j - 19] + o     # close[j-19..j-1] + o
    sc2 = ctx["cumc2"][j] - ctx["cumc2"][j - 19] + o * o
    mid0 = sc / 20.0
    var0 = max(sc2 / 20.0 - mid0 * mid0, 0.0)
    sd0 = np.sqrt(var0)
    # truncated EMA21 ending on the forming bar
    kf = 2.0 / 22.0
    e = c[j - 40]
    for m in range(39, 0, -1):
        e = c[j - m] * kf + e * (1.0 - kf)
    e = o * kf + e * (1.0 - kf)
    # stochastic(21,5,5) signal line including the forming bar.
    # MT5's %K window at bar j is low[j-20..j] / high[j-20..j]; on the forming
    # bar the high and low are both the first tick's price = open[j].
    ll0 = min(np.min(ctx["low"][j - 20:j]), o)
    hh0 = max(np.max(ctx["high"][j - 20:j]), o)
    num = (o - ll0)
    den = (hh0 - ll0)
    for m in range(1, 5):
        b = j - m
        lo_b = np.min(ctx["low"][b - 20:b + 1])
        hi_b = np.max(ctx["high"][b - 20:b + 1])
        num += c[b] - lo_b
        den += hi_b - lo_b
    main0 = 100.0 if den == 0.0 else 100.0 * num / den
    sig0 = (main0 + ctx["conf_main"][j - 1] + ctx["conf_main"][j - 2]
            + ctx["conf_main"][j - 3] + ctx["conf_main"][j - 4]) / 5.0
    return dict(c=o, h=o, l=o, atr=atr0, sma20=mid0,
                bb_up=mid0 + 2.0 * sd0, bb_lo=mid0 - 2.0 * sd0,
                ema21=e, stD=sig0)


def _conf_vals(ctx, j, k, form):
    """Series index k at decision bar j -> absolute bar j-k (k=0 = forming)."""
    if k == 0:
        return form
    b = j - k
    return dict(c=ctx["close"][b], h=ctx["high"][b], l=ctx["low"][b],
                atr=ctx["atr"][b], sma20=ctx["conf_sma20"][b],
                bb_up=ctx["conf_bb_up"][b], bb_lo=ctx["conf_bb_lo"][b],
                ema21=ctx["conf_ema21"][b], stD=ctx["conf_sig"][b])


def confluence_ok(ctx, j, direction, p, include_forming_bar=True):
    """Port of CheckConfluenceDir() (mq5 1132-1178).

    include_forming_bar=False is a deliberate variant: it starts the loop at
    k=1 (last CLOSED bar) instead of k=0, i.e. what the EA's own header means
    by 'runs strictly on closed H4 bars'. Used only as a sensitivity check.
    """
    window = p["confluence_window"]
    form = _forming(ctx, j) if include_forming_bar else None
    k0 = 0 if include_forming_bar else 1
    for k in range(k0, window + 1):
        v = _conf_vals(ctx, j, k, form)
        # --- Tailwind-style
        if not np.isfinite(v["ema21"]) or not np.isfinite(v["sma20"]):
            continue
        if direction > 0:
            if v["c"] > v["ema21"] and v["c"] > v["sma20"]:
                return True
        else:
            if v["c"] < v["ema21"] and v["c"] < v["sma20"]:
                return True
        # --- AuRebound-style
        a = v["atr"]
        if not np.isfinite(a) or a <= 0.0:
            continue
        s0 = v["stD"]
        s1 = _conf_vals(ctx, j, k + 1, form)["stD"]
        s2 = _conf_vals(ctx, j, k + 2, form)["stD"]
        if not (np.isfinite(s0) and np.isfinite(s1) and np.isfinite(s2)):
            continue
        turn_up = (s0 > s1) and (s1 <= s2)
        turn_dn = (s0 < s1) and (s1 >= s2)
        recent_lower = recent_upper = False
        for m in range(k, k + 4):
            vm = _conf_vals(ctx, j, m, form)
            if not np.isfinite(vm["bb_up"]):
                continue
            am = vm["atr"]
            if not np.isfinite(am) or am <= 0.0:
                continue
            if vm["h"] >= vm["bb_up"] - 0.5 * am:
                recent_upper = True
            if vm["l"] <= vm["bb_lo"] + 0.5 * am:
                recent_lower = True
        if direction > 0:
            if recent_lower and turn_up:
                return True
        else:
            if recent_upper and turn_dn:
                return True
    return False


# --------------------------------------------------------------- signals
def is_indecision(o, h, l, c):
    """Port of IsIndecisionCandle (mq5 1093-1101)."""
    rng = h - l
    if rng <= 0:
        return False
    body = abs(c - o)
    up_w = h - max(o, c)
    lo_w = min(o, c) - l
    return (body / rng) < 0.35 and up_w > 0.2 * rng and lo_w > 0.2 * rng


def base_signals(ctx, p, symmetric_touch=False):
    """Vectorised port of CheckForEntry()'s signal block (mq5 1372-1467),
    EXCLUDING the confluence filter (evaluated per-bar in the sim, since it
    reads the forming bar) and excluding the position/cooldown/news gates.

    Returns sig[j] in {-1,0,1}: the direction CheckForEntry() computes when
    run on the first tick of bar j, reading shift i = 1 (bar j-1).

    symmetric_touch: sensitivity variant only - tests the SHORT side's
    pullback against high[] instead of low[] (see report; the shipped code
    measures both directions off low[]).
    """
    n = ctx["n"]
    o, h, l, c = ctx["open"], ctx["high"], ctx["low"], ctx["close"]
    atr, mid, e50, e200, stD = (ctx["atr"], ctx["bbmid"], ctx["ema50"],
                                ctx["ema200"], ctx["stD"])
    lb = p["lookback"]
    tol = p["touch_tol"]
    slope_n = p["trend_slope_bars"]
    sig = np.zeros(n, dtype=int)

    # deepest read is i + lookback = 1 + lb, and i + slope_n = 1 + slope_n
    warm = max(p["ema200"], p["bb_period"], p["stoch_k"] + p["stoch_d"] + p["stoch_slow"]) + 40
    warm = max(warm, slope_n + 45, lb + 45, 45)

    for j in range(warm, n):
        i = j - 1                              # absolute index of shift-1 bar
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        m = mid[i]
        if not np.isfinite(m) or m <= 0.0:
            continue
        if not (np.isfinite(e50[i]) and np.isfinite(e50[i - slope_n]) and np.isfinite(e200[i])):
            continue
        slope_up = e50[i] > e50[i - slope_n]
        uptrend = (c[i] > e200[i]) and slope_up
        downtrend = (c[i] < e200[i]) and (not slope_up)
        if not (uptrend or downtrend):
            continue

        touch_src = l
        recent = (abs(l[i] - m) <= tol * a) or (l[i] <= m and h[i] >= m)
        if symmetric_touch and downtrend:
            recent = (abs(h[i] - m) <= tol * a) or (l[i] <= m and h[i] >= m)
            touch_src = h
        k = 1
        while k <= lb and not recent:
            mk = mid[i - k]
            ak = atr[i - k]
            if np.isfinite(mk) and mk > 0.0 and np.isfinite(ak) and ak > 0:
                recent = (abs(touch_src[i - k] - mk) <= tol * ak) or (l[i - k] <= mk and h[i - k] >= mk)
            k += 1
        if not recent:
            continue

        s0, s1, s2 = stD[i], stD[i - 1], stD[i - 2]
        if not (np.isfinite(s0) and np.isfinite(s1) and np.isfinite(s2)):
            continue
        if p["signal_line_mode"]:
            turn_up = (s0 > s1) and (s1 <= s2)
            turn_dn = (s0 < s1) and (s1 >= s2)
        else:
            turn_up = (s1 < 50.0) and (s0 >= 50.0)
            turn_dn = (s1 > 50.0) and (s0 <= 50.0)

        long_sig = p["allow_longs"] and uptrend and recent and turn_up
        short_sig = p["allow_shorts"] and downtrend and recent and turn_dn
        if not (long_sig or short_sig):
            continue
        if p["block_indecision"] and is_indecision(o[i], h[i], l[i], c[i]):
            continue
        sig[j] = 1 if long_sig else -1
    return sig, warm
