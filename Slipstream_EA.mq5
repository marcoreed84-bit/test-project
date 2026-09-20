//+------------------------------------------------------------------+
//|                                Slipstream_EA.mq5                 |
//|                                                                  |
//|  Trend-continuation pullback EA - executable version of          |
//|  Slipstream_Signals.mq5. Same validated logic, real orders.      |
//|                                                                  |
//|  Entry: uptrend (close>EMA200, EMA50 rising over 10 bars) + price|
//|  pulls back to the SMA14 (BB midline) + Stochastic %D turns      |
//|  (signal-line-turn mode by default, K=14,3,3 - validated best).  |
//|  Mirror for downtrend/short.                                     |
//|                                                                  |
//|  Exit: structural stop -> MFE-lock (locks 70% of best favorable  |
//|  move once price reaches 1x entry-ATR, NO breakeven-snap stage - |
//|  RE-tested with real numbers, not just this comment: an early    |
//|  breakeven trigger goes UNPROFITABLE on train data (PF 0.96, net |
//|  -$53); a clear-midline trigger cuts full net from $1620 to $443.|
//|  Do not add one.) -> trend break (close crosses back through     |
//|  EMA50) -> max-hold timeout (never actually triggers on this     |
//|  data from 50 to 400 bars - SL/trend-break always fire first).   |
//|                                                                  |
//|  Runs strictly on CLOSED H4 bars for signal generation (no       |
//|  intrabar lookahead). MFE-lock is checked every tick for         |
//|  responsiveness, since it only ever tightens the stop, never     |
//|  loosens it or changes direction - safe to evaluate intrabar.    |
//|                                                                  |
//|  Re-validated H4 Gold 2013-2026, 70/30 chronological split, via  |
//|  an independent Python replica of this exact entry/exit logic:   |
//|  full n=554 PF=1.56 net=$1620, train n=394 PF=1.39 net=$632,     |
//|  holdout n=155 PF=1.86 net=$1024. BBPeriod=14/TouchTol=1.25/     |
//|  SLBuffer=0.75 confirmed better than the original 20/1.0/0.5 on  |
//|  BOTH halves via parameter sweep, not just in-sample. Caution:   |
//|  lookback and MFELockFrac both improve monotonically the further |
//|  pushed (no interior peak up to lookback=7, frac=0.9) - classic  |
//|  overfit signature for a strongly trending sample, left as-is    |
//|  rather than chasing the sweep's top number.                     |
//|  Demo-test before sizing up - see project notes for full detail. |
//|                                                                  |
//|  InpRequireConfluence (ON by default): computes AuRebound's and  |
//|  Tailwind's own entry conditions internally (self-fetched price  |
//|  window, own Stochastic(21,5,5) handle) - no dependency on those  |
//|  EAs actually running. Ported from Slipstream_Signals.mq5, same  |
//|  validated numbers - see that file's header for the full detail: |
//|  win rate 65.6%->70.2% train, 73.1%->76.1% holdout; PF 1.36->1.48|
//|  train, 1.84->1.81 holdout (flat, already the strong split);     |
//|  n=554->467, maxdd $132.8->$121.2.                                |
//|                                                                  |
//|  Fixed pre-demo (code review, not yet real-log-confirmed):        |
//|   - CheckForEntry()'s touch-lookback loop read past the end of    |
//|     the copied OHLC arrays (need_bars was undersized) - triggered |
//|     on nearly every bar where the signal bar itself didn't touch  |
//|     the midline. Array size now covers the real max index.        |
//|   - Entry SL and the MFE-lock trailing modify now clamp to the    |
//|     broker's minimum stop distance (stops/freeze level, spread-   |
//|     margin floor) - previously unclamped, the same bug class that |
//|     caused most of AuRebound_EA's invalid-stops failures.         |
//|   - Cooldown now also engages when a position closes via its own  |
//|     broker-side stop (incl. the MFE lock) rather than only on the |
//|     EA's own trend-break/timeout close - matches the indicator,   |
//|     which cooldowns after every exit type uniformly.              |
//|                                                                  |
//|  InpUseNewsFilter (ON by default): blocks new entries around     |
//|  high-impact USD releases via MQL5's live Economic Calendar -    |
//|  NOT backtestable in the Strategy Tester (calendar history is    |
//|  live-terminal-only per MQL5's own docs), so this is pure risk   |
//|  management, same class as the Friday weekend-gap filter: no     |
//|  backtest P&L claim, just avoiding a well-documented real risk.  |
//|                                                                  |
//|  PERFORMANCE FIX: DrawWallpaper/DrawWatermark/DrawPanel ran on    |
//|  every raw tick, unthrottled - each does several ObjectFind/      |
//|  ObjectSet calls, and in "every tick" Strategy Tester mode a      |
//|  single H4 bar can contain hundreds of thousands of ticks. This   |
//|  is why a real-tick Slipstream run over the same span AuRebound   |
//|  covers in ~2 minutes was taking over an hour. Now throttled to   |
//|  once per second of simulated time (same pattern already used in  |
//|  Aurelius_EA.mq5/AuRebound_EA.mq5) - imperceptible to a live      |
//|  trader, but eliminates the redundant per-tick redraw work.       |
//|  ManageOpenPosition() still runs every tick, unchanged - that's   |
//|  real trading logic (the MFE-lock trailing stop), not cosmetic,   |
//|  and intentionally reacts intrabar per the note above.            |
//|                                                                  |
//|  PANEL FIX (v1.02): PRow/PSection/DrawPanelBackground updated an  |
//|  existing object in place - MT5 stacks chart objects by creation  |
//|  order, not ZORDER, so a trade arrow/line MT5 draws after the     |
//|  panel already exists was rendering on top of it, same issue      |
//|  fixed in Aurelius_EA.mq5/Ratchet_EA.mq5 this session. Now         |
//|  deleted and recreated every draw cycle so the panel stays the     |
//|  newest (topmost) object on the chart. Width was already dynamic   |
//|  here and P&L was already magic-filtered (via OnTradeTransaction), |
//|  so neither needed the fix the other two EAs needed.               |
//+------------------------------------------------------------------+
//|  v1.03: this EA closed/modified positions by _Symbol, not by ticket -  |
//|  CTrade's symbol-based overloads resolve to WHATEVER position MT5      |
//|  finds on that symbol, with no guarantee it's this EA's own once a      |
//|  second EA (different magic number) holds a position on GOLD# at the     |
//|  same time - exactly how this portfolio runs. A magic-number check        |
//|  earlier in the same function did NOT protect the close/modify call         |
//|  itself - each is a separate internal position-select with no magic         |
//|  filter. Added FindOwnPosition() (same pattern already used correctly         |
//|  in AuRebound_EA.mq5) + a g_ticket global, and converted every                  |
//|  PositionClose/PositionModify call plus the entry gate and post-fill              |
//|  entry-price capture to use it. No signal/entry-logic changes - this                |
//|  only changes which position gets acted on when multiple EAs share GOLD#.             |
//+------------------------------------------------------------------+
//|  v1.04: real-tick Strategy Tester runs were still taking hours (vs a few    |
//|  minutes for a sibling EA), despite the earlier wallpaper/panel throttle     |
//|  fix. Root cause: NewsBlackoutActive() called CalendarValueHistory() - a       |
//|  live-terminal-only API by this file's own header comment - fresh on every      |
//|  single new H4 bar with zero caching. That call is a well-documented slow         |
//|  path in the Strategy Tester. Since the function already "fails open"               |
//|  (returns false/does-not-block) whenever the calendar has nothing usable,             |
//|  and its Tester result was already documented as not meaningful, now skips             |
//|  the call entirely when MQLInfoInteger(MQL_TESTER) - identical backtest                   |
//|  behaviour, dramatically less wall-clock time.                                              |
//+------------------------------------------------------------------+
//|  v1.05: visual standardization pass (Aurelius/Fulcrum/Ratchet/Zenith/Daybreak's         |
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
//|   - The earlier wallpaper/watermark/panel throttle only cut it to once per second of               |
//|     simulated time - real, but partial: a non-visual Strategy Tester pass (no chart                |
//|     anyone can see) was still redrawing the whole panel every simulated second for no              |
//|     reason. Added g_skipCosmeticDraws (the same flag every other EA this session uses)             |
//|     to skip the block entirely when MQLInfoInteger(MQL_TESTER) && !MQL_VISUAL_MODE,                 |
//|     matching Aurelius/Fulcrum/Ratchet/Zenith/Daybreak's pattern exactly rather than just            |
//|     the once-per-second half of it.                                                                 |
//|   - Added g_panelReclaim (Aurelius/Zenith's pattern): PRect/PText only delete+recreate              |
//|     (to reclaim top-of-stack from a newly-drawn trade tag) when explicitly told to - the            |
//|     per-second live refresh now updates the same objects in place instead of fully                 |
//|     repainting the panel every second, which would otherwise visibly flash on a live/demo           |
//|     chart (the exact issue this pattern exists to solve in Aurelius_EA.mq5).                         |
//|   - OnInit() never drew the panel at all - it only appeared once the first tick reached              |
//|     OnTick()'s throttle block, the same "left to depend on the first tick" gap already               |
//|     found and fixed in Fulcrum_EA.mq5 this session. Now drawn directly in OnInit().                   |
//|                                                                                            |
//|  v1.06: Opus review of the fresh full-portfolio backtest round (2026-09-05) found that, as |
//|  GOLD#'s H4 ATR has grown several-fold since 2023, InpRiskPercent sizing now floors below   |
//|  the broker minimum lot on the large majority of trades (100% in 2025-2026 in that test) -  |
//|  so this EA is silently risking whatever the SL happens to cost at 0.01 lots, not the        |
//|  configured InpRiskPercent, with no indication in the Journal. Ported the same warning       |
//|  Zenith_EA's ComputeLotSize() already prints in this situation to LotsFromRisk() here.       |
//|  Signal/entry/exit logic untouched.                                                          |
//|                                                                                              |
//|  v1.07 (2026-09-06): the midline this system actually trades gets a real indicator handle,    |
//|  and indicator visibility. Two related pieces:                                                |
//|                                                                                               |
//|  1. REAL FIX, independent of any drawing: the BB(InpBBPeriod) "midline" - the pullback        |
//|     target the whole entry rule is built on - had no indicator handle at all. It was          |
//|     hand-rolled in CheckForEntry() as two nested close-summing loops (one for the signal      |
//|     bar, one re-summed from scratch for every InpLookback bar), unlike hEMA50/hEMA200/        |
//|     hStoch/hATR which were already native. Added hBBMid = iMA(..., InpBBPeriod, 0,            |
//|     MODE_SMA, PRICE_CLOSE) next to the other handles, and both loops now read it via          |
//|     CopyBuffer. Same value by construction (an SMA of the last InpBBPeriod closes ending      |
//|     at bar i is exactly what both compute), one MT5-side calculation instead of               |
//|     InpBBPeriod*(1+InpLookback) additions per bar, and the midline is now available to        |
//|     anything else in the file that needs it - which the drawing below does.                    |
//|                                                                                               |
//|  2. Indicator visibility. This EA drew NOTHING price-related before (zero OBJ_TREND/          |
//|     OBJ_HLINE/OBJ_RECTANGLE anywhere in the file), so EMA50, EMA200, the midline and the      |
//|     pullback zone were all invisible. Purely additive chart drawing: no signal, entry,        |
//|     exit, risk or position-management logic touched by this part, and every draw call is      |
//|     gated behind g_skipCosmeticDraws so it can never affect a trading decision.               |
//|      - EMA50 (hEMA50), EMA200 (hEMA200) and the new native midline (hBBMid) are drawn         |
//|        natively BY THIS EA as one OBJ_TREND segment per bar, bar[2]->bar[1], using the        |
//|        family's DrawMASegment()/PurgeOldMALines()/BackfillMALines() pattern from              |
//|        Aurelius_EA.mq5. An EA has no plot buffers of its own (only an indicator can set       |
//|        PLOT_LINE_COLOR) and ChartIndicatorAdd() can only show MT5's own auto-assigned         |
//|        colours, so per-bar trend segments are the only way to get a specific colour per       |
//|        line. Values come straight off the SAME handles CheckForEntry() reads.                  |
//|        Deliberately self-contained: no dependency on Slipstream_Signals.mq5 being attached.   |
//|      - The PULLBACK ZONE rails at mid +/- InpTouchTol*ATR - the literal band                  |
//|        CheckForEntry()'s recentTouch test measures against, i.e. the support/resistance       |
//|        zone this entire system trades. Drawn dotted and dimmer than the midline so the        |
//|        derived level never reads as a primary line.                                            |
//|      - The dynamic swing trendline InpUseTrendlineConfirm already resolves internally         |
//|        (two confirmed swing lows for a long, swing highs for a short) is now emitted as       |
//|        one right-ray OBJ_TREND under a fixed object name, refreshed once per bar. Only        |
//|        drawn when that filter is actually ON - drawing a line the EA isn't consulting         |
//|        would misrepresent what it trades on. TrendlineTouchLongSeries()/ShortSeries()         |
//|        themselves are UNCHANGED; a thin EmitTrendline() wrapper re-resolves the same          |
//|        k1/k2 with the same loop rather than adding an output parameter to a signal            |
//|        function.                                                                               |
//|      - Colours (InpColEMA50Line/InpColEMA200Line/InpColBBMidLine) match                        |
//|        Slipstream_Signals.mq5's own already-shipping plot palette.                             |
//|      - New object prefix SLPL_ (no clash with this file's own SLPEA_, nor with the            |
//|        indicator's SLP_/SLPP_), swept in OnDeinit alongside it, and purged to a rolling       |
//|        InpLineHistoryBars window every bar so a long-running live EA can't accumulate         |
//|        objects forever. BackfillLines() fills the whole window once from OnInit, so a         |
//|        fresh attach shows real history instead of 1-bar stubs (the gap Aurelius v1.34         |
//|        closed with BackfillMALines).                                                           |
//|      - Deliberately NOT drawn: anything from CheckConfluenceDir()/hStochConf. Those are       |
//|        internal replicas of Tailwind's and AuRebound's conditions, not Slipstream's own       |
//|        trading decision - charting them would misrepresent what this EA trades on.            |
//+------------------------------------------------------------------+
#property copyright "Slipstream"
#property version   "1.07"

#include <Trade/Trade.mqh>
CTrade trade;

input group "=== Context ==="
input int    InpBBPeriod       = 14;   // was 20 - validated better on both train and holdout via parameter sweep (see project notes)
input int    InpEMA50          = 50;
input int    InpEMA200         = 200;
input int    InpTrendSlopeBars = 10;

input group "=== Entry ==="
input double InpTouchTol       = 1.25;   // was 1.0 - validated better on both train and holdout
input int    InpATRPeriod      = 14;
input int    InpStochK         = 14;
input int    InpStochD         = 3;
input int    InpStochSlow      = 3;
input bool   InpSignalLineMode = true;   // true=signal-line local turn (validated best). false=cross through 50
input int    InpLookback       = 3;
input bool   InpBlockIndecision = true;
input bool   InpUseTrendlineConfirm = false;   // OFF by default - optional extra filter, tested via sweep: PF improves on
                                                // every split (1.56->1.77 full, 1.39->1.44 train, 1.86->2.31 holdout) but
                                                // trade count drops ~42% (fewer, higher-quality setups, not more profit)
input int    InpSwingLag       = 3;            // bars each side required to confirm a swing high/low (fractal)
input bool   InpRequireConfluence = true;      // ON by default - validated best default. Standalone: does NOT
                                                // require AuRebound or Tailwind to actually be running - computes a
                                                // lightweight internal copy of each one's own entry condition
                                                // (Tailwind's EMA21+BBmid(20) band-walk trend; AuRebound's band-edge
                                                // + Stochastic(21,5,5) turn) off this EA's own price data. See
                                                // Slipstream_Signals.mq5 header for the full validation numbers.
input int    InpConfluenceWindow = 2;          // bars back to check for the other systems' condition being true

input group "=== Exit ==="
input double InpSLBuffer       = 0.75;   // was 0.5 - validated better on both train and holdout via parameter sweep
input int    InpMaxHoldBars    = 200;
input int    InpCooldown       = 2;
input bool   InpUseMFELock     = true;
input double InpMFELockTrigger = 1.0;
input double InpMFELockFrac    = 0.70;

input group "=== Session filter ==="
input bool   InpUseSessionFilter = true;
input int    InpBlockedHour1   = 0;
input int    InpBlockedHour2   = 12;
input bool   InpBlockFridayClose = true;   // no NEW entries after this hour on Friday - avoids opening a position right before the weekend gap-risk window
input int    InpFridayCutoffHour = 16;
input bool   InpCloseBeforeWeekend = false; // optionally force-close any open position before the same cutoff, not just block new entries

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
input ulong  InpMagic          = 20260101;
input int    InpSlippagePoints = 30;

input group "=== Misc ==="
input bool   InpAllowShorts    = true;
input bool   InpAllowLongs     = true;
input string InpTradeComment   = "Slipstream";

input group "=== Display ==="
input bool   InpShowPanel      = true;
input int    InpPanelDrag      = 1;    // 0 = locked, 1 = draggable - matches Aurelius/Fulcrum/Ratchet/Zenith/Daybreak
input int    InpPanelX         = 12;   // distance from the chart's left edge
input int    InpPanelY         = 30;   // was 45, now matches the family standard (Aurelius/Fulcrum/Ratchet/
                                        // Zenith/Daybreak all sit at 30, just below MT5's own symbol/OHLC header bar)
input int    InpPanelW         = 260;
input int    InpPanelSize      = 8;
// Buy/Sell (and the candles themselves) deliberately NOT the conventional
// plain red/green: bullish = neon blue, bearish = neon white, so they read
// as genuinely neon. Matches Slipstream_Signals.mq5's palette so the
// indicator and EA agree.
input color  InpColBuy         = C'0,150,255';   // neon blue (bullish)
input color  InpColSell        = clrWhite;       // neon white (bearish)
input color  InpColExitProfit  = C'0,255,140';   // neon green - distinct from Sell's white
input color  InpColExitBEorLoss = C'255,60,120'; // neon red-pink - distinct from Buy's blue
input bool   InpSetCandleColors = true;   // recolors the ENTIRE chart's candles - affects any other indicator sharing this chart too
input color  InpCandleUp       = C'0,150,255';   // same neon blue as InpColBuy
input color  InpCandleDown     = clrWhite;       // same neon white as InpColSell
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

input group "=== Indicator lines (v1.07) ==="
// Cosmetic only - these draw the SAME hEMA50/hEMA200/hBBMid/hATR values
// CheckForEntry() already reads, never a separately-computed copy, and every
// call site is gated behind g_skipCosmeticDraws. Line colours match
// Slipstream_Signals.mq5's own plot palette so the EA's lines and the
// indicator's read as one system.
input bool   InpShowLines      = true;   // Draw the EMA50 / EMA200 / midline / pullback zone this EA actually trades
input int    InpLineHistoryBars = 500;   // How many recent bars of line history to keep drawn (bounded, so a
                                          // long-running live EA doesn't accumulate objects forever). 500 H4
                                          // bars is ~3 months.
input color  InpColEMA50Line   = C'200,205,215'; // EMA50 - cool silver, same as Slipstream_Signals.mq5's plot
input color  InpColEMA200Line  = C'170,0,255';   // EMA200 - electric violet, same as the indicator's plot
input color  InpColBBMidLine   = C'0,255,255';   // BB(InpBBPeriod) SMA midline - neon cyan, same as the indicator's plot
input color  InpColTouchZone   = C'120,130,150'; // pullback-zone rails at mid +/- InpTouchTol*ATR - deliberately
                                                  // dim/dotted: a derived threshold, not a primary line
input color  InpColTrendline    = C'255,196,84'; // dynamic swing trendline (only when InpUseTrendlineConfirm is on)

input group "=== Wallpaper / Watermark ==="
input bool   InpShowWallpaper  = true;
input string InpBackgroundBMP  = "Slipstream_Wallpaper.bmp";   // place in MQL5\Images\
input int    InpBgWidth        = 1290;
input int    InpBgHeight       = 720;
input bool   InpShowWatermark  = true;
input string InpWatermarkText  = "Slipstream";
input bool   InpWaterBottom    = true;
input color  InpWatermarkColor = C'46,38,24';
input int    InpWatermarkSize  = 42;
input string InpWaterFont      = "Arial Black";

int    hEMA50=INVALID_HANDLE, hEMA200=INVALID_HANDLE, hATR=INVALID_HANDLE, hStoch=INVALID_HANDLE, hStochConf=INVALID_HANDLE;
// v1.07: the BB(InpBBPeriod) midline - the pullback target this system's whole
// entry rule is built on - finally gets a native handle, like every other
// indicator in this file already had. It used to be hand-rolled from nested
// close-summing loops inside CheckForEntry(); see the v1.07 header note.
int    hBBMid=INVALID_HANDLE;
datetime g_lastBarTime = 0;
int    g_cooldownUntilBar = -1;
int    g_barsSeen = 0;

double g_entryPx=0.0, g_entryATR=0.0, g_bestFav=0.0;
// Found in review: every close/modify call in this file used to target
// _Symbol rather than a specific ticket. CTrade's symbol-based overloads
// resolve to WHATEVER position MT5 finds on that symbol - with no
// guarantee it's this EA's own once a second EA (different magic number)
// holds a position on the same symbol at the same time, which is exactly
// how this portfolio is meant to run. A surrounding magic-number check
// earlier in the same function does NOT protect the close/modify call
// itself - it's a separate internal PositionSelect(_Symbol) with no magic
// filter at all. g_ticket + FindOwnPosition() (same pattern AuRebound_EA.mq5
// already uses correctly) replace every symbol-based site below.
ulong  g_ticket = 0;
datetime g_entryTime = 0;

bool   g_bgOK=false;
int    g_bgTries=0;
string g_prefix = "SLPEA_";
//--- v1.07: per-bar indicator line segments (EMA50 / EMA200 / midline / touch
//--- rails) plus the single swing trendline - purged to a rolling window, see
//--- DrawLineSegment/PurgeOldLines/UpdateLines. Deliberately NOT a sub-string
//--- of g_prefix ("SLPEA_") or of the companion indicator's SLP_/SLPP_, so
//--- ObjectsDeleteAll on any of those can never sweep these and vice versa -
//--- each prefix owns exactly its own objects.
string g_pl     = "SLPL_";
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

// live running trade stats (real fills, not a backtest scan)
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
   hEMA50  = iMA(_Symbol, PERIOD_CURRENT, InpEMA50, 0, MODE_EMA, PRICE_CLOSE);
   hEMA200 = iMA(_Symbol, PERIOD_CURRENT, InpEMA200, 0, MODE_EMA, PRICE_CLOSE);
   hATR    = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   hStoch  = iStochastic(_Symbol, PERIOD_CURRENT, InpStochK, InpStochD, InpStochSlow, MODE_SMA, STO_LOWHIGH);
   // AuRebound's own validated Stochastic settings (21,5,5) - kept fixed/internal rather than
   // exposed as inputs, since this is a replica of ANOTHER system's condition, not a primary control.
   hStochConf = iStochastic(_Symbol, PERIOD_CURRENT, 21, 5, 5, MODE_SMA, STO_LOWHIGH);
   // v1.07: the BB midline CheckForEntry() used to hand-roll from a close-summing
   // loop. An SMA of the last InpBBPeriod closes ending at bar i is exactly what
   // that loop computed, so this is the same value from MT5's own calculation.
   hBBMid  = iMA(_Symbol, PERIOD_CURRENT, InpBBPeriod, 0, MODE_SMA, PRICE_CLOSE);
   if(hEMA50==INVALID_HANDLE || hEMA200==INVALID_HANDLE || hATR==INVALID_HANDLE || hStoch==INVALID_HANDLE ||
      hStochConf==INVALID_HANDLE || hBBMid==INVALID_HANDLE)
     { Print("Slipstream EA: indicator handle creation failed"); return(INIT_FAILED); }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   RestoreStateFromOpenPosition();
   RebuildLiveStatsFromHistory();
   //--- one-off, cheap - drawn unconditionally even in a non-visual Tester
   //--- pass, same as Aurelius_EA.mq5's own OnInit. g_skipCosmeticDraws only
   //--- gates the REPEATED per-second redraw further down in OnTick().
   if(InpShowWallpaper) DrawWallpaper();
   if(InpShowWatermark) DrawWatermark();
   DrawPanel();   // show something the moment it attaches - was left to depend on the first tick
   //--- v1.07: fill the whole rolling line window immediately, so a fresh
   //--- attach shows real history instead of 1-bar stubs. Cosmetic only -
   //--- skipped in a non-visual Tester pass, where the loop would draw up to
   //--- 5*InpLineHistoryBars objects onto a chart nobody can see.
   if(!g_skipCosmeticDraws && InpShowLines) BackfillLines();
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(hEMA50!=INVALID_HANDLE) IndicatorRelease(hEMA50);
   if(hEMA200!=INVALID_HANDLE) IndicatorRelease(hEMA200);
   if(hATR!=INVALID_HANDLE) IndicatorRelease(hATR);
   if(hStoch!=INVALID_HANDLE) IndicatorRelease(hStoch);
   if(hStochConf!=INVALID_HANDLE) IndicatorRelease(hStochConf);
   if(hBBMid!=INVALID_HANDLE) IndicatorRelease(hBBMid);
   ObjectsDeleteAll(0, g_prefix);
   ObjectsDeleteAll(0, g_pl);   // v1.07 indicator line segments + trendline - own prefix, own sweep
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
         DrawPanel();   // re-anchor to the new width immediately, don't wait for the next tick
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
     { Print("Slipstream EA BG: ObjectCreate failed, error ", GetLastError()); return; }
   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0,nm,OBJPROP_BMPFILE,0,path);
   int err = GetLastError();
   if(!okSet || err!=0)
     {
      if(g_bgTries<=3)
         PrintFormat("Slipstream EA BG try %d: failed to load \"%s\" set=%s error=%d -> file must be at <data folder>\\MQL5\\Images\\%s",
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
   PrintFormat("Slipstream EA BG: loaded \"%s\" on try %d", path, g_bgTries);
   ChartRedraw(0);
  }
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
//| v1.07 - EMA50 / EMA200 / BB midline / pullback-zone rails, drawn     |
//| natively by this EA.                                                 |
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
                                                        // up to 5*InpLineHistoryBars of these exist
  }
//+------------------------------------------------------------------+
//| The two fixed-name swing trendlines are excluded from the purge on    |
//| purpose - they carry no bar timestamp of their own to age out by, and |
//| EmitTrendline() already replaces them under the same names each bar.  |
//+------------------------------------------------------------------+
void PurgeOldLines(const datetime latestBarTime)
  {
   datetime cutoff = latestBarTime - (datetime)((long)InpLineHistoryBars * PeriodSeconds(PERIOD_CURRENT));
   for(int k = ObjectsTotal(0, 0, OBJ_TREND) - 1; k >= 0; k--)
     {
      string nm = ObjectName(0, k, 0, OBJ_TREND);
      if(StringFind(nm, g_pl) != 0) continue;
      if(StringFind(nm, g_pl + "TL") == 0) continue;   // fixed-name trendlines, see above
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < cutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
//| Creates (or replaces) one right-ray trendline under a fixed name.     |
//| `ok` false means this side has no two confirmed swings right now -    |
//| the stale line is removed rather than left showing an anchor pair     |
//| the EA is no longer using.                                            |
//+------------------------------------------------------------------+
void DrawRayTrendline(const string tag, const bool ok,
                      const datetime t1, const double v1,
                      const datetime t2, const double v2)
  {
   string nm = g_pl + tag;
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   if(!ok) return;
   ObjectCreate(0, nm, OBJ_TREND, 0, t1, v1, t2, v2);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, InpColTrendline);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, true);   // project forward to where price meets it
   ObjectSetInteger(0, nm, OBJPROP_RAY_LEFT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| The dynamic swing trendline InpUseTrendlineConfirm already resolves    |
//| internally, made visible. TrendlineTouchLongSeries()/ShortSeries()     |
//| are signal functions and are left completely untouched - this thin     |
//| wrapper re-runs the identical k1/k2 swing-point search (same swingLag  |
//| fractal test, same loBound/hiBound, same "second confirmed swing wins  |
//| k1" ordering) purely to get the two anchor points out, rather than     |
//| adding an output parameter to a function on the entry path.            |
//|                                                                        |
//| One object per side under a FIXED name, delete-and-recreate each bar:  |
//| the anchors genuinely move as new swings confirm, so there is nothing  |
//| to accumulate, and this is a once-per-bar call, not a hot path.        |
//| RAY_RIGHT so the line projects forward to where price will meet it -   |
//| which is the whole point of looking at it.                             |
//+------------------------------------------------------------------+
void EmitTrendline()
  {
   int i = 1;                                        // last closed bar, same as CheckForEntry()
   int depth = 1 + 2*InpSwingLag + 150 + 10;         // same window the filter searches within
   if(Bars(_Symbol, PERIOD_CURRENT) < depth + 5) return;

   datetime t[]; double h[], l[];
   ArraySetAsSeries(t,true); ArraySetAsSeries(h,true); ArraySetAsSeries(l,true);
   if(CopyTime(_Symbol,PERIOD_CURRENT,0,depth,t) < depth) return;
   if(CopyHigh(_Symbol,PERIOD_CURRENT,0,depth,h) < depth) return;
   if(CopyLow (_Symbol,PERIOD_CURRENT,0,depth,l) < depth) return;

   int loBound = i + InpSwingLag;
   int hiBound = MathMin(ArraySize(l)-1-InpSwingLag, loBound + 150);

   //--- swing lows -> the long-side trendline
   int k1=-1, k2=-1;
   for(int k=loBound; k<=hiBound; k++)
     {
      bool isLow=true;
      for(int m=k-InpSwingLag; m<=k+InpSwingLag; m++) if(l[m]<l[k]) { isLow=false; break; }
      if(isLow) { if(k2<0) k2=k; else { k1=k; break; } }
     }
   DrawRayTrendline("TLlong", (k1>=0 && k2>=0), t[k1<0?0:k1], l[k1<0?0:k1], t[k2<0?0:k2], l[k2<0?0:k2]);

   //--- swing highs -> the short-side trendline
   int j1=-1, j2=-1;
   int hiBoundH = MathMin(ArraySize(h)-1-InpSwingLag, loBound + 150);
   for(int k=loBound; k<=hiBoundH; k++)
     {
      bool isHigh=true;
      for(int m=k-InpSwingLag; m<=k+InpSwingLag; m++) if(h[m]>h[k]) { isHigh=false; break; }
      if(isHigh) { if(j2<0) j2=k; else { j1=k; break; } }
     }
   DrawRayTrendline("TLshort", (j1>=0 && j2>=0), t[j1<0?0:j1], h[j1<0?0:j1], t[j2<0?0:j2], h[j2<0?0:j2]);
  }
//+------------------------------------------------------------------+
//| Draws the segments (bar 2 -> bar 1) for the bar that just closed,     |
//| plus the pullback-zone rails around the midline. Reads the SAME       |
//| hEMA50/hEMA200/hBBMid/hATR handles CheckForEntry() reads - four       |
//| 2-value CopyBuffer calls, so this stays cheap.                        |
//|                                                                       |
//| The rails are mid +/- InpTouchTol*ATR: literally the band             |
//| CheckForEntry()'s recentTouch test measures the bar's low/high        |
//| against, i.e. the support/resistance zone this whole system trades.    |
//+------------------------------------------------------------------+
void UpdateLines()
  {
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, 2);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(tA == 0 || tB == 0) return;

   double e50[], e200[], mid[], atrBuf[];
   ArraySetAsSeries(e50,true); ArraySetAsSeries(e200,true);
   ArraySetAsSeries(mid,true); ArraySetAsSeries(atrBuf,true);
   if(CopyBuffer(hEMA50,  0, 1, 2, e50)    < 2) return;   // [0]=shift1, [1]=shift2
   if(CopyBuffer(hEMA200, 0, 1, 2, e200)   < 2) return;
   if(CopyBuffer(hBBMid,  0, 1, 2, mid)    < 2) return;
   if(CopyBuffer(hATR,    0, 1, 2, atrBuf) < 2) return;

   DrawLineSegment("e50",  tA, e50[1],  tB, e50[0],  InpColEMA50Line,  STYLE_SOLID);
   DrawLineSegment("e200", tA, e200[1], tB, e200[0], InpColEMA200Line, STYLE_SOLID);
   DrawLineSegment("mid",  tA, mid[1],  tB, mid[0],  InpColBBMidLine,  STYLE_SOLID);

   if(atrBuf[0] > 0.0 && atrBuf[1] > 0.0 && mid[0] > 0.0 && mid[1] > 0.0)
     {
      double dA = InpTouchTol * atrBuf[1], dB = InpTouchTol * atrBuf[0];
      DrawLineSegment("zup", tA, mid[1]+dA, tB, mid[0]+dB, InpColTouchZone, STYLE_DOT);
      DrawLineSegment("zlo", tA, mid[1]-dA, tB, mid[0]-dB, InpColTouchZone, STYLE_DOT);
     }

   //--- only when the EA is actually consulting it - see EmitTrendline's header
   if(InpUseTrendlineConfirm) EmitTrendline();

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
//| The swing trendline is not backfilled: it has exactly one current     |
//| position, drawn by the first UpdateLines() call.                      |
//+------------------------------------------------------------------+
void BackfillLines()
  {
   //--- copying from shift 1 yields at most Bars-1 elements, and `want` below
   //--- asks for n+2 of them - so n can be at most Bars-3.
   int avail = Bars(_Symbol, PERIOD_CURRENT) - 3;
   int n = MathMin(InpLineHistoryBars, avail);
   if(n < 1) return;

   datetime bt[]; double e50[], e200[], mid[], atrBuf[];
   ArraySetAsSeries(bt,true);  ArraySetAsSeries(e50,true);
   ArraySetAsSeries(e200,true); ArraySetAsSeries(mid,true); ArraySetAsSeries(atrBuf,true);
   int want = n + 2;   // shift 1 .. n+1, so the oldest segment has both endpoints
   if(CopyTime  (_Symbol, PERIOD_CURRENT, 1, want, bt) < want) return;
   if(CopyBuffer(hEMA50,  0, 1, want, e50)             < want) return;
   if(CopyBuffer(hEMA200, 0, 1, want, e200)            < want) return;
   if(CopyBuffer(hBBMid,  0, 1, want, mid)             < want) return;
   if(CopyBuffer(hATR,    0, 1, want, atrBuf)          < want) return;

   //--- s is a series index relative to shift 1: s+1 is the older bar, s the
   //--- newer one, matching UpdateLines()'s bar2 -> bar1 pairing exactly.
   for(int s = n - 1; s >= 0; s--)
     {
      if(bt[s+1] == 0 || bt[s] == 0) continue;
      //--- an EMA200 (or the midline) that hasn't warmed up yet reads back as
      //--- 0.0 - skip those bars rather than drawing a line down to zero.
      if(e50[s]>0.0 && e50[s+1]>0.0)
         DrawLineSegment("e50",  bt[s+1], e50[s+1],  bt[s], e50[s],  InpColEMA50Line,  STYLE_SOLID);
      if(e200[s]>0.0 && e200[s+1]>0.0)
         DrawLineSegment("e200", bt[s+1], e200[s+1], bt[s], e200[s], InpColEMA200Line, STYLE_SOLID);
      if(mid[s]>0.0 && mid[s+1]>0.0)
        {
         DrawLineSegment("mid", bt[s+1], mid[s+1], bt[s], mid[s], InpColBBMidLine, STYLE_SOLID);
         if(atrBuf[s]>0.0 && atrBuf[s+1]>0.0)
           {
            double dA = InpTouchTol * atrBuf[s+1], dB = InpTouchTol * atrBuf[s];
            DrawLineSegment("zup", bt[s+1], mid[s+1]+dA, bt[s], mid[s]+dB, InpColTouchZone, STYLE_DOT);
            DrawLineSegment("zlo", bt[s+1], mid[s+1]-dA, bt[s], mid[s]-dB, InpColTouchZone, STYLE_DOT);
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
// rebuild running stats from actual closed-deal history on startup, so the
// panel reflects real trading history rather than resetting to zero every
// time the EA is reloaded/recompiled
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
   // every broker-side stop close (the MFE lock included), which meant the
   // header's own "Fixed pre-demo" claim #3 - cooldown engaging on a
   // broker-side stop, not just an EA-initiated close - was never actually
   // in effect, since that fix lives below this check too.
   if(!HistoryDealSelect(ticket)) return;
   if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagic) return;
   if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) return;
   if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;
   double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_SWAP) + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   RecordClosedTrade(profit);
   g_lastSeenDeal = ticket;
   // this is the single place that sees every closed trade regardless of
   // cause - our own trend-break/timeout close, a weekend force-close, or
   // the broker hitting the stop-loss directly (the most common exit for
   // this system). Setting cooldown only in ManageOpenPosition() missed the
   // broker-SL-hit case entirely, letting the EA re-enter with no cooldown
   // at all right after a stop-out. Idempotent with the ManageOpenPosition
   // assignment for EA-initiated closes - same bar count, same result.
   g_cooldownUntilBar = g_barsSeen + InpCooldown;

   long dealType = HistoryDealGetInteger(ticket, DEAL_TYPE);
   double dealPrice = HistoryDealGetDouble(ticket, DEAL_PRICE);
   datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
   // a DEAL_TYPE_SELL closing deal means the position being closed was a BUY
   int wasLong = (dealType==DEAL_TYPE_SELL) ? 1 : 0;
   color mvClr = (profit>0)?InpColExitProfit:InpColExitBEorLoss;
   DrawTradeTag(g_prefix+"X"+(string)ticket, dealTime, dealPrice, "◆",
                mvClr, wasLong?ANCHOR_LOWER:ANCHOR_UPPER);

   DrawPanel();
  }
//+------------------------------------------------------------------+
// the POSITION block (s4,k1-k5) only draws while a position is open - clean
// it up when flat so a closed position doesn't leave stale objects behind
void DeletePositionBlock()
  {
   string ids[] = {"s4bar","s4t","k1L","k1V","k2L","k2V","k3L","k3V","k4L","k4V","k5L","k5V"};
   for(int i=0;i<ArraySize(ids);i++)
     {
      string nm = g_prefix+"P"+ids[i];
      if(ObjectFind(0,nm)>=0) ObjectDelete(0,nm);
     }
  }
// Consolas is monospace - ~0.62x font size per glyph is a safe advance-width
// estimate, used to size the panel so long values never overlap their label
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
struct PanelItem
  {
   string id, label, val;
   int    state;      // -1 neutral, 0 bad/orange, 1 good/green - ignored for sections
   bool   section;     // true = single-line title (PSection), false = two-column (PRow)
   int    gapAfter;    // extra px of breathing room after this item (0 or 6)
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

   PanelItem items[30]; int nI=0;
   ADDSEC("s1","SLIPSTREAM EA [Live]",6)
   ADDROW("r0","position",hasPos?(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"LONG":"SHORT"):"none",
          hasPos?(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:0):-1,0)
   ADDROW("r1","closed trades",(string)g_liveTrades,-1,0)
   ADDROW("r2","win rate",DoubleToString(g_liveTrades>0?100.0*g_liveWins/g_liveTrades:0.0,1)+"%",-1,0)
   ADDROW("r3","profit factor",DoubleToString(pf,2),pf>1.0?1:(pf>0?0:-1),0)
   ADDROW("r4","net",DoubleToString(g_liveNet,2),g_liveNet>=0?1:0,0)
   ADDROW("r5","avg / trade",DoubleToString(avgTrade,3),avgTrade>=0?1:0,6)
   ADDSEC("s2","FILTERS",6)
   ADDROW("g1","blocked hrs",InpUseSessionFilter?StringFormat("%02d, %02d",InpBlockedHour1,InpBlockedHour2):"off",InpUseSessionFilter?0:-1,0)
   ADDROW("g2","Fri cutoff",InpBlockFridayClose?StringFormat("%02d:00",InpFridayCutoffHour):"off",InpBlockFridayClose?0:-1,0)
   int cdLeft = MathMax(0, g_cooldownUntilBar - g_barsSeen);
   ADDROW("g3","cooldown",cdLeft>0?(string)cdLeft+" bars":"clear",cdLeft>0?0:1,0)
   ADDROW("g4","confluence",InpRequireConfluence?"on ("+(string)InpConfluenceWindow+"bar)":"off",InpRequireConfluence?1:-1,0)
   ADDROW("g5","news filter",InpUseNewsFilter?InpNewsCurrency+" hi-imp":"off",InpUseNewsFilter?1:-1,6)
   ADDSEC("s3","SETTINGS",6)
   ADDROW("h1","BB / EMA",StringFormat("%d / %d,%d",InpBBPeriod,InpEMA50,InpEMA200),-1,0)
   ADDROW("h2","Stoch",StringFormat("%d,%d,%d",InpStochK,InpStochD,InpStochSlow),-1,0)
   ADDROW("h3","entry mode",InpSignalLineMode?"signal-turn":"cross-50",-1,0)
   ADDROW("h4","MFE lock",InpUseMFELock?StringFormat("%.0f%% @ %.1fx ATR",InpMFELockFrac*100,InpMFELockTrigger):"off",InpUseMFELock?1:-1,0)
   ADDROW("h5","sizing",InpUseRiskPercent?StringFormat("%.1f%% risk",InpRiskPercent):StringFormat("%.2f lots fixed",InpFixedLots),-1,hasPos?6:0)

   if(hasPos)
     {
      double curSL = PositionGetDouble(POSITION_SL);
      double curPrice = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol,SYMBOL_BID) : SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      int barsHeld = (int)((TimeCurrent()-g_entryTime)/PeriodSeconds(PERIOD_CURRENT));
      ADDSEC("s4","POSITION",6)
      ADDROW("k1","entry",DoubleToString(g_entryPx,_Digits),-1,0)
      ADDROW("k2","stop",curSL>0?DoubleToString(curSL,_Digits):"none",curSL>0?-1:0,0)
      ADDROW("k3","dist to stop",curSL>0?DoubleToString(MathAbs(curPrice-curSL),_Digits):"n/a",-1,0)
      ADDROW("k4","best move",g_entryATR>0?StringFormat("%.5f (%.2fx ATR)",g_bestFav,g_bestFav/g_entryATR):DoubleToString(g_bestFav,_Digits),-1,0)
      ADDROW("k5","bars held",(string)barsHeld+" / "+(string)InpMaxHoldBars,-1,0)
     }
   else
      DeletePositionBlock();

   // pass 1: width - grows past InpPanelW only if some row actually needs it
   int w=InpPanelW, hgt=20;
   for(int r=0;r<nI;r++)
     {
      int need = items[r].section
                 ? EstimateTextWidth(items[r].label,InpPanelSize+1)+8
                 : EstimateTextWidth(items[r].label,InpPanelSize)+24+EstimateTextWidth(items[r].val,InpPanelSize);
      if(need>w) w=need;
      hgt += rh + items[r].gapAfter;
     }

   // pass 2: draw, now that w is final
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
// if the EA restarts/recompiles while a position is already open, recover
// enough state (entry price, entry ATR) to keep the MFE-lock working -
// best-favorable-excursion is conservatively reset to zero and rebuilds
// naturally from here rather than risk a wrong stale value
void RestoreStateFromOpenPosition()
  {
   if(!FindOwnPosition(g_ticket)) return;
   if(!PositionSelectByTicket(g_ticket)) return;
   g_entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
   g_entryTime = (datetime)PositionGetInteger(POSITION_TIME);
   double atrBuf[];
   ArraySetAsSeries(atrBuf,true);
   if(CopyBuffer(hATR,0,0,1,atrBuf)>0) g_entryATR = atrBuf[0]; else g_entryATR = 0.0;
   g_bestFav = 0.0;
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
// dynamic trendline through the two most recent confirmed swing lows
// (long) / highs (short). Series-indexed (0=newest): a swing point at k is
// confirmed once k >= i+swingLag (swingLag bars have occurred more
// recently than it, i.e. at smaller indices, so nothing lower/higher has
// happened since). Same tolerance concept as the horizontal BB-midline
// touch, just on a sloped line instead of a flat one.
bool TrendlineTouchLongSeries(const int i,const int swingLag,const int searchBars,const double &l[],const double &h[],const double atrV,const double touchTol)
  {
   int k1=-1,k2=-1;
   int loBound=i+swingLag;
   int hiBound=MathMin(ArraySize(l)-1-swingLag, loBound+searchBars);
   for(int k=loBound;k<=hiBound;k++)
     {
      bool isLow=true;
      for(int m=k-swingLag;m<=k+swingLag;m++) if(l[m]<l[k]) { isLow=false; break; }
      if(isLow) { if(k2<0) k2=k; else { k1=k; break; } }
     }
   if(k1<0 || k2<0) return(false);
   double slope=(l[k2]-l[k1])/(double)(k1-k2);
   double lineVal=l[k2]+slope*(k2-i);
   return(MathAbs(l[i]-lineVal)<=touchTol*atrV);
  }
// --- self-contained confluence check (see InpRequireConfluence) ---
// Replicates Tailwind's and AuRebound's own entry conditions directly off a
// dedicated, self-fetched price/indicator window - no dependency on either
// EA actually running. Series-indexed (0=newest). Deliberately fetches its
// own 150-bar window independent of the main signal arrays above, so a
// short InpBBPeriod/InpLookback elsewhere can't starve the EMA21 seed this
// needs to converge.
bool CheckConfluenceDir(const int dir, const int window)
  {
   int depth=150;
   double c[],h[],l[],atrC[],stC[];
   ArraySetAsSeries(c,true); ArraySetAsSeries(h,true); ArraySetAsSeries(l,true);
   ArraySetAsSeries(atrC,true); ArraySetAsSeries(stC,true);
   if(CopyClose(_Symbol,PERIOD_CURRENT,0,depth,c)<=0) return(false);
   if(CopyHigh(_Symbol,PERIOD_CURRENT,0,depth,h)<=0) return(false);
   if(CopyLow(_Symbol,PERIOD_CURRENT,0,depth,l)<=0) return(false);
   if(CopyBuffer(hATR,0,0,depth,atrC)<=0) return(false);
   if(CopyBuffer(hStochConf,SIGNAL_LINE,0,depth,stC)<=0) return(false);
   int nAvail=MathMin(MathMin(ArraySize(c),ArraySize(h)),MathMin(ArraySize(l),MathMin(ArraySize(atrC),ArraySize(stC))));
   int need=window+30;
   if(nAvail<need) return(false);

   for(int k=0;k<=window;k++)
     {
      // Tailwind-style: k consecutive-with-trend close vs EMA21 & SMA20 midline
      if(k+19>=nAvail || k+20+21>=nAvail) continue;   // needs SMA20 + EMA21 seed room
      double sma20=0.0; for(int m=0;m<20;m++) sma20+=c[k+m]; sma20/=20.0;
      double ema21 = c[k+20+20];   // seed: oldest available close in the EMA window
      double kf=2.0/(21+1);
      for(int idx=k+20+19; idx>=k; idx--) ema21 = c[idx]*kf + ema21*(1.0-kf);
      bool twMatch = (dir>0) ? (c[k]>ema21 && c[k]>sma20) : (c[k]<ema21 && c[k]<sma20);
      if(twMatch) return(true);

      // AuRebound-style: recent band-edge touch (Bollinger 20,2) + Stochastic(21,5,5) signal-line turn
      if(k+2>=nAvail || k+19>=nAvail) continue;
      double aV=atrC[k]; if(aV<=0.0) continue;
      if(stC[k]==EMPTY_VALUE || stC[k+1]==EMPTY_VALUE || stC[k+2]==EMPTY_VALUE) continue;
      bool arTurnUp = (stC[k]>stC[k+1]) && (stC[k+1]<=stC[k+2]);
      bool arTurnDn = (stC[k]<stC[k+1]) && (stC[k+1]>=stC[k+2]);
      bool recentLower=false, recentUpper=false;
      for(int m=k; m<=k+3 && m+19<nAvail; m++)
        {
         double mMid=0.0; for(int j=0;j<20;j++) mMid+=c[m+j]; mMid/=20.0;
         double var=0.0; for(int j=0;j<20;j++) { double d=c[m+j]-mMid; var+=d*d; } double sd=MathSqrt(var/20.0);
         double up=mMid+2.0*sd, lo=mMid-2.0*sd;
         double aM=atrC[m]; if(aM<=0.0) continue;
         if(h[m]>=up-0.5*aM) recentUpper=true;
         if(l[m]<=lo+0.5*aM) recentLower=true;
        }
      bool arMatch = (dir>0) ? (recentLower && arTurnUp) : (recentUpper && arTurnDn);
      if(arMatch) return(true);
     }
   return(false);
  }
bool TrendlineTouchShortSeries(const int i,const int swingLag,const int searchBars,const double &l[],const double &h[],const double atrV,const double touchTol)
  {
   int k1=-1,k2=-1;
   int loBound=i+swingLag;
   int hiBound=MathMin(ArraySize(h)-1-swingLag, loBound+searchBars);
   for(int k=loBound;k<=hiBound;k++)
     {
      bool isHigh=true;
      for(int m=k-swingLag;m<=k+swingLag;m++) if(h[m]>h[k]) { isHigh=false; break; }
      if(isHigh) { if(k2<0) k2=k; else { k1=k; break; } }
     }
   if(k1<0 || k2<0) return(false);
   double slope=(h[k2]-h[k1])/(double)(k1-k2);
   double lineVal=h[k2]+slope*(k2-i);
   return(MathAbs(h[i]-lineVal)<=touchTol*atrV);
  }
//+------------------------------------------------------------------+
// broker-legal minimum distance a stop may sit from the current price.
// SYMBOL_TRADE_STOPS_LEVEL/FREEZE_LEVEL can legitimately report 0 for some
// brokers without meaning "no restriction" - spread*1.5 is used as a safety
// margin floor on top of whatever the broker does report.
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
      PrintFormat("Slipstream_EA: risk-percent sizing wanted a %.4f lot below the broker minimum (%.4f) - "
                  "raising to the minimum risks more than InpRiskPercent=%.2f%% on this trade",
                  lots, minLot, InpRiskPercent);
   lots = MathMax(minLot, MathMin(maxLot, lots));
   return(lots);
  }
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   if(g_ticket==0 || !PositionSelectByTicket(g_ticket)) { g_ticket=0; return; }

   long ptype = PositionGetInteger(POSITION_TYPE);
   double curSL = PositionGetDouble(POSITION_SL);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double curPrice = (ptype==POSITION_TYPE_BUY) ? bid : ask;

   double favMove = (ptype==POSITION_TYPE_BUY) ? (curPrice - g_entryPx) : (g_entryPx - curPrice);
   g_bestFav = MathMax(g_bestFav, favMove);

   //--- MFE-lock: only ever tightens the stop, safe to check every tick.
   //--- Deliberately NO breakeven-snap stage - validated as worse for this
   //--- entry config (cuts genuine trend continuations short when price
   //--- naturally retests the entry zone before extending).
   if(InpUseMFELock && g_entryATR>0 && g_bestFav >= InpMFELockTrigger*g_entryATR)
     {
      double lockPrice = g_entryPx + (ptype==POSITION_TYPE_BUY?1:-1) * g_bestFav * InpMFELockFrac;
      //--- clamp to the broker-legal minimum distance from price, and never
      //--- let the clamp push the stop past whatever is already on the
      //--- position (the lock must only ever tighten, never loosen)
      double minDist = MinStopDistance();
      if(ptype==POSITION_TYPE_BUY)
        {
         lockPrice = MathMin(lockPrice, bid-minDist);
         if(curSL>0) lockPrice = MathMax(lockPrice, curSL);
        }
      else
        {
         lockPrice = MathMax(lockPrice, ask+minDist);
         if(curSL>0) lockPrice = MathMin(lockPrice, curSL);
        }
      bool improves = (ptype==POSITION_TYPE_BUY) ? (lockPrice > curSL) : (curSL<=0 || lockPrice < curSL);
      if(improves)
        {
         double tp = PositionGetDouble(POSITION_TP);
         if(!trade.PositionModify(g_ticket, NormalizeDouble(lockPrice,_Digits), tp))
            PrintFormat("Slipstream EA: MFE-lock modify failed, error %d retcode %d - target=%.5f curSL=%.5f bid=%.5f ask=%.5f minDist=%.5f",
                        GetLastError(), trade.ResultRetcode(), lockPrice, curSL, bid, ask, minDist);
        }
     }

   //--- optional: force-close ahead of the weekend regardless of bar timing,
   //--- since the cutoff hour can arrive mid-bar, not just at a bar close
   if(InpCloseBeforeWeekend)
     {
      MqlDateTime dtNow;
      TimeToStruct(TimeCurrent(), dtNow);
      if(dtNow.day_of_week==5 && dtNow.hour>=InpFridayCutoffHour)
        {
         trade.PositionClose(g_ticket, InpSlippagePoints);
         g_cooldownUntilBar = g_barsSeen + InpCooldown;
         return;
        }
     }

   //--- trend-break and max-hold checks only need to happen once per closed bar
   if(!IsNewBar()) return;

   double ema50Buf[];
   ArraySetAsSeries(ema50Buf,true);
   if(CopyBuffer(hEMA50,0,1,1,ema50Buf)<=0) return;
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);

   bool trendBreak = (ptype==POSITION_TYPE_BUY) ? (c1 < ema50Buf[0]) : (c1 > ema50Buf[0]);
   int barsHeld = (int)((TimeCurrent()-g_entryTime)/PeriodSeconds(PERIOD_CURRENT));
   bool timedOut = barsHeld >= InpMaxHoldBars;

   if(trendBreak || timedOut)
     {
      trade.PositionClose(g_ticket, InpSlippagePoints);
      g_cooldownUntilBar = g_barsSeen + InpCooldown;
     }
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
   // through, leaving the first one completely unmanaged (no trend-break
   // exit, no MFE-lock, no timeout) until its broker SL hits. Re-sync from
   // a live scan before trusting the cached value.
   if(g_ticket==0) FindOwnPosition(g_ticket);
   if(g_ticket!=0 && PositionSelectByTicket(g_ticket)) return;
   if(g_barsSeen <= g_cooldownUntilBar) return;
   if(NewsBlackoutActive()) return;

   int need = MathMax(InpEMA200, MathMax(InpBBPeriod, InpStochK+InpStochD+InpStochSlow)) + 20;
   if(Bars(_Symbol,PERIOD_CURRENT) < need+20) return;

   MqlDateTime dt;
   TimeToStruct(iTime(_Symbol,PERIOD_CURRENT,1), dt);
   if(InpUseSessionFilter && (dt.hour==InpBlockedHour1 || dt.hour==InpBlockedHour2)) return;
   if(InpBlockFridayClose && dt.day_of_week==5 && dt.hour>=InpFridayCutoffHour) return;
   if(InpBlockFridayClose && dt.day_of_week==6) return;   // Saturday - market closed, defensive guard

   // must cover the deepest index the recentTouch loop below reads:
   // i(1) + InpLookback + InpBBPeriod-1, plus a safety margin. Widened when
   // the trendline filter needs room to search back for two swing points.
   // v1.07: the +InpBBPeriod term is no longer strictly required here - the
   // midline moved to the hBBMid buffer, so this window's deepest read is now
   // just l[i+InpLookback] (the recentTouch/`extreme` loops). Left unchanged
   // rather than trimmed: it only over-fetches, and the size this passes to
   // CopyLow/CopyHigh is what TrendlineTouch*Series() searches within.
   int need_bars = InpLookback + InpBBPeriod + 15;
   if(InpUseTrendlineConfirm) need_bars = MathMax(need_bars, 1+2*InpSwingLag+150+10);
   double o[],h[],l[],c[];
   ArraySetAsSeries(o,true); ArraySetAsSeries(h,true); ArraySetAsSeries(l,true); ArraySetAsSeries(c,true);
   if(CopyOpen(_Symbol,PERIOD_CURRENT,0,need_bars,o)<=0) return;
   if(CopyHigh(_Symbol,PERIOD_CURRENT,0,need_bars,h)<=0) return;
   if(CopyLow(_Symbol,PERIOD_CURRENT,0,need_bars,l)<=0) return;
   if(CopyClose(_Symbol,PERIOD_CURRENT,0,need_bars,c)<=0) return;

   double ema50[], ema200[], atrBuf[], stD[], bbMid[];
   ArraySetAsSeries(ema50,true); ArraySetAsSeries(ema200,true); ArraySetAsSeries(atrBuf,true); ArraySetAsSeries(stD,true);
   ArraySetAsSeries(bbMid,true);
   int need_ind = InpTrendSlopeBars + 15;
   // v1.07: the midline's own depth - the recentTouch loop below reads bbMid
   // as deep as i(1)+InpLookback, which is independent of InpTrendSlopeBars.
   int need_mid = InpLookback + 15;
   if(CopyBuffer(hEMA50,0,0,need_ind,ema50)<=0) return;
   if(CopyBuffer(hEMA200,0,0,need_ind,ema200)<=0) return;
   if(CopyBuffer(hATR,0,0,need_ind,atrBuf)<=0) return;
   if(CopyBuffer(hStoch,SIGNAL_LINE,0,need_ind,stD)<=0) return;
   if(CopyBuffer(hBBMid,0,0,need_mid,bbMid)<need_mid) return;

   // index 1 = last closed bar - the bar the indicator's OnCalculate loop
   // would be evaluating as "current" for signal purposes
   int i = 1;
   double a = atrBuf[i];
   if(a<=0) return;

   bool slopeUp = ema50[i] > ema50[i+InpTrendSlopeBars];
   bool uptrend   = (c[i] > ema200[i]) && slopeUp;
   bool downtrend = (c[i] < ema200[i]) && (!slopeUp);

   // v1.07: was `mid = 0.0; for(k=0..InpBBPeriod-1) mid += c[i+k]; mid /= InpBBPeriod;`
   // - a hand-rolled SMA on a system whose EMA50/EMA200/Stochastic/ATR were all
   // already native handles. hBBMid is the same SMA of the same InpBBPeriod
   // closes ending at bar i, computed once by MT5 instead of re-summed here on
   // every bar (and again for every InpLookback bar in the loop below).
   double mid = bbMid[i];
   // a not-yet-calculated buffer reads back as 0.0; the old loop could never
   // produce that, so reject the bar rather than testing a touch against zero.
   if(mid<=0.0) return;

   bool recentTouch = (MathAbs(l[i]-mid) <= InpTouchTol*a) || (l[i]<=mid && h[i]>=mid);
   for(int k=1;k<=InpLookback && !recentTouch;k++)
     {
      double midK = bbMid[i+k];
      if(midK<=0.0) continue;
      double aK = atrBuf[i+k];
      if(aK<=0) continue;
      if((MathAbs(l[i+k]-midK)<=InpTouchTol*aK) || (l[i+k]<=midK && h[i+k]>=midK)) recentTouch=true;
     }

   bool turnUp=false, turnDn=false;
   if(InpSignalLineMode)
     {
      if(stD[i]!=EMPTY_VALUE && stD[i+1]!=EMPTY_VALUE && stD[i+2]!=EMPTY_VALUE)
        {
         turnUp = (stD[i]>stD[i+1]) && (stD[i+1]<=stD[i+2]);
         turnDn = (stD[i]<stD[i+1]) && (stD[i+1]>=stD[i+2]);
        }
     }
   else
     {
      if(stD[i]!=EMPTY_VALUE && stD[i+1]!=EMPTY_VALUE)
        {
         turnUp = (stD[i+1]<50.0) && (stD[i]>=50.0);
         turnDn = (stD[i+1]>50.0) && (stD[i]<=50.0);
        }
     }

   bool longSig  = InpAllowLongs  && uptrend   && recentTouch && turnUp;
   bool shortSig = InpAllowShorts && downtrend && recentTouch && turnDn;

   if(InpBlockIndecision && IsIndecisionCandle(o[i],h[i],l[i],c[i])) { longSig=false; shortSig=false; }
   if(InpUseTrendlineConfirm)
     {
      if(longSig  && !TrendlineTouchLongSeries(i,InpSwingLag,150,l,h,a,InpTouchTol))   longSig=false;
      if(shortSig && !TrendlineTouchShortSeries(i,InpSwingLag,150,l,h,a,InpTouchTol)) shortSig=false;
     }
   if(InpRequireConfluence)
     {
      if(longSig  && !CheckConfluenceDir(1,InpConfluenceWindow))  longSig=false;
      if(shortSig && !CheckConfluenceDir(-1,InpConfluenceWindow)) shortSig=false;
     }
   if(longSig && shortSig) return;
   if(!longSig && !shortSig) return;

   double extreme;
   if(longSig)
     {
      extreme = l[i];
      for(int k=1;k<=InpLookback;k++) extreme = MathMin(extreme, l[i+k]);
     }
   else
     {
      extreme = h[i];
      for(int k=1;k<=InpLookback;k++) extreme = MathMax(extreme, h[i+k]);
     }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entryPx = longSig ? ask : bid;
   double slDist = MathAbs(entryPx - extreme) + InpSLBuffer*a;
   if(slDist<=0) return;
   double sl = longSig ? (entryPx - slDist) : (entryPx + slDist);
   //--- respect the broker's minimum stop distance from the fill price;
   //--- only widens the stop if the structural one computed above is too
   //--- close, never tightens a stop that's already legally placed
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
      PrintFormat("Slipstream EA: order failed, error %d retcode %d - dir=%s entry=%.5f sl=%.5f bid=%.5f ask=%.5f minDist=%.5f",
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
      g_bestFav = 0.0;
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
   //--- per second of simulated time instead of every raw tick. In "every
   //--- tick" Strategy Tester mode a single bar can contain hundreds of
   //--- thousands of ticks, and these three each do several ObjectFind/
   //--- ObjectSet calls - unthrottled, that's what was making real-tick
   //--- runs take an hour+ instead of the ~2 minutes AuRebound (which
   //--- already throttled its panel this way) takes for a comparable
   //--- span. Same pattern already proven in Aurelius_EA.mq5/AuRebound_EA.mq5.
   //--- v1.05: that throttle was only half the fix - a non-visual Strategy
   //--- Tester pass (no chart anyone can see) was still repainting the panel
   //--- every simulated second for nothing, so this is now skipped entirely
   //--- there (g_skipCosmeticDraws), matching Aurelius/Fulcrum/Ratchet/
   //--- Zenith/Daybreak's pattern exactly. reclaim=false: this is a plain
   //--- value refresh, not a moment something else could have buried the
   //--- panel - see g_panelReclaim's declaration.
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
   //--- v1.07: one new segment per line per bar, from the same hEMA50/hEMA200/
   //--- hBBMid/hATR handles CheckForEntry() reads on the line below. Once per H4
   //--- bar, not per tick - this sits AFTER the IsNewBar() gate deliberately.
   if(!g_skipCosmeticDraws && InpShowLines) UpdateLines();
   CheckForEntry();
  }
//+------------------------------------------------------------------+
