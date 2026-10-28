//+------------------------------------------------------------------+
//|                                        Consolidation_Zones.mq5    |
//|  Standalone indicator - draws a box around a price range while it |
//|  is compressing/consolidating, and freezes + recolors it the      |
//|  moment price genuinely expands back out of it.                   |
//|                                                                    |
//|  Construction: a box STARTS once a short rolling window of bars   |
//|  has a high-low range at or below InpRangeATRMax x ATR (price is   |
//|  compressed). While active, the box's own high/low extend to      |
//|  absorb each new bar's wick - UNLESS doing so would push the      |
//|  box's total range past InpRangeATRMax x ATR, in which case the    |
//|  box is done: it freezes at its current extent (not including     |
//|  this bar), recolors to the "broken" colour, and a fresh box can   |
//|  start forming again from here. No signals, no alerts - purely     |
//|  visual context, same as the other new standalone indicators.      |
//|                                                                    |
//|  Timeframe-flip safety: consolidation is entirely a function of    |
//|  the CHART's own bars (like FVG_Liquidity_Zones.mq5 and            |
//|  MarketStructure_Break.mq5, unlike Important_SR_Levels' timeframe- |
//|  INDEPENDENT H4/D/W layers) - a different timeframe genuinely      |
//|  means different consolidation ranges, so a full rescan on the     |
//|  reinit a timeframe flip triggers is correct, not wasted.          |
//|  InpScanLookbackDays bounds that one-time cost.                    |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property link      ""
#property version   "1.01"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== Consolidation detection ==="
input int      InpStartWindow     = 6;        // how many bars' own high-low range is checked to START a
                                               // new box - a short window so a box can form quickly once
                                               // price actually compresses
input double   InpRangeATRMax     = 2.0;      // a window/box counts as "consolidating" while its total
                                               // high-low range stays at or below this many ATR - lower
                                               // = tighter/stricter boxes, higher = looser
input int      InpMinBoxBars      = 6;        // a box must span at least this many bars before it's
                                               // considered real enough to draw - filters a single
                                               // quiet bar or two from counting as "consolidation"

input group "=== Drawing ==="
input color    InpActiveColor     = C'30,55,70';    // light-shaded while still forming/active
input color    InpBrokenUpColor   = C'0,130,70';    // expanded out the TOP - brighter green
input color    InpBrokenDownColor = C'150,40,40';   // expanded out the BOTTOM - brighter red
input int      InpMaxZones        = 60;             // cap on boxes (active+broken) tracked/drawn at once
input int      InpMaxAgeDays      = 14;             // BROKEN boxes older than this are pruned (0 = never).
                                                     // The active box is never pruned by age.

input group "=== General ==="
input int      InpScanLookbackDays = 30;      // how far back the initial backfill scans, in days of the
                                               // CHART's own timeframe - bounds the one-time cost on
                                               // attach/reinit, same reasoning as this project's other
                                               // new standalone indicators.
input int      InpAtrPeriod        = 14;

//+------------------------------------------------------------------+
struct Box
  {
   double   high;
   double   low;
   datetime startTime;
   datetime endTime;     // right edge - advances each bar while active, frozen once broken
   bool     active;
   bool     brokenUp;    // only meaningful once active==false
  };

Box      g_boxes[];
string   g_pfx = "CZB_";
int      g_atrHandle = INVALID_HANDLE;
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpStartWindow <= 1)
     {
      Print("Consolidation_Zones: InpStartWindow must be >= 2.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpAtrPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("Consolidation_Zones: failed to create ATR handle.");
      return(INIT_FAILED);
     }
   ArrayResize(g_boxes, 0);
   g_lastBarTime = 0;
   PrintFormat("Consolidation_Zones v1.01 OnInit: %s %s  startWindow=%d  rangeATRMax=%.2f  scanLookback=%dd",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpStartWindow, InpRangeATRMax, InpScanLookbackDays);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_pfx);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
string BoxName(const int idx) { return g_pfx + "box_" + IntegerToString((long)g_boxes[idx].startTime); }

//+------------------------------------------------------------------+
void DrawBox(const int idx, const color col)
  {
   string nm = BoxName(idx);
   if(ObjectFind(0, nm) < 0)
     {
      if(!ObjectCreate(0, nm, OBJ_RECTANGLE, 0, g_boxes[idx].startTime, g_boxes[idx].high,
                        g_boxes[idx].endTime, g_boxes[idx].low))
        {
         PrintFormat("Consolidation_Zones: ObjectCreate FAILED for %s - error %d", nm, GetLastError());
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
   ObjectMove(0, nm, 0, g_boxes[idx].startTime, g_boxes[idx].high);
   ObjectMove(0, nm, 1, g_boxes[idx].endTime, g_boxes[idx].low);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP,
                    StringFormat("Consolidation %s..%s  range=%s",
                                 TimeToString(g_boxes[idx].startTime, TIME_DATE | TIME_MINUTES),
                                 TimeToString(g_boxes[idx].endTime, TIME_DATE | TIME_MINUTES),
                                 DoubleToString(g_boxes[idx].high - g_boxes[idx].low, _Digits)));
  }

//+------------------------------------------------------------------+
void PruneBoxes(const datetime lastBarTime)
  {
   if(InpMaxAgeDays > 0)
     {
      datetime cutoff = lastBarTime - (datetime)((long)InpMaxAgeDays * 86400);
      for(int k = ArraySize(g_boxes) - 1; k >= 0; k--)
        {
         if(!g_boxes[k].active && g_boxes[k].endTime < cutoff)
           {
            ObjectDelete(0, BoxName(k));
            g_boxes[k] = g_boxes[ArraySize(g_boxes) - 1];
            ArrayResize(g_boxes, ArraySize(g_boxes) - 1);
           }
        }
     }
   while(ArraySize(g_boxes) > InpMaxZones)
     {
      int oldest = -1;
      for(int k = 0; k < ArraySize(g_boxes); k++)
         if(!g_boxes[k].active && (oldest < 0 || g_boxes[k].startTime < g_boxes[oldest].startTime)) oldest = k;
      if(oldest < 0) break;   // every remaining box is the one active box - nothing safe to evict
      ObjectDelete(0, BoxName(oldest));
      g_boxes[oldest] = g_boxes[ArraySize(g_boxes) - 1];
      ArrayResize(g_boxes, ArraySize(g_boxes) - 1);
     }
  }

//+------------------------------------------------------------------+
//| -1 if no box is currently active, else its index in g_boxes[].    |
//| At most one box is ever active at a time.                          |
//+------------------------------------------------------------------+
int ActiveBoxIndex()
  {
   for(int k = 0; k < ArraySize(g_boxes); k++)
      if(g_boxes[k].active) return k;
   return -1;
  }

//+------------------------------------------------------------------+
//| v1.01 (Opus audit): guards against appending a true duplicate      |
//| array entry if a 1-bar processing overlap between calls ever re-   |
//| detects the same box start - BoxName()'s own ObjectFind guard       |
//| already made the DRAWN object idempotent, but without this the     |
//| underlying g_boxes[] array could still grow a second identical     |
//| struct entry under the same name, corrupting later pruning/lookup. |
//+------------------------------------------------------------------+
bool BoxExists(const datetime startTime)
  {
   for(int k = 0; k < ArraySize(g_boxes); k++)
      if(g_boxes[k].startTime == startTime) return true;
   return false;
  }

//+------------------------------------------------------------------+
//--- v1.01 FIX (Opus audit): `atr[]` is offset-aligned to `from` (atr[0]
//--- == bar `from`), NOT a full rates_total-sized array indexed by
//--- absolute bar number - see the call site's own comment for why.
void ProcessBars(const int from, const int n, const datetime &time[], const double &high[],
                  const double &low[], const double &close[], const double &atr[])
  {
   //--- v1.01 FIX (Opus audit, real bug): used to run up to i<n, which
   //--- lets this read the STILL-FORMING bar (n-1) as if it were closed
   //--- - its high/low change every tick, so a box could start/extend/
   //--- break off a momentary value that never actually closed that way.
   for(int i = MathMax(from, InpStartWindow); i < n - 1; i++)
     {
      double atrHere = atr[i - from];
      if(atrHere <= 0.0) continue;
      double maxRange = InpRangeATRMax * atrHere;

      int ai = ActiveBoxIndex();
      if(ai < 0)
        {
         //--- try to START a new box from the last InpStartWindow bars
         //--- ending here (inclusive of bar i)
         double hi = high[i], lo = low[i];
         for(int k = 1; k < InpStartWindow; k++)
           {
            hi = MathMax(hi, high[i - k]);
            lo = MathMin(lo, low[i - k]);
           }
         datetime newStart = time[i - InpStartWindow + 1];
         if((hi - lo) <= maxRange && !BoxExists(newStart))
           {
            int zi = ArraySize(g_boxes);
            ArrayResize(g_boxes, zi + 1);
            g_boxes[zi].high      = hi;
            g_boxes[zi].low       = lo;
            g_boxes[zi].startTime = newStart;
            g_boxes[zi].endTime   = time[i];
            g_boxes[zi].active    = true;
            g_boxes[zi].brokenUp  = false;
            DrawBox(zi, InpActiveColor);
           }
         continue;
        }

      //--- extend the active box with this bar's wick, unless that would
      //--- push its total range past the compression cap - that's the
      //--- expansion/breakout moment.
      double newHigh = MathMax(g_boxes[ai].high, high[i]);
      double newLow  = MathMin(g_boxes[ai].low, low[i]);
      if((newHigh - newLow) > maxRange)
        {
         bool haveMinBars = (g_boxes[ai].endTime - g_boxes[ai].startTime) >=
                             (datetime)((long)(InpMinBoxBars - 1) * PeriodSeconds(PERIOD_CURRENT));
         g_boxes[ai].active = false;
         if(haveMinBars)
           {
            //--- v1.01 FIX (Opus audit, real bug): `close[i] >= box.high`
            //--- alone mislabels a bar whose close lands BETWEEN the old
            //--- box's high and low (wick pushed the range over the cap
            //--- but the close itself is still ambiguous) as "broken
            //--- down" by default, regardless of which side the range
            //--- violation actually came from. Now determined by which
            //--- edge the bar's own wick actually extended past; if both
            //--- extended in the same bar, fall back to close-vs-midpoint.
            bool highExpanded = high[i] > g_boxes[ai].high;
            bool lowExpanded  = low[i]  < g_boxes[ai].low;
            if(highExpanded && !lowExpanded)      g_boxes[ai].brokenUp = true;
            else if(lowExpanded && !highExpanded) g_boxes[ai].brokenUp = false;
            else                                  g_boxes[ai].brokenUp = (close[i] >= (g_boxes[ai].high + g_boxes[ai].low) / 2.0);
            DrawBox(ai, g_boxes[ai].brokenUp ? InpBrokenUpColor : InpBrokenDownColor);
           }
         else
           {
            //--- never met InpMinBoxBars - too short to count as real
            //--- consolidation at all, discard it outright rather than
            //--- leave a "broken" box for a couple of quiet bars.
            ObjectDelete(0, BoxName(ai));
            g_boxes[ai] = g_boxes[ArraySize(g_boxes) - 1];
            ArrayResize(g_boxes, ArraySize(g_boxes) - 1);
           }
         //--- this bar itself may already be the start of the NEXT box -
         //--- re-run the start check against it right away instead of
         //--- waiting a full InpStartWindow bars for the next attempt.
         double hi = high[i], lo = low[i];
         for(int k = 1; k < InpStartWindow && (i - k) >= 0; k++)
           {
            hi = MathMax(hi, high[i - k]);
            lo = MathMin(lo, low[i - k]);
           }
         datetime newStart2 = time[MathMax(0, i - InpStartWindow + 1)];
         if((hi - lo) <= maxRange && !BoxExists(newStart2))
           {
            int zi = ArraySize(g_boxes);
            ArrayResize(g_boxes, zi + 1);
            g_boxes[zi].high      = hi;
            g_boxes[zi].low       = lo;
            g_boxes[zi].startTime = newStart2;
            g_boxes[zi].endTime   = time[i];
            g_boxes[zi].active    = true;
            g_boxes[zi].brokenUp  = false;
            DrawBox(zi, InpActiveColor);
           }
        }
      else
        {
         g_boxes[ai].high    = newHigh;
         g_boxes[ai].low     = newLow;
         g_boxes[ai].endTime = time[i];
         DrawBox(ai, InpActiveColor);
        }
     }
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   int minBars = InpStartWindow + 10;
   if(rates_total < minBars) return(0);

   //--- v1.01 FIX (Opus audit - real bugs, same root causes already
   //--- fixed in MarketStructure_Break.mq5 v1.01, see that file's own
   //--- comment for the full mechanism): g_lastBarTime committed before
   //--- confirming the ATR fetch succeeded; `from` based on a fixed
   //--- window instead of prev_calculated (here this also meant a box
   //--- that broke in one call could get spuriously re-detected/re-
   //--- started by reprocessing the same already-handled bars again in
   //--- a later call); ProcessBars' own loop reading the still-forming
   //--- bar (fixed there, not here - see its own updated bound).
   bool freshAttach = (prev_calculated <= 0);
   if(!freshAttach && rates_total <= prev_calculated) return(rates_total);   // nothing new
   int lookbackBars = (InpScanLookbackDays > 0)
                       ? (int)((long)InpScanLookbackDays * 86400 / PeriodSeconds(PERIOD_CURRENT)) + minBars
                       : rates_total;
   int from;
   if(freshAttach)
     {
      ObjectsDeleteAll(0, g_pfx);
      ArrayResize(g_boxes, 0);
      from = MathMax(InpStartWindow, rates_total - lookbackBars);
     }
   else
      //--- consolidation/breakout logic never looks ahead of the bar
      //--- being processed (unlike the pivot-window indicators), so no
      //--- "-w" reprocessing margin is needed here - prev_calculated-1
      //--- already covers the one bar that might not have been final
      //--- last time.
      from = MathMax(InpStartWindow, prev_calculated - 1);

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   int atrCount = rates_total - from;
   if(CopyBuffer(g_atrHandle, 0, 0, atrCount, atrBuf) < atrCount)
      return(0);   // ATR not ready yet - retry next tick, prev_calculated stays 0

   //--- v1.01 FIX (Opus audit, real bug): this used to wrap the ATR
   //--- values into a SEPARATE rates_total-sized array just so ProcessBars
   //--- could index it by absolute bar number - an O(history) allocation
   //--- on every call (every tick, since this runs even on a self-gated
   //--- no-op call), the same cost-scaling shape as the old TradePanel
   //--- v2.21 freeze on a large chart history. ProcessBars now indexes
   //--- the small, bounded atrFwd array directly as atr[i-from] instead.
   double atrFwd[];
   ArrayResize(atrFwd, atrCount);
   for(int k = 0; k < atrCount; k++) atrFwd[k] = atrBuf[atrCount - 1 - k];

   ProcessBars(from, rates_total, time, high, low, close, atrFwd);
   g_lastBarTime = time[rates_total - 1];
   PruneBoxes(g_lastBarTime);
   return(rates_total);
  }
