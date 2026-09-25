"""
Scale-up of head_shoulders_target_test.py to M15 (2026-09-25) - unlike the
straight-trendline construction (m15_touch_reaction_walkforward.py: 1
valid line, 0 usable touches on M15, because a no-pierce-between-anchors
line fit can't survive M15's much higher bar-count noise per unit of real
time), H&S pattern detection is a 5-swing SHAPE match, not a straight-line
fit - already confirmed to transfer fine to D1 (71 confirmed breakouts,
zero straight trendlines) despite that same noise-vs-bar-count mismatch,
so M15 is worth testing on its own merits rather than assuming it fails
the same way the trendline construction did.

Reuses run() directly from head_shoulders_target_test.py - identical
construction, identical walk-forward reporting, only the data source
changes.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import engine as E
from head_shoulders_target_test import run

if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    run(df15, "M15 (resampled from real GOLD# M5)")
