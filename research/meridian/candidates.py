"""
Step 4: "find something new" for Meridian - candidates that come out of this
session's EA-vs-model findings, not re-runs of the ideas research/aurelius
already rejected in Python (breakeven, fixed TP, partial scale-out, vol-sized
lots, 13/21-style fast exits, entry-breach, Price21Exit, ATR-percentile and
H4-trend filters, M15 - see their own docstrings/commits).

Judged ONLY through the validated sequential simulator (msim.py), 24 noise
seeds per period, so every cascade (a skipped or added entry changing which
later cross gets the one slot) is inside the result.

Adoption bar, fixed BEFORE running (same as research/ratchet/candidates.py):
  * mean net better than v1.02 in >= 3 of 4 periods (2023/2024/2025 are
    out-of-sample for the simulator; 2026 = the real-report window), AND
  * better in 2026 under both the noisy ('atr') and deterministic ('none')
    execution models, AND
  * worst-period equity DD not worse than v1.02's by more than 2%.

Candidates:
  sar        - stop-and-reverse: on a REVERSAL close, run the entry check on
               the same bar (the EA currently can't - see msim.py docstring;
               every Python number that justified Meridian assumed it could).
  no_stale   - fix the stale-ticket quirk (enter on the bar after an SL).
  slcd3/6    - the opposite direction: widen the quirk into a deliberate
               3- / 6-bar no-entry cooldown after an SL fill (the 16 real-
               window crosses the quirk drops were net losers, -$129.91).
  fri23      - Friday flatten at 23:00 instead of 22:00 (still flat for the
               weekend - the Python-rules comparison showed the 22:00 flatten
               is the single largest EA-vs-model net difference in 2026).
"""
import sys
from dataclasses import replace

import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/meridian")
import mc as MC     # noqa: E402
import msim as M    # noqa: E402

PERIODS = [("2023", "2023-01-02", "2024-01-01"), ("2024", "2024-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01"), ("2026", "2026-01-01", "2026-09-21")]
BASE = M.V102
CANDS = {
    "v1.02 (base)": BASE,
    "sar": replace(BASE, stop_and_reverse=True),
    "no_stale": replace(BASE, stale_ticket_bar=False),
    "sar+no_stale": replace(BASE, stop_and_reverse=True, stale_ticket_bar=False),
    "slcd3": replace(BASE, sl_cooldown=3),
    "slcd6": replace(BASE, sl_cooldown=6),
    "fri23": replace(BASE, fri_close=23),
}

if __name__ == "__main__":
    only = sys.argv[1:] or list(CANDS)
    res = {}
    for name in ["v1.02 (base)"] + [c for c in only if c != "v1.02 (base)"]:
        p = CANDS[name]
        rows = []
        for per, a, b in PERIODS:
            df = MC.mc(p, start=pd.Timestamp(a), end=pd.Timestamp(b))
            rows.append((per, df.n.mean(), df.net.mean(), df.pf.mean(), df.eq_dd.mean()))
        df = MC.mc(p, mode="none")
        rows.append(("2026/none", df.n.mean(), df.net.mean(), df.pf.mean(), df.eq_dd.mean()))
        res[name] = rows
        b = res["v1.02 (base)"]
        line = " | ".join(f"{r[0]} n{r[1]:4.0f} ${r[2]:7.1f} PF{r[3]:.3f} eqDD{r[4]:5.1f}"
                          + ("" if name == "v1.02 (base)" else f" ({r[2]-br[2]:+.1f})")
                          for r, br in zip(rows, b))
        print(f"{name:<13} {line}", flush=True)
        if name != "v1.02 (base)":
            wins = sum(r[2] > br[2] for r, br in zip(rows[:4], b[:4]))
            m26 = all(r[2] > br[2] for r, br in zip(rows[3:], b[3:]))
            wdd, bwdd = max(r[4] for r in rows[:4]), max(r[4] for r in b[:4])
            ok = wins >= 3 and m26 and wdd <= 1.02 * bwdd
            print(f"{'':<13} -> periods better {wins}/4, 2026 both exec models better {m26}, 4-period net "
                  f"{sum(r[2] for r in rows[:4]) - sum(r[2] for r in b[:4]):+.1f}, worst-period eqDD "
                  f"{wdd:.1f} vs {bwdd:.1f} => {'PASS' if ok else 'FAIL'}", flush=True)
