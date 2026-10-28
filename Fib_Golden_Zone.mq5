//+------------------------------------------------------------------+
//|                                          Fib_Golden_Zone.mq5      |
//|  Standalone indicator - draws ONLY the Fibonacci "golden pocket"  |
//|  (0.618-0.65 retracement), lightly shaded, and ONLY on a leg that  |
//|  just broke market structure. Per direct description: a fib drawn |
//|  on just any swing is noise - the point is to catch a retracement |
//|  into the zone after a confirmed break, not label every wiggle.   |
//|                                                                    |
//|  Reuses the same swing-high/swing-low + Break-of-Structure logic   |
//|  as MarketStructure_Break.mq5 (fractal pivots, ATR-filtered for    |
//|  noise, first CLOSE beyond the tracked swing = BOS) - duplicated   |
//|  here rather than shared via #include, matching this project's    |
//|  existing convention of each indicator being self-contained.       |
//|                                                                    |
//|  On a bullish BOS: the "leg" is [swing low that preceded the       |
//|  break -> the running extreme high since the break]. The extreme   |
//|  keeps extending as price makes new highs; the leg (and its zone)  |
//|  freezes the moment a NEW swing low forms after the break (the      |
//|  impulse is read as finished, a retracement/pullback has started   |
//|  - which is the whole point of drawing the zone). Bearish BOS is    |
//|  the mirror. Zone = [extreme - 0.65*range, extreme - 0.618*range]  |
//|  for a bullish leg (mirrored for bearish) - the golden pocket only,|
//|  no other fib levels drawn. Visual only, no signals/alerts.        |
//|                                                                    |
//|  Timeframe-flip safety: entirely chart-timeframe-native (like      |
//|  MarketStructure_Break.mq5 and the other new standalone             |
//|  indicators) - a rescan on a timeframe-switch reinit is correct,   |
//|  bounded by InpScanLookbackDays below.                             |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property link      ""
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== Structure (same convention as MarketStructure_Break.mq5) ==="
input int      InpPivotWindow  = 5;      // fractal window - bars needed on each side for a swing high/low
input double   InpMinMoveATR   = 1.5;    // a pivot only counts as a new swing if it's at least this many
                                          // ATR away from the previously tracked swing of the same type

input group "=== Golden zone ==="
input double   InpFibLow    = 0.618;     // shallow edge of the pocket
input double   InpFibHigh   = 0.65;      // deep edge of the pocket - per direct request, ONLY this band
                                          // is drawn, no other fib levels
input color    InpBullColor = C'20,60,35';   // lightly shaded - bullish leg (retracement expected DOWN
                                              // into the zone before continuation up)
input color    InpBearColor = C'60,25,25';   // bearish leg
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

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpPivotWindow <= 0)
     {
      Print("Fib_Golden_Zone: InpPivotWindow must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpFibLow <= 0.0 || InpFibHigh <= InpFibLow)
     {
      Print("Fib_Golden_Zone: InpFibHigh must be greater than InpFibLow, both > 0.");
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
   PrintFormat("Fib_Golden_Zone v1.00 OnInit: %s %s  pivotWindow=%d  minMoveATR=%.2f  pocket=%.3f-%.3f",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpPivotWindow, InpMinMoveATR, InpFibLow, InpFibHigh);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_pfx);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
void DrawZone(const int idx)
  {
   double top, bottom;
   if(g_zones[idx].bullish)
     {
      double range = g_zones[idx].extreme - g_zones[idx].legStart;
      top    = g_zones[idx].extreme - InpFibLow  * range;
      bottom = g_zones[idx].extreme - InpFibHigh * range;
     }
   else
     {
      double range = g_zones[idx].legStart - g_zones[idx].extreme;
      bottom = g_zones[idx].extreme + InpFibLow  * range;
      top    = g_zones[idx].extreme + InpFibHigh * range;
     }
   color col = g_zones[idx].bullish ? InpBullColor : InpBearColor;
   string nm = g_zones[idx].rectName;
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
                    StringFormat("%s golden pocket %.3f-%.3f: %s..%s", g_zones[idx].bullish ? "Bullish" : "Bearish",
                                 InpFibLow, InpFibHigh, DoubleToString(bottom, _Digits), DoubleToString(top, _Digits)));
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
            ObjectDelete(0, g_zones[k].rectName);
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
      ObjectDelete(0, g_zones[oldest].rectName);
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
   DrawZone(zi);
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

   datetime t0 = time[rates_total - 1];
   if(t0 == g_lastBarTime) return(rates_total);
   bool freshAttach = (prev_calculated <= 0);
   g_lastBarTime = t0;

   int lookbackBars = (InpScanLookbackDays > 0)
                       ? (int)((long)InpScanLookbackDays * 86400 / PeriodSeconds(PERIOD_CURRENT)) + minBars
                       : rates_total;
   int from = freshAttach ? MathMax(w, rates_total - lookbackBars) : MathMax(w, rates_total - 3 - w);
   if(freshAttach)
     {
      ObjectsDeleteAll(0, g_pfx);
      ArrayResize(g_zones, 0);
      g_liveZone = -1;
      g_swingHighPrice = 0.0; g_swingHighTime = 0; g_swingHighBroken = true;
      g_swingLowPrice  = 0.0; g_swingLowTime  = 0; g_swingLowBroken  = true;
     }
   if(from >= rates_total) return(rates_total);

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   int atrCount = rates_total - from;
   if(CopyBuffer(g_atrHandle, 0, 0, atrCount, atrBuf) < atrCount)
      return(0);

   for(int i = MathMax(from, w); i < rates_total - w; i++)
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

      //--- a fresh swing low after a bullish leg is live = the impulse is
      //--- read as finished (retracement under way) - freeze that zone
      //--- BEFORE adopting the new swing low, so the frozen extreme still
      //--- reflects the leg that actually broke structure.
      if(isTrough && g_liveZone >= 0 && g_zones[g_liveZone].bullish && g_zones[g_liveZone].live)
        {
         g_zones[g_liveZone].live = false;
         g_liveZone = -1;
        }
      if(isPeak && g_liveZone >= 0 && !g_zones[g_liveZone].bullish && g_zones[g_liveZone].live)
        {
         g_zones[g_liveZone].live = false;
         g_liveZone = -1;
        }

      if(isPeak && (g_swingHighTime == 0 || MathAbs(high[i] - g_swingHighPrice) >= minMove))
        {
         g_swingHighPrice  = high[i];
         g_swingHighTime   = time[i];
         g_swingHighBroken = false;
        }
      if(isTrough && (g_swingLowTime == 0 || MathAbs(low[i] - g_swingLowPrice) >= minMove))
        {
         g_swingLowPrice  = low[i];
         g_swingLowTime   = time[i];
         g_swingLowBroken = false;
        }

      //--- extend the live zone's extreme with this bar, same as any
      //--- other bar in the leg
      if(g_liveZone >= 0 && g_zones[g_liveZone].live)
        {
         if(g_zones[g_liveZone].bullish) g_zones[g_liveZone].extreme = MathMax(g_zones[g_liveZone].extreme, high[i]);
         else                            g_zones[g_liveZone].extreme = MathMin(g_zones[g_liveZone].extreme, low[i]);
         g_zones[g_liveZone].endTime = time[i];
         DrawZone(g_liveZone);
        }

      //--- BOS check - only ever starts a NEW zone when none is
      //--- currently live (one leg at a time, same convention as
      //--- MarketStructure_Break.mq5's own break tracking)
      int lastClosed = i;
      if(g_liveZone < 0)
        {
         if(!g_swingHighBroken && g_swingHighTime != 0 && close[lastClosed] > g_swingHighPrice &&
            g_swingLowTime != 0 && g_swingLowTime < g_swingHighTime)
           {
            g_swingHighBroken = true;
            StartZone(true, g_swingLowPrice, MathMax(g_swingHighPrice, high[lastClosed]),
                      g_swingLowTime, time[lastClosed]);
           }
         else if(!g_swingLowBroken && g_swingLowTime != 0 && close[lastClosed] < g_swingLowPrice &&
                 g_swingHighTime != 0 && g_swingHighTime < g_swingLowTime)
           {
            g_swingLowBroken = true;
            StartZone(false, g_swingHighPrice, MathMin(g_swingLowPrice, low[lastClosed]),
                      g_swingHighTime, time[lastClosed]);
           }
        }
     }

   PruneZones(t0);
   return(rates_total);
  }
