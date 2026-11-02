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
#property version   "1.06"
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
input int    InpMaxBarWidthBars  = 10;      // v1.03: shrunk from 18 - per direct request, bars were
                                             // still reaching past the chart's right-margin space and
                                             // getting cut off behind the price column. The busiest
                                             // bucket's rectangle extends this many bars rightward from
                                             // the last candle; every other bucket scales proportionally
                                             // to its own volume share of that max.
input bool   InpAutoRightMargin  = true;    // v1.03: the real fix for the cut-off problem - MT5 clips
                                             // any object past the chart's own right-margin ("shift")
                                             // space, which is a SEPARATE setting from anything this
                                             // indicator draws. When true, claims enough right-margin
                                             // room for InpMaxBarWidthBars automatically (only ever
                                             // INCREASES it, never shrinks a larger margin you already
                                             // have set). Turn off if you'd rather control Chart
                                             // Properties -> right margin yourself.
input double InpBucketGapFrac    = 0.25;    // v1.02: each bucket's rectangle only fills this fraction
                                             // of its own vertical slot (centered), leaving a thin gap
                                             // above/below - breaks the solid-wall look into a readable
                                             // comb of bars. 0 = no gap (old look), try 0.15-0.35
input color  InpBarColor         = C'10,80,140';     // v1.05: dim neon blue (same family colour as
                                             // InpThemeBullCol in TradePanel_EA.mq5) instead of the old
                                             // desaturated navy - blends with the blue/white candle theme.
input color  InpPocColor         = clrWhite;         // v1.05: bright white (the theme's accent colour) -
                                             // the single most important level reads as the brightest
                                             // thing on the profile.
input bool   InpShowPocLine      = true;    // a line at the POC price, extended across the chart so you
                                             // can see the level against price history and how price
                                             // reacted there, not just where it sits now
input bool   InpPocLineRayLeft   = true;    // v1.03: per direct request - extend the POC line ALL the
                                             // way across the visible chart to the left (MT5's own
                                             // OBJPROP_RAY_LEFT, genuinely infinite, not just N bars
                                             // back) instead of stopping InpPocLineBackBars bars behind
                                             // the last candle. false = use InpPocLineBackBars instead.
input int    InpPocLineBackBars  = 150;     // only used when InpPocLineRayLeft is false
input color  InpPocLineColor     = C'0,150,255';   // v1.05: exact neon blue (InpThemeBullCol) instead of
                                             // the old dim brown - matches the theme family.

input group "=== Value Area (POC +/- the price range holding InpVAPercent of the window's volume) ==="
input bool   InpShowValueArea    = true;
input double InpVAPercent        = 70.0;    // standard volume-profile convention
input color  InpVahValColor      = C'120,200,255';  // light neon blue/cyan - distinct from both the
                                             // bright-white POC and the dim-blue bars, same family.

#define VP_PFX "VPS_"

//+------------------------------------------------------------------+
//| v1.03: claims enough right-margin ("shift") chart space for the    |
//| profile to actually fit without MT5 clipping it behind the price   |
//| column - the real fix for "extend far into the right past the     |
//| price column, and get cut off". CHART_SHIFT_SIZE is a PERCENTAGE   |
//| of the chart's own width, independent of anything this indicator   |
//| draws in bars, so there's no exact bar->percent conversion - uses  |
//| a generous fixed value instead and only ever INCREASES the margin, |
//| never shrinks one you already had set bigger for your own reasons. |
//+------------------------------------------------------------------+
void EnsureRightMargin()
  {
   if(!InpAutoRightMargin) return;
   if(!(bool)ChartGetInteger(0, CHART_SHIFT))
      ChartSetInteger(0, CHART_SHIFT, true);
   //--- v1.04 FIX (real compile error, caught by the actual MT5 compiler -
   //--- this environment has none, so this slipped through): CHART_SHIFT_SIZE
   //--- is a DOUBLE property (a percentage, e.g. 25.0), not an integer one -
   //--- ChartGetInteger/ChartSetInteger don't have a matching overload for
   //--- it ("wrong parameters count" / "cannot convert enum"). CHART_SHIFT
   //--- itself (the bool just above) genuinely is an integer property, so
   //--- that half was always correct.
   double cur = ChartGetDouble(0, CHART_SHIFT_SIZE);
   double want = 25.0;   // percent - comfortably fits InpMaxBarWidthBars at typical zoom levels
   if(cur < want)
      ChartSetDouble(0, CHART_SHIFT_SIZE, want);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   //--- v1.06 FIX (Opus audit, real crash paths): neither InpBuckets nor
   //--- InpDaysToShow was ever validated. InpBuckets<=0 divides by zero at
   //--- bw=(hi-lo)/InpBuckets and ArrayResize(vol,0) then reads vol[0] out
   //--- of range. InpDaysToShow<=0 puts cutoff AFTER the last bar, so the
   //--- very first loop iteration sets start=rates_total and low[start]
   //--- reads out of range. VolumeProfile_Leg.mq5 already guards its own
   //--- InpBuckets input (v1.01) - Session never got the equivalent check.
   if(InpBuckets <= 0 || InpDaysToShow <= 0)
     {
      Print("VolumeProfile_Session: InpBuckets and InpDaysToShow must both be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   IndicatorSetString(INDICATOR_SHORTNAME, "Session Volume Profile v1.06 (" + IntegerToString(InpDaysToShow) + "d)");
   EnsureRightMargin();
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
   EnsureRightMargin();   // cheap (SetIfDiff-style guard inside) - re-asserted here in case another
                          // EA/indicator on the same chart changed CHART_SHIFT_SIZE back since OnInit
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
   //--- v1.06 FIX (Opus audit, low priority): these two early returns used
   //--- to leave whatever profile was already drawn sitting on screen with
   //--- no indication it's stale (e.g. InpUseRealVolume=true on a symbol
   //--- whose real_volume is 0, confirmed 0 on GOLD/SILVER this project).
   if(hi <= lo) { ObjectsDeleteAll(0, VP_PFX); ChartRedraw(0); return(rates_total); }

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
   if(pocVol <= 0.0) { ObjectsDeleteAll(0, VP_PFX); ChartRedraw(0); return(rates_total); }

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
      //--- v1.03: per direct request - InpPocLineRayLeft uses MT5's own
      //--- OBJPROP_RAY_LEFT to extend the line genuinely infinitely across
      //--- the whole visible (and scrollable-back-into) chart history,
      //--- rather than stopping InpPocLineBackBars bars behind the last
      //--- candle - "so I can see on the chart the levels and how price
      //--- reacted" needs the line to reach back over whatever history
      //--- you scroll to, not a fixed recent window.
      datetime lineStart = InpPocLineRayLeft ? anchorTime : time[(int)MathMax(0, end - InpPocLineBackBars)];
      datetime lineEnd   = anchorTime + (datetime)(InpMaxBarWidthBars * perSec);
      if(ObjectFind(0, pocNm) < 0)
        {
         ObjectCreate(0, pocNm, OBJ_TREND, 0, lineStart, pocPrice, lineEnd, pocPrice);
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
      ObjectSetInteger(0, pocNm, OBJPROP_RAY_LEFT, InpPocLineRayLeft);
      ObjectSetInteger(0, pocNm, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, pocNm, OBJPROP_COLOR, InpPocLineColor);
     }
   else
      ObjectDelete(0, VP_PFX + "pocline");

   //--- v1.05: Value Area High/Low - expand outward from the POC bucket,
   //--- each step adding whichever still-unclaimed neighbour (left or
   //--- right) carries MORE volume, until the accumulated share reaches
   //--- InpVAPercent of the window's total volume. Same anchor/ray
   //--- behaviour as the POC line (InpPocLineRayLeft/InpPocLineBackBars)
   //--- so they read as one consistent family of levels.
   if(InpShowValueArea)
     {
      double totalVol = 0.0;
      for(int b = 0; b < InpBuckets; b++) totalVol += vol[b];
      double target = totalVol * (InpVAPercent / 100.0);
      int vaLo = pocBucket, vaHi = pocBucket;
      double included = vol[pocBucket];
      while(included < target && (vaLo > 0 || vaHi < InpBuckets - 1))
        {
         double leftVol  = (vaLo > 0) ? vol[vaLo - 1] : -1.0;
         double rightVol = (vaHi < InpBuckets - 1) ? vol[vaHi + 1] : -1.0;
         if(rightVol >= leftVol) { vaHi++; included += vol[vaHi]; }
         else                    { vaLo--; included += vol[vaLo]; }
        }
      double vahPrice = lo + (vaHi + 1) * bw;
      double valPrice = lo + vaLo * bw;
      datetime vaLineStart = InpPocLineRayLeft ? anchorTime : time[(int)MathMax(0, end - InpPocLineBackBars)];
      datetime vaLineEnd   = anchorTime + (datetime)(InpMaxBarWidthBars * perSec);

      string vahNm = VP_PFX + "vah";
      if(ObjectFind(0, vahNm) < 0)
        {
         ObjectCreate(0, vahNm, OBJ_TREND, 0, vaLineStart, vahPrice, vaLineEnd, vahPrice);
         ObjectSetInteger(0, vahNm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, vahNm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, vahNm, OBJPROP_STYLE, STYLE_DASH);
         ObjectSetInteger(0, vahNm, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, vahNm, OBJPROP_BACK, true);
        }
      else
        {
         ObjectSetInteger(0, vahNm, OBJPROP_TIME, 0, vaLineStart);
         ObjectSetDouble (0, vahNm, OBJPROP_PRICE, 0, vahPrice);
         ObjectSetInteger(0, vahNm, OBJPROP_TIME, 1, vaLineEnd);
         ObjectSetDouble (0, vahNm, OBJPROP_PRICE, 1, vahPrice);
        }
      ObjectSetInteger(0, vahNm, OBJPROP_RAY_LEFT, InpPocLineRayLeft);
      ObjectSetInteger(0, vahNm, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, vahNm, OBJPROP_COLOR, InpVahValColor);

      string valNm = VP_PFX + "val";
      if(ObjectFind(0, valNm) < 0)
        {
         ObjectCreate(0, valNm, OBJ_TREND, 0, vaLineStart, valPrice, vaLineEnd, valPrice);
         ObjectSetInteger(0, valNm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, valNm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, valNm, OBJPROP_STYLE, STYLE_DASH);
         ObjectSetInteger(0, valNm, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, valNm, OBJPROP_BACK, true);
        }
      else
        {
         ObjectSetInteger(0, valNm, OBJPROP_TIME, 0, vaLineStart);
         ObjectSetDouble (0, valNm, OBJPROP_PRICE, 0, valPrice);
         ObjectSetInteger(0, valNm, OBJPROP_TIME, 1, vaLineEnd);
         ObjectSetDouble (0, valNm, OBJPROP_PRICE, 1, valPrice);
        }
      ObjectSetInteger(0, valNm, OBJPROP_RAY_LEFT, InpPocLineRayLeft);
      ObjectSetInteger(0, valNm, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, valNm, OBJPROP_COLOR, InpVahValColor);
     }
   else
     {
      ObjectDelete(0, VP_PFX + "vah");
      ObjectDelete(0, VP_PFX + "val");
     }

   ChartRedraw(0);
   return(rates_total);
  }
