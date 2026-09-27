"""
Reporting-only follow-ups to aurelius_silver_tailored_test.py /
aurelius_btc_tailored_test.py (2026-09-27). Nothing here selects anything;
every config below is either a walk-forward IS winner already frozen by
those files, or the frozen GOLD config.

  (1) GROSS vs NET on OOS for each frozen IS winner: the same run with the
      spread NOT charged (the spread GATE still uses the real spread, so
      the trade set is identical) - separates "the timing carries no
      information" from "it does, but costs eat it". Gross is never the
      verdict; the net, real-spread number is.
  (2) OOS %PF by calendar year for each winner - is any OOS result one
      regime/one year?
  (3) The frozen GOLD config with the spread gate simply removed (real
      point, real spread charged) - the direct test of the "Aurelius on
      BTC only looked dead because the 60-point gate ate 99.3% of entries"
      story. HONESTY NOTE: this is looked at AFTER seeing its OOS row in
      the tailored logs (BTC OOS %PF 1.134), so it is not a clean
      pre-registered test - treat its K=1 p-value as optimistic; it is
      one of at least 2 reference rows per instrument, and one of 2
      instruments.
  (4) FAMILY-LEVEL K for the OOS answer: each walk-forward's OOS test is
      a single frozen config (K=1 is the textbook walk-forward reading),
      but this task ran FOUR of them (2 instruments x 2 timeframes) and
      would have reported any one that "worked" - so K=4 on the OOS pool
      is the honest floor for claiming "something survived".
  (5) Trade concentration (OOS %PF with the best 1 / 3 trades removed) and
      one-notch OOS neighbourhood (every single-dimension change of the
      winner, run on OOS - reporting only): does the OOS result depend on
      a handful of trades or on the exact grid point?
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import multiprocessing as mp
import aurelius_tailored_common as T
from sim import simulate

WINNERS = {
    ("SILVER", "M15"): dict(ma_scale=1.0, min_slope_atr=0.5, max_slope_atr=None, min_sr_dist_atr=2.5,
                            min_vol_ratio=1.3, pullback_tol_atr=1.0, stop_atr=2.5, vwap_buffer_atr=1.0,
                            spread_q=0.97, spread_cost_atr_cap=0.4, slope_sr_block=True),
    ("BTCUSD", "M15"): dict(ma_scale=2.0, min_slope_atr=0.1, max_slope_atr=0.8, min_sr_dist_atr=2.5,
                            min_vol_ratio=1.6, pullback_tol_atr=0.1, stop_atr=1.5, vwap_buffer_atr=0.1,
                            spread_q=None, spread_cost_atr_cap=0.4, slope_sr_block=False),
    ("SILVER", "M5"): dict(ma_scale=3.0, min_slope_atr=0.75, max_slope_atr=1.25, min_sr_dist_atr=2.5,
                           min_vol_ratio=1.6, pullback_tol_atr=0.25, stop_atr=1.5, vwap_buffer_atr=0.1,
                           spread_q=None, spread_cost_atr_cap=None, slope_sr_block=False),
    ("BTCUSD", "M5"): dict(ma_scale=2.0, min_slope_atr=0.75, max_slope_atr=2.0, min_sr_dist_atr=2.5,
                           min_vol_ratio=1.3, pullback_tol_atr=0.1, stop_atr=4.0, vwap_buffer_atr=0.5,
                           spread_q=0.8, spread_cost_atr_cap=None, slope_sr_block=False),
}


def drop_top(trades, k):
    r = np.sort(T.trade_pct(trades))[:-k] if len(trades) > k else np.array([])
    gw, gl = r[r > 0].sum(), -r[r <= 0].sum()
    return gw / gl if gl > 0 else float("nan")


def run(cfg, part, gross=False):
    tf, point, split = T._G["tf"], T._G["point"], T._G["split"]
    p = T.make_params(tf, cfg, point)
    ctx = T.config_ctx(T._G["base"][cfg["ma_scale"]], cfg, p, point, T._G["sq"])
    c = T.part_slice(ctx, p, split, part)
    q = dict(p)
    if gross:
        q["point"] = 0.0
    return c, simulate(c, params=q)


def by_year(c, trades):
    t = pd.to_datetime(c["time"])
    rows = {}
    for tr in trades:
        y = t[tr["entry_i"]].year
        rows.setdefault(y, []).append(tr)
    return {y: T.summarize(v) for y, v in sorted(rows.items())}


if __name__ == "__main__":
    for (inst, tf) in WINNERS:
        df, split = T.setup(inst, tf)
        print(f"\n===== {inst} {tf}  (OOS from {df['time'].iloc[split]}) =====")
        cfg = WINNERS.get((inst, tf))
        if cfg is not None:
            c, net = run(cfg, "OOS")
            _, gross = run(cfg, "OOS", gross=True)
            sn, sg = T.summarize(net), T.summarize(gross)
            print(f"  IS winner on OOS: net %PF={sn['pf']:.3f} (n={sn['n']})   gross (spread not charged) "
                  f"%PF={sg['pf']:.3f} (n={sg['n']})")
            print("  OOS by year (net): " + ", ".join(f"{y}: {s['pf']:.2f} (n={s['n']})"
                                                     for y, s in by_year(c, net).items()))
            print(f"  concentration: OOS %PF without best 1 trade={drop_top(net,1):.3f}, "
                  f"without best 3={drop_top(net,3):.3f}")
            neigh = [dict(cfg, **{d: v}) for d, vals in T.SPACE.items() for v in vals if v != cfg[d]]
            with mp.get_context("fork").Pool(4) as ex:
                nres = [s for _, _, s in ex.map(T._eval_cfg, [(nc, "OOS") for nc in neigh])]
                npf = np.array([s["pf"] for s in nres if s["n"] >= 10])
                print(f"  one-notch OOS neighbourhood ({len(npf)} of {len(neigh)} with n>=10): "
                      f"median %PF={np.median(npf):.3f}, {(npf > 1).sum()} > 1, "
                      f"p25={np.percentile(npf,25):.3f} p75={np.percentile(npf,75):.3f}")
                rt = T.random_test(ex, cfg, "OOS", 800, [1, 2, 4])
            print(f"  OOS random timing (same pool/seeds as the walk-forward log): real %PF={rt['real_pf']:.3f} "
                  f"pct {rt['pctile']:.1f}; " + ", ".join(f"K={K}: p={pk:.4f}" for K, _, pk in rt["ladder"]))
        if tf == "M15":
            g = T.gold_frozen_cfg(tf)
            with mp.get_context("fork").Pool(4) as ex:
                for part in ("OOS", "ALL"):
                    rt = T.random_test(ex, g, part, 800, [1, 2, 4])
                    lad = ", ".join(f"K={K}: p={pk:.4f}" for K, _, pk in rt["ladder"])
                    print(f"  frozen GOLD config, gate removed, {part}: real %PF={rt['real_pf']:.3f} "
                          f"(n={rt['n']}, long {rt['p_buy']:.2f}); random median={np.median(rt['pool']):.3f} "
                          f"p95={np.percentile(rt['pool'],95):.3f}; pct {rt['pctile']:.1f}; {lad}")
            c, tr = run(g, "ALL")
            print("  frozen GOLD config, gate removed, ALL by year: " +
                  ", ".join(f"{y}: {s['pf']:.2f} (n={s['n']})" for y, s in by_year(c, tr).items()))
