"""
User's construction: Stochastic oversold + price rejecting the GREEN
(bullish) cloud as support -> long; Stochastic overbought + price
rejecting the RED (bearish) cloud as resistance -> short. Not yet tested
this session. Reuses the validated H4 Ichimoku engine (research/ichimoku/
engine.py - chk_* validated, see its own docstring) rather than
re-deriving the cloud math.

Stochastic (%K/%D, period 14/3/3, standard) is NOT yet in engine.py -
added here, in the test script, not in the validated engine file.

Construction (mirrors sr_reject_test.py's touch-and-reject pattern, cloud
edge in place of the S&R level, stochastic extreme added as confirmation):
  bull: cloud is bullish (Senkou A > Senkou B) AND low touched within
        TOL*ATR of cloud_top in the last LOOKBACK bars AND %K dipped
        <= 20 somewhere in that same window AND close has since rejected
        back above cloud_top by REJECT*ATR.
  bear: mirror - bearish cloud, high touched cloud_bot, %K >= 80, close
        rejected back below cloud_bot.
Edge-triggered (first bar the full condition is true), same bounded
forward-scan / random-direction-control rigor as battery3.py.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E

# NOTE: both research/aurelius/ and research/ichimoku/ have a file literally
# named engine.py - `sys.path` + `import engine` would collide via Python's
# module cache (whichever loads first wins the name for both). Rather than
# fight that, tp_sl_outcomes/report_outcome_set (battery3.py's bounded
# forward-scan + random-direction-control machinery) are copied inline
# below, unchanged, instead of cross-imported.

POINT = 0.01
LOOKBACK = 8       # H4 bars - ~1.3 trading days to look back for the touch+oversold
TOL_ATR = 0.30
REJECT_ATR = 0.30
STOCH_PERIOD, STOCH_SMOOTH = 14, 3
STOCH_OVERSOLD, STOCH_OVERBOUGHT = 20.0, 80.0
N_RANDOM_SEEDS = 2000
MAXHOLD_BARS_DEFAULT = 500


def tp_sl_outcomes(ctx, triggers_with_dir, tp_atr, sl_atr, maxhold=MAXHOLD_BARS_DEFAULT):
    """Copied from research/aurelius/battery3.py (unchanged) - see that
    file's docstring for the full rationale. Computes BOTH hypothetical
    buy/sell outcomes per trigger in one forward pass."""
    close, high, low, atr, spread, n = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"], ctx["n"]
    out = []
    dropped = 0
    for i, real_dir in triggers_with_dir:
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        entry_buy, entry_sell = raw + sc, raw - sc
        tp_buy, sl_buy = entry_buy + tp_atr * atr[i], entry_buy - sl_atr * atr[i]
        tp_sell, sl_sell = entry_sell - tp_atr * atr[i], entry_sell + sl_atr * atr[i]
        pnl_buy = pnl_sell = None
        for k2 in range(fill_i, min(fill_i + maxhold, n)):
            if pnl_buy is None:
                hit_tp, hit_sl = high[k2] >= tp_buy, low[k2] <= sl_buy
                if hit_tp or hit_sl:
                    pnl_buy = (sl_buy - entry_buy) if hit_sl else (tp_buy - entry_buy)
            if pnl_sell is None:
                hit_tp, hit_sl = low[k2] <= tp_sell, high[k2] >= sl_sell
                if hit_tp or hit_sl:
                    pnl_sell = (entry_sell - sl_sell) if hit_sl else (entry_sell - tp_sell)
            if pnl_buy is not None and pnl_sell is not None:
                break
        if pnl_buy is None or pnl_sell is None:
            dropped += 1
            continue
        out.append((pnl_buy, pnl_sell, i, real_dir))
    return out, dropped


def report_outcome_set(label, outcomes, n_total, seed=0):
    """Copied from research/aurelius/battery3.py (unchanged)."""
    if not outcomes:
        print(f"  {label}: 0 resolved trades, skip")
        return
    pnl_buy = np.array([o[0] for o in outcomes])
    pnl_sell = np.array([o[1] for o in outcomes])
    entry_i = np.array([o[2] for o in outcomes])
    real_dir = np.array([o[3] for o in outcomes])
    real_pnl = np.where(real_dir > 0, pnl_buy, pnl_sell)
    real_net = real_pnl.sum()
    n_tr = len(outcomes)
    wins = (real_pnl > 0).sum()
    pf = real_pnl[real_pnl > 0].sum() / -real_pnl[real_pnl <= 0].sum() if (real_pnl <= 0).any() and real_pnl[real_pnl <= 0].sum() < 0 else np.inf

    rng = np.random.default_rng(seed)
    rdir = rng.integers(0, 2, size=(N_RANDOM_SEEDS, n_tr))
    random_nets = np.where(rdir == 1, pnl_buy, pnl_sell).sum(axis=1)
    pct = 100 * (random_nets < real_net).mean()

    cutoff = int(n_total * 0.7)
    is_mask = entry_i < cutoff
    is_net, oos_net = real_pnl[is_mask].sum(), real_pnl[~is_mask].sum()
    is_n, oos_n = is_mask.sum(), (~is_mask).sum()

    pnl_sorted = np.sort(real_pnl)[::-1]
    top5 = pnl_sorted[:5].sum()
    ex_top5 = real_net - top5

    print(f"  {label}: n={n_tr} net={real_net:.2f} win%={100*wins/n_tr:.1f} pf={pf:.3f} "
          f"| IS(n={is_n})={is_net:.2f} OOS(n={oos_n})={oos_net:.2f} "
          f"| ex-top5={ex_top5:.2f} "
          f"| random-dir percentile={pct:.1f} (null mean={random_nets.mean():.2f} std={random_nets.std():.2f})")


def stochastic(high, low, close, period=STOCH_PERIOD, smooth=STOCH_SMOOTH):
    hh = pd.Series(high).rolling(period).max().values
    ll = pd.Series(low).rolling(period).min().values
    rng = hh - ll
    with np.errstate(divide="ignore", invalid="ignore"):
        k_raw = np.where(rng > 0, 100.0 * (close - ll) / np.where(rng > 0, rng, 1.0), np.nan)
    k = pd.Series(k_raw).rolling(smooth).mean().values
    d = pd.Series(k).rolling(smooth).mean().values
    return k, d


if __name__ == "__main__":
    d = E.load_h4()
    p = E.params()
    ctx = E.build_context(d, p)
    n = ctx["n"]
    high, low, close, atr = ctx["high"], ctx["low"], ctx["close"], ctx["atr"]
    cloud_top, cloud_bot = ctx["cloud_top"], ctx["cloud_bot"]
    spread = d["spread"].values.astype(float)
    ctx["spread"] = spread  # tp_sl_outcomes expects this key

    D = p["displacement"]
    sa_sh = pd.Series(ctx["sa_raw"]).shift(D).values
    sb_sh = pd.Series(ctx["sb_raw"]).shift(D).values
    is_bull_cloud = sa_sh > sb_sh
    is_bear_cloud = sb_sh > sa_sh

    k, dd = stochastic(high, low, close)

    print(f"n_bars={n} (H4, ~{n/6:.0f} trading days)\n")

    bull_sig = np.zeros(n, dtype=bool)
    bear_sig = np.zeros(n, dtype=bool)
    for i in range(LOOKBACK, n):
        if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(cloud_top[i]) or np.isnan(cloud_bot[i]):
            continue
        tol, rej = TOL_ATR * atr[i], REJECT_ATR * atr[i]
        win = range(max(0, i - LOOKBACK + 1), i + 1)
        if is_bull_cloud[i]:
            touched = any(low[j] <= cloud_top[i] + tol for j in win)
            oversold = any((not np.isnan(k[j])) and k[j] <= STOCH_OVERSOLD for j in win)
            rejected = close[i] - cloud_top[i] >= rej
            bull_sig[i] = touched and oversold and rejected
        if is_bear_cloud[i]:
            touched = any(high[j] >= cloud_bot[i] - tol for j in win)
            overbought = any((not np.isnan(k[j])) and k[j] >= STOCH_OVERBOUGHT for j in win)
            rejected = cloud_bot[i] - close[i] >= rej
            bear_sig[i] = touched and overbought and rejected

    # edge trigger: first bar the condition turns true
    trig_bull = bull_sig & ~np.concatenate(([False], bull_sig[:-1]))
    trig_bear = bear_sig & ~np.concatenate(([False], bear_sig[:-1]))
    triggers = [(i, 1.0) for i in np.where(trig_bull)[0]] + [(i, -1.0) for i in np.where(trig_bear)[0]]
    triggers.sort(key=lambda t: t[0])
    print(f"Stochastic-oversold/overbought + cloud-support/resistance-reject: "
          f"{len(triggers)} triggers ({sum(1 for _,dr in triggers if dr>0)} bull, "
          f"{sum(1 for _,dr in triggers if dr<0)} bear) over {n} H4 bars "
          f"-> {len(triggers)/(n/6):.3f}/day\n")

    if len(triggers) < 10:
        print("Too few triggers for a meaningful test - stopping.")
        sys.exit(0)

    print("=" * 70)
    for maxhold, label in ((12, "~2 days"), (30, "~5 days")):
        print(f"\n--- max hold = {maxhold} H4 bars ({label}) ---")
        for tp_atr, sl_atr in ((1.0, 1.0), (1.5, 1.0), (2.0, 1.5), (2.5, 1.5)):
            out, dropped = tp_sl_outcomes(ctx, triggers, tp_atr, sl_atr, maxhold=maxhold)
            report_outcome_set(f"tp={tp_atr}xATR sl={sl_atr}xATR (dropped={dropped}/{len(triggers)})", out, n)
