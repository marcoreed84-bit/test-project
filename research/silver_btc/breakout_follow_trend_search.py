"""
"Breakout Follow Trend [Strategy]" (jzd101) - the user's eighth pasted
script in this batch. The script's own comments say it is itself a Pine
port of a real MQL5 EA ("matches MQL5 CalculateRMA_ATR", "matches MQL5
daily reset", "matches MQL5 CheckWeekendClose", "matches MQL5 hedge-like
per-position management") - a Bollinger Band breakout with an EMA(200)
trend filter: long when close > EMA(200) [if enabled] AND close breaks
above the upper Bollinger Band(15, 1.5) AND volume > SMA(volume,15),
inside a fixed UTC trade window (12:00-18:00 default), with ATR(18)-
multiple stop, a fixed R:R target, and a 50%-at-1.6R partial take profit
before the final target (script defaults throughout).

STRIPPED AS OUT OF SCOPE FOR %PF (standard convention every script this
session follows): position sizing / compounding / risk-percent, the
daily-loss-limit circuit breaker (an EQUITY-based rule, not a signal-
timing rule - reproducing it would require modeling account equity path-
dependence, which this project's %PF-per-trade statistic deliberately
avoids), max-concurrent-trades>1 (this engine is one-position-at-a-time
by construction, matching the script's own default inpMaxTrades=1),
weekend-close (inpWeekendCl=false, script's own default - already off),
and the EMA-overlap entry block (inpUseEMABodyFilter=false, script's
own default - already off).

DISCLOSED SIMPLIFICATIONS: the partial-TP-then-runner (50% at RR=1.6,
remainder to RR=2.0) is collapsed to a single full-position exit at the
final R:R target - same conservative convention as this session's other
partial-TP scripts (e.g. "PA Patterns Strategy v2"). The 6-bar post-close
cooldown is dropped: trades in this system typically run for many bars
given an ATR(18)*mult stop and R:R>=1.5 target on M15, so a 6-bar (1.5h)
blackout after a close is a second-order friction next to typical trade
duration, and this engine already enforces one-position-at-a-time.

PORTED FAITHFULLY: the exact signal logic (EMA/BB/volume/time-window
gating on the closed bar, matching the script's own "close1 > upperBB"
convention), the fixed 12:00-18:00 UTC trade window, and the ATR-
multiple stop with a fixed R:R target.

GRID (K=27, literal): STOP_ATR_MULT in {1.5,2.0,3.0} x RR in {1.5,2.0,
3.0} x BB_DEV in {1.0,1.5,2.0}. EMA_PERIOD=200, BB_PERIOD=15, ATR_PERIOD
=18, VOL_PERIOD=15, trade window 12:00-18:00 UTC are the script's own
defaults, fixed to keep K honest.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

STOP_ATR_MULTS = [1.5, 2.0, 3.0]
RRS = [1.5, 2.0, 3.0]
BB_DEVS = [1.0, 1.5, 2.0]
EMA_PERIOD, BB_PERIOD, ATR_PERIOD, VOL_PERIOD = 200, 15, 18, 15
START_HOUR, END_HOUR = 12, 18


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    ema200 = C.ema(b.close, EMA_PERIOD)
    vol_ma = C.sma(b.vol, VOL_PERIOD)
    atr18 = C.wilder_atr(b.high, b.low, b.close, ATR_PERIOD)

    in_window = (b.hour >= START_HOUR) & (b.hour < END_HOUR)
    with np.errstate(invalid="ignore"):
        vol_cond = (b.vol > vol_ma) | np.isnan(vol_ma) | (vol_ma == 0)
        is_above_ema = b.close > ema200
        is_below_ema = b.close < ema200

    bb_cache = {dev: C.bollinger(b.close, BB_PERIOD, dev) for dev in BB_DEVS}

    grid = list(itertools.product(STOP_ATR_MULTS, RRS, BB_DEVS))

    def signal_fn(cfg):
        stop_mult, rr, bb_dev = cfg
        _, upper_bb, lower_bb = bb_cache[bb_dev]
        with np.errstate(invalid="ignore"):
            can_long = is_above_ema & (b.close > upper_bb)
            can_short = is_below_ema & (b.close < lower_bb)
            long_sig = can_long & vol_cond & in_window & ~np.isnan(atr18)
            short_sig = can_short & vol_cond & in_window & ~np.isnan(atr18)
        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        valid_l = atr18[il] > 0
        valid_s = atr18[is_] > 0
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = stop_mult * atr18[il]
        dist_s = stop_mult * atr18[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        return sig_bar[order], sig_dir[order], sig_dist[order]

    def exit_fn(cfg):
        stop_mult, rr, bb_dev = cfg
        no_exit = np.zeros(b.n, dtype=np.bool_)
        return dict(target_r=rr, max_hold=2000, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    return C.full_evaluation(b, f"{symbol} M15 -- Breakout Follow Trend, BB+EMA200+Volume, 12-18 UTC "
                              f"(STOP_ATR_MULT, RR, BB_DEV)", grid, signal_fn, exit_fn, allowed=in_window, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/breakout_follow_trend_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
