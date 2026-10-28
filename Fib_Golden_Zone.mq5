//+------------------------------------------------------------------+
//|                                          Fib_Golden_Zone.mq5      |
//|  Standalone indicator - draws ONLY the Fibonacci "golden zone"     |
//|  (the full 38.2-61.8 retracement range by default, split into two  |
//|  separately-coloured bands at the 50.0 midpoint), lightly shaded,  |
//|  and ONLY on a leg that just broke market structure. Per direct    |
//|  description: a fib drawn on just any swing is noise - the point   |
//|  is to catch a retracement into the zone after a confirmed break,  |
//|  not label every wiggle.                                           |
//|                                                                    |
//|  Reuses the same swing-high/swing-low + Break-of-Structure logic   |
//|  as MarketStructure_Break.mq5 (fractal pivots, ATR-filtered for    |
//|  noise, first CLOSE beyond the tracked swing = BOS) - duplicated   |
//|  here rather than shared via #include, matching this project's    |
//|  existing convention of each indicator being self-contained.       |
//|                                                                    |
//|  On a bullish BOS: the "leg" is [swing low that preceded the       |
//|  break -> the running extreme high since the break]. The extreme   |
//|  keeps extending IN MEMORY as price makes new highs, but NOTHING   |
//|  IS DRAWN YET - per direct clarification, the golden zone should   |
//|  only appear once the leg has actually finished and retracement is |
//|  under way, not as a live/growing preview while the leg is still   |
//|  extending. The zone is drawn for the first time at the moment it  |
//|  freezes: a NEW swing forms in the OPPOSITE direction after the    |
//|  break (the impulse is read as finished). Bearish BOS is the       |
//|  mirror. Two bands drawn per leg: InpFibA-InpFibB (38.2-50.0 by     |
//|  default) and InpFibB-InpFibC (50.0-61.8 by default), each its own |
//|  colour - no other fib levels drawn. Visual only, no signals.      |
//|                                                                    |
//|  Timeframe-flip safety: entirely chart-timeframe-native (like      |
//|  MarketStructure_Break.mq5 and the other new standalone             |
//|  indicators) - a rescan on a timeframe-switch reinit is correct,   |
//|  bounded by InpScanLookbackDays below.                             |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property link      ""
#property version   "1.08"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== Structure (same convention as MarketStructure_Break.mq5) ==="
input int      InpPivotWindow  = 5;      // fractal window - bars needed on each side for a swing high/low
input double   InpMinMoveATR   = 1.5;    // a pivot only counts as a new swing if it's at least this many
                                          // ATR away from the previously tracked swing of the same type

input group "=== Golden zone ==="
input double   InpFibA = 0.382;   // v1.08: per direct request - the zone is now the FULL 38.2-61.8
                                   // range (the common wider definition of "the golden zone"), split
                                   // into two separately-coloured bands at the 50.0 midpoint, not just
                                   // the narrow 0.618-0.65 pocket.
input double   InpFibB = 0.5;
input double   InpFibC = 0.618;
input color    InpBand1Color = C'70,55,10';   // v1.02 FIX - real usability bug (per direct report, user
                                              // circled an unrelated box and asked "where does this come
                                              // from"): the old default C'20,60,35'/C'60,25,25' were
                                              // nearly identical to FVG_Liquidity_Zones.mq5's own default
                                              // FVG colors (C'25,55,40'/C'55,25,25') - with both
                                              // indicators on the same chart, an old FVG from a totally
                                              // unrelated consolidation was indistinguishable from this
                                              // file's own golden-pocket zone. Now a distinct gold/amber
                                              // family that doesn't collide with either FVG or liquidity
                                              // zone colors. Band 1 = InpFibA-InpFibB (38.2-50.0 by default).
input color    InpBand2Color = C'95,70,15';   // Band 2 = InpFibB-InpFibC (50.0-61.8 by default) - same
                                              // gold/amber family, slightly brighter so the two bands
                                              // are distinguishable at a glance.
input bool     InpShowLegLines = true;   // v1.05: per direct request - "show me how it was calculated,
                                          // a line at the bottom and top" - draws the leg's own two
                                          // anchor prices (the swing it started at, and the extreme it
                                          // reached) as thin lines spanning the same time range as the
                                          // zone, so the 0.618-0.65 retracement is visibly checkable
                                          // against the actual leg it was computed from.
input color    InpLegLineColor = clrSilver;
input int      InpMaxZones  = 60;
input int      InpMaxAgeDays = 14;       // FROZEN (finished) zones older than this are pruned (0 = never).
                                          // A still-extending (live) zone is never pruned by age.

input group "=== General ==="
input int      InpScanLookbackDays = 30;
input int      InpAtrPeriod        = 14;

//+------------------------------------------------------------------+
struct FibZone
  {
   double   legStart;    // the swing price the leg began at (low for bullish, high for bearish)
   double   extreme;     // running extreme since the break - keeps extending while the zone is live
   datetime startTime;   // the swing's own time (legStart)
   datetime endTime;     // right edge - the latest bar while live, frozen once done
   bool     bullish;
   bool     live;        // still extending; false once frozen
   string   rectName;
  };

FibZone  g_zones[];
string   g_pfx = "FGZ_";
int      g_atrHandle = INVALID_HANDLE;
datetime g_lastBarTime = 0;

double   g_swingHighPrice = 0.0;
datetime g_swingHighTime  = 0;
bool     g_swingHighBroken = true;
double   g_swingLowPrice  = 0.0;
datetime g_swingLowTime   = 0;
bool     g_swingLowBroken  = true;

int      g_liveZone = -1;   // index of the one currently-live zone, or -1 - only one at a time, same
                             // "at most one active" convention as Consolidation_Zones.mq5
datetime g_lastOrderWarnTime = 0;   // v1.03: throttles the "break withheld by ordering" diagnostic
                                     // below to at most once/hour, so a long-withheld break doesn't
                                     // spam the log every single bar while it stays withheld

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpPivotWindow <= 0)
     {
      Print("Fib_Golden_Zone: InpPivotWindow must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpFibA <= 0.0 || InpFibB <= InpFibA || InpFibC <= InpFibB)
     {
      Print("Fib_Golden_Zone: InpFibA < InpFibB < InpFibC must all hold, and InpFibA must be > 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpAtrPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("Fib_Golden_Zone: failed to create ATR handle.");
      return(INIT_FAILED);
     }
   ArrayResize(g_zones, 0);
   g_liveZone = -1;
   g_lastBarTime      = 0;
   g_swingHighPrice   = 0.0; g_swingHighTime = 0; g_swingHighBroken = true;
   g_swingLowPrice    = 0.0; g_swingLowTime  = 0; g_swingLowBroken  = true;
   PrintFormat("Fib_Golden_Zone v1.08 OnInit: %s %s  pivotWindow=%d  minMoveATR=%.2f  zone=%.3f-%.3f-%.3f",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpPivotWindow, InpMinMoveATR, InpFibA, InpFibB, InpFibC);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_pfx);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| One retracement level -> price, for either leg direction.         |
//+------------------------------------------------------------------+
double FibPrice(const int idx, const double level)
  {
   if(g_zones[idx].bullish)
     {
      double range = g_zones[idx].extreme - g_zones[idx].legStart;
      return g_zones[idx].extreme - level * range;
     }
   double range = g_zones[idx].legStart - g_zones[idx].extreme;
   return g_zones[idx].extreme + level * range;
  }

//+------------------------------------------------------------------+
void DrawBand(const string nm, const int idx, const double levelLo, const double levelHi, const color col)
  {
   //--- the two price endpoints of a band depend on leg direction -
   //--- FibPrice(levelLo) and FibPrice(levelHi) aren't consistently
   //--- "top"/"bottom" between bullish and bearish legs, so sort them.
   double p1 = FibPrice(idx, levelLo);
   double p2 = FibPrice(idx, levelHi);
   double top = MathMax(p1, p2), bottom = MathMin(p1, p2);
   if(ObjectFind(0, nm) < 0)
     {
      if(!ObjectCreate(0, nm, OBJ_RECTANGLE, 0, g_zones[idx].startTime, top, g_zones[idx].endTime, bottom))
        {
         PrintFormat("Fib_Golden_Zone: ObjectCreate FAILED for %s - error %d", nm, GetLastError());
         return;
        }
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, true);
      ObjectSetInteger(0, nm, OBJPROP_FILL, true);
      ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
     }
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectMove(0, nm, 0, g_zones[idx].startTime, top);
   ObjectMove(0, nm, 1, g_zones[idx].endTime, bottom);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP,
                    StringFormat("%s %.3f-%.3f: %s..%s", g_zones[idx].bullish ? "Bullish" : "Bearish",
                                 levelLo, levelHi, DoubleToString(bottom, _Digits), DoubleToString(top, _Digits)));
  }

//+------------------------------------------------------------------+
void DrawZone(const int idx)
  {
   string nm = g_zones[idx].rectName;
   //--- v1.08: two bands per direct request - the full InpFibA-InpFibC
   //--- range (38.2-61.8 by default, the common wider "golden zone"),
   //--- split at InpFibB (50.0) into two separately-coloured halves,
   //--- instead of the old single narrow 0.618-0.65 pocket.
   DrawBand(nm + "_b1", idx, InpFibA, InpFibB, InpBand1Color);
   DrawBand(nm + "_b2", idx, InpFibB, InpFibC, InpBand2Color);

   //--- v1.05: the leg's own two anchor prices - legStart (the swing the
   //--- leg began at) and extreme (the frozen high/low it reached) -
   //--- drawn as thin lines spanning the same time range as the zone
   //--- rectangle, so the retracement math is directly checkable against
   //--- the actual leg: top/bottom of the rectangle above should always
   //--- sit strictly between these two lines, closer to the extreme one.
   if(InpShowLegLines)
     {
      string nmStart = nm + "_legstart";
      string nmEnd   = nm + "_legend";
      if(ObjectFind(0, nmStart) < 0)
        {
         ObjectCreate(0, nmStart, OBJ_TREND, 0, g_zones[idx].startTime, g_zones[idx].legStart,
                      g_zones[idx].endTime, g_zones[idx].legStart);
         ObjectSetInteger(0, nmStart, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nmStart, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, nmStart, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, nmStart, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, nmStart, OBJPROP_RAY_RIGHT, false);
        }
      ObjectSetInteger(0, nmStart, OBJPROP_TIME, 0, g_zones[idx].startTime);
      ObjectSetDouble (0, nmStart, OBJPROP_PRICE, 0, g_zones[idx].legStart);
      ObjectSetInteger(0, nmStart, OBJPROP_TIME, 1, g_zones[idx].endTime);
      ObjectSetDouble (0, nmStart, OBJPROP_PRICE, 1, g_zones[idx].legStart);
      ObjectSetInteger(0, nmStart, OBJPROP_COLOR, InpLegLineColor);
      ObjectSetString (0, nmStart, OBJPROP_TOOLTIP,
                        "Leg start (" + (g_zones[idx].bullish ? "low" : "high") + "): " +
                        DoubleToString(g_zones[idx].legStart, _Digits));

      if(ObjectFind(0, nmEnd) < 0)
        {
         ObjectCreate(0, nmEnd, OBJ_TREND, 0, g_zones[idx].startTime, g_zones[idx].extreme,
                      g_zones[idx].endTime, g_zones[idx].extreme);
         ObjectSetInteger(0, nmEnd, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nmEnd, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, nmEnd, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, nmEnd, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, nmEnd, OBJPROP_RAY_RIGHT, false);
        }
      ObjectSetInteger(0, nmEnd, OBJPROP_TIME, 0, g_zones[idx].startTime);
      ObjectSetDouble (0, nmEnd, OBJPROP_PRICE, 0, g_zones[idx].extreme);
      ObjectSetInteger(0, nmEnd, OBJPROP_TIME, 1, g_zones[idx].endTime);
      ObjectSetDouble (0, nmEnd, OBJPROP_PRICE, 1, g_zones[idx].extreme);
      ObjectSetInteger(0, nmEnd, OBJPROP_COLOR, InpLegLineColor);
      ObjectSetString (0, nmEnd, OBJPROP_TOOLTIP,
                        "Leg extreme (" + (g_zones[idx].bullish ? "high" : "low") + "): " +
                        DoubleToString(g_zones[idx].extreme, _Digits));
     }
  }

//+------------------------------------------------------------------+
void PruneZones(const datetime lastBarTime)
  {
   if(InpMaxAgeDays > 0)
     {
      datetime cutoff = lastBarTime - (datetime)((long)InpMaxAgeDays * 86400);
      for(int k = ArraySize(g_zones) - 1; k >= 0; k--)
        {
         if(!g_zones[k].live && g_zones[k].endTime < cutoff)
           {
            ObjectDelete(0, g_zones[k].rectName + "_b1");
            ObjectDelete(0, g_zones[k].rectName + "_b2");
            ObjectDelete(0, g_zones[k].rectName + "_legstart");
            ObjectDelete(0, g_zones[k].rectName + "_legend");
            g_zones[k] = g_zones[ArraySize(g_zones) - 1];
            ArrayResize(g_zones, ArraySize(g_zones) - 1);
            if(g_liveZone == k) g_liveZone = -1;
            else if(g_liveZone == ArraySize(g_zones)) g_liveZone = k;   // the moved slot
           }
        }
     }
   while(ArraySize(g_zones) > InpMaxZones)
     {
      int oldest = -1;
      for(int k = 0; k < ArraySize(g_zones); k++)
         if(!g_zones[k].live && (oldest < 0 || g_zones[k].startTime < g_zones[oldest].startTime)) oldest = k;
      if(oldest < 0) break;
      ObjectDelete(0, g_zones[oldest].rectName + "_b1");
      ObjectDelete(0, g_zones[oldest].rectName + "_b2");
      ObjectDelete(0, g_zones[oldest].rectName + "_legstart");
      ObjectDelete(0, g_zones[oldest].rectName + "_legend");
      g_zones[oldest] = g_zones[ArraySize(g_zones) - 1];
      ArrayResize(g_zones, ArraySize(g_zones) - 1);
      if(g_liveZone == oldest) g_liveZone = -1;
      else if(g_liveZone == ArraySize(g_zones)) g_liveZone = oldest;
     }
  }

//+------------------------------------------------------------------+
void StartZone(const bool bullish, const double legStart, const double extreme,
               const datetime startTime, const datetime endTime)
  {
   int zi = ArraySize(g_zones);
   ArrayResize(g_zones, zi + 1);
   g_zones[zi].bullish   = bullish;
   g_zones[zi].legStart  = legStart;
   g_zones[zi].extreme   = extreme;
   g_zones[zi].startTime = startTime;
   g_zones[zi].endTime   = endTime;
   g_zones[zi].live      = true;
   g_zones[zi].rectName  = g_pfx + (bullish ? "up_" : "dn_") + IntegerToString((long)startTime);
   g_liveZone = zi;
   //--- v1.04: NOT drawn here - per direct clarification, the zone only
   //--- appears once this leg is finished and retracement has started
   //--- (see the freeze point in OnCalculate's own comment). Nothing on
   //--- the chart yet, this just starts tracking the leg internally.
   //--- v1.03: diagnostic - prints exactly which leg this zone anchored
   //--- to, checkable against MarketStructure_Break.mq5's own BOS line.
   PrintFormat("Fib_Golden_Zone: new %s leg - start=%s @ %s, break/extreme=%s @ %s",
               bullish ? "BULLISH" : "BEARISH",
               DoubleToString(legStart, _Digits), TimeToString(startTime, TIME_DATE | TIME_MINUTES),
               DoubleToString(extreme, _Digits), TimeToString(endTime, TIME_DATE | TIME_MINUTES));
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   int w = InpPivotWindow;
   int minBars = 2 * w + 10;
   if(rates_total < minBars) return(0);

   //--- v1.01 FIX (Opus audit - real bugs, same root causes already
   //--- fixed in MarketStructure_Break.mq5 v1.01, see that file's own
   //--- comment for the full mechanism): (a) g_lastBarTime committed
   //--- before confirming the ATR fetch actually succeeded could
   //--- silently skip the entire backfill forever; (b) `from` based on
   //--- a fixed "last 3 bars" window instead of prev_calculated could
   //--- silently drop bars after any gap; (c) the pivot loop could
   //--- judge a bar against the STILL-FORMING bar's momentary high/low.
   bool freshAttach = (prev_calculated <= 0);
   if(!freshAttach && rates_total <= prev_calculated) return(rates_total);   // nothing new
   int lookbackBars = (InpScanLookbackDays > 0)
                       ? (int)((long)InpScanLookbackDays * 86400 / PeriodSeconds(PERIOD_CURRENT)) + minBars
                       : rates_total;
   int from = freshAttach ? MathMax(w, rates_total - lookbackBars) : MathMax(w, prev_calculated - 1 - w);
   if(freshAttach)
     {
      ObjectsDeleteAll(0, g_pfx);
      ArrayResize(g_zones, 0);
      g_liveZone = -1;
      g_swingHighPrice = 0.0; g_swingHighTime = 0; g_swingHighBroken = true;
      g_swingLowPrice  = 0.0; g_swingLowTime  = 0; g_swingLowBroken  = true;
     }

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   int atrCount = rates_total - from;
   if(CopyBuffer(g_atrHandle, 0, 0, atrCount, atrBuf) < atrCount)
      return(0);

   for(int i = MathMax(from, w); i < rates_total - 1 - w; i++)
     {
      double atrHere = atrBuf[rates_total - 1 - i];
      if(atrHere <= 0.0) continue;
      double minMove = InpMinMoveATR * atrHere;

      bool isPeak = true, isTrough = true;
      for(int k = 1; k <= w; k++)
        {
         if(high[i] < high[i - k] || high[i] <= high[i + k]) isPeak = false;
         if(low[i]  > low[i - k]  || low[i]  >= low[i + k])  isTrough = false;
         if(!isPeak && !isTrough) break;
        }

      //--- v1.04 FIX (per direct clarification): the zone used to DRAW
      //--- immediately on the break and visibly grow with the leg - per
      //--- direct correction, the golden zone should only appear once
      //--- the leg that broke structure has actually FINISHED and
      //--- retracement is under way, not as a live/growing preview.
      //--- Drawing is now deferred entirely to this freeze point (a
      //--- fresh opposite swing = the impulse is read as finished) -
      //--- see the now-silent "extend" block below, which still tracks
      //--- the extreme in memory every bar but no longer renders it.
      if(isTrough && g_liveZone >= 0 && g_zones[g_liveZone].bullish && g_zones[g_liveZone].live)
        {
         g_zones[g_liveZone].live = false;
         DrawZone(g_liveZone);
         g_liveZone = -1;
        }
      if(isPeak && g_liveZone >= 0 && !g_zones[g_liveZone].bullish && g_zones[g_liveZone].live)
        {
         g_zones[g_liveZone].live = false;
         DrawZone(g_liveZone);
         g_liveZone = -1;
        }

      //--- v1.06 FIX (real bug, confirmed from the Experts log - a
      //--- withheld-break diagnostic showed the tracked low's TIME still
      //--- pointing at an old touch days earlier, even though price had
      //--- clearly retested that same support level much more recently):
      //--- this used to only update BOTH price and time together, gated
      //--- on the new pivot being far enough away (minMove) to count as
      //--- a genuinely different level. That conflated two different
      //--- questions - "is this a new price level" (correctly needs the
      //--- ATR filter, so minor noise doesn't keep redefining the level)
      //--- and "when did price last touch this level" (should update on
      //--- ANY confirmed same-type pivot near it, including a retest at
      //--- essentially the same price) - which is exactly what Fib's own
      //--- ordering requirement (the opposite swing must be the MORE
      //--- RECENT of the two) depends on to correctly anchor a leg. Now:
      //--- a genuinely new/distant pivot replaces price+time as before;
      //--- a same-level retest keeps the more extreme price but ALWAYS
      //--- refreshes the time to this latest touch.
      //--- note: g_swing*Broken is only reset in the genuinely-new-swing
      //--- branch, NOT on a same-level retest - once a swing has been
      //--- broken, a later retest of that same old level (now acting as
      //--- the other side, e.g. former resistance now support) must NOT
      //--- re-arm it as if it were a fresh, unbroken swing again.
      if(isPeak)
        {
         if(g_swingHighTime == 0 || MathAbs(high[i] - g_swingHighPrice) >= minMove)
           {
            g_swingHighPrice  = high[i];
            g_swingHighBroken = false;
           }
         else
            g_swingHighPrice = MathMax(g_swingHighPrice, high[i]);
         g_swingHighTime = time[i];
        }
      if(isTrough)
        {
         if(g_swingLowTime == 0 || MathAbs(low[i] - g_swingLowPrice) >= minMove)
           {
            g_swingLowPrice  = low[i];
            g_swingLowBroken = false;
           }
         else
            g_swingLowPrice = MathMin(g_swingLowPrice, low[i]);
         g_swingLowTime = time[i];
        }

      //--- v1.04: still tracks the leg's running extreme/endTime every
      //--- bar while live (needed so the frozen zone, once drawn, is
      //--- correct) - just no longer calls DrawZone here. Nothing is
      //--- rendered until the freeze point above actually draws it.
      if(g_liveZone >= 0 && g_zones[g_liveZone].live)
        {
         if(g_zones[g_liveZone].bullish) g_zones[g_liveZone].extreme = MathMax(g_zones[g_liveZone].extreme, high[i]);
         else                            g_zones[g_liveZone].extreme = MathMin(g_zones[g_liveZone].extreme, low[i]);
         g_zones[g_liveZone].endTime = time[i];
        }

      //--- BOS check - only ever starts a NEW zone when none is
      //--- currently live (one leg at a time, same convention as
      //--- MarketStructure_Break.mq5's own break tracking)
      int lastClosed = i;
      if(g_liveZone < 0)
        {
         //--- v1.07 FIX (real design bug, confirmed live from the
         //--- Experts log - v1.01's own ordering requirement, "opposite
         //--- swing must be more recent than the swing being broken",
         //--- turned out to be structurally impossible to satisfy for a
         //--- CONTINUATION break deep into an established trend: in a
         //--- sustained decline, the tracked swing LOW keeps refreshing
         //--- to a newer time on every fresh low, while the relevant
         //--- swing HIGH (the last real pullback top) stays fixed from
         //--- much earlier - so the low is ALWAYS more recent than the
         //--- high for the entire length of the trend, and a bearish
         //--- break could only ever fire right at the very start of a
         //--- fresh reversal, never on a later continuation break. Live
         //--- evidence: a 7-day decline produced zero bearish legs, only
         //--- an unbroken string of WITHHELD lines the whole way down.
         //--- Dropped the ordering requirement entirely - anchors to
         //--- whichever opposite swing is CURRENTLY tracked, regardless
         //--- of its relative age, exactly like MarketStructure_Break.mq5
         //--- already does (no ordering check there at all).
         bool bullBreakPrice = !g_swingHighBroken && g_swingHighTime != 0 && close[lastClosed] > g_swingHighPrice;
         bool bearBreakPrice = !g_swingLowBroken  && g_swingLowTime  != 0 && close[lastClosed] < g_swingLowPrice;
         if(bullBreakPrice && g_swingLowTime != 0)
           {
            g_swingHighBroken = true;
            StartZone(true, g_swingLowPrice, MathMax(g_swingHighPrice, high[lastClosed]),
                      g_swingLowTime, time[lastClosed]);
           }
         else if(bearBreakPrice && g_swingHighTime != 0)
           {
            g_swingLowBroken = true;
            StartZone(false, g_swingHighPrice, MathMin(g_swingLowPrice, low[lastClosed]),
                      g_swingHighTime, time[lastClosed]);
           }
         //--- v1.03 diagnostic - kept for the one remaining case this can
         //--- still withhold a break: no opposite swing has EVER been
         //--- confirmed yet at all (only possible very early in history).
         else if((bullBreakPrice || bearBreakPrice) && (datetime)(time[i] - g_lastOrderWarnTime) >= 3600)
           {
            g_lastOrderWarnTime = time[i];
            PrintFormat("Fib_Golden_Zone: price broke the tracked %s swing at %s but the zone was WITHHELD - "
                        "tracked high=%s @ %s, tracked low=%s @ %s (no opposite swing confirmed yet at all)",
                        bullBreakPrice ? "HIGH" : "LOW", TimeToString(time[i], TIME_DATE | TIME_MINUTES),
                        DoubleToString(g_swingHighPrice, _Digits), TimeToString(g_swingHighTime, TIME_DATE | TIME_MINUTES),
                        DoubleToString(g_swingLowPrice, _Digits), TimeToString(g_swingLowTime, TIME_DATE | TIME_MINUTES));
           }
        }
     }

   g_lastBarTime = time[rates_total - 1];
   PruneZones(g_lastBarTime);
   return(rates_total);
  }
