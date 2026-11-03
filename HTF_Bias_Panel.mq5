//+------------------------------------------------------------------+
//|                                           HTF_Bias_Panel.mq5     |
//|  On-chart panel summarizing higher-timeframe context for a 5-min  |
//|  trader, per direct request following the web research on HTF-bias|
//|  trading conventions. Shows H1 structure bias, Daily structure     |
//|  bias, price position vs the prior completed day's high/low, and   |
//|  price vs each timeframe's own 200-period Smoothed MA - then an     |
//|  overall ONLY BUY / ONLY SELL / MIXED readout.                       |
//|                                                                    |
//|  STATUS - READ BEFORE USING: this is a DISCRETIONARY VISUAL AID,     |
//|  not a validated trading signal. The underlying idea (filter M5       |
//|  BOS/CHOCH entries by H1 trend-bias agreement) was explicitly          |
//|  backtested this session and FAILED a proper regime-matched random      |
//|  null after K=4 correction (p(PF)=0.112, p(net)=0.016, threshold          |
//|  0.0127) - the apparent edge in a naive random-timing null turned out      |
//|  to be the trending regime itself, not anything this filter adds. The       |
//|  panel still shows real, honestly-computed structure/MA/level information    |
//|  (useful context for YOUR OWN discretionary judgement, same as every other     |
//|  visual-only indicator in this project), but its "ONLY BUY"/"ONLY SELL"         |
//|  readout is NOT proven to improve on random entry timing - do not treat it       |
//|  as an automated signal or wire it into any EA.                                   |
//|                                                                                      |
//|  Structure bias uses the identical swing-tracking + BOS/CHOCH mechanics  |
//|  as MarketStructure_Break.mq5 (fractal pivot confirmation, ATR-relative   |
//|  minMove noise filter, body-close-only breaks) - just run fresh on each    |
//|  own timeframe's own recent bars (InpBiasLookbackBars, default 200)         |
//|  rather than shared state, since this panel only needs the CURRENT bias,     |
//|  not a running history of every past break.                                   |
//+------------------------------------------------------------------+
#property copyright "test-project"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== Structure bias ==="
input int    InpPivotWindow       = 5;      // same convention as MarketStructure_Break.mq5
input double InpMinMoveATR        = 1.5;
input int    InpBiasLookbackBars  = 200;    // how many of each timeframe's own recent bars feed its
                                             // bias calc - bounded, cheap, recomputed fresh each new bar
input int    InpAtrPeriod         = 14;

input group "=== Moving average context ==="
input int    InpMaPeriod          = 200;
input ENUM_MA_METHOD InpMaMethod  = MODE_SMMA;

input group "=== Panel ==="
input ENUM_BASE_CORNER InpCorner  = CORNER_RIGHT_UPPER;
input int    InpXOffset           = 15;
input int    InpYOffset           = 25;
input int    InpFontSize          = 10;
input color  InpTextColor         = clrWhite;
input color  InpBullColor         = C'0,150,255';   // matches TradePanel_EA's InpThemeBullCol
input color  InpBearColor         = clrWhite;       // matches TradePanel_EA's InpThemeBearCol - kept
                                             // DISTINCT below via a dedicated bear-specific red/orange
                                             // instead, since bull/bear here must be visually opposite,
                                             // not just the candle theme's own two colours.
input color  InpBearSignalColor   = C'255,90,90';
input color  InpMixedColor        = clrSilver;
input color  InpPanelBgColor      = clrBlack;
input int    InpPanelWidth        = 230;

#define PFX "HBP_"

int g_atrHandleH1 = INVALID_HANDLE, g_atrHandleD1 = INVALID_HANDLE;
int g_maHandleH1  = INVALID_HANDLE, g_maHandleD1  = INVALID_HANDLE;
datetime g_lastH1Bar = 0, g_lastD1Bar = 0;

int    g_h1Bias = 0, g_d1Bias = 0;          // 0 undecided, +1 bullish, -1 bearish
double g_h1Ma = 0.0, g_d1Ma = 0.0;
double g_prevDayHigh = 0.0, g_prevDayLow = 0.0;

//+------------------------------------------------------------------+
//| Fresh, bounded structure-bias calc for one timeframe - same swing/ |
//| break mechanics as MarketStructure_Break.mq5, just a one-shot        |
//| recompute over the last InpBiasLookbackBars bars rather than persistent |
//| running state (this panel only needs the CURRENT bias each time it's      |
//| called, not a drawn history of every past break).                          |
//+------------------------------------------------------------------+
int ComputeBias(const ENUM_TIMEFRAMES tf, const int atrHandle)
  {
   int w = InpPivotWindow;
   int need = InpBiasLookbackBars + 2 * w + 10;
   int bars = Bars(_Symbol, tf);
   if(bars < need) need = bars;
   if(need < 2 * w + 10) return(0);

   double h[], l[], c[];
   if(CopyHigh(_Symbol, tf, 0, need, h) < need) return(0);
   if(CopyLow(_Symbol, tf, 0, need, l) < need) return(0);
   if(CopyClose(_Symbol, tf, 0, need, c) < need) return(0);
   ArraySetAsSeries(h, false);
   ArraySetAsSeries(l, false);
   ArraySetAsSeries(c, false);

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(atrHandle, 0, 0, need, atrBuf) < need) return(0);

   double swingHighPrice = 0.0, swingLowPrice = 0.0;
   bool   haveHigh = false, haveLow = false;
   bool   swingHighBroken = true, swingLowBroken = true;
   int    bias = 0;

   for(int i = w; i < need - 1 - w; i++)
     {
      double atrHere = atrBuf[need - 1 - i];
      if(atrHere == EMPTY_VALUE || atrHere <= 0.0) continue;
      double minMove = InpMinMoveATR * atrHere;

      bool isPeak = true, isTrough = true;
      for(int k = 1; k <= w; k++)
        {
         if(h[i] < h[i - k] || h[i] <= h[i + k]) isPeak = false;
         if(l[i] > l[i - k]  || l[i] >= l[i + k]) isTrough = false;
         if(!isPeak && !isTrough) break;
        }

      if(!swingHighBroken && haveHigh && c[i] > swingHighPrice) { swingHighBroken = true; bias = 1; }
      if(!swingLowBroken  && haveLow  && c[i] < swingLowPrice)  { swingLowBroken  = true; bias = -1; }

      if(isPeak && (!haveHigh || MathAbs(h[i] - swingHighPrice) >= minMove))
        { swingHighPrice = h[i]; haveHigh = true; swingHighBroken = false; }
      if(isTrough && (!haveLow || MathAbs(l[i] - swingLowPrice) >= minMove))
        { swingLowPrice = l[i]; haveLow = true; swingLowBroken = false; }
     }
   return(bias);
  }

//+------------------------------------------------------------------+
string BiasText(const int bias) { return(bias > 0 ? "BULLISH" : (bias < 0 ? "BEARISH" : "NO BIAS")); }
color  BiasColor(const int bias) { return(bias > 0 ? InpBullColor : (bias < 0 ? InpBearSignalColor : InpMixedColor)); }

//+------------------------------------------------------------------+
void DrawLabel(const string name, const int x, const int y, const string text, const color col)
  {
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, InpCorner);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, InpFontSize);
     }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
  }

//+------------------------------------------------------------------+
void RedrawPanel()
  {
   int lineH = InpFontSize + 8;
   int y = InpYOffset;
   int x = InpXOffset;

   if(ObjectFind(0, PFX + "bg") < 0)
     {
      ObjectCreate(0, PFX + "bg", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_CORNER, InpCorner);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BACK, false);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BGCOLOR, InpPanelBgColor);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_COLOR, clrGray);
     }
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XDISTANCE, x - 10);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YDISTANCE, y - 8);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XSIZE, InpPanelWidth);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, lineH * 8 + 16);

   DrawLabel(PFX + "title", x, y, "HTF BIAS (discretionary - not a signal)", InpTextColor); y += lineH;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   DrawLabel(PFX + "h1", x, y, "H1 structure:  " + BiasText(g_h1Bias), BiasColor(g_h1Bias)); y += lineH;
   DrawLabel(PFX + "d1", x, y, "Daily structure:  " + BiasText(g_d1Bias), BiasColor(g_d1Bias)); y += lineH;

   int maH1Side = (g_h1Ma > 0) ? (bid > g_h1Ma ? 1 : -1) : 0;
   int maD1Side = (g_d1Ma > 0) ? (bid > g_d1Ma ? 1 : -1) : 0;
   DrawLabel(PFX + "mah1", x, y, "Price vs H1 MA" + IntegerToString(InpMaPeriod) + ":  " +
             (maH1Side == 0 ? "n/a" : (maH1Side > 0 ? "ABOVE" : "BELOW")), BiasColor(maH1Side)); y += lineH;
   DrawLabel(PFX + "mad1", x, y, "Price vs D1 MA" + IntegerToString(InpMaPeriod) + ":  " +
             (maD1Side == 0 ? "n/a" : (maD1Side > 0 ? "ABOVE" : "BELOW")), BiasColor(maD1Side)); y += lineH;

   int pdSide = 0;
   string pdText = "n/a";
   if(g_prevDayHigh > 0 && g_prevDayLow > 0)
     {
      if(bid > g_prevDayHigh)      { pdSide = 1;  pdText = "ABOVE prior-day high"; }
      else if(bid < g_prevDayLow)  { pdSide = -1; pdText = "BELOW prior-day low"; }
      else                          { pdSide = 0;  pdText = "INSIDE prior-day range"; }
     }
   DrawLabel(PFX + "pd", x, y, "Prior-day range:  " + pdText, pdSide == 0 ? InpMixedColor : BiasColor(pdSide));
   y += lineH;

   //--- overall readout: every factor must agree for a directional call -
   //--- any disagreement is MIXED/no-trade, matching the "if HTFs disagree,
   //--- the market is transitioning, stand aside" rule from the web research.
   int factors[5];
   factors[0] = g_h1Bias; factors[1] = g_d1Bias; factors[2] = maH1Side; factors[3] = maD1Side; factors[4] = pdSide;
   bool allBull = true, allBear = true, anyZero = false;
   for(int k = 0; k < 5; k++)
     {
      if(factors[k] == 0) anyZero = true;
      if(factors[k] <= 0) allBull = false;
      if(factors[k] >= 0) allBear = false;
     }
   string overall; color overallCol;
   if(!anyZero && allBull)      { overall = "ONLY BUY";  overallCol = InpBullColor; }
   else if(!anyZero && allBear) { overall = "ONLY SELL"; overallCol = InpBearSignalColor; }
   else                          { overall = "MIXED - STAND ASIDE"; overallCol = InpMixedColor; }
   DrawLabel(PFX + "overall", x, y, "OVERALL:  " + overall, overallCol);

   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpPivotWindow <= 0 || InpBiasLookbackBars <= 0 || InpMaPeriod <= 0)
     {
      Print("HTF_Bias_Panel: InpPivotWindow, InpBiasLookbackBars and InpMaPeriod must all be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_atrHandleH1 = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   g_atrHandleD1 = iATR(_Symbol, PERIOD_D1, InpAtrPeriod);
   g_maHandleH1  = iMA(_Symbol, PERIOD_H1, InpMaPeriod, 0, InpMaMethod, PRICE_CLOSE);
   g_maHandleD1  = iMA(_Symbol, PERIOD_D1, InpMaPeriod, 0, InpMaMethod, PRICE_CLOSE);
   if(g_atrHandleH1 == INVALID_HANDLE || g_atrHandleD1 == INVALID_HANDLE ||
      g_maHandleH1 == INVALID_HANDLE || g_maHandleD1 == INVALID_HANDLE)
     {
      Print("HTF_Bias_Panel: failed to create one or more indicator handles.");
      return(INIT_FAILED);
     }
   g_lastH1Bar = 0; g_lastD1Bar = 0;
   PrintFormat("HTF_Bias_Panel v1.00 OnInit: %s  pivotWindow=%d  minMoveATR=%.2f  maPeriod=%d",
               _Symbol, InpPivotWindow, InpMinMoveATR, InpMaPeriod);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, PFX);
   if(g_atrHandleH1 != INVALID_HANDLE) IndicatorRelease(g_atrHandleH1);
   if(g_atrHandleD1 != INVALID_HANDLE) IndicatorRelease(g_atrHandleD1);
   if(g_maHandleH1  != INVALID_HANDLE) IndicatorRelease(g_maHandleH1);
   if(g_maHandleD1  != INVALID_HANDLE) IndicatorRelease(g_maHandleD1);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   if(rates_total < 1) return(0);

   //--- handle readiness guard (same real-bug class fixed in
   //--- HTF_EMA_Overlay.mq5 v1.01 - a freshly created handle has no data
   //--- for a tick or two, so retry rather than silently show nothing).
   if(BarsCalculated(g_atrHandleH1) <= 0 || BarsCalculated(g_atrHandleD1) <= 0 ||
      BarsCalculated(g_maHandleH1) <= 0  || BarsCalculated(g_maHandleD1) <= 0)
      return(0);

   datetime h1Bar = iTime(_Symbol, PERIOD_H1, 0);
   datetime d1Bar = iTime(_Symbol, PERIOD_D1, 0);
   bool needRecalc = (prev_calculated <= 0);

   if(needRecalc || h1Bar != g_lastH1Bar)
     {
      g_h1Bias = ComputeBias(PERIOD_H1, g_atrHandleH1);
      double tmp[];
      if(CopyBuffer(g_maHandleH1, 0, 0, 1, tmp) >= 1) g_h1Ma = tmp[0];
      g_lastH1Bar = h1Bar;
     }
   if(needRecalc || d1Bar != g_lastD1Bar)
     {
      g_d1Bias = ComputeBias(PERIOD_D1, g_atrHandleD1);
      double tmp[];
      if(CopyBuffer(g_maHandleD1, 0, 0, 1, tmp) >= 1) g_d1Ma = tmp[0];
      double ph[], pl[];
      if(CopyHigh(_Symbol, PERIOD_D1, 1, 1, ph) >= 1) g_prevDayHigh = ph[0];
      if(CopyLow(_Symbol, PERIOD_D1, 1, 1, pl) >= 1)  g_prevDayLow  = pl[0];
      g_lastD1Bar = d1Bar;
     }

   RedrawPanel();
   return(rates_total);
  }
