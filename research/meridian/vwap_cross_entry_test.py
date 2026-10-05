"""
NEW CANDIDATE (2026-10-05, user's own idea): instead of Meridian's shipped
signal (21/50 EMA cross, confirmed by close vs 250-SMA trend filter AND
close vs session VWAP, both checked on the same bar), trigger directly on
the 21 EMA itself crossing the session VWAP - crossing from below = buy,
from above = sell. Everything else (250-SMA trend confirm, S/R distance
filter, 2.5xATR stop, Friday flatten, hour-0 reversal-retry, real spread
cost, stale-ticket-after-SL quirk) is held IDENTICAL to msim.py's shipped
V102 construction - this is a single-variable swap of the entry TRIGGER
only, not a new strategy from scratch, so any difference in outcome is
attributable to that one change.

This is a near-verbatim copy of msim.simulate()'s loop (not an import-and-
patch, because the reversal-close logic shares the same `above` array as
the entry trigger, and entry_fn's existing hook in msim.py deliberately
bypasses the S/R filter - wrong for testing a real candidate signal that
should still be judged WITH that filter in place, not without it).

Honest K for this idea: 1 (first and only test of this construction run on
this data - no threshold/variant sweep). If this gets revisited later,
count this as attempt #1 against research/meridian/'s own Meridian window.
"""
import sys
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(0, "/home/user/test-project/research/meridian")
import bars as B      # noqa: E402
import msim as M      # noqa: E402

POINT = B.POINT


@dataclass
class VP:
    pconf: int = 250
    conf: str = "sma"
    use_sr: bool = True
    sr_days: int = 3
    min_sr: float = 0.50
    stop_atr: float = 2.5
    max_spread: int = 60
    fri_close: int = 22
    entry_from_min: int = 65
    stale_ticket_bar: bool = True
    sl_cooldown: int = 1
    hour0_reject: bool = True
    rev_retry_minutes: int = 60
    point: Optional[float] = None
    entry_fn: Optional[Callable] = None   # random-timing null hook, same shape as msim.MP.entry_fn


def simulate_vwap_cross(ctx, p=VP(), start=M.WIN_START, end=M.WIN_END):
    t64 = ctx["t64"]
    i0 = int(np.searchsorted(t64, np.datetime64(start)))
    i1 = int(np.searchsorted(t64, np.datetime64(end)))
    o, h, l, c, spread, atr, vwap = ctx["o"], ctx["h"], ctx["l"], ctx["c"], ctx["spread"], ctx["atr"], ctx["vwap"]
    m21 = M.ma(ctx, 21, "ema")
    mc = M.ma(ctx, p.pconf, p.conf)
    srh, srl = M.sr_arrays(ctx, p.sr_days)
    above = m21 > vwap   # THE ONE CHANGE: 21 EMA vs session VWAP, not 21 EMA vs 50 EMA
    trades, pos = [], None
    since_sl = 10 ** 9
    pending_rev_arm_t = None
    stats = dict(crosses=0, blk_conf=0, blk_sr=0, blk_spread=0, blk_reverse_bar=0)

    def fri(t):
        return ctx["dow"][t] == 5 and ctx["hour"][t] >= p.fri_close

    def close(t, px, reason):
        nonlocal pos, pending_rev_arm_t
        pos.update(exit_i=t, exit=px, pnl=(px - pos["entry"]) * pos["dir"], reason=reason, exit_time=t64[t])
        trades.append(pos)
        pos = None
        pending_rev_arm_t = None

    def try_entry(t, sp):
        nonlocal pos
        s = t - 1
        if p.entry_fn is not None:
            if ctx["mod"][t] < p.entry_from_min:
                return
            d = p.entry_fn(ctx, t)
            if d == 0:
                return
            if p.max_spread > 0 and spread[t] > p.max_spread:
                return
            a = atr[s]
            if not (a > 0):
                return
        else:
            if above[s] == above[s - 1]:
                return
            if ctx["mod"][t] < p.entry_from_min:
                return
            d = 1 if above[s] else -1
            stats["crosses"] += 1
            if p.max_spread > 0 and spread[t] > p.max_spread:
                stats["blk_spread"] += 1
                return
            if np.isnan(mc[s]):
                return
            # confirm vs the 250-SMA trend filter only - NOT vs VWAP again,
            # since VWAP is now the trigger itself (checking close-vs-VWAP a
            # second time at the cross bar would be near-tautological).
            ok = (c[s] > mc[s]) if d > 0 else (c[s] < mc[s])
            if not ok:
                stats["blk_conf"] += 1
                return
            a = atr[s]
            if not (a > 0):
                return
        if p.entry_fn is None and p.use_sr and not np.isnan(srh[t]):
            sr = abs(srh[t] - c[s]) / a if d > 0 else abs(c[s] - srl[t]) / a
            if sr < p.min_sr:
                stats["blk_sr"] += 1
                return
        entry = o[t] + sp if d > 0 else o[t]
        sl = entry - d * p.stop_atr * a
        # diagnostic for the user's own hypothesis ("Meridian enters already
        # overextended into overbought/oversold, hoping it stays extended"):
        # how far was price from VWAP, in ATR units, at the moment of entry?
        ext_atr = abs(c[s] - vwap[s]) / a if a > 0 else float("nan")
        pos = dict(entry_i=t, entry_time=t64[t], dir=d, entry=entry, sl=sl, sl0=sl, atr=a, peak=entry, bars=0,
                   ext_atr=ext_atr)

    point = POINT if p.point is None else p.point
    for t in range(i0, i1):
        sp = spread[t] * point
        if pos is not None and fri(t):
            close(t, o[t] if pos["dir"] > 0 else o[t] + sp, "FRIDAY")
        if pos is not None and pending_rev_arm_t is not None:
            if ctx["hour"][t] != 0:
                close(t, o[t] if pos["dir"] > 0 else o[t] + sp, "REVERSAL_RETRY")
            elif p.rev_retry_minutes > 0:
                waited_min = (t64[t] - t64[pending_rev_arm_t]) / np.timedelta64(1, "m")
                if waited_min >= p.rev_retry_minutes:
                    pending_rev_arm_t = None
        if pos is not None:
            pos["bars"] += 1
            d = pos["dir"]
            s = t - 1
            if above[s] != above[s - 1] and (1 if above[s] else -1) != d and p.hour0_reject and ctx["hour"][t] == 0:
                if p.rev_retry_minutes > 0 and pending_rev_arm_t is None:
                    pending_rev_arm_t = t
            elif above[s] != above[s - 1] and (1 if above[s] else -1) != d:
                close(t, o[t] if d > 0 else o[t] + sp, "REVERSAL")
                stats["blk_reverse_bar"] += 1
        elif not fri(t):
            if p.stale_ticket_bar and since_sl < p.sl_cooldown:
                pass
            else:
                try_entry(t, sp)
        since_sl += 1
        if pos is not None:
            d = pos["dir"]
            if d > 0 and l[t] <= pos["sl"]:
                close(t, min(pos["sl"], o[t]), "SL")
                since_sl = 0
            elif d < 0 and h[t] + sp >= pos["sl"]:
                close(t, max(pos["sl"], o[t] + sp), "SL")
                since_sl = 0
    if pos is not None:
        close(i1 - 1, c[i1 - 1], "END")
    return trades, stats


def extension_at_entry(ctx, trades):
    """|close(entry_bar-1) - VWAP(entry_bar-1)| / ATR(entry_bar-1) - how far
    price already was from session fair-value, in ATR units, the instant
    before each trade's entry signal fired. Recomputed from ctx for trades
    that don't already carry it (e.g. msim.py's shipped-signal trades)."""
    out = []
    for t in trades:
        if "ext_atr" in t:
            out.append(t["ext_atr"])
            continue
        s = t["entry_i"] - 1
        a = ctx["atr"][s]
        if a > 0:
            out.append(abs(ctx["c"][s] - ctx["vwap"][s]) / a)
    return np.array(out)


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([t["pnl"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  avg={pnl.mean():7.3f}")


def random_entry_fn_matched(ctx, i0, i1, n_target, entry_from_min, seed=0):
    """Random-timing null: exactly n_target entries, placed uniformly at
    random among bars eligible by the SAME session/Friday gates the real
    signal uses (entry_from_min, not Friday>=22:00) - matched count, same
    real spread cost and same exit machinery as the real run (both go
    through simulate_vwap_cross's own SL/Friday/hour0-retry code), just
    with the entry BAR chosen randomly instead of by the 21-vs-VWAP cross.
    Direction is drawn to match the real run's own long/short split so the
    null isn't quietly biased by a directional market bias."""
    rng = np.random.default_rng(seed)
    eligible = [t for t in range(i0 + 1, i1) if ctx["mod"][t] >= entry_from_min and
                not (ctx["dow"][t] == 5 and ctx["hour"][t] >= 22)]
    chosen = set(rng.choice(eligible, size=min(n_target, len(eligible)), replace=False).tolist())
    return chosen


def make_entry_fn(chosen_set, long_frac, seed=1):
    rng = np.random.default_rng(seed)
    dirs = {t: (1 if rng.random() < long_frac else -1) for t in chosen_set}

    def fn(ctx, t):
        return dirs.get(t, 0)
    return fn


if __name__ == "__main__":
    ctx = M.build_ctx()
    n_bars = len(ctx["t64"])
    cutoff = int(n_bars * 0.70)
    cutoff_time = pd.Timestamp(ctx["t64"][cutoff])
    full_start, full_end = pd.Timestamp(ctx["t64"][0]), pd.Timestamp(ctx["t64"][-1])
    print(f"GOLD M5 real data: {full_start} .. {full_end}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {cutoff_time}")

    vp = VP()

    print("\n" + "=" * 90)
    print("NEW SIGNAL: 21 EMA crosses session VWAP (vs shipped: 21/50 EMA cross + VWAP/150-SMA confirm)")
    print("=" * 90)

    for label, start, end in (("FULL HISTORY", full_start, full_end),
                               ("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                               ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
        trades, stats = simulate_vwap_cross(ctx, vp, start=start, end=end)
        report(f"{label:28s} new-signal", trades)
        ext = extension_at_entry(ctx, trades)
        print(f"    (crosses={stats['crosses']}, blk_conf={stats['blk_conf']}, "
              f"blk_sr={stats['blk_sr']}, blk_spread={stats['blk_spread']}, "
              f"reversal_closes={stats['blk_reverse_bar']}, "
              f"extension@entry: median={np.median(ext):.3f} ATR, mean={ext.mean():.3f} ATR)")

    print("\n" + "=" * 90)
    print("For reference: shipped V102 signal (21/50 cross) over the SAME full history/IS/OOS splits")
    print("=" * 90)
    for label, start, end in (("FULL HISTORY", full_start, full_end),
                               ("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                               ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
        trades, stats = M.simulate(ctx, M.V102, start=start, end=end)
        report(f"{label:28s} shipped-V102", trades)
        ext = extension_at_entry(ctx, trades)
        print(f"    extension@entry (|close-VWAP|/ATR at signal): median={np.median(ext):.3f} ATR, "
              f"mean={ext.mean():.3f} ATR")

    print("\n" + "=" * 90)
    print("RANDOM-TIMING NULL for the NEW signal: same exits/spread/stop, entry count matched,")
    print("entries placed uniformly at random among session-eligible bars (2000 draws)")
    print("=" * 90)
    i0_full = int(np.searchsorted(ctx["t64"], np.datetime64(full_start)))
    i1_full = int(np.searchsorted(ctx["t64"], np.datetime64(full_end)))
    real_trades, _ = simulate_vwap_cross(ctx, vp, start=full_start, end=full_end)
    n_real = len(real_trades)
    long_frac = np.mean([t["dir"] > 0 for t in real_trades]) if real_trades else 0.5
    real_pf = pf([t["pnl"] for t in real_trades])
    print(f"  real new-signal: n={n_real}, PF={real_pf:.3f}, long_frac={long_frac:.2f}")

    NDRAWS = 2000
    null_pfs, null_nets = [], []
    for seed in range(NDRAWS):
        chosen = random_entry_fn_matched(ctx, i0_full, i1_full, n_real, vp.entry_from_min, seed=seed * 2)
        efn = make_entry_fn(chosen, long_frac, seed=seed * 2 + 1)
        null_p = replace(vp, entry_fn=efn)
        ntrades, _ = simulate_vwap_cross(ctx, null_p, start=full_start, end=full_end)
        pnl = np.array([t["pnl"] for t in ntrades])
        null_pfs.append(pf(pnl))
        null_nets.append(pnl.sum())
    null_pfs = np.array(null_pfs)
    p_value = (null_pfs >= real_pf).mean()
    print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
          f"p50={np.percentile(null_pfs,50):.3f}  p95={np.percentile(null_pfs,95):.3f}")
    print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} "
          f"random-timing draws with matched trade count/spread/exits")
    print(f"  p-value (P[null PF >= real PF]) = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")
    print(f"\n  Honest K for this idea: 1 (first test of this exact construction, no variant sweep run).")
