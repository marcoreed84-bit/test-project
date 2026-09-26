"""
Opus's web-review item #2: block new entries around high-impact US
releases (NFP, FOMC - CPI dropped, see note below). Tests the REAL trade
lists from Aurelius and Vanguard (both M5, already have working
simulators in this directory) - does removing entries that fired near a
release change the outcome, and are those entries disproportionately bad?

TIMEZONE: this broker's server clock follows EU DST dates while gold's
session follows US DST dates (engine.py's own dst_gap_adjustment() docstring
and the Friday-flatten-at-22-server-hour convention, which lines up with
15:00 ET both winter and summer) - i.e. server_time = ET + 7h, consistently,
except during the ~1-week-per-year EU/US DST mismatch windows where it's
off by 1h. Good enough for a 30-60 minute blackout window; not claimed to
be tick-perfect.

NFP: first Friday of each month, 8:30 ET = 15:30 server time - a reliable
RULE (a handful of real historical exceptions exist, e.g. holiday shifts,
not modeled - disclosed, not hidden).

FOMC: real meeting decision dates (2nd day of each 2-day meeting, 14:00 ET
= 21:00 server time), sourced via web search since federalreserve.gov
itself is blocked by this session's egress proxy - cross-checked across
multiple independent search results, covering 2022-01 through 2026-09
(the real span of the M5 dataset).

CPI: DROPPED from this test. Unlike NFP (fixed weekday rule) or FOMC
(a public, findable meeting calendar), CPI release dates are irregular
(varies year to year, no clean rule) and getting a reliable 2022-2026 list
without a live data feed isn't something this session can responsibly
fabricate - flagged as a real gap rather than guessed at.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from engine import P
from sim import simulate, stats
import vanguard_random_timing_test as V

SERVER_TZ_OFFSET_HOURS = 7   # server_time = ET + 7h (non-DST-gap weeks)

# FOMC decision dates (2nd day of each meeting), real calendar, web-sourced
# 2026-09-26 (see file docstring) - covers the M5 dataset's real span.
FOMC_DECISION_DATES = [
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27",
    "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26",
    "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31",
    "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
    "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29",
    "2026-09-16",
]


def build_blackout_flags(times, window_min=45):
    idx = pd.DatetimeIndex(times)
    et = idx - pd.Timedelta(hours=SERVER_TZ_OFFSET_HOURS)

    is_first_friday = (et.weekday == 4) & (et.day <= 7)
    et_minutes_of_day = et.hour * 60 + et.minute
    nfp_target_min = 8 * 60 + 30  # 8:30 ET
    nfp_flag = is_first_friday & (np.abs(et_minutes_of_day - nfp_target_min) <= window_min)

    fomc_dates = pd.to_datetime(FOMC_DECISION_DATES)
    fomc_target_min = 14 * 60  # 14:00 ET
    fomc_flag = np.zeros(len(idx), dtype=bool)
    et_date = et.normalize()
    for d in fomc_dates:
        m = (et_date == d) & (np.abs(et_minutes_of_day - fomc_target_min) <= window_min)
        fomc_flag |= np.asarray(m)

    return np.asarray(nfp_flag), fomc_flag


def analyze(name, trades, times, entry_bar_key, pnl_pct_fn):
    nfp_flag, fomc_flag = build_blackout_flags(times)
    any_flag = nfp_flag | fomc_flag

    entry_bars = np.array([t[entry_bar_key] if isinstance(t, dict) else t[0] for t in trades])
    in_nfp = nfp_flag[entry_bars]
    in_fomc = fomc_flag[entry_bars]
    in_any = any_flag[entry_bars]

    pnl_pcts = np.array([pnl_pct_fn(t) for t in trades])

    def seg(mask, label):
        if mask.sum() < 3:
            print(f"    {label}: n={mask.sum()} too few")
            return
        arr = pnl_pcts[mask]
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        pf = gw / gl if gl > 0 else float("inf")
        print(f"    {label}: n={mask.sum()}  win%={100*(arr>0).mean():.1f}  "
              f"mean_pnl%={100*arr.mean():.3f}  %PF={pf:.3f}")

    print(f"\n{name}: {len(trades)} real trades, {in_any.sum()} ({100*in_any.mean():.1f}%) "
          f"entered within +/-45min of NFP or FOMC")
    seg(in_nfp, "  entries near NFP")
    seg(in_fomc, "  entries near FOMC")
    seg(in_any, "  entries near NFP or FOMC (combined)")
    seg(~in_any, "  all OTHER entries")

    kept = pnl_pcts[~in_any]
    gw = kept[kept > 0].sum(); gl = -kept[kept <= 0].sum()
    pf_removed = gw / gl if gl > 0 else float("inf")
    all_arr = pnl_pcts
    gw_all = all_arr[all_arr > 0].sum(); gl_all = -all_arr[all_arr <= 0].sum()
    pf_all = gw_all / gl_all if gl_all > 0 else float("inf")
    print(f"  Full book %PF={pf_all:.3f}  ->  with blackout entries REMOVED: %PF={pf_removed:.3f} "
          f"(n {len(trades)} -> {(~in_any).sum()})")


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    times = df["time"].values

    print("=" * 90)
    print("AURELIUS")
    print("=" * 90)
    ctx = E.build_context(df, h4, P)
    aur_trades = simulate(ctx)
    analyze("Aurelius v1.46", aur_trades, times, "entry_i",
            lambda t: (t["exit_px"] - t["entry_px"]) * t["dir"] / t["entry_px"])

    print("\n" + "=" * 90)
    print("VANGUARD")
    print("=" * 90)
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    from trendline_break_test import build_trendline_values, build_breakout_events
    n = ctx["n"]
    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=V.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < V.MIN_SR)
    entry_ok = vwap_ok & sr_ok
    van_trades = V.sim_full(events, entry_ok, close, high, low, spread, atr, n,
                             V.SAFETY_SL_ATR, stale_bars=V.STALE_BARS,
                             stale_min_profit_atr=V.STALE_MIN_PROFIT_ATR)
    analyze("Vanguard v1.06", van_trades, times, 0, lambda t: t[2] / t[4])
