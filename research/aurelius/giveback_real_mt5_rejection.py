"""
REAL MT5 RESULT (2026-09-25) for InpUseGivebackExit on Aurelius_EA.mq5 v1.50 -
the user ran a real A/B Strategy Tester pair (live GOLD 382043238, M5,
2023.01.01-2026.09.25, identical inputs otherwise, only InpUseGivebackExit
toggled) and it REJECTS the Python estimate from giveback_generalization_test.py
(+39% net, positive IS/OOS) - the real result is -64.3% net. Not a re-runnable
script (the two .xlsx Strategy Tester reports aren't part of this repo's data
pipeline) - this file exists only to record the real numbers and the honest
post-mortem next to the Python research that got it wrong, so nobody trusts
giveback_generalization_test.py's conclusion again without re-reading this.

REAL NUMBERS (both reports, same window/inputs, InpUseGivebackExit only diff):
  default (false): 924 trades, net 35844.76, PF 1.563607, win 28.90%,
    avg win 372.45, avg loss -96.80, largest win 3505.86
  InpUseGivebackExit=true: 1043 trades (+12.9%), net 12811.42 (-64.3%),
    PF 1.274797, win 48.13% (roughly doubled, as predicted), avg win 118.39
    (-68.2%), avg loss -86.18, largest win 2143.58 (-38.8%)

WIN RATE DIRECTION WAS RIGHT, MAGNITUDE WAS CATASTROPHICALLY WRONG. Cutting
small-peak givebacks did roughly double the win rate, exactly as the Python
research predicted (13.7-31.2% win% on small-peak givebacks vs 66.0% on
big-peak ones). But two things the Python test could not see:

1. SINGLE-POSITION CASCADE (most likely dominant cause): giveback_generalization_
   test.py swapped ONLY the exit onto the SAME fixed list of already-real
   entries (sim.py's simulate() ran ONCE with the real baseline exit to produce
   the entry list, then a post-hoc script re-priced only the giveback-affected
   trades' exits). It never re-ran entry gating with the new exit timing feeding
   back into which LATER entries become possible - exactly the blind spot this
   project has hit before (Meridian's real stale-ticket-bar note, the same
   project-wide lesson). An earlier real exit frees the single-position slot
   sooner; real trade count rose 924->1043 (+119, +12.9%) and average win size
   collapsed 372->118 (-68%), both consistent with "more, weaker trades filled
   the freed slots" rather than with the feature working as designed (only
   removing genuinely bad small-peak trades, leaving everything else
   untouched).

2. TICK-LEVEL (real) vs BAR-LEVEL (Python) peak tracking, not yet isolated from
   #1: the real EA checks every tick; giveback_generalization_test.py's
   analyze_generic() only checked each M5 bar's high/low once. Whether this
   alone would have meaningfully changed which trades got cut, independent of
   the cascade effect, was not tested separately before this real result came
   back - an open question if this ever gets revisited.

PORTFOLIO IMPACT: the identical feature was shipped, same Python-only method,
same undetected blind spot, on Meridian_EA.mq5, Aurelius_M15_EA.mq5,
Vanguard_EA.mq5, Vanguard_M15_EA.mq5 - none of those have a real MT5 result
yet. Given this real rejection on the one file that HAS been tested, none of
the other four should be trusted, let alone turned on, until each gets its
own real A/B Strategy Tester run. The "generalizes to 5 systems" conclusion
from giveback_generalization_test.py / giveback_generalization_m15_test.py
is retracted as unconfirmed pending that.

A methodologically honest re-test, if this is revisited, would need a real
EVENT-DRIVEN re-simulation (new exit rule wired into the actual entry-gating
loop, so a freed slot can produce a genuinely different, later entry - the
same fix already applied to msim.py/sim.py for other candidates in this
project) rather than a post-hoc swap on a fixed entry list.
"""
