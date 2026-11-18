//+------------------------------------------------------------------+
//|                                  EMA84_200_Cross_Logger.mq5      |
//|  Forward-tracking logger, NOT a trading EA - places no real       |
//|  orders, risks no money.                                          |
//|                                                                    |
//|  REGIME: EMA(84) vs EMA(200) on the closed bar, as before - a      |
//|  cross defines/flips the regime direction and is still logged to  |
//|  EMA84_200_CrossLog.csv.                                          |
//|                                                                    |
//|  v1.02 POSITION RULE (per direct instruction, 2026-11-18, "waiting|
//|  for the opposite cross is pointless... has to be sooner... trade |
//|  again when it... closes back below the 84 to go further down"):  |
//|  within an unchanged regime, EXIT the simulated position the      |
//|  moment price closes back across EMA(84) AGAINST it (tighter than |
//|  waiting for the full 84/200 cross), then RE-ENTER the moment     |
//|  price closes back across EMA(84) IN FAVOR of the regime again -  |
//|  repeating, possibly several times, until the regime itself flips.|
//|  ASSUMPTION (stated explicitly, confirm/correct if wrong): the     |
//|  "rejects VWAP/200ema" part is read as the usual PLACE this        |
//|  happens, not a hard condition checked in code - the actual        |
//|  mechanical trigger implemented is just "closes back across        |
//|  EMA84", nothing else gates it.                                    |
//|                                                                    |
//|  Logs to TWO shared CSVs: EMA84_200_CrossLog.csv (raw regime       |
//|  crosses, unchanged) and EMA84_200_PositionLog.csv (every          |
//|  simulated ENTRY/EXIT under the v1.02 rule above) - across up to   |
//|  4 timeframes from a SINGLE chart attachment, backfill-capable (no |
//|  need to run MT5 24/7, see InpLookbackBars), with a live panel.    |
//|                                                                    |
//|  Attach ONCE to any chart (symbol only matters, timeframe of the  |
//|  chart itself is irrelevant - all 4 tracked timeframes are read   |
//|  via their own bounded recompute, same pattern as SuperTrend_MTF's|
//|  dashboard rows). For a second instrument (e.g. Silver/BTC),      |
//|  attach a second instance on that symbol's chart - all instances  |
//|  share the same CSV log files.                                    |
//+------------------------------------------------------------------+
#property copyright "Internal"
#property version   "1.10"
#property indicator_chart_window
#property indicator_plots 0
#property indicator_buffers 1

#define LOG_FILE "EMA84_200_CrossLog.csv"
#define POS_LOG_FILE "EMA84_200_PositionLog.csv"
#define PFX "EMA84200_"

input group "=== EMA periods ==="
input int    InpFastPeriod       = 84;
input int    InpSlowPeriod       = 200;

input group "=== Timeframes tracked ==="
input ENUM_TIMEFRAMES InpTF1     = PERIOD_M15;
input ENUM_TIMEFRAMES InpTF2     = PERIOD_H1;
input ENUM_TIMEFRAMES InpTF3     = PERIOD_H4;
input ENUM_TIMEFRAMES InpTF4     = PERIOD_D1;
input int    InpLookbackBars     = 200;       // v1.01: how many closed bars back each TF scans on every
                                               // check, to backfill any cross missed while MT5 was
                                               // closed. 200 M15 bars = ~2 days, 200 H4 bars = ~33 days,
                                               // 200 D1 bars = ~200 days - raise it if you expect to
                                               // leave the platform closed longer than that on any
                                               // tracked timeframe, or a gap longer than this will
                                               // silently skip the crosses inside it.

input group "=== Historical markers (chart's own timeframe only) ==="
input bool   InpShowHistoricalMarkers = true;  // draws past ENTRY/EXIT signals under the v1.02 rule,
                                                // with a $ tag at each exit, for whichever of
                                                // InpTF1-4 matches the CHART's own timeframe - a
                                                // marker needs real time/price coordinates on a
                                                // specific chart, so it can't be drawn for the other
                                                // 3 tracked timeframes from here.
input int    InpHistoricalMarkerBars  = 2000;  // how far back (in this chart's own bars) to draw -
                                                // capped deliberately: this project has hit real MT5
                                                // freeze bugs from indicators creating too many chart
                                                // objects at once, so "all history" is not the default.
input int    InpArrowSize             = 1;
input double InpArrowGapATR           = 1.0;   // v1.07: arrows offset this many ATR(14) away from the
                                                // candle (below for a bullish/UP marker, above for a
                                                // bearish/DOWN one) - v1.06's fixed-points offset
                                                // (150 pts = $1.50 on Gold) was tiny next to a typical
                                                // candle's actual range and barely moved at all; ATR-
                                                // relative scales correctly across instruments/timeframes,
                                                // same fix already applied to SuperTrend_MTF earlier.

input group "=== Trend-strength filter (no trades while EMA84 is sideways) ==="
input int    InpSlopeLookbackBars     = 80;    // v1.09: 20->80 - per direct report "still there" after
                                                // v1.08. Root cause wasn't the threshold value, it was
                                                // the WINDOW being too short: a 20-bar (5h on M15) slope
                                                // check can be satisfied by a small sub-swing INSIDE a
                                                // much wider range that's obviously sideways when you
                                                // look at the whole stretch - raising the threshold alone
                                                // (v1.08) barely helped because it didn't fix that. 80
                                                // bars = ~20h on M15, closer to the timespan a human eye
                                                // actually judges "has this been ranging" over.
input double InpMinSlopeATR           = 0.40;  // a NEW position (entry OR re-entry) only opens if EMA84
                                                // moved at least this many ATR(14) over
                                                // InpSlopeLookbackBars bars; otherwise EMA84 is judged
                                                // "sideways" and no trade is taken. Existing open
                                                // positions are NOT force-closed just because the slope
                                                // flattens mid-trade - this only gates NEW entries.
input double InpMinGapATR             = 1.0;   // v1.10: EMA84 must also sit at least this many ATR(14)
                                                // away from EMA200 - per direct confirmation "when it's
                                                // flat it is near the 200ema" / a real trend needs EMA84
                                                // to have pulled away again, not just be moving locally.
                                                // Required ALONGSIDE the slope check, not instead of it.

input group "=== Panel ==="
input bool   InpShowPanel        = true;
input int    InpPanelX            = 10;
input int    InpPanelY            = 20;
input color  InpPanelHeaderColor  = clrDodgerBlue;
input color  InpPanelTextColor    = clrWhite;
input color  InpPanelUpColor      = clrLime;
input color  InpPanelDownColor    = clrOrangeRed;
input color  InpPanelBgColor      = clrBlack;
input int    InpPanelWidth        = 230;

double g_dummy[];
bool   g_firstCalc = true;
datetime g_lastBarTime = 0;

ENUM_TIMEFRAMES g_tf[4];
int    g_fastHandle[4];
int    g_slowHandle[4];
int    g_atrHandle[4];
datetime g_lastTfBarTime[4];
string g_lastDir[4];      // regime direction: "UP" / "DOWN" / "" (unknown yet)
datetime g_lastCrossTime[4];
double g_lastCrossPrice[4];
bool   g_tfReady[4];

//--- v1.02: inner simulated position state (independent of the regime
//--- cross) - see the file header for the exact rule.
bool     g_posOpen[4];
string   g_posDir[4];          // "UP" / "DOWN" while g_posOpen[k]
datetime g_posEntryTime[4];
double   g_posEntryPrice[4];
datetime g_lastProcessedBarTime[4];   // watermark so bars already scanned for pos events aren't rechecked

//--- v1.03: historical chart markers - only meaningful for whichever
//--- tracked TF equals the chart's own PERIOD_CURRENT, since a marker
//--- needs real time/price coordinates on this specific chart.
int  g_chartTfSlot = -1;        // index into g_tf[] matching PERIOD_CURRENT, -1 if none
bool g_markersBuilt = false;
int  g_markerSeq = 0;           // unique suffix for marker object names

int OnInit()
  {
   SetIndexBuffer(0, g_dummy, INDICATOR_CALCULATIONS);
   IndicatorSetString(INDICATOR_SHORTNAME,
                       StringFormat("EMA%d/%d Cross Logger", InpFastPeriod, InpSlowPeriod));
   g_firstCalc = true;
   g_lastBarTime = 0;

   g_tf[0] = InpTF1; g_tf[1] = InpTF2; g_tf[2] = InpTF3; g_tf[3] = InpTF4;
   g_chartTfSlot = -1;
   //--- v1.05 FIX (real bug, per direct report "still no signals printed"):
   //--- PERIOD_CURRENT is a SENTINEL value (literally 0), meant only to be
   //--- PASSED to functions like iMA()/iTime() meaning "use the chart's own
   //--- period" - it is NOT equal to the chart's actual ENUM_TIMEFRAMES
   //--- value. Comparing g_tf[s] (a real period like PERIOD_M15=15) against
   //--- PERIOD_CURRENT (0) could never match, so g_chartTfSlot was ALWAYS
   //--- -1 regardless of the v1.04 fix - markers never had a chance to
   //--- draw on any chart, on any timeframe. _Period is the predefined
   //--- variable holding the chart's REAL timeframe.
   for(int s = 0; s < 4; s++) if(g_tf[s] == _Period) { g_chartTfSlot = s; break; }
   PrintFormat("EMA Cross Logger: chart period=%s, chartTfSlot=%d (%s) - markers will draw only if this is >= 0",
               EnumToString(_Period), g_chartTfSlot,
               g_chartTfSlot >= 0 ? EnumToString(g_tf[g_chartTfSlot]) : "NONE - no tracked TF matches this chart");
   g_markersBuilt = false;
   g_markerSeq = 0;
   for(int k = 0; k < 4; k++)
     {
      g_fastHandle[k] = INVALID_HANDLE;
      g_slowHandle[k] = INVALID_HANDLE;
      g_atrHandle[k] = INVALID_HANDLE;
      g_lastTfBarTime[k] = 0;
      g_lastDir[k] = "";
      g_lastCrossTime[k] = 0;
      g_lastCrossPrice[k] = 0.0;
      g_tfReady[k] = false;
      g_posOpen[k] = false;
      g_posDir[k] = "";
      g_posEntryTime[k] = 0;
      g_posEntryPrice[k] = 0.0;
      g_lastProcessedBarTime[k] = 0;
     }

   if(!FileIsExist(LOG_FILE, FILE_COMMON))
     {
      int h = FileOpen(LOG_FILE, FILE_WRITE | FILE_READ | FILE_CSV | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
      if(h != INVALID_HANDLE)
        {
         FileWrite(h, "datetime_utc", "symbol", "period", "direction", "close_price", "fast_ema", "slow_ema");
         FileClose(h);
        }
     }
   if(!FileIsExist(POS_LOG_FILE, FILE_COMMON))
     {
      int h2 = FileOpen(POS_LOG_FILE, FILE_WRITE | FILE_READ | FILE_CSV | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
      if(h2 != INVALID_HANDLE)
        {
         FileWrite(h2, "datetime_utc", "symbol", "period", "event", "direction", "price");
         FileClose(h2);
        }
     }
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   for(int k = 0; k < 4; k++)
     {
      if(g_fastHandle[k] != INVALID_HANDLE) IndicatorRelease(g_fastHandle[k]);
      if(g_slowHandle[k] != INVALID_HANDLE) IndicatorRelease(g_slowHandle[k]);
      if(g_atrHandle[k] != INVALID_HANDLE) IndicatorRelease(g_atrHandle[k]);
     }
   ObjectsDeleteAll(0, PFX);
  }

void LogCross(const datetime t, const string sym, const string per,
              const string dir, const double price, const double ef, const double es)
  {
   int h = FileOpen(LOG_FILE, FILE_WRITE | FILE_READ | FILE_CSV | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
   if(h == INVALID_HANDLE) { Print("EMA Cross Logger: FileOpen failed, error ", GetLastError()); return; }
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(t, TIME_DATE | TIME_SECONDS), sym, per, dir,
             DoubleToString(price, _Digits), DoubleToString(ef, _Digits), DoubleToString(es, _Digits));
   FileClose(h);
   PrintFormat("EMA Cross Logger: %s %s %s cross at %s (%.*f)",
               sym, per, dir, TimeToString(t, TIME_DATE | TIME_SECONDS), _Digits, price);
  }

//--- v1.03: draws an entry arrow, or an exit arrow + a "$+12.34" text tag,
//--- on the chart. Only called for the TF that matches this chart's own
//--- PERIOD_CURRENT (see g_chartTfSlot) - every object name is unique
//--- (g_markerSeq) so nothing here is ever re-touched/animated, it's a
//--- one-shot draw per historical event, cheap and not a per-tick cost.
void DrawMarker(const datetime t, const double price, const bool isEntry, const bool isUp,
                 const double dollarMove, const double atrHere)
  {
   g_markerSeq++;
   string nm = PFX + "mk_" + IntegerToString(g_markerSeq);
   int code = isEntry ? (isUp ? 233 : 234) : 251;   // 233=up arrow, 234=down arrow, 251=small x (exit)
   color col = isUp ? InpPanelUpColor : InpPanelDownColor;

   //--- v1.07: ATR-relative offset away from the candle (below for UP,
   //--- above for DOWN) - v1.06's fixed-points gap was too small to be
   //--- visible next to a typical candle's real range (see input comment).
   double gap = (atrHere > 0.0 ? atrHere : SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 100) * InpArrowGapATR;
   double drawPrice = isUp ? price - gap : price + gap;

   ObjectCreate(0, nm, OBJ_ARROW, 0, t, drawPrice);
   ObjectSetInteger(0, nm, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpArrowSize);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isUp ? ANCHOR_TOP : ANCHOR_BOTTOM);

   if(!isEntry)
     {
      string tagNm = PFX + "tag_" + IntegerToString(g_markerSeq);
      string txt = (dollarMove >= 0 ? "+$" : "-$") + DoubleToString(MathAbs(dollarMove), 2);
      ObjectCreate(0, tagNm, OBJ_TEXT, 0, t, drawPrice);
      ObjectSetString(0, tagNm, OBJPROP_TEXT, " " + txt);
      ObjectSetInteger(0, tagNm, OBJPROP_COLOR, dollarMove >= 0 ? InpPanelUpColor : InpPanelDownColor);
      ObjectSetInteger(0, tagNm, OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(0, tagNm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, tagNm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, tagNm, OBJPROP_ANCHOR, isUp ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER);
     }
  }

//--- v1.03: one-shot historical replay of the v1.02 regime+position rule
//--- over up to InpHistoricalMarkerBars closed bars, drawing every past
//--- ENTRY/EXIT. Runs ONCE per attach (g_markersBuilt), only for the TF
//--- slot matching this chart's own PERIOD_CURRENT - everything here is a
//--- single bounded pass over already-fetched arrays, no further API
//--- calls inside the loop, same cost shape as this file's other
//--- bounded recomputes.
void BuildHistoricalMarkers()
  {
   if(g_chartTfSlot < 0) { g_markersBuilt = true; return; }   // none of the 4 tracked TFs is this chart's own - nothing to draw, don't keep re-checking every bar
   ENUM_TIMEFRAMES tf = g_tf[g_chartTfSlot];
   int warm = InpSlopeLookbackBars;   // v1.06: extra lookback so the slope check always has room
   int need = MathMin(InpHistoricalMarkerBars, iBars(_Symbol, tf) - 2 - warm) + InpSlowPeriod + warm;
   need = MathMin(need, iBars(_Symbol, tf) - 2);
   if(need < InpSlowPeriod + warm + 2) return;   // not enough history YET - retry next bar (don't mark built)

   //--- v1.04 FIX (real bug, per direct report "there are no signals on
   //--- the chart"): this used to create its OWN fresh handles and check
   //--- BarsCalculated in the very same call - a freshly-created handle
   //--- has ZERO computed bars until MT5 has a moment to warm it up (the
   //--- exact handle-churn gotcha already documented/fixed elsewhere in
   //--- this repo), and since fh/sh were local and released every call,
   //--- it recreated them from scratch every single bar and could never
   //--- actually finish. Now reuses the SAME persistent per-slot handle
   //--- the live tracker already creates once in CheckTimeframe/OnInit -
   //--- created here if CheckTimeframe hasn't run yet this session, but
   //--- never released until OnDeinit, so it gets real time to warm up.
   if(g_fastHandle[g_chartTfSlot] == INVALID_HANDLE)
      g_fastHandle[g_chartTfSlot] = iMA(_Symbol, tf, InpFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_slowHandle[g_chartTfSlot] == INVALID_HANDLE)
      g_slowHandle[g_chartTfSlot] = iMA(_Symbol, tf, InpSlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_atrHandle[g_chartTfSlot] == INVALID_HANDLE)
      g_atrHandle[g_chartTfSlot] = iATR(_Symbol, tf, 14);
   int fh = g_fastHandle[g_chartTfSlot];
   int sh = g_slowHandle[g_chartTfSlot];
   int ah = g_atrHandle[g_chartTfSlot];
   if(fh == INVALID_HANDLE || sh == INVALID_HANDLE || ah == INVALID_HANDLE) return;
   if(BarsCalculated(fh) < need + 1 || BarsCalculated(sh) < need + 1 || BarsCalculated(ah) < need + 1) return;   // still warming up - retry next bar

   double ef[], es[], cl[], atrArr[];
   ArraySetAsSeries(ef, true); ArraySetAsSeries(es, true); ArraySetAsSeries(cl, true); ArraySetAsSeries(atrArr, true);
   //--- shift 1..need = CLOSED bars only (shift 0 would still be forming)
   //--- - same lookahead-safe convention as CheckTimeframe's own scan.
   if(CopyBuffer(fh, 0, 1, need, ef) < need || CopyBuffer(sh, 0, 1, need, es) < need ||
      CopyBuffer(ah, 0, 1, need, atrArr) < need || CopyClose(_Symbol, tf, 1, need, cl) < need)
      return;
   ArraySetAsSeries(ef, false); ArraySetAsSeries(es, false); ArraySetAsSeries(cl, false); ArraySetAsSeries(atrArr, false);   // 0 = oldest

   //--- show only the last InpHistoricalMarkerBars of this (possibly
   //--- warmup-padded) window, so the EMA itself still had InpSlowPeriod+
   //--- InpSlopeLookbackBars bars to settle before the first drawn signal.
   int startIdx = MathMax(warm + 1, need - InpHistoricalMarkerBars);

   bool posOpen = false; string posDir = ""; datetime entryTime = 0; double entryPx = 0.0;
   string regimeDir = (ef[startIdx - 1] > es[startIdx - 1]) ? "UP" : "DOWN";
   int entriesDrawn = 0, entriesSkippedSideways = 0;   // v1.07: proof the sideways filter actually ran

   for(int j = startIdx; j < need; j++)
     {
      datetime t = iTime(_Symbol, tf, need - j);   // matches ef[j]/es[j]/cl[j]'s shift-1-based fetch above
      double px = cl[j];
      bool regimeUp = ef[j] > es[j];
      bool regimeUpPrev = ef[j - 1] > es[j - 1];

      if(regimeUp != regimeUpPrev)
        {
         string newDir = regimeUp ? "UP" : "DOWN";
         if(posOpen)
           {
            double mv = (px - entryPx) * (posDir == "UP" ? 1.0 : -1.0);
            DrawMarker(t, px, false, posDir == "UP", mv, atrArr[j]);
            posOpen = false;
           }
         regimeDir = newDir;
         //--- v1.06: same sideways gate as the live tracker.
         if(IsTrending(ef, es, atrArr, j, InpSlopeLookbackBars))
           {
            DrawMarker(t, px, true, regimeUp, 0.0, atrArr[j]);
            posOpen = true; posDir = newDir; entryTime = t; entryPx = px;
            entriesDrawn++;
           }
         else entriesSkippedSideways++;
         continue;
        }

      bool closeAboveFast = px > ef[j];
      if(posOpen)
        {
         bool exitNow = (posDir == "UP" && !closeAboveFast) || (posDir == "DOWN" && closeAboveFast);
         if(exitNow)
           {
            double mv = (px - entryPx) * (posDir == "UP" ? 1.0 : -1.0);
            DrawMarker(t, px, false, posDir == "UP", mv, atrArr[j]);
            posOpen = false;
           }
        }
      else
        {
         bool reenterUp = (regimeDir == "UP" && closeAboveFast);
         bool reenterDn = (regimeDir == "DOWN" && !closeAboveFast);
         if(reenterUp || reenterDn)
           {
            if(IsTrending(ef, es, atrArr, j, InpSlopeLookbackBars))
              {
               string dir = reenterUp ? "UP" : "DOWN";
               DrawMarker(t, px, true, reenterUp, 0.0, atrArr[j]);
               posOpen = true; posDir = dir; entryTime = t; entryPx = px;
               entriesDrawn++;
              }
            else entriesSkippedSideways++;
           }
        }
     }

   g_markersBuilt = true;
   PrintFormat("EMA Cross Logger: historical markers built for %s %s, scanned %d bars - %d entries drawn, %d skipped as sideways (min slope %.2fxATR over %d bars)",
               _Symbol, EnumToString(tf), need - startIdx, entriesDrawn, entriesSkippedSideways, InpMinSlopeATR, InpSlopeLookbackBars);
  }

void LogPosition(const datetime t, const string sym, const string per,
                  const string event, const string dir, const double price)
  {
   int h = FileOpen(POS_LOG_FILE, FILE_WRITE | FILE_READ | FILE_CSV | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
   if(h == INVALID_HANDLE) { Print("EMA Cross Logger: PositionLog FileOpen failed, error ", GetLastError()); return; }
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(t, TIME_DATE | TIME_SECONDS), sym, per, event, dir, DoubleToString(price, _Digits));
   FileClose(h);
   PrintFormat("EMA Position Log: %s %s %s %s %s at %.*f", sym, per, event, dir,
               TimeToString(t, TIME_DATE | TIME_SECONDS), _Digits, price);
  }

//--- v1.01: BACKFILL-CAPABLE, per direct constraint ("the trading platform
//--- has to be open all the time?" - no, it doesn't, now). Instead of only
//--- comparing the last 2 closed bars (which would silently miss every
//--- cross that happened while MT5 was closed), this scans back over
//--- InpLookbackBars closed bars each time it runs and logs any cross it
//--- hasn't already logged (tracked via g_lastCrossTime[k] as a watermark).
//--- On reopening MT5 after being closed for a while, the terminal
//--- auto-downloads the missed price history from the broker, so this
//--- reconstructs what actually happened from real historical bars -
//--- not a guess - rather than only catching crosses live, tick by tick.
//--- Persistent handles (created once, released once in OnDeinit - the
//--- handle-churn bug this project already fixed elsewhere), only
//--- re-scanned when THAT timeframe's own last bar actually changes.
//--- v1.06: per direct instruction - "cannot take trades when [EMA84] is
//--- moving sideways". Slope = EMA84's own change over InpSlopeLookbackBars
//--- bars, normalized by ATR(14) so the same threshold means something
//--- comparable across instruments/timeframes with very different price
//--- scales (same reasoning as this project's %PF-on-pnl/entry_price rule
//--- elsewhere - never compare raw price units across different scales).
//--- Gates NEW entries only (both the regime-flip entry and a re-entry) -
//--- an already-open position is not force-closed just because the slope
//--- flattens mid-trade.
//--- v1.10: second required condition, per direct confirmation - during a
//--- real trend EMA84 pulls AWAY from EMA200 (the gap widens, same idea as
//--- a MACD line expanding); during chop it flattens back toward EMA200
//--- (gap narrows, often hugging it). Both this gap check AND the slope
//--- check above must pass for a new entry - slope alone can be fooled by
//--- a brief sub-swing even while the two EMAs are still sitting close
//--- together (not genuinely separated into a real trend).
bool IsTrending(const double &ef[], const double &es[], const double &atrArr[], const int j, const int lookback)
  {
   if(j < lookback) return(false);
   if(!(atrArr[j] > 0.0)) return(false);
   double slope = MathAbs(ef[j] - ef[j - lookback]);
   if(slope < InpMinSlopeATR * atrArr[j]) return(false);
   double gap = MathAbs(ef[j] - es[j]);
   return(gap >= InpMinGapATR * atrArr[j]);
  }

void CheckTimeframe(const int k)
  {
   ENUM_TIMEFRAMES tf = g_tf[k];
   datetime tfBarTime = iTime(_Symbol, tf, 0);
   if(tfBarTime <= 0) return;
   if(g_tfReady[k] && tfBarTime == g_lastTfBarTime[k]) return;   // no new bar on this TF yet
   bool freshTf = !g_tfReady[k];
   g_lastTfBarTime[k] = tfBarTime;

   if(g_fastHandle[k] == INVALID_HANDLE) g_fastHandle[k] = iMA(_Symbol, tf, InpFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_slowHandle[k] == INVALID_HANDLE) g_slowHandle[k] = iMA(_Symbol, tf, InpSlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_atrHandle[k] == INVALID_HANDLE) g_atrHandle[k] = iATR(_Symbol, tf, 14);
   if(g_fastHandle[k] == INVALID_HANDLE || g_slowHandle[k] == INVALID_HANDLE || g_atrHandle[k] == INVALID_HANDLE) return;

   //--- v1.06: fetch InpSlopeLookbackBars of extra history ahead of the
   //--- normal window so ef[j - InpSlopeLookbackBars] is always in range
   //--- for the slope check below, even at the oldest bar actually scanned.
   int warm = InpSlopeLookbackBars;
   int need = InpLookbackBars + 2 + warm;
   if(BarsCalculated(g_fastHandle[k]) < need || BarsCalculated(g_slowHandle[k]) < need ||
      BarsCalculated(g_atrHandle[k]) < need) return;

   double ef[], es[], cl[], atrArr[];
   ArraySetAsSeries(ef, true); ArraySetAsSeries(es, true); ArraySetAsSeries(cl, true); ArraySetAsSeries(atrArr, true);
   //--- shift 1..need = CLOSED bars only (shift 0 would still be forming) -
   //--- oldest to newest once reversed below.
   if(CopyBuffer(g_fastHandle[k], 0, 1, need, ef) < need) return;
   if(CopyBuffer(g_slowHandle[k], 0, 1, need, es) < need) return;
   if(CopyBuffer(g_atrHandle[k], 0, 1, need, atrArr) < need) return;
   if(CopyClose(_Symbol, tf, 1, need, cl) < need) return;
   ArraySetAsSeries(ef, false); ArraySetAsSeries(es, false); ArraySetAsSeries(cl, false); ArraySetAsSeries(atrArr, false);

   if(freshTf)
     {
      //--- first time this TF is checked: just establish the current
      //--- regime, start FLAT (no backfilled position) - don't guess a
      //--- position that existed before this indicator was attached.
      g_lastDir[k] = (ef[need - 1] > es[need - 1]) ? "UP" : "DOWN";
      g_tfReady[k] = true;
      g_lastProcessedBarTime[k] = iTime(_Symbol, tf, 1);
      return;
     }

   for(int j = warm + 1; j < need; j++)
     {
      datetime barTime = iTime(_Symbol, tf, need - j);   // closed-bar shift matching ef[j]/es[j]/cl[j]
      if(barTime <= g_lastProcessedBarTime[k]) continue;  // already scanned this bar
      g_lastProcessedBarTime[k] = barTime;

      bool regimeUp = ef[j] > es[j];
      bool regimeUpPrev = ef[j - 1] > es[j - 1];
      double px = cl[j];

      if(regimeUp != regimeUpPrev)
        {
         //--- REGIME FLIP: log the raw cross (unchanged), force-close any
         //--- open position and immediately open a new one in the new
         //--- regime direction - same "entry on the cross" starting point
         //--- as before, the v1.02 rule only changes what happens WITHIN
         //--- a regime after this.
         string newDir = regimeUp ? "UP" : "DOWN";
         LogCross(barTime, _Symbol, EnumToString(tf), newDir, px, ef[j], es[j]);
         if(g_posOpen[k])
           {
            LogPosition(barTime, _Symbol, EnumToString(tf), "EXIT", g_posDir[k], px);
            if(k == g_chartTfSlot && g_markersBuilt)
               DrawMarker(barTime, px, false, g_posDir[k] == "UP", (px - g_posEntryPrice[k]) * (g_posDir[k] == "UP" ? 1.0 : -1.0), atrArr[j]);
            g_posOpen[k] = false;
           }
         g_lastDir[k] = newDir; g_lastCrossTime[k] = barTime; g_lastCrossPrice[k] = px;
         //--- v1.06: only open the new-regime position immediately if
         //--- EMA84 is actually trending on this bar - otherwise stay flat
         //--- (the re-entry branch below will open it on a later bar once
         //--- the slope condition is met, same as any other re-entry).
         if(IsTrending(ef, es, atrArr, j, InpSlopeLookbackBars))
           {
            LogPosition(barTime, _Symbol, EnumToString(tf), "ENTRY", newDir, px);
            if(k == g_chartTfSlot && g_markersBuilt) DrawMarker(barTime, px, true, regimeUp, 0.0, atrArr[j]);
            g_posOpen[k] = true; g_posDir[k] = newDir; g_posEntryTime[k] = barTime; g_posEntryPrice[k] = px;
           }
         continue;
        }

      //--- SAME REGIME: the v1.02 rule - exit on a close back across EMA84
      //--- against the position, re-enter on a close back across EMA84 in
      //--- favor of the (unchanged) regime. ASSUMPTION per the file header:
      //--- no VWAP/EMA200 "rejection" condition is checked here, only the
      //--- EMA84 close-cross itself.
      bool closeAboveFast = px > ef[j];
      if(g_posOpen[k])
        {
         bool exitNow = (g_posDir[k] == "UP" && !closeAboveFast) || (g_posDir[k] == "DOWN" && closeAboveFast);
         if(exitNow)
           {
            LogPosition(barTime, _Symbol, EnumToString(tf), "EXIT", g_posDir[k], px);
            if(k == g_chartTfSlot && g_markersBuilt)
               DrawMarker(barTime, px, false, g_posDir[k] == "UP", (px - g_posEntryPrice[k]) * (g_posDir[k] == "UP" ? 1.0 : -1.0), atrArr[j]);
            g_posOpen[k] = false;
           }
        }
      else
        {
         bool reenterUp = (g_lastDir[k] == "UP" && closeAboveFast);
         bool reenterDn = (g_lastDir[k] == "DOWN" && !closeAboveFast);
         if((reenterUp || reenterDn) && IsTrending(ef, es, atrArr, j, InpSlopeLookbackBars))
           {
            string dir = reenterUp ? "UP" : "DOWN";
            LogPosition(barTime, _Symbol, EnumToString(tf), "ENTRY", dir, px);
            if(k == g_chartTfSlot && g_markersBuilt) DrawMarker(barTime, px, true, reenterUp, 0.0, atrArr[j]);
            g_posOpen[k] = true; g_posDir[k] = dir; g_posEntryTime[k] = barTime; g_posEntryPrice[k] = px;
           }
        }
     }
  }

bool g_panelCreated = false;

void PanelLabel(const string suffix, const int x, const int y, const string text, const color col)
  {
   static string lastName[24]; static string lastText[24]; static color lastColor[24]; static int used = 0;
   string nm = PFX + suffix;
   int slot = -1;
   for(int i = 0; i < used; i++) if(lastName[i] == nm) { slot = i; break; }
   if(slot < 0 && used < 24) { slot = used; lastName[slot] = nm; lastText[slot] = ""; lastColor[slot] = clrNONE; used++; }

   if(!g_panelCreated)
     {
      ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, y);
     }
   if(slot < 0 || lastText[slot] != text || lastColor[slot] != col)
     {
      ObjectSetString(0, nm, OBJPROP_TEXT, text);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
      if(slot >= 0) { lastText[slot] = text; lastColor[slot] = col; }
     }
  }

void UpdatePanel()
  {
   int lineH = 16;
   int x = InpPanelX, y = InpPanelY;
   int totalLines = 2 + 4 * 2;

   if(!g_panelCreated)
     {
      ObjectCreate(0, PFX + "bg", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BACK, false);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BGCOLOR, InpPanelBgColor);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_COLOR, InpPanelHeaderColor);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_XDISTANCE, x - 8);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_YDISTANCE, y - 6);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_XSIZE, InpPanelWidth);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, lineH * totalLines + 12);
     }

   PanelLabel("title", x, y, StringFormat("EMA%d/%d Tracker (sim only)", InpFastPeriod, InpSlowPeriod),
              InpPanelHeaderColor);
   y += lineH;
   PanelLabel("hdr", x, y, "TF    REGIME  POSITION", InpPanelHeaderColor);
   y += lineH;

   for(int k = 0; k < 4; k++)
     {
      string tfName = StringSubstr(EnumToString(g_tf[k]), 7);
      string regimeTxt = "n/a";
      color regimeCol = InpPanelTextColor;
      string posTxt = "-";
      color posCol = InpPanelTextColor;
      string infoTxt = "-";

      if(g_tfReady[k] && g_lastDir[k] != "")
        {
         bool regimeUp = (g_lastDir[k] == "UP");
         regimeTxt = regimeUp ? "BULL" : "BEAR";
         regimeCol = regimeUp ? InpPanelUpColor : InpPanelDownColor;

         if(g_posOpen[k])
           {
            bool posUp = (g_posDir[k] == "UP");
            posTxt = posUp ? "LONG" : "SHORT";
            posCol = posUp ? InpPanelUpColor : InpPanelDownColor;
            long heldSec = (long)(TimeCurrent() - g_posEntryTime[k]);
            long heldH = heldSec / 3600;
            string heldTxt = (heldH < 48) ? StringFormat("%dh", (int)heldH) : StringFormat("%.1fd", heldH / 24.0);
            infoTxt = "since " + TimeToString(g_posEntryTime[k], TIME_DATE | TIME_MINUTES) + " (" + heldTxt + ")";
           }
         else
           {
            posTxt = "FLAT";
            posCol = InpPanelTextColor;
            infoTxt = "waiting to re-enter " + (regimeUp ? "LONG" : "SHORT");
           }
        }

      PanelLabel("tf" + IntegerToString(k) + "_name", x, y, tfName, InpPanelTextColor);
      PanelLabel("tf" + IntegerToString(k) + "_regime", x + 40, y, regimeTxt, regimeCol);
      PanelLabel("tf" + IntegerToString(k) + "_pos", x + 100, y, posTxt, posCol);
      y += lineH;
      PanelLabel("tf" + IntegerToString(k) + "_info", x + 10, y, infoTxt, InpPanelTextColor);
      y += lineH;
     }

   g_panelCreated = true;
  }

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   if(rates_total < 2) return(0);

   //--- bar-gated on the CHART's own bar for the panel refresh cadence
   //--- (cheap - just label text), but each tracked TF is independently
   //--- gated on ITS OWN bar time inside CheckTimeframe, so a slow TF
   //--- (D1) is never rechecked just because the chart's own TF is fast.
   datetime lastBar = time[rates_total - 1];
   bool newChartBar = (g_firstCalc || lastBar != g_lastBarTime);
   g_lastBarTime = lastBar;
   g_firstCalc = false;

   if(InpShowHistoricalMarkers && !g_markersBuilt) BuildHistoricalMarkers();

   for(int k = 0; k < 4; k++) CheckTimeframe(k);

   if(InpShowPanel && newChartBar) UpdatePanel();
   if(newChartBar) ChartRedraw(0);

   return(rates_total);
  }
