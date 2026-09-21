"""
Independent Python replica of AuRebound_EA.mq5's indicator/signal layer.

Built by reading /home/user/test-project/AuRebound_EA.mq5 directly - NOT from
the header comments, and NOT from any sibling EA's research code except where
the math is literally identical (MT5 ATR / MT5 Stochastic ports, and the H4
CSV loader, all reused verbatim from research/slipstream/engine.py, which in
turn came from research/ichimoku/engine.py).

MODULE-NAME COLLISION WARNING
----------------------------
research/aurelius/engine.py, research/ichimoku/engine.py,
research/slipstream/engine.py and THIS file are all named "engine".  A plain
`import engine` resolves via sys.modules to whichever was imported first.
Always load this one under an explicit distinct name, e.g.

    import importlib.util, os
    spec = importlib.util.spec_from_file_location(
        "aurebound_engine", os.path.join(HERE, "engine.py"))
    aeng = importlib.util.module_from_spec(spec); spec.loader.exec_module(aeng)

sim.py in this directory does exactly that.

WHAT AuRebound ACTUALLY IS (read off the real source, mq5 425-441 / 1499-1535)
-----------------------------------------------------------------------------
Despite the header's phrase "ride the band", the shipped trigger is a
MEAN-REVERSION BOUNCE off the outer band, not a band-walk continuation:

    NearLowerAt(k)  :=  low[k]  <= BB_lower(k) + InpEntryProx * ATR[k]
    NearUpperAt(k)  :=  high[k] >= BB_upper(k) - InpEntryProx * ATR[k]

    recentLower := any NearLowerAt(k) for k in [i-InpLookback .. i]
    recentUpper := any NearUpperAt(k) for k in [i-InpLookback .. i]

    longSig  := recentLower and TurnUpAt(i)     <- LOW band touch -> buy
    shortSig := recentUpper and TurnDnAt(i)     <- HIGH band touch -> sell

TurnUpAt/TurnDnAt at the shipped MODE_SIGNAL_LINE_TURN default are a pure
Stochastic %D pivot, with NO 20/80 threshold at all (mq5 410-423):

    TurnUp := D[i] >  D[i-1] and D[i-1] <= D[i-2]
    TurnDn := D[i] <  D[i-1] and D[i-1] >= D[i-2]

Bollinger bands are computed BY THE EA ITSELF (mq5 316-327, 425-427) from a
plain SMA of close and a POPULATION stddev (divides by `period`, not
`period-1`) - not from an iBands handle.  So the band math needs no MT5
cross-check; it is fully specified by the source.

Signal-bar indexing (mq5 1174-1200): CopyTime(...,0,HIST_BARS,...) then
ArraySetAsSeries(false), so index copied-1 is the still-FORMING bar and
`int i = copied-2` is the last CLOSED bar.  Verified: this is the correct,
off-by-one-free "just-closed bar" convention the header claims.  In this
replica, bar `j` is the forming bar (fill happens at open[j]) and the signal
bar is `j-1`.
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_H4 = ("/tmp/claude-0/-home-user-test-project/"
           "0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data/GOLD_H4.csv")

POINT = 0.01          # meta_point from the CSV's own header row
CONTRACT = 100.0      # meta_contract_size

# ---------------------------------------------------------------------------
# THE REAL SHIPPED INPUT DEFAULTS, read line-by-line out of AuRebound_EA.mq5.
# Line numbers are from the committed file (1729 lines).
# ---------------------------------------------------------------------------
P_SHIPPED = dict(
    # --- Bollinger Bands (mq5 118-119)
    BBPeriod=20,
    BBDev=2.0,
    # --- Stochastic (mq5 122-135); iStochastic(K, D, slowing, MODE_SMA, STO_LOWHIGH)
    StochMode="SIGNAL_LINE_TURN",   # ENUM default = MODE_SIGNAL_LINE_TURN (1)
    StochK=21,
    StochD=5,          # real %D period   (label in the file is documented as swapped)
    StochSlow=5,       # real slowing
    UsePersistFilter=True,   # THRESHOLD mode only -> inert at the shipped default
    MinPersistBars=4,
    # --- Entry (mq5 138-141)
    EntryProx=0.5,     # band proximity, x ATR
    ATRPeriod=14,
    Lookback=3,
    BlockIndecision=False,
    # --- Exit (mq5 144-149)
    SLBuffer=0.5,      # x ATR, added to the structural extreme
    UseSLCap=True,
    SLCapATR=1.5,      # hard cap on stop distance, x ATR
    MFELockFrac=0.70,  # locks 70% of best favourable move, armed at bestFav >= 1.0*entryATR
    MaxHoldBars=120,
    Cooldown=2,
    # --- Session filter (mq5 152-156)
    UseSessionFilter=True,
    BlockedHour=8,
    BlockFridayClose=True,
    FridayCloseHour=16,
    UseSessionScheduleFilter=True,   # broker session schedule - not modellable offline
    # --- News filter (mq5 159-170): live Economic Calendar only, and the file
    # itself short-circuits it under MQL_TESTER (mq5 ~1484). Inert in backtest.
    UseNewsFilter=True,
    # --- Trading (mq5 173-182)
    Magic=800001,
    Lots=0.01,
)


def params(**over):
    p = dict(P_SHIPPED)
    p.update(over)
    return p


# ------------------------------------------------------------------ data
def load_h4(start="2013-01-01", warmup_from_full=True):
    """Identical loader to research/slipstream/engine.py::load_h4()."""
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
def tr_mt5(h, l, c):
    """ATR.mq5's TR: max(high, close_prev) - min(low, close_prev); TR[0]=0."""
    tr = np.empty(len(h))
    tr[0] = 0.0
    pc = c[:-1]
    tr[1:] = np.maximum(h[1:], pc) - np.minimum(l[1:], pc)
    return tr


def atr_mt5(h, l, c, n=14):
    """iATR(n): rolling SMA of TR, first valid at index n. Reused verbatim
    from research/slipstream/engine.py; validated here against the CSV's own
    chk_atr14 column (see chk_check.py)."""
    tr = tr_mt5(h, l, c)
    out = np.array(pd.Series(tr).rolling(n).mean().values, dtype=float)
    out[:n] = np.nan
    return out


def stoch_mt5(h, l, c, kper, dper, slowing):
    """Port of MT5 Stochastic.mq5 (MODE_SMA, STO_LOWHIGH) - the exact handle
    AuRebound_EA.mq5 creates at mq5 1023.  Returns (main %K, signal %D).
    NOTE: there is NO chk_* column for Stochastic in GOLD_H4.csv, so this is
    'implemented per the MQL5 source spec', not MT5-output-verified."""
    ll = pd.Series(l).rolling(kper).min().values
    hh = pd.Series(h).rolling(kper).max().values
    num = pd.Series(c - ll).rolling(slowing).sum().values
    den = pd.Series(hh - ll).rolling(slowing).sum().values
    with np.errstate(divide="ignore", invalid="ignore"):
        main = np.where(den == 0.0, 100.0,
                        100.0 * num / np.where(den == 0.0, 1.0, den))
    main = np.where(np.isnan(num) | np.isnan(den), np.nan, main)
    signal = pd.Series(main).rolling(dper).mean().values
    return main, signal


def sma(x, n):
    return pd.Series(x).rolling(n).mean().values


def popstd(x, n):
    """StdDev() at mq5 321-326 divides the squared deviations by `period`
    (population), not period-1, and uses the SAME window's SMA as the mean."""
    s = pd.Series(x)
    m = s.rolling(n).mean()
    m2 = (s * s).rolling(n).mean()
    return np.sqrt(np.maximum((m2 - m * m).values, 0.0))


# ---------------------------------------------------------------- context
def build_context(d, p):
    """Everything the EA reads off its a_* arrays, on the full bar series."""
    o = d["open"].values.astype(float)
    h = d["high"].values.astype(float)
    l = d["low"].values.astype(float)
    c = d["close"].values.astype(float)
    t = d["time"].values
    spread_pts = d["spread"].values.astype(float)

    atr = atr_mt5(h, l, c, p["ATRPeriod"])
    stmain, stD = stoch_mt5(h, l, c, p["StochK"], p["StochD"], p["StochSlow"])

    mid = sma(c, p["BBPeriod"])
    sd = popstd(c, p["BBPeriod"])
    up = mid + p["BBDev"] * sd
    lo = mid - p["BBDev"] * sd

    ts = pd.DatetimeIndex(d["time"])
    ctx = dict(
        n=len(c), o=o, h=h, l=l, c=c, t=t,
        spread=spread_pts * POINT,
        atr=atr, stD=stD, stMain=stmain,
        bb_mid=mid, bb_up=up, bb_lo=lo,
        hour=ts.hour.values, dow=ts.dayofweek.values,   # Mon=0 .. Fri=4
        year=ts.year.values,
    )

    # NearUpperAt/NearLowerAt (mq5 429-440) - note these use a_atr[k], the
    # ATR of the bar being tested, NOT the trade's frozen entryATR.
    with np.errstate(invalid="ignore"):
        ctx["near_lo"] = (l <= lo + p["EntryProx"] * atr) & (atr > 0.0) & ~np.isnan(lo)
        ctx["near_up"] = (h >= up - p["EntryProx"] * atr) & (atr > 0.0) & ~np.isnan(up)
    ctx["near_lo"] = np.where(np.isnan(atr), False, ctx["near_lo"])
    ctx["near_up"] = np.where(np.isnan(atr), False, ctx["near_up"])
    return ctx


def turn_up(ctx, i, mode="SIGNAL_LINE_TURN"):
    """mq5 410-416."""
    D = ctx["stD"]
    if i < 2 or np.isnan(D[i]) or np.isnan(D[i - 1]) or np.isnan(D[i - 2]):
        return False
    if mode == "SIGNAL_LINE_TURN":
        return bool(D[i] > D[i - 1] and D[i - 1] <= D[i - 2])
    return bool(D[i - 1] < 20.0 and D[i] >= 20.0)


def turn_dn(ctx, i, mode="SIGNAL_LINE_TURN"):
    """mq5 417-423."""
    D = ctx["stD"]
    if i < 2 or np.isnan(D[i]) or np.isnan(D[i - 1]) or np.isnan(D[i - 2]):
        return False
    if mode == "SIGNAL_LINE_TURN":
        return bool(D[i] < D[i - 1] and D[i - 1] >= D[i - 2])
    return bool(D[i - 1] > 80.0 and D[i] <= 80.0)


def turn_up_vec(ctx, mode="SIGNAL_LINE_TURN"):
    D = ctx["stD"]
    out = np.zeros(len(D), bool)
    if mode == "SIGNAL_LINE_TURN":
        out[2:] = (D[2:] > D[1:-1]) & (D[1:-1] <= D[:-2])
    else:
        out[2:] = (D[1:-1] < 20.0) & (D[2:] >= 20.0)
    out &= ~np.isnan(D)
    out[:2] = False
    return out


def turn_dn_vec(ctx, mode="SIGNAL_LINE_TURN"):
    D = ctx["stD"]
    out = np.zeros(len(D), bool)
    if mode == "SIGNAL_LINE_TURN":
        out[2:] = (D[2:] < D[1:-1]) & (D[1:-1] >= D[:-2])
    else:
        out[2:] = (D[1:-1] > 80.0) & (D[2:] <= 80.0)
    out &= ~np.isnan(D)
    out[:2] = False
    return out


def is_indecision(ctx, i):
    """mq5 327-338."""
    rng = ctx["h"][i] - ctx["l"][i]
    if rng <= 0:
        return False
    o, c = ctx["o"][i], ctx["c"][i]
    body = abs(c - o)
    uw = ctx["h"][i] - max(o, c)
    lw = min(o, c) - ctx["l"][i]
    return bool(body / rng < 0.35 and uw > 0.2 * rng and lw > 0.2 * rng)


def stoch_persistence(ctx, i, below20):
    """mq5 339-350."""
    D = ctx["stD"]
    cnt, j = 0, i - 1
    while j > 0 and not np.isnan(D[j]):
        if below20 and D[j] < 20.0:
            cnt += 1; j -= 1
        elif (not below20) and D[j] > 80.0:
            cnt += 1; j -= 1
        else:
            break
    return cnt


def raw_signal(ctx, i, p):
    """CheckForEntry()'s signal computation for signal bar `i`, everything
    except the cooldown gate (mq5 1499-1535).  Returns +1 / -1 / 0."""
    lb = p["Lookback"]
    w0 = max(0, i - lb)
    recent_lo = bool(ctx["near_lo"][w0:i + 1].any())
    recent_up = bool(ctx["near_up"][w0:i + 1].any())

    mode = p["StochMode"]
    long_sig = recent_lo and turn_up(ctx, i, mode)
    short_sig = recent_up and turn_dn(ctx, i, mode)

    if p["BlockIndecision"] and is_indecision(ctx, i):
        return 0

    if p["UseSessionFilter"] or p["BlockFridayClose"]:
        if p["UseSessionFilter"] and ctx["hour"][i] == p["BlockedHour"]:
            return 0
        # MQL5 FRIDAY == 5 in ENUM_DAY_OF_WEEK (Sun=0); pandas dayofweek Fri==4
        if p["BlockFridayClose"] and ctx["dow"][i] == 4 and ctx["hour"][i] >= p["FridayCloseHour"]:
            return 0

    # NewsBlackoutActive(): returns false under MQL_TESTER (mq5 1484) -> inert.

    if mode == "THRESHOLD_CROSS" and p["UsePersistFilter"]:
        if long_sig and stoch_persistence(ctx, i, True) < p["MinPersistBars"]:
            long_sig = False
        if short_sig and stoch_persistence(ctx, i, False) < p["MinPersistBars"]:
            short_sig = False

    if long_sig and short_sig:      # `ambiguous` - both suppressed
        return 0
    if long_sig:
        return 1
    if short_sig:
        return -1
    return 0


def compute_sl_dist(ctx, i, direction, px, p):
    """ComputeSLDist() (mq5 1575-1597). px is the LIVE fill price (ask for a
    long, bid for a short), matching the real code's SymbolInfoDouble call."""
    a = ctx["atr"][i]
    w0 = max(0, i - p["Lookback"])
    if direction > 0:
        extreme = ctx["l"][w0:i + 1].min()
        sl = abs(px - extreme) + p["SLBuffer"] * a
    else:
        extreme = ctx["h"][w0:i + 1].max()
        sl = abs(extreme - px) + p["SLBuffer"] * a
    if p["UseSLCap"]:
        sl = min(sl, p["SLCapATR"] * a)
    return sl, a


def band_exit(ctx, i, direction, entry_atr, bars_in_trade, p):
    """ManageOpenPosition()'s opposite-band-reject test (mq5 1308-1329).
    NOTE the deliberate asymmetry vs NearUpperAt/NearLowerAt: this window test
    uses the trade's FROZEN entryATR, not a_atr[k]."""
    w0 = max(0, i - min(p["Lookback"], bars_in_trade))
    mode = p["StochMode"]
    if direction > 0:
        opp = False
        for k in range(w0, i + 1):
            up = ctx["bb_up"][k]
            if not np.isnan(up) and ctx["h"][k] >= up - p["EntryProx"] * entry_atr:
                opp = True
                break
        return opp and turn_dn(ctx, i, mode)
    opp = False
    for k in range(w0, i + 1):
        lo = ctx["bb_lo"][k]
        if not np.isnan(lo) and ctx["l"][k] <= lo + p["EntryProx"] * entry_atr:
            opp = True
            break
    return opp and turn_up(ctx, i, mode)


def first_tradable(ctx, p):
    """Earliest bar index at which every array the EA reads is calculated.
    Mirrors ProcessNewBar()'s `warmup` guard (mq5 1196-1198)."""
    need = max(p["BBPeriod"],
               max(p["ATRPeriod"], p["StochK"] + p["StochD"] + p["StochSlow"])) + 20
    D = ctx["stD"]
    ok = np.where(~np.isnan(D) & ~np.isnan(ctx["atr"]) & ~np.isnan(ctx["bb_mid"]))[0]
    return max(int(ok[0]) + 2, need)
