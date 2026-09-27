"""
"Liquidity Entry Zones" - the user's third pasted script in this batch
(42KB, almost entirely visual/panel code - this port extracts the actual
tradeable core). A third distinct liquidity-sweep-reversal construction
this session (after "ICT Daily Liquidity Sweep" and "Liquidity Sweep
Reversal Strategy", both already tested and failed): maintain the last
storedLevels(=20) confirmed pivot highs/lows; on each bar, search that
list NEWEST-FIRST for the most recent level swept by the CURRENT bar's
high/low by at least minSweepDistance; if the sweep candle also reclaims
(closes back inside, default rule), and passes wick%/body%/range quality
filters, it becomes a PENDING sweep. Within confirmationWindow(=2) bars
after a pending sweep, the first bar whose close is bullish/bearish AND
on the correct side of the local EMA(50) AND beyond the ORIGINAL sweep
candle's own midline confirms the trade. A signalCooldownBars(=10)
cooldown applies between accepted signals.

PORTED FAITHFULLY (including two real quirks, not silently fixed):
(1) a NEW valid sweep unconditionally OVERWRITES any still-pending sweep
of the same direction (the original never checks "is one already
pending" before overwriting pendingBull*/pendingBear* state) - same
precedent as this session's other "reproduce the real state-machine
quirk" ports; (2) despite computing and storing the swept level's price
(pendingBullLevel/pendingBearLevel) for the on-chart labels, the ACTUAL
stop-loss/take-profit in strategy.exit use FIXED distances from the
entry close (takeProfitPips/stopLossPips), NOT the swept level at all -
so the swept-level values only affect labeling/scoring, never risk
placement, and are correctly omitted here.

DISCLOSED RESCALING: takeProfitPips=2000/stopLossPips=500 (a fixed 4:1
R:R) use a "pip size" that auto-detects per instrument (XAUUSD->0.01,
forex->0.0001, else->syminfo.mintick) - a scale this project's Silver/
BTC data can only approximate via their own point sizes (0.001 / 0.01).
Rather than trust that approximation for risk sizing, the fixed-pip
stop/target are converted to ATR multiples (STOP_ATR_MULT, TP_R_MULT),
same convention as every other raw-point-scaled script this session.
minSweepDistance/minCandleRangePips keep their own pip-size resolution
per instrument (GOLD->0.01, SILVER/BTCUSD->their own point size) since
those only gate which sweeps qualify, not position risk.

GRID (K=27, literal): MIN_WICK_PCT in {0.25,0.35,0.50} (this one re-runs
the full sweep/confirmation state machine, since it changes which bars
qualify) x STOP_ATR_MULT in {1.0,2.0,3.0} x TP_R_MULT in {2.0,4.0,6.0}
(script's own 4:1 ratio is the middle cell). pivotLength=5, storedLevels
=20, confirmationWindow=2, signalCooldownBars=10, maxBodyPercent=0.65,
minCandleRangePips=20, EMA(50) trend filter ON, reclaimRule="Close Back
Inside", requireMidlineBreak=true, requireBullish/BearishBody=true are
the script's own defaults, fixed to keep K honest.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

MIN_WICK_PCTS = [0.25, 0.35, 0.50]
STOP_ATR_MULTS = [1.0, 2.0, 3.0]
TP_R_MULTS = [2.0, 4.0, 6.0]
PIVOT_LEN = 5
STORED_LEVELS = 20
CONFIRMATION_WINDOW = 2
SIGNAL_COOLDOWN_BARS = 10
MAX_BODY_PCT = 0.65
MIN_CANDLE_RANGE_PIPS = 20
MIN_SWEEP_DISTANCE_PIPS = 30
EMA_LEN = 50
PIP_SIZE = {"GOLD": 0.01, "SILVER": 0.001, "BTCUSD": 0.01}


def compute_signals(symbol, b, ph, pl, ema, min_wick_pct):
    n = b.n
    pip = PIP_SIZE[symbol]
    min_sweep_px = MIN_SWEEP_DISTANCE_PIPS * pip
    min_range_px = MIN_CANDLE_RANGE_PIPS * pip

    candle_range = b.high - b.low
    body = np.abs(b.close - b.open)
    upper_wick = b.high - np.maximum(b.open, b.close)
    lower_wick = np.minimum(b.open, b.close) - b.low
    with np.errstate(invalid="ignore", divide="ignore"):
        body_pct = np.where(candle_range > 0, body / candle_range, 0.0)
        upper_wick_pct = np.where(candle_range > 0, upper_wick / candle_range, 0.0)
        lower_wick_pct = np.where(candle_range > 0, lower_wick / candle_range, 0.0)

    buy_signal = np.zeros(n, dtype=np.bool_)
    sell_signal = np.zeros(n, dtype=np.bool_)

    stored_high_levels, stored_high_bars = [], []
    stored_low_levels, stored_low_bars = [], []
    pending_bull_bar, pending_bull_mid = None, None
    pending_bear_bar, pending_bear_mid = None, None
    last_signal_bar = None

    for i in range(n):
        if not np.isnan(ph[i]):
            stored_high_levels.append(ph[i]); stored_high_bars.append(i - PIVOT_LEN)
            if len(stored_high_levels) > STORED_LEVELS:
                stored_high_levels.pop(0); stored_high_bars.pop(0)
        if not np.isnan(pl[i]):
            stored_low_levels.append(pl[i]); stored_low_bars.append(i - PIVOT_LEN)
            if len(stored_low_levels) > STORED_LEVELS:
                stored_low_levels.pop(0); stored_low_bars.pop(0)

        hi, lo, cl, op = b.high[i], b.low[i], b.close[i], b.open[i]

        swept_high = np.nan
        for k in range(len(stored_high_levels) - 1, -1, -1):
            level, bar_ = stored_high_levels[k], stored_high_bars[k]
            if bar_ < i and hi > level and (hi - level) >= min_sweep_px:
                swept_high = level
                break
        swept_low = np.nan
        for k in range(len(stored_low_levels) - 1, -1, -1):
            level, bar_ = stored_low_levels[k], stored_low_bars[k]
            if bar_ < i and lo < level and (level - lo) >= min_sweep_px:
                swept_low = level
                break

        bearish_reclaim = (not np.isnan(swept_high)) and (cl < swept_high)
        bullish_reclaim = (not np.isnan(swept_low)) and (cl > swept_low)
        valid_sell_sweep = (bearish_reclaim and upper_wick_pct[i] >= min_wick_pct
                            and body_pct[i] <= MAX_BODY_PCT and candle_range[i] >= min_range_px)
        valid_buy_sweep = (bullish_reclaim and lower_wick_pct[i] >= min_wick_pct
                           and body_pct[i] <= MAX_BODY_PCT and candle_range[i] >= min_range_px)

        if valid_buy_sweep:
            pending_bull_bar, pending_bull_mid = i, (hi + lo) / 2.0
        if valid_sell_sweep:
            pending_bear_bar, pending_bear_mid = i, (hi + lo) / 2.0

        bull_window_open = pending_bull_bar is not None and (i - pending_bull_bar <= CONFIRMATION_WINDOW)
        bear_window_open = pending_bear_bar is not None and (i - pending_bear_bar <= CONFIRMATION_WINDOW)

        bull_body_ok = cl > op
        bear_body_ok = cl < op
        local_long_ok = (not np.isnan(ema[i])) and cl > ema[i]
        local_short_ok = (not np.isnan(ema[i])) and cl < ema[i]
        bull_mid_ok = pending_bull_mid is not None and cl > pending_bull_mid
        bear_mid_ok = pending_bear_mid is not None and cl < pending_bear_mid

        buy_confirmed = bull_window_open and bull_body_ok and local_long_ok and bull_mid_ok
        sell_confirmed = bear_window_open and bear_body_ok and local_short_ok and bear_mid_ok

        cooldown_passed = (last_signal_bar is None) or (i - last_signal_bar > SIGNAL_COOLDOWN_BARS)
        buy_sig = buy_confirmed and cooldown_passed
        sell_sig = sell_confirmed and cooldown_passed and not buy_sig

        if buy_sig or sell_sig:
            last_signal_bar = i

        if buy_sig or (pending_bull_bar is not None and i - pending_bull_bar > CONFIRMATION_WINDOW):
            pending_bull_bar, pending_bull_mid = None, None
        if sell_sig or (pending_bear_bar is not None and i - pending_bear_bar > CONFIRMATION_WINDOW):
            pending_bear_bar, pending_bear_mid = None, None

        buy_signal[i] = buy_sig
        sell_signal[i] = sell_sig

    return buy_signal, sell_signal


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    ph, pl = C.pivots(b.high, b.low, PIVOT_LEN)
    ema = C.ema(b.close, EMA_LEN)

    sig_cache = {mwp: compute_signals(symbol, b, ph, pl, ema, mwp) for mwp in MIN_WICK_PCTS}

    grid = list(itertools.product(MIN_WICK_PCTS, STOP_ATR_MULTS, TP_R_MULTS))

    def signal_fn(cfg):
        mwp, stop_mult, tp_r = cfg
        buy_signal, sell_signal = sig_cache[mwp]
        il = np.where(buy_signal)[0]
        is_ = np.where(sell_signal)[0]
        valid_l = ~np.isnan(b.atr[il]) & (b.atr[il] > 0)
        valid_s = ~np.isnan(b.atr[is_]) & (b.atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = stop_mult * b.atr[il]
        dist_s = stop_mult * b.atr[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        return sig_bar[order], sig_dir[order], sig_dist[order]

    def exit_fn(cfg):
        mwp, stop_mult, tp_r = cfg
        no_exit = np.zeros(b.n, dtype=np.bool_)
        return dict(target_r=tp_r, max_hold=2000, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    return C.full_evaluation(b, f"{symbol} M15 -- Liquidity Entry Zones (MIN_WICK_PCT, STOP_ATR_MULT, TP_R_MULT)",
                              grid, signal_fn, exit_fn, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/liquidity_entry_zones_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
