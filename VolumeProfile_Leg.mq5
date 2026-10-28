//+------------------------------------------------------------------+
//|                                          VolumeProfile_Leg.mq5    |
//|  Standalone indicator - a volume profile + POC computed ONLY over  |
//|  a single leg that broke market structure, not the whole day.      |
//|  Per direct question/discussion: VolumeProfile_Session.mq5 is a    |
//|  calendar-day composite profile ("where did volume sit all day")   |
//|  - this is a genuinely different question ("where did volume sit   |
//|  DURING THIS MOVE"), so it's a separate indicator, not an option    |
//|  on that one.                                                      |
//|                                                                    |
//|  Reuses the same swing-high/swing-low + Break-of-Structure leg      |
//|  tracking as MarketStructure_Break.mq5/Fib_Golden_Zone.mq5          |
//|  (duplicated rather than shared via #include, matching this         |
//|  project's single-file-per-indicator convention). A leg's own       |
//|  profile is only computed and drawn ONCE, the moment the leg         |
//|  FREEZES (a new opposite swing confirms the impulse is finished) -   |
//|  while a leg is still live/extending there is nothing finished to    |
//|  profile yet, so nothing is drawn for it until then.                 |
//|                                                                    |
//|  Bucket math/drawing (equal-width price buckets, volume split       |
//|  across whichever buckets each bar's [low,high] touches, widest      |
//|  bucket = POC in its own colour) is the same proven method as       |
//|  VolumeProfile_Session.mq5 - anchored just past the LEG's own end     |
//|  time (not the chart's last candle), so each leg's profile sits      |
//|  where that leg actually happened, not all piled up at the current   |
//|  price.                                                              |
//|                                                                    |
//|  Same real_volume caveat as VolumeProfile_Session.mq5: this         |
//|  broker's GOLD/SILVER real_volume is confirmed 0, so tick_volume    |
//|  (trade-count proxy) is the default and only reliable source.       |
//|                                                                    |
//|  STATUS: visual reference only, same as VolumeProfile_Session.mq5 - |
//|  no backtested claim that a leg's POC has predictive value.         |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property link      ""
#property version   "1.01"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== Structure (same convention as MarketStructure_Break.mq5) ==="
input int      InpPivotWindow  = 5;
input double   InpMinMoveATR   = 1.5;

input group "=== Volume profile ==="
input int      InpBuckets         = 20;      // fewer than VolumeProfile_Session.mq5's default - a single
                                              // leg spans far fewer bars than a multi-day window, so a
                                              // finer bucket count would mostly be empty/noisy
input bool     InpUseRealVolume   = false;
input int      InpMaxBarWidthBars = 8;
input double   InpBucketGapFrac   = 0.25;
input color    InpBarColor        = C'40,70,110';
input color    InpPocColor        = C'255,165,0';
input bool     InpShowPocLine     = true;
input int      InpPocLineExtendBars = 20;    // how far the POC line extends right of the leg's own end -
                                              // a short, leg-local line, NOT rayed across the whole chart
                                              // like VolumeProfile_Session.mq5's (this POC is only
                                              // meaningful in the context of that one leg)
input color    InpPocLineColor    = C'130,95,35';

input group "=== General ==="
input int      InpMaxLegs          = 20;     // cap on how many recent legs' profiles stay drawn at once
input int      InpMaxAgeDays        = 14;    // finished legs' profiles older than this are pruned (0 = never)
input int      InpScanLookbackDays = 30;
input int      InpAtrPeriod        = 14;

//+------------------------------------------------------------------+
struct Leg
  {
   int      startIdx;     // bar index (into the array passed to OnCalculate) the leg began at
   int      endIdx;       // bar index the leg froze at - only set once the leg is finished
   datetime startTime;
   datetime endTime;
   bool     finished;      // profile already computed+drawn for this leg
   bool     live;          // still extending - mirrors Fib_Golden_Zone.mq5's own "live" state
   bool     bullish;       // v1.01 FIX (Opus audit, real bug): freezing used to fire on ANY pivot
                            // in either direction with no direction check at all - a bullish leg
                            // froze at its own first swing HIGH instead of waiting for the next
                            // swing LOW like Fib_Golden_Zone.mq5 correctly does. Added so the
                            // freeze check can require the OPPOSITE-direction pivot, same rule.
   double   extreme;       // running extreme while live
  };

Leg      g_legs[];
string   g_pfx = "VPL_";
int      g_atrHandle = INVALID_HANDLE;
datetime g_lastBarTime = 0;

double   g_swingHighPrice = 0.0;
datetime g_swingHighTime  = 0;
int      g_swingHighIdx   = -1;
bool     g_swingHighBroken = true;
double   g_swingLowPrice  = 0.0;
datetime g_swingLowTime   = 0;
int      g_swingLowIdx    = -1;
bool     g_swingLowBroken  = true;

int      g_liveLeg = -1;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpPivotWindow <= 0)
     {
      Print("VolumeProfile_Leg: InpPivotWindow must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   //--- v1.01 FIX (Opus audit): InpBuckets<=0 was never validated -
   //--- DrawLegProfile divides by InpBuckets to get bucket width, and
   //--- indexes vol[0]/ArrayResize(vol, InpBuckets) - a 0 or negative
   //--- value is a divide-by-zero / invalid-array-size crash, not caught
   //--- until a leg actually finishes and tries to draw.
   if(InpBuckets <= 0)
     {
      Print("VolumeProfile_Leg: InpBuckets must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpAtrPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("VolumeProfile_Leg: failed to create ATR handle.");
      return(INIT_FAILED);
     }
   ArrayResize(g_legs, 0);
   g_liveLeg = -1;
   g_lastBarTime = 0;
   g_swingHighPrice = 0.0; g_swingHighTime = 0; g_swingHighIdx = -1; g_swingHighBroken = true;
   g_swingLowPrice  = 0.0; g_swingLowTime  = 0; g_swingLowIdx  = -1; g_swingLowBroken  = true;
   PrintFormat("VolumeProfile_Leg v1.01 OnInit: %s %s  pivotWindow=%d  minMoveATR=%.2f  buckets=%d",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpPivotWindow, InpMinMoveATR, InpBuckets);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_pfx);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
//| Builds and draws the profile for ONE finished leg, over exactly    |
//| its own bars [startIdx, endIdx] - same bucket/POC math as          |
//| VolumeProfile_Session.mq5, anchored past the leg's OWN end time     |
//| rather than the chart's last candle.                               |
//+------------------------------------------------------------------+
void DrawLegProfile(const int legIdx, const double &high[], const double &low[], const double &close[],
                     const long &tick_volume[], const long &volume[], const datetime &time[], const int perSec)
  {
   int s = g_legs[legIdx].startIdx, e = g_legs[legIdx].endIdx;
   if(e < s) return;
   double lo = low[s], hi = high[s];
   for(int i = s; i <= e; i++) { lo = MathMin(lo, low[i]); hi = MathMax(hi, high[i]); }
   if(hi <= lo) return;

   double bw = (hi - lo) / InpBuckets;
   double vol[];
   ArrayResize(vol, InpBuckets);
   ArrayInitialize(vol, 0.0);
   for(int i = s; i <= e; i++)
     {
      double v = InpUseRealVolume ? (double)volume[i] : (double)tick_volume[i];
      if(v <= 0.0) continue;
      int b0 = (int)((low[i] - lo) / bw);
      int b1 = (int)((high[i] - lo) / bw);
      b0 = (int)MathMax(0, MathMin(InpBuckets - 1, b0));
      b1 = (int)MathMax(0, MathMin(InpBuckets - 1, b1));
      if(b1 < b0) { int t = b0; b0 = b1; b1 = t; }
      int span = b1 - b0 + 1;
      double share = v / span;
      for(int b = b0; b <= b1; b++) vol[b] += share;
     }

   int pocBucket = 0;
   double pocVol = vol[0];
   for(int b = 1; b < InpBuckets; b++)
      if(vol[b] > pocVol) { pocVol = vol[b]; pocBucket = b; }
   if(pocVol <= 0.0) return;

   string tag = IntegerToString((long)g_legs[legIdx].endTime);
   datetime anchorTime = g_legs[legIdx].endTime + (datetime)perSec;

   for(int b = 0; b < InpBuckets; b++)
     {
      string nm = g_pfx + "b" + tag + "_" + IntegerToString(b);
      if(vol[b] <= 0.0) { ObjectDelete(0, nm); continue; }
      double gap = bw * InpBucketGapFrac * 0.5;
      double bucketLo = lo + b * bw + gap;
      double bucketHi = bucketLo + bw - 2.0 * gap;
      int widthBars = (int)MathRound(InpMaxBarWidthBars * (vol[b] / pocVol));
      if(widthBars < 1) widthBars = 1;
      datetime t1 = anchorTime;
      datetime t2 = anchorTime + (datetime)(widthBars * perSec);
      bool isPoc = (b == pocBucket);
      if(ObjectFind(0, nm) < 0)
        {
         if(!ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, bucketLo, t2, bucketHi)) continue;
         ObjectSetInteger(0, nm, OBJPROP_FILL, true);
         ObjectSetInteger(0, nm, OBJPROP_BACK, true);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
         ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
        }
      ObjectSetInteger(0, nm, OBJPROP_COLOR, isPoc ? InpPocColor : InpBarColor);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP,
                       (isPoc ? "Leg POC " : "") + "vol=" + DoubleToString(vol[b], 0) +
                       "  [" + DoubleToString(bucketLo, _Digits) + " - " + DoubleToString(bucketHi, _Digits) + "]");
     }

   if(InpShowPocLine)
     {
      string pocNm = g_pfx + "poc_" + tag;
      double pocPrice = lo + (pocBucket + 0.5) * bw;
      datetime lineEnd = anchorTime + (datetime)(InpPocLineExtendBars * perSec);
      if(ObjectFind(0, pocNm) < 0)
        {
         ObjectCreate(0, pocNm, OBJ_TREND, 0, anchorTime, pocPrice, lineEnd, pocPrice);
         ObjectSetInteger(0, pocNm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, pocNm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, pocNm, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, pocNm, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, pocNm, OBJPROP_BACK, true);
         ObjectSetInteger(0, pocNm, OBJPROP_RAY_LEFT, false);
         ObjectSetInteger(0, pocNm, OBJPROP_RAY_RIGHT, false);
        }
      ObjectSetInteger(0, pocNm, OBJPROP_COLOR, InpPocLineColor);
     }
  }

//+------------------------------------------------------------------+
void PruneLegs(const datetime lastBarTime)
  {
   if(InpMaxAgeDays > 0)
     {
      datetime cutoff = lastBarTime - (datetime)((long)InpMaxAgeDays * 86400);
      for(int k = ArraySize(g_legs) - 1; k >= 0; k--)
        {
         if(g_legs[k].finished && g_legs[k].endTime < cutoff)
           {
            string tag = IntegerToString((long)g_legs[k].endTime);
            for(int b = 0; b < InpBuckets; b++) ObjectDelete(0, g_pfx + "b" + tag + "_" + IntegerToString(b));
            ObjectDelete(0, g_pfx + "poc_" + tag);
            g_legs[k] = g_legs[ArraySize(g_legs) - 1];
            ArrayResize(g_legs, ArraySize(g_legs) - 1);
            if(g_liveLeg == k) g_liveLeg = -1;
            else if(g_liveLeg == ArraySize(g_legs)) g_liveLeg = k;
           }
        }
     }
   while(ArraySize(g_legs) > InpMaxLegs)
     {
      int oldest = -1;
      for(int k = 0; k < ArraySize(g_legs); k++)
         if(g_legs[k].finished && (oldest < 0 || g_legs[k].endTime < g_legs[oldest].endTime)) oldest = k;
      if(oldest < 0) break;
      string tag = IntegerToString((long)g_legs[oldest].endTime);
      for(int b = 0; b < InpBuckets; b++) ObjectDelete(0, g_pfx + "b" + tag + "_" + IntegerToString(b));
      ObjectDelete(0, g_pfx + "poc_" + tag);
      g_legs[oldest] = g_legs[ArraySize(g_legs) - 1];
      ArrayResize(g_legs, ArraySize(g_legs) - 1);
      if(g_liveLeg == oldest) g_liveLeg = -1;
      else if(g_liveLeg == ArraySize(g_legs)) g_liveLeg = oldest;
     }
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
   //--- comment for the full mechanism): g_lastBarTime committed before
   //--- confirming the ATR fetch succeeded; `from` based on a fixed
   //--- window instead of prev_calculated; the pivot loop reading the
   //--- still-forming bar.
   bool freshAttach = (prev_calculated <= 0);
   if(!freshAttach && rates_total <= prev_calculated) return(rates_total);   // nothing new
   int lookbackBars = (InpScanLookbackDays > 0)
                       ? (int)((long)InpScanLookbackDays * 86400 / PeriodSeconds(PERIOD_CURRENT)) + minBars
                       : rates_total;
   int from = freshAttach ? MathMax(w, rates_total - lookbackBars) : MathMax(w, prev_calculated - 1 - w);
   if(freshAttach)
     {
      ObjectsDeleteAll(0, g_pfx);
      ArrayResize(g_legs, 0);
      g_liveLeg = -1;
      g_swingHighPrice = 0.0; g_swingHighTime = 0; g_swingHighIdx = -1; g_swingHighBroken = true;
      g_swingLowPrice  = 0.0; g_swingLowTime  = 0; g_swingLowIdx  = -1; g_swingLowBroken  = true;
     }

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   int atrCount = rates_total - from;
   if(CopyBuffer(g_atrHandle, 0, 0, atrCount, atrBuf) < atrCount)
      return(0);

   int perSec = PeriodSeconds(PERIOD_CURRENT);

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

      //--- v1.01 FIX (Opus audit, real bug): used to freeze the live leg
      //--- on ANY pivot in either direction - a bullish leg could freeze
      //--- at its OWN first swing high instead of waiting for the next
      //--- swing LOW (the actual sign the impulse is over). Now checks
      //--- the leg's own direction, same rule Fib_Golden_Zone.mq5 uses.
      if(g_liveLeg >= 0 && g_legs[g_liveLeg].live &&
         ((g_legs[g_liveLeg].bullish && isTrough) || (!g_legs[g_liveLeg].bullish && isPeak)))
        {
         g_legs[g_liveLeg].live     = false;
         g_legs[g_liveLeg].finished = true;
         g_legs[g_liveLeg].endIdx   = i - 1;
         DrawLegProfile(g_liveLeg, high, low, close, tick_volume, volume, time, perSec);
         g_liveLeg = -1;
        }

      if(isPeak && (g_swingHighTime == 0 || MathAbs(high[i] - g_swingHighPrice) >= minMove))
        {
         g_swingHighPrice  = high[i];
         g_swingHighTime   = time[i];
         g_swingHighIdx    = i;
         g_swingHighBroken = false;
        }
      if(isTrough && (g_swingLowTime == 0 || MathAbs(low[i] - g_swingLowPrice) >= minMove))
        {
         g_swingLowPrice  = low[i];
         g_swingLowTime   = time[i];
         g_swingLowIdx    = i;
         g_swingLowBroken = false;
        }

      //--- v1.01 FIX (Opus audit - real bug, same mechanism as
      //--- Fib_Golden_Zone.mq5's own v1.01 fix): these index comparisons
      //--- used to require the tracked opposite swing to be OLDER
      //--- (smaller index) than the swing being broken - backwards, for
      //--- the same reason explained in that file's own comment. Flipped
      //--- to require it be the MORE RECENT of the two.
      if(g_liveLeg < 0)
        {
         if(!g_swingHighBroken && g_swingHighTime != 0 && close[i] > g_swingHighPrice &&
            g_swingLowIdx >= 0 && g_swingLowIdx > g_swingHighIdx)
           {
            g_swingHighBroken = true;
            int zi = ArraySize(g_legs);
            ArrayResize(g_legs, zi + 1);
            g_legs[zi].startIdx = g_swingLowIdx;
            g_legs[zi].endIdx   = -1;
            g_legs[zi].startTime = g_swingLowTime;
            g_legs[zi].endTime   = time[i];
            g_legs[zi].finished  = false;
            g_legs[zi].live      = true;
            g_legs[zi].bullish   = true;
            g_legs[zi].extreme   = high[i];
            g_liveLeg = zi;
           }
         else if(!g_swingLowBroken && g_swingLowTime != 0 && close[i] < g_swingLowPrice &&
                 g_swingHighIdx >= 0 && g_swingHighIdx > g_swingLowIdx)
           {
            g_swingLowBroken = true;
            int zi = ArraySize(g_legs);
            ArrayResize(g_legs, zi + 1);
            g_legs[zi].startIdx = g_swingHighIdx;
            g_legs[zi].endIdx   = -1;
            g_legs[zi].startTime = g_swingHighTime;
            g_legs[zi].endTime   = time[i];
            g_legs[zi].finished  = false;
            g_legs[zi].live      = true;
            g_legs[zi].bullish   = false;
            g_legs[zi].extreme   = low[i];
            g_liveLeg = zi;
           }
        }
      else
        {
         g_legs[g_liveLeg].endTime = time[i];   // keep the still-live leg's own end time current
        }
     }

   g_lastBarTime = time[rates_total - 1];
   PruneLegs(g_lastBarTime);
   return(rates_total);
  }
