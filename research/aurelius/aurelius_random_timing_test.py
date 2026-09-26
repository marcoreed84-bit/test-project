"""
Same random-timing baseline discipline (Opus's Wolfe Wave check, extended
to RoundingBottom/H&S/Rectangle, 2026-09-26) applied to Aurelius - the
flagship, continuously-running trend-follower, adapted for its structural
difference from the pattern EAs: no fixed stop/target bracket, a dynamic
exit chain instead (SESSION_CLOSE > PRICE21 > VWAP > ALIGN_BREAK > STALE,
then breakeven/trail management, then the resting ATR stop - see sim.py).

ADAPTATION: a fixed-bracket replay doesn't apply here, so this tests the
more fundamental question instead - does Aurelius's REAL entry-quality
filter stack (5-MA alignment direction + pullback-to-MA + slope + volume +
S/R distance + cross-count) actually add value, or would the SAME real
exit machinery (unchanged: same ATR stop, same Price21/VWAP/ALIGN_BREAK
exits, same session-close/stale/breakeven logic) produce similar results
if entries fired at RANDOM times with a RANDOM (coin-flip) direction
instead? simulate_random_entry() is a fork of sim.simulate() that keeps
every exit rule byte-identical and only replaces the entry gate: same
practical constraints (cooldown, session/holiday/spread/ATR sanity - things
a live system needs regardless of signal quality), fired with a calibrated
probability so the AVERAGE trade count roughly matches the real run, with
direction chosen by a coin flip rather than the real alignment signal.

Note ALIGN_BREAK's exit condition (ctx["aligned_buy"/"aligned_sell"]) is
NOT disabled for random entries - if the market isn't actually trending in
whatever direction was randomly picked, this exit fires quickly and the
trade is a small, near-breakeven loss, exactly as it should: this isolates
whether Aurelius's entry filters find genuinely favourable moments, not
just "the exit rules are good" (which would help both the real and random
version equally).

%PF (not raw points) is used throughout - the M5 dataset only spans
~2023-2026 (~3.5 years, GOLD ~$1830->~$4000, less extreme than the 25-year
H4 dataset's ~15x move but still a real drift-bias risk for a points-based
PF), per the same lesson from Wolfe Wave/RoundingBottom/Rectangle.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from engine import P, POINT
from sim import simulate, stats

np.random.seed(42)
N_RANDOM = 300


def simulate_random_entry(ctx, params, rng, p_fire):
    """Fork of sim.simulate() - see this file's own docstring for exactly
    what's kept (all exit logic) vs. replaced (the entry gate)."""
    p = params
    n = ctx["n"]
    close, high, low = ctx["close"], ctx["high"], ctx["low"]
    atr = ctx["atr"]

    trades = []
    in_pos = 0
    entry_px = 0.0
    entry_atr = 0.0
    stop_px = 0.0
    entry_i = -1
    bars_since_close = 10 ** 9
    price21_bad = 0
    vwap_bad = 0
    be_done = False
    peak_fav_px = 0.0

    warmup = max(p["p2400"], p["p600"]) + 50

    for i in range(warmup, n - 1):
        fill_i = i + 1
        px_fill = close[i]

        if in_pos != 0:
            is_buy = in_pos > 0
            fired = None
            if ctx["near_daily_close"][i] or ctx["friday_flatten"][i]:
                fired = "SESSION_CLOSE"
            if fired is None and p["use_price21_exit"]:
                m21 = ctx["m21"][i]
                if not np.isnan(m21) and atr[i] > 0:
                    buf = p["price21_buffer_atr"] * atr[i]
                    bad = (close[i] < m21 - buf) if is_buy else (close[i] > m21 + buf)
                    price21_bad = price21_bad + 1 if bad else 0
                else:
                    price21_bad = 0
                if price21_bad >= p["price21_confirm_bars"]:
                    fired = "PRICE21"
            if fired is None and p["use_vwap_exit"]:
                vw = ctx["vwap"][i]
                if vw > 0 and atr[i] > 0:
                    buf = p["vwap_buffer_atr"] * atr[i]
                    bad = (close[i] < vw - buf) if is_buy else (close[i] > vw + buf)
                    vwap_bad = vwap_bad + 1 if bad else 0
                else:
                    vwap_bad = 0
                if vwap_bad >= p["vwap_confirm_bars"]:
                    fired = "VWAP"
            if fired is None:
                still_aligned = ctx["aligned_buy"][i] if is_buy else ctx["aligned_sell"][i]
                if not still_aligned:
                    fired = "ALIGN_BREAK"
            if fired is None and p.get("use_stale_exit") and entry_atr > 0:
                bars_open = i - entry_i + 1
                if bars_open >= p.get("stale_bars", 48):
                    prof = (close[i] - entry_px) * (1 if is_buy else -1)
                    if prof < -p.get("stale_min_loss_atr", 0.5) * entry_atr:
                        fired = "STALE"

            if fired is not None:
                trades.append(dict(entry_i=entry_i, exit_i=fill_i, dir=in_pos,
                                    entry_px=entry_px, exit_px=px_fill,
                                    entry_atr=entry_atr, reason=fired))
                in_pos = 0
                bars_since_close = 0
                price21_bad = 0
                vwap_bad = 0
                be_done = False
                continue

            if p["use_breakeven"] and entry_atr > 0:
                prof = (close[i] - entry_px) * (1 if is_buy else -1)
                if not be_done:
                    if prof >= p["breakeven_atr"] * entry_atr:
                        lock = p["breakeven_lock_atr"] * entry_atr
                        new_sl = entry_px + lock if is_buy else entry_px - lock
                        stop_px = new_sl
                        be_done = True
                        peak_fav_px = close[i]
                elif p["use_trail_after_be"]:
                    if (is_buy and close[i] > peak_fav_px) or ((not is_buy) and close[i] < peak_fav_px):
                        peak_fav_px = close[i]
                    give = p["trail_give_back_atr"] * entry_atr
                    trail_sl = peak_fav_px - give if is_buy else peak_fav_px + give
                    if (is_buy and trail_sl > stop_px) or ((not is_buy) and trail_sl < stop_px):
                        stop_px = trail_sl

            if p["use_stop"] and stop_px > 0:
                hit = (low[fill_i] <= stop_px) if is_buy else (high[fill_i] >= stop_px)
                if hit:
                    trades.append(dict(entry_i=entry_i, exit_i=fill_i, dir=in_pos,
                                        entry_px=entry_px, exit_px=stop_px,
                                        entry_atr=entry_atr, reason="STOP"))
                    in_pos = 0
                    bars_since_close = 0
                    price21_bad = 0
                    vwap_bad = 0
                    be_done = False
            continue

        # --- flat: RANDOM entry gate (practical constraints kept, signal-quality filters dropped) ---
        bars_since_close += 1
        if bars_since_close < p["cooldown_bars"]:
            continue
        if ctx["no_entry_near_close"][i] or ctx["friday_no_entry"][i]:
            continue
        if ctx["is_market_holiday"][fill_i]:
            continue
        if ctx["spread"][i] > 60:
            continue
        if atr[i] <= 0 or np.isnan(atr[i]):
            continue

        if rng.random() >= p_fire:
            continue
        is_buy = rng.random() < 0.5

        spread_cost = ctx["spread"][fill_i] * POINT
        in_pos = 1 if is_buy else -1
        entry_px = px_fill + spread_cost if is_buy else px_fill - spread_cost
        entry_atr = atr[i]
        entry_i = fill_i
        stop_px = (entry_px - p["stop_atr"] * entry_atr) if is_buy else (entry_px + p["stop_atr"] * entry_atr)
        price21_bad = 0
        vwap_bad = 0
        be_done = False
        peak_fav_px = entry_px

        if p["use_stop"] and stop_px > 0:
            hit = (low[fill_i] <= stop_px) if is_buy else (high[fill_i] >= stop_px)
            if hit:
                trades.append(dict(entry_i=entry_i, exit_i=fill_i, dir=in_pos,
                                    entry_px=entry_px, exit_px=stop_px,
                                    entry_atr=entry_atr, reason="STOP"))
                in_pos = 0
                bars_since_close = 0
                price21_bad = 0
                vwap_bad = 0
                be_done = False

    return trades


def pct_pf(trades):
    if not trades:
        return float("nan")
    arr = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] / t["entry_px"] for t in trades])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def calibrate_p_fire(ctx, params, rng, target_n, trials=3):
    p_fire = 0.02
    for _ in range(trials):
        trades = simulate_random_entry(ctx, params, rng, p_fire)
        if len(trades) == 0:
            p_fire *= 2
            continue
        p_fire *= target_n / len(trades)
        p_fire = min(max(p_fire, 1e-5), 0.9)
    return p_fire


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    print(f"M5 data: n={len(df)} bars, {df['time'].min()} -> {df['time'].max()}\n")
    ctx = E.build_context(df, h4, P)

    real_trades = simulate(ctx)
    real_stats = stats(real_trades)
    real_pct_pf = pct_pf(real_trades)
    print(f"REAL Aurelius v1.46 defaults: n={real_stats['n']}  win%={100*real_stats['win_rate']:.1f}  "
          f"net={real_stats['net']:.2f}  raw-points PF={real_stats['pf']:.3f}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = calibrate_p_fire(ctx, P, rng, real_stats["n"])
    print(f"\nCalibrated p_fire={p_fire:.5f} to target ~{real_stats['n']} trades")

    print(f"Running {N_RANDOM} random-entry/coin-flip-direction baselines (same exit machinery)...")
    rng = np.random.default_rng(42)
    rand_pfs, rand_ns = [], []
    for _ in range(N_RANDOM):
        tr = simulate_random_entry(ctx, P, rng, p_fire)
        rand_ns.append(len(tr))
        rand_pfs.append(pct_pf(tr))
    rand_pfs = np.array(rand_pfs)
    rand_pfs = rand_pfs[~np.isnan(rand_pfs) & ~np.isinf(rand_pfs)]
    print(f"  random-entry trade counts: mean={np.mean(rand_ns):.0f} (target {real_stats['n']})")
    print(f"  random-entry %PF distribution: median={np.median(rand_pfs):.3f}  "
          f"p10={np.percentile(rand_pfs,10):.3f}  p90={np.percentile(rand_pfs,90):.3f}  "
          f"p95={np.percentile(rand_pfs,95):.3f}")
    pctile = 100 * (rand_pfs < real_pct_pf).mean()
    p_val = (rand_pfs >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile of {len(rand_pfs)} "
          f"random-entry runs (one-sided p={p_val:.3f})")
    if real_pct_pf > np.percentile(rand_pfs, 95):
        print("  -> ABOVE the random-entry band - Aurelius's entry filters add real, specific value")
        print("     beyond the exit machinery + GOLD's own drift alone.")
    else:
        print("  -> INSIDE (or below) the random-entry band - no clear evidence the entry filter stack")
        print("     adds value beyond what the same exit rules would produce on their own.")
