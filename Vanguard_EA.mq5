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
#property version   "1.01"
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
//| Distance (xATR) from the last closed bar's close to the nearer of |
//| the last InpSRDays COMPLETED daily highs/lows - identical to       |
//| Meridian_EA.mq5's SRDistance(), reused verbatim.                   |
//+------------------------------------------------------------------+
double SRDistance(bool isBuy, double atrVal)
  {
   if(atrVal <= 0.0) return(-1.0);
   double hi = -DBL_MAX, lo = DBL_MAX;
   for(int d = 1; d <= InpSRDays; d++)
     {
      double h = iHigh(_Symbol, PERIOD_D1, d);
      double l = iLow(_Symbol, PERIOD_D1, d);
      if(h <= 0.0 || l <= 0.0) return(-1.0);
      if(h > hi) hi = h;
      if(l < lo) lo = l;
     }
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

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
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

   UpdateVWAP();
   int breakoutDir = UpdateSwingsAndCheckBreakout();

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
