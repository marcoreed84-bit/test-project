"""
Round-number psychological price levels as support/resistance, on BTCUSD -
never tested on BTC before (the only existing round-number test,
research/trendbreaker/round_number_sr_test.py, is GOLD-only, H4/D1, using
$25/$50 increments appropriate to Gold's ~$1900-4500 range). BTC's own IS/
OOS window (2021-2024 / 2024-end) spans roughly $16k-$111k, so Gold's
increments would be meaningless here (a $25 level is noise at BTC's scale)
and BTC's own increments would be meaningless on Gold - this is NOT the
same construction reused instrument-agnostically like the MA-period search
was; the increment itself has to be instrument-appropriate, so this script
is BTC-only by design, not a gap in cross-instrument coverage.

MECHANISM (distinct from the generic MA-bounce test already run and
failed): retail leverage in crypto concentrates stop-losses and liquidation
levels at round dollar figures ($20k, $25k, ..., $100k) far more heavily
than in FX/metals - this is a BTC-specific, not borrowed-from-Gold,
rationale. Same underlying idea as Osler's documented FX round-number
clustering (cited in the Gold version of this test), applied at the scale
BTC retail actually quotes/clusters at.

SIGNAL (same touch-and-reject definition as the Gold version, same-bar):
  SHORT: this bar's HIGH comes within TOUCH_TOL_ATR x ATR14 of the nearest
         round level above (from below), AND this bar's CLOSE ends back
         below (level - TOUCH_TOL_ATR x ATR14).
  LONG:  mirror, at the nearest round level below.
  A bar triggering both directions at once (ambiguous) is skipped.
EXECUTION: this folder's standard convention (see common.py) - signal bar i
fills at close[i] + spread[i+1], not the original Gold script's
next-bar-open convention; the signal's stop distance is reconstructed as
abs(close[i] - (level +/- STOP_ATR x ATR14)) so sim_signals' SL/TP
machinery reproduces "stop beyond the level" exactly. One position at a
time (sim_signals), target = RR x risk, time-stop at HORIZON_BARS.

GRID (K=16, literal, same shape as the Gold version): INCREMENT in
{$1000, $5000} (BTC-appropriate - not copied from Gold's $25/$50) x
TOUCH_TOL_ATR in {0.15, 0.3} x STOP_ATR in {0.5, 1.0} x RR in {1.5, 2.5}.
Run on H4 and D1, resampled losslessly from BTC's real native M15
(common.resample), each with its own frozen K=16 search (not shared/
reused between timeframes, same honesty standard as everywhere else).

Splits/cost/null: common.py (BTC IS 2021-01-01 -> 2024-01-01, OOS
2024-01-01 -> end, already-validated spread/point handling).
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

INCREMENTS = (1000.0, 5000.0)
TOUCH_TOLS = (0.15, 0.3)
STOP_ATRS = (0.5, 1.0)
RRS = (1.5, 2.5)
HORIZON_BARS = dict(H4=180, D1=60)   # same as the Gold version: ~30 days H4, ~60 days D1


def run(symbol, timeframe, resample_rule, log):
    df15, point = C.load_m15(symbol)
    df = C.resample(df15, resample_rule)
    b = C.Bars(df, point, symbol)
    h, l, c, atr = b.high, b.low, b.close, b.atr
    valid = ~np.isnan(atr) & (atr > 0)

    lvl_cache = {}
    for inc in INCREMENTS:
        lvl_cache[inc] = (np.round(h / inc) * inc, np.round(l / inc) * inc)

    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        inc, tol_mult, stop_atr, rr = cfg
        lvl_hi, lvl_lo = lvl_cache[inc]
        tol = tol_mult * atr
        short_ok = valid & (h >= lvl_hi - tol) & (h <= lvl_hi + tol) & (c <= lvl_hi - tol)
        long_ok = valid & (l >= lvl_lo - tol) & (l <= lvl_lo + tol) & (c >= lvl_lo + tol)
        ambiguous = short_ok & long_ok
        short_ok = short_ok & ~ambiguous
        long_ok = long_ok & ~ambiguous

        stop_short = lvl_hi + stop_atr * atr
        stop_long = lvl_lo - stop_atr * atr
        dist_short = stop_short - c
        dist_long = c - stop_long

        il = np.where(long_ok & (dist_long > 0))[0]
        is_ = np.where(short_ok & (dist_short > 0))[0]
        bars_ = np.concatenate((il, is_))
        dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        dist = np.concatenate((dist_long[il], dist_short[is_]))
        o = np.argsort(bars_, kind="stable")
        return bars_[o].astype(np.int64), dirs[o], dist[o]

    def exit_fn(cfg):
        inc, tol_mult, stop_atr, rr = cfg
        return dict(target_r=rr, max_hold=HORIZON_BARS[timeframe], trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(INCREMENTS, TOUCH_TOLS, STOP_ATRS, RRS))
    return C.full_evaluation(b, f"{symbol} {timeframe} -- round-number S/R touch+reject (INCREMENT, TOUCH_TOL_ATR, "
                                f"STOP_ATR, RR)", grid, signal_fn, exit_fn, min_is_n=20, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/round_number_sr_btc_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [
        run("BTCUSD", "H4", "4h", log),
        run("BTCUSD", "D1", "1D", log),
    ]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
