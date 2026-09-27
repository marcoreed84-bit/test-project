"""
ADX trend-strength filter + pullback-to-dynamic-trendline continuation
entry, on SILVER and BTCUSD (H1 resampled from real native M15). Web
sources on Silver describe "buy the pullback while the trendline holds,
only when trend strength (ADX) is high". Never tried in this project: every
earlier trend system here either entered on a cross/breakout event (EMA
cross, trendline break, H&S neckline, Aurelius/Meridian alignment) rather
than on a RETRACEMENT inside an established, strength-confirmed trend, or
used a slope proxy instead of Wilder's ADX/DI.

SIGNAL (long; short is the mirror):
  * Wilder ADX(14) >= ADX_THR and +DI > -DI on bar i (strong up-trend);
  * EMA(PB_EMA) rising (ema[i] > ema[i-5]) - the dynamic trendline slopes up;
  * pullback that holds: low[i] <= EMA(PB_EMA)[i] (price came back to the
    trendline) but close[i] > EMA(PB_EMA)[i] (the line held on the close);
  * stop = lowest low of bars i-4..i minus 0.25 x ATR (just under the
    pullback's own low - fixed, not tuned).
EXIT (EXIT_MODE): "2R" / "3R" = fixed R-multiple target on the structural
stop, max hold 120 H1 bars; "trail" = no target, chandelier trail at 3 x
ATR from the best close, same max hold. All self-contained, so random
entries go through the literal same exit (stop distances drawn from the
real OOS stop-distance distribution, in ATR units).

GRID (declared before running, K = 18 per instrument):
  ADX_THR in {20, 25, 30} x PB_EMA in {20, 50} x EXIT_MODE in {2R, 3R, trail}
ADX/DI period 14 and the 5-bar stop window are textbook defaults, fixed.

Splits / cost / null / K: see common.py.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

ADX_THRS = [20, 25, 30]
PB_EMAS = [20, 50]
EXIT_MODES = ["2R", "3R", "trail"]
MAX_HOLD = 120
STOP_WIN = 5
STOP_BUF_ATR = 0.25


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    df = C.resample(df15, "1h")
    b = C.Bars(df, point, symbol)
    adx, pdi, mdi = C.wilder_adx(b.high, b.low, b.close, 14)
    emas = {p: C.ema(b.close, p) for p in PB_EMAS}
    import pandas as pd
    ll = pd.Series(b.low).rolling(STOP_WIN, min_periods=STOP_WIN).min().values
    hh = pd.Series(b.high).rolling(STOP_WIN, min_periods=STOP_WIN).max().values
    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        thr, pe, _ = cfg
        e = emas[pe]
        e5 = np.concatenate((np.full(5, np.nan), e[:-5]))
        strong = adx >= thr
        L = strong & (pdi > mdi) & (e > e5) & (b.low <= e) & (b.close > e)
        S = strong & (mdi > pdi) & (e < e5) & (b.high >= e) & (b.close < e)
        L &= ~np.isnan(b.atr); S &= ~np.isnan(b.atr)
        il = np.where(L)[0]; is_ = np.where(S)[0]
        dl = b.close[il] - (ll[il] - STOP_BUF_ATR * b.atr[il])
        ds = (hh[is_] + STOP_BUF_ATR * b.atr[is_]) - b.close[is_]
        bars_ = np.concatenate((il, is_)); dirs = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        dist = np.concatenate((dl, ds))
        o = np.argsort(bars_, kind="stable")
        return bars_[o].astype(np.int64), dirs[o], dist[o]

    def exit_fn(cfg):
        m = cfg[2]
        if m == "trail":
            return dict(target_r=0.0, max_hold=MAX_HOLD, trail_atr=3.0, exit_long=no_exit, exit_short=no_exit)
        return dict(target_r=float(m[0]), max_hold=MAX_HOLD, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(ADX_THRS, PB_EMAS, EXIT_MODES))
    return C.full_evaluation(b, f"{symbol} H1 -- ADX-gated pullback-to-EMA continuation (ADX_THR, PB_EMA, EXIT)",
                             grid, signal_fn, exit_fn, min_is_n=100, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/adx_pullback_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
