"""
Descriptive (not a trading-signal test, like stochastic_time_of_day_
analysis.py): after an abnormally large one-bar move ("spike candle"),
how often does price reverse (go the OPPOSITE way from the spike), and
how often does it pull back a LITTLE and then continue in the spike's
OWN direction?

SPIKE DEFINITION: a bar whose body |close-open| >= SPIKE_ATR_MULT x
ATR(14) at that bar - this catches any real large directional move,
scheduled (NFP/FOMC/CPI) or not, rather than relying only on a fixed
calendar (research/aurelius/news_blackout_test.py already has a real
NFP/FOMC calendar for GOLD's broker-server time - reused here ONLY as a
cross-check on how many detected spikes land near a known release, not
as the primary detector, since an unscheduled headline/flash-move spike
would be invisible to a calendar-only approach).

OUTCOME CLASSIFICATION, measured at each horizon H bars after the spike
bar's close (c0), in units of the spike's OWN size (spike_size =
|c0-open0|, spike_dir = sign(c0-open0)):
  - max_fav  = best price move IN the spike's direction within H bars
  - max_adv  = worst price move AGAINST the spike's direction within H bars
  - final    = net move at bar H, in spike-direction terms (positive =
               ended up further in the spike's own direction)
  REVERSAL:          final <= -REV_THRESH * spike_size (ended up
                      meaningfully on the OPPOSITE side of where the spike
                      pointed)
  SMALL_DD_CONTINUE: max_adv <= DD_THRESH * spike_size AND
                      final >= CONT_THRESH * spike_size (pulled back only
                      a little against the spike, then continued)
  OTHER:             anything else (big drawdown then continuation, or
                      indecisive/flat)

BASELINE: the identical classification run on the SAME number of ORDINARY
(non-spike) bars, chosen uniformly at random, with "spike_dir"/"spike_size"
for each baseline bar taken from ITS OWN body move (so the baseline asks
"does a random bar's own small intrabar direction/size predict anything
about what follows," the fair comparison) - this tells us whether spike
bars are actually special, not just "stuff happens after any bar too."
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import bars as B  # noqa: E402
from news_blackout_test import FOMC_DECISION_DATES, SERVER_TZ_OFFSET_HOURS  # noqa: E402

SPIKE_ATR_MULT = 3.0
REV_THRESH = 0.5
DD_THRESH = 0.3
CONT_THRESH = 0.5
HORIZONS = {"1h": 12, "4h": 48, "8h": 96, "1day": 288}


def classify(c0, open0, h, l, c, horizon):
    spike_dir = 1.0 if (c0 - open0) >= 0 else -1.0
    spike_size = abs(c0 - open0)
    if spike_size <= 0:
        return None
    window_h = h[1:horizon + 1]
    window_l = l[1:horizon + 1]
    if len(window_h) == 0:
        return None
    max_fav = (window_h.max() - c0) if spike_dir > 0 else (c0 - window_l.min())
    max_adv = (c0 - window_l.min()) if spike_dir > 0 else (window_h.max() - c0)
    final_px = c[horizon] if horizon < len(c) else c[-1]
    final = (final_px - c0) * spike_dir
    max_fav /= spike_size
    max_adv /= spike_size
    final /= spike_size
    if final <= -REV_THRESH:
        return "REVERSAL"
    if max_adv <= DD_THRESH and final >= CONT_THRESH:
        return "SMALL_DD_CONTINUE"
    return "OTHER"


def run_classification(idx_list, o, h, l, c, atr, horizon_bars, n):
    counts = dict(REVERSAL=0, SMALL_DD_CONTINUE=0, OTHER=0, skipped=0)
    for i in idx_list:
        if i + horizon_bars >= n or i < 1:
            counts["skipped"] += 1
            continue
        outcome = classify(c[i], o[i], h[i:i + horizon_bars + 1], l[i:i + horizon_bars + 1],
                            c[i:i + horizon_bars + 1], horizon_bars)
        if outcome is None:
            counts["skipped"] += 1
        else:
            counts[outcome] += 1
    return counts


def pct(counts):
    total = counts["REVERSAL"] + counts["SMALL_DD_CONTINUE"] + counts["OTHER"]
    if total == 0:
        return counts, 0
    return {k: (100 * v / total if k != "skipped" else v) for k, v in counts.items()}, total


if __name__ == "__main__":
    m5 = B.load_m5()
    o, h, l, c = (m5[k].values for k in ("open", "high", "low", "close"))
    atr = B.wilder_atr(h, l, c, 14)
    n = len(m5)
    body = np.abs(c - o)
    with np.errstate(invalid="ignore"):
        spike_mult = body / atr
    spike_idx = np.where((spike_mult >= SPIKE_ATR_MULT) & ~np.isnan(spike_mult))[0]
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({n} bars)")
    print(f"Spike definition: |close-open| >= {SPIKE_ATR_MULT}x ATR(14)")
    print(f"Spikes found: {len(spike_idx)} ({100*len(spike_idx)/n:.3f}% of bars)")

    # cross-check against the real NFP/FOMC calendar (research/aurelius/news_blackout_test.py)
    times = m5["time"].values
    spike_times = pd.DatetimeIndex(times[spike_idx])
    nfp_mask = (spike_times.weekday == 4) & (spike_times.day <= 7) & \
               (spike_times.hour == 15) & (spike_times.minute.isin([30, 35, 40, 45]))
    fomc_dates = pd.DatetimeIndex(FOMC_DECISION_DATES) + pd.Timedelta(hours=21)
    near_fomc = np.array([any(abs((st - fd).total_seconds()) <= 3600 for fd in fomc_dates)
                           for st in spike_times])
    print(f"  of those, near a known NFP release window: {nfp_mask.sum()} "
          f"({100*nfp_mask.sum()/max(1,len(spike_idx)):.1f}%)")
    print(f"  of those, within 1h of a known FOMC decision: {near_fomc.sum()} "
          f"({100*near_fomc.sum()/max(1,len(spike_idx)):.1f}%)")
    print(f"  (most real spikes are NOT NFP/FOMC - unscheduled headlines, data releases this "
          f"calendar doesn't cover, or ordinary volatility bursts - exactly why price itself, "
          f"not a fixed calendar, is the primary detector here)")

    rng = np.random.default_rng(0)
    baseline_idx = rng.choice(np.arange(1, n - max(HORIZONS.values()) - 1),
                               size=len(spike_idx), replace=False)

    print(f"\n{'='*100}")
    print(f"{'horizon':8s} | {'SPIKE: reversal':>16s} {'small-dd+cont':>16s} {'other':>10s} | "
          f"{'RANDOM: reversal':>17s} {'small-dd+cont':>16s} {'other':>10s} | n(spike)")
    print(f"{'='*100}")
    for label, hb in HORIZONS.items():
        spike_counts = run_classification(spike_idx, o, h, l, c, atr, hb, n)
        spike_pct, n_spike = pct(spike_counts)
        base_counts = run_classification(baseline_idx, o, h, l, c, atr, hb, n)
        base_pct, n_base = pct(base_counts)
        print(f"{label:8s} | {spike_pct['REVERSAL']:15.1f}% {spike_pct['SMALL_DD_CONTINUE']:15.1f}% "
              f"{spike_pct['OTHER']:9.1f}% | {base_pct['REVERSAL']:16.1f}% "
              f"{base_pct['SMALL_DD_CONTINUE']:15.1f}% {base_pct['OTHER']:9.1f}% | n={n_spike}")

    print(f"\nREVERSAL = price ended up net >= {REV_THRESH}x the spike's own size on the OPPOSITE "
          f"side from where it pointed.")
    print(f"SMALL_DD_CONTINUE = price never pulled back more than {DD_THRESH}x the spike's size "
          f"against it, AND ended up net >= {CONT_THRESH}x further in the spike's OWN direction.")
    print(f"OTHER = neither (e.g. a bigger drawdown before continuing, or an indecisive/flat outcome).")
    print(f"\nSPIKE vs RANDOM comparison answers whether spike bars behave differently from an "
          f"ordinary bar's own small intrabar move - not yet a trading signal, no P&L/cost modeled.")
