"""
Liquidity-sweep + break-of-structure (BOS / CHoCH) REVERSAL search - the
ICT / "smart money concepts" idea, never tried before in this project, run
as a native search on SILVER and BTCUSD (M15, real native data).

MECHANISM (a reversal, distinct from H&S / trendline continuation breakouts
and from the Stochastic mean-reversion that already failed):
  * Major swing highs/lows = N_MAJOR-bar fractal pivots, used only once
    CONFIRMED (N_MAJOR bars after the pivot - common.pivots(), no lookahead).
    Minor structure = N_MINOR-bar fractal pivots, same confirmation rule.
  * Bearish case (mirror for bullish): price trades ABOVE the most recent
    confirmed, not-yet-taken major swing high (the resting buy-stop
    liquidity), but closes back BELOW that level either on the same bar or
    within the next 2 bars (a sweep / stop-hunt; a close that stays above for
    3 bars is a genuine breakout and is discarded). Sweep extreme = highest
    high during the sweep.
  * The "structure" to break = the most recent confirmed minor swing low at
    the moment of the sweep (the base of the leg that ran the stops). Once
    armed, if price CLOSES below it within N_MAJOR bars, before trading back
    above the sweep extreme, that is the BOS -> SHORT on that bar's close.
  * Stop = the sweep extreme (the liquidity grab's own high). Target =
    TARGET_R x stop distance. Max hold 96 M15 bars (1 day). Trades whose
    stop distance is under 0.25 ATR are skipped (fixed, not tuned).

GRID (declared before running, K = 24 per instrument):
  N_MAJOR in {8, 16, 32, 64}  x  N_MINOR in {2, 4}  x  TARGET_R in {1, 2, 3}
Selection = highest IS %PF with IS n >= 100. Everything else (sweep window,
BOS deadline, max hold, min stop) is fixed and was not varied.

SPLITS / cost / null / K correction: see common.py (Silver IS 2014-06 ->
2021-01, OOS 2021-01 -> 2026-09; BTC IS 2021-01 -> 2024-01, OOS 2024-01 ->
2026-09, chosen because BTC's 2018-2020 spread was 0.65-1.6% of price).
Point sizes read from each CSV header and asserted (SILVER 0.001, BTC 0.01).
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

N_MAJORS = [8, 16, 32, 64]
N_MINORS = [2, 4]
TARGET_RS = [1.0, 2.0, 3.0]
MAX_HOLD = 96
SWEEP_BACK_BARS = 2
MIN_STOP_ATR = 0.25


@C.njit(cache=True)
def sweep_bos_signals(h, l, c, atr, maj_ph, maj_pl, min_ph, min_pl, n_major, back_bars, min_stop_atr):
    n = len(c)
    sb = np.empty(n, np.int64); sd = np.empty(n); sdist = np.empty(n)
    cnt = 0
    sh = np.nan; sl = np.nan          # active major swing levels (untaken)
    last_minor_low = np.nan; last_minor_high = np.nan
    # pending sweep (closed beyond, waiting to come back inside)
    pend_s = -1; pend_s_lvl = 0.0; pend_s_ext = 0.0
    pend_b = -1; pend_b_lvl = 0.0; pend_b_ext = 0.0
    # armed BOS states
    arm_s = False; arm_s_ext = 0.0; arm_s_lvl = 0.0; arm_s_dead = 0
    arm_b = False; arm_b_ext = 0.0; arm_b_lvl = 0.0; arm_b_dead = 0
    for i in range(n):
        # structure confirmations available at bar i
        if not np.isnan(maj_ph[i]):
            sh = maj_ph[i]
        if not np.isnan(maj_pl[i]):
            sl = maj_pl[i]
        # --- bearish side: sweep of highs
        fire_s = False
        if arm_s:
            if h[i] > arm_s_ext:
                arm_s = False
            elif c[i] < arm_s_lvl:
                fire_s = True
                arm_s = False
            elif i > arm_s_dead:
                arm_s = False
        if pend_s >= 0:
            pend_s_ext = max(pend_s_ext, h[i])
            if c[i] < pend_s_lvl:
                if not np.isnan(last_minor_low) and last_minor_low < pend_s_lvl:
                    arm_s = True; arm_s_ext = pend_s_ext; arm_s_lvl = last_minor_low; arm_s_dead = i + n_major
                pend_s = -1
            elif i - pend_s >= back_bars:
                pend_s = -1
        if not np.isnan(sh) and h[i] > sh:
            lvl = sh
            sh = np.nan
            if c[i] < lvl:
                if not np.isnan(last_minor_low) and last_minor_low < lvl:
                    arm_s = True; arm_s_ext = h[i]; arm_s_lvl = last_minor_low; arm_s_dead = i + n_major
                    if c[i] < arm_s_lvl:        # sweep bar itself broke structure
                        fire_s = True; arm_s = False
            else:
                pend_s = i; pend_s_lvl = lvl; pend_s_ext = h[i]
        if fire_s and not np.isnan(atr[i]):
            dist = arm_s_ext - c[i]
            if dist >= min_stop_atr * atr[i]:
                sb[cnt] = i; sd[cnt] = -1.0; sdist[cnt] = dist; cnt += 1
        # --- bullish side: sweep of lows
        fire_b = False
        if arm_b:
            if l[i] < arm_b_ext:
                arm_b = False
            elif c[i] > arm_b_lvl:
                fire_b = True
                arm_b = False
            elif i > arm_b_dead:
                arm_b = False
        if pend_b >= 0:
            pend_b_ext = min(pend_b_ext, l[i])
            if c[i] > pend_b_lvl:
                if not np.isnan(last_minor_high) and last_minor_high > pend_b_lvl:
                    arm_b = True; arm_b_ext = pend_b_ext; arm_b_lvl = last_minor_high; arm_b_dead = i + n_major
                pend_b = -1
            elif i - pend_b >= back_bars:
                pend_b = -1
        if not np.isnan(sl) and l[i] < sl:
            lvl = sl
            sl = np.nan
            if c[i] > lvl:
                if not np.isnan(last_minor_high) and last_minor_high > lvl:
                    arm_b = True; arm_b_ext = l[i]; arm_b_lvl = last_minor_high; arm_b_dead = i + n_major
                    if c[i] > arm_b_lvl:
                        fire_b = True; arm_b = False
            else:
                pend_b = i; pend_b_lvl = lvl; pend_b_ext = l[i]
        if fire_b and not np.isnan(atr[i]):
            dist = c[i] - arm_b_ext
            if dist >= min_stop_atr * atr[i]:
                sb[cnt] = i; sd[cnt] = 1.0; sdist[cnt] = dist; cnt += 1
        # minor structure updates AFTER this bar's sweep logic (a pivot
        # confirmed on bar i is usable from bar i+1)
        if not np.isnan(min_pl[i]):
            last_minor_low = min_pl[i]
        if not np.isnan(min_ph[i]):
            last_minor_high = min_ph[i]
    return sb[:cnt], sd[:cnt], sdist[:cnt]


def run(symbol, log):
    df, point = C.load_m15(symbol)
    b = C.Bars(df, point, symbol)
    piv = {k: C.pivots(b.high, b.low, k) for k in set(N_MAJORS) | set(N_MINORS)}
    no_exit = np.zeros(b.n, dtype=np.bool_)

    def signal_fn(cfg):
        nmaj, nmin, _ = cfg
        return sweep_bos_signals(b.high, b.low, b.close, b.atr, piv[nmaj][0], piv[nmaj][1],
                                 piv[nmin][0], piv[nmin][1], nmaj, SWEEP_BACK_BARS, MIN_STOP_ATR)

    def exit_fn(cfg):
        return dict(target_r=cfg[2], max_hold=MAX_HOLD, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)

    grid = list(itertools.product(N_MAJORS, N_MINORS, TARGET_RS))
    return C.full_evaluation(b, f"{symbol} M15 -- liquidity sweep + BOS reversal (N_MAJOR, N_MINOR, TARGET_R)",
                             grid, signal_fn, exit_fn, min_is_n=100, log=log)


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/smc_sweep_bos_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
