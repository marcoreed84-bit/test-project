//+------------------------------------------------------------------+
//|                                      Fulcrum_M15_EA.mq5             |
//|                                                                     |
//|  v1.00 (2026-09-14) - M15-NATIVE VARIANT of Fulcrum_EA.mq5 v2.13.   |
//|  A SEPARATE FILE, deliberately, following the same pattern this repo |
//|  already uses for Aurelius_EA.mq5 vs Aurelius_M15_EA.mq5: different  |
//|  filename, different magic (750092 vs Fulcrum_EA.mq5's 750091), so   |
//|  the M5 and M15 versions can run SIMULTANEOUSLY on the same account  |
//|  and symbol without their position tracking, cooldown counter,       |
//|  daily-loss accumulator or circuit-breaker state ever mixing. This   |
//|  is NOT a second position slot bolted into the M5 file, and it is    |
//|  NOT a rewrite - everything below this block is Fulcrum_EA.mq5's own |
//|  header/version history, kept verbatim, because the trading logic is |
//|  byte-for-byte the same. Its own version history starts fresh here   |
//|  at v1.00.                                                           |
//|                                                                     |
//|  WHAT ACTUALLY DIFFERS FROM Fulcrum_EA.mq5 v2.13 (the whole list):   |
//|   1. The five alignment-stack MA legs (periods AND methods) - see    |
//|      "M15 LEG-SET" below and the inputs' own comments.               |
//|   2. The MA METHODS are now selectable ENUM_MA_METHOD inputs         |
//|      (InpM21/InpM50/InpM150/InpM600/InpM2400) instead of being       |
//|      hardcoded in the iMA() calls, matching Aurelius_M15_EA.mq5's    |
//|      convention - the M15 leg-set needs a method (SMMA) that the M5  |
//|      file's hardcoding could not express.                            |
//|   3. InpMagic 750091 -> 750092 (and the trade comment / CSV log      |
//|      filename / log-line prefix follow it, so merged deal exports    |
//|      and a shared Experts tab stay readable).                        |
//|   4. OnInit's timeframe warning checks PERIOD_M15, not PERIOD_M5.    |
//|   5. This header.                                                    |
//|  Nothing else. The entry gate's SHAPE, the structural stop, the      |
//|  fixed-$ target, TargetDistance(), InpMinStopATR, risk sizing,       |
//|  InpMaxDailyLossPct, the Friday/holiday/DST session protection, the  |
//|  panel/theme/wallpaper/watermark code and every performance fix are  |
//|  unchanged. Panel and chart-object prefixes (FULP_/FULW_/FULM_/      |
//|  FULL_) are deliberately NOT renamed - the two EAs live on two       |
//|  different charts, so they never share an object namespace, and      |
//|  Aurelius_M15_EA.mq5 keeps its parent's prefixes for the same        |
//|  reason.                                                             |
//|                                                                     |
//|  M15 LEG-SET (the one real change - validated, do not "restore" the  |
//|  M5 numbers): fast 30/EMA, med 50/EMA, mid 150/EMA, slow 200/SMMA,   |
//|  macro 1200/EMA. Fulcrum_EA.mq5's M5 defaults are 21/50/150/600/2400 |
//|  with methods EMA/EMA/EMA/SMA/EMA - THREE of the five periods differ |
//|  (fast 21->30, slow 600->200, macro 2400->1200) and the slow leg's   |
//|  METHOD differs too (SMA->SMMA). These are not rescale guesses: they |
//|  are the same leg-set Aurelius_M15_EA.mq5 actually ships, re-checked |
//|  against Fulcrum's own M15 risk/reward shape by a leg-space sweep    |
//|  with a search-width correction, where they sit at the 96th-98th     |
//|  percentile. Shipping this file with 600/2400 left in place would    |
//|  have run a materially WORSE system on M15 - that specific mistake   |
//|  was flagged as the main risk when this file was built.              |
//|  Note the leg-NAMES (InpP21/InpP600/InpP2400, the "21/50/150/600/    |
//|  2400" object suffixes, and the panel's "150 vs 600" row labels) are |
//|  kept from the M5 file on purpose - they are stable identifiers for  |
//|  "fast/med/mid/slow/macro", not claims about the period held. Same   |
//|  convention as Aurelius_M15_EA.mq5, which also holds 200 in InpP600  |
//|  and 1200 in InpP2400.                                               |
//|                                                                     |
//|  THE MED LEG IS STILL 50, AND IS STILL THE STOP ANCHOR. Unchanged    |
//|  across both timeframes, and that is load-bearing: h50 is read by    |
//|  the alignment check, the slope filter (SlopeATR), the criss-cross   |
//|  filter (CrissCross), the pullback filter (PullbackOK) AND it is the |
//|  structural stop anchor in CheckForEntry() (stop = the med MA's      |
//|  value at entry, offset by InpStopBufferATR x ATR) and the centre of |
//|  the drawn stop-buffer band. Because the med leg's period does not   |
//|  change on M15, that whole relationship carries over untouched.      |
//|                                                                     |
//|  EXIT IS UNCHANGED AND THAT IS DELIBERATE: InpFixedTargetUSD = 45.0, |
//|  InpStopBufferATR = 0.15, exactly as on M5. DO NOT "FIX" THIS from a |
//|  naive M15 target sweep - one was run, it appeared to favour $60-70, |
//|  and that was PROVEN to be an artifact of Friday forced-flat exits:  |
//|  once the Friday-close bucket is isolated the apparent gain          |
//|  disappears and $45 is genuinely the best target on M15 as well as   |
//|  M5. This is the same decomposition lesson as SESSION_NOTES.md item  |
//|  6 and the v2.04 gate-relaxation test in the header below, reached   |
//|  for a third time. InpMinStopATR is kept at its v2.13 default of 0.0 |
//|  (off): it is a real finding, but it was tested on M5 only, so       |
//|  NOTHING here claims it is validated on M15 - treat it as an         |
//|  untested opt-in on this timeframe.                                  |
//|                                                                     |
//|  REAL VALIDATED M15 BASELINE (real MT5 backtest, GOLD# M15, at these |
//|  exact settings, InpLots=0.01, 2023.01.01-2026.09.03):               |
//|     289 trades, win rate 31.14%, profit factor 1.597,                |
//|     recovery factor 8.203, Sharpe 4.397,                             |
//|     Balance drawdown max 10.73%, Equity drawdown max 11.71%,         |
//|     max consecutive losses 14.                                       |
//|  Deliberately quoted as ratios/percentages only: that account was    |
//|  denominated in ZAR, so any absolute cash figure from it would be a  |
//|  currency-specific number, not a USD one, and must not be restated   |
//|  as dollars. Win rate is higher and PF better than the M5 file's own |
//|  numbers, but read it alongside the drawdown: ~10-12% is roughly     |
//|  double what the M5 version runs at, which is the price of M15's     |
//|  wider bars, not a bug.                                              |
//|                                                                     |
//|  WHY THIS FILE EXISTS AT ALL - THE COMBINED-PORTFOLIO FINDING.       |
//|  Running M5 Fulcrum and M15 Fulcrum TOGETHER on one account (matched |
//|  lot size, separate magic numbers - which is exactly what this file  |
//|  makes possible) was measured, from real merged deal data, at        |
//|  +81% net for +5% max balance drawdown and -3% max equity drawdown   |
//|  versus running M5 alone. That result survived a rotation-null       |
//|  control, held on BOTH sides of a blind split, held across all four  |
//|  years, and came with reduced tail concentration. Be precise about   |
//|  what it is: it is NOT new alpha and not a better strategy - it is   |
//|  the ordinary, honest statistical benefit of combining two weakly    |
//|  correlated instances of the same edge (r ~ 0.3 between the two      |
//|  timeframes' returns). That is also its limit: it is a              |
//|  diversification result, so it degrades if the two are ever made     |
//|  more similar (e.g. by "harmonising" the leg-sets).                  |
//|                                                                     |
//|  *** NEEDS A REAL MT5 TEST AT THESE EXACT SETTINGS BEFORE TRUSTING   |
//|  IT. *** The numbers above ARE already real-MT5-validated for M15    |
//|  STANDALONE - this is not a Python-only file - but this is the first |
//|  time they are shipped as a permanent EA file rather than as a       |
//|  research-only backtest, so the file itself has never been run. And  |
//|  the combined-portfolio finding specifically has NEVER been real-MT5 |
//|  tested as a combined run: only each leg separately, with the M5 and |
//|  M15 deal streams merged afterwards. Run both together before        |
//|  relying on the +81%/+5%/-3% figures.                                |
//+------------------------------------------------------------------+
//|  Everything below this line is Fulcrum_EA.mq5's original header,     |
//|  kept verbatim - the trading logic it documents is identical here.   |
//|  Where it says "M5", read "the timeframe this EA was validated on";  |
//|  the M15 specifics are all above.                                    |
//+------------------------------------------------------------------+
//|                                          Fulcrum_EA.mq5             |
//|                                                                  |
//|  A standalone scalp-style system, not a variant of Aurelius: the  |
//|  SAME validated Aurelius entry gate (21>50>150>600 alignment +     |
//|  price vs the 2400, slope filter, criss-cross filter, pullback to |
//|  the 50, volume filter, daily S/R distance filter - ALIGN_MID     |
//|  mode, matching Aurelius's own shipped default) - but a completely|
//|  different exit shape:                                            |
//|                                                                  |
//|   - Stop: just past the 50 EMA's value AT ENTRY (InpStopBufferATR |
//|     beyond it) - a structural stop tied to the specific level     |
//|     that just held, not a volatility multiple of price.           |
//|   - Target: a FIXED dollar amount (InpFixedTargetUSD), not ATR-    |
//|     relative and not open-ended. At 0.01 lots on GOLD#, $1 = 1     |
//|     price unit, so InpFixedTargetUSD is literally a price          |
//|     distance at that lot size - scale it with InpLots if you       |
//|     trade a different size.                                       |
//|                                                                  |
//|  VALIDATED (Python, GOLD# M5, 2023-01 to 2026-08, full alignment   |
//|  gate, stop=0.15 ATR past the 50 EMA):                             |
//|   target=$40   FULL PF 1.46  TRAIN PF 1.45  HOLD PF 1.46           |
//|   target=$45   FULL PF 1.47  TRAIN PF 1.45  HOLD PF 1.49  (best)   |
//|   target=$50   FULL PF 1.43  TRAIN PF 1.43  HOLD PF 1.43           |
//|   target=$55   FULL PF 1.40  TRAIN PF 1.38  HOLD PF 1.42           |
//|  Unusually clean for this whole session's testing - PF sits in the |
//|  same tight 1.4-1.5 band across FULL/TRAIN/HOLD at every setting   |
//|  in the $40-60 plateau, not just at one lucky point. Win rate is   |
//|  LOW by design (~15-28%) - the edge is entirely in the payoff      |
//|  ratio (small structural stop, much larger fixed target), not in   |
//|  winning often. Expect long stretches of small losses between      |
//|  wins; that is the strategy working as intended, not a problem.    |
//|  Average time to target is ~17 hours (206 bars) - a wide-R:R,      |
//|  low-frequency system, NOT a couple-candle scalp, even though the  |
//|  stop itself is tight. Real-tick validated twice (2yr backtest+    |
//|  forward split): PF 1.81 backtest / 1.47 forward.                  |
//|                                                                  |
//|  CONFIRMED: the full alignment stack is load-bearing, not optional |
//|  overhead. Re-tested with just price-vs-50-EMA instead of the full |
//|  stack: PF fell to 1.20 and drawdown grew 1.6x for barely more net.|
//|  Dropping the slope/cross/volume/SR filters too (bounce+trend      |
//|  only): PF ~1.10, drawdown grew 5.5x. Do not simplify this entry   |
//|  gate without re-testing - every filter here earns its place.      |
//|  VWAP-as-entry-filter tested separately for this system and found  |
//|  neutral (not worth adding) - deliberately not included here.      |
//|                                                                  |
//|  v2.00: full production dress-up - wallpaper, watermark, a rich    |
//|  diagnostic panel showing every entry-gate filter's live pass/fail |
//|  state (not just a 6-line summary). All of it is cosmetic and NONE |
//|  of it touches the trading logic above, which is byte-for-byte the |
//|  same gate/stop/target math that was Python- and real-tick-        |
//|  validated.                                                        |
//|                                                                  |
//|  PERFORMANCE: this EA was built applying, from the start, all      |
//|  three fixes that a multi-hour Aurelius backtest bug needed three   |
//|  rounds to find:                                                   |
//|   1. No HistorySelect()/deal-history scan anywhere in a hot path -  |
//|      "today P/L" is a running accumulator (g_myRealizedToday)       |
//|      updated once per closing deal in OnTradeTransaction, O(1).     |
//|   2. Every cosmetic draw (wallpaper, watermark, the full panel) is  |
//|      gated behind g_skipCosmeticDraws, computed once in OnInit as   |
//|      MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE) |
//|      - a non-visual Strategy Tester run draws NONE of it, since     |
//|      nobody can see it and it has zero effect on any trading        |
//|      decision. Still fully live for real trading, demo, and         |
//|      visual-mode backtests, and additionally throttled to once per  |
//|      unique TimeCurrent() second there so it can't redraw twice in  |
//|      the same simulated instant.                                   |
//|   3. NO EventSetTimer() anywhere in this file. That independent      |
//|      timer callback was the actual remaining cause of Aurelius's     |
//|      multi-hour runtime even after fix #2 - Strategy Tester still    |
//|      simulates timer ticks regardless of OnTick throttling. Fulcrum  |
//|      simply never starts one; the panel updates on ticks/bars only.  |
//|  Net effect: a non-visual Tester run should complete at the same     |
//|  speed the trading logic alone would take - the panel/wallpaper/     |
//|  watermark cost approximately nothing there.                        |
//|                                                                  |
//|  v2.01 - a real review, before the InpFixedTargetUSD/InpStopBufferATR |
//|  sweeps this file exists to run, found InpCooldownBars was dead -      |
//|  the exact bug Aurelius_EA.mq5 already documented and fixed (see its   |
//|  own header): g_barsSinceClose was incremented every bar but never     |
//|  reset on a normal SL/TP close (OnTradeTransaction set g_ticket=0       |
//|  without resetting it, and OnTick's stale-ticket cleanup - the only     |
//|  place that DID reset it - never ran because g_ticket was already 0     |
//|  by the time it checked). So the cooldown counter just kept climbing    |
//|  from EA start and the gate was permanently satisfied. Fixed: both       |
//|  OnTradeTransaction and CloseCurrentPosition now reset it directly on    |
//|  close, matching Aurelius's fix. Also added HistoryDealSelect(ticket)     |
//|  before reading deal properties in OnTradeTransaction - it wasn't         |
//|  guaranteed the just-added deal was already in the selected history       |
//|  window, and a failure there would have silently skipped both the         |
//|  realized-P/L accumulator and this same reset. Everything else in this     |
//|  file (entry gate, stop/target math, cosmetic-draw gating) was verified    |
//|  correct against Aurelius's equivalents and is unchanged.                   |
//|                                                                             |
//|  v2.02: same ATR fix as Aurelius_EA.mq5 v1.36, which this file's entry       |
//|  gate is a copy of - iATR() on this broker is a plain SMA(14) of True         |
//|  Range, not Wilder smoothing, despite MT5's own docs. ATR is now computed      |
//|  manually (ComputeWilderATR) once per new bar into g_atrManual, read            |
//|  through GetATR() everywhere MA(hATR,...) was used - affects the entry           |
//|  gate's slope/pullback/S/R filters AND the structural stop distance                |
//|  (stop = the 50 EMA's value at entry, offset by InpStopBufferATR x ATR) -            |
//|  a real behavior change, not just a Python-fidelity fix. Needs a real                 |
//|  Strategy Tester run before trusting it against the header's PF 1.81/1.47               |
//|  real-tick numbers, which predate this fix.                                              |
//|                                                                                            |
//|  v2.03: full visual/professional overhaul, at the user's explicit request - no             |
//|  entry/exit/stop/target logic touched, cosmetic only. The moving averages used               |
//|  by this file's entry gate (21/50/150/600/2400, same alignment gate as Aurelius)              |
//|  are now drawn directly on the chart as their own neon-coloured OBJ_TREND                      |
//|  segments (new inputs InpShowMAs, InpCol21/50/150/600/2400 - yellow/white/purple/                |
//|  pink/green - Fulcrum had no MA-visualization inputs at all before this), one new                 |
//|  segment per bar, bounded to a rolling InpMAHistoryBars window (default 300) and                   |
//|  purged each bar so a long-running live EA doesn't accumulate objects forever - see                 |
//|  DrawMASegment/PurgeOldMALines/UpdateMALines, ported from Aurelius_EA.mq5 v1.37                      |
//|  unchanged. UpdateMALines() is called before DrawPanel() every cosmetic-draw cycle                    |
//|  (MT5 renders chart objects in creation order, not z-order) so the panel stays the                     |
//|  topmost, visually "solid" object. Added InpHideTradeMarks (default true), which turns                  |
//|  off MT5's own native buy/sell/SL/TP arrows and lines via ChartSetInteger                                 |
//|  (CHART_SHOW_TRADE_LEVELS/CHART_SHOW_TRADE_HISTORY, false) - these are a terminal                          |
//|  display setting, not real chart objects, so ObjectDelete can't remove them; this is                        |
//|  the actual way to suppress them. Also found and fixed two real, pre-existing panel                          |
//|  bugs, independent of anything else touched this session: (1) DrawPanel()'s height                            |
//|  formula (hdr+rows*rh+24) undersized the panel's background rectangle by roughly 10px -                        |
//|  the row count itself (24) was correct, but the formula never budgeted for the actual                           |
//|  6px top offset from y to the first row, or the 7 separate 4px inter-section gaps                                |
//|  (28px total) against only a flat +24 - letting rows render partly outside the panel,                             |
//|  exactly the "no overlapping text, all text inside the window" bug the user asked to                               |
//|  have eliminated. Fixed with explicit ROWS=24/GAPS=7 constants and a corrected formula                              |
//|  that accounts for both. (2) Fulcrum had no self-adapting/autofit panel behavior at all                              |
//|  (Aurelius already had this) despite the user's "self adapting to the size of the                                     |
//|  screen" requirement covering both files - added the same shrink-rh-to-an-11px-floor                                  |
//|  loop Aurelius uses, so the panel no longer runs off a short screen. Wallpaper/                                        |
//|  watermark/candle theme/panel solidity were already implemented pre-v2.03 and are                                       |
//|  unchanged by this round.                                                                                                 |
//|                                                                                                                             |
//|  Opus review of the above (before shipping) found the same panel-solidity,                    |
//|  MA-color, MA-backfill and Object-List issues as Aurelius_EA.mq5 v1.37, fixed                   |
//|  identically here: PRect now deletes-and-recreates every cycle (except the                        |
//|  draggable "bg" rect), a new opaque "fl" fill rect keeps the panel body solid,                       |
//|  InpCol50 changed from white (collided with InpBearCol) to neon orange, a new                         |
//|  BackfillMALines() draws the whole rolling MA window on attach instead of a                             |
//|  1-bar stub per line, and DrawMASegment's objects are now OBJPROP_HIDDEN so                               |
//|  they don't flood the Object List. Same review also independently re-derived                               |
//|  this file's own ROWS=24/GAPS=7 panel constants from scratch and confirmed them                              |
//|  correct (see the comment above DrawPanel's ROWS/GAPS declaration for the exact                               |
//|  count).                                                                                                        |
//|                                                                                                                   |
//|  v2.04: same panel-flashing fix as Aurelius_EA.mq5 v1.38, for the same                                            |
//|  reason - v2.03's solidity fix (PRect/PText deleting-and-recreating every                                          |
//|  DrawPanel() call) directly caused the panel to visibly flash/repaint on                                            |
//|  every live-number refresh. Fixed identically: a new g_panelReclaim flag,                                            |
//|  driven by a `reclaim` parameter on DrawPanel() (true only once per new bar,                                          |
//|  right when UpdateMALines() adds the one object that could bury the panel;                                             |
//|  false everywhere else), that PRect/PText check before deleting - false just                                           |
//|  updates properties in place, no visual churn. Opus review also caught: an                                              |
//|  unconditional ChartRedraw() on the between-bar refresh path (this file has                                              |
//|  no OnTimer, so this was the only per-second redraw) - fixed to only redraw                                              |
//|  when a position is open (g_ticket != 0), matching Aurelius's own OnTimer                                                 |
//|  guard; the new `reclaim = true` default was repeated on both the forward                                                 |
//|  declaration and the definition, a hard error in some MQL5/C++-family                                                     |
//|  compilers - moved to the declaration only; and a stale comment directly                                                   |
//|  above PText/PRect still claimed they "delete+recreate every call" -                                                       |
//|  corrected to describe the g_panelReclaim-gated behavior. No trading-logic                                                  |
//|  changes.                                                                                                                    |
//|                                                                                                                                |
//|  Also: at the user's request, tested (Python-only, walk-forward, 4                                                           |
//|  sequential folds) whether relaxing this file's entry gate from all 5 MAs                                                     |
//|  aligned to just 21/50/150 would improve it, Aurelius's own gate left                                                          |
//|  untouched either way. Result, Opus-reviewed: looks like a win headline                                                        |
//|  (+64% more trades, +20% more net) but isn't one - decomposed by exit                                                          |
//|  reason, the entire net gain (and more) comes from trades that get forced                                                      |
//|  closed into Friday, the least-validated fill in the Python replica; on the                                                     |
//|  STOP/TARGET exits this gate actually governs, the looser gate earns LESS                                                       |
//|  (+1137 vs +1206) while taking 62% more trades, and the ranking (5 MAs >                                                         |
//|  fewer) holds cleanly once that bucket is set aside. Not shipped - no gate-                                                      |
//|  mode input was added. See scratchpad/m5/fulcrum_ma_gate_test.py.                                                                 |
//+------------------------------------------------------------------+
//|  v2.05: visual standardization pass across Aurelius_EA.mq5/Fulcrum/       |
//|  Ratchet_EA.mq5, all three sharing one account, so they should read as     |
//|  one product rather than three different panels. (1) PRect's own            |
//|  OBJ_RECTANGLE_LABEL border rendered unreliably - observed live as only       |
//|  two of the four sides actually drawn - replaced with an explicit 4-strip      |
//|  PFrame() outline, immune to the quirk. (2) InpPanelX/InpPanelY were 20/20,      |
//|  the only one of the three off from the shared 12/30 top-left anchor - now        |
//|  matches. (3) InpMAHistoryBars default 300->2500 (300 M5 bars is only ~25h -       |
//|  "a short line, not covering the whole chart" on any normal zoomed-out view;        |
//|  2500 is ~8.7 days). (4) ACCOUNT section was realized-only ("today (mine)" =         |
//|  g_myRealizedToday alone, no floating component, no comparison against the            |
//|  rest of the account) while Aurelius/Ratchet both fold floating P&L in AND             |
//|  show "today (other)" - added the same MyFloatingPL() + g_dayStartEquity               |
//|  tracking + "today (other)" row here, so all three EAs present their own                |
//|  P&L identically when run together. ROWS bumped 24->25 for the new row.                   |
//|  No trading-logic changes.                                                                  |
//+------------------------------------------------------------------+
//|  v2.06: same holiday-session-gap fix as Daybreak_EA.mq5 v1.11-1.12/Zenith_EA.mq5/ |
//|  Aurelius_EA.mq5 v1.40, confirmed live in real Strategy Tester data and found by     |
//|  code inspection to apply identically here: ManageOpenPosition's IsFridayCutoff        |
//|  only ran once per new bar (via ProcessNewBar), so a holiday leaving zero ticks/         |
//|  bars near the Friday cutoff hour meant it never fired at all, and nothing then            |
//|  existed to catch a stale position over the following weekend either. Added                  |
//|  WeekendStillOpen() (deadline-based - true once now is past the most recent Friday             |
//|  InpFridayCloseHour:00 AND the position opened before it, regardless of which day                |
//|  the first tick back lands on), called every tick at the top of OnTick, ahead of the               |
//|  new-bar gate - closes on literally the first tick available after any gap. The old                 |
//|  bar-gated call in ManageOpenPosition removed (now dead weight, always beaten by the                  |
//|  tick-level check). Also added IsMarketHoliday() (New Year's/MLK/Presidents/Good Friday/                |
//|  Memorial/Juneteenth/Independence/Labor/Thanksgiving/Christmas, every date computed from                  |
//|  the year - no hardcoded table, no yearly maintenance) and blocked new entries on a flagged                 |
//|  holiday the same place/way as the existing Friday no-entry rule.                                              |
//+------------------------------------------------------------------+
//|  v2.07: real GOLD# M5 price data (2023-2026) shows this broker's server        |
//|  clock follows EU DST dates while gold's true session timing follows US          |
//|  DST dates - confirmed directly from the daily first-bar-of-day time, which        |
//|  shifts by exactly 60 minutes on the Monday after each transition, twice a           |
//|  year, every year, no exceptions. During the ~2-week March gap and ~1-week             |
//|  Oct/Nov gap this creates, InpFridayCloseHour and InpFridayNoEntryHour read              |
//|  1 server-clock hour off from the true session boundary. Added                            |
//|  DSTGapHourAdjustment() (returns -1 during a gap week, 0 otherwise, computed                |
//|  from the permanent US/EU DST transition rules - no hardcoded dates, no                      |
//|  yearly maintenance, same principle as IsMarketHoliday) and applied it to both                 |
//|  hour thresholds. No core-signal timing in this file depends on a fixed server                  |
//|  hour (unlike Daybreak_EA.mq5's InpSessionHour), so this is risk-management only,                |
//|  same scope as the weekend-gap fix above.                                                          |
//+------------------------------------------------------------------+
//|  v2.08: live/demo bug - panel (and everything else cosmetic) never       |
//|  appeared on attach, unlike Aurelius_EA.mq5/Ratchet_EA.mq5 run on the        |
//|  same account/terminal. Root cause: this file's PERFORMANCE FIX #3            |
//|  deliberately removed EventSetTimer(), and unlike Aurelius (which calls          |
//|  DrawPanel() directly in OnInit) this file never gained a compensating            |
//|  immediate draw - the panel only ever rendered from inside OnTick(), so             |
//|  it depended entirely on the first tick reaching the EA after attach.                |
//|  Added PBackground()+DrawPanel()+ChartRedraw(0) right after the existing              |
//|  OnInit BackfillMALines() call so the panel (and MA line backfill, which               |
//|  was already unconditional there but never got flushed to screen) show                 |
//|  the moment the EA attaches, same as Aurelius. The chart background/candle              |
//|  colour ChartSetInteger calls above are unconditional and tick-independent                |
//|  already and were not touched - if those are still wrong after this fix,                    |
//|  it points to a second, separate cause (most likely OnInit returning                          |
//|  INIT_FAILED before reaching them, e.g. an indicator handle problem) and                        |
//|  the Experts-tab log right after attaching is the next thing to check.                            |
//+------------------------------------------------------------------+
//|  v2.09: pre-live risk-sizing pass. This file only ever supported a fixed        |
//|  InpLots and had no daily-loss circuit breaker at all (Aurelius_EA.mq5/           |
//|  Ratchet_EA.mq5 both have one) - gold's ATR has moved roughly 5-6x since            |
//|  2023 while InpLots never did, so a fixed lot now risks far more per trade           |
//|  in dollar terms than it did when this system was validated. Added the same           |
//|  InpLotMode/InpRiskPct LOT_RISK_PCT option (LOT_FIXED stays the default - no            |
//|  change unless deliberately switched on) and InpMaxDailyLossPct (default 0 =             |
//|  off). Because InpFixedTargetUSD was written as a literal PRICE distance,                  |
//|  true only at exactly 0.01 lots (see the header note on this EA's exit                      |
//|  design), added TargetDistance() so the target keeps meaning an actual                        |
//|  dollar amount at whatever lot size LotSize() actually returns, instead of                      |
//|  silently drifting once lot size stops being fixed at 0.01.                                           |
//|  CORRECTION (2026-09-06, Opus review): the line originally here claimed this        |
//|  "reduces back to the exact original literal-price-distance behaviour" / is         |
//|  "byte-for-byte the same price distance as before" whenever lots==InpLots (i.e.      |
//|  LOT_FIXED). That is FALSE for any InpLots other than exactly 0.01 - TargetDistance()  |
//|  scales the price distance as 1/lots regardless of WHY lots holds that value, so        |
//|  running LOT_FIXED at InpLots=0.03 (as this session's own comparisons did) gives a        |
//|  3x-WIDER target than validated, not the original behaviour. This wrong invariant          |
//|  is exactly what made an InpLots=0.03-vs-0.01 comparison look like a safe apples-to-         |
//|  apples rescale when it was actually comparing two different reward:risk geometries -          |
//|  see the InpLots=0.01 vs 0.03 backtest comparison in SESSION_NOTES.md item 19. The          |
//|  true invariant is: this is byte-for-byte the original behaviour ONLY at exactly             |
//|  InpLots=0.01 (the shipped default), regardless of InpLotMode. No signal/entry-logic           |
//|  changes from any of this.                                                                       |
//+------------------------------------------------------------------+
//|  v2.10: Opus review found NthWeekdayOfMonth/LastWeekdayOfMonth built their |
//|  date at 12:00 noon, not midnight, so the "+86400 -> Monday" arithmetic in    |
//|  DSTGapHourAdjustment() landed each DST-gap boundary at Monday 12:00 rather     |
//|  than Monday 00:00 - harmless at this file's shipped hour thresholds (all       |
//|  above noon) but would silently mis-adjust any lower hour on the 4 transition    |
//|  Mondays/year. Changed both helpers to build at 00:00. No other logic changed.    |
//+------------------------------------------------------------------+
//|  v2.11: Opus review (2026-09-06, SESSION_NOTES.md item 19) of a real InpLots=0.03  |
//|  vs 0.01 backtest pair found the v2.09/v2.10 header comments above were WRONG:      |
//|  TargetDistance() does NOT "reduce back to the exact original literal-price-         |
//|  distance behaviour" whenever LOT_FIXED is used - it does so only at exactly          |
//|  InpLots=0.01. Running LOT_FIXED at 0.03 gave a 3x-wider take-profit than validated,    |
//|  which alone explained a win-rate drop from ~27% to ~16%, a near-doubled average         |
//|  hold time, and a much longer loss streak between two InpLots settings that looked        |
//|  like a safe linear rescale. Corrected both comments (v2.09's and TargetDistance()'s        |
//|  own) to state the true invariant, and added an OnInit warning that fires whenever          |
//|  InpLotMode != LOT_FIXED or InpLots != 0.01, since either one now silently trades a           |
//|  different, unvalidated reward:risk geometry under the same code - LOT_RISK_PCT               |
//|  specifically turns the ratio into a constant (InpFixedTargetUSD / risk-per-trade)             |
//|  that can land far below the ~11.8:1 this system is actually validated on. No signal/           |
//|  entry-logic changes; the shipped default (InpLotMode=LOT_FIXED, InpLots=0.01) is               |
//|  unaffected and was never wrong.                                                                  |
//+------------------------------------------------------------------+
//|  v2.12 (2026-09-06): indicator-visibility pass, from the Opus deep-dive review's  |
//|  third ask ("whatever indicators the EA's use ... i want to see them on the        |
//|  charts"). That review found this file already draws its 5 MAs but that three       |
//|  things it genuinely trades on were still invisible, so nothing added here changes   |
//|  a single decision - it only draws what the existing code already computes:          |
//|  (1) Stop, target and entry price. InpHideTradeMarks (on by default) switches MT5's  |
//|  own CHART_SHOW_TRADE_LEVELS off, and nothing ever replaced it - the real broker-    |
//|  side stop and the fixed $45 target were simply not on the chart, which matters      |
//|  more here than in any sibling: this file's whole edge is letting a rare winner      |
//|  reach that exact target (see the target sweep at the top of this header). Now       |
//|  three OBJ_HLINEs while a position is open (entry InpColEntryLine, stop             |
//|  InpColStopLine, target InpColTargetLine), deleted the moment the EA is flat.       |
//|  Horizontal rays, not per-bar segments: none of the three moves bar to bar, so one  |
//|  object each is both simpler and correct, and they are updated in place rather      |
//|  than recreated so they never re-bury the panel (the same creation-order problem    |
//|  g_panelReclaim exists for). Position is resolved through FindOwnPosition(), not    |
//|  the cached g_ticket, so the lines are right on the tick after a restart too.       |
//|  (2) Support/resistance. SRDistanceATR() computes the real prior-InpSRDays D1       |
//|  high/low but only ever surfaced a derived ATR distance on the panel - the price    |
//|  levels themselves were never drawn. Its D1 loop is now extracted verbatim into     |
//|  SRLevels() (no behaviour change) so the drawn level is provably the same one the   |
//|  filter tests, and both are drawn dashed in InpColSR. (3) The stop-buffer band.     |
//|  CheckForEntry() places the stop at the 50 EMA's value at entry -/+                 |
//|  InpStopBufferATR x ATR; the 50 was drawn, the buffer around it was not, leaving    |
//|  "where the stop would land if a trade opened on this bar" with no visible form.    |
//|  Now a dotted InpColStopBand envelope through the same DrawMASegment()/             |
//|  PurgeOldMALines() machinery the MAs use (DrawMASegment gained an optional `style`  |
//|  argument, defaulting to STYLE_SOLID, so every pre-existing call is unchanged),     |
//|  with a matching BackfillMALines() pass so a fresh attach shows the whole window    |
//|  rather than a 2-bar stub. That backfill computes a real per-bar ATR series (one    |
//|  CopyRates + ComputeWilderATR, 500 warm-up bars per UpdateATRManual()'s own note)   |
//|  instead of painting the whole history with today's ATR, which would have drawn a   |
//|  constant-width band that never existed. UpdateMALines()/BackfillMALines()' old     |
//|  leading `if(!InpShowMAs) return;` became a per-block guard (the shape              |
//|  Aurelius_EA.mq5 already uses) so the band is still purged with the MAs switched    |
//|  off; at the shipped defaults nothing about what gets drawn changed. New object     |
//|  prefix FULL_ for the horizontal levels (the band belongs to FULM_, since it really |
//|  is a per-bar segment pair and wants the same purge), swept in OnDeinit alongside   |
//|  FULP_/FULW_/FULM_; every new object is OBJPROP_HIDDEN and every new draw sits      |
//|  inside the existing g_skipCosmeticDraws gate, so a non-visual Strategy Tester pass |
//|  does none of it. No signal, entry, exit, sizing or risk-management logic touched.  |
//|                                                                                      |
//|  v2.13 (2026-09-14) - OPTIONAL MINIMUM STOP DISTANCE (InpMinStopATR, default 0.0    |
//|  = OFF = byte-for-byte v2.12 behaviour). Result of an exit-research pass that       |
//|  tested TWO proposed ideas and REJECTED BOTH; this input is the one thing that      |
//|  survived, and it came out of the falsification control rather than the proposals.  |
//|  Python only - NOT real-MT5 tested. Replica calibrated against the real 2026-09-06  |
//|  log first (809 vs 833 trades, avg win $38.04 vs $37.95, avg loss -$6.32 vs -$5.70, |
//|  worst -$65.11 vs -$65.83, after a $0.573/trade residual-slippage charge that puts  |
//|  net exactly on the real $1,320.25 for the CSV's 2023-01..2026-08 window).          |
//|                                                                                      |
//|  REJECTED 1 - SWAP THE $45 TARGET FOR AN ARM-THEN-TRAIL EXIT (Meridian_EA.mq5's     |
//|  InpTrailArmR / InpTrailATR style). Decisively worse, and for a structural reason:  |
//|  Fulcrum's initial risk is TINY (median $4.22, ~1.9 x ATR), so $45 is already ~10.7R|
//|  and ANY R-based arm point fires long before the target. 2.5R/1.0xATR (Meridian's   |
//|  own shipped values) -> net $666 vs $1,320, -50%. 42 of 42 sweep cells from 1.5-8R  |
//|  and 0.5-8xATR that arm meaningfully were worse. Net only rises above the baseline  |
//|  at arm 10-14R - i.e. an arm point of $39-$54, ABOVE the $45 target, where the trail|
//|  fires on 5.8-8.3% of trades and the config is really just "$45 ceiling removed".   |
//|  Even there it is not a win: max drawdown $444 vs $238 (+86%), and it is completely |
//|  TAIL-DOMINATED - the top 1% of trades carry 116% of net, and net-minus-top-5-trades|
//|  is $90 vs the shipped design's $1,098. Under the pessimistic intrabar convention   |
//|  it collapses further. This is the same lesson as the three exits already rejected  |
//|  in SESSION_NOTES.md item 6, reached from the opposite direction.                   |
//|                                                                                      |
//|  REJECTED 2 - FLAT $ CAP ON THE STOP (the fix that worked for Meridian v2.05).      |
//|  $15 looked like a +6% win ($1,405 vs $1,320) - and it is a mirage. The cap curve   |
//|  is jagged with no plateau ($12 $1,199 / $14 $1,263 / $15 $1,405 / $18 $1,253 /     |
//|  $25 $1,071 / $35 $1,372), every cap value is WORSE than the default in-sample, and |
//|  a monthly bootstrap gives P(no gain)=34.5%. The reason it flatters OOS: GOLD#'s    |
//|  median M5 ATR went $1.30 (2023) -> $6.76 (2026), so a $15 cap binds on 1.4% of     |
//|  2023 trades and 46.0% of 2026 trades - it is a DATE FILTER, exactly SESSION_NOTES  |
//|  item 5's methodology lesson #3. Re-expressed ATR-normalised (which binds evenly,   |
//|  9-13%/yr) the whole cap family is worse than the default at EVERY level tested.    |
//|  It does cut the loss tail by construction (-$65 -> -$16) but, unlike Meridian, it  |
//|  buys NO drawdown improvement here ($249 vs $238). Not shipped, no input added.     |
//|                                                                                      |
//|  WHAT SURVIVED - this input. Running the same methodology-lesson-#3 control in the  |
//|  other direction found that FLOORING the stop at k x ATR beats the default in       |
//|  14/14 grid cells in-sample and 9/14 blind-OOS, on a broad plateau (1.0x-4.0x all   |
//|  beat it), sits at the 98.3rd percentile of a 20,000-draw random-cull control (so   |
//|  it is not just "trades less"), is LESS tail-concentrated than the shipped default  |
//|  (top 1% = 20.5% of net vs 26.9%; net-minus-top-20 $631 vs $432), holds in 3 of 4   |
//|  years and at every IS/OOS boundary from 50% to 80%. At the shipped-adjacent 2.0x:  |
//|  net $1,520 vs $1,320 (+15%), PF 1.337 vs 1.315, monthly-bootstrap P(no gain)=8.4%. |
//|  $45 remains the best target WITH the floor on (checked $20-$90, both halves), so   |
//|  this is additive to the validated exit, not a re-parameterisation of it.           |
//|  HONEST LIMITS: it is NOT a drawdown or tail fix (maxDD $246 vs $238, worst loss    |
//|  -$65.11 unchanged) - it is a profit/robustness change only; P=8.4% is suggestive,  |
//|  not proof; and it was found by a grid search AFTER the two pre-registered ideas    |
//|  failed, so it carries selection risk the plateau/random-cull controls reduce but   |
//|  do not eliminate. Default 0.0 keeps v2.12 exactly; set 2.0 to test it for real.    |
//+------------------------------------------------------------------+
#property copyright "Fulcrum"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

enum ENUM_LOTMODE{ LOT_FIXED = 0, LOT_RISK_PCT = 1 };

input group "=== Entry: alignment stack (validated, ALIGN_MID mode) ==="
//--- M15 LEG-SET. The input NAMES are the M5 file's (InpP21/InpP600/InpP2400)
//--- and are kept on purpose as stable identifiers for fast/med/mid/slow/macro -
//--- exactly the convention Aurelius_M15_EA.mq5 uses, where InpP600 likewise
//--- holds 200 and InpP2400 holds 1200. Read the VALUE, not the name.
//--- Validated leg-space sweep (with a search-width correction) puts this set at
//--- the 96th-98th percentile for Fulcrum's own M15 risk/reward shape, and it is
//--- the same set Aurelius_M15_EA.mq5 actually ships. DO NOT restore the M5
//--- numbers here: 600/2400 on M15 runs a materially worse system.
input int    InpP21             = 30;       // FAST leg: 21 -> 30 vs Fulcrum_EA.mq5's M5 value
input int    InpP50             = 50;       // MED leg: unchanged at 50 on both timeframes - and it is
                                             // load-bearing that it is unchanged: this is the leg the
                                             // slope filter, criss-cross filter and pullback filter all
                                             // read, AND the structural stop anchor (CheckForEntry puts
                                             // the stop at this MA's value at entry +/- InpStopBufferATR
                                             // x ATR), AND the centre of the drawn stop-buffer band
input int    InpP150            = 150;      // MID leg: unchanged at 150
input int    InpP600             = 200;     // SLOW leg: 600 -> 200 (name kept, see the block comment)
input int    InpP2400            = 1200;    // MACRO leg: 2400 -> 1200 (name kept). NOT the naive 2400/3
                                             // = 800 rescale - 1200 is what the sweep actually found
//--- MA methods. Hardcoded in the iMA() calls in Fulcrum_EA.mq5 (EMA/EMA/EMA/
//--- SMA/EMA); selectable inputs here, matching Aurelius_M15_EA.mq5's pattern,
//--- because the validated M15 slow leg needs MODE_SMMA - a method the M5 file's
//--- hardcoding could not express at all.
input ENUM_MA_METHOD InpM21     = MODE_EMA;  // FAST method - unchanged from M5
input ENUM_MA_METHOD InpM50     = MODE_EMA;  // MED method - unchanged from M5
input ENUM_MA_METHOD InpM150    = MODE_EMA;  // MID method - unchanged from M5
input ENUM_MA_METHOD InpM600    = MODE_SMMA; // SLOW method - M5 hardcodes MODE_SMA here; the validated
                                              // M15 leg-set uses MODE_SMMA (matching Aurelius_M15_EA.mq5).
                                              // This is the one METHOD that differs between the two files -
                                              // do not carry the M5 SMA choice over
input ENUM_MA_METHOD InpM2400   = MODE_EMA;  // MACRO method - unchanged from M5
input double InpMinSlopeATR      = 0.50;    // 50 EMA slope over InpSlopeBars, x ATR - lower bound
input double InpMaxSlopeATR      = 1.00;    // upper bound (0 = no cap)
input int    InpSlopeBars        = 20;
input int    InpCrossWindow      = 10;      // bars checked for 21x50 crisscrossing
input int    InpMaxCrosses       = 1;       // skip entries into choppy/criss-crossing conditions
input double InpPullbackTolATR   = 0.25;    // how close to the 50 counts as "touched", x ATR
input int    InpPullbackBars     = 10;      // lookback for the touch
input bool   InpUseVolume        = true;
input int    InpVolAvgBars       = 100;
input double InpMinVolRatio      = 1.30;
input bool   InpUseSRDist        = true;
input int    InpSRDays           = 3;
input double InpMinSRDistATR     = 0.50;
input int    InpCooldownBars     = 5;

input group "=== Exit: structural stop + fixed target (the whole point of this EA) ==="
//--- UNCHANGED from Fulcrum_EA.mq5 v2.13, and that is a finding, not an
//--- oversight. A naive M15 target sweep appeared to favour $60-70; decomposing
//--- by exit reason showed the entire apparent gain came from trades force-closed
//--- into Friday, and once that bucket is isolated $45 is genuinely best on M15
//--- too. Do NOT "fix" these from a fresh naive sweep - same lesson as
//--- SESSION_NOTES.md item 6 and the v2.04 gate test in the header above.
input double InpStopBufferATR    = 0.15;    // stop = the MED MA's value at entry +/- this many ATR
input double InpFixedTargetUSD   = 45.0;    // fixed $ target at InpLots=0.01 (scale with lot size)
input double InpMinStopATR       = 0.0;     // M15 NOTE: kept at v2.13's default of 0.0 (off) and NOT claimed
                                             // to be validated here - every number in the comment below was
                                             // measured on M5 only. On M15 this is an untested opt-in.
                                             // OPT-IN (0 = off = shipped v2.12 behaviour). Floor on the initial
                                             // stop DISTANCE, as a multiple of entry ATR(14): if the 50 EMA
                                             // happens to sit closer than this to the fill, push the stop out to
                                             // InpMinStopATR x ATR instead. Deliberately an ATR MULTIPLE, never a
                                             // dollar amount - GOLD#'s median M5 ATR ran $1.30 in 2023 and $6.76
                                             // in 2026 on the validated sample, so any absolute-$ stop threshold
                                             // on this symbol is a disguised date filter (SESSION_NOTES.md item 5,
                                             // methodology lesson #3 - independently re-confirmed on this EA).
                                             // WHY IT IS HERE: Fulcrum's structural stop has no lower bound, and
                                             // its median initial risk is only ~1.9 x ATR (~$4.22) - a real share
                                             // of losers are ordinary noise stop-outs on trades that had not been
                                             // invalidated. Widening the tightest stops leaves the $45 target and
                                             // the let-winners-run mechanism completely untouched; it only stops
                                             // throwing away trades that were still alive. Python finding ONLY,
                                             // NOT real-MT5 tested: +15% net ($1,520 vs $1,320 slippage-charged on
                                             // 2023-01..2026-08), better in 14/14 grid cells in-sample and 9/14
                                             // blind-OOS, 98.3rd percentile against a random-cull control, and
                                             // LESS tail-concentrated than the shipped default (top 1% of trades
                                             // carry 20.5% of net vs 26.9%). It does NOT reduce drawdown (maxDD
                                             // $246 vs $238) and does NOT cut the worst loss (-$65 either way) -
                                             // it is a profit/robustness change, not a tail fix. Trade-offs: win
                                             // rate 17.9% -> 22.4%, average loss -$6.32 -> -$8.07, ~11% fewer
                                             // trades, median hold 1.3h -> 2.6h. 1.0-4.0 is the tested range and
                                             // the whole range beats the default; 2.0 is a mid-plateau pick, NOT
                                             // the grid maximum (that was 3.5, which is where a curve-fit would
                                             // have landed). RUN A REAL MT5 BACKTEST before trusting any of it.

input group "=== Risk ==="
input ENUM_LOTMODE InpLotMode    = LOT_FIXED;   // How the size is decided
input double InpLots             = 0.01;
input double InpRiskPct          = 1.0;         // Risk per trade (% of balance) - needs a stop
input double InpMaxLots          = 1.0;         // Hard cap on size
input double InpMaxDailyLossPct  = 0.0;         // Stop trading after this daily loss % (0 = off)
input int    InpMaxSpreadPoints  = 60;
input int    InpSlippage         = 20;

input group "=== Session protection ==="
input int    InpFridayNoEntryHour = 20;
input int    InpFridayCloseHour   = 22;

input group "=== Misc ==="
input ulong  InpMagic            = 750092;  // DELIBERATELY different from Fulcrum_EA.mq5's 750091 so the M5
                                             // and M15 versions can run on the same account/symbol at the same
                                             // time without their position lookups (FindOwnPosition), cooldown
                                             // counter, realized-P&L accumulator or daily-loss circuit breaker
                                             // ever seeing each other's trades. Verified free against every
                                             // .mq5 in this repo: Aurelius 750004, Ratchet 750005, Prism/
                                             // StochSwing 750007, AsiaRangeBreak 750008, Aurelius_M15 750015,
                                             // Fulcrum 750091, Bastion 750095, Zenith 750210, Meridian
                                             // 750500/750501/750502, Daybreak 778821, AuRebound 800001,
                                             // Slipstream 20260101, Tailwind 20260102. 750092 sits in
                                             // Fulcrum's own 7500xx neighbourhood (next free number after
                                             // 750091, and below Bastion's 750095), the same per-EA block
                                             // convention Meridian uses for its 750500-750502 slots.
input string InpTradeComment     = "Fulcrum M15";  // distinct from the M5 file's "Fulcrum" so a merged deal
                                                    // export can be split by timeframe as well as by magic

input group "=== Panel ==="
input bool    InpShowPanel   = true;
input int     InpPanelX      = 12;                // matches Aurelius/Ratchet - same top-left anchor
input int     InpPanelY      = 30;                // (was 20/20 - one panel sat a few px off from its siblings)
input int     InpPanelW      = 260;
input int     InpPanelDrag   = 1;                 // 0 = locked, 1 = draggable
input string  InpPanelFont   = "Consolas";
input int     InpPanelSize   = 8;
input color   InpPanelBg     = C'13,17,28';
input color   InpHeaderBg    = C'28,36,58';
input color   InpPanelEdge   = C'0,150,255';       // border - neon blue, matches the bull colour
input color   InpTitleCol    = C'0,150,255';
input color   InpSectionCol  = C'214,226,238';
input color   InpTextCol     = C'150,166,192';
input color   InpValCol      = C'236,242,252';
input color   InpOkCol       = C'0,230,118';       // filter passed - neon green
input color   InpNoCol       = C'255,61,90';       // filter blocked - hot red

input group "=== Chart theme ==="
input color   InpChartBg     = clrBlack;            // matches Aurelius/Ratchet/Slipstream/Tailwind
input color   InpBullCol     = C'0,150,255';        // neon blue
input color   InpBearCol     = clrWhite;             // neon white
input bool    InpHideTradeMarks = true;             // Hide MT5's own buy/sell/SL/TP arrows and lines - the panel
                                                     // and MA lines are meant to be the only things on this chart
input bool    InpShowMAs     = true;                // Draw the moving averages on the chart, each its own neon colour
input int     InpMAHistoryBars = 2500;              // How many recent bars of MA line history to keep drawn (bounded,
                                                     // so a long-running live EA doesn't accumulate objects forever)
input color   InpCol21       = clrYellow;           // MA 21 line colour
input color   InpCol50       = C'255,140,0';        // MA 50 line colour - neon orange (NOT white:
                                                     // InpBearCol/CHART_COLOR_CHART_DOWN are also
                                                     // white, and the 50 hugs price closely enough
                                                     // to vanish into bearish candle bodies/wicks)
input color   InpCol150      = C'191,0,255';        // MA 150 line colour - neon purple
input color   InpCol600      = C'255,20,147';       // MA 600 line colour - neon pink
input color   InpCol2400     = C'57,255,20';        // MA 2400 line colour - neon green
//--- v2.12 indicator-visibility inputs. All cosmetic: nothing below is read by
//--- any entry, exit, sizing or risk decision, and every draw they gate sits
//--- behind g_skipCosmeticDraws exactly like the MA lines above.
input bool    InpShowTradeLevels = true;            // Draw the OPEN position's entry, stop and target as
                                                     // horizontal lines. InpHideTradeMarks (above, on by
                                                     // default) switches MT5's own CHART_SHOW_TRADE_LEVELS
                                                     // off, which left the real stop and the $45 target -
                                                     // this system's entire edge, per the header - invisible
                                                     // with nothing replacing them
input color   InpColEntryLine = C'150,166,192';      // Entry-price line - same silver-grey as InpTextCol
input color   InpColStopLine  = C'255,61,90';        // Stop-loss line - same hot red as InpNoCol
input color   InpColTargetLine= C'0,230,118';        // Take-profit line - same neon green as InpOkCol
input bool    InpShowSR      = true;                 // Draw the prior-InpSRDays daily high/low the S/R
                                                     // proximity filter actually measures against.
                                                     // Independent of InpUseSRDist on purpose - the levels
                                                     // are worth seeing even when the filter reading them
                                                     // is switched off
input color   InpColSR       = C'120,144,176';       // S/R level colour - InpSectionCol's silver, dimmed
                                                     // roughly in half so a static daily level never
                                                     // competes with the live MA lines for attention
input bool    InpShowStopBand = true;                // Draw the InpStopBufferATR envelope around the 50 EMA -
                                                     // this EA's stop is placed at the 50 EMA's value AT
                                                     // ENTRY offset by that buffer, so this band is literally
                                                     // "where the stop would go if a trade opened on this
                                                     // bar", the one piece of the exit geometry with no
                                                     // visible form until now
input color   InpColStopBand = C'128,70,0';          // Stop-buffer band colour - InpCol50's neon orange at
                                                     // ~half brightness, so the band reads as a zone
                                                     // belonging to that line rather than as a sixth MA
                                                     // (drawn STYLE_DOT too)

input group "=== Wallpaper & watermark ==="
input string  InpBackgroundBMP = "Fulcrum_Wallpaper.bmp";  // .bmp file in <data folder>\MQL5\Images
input int     InpBgWidth       = 1290;
input int     InpBgHeight      = 720;
input string  InpWatermark     = "FULCRUM M15";          // empty = none
input color   InpWaterCol      = C'46,38,24';
input bool    InpWaterBottom   = true;                // bottom-right instead of centred
input int     InpWaterSize     = 42;
input string  InpWaterFont     = "Arial Black";

CTrade trade;

int h21 = INVALID_HANDLE, h50 = INVALID_HANDLE, h150 = INVALID_HANDLE;
int h600 = INVALID_HANDLE, h2400 = INVALID_HANDLE;
// v2.02: ATR is no longer read via a built-in iATR() handle - see
// ComputeWilderATR()'s header note for why. g_atrManual is refreshed once
// per new bar in OnCalculate.../OnTick, read through GetATR() everywhere
// the old MA(hATR,shift,atr) pattern was used. Same fix as Aurelius_EA.mq5
// v1.36, which shares this file's entry gate.
double   g_atrManual = 0.0;

datetime g_lastBar        = 0;
int      g_barsSinceClose = 9999;

ulong    g_ticket  = 0;
int      g_posDir  = 0;
double   g_entryPx = 0.0;
int      g_panelMinW = 0;
//--- Controls whether PRect/PText delete-and-recreate (to reclaim top-of-
//--- stack, see their own comments) or just update the existing object's
//--- properties in place. Reclaiming is only NEEDED once per new bar,
//--- right after UpdateMALines() adds the one new object that could bury
//--- the panel - churning it on EVERY draw call (which, between bars, was
//--- happening up to once a second from the live-P&L refresh) made the
//--- whole panel visibly flash/repaint instead of just its numbers
//--- updating, since deleting and recreating a dozen large filled
//--- rectangles is a much bigger visual event than the text-only churn
//--- this pattern originally shipped with. DrawPanel() sets this at the
//--- top of every call from its own `reclaim` parameter - true only for
//--- the once-per-new-bar draw (and the very first draw), false for
//--- every live-number-only refresh in between.
bool     g_panelReclaim = true;

//--- running "today" realized P/L - O(1) accumulator, updated only on a
//--- closing deal in OnTradeTransaction. Deliberately NOT a HistorySelect
//--- scan (that exact pattern is what made Aurelius take 8 hours to
//--- backtest before it was fixed - built right here from the start).
double   g_myRealizedToday = 0.0;
datetime g_dayStamp        = 0;
//--- account equity at the start of today - needed to split "today (mine)"
//--- from "today (other)" in the ACCOUNT panel section, same convention as
//--- Aurelius_EA.mq5/Ratchet_EA.mq5. This file previously only showed its
//--- own realized P&L with no floating component and no "other" comparison -
//--- inconsistent with its siblings when all three share an account.
double   g_dayStartEquity  = 0.0;

//--- panel/wallpaper/watermark plumbing
string   g_pp = "FULP_";     // panel object prefix
string   g_pw = "FULW_";     // wallpaper/watermark prefix, kept out of the panel wipe
string   g_pm = "FULM_";     // per-bar MA line segments, purged to a rolling window - see UpdateMALines
//--- v2.12: horizontal price levels (entry, stop, target, prior-days S/R).
//--- Deliberately NOT g_pm: those are per-bar OBJ_TREND segments swept by
//--- PurgeOldMALines on a rolling window, whereas these are a fixed handful of
//--- OBJ_HLINEs updated in place and deleted explicitly the moment they stop
//--- applying. The stop-buffer band is the one new drawing that DOES belong to
//--- g_pm - it really is a per-bar segment pair, so it wants the same purge.
string   g_pl = "FULL_";
int      g_panX = -1, g_panY = -1;   // live panel position once dragged
bool     g_bgOK = false;
int      g_bgTries = 0;

//--- PERFORMANCE FIX applied from v1: see header. Computed once, gates
//--- every cosmetic draw call for the lifetime of the run.
bool     g_skipCosmeticDraws = false;

void PBackground();
void PWatermark();
void DrawPanel(const bool reclaim = true);
void UpdateMALines();
void BackfillMALines();
//--- v2.12: the indicator-visibility draws sit up with the rest of the drawing
//--- code, but the values they draw are computed further down the file.
void UpdateLevelLines();                    // OnInit draws the price levels at attach time too
bool SRLevels(double &hi, double &lo);      // extracted from SRDistanceATR - the same levels the filter tests
bool FindOwnPosition(ulong &ticket);        // symbol+magic scoped, per item 16's ticket-scoping rule
double LotSize(const double stopDistance);  // OnInit's reward:risk warning needs the EFFECTIVE lot size,
                                            // i.e. after this function's own broker-volume clamping
bool GetATR(double &out);
void ComputeWilderATR(const MqlRates &arr[], double &out[], int period);   // BackfillMALines needs a per-bar
                                                                           // ATR series for the stop band

//+------------------------------------------------------------------+
int OnInit()
  {
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   //--- methods come from the InpM* inputs here, not hardcoded as in
   //--- Fulcrum_EA.mq5 - the validated M15 slow leg needs MODE_SMMA.
   h21   = iMA(_Symbol, PERIOD_CURRENT, InpP21,  0, InpM21,   PRICE_CLOSE);
   h50   = iMA(_Symbol, PERIOD_CURRENT, InpP50,  0, InpM50,   PRICE_CLOSE);
   h150  = iMA(_Symbol, PERIOD_CURRENT, InpP150, 0, InpM150,  PRICE_CLOSE);
   h600  = iMA(_Symbol, PERIOD_CURRENT, InpP600, 0, InpM600,  PRICE_CLOSE);
   h2400 = iMA(_Symbol, PERIOD_CURRENT, InpP2400,0, InpM2400, PRICE_CLOSE);
   if(h21==INVALID_HANDLE || h50==INVALID_HANDLE || h150==INVALID_HANDLE ||
      h600==INVALID_HANDLE || h2400==INVALID_HANDLE)
     {
      Print("Fulcrum M15 EA: failed to create an indicator handle");
      return(INIT_FAILED);
     }
   PrintFormat("Fulcrum M15 EA init: legs %d/%s %d/%s %d/%s %d/%s %d/%s, magic %I64u",
               InpP21,   EnumToString(InpM21),
               InpP50,   EnumToString(InpM50),
               InpP150,  EnumToString(InpM150),
               InpP600,  EnumToString(InpM600),
               InpP2400, EnumToString(InpM2400), InpMagic);
   if(_Period != PERIOD_M15)
      Print("Fulcrum M15 EA WARNING: this variant is validated on M15 - its MA leg periods/methods "
            "(InpP21/InpP600/InpP2400/InpM600) are M15-specific and are NOT validated on any other "
            "timeframe. Use Fulcrum_EA.mq5 for M5. Current timeframe is ",
            EnumToString((ENUM_TIMEFRAMES)_Period));

   // 2026-09-06 (Opus review, SESSION_NOTES.md item 19): TargetDistance()
   // makes the take-profit's PRICE distance proportional to 1/lots so
   // InpFixedTargetUSD keeps meaning the same DOLLAR amount regardless of
   // position size - but that also means InpLots (under LOT_FIXED) or
   // InpRiskPct (under LOT_RISK_PCT) silently changes the reward:risk
   // GEOMETRY, not just the dollar scale. This system is only validated at
   // exactly InpLots=0.01 under LOT_FIXED (~11.8:1 reward:risk); any other
   // fixed lot, or LOT_RISK_PCT at all (which makes the ratio a constant
   // equal to InpFixedTargetUSD/riskCash - far below 11.8:1 at a typical
   // small-account risk %), trades a materially different, unvalidated
   // system with the same code. Warn loudly rather than let that happen
   // silently - not a hard refusal, since a deliberate, informed override
   // is still someone's call to make, not this EA's.
   if(InpLotMode != LOT_FIXED)
      Print("Fulcrum M15 EA WARNING: InpLotMode is not LOT_FIXED - TargetDistance() will scale the "
            "take-profit's price distance to keep InpFixedTargetUSD's DOLLAR value fixed, which "
            "means InpRiskPct now controls this system's reward:risk ratio, not just its position "
            "size. This is UNVALIDATED - the ~11.8:1 reward:risk this system was tested on only "
            "holds at InpLots=0.01 under LOT_FIXED.");
   else if(MathAbs(InpLots - 0.01) > 0.0001)
      PrintFormat("Fulcrum M15 EA WARNING: InpLots=%.2f, not the validated 0.01 - TargetDistance() will "
                  "scale the take-profit's price distance by 0.01/%.2f, changing this system's "
                  "reward:risk ratio, not just its position size. This is UNVALIDATED at any lot "
                  "size other than 0.01.", InpLots, InpLots);

   // 2026-09-20 (Opus review): both warnings above test the INPUT, but the
   // geometry actually traded depends on what LotSize() RETURNS - and
   // LotSize() raises anything below the broker's SYMBOL_VOLUME_MIN up to it
   // (MathMax(mn, ...)), and floors to SYMBOL_VOLUME_STEP. On a broker whose
   // minimum gold volume is 0.10 - normal on "standard" (non-micro) accounts -
   // InpLots=0.01 is silently traded as 0.10, TargetDistance() shrinks the
   // take-profit's price distance to 0.01/0.10 = one tenth of the validated
   // $45, and the ATR-based structural stop does NOT shrink with it. That is
   // roughly a 1:1 reward:risk on a system whose edge needs ~11.8:1 at a ~30%
   // win rate on this timeframe - a guaranteed loser - and BOTH warnings above
   // stay silent, because InpLots itself is still exactly 0.01. Check the
   // effective size, not the requested one. LotSize(0.0) is the right probe:
   // its LOT_RISK_PCT branch is gated on stopDistance > 0.0, so this returns
   // exactly the clamping the fixed path would apply.
   double effLots = LotSize(0.0);
   if(MathAbs(effLots - InpLots) > 0.0001)
      PrintFormat("Fulcrum M15 EA WARNING: this broker's volume constraints turn InpLots=%.2f into an "
                  "EFFECTIVE %.2f lots (SYMBOL_VOLUME_MIN=%.2f, SYMBOL_VOLUME_STEP=%.2f, InpMaxLots=%.2f). "
                  "TargetDistance() scales the take-profit's price distance by 0.01/%.2f while the "
                  "structural stop does not scale at all, so the ~11.8:1 reward:risk this system is "
                  "validated on does NOT hold on this account.",
                  InpLots, effLots,
                  SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
                  SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP),
                  InpMaxLots, effLots);

   UpdateATRManual();   // initial seed - also refreshed once per new bar

   ChartSetInteger(0, CHART_COLOR_BACKGROUND, InpChartBg);
   ChartSetInteger(0, CHART_COLOR_CHART_UP, InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CHART_DOWN, InpBearCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, InpBearCol);
   //--- the panel/MA lines are meant to be the only things on this chart -
   //--- MT5's own buy/sell arrows and SL/TP lines are a terminal display
   //--- setting, not chart objects, so they can't be deleted via code -
   //--- this is the actual way to turn them off.
   if(InpHideTradeMarks)
     {
      ChartSetInteger(0, CHART_SHOW_TRADE_LEVELS, false);
      ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, false);
     }
   if(!g_skipCosmeticDraws)
     {
      BackfillMALines(); // fill in the whole rolling window immediately,
                          // not just a 1-bar stub per line (see its comment)
      //--- v2.12: same "show something the moment it attaches" reasoning as
      //--- the DrawPanel() call below - otherwise the stop/target/entry/S-R
      //--- levels would not appear until the next M15 bar closes, and on a
      //--- restart with a position already open (the case CheckForEntry()'s
      //--- own FindOwnPosition re-sync exists to handle) that is exactly the
      //--- moment the stop and target most need to be on the chart. Reading
      //--- the position directly here rather than via g_ticket is what makes
      //--- this correct at OnInit, before any tick has restored that cache.
      UpdateLevelLines();
      //--- unlike Aurelius_EA.mq5 (draws immediately in OnInit) and
      //--- Ratchet_EA.mq5 (redraws once a second via EventSetTimer),
      //--- this file has neither - it deliberately never starts a timer
      //--- (see the header's PERFORMANCE FIX #3) and never drew the panel
      //--- until the first real tick reached OnTick(). Show something the
      //--- moment it attaches, same as Aurelius, instead of depending on
      //--- tick timing for the very first draw.
      PBackground();
      DrawPanel();
      ChartRedraw(0);
     }
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pw);
   ObjectsDeleteAll(0, g_pm);
   ObjectsDeleteAll(0, g_pl);   // v2.12: entry/stop/target/S-R horizontal levels
  }
//+------------------------------------------------------------------+
bool MA(const int handle, const int shift, double &out)
  {
   double b[];
   ArraySetAsSeries(b, true);
   if(CopyBuffer(handle, 0, shift, 1, b) < 1) return(false);
   out = b[0];
   return(true);
  }
//+------------------------------------------------------------------+
//| Each MA drawn as its own neon-coloured line. An EA has no plot       |
//| buffers (only an indicator can set PLOT_LINE_COLOR), so a built-in     |
//| ChartIndicatorAdd() approach could only show MT5's own auto-assigned    |
//| colours, never a specific one per line - this draws one new trend        |
//| segment per MA per new bar instead (bar[shift2]->bar[shift1], same         |
//| idiom this repo already uses for session VWAP dots), and sweeps            |
//| anything older than InpMAHistoryBars so a long-running live EA doesn't      |
//| accumulate objects forever. Called once per new bar, gated by                |
//| g_skipCosmeticDraws same as every other cosmetic draw in this file.           |
//+------------------------------------------------------------------+
//| v2.12: `style` added (default STYLE_SOLID, so every existing call      |
//| below is byte-for-byte unchanged) purely so the stop-buffer band can    |
//| be drawn dotted through this same function - the band is a guide, not   |
//| an indicator line, and must not read as a sixth MA.                     |
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
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);      // keep it out of the Object List/dialog -
                                                        // up to 5*InpMAHistoryBars of these exist
  }
//+------------------------------------------------------------------+
void PurgeOldMALines(const datetime latestBarTime)
  {
   datetime cutoff = latestBarTime - (datetime)((long)InpMAHistoryBars * PeriodSeconds(PERIOD_CURRENT));
   for(int i = ObjectsTotal(0, 0, OBJ_TREND) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, OBJ_TREND);
      if(StringFind(nm, g_pm) != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < cutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
//| v2.12 - horizontal price levels (entry / stop / target / prior-days  |
//| S+R).                                                                |
//|                                                                      |
//| A stop, a target or a daily high doesn't move bar to bar, so these    |
//| are single OBJ_HLINE rays rather than the per-bar OBJ_TREND segments   |
//| the MAs need - one object each, not one per bar, so there is nothing   |
//| here for PurgeOldMALines to sweep and no risk of the Object List flood  |
//| that forced OBJPROP_HIDDEN onto DrawMASegment.                         |
//|                                                                        |
//| Created once and then UPDATED IN PLACE (ObjectSetDouble on the existing |
//| object) rather than deleted and recreated. That matters for exactly the |
//| reason g_panelReclaim exists: MT5 stacks objects by creation order, so  |
//| recreating a level every bar would keep re-burying the panel under it.  |
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
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);   // same reason as DrawMASegment - these
                                                     // are EA chrome, not user-drawn analysis
  }
//+------------------------------------------------------------------+
//| Called once per new bar from OnTick, immediately after                |
//| UpdateMALines() and BEFORE DrawPanel() - the same creation-order       |
//| reasoning that already puts UpdateMALines there (see that call site).  |
//| Deliberately not folded into DrawPanel()'s own in-position branch,     |
//| even though that branch already reads POSITION_SL/POSITION_TP for its  |
//| own rows: anything created from inside DrawPanel() would be created    |
//| AFTER the panel's own background/frame that same cycle and would       |
//| therefore paint over it.                                              |
//|                                                                        |
//| Purely cosmetic - reads position state and daily highs/lows, writes     |
//| nothing but chart objects. It can never affect a trading decision.      |
//+------------------------------------------------------------------+
void UpdateLevelLines()
  {
   //--- open position: entry, the stop actually sitting at the broker, and
   //--- the fixed target. InpHideTradeMarks turns MT5's own SL/TP lines off,
   //--- so without these the real exit geometry is invisible on a live chart -
   //--- and per this file's header, the whole edge lives in letting a winner
   //--- reach that target, which makes it the one level most worth watching.
   if(InpShowTradeLevels)
     {
      //--- FindOwnPosition() rather than g_ticket: symbol+magic scoped (item
      //--- 16's rule), and correct even on the tick right after a restart,
      //--- before any cached ticket has been re-synced.
      ulong tk = 0;
      if(FindOwnPosition(tk) && PositionSelectByTicket(tk))
        {
         DrawLevelLine("entry", PositionGetDouble(POSITION_PRICE_OPEN), InpColEntryLine, STYLE_SOLID, 1);
         //--- a 0.0 SL/TP is a real, normal state (an order that came back
         //--- without one, or a stop this EA has not attached) - DrawLevelLine
         //--- deletes rather than drawing a line at price 0.
         DrawLevelLine("sl", PositionGetDouble(POSITION_SL), InpColStopLine,   STYLE_SOLID, 1);
         DrawLevelLine("tp", PositionGetDouble(POSITION_TP), InpColTargetLine, STYLE_SOLID, 1);
        }
      else
        { DeleteLevelLine("entry"); DeleteLevelLine("sl"); DeleteLevelLine("tp"); }
     }
   else
     { DeleteLevelLine("entry"); DeleteLevelLine("sl"); DeleteLevelLine("tp"); }

   //--- prior-InpSRDays daily high/low - the exact pair SRDistanceATR()
   //--- measures against (same SRLevels() call, not a re-derivation, so the
   //--- drawn level cannot drift from the tested one). Dashed, because these
   //--- are structural reference levels, not live indicator values.
   if(InpShowSR)
     {
      double hi, lo;
      if(SRLevels(hi, lo))
        {
         DrawLevelLine("srhi", hi, InpColSR, STYLE_DASH, 1);
         DrawLevelLine("srlo", lo, InpColSR, STYLE_DASH, 1);
        }
     }
   else
     { DeleteLevelLine("srhi"); DeleteLevelLine("srlo"); }
  }
//+------------------------------------------------------------------+
void UpdateMALines()
  {
   //--- v2.12: the early `if(!InpShowMAs) return;` that used to sit here has
   //--- become a per-block guard instead, so the stop-buffer band can still be
   //--- drawn (and, more importantly, still be PURGED) with the MAs switched
   //--- off. Same shape Aurelius_EA.mq5's UpdateMALines already uses for its
   //--- MA/VWAP split. No change to what gets drawn at the shipped defaults.
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, 2);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(tA == 0 || tB == 0) return;
   if(InpShowMAs)
     {
      double m21a, m21b, m50a, m50b, m150a, m150b, m600a, m600b, m2400a, m2400b;
      if(MA(h21,2,m21a) && MA(h21,1,m21b) && MA(h50,2,m50a) && MA(h50,1,m50b) &&
         MA(h150,2,m150a) && MA(h150,1,m150b) && MA(h600,2,m600a) && MA(h600,1,m600b) &&
         MA(h2400,2,m2400a) && MA(h2400,1,m2400b))
        {
         DrawMASegment("21",   tA, m21a,   tB, m21b,   InpCol21);
         DrawMASegment("50",   tA, m50a,   tB, m50b,   InpCol50);
         DrawMASegment("150",  tA, m150a,  tB, m150b,  InpCol150);
         DrawMASegment("600",  tA, m600a,  tB, m600b,  InpCol600);
         DrawMASegment("2400", tA, m2400a, tB, m2400b, InpCol2400);
        }
     }
   //--- v2.12: the stop-buffer envelope. CheckForEntry() places the stop at
   //--- ma50 -/+ InpStopBufferATR * atr (see its own line), so this band is
   //--- exactly "where the stop would be put if a trade opened on this bar" -
   //--- drawn from the same two quantities, not a look-alike reconstruction.
   if(InpShowStopBand)
     {
      double atr, s50a, s50b;
      if(GetATR(atr) && atr > 0.0 && MA(h50, 2, s50a) && MA(h50, 1, s50b))
        {
         //--- GetATR() is the last-CLOSED-bar value (g_atrManual, refreshed
         //--- once per new bar just before this call site), i.e. the ATR at
         //--- shift 1 - the same reading CheckForEntry() would use. Applied to
         //--- both ends of this one-bar segment, which leaves at most a
         //--- sub-pixel step between consecutive segments as ATR drifts.
         double buf = atr * InpStopBufferATR;
         DrawMASegment("sbhi", tA, s50a + buf, tB, s50b + buf, InpColStopBand, STYLE_DOT);
         DrawMASegment("sblo", tA, s50a - buf, tB, s50b - buf, InpColStopBand, STYLE_DOT);
        }
     }
   //--- purges everything tagged g_pm (MAs and the stop band alike), so this
   //--- must run whenever EITHER is shown, not nested inside just one of them -
   //--- a band drawn with the MAs switched off would otherwise accumulate
   //--- forever, the exact leak PurgeOldMALines exists to prevent.
   if(InpShowMAs || InpShowStopBand) PurgeOldMALines(tB);
  }
//+------------------------------------------------------------------+
//| UpdateMALines() only ever draws ONE new bar's worth of segment per     |
//| call, so a fresh attach would show a single 1-bar stub per line and     |
//| take InpMAHistoryBars bars (300 = ~25h on M5) to fill in the window       |
//| the input claims to be showing. Called once from OnInit instead, this      |
//| walks backward and draws the whole rolling window immediately. Same        |
//| shift-1-minimum, no-lookahead indexing as UpdateMALines - never touches     |
//| bar 0.                                                                        |
//+------------------------------------------------------------------+
void BackfillMALines()
  {
   if(InpShowMAs)
     {
      int avail = Bars(_Symbol, PERIOD_CURRENT) - 2;
      int n = MathMin(InpMAHistoryBars, avail);
      double a, b;
      for(int s = n; s >= 1; s--)
        {
         datetime tA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
         datetime tB = iTime(_Symbol, PERIOD_CURRENT, s);
         if(tA == 0 || tB == 0) continue;
         if(MA(h21,  s+1,a) && MA(h21,  s,b)) DrawMASegment("21",  tA,a,tB,b,InpCol21);
         if(MA(h50,  s+1,a) && MA(h50,  s,b)) DrawMASegment("50",  tA,a,tB,b,InpCol50);
         if(MA(h150, s+1,a) && MA(h150, s,b)) DrawMASegment("150", tA,a,tB,b,InpCol150);
         if(MA(h600, s+1,a) && MA(h600, s,b)) DrawMASegment("600", tA,a,tB,b,InpCol600);
         if(MA(h2400,s+1,a) && MA(h2400,s,b)) DrawMASegment("2400",tA,a,tB,b,InpCol2400);
        }
     }
   //--- v2.12: the same backfill for the stop-buffer band, so a fresh attach
   //--- shows the whole envelope rather than a 2-bar stub. The band's width at
   //--- bar s has to be the ATR AT bar s (that is the ATR CheckForEntry() would
   //--- have sized the stop with), so painting all 2500 bars with today's
   //--- g_atrManual would draw a constant-width band that never existed. One
   //--- CopyRates + one ComputeWilderATR gives the whole series in a single
   //--- pass instead of an ATR read per bar; the +500 warm-up bars are for the
   //--- reason UpdateATRManual()'s own header gives (a short window leaves the
   //--- Wilder SMA seed carrying real weight).
   if(InpShowStopBand)
     {
      int availB = Bars(_Symbol, PERIOD_CURRENT) - 2;
      int nB = MathMin(InpMAHistoryBars, availB);
      MqlRates rr[]; ArraySetAsSeries(rr, false);
      int got = CopyRates(_Symbol, PERIOD_CURRENT, 1, nB + 1 + 500, rr);
      if(got >= 14 + 2)
        {
         double atrSeries[];
         ComputeWilderATR(rr, atrSeries, 14);
         double sa, sb;
         for(int s = nB; s >= 1; s--)
           {
            //--- rr[] is ascending (oldest first) and its LAST element is
            //--- shift 1, so shift s lives at index got - s.
            int iA = got - (s + 1), iB = got - s;
            if(iA < 0 || iB < 0) continue;
            double atrA = atrSeries[iA], atrB = atrSeries[iB];
            if(atrA == EMPTY_VALUE || atrB == EMPTY_VALUE || atrA <= 0.0 || atrB <= 0.0) continue;
            datetime tA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
            datetime tB = iTime(_Symbol, PERIOD_CURRENT, s);
            if(tA == 0 || tB == 0) continue;
            if(!MA(h50, s + 1, sa) || !MA(h50, s, sb)) continue;
            double bufA = atrA * InpStopBufferATR, bufB = atrB * InpStopBufferATR;
            DrawMASegment("sbhi", tA, sa + bufA, tB, sb + bufB, InpColStopBand, STYLE_DOT);
            DrawMASegment("sblo", tA, sa - bufA, tB, sb - bufB, InpColStopBand, STYLE_DOT);
           }
        }
     }
  }
//+------------------------------------------------------------------+
//| Manual Wilder ATR, matching the Python atr_wilder() implementation |
//| this file's ATR-scaled thresholds were tuned against (SMA seed of   |
//| the first `period` true ranges landing at index `period`, then       |
//| Wilder recursive smoothing). Deliberately NOT the built-in iATR() -    |
//| a real GOLD# D1 export elsewhere in this repo proved this broker's      |
//| iATR is actually a plain SMA(period) of True Range, not Wilder           |
//| smoothing, despite MT5's own docs describing ATR as Wilder-smoothed       |
//| (see Zenith_EA.mq5/Aurelius_EA.mq5's identical fix). arr[] must be         |
//| ascending (oldest-first), same as CopyRates(...,ArraySetAsSeries(...,      |
//| false)) returns.                                                            |
//+------------------------------------------------------------------+
void ComputeWilderATR(const MqlRates &arr[], double &out[], int period)
  {
   int n = ArraySize(arr);
   ArrayResize(out, n);
   for(int i = 0; i < n; i++) out[i] = EMPTY_VALUE;
   if(n <= period) return;
   double tr[]; ArrayResize(tr, n);
   tr[0] = arr[0].high - arr[0].low;
   for(int i = 1; i < n; i++)
      tr[i] = MathMax(arr[i].high - arr[i].low,
              MathMax(MathAbs(arr[i].high - arr[i-1].close), MathAbs(arr[i].low - arr[i-1].close)));
   double seed = 0;
   for(int i = 1; i <= period; i++) seed += tr[i];
   out[period] = seed / period;
   for(int i = period + 1; i < n; i++)
      out[i] = (out[i-1] * (period - 1) + tr[i]) / period;
  }
//+------------------------------------------------------------------+
//| Refreshes g_atrManual from the last CLOSED bar - called once at     |
//| OnInit (initial seed) and once per new bar. A real Opus review        |
//| caught that a short window here (originally 14*3=42 bars) leaves the   |
//| SMA seed carrying real weight - (13/14)^(42-14) is still 13.5%,          |
//| measured up to +20.8% ATR error when a volatility spike (one M5 news      |
//| candle) sits in the seed slice, which directly mis-sizes the stop.         |
//| 500 bars gives (13/14)^(500-14) ~= 0, i.e. a genuinely converged Wilder     |
//| value, not just a seeded one - cheap either way (once per bar).             |
//+------------------------------------------------------------------+
void UpdateATRManual()
  {
   MqlRates arr[]; ArraySetAsSeries(arr, false);
   int got = CopyRates(_Symbol, PERIOD_CURRENT, 1, 500, arr);
   if(got < 14 + 2) return;   // leave g_atrManual at its previous value
   double out[]; ComputeWilderATR(arr, out, 14);
   double last = out[ArraySize(out) - 1];
   if(last != EMPTY_VALUE && last > 0.0) g_atrManual = last;
  }
//+------------------------------------------------------------------+
bool GetATR(double &out)
  {
   out = g_atrManual;
   return(out > 0.0);
  }
//+------------------------------------------------------------------+
bool Aligned(const int shift, const bool isBuy)
  {
   double m21, m50, m150, m600, m2400, atr;
   // GetATR() is always the last-closed-bar value (g_atrManual, refreshed
   // once per new bar), regardless of shift - fine since every call site
   // in this file passes shift=1, same bar GetATR() already means.
   if(!MA(h21,shift,m21) || !MA(h50,shift,m50) || !MA(h150,shift,m150) ||
      !MA(h600,shift,m600) || !MA(h2400,shift,m2400) || !GetATR(atr)) return(false);
   double c = iClose(_Symbol, PERIOD_CURRENT, shift);
   if(c <= 0.0) return(false);
   // ALIGN_MID: 21>50>150>600 + price vs the 2400 (matches Aurelius's own validated default)
   if(isBuy)
     {
      if(!(c > m2400)) return(false);
      return(m21 > m50 && m50 > m150 && m150 > m600);
     }
   if(!(c < m2400)) return(false);
   return(m21 < m50 && m50 < m150 && m150 < m600);
  }
//+------------------------------------------------------------------+
double SlopeATR(const bool isBuy)
  {
   double now, then, atr;
   if(!MA(h50, 1, now) || !MA(h50, 1 + InpSlopeBars, then) || !GetATR(atr) || atr <= 0.0) return(0.0);
   double sl = (now - then) / atr;
   return(isBuy ? sl : -sl);
  }
//+------------------------------------------------------------------+
int CrissCross()
  {
   int n = 0;
   for(int j = 1; j <= InpCrossWindow; j++)
     {
      double a1,b1,a2,b2;
      if(!MA(h21,j,a1) || !MA(h50,j,b1) || !MA(h21,j+1,a2) || !MA(h50,j+1,b2)) return(999);
      if((a1 > b1) != (a2 > b2)) n++;
     }
   return(n);
  }
//+------------------------------------------------------------------+
bool PullbackOK(const bool isBuy)
  {
   double atr;
   if(!GetATR(atr) || atr <= 0.0) return(false);
   double tol = atr * InpPullbackTolATR;
   double ln;
   if(!MA(h50, 1, ln)) return(false);
   double c = iClose(_Symbol, PERIOD_CURRENT, 1);
   if(isBuy  && c <= ln) return(false);
   if(!isBuy && c >= ln) return(false);
   for(int j = 1; j <= InpPullbackBars; j++)
     {
      double lj;
      if(!MA(h50, j, lj)) return(false);
      if(isBuy  && iLow(_Symbol, PERIOD_CURRENT, j)  <= lj + tol) return(true);
      if(!isBuy && iHigh(_Symbol, PERIOD_CURRENT, j) >= lj - tol) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
double VolumeRatio()
  {
   long v[];
   ArraySetAsSeries(v, true);
   int need = InpVolAvgBars + 2;
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, 1, need, v) < need) return(-1.0);
   double sum = 0.0;
   for(int i = 1; i <= InpVolAvgBars; i++) sum += (double)v[i];
   double avg = sum / InpVolAvgBars;
   if(avg <= 0.0) return(-1.0);
   return((double)v[0] / avg);
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| The previous N completed days' high / low. v2.12 lifted this loop   |
//| verbatim out of SRDistanceATR() below - no behaviour change, the    |
//| bounds, the shift-1 start and the "any unreadable day fails the     |
//| whole read" rule are all exactly as they were. Extracted rather     |
//| than duplicated on purpose: UpdateLevelLines() now DRAWS these two  |
//| levels, and a second copy of the loop could silently drift from     |
//| the one the entry filter is actually tested against.                |
//+------------------------------------------------------------------+
bool SRLevels(double &hi, double &lo)
  {
   int nDays = MathMax(1, InpSRDays);
   hi = -DBL_MAX; lo = DBL_MAX;
   for(int i = 1; i <= nDays; i++)
     {
      double dh = iHigh(_Symbol, PERIOD_D1, i);
      double dl = iLow(_Symbol, PERIOD_D1, i);
      if(dh <= 0.0 || dl <= 0.0) return(false);
      if(dh > hi) hi = dh;
      if(dl < lo) lo = dl;
     }
   return(true);
  }
//+------------------------------------------------------------------+
double SRDistanceATR(const bool isBuy, const double atr)
  {
   if(atr <= 0.0) return(-1.0);
   double hi, lo;
   if(!SRLevels(hi, lo)) return(-1.0);
   double c = iClose(_Symbol, PERIOD_CURRENT, 1);
   return((isBuy ? MathAbs(hi - c) : MathAbs(c - lo)) / atr);
  }
//+------------------------------------------------------------------+
bool IsFridayCutoff(const datetime t, const int hour)
  {
   MqlDateTime dt; TimeToStruct(t, dt);
   return(dt.day_of_week == 5 && dt.hour >= hour);
  }
//+------------------------------------------------------------------+
//| Deadline-based replacement for the close-side use of IsFridayCutoff   |
//| in ManageOpenPosition() below, for the same reason Zenith_EA.mq5's       |
//| original day-of-week Friday/weekend check turned out to ride 127h in       |
//| real data: a bar-gated, day-of-week==5 check can't fire AT ALL if a          |
//| holiday leaves zero ticks/bars near the cutoff hour, however many days         |
//| that closure ends up running. True once 'now' is at or past the most             |
//| recent Friday InpFridayCloseHour:00 threshold AND the position opened              |
//| before that threshold - regardless of which day of the week the first               |
//| tick back happens to land on. Called every tick, ahead of OnTick's new-bar            |
//| gate - see its call site. IsFridayCutoff itself is unchanged and still used             |
//| for the entry-side no-entry check (a missed exact hour there is harmless -               |
//| worst case one extra entry near the boundary, unlike the close side).                       |
//+------------------------------------------------------------------+
int DSTGapHourAdjustment(datetime now);   // forward declaration - defined below, after the holiday-calendar
                                           // date-arithmetic helpers it depends on; see its own header
bool WeekendStillOpen(datetime now, datetime openTime)
  {
   MqlDateTime t; TimeToStruct(now, t);
   int daysSinceFriday = (t.day_of_week - 5 + 7) % 7;   // Fri=0, Sat=1, Sun=2, Mon=3, Tue=4, Wed=5, Thu=6
   datetime friday = now - (datetime)daysSinceFriday * 86400;
   MqlDateTime f; TimeToStruct(friday, f);
   // DST-gap-week correction (see DSTGapHourAdjustment's own header) -
   // evaluated against `friday`'s own date, not `now`, since that's the
   // date whose true close hour this is meant to represent.
   f.hour = InpFridayCloseHour + DSTGapHourAdjustment(friday); f.min = 0; f.sec = 0;
   datetime deadline = StructToTime(f);
   if(deadline > now) deadline -= 7 * 86400;   // today IS Friday but before the close hour - last week's deadline applies
   return(now >= deadline && openTime > 0 && openTime < deadline);
  }
//+------------------------------------------------------------------+
//| US market holiday calendar - same mechanism confirmed live in          |
//| Daybreak_EA.mq5/Zenith_EA.mq5's own real Strategy Tester data: a         |
//| position opened on a holiday can find its session closing far earlier     |
//| than usual, with no active management able to react before the market      |
//| genuinely closes. Blocks new entries on a flagged holiday the same way       |
//| IsFridayCutoff already blocks them late in a normal week. Every date is       |
//| COMPUTED from the current year, not looked up in a hardcoded table - no       |
//| yearly maintenance, works indefinitely.                                        |
//+------------------------------------------------------------------+
void EasterSunday(const int year, int &month, int &day)
  {
   int a = year % 19;
   int b = year / 100;
   int c = year % 100;
   int d = b / 4;
   int e = b % 4;
   int f = (b + 8) / 25;
   int g = (b - f + 1) / 3;
   int h = (19*a + b - d - g + 15) % 30;
   int i = c / 4;
   int k = c % 4;
   int l = (32 + 2*e + 2*i - h - k) % 7;
   int m = (a + 11*h + 22*l) / 451;
   month = (h + l - 7*m + 114) / 31;
   day   = ((h + l - 7*m + 114) % 31) + 1;
  }
//+------------------------------------------------------------------+
//| Both NthWeekdayOfMonth and LastWeekdayOfMonth build their date at         |
//| t.hour=0 (was 12 - fixed after Opus review found this session's own       |
//| DSTGapHourAdjustment() Monday-boundary math, e.g. NthWeekdayOfMonth(...)+   |
//| 86400, landed at Monday 12:00 rather than Monday 00:00 - harmless at the     |
//| gold-trio/Zenith/Daybreak's shipped hour thresholds, which all sit above       |
//| noon, but would silently mis-adjust any hour below 12 on the 4 transition       |
//| Mondays/year if ever configured that low - e.g. exactly the kind of change        |
//| Daybreak_EA.mq5's own header invites for InpSessionHour). ObservedFixedHoliday's   |
//| own t.hour=12 is untouched - IsMarketHoliday only ever compares y/m/d from it,       |
//| so it was never actually affected by this.                                            |
//+------------------------------------------------------------------+
datetime NthWeekdayOfMonth(const int year, const int month, const int weekday, const int n)
  {
   MqlDateTime t; ZeroMemory(t);
   t.year = year; t.mon = month; t.day = 1; t.hour = 0;
   datetime first = StructToTime(t);
   MqlDateTime f; TimeToStruct(first, f);
   int offset = (weekday - f.day_of_week + 7) % 7;
   t.day = 1 + offset + (n - 1) * 7;
   return(StructToTime(t));
  }
//+------------------------------------------------------------------+
datetime LastWeekdayOfMonth(const int year, const int month, const int weekday)
  {
   MqlDateTime t; ZeroMemory(t);
   int nm = month + 1, ny = year;
   if(nm > 12) { nm = 1; ny++; }
   t.year = ny; t.mon = nm; t.day = 1; t.hour = 0;
   datetime lastDay = StructToTime(t) - 86400;   // last day of `month`
   MqlDateTime l; TimeToStruct(lastDay, l);
   int back = (l.day_of_week - weekday + 7) % 7;
   return(lastDay - (datetime)back * 86400);
  }
//+------------------------------------------------------------------+
datetime ObservedFixedHoliday(const int year, const int month, const int day)
  {
   MqlDateTime t; ZeroMemory(t);
   t.year = year; t.mon = month; t.day = day; t.hour = 12;
   datetime d = StructToTime(t);
   MqlDateTime m; TimeToStruct(d, m);
   if(m.day_of_week == 6) return(d - 86400);   // Saturday -> observed Friday
   if(m.day_of_week == 0) return(d + 86400);   // Sunday -> observed Monday
   return(d);
  }
//+------------------------------------------------------------------+
bool IsMarketHoliday(datetime now)
  {
   MqlDateTime m; TimeToStruct(now, m);
   int year = m.year;
   datetime dates[10];
   int n = 0;
   dates[n++] = ObservedFixedHoliday(year, 1, 1);        // New Year's Day
   dates[n++] = NthWeekdayOfMonth(year, 1, 1, 3);         // MLK Day: 3rd Monday of January
   dates[n++] = NthWeekdayOfMonth(year, 2, 1, 3);         // Presidents Day: 3rd Monday of February
   int em, ed; EasterSunday(year, em, ed);
   MqlDateTime e; ZeroMemory(e); e.year = year; e.mon = em; e.day = ed; e.hour = 12;
   dates[n++] = StructToTime(e) - 2 * 86400;              // Good Friday
   dates[n++] = LastWeekdayOfMonth(year, 5, 1);           // Memorial Day: last Monday of May
   dates[n++] = ObservedFixedHoliday(year, 6, 19);        // Juneteenth
   dates[n++] = ObservedFixedHoliday(year, 7, 4);         // Independence Day
   dates[n++] = NthWeekdayOfMonth(year, 9, 1, 1);         // Labor Day: 1st Monday of September
   dates[n++] = NthWeekdayOfMonth(year, 11, 4, 4);        // Thanksgiving: 4th Thursday of November
   dates[n++] = ObservedFixedHoliday(year, 12, 25);       // Christmas Day

   for(int i = 0; i < n; i++)
     {
      MqlDateTime h; TimeToStruct(dates[i], h);
      if(h.year == m.year && h.mon == m.mon && h.day == m.day) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
//| Real GOLD# M5 price data (2023-2026, XM Global) shows this broker's  |
//| server clock follows EU DST dates while gold's true session timing     |
//| follows US DST dates - confirmed directly from the daily first-bar-      |
//| of-day time, which shifts by exactly 60 minutes on the Monday after       |
//| each transition, twice a year, with no exceptions across 4 years:          |
//|   Spring: -60min the Monday after the 2nd Sunday of March (US DST         |
//|   start), +60min back to normal the Monday after the last Sunday of        |
//|   March (EU/broker DST start) - a ~2-week gap.                              |
//|   Autumn: -60min the Monday after the last Sunday of October (EU/broker      |
//|   DST end), +60min back to normal the Monday after the 1st Sunday of          |
//|   November (US DST end) - a ~1-week gap.                                       |
//| During either gap, true session events read 1 SERVER-CLOCK HOUR EARLIER          |
//| than their normal mapping - so a fixed-hour threshold needs to be                  |
//| evaluated 1 hour earlier to actually catch the same real event. Returns             |
//| -1 during a gap week, 0 otherwise - ADD this to a configured hour before             |
//| comparing against the clock. Both the US and EU/UK transition rules are               |
//| permanent, legally fixed rules (not looked up in a table), so - like                   |
//| IsMarketHoliday - this needs no yearly maintenance.                                      |
//+------------------------------------------------------------------+
int DSTGapHourAdjustment(datetime now)
  {
   MqlDateTime t; TimeToStruct(now, t);
   int year = t.year;

   datetime usSpringStart = NthWeekdayOfMonth(year, 3, 0, 2) + 86400;   // Mon after 2nd Sun March (US DST start)
   datetime euSpringStart = LastWeekdayOfMonth(year, 3, 0) + 86400;      // Mon after last Sun March (EU DST start)
   if(now >= usSpringStart && now < euSpringStart) return(-1);

   datetime euAutumnEnd = LastWeekdayOfMonth(year, 10, 0) + 86400;      // Mon after last Sun October (EU DST end)
   datetime usAutumnEnd = NthWeekdayOfMonth(year, 11, 0, 1) + 86400;    // Mon after 1st Sun November (US DST end)
   if(now >= euAutumnEnd && now < usAutumnEnd) return(-1);

   return(0);
  }
//+------------------------------------------------------------------+
void UpdateDayStamp()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime today = StructToTime(dt);
   if(today != g_dayStamp)
     {
      g_dayStamp = today;
      g_myRealizedToday = 0.0;
      g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
     }
  }
//+------------------------------------------------------------------+
//| Same daily-loss circuit breaker as Aurelius_EA.mq5/Ratchet_EA.mq5 -   |
//| off by default (InpMaxDailyLossPct=0), so nothing changes unless it's  |
//| deliberately switched on before going live.                             |
//+------------------------------------------------------------------+
bool DailyLossHit()
  {
   UpdateDayStamp();
   if(InpMaxDailyLossPct <= 0.0) return(false);
   if(g_dayStartEquity <= 0.0) return(false);
   double dd = 100.0 * (g_dayStartEquity - AccountInfoDouble(ACCOUNT_EQUITY))
               / g_dayStartEquity;
   return(dd >= InpMaxDailyLossPct);
  }
//+------------------------------------------------------------------+
//| Same LOT_RISK_PCT sizing as Aurelius_EA.mq5/Ratchet_EA.mq5's LotSize() -  |
//| gold's ATR has moved roughly 5-6x since 2023 while InpLots stayed fixed,   |
//| so a fixed lot now risks far more per trade in dollar terms than it did     |
//| when this system was validated. LOT_FIXED (the existing default, 0.01)      |
//| is unchanged for anyone not opting in.                                       |
//+------------------------------------------------------------------+
double LotSize(const double stopDistance)
  {
   double lots = InpLots;
   if(InpLotMode == LOT_RISK_PCT && stopDistance > 0.0)
     {
      double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickVal > 0.0 && tickSize > 0.0)
        {
         double riskCash = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct / 100.0;
         double lossPerLot = (stopDistance / tickSize) * tickVal;
         if(lossPerLot > 0.0) lots = riskCash / lossPerLot;
        }
     }
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(st > 0.0) lots = MathFloor(lots / st) * st;
   lots = MathMax(mn, MathMin(MathMin(mx, InpMaxLots), lots));
   return(NormalizeDouble(lots, 2));
  }
//+------------------------------------------------------------------+
//| InpFixedTargetUSD was written as a literal PRICE distance, true only  |
//| at exactly InpLots=0.01 on GOLD# (see the header note on this EA's     |
//| exit design) - now that LotSize() can return something other than       |
//| InpLots, this converts the intended DOLLAR target into whatever price    |
//| distance actually produces that dollar profit at the lot size really     |
//| being traded, so InpFixedTargetUSD keeps meaning dollars, not a stale     |
//| price offset, regardless of position size.                                 |
//| CORRECTION (2026-09-06, Opus review): this distance is proportional to       |
//| 1/lots for ANY lots value, not just under LOT_RISK_PCT - it does NOT reduce   |
//| back to the original literal-price-distance behaviour just because           |
//| InpLotMode==LOT_FIXED. It only matches the original validated behaviour at     |
//| exactly lots==0.01 (the shipped InpLots default). Running LOT_FIXED at any      |
//| other InpLots gives a genuinely different reward:risk geometry, not a linear     |
//| rescale of the same trades - confirmed by a real InpLots=0.03 vs 0.01 backtest    |
//| pair where the wider (0.01-lot) target cut win rate from ~27% to ~16% and         |
//| roughly doubled average holding time, because the stop (ATR-based, see stopPx      |
//| in CheckForEntry) is NOT lot-scaled while this target now is. See SESSION_NOTES     |
//| .md item 19. Also true under LOT_RISK_PCT: since lots there is already            |
//| proportional to 1/stopDistance, this makes the reward:risk ratio a CONSTANT       |
//| equal to InpFixedTargetUSD/riskCash regardless of stop distance - at a typical    |
//| small-account InpRiskPct=1% that constant lands far below the ~11.8:1 ratio      |
//| this system is actually validated on, silently trading a different, unvalidated  |
//| system the moment InpLotMode is switched away from LOT_FIXED at InpLots=0.01.    |
//+------------------------------------------------------------------+
double TargetDistance(const double lots)
  {
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(lots <= 0.0)
      return(InpFixedTargetUSD);           // caller already refuses to trade at lots<=0 - dead code, kept as a safe fallback
   if(tickVal <= 0.0 || tickSize <= 0.0)
     {
      // 2026-09-06 (Opus deep-dive review): the old fallback here returned
      // InpFixedTargetUSD as a raw literal price distance, which is only
      // the validated geometry at exactly lots==0.01 (see the header note
      // above this function). A transient SymbolInfoDouble failure at any
      // OTHER lot size used to silently re-introduce the exact "wider
      // target at smaller lots" problem that comment describes - e.g. a
      // $135 target at 0.03 lots instead of the validated $45. Scale by
      // the pure lot ratio instead - no tick value needed, and it holds
      // the same reward:risk geometry the tick-value path would have
      // produced. Logged once so a real symbol-info failure isn't silent.
      PrintFormat("Fulcrum M15 EA: TargetDistance() tick value/size read failed (tickVal=%.5f tickSize=%.5f) - "
                  "falling back to a pure lot-ratio scaling of InpFixedTargetUSD instead of the tick-value path",
                  tickVal, tickSize);
      return(InpFixedTargetUSD * 0.01 / lots);
     }
   return(InpFixedTargetUSD * tickSize / (tickVal * lots));
  }
//+------------------------------------------------------------------+
//| This EA's own floating P&L right now (open positions with this      |
//| magic only) - same "mine, not the whole account" filtering as        |
//| g_myRealizedToday. Same convention as Aurelius_EA.mq5/Ratchet_EA.mq5.  |
//+------------------------------------------------------------------+
double MyFloatingPL()
  {
   double sum = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol ||
         (long)PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      sum += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   return(sum);
  }
//+------------------------------------------------------------------+
void LogClosed(const string reason, const double exitPx, const double profit)
  {
   string fn = "Fulcrum_M15_trades.csv";
   bool exists = FileIsExist(fn, FILE_COMMON);
   int handle = FileOpen(fn, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_SHARE_READ, ',');
   if(handle == INVALID_HANDLE)
     {
      Print("Fulcrum M15 EA: failed to open CSV log, error ", GetLastError());
      return;
     }
   if(!exists)
      FileWrite(handle, "close_time", "dir", "entry", "exit", "profit", "reason");
   FileSeek(handle, 0, SEEK_END);
   FileWrite(handle, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
             (g_posDir > 0 ? "BUY" : "SELL"), DoubleToString(g_entryPx, _Digits),
             DoubleToString(exitPx, _Digits), DoubleToString(profit, 2), reason);
   FileClose(handle);
   PrintFormat("Fulcrum M15 EA: CSV export -> %s\\Files\\%s", TerminalInfoString(TERMINAL_COMMONDATA_PATH), fn);
  }
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                         const MqlTradeRequest &request,
                         const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   ulong ticket = trans.deal;
   if(ticket == 0) return;
   // A just-added deal isn't guaranteed to already be in the selected
   // history window - select it explicitly rather than assume the
   // terminal's cache already covers it (the deal-getters below return 0/
   // empty on an unselected ticket, which would silently skip both the
   // P/L accumulator AND the g_barsSinceClose reset right below it).
   if(!HistoryDealSelect(ticket)) return;
   if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagic) return;
   if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) return;
   if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;

   double dealProfit = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_SWAP)
                        + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   UpdateDayStamp();
   g_myRealizedToday += dealProfit;

   ENUM_DEAL_REASON reason = (ENUM_DEAL_REASON)HistoryDealGetInteger(ticket, DEAL_REASON);
   if(reason != DEAL_REASON_SL && reason != DEAL_REASON_TP) return;
   double exitPx = HistoryDealGetDouble(ticket, DEAL_PRICE);
   LogClosed(reason == DEAL_REASON_SL ? "STOP" : "TARGET", exitPx, dealProfit);
   g_ticket = 0; g_posDir = 0;
   g_barsSinceClose = 0;   // was never reset here - InpCooldownBars was dead on every SL/TP close
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
void CloseCurrentPosition(const string reason)
  {
   if(!PositionSelectByTicket(g_ticket)) { g_ticket = 0; g_posDir = 0; return; }
   double before = PositionGetDouble(POSITION_PROFIT);
   double exitPx = (g_posDir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(trade.PositionClose(g_ticket))
     {
      LogClosed(reason, exitPx, before);
      g_ticket = 0; g_posDir = 0;
      g_barsSinceClose = 0;   // was never reset here either - see OnTradeTransaction
     }
   else
      // 2026-09-06 (Opus deep-dive review): this is the ONLY code path
      // Fulcrum has for a Friday/weekend flatten - a rejected close
      // (requote, off-quotes, market closed) used to fail completely
      // silently here, with no Print at all. WeekendStillOpen() retries on
      // the next tick so this self-heals IF ticks keep arriving - but a
      // gap is exactly the situation where they don't, which is the same
      // exposure item 1's weekend-gap fix exists to prevent. Log it so a
      // failed flatten is at least visible in the Journal instead of
      // silent.
      PrintFormat("Fulcrum M15 EA: %s close FAILED for ticket %I64u, retcode %d (%s) - will retry next tick",
                  reason, g_ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
void CheckForEntry(const datetime bar1Time)
  {
   // 2026-09-06 (Opus deep-dive review): this used to be gated ONLY by the
   // caller (ProcessNewBar's `g_ticket != 0` check), a cached global that
   // can read 0 while a position genuinely exists - on a restart/recompile/
   // input-change with a position open (g_ticket resets to its 0
   // initializer, see the OnInit position-recovery fix below), or if
   // FindOwnPosition() failed to see the position on the tick right after a
   // successful trade.Buy()/Sell() call (async/ECN execution can register
   // the deal before the position, hitting the `else` branch below that
   // sets g_ticket=0 while the trade is actually live). Either way,
   // CheckForEntry() itself had no live check of its own, so a second,
   // concurrent position could be opened - a real risk-doubling bug on a
   // system whose whole edge depends on holding exactly one position at a
   // time (see TargetDistance()'s comment on that assumption). A live scan
   // costs nothing extra here (PositionsTotal() is already O(positions on
   // the account), not O(history)) and closes both routes at once.
   ulong existingTk;
   if(FindOwnPosition(existingTk))
     {
      g_ticket = existingTk;
      // Restore the state ManageOpenPosition()/CloseCurrentPosition() need
      // (g_posDir picks bid/ask for the logged exit price; g_entryPx feeds
      // the panel) - both would otherwise sit at their 0/0.0 initializers
      // after a restart until the position closes, same class of gap as
      // the cross-file OnInit finding above.
      if(PositionSelectByTicket(g_ticket))
        {
         g_posDir  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
         g_entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
        }
      return;
     }
   if(DailyLossHit()) return;
   if(g_barsSinceClose < InpCooldownBars) return;
   if(IsFridayCutoff(TimeCurrent(), InpFridayNoEntryHour + DSTGapHourAdjustment(TimeCurrent()))) return;
   if(IsMarketHoliday(TimeCurrent())) return;

   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadPts > InpMaxSpreadPoints) return;

   bool up = Aligned(1, true);
   bool dn = Aligned(1, false);
   if(!up && !dn) return;
   bool isBuy = up;

   if(CrissCross() > InpMaxCrosses) return;
   double sl = SlopeATR(isBuy);
   if(sl < InpMinSlopeATR || (InpMaxSlopeATR > 0.0 && sl > InpMaxSlopeATR)) return;
   if(!PullbackOK(isBuy)) return;

   double atr;
   if(!GetATR(atr) || atr <= 0.0) return;

   if(InpUseVolume)
     {
      double vr = VolumeRatio();
      if(vr >= 0.0 && vr < InpMinVolRatio) return;
     }
   if(InpUseSRDist)
     {
      double sd = SRDistanceATR(isBuy, atr);
      if(sd >= 0.0 && sd < InpMinSRDistATR) return;
     }

   double ma50;
   if(!MA(h50, 1, ma50)) return;

   double refPx = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double stopPx = isBuy ? ma50 - InpStopBufferATR * atr : ma50 + InpStopBufferATR * atr;
   // the bounce MA must actually sit on the protective side of the fill price
   if(isBuy && stopPx >= refPx) return;
   if(!isBuy && stopPx <= refPx) return;

   //--- OPT-IN minimum stop distance (InpMinStopATR, 0 = off = unchanged v2.12
   //--- behaviour). Applied AFTER the protective-side check above, so it can
   //--- only ever move the stop further away from the fill - it can never
   //--- rescue a geometry that the check just rejected, and it never makes a
   //--- stop tighter. See the input's own comment for the full research note.
   if(InpMinStopATR > 0.0)
     {
      double minDist = InpMinStopATR * atr;
      if(MathAbs(refPx - stopPx) < minDist)
         stopPx = isBuy ? refPx - minDist : refPx + minDist;
     }

   double lots = LotSize(MathAbs(refPx - stopPx));
   if(lots <= 0.0) return;
   double tgtDist = TargetDistance(lots);
   double tgtPx = isBuy ? refPx + tgtDist : refPx - tgtDist;

   bool sent = isBuy
      ? trade.Buy(lots, _Symbol, 0.0, stopPx, tgtPx, InpTradeComment)
      : trade.Sell(lots, _Symbol, 0.0, stopPx, tgtPx, InpTradeComment);
   if(sent)
     {
      ulong tk;
      if(FindOwnPosition(tk) && PositionSelectByTicket(tk))
        {
         g_ticket  = tk;
         g_entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
        }
      else
        {
         g_ticket  = 0;
         g_entryPx = refPx;
        }
      g_posDir = isBuy ? 1 : -1;
      PrintFormat("Fulcrum M15 EA: %s entry @ %.2f, stop %.2f, target %.2f",
                  (isBuy?"BUY":"SELL"), g_entryPx, stopPx, tgtPx);
     }
   else
      Print("Fulcrum M15 EA: order send failed, error ", GetLastError());
  }
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   if(!PositionSelectByTicket(g_ticket))
     {
      g_ticket = 0; g_posDir = 0;
      return;
     }
   //--- weekend flatten now handled tick-level at the top of OnTick (see
   //--- WeekendStillOpen) - IsFridayCutoff here would just be dead weight
   //--- by the time a new bar completes, since the tick-level check
   //--- already caught it.
  }
//+------------------------------------------------------------------+
void ProcessNewBar()
  {
   UpdateATRManual();   // once per new bar - see its own header note
   if(g_barsSinceClose < 100000) g_barsSinceClose++;

   if(g_ticket != 0)
      ManageOpenPosition();
   else
      CheckForEntry(iTime(_Symbol, PERIOD_CURRENT, 1));
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- keep the day boundary fresh every tick, cheap (no history scan) -
   //--- the panel's "today" P/L needs this regardless of position state
   UpdateDayStamp();

   //--- tick-level weekend-flatten backstop, evaluated BEFORE the new-bar
   //--- gate below - a holiday can leave zero ticks/bars near the normal
   //--- Friday cutoff hour, so a bar-gated check never gets a chance to
   //--- fire; this can act on the very first tick available, whenever that
   //--- turns out to be. Same fix as Daybreak_EA.mq5 v1.11/Zenith_EA.mq5/
   //--- Aurelius_EA.mq5 for the identical holiday-session-gap bug class -
   //--- see WeekendStillOpen's own header.
   if(g_ticket != 0 && PositionSelectByTicket(g_ticket))
     {
      if(WeekendStillOpen(TimeCurrent(), (datetime)PositionGetInteger(POSITION_TIME)))
         CloseCurrentPosition("FRIDAY");
     }

   if(g_ticket != 0 && !PositionSelectByTicket(g_ticket))
     {
      // closed since last check (broker SL/TP hit) - OnTradeTransaction
      // already logged it if applicable; reset the cooldown clock either way
      g_ticket = 0; g_posDir = 0; g_barsSinceClose = 0;
     }

   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(bt == g_lastBar)
     {
      //--- between-bar: purely cosmetic, skipped entirely in a non-visual
      //--- Tester run (see header). Throttled to once/second elsewhere so
      //--- it can't redraw twice inside the same simulated instant.
      if(g_skipCosmeticDraws) return;
      static datetime lastPanel = 0;
      if(InpShowPanel && TimeCurrent() != lastPanel)
        {
         lastPanel = TimeCurrent();
         //--- reclaim=false: live numbers only, updated in place - see
         //--- g_panelReclaim's comment for why this is what stops the
         //--- panel from visibly flashing on every one-second refresh.
         DrawPanel(false);
         //--- forcing a full chart redraw on a fixed clock fights the
         //--- user's own scrolling/panning and can itself look like
         //--- flicker even with no object churn behind it (Opus review
         //--- caught this was unconditional) - only force it when a
         //--- position is actually open and the floating P/L needs to
         //--- look live, same guard Aurelius_EA.mq5's OnTimer uses.
         if(g_ticket != 0) ChartRedraw(0);
        }
      return;
     }
   g_lastBar = bt;

   ProcessNewBar();

   //--- MA lines drawn BEFORE the panel, and DrawPanel's default
   //--- reclaim=true means this (and only this) call deletes-and-recreates
   //--- every panel object so they stay the newest (topmost) ones - the one
   //--- point per bar where that's actually needed, since it's the only
   //--- point a new MA line segment was just drawn. See g_panelReclaim's
   //--- comment.
   if(!g_skipCosmeticDraws)
     {
      UpdateMALines();
      UpdateLevelLines();   // v2.12: entry/stop/target/S-R horizontal levels -
                             // same reasoning as UpdateMALines, and for the same
                             // reason it has to come BEFORE DrawPanel()
      DrawPanel();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
//| Dragging the panel background moves the whole panel; resizing the |
//| chart re-centres the wallpaper.                                   |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_pp + "bg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      //--- reposition only - reclaiming mid-drag would be jarring
      if(!g_skipCosmeticDraws) { DrawPanel(false); ChartRedraw(0); }
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      static int lastW = -1, lastH = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lastW || nh != lastH)
        {
         lastW = nw; lastH = nh; g_bgOK = false; g_bgTries = 0;
         if(!g_skipCosmeticDraws) PBackground();
        }
     }
  }
//+------------------------------------------------------------------+
//| Wallpaper / watermark - ported from the family's proven pattern   |
//| (Aurelius/Tailwind): PBackground retries loading the BMP up to 40 |
//| times then gives up quietly; PWatermark is created ONCE (not      |
//| deleted+recreated every draw) so it costs nothing after that.     |
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
     { Print("Fulcrum M15 EA BG: ObjectCreate failed, error ", GetLastError()); return; }

   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0, nm, OBJPROP_BMPFILE, 0, path);
   int err = GetLastError();
   if(!okSet || err != 0)
     {
      if(g_bgTries <= 3)
         PrintFormat("Fulcrum M15 EA BG try %d: failed to load \"%s\" set=%s error=%d"
                     " -> file must be at <data folder>\\MQL5\\Images\\%s",
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
   if(ObjectFind(0, g_pw + "wm") >= 0) ObjectDelete(0, g_pw + "wm");
   PWatermark();
   PrintFormat("Fulcrum M15 EA BG: loaded \"%s\" on try %d", path, g_bgTries);
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
//| Panel primitives - PText/PRect delete+recreate ONLY when           |
//| g_panelReclaim is set (once per new bar), so they become the       |
//| newest (topmost) chart objects at that point; MT5 stacks by        |
//| creation order, not OBJPROP_ZORDER (which only affects click       |
//| priority). Every other call just updates the existing object's     |
//| properties in place - see g_panelReclaim's own comment for why.    |
//+------------------------------------------------------------------+
int EstimateTextWidth(const string s, const int fontSize) { return (int)(StringLen(s)*fontSize*0.62)+2; }

void PText(const string id, const int x, const int y, const string txt,
           const color col, const int size = 0, const bool rightAlign = false,
           const string font = "")
  {
   string nm = g_pp + id;
   //--- an OBJ_LABEL with empty text renders MT5's default "Label" - this
   //--- delete is unconditional (not gated by g_panelReclaim) because it's
   //--- not about stacking, it's a row that genuinely no longer has a value
   //--- and needs to disappear.
   if(txt == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   bool exists = (ObjectFind(0, nm) >= 0);
   //--- MT5 stacks chart objects by CREATION order, not by ZORDER - a trade
   //--- arrow/line, or a new MA line segment, created AFTER the panel
   //--- already exists renders on top and shows through it. Deleting and
   //--- recreating this object (instead of just updating it in place) makes
   //--- it the newest object again - but that's only actually needed once
   //--- per new bar (when a new MA segment was just drawn), gated by
   //--- g_panelReclaim; see its own comment for why churning this every
   //--- draw call caused visible flashing.
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
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, rightAlign ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
  }
//+------------------------------------------------------------------+
void PRect(const string id, const int x, const int y, const int w, const int h,
           const color bg, const color edge, const int border)
  {
   string nm = g_pp + id;
   //--- only the draggable background keeps its object identity across
   //--- draws (recreating it would break an in-progress drag) - everything
   //--- else is deleted and recreated when g_panelReclaim is set, same
   //--- reasoning as PText above, so an MA line segment drawn on a later
   //--- bar can't end up stacked above it. See the "fl" fill rect drawn
   //--- right after "bg" in DrawPanel(), which reclaims the same way and is
   //--- what actually keeps the panel body opaque.
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
//| PRect's own OBJ_RECTANGLE_LABEL border (BORDER_FLAT + OBJPROP_COLOR) |
//| renders unreliably in this terminal build - observed live as only     |
//| two of the four sides actually drawn (top + one side), bottom and      |
//| the other side missing. Rather than depend on that object's built-in    |
//| border at all, this draws an explicit 4-strip frame - one thin filled     |
//| rectangle per edge - immune to the quirk since each strip is just an       |
//| ordinary solid-filled OBJ_RECTANGLE_LABEL, the one thing that already       |
//| renders correctly. Same fix, same helper, as Aurelius_EA.mq5/Ratchet_EA.mq5.|
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
//| A row: status dot, label on the left, value right-aligned.        |
//| state: 1 = pass (green), 0 = fail (red), -1 = neutral (no dot     |
//| colour, informational only).                                      |
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
   PText(id + "d", x + 10, y, CharToString(108), dot, InpPanelSize + 1, false, "Wingdings");
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
//| Live diagnostic snapshot of every entry-gate filter, computed by   |
//| reusing the exact same functions CheckForEntry() calls - so the    |
//| panel can never drift from the real gate. Cheap (a handful of      |
//| CopyBuffer reads); only ever called from DrawPanel(), which is      |
//| itself gated/throttled - see header.                                |
//+------------------------------------------------------------------+
struct GateState
  {
   double c, m21, m50, m150, m600, m2400, atr;
   bool   haveDir, isBuy;
   int    cross;
   bool   okCross;
   double slope;
   bool   okSlope;
   bool   okPullback;
   double volRatio;
   bool   okVol;
   double srDist;
   bool   okSR;
   long   spread;
   bool   okSpread;
   bool   okCooldown;
   bool   okFriday;
  };

void ComputeGate(GateState &g)
  {
   g.c = iClose(_Symbol, PERIOD_CURRENT, 1);
   MA(h21,1,g.m21); MA(h50,1,g.m50); MA(h150,1,g.m150); MA(h600,1,g.m600); MA(h2400,1,g.m2400);
   GetATR(g.atr);

   bool up = Aligned(1, true);
   bool dn = Aligned(1, false);
   g.haveDir = up || dn;
   g.isBuy   = up;

   g.cross   = CrissCross();
   g.okCross = (g.cross <= InpMaxCrosses);

   //--- fallback direction for display purposes only when the alignment
   //--- gate itself is already failing (so slope/pullback rows still show
   //--- something sensible rather than always reading "fail")
   bool dispDir = g.haveDir ? g.isBuy : (g.c >= g.m50);
   g.slope   = SlopeATR(dispDir);
   g.okSlope = (g.slope >= InpMinSlopeATR) && (InpMaxSlopeATR <= 0.0 || g.slope <= InpMaxSlopeATR);

   g.okPullback = PullbackOK(dispDir);

   g.volRatio = VolumeRatio();
   g.okVol    = (!InpUseVolume) || g.volRatio < 0.0 || g.volRatio >= InpMinVolRatio;

   g.srDist = SRDistanceATR(dispDir, g.atr);
   g.okSR   = (!InpUseSRDist) || g.srDist < 0.0 || g.srDist >= InpMinSRDistATR;

   g.spread   = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   g.okSpread = g.spread <= InpMaxSpreadPoints;

   g.okCooldown = g_barsSinceClose >= InpCooldownBars;
   g.okFriday   = !IsFridayCutoff(TimeCurrent(), InpFridayNoEntryHour + DSTGapHourAdjustment(TimeCurrent()));
  }
//+------------------------------------------------------------------+
//--- default argument lives on the forward declaration only (line 293) -
//--- repeating it here too is a hard error in some MQL5/C++-family
//--- compilers, and this pair is the only default-arg forward declaration
//--- anywhere in this repo, so there's no local precedent to lean on.
void DrawPanel(const bool reclaim)
  {
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }

   //--- see g_panelReclaim's own comment: true only reclaims top-of-stack
   //--- (delete+recreate) once per new bar, right after a new MA line
   //--- segment could have buried the panel - everything in between just
   //--- updates the existing objects' text/values in place, so live P&L
   //--- ticking doesn't visibly flash the whole panel.
   g_panelReclaim = reclaim;

   PBackground();
   PWatermark();

   GateState gs;
   ComputeGate(gs);

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;
   int rh  = InpPanelSize + 11;
   int hdr = rh + 14;

   // Height re-derived directly from the literal ty+= sequence below (the
   // same class of bug found and fixed in Daybreak_EA.mq5 earlier this
   // session - a hand-counted row estimate here undersized the frame by
   // ~10px, enough for the ACCOUNT section's last row to render partly
   // outside the panel's own background rectangle):
   //   ROWS = 4 section bands + 4 alignment + 9 gate + 4 position + 3
   //          account = 24 rh-tall rows total. Note: this is 24 ROWS, not
   //          24 "ty += rh" advances - the literal sequence has 23 trailing
   //          ty+= (the very last row, q3, has none - there's nothing after
   //          it to advance for) plus that final row's own height, i.e.
   //          23 + 1 = 24. Re-verified by Opus review (independent re-
   //          derivation) before shipping - don't "fix" this to 23.
   //   GAPS = 7 standalone/bundled 4px gaps (after s1, a4, s2, g9, s3, the
   //          bare "ty += 4" post-position, and s4).
   //--- ROWS bumped 24->25: the ACCOUNT section gained a "today (other)" row
   //--- to match Aurelius_EA.mq5/Ratchet_EA.mq5's panel P&L convention -
   //--- see the ACCOUNT section below.
   const int ROWS = 25, GAPS = 7;
   //--- autofit: shrink the row height until the panel fits the window, so
   //--- it's never cut off on a small screen - same technique as Aurelius.
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int h = hdr + 6 + ROWS * rh + GAPS * 4 + 10;   // +6 = y..ty_start, +10 = bottom padding
   int guard = 0;
   while(h > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     {
      rh--; guard++;
      hdr = rh + 14;
      h = hdr + 6 + ROWS * rh + GAPS * 4 + 10;
     }
   int x = (g_panX >= 0) ? g_panX : InpPanelX;
   int y = (g_panY >= 0) ? g_panY : InpPanelY;

   bool haveLong = (g_ticket != 0 && g_posDir > 0);

   PRect("bg", x, y, w, h, InpPanelBg, InpPanelBg, 0);
   //--- explicit 4-strip frame, not PRect's own unreliable built-in border -
   //--- see PFrame's own comment for why.
   PFrame("bd", x, y, w, h, InpPanelEdge, 2);
   //--- "bg" keeps its object identity across cycles so dragging works,
   //--- which means it can't reclaim top-of-stack the way everything else
   //--- does - an MA line segment drawn on a later bar would otherwise end
   //--- up stacked above it and show through. This opaque fill sits right
   //--- on top of "bg" and IS recreated every cycle, so it's what actually
   //--- keeps the panel body solid.
   PRect("fl", x + 2, y + 2, w - 4, h - 4, InpPanelBg, InpPanelBg, 0);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);

   int ty = y + 6;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "FULCRUM M15", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 6;

   PSection("s1", x, ty, w, rh, "ALIGNMENT"); ty += rh + 4;
   //--- The "21/50/150/600/2400" in these four labels are the LEG NAMES carried
   //--- over from Fulcrum_EA.mq5 (fast/med/mid/slow/macro), not this file's
   //--- periods - on M15 they hold 30/50/150/200/1200. Same naming convention as
   //--- the InpP* inputs and Aurelius_M15_EA.mq5; deliberately left alone so the
   //--- two EAs' panels stay directly comparable side by side.
   PRow("a1", x, ty, w, "21 vs 50",     gs.m21  > gs.m50  ? "UP" : "DOWN", gs.m21  > gs.m50  ? 1 : 0); ty += rh;
   PRow("a2", x, ty, w, "50 vs 150",    gs.m50  > gs.m150 ? "UP" : "DOWN", gs.m50  > gs.m150 ? 1 : 0); ty += rh;
   PRow("a3", x, ty, w, "150 vs 600",   gs.m150 > gs.m600 ? "UP" : "DOWN", gs.m150 > gs.m600 ? 1 : 0); ty += rh;
   PRow("a4", x, ty, w, "price vs 2400",gs.c > gs.m2400   ? "UP" : "DOWN", gs.c > gs.m2400   ? 1 : 0); ty += rh + 4;

   PSection("s2", x, ty, w, rh, "ENTRY GATE"); ty += rh + 4;
   PRow("g1", x, ty, w, "aligned",      gs.haveDir ? (gs.isBuy?"BUY":"SELL") : "no", gs.haveDir?1:0); ty += rh;
   PRow("g2", x, ty, w, "criss-cross",  (string)gs.cross + "/" + (string)InpMaxCrosses, gs.okCross?1:0); ty += rh;
   PRow("g3", x, ty, w, "slope",        DoubleToString(gs.slope,2) + " ATR", gs.okSlope?1:0); ty += rh;
   PRow("g4", x, ty, w, "pullback",     gs.okPullback ? "yes" : "no", gs.okPullback?1:0); ty += rh;
   PRow("g5", x, ty, w, "volume",       gs.volRatio < 0 ? "n/a" : DoubleToString(gs.volRatio,2)+"x", gs.okVol?1:0); ty += rh;
   PRow("g6", x, ty, w, "S/R distance", gs.srDist < 0 ? "n/a" : DoubleToString(gs.srDist,2)+" ATR", gs.okSR?1:0); ty += rh;
   PRow("g7", x, ty, w, "spread",       (string)gs.spread + " pt", gs.okSpread?1:0); ty += rh;
   PRow("g8", x, ty, w, "cooldown",     gs.okCooldown ? "clear" : (string)(InpCooldownBars-g_barsSinceClose)+" bars", gs.okCooldown?1:0); ty += rh;
   PRow("g9", x, ty, w, "session",      gs.okFriday ? "open" : "Friday cutoff", gs.okFriday?1:0); ty += rh + 4;

   PSection("s3", x, ty, w, rh, "POSITION"); ty += rh + 4;
   if(g_ticket != 0 && PositionSelectByTicket(g_ticket))
     {
      double prof = PositionGetDouble(POSITION_PROFIT);
      PRow("p1", x, ty, w, haveLong?"LONG":"SHORT", DoubleToString(g_entryPx,2), haveLong?1:0); ty += rh;
      PRow("p2", x, ty, w, "stop",   DoubleToString(PositionGetDouble(POSITION_SL),2), -1); ty += rh;
      PRow("p3", x, ty, w, "target", DoubleToString(PositionGetDouble(POSITION_TP),2), -1); ty += rh;
      PRow("p4", x, ty, w, "floating P/L", StringFormat("%+.2f", prof), prof>=0?1:0); ty += rh;
     }
   else
     {
      PRow("p1", x, ty, w, "state", "FLAT", -1); ty += rh;
      PRow("p2", x, ty, w, "lot size", DoubleToString(InpLots,2), -1); ty += rh;
      PRow("p3", x, ty, w, "target / stop buf",
           "$" + DoubleToString(InpFixedTargetUSD,0) + " / " + DoubleToString(InpStopBufferATR,2) + " ATR", -1); ty += rh;
      PRow("p4", x, ty, w, "", "", -1); ty += rh;
     }
   ty += 4;

   //--- "today" is split mine/other because ACCOUNT_EQUITY reflects the
   //--- WHOLE account - if Aurelius/Ratchet or a manual trade shares this
   //--- account, its P&L was previously mixed into this EA's own number
   //--- with no way to tell them apart. Same convention as Aurelius_EA.mq5/
   //--- Ratchet_EA.mq5 - this row used to be realized-only with no floating
   //--- component and no "other" split, inconsistent with its siblings.
   PSection("s4", x, ty, w, rh, "ACCOUNT"); ty += rh + 4;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double dayPL   = (g_dayStartEquity > 0.0) ? eq - g_dayStartEquity : 0.0;
   double myDayPL = g_myRealizedToday + MyFloatingPL();
   double otherPL = dayPL - myDayPL;
   PRow("q1", x, ty, w, "balance", DoubleToString(bal,2), -1); ty += rh;
   PRow("q2", x, ty, w, "equity",  DoubleToString(eq,2), eq>=bal?1:0); ty += rh;
   PRow("q3", x, ty, w, "today (mine)", StringFormat("%+.2f", myDayPL), myDayPL>=0?1:0); ty += rh;
   PRow("q5", x, ty, w, "today (other)", StringFormat("%+.2f", otherPL),
        otherPL == 0.0 ? -1 : (otherPL >= 0 ? 1 : 0));
  }
//+------------------------------------------------------------------+
