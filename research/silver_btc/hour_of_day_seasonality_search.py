"""
Hour-of-day seasonality on BTC - distinct from the day-of-week test already
run (day_of_week_seasonality_search.py, DOES NOT SURVIVE): this asks
whether a specific UTC HOUR of the day carries a systematic directional
bias (e.g. a liquidity-driven effect around Asia/Europe/US session opens),
also part of the Baur et al. (2019) "time-of-day" finding cited alongside
day-of-week in that paper's title.

CONSTRUCTION: at the first bar of each UTC hour, trade that HOUR's full
return (open of :00 bar -> close of :45 bar, 4 M15 bars), long or short,
ONLY on one pre-specified UTC hour - every other hour, no trade. Pure
calendar directional exposure, no stop/target (oversized nominal stop,
same convention as every other calendar/momentum test tonight).

GRID (K=48, literal, honestly searched): HOUR in {0..23} x DIRECTION in
{long, short}. Best IS %PF frozen, evaluated once on untouched OOS,
random-timing null + K=48 correction.

Splits/cost/null: common.py. BTCUSD only - an hour-of-day effect tied to
TradFi session opens (Asia/Europe/US) is a claim specifically about BTC's
documented behavior around those windows, not something to blindly port to
Gold/Silver, which already HAVE their own session structure baked into
when they trade at all (most of this grid's hours wouldn't even have data
for a session-limited instrument).
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

HOURS = list(range(24))
DIRECTIONS = [1.0, -1.0]
NOMINAL_STOP_ATR = 50.0


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    o, c, atr = b.open, b.close, b.atr
    hour, minute = b.hour, b.minute

    hour_start_bar = np.where(minute == 0)[0]
    # that hour's own return: open of :00 bar -> close of the LAST bar before the next hour starts
    next_start = np.concatenate((hour_start_bar[1:], [b.n]))
    hour_end_bar = next_start - 1
    valid_pair = (hour_end_bar > hour_start_bar) | (hour_end_bar == hour_start_bar)
    hour_start_bar = hour_start_bar[valid_pair]
    hour_end_bar = hour_end_bar[valid_pair]
    hour_of_hour = hour[hour_start_bar]
    hour_ret = c[hour_end_bar] - o[hour_start_bar]
    valid = ~np.isnan(atr[hour_start_bar]) & (atr[hour_start_bar] > 0) & (hour_ret != 0)

    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        h, direction = cfg
        keep = valid & (hour_of_hour == h)
        bars_ = hour_start_bar[keep].astype(np.int64)
        dirs = np.full(len(bars_), direction)
        dist = NOMINAL_STOP_ATR * atr[bars_]
        return bars_, dirs, dist

    def exit_fn(cfg):
        return dict(target_r=0.0, max_hold=4, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(HOURS, DIRECTIONS))
    return C.full_evaluation(b, f"{symbol} -- hour-of-day seasonality (HOUR UTC 0-23, DIRECTION)",
                             grid, signal_fn, exit_fn, min_is_n=50, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/hour_of_day_seasonality_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    result = run("BTCUSD", log)
    log("\nSUMMARY")
    log(f"  {result}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
