"""Tailwind_EA.mq5 independent re-validation driver.

Reproduces (or fails to reproduce) the header's claimed
  full n=835 PF=1.29 net=$1959 / train PF=1.14 net=$473 / holdout PF=1.42 net=$1486
from the real shipped `input` defaults, on the same 70/30 chronological split
convention used for ichimoku/slipstream.
"""
import importlib.util
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


E = _load("engine_tailwind", "engine.py")
M = _load("sim_tailwind", "sim.py")


# ----------------------------------------------------------- chk_* validation
def chk_report(d):
    c = d["close"].values.astype(float)
    h = d["high"].values.astype(float)
    l = d["low"].values.astype(float)
    out = []
    for n, col in ((3, "chk_ema3"), (21, "chk_ema21"), (150, "chk_ema150")):
        ref = d[col].values.astype(float)
        mine = E.ema_mt5(c, n)
        m = np.isfinite(ref) & (np.abs(ref) < 1e6) & np.isfinite(mine)
        m[:400] = False
        err = np.abs(np.round(mine[m], 2) - ref[m])
        out.append(f"  EMA{n:<3d} vs {col}: n={m.sum()} maxerr={err.max():.4f} "
                   f"mean={err.mean():.5f}  (chk cols are 2-dp rounded)")
    ref = d["chk_atr14"].values.astype(float)
    sma_tr = E.atr_mt5(h, l, c, 14)
    wil = E.S.atr_wilder(h, l, c, 14) if hasattr(E.S, "atr_wilder") else None
    m = np.isfinite(ref) & (np.abs(ref) < 1e6) & np.isfinite(sma_tr)
    m[:400] = False
    e1 = np.abs(np.round(sma_tr[m], 2) - ref[m])
    out.append(f"  ATR14 SMA-of-TR vs chk_atr14: n={m.sum()} maxerr={e1.max():.4f} mean={e1.mean():.5f}")
    if wil is not None:
        mw = m & np.isfinite(wil)
        e2 = np.abs(np.round(wil[mw], 2) - ref[mw])
        out.append(f"  ATR14 Wilder    vs chk_atr14: n={mw.sum()} maxerr={e2.max():.4f} mean={e2.mean():.5f}")
    return "\n".join(out)


def run(label, ctx, p, i0, sig=None, **kw):
    t0 = time.time()
    tr = M.simulate(ctx, p, sig=sig, **kw)
    full = M.stats(tr)
    a, b, cut = M.split_stats(tr, i0, ctx["n"])
    print(f"{label}")
    print(f"   full    {M.fmt(full)}")
    print(f"   train   {M.fmt(a)}")
    print(f"   holdout {M.fmt(b)}    [{time.time()-t0:.1f}s]")
    return tr, full, a, b


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2013-01-01"
    d, i0 = E.load_h4(start=start)
    print(f"data: {d['time'].iloc[0]} .. {d['time'].iloc[-1]}  bars={len(d)}  "
          f"tradable from {d['time'].iloc[i0]} (index {i0})")
    print("chk_* reference-column validation:")
    print(chk_report(d))

    p = E.params()
    ctx = E.build_context(d, p)
    sig = E.base_signals(ctx, p)
    print(f"\nraw signal bars (pre-position/cooldown/shadow): "
          f"{int((sig[0] != 0).sum())}  (long {int((sig[0]==1).sum())} / "
          f"short {int((sig[0]==-1).sum())})")

    print("\n=== SHIPPED DEFAULTS (InpAvoidOpposing=true) ===")
    run("shipped", ctx, p, i0, sig=sig)

    print("\n=== InpAvoidOpposing = FALSE (the filter's own baseline) ===")
    run("no-shadow", ctx, p, i0, sig=sig, avoid_opposing=False)


if __name__ == "__main__":
    main()
