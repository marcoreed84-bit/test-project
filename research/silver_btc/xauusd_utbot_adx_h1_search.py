"""
"XAUUSD 15m - 200 EMA (1h) + UT Bot + ADX Strategy" (r2keymoneymind) - the
user's second pasted script in this batch, EXPLICITLY tuned/named for
XAUUSD on M15 (the exact instrument/timeframe of this project's own GOLD
M15 data - honored as this file's primary test, Silver/BTC run for
comparison as always). Long-only: UT Bot bullish flip (a DIFFERENT
recursive-stop variant from the plain "UT Bot v2" script just tested -
this one seeds xTrailingStop from max(close-nLoss,0) and reads pos off
xTrailingStop[1], not the crossover primitive) + price above a 1-Hour
200 EMA (via request.security, lookahead=off) + ADX(14)>threshold, fixed
percent-of-price TP/SL (not ATR-relative).

PORTED FAITHFULLY: the exact xTrailingStop recursion as written (bar
loop, self-referential), the pos-flip definition of utBotBuy (requires
BOTH close crossing above xTrailingStop[1] on this bar AND pos[1]==-1 -
i.e. the previous confirmed position must have been short, not just
"any bullish flip" - a real extra constraint vs the plain UT Bot script),
Wilder ADX/DI (common.wilder_adx, matching ta.dmi with diLen=adxLen=14),
the 1H EMA(200) with the SAME previous-completed-bar HTF convention
already used for two other scripts this session (Ichimoku's Daily filter,
ICT's previous-day levels) - matches request.security's lookahead=off
semantics for an LTF chart, and the fixed-percent TP/SL (tp_pct of close
as the target distance, sl_pct of close as the stop distance - NOT ATR-
scaled, ported as literal percent-of-price since that's what the script
computes). Position-sizing (percent_of_equity) and the dashboard table
are dropped as usual.

GRID (K=27, literal): ADX_THRESH in {20,25,30} x TP_PCT in {1.0,1.5,2.0}
x SL_PCT in {0.5,1.0,1.5}. keyValue=2.0, atrPeriod=1, diLen=adxLen=14,
emaPeriod=200, htfTime=1H are the script's own defaults, fixed to keep K
honest. Long-only by construction (script defines no short side).
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

ADX_THRESHS = [20.0, 25.0, 30.0]
TP_PCTS = [1.0, 1.5, 2.0]
SL_PCTS = [0.5, 1.0, 1.5]
KEY_VALUE = 2.0
ATR_PERIOD = 1
ADX_LEN = 14
EMA_PERIOD = 200


def compute_ut_pos(close, atr, key_value):
    n = len(close)
    nloss = key_value * atr
    xts = np.maximum(close - nloss, 0.0)
    pos = np.zeros(n, dtype=np.int64)
    for i in range(1, n):
        prev_xts = xts[i - 1]
        if close[i - 1] > prev_xts and close[i] > prev_xts:
            xts[i] = max(prev_xts, close[i] - nloss[i])
        elif close[i - 1] < prev_xts and close[i] < prev_xts:
            xts[i] = min(prev_xts, close[i] + nloss[i])
        else:
            xts[i] = close[i] - nloss[i] if close[i] > prev_xts else close[i] + nloss[i]
        if close[i] > xts[i - 1] and close[i - 1] <= xts[i - 1]:
            pos[i] = 1
        elif close[i] < xts[i - 1] and close[i - 1] >= xts[i - 1]:
            pos[i] = -1
        else:
            pos[i] = pos[i - 1]
    return pos


def build_htf_ema_filter(df15, b):
    df1h = C.resample(df15, "1h")
    ema1h = C.ema(df1h["close"].values, EMA_PERIOD)
    h1_starts = pd.to_datetime(df1h["time"]).values
    ema_series = pd.Series(ema1h, index=h1_starts).shift(1)  # only the previous CLOSED 1h bar is visible
    m15_floor = pd.to_datetime(b.time).floor("1h")
    htf_ema = ema_series.reindex(m15_floor).values
    return htf_ema


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    atr1 = C.wilder_atr(b.high, b.low, b.close, ATR_PERIOD)
    atr1_filled = np.nan_to_num(atr1, nan=0.0)
    pos = compute_ut_pos(b.close, atr1_filled, KEY_VALUE)
    pos_prev = np.concatenate(([0], pos[:-1]))
    ut_buy = (pos == 1) & (pos_prev == -1)

    adx, pdi, mdi = C.wilder_adx(b.high, b.low, b.close, ADX_LEN)
    htf_ema = build_htf_ema_filter(df15, b)
    htf_bull = b.close > htf_ema

    with np.errstate(invalid="ignore"):
        buy_condition = ut_buy & htf_bull & (adx > 0)  # base mask; threshold applied per-cfg below

    grid = list(itertools.product(ADX_THRESHS, TP_PCTS, SL_PCTS))

    def signal_fn(cfg):
        adx_th, tp_pct, sl_pct = cfg
        with np.errstate(invalid="ignore"):
            sig = ut_buy & htf_bull & (adx > adx_th)
        il = np.where(sig)[0]
        valid = ~np.isnan(b.close[il])
        il = il[valid]
        dist_l = (sl_pct / 100.0) * b.close[il]
        return il.astype(np.int64), np.ones(len(il)), dist_l

    def exit_fn(cfg):
        adx_th, tp_pct, sl_pct = cfg
        target_r = (tp_pct / 100.0) / (sl_pct / 100.0)
        no_exit = np.zeros(b.n, dtype=np.bool_)
        return dict(target_r=target_r, max_hold=2000, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    return C.full_evaluation(b, f"{symbol} M15 -- XAUUSD UT Bot+ADX+1H EMA200, long-only (ADX_THRESH, TP_PCT, SL_PCT)",
                              grid, signal_fn, exit_fn, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/xauusd_utbot_adx_h1_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
