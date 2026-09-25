//+------------------------------------------------------------------+
//|                                   VWAP_Readiness_Indicator.mq5    |
//|                                                                  |
//|  WHAT THIS IS: a small, standalone chart-window panel - NOT an   |
//|  Expert Advisor, zero trade-execution code. It draws the session |
//|  VWAP (with its outer deviation bands) on the chart, plus a lean |
//|  readiness panel answering exactly three questions at a glance:  |
//|    - is there enough VOLUME right now to trade,                  |
//|    - is the SPREAD currently inside an acceptable range,          |
//|    - is the SHORT-TERM TREND up or down.                           |
//|  This is deliberately a separate, simpler tool from                |
//|  ScalpSignal_Indicator.mq5 (which ports Aurelius's full real         |
//|  entry/exit gate and draws historical trade arrows) - "the VWAP       |
//|  indicator on its own", per the explicit request that led to this      |
//|  file, 2026-09-25. No arrows, no trade history, no entry gate, no       |
//|  claimed edge - just VWAP + 3 readiness readouts.                        |
//|                                                                  |
//|  TIMEFRAME: unlike ScalpSignal_Indicator, this is NOT locked to    |
//|  M5/M15 - volume ratio, spread and short-term MA slope are generic  |
//|  concepts that work on any chart period, so it runs on whatever      |
//|  timeframe it's attached to.                                          |
//|                                                                  |
//|  VOLUME readiness: current bar's tick_volume vs the average of the |
//|  prior InpVolAvgBars closed bars, ratio >= InpMinVolRatio. Same      |
//|  construction and default threshold as Aurelius_EA.mq5's own real     |
//|  InpUseVolume/InpMinVolRatio (VolumeRatioAt()) - a real, already-       |
//|  validated lever in this portfolio, not a new invented one.              |
//|                                                                  |
//|  SPREAD readiness: current LIVE spread (points) <= InpMaxSpreadPoints. |
//|  Live-only, like every other spread check in this project's indicators  |
//|  - MT5's standard OHLCV bar history carries no reliable per-bar spread   |
//|  series (same disclosed platform limitation as ScalpSignal_Indicator).    |
//|                                                                  |
//|  TREND: the InpTrendMAPeriod EMA's own slope over InpTrendSlopeBars,  |
//|  normalised by ATR (the built-in iATR, matching Ratchet_EA.mq5's own    |
//|  ATR choice, not the manual Wilder ATR the Aurelius files use - this      |
//|  file doesn't port any EA's exact gate, so there is no "real" ATR to       |
//|  match). Up if slope >= +InpTrendSlopeThresholdATR, down if <=            |
//|  -InpTrendSlopeThresholdATR, else "flat" - a small threshold, not a        |
//|  bare sign check, so it doesn't flicker on noise.                           |
//|                                                                  |
//|  VWAP + outer bands: SessionVWAP()/SessionVWAPBand() are the SAME real |
//|  constructions added to ScalpSignal_Indicator.mq5 this session (session- |
//|  anchored VWAP, +/- k * volume-weighted stdev bands) - shown here as a     |
//|  chart visual and as two panel rows (price vs VWAP, price vs the band),     |
//|  purely informational. Real M1 testing this session found NO construction   |
//|  built on this pattern (VWAP-band + stochastic reversal, wide or tight-      |
//|  tuned) cleared a real edge - see ScalpSignal_Indicator.mq5's own header      |
//|  RESEARCH NOTE for the numbers. Drawn here for the same reason: a              |
//|  discretionary visual reference, never a claimed signal.                        |
//+------------------------------------------------------------------+
#property copyright "VWAP_Readiness"
#property version   "1.00"
#property description "Standalone VWAP + volume/spread/trend readiness panel (no trade execution)"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0
#property strict

//--- VWAP visuals ------------------------------------------------------
input bool     InpShowVWAP       = true;         // Draw the session VWAP line
input color    InpColVWAP        = C'0,255,255';
input bool     InpShowVWAPBands  = true;         // Draw VWAP's outer deviation bands (informational - see header)
input double   InpVWAPBandK      = 2.0;          // Band width, x volume-weighted stdev from VWAP
input color    InpColVWAPBand    = C'0,150,150';

//--- Volume readiness ----------------------------------------------------
input int      InpVolAvgBars     = 100;          // Bars used for the volume average (Aurelius_EA.mq5's own real default)
input double   InpMinVolRatio    = 1.25;         // Min current-bar volume vs that average to call it "ready" (Aurelius's own real default)

//--- Spread readiness (live only - see header) ---------------------------
input int      InpMaxSpreadPoints = 60;          // Max acceptable live spread, points (Aurelius_EA.mq5's own real default)

//--- Short-term trend ------------------------------------------------------
input int      InpTrendMAPeriod        = 21;     // EMA period used for the trend slope
input int      InpTrendSlopeBars       = 10;     // Bars back the slope is measured over
input double   InpTrendSlopeThresholdATR = 0.10; // Min |slope| (x ATR) to call it up/down rather than "flat"

//--- Panel -----------------------------------------------------------------
input bool     InpShowPanel   = true;
input int      InpPanelDrag   = 1;               // 0 = locked, 1 = draggable
input int      InpPanelX      = 12;
input int      InpPanelY      = 30;              // From the bottom edge when InpPanelBottom=true
input bool     InpPanelBottom = true;
input int      InpPanelW      = 240;
input color    InpPanelBg     = C'13,17,28';
input color    InpHeaderBg    = C'28,36,58';
input color    InpPanelEdge   = C'255,196,84';
input color    InpTitleCol    = C'255,196,84';
input color    InpSectionCol  = C'214,226,238';
input color    InpTextCol     = C'150,166,192';
input color    InpValCol      = C'236,242,252';
input color    InpOkCol       = C'0,230,118';
input color    InpNoCol       = C'255,61,90';
input color    InpShadowCol   = C'6,8,14';
input string   InpPanelFont   = "Consolas";
input int      InpPanelSize   = 8;
input string   InpWatermark   = "VWAP READY";
input color    InpWaterCol    = C'46,38,24';

string   g_pp = "VWRP_";   // panel objects
string   g_pm = "VWRM_";   // VWAP/band chart-line segments
string   g_pw = "VWRW_";   // watermark
int      g_panelMinW = 0;
bool     g_panelReclaim = true;
int      g_panX = -1, g_panY = -1;
datetime g_lastPanelDraw = 0;
int      hTrendMA = INVALID_HANDLE;
int      hATR     = INVALID_HANDLE;
datetime g_lastVwapBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   hTrendMA = iMA(_Symbol, PERIOD_CURRENT, InpTrendMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   hATR     = iATR(_Symbol, PERIOD_CURRENT, 14);
   if(hTrendMA == INVALID_HANDLE || hATR == INVALID_HANDLE)
     {
      Print("VWAP_Readiness_Indicator: failed to create an indicator handle. Error ", GetLastError());
      return(INIT_FAILED);
     }
   IndicatorSetString(INDICATOR_SHORTNAME, "VWAP Readiness (" + _Symbol + " " + EnumToString((ENUM_TIMEFRAMES)_Period) + ")");
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pm);
   ObjectsDeleteAll(0, g_pw);
   Comment("");
  }
//+------------------------------------------------------------------+
//| Session VWAP - same real construction as ScalpSignal_Indicator's  |
//| SessionVWAP(shift), ported from Aurelius_EA.mq5's own function.   |
//+------------------------------------------------------------------+
double SessionVWAP(const int shift)
  {
   datetime barTime = iTime(_Symbol, PERIOD_CURRENT, shift);
   if(barTime == 0) return(0.0);
   MqlDateTime dt; TimeToStruct(barTime, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);

   datetime tArr[]; double hArr[], lArr[], cArr[]; long vArr[];
   ArraySetAsSeries(tArr, true); ArraySetAsSeries(hArr, true);
   ArraySetAsSeries(lArr, true); ArraySetAsSeries(cArr, true);
   ArraySetAsSeries(vArr, true);
   int got = CopyTime(_Symbol, PERIOD_CURRENT, shift, 400, tArr);
   if(got <= 0) return(0.0);
   if(CopyHigh(_Symbol, PERIOD_CURRENT, shift, got, hArr) <= 0) return(0.0);
   if(CopyLow(_Symbol, PERIOD_CURRENT, shift, got, lArr) <= 0) return(0.0);
   if(CopyClose(_Symbol, PERIOD_CURRENT, shift, got, cArr) <= 0) return(0.0);
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, shift, got, vArr) <= 0) return(0.0);

   double cumPV = 0.0, cumV = 0.0;
   for(int s = 0; s < got; s++)
     {
      if(tArr[s] < dayStart) break;
      double typical = (hArr[s] + lArr[s] + cArr[s]) / 3.0;
      cumPV += typical * (double)vArr[s];
      cumV  += (double)vArr[s];
     }
   if(cumV <= 0.0) return(0.0);
   return(cumPV / cumV);
  }
//+------------------------------------------------------------------+
//| VWAP outer bands - same real construction as ScalpSignal_         |
//| Indicator's SessionVWAPBand(): VWAP +/- k * session-cumulative    |
//| volume-weighted stdev of typical price from VWAP.                 |
//+------------------------------------------------------------------+
bool SessionVWAPBand(const int shift, const double k, double &upper, double &lower)
  {
   upper = 0.0; lower = 0.0;
   datetime barTime = iTime(_Symbol, PERIOD_CURRENT, shift);
   if(barTime == 0) return(false);
   MqlDateTime dt; TimeToStruct(barTime, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);

   datetime tArr[]; double hArr[], lArr[], cArr[]; long vArr[];
   ArraySetAsSeries(tArr, true); ArraySetAsSeries(hArr, true);
   ArraySetAsSeries(lArr, true); ArraySetAsSeries(cArr, true);
   ArraySetAsSeries(vArr, true);
   int got = CopyTime(_Symbol, PERIOD_CURRENT, shift, 400, tArr);
   if(got <= 0) return(false);
   if(CopyHigh(_Symbol, PERIOD_CURRENT, shift, got, hArr) <= 0) return(false);
   if(CopyLow(_Symbol, PERIOD_CURRENT, shift, got, lArr) <= 0) return(false);
   if(CopyClose(_Symbol, PERIOD_CURRENT, shift, got, cArr) <= 0) return(false);
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, shift, got, vArr) <= 0) return(false);

   double sumWX = 0.0, sumWX2 = 0.0, sumW = 0.0;
   for(int s = 0; s < got; s++)
     {
      if(tArr[s] < dayStart) break;
      double typical = (hArr[s] + lArr[s] + cArr[s]) / 3.0;
      double w = (double)vArr[s];
      sumWX  += typical * w;
      sumWX2 += typical * typical * w;
      sumW   += w;
     }
   if(sumW <= 0.0) return(false);
   double vwap = sumWX / sumW;
   double var  = sumWX2 / sumW - vwap * vwap;
   double sd   = MathSqrt(MathMax(var, 0.0));
   upper = vwap + k * sd;
   lower = vwap - k * sd;
   return(true);
  }
//+------------------------------------------------------------------+
//| Volume readiness - Aurelius_EA.mq5's own real VolumeRatioAt():    |
//| current bar's tick_volume / average of the prior avgBars bars.    |
//+------------------------------------------------------------------+
double VolumeRatioAt(const int shift, const int avgBars)
  {
   long vCur[]; ArraySetAsSeries(vCur, true);
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, shift, 1, vCur) < 1) return(-1.0);
   long vAvg[]; ArraySetAsSeries(vAvg, true);
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, shift + 1, avgBars, vAvg) < avgBars) return(-1.0);
   double sum = 0.0;
   for(int k = 0; k < avgBars; k++) sum += (double)vAvg[k];
   double avg = sum / avgBars;
   if(avg <= 0.0) return(-1.0);
   return((double)vCur[0] / avg);
  }
//+------------------------------------------------------------------+
//| Short-term trend - EMA(InpTrendMAPeriod) slope over               |
//| InpTrendSlopeBars, ATR-normalised, thresholded to avoid noise     |
//| flicker. Returns +1 up, -1 down, 0 flat/unavailable.              |
//+------------------------------------------------------------------+
int TrendDir(double &slopeOut)
  {
   slopeOut = 0.0;
   double maNow[], maPast[], atrNow[];
   ArraySetAsSeries(maNow, true); ArraySetAsSeries(maPast, true); ArraySetAsSeries(atrNow, true);
   if(CopyBuffer(hTrendMA, 0, 1, 1, maNow) < 1) return(0);
   if(CopyBuffer(hTrendMA, 0, 1 + InpTrendSlopeBars, 1, maPast) < 1) return(0);
   if(CopyBuffer(hATR, 0, 1, 1, atrNow) < 1) return(0);
   if(atrNow[0] <= 0.0 || maNow[0] == EMPTY_VALUE || maPast[0] == EMPTY_VALUE) return(0);
   double slope = (maNow[0] - maPast[0]) / atrNow[0];
   slopeOut = slope;
   if(slope >= InpTrendSlopeThresholdATR)  return(1);
   if(slope <= -InpTrendSlopeThresholdATR) return(-1);
   return(0);
  }
//+------------------------------------------------------------------+
//| Chart-line drawing for the VWAP/band segments - same OBJ_TREND    |
//| per-bar idiom as ScalpSignal_Indicator.mq5's DrawMASegment().     |
//+------------------------------------------------------------------+
void DrawSeg(const string tag, const datetime tOld, const double vOld,
             const datetime tNew, const double vNew, const color col)
  {
   if(vOld == 0.0 || vNew == 0.0) return;
   string nm = g_pm + tag + "_" + IntegerToString((long)tNew);
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_TREND, 0, tOld, vOld, tNew, vNew);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
bool DifferentSession(const int shiftOld, const int shiftNew)
  {
   datetime tOld = iTime(_Symbol, PERIOD_CURRENT, shiftOld);
   datetime tNew = iTime(_Symbol, PERIOD_CURRENT, shiftNew);
   if(tOld == 0 || tNew == 0) return(true);
   MqlDateTime a, b; TimeToStruct(tOld, a); TimeToStruct(tNew, b);
   return(a.day != b.day || a.mon != b.mon || a.year != b.year);
  }
//+------------------------------------------------------------------+
//| Draws the newest closed bar's VWAP/band segment only, each new    |
//| bar - a live panel doesn't need to re-walk full history the way   |
//| ScalpSignal_Indicator's historical markup does.                   |
//+------------------------------------------------------------------+
void UpdateVwapLine()
  {
   datetime bt1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(bt1 == 0 || bt1 == g_lastVwapBarTime) return;
   g_lastVwapBarTime = bt1;
   datetime bt2 = iTime(_Symbol, PERIOD_CURRENT, 2);
   if(bt2 == 0 || DifferentSession(2, 1)) return;

   if(InpShowVWAP)
     {
      double vA = SessionVWAP(2), vB = SessionVWAP(1);
      if(vA > 0.0 && vB > 0.0) DrawSeg("vwap", bt2, vA, bt1, vB, InpColVWAP);
     }
   if(InpShowVWAPBands)
     {
      double uA, lA, uB, lB;
      if(SessionVWAPBand(2, InpVWAPBandK, uA, lA) && SessionVWAPBand(1, InpVWAPBandK, uB, lB))
        {
         DrawSeg("vwapU", bt2, uA, bt1, uB, InpColVWAPBand);
         DrawSeg("vwapL", bt2, lA, bt1, lB, InpColVWAPBand);
        }
     }
  }
//+------------------------------------------------------------------+
//| Panel primitives - identical to ScalpSignal_Indicator.mq5's own   |
//| PRect/PFrame/PText/PRow/PSection/PWatermark/EstimateTextWidth.    |
//+------------------------------------------------------------------+
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
void PRect(const string id, const int x, const int y, const int w, const int h,
           const color bg, const color edge, const int border = 1)
  {
   string nm = g_pp + id;
   bool grab = (InpPanelDrag == 1 && id == "bg");
   bool exists = (ObjectFind(0, nm) >= 0);
   if(g_panelReclaim && !grab && exists) { ObjectDelete(0, nm); exists = false; }
   if(!exists) ObjectCreate(0, nm, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, nm, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, nm, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, nm, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, nm, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, edge);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, border);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, grab);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, !grab);
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5000);
  }
void PFrame(const string id, const int x, const int y, const int w, const int h,
            const color edge, const int thick = 2)
  {
   PRect(id + "ft", x,             y,             w,     thick, edge, edge, 0);
   PRect(id + "fb", x,             y + h - thick, w,     thick, edge, edge, 0);
   PRect(id + "fl", x,             y,             thick, h,     edge, edge, 0);
   PRect(id + "fr", x + w - thick, y,             thick, h,     edge, edge, 0);
  }
void PText(const string id, const int x, const int y, const string txt,
           const color col, const int size = 0, const bool rightAlign = false,
           const string font = "")
  {
   string nm = g_pp + id;
   if(txt == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   bool exists = (ObjectFind(0, nm) >= 0);
   if(g_panelReclaim && exists) { ObjectDelete(0, nm); exists = false; }
   if(!exists) ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, y);
   ObjectSetString (0, nm, OBJPROP_TEXT, txt);
   ObjectSetString (0, nm, OBJPROP_FONT, font == "" ? InpPanelFont : font);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, size > 0 ? size : InpPanelSize);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5001);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
                    rightAlign ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
  }
void PRow(const string id, const int x, const int y, const int w,
          const string label, const string value, const int state)
  {
   color dot = (state == 1) ? InpOkCol : (state == 0) ? InpNoCol : InpTextCol;
   PText(id + "d", x + 10, y, CharToString(108), dot, InpPanelSize + 1, false, "Wingdings");
   PText(id + "l", x + 26, y, label, InpTextCol);
   PText(id + "v", x + w - 12, y, value, InpValCol, 0, true);
   int need = 26 + EstimateTextWidth(label, InpPanelSize) + 16
              + EstimateTextWidth(value, InpPanelSize) + 20;
   if(need > g_panelMinW) g_panelMinW = need;
  }
void PSection(const string id, const int x, const int y, const int w,
              const int rh, const string title)
  {
   PRect(id + "bar", x + 1, y - 3, w - 2, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x + 10, y, title, InpSectionCol, InpPanelSize, false, "Arial Bold");
  }
void PWatermark()
  {
   string nm = g_pw + "wm";
   if(InpWatermark == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_RIGHT_LOWER);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_RIGHT_LOWER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 18);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 18);
   ObjectSetString (0, nm, OBJPROP_TEXT, InpWatermark);
   ObjectSetString (0, nm, OBJPROP_FONT, "Arial Black");
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 28);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, InpWaterCol);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| The panel. ROWS/GAPS hand-counted against the literal PRow/       |
//| PSection sequence below, same discipline as ScalpSignal_          |
//| Indicator.mq5's own DrawPanel() - re-verify by grep if this ever  |
//| changes: (ty += rh) count must equal ROWS, (// GAP) count = GAPS. |
//| Background/watermark drawn BEFORE the InpShowPanel early-return.  |
//+------------------------------------------------------------------+
void DrawPanel()
  {
   PWatermark();
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }

   g_panelReclaim = true;

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;
   int rh = InpPanelSize + 11;
   int hdr = rh + 14;

   const int ROWS = 9, GAPS = 5;
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH  = hdr + 10 + ROWS * rh + GAPS * 6 + 12;
   int guard  = 0;
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     {
      rh--; guard++;
      hdr   = rh + 14;
      bodyH = hdr + 10 + ROWS * rh + GAPS * 6 + 12;
     }
   if(g_panX < 0)
     {
      g_panX = InpPanelX;
      if(InpPanelBottom)
        {
         int ch2 = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
         g_panY = MathMax(2, ch2 - bodyH - InpPanelY);
        }
      else
         g_panY = InpPanelY;
     }
   int x = g_panX, y = g_panY;

   PRect("sh", x + 4, y + 4, w, bodyH, InpShadowCol, InpShadowCol, 0);
   PRect("bg", x, y, w, bodyH, InpPanelBg, InpPanelBg, 0);
   PRect("fl", x + 2, y + 2, w - 4, bodyH - 4, InpPanelBg, InpPanelBg, 0);
   PFrame("bd", x, y, w, bodyH, InpPanelEdge, 2);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);

   int ty = y + 9;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "VWAP READY", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   // --- a0: timeframe (1 row) ------------------------------------------
   PRow("a0", x, ty, w, "timeframe", EnumToString((ENUM_TIMEFRAMES)_Period), 1); ty += rh + 6;   // GAP 1

   // --- READINESS (section + 4 rows) -----------------------------------
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   bool spreadOK = (InpMaxSpreadPoints <= 0 || spr <= InpMaxSpreadPoints);
   double volRatio = VolumeRatioAt(1, InpVolAvgBars);
   bool haveVol = volRatio >= 0.0;
   bool volOK = haveVol && volRatio >= InpMinVolRatio;
   double slope; int trend = TrendDir(slope);
   bool overallOK = spreadOK && volOK;

   PSection("s1", x, ty, w, rh, "READINESS"); ty += rh + 6;                                       // GAP 2
   PRow("r1", x, ty, w, "spread", (string)spr + " / " + (string)InpMaxSpreadPoints, spreadOK ? 1 : 0); ty += rh;
   PRow("r2", x, ty, w, "volume",
        !haveVol ? "n/a" : DoubleToString(volRatio, 2) + "x / " + DoubleToString(InpMinVolRatio, 2) + "x",
        !haveVol ? -1 : (volOK ? 1 : 0)); ty += rh;
   PRow("r3", x, ty, w, "short-term trend",
        trend > 0 ? "UP" : trend < 0 ? "DOWN" : "flat", trend > 0 ? 1 : trend < 0 ? 0 : -1); ty += rh;
   PRow("r4", x, ty, w, "OVERALL", overallOK ? "READY" : "WAIT", overallOK ? 1 : 0); ty += rh + 6; // GAP 3

   // --- VWAP (section + 2 rows) -----------------------------------------
   double vw1 = SessionVWAP(1);
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double bU = 0.0, bL = 0.0; bool haveBand = InpShowVWAPBands && SessionVWAPBand(1, InpVWAPBandK, bU, bL);

   PSection("s2", x, ty, w, rh, "VWAP"); ty += rh + 6;                                             // GAP 4
   PRow("v1", x, ty, w, "price vs VWAP",
        vw1 <= 0.0 ? "n/a" : (c1 > vw1 ? "above" : "below"), -1); ty += rh;
   PRow("v2", x, ty, w, "price vs VWAP band",
        !haveBand ? "off" : (c1 > bU ? "above upper" : c1 < bL ? "below lower" : "inside"), -1); ty += rh + 6; // GAP 5
  }
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   UpdateVwapLine();
   if(InpShowPanel && TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      DrawPanel();
      ChartRedraw(0);
     }
   return(rates_total);
  }
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(InpShowPanel && TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      DrawPanel();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
