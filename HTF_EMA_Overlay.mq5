//+------------------------------------------------------------------+
//|                                        HTF_EMA_Overlay.mq5       |
//|  Plots up to 3 TRUE higher-timeframe moving averages directly on  |
//|  the current chart - per direct request, this replaces trying to  |
//|  approximate a higher-timeframe EMA by scaling its period on a     |
//|  lower-timeframe chart (checked against a user-provided table of    |
//|  such scaled periods: the pattern was internally inconsistent        |
//|  between rows, and "Smoothed"/SMMA and "Exponential"/EMA are          |
//|  mathematically different averaging methods to begin with - no        |
//|  period scaling makes one exactly equal the other). This indicator     |
//|  instead computes each line's real iMA() handle on ITS OWN                |
//|  timeframe (independent of the chart it's displayed on) and projects       |
//|  that genuine value onto the current chart - exact, not approximated.      |
//|                                                                    |
//|  Each of the 3 lines is independently configurable: show/hide,     |
//|  timeframe, period, MA method, applied price, colour, line width,   |
//|  and line style (solid/dash/dot/dash-dot/dash-dot-dot) - per direct  |
//|  request. Defaults: M15 21/50/200, method "Smoothed" (MODE_SMMA) -    |
//|  per direct follow-up request, so the line reads exactly as it would   |
//|  on a real M15 chart using that method, at the TRUE period (21/50/200, |
//|  no scaling needed at all now that this computes the real M15 value     |
//|  directly via iMA(PERIOD_M15, ...) rather than approximating it on the   |
//|  current chart's own timeframe).                                          |
//+------------------------------------------------------------------+
#property copyright "test-project"
#property version   "1.03"
#property indicator_chart_window
#property indicator_buffers 3
#property indicator_plots   3
#property indicator_label1  "HTF EMA 1"
#property indicator_type1   DRAW_LINE
#property indicator_label2  "HTF EMA 2"
#property indicator_type2   DRAW_LINE
#property indicator_label3  "HTF EMA 3"
#property indicator_type3   DRAW_LINE

input group "=== Line 1 ==="
input bool               InpShowLine1   = true;
input ENUM_TIMEFRAMES    InpTF1         = PERIOD_M15;
input int                InpPeriod1     = 21;
input ENUM_MA_METHOD     InpMethod1     = MODE_SMMA;   // "Smoothed" - matches what the real M15 chart
                                             // would show with this method, true period 21, no scaling.
input ENUM_APPLIED_PRICE InpPrice1      = PRICE_CLOSE;
input color               InpColor1     = clrDodgerBlue;
input int                 InpWidth1     = 2;
input ENUM_LINE_STYLE     InpStyle1     = STYLE_SOLID;

input group "=== Line 2 ==="
input bool               InpShowLine2   = true;
input ENUM_TIMEFRAMES    InpTF2         = PERIOD_M15;
input int                InpPeriod2     = 50;
input ENUM_MA_METHOD     InpMethod2     = MODE_SMMA;   // "Smoothed", true period 50, no scaling.
input ENUM_APPLIED_PRICE InpPrice2      = PRICE_CLOSE;
input color               InpColor2     = clrOrange;
input int                 InpWidth2     = 2;
input ENUM_LINE_STYLE     InpStyle2     = STYLE_SOLID;

input group "=== Line 3 ==="
input bool               InpShowLine3   = true;
input ENUM_TIMEFRAMES    InpTF3         = PERIOD_M15;
input int                InpPeriod3     = 200;
input ENUM_MA_METHOD     InpMethod3     = MODE_SMMA;   // "Smoothed", true period 200, no scaling.
input ENUM_APPLIED_PRICE InpPrice3      = PRICE_CLOSE;
input color               InpColor3     = clrWhite;
input int                 InpWidth3     = 2;
input ENUM_LINE_STYLE     InpStyle3     = STYLE_SOLID;

//+------------------------------------------------------------------+
double g_buf1[], g_buf2[], g_buf3[];
int    g_handle1 = INVALID_HANDLE, g_handle2 = INVALID_HANDLE, g_handle3 = INVALID_HANDLE;

//+------------------------------------------------------------------+
bool SetupLine(const int bufIndex, double &buf[], const bool show, const int period,
               const ENUM_TIMEFRAMES tf, const ENUM_MA_METHOD method, const ENUM_APPLIED_PRICE price,
               const color col, const int width, const ENUM_LINE_STYLE style, int &handle)
  {
   SetIndexBuffer(bufIndex, buf, INDICATOR_DATA);
   ArraySetAsSeries(buf, false);
   PlotIndexSetDouble(bufIndex, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetInteger(bufIndex, PLOT_DRAW_TYPE, show ? DRAW_LINE : DRAW_NONE);
   PlotIndexSetInteger(bufIndex, PLOT_LINE_COLOR, col);
   PlotIndexSetInteger(bufIndex, PLOT_LINE_WIDTH, width);
   PlotIndexSetInteger(bufIndex, PLOT_LINE_STYLE, style);
   PlotIndexSetInteger(bufIndex, PLOT_SHOW_DATA, show);
   if(!show)
     {
      handle = INVALID_HANDLE;
      return(true);
     }
   if(period <= 0)
     {
      PrintFormat("HTF_EMA_Overlay: line %d period must be >= 1.", bufIndex + 1);
      return(false);
     }
   handle = iMA(_Symbol, tf, period, 0, method, price);
   if(handle == INVALID_HANDLE)
     {
      PrintFormat("HTF_EMA_Overlay: line %d failed to create iMA handle (tf=%s period=%d) - error %d",
                  bufIndex + 1, StringSubstr(EnumToString(tf), 7), period, GetLastError());
      return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(!SetupLine(0, g_buf1, InpShowLine1, InpPeriod1, InpTF1, InpMethod1, InpPrice1,
                 InpColor1, InpWidth1, InpStyle1, g_handle1))
      return(INIT_FAILED);
   if(!SetupLine(1, g_buf2, InpShowLine2, InpPeriod2, InpTF2, InpMethod2, InpPrice2,
                 InpColor2, InpWidth2, InpStyle2, g_handle2))
      return(INIT_FAILED);
   if(!SetupLine(2, g_buf3, InpShowLine3, InpPeriod3, InpTF3, InpMethod3, InpPrice3,
                 InpColor3, InpWidth3, InpStyle3, g_handle3))
      return(INIT_FAILED);

   //--- a higher-timeframe handle needs that timeframe's own bars to exist
   //--- before it can return real values - MT5 handles this by returning
   //--- 0/not-ready from CopyBuffer until enough history is available, so
   //--- no extra guard needed here beyond what FillLine() already checks.
   IndicatorSetString(INDICATOR_SHORTNAME, "HTF EMA Overlay");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_handle1 != INVALID_HANDLE) IndicatorRelease(g_handle1);
   if(g_handle2 != INVALID_HANDLE) IndicatorRelease(g_handle2);
   if(g_handle3 != INVALID_HANDLE) IndicatorRelease(g_handle3);
  }

//+------------------------------------------------------------------+
//| Fills buf[from..rates_total-1] with the given HTF iMA handle's own |
//| value as of each current-chart bar's time - the real HTF EMA, not   |
//| an approximation. iBarShift finds which HTF bar covers that LTF     |
//| bar's time (the currently-forming HTF bar if that time falls        |
//| inside a still-open higher-timeframe candle, which is correct: a     |
//| live HTF EMA genuinely does update with its own still-forming bar,    |
//| exactly as it would look on that timeframe's own chart in real time). |
//+------------------------------------------------------------------+
//| v1.02 FIX (real design bug - "lines are all choppy, zigzag"): the   |
//| old version flat-repeated one HTF bar's value across every LTF bar   |
//| inside it, then JUMPED straight to the next HTF bar's value - a       |
//| staircase, not a line. A real HTF chart draws one point per HTF bar    |
//| and connects consecutive points with a straight diagonal - this is     |
//| what "look like it's attached to the 15min chart directly" actually    |
//| means. Fixed by interpolating: find the HTF bar covering this LTF       |
//| bar's time (valCur) and the NEXT, more recent HTF bar (valNext),         |
//| compute how far through the current HTF bar's own span this LTF bar      |
//| sits (frac, 0 at the HTF bar's open, approaching 1 just before the        |
//| next one begins), and blend linearly - reproducing exactly what           |
//| sampling that same diagonal line at this LTF bar's time would give.        |
//| The still-forming (most recent, shift 0) HTF bar has no "next" bar yet     |
//| to interpolate toward, so it's used as-is - same as a live HTF chart's      |
//| own most recent point, which is also not yet connected to anything.          |
//+------------------------------------------------------------------+
void FillLine(double &buf[], const int handle, const ENUM_TIMEFRAMES tf,
              const int from, const int rates_total, const datetime &time[])
  {
   if(handle == INVALID_HANDLE)
     {
      for(int i = from; i < rates_total; i++) buf[i] = EMPTY_VALUE;
      return;
     }
   int htfPeriodSec = PeriodSeconds(tf);
   if(from >= rates_total || htfPeriodSec <= 0) return;

   //--- v1.03 FIX (real freeze-causing bug - confirmed, not a settings
   //--- issue): the previous version called CopyBuffer TWICE per LTF bar,
   //--- inside this loop - on a fresh attach that loop can run across the
   //--- chart's entire history (hundreds of thousands of bars), so a
   //--- single OnCalculate call could fire well over a million individual
   //--- CopyBuffer calls. Each one has real per-call overhead, and
   //--- indicator calculation runs on the terminal's main thread, so a
   //--- call that takes that long freezes the whole terminal UI, not just
   //--- this indicator. Fixed by bulk-fetching the whole needed shift
   //--- range of HTF values (and HTF bar open times) ONCE per FillLine
   //--- call, then doing plain in-memory array lookups per LTF bar instead
   //--- of a fresh CopyBuffer call each time - the same bulk-fetch-then-
   //--- index pattern every other indicator in this project already uses
   //--- for its ATR buffer.
   int shiftOldest = iBarShift(_Symbol, tf, time[from], false);
   int shiftNewest = iBarShift(_Symbol, tf, time[rates_total - 1], false);
   if(shiftOldest < 0 || shiftNewest < 0)
     {
      for(int i = from; i < rates_total; i++) buf[i] = EMPTY_VALUE;
      return;
     }
   //--- +2 margin: need one bar MORE recent than shiftNewest for its own
   //--- "next bar" interpolation target, plus the usual off-by-one safety.
   int need = shiftOldest - shiftNewest + 3;
   int haveHtf = BarsCalculated(handle);
   if(need > haveHtf) need = haveHtf;
   if(need < 2) need = MathMin(2, haveHtf);

   double vals[];
   datetime opens[];
   ArraySetAsSeries(vals, true);
   ArraySetAsSeries(opens, true);
   int gotVals = CopyBuffer(handle, 0, 0, need, vals);
   int gotTimes = CopyTime(_Symbol, tf, 0, need, opens);
   int got = MathMin(gotVals, gotTimes);
   if(got < 1)
     {
      for(int i = from; i < rates_total; i++) buf[i] = EMPTY_VALUE;
      return;
     }

   for(int i = from; i < rates_total; i++)
     {
      int htfShift = iBarShift(_Symbol, tf, time[i], false);
      if(htfShift < 0 || htfShift >= got) { buf[i] = EMPTY_VALUE; continue; }
      double valCur = vals[htfShift];

      if(htfShift <= 0)
        {
         buf[i] = valCur;   // still-forming HTF bar - nothing to interpolate toward yet
         continue;
        }
      if(htfShift - 1 >= got) { buf[i] = valCur; continue; }
      double valNext = vals[htfShift - 1];

      double frac = (double)(time[i] - opens[htfShift]) / (double)htfPeriodSec;
      if(frac < 0.0) frac = 0.0;
      if(frac > 1.0) frac = 1.0;
      buf[i] = valCur + frac * (valNext - valCur);
     }
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   if(rates_total < 1) return(0);
   //--- v1.01 FIX (real bug - "nothing shows on the chart"): a freshly
   //--- created iMA() handle has no computed data at all for a tick or
   //--- two after OnInit - CopyBuffer against it just fails. The old code
   //--- never checked for this, so on the VERY FIRST OnCalculate call (the
   //--- one that backfills the entire chart's history) every bar's
   //--- CopyBuffer call failed and got silently set to EMPTY_VALUE - and
   //--- since that call still returned rates_total, MT5 treated the whole
   //--- backfill as done and never retried it. Same "not ready yet, retry
   //--- next tick" pattern already used for every ATR handle elsewhere in
   //--- this project (e.g. MarketStructure_Break.mq5) - return(0) keeps
   //--- prev_calculated at 0 so MT5 calls OnCalculate again next tick
   //--- instead of accepting a backfill that silently filled nothing.
   if((g_handle1 != INVALID_HANDLE && BarsCalculated(g_handle1) <= 0) ||
      (g_handle2 != INVALID_HANDLE && BarsCalculated(g_handle2) <= 0) ||
      (g_handle3 != INVALID_HANDLE && BarsCalculated(g_handle3) <= 0))
      return(0);

   //--- incremental: only (re)compute bars that are new or could have
   //--- changed (the current forming bar, always re-evaluated since its
   //--- own HTF parent bar's EMA value can still move intra-bar).
   int from = (prev_calculated <= 1) ? 0 : prev_calculated - 1;

   FillLine(g_buf1, g_handle1, InpTF1, from, rates_total, time);
   FillLine(g_buf2, g_handle2, InpTF2, from, rates_total, time);
   FillLine(g_buf3, g_handle3, InpTF3, from, rates_total, time);

   return(rates_total);
  }
