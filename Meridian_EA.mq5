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
//|  v1.03 - CHART VISUALS (2026-09-23). CLOSES THE v1.00 "NO VISUAL   |
//|  PANEL/WALLPAPER" KNOWN GAP BELOW, AT THE USER'S REQUEST ("all the |
//|  visuals ... all in the correct layering"). COSMETIC ONLY - NO     |
//|  SIGNAL, ENTRY, EXIT, SIZING OR RISK LOGIC TOUCHED:                |
//|  CheckForEntry(), ManageOpenPosition(), DetectCross(),             |
//|  SRDistance(), UpdateVWAP(), SeedVWAP() and ComputeWilderATR() are |
//|  byte-for-byte what v1.02 shipped, so every number above still     |
//|  describes this file and the only thing to check on a real attach  |
//|  is that it draws.                                                 |
//|                                                                    |
//|  PORTED, NOT REINVENTED. Aurelius_EA.mq5 (v1.37-v1.44) is the      |
//|  canonical source Fulcrum_EA.mq5 (v2.03-v2.05) and Ratchet_EA.mq5  |
//|  (v3.22/v3.27) copied their chart conventions from;                |
//|  PText/PRow/PRect/PFrame/PSection, PBackground/PWatermark/PTheme   |
//|  and DrawMASegment/PurgeOldMALines are carried over from it        |
//|  essentially line for line (PRow only gains an optional legend-dot |
//|  colour, default off), and the on-chart captions follow            |
//|  MSG_Trader_EA.mq5 v1.16's DrawChartLabel(). What is drawn:        |
//|                                                                    |
//|   - Chart theme: black background, neon-blue bull / white bear     |
//|     candles and wicks - InpChartBg/InpBullCol/InpBearCol hold the  |
//|     exact values Aurelius, Fulcrum and Ratchet share. MT5's own    |
//|     trade arrows and SL lines are hidden (InpHideTradeMarks),      |
//|     replaced by this file's labelled lines below.                  |
//|   - Wallpaper + "MERIDIAN" watermark, both behind the candles.     |
//|     InpBackgroundBMP = Meridian_Wallpaper.bmp, named like          |
//|     Ratchet_/Fulcrum_Wallpaper.bmp. The image does NOT exist yet - |
//|     PBackground() retries 40 times, logs where the file has to go  |
//|     (MQL5\Images), then gives up quietly; the EA runs the same     |
//|     without it.                                                    |
//|   - The three MAs this system trades on, as per-bar OBJ_TREND      |
//|     segments over InpMAHistoryBars (2500 bars, ~8.7 days): 21 EMA  |
//|     yellow, 50 EMA orange, and the InpPConfirm/InpConfirmMAMethod  |
//|     line (250 SMA) neon purple - the colour every sibling gives    |
//|     this same "former 150" slot. NOT ChartIndicatorAdd: an EA      |
//|     cannot set a built-in indicator's PLOT_LINE_COLOR (Ratchet     |
//|     v3.22). There is no oscillator here, so Ratchet's one subwindow|
//|     exception does not apply.                                      |
//|   - Session VWAP, neon aqua (Aurelius's InpColVWAP). Each live     |
//|     segment is drawn from g_vwapValue itself - the exact number    |
//|     CheckForEntry() reads - never a recomputation, and the line is |
//|     broken at every day boundary so a session reset does not read  |
//|     as a price move. The attach-time backfill rebuilds history in  |
//|     one forward pass with SeedVWAP()'s own typical-price x         |
//|     tick-volume maths.                                             |
//|   - The S/R levels the v1.01 filter actually measures:             |
//|     prior-InpSRDays D1 high (what a BUY is checked against) and low|
//|     (a SELL), dashed, each with a dotted +/- InpMinSRDistATR x ATR |
//|     band - the real no-entry zone, so an entry rejected near a     |
//|     level is visibly inside it. SRLevels() is a display-only copy  |
//|     of SRDistance()'s D1 loop; SRDistance() was deliberately NOT   |
//|     refactored to share it (no logic change this version) - keep   |
//|     the two in step if either is edited.                           |
//|   - An open position's entry and safety stop as horizontal lines   |
//|     WITH captions ("ENTRY LONG 2345.67", "SAFETY SL 2339.10 (1.84  |
//|     ATR away)") - MSG v1.16's lesson that an unlabelled line is    |
//|     useless to someone watching live. Every MA/VWAP line and both  |
//|     S/R levels carry a caption too.                                |
//|   - The panel (draggable, autofit, self-learning width). ENTRY     |
//|     GATE, for the side a cross would trade: 21 vs 50, last 21/50   |
//|     cross and how many bars ago, close vs the confirm line, close  |
//|     vs VWAP, S/R distance vs InpMinSRDistATR (red = the filter is  |
//|     blocking), spread, Friday flatten, and what the last closed bar|
//|     actually did - ENTERED, BLOCKED: <first failing gate, in       |
//|     CheckForEntry()'s own order>, or "exit-only" when that bar went|
//|     to ManageOpenPosition(), which is how the two quirks documented|
//|     above (not stop-and-reverse; the post-SL stale-ticket bar) show|
//|     up live. There is no "pending confirmation" state to show - the|
//|     confirm/VWAP/S-R checks only ever run on the cross bar itself. |
//|     POSITION: entry, safety stop, distance to it in price and ATR, |
//|     floating P/L, bars held (flat: lot size and the stop/exit      |
//|     rules). DRAWN LINES: a colour-keyed legend with each line's    |
//|     current value. ACCOUNT: "today (mine)" / "today (other)", split|
//|     exactly as Aurelius/Fulcrum/Ratchet do because this account is |
//|     shared - ACCOUNT_EQUITY alone would mix any other EA's P&L into|
//|     this one's.                                                    |
//|                                                                    |
//|  LAYERING - every fix the siblings already paid for, built in from |
//|  the start rather than retrofitted:                                |
//|                                                                    |
//|   - MT5 stacks chart objects by CREATION order, not OBJPROP_ZORDER.|
//|     On each new bar every chart draw (MA/VWAP segments, captions,  |
//|     level lines) runs BEFORE DrawPanel(true), and that call deletes|
//|     and recreates every panel object except the draggable "bg"     |
//|     (g_panelReclaim, Aurelius v1.38), so the panel is always the   |
//|     newest thing on the chart. An opaque "fl" fill over "bg" keeps |
//|     the body solid (Ratchet v3.22 / Fulcrum).                      |
//|   - The 1-second OnTimer() refresh updates the panel in place (no  |
//|     flashing) and reclaims top-of-stack ONLY when it has just      |
//|     created a chart object itself - a level line appearing mid-bar |
//|     after a fill, or the deferred backfill below.                  |
//|   - Explicit 4-strip PFrame(), not PRect()'s own border (the       |
//|     2-of-4-sides quirk, Ratchet v3.22).                            |
//|   - Level lines and captions are created once and then moved in    |
//|     place, so they never re-bury the panel. Wallpaper and watermark|
//|     are OBJPROP_BACK (behind the candles); the watermark is        |
//|     recreated after the bitmap loads so it sits on top of it.      |
//|   - New: iMA handles are usually not calculated yet inside         |
//|     OnInit(), where the siblings' one-shot backfill runs. Here     |
//|     BackfillLines() checks BarsCalculated() and, if not ready,     |
//|     retries from the timer/next bar instead of silently drawing a  |
//|     1-bar stub.                                                    |
//|                                                                    |
//|  TESTER SPEED. g_skipCosmeticDraws (MQL_TESTER &&                  |
//|  !MQL_VISUAL_MODE), set first thing in OnInit(), gates ALL of it - |
//|  theme, backfill, per-bar draws, panel, the day-stamp/display      |
//|  caches, and EventSetTimer(1) itself; OnTimer() and OnChartEvent() |
//|  also return early as a backstop (Ratchet v3.15's lesson). A       |
//|  non-visual Strategy Tester run executes none of it. The only      |
//|  ungated addition is a realized-P&L running total in               |
//|  OnTradeTransaction() - per deal, not per tick, and never read by  |
//|  any decision.                                                     |
//|                                                                    |
//|  NOTHING HERE WRITES TRADING STATE. The drawing code finds the     |
//|  position via FindOwnPosition() into a LOCAL ticket and never calls|
//|  SyncPositionState() - that re-syncs g_ticket, and doing it from a |
//|  1s timer would quietly "fix" the post-SL stale-ticket bar the     |
//|  2026-09-23 section measured and deliberately kept. The one        |
//|  addition next to OnTick()'s ManageOpenPosition()/CheckForEntry()  |
//|  branch only records which branch is about to run (for the panel), |
//|  inside the same gate; the branch itself is untouched, and all     |
//|  drawing happens AFTER it, so a fill is drawn on the bar it        |
//|  happens. Display ATR is its own ComputeWilderATR() call into a    |
//|  local array, so g_atrBuf is untouched.                            |
//|                                                                    |
//|  NOT COMPILED - no MT5 in the environment this was written in.     |
//|  Checked by brace/paren balance and line by line against the       |
//|  sibling functions it ports. On first attach, check the Experts tab|
//|  for the BG message and that the panel/lines appear.               |
//|                                                                    |
//|  KNOWN GAPS (flagged, not fixed, so they don't get lost):          |
//|   - RESOLVED in v1.03: "No visual panel/wallpaper" - see the v1.03 |
//|     section above. The one piece left outside the code is the      |
//|     wallpaper image itself: InpBackgroundBMP is wired and defaults |
//|     to Meridian_Wallpaper.bmp, which has to be made and put in     |
//|     <data folder>\MQL5\Images (until then PBackground() logs that 3|
//|     times and gives up quietly).                                   |
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
//|   - VWAP counts the last closed bar TWICE after every (re)start,   |
//|     until the day rolls: SeedVWAP() in OnInit() already includes   |
//|     shift 1, and the first tick's forced IsNewBar() (g_lastBarTime |
//|     = 0) then runs UpdateVWAP(), which adds that same bar again.   |
//|     Found while wiring the VWAP line in v1.03; NOT fixed - it moves|
//|     the VWAP gate, so it is a logic change that needs its own      |
//|     simulator check, not a cosmetic one. The drawn VWAP is         |
//|     g_vwapValue as-is, so it shows this too (the attach-time       |
//|     backfill does not).                                            |
//+------------------------------------------------------------------+
#property copyright "Meridian_EA"
#property version   "1.03"
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

//--- v1.03: everything below is cosmetic only - nothing in these three groups
//--- is read by any entry, exit, sizing or risk decision, and every draw they
//--- control sits behind g_skipCosmeticDraws (see header). Palette values are
//--- the ones Aurelius_EA.mq5/Fulcrum_EA.mq5/Ratchet_EA.mq5 already share, not
//--- new ones, so all four EAs read as one product on the same account.
input group "=== Dashboard (v1.03 - cosmetic, see header) ==="
input bool    InpShowPanel   = true;              // Show the panel
input int     InpPanelDrag   = 1;                 // 0 = locked, 1 = draggable
input int     InpPanelX      = 12;                // X offset - same 12/30 top-left anchor as the siblings
input int     InpPanelY      = 30;                // Y offset (from the anchor edge)
input bool    InpPanelBottom = false;             // Anchor the panel to the BOTTOM left
input int     InpPanelW      = 260;               // Width (grows on its own if a row needs more)
input color   InpPanelBg     = C'13,17,28';       // Panel background (solid)
input color   InpHeaderBg    = C'28,36,58';       // Header / section band
input color   InpPanelEdge   = C'0,150,255';      // Border - neon blue, same as Fulcrum/Ratchet
input color   InpTitleCol    = C'0,150,255';      // Title - neon blue
input color   InpSectionCol  = C'214,226,238';    // Section headings - silver
input color   InpTextCol     = C'150,166,192';    // Labels
input color   InpValCol      = C'236,242,252';    // Values
input color   InpOkCol       = C'0,230,118';      // Gate passed - neon green
input color   InpNoCol       = C'255,61,90';      // Gate blocking - hot red
input color   InpShadowCol   = C'6,8,14';         // Drop shadow
input string  InpPanelFont   = "Consolas";        // Font
input int     InpPanelSize   = 8;                 // Font size

input group "=== Chart theme and drawn indicators (v1.03) ==="
input bool    InpApplyTheme  = true;              // Recolour the chart
input bool    InpHideTradeMarks = true;           // Hide MT5's own trade arrows/SL lines - replaced by the
                                                  // labelled entry/stop lines below, in this file's palette
input color   InpChartBg     = clrBlack;          // Chart background - same as Aurelius/Fulcrum/Ratchet
input color   InpBullCol     = C'0,150,255';      // Bullish candle - neon blue, same as Aurelius/Fulcrum/Ratchet
input color   InpBearCol     = clrWhite;          // Bearish candle - neon white, same as Aurelius/Fulcrum/Ratchet
input bool    InpShowMAs     = true;              // Draw the 21/50/confirm MAs this EA trades on
input bool    InpShowVWAP    = true;              // Draw the session VWAP CheckForEntry() gates on
input int     InpMAHistoryBars = 2500;            // Bars of MA/VWAP line history kept drawn (bounded, so a
                                                  // long-running live EA doesn't accumulate objects forever -
                                                  // 2500 M5 bars is ~8.7 days, same as the siblings)
input color   InpCol21       = clrYellow;         // 21 line colour - same as the siblings' 21
input color   InpCol50       = C'255,140,0';      // 50 line colour - neon orange (NOT white: it would vanish
                                                  // into the white bear candles, see Aurelius v1.37)
input color   InpColConfirm  = C'191,0,255';      // InpPConfirm line (250 SMA) - neon purple, the colour the
                                                  // siblings give this same "former 150" slot
input color   InpColVWAP     = C'0,255,255';      // VWAP colour - neon aqua, same as Aurelius's InpColVWAP
input bool    InpShowLineLabels = true;           // Caption each MA/VWAP line at its right-hand end
input bool    InpShowTradeLevels = true;          // Draw the OPEN position's entry and safety stop, each with
                                                  // an on-chart caption (MSG_Trader_EA.mq5 v1.16 pattern)
input color   InpColEntryLine = C'150,166,192';   // Entry line - InpTextCol's silver-grey (a level, not news)
input color   InpColStopLine  = C'255,61,90';     // Safety-stop line - InpNoCol's hot red
input bool    InpShowSR      = true;              // Draw the prior-InpSRDays D1 high/low the S/R filter measures
input bool    InpShowSRZone  = true;              // ...plus the +/- InpMinSRDistATR x ATR no-entry band around each
input color   InpColSR       = C'120,144,176';    // S/R level colour - same as Aurelius/Fulcrum's InpColSR
input color   InpColSRZone   = C'60,72,88';       // No-entry band - InpColSR at half brightness (drawn dotted),
                                                  // so it reads as a zone belonging to the level, not a level

input group "=== Wallpaper & watermark (v1.03) ==="
input string  InpBackgroundBMP = "Meridian_Wallpaper.bmp"; // .bmp file in <data folder>\MQL5\Images (empty = none)
input int     InpBgWidth     = 1290;              // Image width (px) - for centring only
input int     InpBgHeight    = 720;               // Image height (px) - for centring only
input string  InpWatermark   = "MERIDIAN";        // Watermark text (empty = none)
input color   InpWaterCol    = C'46,38,24';       // Watermark colour - same as the siblings
input bool    InpWaterBottom = true;              // Watermark bottom-right instead of centred
input int     InpWaterSize   = 42;                // Watermark font size
input string  InpWaterFont   = "Arial Black";     // Watermark font

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

//--- v1.03 chart visuals - cosmetic state only. Nothing below is read by
//--- CheckForEntry()/ManageOpenPosition() or anything they call; every write
//--- to it sits behind g_skipCosmeticDraws except g_myRealizedToday (one add
//--- per closing deal in OnTradeTransaction - never per tick).
//---
//--- PERFORMANCE: true when running a non-visual Strategy Tester pass (no
//--- chart anyone is watching) - set once, first thing in OnInit(). Gates the
//--- theme, the timer, every chart object and the panel. Same flag, same
//--- test, as every sibling (Ratchet v3.15 found an ungated EventSetTimer(1)
//--- firing a full panel redraw once per SIMULATED second - hours of backtest).
bool     g_skipCosmeticDraws = false;
string   g_pp = "MERP_";     // panel
string   g_pw = "MERW_";     // wallpaper + watermark, kept out of the panel wipe
string   g_pm = "MERM_";     // per-bar MA/VWAP segments, purged to a rolling window
string   g_pl = "MERL_";     // horizontal levels (entry/stop/S-R) and every on-chart caption
int      g_panX = -1, g_panY = -1;   // live panel position, updated by dragging
bool     g_bgOK = false;              // wallpaper loaded (or none requested)
int      g_bgTries = 0;
int      g_panelMinW = 0;             // self-learning minimum width - see PRow()
//--- Controls whether PRect/PText delete-and-recreate (to reclaim top-of-
//--- stack) or just update in place. MT5 stacks chart objects by CREATION
//--- order, not OBJPROP_ZORDER, so reclaiming is needed whenever a chart
//--- object has been created since the panel was - once per new bar (after
//--- the new MA/VWAP segments), and on the rare timer tick that itself just
//--- created one. Doing it on EVERY refresh made the whole panel visibly
//--- flash in Aurelius v1.37 - see Aurelius v1.38 for the fix ported here.
bool     g_panelReclaim = true;
bool     g_backfilled = false;        // MA/VWAP history drawn yet - see BackfillLines()
//--- "today (mine)" vs "today (other)" - same convention as Aurelius/Fulcrum/
//--- Ratchet: ACCOUNT_EQUITY is the WHOLE account, so any other EA or manual
//--- trade sharing it would otherwise be mixed into this EA's own number.
double   g_myRealizedToday = 0.0;     // O(1) running total, never a HistorySelect() scan
double   g_dayStartEquity  = 0.0;
int      g_dayStamp        = -1;
//--- display-only caches, refreshed once per new bar (RefreshDisplayState)
double   g_dispATR         = 0.0;     // same Wilder ATR CheckForEntry() computes, own buffer
int      g_dispCrossDir    = 0;       // most recent 21/50 cross: +1 up, -1 down, 0 none found
int      g_dispCrossShift  = 0;       // ...and which closed bar it was on (1 = the last one)
datetime g_dispBranchBar   = 0;       // closed bar OnTick() last dispatched on...
bool     g_dispBranchManaged = false; // ...and whether it went to ManageOpenPosition()
datetime g_vwapDrawT       = 0;       // last VWAP point drawn (bar time / value) - the next
double   g_vwapDrawV       = 0.0;     // bar's segment starts here

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
//+==================================================================+
//|  v1.03 CHART VISUALS - everything from here to OnInit() is        |
//|  cosmetic. It READS existing state (MA handles, g_vwapValue,      |
//|  the live position via FindOwnPosition into a local ticket) and   |
//|  WRITES nothing but chart objects and the display-only globals    |
//|  above. It never calls SyncPositionState() - that re-syncs        |
//|  g_ticket, and doing so from the 1s timer would silently remove   |
//|  the post-SL stale-ticket bar the header measured and kept.       |
//+==================================================================+
//+------------------------------------------------------------------+
//| Panel primitives - ported from Aurelius_EA.mq5 (the canonical     |
//| copy Fulcrum/Ratchet took theirs from). All layout is left-corner |
//| based: right corners invert the X axis in MT5, which silently     |
//| mirrored the whole panel off-screen in an earlier sibling.        |
//+------------------------------------------------------------------+
//--- rough monospace-ish width estimate, same formula as every sibling
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
//+------------------------------------------------------------------+
void PRect(const string id, const int x, const int y, const int w, const int h,
           const color bg, const color edge, const int border = 1)
  {
   string nm = g_pp + id;
   //--- only the background is grabbable, and it must not be HIDDEN or
   //--- MT5 will not let it be selected, which is what blocked dragging
   bool grab = (InpPanelDrag == 1 && id == "bg");
   bool exists = (ObjectFind(0, nm) >= 0);
   //--- everything EXCEPT the draggable bg is deleted and recreated when
   //--- g_panelReclaim is set, so it is the newest object and can't be
   //--- buried under an MA/VWAP segment or level line drawn since the last
   //--- reclaim. bg keeps its identity so an in-progress drag isn't reset -
   //--- the "fl" fill drawn right after it in DrawPanel() reclaims instead
   //--- and is what actually keeps the panel body opaque.
   if(g_panelReclaim && !grab && exists) { ObjectDelete(0, nm); exists = false; }
   if(!exists) ObjectCreate(0, nm, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, nm, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, nm, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, nm, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, nm, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, edge);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, border);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);       // in front of candles
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, grab);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, !grab);
   //--- ZORDER affects click priority, not visual stacking - set high anyway,
   //--- but the real fix for staying on top is the reclaim above, not this.
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5000);
  }
//+------------------------------------------------------------------+
//| PRect's own OBJ_RECTANGLE_LABEL border renders unreliably in this |
//| terminal build - observed live on the siblings as only two of the |
//| four sides drawn. This draws an explicit 4-strip frame instead,    |
//| each strip an ordinary solid-filled rect (the one thing that does  |
//| render correctly). Same helper as Aurelius/Fulcrum/Ratchet.        |
//+------------------------------------------------------------------+
void PFrame(const string id, const int x, const int y, const int w, const int h,
            const color edge, const int thick = 2)
  {
   PRect(id + "ft", x,             y,             w,     thick, edge, edge, 0);   // top
   PRect(id + "fb", x,             y + h - thick, w,     thick, edge, edge, 0);   // bottom
   PRect(id + "fl", x,             y,             thick, h,     edge, edge, 0);   // left
   PRect(id + "fr", x + w - thick, y,             thick, h,     edge, edge, 0);   // right
  }
//+------------------------------------------------------------------+
void PText(const string id, const int x, const int y, const string txt,
           const color col, const int size = 0, const bool rightAlign = false,
           const string font = "")
  {
   string nm = g_pp + id;
   //--- an OBJ_LABEL with empty text renders MT5's default "Label" - this
   //--- delete is unconditional (not gated by g_panelReclaim): it's a row
   //--- that genuinely no longer has a value and has to disappear.
   if(txt == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   bool exists = (ObjectFind(0, nm) >= 0);
   //--- creation-order reclaim, see g_panelReclaim / PRect above
   if(g_panelReclaim && exists) { ObjectDelete(0, nm); exists = false; }
   if(!exists) ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, y);
   ObjectSetString (0, nm, OBJPROP_TEXT, txt);
   ObjectSetString (0, nm, OBJPROP_FONT, font == "" ? InpPanelFont : font);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, size > 0 ? size : InpPanelSize);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5001);      // above PRect's 5000
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
                    rightAlign ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
  }
//+------------------------------------------------------------------+
//| A row: status dot, label on the left, value right-aligned.        |
//| state: 1 = pass (green), 0 = blocking (red), -1 = informational.  |
//| dotCol (Meridian addition, default off so every sibling-style     |
//| call is unchanged): an explicit dot colour, used only by the      |
//| DRAWN LINES legend so each row's dot matches its line on chart.   |
//+------------------------------------------------------------------+
void PRow(const string id, const int x, const int y, const int w,
          const string label, const string value, const int state,
          const color dotCol = clrNONE)
  {
   if(label == "" && value == "")
     {
      PText(id + "d", x, y, "", InpTextCol);
      PText(id + "l", x, y, "", InpTextCol);
      PText(id + "v", x, y, "", InpTextCol);
      return;
     }
   color dot = (dotCol != clrNONE) ? dotCol :
               ((state == 1) ? InpOkCol : (state == 0) ? InpNoCol : InpTextCol);
   PText(id + "d", x + 10, y, CharToString(108), dot, InpPanelSize + 1,
         false, "Wingdings");
   PText(id + "l", x + 26, y, label, InpTextCol);
   PText(id + "v", x + w - 12, y, value, InpValCol, 0, true);
   //--- learn the width this row actually needed, for the next draw cycle
   int need = 26 + EstimateTextWidth(label, InpPanelSize) + 16
              + EstimateTextWidth(value, InpPanelSize) + 20;
   if(need > g_panelMinW) g_panelMinW = need;
  }
//+------------------------------------------------------------------+
//| Section heading on its own tinted band.                           |
//+------------------------------------------------------------------+
void PSection(const string id, const int x, const int y, const int w,
              const int rh, const string title)
  {
   //--- band created first, label second, or the band hides the label
   PRect(id + "bar", x + 1, y - 3, w - 2, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x + 10, y, title, InpSectionCol, InpPanelSize, false, "Arial Bold");
  }
//+------------------------------------------------------------------+
//| Watermark - drawn BEHIND the candles (OBJPROP_BACK) so it never   |
//| obscures price. Created once; recreated only when the wallpaper   |
//| (re)loads, so it stays layered above the bitmap.                  |
//+------------------------------------------------------------------+
void PWatermark()
  {
   string nm = g_pw + "wm";
   if(InpWatermark == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
   int cw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int ch = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   if(InpWaterBottom)
     {
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_RIGHT_LOWER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_RIGHT_LOWER);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 18);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 18);
     }
   else
     {
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_CENTER);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, cw / 2);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, ch / 2);
     }
   ObjectSetString (0, nm, OBJPROP_TEXT, InpWatermark);
   ObjectSetString (0, nm, OBJPROP_FONT, InpWaterFont);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpWaterSize);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, InpWaterCol);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| Wallpaper bitmap, centred, behind the candles. Retries up to 40   |
//| times (it is called from every panel draw and the 1s timer), then |
//| gives up quietly - Meridian_Wallpaper.bmp does not exist yet (see |
//| header), and a missing image must never be more than 3 log lines. |
//+------------------------------------------------------------------+
void PBackground()
  {
   string nm = g_pw + "bmp";
   if(InpBackgroundBMP == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); g_bgOK = true; return; }
   if(g_bgOK) return;                       // already showing, nothing to do
   if(g_bgTries > 40) return;               // give up quietly after ~40 tries

   g_bgTries++;
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   if(!ObjectCreate(0, nm, OBJ_BITMAP_LABEL, 0, 0, 0))
     { Print("Meridian EA BG: ObjectCreate failed, error ", GetLastError()); return; }

   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0, nm, OBJPROP_BMPFILE, 0, path);
   int err = GetLastError();
   if(!okSet || err != 0)
     {
      if(g_bgTries <= 3)
         PrintFormat("Meridian EA BG try %d: failed to load \"%s\"  set=%s  error=%d"
                     "  -> file must be at <data folder>\\MQL5\\Images\\%s",
                     g_bgTries, path, (okSet ? "true" : "false"), err, InpBackgroundBMP);
      ObjectDelete(0, nm);
      return;
     }

   int cw  = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int chh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, MathMax(0, (cw  - InpBgWidth)  / 2));
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, MathMax(0, (chh - InpBgHeight) / 2));
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   g_bgOK = true;
   //--- the bitmap is now the newest background object, so rebuild the
   //--- watermark once to put it back on top of it
   if(ObjectFind(0, g_pw + "wm") >= 0) ObjectDelete(0, g_pw + "wm");
   PWatermark();
   PrintFormat("Meridian EA BG: loaded \"%s\" on try %d", path, g_bgTries);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Chart colours - same values and calls as Aurelius_EA.mq5's PTheme.|
//+------------------------------------------------------------------+
void PTheme()
  {
   if(!InpApplyTheme) return;
   ChartSetInteger(0, CHART_COLOR_BACKGROUND,  InpChartBg);
   ChartSetInteger(0, CHART_COLOR_FOREGROUND,  C'138,152,178');
   ChartSetInteger(0, CHART_COLOR_GRID,        C'20,26,40');
   //--- wick colours match the bodies so candles read as one solid shape
   ChartSetInteger(0, CHART_COLOR_CHART_UP,    InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CHART_DOWN,  InpBearCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, InpBearCol);
   ChartSetInteger(0, CHART_COLOR_CHART_LINE,  C'138,152,178');
   ChartSetInteger(0, CHART_COLOR_BID,         C'0,229,255');
   ChartSetInteger(0, CHART_COLOR_ASK,         C'255,193,7');
   ChartSetInteger(0, CHART_SHOW_GRID,   false);
   ChartSetInteger(0, CHART_MODE,        CHART_CANDLES);
   ChartSetInteger(0, CHART_SHOW_PERIOD_SEP, false);
   ChartSetInteger(0, CHART_COLOR_VOLUME,      C'40,52,76');
   ChartSetInteger(0, CHART_SHOW_OBJECT_DESCR, false);
   //--- MT5's own buy/sell arrows and SL/TP lines are a terminal display
   //--- setting, not chart objects - this is the only way to turn them off.
   //--- UpdateLevelLines() draws this EA's own, labelled, replacements.
   if(InpHideTradeMarks)
     {
      ChartSetInteger(0, CHART_SHOW_TRADE_LEVELS, false);
      ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, false);
     }
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Each MA/VWAP line is its own coloured OBJ_TREND segment per bar -  |
//| NOT ChartIndicatorAdd, which can't set a built-in indicator's      |
//| PLOT_LINE_COLOR from an EA (Ratchet v3.22), so the lines would show |
//| in MT5's default colours instead of this palette. Same idiom as    |
//| Aurelius/Fulcrum/Ratchet's DrawMASegment. OBJPROP_HIDDEN keeps up  |
//| to 4 x InpMAHistoryBars of these out of the Object List.           |
//+------------------------------------------------------------------+
void DrawMASegment(const string tag, const datetime tOld, const double vOld,
                   const datetime tNew, const double vNew, const color col,
                   const ENUM_LINE_STYLE style = STYLE_SOLID)
  {
   string nm = g_pm + tag + "_" + IntegerToString((long)tNew);
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_TREND, 0, tOld, vOld, tNew, vNew);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
void PurgeOldMALines(const datetime latestBarTime)
  {
   datetime cutoff = latestBarTime - (datetime)((long)InpMAHistoryBars * PeriodSeconds(PERIOD_M5));
   for(int i = ObjectsTotal(0, 0, OBJ_TREND) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, OBJ_TREND);
      if(StringFind(nm, g_pm) != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < cutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
//| On-chart caption anchored at a time/price (OBJ_TEXT) - MSG v1.16's |
//| DrawChartLabel(), so every line says what it is on the chart       |
//| itself. Created once, then moved in place (never recreated), so a  |
//| caption can't re-bury the panel. Returns true if it was CREATED    |
//| this call - the caller then knows the panel needs a reclaim.       |
//+------------------------------------------------------------------+
bool DrawChartLabel(const string tag, const datetime t, const double price,
                    const string text, const color col)
  {
   string nm = g_pl + tag;
   if(text == "" || t <= 0 || price <= 0.0)
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return(false); }
   bool created = false;
   if(ObjectFind(0, nm) < 0)
     { ObjectCreate(0, nm, OBJ_TEXT, 0, t, price); created = true; }
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetString (0, nm, OBJPROP_TEXT, text);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 8);
   ObjectSetString (0, nm, OBJPROP_FONT, InpPanelFont);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   return(created);
  }
//+------------------------------------------------------------------+
bool DeleteChartLabel(const string tag)
  {
   string nm = g_pl + tag;
   if(ObjectFind(0, nm) < 0) return(false);
   ObjectDelete(0, nm);
   return(true);
  }
//+------------------------------------------------------------------+
//| Horizontal levels (entry / safety stop / S-R and its band). None   |
//| of these move bar to bar, so one OBJ_HLINE each (Aurelius/Fulcrum  |
//| v1.44/v2.12 pattern), created once and UPDATED IN PLACE - recreating |
//| them every bar would keep re-burying the panel. Each carries an     |
//| optional caption (MSG v1.16). Returns true if anything was CREATED. |
//+------------------------------------------------------------------+
bool DeleteLevelLine(const string tag)
  {
   string nm = g_pl + tag;
   bool had = (ObjectFind(0, nm) >= 0);
   if(had) ObjectDelete(0, nm);
   if(DeleteChartLabel(tag + "_lbl")) had = true;
   return(had);
  }
//+------------------------------------------------------------------+
bool DrawLevelLine(const string tag, const double price, const color col,
                   const ENUM_LINE_STYLE style, const string label = "")
  {
   if(price <= 0.0) { DeleteLevelLine(tag); return(false); }
   string nm = g_pl + tag;
   bool created = false;
   if(ObjectFind(0, nm) < 0)
     { ObjectCreate(0, nm, OBJ_HLINE, 0, 0, price); created = true; }
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTED, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   //--- caption at the live edge of the chart, like MSG v1.16
   if(label != "")
     { if(DrawChartLabel(tag + "_lbl", TimeCurrent(), price, "  " + label, col)) created = true; }
   else
      DeleteChartLabel(tag + "_lbl");
   return(created);
  }
//+------------------------------------------------------------------+
//| Display-only copy of SRDistance()'s D1 loop, line for line: the    |
//| prior InpSRDays COMPLETED daily bars (shift 1..InpSRDays), highest |
//| high = what a BUY is measured against, lowest low = a SELL.        |
//| SRDistance() itself is deliberately left untouched (v1.03 changes  |
//| no logic) - if either is ever edited, edit both.                   |
//+------------------------------------------------------------------+
bool SRLevels(double &hi, double &lo)
  {
   hi = -DBL_MAX; lo = DBL_MAX;
   if(InpSRDays < 1) return(false);          // SRDistance() never blocks at 0 days either
   for(int d = 1; d <= InpSRDays; d++)
     {
      double h = iHigh(_Symbol, PERIOD_D1, d);
      double l = iLow(_Symbol, PERIOD_D1, d);
      if(h <= 0.0 || l <= 0.0) return(false); // not enough D1 history yet (SRDistance fails open here)
      if(h > hi) hi = h;
      if(l < lo) lo = l;
     }
   return(true);
  }
//+------------------------------------------------------------------+
string MethodName(const ENUM_MA_METHOD m)
  {
   if(m == MODE_SMA)  return("SMA");
   if(m == MODE_EMA)  return("EMA");
   if(m == MODE_SMMA) return("SMMA");
   return("LWMA");
  }
string MALabel(const int period, const ENUM_MA_METHOD m)
  {
   return(IntegerToString(period) + " " + MethodName(m));
  }
//+------------------------------------------------------------------+
//| Own position, found via FindOwnPosition() into a LOCAL ticket and  |
//| selected - never via g_ticket/SyncPositionState() (see the block   |
//| comment above). Symbol+magic scoped, so another EA's position on   |
//| this account is never drawn as Meridian's.                         |
//+------------------------------------------------------------------+
bool SelectOwnPositionForDisplay()
  {
   ulong tk = 0;
   return(FindOwnPosition(tk) && PositionSelectByTicket(tk));
  }
//+------------------------------------------------------------------+
double MyFloatingPL()
  {
   double sum = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      sum += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   return(sum);
  }
//+------------------------------------------------------------------+
//| Day boundary for the panel's "today" rows - same as every sibling. |
//+------------------------------------------------------------------+
void UpdateDayStamp()
  {
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(t.day != g_dayStamp)
     {
      g_dayStamp = t.day;
      g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_myRealizedToday = 0.0;
     }
  }
//+------------------------------------------------------------------+
//| Once per new bar: the display ATR (the same ComputeWilderATR() call |
//| CheckForEntry() makes, into its OWN array - g_atrBuf is never      |
//| touched from here) and the most recent 21/50 cross, found with the |
//| same strict m21 > m50 test DetectCross() uses.                     |
//+------------------------------------------------------------------+
void RefreshDisplayState()
  {
   double tmp[];
   ComputeWilderATR(tmp, InpATRPeriod);
   g_dispATR = (ArraySize(tmp) > 0) ? tmp[0] : 0.0;

   g_dispCrossDir = 0;
   g_dispCrossShift = 0;
   double a21[], a50[];
   ArraySetAsSeries(a21, true);
   ArraySetAsSeries(a50, true);
   int g1 = CopyBuffer(h21, 0, 1, 600, a21);    // index 0 = shift 1 (last closed bar)
   int g2 = CopyBuffer(h50, 0, 1, 600, a50);
   int m = MathMin(g1, g2);
   for(int k = 0; k + 1 < m; k++)
     {
      bool aboveNow  = a21[k]     > a50[k];
      bool abovePrev = a21[k + 1] > a50[k + 1];
      if(aboveNow != abovePrev)
        {
         g_dispCrossDir   = aboveNow ? 1 : -1;
         g_dispCrossShift = k + 1;
         break;
        }
     }
  }
//+------------------------------------------------------------------+
//| Caption at the right-hand end of each MA/VWAP line, anchored at the |
//| forming bar's time and the line's last CLOSED-bar value. Returns   |
//| true if any caption was created.                                   |
//+------------------------------------------------------------------+
bool UpdateLineLabels()
  {
   bool created = false;
   datetime t0 = iTime(_Symbol, PERIOD_M5, 0);
   bool show = InpShowLineLabels && t0 > 0;
   double v;
   if(show && InpShowMAs && MA(h21, 1, v))
     { if(DrawChartLabel("lbl21", t0, v, "  " + MALabel(InpP21, InpFastMAMethod) + " " + DoubleToString(v, _Digits), InpCol21)) created = true; }
   else DeleteChartLabel("lbl21");
   if(show && InpShowMAs && MA(h50, 1, v))
     { if(DrawChartLabel("lbl50", t0, v, "  " + MALabel(InpP50, InpFastMAMethod) + " " + DoubleToString(v, _Digits), InpCol50)) created = true; }
   else DeleteChartLabel("lbl50");
   if(show && InpShowMAs && MA(h150, 1, v))
     { if(DrawChartLabel("lblcf", t0, v, "  " + MALabel(InpPConfirm, InpConfirmMAMethod) + " " + DoubleToString(v, _Digits), InpColConfirm)) created = true; }
   else DeleteChartLabel("lblcf");
   if(show && InpShowVWAP && g_vwapValue > 0.0)
     { if(DrawChartLabel("lblvw", t0, g_vwapValue, "  VWAP " + DoubleToString(g_vwapValue, _Digits), InpColVWAP)) created = true; }
   else DeleteChartLabel("lblvw");
   return(created);
  }
//+------------------------------------------------------------------+
//| Once per new bar: one new segment per line, bar[2] -> bar[1].      |
//| VWAP uses g_vwapValue itself - the exact number CheckForEntry()    |
//| just read - joined to the previous bar's drawn value, and is left  |
//| broken across a day boundary (a session reset is not a price move) |
//| or a gap in bars (no ticks - nothing was computed for the bar).    |
//+------------------------------------------------------------------+
void UpdateMALines()
  {
   datetime tA = iTime(_Symbol, PERIOD_M5, 2);
   datetime tB = iTime(_Symbol, PERIOD_M5, 1);
   if(tA == 0 || tB == 0) return;
   if(InpShowMAs)
     {
      double a, b;
      if(MA(h21,  2, a) && MA(h21,  1, b)) DrawMASegment("21", tA, a, tB, b, InpCol21);
      if(MA(h50,  2, a) && MA(h50,  1, b)) DrawMASegment("50", tA, a, tB, b, InpCol50);
      if(MA(h150, 2, a) && MA(h150, 1, b)) DrawMASegment("cf", tA, a, tB, b, InpColConfirm);
     }
   if(InpShowVWAP && g_vwapDrawT == tA && g_vwapDrawV > 0.0 && g_vwapValue > 0.0 &&
      DayStart(tA) == DayStart(tB))
      DrawMASegment("vwap", tA, g_vwapDrawV, tB, g_vwapValue, InpColVWAP);
   g_vwapDrawT = tB;
   g_vwapDrawV = g_vwapValue;
   //--- purges everything tagged g_pm, so it runs whenever EITHER is shown
   if(InpShowMAs || InpShowVWAP) PurgeOldMALines(tB);
  }
//+------------------------------------------------------------------+
//| UpdateMALines() only draws ONE new bar's segment per call, so a     |
//| fresh attach would otherwise show a 1-bar stub per line - this      |
//| draws the whole InpMAHistoryBars window at once. Never touches bar  |
//| 0 (same shift >= 1 rule as everything else in this file).           |
//|                                                                     |
//| New vs the siblings: an iMA handle created in OnInit() usually has  |
//| not been calculated yet at that point (BarsCalculated() <= 0), and  |
//| the siblings' one-shot OnInit backfill then silently draws nothing  |
//| older than the next bar. This returns false in that case, and       |
//| OnTimer()/OnTick() retry until it succeeds.                         |
//|                                                                     |
//| VWAP history: one forward pass accumulating (H+L+C)/3 x tick volume |
//| from each day's first bar - SeedVWAP()'s maths exactly - over the   |
//| window plus up to one extra day (288 M5 bars) of lead-in, so the    |
//| oldest drawn day starts from its real first bar. The copy's first,  |
//| possibly mid-session, day is never drawn.                           |
//+------------------------------------------------------------------+
bool BackfillLines()
  {
   if(BarsCalculated(h21) <= 0 || BarsCalculated(h50) <= 0 || BarsCalculated(h150) <= 0)
      return(false);
   int avail = Bars(_Symbol, PERIOD_M5) - 2;
   int n = MathMin(InpMAHistoryBars, avail);
   if(n < 1) return(false);

   if(InpShowMAs)
     {
      double b21[], b50[], bcf[];
      datetime bt[];
      ArraySetAsSeries(b21, true); ArraySetAsSeries(b50, true);
      ArraySetAsSeries(bcf, true); ArraySetAsSeries(bt, true);
      //--- index i = shift i+1, so the segment ending at shift s uses [s-1] and [s]
      int gt = CopyTime(_Symbol, PERIOD_M5, 1, n + 1, bt);
      int g1 = CopyBuffer(h21,  0, 1, n + 1, b21);
      int g2 = CopyBuffer(h50,  0, 1, n + 1, b50);
      int g3 = CopyBuffer(h150, 0, 1, n + 1, bcf);
      int m = MathMin(MathMin(gt, g1), MathMin(g2, g3));
      if(m < 2) return(false);
      for(int s = m - 1; s >= 1; s--)
        {
         datetime tA = bt[s], tB = bt[s - 1];
         //--- EMPTY_VALUE = inside the MA's own warm-up (250 SMA on a short
         //--- history) - skip rather than draw a spike to DBL_MAX
         if(b21[s] != EMPTY_VALUE && b21[s - 1] != EMPTY_VALUE)
            DrawMASegment("21", tA, b21[s], tB, b21[s - 1], InpCol21);
         if(b50[s] != EMPTY_VALUE && b50[s - 1] != EMPTY_VALUE)
            DrawMASegment("50", tA, b50[s], tB, b50[s - 1], InpCol50);
         if(bcf[s] != EMPTY_VALUE && bcf[s - 1] != EMPTY_VALUE)
            DrawMASegment("cf", tA, bcf[s], tB, bcf[s - 1], InpColConfirm);
        }
     }

   if(InpShowVWAP)
     {
      MqlRates r[];
      ArraySetAsSeries(r, false);                       // oldest first; r[got-1] = shift 1
      int got = CopyRates(_Symbol, PERIOD_M5, 1, n + 1 + 288, r);
      double cumPV = 0.0, cumVol = 0.0;
      datetime day = 0, prevT = 0;
      double prevV = 0.0;
      bool dayValid = false, havePrev = false;
      for(int i = 0; i < got; i++)
        {
         datetime d = DayStart(r[i].time);
         if(d != day)
           {
            day = d; cumPV = 0.0; cumVol = 0.0; havePrev = false;
            dayValid = (i > 0);                         // i == 0 may be mid-session
           }
         double typical = (r[i].high + r[i].low + r[i].close) / 3.0;
         double vol = (double)r[i].tick_volume;
         cumPV  += typical * vol;
         cumVol += vol;
         double v = (cumVol > 0.0) ? cumPV / cumVol : r[i].close;
         int shift = got - i;
         if(dayValid && havePrev && shift <= n)
            DrawMASegment("vwap", prevT, prevV, r[i].time, v, InpColVWAP);
         prevT = r[i].time;
         prevV = v;
         havePrev = dayValid;
        }
      //--- hand over to UpdateMALines() so the next live segment joins on -
      //--- only if the last day was a complete session (havePrev), and never
      //--- backwards past a live bar that has already been drawn since
      if(got > 0 && havePrev && r[got - 1].time >= g_vwapDrawT)
        { g_vwapDrawT = r[got - 1].time; g_vwapDrawV = prevV; }
     }
   UpdateLineLabels();
   return(true);
  }
//+------------------------------------------------------------------+
//| Entry / safety stop of the open position, and the S/R levels the   |
//| v1.01 filter tests with their no-entry band. Returns true if any   |
//| object was CREATED (caller reclaims the panel's top-of-stack);     |
//| `deleted` reports removals (caller only needs a ChartRedraw).      |
//|                                                                    |
//| Always called BEFORE DrawPanel() in the same cycle - anything      |
//| created from inside DrawPanel() would land on top of the panel.    |
//+------------------------------------------------------------------+
bool UpdateLevelLines(bool &deleted)
  {
   bool created = false;
   deleted = false;
   double atr = g_dispATR;

   //--- open position: the entry and the safety stop actually resting at
   //--- the broker (set at entry, CheckForEntry). InpHideTradeMarks hides
   //--- MT5's own SL line, so these are the only place the stop is visible.
   if(InpShowTradeLevels && SelectOwnPositionForDisplay())
     {
      bool   isLong = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double opx    = PositionGetDouble(POSITION_PRICE_OPEN);
      double slp    = PositionGetDouble(POSITION_SL);
      if(DrawLevelLine("entry", opx, InpColEntryLine, STYLE_SOLID,
                       (isLong ? "ENTRY LONG " : "ENTRY SHORT ") + DoubleToString(opx, _Digits)))
         created = true;
      if(slp > 0.0)
        {
         double cur  = isLong ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         string away = (atr > 0.0 && cur > 0.0)
                       ? "  (" + DoubleToString(MathAbs(cur - slp) / atr, 2) + " ATR away)" : "";
         if(DrawLevelLine("sl", slp, InpColStopLine, STYLE_SOLID,
                          "SAFETY SL " + DoubleToString(slp, _Digits) + away))
            created = true;
        }
      else if(DeleteLevelLine("sl")) deleted = true;
     }
   else
     {
      if(DeleteLevelLine("entry")) deleted = true;
      if(DeleteLevelLine("sl"))    deleted = true;
     }

   //--- S/R: SRDistance() measures a BUY to the high and a SELL to the low,
   //--- with MathAbs - so the no-entry zone is +/- InpMinSRDistATR x ATR on
   //--- BOTH sides of each level. Dashed = structural level; dotted band =
   //--- where an entry on that side would be rejected right now.
   double hi, lo;
   if(InpShowSR && SRLevels(hi, lo))
     {
      string dd  = IntegerToString(InpSRDays) + "D ";
      string blk = (InpMinSRDistATR > 0.0) ? " - within " + DoubleToString(InpMinSRDistATR, 2) + " ATR blocks " : "";
      if(DrawLevelLine("srhi", hi, InpColSR, STYLE_DASH,
                       dd + "HIGH " + DoubleToString(hi, _Digits) + (blk != "" ? blk + "BUYS" : "")))
         created = true;
      if(DrawLevelLine("srlo", lo, InpColSR, STYLE_DASH,
                       dd + "LOW " + DoubleToString(lo, _Digits) + (blk != "" ? blk + "SELLS" : "")))
         created = true;
      double z = (InpShowSRZone && InpMinSRDistATR > 0.0 && atr > 0.0) ? InpMinSRDistATR * atr : 0.0;
      if(z > 0.0)
        {
         if(DrawLevelLine("srhi_up", hi + z, InpColSRZone, STYLE_DOT)) created = true;
         if(DrawLevelLine("srhi_dn", hi - z, InpColSRZone, STYLE_DOT)) created = true;
         if(DrawLevelLine("srlo_up", lo + z, InpColSRZone, STYLE_DOT)) created = true;
         if(DrawLevelLine("srlo_dn", lo - z, InpColSRZone, STYLE_DOT)) created = true;
        }
      else
        {
         if(DeleteLevelLine("srhi_up")) deleted = true;
         if(DeleteLevelLine("srhi_dn")) deleted = true;
         if(DeleteLevelLine("srlo_up")) deleted = true;
         if(DeleteLevelLine("srlo_dn")) deleted = true;
        }
     }
   else
     {
      if(DeleteLevelLine("srhi"))    deleted = true;
      if(DeleteLevelLine("srlo"))    deleted = true;
      if(DeleteLevelLine("srhi_up")) deleted = true;
      if(DeleteLevelLine("srhi_dn")) deleted = true;
      if(DeleteLevelLine("srlo_up")) deleted = true;
      if(DeleteLevelLine("srlo_dn")) deleted = true;
     }
   return(created);
  }
//+------------------------------------------------------------------+
//| First entry gate that fails for `isBuy`, checked in CheckForEntry()'s |
//| own order with its own functions and thresholds ("" = all pass).     |
//| A read-only re-evaluation for the panel - it cannot change what      |
//| CheckForEntry() decided. Spread/Friday are read NOW, so they can     |
//| differ from the instant the bar was actually dispatched.             |
//+------------------------------------------------------------------+
string DisplayFirstBlock(const bool isBuy)
  {
   if(IsFridayFlattenTime()) return("Friday");
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints) return("spread");
   double mcf, c1 = iClose(_Symbol, PERIOD_M5, 1);
   if(!MA(h150, 1, mcf)) return("MA n/a");
   if(isBuy ? !(c1 > mcf) : !(c1 < mcf)) return(MALabel(InpPConfirm, InpConfirmMAMethod));
   if(isBuy ? !(c1 > g_vwapValue) : !(c1 < g_vwapValue)) return("VWAP");
   if(g_dispATR <= 0.0) return("ATR n/a");
   double sr = SRDistance(isBuy, g_dispATR);
   if(sr >= 0.0 && sr < InpMinSRDistATR) return("S/R");
   return("");
  }
//+------------------------------------------------------------------+
//| The panel. `reclaim` = delete+recreate every object (except the    |
//| draggable bg) so the panel is the newest thing on the chart - true |
//| only when a chart object has been created since the last draw (see |
//| g_panelReclaim); false for the 1s in-place refresh and dragging.   |
//+------------------------------------------------------------------+
void DrawPanel(const bool reclaim = true)
  {
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }
   g_panelReclaim = reclaim;

   PBackground();
   PWatermark();

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;   // re-measured fresh this cycle, used by the NEXT one
   int rh = InpPanelSize + 11;
   int hdr = rh + 14;
   //--- Counted directly against the literal ty+= sequence below (project
   //--- convention - Aurelius/Fulcrum/Ratchet each found an off-by-one here):
   //--- a0(1) + ENTRY GATE(1 band + c1-c8) + POSITION(1 + p1-p5, SAME count
   //--- in and out of a trade, so nothing is left stale when a trade closes)
   //--- + DRAWN LINES(1 + l1-l6) + ACCOUNT(1 + q1-q5) = 29 rh-rows.
   //--- GAPS: after a0, s1, c8, s2, p5, s3, l6, s4 = 8.
   const int ROWS = 29, GAPS = 8;
   //--- autofit: shrink the row height until the panel fits the window
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH  = hdr + 10 + ROWS * rh + GAPS * 6 + 12;
   int guard  = 0;
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     {
      rh--; guard++;
      hdr   = rh + 14;
      bodyH = hdr + 10 + ROWS * rh + GAPS * 6 + 12;
     }
   if(g_panX < 0)                       // first draw: take the inputs
     {
      g_panX = InpPanelX;
      g_panY = InpPanelBottom ? MathMax(2, chartH - bodyH - InpPanelY) : InpPanelY;
     }
   int x = g_panX, y = g_panY;

   //--- frame first, so everything else draws on top of it (creation order)
   PRect("sh", x + 4, y + 4, w, bodyH, InpShadowCol, InpShadowCol, 0);
   PRect("bg", x, y, w, bodyH, InpPanelBg, InpPanelBg, 0);
   //--- "bg" keeps its identity across cycles so dragging works, which means
   //--- it can't reclaim top-of-stack - this opaque fill sits right on top of
   //--- it and IS recreated on every reclaim, so it's what keeps the body solid
   PRect("fl", x + 2, y + 2, w - 4, bodyH - 4, InpPanelBg, InpPanelBg, 0);
   //--- explicit 4-strip frame, not PRect's own unreliable built-in border
   PFrame("bd", x, y, w, bodyH, InpPanelEdge, 2);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);

   int ty = y + 9;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "MERIDIAN", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   bool algo = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED);
   PRow("a0", x, ty, w, "algo trading", algo ? "ON" : "OFF", algo ? 1 : 0);
   ty += rh + 6;

   //--- entry gate ----------------------------------------------------
   //--- shown for the side a cross would trade: the cross's own side if the
   //--- last closed bar crossed, otherwise the side the 21 is on now.
   double m21 = 0.0, m50 = 0.0, mcf = 0.0;
   bool   ok  = MA(h21, 1, m21) && MA(h50, 1, m50) && MA(h150, 1, mcf);
   double c1  = iClose(_Symbol, PERIOD_M5, 1);
   double atr = g_dispATR;
   bool   crossNow = (g_dispCrossDir != 0 && g_dispCrossShift == 1);
   int    dispDir  = crossNow ? g_dispCrossDir : (ok ? (m21 > m50 ? 1 : -1) : 0);
   bool   isBuy    = (dispDir >= 0);
   string cfName   = MALabel(InpPConfirm, InpConfirmMAMethod);

   bool   cfPass = ok && (isBuy ? c1 > mcf : c1 < mcf);
   bool   vwPass = g_vwapValue > 0.0 && (isBuy ? c1 > g_vwapValue : c1 < g_vwapValue);
   double sr     = SRDistance(isBuy, atr);                // the filter's own function
   bool   srPass = !(sr >= 0.0 && sr < InpMinSRDistATR);
   long   spr    = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   bool   sprPass = (spr <= InpMaxSpreadPoints);
   bool   friPass = !IsFridayFlattenTime();

   string crossTxt = "none in 600 bars";
   if(g_dispCrossDir != 0)
      crossTxt = (g_dispCrossDir > 0 ? "BUY " : "SELL ") +
                 (g_dispCrossShift == 1 ? "last bar" : IntegerToString(g_dispCrossShift) + " bars ago");

   //--- what the last closed bar actually did. OnTick() runs EITHER
   //--- ManageOpenPosition() OR CheckForEntry() per bar (see header), so a
   //--- cross on a bar that went to ManageOpenPosition() - a reversal exit,
   //--- or the post-SL stale-ticket bar - was never evaluated as an entry.
   string verdict = "-";
   int    vState  = -1;
   bool   branchValid = (g_dispBranchBar != 0 && g_dispBranchBar == iTime(_Symbol, PERIOD_M5, 1));
   bool   openedThisBar = false;
   if(SelectOwnPositionForDisplay())
      openedThisBar = ((datetime)PositionGetInteger(POSITION_TIME) >= iTime(_Symbol, PERIOD_M5, 0));
   if(!branchValid)                verdict = "waiting for a bar";
   else if(!crossNow)              verdict = g_dispBranchManaged ? "managing position" : "no cross";
   else if(g_dispBranchManaged)    verdict = "exit-only (no entry)";
   else if(openedThisBar)          { verdict = "ENTERED"; vState = 1; }
   else
     {
      string blk = DisplayFirstBlock(g_dispCrossDir > 0);
      verdict = (blk != "") ? "BLOCKED: " + blk : "not filled";
      vState  = 0;
     }

   string side = (dispDir > 0) ? "BUY" : (dispDir < 0 ? "SELL" : "-");
   PSection("s1", x, ty, w, rh, "ENTRY GATE (" + side + " side)"); ty += rh + 6;
   PRow("c1", x, ty, w, "21 vs 50", !ok ? "-" : (m21 > m50 ? "UP" : "DOWN"),
        !ok ? -1 : (m21 > m50 ? 1 : 0)); ty += rh;
   PRow("c2", x, ty, w, "last 21/50 cross", crossTxt, crossNow ? 1 : -1); ty += rh;
   PRow("c3", x, ty, w, "close vs " + cfName, !ok ? "-" : (c1 > mcf ? "above" : "below"),
        !ok ? -1 : (cfPass ? 1 : 0)); ty += rh;
   PRow("c4", x, ty, w, "close vs VWAP", g_vwapValue <= 0.0 ? "-" : (c1 > g_vwapValue ? "above" : "below"),
        g_vwapValue <= 0.0 ? -1 : (vwPass ? 1 : 0)); ty += rh;
   PRow("c5", x, ty, w, "to " + IntegerToString(InpSRDays) + "d S/R",
        sr < 0.0 ? "n/a" : DoubleToString(sr, 2) + (srPass ? " >= " : " < ") +
                           DoubleToString(InpMinSRDistATR, 2) + " ATR",
        sr < 0.0 ? -1 : (srPass ? 1 : 0)); ty += rh;
   PRow("c6", x, ty, w, "spread", IntegerToString(spr) + " / " + DoubleToString(InpMaxSpreadPoints, 0),
        sprPass ? 1 : 0); ty += rh;
   PRow("c7", x, ty, w, "Friday flatten", !InpCloseFriday ? "off" : (friPass ? "not yet" : "ACTIVE"),
        !InpCloseFriday ? -1 : (friPass ? 1 : 0)); ty += rh;
   PRow("c8", x, ty, w, "last bar", verdict, vState); ty += rh + 6;

   //--- position --------------------------------------------------------
   PSection("s2", x, ty, w, rh, "POSITION"); ty += rh + 6;
   if(SelectOwnPositionForDisplay())
     {
      bool     isLong = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double   opx    = PositionGetDouble(POSITION_PRICE_OPEN);
      double   slp    = PositionGetDouble(POSITION_SL);
      double   prof   = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      datetime ot     = (datetime)PositionGetInteger(POSITION_TIME);
      double   cur    = isLong ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double   toStop = (slp > 0.0 && cur > 0.0) ? MathAbs(cur - slp) : -1.0;
      int      held   = (int)((TimeCurrent() - ot) / PeriodSeconds(PERIOD_M5));
      PRow("p1", x, ty, w, isLong ? "LONG" : "SHORT", DoubleToString(opx, _Digits), 1); ty += rh;
      PRow("p2", x, ty, w, "safety stop", slp > 0.0 ? DoubleToString(slp, _Digits) : "none",
           slp > 0.0 ? -1 : 0); ty += rh;
      PRow("p3", x, ty, w, "to stop",
           toStop < 0.0 ? "-" : DoubleToString(toStop, 2) +
                                (atr > 0.0 ? " (" + DoubleToString(toStop / atr, 2) + " ATR)" : ""), -1); ty += rh;
      PRow("p4", x, ty, w, "floating P/L", StringFormat("%+.2f", prof), prof >= 0.0 ? 1 : 0); ty += rh;
      PRow("p5", x, ty, w, "bars held", IntegerToString(held), -1); ty += rh + 6;
     }
   else
     {
      PRow("p1", x, ty, w, "state", "FLAT", -1); ty += rh;
      PRow("p2", x, ty, w, "lot size", DoubleToString(InpLots, 2), -1); ty += rh;
      PRow("p3", x, ty, w, "safety stop",
           DoubleToString(InpSafetyStopATR, 2) + " ATR" +
           (atr > 0.0 ? " = " + DoubleToString(InpSafetyStopATR * atr, 2) : ""), -1); ty += rh;
      PRow("p4", x, ty, w, "exit", "opposite 21/50 cross", -1); ty += rh;
      PRow("p5", x, ty, w, "Friday flatten",
           InpCloseFriday ? StringFormat("%02d:00 server", InpFridayCloseHour) : "off", -1); ty += rh + 6;
     }

   //--- drawn lines - a legend: each dot is its line's own chart colour ----
   double hi = 0.0, lo = 0.0;
   bool haveSR = SRLevels(hi, lo);
   PSection("s3", x, ty, w, rh, "DRAWN LINES"); ty += rh + 6;
   PRow("l1", x, ty, w, MALabel(InpP21, InpFastMAMethod), ok ? DoubleToString(m21, _Digits) : "-", -1, InpCol21); ty += rh;
   PRow("l2", x, ty, w, MALabel(InpP50, InpFastMAMethod), ok ? DoubleToString(m50, _Digits) : "-", -1, InpCol50); ty += rh;
   PRow("l3", x, ty, w, cfName + " (confirm)", ok ? DoubleToString(mcf, _Digits) : "-", -1, InpColConfirm); ty += rh;
   PRow("l4", x, ty, w, "session VWAP", g_vwapValue > 0.0 ? DoubleToString(g_vwapValue, _Digits) : "-", -1, InpColVWAP); ty += rh;
   PRow("l5", x, ty, w, IntegerToString(InpSRDays) + "d high (buy S/R)", haveSR ? DoubleToString(hi, _Digits) : "-", -1, InpColSR); ty += rh;
   PRow("l6", x, ty, w, IntegerToString(InpSRDays) + "d low (sell S/R)", haveSR ? DoubleToString(lo, _Digits) : "-", -1, InpColSR); ty += rh + 6;

   //--- account ---------------------------------------------------------
   //--- "today" split mine/other: ACCOUNT_EQUITY is the whole account, and
   //--- this account is shared with the other EAs (see header)
   PSection("s4", x, ty, w, rh, "ACCOUNT"); ty += rh + 6;
   double bal     = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq      = AccountInfoDouble(ACCOUNT_EQUITY);
   double dayPL   = (g_dayStartEquity > 0.0) ? eq - g_dayStartEquity : 0.0;
   double myDayPL = g_myRealizedToday + MyFloatingPL();
   double otherPL = dayPL - myDayPL;
   PRow("q1", x, ty, w, "balance", DoubleToString(bal, 2), -1); ty += rh;
   PRow("q2", x, ty, w, "equity", DoubleToString(eq, 2), eq >= bal ? 1 : 0); ty += rh;
   PRow("q3", x, ty, w, "today (mine)", StringFormat("%+.2f", myDayPL), myDayPL >= 0.0 ? 1 : 0); ty += rh;
   PRow("q4", x, ty, w, "today (other)", StringFormat("%+.2f", otherPL),
        otherPL == 0.0 ? -1 : (otherPL >= 0.0 ? 1 : 0)); ty += rh;
   PRow("q5", x, ty, w, "magic", IntegerToString((long)InpMagic), -1); ty += rh;

   //--- if the row count ever drifts from ROWS/GAPS, say so in the log
   //--- instead of silently clipping the panel (Aurelius/Ratchet)
   static int warned = 0;
   int used = ty + 12 - y;
   if(used > bodyH && warned < 3)
     { warned++; PrintFormat("Meridian EA: panel content %d px vs frame %d px", used, bodyH); }
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   //--- v1.03 PERFORMANCE: see g_skipCosmeticDraws' declaration. Set first,
   //--- before anything that could draw.
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);

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

   //--- v1.03 visuals - skipped entirely in a non-visual Tester run. Drawn
   //--- the moment it attaches (Fulcrum v2.08's lesson: don't wait for the
   //--- first tick), chart objects first and the panel LAST so it starts on
   //--- top. The timer is only ever started here, inside the same gate.
   if(!g_skipCosmeticDraws)
     {
      //--- MQL5 keeps an EA's globals across a parameter-change re-init, but
      //--- OnDeinit() just deleted every object - so start the display state
      //--- clean, or e.g. g_bgOK=true would stop the wallpaper ever reloading
      g_bgOK = false; g_bgTries = 0; g_panX = -1; g_panY = -1; g_panelMinW = 0;
      g_vwapDrawT = 0; g_vwapDrawV = 0.0; g_dispBranchBar = 0; g_dayStamp = -1;
      PTheme();
      UpdateDayStamp();
      RefreshDisplayState();
      g_backfilled = BackfillLines();   // often false here - iMA not calculated yet; retried
      bool dummy = false;
      UpdateLevelLines(dummy);
      DrawPanel(true);
      ChartRedraw(0);
      EventSetTimer(1);
     }

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   IndicatorRelease(h21);
   IndicatorRelease(h50);
   IndicatorRelease(h150);
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pw);
   ObjectsDeleteAll(0, g_pm);
   ObjectsDeleteAll(0, g_pl);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| v1.03: keeps the panel live between bars and when no ticks arrive |
//| (weekend, closed session). Never started in a non-visual Tester   |
//| run; the early return is a defense-in-depth backstop (Ratchet     |
//| v3.15). Updates in place - reclaims top-of-stack only when this   |
//| call itself just created a chart object.                          |
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(g_skipCosmeticDraws) return;
   PBackground();                                   // retries until the image loads (or gives up)
   if(g_dispATR <= 0.0) RefreshDisplayState();      // attach before enough history - try again
   bool reclaim = false;
   if(!g_backfilled)
     {
      g_backfilled = BackfillLines();
      if(g_backfilled) reclaim = true;
     }
   bool deleted = false;
   if(UpdateLevelLines(deleted)) reclaim = true;    // e.g. entry/SL lines right after a fill
   DrawPanel(reclaim);
   //--- a forced redraw every second fights the user's own scrolling/panning
   //--- (Aurelius v1.38) - only when something changed or P/L is floating live
   if(reclaim || deleted || SelectOwnPositionForDisplay()) ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| v1.03: dragging the panel background moves the whole panel;       |
//| resizing the chart re-centres the wallpaper/watermark.            |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(g_skipCosmeticDraws) return;
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_pp + "bg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      DrawPanel(false);            // reposition only - reclaiming mid-drag would be jarring
      ChartRedraw(0);
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      //--- MT5 also raises CHART_CHANGE for plain scrolling/panning - only
      //--- react to a genuine resize, or every scroll tick redraws everything
      //--- (the flashing Aurelius found)
      static int lastW = -1, lastH = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lastW || nh != lastH)
        {
         lastW = nw; lastH = nh; g_bgOK = false; g_bgTries = 0;
         PBackground();
         PWatermark();
         if(InpPanelBottom) { g_panX = -1; DrawPanel(false); }
        }
     }
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- v1.03: day boundary for the panel's "today" rows - cosmetic, gated
   if(!g_skipCosmeticDraws) UpdateDayStamp();

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

   // v1.03, cosmetic: remember which branch below this bar takes, so the
   // panel can say "exit-only" for a cross that was never an entry check.
   // Reads g_ticket, writes only display state - the branch is unchanged.
   if(!g_skipCosmeticDraws)
     {
      g_dispBranchBar     = iTime(_Symbol, PERIOD_M5, 1);
      g_dispBranchManaged = (g_ticket != 0);
     }

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

   // v1.03 visuals, AFTER this bar's trading decision (so a position opened
   // or closed just now is drawn now, not a bar late) and skipped entirely
   // in a non-visual Tester run. Order is the layering: every chart object
   // (MA/VWAP segments, captions, level lines) first, the panel LAST with
   // reclaim=true, because MT5 stacks by creation order, not ZORDER.
   if(!g_skipCosmeticDraws)
     {
      RefreshDisplayState();
      if(!g_backfilled) g_backfilled = BackfillLines();
      UpdateMALines();
      UpdateLineLabels();
      bool deleted = false;
      UpdateLevelLines(deleted);
      DrawPanel(true);
      ChartRedraw(0);
     }
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

   // v1.03 panel "today (mine)": O(1) running total of this EA's own realized
   // result, once per deal (never a HistorySelect() scan - the Aurelius/
   // Ratchet v3.15 backtest-speed lesson). Commission is counted on every
   // deal including the opening one, since the broker charges it there and
   // POSITION_PROFIT (the floating half of "mine") never includes it.
   // Display only - nothing reads it but DrawPanel().
   g_myRealizedToday += HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      g_myRealizedToday += HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
                         + HistoryDealGetDouble(trans.deal, DEAL_SWAP);

   if(entry == DEAL_ENTRY_IN)
      NotifyPush(StringFormat("Meridian %s OPEN %.2f lots @ %.2f", side, vol, price));
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      NotifyPush(StringFormat("Meridian %s CLOSE %.2f lots @ %.2f P/L=%.2f", side, vol, price, profit));
     }
  }
//+------------------------------------------------------------------+
