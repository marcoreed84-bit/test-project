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
//|  closed bar and kept in the indicator's own buffers rather              |
//|  than recomputed from scratch on every tick - recomputing from a          |
//|  fixed lookback window on every tick would let a different lookback        |
//|  length quietly change HA_open for bars inside that window (HA_open is      |
//|  a running recursive average over the WHOLE history, not a fixed-window      |
//|  indicator), which is a real, easy-to-miss correctness bug for this           |
//|  specific construction.                                                        |
//|                                                                  |
//|  VERSION HISTORY                                                  |
//|  1.00 - first version.                                            |
//|  1.01 - FIX "no Heikin-Ashi candles show at all". Three causes:    |
//|   (a) The bar-time cache lookup scanned the whole cache for every  |
//|       bar, so the first full calculation on a normal chart (tens   |
//|       of thousands of bars) took minutes - the terminal shows      |
//|       nothing until that finishes, and it restarts on every        |
//|       history reload. The cache is removed; each HA bar now just   |
//|       reads the previous HA bar straight from the indicator's own  |
//|       buffers (same formula, same results, instant).               |
//|   (b) If "Chart on foreground" was on, the real candles (painted   |
//|       in the background colour to hide them) were drawn ON TOP of  |
//|       the HA candles and blanked them out. Now forced off while    |
//|       attached, restored on removal.                               |
//|   (c) Only the real candle BODIES were hidden; their outlines and  |
//|       wicks (separate chart colours) stayed visible in the same    |
//|       blue/white as the HA candles, so the chart looked like       |
//|       ordinary candles. Outlines/wicks are now hidden too.         |
//|  Also: the hide is re-checked twice a second by a timer (not only  |
//|  on new ticks), so another EA on the same chart (e.g. TradePanel   |
//|  re-applying its theme) can't bring the real candles back for long.|
//|  1.02 - FIX (real bug, per report - "still doesn't show HA candles |
//|   instead of regular"): v1.01 hid the wick/outline by setting      |
//|   CHART_COLOR_CHART_UP/CHART_COLOR_CHART_DOWN - but those two      |
//|   properties only affect the BARS chart display mode ("color of    |
//|   the up/down bar"), not Candles mode, which this indicator forces |
//|   via CHART_MODE. They did nothing. The actual wick/shadow color    |
//|   property in Candles mode is CHART_COLOR_CHART_LINE (it also       |
//|   doubles as the Line-chart-type's own line color) - never touched |
//|   until now, which is exactly why the real candles' wicks kept      |
//|   showing through the HA candles the whole time.                    |
//|  1.03 - FIX (real bug, per report - "making price pause"): OnCalculate|
//|   called HideRealCandles() on every tick (several times a second on  |
//|   a fast market), on top of the 500ms timer already doing the same    |
//|   job - each call forces a ChartRedraw(0) whenever another EA on the  |
//|   chart (e.g. TradePanel_EA's ApplyTheme(), which sets these exact      |
//|   same 4 chart properties) had touched the same properties. Redrawing   |
//|   at tick frequency on a chart also carrying another EA's thousands of   |
//|   objects is a real, visible stutter - removed the per-tick copy, kept    |
//|   only the 500ms timer's.                                                  |
//+------------------------------------------------------------------+
#property copyright "test-project"
#property version   "1.03"
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

//--- original chart state, saved on init, restored on removal.
long  g_origCandleBull = -1;
long  g_origCandleBear = -1;
long  g_origChartMode  = -1;
long  g_origChartLine  = -1;
long  g_origForeground = -1;
bool  g_savedOriginal   = false;

//--- set a chart integer property only if it differs; returns true if changed
bool SetIfDiff(ENUM_CHART_PROPERTY_INTEGER prop, long value)
  {
   if(ChartGetInteger(0, prop) == value) return false;
   ChartSetInteger(0, prop, value);
   return true;
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
      g_origChartLine  = ChartGetInteger(0, CHART_COLOR_CHART_LINE);
      g_origForeground = ChartGetInteger(0, CHART_FOREGROUND);
      g_savedOriginal  = true;
     }
   long bg = ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   bool changed = false;
   if(SetIfDiff(CHART_MODE, CHART_CANDLES)) changed = true;      // the color trick only works in candle mode
   if(SetIfDiff(CHART_FOREGROUND, 0)) changed = true;            // price chart must be BEHIND indicator plots
   if(SetIfDiff(CHART_COLOR_CANDLE_BULL, bg)) changed = true;    // bodies
   if(SetIfDiff(CHART_COLOR_CANDLE_BEAR, bg)) changed = true;
   //--- v1.02 FIX (real bug - "still doesn't show HA candles instead of
   //--- regular"): v1.01 set CHART_COLOR_CHART_UP/CHART_COLOR_CHART_DOWN
   //--- to hide the wick/outline - but those two properties only affect
   //--- the BARS chart display mode ("color of the up/down bar"), not
   //--- Candles mode, which this indicator forces via CHART_MODE above.
   //--- They did nothing here. The actual wick/shadow color property in
   //--- BOTH Bars and Candles mode is CHART_COLOR_CHART_LINE (it also
   //--- doubles as the Line-chart-type's own line color, hence the
   //--- name) - that's the one that actually needed hiding, and was
   //--- never touched, which is exactly why the real candles' wicks
   //--- kept showing through the HA candles the whole time.
   if(SetIfDiff(CHART_COLOR_CHART_LINE, bg)) changed = true;     // outlines + wicks
   if(changed) ChartRedraw(0);
  }

//+------------------------------------------------------------------+
void RestoreRealCandles()
  {
   if(!g_savedOriginal) return;
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, (color)g_origCandleBull);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, (color)g_origCandleBear);
   ChartSetInteger(0, CHART_COLOR_CHART_LINE,  (color)g_origChartLine);
   ChartSetInteger(0, CHART_FOREGROUND, g_origForeground != 0);
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

   HideRealCandles();
   EventSetMillisecondTimer(500);   // reassert hide even when no ticks arrive
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   RestoreRealCandles();
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   HideRealCandles();
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   //--- v1.03 FIX (real bug, per report - "making price pause"): this used
   //--- to call HideRealCandles() here too, on EVERY TICK, not just from
   //--- the 500ms timer. OnCalculate fires on every tick, which on a fast
   //--- market can be several times a SECOND - each call re-checks 5 chart
   //--- properties and, whenever anything else on the chart touched them
   //--- (e.g. another EA on the same chart re-asserting ITS OWN theme
   //--- colors - TradePanel_EA's ApplyTheme() sets these exact same 4
   //--- properties), forces a synchronous ChartRedraw(0). On a chart also
   //--- carrying thousands of another EA's objects, a ChartRedraw() at
   //--- tick frequency is a real, visible stutter - this project's own
   //--- TradePanel_EA has hit and fixed the identical mistake before (see
   //--- its v2.09/v2.14 notes on per-tick force-redraws). The 500ms timer
   //--- (OnTimer) already re-asserts the hide twice a second, which is
   //--- more than fast enough for a cosmetic color property - removed the
   //--- redundant, far more frequent copy here.
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
         //--- previous HA bar is already in our own buffers (bars before
         //--- prev_calculated-1 are kept by the terminal between calls).
         haOpen = (BufOpen[i - 1] + BufClose[i - 1]) / 2.0;
        }
      double haHigh = MathMax(high[i], MathMax(haOpen, haClose));
      double haLow  = MathMin(low[i],  MathMin(haOpen, haClose));

      BufOpen[i]  = haOpen;
      BufHigh[i]  = haHigh;
      BufLow[i]   = haLow;
      BufClose[i] = haClose;
      BufColor[i] = (haClose >= haOpen) ? 0 : 1;   // 0 = bull color, 1 = bear color
     }
   return(rates_total);
  }
//+------------------------------------------------------------------+
