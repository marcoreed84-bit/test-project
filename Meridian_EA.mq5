//+------------------------------------------------------------------+
//|                          Meridian_EA.mq5                          |
//|                                                                    |
//|  NEW, standalone system - NOT a modification of Aurelius_EA.mq5,   |
//|  built from a clean file per the user's explicit request. Entry   |
//|  and exit logic below is exactly the winning construction from    |
//|  this session's research (research/aurelius/m5_stack_variants_    |
//|  fixed_test.py, the corrected version - see that file's header    |
//|  for the bug that was found and fixed in the earlier, uncorrected |
//|  pass before this was trusted):                                   |
//|                                                                    |
//|  entry : 21 EMA crosses the 50 EMA (M5, close-based) AND, at that  |
//|          exact bar, close is on the trend side of BOTH the 150     |
//|          EMA and the session VWAP - buy needs close>150EMA AND     |
//|          close>VWAP, sell the mirror.                              |
//|  exit  : the NEXT raw 21/50 cross in the opposite direction        |
//|          (unconfirmed - no 150/VWAP re-check on exit, matching     |
//|          the validated design: the filter gates entry only, it     |
//|          does not gate the reversal exit) OR a safety stop at      |
//|          InpSafetyStopATR x ATR(14), whichever comes first. No     |
//|          take-profit - this rides the leg until it actually        |
//|          reverses, by design.                                      |
//|                                                                    |
//|  PYTHON BACKTEST (full real M5 history, 2023-01 to 2026-08,        |
//|  256,318 bars, real spread, correct single-position sequencing,    |
//|  random-direction control, 5-block walk-forward - all re-verified  |
//|  after catching and fixing a same-direction-exit bug in the first  |
//|  pass): 2603 trades, net +3184.61 (price-difference $, ~2.9        |
//|  trades/day, median hold 2.6h / mean 5.3h - NOT a scalp), PF       |
//|  1.300, win rate 26.0%, random-direction percentile 99.7,          |
//|  walk-forward 4/5 blocks positive (2023 Jan-Sep is the one losing  |
//|  block, -68, the smallest loss of any construction tried this      |
//|  session there). Closed-trade max drawdown 323 (10.1% of net),     |
//|  bar-by-bar mark-to-market floating max drawdown 391 (12.3% of     |
//|  net).                                                              |
//|                                                                    |
//|  HONEST COMPARISON TO AURELIUS (asked directly before this was     |
//|  built): Aurelius's own real, LIVE MT5 Strategy Tester result      |
//|  (see Aurelius_EA.mq5's header) is PF 1.56 on real-tick execution  |
//|  (Python backtest PF 1.51) - both meaningfully higher than this    |
//|  system's 1.30 (Python) / 1.244 (real, see below). Aurelius's real |
//|  documented weakness is a 27.69% equity drawdown (a position       |
//|  floated ~$1184 underwater once) vs 9.76% balance drawdown - a     |
//|  known, still-being-worked-on risk. Verdict at build time was that |
//|  this does NOT look better than Aurelius, and the real test below  |
//|  CONFIRMS that rather than softening it - real drawdown here is    |
//|  worse than Aurelius's own documented weak point, not better.      |
//|                                                                    |
//|  REAL MT5 STRATEGY TESTER RESULT (2026-09-21, XM Global GOLD#, M5, |
//|  2023.01.01-2026.09.19, 20000 ZAR deposit, InpLots=0.01, real-tick |
//|  execution, 84% real-tick history quality): 2512 trades, PF        |
//|  1.243712 (vs Python's 1.300 - close agreement, confirms the       |
//|  signal is real, not a backtest artifact), win rate 26.75% (vs     |
//|  Python's 26.0%), avg hold 4h13m, net +44899.83 ZAR. BUT: Balance  |
//|  Drawdown Maximal 35.96% (8094.79), Equity Drawdown Maximal        |
//|  36.78% (8324.51) - WORSE than Aurelius's real 27.69%. Reconciled  |
//|  the deal-by-deal balance curve: peak was 2023-06-09, trough was   |
//|  2024-11-06 - a 17-MONTH drawdown before recovery, not one bad     |
//|  trade. Yearly net: 2023 +20365, 2024 -2799 (the losing year the   |
//|  drawdown traces to), 2025 +10218, 2026 +37116. The 0.01-lot /     |
//|  3.0xATR-stop design was never checked against account size before |
//|  this ran - a 20000 ZAR (~$1100) account carrying gold-CFD ATR     |
//|  stops is thin relative to this system's per-trade risk, which is  |
//|  a real contributor to the severity here, not just the signal      |
//|  itself. VERDICT UNCHANGED, REINFORCED: not better than Aurelius,  |
//|  real but not ready to trade as-is - needs either a materially     |
//|  larger account, a tighter/scaled stop, or a real defensive filter |
//|  layer (the thing Aurelius has that this doesn't) before more than |
//|  demo exposure would be responsible.                               |
//|                                                                    |
//|  KNOWN v1.00 GAPS (flagged, not fixed, so they don't get lost):    |
//|   - No visual panel/wallpaper - deliberately out of scope for a    |
//|     first pass; every other EA in this project has one, this one   |
//|     can get one later if the system proves out.                    |
//|   - Friday flatten is day-of-week + hour only - no full US-market  |
//|     holiday calendar (IsMarketHoliday/DSTGapHourAdjustment ported  |
//|     in every sibling EA) - a holiday weekend could still leave a   |
//|     position open into a gap this file won't catch.                |
//|   - ATR uses this project's own Wilder recursion (ComputeWilderATR |
//|     below), NOT MT5's built-in iATR - Aurelius's v1.36 note found  |
//|     this broker's iATR is a plain SMA(period) of true range, not   |
//|     real Wilder smoothing. Matches engine.py's wilder_atr exactly. |
//+------------------------------------------------------------------+
#property copyright "Meridian_EA"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

input group "=== Signal: 21/50 cross, 150 + VWAP confirmed ==="
input int    InpP21             = 21;
input int    InpP50             = 50;
input int    InpP150            = 150;
input ENUM_MA_METHOD InpMAMethod = MODE_EMA;

input group "=== Exit ==="
input double InpSafetyStopATR   = 3.0;      // validated best cell - see header
input int    InpATRPeriod       = 14;

input group "=== Risk ==="
input double InpLots            = 0.01;
input double InpMaxSpreadPoints = 60;
input int    InpSlippage        = 20;

input group "=== Session protection (v1.00 gap - see header) ==="
input bool   InpCloseFriday     = true;
input int    InpFridayCloseHour = 22;       // server time

input group "=== Notifications ==="
input bool   InpPushNotifications = true;

input group "=== Misc ==="
input ulong  InpMagic           = 750731;
input string InpTradeComment    = "Meridian";

//--- indicator handles
int h21 = INVALID_HANDLE, h50 = INVALID_HANDLE, h150 = INVALID_HANDLE;

//--- restart-safe position state (re-synced from the live account every
//--- check, not trusted from cache alone - see FindOwnPosition() and its
//--- callers; this is the exact bug class an earlier session found and
//--- fixed across every other EA in this project)
ulong    g_ticket  = 0;
int      g_posDir  = 0;      // +1 long, -1 short, 0 flat

//--- single-latch new-bar gate (called exactly once per tick - the
//--- double-call pattern found and fixed in Slipstream/Tailwind this
//--- session silently ate bars when called from two places per tick)
datetime g_lastBarTime = 0;

//--- session VWAP (cumulative typical-price*volume from each calendar
//--- day's first bar - matches engine.py's session_vwap() exactly, no
//--- built-in MT5 VWAP indicator exists)
datetime g_vwapDay    = 0;
double   g_vwapCumPV  = 0.0;
double   g_vwapCumVol = 0.0;
double   g_vwapValue  = 0.0;

//--- manual Wilder ATR (see header - NOT iATR)
double   g_atrBuf[];

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
//| project's engine.wilder_atr(): SMA seed of the first `period` true|
//| ranges, then Wilder recursive smoothing. Called once per new bar. |
//+------------------------------------------------------------------+
void ComputeWilderATR(double &out[], int period)
  {
   int need = period + 2;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   // start_pos=1: r[0] is the last CLOSED bar (shift 1), never the still-
   // forming current bar - matches this project's shift=1 convention
   // (engine.py: "index i means bar i has just closed") everywhere else.
   int got = CopyRates(_Symbol, PERIOD_M5, 1, MathMax(period * 3, 200), r);
   if(got < need) { ArrayResize(out, 1); out[0] = 0.0; return; }
   ArraySetAsSeries(out, true);
   ArrayResize(out, got);
   double tr[];
   ArrayResize(tr, got);
   for(int i = 0; i < got - 1; i++)
     {
      double hi = r[i].high, lo = r[i].low, pc = r[i + 1].close;
      tr[i] = MathMax(hi - lo, MathMax(MathAbs(hi - pc), MathAbs(lo - pc)));
     }
   // tr[] is series-ordered (index 0 = most recent); Wilder needs
   // chronological seeding, so walk from the oldest available bar forward.
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
//| Session VWAP - seeds from the current calendar day's first bar on |
//| a (re)start, then updates incrementally one closed bar at a time. |
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
      double typical = (iHigh(_Symbol, PERIOD_M5, shift) +
                         iLow(_Symbol, PERIOD_M5, shift) +
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
bool MA(int handle, int shift, double &value)
  {
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle, 0, shift, 1, buf) < 1) return(false);
   value = buf[0];
   return(true);
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
      PrintFormat("Meridian EA: %s close FAILED for ticket %I64u, retcode %d (%s) - will retry next tick",
                  reason, g_ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
//| Detects the raw 21/50 cross on the bar that JUST closed (shift 1  |
//| vs shift 2) - used for both entry (with confirmation) and exit    |
//| (unconfirmed, per the validated design).                          |
//+------------------------------------------------------------------+
bool DetectCross(int &direction)
  {
   double m21_1, m21_2, m50_1, m50_2;
   if(!MA(h21, 1, m21_1) || !MA(h21, 2, m21_2) || !MA(h50, 1, m50_1) || !MA(h50, 2, m50_2))
      return(false);
   bool aboveNow  = m21_1 > m50_1;
   bool abovePrev = m21_2 > m50_2;
   if(aboveNow == abovePrev) return(false);
   direction = aboveNow ? 1 : -1;
   return(true);
  }
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   SyncPositionState();
   if(g_ticket == 0) return;

   if(IsFridayFlattenTime()) { CloseCurrentPosition("FRIDAY"); return; }

   int dir;
   if(DetectCross(dir) && dir != g_posDir)
      CloseCurrentPosition("REVERSAL");
   // safety stop is a real resting SL order on the position (set at
   // entry, see CheckForEntry) - the broker enforces it even if this
   // EA/terminal goes offline, so nothing further to do for it here.
  }
//+------------------------------------------------------------------+
void CheckForEntry()
  {
   SyncPositionState();
   if(g_ticket != 0) return;
   if(IsFridayFlattenTime()) return;

   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadPts > InpMaxSpreadPoints) return;

   int dir;
   if(!DetectCross(dir)) return;

   double m150_1, close1 = iClose(_Symbol, PERIOD_M5, 1);
   if(!MA(h150, 1, m150_1)) return;

   bool isBuy = (dir > 0);
   bool confirm150 = isBuy ? (close1 > m150_1) : (close1 < m150_1);
   bool confirmVWAP = isBuy ? (close1 > g_vwapValue) : (close1 < g_vwapValue);
   if(!confirm150 || !confirmVWAP) return;

   double atr;
   if(!GetATR(atr) || atr <= 0.0) return;

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
      PrintFormat("Meridian EA: entry FAILED, retcode %d (%s)",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   // Every number in this EA's header (the validated M5 backtest) was
   // calibrated specifically on M5 bars - all internal calls already use
   // PERIOD_M5 explicitly (not PERIOD_CURRENT), so this only prevents a
   // chart-attach mistake (e.g. dropped on an M15/H1 chart by habit) from
   // running silently: the EA would still fetch and trade M5 data
   // correctly regardless of the chart it's on, but a mismatched chart
   // period is exactly the kind of easy-to-miss setup error this project
   // has hit before (ExportBarData.mq5's PERIOD_M5-default bug earlier
   // this session) - refuse to load rather than risk it going unnoticed.
   if(_Period != PERIOD_M5)
     {
      PrintFormat("Meridian EA: this system is calibrated for M5 only - attach it to an M5 chart "
                  "(currently on period %d)", _Period);
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   h21  = iMA(_Symbol, PERIOD_M5, InpP21,  0, InpMAMethod, PRICE_CLOSE);
   h50  = iMA(_Symbol, PERIOD_M5, InpP50,  0, InpMAMethod, PRICE_CLOSE);
   h150 = iMA(_Symbol, PERIOD_M5, InpP150, 0, InpMAMethod, PRICE_CLOSE);
   if(h21 == INVALID_HANDLE || h50 == INVALID_HANDLE || h150 == INVALID_HANDLE)
     {
      Print("Meridian EA: indicator handle creation failed");
      return(INIT_FAILED);
     }

   SeedVWAP();
   SyncPositionState();   // restart with a position already open - see header
   g_lastBarTime = 0;     // force IsNewBar() true on the first tick

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(h21);
   IndicatorRelease(h50);
   IndicatorRelease(h150);
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- tick-level Friday backstop, evaluated before the new-bar gate -
   //--- a thin-liquidity Friday can leave few/no ticks right at the
   //--- cutoff hour if gated on a bar close alone (same fix pattern as
   //--- every sibling EA's WeekendStillOpen()).
   if(g_ticket != 0 && IsFridayFlattenTime())
     {
      SyncPositionState();
      if(g_ticket != 0) CloseCurrentPosition("FRIDAY");
     }

   if(!IsNewBar()) return;

   // Unconditional, every new bar regardless of position state - VWAP is
   // a running cumulative sum, so skipping bars while in a trade would
   // silently undercount volume and desync it the moment the position
   // eventually closes and CheckForEntry() reads it again.
   UpdateVWAP();

   if(g_ticket != 0)
      ManageOpenPosition();
   else
      CheckForEntry();
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
      NotifyPush(StringFormat("Meridian %s OPEN %.2f lots @ %.2f", side, vol, price));
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      NotifyPush(StringFormat("Meridian %s CLOSE %.2f lots @ %.2f P/L=%.2f", side, vol, price, profit));
     }
  }
//+------------------------------------------------------------------+
