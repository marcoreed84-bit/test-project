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
//+------------------------------------------------------------------+
#property copyright "RoundingBottom_EA"
#property version   "1.00"
#property description "Trades the real-validated Rounding Bottom measured-move target (81.1% win, PF 2.726, H4) - first real MT5 run"
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
input double InpStopBufferATR   = 1.0;     // SL buffer beyond cup bottom, x ATR

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
input bool   InpDrawHistory      = true;
input int    InpHistoryDays      = 120;
input color  InpColRim            = C'0,230,118';   // rim line - bullish, green
input color  InpColBottom          = C'255,196,84'; // cup-bottom marker
input color  InpColTarget          = C'255,196,84'; // measured-move target line
input color  InpColEntryArrow      = C'255,255,255';
input int    InpLabelSize          = 8;

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
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(reason != REASON_CHARTCHANGE && reason != REASON_PARAMETERS)
      ObjectsDeleteAll(0, g_pz);
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
//| Full rescan: find NEW rounding-bottom candidates over the real-time  |
//| greedy NMS watermark (g_greedyLastEndTime - see header's disclosed    |
//| construction note). Called once per InpRecomputeEveryBars new bars.    |
//+------------------------------------------------------------------+
void Recompute()
  {
   MqlRates r[]; ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpLookbackBars, r);
   if(n <= g_npts + InpATRPeriod + 20) return;

   double atr[]; BuildATR(r, n, atr);
   double c[]; ArrayResize(c, n);
   for(int i = 0; i < n; i++) c[i] = r[i].close;

   for(int end = g_npts - 1; end < n; end += InpStride)
     {
      if(r[end].time <= g_greedyLastEndTime) continue;   // already covered by a previously accepted candidate
      int start = end - g_npts + 1;
      if(start < 0) continue;

      double a, b, cc, r2;
      if(!QuadFit(c, start, a, b, cc, r2)) continue;
      if(a <= 0.0 || r2 < InpR2Min) continue;

      int bottomI = start;
      double bottomPx = c[start];
      for(int i = start + 1; i <= end; i++)
         if(c[i] < bottomPx) { bottomPx = c[i]; bottomI = i; }
      double frac = (double)(bottomI - start) / (double)g_npts;
      if(frac < InpCenterTol || frac > 1.0 - InpCenterTol) continue;

      double rim = c[start];
      double height = rim - bottomPx;
      if(height <= 0.0) continue;

      if(AlreadyKnown(r[start].time, r[end].time)) continue;

      RBPattern P; ZeroMemory(P);
      P.i_start = start; P.i_end = end;
      P.t_start = r[start].time; P.t_end = r[end].time;
      P.rim = rim; P.bottomPx = bottomPx; P.t_bottom = r[bottomI].time;
      P.height = height;
      P.brk_i = -1;
      P.traded = false;
      P.run = 0;
      P.handleArmed = false;
      P.handleDecided = !InpRequireHandle;   // if the filter is off, treat it as already-decided/pass
      int k = ArraySize(g_pending);
      ArrayResize(g_pending, k + 1, 32);
      g_pending[k] = P;

      g_greedyLastEndTime = r[end].time;   // this candidate now "owns" this stretch of time - see header note
     }
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
//+------------------------------------------------------------------+
void AdvancePending()
  {
   if(ArraySize(g_pending) == 0) return;
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double l1 = iLow(_Symbol, PERIOD_CURRENT, 1);
   if(t1 == 0) return;
   double atrNow = CurrentATR();
   int periodSec = MathMax(PeriodSeconds(PERIOD_CURRENT), 1);

   for(int i = ArraySize(g_pending) - 1; i >= 0; i--)
     {
      RBPattern P = g_pending[i];
      if(t1 <= P.t_end) continue;

      long ageBars = ((long)t1 - (long)P.t_end) / periodSec;

      // --- InpRequireHandle: watch for a shallow pullback before allowing breakout scanning
      if(!P.handleDecided)
        {
         if(ageBars >= InpHandleMinBars && ageBars <= InpHandleMaxBars)
           {
            double retrace = P.rim - l1;
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

      bool confirmed = false;
      double beyond = c1 - P.rim;
      if(beyond > InpBreakTolATR * atrNow)
        {
         g_pending[i].run++;
         if(g_pending[i].run >= InpBreakConfirmCloses)
           {
            P = g_pending[i];
            P.brk_t = t1; P.brk_price = c1;
            P.target = P.brk_price + P.height;
            P.stop = P.bottomPx - InpStopBufferATR * atrNow;
            P.brk_i = 0;
            int k = ArraySize(g_patterns);
            ArrayResize(g_patterns, k + 1, 32);
            g_patterns[k] = P;
            confirmed = true;
           }
        }
      else
         g_pending[i].run = 0;

      bool expired = (!confirmed) && (ageBars > InpMaxHorizonBars);

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
void RefreshDrawings()
  {
   if(g_skipCosmeticDraws) return;   // PERFORMANCE FIX - see header
   if(!InpDrawPatterns) { ObjectsDeleteAll(0, g_pz + "p_"); return; }
   datetime cutoff = InpDrawHistory ? (datetime)(TimeCurrent() - (long)InpHistoryDays * 86400)
                                     : (datetime)(TimeCurrent() - 5 * (long)PeriodSeconds(PERIOD_CURRENT) * InpLookbackBars);
   for(int i = 0; i < ArraySize(g_patterns); i++)
     {
      if(g_patterns[i].t_end < cutoff) continue;
      DrawPattern(g_patterns[i]);
     }
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
   if(!g_skipCosmeticDraws && InpShowPanel && TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      DrawPanel();
      ChartRedraw(0);
     }
  }
void OnTimer()
  {
   SyncPosition();
   if(!g_skipCosmeticDraws && InpShowPanel && TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      DrawPanel();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
