"""
Intraday time-series momentum on BTC: "the first half-hour return predicts
the last half-hour return" - Shen, Urquhart & Wang, "Bitcoin intraday
time-series momentum," Financial Review 57(2), 2022. Peer-reviewed,
published finding, genuinely different mechanism from everything else
tried on BTC in this project (53 prior constructions, all price-pattern/
indicator-based) - this is a session-timing/autocorrelation effect.

IMPORTANT CAVEAT, disclosed up front: the published paper defines Bitcoin's
"trading day" using TRADING VOLUME as a proxy (BTC has no calendar open/
close), not plain UTC clock time - the exact binning algorithm could not be
retrieved. Every academic-paper host that might carry the full text
(Reading University repository, ResearchGate, University of Birmingham,
DIVA) returned a hard network-policy block (403) in this environment, not
a retriable failure. This script therefore tests the PLAIN-UTC-CALENDAR-DAY
version of the same hypothesis (first 30 min of the UTC day predicts the
last 30 min) - a reasonable, disclosed adaptation of the published idea,
NOT a replication of the paper's exact result. Treat accordingly.

CONSTRUCTION (K=1 - no free parameters, nothing searched/tuned, straight
from the published rule - the strongest kind of test, no overfitting risk):
  FIRST_RET = close[bar at 00:15 UTC] - open[bar at 00:00 UTC]  (first 30
              min of the UTC day, M15 bars)
  Signal fires at the close of the bar at 23:15 UTC (last bar before the
  "last half hour"): direction = sign(FIRST_RET) (zero return = no trade)
  ENTRY: next bar's open (23:30 UTC) + real spread.
  EXIT: next bar's close (00:00 UTC next day, i.e. exactly 30 min later) -
        implemented as max_hold=1 bar, no stop/target/trail (a deliberately
        oversized nominal stop keeps sim_signals' dist>0 requirement
        satisfied without ever actually binding within one bar).
One trade per UTC day, 24/7 (BTC has no session gap to worry about, unlike
Gold/Silver - this script is BTC-only for that reason, not because of a
missing-data gap in the other two).

Splits/cost/null: common.py (BTC IS 2021-01-01 -> 2024-01-01, OOS
2024-01-01 -> end). Reported on both IS and OOS for transparency, since
there is nothing to freeze (K=1, no search) - the IS/OOS split here is
just the project's standard comparability convention, not a walk-forward
tuning step.
"""
import sys
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

NOMINAL_STOP_ATR = 50.0   # oversized on purpose - never binds within max_hold=1, keeps sim_signals' dist>0 requirement happy


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    o, c, atr = b.open, b.close, b.atr
    hour, minute = b.hour, b.minute

    idx_0000 = np.where((hour == 0) & (minute == 0))[0]
    idx_0015 = np.where((hour == 0) & (minute == 15))[0]
    idx_2315 = np.where((hour == 23) & (minute == 15))[0]

    # match each day's 00:00/00:15 pair with that SAME day's 23:15 signal bar
    # by DATE KEY, not array position - a single missing bar anywhere in the
    # history (exchange downtime, data vendor gap) would silently misalign a
    # positional zip() for every day after it (this was a real bug: first
    # version found only 65 signals across 9 years instead of ~3400 days).
    date_of = b.date_id
    open_0000_by_date = {date_of[i]: o[i] for i in idx_0000}
    close_0015_by_date = {date_of[i]: c[i] for i in idx_0015}
    first_ret_by_date = {}
    for d, op in open_0000_by_date.items():
        if d in close_0015_by_date:
            first_ret_by_date[d] = close_0015_by_date[d] - op

    sig_bar, sig_dir = [], []
    for i in idx_2315:
        d = date_of[i]
        if d not in first_ret_by_date:
            continue
        fr = first_ret_by_date[d]
        if fr == 0 or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        sig_bar.append(i)
        sig_dir.append(1.0 if fr > 0 else -1.0)

    sig_bar = np.array(sig_bar, dtype=np.int64)
    sig_dir = np.array(sig_dir, dtype=np.float64)
    o_ = np.argsort(sig_bar, kind="stable")
    sig_bar, sig_dir = sig_bar[o_], sig_dir[o_]
    sig_dist = NOMINAL_STOP_ATR * atr[sig_bar]

    no_exit = np.zeros(b.n, dtype=np.bool_)
    exargs = (0.0, 1, 0.0, no_exit, no_exit)   # target_r=0, max_hold=1 bar, trail_atr=0

    log(f"\n{'='*90}\n{symbol} -- intraday time-series momentum, UTC-calendar-day version "
        f"(first 00:00-00:15 UTC return -> last 23:30-00:00 UTC trade), K=1 (no search)\n{b.describe()}\n{'='*90}")
    log(f"signals found: {len(sig_bar)} (one per UTC day with both windows present)")

    for label, lo, hi in (("IS", b.is_lo, b.is_hi), ("OOS", b.oos_lo, b.oos_hi)):
        r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          *exargs, lo, hi)
        pnl, dist = r[3], r[4]
        n = len(pnl)
        if n == 0:
            log(f"{label}: 0 trades"); continue
        pf = C.pct_pf(pnl)
        win = 100 * (pnl > 0).mean()
        log(f"{label}: n={n}  win%={win:.1f}  %PF={pf:.3f}  net%={100*pnl.sum():.1f}")
        if label == "OOS" and n >= 20:
            allowed = np.ones(b.n, dtype=np.bool_)
            pool, p_fire, mean_n = C.random_pool(b, dist, n, *exargs, lo, hi, allowed)
            pctile = 100 * (pool < pf).mean()
            p1 = float((pool >= pf).mean())
            log(f"  random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={mean_n:.0f}): "
                f"median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
            log(f"  REAL OOS %PF={pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]")
            return dict(label=symbol, K=1, oos_n=n, oos_pf=pf, pctile=pctile, p1=p1, verdict=C.verdict(p1))
    return dict(label=symbol, K=1, verdict="insufficient OOS trades")


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/intraday_momentum_halfhour_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    result = run("BTCUSD", log)
    log("\nSUMMARY")
    log(f"  {result}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
