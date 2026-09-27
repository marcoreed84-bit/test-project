"""
Bollinger-extreme + volume-climax EXHAUSTION FADE on SILVER and BTCUSD (H1
resampled from real native M15). Mean reversion off Bollinger extremes
WITH a volume confirmation - a different reversal trigger from the
Stochastic cross-from-extreme that already failed (that one fired on an
oscillator cross with no volume/exhaustion condition and no structural
stop) and from the liquidity-sweep/BOS reversal in this folder (that one
needs a swing-level stop-run; this one needs a volatility-band overshoot on
abnormal volume).

SIGNAL (short; long is the mirror): bar i-1 CLOSED above the upper
Bollinger(20, DEV) band on tick volume > VM x its own prior-20-bar mean
(climax; VM=0 -> no volume condition), and bar i closes back INSIDE the
band (the overshoot failed) -> SHORT at bar i's close. Stop = the higher of
bars i-1/i's highs + 0.25 ATR (structural, fixed buffer). Target =
TARGET_R x stop distance; max hold 48 H1 bars.

GRID (declared before running, K = 8 per instrument):
  DEV in {2.0, 2.5} x VM in {0, 2.0} x TARGET_R in {1, 2}

Splits / cost / null / K: see common.py. Point from the CSV header.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

DEVS = [2.0, 2.5]
VMS = [0.0, 2.0]
TARGET_RS = [1.0, 2.0]
MAX_HOLD = 48
STOP_BUF_ATR = 0.25


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    df = C.resample(df15, "1h")
    b = C.Bars(df, point, symbol)
    c = b.close
    vavg_prev = np.concatenate(([np.nan], C.sma(b.vol, 20)[:-1]))
    vratio = b.vol / vavg_prev
    bands = {d: C.bollinger(c, 20, d) for d in DEVS}
    sh = lambda x: np.concatenate(([np.nan], x[:-1]))
    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        dev, vm, _ = cfg
        mid, up, lo = bands[dev]
        climax = np.ones(b.n, bool) if vm == 0 else (sh(vratio) > vm)
        S = (sh(c) > sh(up)) & climax & (c < up) & ~np.isnan(b.atr)
        L = (sh(c) < sh(lo)) & climax & (c > lo) & ~np.isnan(b.atr)
        il = np.where(L)[0]; is_ = np.where(S)[0]
        dl = c[il] - (np.minimum(b.low[il], b.low[il - 1]) - STOP_BUF_ATR * b.atr[il])
        ds = (np.maximum(b.high[is_], b.high[is_ - 1]) + STOP_BUF_ATR * b.atr[is_]) - c[is_]
        bars_ = np.concatenate((il, is_)); dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        dist = np.concatenate((dl, ds))
        o = np.argsort(bars_, kind="stable")
        return bars_[o].astype(np.int64), dirs[o], dist[o]

    def exit_fn(cfg):
        return dict(target_r=cfg[2], max_hold=MAX_HOLD, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(DEVS, VMS, TARGET_RS))
    return C.full_evaluation(b, f"{symbol} H1 -- Bollinger-extreme volume-climax fade (DEV, VM, TARGET_R)",
                             grid, signal_fn, exit_fn, min_is_n=100, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/bb_climax_fade_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
