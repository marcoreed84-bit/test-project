//+------------------------------------------------------------------+
//|                                          SuperTrend_MTF.mq5      |
//|  Standalone rebuild of a commercial-looking "LT Super Trend 2.0"  |
//|  indicator the user has running and reported causes chart hangs -  |
//|  per direct request, built from scratch (not decompiled/copied -   |
//|  the original's compiled .ex5 was never read) so there's something  |
//|  the user can compare on the same chart against the one that hangs,  |
//|  and so a freeze can be ruled in or out by isolation.                 |
//|                                                                    |
//|  Core: textbook ATR SuperTrend (standard formula, same on every      |
//|  platform - NOT proprietary): basic bands = (high+low)/2 +/- mult*     |
//|  ATR; final bands only move in the trend-favourable direction unless    |
//|  price closes through the opposite one ("sticky" bands); trend flips     |
//|  the first close beyond the opposite final band.                          |
//|                                                                    |
//|  Everything visible in the user's Inputs screenshot is implemented:  |
//|  line colour/width, buy/sell arrows (Wingdings codes 233/234, same     |
//|  as shown), cloud fill between price and the trend line, a price        |
//|  label, an optional single HTF SuperTrend line projected onto the        |
//|  current chart, and a 4-timeframe dashboard panel.                        |
//|                                                                    |
//|  ONE THING IS NOT SPECIFIED by the inputs screenshot and had to be    |
//|  invented: the dashboard's "Warning" (gold) state, between Bullish       |
//|  and Bearish. Defined here as "price is within InpWarningATR x ATR of     |
//|  flipping" - a reasonable guess, not a known fact about the original.      |
//|                                                                    |
//|  PERFORMANCE - this is the actual point of the rebuild, so it's        |
//|  called out explicitly: every per-tick Copy*()/CopyBuffer() call in      |
//|  this file is a SINGLE bulk fetch covering however many bars are          |
//|  actually new, never one call per historical bar inside a loop - the       |
//|  exact anti-pattern that caused real, confirmed freezes in this project's    |
//|  HTF_EMA_Overlay.mq5 (fixed in its own v1.03) earlier. The HTF line and the  |
//|  dashboard's 4 timeframes are each bar-gated to their OWN timeframe (only     |
//|  recomputed when THAT timeframe prints a new bar, not every tick) and bound    |
//|  their own lookback (InpHtfLookbackBars) so a SuperTrend's recurrence (each     |
//|  bar depends on the previous one's final bands) can't turn into an unbounded     |
//|  per-tick cost either.                                                            |
//+------------------------------------------------------------------+
#property copyright "test-project"
#property version   "1.14"
#property indicator_chart_window
#property indicator_buffers 10
#property indicator_plots   5
#property indicator_label1  "Uptrend"
#property indicator_type1   DRAW_LINE
#property indicator_label2  "Downtrend"
#property indicator_type2   DRAW_LINE
#property indicator_label3  "Buy"
#property indicator_type3   DRAW_ARROW
#property indicator_label4  "Sell"
#property indicator_type4   DRAW_ARROW
#property indicator_label5  "Cloud"
#property indicator_type5   DRAW_FILLING
//--- v1.05 FIX (real bug, confirmed - "still no red shading"): a
//--- DRAW_FILLING plot's TWO colours must be declared at COMPILE TIME via
//--- this #property directive - without it, only ONE colour slot exists
//--- for the plot at all, and the runtime PlotIndexSetInteger(4,
//--- PLOT_LINE_COLOR, 1, ...) call for colour index 1 (bearish/red) had
//--- nowhere to go and silently did nothing. These are placeholders only
//--- - OnInit still overwrites both with the actual InpCloudBullColor/
//--- InpCloudBearColor input values at runtime, same as before.
#property indicator_color5  clrGreen, clrRed

input group "=== 1. Indicator settings ==="
input int    InpAtrPeriod        = 10;
input double InpAtrMultiplier    = 3.0;

input group "=== 2. Visual settings - Line ==="
input color  InpBullColor        = clrLime;
input color  InpBearColor        = clrRed;
input int    InpLineWidth        = 2;

input group "=== Signal arrows ==="
input bool   InpShowSignalArrows = true;
input int    InpArrowSize        = 2;
input double InpArrowOffsetATR   = 6.0;    // v1.07: raised again from 3.0 - signals were still printing
                                            // that 1.5x ATR still wasn't far enough from the candles.
                                            // How far an arrow sits from the candle it marks, in ATR.
input color  InpBuyArrowColor    = clrLime;
input color  InpSellArrowColor   = clrRed;
input int    InpBuyArrowCode     = 233;
input int    InpSellArrowCode    = 234;

input group "=== Cloud fill ==="
input bool   InpShowCloudFill    = true;
input color  InpCloudBullColor   = C'0,50,0';      // v1.10: exact values per direct instruction
input color  InpCloudBearColor   = C'50,0,0';

input group "=== Price label ==="
input bool   InpShowPriceLabel   = false;   // v1.11: off by default - overlapped the volume profile
                                             // columns and the dashboard's own ST Value row already
                                             // shows this number, per direct report ("we dont actually
                                             // need it there")
input int    InpPriceLabelOffsetBars = 3;   // v1.06: bars to the right of the last candle the "ST
                                             // Value" label sits - per direct request ("a little away
                                             // from the candle"), was pinned directly at TimeCurrent().
input int    InpPriceLabelBoxBars = 9;      // v1.06: width (in bars) of the dotted box drawn around
                                             // the ST Value label, matching the reference panel.

input group "=== 3. HTF line on chart ==="
input bool             InpShowHtfLine  = false;
input ENUM_TIMEFRAMES  InpHtfTimeframe = PERIOD_H4;
input color             InpHtfBullColor = clrDodgerBlue;
input color             InpHtfBearColor = clrOrangeRed;
input int               InpHtfLineWidth = 3;
input ENUM_LINE_STYLE   InpHtfLineStyle = STYLE_SOLID;

input group "=== 4. Dashboard ==="
input bool   InpShowDashboard    = true;
input int    InpDashX            = 10;     // v1.13: margin from the chart's RIGHT edge (panel is now
                                            // bottom-right anchored, so it can't sit under the
                                            // top-left SELL/BUY quick-trade panel at all)
input int    InpDashY            = 20;     // v1.13: margin from the chart's BOTTOM edge
input color  InpDashTextColor    = clrWhite;
input color  InpDashHeaderColor  = clrDodgerBlue;
input color  InpDashBullColor    = clrLime;
input color  InpDashWarnColor    = clrGold;
input color  InpDashBearColor    = clrRed;
input int    InpVolAvgBars       = 20;      // v1.09: closed bars averaged for the panel's Volume row
input color  InpDashBgColor      = clrBlack;
input int    InpDashWidth        = 210;
//--- NOT in the original's visible inputs - my own addition to define
//--- "Warning" (see file header): price within this many ATR of the
//--- opposite band counts as about-to-flip.
input double InpWarningATR       = 0.25;

input group "=== 5. Multi-timeframe (dashboard rows) ==="
input ENUM_TIMEFRAMES InpTF1 = PERIOD_M15;
input ENUM_TIMEFRAMES InpTF2 = PERIOD_H1;
input ENUM_TIMEFRAMES InpTF3 = PERIOD_H4;
input ENUM_TIMEFRAMES InpTF4 = PERIOD_D1;

input group "=== General ==="
input int    InpHtfLookbackBars  = 500;   // bounds the one-shot SuperTrend recurrence recompute for
                                           // the HTF line AND each dashboard row - a new bar on that
                                           // timeframe triggers a recompute over at most this many of
                                           // its own bars, never per-tick, never unbounded.

//+------------------------------------------------------------------+
double g_lineUp[], g_lineDown[], g_arrowBuy[], g_arrowSell[], g_cloudUp[], g_cloudDn[];
double g_finalUpper[], g_finalLower[], g_trendState[], g_trendDuration[];   // calc-only, not plotted

int      g_atrHandle = INVALID_HANDLE;
datetime g_lastBarTime = 0;
//--- v1.03 FIX (Opus audit, real bug): HTF line / dashboard ATR handles
//--- are now created ONCE here and reused, instead of a fresh handle
//--- being created and immediately released inside ComputeTimeframeTrend
//--- on every call - a brand-new handle has no computed data until after
//--- the CURRENT calculation context returns, so BarsCalculated() nearly
//--- always read 0 and the create/release/retry cycle could essentially
//--- never produce a usable value.
int g_htfAtrHandle = INVALID_HANDLE;
int g_rowAtrHandle[4] = {INVALID_HANDLE, INVALID_HANDLE, INVALID_HANDLE, INVALID_HANDLE};

#define PFX "STM_"

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpAtrPeriod <= 0 || InpAtrMultiplier <= 0.0 || InpHtfLookbackBars <= 0)
     {
      Print("SuperTrend_MTF: InpAtrPeriod, InpAtrMultiplier and InpHtfLookbackBars must all be >= 1 (> 0 for the multiplier).");
      return(INIT_PARAMETERS_INCORRECT);
     }
   SetIndexBuffer(0, g_lineUp, INDICATOR_DATA);
   SetIndexBuffer(1, g_lineDown, INDICATOR_DATA);
   SetIndexBuffer(2, g_arrowBuy, INDICATOR_DATA);
   SetIndexBuffer(3, g_arrowSell, INDICATOR_DATA);
   SetIndexBuffer(4, g_cloudUp, INDICATOR_DATA);
   SetIndexBuffer(5, g_cloudDn, INDICATOR_DATA);
   SetIndexBuffer(6, g_finalUpper, INDICATOR_CALCULATIONS);
   SetIndexBuffer(7, g_finalLower, INDICATOR_CALCULATIONS);
   SetIndexBuffer(8, g_trendState, INDICATOR_CALCULATIONS);
   SetIndexBuffer(9, g_trendDuration, INDICATOR_CALCULATIONS);
   ArraySetAsSeries(g_lineUp, false);
   ArraySetAsSeries(g_lineDown, false);
   ArraySetAsSeries(g_arrowBuy, false);
   ArraySetAsSeries(g_arrowSell, false);
   ArraySetAsSeries(g_cloudUp, false);
   ArraySetAsSeries(g_cloudDn, false);
   ArraySetAsSeries(g_finalUpper, false);
   ArraySetAsSeries(g_finalLower, false);
   ArraySetAsSeries(g_trendState, false);
   ArraySetAsSeries(g_trendDuration, false);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(2, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(3, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(4, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   PlotIndexSetInteger(0, PLOT_LINE_COLOR, InpBullColor);
   PlotIndexSetInteger(0, PLOT_LINE_WIDTH, InpLineWidth);
   PlotIndexSetInteger(1, PLOT_LINE_COLOR, InpBearColor);
   PlotIndexSetInteger(1, PLOT_LINE_WIDTH, InpLineWidth);

   PlotIndexSetInteger(2, PLOT_ARROW, InpBuyArrowCode);
   PlotIndexSetInteger(2, PLOT_LINE_COLOR, InpBuyArrowColor);
   PlotIndexSetInteger(2, PLOT_LINE_WIDTH, InpArrowSize);
   PlotIndexSetInteger(2, PLOT_DRAW_TYPE, InpShowSignalArrows ? DRAW_ARROW : DRAW_NONE);
   PlotIndexSetInteger(3, PLOT_ARROW, InpSellArrowCode);
   PlotIndexSetInteger(3, PLOT_LINE_COLOR, InpSellArrowColor);
   PlotIndexSetInteger(3, PLOT_LINE_WIDTH, InpArrowSize);
   PlotIndexSetInteger(3, PLOT_DRAW_TYPE, InpShowSignalArrows ? DRAW_ARROW : DRAW_NONE);

   PlotIndexSetInteger(4, PLOT_LINE_COLOR, 0, InpCloudBullColor);
   PlotIndexSetInteger(4, PLOT_LINE_COLOR, 1, InpCloudBearColor);
   PlotIndexSetInteger(4, PLOT_DRAW_TYPE, InpShowCloudFill ? DRAW_FILLING : DRAW_NONE);

   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpAtrPeriod);
   g_htfAtrHandle = iATR(_Symbol, InpHtfTimeframe, InpAtrPeriod);
   g_rowAtrHandle[0] = iATR(_Symbol, InpTF1, InpAtrPeriod);
   g_rowAtrHandle[1] = iATR(_Symbol, InpTF2, InpAtrPeriod);
   g_rowAtrHandle[2] = iATR(_Symbol, InpTF3, InpAtrPeriod);
   g_rowAtrHandle[3] = iATR(_Symbol, InpTF4, InpAtrPeriod);
   if(g_atrHandle == INVALID_HANDLE || g_htfAtrHandle == INVALID_HANDLE ||
      g_rowAtrHandle[0] == INVALID_HANDLE || g_rowAtrHandle[1] == INVALID_HANDLE ||
      g_rowAtrHandle[2] == INVALID_HANDLE || g_rowAtrHandle[3] == INVALID_HANDLE)
     {
      Print("SuperTrend_MTF: failed to create one or more ATR handles.");
      return(INIT_FAILED);
     }
   g_lastBarTime = 0;
   //--- v1.02 FIX (real bug - "displays nothing"): v1.01 used a 3-second
   //--- timer calling ChartSetSymbolPeriod() to force a recalc on a
   //--- closed market. MT5's own documentation explicitly warns this can
   //--- RE-INITIALIZE the chart's indicators, even for a same-symbol/
   //--- period call (forum reports are mixed on whether it actually does
   //--- in practice, but the official docs' warning alone makes this too
   //--- risky to rely on). If it does reinit, every 3 seconds would wipe
   //--- all buffered state and restart the ENTIRE historical backfill
   //--- from bar 0 - on a large chart history, that backfill could never
   //--- finish before being torn down and restarted again, which would
   //--- look exactly like "displays nothing, ever". Removed entirely -
   //--- OnCalculate already runs on every real tick without it, same as
   //--- every other indicator in this project that doesn't use this
   //--- trick. The "stays blank on a dead-quiet market" edge case this
   //--- was meant to fix is a minor cosmetic issue; this was a severe,
   //--- unverified risk traded for it.
   IndicatorSetString(INDICATOR_SHORTNAME, "SuperTrend MTF");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, PFX);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   if(g_htfAtrHandle != INVALID_HANDLE) IndicatorRelease(g_htfAtrHandle);
   for(int k = 0; k < 4; k++)
      if(g_rowAtrHandle[k] != INVALID_HANDLE) IndicatorRelease(g_rowAtrHandle[k]);
  }

//+------------------------------------------------------------------+
//| One step of the standard ATR SuperTrend recurrence, given bar i's   |
//| own high/low/close/atr and the PREVIOUS bar's final bands/trend -    |
//| same formula used identically for the main chart and for each HTF     |
//| bounded recompute below, so there's only one implementation of the      |
//| actual math to get right.                                                |
//+------------------------------------------------------------------+
void SuperTrendStep(const double h, const double l, const double c, const double atr,
                     const double prevClose, const double prevFinalUpper, const double prevFinalLower,
                     const double prevTrend, const double mult,
                     double &finalUpper, double &finalLower, double &trend)
  {
   double mid = (h + l) / 2.0;
   double basicUpper = mid + mult * atr;
   double basicLower = mid - mult * atr;

   finalUpper = (basicUpper < prevFinalUpper || prevClose > prevFinalUpper) ? basicUpper : prevFinalUpper;
   finalLower = (basicLower > prevFinalLower || prevClose < prevFinalLower) ? basicLower : prevFinalLower;

   if(c > prevFinalUpper)      trend = 1.0;
   else if(c < prevFinalLower) trend = -1.0;
   else                         trend = prevTrend;
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   bool freshAttach = (prev_calculated <= 0);
   int minBars = InpAtrPeriod + 2;
   //--- v1.03 FIX (Opus audit, real bug): both of these used to return(0)
   //--- unconditionally on failure, which makes MT5 treat the NEXT call as
   //--- a fresh attach (prev_calculated reset to 0) and redo the entire
   //--- historical backfill from bar 0 for a single transient hiccup
   //--- (e.g. the ATR handle not quite ready on one tick). Bounded/cheap
   //--- either way (confirmed no freeze risk), but wasteful and pointless
   //--- - returning prev_calculated on a non-fresh-attach failure instead
   //--- just leaves state as-is and retries incrementally next tick.
   if(rates_total < minBars) return(freshAttach ? 0 : prev_calculated);
   if(BarsCalculated(g_atrHandle) <= 0) return(freshAttach ? 0 : prev_calculated);

   //--- v1.03 FIX (Opus audit, real bug): an early return here used to skip
   //--- the main loop on every tick except the first one of a new bar, so
   //--- the forming bar's line/arrows/price label only ever reflected its
   //--- opening tick, not live price movement within the bar. Removed -
   //--- the normal incremental path below already recomputes just the
   //--- newest bar or two per tick (O(1), not a cost concern).
   int from = freshAttach ? 1 : prev_calculated - 1;
   if(from < 1) from = 1;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   int atrCount = rates_total - from + 1;
   if(CopyBuffer(g_atrHandle, 0, 0, atrCount, atrBuf) < atrCount) return(0);

   if(freshAttach)
     {
      g_finalUpper[0] = (high[0] + low[0]) / 2.0 + InpAtrMultiplier * atrBuf[rates_total - 1];
      g_finalLower[0] = (high[0] + low[0]) / 2.0 - InpAtrMultiplier * atrBuf[rates_total - 1];
      g_trendState[0] = 1.0;
      g_trendDuration[0] = 1.0;
      g_lineUp[0] = EMPTY_VALUE; g_lineDown[0] = EMPTY_VALUE;
      g_arrowBuy[0] = EMPTY_VALUE; g_arrowSell[0] = EMPTY_VALUE;
      g_cloudUp[0] = EMPTY_VALUE; g_cloudDn[0] = EMPTY_VALUE;
     }

   for(int i = from; i < rates_total; i++)
     {
      double atrHere = atrBuf[rates_total - 1 - i];
      if(atrHere == EMPTY_VALUE || atrHere <= 0.0) { atrHere = atrBuf[rates_total - from]; }

      double fu, fl, tr;
      SuperTrendStep(high[i], low[i], close[i], atrHere,
                      close[i - 1], g_finalUpper[i - 1], g_finalLower[i - 1], g_trendState[i - 1],
                      InpAtrMultiplier, fu, fl, tr);
      g_finalUpper[i] = fu; g_finalLower[i] = fl;
      //--- v1.06: tracks how many bars the current trend has held, for
      //--- the dashboard's "Duration" row - compared against the PRIOR
      //--- bar's trend (g_trendState[i-1], still unoverwritten here).
      g_trendDuration[i] = ((tr > 0.0) == (g_trendState[i - 1] > 0.0)) ? g_trendDuration[i - 1] + 1.0 : 1.0;
      g_trendState[i] = tr;

      bool bull = (tr > 0.0);
      double trendVal = bull ? fl : fu;

      g_lineUp[i]   = bull ? trendVal : EMPTY_VALUE;
      g_lineDown[i] = bull ? EMPTY_VALUE : trendVal;

      bool flippedUp   = bull  && g_trendState[i - 1] <= 0.0;
      bool flippedDown = !bull && g_trendState[i - 1] >= 0.0;
      g_arrowBuy[i]  = flippedUp   ? low[i]  - atrHere * InpArrowOffsetATR : EMPTY_VALUE;
      g_arrowSell[i] = flippedDown ? high[i] + atrHere * InpArrowOffsetATR : EMPTY_VALUE;

      if(InpShowCloudFill) { g_cloudUp[i] = close[i]; g_cloudDn[i] = trendVal; }
      else                 { g_cloudUp[i] = EMPTY_VALUE; g_cloudDn[i] = EMPTY_VALUE; }
     }

   if(InpShowPriceLabel)
     {
      int last = rates_total - 1;
      bool lastBull = g_trendState[last] > 0.0;
      double stVal = lastBull ? g_finalLower[last] : g_finalUpper[last];
      datetime lblTime = time[last] + (datetime)(InpPriceLabelOffsetBars * PeriodSeconds(PERIOD_CURRENT));
      DrawPriceLabel(lblTime, lastBull, stVal, atrBuf[0]);
     }
   else { ObjectDelete(0, PFX + "pricelbl"); ObjectDelete(0, PFX + "pricebox"); }

   if(InpShowHtfLine) UpdateHtfLine(time, rates_total);
   else ObjectsDeleteAll(0, PFX + "htfseg_");

   if(InpShowDashboard) UpdateDashboard(tick_volume, rates_total);
   else ObjectsDeleteAll(0, PFX + "dash_");

   g_lastBarTime = time[rates_total - 1];
   return(rates_total);
  }

//+------------------------------------------------------------------+
//--- v1.06 FIX (real bug, per direct report): used to label the candle's
//--- own CLOSE price as "UP "/"DOWN " - the reference screenshot's "ST
//--- Value" is the SuperTrend LINE's own current value, not the close
//--- price, and is a plain price reading, not a trend-direction prefix.
//--- Now shows the same thing the reference does, offset
//--- InpPriceLabelOffsetBars bars to the right of the last candle
//--- instead of pinned at TimeCurrent() (which could sit on/inside it).
void DrawPriceLabel(const datetime lblTime, const bool bull, const double stValue, const double atrHere)
  {
   string nm = PFX + "pricelbl";
   string txt = DoubleToString(stValue, _Digits);

   //--- v1.09 FIX (real bug, per direct report "st value falls outside the
   //--- dotted block"): the label used to anchor LEFT at the box's own left
   //--- edge, so the text (pixel-width, unknown to us) could run past the
   //--- box's right edge depending on digit count/font. Now anchored CENTER
   //--- at the box's own time/price midpoint, so it's always centered
   //--- inside it regardless of text width.
   string box = PFX + "pricebox";
   double halfH = (atrHere > 0.0 ? atrHere : SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 100) * 0.35;
   datetime t1 = lblTime - (datetime)(1 * PeriodSeconds(PERIOD_CURRENT));
   datetime t2 = lblTime + (datetime)(InpPriceLabelBoxBars * PeriodSeconds(PERIOD_CURRENT));
   datetime tMid = t1 + (datetime)(((long)t2 - (long)t1) / 2);

   if(ObjectFind(0, nm) < 0)
     {
      ObjectCreate(0, nm, OBJ_TEXT, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_CENTER);
     }
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, tMid);
   ObjectSetDouble(0, nm, OBJPROP_PRICE, 0, stValue);
   ObjectSetString(0, nm, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, bull ? InpBullColor : InpBearColor);

   //--- v1.06: dotted box around the ST Value label, matching the
   //--- reference "LT Super Trend" panel's boxed value reading.
   if(ObjectFind(0, box) < 0)
     {
      ObjectCreate(0, box, OBJ_RECTANGLE, 0, t1, stValue + halfH, t2, stValue - halfH);
      ObjectSetInteger(0, box, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, box, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, box, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, box, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, box, OBJPROP_FILL, false);
      ObjectSetInteger(0, box, OBJPROP_BACK, true);
     }
   ObjectSetInteger(0, box, OBJPROP_TIME, 0, t1);
   ObjectSetDouble(0, box, OBJPROP_PRICE, 0, stValue + halfH);
   ObjectSetInteger(0, box, OBJPROP_TIME, 1, t2);
   ObjectSetDouble(0, box, OBJPROP_PRICE, 1, stValue - halfH);
   ObjectSetInteger(0, box, OBJPROP_COLOR, bull ? InpBullColor : InpBearColor);
  }

//+------------------------------------------------------------------+
//| Bounded, one-shot SuperTrend recompute over the last InpHtfLookbackBars |
//| CLOSED bars of one timeframe - a single CopyRates + single CopyBuffer    |
//| (ATR) call, then a plain in-memory sequential loop (no further API        |
//| calls). Returns the final bar's own trend state (+1/-1) and, via the       |
//| out arrays, every bar's own trend VALUE (for projecting the HTF line)       |
//| and time (for locating it on the current chart) - same bulk-fetch-then-      |
//| index pattern already fixed into HTF_EMA_Overlay.mq5 v1.04, not a fresh       |
//| per-bar-fetch risk.                                                            |
//+------------------------------------------------------------------+
//--- v1.03 FIX (Opus audit, real bug): used to create+release a fresh
//--- iATR() handle inside this function on every call. A brand-new MT5
//--- indicator handle has no computed data at all until AFTER the
//--- current OnCalculate-equivalent context returns - so BarsCalculated()
//--- almost always read 0 and this returned 0.0/outCount=0 EVERY time,
//--- meaning the HTF line and dashboard rows could essentially never
//--- populate. Fixed by taking an already-created, persistent handle
//--- (made once in OnInit, released once in OnDeinit) as a parameter
//--- instead. Also switched from including the still-forming bar (shift
//--- 0) to CLOSED bars only (shift 1 onward) - the file's own comment
//--- already claimed "CLOSED bars" but the code didn't actually do that.
double ComputeTimeframeTrend(const ENUM_TIMEFRAMES tf, const int atrHandle,
                              double &outTrendVal[], datetime &outTime[], int &outCount)
  {
   outCount = 0;
   if(atrHandle == INVALID_HANDLE || BarsCalculated(atrHandle) <= 0) return(0.0);
   int bars = Bars(_Symbol, tf);
   int need = MathMin(InpHtfLookbackBars, bars - 1);
   if(need < InpAtrPeriod + 2) return(0.0);

   MqlRates r[];
   ArraySetAsSeries(r, true);
   int n = CopyRates(_Symbol, tf, 1, need, r);
   if(n < InpAtrPeriod + 2) return(0.0);

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   int gotAtr = CopyBuffer(atrHandle, 0, 1, n, atrBuf);
   if(gotAtr < n) return(0.0);

   //--- r[]/atrBuf[] are series (index 0 = most recent) - walk oldest to
   //--- newest for the recurrence, i.e. descending array index.
   double finalUpper = (r[n - 1].high + r[n - 1].low) / 2.0 + InpAtrMultiplier * atrBuf[n - 1];
   double finalLower = (r[n - 1].high + r[n - 1].low) / 2.0 - InpAtrMultiplier * atrBuf[n - 1];
   double trend = 1.0;
   double prevClose = r[n - 1].close;

   ArrayResize(outTrendVal, n);
   ArrayResize(outTime, n);
   outTrendVal[n - 1] = trend > 0.0 ? finalLower : finalUpper;
   outTime[n - 1] = r[n - 1].time;

   for(int k = n - 2; k >= 0; k--)
     {
      double atrHere = atrBuf[k];
      if(atrHere == EMPTY_VALUE || atrHere <= 0.0) atrHere = atrBuf[k + 1];
      double fu, fl, tr;
      SuperTrendStep(r[k].high, r[k].low, r[k].close, atrHere,
                      prevClose, finalUpper, finalLower, trend, InpAtrMultiplier, fu, fl, tr);
      finalUpper = fu; finalLower = fl; trend = tr;
      prevClose = r[k].close;
      outTrendVal[k] = (trend > 0.0) ? fl : fu;
      outTime[k] = r[k].time;
     }
   outCount = n;
   return(trend);
  }

//+------------------------------------------------------------------+
//| HTF line: bar-gated to InpHtfTimeframe's own new bars (not every tick), |
//| bulk-computed via ComputeTimeframeTrend above, then projected onto the   |
//| current chart with plain iBarShift index lookups (no Copy* calls inside   |
//| the per-bar loop) - a step function (flat between flips, jump at a flip)    |
//| is the CORRECT representation here, unlike an EMA - SuperTrend's own value  |
//| genuinely doesn't change between flips, so no interpolation is needed.       |
//+------------------------------------------------------------------+
datetime g_lastHtfBar = 0;
double   g_htfTrendVal[];
datetime g_htfTime[];
int      g_htfCount = 0;
double   g_htfTrendDir = 0.0;

void UpdateHtfLine(const datetime &chartTime[], const int rates_total)
  {
   datetime htfBar = iTime(_Symbol, InpHtfTimeframe, 0);
   if(htfBar != g_lastHtfBar || g_htfCount == 0)
     {
      double trend = ComputeTimeframeTrend(InpHtfTimeframe, g_htfAtrHandle, g_htfTrendVal, g_htfTime, g_htfCount);
      if(g_htfCount > 0) { g_htfTrendDir = trend; g_lastHtfBar = htfBar; }
     }
   if(g_htfCount == 0) return;

   //--- OBJ_TREND only supports 2 points - for a genuine multi-segment
   //--- step line, draw a short OBJ_TREND per segment instead, named by
   //--- segment start time so segments update in place rather than
   //--- accumulating. Only (re)draw the last few segments each call -
   //--- bounded, not the whole lookback every tick.
   int pts = g_htfCount;
   int segsToShow = 12;
   int shown = 0;
   for(int k = 0; k < pts && shown < segsToShow; k++)
     {
      datetime t1 = g_htfTime[k];
      datetime t2 = (k > 0) ? g_htfTime[k - 1] : TimeCurrent() + (datetime)PeriodSeconds(InpHtfTimeframe);
      string segNm = PFX + "htfseg_" + IntegerToString((long)t1);
      bool bull = false;
      //--- recover direction at this point by comparing to the adjacent
      //--- final bands is unnecessary here - trend VALUE alone doesn't
      //--- carry sign, so colour by whether price was above/below it.
      int barShift = iBarShift(_Symbol, InpHtfTimeframe, t1, false);
      bull = (barShift >= 0) ? (iClose(_Symbol, InpHtfTimeframe, barShift) >= g_htfTrendVal[k]) : true;
      if(ObjectFind(0, segNm) < 0)
        {
         ObjectCreate(0, segNm, OBJ_TREND, 0, t1, g_htfTrendVal[k], t2, g_htfTrendVal[k]);
         ObjectSetInteger(0, segNm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, segNm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, segNm, OBJPROP_RAY_LEFT, false);
         ObjectSetInteger(0, segNm, OBJPROP_RAY_RIGHT, false);
        }
      else
        {
         ObjectSetInteger(0, segNm, OBJPROP_TIME, 0, t1);
         ObjectSetDouble (0, segNm, OBJPROP_PRICE, 0, g_htfTrendVal[k]);
         ObjectSetInteger(0, segNm, OBJPROP_TIME, 1, t2);
         ObjectSetDouble (0, segNm, OBJPROP_PRICE, 1, g_htfTrendVal[k]);
        }
      ObjectSetInteger(0, segNm, OBJPROP_COLOR, bull ? InpHtfBullColor : InpHtfBearColor);
      ObjectSetInteger(0, segNm, OBJPROP_WIDTH, InpHtfLineWidth);
      ObjectSetInteger(0, segNm, OBJPROP_STYLE, InpHtfLineStyle);
      shown++;
     }
   //--- prune older segments beyond what's still shown
   for(int k = segsToShow; k < pts; k++)
      ObjectDelete(0, PFX + "htfseg_" + IntegerToString((long)g_htfTime[k]));
  }

//+------------------------------------------------------------------+
//| Dashboard: each of the 4 rows is bar-gated to ITS OWN timeframe (only |
//| recomputed when that timeframe prints a new bar), each a single        |
//| bounded ComputeTimeframeTrend call - never per-tick, never per-bar       |
//| Copy* calls.                                                               |
//+------------------------------------------------------------------+
datetime g_lastRowBar[4] = {0, 0, 0, 0};
double   g_rowState[4]   = {0, 0, 0, 0};   // +1 bull, -1 bear, 0 unknown/not-ready
bool     g_rowWarn[4]    = {false, false, false, false};

void UpdateDashboardRow(const int idx, const ENUM_TIMEFRAMES tf, const int atrHandle)
  {
   datetime bar0 = iTime(_Symbol, tf, 0);
   if(bar0 == g_lastRowBar[idx] && g_lastRowBar[idx] != 0) return;

   double trendVal[]; datetime trendTime[]; int cnt = 0;
   double trend = ComputeTimeframeTrend(tf, atrHandle, trendVal, trendTime, cnt);
   if(cnt == 0) return;   // not ready - leave previous state, retry next call

   g_rowState[idx] = trend;
   g_lastRowBar[idx] = bar0;

   //--- v1.03 FIX (Opus audit): reuses the same persistent handle
   //--- (no longer creates/releases its own), and reads the last CLOSED
   //--- bar's ATR (shift 1) to match trendVal[0], which is now also the
   //--- last closed bar's own trend value (see ComputeTimeframeTrend fix).
   double atrBuf[];
   if(atrHandle != INVALID_HANDLE && CopyBuffer(atrHandle, 0, 1, 1, atrBuf) >= 1)
     {
      double close1 = iClose(_Symbol, tf, 1);
      double dist = MathAbs(close1 - trendVal[0]);
      g_rowWarn[idx] = (dist <= InpWarningATR * atrBuf[0]);
     }
  }

//--- v1.06: full consolidated panel, per direct request/reference image -
//--- current-timeframe trend/duration/ST value/distance/ATR/spread, the
//--- same 4-timeframe alignment rows as before, plus a score+caution
//--- readout - replaces needing HTF_Bias_Panel.mq5 as a separate window
//--- alongside this one for the same kind of context.
bool g_dashCreated = false;

void UpdateDashboard(const long &tick_volume[], const int rates_total)
  {
   UpdateDashboardRow(0, InpTF1, g_rowAtrHandle[0]);
   UpdateDashboardRow(1, InpTF2, g_rowAtrHandle[1]);
   UpdateDashboardRow(2, InpTF3, g_rowAtrHandle[2]);
   UpdateDashboardRow(3, InpTF4, g_rowAtrHandle[3]);

   int last = ArraySize(g_trendState) - 1;
   if(last < 1) return;
   bool bull = g_trendState[last] > 0.0;
   double stVal = bull ? g_finalLower[last] : g_finalUpper[last];
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);   // never hardcode point size
   //--- v1.06: ATR pips read from the live indicator handle (last closed bar),
   //--- not a nonexistent g_lastAtr global - fixes a build error.
   double atrNow[];
   ArraySetAsSeries(atrNow, true);
   double atrPips = 0.0;
   if(CopyBuffer(g_atrHandle, 0, 0, 1, atrNow) > 0 && pt > 0.0) atrPips = atrNow[0] / pt;
   int spreadPts = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   int duration = (int)g_trendDuration[last];

   //--- v1.09: volume read - forming bar's tick volume vs the average of
   //--- the last InpVolAvgBars CLOSED bars, so the panel actually answers
   //--- "is the volume right to take this trade" instead of showing nothing.
   long curVol = tick_volume[rates_total - 1];
   long volSum = 0; int volN = 0;
   for(int k = rates_total - 2; k >= 0 && volN < InpVolAvgBars; k--, volN++) volSum += tick_volume[k];
   double avgVol = (volN > 0) ? (double)volSum / volN : 0.0;
   double volRatio = (avgVol > 0.0) ? (double)curVol / avgVol : 0.0;
   string volTxt = (avgVol <= 0.0) ? "n/a" : DoubleToString(volRatio, 1) + "x avg";
   color volCol = (avgVol <= 0.0) ? InpDashTextColor :
                  (volRatio >= 1.2 ? InpDashBullColor : (volRatio < 0.6 ? InpDashWarnColor : InpDashTextColor));

   int lineH = 18;
   int x = InpDashX;
   //--- v1.14: row text centered within the panel width, per direct
   //--- request - centerX is the panel's own horizontal midpoint
   //--- (distance-from-right-edge), independent of each row's text length.
   int centerX = InpDashX - 8 + InpDashWidth / 2;
   int totalLines = 17;
   int panelH = lineH * totalLines + 12;

   //--- v1.13: anchored to the bottom-right corner instead of top-left, per
   //--- direct request ("move it to the bottom right corner") - sidesteps
   //--- the top-left quick-trade panel entirely instead of chasing its
   //--- exact pixel height. y here is distance-from-bottom of the TOP row;
   //--- each successive row's distance-from-bottom shrinks by lineH.
   int y = InpDashY + panelH;

   if(!g_dashCreated)
     {
      ObjectCreate(0, PFX + "dash_bg", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_CORNER, CORNER_RIGHT_LOWER);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_BACK, false);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_BGCOLOR, InpDashBgColor);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_BORDER_TYPE, BORDER_FLAT);
      //--- v1.09: a visible accent border (was near-invisible clrGray on
      //--- a black background) - "more professional" per direct feedback.
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_COLOR, InpDashHeaderColor);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_XDISTANCE, x - 8);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_YDISTANCE, InpDashY - 6);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_XSIZE, InpDashWidth);
      ObjectSetInteger(0, PFX + "dash_bg", OBJPROP_YSIZE, panelH);

      //--- v1.09: thin divider under the title row, same accent color as
      //--- the outer border, for a cleaner/more "professional" layout.
      ObjectCreate(0, PFX + "dash_div", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_CORNER, CORNER_RIGHT_LOWER);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_BACK, false);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_BGCOLOR, InpDashHeaderColor);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_COLOR, InpDashHeaderColor);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_XDISTANCE, x - 8);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_YDISTANCE, y - lineH - 4);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_XSIZE, InpDashWidth);
      ObjectSetInteger(0, PFX + "dash_div", OBJPROP_YSIZE, 1);
     }

   DashLabel("title", centerX, y, "LT Super Trend", InpDashTextColor); y -= lineH;
   DashLabel("hdr1", centerX, y, "CURRENT TIMEFRAME", InpDashHeaderColor); y -= lineH;
   DashLabel("trend", centerX, y, "Trend:  " + (bull ? "BULLISH" : "BEARISH"),
             bull ? InpDashBullColor : InpDashBearColor); y -= lineH;
   DashLabel("dur", centerX, y, "Duration:  " + IntegerToString(duration) + " bars", InpDashTextColor); y -= lineH;
   DashLabel("stval", centerX, y, "ST Value:  " + DoubleToString(stVal, _Digits), InpDashTextColor); y -= lineH;
   DashLabel("atr", centerX, y, "ATR:  " + DoubleToString(atrPips, 1) + " pips", InpDashTextColor); y -= lineH;
   DashLabel("spread", centerX, y, "Spread:  " + IntegerToString(spreadPts) + " pts", InpDashTextColor); y -= lineH;
   DashLabel("vol", centerX, y, "Volume:  " + volTxt, volCol); y -= lineH;

   DashLabel("hdr2", centerX, y, "MULTI-TIMEFRAME", InpDashHeaderColor); y -= lineH;
   string names[4] = {StringSubstr(EnumToString(InpTF1), 7), StringSubstr(EnumToString(InpTF2), 7),
                       StringSubstr(EnumToString(InpTF3), 7), StringSubstr(EnumToString(InpTF4), 7)};
   int bullCount = 0, bearCount = 0;
   for(int idx = 0; idx < 4; idx++)
     {
      string txt = names[idx] + ":  " + (g_rowState[idx] > 0.0 ? "BULLISH" : (g_rowState[idx] < 0.0 ? "BEARISH" : "..."));
      color col = g_rowWarn[idx] ? InpDashWarnColor : (g_rowState[idx] > 0.0 ? InpDashBullColor :
                  (g_rowState[idx] < 0.0 ? InpDashBearColor : InpDashTextColor));
      DashLabel("row" + IntegerToString(idx), centerX, y, txt, col);
      y -= lineH;
      if(g_rowState[idx] > 0.0) bullCount++;
      else if(g_rowState[idx] < 0.0) bearCount++;
     }

   DashLabel("hdr3", centerX, y, "ALIGNMENT", InpDashHeaderColor); y -= lineH;
   int score = MathMax(bullCount, bearCount);
   bool scoreBull = bullCount >= bearCount;
   DashLabel("score", centerX, y, "Score:  " + IntegerToString(score) + "/4  " + (scoreBull ? "BULLISH" : "BEARISH"),
             scoreBull ? InpDashBullColor : InpDashBearColor); y -= lineH;
   DashLabel("status", centerX, y, (score >= 4 ? "STRONG" : "CAUTION"),
             score >= 4 ? (scoreBull ? InpDashBullColor : InpDashBearColor) : InpDashWarnColor);

   g_dashCreated = true;
  }

void DashLabel(const string suffix, const int x, const int y, const string text, const color col)
  {
   static string lastName[32];
   static string lastText[32];
   static color  lastColor[32];
   static int    used = 0;

   string nm = PFX + "dash_" + suffix;
   int slot = -1;
   for(int i = 0; i < used; i++)
      if(lastName[i] == nm) { slot = i; break; }
   if(slot < 0 && used < 32) { slot = used; lastName[slot] = nm; lastText[slot] = ""; lastColor[slot] = clrNONE; used++; }

   if(!g_dashCreated)
     {
      ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      //--- v1.13: bottom-right anchored to match the panel's own corner.
      //--- v1.14: ANCHOR_UPPER (not RIGHT_UPPER) centers each row
      //--- horizontally on its passed-in x, independent of text length -
      //--- per direct request ("align the text... to centred text").
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_RIGHT_LOWER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 10);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, y);
     }

   if(slot < 0 || lastText[slot] != text || lastColor[slot] != col)
     {
      ObjectSetString(0, nm, OBJPROP_TEXT, text);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
      if(slot >= 0) { lastText[slot] = text; lastColor[slot] = col; }
     }
  }
