//+------------------------------------------------------------------+
//|                                Tailwind_EA.mq5                   |
//|                                                                  |
//|  Band-walk trend continuation EA - executable version of         |
//|  Tailwind_Signals.mq5. Same validated logic, real orders.        |
//|                                                                  |
//|  Entry: InpMinRun consecutive closed bars with close above BOTH  |
//|  the EMA21 and the BB(20) midline (mirror for downtrend) - a     |
//|  fresh crossing of the threshold, computed directly rather than  |
//|  via a rolling counter (equivalent: above[1..MinRun] all true,   |
//|  above[MinRun+1] false - see CheckForEntry()).                   |
//|  Exit: close crosses back through the BB midline, a structural   |
//|  stop (1.5x ATR), or a max-hold timeout.                         |
//|                                                                  |
//|  Runs strictly on CLOSED H4 bars for entry/exit-condition checks |
//|  (no intrabar lookahead). The optional partial-close is checked  |
//|  every tick for responsiveness, since it only ever takes profit  |
//|  off the table, never changes direction or loosens anything.     |
//|                                                                  |
//|  All defaults match Tailwind_Signals.mq5's validated numbers -   |
//|  see that file's header for the full sweep/validation detail:    |
//|  full n=835 PF=1.29 net=$1959, train PF=1.14 net=$473, holdout   |
//|  PF=1.42 net=$1486 (with InpEntryDistATR=0.5, InpSLBuffer_ATR=1.5 |
//|  applied - the genuine loss-count-reduction improvement).        |
//|                                                                  |
//|  InpAvoidOpposing (ON by default - the strongest filter found    |
//|  for this system): full standalone entry+exit replicas of        |
//|  AuRebound's and Slipstream's own validated logic, using NATIVE  |
//|  MT5 indicator handles (iBands/iMA/iStochastic/iATR - fully      |
//|  converged, not a manually-seeded approximation like the         |
//|  indicator version had to use). Fetches a deep window, reverses  |
//|  it to forward-chronological order, and walks it exactly like    |
//|  the validated Tailwind_Signals.mq5 logic (see that file's       |
//|  header) to determine whether either system currently holds an   |
//|  open synthetic position - no dependency on those EAs actually   |
//|  running. Validated there: conflict trades PF~1.00 on BOTH       |
//|  train and holdout (genuinely breakeven, not noise); avoiding    |
//|  them cuts max drawdown $470->$292 (-38%) for $2 of $1959 total  |
//|  profit given up.                                                 |
//|                                                                  |
//|  InpUsePartialClose (OFF by default - a real preference          |
//|  tradeoff, not a free win): closes InpPartialFrac of the         |
//|  position once favorable move reaches InpPartialTriggerATR, lets |
//|  the rest ride to the normal exit. Validated (50%/1.5xATR): win  |
//|  rate 34.7%->47.7%, losing trades -20%, maxdd -9%, net profit    |
//|  -15%. On restart with a position already open from a prior      |
//|  session, partial-close is skipped for that position (can't      |
//|  reliably tell whether it was already applied) - only positions  |
//|  opened by the current running session get it.                  |
//|                                                                  |
//|  InpUseNewsFilter (ON by default): blocks new entries around     |
//|  high-impact USD releases via MQL5's live Economic Calendar -    |
//|  NOT backtestable in the Strategy Tester (calendar history is    |
//|  live-terminal-only per MQL5's own docs), so this is pure risk   |
//|  management, same class as the Friday weekend-gap filter: no     |
//|  backtest P&L claim, just avoiding a well-documented real risk.  |
//|                                                                  |
//|  FIXES (v1.01), both found and fixed in Slipstream_EA.mq5 this    |
//|  session first (same author pattern, same two bugs):              |
//|   - OnTick() drew the wallpaper/watermark/panel unconditionally   |
//|     on every raw tick with no throttle - in "every tick" Strategy |
//|     Tester mode a single bar can contain hundreds of thousands of |
//|     ticks, so this made real-tick runs far slower than necessary. |
//|     Now throttled to once per second of simulated time.           |
//|   - PRow/PSection/DrawPanelBackground updated existing objects in |
//|     place - MT5 stacks chart objects by creation order, not       |
//|     ZORDER, so a trade arrow/line MT5 draws after the panel       |
//|     already exists was rendering on top of it. Now deleted and    |
//|     recreated every draw cycle so the panel stays topmost.        |
//+------------------------------------------------------------------+
//|  v1.02: this EA closed/modified positions by _Symbol, not by ticket -  |
//|  CTrade's symbol-based overloads resolve to WHATEVER position MT5      |
//|  finds on that symbol, with no guarantee it's this EA's own once a      |
//|  second EA (different magic number) holds a position on GOLD# at the     |
//|  same time - exactly how this portfolio runs. A magic-number check        |
//|  earlier in the same function did NOT protect the close/modify/partial-    |
//|  close call itself - each is a separate internal position-select with       |
//|  no magic filter. Added FindOwnPosition() (same pattern already used         |
//|  correctly in AuRebound_EA.mq5) + a g_ticket global, and converted every       |
//|  PositionClose/PositionModify/PositionClosePartial call plus the entry          |
//|  gate and post-fill entry-price capture to use it. No signal/entry-logic          |
//|  changes - this only changes which position gets acted on when multiple            |
//|  EAs share GOLD#.                                                                    |
//+------------------------------------------------------------------+
//|  v1.03: real-tick Strategy Tester runs were still taking hours (vs a few    |
//|  minutes for a sibling EA), despite v1.01's wallpaper/panel throttle fix.     |
//|  Root cause: NewsBlackoutActive() called CalendarValueHistory() - a live-       |
//|  terminal-only API by this file's own header comment - fresh on every            |
//|  single new H4 bar with zero caching. That call is a well-documented slow          |
//|  path in the Strategy Tester. Since the function already "fails open"                |
//|  (returns false/does-not-block) whenever the calendar has nothing usable,              |
//|  and its Tester result was already documented as not meaningful, now skips              |
//|  the call entirely when MQLInfoInteger(MQL_TESTER) - identical backtest                  |
//|  behaviour, dramatically less wall-clock time.                                             |
//+------------------------------------------------------------------+
//|  v1.04: visual standardization pass (Aurelius/Fulcrum/Ratchet/Zenith/Daybreak's         |
//|  shared panel standard, brought to this file for the first time). Nothing here          |
//|  touches signal/entry/exit/risk/news-filter logic.                                        |
//|   - Panel border was a single OBJ_RECTANGLE_LABEL BORDER_FLAT rect - the same             |
//|     unreliable border (only 2 of 4 sides render live) already replaced everywhere         |
//|     else. Ported PRect()/PFrame() from Aurelius_EA.mq5 verbatim: an explicit 4-strip       |
//|     frame plus a drop shadow and an opaque top fill, all drawn from the new                |
//|     InpPanelBg/InpPanelEdge/InpHeaderBg/InpTitleCol/InpSectionCol/InpTextCol/InpValCol/     |
//|     InpOkCol/InpNoCol/InpShadowCol inputs - the same palette values already shipping on     |
//|     every other GOLD EA this session.                                                        |
//|   - InpPanelY 45 -> 30, matching where every sibling EA sits (just below MT5's own              |
//|     symbol/OHLC header bar).                                                                     |
//|   - Added InpPanelDrag + drag-to-move (CHARTEVENT_OBJECT_DRAG on the panel background) -          |
//|     this panel had no drag support at all.                                                        |
//|   - The v1.01 wallpaper/watermark/panel throttle only cut it to once per second of                |
//|     simulated time - real, but partial: a non-visual Strategy Tester pass (no chart               |
//|     anyone can see) was still redrawing the whole panel every simulated second for no             |
//|     reason. Added g_skipCosmeticDraws (the same flag every other EA this session uses)            |
//|     to skip the block entirely when MQLInfoInteger(MQL_TESTER) && !MQL_VISUAL_MODE,                |
//|     matching Aurelius/Fulcrum/Ratchet/Zenith/Daybreak's pattern exactly rather than just           |
//|     the once-per-second half of it.                                                                |
//|   - Added g_panelReclaim (Aurelius/Zenith's pattern): PRect/PText only delete+recreate             |
//|     (to reclaim top-of-stack from a newly-drawn trade tag) when explicitly told to - the           |
//|     per-second live refresh now updates the same objects in place instead of fully                |
//|     repainting the panel every second, which would otherwise visibly flash on a live/demo          |
//|     chart (the exact issue this pattern exists to solve in Aurelius_EA.mq5).                        |
//|   - OnInit() never drew the panel at all - it only appeared once the first tick reached             |
//|     OnTick()'s throttle block, the same "left to depend on the first tick" gap already              |
//|     found and fixed in Fulcrum_EA.mq5 this session. Now drawn directly in OnInit().                  |
//|                                                                                            |
//|  v1.05: Opus review of the fresh full-portfolio backtest round (2026-09-05) found that, as |
//|  GOLD#'s H4 ATR has grown several-fold since 2023, InpRiskPercent sizing now floors below   |
//|  the broker minimum lot on the large majority of trades (93% in 2025, 100% in 2026 in that  |
//|  test) - so this EA is silently risking whatever the SL happens to cost at 0.01 lots, not   |
//|  the configured InpRiskPercent, with no indication in the Journal. Ported the same warning   |
//|  Zenith_EA's ComputeLotSize() already prints in this situation to LotsFromRisk() here.       |
//|  Signal/entry/exit logic untouched.                                                          |
//|                                                                                              |
//|  v1.06 (2026-09-06): indicator visibility. This EA drew NOTHING price-related before          |
//|  (zero OBJ_TREND/OBJ_HLINE/OBJ_RECTANGLE anywhere in the file) - the EMA21 and BB midline      |
//|  it band-walks, and the entry-distance threshold it actually measures against, were all        |
//|  invisible on the chart. Purely additive chart drawing: no signal, entry, exit, risk or        |
//|  position-management logic touched, and every draw call is gated behind g_skipCosmeticDraws     |
//|  so it can never affect a trading decision or slow a non-visual Tester pass.                    |
//|   - EMA21 (hEMA21) and the BB(20) SMA midline (hBBMid) are now drawn natively BY THIS EA as     |
//|     one OBJ_TREND segment per bar, bar[2]->bar[1], using the family's DrawMASegment()/          |
//|     PurgeOldMALines()/BackfillMALines() pattern from Aurelius_EA.mq5. An EA has no plot         |
//|     buffers of its own (only an indicator can set PLOT_LINE_COLOR) and ChartIndicatorAdd()      |
//|     can only show MT5's own auto-assigned colours, so per-bar trend segments are the only       |
//|     way to get a specific colour per line. Values come straight off the SAME handles            |
//|     CheckForEntry() reads - not a re-derived approximation. Deliberately self-contained:        |
//|     no dependency on Tailwind_Signals.mq5 being attached to the chart.                          |
//|   - Added the entry-distance RAILS at mid +/- InpEntryDistATR*ATR - the literal threshold       |
//|     CheckForEntry() tests (`MathAbs(c[i]-mid[i])/a < InpEntryDistATR` rejects), i.e. the        |
//|     real support/resistance zone this system enters beyond. Drawn dotted and dimmer than        |
//|     the midline itself so the derived level never reads as a primary line. Skipped             |
//|     entirely when InpEntryDistATR<=0 (the filter is off, so there is no rail to show).          |
//|   - Colours (InpColEMA21/InpColBBMidLine) match Tailwind_Signals.mq5's own already-shipping     |
//|     plot palette, so the EA's lines look identical to the indicator's either way.               |
//|   - New object prefix TWDL_ (no clash with this file's own TWDEA_, nor with the indicator's     |
//|     TWD_/TWDP_), swept in OnDeinit alongside it, and purged to a rolling InpLineHistoryBars     |
//|     window every bar so a long-running live EA can't accumulate objects forever.                |
//|   - BackfillLines() fills the whole rolling window once from OnInit, so a fresh attach shows    |
//|     real history immediately instead of 1-bar stubs (the gap Aurelius v1.34 closed with         |
//|     BackfillMALines).                                                                            |
//|   - Deliberately NOT drawn: hBandsAR/hStochAR/hEMA50SS/hEMA200SS/hBBMidSS/hStochSS. Those       |
//|     belong to ShadowOpposing()'s internal replicas of AuRebound's and Slipstream's logic,       |
//|     not to Tailwind's own trading decision - putting them on the chart would misrepresent       |
//|     what this EA actually trades on.                                                             |
//+------------------------------------------------------------------+
#property copyright "Tailwind"
#property version   "1.06"

#include <Trade/Trade.mqh>
CTrade trade;

input group "=== Context ==="
input int    InpBBPeriod    = 20;
input int    InpEMA21       = 21;

input group "=== Entry ==="
input int    InpMinRun      = 3;      // consecutive bars above/below BOTH EMA21 and BB midline
input int    InpATRPeriod   = 14;
input bool   InpBlockIndecision = true;
input bool   InpRequireATRExpanding = false;   // OFF by default - optional filter, tested via sweep: PF improves on
                                                // full and holdout with train PF unchanged, but ~34% fewer trades -
                                                // fewer, higher-quality setups. See Tailwind_Signals.mq5 header.
input int    InpATRExpandWindow = 10;          // bars back to compare current ATR against, when the filter above is on
input double InpEntryDistATR = 0.5;   // require close beyond the BB midline by this many ATR before entry -
                                       // validated: cuts losing-trade COUNT (-18%), win rate up on every split
                                       // (no train/holdout disagreement). Set to 0.0 to disable.
input bool   InpAvoidOpposing = true;  // ON by default - strongest validated filter found for this system.
                                        // Standalone - see file header and Tailwind_Signals.mq5 for full detail.

input group "=== Session filter ==="
input bool   InpUseSessionFilter = true;   // Block a specific broker-server hour (validated: hour 12 was the only clear loser on this data)
input int    InpBlockedHour = 12;
input bool   InpBlockFridayClose = true;   // no NEW entries after this hour on Friday - risk management against
                                            // weekend gap risk, not a backtest-measurable performance lever
input int    InpFridayCutoffHour = 16;

input group "=== Exit ==="
input double InpSLBuffer_ATR = 1.5;   // structural stop distance, x ATR at entry - validated local optimum
                                       // (a finer sweep confirmed both tighter and looser make losses/drawdown worse)
input int    InpMaxHoldBars  = 250;
input int    InpCooldown     = 1;
input bool   InpUsePartialClose = false;   // OFF by default - a real preference tradeoff, not a free improvement.
                                            // See file header for the validated tradeoff numbers.
input double InpPartialFrac       = 0.5;   // fraction of the position closed at the trigger
input double InpPartialTriggerATR = 1.5;   // x entryATR favorable move before the partial close fires

input group "=== News Filter ==="
input bool   InpUseNewsFilter     = true;   // Blocks new entries around high-impact USD economic releases
                                             // (NFP, CPI, FOMC, etc.) - the primary drivers of Gold
                                             // volatility. NOT backtestable in the Strategy Tester (MQL5's
                                             // calendar history is live-terminal-only, per MQL5's own docs)
                                             // - this is pure risk management, same class as the Friday
                                             // weekend-gap filter: no backtest P&L claim, just avoiding a
                                             // well-documented real risk (news-driven spread spikes,
                                             // slippage, whipsaws). Fails OPEN on any calendar API error.
input ENUM_CALENDAR_EVENT_IMPORTANCE InpNewsImportance = CALENDAR_IMPORTANCE_HIGH;
input int    InpNewsMinutesBefore = 30;     // block new entries this many minutes BEFORE a matching event
input int    InpNewsMinutesAfter  = 30;     // and this many minutes AFTER it
input string InpNewsCurrency      = "USD";  // Gold's primary driver - blank to widen the filter to all currencies

input group "=== Money management ==="
input bool   InpUseRiskPercent = true;
input double InpRiskPercent    = 1.0;    // % of balance risked per trade (only if InpUseRiskPercent)
input double InpFixedLots      = 0.01;   // used if InpUseRiskPercent = false
input ulong  InpMagic          = 20260102;
input int    InpSlippagePoints = 30;

input group "=== Misc ==="
input bool   InpAllowShorts    = true;
input bool   InpAllowLongs     = true;
input string InpTradeComment   = "Tailwind";

input group "=== Display ==="
input bool   InpShowPanel      = true;
input int    InpPanelDrag      = 1;    // 0 = locked, 1 = draggable - matches Aurelius/Fulcrum/Ratchet/Zenith/Daybreak
input int    InpPanelX         = 12;
input int    InpPanelY         = 30;   // was 45, now matches the family standard (Aurelius/Fulcrum/Ratchet/
                                        // Zenith/Daybreak all sit at 30, just below MT5's own symbol/OHLC header bar)
input int    InpPanelW         = 260;
input int    InpPanelSize      = 8;
input color  InpColBuy         = C'0,150,255';   // neon blue (bullish) - matches Slipstream/AuRebound
input color  InpColSell        = clrWhite;       // neon white (bearish)
input color  InpColExitProfit  = C'0,255,140';   // neon green
input color  InpColExitBEorLoss = C'255,60,120'; // neon red-pink
input bool   InpSetCandleColors = true;
input color  InpCandleUp       = C'0,150,255';
input color  InpCandleDown     = clrWhite;
input color  InpChartBG        = clrBlack;
input color  InpPanelBg        = C'13,17,28';       // panel background - matches the shared family palette
input color  InpHeaderBg       = C'28,36,58';       // section/title band background
input color  InpPanelEdge      = C'0,150,255';      // panel border - neon blue, matches Fulcrum/Ratchet/Zenith/Daybreak
                                                     // (Aurelius alone uses gold as a documented exception)
input color  InpTitleCol       = C'255,196,84';     // title text - gold, matches Aurelius/Zenith
input color  InpSectionCol     = C'214,226,238';    // section headings - silver
input color  InpTextCol        = C'150,166,192';    // row labels
input color  InpValCol         = C'236,242,252';    // row values (neutral state)
input color  InpOkCol          = C'0,230,118';      // row value - good/on state, neon green
input color  InpNoCol          = C'255,61,90';      // row value - bad/off state, hot red
input color  InpShadowCol      = C'6,8,14';         // drop shadow behind the panel

input group "=== Indicator lines (v1.06) ==="
// Cosmetic only - these draw the SAME hEMA21/hBBMid/hATR values CheckForEntry()
// already reads, never a separately-computed copy, and every call site is gated
// behind g_skipCosmeticDraws. Line colours match Tailwind_Signals.mq5's own plot
// palette so the EA's lines and the indicator's read as one system.
input bool   InpShowLines      = true;   // Draw the EMA21 / BB midline / entry rails this EA actually trades
input int    InpLineHistoryBars = 500;   // How many recent bars of line history to keep drawn (bounded, so a
                                          // long-running live EA doesn't accumulate objects forever). 500 H4
                                          // bars is ~3 months.
input color  InpColEMA21       = C'170,0,255';   // EMA21 - electric violet, same as Tailwind_Signals.mq5's plot
input color  InpColBBMidLine   = C'0,255,255';   // BB(20) SMA midline - neon cyan, same as the indicator's plot
input color  InpColEntryRail   = C'120,130,150'; // entry-distance rails at mid +/- InpEntryDistATR*ATR - deliberately
                                                  // dim/dotted: a derived threshold, not a primary line

input group "=== Wallpaper / Watermark ==="
input bool   InpShowWallpaper  = true;
input string InpBackgroundBMP  = "Tailwind_Wallpaper.bmp";   // place in MQL5\Images\
input int    InpBgWidth        = 1290;
input int    InpBgHeight       = 720;
input bool   InpShowWatermark  = true;
input string InpWatermarkText  = "Tailwind";
input bool   InpWaterBottom    = true;
input color  InpWatermarkColor = C'46,38,24';
input int    InpWatermarkSize  = 42;
input string InpWaterFont      = "Arial Black";

// Tailwind's own context indicators
int hEMA21=INVALID_HANDLE, hBBMid=INVALID_HANDLE, hATR=INVALID_HANDLE;
// InpAvoidOpposing shadow-system handles - AuRebound's own validated settings
// (Bollinger 20,2.0 + Stochastic 21,5,5) and Slipstream's own (EMA50/200,
// BB(14), Stochastic 14,3,3). Kept fixed/internal, not exposed as inputs,
// since these are replicas of ANOTHER system's condition, not primary controls.
int hBandsAR=INVALID_HANDLE, hStochAR=INVALID_HANDLE;
int hEMA50SS=INVALID_HANDLE, hEMA200SS=INVALID_HANDLE, hBBMidSS=INVALID_HANDLE, hStochSS=INVALID_HANDLE;

datetime g_lastBarTime = 0;
int    g_cooldownUntilBar = -1;
int    g_barsSeen = 0;

double g_entryPx=0.0, g_entryATR=0.0;
datetime g_entryTime = 0;
bool   g_partialDone = false;
// Found in review: every close/modify/partial-close call in this file used
// to target _Symbol rather than a specific ticket. CTrade's symbol-based
// overloads resolve to WHATEVER position MT5 finds on that symbol - with
// no guarantee it's this EA's own once a second EA (different magic number)
// holds a position on the same symbol at the same time, which is exactly
// how this portfolio is meant to run. A surrounding magic-number check
// earlier in the same function does NOT protect the close/modify call
// itself - it's a separate internal PositionSelect(_Symbol) with no magic
// filter at all. g_ticket + FindOwnPosition() (same pattern AuRebound_EA.mq5
// already uses correctly) replace every symbol-based site below.
ulong  g_ticket = 0;

bool   g_bgOK=false;
int    g_bgTries=0;
string g_prefix = "TWDEA_";
//--- v1.06: per-bar indicator line segments (EMA21 / BB midline / entry rails),
//--- purged to a rolling window - see DrawLineSegment/PurgeOldLines/UpdateLines.
//--- Deliberately NOT a sub-string of g_prefix ("TWDEA_") or of the companion
//--- indicator's TWD_/TWDP_, so ObjectsDeleteAll on any of those can never sweep
//--- these and vice versa - each prefix owns exactly its own objects.
string g_pl     = "TWDL_";
//--- PERFORMANCE: true only in a non-visual Strategy Tester pass (no chart
//--- anyone can see) - same flag/definition as every other EA this session.
//--- Gates the once-per-second wallpaper/watermark/panel refresh in OnTick().
bool   g_skipCosmeticDraws = false;
//--- draggable panel position - matches Aurelius/Zenith. -1 means "not yet
//--- placed"; DrawPanel() seeds it from InpPanelX/InpPanelY on first draw.
int    g_panX = -1, g_panY = -1;
//--- Controls whether PRect/PText delete-and-recreate (to reclaim top-of-
//--- stack - see PRect's own comment) or just update the existing object's
//--- properties in place. True only right after something else could have
//--- buried the panel (a new trade tag) - the once-per-second live refresh
//--- passes false, so it doesn't visibly flash the whole panel the way a
//--- full delete+recreate would every second. Same pattern as
//--- Aurelius_EA.mq5/Zenith_EA.mq5's g_panelReclaim.
bool   g_panelReclaim = true;

int    g_liveTrades=0, g_liveWins=0, g_liveLosses=0;
double g_liveNet=0.0, g_liveGrossWin=0.0, g_liveGrossLoss=0.0;
ulong  g_lastSeenDeal=0;

//+------------------------------------------------------------------+
int OnInit()
  {
   //--- PERFORMANCE: see g_skipCosmeticDraws declaration - true only in a
   //--- non-visual Strategy Tester pass (no chart anyone can see).
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);

   if(InpSetCandleColors)
     {
      ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, InpCandleUp);
      ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, InpCandleDown);
      ChartSetInteger(0, CHART_COLOR_CHART_UP, InpCandleUp);
      ChartSetInteger(0, CHART_COLOR_CHART_DOWN, InpCandleDown);
      ChartSetInteger(0, CHART_COLOR_BACKGROUND, InpChartBG);
      ChartRedraw(0);
     }
   hEMA21 = iMA(_Symbol, PERIOD_CURRENT, InpEMA21, 0, MODE_EMA, PRICE_CLOSE);
   hBBMid = iMA(_Symbol, PERIOD_CURRENT, InpBBPeriod, 0, MODE_SMA, PRICE_CLOSE);
   hATR   = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   hBandsAR  = iBands(_Symbol, PERIOD_CURRENT, 20, 0, 2.0, PRICE_CLOSE);
   hStochAR  = iStochastic(_Symbol, PERIOD_CURRENT, 21, 5, 5, MODE_SMA, STO_LOWHIGH);
   hEMA50SS  = iMA(_Symbol, PERIOD_CURRENT, 50, 0, MODE_EMA, PRICE_CLOSE);
   hEMA200SS = iMA(_Symbol, PERIOD_CURRENT, 200, 0, MODE_EMA, PRICE_CLOSE);
   hBBMidSS  = iMA(_Symbol, PERIOD_CURRENT, 14, 0, MODE_SMA, PRICE_CLOSE);
   hStochSS  = iStochastic(_Symbol, PERIOD_CURRENT, 14, 3, 3, MODE_SMA, STO_LOWHIGH);
   if(hEMA21==INVALID_HANDLE || hBBMid==INVALID_HANDLE || hATR==INVALID_HANDLE ||
      hBandsAR==INVALID_HANDLE || hStochAR==INVALID_HANDLE ||
      hEMA50SS==INVALID_HANDLE || hEMA200SS==INVALID_HANDLE || hBBMidSS==INVALID_HANDLE || hStochSS==INVALID_HANDLE)
     { Print("Tailwind EA: indicator handle creation failed"); return(INIT_FAILED); }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   RestoreStateFromOpenPosition();   // establishes g_ticket via FindOwnPosition() internally
   RebuildLiveStatsFromHistory();
   //--- one-off, cheap - drawn unconditionally even in a non-visual Tester
   //--- pass, same as Aurelius_EA.mq5's own OnInit. g_skipCosmeticDraws only
   //--- gates the REPEATED per-second redraw further down in OnTick().
   if(InpShowWallpaper) DrawWallpaper();
   if(InpShowWatermark) DrawWatermark();
   DrawPanel();   // show something the moment it attaches - was left to depend on the first tick
   //--- v1.06: fill the whole rolling line window immediately, so a fresh
   //--- attach shows real history instead of 1-bar stubs. Cosmetic only -
   //--- skipped in a non-visual Tester pass, where the loop would draw up to
   //--- 4*InpLineHistoryBars objects onto a chart nobody can see.
   if(!g_skipCosmeticDraws && InpShowLines) BackfillLines();
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(hEMA21!=INVALID_HANDLE) IndicatorRelease(hEMA21);
   if(hBBMid!=INVALID_HANDLE) IndicatorRelease(hBBMid);
   if(hATR!=INVALID_HANDLE) IndicatorRelease(hATR);
   if(hBandsAR!=INVALID_HANDLE) IndicatorRelease(hBandsAR);
   if(hStochAR!=INVALID_HANDLE) IndicatorRelease(hStochAR);
   if(hEMA50SS!=INVALID_HANDLE) IndicatorRelease(hEMA50SS);
   if(hEMA200SS!=INVALID_HANDLE) IndicatorRelease(hEMA200SS);
   if(hBBMidSS!=INVALID_HANDLE) IndicatorRelease(hBBMidSS);
   if(hStochSS!=INVALID_HANDLE) IndicatorRelease(hStochSS);
   ObjectsDeleteAll(0, g_prefix);
   ObjectsDeleteAll(0, g_pl);   // v1.06 indicator line segments - own prefix, own sweep
   Comment("");
  }
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   //--- dragging the background moves the whole panel - matches Aurelius/
   //--- Zenith. This panel had no drag support at all before InpPanelDrag.
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_prefix + "Pbg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      DrawPanel(false);   // reposition only - reclaiming mid-drag would be jarring
      ChartRedraw(0);
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      static int lastW=-1, lastH=-1;
      int nw=(int)ChartGetInteger(0,CHART_WIDTH_IN_PIXELS);
      int nh=(int)ChartGetInteger(0,CHART_HEIGHT_IN_PIXELS);
      if(nw!=lastW || nh!=lastH)
        {
         lastW=nw; lastH=nh;
         if(InpShowWallpaper) { g_bgOK=false; g_bgTries=0; DrawWallpaper(); }
         if(InpShowWatermark) DrawWatermark();
         DrawPanel();
         ChartRedraw(0);
        }
     }
  }
//+------------------------------------------------------------------+
void DrawWatermark()
  {
   string nm = g_prefix+"WM";
   if(InpWatermarkText=="") { if(ObjectFind(0,nm)>=0) ObjectDelete(0,nm); return; }
   if(ObjectFind(0,nm)<0) ObjectCreate(0,nm,OBJ_LABEL,0,0,0);
   int cw=(int)ChartGetInteger(0,CHART_WIDTH_IN_PIXELS);
   int ch=(int)ChartGetInteger(0,CHART_HEIGHT_IN_PIXELS);
   if(InpWaterBottom)
     {
      ObjectSetInteger(0,nm,OBJPROP_CORNER,CORNER_RIGHT_LOWER);
      ObjectSetInteger(0,nm,OBJPROP_ANCHOR,ANCHOR_RIGHT_LOWER);
      ObjectSetInteger(0,nm,OBJPROP_XDISTANCE,18);
      ObjectSetInteger(0,nm,OBJPROP_YDISTANCE,18);
     }
   else
     {
      ObjectSetInteger(0,nm,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(0,nm,OBJPROP_ANCHOR,ANCHOR_CENTER);
      ObjectSetInteger(0,nm,OBJPROP_XDISTANCE,cw/2);
      ObjectSetInteger(0,nm,OBJPROP_YDISTANCE,ch/2);
     }
   ObjectSetString(0,nm,OBJPROP_TEXT,InpWatermarkText);
   ObjectSetString(0,nm,OBJPROP_FONT,InpWaterFont);
   ObjectSetInteger(0,nm,OBJPROP_FONTSIZE,InpWatermarkSize);
   ObjectSetInteger(0,nm,OBJPROP_COLOR,InpWatermarkColor);
   ObjectSetInteger(0,nm,OBJPROP_BACK,true);
   ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
  }
//+------------------------------------------------------------------+
void DrawWallpaper()
  {
   string nm = g_prefix+"BMP";
   if(InpBackgroundBMP=="") { if(ObjectFind(0,nm)>=0) ObjectDelete(0,nm); g_bgOK=true; return; }
   if(g_bgOK) return;
   if(g_bgTries>40) return;
   g_bgTries++;
   if(ObjectFind(0,nm)>=0) ObjectDelete(0,nm);
   if(!ObjectCreate(0,nm,OBJ_BITMAP_LABEL,0,0,0))
     { Print("Tailwind EA BG: ObjectCreate failed, error ", GetLastError()); return; }
   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0,nm,OBJPROP_BMPFILE,0,path);
   int err = GetLastError();
   if(!okSet || err!=0)
     {
      if(g_bgTries<=3)
         PrintFormat("Tailwind EA BG try %d: failed to load \"%s\" set=%s error=%d -> file must be at <data folder>\\MQL5\\Images\\%s",
                     g_bgTries, path, (okSet?"true":"false"), err, InpBackgroundBMP);
      ObjectDelete(0,nm);
      return;
     }
   int cw=(int)ChartGetInteger(0,CHART_WIDTH_IN_PIXELS);
   int chh=(int)ChartGetInteger(0,CHART_HEIGHT_IN_PIXELS);
   ObjectSetInteger(0,nm,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,nm,OBJPROP_XDISTANCE, MathMax(0,(cw-InpBgWidth)/2));
   ObjectSetInteger(0,nm,OBJPROP_YDISTANCE, MathMax(0,(chh-InpBgHeight)/2));
   ObjectSetInteger(0,nm,OBJPROP_BACK,true);
   ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
   g_bgOK=true;
   if(ObjectFind(0,g_prefix+"WM")>=0) ObjectDelete(0,g_prefix+"WM");
   if(InpShowWatermark) DrawWatermark();
   PrintFormat("Tailwind EA BG: loaded \"%s\" on try %d", path, g_bgTries);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Panel primitives - ported from Aurelius_EA.mq5. PRect's own              |
//| OBJ_RECTANGLE_LABEL border (BORDER_FLAT + OBJPROP_COLOR) renders          |
//| unreliably live - only 2 of 4 sides observed - so PFrame draws an          |
//| explicit 4-strip frame instead, immune to the quirk since each strip is     |
//| an ordinary solid-filled rectangle, the one thing that already renders      |
//| correctly. Same fix as every sibling EA this session.                        |
//+------------------------------------------------------------------+
void PRect(const string id, const int x, const int y, const int w, const int h,
           const color bg, const color edge, const int border = 1)
  {
   string nm = g_prefix + "P" + id;
   //--- only the draggable bg is grabbable, and it must not be HIDDEN or
   //--- MT5 won't let it be selected/dragged
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
void PFrame(const string id, const int x, const int y, const int w, const int h,
            const color edge, const int thick = 2)
  {
   PRect(id + "ft", x,             y,             w,     thick, edge, edge, 0);   // top
   PRect(id + "fb", x,             y + h - thick, w,     thick, edge, edge, 0);   // bottom
   PRect(id + "fl", x,             y,             thick, h,     edge, edge, 0);   // left
   PRect(id + "fr", x + w - thick, y,             thick, h,     edge, edge, 0);   // right
  }
void PText(const string id, const int x, const int y, const string txt,
           const color col, const int size = 0, const bool rightAlign = false,
           const string font = "")
  {
   string nm = g_prefix + "P" + id;
   if(txt == "") { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   bool exists = (ObjectFind(0, nm) >= 0);
   if(g_panelReclaim && exists) { ObjectDelete(0, nm); exists = false; }
   if(!exists) ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, y);
   ObjectSetString (0, nm, OBJPROP_TEXT, txt);
   ObjectSetString (0, nm, OBJPROP_FONT, font == "" ? "Consolas" : font);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, size > 0 ? size : InpPanelSize);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5001);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
                    rightAlign ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
  }
//--- MT5 stacks chart objects by creation order, not by their ZORDER
//--- property - a trade arrow/line MT5 draws natively when an order fills
//--- is created AFTER the panel already exists, so left alone it renders
//--- on top and the panel text shows through it. PText (above) handles the
//--- reclaim; PRow just calls it for the label/value pair.
void PRow(const string id,const int x,const int y,const int w,const string label,const string val,const int state)
  {
   color c = (state==1) ? InpOkCol : (state==0 ? InpNoCol : InpValCol);
   PText(id + "L", x, y, label, InpTextCol);
   PText(id + "V", x + w - 8, y, val, c, 0, true);
  }
//+------------------------------------------------------------------+
//| Section heading on its own tinted band. isTitle colors the text gold     |
//| (InpTitleCol) instead of silver (InpSectionCol) - used for the single     |
//| top banner row ("s1") only, matching Aurelius/Zenith's title/section split.|
//+------------------------------------------------------------------+
void PSection(const string id,const int x,const int y,const int w,const string title,const bool isTitle=false)
  {
   int rh = InpPanelSize + 11;
   PRect(id + "bar", x - 2, y - 3, w + 4, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x, y, title, isTitle ? InpTitleCol : InpSectionCol,
         InpPanelSize + 1, false, "Consolas Bold");
  }
void DrawTradeTag(const string nm, const datetime t, const double price, const string txt, const color clr, const int anchor)
  {
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetString (0, nm, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
  }
//+------------------------------------------------------------------+
void DrawPanelBackground(int x,int y,int w,int hgt)
  {
   int bx=x-8, by=y-8, bw=w+16, bh=hgt+16;
   //--- frame first, so everything else draws on top of it
   PRect("sh", bx+4, by+4, bw, bh, InpShadowCol, InpShadowCol, 0);
   PRect("bg", bx,   by,   bw, bh, InpPanelBg,   InpPanelBg,   0);
   //--- "bg" keeps its identity across cycles (so dragging works) - "fl" is
   //--- an identical opaque fill drawn on top of it EVERY cycle, so a trade
   //--- tag drawn since the last reclaim can never show through the panel
   //--- body the way it could through "bg" alone.
   PRect("fl", bx+2, by+2, bw-4, bh-4, InpPanelBg, InpPanelBg, 0);
   //--- explicit 4-strip frame, not PRect's own unreliable built-in border -
   //--- see PFrame's own comment; same fix as every sibling EA this session.
   PFrame("bd", bx, by, bw, bh, InpPanelEdge, 2);
  }
//+------------------------------------------------------------------+
//| v1.06 - the EMA21 / BB midline / entry rails, drawn natively by      |
//| this EA.                                                             |
//|                                                                      |
//| An EA has no plot buffers (only an indicator can set PLOT_LINE_COLOR) |
//| and ChartIndicatorAdd() would only ever show MT5's own auto-assigned  |
//| colours, never a specific one per line - so each line is drawn as one |
//| OBJ_TREND segment per bar, bar[2] -> bar[1], exactly the idiom        |
//| Aurelius_EA.mq5's DrawMASegment() already uses for its five MAs and   |
//| VWAP. PurgeOldLines() sweeps anything older than InpLineHistoryBars   |
//| so a long-running live EA doesn't accumulate objects forever.         |
//| Called only from inside a g_skipCosmeticDraws guard, same as every    |
//| other cosmetic draw in this file.                                     |
//+------------------------------------------------------------------+
void DrawLineSegment(const string tag, const datetime tOld, const double vOld,
                     const datetime tNew, const double vNew,
                     const color col, const ENUM_LINE_STYLE style)
  {
   string nm = g_pl + tag + "_" + IntegerToString((long)tNew);
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_TREND, 0, tOld, vOld, tNew, vNew);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);      // keep it out of the Object List/dialog -
                                                        // up to 4*InpLineHistoryBars of these exist
  }
//+------------------------------------------------------------------+
void PurgeOldLines(const datetime latestBarTime)
  {
   datetime cutoff = latestBarTime - (datetime)((long)InpLineHistoryBars * PeriodSeconds(PERIOD_CURRENT));
   for(int k = ObjectsTotal(0, 0, OBJ_TREND) - 1; k >= 0; k--)
     {
      string nm = ObjectName(0, k, 0, OBJ_TREND);
      if(StringFind(nm, g_pl) != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < cutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
//| Draws the two segments (bar 2 -> bar 1) for the bar that just         |
//| closed, plus the entry rails around the midline. Reads the SAME       |
//| hEMA21/hBBMid/hATR handles CheckForEntry() reads - three 2-value      |
//| CopyBuffer calls, so this stays cheap even though it has to fetch     |
//| (unlike AuRebound, Tailwind's entry path doesn't keep a shared        |
//| rolling window this could borrow from).                               |
//|                                                                       |
//| The rails are mid +/- InpEntryDistATR*ATR: literally the level        |
//| CheckForEntry() measures the close against (it rejects when           |
//| MathAbs(c[i]-mid[i])/a < InpEntryDistATR), i.e. the real support/     |
//| resistance zone an entry has to clear. Not drawn at all when the      |
//| filter is switched off - there is no threshold to show then.          |
//+------------------------------------------------------------------+
void UpdateLines()
  {
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, 2);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(tA == 0 || tB == 0) return;

   double e21[], mid[], atrBuf[];
   ArraySetAsSeries(e21, true); ArraySetAsSeries(mid, true); ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(hEMA21, 0, 1, 2, e21)    < 2) return;   // [0]=shift1, [1]=shift2
   if(CopyBuffer(hBBMid, 0, 1, 2, mid)    < 2) return;
   if(CopyBuffer(hATR,   0, 1, 2, atrBuf) < 2) return;

   DrawLineSegment("e21", tA, e21[1], tB, e21[0], InpColEMA21,     STYLE_SOLID);
   DrawLineSegment("mid", tA, mid[1], tB, mid[0], InpColBBMidLine, STYLE_SOLID);

   if(InpEntryDistATR > 0.0 && atrBuf[0] > 0.0 && atrBuf[1] > 0.0)
     {
      double dA = InpEntryDistATR * atrBuf[1], dB = InpEntryDistATR * atrBuf[0];
      DrawLineSegment("rup", tA, mid[1]+dA, tB, mid[0]+dB, InpColEntryRail, STYLE_DOT);
      DrawLineSegment("rlo", tA, mid[1]-dA, tB, mid[0]-dB, InpColEntryRail, STYLE_DOT);
     }

   PurgeOldLines(tB);
  }
//+------------------------------------------------------------------+
//| UpdateLines() only ever draws ONE bar's worth of segment per call,    |
//| so a fresh attach would show 1-bar stubs and take InpLineHistoryBars  |
//| bars (500 H4 bars = ~3 months) to fill in the window the input claims |
//| to be showing - the same gap Aurelius v1.34 closed with               |
//| BackfillMALines(). Called once from OnInit instead, this walks the    |
//| whole rolling window in one pass. Same shift-1-minimum, no-lookahead  |
//| indexing as the live path - the still-forming bar 0 is never touched. |
//+------------------------------------------------------------------+
void BackfillLines()
  {
   //--- copying from shift 1 yields at most Bars-1 elements, and `want` below
   //--- asks for n+2 of them - so n can be at most Bars-3.
   int avail = Bars(_Symbol, PERIOD_CURRENT) - 3;
   int n = MathMin(InpLineHistoryBars, avail);
   if(n < 1) return;

   datetime bt[]; double e21[], mid[], atrBuf[];
   ArraySetAsSeries(bt, true); ArraySetAsSeries(e21, true);
   ArraySetAsSeries(mid, true); ArraySetAsSeries(atrBuf, true);
   int want = n + 2;   // shift 1 .. n+1, so the oldest segment has both endpoints
   if(CopyTime  (_Symbol, PERIOD_CURRENT, 1, want, bt)     < want) return;
   if(CopyBuffer(hEMA21, 0, 1, want, e21)                  < want) return;
   if(CopyBuffer(hBBMid, 0, 1, want, mid)                  < want) return;
   if(CopyBuffer(hATR,   0, 1, want, atrBuf)               < want) return;

   //--- s is a series index relative to shift 1: s+1 is the older bar, s the
   //--- newer one, matching UpdateLines()'s bar2 -> bar1 pairing exactly.
   for(int s = n - 1; s >= 0; s--)
     {
      if(bt[s+1] == 0 || bt[s] == 0) continue;
      //--- a buffer that hasn't warmed up yet at the deep end of the window
      //--- reads back as 0.0 - skip those bars rather than drawing a line
      //--- down to zero.
      if(e21[s] > 0.0 && e21[s+1] > 0.0)
         DrawLineSegment("e21", bt[s+1], e21[s+1], bt[s], e21[s], InpColEMA21, STYLE_SOLID);
      if(mid[s] > 0.0 && mid[s+1] > 0.0)
        {
         DrawLineSegment("mid", bt[s+1], mid[s+1], bt[s], mid[s], InpColBBMidLine, STYLE_SOLID);
         if(InpEntryDistATR > 0.0 && atrBuf[s] > 0.0 && atrBuf[s+1] > 0.0)
           {
            double dA = InpEntryDistATR * atrBuf[s+1], dB = InpEntryDistATR * atrBuf[s];
            DrawLineSegment("rup", bt[s+1], mid[s+1]+dA, bt[s], mid[s]+dB, InpColEntryRail, STYLE_DOT);
            DrawLineSegment("rlo", bt[s+1], mid[s+1]-dA, bt[s], mid[s]-dB, InpColEntryRail, STYLE_DOT);
           }
        }
     }
  }
//+------------------------------------------------------------------+
// Same pattern as AuRebound_EA.mq5's FindOwnPosition() - scoped to BOTH
// symbol and magic, unlike the PositionSelect(_Symbol) calls this replaces
// everywhere in this file.
bool FindOwnPosition(ulong &ticket)
  {
   for(int i=PositionsTotal()-1; i>=0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol && (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic)
        { ticket=tk; return(true); }
     }
   ticket=0;
   return(false);
  }
//+------------------------------------------------------------------+
void RebuildLiveStatsFromHistory()
  {
   g_liveTrades=0; g_liveWins=0; g_liveLosses=0; g_liveNet=0.0; g_liveGrossWin=0.0; g_liveGrossLoss=0.0;
   if(!HistorySelect(0, TimeCurrent())) return;
   int total = HistoryDealsTotal();
   for(int k=0;k<total;k++)
     {
      ulong ticket = HistoryDealGetTicket(k);
      if(ticket==0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagic) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_SWAP) + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      RecordClosedTrade(profit);
      g_lastSeenDeal = ticket;
     }
  }
void RecordClosedTrade(double profit)
  {
   g_liveTrades++;
   g_liveNet += profit;
   if(profit>=0) { g_liveWins++; g_liveGrossWin += profit; }
   else { g_liveLosses++; g_liveGrossLoss += profit; }
  }
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   ulong ticket = trans.deal;
   if(ticket==0 || ticket<=g_lastSeenDeal) return;
   // 2026-09-06 (Opus deep-dive review): a just-added deal isn't guaranteed
   // to already be in the terminal's selected history window - the exact
   // bug already found and fixed in Daybreak_EA.mq5 (item 11), reading deal
   // properties without selecting first, which returns 0/empty on an
   // unselected ticket. Here that made the DEAL_MAGIC check below fail on
   // every broker-side SL/trend-break close, which made InpCooldown
   // completely inert (g_cooldownUntilBar's only write site is below this
   // check) - a stop-out could be re-entered on the very next bar.
   if(!HistoryDealSelect(ticket)) return;
   if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagic) return;
   if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) return;
   if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;
   double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_SWAP) + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   RecordClosedTrade(profit);
   g_lastSeenDeal = ticket;
   // sees every closed/partial deal regardless of cause - a full close resets
   // cooldown; a partial close (DEAL_ENTRY_OUT with the position still open)
   // also lands here but FindOwnPosition below will still find the position,
   // so cooldown only actually matters once OUR OWN position is truly flat -
   // not just whenever the symbol happens to be flat (found in review: the
   // old PositionSelect(_Symbol) check meant this EA's cooldown wouldn't even
   // engage on its own close if another EA still held a GOLD# position).
   if(!FindOwnPosition(g_ticket))
      g_cooldownUntilBar = g_barsSeen + InpCooldown;

   long dealType = HistoryDealGetInteger(ticket, DEAL_TYPE);
   double dealPrice = HistoryDealGetDouble(ticket, DEAL_PRICE);
   datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
   int wasLong = (dealType==DEAL_TYPE_SELL) ? 1 : 0;
   color mvClr = (profit>0)?InpColExitProfit:InpColExitBEorLoss;
   DrawTradeTag(g_prefix+"X"+(string)ticket, dealTime, dealPrice, "◆",
                mvClr, wasLong?ANCHOR_LOWER:ANCHOR_UPPER);

   DrawPanel();
  }
//+------------------------------------------------------------------+
void DeletePositionBlock()
  {
   string ids[] = {"s4bar","s4t","k1L","k1V","k2L","k2V","k3L","k3V","k4L","k4V","k5L","k5V"};
   for(int i=0;i<ArraySize(ids);i++)
     {
      string nm = g_prefix+"P"+ids[i];
      if(ObjectFind(0,nm)>=0) ObjectDelete(0,nm);
     }
  }
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
struct PanelItem
  {
   string id, label, val;
   int    state;
   bool   section;
   int    gapAfter;
  };
#define ADDSEC(_id,_title,_gap) { items[nI].id=_id; items[nI].label=_title; items[nI].val=""; items[nI].state=-1; items[nI].section=true;  items[nI].gapAfter=_gap; nI++; }
#define ADDROW(_id,_lbl,_val,_state,_gap) { items[nI].id=_id; items[nI].label=_lbl; items[nI].val=_val; items[nI].state=_state; items[nI].section=false; items[nI].gapAfter=_gap; nI++; }
void DrawPanel(const bool reclaim = true)
  {
   if(!InpShowPanel) return;
   g_panelReclaim = reclaim;
   int rh=InpPanelSize+11;
   double pf = (g_liveGrossLoss!=0.0) ? g_liveGrossWin/MathAbs(g_liveGrossLoss) : 0.0;
   double avgTrade = (g_liveTrades>0) ? g_liveNet/g_liveTrades : 0.0;
   bool hasPos = (g_ticket!=0) && PositionSelectByTicket(g_ticket);

   PanelItem items[32]; int nI=0;
   ADDSEC("s1","TAILWIND EA [Live]",6)
   ADDROW("r0","position",hasPos?(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"LONG":"SHORT"):"none",
          hasPos?(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:0):-1,0)
   ADDROW("r1","closed trades",(string)g_liveTrades,-1,0)
   ADDROW("r2","win rate",DoubleToString(g_liveTrades>0?100.0*g_liveWins/g_liveTrades:0.0,1)+"%",-1,0)
   ADDROW("r3","profit factor",DoubleToString(pf,2),pf>1.0?1:(pf>0?0:-1),0)
   ADDROW("r4","net",DoubleToString(g_liveNet,2),g_liveNet>=0?1:0,0)
   ADDROW("r5","avg / trade",DoubleToString(avgTrade,3),avgTrade>=0?1:0,6)
   ADDSEC("s2","FILTERS",6)
   ADDROW("g1","blocked hour",InpUseSessionFilter?StringFormat("%02d",InpBlockedHour):"off",InpUseSessionFilter?0:-1,0)
   ADDROW("g2","Fri cutoff",InpBlockFridayClose?StringFormat("%02d:00",InpFridayCutoffHour):"off",InpBlockFridayClose?0:-1,0)
   ADDROW("g3","ATR expanding",InpRequireATRExpanding?"on":"off",InpRequireATRExpanding?1:-1,0)
   ADDROW("g4","entry dist",InpEntryDistATR>0.0?DoubleToString(InpEntryDistATR,2)+"x ATR":"off",InpEntryDistATR>0.0?1:-1,0)
   ADDROW("g5","avoid opposing",InpAvoidOpposing?"on":"off",InpAvoidOpposing?1:-1,0)
   int cdLeft = MathMax(0, g_cooldownUntilBar - g_barsSeen);
   ADDROW("g6","cooldown",cdLeft>0?(string)cdLeft+" bars":"clear",cdLeft>0?0:1,0)
   ADDROW("g7","news filter",InpUseNewsFilter?InpNewsCurrency+" hi-imp":"off",InpUseNewsFilter?1:-1,6)
   ADDSEC("s3","SETTINGS",6)
   ADDROW("h1","BB / EMA21",StringFormat("%d / %d",InpBBPeriod,InpEMA21),-1,0)
   ADDROW("h2","min run",(string)InpMinRun,-1,0)
   ADDROW("h3","SL buffer",DoubleToString(InpSLBuffer_ATR,1)+"x ATR",-1,0)
   ADDROW("h4","max hold",(string)InpMaxHoldBars,-1,0)
   ADDROW("h5","partial close",InpUsePartialClose?DoubleToString(InpPartialFrac*100,0)+"% @ "+DoubleToString(InpPartialTriggerATR,1)+"x ATR":"off",InpUsePartialClose?1:-1,0)
   ADDROW("h6","sizing",InpUseRiskPercent?StringFormat("%.1f%% risk",InpRiskPercent):StringFormat("%.2f lots fixed",InpFixedLots),-1,hasPos?6:0)

   if(hasPos)
     {
      double curSL = PositionGetDouble(POSITION_SL);
      double curPrice = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol,SYMBOL_BID) : SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      int barsHeld = (int)((TimeCurrent()-g_entryTime)/PeriodSeconds(PERIOD_CURRENT));
      ADDSEC("s4","POSITION",6)
      ADDROW("k1","entry",DoubleToString(g_entryPx,_Digits),-1,0)
      ADDROW("k2","stop",curSL>0?DoubleToString(curSL,_Digits):"none",curSL>0?-1:0,0)
      ADDROW("k3","dist to stop",curSL>0?DoubleToString(MathAbs(curPrice-curSL),_Digits):"n/a",-1,0)
      ADDROW("k4","volume",DoubleToString(PositionGetDouble(POSITION_VOLUME),2)+(g_partialDone?" (partial taken)":""),-1,0)
      ADDROW("k5","bars held",(string)barsHeld+" / "+(string)InpMaxHoldBars,-1,0)
     }
   else
      DeletePositionBlock();

   int w=InpPanelW, hgt=20;
   for(int r=0;r<nI;r++)
     {
      int need = items[r].section
                 ? EstimateTextWidth(items[r].label,InpPanelSize+1)+8
                 : EstimateTextWidth(items[r].label,InpPanelSize)+24+EstimateTextWidth(items[r].val,InpPanelSize);
      if(need>w) w=need;
      hgt += rh + items[r].gapAfter;
     }

   // draggable position - matches Aurelius/Zenith. First call seeds it from
   // the inputs; a drag (OnChartEvent, CHARTEVENT_OBJECT_DRAG) updates it
   // from there. Was purely InpPanelX/InpPanelY, no drag support at all.
   if(g_panX < 0) { g_panX = InpPanelX; g_panY = InpPanelY; }
   int x=g_panX, y=g_panY;
   DrawPanelBackground(x,y,w,hgt);
   for(int r=0;r<nI;r++)
     {
      if(items[r].section) PSection(items[r].id,x,y,w,items[r].label,items[r].id=="s1");
      else PRow(items[r].id,x,y,w,items[r].label,items[r].val,items[r].state);
      y += rh + items[r].gapAfter;
     }
  }
//+------------------------------------------------------------------+
// on restart with a position already open, recover entry price/ATR but
// deliberately mark the partial-close as already "done" for that position -
// we can't reliably tell from position state alone whether a partial was
// already taken by a prior session, and double-partialing would incorrectly
// shrink the position further. Only entries opened by THIS running session
// get a genuine fresh partial-close cycle.
void RestoreStateFromOpenPosition()
  {
   if(!FindOwnPosition(g_ticket)) return;
   if(!PositionSelectByTicket(g_ticket)) return;
   g_entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
   g_entryTime = (datetime)PositionGetInteger(POSITION_TIME);
   double atrBuf[];
   ArraySetAsSeries(atrBuf,true);
   if(CopyBuffer(hATR,0,0,1,atrBuf)>0) g_entryATR = atrBuf[0]; else g_entryATR = 0.0;
   g_partialDone = true;
  }
//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t[];
   ArraySetAsSeries(t,true);
   if(CopyTime(_Symbol,PERIOD_CURRENT,0,1,t)<=0) return(false);
   if(t[0]==g_lastBarTime) return(false);
   g_lastBarTime = t[0];
   g_barsSeen++;
   return(true);
  }
//+------------------------------------------------------------------+
bool IsIndecisionCandle(const double o,const double h,const double l,const double c)
  {
   double rng = h-l;
   if(rng<=0) return(false);
   double body = MathAbs(c-o);
   double upperWick = h - MathMax(o,c);
   double lowerWick = MathMin(o,c) - l;
   return((body/rng) < 0.35 && upperWick > 0.2*rng && lowerWick > 0.2*rng);
  }
//+------------------------------------------------------------------+
double MinStopDistance()
  {
   double stopLevelPts   = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double freezeLevelPts = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double minDist = MathMax(MathMax(stopLevelPts, freezeLevelPts), 0) * _Point;
   minDist = MathMax(minDist, (ask-bid)*1.5);
   return(minDist);
  }
//+------------------------------------------------------------------+
double LotsFromRisk(double slDistance)
  {
   if(!InpUseRiskPercent) return(InpFixedLots);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize<=0 || tickValue<=0 || slDistance<=0) return(InpFixedLots);
   double lossPerLot = (slDistance/tickSize) * tickValue;
   if(lossPerLot<=0) return(InpFixedLots);
   double lots = riskMoney / lossPerLot;

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot<=0) stepLot = 0.01;
   lots = MathFloor(lots/stepLot)*stepLot;
   // Ported from Zenith_EA's ComputeLotSize(): as GOLD#'s H4 ATR grows over
   // time, the same InpRiskPercent divided by a wider stop distance can floor
   // below the broker minimum - raising to minLot then silently risks more
   // than InpRiskPercent on that trade. Warn instead of failing silently.
   if(InpUseRiskPercent && minLot > 0 && lots < minLot)
      PrintFormat("Tailwind_EA: risk-percent sizing wanted a %.4f lot below the broker minimum (%.4f) - "
                  "raising to the minimum risks more than InpRiskPercent=%.2f%% on this trade",
                  lots, minLot, InpRiskPercent);
   lots = MathMax(minLot, MathMin(maxLot, lots));
   return(lots);
  }
//+------------------------------------------------------------------+
void ReverseSeries(const double &src[], double &dst[], const int n)
  {
   ArrayResize(dst,n);
   for(int i=0;i<n;i++) dst[i]=src[n-1-i];
  }
//+------------------------------------------------------------------+
// --- InpAvoidOpposing: see file header. Fetches a deep window (native,   ---
// --- fully-converged indicator handles - no manual EMA/BB seeding), re- ---
// --- verses it to forward-chronological order, and walks it exactly    ---
// --- like the validated Tailwind_Signals.mq5 shadow logic. Returns true ---
// --- if a synthetic AuRebound or Slipstream position is open AGAINST dir.
bool ShadowOpposing(const int dir)
  {
   int depth=800;
   double sO[],sH[],sL[],sC[],sATR[],sArMid[],sArUp[],sArLo[],sStAR[],sE50[],sE200[],sMidSS[],sStSS[];
   ArraySetAsSeries(sO,true); ArraySetAsSeries(sH,true); ArraySetAsSeries(sL,true); ArraySetAsSeries(sC,true);
   ArraySetAsSeries(sATR,true);
   ArraySetAsSeries(sArMid,true); ArraySetAsSeries(sArUp,true); ArraySetAsSeries(sArLo,true); ArraySetAsSeries(sStAR,true);
   ArraySetAsSeries(sE50,true); ArraySetAsSeries(sE200,true); ArraySetAsSeries(sMidSS,true); ArraySetAsSeries(sStSS,true);

   if(CopyOpen(_Symbol,PERIOD_CURRENT,0,depth,sO)<=0) return(false);
   if(CopyHigh(_Symbol,PERIOD_CURRENT,0,depth,sH)<=0) return(false);
   if(CopyLow(_Symbol,PERIOD_CURRENT,0,depth,sL)<=0) return(false);
   if(CopyClose(_Symbol,PERIOD_CURRENT,0,depth,sC)<=0) return(false);
   if(CopyBuffer(hATR,0,0,depth,sATR)<=0) return(false);
   if(CopyBuffer(hBandsAR,BASE_LINE,0,depth,sArMid)<=0) return(false);
   if(CopyBuffer(hBandsAR,UPPER_BAND,0,depth,sArUp)<=0) return(false);
   if(CopyBuffer(hBandsAR,LOWER_BAND,0,depth,sArLo)<=0) return(false);
   if(CopyBuffer(hStochAR,SIGNAL_LINE,0,depth,sStAR)<=0) return(false);
   if(CopyBuffer(hEMA50SS,0,0,depth,sE50)<=0) return(false);
   if(CopyBuffer(hEMA200SS,0,0,depth,sE200)<=0) return(false);
   if(CopyBuffer(hBBMidSS,0,0,depth,sMidSS)<=0) return(false);
   if(CopyBuffer(hStochSS,SIGNAL_LINE,0,depth,sStSS)<=0) return(false);

   int nAvail=ArraySize(sO);
   nAvail=MathMin(nAvail,MathMin(ArraySize(sH),MathMin(ArraySize(sL),ArraySize(sC))));
   nAvail=MathMin(nAvail,ArraySize(sATR));
   nAvail=MathMin(nAvail,MathMin(ArraySize(sArMid),MathMin(ArraySize(sArUp),ArraySize(sArLo))));
   nAvail=MathMin(nAvail,ArraySize(sStAR));
   nAvail=MathMin(nAvail,MathMin(ArraySize(sE50),MathMin(ArraySize(sE200),ArraySize(sMidSS))));
   nAvail=MathMin(nAvail,ArraySize(sStSS));
   if(nAvail<300) return(false);   // not enough history loaded to trust the shadow state yet

   double o[],h[],l[],c[],a[],arMid[],arUp[],arLo[],stAR[],e50[],e200[],midSS[],stSS[];
   ReverseSeries(sO,o,nAvail); ReverseSeries(sH,h,nAvail); ReverseSeries(sL,l,nAvail); ReverseSeries(sC,c,nAvail);
   ReverseSeries(sATR,a,nAvail);
   ReverseSeries(sArMid,arMid,nAvail); ReverseSeries(sArUp,arUp,nAvail); ReverseSeries(sArLo,arLo,nAvail);
   ReverseSeries(sStAR,stAR,nAvail);
   ReverseSeries(sE50,e50,nAvail); ReverseSeries(sE200,e200,nAvail); ReverseSeries(sMidSS,midSS,nAvail);
   ReverseSeries(sStSS,stSS,nAvail);

   int n=nAvail;
   bool arTurnUp[],arTurnDn[],arNearUpper[],arNearLower[];
   ArrayResize(arTurnUp,n); ArrayResize(arTurnDn,n); ArrayResize(arNearUpper,n); ArrayResize(arNearLower,n);
   for(int i=0;i<n;i++)
     {
      arTurnUp[i]=false; arTurnDn[i]=false; arNearUpper[i]=false; arNearLower[i]=false;
      if(a[i]<=0.0) continue;
      arNearUpper[i] = h[i] >= arUp[i]-0.5*a[i];
      arNearLower[i] = l[i] <= arLo[i]+0.5*a[i];
      if(i>=2 && stAR[i]!=EMPTY_VALUE && stAR[i-1]!=EMPTY_VALUE && stAR[i-2]!=EMPTY_VALUE)
        {
         arTurnUp[i] = (stAR[i]>stAR[i-1]) && (stAR[i-1]<=stAR[i-2]);
         arTurnDn[i] = (stAR[i]<stAR[i-1]) && (stAR[i-1]>=stAR[i-2]);
        }
     }
   bool ssUptrend[],ssDowntrend[],ssNearMid[],ssTurnUp[],ssTurnDn[];
   ArrayResize(ssUptrend,n); ArrayResize(ssDowntrend,n); ArrayResize(ssNearMid,n);
   ArrayResize(ssTurnUp,n); ArrayResize(ssTurnDn,n);
   for(int i=0;i<n;i++)
     {
      ssUptrend[i]=false; ssDowntrend[i]=false; ssNearMid[i]=false; ssTurnUp[i]=false; ssTurnDn[i]=false;
      if(i<10 || a[i]<=0.0) continue;
      bool slopeUp = e50[i] > e50[i-10];
      ssUptrend[i]   = (c[i]>e200[i]) && slopeUp;
      ssDowntrend[i] = (c[i]<e200[i]) && (!slopeUp);
      ssNearMid[i]   = (MathAbs(l[i]-midSS[i])<=1.25*a[i]) || (l[i]<=midSS[i] && h[i]>=midSS[i]);
      if(i>=2 && stSS[i]!=EMPTY_VALUE && stSS[i-1]!=EMPTY_VALUE && stSS[i-2]!=EMPTY_VALUE)
        {
         ssTurnUp[i] = (stSS[i]>stSS[i-1]) && (stSS[i-1]<=stSS[i-2]);
         ssTurnDn[i] = (stSS[i]<stSS[i-1]) && (stSS[i-1]>=stSS[i-2]);
        }
     }

   int last=n-2;

   // --- shadow AuRebound walk (SIGNAL_LINE_TURN, blocked_hour=8, no indecision
   //     block, sl_buffer=0.5xATR capped 1.5xATR, MFE-lock 70%@1.0xATR, max_hold=120, cooldown=2)
   int posAR=0, entryBarAR=-1, posDirAR=0; bool stage2AR=false;
   double entryPxAR=0.0, entrySLAR=0.0, entryATRAR=0.0, bestFavAR=0.0;
   int cooldownUntilAR=-1;
   int dirAR=0;
   for(int i=0;i<=last;i++)
     {
      double av=a[i]; if(av<=0.0) continue;
      dirAR = (posAR!=0) ? posDirAR : 0;
      if(posAR!=0)
        {
         double curFav=(posDirAR>0)?(h[i]-entryPxAR):(entryPxAR-l[i]);
         bestFavAR=MathMax(bestFavAR,curFav);
         if(!stage2AR)
           {
            bool clearedMid=(posDirAR>0)?(c[i]>arMid[i]):(c[i]<arMid[i]);
            if(clearedMid) { stage2AR=true; entrySLAR=entryPxAR; }
           }
         if(bestFavAR>=1.0*entryATRAR)
           {
            double lockPrice=entryPxAR+posDirAR*bestFavAR*0.70;
            entrySLAR=(posDirAR>0)?MathMax(entrySLAR,lockPrice):MathMin(entrySLAR,lockPrice);
           }
         bool hitSL=(posDirAR>0)?(l[i]<=entrySLAR):(h[i]>=entrySLAR);
         bool timedOut=(i-entryBarAR)>=120;
         bool bandExit=false;
         if(stage2AR)
           {
            bool recentOpp=false;
            if(posDirAR>0)
              {
               for(int k=MathMax(entryBarAR,i-3);k<=i;k++) if(h[k]>=arUp[k]-0.5*entryATRAR) { recentOpp=true; break; }
               bandExit = recentOpp && arTurnDn[i];
              }
            else
              {
               for(int k=MathMax(entryBarAR,i-3);k<=i;k++) if(l[k]<=arLo[k]+0.5*entryATRAR) { recentOpp=true; break; }
               bandExit = recentOpp && arTurnUp[i];
              }
           }
         if(hitSL || bandExit || timedOut) { posAR=0; stage2AR=false; bestFavAR=0.0; cooldownUntilAR=i+2; }
        }
      else
        {
         if(i<=cooldownUntilAR) continue;
         bool recentLower=false, recentUpper=false;
         for(int k=MathMax(0,i-3);k<=i;k++) { if(arNearLower[k]) recentLower=true; if(arNearUpper[k]) recentUpper=true; }
         bool longSigAR = recentLower && arTurnUp[i];
         bool shortSigAR = recentUpper && arTurnDn[i];
         MqlDateTime dtk; TimeToStruct(iTime(_Symbol,PERIOD_CURRENT, n-1-i), dtk);
         if(dtk.hour==8) { longSigAR=false; shortSigAR=false; }
         if(longSigAR && shortSigAR) { longSigAR=false; shortSigAR=false; }
         if(longSigAR)
           {
            posAR=1; posDirAR=1; entryBarAR=i; entryPxAR=o[i+1]; entryATRAR=av;
            double extreme=l[i]; for(int k=MathMax(0,i-3);k<=i;k++) extreme=MathMin(extreme,l[k]);
            double slDist=MathMin(MathAbs(entryPxAR-extreme)+0.5*av,1.5*av);
            entrySLAR=entryPxAR-slDist; stage2AR=false; bestFavAR=0.0; dirAR=1;
           }
         else if(shortSigAR)
           {
            posAR=1; posDirAR=-1; entryBarAR=i; entryPxAR=o[i+1]; entryATRAR=av;
            double extreme=h[i]; for(int k=MathMax(0,i-3);k<=i;k++) extreme=MathMax(extreme,h[k]);
            double slDist=MathMin(MathAbs(extreme-entryPxAR)+0.5*av,1.5*av);
            entrySLAR=entryPxAR+slDist; stage2AR=false; bestFavAR=0.0; dirAR=-1;
           }
        }
     }

   // --- shadow Slipstream walk (BB(14)+EMA50/200 trend, touch_tol=1.25xATR,
   //     block_indecision=true, sl_buffer=0.75xATR uncapped, MFE-lock 70%@1.0xATR,
   //     trend-break exit, max_hold=200, cooldown=2, blocked hours 0&12, Fri cutoff 16:00)
   int posSS=0, entryBarSS=-1, posDirSS=0;
   double entryPxSS=0.0, entrySLSS=0.0, entryATRSS=0.0, bestFavSS=0.0;
   int cooldownUntilSS=-1;
   int dirSS=0;
   for(int i=0;i<=last;i++)
     {
      double av=a[i]; if(av<=0.0) continue;
      dirSS = (posSS!=0) ? posDirSS : 0;
      if(posSS!=0)
        {
         double curFav=(posDirSS>0)?(h[i]-entryPxSS):(entryPxSS-l[i]);
         bestFavSS=MathMax(bestFavSS,curFav);
         if(bestFavSS>=1.0*entryATRSS)
           {
            double lockPrice=entryPxSS+posDirSS*bestFavSS*0.70;
            entrySLSS=(posDirSS>0)?MathMax(entrySLSS,lockPrice):MathMin(entrySLSS,lockPrice);
           }
         bool hitSL=(posDirSS>0)?(l[i]<=entrySLSS):(h[i]>=entrySLSS);
         bool trendBreak=(posDirSS>0)?(c[i]<e50[i]):(c[i]>e50[i]);
         bool timedOut=(i-entryBarSS)>=200;
         if(hitSL || trendBreak || timedOut) { posSS=0; bestFavSS=0.0; cooldownUntilSS=i+2; }
        }
      else
        {
         if(i<=cooldownUntilSS) continue;
         bool recentTouch=false;
         for(int k=MathMax(0,i-3);k<=i;k++) if(ssNearMid[k]) { recentTouch=true; break; }
         bool longSigSS  = ssUptrend[i]   && recentTouch && ssTurnUp[i];
         bool shortSigSS = ssDowntrend[i] && recentTouch && ssTurnDn[i];
         if(IsIndecisionCandle(o[i],h[i],l[i],c[i])) { longSigSS=false; shortSigSS=false; }
         MqlDateTime dtk; TimeToStruct(iTime(_Symbol,PERIOD_CURRENT, n-1-i), dtk);
         if(dtk.hour==0 || dtk.hour==12) { longSigSS=false; shortSigSS=false; }
         if(dtk.day_of_week==5 && dtk.hour>=16) { longSigSS=false; shortSigSS=false; }
         if(dtk.day_of_week==6) { longSigSS=false; shortSigSS=false; }
         if(longSigSS && shortSigSS) { longSigSS=false; shortSigSS=false; }
         if(longSigSS)
           {
            posSS=1; posDirSS=1; entryBarSS=i; entryPxSS=o[i+1]; entryATRSS=av;
            double extreme=l[i]; for(int k=MathMax(0,i-3);k<=i;k++) extreme=MathMin(extreme,l[k]);
            entrySLSS=entryPxSS-(MathAbs(entryPxSS-extreme)+0.75*av); bestFavSS=0.0; dirSS=1;
           }
         else if(shortSigSS)
           {
            posSS=1; posDirSS=-1; entryBarSS=i; entryPxSS=o[i+1]; entryATRSS=av;
            double extreme=h[i]; for(int k=MathMax(0,i-3);k<=i;k++) extreme=MathMax(extreme,h[k]);
            entrySLSS=entryPxSS+(MathAbs(extreme-entryPxSS)+0.75*av); bestFavSS=0.0; dirSS=-1;
           }
        }
     }

   return (dirAR==-dir) || (dirSS==-dir);
  }
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   if(g_ticket==0 || !PositionSelectByTicket(g_ticket)) { g_ticket=0; return; }

   long ptype = PositionGetInteger(POSITION_TYPE);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double curPrice = (ptype==POSITION_TYPE_BUY) ? bid : ask;

   //--- optional partial close: only ever takes profit, never changes
   //--- direction or loosens the stop - safe to check every tick
   if(InpUsePartialClose && !g_partialDone && g_entryATR>0)
     {
      double favMove = (ptype==POSITION_TYPE_BUY) ? (curPrice-g_entryPx) : (g_entryPx-curPrice);
      if(favMove >= InpPartialTriggerATR*g_entryATR)
        {
         double vol = PositionGetDouble(POSITION_VOLUME);
         double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP); if(volStep<=0) volStep=0.01;
         double volMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double closeVol = MathFloor((vol*InpPartialFrac)/volStep)*volStep;
         if(closeVol>=volMin && closeVol<vol)
           {
            if(trade.PositionClosePartial(g_ticket, closeVol))
               g_partialDone=true;
            else
               PrintFormat("Tailwind EA: partial close failed, error %d retcode %d", GetLastError(), trade.ResultRetcode());
           }
         else
            g_partialDone=true;   // remaining volume too small to split - don't keep retrying every tick
        }
     }

   //--- midline-break and max-hold checks only need to happen once per closed bar
   if(!IsNewBar()) return;

   double midBuf[];
   ArraySetAsSeries(midBuf,true);
   if(CopyBuffer(hBBMid,0,1,1,midBuf)<=0) return;
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);

   bool midBreak = (ptype==POSITION_TYPE_BUY) ? (c1 < midBuf[0]) : (c1 > midBuf[0]);
   int barsHeld = (int)((TimeCurrent()-g_entryTime)/PeriodSeconds(PERIOD_CURRENT));
   bool timedOut = barsHeld >= InpMaxHoldBars;

   if(midBreak || timedOut)
      trade.PositionClose(g_ticket, InpSlippagePoints);
   // cooldown is set in OnTradeTransaction once the position is confirmed flat,
   // covering both this EA-initiated close and a broker-side SL hit uniformly
  }
//+------------------------------------------------------------------+
// Blocks new entries in a window around high-impact news releases via
// MQL5's live Economic Calendar API. NOT usable in the Strategy Tester
// (MQL5's own calendar history is live-terminal-only) - see InpUseNewsFilter.
// Fails OPEN (does not block) on any API error, so a calendar outage never
// silently halts trading.
bool NewsBlackoutActive()
  {
   if(!InpUseNewsFilter) return(false);
   // Found in review, live user report: CalendarValueHistory() is a live-
   // terminal-only API (this file's own header already says so) - in the
   // Strategy Tester it still gets called fresh on every single new H4 bar
   // with zero caching, and that call is a well-documented slow path when
   // hit repeatedly across a multi-year real-tick run (users have reported
   // multi-hour runs here vs a few minutes for a sibling EA with no such
   // call). Since this file already treats the function as "fails open"
   // (returns false = does not block) whenever the calendar has nothing
   // usable, and the Tester result is already documented as not meaningful,
   // skip the call entirely in the Tester rather than pay its cost only to
   // discard the answer - identical backtest behaviour, dramatically less
   // wall-clock time.
   if(MQLInfoInteger(MQL_TESTER)) return(false);
   datetime now = TimeCurrent();
   datetime from = now - InpNewsMinutesAfter*60;
   datetime to   = now + InpNewsMinutesBefore*60;
   MqlCalendarValue values[];
   if(!CalendarValueHistory(values, from, to, NULL, InpNewsCurrency)) return(false);
   for(int k=0;k<ArraySize(values);k++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[k].event_id, ev)) continue;
      if(ev.importance != InpNewsImportance) continue;
      return(true);
     }
   return(false);
  }
void CheckForEntry()
  {
   // was PositionSelect(_Symbol) - blocked a new entry whenever ANY EA held
   // a GOLD# position, not just this one (found in review). Now scoped to
   // this EA's own tracked ticket, same "one position at a time" intent,
   // just correctly scoped.
   //
   // 2026-09-06 (Opus deep-dive review): that fix has one fail-open gap the
   // old symbol-based gate didn't have - if g_ticket is ever lost while a
   // position is genuinely still open (e.g. FindOwnPosition() missed it on
   // the tick right after a successful trade.Buy()/Sell(), a broker-side
   // latency race), this gate reads g_ticket==0 and lets a second position
   // through, leaving the first one completely unmanaged (no midline-break
   // exit, no MFE-lock, no timeout) until its broker SL hits. Re-sync from
   // a live scan before trusting the cached value.
   if(g_ticket==0) FindOwnPosition(g_ticket);
   if(g_ticket!=0 && PositionSelectByTicket(g_ticket)) return;
   if(g_barsSeen <= g_cooldownUntilBar) return;
   if(NewsBlackoutActive()) return;

   MqlDateTime dt;
   TimeToStruct(iTime(_Symbol,PERIOD_CURRENT,1), dt);
   if(InpUseSessionFilter && dt.hour==InpBlockedHour) return;
   if(InpBlockFridayClose && dt.day_of_week==5 && dt.hour>=InpFridayCutoffHour) return;
   if(InpBlockFridayClose && dt.day_of_week==6) return;

   int depth = MathMax(InpMinRun, InpATRExpandWindow) + 5;
   if(Bars(_Symbol,PERIOD_CURRENT) < depth+20) return;

   double o[],h[],l[],c[],e21[],mid[],atrBuf[];
   ArraySetAsSeries(o,true); ArraySetAsSeries(h,true); ArraySetAsSeries(l,true); ArraySetAsSeries(c,true);
   ArraySetAsSeries(e21,true); ArraySetAsSeries(mid,true); ArraySetAsSeries(atrBuf,true);
   if(CopyOpen(_Symbol,PERIOD_CURRENT,0,depth,o)<=0) return;
   if(CopyHigh(_Symbol,PERIOD_CURRENT,0,depth,h)<=0) return;
   if(CopyLow(_Symbol,PERIOD_CURRENT,0,depth,l)<=0) return;
   if(CopyClose(_Symbol,PERIOD_CURRENT,0,depth,c)<=0) return;
   if(CopyBuffer(hEMA21,0,0,depth,e21)<=0) return;
   if(CopyBuffer(hBBMid,0,0,depth,mid)<=0) return;
   if(CopyBuffer(hATR,0,0,depth,atrBuf)<=0) return;

   int i=1;
   double a = atrBuf[i];
   if(a<=0) return;

   // fresh threshold crossing of InpMinRun, computed directly rather than via
   // a rolling counter: above[1..MinRun] all true AND above[MinRun+1] false
   // is exactly equivalent to "runCount just reached MinRun" (see file header)
   bool longSig=true, shortSig=true;
   for(int k=1;k<=InpMinRun;k++)
     {
      bool above = (c[k]>e21[k]) && (c[k]>mid[k]);
      bool below = (c[k]<e21[k]) && (c[k]<mid[k]);
      if(!above) longSig=false;
      if(!below) shortSig=false;
     }
   if(longSig)
     {
      bool aboveNext = (c[InpMinRun+1]>e21[InpMinRun+1]) && (c[InpMinRun+1]>mid[InpMinRun+1]);
      if(aboveNext) longSig=false;
     }
   if(shortSig)
     {
      bool belowNext = (c[InpMinRun+1]<e21[InpMinRun+1]) && (c[InpMinRun+1]<mid[InpMinRun+1]);
      if(belowNext) shortSig=false;
     }
   if(longSig && shortSig) return;
   if(!longSig && !shortSig) return;

   if(InpBlockIndecision && IsIndecisionCandle(o[i],h[i],l[i],c[i])) { longSig=false; shortSig=false; }

   if(InpRequireATRExpanding && (longSig || shortSig))
     {
      double aRef = atrBuf[i+InpATRExpandWindow];
      if(a<=aRef) { longSig=false; shortSig=false; }
     }

   if(InpEntryDistATR>0.0 && (longSig || shortSig))
     {
      double dist = MathAbs(c[i]-mid[i])/a;
      if(dist<InpEntryDistATR) { longSig=false; shortSig=false; }
     }

   if(!longSig && !shortSig) return;

   if(InpAvoidOpposing)
     {
      if(longSig  && ShadowOpposing(1))  longSig=false;
      if(shortSig && ShadowOpposing(-1)) shortSig=false;
     }
   if(!longSig && !shortSig) return;
   if(longSig && !InpAllowLongs) longSig=false;
   if(shortSig && !InpAllowShorts) shortSig=false;
   if(!longSig && !shortSig) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entryPx = longSig ? ask : bid;
   double slDist = InpSLBuffer_ATR*a;
   if(slDist<=0) return;
   double sl = longSig ? (entryPx - slDist) : (entryPx + slDist);
   double minDist = MinStopDistance();
   if(longSig) sl = MathMin(sl, ask - minDist);
   else        sl = MathMax(sl, bid + minDist);
   double lots = LotsFromRisk(slDist);

   bool ok;
   if(longSig)
      ok = trade.Buy(lots, _Symbol, 0.0, NormalizeDouble(sl,_Digits), 0.0, InpTradeComment);
   else
      ok = trade.Sell(lots, _Symbol, 0.0, NormalizeDouble(sl,_Digits), 0.0, InpTradeComment);

   if(!ok)
      PrintFormat("Tailwind EA: order failed, error %d retcode %d - dir=%s entry=%.5f sl=%.5f bid=%.5f ask=%.5f minDist=%.5f",
                  GetLastError(), trade.ResultRetcode(), longSig?"BUY":"SELL", entryPx, sl, bid, ask, minDist);

   if(ok)
     {
      // was PositionSelect(_Symbol) - could have captured a DIFFERENT EA's
      // entry price if another position existed on GOLD# at this instant
      // (found in review). FindOwnPosition() scopes to symbol+magic.
      if(FindOwnPosition(g_ticket) && PositionSelectByTicket(g_ticket))
         g_entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
      else
         g_entryPx = entryPx;
      g_entryATR = a;
      g_partialDone = false;
      g_entryTime = TimeCurrent();
      double markPrice = longSig ? (l[i]-a*0.5) : (h[i]+a*0.5);
      DrawTradeTag(g_prefix+"E"+(string)g_entryTime, g_entryTime, markPrice,
                   longSig?"▲ BUY":"▼ SELL", longSig?InpColBuy:InpColSell,
                   longSig?ANCHOR_UPPER:ANCHOR_LOWER);
     }
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- wallpaper/watermark/panel are cosmetic only - throttle them to once
   //--- per second of simulated time instead of every raw tick, same fix
   //--- as Slipstream_EA.mq5 this session (identical bug, same author
   //--- pattern): unthrottled, these were making real-tick Strategy Tester
   //--- runs take far longer than necessary. v1.04: that throttle was only
   //--- half the fix - a non-visual Strategy Tester pass (no chart anyone
   //--- can see) was still repainting the panel every simulated second for
   //--- nothing, so this is now skipped entirely there (g_skipCosmeticDraws),
   //--- matching Aurelius/Fulcrum/Ratchet/Zenith/Daybreak's pattern exactly.
   //--- reclaim=false: this is a plain value refresh, not a moment something
   //--- else could have buried the panel - see g_panelReclaim's declaration.
   if(!g_skipCosmeticDraws)
     {
      static datetime lastDraw = 0;
      if(TimeCurrent() != lastDraw)
        {
         lastDraw = TimeCurrent();
         if(InpShowWallpaper) DrawWallpaper();
         if(InpShowWatermark) DrawWatermark();
         DrawPanel(false);
        }
     }
   ManageOpenPosition();
   if(!IsNewBar()) return;
   //--- v1.06: one new segment per line per bar, from the same hEMA21/hBBMid/
   //--- hATR handles CheckForEntry() reads on the line below. Once per H4 bar,
   //--- not per tick - this sits AFTER the IsNewBar() gate deliberately.
   if(!g_skipCosmeticDraws && InpShowLines) UpdateLines();
   CheckForEntry();
  }
//+------------------------------------------------------------------+
