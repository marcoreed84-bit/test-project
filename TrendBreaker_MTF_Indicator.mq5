//+------------------------------------------------------------------+
//|                                  TrendBreaker_MTF_Indicator.mq5  |
//|                                                                  |
//|  WHAT THIS IS: a chart-window VISUAL indicator - NOT an Expert   |
//|  Advisor. ZERO trade-execution code (no order sending, no trade  |
//|  class, no position handling - nothing that can touch an         |
//|  account). It draws automatically-built trendlines for the chart |
//|  timeframe AND every higher timeframe, plus a panel.             |
//|                                                                  |
//|  STATUS - PORTED, NOT VALIDATED: every construction rule below   |
//|  is a faithful port of the user's own written trendline method   |
//|  ("Source 1": 3-touch rule, BOS anchors, angle rule, fan, wick/  |
//|  body, liquidity sweep, drift-to-range) and of the Trend Breaker |
//|  Strategy Guide's MACD/SMA/EMA confirmation stack ("Source 2",   |
//|  tradingstrategyguides.com). Neither has been real-data tested   |
//|  in this project the way the EAs' own inputs have. No edge is    |
//|  claimed anywhere. The panel is informational; nothing gates.    |
//|                                                                  |
//|  TIMEFRAME CASCADE (the user's own rule): on any chart, draw the |
//|  chart timeframe's own lines + every HIGHER timeframe's lines,   |
//|  never a lower one. H4 chart -> MN1/W1/D1/H4. H1 chart ->        |
//|  MN1..H1. M15 chart -> MN1..M15 (no M5, no M1). A non-standard   |
//|  chart period (M30, H2, ...) gets its own extra slot so its own  |
//|  lines are still drawn. Each timeframe's lines are built from    |
//|  THAT timeframe's own bars (CopyRates with an explicit TF), never |
//|  resampled from the chart's bars. The chart objects are placed at |
//|  the source bar's open time; on a lower-TF chart the true wick    |
//|  sat somewhere inside that source bar, so the anchor is exact in  |
//|  price and bar-exact (not intrabar-exact) in time.                 |
//|                                                                  |
//|  SWING DETECTION (web-grounded, not invented):                    |
//|   1. N-bar pivot: a bar whose high is above the N bars to its left |
//|      (strict) and not below the N bars to its right - the         |
//|      "extremum" definition of MQL5 Code Base AutoTrendLines         |
//|      (mql5.com/en/code/1220), a generalised Williams fractal        |
//|      (N=2 is iFractals; mql5.com/en/articles/1201).                  |
//|   2. ZigZag alternation pass: consecutive same-type pivots keep     |
//|      only the more extreme one (ZigZag "Backstep"), and an opposite  |
//|      pivot is accepted only if the leg is >= InpSwingMinATR x ATR    |
//|      (ZigZag "Deviation", ATR-scaled instead of fixed points so it   |
//|      works on every TF). Alternation is required because Source 1's  |
//|      BOS test needs an unambiguous "previous swing low" for every    |
//|      swing high.                                                     |
//|   3. Line fitting: every BOS-valid anchor pair is tried and scored  |
//|      (exhaustive pair search + ATR-tolerance touch counting, as in   |
//|      pytrendline, github.com/ednunezg/pytrendline, and the ATR       |
//|      touch/pierce-tolerance split used by TradingView auto-trendline |
//|      scripts). Only the lines that pass Source 1's rules are kept.   |
//|                                                                  |
//|  SOURCE 1 RULES, AS IMPLEMENTED:                                  |
//|   - 3-touch: 2 touches = tentative (dotted, width 1); the 3rd touch  |
//|     (a bar reaching within InpTouchTolATR of the line while closing  |
//|     on the correct side, >= N bars from the previous touch) makes it |
//|     VALID (solid). Only VALID lines set a timeframe's trend readout. |
//|   - BOS: a swing high anchors a down line only if price, before the  |
//|     next swing high, traded below the swing low that preceded it     |
//|     (mirror for lows). The first swing in the window has no prior    |
//|     swing to break, so it cannot be verified and is REJECTED, not    |
//|     assumed valid.                                                   |
//|   - Wick vs body: anchors default to wicks. If an anchor bar's wick  |
//|     alone is > InpSpikeWickATR x ATR (the guide's "single news spike")|
//|     the WHOLE line switches to body extremes for its life - anchors, |
//|     touches, pierces - so it stays internally consistent. Macro TFs  |
//|     (MN1/W1/D1) use bodies from the start (InpMacroBodies): the      |
//|     guide builds them on a close-only line chart, then fits a "zone  |
//|     of best fit" through bodies that may cut minor wicks.            |
//|   - Liquidity sweep: a VALID line pierced (wick > InpPierceTolATR,   |
//|     or 1-2 closes beyond) that then closes back inside is NOT       |
//|     deleted. Its second anchor moves to the sweep extreme, it is     |
//|     tagged LIQ, and the extreme gets a marker. Because the line      |
//|     pivots outward about anchor 1, every bar that was inside stays   |
//|     inside. A tentative draft that gets pierced is simply retired.   |
//|   - Break: BREAK_CONFIRM_CLOSES (3) consecutive closes beyond the    |
//|     line. The number 3 is Source 2's own "wait for 3 candles to     |
//|     close beyond the trendline". That also lines up with Source 1's |
//|     "closes back inside within 1-2 candles" = sweep. The two sources |
//|     agree, so one constant serves both.                              |
//|   - Drift-to-range: when a VALID line is crossed by 3 closes, the    |
//|     last InpDriftBars bars are tested. Net close displacement        |
//|     <= InpDriftMaxNetATR x ATR, AND no break-direction candle body   |
//|     > InpDriftMaxBodyATR x ATR ("aggressive opposing candles"), AND  |
//|     peak tick volume <= InpDriftMaxVolRatio x its prior average      |
//|     ("explosive volume"). All three true = a DRIFT: the diagonal is  |
//|     retired and a horizontal box (MSG_Trader_EA.mq5's               |
//|     DrawSessionBox() idiom) is drawn over that window instead. If   |
//|     any is false it is a real BREAK and the line is removed.         |
//|   - Fan: on non-macro TFs, while the primary line is VALID, a later |
//|     line (both anchors at/after the primary's 2nd anchor), at least  |
//|     InpFanSteepen x steeper and starting >= InpFanMinGapATR beyond   |
//|     the primary ("accelerating away"), is drawn as fan 2; the same   |
//|     test against fan 2 gives fan 3. Macro lines get no fans: the     |
//|     guide calls them fixed "absolute walls".                         |
//|   - Macro freeze: with InpMacroFreezeWeekly, D1 lines are recomputed |
//|     once per W1 bar (W1/MN1 already roll no more than weekly): "they |
//|     do not change throughout the week". Live distances to them are   |
//|     still re-measured every second.                                  |
//|   - Source 1 Step 3 says LTF (M15..M1) standalone lines are noisy.   |
//|     The user explicitly asked to SEE them, so they are drawn, tagged |
//|     "LTF" on the panel, and their breaks are used for Step 3's      |
//|     trigger readout (LTF counter-line break near a validated MTF/HTF |
//|     line). That readout is display-only, never a gate.              |
//|                                                                  |
//|  ANGLE - A DISCLOSED DESIGN DECISION. MT5 has no fixed degrees:   |
//|  the drawn angle depends on zoom, scroll and autoscale. So there  |
//|  are two numbers, each labelled for what it really is:            |
//|   (a) "NNdeg" on every line label is the REAL ON-SCREEN angle. It  |
//|       comes from ChartTimePriceToXY() on the drawn object's        |
//|       rendered values across its visible on-screen span, so it uses|
//|       the chart's actual live price-per-pixel and bar-per-pixel    |
//|       scale. It is re-measured on every CHARTEVENT_CHART_CHANGE    |
//|       (zoom/scroll/resize) and every second (autoscale moves as    |
//|       price moves). It is exactly what the eye sees, so it changes |
//|       when you zoom - that is the honest behaviour, not a bug.     |
//|   (b) The reliable/steep CLASSIFICATION, which drives line style,  |
//|       the panel, and the "steep line broke -> back to the higher-TF|
//|       line" rule, must not flip when the user zooms. It uses the   |
//|       scale-invariant slope in ATR per bar of the line's own TF    |
//|       (|slope| / mean ATR over the anchor span) - the same ATR-    |
//|       normalised slope convention as the EAs' SlopeATR/            |
//|       InpMinSlopeATR. It is shown as "x.xx ATR/bar", never as      |
//|       degrees. The defaults are the guide's 30/45/60 degrees       |
//|       translated at a stated reference geometry of 5.5 bar-widths  |
//|       per 1 ATR of height: tan(deg)/5.5 = 0.105 / 0.182 / 0.315.   |
//|       5.5 was MEASURED on this project's real GOLD bars, not       |
//|       assumed. Take an auto-scaled ~1300x600 px plot at 8 px per   |
//|       bar (~160 bars visible). The median high-low range of any    |
//|       160-bar window is 13.2 ATR on H4 and 13.4 ATR on M5, so one  |
//|       ATR is (600/13.2)/(1300/160) = 5.6 / 5.5 bar-widths tall.    |
//|       The interquartile range is 4.5-6.9, i.e. roughly +/-7deg     |
//|       around 45deg, and ~80 visible bars gives ~4.1. So this is a  |
//|       calibration, not a law. The thresholds are inputs, and the   |
//|       live on-screen degrees sit next to them on every label.      |
//|                                                                  |
//|  STALE-OBJECT REMOVAL: every chart object is named               |
//|  TBML_<TF>_<U|D><role>_<part>. Each redraw pass records the names |
//|  it (re)drew; anything else with the TBML_ prefix is deleted in   |
//|  the same pass. That removes broken lines, diagonals replaced by  |
//|  a drift box, fans that no longer qualify, lines out of play      |
//|  (> InpMaxDistATR away), and any TF outside the cascade.          |
//|                                                                  |
//|  SOURCE 2 STACK (chart TF only, context - never a gate, same      |
//|  discipline as ScalpSignal_Indicator.mq5's MACD row): MACD(12,26,9)|
//|  with an EMA signal line, computed here because MT5's built-in    |
//|  iMACD uses an SMA signal line, unlike the guide's standard MACD; |
//|  SMA(8) vs EMA(20); both crossing together = the guide's "trend   |
//|  is breaking".                                                    |
//|                                                                  |
//|  VOLUME / SPREAD: VolumeRatioAt() copied verbatim from            |
//|  VWAP_Readiness_Indicator.mq5 (Aurelius's real construction and   |
//|  defaults). Spread is LIVE-ONLY vs InpMaxSpreadPoints, with the   |
//|  same disclosed limitation as both existing indicators: MT5 bar   |
//|  history has no reliable per-bar spread.                          |
//+------------------------------------------------------------------+
#property copyright "TrendBreaker_MTF"
#property version   "1.00"
#property description "MTF cascading auto-trendlines (3-touch/BOS/angle/fan/sweep/drift) + trend/volume/spread panel (no trade execution)"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0
#property strict

#define NSLOT                 9    // 8 standard TFs + 1 slot for a non-standard chart period
#define TOUCHES_TO_VALIDATE   3    // Source 1: "Touch 3: Validates the line"
#define BREAK_CONFIRM_CLOSES  3    // Source 2 step 3.4; 1-2 closes then back inside = Source 1 sweep

#define ST_TENT    0
#define ST_VALID   1
#define ST_BROKEN  2
#define ST_DRIFT   3

#define DC_NONE    0
#define DC_UP      1
#define DC_DN     -1
#define DC_WEDGE   2
#define DC_RANGE   3
#define DC_TOHTF   4

#define ROLE_PRIMARY 1
#define ROLE_FAN2    2
#define ROLE_FAN3    3
#define ROLE_BOX     9

//--- Timeframe cascade -------------------------------------------------
input group "=== Timeframe cascade (chart TF + every HIGHER TF, never lower) ==="
input bool     InpShowMN1 = true;
input bool     InpShowW1  = true;
input bool     InpShowD1  = true;
input bool     InpShowH4  = true;
input bool     InpShowH1  = true;
input bool     InpShowM15 = true;
input bool     InpShowM5  = true;
input bool     InpShowM1  = true;

input group "=== Per-timeframe neon colours (line, label, panel row) ==="
input color    InpColMN1    = C'255,49,49';     // neon red
input color    InpColW1     = C'191,64,255';    // electric purple
input color    InpColD1     = C'255,20,147';    // neon pink
input color    InpColH4     = C'0,255,255';     // neon cyan
input color    InpColH1     = C'57,255,20';     // neon green
input color    InpColM15    = C'255,196,84';    // project amber
input color    InpColM5     = C'255,120,0';     // neon orange
input color    InpColM1     = C'77,121,255';    // neon blue
input color    InpColCustom = C'230,230,250';   // non-standard chart period (M30, H2, ...)
input color    InpColLiquidity = C'255,255,0';  // liquidity-sweep marker (Source 1 Phase 3)
input int      InpLabelSize = 8;

input group "=== Swing / pivot detection ==="
input int      InpLookbackBars  = 300;          // Bars of history per timeframe
input int      InpPivotStrength = 5;            // N bars each side (N-bar fractal; Williams fractal = 2)
input double   InpSwingMinATR   = 1.0;          // ZigZag "deviation": min swing leg, x ATR
input int      InpATRPeriod     = 14;           // SMA-of-true-range, same definition as MT5's iATR

input group "=== Line validation (Source 1 Phase 1) ==="
input double   InpTouchTolATR   = 0.25;         // A bar within this of the line (x ATR) counts as a touch
input double   InpPierceTolATR  = 0.35;         // Wick beyond the line by more than this = a pierce
input double   InpBreakTolATR   = 0.10;         // Close beyond the line by more than this = a close beyond
input double   InpMaxDistATR    = 10.0;         // Line further than this from price (x its TF's ATR) = out of play, removed

input group "=== Angle classification (ATR-normalised slope - see header) ==="
input double   InpSlopeReliableLoATR = 0.105;   // ~30deg at the reference geometry (tan30/5.5)
input double   InpSlopeReliableHiATR = 0.182;   // ~45deg (tan45/5.5)
input double   InpSlopeSteepATR      = 0.315;   // ~60deg (tan60/5.5): above = unsustainable per Source 1

input group "=== Fan / wick-body / macro (Source 1 Phase 2-3) ==="
input bool     InpShowFans        = true;
input double   InpFanSteepen      = 1.30;       // Fan line must be >= this x steeper than the one before it
input double   InpFanMinGapATR    = 0.50;       // ...and start at least this far beyond it (accelerating away)
input double   InpSpikeWickATR    = 1.50;       // Anchor wick longer than this (x ATR) = news spike -> body mode
input bool     InpMacroBodies     = true;       // MN1/W1/D1 built on bodies (guide's close-line + body best-fit)
input bool     InpMacroFreezeWeekly = true;     // MN1/W1/D1 lines recomputed once per week only

input group "=== Drift-to-range (Source 1 Phase 3) ==="
input int      InpDriftBars        = 10;        // Window tested when a valid line is crossed
input double   InpDriftMaxNetATR   = 1.00;      // Max net close displacement over the window, x ATR
input double   InpDriftMaxBodyATR  = 1.00;      // Max break-direction candle body, x ATR
input double   InpDriftMaxVolRatio = 1.50;      // Max tick volume vs its prior 50-bar average
input int      InpBoxKeepBars      = 60;        // Keep a drift box this many source-TF bars after it forms
input int      InpBoxExtendBars    = 20;        // Chart bars the box projects to the right of now

input group "=== Source 2 confirmation stack (context only, never a gate) ==="
input int      InpMacdFast     = 12;
input int      InpMacdSlow     = 26;
input int      InpMacdSignal   = 9;
input int      InpSmaPeriod    = 8;
input int      InpEmaPeriod    = 20;
input int      InpCrossLookback = 10;           // A cross this many bars ago or fewer counts as "fresh"

input group "=== LTF entry trigger (Source 1 Phase 2 Step 3, context only) ==="
input double   InpApproachATR  = 2.0;           // Price within this (x chart ATR) of a valid MTF/HTF line = approaching
input int      InpTriggerBars  = 5;             // An LTF counter-line break this recent counts

input group "=== Readiness ==="
input int      InpVolAvgBars      = 100;        // Bars used for the volume average (Aurelius_EA.mq5's own real default)
input double   InpMinVolRatio     = 1.25;       // Min current-bar volume vs that average (Aurelius's own real default)
input int      InpMaxSpreadPoints = 60;         // Max acceptable live spread, points (Aurelius_EA.mq5's own real default)

input group "=== Panel ==="
input bool     InpShowPanel   = true;
input int      InpPanelDrag   = 1;              // 0 = locked, 1 = draggable
input int      InpPanelX      = 12;
input int      InpPanelY      = 30;             // From the bottom edge when InpPanelBottom=true
input bool     InpPanelBottom = true;
input int      InpPanelW      = 290;
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
input string   InpWatermark   = "TREND MTF";
input color    InpWaterCol    = C'46,38,24';

//+------------------------------------------------------------------+
struct TLine
  {
   int      slot;       // timeframe slot
   int      dir;        // +1 support (up trendline, swing lows), -1 resistance (down trendline, swing highs)
   int      role;       // ROLE_* once selected for drawing
   int      ia, ib;     // anchor bar indices in the compute pass's rates array (valid only inside that pass)
   int      iret;       // retirement bar index (same caveat)
   datetime t1, t2;
   double   p1, p2;
   double   slope;      // price per source-TF bar
   double   slopeATR;   // |slope| / mean ATR over the anchor span - the scale-invariant angle measure
   int      state;
   int      touches;
   bool     body;       // body-extreme mode for this line's whole life
   bool     liq;        // re-anchored by a liquidity sweep
   bool     pending;    // 1-2 closes currently beyond a valid line (sweep-or-break not yet decided)
   datetime sweepT;
   double   sweepP;
   datetime lastTouchT;
   double   meanErr;    // mean |touch distance| in ATR (pytrendline-style fit quality, tie-break only)
   datetime retireT;
   datetime boxT1;
   double   boxHi, boxLo;
  };

struct TFSum
  {
   bool     ok;
   string   status;
   datetime calcKey;
   double   atr;
   int      dirCode;
   bool     dirTent;
   bool     dirFromBreak;
   datetime anyBrkT[2];  // [0] = latest broken support (up) line, [1] = latest broken resistance (down) line
   datetime vBrkT[2];    // same, VALID lines only (3-close confirmed)
   datetime lastRetT;
   int      lastRetKind;
   bool     lastRetSteep;
   int      lastRetDir;
  };

ENUM_TIMEFRAMES g_tf[NSLOT];
string   g_tfName[NSLOT];
int      g_tier[NSLOT];     // 0 macro, 1 intermediate (MTF), 2 refinement (LTF)
bool     g_slotUsed[NSLOT];
bool     g_vis[NSLOT];
int      g_order[NSLOT];    // used slots, largest period first
int      g_nUsed = 0;
int      g_chartSlot = -1;
TLine    g_lines[];
TFSum    g_sum[NSLOT];
string   g_drawn[];
int      g_drawnN = 0;

string   g_pp = "TBMP_";    // panel objects
string   g_pl = "TBML_";    // chart lines / labels / boxes / markers
string   g_pw = "TBMW_";    // watermark
int      g_panelMinW = 0;
bool     g_panelReclaim = true;
int      g_panX = -1, g_panY = -1;
datetime g_lastPanelDraw = 0;
datetime g_lastChartBar = 0;

//+------------------------------------------------------------------+
string TFShort(const ENUM_TIMEFRAMES tf)
  {
   string s = EnumToString(tf);
   if(StringFind(s, "PERIOD_") == 0) s = StringSubstr(s, 7);
   return(s);
  }
color TFColor(const int s)
  {
   switch(s)
     {
      case 0: return(InpColMN1);
      case 1: return(InpColW1);
      case 2: return(InpColD1);
      case 3: return(InpColH4);
      case 4: return(InpColH1);
      case 5: return(InpColM15);
      case 6: return(InpColM5);
      case 7: return(InpColM1);
     }
   return(InpColCustom);
  }
bool TFEnabled(const int s)
  {
   switch(s)
     {
      case 0: return(InpShowMN1);
      case 1: return(InpShowW1);
      case 2: return(InpShowD1);
      case 3: return(InpShowH4);
      case 4: return(InpShowH1);
      case 5: return(InpShowM15);
      case 6: return(InpShowM5);
      case 7: return(InpShowM1);
     }
   return(true);   // the non-standard chart period is the chart's own TF - always shown
  }
string TierName(const int t)
  {
   return(t == 0 ? "macro" : t == 1 ? "MTF" : "LTF");
  }
void ResetSum(const int s)
  {
   g_sum[s].ok = false;
   g_sum[s].atr = 0.0;
   g_sum[s].dirCode = DC_NONE;
   g_sum[s].dirTent = false;
   g_sum[s].dirFromBreak = false;
   g_sum[s].anyBrkT[0] = 0; g_sum[s].anyBrkT[1] = 0;
   g_sum[s].vBrkT[0] = 0;   g_sum[s].vBrkT[1] = 0;
   g_sum[s].lastRetT = 0;
   g_sum[s].lastRetKind = ST_TENT;
   g_sum[s].lastRetSteep = false;
   g_sum[s].lastRetDir = 0;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpPivotStrength < 1 || InpLookbackBars < 50 || InpATRPeriod < 1 || InpDriftBars < 2 ||
      InpMacdFast < 1 || InpMacdSlow <= InpMacdFast || InpMacdSignal < 1 || InpSmaPeriod < 1 || InpEmaPeriod < 1)
     {
      Print("TrendBreaker_MTF_Indicator: invalid inputs (pivot strength >= 1, lookback >= 50, MACD slow > fast, periods >= 1).");
      return(INIT_PARAMETERS_INCORRECT);
     }
   ENUM_TIMEFRAMES stdTf[8] = {PERIOD_MN1, PERIOD_W1, PERIOD_D1, PERIOD_H4, PERIOD_H1, PERIOD_M15, PERIOD_M5, PERIOD_M1};
   int tiers[8] = {0, 0, 0, 1, 1, 2, 2, 2};
   ENUM_TIMEFRAMES chart = (ENUM_TIMEFRAMES)_Period;
   g_chartSlot = -1;
   for(int i = 0; i < 8; i++)
     {
      g_tf[i] = stdTf[i];
      g_tfName[i] = TFShort(stdTf[i]);
      g_tier[i] = tiers[i];
      g_slotUsed[i] = true;
      if(stdTf[i] == chart) g_chartSlot = i;
     }
   g_slotUsed[8] = false;
   g_tf[8] = chart; g_tfName[8] = TFShort(chart); g_tier[8] = 2;
   if(g_chartSlot < 0)
     {
      int cs = PeriodSeconds(chart);
      g_slotUsed[8] = true;
      g_tier[8] = (cs >= PeriodSeconds(PERIOD_D1)) ? 0 : (cs >= PeriodSeconds(PERIOD_H1)) ? 1 : 2;
      g_chartSlot = 8;
     }
   int chartSecs = PeriodSeconds(chart);
   for(int s = 0; s < NSLOT; s++)
     {
      g_vis[s] = g_slotUsed[s] && TFEnabled(s) && PeriodSeconds(g_tf[s]) >= chartSecs;
      ResetSum(s);
      g_sum[s].status = "loading";
      g_sum[s].calcKey = 0;
     }
   g_nUsed = 0;
   for(int s = 0; s < NSLOT; s++) if(g_slotUsed[s]) g_order[g_nUsed++] = s;
   for(int a = 0; a < g_nUsed - 1; a++)
      for(int b = a + 1; b < g_nUsed; b++)
         if(PeriodSeconds(g_tf[g_order[b]]) > PeriodSeconds(g_tf[g_order[a]]))
           { int t = g_order[a]; g_order[a] = g_order[b]; g_order[b] = t; }

   ArrayResize(g_lines, 0);
   IndicatorSetString(INDICATOR_SHORTNAME, "TrendBreaker MTF (" + _Symbol + " " + g_tfName[g_chartSlot] + ")");
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pl);
   ObjectsDeleteAll(0, g_pw);
   Comment("");
  }

//+------------------------------------------------------------------+
//| Price helpers. dir -1 (resistance) looks at the upper extreme,    |
//| dir +1 (support) at the lower one; body=true swaps wick for body.  |
//| Pen() > 0 means "beyond the line" (above resistance / below        |
//| support), whatever the line's direction.                           |
//+------------------------------------------------------------------+
double ExtPx(const MqlRates &b, const int dir, const bool body)
  {
   if(dir < 0) return(body ? MathMax(b.open, b.close) : b.high);
   return(body ? MathMin(b.open, b.close) : b.low);
  }
double WickLen(const MqlRates &b, const int dir)
  {
   if(dir < 0) return(b.high - MathMax(b.open, b.close));
   return(MathMin(b.open, b.close) - b.low);
  }
double Pen(const double px, const double lineVal, const int dir)
  {
   return(dir < 0 ? px - lineVal : lineVal - px);
  }

//+------------------------------------------------------------------+
//| SMA of true range - MT5's built-in iATR definition, computed on    |
//| the source TF's own rates so no per-TF indicator handle has to      |
//| finish loading first. Floored at one point so zero-range bars       |
//| (holiday/no-tick bars) can never cause a divide-by-zero.            |
//+------------------------------------------------------------------+
void BuildATR(const MqlRates &r[], const int n, double &atr[])
  {
   ArrayResize(atr, n);
   double tr[]; ArrayResize(tr, n);
   double sum = 0.0;
   for(int i = 0; i < n; i++)
     {
      double hl = r[i].high - r[i].low;
      if(i == 0) tr[i] = hl;
      else
        {
         double pc = r[i - 1].close;
         tr[i] = MathMax(hl, MathMax(MathAbs(r[i].high - pc), MathAbs(r[i].low - pc)));
        }
      sum += tr[i];
      if(i >= InpATRPeriod) sum -= tr[i - InpATRPeriod];
      int cnt = MathMin(i + 1, InpATRPeriod);
      atr[i] = MathMax(sum / cnt, _Point);
     }
  }

//+------------------------------------------------------------------+
//| ZigZag alternation (Backstep + ATR Deviation - see header).         |
//+------------------------------------------------------------------+
void AddSwing(const int type, const int idx, const double px, const double minLeg,
              int &cnt, int &zIdx[], int &zType[], double &zPx[])
  {
   if(cnt > 0 && zType[cnt - 1] == type)
     {
      bool moreExtreme = (type == 1) ? (px > zPx[cnt - 1]) : (px < zPx[cnt - 1]);
      if(moreExtreme) { zIdx[cnt - 1] = idx; zPx[cnt - 1] = px; }
      return;
     }
   if(cnt > 0 && MathAbs(px - zPx[cnt - 1]) < minLeg) return;
   ArrayResize(zIdx, cnt + 1, 64); ArrayResize(zType, cnt + 1, 64); ArrayResize(zPx, cnt + 1, 64);
   zIdx[cnt] = idx; zType[cnt] = type; zPx[cnt] = px;
   cnt++;
  }
//+------------------------------------------------------------------+
//| N-bar pivots over CLOSED bars only. A pivot needs N closed bars on |
//| its right, so the newest N closed bars can never be pivots yet.     |
//| This is the confirmation lag every fractal/ZigZag has, and it is    |
//| why nothing here repaints once confirmed.                           |
//+------------------------------------------------------------------+
int FindSwings(const MqlRates &r[], const double &atr[], const int n, const bool body,
               int &zIdx[], int &zType[], double &zPx[])
  {
   int N = InpPivotStrength;
   int lastClosed = n - 2;
   int cnt = 0;
   ArrayResize(zIdx, 0); ArrayResize(zType, 0); ArrayResize(zPx, 0);
   for(int i = N; i <= lastClosed - N; i++)
     {
      double hi = ExtPx(r[i], -1, body), lo = ExtPx(r[i], 1, body);
      bool isH = true, isL = true;
      for(int m = 1; m <= N && (isH || isL); m++)
        {
         if(ExtPx(r[i - m], -1, body) >= hi || ExtPx(r[i + m], -1, body) > hi) isH = false;
         if(ExtPx(r[i - m],  1, body) <= lo || ExtPx(r[i + m],  1, body) < lo) isL = false;
        }
      double minLeg = InpSwingMinATR * atr[i];
      if(isH && isL)
        {
         // outside bar that is both: add in the order that continues the alternation
         if(cnt > 0 && zType[cnt - 1] == 1)
           { AddSwing(-1, i, lo, minLeg, cnt, zIdx, zType, zPx); AddSwing(1, i, hi, minLeg, cnt, zIdx, zType, zPx); }
         else
           { AddSwing(1, i, hi, minLeg, cnt, zIdx, zType, zPx); AddSwing(-1, i, lo, minLeg, cnt, zIdx, zType, zPx); }
        }
      else if(isH) AddSwing(1, i, hi, minLeg, cnt, zIdx, zType, zPx);
      else if(isL) AddSwing(-1, i, lo, minLeg, cnt, zIdx, zType, zPx);
     }
   return(cnt);
  }
//+------------------------------------------------------------------+
//| Source 1 BOS: "A lower high is only valid if the subsequent drop   |
//| broke below the previous swing low." The whole stretch up to the   |
//| next same-type swing (or the last closed bar, for the newest swing) |
//| is scanned, not just the next ZigZag point, so the newest swing is  |
//| judged by what price has actually done so far. With no prior        |
//| opposite swing (m == 0) the rule cannot be checked, so it fails.     |
//+------------------------------------------------------------------+
bool BOSOk(const int m, const int cnt, const int &zIdx[], const int &zType[], const double &zPx[],
           const MqlRates &r[], const int n, const bool body)
  {
   if(m < 1) return(false);
   if(zType[m - 1] == zType[m]) return(false);
   double level = zPx[m - 1];
   int endI = (m + 2 < cnt) ? zIdx[m + 2] : n - 2;
   for(int q = zIdx[m] + 1; q <= endI; q++)
     {
      if(zType[m] == 1 && ExtPx(r[q], 1, body) < level)  return(true);
      if(zType[m] == -1 && ExtPx(r[q], -1, body) > level) return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
double MeanATR(const double &atr[], const int a, const int b)
  {
   double s = 0.0; int c = 0;
   for(int i = a; i <= b; i++) { s += atr[i]; c++; }
   return(c > 0 ? s / c : _Point);
  }
void SetSlopeATR(TLine &L, const double &atr[])
  {
   L.slopeATR = MathAbs(L.slope) / MathMax(MeanATR(atr, L.ia, L.ib), _Point);
  }
bool IsSteep(const TLine &L) { return(L.slopeATR > InpSlopeSteepATR); }
string SlopeClass(const double sATR)
  {
   if(sATR > InpSlopeSteepATR)      return("STEEP");
   if(sATR > InpSlopeReliableHiATR) return("steepening");
   if(sATR >= InpSlopeReliableLoATR) return("reliable");
   return("shallow");
  }

//+------------------------------------------------------------------+
//| Drift test at the bar a valid line's 3rd close beyond landed on.   |
//| All three conditions are Source 1's own words ("slowly drifts       |
//| sideways ... without explosive volume or aggressive opposing        |
//| candles"), each made measurable in ATR / volume-ratio terms.        |
//+------------------------------------------------------------------+
bool IsDrift(const MqlRates &r[], const double &atr[], const int q, const int lineDir)
  {
   int q0 = q - InpDriftBars;
   if(q0 < 1) return(false);   // not enough history to call it a drift - treat as a real break
   double a = atr[q];
   if(MathAbs(r[q].close - r[q0].close) / a > InpDriftMaxNetATR) return(false);
   int brkDir = -lineDir;       // resistance breaks upward, support breaks downward
   for(int m = q0 + 1; m <= q; m++)
     {
      double bodySigned = r[m].close - r[m].open;
      if(bodySigned * brkDir > 0.0 && MathAbs(bodySigned) / atr[m] > InpDriftMaxBodyATR) return(false);
     }
   int vFrom = MathMax(0, q0 - 50);
   if(q0 - vFrom < 10) return(false);   // too little volume history to rule out "explosive" - call it a break
   double vs = 0.0;
   for(int m = vFrom; m < q0; m++) vs += (double)r[m].tick_volume;
   double vAvg = vs / (q0 - vFrom);
   if(vAvg <= 0.0) return(false);
   for(int m = q0 + 1; m <= q; m++)
      if((double)r[m].tick_volume / vAvg > InpDriftMaxVolRatio) return(false);
   return(true);
  }

void RetireLine(TLine &L, const int s, const MqlRates &r[], const double &atr[], const int q, const bool drift)
  {
   bool wasValid = (L.state == ST_VALID);
   L.retireT = r[q].time;
   L.iret = q;
   L.pending = false;
   if(drift)
     {
      L.state = ST_DRIFT;
      int q0 = MathMax(0, q - InpDriftBars);
      double hi = r[q0].high, lo = r[q0].low;
      for(int m = q0 + 1; m <= q; m++) { hi = MathMax(hi, r[m].high); lo = MathMin(lo, r[m].low); }
      L.boxHi = hi; L.boxLo = lo; L.boxT1 = r[q0].time;
     }
   else
     {
      L.state = ST_BROKEN;
      int k = (L.dir > 0) ? 0 : 1;
      if(L.retireT > g_sum[s].anyBrkT[k]) g_sum[s].anyBrkT[k] = L.retireT;
      if(wasValid && L.retireT > g_sum[s].vBrkT[k]) g_sum[s].vBrkT[k] = L.retireT;
     }
   if(wasValid && L.retireT > g_sum[s].lastRetT)
     {
      g_sum[s].lastRetT = L.retireT;
      g_sum[s].lastRetKind = L.state;
      g_sum[s].lastRetSteep = IsSteep(L);
      g_sum[s].lastRetDir = L.dir;
     }
  }

//+------------------------------------------------------------------+
//| Moves anchor 2 outward to a sweep extreme (Source 1: "Redraw the   |
//| outer boundary to include that extreme wick"). If that would flip  |
//| the line's slope sign (the sweep ran past anchor 1 itself), it is   |
//| no longer the same falling/rising structure, so the caller retires  |
//| it instead.                                                         |
//+------------------------------------------------------------------+
bool ReAnchor(TLine &L, const MqlRates &r[], const double &atr[], const int sIdx, const double ext)
  {
   if(sIdx <= L.ia) return(false);
   double ns = (ext - L.p1) / (double)(sIdx - L.ia);
   if((L.dir < 0 && ns >= 0.0) || (L.dir > 0 && ns <= 0.0)) return(false);
   L.slope = ns;
   L.ib = sIdx; L.t2 = r[sIdx].time; L.p2 = ext;
   L.liq = true; L.sweepT = r[sIdx].time; L.sweepP = ext;
   L.touches++; L.lastTouchT = r[sIdx].time;
   SetSlopeATR(L, atr);
   return(true);
  }

//+------------------------------------------------------------------+
//| Builds one candidate from anchors (ia, ib) and runs it bar by bar   |
//| through the life-cycle, strictly forward in time. Returns false if  |
//| the pair is not a line at all (not lower-high / higher-low, or       |
//| price pierced it between the anchors).                               |
//+------------------------------------------------------------------+
bool BuildLine(const int s, const MqlRates &r[], const double &atr[], const int n,
               const int ia, const int ib, const int dir, const bool macroBody, TLine &L)
  {
   bool body = macroBody;
   if(!body && (WickLen(r[ia], dir) > InpSpikeWickATR * atr[ia] || WickLen(r[ib], dir) > InpSpikeWickATR * atr[ib]))
      body = true;
   double p1 = ExtPx(r[ia], dir, body), p2 = ExtPx(r[ib], dir, body);
   if(dir < 0 && p2 >= p1) return(false);   // down line needs a lower high
   if(dir > 0 && p2 <= p1) return(false);   // up line needs a higher low

   ZeroMemory(L);
   L.slot = s; L.dir = dir; L.body = body;
   L.ia = ia; L.ib = ib; L.iret = -1;
   L.t1 = r[ia].time; L.p1 = p1; L.t2 = r[ib].time; L.p2 = p2;
   L.slope = (p2 - p1) / (double)(ib - ia);
   SetSlopeATR(L, atr);

   int gap = MathMax(2, InpPivotStrength);
   int touches = 2, lastTouch = ia;
   double errSum = 0.0; int errN = 0;
   for(int q = ia + 1; q < ib; q++)
     {
      double lv = p1 + L.slope * (q - ia);
      double pe = Pen(ExtPx(r[q], dir, body), lv, dir);
      if(pe > InpPierceTolATR * atr[q]) return(false);
      if(pe >= -InpTouchTolATR * atr[q] && q - lastTouch >= gap && ib - q >= gap)
        { touches++; lastTouch = q; errSum += MathAbs(pe) / atr[q]; errN++; }
     }
   L.touches = touches;
   L.lastTouchT = r[ib].time;
   lastTouch = ib;
   L.state = (touches >= TOUCHES_TO_VALIDATE) ? ST_VALID : ST_TENT;

   int last = n - 2;           // newest CLOSED bar
   int run = 0, runStart = -1;
   for(int q = ib + 1; q <= last; q++)
     {
      double a  = atr[q];
      double lv = L.p1 + L.slope * (q - L.ia);
      double penC = Pen(r[q].close, lv, dir);
      double penE = Pen(ExtPx(r[q], dir, L.body), lv, dir);

      if(penC > InpBreakTolATR * a)
        {
         if(run == 0) runStart = q;
         run++;
         if(L.state == ST_TENT) { RetireLine(L, s, r, atr, q, false); break; }
         if(run >= BREAK_CONFIRM_CLOSES)
           { RetireLine(L, s, r, atr, q, IsDrift(r, atr, q, dir)); break; }
         continue;
        }
      if(run > 0)
        {
         // back inside after 1-2 closes beyond: Source 1 liquidity sweep on a valid line
         int sIdx = runStart; double ext = ExtPx(r[runStart], dir, L.body);
         for(int m = runStart + 1; m <= q; m++)
           {
            double e = ExtPx(r[m], dir, L.body);
            if((dir < 0 && e > ext) || (dir > 0 && e < ext)) { ext = e; sIdx = m; }
           }
         run = 0;
         if(!ReAnchor(L, r, atr, sIdx, ext)) { RetireLine(L, s, r, atr, q, false); break; }
         lastTouch = sIdx;
         continue;
        }
      if(penE > InpPierceTolATR * a)
        {
         // pierce with the close still inside (wick in wick mode; open/body in body mode)
         if(L.state == ST_TENT) { RetireLine(L, s, r, atr, q, false); break; }
         if(!ReAnchor(L, r, atr, q, ExtPx(r[q], dir, L.body))) { RetireLine(L, s, r, atr, q, false); break; }
         lastTouch = q;
         continue;
        }
      if(penE >= -InpTouchTolATR * a && q - lastTouch >= gap)
        {
         L.touches++; lastTouch = q; L.lastTouchT = r[q].time;
         errSum += MathAbs(penE) / a; errN++;
         if(L.state == ST_TENT && L.touches >= TOUCHES_TO_VALIDATE) L.state = ST_VALID;
        }
     }
   if((L.state == ST_VALID || L.state == ST_TENT) && run > 0) L.pending = true;
   L.meanErr = (errN > 0) ? errSum / errN : 0.0;
   return(true);
  }

//+------------------------------------------------------------------+
//| Selection: which candidates are the timeframe's lines "in play".   |
//+------------------------------------------------------------------+
bool IsActive(const TLine &L) { return(L.state == ST_VALID || L.state == ST_TENT); }
double CandValue(const TLine &L, const int idx) { return(L.p1 + L.slope * (idx - L.ia)); }

bool Better(const TLine &a, const TLine &b)
  {
   if(a.state != b.state) return(a.state == ST_VALID);
   if(a.state == ST_VALID)
     {
      if(a.touches != b.touches) return(a.touches > b.touches);
      if(a.lastTouchT != b.lastTouchT) return(a.lastTouchT > b.lastTouchT);
      return(a.meanErr < b.meanErr);
     }
   // tentative: the user wants to see lines FORMING, so the newest draft wins
   if(a.t2 != b.t2) return(a.t2 > b.t2);
   if(a.touches != b.touches) return(a.touches > b.touches);
   return(a.meanErr < b.meanErr);
  }
int PickPrimary(const TLine &c[], const int nc, const int dir, const int n, const double px, const double atrNow)
  {
   int best = -1;
   for(int i = 0; i < nc; i++)
     {
      if(c[i].dir != dir || !IsActive(c[i])) continue;
      if(MathAbs(px - CandValue(c[i], n - 1)) > InpMaxDistATR * atrNow) continue;
      if(best < 0 || Better(c[i], c[best])) best = i;
     }
   return(best);
  }
int PickFan(const TLine &c[], const int nc, const int base, const double &atr[])
  {
   int best = -1;
   for(int i = 0; i < nc; i++)
     {
      if(i == base || c[i].dir != c[base].dir || !IsActive(c[i])) continue;
      if(c[i].ia < c[base].ib) continue;
      if(c[i].slope * c[base].slope <= 0.0) continue;
      if(MathAbs(c[i].slope) < InpFanSteepen * MathAbs(c[base].slope)) continue;
      double gapPx = Pen(c[i].p1, CandValue(c[base], c[i].ia), -c[base].dir);   // > 0 = on the trend side of the base
      if(gapPx < InpFanMinGapATR * atr[c[i].ia]) continue;
      if(best < 0 || Better(c[i], c[best])) best = i;
     }
   return(best);
  }
int PickBox(const TLine &c[], const int nc, const int dir, const int n, const double px, const double atrNow)
  {
   int best = -1;
   for(int i = 0; i < nc; i++)
     {
      if(c[i].dir != dir || c[i].state != ST_DRIFT) continue;
      if((n - 2) - c[i].iret > InpBoxKeepBars) continue;
      double d = (px > c[i].boxHi) ? px - c[i].boxHi : (px < c[i].boxLo) ? c[i].boxLo - px : 0.0;
      if(d > InpMaxDistATR * atrNow) continue;
      if(best < 0 || c[i].iret > c[best].iret) best = i;
     }
   return(best);
  }
void PushLine(const TLine &L, const int role)
  {
   int k = ArraySize(g_lines);
   ArrayResize(g_lines, k + 1, 32);
   g_lines[k] = L;
   g_lines[k].role = role;
  }
void RemoveSlotLines(const int s)
  {
   int w = 0, n = ArraySize(g_lines);
   for(int i = 0; i < n; i++)
      if(g_lines[i].slot != s) { if(w != i) g_lines[w] = g_lines[i]; w++; }
   ArrayResize(g_lines, w);
  }
int FindLine(const int s, const int dir, const int role)
  {
   for(int i = 0; i < ArraySize(g_lines); i++)
      if(g_lines[i].slot == s && g_lines[i].dir == dir && g_lines[i].role == role) return(i);
   return(-1);
  }

//+------------------------------------------------------------------+
//| Full rebuild of one timeframe slot. Returns false only when data   |
//| is not available YET (so the caller retries). "Not enough history" |
//| is a real, stable answer: it returns true with ok=false and a       |
//| status string, so there is no retry storm.                          |
//+------------------------------------------------------------------+
bool ComputeTF(const int s)
  {
   ENUM_TIMEFRAMES tf = g_tf[s];
   ResetSum(s);
   RemoveSlotLines(s);

   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, tf, 0, InpLookbackBars, r);   // also kicks off the terminal's async load of this TF
   if(n <= 0) { g_sum[s].status = "loading history"; return(false); }
   if(!SeriesInfoInteger(_Symbol, tf, SERIES_SYNCHRONIZED))
     { g_sum[s].status = "syncing history"; return(false); }   // partial data would give wrong swings - wait
   int need = 4 * InpPivotStrength + InpATRPeriod + InpDriftBars + 12;
   if(n < need)
     {
      g_sum[s].status = "only " + IntegerToString(n) + " bars (need " + IntegerToString(need) + ")";
      return(true);
     }

   double atr[];
   BuildATR(r, n, atr);
   bool macroBody = (g_tier[s] == 0 && InpMacroBodies);
   int zIdx[], zType[]; double zPx[];
   int zc = FindSwings(r, atr, n, macroBody, zIdx, zType, zPx);

   double px = r[n - 1].close;
   double atrNow = atr[n - 2];
   g_sum[s].atr = atrNow;

   TLine cand[];
   int nc = 0;
   for(int d = 0; d < 2; d++)
     {
      int dir = (d == 0) ? 1 : -1;
      int want = (dir < 0) ? 1 : -1;       // resistance from swing highs, support from swing lows
      int anc[]; int na = 0;
      for(int m = 0; m < zc; m++)
         if(zType[m] == want && BOSOk(m, zc, zIdx, zType, zPx, r, n, macroBody))
           { ArrayResize(anc, na + 1, 32); anc[na++] = zIdx[m]; }
      for(int a = 0; a < na - 1; a++)
         for(int b = a + 1; b < na; b++)
           {
            if(anc[b] - anc[a] < InpPivotStrength) continue;
            TLine L;
            if(!BuildLine(s, r, atr, n, anc[a], anc[b], dir, macroBody, L)) continue;
            ArrayResize(cand, nc + 1, 128);
            cand[nc++] = L;
           }
     }

   int prim[2] = {-1, -1};
   int fans = 0, liq = 0;
   for(int d = 0; d < 2; d++)
     {
      int dir = (d == 0) ? 1 : -1;
      int p = PickPrimary(cand, nc, dir, n, px, atrNow);
      prim[d] = p;
      if(p >= 0)
        {
         PushLine(cand[p], ROLE_PRIMARY);
         if(cand[p].liq) liq++;
         if(InpShowFans && g_tier[s] >= 1 && cand[p].state == ST_VALID)
           {
            int f2 = PickFan(cand, nc, p, atr);
            if(f2 >= 0)
              {
               PushLine(cand[f2], ROLE_FAN2); fans++;
               int f3 = PickFan(cand, nc, f2, atr);
               if(f3 >= 0) { PushLine(cand[f3], ROLE_FAN3); fans++; }
              }
           }
        }
      int bx = PickBox(cand, nc, dir, n, px, atrNow);
      if(bx >= 0) PushLine(cand[bx], ROLE_BOX);
     }

   //--- timeframe direction from VALID structure only (Source 1: "You only trade the 3rd touch")
   bool upV = prim[0] >= 0 && cand[prim[0]].state == ST_VALID;
   bool dnV = prim[1] >= 0 && cand[prim[1]].state == ST_VALID;
   int  retAgo = (g_sum[s].lastRetT > 0) ? (n - 2) - iBarShiftLocal(r, n, g_sum[s].lastRetT) : 999999;
   if(upV && !dnV)      g_sum[s].dirCode = DC_UP;
   else if(dnV && !upV) g_sum[s].dirCode = DC_DN;
   else if(upV && dnV)  g_sum[s].dirCode = DC_WEDGE;
   else if(g_sum[s].lastRetT > 0 && retAgo <= InpBoxKeepBars)
     {
      if(g_sum[s].lastRetKind == ST_DRIFT) g_sum[s].dirCode = DC_RANGE;
      else if(g_sum[s].lastRetSteep)       g_sum[s].dirCode = DC_TOHTF;   // Source 1: steep break = back to the macro line, not a reversal
      else { g_sum[s].dirCode = -g_sum[s].lastRetDir; g_sum[s].dirFromBreak = true; }
     }
   else
     {
      bool upT = prim[0] >= 0, dnT = prim[1] >= 0;
      if(upT && !dnT)      { g_sum[s].dirCode = DC_UP; g_sum[s].dirTent = true; }
      else if(dnT && !upT) { g_sum[s].dirCode = DC_DN; g_sum[s].dirTent = true; }
      else                   g_sum[s].dirCode = DC_NONE;
     }
   g_sum[s].ok = true;
   g_sum[s].status = (zc < 3) ? "no confirmed swings yet" : (nc == 0 ? "no BOS-valid line yet" : "");
   return(true);
  }
//+------------------------------------------------------------------+
//| Index of the bar holding time t in a chronological rates array.   |
//+------------------------------------------------------------------+
int iBarShiftLocal(const MqlRates &r[], const int n, const datetime t)
  {
   for(int i = n - 1; i >= 0; i--) if(r[i].time <= t) return(i);
   return(0);
  }

//+------------------------------------------------------------------+
//| Recomputes a slot only when its own source bar rolls (or, for      |
//| frozen macro slots, when the W1 bar rolls).                        |
//+------------------------------------------------------------------+
bool RefreshTFs()
  {
   bool changed = false;
   for(int s = 0; s < NSLOT; s++)
     {
      if(!g_vis[s]) continue;
      datetime key = (g_tier[s] == 0 && InpMacroFreezeWeekly && g_tf[s] != PERIOD_MN1 && g_tf[s] != PERIOD_W1)
                     ? iTime(_Symbol, PERIOD_W1, 0) : iTime(_Symbol, g_tf[s], 0);
      if(key == 0) { g_sum[s].status = "loading history"; continue; }
      if(key == g_sum[s].calcKey) continue;
      bool hadLines = false;
      for(int i = 0; i < ArraySize(g_lines); i++) if(g_lines[i].slot == s) { hadLines = true; break; }
      if(ComputeTF(s)) { g_sum[s].calcKey = key; changed = true; }
      else if(hadLines) changed = true;
     }
   return(changed);
  }

//+------------------------------------------------------------------+
//| Line value helpers. LineValueAt() uses the SOURCE timeframe's bar- |
//| index geometry (what the line was fitted in); RenderedValue()       |
//| asks the chart where it actually drew the object, so the panel's    |
//| distances match what the user sees.                                 |
//+------------------------------------------------------------------+
double LineValueAt(const TLine &L, const datetime t)
  {
   ENUM_TIMEFRAMES tf = g_tf[L.slot];
   int s1 = iBarShift(_Symbol, tf, L.t1, false);
   if(s1 < 0) return(0.0);
   datetime t0 = iTime(_Symbol, tf, 0);
   if(t0 == 0) return(0.0);
   double st;
   if(t > t0) st = -(double)(t - t0) / (double)PeriodSeconds(tf);
   else
     {
      int sh = iBarShift(_Symbol, tf, t, false);
      if(sh < 0) return(0.0);
      st = (double)sh;
     }
   return(L.p1 + L.slope * ((double)s1 - st));
  }
string LineBase(const TLine &L)
  {
   return(g_pl + g_tfName[L.slot] + "_" + (L.dir > 0 ? "U" : "D") + IntegerToString(L.role));
  }
double RenderedValue(const TLine &L, const datetime t)
  {
   string nm = LineBase(L) + "_ln";
   if(ObjectFind(0, nm) >= 0)
     {
      double v = ObjectGetValueByTime(0, nm, t, 0);
      if(v > 0.0) return(v);
     }
   return(LineValueAt(L, t));
  }

//+------------------------------------------------------------------+
//| Chart objects. DrawChartLabel()/DeleteChartLabel() are MSG_Trader_ |
//| EA.mq5's own; DrawRangeBox() is its DrawSessionBox() idiom.        |
//+------------------------------------------------------------------+
void MarkDrawn(const string nm)
  {
   ArrayResize(g_drawn, g_drawnN + 1, 64);
   g_drawn[g_drawnN++] = nm;
  }
bool WasDrawn(const string nm)
  {
   for(int i = 0; i < g_drawnN; i++) if(g_drawn[i] == nm) return(true);
   return(false);
  }
void DrawChartLabel(const string prefix, const string tag, datetime t, double price,
                    const string text, const color col, const int fontSize = 9)
  {
   string nm = prefix + tag;
   if(text == "") { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetString (0, nm, OBJPROP_TEXT, text);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString (0, nm, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
void DrawRangeBox(const string nm, datetime t1, datetime t2, double hi, double lo, color col, bool emphasis)
  {
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t1);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, hi);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t2);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, lo);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, emphasis ? 2 : 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, nm, OBJPROP_FILL, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
void DrawTrendObj(const string nm, const TLine &L, const color col, const int width, const ENUM_LINE_STYLE style)
  {
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_TREND, 0, L.t1, L.p1, L.t2, L.p2);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, L.t1);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, L.p1);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 1, L.t2);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, L.p2);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, true);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
void DrawMarker(const string nm, const datetime t, const double px, const color col, const int dir)
  {
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_ARROW, 0, t, px);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, px);
   ObjectSetInteger(0, nm, OBJPROP_ARROWCODE, 159);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 3);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, dir < 0 ? ANCHOR_BOTTOM : ANCHOR_TOP);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
//| Real on-screen angle of a drawn line (see header, method (a)).     |
//| Measured between the line's rendered values at the leftmost and     |
//| rightmost VISIBLE bars (clamped to anchor 1, where the object       |
//| starts). That is the widest span actually on screen, so integer-    |
//| pixel rounding costs well under a degree at any sensible zoom. If   |
//| the line isn't in view at all, its own anchor span is used instead. |
//+------------------------------------------------------------------+
bool ScreenAngle(const TLine &L, double &deg)
  {
   string nm = LineBase(L) + "_ln";
   if(ObjectFind(0, nm) < 0) return(false);
   int firstVis = (int)ChartGetInteger(0, CHART_FIRST_VISIBLE_BAR);
   int visBars  = (int)ChartGetInteger(0, CHART_VISIBLE_BARS);
   int lastVis  = MathMax(0, firstVis - visBars + 1);
   datetime ta = iTime(_Symbol, PERIOD_CURRENT, firstVis);
   datetime tb = iTime(_Symbol, PERIOD_CURRENT, lastVis);
   if(ta == 0 || tb == 0) return(false);
   if(ta < L.t1) ta = L.t1;
   if(tb <= ta) { ta = L.t1; tb = L.t2; }
   double va = (ta == L.t1) ? L.p1 : ObjectGetValueByTime(0, nm, ta, 0);
   double vb = (tb == L.t2) ? L.p2 : ObjectGetValueByTime(0, nm, tb, 0);
   if(va <= 0.0 || vb <= 0.0) return(false);
   int x1, y1, x2, y2;
   if(!ChartTimePriceToXY(0, 0, ta, va, x1, y1)) return(false);
   if(!ChartTimePriceToXY(0, 0, tb, vb, x2, y2)) return(false);
   int dx = x2 - x1, dy = y1 - y2;   // screen y grows downward
   if(dx <= 0) { deg = 90.0; return(true); }
   deg = MathAbs(MathArctan((double)dy / (double)dx)) * 180.0 / M_PI;
   return(true);
  }
string LineCaption(const TLine &L)
  {
   double deg;
   string degTxt = ScreenAngle(L, deg) ? DoubleToString(deg, 0) + "deg" : "--deg";
   string s = "  " + g_tfName[L.slot] + (L.dir > 0 ? " UP" : " DN");
   if(L.role == ROLE_FAN2) s += " fan2";
   if(L.role == ROLE_FAN3) s += " fan3";
   if(L.liq) s += " LIQ";
   s += " " + degTxt + " (" + DoubleToString(L.slopeATR, 2) + " ATR/bar " + SlopeClass(L.slopeATR) + ")";
   s += (L.state == ST_VALID ? " VALID x" : " tent x") + IntegerToString(L.touches);
   if(L.pending) s += " testing";
   return(s);
  }
void DrawLineLabel(const TLine &L)
  {
   string base = LineBase(L);
   datetime tb = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(tb == 0) return;
   if(L.role == ROLE_BOX)
     {
      DrawChartLabel(base, "_lb", L.boxT1, L.boxHi,
                     "  " + g_tfName[L.slot] + " RANGE (drift)  H " + DoubleToString(L.boxHi, _Digits)
                     + " / L " + DoubleToString(L.boxLo, _Digits), TFColor(L.slot), InpLabelSize);
      return;
     }
   double v = RenderedValue(L, tb);
   if(v <= 0.0) return;
   DrawChartLabel(base, "_lb", tb, v, LineCaption(L), TFColor(L.slot), InpLabelSize);
  }

//+------------------------------------------------------------------+
//| One full redraw pass + keyed purge of anything not redrawn.        |
//+------------------------------------------------------------------+
void DrawAll()
  {
   g_drawnN = 0;
   ArrayResize(g_drawn, 0, 64);
   datetime tb = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(tb == 0) return;   // chart series not ready - keep existing objects, purge on the next pass
   datetime boxEnd = (datetime)((long)tb + (long)InpBoxExtendBars * PeriodSeconds(_Period));
   for(int i = 0; i < ArraySize(g_lines); i++)
     {
      if(!g_vis[g_lines[i].slot]) continue;
      TLine L = g_lines[i];
      string base = LineBase(L);
      color col = TFColor(L.slot);
      if(L.role == ROLE_BOX)
        {
         DrawRangeBox(base + "_bx", L.boxT1, boxEnd, L.boxHi, L.boxLo, col, g_tier[L.slot] <= 1);
         MarkDrawn(base + "_bx");
         DrawLineLabel(L); MarkDrawn(base + "_lb");
         continue;
        }
      int tierW = (g_tier[L.slot] == 0) ? 3 : (g_tier[L.slot] == 1) ? 2 : 1;
      // MT5 renders dashed/dotted styles only at width 1, so non-solid states use width 1
      int width; ENUM_LINE_STYLE st;
      if(L.state != ST_VALID)  { width = 1; st = STYLE_DOT; }
      else if(IsSteep(L))      { width = 1; st = STYLE_DASHDOT; }
      else                     { width = tierW; st = STYLE_SOLID; }
      DrawTrendObj(base + "_ln", L, col, width, st);
      MarkDrawn(base + "_ln");
      DrawLineLabel(L); MarkDrawn(base + "_lb");
      if(L.liq)
        {
         DrawMarker(base + "_sw", L.sweepT, L.sweepP, InpColLiquidity, L.dir);
         MarkDrawn(base + "_sw");
        }
     }
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, g_pl) != 0) continue;
      if(!WasDrawn(nm)) ObjectDelete(0, nm);
     }
  }
void RefreshLabels()
  {
   for(int i = 0; i < ArraySize(g_lines); i++)
      if(g_vis[g_lines[i].slot] && g_lines[i].role != ROLE_BOX) DrawLineLabel(g_lines[i]);
  }

//+------------------------------------------------------------------+
//| Source 2 stack on the chart TF. EMA seeded with an SMA of its first |
//| `period` values (TradingView ta.ema convention, the guide's own      |
//| platform). A 400-bar window leaves every seed long converged.        |
//+------------------------------------------------------------------+
void EmaSeries(const double &src[], const int n, const int start, const int period, double &out[])
  {
   ArrayResize(out, n);
   ArrayInitialize(out, EMPTY_VALUE);
   if(start + period > n) return;
   double k = 2.0 / (period + 1.0), s = 0.0;
   for(int i = start; i < start + period; i++) s += src[i];
   out[start + period - 1] = s / period;
   for(int i = start + period; i < n; i++) out[i] = src[i] * k + out[i - 1] * (1.0 - k);
  }
// sign of (a-b) on the newest closed bar and how many bars since it last flipped (-1 = no flip in window)
bool CrossState(const double &a[], const double &b[], const int n, const int firstValid, int &dir, int &ago)
  {
   dir = 0; ago = -1;
   int e = n - 2;
   if(e < firstValid || a[e] == EMPTY_VALUE || b[e] == EMPTY_VALUE) return(false);
   double d0 = a[e] - b[e];
   if(d0 == 0.0) return(false);
   dir = (d0 > 0.0) ? 1 : -1;
   for(int j = e - 1; j >= firstValid; j--)
     {
      if(a[j] == EMPTY_VALUE || b[j] == EMPTY_VALUE) break;
      double d = a[j] - b[j];
      if(d * dir < 0.0) { ago = e - j - 1; break; }   // bars since the bar that crossed (0 = crossed on bar 1)
     }
   return(true);
  }
bool BreakerStack(int &macdDir, int &macdAgo, int &maDir, int &maAgo)
  {
   double c[];
   ArraySetAsSeries(c, false);
   int n = CopyClose(_Symbol, PERIOD_CURRENT, 0, 400, c);
   int need = InpMacdSlow + InpMacdSignal + 10;
   if(n < MathMax(need, InpEmaPeriod + 10)) return(false);
   double ef[], es[], macd[], sig[];
   EmaSeries(c, n, 0, InpMacdFast, ef);
   EmaSeries(c, n, 0, InpMacdSlow, es);
   ArrayResize(macd, n); ArrayInitialize(macd, EMPTY_VALUE);
   int m0 = InpMacdSlow - 1;
   for(int i = m0; i < n; i++) macd[i] = ef[i] - es[i];
   EmaSeries(macd, n, m0, InpMacdSignal, sig);
   bool ok1 = CrossState(macd, sig, n, m0 + InpMacdSignal - 1, macdDir, macdAgo);

   double sma[], ema[];
   ArrayResize(sma, n); ArrayInitialize(sma, EMPTY_VALUE);
   double s = 0.0;
   for(int i = 0; i < n; i++)
     {
      s += c[i];
      if(i >= InpSmaPeriod) s -= c[i - InpSmaPeriod];
      if(i >= InpSmaPeriod - 1) sma[i] = s / InpSmaPeriod;
     }
   EmaSeries(c, n, 0, InpEmaPeriod, ema);
   bool ok2 = CrossState(sma, ema, n, MathMax(InpSmaPeriod, InpEmaPeriod) - 1, maDir, maAgo);
   return(ok1 && ok2);
  }

//+------------------------------------------------------------------+
//| Volume readiness - VWAP_Readiness_Indicator.mq5's VolumeRatioAt(), |
//| verbatim (Aurelius_EA.mq5's own real construction).                |
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
double ChartATR()
  {
   if(g_chartSlot >= 0 && g_sum[g_chartSlot].ok && g_sum[g_chartSlot].atr > 0.0) return(g_sum[g_chartSlot].atr);
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 1, InpATRPeriod + 1, r);
   if(n < 2) return(0.0);
   double s = 0.0;
   for(int i = 1; i < n; i++)
      s += MathMax(r[i].high - r[i].low, MathMax(MathAbs(r[i].high - r[i - 1].close), MathAbs(r[i].low - r[i - 1].close)));
   return(MathMax(s / (n - 1), _Point));
  }
int ChartBarsAgo(const datetime t)
  {
   if(t <= 0) return(-1);
   return(iBarShift(_Symbol, PERIOD_CURRENT, t, false));
  }

//+------------------------------------------------------------------+
//| Panel text builders.                                                |
//+------------------------------------------------------------------+
string ShortLine(const TLine &L)
  {
   return(g_tfName[L.slot] + (L.dir > 0 ? " UP " : " DN ") + (L.state == ST_VALID ? "VALID x" : "tent x")
          + IntegerToString(L.touches) + (L.liq ? " LIQ" : ""));
  }
string DirText(const int s, int &st)
  {
   st = -1;
   if(!g_sum[s].ok) return(g_sum[s].status == "" ? "loading" : g_sum[s].status);
   int code = g_sum[s].dirCode;
   if(code == DC_UP || code == DC_DN)
     {
      st = (code == DC_UP) ? 1 : 0;
      string d = (code == DC_UP) ? "UP" : "DOWN";
      if(g_sum[s].dirFromBreak)
         return(d + (code == DC_UP ? " (res. line broke)" : " (sup. line broke)"));
      int li = FindLine(s, code, ROLE_PRIMARY);
      if(li < 0) return(d);
      string v = d + (g_sum[s].dirTent ? "? tent x" : " VALID x") + IntegerToString(g_lines[li].touches)
                 + " " + SlopeClass(g_lines[li].slopeATR);
      int nf = (FindLine(s, code, ROLE_FAN2) >= 0 ? 1 : 0) + (FindLine(s, code, ROLE_FAN3) >= 0 ? 1 : 0);
      if(nf > 0) v += " +" + IntegerToString(nf) + " fan";
      return(v);
     }
   if(code == DC_WEDGE) return("WEDGE (up+dn valid)");
   if(code == DC_RANGE) return("RANGE (drift box)");
   if(code == DC_TOHTF)
     {
      // Source 1: a >60deg line breaking = "a shift back to the macro trendline" - defer to the next higher TF's own reading
      // g_order is largest-first, so walking it backwards meets the NEAREST higher TF first
      for(int p = g_nUsed - 1; p >= 0; p--)
        {
         int h = g_order[p];
         if(PeriodSeconds(g_tf[h]) <= PeriodSeconds(g_tf[s]) || !g_sum[h].ok) continue;
         int hc = g_sum[h].dirCode;
         if(hc == DC_UP || hc == DC_DN)
           {
            st = (hc == DC_UP) ? 1 : 0;
            return("steep brk -> " + g_tfName[h] + (hc == DC_UP ? " UP" : " DOWN"));
           }
        }
      return("steep brk -> no HTF line");
     }
   return(g_sum[s].status != "" ? g_sum[s].status : "no line yet");
  }
bool TFRow(const int pos, const int x, const int y, const int w)
  {
   if(pos >= g_nUsed) return(false);
   int s = g_order[pos];
   if(!g_vis[s]) return(false);
   int st;
   string v = DirText(s, st);
   string id = "f" + IntegerToString(pos);
   PRow(id, x, y, w, g_tfName[s] + " " + TierName(g_tier[s]), v, st);
   ObjectSetInteger(0, g_pp + id + "l", OBJPROP_COLOR, TFColor(s));   // row label in the TF's own line colour
   return(true);
  }
int NearestLine(const bool higherOnly, const bool validOnly, const double px, double &dist, double &val)
  {
   int best = -1; dist = DBL_MAX; val = 0.0;
   datetime tb = iTime(_Symbol, PERIOD_CURRENT, 0);
   int cs = PeriodSeconds(_Period);
   for(int i = 0; i < ArraySize(g_lines); i++)
     {
      TLine L = g_lines[i];
      if(!g_vis[L.slot] || L.role == ROLE_BOX) continue;
      if(higherOnly && PeriodSeconds(g_tf[L.slot]) <= cs) continue;
      if(validOnly && L.state != ST_VALID) continue;
      double v = RenderedValue(L, tb);
      if(v <= 0.0) continue;
      double d = MathAbs(px - v);
      if(d < dist) { dist = d; best = i; val = v; }
     }
   return(best);
  }

//+------------------------------------------------------------------+
//| Panel primitives - identical to ScalpSignal_Indicator.mq5's /      |
//| VWAP_Readiness_Indicator.mq5's own.                                |
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
//| The panel. ROWS/GAPS hand-counted against the literal PRow/        |
//| PSection sequence below, same discipline as ScalpSignal_           |
//| Indicator.mq5's DrawPanel(). ROWS includes all NSLOT (9) possible  |
//| timeframe rows. Only the chart TF and higher ones actually draw,   |
//| so the height uses ROWS minus the rows skipped this pass.          |
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

   const int ROWS = 28, GAPS = 9;
   int shownTF = 0;
   for(int p = 0; p < g_nUsed; p++) if(g_vis[g_order[p]]) shownTF++;
   int rowsUsed = ROWS - (NSLOT - shownTF);
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH  = hdr + 10 + rowsUsed * rh + GAPS * 6 + 12;
   int guard  = 0;
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     {
      rh--; guard++;
      hdr   = rh + 14;
      bodyH = hdr + 10 + rowsUsed * rh + GAPS * 6 + 12;
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
   PText("t2", x + w - 12, ty + 3, "TREND BREAKER MTF", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   // --- a0: chart timeframe (1 row) ---------------------------------------
   PRow("a0", x, ty, w, "chart timeframe",
        g_tfName[g_chartSlot] + " (+" + IntegerToString(shownTF - 1) + " higher shown)", 1); ty += rh + 6;   // GAP 1

   // --- TREND BY TIMEFRAME (section + up to 9 conditional rows) -------------
   PSection("s1", x, ty, w, rh, "TREND BY TIMEFRAME"); ty += rh + 6;                                  // GAP 2
   if(TFRow(0, x, ty, w)) ty += rh;
   if(TFRow(1, x, ty, w)) ty += rh;
   if(TFRow(2, x, ty, w)) ty += rh;
   if(TFRow(3, x, ty, w)) ty += rh;
   if(TFRow(4, x, ty, w)) ty += rh;
   if(TFRow(5, x, ty, w)) ty += rh;
   if(TFRow(6, x, ty, w)) ty += rh;
   if(TFRow(7, x, ty, w)) ty += rh;
   if(TFRow(8, x, ty, w)) ty += rh;
   ty += 6;                                                                                            // GAP 3

   // --- STRUCTURE NEAR PRICE (section + 6 rows) -------------------------------
   double px   = iClose(_Symbol, PERIOD_CURRENT, 0);
   double atrC = ChartATR();
   double dN, vN, dH, vH;
   int iN = NearestLine(false, false, px, dN, vN);
   int iH = NearestLine(true, false, px, dH, vH);

   string n1 = "none in play", n2 = "n/a", n3 = "n/a";
   int st1 = -1, st3 = -1;
   if(iN >= 0)
     {
      n1 = ShortLine(g_lines[iN]);
      st1 = g_lines[iN].dir > 0 ? 1 : 0;
      n2 = (atrC > 0.0 ? DoubleToString(dN / atrC, 2) + " ATR " : "") + (px >= vN ? "above it" : "below it");
     }
   if(PeriodSeconds(_Period) >= PeriodSeconds(PERIOD_MN1)) n3 = "n/a (top TF)";
   else if(iH >= 0)
     {
      TLine H = g_lines[iH];
      st3 = H.dir > 0 ? 1 : 0;
      n3 = g_tfName[H.slot] + (H.dir > 0 ? " UP " : " DN ") + (atrC > 0.0 ? DoubleToString(dH / atrC, 1) + " ATR" : "");
      datetime t5 = iTime(_Symbol, PERIOD_CURRENT, 5);
      double v5 = (t5 > 0) ? RenderedValue(H, t5) : 0.0;
      double c5 = iClose(_Symbol, PERIOD_CURRENT, 5);
      if(v5 > 0.0 && c5 > 0.0)
         n3 += (MathAbs(c5 - v5) < dH) ? ", expanding" : ", pulling back";   // Source 1 Step 2's own question
     }
   else n3 = "none in play";

   string fanTxt = ""; int liqN = 0, boxN = 0;
   for(int p = 0; p < g_nUsed; p++)
     {
      int s = g_order[p];
      if(!g_vis[s]) continue;
      int f = 0;
      for(int i = 0; i < ArraySize(g_lines); i++)
        {
         if(g_lines[i].slot != s) continue;
         if(g_lines[i].role == ROLE_FAN2 || g_lines[i].role == ROLE_FAN3) f++;
         if(g_lines[i].role == ROLE_BOX) boxN++;
         else if(g_lines[i].liq) liqN++;
        }
      if(f > 0) fanTxt += (fanTxt == "" ? "" : " ") + g_tfName[s] + ":" + IntegerToString(f);
     }
   if(fanTxt == "") fanTxt = "none";

   // Source 1 Step 3: LTF counter-trendline break while price is at a validated MTF/HTF line
   string trig = "n/a (not an LTF chart)"; int stT = -1;
   if(g_tier[g_chartSlot] == 2)
     {
      double dV, vV;
      int iV = NearestLine(true, true, px, dV, vV);
      if(iV < 0) trig = "no valid MTF/HTF line";
      else
        {
         TLine V = g_lines[iV];
         string at = g_tfName[V.slot] + (V.dir > 0 ? " UP" : " DN");
         if(atrC <= 0.0 || dV / atrC > InpApproachATR)
            trig = "not at a line (" + at + " " + (atrC > 0.0 ? DoubleToString(dV / atrC, 1) : "?") + " ATR)";
         else
           {
            int k = (-V.dir > 0) ? 0 : 1;   // the counter line has the opposite direction to the HTF line
            int ago = ChartBarsAgo(g_sum[g_chartSlot].anyBrkT[k]);
            if(ago >= 0 && ago <= InpTriggerBars)
              {
               trig = (V.dir > 0 ? "BUY cue: LTF DN line broke at " : "SELL cue: LTF UP line broke at ") + at;
               stT = V.dir > 0 ? 1 : 0;
              }
            else trig = "at " + at + ", no LTF counter-break";
           }
        }
     }

   PSection("s2", x, ty, w, rh, "STRUCTURE NEAR PRICE"); ty += rh + 6;                                // GAP 4
   PRow("n1", x, ty, w, "nearest line", n1, st1); ty += rh;
   PRow("n2", x, ty, w, "price vs it", n2, -1); ty += rh;
   PRow("n3", x, ty, w, "nearest higher-TF line", n3, st3); ty += rh;
   PRow("n4", x, ty, w, "fan lines", fanTxt, -1); ty += rh;
   PRow("n5", x, ty, w, "liquidity / range", IntegerToString(liqN) + " LIQ / " + IntegerToString(boxN) + " box", -1); ty += rh;
   PRow("n6", x, ty, w, "LTF trigger (Step 3)", trig, stT); ty += rh + 6;                              // GAP 5

   // --- BREAKER STACK, Source 2, context only (section + 4 rows) --------------
   int mD, mA, aD, aA;
   bool haveStack = BreakerStack(mD, mA, aD, aA);
   string c1 = "n/a", c2 = "n/a", c3 = "n/a", c4 = "n/a";
   int sc1 = -1, sc2 = -1, sc3 = -1, sc4 = -1;
   if(haveStack)
     {
      c1 = (mD > 0 ? "above signal" : "below signal") + (mA >= 0 && mA <= InpCrossLookback ? ", x " + IntegerToString(mA) + "b ago" : "");
      sc1 = mD > 0 ? 1 : 0;
      c2 = (aD > 0 ? "SMA above" : "SMA below") + (aA >= 0 && aA <= InpCrossLookback ? ", x " + IntegerToString(aA) + "b ago" : "");
      sc2 = aD > 0 ? 1 : 0;
      bool freshM = (mA >= 0 && mA <= InpCrossLookback), freshA = (aA >= 0 && aA <= InpCrossLookback);
      if(mD == aD && freshM && freshA) { c3 = (mD > 0 ? "BREAKING UP" : "BREAKING DOWN"); sc3 = mD > 0 ? 1 : 0; }
      else if(mD == aD)                { c3 = (mD > 0 ? "aligned up, no fresh x" : "aligned down, no fresh x"); sc3 = -1; }
      else                               c3 = "mixed";
     }
   if(g_sum[g_chartSlot].ok)
     {
      int agoU = ChartBarsAgo(g_sum[g_chartSlot].vBrkT[1]);   // valid resistance broke -> up break
      int agoD = ChartBarsAgo(g_sum[g_chartSlot].vBrkT[0]);   // valid support broke    -> down break
      if(agoU < 0 && agoD < 0) c4 = "none in window";
      else if(agoD < 0 || (agoU >= 0 && agoU <= agoD)) { c4 = "UP break, " + IntegerToString(agoU) + "b ago"; sc4 = 1; }
      else                                              { c4 = "DOWN break, " + IntegerToString(agoD) + "b ago"; sc4 = 0; }
     }

   PSection("s3", x, ty, w, rh, "BREAKER STACK (context only)"); ty += rh + 6;                         // GAP 6
   PRow("c1", x, ty, w, "MACD " + IntegerToString(InpMacdFast) + "/" + IntegerToString(InpMacdSlow) + "/" + IntegerToString(InpMacdSignal), c1, sc1); ty += rh;
   PRow("c2", x, ty, w, "SMA" + IntegerToString(InpSmaPeriod) + " vs EMA" + IntegerToString(InpEmaPeriod), c2, sc2); ty += rh;
   PRow("c3", x, ty, w, "both crossed", c3, sc3); ty += rh;
   PRow("c4", x, ty, w, "TL break (3 closes)", c4, sc4); ty += rh + 6;                                 // GAP 7

   // --- READINESS (section + 4 rows) -------------------------------------------
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   bool spreadOK = (InpMaxSpreadPoints <= 0 || spr <= InpMaxSpreadPoints);
   double volRatio = VolumeRatioAt(1, InpVolAvgBars);
   bool haveVol = volRatio >= 0.0;
   bool volOK = haveVol && volRatio >= InpMinVolRatio;
   bool overallOK = spreadOK && volOK;

   // Source 1 Step 2: the MTF line sets the bias ("only looking for buys if above the MTF line")
   int cs = PeriodSeconds(_Period);
   int bSlot = (cs <= PeriodSeconds(PERIOD_H1)) ? 4 : (cs <= PeriodSeconds(PERIOD_H4)) ? 3 : g_chartSlot;
   if(!g_vis[bSlot]) bSlot = g_chartSlot;
   string bias = "no valid " + g_tfName[bSlot] + " line"; int sb = -1;
   int bu = FindLine(bSlot, 1, ROLE_PRIMARY), bd = FindLine(bSlot, -1, ROLE_PRIMARY);
   bool buV = bu >= 0 && g_lines[bu].state == ST_VALID, bdV = bd >= 0 && g_lines[bd].state == ST_VALID;
   datetime tb0 = iTime(_Symbol, PERIOD_CURRENT, 0);
   bool aboveU = buV && px >= RenderedValue(g_lines[bu], tb0);
   bool belowD = bdV && px <= RenderedValue(g_lines[bd], tb0);
   if(aboveU && belowD)  bias = "inside " + g_tfName[bSlot] + " wedge";
   else if(aboveU)       { bias = "BUYS (above " + g_tfName[bSlot] + " UP)"; sb = 1; }
   else if(belowD)       { bias = "SELLS (below " + g_tfName[bSlot] + " DN)"; sb = 0; }

   PSection("s4", x, ty, w, rh, "READINESS"); ty += rh + 6;                                            // GAP 8
   PRow("r1", x, ty, w, "spread", (string)spr + " / " + (string)InpMaxSpreadPoints, spreadOK ? 1 : 0); ty += rh;
   PRow("r2", x, ty, w, "volume",
        !haveVol ? "n/a" : DoubleToString(volRatio, 2) + "x / " + DoubleToString(InpMinVolRatio, 2) + "x",
        !haveVol ? -1 : (volOK ? 1 : 0)); ty += rh;
   PRow("r3", x, ty, w, "MTF bias", bias, sb); ty += rh;
   PRow("r4", x, ty, w, "OVERALL", overallOK ? "READY" : "WAIT", overallOK ? 1 : 0); ty += rh + 6;    // GAP 9
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
  {
   Tick();
   return(rates_total);
  }
void OnTimer()
  {
   Tick();
  }
void Tick()
  {
   bool changed = RefreshTFs();
   datetime b0 = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(changed || (b0 != 0 && b0 != g_lastChartBar))
     {
      g_lastChartBar = b0;
      DrawAll();
      ChartRedraw(0);
     }
   if(TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      RefreshLabels();   // autoscale moves with price, so the on-screen angle is re-measured every second
      DrawPanel();       // handles InpShowPanel=false itself (watermark kept, panel objects removed)
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
//| Zoom/scroll/resize changes the on-screen angle; a panel drag must  |
//| stick. Without the drag handler the next redraw would snap the     |
//| panel back to g_panX/g_panY.                                        |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      RefreshLabels();
      ChartRedraw(0);
     }
   else if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_pp + "bg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      if(InpShowPanel) DrawPanel();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
