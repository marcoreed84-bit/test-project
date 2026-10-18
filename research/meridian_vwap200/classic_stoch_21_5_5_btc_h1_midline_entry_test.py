"""
Genuinely new entry idea, per direct request from a live chart: instead
of requiring the %K/%D cross to happen in the deep 20/80 zone, take a
cross that happens back through the 50 MIDLINE after a pullback that
reached down to (or up to) 50 but not all the way to the extreme zone -
the user's observed pattern being that these "failed deep retest,
crosses back through 50 with momentum" moves tend to run hard.

Rule: a BUY fires when %K crosses UP through %D while %K is in a band
around 50 (MIDLINE_BAND_LOW to MIDLINE_BAND_HIGH), PROVIDED %K had
dipped to <=50 at some point in the preceding PRIOR_DIP_LOOKBACK bars
(confirming this is a genuine pullback-and-reversal through the
middle, not just noise sitting near 50). SELL is the mirror. This is
an ADDITIONAL entry type, tested on its own (not combined with the
existing zone-cross entry), same stop (swing)/target (1:2 R:R)/exit
(same-stoch opposite cross with grace=10 trail) as every other file
tonight.

Tested MIDLINE_BAND = (40,60) with PRIOR_DIP_LOOKBACK in {5, 10, 20}
on BTCUSD H1 full real history, real spread.

Honest K: 1 per lookback value - this is a genuinely NEW entry
construction, not a filter/tweak on the already-tested zone-cross
entry (that line is separately at K=35 after tonight's filters).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, RR
from classic_stoch_21_5_5_btc_h1_test import load_btc_h1

TIME_CAP_BARS = 300
GRACE_BARS = 10
MIDLINE_BAND_LOW, MIDLINE_BAND_HIGH = 40.0, 60.0


def build_trades(df, point, prior_dip_lookback):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + prior_dip_lookback + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue

        dir_ = 0
        in_band = MIDLINE_BAND_LOW <= k[i] <= MIDLINE_BAND_HIGH
        if in_band and crossUp[i]:
            window = [w for w in k[i - prior_dip_lookback:i] if not np.isnan(w)]
            if window and min(window) <= 50.0:
                dir_ = 1
        elif in_band and crossDown[i]:
            window = [w for w in k[i - prior_dip_lookback:i] if not np.isnan(w)]
            if window and max(window) >= 50.0:
                dir_ = -1
        if dir_ == 0:
            i += 1
            continue

        swing = min(low[i - SWING_BARS:i]) if dir_ > 0 else max(high[i - SWING_BARS:i])
        risk = dir_ * (close[i] - swing)
        if risk <= 0.0:
            i += 1
            continue
        fill_i = i + 1
        if fill_i >= n:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
        stop_px = swing
        target_px = entry_px + dir_ * RR * risk
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

        pending_exit_bar = None
        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if dir_ > 0 else (high[j] >= stop_px)
            target_hit = (high[j] >= target_px) if dir_ > 0 else (low[j] <= target_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if target_hit:
                exit_i, exit_px, reason = j, target_px, "TARGET"
                break
            if valid[j] and valid[j - 1]:
                favorable = (dir_ > 0 and crossUp[j]) or (dir_ < 0 and crossDown[j])
                opposite  = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                if pending_exit_bar is not None and favorable:
                    new_swing = min(low[j - SWING_BARS:j]) if dir_ > 0 else max(high[j - SWING_BARS:j])
                    if dir_ > 0 and new_swing > stop_px:
                        stop_px = new_swing
                    elif dir_ < 0 and new_swing < stop_px:
                        stop_px = new_swing
                    pending_exit_bar = None
                if pending_exit_bar is None and opposite:
                    pending_exit_bar = j + GRACE_BARS
                if pending_exit_bar is not None and j >= pending_exit_bar:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-STOCH-GRACE"
                    break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run(prior_dip_lookback):
    df, point = load_btc_h1()
    n = len(df)
    print(f"\n{'#'*100}\nBTCUSD H1 - MIDLINE-CROSS entry (band {MIDLINE_BAND_LOW}-{MIDLINE_BAND_HIGH}, prior dip/rise "
          f"to 50 within {prior_dip_lookback} bars) + swing stop/1:2RR + grace=10 trail\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point, prior_dip_lookback)
    report(f"BTCUSD H1 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point, prior_dip_lookback)
    report(f"BTCUSD H1 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point, prior_dip_lookback)
    report(f"BTCUSD H1 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    for pdl in (5, 10, 20):
        run(pdl)
    print(f"\n\n  Honest K: 1 per lookback value - NEW entry construction (midline cross after")
    print(f"  a pullback to 50), separate line from the zone-cross construction's K=35.")
