"""
Independent re-test of the three "coded but never real-MT5-tested" leads in
Aurelius_EA.mq5 / Aurelius_M15_EA.mq5, run against the validated engine
rather than re-quoting the headers' own prior Python claims:

  1. InpUseStaleExit  (M5, default off)  - time-based exit, aimed at the
     documented 27.69%-equity-drawdown incident, which the EA's own header
     diagnoses as a DURATION problem no distance stop can reach.
  2. InpUseSlopeSRBlock (M15, default ON, about to go live, never real-tested)
     - combined steep-slope x far-from-S/R entry block.
  3. InpUseMomentum (both files, default off) - MACD-histogram-turn entry gate.

Rigor is this project's standing standard (SESSION_NOTES.md): chronological
70/30 IS/OOS split, tail concentration with the ex-top-5 honesty check, and a
permutation null. Helpers are imported from sr_reject_test.py rather than
re-implemented so the null is literally the same code the S&R test used.

Two nulls are used, because the candidates are not the same kind of change:
  - ENTRY filters (2 and 3) remove trades from the base population, so the
    null is sr_reject_test.permutation_test: random same-size subsets of the
    BASE model's own trades.
  - The STALE EXIT does not remove trades, it re-times exits, so a subset
    null is meaningless for it. Its null instead keeps the rule's ELIGIBILITY
    (open >= InpStaleBars) and replaces only the still-losing CONDITION with a
    coin flip, calibrated to fire the same number of stale exits. It answers
    the actual question: does "still losing" carry information, or is exiting
    any long-held trade equally good?

Drawdown is measured with sim.risk_stats() - see its docstring for what
closed_dd / float_dd / worst_mae mean and what they approximate.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S
from sr_reject_test import split_stats, tail_concentration, permutation_test


def show(tag, trades, ctx):
    st = S.stats(trades)
    rk = S.risk_stats(trades, ctx)
    print(f"  {tag:30s} n={st['n']:4d} net={st['net']:9.1f} pf={st['pf']:5.3f} "
          f"wr={100*st['win_rate']:4.1f}%  closedDD={rk['closed_dd']:7.1f} "
          f"floatDD={rk['float_dd']:7.1f} worstMAE={rk['worst_mae']:6.1f}")
    return st, rk


def show_split(tag, trades, n_total):
    a, b = split_stats(trades, n_total)
    print(f"  {tag:30s} IS  n={a['n']:4d} net={a['net']:8.1f} pf={a['pf']:5.3f}"
          f"   |  OOS n={b['n']:4d} net={b['net']:8.1f} pf={b['pf']:5.3f}")


def show_tail(tag, trades):
    t = tail_concentration(trades)
    print(f"  {tag:30s} net={t['net']:8.1f}  top5={t['top5_pct']:5.1f}% of net  "
          f"ex-top5 net={t['ex_top5_net']:8.1f}")


def count_stale(trades):
    return sum(1 for t in trades if t["reason"] == "STALE")


def calibrate_random_stale(ctx, base_params, target, seed=0, tol=2, iters=22):
    """Find the per-bar firing probability q that makes an information-free
    stale rule fire ~`target` times, so the null is count-matched."""
    lo, hi = 0.0, 1.0
    q = 0.05
    for _ in range(iters):
        q = 0.5 * (lo + hi)
        rng = np.random.default_rng(seed)
        p = dict(base_params)
        p["stale_rule"] = lambda bars, prof, atr, _r=rng, _q=q: _r.random() < _q
        c = count_stale(S.simulate(ctx, params=p))
        if abs(c - target) <= tol:
            return q, c
        if c < target:
            lo = q
        else:
            hi = q
    return q, c


def random_stale_null(ctx, base_params, q, n_draws, seed0=1000):
    out = []
    for d in range(n_draws):
        rng = np.random.default_rng(seed0 + d)
        p = dict(base_params)
        p["stale_rule"] = lambda bars, prof, atr, _r=rng, _q=q: _r.random() < _q
        tr = S.simulate(ctx, params=p)
        st = S.stats(tr)
        rk = S.risk_stats(tr, ctx)
        out.append((st["net"], rk["closed_dd"], rk["float_dd"], count_stale(tr)))
    return np.array(out)


def pct_below(draws, real):
    return 100.0 * (draws < real).mean()


if __name__ == "__main__":
    N_PERM = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    N_NULL = int(sys.argv[2]) if len(sys.argv) > 2 else 400

    df = E.load_m5()
    h4 = E.load_h4()
    ctx5 = E.build_context(df, h4, E.P)
    m15 = E.resample_m15_from_m5(df)
    ctx15 = E.build_context(m15, h4, E.P15)
    n5, n15 = ctx5["n"], ctx15["n"]
    print(f"M5 bars {n5}, M15 bars {n15}, "
          f"{df['time'].iloc[0]} .. {df['time'].iloc[-1]}")

    b5 = S.simulate(ctx5, params=E.P)
    b15on = S.simulate(ctx15, params=E.P15)
    b15off = S.simulate(ctx15, params=dict(E.P15, use_slope_sr_block=False))

    # ================= 1. InpUseStaleExit (M5) =================
    print("\n" + "=" * 78)
    print("1. InpUseStaleExit - M5, v1.46 true defaults")
    print("=" * 78)
    show("baseline (stale OFF)", b5, ctx5)
    show_split("baseline", b5, n5)
    show_tail("baseline", b5)

    for bars, loss in ((48, 0.5), (60, 0.25)):
        p = dict(E.P, use_stale_exit=True, stale_bars=bars, stale_min_loss_atr=loss)
        tr = S.simulate(ctx5, params=p)
        k = count_stale(tr)
        tag = f"stale {bars}b/{loss}ATR ({k} fired)"
        print()
        st, rk = show(tag, tr, ctx5)
        show_split(tag, tr, n5)
        show_tail(tag, tr)

        q, got = calibrate_random_stale(ctx5, p, k)
        print(f"  null: q={q:.5f} -> {got} random stale exits (target {k}); "
              f"{N_NULL} draws")
        draws = random_stale_null(ctx5, p, q, N_NULL)
        print(f"  null net      mean={draws[:,0].mean():8.1f} sd={draws[:,0].std():6.1f}"
              f"   real={st['net']:8.1f}  pct={pct_below(draws[:,0], st['net']):5.1f}")
        print(f"  null closedDD mean={draws[:,1].mean():8.1f} sd={draws[:,1].std():6.1f}"
              f"   real={rk['closed_dd']:8.1f}  pct(lower is better)="
              f"{100-pct_below(draws[:,1], rk['closed_dd']):5.1f}")
        print(f"  null floatDD  mean={draws[:,2].mean():8.1f} sd={draws[:,2].std():6.1f}"
              f"   real={rk['float_dd']:8.1f}  pct(lower is better)="
              f"{100-pct_below(draws[:,2], rk['float_dd']):5.1f}")

    # ================= 2. InpUseSlopeSRBlock (M15) =================
    print("\n" + "=" * 78)
    print("2. InpUseSlopeSRBlock - M15, v1.51 shipped default is ON")
    print("=" * 78)
    show("block OFF (pre-v1.51)", b15off, ctx15)
    show_split("block OFF", b15off, n15)
    show_tail("block OFF", b15off)
    print()
    show("block ON  (v1.51 ship)", b15on, ctx15)
    show_split("block ON", b15on, n15)
    show_tail("block ON", b15on)
    print(f"  permutation ({N_PERM} draws, random same-size subsets of block-OFF trades):")
    print("   ", permutation_test(b15off, b15on, n_draws=N_PERM))

    print("\n  threshold plateau check (slope x S/R, net / PF / floatDD):")
    for slope in (0.6, 0.8, 1.0, 1.2):
        for sr in (4.0, 5.0, 6.0, 7.0, 8.0):
            p = dict(E.P15, use_slope_sr_block=True,
                     slope_sr_block_slope=slope, slope_sr_block_sr=sr)
            tr = S.simulate(ctx15, params=p)
            st = S.stats(tr); rk = S.risk_stats(tr, ctx15)
            print(f"    slope>={slope:.1f} sr>={sr:.1f}  n={st['n']:4d} "
                  f"net={st['net']:8.1f} pf={st['pf']:5.3f} floatDD={rk['float_dd']:7.1f}")

    print("\n  same block PORTED TO M5 (does it carry over?):")
    for slope in (0.6, 0.8, 1.0):
        for sr in (4.0, 6.0, 8.0):
            p = dict(E.P, use_slope_sr_block=True,
                     slope_sr_block_slope=slope, slope_sr_block_sr=sr)
            tr = S.simulate(ctx5, params=p)
            st = S.stats(tr); rk = S.risk_stats(tr, ctx5)
            print(f"    slope>={slope:.1f} sr>={sr:.1f}  n={st['n']:4d} "
                  f"net={st['net']:8.1f} pf={st['pf']:5.3f} floatDD={rk['float_dd']:7.1f}")

    # ================= 3. InpUseMomentum =================
    print("\n" + "=" * 78)
    print("3. InpUseMomentum (MACD 12/26/9 histogram turn)")
    print("=" * 78)
    for meth in ("sma", "ema"):
        print(f"\n  --- MACD signal line smoothed with {meth.upper()} "
              f"({'MetaTrader convention' if meth=='sma' else 'sensitivity check'}) ---")
        c5 = E.build_context(df, h4, dict(E.P, macd_signal_method=meth))
        t5 = S.simulate(c5, params=dict(E.P, use_momentum=True))
        show(f"M5 momentum ({meth})", t5, c5)
        show_split(f"M5 momentum ({meth})", t5, n5)
        show_tail(f"M5 momentum ({meth})", t5)
        print("   ", permutation_test(b5, t5, n_draws=N_PERM))

        c15 = E.build_context(m15, h4, dict(E.P15, macd_signal_method=meth))
        t15 = S.simulate(c15, params=dict(E.P15, use_momentum=True))
        show(f"M15 momentum ({meth})", t15, c15)
        show_split(f"M15 momentum ({meth})", t15, n15)
        show_tail(f"M15 momentum ({meth})", t15)
        print("   ", permutation_test(b15on, t15, n_draws=N_PERM))
