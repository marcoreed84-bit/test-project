"""
Tailwind_EA.mq5 Python replica - built by reading the real MQL5 source
directly (Tailwind_EA.mq5, 1468 lines, v1.06), NOT from its header comment.

Indicator handles the EA actually creates in OnInit() (mq5 360-368):
  hEMA21    = iMA(..., InpEMA21=21, 0, MODE_EMA, PRICE_CLOSE)
  hBBMid    = iMA(..., InpBBPeriod=20, 0, MODE_SMA, PRICE_CLOSE)   <- "BB midline"
  hATR      = iATR(..., InpATRPeriod=14)
  -- InpAvoidOpposing shadow handles (mq5 363-368) --
  hBandsAR  = iBands(..., 20, 0, 2.0, PRICE_CLOSE)
  hStochAR  = iStochastic(..., 21, 5, 5, MODE_SMA, STO_LOWHIGH) -> SIGNAL_LINE
  hEMA50SS  = iMA(..., 50, 0, MODE_EMA, PRICE_CLOSE)
  hEMA200SS = iMA(..., 200, 0, MODE_EMA, PRICE_CLOSE)
  hBBMidSS  = iMA(..., 14, 0, MODE_SMA, PRICE_CLOSE)
  hStochSS  = iStochastic(..., 14, 3, 3, MODE_SMA, STO_LOWHIGH) -> SIGNAL_LINE

All indicator primitives are REUSED from research/slipstream/engine.py, which
validated them against the CSV's chk_* reference columns (EMA recursion seeded
at close[0]; iATR = rolling SMA of TR, NOT Wilder; MT5 Stochastic.mq5 port).
Loaded here under an explicit distinct module name - research/aurelius,
research/ichimoku and research/slipstream all ship a module literally called
"engine", so a plain `import engine` collides via sys.modules.

Bar/fill convention (identical to ichimoku/slipstream): OnTick() acts on the
first tick of a new bar j; CheckForEntry() reads shift i=1 = bar j-1, so a
decision derived from bar j-1 fills at bar j's OPEN.
"""
import importlib.util
import os

import numpy as np
import pandas as pd

_SLIP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "slipstream", "engine.py")
_spec = importlib.util.spec_from_file_location("engine_slipstream_tw", _SLIP)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

ema_mt5 = S.ema_mt5          # chk_ema3/21/150-validated
sma = S.sma
atr_mt5 = S.atr_mt5          # chk_atr14-validated (SMA-of-TR, what iATR returns)
stoch_mt5 = S.stoch_mt5      # per MQL5 Stochastic.mq5 - NO chk column exists
is_indecision = S.is_indecision
load_h4 = S.load_h4
DATA_H4 = S.DATA_H4
POINT = S.POINT              # 0.01, meta_point from the CSV header line

# ---------------------------------------------------------------------------
# Shipped defaults, read from the literal `input` declarations in
# Tailwind_EA.mq5 (line numbers in comments). NOT from the header comment.
# ---------------------------------------------------------------------------
P_SHIPPED = dict(
    bb_period=20,               # 173  InpBBPeriod
    ema21=21,                   # 174  InpEMA21
    min_run=3,                  # 177  InpMinRun
    atr_period=14,              # 178  InpATRPeriod
    block_indecision=True,      # 179  InpBlockIndecision
    require_atr_expanding=False,  # 180 InpRequireATRExpanding
    atr_expand_window=10,       # 183  InpATRExpandWindow
    entry_dist_atr=0.5,         # 184  InpEntryDistATR
    avoid_opposing=True,        # 187  InpAvoidOpposing
    use_session_filter=True,    # 191  InpUseSessionFilter
    blocked_hour=12,            # 192  InpBlockedHour
    block_friday_close=True,    # 193  InpBlockFridayClose
    friday_cutoff_hour=16,      # 195  InpFridayCutoffHour
    sl_buffer_atr=1.5,          # 198  InpSLBuffer_ATR
    max_hold_bars=250,          # 200  InpMaxHoldBars
    cooldown=1,                 # 201  InpCooldown
    use_partial_close=False,    # 202  InpUsePartialClose
    partial_frac=0.5,           # 204  InpPartialFrac
    partial_trigger_atr=1.5,    # 205  InpPartialTriggerATR
    allow_shorts=True,          # 229  InpAllowShorts
    allow_longs=True,           # 230  InpAllowLongs
    # NOT modelled: InpUseNewsFilter (208) - NewsBlackoutActive() returns false
    # unconditionally under MQL_TESTER (mq5 v1.03 fix), a no-op in any backtest.
    # InpUseRiskPercent/InpRiskPercent: P&L is reported in price units (= $ at
    # 0.01 lots on GOLD#, contract size 100), same as every other sim here.
)


def params(**over):
    p = dict(P_SHIPPED)
    p.update(over)
    return p


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
               dow=((ts.dt.dayofweek.values + 1) % 7),
               # epoch seconds, for the EA's wall-clock max-hold variant
               epoch=ts.values.astype("datetime64[s]").astype(np.int64))

    # --- Tailwind's own three handles
    ctx["ema21"] = ema_mt5(c, p["ema21"])
    ctx["bbmid"] = sma(c, p["bb_period"])
    ctx["atr"] = atr_mt5(h, l, c, p["atr_period"])

    # --- InpAvoidOpposing shadow handles (all fixed/internal in the EA)
    ar_mid = sma(c, 20)
    sd20 = pd.Series(c).rolling(20).std(ddof=0).values   # iBands: population sd
    ctx["ar_mid"] = ar_mid
    ctx["ar_up"] = ar_mid + 2.0 * sd20
    ctx["ar_lo"] = ar_mid - 2.0 * sd20
    _, ctx["ar_st"] = stoch_mt5(h, l, c, 21, 5, 5)
    ctx["ss_e50"] = ema_mt5(c, 50)
    ctx["ss_e200"] = ema_mt5(c, 200)
    ctx["ss_mid"] = sma(c, 14)
    _, ctx["ss_st"] = stoch_mt5(h, l, c, 14, 3, 3)
    return ctx


# ---------------------------------------------------------------- signals
def base_signals(ctx, p):
    """Vectorised port of CheckForEntry()'s signal block (mq5 1328-1385),
    EXCLUDING the position/cooldown/news gates and EXCLUDING ShadowOpposing()
    (evaluated lazily per-bar in the sim - it is an 800-bar re-walk).

    Returns (sig, warm): sig[j] in {-1,0,+1} = the direction CheckForEntry()
    computes when it runs on the first tick of bar j, reading shift i=1.
    """
    n = ctx["n"]
    o, h, l, c = ctx["open"], ctx["high"], ctx["low"], ctx["close"]
    e21, mid, atr = ctx["ema21"], ctx["bbmid"], ctx["atr"]
    mr = p["min_run"]
    hour, dow = ctx["hour"], ctx["dow"]
    sig = np.zeros(n, dtype=int)

    above = (c > e21) & (c > mid)
    below = (c < e21) & (c < mid)

    # EA history gate (mq5 1328): depth = max(MinRun, ATRExpandWindow)+5,
    # requires Bars >= depth+20.
    depth = max(mr, p["atr_expand_window"]) + 5
    warm = max(p["ema21"], p["bb_period"], p["atr_period"]) + depth + 25
    warm = max(warm, mr + p["atr_expand_window"] + 25, 60)

    for j in range(warm, n):
        i = j - 1
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue

        # session gates are read off the SIGNAL bar's time (shift 1, mq5 1322)
        if p["use_session_filter"] and hour[i] == p["blocked_hour"]:
            continue
        if p["block_friday_close"] and dow[i] == 5 and hour[i] >= p["friday_cutoff_hour"]:
            continue
        if p["block_friday_close"] and dow[i] == 6:
            continue

        # fresh threshold crossing: above[shift 1..MinRun] all true AND
        # above[shift MinRun+1] false  (shift k == absolute bar j-k)
        long_sig = bool(above[j - mr:j].all())
        short_sig = bool(below[j - mr:j].all())
        if long_sig and above[j - mr - 1]:
            long_sig = False
        if short_sig and below[j - mr - 1]:
            short_sig = False
        if long_sig and short_sig:
            continue
        if not (long_sig or short_sig):
            continue

        if p["block_indecision"] and is_indecision(o[i], h[i], l[i], c[i]):
            continue
        if p["require_atr_expanding"]:
            a_ref = atr[i - p["atr_expand_window"]]
            if not np.isfinite(a_ref) or a <= a_ref:
                continue
        if p["entry_dist_atr"] > 0.0:
            m = mid[i]
            if not np.isfinite(m) or abs(c[i] - m) / a < p["entry_dist_atr"]:
                continue
        if long_sig and not p["allow_longs"]:
            continue
        if short_sig and not p["allow_shorts"]:
            continue
        sig[j] = 1 if long_sig else -1
    return sig, warm


# ------------------------------------------------- InpAvoidOpposing shadow
SHADOW_DEPTH = 800


def shadow_dirs(ctx, j, depth=SHADOW_DEPTH):
    """Exact port of ShadowOpposing() (mq5 1016-1215), returning
    (dirAR, dirSS) = the direction of the synthetic AuRebound / Slipstream
    position that is open at the end of the walk (0 = flat).

    The EA copies `depth` bars ending at the FORMING bar (shift 0 = bar j),
    reverses to forward-chronological order and walks window index
    i = 0 .. n-2, i.e. absolute bars (j-depth+1) .. (j-1).  A synthetic entry
    at window index i fills at o[i+1] = the NEXT bar's open, so an entry at
    i = n-2 fills at open[j]. Indicator values come from fully-converged
    native handles, so they are read off the full-history arrays.

    NOTE the state is rebuilt from FLAT at the window start on every call -
    that is literally what the EA does, and it is reproduced here rather than
    replaced by a cheaper full-history walk.
    """
    start = j - depth + 1
    if start < 0:
        return 0, 0
    n = depth
    if n < 300:                      # mq5 1046: nAvail<300 -> return false
        return 0, 0

    o, h, l, c = ctx["open"], ctx["high"], ctx["low"], ctx["close"]
    a = ctx["atr"]
    ar_mid, ar_up, ar_lo, ar_st = ctx["ar_mid"], ctx["ar_up"], ctx["ar_lo"], ctx["ar_st"]
    e50, e200, ss_mid, ss_st = ctx["ss_e50"], ctx["ss_e200"], ctx["ss_mid"], ctx["ss_st"]
    hour, dow = ctx["hour"], ctx["dow"]
    last = n - 2

    # ---- per-bar precomputed flags (mq5 1057-1088), window-index guarded
    ar_turn_up = np.zeros(n, bool); ar_turn_dn = np.zeros(n, bool)
    ar_near_up = np.zeros(n, bool); ar_near_lo = np.zeros(n, bool)
    ss_up = np.zeros(n, bool); ss_dn = np.zeros(n, bool)
    ss_near = np.zeros(n, bool)
    ss_turn_up = np.zeros(n, bool); ss_turn_dn = np.zeros(n, bool)

    sl_ = slice(start, start + n)
    av = a[sl_]
    ok = np.isfinite(av) & (av > 0)
    ar_near_up[ok] = (h[sl_][ok] >= ar_up[sl_][ok] - 0.5 * av[ok])
    ar_near_lo[ok] = (l[sl_][ok] <= ar_lo[sl_][ok] + 0.5 * av[ok])
    s = ar_st[sl_]
    t = np.zeros(n, bool); t[2:] = np.isfinite(s[2:]) & np.isfinite(s[1:-1]) & np.isfinite(s[:-2])
    ar_turn_up[2:] = t[2:] & (s[2:] > s[1:-1]) & (s[1:-1] <= s[:-2])
    ar_turn_dn[2:] = t[2:] & (s[2:] < s[1:-1]) & (s[1:-1] >= s[:-2])

    idx = np.arange(n)
    ok2 = ok & (idx >= 10)
    slope_up = np.zeros(n, bool)
    slope_up[10:] = e50[sl_][10:] > e50[sl_][:-10]
    ss_up[ok2] = (c[sl_][ok2] > e200[sl_][ok2]) & slope_up[ok2]
    ss_dn[ok2] = (c[sl_][ok2] < e200[sl_][ok2]) & (~slope_up[ok2])
    ss_near[ok2] = ((np.abs(l[sl_][ok2] - ss_mid[sl_][ok2]) <= 1.25 * av[ok2])
                    | ((l[sl_][ok2] <= ss_mid[sl_][ok2]) & (h[sl_][ok2] >= ss_mid[sl_][ok2])))
    s2 = ss_st[sl_]
    t2 = np.zeros(n, bool); t2[2:] = np.isfinite(s2[2:]) & np.isfinite(s2[1:-1]) & np.isfinite(s2[:-2])
    ss_turn_up[2:] = t2[2:] & (s2[2:] > s2[1:-1]) & (s2[1:-1] <= s2[:-2]) & ok2[2:]
    ss_turn_dn[2:] = t2[2:] & (s2[2:] < s2[1:-1]) & (s2[1:-1] >= s2[:-2]) & ok2[2:]

    # ---- shadow AuRebound walk (mq5 1090-1157)
    pos = 0; entry_bar = -1; pdir = 0; stage2 = False
    epx = esl = eatr = best = 0.0
    cd = -1
    dir_ar = 0
    for i in range(0, last + 1):
        b = start + i
        avi = a[b]
        if not (np.isfinite(avi) and avi > 0.0):
            continue
        dir_ar = pdir if pos != 0 else 0
        if pos != 0:
            best = max(best, (h[b] - epx) if pdir > 0 else (epx - l[b]))
            if not stage2:
                if (c[b] > ar_mid[b]) if pdir > 0 else (c[b] < ar_mid[b]):
                    stage2 = True; esl = epx
            if best >= 1.0 * eatr:
                lock = epx + pdir * best * 0.70
                esl = max(esl, lock) if pdir > 0 else min(esl, lock)
            hit = (l[b] <= esl) if pdir > 0 else (h[b] >= esl)
            timed = (i - entry_bar) >= 120
            band = False
            if stage2:
                lo_k = max(entry_bar, i - 3)
                recent = False
                for k in range(lo_k, i + 1):
                    bk = start + k
                    if pdir > 0:
                        if h[bk] >= ar_up[bk] - 0.5 * eatr:
                            recent = True; break
                    else:
                        if l[bk] <= ar_lo[bk] + 0.5 * eatr:
                            recent = True; break
                band = recent and (ar_turn_dn[i] if pdir > 0 else ar_turn_up[i])
            if hit or band or timed:
                pos = 0; stage2 = False; best = 0.0; cd = i + 2
                # NOTE (faithful to mq5 1129): dirAR is assigned ONLY at the
                # top of a loop pass (from the state BEFORE the bar) and on a
                # new entry. A close on the LAST processed bar therefore still
                # leaves dirAR reporting that position as open. Replicated.
        else:
            if i <= cd:
                continue
            lo_k = max(0, i - 3)
            rl = ar_near_lo[lo_k:i + 1].any()
            ru = ar_near_up[lo_k:i + 1].any()
            ls = rl and ar_turn_up[i]
            ss_ = ru and ar_turn_dn[i]
            if hour[b] == 8:
                ls = ss_ = False
            if ls and ss_:
                ls = ss_ = False
            if ls or ss_:
                d = 1 if ls else -1
                pos = 1; pdir = d; entry_bar = i; epx = o[b + 1]; eatr = avi
                if d > 0:
                    ext = l[max(start, b - 3):b + 1].min()
                    sld = min(abs(epx - ext) + 0.5 * avi, 1.5 * avi)
                    esl = epx - sld
                else:
                    ext = h[max(start, b - 3):b + 1].max()
                    sld = min(abs(ext - epx) + 0.5 * avi, 1.5 * avi)
                    esl = epx + sld
                stage2 = False; best = 0.0; dir_ar = d

    # ---- shadow Slipstream walk (mq5 1159-1213)
    pos = 0; entry_bar = -1; pdir = 0
    epx = esl = eatr = best = 0.0
    cd = -1
    dir_ss = 0
    for i in range(0, last + 1):
        b = start + i
        avi = a[b]
        if not (np.isfinite(avi) and avi > 0.0):
            continue
        dir_ss = pdir if pos != 0 else 0
        if pos != 0:
            best = max(best, (h[b] - epx) if pdir > 0 else (epx - l[b]))
            if best >= 1.0 * eatr:
                lock = epx + pdir * best * 0.70
                esl = max(esl, lock) if pdir > 0 else min(esl, lock)
            hit = (l[b] <= esl) if pdir > 0 else (h[b] >= esl)
            tb = (c[b] < e50[b]) if pdir > 0 else (c[b] > e50[b])
            timed = (i - entry_bar) >= 200
            if hit or tb or timed:
                pos = 0; best = 0.0; cd = i + 2
        else:
            if i <= cd:
                continue
            recent = ss_near[max(0, i - 3):i + 1].any()
            ls = ss_up[i] and recent and ss_turn_up[i]
            sh = ss_dn[i] and recent and ss_turn_dn[i]
            if is_indecision(o[b], h[b], l[b], c[b]):
                ls = sh = False
            if hour[b] == 0 or hour[b] == 12:
                ls = sh = False
            if dow[b] == 5 and hour[b] >= 16:
                ls = sh = False
            if dow[b] == 6:
                ls = sh = False
            if ls and sh:
                ls = sh = False
            if ls or sh:
                d = 1 if ls else -1
                pos = 1; pdir = d; entry_bar = i; epx = o[b + 1]; eatr = avi
                if d > 0:
                    ext = l[max(start, b - 3):b + 1].min()
                    esl = epx - (abs(epx - ext) + 0.75 * avi)
                else:
                    ext = h[max(start, b - 3):b + 1].max()
                    esl = epx + (abs(ext - epx) + 0.75 * avi)
                best = 0.0; dir_ss = d
    return dir_ar, dir_ss


def shadow_opposing(ctx, j, direction, cache=None):
    """return (dirAR == -dir) || (dirSS == -dir)   (mq5 1215)."""
    if cache is None:
        cache = {}
    if j not in cache:
        cache[j] = shadow_dirs(ctx, j)
    da, ds = cache[j]
    return (da == -direction) or (ds == -direction)
