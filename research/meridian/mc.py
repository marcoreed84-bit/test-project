"""
Execution noise + Monte Carlo runner for msim.py - same method as
research/ratchet/noise.py, measured on Meridian's OWN two real reports:
entry offset (real fill vs bar open, in ATR units) and SL-fill slippage (real
exit vs the resting SL in the deal comment, ATR units), drawn per trade.

Also: an M5 mark-to-market equity drawdown (USD, and % of the running peak on
a 10,000 ZAR = $607 deposit at the window's realized ~16.5 ZAR/USD), since
the real reports' headline drawdown is an EQUITY figure and Meridian holds
trades for hours (avg 4h10m) - closed-trade DD understates it.
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/meridian")
sys.path.insert(0, "/home/user/test-project/research/ratchet")
import msim as M    # noqa: E402
import report as R  # noqa: E402

DEP_USD = 10000.0 / 16.5
_CTX = None
_NOISE = None


def key(ts):
    return pd.Timestamp(ts).floor("5min")


def measure(ctx):
    ent, slp = [], []
    for path, p in [(R.MERIDIAN_BT1, M.BT1_BINARY), (R.MERIDIAN_BT2, M.V102)]:
        sk = {key(t["entry_time"]): t for t in M.simulate(ctx, p)[0]}
        for r in R.load(path):
            s = sk.get(key(r["entry_time"]))
            if s is None or s["dir"] != r["side"]:
                continue
            ent.append((r["entry"] - s["entry"]) * r["side"] / s["atr"])
            if r["reason"] == "SL":
                slp.append((r["exit"] - float(r["last_comment"][3:])) * r["side"] / s["atr"])
    return np.array(ent), np.array(slp)


def get_ctx():
    global _CTX, _NOISE
    if _CTX is None:
        _CTX = M.build_ctx()
        _NOISE = measure(_CTX)
    return _CTX, _NOISE


def equity_dd(ctx, trades, dep=DEP_USD):
    h, l, sp = ctx["h"], ctx["l"], ctx["spread"] * M.POINT
    peak, bal, best, bestp = dep, dep, 0.0, 0.0
    for x in trades:
        a, b, d = x["entry_i"], x["exit_i"], x["dir"]
        if d > 0:
            fh, fl = h[a:b + 1] - x["entry"], l[a:b + 1] - x["entry"]
        else:
            fh, fl = x["entry"] - (l[a:b + 1] + sp[a:b + 1]), x["entry"] - (h[a:b + 1] + sp[a:b + 1])
        if len(fl):
            fl[-1] = max(fl[-1], min(x["pnl"], 0.0) if x["reason"] == "SL" else fl[-1])
        for k in range(len(fh)):
            dd = peak - (bal + fl[k])
            if dd > best:
                best, bestp = dd, dd / peak
            peak = max(peak, bal + fh[k])
        bal += x["pnl"]
        peak = max(peak, bal)
    return best, bestp


def _run(args):
    p, seed, start, end, mode = args
    ctx, (ent, slp) = get_ctx()
    if mode == "none":
        q = replace(p, entry_noise=None, sl_slip=np.array([slp.mean()]), noise_in_atr=True, seed=seed)
    else:
        q = replace(p, entry_noise=ent, sl_slip=slp, noise_in_atr=True, seed=seed)
    tr, st = M.simulate(ctx, q, start=start, end=end)
    s = M.stats_of(tr)
    s["eq_dd"], s["eq_ddp"] = equity_dd(ctx, tr)
    return s


def mc(p, seeds=range(24), start=M.WIN_START, end=M.WIN_END, mode="atr", workers=4):
    if mode == "none":
        seeds = [0]
    with ProcessPoolExecutor(workers, initializer=get_ctx) as ex:
        rows = list(ex.map(_run, [(p, s, start, end, mode) for s in seeds]))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ctx, (ent, slp) = get_ctx()
    print(f"entry offset (ATR, + = real worse): n={len(ent)} mean {ent.mean():+.4f} sd {ent.std():.4f}")
    print(f"SL slippage  (ATR, - = real worse): n={len(slp)} mean {slp.mean():+.4f} max {slp.max():+.4f}")
    for lbl, p, path in [("BT1 binary", M.BT1_BINARY, R.MERIDIAN_BT1), ("v1.02", M.V102, R.MERIDIAN_BT2)]:
        df = mc(p, seeds=range(48))
        rs = R.summary([t["pnl_usd"] for t in R.load(path)])
        print(f"{lbl:<11} SIM MC n={df.n.mean():.0f} net=${df.net.mean():.1f} (sd {df.net.std():.1f}) "
              f"PF={df.pf.mean():.3f} eqDD=${df.eq_dd.mean():.0f} ({100*df.eq_ddp.mean():.1f}%) | REAL n={rs['n']} "
              f"net=${rs['net']:.1f} PF={rs['pf']}  -> real net pct in MC {100*(df.net < rs['net']).mean():.0f}%")
