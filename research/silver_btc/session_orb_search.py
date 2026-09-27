"""
Session opening-range breakout (ORB) search on SILVER and BTCUSD, M15 real
native data. A TIME-OF-DAY mechanism - nothing in this project so far has
conditioned on the clock (every earlier system fires whenever its price
pattern appears). The idea: liquidity/information arrives at specific
session opens (Asia open, London open, NY/COMEX or US-equity open), the
first 30-60 minutes set a range, and the first decisive break of that
range carries in its direction for the rest of the day.

SERVER TIME: this broker's gold/silver quotes open at 01:00 server time
(= 23:00 UTC), i.e. the usual GMT+2 / GMT+3 (DST) MT5 server clock. Session
hours below are in SERVER time and were picked from that convention, not
from the data:
  SILVER: 01:00 (Asia open), 10:00 (London open), 15:15 (COMEX open, 08:20 NY)
  BTCUSD: 00:00 (server day roll), 10:00 (London), 16:30 (US equity open,
          09:30 NY - BTC's most-cited intraday liquidity event)
(US/EU DST switch-date mismatch shifts the NY opens by 1h for ~3 weeks a
year - ignored, not corrected, same for the real EA would-be.)

SIGNAL: range = high/low of the first RANGE_BARS M15 bars from the session
start (same calendar day). After the range completes, the FIRST close
outside it (before 23:00 server) triggers one trade per session per day in
the break direction. Stop = the opposite side of the range (structural);
trades with stop < 0.25 ATR skipped (fixed). EXIT: TARGET in {1R, 2R} or
"EOD" (no target); every trade is flat at the day's 23:45 bar close at the
latest (exit array, self-contained). The random null is restricted
(`allowed` mask) to the same intraday window the real system can trade in
(from range end to 23:00), so it isn't handed overnight/illiquid bars the
system never touches.

GRID (declared before running, K = 18 per instrument):
  SESSION (3 per instrument) x RANGE_BARS in {2, 4} x TARGET in {1R, 2R, EOD}

Splits / cost / null / K: see common.py. Point from CSV header.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

SESSIONS = {"SILVER": [(1, 0), (10, 0), (15, 15)], "BTCUSD": [(0, 0), (10, 0), (16, 30)]}
RANGE_BARS = [2, 4]
TARGETS = [1.0, 2.0, 0.0]   # 0.0 = EOD
LAST_ENTRY_HOUR = 23
MIN_STOP_ATR = 0.25


@C.njit(cache=True)
def orb_signals(h, l, c, atr, date_id, hour, minute, sh, sm, nbars, last_hour, min_stop_atr):
    n = len(c)
    sb = np.empty(n, np.int64); sd = np.empty(n); sdist = np.empty(n)
    cnt = 0
    cur_day = -1; state = 0  # 0 waiting for session start, 1 building range, 2 armed, 3 done
    rh = 0.0; rl = 0.0; built = 0
    for i in range(n):
        if date_id[i] != cur_day:
            cur_day = date_id[i]; state = 0
        if state == 0:
            if hour[i] == sh and minute[i] == sm:
                state = 1; rh = h[i]; rl = l[i]; built = 1
                if built >= nbars:
                    state = 2
                continue
            if hour[i] * 60 + minute[i] > sh * 60 + sm:
                state = 3      # session bar missing (holiday / data gap) -> skip day
            continue
        if state == 1:
            rh = max(rh, h[i]); rl = min(rl, l[i]); built += 1
            if built >= nbars:
                state = 2
            continue
        if state == 2:
            if hour[i] >= last_hour or np.isnan(atr[i]):
                if hour[i] >= last_hour:
                    state = 3
                continue
            if c[i] > rh:
                d = c[i] - rl
                if d >= min_stop_atr * atr[i]:
                    sb[cnt] = i; sd[cnt] = 1.0; sdist[cnt] = d; cnt += 1
                state = 3
            elif c[i] < rl:
                d = rh - c[i]
                if d >= min_stop_atr * atr[i]:
                    sb[cnt] = i; sd[cnt] = -1.0; sdist[cnt] = d; cnt += 1
                state = 3
    return sb[:cnt], sd[:cnt], sdist[:cnt]


def run(symbol, log):
    df, point = C.load_m15(symbol)
    b = C.Bars(df, point, symbol)
    eod = (b.hour == 23) & (b.minute == 45)
    # also flatten on the last bar of any day that closes early (next bar is a new date)
    nxt_new_day = np.concatenate((b.date_id[1:] != b.date_id[:-1], [True]))
    eod = (eod | nxt_new_day).astype(np.bool_)
    tod = b.hour * 60 + b.minute
    results = []
    grid = list(itertools.product(SESSIONS[symbol], RANGE_BARS, TARGETS))

    def signal_fn(cfg):
        (sh, sm), nb, _ = cfg
        return orb_signals(b.high, b.low, b.close, b.atr, b.date_id, b.hour, b.minute, sh, sm, nb,
                           LAST_ENTRY_HOUR, MIN_STOP_ATR)

    def exit_fn(cfg):
        return dict(target_r=cfg[2], max_hold=200, trail_atr=0.0, exit_long=eod, exit_short=eod)

    # The random null's allowed window depends on the frozen config's session/range; full_evaluation
    # takes one mask, so build it for every session and pass the union-of-one via a small wrapper:
    # evaluate once to learn the winner, then re-run with the winner's own mask. The second call
    # repeats the identical IS selection (deterministic) - it is NOT a second search.
    probe = C.full_evaluation(b, f"[probe for winner's session window - identical IS selection] {symbol}",
                              grid, signal_fn, exit_fn, min_is_n=100, log=lambda s: None)
    if "cfg" not in probe:
        log(f"{symbol}: no valid IS combo"); return probe
    (sh, sm), nb, _ = probe["cfg"]
    start = sh * 60 + sm + 15 * nb
    allowed = ((tod >= start) & (b.hour < LAST_ENTRY_HOUR)).astype(np.bool_)
    return C.full_evaluation(b, f"{symbol} M15 -- session opening-range breakout (SESSION, RANGE_BARS, TARGET[0=EOD]) "
                                f"[null restricted to {start // 60:02d}:{start % 60:02d}-{LAST_ENTRY_HOUR}:00 server]",
                             grid, signal_fn, exit_fn, min_is_n=100, allowed=allowed, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/session_orb_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
