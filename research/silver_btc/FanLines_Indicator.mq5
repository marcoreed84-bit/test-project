//+------------------------------------------------------------------+
//|                                              FanLines_Indicator.mq5 |
//| Chart port of research/silver_btc/fan_line_search.py's construction |
//| (this session's closest-to-real backtest result: Gold p(K=1)=0.026, |
//| still failed the honest multi-config correction - see              |
//| fan_line_output.txt - so treat this as a DISCRETIONARY chart aid,   |
//| not a proven signal generator).                                     |
//|                                                                      |
//| WHAT IT DOES                                                        |
//| - Detects every confirmed N-bar fractal swing high/low (InpPivotK   |
//|   bars strictly higher/lower on each side - same rule as the        |
//|   Python backtest's common.pivots()) and marks each one with a      |
//|   small arrow, if InpMarkSwings is true.                            |
//| - From the most recent swing LOW, draws a line to EVERY later swing |
//|   HIGH since that low (an "up-fan") - the anchor resets to a fresh  |
//|   point whenever an even lower swing low confirms. Mirror: from the |
//|   most recent swing HIGH, a line to every later swing LOW           |
//|   ("down-fan").                                                     |
//| - The line nearest to current price (the steepest one still above/  |
//|   below price) is highlighted in InpOuterLineColor - that's the one |
//|   "in play" right now, closest to being tested/broken.              |
//| - Once price closes through a line, that line is DROPPED and not    |
//|   redrawn - it becomes irrelevant once broken, matching exactly     |
//|   what the backtest did (a broken line is popped and never reused). |
//|   So yes: redundant/broken lines are removed automatically, every   |
//|   bar, not just left cluttering the chart.                          |
//|                                                                      |
//| TIMEFRAME: fully interchangeable. InpPivotK is a bar count, not a    |
//| time span, so attaching this to any chart just re-detects swings on |
//| THAT timeframe's own bars - a "10-bar swing" naturally means more   |
//| wall-clock time on H1 than on M15. No parameter needs to change     |
//| when you switch timeframes (though you may want a smaller InpPivotK |
//| on a higher timeframe if you want swings to confirm faster).        |
//|                                                                      |
//| OPTIONAL FILTERS (off by default - InpMarkSwings/all fan lines show |
//| by default): InpMinGapATR/InpMaxGapATR hide a line-pair whose gap   |
//| is too small/large relative to ATR to be a sane target (the         |
//| backtest found gaps from stale, years-old anchors could reach       |
//| 100s of ATR and were meaningless - MAX defaults to 0 = no cap here, |
//| since this is a visual aid, not a live filter; set it if the chart  |
//| gets cluttered with absurd lines). InpMinSlopeATR only highlights   |
//| the outer line if it's actually "steep" (the user's own "healthy   |
//| trend vs. too steep" refinement) - note the backtest found this     |
//| filter did NOT improve results on any instrument, so it's off by    |
//| default here too; it's a display aid, not a validated edge.         |
//+------------------------------------------------------------------+
#property copyright "research/silver_btc/fan_line_search.py"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   0

input int    InpPivotK         = 10;    // swing size, bars each side (same axis as PIVOT_K in the backtest)
input int    InpAtrPeriod      = 14;    // ATR period for the optional gap/steepness filters
input double InpMinGapATR      = 0.0;   // hide a line-pair whose gap is < this many ATR (0 = show all)
input double InpMaxGapATR      = 0.0;   // hide a line-pair whose gap is > this many ATR (0 = no cap)
input double InpMinSlopeATR    = 0.0;   // only highlight the outer line if slope/bar >= this many ATR (0 = no filter)
input int    InpMaxBarsBack    = 5000;  // how far back to detect swings / build fans
input bool   InpMarkSwings     = true;  // draw small arrows at every confirmed swing high/low
input color  InpUpFanColor     = clrDeepSkyBlue;
input color  InpDownFanColor   = clrOrangeRed;
input color  InpOuterLineColor = clrYellow;   // the line nearest price right now - "in play"
input color  InpSwingHighColor = clrRed;
input color  InpSwingLowColor  = clrLime;

#define PFX  "FanLn_"
#define PFXP "FanPv_"

double    g_dummy[];
int       g_atrHandle = INVALID_HANDLE;
datetime  g_lastBarTime = 0;

struct FanLine
  {
   datetime anchor_time;
   double   anchor_price;
   datetime pivot_time;
   double   pivot_price;
   double   slope;   // price per second - timeframe-agnostic storage
  };

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, g_dummy, INDICATOR_CALCULATIONS);
   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpAtrPeriod);
   return(g_atrHandle == INVALID_HANDLE ? INIT_FAILED : INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, PFX);
   ObjectsDeleteAll(0, PFXP);
   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
void SortFanDesc(FanLine &lines[], int count, bool byLargestSlope)
  {
   for(int x = 0; x < count - 1; x++)
      for(int y = x + 1; y < count; y++)
        {
         bool swap = byLargestSlope ? (lines[y].slope > lines[x].slope) : (lines[y].slope < lines[x].slope);
         if(swap)
           {
            FanLine t = lines[x]; lines[x] = lines[y]; lines[y] = t;
           }
        }
  }

//+------------------------------------------------------------------+
void DrawFan(FanLine &lines[], int count, string tag, color col, bool byLargestSlope,
             double lastAtr, datetime nowTime)
  {
   if(count == 0)
      return;
   SortFanDesc(lines, count, byLargestSlope);

   for(int k = 0; k < count; k++)
     {
      if(k + 1 < count && lastAtr > 0)
        {
         double vHere = lines[k].anchor_price   + lines[k].slope   * (double)(nowTime - lines[k].anchor_time);
         double vNext = lines[k + 1].anchor_price + lines[k + 1].slope * (double)(nowTime - lines[k + 1].anchor_time);
         double gap = MathAbs(vHere - vNext);
         if(InpMinGapATR > 0 && gap < InpMinGapATR * lastAtr)
            continue;
         if(InpMaxGapATR > 0 && gap > InpMaxGapATR * lastAtr)
            continue;
        }
      bool isOuter = (k == 0);
      if(isOuter && InpMinSlopeATR > 0 && lastAtr > 0)
        {
         double slopePerBar = MathAbs(lines[k].slope) * (double)PeriodSeconds();
         if(slopePerBar / lastAtr < InpMinSlopeATR)
            isOuter = false;   // still drawn, just not highlighted as "in play"
        }

      string name = PFX + tag + "_" + IntegerToString((long)lines[k].pivot_time);
      if(ObjectFind(0, name) >= 0)
         ObjectDelete(0, name);
      ObjectCreate(0, name, OBJ_TREND, 0, lines[k].anchor_time, lines[k].anchor_price,
                   lines[k].pivot_time, lines[k].pivot_price);
      ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);
      ObjectSetInteger(0, name, OBJPROP_COLOR, (isOuter ? InpOuterLineColor : col));
      ObjectSetInteger(0, name, OBJPROP_WIDTH, (isOuter ? 2 : 1));
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
     }
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(rates_total < 2 * InpPivotK + 5)
      return(rates_total);

   bool isNewBar = (time[rates_total - 1] != g_lastBarTime);
   if(!isNewBar && prev_calculated > 0)
      return(rates_total);
   g_lastBarTime = time[rates_total - 1];

   double atrBuf[];
   ArraySetAsSeries(atrBuf, false);
   if(CopyBuffer(g_atrHandle, 0, 0, rates_total, atrBuf) <= 0)
      return(rates_total);

   ObjectsDeleteAll(0, PFX);
   ObjectsDeleteAll(0, PFXP);

   int start = MathMax(InpPivotK, rates_total - InpMaxBarsBack);
   int end   = rates_total - InpPivotK - 1;
   if(end <= start)
      return(rates_total);

   bool isHigh[], isLow[];
   ArrayResize(isHigh, rates_total);
   ArrayResize(isLow,  rates_total);
   for(int z = 0; z < rates_total; z++)
     {
      isHigh[z] = false;
      isLow[z]  = false;
     }

   //--- fractal pivot detection, confirmation-time, no lookahead - same rule as common.pivots()
   for(int j = InpPivotK; j < rates_total - InpPivotK; j++)
     {
      bool okh = true, okl = true;
      for(int m = j - InpPivotK; m < j; m++)
        {
         if(high[m] >= high[j]) okh = false;
         if(low[m]  <= low[j])  okl = false;
        }
      for(int m = j + 1; m <= j + InpPivotK; m++)
        {
         if(high[m] > high[j]) okh = false;
         if(low[m]  < low[j])  okl = false;
        }
      isHigh[j] = okh;
      isLow[j]  = okl;

      if(InpMarkSwings && j >= start)
        {
         if(okh)
           {
            string name = PFXP + "H_" + IntegerToString((long)time[j]);
            ObjectCreate(0, name, OBJ_ARROW, 0, time[j], high[j]);
            ObjectSetInteger(0, name, OBJPROP_ARROWCODE, 217);
            ObjectSetInteger(0, name, OBJPROP_COLOR, InpSwingHighColor);
            ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_BOTTOM);
            ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
           }
         if(okl)
           {
            string name = PFXP + "L_" + IntegerToString((long)time[j]);
            ObjectCreate(0, name, OBJ_ARROW, 0, time[j], low[j]);
            ObjectSetInteger(0, name, OBJPROP_ARROWCODE, 218);
            ObjectSetInteger(0, name, OBJPROP_COLOR, InpSwingLowColor);
            ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_TOP);
            ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
           }
        }
     }

   //--- up-fan (anchor = swing low) / down-fan (anchor = swing high), forward pass - mirrors
   //--- fan_line_search.py's build_fan_signals(): same-origin lines never need re-sorting by
   //--- value, only by slope (fixed once each line exists), and a broken line is simply dropped.
   int      upAnchorBar = -1;  double upAnchorPrice = 0;
   int      dnAnchorBar = -1;  double dnAnchorPrice = 0;
   FanLine  upLines[]; int upCount = 0;
   FanLine  dnLines[]; int dnCount = 0;
   ArrayResize(upLines, 0);
   ArrayResize(dnLines, 0);

   for(int i = start; i < end; i++)
     {
      if(isLow[i] && (upAnchorBar < 0 || low[i] < upAnchorPrice))
        {
         upAnchorBar = i; upAnchorPrice = low[i];
         ArrayResize(upLines, 0); upCount = 0;
        }
      if(isHigh[i] && (dnAnchorBar < 0 || high[i] > dnAnchorPrice))
        {
         dnAnchorBar = i; dnAnchorPrice = high[i];
         ArrayResize(dnLines, 0); dnCount = 0;
        }

      if(isHigh[i] && upAnchorBar >= 0 && i > upAnchorBar && high[i] > upAnchorPrice)
        {
         FanLine fl;
         fl.anchor_time = time[upAnchorBar]; fl.anchor_price = upAnchorPrice;
         fl.pivot_time  = time[i];           fl.pivot_price  = high[i];
         fl.slope = (high[i] - upAnchorPrice) / (double)(time[i] - time[upAnchorBar]);
         ArrayResize(upLines, upCount + 1); upLines[upCount] = fl; upCount++;
        }
      if(isLow[i] && dnAnchorBar >= 0 && i > dnAnchorBar && low[i] < dnAnchorPrice)
        {
         FanLine fl;
         fl.anchor_time = time[dnAnchorBar]; fl.anchor_price = dnAnchorPrice;
         fl.pivot_time  = time[i];           fl.pivot_price  = low[i];
         fl.slope = (low[i] - dnAnchorPrice) / (double)(time[i] - time[dnAnchorBar]);
         ArrayResize(dnLines, dnCount + 1); dnLines[dnCount] = fl; dnCount++;
        }

      double a = atrBuf[i];
      if(a <= 0)
         continue;

      if(upCount >= 1)
        {
         SortFanDesc(upLines, upCount, true);
         double outerV = upLines[0].anchor_price + upLines[0].slope * (double)(time[i] - upLines[0].anchor_time);
         if(close[i] < outerV)
           {
            for(int x = 0; x < upCount - 1; x++)
               upLines[x] = upLines[x + 1];
            upCount--;
            ArrayResize(upLines, upCount);
           }
        }
      if(dnCount >= 1)
        {
         SortFanDesc(dnLines, dnCount, false);
         double outerV = dnLines[0].anchor_price + dnLines[0].slope * (double)(time[i] - dnLines[0].anchor_time);
         if(close[i] > outerV)
           {
            for(int x = 0; x < dnCount - 1; x++)
               dnLines[x] = dnLines[x + 1];
            dnCount--;
            ArrayResize(dnLines, dnCount);
           }
        }
     }

   //--- only the CURRENTLY ACTIVE (unbroken) lines get drawn - broken ones were already dropped above
   DrawFan(upLines, upCount, "Up", InpUpFanColor, true,  atrBuf[rates_total - 1], time[rates_total - 1]);
   DrawFan(dnLines, dnCount, "Dn", InpDownFanColor, false, atrBuf[rates_total - 1], time[rates_total - 1]);

   return(rates_total);
  }
//+------------------------------------------------------------------+
