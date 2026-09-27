"""
"Asian Breakout - AutoBot & Visuals" - the user's ninth pasted script in
this batch. A clean, well-known ICT-style session-range breakout: the
Asia session (00:00-08:00 UTC) builds a high/low box; during the UK
(08:00-13:30) and US (13:30-20:00) sessions (one continuous trade
window, 08:00-20:00), a close crossing above the Asia high triggers a
long (stop = Asia low, target = Asia high + Asia-range * RR); crossing
below the Asia low triggers a short (mirrored). Position force-closed at
the end of the US session if still open.

PORTED FAITHFULLY: the session-box high/low tracking (causal running
max/min while in Asia, held fixed once Asia ends - forward-filled per
session, same technique used for this session's other session-box
scripts), true crossover/crossunder of close vs the Asia high/low level,
one-trade-at-a-time (already this engine's own convention), and the
end-of-US-session forced close (an unconditional exit_long/exit_short
signal at that bar, matching strategy.close_all).

DISCLOSED APPROXIMATION: the original's stop/target are absolute PRICE
LEVELS (a_low, a_high + range*RR), not an R-multiple of the entry's own
risk. This engine's target_r is a single scalar shared across a whole
grid config, not a per-trade ratio - but since long entries fire almost
exactly AT the Asia-high crossing (close only marginally beyond a_high
on the triggering bar), the realized stop distance (close-a_low) is
already ~= the Asia range, so target_r=RR_TARGET is a near-exact
reproduction of "target = a_high + range*RR" and not a separate
simplification of the trade's economics - the actual per-trade stop
distance (close-a_low, exact) still drives risk and %PF.

GRID (K=12): RR_TARGET in {1.0,1.5,2.0,3.0} (script default 2.0) x
MIN_ASIA_RANGE_ATR_MULT in {0.0 (off), 0.3, 0.6} - a minimum-range floor
excluding abnormally tight/noise-scale Asia ranges, same precedent as
the minimum-stop-distance floor used in the Liquidity Sweep Reversal
port. Session boundaries (00:00/08:00/13:30/20:00 UTC) are the script's
own defaults, fixed to keep K honest.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

RR_TARGETS = [1.0, 1.5, 2.0, 3.0]
MIN_RANGE_ATR_MULTS = [0.0, 0.3, 0.6]


def session_mask(hour, minute, h0, m0, h1, m1):
    t = hour * 60 + minute
    t0, t1 = h0 * 60 + m0, h1 * 60 + m1
    return (t >= t0) & (t < t1)


def session_start_end(mask):
    prev = np.concatenate(([False], mask[:-1]))
    start = mask & ~prev
    end = prev & ~mask  # bar where session just ended (first bar OUTSIDE, matching Pine's is_new-style edge)
    return start, end


def ffill_running_extreme(start_mask, active_mask, high, low):
    n = len(high)
    sess_high = np.full(n, np.nan)
    sess_low = np.full(n, np.nan)
    cur_h, cur_l = np.nan, np.nan
    for i in range(n):
        if start_mask[i]:
            cur_h, cur_l = high[i], low[i]
        elif active_mask[i]:
            cur_h = max(cur_h, high[i]) if not np.isnan(cur_h) else high[i]
            cur_l = min(cur_l, low[i]) if not np.isnan(cur_l) else low[i]
        sess_high[i] = cur_h
        sess_low[i] = cur_l
    return sess_high, sess_low


def cross(a, b):
    above = a > b
    above_prev = np.concatenate(([False], above[:-1]))
    valid = ~np.isnan(a) & ~np.isnan(b)
    valid_prev = np.concatenate(([False], valid[:-1]))
    up = above & ~above_prev & valid & valid_prev
    dn = (~above) & above_prev & valid & valid_prev
    return up, dn


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    in_asia = session_mask(b.hour, b.minute, 0, 0, 8, 0)
    in_uk = session_mask(b.hour, b.minute, 8, 0, 13, 30)
    in_us = session_mask(b.hour, b.minute, 13, 30, 20, 0)
    trade_window = in_uk | in_us

    asia_start, _ = session_start_end(in_asia)
    a_high, a_low = ffill_running_extreme(asia_start, in_asia, b.high, b.low)
    asia_range = a_high - a_low

    cross_up, _ = cross(b.close, a_high)
    _, cross_dn = cross(b.close, a_low)
    long_base = trade_window & cross_up
    short_base = trade_window & cross_dn

    _, us_end = session_start_end(in_us)

    grid = list(itertools.product(RR_TARGETS, MIN_RANGE_ATR_MULTS))

    def signal_fn(cfg):
        rr, min_range_mult = cfg
        min_range = min_range_mult * b.atr
        long_sig = long_base & (asia_range >= min_range)
        short_sig = short_base & (asia_range >= min_range)
        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        valid_l = ~np.isnan(a_low[il]) & (b.close[il] > a_low[il])
        valid_s = ~np.isnan(a_high[is_]) & (a_high[is_] > b.close[is_])
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = b.close[il] - a_low[il]
        dist_s = a_high[is_] - b.close[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        return sig_bar[order], sig_dir[order], sig_dist[order]

    def exit_fn(cfg):
        rr, min_range_mult = cfg
        return dict(target_r=rr, max_hold=2000, trail_atr=0.0, exit_long=us_end, exit_short=us_end)

    return C.full_evaluation(b, f"{symbol} M15 -- Asian Breakout AutoBot (RR_TARGET, MIN_ASIA_RANGE_ATR_MULT)",
                              grid, signal_fn, exit_fn, allowed=trade_window, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/asian_breakout_autobot_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
