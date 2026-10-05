"""
NEW CANDIDATE (2026-10-05, user's own idea, single construction, own K=1):
a causal, tradable version of news_spike_aftermath_analysis.py's
descriptive finding (spikes continue, with a shallow pullback, more often
than they reverse - 10-16% small-dd-continue vs 30-42% reversal across
horizons, both clearly different from a random bar's own baseline).

That earlier script classified outcomes WITH HINDSIGHT (it already knew
the final move at horizon H). This one is a real, causal entry rule:

  1. SPIKE: a bar where |close-open| >= SPIKE_ATR_MULT=3.0 x ATR(14) (same
     detector, same threshold, not re-tuned).
  2. PULLBACK WINDOW: scan the next LOOKBACK=24 bars (~2h on M5) after the
     spike for the entry trigger.
  3. TRIGGER: the first bar in that window whose retracement against the
     spike's own direction falls in [MIN_PB=0.05, MAX_PB=0.30] x the
     spike's own size S (MAX_PB reused verbatim from the descriptive
     script's own DD_THRESH, not a new free choice), AND whose own close
     is back in the spike's direction (close>open for a long setup,
     close<open for a short) - "pulled back a little, now turning".
  4. INVALIDATION: if the retracement ever exceeds MAX_PB before the
     trigger condition fires, the setup is abandoned - no trade for that
     spike (the "small drawdown" premise was broken).
  5. ENTRY: at the open of the bar AFTER the trigger bar.
  6. EXIT: a TARGET of 1.0x the spike's own size S further in the
     continuation direction (ties directly to "continue in that
     direction" - not an arbitrary level), a 2.0xATR stop (this project's
     plain round default all day), or a 288-bar (~1 day) timeout - same
     longest horizon already explored in the descriptive script.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B  # noqa: E402

POINT = B.POINT
SPIKE_ATR_MULT = 3.0
LOOKBACK = 24
MIN_PB = 0.05
MAX_PB = 0.30
TARGET_MULT = 1.0
ATR_STOP = 2.0
MAX_BARS = 288


def find_entries(o, h, l, c, atr, n):
    """Returns list of (entry_bar, dir, stop, target)."""
    body = np.abs(c - o)
    with np.errstate(invalid="ignore"):
        spike_mult = body / atr
    spikes = np.where((spike_mult >= SPIKE_ATR_MULT) & ~np.isnan(spike_mult))[0]
    entries = []
    for i in spikes:
        if i + LOOKBACK + 1 >= n:
            continue
        d = 1.0 if (c[i] - o[i]) >= 0 else -1.0
        s = abs(c[i] - o[i])
        c0 = c[i]
        triggered = False
        for j in range(i + 1, i + 1 + LOOKBACK):
            adverse_px = l[j] if d > 0 else h[j]
            retrace = (c0 - adverse_px) / s if d > 0 else (adverse_px - c0) / s
            if retrace > MAX_PB:
                break   # invalidated - drawdown exceeded the "small" cap
            bar_confirms = (c[j] > o[j]) if d > 0 else (c[j] < o[j])
            if MIN_PB <= retrace <= MAX_PB and bar_confirms:
                entry_i = j + 1
                a = atr[j]
                if a <= 0 or entry_i >= n:
                    break
                entry_px = None  # filled at open[entry_i], computed in simulate() with real spread
                stop = None
                target = c0 + d * TARGET_MULT * s
                entries.append(dict(entry_i=entry_i, dir=d, atr_at_signal=a, target=target))
                triggered = True
                break
    return entries


def simulate(o, h, l, c, sp_pts, entries_by_bar, start_i, end_i):
    trades = []
    pos = None
    for t in range(start_i, end_i):
        sp = sp_pts[t] * POINT
        if pos is not None:
            d = pos["dir"]
            hit_sl = (l[t] <= pos["sl"]) if d > 0 else (h[t] + sp >= pos["sl"])
            hit_tp = (h[t] >= pos["target"]) if d > 0 else (l[t] <= pos["target"])
            timed_out = (t - pos["entry_i"]) >= MAX_BARS
            if hit_sl and hit_tp:
                px, reason = (pos["sl"], "SL") if abs(o[t] - pos["sl"]) <= abs(pos["target"] - o[t]) else (pos["target"], "TP")
            elif hit_sl:
                px, reason = pos["sl"], "SL"
            elif hit_tp:
                px, reason = pos["target"], "TP"
            elif timed_out:
                px, reason = c[t], "TIMEOUT"
            else:
                continue
            trades.append(dict(entry_i=pos["entry_i"], dir=d, pnl=(px - pos["entry"]) * d, reason=reason))
            pos = None
        if pos is None and t in entries_by_bar and start_i <= t < end_i:
            d, atr_v, target = entries_by_bar[t]
            entry = o[t] + sp if d > 0 else o[t]
            sl = entry - d * ATR_STOP * atr_v
            pos = dict(entry_i=t, dir=d, entry=entry, sl=sl, target=target)
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


def random_entries_matched(dirs_sizes, start_i, end_i, seed):
    """Matched count AND matched direction mix, random bar, SAME exit
    machinery (target = entry's own ATR-at-the-time * nothing - instead
    reuse the REAL trades' own (dir, atr_at_signal, target-distance) tuples
    assigned to random bars, so stop/target distances are drawn from the
    same real distribution, not invented)."""
    rng = np.random.default_rng(seed)
    eligible = rng.choice(np.arange(start_i + 1, end_i), size=len(dirs_sizes), replace=False)
    order = rng.permutation(len(dirs_sizes))
    out = {}
    for bar, idx in zip(eligible, order):
        d, atr_v, target_dist = dirs_sizes[idx]
        out[int(bar)] = (d, atr_v, target_dist)
    return out


if __name__ == "__main__":
    m5 = B.load_m5()
    o, h, l, c = (m5[k].values for k in ("open", "high", "low", "close"))
    sp_pts = m5["spread"].values
    atr = B.wilder_atr(h, l, c, 14)
    n = len(m5)
    cutoff = int(n * 0.70)
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({n} bars)")
    print(f"Walk-forward cutoff (70%): {m5['time'].iloc[cutoff]}")
    print(f"Construction: spike(3xATR) -> pullback [{MIN_PB},{MAX_PB}]xsize + confirming close -> "
          f"entry, target={TARGET_MULT}xspike-size, stop={ATR_STOP}xATR, timeout={MAX_BARS}bars")

    entries = find_entries(o, h, l, c, atr, n)
    print(f"\n  total triggered entries across full history: {len(entries)}")

    print(f"\n{'='*92}\nIN-SAMPLE (first 70%) - transparency only\n{'='*92}")
    is_eb = {ee["entry_i"]: (ee["dir"], ee["atr_at_signal"], ee["target"]) for ee in entries
             if ee["entry_i"] < cutoff}
    is_trades = simulate(o, h, l, c, sp_pts, is_eb, 20, cutoff)
    report("spike-pullback-continuation", is_trades)

    print(f"\n{'='*92}\nOUT-OF-SAMPLE (last 30%, untouched) - this is the verdict\n{'='*92}")
    oos_eb = {ee["entry_i"]: (ee["dir"], ee["atr_at_signal"], ee["target"]) for ee in entries
              if ee["entry_i"] >= cutoff}
    oos_trades = simulate(o, h, l, c, sp_pts, oos_eb, cutoff, n)
    report("spike-pullback-continuation", oos_trades)
    n_oos = len(oos_trades)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws - same stop/target distances as the\n"
          f"real trades (drawn from the real distribution, just assigned to random bars/times)\n{'='*92}")
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few to run a meaningful null")
    else:
        real_pf = pf([t["pnl"] for t in oos_trades])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}")
        oos_dirs_sizes = [(ee["dir"], ee["atr_at_signal"], ee["target"] - c[ee["entry_i"] - 1])
                          for ee in entries if ee["entry_i"] >= cutoff]
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            rb = random_entries_matched(oos_dirs_sizes, cutoff, n, seed)
            rb_eb = {bar: (d, a, c[bar - 1] + td) for bar, (d, a, td) in rb.items()}
            ntrades = simulate(o, h, l, c, sp_pts, rb_eb, cutoff, n)
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K for this idea: 1 (single pre-specified construction, no sweep run).")
