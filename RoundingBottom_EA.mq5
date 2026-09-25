//+------------------------------------------------------------------+
//|                                          RoundingBottom_EA.mq5   |
//|                                                                  |
//|  WHAT THIS IS: an Expert Advisor (real order execution, runs in   |
//|  the Strategy Tester) that trades the Rounding Bottom pattern - a   |
//|  long, smooth U-shaped consolidation that reverses a downtrend        |
//|  into an uptrend, per the Kanu Jain "Fundamentals of Investments"       |
//|  deck ("best suited for weekly charts... a long consolidation           |
//|  period that turns from a bearish to a bullish bias").                    |
//|                                                                    |
//|  REAL PYTHON VALIDATION (2026-09-25, research/trendbreaker/           |
//|  rounding_cup_handle_test.py, real GOLD H4 data 2001-2026, 23763         |
//|  bars). Genuinely different construction from every other EA in this      |
//|  portfolio - not a swing-point shape (H&S, double/triple tops) and         |
//|  not a straight-line construction (triangles/wedges/rectangle): a          |
//|  ROLLING QUADRATIC FIT. Slide a fixed-length window over closes;             |
//|  fit y = a*x^2 + b*x + c by least squares; require a real R^2 >=              |
//|  InpR2Min (evidence of an ACTUAL rounding shape, not just "any three            |
//|  points") and upward curvature (a>0); require the window's own low              |
//|  point to sit roughly CENTERED (not at either edge, so a straight                |
//|  trend can't masquerade as "rounding"). RIM = the window's own                    |
//|  starting price. BREAKOUT = InpBreakConfirmCloses consecutive closes               |
//|  above the rim by more than InpBreakTolATR x ATR. TARGET = the classic              |
//|  measured-move rule (rim-to-bottom height, projected UP from the                     |
//|  breakout price) - same convention as every other pattern EA in this                  |
//|  portfolio. Real result at the validated default window (60 H4 bars,                   |
//|  ~10 days): n=111, win 81.1%, PF 2.726, net +2336.34 (USD price-difference               |
//|  units, real GOLD H4 data - NOT directly comparable to a ZAR MT5 report                   |
//|  without converting), stable across a stop-buffer sweep from 0.5x to 2.0x                  |
//|  ATR (PF stayed 2.4-2.7 throughout) and IS/OOS split (77.9% IS / 88.2% OOS,                  |
//|  i.e. it held up BETTER out-of-sample, the opposite of overfitting).                          |
//|                                                                    |
//|  WHAT WAS ALSO TESTED AND REJECTED - do not enable trading it here: the    |
//|  bearish mirror (Rounding TOP) was real-tested the same way and is a         |
//|  genuine loser at every window size tried (PF 0.34-0.77), most likely          |
//|  because real GOLD has been in a strong secular uptrend across the same         |
//|  2001-2026 window this was tested on - a real regime bias, not a construction    |
//|  bug. This file therefore only ever trades the bullish/buy side. There is no      |
//|  toggle to enable the bearish side because there is no real evidence behind it.     |
//|                                                                    |
//|  WHAT IS NOT VALIDATED - STOP-LOSS PLACEMENT, exactly like this portfolio's      |
//|  HeadShoulders_EA.mq5: InpStopBufferATR below (beyond the window's own bottom,     |
//|  buffered by InpStopBufferATR x ATR) is a disclosed, standard, technically-          |
//|  reasonable choice (a break back past the cup's own low invalidates the shape),       |
//|  not independently researched the way the target is. The stop-buffer sweep above      |
//|  (0.5x-2.0x, PF always 2.4-2.7) suggests this choice isn't fragile, but that's a        |
//|  side effect of testing something else, not a dedicated stop-loss study.                 |
//|                                                                    |
//|  ALSO NOT VALIDATED - real MT5 execution. Everything above is a real, strictly-    |
//|  forward, no-lookahead PYTHON replay of real GOLD H4 OHLCV bars - this is its         |
//|  first real MT5 Strategy Tester run. Run it in the Tester before trusting it           |
//|  further, same discipline as every other EA in this portfolio.                          |
//|                                                                    |
//|  TIMEFRAME: this pattern was validated on H4 specifically (the Kanu Jain deck's own   |
//|  cue - "best suited for weekly/longer charts" - M15 was judged too short/noisy a bar     |
//|  for a pattern meant to span days-to-weeks). Attach this to an H4 GOLD chart. Nothing      |
//|  in the code hard-enforces the timeframe (matching how Aurelius_EA.mq5/Aurelius_M15_EA.mq5  |
//|  are separate files rather than one file enforcing a period) - running it elsewhere is real   |
//|  but untested territory, not a validated variant.                                              |
//|                                                                    |
//|  REAL, DISCLOSED CONSTRUCTION DIFFERENCE FROM THE PYTHON BACKTEST: the Python research    |
//|  scans the ENTIRE history at once and picks the globally best-fitting (highest R^2)          |
//|  non-overlapping window in every overlapping cluster (a retrospective, offline               |
//|  optimization only possible with the whole history in hand). A live EA cannot do this -        |
//|  it only knows the past, one new bar at a time. This file instead accepts the FIRST valid       |
//|  candidate it finds moving forward in time that doesn't overlap the previously accepted          |
//|  one (a standard real-time/causal equivalent - process events in the order they actually          |
//|  happen). This is the same category of real/Python gap already disclosed and accepted for          |
//|  HeadShoulders_EA.mq5's pullback-entry fill price - it does not change the core validated            |
//|  claim (a real U-shape with R^2 evidence predicts a real breakout), only exactly which             |
//|  specific overlapping window gets picked when more than one candidate is available at once.          |
//|                                                                    |
//|  ENTRY: on the bar that confirms the breakout, market order (buy only - see above), ONLY  |
//|  while flat (single position, same convention as every other EA in this portfolio). TP is     |
//|  the real measured-move target (broker-side limit); SL is the disclosed cup-bottom-based        |
//|  stop above (broker-side stop). No further management - the position runs to TP or SL,            |
//|  matching exactly what the Python research itself measured.                                        |
//|                                                                    |
//|  CUP AND HANDLE (InpRequireHandle, off by default): an entry filter on top of the base       |
//|  rounding-bottom construction - real Python evidence (same file): requiring a shallow            |
//|  pullback ("handle") within InpHandleMinBars-InpHandleMaxBars bars after the cup's own end          |
//|  keeps the same quality (81.5% win, PF 2.074) but cuts the sample from 111 to 27 - it does NOT       |
//|  clearly improve on the base pattern, just trades less often. Off by default: real, but doesn't        |
//|  clearly help, shipped as a toggle so it can be tried for real rather than left untested.               |
//|                                                                    |
//|  PERFORMANCE: this file ships with the g_skipCosmeticDraws idiom from HeadShoulders_EA.mq5's    |
//|  own v1.05 fix already built in (see that file's header for why it mattered - a non-visual         |
//|  Strategy Tester run never shows the panel or pattern drawings, so they're skipped entirely           |
//|  there rather than repeated on every bar for nothing).                                                  |
//|                                                                    |
//|  INPUT COMMENTS: kept short from the start (see HeadShoulders_EA.mq5 v1.06's header for why -    |
//|  MT5's Tester Inputs tab shows an input's COMMENT as the row label, not its variable name, so       |
//|  a long comment makes that label unreadable). Full detail lives here in the header instead.           |
//|                                                                    |
//|  v1.01: real bugs in v1.00's own code, caught by an Opus review requested BEFORE this file's    |
//|  first real MT5 run (same discipline as HeadShoulders_EA.mq5 v1.04). Fixed: (1) the real-time      |
//|  NMS overlap check compared the wrong endpoint (a candidate's END against the watermark, not its     |
//|  START) - overlapping/duplicate windows over the same cup could each be accepted and independently     |
//|  confirm and trade; (2) the very first Recompute() (on attach or after any restart) would scan the       |
//|  full InpLookbackBars of PAST history and could queue a candidate whose breakout already happened         |
//|  long ago, confirming "fresh" at whatever price the market has since run to - the first pass now           |
//|  only primes the real-time watermark and queues nothing, exactly matching what a live EA can honestly        |
//|  know (only what happens after it starts watching); (3) the strided candidate scan could lag the            |
//|  newest closed bar by a few bars every call (and in one specific stride/lookback combination could            |
//|  reach the still-forming bar) - the newest closed bar is now always explicitly checked; (4) bar-age             |
//|  for both the handle window and the overall expiry horizon was counting elapsed wall-clock seconds /             |
//|  period length instead of real bars (the same bug class as HeadShoulders_EA.mq5 v1.04) - now uses the             |
//|  real MQL5 Bars() count, immune to weekend/session gaps; (5) InpRequireHandle's shallow-pullback check              |
//|  read each bar's own LOW independently instead of a running minimum of CLOSES since the cup's own end -              |
//|  now matches the Python research's seg.min()-over-closes exactly; (6) the breakout-confirmation horizon               |
//|  was measured from the cup's own end even with a handle required, eating into the breakout's own budget               |
//|  instead of getting a fresh one from the handle's end, like the Python research does; (7) SL/TP are now                |
//|  normalized to the symbol's real tick precision - an un-rounded price could be rejected outright by some                |
//|  brokers as "invalid stops", silently failing every entry. Also removed a dead ATR computation in                       |
//|  Recompute() that was never actually read (candidate detection needs no ATR at all - only the later                     |
//|  breakout-tolerance/stop-buffer steps do, and those already read a fresh CurrentATR() of their own).                     |
//|                                                                    |
//|  v1.02: brought up to the same family visual standard as HeadShoulders_EA.mq5 v1.07 (see        |
//|  SESSION_NOTES.md on the original standardization pass this whole portfolio got). Chart theme        |
//|  (InpApplyTheme - neon-blue/white candles, black background), a background wallpaper image             |
//|  (InpBackgroundBMP), and a corner watermark (InpWatermark) - all ported verbatim from                    |
//|  Aurelius_EA.mq5's own code. Also new: InpDrawPending (on by default) draws un-confirmed shapes -          |
//|  found by Recompute() but not yet handle-armed/breakout-confirmed - in a dimmer InpColPending               |
//|  colour, with a status label ("awaiting handle" / "awaiting break (n/N closes)"), so a candidate              |
//|  is visible on the chart as it's tracked rather than only appearing once it's already tradeable.               |
//|  Same real limitation as HeadShoulders_EA.mq5's own version of this: what appears is a fully-formed              |
//|  rounding shape (Recompute() only evaluates a COMPLETE InpWindowBars-length window), not a bottom                 |
//|  still being carved out candle-by-candle before the window closes - there is no way to show a fit                  |
//|  the quadratic regression itself hasn't been run on yet. Purely visual/cosmetic - no signal, entry,                  |
//|  exit, sizing, or risk-management logic touched.                                                                       |
//|                                                                    |
//|  v1.03: SL RE-ANCHORED FROM THE CUP'S OWN BOTTOM TO THE RIM, in response to a real,      |
//|  bad first MT5 result (Backtest 1, 2020-2026 H4, real GOLD, real account): win% held up      |
//|  reasonably close to Python (74.5% real vs 81.1% Python) but PF collapsed to 1.030 (from         |
//|  Python's 2.726) because avg loss (-2289) ran ~2.8x avg win (807), and equity DD hit 45.07%         |
//|  on net profit of only 898.90 ZAR over 6.73 years. Root cause: the old stop sat beyond the             |
//|  CUP'S OWN BOTTOM, which can be very far below the entry price (entry happens at the rim, well           |
//|  above the bottom) - risk was structurally close to the full reward even before slippage, and             |
//|  positions could stay open up to 1590 hours (66 days) per Backtest 1's own holding-time stats,             |
//|  which is a lot of real weekend-gap exposure a frictionless Python backtest can't see (a stop-             |
//|  loss can slip past its trigger on a gap; a take-profit limit can't slip against you the same way).           |
//|  Real Python re-test (same real GOLD H4 data, same single-position-sequenced construction, stop            |
//|  now = rim - InpStopBufferATR x ATR): at the new default (1.0xATR) - n=134, win% 61.2, PF 2.553,           |
//|  net +1909.35, IS/OOS 52.7%/80.5%. Win rate drops (a tighter stop catches trades earlier, before             |
//|  some would have recovered to target) but PF holds up because losses are now small and fast              |
//|  instead of deep and slow - the same real mechanism expected to reduce the weekend-gap exposure             |
//|  that likely hurt Backtest 1. NOT the single best-looking Python number (0.5xATR gave PF 2.836)              |
//|  - picked a middle value instead since the tightest option's IS/OOS split (50.5%/78.0%) was the               |
//|  least stable of those tried. This is a real, disclosed FIX ATTEMPT, not yet its own real MT5                  |
//|  confirmation - Backtest 1's failure was real, this response needs its own fresh real MT5 run                   |
//|  before being trusted, same discipline as every other change in this portfolio.                                   |
//+------------------------------------------------------------------+
#property copyright "RoundingBottom_EA"
#property version   "1.03"
#property description "Trades the real-validated Rounding Bottom measured-move target (rim-anchored stop since v1.03) - needs its own first real MT5 run"
#property strict
#include <Trade\Trade.mqh>
CTrade trade;

input group "=== Rounding-bottom detection (real-validated, see header) ==="
input int    InpWindowBars      = 60;      // Fit window length, bars
input int    InpStride          = 5;       // Scan stride, bars
input double InpR2Min           = 0.50;    // Min fit quality (R-squared)
input double InpCenterTol       = 0.25;    // Bottom must sit within this fraction of window edges
input int    InpLookbackBars    = 1000;    // Bars of history scanned each recompute
input int    InpRecomputeEveryBars = 5;    // Full rescan throttle, every N bars

input group "=== Breakout confirmation (same construction as research/trendbreaker/) ==="
input int    InpATRPeriod       = 14;      // ATR period (MT5 iATR)
input double InpBreakTolATR     = 0.10;    // Rim break tolerance, x ATR
input int    InpBreakConfirmCloses = 3;    // Closes to confirm breakout
input int    InpMaxHorizonBars  = 300;     // How long a pattern stays "live" for entry, bars

input group "=== Stop-loss (disclosed, NOT independently validated - see header) ==="
input double InpStopBufferATR   = 1.0;     // SL buffer beyond the rim, x ATR

input group "=== Cup and handle filter (optional candidate, off by default) ==="
input bool   InpRequireHandle    = false;  // Require a shallow pullback before entry
input int    InpHandleMinBars    = 3;      // Min bars after cup end before a handle counts
input int    InpHandleMaxBars    = 40;     // Give the handle at most this many bars to form
input double InpHandleMaxRetrace = 0.5;    // Max handle pullback, fraction of cup depth

input group "=== Trade management ==="
input double InpLots             = 0.01;
input int    InpMagic            = 20260925;
input int    InpMaxSpreadPoints  = 60;     // Max spread to allow entry, points
input int    InpSlippage         = 30;

input group "=== Chart visuals ==="
input bool   InpDrawPatterns     = true;
input bool   InpDrawPending      = true;   // Draw un-confirmed shapes as they form
input bool   InpDrawHistory      = true;
input int    InpHistoryDays      = 120;
input color  InpColRim            = C'0,230,118';   // rim line - bullish, green
input color  InpColBottom          = C'255,196,84'; // cup-bottom marker
input color  InpColPending          = C'150,166,192'; // Un-confirmed shape colour, dimmer
input color  InpColTarget          = C'255,196,84'; // measured-move target line
input color  InpColEntryArrow      = C'255,255,255';
input int    InpLabelSize          = 8;

input group "=== Dashboard ==="
input string InpBackgroundBMP = "goldbg_blend.bmp";   // Background image (.bmp in MQL5\Images)
input int    InpBgWidth       = 1290;      // Image width, px (centring only)
input int    InpBgHeight      = 720;       // Image height, px (centring only)

input group "=== Chart theme ==="
input bool   InpApplyTheme      = true;    // Recolour the chart
input bool   InpHideTradeMarks  = true;    // Hide MT5's own buy/sell/SL/TP arrows
input color  InpChartBg     = clrBlack;           // Chart background
input color  InpBullCol     = C'0,150,255';       // Bullish candle - neon blue, family standard
input color  InpBearCol     = clrWhite;           // Bearish candle - neon white, family standard
input string InpWatermark   = "ROUNDINGBOTTOM";   // Watermark text (empty = none)
input color  InpWaterCol    = C'46,38,24';        // Watermark colour
input bool   InpWaterBottom = true;               // Watermark bottom-right instead of centred
input int    InpWaterSize   = 42;                 // Watermark font size
input string InpWaterFont   = "Arial Black";      // Watermark font

input group "=== Panel ==="
input bool   InpShowPanel   = true;
input int    InpPanelX      = 12;
input int    InpPanelY      = 30;
input bool   InpPanelBottom = true;
input int    InpPanelW      = 280;
input color  InpPanelBg     = C'13,17,28';
input color  InpHeaderBg    = C'28,36,58';
input color  InpPanelEdge   = C'0,230,118';
input color  InpTitleCol    = C'0,230,118';
input color  InpSectionCol  = C'214,226,238';
input color  InpTextCol     = C'150,166,192';
input color  InpValCol      = C'236,242,252';
input color  InpOkCol       = C'0,230,118';
input color  InpNoCol       = C'255,61,90';
input color  InpShadowCol   = C'6,8,14';
input string InpPanelFont   = "Consolas";
input int    InpPanelSize   = 8;

//+------------------------------------------------------------------+
struct RBPattern
  {
   int      i_start, i_end;      // array indices - valid only inside the Recompute() pass that found them
   datetime t_start, t_end;
   double   rim;                 // price at the window's start - the level the pattern must break back above
   double   bottomPx;
   datetime t_bottom;
   double   height;              // rim - bottomPx
   bool     handleArmed;         // InpRequireHandle only
   datetime handleEndTime;       // InpRequireHandle only - breakout scanning starts from here once armed
   bool     handleDecided;       // InpRequireHandle only - true once the handle window has elapsed either way
   double   handleMinClose;      // InpRequireHandle only - running min of CLOSES since t_end, matches Python's seg.min() over closes (Opus review Medium finding, fixed pre-first-MT5-run)
   int      run;                 // consecutive closes beyond the rim seen so far
   int      brk_i;               // -1 until confirmed
   datetime brk_t;
   double   brk_price;
   double   target;
   double   stop;
   bool     traded;
  };

datetime g_lastBarTime = 0;
int      g_barCounter = 0;
ulong    g_ticket = 0;
RBPattern g_patterns[];     // confirmed-breakout patterns (kept for drawing/history/entry)
RBPattern g_pending[];      // candidates found, not yet confirmed or expired
datetime g_greedyLastEndTime = 0;   // real-time NMS watermark - see header's disclosed construction note
bool     g_firstRecomputeDone = false;   // first Recompute() only primes the watermark - see its own comment (Opus review High finding, fixed pre-first-MT5-run)
string   g_pz = "RBEA_";

int      g_panX = -1, g_panY = -1;
int      g_panelMinW = 0;
bool     g_panelReclaim = true;
bool     g_skipCosmeticDraws = false;   // PERFORMANCE FIX - see header, same idiom as the rest of this portfolio
datetime g_lastPanelDraw = 0;
int      g_statTrades = 0, g_statWins = 0;

// quad-fit constants for the fixed window length - computed once in OnInit (see BuildQuadConsts())
int      g_npts = 0;         // InpWindowBars + 1
double   g_S2 = 0.0, g_S4 = 0.0, g_det = 0.0;
double   g_xn[];              // centered x values, precomputed once

//--- wallpaper/watermark/theme - same family idiom as Aurelius_EA.mq5/HeadShoulders_EA.mq5 (see PBackground()/PTheme()/PWatermark())
string   g_pw = "RBW_";   // kept out of the panel wipe (g_pz)
bool     g_bgOK = false;
int      g_bgTries = 0;

void PBackground();
void PTheme();
void PWatermark();

//+------------------------------------------------------------------+
void BuildQuadConsts()
  {
   g_npts = InpWindowBars + 1;
   ArrayResize(g_xn, g_npts);
   double mid = (g_npts - 1) / 2.0;
   g_S2 = 0.0; g_S4 = 0.0;
   for(int i = 0; i < g_npts; i++)
     {
      g_xn[i] = i - mid;
      double x2 = g_xn[i] * g_xn[i];
      g_S2 += x2;
      g_S4 += x2 * x2;
     }
   g_det = g_S4 * g_npts - g_S2 * g_S2;
  }
//+------------------------------------------------------------------+
//| Least-squares quadratic fit y = a*xn^2 + b*xn + c on the fixed,    |
//| pre-centered x grid (g_xn). Closed-form (not a general solve) -     |
//| valid because g_xn is evenly-spaced and centered, so sum(xn) and     |
//| sum(xn^3) are both exactly zero, decoupling the normal equations.     |
//| Returns R^2 via out params; a>0 is required by the caller for a        |
//| genuine U-shape (rounding bottom).                                      |
//+------------------------------------------------------------------+
bool QuadFit(const double &y[], const int offset, double &a, double &b, double &c, double &r2)
  {
   double Sy = 0.0, Sxy = 0.0, Sxxy = 0.0;
   for(int i = 0; i < g_npts; i++)
     {
      double yi = y[offset + i];
      double xn = g_xn[i];
      Sy   += yi;
      Sxy  += xn * yi;
      Sxxy += xn * xn * yi;
     }
   if(MathAbs(g_det) < 1e-12 || g_S2 <= 0.0) return(false);
   a = (Sxxy * g_npts - Sy * g_S2) / g_det;
   c = (g_S4 * Sy - g_S2 * Sxxy) / g_det;
   b = Sxy / g_S2;

   double meanY = Sy / g_npts;
   double ssRes = 0.0, ssTot = 0.0;
   for(int i = 0; i < g_npts; i++)
     {
      double xn = g_xn[i];
      double fit = a * xn * xn + b * xn + c;
      double yi = y[offset + i];
      ssRes += (yi - fit) * (yi - fit);
      ssTot += (yi - meanY) * (yi - meanY);
     }
   if(ssTot <= 0.0) return(false);
   r2 = 1.0 - ssRes / ssTot;
   return(true);
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);
   if(InpWindowBars < 5)
     {
      Print("RoundingBottom_EA: InpWindowBars too small");
      return(INIT_FAILED);
     }
   BuildQuadConsts();
   //--- timer's only real job is keeping the panel/wallpaper alive between
   //--- ticks - meaningless in a non-visual Tester run (same fix Aurelius_EA.mq5
   //--- needed in its own v1.33, and HeadShoulders_EA.mq5's own v1.07 port of it)
   if(!g_skipCosmeticDraws) EventSetTimer(1);
   PTheme();   // theme applies even with the panel off - cheap, one-time, not gated
   return(INIT_SUCCEEDED);
  }
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(reason != REASON_CHARTCHANGE && reason != REASON_PARAMETERS)
     {
      ObjectsDeleteAll(0, g_pz);
      ObjectsDeleteAll(0, g_pw);
     }
   Comment("");
  }
//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t == 0) return(false);
   if(t == g_lastBarTime) return(false);
   g_lastBarTime = t;
   return(true);
  }
//+------------------------------------------------------------------+
//| Same pattern (by its start/end bar times) already known, either     |
//| confirmed or still pending?                                          |
//+------------------------------------------------------------------+
bool AlreadyKnown(const datetime tStart, const datetime tEnd)
  {
   for(int i = 0; i < ArraySize(g_patterns); i++)
      if(g_patterns[i].t_start == tStart && g_patterns[i].t_end == tEnd) return(true);
   for(int i = 0; i < ArraySize(g_pending); i++)
      if(g_pending[i].t_start == tStart && g_pending[i].t_end == tEnd) return(true);
   return(false);
  }
//+------------------------------------------------------------------+
//| Tries ONE candidate window ending at `end`. Factored out of         |
//| Recompute() so the strided scan and the explicit trailing check       |
//| (see Recompute()'s own comment on why that trailing check exists)      |
//| share one implementation.                                               |
//+------------------------------------------------------------------+
void TryCandidate(const MqlRates &r[], const double &c[], const int end, const bool primingOnly)
  {
   int start = end - g_npts + 1;
   if(start < 0) return;
   //--- overlap check on the candidate's own START, not its end (Opus review
   //--- Critical finding, fixed pre-first-MT5-run): checking `end` against the
   //--- watermark only blocks candidates that finish before the watermark - it
   //--- does NOT stop a later-ending candidate whose START still falls inside
   //--- the previously accepted window, so overlapping/duplicate windows over
   //--- the same cup were being accepted and could each independently confirm
   //--- and trade. A real overlap check compares the new candidate's START to
   //--- where the last accepted one ENDED.
   if(r[start].time <= g_greedyLastEndTime) return;

   double a, b, cc, r2;
   if(!QuadFit(c, start, a, b, cc, r2)) return;
   if(a <= 0.0 || r2 < InpR2Min) return;

   int bottomI = start;
   double bottomPx = c[start];
   for(int i = start + 1; i <= end; i++)
      if(c[i] < bottomPx) { bottomPx = c[i]; bottomI = i; }
   double frac = (double)(bottomI - start) / (double)g_npts;
   if(frac < InpCenterTol || frac > 1.0 - InpCenterTol) return;

   double rim = c[start];
   double height = rim - bottomPx;
   if(height <= 0.0) return;

   //--- this candidate now "owns" this stretch of time - see header note.
   //--- Advanced even during priming (see Recompute()) so the FOLLOWING real
   //--- call doesn't re-find and re-queue the exact same historical ground.
   g_greedyLastEndTime = r[end].time;

   //--- Opus review High finding, fixed pre-first-MT5-run: the very first
   //--- Recompute() this EA ever runs (on attach, or after any restart) would
   //--- otherwise scan up to InpLookbackBars of PAST history and queue
   //--- candidates whose breakout may have already happened, sometimes deep
   //--- in an existing move - AdvancePending() has no way to know that and
   //--- would confirm it "fresh" a few bars later, entering at whatever price
   //--- the market has already run to rather than a real breakout price. A
   //--- live EA can only honestly act on what happens AFTER it starts
   //--- watching, so the first pass only primes the watermark and queues
   //--- nothing; every later pass behaves normally.
   if(primingOnly) return;

   if(AlreadyKnown(r[start].time, r[end].time)) return;

   RBPattern P; ZeroMemory(P);
   P.i_start = start; P.i_end = end;
   P.t_start = r[start].time; P.t_end = r[end].time;
   P.rim = rim; P.bottomPx = bottomPx; P.t_bottom = r[bottomI].time;
   P.height = height;
   P.handleMinClose = rim;   // safe starting upper bound - see AdvancePending()'s running-min update
   P.brk_i = -1;
   P.traded = false;
   P.run = 0;
   P.handleArmed = false;
   P.handleDecided = !InpRequireHandle;   // if the filter is off, treat it as already-decided/pass
   int k = ArraySize(g_pending);
   ArrayResize(g_pending, k + 1, 32);
   g_pending[k] = P;
  }
//+------------------------------------------------------------------+
//| Full rescan: find NEW rounding-bottom candidates over the real-time  |
//| greedy NMS watermark (g_greedyLastEndTime - see header's disclosed    |
//| construction note). Called once per InpRecomputeEveryBars new bars.    |
//| Always explicitly checks the newest CLOSED bar (n-2) even if the        |
//| strided scan wouldn't naturally land on it (Opus review Medium/Low       |
//| findings, fixed pre-first-MT5-run: with the stride arithmetic alone,      |
//| detection could lag the true newest bar by up to InpStride-1 bars every    |
//| single call, and in one specific stride/lookback combination the strided    |
//| loop could reach the still-FORMING bar (n-1) instead of stopping at the      |
//| last real CLOSED one).                                                        |
//+------------------------------------------------------------------+
void Recompute()
  {
   MqlRates r[]; ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpLookbackBars, r);
   if(n <= g_npts + InpATRPeriod + 20) return;

   //--- no ATR needed here - candidate detection is pure quad-fit/R^2/centering
   //--- on price alone; ATR only matters later, for breakout tolerance and the
   //--- stop buffer, both read fresh from CurrentATR() in AdvancePending().
   double c[]; ArrayResize(c, n);
   for(int i = 0; i < n; i++) c[i] = r[i].close;

   int lastEnd = n - 2;   // shift=1, the newest CLOSED bar - the forming bar (n-1) is never a valid window end
   if(lastEnd < g_npts - 1) return;

   bool primingOnly = !g_firstRecomputeDone;

   int end = g_npts - 1;
   bool didLast = false;
   while(end <= lastEnd)
     {
      TryCandidate(r, c, end, primingOnly);
      if(end == lastEnd) didLast = true;
      end += InpStride;
     }
   if(!didLast)
      TryCandidate(r, c, lastEnd, primingOnly);

   g_firstRecomputeDone = true;
  }
//+------------------------------------------------------------------+
double CurrentATR()
  {
   MqlRates r[]; ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, PERIOD_CURRENT, 1, InpATRPeriod + 1, r);
   if(got < 2) return(_Point);
   double sum = 0.0; int cnt = 0;
   for(int i = 0; i < got - 1; i++)
     {
      double hl = r[i].high - r[i].low;
      double pc = r[i + 1].close;
      double tr = MathMax(hl, MathMax(MathAbs(r[i].high - pc), MathAbs(r[i].low - pc)));
      sum += tr; cnt++;
     }
   return(cnt > 0 ? MathMax(sum / cnt, _Point) : _Point);
  }
//+------------------------------------------------------------------+
//| Advances every pending candidate by exactly the ONE newest closed   |
//| bar: first resolves InpRequireHandle (if on), then watches for a      |
//| confirmed breakout above the rim, or expiry (InpMaxHorizonBars with     |
//| no breakout). Called once per new bar, after Recompute().                |
//| Bar-age uses the real MQL5 Bars() count between two times, not wall-      |
//| clock seconds / period length (Opus review Medium finding, fixed pre-      |
//| first-MT5-run, same bug class as HeadShoulders_EA.mq5 v1.04: dividing       |
//| elapsed real time overcounts "bars" across a weekend/session gap,            |
//| silently shrinking every window below).                                       |
//+------------------------------------------------------------------+
void AdvancePending()
  {
   if(ArraySize(g_pending) == 0) return;
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   if(t1 == 0) return;
   double atrNow = CurrentATR();

   for(int i = ArraySize(g_pending) - 1; i >= 0; i--)
     {
      RBPattern P = g_pending[i];
      if(t1 <= P.t_end) continue;

      long ageBars = Bars(_Symbol, PERIOD_CURRENT, P.t_end, t1) - 1;

      // --- InpRequireHandle: watch for a shallow pullback before allowing breakout scanning
      if(!P.handleDecided)
        {
         //--- running min of CLOSES since t_end, matching Python's seg.min()
         //--- over c[end:h_end+1] exactly (Opus review Medium finding, fixed
         //--- pre-first-MT5-run: checking each bar's own LOW independently, as
         //--- this did before, could arm the handle on a dip deeper than
         //--- InpHandleMaxRetrace followed by a shallower bar - Python's
         //--- cumulative-minimum-of-closes would correctly reject that).
         g_pending[i].handleMinClose = MathMin(g_pending[i].handleMinClose, c1);
         if(ageBars >= InpHandleMinBars && ageBars <= InpHandleMaxBars)
           {
            double retrace = P.rim - g_pending[i].handleMinClose;
            if(retrace > 0.0 && retrace <= InpHandleMaxRetrace * P.height)
              {
               g_pending[i].handleArmed = true;
               g_pending[i].handleEndTime = t1;
              }
           }
         if(ageBars > InpHandleMaxBars)
           {
            g_pending[i].handleDecided = true;
            if(!g_pending[i].handleArmed)
              {
               // no valid handle ever formed - skip this candidate entirely, no fallback
               int last = ArraySize(g_pending) - 1;
               if(i != last) g_pending[i] = g_pending[last];
               ArrayResize(g_pending, last);
               continue;
              }
           }
         else
            continue;   // still inside the handle window - not ready for breakout scanning yet
        }

      datetime scanFrom = InpRequireHandle ? g_pending[i].handleEndTime : P.t_end;
      if(t1 <= scanFrom) continue;
      //--- horizon measured from scanFrom (post-handle), not t_end - matches
      //--- Python's own search_start-anchored horizon (Opus review Medium
      //--- finding, fixed pre-first-MT5-run): otherwise a slow-forming handle
      //--- eats into the breakout's own confirmation budget instead of getting
      //--- a fresh one, same as Python gives it.
      long ageBarsFromScan = Bars(_Symbol, PERIOD_CURRENT, scanFrom, t1) - 1;

      bool confirmed = false;
      double beyond = c1 - P.rim;
      if(beyond > InpBreakTolATR * atrNow)
        {
         g_pending[i].run++;
         if(g_pending[i].run >= InpBreakConfirmCloses)
           {
            P = g_pending[i];
            P.brk_t = t1; P.brk_price = c1;
            //--- normalized to the symbol's real tick precision (Opus review
            //--- Medium finding, fixed pre-first-MT5-run) - an un-rounded SL/TP
            //--- (an ATR fraction added to a raw price) can be rejected outright
            //--- by some brokers/builds as "invalid stops", silently failing
            //--- every single entry with nothing but a log line to show for it.
            P.target = NormalizeDouble(P.brk_price + P.height, _Digits);
            //--- stop anchored to the RIM, not the cup's own bottom (v1.03 - see
            //--- header for the real evidence behind this change).
            P.stop = NormalizeDouble(P.rim - InpStopBufferATR * atrNow, _Digits);
            P.brk_i = 0;
            int k = ArraySize(g_patterns);
            ArrayResize(g_patterns, k + 1, 32);
            g_patterns[k] = P;
            confirmed = true;
           }
        }
      else
         g_pending[i].run = 0;

      bool expired = (!confirmed) && (ageBarsFromScan > InpMaxHorizonBars);

      if(confirmed || expired)
        {
         int last = ArraySize(g_pending) - 1;
         if(i != last) g_pending[i] = g_pending[last];
         ArrayResize(g_pending, last);
        }
     }
  }
//+------------------------------------------------------------------+
//| Entry - only acts on a pattern the EXACT bar its breakout is        |
//| confirmed (P.brk_t == the just-closed bar). Buy only - see header.    |
//+------------------------------------------------------------------+
void CheckForEntry()
  {
   if(g_ticket != 0) return;
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && spr > InpMaxSpreadPoints) return;

   datetime bt1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   for(int i = ArraySize(g_patterns) - 1; i >= 0; i--)
     {
      RBPattern P = g_patterns[i];
      if(P.traded || P.brk_t != bt1) continue;
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double entry = ask;
      if(P.target <= entry) { g_patterns[i].traded = true; continue; }
      if(P.stop >= entry) { g_patterns[i].traded = true; continue; }

      trade.SetExpertMagicNumber(InpMagic);
      trade.SetDeviationInPoints(InpSlippage);
      trade.SetTypeFillingBySymbol(_Symbol);
      bool ok = trade.Buy(InpLots, _Symbol, entry, P.stop, P.target, "RoundingBottom");
      g_patterns[i].traded = true;
      if(ok)
        {
         SyncPosition();
         if(!g_skipCosmeticDraws) DrawEntryArrow(P, entry);
        }
      else
         PrintFormat("RoundingBottom_EA: entry FAILED, retcode %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      return;
     }
  }
//+------------------------------------------------------------------+
bool FindOwnPosition(ulong &ticket)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && (long)PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
        { ticket = tk; return(true); }
     }
   return(false);
  }
void SyncPosition()
  {
   ulong tk;
   if(FindOwnPosition(tk))
     {
      g_ticket = tk;
      return;
     }
   if(g_ticket != 0)
     {
      if(HistorySelect(TimeCurrent() - 3 * 86400, TimeCurrent()))
        {
         for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
           {
            ulong d = HistoryDealGetTicket(i);
            if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic) continue;
            if((long)HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
            g_statTrades++;
            if(HistoryDealGetDouble(d, DEAL_PROFIT) > 0) g_statWins++;
            break;
           }
        }
     }
   g_ticket = 0;
  }
//+------------------------------------------------------------------+
//| Visuals                                                             |
//+------------------------------------------------------------------+
void DrawMarker(const string nm, const datetime t, const double px, const color col, const bool up)
  {
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_ARROW, 0, t, px);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, px);
   ObjectSetInteger(0, nm, OBJPROP_ARROWCODE, 159);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, up ? ANCHOR_BOTTOM : ANCHOR_TOP);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
void DrawLabel(const string nm, const datetime t, const double px, const string txt, const color col)
  {
   if(txt == "") { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_TEXT, 0, t, px);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, px);
   ObjectSetString (0, nm, OBJPROP_TEXT, txt);
   ObjectSetString (0, nm, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpLabelSize);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
void DrawLine(const string nm, const datetime t1, const double p1, const datetime t2, const double p2,
              const color col, const int width, const ENUM_LINE_STYLE style, const bool rayRight)
  {
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t1);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, p1);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t2);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, p2);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, rayRight);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
void DrawEntryArrow(const RBPattern &P, const double px)
  {
   string tag = TimeToString(P.brk_t, TIME_DATE|TIME_MINUTES);
   DrawMarker(g_pz + "en_" + tag, P.brk_t, px, InpColEntryArrow, true);
   DrawLabel(g_pz + "ent_" + tag, P.brk_t, px, "BUY " + DoubleToString(px, _Digits), InpColEntryArrow);
  }
color RBColNoStop() { return(C'255,120,120'); }
void DrawPattern(const RBPattern &P)
  {
   string base = g_pz + "p_" + TimeToString(P.t_end, TIME_DATE|TIME_MINUTES) + "_";
   DrawMarker(base + "bottom", P.t_bottom, P.bottomPx, InpColBottom, false);
   DrawLabel(base + "bl", P.t_bottom, P.bottomPx, "  bottom", InpColBottom);

   datetime tEnd = (P.brk_i >= 0) ? P.brk_t : P.t_end;
   DrawLine(base + "rim", P.t_start, P.rim, tEnd, P.rim, InpColRim, 2, STYLE_SOLID, (P.brk_i < 0));
   DrawLabel(base + "rimlbl", P.t_start, P.rim, "  rim", InpColRim);

   if(P.brk_i >= 0)
     {
      datetime tb0 = iTime(_Symbol, PERIOD_CURRENT, 0);
      datetime rightEdge = (tb0 > P.brk_t) ? tb0 : (datetime)((long)P.brk_t + 20 * PeriodSeconds(PERIOD_CURRENT));
      DrawLine(base + "tgt", P.brk_t, P.target, rightEdge, P.target, InpColTarget, 2, STYLE_DASH, true);
      DrawLabel(base + "tgtlbl", P.brk_t, P.target, "  target " + DoubleToString(P.target, _Digits), InpColTarget);
      DrawLine(base + "stop", P.brk_t, P.stop, rightEdge, P.stop, RBColNoStop(), 1, STYLE_DOT, false);
     }
  }
//+------------------------------------------------------------------+
//| Un-confirmed candidate - InpDrawPending. Same rim/bottom markers as   |
//| a confirmed pattern, no target/stop (none yet), InpColPending so a      |
//| shape mid-detection reads visibly differently from a real, tradeable,    |
//| confirmed one. Object namespace ("pend_") fully wiped and redrawn from     |
//| g_pending every call - see HeadShoulders_EA.mq5's own DrawPendingPattern()  |
//| for why that's simpler and provably correct than diffing array removals.     |
//+------------------------------------------------------------------+
void DrawPendingPattern(const RBPattern &P)
  {
   string base = g_pz + "pend_" + TimeToString(P.t_end, TIME_DATE|TIME_MINUTES) + "_";
   DrawMarker(base + "bottom", P.t_bottom, P.bottomPx, InpColPending, false);
   DrawLabel(base + "bl", P.t_bottom, P.bottomPx, "  bottom", InpColPending);
   DrawLine(base + "rim", P.t_start, P.rim, P.t_end, P.rim, InpColPending, 1, STYLE_DASH, true);

   string statusTxt;
   if(InpRequireHandle && !P.handleDecided)
      statusTxt = "  awaiting handle";
   else if(InpRequireHandle && !P.handleArmed)
      statusTxt = "  no handle - skipped";
   else
      statusTxt = StringFormat("  awaiting break (%d/%d closes)", P.run, InpBreakConfirmCloses);
   DrawLabel(base + "statuslbl", P.t_end, P.rim, statusTxt, InpColPending);
  }
void RefreshDrawings()
  {
   if(g_skipCosmeticDraws) return;   // PERFORMANCE FIX - see header
   if(!InpDrawPatterns) { ObjectsDeleteAll(0, g_pz + "p_"); ObjectsDeleteAll(0, g_pz + "pend_"); return; }
   datetime cutoff = InpDrawHistory ? (datetime)(TimeCurrent() - (long)InpHistoryDays * 86400)
                                     : (datetime)(TimeCurrent() - 5 * (long)PeriodSeconds(PERIOD_CURRENT) * InpLookbackBars);
   for(int i = 0; i < ArraySize(g_patterns); i++)
     {
      if(g_patterns[i].t_end < cutoff) continue;
      DrawPattern(g_patterns[i]);
     }

   ObjectsDeleteAll(0, g_pz + "pend_");
   if(InpDrawPending)
      for(int i = 0; i < ArraySize(g_pending); i++)
         DrawPendingPattern(g_pending[i]);
  }
//+------------------------------------------------------------------+
//| Wallpaper/theme/watermark - ported verbatim from Aurelius_EA.mq5's    |
//| own shared-family idiom (see SESSION_NOTES.md on the visual-           |
//| standardization pass every other EA in this portfolio already got,      |
//| and HeadShoulders_EA.mq5 v1.07's own port of the same code).             |
//+------------------------------------------------------------------+
void PBackground()
  {
   string nm = g_pw + "bmp";
   if(InpBackgroundBMP == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); g_bgOK = true; return; }
   if(g_bgOK) return;
   if(g_bgTries > 40) return;

   g_bgTries++;
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   if(!ObjectCreate(0, nm, OBJ_BITMAP_LABEL, 0, 0, 0))
     { Print("RoundingBottom_EA BG: ObjectCreate failed, error ", GetLastError()); return; }

   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0, nm, OBJPROP_BMPFILE, 0, path);
   int err = GetLastError();

   if(!okSet || err != 0)
     {
      if(g_bgTries <= 3)
         PrintFormat("RoundingBottom_EA BG try %d: failed to load \"%s\"  set=%s  error=%d"
                     "  -> file must be at <data folder>\\MQL5\\Images\\%s",
                     g_bgTries, path, (okSet ? "true" : "false"), err, InpBackgroundBMP);
      ObjectDelete(0, nm);
      return;
     }

   int cw  = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int chh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, MathMax(0, (cw  - InpBgWidth)  / 2));
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, MathMax(0, (chh - InpBgHeight) / 2));
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   g_bgOK = true;
   if(ObjectFind(0, g_pw + "wm") >= 0) ObjectDelete(0, g_pw + "wm");
   PWatermark();
   ChartRedraw(0);
  }
void PTheme()
  {
   if(!InpApplyTheme) return;
   ChartSetInteger(0, CHART_COLOR_BACKGROUND,  InpChartBg);
   ChartSetInteger(0, CHART_COLOR_FOREGROUND,  C'138,152,178');
   ChartSetInteger(0, CHART_COLOR_GRID,        C'20,26,40');
   ChartSetInteger(0, CHART_COLOR_CHART_UP,    InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CHART_DOWN,  InpBearCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, InpBearCol);
   ChartSetInteger(0, CHART_COLOR_CHART_LINE,  C'138,152,178');
   ChartSetInteger(0, CHART_COLOR_BID,         C'0,229,255');
   ChartSetInteger(0, CHART_COLOR_ASK,         C'255,193,7');
   ChartSetInteger(0, CHART_SHOW_GRID,   false);
   ChartSetInteger(0, CHART_MODE,        CHART_CANDLES);
   ChartSetInteger(0, CHART_SHOW_PERIOD_SEP, false);
   ChartSetInteger(0, CHART_COLOR_VOLUME,      C'40,52,76');
   ChartSetInteger(0, CHART_SHOW_OBJECT_DESCR, false);
   if(InpHideTradeMarks)
     {
      ChartSetInteger(0, CHART_SHOW_TRADE_LEVELS, false);
      ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, false);
     }
   ChartRedraw(0);
  }
void PWatermark()
  {
   string nm = g_pw + "wm";
   if(InpWatermark == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
   int cw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int ch = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   if(InpWaterBottom)
     {
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_RIGHT_LOWER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_RIGHT_LOWER);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 18);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 18);
     }
   else
     {
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_CENTER);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, cw / 2);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, ch / 2);
     }
   ObjectSetString (0, nm, OBJPROP_TEXT, InpWatermark);
   ObjectSetString (0, nm, OBJPROP_FONT, InpWaterFont);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpWaterSize);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, InpWaterCol);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| Panel primitives - same idiom as this project's other panels.       |
//+------------------------------------------------------------------+
int EstimateTextWidth(const string s, const int fontSize) { return (int)(StringLen(s) * fontSize * 0.62) + 2; }
void PRect(const string id, const int x, const int y, const int w, const int h, const color bg, const color edge, const int border)
  {
   string nm = g_pz + "pp_" + id;
   bool exists = (ObjectFind(0, nm) >= 0);
   if(g_panelReclaim && exists) { ObjectDelete(0, nm); exists = false; }
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
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5000);
  }
void PFrame(const string id, const int x, const int y, const int w, const int h, const color edge)
  {
   PRect(id + "ft", x, y, w, 2, edge, edge, 0);
   PRect(id + "fb", x, y + h - 2, w, 2, edge, edge, 0);
   PRect(id + "fl", x, y, 2, h, edge, edge, 0);
   PRect(id + "fr", x + w - 2, y, 2, h, edge, edge, 0);
  }
void PText(const string id, const int x, const int y, const string txt, const color col, const int size, const bool rightAlign, const string font = "")
  {
   string nm = g_pz + "pp_" + id;
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
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5001);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, rightAlign ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
  }
void PRow(const string id, const int x, const int y, const int w, const string label, const string value, const int state)
  {
   color dot = (state == 1) ? InpOkCol : (state == 0) ? InpNoCol : InpTextCol;
   PText(id + "d", x + 10, y, CharToString(108), dot, InpPanelSize + 1, false, "Wingdings");
   PText(id + "l", x + 26, y, label, InpTextCol, 0, false);
   PText(id + "v", x + w - 12, y, value, InpValCol, 0, true);
   int need = 26 + EstimateTextWidth(label, InpPanelSize) + 16 + EstimateTextWidth(value, InpPanelSize) + 20;
   if(need > g_panelMinW) g_panelMinW = need;
  }
void PSection(const string id, const int x, const int y, const int w, const int rh, const string title)
  {
   PRect(id + "bar", x + 1, y - 3, w - 2, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x + 10, y, title, InpSectionCol, InpPanelSize, false, "Arial Bold");
  }
//+------------------------------------------------------------------+
void DrawPanel()
  {
   //--- background/watermark are independent of the panel (InpShowPanel/
   //--- InpWatermark are separate inputs) - drawn BEFORE the panel's own
   //--- early-return, same fix HeadShoulders_EA.mq5 v1.07 ported from
   //--- Aurelius_EA.mq5/Vanguard_EA.mq5.
   PBackground();
   PWatermark();
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pz + "pp_"); return; }
   g_panelReclaim = true;
   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;
   int rh = InpPanelSize + 11;
   int hdr = rh + 14;
   const int ROWS = 8, GAPS = 4;
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH = hdr + 10 + ROWS * rh + GAPS * 6 + 12;
   int guard = 0;
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     { rh--; guard++; hdr = rh + 14; bodyH = hdr + 10 + ROWS * rh + GAPS * 6 + 12; }
   if(g_panX < 0)
     {
      g_panX = InpPanelX;
      g_panY = InpPanelBottom ? MathMax(2, chartH - bodyH - InpPanelY) : InpPanelY;
     }
   int x = g_panX, y = g_panY;
   PRect("sh", x + 4, y + 4, w, bodyH, InpShadowCol, InpShadowCol, 0);
   PRect("bg", x, y, w, bodyH, InpPanelBg, InpPanelBg, 0);
   PFrame("bd", x, y, w, bodyH, InpPanelEdge);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);
   int ty = y + 9;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "RoundingBottom EA", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   bool spreadOK = (InpMaxSpreadPoints <= 0 || spr <= InpMaxSpreadPoints);
   PSection("s1", x, ty, w, rh, "STATUS"); ty += rh + 6;
   PRow("a0", x, ty, w, "timeframe", EnumToString((ENUM_TIMEFRAMES)_Period), 1); ty += rh;
   PRow("a1", x, ty, w, "spread", (string)spr + " / " + (string)InpMaxSpreadPoints, spreadOK ? 1 : 0); ty += rh;
   PRow("a2", x, ty, w, "position", g_ticket != 0 ? "OPEN" : "flat", g_ticket != 0 ? 1 : -1); ty += rh + 6;

   int nPat = ArraySize(g_patterns);
   int nConfirmed = 0, nTraded = 0;
   datetime lastBrk = 0; int lastIdx = -1;
   for(int i = 0; i < nPat; i++)
     {
      if(g_patterns[i].brk_i < 0) continue;
      nConfirmed++;
      if(g_patterns[i].traded) nTraded++;
      if(g_patterns[i].brk_t >= lastBrk) { lastBrk = g_patterns[i].brk_t; lastIdx = i; }
     }
   PSection("s2", x, ty, w, rh, "PATTERNS"); ty += rh + 6;
   PRow("b0", x, ty, w, "confirmed / traded", IntegerToString(nConfirmed) + " / " + IntegerToString(nTraded), -1); ty += rh;
   string lastTxt = "none yet"; int lastState = -1;
   if(lastIdx >= 0)
     {
      lastTxt = "target " + DoubleToString(g_patterns[lastIdx].target, _Digits);
      lastState = 1;
     }
   PRow("b1", x, ty, w, "last confirmed", lastTxt, lastState); ty += rh;
   double wr = g_statTrades > 0 ? 100.0 * g_statWins / g_statTrades : 0.0;
   PRow("b2", x, ty, w, "session trades", IntegerToString(g_statTrades) + " (" + DoubleToString(wr, 0) + "% win)", -1); ty += rh + 6;
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   SyncPosition();
   if(IsNewBar())
     {
      g_barCounter++;
      if(InpRecomputeEveryBars <= 1 || g_barCounter % InpRecomputeEveryBars == 0)
         Recompute();
      AdvancePending();
      CheckForEntry();
      RefreshDrawings();
     }
   SyncPosition();
   //--- InpShowPanel dropped from this gate - DrawPanel() itself now draws
   //--- the wallpaper/watermark BEFORE its own internal InpShowPanel check,
   //--- so they must still be called even with the panel off.
   if(!g_skipCosmeticDraws && TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      DrawPanel();
      ChartRedraw(0);
     }
  }
void OnTimer()
  {
   SyncPosition();
   if(!g_skipCosmeticDraws && TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      DrawPanel();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
//| Resize -> the wallpaper needs re-centring (same idiom as              |
//| Aurelius_EA.mq5/HeadShoulders_EA.mq5 v1.07's own resize handler).       |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(g_skipCosmeticDraws) return;
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      static int lastW = -1, lastH = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lastW || nh != lastH)
        {
         lastW = nw; lastH = nh; g_bgOK = false; g_bgTries = 0; PBackground();
        }
     }
  }
//+------------------------------------------------------------------+
