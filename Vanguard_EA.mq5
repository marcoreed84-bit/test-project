//+------------------------------------------------------------------+
//|                          Vanguard_EA.mq5                          |
//|                                                                    |
//|  NEW, standalone system - built from a clean file, same as        |
//|  Meridian_EA.mq5 was. Directly implements the diagonal-trendline   |
//|  breakout construction validated in this session's research       |
//|  (research/aurelius/trendline_break_test.py,                      |
//|  trendline_confluence_test.py) - the user's own long-standing      |
//|  ask ("trendlines, support and resistance... from weeks"), tested  |
//|  properly rather than assumed to work.                             |
//|                                                                    |
//|  entry : a diagonal trendline through the last TWO confirmed       |
//|          fractal swing highs (100-bar symmetric fractal - needs    |
//|          100 bars on each side to confirm, a genuinely significant |
//|          swing, not minor noise) is only valid when it's actually  |
//|          DESCENDING (the newer high is lower than the older one -  |
//|          a real "lower highs" sequence). Buy fires when price      |
//|          closes back ABOVE that descending line (a breakout), AND  |
//|          close agrees with session VWAP, AND price is >= 0.5xATR   |
//|          from the nearest daily S/R level (both confirmations      |
//|          already validated for Meridian, independently re-         |
//|          confirmed here). Sell is the exact mirror: an ASCENDING   |
//|          line through the last two confirmed swing LOWS (a real    |
//|          "higher lows" sequence), breakdown below it.               |
//|  exit  : the NEXT opposite-direction breakout, OR a safety stop at |
//|          InpSafetyStopATR x ATR(14), whichever comes first. No     |
//|          take-profit - matches Meridian's validated "let winners   |
//|          run" design, the only exit style that survived extensive  |
//|          testing this session (six other exit ideas were tried and |
//|          rejected on Meridian; this reuses the one that works).    |
//|                                                                    |
//|  PYTHON BACKTEST (full real M5 history, 2023-01 to 2026-08,        |
//|  256,318 bars, real spread, correct single-position sequencing,    |
//|  drawdown, walk-forward, random-direction control - all real,      |
//|  independently re-verified after this exact research line          |
//|  produced ONE serious false-positive that was caught and fixed     |
//|  before being trusted, see KNOWN GAPS below):                       |
//|                                                                    |
//|  Baseline (no confirmation filters): n=919, net=+3254.33 (price-    |
//|  difference $), PF=1.493, win rate 26.2%, random-direction          |
//|  percentile 99.7 (confirmed via a broad parameter plateau, k=85-115 |
//|  all net 2500-3590/PF 1.37-1.49 - not a lucky single point).        |
//|  Walk-forward 3/5 blocks (blocks 1-2 near-flat, not real losses;    |
//|  blocks 3-5 carry the gains - same recency pattern as every real    |
//|  construction this session, including Meridian and Aurelius's own   |
//|  validated year-by-year numbers). Closed DD 15.8% of net, floating  |
//|  DD 18.8% of net.                                                   |
//|                                                                    |
//|  +VWAP+S/R (what this file actually implements, InpMinSRDistATR=    |
//|  0.50 below): n=716, net=+2989.87, PF=1.570 (up from 1.493),        |
//|  floating DD 15.4% of net (down from 18.8%, the best DD found in    |
//|  this whole research line), random-direction percentile 99.7        |
//|  (unchanged - the filter cuts trade count without hurting           |
//|  significance). Chosen over the unfiltered baseline for the same    |
//|  reason S/R got added to Meridian: net AND drawdown improved        |
//|  together, not traded off against each other.                       |
//|                                                                    |
//|  HONEST CONTEXT: S/R distance is now the ONE confluence filter      |
//|  that has independently helped on TWO different constructions       |
//|  this session (Meridian's 21/50 cross AND this trendline breakout)  |
//|  - real, repeated evidence it's a generalizable signal, not         |
//|  construction-specific luck. VWAP helps drawdown specifically       |
//|  (18.8%->15.4%) at a modest net cost, same tradeoff shape seen       |
//|  throughout this session's confluence testing.                      |
//|                                                                    |
//|  REAL MT5 STRATEGY TESTER, v1.00 (fixed 0.01 lots, 2023.01-        |
//|  2026.09, GOLD#, XM Global): net=+56,913.47 ZAR, PF=1.638,          |
//|  Sharpe=2.81, win rate 28.6% (748 trades), Equity DD Maximal        |
//|  8.42%. Confirmed real and working - but the user directly flagged  |
//|  a real fragility this run exposed: 2026 alone (partial year)       |
//|  carried ~60% of total net profit, 2023 was nearly flat. Top 20     |
//|  trades (2.7% of all trades) summed to MORE than 100% of net -      |
//|  remove them and the system is net negative. Investigated: this is  |
//|  NOT a broken/fake edge in 2023-2024 (every year was net positive,  |
//|  PF>1 in the underlying Python construction even for 2023) - it's   |
//|  gold's own dollar ATR expanding ~5.7x over the period (2023        |
//|  avg $1.18 -> 2026 avg $6.68, and ATR AS % OF PRICE also grew       |
//|  0.061%->0.146%, a real volatility increase, not just nominal price |
//|  inflation) while the EA traded a FIXED lot size regardless.        |
//|                                                                    |
//|  v1.01 ADDS ATR-INVERSE POSITION SIZING (InpBaseLots/InpRefATR      |
//|  below, LotSize()) to directly address that: size scales UP in      |
//|  calmer (lower-ATR) periods and is floored at the broker's real     |
//|  0.01 lot minimum in high-ATR periods (so 2025-2026-era trades are  |
//|  UNCHANGED from what's already real-MT5-validated above - only the  |
//|  calmer years get bigger). Python-revalidated with this exact       |
//|  floor/step behavior (not an idealized continuous version - an      |
//|  earlier draft of this test had a real scaling bug in its drawdown  |
//|  math that overstated floating DD at 41.6%; fixed and rechecked):   |
//|  net=+3,679.04 (price-diff $, up from +2,989.87), PF=1.506,         |
//|  closedDD=11.3% of net (better than 12.8%), floatDD=13.0% of net    |
//|  (better than 15.4%), walk-forward 4/5, random-direction percentile |
//|  100.0. Year-by-year net (fixed-lot -> ATR-sized): 2023 $62->$455,  |
//|  2024 $206->$368, 2025 $904->$1,037, 2026 $1,818 unchanged (already |
//|  at the lot floor). Range shrinks from 29x (best year/worst year)   |
//|  to about 4x. Trade concentration (top 20 > net) is UNCHANGED by    |
//|  this - that's inherent to trend-following, sizing redistributes    |
//|  WHEN the profit lands, not how few trades produce it.              |
//|                                                                    |
//|  KNOWN GAPS (flagged, not silently fixed elsewhere, so they don't   |
//|  get lost):                                                         |
//|   - Same-day research on a "fan trendline" (three-line-break)       |
//|     construction initially showed PF 5-12x, which turned out to be  |
//|     a serious backtest artifact - every "best" result's top trade   |
//|     was the SAME position, entered mid-2024, that only "exited"     |
//|     because the Python dataset ran out in Aug 2026 before a real    |
//|     opposite signal ever fired (a live account would still be       |
//|     holding it today, not miraculously closed at the best price).   |
//|     Caught and excluded before being trusted; the corrected fan     |
//|     construction showed no real edge and was rejected. Flagged      |
//|     here because THIS file's own "hold until opposite breakout"     |
//|     exit has the exact same theoretical exposure (a position open   |
//|     when a real MT5 test period ends isn't a "win", it's an         |
//|     unresolved open risk) - something to watch for when reading     |
//|     any real Strategy Tester report on this file, not just the      |
//|     Python backtest.                                                |
//|   - No visual panel/wallpaper - same scope decision as Meridian     |
//|     v1.00, can be added later if the system proves out.             |
//|   - Friday flatten is day-of-week + hour only, no full US-market    |
//|     holiday calendar - same known gap as Meridian.                  |
//|   - ATR uses this project's own Wilder recursion (ComputeWilderATR  |
//|     below), NOT MT5's built-in iATR - same reason as every sibling  |
//|     EA (this broker's iATR is a plain SMA of true range, not real   |
//|     Wilder smoothing).                                              |
//|   - v1.01's ATR sizing has NOT yet itself been through a real MT5   |
//|     Strategy Tester run - only v1.00 (fixed lots) has. Needs that   |
//|     before these specific numbers are trusted the same way v1.00's  |
//|     are. Also: only 2023-2026 data exists to test against (no       |
//|     earlier real history was available to check behavior in a      |
//|     genuinely different, more range-bound gold regime) - this       |
//|     can't be fully ruled out as a risk, only reasoned about.        |
//+------------------------------------------------------------------+
#property copyright "Vanguard_EA"
#property version   "1.02"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

input group "=== Signal: diagonal trendline breakout ==="
input int    InpFractalK          = 100;     // bars on each side to confirm a swing point
input int    InpSRDays            = 3;       // trailing completed D1 bars checked for the nearest level
input double InpMinSRDistATR      = 0.50;    // reject entries this close (xATR) to that level

input group "=== Exit ==="
input double InpSafetyStopATR     = 4.0;     // validated best cell - see header
input int    InpATRPeriod         = 14;

input group "=== Risk (ATR-inverse sizing - see header) ==="
input double InpBaseLots           = 0.01;    // lot size AT the reference ATR below
input double InpRefATR             = 3.073;   // this construction's real avg entry ATR - see header
input double InpMaxSpreadPoints    = 60;
input int    InpSlippage           = 20;

input group "=== Session protection (v1.00 gap - see header) ==="
input bool   InpCloseFriday        = true;
input int    InpFridayCloseHour    = 22;      // server time

input group "=== Notifications ==="
input bool   InpPushNotifications  = true;

input group "=== Misc ==="
input ulong  InpMagic              = 750801;
input string InpTradeComment       = "Vanguard";

//+------------------------------------------------------------------+
//| VISUALS (v1.02). Same panel/watermark/chart-theme architecture,   |
//| primitives, and hard-won bugfixes as Aurelius_EA.mq5 - the        |
//| project's established "standard" (also shared by Ratchet/         |
//| Slipstream/Tailwind/AuRebound's chart-theme colours) - reused      |
//| verbatim where the mechanism is generic (PRect/PFrame/PText/PRow/  |
//| PSection/PTheme/PWatermark/PBackground, the reclaim-on-new-bar-    |
//| only pattern that avoids panel flashing, the explicit 4-strip      |
//| frame instead of PRect's own unreliable border). What's NEW here   |
//| is content specific to THIS construction: the live descending/     |
//| ascending trendline itself drawn as an extending ray (not a        |
//| per-bar MA segment - a trendline is two fixed swing points, not a  |
//| value that changes every bar), VWAP as a per-bar segment (Aurelius |
//| pattern, live-only here - no multi-day backfill, see UpdateVWAPLine|
//| header), and the S/R levels / entry / stop as horizontal lines     |
//| (Aurelius pattern, reused directly). Panel content (SIGNAL/ENTRY   |
//| CRITERIA/STRATEGY/POSITION/ACCOUNT) mirrors Aurelius's section     |
//| layout but shows what THIS EA actually tests, not a copy of        |
//| Aurelius's MA-alignment criteria.                                  |
//+------------------------------------------------------------------+
input group "=== Dashboard ==="
input bool    InpShowPanel   = true;              // Show the panel
input int     InpPanelDrag   = 1;                 // 0 = locked, 1 = draggable
input int     InpPanelX      = 12;                // X offset
input int     InpPanelY      = 30;                // Y offset (from the anchor edge)
input bool    InpPanelBottom = false;             // Anchor the panel to the BOTTOM left
input int     InpPanelW      = 260;               // Width
input color   InpPanelBg     = C'13,17,28';       // Panel background (solid)
input color   InpHeaderBg    = C'28,36,58';       // Header / section background
input color   InpPanelEdge   = C'255,196,84';     // Border - gold
input color   InpTitleCol    = C'255,196,84';     // Title text - gold
input color   InpSectionCol  = C'214,226,238';    // Section headings - silver
input color   InpTextCol     = C'150,166,192';    // Labels
input color   InpValCol      = C'236,242,252';    // Values
input color   InpOkCol       = C'0,230,118';      // Met - neon green
input color   InpNoCol       = C'255,61,90';      // Not met - hot red
input color   InpShadowCol   = C'6,8,14';         // Drop shadow
input string  InpPanelFont   = "Consolas";        // Font
input int     InpPanelSize   = 8;                 // Font size
input string  InpBackgroundBMP = "";              // Optional background image (.bmp in MQL5\Images) - empty by
                                                   // default, no Vanguard-branded image exists yet
input int     InpBgWidth       = 1290;            // Image width (px) - for centring only
input int     InpBgHeight      = 720;             // Image height (px) - for centring only

input group "=== Chart theme ==="
input bool    InpApplyTheme      = true;          // Recolour the chart
input bool    InpHideTradeMarks  = true;          // Hide MT5's own buy/sell/SL/TP arrows and lines - the panel
                                                   // and signal lines are meant to be the only things on this chart
input bool    InpShowSignalLine  = true;          // Draw the live descending/ascending trendline as an extending ray
input color   InpColDesc         = C'255,61,90';  // Descending line (resistance / sell-side) - hot red
input color   InpColAsc          = C'0,230,118';  // Ascending line (support / buy-side) - neon green
input bool    InpShowVWAPLine    = true;          // Draw session VWAP (live only from attach time - see header)
input color   InpColVWAP         = C'0,255,255';  // VWAP line colour - neon aqua
input int     InpVwapHistoryBars = 400;           // How many recent bars of VWAP line to keep drawn (bounded,
                                                   // purged the same way as the signal-line history would be)
input bool    InpShowTradeLevels = true;          // Draw the OPEN position's entry and stop-loss as horizontal lines
input color   InpColEntryLine    = C'150,166,192';// Entry-price line
input color   InpColStopLine     = C'255,61,90';  // Stop-loss line
input bool    InpShowSR          = true;          // Draw the InpSRDays nearest daily high/low SRDistance() tests against
input color   InpColSR           = C'120,144,176';// S/R level colour
input color   InpChartBg   = clrBlack;            // Chart background - matches the rest of this project
input color   InpBullCol   = C'0,150,255';        // Bullish candle - neon blue, matches the rest of this project
input color   InpBearCol   = clrWhite;            // Bearish candle - neon white, matches the rest of this project
input string  InpWatermark  = "VANGUARD";         // Watermark text (empty = none)
input color   InpWaterCol   = C'46,38,24';        // Watermark colour
input bool    InpWaterBottom = true;              // Watermark bottom-right instead of centred
input int     InpWaterSize  = 42;                 // Watermark font size
input string  InpWaterFont  = "Arial Black";      // Watermark font

//--- restart-safe position state (re-synced from the live account every
//--- check, not trusted from cache alone - the exact bug class fixed
//--- across every EA in this project earlier this session)
ulong    g_ticket  = 0;
int      g_posDir  = 0;      // +1 long, -1 short, 0 flat

//--- single-latch new-bar gate (called exactly once per tick)
datetime g_lastBarTime = 0;

//--- session VWAP (cumulative typical-price*volume from each calendar
//--- day's first bar) - identical construction to Meridian_EA.mq5,
//--- reused verbatim since it's already validated there.
datetime g_vwapDay    = 0;
double   g_vwapCumPV  = 0.0;
double   g_vwapCumVol = 0.0;
double   g_vwapValue  = 0.0;

//--- manual Wilder ATR (see header - NOT iATR)
double   g_atrBuf[];

//--- diagonal trendline state: last TWO confirmed swing highs (for the
//--- descending/lower-highs line) and last TWO confirmed swing lows
//--- (ascending/higher-lows line). datetime(0) means "unset".
datetime g_curHiTime = 0, g_prevHiTime = 0;
double   g_curHiPrice = 0.0, g_prevHiPrice = 0.0;
datetime g_curLoTime = 0, g_prevLoTime = 0;
double   g_curLoPrice = 0.0, g_prevLoPrice = 0.0;

//--- previous bar's own close-vs-line state, for edge-triggering a
//--- fresh cross (matches how the Python research vectorized this -
//--- each bar's comparison uses whatever line was valid AT that bar,
//--- not retroactively recomputed with later swing points)
bool     g_prevAboveDesc = false, g_prevDescValid = false;
bool     g_prevBelowAsc  = false, g_prevAscValid  = false;

//--- visuals (v1.02) - object name prefixes, kept distinct per group so
//--- ObjectsTotal(...) filters / ObjectsDeleteAll(0, prefix) never touch
//--- the wrong family of objects
string   g_pp = "VGP_";    // panel
string   g_pw = "VGW_";    // wallpaper + watermark
string   g_pm = "VGM_";    // per-bar VWAP segments
string   g_pl = "VGL_";    // level lines: signal-line rays, entry/stop, S/R
int      g_panX = -1, g_panY = -1;      // live panel position, updated by dragging
bool     g_bgOK = false;
int      g_bgTries = 0;
//--- PERFORMANCE (matches Aurelius_EA.mq5's identical fix): true when
//--- running a non-visual Strategy Tester pass (no chart anyone is
//--- watching) - set once in OnInit(). Gates every cosmetic draw below,
//--- none of which can ever affect a trading decision.
bool     g_skipCosmeticDraws = false;
int      g_panelMinW = 0;
bool     g_panelReclaim = true;
double   g_vwapPrevValue = 0.0;   // snapshotted each new bar, for the per-bar VWAP segment draw
int      g_barLastBreakoutDir = 0; // cosmetic only - the panel's "breakout this bar" row

//--- forward declarations: OnInit draws the panel before DrawPanel is defined
void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim = true);
void PTheme();
void PBackground();
void PWatermark();
void UpdateSignalLines();
void UpdateVWAPLine();
void UpdateLevelLines();

//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, PERIOD_M5, 0);
   if(t == g_lastBarTime) return(false);
   g_lastBarTime = t;
   return(true);
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
//+------------------------------------------------------------------+
void SyncPositionState()
  {
   ulong tk;
   if(FindOwnPosition(tk))
     {
      g_ticket = tk;
      if(PositionSelectByTicket(g_ticket))
         g_posDir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
     }
   else
     {
      g_ticket = 0;
      g_posDir = 0;
     }
  }
//+------------------------------------------------------------------+
//| Wilder ATR - matches ComputeWilderATR in every sibling EA / this  |
//| project's engine.wilder_atr(). Called once per new bar.           |
//+------------------------------------------------------------------+
void ComputeWilderATR(double &out[], int period)
  {
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, PERIOD_M5, 1, MathMax(period * 3, 200), r);
   if(got < period + 2) { ArrayResize(out, 1); out[0] = 0.0; return; }
   ArraySetAsSeries(out, true);
   ArrayResize(out, got);
   double tr[];
   ArrayResize(tr, got);
   for(int i = 0; i < got - 1; i++)
     {
      double hi = r[i].high, lo = r[i].low, pc = r[i + 1].close;
      tr[i] = MathMax(hi - lo, MathMax(MathAbs(hi - pc), MathAbs(lo - pc)));
     }
   int lastIdx = got - period - 1;
   if(lastIdx < 0) { out[0] = 0.0; return; }
   double seed = 0.0;
   for(int k = lastIdx; k < lastIdx + period; k++) seed += tr[k];
   seed /= period;
   double prev = seed;
   for(int k = lastIdx - 1; k >= 0; k--)
      prev = (prev * (period - 1) + tr[k]) / period;
   out[0] = prev;
  }
//+------------------------------------------------------------------+
bool GetATR(double &value)
  {
   ComputeWilderATR(g_atrBuf, InpATRPeriod);
   value = g_atrBuf[0];
   return(value > 0.0);
  }
//+------------------------------------------------------------------+
//| Session VWAP - identical construction to Meridian_EA.mq5.         |
//+------------------------------------------------------------------+
datetime DayStart(datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return(StructToTime(dt));
  }
//+------------------------------------------------------------------+
void SeedVWAP()
  {
   datetime last = iTime(_Symbol, PERIOD_M5, 1);
   if(last == 0) return;
   datetime day = DayStart(last);
   g_vwapDay = day;
   g_vwapCumPV = 0.0;
   g_vwapCumVol = 0.0;
   for(int shift = 1; shift < 400; shift++)
     {
      datetime t = iTime(_Symbol, PERIOD_M5, shift);
      if(t == 0 || DayStart(t) != day) break;
      double typical = (iHigh(_Symbol, PERIOD_M5, shift) + iLow(_Symbol, PERIOD_M5, shift) +
                         iClose(_Symbol, PERIOD_M5, shift)) / 3.0;
      double vol = (double)iTickVolume(_Symbol, PERIOD_M5, shift);
      g_vwapCumPV  += typical * vol;
      g_vwapCumVol += vol;
     }
   g_vwapValue = (g_vwapCumVol > 0.0) ? g_vwapCumPV / g_vwapCumVol : iClose(_Symbol, PERIOD_M5, 1);
  }
//+------------------------------------------------------------------+
void UpdateVWAP()
  {
   datetime t1 = iTime(_Symbol, PERIOD_M5, 1);
   if(t1 == 0) return;
   datetime day = DayStart(t1);
   if(day != g_vwapDay)
     {
      SeedVWAP();
      return;
     }
   double typical = (iHigh(_Symbol, PERIOD_M5, 1) + iLow(_Symbol, PERIOD_M5, 1) +
                      iClose(_Symbol, PERIOD_M5, 1)) / 3.0;
   double vol = (double)iTickVolume(_Symbol, PERIOD_M5, 1);
   g_vwapCumPV  += typical * vol;
   g_vwapCumVol += vol;
   g_vwapValue = (g_vwapCumVol > 0.0) ? g_vwapCumPV / g_vwapCumVol : iClose(_Symbol, PERIOD_M5, 1);
  }
//+------------------------------------------------------------------+
//| Raw nearest-level pair over the last InpSRDays COMPLETED daily     |
//| bars - split out from SRDistance() (v1.02) so the chart drawing    |
//| below can show the exact levels the filter tests against, instead  |
//| of re-deriving them and risking drift from what's actually traded. |
//+------------------------------------------------------------------+
bool GetSRLevels(double &hi, double &lo)
  {
   hi = -DBL_MAX; lo = DBL_MAX;
   for(int d = 1; d <= InpSRDays; d++)
     {
      double h = iHigh(_Symbol, PERIOD_D1, d);
      double l = iLow(_Symbol, PERIOD_D1, d);
      if(h <= 0.0 || l <= 0.0) return(false);
      if(h > hi) hi = h;
      if(l < lo) lo = l;
     }
   return(true);
  }
//+------------------------------------------------------------------+
//| Distance (xATR) from the last closed bar's close to the nearer of |
//| the last InpSRDays COMPLETED daily highs/lows - identical to       |
//| Meridian_EA.mq5's SRDistance(), reused verbatim.                   |
//+------------------------------------------------------------------+
double SRDistance(bool isBuy, double atrVal)
  {
   if(atrVal <= 0.0) return(-1.0);
   double hi, lo;
   if(!GetSRLevels(hi, lo)) return(-1.0);
   double close1 = iClose(_Symbol, PERIOD_M5, 1);
   return isBuy ? MathAbs(hi - close1) / atrVal : MathAbs(close1 - lo) / atrVal;
  }
//+------------------------------------------------------------------+
//| Fractal swing check - is the bar at shift=(InpFractalK+1) a        |
//| confirmed strict local extreme over the (2*InpFractalK+1)-bar      |
//| window centered on it (shift 1..2k+1, all now fully closed)?       |
//+------------------------------------------------------------------+
bool CheckNewSwingHigh(double &price)
  {
   int centerShift = InpFractalK + 1;
   double val = iHigh(_Symbol, PERIOD_M5, centerShift);
   for(int s = 1; s <= 2 * InpFractalK + 1; s++)
     {
      if(s == centerShift) continue;
      if(iHigh(_Symbol, PERIOD_M5, s) >= val) return(false);
     }
   price = val;
   return(true);
  }
//+------------------------------------------------------------------+
bool CheckNewSwingLow(double &price)
  {
   int centerShift = InpFractalK + 1;
   double val = iLow(_Symbol, PERIOD_M5, centerShift);
   for(int s = 1; s <= 2 * InpFractalK + 1; s++)
     {
      if(s == centerShift) continue;
      if(iLow(_Symbol, PERIOD_M5, s) <= val) return(false);
     }
   price = val;
   return(true);
  }
//+------------------------------------------------------------------+
//| Extrapolate the line through (t1,p1)->(t2,p2) (t1 older than t2)  |
//| to the bar at `atShift`. Returns false if either point is unset   |
//| or out of order.                                                   |
//+------------------------------------------------------------------+
bool GetTrendlineValue(datetime t1, double p1, datetime t2, double p2, int atShift, double &value)
  {
   if(t1 == 0 || t2 == 0) return(false);
   int shift1 = iBarShift(_Symbol, PERIOD_M5, t1, false);
   int shift2 = iBarShift(_Symbol, PERIOD_M5, t2, false);
   if(shift1 <= shift2) return(false);
   double slope = (p2 - p1) / (double)(shift1 - shift2);
   value = p2 + slope * (double)(shift2 - atShift);
   return(true);
  }
//+------------------------------------------------------------------+
//| Updates swing state for the bar that just closed, and returns any |
//| fresh breakout (edge-triggered) as dir (+1/-1/0).                 |
//+------------------------------------------------------------------+
int UpdateSwingsAndCheckBreakout()
  {
   double hiPrice, loPrice;
   if(CheckNewSwingHigh(hiPrice))
     {
      datetime formTime = iTime(_Symbol, PERIOD_M5, InpFractalK + 1);
      g_prevHiTime = g_curHiTime; g_prevHiPrice = g_curHiPrice;
      g_curHiTime  = formTime;    g_curHiPrice  = hiPrice;
     }
   if(CheckNewSwingLow(loPrice))
     {
      datetime formTime = iTime(_Symbol, PERIOD_M5, InpFractalK + 1);
      g_prevLoTime = g_curLoTime; g_prevLoPrice = g_curLoPrice;
      g_curLoTime  = formTime;    g_curLoPrice  = loPrice;
     }

   int dir = 0;
   double close1 = iClose(_Symbol, PERIOD_M5, 1);

   double descVal;
   bool descValid = GetTrendlineValue(g_prevHiTime, g_prevHiPrice, g_curHiTime, g_curHiPrice, 1, descVal)
                     && (g_curHiPrice < g_prevHiPrice);   // only a genuine descending (lower-highs) line
   bool aboveDesc = descValid && (close1 > descVal);
   if(descValid && g_prevDescValid && aboveDesc && !g_prevAboveDesc)
      dir = 1;
   g_prevAboveDesc = aboveDesc;
   g_prevDescValid = descValid;

   double ascVal;
   bool ascValid = GetTrendlineValue(g_prevLoTime, g_prevLoPrice, g_curLoTime, g_curLoPrice, 1, ascVal)
                     && (g_curLoPrice > g_prevLoPrice);   // only a genuine ascending (higher-lows) line
   bool belowAsc = ascValid && (close1 < ascVal);
   if(ascValid && g_prevAscValid && belowAsc && !g_prevBelowAsc)
      dir = -1;   // if both fired the same bar (rare), sell takes priority arbitrarily - documented, not hidden
   g_prevBelowAsc = belowAsc;
   g_prevAscValid = ascValid;

   return(dir);
  }
//+------------------------------------------------------------------+
//| VISUALS (v1.02) - see the header block above InpShowPanel for the |
//| overall design. Every function below is purely cosmetic: reads     |
//| trading/account state, writes nothing but chart objects, and can   |
//| never affect an entry, exit, sizing or risk decision.               |
//+------------------------------------------------------------------+
//| Panel primitives - reused verbatim from Aurelius_EA.mq5 (the       |
//| project's proven, bug-fixed implementation: the reclaim-on-new-    |
//| bar-only pattern that avoids visible flashing, the explicit         |
//| 4-strip frame instead of OBJ_RECTANGLE_LABEL's own unreliable       |
//| border, MT5 stacking objects by creation order not ZORDER).         |
//+------------------------------------------------------------------+
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
//+------------------------------------------------------------------+
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
//+------------------------------------------------------------------+
void PFrame(const string id, const int x, const int y, const int w, const int h,
            const color edge, const int thick = 2)
  {
   PRect(id + "ft", x,             y,             w,     thick, edge, edge, 0);   // top
   PRect(id + "fb", x,             y + h - thick, w,     thick, edge, edge, 0);   // bottom
   PRect(id + "fl", x,             y,             thick, h,     edge, edge, 0);   // left
   PRect(id + "fr", x + w - thick, y,             thick, h,     edge, edge, 0);   // right
  }
//+------------------------------------------------------------------+
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
//+------------------------------------------------------------------+
void PRow(const string id, const int x, const int y, const int w,
          const string label, const string value, const int state)
  {
   if(label == "" && value == "")
     {
      PText(id + "d", x, y, "", InpTextCol);
      PText(id + "l", x, y, "", InpTextCol);
      PText(id + "v", x, y, "", InpTextCol);
      return;
     }
   color dot = (state == 1) ? InpOkCol : (state == 0) ? InpNoCol : InpTextCol;
   PText(id + "d", x + 10, y, CharToString(108), dot, InpPanelSize + 1,
         false, "Wingdings");
   PText(id + "l", x + 26, y, label, InpTextCol);
   PText(id + "v", x + w - 12, y, value, InpValCol, 0, true);
   int need = 26 + EstimateTextWidth(label, InpPanelSize) + 16
              + EstimateTextWidth(value, InpPanelSize) + 20;
   if(need > g_panelMinW) g_panelMinW = need;
  }
//+------------------------------------------------------------------+
void PSection(const string id, const int x, const int y, const int w,
              const int rh, const string title)
  {
   PRect(id + "bar", x + 1, y - 3, w - 2, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x + 10, y, title, InpSectionCol, InpPanelSize, false, "Arial Bold");
  }
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
     { Print("BG: ObjectCreate failed, error ", GetLastError()); return; }

   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0, nm, OBJPROP_BMPFILE, 0, path);
   int err = GetLastError();

   if(!okSet || err != 0)
     {
      if(g_bgTries <= 3)
         PrintFormat("BG try %d: failed to load \"%s\"  set=%s  error=%d"
                     "  -> file must be at <data folder>\\MQL5\\Images\\%s",
                     g_bgTries, path, (okSet ? "true" : "false"), err,
                     InpBackgroundBMP);
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
   PrintFormat("BG: loaded \"%s\" on try %d", path, g_bgTries);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
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
//+------------------------------------------------------------------+
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
//| Level-line helpers (Aurelius pattern): created once, then UPDATED  |
//| IN PLACE, never deleted-and-recreated per bar - a stop or an S/R    |
//| level doesn't move every bar the way an MA does, so there's no      |
//| object-count growth to purge and no risk of re-burying the panel.   |
//+------------------------------------------------------------------+
void DeleteLevelLine(const string tag)
  {
   string nm = g_pl + tag;
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
  }
//+------------------------------------------------------------------+
void DrawLevelLine(const string tag, const double price, const color col,
                   const ENUM_LINE_STYLE style, const int width)
  {
   if(price <= 0.0) { DeleteLevelLine(tag); return; }
   string nm = g_pl + tag;
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTED, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| The signal line itself, drawn as an extending ray through the two  |
//| swing points that define it - NOT a per-bar segment like an MA:    |
//| a trendline is two fixed points, unchanged until the next swing    |
//| point replaces one of them, so it's created once and moved in      |
//| place (same update-in-place reasoning as DrawLevelLine) rather      |
//| than redrawn every bar.                                             |
//+------------------------------------------------------------------+
void DrawTrendlineRay(const string tag, const datetime t1, const double p1,
                       const datetime t2, const double p2, const color col)
  {
   if(t1 == 0 || t2 == 0 || t1 >= t2) { DeleteLevelLine(tag); return; }
   string nm = g_pl + tag;
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, nm, OBJPROP_TIME,  0, t1);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, p1);
   ObjectSetInteger(0, nm, OBJPROP_TIME,  1, t2);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, p2);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, true);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| Re-derives descValid/ascValid purely for drawing - deliberately     |
//| kept separate from UpdateSwingsAndCheckBreakout() (the trading      |
//| logic) rather than fused into it, matching Aurelius's own            |
//| separation of signal computation from cosmetics. Called once per     |
//| new bar, right after the trading logic has updated the swing         |
//| state, so it's reading this bar's real, final values.                |
//+------------------------------------------------------------------+
void UpdateSignalLines()
  {
   if(!InpShowSignalLine) { DeleteLevelLine("desc"); DeleteLevelLine("asc"); return; }

   double descVal;
   bool descValid = GetTrendlineValue(g_prevHiTime, g_prevHiPrice, g_curHiTime, g_curHiPrice, 1, descVal)
                     && (g_curHiPrice < g_prevHiPrice);
   if(descValid)
      DrawTrendlineRay("desc", g_prevHiTime, g_prevHiPrice, g_curHiTime, g_curHiPrice, InpColDesc);
   else
      DeleteLevelLine("desc");

   double ascVal;
   bool ascValid = GetTrendlineValue(g_prevLoTime, g_prevLoPrice, g_curLoTime, g_curLoPrice, 1, ascVal)
                     && (g_curLoPrice > g_prevLoPrice);
   if(ascValid)
      DrawTrendlineRay("asc", g_prevLoTime, g_prevLoPrice, g_curLoTime, g_curLoPrice, InpColAsc);
   else
      DeleteLevelLine("asc");
  }
//+------------------------------------------------------------------+
//| VWAP as an accumulating trail of per-bar segments - the actual      |
//| Aurelius pattern (DrawMASegment/PurgeOldMALines), not a single       |
//| update-in-place object: a trendline is two fixed points and belongs |
//| there, but VWAP's value genuinely changes every bar, so it needs     |
//| ONE NEW segment per bar (kept, not moved) to read as a continuous    |
//| line rather than a stub that jumps and erases itself. Bounded by     |
//| InpVwapHistoryBars via PurgeVWAPSegments so a long-running live EA   |
//| doesn't accumulate objects forever - VWAP resets every session       |
//| anyway, so nothing is lost by not keeping more than that. LIVE ONLY: |
//| no multi-day backfill on attach (a real scope reduction vs Aurelius, |
//| disclosed in the header) - a fresh attach starts showing today's     |
//| line building from whenever the EA attached, not prior sessions.     |
//| g_vwapPrevValue is snapshotted in OnTick right before UpdateVWAP()    |
//| runs, so it holds the value as of the end of the PREVIOUS bar.        |
//+------------------------------------------------------------------+
void DrawVWAPSegment(const datetime tOld, const double vOld, const datetime tNew, const double vNew)
  {
   string nm = g_pm + "vwap_" + IntegerToString((long)tNew);
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_TREND, 0, tOld, vOld, tNew, vNew);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, InpColVWAP);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
void PurgeVWAPSegments(const datetime latestBarTime)
  {
   datetime cutoff = latestBarTime - (datetime)((long)InpVwapHistoryBars * PeriodSeconds(PERIOD_M5));
   for(int i = ObjectsTotal(0, 0, OBJ_TREND) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, OBJ_TREND);
      if(StringFind(nm, g_pm) != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < cutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
void UpdateVWAPLine()
  {
   if(!InpShowVWAPLine) return;
   datetime t2 = iTime(_Symbol, PERIOD_M5, 2);
   datetime t1 = iTime(_Symbol, PERIOD_M5, 1);
   if(t2 == 0 || t1 == 0 || DayStart(t2) != DayStart(t1) || g_vwapPrevValue <= 0.0)
      return;   // session boundary or no prior value yet - nothing to connect
   DrawVWAPSegment(t2, g_vwapPrevValue, t1, g_vwapValue);
   PurgeVWAPSegments(t1);
  }
//+------------------------------------------------------------------+
//| Open position's entry/stop, and the S/R levels SRDistance() tests   |
//| against - both as horizontal lines (Aurelius pattern). Purely        |
//| cosmetic; SRDistance() itself still calls GetSRLevels() separately   |
//| so the drawn levels can never drift from the ones actually traded.   |
//+------------------------------------------------------------------+
void UpdateLevelLines()
  {
   if(InpShowTradeLevels && g_ticket != 0 && PositionSelectByTicket(g_ticket))
     {
      DrawLevelLine("entry", PositionGetDouble(POSITION_PRICE_OPEN), InpColEntryLine, STYLE_SOLID, 1);
      double sl = PositionGetDouble(POSITION_SL);
      if(sl > 0.0) DrawLevelLine("sl", sl, InpColStopLine, STYLE_SOLID, 1);
      else         DeleteLevelLine("sl");
     }
   else
     { DeleteLevelLine("entry"); DeleteLevelLine("sl"); }

   if(InpShowSR)
     {
      double hi, lo;
      if(GetSRLevels(hi, lo))
        {
         DrawLevelLine("srhi", hi, InpColSR, STYLE_DASH, 1);
         DrawLevelLine("srlo", lo, InpColSR, STYLE_DASH, 1);
        }
      else
        { DeleteLevelLine("srhi"); DeleteLevelLine("srlo"); }
     }
   else
     { DeleteLevelLine("srhi"); DeleteLevelLine("srlo"); }
  }
//+------------------------------------------------------------------+
//| Today's realized P/L for THIS EA only (own symbol+magic), from      |
//| calendar day start - simple HistorySelect scan rather than           |
//| Aurelius's incremental OnTradeTransaction accumulator: this           |
//| construction trades a few times a day at most, so the scan's cost     |
//| is negligible, and it's gated behind g_skipCosmeticDraws/the 1s        |
//| timer the same way regardless.                                        |
//+------------------------------------------------------------------+
double MyRealizedPLToday()
  {
   double sum = 0.0;
   if(!HistorySelect(DayStart(TimeCurrent()), TimeCurrent())) return(0.0);
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagic) continue;
      sum += HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_SWAP)
             + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
     }
   return(sum);
  }
//+------------------------------------------------------------------+
double MyFloatingPL()
  {
   double sum = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      sum += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   return(sum);
  }
//+------------------------------------------------------------------+
//| Dashboard content. Same section-based layout as Aurelius, but the   |
//| rows show what THIS construction actually tests (signal/entry        |
//| criteria/strategy for a trendline breakout), not a copy of            |
//| Aurelius's MA-alignment criteria.                                     |
//+------------------------------------------------------------------+
void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim)
  {
   //--- background/watermark are documented as independent of the panel
   //--- (InpShowPanel/InpWatermark are separate inputs) - drawn BEFORE
   //--- the panel's own early-return, found in review: nesting them
   //--- after the InpShowPanel gate silently disabled the watermark
   //--- whenever the panel itself was switched off.
   PBackground();
   PWatermark();
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }
   g_panelReclaim = reclaim;

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;
   int rh = InpPanelSize + 11;
   int hdr = rh + 14;
   //--- Counted directly against the literal ty+= sequence below, same
   //--- discipline as Aurelius's own derivation (it found a real off-by-
   //--- one doing this by guesswork instead): every PSection/PRow call
   //--- advances ty by rh (ROWS) and every section boundary adds a
   //--- further +6 (GAPS). In-position: a0 + s1+g1-g3 + s2+c1-c4 +
   //--- s3+d1-d4 + s4+p1-p4 + s5+q1-q4 = 25 rh-rows, 10 gap-boundaries.
   //--- Flat: identical through s4, but p4 there only advances +6 (no
   //--- rh) - one row shorter (24), same 10 gap-boundaries (p4's +6 and
   //--- s5's own gap both still happen).
   const int ROWS = (haveLong || haveShort) ? 25 : 24, GAPS = 10;
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH  = hdr + 10 + ROWS * rh + GAPS * 6 + 12;
   int guard = 0;
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     {
      rh--; guard++;
      hdr = rh + 14;
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
   int x = g_panX;
   int y = g_panY;

   PRect("sh", x + 4, y + 4, w, bodyH, InpShadowCol, InpShadowCol, 0);
   PRect("bg", x, y, w, bodyH, InpPanelBg, InpPanelBg, 0);
   PRect("fl", x + 2, y + 2, w - 4, bodyH - 4, InpPanelBg, InpPanelBg, 0);
   PFrame("bd", x, y, w, bodyH, InpPanelEdge, 2);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);

   int ty = y + 9;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "VANGUARD", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   bool algo = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED);
   PRow("a0", x, ty, w, "algo trading", algo ? "ON" : "OFF", algo ? 1 : 0);
   ty += rh + 6;

   //--- signal ------------------------------------------------------
   double descVal, ascVal;
   bool descValid = GetTrendlineValue(g_prevHiTime, g_prevHiPrice, g_curHiTime, g_curHiPrice, 1, descVal)
                     && (g_curHiPrice < g_prevHiPrice);
   bool ascValid = GetTrendlineValue(g_prevLoTime, g_prevLoPrice, g_curLoTime, g_curLoPrice, 1, ascVal)
                     && (g_curLoPrice > g_prevLoPrice);
   double close1 = iClose(_Symbol, PERIOD_M5, 1);
   PSection("s1", x, ty, w, rh, "SIGNAL"); ty += rh + 6;
   PRow("g1", x, ty, w, "descending line", descValid ? DoubleToString(descVal, _Digits) : "-",
        descValid ? (close1 > descVal ? 1 : -1) : -1); ty += rh;
   PRow("g2", x, ty, w, "ascending line", ascValid ? DoubleToString(ascVal, _Digits) : "-",
        ascValid ? (close1 < ascVal ? 1 : -1) : -1); ty += rh;
   PRow("g3", x, ty, w, "breakout this bar",
        g_barLastBreakoutDir > 0 ? "BUY" : (g_barLastBreakoutDir < 0 ? "SELL" : "no"), -1); ty += rh + 6;

   //--- entry criteria ------------------------------------------------
   double atr; bool haveATR = GetATR(atr);
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   double srBuy = haveATR ? SRDistance(true, atr) : -1.0;
   double srSell = haveATR ? SRDistance(false, atr) : -1.0;
   //--- CheckForEntry() only ever tests the ONE distance relevant to the
   //--- direction that actually broke out this bar - showing a combined
   //--- AND of both sides (found in review) could flag red on a bar
   //--- where a trade fires, or green when it wouldn't, whichever side
   //--- isn't actually being traded. Neutral (-1) when no breakout fired
   //--- this bar, since neither side is "the criteria being tested" yet.
   int srState = -1;
   if(haveATR && g_barLastBreakoutDir != 0)
     {
      double srActive = (g_barLastBreakoutDir > 0) ? srBuy : srSell;
      srState = (srActive >= InpMinSRDistATR || srActive < 0.0) ? 1 : 0;
     }
   PSection("s2", x, ty, w, rh, "ENTRY CRITERIA"); ty += rh + 6;
   PRow("c1", x, ty, w, "vs VWAP", close1 > g_vwapValue ? "above" : "below", -1); ty += rh;
   PRow("c2", x, ty, w, "S/R dist (buy/sell)",
        haveATR ? StringFormat("%.2f / %.2f ATR", srBuy, srSell) : "-", srState); ty += rh;
   PRow("c3", x, ty, w, "spread", (string)spr, spr <= InpMaxSpreadPoints ? 1 : 0); ty += rh;
   PRow("c4", x, ty, w, "ATR(14)", haveATR ? DoubleToString(atr, 2) : "-", -1); ty += rh + 6;

   //--- strategy ------------------------------------------------------
   PSection("s3", x, ty, w, rh, "STRATEGY"); ty += rh + 6;
   PRow("d1", x, ty, w, "fractal window", (string)InpFractalK + " bars", -1); ty += rh;
   PRow("d2", x, ty, w, "safety stop", DoubleToString(InpSafetyStopATR, 1) + " ATR", -1); ty += rh;
   PRow("d3", x, ty, w, "exit", "opposite breakout", -1); ty += rh;
   PRow("d4", x, ty, w, "sizing", StringFormat("%.2f @ %.2f ATR", InpBaseLots, InpRefATR), -1); ty += rh + 6;

   //--- position --------------------------------------------------
   PSection("s4", x, ty, w, rh, "POSITION"); ty += rh + 6;
   if(haveLong || haveShort)
     {
      double opx = 0.0, vol = 0.0, prof = 0.0;
      datetime opTime = 0;
      if(g_ticket != 0 && PositionSelectByTicket(g_ticket))
        {
         opx = PositionGetDouble(POSITION_PRICE_OPEN);
         vol = PositionGetDouble(POSITION_VOLUME);
         prof = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
         opTime = (datetime)PositionGetInteger(POSITION_TIME);
        }
      int barsHeld = (opTime > 0) ? (int)iBarShift(_Symbol, PERIOD_M5, opTime, false) : 0;
      PRow("p1", x, ty, w, haveLong ? "LONG" : "SHORT", DoubleToString(opx, _Digits), 1); ty += rh;
      PRow("p2", x, ty, w, "volume", DoubleToString(vol, 2), -1); ty += rh;
      PRow("p3", x, ty, w, "floating P/L", StringFormat("%+.2f", prof), prof >= 0 ? 1 : 0); ty += rh;
      PRow("p4", x, ty, w, "bars held", (string)barsHeld, -1); ty += rh + 6;
     }
   else
     {
      double nextLots = haveATR ? LotSize(atr) : InpBaseLots;
      PRow("p1", x, ty, w, "state", "FLAT", -1); ty += rh;
      PRow("p2", x, ty, w, "next lot size", DoubleToString(nextLots, 2), -1); ty += rh;
      PRow("p3", x, ty, w, "", "", -1); ty += rh;
      PRow("p4", x, ty, w, "", "", -1); ty += 6;
     }

   //--- account ------------------------------------------------------
   PSection("s5", x, ty, w, rh, "ACCOUNT"); ty += rh + 6;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double myDayPL = MyRealizedPLToday() + MyFloatingPL();
   PRow("q1", x, ty, w, "balance", DoubleToString(bal, 2), -1); ty += rh;
   PRow("q2", x, ty, w, "equity", DoubleToString(eq, 2), eq >= bal ? 1 : 0); ty += rh;
   PRow("q3", x, ty, w, "today (mine)", StringFormat("%+.2f", myDayPL), myDayPL >= 0 ? 1 : 0); ty += rh;
   PRow("q4", x, ty, w, "magic", (string)InpMagic, -1); ty += rh;

   static int warned = 0;
   int used = ty + 12 - y;
   if(used > bodyH && warned < 3)
     { warned++; PrintFormat("Panel: content %d px vs frame %d px", used, bodyH); }
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Live-queries the broker directly (Aurelius's own pattern), NOT     |
//| g_posDir/g_ticket: those are only resynced once per new bar (from   |
//| ManageOpenPosition/CheckForEntry), so a position closed mid-bar     |
//| (e.g. the resting stop-loss order filling) would otherwise leave     |
//| OnTimer's between-bar panel refresh showing a phantom position       |
//| with stale/zeroed details until the next new bar arrives - a real    |
//| bug caught in review, since OnTimer exists specifically to keep      |
//| the panel live when ticks/bars are sparse (weekend, closed session). |
//+------------------------------------------------------------------+
void CurrentPositions(bool &haveLong, bool &haveShort)
  {
   haveLong = false; haveShort = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) haveLong = true;
      else                                                       haveShort = true;
     }
  }
//+------------------------------------------------------------------+
//| Timer: keeps the panel alive (live P/L etc) when no ticks are      |
//| arriving, e.g. at the weekend or on a closed session. Same 1Hz      |
//| throttle and reclaim=false live-numbers-only refresh as Aurelius.   |
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(g_skipCosmeticDraws) return;
   bool hl, hs;
   CurrentPositions(hl, hs);
   //--- UpdateLevelLines() (found missing in review): without it, a
   //--- position closed mid-bar (SL fill, or the Friday flatten at the
   //--- top of OnTick which runs on every tick, not just new bars) left
   //--- the entry/stop-loss lines on the chart contradicting the panel
   //--- (already correctly showing FLAT via CurrentPositions' live
   //--- query) until the next new bar's OnTick call got there.
   UpdateLevelLines();
   DrawPanel(hl, hs, false);   // draws background/watermark internally regardless of InpShowPanel
   //--- always redraw (found in review): this only fires once a second
   //--- at most (EventSetTimer(1)) and is exactly the no-tick scenario
   //--- (weekend, closed session, AutoTrading toggled) OnTimer exists to
   //--- cover - gating it on hl||hs left a flat chart's panel (e.g. the
   //--- "algo trading" row) stale with nothing else around to redraw it.
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Dragging the background moves the whole panel (Aurelius pattern).  |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam,
                  const string &sparam)
  {
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_pp + "bg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      bool hl, hs;
      CurrentPositions(hl, hs);
      DrawPanel(hl, hs, false);
      ChartRedraw(0);
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      static int lastW = -1, lastH = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lastW || nh != lastH)
        {
         lastW = nw; lastH = nh; g_bgOK = false; g_bgTries = 0; PBackground();
         if(InpPanelBottom)
           {
            g_panX = -1;
            bool hl2, hs2;
            CurrentPositions(hl2, hs2);
            DrawPanel(hl2, hs2, false);
           }
        }
     }
  }
//+------------------------------------------------------------------+
//| ATR-inverse sizing (v1.01 - see header): InpBaseLots is the size  |
//| AT the reference ATR (InpRefATR, this construction's real average |
//| entry ATR over the validated backtest). A calmer-than-average bar |
//| sizes UP, a more volatile one sizes DOWN - real broker lot        |
//| step/floor enforced same as before, which is what makes this      |
//| asymmetric: it can't shrink below InpBaseLots's floor, so it only |
//| ever adds size in calm periods rather than removing it in wild    |
//| ones. That asymmetry is what was actually validated (see header)  |
//| - a naive unfloored version tested first showed misleadingly high |
//| floating DD from a scaling bug, not from the sizing idea itself.  |
//+------------------------------------------------------------------+
double LotSize(double atrVal)
  {
   double lots = InpBaseLots;
   if(atrVal > 0.0 && InpRefATR > 0.0)
      lots = InpBaseLots * (InpRefATR / atrVal);
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0.0) lots = MathRound(lots / step) * step;
   if(lots < mn) lots = mn;
   if(lots > mx) lots = mx;
   return(lots);
  }
//+------------------------------------------------------------------+
void NotifyPush(const string text)
  {
   if(!InpPushNotifications) return;
   SendNotification(StringSubstr(text, 0, 255));
  }
//+------------------------------------------------------------------+
bool IsFridayFlattenTime()
  {
   if(!InpCloseFriday) return(false);
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return(dt.day_of_week == 5 && dt.hour >= InpFridayCloseHour);
  }
//+------------------------------------------------------------------+
void CloseCurrentPosition(const string reason)
  {
   if(!PositionSelectByTicket(g_ticket)) { g_ticket = 0; g_posDir = 0; return; }
   if(trade.PositionClose(g_ticket))
     {
      g_ticket = 0;
      g_posDir = 0;
     }
   else
      PrintFormat("Vanguard EA: %s close FAILED for ticket %I64u, retcode %d (%s) - will retry next tick",
                  reason, g_ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
void ManageOpenPosition(int breakoutDir)
  {
   SyncPositionState();
   if(g_ticket == 0) return;

   if(IsFridayFlattenTime()) { CloseCurrentPosition("FRIDAY"); return; }

   if(breakoutDir != 0 && breakoutDir != g_posDir)
      CloseCurrentPosition("REVERSAL");
   // safety stop is a real resting SL order (set at entry) - the broker
   // enforces it even if this EA/terminal goes offline.
  }
//+------------------------------------------------------------------+
void CheckForEntry(int breakoutDir)
  {
   SyncPositionState();
   if(g_ticket != 0) return;
   if(IsFridayFlattenTime()) return;
   if(breakoutDir == 0) return;

   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadPts > InpMaxSpreadPoints) return;

   bool isBuy = (breakoutDir > 0);
   double close1 = iClose(_Symbol, PERIOD_M5, 1);
   bool confirmVWAP = isBuy ? (close1 > g_vwapValue) : (close1 < g_vwapValue);
   if(!confirmVWAP) return;

   double atr;
   if(!GetATR(atr) || atr <= 0.0) return;

   double sr = SRDistance(isBuy, atr);
   if(sr >= 0.0 && sr < InpMinSRDistATR) return;

   double px = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = isBuy ? px - InpSafetyStopATR * atr : px + InpSafetyStopATR * atr;
   double lots = LotSize(atr);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   bool ok = isBuy ? trade.Buy(lots, _Symbol, px, sl, 0.0, InpTradeComment)
                    : trade.Sell(lots, _Symbol, px, sl, 0.0, InpTradeComment);
   if(ok)
      SyncPositionState();
   else
      PrintFormat("Vanguard EA: entry FAILED, retcode %d (%s)",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   // Calibrated for M5 only - InpFractalK=100 needs 200 bars either
   // side plus safety-stop math tuned for M5's ATR scale; a mismatched
   // chart period would run the same logic against a different bar
   // structure entirely, invalidating every validated number.
   if(_Period != PERIOD_M5)
     {
      PrintFormat("Vanguard EA: this system is calibrated for M5 only - attach it to an M5 chart "
                  "(currently on period %d)", _Period);
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   SeedVWAP();
   SyncPositionState();
   g_lastBarTime = 0;

   //--- visuals (v1.02) - same performance guard as Aurelius: skip every
   //--- cosmetic draw entirely in a non-visual Strategy Tester pass,
   //--- where nobody can see the chart and it would only slow the run.
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);
   if(!g_skipCosmeticDraws)
     {
      PTheme();
      PBackground();
      UpdateLevelLines();
      bool hl0, hs0;
      CurrentPositions(hl0, hs0);
      if(InpShowPanel) DrawPanel(hl0, hs0);   // show something the moment it attaches
      EventSetTimer(1);
     }

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   //--- clean up everything the visuals drew (found missing in review) -
   //--- without this, the panel/watermark/S-R/entry-stop lines and the
   //--- background bitmap stayed on the chart permanently after the EA
   //--- was removed. Chart THEME colours (PTheme()) are deliberately
   //--- left as-is: recolouring the chart is a standing user choice the
   //--- same way changing it manually would be, not tied to the EA's
   //--- own lifetime, and MT5 has no reliable "restore previous colour"
   //--- API to revert to (only a fixed default, which may not be what
   //--- the user had before attaching this EA).
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pw);
   ObjectsDeleteAll(0, g_pm);
   ObjectsDeleteAll(0, g_pl);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   if(g_ticket != 0 && IsFridayFlattenTime())
     {
      SyncPositionState();
      if(g_ticket != 0) CloseCurrentPosition("FRIDAY");
     }

   if(!IsNewBar()) return;

   double vwapPrev = g_vwapValue;
   UpdateVWAP();
   int breakoutDir = UpdateSwingsAndCheckBreakout();
   g_barLastBreakoutDir = breakoutDir;

   // NOT else-if: a reversal breakout must close the old position AND
   // open the new opposite one on the SAME bar (matches the Python
   // validation's semantics, where the opposite-direction event is both
   // the exit and the next entry at one fill). Splitting these into
   // mutually-exclusive branches would silently drop the entry, since
   // the breakout is edge-triggered and won't fire again next bar.
   if(g_ticket != 0)
      ManageOpenPosition(breakoutDir);
   if(g_ticket == 0)
      CheckForEntry(breakoutDir);

   //--- visuals (v1.02) - purely cosmetic, runs after every trading
   //--- decision above so the panel/lines reflect this bar's real,
   //--- final state. reclaim=true here (once per new bar) is the only
   //--- time the panel needs to reclaim top-of-stack - see g_panelReclaim.
   if(!g_skipCosmeticDraws)
     {
      g_vwapPrevValue = vwapPrev;
      UpdateSignalLines();
      UpdateVWAPLine();
      UpdateLevelLines();
      bool hl, hs;
      CurrentPositions(hl, hs);
      if(InpShowPanel) DrawPanel(hl, hs, true);
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   if((long)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != (long)InpMagic) return;

   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   double price = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   double vol = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   long dtype = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   string side = (dtype == DEAL_TYPE_BUY) ? "BUY" : "SELL";

   if(entry == DEAL_ENTRY_IN)
      NotifyPush(StringFormat("Vanguard %s OPEN %.2f lots @ %.2f", side, vol, price));
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      NotifyPush(StringFormat("Vanguard %s CLOSE %.2f lots @ %.2f P/L=%.2f", side, vol, price, profit));
     }
  }
//+------------------------------------------------------------------+
