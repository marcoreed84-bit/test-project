"""
"20 / 200 SMA Bot Strategy - Clean Usable Version" - the user's fourth
pasted script in this batch. Default configuration (every mode below is
the script's own stated default, not cherry-picked): entryStrictness=
"Trend Pullback Entry" -> long when SMA20>SMA200 (uptrend regime) AND
price crosses back above SMA20 (a pullback-to-the-fast-MA re-entry, not
the raw 20/200 golden-cross itself); mirrored short. stopLossMode=
"Last Opposing Candle Beyond 200 SMA" -> the stop is the low (useOpposing
Wick=true) of the most recent bearish candle that ALSO closed below the
200 SMA (a structural, price-based stop, not a fixed distance), falling
back to a fixed-distance stop if no such candle occurred within
opposingLookback=300 bars or if it sits on the wrong side of price.

DISCLOSED RESCALING (necessary, not optional - same convention as this
session's "Range Breakout Targets" port): takeProfitPoints=100 and
fixedStopPoints=30 are RAW PRICE POINTS, gold-scaled numbers that would
be meaninglessly tiny on BTCUSD and wildly oversized on Silver. The
structural opposing-candle stop is genuinely portable as-is (it's a real
price level, not a fixed distance) and is ported faithfully; the FIXED-
POINTS pieces (the fallback stop and the take-profit) are converted to
ATR multiples instead, exactly as the Range Breakout Targets port did for
its own raw-point measured-move targets. stopBufferPoints=1.0 is dropped
as immaterial next to an ATR-scaled stop (a 1-point buffer is noise on
any of these three instruments' real M15 ranges). A minimum-stop-distance
ATR floor is added (same precedent as the Liquidity Sweep Reversal port)
since a structural opposing-candle stop can occasionally sit
unrealistically close to price.

PORTED FAITHFULLY: the SMA20/SMA200 pullback entry logic exactly as
written, the causal "most recent opposing candle, only if within
opposingLookback bars" stop search (forward-filled low/high of the last
qualifying candle, invalidated once it falls off the lookback window or
sits on the wrong side of price), and "Both" trade direction (script
default) with one position at a time (pyramiding=0, matches this
engine's convention already).

GRID (K=27, literal): TP_R_MULT in {1.0,2.0,3.0} (take-profit as a
multiple of the REALIZED stop distance, replacing the fixed 100-point
target) x FALLBACK_STOP_ATR_MULT in {1.0,2.0,3.0} (replacing the fixed
30-point fallback stop) x MIN_STOP_ATR_FLOOR in {0.3,0.6,1.0}. SMA
lengths (20,200), opposingLookback=300 are the script's own defaults,
fixed to keep K honest.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

TP_R_MULTS = [1.0, 2.0, 3.0]
FALLBACK_STOP_ATR_MULTS = [1.0, 2.0, 3.0]
MIN_STOP_ATR_FLOORS = [0.3, 0.6, 1.0]
FAST_LEN, SLOW_LEN, OPPOSING_LOOKBACK = 20, 200, 300


def cross(a, b):
    above = a > b
    above_prev = np.concatenate(([False], above[:-1]))
    up = above & ~above_prev
    dn = (~above) & above_prev
    return up, dn


def bars_since(cond):
    n = len(cond)
    out = np.full(n, 10 ** 9, dtype=np.int64)
    last = -1
    for i in range(n):
        if cond[i]:
            last = i
        out[i] = (i - last) if last >= 0 else 10 ** 9
    return out


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    fast_sma = C.sma(b.close, FAST_LEN)
    slow_sma = C.sma(b.close, SLOW_LEN)
    fast_above = fast_sma > slow_sma
    fast_below = fast_sma < slow_sma
    cross_up_close_fast, _ = cross(b.close, fast_sma)
    _, cross_dn_close_fast = cross(b.close, fast_sma)

    with np.errstate(invalid="ignore"):
        long_base = fast_above & cross_up_close_fast
        short_base = fast_below & cross_dn_close_fast

    buy_opposing = (b.close < b.open) & (b.close < slow_sma)
    sell_opposing = (b.close > b.open) & (b.close > slow_sma)

    buy_opp_low = pd.Series(np.where(buy_opposing, b.low, np.nan)).ffill().values
    sell_opp_high = pd.Series(np.where(sell_opposing, b.high, np.nan)).ffill().values
    bars_since_buy = bars_since(buy_opposing)
    bars_since_sell = bars_since(sell_opposing)
    valid_buy_opp = bars_since_buy <= OPPOSING_LOOKBACK
    valid_sell_opp = bars_since_sell <= OPPOSING_LOOKBACK

    grid = list(itertools.product(TP_R_MULTS, FALLBACK_STOP_ATR_MULTS, MIN_STOP_ATR_FLOORS))

    def signal_fn(cfg):
        tp_r_mult, fb_mult, floor_mult = cfg
        il = np.where(long_base)[0]
        is_ = np.where(short_base)[0]
        valid_l = ~np.isnan(b.atr[il]) & (b.atr[il] > 0)
        valid_s = ~np.isnan(b.atr[is_]) & (b.atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]

        struct_stop_l = np.where(valid_buy_opp[il], buy_opp_low[il], np.nan)
        dist_struct_l = b.close[il] - struct_stop_l
        use_struct_l = ~np.isnan(dist_struct_l) & (dist_struct_l > 0)
        dist_l = np.where(use_struct_l, dist_struct_l, fb_mult * b.atr[il])
        dist_l = np.maximum(dist_l, floor_mult * b.atr[il])

        struct_stop_s = np.where(valid_sell_opp[is_], sell_opp_high[is_], np.nan)
        dist_struct_s = struct_stop_s - b.close[is_]
        use_struct_s = ~np.isnan(dist_struct_s) & (dist_struct_s > 0)
        dist_s = np.where(use_struct_s, dist_struct_s, fb_mult * b.atr[is_])
        dist_s = np.maximum(dist_s, floor_mult * b.atr[is_])

        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        return sig_bar[order], sig_dir[order], sig_dist[order]

    def exit_fn(cfg):
        tp_r_mult, fb_mult, floor_mult = cfg
        no_exit = np.zeros(b.n, dtype=np.bool_)
        return dict(target_r=tp_r_mult, max_hold=2000, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    return C.full_evaluation(b, f"{symbol} M15 -- 20/200 SMA Bot, Trend Pullback Entry (TP_R_MULT, "
                              f"FALLBACK_STOP_ATR_MULT, MIN_STOP_ATR_FLOOR)", grid, signal_fn, exit_fn, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/sma_20_200_bot_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
