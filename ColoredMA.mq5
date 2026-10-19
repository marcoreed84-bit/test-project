//+------------------------------------------------------------------+
//|                                                     ColoredMA.mq5 |
//|  Generic colored/width-configurable moving average - exists so    |
//|  TradePanel_EA.mq5 can plot the 21/50/200 MAs with full color/     |
//|  width control (set per-instance from each MA's own InpColor/      |
//|  InpWidth input below), unlike MT5's built-in Moving Average        |
//|  indicator, which an EA can add via ChartIndicatorAdd(iMA handle)   |
//|  but can never recolor or rewidth once added. The EA adds THREE     |
//|  separate instances of this same file (one per period), each with  |
//|  its own iCustom() parameters - same unlimited-history/zero-extra-  |
//|  chart-object reasoning as SessionVWAP.mq5.                         |
//|                                                                     |
//|  Supports all four standard MT5 MA methods (SMA/EMA/SMMA/LWMA) on   |
//|  the close price, matching exactly what TradePanel_EA.mq5's own     |
//|  InpMAMethod input already offers.                                  |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   1
#property indicator_type1   DRAW_LINE
#property indicator_label1  "MA"

input int              InpPeriod = 21;
input ENUM_MA_METHOD    InpMethod = MODE_EMA;
input color             InpColor  = clrYellow;
input int               InpWidth  = 1;

double MaBuffer[];

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, MaBuffer, INDICATOR_DATA);
   ArraySetAsSeries(MaBuffer, false);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, InpColor);
   PlotIndexSetInteger(0, PLOT_LINE_WIDTH, InpWidth);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, InpPeriod);
   IndicatorSetString(INDICATOR_SHORTNAME, "ColoredMA(" + IntegerToString(InpPeriod) + ")");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(rates_total < InpPeriod) return(0);

   int start = (prev_calculated > 1) ? prev_calculated - 1 : InpPeriod - 1;

   switch(InpMethod)
     {
      case MODE_SMA:
        {
         for(int i = start; i < rates_total; i++)
           {
            double sum = 0.0;
            for(int j = i - InpPeriod + 1; j <= i; j++) sum += close[j];
            MaBuffer[i] = sum / InpPeriod;
           }
         break;
        }
      case MODE_EMA:
        {
         double alpha = 2.0 / (InpPeriod + 1.0);
         if(start == InpPeriod - 1)
           {
            double sum = 0.0;
            for(int j = 0; j < InpPeriod; j++) sum += close[j];
            MaBuffer[InpPeriod - 1] = sum / InpPeriod;
            start = InpPeriod;
           }
         for(int i = start; i < rates_total; i++)
            MaBuffer[i] = MaBuffer[i - 1] + alpha * (close[i] - MaBuffer[i - 1]);
         break;
        }
      case MODE_SMMA:
        {
         if(start == InpPeriod - 1)
           {
            double sum = 0.0;
            for(int j = 0; j < InpPeriod; j++) sum += close[j];
            MaBuffer[InpPeriod - 1] = sum / InpPeriod;
            start = InpPeriod;
           }
         for(int i = start; i < rates_total; i++)
            MaBuffer[i] = (MaBuffer[i - 1] * (InpPeriod - 1) + close[i]) / InpPeriod;
         break;
        }
      case MODE_LWMA:
        {
         int denom = InpPeriod * (InpPeriod + 1) / 2;
         for(int i = start; i < rates_total; i++)
           {
            double sum = 0.0;
            int weight = 1;
            for(int j = i - InpPeriod + 1; j <= i; j++) { sum += close[j] * weight; weight++; }
            MaBuffer[i] = sum / denom;
           }
         break;
        }
     }

   return(rates_total);
  }
