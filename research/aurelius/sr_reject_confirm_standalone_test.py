"""
NEW CANDIDATE (2026-10-05, user's own further clarification on the S/R-
rejection idea): a THIRD, distinct construction - not the same-bar
touch+close-back-away version in sr_reject_standalone_test.py (REJECTED,
p=0.9665, worse than random timing), and NOT a wick-ratio pin-bar version
either. The user explicitly corrected both:
  - "they are not specifically candles with a long rejection wick" - so no
    InpWickRejectRatio-style same-bar wick/body shape requirement.
  - "again one would have to look at the next candle after the one that
    rejected the line" - the touch and the confirmation are TWO SEPARATE
    bars, not one bar doing both jobs.

So this version is a genuine two-bar sequence:
  BAR T (touch bar): price simply comes within TOUCH_TOL_ATR*ATR of the
    level. No requirement on how bar T closes - it may close anywhere.
  BAR T+1 (confirmation bar): closes back away from the same level by at
    least REJECT_ATR*ATR(T+1). This is the bar that actually confirms the
    level held, one bar after the touch - exactly the "look at the next
    candle after the one that rejected the line" sequence the user
    described.
  Entry fills at the open of bar T+2 (one more bar after the confirmation
  closes), real spread charged - same "signal bar, then act on the next
  bar's open" convention used throughout this repo (e.g. Ratchet/Aurelius
  entries never fill on their own signal bar's close).

S/R LEVEL: identical prior InpSRDays=3 COMPLETED daily highs/lows as
sr_reject_standalone_test.py and Aurelius_EA.mq5's own SRDistanceATR() -
same level definition, not re-litigated here.

EXIT: identical to sr_reject_standalone_test.py - stop = level +/-
STOP_ATR*ATR beyond the level (1.0xATR, un-tuned), target = RR=2.0 x risk,
MAX_BARS=288 (~1 day) time-stop. Stop takes priority if both would trigger
on the same bar.

Single pre-specified construction, honest K=1 - this is its own distinct
hypothesis from the already-tested same-bar version, so it gets its own
K=1, not folded into the earlier test's K.
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
    """Two-bar sequence: bar t touches the level, bar t+1 confirms by
    closing away from it. Entry fills at bar (t+1)+1's open, i.e. signal_i
    is set to t+1 (the confirmation bar) so the caller's usual
    signal_i+1-fills-next-bar-open convention lines up unchanged."""
    entries = []
    for t in range(1, n - 2):
        s = t      # touch bar
        f = t + 1  # confirmation bar
        a_s, a_f = atr[s], atr[f]
        if not (a_s > 0) or not (a_f > 0) or np.isnan(sr_hi[s]) or np.isnan(sr_lo[s]):
            continue
        tol = TOUCH_TOL_ATR * a_s
        touch_hi = h[s] >= sr_hi[s] - tol
        touch_lo = l[s] <= sr_lo[s] + tol
        if touch_hi and touch_lo:
            continue  # ambiguous touch bar - skip
        rej = REJECT_ATR * a_f
        if touch_hi:
            confirm_short = c[f] <= sr_hi[s] - rej
            confirm_long = c[f] >= sr_hi[s] + rej  # price broke back above its own touch - not a rejection
            if confirm_short and not confirm_long:
                entries.append(dict(signal_i=f, dir=-1, level=sr_hi[s], atr=a_f))
        elif touch_lo:
            confirm_long = c[f] >= sr_lo[s] + rej
            confirm_short = c[f] <= sr_lo[s] - rej
            if confirm_long and not confirm_short:
                entries.append(dict(signal_i=f, dir=1, level=sr_lo[s], atr=a_f))
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
    print(f"Construction: two-bar touch(tol={TOUCH_TOL_ATR}xATR)-then-confirm(reject={REJECT_ATR}xATR) "
          f"of prior-{SR_DAYS}-day D1 S/R, stop={STOP_ATR}xATR beyond level, RR={RR}, timeout={MAX_BARS}bars")

    entries = find_entries(o, h, l, c, atr, sr_hi, sr_lo, n)
    print(f"\n  total triggered entries across full history: {len(entries)}")
    entries_by_bar_all = {e["signal_i"] + 1: (e["dir"], e["level"], e["atr"]) for e in entries}

    print(f"\n{'='*92}\nIN-SAMPLE (first 70%) - transparency only\n{'='*92}")
    is_eb = {k: v for k, v in entries_by_bar_all.items() if k < cutoff}
    is_trades = simulate(o, h, l, c, sp_pts, is_eb, 20, cutoff)
    report("two-bar S/R touch+confirm", is_trades)

    print(f"\n{'='*92}\nOUT-OF-SAMPLE (last 30%, untouched) - this is the verdict\n{'='*92}")
    oos_eb = {k: v for k, v in entries_by_bar_all.items() if k >= cutoff}
    oos_trades = simulate(o, h, l, c, sp_pts, oos_eb, cutoff, n)
    report("two-bar S/R touch+confirm", oos_trades)
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
