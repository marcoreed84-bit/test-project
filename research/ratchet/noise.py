"""
Execution-noise model for sim.py, measured (not assumed) from the two real
2026-09-23 Ratchet reports, plus the Monte Carlo evaluator every candidate in
this folder is judged with.

Why this exists: bar-matching the real trades (validate.py) showed the sim's
trail/breakeven arithmetic is exact - on the 1,090 trades exiting via SL on
the same bar in both, the sim's resting SL matches the real one to a median
$0.07 absolute with no bias (the cents are the entry offset below feeding the
breakeven level) - but two things the bar data cannot see drive the rest:

  1. ENTRY OFFSET: the tester ran with a random execution delay (real entry
     fill lands a median 4-5s, up to 18s, past the bar open), so it differs from
     the bar open by a random amount (median ~$0.05, sd ~$0.9, a few >$5 on
     fast bars). Because Ratchet's breakeven (0.3 ATR) and trail (0.5 ATR)
     trigger within a bar or two of entry, a ~$1 entry difference routinely
     flips WHICH bar the stop first moves on, which flips the trade outcome
     (validate.py examples: 2026-06-05 16:20 short, real +$1.55 vs bar-open
     +$95; 2026-01-26 05:05 long, real -$18 vs bar-open $0.00). Individually
     unpredictable, so it is modeled as a random draw per trade.
  2. SL SLIPPAGE: every real SL fill is at or worse than the resting SL level
     in its comment (mean -$0.15, both directions alike, never better).

A single deterministic sim path is therefore one draw from a noisy process.
Every configuration here is run over N seeds and judged on the distribution.
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import report as R  # noqa: E402
import sim as S     # noqa: E402

_CTX = None
_NOISE = None


def key(ts):
    return pd.Timestamp(ts).floor("5min")


def measure(ctx):
    """Empirical (entry_offset, sl_slip) arrays from both real reports, in
    ATR-at-entry units, so the same measured noise scales correctly when the
    simulator is run on 2023-2025 bars (gold's M5 ATR was a fraction of its
    2026 level then - a fixed-dollar noise draw would overstate it there)."""
    ent, slp = [], []
    for path, p in [(R.RATCHET_BT1, S.BASELINE), (R.RATCHET_BT2, S.SHIPPED)]:
        real = R.load(path)
        simt, _ = S.simulate(ctx, p)
        sk = {key(t["entry_time"]): t for t in simt}
        for r in real:
            s = sk.get(key(r["entry_time"]))
            if s is not None and s["dir"] == r["side"]:
                ent.append(((r["entry"] - s["entry"]) * r["side"], s["atr"]))
                if r["reason"] == "SL":
                    slp.append(((r["exit"] - float(r["last_comment"][3:])) * r["side"], s["atr"]))
    ent, slp = np.array(ent), np.array(slp)
    return dict(atr=(ent[:, 0] / ent[:, 1], slp[:, 0] / slp[:, 1]), usd=(ent[:, 0], slp[:, 0]))


def get_ctx():
    global _CTX, _NOISE
    if _CTX is None:
        _CTX = S.build_ctx()
        _NOISE = measure(_CTX)
    return _CTX, _NOISE


def _run(args):
    p, seed, start, end, mode = args
    ctx, noise = get_ctx()
    if mode == "none":      # deterministic bar-open fills + the measured MEAN slippage
        q = replace(p, entry_noise=None, sl_slip=np.array([noise["usd"][1].mean()]), noise_in_atr=False, seed=seed)
    else:
        ent, slp = noise[mode]
        q = replace(p, entry_noise=ent, sl_slip=slp, noise_in_atr=(mode == "atr"), seed=seed)
    tr, st = S.simulate(ctx, q, start=start, end=end)
    return tr, st


def mc(p, seeds=range(24), workers=4, keep_trades=False, start=S.WIN_START, end=S.WIN_END, mode="atr"):
    """mode: 'atr' (noise scaled by ATR - usable on any year), 'usd' (raw
    2026 dollar draws), 'none' (no entry noise, mean slippage only)."""
    if mode == "none":
        seeds = [0]
    with ProcessPoolExecutor(workers, initializer=get_ctx) as ex:
        outs = list(ex.map(_run, [(p, s, start, end, mode) for s in seeds]))
    rows = []
    for tr, st in outs:
        s = S.stats_of(tr)
        s["mom_n"] = sum(1 for x in tr if x.get("kind") == "momentum")
        rows.append(s)
    df = pd.DataFrame(rows)
    return (df, [o[0] for o in outs]) if keep_trades else df


def fmt(df, label):
    return (f"{label:<46} n={df.n.mean():6.1f}  net=${df.net.mean():7.1f} (sd {df.net.std():5.1f}, "
            f"5-95% {df.net.quantile(.05):6.1f}..{df.net.quantile(.95):6.1f})  PF={df.pf.mean():.3f}  "
            f"closedDD=${df.closed_dd.mean():6.1f}")


if __name__ == "__main__":
    ctx, noise = get_ctx()
    ent, slp = noise["atr"]
    print(f"entry offset, ATR units (+ = real worse): n={len(ent)} mean {ent.mean():+.4f} "
          f"median {np.median(ent):+.4f} sd {ent.std():.4f}")
    print(f"SL slippage, ATR units (- = real worse):  n={len(slp)} mean {slp.mean():+.4f} "
          f"median {np.median(slp):+.4f} max {slp.max():+.4f}")
    r1 = R.summary([t["pnl_usd"] for t in R.load(R.RATCHET_BT1)])
    r2 = R.summary([t["pnl_usd"] for t in R.load(R.RATCHET_BT2)])
    print(f"{'REAL    Backtest_1':<46} n={r1['n']:6d}  net=${r1['net']:7.1f}  PF={r1['pf']}")
    print(f"{'REAL    Backtest_2':<46} n={r2['n']:6d}  net=${r2['net']:7.1f}  PF={r2['pf']}")
    for mode in ("none", "usd", "atr"):
        seeds = range(48)
        d1 = mc(S.BASELINE, seeds=seeds, mode=mode)
        d2 = mc(S.SHIPPED, seeds=seeds, mode=mode)
        print(f"--- execution model: {mode}")
        print(fmt(d1, "SIM  BT1 config (mom OFF, wick OFF)"))
        print(fmt(d2, "SIM  BT2 config (mom ON,  wick ON)"))
        if mode != "none":
            print(f"   real Backtest_1 net percentile within sim MC: {100*(d1.net < r1['net']).mean():.0f}%;  "
                  f"real Backtest_2: {100*(d2.net < r2['net']).mean():.0f}%")
