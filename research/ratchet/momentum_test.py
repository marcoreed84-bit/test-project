"""
Step 4: the momentum-entry test the user asked for, done properly.

Real evidence (decompose.py): in Backtest_2, the 90 real trades whose trigger
was FreshAligned() (momentum) lost -3,182.78 ZAR at PF 0.44; the 345 pullback
trades made +10,146.73 ZAR at PF 1.515. But a static "delete the momentum
rows" read is exactly the mistake MSG v1.13 made - with one position at a
time, the cooldown and the 3-loss breaker, removing an entry changes which
later setups fire. So the verdict comes from the sequential simulator:
momentum ON vs OFF, under both wick settings, in every calendar year the M5
export covers (2023/2024/2025 are pure out-of-sample for the simulator - it
was only ever validated against the 2026 reports), 24 execution-noise seeds
each (ATR-scaled noise, see noise.py), plus the 2026 window under all three
execution models so the verdict can't be an artifact of one noise model.
"""
import sys
from dataclasses import replace

import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import noise as N   # noqa: E402
import sim as S     # noqa: E402

PERIODS = [("2023", "2023-01-02", "2024-01-01"), ("2024", "2024-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01"), ("2026 Jan-Sep", "2026-01-01", "2026-09-21")]


def row(df):
    return dict(n=df.n.mean(), mom=df.mom_n.mean(), net=df.net.mean(), sd=df.net.std(), pf=df.pf.mean(),
                dd=df.closed_dd.mean(), pwin=None)


if __name__ == "__main__":
    out = []
    for wick in (True, False):
        base = replace(S.SHIPPED, wick=wick)
        for name, a, b in PERIODS:
            off = N.mc(replace(base, momentum=False), start=pd.Timestamp(a), end=pd.Timestamp(b))
            on = N.mc(replace(base, momentum=True), start=pd.Timestamp(a), end=pd.Timestamp(b))
            print(f"wick {'ON ' if wick else 'OFF'} {name:<13} OFF: n={off.n.mean():6.1f} net={off.net.mean():7.1f} "
                  f"PF={off.pf.mean():.3f} DD={off.closed_dd.mean():6.1f} | ON: n={on.n.mean():6.1f} "
                  f"(mom {on.mom_n.mean():5.1f}) net={on.net.mean():7.1f} PF={on.pf.mean():.3f} "
                  f"DD={on.closed_dd.mean():6.1f} | ON-OFF net {on.net.mean()-off.net.mean():+7.1f} "
                  f"({100*(on.net.mean()/off.net.mean()-1):+.0f}%), DD {100*(on.closed_dd.mean()/off.closed_dd.mean()-1):+.0f}%",
                  flush=True)
            out.append((wick, name, off, on))
    print("\n2026 window, all three execution models (wick ON = shipped):")
    for mode in ("none", "usd", "atr"):
        off = N.mc(replace(S.SHIPPED, momentum=False), mode=mode, seeds=range(48))
        on = N.mc(S.SHIPPED, mode=mode, seeds=range(48))
        print(f"  {mode:<4}  OFF net={off.net.mean():6.1f} PF={off.pf.mean():.3f} DD={off.closed_dd.mean():5.1f}   "
              f"ON net={on.net.mean():6.1f} PF={on.pf.mean():.3f} DD={on.closed_dd.mean():5.1f}")
