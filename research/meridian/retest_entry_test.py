"""
NEW CANDIDATE (2026-10-06, user's own observation from a real live Meridian
chart screenshot): Meridian's shipped entry (msim.py's V102 - 21/50 EMA
cross, confirmed by close vs 250-SMA AND close vs VWAP, both on the SAME
bar the cross confirms) enters IMMEDIATELY at the next bar's open, with NO
check on how far price has already run from the 21/50 EMAs by that point.
The screenshot showed a real example: entry 4168.62 while the 21 EMA sat
at 4162.19 and the 50 EMA at 4160.79 - price already well clear of both.
This is the exact same "entry chasing" problem independently found and
fixed today in research/ema_vwap_pullback/ema_vwap_pullback_test.py.

The user's proposal: instead of entering right at the cross confirmation
(often already extended), WAIT for price to retest back down into the
21/50 EMA zone first - "if it bounces off the 21/50 EMA, that's when you
know the trend is actually going to continue."

This is a single-variable swap of the entry TRIGGER TIMING only - same
shipped cross+confirm gate (above[s]!=above[s-1], close vs 250-SMA, close
vs VWAP, same S/R filter, same InpStopATR=2.5 stop, same Friday/hour0-
retry/reversal-close machinery - all identical to msim.py's V102), reused
near-verbatim from msim.simulate() (not imported-and-patched, for the same
reason vwap_cross_entry_test.py gives: the reversal-close logic shares the
same `above` array as the entry trigger, and entry_fn's hook bypasses the
S/R filter).

SEQUENCE:
  1. Cross+confirm gate fires at bar s=t-1 (same as shipped) - this ARMS a
     pending setup, direction d, but does NOT enter yet.
  2. Scanning forward from bar t, within RETEST_MAX_BARS bars: look for the
     first bar where price actually comes back within RETEST_TOL_ATR x ATR
     of EITHER the 21 or 50 EMA (close within that tolerance of either
     line) - "price is now buying the 21/50 EMA" per the user's own words.
  3. If an OPPOSING 21/50 cross happens before a retest is found, the setup
     is invalidated (cancelled, not retried).
  4. On finding the retest bar, enter at the FOLLOWING bar's open (signal-
     then-fill, same convention as every other construction in this
     project), real spread charged, stop = 2.5xATR (unchanged), S/R filter
     re-checked at the entry bar (unchanged).
  5. If no retest happens within the window, no trade - skipped, not
     retried.

Honest K=1 (single pre-specified construction, no threshold sweep). Full
real GOLD M5 history (2022-07-04 onward, NOT the narrow 2026-01-01..09-21
real-MT5-validation window used elsewhere for bar-matching), walk-forward
70/30 split, same pattern as every other Meridian research test this
session.
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(0, "/home/user/test-project/research/meridian")
import bars as B      # noqa: E402
import msim as M      # noqa: E402

POINT = B.POINT
RETEST_TOL_ATR = 0.30
RETEST_MAX_BARS = 3   # 2026-10-06 (user correction): "the next couple candles", not a 2h window -
                       # a retest that takes hours to show up has already lost whatever immediacy
                       # made it a retest rather than just noise; tightened 24 -> 3 bars (15 min)


def simulate_retest(ctx, p=M.V102, start=M.WIN_START, end=M.WIN_END):
    t64 = ctx["t64"]
    i0 = int(np.searchsorted(t64, np.datetime64(start)))
    i1 = int(np.searchsorted(t64, np.datetime64(end)))
    o, h, l, c, spread, atr, vwap = ctx["o"], ctx["h"], ctx["l"], ctx["c"], ctx["spread"], ctx["atr"], ctx["vwap"]
    m21, m50, mc = M.ma(ctx, p.p21, p.fast), M.ma(ctx, p.p50, p.fast), M.ma(ctx, p.pconf, p.conf)
    srh, srl = M.sr_arrays(ctx, p.sr_days)
    above = m21 > m50
    trades, pos = [], None
    since_sl = 10 ** 9
    pending_rev_arm_t = None
    pending = None   # armed-but-not-yet-entered setup: dict(dir, armed_i)
    stats = dict(crosses=0, blk_conf=0, blk_sr=0, blk_spread=0, blk_reverse_bar=0,
                 armed=0, retested=0, invalidated=0, timed_out=0)

    def fri(t):
        return ctx["dow"][t] == 5 and ctx["hour"][t] >= p.fri_close

    def close(t, px, reason):
        nonlocal pos, pending_rev_arm_t
        pos.update(exit_i=t, exit=px, pnl=(px - pos["entry"]) * pos["dir"], reason=reason, exit_time=t64[t])
        trades.append(pos)
        pos = None
        pending_rev_arm_t = None

    def arm_or_check(t, sp):
        nonlocal pos, pending
        s = t - 1
        # (1) look for a fresh cross+confirm to ARM a new pending setup -
        # same gate as msim.V102's try_entry(), unchanged.
        if above[s] != above[s - 1]:
            stats["crosses"] += 1
            d = 1 if above[s] else -1
            if ctx["mod"][t] >= p.entry_from_min and not np.isnan(mc[s]):
                ok = (c[s] > mc[s]) if d > 0 else (c[s] < mc[s])
                if p.use_vwap:
                    ok = ok and ((c[s] > vwap[s]) if d > 0 else (c[s] < vwap[s]))
                if ok:
                    pending = dict(dir=d, armed_i=t)
                    stats["armed"] += 1
                else:
                    stats["blk_conf"] += 1
        # (2) if a setup is pending, check for the retest / invalidation /
        # timeout, each bar, BEFORE trying to enter on it.
        if pending is not None:
            d = pending["dir"]
            if (t - pending["armed_i"]) > RETEST_MAX_BARS:
                stats["timed_out"] += 1
                pending = None
                return
            # invalidated: an OPPOSING cross happened before a retest was found
            if t > pending["armed_i"] and above[s] != above[s - 1] and (1 if above[s] else -1) != d:
                stats["invalidated"] += 1
                pending = None
                return
            a = atr[s]
            if not (a > 0):
                return
            tol = RETEST_TOL_ATR * a
            retested = (abs(c[s] - m21[s]) <= tol) or (abs(c[s] - m50[s]) <= tol)
            if not retested:
                return
            stats["retested"] += 1
            # entry fires at THIS bar's open (bar t, the one right after the
            # retest bar s closed) - same signal-bar-then-next-open fill
            # convention used throughout this project.
            if p.max_spread > 0 and spread[t] > p.max_spread:
                stats["blk_spread"] += 1
                pending = None
                return
            if p.use_sr and not np.isnan(srh[t]):
                sr = abs(srh[t] - c[s]) / a if d > 0 else abs(c[s] - srl[t]) / a
                if sr < p.min_sr:
                    stats["blk_sr"] += 1
                    pending = None
                    return
            entry = o[t] + sp if d > 0 else o[t]
            sl = entry - d * p.stop_atr * a
            pos = dict(entry_i=t, entry_time=t64[t], dir=d, entry=entry, sl=sl, sl0=sl, atr=a, peak=entry, bars=0)
            pending = None

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
                arm_or_check(t, sp)
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


def random_dirs_matched(dirs, eligible_bars, seed):
    rng = np.random.default_rng(seed)
    eligible = rng.choice(eligible_bars, size=len(dirs), replace=False)
    order = rng.permutation(len(dirs))
    out = {}
    for bar, idx in zip(eligible, order):
        out[int(bar)] = dirs[idx]
    return out


def make_entry_fn(bar_to_dir):
    def fn(ctx, t):
        return bar_to_dir.get(t, 0)
    return fn


if __name__ == "__main__":
    ctx = M.build_ctx()
    n_bars = len(ctx["t64"])
    cutoff = int(n_bars * 0.70)
    cutoff_time = pd.Timestamp(ctx["t64"][cutoff])
    full_start, full_end = pd.Timestamp(ctx["t64"][0]), pd.Timestamp(ctx["t64"][-1])
    print(f"GOLD M5 real data: {full_start} .. {full_end}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {cutoff_time}")
    print(f"Retest tolerance: {RETEST_TOL_ATR}xATR to either 21/50 EMA, within {RETEST_MAX_BARS} bars of the "
          f"cross+confirm. Same shipped V102 stop (2.5xATR), S/R filter, Friday/reversal machinery.\n")

    print(f"{'='*92}\nSAME ENTRY GATE, BUT WAIT FOR THE RETEST (new candidate)\n{'='*92}")
    for label, start, end in (("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                               ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
        trades, stats = simulate_retest(ctx, M.V102, start=start, end=end)
        report(label, trades)
        print(f"    armed={stats['armed']}  retested={stats['retested']}  invalidated={stats['invalidated']}  "
              f"timed_out={stats['timed_out']}  blk_sr={stats['blk_sr']}")

    print(f"\n{'='*92}\nFor reference: shipped V102 (enters immediately, no retest) over the SAME splits\n{'='*92}")
    for label, start, end in (("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                               ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
        trades, stats = M.simulate(ctx, M.V102, start=start, end=end)
        report(label, trades)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws - matched trade count/direction, SAME\n"
          f"real exit machinery (reversal-close, Friday flatten, hour0 retry, SL) via msim's own\n"
          f"entry_fn hook - not a hand-rolled stop-only loop (an earlier version of this null was\n"
          f"exactly that and produced an impossible median PF of 0.000 - fixed)\n{'='*92}")
    oos_trades, _ = simulate_retest(ctx, M.V102, start=cutoff_time, end=full_end)
    n_oos = len(oos_trades)
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few for a meaningful null")
    else:
        real_pf = pf([t["pnl"] for t in oos_trades])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}")
        i0 = int(np.searchsorted(ctx["t64"], np.datetime64(cutoff_time)))
        i1 = int(np.searchsorted(ctx["t64"], np.datetime64(full_end)))
        dirs = [t["dir"] for t in oos_trades]
        eligible_bars = np.array([t for t in range(i0 + 1, i1) if ctx["mod"][t] >= M.V102.entry_from_min])
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            rb = random_dirs_matched(dirs, eligible_bars, seed)
            p_null = replace(M.V102, entry_fn=make_entry_fn(rb))
            ntrades, _ = M.simulate(ctx, p_null, start=cutoff_time, end=full_end)
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K for this idea: 1 (single pre-specified construction, no sweep run).")
