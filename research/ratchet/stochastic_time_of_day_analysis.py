"""
Descriptive (not a trading-signal test): does the Stochastic oscillator's
time spent in overbought/oversold, and the timing of a normal full swing
from oversold to overbought (and back), cluster at particular hours of the
broker-server day, or is it close to uniform across the 24h session?

Uses the same Stochastic construction Ratchet_EA.mq5 itself already uses
(bars.mt5_stoch_signal, K=5/slowing=3/D=3, STO_LOWHIGH/MODE_SMA - see that
function's own header) on real GOLD M5 data (2022-07-04..2026-09-25, the
same already-validated window every other Ratchet/Meridian script in this
project trusts - NOT the newer, unverified GOLD_M5_full_2014_2026.csv,
whose early years have not been checked for the same hourly-bars-mislabeled-
as-M5 problem CLAUDE.md documents for the M15 file), then resampled up to
M15/H1/H4 (OHLC resampled first, Stochastic recomputed fresh on each
timeframe's own bars - not just downsampled from the M5 oscillator values).

Two separate questions, two separate tests:
  1. DWELL: of all bars where the oscillator sits in OB (>=80) or OS (<=20),
     is the hour-of-day distribution uniform? Chi-square goodness-of-fit
     against a uniform null.
  2. SWING: for each completed OS->OB (and OB->OS) full swing, what hour did
     it START and what hour did it COMPLETE, and does swing duration itself
     vary by start hour? Same chi-square test on the start/complete hours.

Both standard 80/20 levels AND Ratchet's own exact InpKLevel=95/5 exit
threshold are reported, since 95/5 is what actually matters for this
project's own system.
"""
import sys

import numpy as np
import pandas as pd
from scipy import stats as sstats

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B  # noqa: E402


def resample_ohlc(df, rule):
    g = df.set_index("time").resample(rule, label="left", closed="left")
    out = pd.DataFrame(dict(open=g["open"].first(), high=g["high"].max(),
                             low=g["low"].min(), close=g["close"].last()))
    out = out.dropna().reset_index()
    return out


def chi2_uniform(hour_values, all_hours):
    """Chi-square goodness-of-fit: are these hour-of-day occurrences spread
    uniformly across all_hours, or do some hours get more than their share?"""
    counts = pd.Series(hour_values).value_counts().reindex(all_hours, fill_value=0)
    expected = counts.sum() / len(all_hours)
    if expected == 0:
        return counts, float("nan"), float("nan")
    chi2, p = sstats.chisquare(counts.values, f_exp=[expected] * len(all_hours))
    return counts, chi2, p


def analyze(label, df, k=5, slowing=3, d=3):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    main, _ = B.mt5_stoch_signal(h, l, c, k, slowing, d)
    hour = df["time"].dt.hour.values
    valid = ~np.isnan(main)
    main, hour, t = main[valid], hour[valid], df["time"].values[valid]
    all_hours = sorted(set(hour.tolist()))

    print(f"\n{'='*92}\n{label}  (n={len(main)} bars, hours present: {len(all_hours)})\n{'='*92}")

    for lo, hi, name in ((20, 80, "standard 20/80"), (5, 95, "Ratchet's own InpKLevel 5/95")):
        ob = main >= hi
        os_ = main <= lo
        print(f"\n  -- {name} levels --")
        print(f"  overall: {100*ob.mean():.1f}% of bars OB (>={hi}), {100*os_.mean():.1f}% OS (<={lo})")
        for cond_name, cond in (("OB", ob), ("OS", os_)):
            counts, chi2, p = chi2_uniform(hour[cond], all_hours)
            rate_by_hour = counts / pd.Series(hour).value_counts().reindex(all_hours, fill_value=1)
            top = rate_by_hour.sort_values(ascending=False).head(4)
            bot = rate_by_hour.sort_values(ascending=True).head(4)
            verdict = "NOT uniform (real time-of-day pattern)" if p < 0.05 else "uniform (no real pattern, looks random)"
            print(f"    {cond_name} dwell by hour: chi2={chi2:.1f}, p={p:.4f}  -> {verdict}")
            print(f"      highest-rate hours: " + ", ".join(f"{hh:02d}:00={100*r:.1f}%" for hh, r in top.items()))
            print(f"      lowest-rate hours:  " + ", ".join(f"{hh:02d}:00={100*r:.1f}%" for hh, r in bot.items()))

    # ---- swing analysis: standard 20/80 only (95/5 gives too few completed
    # swings to resolve a hime-of-day pattern on some timeframes) ----
    print(f"\n  -- full OS->OB and OB->OS swings (standard 20/80) --")
    for up in (True, False):
        entry_level, exit_level = (20, 80) if up else (80, 20)
        in_zone = (main <= entry_level) if up else (main >= entry_level)
        starts, completes, durations = [], [], []
        i = 0
        n = len(main)
        while i < n:
            if in_zone[i]:
                start_i = i
                j = i + 1
                reached = False
                while j < n:
                    if (main[j] >= exit_level) if up else (main[j] <= exit_level):
                        reached = True
                        break
                    j += 1
                if reached:
                    starts.append(hour[start_i])
                    completes.append(hour[j])
                    durations.append(j - start_i)
                    i = j + 1
                    continue
                else:
                    break
            i += 1
        kind = "OS->OB (up)" if up else "OB->OS (down)"
        if len(starts) < 10:
            print(f"    {kind}: only {len(starts)} completed swings - too few to test")
            continue
        _, chi2_s, p_s = chi2_uniform(starts, all_hours)
        _, chi2_c, p_c = chi2_uniform(completes, all_hours)
        durations = np.array(durations)
        verdict_s = "NOT uniform" if p_s < 0.05 else "uniform"
        verdict_c = "NOT uniform" if p_c < 0.05 else "uniform"
        print(f"    {kind}: n={len(starts)} swings, median duration={np.median(durations):.1f} bars "
              f"(mean {durations.mean():.1f})")
        print(f"      start-hour distribution:    chi2={chi2_s:.1f} p={p_s:.4f} -> {verdict_s}")
        print(f"      complete-hour distribution: chi2={chi2_c:.1f} p={p_c:.4f} -> {verdict_c}")
        dur_by_start_hour = pd.Series(durations).groupby(pd.Series(starts)).mean().sort_values()
        print(f"      fastest-to-complete start hours: " +
              ", ".join(f"{hh:02d}:00={v:.1f}bars" for hh, v in dur_by_start_hour.head(3).items()))
        print(f"      slowest-to-complete start hours: " +
              ", ".join(f"{hh:02d}:00={v:.1f}bars" for hh, v in dur_by_start_hour.tail(3).items()))


if __name__ == "__main__":
    m5 = B.load_m5()
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({len(m5)} bars)")
    print("Server-time hours below (same clock the real MT5 reports use).")

    analyze("M5 (native, Ratchet's own timeframe)", m5)
    analyze("M15 (resampled from M5)", resample_ohlc(m5, "15min"))
    analyze("H1 (resampled from M5)", resample_ohlc(m5, "1h"))
    analyze("H4 (resampled from M5)", resample_ohlc(m5, "4h"))
