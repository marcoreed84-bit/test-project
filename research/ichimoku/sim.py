"""
Event-driven replica of Ichimoku_EA.mq5's OnTick() loop.

Exact ordering ported from mq5 681-704:
  per new bar j (first tick of bar j):
    0. [every tick] FridayCutoff(false): dow==Fri and hour>=InpFridayCloseHour
       -> ClosePosition("FRIDAY"). H4 bars start at 00/04/08/12/16/20, so hour
       21 falls INSIDE the Friday 20:00 bar. Modelled as an intra-bar event on
       that bar, priced at its close. (Approximation: the real flatten is at
       21:00, ~1h into a 4h bar. Flagged in the writeup.)
    1. new-bar gate, HasEnoughHistory()
    2. ManagePosition() (mq5 601-612):
         no position -> g_barsInTrade = 0
         g_barsInTrade >= InpMinHoldBars AND ShouldExit(bar j-1) -> close at
           open[j], g_barsInTrade = 0
         else g_barsInTrade++
       NOTE the counter is incremented AFTER the test, and is 0 on the bar
       after entry, so the earliest possible signal exit is bar E+minHold+1.
    3. TryEnter() (mq5 639-679):
         no position, not FridayCutoff(true) (Fri and hour>=InpNoEntryAfterHourFri),
         CheckEntry(bar j-1) != 0 -> fill at open[j], SL at
         price -/+ InpSafetyStopATR * ComputeATR(1,14) (Wilder), g_barsInTrade=0

The broker-side SL is live from the instant of the fill, so it is checked
intra-bar on the entry bar too, and it is NOT gated by InpMinHoldBars.
"""
import numpy as np
import engine as E

FRI = 4  # pandas dayofweek: Monday=0 .. Friday=4  (MqlDateTime day_of_week 5)


def simulate(ctx, p, fill="open", extra_filter=None, entry_override=None,
             pause_rule=None):
    """extra_filter(ctx, i, is_buy) -> bool, evaluated on the SIGNAL bar i
    (= bar j-1), same place an added MQL5 entry condition would sit.
    pause_rule: optional callable(trades_so_far, i) -> True to block entry
    (used for the consecutive-loss circuit-breaker test)."""
    sig = entry_signal_cached(ctx, p) if entry_override is None else entry_override
    xl, xs = E.exit_signal(ctx, p)
    o, h, l, c = ctx["open"], ctx["high"], ctx["low"], ctx["close"]
    atr = ctx["atr"]
    dow, hour = ctx["dow"], ctx["hour"]
    n = ctx["n"]
    minhold = p["min_hold_bars"]
    stopmult = p["safety_stop_atr"]
    warm = p["senkou_b"] + 2*p["displacement"] + 20

    px_at = (lambda j: o[j]) if fill == "open" else (lambda j: c[j-1])

    trades = []
    pos = 0          # 0 flat, +1 long, -1 short
    entry_i = -1; entry_px = 0.0; sl = 0.0; bars_in = 0

    for j in range(max(warm, 1), n):
        # ---- 2. ManagePosition (signal exit at this bar's open)
        if pos != 0:
            sx = xl[j-1] if pos == 1 else xs[j-1]
            if bars_in >= minhold and sx:
                trades.append(_mk(ctx, entry_i, entry_px, j, px_at(j), pos,
                                  "SIGNAL", bars_in))
                pos = 0; bars_in = 0
            else:
                bars_in += 1

        # ---- 3. TryEnter
        if pos == 0:
            if not (dow[j] == FRI and hour[j] >= p["no_entry_after_hour_fri"]):
                d = sig[j-1]
                if d != 0 and (extra_filter is None or extra_filter(ctx, j-1, d == 1)):
                    if pause_rule is None or not pause_rule(trades, j):
                        pos = d; entry_i = j; entry_px = px_at(j); bars_in = 0
                        if stopmult > 0 and np.isfinite(atr[j-1]) and atr[j-1] > 0:
                            sl = entry_px - d*stopmult*atr[j-1]
                        else:
                            sl = np.nan

        # ---- intra-bar: broker SL (live immediately, not gated by minhold)
        if pos != 0 and np.isfinite(sl):
            if (pos == 1 and l[j] <= sl) or (pos == -1 and h[j] >= sl):
                trades.append(_mk(ctx, entry_i, entry_px, j, sl, pos, "STOP", bars_in))
                pos = 0; bars_in = 0

        # ---- 0. Friday flatten (intra-bar, on the Fri 20:00 bar)
        if pos != 0 and p["close_friday"] and dow[j] == FRI and \
           hour[j] + 4 > p["friday_close_hour"] and hour[j] <= p["friday_close_hour"]:
            trades.append(_mk(ctx, entry_i, entry_px, j, c[j], pos, "FRIDAY", bars_in))
            pos = 0; bars_in = 0

    return trades


_SIG_CACHE = {}
def entry_signal_cached(ctx, p):
    key = (id(ctx), p["entry_mode"], p["require_chikou"], p["use_adx"],
           p["adx_threshold"], p["use_rsi"], p["use_cmf"], p["rsi_hi"], p["rsi_lo"])
    if key not in _SIG_CACHE:
        _SIG_CACHE[key] = E.entry_signal(ctx, p)
    return _SIG_CACHE[key]


def _mk(ctx, ei, epx, xi, xpx, d, reason, bars):
    return dict(entry_i=ei, entry_px=epx, exit_i=xi, exit_px=xpx, dir=d,
                reason=reason, bars=bars, pnl=(xpx-epx)*d,
                entry_t=ctx["time"][ei], exit_t=ctx["time"][xi],
                year=ctx["year"][ei])


# ------------------------------------------------------------- stats
def stats(trades):
    if not trades:
        return dict(n=0, pf=float("nan"), net=0.0, win=float("nan"))
    p = np.array([t["pnl"] for t in trades])
    gw = p[p > 0].sum(); gl = -p[p < 0].sum()
    return dict(n=len(p), pf=(gw/gl if gl > 0 else float("inf")),
                net=round(p.sum(), 2), win=round(100*(p > 0).mean(), 1),
                avg_win=round(p[p > 0].mean(), 2) if (p > 0).any() else 0.0,
                avg_loss=round(p[p < 0].mean(), 2) if (p < 0).any() else 0.0,
                worst=round(p.min(), 2), maxdd=round(max_dd(p), 2))


def max_dd(pnl):
    eq = np.cumsum(pnl); peak = np.maximum.accumulate(eq)
    return float((peak - eq).max()) if len(eq) else 0.0


def fmt(s):
    if s["n"] == 0: return "n=0"
    return (f"n={s['n']:4d} PF={s['pf']:.3f} net=${s['net']:9.2f} win={s['win']:4.1f}% "
            f"worst={s['worst']:8.2f} maxDD={s['maxdd']:8.2f}")


# ----------------------------------------------- project rigor helpers
def split_stats(trades, n_total, is_frac=0.7):
    """Chronological 70/30 IS/OOS on BAR index (same as sr_reject_test.py)."""
    if not trades: return None, None
    cut = int(n_total * is_frac)
    return (stats([t for t in trades if t["entry_i"] < cut]),
            stats([t for t in trades if t["entry_i"] >= cut]))


def tail_concentration(trades):
    if not trades: return None
    pnl = sorted([t["pnl"] for t in trades], reverse=True)
    net = sum(pnl); top5 = sum(pnl[:5])
    return dict(net=round(net, 2),
                top5_pct=round(100*top5/net, 1) if net else float("nan"),
                ex_top5_net=round(net-top5, 2))


def year_breakdown(trades):
    ys = {}
    for t in trades:
        ys.setdefault(int(t["year"]), []).append(t["pnl"])
    return {y: round(sum(v), 2) for y, v in sorted(ys.items())}


def neg_years(trades):
    yb = year_breakdown(trades)
    return sum(1 for v in yb.values() if v < 0), len(yb)


def permutation_test(base_trades, cand_trades, n_draws=2000, seed=0):
    """Null = random same-size subsets of the BASE signal's OWN trades.
    This is the stricter 'does the added filter beat the base signal' null
    the project switched to, NOT random bars / pure noise."""
    if not cand_trades or not base_trades: return None
    rng = np.random.default_rng(seed)
    k = len(cand_trades)
    allp = np.array([t["pnl"] for t in base_trades])
    if k > len(allp): return None
    real = sum(t["pnl"] for t in cand_trades)
    draws = np.array([allp[rng.choice(len(allp), k, replace=False)].sum()
                      for _ in range(n_draws)])
    return dict(percentile=round(100*(draws < real).mean(), 1), real_net=round(real, 2),
                null_mean=round(draws.mean(), 2), null_std=round(draws.std(), 2), k=k)


def permutation_test_bestofN(base_trades, cand_trade_sets, n_draws=2000, seed=0):
    """Best-of-many-cells correction: if you searched N variants and kept the
    best, the null must also be best-of-N. Returns the percentile of the real
    BEST net against the distribution of best-of-N random-subset nets."""
    if not base_trades: return None
    rng = np.random.default_rng(seed)
    allp = np.array([t["pnl"] for t in base_trades])
    ks = [len(ts) for ts in cand_trade_sets if ts and len(ts) <= len(allp)]
    if not ks: return None
    real_best = max(sum(t["pnl"] for t in ts) for ts in cand_trade_sets
                    if ts and len(ts) <= len(allp))
    draws = []
    for _ in range(n_draws):
        draws.append(max(allp[rng.choice(len(allp), k, replace=False)].sum() for k in ks))
    draws = np.array(draws)
    return dict(percentile=round(100*(draws < real_best).mean(), 1),
                real_best=round(real_best, 2), n_cells=len(ks),
                null_mean=round(draws.mean(), 2))
