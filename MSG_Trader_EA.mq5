//+------------------------------------------------------------------+
//|                        MSG_Trader_EA.mq5                          |
//|                                                                    |
//|  RECONSTRUCTION, not a port. No source for MSG_Trader_EA_v1.1     |
//|  exists in this project - only a real MT5 Strategy Tester report  |
//|  (account 1301880049, GOLD#, M5, 2026.06.01-2026.08.31, 0.03      |
//|  lots) was available. Built at the user's explicit request after  |
//|  being asked directly ("I don't see the source... how should I    |
//|  proceed?") and choosing reverse-engineering over waiting for the |
//|  real file. What follows is separated into what the report        |
//|  actually PROVED vs what is this file's own best-effort inference |
//|  - do not treat the inferred parts as verified.                   |
//|                                                                    |
//|  CONFIRMED from the real report (exact, not guessed):              |
//|   - Every input name/value in the Settings block below (lots,      |
//|     magic, slippage, fib SL %, scale-out RR levels 1.0/1.5/2.0,    |
//|     trail RR 1.0, max hold 48h, all 4 session windows, chart-draw  |
//|     toggles, history days) - copied verbatim from the report.      |
//|   - The broker-side take-profit is EXACTLY entry +/- 2.000x the    |
//|     position's own risk (SL distance) on every one of 68 real      |
//|     trades checked (mean RR=2.0001, stdev=0.0007) - matches         |
//|     InpTP3_RR=2.0 used as the final/outer target.                  |
//|   - Only MSG1 (22:00-00:00 GMT) and MSG3 (09:00-12:00 GMT) were    |
//|     enabled in the tested run; MSG2/MSG4 never fired a trade.      |
//|   - Entries cluster in a 60-90% retracement zone of that session's |
//|     own high/low range (mean 80.4%, median 75.1% across 47 sampled |
//|     trades, measured against real M5 bars) - a classic Fibonacci   |
//|     "OTE" continuation entry, not a flat breakout-at-the-extreme.  |
//|   - Stop-loss distance is NOT a fixed fib % of that range (matches |
//|     InpFixedFibSL=false): measured SL retracement % varied bar to  |
//|     bar (0%, 25-40%, up to 57%) rather than clustering on one       |
//|     constant - consistent with a structural (swing-based) stop,    |
//|     not InpFibSLPct applied directly.                               |
//|                                                                    |
//|  INFERRED (this file's own design, not verifiable without the      |
//|  real source - flagged so it is never mistaken for a proven port): |
//|   - The exact retracement zone boundary (61.8%-78.6%, the standard |
//|     ICT/fib "OTE" window). The stop distance itself (InpRangeRiskPct|
//|     of the session range) IS real-data-calibrated as of v1.04 - see |
//|     its own header note below - not left as a guess.               |
//|   - InpTPMode's meaning (0 = 3-stage scale-out via TP1/TP2/TP3;     |
//|     any other value = single fixed target at InpTP_RR) - the       |
//|     report only ever showed TPMode=0.                              |
//|   - InpTrailRR's exact behaviour: no longer inferred at all. Fully  |
//|     CONFIRMED as of v1.11 by direct measurement of the real M1      |
//|     report's own stop prices - a STATIC lock-in level at entry      |
//|     +/- 1.000R set once at TP2, exact on 20 of 20 real trades       |
//|     (see the v1.11 block below). v1.09 had the trigger and the      |
//|     value right but the mechanism wrong (it built a ratchet).       |
//|   - GMT-offset auto-detection (TimeGMT()-TimeTradeServer(), see    |
//|     BrokerGMTOffsetHours()) - the report ran with InpGMTOffset=0    |
//|     and auto-detect on, so this was never exercised against a      |
//|     non-zero broker offset.                                        |
//|                                                                    |
//|  Before trusting this the way the project's other EAs are trusted, |
//|  it needs: a real MT5 Strategy Tester run over the same real       |
//|  2026.06.01-2026.08.31 window, compared trade-by-trade against the |
//|  uploaded report (win rate, RR=2.0 on every trade, session split), |
//|  the same rigor already applied to every validated construction    |
//|  in this project.                                                  |
//|                                                                    |
//|  Visual system (panel/watermark/chart theme/restart-safe position  |
//|  sync) matches this project's established standard - reused        |
//|  verbatim from Vanguard_EA.mq5 where the mechanism is generic       |
//|  (PRect/PFrame/PText/PRow/PSection/PTheme/PWatermark/PBackground,   |
//|  the reclaim-on-new-bar-only pattern, restart-safe SyncPositionState|
//|  / FindOwnPosition, the non-visual-tester cosmetic-draw skip).      |
//|  Panel content and chart drawings (session range box, fib levels,  |
//|  history) are new, specific to this construction.                  |
//|                                                                    |
//|  v1.01 ADDS InpOneTradeAfterLoss (default FALSE - opt-in, see       |
//|  below): found by analysing the REAL 8-month MSG3-only report       |
//|  (account 1301880049, 2026.01-2026.08, 86 real round-trip trades) - |
//|  two of the worst losses (2026.02.11 and 2026.03.25) were each a    |
//|  SAME-DAY re-entry into the exact same stopped-out zone (identical  |
//|  SL price both times: 5061.51 and 4540.22) - a revenge re-entry,    |
//|  not two independent bad trades. Blocking any further entry once    |
//|  one loss has happened that day: net 18,145.57->18,720.44 (+3.2%),  |
//|  max balance DD 3,774.60->2,440.98 (-35.3%), preserves 19/20 top     |
//|  trades (drops one +1,073.05 winner), holds up on a chronological    |
//|  70/30 IS/OOS split (+2.0% IS, +16.2% OOS - not a one-sided fluke).  |
//|  HONEST CAVEAT: only 15 of 86 trades are ever cut by this rule -     |
//|  a permutation test against random same-size cuts gives p=0.11-0.12,|
//|  NOT below the usual 0.05 bar. Real, mechanistically sensible (a     |
//|  same-zone double stop-out is a real, checkable event in the data), |
//|  but not statistically proven at this sample size - left OFF by      |
//|  default rather than presented as a validated filter.                |
//|                                                                    |
//|  v1.02 FIXES A REAL BUG found from the user's own real MT5 test on  |
//|  v1.01 (2026.01-09.21, GOLD#, account 1301959345): 406 trades vs     |
//|  the real EA's 169, 43.6% win rate vs the real 71%, account          |
//|  drawdown hit 100.2% (wiped out) by 2026.04.13. Root cause: a        |
//|  session's frozen range stayed re-armable for ~21h (until that       |
//|  session's window reopened), so ordinary chop around the range       |
//|  boundary could break out, retrace into the zone, enter, stop out,   |
//|  break out again, retrace again, enter again - repeatedly, all on    |
//|  the SAME static range. Confirmed directly: 59 of 68 trading days    |
//|  had more than one entry, averaging 4.9/day, one day hit 14. The     |
//|  real report never shows more than 2 trades on any day. Fixed with   |
//|  g_sesRangeTraded[] (see its own header note): once a trade is       |
//|  taken from a session's current range, that range is retired -       |
//|  no further entries from it until its window reopens and freezes     |
//|  a brand new one. NOT yet re-tested on a real MT5 run - needs that    |
//|  before the overtrading is confirmed fixed, not just reasoned about. |
//|                                                                    |
//|  v1.03 ADDS InpMaxSetupWatchHours=4.25 (real-data calibrated): v1.02 |
//|  still overtraded on the user's real MT5 run (360 trades vs the      |
//|  real EA's 169, still net-negative, 82.55% DD) because the one-      |
//|  trade-per-range fix only stopped WITHIN-range repeat-firing, not     |
//|  the deeper issue - the retracement zone was being watched for the   |
//|  FULL ~21h until the session reopened, while the real EA is far      |
//|  more time-limited. Checked directly against the real 8-month        |
//|  MSG3-only report (159 session-days with real M5 bar coverage):      |
//|  EVERY real entry happened within 4.08h of the session closing -     |
//|  none later. Cross-checking my own zone-touch trigger against real   |
//|  per-day outcomes: with no time limit, precision (of the days my     |
//|  trigger fires, how many the real EA also traded) was only 48%;      |
//|  with a 4.25h cutoff, precision rises to 76%, recall 67%. Real,      |
//|  measured against actual day-by-day data - not a fresh guess. Not    |
//|  a perfect match (24% of my fires still don't correspond to a real   |
//|  trade, and 33% of real trades aren't found by this zone logic at    |
//|  all - a different/additional trigger likely exists) - still needs   |
//|  a real MT5 re-test before trusting the overtrading is resolved.     |
//|                                                                    |
//|  v1.04 FIXES THE STOP DISTANCE. v1.03's real re-test got trade       |
//|  count right (181 vs real 169) and direction right (43/45 = 95.6%    |
//|  match on days both models fire), but was still net-negative (win    |
//|  rate 39% vs real 71%, PF 0.64) with average hold time of just 11    |
//|  minutes vs the real 63 minutes - trades were getting stopped out    |
//|  ~5x faster than real ones. Root cause: the "structural" stop (last  |
//|  InpStructLookback bars' extreme) measured a median risk of just     |
//|  $2.59 - a tight local-noise stop, nothing like the real EA's own    |
//|  risk. Checked the real 8-month report's actual risk-to-range ratio  |
//|  directly (82 trades with real M5 bar coverage): median 41.7%,       |
//|  mean 45.9%, tightly clustered (most between 33%-54%) - a real,      |
//|  measured relationship, not a guess. InpRangeRiskPct=41.7 replaces   |
//|  the old bar-lookback stop entirely: risk is now that % of the       |
//|  session's own finalized range, applied directly from the entry      |
//|  price. Still needs a real MT5 re-test - if win rate/PF come back    |
//|  in line with the real report, this is the fix; if not, the entry    |
//|  price itself (not just the stop) may also differ from real.         |
//|                                                                    |
//|  v1.04 REAL RE-TEST (MSG3-only, matching the real report's own       |
//|  config directly): net +2,199.84 (real: +18,145.57), PF 1.12 (real   |
//|  1.82), win rate 57.55% (real 71.0%) - genuinely profitable now,      |
//|  and trade SHAPE matches closely (avg win 345.66 vs real 335.18,      |
//|  avg loss -419.67 vs real -450.53, avg hold 1:02:29 vs real 1:03:01,  |
//|  max DD 37.81%/42.06% vs real 37.75%/42.43% - all close). Remaining   |
//|  gap is pure selectivity, not trade sizing. Tried zone-width sweeps   |
//|  (50-90% range) and multi-bar zone confirmation (1-4 bars) against    |
//|  the real day-by-day record - neither broke past ~75-76% precision,   |
//|  confirming the zone-touch trigger itself has a real ceiling, not a   |
//|  tuning gap.                                                          |
//|                                                                    |
//|  v1.05 FIXES THE SL REFERENCE POINT. User's own hypothesis (SL at     |
//|  the range boundary) tested directly: not exact (only 2/82 real       |
//|  trades have SL within 1% of L/H), but measuring SL's distance FROM   |
//|  the block edge (instead of from entry, v1.04's approach) is a        |
//|  visibly tighter fit - interquartile 26-38% of range vs 33-54% when   |
//|  measured from entry. Real: entry moves around inside the 61.8-78.6%  |
//|  OTE zone, but SL stays close to a FIXED level relative to L/H         |
//|  regardless - a structural stop, not one measured from the fill        |
//|  price. InpRangeRiskPct=30.8 (median) now applies from the range's     |
//|  own L/H rather than from entry. Not yet re-tested on a real MT5 run.  |
//|                                                                    |
//|  v1.05 REAL RE-TEST (MSG3-only): net +1,513.50 (v1.04 was            |
//|  +2,199.84), win rate 58.49% (v1.04: 57.55%) - the tighter stop        |
//|  barely moved win rate at all, just shrank average win/loss size       |
//|  proportionally (TP is always 2x risk) and lowered DD 37.81%->29.78%.  |
//|  CONCLUSION: the SL reference point was never the real bottleneck -     |
//|  same 106 trades both versions, so it only rescales risk, not which     |
//|  setups get selected.                                                   |
//|                                                                    |
//|  v1.06 ADDS A MINIMUM BREAKOUT EXTENSION FILTER (InpMinExtensionPct     |
//|  =15.0) - found by comparing the real per-day false-positive vs         |
//|  true-positive cases directly: on days my zone-touch trigger fires      |
//|  but the real EA does NOT trade, the breakout only extended a median    |
//|  of ~3.1 points beyond the range before retracing; on days that DO      |
//|  match a real trade, the median extension is ~9.9 points - a ~3x        |
//|  real difference, not noise. Swept the threshold against the real       |
//|  86-trade day-by-day record: 0% gives 76.3% precision/67.2% recall;     |
//|  15% gives 89.6% precision/64.2% recall (cuts false positives from      |
//|  14 to 5 while losing only 2 of 45 true positives) - the best real       |
//|  tradeoff found. A marginal few-point poke past the range is noise,      |
//|  not a genuine breakout with real directional conviction. Not yet        |
//|  re-tested on a real MT5 run.                                            |
//|                                                                    |
//|  v1.07 RECALIBRATES FOR M1. A genuine real M1 backtest of the ACTUAL      |
//|  T1 EA surfaced (Strategy Tester's period selector isn't gated the same   |
//|  way live-chart attachment is - the real EA forces a live M1 chart back   |
//|  to M5, but a Tester run can still be set to M1, producing a real report: |
//|  108 round-trip trades, 2026.01.01-2026.09.21, PF 1.894, win rate 70.14%, |
//|  DD 28.19%/31.21% - genuinely better than the real M5 report on several   |
//|  real axes, not just a hunch). Made the file period-agnostic (every        |
//|  PERIOD_M5 literal replaced with _Period; OnInit now accepts M1 or M5,    |
//|  refuses anything else) and recalibrated against real M1 bars/trades      |
//|  (GOLD#_PERIOD_M1.csv, 2025.11.12-2026.09.18, covering all but the last   |
//|  ~3 days of the report) using the exact same measurement discipline as    |
//|  every M5 version above:                                                  |
//|   - RR: confirmed ~2.0 by design (mean 2.0009) but with real, much wider  |
//|     scatter than M5's near-zero variance (stdev 0.194 vs 0.0007) - M1's   |
//|     order-decision-to-fill gap is proportionally larger relative to a     |
//|     1-minute bar's own price move than M5's gap is to a 5-minute bar's -  |
//|     a real execution/slippage effect, not a flaw in the RR=2.0 design     |
//|     itself (this file computes SL/TP from decision-bar values only, same  |
//|     as before, so no code change follows from this - flagged for the      |
//|     record, not acted on).                                                |
//|   - InpRangeRiskPct and InpMaxSetupWatchHours: RE-CONFIRMED, NOT CHANGED. |
//|     Real M1 risk-from-block-edge median is 30.63% (M5: 30.8%) and real    |
//|     M1 entries topped out at 3.95h after session close (M5: 4.08h) -      |
//|     both close enough to the existing M5-derived values that they hold    |
//|     for M1 too without adjustment. These two properties appear to be      |
//|     real characteristics of the session/price structure itself, not the   |
//|     bar granularity used to detect them.                                  |
//|   - InpMinExtensionPct: genuinely different on M1. Same false-positive-   |
//|     vs-true-positive day classification as v1.06's M5 work, rebuilt       |
//|     against real M1 bars: 0% gives 78.0% precision/70.3% recall; 10%      |
//|     gives 95.3% precision/67.0% recall (only 3 false positives left, vs   |
//|     18 at 0%) - the best M1 tradeoff, tighter than M5 needed (M5's own    |
//|     optimum was 15%, only reaching 89.6%/64.2%). M1's finer bars need     |
//|     less aggressive filtering to get the same false-positive rejection.   |
//|   - InpZoneTopPct: also genuinely different. Widening the OTE zone from   |
//|     61.8% to 50% (keeping InpZoneBotPct=78.6%) raises real recall from    |
//|     67.0% to 89.0% for only a small precision cost (95.3%->91.0%, 8 false |
//|     positives instead of 3) - checked for overfitting with a chronological|
//|     half-split (first half: 88.0%/86.3%, second half: 94.9%/92.5% - holds |
//|     up in both, actually stronger in the second half, not a fluke).       |
//|     Combined final M1 config (zone 50-78.6%, min ext 10%, watch 4.25h):   |
//|     91.0% precision / 89.0% recall against the real 92-day M1 record -    |
//|     meaningfully tighter day-selection than the M5 reconstruction ever    |
//|     achieved (v1.06's best was 89.6%/64.2%).                              |
//|   - InpZoneTopPct and InpMinExtensionPct now default to their M1 values - |
//|     SET THEM BACK to 61.8 / 15.0 if running this file on an M5 chart      |
//|     (OnInit prints a warning if it detects the mismatch). InpRangeRiskPct |
//|     and InpMaxSetupWatchHours need no per-period override.                |
//|   - NOT YET verified with a real MT5 M1 Strategy Tester run of this        |
//|     reconstruction itself (only the real T1 EA's own M1 report exists     |
//|     so far) - needs that before trusting these numbers the way the M5      |
//|     versions' real re-tests are trusted.                                   |
//|                                                                    |
//|  v1.07 REAL M1 RE-TEST (first attempt used a stale InpZoneTopPct=61.8      |
//|  left over from a previous MT5 input-cache session, not a clean v1.07       |
//|  test - net -823, PF 0.93. Re-run with the correct 50/78.6/30.8/10.0/4.25   |
//|  config): net +21,479.90 (real M1 report: +22,358.79, 96% of real), PF      |
//|  1.839 (real: 1.894, 97%), win rate 63.84% (real: 70.14%), 96 round-trip    |
//|  trades (real: 108, 89%) - by far the closest convergence this              |
//|  reconstruction has reached on either timeframe. Two real gaps remained:    |
//|  drawdown (42.41%/38.20% vs real 28.19%/31.21%) and trade concentration     |
//|  (top-20 = 167.1% of net vs real 125.1%) - both worse than real despite     |
//|  net/PF being close.                                                        |
//|                                                                    |
//|  v1.08 FIXES THE MAX-HOLD CAP - the real cause of both v1.07 gaps above.    |
//|  Found by inspecting the actual trades: one M1 trade ran 80.8 HOURS         |
//|  (opened Thu 16:12, a weekend gap pushed its 48h nominal cap into the       |
//|  closed market, so it only force-closed at the first bar after Monday's    |
//|  reopen) and single-handedly contributed $6,958.88 - close to a third of    |
//|  the period's entire net profit. Checked both real reports directly for    |
//|  their ACTUAL observed hold times (not the shipped 48h input, which        |
//|  neither ever came close to using): real M1 max hold across all 108        |
//|  trades is 5.16h (95th percentile 2.5h); real M5 max across 86 trades is    |
//|  10.95h (95th percentile 2.67h). The real EA's true 48h setting apparently  |
//|  never actually binds in practice - something else reliably exits every    |
//|  real trade within hours, well before 48h ever matters. This file has no   |
//|  equivalent of that unknown mechanism, so a rare slow-drifting trade with   |
//|  no other exit trigger can ride the nominal cap into a multi-day outlier -  |
//|  exactly what happened. INFERRED FIX, not a discovery of what the real     |
//|  mechanism actually is: InpMaxHoldHours tightened to 6 (M1) / 12 (M5) -     |
//|  the real observed max plus headroom, a proxy that prevents the             |
//|  pathological case without claiming to know the real EA's real exit logic. |
//|                                                                    |
//|  v1.08 REAL M1 RE-TEST (took two attempts - the first still showed the      |
//|  80.8h outlier because InpMaxHoldHours was stuck at a cached 48 from a       |
//|  previous MT5 session, same input-cache trap as v1.07's own first attempt;  |
//|  re-run with InpMaxHoldHours correctly at 6 confirmed max hold capped at     |
//|  6:01:01, no more outlier): net +15,983.75 (v1.07 was +21,479.90, -25.6%),   |
//|  PF 1.614 (v1.07: 1.839, worse), equity DD 24.14% (v1.07: 38.37%, much       |
//|  better), balance DD 41.99% (v1.07: 42.32%, basically unchanged). Capping    |
//|  that outlier trade removed both its pathological risk AND the large real    |
//|  profit its eventual favorable resolution produced - an honest trade-off,    |
//|  not a clean win. Whether 6h is the RIGHT cap (vs just A cap, taken from      |
//|  the real observed max) is still an open question.                           |
//|                                                                    |
//|  v1.09 FIXES THE TRAIL MECHANISM - the real EA's own UI (a user screenshot   |
//|  of the actual T1 EA's Inputs tab) labels InpTP1_RR "1st target (R) - then    |
//|  stop to break-even" and InpTrailRR "Trail lock-in (R) after 2nd target",     |
//|  next to a separate "2nd target (R) - then trail stop" label on InpTP2_RR -   |
//|  confirming a TWO-STAGE mechanism this file never implemented: a one-time     |
//|  move to breakeven at TP1 (already had this, just tied to the wrong trigger  |
//|  - InpTrailRR reaching its own threshold, not TP1 itself), then a CONTINUOUS  |
//|  trailing stop from TP2 onward that keeps InpTrailRR x risk of profit locked  |
//|  in as price extends further favorably. v1.01-v1.08 only ever moved to        |
//|  breakeven once and then left the remaining position with a fully static      |
//|  stop all the way to TP3 or the max-hold timer - very plausibly the real       |
//|  cause of the real EA's own short observed hold times (v1.08's header above): |
//|  a real trailing stop exits on its own the moment price pulls back by the      |
//|  lock-in distance, it doesn't need a timer to end a trade at all. Not yet       |
//|  re-tested on a real MT5 run - if this closes the hold-time gap on its own,     |
//|  InpMaxHoldHours may not need to be as aggressively tightened as v1.08 made     |
//|  it; that's a real open question for the next real test to answer.              |
//|                                                                    |
//|  v1.10 REVERTS InpMaxHoldHours to 48 (v1.08's 6/12 split removed). Real,          |
//|  controlled A/B test on two identical M1 configs (v1.09 trailing stop active      |
//|  in both, only InpMaxHoldHours differing) proved 48 genuinely beats 6: net         |
//|  +20,731.20 vs +14,805.10, PF 1.804 vs 1.562 - the tight cap was cutting off        |
//|  real, still-developing profitable trades, not just the one pathological           |
//|  outlier. v1.08's theory (tighten the cap to match the real EA's observed           |
//|  ceiling) is DISPROVEN by this direct comparison, not just unconfirmed.              |
//|                                                                    |
//|  HONEST UNRESOLVED FINDING: the SAME outlier trade still ran 32:49:58 in the          |
//|  48h test - not capped by the 48h timer (32.8h < 48h, so the timer never fired),       |
//|  and NOT caught by v1.09's new trailing stop either. Root cause, reasoned from          |
//|  this: a trailing stop only protects against a REVERSAL - it does nothing for a          |
//|  trade that grinds slowly in its favorable direction without ever pulling back by         |
//|  the full lock-in distance. That appears to be what happened here. Neither lever            |
//|  tried so far (tight time cap, trailing stop) actually explains why the real EA's             |
//|  own trades never take anywhere near this long (real max 5.16h M1 / 10.95h M5) -               |
//|  this remains a genuine, unexplained gap in the reconstruction, not something this              |
//|  version claims to have fixed. Flagged rather than papered over with another guess.              |
//|                                                                    |
//|  v1.11 ANSWERS v1.10's UNRESOLVED QUESTION - and the answer is that v1.09 implemented             |
//|  the RIGHT input with the WRONG mechanism. Re-parsed the real M1 report's Orders+Deals            |
//|  tables directly (108 round-trips, grouped by cumulative volume in/out, same methodology          |
//|  as every version above) and looked at the exit LEG-BY-LEG rather than just at hold time.         |
//|  39 of the 108 real trades scale out all three legs, so the post-TP2 stage is directly             |
//|  observable on them.                                                                               |
//|                                                                    |
//|  CONFIRMED - the real exit ladder, measured to full precision, three stages, each exact:           |
//|   - Before TP1: stop sits at the original -1.000R. 43 of the 44 one-leg trades closed at            |
//|     exactly -1.0000R (the 44th closed on the broker TP).                                            |
//|   - At TP1 (1.0R, 1/3 out): stop moves to EXACTLY breakeven. All 21 of the 21 two-leg               |
//|     trades that closed on a stop closed at 0.0000R - min -0.0000, max 0.0000, no spread.            |
//|     This file already did this correctly; re-confirmed, not changed.                                |
//|   - At TP2 (1.5R, half the remainder out): stop moves to EXACTLY entry +/- 1.000R and then          |
//|     NEVER MOVES AGAIN. All 20 of the 20 three-leg trades whose final leg closed on a stop           |
//|     closed at exactly 1.000000R - mean 1.000000, stdev 0.000000, across real risks ranging          |
//|     6.64 to 29.13 points and TP2->exit times from 0.15 to 25.5 minutes. The other 19 of the         |
//|     39 ran to the 2.0R broker TP. So the final leg lives in a 1.0R-wide corridor: a hard            |
//|     floor at +1.0R and the broker TP at +2.0R.                                                       |
//|                                                                    |
//|  THE RATCHET IS DISPROVEN, NOT MERELY UNCONFIRMED. Replayed real M1 bars                             |
//|  (GOLD#_PERIOD_M1.csv) between each real TP2 fill and each real final exit and measured how          |
//|  far price actually ran past TP2 before reversing: post-TP2 peaks span 1.127R to 1.954R              |
//|  (median 1.628R; 10 of 20 went past 1.6R, 5 past 1.75R). v1.09's peak-minus-1.0R ratchet             |
//|  would therefore have exited those same 20 trades anywhere between 0.127R and 0.954R, each           |
//|  one at a different level. The real report shows all 20 at a flat, identical 1.000R.                 |
//|  Zero of 20 fit a ratchet; 20 of 20 fit a static level. The clearest single case: the                |
//|  2026-06-17 trade peaked at 1.954R after TP2 and still exited at exactly 1.000R - a ratchet          |
//|  would have had its stop up at 0.954R by then and would have closed it there.                        |
//|                                                                    |
//|  THIS IS ALSO WHY v1.10's 32.8h OUTLIER SURVIVED THE TRAIL, and the reason is structural,            |
//|  not a matter of tuning. A ratchet's stop is (running peak - InpTrailRR x risk), and the             |
//|  peak can never exceed 2.0R because the broker TP closes the trade there - so the ratchet's          |
//|  stop is mathematically BOUNDED ABOVE by 2.0R - 1.0R = 1.0R, i.e. it is at or below the real         |
//|  EA's static floor at every price on every path, and starts a full 0.5R below it the moment          |
//|  TP2 fires (peak 1.5R -> stop 0.5R, vs the real EA's 1.0R). A position grinding between              |
//|  1.5R and 1.9R touches neither the 2.0R TP nor a stop down at 0.5-0.9R, and can sit there            |
//|  for as long as the grind lasts - which is exactly the "slow monotonic grind" failure mode           |
//|  v1.10's header described but attributed to trailing stops in general. It is not general:            |
//|  it is specific to a ratchet. The real EA's static floor makes the corridor 1.0R wide                |
//|  instead of up to 1.5R wide and, because it is weakly tighter than the ratchet on every              |
//|  path, it closes the remaining leg no later than v1.09 would have on any path - usually              |
//|  much sooner.                                                                                        |
//|                                                                    |
//|  INDEPENDENT CHECK - bar-replay of the candidate rules against the real timing. Walked real          |
//|  M1 bars forward from each of the 39 real TP2 fills, exiting on whichever of the candidate           |
//|  stop or the real broker TP came first, and compared five statistics against the real                |
//|  observed TP2->final-exit behaviour:                                                                 |
//|        rule                    median   mean    p90     max      sl/tp split                         |
//|        REAL observed           3.72m    7.98m    -      54.3m    20 / 19                             |
//|        static +1.0R (v1.11)    3.18m    7.64m   21.3m   53.6m    21 / 18   <- adopted                |
//|        ratchet peak-1.0R(1.09) 8.35m   13.26m   39.5m   69.5m    16 / 23                             |
//|        ratchet peak-0.5R       3.18m    5.03m   16.5m   26.6m    25 / 14                             |
//|  The static +1.0R rule matches real on all five at once. Note particularly the sl/tp split:          |
//|  simply tightening InpTrailRR to 0.5 (the obvious "just shrink the knob" move) recovers the          |
//|  median but gets the outcome mix badly wrong - 25 stop-outs vs the real 20, because a tight          |
//|  ratchet strangles the runners that should reach 2.0R. Fixed-level and tighter-ratchet are           |
//|  genuinely different rules, and the data picks the fixed level.                                      |
//|                                                                    |
//|  THE CHANGE: InpTrailRR's VALUE stays at 1.0 (now independently confirmed by measurement,            |
//|  not just copied from the real EA's inputs screen). The post-TP2 block in                            |
//|  ManageOpenPosition() no longer recomputes the stop from the live price on every tick;               |
//|  it sets the stop once to entry +/- InpTrailRR x risk and re-asserts that same level                 |
//|  idempotently (covering a failed PositionModify or an EA restart) but never walks it                 |
//|  further. This is a one-line-of-arithmetic change - g_posEntry instead of price - but it             |
//|  is a different exit rule, not a re-tuning of the old one.                                            |
//|                                                                    |
//|  STILL INFERRED, flagged so it is not read as more than it is:                                        |
//|   - WHICH input the +1.0R level is read from. InpTrailRR=1.0 and InpTP1_RR=1.0 are both 1.0           |
//|     in the only configuration ever observed, so this data cannot distinguish "lock in                 |
//|     InpTrailRR" from "put the stop back at the TP1 price". The real EA's own UI label                 |
//|     ("Trail lock-in (R) after 2nd target" sitting on InpTrailRR) is the tiebreaker used               |
//|     here, and it is a label, not a measurement. If someone ever runs the real EA with                 |
//|     InpTrailRR != InpTP1_RR, one report settles it.                                                    |
//|   - Whether the real EA re-asserts the level after a restart, or sets it once and forgets.             |
//|     Unobservable from a Strategy Tester report, which never restarts. The idempotent                   |
//|     re-assert here is this file's own choice for robustness, not a copied behaviour.                   |
//|                                                                    |
//|  NOT VALIDATED BY A REAL BACKTEST - there is no MT5 in the environment this was written in.            |
//|  Everything above is calibrated against the real EA's real observed exit prices and the real           |
//|  M1 bar path, which is the strongest evidence available here, but it is NOT the same thing as          |
//|  a real Strategy Tester run of this reconstruction, and it is not claimed to be. What the next         |
//|  real run needs to check: (a) does the 32:49:58 outlier disappear, (b) do hold times move              |
//|  toward the real distribution (real M1: median 0.68h, mean 0.91h, p95 2.50h, max 5.16h - this          |
//|  reconstruction's job is to reproduce that shape, and v1.10 did not), and (c) what it costs.           |
//|  HONEST EXPECTATION, stated in advance rather than after the fact: this will very likely              |
//|  REDUCE net profit. A static +1.0R floor is weakly tighter than v1.09's ratchet on every              |
//|  path, so it can only cut winners shorter, never longer - the same trade-off v1.08 made and           |
//|  v1.10 had to walk back. The difference, and the reason it is worth making anyway, is that            |
//|  v1.08's 6h cap was a proxy invented to suppress a symptom, whereas this is the real EA's             |
//|  actual measured rule. If the real re-test shows this losing money against v1.10, the honest           |
//|  reading is NOT that the rule is wrong - it is measured, exactly, 20 times over - but that            |
//|  this reconstruction's ENTRIES differ from the real EA's in some way that makes the real              |
//|  EA's own exit rule a poor fit for them, which would be a genuinely new and more useful               |
//|  finding than another exit knob. Do not revert this on a net-profit comparison alone.                  |
//|                                                                    |
//|  WHAT THIS DOES NOT EXPLAIN. The bar-replay above covers only the post-TP2 stage of the 39            |
//|  real trades that got that far. It does NOT independently reproduce the 32.8h outlier -               |
//|  that trade belongs to this reconstruction, not to the real report, so it has no real                 |
//|  counterpart to measure. The argument that the static floor would have closed it is a                 |
//|  mechanical one (the floor is weakly tighter than the ratchet at every price), and it is              |
//|  sound, but it is reasoning, not a measurement of that specific trade. Separately, 5 of the           |
//|  108 real trades skip a partial they should have taken - 1 runs straight to the 2.0R TP with          |
//|  no TP1 partial at all, and 4 take TP1 but then reach the 2.0R TP with no TP2 partial in              |
//|  between - which this file's strictly staged logic cannot produce. Most likely fast bars              |
//|  jumping through a level between ticks; not investigated here, and too few to affect any              |
//|  of the numbers above.                                                                                 |
//|                                                                    |
//|  v1.11 REAL M1 RE-TEST, clean MSG3-only config (Backtest_11): net +17,548.30 (v1.10 was                |
//|  +20,731.20, -15.4%), PF 1.655 (v1.10: 1.804) - the reduction the v1.11 header predicted in            |
//|  advance, not a surprise. CONFIRMED the static lock-in is actually running, not a stale                |
//|  binary still on the ratchet: measured the post-TP2 stop LEVEL directly from each exit                 |
//|  order's own price (not the fill, which carries slippage noise) for every 3-leg trade in               |
//|  this run - median 0.994R, and several trades exit at 1.02-1.36R, which a ratchet cannot               |
//|  ever produce (its stop is mathematically bounded below the peak, which itself never                   |
//|  exceeds 2.0R, so a ratchet stop can never reach 1.0R let alone exceed it). The mechanism               |
//|  fix works as designed.                                                                                 |
//|                                                                    |
//|  BUT A DIFFERENT, ALREADY-KNOWN BUG RESURFACED: the slowest trade in Backtest_11 ran                    |
//|  80:50:08 and alone contributed $7,027.88 - about 40% of the run's entire net profit from               |
//|  one trade. This is NOT a new failure mode - it is the identical weekend-gap interaction               |
//|  first found in v1.07->v1.08 (see that header entry above): entry Thursday 16:12:06, whose              |
//|  48h nominal InpMaxHoldHours deadline lands Saturday 16:12:06 (market closed), so the check             |
//|  cannot fire until the first tick after Monday's reopen. v1.08 closed this gap by tightening            |
//|  InpMaxHoldHours to 6h - but v1.10's real A/B test proved that blanket tightening costs far             |
//|  more in cut-short winners than it saves, and reverted it. Reverting to 48h necessarily                 |
//|  reopened this specific weekend-gap door too; that was a known, accepted side effect of the             |
//|  v1.10 decision, not an oversight, and it has now been observed for real.                               |
//|                                                                    |
//|  v1.12 FIXES THE WEEKEND GAP DIRECTLY instead of re-tightening InpMaxHoldHours a second time             |
//|  (already disproven as the right lever by v1.10's A/B test). Added a narrow guard: any still-           |
//|  open position gets flattened in the last InpWeekendGuardMinutes (default 30) before the                |
//|  symbol's own Friday trading session closes (read via SymbolInfoSessionTrade, not a hardcoded            |
//|  hour, so it follows this broker's actual schedule), rather than being left to sit through the          |
//|  weekend and have its InpMaxHoldHours deadline miss by dozens of hours. This targets only the           |
//|  specific failure mode observed - a position still open minutes before the weekly close - and           |
//|  leaves InpMaxHoldHours=48 completely untouched for every other trade, unlike v1.08's blanket           |
//|  cut which touched all trades under 48h regardless of when in the week they occurred. Given real        |
//|  M1 trades resolve in a median of 0.68h and a max of 5.16h, this guard should essentially never          |
//|  fire on a normal trade - only on a pathological grind exactly like this one.                            |
//|                                                                    |
//|  INFERRED, NOT MEASURED: there is no real data on how the real EA itself handles a trade still           |
//|  open into a weekend, because none of its 108+86 observed real trades ever ran anywhere near             |
//|  long enough to reach one. InpWeekendGuardMinutes=30 is a reasonable defensive buffer, not a             |
//|  calibrated value. NOT VALIDATED BY A REAL BACKTEST - the next real run needs to confirm this            |
//|  outlier is actually gone and check what, if anything, the guard costs (expected: negligible,            |
//|  since it should almost never fire).                                                                     |
//|                                                                    |
//|  v1.13 ADDS A REAL ENTRY FILTER in response to "can we reduce the losses". Re-parsed Backtest_1           |
//|  (v1.12, clean MSG3-only, structural SL, 93 round-trips) and split by outcome. Every single               |
//|  losing trade - 51 of 51 - is a ONE-LEG trade: it never even reached TP1. Since TP1 moves the             |
//|  stop to breakeven (real-confirmed since v1.01, re-confirmed in the v1.11 header), no trade that          |
//|  reaches TP1 can ever finish net-negative. So "smaller losses" cannot come from resizing the              |
//|  stop - the SL and every TP level are all fixed R-multiples of the same risk, so shrinking risk           |
//|  shrinks wins by the identical proportion (confirmed by comparing this run to InpFixedFibSL=true:         |
//|  PF is virtually identical, 1.6536 vs 1.6548, net is just smaller because average risk is smaller         |
//|  - a scale change, not a real edge). The only real lever is not taking the setups that were always        |
//|  going to run straight to the original stop.                                                              |
//|                                                                    |
//|  CONFIRMED: risk size (SL distance) as a % of entry price predicts outcome, and not the way a              |
//|  simple "smaller stop = safer" intuition would suggest - it is a VALLEY, not a slope. Quintiles by         |
//|  risk% on Backtest_1: 44/22/39/67/52% win rate low to high, i.e. both the smallest and largest risk        |
//|  trades do fine and the MIDDLE band is where it loses money. Re-measured independently on the real         |
//|  EA's own 108 real M1 trades (completely separate calculation, same underlying real report used for       |
//|  every prior version): same valley shape, 67/48/38/71/75% win rate by quintile. Tested the ~0.18-0.26%    |
//|  band (real quintiles 2+3 combined, 44 of 108 real trades) against 20,000 random same-size removals       |
//|  from the same 108 trades: the real dead-zone trades' combined net (-2,126.48) sits at the 0.31           |
//|  percentile of that null distribution (mean random-removal net +9,136.55) - about 1 real trial in         |
//|  300 would be this bad by chance. Removing it would take the real EA's own reported net from              |
//|  22,358.79 to 24,485.27 (+9.5%) on 64 of 108 trades. Checked this is not a gold-price-drift artifact:      |
//|  dead-zone trades span the full real entry-price range ($4,021.60-$5,399.50), not one period.              |
//|                                                                    |
//|  NOT ADOPTED: direction bias. Backtest_1 shows sell trades winning far more than buy trades (54.2%         |
//|  vs 29.4%), which looks like an obvious second filter - but the real EA's OWN 108 trades show the          |
//|  same skew (71.56% short vs 52.83% long, from every "Short/Long Trades (won%)" line in every real          |
//|  report used throughout this file). Since the real EA does not filter by direction and still ships         |
//|  with this same asymmetry, it reads as a real feature of this GOLD period's regime (trending market),      |
//|  not a fixable flaw - filtering it here would be fitting this reconstruction to one period's direction     |
//|  rather than reproducing the real EA's actual behaviour, so it was left alone.                             |
//|                                                                    |
//|  THE CHANGE: InpSkipDeadZone (default true) rejects a retracement-zone touch in CheckSessionSetups()       |
//|  when the candidate risk (already computed by StructuralOrFibSL/InpFixedFibSL either way) falls            |
//|  between InpDeadZoneMinPct and InpDeadZoneMaxPct of the entry price. It does not retire the range -        |
//|  entry price still moves bar to bar inside the retracement zone, so a later touch at a different risk%    |
//|  can still fire normally.                                                                                  |
//|                                                                    |
//|  STILL INFERRED: the EXACT 0.18/0.26 boundary is fit from a 108-real-trade sample (quintile edges,         |
//|  not an independently re-validated cut), so treat the DIRECTION and EXISTENCE of the effect as             |
//|  confirmed but the precise edges as approximate, likely to move slightly as more real data comes in.       |
//|  NOT VALIDATED BY A REAL BACKTEST of this reconstruction with the filter live - the next real run          |
//|  needs to check whether it reproduces a similar win-rate/net-profit lift here, not just on the real         |
//|  EA's own trades used to derive it.                                                                        |
//|                                                                    |
//|  v1.14 DEFAULTS InpSkipDeadZone BACK TO FALSE - the real M1 re-test v1.13 asked for came back worse,        |
//|  and the reason is now understood precisely, not just observed. This EA holds exactly ONE position at      |
//|  a time (single g_ticket slot). Diffed the real re-test (Backtest_2, filter on, 87 round-trips) against    |
//|  the clean baseline it was re-run from (Backtest_1, filter off, 93 round-trips) trade by trade: only 3     |
//|  of the 93 baseline trades survive unchanged. 90 differ, and of those 90, only 23 were actually INSIDE     |
//|  the dead zone - the trades the filter was built to block, and they were correctly bad (net -3,190.19,     |
//|  matching the v1.13 analysis exactly). The other 67 vanished purely as a CASCADE side effect: skipping     |
//|  an entry frees the single position slot earlier than it would have been freed otherwise, which changes    |
//|  which LATER setups get a slot at all - a completely different downstream trade sequence, unrelated to     |
//|  whether any of those later setups were themselves in the dead zone. Those 67 cascaded-away trades were    |
//|  worth +20,245.27 - about 6.3x more than the 23 correctly-blocked trades saved - and were replaced by 84   |
//|  different trades worth only +15,781.55. Net effect: -1,275.49 versus baseline on this run, despite the    |
//|  filter doing exactly what it was designed to do on the 23 trades it actually touched directly.            |
//|                                                                    |
//|  WHY THE PERMUTATION TEST DIDN'T CATCH THIS: it validated a STATIC question - "were the real dead-zone     |
//|  trades unusually bad, holding every other real trade fixed" - which is true, p=0.0031, and remains        |
//|  true today. It could not and did not test the DYNAMIC question - "what happens to the rest of the         |
//|  sequence if these entries are actually blocked live" - because that requires the single-position          |
//|  cascade, which only a real sequential re-test can expose. This is a genuine blind spot in trade-level     |
//|  permutation validation for a single-position system, not a flaw in the permutation test itself for the    |
//|  narrower question it was built to answer.                                                                 |
//|                                                                    |
//|  NOT DELETED: the underlying dead-zone finding on the real EA's own 108 trades is still real and still     |
//|  unexplained by anything else measured so far - only the STATIC framing of "just skip these entries live"  |
//|  is disproven as a net-positive change on this run. InpSkipDeadZone is left in, defaulted OFF, as an        |
//|  opt-in for further experimentation (e.g. it may behave differently on M5, where trades are less dense     |
//|  and cascade collisions rarer, or if the EA ever supported more than one concurrent position) rather than  |
//|  deleted outright - same "walk back the conclusion, keep the honestly-documented attempt" precedent as     |
//|  v1.08's max-hold tightening.                                                                              |
//+------------------------------------------------------------------+
#property copyright "MSG_Trader_EA (reconstruction)"
#property version   "1.14"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- session indices, used throughout as array index 0..3
#define SES_MSG1 0
#define SES_MSG2 1
#define SES_MSG3 2
#define SES_MSG4 3

input group "==== Risk & execution ==="
input double InpLots              = 0.03;
input ulong  InpMagic             = 770025;
input int    InpSlippagePoints    = 20;
input bool   InpFixedFibSL        = false;    // false (as tested): structural swing stop, not a fixed fib %
input double InpFibSLPct          = 78.6;     // only used when InpFixedFibSL=true

input group "==== 3-stage partial TP ==="
input bool   InpScaleOut          = true;
input double InpTP1_RR            = 1.0;
input double InpTP2_RR            = 1.5;
input double InpTP3_RR            = 2.0;      // CONFIRMED: real broker TP order is always entry +/- 2.0x risk
input double InpTrailRR           = 1.0;      // VALUE unchanged and now independently CONFIRMED by measurement:
                                               // all 20 real M1 three-leg trades that closed on a stop after TP2
                                               // closed at EXACTLY entry +/- 1.000R (stdev 0.000000). v1.11 keeps
                                               // the 1.0 but changes what it MEANS: "Trail lock-in (R) after 2nd
                                               // target" is a STATIC lock-in LEVEL measured from entry, not
                                               // v1.09's trailing DISTANCE behind the running price. See header.

input group "==== Exit ==="
input int    InpTPMode            = 0;        // 0 = 3-stage scale-out (InpScaleOut/TP1-3), else = single TP at InpTP_RR
input double InpTP_RR             = 1.5;
input int    InpMaxHoldHours      = 48;       // v1.10: REVERTED from v1.08's 6 - see header. Real A/B test on
                                               // identical M1 configs proved 48 beats 6 (net +20,731 vs +14,805,
                                               // PF 1.80 vs 1.56). Matches the real EA's own actual shipped value.
input int    InpWeekendGuardMinutes = 30;     // v1.12: INFERRED, not measured - see header. Flattens any still-
                                               // open position this many minutes before the symbol's Friday
                                               // close, so a slow grind can't sit through the weekend gap and
                                               // miss its InpMaxHoldHours deadline by dozens of hours. 0 disables.

input group "==== Sessions (GMT) ==="
input bool   InpMsg1Enable        = true;
input int    InpMsg1StartHour     = 22;
input int    InpMsg1EndHour       = 0;
input bool   InpMsg2Enable        = false;
input int    InpMsg2StartHour     = 0;
input int    InpMsg2EndHour       = 8;
input bool   InpMsg3Enable        = true;
input int    InpMsg3StartHour     = 9;
input int    InpMsg3EndHour       = 12;
input bool   InpMsg4Enable        = false;
input int    InpMsg4StartHour     = 17;
input int    InpMsg4EndHour       = 21;

input group "==== Broker clock (GMT) ==="
input bool   InpAutoGMTOffset     = true;
input int    InpGMTOffset         = 0;        // manual hours, used only when InpAutoGMTOffset=false

input group "==== Chart drawings ==="
input bool   InpDrawRange         = true;
input bool   InpDrawFib           = true;
input bool   InpDrawLevels        = true;
input bool   InpDrawHistory       = true;
input int    InpZoneLineWidth     = 2;
input int    InpHistoryDays       = 30;

input group "==== Reconstruction-specific (not in the original report) ==="
input double InpZoneTopPct        = 50.0;     // v1.07 M1 real-data fix - see header. M5 value was 61.8 (standard
                                               // OTE) - set THIS BACK TO 61.8 IF RUNNING ON M5.
input double InpZoneBotPct        = 78.6;     // unchanged between M1/M5 - both real-calibrated to the same value
input double InpRangeRiskPct       = 30.8;    // real-confirmed IDENTICAL on M1 and M5 (30.63% vs 30.8% median) -
                                               // see v1.07 header note. No period-specific override needed.
input double InpMinExtensionPct    = 10.0;    // v1.07 M1 real-data fix - see header. M5 value was 15.0 - SET THIS
                                               // BACK TO 15.0 IF RUNNING ON M5.
input bool   InpSkipDeadZone      = false;    // v1.14: DEFAULTED OFF - v1.13's real M1 re-test showed a cascade
                                               // side effect costs more than the filter saves. See header. Left
                                               // in as opt-in - the underlying dead-zone finding is still real.
input double InpDeadZoneMinPct    = 0.18;     // % of entry price. Boundary fit from real data - approximate, see header.
input double InpDeadZoneMaxPct    = 0.26;     // % of entry price. Boundary fit from real data - approximate, see header.
input int    InpATRPeriod         = 14;
input double InpMaxSpreadPoints   = 60;
input bool   InpOneTradeAfterLoss = false;    // v1.01 real-data circuit breaker - see header, opt-in (p=0.11-0.12)
input double InpMaxSetupWatchHours = 4.25;    // real-confirmed compatible with BOTH M1 and M5 - real M1 entries
                                               // topped out at 3.95h, real M5 entries at 4.08h, same window covers
                                               // both. No period-specific override needed.

input group "==== Notifications ==="
input bool   InpPushNotifications = true;

input group "==== Dashboard ==="
input bool    InpShowPanel   = true;
input int     InpPanelDrag   = 1;
input int     InpPanelX      = 12;
input int     InpPanelY      = 30;
input bool    InpPanelBottom = false;
input int     InpPanelW      = 260;
input color   InpPanelBg     = C'13,17,28';
input color   InpHeaderBg    = C'28,36,58';
input color   InpPanelEdge   = C'255,196,84';
input color   InpTitleCol    = C'255,196,84';
input color   InpSectionCol  = C'214,226,238';
input color   InpTextCol     = C'150,166,192';
input color   InpValCol      = C'236,242,252';
input color   InpOkCol       = C'0,230,118';
input color   InpNoCol       = C'255,61,90';
input color   InpShadowCol   = C'6,8,14';
input string  InpPanelFont   = "Consolas";
input int     InpPanelSize   = 8;
input string  InpBackgroundBMP = "";
input int     InpBgWidth       = 1290;
input int     InpBgHeight      = 720;

input group "==== Chart theme ==="
input bool    InpApplyTheme      = true;
input bool    InpHideTradeMarks  = true;
input color   InpColMsg1         = C'0,230,118';   // range/fib colour per session - neon green
input color   InpColMsg2         = C'0,255,255';   // neon aqua
input color   InpColMsg3         = C'255,196,84';  // gold
input color   InpColMsg4         = C'255,61,90';   // hot red
input color   InpColEntryLine    = C'150,166,192';
input color   InpColStopLine     = C'255,61,90';
input color   InpColTPLine       = C'0,230,118';
input color   InpChartBg   = clrBlack;
input color   InpBullCol   = C'0,150,255';
input color   InpBearCol   = clrWhite;
input string  InpWatermark  = "MSG";
input color   InpWaterCol   = C'46,38,24';
input bool    InpWaterBottom = true;
input int     InpWaterSize  = 42;
input string  InpWaterFont  = "Arial Black";

//--- restart-safe position state (Vanguard/Aurelius pattern)
ulong    g_ticket  = 0;
int      g_posDir  = 0;
datetime g_lastBarTime = 0;
bool     g_skipCosmeticDraws = false;

//--- manual Wilder ATR - used only for the structural-stop buffer and panel display
double   g_atrBuf[];

//--- per-session state (index by SES_MSG1..SES_MSG4)
bool     g_sesEnable[4];
int      g_sesStart[4];
int      g_sesEnd[4];
string   g_sesTag[4] = {"MSG_MSG1", "MSG_MSG2", "MSG_MSG3", "MSG_MSG4"};
color    g_sesCol[4];
bool     g_sesWasIn[4];
double   g_sesFormHigh[4], g_sesFormLow[4];         // range being formed right now
double   g_sesRangeHigh[4], g_sesRangeLow[4];       // last finalized range
bool     g_sesRangeValid[4];
datetime g_sesRangeStartTime[4], g_sesRangeEndTime[4];
int      g_sesBiasDir[4];                            // 0 none, +1/-1 breakout seen, awaiting retracement
double   g_sesExtHigh[4], g_sesExtLow[4];
datetime g_sesExtTime[4];
//--- v1.02 bugfix (see header): true once a trade has already been
//--- taken from the CURRENT frozen range - without this, a still-valid
//--- range stays re-armable for ~21h (until its session reopens), so
//--- ordinary chop around the range boundary re-triggers entry after
//--- entry all day (confirmed against a real MT5 run: 4.9 entries/day
//--- average, one day hit 14, vs the real EA's report which never
//--- shows more than 2/day).
bool     g_sesRangeTraded[4];

//--- current position's own scale-out state (only one position at a time)
double   g_posEntry = 0.0, g_posRisk = 0.0;
double   g_posTP1 = 0.0, g_posTP2 = 0.0, g_posTP3 = 0.0;
bool     g_posTP1Done = false, g_posTP2Done = false;
string   g_posTag = "";
datetime g_posOpenTime = 0;

//--- visuals object prefixes
string   g_pp = "MSGP_";   // panel
string   g_pw = "MSGW_";   // wallpaper + watermark
string   g_pz = "MSGZ_";   // session range boxes / fib zone lines (current + history)
string   g_pl = "MSGL_";   // entry/stop/TP level lines
int      g_panX = -1, g_panY = -1;
bool     g_bgOK = false;
int      g_bgTries = 0;
int      g_panelMinW = 0;
bool     g_panelReclaim = true;

void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim = true);
void PTheme();
void PBackground();
void PWatermark();
void UpdateLevelLines();
void UpdateRangeDrawings();

//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, _Period, 0);
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
      if(g_ticket != 0) { g_posTP1Done = false; g_posTP2Done = false; }
      g_ticket = 0;
      g_posDir = 0;
     }
  }
//+------------------------------------------------------------------+
void ComputeWilderATR(double &out[], int period)
  {
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, _Period, 1, MathMax(period * 3, 200), r);
   if(got < period + 2) { ArrayResize(out, 1); out[0] = 0.0; return; }
   ArraySetAsSeries(out, true);
   ArrayResize(out, got);
   double tr[];
   ArrayResize(tr, got);
   for(int i = 0; i < got - 1; i++)
     {
      double hi = r[i].high, lo = r[i].low, pc = r[i + 1].close;
      tr[i] = MathMax(hi - lo, MathMax(MathAbs(hi - pc), MathAbs(lo - pc)));
     }
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
//| Best-effort broker GMT offset (INFERRED - see header). Falls back  |
//| to the manual input when auto-detect is off. TimeGMT() reflects    |
//| the terminal's own OS timezone, not the broker's - a real,          |
//| disclosed limitation, same honesty standard as this project's       |
//| other "known gaps".                                                 |
//+------------------------------------------------------------------+
int BrokerGMTOffsetHours()
  {
   if(!InpAutoGMTOffset) return(InpGMTOffset);
   int diffSec = (int)(TimeTradeServer() - TimeGMT());
   return (int)MathRound(diffSec / 3600.0);
  }
//+------------------------------------------------------------------+
int HourGMT(datetime serverTime)
  {
   MqlDateTime dt;
   TimeToStruct(serverTime, dt);
   int h = dt.hour - BrokerGMTOffsetHours();
   h = ((h % 24) + 24) % 24;
   return(h);
  }
//+------------------------------------------------------------------+
bool HourInWindow(int hour, int startH, int endH)
  {
   if(startH == endH) return(false);
   if(startH < endH) return(hour >= startH && hour < endH);
   return(hour >= startH || hour < endH);   // wraps midnight, e.g. 22..0
  }
//+------------------------------------------------------------------+
//| v1.12: minutes remaining until the symbol's own Friday trading    |
//| session closes, or -1 if it's not Friday or the session can't be  |
//| read. Uses SymbolInfoSessionTrade (the broker's actual schedule)  |
//| rather than a hardcoded close hour - both it and TimeCurrent()    |
//| are in server time, so no GMT conversion is needed here.          |
//+------------------------------------------------------------------+
int MinutesToFridayClose()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.day_of_week != FRIDAY) return(-1);
   datetime from, to;
   if(!SymbolInfoSessionTrade(_Symbol, FRIDAY, 0, from, to)) return(-1);
   MqlDateTime todt;
   TimeToStruct(to, todt);
   int closeSec = todt.hour * 3600 + todt.min * 60 + todt.sec;
   int nowSec   = dt.hour * 3600 + dt.min * 60 + dt.sec;
   int diffSec  = closeSec - nowSec;
   if(diffSec < 0) return(-1);   // already past this session - not the pre-close window
   return(diffSec / 60);
  }
//+------------------------------------------------------------------+
void LoadSessionConfig()
  {
   g_sesEnable[SES_MSG1] = InpMsg1Enable; g_sesStart[SES_MSG1] = InpMsg1StartHour; g_sesEnd[SES_MSG1] = InpMsg1EndHour; g_sesCol[SES_MSG1] = InpColMsg1;
   g_sesEnable[SES_MSG2] = InpMsg2Enable; g_sesStart[SES_MSG2] = InpMsg2StartHour; g_sesEnd[SES_MSG2] = InpMsg2EndHour; g_sesCol[SES_MSG2] = InpColMsg2;
   g_sesEnable[SES_MSG3] = InpMsg3Enable; g_sesStart[SES_MSG3] = InpMsg3StartHour; g_sesEnd[SES_MSG3] = InpMsg3EndHour; g_sesCol[SES_MSG3] = InpColMsg3;
   g_sesEnable[SES_MSG4] = InpMsg4Enable; g_sesStart[SES_MSG4] = InpMsg4StartHour; g_sesEnd[SES_MSG4] = InpMsg4EndHour; g_sesCol[SES_MSG4] = InpColMsg4;
  }
//+------------------------------------------------------------------+
//| Called once per new bar with the bar that just closed (shift=1).   |
//| Grows/freezes each enabled session's range, and resets the         |
//| breakout/retracement watch the moment a session re-opens.          |
//+------------------------------------------------------------------+
void UpdateSessionRanges(datetime barTime, double barHigh, double barLow)
  {
   int hourGMT = HourGMT(barTime);
   for(int i = 0; i < 4; i++)
     {
      if(!g_sesEnable[i]) continue;
      bool inWin = HourInWindow(hourGMT, g_sesStart[i], g_sesEnd[i]);
      if(inWin)
        {
         if(!g_sesWasIn[i]) { g_sesFormHigh[i] = barHigh; g_sesFormLow[i] = barLow; g_sesRangeStartTime[i] = barTime; }
         else { g_sesFormHigh[i] = MathMax(g_sesFormHigh[i], barHigh); g_sesFormLow[i] = MathMin(g_sesFormLow[i], barLow); }
        }
      else if(g_sesWasIn[i])
        {
         //--- window just closed: freeze the range, and start a fresh
         //--- breakout/retracement watch against it
         g_sesRangeHigh[i]  = g_sesFormHigh[i];
         g_sesRangeLow[i]   = g_sesFormLow[i];
         g_sesRangeValid[i] = (g_sesRangeHigh[i] > g_sesRangeLow[i]);
         g_sesRangeEndTime[i] = barTime;
         g_sesBiasDir[i] = 0;
         g_sesExtHigh[i] = 0.0; g_sesExtLow[i] = 0.0;
         g_sesRangeTraded[i] = false;
        }
      g_sesWasIn[i] = inWin;
     }
  }
//+------------------------------------------------------------------+
//| v1.13 real-data fix (see header): CONFIRMED on the real EA's own    |
//| 108 real M1 trades (permutation p=0.0031) that risk-as-%-of-price   |
//| between InpDeadZoneMinPct and InpDeadZoneMaxPct is a "dead zone" -  |
//| win rate collapses there (43.2% real, vs 60-75% outside it) even    |
//| though it sits in the MIDDLE of the risk-size range, not at either  |
//| extreme. Boundary is fit from a 108-trade sample, so treat the      |
//| EXISTENCE of the effect as confirmed but the exact edges as         |
//| approximate - see header for the full analysis.                     |
//+------------------------------------------------------------------+
bool InRiskDeadZone(double entryPx, double slPx)
  {
   if(!InpSkipDeadZone) return(false);
   double riskPct = MathAbs(entryPx - slPx) / entryPx * 100.0;
   return(riskPct >= InpDeadZoneMinPct && riskPct <= InpDeadZoneMaxPct);
  }
//+------------------------------------------------------------------+
//| INFERRED entry trigger (see header): after a session's range       |
//| breaks in one direction, wait for a retracement back into the      |
//| InpZoneTopPct/InpZoneBotPct fib zone of the (extension extreme ->  |
//| range's opposite side) swing, then trade CONTINUATION of the       |
//| original breakout direction. Returns 0/+1/-1 and, on a signal,     |
//| fills sesIdx/slPrice with the session that fired and its stop.     |
//+------------------------------------------------------------------+
int CheckSessionSetups(double close1, double high1, double low1, double atr, int &sesIdx, double &slPrice)
  {
   datetime barTime = iTime(_Symbol, _Period, 1);
   for(int i = 0; i < 4; i++)
     {
      if(!g_sesEnable[i] || !g_sesRangeValid[i] || g_sesRangeTraded[i]) continue;
      //--- v1.03 real-data fix (see header): the watch window expires
      //--- InpMaxSetupWatchHours after the range froze - retire it
      //--- rather than leaving it re-armable for the rest of the day.
      if(barTime - g_sesRangeEndTime[i] > (datetime)(InpMaxSetupWatchHours * 3600.0))
        {
         g_sesBiasDir[i] = 0;
         continue;
        }
      double H = g_sesRangeHigh[i], L = g_sesRangeLow[i];
      double rng = H - L;
      if(rng <= 0.0) continue;

      if(g_sesBiasDir[i] == 0)
        {
         if(close1 > H) { g_sesBiasDir[i] = 1; g_sesExtHigh[i] = high1; g_sesExtTime[i] = iTime(_Symbol, _Period, 1); }
         else if(close1 < L) { g_sesBiasDir[i] = -1; g_sesExtLow[i] = low1; g_sesExtTime[i] = iTime(_Symbol, _Period, 1); }
         continue;
        }

      if(g_sesBiasDir[i] == 1)
        {
         g_sesExtHigh[i] = MathMax(g_sesExtHigh[i], high1);
         if(close1 < L) { g_sesBiasDir[i] = 0; continue; }   // fully invalidated, must re-break to try again
         double swing = g_sesExtHigh[i] - L;
         if(swing <= 0.0) continue;
         double zoneTop = g_sesExtHigh[i] - (InpZoneTopPct / 100.0) * swing;
         double zoneBot = g_sesExtHigh[i] - (InpZoneBotPct / 100.0) * swing;
         //--- v1.06 real-data fix (see header): require the breakout to
         //--- have travelled at least InpMinExtensionPct% of the range
         //--- beyond H before a retracement into the zone counts - a
         //--- marginal few-point poke past the range is noise, not a
         //--- real breakout.
         double extPct = (g_sesExtHigh[i] - H) / rng * 100.0;
         if(close1 <= zoneTop && close1 >= zoneBot && extPct >= InpMinExtensionPct)
           {
            double slCand = StructuralOrFibSL(true, i, close1, rng, atr);
            if(InRiskDeadZone(close1, slCand)) continue;
            sesIdx = i;
            slPrice = slCand;
            return(1);
           }
        }
      else //-1
        {
         g_sesExtLow[i] = (g_sesExtLow[i] == 0.0) ? low1 : MathMin(g_sesExtLow[i], low1);
         if(close1 > H) { g_sesBiasDir[i] = 0; continue; }
         double swing = H - g_sesExtLow[i];
         if(swing <= 0.0) continue;
         double zoneBot = g_sesExtLow[i] + (InpZoneTopPct / 100.0) * swing;
         double zoneTop = g_sesExtLow[i] + (InpZoneBotPct / 100.0) * swing;
         double extPct = (L - g_sesExtLow[i]) / rng * 100.0;
         if(close1 >= zoneBot && close1 <= zoneTop && extPct >= InpMinExtensionPct)
           {
            double slCand = StructuralOrFibSL(false, i, close1, rng, atr);
            if(InRiskDeadZone(close1, slCand)) continue;
            sesIdx = i;
            slPrice = slCand;
            return(-1);
           }
        }
     }
   return(0);
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| v1.05 real-data fix (see header): SL is a fixed InpRangeRiskPct%   |
//| level measured from the session range's OWN boundary (L for a buy, |
//| H for a sell) - NOT a distance measured back from the entry price   |
//| (v1.04's approach). Checked directly against the real 8-month       |
//| report: measuring SL-to-entry gave a real but noisier fit (33-54%   |
//| interquartile spread, since entry itself moves around inside the    |
//| 61.8-78.6% OTE zone); measuring SL-to-block-edge instead is a        |
//| visibly tighter fit (26-38% interquartile spread, same 82 real       |
//| trades) - real evidence the stop is a fixed structural level of the |
//| range, independent of exactly where inside the zone the entry       |
//| filled. Median real value: 30.8%.                                   |
//+------------------------------------------------------------------+
double StructuralOrFibSL(bool isBuy, int sesIdx, double entryPx, double rng, double atr)
  {
   double H = g_sesRangeHigh[sesIdx], L = g_sesRangeLow[sesIdx];
   if(InpFixedFibSL)
     {
      double swing = isBuy ? (g_sesExtHigh[sesIdx] - L) : (H - g_sesExtLow[sesIdx]);
      return isBuy ? g_sesExtHigh[sesIdx] - (InpFibSLPct / 100.0) * swing
                   : g_sesExtLow[sesIdx]  + (InpFibSLPct / 100.0) * swing;
     }
   double off = (InpRangeRiskPct / 100.0) * rng;
   double sl = isBuy ? L + off : H - off;
   //--- safety clamp: with a minimal breakout extension AND a deep-zone
   //--- entry (close to 78.6%), a fixed offset from L/H can land on the
   //--- wrong side of entryPx - fall back to a small fixed fraction of
   //--- the range so risk is always positive and on the correct side.
   double minRisk = 0.05 * rng;
   if(isBuy && sl >= entryPx - minRisk) sl = entryPx - minRisk;
   if(!isBuy && sl <= entryPx + minRisk) sl = entryPx + minRisk;
   return sl;
  }
//+------------------------------------------------------------------+
double LotStep(double lots)
  {
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0.0) lots = MathRound(lots / step) * step;
   if(lots < mn) lots = 0.0;
   return(lots);
  }
//+------------------------------------------------------------------+
void NotifyPush(const string text)
  {
   if(!InpPushNotifications) return;
   SendNotification(StringSubstr(text, 0, 255));
  }
//+------------------------------------------------------------------+
//| v1.01 circuit breaker (see header) - true once THIS EA (own symbol |
//| + magic) has closed at least one losing deal since today's start,  |
//| server-time calendar day.                                          |
//+------------------------------------------------------------------+
bool LossAlreadyToday()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);
   if(!HistorySelect(dayStart, TimeCurrent())) return(false);
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagic) continue;
      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY) continue;
      if(HistoryDealGetDouble(ticket, DEAL_PROFIT) < 0.0) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
void CheckForEntry()
  {
   SyncPositionState();
   if(g_ticket != 0) return;
   if(InpOneTradeAfterLoss && LossAlreadyToday()) return;

   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadPts > InpMaxSpreadPoints) return;

   double atr;
   if(!GetATR(atr)) atr = 0.0;

   double close1 = iClose(_Symbol, _Period, 1);
   double high1  = iHigh(_Symbol, _Period, 1);
   double low1   = iLow(_Symbol, _Period, 1);

   int sesIdx = -1; double slPrice = 0.0;
   int dir = CheckSessionSetups(close1, high1, low1, atr, sesIdx, slPrice);
   if(dir == 0) return;

   bool isBuy = (dir > 0);
   double px = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double risk = isBuy ? (px - slPrice) : (slPrice - px);
   if(risk <= 0.0) return;

   double tp3 = isBuy ? px + InpTP3_RR * risk : px - InpTP3_RR * risk;
   double tpFinal = (InpTPMode == 0) ? tp3 : (isBuy ? px + InpTP_RR * risk : px - InpTP_RR * risk);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   bool ok = isBuy ? trade.Buy(InpLots, _Symbol, px, slPrice, tpFinal, g_sesTag[sesIdx])
                    : trade.Sell(InpLots, _Symbol, px, slPrice, tpFinal, g_sesTag[sesIdx]);
   if(ok)
     {
      SyncPositionState();
      g_posEntry = px; g_posRisk = risk; g_posTag = g_sesTag[sesIdx];
      g_posOpenTime = TimeCurrent();
      g_posTP1 = isBuy ? px + InpTP1_RR * risk : px - InpTP1_RR * risk;
      g_posTP2 = isBuy ? px + InpTP2_RR * risk : px - InpTP2_RR * risk;
      g_posTP3 = tp3;
      g_posTP1Done = false; g_posTP2Done = false;
      //--- v1.02: this range is now spent - no further entries from it
      //--- until its session window reopens and freezes a brand new one
      //--- (see g_sesRangeTraded's own header note)
      g_sesBiasDir[sesIdx] = 0;
      g_sesRangeTraded[sesIdx] = true;
     }
   else
      PrintFormat("MSG EA: entry FAILED, retcode %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
void ClosePartial(double vol, const string reason)
  {
   vol = LotStep(vol);
   double curVol = PositionGetDouble(POSITION_VOLUME);
   double minVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(vol <= 0.0 || curVol - vol < minVol - 1e-8)
      return;   // remainder would be sub-minimum - skip, let it ride to the next stage
   if(!trade.PositionClosePartial(g_ticket, vol))
      PrintFormat("MSG EA: partial close (%s) FAILED for ticket %I64u, retcode %d",
                  reason, g_ticket, trade.ResultRetcode());
  }
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   SyncPositionState();
   if(g_ticket == 0) return;
   if(!PositionSelectByTicket(g_ticket)) return;

   //--- max hold - v1.10 reverted to 48h (v1.08's tighter 6/12h split disproven by real A/B test, see header)
   int barsHeld = (int)((TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME)));
   if(InpMaxHoldHours > 0 && barsHeld >= InpMaxHoldHours * 3600)
     {
      trade.PositionClose(g_ticket);
      return;
     }

   //--- v1.12 weekend-gap guard (INFERRED - see header): flatten a still-open position
   //--- shortly before the weekly close instead of letting it sit through the weekend
   //--- gap, where InpMaxHoldHours's nominal deadline can miss by dozens of hours (the
   //--- exact 80.8h failure mode in the header). Only bites in the closing minutes of
   //--- Friday, so it does not touch the InpMaxHoldHours=48 calibration itself.
   if(InpWeekendGuardMinutes > 0)
     {
      int minsToClose = MinutesToFridayClose();
      if(minsToClose >= 0 && minsToClose <= InpWeekendGuardMinutes)
        {
         trade.PositionClose(g_ticket);
         return;
        }
     }

   if(!InpScaleOut || InpTPMode != 0 || g_posRisk <= 0.0) return;

   double price = (g_posDir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double vol = PositionGetDouble(POSITION_VOLUME);

   bool hitTP1 = (g_posDir > 0) ? (price >= g_posTP1) : (price <= g_posTP1);
   bool hitTP2 = (g_posDir > 0) ? (price >= g_posTP2) : (price <= g_posTP2);

   //--- v1.09 real-data fix (see header): the real EA's own UI labels -
   //--- "1st target (R) - then stop to break-even" and "2nd target (R) -
   //--- then trail stop" / "Trail lock-in (R) after 2nd target" - describe
   //--- a TWO-STAGE mechanism this file never had: a one-time move to
   //--- breakeven at TP1, then a second stop move at TP2 that locks in
   //--- InpTrailRR x risk of profit. v1.09 read that second stage as a
   //--- continuous ratchet behind the running price; v1.11 re-measured it
   //--- and found it is a STATIC level at entry +/- InpTrailRR x risk that
   //--- never moves again (see the v1.11 block below and the file header).
   //--- v1.01-v1.08 only ever did the breakeven half, once, and
   //--- then left the remaining position with a static stop all the way
   //--- to TP3 or the max-hold timer - very likely the real cause of the
   //--- real EA's own short observed hold times (a trailing stop exits on
   //--- its own as soon as price pulls back, it doesn't need a timer).
   if(!g_posTP1Done && hitTP1)
     {
      ClosePartial(vol / 3.0, "TP1");
      g_posTP1Done = true;
      if(PositionSelectByTicket(g_ticket))
         trade.PositionModify(g_ticket, g_posEntry, PositionGetDouble(POSITION_TP));
     }
   if(g_posTP1Done && !g_posTP2Done && hitTP2)
     {
      if(PositionSelectByTicket(g_ticket))
         ClosePartial(PositionGetDouble(POSITION_VOLUME) / 2.0, "TP2");
      g_posTP2Done = true;
     }

   //--- v1.11 real-data fix (see header): the post-TP2 stop is a STATIC
   //--- LOCK-IN LEVEL at entry +/- InpTrailRR x risk, NOT v1.09's ratchet
   //--- that followed the running price at a fixed distance behind it.
   //--- CONFIRMED from the real M1 report: all 20 real three-leg trades
   //--- whose final leg closed on a stop closed at EXACTLY entry +/- 1.000R
   //--- (stdev 0.000000 across risks of 6.64-29.13 points), while their
   //--- post-TP2 peaks ranged 1.127R-1.954R - a peak-minus-1.0R ratchet
   //--- would have exited those same trades anywhere from 0.127R to 0.954R.
   //--- Zero of 20 match the ratchet; 20 of 20 match a static level.
   //--- The level never moves again once set: the trade whose price peaked
   //--- at 1.954R after TP2 still exited at exactly 1.000R.
   if(g_posTP2Done)
     {
      double lockPx = (g_posDir > 0) ? g_posEntry + InpTrailRR * g_posRisk
                                     : g_posEntry - InpTrailRR * g_posRisk;
      double tol    = _Point * 0.5;
      double curSL  = PositionGetDouble(POSITION_SL);
      //--- idempotent, and deliberately one-directional: this re-asserts the
      //--- level if it is not in place yet (first tick after TP2, or a stop
      //--- left behind by a failed PositionModify / an EA restart), but it
      //--- never walks the stop past lockPx the way v1.09's ratchet did.
      bool needMove = (curSL <= 0.0) ||
                      ((g_posDir > 0) ? (curSL < lockPx - tol) : (curSL > lockPx + tol));
      if(needMove && PositionSelectByTicket(g_ticket))
         trade.PositionModify(g_ticket, lockPx, PositionGetDouble(POSITION_TP));
     }
  }
//+------------------------------------------------------------------+
//| VISUALS - panel primitives reused verbatim from Vanguard_EA.mq5    |
//| (this project's established, bug-fixed implementation).             |
//+------------------------------------------------------------------+
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
//+------------------------------------------------------------------+
void PRect(const string id, const int x, const int y, const int w, const int h,
           const color bg, const color edge, const int border = 1)
  {
   string nm = g_pp + id;
   bool grab = (InpPanelDrag == 1 && id == "bg");
   bool exists = (ObjectFind(0, nm) >= 0);
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
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, grab);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, !grab);
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5000);
  }
//+------------------------------------------------------------------+
void PFrame(const string id, const int x, const int y, const int w, const int h,
            const color edge, const int thick = 2)
  {
   PRect(id + "ft", x,             y,             w,     thick, edge, edge, 0);
   PRect(id + "fb", x,             y + h - thick, w,     thick, edge, edge, 0);
   PRect(id + "fl", x,             y,             thick, h,     edge, edge, 0);
   PRect(id + "fr", x + w - thick, y,             thick, h,     edge, edge, 0);
  }
//+------------------------------------------------------------------+
void PText(const string id, const int x, const int y, const string txt,
           const color col, const int size = 0, const bool rightAlign = false,
           const string font = "")
  {
   string nm = g_pp + id;
   if(txt == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   bool exists = (ObjectFind(0, nm) >= 0);
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
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5001);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
                    rightAlign ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
  }
//+------------------------------------------------------------------+
void PRow(const string id, const int x, const int y, const int w,
          const string label, const string value, const int state)
  {
   if(label == "" && value == "")
     {
      PText(id + "d", x, y, "", InpTextCol);
      PText(id + "l", x, y, "", InpTextCol);
      PText(id + "v", x, y, "", InpTextCol);
      return;
     }
   color dot = (state == 1) ? InpOkCol : (state == 0) ? InpNoCol : InpTextCol;
   PText(id + "d", x + 10, y, CharToString(108), dot, InpPanelSize + 1,
         false, "Wingdings");
   PText(id + "l", x + 26, y, label, InpTextCol);
   PText(id + "v", x + w - 12, y, value, InpValCol, 0, true);
   int need = 26 + EstimateTextWidth(label, InpPanelSize) + 16
              + EstimateTextWidth(value, InpPanelSize) + 20;
   if(need > g_panelMinW) g_panelMinW = need;
  }
//+------------------------------------------------------------------+
void PSection(const string id, const int x, const int y, const int w,
              const int rh, const string title)
  {
   PRect(id + "bar", x + 1, y - 3, w - 2, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x + 10, y, title, InpSectionCol, InpPanelSize, false, "Arial Bold");
  }
//+------------------------------------------------------------------+
void PBackground()
  {
   string nm = g_pw + "bmp";
   if(InpBackgroundBMP == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); g_bgOK = true; return; }
   if(g_bgOK) return;
   if(g_bgTries > 40) return;

   g_bgTries++;
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   if(!ObjectCreate(0, nm, OBJ_BITMAP_LABEL, 0, 0, 0))
     { Print("BG: ObjectCreate failed, error ", GetLastError()); return; }

   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0, nm, OBJPROP_BMPFILE, 0, path);
   int err = GetLastError();

   if(!okSet || err != 0)
     {
      if(g_bgTries <= 3)
         PrintFormat("BG try %d: failed to load \"%s\"  set=%s  error=%d"
                     "  -> file must be at <data folder>\\MQL5\\Images\\%s",
                     g_bgTries, path, (okSet ? "true" : "false"), err,
                     InpBackgroundBMP);
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
   if(ObjectFind(0, g_pw + "wm") >= 0) ObjectDelete(0, g_pw + "wm");
   PWatermark();
   PrintFormat("BG: loaded \"%s\" on try %d", path, g_bgTries);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
void PTheme()
  {
   if(!InpApplyTheme) return;
   ChartSetInteger(0, CHART_COLOR_BACKGROUND,  InpChartBg);
   ChartSetInteger(0, CHART_COLOR_FOREGROUND,  C'138,152,178');
   ChartSetInteger(0, CHART_COLOR_GRID,        C'20,26,40');
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
   if(InpHideTradeMarks)
     {
      ChartSetInteger(0, CHART_SHOW_TRADE_LEVELS, false);
      ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, false);
     }
   ChartRedraw(0);
  }
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
void DeleteLevelLine(const string tag)
  {
   string nm = g_pl + tag;
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
  }
//+------------------------------------------------------------------+
void DrawLevelLine(const string tag, const double price, const color col,
                   const ENUM_LINE_STYLE style, const int width)
  {
   if(price <= 0.0) { DeleteLevelLine(tag); return; }
   string nm = g_pl + tag;
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTED, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| Entry/stop/TP1-3 of the OPEN position, as horizontal lines.        |
//+------------------------------------------------------------------+
void UpdateLevelLines()
  {
   if(InpDrawLevels && g_ticket != 0 && PositionSelectByTicket(g_ticket))
     {
      DrawLevelLine("entry", PositionGetDouble(POSITION_PRICE_OPEN), InpColEntryLine, STYLE_SOLID, 1);
      double sl = PositionGetDouble(POSITION_SL);
      if(sl > 0.0) DrawLevelLine("sl", sl, InpColStopLine, STYLE_SOLID, 1); else DeleteLevelLine("sl");
      DrawLevelLine("tp1", g_posTP1Done ? 0.0 : g_posTP1, InpColTPLine, STYLE_DOT, 1);
      DrawLevelLine("tp2", g_posTP2Done ? 0.0 : g_posTP2, InpColTPLine, STYLE_DOT, 1);
      double tp = PositionGetDouble(POSITION_TP);
      if(tp > 0.0) DrawLevelLine("tp3", tp, InpColTPLine, STYLE_SOLID, 1); else DeleteLevelLine("tp3");
     }
   else
     {
      DeleteLevelLine("entry"); DeleteLevelLine("sl");
      DeleteLevelLine("tp1"); DeleteLevelLine("tp2"); DeleteLevelLine("tp3");
     }
  }
//+------------------------------------------------------------------+
//| Session range box + fib zone lines - current range per session,    |
//| plus (InpDrawHistory) a fading trail of past InpHistoryDays worth. |
//+------------------------------------------------------------------+
void DrawSessionBox(const string tag, datetime t1, datetime t2, double hi, double lo, color col, bool emphasis)
  {
   if(!InpDrawRange) { return; }
   string nm = g_pz + tag;
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t1);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, hi);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t2);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, lo);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, emphasis ? InpZoneLineWidth : 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, nm, OBJPROP_FILL, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
void DrawFibLine(const string tag, datetime t1, datetime t2, double price, color col, bool emphasis)
  {
   string nm = g_pz + tag;
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t1);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t2);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, emphasis ? InpZoneLineWidth : 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, emphasis ? STYLE_SOLID : STYLE_DOT);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
void UpdateRangeDrawings()
  {
   datetime now = TimeCurrent();
   datetime histCutoff = now - (datetime)InpHistoryDays * 86400;

   for(int i = 0; i < 4; i++)
     {
      if(!g_sesEnable[i] || !g_sesRangeValid[i]) continue;
      string base = "cur" + IntegerToString(i) + "_";
      datetime t1 = g_sesRangeStartTime[i], t2 = now + PeriodSeconds(_Period) * 20;
      double H = g_sesRangeHigh[i], L = g_sesRangeLow[i], rng = H - L;

      DrawSessionBox(base + "box", t1, g_sesRangeEndTime[i], H, L, g_sesCol[i], true);

      if(InpDrawFib && rng > 0.0)
        {
         double lvl0   = L, lvl236 = L + 0.236 * rng, lvl382 = L + 0.382 * rng, lvl50 = L + 0.5 * rng;
         double lvl618 = L + (100 - InpZoneTopPct) / 100.0 * rng, lvl786 = L + (100 - InpZoneBotPct) / 100.0 * rng, lvl100 = H;
         DrawFibLine(base + "f0",   g_sesRangeEndTime[i], t2, lvl0,   g_sesCol[i], false);
         DrawFibLine(base + "f236", g_sesRangeEndTime[i], t2, lvl236, g_sesCol[i], false);
         DrawFibLine(base + "f382", g_sesRangeEndTime[i], t2, lvl382, g_sesCol[i], false);
         DrawFibLine(base + "f50",  g_sesRangeEndTime[i], t2, lvl50,  g_sesCol[i], false);
         DrawFibLine(base + "f618", g_sesRangeEndTime[i], t2, lvl618, g_sesCol[i], true);   // OTE zone edges
         DrawFibLine(base + "f786", g_sesRangeEndTime[i], t2, lvl786, g_sesCol[i], true);
         DrawFibLine(base + "f100", g_sesRangeEndTime[i], t2, lvl100, g_sesCol[i], false);
        }
      else
        {
         string f[] = {"f0","f236","f382","f50","f618","f786","f100"};
         for(int k = 0; k < ArraySize(f); k++) DeleteZoneObj(base + f[k]);
        }
     }

   if(!InpDrawHistory)
     {
      PurgeZonePrefix("h");
      return;
     }
   //--- purge history objects older than the cutoff (kept simple - full
   //--- multi-day history backfill on attach is out of scope, same
   //--- disclosed live-only limitation as Vanguard's VWAP line)
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, g_pz + "h") != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < histCutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
void DeleteZoneObj(const string tag)
  {
   string nm = g_pz + tag;
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
  }
//+------------------------------------------------------------------+
void PurgeZonePrefix(const string sub)
  {
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, g_pz + sub) == 0) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
//| Archives the range that just finalized into the history trail      |
//| (InpDrawHistory) - called right when UpdateSessionRanges freezes   |
//| a session's window, so it isn't lost once the "cur" box moves on.  |
//+------------------------------------------------------------------+
void ArchiveSessionRange(int i)
  {
   if(!InpDrawHistory) return;
   string tag = "h" + IntegerToString(i) + "_" + IntegerToString((long)g_sesRangeEndTime[i]);
   DrawSessionBox(tag, g_sesRangeStartTime[i], g_sesRangeEndTime[i], g_sesRangeHigh[i], g_sesRangeLow[i], g_sesCol[i], false);
  }
//+------------------------------------------------------------------+
double MyRealizedPLToday()
  {
   double sum = 0.0;
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);
   if(!HistorySelect(dayStart, TimeCurrent())) return(0.0);
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagic) continue;
      sum += HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_SWAP)
             + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
     }
   return(sum);
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
void CurrentPositions(bool &haveLong, bool &haveShort)
  {
   haveLong = false; haveShort = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) haveLong = true;
      else                                                       haveShort = true;
     }
  }
//+------------------------------------------------------------------+
void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim)
  {
   PBackground();
   PWatermark();
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }
   g_panelReclaim = reclaim;

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;
   int rh = InpPanelSize + 11;
   int hdr = rh + 14;
   //--- counted directly against the ty+= sequence below (project
   //--- convention - see Vanguard/Aurelius header notes on this exact
   //--- discipline). In-position: a0(1) + s1(1)+g1-g4(4) + s2(1)+h1-h5(5)
   //--- + s3(1)+p1-p4(4) + s4(1)+q1-q4(4) = 22 rh-rows, 8 gap-boundaries.
   //--- Flat: p-block loses one rh-row (p4 becomes gap-only) = 21 rh-rows,
   //--- 8 gap-boundaries.
   const int ROWS = (haveLong || haveShort) ? 22 : 21, GAPS = 8;
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH  = hdr + 10 + ROWS * rh + GAPS * 6 + 12;
   int guard = 0;
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     {
      rh--; guard++;
      hdr = rh + 14;
      bodyH = hdr + 10 + ROWS * rh + GAPS * 6 + 12;
     }
   if(g_panX < 0)
     {
      g_panX = InpPanelX;
      if(InpPanelBottom)
        {
         int ch2 = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
         g_panY = MathMax(2, ch2 - bodyH - InpPanelY);
        }
      else
         g_panY = InpPanelY;
     }
   int x = g_panX;
   int y = g_panY;

   PRect("sh", x + 4, y + 4, w, bodyH, InpShadowCol, InpShadowCol, 0);
   PRect("bg", x, y, w, bodyH, InpPanelBg, InpPanelBg, 0);
   PRect("fl", x + 2, y + 2, w - 4, bodyH - 4, InpPanelBg, InpPanelBg, 0);
   PFrame("bd", x, y, w, bodyH, InpPanelEdge, 2);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);

   int ty = y + 9;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "MSG TRADER", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   bool algo = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED);
   PRow("a0", x, ty, w, "algo trading", algo ? "ON" : "OFF", algo ? 1 : 0);
   ty += rh + 6;

   //--- sessions ------------------------------------------------------
   int hourGMT = HourGMT(TimeCurrent());
   PSection("s1", x, ty, w, rh, "SESSIONS (GMT)"); ty += rh + 6;
   string names[4] = {"MSG1 22-00", "MSG2 00-08", "MSG3 09-12", "MSG4 17-21"};
   for(int i = 0; i < 4; i++)
     {
      bool inWin = g_sesEnable[i] && HourInWindow(hourGMT, g_sesStart[i], g_sesEnd[i]);
      string val = !g_sesEnable[i] ? "off" : (inWin ? "forming" :
                   (!g_sesRangeValid[i] ? "-" : (g_sesRangeTraded[i] ? "traded" : "watching")));
      PRow("g" + IntegerToString(i + 1), x, ty, w, names[i], val, !g_sesEnable[i] ? -1 : (inWin ? 1 : (g_sesBiasDir[i] != 0 ? 1 : -1)));
      ty += rh;
     }
   ty += 6;

   //--- setup -----------------------------------------------------
   PSection("s2", x, ty, w, rh, "SETUP"); ty += rh + 6;
   int watching = -1; string watchTxt = "none";
   for(int i = 0; i < 4; i++)
      if(g_sesEnable[i] && g_sesBiasDir[i] != 0) { watching = i; watchTxt = g_sesTag[i] + (g_sesBiasDir[i] > 0 ? " bull" : " bear"); break; }
   PRow("h1", x, ty, w, "awaiting retracement", watchTxt, watching >= 0 ? 1 : -1); ty += rh;
   PRow("h2", x, ty, w, "zone", DoubleToString(InpZoneTopPct, 1) + "-" + DoubleToString(InpZoneBotPct, 1) + "%", -1); ty += rh;
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   PRow("h3", x, ty, w, "spread", (string)spr, spr <= InpMaxSpreadPoints ? 1 : 0); ty += rh;
   double atrShow; bool haveATR = GetATR(atrShow);
   PRow("h4", x, ty, w, "ATR(14)", haveATR ? DoubleToString(atrShow, 2) : "-", -1); ty += rh;
   bool lossToday = InpOneTradeAfterLoss && LossAlreadyToday();
   PRow("h5", x, ty, w, "one-trade breaker",
        !InpOneTradeAfterLoss ? "off" : (lossToday ? "BLOCKING" : "armed"),
        !InpOneTradeAfterLoss ? -1 : (lossToday ? 0 : 1)); ty += rh + 6;

   //--- position --------------------------------------------------
   PSection("s3", x, ty, w, rh, "POSITION"); ty += rh + 6;
   if(haveLong || haveShort)
     {
      double opx = 0.0, vol = 0.0, prof = 0.0;
      if(g_ticket != 0 && PositionSelectByTicket(g_ticket))
        {
         opx = PositionGetDouble(POSITION_PRICE_OPEN);
         vol = PositionGetDouble(POSITION_VOLUME);
         prof = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
        }
      PRow("p1", x, ty, w, (haveLong ? "LONG " : "SHORT ") + g_posTag, DoubleToString(opx, _Digits), 1); ty += rh;
      PRow("p2", x, ty, w, "volume", DoubleToString(vol, 2), -1); ty += rh;
      PRow("p3", x, ty, w, "floating P/L", StringFormat("%+.2f", prof), prof >= 0 ? 1 : 0); ty += rh;
      string stage = g_posTP2Done ? "TP2 done" : g_posTP1Done ? "TP1 done" : "open";
      PRow("p4", x, ty, w, "scale-out", stage, -1); ty += rh + 6;
     }
   else
     {
      PRow("p1", x, ty, w, "state", "FLAT", -1); ty += rh;
      PRow("p2", x, ty, w, "next lot size", DoubleToString(InpLots, 2), -1); ty += rh;
      PRow("p3", x, ty, w, "", "", -1); ty += rh;
      PRow("p4", x, ty, w, "", "", -1); ty += 6;
     }

   //--- account ------------------------------------------------------
   PSection("s4", x, ty, w, rh, "ACCOUNT"); ty += rh + 6;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double myDayPL = MyRealizedPLToday() + MyFloatingPL();
   PRow("q1", x, ty, w, "balance", DoubleToString(bal, 2), -1); ty += rh;
   PRow("q2", x, ty, w, "equity", DoubleToString(eq, 2), eq >= bal ? 1 : 0); ty += rh;
   PRow("q3", x, ty, w, "today (mine)", StringFormat("%+.2f", myDayPL), myDayPL >= 0 ? 1 : 0); ty += rh;
   PRow("q4", x, ty, w, "magic", (string)InpMagic, -1); ty += rh;

   static int warned = 0;
   int used = ty + 12 - y;
   if(used > bodyH && warned < 3)
     { warned++; PrintFormat("Panel: content %d px vs frame %d px", used, bodyH); }
  }
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(g_skipCosmeticDraws) return;
   bool hl, hs;
   CurrentPositions(hl, hs);
   UpdateLevelLines();
   DrawPanel(hl, hs, false);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_pp + "bg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      bool hl, hs;
      CurrentPositions(hl, hs);
      DrawPanel(hl, hs, false);
      ChartRedraw(0);
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      static int lastW = -1, lastH = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lastW || nh != lastH)
        {
         lastW = nw; lastH = nh; g_bgOK = false; g_bgTries = 0; PBackground();
         if(InpPanelBottom)
           {
            g_panX = -1;
            bool hl2, hs2;
            CurrentPositions(hl2, hs2);
            DrawPanel(hl2, hs2, false);
           }
        }
     }
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   //--- v1.07: M1 and M5 are the two periods this reconstruction has been
   //--- calibrated against real reports on. Every bar-data call elsewhere in
   //--- the file follows _Period, so the logic itself is period-agnostic -
   //--- but the calibrated constants are not, so anything else is refused
   //--- rather than silently run on uncalibrated settings.
   if(_Period != PERIOD_M1 && _Period != PERIOD_M5)
     {
      PrintFormat("MSG EA: calibrated for M1 and M5 only - attach it to an M1 or M5 chart "
                  "(currently on period %d)", _Period);
      return(INIT_FAILED);
     }
   //--- v1.07: the two inputs that are genuinely period-specific (see
   //--- header) still hold their M1-calibrated default when attached to
   //--- M5 - warn rather than silently mis-trade on the wrong number.
   if(_Period == PERIOD_M5 && MathAbs(InpZoneTopPct - 61.8) > 0.01)
      Print("MSG EA: running on M5 with the M1 default InpZoneTopPct=", DoubleToString(InpZoneTopPct, 1),
            " - the real M5 value is 61.8, set it back for M5.");
   if(_Period == PERIOD_M5 && MathAbs(InpMinExtensionPct - 15.0) > 0.01)
      Print("MSG EA: running on M5 with the M1 default InpMinExtensionPct=", DoubleToString(InpMinExtensionPct, 1),
            " - the real M5 value is 15.0, set it back for M5.");
   PrintFormat("MSG EA: period %s, zone %.1f-%.1f%%, watch %.2fh, range risk %.1f%%, min ext %.1f%%",
               (_Period == PERIOD_M1 ? "M1" : "M5"), InpZoneTopPct, InpZoneBotPct,
               InpMaxSetupWatchHours, InpRangeRiskPct, InpMinExtensionPct);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   LoadSessionConfig();
   ArrayInitialize(g_sesWasIn, false);
   ArrayInitialize(g_sesRangeValid, false);
   ArrayInitialize(g_sesBiasDir, 0);
   ArrayInitialize(g_sesRangeTraded, false);

   SyncPositionState();
   g_lastBarTime = 0;

   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);
   if(!g_skipCosmeticDraws)
     {
      PTheme();
      PBackground();
      UpdateLevelLines();
      bool hl0, hs0;
      CurrentPositions(hl0, hs0);
      if(InpShowPanel) DrawPanel(hl0, hs0);
      EventSetTimer(1);
     }

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pw);
   ObjectsDeleteAll(0, g_pz);
   ObjectsDeleteAll(0, g_pl);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   if(!IsNewBar()) return;

   datetime barTime = iTime(_Symbol, _Period, 1);
   double barHigh = iHigh(_Symbol, _Period, 1);
   double barLow  = iLow(_Symbol, _Period, 1);

   //--- snapshot which sessions are about to freeze, so their range can
   //--- be archived into the history trail right after
   bool willFreeze[4];
   for(int i = 0; i < 4; i++)
      willFreeze[i] = g_sesEnable[i] && g_sesWasIn[i] && !HourInWindow(HourGMT(barTime), g_sesStart[i], g_sesEnd[i]);

   UpdateSessionRanges(barTime, barHigh, barLow);

   for(int i = 0; i < 4; i++)
      if(willFreeze[i]) ArchiveSessionRange(i);

   if(g_ticket != 0)
      ManageOpenPosition();
   if(g_ticket == 0)
      CheckForEntry();

   if(!g_skipCosmeticDraws)
     {
      UpdateRangeDrawings();
      UpdateLevelLines();
      bool hl, hs;
      CurrentPositions(hl, hs);
      if(InpShowPanel) DrawPanel(hl, hs, true);
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

   if(entry == DEAL_ENTRY_IN)
      NotifyPush(StringFormat("MSG %s OPEN %.2f lots @ %.2f", side, vol, price));
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      NotifyPush(StringFormat("MSG %s CLOSE %.2f lots @ %.2f P/L=%.2f", side, vol, price, profit));
     }
  }
//+------------------------------------------------------------------+
