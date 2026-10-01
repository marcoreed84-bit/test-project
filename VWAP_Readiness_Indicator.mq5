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
//|  chart visual and as two panel rows (price vs VWAP, price vs the bands),    |
//|  purely informational. v1.01: now up to THREE independently-toggleable       |
//|  band levels (InpShowBand1/2/3, default 1.0/2.0/3.0x stdev, band 3 off by     |
//|  default), matching the convention most VWAP+bands indicators use (e.g.       |
//|  TradingView's built-in VWAP) instead of the single fixed band v1.00 shipped.  |
//|  Real M1 testing this session found NO construction built on this pattern      |
//|  (VWAP-band + stochastic reversal, wide or tight-tuned) cleared a real edge -   |
//|  see ScalpSignal_Indicator.mq5's own header RESEARCH NOTE for the numbers.       |
//|  Drawn here for the same reason: a discretionary visual reference, never a        |
//|  claimed signal.                                                                   |
//+------------------------------------------------------------------+
#property copyright "VWAP_Readiness"
#property version   "1.03"
#property description "Standalone VWAP + volume/spread/trend readiness panel (no trade execution)"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0
#property strict

//--- VWAP visuals ------------------------------------------------------
input bool     InpShowVWAP       = true;         // Draw the session VWAP line
input color    InpColVWAP        = C'0,255,255';
input bool     InpShowVWAPBands  = true;         // Master switch for all three band levels below
//--- three deviation levels, same convention as TradingView's own VWAP+bands
//--- indicator (1/2/3 standard deviations) - band 3 off by default since most
//--- charts only need the inner two to stay readable; turn it on if you want it.
input bool     InpShowBand1      = true;         // +/- InpVWAPBandK1 x stdev (innermost)
input double   InpVWAPBandK1     = 1.0;
input color    InpColBand1       = C'0,150,150';
input bool     InpShowBand2      = true;         // +/- InpVWAPBandK2 x stdev
input double   InpVWAPBandK2     = 2.0;
input color    InpColBand2       = C'140,90,0';
input bool     InpShowBand3      = false;        // +/- InpVWAPBandK3 x stdev (outermost)
input double   InpVWAPBandK3     = 3.0;
input color    InpColBand3       = C'120,0,120';
input bool     InpShowLineLabels = true;         // Caption each drawn line at the chart's live edge (same idiom as Meridian_EA.mq5's MA/VWAP labels)

//--- Volume readiness ----------------------------------------------------
input int      InpVolAvgBars     = 100;          // Bars used for the volume average (Aurelius_EA.mq5's own real default)
input double   InpMinVolRatio    = 1.25;         // Min current-bar volume vs that average to call it "ready" (Aurelius's own real default)

//--- Spread readiness (live only - see header) ---------------------------
input int      InpMaxSpreadPoints = 60;          // Max acceptable live spread, points (Aurelius_EA.mq5's own real default)

//--- Short-term trend ------------------------------------------------------
input int      InpTrendMAPeriod        = 21;     // EMA period used for the trend slope
input int      InpTrendSlopeBars       = 10;     // Bars back the slope is measured over
input double   InpTrendSlopeThresholdATR = 0.10; // Min |slope| (x ATR) to call it up/down rather than "flat"

//--- Higher-timeframe trend (same EMA-slope-vs-ATR method as the chart's own
//--- trend above, just run on other timeframes too - default ladder M5/M15/H1,
//--- change any slot to whatever timeframes you actually trade off) ---------
input bool            InpShowHTF1 = true;  input ENUM_TIMEFRAMES InpHTF1 = PERIOD_M5;
input bool            InpShowHTF2 = true;  input ENUM_TIMEFRAMES InpHTF2 = PERIOD_M15;
input bool            InpShowHTF3 = true;  input ENUM_TIMEFRAMES InpHTF3 = PERIOD_H1;

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
string   g_pl = "VWRL_";   // VWAP/band end-of-line labels
string   g_pw = "VWRW_";   // watermark
int      g_panelMinW = 0;
bool     g_panelReclaim = true;
int      g_panX = -1, g_panY = -1;
datetime g_lastPanelDraw = 0;
int      hTrendMA = INVALID_HANDLE;
int      hATR     = INVALID_HANDLE;
//--- higher-timeframe trend handles, parallel to InpHTF1/2/3 above - each
//--- pair is only created if its InpShowHTFn is true (no point paying for
//--- a handle nobody asked to see)
int      hHTFMa[3] = {INVALID_HANDLE, INVALID_HANDLE, INVALID_HANDLE};
int      hHTFAtr[3] = {INVALID_HANDLE, INVALID_HANDLE, INVALID_HANDLE};
datetime g_lastVwapBarTime = 0;
datetime g_lastCacheBarTime = 0;

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
   bool htfShow[3] = {InpShowHTF1, InpShowHTF2, InpShowHTF3};
   ENUM_TIMEFRAMES htfTf[3] = {InpHTF1, InpHTF2, InpHTF3};
   for(int i = 0; i < 3; i++)
     {
      if(!htfShow[i]) continue;
      hHTFMa[i]  = iMA(_Symbol, htfTf[i], InpTrendMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
      hHTFAtr[i] = iATR(_Symbol, htfTf[i], 14);
      if(hHTFMa[i] == INVALID_HANDLE || hHTFAtr[i] == INVALID_HANDLE)
        {
         PrintFormat("VWAP_Readiness_Indicator: failed to create the HTF%d (%s) handle. Error %d",
                     i + 1, EnumToString(htfTf[i]), GetLastError());
         return(INIT_FAILED);
        }
     }
   IndicatorSetString(INDICATOR_SHORTNAME, "VWAP Readiness (" + _Symbol + " " + EnumToString((ENUM_TIMEFRAMES)_Period) + ")");
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   for(int i = 0; i < 3; i++)
     {
      if(hHTFMa[i] != INVALID_HANDLE) IndicatorRelease(hHTFMa[i]);
      if(hHTFAtr[i] != INVALID_HANDLE) IndicatorRelease(hHTFAtr[i]);
     }
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pm);
   ObjectsDeleteAll(0, g_pw);
   ObjectsDeleteAll(0, g_pl);
   Comment("");
  }
//+------------------------------------------------------------------+
//| v1.03 BUG FIX: v1.00-v1.02's SessionVWAP()/SessionVWAPBand() each |
//| re-walked history from scratch on every call, capped at a         |
//| hardcoded 400 bars (CopyTime(..., shift, 400, ...)). Harmless on   |
//| a slow timeframe, but on M1 (up to ~1440 bars/day) that cap is hit  |
//| well before the session's actual start once more than ~6.7 hours    |
//| have elapsed - the loop just ran out of copied bars and silently     |
//| returned a "last 400 bars" average instead of a true SESSION VWAP,    |
//| which is why it diverged from VWAP_Bands.mq5 (no such cap, and the     |
//| one found to be correct). Fixed by computing the real cumulative        |
//| VWAP/stdev for TODAY's bars in one pass (same proven construction as     |
//| VWAP_Bands.mq5) into a cache, rebuilt once per new closed bar -           |
//| SessionVWAP()/SessionVWAPBand() are now just cheap lookups into it.        |
//+------------------------------------------------------------------+
double g_cacheVwap[];
double g_cacheStdev[];
int    g_cacheN = 0;   // g_cacheVwap[0..g_cacheN-1] valid; index 0 = shift 1

void RebuildSessionVwapCache()
  {
   g_cacheN = 0;
   int maxBars = Bars(_Symbol, PERIOD_CURRENT);
   if(maxBars < 2) return;
   int s = 2;
   while(s < maxBars && !DifferentSession(s, 1)) s++;   // s = first shift OUTSIDE today
   int todayBars = s - 1;                               // shifts 1..todayBars are today
   if(todayBars < 1) return;

   datetime tArr[]; double hArr[], lArr[], cArr[]; long vArr[];
   ArraySetAsSeries(tArr, true); ArraySetAsSeries(hArr, true);
   ArraySetAsSeries(lArr, true); ArraySetAsSeries(cArr, true);
   ArraySetAsSeries(vArr, true);
   int got = CopyTime(_Symbol, PERIOD_CURRENT, 1, todayBars, tArr);
   if(got <= 0) return;
   if(CopyHigh(_Symbol, PERIOD_CURRENT, 1, got, hArr) <= 0) return;
   if(CopyLow(_Symbol, PERIOD_CURRENT, 1, got, lArr) <= 0) return;
   if(CopyClose(_Symbol, PERIOD_CURRENT, 1, got, cArr) <= 0) return;
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, 1, got, vArr) <= 0) return;

   ArrayResize(g_cacheVwap, got);
   ArrayResize(g_cacheStdev, got);
   double cumPV = 0.0, cumV = 0.0, cumPPV = 0.0;
   // arrays are series (index 0 = shift 1, most recent); walk OLDEST
   // (index got-1) to NEWEST (index 0) to accumulate chronologically,
   // exactly like VWAP_Bands.mq5's own forward day-reset loop.
   for(int i = got - 1; i >= 0; i--)
     {
      double typical = (hArr[i] + lArr[i] + cArr[i]) / 3.0;
      double vol = (double)vArr[i];
      cumPV  += typical * vol;
      cumV   += vol;
      cumPPV += typical * typical * vol;
      double vwap = (cumV > 0.0) ? cumPV / cumV : 0.0;
      double variance = (cumV > 0.0) ? (cumPPV / cumV - vwap * vwap) : 0.0;
      g_cacheVwap[i]  = vwap;
      g_cacheStdev[i] = MathSqrt(MathMax(variance, 0.0));
     }
   g_cacheN = got;
  }
//+------------------------------------------------------------------+
double SessionVWAP(const int shift)
  {
   int idx = shift - 1;
   if(idx < 0 || idx >= g_cacheN || g_cacheVwap[idx] <= 0.0) return(0.0);
   return(g_cacheVwap[idx]);
  }
//+------------------------------------------------------------------+
bool SessionVWAPBand(const int shift, const double k, double &upper, double &lower)
  {
   upper = 0.0; lower = 0.0;
   int idx = shift - 1;
   if(idx < 0 || idx >= g_cacheN || g_cacheVwap[idx] <= 0.0) return(false);
   upper = g_cacheVwap[idx] + k * g_cacheStdev[idx];
   lower = g_cacheVwap[idx] - k * g_cacheStdev[idx];
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
int TrendDirH(const int handleMA, const int handleATR, double &slopeOut)
  {
   slopeOut = 0.0;
   if(handleMA == INVALID_HANDLE || handleATR == INVALID_HANDLE) return(0);
   double maNow[], maPast[], atrNow[];
   ArraySetAsSeries(maNow, true); ArraySetAsSeries(maPast, true); ArraySetAsSeries(atrNow, true);
   if(CopyBuffer(handleMA, 0, 1, 1, maNow) < 1) return(0);
   if(CopyBuffer(handleMA, 0, 1 + InpTrendSlopeBars, 1, maPast) < 1) return(0);
   if(CopyBuffer(handleATR, 0, 1, 1, atrNow) < 1) return(0);
   if(atrNow[0] <= 0.0 || maNow[0] == EMPTY_VALUE || maPast[0] == EMPTY_VALUE) return(0);
   double slope = (maNow[0] - maPast[0]) / atrNow[0];
   slopeOut = slope;
   if(slope >= InpTrendSlopeThresholdATR)  return(1);
   if(slope <= -InpTrendSlopeThresholdATR) return(-1);
   return(0);
  }
int TrendDir(double &slopeOut) { return TrendDirH(hTrendMA, hATR, slopeOut); }
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
//+------------------------------------------------------------------+
//| End-of-line captions - same OBJ_TEXT idiom as Meridian_EA.mq5's    |
//| DrawChartLabel()/DeleteChartLabel(), so every drawn line says what   |
//| it is at the chart's live edge instead of relying on color alone.     |
//+------------------------------------------------------------------+
bool DrawChartLabel(const string tag, const datetime t, const double price,
                     const string text, const color col)
  {
   string nm = g_pl + tag;
   if(text == "" || t <= 0 || price <= 0.0)
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return(false); }
   bool created = false;
   if(ObjectFind(0, nm) < 0)
     { ObjectCreate(0, nm, OBJ_TEXT, 0, t, price); created = true; }
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetString (0, nm, OBJPROP_TEXT, text);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 8);
   ObjectSetString (0, nm, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   return(created);
  }
void DeleteChartLabel(const string tag)
  {
   string nm = g_pl + tag;
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
  }
//+------------------------------------------------------------------+
//| Labels VWAP + each enabled band's upper/lower line at its latest   |
//| (shift=1) value, anchored at the chart's live edge (TimeCurrent()) -  |
//| called once per new bar and once per second from OnTimer() so the      |
//| labels keep tracking the live edge as time passes between bar closes.   |
//+------------------------------------------------------------------+
void UpdateVwapLabels()
  {
   if(!InpShowLineLabels)
     {
      DeleteChartLabel("vwap");
      for(int i = 1; i <= 3; i++) { DeleteChartLabel("bU"+IntegerToString(i)); DeleteChartLabel("bL"+IntegerToString(i)); }
      return;
     }
   datetime tLive = TimeCurrent();
   if(InpShowVWAP)
     {
      double vw = SessionVWAP(1);
      if(vw > 0.0) DrawChartLabel("vwap", tLive, vw, "  VWAP " + DoubleToString(vw, _Digits), InpColVWAP);
      else         DeleteChartLabel("vwap");
     }
   bool show[3] = {InpShowBand1, InpShowBand2, InpShowBand3};
   double kArr[3] = {InpVWAPBandK1, InpVWAPBandK2, InpVWAPBandK3};
   color colArr[3] = {InpColBand1, InpColBand2, InpColBand3};
   for(int i = 0; i < 3; i++)
     {
      string tagU = "bU" + IntegerToString(i+1), tagL = "bL" + IntegerToString(i+1);
      if(!InpShowVWAPBands || !show[i])
        { DeleteChartLabel(tagU); DeleteChartLabel(tagL); continue; }
      double u, l;
      if(SessionVWAPBand(1, kArr[i], u, l))
        {
         DrawChartLabel(tagU, tLive, u, "  Band " + IntegerToString(i+1) + " " + DoubleToString(u, _Digits), colArr[i]);
         DrawChartLabel(tagL, tLive, l, "  Band " + IntegerToString(i+1) + " " + DoubleToString(l, _Digits), colArr[i]);
        }
      else
        { DeleteChartLabel(tagU); DeleteChartLabel(tagL); }
     }
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
//| Draws one bar's VWAP/band segment, shiftOld->shiftNew (both real   |
//| shifts, not hardcoded) - used both for the live one-new-bar update  |
//| and for the backfill walk below.                                    |
//+------------------------------------------------------------------+
void DrawVwapSegment(const int shiftOld, const int shiftNew)
  {
   datetime tOld = iTime(_Symbol, PERIOD_CURRENT, shiftOld);
   datetime tNew = iTime(_Symbol, PERIOD_CURRENT, shiftNew);
   if(tOld == 0 || tNew == 0) return;
   if(InpShowVWAP)
     {
      double vA = SessionVWAP(shiftOld), vB = SessionVWAP(shiftNew);
      if(vA > 0.0 && vB > 0.0) DrawSeg("vwap", tOld, vA, tNew, vB, InpColVWAP);
     }
   if(InpShowVWAPBands)
     {
      if(InpShowBand1) DrawBandPair(1, shiftOld, shiftNew, InpVWAPBandK1, InpColBand1);
      if(InpShowBand2) DrawBandPair(2, shiftOld, shiftNew, InpVWAPBandK2, InpColBand2);
      if(InpShowBand3) DrawBandPair(3, shiftOld, shiftNew, InpVWAPBandK3, InpColBand3);
     }
  }
//+------------------------------------------------------------------+
//| Draws one band level's upper+lower segment pair at real shifts.    |
//| levelTag keeps each level's chart objects independent so band1/2/3  |
//| don't overwrite each other (same per-bar-segment idiom as           |
//| DrawSeg() above). PREVIOUSLY (v1.00/v1.01) this always read shift   |
//| 2/1 regardless of which bar times were passed in - harmless while   |
//| only ever called for the newest bar, but wrong for backfilling      |
//| older bars, so fixed alongside the backfill below.                  |
//+------------------------------------------------------------------+
void DrawBandPair(const int levelTag, const int shiftOld, const int shiftNew,
                   const double k, const color col)
  {
   datetime tOld = iTime(_Symbol, PERIOD_CURRENT, shiftOld);
   datetime tNew = iTime(_Symbol, PERIOD_CURRENT, shiftNew);
   if(tOld == 0 || tNew == 0) return;
   double uA, lA, uB, lB;
   if(!SessionVWAPBand(shiftOld, k, uA, lA) || !SessionVWAPBand(shiftNew, k, uB, lB)) return;
   string tagU = "vwapU" + IntegerToString(levelTag);
   string tagL = "vwapL" + IntegerToString(levelTag);
   DrawSeg(tagU, tOld, uA, tNew, uB, col);
   DrawSeg(tagL, tOld, lA, tNew, lB, col);
  }
//+------------------------------------------------------------------+
//| v1.01 bug fix: v1.00 only ever drew the newest closed bar's         |
//| segment, so the line only grew forward from whenever the indicator   |
//| was attached - attach mid-session and the earlier part of today's     |
//| VWAP never appeared, looking like an "incomplete" line. Now backfills  |
//| the WHOLE current session (VWAP is session-anchored anyway, so there's  |
//| no real data before today's start regardless) the first time it runs,   |
//| then falls back to the cheap one-new-bar-per-call update after that.     |
//+------------------------------------------------------------------+
void UpdateVwapLine()
  {
   datetime bt1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(bt1 == 0) return;
   if(g_lastVwapBarTime == 0)
     {
      int maxBars = Bars(_Symbol, PERIOD_CURRENT);
      int s = 2;
      while(s < maxBars && !DifferentSession(s, 1)) s++;   // walk to today's session start
      for(int shift = s - 1; shift >= 2; shift--)
         DrawVwapSegment(shift, shift - 1);
      g_lastVwapBarTime = bt1;
      return;
     }
   if(bt1 == g_lastVwapBarTime) return;
   g_lastVwapBarTime = bt1;
   if(DifferentSession(2, 1)) return;
   DrawVwapSegment(2, 1);
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

   // 9 rows/5 gaps fixed + up to 4 rows/2 gaps for the HIGHER TIMEFRAMES
   // section (1 header row + up to 3 HTF rows, sized for the worst case so
   // it never overflows if all three InpShowHTFn are on - see DrawPanel()'s
   // own header comment, this must track the real ty+=/GAP count below)
   const int ROWS = 13, GAPS = 7;
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

   // --- Higher-timeframe trend (section + up to 3 rows) -------------------
   bool htfShowArr[3] = {InpShowHTF1, InpShowHTF2, InpShowHTF3};
   ENUM_TIMEFRAMES htfTfArr[3] = {InpHTF1, InpHTF2, InpHTF3};
   bool anyHtf = InpShowHTF1 || InpShowHTF2 || InpShowHTF3;
   if(anyHtf)
     {
      PSection("sh", x, ty, w, rh, "HIGHER TIMEFRAMES"); ty += rh + 6;
      for(int i = 0; i < 3; i++)
        {
         if(!htfShowArr[i]) continue;
         double hSlope; int hTrend = TrendDirH(hHTFMa[i], hHTFAtr[i], hSlope);
         PRow("ht" + IntegerToString(i), x, ty, w, EnumToString(htfTfArr[i]),
              hTrend > 0 ? "UP" : hTrend < 0 ? "DOWN" : "flat", hTrend > 0 ? 1 : hTrend < 0 ? 0 : -1);
         ty += rh;
        }
      ty += 6;
     }

   // --- VWAP (section + 2 rows) -----------------------------------------
   double vw1 = SessionVWAP(1);
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);

   PSection("s2", x, ty, w, rh, "VWAP"); ty += rh + 6;                                             // GAP 4
   PRow("v1", x, ty, w, "price vs VWAP",
        vw1 <= 0.0 ? "n/a" : (c1 > vw1 ? "above" : "below"), -1); ty += rh;
   PRow("v2", x, ty, w, "price vs bands", VwapBandZoneText(c1), -1); ty += rh + 6; // GAP 5
  }
//+------------------------------------------------------------------+
//| Reports which band zone price is in, checked outermost-enabled-   |
//| level inward first so e.g. "beyond band 3" takes priority over    |
//| "beyond band 1" when band 3 is also on.                           |
//+------------------------------------------------------------------+
string VwapBandZoneText(const double c1)
  {
   if(!InpShowVWAPBands) return("off");
   double u, l;
   if(InpShowBand3 && SessionVWAPBand(1, InpVWAPBandK3, u, l))
     { if(c1 > u) return("above band 3"); if(c1 < l) return("below band 3"); }
   if(InpShowBand2 && SessionVWAPBand(1, InpVWAPBandK2, u, l))
     { if(c1 > u) return("above band 2"); if(c1 < l) return("below band 2"); }
   if(InpShowBand1 && SessionVWAPBand(1, InpVWAPBandK1, u, l))
     { if(c1 > u) return("above band 1"); if(c1 < l) return("below band 1"); }
   if(InpShowBand1 || InpShowBand2 || InpShowBand3) return("inside");
   return("off");
  }
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   datetime bt1Now = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(bt1Now != 0 && bt1Now != g_lastCacheBarTime)
     {
      g_lastCacheBarTime = bt1Now;
      RebuildSessionVwapCache();
     }
   UpdateVwapLine();
   UpdateVwapLabels();
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
   if(TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      UpdateVwapLabels();   // keeps labels tracking the live edge between bar closes
      if(InpShowPanel) DrawPanel();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
