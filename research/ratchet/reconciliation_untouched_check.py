"""
Ratchet reconciliation, parallel to Meridian's (see commit d922742 and
research/meridian/msim.py's own docstring). Unlike Meridian, sim.py was
NOT found to have a mechanism-fidelity gap against the real EA - every
input default in Ratchet_EA.mq5 (wick-reject, momentum, trail, trail-
runner, breakeven, stochastic exit, max-bars, session/Friday/holiday
gates, cooldown, consec-loss breaker, max-spread) matches RP/SHIPPED in
sim.py field-for-field, and validate.py already bar-matches sim.py
against BOTH real 2026-09-23 Strategy Tester reports (Backtest_1:
momentum OFF/wick OFF, 95.5% entry-bar match, net/PF within ~10%;
Backtest_2: momentum ON/wick ON, only 77.4% match, sim net $773 vs real
$510 - sim OVERSTATES real performance on that config). noise.py already
measured (not assumed) the residual gap from those bar-matches: a random
per-trade entry-fill offset (tester execution delay, ~zero-mean) and SL
slippage that is NEVER favorable (mean -0.15 ATR-equivalent, always
worse than the resting SL's own comment price).

What WAS missing: neither the original "survives decisively" run nor the
untouched-2014-2022 check (ratchet_untouched_oos_check.py) applied this
measured noise model - both used a deterministic, noise-free simulator.
Since the measured noise is unbiased on entry but strictly adverse on SL
fills, a noise-free sim is, if anything, an OPTIMISTIC estimate of real
performance. This file re-runs the untouched-window check through
noise.mc()'s ATR-scaled Monte Carlo (the same model already used to
judge every other Ratchet candidate in this folder), on the exact
current SHIPPED config (momentum=False, wick=True, trail_runner_atr=6.0),
to see whether that changes the verdict.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(1, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import sim as S
import noise as N
import engine as E
from ratchet_random_timing_test import make_random_entry_signal, pct_pf

CUTOFF = pd.Timestamp("2022-07-04")
START = pd.Timestamp("2014-07-01")
N_SEEDS = 48
N_RANDOM = 200


def build_untouched_ctx():
    m5x = E.load_m5_extended()
    oos = m5x[m5x["time"] < CUTOFF][["time", "open", "high", "low", "close", "tick_volume", "spread"]].reset_index(drop=True)
    return S.build_ctx(oos)


if __name__ == "__main__":
    ctx_2026, noise = N.get_ctx()          # the measured (entry_offset, sl_slip) arrays, ATR units
    ent, slp = noise["atr"]
    ctx = build_untouched_ctx()

    print(f"Ratchet SHIPPED (momentum={S.SHIPPED.momentum}, wick={S.SHIPPED.wick}, "
          f"trail_runner_atr={S.SHIPPED.trail_runner_atr}) - untouched {START.date()} -> {CUTOFF.date()}")
    print(f"Execution noise measured from real 2026 bar-matches: entry offset mean {ent.mean():+.4f} ATR "
          f"(sd {ent.std():.4f}), SL slippage mean {slp.mean():+.4f} ATR (max {slp.max():+.4f}, i.e. never favorable)")

    # deterministic (noise-free) baseline, for comparison with the original 18ed3c2 check
    det, _ = S.simulate(ctx, S.SHIPPED, start=START, end=CUTOFF)
    det_pf = pct_pf(det)
    det_pn = np.array([t["pnl"] / t["entry"] for t in det])
    print(f"\nDeterministic (noise-free, matches the original 18ed3c2 check): "
          f"n={len(det)} win%={100*(det_pn>0).mean():.1f} %PF={det_pf:.3f} net%={100*det_pn.sum():.1f}")

    # Monte Carlo with the REAL measured execution noise, ATR-scaled (usable on any year per noise.py's own docstring)
    rows = []
    for seed in range(N_SEEDS):
        q_ent, q_slp = ent, slp
        from dataclasses import replace
        p = replace(S.SHIPPED, entry_noise=q_ent, sl_slip=q_slp, noise_in_atr=True, seed=seed)
        tr, _ = S.simulate(ctx, p, start=START, end=CUTOFF)
        pn = np.array([t["pnl"] / t["entry"] for t in tr])
        rows.append(dict(n=len(tr), pf=pct_pf(tr), net_pct=100 * pn.sum()))
    mcdf = pd.DataFrame(rows)
    print(f"\nMonte Carlo with REAL measured execution noise ({N_SEEDS} seeds, ATR-scaled): "
          f"n={mcdf.n.mean():.1f}  %PF mean={mcdf.pf.mean():.3f} (sd {mcdf.pf.std():.3f}, "
          f"5-95% {mcdf.pf.quantile(.05):.3f}..{mcdf.pf.quantile(.95):.3f})  "
          f"net%={mcdf.net_pct.mean():.1f} (sd {mcdf.net_pct.std():.1f})")

    # random-timing null, run through the SAME noisy execution model for a fair comparison
    def run_random(rng, p_fire, use_noise):
        orig = S.entry_signal
        S.entry_signal = make_random_entry_signal(rng, p_fire)
        try:
            if use_noise:
                from dataclasses import replace
                p = replace(S.SHIPPED, entry_noise=ent, sl_slip=slp, noise_in_atr=True, seed=int(rng.integers(0, 10**6)))
            else:
                p = S.SHIPPED
            tr, _ = S.simulate(ctx, p, start=START, end=CUTOFF)
        finally:
            S.entry_signal = orig
        return tr

    rng = np.random.default_rng(1)
    p_fire = 0.01
    target_n = int(mcdf.n.mean())
    for _ in range(4):
        tr = run_random(rng, p_fire, use_noise=False)
        p_fire = min(max(p_fire * target_n / max(len(tr), 1), 1e-5), 0.9)
    rng = np.random.default_rng(42)
    pool = np.array([pct_pf(run_random(rng, p_fire, use_noise=True)) for _ in range(N_RANDOM)])
    pool = pool[np.isfinite(pool)]
    real_pf_mc = mcdf.pf.mean()
    pct = 100 * (pool < real_pf_mc).mean()
    p = (pool >= real_pf_mc).mean()
    print(f"\nrandom-timing null, SAME noisy execution model ({len(pool)} draws): "
          f"median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    print(f"REAL (noise-adjusted mean) %PF={real_pf_mc:.3f} -> {pct:.1f}th percentile; p(K=1)={p:.4f}")

    # per-seed comparison against the SAME random pool (accounts for MC variance on both sides)
    beat = np.mean([(pool >= row.pf).mean() for row in mcdf.itertuples()])
    print(f"Averaged per-seed p-value (each noisy real draw vs the random pool): {beat:.4f}")
