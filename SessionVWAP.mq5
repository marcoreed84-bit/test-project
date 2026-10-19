//+------------------------------------------------------------------+
//|                                                   SessionVWAP.mq5 |
//|  Custom VWAP indicator - MT5 has no built-in VWAP. This exists so |
//|  TradePanel_EA.mq5 can add it as a NATIVE chart indicator          |
//|  (ChartIndicatorAdd) instead of hand-drawing one OBJ_TREND segment |
//|  per bar - unlimited history, zero extra chart objects, no hang   |
//|  risk, and (because this is our own indicator, not a built-in     |
//|  one) full color/width control via its own inputs below.          |
//|                                                                     |
//|  Construction: typical price * tick volume, accumulated from the   |
//|  start of each calendar day (session reset at midnight, broker     |
//|  time) - the exact same math as TradePanel_EA.mq5's own            |
//|  SessionVWAP()/DifferentSession() helpers, just computed as a      |
//|  normal single-pass indicator buffer instead of a per-call         |
//|  CopyTime/CopyHigh/... lookup (an indicator buffer is the natural  |
//|  place for this - OnCalculate already gives every bar's arrays in  |
//|  one call, no need to re-fetch a 400-bar window every time).       |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   1
#property indicator_type1   DRAW_LINE
#property indicator_label1  "VWAP"

input color InpVWAPColor = C'0,255,255';   // neon aqua - same family-standard color as every other EA's VWAP
input int   InpVWAPWidth = 1;

double VwapBuffer[];

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, VwapBuffer, INDICATOR_DATA);
   ArraySetAsSeries(VwapBuffer, false);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, InpVWAPColor);
   PlotIndexSetInteger(0, PLOT_LINE_WIDTH, InpVWAPWidth);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   IndicatorSetString(INDICATOR_SHORTNAME, "SessionVWAP");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   //--- a day boundary can only ever invalidate bars from the START of
   //--- that day forward, never earlier ones - find the start of the
   //--- CURRENT (most recent) calendar day once, then recompute from
   //--- whichever is earlier: that day-start, or prev_calculated. A
   //--- plain "recompute everything" every tick would be needlessly
   //--- heavy over a multi-year chart; recomputing only today (worst
   //--- case) is what a session-reset indicator actually needs.
   if(rates_total <= 0) return(0);

   MqlDateTime dtLast; TimeToStruct(time[rates_total - 1], dtLast);
   dtLast.hour = 0; dtLast.min = 0; dtLast.sec = 0;
   datetime todayStart = StructToTime(dtLast);

   int start = 0;
   if(prev_calculated > 1)
     {
      start = prev_calculated - 1;
      //--- walk back further if the recalculation window doesn't yet
      //--- reach today's own start (a fresh day just began)
      while(start > 0 && time[start] >= todayStart) start--;
     }

   double cumPV = 0.0, cumV = 0.0;
   datetime curDay = 0;
   //--- re-accumulate from whatever day each `start` bar belongs to, and
   //--- seed curDay to that same day - otherwise the main loop below,
   //--- which resets the accumulator on every day CHANGE, would see
   //--- curDay==0 on its first iteration and wrongly reset mid-day
   if(start > 0)
     {
      MqlDateTime dtStart; TimeToStruct(time[start], dtStart);
      dtStart.hour = 0; dtStart.min = 0; dtStart.sec = 0;
      datetime dayOfStart = StructToTime(dtStart);
      curDay = dayOfStart;
      for(int j = start - 1; j >= 0; j--)
        {
         if(time[j] < dayOfStart) break;
         double typical = (high[j] + low[j] + close[j]) / 3.0;
         cumPV += typical * (double)tick_volume[j];
         cumV  += (double)tick_volume[j];
        }
     }

   for(int i = start; i < rates_total; i++)
     {
      MqlDateTime dti; TimeToStruct(time[i], dti);
      dti.hour = 0; dti.min = 0; dti.sec = 0;
      datetime dayOfI = StructToTime(dti);
      if(dayOfI != curDay)
        {
         curDay = dayOfI;
         cumPV = 0.0;
         cumV  = 0.0;
        }
      double typical = (high[i] + low[i] + close[i]) / 3.0;
      cumPV += typical * (double)tick_volume[i];
      cumV  += (double)tick_volume[i];
      VwapBuffer[i] = (cumV > 0.0) ? (cumPV / cumV) : EMPTY_VALUE;
     }

   return(rates_total);
  }
