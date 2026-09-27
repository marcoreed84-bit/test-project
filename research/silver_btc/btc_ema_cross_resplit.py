"""
Re-run of research/aurelius/btc_native_search.py's bare EMA-cross search on
BTCUSD M15 with the IDENTICAL 64-combo grid, but under this folder's
cost-sane split (IS 2021-01-01 -> 2024-01-01, OOS 2024-01-01 -> end) instead
of the original IS 2017-07 -> 2022-01.

WHY RE-TEST AN ALREADY-FAILED MECHANISM: the original search's IS window is
dominated by 2018Q2-2020Q4, when this broker's recorded BTC spread was
0.65-1.6% of price per round trip (3-5x a whole M15 bar's range). Its IS
ranking therefore mostly measured "which config trades least" rather than
signal quality, so its OOS failure (p=0.56) does not cleanly say whether
EMA-cross trend following works on BTC. This is the one earlier result
whose verdict could have been an artifact of the split, so it is re-checked
here - same grid, same hold-to-reversal logic, no new parameters.

CONSTRUCTION (unchanged): fast/slow EMA cross on close, enter on the cross,
exit on the next opposite cross (an exit ARRAY here: exit_long = bars where
fast crosses below slow, exit_short mirror - identical for random entries,
which is exactly how the original file capped random trades), or a
STOP_ATR x ATR14 stop. Grid FAST {10,20,30,50} x SLOW {100,150,200,300} x
STOP_ATR {2,3,4,5} = K=64. IS n floor 100. Point 0.01 from the CSV header.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

FASTS = [10, 20, 30, 50]
SLOWS = [100, 150, 200, 300]
STOP_ATRS = [2.0, 3.0, 4.0, 5.0]


def run(log):
    df, point = C.load_m15("BTCUSD")
    b = C.Bars(df, point, "BTCUSD")
    emas = {p: C.ema(b.close, p) for p in set(FASTS) | set(SLOWS)}
    crosses = {}
    for f, s in itertools.product(FASTS, SLOWS):
        above = emas[f] > emas[s]
        ap = np.concatenate(([False], above[:-1]))
        warm = np.arange(b.n) > s
        crosses[(f, s)] = ((above & ~ap & warm).astype(np.bool_), (~above & ap & warm).astype(np.bool_))

    def signal_fn(cfg):
        f, s, stop = cfg
        up, dn = crosses[(f, s)]
        il = np.where(up)[0]; is_ = np.where(dn)[0]
        bars_ = np.concatenate((il, is_)); dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        o = np.argsort(bars_, kind="stable")
        bars_, dirs = bars_[o].astype(np.int64), dirs[o]
        a = np.nan_to_num(b.atr[bars_], nan=0.0)
        return bars_, dirs, stop * a

    def exit_fn(cfg):
        up, dn = crosses[(cfg[0], cfg[1])]
        return dict(target_r=0.0, max_hold=10**7, trail_atr=0.0, exit_long=dn, exit_short=up)

    grid = list(itertools.product(FASTS, SLOWS, STOP_ATRS))
    return C.full_evaluation(b, "BTCUSD M15 -- bare EMA cross, hold to reversal (FAST, SLOW, STOP_ATR) [cost-sane re-split]",
                             grid, signal_fn, exit_fn, min_is_n=100, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/btc_ema_cross_resplit_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    res = run(log)
    log("\nSUMMARY")
    log(f"  {res}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
