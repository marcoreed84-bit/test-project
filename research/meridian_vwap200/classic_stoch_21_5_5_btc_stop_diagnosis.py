"""
Diagnostic (not a new construction - explains the already-reported
grace=0 stop-loss result), per direct request: of the trades that hit
their stop, how many were EVER in unrealized profit first (favorable
excursion before reversing), and - at the point price turned against
the trade - was that reversal happening near a common moving
average/VWAP (a real, explainable "bounce" level) or did price just
keep running further into an already-overextended move with nothing
nearby to explain the turn?

Method: replay every STOP-exit trade from the grace=0 construction bar
by bar, track the best unrealized price reached before the stop (MFE -
maximum favorable excursion), and at the bar where price reached that
MFE peak, measure its distance (in ATR) to EMA21/50/200 and session
VWAP. "Near an MA/VWAP" = within 0.5x ATR of at least one of them at
the MFE peak - a real, pre-defined threshold, not picked after looking
at the data.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import load_btc_m15, K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH, RR
from vwap_open_scenarios_test import ema, session_vwap, wilder_atr

TIME_CAP_BARS = 300
NEAR_ATR_MULT = 0.5


def build_trades_with_mfe(df, point):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    m21 = ema(close_a, 21)
    m50 = ema(close_a, 50)
    m200 = ema(close_a, 200)
    vwap = session_vwap(df)
    atr = wilder_atr(high_a, low_a, close_a, 14)

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
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 210  # +210 so m200/atr are warm
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

        exit_i, exit_px, reason = None, None, None
        best_favorable = 0.0   # best unrealized pnl_pct reached during the trade
        best_j = fill_i
        for j in range(fill_i + 1, hard_limit + 1):
            # unrealized excursion using this bar's favorable extreme (high for
            # a long, low for a short) - the best price actually touched
            fav_px = high[j] if dir_ > 0 else low[j]
            fav_pct = ((fav_px - entry_px) / entry_px) * dir_
            if fav_pct > best_favorable:
                best_favorable = fav_pct
                best_j = j

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

        # at the MFE peak bar, how close was price to EMA21/50/200/VWAP, in ATR?
        near_ma = False
        if not np.isnan(atr[best_j]) and atr[best_j] > 0:
            dists = []
            for ref in (m21[best_j], m50[best_j], m200[best_j], vwap[best_j]):
                if not np.isnan(ref):
                    dists.append(abs(close[best_j] - ref) / atr[best_j])
            if dists and min(dists) <= NEAR_ATR_MULT:
                near_ma = True

        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_, reason=reason,
                             best_favorable=best_favorable, near_ma_at_peak=near_ma))
        i = exit_i + 1

    return results


def run():
    df, point = load_btc_m15()
    res = build_trades_with_mfe(df, point)
    stops = [r for r in res if r["reason"] == "STOP"]
    print(f"Total trades: {len(res)}")
    print(f"STOP-exit trades: {len(stops)} ({100*len(stops)/len(res):.1f}% of all trades)")
    print()

    ever_profitable = [r for r in stops if r["best_favorable"] > 0.0]
    print(f"Of the {len(stops)} STOP-exit trades:")
    print(f"  Were EVER in unrealized profit before stopping out: {len(ever_profitable)} "
          f"({100*len(ever_profitable)/len(stops):.1f}%)")
    print(f"  NEVER saw a positive price (straight to the stop):   {len(stops)-len(ever_profitable)} "
          f"({100*(len(stops)-len(ever_profitable))/len(stops):.1f}%)")
    print()

    mfe_vals = [r["best_favorable"] for r in stops]
    print(f"  Median best unrealized gain before the eventual stop: {100*np.median(mfe_vals):.3f}%")
    print(f"  Mean best unrealized gain before the eventual stop:   {100*np.mean(mfe_vals):.3f}%")
    print(f"  90th percentile best unrealized gain:                 {100*np.percentile(mfe_vals, 90):.3f}%")
    print()

    near = [r for r in stops if r["near_ma_at_peak"]]
    far = [r for r in stops if not r["near_ma_at_peak"]]
    print(f"  At the best-favorable-price point, reversal happened NEAR an EMA21/50/200/VWAP "
          f"(within {NEAR_ATR_MULT}x ATR): {len(near)} ({100*len(near)/len(stops):.1f}%)")
    print(f"  At the best-favorable-price point, NOT near any of them "
          f"(ran further into an extended move with nothing nearby to explain the turn): "
          f"{len(far)} ({100*len(far)/len(stops):.1f}%)")
    print()
    print(f"  Among the {len(ever_profitable)} that WERE profitable at some point:")
    near2 = [r for r in ever_profitable if r["near_ma_at_peak"]]
    print(f"    reversed near an MA/VWAP: {len(near2)} ({100*len(near2)/len(ever_profitable):.1f}%)")
    print(f"    reversed with nothing nearby: {len(ever_profitable)-len(near2)} "
          f"({100*(len(ever_profitable)-len(near2))/len(ever_profitable):.1f}%)")


if __name__ == "__main__":
    run()
