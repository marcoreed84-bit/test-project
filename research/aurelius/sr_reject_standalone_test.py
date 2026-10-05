"""
NEW CANDIDATE (2026-10-05, user's own idea): a STANDALONE EA trading the
touch-and-reject of a prior-day S/R level directly - no Aurelius trend/MA/
volume/slope filters at all, unlike sr_reject_test.py (which tested the
same touch-and-reject idea bolted onto Aurelius's already-filtered entries,
and found it made results worse - PF 1.52 vs baseline 1.60, 79% fewer
trades, 77.5% of profit from just 5 trades, and a permutation test showing
the filtered subset sits at only the 43rd percentile of random same-size
draws from Aurelius's own trades).

This answers a genuinely different question: does the level itself produce
a tradable reaction on its own, when you trade EVERY real touch-and-reject
event rather than only the ones that also happen to pass an unrelated
trend-following EA's other gates? Same relationship as this project's
existing divergence work: "divergence as an add-on" (bolted onto an EA,
tested separately in research/divergence.py) vs "divergence as a
standalone system" (research/divergence_standalone/, found to lose money
outright on its own).

S/R LEVEL: prior InpSRDays=3 COMPLETED daily highs/lows - the exact
definition Aurelius_EA.mq5's own SRDistanceATR() uses, and the same one
drawn on its chart (InpShowSR) - reused verbatim (same rolling-window/
shift-by-1-day construction as research/meridian/msim.py's sr_arrays()),
not a new level definition.

ENTRY (same-bar fade/rejection, same construction and thresholds already
established in this repo for level-touch entries - research/aurelius/
sr_reject_test.py's TOUCH_TOL_ATR/REJECT_ATR=0.30, research/trendbreaker/
round_number_sr_test.py's same-bar touch+close-back-away pattern):
  SHORT: this bar's HIGH comes within TOUCH_TOL_ATR*ATR of the resistance
         level (prior 3-day high), AND this bar's CLOSE ends back below
         (level - REJECT_ATR*ATR).
  LONG:  mirror, at the support level (prior 3-day low).
  One trade at a time; a bar triggering both conditions is skipped
  (ambiguous). Entry fills at the NEXT bar's open, real spread charged.

EXIT: stop = level +/- STOP_ATR*ATR (beyond the level - a plain, un-tuned
1.0xATR, this project's typical sane starting distance for a structural
stop); target = RR=2.0 x risk (this project's typical go-to reward:risk,
not swept); a MAX_BARS=288 (~1 day) time-stop if neither is hit. If stop
and target would both trigger on the same bar, stop takes priority
(conservative) - same convention round_number_sr_test.py already uses.

Single pre-specified construction, honest K=1 - no threshold sweep run
(round_number_sr_test.py already showed what an honest K=16 sweep on a
similar level-touch idea looks like; this is deliberately the single-shot
version, matching how every other user-proposed idea was tested today).
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B  # noqa: E402

POINT = B.POINT
SR_DAYS = 3
TOUCH_TOL_ATR = 0.30
REJECT_ATR = 0.30
STOP_ATR = 1.0
RR = 2.0
MAX_BARS = 288


def build_sr_levels(df):
    """Prior SR_DAYS COMPLETED daily highs/lows, broadcast to every M5 bar
    of the following day - same rolling-window/shift-by-1 construction as
    research/meridian/msim.py's sr_arrays()."""
    date = df["time"].dt.date.values
    daily = pd.DataFrame(dict(date=date, h=df["high"].values, l=df["low"].values)).groupby("date").agg(
        h=("h", "max"), l=("l", "min"))
    hi = daily["h"].rolling(SR_DAYS).max().shift(1)
    lo = daily["l"].rolling(SR_DAYS).min().shift(1)
    idx = pd.Index(daily.index)
    pos = idx.get_indexer(date)
    return hi.values[pos], lo.values[pos]


def find_entries(o, h, l, c, atr, sr_hi, sr_lo, n):
    entries = []
    for t in range(1, n - 1):
        s = t
        a = atr[s]
        if not (a > 0) or np.isnan(sr_hi[s]) or np.isnan(sr_lo[s]):
            continue
        tol, rej = TOUCH_TOL_ATR * a, REJECT_ATR * a
        short_sig = (h[s] >= sr_hi[s] - tol) and (c[s] <= sr_hi[s] - rej)
        long_sig = (l[s] <= sr_lo[s] + tol) and (c[s] >= sr_lo[s] + rej)
        if short_sig and long_sig:
            continue   # ambiguous same bar - skip
        if short_sig:
            entries.append(dict(signal_i=s, dir=-1, level=sr_hi[s], atr=a))
        elif long_sig:
            entries.append(dict(signal_i=s, dir=1, level=sr_lo[s], atr=a))
    return entries


def simulate(o, h, l, c, sp_pts, entries_by_bar, start_i, end_i):
    """entries_by_bar: bar -> (dir, level_or_None, atr). If level is given,
    sl/tp are computed from the real S/R level (the normal path). If level
    is None, (dir, risk_dist, reward_dist) is passed instead via the 3rd
    slot overloaded - see the null caller below, which must NOT reuse a
    historical absolute price level on a random bar from a different era
    (gold's price moved thousands of dollars over this dataset - reusing
    an old level's absolute price would produce a nonsensical risk
    distance). The null instead reuses each real trade's own RISK/REWARD
    DISTANCE in price terms, reapplied relative to the random bar's own
    entry price."""
    trades = []
    pos = None
    for t in range(start_i, end_i):
        sp = sp_pts[t] * POINT
        if pos is not None:
            d = pos["dir"]
            hit_sl = (l[t] <= pos["sl"]) if d > 0 else (h[t] + sp >= pos["sl"])
            hit_tp = (h[t] >= pos["tp"]) if d > 0 else (l[t] <= pos["tp"])
            timed_out = (t - pos["entry_i"]) >= MAX_BARS
            if hit_sl:
                px, reason = pos["sl"], "SL"
            elif hit_tp:
                px, reason = pos["tp"], "TP"
            elif timed_out:
                px, reason = c[t], "TIMEOUT"
            else:
                continue
            trades.append(dict(entry_i=pos["entry_i"], dir=d, pnl=(px - pos["entry"]) * d, reason=reason,
                                risk=pos["risk"]))
            pos = None
        if pos is None and t in entries_by_bar and start_i <= t < end_i:
            d, level, a = entries_by_bar[t]
            entry = o[t] + sp if d > 0 else o[t]
            if level is not None:
                sl = level - d * STOP_ATR * a
                risk = abs(entry - sl)
            else:
                risk = a   # here `a` is actually the real trade's own risk DISTANCE (see null builder)
                sl = entry - d * risk
            tp = entry + d * RR * risk
            pos = dict(entry_i=t, dir=d, entry=entry, sl=sl, tp=tp, risk=risk)
    return trades


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
    for r in ("TP", "SL", "TIMEOUT"):
        cnt = sum(1 for t in trades if t["reason"] == r)
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


def random_entries_matched(dirs_levels, start_i, end_i, seed):
    rng = np.random.default_rng(seed)
    eligible = rng.choice(np.arange(start_i + 1, end_i), size=len(dirs_levels), replace=False)
    order = rng.permutation(len(dirs_levels))
    out = {}
    for bar, idx in zip(eligible, order):
        out[int(bar)] = dirs_levels[idx]
    return out


if __name__ == "__main__":
    m5 = B.load_m5()
    o, h, l, c = (m5[k].values for k in ("open", "high", "low", "close"))
    sp_pts = m5["spread"].values
    atr = B.wilder_atr(h, l, c, 14)
    sr_hi, sr_lo = build_sr_levels(m5)
    n = len(m5)
    cutoff = int(n * 0.70)
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({n} bars)")
    print(f"Walk-forward cutoff (70%): {m5['time'].iloc[cutoff]}")
    print(f"Construction: standalone touch+reject of prior-{SR_DAYS}-day D1 S/R "
          f"(tol={TOUCH_TOL_ATR}xATR, reject={REJECT_ATR}xATR), stop={STOP_ATR}xATR beyond level, RR={RR}, "
          f"timeout={MAX_BARS}bars")

    entries = find_entries(o, h, l, c, atr, sr_hi, sr_lo, n)
    print(f"\n  total triggered entries across full history: {len(entries)}")
    entries_by_bar_all = {e["signal_i"] + 1: (e["dir"], e["level"], e["atr"]) for e in entries}

    print(f"\n{'='*92}\nIN-SAMPLE (first 70%) - transparency only\n{'='*92}")
    is_eb = {k: v for k, v in entries_by_bar_all.items() if k < cutoff}
    is_trades = simulate(o, h, l, c, sp_pts, is_eb, 20, cutoff)
    report("standalone S/R rejection", is_trades)

    print(f"\n{'='*92}\nOUT-OF-SAMPLE (last 30%, untouched) - this is the verdict\n{'='*92}")
    oos_eb = {k: v for k, v in entries_by_bar_all.items() if k >= cutoff}
    oos_trades = simulate(o, h, l, c, sp_pts, oos_eb, cutoff, n)
    report("standalone S/R rejection", oos_trades)
    n_oos = len(oos_trades)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws - same stop/target distances as the\n"
          f"real trades (drawn from the real distribution, just assigned to random bars/times)\n{'='*92}")
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few to run a meaningful null")
    else:
        real_pf = pf([t["pnl"] for t in oos_trades])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}")
        # (dir, None, risk_dist) - None tells simulate() to reuse the real
        # trade's own RISK DISTANCE relative to the random bar's own entry
        # price, not an old absolute level from a different price era.
        oos_dls = [(t["dir"], None, t["risk"]) for t in oos_trades]
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            rb = random_entries_matched(oos_dls, cutoff, n, seed)
            ntrades = simulate(o, h, l, c, sp_pts, rb, cutoff, n)
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K for this idea: 1 (single pre-specified construction, no sweep run).")
