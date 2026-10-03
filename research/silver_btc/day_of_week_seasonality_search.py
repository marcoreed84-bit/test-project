"""
Day-of-week calendar seasonality on BTC - a genuinely different criterion
from everything else tried in this project (56 prior constructions, all
either chart-pattern/indicator-based or single-asset time-series momentum).
This is a pure calendar effect: is there a systematically different return
on one weekday vs the others. Cited in two of tonight's literature sources
(Baur, Cahill, Godfrey & Liu 2019, "Bitcoin time-of-day, day-of-week and
month-of-year effects in returns and trading volume," Finance Research
Letters; Kaiser 2019, "Seasonality in cryptocurrencies," Finance Research
Letters) - both referenced in the neura/Parente&Rizzuti paper read earlier
tonight, neither independently verified here before now.

CONSTRUCTION: at the first bar of each UTC day, trade that day's FULL
return (open to close) long or short, ONLY on a single pre-specified
weekday - every other day, no trade. Pure calendar directional exposure,
no stop/target (oversized nominal stop, matching the same convention as
the intraday/weekly momentum tests tonight) - this is deliberately NOT
risk-managed, since the thing being tested is whether the calendar day
itself carries a real return bias, not whether a trading overlay can be
built around it.

GRID (K=14, literal, searched honestly - NOT cherry-picked from the
academic sources' claimed direction, since their exact finding couldn't be
retrieved from behind this environment's network block): WEEKDAY in
{Mon,Tue,Wed,Thu,Fri,Sat,Sun} x DIRECTION in {long, short}. Best IS %PF
frozen, evaluated once on untouched OOS, random-timing-null + K=14
correction - identical discipline to every other search in this folder.

Splits/cost/null: common.py. Run on BTCUSD (the subject of the cited
papers) plus GOLD/SILVER for context, though both have real weekend
closures BTC doesn't - a "Saturday effect" is structurally meaningless on
an instrument that doesn't trade Saturdays, so expect fewer/no signals on
those weekdays for Gold/Silver (not a bug).
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]   # Monday=0 .. Sunday=6 (pandas/python convention)
DIRECTIONS = [1.0, -1.0]
NOMINAL_STOP_ATR = 50.0


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    o, c, atr = b.open, b.close, b.atr

    date_of = b.date_id
    is_day_start = np.concatenate(([True], date_of[1:] != date_of[:-1]))
    day_start_bar = np.where(is_day_start)[0]
    # that day's own weekday and full-day return (open of first bar -> close of last bar before next day starts)
    day_end_bar = np.concatenate((day_start_bar[1:] - 1, [b.n - 1]))
    weekday_of_day = (df15["time"].dt.weekday.values)[day_start_bar]
    day_ret = c[day_end_bar] - o[day_start_bar]
    valid_day = ~np.isnan(atr[day_start_bar]) & (atr[day_start_bar] > 0) & (day_ret != 0)

    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        wd, direction = cfg
        keep = valid_day & (weekday_of_day == wd)
        bars_ = day_start_bar[keep].astype(np.int64)
        dirs = np.full(len(bars_), direction)
        dist = NOMINAL_STOP_ATR * atr[bars_]
        return bars_, dirs, dist

    def exit_fn(cfg):
        return dict(target_r=0.0, max_hold=96, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(WEEKDAYS, DIRECTIONS))
    return C.full_evaluation(b, f"{symbol} -- day-of-week seasonality (WEEKDAY 0=Mon..6=Sun, DIRECTION)",
                             grid, signal_fn, exit_fn, min_is_n=15, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/day_of_week_seasonality_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
