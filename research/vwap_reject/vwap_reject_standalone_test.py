"""
NEW CANDIDATE (2026-10-06, user's own idea from a Meridian chart example):
a STANDALONE entry trading the rejection of session VWAP directly, instead
of the 21/50 EMA cross Meridian actually uses. The user's diagnosis of a
specific real example: the 21/50 cross fired on an already-finished leg (a
lower high forming, oscillator rolling over from overbought) - by the time
the EMAs confirmed, the move was basically over. Their proposal: trade the
rejection of VWAP itself as the primary signal, not a lagging MA cross.

This reuses the exact two-bar touch-then-confirm rejection pattern already
established and tested today for S/R levels (research/aurelius/
sr_reject_confirm_standalone_test.py) - same discipline, same reasoning
(a same-bar touch alone isn't a rejection; the FOLLOWING bar must actually
confirm the move away, or there was no real rejection) - applied to VWAP
as the level instead of a prior-day S/R high/low. VWAP definition
identical to every other VWAP use in this project (cumulative typical
price x tick volume / cumulative tick volume, reset each calendar day).

ENTRY:
  TOUCH bar s - BEARISH setup (VWAP tested as resistance from below):
    high[s] >= vwap[s] - TOUCH_TOL_ATR x ATR, AND close[s] <= vwap[s]
    (came up to it, did not close through).
  TOUCH bar s - BULLISH setup (VWAP tested as support from above):
    low[s] <= vwap[s] + TOUCH_TOL_ATR x ATR, AND close[s] >= vwap[s].
  CONFIRM bar s+1 (the very next bar - NOT a same-bar condition, same
  lesson already learned today building the Meridian retest test): must
  close further away from VWAP in the rejection direction by at least
  REJECT_ATR x ATR. If it instead closes back through VWAP, the rejection
  FAILED and the setup is simply skipped - no trade, no retry.
  Entry fills at bar (s+2)'s open, real spread charged.

STOP: structural, VWAP[s] +/- STOP_BUFFER_ATR x ATR (VWAP is the level
this trades off of, same "stop belongs at the structure" principle
already applied to the 21/50 EMA stop earlier today).
TARGET: RR x risk, this project's typical un-tuned 2.0 reward:risk.
MAX_BARS=288 (~1 day) final time-stop backstop if neither fires.

Honest K=1 (single pre-specified construction, no threshold sweep).
Walk-forward 70/30 split, OOS random-timing null (2000 draws, matched
trade count/direction/ATR, real spread, same exit machinery).
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B  # noqa: E402

POINT = B.POINT
TOUCH_TOL_ATR = 0.20
REJECT_ATR = 0.20
STOP_BUFFER_ATR = 0.30
RR = 2.0
MAX_BARS = 288


def build_vwap(df):
    date = df["time"].dt.date.values
    typ = (df["high"].values + df["low"].values + df["close"].values) / 3.0
    v = df["tick_volume"].values.astype(float)
    return (pd.Series(typ * v).groupby(date).cumsum() / pd.Series(v).groupby(date).cumsum()).values


def find_entries(o, h, l, c, atr, vwap, n):
    entries = []
    for s in range(1, n - 2):
        a = atr[s]
        if not (a > 0):
            continue
        tol = TOUCH_TOL_ATR * a
        touch_bear = (h[s] >= vwap[s] - tol) and (c[s] <= vwap[s])
        touch_bull = (l[s] <= vwap[s] + tol) and (c[s] >= vwap[s])
        if touch_bear and touch_bull:
            continue   # ambiguous same bar - skip
        if not (touch_bear or touch_bull):
            continue
        d = -1 if touch_bear else 1
        f = s + 1
        af = atr[f]
        if not (af > 0):
            continue
        rej = REJECT_ATR * af
        confirmed = (c[f] <= vwap[f] - rej) if d < 0 else (c[f] >= vwap[f] + rej)
        if not confirmed:
            continue   # failed rejection - price closed back through VWAP instead - no trade
        entries.append(dict(signal_i=f, dir=d, level=vwap[s], atr=af))
    return entries


def simulate(o, h, l, c, sp_pts, entries_by_bar, start_i, end_i):
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
                sl = level - d * STOP_BUFFER_ATR * a
                risk = abs(entry - sl)
                if (d > 0 and sl >= entry) or (d < 0 and sl <= entry):
                    continue  # degenerate - price already past its own stop at fill
            else:
                risk = a   # null draw: `a` here is the real trade's own risk DISTANCE - see __main__
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
        if cnt:
            print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


def random_entries_matched(dir_risk_list, start_i, end_i, seed):
    rng = np.random.default_rng(seed)
    eligible = rng.choice(np.arange(start_i + 1, end_i), size=len(dir_risk_list), replace=False)
    order = rng.permutation(len(dir_risk_list))
    out = {}
    for bar, idx in zip(eligible, order):
        out[int(bar)] = dir_risk_list[idx]
    return out


if __name__ == "__main__":
    m5 = B.load_m5()
    o, h, l, c = (m5[k].values for k in ("open", "high", "low", "close"))
    sp_pts = m5["spread"].values
    atr = B.wilder_atr(h, l, c, 14)
    vwap = build_vwap(m5)
    n = len(m5)
    cutoff = int(n * 0.70)
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({n} bars)")
    print(f"Walk-forward cutoff (70%): {m5['time'].iloc[cutoff]}")
    print(f"Construction: touch({TOUCH_TOL_ATR}xATR)-then-confirm({REJECT_ATR}xATR) rejection of session VWAP, "
          f"stop={STOP_BUFFER_ATR}xATR beyond VWAP, RR={RR}, timeout={MAX_BARS}bars")

    entries = find_entries(o, h, l, c, atr, vwap, n)
    print(f"\n  total triggered entries across full history: {len(entries)}")
    entries_by_bar_all = {e["signal_i"] + 1: (e["dir"], e["level"], e["atr"]) for e in entries}

    print(f"\n{'='*92}\nIN-SAMPLE (first 70%) - transparency only\n{'='*92}")
    is_eb = {k: v for k, v in entries_by_bar_all.items() if k < cutoff}
    is_trades = simulate(o, h, l, c, sp_pts, is_eb, 20, cutoff)
    report("VWAP rejection", is_trades)

    print(f"\n{'='*92}\nOUT-OF-SAMPLE (last 30%, untouched) - this is the verdict\n{'='*92}")
    oos_eb = {k: v for k, v in entries_by_bar_all.items() if k >= cutoff}
    oos_trades = simulate(o, h, l, c, sp_pts, oos_eb, cutoff, n)
    report("VWAP rejection", oos_trades)
    n_oos = len(oos_trades)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws - same stop/target distances as the\n"
          f"real trades (drawn from the real distribution, just assigned to random bars/times)\n{'='*92}")
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few to run a meaningful null")
    else:
        real_pf = pf([t["pnl"] for t in oos_trades])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}")
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
