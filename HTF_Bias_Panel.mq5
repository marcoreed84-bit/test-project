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
#property version   "1.03"
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

input group "=== v1.02: H1 momentum + stochastic (per direct request - a static ==="
input group "=== 'below the MA' reading alone doesn't say what price is doing RIGHT NOW) ==="
input int    InpMomentumBars      = 3;      // H1 momentum: last closed H1 close vs the close this many
                                             // H1 bars earlier - independent of where price sits vs the
                                             // 200 MA, since price can be below a falling-slowly MA
                                             // while still actively rising bar to bar.
input int    InpStochK            = 5;
input int    InpStochD            = 3;
input int    InpStochSlow         = 3;
input ENUM_MA_METHOD   InpStochMaMethod = MODE_SMA;
input ENUM_STO_PRICE   InpStochPrice    = STO_LOWHIGH;

input group "=== v1.02: Volume check ('is volume correct to trade') ==="
input int    InpVolAvgBars        = 20;     // last closed chart-timeframe bar's tick_volume vs the
                                             // average of the InpVolAvgBars bars before it - a rough
                                             // read of whether the current move has real participation
                                             // behind it, not a validated signal (same caveat as the
                                             // rest of this project's tick_volume-based constructions).

input group "=== v1.02: M5/M15 trend (per direct request) ==="
input bool   InpShowM5M15Trend    = true;   // same structure-bias method as H1/Daily below, just run
                                             // on M5 and M15 too - "sideways" = NO BIAS (no confirmed
                                             // break in either direction yet).

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
input int    InpPanelWidth        = 280;    // v1.02: widened from 230 - per direct report the panel was
                                             // too small for its own text, and more rows were added.

#define PFX "HBP_"

int g_atrHandleH1 = INVALID_HANDLE, g_atrHandleD1 = INVALID_HANDLE;
int g_maHandleH1  = INVALID_HANDLE, g_maHandleD1  = INVALID_HANDLE;
int g_stochHandleH1 = INVALID_HANDLE;
int g_atrHandleM5 = INVALID_HANDLE, g_atrHandleM15 = INVALID_HANDLE;
datetime g_lastH1Bar = 0, g_lastD1Bar = 0, g_lastM5Bar = 0, g_lastM15Bar = 0;

int    g_h1Bias = 0, g_d1Bias = 0, g_m5Bias = 0, g_m15Bias = 0;   // 0 undecided, +1 bullish, -1 bearish
double g_h1Ma = 0.0, g_d1Ma = 0.0;
double g_prevDayHigh = 0.0, g_prevDayLow = 0.0;
int    g_h1Momentum = 0;          // +1 rising, -1 falling, 0 unknown
double g_h1StochK = 0.0;
int    g_h1StochDir = 0;          // +1 rising, -1 falling, 0 unknown
bool   g_h1StochOB = false, g_h1StochOS = false;
int    g_volSide = 0;             // +1 above average, -1 below average, 0 unknown

//+------------------------------------------------------------------+
//| Fresh, bounded structure-bias calc for one timeframe - same swing/ |
//| break mechanics as MarketStructure_Break.mq5, just a one-shot        |
//| recompute over the last InpBiasLookbackBars bars rather than persistent |
//| running state (this panel only needs the CURRENT bias each time it's      |
//| called, not a drawn history of every past break).                          |
//+------------------------------------------------------------------+
int ComputeBias(const ENUM_TIMEFRAMES tf, const int atrHandle, bool &ok)
  {
   int w = InpPivotWindow;
   int need = InpBiasLookbackBars + 2 * w + 10;
   int bars = Bars(_Symbol, tf);
   if(bars < need) need = bars;
   if(need < 2 * w + 10) { ok = false; return(0); }

   double h[], l[], c[];
   if(CopyHigh(_Symbol, tf, 0, need, h) < need) { ok = false; return(0); }
   if(CopyLow(_Symbol, tf, 0, need, l) < need) { ok = false; return(0); }
   if(CopyClose(_Symbol, tf, 0, need, c) < need) { ok = false; return(0); }
   ArraySetAsSeries(h, false);
   ArraySetAsSeries(l, false);
   ArraySetAsSeries(c, false);

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(atrHandle, 0, 0, need, atrBuf) < need) { ok = false; return(0); }
   ok = true;

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
//--- v1.01 FIX (Opus audit, real bug - "nothing shows", same class as
//--- Overlay v1.01): OBJ_LABEL defaults to ANCHOR_LEFT_UPPER regardless of
//--- which chart CORNER it's pinned to. With a RIGHT corner, XDISTANCE
//--- measures from the right edge inward, but the text's own left edge
//--- was still being used as the anchor point - so the text ran off the
//--- right side of the chart instead of sitting inside it. Every other
//--- right-corner panel in this project (Aurelius_EA, Fulcrum_EA,
//--- AuRebound_EA) pairs a right corner with ANCHOR_RIGHT_* for exactly
//--- this reason.
//--- v1.03 FIX (Opus audit, real per-tick cost): RedrawPanel() used to run
//--- on EVERY tick with no gating at all, and this function called
//--- ObjectFind() before every single label touch to decide create-vs-
//--- update - about 14 synchronous chart calls per tick just for that,
//--- plus an unconditional ChartRedraw() every tick regardless of whether
//--- anything actually changed. All of this panel's object names are
//--- FIXED (never deleted except in OnDeinit), so ObjectFind is always
//--- redundant after the very first call - replaced with a single shared
//--- "already created" flag. Also now caches each label's last-drawn text
//--- and colour and skips the ObjectSet calls entirely when nothing
//--- changed, reporting back via the `changed` out-parameter so the
//--- caller can skip ChartRedraw() too when nothing on the whole panel
//--- moved this tick.
bool g_panelObjectsCreated = false;

void DrawLabel(const string name, const int x, const int y, const string text, const color col, bool &changed)
  {
   static string lastText[64];
   static color  lastColor[64];
   static string lastName[64];
   static int    used = 0;

   int slot = -1;
   for(int i = 0; i < used; i++)
      if(lastName[i] == name) { slot = i; break; }
   if(slot < 0 && used < 64) { slot = used; lastName[slot] = name; lastText[slot] = ""; lastColor[slot] = clrNONE; used++; }

   if(!g_panelObjectsCreated)
     {
      bool rightCorner = (InpCorner == CORNER_RIGHT_UPPER || InpCorner == CORNER_RIGHT_LOWER);
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, InpCorner);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, rightCorner ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, InpFontSize);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
     }

   if(slot < 0 || lastText[slot] != text || lastColor[slot] != col)
     {
      ObjectSetString(0, name, OBJPROP_TEXT, text);
      ObjectSetInteger(0, name, OBJPROP_COLOR, col);
      if(slot >= 0) { lastText[slot] = text; lastColor[slot] = col; }
      changed = true;
     }
  }

//+------------------------------------------------------------------+
void RedrawPanel()
  {
   int lineH = InpFontSize + 8;
   int y = InpYOffset;
   int x = InpXOffset;

   //--- v1.01 FIX (Opus audit, same right-corner issue as DrawLabel):
   //--- OBJ_RECTANGLE_LABEL is always anchored at its OWN top-left
   //--- regardless of chart corner - XDISTANCE=x-10 with a RIGHT corner
   //--- left almost the entire box off-screen to the right. For a right
   //--- corner, XDISTANCE must be measured from the box's own left edge,
   //--- i.e. pushed out by the box's own width.
   bool rightCorner = (InpCorner == CORNER_RIGHT_UPPER || InpCorner == CORNER_RIGHT_LOWER);
   bool changed = false;
   int totalLines = InpShowM5M15Trend ? 13 : 11;
   if(!g_panelObjectsCreated)
     {
      ObjectCreate(0, PFX + "bg", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_CORNER, InpCorner);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BACK, false);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BGCOLOR, InpPanelBgColor);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_COLOR, clrGray);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_XDISTANCE, rightCorner ? (x - 10 + InpPanelWidth) : (x - 10));
      ObjectSetInteger(0, PFX + "bg", OBJPROP_YDISTANCE, y - 8);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_XSIZE, InpPanelWidth);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, lineH * totalLines + 16);
      changed = true;
     }

   DrawLabel(PFX + "title", x, y, "HTF BIAS (not a signal)", InpTextColor, changed); y += lineH;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   DrawLabel(PFX + "h1", x, y, "H1 structure:  " + BiasText(g_h1Bias), BiasColor(g_h1Bias), changed); y += lineH;

   string momTxt = (g_h1Momentum > 0 ? "RISING" : (g_h1Momentum < 0 ? "FALLING" : "n/a"));
   DrawLabel(PFX + "h1mom", x, y, "H1 momentum (" + IntegerToString(InpMomentumBars) + "b):  " + momTxt,
             BiasColor(g_h1Momentum), changed); y += lineH;

   string stochTxt = DoubleToString(g_h1StochK, 1) + " " +
                      (g_h1StochDir > 0 ? "RISING" : (g_h1StochDir < 0 ? "FALLING" : "n/a")) +
                      (g_h1StochOB ? " (OB)" : (g_h1StochOS ? " (OS)" : ""));
   DrawLabel(PFX + "h1stoch", x, y, "H1 Stoch %K:  " + stochTxt, BiasColor(g_h1StochDir), changed); y += lineH;

   DrawLabel(PFX + "d1", x, y, "Daily structure:  " + BiasText(g_d1Bias), BiasColor(g_d1Bias), changed); y += lineH;

   int maH1Side = (g_h1Ma > 0) ? (bid > g_h1Ma ? 1 : -1) : 0;
   int maD1Side = (g_d1Ma > 0) ? (bid > g_d1Ma ? 1 : -1) : 0;
   DrawLabel(PFX + "mah1", x, y, "Price vs H1 MA" + IntegerToString(InpMaPeriod) + ":  " +
             (maH1Side == 0 ? "n/a" : (maH1Side > 0 ? "ABOVE" : "BELOW")), BiasColor(maH1Side), changed); y += lineH;
   DrawLabel(PFX + "mad1", x, y, "Price vs D1 MA" + IntegerToString(InpMaPeriod) + ":  " +
             (maD1Side == 0 ? "n/a" : (maD1Side > 0 ? "ABOVE" : "BELOW")), BiasColor(maD1Side), changed); y += lineH;

   int pdSide = 0;
   string pdText = "n/a";
   if(g_prevDayHigh > 0 && g_prevDayLow > 0)
     {
      if(bid > g_prevDayHigh)      { pdSide = 1;  pdText = "ABOVE prior-day high"; }
      else if(bid < g_prevDayLow)  { pdSide = -1; pdText = "BELOW prior-day low"; }
      else                          { pdSide = 0;  pdText = "INSIDE prior-day range"; }
     }
   DrawLabel(PFX + "pd", x, y, "Prior-day range:  " + pdText, pdSide == 0 ? InpMixedColor : BiasColor(pdSide), changed);
   y += lineH;

   string volTxt = (g_volSide > 0 ? "ABOVE AVG" : (g_volSide < 0 ? "below avg" : "n/a"));
   DrawLabel(PFX + "vol", x, y, "Volume vs avg:  " + volTxt,
             g_volSide > 0 ? InpBullColor : InpMixedColor, changed); y += lineH;

   if(InpShowM5M15Trend)
     {
      DrawLabel(PFX + "m15", x, y, "M15 trend:  " + BiasText(g_m15Bias), BiasColor(g_m15Bias), changed); y += lineH;
      DrawLabel(PFX + "m5", x, y, "M5 trend:  " + BiasText(g_m5Bias), BiasColor(g_m5Bias), changed); y += lineH;
     }
   else if(!g_panelObjectsCreated)
     {
      ObjectDelete(0, PFX + "m15");
      ObjectDelete(0, PFX + "m5");
     }

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
   DrawLabel(PFX + "overall", x, y, "OVERALL:  " + overall, overallCol, changed);

   g_panelObjectsCreated = true;
   //--- v1.03 FIX (Opus audit, real per-tick cost): used to call
   //--- ChartRedraw() unconditionally on every tick. Only redraw when
   //--- something on the panel actually changed this call.
   if(changed) ChartRedraw(0);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpPivotWindow <= 0 || InpBiasLookbackBars <= 0 || InpMaPeriod <= 0 ||
      InpMomentumBars <= 0 || InpVolAvgBars <= 0 || InpStochK <= 0 || InpStochD <= 0 || InpStochSlow <= 0)
     {
      Print("HTF_Bias_Panel: InpPivotWindow, InpBiasLookbackBars, InpMaPeriod, InpMomentumBars, "
            "InpVolAvgBars, InpStochK, InpStochD and InpStochSlow must all be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_atrHandleH1 = iATR(_Symbol, PERIOD_H1, InpAtrPeriod);
   g_atrHandleD1 = iATR(_Symbol, PERIOD_D1, InpAtrPeriod);
   g_maHandleH1  = iMA(_Symbol, PERIOD_H1, InpMaPeriod, 0, InpMaMethod, PRICE_CLOSE);
   g_maHandleD1  = iMA(_Symbol, PERIOD_D1, InpMaPeriod, 0, InpMaMethod, PRICE_CLOSE);
   g_stochHandleH1 = iStochastic(_Symbol, PERIOD_H1, InpStochK, InpStochD, InpStochSlow, InpStochMaMethod, InpStochPrice);
   g_atrHandleM5  = iATR(_Symbol, PERIOD_M5, InpAtrPeriod);
   g_atrHandleM15 = iATR(_Symbol, PERIOD_M15, InpAtrPeriod);
   if(g_atrHandleH1 == INVALID_HANDLE || g_atrHandleD1 == INVALID_HANDLE ||
      g_maHandleH1 == INVALID_HANDLE || g_maHandleD1 == INVALID_HANDLE ||
      g_stochHandleH1 == INVALID_HANDLE || g_atrHandleM5 == INVALID_HANDLE || g_atrHandleM15 == INVALID_HANDLE)
     {
      Print("HTF_Bias_Panel: failed to create one or more indicator handles.");
      return(INIT_FAILED);
     }
   g_lastH1Bar = 0; g_lastD1Bar = 0; g_lastM5Bar = 0; g_lastM15Bar = 0;
   g_panelObjectsCreated = false;
   PrintFormat("HTF_Bias_Panel v1.03 OnInit: %s  pivotWindow=%d  minMoveATR=%.2f  maPeriod=%d",
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
   if(g_stochHandleH1 != INVALID_HANDLE) IndicatorRelease(g_stochHandleH1);
   if(g_atrHandleM5  != INVALID_HANDLE) IndicatorRelease(g_atrHandleM5);
   if(g_atrHandleM15 != INVALID_HANDLE) IndicatorRelease(g_atrHandleM15);
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
      BarsCalculated(g_maHandleH1) <= 0  || BarsCalculated(g_maHandleD1) <= 0 ||
      BarsCalculated(g_stochHandleH1) <= 0 ||
      (InpShowM5M15Trend && (BarsCalculated(g_atrHandleM5) <= 0 || BarsCalculated(g_atrHandleM15) <= 0)))
      return(0);

   datetime h1Bar = iTime(_Symbol, PERIOD_H1, 0);
   datetime d1Bar = iTime(_Symbol, PERIOD_D1, 0);
   bool needRecalc = (prev_calculated <= 0);

   //--- v1.01 FIX (Opus audit, real gap): ComputeBias/CopyBuffer/CopyHigh/
   //--- CopyLow failures were silently accepted as "done for this bar" -
   //--- g_lastH1Bar/g_lastD1Bar advanced regardless, so a transient copy
   //--- failure left stale "NO BIAS"/"n/a" showing until the NEXT H1 bar
   //--- (or, for Daily, the next calendar day) instead of retrying next
   //--- tick. Now only advances the "last bar" marker when every copy for
   //--- that block actually succeeded.
   if(needRecalc || h1Bar != g_lastH1Bar)
     {
      bool biasOk = false;
      int bias = ComputeBias(PERIOD_H1, g_atrHandleH1, biasOk);
      double tmp[];
      bool maOk = (CopyBuffer(g_maHandleH1, 0, 0, 1, tmp) >= 1);

      //--- v1.02: H1 momentum - last closed H1 close vs the close
      //--- InpMomentumBars H1 bars earlier. Independent of the 200 MA
      //--- reading above, per direct report ("price can be below the 200
      //--- EMA on the 1hour but going up").
      double closeNow = iClose(_Symbol, PERIOD_H1, 1);
      double closeThen = iClose(_Symbol, PERIOD_H1, 1 + InpMomentumBars);
      bool momOk = (closeNow > 0.0 && closeThen > 0.0);
      int mom = momOk ? (closeNow > closeThen ? 1 : (closeNow < closeThen ? -1 : 0)) : 0;

      //--- v1.02: H1 Stochastic %K - last closed value plus rising/falling
      //--- vs one bar earlier, and overbought(>80)/oversold(<20) flags.
      double stochBuf[];
      bool stochOk = (CopyBuffer(g_stochHandleH1, 0, 1, 2, stochBuf) >= 2);
      double kNow = 0.0; int stochDir = 0; bool ob = false, os = false;
      if(stochOk)
        {
         ArraySetAsSeries(stochBuf, true);
         kNow = stochBuf[0];
         stochDir = (stochBuf[0] > stochBuf[1]) ? 1 : (stochBuf[0] < stochBuf[1] ? -1 : 0);
         ob = (kNow > 80.0); os = (kNow < 20.0);
        }

      if(biasOk) g_h1Bias = bias;
      if(maOk) g_h1Ma = tmp[0];
      if(momOk) g_h1Momentum = mom;
      if(stochOk) { g_h1StochK = kNow; g_h1StochDir = stochDir; g_h1StochOB = ob; g_h1StochOS = os; }
      if(biasOk && maOk && momOk && stochOk) g_lastH1Bar = h1Bar;
     }

   if(InpShowM5M15Trend)
     {
      datetime m5Bar = iTime(_Symbol, PERIOD_M5, 0);
      if(needRecalc || m5Bar != g_lastM5Bar)
        {
         bool ok = false;
         int bias = ComputeBias(PERIOD_M5, g_atrHandleM5, ok);
         if(ok) { g_m5Bias = bias; g_lastM5Bar = m5Bar; }
        }
      datetime m15Bar = iTime(_Symbol, PERIOD_M15, 0);
      if(needRecalc || m15Bar != g_lastM15Bar)
        {
         bool ok = false;
         int bias = ComputeBias(PERIOD_M15, g_atrHandleM15, ok);
         if(ok) { g_m15Bias = bias; g_lastM15Bar = m15Bar; }
        }
     }

   //--- v1.02: volume check - reuses the CHART'S OWN tick_volume[] array
   //--- already passed into OnCalculate, no extra Copy* call needed. Last
   //--- CLOSED bar (rates_total-2) vs the average of the InpVolAvgBars
   //--- bars before it - cheap enough to just run every call.
   if(rates_total >= InpVolAvgBars + 2)
     {
      long sum = 0;
      for(int k = rates_total - 2 - InpVolAvgBars; k < rates_total - 2; k++) sum += tick_volume[k];
      double avg = (double)sum / InpVolAvgBars;
      long lastClosedVol = tick_volume[rates_total - 2];
      g_volSide = (avg > 0.0) ? (lastClosedVol > avg ? 1 : -1) : 0;
     }
   if(needRecalc || d1Bar != g_lastD1Bar)
     {
      bool biasOk = false;
      int bias = ComputeBias(PERIOD_D1, g_atrHandleD1, biasOk);
      double tmp[];
      bool maOk = (CopyBuffer(g_maHandleD1, 0, 0, 1, tmp) >= 1);
      double ph[], pl[];
      bool phOk = (CopyHigh(_Symbol, PERIOD_D1, 1, 1, ph) >= 1);
      bool plOk = (CopyLow(_Symbol, PERIOD_D1, 1, 1, pl) >= 1);
      if(biasOk) g_d1Bias = bias;
      if(maOk) g_d1Ma = tmp[0];
      if(phOk) g_prevDayHigh = ph[0];
      if(plOk) g_prevDayLow = pl[0];
      if(biasOk && maOk && phOk && plOk) g_lastD1Bar = d1Bar;
     }

   RedrawPanel();
   return(rates_total);
  }
