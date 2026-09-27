"""
"MSG Ultimate v5.1" - the user's seventh pasted script in this batch.
Genuinely different construction from the real MQL5 "MSG EA" already
audited and dropped earlier this session (research/msg*/ - a distinct,
unrelated system despite the shared name). This one is a session-box
mean/breakout bias system: at the start of each of three UTC session
windows (Asia 00:00-06:00, London 07:00-12:00, NY 13:00-17:00), record
that session's opening (high+low)/2 as its "mean" (held fixed for the
rest of that session, NOT updated as the session's range grows). Entry
requires close to break above/below BOTH the currently-active session's
mean and a "previous session's mean" by an ATR/2 buffer, plus a trend
filter (EMA 50).

FAITHFULLY REPRODUCED QUIRK (not silently fixed - same policy as this
session's other scripts with a real behavioral oddity, e.g. the 1
Trendline Strategy's raw/padded asymmetry): "prevMean" is written as
`not na(nyMean) ? nyMean : not na(londonMean) ? londonMean : asiaMean`
using Pine `var` variables that are NEVER reset to na once first
assigned. Since nyMean gets set on the very first NY session and stays
non-na forever after, prevMean collapses to "the mean of the most recent
NY session" for the entire remaining backtest - it is NOT a rolling
"previous session" value once trading has run past its first NY session.
Ported exactly as written (forward-filled per-session means, same
priority-ternary), not as the author probably intended.

ALSO FAITHFULLY REPRODUCED: `bias==1`/`bias==-1` and the probability/
minProb gate are BOTH structurally redundant given the script's own math
(bull/bear already imply bias's sign; score can only be 0 or 1 so
prob is only ever 30 or 65, and the default minProb=50 just requires
score>=1, which bull/bear already require) - kept in spirit by simply
not re-deriving them, since they change nothing. "One trade per session"
(the `traded` flag reset at every Asia/London/NY start, even though Asia
is disabled by default) is reproduced via a per-session-block "first
qualifying signal only" mask. TP/SL are symmetric ATR multiples (target_r
is therefore always exactly 1.0, not a free parameter - it cancels out
regardless of atrMult).

GRID (K=27, literal): EMA_LEN in {20,50,100} x ATR_MULT in {1.0,1.5,2.5}
x BUFFER_ATR_MULT in {0.25,0.5,0.75}. Sessions traded = London+NY (script
defaults, Asia off), ATR_LEN=14 fixed to keep K honest.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

EMA_LENS = [20, 50, 100]
ATR_MULTS = [1.0, 1.5, 2.5]
BUFFER_ATR_MULTS = [0.25, 0.5, 0.75]
ATR_LEN = 14
TRADE_ASIA, TRADE_LONDON, TRADE_NY = False, True, True


def session_start(mask):
    prev = np.concatenate(([False], mask[:-1]))
    return mask & ~prev


def ffill_on(raw_where_true, source_values):
    arr = np.where(raw_where_true, source_values, np.nan)
    return pd.Series(arr).ffill().values


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    in_asia = b.hour < 6
    in_london = (b.hour >= 7) & (b.hour < 12)
    in_ny = (b.hour >= 13) & (b.hour < 17)
    asia_start = session_start(in_asia)
    london_start = session_start(in_london)
    ny_start = session_start(in_ny)

    mid = (b.high + b.low) / 2.0
    asia_mean = ffill_on(asia_start, mid)
    london_mean = ffill_on(london_start, mid)
    ny_mean = ffill_on(ny_start, mid)

    prev_mean = np.where(~np.isnan(ny_mean), ny_mean, np.where(~np.isnan(london_mean), london_mean, asia_mean))
    current_mean = np.where(in_ny, ny_mean, np.where(in_london, london_mean, asia_mean))

    valid_session = (in_asia & TRADE_ASIA) | (in_london & TRADE_LONDON) | (in_ny & TRADE_NY)

    any_start = asia_start | london_start | ny_start
    block_id = np.cumsum(any_start)

    atr = C.wilder_atr(b.high, b.low, b.close, ATR_LEN)

    grid = list(itertools.product(EMA_LENS, ATR_MULTS, BUFFER_ATR_MULTS))
    ema_cache = {el: C.ema(b.close, el) for el in EMA_LENS}

    def signal_fn(cfg):
        ema_len, atr_mult, buf_mult = cfg
        ema = ema_cache[ema_len]
        buffer = atr * buf_mult
        with np.errstate(invalid="ignore"):
            bull = (b.close > prev_mean + buffer) & (b.close > current_mean + buffer) & (b.close > ema)
            bear = (b.close < prev_mean - buffer) & (b.close < current_mean - buffer) & (b.close < ema)
            buy = bull & valid_session
            sell = bear & valid_session
        sig = buy | sell
        dfb = pd.DataFrame({"block": block_id, "sig": sig.astype(np.int64)})
        cum_in_block = dfb.groupby("block")["sig"].cumsum().values
        first_in_block = sig & (cum_in_block == 1)
        buy_first = buy & first_in_block
        sell_first = sell & first_in_block

        il = np.where(buy_first)[0]
        is_ = np.where(sell_first)[0]
        valid_l = ~np.isnan(atr[il]) & (atr[il] > 0)
        valid_s = ~np.isnan(atr[is_]) & (atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = atr_mult * atr[il]
        dist_s = atr_mult * atr[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        return sig_bar[order], sig_dir[order], sig_dist[order]

    def exit_fn(cfg):
        no_exit = np.zeros(b.n, dtype=np.bool_)
        return dict(target_r=1.0, max_hold=2000, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    return C.full_evaluation(b, f"{symbol} M15 -- MSG Ultimate v5.1, session-mean breakout (EMA_LEN, ATR_MULT, "
                              f"BUFFER_ATR_MULT)", grid, signal_fn, exit_fn,
                              allowed=valid_session.astype(np.bool_), log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/msg_ultimate_v51_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
