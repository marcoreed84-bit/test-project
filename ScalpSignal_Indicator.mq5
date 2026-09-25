//+------------------------------------------------------------------+
//|                                        ScalpSignal_Indicator.mq5 |
//|                                                                  |
//|  WHAT THIS IS: a chart-window VISUAL SCALPING AID for manual     |
//|  GOLD/XAUUSD scalping on M5 or M15 - NOT an Expert Advisor. It   |
//|  contains ZERO trade-execution code (no OrderSend/CTrade calls,  |
//|  no position management, nothing that can touch a real account). |
//|  It draws buy/sell entry arrows, exit arrows/dots, a P/L caption |
//|  per closed trade, the session VWAP, the relevant moving         |
//|  averages, and a live "ready to scalp" panel - purely so the     |
//|  person at the chart can decide, by hand, whether to take a      |
//|  trade the way this project's own EAs already would.             |
//|                                                                  |
//|  WHOSE LOGIC THIS PORTS: the real, currently-shipped Aurelius    |
//|  entry gate and exit rules - Aurelius_EA.mq5's own defaults when |
//|  attached to an M5 chart, Aurelius_M15_EA.mq5's own (materially  |
//|  different) defaults when attached to an M15 chart, auto-        |
//|  detected from _Period at OnInit(). Every threshold below is a   |
//|  literal copy of that timeframe's own shipped input default, not |
//|  a new guess - see g_eff's assignment in OnInit() and the M15_*  |
//|  #define block for the exact M15 values. Any other timeframe is  |
//|  refused outright (Experts-log error + a chart Comment() banner) |
//|  rather than silently running unvalidated logic on it.           |
//|                                                                  |
//|  NOT PORTED, ON PURPOSE: InpUseMomentum (MACD-histogram-turning  |
//|  entry filter). Real MT5 testing on live Aurelius (both M5 and   |
//|  M15, 2026-09-24, see Aurelius_EA.mq5/Aurelius_M15_EA.mq5's own  |
//|  headers) found it cuts trade count ~61-65% and net profit       |
//|  ~40-62% - REJECTED, shipped OFF on both real EAs. It never gates|
//|  an arrow here either. The MACD histogram is still shown on the  |
//|  panel, clearly labeled "context only", per the user's own       |
//|  request to see it - it just never decides whether a trade would |
//|  have been taken. The same informational, non-gating treatment   |
//|  is given to a Stochastic(5,3,3) reading, ported from Ratchet_    |
//|  EA.mq5's own real construction (iStochastic with InpStochK=5,   |
//|  InpStochD=3, InpStochSlow=3, MODE_SMA, STO_LOWHIGH) - it is not  |
//|  part of Aurelius's own validated gate at all, so it is shown for |
//|  context (overbought/oversold zone) only, never folded into the   |
//|  hard "ready" light.                                              |
//|                                                                  |
//|  HISTORICAL MARKUP DISCIPLINE: OnCalculate() walks bars strictly |
//|  forward in time, maintaining real single-position state (flat / |
//|  long / short) exactly like this project's own Python simulator  |
//|  (research/aurelius/sim.py) - never a per-bar signal check done  |
//|  in isolation. A naive "was the gate true on this bar" scan       |
//|  (ignoring position state) is a real, previously-hit bug class in |
//|  this project (see MSG_Trader_EA.mq5's v1.13->v1.15 history) and  |
//|  produces a materially misleading picture. An arrow is drawn AT   |
//|  the bar whose own close made the decision knowable - never using |
//|  anything from a later bar. The one deliberate difference from    |
//|  sim.py: sim.py fills a decision at the NEXT bar's open purely for |
//|  backtest realism (it says so in its own docstring); this is a     |
//|  chart aid, not a fill simulator, so each arrow's caption/pnl uses  |
//|  that SAME bar's own close as both the trigger evidence and the     |
//|  fixed-lot price - simpler, still zero lookahead, and matches this   |
//|  file's own literal design brief ("a signal drawn at bar i must only  |
//|  use information knowable at bar i's own close").                      |
//|                                                                  |
//|  PNL LABEL CONVENTION: every dollar figure this file draws or      |
//|  totals ($ next to an exit arrow, the panel's "total pnl" row) is   |
//|  (exit price - entry price) in raw price units, i.e. this project's  |
//|  own established "$ = price move x 1.0 per 0.01 lot" fixed-lot-       |
//|  equivalent convention (see Aurelius_EA.mq5's own header, e.g. the     |
//|  ablation table's "net=$2587.24" figures) - NOT a live account-         |
//|  currency amount, and it includes no spread, swap or commission.         |
//|                                                                  |
//|  A stop-loss is checked two ways: against each historical bar's    |
//|  OWN high/low once that bar is fully closed (matching the resting-  |
//|  order behaviour sim.py models), AND, for whichever bar is still     |
//|  forming right now, against the LIVE bid/ask on every tick - a real   |
//|  broker-side stop is continuous, not bar-gated, and this is the one    |
//|  place "live tick data" legitimately drives the historical markup      |
//|  itself (see OnCalculate()'s own comment) without it being lookahead.   |
//|                                                                  |
//|  NOT MODELLED: historical spread. MT5's standard OHLCV bar history  |
//|  does not carry a reliable per-bar spread series the way this        |
//|  project's real-tick research datasets do - InpMaxSpreadPoints is     |
//|  therefore enforced LIVE only (the panel's SPREAD row, using the       |
//|  symbol's current real spread), never against historical bars. This    |
//|  is a genuine, disclosed limitation of the platform's own indicator     |
//|  API for a chart-only tool, not an oversight - see the build report.    |
//|                                                                  |
//|  Bottom-left panel by default (InpPanelBottom=true, small InpPanelX/  |
//|  InpPanelY), reusing Aurelius_EA.mq5's own DrawPanel() positioning      |
//|  math verbatim (g_panX = InpPanelX always; g_panY, when InpPanelBottom  |
//|  is true, is ChartHeight - bodyH - InpPanelY - i.e. anchored to the      |
//|  bottom-left corner, not guessed).                                       |
//|                                                                  |
//|  One bull market, one instrument, one discretionary trader at the   |
//|  keyboard. This draws pictures and a light; it never sends an order. |
//|                                                                  |
//|  RESEARCH NOTE (2026-09-25): before this file was reworked for M1  |
//|  scalping, three real-data M1 constructions were tested on the      |
//|  real GOLD# M1 export (300k bars, 2025-11-12 -> 2026-09-18):         |
//|   1) Price/VWAP-band re-entry + Stochastic(5,3,3) reversal (the       |
//|      user's own described chart pattern) - wide AND M1-tight-tuned     |
//|      parameters, 48 total configurations, ALL net negative, PF          |
//|      0.70-0.88. A clean rejection, not a tuning problem.                 |
//|   2) Aurelius's own real trend+bounce trigger, unfiltered, on M1:         |
//|      5.19 real triggers/day (in the user's 5-15/day target) but PF        |
//|      only 1.118 with OOS nearly flat (4.70 of 99.28 net) - decaying,       |
//|      not a real edge.                                                       |
//|   3) Same trigger + Ratchet_EA.mq5's real wick-reject filter                 |
//|      (InpWickRejectRatio=1.5): positive in 4/4 walk-forward blocks but        |
//|      frequency collapses to 0.65/day (net $10 over 310 days) - too thin        |
//|      and far too rare to be the scalp signal asked for.                         |
//|  VERDICT: no construction tested this session clears a real, robust              |
//|  edge at scalp frequency. The VWAP outer bands below are therefore drawn          |
//|  as a DISCRETIONARY VISUAL REFERENCE ONLY (matching the user's own chart           |
//|  example), same non-gating treatment as the Stochastic/MACD readouts above -        |
//|  never folded into the ready light or an arrow's trigger condition.                  |
//+------------------------------------------------------------------+
#property copyright "ScalpSignal"
#property version   "1.01"
#property description "Visual scalping aid (no trade execution) porting Aurelius's real M5/M15 entry-exit logic"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0
#property strict

//+------------------------------------------------------------------+
//| Enums - mirror Aurelius_EA.mq5's own, so the port is traceable    |
//+------------------------------------------------------------------+
enum ENUM_ALIGN
  {
   ALIGN_FULL  = 0,   // 21>50>150>600>2400
   ALIGN_MID   = 1,   // 21>50>150>600 + price vs 2400
   ALIGN_FAST  = 2,   // 21>50>150 + price vs 2400
   ALIGN_PRICE = 3    // 21>50 + price vs 2400
  };
enum ENUM_PBMA   { PB_21 = 0, PB_50 = 1, PB_150 = 2 };

//+------------------------------------------------------------------+
//| Aurelius_M15_EA.mq5's own real shipped defaults (2026-09-24 read |
//| of that file) - hardcoded, not inputs, because MQL5 inputs can   |
//| only carry ONE compiled default and this indicator must be able  |
//| to switch its whole threshold set at OnInit() based on _Period.  |
//| See "CORE SIGNAL" input group below for the M5 side (those ARE   |
//| inputs, since Aurelius_EA.mq5's own file is this file's primary  |
//| default) and the report's own note on this genuine MQL5 limit.   |
//+------------------------------------------------------------------+
#define M15_P21               30
#define M15_M21               MODE_EMA
#define M15_P150              150
#define M15_M150              MODE_EMA
#define M15_P600              200
#define M15_M600              MODE_SMMA
#define M15_P2400             1200
#define M15_M2400             MODE_EMA
#define M15_PULLBACK_MA       PB_21
#define M15_MIN_SLOPE_ATR     0.20
#define M15_MAX_SLOPE_ATR     1.25
#define M15_MIN_VOL_RATIO     1.30
#define M15_USE_SLOPE_SR_BLOCK true
#define M15_SLOPE_SR_BLOCK_SLOPE 1.00
#define M15_SLOPE_SR_BLOCK_SR    6.00

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "=== CORE SIGNAL (M5 = Aurelius_EA.mq5's own real defaults, shown here; auto-REPLACED with Aurelius_M15_EA.mq5's own real defaults the instant this loads on an M15 chart - see OnInit()/g_eff) ==="
input int              InpP21              = 21;          // MA 21 period (M5 default; M15 auto-uses 30)
input ENUM_MA_METHOD   InpM21              = MODE_EMA;     // MA 21 method
input int              InpP50              = 50;           // MA 50 period (same on M5 and M15)
input ENUM_MA_METHOD   InpM50              = MODE_EMA;      // MA 50 method
input int              InpP150             = 250;            // MA 150 period (M5 default; M15 auto-uses 150)
input ENUM_MA_METHOD   InpM150             = MODE_SMA;        // MA 150 method (M5 default; M15 auto-uses EMA)
input int              InpP600             = 500;              // MA 600 period (M5 default; M15 auto-uses 200)
input ENUM_MA_METHOD   InpM600             = MODE_SMMA;         // MA 600 method (same on M5 and M15)
input int              InpP2400            = 2400;               // MA 2400 period (M5 default; M15 auto-uses 1200)
input ENUM_MA_METHOD   InpM2400            = MODE_EMA;            // MA 2400 method
input ENUM_APPLIED_PRICE InpPrice          = PRICE_CLOSE;          // Applied price (all MAs)
input ENUM_ALIGN       InpAlignMode        = ALIGN_MID;             // Alignment requirement (same on M5 and M15)
input ENUM_PBMA        InpPullbackMA       = PB_50;                  // Pullback-touch MA (M5 default; M15 auto-uses PB_21)
input double           InpPullbackTolATR   = 0.25;                   // Touch tolerance (x ATR)
input int              InpPullbackBars     = 10;                      // Bars allowed from touch to entry
input bool             InpUseSlope         = true;                     // Require a minimum 50-slope
input int              InpSlopeBars        = 20;                        // Bars used for the slope
input double           InpMinSlopeATR      = 0.40;                       // Min slope, x ATR (M5 default; M15 auto-uses 0.20) - REAL-CONFIRMED per-timeframe, see the EA headers
input double           InpMaxSlopeATR      = 1.00;                        // Max slope, x ATR, 0=off (M5 default; M15 auto-uses 1.25)
input bool             InpUseCrossFilter   = true;                         // Block after repeated 21/50 crossings
input int              InpCrossWindow      = 10;                            // Cross lookback (bars)
input int              InpMaxCrosses       = 1;                              // Max crossings allowed
input int              InpCooldownBars     = 5;                               // Bars to wait after a close before a new entry
input bool             InpUseVolume        = true;                             // Require above-average tick volume
input int              InpVolAvgBars       = 100;                               // Bars for the volume average
input double           InpMinVolRatio      = 1.25;                               // Min volume vs that average (M5 default; M15 auto-uses 1.30)
input bool             InpUseSRDist        = true;                                // Skip entries sitting on a previous-days S/R level
input int              InpSRDays           = 3;                                    // Previous completed days used for the level
input double           InpMinSRDistATR     = 1.50;                                  // Min distance from that level, x ATR
input bool             InpUseStopLoss      = true;                                   // Model a protective stop
input double           InpStopATR          = 2.5;                                     // Stop distance, x entry ATR
input bool             InpUsePrice21Exit   = false;                                    // Exit as soon as price closes back through the 21 (Aurelius ships this OFF on both M5 and M15 - see headers)
input double           InpPrice21BufferATR = 0.7;                                       // "Through" buffer, x ATR
input int              InpPrice21ConfirmBars = 8;                                        // Consecutive closed bars required
input bool             InpUseVwapExit      = true;                                        // Exit as soon as price closes back through session VWAP (Aurelius ships this ON on both M5 and M15)
input double           InpVwapBufferATR    = 0.2;                                          // "Through" buffer, x ATR
input int              InpVwapConfirmBars  = 8;                                             // Consecutive closed bars required
input bool             InpAllowBuys        = true;                                           // Allow long signals
input bool             InpAllowSells       = true;                                            // Allow short signals

input group "=== Safety / history window ==="
input int              InpMaxSpreadPoints  = 60;      // LIVE-only spread gate for the panel's READY light (matches Aurelius's own real default) - historical bars carry no reliable spread series, see header
input int              InpMaxHistoryBars   = 3000;     // How far back to walk and draw real past trades (bounded, like InpMAHistoryBars in the EAs - keeps chart-object count sane on a long-running attach)

input group "=== Momentum context (INFORMATIONAL ONLY - never gates an arrow or the ready light) ==="
input bool             InpShowMomentum     = true;      // Show the MACD(12,26,9) histogram-turning reading on the panel

input group "=== Stochastic context (INFORMATIONAL ONLY - ported from Ratchet_EA.mq5's real construction, never gates an arrow or the ready light) ==="
input bool             InpShowStoch        = true;
input int              InpStochK           = 5;          // %K period - Ratchet_EA.mq5's own real value
input int              InpStochD           = 3;           // %D period
input int              InpStochSlow        = 3;            // %K slowing
input ENUM_MA_METHOD   InpStochMeth        = MODE_SMA;      // Stochastic method
input ENUM_STO_PRICE   InpStochPrice       = STO_LOWHIGH;    // Stochastic price mode
input bool             InpStochUseSignal   = true;            // Read %D (signal) rather than %K (main) - matches Ratchet's own InpUseSignal default
input double           InpStochOBLevel     = 80.0;             // Overbought zone (informational display only)
input double           InpStochOSLevel     = 20.0;              // Oversold zone (informational display only)

input group "=== Chart visuals ==="
input bool             InpShowMAs          = true;
input color             InpCol21    = clrYellow;
input color             InpCol50    = C'255,140,0';
input color             InpCol150   = C'191,0,255';
input color             InpCol600   = C'255,20,147';
input color             InpCol2400  = C'57,255,20';
input bool              InpShowVWAP = true;
input color             InpColVWAP  = C'0,255,255';
input bool              InpShowVWAPBands = true;    // Draw VWAP's outer deviation bands (informational only - see SessionVWAPBand()'s own comment; not a validated entry signal)
input double            InpVWAPBandK     = 2.0;     // Band width, x volume-weighted stdev from VWAP (standard convention, matches research/vwap_band_stoch_test.py's default)
input color             InpColVWAPBand   = C'0,150,150';
input color             InpColBuyArrow  = C'0,230,118';
input color             InpColSellArrow = C'255,61,90';
input color             InpColExitWin   = C'0,230,118';
input color             InpColExitLoss  = C'255,61,90';
input int               InpArrowSize    = 2;

input group "=== Dashboard (default BOTTOM-LEFT, matching Aurelius_EA.mq5's own positioning math) ==="
input bool    InpShowPanel  = true;
input int     InpPanelDrag  = 1;                 // 0 = locked, 1 = draggable
input int     InpPanelX     = 12;                // X offset from the left edge (Aurelius's own math never anchors X by the Bottom flag)
input int     InpPanelY     = 30;                // Y offset - from the BOTTOM edge when InpPanelBottom=true
input bool    InpPanelBottom = true;             // Anchor the panel to the bottom-left corner (this file's own default - differs from the EAs' top-left default, per explicit request)
input int     InpPanelW     = 260;
input color   InpPanelBg    = C'13,17,28';
input color   InpHeaderBg   = C'28,36,58';
input color   InpPanelEdge  = C'255,196,84';
input color   InpTitleCol   = C'255,196,84';
input color   InpSectionCol = C'214,226,238';
input color   InpTextCol    = C'150,166,192';
input color   InpValCol     = C'236,242,252';
input color   InpOkCol      = C'0,230,118';
input color   InpNoCol      = C'255,61,90';
input color   InpShadowCol  = C'6,8,14';
input string  InpPanelFont  = "Consolas";
input int     InpPanelSize  = 8;
input string  InpWatermark  = "SCALPSIGNAL";
input color   InpWaterCol   = C'46,38,24';

//+------------------------------------------------------------------+
//| Effective (auto-detected) parameter set - see OnInit()            |
//+------------------------------------------------------------------+
struct EffParams
  {
   int    p21;  ENUM_MA_METHOD m21;
   int    p50;  ENUM_MA_METHOD m50;
   int    p150; ENUM_MA_METHOD m150;
   int    p600; ENUM_MA_METHOD m600;
   int    p2400;ENUM_MA_METHOD m2400;
   ENUM_APPLIED_PRICE price;
   ENUM_ALIGN alignMode;
   ENUM_PBMA  pullbackMA;
   double pullbackTolATR; int pullbackBars;
   bool   useSlope; int slopeBars; double minSlopeATR; double maxSlopeATR;
   bool   useCrossFilter; int crossWindow; int maxCrosses; int cooldownBars;
   bool   useVolume; int volAvgBars; double minVolRatio;
   bool   useSRDist; int srDays; double minSRDistATR;
   bool   useSlopeSRBlock; double slopeSRBlockSlope; double slopeSRBlockSR;
   bool   useStopLoss; double stopATR;
   bool   usePrice21Exit; double price21BufferATR; int price21ConfirmBars;
   bool   useVwapExit; double vwapBufferATR; int vwapConfirmBars;
   bool   allowBuys; bool allowSells;
   string sourceName;
  };
EffParams g_eff;
bool      g_supported = false;

//+------------------------------------------------------------------+
//| Handles / object prefixes / state                                |
//+------------------------------------------------------------------+
int h21=INVALID_HANDLE, h50=INVALID_HANDLE, h150=INVALID_HANDLE;
int h600=INVALID_HANDLE, h2400=INVALID_HANDLE, hMACD=INVALID_HANDLE, hSto=INVALID_HANDLE;

string g_pp = "SSIP_";   // panel
string g_pm = "SSIM_";   // MA/VWAP per-bar segments
string g_pa = "SSIA_";   // trade arrows/captions
string g_pw = "SSIW_";   // watermark

datetime g_lastProcessedBarTime = 0;
int      g_backfillStartShift   = 0;

// sequential single-position walk state
int      g_posDir = 0;          // 0 flat, +1 long, -1 short
double   g_posEntryPx = 0.0, g_posEntryATR = 0.0, g_posStopPx = 0.0;
datetime g_posEntryTime = 0;
int      g_posEntryBarShiftAtOpen = 0;
int      g_barsSinceClose = 1000000;
int      g_price21Bad = 0, g_vwapBad = 0;

// running stats (since attach)
int      g_statTrades = 0, g_statWins = 0;
double   g_statTotalPnl = 0.0;

// ATR history cache
double   g_atrHist[]; int g_atrHistCount = 0;

// SR-per-day cache
int      g_srCacheDayKey = -1; bool g_srCacheOK = false;
double   g_srCacheHi = 0.0, g_srCacheLo = 0.0;

// panel self-learning width
int      g_panelMinW = 0;
bool     g_panelReclaim = true;
int      g_panX = -1, g_panY = -1;
bool     g_bgWatermarkDone = false;

// throttle
datetime g_lastPanelDraw = 0;
bool     g_skipCosmeticDraws = false;

//+------------------------------------------------------------------+
//| Forward declarations                                             |
//+------------------------------------------------------------------+
bool MA(const int handle, const int shift, double &out);
bool BufVal(const int handle, const int bufIdx, const int shift, double &out);
void ComputeWilderATR(const MqlRates &arr[], double &out[], int period);
bool ATRAt(const int shift, double &atr);
double SessionVWAP(const int shift);
bool AlignedAt(const int shift, const bool isBuy);
double PullbackLineAt(const int shift);
double SlopeATRAt(const int shift, const bool isBuy);
int    CrissCrossAt(const int shift);
bool   PullbackOKAt(const int shift, const bool isBuy);
double VolumeRatioAt(const int shift);
bool   SRForShift(const int shift, double &hi, double &lo);
double SRDistanceATRAt(const int shift, const bool isBuy, const double atr);
void   DrawPanel();
void   PWatermark();

//+------------------------------------------------------------------+
int OnInit()
  {
   ENUM_TIMEFRAMES per = (ENUM_TIMEFRAMES)_Period;
   if(per != PERIOD_M5 && per != PERIOD_M15)
     {
      g_supported = false;
      PrintFormat("ScalpSignal_Indicator: UNSUPPORTED timeframe %s - this indicator ports Aurelius_EA.mq5 (M5) / Aurelius_M15_EA.mq5 (M15) real logic only. Attach it to an M5 or M15 GOLD chart.",
                  EnumToString(per));
      Comment("ScalpSignal_Indicator: only validated for M5 or M15 - not running on ", EnumToString(per));
      IndicatorSetString(INDICATOR_SHORTNAME, "ScalpSignal (UNSUPPORTED TF)");
      return(INIT_SUCCEEDED);
     }
   g_supported = true;
   Comment("");

   if(per == PERIOD_M5)
     {
      g_eff.p21=InpP21; g_eff.m21=InpM21;
      g_eff.p50=InpP50; g_eff.m50=InpM50;
      g_eff.p150=InpP150; g_eff.m150=InpM150;
      g_eff.p600=InpP600; g_eff.m600=InpM600;
      g_eff.p2400=InpP2400; g_eff.m2400=InpM2400;
      g_eff.price=InpPrice;
      g_eff.alignMode=InpAlignMode;
      g_eff.pullbackMA=InpPullbackMA;
      g_eff.minSlopeATR=InpMinSlopeATR; g_eff.maxSlopeATR=InpMaxSlopeATR;
      g_eff.minVolRatio=InpMinVolRatio;
      g_eff.useSlopeSRBlock=false; g_eff.slopeSRBlockSlope=0.0; g_eff.slopeSRBlockSR=0.0;
      g_eff.sourceName="Aurelius_EA.mq5 (M5)";
     }
   else // PERIOD_M15
     {
      g_eff.p21=M15_P21; g_eff.m21=M15_M21;
      g_eff.p50=InpP50; g_eff.m50=InpM50;              // identical on both files
      g_eff.p150=M15_P150; g_eff.m150=M15_M150;
      g_eff.p600=M15_P600; g_eff.m600=M15_M600;
      g_eff.p2400=M15_P2400; g_eff.m2400=InpM2400;      // method EMA on both, period differs
      g_eff.price=InpPrice;                              // PRICE_CLOSE on both
      g_eff.alignMode=InpAlignMode;                        // ALIGN_MID on both
      g_eff.pullbackMA=M15_PULLBACK_MA;
      g_eff.minSlopeATR=M15_MIN_SLOPE_ATR; g_eff.maxSlopeATR=M15_MAX_SLOPE_ATR;
      g_eff.minVolRatio=M15_MIN_VOL_RATIO;
      g_eff.useSlopeSRBlock=M15_USE_SLOPE_SR_BLOCK;
      g_eff.slopeSRBlockSlope=M15_SLOPE_SR_BLOCK_SLOPE; g_eff.slopeSRBlockSR=M15_SLOPE_SR_BLOCK_SR;
      g_eff.sourceName="Aurelius_M15_EA.mq5 (M15)";
     }
   // shared across both real files, unchanged
   g_eff.pullbackTolATR=InpPullbackTolATR; g_eff.pullbackBars=InpPullbackBars;
   g_eff.useSlope=InpUseSlope; g_eff.slopeBars=InpSlopeBars;
   g_eff.useCrossFilter=InpUseCrossFilter; g_eff.crossWindow=InpCrossWindow;
   g_eff.maxCrosses=InpMaxCrosses; g_eff.cooldownBars=InpCooldownBars;
   g_eff.useVolume=InpUseVolume; g_eff.volAvgBars=InpVolAvgBars;
   g_eff.useSRDist=InpUseSRDist; g_eff.srDays=InpSRDays; g_eff.minSRDistATR=InpMinSRDistATR;
   g_eff.useStopLoss=InpUseStopLoss; g_eff.stopATR=InpStopATR;
   g_eff.usePrice21Exit=InpUsePrice21Exit; g_eff.price21BufferATR=InpPrice21BufferATR;
   g_eff.price21ConfirmBars=InpPrice21ConfirmBars;
   g_eff.useVwapExit=InpUseVwapExit; g_eff.vwapBufferATR=InpVwapBufferATR;
   g_eff.vwapConfirmBars=InpVwapConfirmBars;
   g_eff.allowBuys=InpAllowBuys; g_eff.allowSells=InpAllowSells;

   h21   = iMA(_Symbol, PERIOD_CURRENT, g_eff.p21,   0, g_eff.m21,   g_eff.price);
   h50   = iMA(_Symbol, PERIOD_CURRENT, g_eff.p50,   0, g_eff.m50,   g_eff.price);
   h150  = iMA(_Symbol, PERIOD_CURRENT, g_eff.p150,  0, g_eff.m150,  g_eff.price);
   h600  = iMA(_Symbol, PERIOD_CURRENT, g_eff.p600,  0, g_eff.m600,  g_eff.price);
   h2400 = iMA(_Symbol, PERIOD_CURRENT, g_eff.p2400, 0, g_eff.m2400, g_eff.price);
   hMACD = iMACD(_Symbol, PERIOD_CURRENT, 12, 26, 9, PRICE_CLOSE);
   hSto  = iStochastic(_Symbol, PERIOD_CURRENT, InpStochK, InpStochD, InpStochSlow, InpStochMeth, InpStochPrice);
   if(h21==INVALID_HANDLE || h50==INVALID_HANDLE || h150==INVALID_HANDLE ||
      h600==INVALID_HANDLE || h2400==INVALID_HANDLE || hMACD==INVALID_HANDLE || hSto==INVALID_HANDLE)
     {
      Print("ScalpSignal_Indicator: failed to create an indicator handle. Error ", GetLastError());
      return(INIT_FAILED);
     }

   IndicatorSetString(INDICATOR_SHORTNAME, "ScalpSignal (" + g_eff.sourceName + ")");
   PrintFormat("ScalpSignal_Indicator: attached on %s, porting %s. MA21=%d/%s MA150=%d/%s MA600=%d/%s MA2400=%d/%s pullback=%s minSlope=%.2f maxSlope=%.2f minVol=%.2f slopeSRBlock=%s stopATR=%.1f price21Exit=%s vwapExit=%s",
               EnumToString(per), g_eff.sourceName,
               g_eff.p21, EnumToString(g_eff.m21), g_eff.p150, EnumToString(g_eff.m150),
               g_eff.p600, EnumToString(g_eff.m600), g_eff.p2400, EnumToString(g_eff.m2400),
               EnumToString(g_eff.pullbackMA), g_eff.minSlopeATR, g_eff.maxSlopeATR, g_eff.minVolRatio,
               (g_eff.useSlopeSRBlock?"on":"off"), g_eff.stopATR,
               (g_eff.usePrice21Exit?"on":"off"), (g_eff.useVwapExit?"on":"off"));

   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pm);
   ObjectsDeleteAll(0, g_pa);
   ObjectsDeleteAll(0, g_pw);
   Comment("");
  }
//+------------------------------------------------------------------+
//| Buffer helpers - identical to Aurelius_EA.mq5's own               |
//+------------------------------------------------------------------+
bool MA(const int handle, const int shift, double &out)
  {
   double b[]; ArraySetAsSeries(b, true);
   if(CopyBuffer(handle, 0, shift, 1, b) < 1) return(false);
   out = b[0]; return(true);
  }
bool BufVal(const int handle, const int bufIdx, const int shift, double &out)
  {
   double b[]; ArraySetAsSeries(b, true);
   if(CopyBuffer(handle, bufIdx, shift, 1, b) < 1) return(false);
   out = b[0]; return(true);
  }
//+------------------------------------------------------------------+
//| Manual Wilder ATR - ported VERBATIM from Aurelius_EA.mq5          |
//| (this broker's iATR() is a plain SMA of True Range, not Wilder-    |
//| smoothed, despite MT5's own docs - see that file's v1.36 note).    |
//+------------------------------------------------------------------+
void ComputeWilderATR(const MqlRates &arr[], double &out[], int period)
  {
   int n = ArraySize(arr);
   ArrayResize(out, n);
   for(int i = 0; i < n; i++) out[i] = EMPTY_VALUE;
   if(n <= period) return;
   double tr[]; ArrayResize(tr, n);
   tr[0] = arr[0].high - arr[0].low;
   for(int i = 1; i < n; i++)
      tr[i] = MathMax(arr[i].high - arr[i].low,
              MathMax(MathAbs(arr[i].high - arr[i-1].close), MathAbs(arr[i].low - arr[i-1].close)));
   double seed = 0;
   for(int i = 1; i <= period; i++) seed += tr[i];
   out[period] = seed / period;
   for(int i = period + 1; i < n; i++)
      out[i] = (out[i-1] * (period - 1) + tr[i]) / period;
  }
//+------------------------------------------------------------------+
//| One bulk fetch covering the whole InpMaxHistoryBars window, same  |
//| got-shift index mapping Aurelius_EA.mq5's own BackfillMALines()   |
//| uses for its pullback band (iA = got-(s+1), iB = got-s) - reused   |
//| here as ATRAt(shift) = g_atrHist[g_atrHistCount - shift].          |
//+------------------------------------------------------------------+
void RebuildATRSeries()
  {
   int avail = Bars(_Symbol, PERIOD_CURRENT);
   int need = MathMin(InpMaxHistoryBars, MathMax(1, avail - 2)) + 550;
   MqlRates rr[]; ArraySetAsSeries(rr, false);
   int got = CopyRates(_Symbol, PERIOD_CURRENT, 1, need, rr);
   if(got < 14 + 2) { g_atrHistCount = 0; return; }
   ComputeWilderATR(rr, g_atrHist, 14);
   g_atrHistCount = got;
  }
bool ATRAt(const int shift, double &atr)
  {
   if(g_atrHistCount <= 0) return(false);
   int idx = g_atrHistCount - shift;
   if(idx < 0 || idx >= g_atrHistCount) return(false);
   double v = g_atrHist[idx];
   if(v == EMPTY_VALUE || v <= 0.0) return(false);
   atr = v; return(true);
  }
//+------------------------------------------------------------------+
//| Session VWAP - ported VERBATIM from Aurelius_EA.mq5's             |
//| SessionVWAP(shift). Already fully shift-parameterised, so it      |
//| works unchanged for any historical shift, not just "now".         |
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
//| Session VWAP outer bands - VWAP +/- k * session-cumulative        |
//| volume-weighted stdev of typical price from VWAP. Same session    |
//| reset/window as SessionVWAP() above (duplicated rather than       |
//| refactored to share it, to keep both functions independently      |
//| shift-safe). Matches research/vwap_band_stoch_test.py's real      |
//| vwap_bands() construction, tested on real GOLD M15/M1 data         |
//| 2026-09-25 - informational display only, NOT a validated entry    |
//| signal (all 48 tested configurations came back net negative,      |
//| PF 0.70-0.88 - see that script's own header for the real numbers).|
//| Drawn here purely because the user asked to see the same visual   |
//| their own chart example showed, not because it is a proven edge.  |
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
bool DifferentSession(const int shiftA, const int shiftB)
  {
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, shiftA);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, shiftB);
   if(tA == 0 || tB == 0) return(true);
   MqlDateTime dA, dB; TimeToStruct(tA, dA); TimeToStruct(tB, dB);
   return(dA.day != dB.day || dA.mon != dB.mon || dA.year != dB.year);
  }
//+------------------------------------------------------------------+
//| Alignment - ported VERBATIM from Aurelius_EA.mq5's Aligned(shift, |
//| isBuy). Already shift-parameterised.                              |
//+------------------------------------------------------------------+
bool AlignedAt(const int shift, const bool isBuy)
  {
   double m21,m50,m150,m600,m2400;
   if(!MA(h21,shift,m21) || !MA(h50,shift,m50) || !MA(h150,shift,m150) ||
      !MA(h600,shift,m600) || !MA(h2400,shift,m2400)) return(false);
   double c = iClose(_Symbol, PERIOD_CURRENT, shift);
   if(c <= 0.0) return(false);

   if(isBuy)
     {
      if(g_eff.alignMode == ALIGN_FULL) { if(!(m600 > m2400)) return(false); }
      else                              { if(!(c > m2400))    return(false); }
      if(!(m21 > m50)) return(false);
      if(g_eff.alignMode == ALIGN_PRICE) return(true);
      if(!(m50 > m150)) return(false);
      if(g_eff.alignMode == ALIGN_FAST) return(true);
      return(m150 > m600);
     }
   if(g_eff.alignMode == ALIGN_FULL) { if(!(m600 < m2400)) return(false); }
   else                              { if(!(c < m2400))    return(false); }
   if(!(m21 < m50)) return(false);
   if(g_eff.alignMode == ALIGN_PRICE) return(true);
   if(!(m50 < m150)) return(false);
   if(g_eff.alignMode == ALIGN_FAST) return(true);
   return(m150 < m600);
  }
//+------------------------------------------------------------------+
double PullbackLineAt(const int shift)
  {
   double v = 0.0;
   if(g_eff.pullbackMA == PB_21)       MA(h21,  shift, v);
   else if(g_eff.pullbackMA == PB_150) MA(h150, shift, v);
   else                                MA(h50,  shift, v);
   return(v);
  }
//+------------------------------------------------------------------+
//| Slope - generalised from Aurelius_EA.mq5's SlopeATR(isBuy), which |
//| always hardcoded shift=1; SLOPE_50 on both real files, so the      |
//| MA used is fixed to h50, same as both shipped EAs.                 |
//+------------------------------------------------------------------+
double SlopeATRAt(const int shift, const bool isBuy)
  {
   double now, then, atr;
   if(!MA(h50, shift, now) || !MA(h50, shift + g_eff.slopeBars, then) ||
      !ATRAt(shift, atr) || atr <= 0.0) return(0.0);
   double sl = (now - then) / atr;
   return(isBuy ? sl : -sl);
  }
//+------------------------------------------------------------------+
int CrissCrossAt(const int shift)
  {
   int n = 0;
   for(int j = shift; j <= shift + g_eff.crossWindow - 1; j++)
     {
      double a1,b1,a2,b2;
      if(!MA(h21,j,a1) || !MA(h50,j,b1) || !MA(h21,j+1,a2) || !MA(h50,j+1,b2))
         return(999);
      if((a1 > b1) != (a2 > b2)) n++;
     }
   return(n);
  }
//+------------------------------------------------------------------+
bool PullbackOKAt(const int shift, const bool isBuy)
  {
   double atr;
   if(!ATRAt(shift, atr) || atr <= 0.0) return(false);
   double tol = atr * g_eff.pullbackTolATR;
   double ln  = PullbackLineAt(shift);
   double c   = iClose(_Symbol, PERIOD_CURRENT, shift);
   if(isBuy  && c <= ln) return(false);
   if(!isBuy && c >= ln) return(false);
   for(int j = shift; j <= shift + g_eff.pullbackBars - 1; j++)
     {
      double lj = PullbackLineAt(j);
      if(isBuy  && iLow(_Symbol, PERIOD_CURRENT, j)  <= lj + tol) return(true);
      if(!isBuy && iHigh(_Symbol, PERIOD_CURRENT, j) >= lj - tol) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
double VolumeRatioAt(const int shift)
  {
   long vCur[]; ArraySetAsSeries(vCur, true);
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, shift, 1, vCur) < 1) return(-1.0);
   long vAvg[]; ArraySetAsSeries(vAvg, true);
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, shift + 1, g_eff.volAvgBars, vAvg) < g_eff.volAvgBars) return(-1.0);
   double sum = 0.0;
   for(int k = 0; k < g_eff.volAvgBars; k++) sum += (double)vAvg[k];
   double avg = sum / g_eff.volAvgBars;
   if(avg <= 0.0) return(-1.0);
   return((double)vCur[0] / avg);
  }
//+------------------------------------------------------------------+
//| S/R - generalised from Aurelius_EA.mq5's SRLevels()/SRDistanceATR |
//| ("previous N completed days" relative to THIS bar's own day, not  |
//| always "today"), cached per calendar day since the walk visits    |
//| many M5/M15 bars per D1 day.                                      |
//+------------------------------------------------------------------+
bool SRForShift(const int shift, double &hi, double &lo)
  {
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, shift);
   if(bt == 0) return(false);
   MqlDateTime dt; TimeToStruct(bt, dt);
   int key = dt.year * 10000 + dt.mon * 100 + dt.day;
   if(g_srCacheOK && key == g_srCacheDayKey) { hi = g_srCacheHi; lo = g_srCacheLo; return(true); }
   int d1idx = iBarShift(_Symbol, PERIOD_D1, bt, false);
   if(d1idx < 0) return(false);
   int n = MathMax(1, g_eff.srDays);
   double h = -DBL_MAX, l = DBL_MAX;
   for(int k = 1; k <= n; k++)
     {
      double dh = iHigh(_Symbol, PERIOD_D1, d1idx + k);
      double dl = iLow(_Symbol, PERIOD_D1, d1idx + k);
      if(dh <= 0.0 || dl <= 0.0) return(false);
      if(dh > h) h = dh;
      if(dl < l) l = dl;
     }
   g_srCacheDayKey = key; g_srCacheOK = true; g_srCacheHi = h; g_srCacheLo = l;
   hi = h; lo = l; return(true);
  }
double SRDistanceATRAt(const int shift, const bool isBuy, const double atr)
  {
   if(atr <= 0.0) return(-1.0);
   double hi, lo;
   if(!SRForShift(shift, hi, lo)) return(-1.0);
   double c = iClose(_Symbol, PERIOD_CURRENT, shift);
   return((isBuy ? MathAbs(hi - c) : MathAbs(c - lo)) / atr);
  }
//+------------------------------------------------------------------+
//| MA/VWAP segment drawing - same per-bar OBJ_TREND idiom as         |
//| Aurelius_EA.mq5's DrawMASegment()/PurgeOldMALines().               |
//+------------------------------------------------------------------+
void DrawMASegment(const string tag, const datetime tOld, const double vOld,
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
void PurgeOld(const string prefix, const datetime cutoff)
  {
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, prefix) != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot > 0 && ot < cutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
//| Trade markers - OBJ_ARROW + OBJ_TEXT (time/price anchored, same   |
//| family as Aurelius_EA.mq5's DrawLevelLine()/its MA segments -     |
//| chart objects, not indicator plot buffers, matching how this      |
//| project's other files already draw entry/level markers).          |
//+------------------------------------------------------------------+
void DrawArrowObj(const string nm, const datetime t, const double px, const int code,
                   const color col, const int anchor)
  {
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_ARROW, 0, t, px);
   ObjectSetInteger(0, nm, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpArrowSize);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
  }
void DrawCaption(const string nm, const datetime t, const double px, const string txt, const color col, const int anchor)
  {
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_TEXT, 0, t, px);
   ObjectSetString (0, nm, OBJPROP_TEXT, txt);
   ObjectSetString (0, nm, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
  }
//+------------------------------------------------------------------+
//| Sequential state machine                                          |
//+------------------------------------------------------------------+
void OpenSimPosition(const datetime bt, const double px, const int dir, const double atr, const int shiftNow)
  {
   g_posDir = dir;
   g_posEntryPx = px;
   g_posEntryATR = atr;
   g_posEntryTime = bt;
   g_posEntryBarShiftAtOpen = shiftNow;
   g_posStopPx = (g_eff.useStopLoss && atr > 0.0)
                 ? (dir > 0 ? px - g_eff.stopATR * atr : px + g_eff.stopATR * atr)
                 : 0.0;
   g_price21Bad = 0; g_vwapBad = 0;

   double offset = (atr > 0.0 ? atr * 0.15 : (px * 0.0005));
   double arrowPx = dir > 0 ? px - offset : px + offset;
   int code = dir > 0 ? 233 : 234;
   color col = dir > 0 ? InpColBuyArrow : InpColSellArrow;
   int anchor = dir > 0 ? ANCHOR_TOP : ANCHOR_BOTTOM;
   string tag = IntegerToString((long)bt);
   DrawArrowObj(g_pa + "en_" + tag, bt, arrowPx, code, col, anchor);
   double capPx = dir > 0 ? arrowPx - offset : arrowPx + offset;
   DrawCaption(g_pa + "et_" + tag, bt, capPx,
               (dir > 0 ? "BUY " : "SELL ") + DoubleToString(px, _Digits), col,
               dir > 0 ? ANCHOR_TOP : ANCHOR_BOTTOM);
  }
void CloseSimPosition(const datetime bt, const double px, const string reason)
  {
   if(g_posDir == 0) return;
   double pnl = (px - g_posEntryPx) * g_posDir;
   g_statTrades++;
   if(pnl > 0) g_statWins++;
   g_statTotalPnl += pnl;

   int code = 159; // filled circle
   color col = (pnl >= 0) ? InpColExitWin : InpColExitLoss;
   int anchor = (g_posDir > 0) ? ANCHOR_BOTTOM : ANCHOR_TOP;
   string tag = IntegerToString((long)bt) + "_" + IntegerToString((long)g_posEntryTime);
   DrawArrowObj(g_pa + "ex_" + tag, bt, px, code, col, ANCHOR_CENTER);
   double atr = (g_posEntryATR > 0.0) ? g_posEntryATR : (px * 0.0005);
   double capPx = (g_posDir > 0) ? px - atr * 0.15 : px + atr * 0.15;
   DrawCaption(g_pa + "et2_" + tag, bt, capPx,
               reason + " " + StringFormat("%+.2f", pnl), col, anchor);

   g_posDir = 0; g_posEntryPx = 0.0; g_posEntryATR = 0.0; g_posStopPx = 0.0;
   g_price21Bad = 0; g_vwapBad = 0;
  }
//+------------------------------------------------------------------+
//| One bar of the sequential walk - draws that bar's MA/VWAP segment |
//| (if enabled) then runs the real entry/exit gate on it. Exit       |
//| priority PRICE21 > VWAP > ALIGN_BREAK, then the resting stop      |
//| checked against that same bar's own high/low - identical order to |
//| research/aurelius/sim.py's simulate(), the project's own reference|
//| for this exact single-position, no-lookahead discipline.          |
//+------------------------------------------------------------------+
void WalkOneBar(const int s)
  {
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, s);
   if(bt == 0) return;
   datetime btPrev = iTime(_Symbol, PERIOD_CURRENT, s + 1);

   if(InpShowMAs && btPrev != 0)
     {
      double a,b;
      if(MA(h21,s+1,a)  && MA(h21,s,b))  DrawMASegment("21",  btPrev,a,bt,b,InpCol21);
      if(MA(h50,s+1,a)  && MA(h50,s,b))  DrawMASegment("50",  btPrev,a,bt,b,InpCol50);
      if(MA(h150,s+1,a) && MA(h150,s,b)) DrawMASegment("150", btPrev,a,bt,b,InpCol150);
      if(MA(h600,s+1,a) && MA(h600,s,b)) DrawMASegment("600", btPrev,a,bt,b,InpCol600);
      if(MA(h2400,s+1,a)&& MA(h2400,s,b))DrawMASegment("2400",btPrev,a,bt,b,InpCol2400);
     }
   if(InpShowVWAP && btPrev != 0 && !DifferentSession(s+1, s))
     {
      double vA = SessionVWAP(s+1), vB = SessionVWAP(s);
      if(vA > 0.0 && vB > 0.0) DrawMASegment("vwap", btPrev, vA, bt, vB, InpColVWAP);
     }
   if(InpShowVWAPBands && btPrev != 0 && !DifferentSession(s+1, s))
     {
      double uA, lA, uB, lB;
      bool okA = SessionVWAPBand(s+1, InpVWAPBandK, uA, lA);
      bool okB = SessionVWAPBand(s,   InpVWAPBandK, uB, lB);
      if(okA && okB)
        {
         DrawMASegment("vwapU", btPrev, uA, bt, uB, InpColVWAPBand);
         DrawMASegment("vwapL", btPrev, lA, bt, lB, InpColVWAPBand);
        }
     }

   double atr; if(!ATRAt(s, atr)) atr = 0.0;

   if(g_posDir != 0)
     {
      bool isBuy = g_posDir > 0;
      string exitReason = "";

      if(g_eff.usePrice21Exit && atr > 0.0)
        {
         double m21;
         if(MA(h21, s, m21))
           {
            double c = iClose(_Symbol, PERIOD_CURRENT, s);
            double buf = g_eff.price21BufferATR * atr;
            bool bad = isBuy ? (c < m21 - buf) : (c > m21 + buf);
            g_price21Bad = bad ? g_price21Bad + 1 : 0;
            if(g_price21Bad >= g_eff.price21ConfirmBars) exitReason = "PRICE21";
           }
         else g_price21Bad = 0;
        }

      if(exitReason == "" && g_eff.useVwapExit)
        {
         double vw = SessionVWAP(s);
         if(vw > 0.0 && atr > 0.0)
           {
            double c = iClose(_Symbol, PERIOD_CURRENT, s);
            double buf = g_eff.vwapBufferATR * atr;
            bool bad = isBuy ? (c < vw - buf) : (c > vw + buf);
            g_vwapBad = bad ? g_vwapBad + 1 : 0;
            if(g_vwapBad >= g_eff.vwapConfirmBars) exitReason = "VWAP";
           }
         else g_vwapBad = 0;
        }

      if(exitReason == "")
        {
         if(!AlignedAt(s, isBuy)) exitReason = "ALIGN_BREAK";
        }

      if(exitReason != "")
        {
         double exitPx = iClose(_Symbol, PERIOD_CURRENT, s);
         CloseSimPosition(bt, exitPx, exitReason);
         g_barsSinceClose = 0;
         return;
        }

      if(g_eff.useStopLoss && g_posStopPx > 0.0)
        {
         bool hit = isBuy ? (iLow(_Symbol, PERIOD_CURRENT, s) <= g_posStopPx)
                           : (iHigh(_Symbol, PERIOD_CURRENT, s) >= g_posStopPx);
         if(hit)
           {
            CloseSimPosition(bt, g_posStopPx, "STOP");
            g_barsSinceClose = 0;
           }
        }
      return;
     }

   // flat: entry gate, same order as Aurelius_EA.mq5's own OnTick()
   g_barsSinceClose++;
   if(g_barsSinceClose < g_eff.cooldownBars) return;
   if(atr <= 0.0) return;

   bool up = AlignedAt(s, true);
   bool dn = AlignedAt(s, false);
   if(!up && !dn) return;
   if(up && !g_eff.allowBuys) return;
   if(dn && !g_eff.allowSells) return;

   if(g_eff.useCrossFilter)
     { int cc = CrissCrossAt(s); if(cc > g_eff.maxCrosses) return; }

   double slope = SlopeATRAt(s, up);
   if(g_eff.useSlope && slope < g_eff.minSlopeATR) return;
   if(g_eff.maxSlopeATR > 0.0 && slope > g_eff.maxSlopeATR) return;

   if(!PullbackOKAt(s, up)) return;

   if(g_eff.useVolume)
     {
      double vr = VolumeRatioAt(s);
      if(vr >= 0.0 && vr < g_eff.minVolRatio) return;
     }

   double sd = -1.0;
   if(g_eff.useSRDist || g_eff.useSlopeSRBlock)
      sd = SRDistanceATRAt(s, up, atr);
   if(g_eff.useSRDist && sd >= 0.0 && sd < g_eff.minSRDistATR) return;
   if(g_eff.useSlopeSRBlock && sd >= 0.0 && slope >= g_eff.slopeSRBlockSlope && sd >= g_eff.slopeSRBlockSR) return;

   double entryPx = iClose(_Symbol, PERIOD_CURRENT, s);
   OpenSimPosition(bt, entryPx, up ? 1 : -1, atr, s);

   if(g_eff.useStopLoss && g_posStopPx > 0.0)
     {
      bool hit = up ? (iLow(_Symbol, PERIOD_CURRENT, s) <= g_posStopPx)
                    : (iHigh(_Symbol, PERIOD_CURRENT, s) >= g_posStopPx);
      if(hit) { CloseSimPosition(bt, g_posStopPx, "STOP"); g_barsSinceClose = 0; }
     }
  }
//+------------------------------------------------------------------+
//| Drives the whole walk: on first run, backfills the InpMaxHistory- |
//| Bars window (BackfillMALines-style bootstrap); on every call      |
//| after that, processes only bars newly closed since last time      |
//| (normally exactly one, per new bar - UpdateMALines-style          |
//| increment). Cheap no-op when nothing new has closed.              |
//+------------------------------------------------------------------+
void SyncSignals()
  {
   int avail = Bars(_Symbol, PERIOD_CURRENT);
   int warmup = g_eff.p2400 + 600;
   if(avail < warmup + 2)
     {
      Comment("ScalpSignal_Indicator: waiting for history - ", avail, " bars, need ", warmup + 2);
      return;
     }

   int fromShift;
   if(g_lastProcessedBarTime <= 0)
     {
      int start = MathMin(InpMaxHistoryBars, avail - 2);
      fromShift = MathMax(2, start);
     }
   else
     {
      int lastShift = iBarShift(_Symbol, PERIOD_CURRENT, g_lastProcessedBarTime, true);
      if(lastShift < 0) fromShift = 0;
      else              fromShift = lastShift - 1;
     }
   if(fromShift < 1) return;   // nothing new

   RebuildATRSeries();
   for(int s = fromShift; s >= 1; s--)
      WalkOneBar(s);
   g_lastProcessedBarTime = iTime(_Symbol, PERIOD_CURRENT, 1);

   datetime cutoff = iTime(_Symbol, PERIOD_CURRENT, 1) - (datetime)((long)InpMaxHistoryBars * PeriodSeconds(PERIOD_CURRENT));
   PurgeOld(g_pm, cutoff);
   PurgeOld(g_pa, cutoff);
  }
//+------------------------------------------------------------------+
//| Live (tick-level) stop check for the still-forming bar - a real   |
//| broker-side stop is continuous, not bar-gated, so this is the one |
//| place live tick data legitimately drives the historical markup    |
//| itself (see header). Only the resting stop is checked this way -  |
//| Price21/VWAP/ALIGN_BREAK stay bar-close-gated, exactly matching   |
//| how Aurelius's own OnTick() only re-evaluates those on a new bar.  |
//+------------------------------------------------------------------+
void CheckLiveStop()
  {
   if(g_posDir == 0 || !g_eff.useStopLoss || g_posStopPx <= 0.0) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   bool hit = (g_posDir > 0) ? (bid <= g_posStopPx) : (ask >= g_posStopPx);
   if(hit) { CloseSimPosition(TimeCurrent(), g_posStopPx, "STOP"); g_barsSinceClose = 0; }
  }
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(!g_supported) return(rates_total);
   SyncSignals();
   CheckLiveStop();
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
   if(!g_supported) return;
   if(InpShowPanel && TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      DrawPanel();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
//| Panel primitives - reused/adapted directly from Aurelius_EA.mq5's |
//| own PRect/PFrame/PText/PRow/PSection/PWatermark/EstimateTextWidth.|
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
//| Informational-only readouts (never gate an arrow or the ready     |
//| light) - MACD histogram turning (same construction Aurelius's own |
//| MomentumShiftOK() uses/used) and the Ratchet_EA.mq5-ported        |
//| Stochastic(5,3,3).                                                |
//+------------------------------------------------------------------+
bool MomentumTurning(const bool up)
  {
   double macdNow, macdPrev1, macdPrev2, sigNow, sigPrev1, sigPrev2;
   if(!BufVal(hMACD, 0, 1, macdNow) || !BufVal(hMACD, 0, 2, macdPrev1) || !BufVal(hMACD, 0, 3, macdPrev2))
      return(false);
   if(!BufVal(hMACD, 1, 1, sigNow) || !BufVal(hMACD, 1, 2, sigPrev1) || !BufVal(hMACD, 1, 3, sigPrev2))
      return(false);
   double histNow   = macdNow   - sigNow;
   double histPrev1 = macdPrev1 - sigPrev1;
   double histPrev2 = macdPrev2 - sigPrev2;
   if(up)  return(histNow > histPrev1 && histPrev1 <= histPrev2);
   return(histNow < histPrev1 && histPrev1 >= histPrev2);
  }
double StochK()
  {
   double v;
   if(!BufVal(hSto, (InpStochUseSignal ? 1 : 0), 1, v)) return(-1.0);
   return(v);
  }
//+------------------------------------------------------------------+
//| The dashboard. ROWS/GAPS hand-counted against the literal PRow/   |
//| PSection call sequence below (see the build report for the count)|
//| and re-verified the same way Aurelius_EA.mq5's own header         |
//| documents doing after its own off-by-one was found. Every section |
//| below draws a FIXED number of rows regardless of runtime state    |
//| (flat vs in-sim-position uses "-" placeholder VALUES, never a     |
//| different ROW COUNT) - deliberately avoids the variable-row-count |
//| branching that caused that earlier bug, not just reusing its fix. |
//| Background/watermark drawn BEFORE the InpShowPanel early-return.  |
//+------------------------------------------------------------------+
void DrawPanel()
  {
   PWatermark();
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }

   g_panelReclaim = true;   // this file redraws at most once/second - always safe to reclaim

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;
   int rh = InpPanelSize + 11;
   int hdr = rh + 14;

   const int ROWS = 34, GAPS = 12;   // s2 (CONTEXT) grew 3->4 rows for the new "price vs VWAP band" row (m4), 2026-09-25
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
   PText("t2", x + w - 12, ty + 3, "SCALPSIGNAL", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   // --- a0: timeframe/source (1 row) --------------------------------
   PRow("a0", x, ty, w, "timeframe", g_eff.sourceName, 1); ty += rh + 6;                    // GAP 1

   // --- READY (section + 3 rows) -------------------------------------
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   bool spreadOK = (InpMaxSpreadPoints <= 0 || spr <= InpMaxSpreadPoints);
   bool up1 = AlignedAt(1, true), dn1 = AlignedAt(1, false);
   int  dir = up1 ? 1 : (dn1 ? -1 : 0);
   double slope1 = (dir != 0) ? SlopeATRAt(1, dir > 0) : 0.0;
   bool slopeOK = (dir != 0) &&
                  (!g_eff.useSlope || slope1 >= g_eff.minSlopeATR) &&
                  (g_eff.maxSlopeATR <= 0.0 || slope1 <= g_eff.maxSlopeATR);
   bool coreOK = (dir != 0) && slopeOK;
   bool ready  = spreadOK && coreOK;

   PSection("s1", x, ty, w, rh, "READY TO SCALP"); ty += rh + 6;                             // GAP 2
   PRow("r1", x, ty, w, "spread", (string)spr + " / " + (string)InpMaxSpreadPoints, spreadOK ? 1 : 0); ty += rh;
   PRow("r2", x, ty, w, "align+slope",
        dir == 1 ? "BUY" : dir == -1 ? "SELL" : "no", coreOK ? 1 : 0); ty += rh;
   PRow("r3", x, ty, w, "OVERALL", ready ? "READY" : "WAIT", ready ? 1 : 0); ty += rh + 6;   // GAP 3

   // --- CONTEXT, informational only (section + 4 rows) ----------------
   bool momUp = InpShowMomentum && MomentumTurning(true);
   bool momDn = InpShowMomentum && MomentumTurning(false);
   double kVal = InpShowStoch ? StochK() : -1.0;
   bool kExtreme = (kVal >= 0.0) && (kVal >= InpStochOBLevel || kVal <= InpStochOSLevel);
   double vw1 = SessionVWAP(1);
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);

   PSection("s2", x, ty, w, rh, "CONTEXT (not a gate)"); ty += rh + 6;                       // GAP 4
   PRow("m1", x, ty, w, "momentum (MACD)",
        !InpShowMomentum ? "off" : (momUp ? "turning up" : momDn ? "turning down" : "flat"),
        !InpShowMomentum ? -1 : (momUp ? 1 : momDn ? 0 : -1)); ty += rh;
   PRow("m2", x, ty, w, "stochastic %K",
        !InpShowStoch || kVal < 0.0 ? "off" : DoubleToString(kVal, 1) + (kExtreme ? " extreme" : ""),
        !InpShowStoch || kVal < 0.0 ? -1 : (kExtreme ? 0 : 1)); ty += rh;
   PRow("m3", x, ty, w, "price vs VWAP",
        vw1 <= 0.0 ? "n/a" : (c1 > vw1 ? "above" : "below"), -1); ty += rh;
   double bU = 0.0, bL = 0.0; bool haveBand = InpShowVWAPBands && SessionVWAPBand(1, InpVWAPBandK, bU, bL);
   PRow("m4", x, ty, w, "price vs VWAP band",
        !haveBand ? "off" : (c1 > bU ? "above upper" : c1 < bL ? "below lower" : "inside"), -1); ty += rh + 6; // GAP 5

   // --- ENTRY CRITERIA (section + 7 rows) ------------------------------
   int cc = g_eff.useCrossFilter ? CrissCrossAt(1) : -1;
   bool pb = (dir != 0) && PullbackOKAt(1, dir > 0);
   double vr = g_eff.useVolume ? VolumeRatioAt(1) : -1.0;
   double atrNow; bool haveAtr = ATRAt(1, atrNow);
   double sd = (haveAtr && dir != 0 && (g_eff.useSRDist || g_eff.useSlopeSRBlock))
               ? SRDistanceATRAt(1, dir > 0, atrNow) : -1.0;
   bool srBlockHit = g_eff.useSlopeSRBlock && dir != 0 && sd >= 0.0 &&
                     slope1 >= g_eff.slopeSRBlockSlope && sd >= g_eff.slopeSRBlockSR;

   PSection("s3", x, ty, w, rh, "ENTRY CRITERIA"); ty += rh + 6;                              // GAP 6
   PRow("c1", x, ty, w, "aligned", dir == 1 ? "BUY" : dir == -1 ? "SELL" : "no", dir != 0 ? 1 : 0); ty += rh;
   PRow("c2", x, ty, w, "slope", DoubleToString(slope1, 2), slopeOK ? 1 : 0); ty += rh;
   PRow("c3", x, ty, w, "criss-cross", cc < 0 ? "off" : (string)cc,
        !g_eff.useCrossFilter ? -1 : (cc <= g_eff.maxCrosses ? 1 : 0)); ty += rh;
   PRow("c4", x, ty, w, "pullback", pb ? "yes" : "no", pb ? 1 : 0); ty += rh;
   PRow("c5", x, ty, w, "volume", vr < 0.0 ? "off" : DoubleToString(vr, 2),
        !g_eff.useVolume ? -1 : (vr >= g_eff.minVolRatio ? 1 : 0)); ty += rh;
   PRow("c6", x, ty, w, "to S/R level", sd < 0.0 ? "off" : DoubleToString(sd, 2) + " ATR",
        !g_eff.useSRDist ? -1 : (sd >= g_eff.minSRDistATR ? 1 : 0)); ty += rh;
   PRow("c7", x, ty, w, "slope x SR block",
        !g_eff.useSlopeSRBlock ? "off (M5)" : (srBlockHit ? "BLOCKED" : "clear"),
        !g_eff.useSlopeSRBlock ? -1 : (srBlockHit ? 0 : 1)); ty += rh + 6;                    // GAP 7

   // --- STRATEGY, read-only echo of the auto-detected settings (section + 6 rows) --
   string alName = (g_eff.alignMode == ALIGN_FULL) ? "FULL" :
                   (g_eff.alignMode == ALIGN_MID)  ? "MID"  :
                   (g_eff.alignMode == ALIGN_FAST) ? "FAST" : "PRICE";
   string pbName = (g_eff.pullbackMA == PB_21) ? "21" : (g_eff.pullbackMA == PB_50) ? "50" : "150/250";

   PSection("s4", x, ty, w, rh, "STRATEGY (auto)"); ty += rh + 6;                             // GAP 8
   PRow("d1", x, ty, w, "source", g_eff.sourceName, -1); ty += rh;
   PRow("d2", x, ty, w, "alignment", alName, -1); ty += rh;
   PRow("d3", x, ty, w, "pullback to", pbName, -1); ty += rh;
   PRow("d4", x, ty, w, "stop loss",
        g_eff.useStopLoss ? DoubleToString(g_eff.stopATR, 1) + " ATR" : "none", -1); ty += rh;
   PRow("d5", x, ty, w, "price-21 exit", g_eff.usePrice21Exit ? "on" : "off", -1); ty += rh;
   PRow("d6", x, ty, w, "vwap exit", g_eff.useVwapExit ? "on" : "off", -1); ty += rh + 6;     // GAP 9

   // --- SIM POSITION - fixed 4 rows regardless of state (section + 4 rows) --
   double liveBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double liveAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double liveFloat = 0.0;
   int barsHeld = 0;
   if(g_posDir != 0)
     {
      double markPx = (g_posDir > 0) ? liveBid : liveAsk;
      liveFloat = (markPx - g_posEntryPx) * g_posDir;
      barsHeld = iBarShift(_Symbol, PERIOD_CURRENT, g_posEntryTime, false);
      if(barsHeld < 0) barsHeld = 0;
     }
   PSection("s5", x, ty, w, rh, "SIM POSITION"); ty += rh + 6;                                // GAP 10
   PRow("p1", x, ty, w, "state",
        g_posDir > 0 ? "LONG" : g_posDir < 0 ? "SHORT" : "FLAT", g_posDir != 0 ? 1 : -1); ty += rh;
   PRow("p2", x, ty, w, "entry px", g_posDir != 0 ? DoubleToString(g_posEntryPx, _Digits) : "-", -1); ty += rh;
   PRow("p3", x, ty, w, "bars held", g_posDir != 0 ? (string)barsHeld : "-", -1); ty += rh;
   PRow("p4", x, ty, w, "floating P/L", g_posDir != 0 ? StringFormat("%+.2f", liveFloat) : "-",
        g_posDir == 0 ? -1 : (liveFloat >= 0 ? 1 : 0)); ty += rh + 6;                          // GAP 11

   // --- MARKUP STATS (section + 3 rows) --------------------------------
   double winRate = (g_statTrades > 0) ? (100.0 * g_statWins / g_statTrades) : 0.0;
   PSection("s6", x, ty, w, rh, "MARKUP STATS (since attach)"); ty += rh + 6;                 // GAP 12
   PRow("t1", x, ty, w, "trades", (string)g_statTrades, -1); ty += rh;
   PRow("t2", x, ty, w, "win rate", g_statTrades > 0 ? DoubleToString(winRate, 1) + "%" : "-", -1); ty += rh;
   PRow("t3", x, ty, w, "total pnl", StringFormat("%+.2f", g_statTotalPnl),
        g_statTotalPnl >= 0 ? 1 : 0); ty += rh;
   // no trailing gap after the panel's last row - matches Aurelius_EA.mq5's own q4

   static int warned = 0;
   int used = ty + 12 - y;
   if(used > bodyH && warned < 3)
     { warned++; PrintFormat("ScalpSignal panel: content %d px vs frame %d px", used, bodyH); }
  }
//+------------------------------------------------------------------+
