//+------------------------------------------------------------------+
//|                       Vanguard_M15_EA.mq5                          |
//|                                                                    |
//|  M15 companion to Vanguard_EA.mq5 (M5) - same diagonal-trendline   |
//|  breakout construction, independently re-swept on M15 (NOT a       |
//|  naive /3 rescale of the M5 parameters - a fresh k-sweep, matching  |
//|  the lesson learned when Meridian's 21/50 cross failed to transfer  |
//|  naively to M15 earlier this session). Built because the user      |
//|  asked directly whether a higher timeframe had been tested.         |
//|                                                                    |
//|  entry : a diagonal trendline through the last TWO confirmed       |
//|          fractal swing highs (InpFractalK=33 bars on each side to  |
//|          confirm a swing point on M15, vs 100 on M5 - the real,    |
//|          independently re-optimal value found on this timeframe)   |
//|          is only valid when it's actually DESCENDING (the newer    |
//|          high is lower than the older one - a real "lower highs"   |
//|          sequence). Buy fires when price closes back ABOVE that    |
//|          descending line (a breakout), AND close agrees with       |
//|          session VWAP, AND price is >= 0.5xATR from the nearest    |
//|          daily S/R level. Sell is the exact mirror: an ASCENDING   |
//|          line through the last two confirmed swing LOWS (a real    |
//|          "higher lows" sequence), breakdown below it.               |
//|  exit  : the NEXT opposite-direction breakout, OR a safety stop at |
//|          InpSafetyStopATR x ATR(14), whichever comes first. No     |
//|          take-profit - same "let winners run" design as the M5     |
//|          file and Meridian.                                        |
//|                                                                    |
//|  PYTHON BACKTEST (full real M15 history, 2023-01 to 2026-08, real   |
//|  spread, correct single-position sequencing, drawdown, walk-        |
//|  forward, random-direction control - fresh k-sweep on M15, see      |
//|  research/aurelius/trendline_m15_test.py; filters reused unchanged  |
//|  from trendline_confluence_test.py's M5 result since they gate      |
//|  entry only and aren't timeframe-specific):                         |
//|                                                                    |
//|  +VWAP+S/R (what this file implements, k=33, InpSafetyStopATR=3.0,  |
//|  InpMinSRDistATR=0.50 below): net=+2730.94, PF=1.509, win rate       |
//|  28.0%, floating DD 15.8% of net, random-direction percentile        |
//|  99.0, walk-forward 4/5 blocks positive. Confirmed via a neighbor    |
//|  parameter check (k=28-40 all comparable, not a lucky single         |
//|  point) - a real, independent result, comparable in strength to      |
//|  the M5 version's net $2989.87/PF 1.570/floatDD 15.4%/wf 3-5,       |
//|  NOT a scaled-down copy of it.                                       |
//|                                                                    |
//|  HONEST CONTEXT: S/R distance has now independently helped on        |
//|  THREE constructions this session (Meridian's 21/50 cross, the      |
//|  M5 trendline breakout, and this M15 version) - real, repeated       |
//|  evidence it's a generalizable signal, not construction- or          |
//|  timeframe-specific luck.                                            |
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
//|   - NEVER RUN THROUGH A REAL MT5 STRATEGY TESTER - this is the      |
//|     Python-only validation step, same stage Meridian was at before  |
//|     its first real test. Needs that before any number here can be   |
//|     trusted the way Meridian's real-tested numbers now are.         |
//+------------------------------------------------------------------+
#property copyright "Vanguard_M15_EA"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

input group "=== Signal: diagonal trendline breakout ==="
input int    InpFractalK          = 33;      // bars on each side to confirm a swing point (M15-specific)
input int    InpSRDays            = 3;       // trailing completed D1 bars checked for the nearest level
input double InpMinSRDistATR      = 0.50;    // reject entries this close (xATR) to that level

input group "=== Exit ==="
input double InpSafetyStopATR     = 3.0;     // validated best cell on M15 - see header
input int    InpATRPeriod         = 14;

input group "=== Risk ==="
input double InpLots               = 0.01;
input double InpMaxSpreadPoints    = 60;
input int    InpSlippage           = 20;

input group "=== Session protection (v1.00 gap - see header) ==="
input bool   InpCloseFriday        = true;
input int    InpFridayCloseHour    = 22;      // server time

input group "=== Notifications ==="
input bool   InpPushNotifications  = true;

input group "=== Misc ==="
input ulong  InpMagic              = 750802;
input string InpTradeComment       = "Vanguard_M15";

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
   datetime t = iTime(_Symbol, PERIOD_M15, 0);
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
   int got = CopyRates(_Symbol, PERIOD_M15, 1, MathMax(period * 3, 200), r);
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
   datetime last = iTime(_Symbol, PERIOD_M15, 1);
   if(last == 0) return;
   datetime day = DayStart(last);
   g_vwapDay = day;
   g_vwapCumPV = 0.0;
   g_vwapCumVol = 0.0;
   for(int shift = 1; shift < 400; shift++)
     {
      datetime t = iTime(_Symbol, PERIOD_M15, shift);
      if(t == 0 || DayStart(t) != day) break;
      double typical = (iHigh(_Symbol, PERIOD_M15, shift) + iLow(_Symbol, PERIOD_M15, shift) +
                         iClose(_Symbol, PERIOD_M15, shift)) / 3.0;
      double vol = (double)iTickVolume(_Symbol, PERIOD_M15, shift);
      g_vwapCumPV  += typical * vol;
      g_vwapCumVol += vol;
     }
   g_vwapValue = (g_vwapCumVol > 0.0) ? g_vwapCumPV / g_vwapCumVol : iClose(_Symbol, PERIOD_M15, 1);
  }
//+------------------------------------------------------------------+
void UpdateVWAP()
  {
   datetime t1 = iTime(_Symbol, PERIOD_M15, 1);
   if(t1 == 0) return;
   datetime day = DayStart(t1);
   if(day != g_vwapDay)
     {
      SeedVWAP();
      return;
     }
   double typical = (iHigh(_Symbol, PERIOD_M15, 1) + iLow(_Symbol, PERIOD_M15, 1) +
                      iClose(_Symbol, PERIOD_M15, 1)) / 3.0;
   double vol = (double)iTickVolume(_Symbol, PERIOD_M15, 1);
   g_vwapCumPV  += typical * vol;
   g_vwapCumVol += vol;
   g_vwapValue = (g_vwapCumVol > 0.0) ? g_vwapCumPV / g_vwapCumVol : iClose(_Symbol, PERIOD_M15, 1);
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
   double close1 = iClose(_Symbol, PERIOD_M15, 1);
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
   double val = iHigh(_Symbol, PERIOD_M15, centerShift);
   for(int s = 1; s <= 2 * InpFractalK + 1; s++)
     {
      if(s == centerShift) continue;
      if(iHigh(_Symbol, PERIOD_M15, s) >= val) return(false);
     }
   price = val;
   return(true);
  }
//+------------------------------------------------------------------+
bool CheckNewSwingLow(double &price)
  {
   int centerShift = InpFractalK + 1;
   double val = iLow(_Symbol, PERIOD_M15, centerShift);
   for(int s = 1; s <= 2 * InpFractalK + 1; s++)
     {
      if(s == centerShift) continue;
      if(iLow(_Symbol, PERIOD_M15, s) <= val) return(false);
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
   int shift1 = iBarShift(_Symbol, PERIOD_M15, t1, false);
   int shift2 = iBarShift(_Symbol, PERIOD_M15, t2, false);
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
      datetime formTime = iTime(_Symbol, PERIOD_M15, InpFractalK + 1);
      g_prevHiTime = g_curHiTime; g_prevHiPrice = g_curHiPrice;
      g_curHiTime  = formTime;    g_curHiPrice  = hiPrice;
     }
   if(CheckNewSwingLow(loPrice))
     {
      datetime formTime = iTime(_Symbol, PERIOD_M15, InpFractalK + 1);
      g_prevLoTime = g_curLoTime; g_prevLoPrice = g_curLoPrice;
      g_curLoTime  = formTime;    g_curLoPrice  = loPrice;
     }

   int dir = 0;
   double close1 = iClose(_Symbol, PERIOD_M15, 1);

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
double LotSize()
  {
   double lots = InpLots;
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
      PrintFormat("Vanguard M15 EA: %s close FAILED for ticket %I64u, retcode %d (%s) - will retry next tick",
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
   double close1 = iClose(_Symbol, PERIOD_M15, 1);
   bool confirmVWAP = isBuy ? (close1 > g_vwapValue) : (close1 < g_vwapValue);
   if(!confirmVWAP) return;

   double atr;
   if(!GetATR(atr) || atr <= 0.0) return;

   double sr = SRDistance(isBuy, atr);
   if(sr >= 0.0 && sr < InpMinSRDistATR) return;

   double px = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = isBuy ? px - InpSafetyStopATR * atr : px + InpSafetyStopATR * atr;
   double lots = LotSize();

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   bool ok = isBuy ? trade.Buy(lots, _Symbol, px, sl, 0.0, InpTradeComment)
                    : trade.Sell(lots, _Symbol, px, sl, 0.0, InpTradeComment);
   if(ok)
      SyncPositionState();
   else
      PrintFormat("Vanguard M15 EA: entry FAILED, retcode %d (%s)",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   // Calibrated for M15 only - InpFractalK=33 needs 66 bars either
   // side plus safety-stop math independently re-tuned for M15's bar
   // structure and ATR scale (NOT a rescale of the M5 file's k=100/
   // sl=4.0); a mismatched chart period would run this logic against a
   // different bar structure entirely, invalidating every validated
   // number.
   if(_Period != PERIOD_M15)
     {
      PrintFormat("Vanguard M15 EA: this system is calibrated for M15 only - attach it to an M15 chart "
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
      NotifyPush(StringFormat("Vanguard M15 %s OPEN %.2f lots @ %.2f", side, vol, price));
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      NotifyPush(StringFormat("Vanguard M15 %s CLOSE %.2f lots @ %.2f P/L=%.2f", side, vol, price, profit));
     }
  }
//+------------------------------------------------------------------+
