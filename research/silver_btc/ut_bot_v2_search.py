"""
"UT Bot v2 -- ATR Trailing Stop" (QuantNomad) - the user's first pasted
script in this newest batch. A pure ATR trailing-stop-line flip system:
a recursive stop line (tsl_price) that ratchets toward price from below
while price stays above it (locking in the max of its prior value and
close-mult*ATR) or ratchets from above while price stays below it, and
resets to close -/+ mult*ATR the instant price crosses the line. Entries
ARE exits: buy = price crosses above the line (closes any short, opens
long); sell = price crosses below (closes any long, opens short). No
separate stop-loss or take-profit anywhere in the original - the line
itself is the only risk control, entirely via the opposite-cross exit.

PORTED FAITHFULLY: the exact recursive tsl_price update (4-way ternary,
vectorized here as a bar loop since it's self-referential), true
crossover (not just >/< - requires the PREVIOUS bar to be on the other
side), and "no stop-loss/take-profit, exit only on opposite cross" -
modeled the same way as this session's other hold-until-flip scripts
(BTC Supertrend+EMA, Supertrend Vol Regime): a practically-unreachable
50x-ATR stop stands in for "none", target_r=0, exit_long/exit_short =
the opposite signal's own boolean array. Backtest date range filter
(use_date_filter, defaults to 2020-2030) is dropped - out of scope for
a walk-forward IS/OOS split that already restricts the tested window.

GRID (K=15, literal): MULT in {0.5,1.0,1.5,2.0,3.0} x ATR_LEN in
{7,10,14}. mult=1, atr_len=10 are the script's own defaults.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

MULTS = [0.5, 1.0, 1.5, 2.0, 3.0]
ATR_LENS = [7, 10, 14]
NO_STOP_ATR_MULT = 50.0


def compute_tsl(src, atr, mult):
    n = len(src)
    sl = mult * atr
    tsl = np.zeros(n)
    for i in range(1, n):
        prev = tsl[i - 1]
        if src[i] > prev and src[i - 1] > prev:
            tsl[i] = max(prev, src[i] - sl[i])
        elif src[i] < prev and src[i - 1] < prev:
            tsl[i] = min(prev, src[i] + sl[i])
        else:
            tsl[i] = src[i] - sl[i] if src[i] > prev else src[i] + sl[i]
    return tsl


def cross(a, b):
    above = a > b
    above_prev = np.concatenate(([False], above[:-1]))
    up = above & ~above_prev
    dn = (~above) & above_prev
    return up, dn


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    atr_cache = {al: C.wilder_atr(b.high, b.low, b.close, al) for al in ATR_LENS}

    grid = list(itertools.product(MULTS, ATR_LENS))

    def signal_fn(cfg):
        mult, atr_len = cfg
        atr = atr_cache[atr_len]
        tsl = compute_tsl(b.close, np.nan_to_num(atr, nan=0.0), mult)
        buy, sell = cross(b.close, tsl)
        il = np.where(buy)[0]
        is_ = np.where(sell)[0]
        valid_l = ~np.isnan(atr[il]) & (atr[il] > 0)
        valid_s = ~np.isnan(atr[is_]) & (atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = NO_STOP_ATR_MULT * atr[il]
        dist_s = NO_STOP_ATR_MULT * atr[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        return sig_bar[order], sig_dir[order], sig_dist[order]

    def exit_fn(cfg):
        mult, atr_len = cfg
        atr = atr_cache[atr_len]
        tsl = compute_tsl(b.close, np.nan_to_num(atr, nan=0.0), mult)
        buy, sell = cross(b.close, tsl)
        return dict(target_r=0.0, max_hold=100000, trail_atr=0.0, exit_long=sell, exit_short=buy)

    return C.full_evaluation(b, f"{symbol} M15 -- UT Bot v2 (MULT, ATR_LEN)", grid, signal_fn, exit_fn, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/ut_bot_v2_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
