//+------------------------------------------------------------------+
//|                                   VolumeProfile_Session.mq5      |
//|  Session (daily) volume profile - per direct request, as its own |
//|  standalone indicator. Aggregates the last InpDaysToShow calendar  |
//|  days (same day boundary as this project's VWAP_Bands_Metals/     |
//|  Crypto.mq5 daily VWAP) into ONE profile, drawn entirely in the    |
//|  BLANK SPACE to the right of the most recent candle - per direct   |
//|  request/screenshot, it must sit there, not overlap any candles.   |
//|  Anchored at (last bar time + 1 bar), extending further right as   |
//|  chart's own empty future space - scroll/zoom moves it exactly     |
//|  like any other chart object anchored by time, same as everything  |
//|  else in this project's indicators.                                |
//|                                                                   |
//|  Buckets: that InpDaysToShow window's own [low, high] range split  |
//|  into InpBuckets equal-width price buckets; each bar's volume is   |
//|  split evenly across the buckets its own [low, high] touches (same |
//|  distribution method already used and tested in this project's    |
//|  volume_profile_poc_test.py research script). One horizontal      |
//|  OBJ_RECTANGLE per non-empty bucket, width proportional to that    |
//|  bucket's volume share of the single busiest bucket (POC - Point   |
//|  of Control), which is drawn in its own distinct color. An         |
//|  optional dotted line extends the POC price back across the        |
//|  visible chart (InpShowPocLine) so it is easy to read against the  |
//|  actual candles despite the profile itself sitting off to the side.|
//|                                                                   |
//|  CAVEAT (same as every other volume-based construction in this   |
//|  project - see CLAUDE.md and volume_profile_poc_test.py's own     |
//|  header): this broker's GOLD/SILVER real_volume is confirmed 0,   |
//|  so tick_volume (a trade-COUNT proxy, not real traded volume) is   |
//|  the only usable source - a materially weaker signal of where real |
//|  volume actually sat than a real exchange instrument's own volume   |
//|  profile would be. InpUseRealVolume exists in case that ever        |
//|  changes on a different symbol/broker, defaults OFF.                 |
//|                                                                   |
//|  STATUS: visual reference only. "Prior-day volume-profile POC      |
//|  touch-reject" was tested as a TradePanel signal (2026-10-26, GOLD |
//|  M5, real TP/SL, walk-forward split, random-timing null) and        |
//|  FAILED: OOS PF 0.969, net -379.9, p(PF)=0.52, p(net)=0.58 -         |
//|  indistinguishable from random entry timing. NOT implemented as a    |
//|  signal here or anywhere - this indicator draws the profile for      |
//|  discretionary/visual judgement only, it does not claim the levels    |
//|  it shows have any backtested predictive edge.                        |
//+------------------------------------------------------------------+
#property copyright "test-project"
#property version   "1.02"
#property indicator_chart_window
#property indicator_plots 0

input group "=== Volume profile settings ==="
input int    InpDaysToShow       = 3;       // how many of the most recent calendar days feed the
                                             // ONE profile shown (same day boundary as the daily VWAP)
input int    InpBuckets          = 30;      // price buckets - more buckets = finer resolution,
                                             // noisier-looking histogram
input bool   InpUseRealVolume    = false;   // GOLD/SILVER real_volume is 0 on this broker's feed
                                             // (confirmed this project) - leave off unless you have
                                             // verified your own symbol/broker actually populates it
input int    InpMaxBarWidthBars  = 18;      // v1.02: shrunk from 50 - per direct request, the busiest
                                             // bucket was stretching almost to the chart's right edge,
                                             // reading as one solid wall rather than a profile. The
                                             // busiest bucket's rectangle extends this many bars
                                             // rightward from the last candle; every other bucket
                                             // scales proportionally to its own volume share of that max
input double InpBucketGapFrac    = 0.25;    // v1.02: each bucket's rectangle only fills this fraction
                                             // of its own vertical slot (centered), leaving a thin gap
                                             // above/below - breaks the solid-wall look into a readable
                                             // comb of bars. 0 = no gap (old look), try 0.15-0.35
input color  InpBarColor         = C'40,70,110';     // ordinary bucket fill
input color  InpPocColor         = C'255,165,0';     // Point-of-Control (busiest bucket) fill - distinct
input bool   InpShowPocLine      = true;    // a thin dotted line at the POC price, extended back across
                                             // the VISIBLE candles too - easier to read against price
                                             // action despite the profile itself sitting off to the side
input int    InpPocLineBackBars  = 150;     // how many bars back (left, over the candles) the POC line extends
input color  InpPocLineColor     = C'255,165,0';

#define VP_PFX "VPS_"

//+------------------------------------------------------------------+
int OnInit()
  {
   IndicatorSetString(INDICATOR_SHORTNAME, "Session Volume Profile (" + IntegerToString(InpDaysToShow) + "d)");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, VP_PFX);
  }

//+------------------------------------------------------------------+
//| Full recompute every call - cheap (InpDaysToShow+1 days of bars    |
//| only, same bounded-window convention as VWAP_Bands_Metals/Crypto). |
//| Draws ONE aggregate profile, anchored just past the last candle,   |
//| extending rightward into the chart's own blank/empty space - never |
//| over any candle, per direct request.                               |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(rates_total < 2) return(0);
   int perSec = PeriodSeconds(PERIOD_CURRENT);
   if(perSec <= 0) return(rates_total);

   datetime lastDay = time[rates_total - 1] - (time[rates_total - 1] % 86400);
   datetime cutoff  = lastDay - (datetime)((long)(InpDaysToShow - 1) * 86400);

   int start = 0;
   for(int i = rates_total - 1; i >= 0; i--)
      if(time[i] < cutoff) { start = i + 1; break; }
   int end = rates_total - 1;

   double lo = low[start], hi = high[start];
   for(int i = start; i <= end; i++)
     {
      lo = MathMin(lo, low[i]);
      hi = MathMax(hi, high[i]);
     }
   if(hi <= lo) { ChartRedraw(0); return(rates_total); }

   double bw = (hi - lo) / InpBuckets;
   double vol[];
   ArrayResize(vol, InpBuckets);
   ArrayInitialize(vol, 0.0);

   for(int i = start; i <= end; i++)
     {
      double v = InpUseRealVolume ? (double)volume[i] : (double)tick_volume[i];
      if(v <= 0.0) continue;
      int b0 = (int)((low[i]  - lo) / bw);
      int b1 = (int)((high[i] - lo) / bw);
      b0 = (int)MathMax(0, MathMin(InpBuckets - 1, b0));
      b1 = (int)MathMax(0, MathMin(InpBuckets - 1, b1));
      if(b1 < b0) { int t = b0; b0 = b1; b1 = t; }
      int span = b1 - b0 + 1;
      double share = v / span;
      for(int b = b0; b <= b1; b++)
         vol[b] += share;
     }

   int pocBucket = 0;
   double pocVol = vol[0];
   for(int b = 1; b < InpBuckets; b++)
      if(vol[b] > pocVol) { pocVol = vol[b]; pocBucket = b; }
   if(pocVol <= 0.0) { ChartRedraw(0); return(rates_total); }

   //--- anchor the WHOLE profile one bar past the last candle, into the
   //--- chart's own empty future space - this is the only time coordinate
   //--- every bucket rectangle uses, so nothing here ever sits on top of
   //--- a real candle.
   datetime anchorTime = time[end] + (datetime)perSec;

   for(int b = 0; b < InpBuckets; b++)
     {
      string nm = VP_PFX + "bucket_" + IntegerToString(b);
      if(vol[b] <= 0.0)
        {
         ObjectDelete(0, nm);
         continue;
        }
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
      else
        {
         ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t1);
         ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, bucketLo);
         ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t2);
         ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, bucketHi);
        }
      ObjectSetInteger(0, nm, OBJPROP_COLOR, isPoc ? InpPocColor : InpBarColor);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP,
                       (isPoc ? "POC " : "") + "vol=" + DoubleToString(vol[b], 0) +
                       "  [" + DoubleToString(bucketLo, _Digits) + " - " + DoubleToString(bucketHi, _Digits) + "]");
     }
   //--- clean up any leftover buckets from a previous call with more buckets than now
   for(int b = InpBuckets; b < 200; b++)
     {
      string nm = VP_PFX + "bucket_" + IntegerToString(b);
      if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
      else break;
     }

   if(InpShowPocLine)
     {
      string pocNm = VP_PFX + "pocline";
      double pocPrice = lo + (pocBucket + 0.5) * bw;
      //--- extends from InpPocLineBackBars bars BEHIND the last candle (so it
      //--- reads against recent price action) through to the right edge of
      //--- the profile itself - covers both the candles and the profile in
      //--- one continuous line.
      int backIdx = (int)MathMax(0, end - InpPocLineBackBars);
      datetime lineStart = time[backIdx];
      datetime lineEnd   = anchorTime + (datetime)(InpMaxBarWidthBars * perSec);
      if(ObjectFind(0, pocNm) < 0)
        {
         ObjectCreate(0, pocNm, OBJ_TREND, 0, lineStart, pocPrice, lineEnd, pocPrice);
         ObjectSetInteger(0, pocNm, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, pocNm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, pocNm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, pocNm, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, pocNm, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, pocNm, OBJPROP_BACK, true);
        }
      else
        {
         ObjectSetInteger(0, pocNm, OBJPROP_TIME, 0, lineStart);
         ObjectSetDouble (0, pocNm, OBJPROP_PRICE, 0, pocPrice);
         ObjectSetInteger(0, pocNm, OBJPROP_TIME, 1, lineEnd);
         ObjectSetDouble (0, pocNm, OBJPROP_PRICE, 1, pocPrice);
        }
      ObjectSetInteger(0, pocNm, OBJPROP_COLOR, InpPocLineColor);
     }
   else
      ObjectDelete(0, VP_PFX + "pocline");

   ChartRedraw(0);
   return(rates_total);
  }
