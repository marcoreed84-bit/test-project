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
#property version   "1.00"
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
   PrintFormat("Consolidation_Zones v1.00 OnInit: %s %s  startWindow=%d  rangeATRMax=%.2f  scanLookback=%dd",
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
void ProcessBars(const int from, const int n, const datetime &time[], const double &high[],
                  const double &low[], const double &close[], const double &atrAligned[])
  {
   for(int i = MathMax(from, InpStartWindow); i < n; i++)
     {
      double atrHere = atrAligned[i];
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
         if((hi - lo) <= maxRange)
           {
            int zi = ArraySize(g_boxes);
            ArrayResize(g_boxes, zi + 1);
            g_boxes[zi].high      = hi;
            g_boxes[zi].low       = lo;
            g_boxes[zi].startTime = time[i - InpStartWindow + 1];
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
            g_boxes[ai].brokenUp = (close[i] >= g_boxes[ai].high);
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
         if((hi - lo) <= maxRange)
           {
            int zi = ArraySize(g_boxes);
            ArrayResize(g_boxes, zi + 1);
            g_boxes[zi].high      = hi;
            g_boxes[zi].low       = lo;
            g_boxes[zi].startTime = time[MathMax(0, i - InpStartWindow + 1)];
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

   datetime t0 = time[rates_total - 1];
   if(t0 == g_lastBarTime) return(rates_total);   // once per new CLOSED bar only - see MarketStructure_Break's own comment on why
   bool freshAttach = (prev_calculated <= 0);
   g_lastBarTime = t0;

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
      from = MathMax(InpStartWindow, rates_total - 3);

   if(from >= rates_total) return(rates_total);

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   int atrCount = rates_total - from;
   if(CopyBuffer(g_atrHandle, 0, 0, atrCount, atrBuf) < atrCount)
      return(0);   // ATR not ready yet - retry next tick, prev_calculated stays 0

   double atrAligned[];
   ArrayResize(atrAligned, rates_total);
   for(int k = 0; k < atrCount; k++) atrAligned[from + k] = atrBuf[atrCount - 1 - k];

   ProcessBars(from, rates_total, time, high, low, close, atrAligned);
   PruneBoxes(t0);
   return(rates_total);
  }
