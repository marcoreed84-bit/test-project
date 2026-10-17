"""
Entry-confirmation filter, per direct follow-up request: instead of
filling the trade one bar after the zone-cross (the existing
convention), require the cross to still HOLD (K still on the correct
side of D) for confirm_bars MORE closed bars before actually entering.
If the stochastic flips back before confirmation completes, the
signal is thrown away entirely - no trade taken. This directly targets
the "touch and reverse" pattern found in the stop-loss diagnosis (57%
of stopped trades never went profitable at all), where confirm_bars=0
(the existing construction) already fills one bar after the cross but
still catches a lot of one-bar fakeouts.

Entry/stop/target unchanged from the stop_trail file (swing stop,
1:2 R:R, real spread). Exit kept simple here (grace=0, immediate
opposite-cross exit + stop/target) so the entry filter's effect isn't
mixed up with the exit-grace effect already tested separately.

Tested confirm_bars in {0, 1, 2, 3} on BTCUSD M15 full real history.
Honest K: this project's BTC stochastic exploration today is now at
K=15 (11 before this file + 4 confirm_bars values here), all against
the SAME data, same day - a genuinely different idea each time, but
that doesn't reduce how many free looks the data has had.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import load_btc_m15, K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH, RR

TIME_CAP_BARS = 300


def build_trades(df, point, confirm_bars):
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
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 0
        if crossUp[i] and k[i] < ZONE_LOW:
            dir_ = 1
        elif crossDown[i] and k[i] > ZONE_HIGH:
            dir_ = -1
        if dir_ == 0:
            i += 1
            continue

        # confirmation: K must stay on the correct side of D for
        # confirm_bars MORE closed bars after the cross bar, or the
        # signal is discarded entirely (no trade)
        confirmed = True
        entry_i = i
        for c in range(1, confirm_bars + 1):
            ci = i + c
            if ci >= n or not valid[ci]:
                confirmed = False
                break
            still_holds = (k[ci] > d[ci]) if dir_ > 0 else (k[ci] < d[ci])
            if not still_holds:
                confirmed = False
                break
            entry_i = ci
        if not confirmed:
            i += 1
            continue

        swing = min(low[entry_i - SWING_BARS:entry_i]) if dir_ > 0 else max(high[entry_i - SWING_BARS:entry_i])
        risk = dir_ * (close[entry_i] - swing)
        if risk <= 0.0:
            i += 1
            continue
        fill_i = entry_i + 1
        if fill_i >= n:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
        stop_px = swing
        target_px = entry_px + dir_ * RR * risk
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

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
                opposite = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                if opposite:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-STOCH"
                    break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=entry_i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run(confirm_bars):
    df, point = load_btc_m15()
    n = len(df)
    print(f"\n{'#'*100}\nBTCUSD M15 - Stoch(21,5,5) entry + swing stop/1:2RR, requiring the cross to HOLD "
          f"{confirm_bars} more bar(s) before entering (else no trade)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point, confirm_bars)
    report(f"BTCUSD M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point, confirm_bars)
    report(f"BTCUSD M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point, confirm_bars)
    report(f"BTCUSD M15 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    for cb in (0, 1, 2, 3):
        run(cb)
    print(f"\n\n  Honest K: this project's BTC stochastic exploration today is now at K=15")
    print(f"  (11 before this file + 4 confirm_bars values here), all against the SAME")
    print(f"  data, same day.")
