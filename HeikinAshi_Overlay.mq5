//+------------------------------------------------------------------+
//|                                       HeikinAshi_Overlay.mq5     |
//|                                                                  |
//|  WHAT THIS IS: a Heikin-Ashi indicator that REPLACES the chart's |
//|  real candles while attached, instead of drawing HA candles on   |
//|  top of them (the built-in MT5 example Heiken_Ashi.mq5 does the  |
//|  latter - both series end up visible at once, which is not what  |
//|  was asked for here). On attach, the real candles are made        |
//|  invisible (their colors are set to match the chart's own          |
//|  background, not deleted or hidden structurally - the real price    |
//|  data is untouched and every other indicator/EA on the chart keeps    |
//|  seeing normal OHLC) and only the computed HA candle series is         |
//|  drawn. On removal, OnDeinit restores the exact candle colors and       |
//|  chart mode that were in effect before this indicator was attached,      |
//|  so the chart goes back to showing normal candles with no trace left.    |
//|                                                                  |
//|  HEIKIN-ASHI FORMULA (standard, no variant):                      |
//|    HA_close = (O + H + L + C) / 4                                  |
//|    HA_open  = (prev HA_open + prev HA_close) / 2                    |
//|               (first bar: (O + C) / 2, i.e. the real bar's own mid)  |
//|    HA_high  = max(H, HA_open, HA_close)                               |
//|    HA_low   = min(L, HA_open, HA_close)                                |
//|  HA_open depends on the PRIOR HA bar, so it's computed once per        |
//|  closed bar and cached (g_haOpen[]/g_haClose[] by bar time) rather       |
//|  than recomputed from scratch on every tick - recomputing from a          |
//|  fixed lookback window on every tick would let a different lookback        |
//|  length quietly change HA_open for bars inside that window (HA_open is      |
//|  a running recursive average over the WHOLE history, not a fixed-window      |
//|  indicator), which is a real, easy-to-miss correctness bug for this           |
//|  specific construction.                                                        |
//+------------------------------------------------------------------+
#property copyright "test-project"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 5
#property indicator_plots   1

#property indicator_type1   DRAW_COLOR_CANDLES
#property indicator_color1  clrDeepSkyBlue, clrSilver   // bull, bear - overridable below
#property indicator_width1  1

input color InpBullColor = C'0,150,255';   // family-standard neon blue
input color InpBearColor = clrWhite;       // family-standard neon white

double BufOpen[];
double BufHigh[];
double BufLow[];
double BufClose[];
double BufColor[];

//--- cache of HA_open/HA_close by bar TIME (not index - index shifts as
//--- new bars arrive, time doesn't), so the recursive relationship never
//--- needs recomputation deeper than "one bar back" on each new tick/bar.
datetime g_haTime[];
double   g_haOpen[];
double   g_haClose[];
int      g_haCount = 0;

//--- original chart state, saved on init, restored on removal.
long  g_origCandleBull = -1;
long  g_origCandleBear = -1;
long  g_origChartMode  = -1;
bool  g_savedOriginal   = false;

//+------------------------------------------------------------------+
int FindCachedHA(datetime t)
  {
   for(int i = g_haCount - 1; i >= 0; i--)
      if(g_haTime[i] == t) return i;
   return -1;
  }

//+------------------------------------------------------------------+
void CacheHA(datetime t, double o, double c)
  {
   int idx = FindCachedHA(t);
   if(idx >= 0) { g_haOpen[idx] = o; g_haClose[idx] = c; return; }
   if(g_haCount >= ArraySize(g_haTime))
     {
      int newSize = ArraySize(g_haTime) + 1000;
      ArrayResize(g_haTime, newSize);
      ArrayResize(g_haOpen, newSize);
      ArrayResize(g_haClose, newSize);
     }
   g_haTime[g_haCount] = t;
   g_haOpen[g_haCount] = o;
   g_haClose[g_haCount] = c;
   g_haCount++;
  }

//+------------------------------------------------------------------+
//| Hides the chart's real candles by matching their draw colors to  |
//| the chart's own background - real OHLC data and every other      |
//| indicator/EA on the chart are completely unaffected, only the     |
//| visual rendering of the native candle series changes.             |
//+------------------------------------------------------------------+
void HideRealCandles()
  {
   if(!g_savedOriginal)
     {
      g_origCandleBull = ChartGetInteger(0, CHART_COLOR_CANDLE_BULL);
      g_origCandleBear = ChartGetInteger(0, CHART_COLOR_CANDLE_BEAR);
      g_origChartMode  = ChartGetInteger(0, CHART_MODE);
      g_savedOriginal  = true;
     }
   long bg = ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   ChartSetInteger(0, CHART_MODE, CHART_CANDLES);   // the color trick only works in candle mode
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, (color)bg);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, (color)bg);
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
void RestoreRealCandles()
  {
   if(!g_savedOriginal) return;
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, (color)g_origCandleBull);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, (color)g_origCandleBear);
   ChartSetInteger(0, CHART_MODE, (int)g_origChartMode);
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, BufOpen,  INDICATOR_DATA);
   SetIndexBuffer(1, BufHigh,  INDICATOR_DATA);
   SetIndexBuffer(2, BufLow,   INDICATOR_DATA);
   SetIndexBuffer(3, BufClose, INDICATOR_DATA);
   SetIndexBuffer(4, BufColor, INDICATOR_COLOR_INDEX);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR,   0, InpBullColor);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR,   1, InpBearColor);
   PlotIndexSetString(0,  PLOT_LABEL, "HA_Open;HA_High;HA_Low;HA_Close");
   ArraySetAsSeries(BufOpen,  false);
   ArraySetAsSeries(BufHigh,  false);
   ArraySetAsSeries(BufLow,   false);
   ArraySetAsSeries(BufClose, false);
   ArraySetAsSeries(BufColor, false);

   ArrayResize(g_haTime,  1000);
   ArrayResize(g_haOpen,  1000);
   ArrayResize(g_haClose, 1000);

   HideRealCandles();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   RestoreRealCandles();
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   //--- re-assert the hide every recalc too - another indicator/EA
   //--- changing chart colors after this one's OnInit (load order isn't
   //--- guaranteed) would otherwise silently bring the real candles back.
   HideRealCandles();

   int start = (prev_calculated > 1) ? prev_calculated - 1 : 0;
   for(int i = start; i < rates_total; i++)
     {
      double haClose = (open[i] + high[i] + low[i] + close[i]) / 4.0;
      double haOpen;
      if(i == 0)
        {
         haOpen = (open[i] + close[i]) / 2.0;
        }
      else
        {
         int prevIdx = FindCachedHA(time[i - 1]);
         double prevOpen, prevClose;
         if(prevIdx >= 0) { prevOpen = g_haOpen[prevIdx]; prevClose = g_haClose[prevIdx]; }
         else             { prevOpen = BufOpen[i - 1];    prevClose = BufClose[i - 1]; }
         haOpen = (prevOpen + prevClose) / 2.0;
        }
      double haHigh = MathMax(high[i], MathMax(haOpen, haClose));
      double haLow  = MathMin(low[i],  MathMin(haOpen, haClose));

      BufOpen[i]  = haOpen;
      BufHigh[i]  = haHigh;
      BufLow[i]   = haLow;
      BufClose[i] = haClose;
      BufColor[i] = (haClose >= haOpen) ? 0 : 1;   // 0 = bull color, 1 = bear color

      CacheHA(time[i], haOpen, haClose);
     }
   return(rates_total);
  }
//+------------------------------------------------------------------+
