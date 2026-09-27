"""
"RSI Mean Reversion Strategy" (kparicharak92615) - the user's last pasted
script in this batch. FLAGGED PER THE USER'S OWN STANDING INSTRUCTION:
the script's own docstring says "Optimized for Natural Gas Mini (MCX) on
4H timeframe" - a different commodity (natural gas, not gold/silver/
bitcoin), a different exchange (India's MCX, not the FX/crypto venue this
project's data comes from), and a different timeframe (4H, not this
project's M15). None of its tuned levels ("Best configs: RSI 3, Oversold
34-40, Overbought 70") carry any presumption of transferring here. Tested
anyway, on M15, on all three instruments, exactly like every other script
this session - but the mismatch is real and disclosed, not silently
ignored.

MECHANISM (simple, fully portable regardless of the above): RSI(n)
crosses back ABOVE an oversold level -> go long (closing any short);
RSI crosses back BELOW an overbought level -> go short (closing any
long). Always-in-market stop-and-reverse, "Both" direction (script
default), no stop-loss/take-profit anywhere - modeled the same way as
this session's other hold-until-opposite-signal systems (unreachable
50x-ATR safety stop, target_r=0, exit_long=shortSignal array,
exit_short=longSignal array).

GRID (K=27, literal): RSI_LEN in {2,3,5} x OVERSOLD in {30,34,40} x
OVERBOUGHT in {60,70,80} - centered on the author's own stated "best
configs" range. awaitBarConfirmation=true (script default, already this
project's own bar-closed convention) is not a free parameter.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C
from xauusd_scalping_v2_search import wilder_rsi

RSI_LENS = [2, 3, 5]
OVERSOLDS = [30.0, 34.0, 40.0]
OVERBOUGHTS = [60.0, 70.0, 80.0]
NO_STOP_ATR_MULT = 50.0


def cross(a, b):
    above = a > b
    above_prev = np.concatenate(([False], above[:-1]))
    up = above & ~above_prev
    dn = (~above) & above_prev
    return up, dn


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    rsi_cache = {rl: wilder_rsi(b.close, rl) for rl in RSI_LENS}

    grid = list(itertools.product(RSI_LENS, OVERSOLDS, OVERBOUGHTS))

    def signal_fn(cfg):
        rsi_len, oversold, overbought = cfg
        rsi = rsi_cache[rsi_len]
        long_sig, _ = cross(rsi, np.full(b.n, oversold))
        _, short_sig = cross(rsi, np.full(b.n, overbought))
        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        valid_l = ~np.isnan(b.atr[il]) & (b.atr[il] > 0)
        valid_s = ~np.isnan(b.atr[is_]) & (b.atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = NO_STOP_ATR_MULT * b.atr[il]
        dist_s = NO_STOP_ATR_MULT * b.atr[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        return sig_bar[order], sig_dir[order], sig_dist[order]

    def exit_fn(cfg):
        rsi_len, oversold, overbought = cfg
        rsi = rsi_cache[rsi_len]
        long_sig, _ = cross(rsi, np.full(b.n, oversold))
        _, short_sig = cross(rsi, np.full(b.n, overbought))
        return dict(target_r=0.0, max_hold=100000, trail_atr=0.0, exit_long=short_sig, exit_short=long_sig)

    return C.full_evaluation(b, f"{symbol} M15 -- RSI Mean Reversion [off-market port, orig=NatGas Mini/MCX 4H] "
                              f"(RSI_LEN, OVERSOLD, OVERBOUGHT)", grid, signal_fn, exit_fn, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/rsi_mean_reversion_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
