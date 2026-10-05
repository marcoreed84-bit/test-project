"""
HONEST SEARCH (2026-10-05, user explicitly asked to "find the criteria
that works") - unlike the three single-hypothesis tests run earlier today
(VWAP-cross, trend-slope filter, fixed-top-6 time-gate - all K=1, no
sweep), this IS a parameter search, so it needs the multiple-testing
discipline CLAUDE.md already learned the hard way to apply going in, not
after the fact (see the 2026-10-04 Vanguard section: "a different, more
mundane failure mode than a construction defect, and worth naming as
such" - and the explicit rule: K = the literal number of configurations
actually searched).

FIXED GRID (defined before running anything, not expanded after seeing
results):
  hour_criterion in {top3, top6, top9, top12, zsig}   (5)
  atr_stop       in {1.5, 2.0, 2.5, 3.0}              (4)
  exit_rule      in {fade50, maxbars_only}             (2)
  -> 40 configs. K=40 for the correction below.

Selection rule (fixed before running): rank by IN-SAMPLE PF among configs
with >=30 IS trades (a floor applied uniformly, not picked after seeing
which configs clear it) - best IS PF wins, no other criterion. The winner
is then FROZEN and run ONCE on the untouched OOS 30%, with its own
random-timing null. Every other config's OOS performance is NEVER looked
at - only the single IS-selected winner touches OOS, exactly once.

Correction applied to the winner's result: Sidak, alpha_corrected =
1-(1-0.05)**(1/40) - same family of correction CLAUDE.md's 2026-10-04
section used for the three Vanguard/Meridian attempts.
"""
import sys
import itertools

import numpy as np
import pandas as pd
from scipy import stats as sstats

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B  # noqa: E402

POINT = B.POINT
MAX_BARS = 200
K_TOTAL = 40
MIN_IS_TRADES = 30


def pick_hours_topn(hour, ob, os_, n):
    df = pd.DataFrame(dict(hour=hour, ob=ob, os=os_))
    rates = df.groupby("hour").mean()
    buy_hours = set(rates["ob"].sort_values(ascending=False).head(n).index.tolist())
    sell_hours = set(rates["os"].sort_values(ascending=False).head(n).index.tolist())
    return buy_hours, sell_hours


def pick_hours_zsig(hour, ob, os_, alpha=0.05):
    """Hours whose OB (or OS) rate is statistically above the overall mean
    at the given alpha, one-sided z-test, UNCORRECTED across hours (this is
    itself a plain, named criterion in the grid, not a second hidden search
    - its own false-positive risk from testing 24 hours is exactly the kind
    of thing an OOS check and the grid-level Sidak correction below guard
    against)."""
    def sig_hours(cond):
        df = pd.DataFrame(dict(hour=hour, c=cond))
        g = df.groupby("hour")["c"]
        rates, ns = g.mean(), g.size()
        p0 = cond.mean()
        se = np.sqrt(p0 * (1 - p0) / ns)
        z = (rates - p0) / se
        pvals = 1 - sstats.norm.cdf(z)
        return set(rates.index[pvals < alpha].tolist())
    return sig_hours(ob), sig_hours(os_)


def simulate(df, main, atr, buy_hours, sell_hours, atr_stop, exit_rule, start_i, end_i,
             entry_dirs=None):
    o, h, l, sp_pts = df["open"].values, df["high"].values, df["low"].values, df["spread"].values
    hour = df["time"].dt.hour.values
    trades = []
    pos = None
    for t in range(start_i, end_i):
        sp = sp_pts[t] * POINT
        if pos is not None:
            d = pos["dir"]
            hit_sl = (l[t] <= pos["sl"]) if d > 0 else (h[t] + sp >= pos["sl"])
            if hit_sl:
                px = pos["sl"]
                trades.append(dict(entry_i=pos["entry_i"], dir=d, pnl=(px - pos["entry"]) * d, reason="SL"))
                pos = None
                continue
            faded = exit_rule == "fade50" and ((main[t] <= 50.0) if d > 0 else (main[t] >= 50.0))
            timed_out = (t - pos["entry_i"]) >= MAX_BARS
            if faded or timed_out:
                px = o[t] if d > 0 else o[t] + sp
                trades.append(dict(entry_i=pos["entry_i"], dir=d, pnl=(px - pos["entry"]) * d,
                                    reason="FADE" if faded else "TIMEOUT"))
                pos = None
                continue
        if pos is None:
            a = atr[t - 1]
            if not (a > 0):
                continue
            if entry_dirs is not None:
                d = entry_dirs.get(t, 0)
                if d == 0:
                    continue
            else:
                s = t - 1
                fresh_ob = main[s] >= 80.0 and main[s - 1] < 80.0
                fresh_os = main[s] <= 20.0 and main[s - 1] > 20.0
                if fresh_ob and hour[t] in buy_hours:
                    d = 1
                elif fresh_os and hour[t] in sell_hours:
                    d = -1
                else:
                    continue
            entry = o[t] + sp if d > 0 else o[t]
            sl = entry - d * atr_stop * a
            pos = dict(entry_i=t, dir=d, entry=entry, sl=sl)
    return trades


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_entry_matched(start_i, end_i, n_target, long_frac, seed):
    rng = np.random.default_rng(seed)
    eligible = np.arange(start_i + 1, end_i)
    chosen = rng.choice(eligible, size=min(n_target, len(eligible)), replace=False)
    return {int(t): (1 if rng.random() < long_frac else -1) for t in chosen}


if __name__ == "__main__":
    m5 = B.load_m5()
    h, l, c = m5["high"].values, m5["low"].values, m5["close"].values
    main, _ = B.mt5_stoch_signal(h, l, c, 5, 3, 3)
    atr = B.wilder_atr(h, l, c, 14)
    hour_all = m5["time"].dt.hour.values
    n_bars = len(m5)
    cutoff = int(n_bars * 0.70)
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {m5['time'].iloc[cutoff]}")

    valid = ~np.isnan(main)
    is_mask = valid & (np.arange(n_bars) < cutoff)
    ob_is, os_is = main[is_mask] >= 80.0, main[is_mask] <= 20.0
    hour_is = hour_all[is_mask]

    hour_criteria = {
        "top3": pick_hours_topn(hour_is, ob_is, os_is, 3),
        "top6": pick_hours_topn(hour_is, ob_is, os_is, 6),
        "top9": pick_hours_topn(hour_is, ob_is, os_is, 9),
        "top12": pick_hours_topn(hour_is, ob_is, os_is, 12),
        "zsig": pick_hours_zsig(hour_is, ob_is, os_is),
    }
    stops = [1.5, 2.0, 2.5, 3.0]
    exit_rules = ["fade50", "maxbars_only"]

    grid = list(itertools.product(hour_criteria.keys(), stops, exit_rules))
    assert len(grid) == K_TOTAL, f"grid size {len(grid)} != declared K={K_TOTAL}"

    print(f"\n{'='*92}\nSEARCHING {K_TOTAL} configs on IN-SAMPLE ONLY (OOS not touched yet)\n{'='*92}")
    results = []
    for hc, stop, ex in grid:
        bh, sh = hour_criteria[hc]
        trades = simulate(m5, main, atr, bh, sh, stop, ex, 20, cutoff)
        n = len(trades)
        if n < MIN_IS_TRADES:
            continue
        pnl = [t["pnl"] for t in trades]
        results.append(dict(hc=hc, stop=stop, ex=ex, n=n, pf=pf(pnl), net=sum(pnl)))

    results.sort(key=lambda r: r["pf"], reverse=True)
    print(f"  {len(results)}/{K_TOTAL} configs cleared the {MIN_IS_TRADES}-trade IS floor")
    print(f"  top 5 by IS PF:")
    for r in results[:5]:
        print(f"    hour={r['hc']:6s} stop={r['stop']:.1f} exit={r['ex']:12s} "
              f"n={r['n']:4d} PF={r['pf']:.3f} net={r['net']:8.2f}")

    winner = results[0]
    print(f"\n  WINNER (best IS PF): hour={winner['hc']}, stop={winner['stop']}, exit={winner['ex']}")
    print(f"  This is the ONLY config that will touch OOS data.")

    bh, sh = hour_criteria[winner["hc"]]
    print(f"\n{'='*92}\nFROZEN WINNER on OUT-OF-SAMPLE (last 30%, touched for the first time now)\n{'='*92}")
    oos_trades = simulate(m5, main, atr, bh, sh, winner["stop"], winner["ex"], cutoff, n_bars)
    n_oos = len(oos_trades)
    if n_oos == 0:
        print("  n=0 OOS trades - cannot evaluate")
    else:
        oos_pnl = [t["pnl"] for t in oos_trades]
        oos_pf = pf(oos_pnl)
        print(f"  OOS: n={n_oos}, win%={100*np.mean([x>0 for x in oos_pnl]):.1f}, "
              f"PF={oos_pf:.3f}, net={sum(oos_pnl):.2f}")

        print(f"\n{'='*92}\nRANDOM-TIMING NULL for the frozen winner, OOS only (2000 draws)\n{'='*92}")
        long_frac = np.mean([t["dir"] > 0 for t in oos_trades])
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            dirs = random_entry_matched(cutoff, n_bars, n_oos, long_frac, seed)
            ntrades = simulate(m5, main, atr, bh, sh, winner["stop"], winner["ex"], cutoff, n_bars,
                                entry_dirs=dirs)
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_raw = (null_pfs >= oos_pf).mean()
        alpha_sidak = 1 - (1 - 0.05) ** (1.0 / K_TOTAL)
        print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}")
        print(f"  RAW p-value (K=1, face value) = {p_raw:.4f}")
        print(f"  Honest K for this search = {K_TOTAL}. Sidak-corrected significance threshold "
              f"= {alpha_sidak:.5f} (vs the usual 0.05)")
        if p_raw < alpha_sidak:
            print(f"  -> SURVIVES even after correcting for searching {K_TOTAL} configs (p={p_raw:.4f} < {alpha_sidak:.5f})")
        elif p_raw < 0.05:
            print(f"  -> Looks significant at face value (p={p_raw:.4f} < 0.05) but FAILS the honest "
                  f"K={K_TOTAL}-corrected bar ({alpha_sidak:.5f}) - overfitting, not a real edge")
        else:
            print(f"  -> Does not even clear the uncorrected p<0.05 bar - rejected outright")
