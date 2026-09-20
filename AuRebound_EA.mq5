//+------------------------------------------------------------------+
//|                                   AuRebound_EA.mq5                |
//|                                                                  |
//|  Live-trading counterpart to AuRebound_Signals.mq5. Same         |
//|  Bollinger+Stochastic "ride the band" logic, same entry filters, |
//|  same stop -> breakeven -> MFE-lock -> band-reject/timeout exit  |
//|  ladder, same Friday weekend-gap protection. The indicator draws |
//|  what would have happened; this EA actually places the orders.   |
//|                                                                  |
//|  Signal timing matches the indicator exactly: on every new bar,  |
//|  the just-CLOSED bar (index count-2 of the copied window) is the |
//|  signal bar, and execution happens at the market right away -    |
//|  the live equivalent of the indicator's open[i+1] fill.          |
//|                                                                  |
//|  One position at a time per (symbol, magic number), matching the |
//|  indicator's single-slot pos/posDir model. Protective stops are  |
//|  real broker-side orders (continuous protection) rather than the |
//|  indicator's once-per-bar high/low check - strictly safer, same  |
//|  stop distance math.                                             |
//|                                                                  |
//|  InpUseNewsFilter (ON by default): blocks new entries around     |
//|  high-impact USD releases via MQL5's live Economic Calendar -    |
//|  NOT backtestable in the Strategy Tester (calendar history is    |
//|  live-terminal-only per MQL5's own docs), so this is pure risk   |
//|  management, same class as the Friday weekend-gap filter: no     |
//|  backtest P&L claim, just avoiding a well-documented real risk.  |
//|                                                                  |
//|  PANEL FIXES (v1.01), same class of issue found in the other EAs |
//|  this session:                                                    |
//|   - Panel width now self-learns from measured row text instead   |
//|     of a fixed InpPanelW, so a long value string can't clip.      |
//|   - PRow/PSection/DrawPanelBackground now delete+recreate their   |
//|     objects every draw cycle instead of updating in place - MT5   |
//|     stacks chart objects by creation order, not ZORDER, so a      |
//|     trade arrow/line MT5 draws after the panel already exists     |
//|     was rendering on top of it.                                   |
//|  Not touched, already correct: CSV export already covers broker-  |
//|  side SL/TP closes via the shared FinalizeClosedTrade() path (no  |
//|  separate ClosePosition()-only logging gap like Aurelius/Ratchet  |
//|  had), and the live stats panel already only tracks this EA's own |
//|  trades - no other-EA P&L leak to split out.                      |
//+------------------------------------------------------------------+
//|  v1.02: NewsBlackoutActive() called CalendarValueHistory() - a live-    |
//|  terminal-only API (this file's own header already says so) - fresh on    |
//|  every check with zero caching, a well-documented slow path in the Tester   |
//|  when hit repeatedly across a multi-year real-tick run (same fix applied     |
//|  to Tailwind_EA.mq5/Slipstream_EA.mq5 this session after a live user report    |
//|  of multi-hour runs). Since the function already "fails open" and its Tester    |
//|  result was already documented as not meaningful, now skips the call entirely     |
//|  when MQLInfoInteger(MQL_TESTER) - identical backtest behaviour, less wall-clock    |
//|  time. No signal/entry-logic change.                                                  |
//+------------------------------------------------------------------+
//|  v1.03: visual standardization pass (Aurelius/Fulcrum/Ratchet/Zenith/Daybreak's         |
//|  shared panel standard, brought to this file for the first time). Nothing here          |
//|  touches signal/entry/exit/risk logic.                                                    |
//|   - Panel border was a single OBJ_RECTANGLE_LABEL BORDER_FLAT rect - the same             |
//|     unreliable border (only 2 of 4 sides render live) already replaced everywhere         |
//|     else. Ported PRect()/PFrame() from Aurelius_EA.mq5 verbatim: an explicit 4-strip       |
//|     frame plus a drop shadow and an opaque top fill, all drawn from the new                |
//|     InpPanelBg/InpPanelEdge/InpHeaderBg/InpTitleCol/InpSectionCol/InpTextCol/InpValCol/     |
//|     InpOkCol/InpNoCol/InpShadowCol inputs - the same palette values already shipping on     |
//|     every other GOLD EA this session (Fulcrum/Ratchet/Zenith/Daybreak's neon-blue edge;      |
//|     Aurelius alone keeps a documented gold-edge exception, untouched).                        |
//|   - InpPanelY 45 -> 30, matching where every sibling EA sits (just below MT5's own              |
//|     symbol/OHLC header bar). InpPanelX (12, left-anchored) was already correct.                  |
//|   - Added InpPanelDrag + drag-to-move (CHARTEVENT_OBJECT_DRAG on the panel background),           |
//|     matching Aurelius/Fulcrum/Ratchet/Zenith/Daybreak - this panel had no drag support at all.     |
//|   - Added g_panelReclaim (Aurelius/Zenith's pattern): PRect/PText only delete+recreate            |
//|     (to reclaim top-of-stack from a newly-drawn trade tag) when explicitly told to -              |
//|     a plain value refresh just updates the same objects in place instead of a full               |
//|     panel repaint. Not a performance concern for THIS file specifically (DrawPanel() only        |
//|     ever runs once per H4 bar or on a discrete trade event here, never per-tick or per-second),   |
//|     but added for consistency with the shared primitive set and because it's the correct fix     |
//|     for the underlying object-stacking issue regardless of call frequency.                        |
//|   - Added g_skipCosmeticDraws (same flag/definition as every other EA this session):              |
//|     true only in a non-visual Strategy Tester pass. Gates the wallpaper/watermark/panel            |
//|     redraw inside ProcessNewBar() (the one call site that repeats on every bar of a whole          |
//|     backtest) - this file was never reported as slow (H4 bars are far fewer than Tailwind/         |
//|     Slipstream's per-tick redraw problem), but the same fix was checked and applied for            |
//|     consistency with the family standard rather than left as the one file without it.              |
//|                                                                                                     |
//|  v1.04 (2026-09-06): indicator visibility - this EA drew NOTHING price-related before                |
//|  (zero OBJ_TREND/OBJ_HLINE/OBJ_RECTANGLE anywhere in the file), so the Bollinger bands it            |
//|  actually trades were invisible on the chart. Purely additive chart drawing - no signal,             |
//|  entry, exit, risk or position-management logic touched, and every new draw call is gated            |
//|  behind g_skipCosmeticDraws so it can never affect a trading decision or a Tester run.               |
//|   - The three Bollinger lines (upper/mid/lower) are now drawn natively BY THIS EA as one             |
//|     OBJ_TREND segment per bar, using the family's DrawMASegment()/PurgeOldMALines()/                 |
//|     BackfillMALines() pattern from Aurelius_EA.mq5 (an EA has no plot buffers of its own -           |
//|     only an indicator can set PLOT_LINE_COLOR - so per-bar trend segments are the only way            |
//|     to get a specific colour per line). Values come from this file's own BandUpAt()/                  |
//|     BandMidAt()/BandLoAt() on the already-copied a_close[] window: the exact numbers the              |
//|     entry logic reads, not a re-derived approximation, and no extra fetch on the bar path.            |
//|     Deliberately self-contained: no dependency on AuRebound_Signals.mq5 being attached.               |
//|   - Colours (InpColBBUpper/InpColBBMid/InpColBBLower) and the dotted upper/lower styling              |
//|     are taken from AuRebound_Signals.mq5's own already-shipping plot palette, so the EA's             |
//|     bands look identical to the indicator's whether or not both are on the chart.                     |
//|   - New object prefix AURL_ (no clash with this file's AUREA_/AUREAP_ or the indicator's              |
//|     AUR_/AURP_), swept in OnDeinit alongside the existing two, and purged to a rolling                 |
//|     InpBandHistoryBars window every bar so a long-running live EA can't accumulate objects.            |
//|   - BackfillBandLines() fills the whole rolling window once from OnInit, so a fresh attach             |
//|     shows real history immediately instead of three 1-bar stubs (the same gap Aurelius                 |
//|     v1.34 fixed with BackfillMALines). It re-copies its own local close/time window rather             |
//|     than seeding the shared a_close[]/a_time[] globals - those are trading state, and                  |
//|     HandleExternalClose() can legitimately read a_time[] before the first ProcessNewBar().             |
//+------------------------------------------------------------------+
#property copyright "AuRebound"
#property version   "1.04"
#property strict

#include <Trade\Trade.mqh>

enum ENUM_STOCH_MODE
  {
   MODE_THRESHOLD_CROSS = 0,   // Must fully cross 20/80 + persistence (fewer, higher-conviction)
   MODE_SIGNAL_LINE_TURN = 1   // Just the %D line turning, no threshold (more trades, DEFAULT - best total net)
  };

input group "=== Bollinger Bands ==="
input int    InpBBPeriod    = 20;
input double InpBBDev       = 2.0;

input group "=== Stochastic ==="
input ENUM_STOCH_MODE InpStochMode = MODE_SIGNAL_LINE_TURN;
input int    InpStochK      = 21;    // %K period
// CORRECTED (2026-09-06, Opus deep-dive review): these two labels were
// swapped - iStochastic(...)'s signature is (Kperiod, Dperiod, slowing),
// and the actual call below passes (InpStochK, InpStochD, InpStochSlow),
// so InpStochD is really the %D period and InpStochSlow is really the
// slowing. Harmless at the shipped defaults (both 5), wrong the moment
// either is changed independently. Documentation only - the argument
// order itself is correct and matches AuRebound_Signals.mq5's identical
// call, so it is NOT changed here (that would break validation).
input int    InpStochD      = 5;     // %D period
input int    InpStochSlow   = 5;     // %K slowing
input bool   InpUsePersistFilter = true;   // THRESHOLD mode only - ignored in SIGNAL_LINE_TURN mode
input int    InpMinPersistBars = 4;

input group "=== Entry ==="
input double InpEntryProx   = 0.5;    // Band proximity, x ATR
input int    InpATRPeriod   = 14;
input int    InpLookback    = 3;
input bool   InpBlockIndecision = false;  // Validated OFF for SIGNAL_LINE_TURN, ON helped THRESHOLD_CROSS

input group "=== Exit ==="
input double InpSLBuffer    = 0.5;
input bool   InpUseSLCap    = true;
input double InpSLCapATR    = 1.5;
input double InpMFELockFrac = 0.70;
input int    InpMaxHoldBars = 120;
input int    InpCooldown    = 2;

input group "=== Session filter ==="
input bool   InpUseSessionFilter = true;
input int    InpBlockedHour = 8;     // Leave-one-fold-out validated (see indicator header notes)
input bool   InpBlockFridayClose = true;
input int    InpFridayCloseHour  = 16;   // Block new entries on Friday from this hour onward
input bool   InpUseSessionScheduleFilter = true;  // Skip entries outside the broker's published trading session. Toggle OFF to compare against pre-fix behavior.

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

input group "=== Trading ==="
input long   InpMagicNumber   = 800001;
input double InpLots          = 0.01;
input int    InpSlippagePoints = 30;
input string InpTradeComment  = "AuRebound";
input int    InpMarketClosedRetries   = 5;   // fallback for closures the session schedule doesn't list (e.g. unscheduled holiday)
input int    InpMarketClosedRetryDelaySec = 2;
input int    InpPendingMaxWaitMinutes = 60;  // give up on a queued signal if the market hasn't reopened within this long (protects against chasing a stale, badly-gapped price)
input int    InpPendingRetryDelaySec = 30;   // throttle for a queued order NOT gated on the schedule (transient failure, or InpUseSessionScheduleFilter off) - kept longer than InpMarketClosedRetryDelaySec since these retries are real broker network calls with no cheap local check backing them off

input group "=== Export ==="
input bool   InpExportCSV = false;
input string InpExportTag = "";

input group "=== Display ==="
// Unified with Slipstream/Tailwind's neon blue/white palette - was a distinct
// spring-green/hot-pink/royal-blue scheme (steered away from this wallpaper's
// gold/amber to avoid merging into the artwork). Now matching across all
// three EAs so the systems read as one family.
input bool   InpShowMarkers = true;
input color  InpColBuy      = C'0,150,255';     // neon blue - matches Slipstream/Tailwind (was spring green)
input color  InpColSell     = clrWhite;         // neon white - matches Slipstream/Tailwind (was hot pink-crimson)
input color  InpColExitProfit   = C'0,255,140';    // neon green - matches Slipstream/Tailwind (was pure white)
input color  InpColExitBEorLoss = C'255,60,120';   // neon red-pink - matches Slipstream/Tailwind (was royal blue)
input bool   InpSetCandleColors = true;   // recolors the ENTIRE chart's candles to match the marker palette - affects any other indicator sharing this chart too
input color  InpCandleUp    = C'0,150,255';     // same neon blue as InpColBuy, so candles and markers read as one system
input color  InpCandleDown  = clrWhite;         // same neon white as InpColSell
input color  InpChartBG     = clrBlack;
input int    InpFont        = 9;
input bool   InpShowPanel   = true;
input int    InpPanelDrag   = 1;     // 0 = locked, 1 = draggable - matches Aurelius/Fulcrum/Ratchet/Zenith/Daybreak
input int    InpPanelX      = 12;    // distance from the chart's LEFT edge - matches Slipstream/Tailwind (was right-anchored)
input int    InpPanelY      = 30;    // distance down from the top edge - was 45, now matches the family
                                      // standard (Aurelius/Fulcrum/Ratchet/Zenith/Daybreak all sit at 30,
                                      // just below MT5's own symbol/OHLC header bar)
input int    InpPanelW      = 270;
input int    InpPanelSize   = 8;
input color  InpPanelBg     = C'13,17,28';       // panel background - matches the shared family palette
input color  InpHeaderBg    = C'28,36,58';       // section/title band background
input color  InpPanelEdge   = C'0,150,255';      // panel border - neon blue, matches Fulcrum/Ratchet/Zenith/Daybreak
                                                  // (Aurelius alone uses gold as a documented exception)
input color  InpTitleCol    = C'255,196,84';     // title text - gold, matches Aurelius/Zenith
input color  InpSectionCol  = C'214,226,238';    // section headings - silver
input color  InpTextCol     = C'150,166,192';    // row labels
input color  InpValCol      = C'236,242,252';    // row values (neutral state)
input color  InpOkCol       = C'0,230,118';      // row value - good/on state, neon green
input color  InpNoCol       = C'255,61,90';      // row value - bad/off state, hot red
input color  InpShadowCol   = C'6,8,14';         // drop shadow behind the panel

input group "=== Indicator lines (v1.04) ==="
// Cosmetic only - these draw the SAME Bollinger values CheckForEntry()/
// NearUpperAt()/NearLowerAt() already read (BandUpAt/BandMidAt/BandLoAt on
// a_close[]), never a separately-computed copy, and every call site is gated
// behind g_skipCosmeticDraws. Colours/styles match AuRebound_Signals.mq5's
// own plot palette so the EA's lines and the indicator's look identical.
input bool   InpShowBands   = true;   // Draw the Bollinger upper/mid/lower this EA actually trades
input int    InpBandHistoryBars = 500;  // How many recent bars of band history to keep drawn (bounded, so a
                                         // long-running live EA doesn't accumulate objects forever). 500 H4
                                         // bars is ~3 months.
input color  InpColBBUpper  = C'0,225,255';     // upper band - electric cyan (drawn dotted, as in the indicator)
input color  InpColBBMid    = C'190,195,205';   // midline - cool silver, neutral reference line
input color  InpColBBLower  = C'170,90,255';    // lower band - electric violet (drawn dotted, as in the indicator)

input group "=== Wallpaper / Watermark ==="
input bool   InpShowWallpaper = true;
input string InpBackgroundBMP = "AuRebound_Wallpaper.bmp";   // .bmp file, must be placed in MQL5\Images\
input int    InpBgWidth  = 1290;
input int    InpBgHeight = 720;
input bool   InpShowWatermark = true;
input string InpWatermarkText = "AuRebound";   // was "AuRebound EA" - now matches the indicator and the Slipstream/Tailwind convention (plain name, no "EA" suffix)
input bool   InpWaterBottom = true;
input color  InpWatermarkColor = C'46,38,24';
input int    InpWatermarkSize  = 42;
input string InpWaterFont = "Arial Black";

//--- indicator handles
int    hATR=INVALID_HANDLE, hStoch=INVALID_HANDLE;

//--- object name prefixes - deliberately different from the indicator's AUR_/AURP_
//--- so the EA and the indicator can run on the same chart without colliding
string g_prefix = "AUREA_";
string g_pp     = "AUREAP_";
//--- v1.04: per-bar Bollinger line segments, purged to a rolling window - see
//--- DrawBandSegment/PurgeOldBandLines/UpdateBandLines. Deliberately NOT a
//--- sub-string of g_prefix/g_pp (both start "AUREA") or of the indicator's
//--- AUR_/AURP_, so ObjectsDeleteAll on any of those can never sweep these and
//--- vice versa - each prefix owns exactly its own objects.
string g_pl     = "AURL_";
bool   g_bgOK = false;
int    g_bgTries = 0;
//--- PERFORMANCE: true only in a non-visual Strategy Tester pass (no chart
//--- anyone can see) - same flag/definition as every other EA this session.
//--- Gates the repeated wallpaper/watermark/panel redraw in ProcessNewBar().
bool   g_skipCosmeticDraws = false;

//--- live trade stats (real fills, not a backtest replay - accumulated as the EA trades)
int    g_n=0, g_win=0, g_loss=0, g_nBuy=0, g_nSell=0;
double g_net=0.0, g_gWin=0.0, g_gLoss=0.0;

//--- rolling calculation window (chronological, index[0]=oldest of the window)
#define HIST_BARS 500
datetime a_time[]; double a_open[], a_high[], a_low[], a_close[];
double   a_atr[], a_std[];

//--- position/trade state (single slot, mirrors the indicator's pos/posDir/stage2/bestFav)
CTrade trade;
bool     posOpen=false;
int      posDir=0;              // +1 long, -1 short
double   entryPx=0.0, entrySL=0.0, entryATR=0.0;
bool     stage2=false;
double   bestFav=0.0;
int      barsInTrade=0;
ulong    posTicket=0;
// exact bar-index cooldown, matching the indicator's "i <= cooldown_until" (inclusive)
// semantics - blocks exactly InpCooldown bars after an exit, same as the indicator,
// rather than a decrement-then-check counter which was blocking one bar too few.
long     g_barCounter=0;
long     g_cooldownUntilBar=-1;

// a signal that passed every filter but hit a market-closed order rejection
// is queued here rather than dropped, and fired the moment CanFillAt() goes
// true again - checked on every tick, not just new-bar ticks, so it fires as
// soon as possible after the market actually reopens. slDist is frozen at
// signal time (same distance the indicator's backtest would have used), then
// applied relative to whatever the live price actually is when it fires.
bool     g_pendingOrder=false;
int      g_pendingDir=0;
double   g_pendingSLDist=0.0;
double   g_pendingATR=0.0;   // ATR that slDist was actually computed from - kept consistent through to entryATR on fill
datetime g_pendingSince=0;
// true only when the reason for waiting is the session schedule (gate retries
// on CanFillAt()); false for a transient failure unrelated to it (REQUOTE,
// CONNECTION, ...), where gating on the schedule would be wrong - especially
// if the user has InpUseSessionScheduleFilter off, in which case the schedule
// shouldn't be consulted at all. Retried on a plain time throttle instead.
bool     g_pendingScheduleGated=false;
datetime g_pendingLastAttempt=0;

int      g_fh = INVALID_HANDLE;
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
double Sma(const double &arr[], int i, int period)
  {
   if(i<period-1) return(EMPTY_VALUE);
   double s=0; for(int k=0;k<period;k++) s+=arr[i-k]; return(s/period);
  }
double StdDev(const double &arr[], int i, int period, double mean)
  {
   if(i<period-1) return(EMPTY_VALUE);
   double s=0; for(int k=0;k<period;k++) { double d=arr[i-k]-mean; s+=d*d; } return(MathSqrt(s/period));
  }
//+------------------------------------------------------------------+
bool IsIndecisionCandle(const int i, const double &open[], const double &high[],
                        const double &low[], const double &close[])
  {
   double rng = high[i]-low[i];
   if(rng<=0) return(false);
   double body = MathAbs(close[i]-open[i]);
   double upperWick = high[i] - MathMax(open[i],close[i]);
   double lowerWick = MathMin(open[i],close[i]) - low[i];
   double bodyRatio = body/rng;
   return(bodyRatio < 0.35 && upperWick > 0.2*rng && lowerWick > 0.2*rng);
  }
//+------------------------------------------------------------------+
int StochPersistence(const int i, const bool below20, const double &stD[])
  {
   int cnt=0; int j=i-1;
   while(j>0 && stD[j]!=EMPTY_VALUE)
     {
      if(below20 && stD[j]<20.0) { cnt++; j--; }
      else if(!below20 && stD[j]>80.0) { cnt++; j--; }
      else break;
     }
   return(cnt);
  }
//+------------------------------------------------------------------+
// Same schedule check as the indicator - avoids attempting an order at a
// moment the broker's own published session schedule marks as closed
// (e.g. a continuous-contract symbol's daily rollover break). Not exhaustive
// (unscheduled holidays etc. aren't in the schedule), so SendOrder() still
// carries a short bounded retry, and TryFulfillPending() a longer queued
// wait, as fallbacks for anything this misses.
bool CanFillAt(const datetime t)
  {
   MqlDateTime dt; TimeToStruct(t, dt);
   long todaySecs = dt.hour*3600 + dt.min*60 + dt.sec;
   for(uint s=0; ; s++)
     {
      datetime from, to;
      if(!SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)dt.day_of_week, s, from, to)) break;
      long fromSecs = (long)from % 86400;
      long toRaw = (long)to % 86400;
      // a session ending exactly at midnight (to=86400, e.g. a 00:00-24:00
      // "all day" session, common for near-continuous CFD symbols) reduces to
      // 0 under a plain %86400 - which would make toSecs < fromSecs and the
      // range never match, wrongly reporting the market closed all day
      long toSecs = (toRaw==0 && to>from) ? 86400 : toRaw;
      if(to==from) continue;   // zero-width/malformed session row - never tradeable, not "all day"
      if(toSecs > fromSecs)
        {
         if(todaySecs>=fromSecs && todaySecs<toSecs) return(true);
        }
      else
        {
         // overnight session wrapping past midnight (to time-of-day < from)
         if(todaySecs>=fromSecs || todaySecs<toSecs) return(true);
        }
     }
   return(false);
  }
//+------------------------------------------------------------------+
// Only these are worth retrying a queued order against - genuinely transient,
// timing/connectivity-shaped failures. Anything else (no money, invalid
// stops, trade disabled, wrong volume, hedge prohibited, ...) will fail
// identically on every retry, so retrying it every tick for up to
// InpPendingMaxWaitMinutes would just hammer the broker for nothing - drop
// those immediately instead.
bool IsRetryableRetcode(const int code)
  {
   switch(code)
     {
      case TRADE_RETCODE_REQUOTE:
      case TRADE_RETCODE_PRICE_CHANGED:
      case TRADE_RETCODE_PRICE_OFF:
      case TRADE_RETCODE_TIMEOUT:
      case TRADE_RETCODE_CONNECTION:
      case TRADE_RETCODE_MARKET_CLOSED:
      case TRADE_RETCODE_TOO_MANY_REQUESTS:
      case TRADE_RETCODE_FROZEN:
         return(true);
      default:
         return(false);
     }
  }
//+------------------------------------------------------------------+
bool TurnUpAt(const int i, const double &stD[])
  {
   if(i<2 || stD[i]==EMPTY_VALUE || stD[i-1]==EMPTY_VALUE || stD[i-2]==EMPTY_VALUE) return(false);
   if(InpStochMode==MODE_SIGNAL_LINE_TURN)
      return(stD[i]>stD[i-1] && stD[i-1]<=stD[i-2]);
   return(stD[i-1]<20.0 && stD[i]>=20.0);
  }
bool TurnDnAt(const int i, const double &stD[])
  {
   if(i<2 || stD[i]==EMPTY_VALUE || stD[i-1]==EMPTY_VALUE || stD[i-2]==EMPTY_VALUE) return(false);
   if(InpStochMode==MODE_SIGNAL_LINE_TURN)
      return(stD[i]<stD[i-1] && stD[i-1]>=stD[i-2]);
   return(stD[i-1]>80.0 && stD[i]<=80.0);
  }
//+------------------------------------------------------------------+
double BandUpAt(const int i) { double m=Sma(a_close,i,InpBBPeriod); if(m==EMPTY_VALUE) return(EMPTY_VALUE); return(m+InpBBDev*StdDev(a_close,i,InpBBPeriod,m)); }
double BandLoAt(const int i) { double m=Sma(a_close,i,InpBBPeriod); if(m==EMPTY_VALUE) return(EMPTY_VALUE); return(m-InpBBDev*StdDev(a_close,i,InpBBPeriod,m)); }
double BandMidAt(const int i){ return(Sma(a_close,i,InpBBPeriod)); }

bool NearUpperAt(const int i)
  {
   double up=BandUpAt(i);
   if(up==EMPTY_VALUE || a_atr[i]<=0.0) return(false);
   return(a_high[i] >= up - InpEntryProx*a_atr[i]);
  }
bool NearLowerAt(const int i)
  {
   double lo=BandLoAt(i);
   if(lo==EMPTY_VALUE || a_atr[i]<=0.0) return(false);
   return(a_low[i] <= lo + InpEntryProx*a_atr[i]);
  }
//+------------------------------------------------------------------+
double NormalizeLots(double lots)
  {
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathRound(lots/step)*step;
   return(MathMax(minL, MathMin(maxL, lots)));
  }
//+------------------------------------------------------------------+
bool FindOwnPosition(ulong &ticket)
  {
   for(int i=PositionsTotal()-1; i>=0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol && (long)PositionGetInteger(POSITION_MAGIC)==InpMagicNumber)
        { ticket=tk; return(true); }
     }
   return(false);
  }
//+------------------------------------------------------------------+
// Used when SendOrder() finds a position already exists (an ambiguous
// TIMEOUT/CONNECTION retry that actually filled at the broker) - adopts it
// into the EA's own state instead of sending a duplicate live order.
bool AdoptFoundPosition(const ulong tk, const int dir, const double atrForEntry)
  {
   if(!PositionSelectByTicket(tk))
     {
      // gone between FindOwnPosition()'s scan and here (closed in the same
      // instant, e.g. by SL/TP or manually) - don't adopt zeroed/stale field
      // reads as a real position, let the caller fall through to a normal send
      Print("AuRebound EA: position #", tk, " vanished before it could be adopted - trying a fresh send instead");
      return(false);
     }
   // trust the POSITION's actual side, not the direction we were attempting -
   // a stray position sharing this symbol/magic (leftover from a prior run, a
   // manual trade, another process reusing the magic number) could be on the
   // opposite side, and blindly assuming `dir` would then manage a real
   // position with an inverted stage2/exit logic
   int realDir = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? 1 : -1;
   if(realDir != dir)
      Print("AuRebound EA: WARNING - found position #", tk, " is ", (realDir>0?"LONG":"SHORT"),
            " but a ", (dir>0?"BUY":"SELL"), " was being attempted - adopting its REAL side, not the attempted one");

   posOpen=true; posDir=realDir; posTicket=tk;
   entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
   entrySL = PositionGetDouble(POSITION_SL);
   entryATR = atrForEntry;
   stage2 = (realDir>0) ? (entrySL >= entryPx - _Point) : (entrySL <= entryPx + _Point);
   bestFav = 0.0;
   barsInTrade = 0;   // best-effort - exact bars-since-entry unknown here, resumes counting from now
   if(realDir>0) g_nBuy++; else g_nSell++;
   g_pendingOrder=false; g_pendingScheduleGated=false;
   Print("AuRebound EA: found an existing position #", tk,
         " while attempting a fill - adopting it instead of sending a duplicate order");
   DrawPanel();
   SavePendingState();
   return(true);
  }
//+------------------------------------------------------------------+
void OpenExport()
  {
   if(!InpExportCSV) return;
   string fn = "AuRebound_EA_Trades_" + _Symbol;
   if(InpExportTag != "") fn += "_" + InpExportTag;
   fn += ".csv";
   // Plain MQL5\Files\ - same as the indicator, which has always worked
   // reliably. FILE_COMMON was a detour: it helps nothing inside the Strategy
   // Tester (each agent is sandboxed regardless, so the file just ends up
   // under a differently-named subfolder of the same per-agent tree either
   // way), and on a live/demo chart it would put the EA's export in a
   // different folder than the indicator's for no good reason. Live/demo:
   // this terminal's own MQL5\Files\, same as the indicator. In the tester:
   // the agent's MQL5\Files\ - search the Data Folder for the filename,
   // since the exact agent folder isn't predictable.
   bool exists = FileIsExist(fn);
   g_fh = FileOpen(fn, FILE_WRITE|FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(g_fh == INVALID_HANDLE) { Print("AuRebound EA export failed ", GetLastError()); return; }
   //--- print the fully resolved path rather than leave it to guesswork -
   //--- whether FILE_COMMON actually escapes Strategy Tester sandboxing
   //--- is disputed even between this file and Aurelius/Ratchet_EA.mq5
   //--- (both switched to FILE_COMMON this session; this one deliberately
   //--- didn't, per the comment above), so settle it in the log instead
   //--- of by theory: this line always tells you exactly where the file
   //--- landed for this specific run.
   PrintFormat("AuRebound EA: CSV export -> %s\\MQL5\\Files\\%s",
               TerminalInfoString(TERMINAL_DATA_PATH), fn);
   FileSeek(g_fh, 0, SEEK_END);
   if(!exists)
     {
      string modeStr = (InpStochMode==MODE_THRESHOLD_CROSS) ? "ThresholdCross" : "SignalLineTurn";
      FileWrite(g_fh, "settings",
         StringFormat("mode=%s BB=%d/%.1f ATR=%d Stoch=%d/%d/%d entryProx=%.2f slBuffer=%.2f maxHold=%d magic=%d",
                      modeStr, InpBBPeriod, InpBBDev, InpATRPeriod, InpStochK, InpStochD, InpStochSlow,
                      InpEntryProx, InpSLBuffer, InpMaxHoldBars, InpMagicNumber));
      FileWrite(g_fh, "entry_time","exit_time","dir","entry_px","exit_px","bars_held","pnl","exit_reason");
     }
  }
void LogTrade(datetime entryT, datetime exitT, int dir, double ePx, double xPx, int bars, double pnl, string reason)
  {
   if(g_fh==INVALID_HANDLE) return;
   FileSeek(g_fh, 0, SEEK_END);
   FileWrite(g_fh, TimeToString(entryT,TIME_DATE|TIME_MINUTES), TimeToString(exitT,TIME_DATE|TIME_MINUTES),
             (dir>0?"BUY":"SELL"), DoubleToString(ePx,_Digits), DoubleToString(xPx,_Digits),
             (string)bars, DoubleToString(pnl,2), reason);
   FileFlush(g_fh);
  }
//+------------------------------------------------------------------+
// Persists the pending-order queue across an EA/terminal restart - a queued
// signal only lived in memory otherwise, so a VPS reboot or MT5 update during
// exactly the kind of closure window this feature targets (weekend, broker
// maintenance) would silently lose it with no recovery, unlike an already-
// open position (which OnInit() recovers from the broker itself).
string PendingFileName()
  {
   // sanitize - a symbol containing '/', '\', ':' etc. (seen on some brokers,
   // e.g. crypto pairs) would otherwise be read by FileOpen as a path
   // separator and silently write/read the wrong location entirely
   string sym = _Symbol;
   string bad = "\\/:*?\"<>|";
   for(int k=0; k<StringLen(bad); k++)
      StringReplace(sym, StringSubstr(bad,k,1), "_");
   // include the timeframe - two instances of this EA on the same symbol/magic
   // but different periods would otherwise silently clobber each other's
   // pending-order file (each one's slDist/ATR/bar structure is period-specific)
   return "AuRebound_EA_Pending_" + sym + "_" + EnumToString((ENUM_TIMEFRAMES)_Period) + "_" + (string)InpMagicNumber + ".dat";
  }
void SavePendingState()
  {
   int fh = FileOpen(PendingFileName(), FILE_WRITE|FILE_BIN);
   if(fh==INVALID_HANDLE)
     {
      Print("AuRebound EA: failed to save pending-order state, error ", GetLastError(),
            " - a queued signal would NOT survive an EA/terminal restart right now");
      return;
     }
   FileWriteInteger(fh, g_pendingOrder ? 1 : 0);
   FileWriteInteger(fh, g_pendingDir);
   FileWriteDouble(fh, g_pendingSLDist);
   FileWriteDouble(fh, g_pendingATR);
   FileWriteLong(fh, (long)g_pendingSince);
   FileWriteInteger(fh, g_pendingScheduleGated ? 1 : 0);
   FileClose(fh);
  }
void LoadPendingState()
  {
   if(!FileIsExist(PendingFileName())) return;
   int fh = FileOpen(PendingFileName(), FILE_READ|FILE_BIN);
   if(fh==INVALID_HANDLE)
     {
      Print("AuRebound EA: pending-order state file exists but failed to open, error ", GetLastError());
      return;
     }
   bool has   = FileReadInteger(fh)!=0;
   int  dir   = FileReadInteger(fh);
   double sl  = FileReadDouble(fh);
   double atr = FileReadDouble(fh);
   datetime since = (datetime)FileReadLong(fh);
   bool schedGated = FileIsEnding(fh) ? false : (FileReadInteger(fh)!=0);   // tolerate an older file without this field
   FileClose(fh);
   if(!has) return;

   // sanity-check before trusting this enough to fire a live order - a file
   // left truncated by an abrupt kill (VPS power loss, forced termination)
   // between writes could otherwise resurrect garbage as a real signal
   bool sane = (dir==1 || dir==-1) && sl>0.0 && atr>0.0 &&
               since>0 && since<=TimeCurrent()+60 &&
               (TimeCurrent()-since) <= InpPendingMaxWaitMinutes*60;
   if(!sane)
     {
      Print("AuRebound EA: pending-order state file failed sanity check (dir=", dir, " slDist=", sl,
            " atr=", atr, " since=", since, ") - discarding rather than trusting it");
      return;
     }

   g_pendingOrder=true; g_pendingDir=dir; g_pendingSLDist=sl; g_pendingATR=atr; g_pendingSince=since;
   // if the user has since turned the schedule filter off, don't let a
   // restored flag from before the restart keep gating retries on it
   g_pendingScheduleGated = schedGated && InpUseSessionScheduleFilter;
   Print("AuRebound EA: recovered a pending ", (dir>0?"BUY":"SELL"), " queued at ",
         TimeToString(since,TIME_DATE|TIME_MINUTES), " from before restart");
  }
//+------------------------------------------------------------------+
void DrawWatermark()
  {
   string nm = g_prefix+"WM";
   if(InpWatermarkText == "")
     { if(ObjectFind(0,nm)>=0) ObjectDelete(0,nm); return; }
   if(ObjectFind(0,nm)<0) ObjectCreate(0,nm,OBJ_LABEL,0,0,0);
   int cw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int ch = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
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
   ObjectSetString (0,nm,OBJPROP_TEXT,InpWatermarkText);
   ObjectSetString (0,nm,OBJPROP_FONT,InpWaterFont);
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
   if(InpBackgroundBMP == "")
     { if(ObjectFind(0,nm)>=0) ObjectDelete(0,nm); g_bgOK = true; return; }
   if(g_bgOK) return;
   if(g_bgTries > 40) return;

   g_bgTries++;
   if(ObjectFind(0,nm)>=0) ObjectDelete(0,nm);
   if(!ObjectCreate(0,nm,OBJ_BITMAP_LABEL,0,0,0))
     { Print("AuRebound EA BG: ObjectCreate failed, error ", GetLastError()); return; }

   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0,nm,OBJPROP_BMPFILE,0,path);
   int err = GetLastError();

   if(!okSet || err != 0)
     {
      if(g_bgTries <= 3)
         PrintFormat("AuRebound EA BG try %d: failed to load \"%s\"  set=%s  error=%d"
                     "  -> file must be at <data folder>\\MQL5\\Images\\%s",
                     g_bgTries, path, (okSet?"true":"false"), err, InpBackgroundBMP);
      ObjectDelete(0,nm);
      return;
     }

   int cw  = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int chh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   ObjectSetInteger(0,nm,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,nm,OBJPROP_XDISTANCE, MathMax(0,(cw-InpBgWidth)/2));
   ObjectSetInteger(0,nm,OBJPROP_YDISTANCE, MathMax(0,(chh-InpBgHeight)/2));
   ObjectSetInteger(0,nm,OBJPROP_BACK,true);
   ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
   g_bgOK = true;
   if(ObjectFind(0, g_prefix+"WM")>=0) ObjectDelete(0, g_prefix+"WM");
   if(InpShowWatermark) DrawWatermark();
   PrintFormat("AuRebound EA BG: loaded \"%s\" on try %d", path, g_bgTries);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
void DrawTag(const string nm, const datetime t, const double price, const string txt,
             const color clr, const int anchor)
  {
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetString (0, nm, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpFont);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
  }
//+------------------------------------------------------------------+
//| v1.04 - Bollinger band lines, drawn natively by this EA.            |
//|                                                                     |
//| An EA has no plot buffers (only an indicator can set PLOT_LINE_COLOR)|
//| and ChartIndicatorAdd() would only ever show MT5's own auto-assigned |
//| colours, never a specific one per line - so each band is drawn as    |
//| one OBJ_TREND segment per bar, bar[i-1] -> bar[i], exactly the idiom |
//| Aurelius_EA.mq5's DrawMASegment() already uses for its five MAs and  |
//| VWAP. Old segments are swept by PurgeOldBandLines() so a long-       |
//| running live EA doesn't accumulate objects forever.                  |
//| Called only from inside a g_skipCosmeticDraws guard, same as every   |
//| other cosmetic draw in this file.                                    |
//+------------------------------------------------------------------+
void DrawBandSegment(const string tag, const datetime tOld, const double vOld,
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
                                                        // up to 3*InpBandHistoryBars of these exist
  }
//+------------------------------------------------------------------+
void PurgeOldBandLines(const datetime latestBarTime)
  {
   datetime cutoff = latestBarTime - (datetime)((long)InpBandHistoryBars * PeriodSeconds(PERIOD_CURRENT));
   for(int k = ObjectsTotal(0, 0, OBJ_TREND) - 1; k >= 0; k--)
     {
      string nm = ObjectName(0, k, 0, OBJ_TREND);
      if(StringFind(nm, g_pl) != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < cutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
//| One new bar's worth of band segment, drawn from the SAME BandUpAt/  |
//| BandMidAt/BandLoAt values CheckForEntry() reads on this bar - the   |
//| chart shows the actual numbers the decision was made on, not a      |
//| re-derived copy. `i` is ProcessNewBar()'s signal-bar index, so this |
//| needs no fetch of its own: a_close[]/a_time[] are already populated  |
//| for this bar, and i-1 is guaranteed valid (i >= warmup >> 1).        |
//+------------------------------------------------------------------+
void UpdateBandLines(const int i)
  {
   if(i < 1) return;
   datetime tA = a_time[i-1], tB = a_time[i];
   if(tA == 0 || tB == 0) return;

   double uA = BandUpAt(i-1),  uB = BandUpAt(i);
   double mA = BandMidAt(i-1), mB = BandMidAt(i);
   double lA = BandLoAt(i-1),  lB = BandLoAt(i);
   //--- Sma()/StdDev() return EMPTY_VALUE below their own warm-up length;
   //--- draw each line only when BOTH of its endpoints are real.
   if(uA != EMPTY_VALUE && uB != EMPTY_VALUE) DrawBandSegment("up",  tA, uA, tB, uB, InpColBBUpper, STYLE_DOT);
   if(mA != EMPTY_VALUE && mB != EMPTY_VALUE) DrawBandSegment("mid", tA, mA, tB, mB, InpColBBMid,   STYLE_SOLID);
   if(lA != EMPTY_VALUE && lB != EMPTY_VALUE) DrawBandSegment("lo",  tA, lA, tB, lB, InpColBBLower, STYLE_DOT);

   PurgeOldBandLines(tB);
  }
//+------------------------------------------------------------------+
//| UpdateBandLines() only ever draws ONE bar's worth of segment per     |
//| call, so a fresh attach would show three 1-bar stubs and take        |
//| InpBandHistoryBars bars (500 H4 bars = ~3 months) to fill in the     |
//| window the input claims to be showing - the same gap Aurelius v1.34  |
//| closed with BackfillMALines(). Called once from OnInit instead, this |
//| walks the whole rolling window in one pass.                          |
//|                                                                      |
//| Uses its own LOCAL time/close window rather than the shared a_time[]/ |
//| a_close[] globals on purpose: those are trading state owned by        |
//| ProcessNewBar(), and HandleExternalClose() can legitimately run off a |
//| tick before the first ProcessNewBar() ever fills them (the empty-     |
//| array case the 2026-09-06 review explicitly added guards for). Seeding|
//| them here would silently change which branch that guard takes.        |
//| Same shift-1-minimum, no-lookahead indexing as the live path - the    |
//| still-forming bar 0 is never touched.                                |
//+------------------------------------------------------------------+
void BackfillBandLines()
  {
   //--- InpBBPeriod extra bars beyond the window itself: the OLDEST segment's
   //--- older endpoint still needs a full InpBBPeriod of closes behind it for
   //--- Sma()/StdDev() to return a real value rather than EMPTY_VALUE.
   //--- CopyTime clamps to whatever history is actually loaded, so a short
   //--- read just yields a shorter window - never an out-of-range index.
   int want = InpBandHistoryBars + InpBBPeriod + 2;
   datetime bt[]; double bc[];
   int copied = CopyTime(_Symbol, PERIOD_CURRENT, 0, want, bt);
   if(copied < InpBBPeriod + 2) return;
   if(CopyClose(_Symbol, PERIOD_CURRENT, 0, copied, bc) < copied) return;
   ArraySetAsSeries(bt, false); ArraySetAsSeries(bc, false);

   int last  = copied - 2;                                   // last CLOSED bar
   int first = MathMax(InpBBPeriod, last - InpBandHistoryBars + 1);
   for(int s = first; s <= last; s++)
     {
      if(bt[s-1] == 0 || bt[s] == 0) continue;
      double mA = Sma(bc, s-1, InpBBPeriod), mB = Sma(bc, s, InpBBPeriod);
      if(mA == EMPTY_VALUE || mB == EMPTY_VALUE) continue;
      double dA = StdDev(bc, s-1, InpBBPeriod, mA), dB = StdDev(bc, s, InpBBPeriod, mB);
      if(dA == EMPTY_VALUE || dB == EMPTY_VALUE) continue;
      //--- same expressions as BandUpAt/BandMidAt/BandLoAt, just against the
      //--- local window instead of the shared a_close[] one.
      DrawBandSegment("up",  bt[s-1], mA+InpBBDev*dA, bt[s], mB+InpBBDev*dB, InpColBBUpper, STYLE_DOT);
      DrawBandSegment("mid", bt[s-1], mA,             bt[s], mB,             InpColBBMid,   STYLE_SOLID);
      DrawBandSegment("lo",  bt[s-1], mA-InpBBDev*dA, bt[s], mB-InpBBDev*dB, InpColBBLower, STYLE_DOT);
     }
  }
//+------------------------------------------------------------------+
//--- rough monospace-ish width estimate, same formula used across the
//--- other EAs' panels for consistency
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
//--- self-learning minimum panel width: PRow updates this as each row's
//--- real text is measured, and the NEXT DrawPanel() call uses it - lags
//--- one draw cycle behind (well under a second in practice) rather than
//--- needing a full two-pass restructure, and means no row can ever clip
//--- regardless of how long a value string gets.
int g_panelMinW = 0;
//--- draggable panel position - matches Aurelius/Zenith. -1 means "not yet
//--- placed"; DrawPanel() seeds it from InpPanelX/InpPanelY on first draw.
int  g_panX = -1, g_panY = -1;
//--- Controls whether PRect/PText delete-and-recreate (to reclaim top-of-
//--- stack - see PRect's own comment) or just update the existing object's
//--- properties in place. True only right after something else could have
//--- buried the panel (a new trade tag) - everything in between just
//--- updates values, so a live refresh doesn't flash the whole panel the
//--- way a full delete+recreate would. Same pattern as Aurelius_EA.mq5/
//--- Zenith_EA.mq5's g_panelReclaim; see the v1.03 header note for why this
//--- is added here even though this file has no per-tick/per-second redraw.
bool g_panelReclaim = true;
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
   string nm = g_pp + id;
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
   string nm = g_pp + id;
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
void PRow(const string id, const int x, const int y, const int w,
          const string label, const string val, const int state)
  {
   color c = (state==1) ? InpOkCol : (state==0 ? InpNoCol : InpValCol);
   PText(id + "L", x, y, label, InpTextCol);
   PText(id + "V", x + w - 8, y, val, c, 0, true);
   //--- learn the width this row actually needed, for next draw cycle
   int need = EstimateTextWidth(label, InpPanelSize) + 16
              + EstimateTextWidth(val, InpPanelSize) + 20;
   if(need > g_panelMinW) g_panelMinW = need;
  }
//+------------------------------------------------------------------+
//| Section heading on its own tinted band. isTitle colors the text gold     |
//| (InpTitleCol) instead of silver (InpSectionCol) - used for the single     |
//| top banner row only, matching Aurelius/Zenith's title/section split.       |
//+------------------------------------------------------------------+
void PSection(const string id, const int x, const int y, const int w,
              const string title, const bool isTitle = false)
  {
   int rh = InpPanelSize + 11;
   //--- band created first, label second, or the band hides the label
   PRect(id + "bar", x + 1, y - 3, w - 2, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x + 10, y, title, isTitle ? InpTitleCol : InpSectionCol,
         InpPanelSize + 1, false, "Consolas Bold");
  }
void DrawPanelBackground(int x, int y, int w, int hgt)
  {
   int bx = x - 8, by = y - 8, bw = w + 16, bh = hgt + 16;
   //--- frame first, so everything else draws on top of it
   PRect("sh", bx + 4, by + 4, bw, bh, InpShadowCol, InpShadowCol, 0);
   PRect("bg", bx,     by,     bw, bh, InpPanelBg,   InpPanelBg,   0);
   //--- "bg" keeps its identity across cycles (so dragging works) - "fl" is
   //--- an identical opaque fill drawn on top of it EVERY cycle, so a trade
   //--- tag drawn since the last reclaim can never show through the panel
   //--- body the way it could through "bg" alone.
   PRect("fl", bx + 2, by + 2, bw - 4, bh - 4, InpPanelBg, InpPanelBg, 0);
   //--- explicit 4-strip frame, not PRect's own unreliable built-in border -
   //--- see PFrame's own comment; same fix as every sibling EA this session.
   PFrame("bd", bx, by, bw, bh, InpPanelEdge, 2);
  }
//+------------------------------------------------------------------+
// Live panel - shows the EA's own real position/trade state, not a backtest
// replay. Refreshed on every new bar plus right after every open/close.
void DrawPanel(const bool reclaim = true)
  {
   if(!InpShowPanel) return;
   g_panelReclaim = reclaim;

   // draggable position - matches Aurelius/Zenith. First call seeds it from
   // the inputs; a drag (OnChartEvent, CHARTEVENT_OBJECT_DRAG) updates it
   // from there. Was purely InpPanelX/InpPanelY, no drag support at all.
   if(g_panX < 0) { g_panX = InpPanelX; g_panY = InpPanelY; }
   int x=g_panX, y=g_panY, w=MathMax(InpPanelW, g_panelMinW), rh=InpPanelSize+11;
   g_panelMinW = 0;   // re-measured fresh this cycle, used by the NEXT one
   int rows = 20;
   DrawPanelBackground(x, y, w, rows*rh+30);

   string modeStr = (InpStochMode==MODE_THRESHOLD_CROSS) ? "Threshold-Cross" : "Signal-Line-Turn";
   PSection("s1", x, y, w, "AUREBOUND EA  ["+modeStr+"]", true); y+=rh+6;
   PRow("r0", x, y, w, "BB / Stoch",
        StringFormat("%d,%.1f / %d,%d,%d", InpBBPeriod, InpBBDev, InpStochK, InpStochD, InpStochSlow), -1); y+=rh;
   PRow("rm", x, y, w, "magic", (string)InpMagicNumber, -1); y+=rh;
   PRow("rn", x, y, w, "news filter", InpUseNewsFilter?InpNewsCurrency+" hi-imp":"off", InpUseNewsFilter?1:-1); y+=rh;
   string statusStr = posOpen ? (posDir>0?"LONG":"SHORT") : (g_pendingOrder ? "PENDING "+(g_pendingDir>0?"BUY":"SELL") : "flat");
   int statusDir = posOpen ? posDir : (g_pendingOrder ? g_pendingDir : 0);
   PRow("rs", x, y, w, "status", statusStr, (posOpen||g_pendingOrder) ? (statusDir>0?1:0) : -1); y+=rh;
   PRow("re", x, y, w, "entry / SL",
        posOpen ? DoubleToString(entryPx,_Digits)+" / "+DoubleToString(entrySL,_Digits) : "-", -1); y+=rh;
   PRow("rb", x, y, w, "bars held", posOpen ? (string)barsInTrade+" / "+(string)InpMaxHoldBars : "-", -1); y+=rh+6;

   double pf = (g_gLoss!=0.0) ? g_gWin/MathAbs(g_gLoss) : 0.0;
   double avgTrade = (g_n>0) ? g_net/g_n : 0.0;
   PSection("s2", x, y, w, "LIVE STATS"); y+=rh+6;
   PRow("t1", x, y, w, "trades", (string)g_n, -1); y+=rh;
   PRow("t2", x, y, w, "  buy / sell", (string)g_nBuy+" / "+(string)g_nSell, -1); y+=rh;
   PRow("t3", x, y, w, "win rate", DoubleToString(g_n>0?100.0*g_win/g_n:0.0,1)+"%",
        g_n>0 ? ((100.0*g_win/g_n>=35.0)?1:0) : -1); y+=rh;
   PRow("t4", x, y, w, "profit factor", DoubleToString(pf,2), pf>1.0?1:(pf>0?0:-1)); y+=rh;
   PRow("t5", x, y, w, "net", DoubleToString(g_net,2), g_net>=0?1:0); y+=rh;
   PRow("t6", x, y, w, "avg / trade", DoubleToString(avgTrade,3), avgTrade>=0?1:0); y+=rh+6;

   PSection("s3", x, y, w, "LEGEND"); y+=rh+6;
   PRow("l1", x, y, w, "triangle (neon blue)", "entry - BUY", 1); y+=rh;
   PRow("l2", x, y, w, "triangle (white)", "entry - SELL", 0); y+=rh;
   PRow("l3", x, y, w, "diamond (neon green)", "exit - profit", 1); y+=rh;
   PRow("l4", x, y, w, "diamond (neon red-pink)", "exit - breakeven/loss", 0); y+=rh;
  }
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
   hATR   = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   hStoch = iStochastic(_Symbol, PERIOD_CURRENT, InpStochK, InpStochD, InpStochSlow, MODE_SMA, STO_LOWHIGH);
   if(hATR==INVALID_HANDLE || hStoch==INVALID_HANDLE)
     { Print("AuRebound EA: handle creation failed"); return(INIT_FAILED); }

   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   OpenExport();

   // best-effort recovery if the EA was restarted with a position already open
   ulong tk;
   if(FindOwnPosition(tk))
     {
      PositionSelectByTicket(tk);
      posTicket   = tk;
      posOpen     = true;
      posDir      = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? 1 : -1;
      entryPx     = PositionGetDouble(POSITION_PRICE_OPEN);
      entrySL     = PositionGetDouble(POSITION_SL);
      datetime openT = (datetime)PositionGetInteger(POSITION_TIME);
      int shift = iBarShift(_Symbol, PERIOD_CURRENT, openT, false);
      barsInTrade = MathMax(0, shift);
      entryATR = 0.0;
      double tmpBuf[];
      if(CopyBuffer(hATR, 0, MathMax(0,shift), 1, tmpBuf) > 0) entryATR = tmpBuf[0];
      // approximate: if the current SL already sits at/beyond breakeven, assume
      // stage2 already triggered; bestFav is rebuilt from price action since entry
      stage2 = (posDir>0) ? (entrySL >= entryPx - _Point) : (entrySL <= entryPx + _Point);
      bestFav = 0.0;
      double hh[], ll[];
      int n2 = shift+1;
      if(n2>0 && CopyHigh(_Symbol,PERIOD_CURRENT,0,n2,hh)>0 && CopyLow(_Symbol,PERIOD_CURRENT,0,n2,ll)>0)
        {
         double best=(posDir>0)?hh[ArrayMaximum(hh)]-entryPx:entryPx-ll[ArrayMinimum(ll)];
         bestFav = MathMax(0.0, best);
        }
      Print("AuRebound EA: recovered open position #", tk, " dir=", posDir, " barsInTrade=", barsInTrade,
            " stage2=", stage2, " bestFav=", bestFav);
     }
   else
      LoadPendingState();   // only meaningful if there's no open position to manage instead

   if(InpShowWallpaper) DrawWallpaper();
   if(InpShowWatermark) DrawWatermark();
   DrawPanel();
   //--- v1.04: fill the whole rolling band window immediately, so a fresh
   //--- attach shows real history instead of three 1-bar stubs. Cosmetic
   //--- only - skipped entirely in a non-visual Tester pass, where the loop
   //--- would draw InpBandHistoryBars*3 objects onto a chart nobody sees.
   if(!g_skipCosmeticDraws && InpShowBands) BackfillBandLines();
   ChartSetInteger(0, CHART_EVENT_OBJECT_CREATE, false);

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_prefix);
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pl);   // v1.04 band-line segments - own prefix, own sweep
   if(g_fh != INVALID_HANDLE) { FileClose(g_fh); g_fh = INVALID_HANDLE; }
  }
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   //--- dragging the background moves the whole panel - matches Aurelius/
   //--- Zenith. This panel had no drag support at all before InpPanelDrag.
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_pp + "bg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      DrawPanel(false);   // reposition only - reclaiming mid-drag would be jarring
      ChartRedraw(0);
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      static int lastW = -1, lastH = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lastW || nh != lastH)
        {
         lastW = nw; lastH = nh;
         if(InpShowWallpaper) { g_bgOK = false; g_bgTries = 0; DrawWallpaper(); }
         if(InpShowWatermark) DrawWatermark();
         DrawPanel();   // re-anchor to the new width immediately, don't wait for the next tick
         ChartRedraw(0);
        }
     }
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   // checked on every tick (not gated to new-bar) so a queued signal fires as
   // soon as possible once trading actually resumes, not up to 4 hours late
   if(g_pendingOrder) TryFulfillPending();

   // detect a position that closed on its own (broker-side SL/TP hit, manual
   // close) as fast as possible - every tick, not just once per bar, since
   // ManageOpenPosition() would otherwise keep trying to manage a ticket that
   // no longer exists and the EA would never resume scanning for signals
   if(posOpen && !PositionSelectByTicket(posTicket))
      HandleExternalClose();

   datetime curBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(curBarTime == g_lastBarTime) return;
   g_lastBarTime = curBarTime;
   ProcessNewBar();
  }
//+------------------------------------------------------------------+
void TryFulfillPending()
  {
   if((TimeCurrent()-g_pendingSince) > InpPendingMaxWaitMinutes*60)
     {
      Print("AuRebound EA: pending ", (g_pendingDir>0?"BUY":"SELL"), " expired after ",
            InpPendingMaxWaitMinutes, " min without the market reopening - discarding");
      g_pendingOrder=false;
      DrawPanel();   // reflect the discard immediately - no new bar may come for a while (e.g. still weekend)
      SavePendingState();
      return;
     }
   // schedule-gated: don't even try while the schedule still says closed - a
   // cheap local check, so InpMarketClosedRetryDelaySec's short throttle is
   // fine once it does open (any bounce past that point is a broker quirk
   // right at the reopen boundary, expected to clear quickly). NOT schedule-
   // gated means every attempt is a real network call to the broker with no
   // local check backing it off first, so it gets the longer
   // InpPendingRetryDelaySec instead - a 2s throttle there could mean ~1800
   // live order attempts over the full InpPendingMaxWaitMinutes window.
   if(g_pendingScheduleGated)
     {
      if(!CanFillAt(TimeCurrent())) return;
      if(TimeCurrent()-g_pendingLastAttempt < InpMarketClosedRetryDelaySec) return;
     }
   else
     {
      if(TimeCurrent()-g_pendingLastAttempt < InpPendingRetryDelaySec) return;
     }
   g_pendingLastAttempt = TimeCurrent();

   int dir = g_pendingDir; double slDist = g_pendingSLDist; double atr = g_pendingATR;
   datetime origSince = g_pendingSince;   // preserved through SendOrder in case it has to re-queue
   g_pendingOrder=false;   // clear first so a fresh failure re-queues cleanly rather than looping
   // no SavePendingState() here - the queuedSince>0 path below runs a single
   // attempt with no Sleep, so there's no meaningful blocking window to guard
   // against, and SendOrder() saves exactly once on every exit path already;
   // saving here too would double the disk write on every tick of a retry storm
   Print("AuRebound EA: market reopened, firing queued ", (dir>0?"BUY":"SELL"));
   SendOrder(dir, slDist, atr, origSince);
  }
//+------------------------------------------------------------------+
void ProcessNewBar()
  {
   int copied = CopyTime(_Symbol, PERIOD_CURRENT, 0, HIST_BARS, a_time);
   if(copied < InpBBPeriod+20) return;
   // 2026-09-06 (Opus deep-dive review): a returned copy count strictly
   // less than `copied` (indicator not yet fully calculated - routine
   // right after attach, or after a history refresh) used to only be
   // rejected via a `<=0` check below, missing a genuinely SHORT copy.
   // CopyBuffer/CopyOpen/etc. resize the receiving array down to what they
   // actually copied, so `i = copied-2` a few lines down could then index
   // past the end of a shorter array. Require a full `copied`-length read
   // from every series used below, not just a nonzero one.
   if(CopyOpen(_Symbol, PERIOD_CURRENT, 0, copied, a_open) < copied) return;
   if(CopyHigh(_Symbol, PERIOD_CURRENT, 0, copied, a_high) < copied) return;
   if(CopyLow(_Symbol, PERIOD_CURRENT, 0, copied, a_low) < copied) return;
   if(CopyClose(_Symbol, PERIOD_CURRENT, 0, copied, a_close) < copied) return;
   ArraySetAsSeries(a_time,false); ArraySetAsSeries(a_open,false); ArraySetAsSeries(a_high,false);
   ArraySetAsSeries(a_low,false);  ArraySetAsSeries(a_close,false);

   if(CopyBuffer(hATR, 0, 0, copied, a_atr) < copied) return;
   if(CopyBuffer(hStoch, SIGNAL_LINE, 0, copied, a_std) < copied) return;
   ArraySetAsSeries(a_atr,false); ArraySetAsSeries(a_std,false);

   int warmup = MathMax(InpBBPeriod, MathMax(InpATRPeriod, InpStochK+InpStochD+InpStochSlow)) + 20;
   int i = copied-2;   // last CLOSED bar - the signal bar, same convention as the indicator
   if(i < warmup) return;
   if(a_atr[i] <= 0.0) return;

   g_barCounter++;

   //--- PERFORMANCE: cosmetic-only, skip entirely in a non-visual Strategy
   //--- Tester pass - see g_skipCosmeticDraws declaration. This is the one
   //--- call site that repeats on every processed bar of a whole backtest.
   if(!g_skipCosmeticDraws)
     {
      if(InpShowWallpaper) DrawWallpaper();
      if(InpShowWatermark) DrawWatermark();
      //--- v1.04: one new band segment per line per bar, from the same
      //--- BandUpAt/BandMidAt/BandLoAt values the entry check below reads.
      if(InpShowBands) UpdateBandLines(i);
     }

   if(posOpen)
      ManageOpenPosition(i);
   else if(!g_pendingOrder)   // already committed to a queued signal - don't let a fresh one clobber it
      CheckForEntry(i);

   if(!g_skipCosmeticDraws)
      DrawPanel();   // refresh every bar so bars-held/status stay live even with no new event
  }
//+------------------------------------------------------------------+
void ManageOpenPosition(const int i)
  {
   barsInTrade++;

   if(barsInTrade >= InpMaxHoldBars)
     {
      ClosePositionAtMarket("timeout");
      return;
     }

   double curFav = (posDir>0) ? (a_high[i]-entryPx) : (entryPx-a_low[i]);
   bestFav = MathMax(bestFav, curFav);

   double newSL = entrySL;

   if(!stage2)
     {
      double mid = BandMidAt(i);
      if(mid!=EMPTY_VALUE)
        {
         bool clearedMid = (posDir>0) ? (a_close[i]>mid) : (a_close[i]<mid);
         if(clearedMid) { stage2=true; newSL=entryPx; }
        }
     }

   if(bestFav >= 1.0*entryATR)
     {
      double lockPrice = entryPx + posDir*bestFav*InpMFELockFrac;
      newSL = (posDir>0) ? MathMax(newSL, lockPrice) : MathMin(newSL, lockPrice);
     }

   // Clamp against the CURRENT market, always - not just a broker-published
   // minimum distance. The MFE-lock target is derived from bestFav, which is
   // a monotonic historical maximum: if price retraces significantly after
   // reaching that peak before this code manages to apply the new stop, the
   // target can end up stale - on the wrong side of, or too close to, where
   // price actually is right now - and get rejected as "invalid stops" every
   // single bar from then on, since bestFav never decreases so the same
   // stale target keeps getting recomputed. SYMBOL_TRADE_STOPS_LEVEL alone
   // isn't reliable here - some brokers report 0 (no published fixed
   // distance) while still rejecting a stop that's already inside/through
   // the market, so the floor also always includes the current spread as a
   // safety margin, never just the broker's number on its own.
   double stopLevelPts  = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double freezeLevelPts= (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double minDist = MathMax(MathMax(stopLevelPts, freezeLevelPts), 0) * _Point;
   minDist = MathMax(minDist, (ask-bid)*1.5);
   if(posDir>0)
      newSL = MathMax(MathMin(newSL, bid-minDist), entrySL);
   else
      newSL = MathMin(MathMax(newSL, ask+minDist), entrySL);

   if(MathAbs(newSL-entrySL) > _Point/2.0)
     {
      if(trade.PositionModify(posTicket, newSL, 0))
         entrySL = newSL;
      else
        {
         // Comprehensive dump for whenever this recurs - enough to refine the
         // clamp with real data instead of guessing again: broker-published
         // levels, live bid/ask/spread, the floor actually used, how close
         // the target and the currently-set stop each are to the market
         // (negative = already past/through it), and the MFE-lock state that
         // produced this target.
         double distTargetToPrice = (posDir>0) ? (bid-newSL) : (newSL-ask);
         double distCurSLToPrice  = (posDir>0) ? (bid-entrySL) : (entrySL-ask);
         PrintFormat("AuRebound EA: SL modify failed on #%d, error=%d retcode=%d (%s) | "
                     "dir=%s target=%s curSL=%s bid=%s ask=%s spread=%s | "
                     "stopLevelPts=%.0f freezeLevelPts=%.0f minDistUsed=%s | "
                     "distTargetToPrice=%s distCurSLToPrice=%s (negative = already past/through price) | "
                     "bestFav=%s entryATR=%s stage2=%s barsInTrade=%d",
                     posTicket, GetLastError(), trade.ResultRetcode(), trade.ResultRetcodeDescription(),
                     (posDir>0?"LONG":"SHORT"), DoubleToString(newSL,_Digits), DoubleToString(entrySL,_Digits),
                     DoubleToString(bid,_Digits), DoubleToString(ask,_Digits), DoubleToString(ask-bid,_Digits),
                     stopLevelPts, freezeLevelPts, DoubleToString(minDist,_Digits),
                     DoubleToString(distTargetToPrice,_Digits), DoubleToString(distCurSLToPrice,_Digits),
                     DoubleToString(bestFav,_Digits), DoubleToString(entryATR,_Digits),
                     (stage2?"true":"false"), barsInTrade);
        }
     }

   bool bandExit=false;
   if(stage2)
     {
      int winStart = MathMax(0, i - MathMin(InpLookback, barsInTrade));
      if(posDir>0)
        {
         bool recentOpp=false;
         for(int k=winStart;k<=i;k++)
           { double up=BandUpAt(k); if(up!=EMPTY_VALUE && a_high[k]>=up-InpEntryProx*entryATR) { recentOpp=true; break; } }
         bandExit = recentOpp && TurnDnAt(i, a_std);
        }
      else
        {
         bool recentOpp=false;
         for(int k=winStart;k<=i;k++)
           { double lo=BandLoAt(k); if(lo!=EMPTY_VALUE && a_low[k]<=lo+InpEntryProx*entryATR) { recentOpp=true; break; } }
         bandExit = recentOpp && TurnUpAt(i, a_std);
        }
     }

   if(bandExit)
      ClosePositionAtMarket("opposite-band reject");
  }
//+------------------------------------------------------------------+
// Shared by both an EA-initiated close (ClosePositionAtMarket) and a
// position that closed on its own (HandleExternalClose - broker-side SL/TP
// hit, manual close). Logs the trade, updates stats/markers, and resets to
// flat so the EA resumes looking for new signals.
void FinalizeClosedTrade(const datetime entryTimeForLog, const datetime exitTime,
                          const double xPx, const double pnl, const string reason)
  {
   LogTrade(entryTimeForLog, exitTime, posDir, entryPx, xPx, barsInTrade, pnl, reason);
   g_n++; g_net+=pnl;
   if(pnl>=0) { g_win++; g_gWin+=pnl; } else { g_loss++; g_gLoss+=pnl; }

   if(InpShowMarkers)
     {
      // 2026-09-06 (Opus deep-dive review): guard was >0, but the index
      // used is ArraySize-2 - a size-1 array would still index [-1].
      double curATR = (ArraySize(a_atr)>=2) ? a_atr[ArraySize(a_atr)-2] : entryATR;
      double sp = curATR*1.2;
      string tagId = TimeToString(exitTime,TIME_DATE|TIME_SECONDS);
      color mvClr = (pnl>0) ? InpColExitProfit : InpColExitBEorLoss;
      double arrowPrice = (posDir>0) ? xPx+sp*1.2 : xPx-sp*1.2;
      DrawTag(g_prefix+"XM"+tagId, exitTime, arrowPrice, "◆", mvClr,
              (posDir>0)?ANCHOR_LOWER:ANCHOR_UPPER);
      DrawTag(g_prefix+"X"+tagId, exitTime, arrowPrice+((posDir>0)?sp*1.2:-sp*1.2),
              StringFormat("%s\n%+.2f (%s)", (posDir>0?"EXIT BUY":"EXIT SELL"), pnl, reason),
              mvClr, (posDir>0)?ANCHOR_LOWER:ANCHOR_UPPER);
     }

   posOpen=false; posDir=0; entryPx=0; entrySL=0; entryATR=0; stage2=false; bestFav=0; barsInTrade=0; posTicket=0;
   g_cooldownUntilBar = g_barCounter + InpCooldown;
   DrawPanel();
  }
//+------------------------------------------------------------------+
void ClosePositionAtMarket(const string reason)
  {
   double xPx = (posDir>0) ? SymbolInfoDouble(_Symbol,SYMBOL_BID) : SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   // 2026-09-06 (Opus deep-dive review): guarded against ArraySize(a_time)
   // ==0 - a_time[] is only populated inside ProcessNewBar(), so a call
   // path reaching this before the first ProcessNewBar() would otherwise
   // index a zero-length array and raise a critical "array out of range"
   // error, terminating the EA. This function is only reachable from
   // ProcessNewBar() itself so a_time is always populated here in
   // practice, but guarding costs nothing and matches HandleExternalClose
   // below, which genuinely can be called before it.
   datetime entryTimeForLog = (ArraySize(a_time) > 0)
      ? a_time[MathMax(0, ArraySize(a_time)-2-barsInTrade)] : g_lastBarTime;
   if(trade.PositionClose(posTicket))
     {
      // 2026-09-06 (Opus deep-dive review): this used to be a raw PRICE
      // distance ((xPx-entryPx)*posDir), only numerically equal to real
      // dollars at exactly 0.01 lots on GOLD#'s 100oz contract size (the
      // same class of trap as Fulcrum's TargetDistance(), item 19) - and
      // it excluded commission/swap entirely, unlike HandleExternalClose's
      // already-correct HistorySelectByPosition-based P&L just below.
      // Reuse that same approach here so both closing paths feed the
      // panel/CSV the same real dollar figure regardless of lot size.
      double pnl = (xPx-entryPx)*posDir;   // fallback if history isn't available yet
      if(HistorySelectByPosition(posTicket))
        {
         double real = 0.0; bool found = false;
         int total = HistoryDealsTotal();
         for(int k=0; k<total; k++)
           {
            ulong dealTk = HistoryDealGetTicket(k);
            if(dealTk==0) continue;
            long entryType = HistoryDealGetInteger(dealTk, DEAL_ENTRY);
            if(entryType==DEAL_ENTRY_OUT || entryType==DEAL_ENTRY_OUT_BY)
              {
               real += HistoryDealGetDouble(dealTk, DEAL_PROFIT) + HistoryDealGetDouble(dealTk, DEAL_SWAP)
                       + HistoryDealGetDouble(dealTk, DEAL_COMMISSION);
               found = true;
              }
           }
         if(found) pnl = real;
        }
      Print("AuRebound EA: closed #", posTicket, " reason=", reason, " pnl~", DoubleToString(pnl,2));
      FinalizeClosedTrade(entryTimeForLog, TimeCurrent(), xPx, pnl, reason);
     }
   else
      Print("AuRebound EA: close failed, error ", GetLastError());
  }
//+------------------------------------------------------------------+
// The protective stop is a real broker-side order, so a position can close
// on its own (SL hit, or TP/manual) without the EA ever calling
// ClosePositionAtMarket() - without this, the EA would never notice: it
// would keep trying to modify/close a ticket that no longer exists on every
// subsequent bar, that trade would never get logged to the CSV at all, and
// it would never resume looking for new signals. Checked every tick in
// OnTick(), not just once per bar, so it's noticed as fast as possible.
void HandleExternalClose()
  {
   ulong tk = posTicket;
   double xPx=0.0, pnl=0.0; datetime exitTime=TimeCurrent(); bool found=false;

   if(HistorySelectByPosition(tk))
     {
      int total = HistoryDealsTotal();
      for(int k=0; k<total; k++)
        {
         ulong dealTk = HistoryDealGetTicket(k);
         if(dealTk==0) continue;
         long entryType = HistoryDealGetInteger(dealTk, DEAL_ENTRY);
         if(entryType==DEAL_ENTRY_OUT || entryType==DEAL_ENTRY_OUT_BY)
           {
            xPx = HistoryDealGetDouble(dealTk, DEAL_PRICE);
            pnl += HistoryDealGetDouble(dealTk, DEAL_PROFIT) + HistoryDealGetDouble(dealTk, DEAL_SWAP)
                   + HistoryDealGetDouble(dealTk, DEAL_COMMISSION);
            exitTime = (datetime)HistoryDealGetInteger(dealTk, DEAL_TIME);
            found=true;
           }
        }
     }
   if(!found)
     {
      // couldn't pull the closing deal from history (rare) - fall back to a
      // reasonable estimate so state still resets correctly either way
      xPx = (posDir>0) ? SymbolInfoDouble(_Symbol,SYMBOL_BID) : SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      pnl = (xPx-entryPx)*posDir;
     }

   // 2026-09-06 (Opus deep-dive review): the real, exploitable case - this
   // function IS reachable before the first ProcessNewBar() ever runs
   // (OnTick calls HandleExternalClose() before checking for a new bar), so
   // a restart-mid-trade whose broker-side SL hits before the next H4 bar
   // closes would index a_time[] at size 0 and terminate the EA with an
   // array-out-of-range error. Fall back to the last known bar time - this
   // value is for the CSV/log entry only, not any risk decision.
   datetime entryTimeForLog = (ArraySize(a_time) > 0)
      ? a_time[MathMax(0, ArraySize(a_time)-2-barsInTrade)] : g_lastBarTime;
   Print("AuRebound EA: position #", tk, " closed externally (broker-side stop or manual) - exit~",
         DoubleToString(xPx,_Digits), " pnl~", DoubleToString(pnl,2));
   FinalizeClosedTrade(entryTimeForLog, exitTime, xPx, pnl, "stop-loss (broker)");
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
   // Found in review: CalendarValueHistory() is a live-terminal-only API
   // (this file's own header comment already says so) - in the Strategy
   // Tester it was still being called fresh on every check with zero
   // caching, a well-documented slow path when hit repeatedly across a
   // multi-year real-tick run (same fix applied to Tailwind_EA.mq5/
   // Slipstream_EA.mq5 this session after a live user report of multi-hour
   // runs). Since this function already "fails open" (returns false/does-
   // not-block) whenever the calendar has nothing usable, and its Tester
   // result was already documented as not meaningful, skip the call
   // entirely in the Tester - identical backtest behaviour, less wall-clock
   // time.
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
void CheckForEntry(const int i)
  {
   bool nearLower = NearLowerAt(i);
   bool nearUpper = NearUpperAt(i);

   bool recentLower=false, recentUpper=false;
   int winStart = MathMax(0, i-InpLookback);
   for(int k=winStart;k<=i;k++) { if(NearLowerAt(k)) recentLower=true; if(NearUpperAt(k)) recentUpper=true; }

   bool longSig  = recentLower && TurnUpAt(i, a_std);
   bool shortSig = recentUpper && TurnDnAt(i, a_std);

   bool isIndecision = InpBlockIndecision && IsIndecisionCandle(i, a_open, a_high, a_low, a_close);
   if(isIndecision) { longSig=false; shortSig=false; }

   if(InpUseSessionFilter || InpBlockFridayClose)
     {
      MqlDateTime dt; TimeToStruct(a_time[i], dt);
      if(InpUseSessionFilter && dt.hour==InpBlockedHour) { longSig=false; shortSig=false; }
      if(InpBlockFridayClose && dt.day_of_week==FRIDAY && dt.hour>=InpFridayCloseHour) { longSig=false; shortSig=false; }
     }

   if(NewsBlackoutActive()) { longSig=false; shortSig=false; }

   if(InpStochMode==MODE_THRESHOLD_CROSS && InpUsePersistFilter)
     {
      if(longSig  && StochPersistence(i, true,  a_std) < InpMinPersistBars) longSig=false;
      if(shortSig && StochPersistence(i, false, a_std) < InpMinPersistBars) shortSig=false;
     }

   bool ambiguous = longSig && shortSig;
   bool blockedCooldown = (g_barCounter <= g_cooldownUntilBar);

   if(longSig && !ambiguous && !blockedCooldown)
      TryEnter(1, i);
   else if(shortSig && !ambiguous && !blockedCooldown)
      TryEnter(-1, i);
  }
//+------------------------------------------------------------------+
// Fill happens right now (market order), so the schedule check is against
// "now", not the signal bar's time - same idea as the indicator's time[i+1]
// check. If the schedule already says closed, queue directly instead of
// wasting the retry loop in SendOrder() attempting an order we know will
// bounce; SendOrder()'s own retry-then-queue still catches anything the
// schedule doesn't predict (unscheduled holidays etc).
void TryEnter(const int dir, const int i)
  {
   double atr;
   double slDist = ComputeSLDist(dir, i, atr);
   if(InpUseSessionScheduleFilter && !CanFillAt(TimeCurrent()))
     {
      QueuePending(dir, slDist, atr, i);
      return;
     }
   SendOrder(dir, slDist, atr, 0);   // queuedSince=0: fresh attempt, not an existing pending order firing
  }
//+------------------------------------------------------------------+
void QueuePending(const int dir, const double slDist, const double atr, const int i)
  {
   // defensive backstop only - QueuePending() is only ever reached via TryEnter()
   // <- CheckForEntry(), which ProcessNewBar() already gates on !g_pendingOrder,
   // so g_pendingOrder should always be false here. Kept in case that gating
   // ever changes; not the real single-slot enforcement.
   if(g_pendingOrder)
     {
      Print("AuRebound EA: signal at ", TimeToString(a_time[i],TIME_DATE|TIME_MINUTES),
            " ignored - already have a pending order queued");
      return;
     }
   g_pendingOrder=true; g_pendingDir=dir; g_pendingSLDist=slDist; g_pendingATR=atr; g_pendingSince=TimeCurrent();
   g_pendingScheduleGated=true;   // queued specifically because the schedule said closed
   Print("AuRebound EA: signal at ", TimeToString(a_time[i],TIME_DATE|TIME_MINUTES),
         " - market closed, queued ", (dir>0?"BUY":"SELL"), " (max wait ", InpPendingMaxWaitMinutes, " min)");
   DrawPanel();
   SavePendingState();
  }
//+------------------------------------------------------------------+
double ComputeSLDist(const int dir, const int i, double &atrOut)
  {
   double a = a_atr[i];
   atrOut = a;
   double px = (dir>0) ? SymbolInfoDouble(_Symbol,SYMBOL_ASK) : SymbolInfoDouble(_Symbol,SYMBOL_BID);

   double slDist;
   if(dir>0)
     {
      double extreme = a_low[i];
      for(int k=MathMax(0,i-InpLookback);k<=i;k++) extreme=MathMin(extreme,a_low[k]);
      slDist = MathAbs(px-extreme) + InpSLBuffer*a;
     }
   else
     {
      double extreme = a_high[i];
      for(int k=MathMax(0,i-InpLookback);k<=i;k++) extreme=MathMax(extreme,a_high[k]);
      slDist = MathAbs(extreme-px) + InpSLBuffer*a;
     }
   if(InpUseSLCap) slDist = MathMin(slDist, InpSLCapATR*a);
   return(slDist);
  }
//+------------------------------------------------------------------+
// Shared by a fresh signal and a queued one firing on market reopen. slDist
// is the raw structural distance computed at signal time; the broker stop-
// level floor is applied here, right before sending, against whatever the
// live price actually is at send time. atrForEntry is the SAME ATR that
// determined slDist - kept consistent through to entryATR rather than
// re-derived fresh, which would decouple the stop distance from the value
// driving the MFE-lock trigger for anything that went through the pending
// queue. queuedSince is 0 for a fresh signal, or the ORIGINAL queue
// timestamp when this call is an existing pending order firing/retrying -
// preserved so a re-queue on repeated failure doesn't reset the expiry
// clock and let a signal sit queued indefinitely.
void SendOrder(const int dir, double slDist, const double atrForEntry, const datetime queuedSince)
  {
   double a = atrForEntry;

   // the indicator's simulated stop never has to clear the broker's minimum stop
   // distance - a live order can, and a tight ATR-based stop can get silently
   // rejected ("invalid stops") in exactly the cases the indicator shows as a
   // clean entry. Widen to the broker's floor rather than let that happen
   // quietly - and always include the current spread as a safety margin too,
   // not just SYMBOL_TRADE_STOPS_LEVEL/FREEZE_LEVEL on their own, since some
   // brokers report 0 for those while still rejecting a too-tight stop (see
   // the same fix and full explanation in ManageOpenPosition).
   double stopLevelPts  = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double freezeLevelPts= (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double curSpread = SymbolInfoDouble(_Symbol,SYMBOL_ASK) - SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double minDist = MathMax(MathMax(stopLevelPts, freezeLevelPts), 0) * _Point;
   minDist = MathMax(minDist, curSpread*1.5);
   if(slDist<minDist) slDist = minDist;

   double lots = NormalizeLots(InpLots);
   bool ok=false;
   double px=0.0, sl=0.0;
   // A fresh signal (queuedSince==0) gets its own short blocking retry burst -
   // a one-off cost, fine to Sleep() through. A signal already in the pending
   // queue (queuedSince>0) is being polled every tick by TryFulfillPending()
   // already, so it gets exactly ONE attempt here with no Sleep - retrying the
   // multi-attempt Sleep loop on every tick during a reopen would block the EA
   // for seconds at a time, repeatedly, for as long as the mismatch lasts.
   int attempts = (queuedSince>0) ? 1 : MathMax(1, InpMarketClosedRetries);
   for(int attempt=1; attempt<=attempts; attempt++)
     {
      // TIMEOUT/CONNECTION are ambiguous - the previous attempt may have
      // actually filled at the broker even though the terminal never got
      // confirmation. Check for a real position before EVERY attempt
      // (including retries within this same burst) and adopt it rather than
      // blindly resending, which would otherwise risk a duplicate live fill.
      ulong existingTk;
      if(FindOwnPosition(existingTk) && AdoptFoundPosition(existingTk, dir, atrForEntry))
         return;
      // recompute against the CURRENT price every attempt - REQUOTE/PRICE_CHANGED
      // specifically mean the price used in the previous attempt is stale, so
      // resending the exact same price/sl would likely just fail identically
      px = (dir>0) ? SymbolInfoDouble(_Symbol,SYMBOL_ASK) : SymbolInfoDouble(_Symbol,SYMBOL_BID);
      sl = (dir>0) ? px-slDist : px+slDist;
      ok = (dir>0) ? trade.Buy(lots, _Symbol, 0.0, sl, 0.0, InpTradeComment)
                   : trade.Sell(lots, _Symbol, 0.0, sl, 0.0, InpTradeComment);
      if(ok) break;
      if(!IsRetryableRetcode(trade.ResultRetcode())) break;   // permanent error: don't keep retrying blind
      if(attempt < attempts)
        {
         Print("AuRebound EA: ", trade.ResultRetcodeDescription(), ", retry ", attempt, "/", attempts-1,
               " in ", InpMarketClosedRetryDelaySec, "s");
         Sleep(InpMarketClosedRetryDelaySec*1000);
        }
     }
   if(!ok)
     {
      // same retryable/permanent classification either way now - a fresh
      // signal (queuedSince==0) that exhausts its burst on a transient error
      // gets queued for the tick-poller just like an already-pending one that
      // failed again, instead of only ever queuing on MARKET_CLOSED specifically
      if(IsRetryableRetcode(trade.ResultRetcode()))
        {
         g_pendingOrder=true; g_pendingDir=dir; g_pendingSLDist=slDist; g_pendingATR=atrForEntry;
         g_pendingSince = (queuedSince>0) ? queuedSince : TimeCurrent();
         // only MARKET_CLOSED means "wait on the schedule" - every other
         // retryable reason (REQUOTE, CONNECTION, ...) has nothing to do with
         // the session schedule and should just be retried on a time throttle.
         // And never gate on the schedule if the user turned that filter off -
         // they did so because they don't trust it for this symbol, so it
         // shouldn't be consulted for anything, including this.
         g_pendingScheduleGated = InpUseSessionScheduleFilter && (trade.ResultRetcode()==TRADE_RETCODE_MARKET_CLOSED);
         Print("AuRebound EA: ", (queuedSince>0?"pending ":""), (dir>0?"BUY":"SELL"),
               " fill attempt failed (", trade.ResultRetcodeDescription(), ") - queued, will retry (max wait ",
               InpPendingMaxWaitMinutes, " min)");
        }
      else
        {
         Print("AuRebound EA: ", (queuedSince>0?"pending ":""), (dir>0?"BUY":"SELL"),
               " permanently failed (", trade.ResultRetcodeDescription(), ") - not retryable, discarding");
         // same comprehensive dump as ManageOpenPosition's SL-modify failure -
         // hasn't been observed on entry yet, but if it ever is, this gives
         // enough to refine the floor with real data instead of guessing
         double curBid = SymbolInfoDouble(_Symbol,SYMBOL_BID), curAsk = SymbolInfoDouble(_Symbol,SYMBOL_ASK);
         PrintFormat("AuRebound EA: entry failure detail | error=%d retcode=%d (%s) | "
                     "dir=%s attemptedPx=%s attemptedSL=%s bid=%s ask=%s spread=%s | "
                     "stopLevelPts=%.0f freezeLevelPts=%.0f minDistUsed=%s slDist=%s",
                     GetLastError(), trade.ResultRetcode(), trade.ResultRetcodeDescription(),
                     (dir>0?"LONG":"SHORT"), DoubleToString(px,_Digits), DoubleToString(sl,_Digits),
                     DoubleToString(curBid,_Digits), DoubleToString(curAsk,_Digits), DoubleToString(curAsk-curBid,_Digits),
                     stopLevelPts, freezeLevelPts, DoubleToString(minDist,_Digits), DoubleToString(slDist,_Digits));
        }
      DrawPanel();   // status may have just changed (flat->pending, or pending->flat on a non-requeue failure)
      SavePendingState();
      return;
     }

   posOpen=true; posDir=dir; posTicket=trade.ResultDeal()>0 ? trade.ResultOrder() : 0;
   // resolve the actual position ticket freshly opened for this symbol/magic
   ulong tk; if(FindOwnPosition(tk)) posTicket=tk;
   entryPx = trade.ResultPrice()>0 ? trade.ResultPrice() : px;
   entrySL = sl;
   entryATR = a;
   stage2=false; bestFav=0.0; barsInTrade=0;
   if(dir>0) g_nBuy++; else g_nSell++;

   if(InpShowMarkers)
     {
      double sp = a*1.2;
      color clr = (dir>0) ? InpColBuy : InpColSell;
      double tagPrice = (dir>0) ? entryPx-sp*1.9 : entryPx+sp*1.9;
      DrawTag(g_prefix+"E"+TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS), TimeCurrent(), tagPrice,
              (dir>0?"▲ BUY":"▼ SELL"), clr, (dir>0)?ANCHOR_UPPER:ANCHOR_LOWER);
     }

   Print("AuRebound EA: opened ", (dir>0?"BUY":"SELL"), " #", posTicket, " @", entryPx, " SL=", entrySL);
   DrawPanel();
   SavePendingState();   // g_pendingOrder is false here either way - make sure the on-disk file agrees
  }
//+------------------------------------------------------------------+
