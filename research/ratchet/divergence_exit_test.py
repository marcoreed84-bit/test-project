"""
Divergence-exit screen (2026-09-23) for Ratchet_EA.mq5 (v3.30) - see
research/divergence.py's module docstring for the full construction
(swing-pivot definition, RSI/MACD/Stochastic constructions).

Tests each of RSI(14), MACD histogram (standalone 12/26/9, since Ratchet's own
Stochastic exit is a different, already-used lever at different periods - see
divergence.py's module docstring) and Stochastic(14,3) as an OPTIONAL
EARLY-EXIT trigger layered on top of the real, currently-shipped SHIPPED
config (v3.30 defaults, InpTrailRunnerATR=6.0), via sim.py's new exit_fn hook
- checked right after SESSION_CLOSE and before TAILCAP/TrailStop/STOCH-exit/
MAXBARS, i.e. as early as this simulator's own exit-priority chain allows a
signal-based exit to run. No entry logic, no other exit, and no input default
is touched.

Window: SHIPPED's own default WIN_START/WIN_END (2026-01-01 - 2026-09-21),
same window this file's own real MT5 confirmations (v3.29 momentum test,
v3.30 runner-trail test) both used, deterministic (seed=0, no entry_noise/
sl_slip draws) - a first-pass screen, not the noise.py-calibrated realistic
run validate.py/robust_keep.py use for an adoption decision.

Data/caveats: identical to this folder's other scripts - real M5 bars via
bars.py's loader, USD-per-0.01-lot net.
"""
import sys
from dataclasses import replace

sys.path.insert(0, "/home/user/test-project/research")
sys.path.insert(0, "/home/user/test-project/research/ratchet")
import divergence as D   # noqa: E402
import sim as S          # noqa: E402


def make_exit(bear, bull):
    def f(ctx, t, pos):
        i = t - 1
        if i < 0:
            return None
        sig = bear[i] if pos["dir"] > 0 else bull[i]
        return "DIVERGENCE" if sig else None
    return f


if __name__ == "__main__":
    ctx = S.build_ctx()
    h, l, c = ctx["h"], ctx["l"], ctx["c"]
    print(f"M5 bars: {len(c)}  range {ctx['t64'][0]} .. {ctx['t64'][-1]}")

    sigs = D.all_divergence_signals(h, l, c, n=5)  # macd_hist=None -> standalone 12/26/9 build

    cands = {"baseline (v3.30, no divergence exit)": S.SHIPPED}
    for name in ("rsi", "macd", "stoch"):
        bear, bull = sigs[name]
        cands[f"+ {name.upper()} divergence exit (n=5 pivot)"] = replace(S.SHIPPED, exit_fn=make_exit(bear, bull))

    base_trades, _ = S.simulate(ctx, cands["baseline (v3.30, no divergence exit)"])
    base_st = S.stats_of(base_trades)
    print(f"{'baseline (v3.30, no divergence exit)':<40} n={base_st['n']:4d} "
          f"net=${base_st['net']:9.2f} pf={base_st['pf']:.3f} win={base_st['win']:.1f}% DD=${base_st['closed_dd']:.2f}")

    for label, p in cands.items():
        if label.startswith("baseline"):
            continue
        trades, _ = S.simulate(ctx, p)
        st = S.stats_of(trades)
        n_div = sum(1 for t in trades if t.get("reason") == "DIVERGENCE")
        print(f"{label:<40} n={st['n']:4d} net=${st['net']:9.2f} pf={st['pf']:.3f} "
              f"win={st['win']:.1f}% DD=${st['closed_dd']:.2f}  "
              f"(net {st['net']-base_st['net']:+.2f}, div_exits={n_div})")
