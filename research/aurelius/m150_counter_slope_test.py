"""
Follow-up to slow_ma_counter_test.py: the 600 EMA never goes counter-trend
at a real M5 entry (0/885, any window 3-20 bars, confirmed twice). The 150
EMA does (84-123/885 depending on window) - a real, non-trivial population,
worth testing properly rather than dismissing alongside the 600 result.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S


def tail_concentration(trades):
    if not trades:
        return None
    pnl = sorted([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades], reverse=True)
    net = sum(pnl)
    top20 = sum(pnl[:20])
    return dict(net=round(net, 2), top20_pct=round(100 * top20 / net, 1) if net else float("nan"))


def permutation_test(base_trades, candidate_trades, n_draws=2000, seed=0):
    rng = np.random.default_rng(seed)
    k = len(candidate_trades)
    pnl_all = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in base_trades])
    real_net = sum((t["exit_px"] - t["entry_px"]) * t["dir"] for t in candidate_trades)
    if k == 0 or k > len(pnl_all):
        return None
    draws = np.array([pnl_all[rng.choice(len(pnl_all), size=k, replace=False)].sum()
                       for _ in range(n_draws)])
    pct = 100 * (draws < real_net).mean()
    return dict(percentile=round(pct, 1), real_net=round(real_net, 2))


def split_stats(trades, n_total, is_frac=0.7):
    cutoff = int(n_total * is_frac)
    is_t = [t for t in trades if t["entry_i"] < cutoff]
    oos_t = [t for t in trades if t["entry_i"] >= cutoff]
    return S.stats(is_t), S.stats(oos_t)


df = E.load_m5(); h4 = E.load_h4()
ctx = E.build_context(df, h4, params=E.P)
n = ctx["n"]
base_trades = S.simulate(ctx, params=E.P)
print("BASELINE:", S.stats(base_trades))
print()

atr = ctx["atr"]; m150 = ctx["m150"]

for sb in [3, 5, 10, 20]:
    slope150 = np.full(n, np.nan)
    slope150[sb:] = (m150[sb:] - m150[:-sb]) / atr[sb:]

    def filt(ctx_unused, i, is_buy, slope150=slope150):
        if np.isnan(slope150[i]):
            return True
        counter = (slope150[i] < 0) if is_buy else (slope150[i] > 0)
        return not counter

    trades = S.simulate(ctx, params=E.P, extra_filter=filt)
    blocked = len(base_trades) - len(trades)
    st = S.stats(trades)
    tail = tail_concentration(trades)
    print(f"slope_bars={sb}: blocked={blocked} n={st['n']} net={st['net']:.2f} pf={st['pf']:.3f} "
          f"win={st['win_rate']:.3f} top20={tail['top20_pct']}%")

    base_keys = {(t["entry_i"], t["dir"]): t for t in base_trades}
    cand_keys = {(t["entry_i"], t["dir"]) for t in trades}
    removed = [t for k, t in base_keys.items() if k not in cand_keys]
    if removed:
        pnl_removed = [(t["exit_px"] - t["entry_px"]) * t["dir"] for t in removed]
        wins = [p for p in pnl_removed if p > 0]
        print(f"   removed trades: n={len(removed)} net={sum(pnl_removed):.2f} win_rate={len(wins)/len(removed):.3f}")
        perm = permutation_test(base_trades, trades)
        print(f"   permutation (candidate's kept trades vs random same-size draw): {perm}")
        b_is, b_oos = split_stats(base_trades, n)
        c_is, c_oos = split_stats(trades, n)
        print(f"   IS: base={b_is['net']:.2f} cand={c_is['net']:.2f}  OOS: base={b_oos['net']:.2f} cand={c_oos['net']:.2f}")
    print()
