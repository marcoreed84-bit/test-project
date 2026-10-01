//+------------------------------------------------------------------+
//|                                              MTF_Stochastic.mq5   |
//|                                                                    |
//|  Multi-timeframe Stochastic: attach to any chart (e.g. M1) and it |
//|  plots a HIGHER timeframe's Stochastic %K/%D (e.g. M15) in a      |
//|  separate indicator window below the chart - so you can see what  |
//|  the stochastic is doing on a bigger timeframe while watching     |
//|  price on a smaller one, without needing a second chart window.   |
//|                                                                    |
//|  MECHANISM: computes the Stochastic on InpTimeframe as normal,     |
//|  then for every bar on the CURRENT chart, looks up which           |
//|  InpTimeframe bar it falls inside and plots that bar's %K/%D        |
//|  value - so the line is "stepped": flat across all the small-       |
//|  timeframe bars that share one higher-timeframe bar, then jumps      |
//|  to the next value once a new higher-timeframe bar starts. That's     |
//|  the correct, honest way to show it - the real indicator only UPDATES |
//|  once per higher-timeframe bar close (plus live movement on the        |
//|  still-forming one), it doesn't move every minute.                      |
//|                                                                            |
//|  Run two instances (one InpTimeframe=PERIOD_M5, one =PERIOD_M15) if        |
//|  you want both on screen at once, same way you'd run two of any            |
//|  other indicator.                                                           |
//+------------------------------------------------------------------+
#property copyright "MTF_Stochastic"
#property version   "1.01"
#property strict
#property indicator_separate_window
#property indicator_buffers 2
#property indicator_plots   2
#property indicator_label1  "%K (HTF)"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrDodgerBlue
#property indicator_width1  2
#property indicator_label2  "%D (HTF)"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrOrange
#property indicator_width2  1
#property indicator_minimum 0
#property indicator_maximum 100
#property indicator_level1  20
#property indicator_level2  80

input ENUM_TIMEFRAMES InpTimeframe   = PERIOD_M15;   // Timeframe the Stochastic is computed on
input int             InpKPeriod     = 5;
input int             InpDPeriod     = 3;
input int             InpSlowing     = 3;
input ENUM_MA_METHOD  InpMAMethod    = MODE_SMA;
input ENUM_STO_PRICE  InpPriceField  = STO_LOWHIGH;
input bool             InpSmooth      = false;   // Cosmetic only: linearly interpolate between HTF values
                                                  // instead of a flat step. The real %K/%D genuinely only
                                                  // moves once per InpTimeframe bar - a smooth line here is
                                                  // visual comfort, not real data, so this defaults OFF.
input int              InpMaxHtfBars  = 3000;    // Cap on how much HTF history is pulled per tick (plenty
                                                  // for any realistic chart view - keeps this cheap on a
                                                  // symbol/timeframe with very long history).

double g_kBuf[];
double g_dBuf[];
int    g_handle = INVALID_HANDLE;

int OnInit()
  {
   SetIndexBuffer(0, g_kBuf, INDICATOR_DATA);
   SetIndexBuffer(1, g_dBuf, INDICATOR_DATA);
   ArraySetAsSeries(g_kBuf, true);
   ArraySetAsSeries(g_dBuf, true);

   g_handle = iStochastic(_Symbol, InpTimeframe, InpKPeriod, InpDPeriod, InpSlowing, InpMAMethod, InpPriceField);
   if(g_handle == INVALID_HANDLE)
     {
      PrintFormat("MTF_Stochastic: iStochastic() failed, error %d", GetLastError());
      return(INIT_FAILED);
     }

   IndicatorSetString(INDICATOR_SHORTNAME,
                       StringFormat("MTF Stoch(%s %d,%d,%d)", EnumToString(InpTimeframe), InpKPeriod, InpDPeriod, InpSlowing));
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   if(g_handle != INVALID_HANDLE) IndicatorRelease(g_handle);
  }

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(BarsCalculated(g_handle) < 2) return(0);   // HTF indicator not ready yet

   double htfK[], htfD[];
   ArraySetAsSeries(htfK, true);
   ArraySetAsSeries(htfD, true);
   int htfBars = MathMin(Bars(_Symbol, InpTimeframe), InpMaxHtfBars);
   if(htfBars < 2) return(0);
   if(CopyBuffer(g_handle, 0, 0, htfBars, htfK) <= 0) return(0);
   if(CopyBuffer(g_handle, 1, 0, htfBars, htfD) <= 0) return(0);

   // chart arrays here are time-ascending (not series) by MQL5 convention
   // for OnCalculate - iterate forward, recompute from prev_calculated-1
   // so a mid-bar HTF update still repaints just the current forming bar.
   int start = (prev_calculated > 1) ? prev_calculated - 1 : 0;
   for(int i = start; i < rates_total; i++)
     {
      int htfShift = iBarShift(_Symbol, InpTimeframe, time[i], false);
      if(htfShift < 0 || htfShift >= htfBars)
        {
         g_kBuf[rates_total - 1 - i] = EMPTY_VALUE;
         g_dBuf[rates_total - 1 - i] = EMPTY_VALUE;
         continue;
        }
      // htfK/htfD are series-indexed (0 = most recent HTF bar); map the
      // current-chart bar's own series position the same way so both
      // buffers line up with MT5's bottom-up indicator buffer convention.
      int seriesPos = rates_total - 1 - i;
      if(!InpSmooth || htfShift + 1 >= htfBars)
        {
         g_kBuf[seriesPos] = htfK[htfShift];
         g_dBuf[seriesPos] = htfD[htfShift];
        }
      else
        {
         // InpSmooth: glide from the PREVIOUS HTF value (htfShift+1, the
         // bar just before this one) toward the CURRENT HTF bar's value
         // (htfShift), by how far time[i] sits through the current HTF
         // bar's own span - cosmetic only, see the input's own comment.
         datetime htfOpenNow = iTime(_Symbol, InpTimeframe, htfShift);
         int periodSec = PeriodSeconds(InpTimeframe);
         double frac = 0.0;
         if(htfOpenNow != 0 && periodSec > 0)
            frac = (double)(time[i] - htfOpenNow) / (double)periodSec;
         frac = MathMax(0.0, MathMin(1.0, frac));
         g_kBuf[seriesPos] = htfK[htfShift + 1] + frac * (htfK[htfShift] - htfK[htfShift + 1]);
         g_dBuf[seriesPos] = htfD[htfShift + 1] + frac * (htfD[htfShift] - htfD[htfShift + 1]);
        }
     }

   return(rates_total);
  }
