"""
Weekly time-series momentum on BTC - Liu & Tsyvinski, "Risks and Returns
of Cryptocurrency," Review of Financial Studies 34(6), 2021: past
crypto-market return predicts future returns at 1-8 week horizons. A
completely different timeframe from everything else tried in this project
(54 prior BTC constructions, all M15-to-D1) - this is weekly bars, 1-week
hold, pure directional exposure, no intraday mechanics at all.

CONSTRUCTION (K=1 - no free parameters searched/tuned, the single most
literal version of the published rule: 1-week lookback, 1-week hold,
matching the same no-overfitting-risk discipline as the intraday-momentum
test): at the close of week t-1, direction = sign(week t-1's own return,
close-to-open). Enter at week t's open + real spread (this folder's
standard entry convention - see common.py). Hold the FULL week, exit at
week t's close, no stop/target (a deliberately oversized nominal stop
keeps sim_signals' dist>0 requirement satisfied without ever binding -
this is a pure directional momentum bet exactly as the academic
literature defines it, not a risk-managed trading rule).

Weekly bars resampled losslessly from BTC's real native M15 (common.
resample, W = week ending Sunday). ATR(14) computed on the weekly series
itself (roughly a 3-month lookback) only for the nominal-stop sizing.

Splits/cost/null: common.py (BTC IS 2021-01-01 -> 2024-01-01, OOS
2024-01-01 -> end). At weekly granularity the OOS window is only ~140
weeks - flagged honestly if the trade count comes out too thin to
conclude anything either way, per this project's standard (n<20 -> not
enough evidence, not a verdict).
"""
import sys
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

NOMINAL_STOP_ATR = 50.0   # oversized on purpose - pure directional bet, no real risk control, matches the academic construction


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    dfw = C.resample(df15, "W")
    b = C.Bars(dfw, point, symbol)
    o, c, atr = b.open, b.close, b.atr

    week_ret = c - o   # that week's own close-to-open return (points, sign only used)
    sig_bar = np.arange(0, b.n - 1, dtype=np.int64)   # signal fires at the close of week i, trades week i+1
    sig_dir = np.where(week_ret[sig_bar] > 0, 1.0, np.where(week_ret[sig_bar] < 0, -1.0, 0.0))
    keep = (sig_dir != 0) & ~np.isnan(atr[sig_bar]) & (atr[sig_bar] > 0)
    sig_bar, sig_dir = sig_bar[keep], sig_dir[keep]
    sig_dist = NOMINAL_STOP_ATR * atr[sig_bar]

    no_exit = np.zeros(b.n, dtype=np.bool_)
    exargs = (0.0, 1, 0.0, no_exit, no_exit)   # target_r=0, max_hold=1 WEEKLY bar, trail_atr=0

    log(f"\n{'='*90}\n{symbol} -- weekly time-series momentum (1-week lookback, 1-week hold), K=1 (no search)\n"
        f"{b.describe()}\n{'='*90}")
    log(f"weekly bars: {b.n}, signals: {len(sig_bar)}")

    result = dict(label=symbol, K=1)
    for key, lo, hi in (("is", b.is_lo, b.is_hi), ("oos", b.oos_lo, b.oos_hi)):
        r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          *exargs, lo, hi)
        pnl = r[3]
        n = len(pnl)
        if n == 0:
            log(f"{key.upper()}: 0 trades"); result[f"{key}_n"] = 0; continue
        pf = C.pct_pf(pnl)
        win = 100 * (pnl > 0).mean()
        log(f"{key.upper()}: n={n}  win%={win:.1f}  %PF={pf:.3f}  net%={100*pnl.sum():.1f}")
        result[f"{key}_n"], result[f"{key}_pf"] = n, pf
        if key == "oos":
            if n < 20:
                log(f"  Only {n} OOS trades at weekly granularity - too few to conclude anything, not a verdict.")
                result["verdict"] = f"insufficient OOS trades (n={n})"
                continue
            allowed = np.ones(b.n, dtype=np.bool_)
            pool, p_fire, mean_n = C.random_pool(b, r[4], n, *exargs, lo, hi, allowed)
            pctile = 100 * (pool < pf).mean()
            p1 = float((pool >= pf).mean())
            log(f"  random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={mean_n:.0f}): "
                f"median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
            log(f"  REAL OOS %PF={pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]")
            result.update(pctile=pctile, p1=p1, verdict=C.verdict(p1))
    return result


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/weekly_momentum_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
