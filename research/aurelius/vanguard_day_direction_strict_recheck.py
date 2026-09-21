"""
Stricter re-check of day_direction_filter_test.py's Vanguard result,
after aurelius_day_direction_filter_test.py's proper test on Aurelius's
side showed the day-direction filter provides NO real marginal value
there (47.4th percentile on a permutation-null drawn from the base
model's own trades) despite a strong raw retrospective signal - the
exact kind of illusory improvement a weaker "random-direction" control
(what day_direction_filter_test.py used) can miss, since it tests "is
this signal better than pure random chance" rather than "does this
filter add value beyond what the base construction's OWN already-
filtered trade population already captures".

Re-tests Vanguard's +VWAP+S/R+day-direction result with the stricter
null (sr_reject_test.py's own methodology: random same-size draws from
the BASELINE +VWAP+S/R trades themselves, not shuffled event
directions) to make sure that result wasn't the same kind of illusion.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered

FRACTAL_K = 100
MIN_SR = 0.50


def permutation_test_own_trades(base_trades, candidate_net, candidate_n, n_draws=2000, seed=0):
    rng = np.random.default_rng(seed)
    pnl_all = np.array([t[2] for t in base_trades])
    if candidate_n == 0 or candidate_n > len(pnl_all):
        return None
    draws = np.array([pnl_all[rng.choice(len(pnl_all), size=candidate_n, replace=False)].sum()
                       for _ in range(n_draws)])
    pct = 100 * (draws < candidate_net).mean()
    return dict(percentile=pct, null_mean=draws.mean(), null_std=draws.std())


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

    import pandas as pd
    dates = df5["time"].dt.date.values
    day_open = pd.Series(close).groupby(pd.Series(dates)).transform("first").values
    day_dir_sign = np.sign(close - day_open)

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)

    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < MIN_SR)
    vwap_sr_ok = vwap_ok & sr_ok
    day_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        day_ok[i] = (day_dir_sign[i] == d)
    combo_ok = vwap_sr_ok & day_ok

    base_trades, _ = sim_trendline_filtered(events, vwap_sr_ok, close, high, low, spread, atr, n)
    cand_trades, _ = sim_trendline_filtered(events, combo_ok, close, high, low, spread, atr, n)

    base_net = sum(t[2] for t in base_trades)
    cand_net = sum(t[2] for t in cand_trades)
    print(f"baseline  (+VWAP+S/R): n={len(base_trades)} net={base_net:.2f}")
    print(f"candidate (+day-dir):  n={len(cand_trades)} net={cand_net:.2f}")

    perm = permutation_test_own_trades(base_trades, cand_net, len(cand_trades), n_draws=2000)
    print(f"\npermutation test (candidate's {len(cand_trades)} trades' net vs random same-size draws")
    print(f"from baseline's OWN {len(base_trades)} trades):")
    print(f"  percentile={perm['percentile']:.1f}  null_mean={perm['null_mean']:.2f}  null_std={perm['null_std']:.2f}")
