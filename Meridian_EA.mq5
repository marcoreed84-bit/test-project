//+------------------------------------------------------------------+
//|                          Meridian_EA.mq5                          |
//|                                                                    |
//|  NEW, standalone system - NOT a modification of Aurelius_EA.mq5,   |
//|  built from a clean file per the user's explicit request. Entry   |
//|  and exit logic below is exactly the winning construction from    |
//|  this session's research (research/aurelius/m5_stack_variants_    |
//|  fixed_test.py, the corrected version - see that file's header    |
//|  for the bug that was found and fixed in the earlier, uncorrected |
//|  pass before this was trusted):                                   |
//|                                                                    |
//|  entry : 21 EMA crosses the 50 EMA (M5, close-based) AND, at that  |
//|          exact bar, close is on the trend side of BOTH the 150     |
//|          EMA and the session VWAP - buy needs close>150EMA AND     |
//|          close>VWAP, sell the mirror.                              |
//|  exit  : the NEXT raw 21/50 cross in the opposite direction        |
//|          (unconfirmed - no 150/VWAP re-check on exit, matching     |
//|          the validated design: the filter gates entry only, it     |
//|          does not gate the reversal exit) OR a safety stop at      |
//|          InpSafetyStopATR x ATR(14), whichever comes first. No     |
//|          take-profit - this rides the leg until it actually        |
//|          reverses, by design.                                      |
//|                                                                    |
//|  PYTHON BACKTEST (full real M5 history, 2023-01 to 2026-08,        |
//|  256,318 bars, real spread, correct single-position sequencing,    |
//|  random-direction control, 5-block walk-forward - all re-verified  |
//|  after catching and fixing a same-direction-exit bug in the first  |
//|  pass): 2603 trades, net +3184.61 (price-difference $, ~2.9        |
//|  trades/day, median hold 2.6h / mean 5.3h - NOT a scalp), PF       |
//|  1.300, win rate 26.0%, random-direction percentile 99.7,          |
//|  walk-forward 4/5 blocks positive (2023 Jan-Sep is the one losing  |
//|  block, -68, the smallest loss of any construction tried this      |
//|  session there). Closed-trade max drawdown 323 (10.1% of net),     |
//|  bar-by-bar mark-to-market floating max drawdown 391 (12.3% of     |
//|  net).                                                              |
//|                                                                    |
//|  HONEST COMPARISON TO AURELIUS (asked directly before this was     |
//|  built): Aurelius's own real, LIVE MT5 Strategy Tester result      |
//|  (see Aurelius_EA.mq5's header) is PF 1.56 on real-tick execution  |
//|  (Python backtest PF 1.51) - both meaningfully higher than this    |
//|  system's 1.30 (Python) / 1.244 (real, see below). Aurelius's real |
//|  documented weakness is a 27.69% equity drawdown (a position       |
//|  floated ~$1184 underwater once) vs 9.76% balance drawdown - a     |
//|  known, still-being-worked-on risk. Verdict at build time was that |
//|  this does NOT look better than Aurelius, and the real test below  |
//|  CONFIRMS that rather than softening it - real drawdown here is    |
//|  worse than Aurelius's own documented weak point, not better.      |
//|                                                                    |
//|  REAL MT5 STRATEGY TESTER RESULT (2026-09-21, XM Global GOLD#, M5, |
//|  2023.01.01-2026.09.19, 20000 ZAR deposit, InpLots=0.01, real-tick |
//|  execution, 84% real-tick history quality): 2512 trades, PF        |
//|  1.243712 (vs Python's 1.300 - close agreement, confirms the       |
//|  signal is real, not a backtest artifact), win rate 26.75% (vs     |
//|  Python's 26.0%), avg hold 4h13m, net +44899.83 ZAR. BUT: Balance  |
//|  Drawdown Maximal 35.96% (8094.79), Equity Drawdown Maximal        |
//|  36.78% (8324.51) - WORSE than Aurelius's real 27.69%. Reconciled  |
//|  the deal-by-deal balance curve: peak was 2023-06-09, trough was   |
//|  2024-11-06 - a 17-MONTH drawdown before recovery, not one bad     |
//|  trade. Yearly net: 2023 +20365, 2024 -2799 (the losing year the   |
//|  drawdown traces to), 2025 +10218, 2026 +37116. The 0.01-lot /     |
//|  3.0xATR-stop design was never checked against account size before |
//|  this ran - a 20000 ZAR (~$1100) account carrying gold-CFD ATR     |
//|  stops is thin relative to this system's per-trade risk, which is  |
//|  a real contributor to the severity here, not just the signal      |
//|  itself. VERDICT UNCHANGED, REINFORCED: not better than Aurelius,  |
//|  real but not ready to trade as-is - needs either a materially     |
//|  larger account, a tighter/scaled stop, or a real defensive filter |
//|  layer (the thing Aurelius has that this doesn't) before more than |
//|  demo exposure would be responsible.                               |
//|                                                                    |
//|  v1.01 DRAWDOWN WORK (asked directly: "more confluence to cut the  |
//|  losers"): research/aurelius/meridian_dd_confluence_test.py tested |
//|  every filter Aurelius_EA.mq5 already has validated - momentum,    |
//|  pullback, volume ratio, S/R distance, slope, crisscross - on top  |
//|  of this entry. Only S/R distance helped (floating DD 12.3%->11.3% |
//|  of net); momentum/volume/crisscross made DD WORSE despite cutting |
//|  trade count; the slope filter is nearly incompatible with a fresh |
//|  cross by construction (a 21/50 cross happens near the 50 EMA's    |
//|  slope INFLECTION, not after it's already built momentum - only 1  |
//|  of 2603 trades satisfied both). Separately tested Aurelius's own   |
//|  proven drawdown fix (InpUsePrice21Exit-style early exit on price   |
//|  closing back through the 21) via                                   |
//|  research/aurelius/meridian_price21exit_test.py - it made THIS      |
//|  system's drawdown worse at every setting tried (13.1%-34.2% vs     |
//|  12.3% baseline), because unlike Aurelius (slow multi-MA alignment- |
//|  break exit), Meridian's exit is already the fast 21/50 relationship|
//|  - an early exit on the same line just cuts winners short without   |
//|  preventing the real tail-risk trades. Not shipped.                 |
//|                                                                     |
//|  What DID work, combined and verified (Python): the S/R filter      |
//|  above (InpSRDays=3, InpMinSRDistATR=0.50, now wired into           |
//|  CheckForEntry() via SRDistance()) PLUS tightening the safety stop  |
//|  2.5xATR (was 3.0, itself swept - see meridian_dd_confluence_test.py|
//|  for the full grid) - net AND drawdown improved TOGETHER, not a     |
//|  tradeoff (Python numbers here used the mislabeled 250-SMA line,    |
//|  see v1.02 below - directionally same conclusion, exact figures     |
//|  superseded): n=2539, net=3420.71 (was 3184.61), PF=1.356 (was      |
//|  1.300), floating DD 11.1% (was 12.3%), walk-forward 5/5 BLOCKS     |
//|  POSITIVE - the first construction all session to clear every       |
//|  block, including the previously-always-losing 2023 Jan-Sep block   |
//|  (now +6.99, barely positive but real).                             |
//|                                                                     |
//|  REAL MT5 STRATEGY TESTER RESULT, v1.01 (2026-09-21, same setup as   |
//|  v1.00's real test): 2641 trades, PF 1.2824 (vs v1.00's 1.2437),    |
//|  net +51394.84 ZAR (vs +44899.83), Balance DD Maximal 29.00% (vs    |
//|  35.96%), Equity DD Maximal 29.82% (vs 36.78%), Sharpe 2.055 (vs    |
//|  1.756) - confirms the Python direction on BOTH net and drawdown,   |
//|  and the real cut (36.78%->29.82%, ~19% relative) beat the Python   |
//|  model's own ~10% prediction. Same worst-drawdown window (peak      |
//|  2023-06-09, trough 2024-11-06) but shallower (6449.51 vs 8094.79). |
//|  Real but still not enough - this account is thin relative to the   |
//|  position risk regardless of signal quality (see v1.00 section).    |
//|                                                                     |
//|  v1.02 - MISLABELING FOUND AND TURNED INTO A REAL IMPROVEMENT:      |
//|  research/aurelius/engine.py's build_context() ctx['m150'] is       |
//|  Aurelius's REAL, validated p150=250/m150=SMA default (a genuine,   |
//|  documented 2026-09-07 change in Aurelius_EA.mq5 itself, not a bug  |
//|  there) - NOT a 150 EMA as 6 Meridian research scripts assumed      |
//|  while quoting the v1.01 Python numbers above. This file's own code |
//|  was never affected (always computed a literal 150 EMA). Checked    |
//|  both explicitly (meridian_ma_variant_test.py: EMA/SMA/SMMA x       |
//|  close/open, 6-way sweep - EMA-of-close, i.e. what v1.01 shipped,   |
//|  won clearly: net=3253.93 floatDD%=14.9 vs SMA/SMMA's 12.9-39.6%)   |
//|  THEN swept period x method for the confirm line specifically       |
//|  (meridian_slow_confirm_sweep_test.py) - SMA beat EMA at every      |
//|  period tested (150/200/250/300), and 250 SMA (Aurelius's own real  |
//|  choice) won overall: net=3432.72, PF=1.357 (best of the session),  |
//|  floating DD=11.1% (best), walk-forward 5/5, random-direction       |
//|  percentile=100.0 (the single strongest statistical score of the    |
//|  whole session). Adopted: InpP150/InpMAMethod split into            |
//|  InpFastMAMethod (21/50, still EMA) and InpPConfirm=250/             |
//|  InpConfirmMAMethod=SMA (the former "150" line, renamed to avoid    |
//|  repeating the exact confusion that caused this). NOT YET RUN       |
//|  THROUGH A REAL MT5 STRATEGY TESTER AT THESE SETTINGS - needs the   |
//|  same real-test step v1.00 and v1.01 both got before this can be    |
//|  trusted the way those numbers were.                                |
//|                                                                    |
//|  v1.02 REAL TEST + RESEARCH NOTE (2026-09-23, Opus review) - NO    |
//|  LOGIC CHANGE, #property version STAYS 1.02. Four real reports came|
//|  in the same day (two Ratchet, two Meridian); everything below uses|
//|  the two Meridian ones.                                            |
//|                                                                    |
//|  REAL MT5 STRATEGY TESTER RESULT, v1.02 (2026-09-23, XM Global     |
//|  GOLD#, M5, 2026.01.01-2026.09.21, 10000 ZAR deposit, InpLots=0.01,|
//|  100% real ticks; recompiled - all five renamed/new inputs present |
//|  in the report: InpPConfirm=250, InpConfirmMAMethod=SMA,           |
//|  InpFastMAMethod=EMA, InpSRDays=3, InpMinSRDistATR=0.5): 414       |
//|  trades, net +36600.33 ZAR, PF 1.636736, win 29.95%, avg hold      |
//|  4h10m, Balance DD Maximal 4968.25 (14.50%), Equity DD Maximal     |
//|  5690.44 (16.30%). Deals parsed into round-trips by cumulative     |
//|  volume (research/ratchet/report.py): 414 round-trips, exactly one |
//|  out-leg each (no scale-out), profit+commission+swap sums to the   |
//|  report's Total Net Profit to the cent. This closes the v1.02 "not |
//|  yet run through a real MT5 Strategy Tester" gap above.            |
//|                                                                    |
//|  NOT LIKE-FOR-LIKE WITH v1.00/v1.01's REAL NUMBERS. Those ran 20000|
//|  ZAR over 2023.01-2026.09 at 84% tick quality; this is 10000 ZAR   |
//|  over Jan-Sep 2026 only, the strongest gold trend stretch in the   |
//|  data (see per-year table below - 2026 alone out-earns 2023-2025   |
//|  combined on every config). So 36.78% / 29.82% -> 16.30% is NOT a  |
//|  v1.02 drawdown improvement and must not be read as one.           |
//|                                                                    |
//|  THE SAME-WINDOW BASELINE THAT DOES EXIST. The same day's          |
//|  Backtest_1 ran a stale pre-v1.02 binary. Identified exactly, not  |
//|  assumed: its Inputs block has v1.00's layout (InpP150=150,        |
//|  InpMAMethod=EMA) with InpSafetyStopATR=2.5 and NO                 |
//|  InpSRDays/InpMinSRDistATR - a combination no committed version    |
//|  has. The real initial-SL/Wilder-ATR ratio is 2.500 (median), and  |
//|  the EA-faithful simulator (below) matches 471/473 of its real     |
//|  entries to the bar on "150 EMA + VWAP, NO S/R, 2.5 stop", vs 461  |
//|  with v1.01's S/R on and 440 with v1.00's 3.0 stop. Real result:   |
//|  473 trades, net +40882.66 ZAR, PF 1.626120, Balance DD 5141.70    |
//|  (15.09%), Equity DD 6377.98 (21.40%). CONFIRMED same-window       |
//|  comparison, that binary -> v1.02: trades -12.5%, net -10.5%, PF   |
//|  flat (1.626 -> 1.637), equity DD -10.8% in ZAR (21.40% -> 16.30%),|
//|  balance DD -3.4%. A PF-neutral volume cut with net and drawdown   |
//|  shrinking roughly together, NOT the "net AND drawdown improved    |
//|  together" v1.01/v1.02's Python said. (It is two changes at once - |
//|  150 EMA -> 250 SMA AND S/R on - separated below.)                 |
//|                                                                    |
//|  PYTHON PREDICTION vs REAL FILLS, SAME WINDOW                      |
//|  (research/meridian/python_vs_real.py). Re-ran the exact           |
//|  meridian_slow_confirm_sweep_test.py construction; it reproduces   |
//|  the header's full-history 3432.72 / PF 1.357 / n=2537 to the cent,|
//|  so it is the same model. Restricted to 2026-01-01..2026-08-14     |
//|  (engine's GOLD_M5.csv ends there; real trades cut at the same     |
//|  date), in price-$ per 0.01 lot:                                   |
//|                                                                    |
//|              Python predicted         REAL                         |
//|   v1.02      n=412 $2376.52 PF 1.669  n=362 $1987.17 PF 1.629      |
//|   BT1 bin.   n=504 $2315.02 PF 1.532  n=409 $2017.81 PF 1.565      |
//|   BT1->v1.02 net +2.7%                net -1.5% (-10.5% to 09-21)  |
//|                                                                    |
//|  PF held (within 2.5% on v1.02). Trade count and net did not:      |
//|  Python over-counted trades by 14-23% and over-stated v1.02's net  |
//|  by ~20%, and its predicted direction for the change was wrong on  |
//|  this window.                                                      |
//|                                                                    |
//|  WHY - THE EA IS NOT THE PYTHON MODEL. research/meridian/msim.py is|
//|  a bar-by-bar port of this file's                                  |
//|  OnTick/ManageOpenPosition/CheckForEntry (validated: 414/414 of    |
//|  Backtest_2's real entries matched to the bar, 411 exiting on the  |
//|  same bar; on the header's full-history real runs it gives 2511    |
//|  trades vs v1.00's real 2512, win 26.8% vs 26.75%, and reproduces  |
//|  v1.01 having MORE trades than v1.00 - the tighter stop frees the  |
//|  one slot sooner). It exposed four EA-vs-model differences, every  |
//|  one real behavior of this file's code, none a Python bug as such: |
//|  - NOT stop-and-reverse. OnTick runs ManageOpenPosition() OR       |
//|    CheckForEntry(), never both, so the 21/50 cross that closes a   |
//|    trade on REVERSAL can never open the opposite one (next bar it  |
//|    is no longer fresh). Python's sim_filtered_entries() opens it.  |
//|    In the 2026 window 204 reversal-closing crosses are never even  |
//|    evaluated as entries.                                           |
//|  - STALE-TICKET BAR. g_ticket is only re-synced inside             |
//|    ManageOpenPosition()/CheckForEntry(), so after the broker SL    |
//|    fills mid-bar the next new bar still sees g_ticket != 0 and runs|
//|    ManageOpenPosition() (which syncs to flat and returns) instead  |
//|    of CheckForEntry(). A cross on the first bar after an SL        |
//|    stop-out is never traded. Found because it was the only thing   |
//|    the simulator's 16 unmatched Backtest_2 entries had in common   |
//|    (all 16 sat on that bar; real EA flat each time; every condition|
//|    cleared by a wide margin).                                      |
//|  - FRIDAY 22:00 FLATTEN (Python has none) - the largest single net |
//|    difference on the 2026 window: turning just this on in a        |
//|    Python-rules run cuts net 13.5%.                                |
//|  - InpMaxSpreadPoints, and no entries before 01:05 server time     |
//|    (zero real entries at 00:xx or in the 01:00 bar across all four |
//|    2026-09-23 reports - hour-0 bars only exist in DST-gap weeks,   |
//|    outside the broker's session table). Minor.                     |
//|                                                                    |
//|  Run under Python's rules the simulator lands on Python's counts   |
//|  (411 vs 412, 503 vs 504); under the EA's, on the real ones (364 vs|
//|  362, 410 vs 409) - research/meridian/ea_vs_python.py, which also  |
//|  switches each EA rule on alone.                                   |
//|                                                                    |
//|  WHICH v1.02 CHANGE DID WHAT (research/meridian/v102_decompose.py).|
//|  Four corners, validated simulator, 24 seeds of execution noise    |
//|  measured from these two reports (entry offset vs bar open, SL-fill|
//|  slippage). Mean net, price-$ per 0.01 lot; 2023-2025 are          |
//|  out-of-sample for the simulator:                                  |
//|                                                                    |
//|                    2023  2024  2025  2026  total  worst eqDD       |
//|   150 EMA, no SR      3   -84   532  2405   2856  416              |
//|   150 EMA + SR v1.01 31   -67   612  2362   2939  437              |
//|   250 SMA, no SR    -36    25   670  2176   2834  381              |
//|   250 SMA + SR v1.02  8    61   691  2155   2915  382              |
//|                                                                    |
//|  - S/R filter: small and consistent - helps 3 of 4 years under     |
//|    either confirm line (+$81 total), costs a little in 2026.       |
//|  - 250 SMA vs 150 EMA (both with S/R): -$24 over the four periods, |
//|    i.e. noise (per-period sd $29-$142). Better in 2024/2025, worse |
//|    in 2023 and in 2026 (-$207, -9%), worst-period equity DD -13%,  |
//|    and the only corner net-positive in all four years (2023's +8 is|
//|    inside its own sd of 37).                                       |
//|                                                                    |
//|  VERDICT: v1.02 KEPT. What the real test CONFIRMS: the PF level    |
//|  Python predicted, and a lower equity drawdown than the same-window|
//|  150 EMA binary. What it does NOT confirm: "net AND drawdown       |
//|  improved together" - on real 2026 fills it is a drawdown-for-net  |
//|  trade, and across 2023-2026 (simulator, not real) it is           |
//|  net-neutral vs v1.01 with a shallower worst year.                 |
//|                                                                    |
//|  WHAT DRIVES THE REAL DRAWDOWN (Backtest_2's equity curve rebuilt  |
//|  on real GOLD# M1 bars - 5747.63 vs the report's 5690.44). Worst   |
//|  episode 2026-05-06 13:54 -> 05-29 04:03: +2360.98 floating on at  |
//|  the peak (a long later closed on reversal at +1676.01) plus 48    |
//|  trades of May chop realizing -3259.09. Mostly realized chop, not  |
//|  one trade's give-back. And unlike Ratchet, profit is broad: top 5 |
//|  trades = 48% of net, net without them +18962 ZAR.                 |
//|                                                                    |
//|  "FIND SOMETHING NEW" - SIX CANDIDATES FROM THE FINDINGS ABOVE, ALL|
//|  REJECTED (research/meridian/candidates.py). Deliberately not      |
//|  re-runs of what research/aurelius already rejected in Python      |
//|  (breakeven, fixed TP, partial scale-out, vol-sized lots, fast-MA  |
//|  and entry-breach/Price21 exits, ATR-percentile and H4-trend       |
//|  filters, M15). All judged ONLY through the sequential simulator,  |
//|  so any single-position cascade is inside the result. Bar fixed    |
//|  BEFORE running: better net in >=3 of 4 years, better in 2026 under|
//|  both noisy and deterministic execution, worst-year equity DD not  |
//|  worse by >2%.                                                     |
//|  - STOP-AND-REVERSE (make the EA do what every Python number       |
//|    assumed): 2023 +64, 2024 +46, 2025 -119, 2026 -84 (deterministic|
//|    -146); total -94. FAIL. Not taking the reversal cross costs in  |
//|    chop years and pays in trend years. The EA's structure is not a |
//|    bug to fix.                                                     |
//|  - FIX THE STALE-TICKET BAR: worse in all 4 years (-6, -24, -28,   |
//|    -22; total -80). FAIL. It is an accidental one-bar post-stop    |
//|    cooldown and it helps slightly (the 16 real-window crosses it   |
//|    dropped would have netted -129.91 in the simulator - modeled,   |
//|    since the real EA never took them). Kept as-is, now documented  |
//|    here and at the OnTick() call site.                             |
//|  - BOTH OF THE ABOVE: 2023 +59, 2024 +48, 2025 -165, 2026 -48;     |
//|    total -107. FAIL.                                               |
//|  - WIDEN IT ON PURPOSE (no entry for 3 / 6 bars after an SL): total|
//|    -497 / -561. FAIL. Of 0 / 1 / 3 / 6 bars, the accidental 1 is   |
//|    best.                                                           |
//|  - FRIDAY FLATTEN 23:00 instead of 22:00 (still flat for the       |
//|    weekend): +15, -55, -6, +37; total -10. FAIL - noise.           |
//|                                                                    |
//|  No code change, so #property version stays 1.02 - same precedent  |
//|  as MSG_Trader_EA.mq5's v1.14 / v1.16 research note: a disproven   |
//|  idea, explained mechanistically, is what this history is for.     |
//|                                                                    |
//|  CAVEATS. The simulator is bar-level; its per-year numbers for     |
//|  2023-2025 are modeled, not real fills (only the 2026 window and   |
//|  the header's two full-history trade counts are real checks).      |
//|  Execution noise was measured on 2026 fills and applied in ATR     |
//|  units elsewhere. The real v1.02 test is one 9-month window in one |
//|  regime; a real 2023-2026 v1.02 run at the header's 20000 ZAR would|
//|  be the like-for-like check against v1.00/v1.01 and is still       |
//|  missing.                                                          |
//|                                                                    |
//|  KNOWN GAPS (flagged, not fixed, so they don't get lost):          |
//|   - No visual panel/wallpaper - deliberately out of scope for a    |
//|     first pass; every other EA in this project has one, this one   |
//|     can get one later if the system proves out.                    |
//|   - Friday flatten is day-of-week + hour only - no full US-market  |
//|     holiday calendar (IsMarketHoliday/DSTGapHourAdjustment ported  |
//|     in every sibling EA) - a holiday weekend could still leave a   |
//|     position open into a gap this file won't catch.                |
//|   - ATR uses this project's own Wilder recursion (ComputeWilderATR |
//|     below), NOT MT5's built-in iATR - Aurelius's v1.36 note found  |
//|     this broker's iATR is a plain SMA(period) of true range, not   |
//|     real Wilder smoothing. Matches engine.py's wilder_atr exactly. |
//|   - No entry on the first bar after a broker SL fill (stale        |
//|     g_ticket - see the 2026-09-23 section). Accidental, but         |
//|     measured: "fixing" it lost net in all four years simulated, so |
//|     it is deliberately kept.                                       |
//+------------------------------------------------------------------+
#property copyright "Meridian_EA"
#property version   "1.02"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

input group "=== Signal: 21/50 cross, slow-confirm + VWAP + S/R confirmed ==="
input int    InpP21             = 21;
input int    InpP50             = 50;
input ENUM_MA_METHOD InpFastMAMethod = MODE_EMA;   // 21/50 method - EMA confirmed best, see header
input int    InpPConfirm        = 250;      // v1.02: was 150 (named InpP150) - see header, SMA beat EMA
                                             // at every period tested, 250 was the best of those
input ENUM_MA_METHOD InpConfirmMAMethod = MODE_SMA; // v1.02: was MODE_EMA (shared with 21/50) - see header
input int    InpSRDays          = 3;        // trailing completed D1 bars checked for the nearest level
input double InpMinSRDistATR    = 0.50;     // reject entries this close (xATR) to that level - see header

input group "=== Exit ==="
input double InpSafetyStopATR   = 2.5;      // v1.01: tightened from 3.0 - see header (net AND drawdown both improved)
input int    InpATRPeriod       = 14;

input group "=== Risk ==="
input double InpLots            = 0.01;
input double InpMaxSpreadPoints = 60;
input int    InpSlippage        = 20;

input group "=== Session protection (v1.00 gap - see header) ==="
input bool   InpCloseFriday     = true;
input int    InpFridayCloseHour = 22;       // server time

input group "=== Notifications ==="
input bool   InpPushNotifications = true;

input group "=== Misc ==="
input ulong  InpMagic           = 750731;
input string InpTradeComment    = "Meridian";

//--- indicator handles
int h21 = INVALID_HANDLE, h50 = INVALID_HANDLE, h150 = INVALID_HANDLE;

//--- restart-safe position state (re-synced from the live account every
//--- check, not trusted from cache alone - see FindOwnPosition() and its
//--- callers; this is the exact bug class an earlier session found and
//--- fixed across every other EA in this project)
ulong    g_ticket  = 0;
int      g_posDir  = 0;      // +1 long, -1 short, 0 flat

//--- single-latch new-bar gate (called exactly once per tick - the
//--- double-call pattern found and fixed in Slipstream/Tailwind this
//--- session silently ate bars when called from two places per tick)
datetime g_lastBarTime = 0;

//--- session VWAP (cumulative typical-price*volume from each calendar
//--- day's first bar - matches engine.py's session_vwap() exactly, no
//--- built-in MT5 VWAP indicator exists)
datetime g_vwapDay    = 0;
double   g_vwapCumPV  = 0.0;
double   g_vwapCumVol = 0.0;
double   g_vwapValue  = 0.0;

//--- manual Wilder ATR (see header - NOT iATR)
double   g_atrBuf[];

//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, PERIOD_M5, 0);
   if(t == g_lastBarTime) return(false);
   g_lastBarTime = t;
   return(true);
  }
//+------------------------------------------------------------------+
bool FindOwnPosition(ulong &ticket)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && (long)PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
        { ticket = tk; return(true); }
     }
   return(false);
  }
//+------------------------------------------------------------------+
void SyncPositionState()
  {
   ulong tk;
   if(FindOwnPosition(tk))
     {
      g_ticket = tk;
      if(PositionSelectByTicket(g_ticket))
         g_posDir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
     }
   else
     {
      g_ticket = 0;
      g_posDir = 0;
     }
  }
//+------------------------------------------------------------------+
//| Wilder ATR - matches ComputeWilderATR in every sibling EA / this  |
//| project's engine.wilder_atr(): SMA seed of the first `period` true|
//| ranges, then Wilder recursive smoothing. Called once per new bar. |
//+------------------------------------------------------------------+
void ComputeWilderATR(double &out[], int period)
  {
   int need = period + 2;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   // start_pos=1: r[0] is the last CLOSED bar (shift 1), never the still-
   // forming current bar - matches this project's shift=1 convention
   // (engine.py: "index i means bar i has just closed") everywhere else.
   int got = CopyRates(_Symbol, PERIOD_M5, 1, MathMax(period * 3, 200), r);
   if(got < need) { ArrayResize(out, 1); out[0] = 0.0; return; }
   ArraySetAsSeries(out, true);
   ArrayResize(out, got);
   double tr[];
   ArrayResize(tr, got);
   for(int i = 0; i < got - 1; i++)
     {
      double hi = r[i].high, lo = r[i].low, pc = r[i + 1].close;
      tr[i] = MathMax(hi - lo, MathMax(MathAbs(hi - pc), MathAbs(lo - pc)));
     }
   // tr[] is series-ordered (index 0 = most recent); Wilder needs
   // chronological seeding, so walk from the oldest available bar forward.
   int lastIdx = got - period - 1;
   if(lastIdx < 0) { out[0] = 0.0; return; }
   double seed = 0.0;
   for(int k = lastIdx; k < lastIdx + period; k++) seed += tr[k];
   seed /= period;
   double prev = seed;
   for(int k = lastIdx - 1; k >= 0; k--)
      prev = (prev * (period - 1) + tr[k]) / period;
   out[0] = prev;
  }
//+------------------------------------------------------------------+
bool GetATR(double &value)
  {
   ComputeWilderATR(g_atrBuf, InpATRPeriod);
   value = g_atrBuf[0];
   return(value > 0.0);
  }
//+------------------------------------------------------------------+
//| Distance (xATR) from the last closed M5 bar's close to the nearer |
//| of the last InpSRDays COMPLETED daily highs/lows - matches         |
//| engine.py's SRDistanceATR port of Aurelius_EA.mq5 exactly (D1      |
//| shift 1..InpSRDays, never shift 0's still-forming day). Returns    |
//| -1.0 (never rejects) if ATR or D1 history isn't available yet.     |
//+------------------------------------------------------------------+
double SRDistance(bool isBuy, double atrVal)
  {
   if(atrVal <= 0.0) return(-1.0);
   double hi = -DBL_MAX, lo = DBL_MAX;
   for(int d = 1; d <= InpSRDays; d++)
     {
      double h = iHigh(_Symbol, PERIOD_D1, d);
      double l = iLow(_Symbol, PERIOD_D1, d);
      if(h <= 0.0 || l <= 0.0) return(-1.0);   // not enough D1 history yet
      if(h > hi) hi = h;
      if(l < lo) lo = l;
     }
   double close1 = iClose(_Symbol, PERIOD_M5, 1);
   return isBuy ? MathAbs(hi - close1) / atrVal : MathAbs(close1 - lo) / atrVal;
  }
//+------------------------------------------------------------------+
//| Session VWAP - seeds from the current calendar day's first bar on |
//| a (re)start, then updates incrementally one closed bar at a time. |
//+------------------------------------------------------------------+
datetime DayStart(datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return(StructToTime(dt));
  }
//+------------------------------------------------------------------+
void SeedVWAP()
  {
   datetime last = iTime(_Symbol, PERIOD_M5, 1);
   if(last == 0) return;
   datetime day = DayStart(last);
   g_vwapDay = day;
   g_vwapCumPV = 0.0;
   g_vwapCumVol = 0.0;
   for(int shift = 1; shift < 400; shift++)
     {
      datetime t = iTime(_Symbol, PERIOD_M5, shift);
      if(t == 0 || DayStart(t) != day) break;
      double typical = (iHigh(_Symbol, PERIOD_M5, shift) +
                         iLow(_Symbol, PERIOD_M5, shift) +
                         iClose(_Symbol, PERIOD_M5, shift)) / 3.0;
      double vol = (double)iTickVolume(_Symbol, PERIOD_M5, shift);
      g_vwapCumPV  += typical * vol;
      g_vwapCumVol += vol;
     }
   g_vwapValue = (g_vwapCumVol > 0.0) ? g_vwapCumPV / g_vwapCumVol : iClose(_Symbol, PERIOD_M5, 1);
  }
//+------------------------------------------------------------------+
void UpdateVWAP()
  {
   datetime t1 = iTime(_Symbol, PERIOD_M5, 1);
   if(t1 == 0) return;
   datetime day = DayStart(t1);
   if(day != g_vwapDay)
     {
      SeedVWAP();
      return;
     }
   double typical = (iHigh(_Symbol, PERIOD_M5, 1) + iLow(_Symbol, PERIOD_M5, 1) +
                      iClose(_Symbol, PERIOD_M5, 1)) / 3.0;
   double vol = (double)iTickVolume(_Symbol, PERIOD_M5, 1);
   g_vwapCumPV  += typical * vol;
   g_vwapCumVol += vol;
   g_vwapValue = (g_vwapCumVol > 0.0) ? g_vwapCumPV / g_vwapCumVol : iClose(_Symbol, PERIOD_M5, 1);
  }
//+------------------------------------------------------------------+
bool MA(int handle, int shift, double &value)
  {
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle, 0, shift, 1, buf) < 1) return(false);
   value = buf[0];
   return(true);
  }
//+------------------------------------------------------------------+
double LotSize()
  {
   double lots = InpLots;
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0.0) lots = MathRound(lots / step) * step;
   if(lots < mn) lots = mn;
   if(lots > mx) lots = mx;
   return(lots);
  }
//+------------------------------------------------------------------+
void NotifyPush(const string text)
  {
   if(!InpPushNotifications) return;
   SendNotification(StringSubstr(text, 0, 255));
  }
//+------------------------------------------------------------------+
bool IsFridayFlattenTime()
  {
   if(!InpCloseFriday) return(false);
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return(dt.day_of_week == 5 && dt.hour >= InpFridayCloseHour);
  }
//+------------------------------------------------------------------+
void CloseCurrentPosition(const string reason)
  {
   if(!PositionSelectByTicket(g_ticket)) { g_ticket = 0; g_posDir = 0; return; }
   if(trade.PositionClose(g_ticket))
     {
      g_ticket = 0;
      g_posDir = 0;
     }
   else
      PrintFormat("Meridian EA: %s close FAILED for ticket %I64u, retcode %d (%s) - will retry next tick",
                  reason, g_ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
//| Detects the raw 21/50 cross on the bar that JUST closed (shift 1  |
//| vs shift 2) - used for both entry (with confirmation) and exit    |
//| (unconfirmed, per the validated design).                          |
//+------------------------------------------------------------------+
bool DetectCross(int &direction)
  {
   double m21_1, m21_2, m50_1, m50_2;
   if(!MA(h21, 1, m21_1) || !MA(h21, 2, m21_2) || !MA(h50, 1, m50_1) || !MA(h50, 2, m50_2))
      return(false);
   bool aboveNow  = m21_1 > m50_1;
   bool abovePrev = m21_2 > m50_2;
   if(aboveNow == abovePrev) return(false);
   direction = aboveNow ? 1 : -1;
   return(true);
  }
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   SyncPositionState();
   if(g_ticket == 0) return;

   if(IsFridayFlattenTime()) { CloseCurrentPosition("FRIDAY"); return; }

   int dir;
   if(DetectCross(dir) && dir != g_posDir)
      CloseCurrentPosition("REVERSAL");
   // safety stop is a real resting SL order on the position (set at
   // entry, see CheckForEntry) - the broker enforces it even if this
   // EA/terminal goes offline, so nothing further to do for it here.
  }
//+------------------------------------------------------------------+
void CheckForEntry()
  {
   SyncPositionState();
   if(g_ticket != 0) return;
   if(IsFridayFlattenTime()) return;

   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadPts > InpMaxSpreadPoints) return;

   int dir;
   if(!DetectCross(dir)) return;

   double m150_1, close1 = iClose(_Symbol, PERIOD_M5, 1);
   if(!MA(h150, 1, m150_1)) return;

   bool isBuy = (dir > 0);
   bool confirm150 = isBuy ? (close1 > m150_1) : (close1 < m150_1);
   bool confirmVWAP = isBuy ? (close1 > g_vwapValue) : (close1 < g_vwapValue);
   if(!confirm150 || !confirmVWAP) return;

   double atr;
   if(!GetATR(atr) || atr <= 0.0) return;

   // v1.01: reject entries too close to the nearest recent daily S/R level -
   // the one confluence filter this session's research found actually cuts
   // drawdown instead of just cutting trade count (see header). sr < 0
   // means "not enough D1 history yet" - never rejects on that, matching
   // the Python model's fail-open convention for missing data.
   double sr = SRDistance(isBuy, atr);
   if(sr >= 0.0 && sr < InpMinSRDistATR) return;

   double px = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = isBuy ? px - InpSafetyStopATR * atr : px + InpSafetyStopATR * atr;
   double lots = LotSize();

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   bool ok = isBuy ? trade.Buy(lots, _Symbol, px, sl, 0.0, InpTradeComment)
                    : trade.Sell(lots, _Symbol, px, sl, 0.0, InpTradeComment);
   if(ok)
      SyncPositionState();
   else
      PrintFormat("Meridian EA: entry FAILED, retcode %d (%s)",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   // Every number in this EA's header (the validated M5 backtest) was
   // calibrated specifically on M5 bars - all internal calls already use
   // PERIOD_M5 explicitly (not PERIOD_CURRENT), so this only prevents a
   // chart-attach mistake (e.g. dropped on an M15/H1 chart by habit) from
   // running silently: the EA would still fetch and trade M5 data
   // correctly regardless of the chart it's on, but a mismatched chart
   // period is exactly the kind of easy-to-miss setup error this project
   // has hit before (ExportBarData.mq5's PERIOD_M5-default bug earlier
   // this session) - refuse to load rather than risk it going unnoticed.
   if(_Period != PERIOD_M5)
     {
      PrintFormat("Meridian EA: this system is calibrated for M5 only - attach it to an M5 chart "
                  "(currently on period %d)", _Period);
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   h21  = iMA(_Symbol, PERIOD_M5, InpP21,      0, InpFastMAMethod,    PRICE_CLOSE);
   h50  = iMA(_Symbol, PERIOD_M5, InpP50,      0, InpFastMAMethod,    PRICE_CLOSE);
   h150 = iMA(_Symbol, PERIOD_M5, InpPConfirm, 0, InpConfirmMAMethod, PRICE_CLOSE);
   if(h21 == INVALID_HANDLE || h50 == INVALID_HANDLE || h150 == INVALID_HANDLE)
     {
      Print("Meridian EA: indicator handle creation failed");
      return(INIT_FAILED);
     }

   SeedVWAP();
   SyncPositionState();   // restart with a position already open - see header
   g_lastBarTime = 0;     // force IsNewBar() true on the first tick

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(h21);
   IndicatorRelease(h50);
   IndicatorRelease(h150);
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- tick-level Friday backstop, evaluated before the new-bar gate -
   //--- a thin-liquidity Friday can leave few/no ticks right at the
   //--- cutoff hour if gated on a bar close alone (same fix pattern as
   //--- every sibling EA's WeekendStillOpen()).
   if(g_ticket != 0 && IsFridayFlattenTime())
     {
      SyncPositionState();
      if(g_ticket != 0) CloseCurrentPosition("FRIDAY");
     }

   if(!IsNewBar()) return;

   // Unconditional, every new bar regardless of position state - VWAP is
   // a running cumulative sum, so skipping bars while in a trade would
   // silently undercount volume and desync it the moment the position
   // eventually closes and CheckForEntry() reads it again.
   UpdateVWAP();

   // Exactly one of these per bar, never both (2026-09-23 note, see header):
   //  - a REVERSAL close can't also open the opposite trade on the same bar
   //    (not stop-and-reverse, unlike the Python research model - tested,
   //    making it so lost net over 2023-2026);
   //  - after a broker-side SL fill mid-bar, g_ticket is still non-zero at
   //    the next new bar, so that bar goes to ManageOpenPosition() (which
   //    syncs to flat) and a cross on it is never traded. Deliberately kept
   //    - "fixing" it lost net in all four years simulated.
   if(g_ticket != 0)
      ManageOpenPosition();
   else
      CheckForEntry();
  }
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   if((long)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != (long)InpMagic) return;

   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   double price = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   double vol = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   long dtype = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   string side = (dtype == DEAL_TYPE_BUY) ? "BUY" : "SELL";

   if(entry == DEAL_ENTRY_IN)
      NotifyPush(StringFormat("Meridian %s OPEN %.2f lots @ %.2f", side, vol, price));
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      NotifyPush(StringFormat("Meridian %s CLOSE %.2f lots @ %.2f P/L=%.2f", side, vol, price, profit));
     }
  }
//+------------------------------------------------------------------+
