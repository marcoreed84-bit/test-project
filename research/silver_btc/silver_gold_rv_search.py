"""
Gold/silver RELATIVE-VALUE mean reversion, traded as a SILVER-only position
(H1, both legs resampled from real native M15 and inner-joined on common
timestamps).

WHY / HOW THIS DIFFERS FROM silver_gold_lead_signal_search.py: that file
used gold's own EMA trend (a directional signal on gold) to time silver and
failed at its real K=64. This asks a different question: gold and silver
co-move at ~0.75 correlation on M15 (stable 2014-2026), so when silver has
temporarily lagged or overshot gold by an unusual amount, does silver
converge back? Signal = z-score of the log price ratio residual
r = log(SILVER) - log(GOLD) against its own rolling N-bar mean/std. The
position is SILVER only (no gold hedge) - the thing being tested is whether
the relative dislocation predicts silver's own next move.

SIGNAL: long SILVER when z crosses below -Z (silver cheap vs gold), short
when z crosses above +Z. EXIT: fixed time exit after HOLD H1 bars, plus a
3 x ATR14(H1) catastrophe stop (fixed). A z-reverts-to-zero exit was
deliberately NOT used: a random-direction entry run through a "z back to 0"
exit array exits almost immediately whenever it happens to be on the
"wrong" side, which would drag the random null down and flatter the real
system. Time + ATR exits are identical and neutral for both.

GRID (declared before running, K = 12):
  N in {48, 240} H1 bars (~2 / ~10 trading days) x Z in {1.5, 2.0, 2.5}
  x HOLD in {12, 48} H1 bars

DATA: GOLD_M15_native.csv trimmed to >= 2014-06-13 (the pre-2014-06 rows
are mislabeled daily/hourly bars - see research/aurelius/engine.py);
SILVER_M15_native.csv from 2014-06-12. Silver point 0.001 (asserted from
the header). Split = common.SPLITS["SILVER"] (IS -> 2021-01-01, OOS after).
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

NS = [48, 240]
ZS = [1.5, 2.0, 2.5]
HOLDS = [12, 48]
STOP_ATR = 3.0


def load_merged_h1():
    s15, sp = C.load_m15("SILVER")
    g15, _ = C.load_m15("GOLD")
    g15 = g15[g15["time"] >= "2014-06-13"]
    s15 = s15[s15["time"] >= "2014-06-13"]
    s1 = C.resample(s15, "1h"); g1 = C.resample(g15, "1h")
    m = s1.merge(g1[["time", "close"]].rename(columns={"close": "gclose"}), on="time", how="inner")
    return m.reset_index(drop=True), sp


def run(log):
    m, point = load_merged_h1()
    b = C.Bars(m, point, "SILVER")
    r = np.log(b.close) - np.log(m["gclose"].values.astype(float))
    no_exit = np.zeros(b.n, dtype=np.bool_)
    zc = {}
    for N in NS:
        mu = pd.Series(r).rolling(N, min_periods=N).mean().values
        sd = pd.Series(r).rolling(N, min_periods=N).std(ddof=0).values
        zc[N] = (r - mu) / sd

    def signal_fn(cfg):
        N, Z, _ = cfg
        z = zc[N]
        zp = np.concatenate(([np.nan], z[:-1]))
        L = (z < -Z) & (zp >= -Z) & ~np.isnan(b.atr)
        S = (z > Z) & (zp <= Z) & ~np.isnan(b.atr)
        il = np.where(L)[0]; is_ = np.where(S)[0]
        bars_ = np.concatenate((il, is_)); dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        o = np.argsort(bars_, kind="stable")
        bars_, dirs = bars_[o].astype(np.int64), dirs[o]
        return bars_, dirs, STOP_ATR * b.atr[bars_]

    def exit_fn(cfg):
        return dict(target_r=0.0, max_hold=cfg[2], trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(NS, ZS, HOLDS))
    return C.full_evaluation(b, "SILVER H1 (traded) vs GOLD H1 (reference) -- log-ratio z-score reversion (N, Z, HOLD)",
                             grid, signal_fn, exit_fn, min_is_n=100, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/silver_gold_rv_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    res = run(log)
    log("\nSUMMARY")
    log(f"  {res}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
