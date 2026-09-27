"""
"XAUUSD Scalping V2 AGRESIV" (Romanian-language inputs, e.g. "EMA Rapid" /
"EMA Lent" = fast/slow EMA) - the user's sixth pasted script in this
batch, explicitly named for XAUUSD scalping. Plain EMA(5)/EMA(13) cross
+ RSI(7) momentum filter (RSI>55 for longs, RSI<45 for shorts) + a raw-
ATR minimum-volatility gate, ATR-multiple TP/SL/trailing stop.

DISCLOSED SCALE MISMATCH (per the user's own instruction to flag when a
script's parameters are tuned for a different instrument than the one
being tested): minVolatility=0.5 is a RAW PRICE-UNIT ATR floor, not a
percentage - calibrated for XAUUSD's own ATR scale (~$3-15 on M15).
Applied literally, it would be a near-no-op filter on BTCUSD (ATR in the
hundreds-to-thousands of $) and a much stricter filter on Silver (ATR
often <$0.5 on M15) than the author intended for gold. Rather than carry
a gold-specific magic number onto instruments it wasn't built for, this
filter is DROPPED for all three (minVolatility=0 effectively) and
flagged here rather than silently reinterpreted or silently kept.

PORTED FAITHFULLY: ta.crossover/crossunder(EMA_fast, EMA_slow) with the
RSI(7) confirmation, ATR(14)-multiple stop/target, and the trailing-stop-
with-activation-offset (trail_points) mechanic - approximated with this
engine's trail_atr (chandelier-from-best-close-since-entry), a disclosed
simplification since Pine's trail_points needs an activation offset this
engine doesn't model; close enough in spirit (both ratchet the stop
toward price by a fixed ATR multiple once triggered).

GRID (K=27, literal): RSI_LONG_TH in {50,55,60} (short threshold mirrored
as 100-RSI_LONG_TH) x TP_ATR_MULT in {1.0,1.2,1.8} x SL_ATR_MULT in
{0.6,0.8,1.2}. EMA lengths (5,13), RSI length (7), ATR length (14) and
trail multiple (0.5) are the script's own defaults, fixed to keep K
honest.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

RSI_LONG_THS = [50.0, 55.0, 60.0]
TP_ATR_MULTS = [1.0, 1.2, 1.8]
SL_ATR_MULTS = [0.6, 0.8, 1.2]
EMA_FAST_LEN, EMA_SLOW_LEN, RSI_LEN, ATR_LEN = 5, 13, 7, 14
TRAIL_ATR_MULT = 0.5


def wilder_rsi(c, period):
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = pd.Series(gain).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean().values
    avg_loss = pd.Series(loss).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean().values
    rs = np.divide(avg_gain, avg_loss, out=np.full(len(c), np.nan), where=avg_loss != 0)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = np.where(avg_loss == 0, 100.0, rsi)
    return rsi


def cross(a, b):
    above = a > b
    above_prev = np.concatenate(([False], above[:-1]))
    up = above & ~above_prev
    dn = (~above) & above_prev
    return up, dn


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    ema_fast = C.ema(b.close, EMA_FAST_LEN)
    ema_slow = C.ema(b.close, EMA_SLOW_LEN)
    rsi = wilder_rsi(b.close, RSI_LEN)
    cross_up, cross_dn = cross(ema_fast, ema_slow)

    grid = list(itertools.product(RSI_LONG_THS, TP_ATR_MULTS, SL_ATR_MULTS))

    def signal_fn(cfg):
        rsi_long_th, tp_mult, sl_mult = cfg
        rsi_short_th = 100.0 - rsi_long_th
        long_sig = cross_up & (rsi > rsi_long_th)
        short_sig = cross_dn & (rsi < rsi_short_th)
        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        valid_l = ~np.isnan(b.atr[il]) & (b.atr[il] > 0)
        valid_s = ~np.isnan(b.atr[is_]) & (b.atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = sl_mult * b.atr[il]
        dist_s = sl_mult * b.atr[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        return sig_bar[order], sig_dir[order], sig_dist[order]

    def exit_fn(cfg):
        rsi_long_th, tp_mult, sl_mult = cfg
        target_r = tp_mult / sl_mult
        no_exit = np.zeros(b.n, dtype=np.bool_)
        return dict(target_r=target_r, max_hold=2000, trail_atr=TRAIL_ATR_MULT, exit_long=no_exit, exit_short=no_exit)

    return C.full_evaluation(b, f"{symbol} M15 -- XAUUSD Scalping V2 AGRESIV (RSI_LONG_TH, TP_ATR_MULT, SL_ATR_MULT)",
                              grid, signal_fn, exit_fn, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/xauusd_scalping_v2_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
