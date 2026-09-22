//+------------------------------------------------------------------+
//|                        MSG_Trader_EA.mq5                          |
//|                                                                    |
//|  RECONSTRUCTION, not a port. No source for MSG_Trader_EA_v1.1     |
//|  exists in this project - only a real MT5 Strategy Tester report  |
//|  (account 1301880049, GOLD#, M5, 2026.06.01-2026.08.31, 0.03      |
//|  lots) was available. Built at the user's explicit request after  |
//|  being asked directly ("I don't see the source... how should I    |
//|  proceed?") and choosing reverse-engineering over waiting for the |
//|  real file. What follows is separated into what the report        |
//|  actually PROVED vs what is this file's own best-effort inference |
//|  - do not treat the inferred parts as verified.                   |
//|                                                                    |
//|  CONFIRMED from the real report (exact, not guessed):              |
//|   - Every input name/value in the Settings block below (lots,      |
//|     magic, slippage, fib SL %, scale-out RR levels 1.0/1.5/2.0,    |
//|     trail RR 1.0, max hold 48h, all 4 session windows, chart-draw  |
//|     toggles, history days) - copied verbatim from the report.      |
//|   - The broker-side take-profit is EXACTLY entry +/- 2.000x the    |
//|     position's own risk (SL distance) on every one of 68 real      |
//|     trades checked (mean RR=2.0001, stdev=0.0007) - matches         |
//|     InpTP3_RR=2.0 used as the final/outer target.                  |
//|   - Only MSG1 (22:00-00:00 GMT) and MSG3 (09:00-12:00 GMT) were    |
//|     enabled in the tested run; MSG2/MSG4 never fired a trade.      |
//|   - Entries cluster in a 60-90% retracement zone of that session's |
//|     own high/low range (mean 80.4%, median 75.1% across 47 sampled |
//|     trades, measured against real M5 bars) - a classic Fibonacci   |
//|     "OTE" continuation entry, not a flat breakout-at-the-extreme.  |
//|   - Stop-loss distance is NOT a fixed fib % of that range (matches |
//|     InpFixedFibSL=false): measured SL retracement % varied bar to  |
//|     bar (0%, 25-40%, up to 57%) rather than clustering on one       |
//|     constant - consistent with a structural (swing-based) stop,    |
//|     not InpFibSLPct applied directly.                               |
//|                                                                    |
//|  INFERRED (this file's own design, not verifiable without the      |
//|  real source - flagged so it is never mistaken for a proven port): |
//|   - The exact retracement zone boundary (61.8%-78.6%, the standard |
//|     ICT/fib "OTE" window). The stop distance itself (InpRangeRiskPct|
//|     of the session range) IS real-data-calibrated as of v1.04 - see |
//|     its own header note below - not left as a guess.               |
//|   - InpTPMode's meaning (0 = 3-stage scale-out via TP1/TP2/TP3;     |
//|     any other value = single fixed target at InpTP_RR) - the       |
//|     report only ever showed TPMode=0.                              |
//|   - InpTrailRR's exact behaviour (implemented here as: move the    |
//|     stop to breakeven once floating profit reaches InpTrailRR x    |
//|     the original risk - a common, simple reading of "trail RR",    |
//|     not the only possible one).                                    |
//|   - GMT-offset auto-detection (TimeGMT()-TimeTradeServer(), see    |
//|     BrokerGMTOffsetHours()) - the report ran with InpGMTOffset=0    |
//|     and auto-detect on, so this was never exercised against a      |
//|     non-zero broker offset.                                        |
//|                                                                    |
//|  Before trusting this the way the project's other EAs are trusted, |
//|  it needs: a real MT5 Strategy Tester run over the same real       |
//|  2026.06.01-2026.08.31 window, compared trade-by-trade against the |
//|  uploaded report (win rate, RR=2.0 on every trade, session split), |
//|  the same rigor already applied to every validated construction    |
//|  in this project.                                                  |
//|                                                                    |
//|  Visual system (panel/watermark/chart theme/restart-safe position  |
//|  sync) matches this project's established standard - reused        |
//|  verbatim from Vanguard_EA.mq5 where the mechanism is generic       |
//|  (PRect/PFrame/PText/PRow/PSection/PTheme/PWatermark/PBackground,   |
//|  the reclaim-on-new-bar-only pattern, restart-safe SyncPositionState|
//|  / FindOwnPosition, the non-visual-tester cosmetic-draw skip).      |
//|  Panel content and chart drawings (session range box, fib levels,  |
//|  history) are new, specific to this construction.                  |
//|                                                                    |
//|  v1.01 ADDS InpOneTradeAfterLoss (default FALSE - opt-in, see       |
//|  below): found by analysing the REAL 8-month MSG3-only report       |
//|  (account 1301880049, 2026.01-2026.08, 86 real round-trip trades) - |
//|  two of the worst losses (2026.02.11 and 2026.03.25) were each a    |
//|  SAME-DAY re-entry into the exact same stopped-out zone (identical  |
//|  SL price both times: 5061.51 and 4540.22) - a revenge re-entry,    |
//|  not two independent bad trades. Blocking any further entry once    |
//|  one loss has happened that day: net 18,145.57->18,720.44 (+3.2%),  |
//|  max balance DD 3,774.60->2,440.98 (-35.3%), preserves 19/20 top     |
//|  trades (drops one +1,073.05 winner), holds up on a chronological    |
//|  70/30 IS/OOS split (+2.0% IS, +16.2% OOS - not a one-sided fluke).  |
//|  HONEST CAVEAT: only 15 of 86 trades are ever cut by this rule -     |
//|  a permutation test against random same-size cuts gives p=0.11-0.12,|
//|  NOT below the usual 0.05 bar. Real, mechanistically sensible (a     |
//|  same-zone double stop-out is a real, checkable event in the data), |
//|  but not statistically proven at this sample size - left OFF by      |
//|  default rather than presented as a validated filter.                |
//|                                                                    |
//|  v1.02 FIXES A REAL BUG found from the user's own real MT5 test on  |
//|  v1.01 (2026.01-09.21, GOLD#, account 1301959345): 406 trades vs     |
//|  the real EA's 169, 43.6% win rate vs the real 71%, account          |
//|  drawdown hit 100.2% (wiped out) by 2026.04.13. Root cause: a        |
//|  session's frozen range stayed re-armable for ~21h (until that       |
//|  session's window reopened), so ordinary chop around the range       |
//|  boundary could break out, retrace into the zone, enter, stop out,   |
//|  break out again, retrace again, enter again - repeatedly, all on    |
//|  the SAME static range. Confirmed directly: 59 of 68 trading days    |
//|  had more than one entry, averaging 4.9/day, one day hit 14. The     |
//|  real report never shows more than 2 trades on any day. Fixed with   |
//|  g_sesRangeTraded[] (see its own header note): once a trade is       |
//|  taken from a session's current range, that range is retired -       |
//|  no further entries from it until its window reopens and freezes     |
//|  a brand new one. NOT yet re-tested on a real MT5 run - needs that    |
//|  before the overtrading is confirmed fixed, not just reasoned about. |
//|                                                                    |
//|  v1.03 ADDS InpMaxSetupWatchHours=4.25 (real-data calibrated): v1.02 |
//|  still overtraded on the user's real MT5 run (360 trades vs the      |
//|  real EA's 169, still net-negative, 82.55% DD) because the one-      |
//|  trade-per-range fix only stopped WITHIN-range repeat-firing, not     |
//|  the deeper issue - the retracement zone was being watched for the   |
//|  FULL ~21h until the session reopened, while the real EA is far      |
//|  more time-limited. Checked directly against the real 8-month        |
//|  MSG3-only report (159 session-days with real M5 bar coverage):      |
//|  EVERY real entry happened within 4.08h of the session closing -     |
//|  none later. Cross-checking my own zone-touch trigger against real   |
//|  per-day outcomes: with no time limit, precision (of the days my     |
//|  trigger fires, how many the real EA also traded) was only 48%;      |
//|  with a 4.25h cutoff, precision rises to 76%, recall 67%. Real,      |
//|  measured against actual day-by-day data - not a fresh guess. Not    |
//|  a perfect match (24% of my fires still don't correspond to a real   |
//|  trade, and 33% of real trades aren't found by this zone logic at    |
//|  all - a different/additional trigger likely exists) - still needs   |
//|  a real MT5 re-test before trusting the overtrading is resolved.     |
//|                                                                    |
//|  v1.04 FIXES THE STOP DISTANCE. v1.03's real re-test got trade       |
//|  count right (181 vs real 169) and direction right (43/45 = 95.6%    |
//|  match on days both models fire), but was still net-negative (win    |
//|  rate 39% vs real 71%, PF 0.64) with average hold time of just 11    |
//|  minutes vs the real 63 minutes - trades were getting stopped out    |
//|  ~5x faster than real ones. Root cause: the "structural" stop (last  |
//|  InpStructLookback bars' extreme) measured a median risk of just     |
//|  $2.59 - a tight local-noise stop, nothing like the real EA's own    |
//|  risk. Checked the real 8-month report's actual risk-to-range ratio  |
//|  directly (82 trades with real M5 bar coverage): median 41.7%,       |
//|  mean 45.9%, tightly clustered (most between 33%-54%) - a real,      |
//|  measured relationship, not a guess. InpRangeRiskPct=41.7 replaces   |
//|  the old bar-lookback stop entirely: risk is now that % of the       |
//|  session's own finalized range, applied directly from the entry      |
//|  price. Still needs a real MT5 re-test - if win rate/PF come back    |
//|  in line with the real report, this is the fix; if not, the entry    |
//|  price itself (not just the stop) may also differ from real.         |
//|                                                                    |
//|  v1.04 REAL RE-TEST (MSG3-only, matching the real report's own       |
//|  config directly): net +2,199.84 (real: +18,145.57), PF 1.12 (real   |
//|  1.82), win rate 57.55% (real 71.0%) - genuinely profitable now,      |
//|  and trade SHAPE matches closely (avg win 345.66 vs real 335.18,      |
//|  avg loss -419.67 vs real -450.53, avg hold 1:02:29 vs real 1:03:01,  |
//|  max DD 37.81%/42.06% vs real 37.75%/42.43% - all close). Remaining   |
//|  gap is pure selectivity, not trade sizing. Tried zone-width sweeps   |
//|  (50-90% range) and multi-bar zone confirmation (1-4 bars) against    |
//|  the real day-by-day record - neither broke past ~75-76% precision,   |
//|  confirming the zone-touch trigger itself has a real ceiling, not a   |
//|  tuning gap.                                                          |
//|                                                                    |
//|  v1.05 FIXES THE SL REFERENCE POINT. User's own hypothesis (SL at     |
//|  the range boundary) tested directly: not exact (only 2/82 real       |
//|  trades have SL within 1% of L/H), but measuring SL's distance FROM   |
//|  the block edge (instead of from entry, v1.04's approach) is a        |
//|  visibly tighter fit - interquartile 26-38% of range vs 33-54% when   |
//|  measured from entry. Real: entry moves around inside the 61.8-78.6%  |
//|  OTE zone, but SL stays close to a FIXED level relative to L/H         |
//|  regardless - a structural stop, not one measured from the fill        |
//|  price. InpRangeRiskPct=30.8 (median) now applies from the range's     |
//|  own L/H rather than from entry. Not yet re-tested on a real MT5 run.  |
//|                                                                    |
//|  v1.05 REAL RE-TEST (MSG3-only): net +1,513.50 (v1.04 was            |
//|  +2,199.84), win rate 58.49% (v1.04: 57.55%) - the tighter stop        |
//|  barely moved win rate at all, just shrank average win/loss size       |
//|  proportionally (TP is always 2x risk) and lowered DD 37.81%->29.78%.  |
//|  CONCLUSION: the SL reference point was never the real bottleneck -     |
//|  same 106 trades both versions, so it only rescales risk, not which     |
//|  setups get selected.                                                   |
//|                                                                    |
//|  v1.06 ADDS A MINIMUM BREAKOUT EXTENSION FILTER (InpMinExtensionPct     |
//|  =15.0) - found by comparing the real per-day false-positive vs         |
//|  true-positive cases directly: on days my zone-touch trigger fires      |
//|  but the real EA does NOT trade, the breakout only extended a median    |
//|  of ~3.1 points beyond the range before retracing; on days that DO      |
//|  match a real trade, the median extension is ~9.9 points - a ~3x        |
//|  real difference, not noise. Swept the threshold against the real       |
//|  86-trade day-by-day record: 0% gives 76.3% precision/67.2% recall;     |
//|  15% gives 89.6% precision/64.2% recall (cuts false positives from      |
//|  14 to 5 while losing only 2 of 45 true positives) - the best real       |
//|  tradeoff found. A marginal few-point poke past the range is noise,      |
//|  not a genuine breakout with real directional conviction. Not yet        |
//|  re-tested on a real MT5 run.                                            |
//+------------------------------------------------------------------+
#property copyright "MSG_Trader_EA (reconstruction)"
#property version   "1.06"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- session indices, used throughout as array index 0..3
#define SES_MSG1 0
#define SES_MSG2 1
#define SES_MSG3 2
#define SES_MSG4 3

input group "==== Risk & execution ==="
input double InpLots              = 0.03;
input ulong  InpMagic             = 770025;
input int    InpSlippagePoints    = 20;
input bool   InpFixedFibSL        = false;    // false (as tested): structural swing stop, not a fixed fib %
input double InpFibSLPct          = 78.6;     // only used when InpFixedFibSL=true

input group "==== 3-stage partial TP ==="
input bool   InpScaleOut          = true;
input double InpTP1_RR            = 1.0;
input double InpTP2_RR            = 1.5;
input double InpTP3_RR            = 2.0;      // CONFIRMED: real broker TP order is always entry +/- 2.0x risk
input double InpTrailRR           = 1.0;      // move stop to breakeven once floating profit reaches this x risk

input group "==== Exit ==="
input int    InpTPMode            = 0;        // 0 = 3-stage scale-out (InpScaleOut/TP1-3), else = single TP at InpTP_RR
input double InpTP_RR             = 1.5;
input int    InpMaxHoldHours      = 48;

input group "==== Sessions (GMT) ==="
input bool   InpMsg1Enable        = true;
input int    InpMsg1StartHour     = 22;
input int    InpMsg1EndHour       = 0;
input bool   InpMsg2Enable        = false;
input int    InpMsg2StartHour     = 0;
input int    InpMsg2EndHour       = 8;
input bool   InpMsg3Enable        = true;
input int    InpMsg3StartHour     = 9;
input int    InpMsg3EndHour       = 12;
input bool   InpMsg4Enable        = false;
input int    InpMsg4StartHour     = 17;
input int    InpMsg4EndHour       = 21;

input group "==== Broker clock (GMT) ==="
input bool   InpAutoGMTOffset     = true;
input int    InpGMTOffset         = 0;        // manual hours, used only when InpAutoGMTOffset=false

input group "==== Chart drawings ==="
input bool   InpDrawRange         = true;
input bool   InpDrawFib           = true;
input bool   InpDrawLevels        = true;
input bool   InpDrawHistory       = true;
input int    InpZoneLineWidth     = 2;
input int    InpHistoryDays       = 30;

input group "==== Reconstruction-specific (not in the original report) ==="
input double InpZoneTopPct        = 61.8;     // OTE retracement zone - see header, INFERRED
input double InpZoneBotPct        = 78.6;
input double InpRangeRiskPct       = 30.8;    // v1.05 real-data fix - see header (median SL level from block edge)
input double InpMinExtensionPct    = 15.0;    // v1.06 real-data fix - see header (min breakout extension before a
                                               // zone retracement counts as a real setup, not noise)
input int    InpATRPeriod         = 14;
input double InpMaxSpreadPoints   = 60;
input bool   InpOneTradeAfterLoss = false;    // v1.01 real-data circuit breaker - see header, opt-in (p=0.11-0.12)
input double InpMaxSetupWatchHours = 4.25;    // v1.03 real-data fix - see header. Every real MSG3 entry in the
                                               // 8-month report happened within 4.08h of session close - none later.

input group "==== Notifications ==="
input bool   InpPushNotifications = true;

input group "==== Dashboard ==="
input bool    InpShowPanel   = true;
input int     InpPanelDrag   = 1;
input int     InpPanelX      = 12;
input int     InpPanelY      = 30;
input bool    InpPanelBottom = false;
input int     InpPanelW      = 260;
input color   InpPanelBg     = C'13,17,28';
input color   InpHeaderBg    = C'28,36,58';
input color   InpPanelEdge   = C'255,196,84';
input color   InpTitleCol    = C'255,196,84';
input color   InpSectionCol  = C'214,226,238';
input color   InpTextCol     = C'150,166,192';
input color   InpValCol      = C'236,242,252';
input color   InpOkCol       = C'0,230,118';
input color   InpNoCol       = C'255,61,90';
input color   InpShadowCol   = C'6,8,14';
input string  InpPanelFont   = "Consolas";
input int     InpPanelSize   = 8;
input string  InpBackgroundBMP = "";
input int     InpBgWidth       = 1290;
input int     InpBgHeight      = 720;

input group "==== Chart theme ==="
input bool    InpApplyTheme      = true;
input bool    InpHideTradeMarks  = true;
input color   InpColMsg1         = C'0,230,118';   // range/fib colour per session - neon green
input color   InpColMsg2         = C'0,255,255';   // neon aqua
input color   InpColMsg3         = C'255,196,84';  // gold
input color   InpColMsg4         = C'255,61,90';   // hot red
input color   InpColEntryLine    = C'150,166,192';
input color   InpColStopLine     = C'255,61,90';
input color   InpColTPLine       = C'0,230,118';
input color   InpChartBg   = clrBlack;
input color   InpBullCol   = C'0,150,255';
input color   InpBearCol   = clrWhite;
input string  InpWatermark  = "MSG";
input color   InpWaterCol   = C'46,38,24';
input bool    InpWaterBottom = true;
input int     InpWaterSize  = 42;
input string  InpWaterFont  = "Arial Black";

//--- restart-safe position state (Vanguard/Aurelius pattern)
ulong    g_ticket  = 0;
int      g_posDir  = 0;
datetime g_lastBarTime = 0;
bool     g_skipCosmeticDraws = false;

//--- manual Wilder ATR - used only for the structural-stop buffer and panel display
double   g_atrBuf[];

//--- per-session state (index by SES_MSG1..SES_MSG4)
bool     g_sesEnable[4];
int      g_sesStart[4];
int      g_sesEnd[4];
string   g_sesTag[4] = {"MSG_MSG1", "MSG_MSG2", "MSG_MSG3", "MSG_MSG4"};
color    g_sesCol[4];
bool     g_sesWasIn[4];
double   g_sesFormHigh[4], g_sesFormLow[4];         // range being formed right now
double   g_sesRangeHigh[4], g_sesRangeLow[4];       // last finalized range
bool     g_sesRangeValid[4];
datetime g_sesRangeStartTime[4], g_sesRangeEndTime[4];
int      g_sesBiasDir[4];                            // 0 none, +1/-1 breakout seen, awaiting retracement
double   g_sesExtHigh[4], g_sesExtLow[4];
datetime g_sesExtTime[4];
//--- v1.02 bugfix (see header): true once a trade has already been
//--- taken from the CURRENT frozen range - without this, a still-valid
//--- range stays re-armable for ~21h (until its session reopens), so
//--- ordinary chop around the range boundary re-triggers entry after
//--- entry all day (confirmed against a real MT5 run: 4.9 entries/day
//--- average, one day hit 14, vs the real EA's report which never
//--- shows more than 2/day).
bool     g_sesRangeTraded[4];

//--- current position's own scale-out state (only one position at a time)
double   g_posEntry = 0.0, g_posRisk = 0.0;
double   g_posTP1 = 0.0, g_posTP2 = 0.0, g_posTP3 = 0.0;
bool     g_posTP1Done = false, g_posTP2Done = false, g_posBEDone = false;
string   g_posTag = "";
datetime g_posOpenTime = 0;

//--- visuals object prefixes
string   g_pp = "MSGP_";   // panel
string   g_pw = "MSGW_";   // wallpaper + watermark
string   g_pz = "MSGZ_";   // session range boxes / fib zone lines (current + history)
string   g_pl = "MSGL_";   // entry/stop/TP level lines
int      g_panX = -1, g_panY = -1;
bool     g_bgOK = false;
int      g_bgTries = 0;
int      g_panelMinW = 0;
bool     g_panelReclaim = true;

void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim = true);
void PTheme();
void PBackground();
void PWatermark();
void UpdateLevelLines();
void UpdateRangeDrawings();

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
      if(g_ticket != 0) { g_posTP1Done = false; g_posTP2Done = false; g_posBEDone = false; }
      g_ticket = 0;
      g_posDir = 0;
     }
  }
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
//| Best-effort broker GMT offset (INFERRED - see header). Falls back  |
//| to the manual input when auto-detect is off. TimeGMT() reflects    |
//| the terminal's own OS timezone, not the broker's - a real,          |
//| disclosed limitation, same honesty standard as this project's       |
//| other "known gaps".                                                 |
//+------------------------------------------------------------------+
int BrokerGMTOffsetHours()
  {
   if(!InpAutoGMTOffset) return(InpGMTOffset);
   int diffSec = (int)(TimeTradeServer() - TimeGMT());
   return (int)MathRound(diffSec / 3600.0);
  }
//+------------------------------------------------------------------+
int HourGMT(datetime serverTime)
  {
   MqlDateTime dt;
   TimeToStruct(serverTime, dt);
   int h = dt.hour - BrokerGMTOffsetHours();
   h = ((h % 24) + 24) % 24;
   return(h);
  }
//+------------------------------------------------------------------+
bool HourInWindow(int hour, int startH, int endH)
  {
   if(startH == endH) return(false);
   if(startH < endH) return(hour >= startH && hour < endH);
   return(hour >= startH || hour < endH);   // wraps midnight, e.g. 22..0
  }
//+------------------------------------------------------------------+
void LoadSessionConfig()
  {
   g_sesEnable[SES_MSG1] = InpMsg1Enable; g_sesStart[SES_MSG1] = InpMsg1StartHour; g_sesEnd[SES_MSG1] = InpMsg1EndHour; g_sesCol[SES_MSG1] = InpColMsg1;
   g_sesEnable[SES_MSG2] = InpMsg2Enable; g_sesStart[SES_MSG2] = InpMsg2StartHour; g_sesEnd[SES_MSG2] = InpMsg2EndHour; g_sesCol[SES_MSG2] = InpColMsg2;
   g_sesEnable[SES_MSG3] = InpMsg3Enable; g_sesStart[SES_MSG3] = InpMsg3StartHour; g_sesEnd[SES_MSG3] = InpMsg3EndHour; g_sesCol[SES_MSG3] = InpColMsg3;
   g_sesEnable[SES_MSG4] = InpMsg4Enable; g_sesStart[SES_MSG4] = InpMsg4StartHour; g_sesEnd[SES_MSG4] = InpMsg4EndHour; g_sesCol[SES_MSG4] = InpColMsg4;
  }
//+------------------------------------------------------------------+
//| Called once per new bar with the bar that just closed (shift=1).   |
//| Grows/freezes each enabled session's range, and resets the         |
//| breakout/retracement watch the moment a session re-opens.          |
//+------------------------------------------------------------------+
void UpdateSessionRanges(datetime barTime, double barHigh, double barLow)
  {
   int hourGMT = HourGMT(barTime);
   for(int i = 0; i < 4; i++)
     {
      if(!g_sesEnable[i]) continue;
      bool inWin = HourInWindow(hourGMT, g_sesStart[i], g_sesEnd[i]);
      if(inWin)
        {
         if(!g_sesWasIn[i]) { g_sesFormHigh[i] = barHigh; g_sesFormLow[i] = barLow; g_sesRangeStartTime[i] = barTime; }
         else { g_sesFormHigh[i] = MathMax(g_sesFormHigh[i], barHigh); g_sesFormLow[i] = MathMin(g_sesFormLow[i], barLow); }
        }
      else if(g_sesWasIn[i])
        {
         //--- window just closed: freeze the range, and start a fresh
         //--- breakout/retracement watch against it
         g_sesRangeHigh[i]  = g_sesFormHigh[i];
         g_sesRangeLow[i]   = g_sesFormLow[i];
         g_sesRangeValid[i] = (g_sesRangeHigh[i] > g_sesRangeLow[i]);
         g_sesRangeEndTime[i] = barTime;
         g_sesBiasDir[i] = 0;
         g_sesExtHigh[i] = 0.0; g_sesExtLow[i] = 0.0;
         g_sesRangeTraded[i] = false;
        }
      g_sesWasIn[i] = inWin;
     }
  }
//+------------------------------------------------------------------+
//| INFERRED entry trigger (see header): after a session's range       |
//| breaks in one direction, wait for a retracement back into the      |
//| InpZoneTopPct/InpZoneBotPct fib zone of the (extension extreme ->  |
//| range's opposite side) swing, then trade CONTINUATION of the       |
//| original breakout direction. Returns 0/+1/-1 and, on a signal,     |
//| fills sesIdx/slPrice with the session that fired and its stop.     |
//+------------------------------------------------------------------+
int CheckSessionSetups(double close1, double high1, double low1, double atr, int &sesIdx, double &slPrice)
  {
   datetime barTime = iTime(_Symbol, PERIOD_M5, 1);
   for(int i = 0; i < 4; i++)
     {
      if(!g_sesEnable[i] || !g_sesRangeValid[i] || g_sesRangeTraded[i]) continue;
      //--- v1.03 real-data fix (see header): the watch window expires
      //--- InpMaxSetupWatchHours after the range froze - retire it
      //--- rather than leaving it re-armable for the rest of the day.
      if(barTime - g_sesRangeEndTime[i] > (datetime)(InpMaxSetupWatchHours * 3600.0))
        {
         g_sesBiasDir[i] = 0;
         continue;
        }
      double H = g_sesRangeHigh[i], L = g_sesRangeLow[i];
      double rng = H - L;
      if(rng <= 0.0) continue;

      if(g_sesBiasDir[i] == 0)
        {
         if(close1 > H) { g_sesBiasDir[i] = 1; g_sesExtHigh[i] = high1; g_sesExtTime[i] = iTime(_Symbol, PERIOD_M5, 1); }
         else if(close1 < L) { g_sesBiasDir[i] = -1; g_sesExtLow[i] = low1; g_sesExtTime[i] = iTime(_Symbol, PERIOD_M5, 1); }
         continue;
        }

      if(g_sesBiasDir[i] == 1)
        {
         g_sesExtHigh[i] = MathMax(g_sesExtHigh[i], high1);
         if(close1 < L) { g_sesBiasDir[i] = 0; continue; }   // fully invalidated, must re-break to try again
         double swing = g_sesExtHigh[i] - L;
         if(swing <= 0.0) continue;
         double zoneTop = g_sesExtHigh[i] - (InpZoneTopPct / 100.0) * swing;
         double zoneBot = g_sesExtHigh[i] - (InpZoneBotPct / 100.0) * swing;
         //--- v1.06 real-data fix (see header): require the breakout to
         //--- have travelled at least InpMinExtensionPct% of the range
         //--- beyond H before a retracement into the zone counts - a
         //--- marginal few-point poke past the range is noise, not a
         //--- real breakout.
         double extPct = (g_sesExtHigh[i] - H) / rng * 100.0;
         if(close1 <= zoneTop && close1 >= zoneBot && extPct >= InpMinExtensionPct)
           {
            sesIdx = i;
            slPrice = StructuralOrFibSL(true, i, close1, rng, atr);
            return(1);
           }
        }
      else //-1
        {
         g_sesExtLow[i] = (g_sesExtLow[i] == 0.0) ? low1 : MathMin(g_sesExtLow[i], low1);
         if(close1 > H) { g_sesBiasDir[i] = 0; continue; }
         double swing = H - g_sesExtLow[i];
         if(swing <= 0.0) continue;
         double zoneBot = g_sesExtLow[i] + (InpZoneTopPct / 100.0) * swing;
         double zoneTop = g_sesExtLow[i] + (InpZoneBotPct / 100.0) * swing;
         double extPct = (L - g_sesExtLow[i]) / rng * 100.0;
         if(close1 >= zoneBot && close1 <= zoneTop && extPct >= InpMinExtensionPct)
           {
            sesIdx = i;
            slPrice = StructuralOrFibSL(false, i, close1, rng, atr);
            return(-1);
           }
        }
     }
   return(0);
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| v1.05 real-data fix (see header): SL is a fixed InpRangeRiskPct%   |
//| level measured from the session range's OWN boundary (L for a buy, |
//| H for a sell) - NOT a distance measured back from the entry price   |
//| (v1.04's approach). Checked directly against the real 8-month       |
//| report: measuring SL-to-entry gave a real but noisier fit (33-54%   |
//| interquartile spread, since entry itself moves around inside the    |
//| 61.8-78.6% OTE zone); measuring SL-to-block-edge instead is a        |
//| visibly tighter fit (26-38% interquartile spread, same 82 real       |
//| trades) - real evidence the stop is a fixed structural level of the |
//| range, independent of exactly where inside the zone the entry       |
//| filled. Median real value: 30.8%.                                   |
//+------------------------------------------------------------------+
double StructuralOrFibSL(bool isBuy, int sesIdx, double entryPx, double rng, double atr)
  {
   double H = g_sesRangeHigh[sesIdx], L = g_sesRangeLow[sesIdx];
   if(InpFixedFibSL)
     {
      double swing = isBuy ? (g_sesExtHigh[sesIdx] - L) : (H - g_sesExtLow[sesIdx]);
      return isBuy ? g_sesExtHigh[sesIdx] - (InpFibSLPct / 100.0) * swing
                   : g_sesExtLow[sesIdx]  + (InpFibSLPct / 100.0) * swing;
     }
   double off = (InpRangeRiskPct / 100.0) * rng;
   double sl = isBuy ? L + off : H - off;
   //--- safety clamp: with a minimal breakout extension AND a deep-zone
   //--- entry (close to 78.6%), a fixed offset from L/H can land on the
   //--- wrong side of entryPx - fall back to a small fixed fraction of
   //--- the range so risk is always positive and on the correct side.
   double minRisk = 0.05 * rng;
   if(isBuy && sl >= entryPx - minRisk) sl = entryPx - minRisk;
   if(!isBuy && sl <= entryPx + minRisk) sl = entryPx + minRisk;
   return sl;
  }
//+------------------------------------------------------------------+
double LotStep(double lots)
  {
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0.0) lots = MathRound(lots / step) * step;
   if(lots < mn) lots = 0.0;
   return(lots);
  }
//+------------------------------------------------------------------+
void NotifyPush(const string text)
  {
   if(!InpPushNotifications) return;
   SendNotification(StringSubstr(text, 0, 255));
  }
//+------------------------------------------------------------------+
//| v1.01 circuit breaker (see header) - true once THIS EA (own symbol |
//| + magic) has closed at least one losing deal since today's start,  |
//| server-time calendar day.                                          |
//+------------------------------------------------------------------+
bool LossAlreadyToday()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);
   if(!HistorySelect(dayStart, TimeCurrent())) return(false);
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagic) continue;
      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY) continue;
      if(HistoryDealGetDouble(ticket, DEAL_PROFIT) < 0.0) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
void CheckForEntry()
  {
   SyncPositionState();
   if(g_ticket != 0) return;
   if(InpOneTradeAfterLoss && LossAlreadyToday()) return;

   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadPts > InpMaxSpreadPoints) return;

   double atr;
   if(!GetATR(atr)) atr = 0.0;

   double close1 = iClose(_Symbol, PERIOD_M5, 1);
   double high1  = iHigh(_Symbol, PERIOD_M5, 1);
   double low1   = iLow(_Symbol, PERIOD_M5, 1);

   int sesIdx = -1; double slPrice = 0.0;
   int dir = CheckSessionSetups(close1, high1, low1, atr, sesIdx, slPrice);
   if(dir == 0) return;

   bool isBuy = (dir > 0);
   double px = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double risk = isBuy ? (px - slPrice) : (slPrice - px);
   if(risk <= 0.0) return;

   double tp3 = isBuy ? px + InpTP3_RR * risk : px - InpTP3_RR * risk;
   double tpFinal = (InpTPMode == 0) ? tp3 : (isBuy ? px + InpTP_RR * risk : px - InpTP_RR * risk);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   bool ok = isBuy ? trade.Buy(InpLots, _Symbol, px, slPrice, tpFinal, g_sesTag[sesIdx])
                    : trade.Sell(InpLots, _Symbol, px, slPrice, tpFinal, g_sesTag[sesIdx]);
   if(ok)
     {
      SyncPositionState();
      g_posEntry = px; g_posRisk = risk; g_posTag = g_sesTag[sesIdx];
      g_posOpenTime = TimeCurrent();
      g_posTP1 = isBuy ? px + InpTP1_RR * risk : px - InpTP1_RR * risk;
      g_posTP2 = isBuy ? px + InpTP2_RR * risk : px - InpTP2_RR * risk;
      g_posTP3 = tp3;
      g_posTP1Done = false; g_posTP2Done = false; g_posBEDone = false;
      //--- v1.02: this range is now spent - no further entries from it
      //--- until its session window reopens and freezes a brand new one
      //--- (see g_sesRangeTraded's own header note)
      g_sesBiasDir[sesIdx] = 0;
      g_sesRangeTraded[sesIdx] = true;
     }
   else
      PrintFormat("MSG EA: entry FAILED, retcode %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
void ClosePartial(double vol, const string reason)
  {
   vol = LotStep(vol);
   double curVol = PositionGetDouble(POSITION_VOLUME);
   double minVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(vol <= 0.0 || curVol - vol < minVol - 1e-8)
      return;   // remainder would be sub-minimum - skip, let it ride to the next stage
   if(!trade.PositionClosePartial(g_ticket, vol))
      PrintFormat("MSG EA: partial close (%s) FAILED for ticket %I64u, retcode %d",
                  reason, g_ticket, trade.ResultRetcode());
  }
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   SyncPositionState();
   if(g_ticket == 0) return;
   if(!PositionSelectByTicket(g_ticket)) return;

   //--- max hold (CONFIRMED input, InpMaxHoldHours=48)
   int barsHeld = (int)((TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME)));
   if(InpMaxHoldHours > 0 && barsHeld >= InpMaxHoldHours * 3600)
     {
      trade.PositionClose(g_ticket);
      return;
     }

   if(!InpScaleOut || InpTPMode != 0 || g_posRisk <= 0.0) return;

   double price = (g_posDir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double vol = PositionGetDouble(POSITION_VOLUME);

   bool hitTP1 = (g_posDir > 0) ? (price >= g_posTP1) : (price <= g_posTP1);
   bool hitTP2 = (g_posDir > 0) ? (price >= g_posTP2) : (price <= g_posTP2);

   if(!g_posTP1Done && hitTP1)
     {
      ClosePartial(vol / 3.0, "TP1");
      g_posTP1Done = true;
     }
   if(g_posTP1Done && !g_posTP2Done && hitTP2)
     {
      if(PositionSelectByTicket(g_ticket))
         ClosePartial(PositionGetDouble(POSITION_VOLUME) / 2.0, "TP2");
      g_posTP2Done = true;
     }

   //--- trail to breakeven once InpTrailRR x risk of profit is reached
   //--- (INFERRED reading of InpTrailRR - see header)
   if(!g_posBEDone)
     {
      double profitR = (g_posDir > 0) ? (price - g_posEntry) / g_posRisk : (g_posEntry - price) / g_posRisk;
      if(profitR >= InpTrailRR)
        {
         if(PositionSelectByTicket(g_ticket))
            trade.PositionModify(g_ticket, g_posEntry, PositionGetDouble(POSITION_TP));
         g_posBEDone = true;
        }
     }
  }
//+------------------------------------------------------------------+
//| VISUALS - panel primitives reused verbatim from Vanguard_EA.mq5    |
//| (this project's established, bug-fixed implementation).             |
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
   PRect(id + "ft", x,             y,             w,     thick, edge, edge, 0);
   PRect(id + "fb", x,             y + h - thick, w,     thick, edge, edge, 0);
   PRect(id + "fl", x,             y,             thick, h,     edge, edge, 0);
   PRect(id + "fr", x + w - thick, y,             thick, h,     edge, edge, 0);
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
//| Entry/stop/TP1-3 of the OPEN position, as horizontal lines.        |
//+------------------------------------------------------------------+
void UpdateLevelLines()
  {
   if(InpDrawLevels && g_ticket != 0 && PositionSelectByTicket(g_ticket))
     {
      DrawLevelLine("entry", PositionGetDouble(POSITION_PRICE_OPEN), InpColEntryLine, STYLE_SOLID, 1);
      double sl = PositionGetDouble(POSITION_SL);
      if(sl > 0.0) DrawLevelLine("sl", sl, InpColStopLine, STYLE_SOLID, 1); else DeleteLevelLine("sl");
      DrawLevelLine("tp1", g_posTP1Done ? 0.0 : g_posTP1, InpColTPLine, STYLE_DOT, 1);
      DrawLevelLine("tp2", g_posTP2Done ? 0.0 : g_posTP2, InpColTPLine, STYLE_DOT, 1);
      double tp = PositionGetDouble(POSITION_TP);
      if(tp > 0.0) DrawLevelLine("tp3", tp, InpColTPLine, STYLE_SOLID, 1); else DeleteLevelLine("tp3");
     }
   else
     {
      DeleteLevelLine("entry"); DeleteLevelLine("sl");
      DeleteLevelLine("tp1"); DeleteLevelLine("tp2"); DeleteLevelLine("tp3");
     }
  }
//+------------------------------------------------------------------+
//| Session range box + fib zone lines - current range per session,    |
//| plus (InpDrawHistory) a fading trail of past InpHistoryDays worth. |
//+------------------------------------------------------------------+
void DrawSessionBox(const string tag, datetime t1, datetime t2, double hi, double lo, color col, bool emphasis)
  {
   if(!InpDrawRange) { return; }
   string nm = g_pz + tag;
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t1);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, hi);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t2);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, lo);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, emphasis ? InpZoneLineWidth : 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, nm, OBJPROP_FILL, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
void DrawFibLine(const string tag, datetime t1, datetime t2, double price, color col, bool emphasis)
  {
   string nm = g_pz + tag;
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t1);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t2);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, emphasis ? InpZoneLineWidth : 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, emphasis ? STYLE_SOLID : STYLE_DOT);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
void UpdateRangeDrawings()
  {
   datetime now = TimeCurrent();
   datetime histCutoff = now - (datetime)InpHistoryDays * 86400;

   for(int i = 0; i < 4; i++)
     {
      if(!g_sesEnable[i] || !g_sesRangeValid[i]) continue;
      string base = "cur" + IntegerToString(i) + "_";
      datetime t1 = g_sesRangeStartTime[i], t2 = now + PeriodSeconds(PERIOD_M5) * 20;
      double H = g_sesRangeHigh[i], L = g_sesRangeLow[i], rng = H - L;

      DrawSessionBox(base + "box", t1, g_sesRangeEndTime[i], H, L, g_sesCol[i], true);

      if(InpDrawFib && rng > 0.0)
        {
         double lvl0   = L, lvl236 = L + 0.236 * rng, lvl382 = L + 0.382 * rng, lvl50 = L + 0.5 * rng;
         double lvl618 = L + (100 - InpZoneTopPct) / 100.0 * rng, lvl786 = L + (100 - InpZoneBotPct) / 100.0 * rng, lvl100 = H;
         DrawFibLine(base + "f0",   g_sesRangeEndTime[i], t2, lvl0,   g_sesCol[i], false);
         DrawFibLine(base + "f236", g_sesRangeEndTime[i], t2, lvl236, g_sesCol[i], false);
         DrawFibLine(base + "f382", g_sesRangeEndTime[i], t2, lvl382, g_sesCol[i], false);
         DrawFibLine(base + "f50",  g_sesRangeEndTime[i], t2, lvl50,  g_sesCol[i], false);
         DrawFibLine(base + "f618", g_sesRangeEndTime[i], t2, lvl618, g_sesCol[i], true);   // OTE zone edges
         DrawFibLine(base + "f786", g_sesRangeEndTime[i], t2, lvl786, g_sesCol[i], true);
         DrawFibLine(base + "f100", g_sesRangeEndTime[i], t2, lvl100, g_sesCol[i], false);
        }
      else
        {
         string f[] = {"f0","f236","f382","f50","f618","f786","f100"};
         for(int k = 0; k < ArraySize(f); k++) DeleteZoneObj(base + f[k]);
        }
     }

   if(!InpDrawHistory)
     {
      PurgeZonePrefix("h");
      return;
     }
   //--- purge history objects older than the cutoff (kept simple - full
   //--- multi-day history backfill on attach is out of scope, same
   //--- disclosed live-only limitation as Vanguard's VWAP line)
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, g_pz + "h") != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < histCutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
void DeleteZoneObj(const string tag)
  {
   string nm = g_pz + tag;
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
  }
//+------------------------------------------------------------------+
void PurgeZonePrefix(const string sub)
  {
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, g_pz + sub) == 0) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
//| Archives the range that just finalized into the history trail      |
//| (InpDrawHistory) - called right when UpdateSessionRanges freezes   |
//| a session's window, so it isn't lost once the "cur" box moves on.  |
//+------------------------------------------------------------------+
void ArchiveSessionRange(int i)
  {
   if(!InpDrawHistory) return;
   string tag = "h" + IntegerToString(i) + "_" + IntegerToString((long)g_sesRangeEndTime[i]);
   DrawSessionBox(tag, g_sesRangeStartTime[i], g_sesRangeEndTime[i], g_sesRangeHigh[i], g_sesRangeLow[i], g_sesCol[i], false);
  }
//+------------------------------------------------------------------+
double MyRealizedPLToday()
  {
   double sum = 0.0;
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);
   if(!HistorySelect(dayStart, TimeCurrent())) return(0.0);
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
void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim)
  {
   PBackground();
   PWatermark();
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }
   g_panelReclaim = reclaim;

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;
   int rh = InpPanelSize + 11;
   int hdr = rh + 14;
   //--- counted directly against the ty+= sequence below (project
   //--- convention - see Vanguard/Aurelius header notes on this exact
   //--- discipline). In-position: a0(1) + s1(1)+g1-g4(4) + s2(1)+h1-h5(5)
   //--- + s3(1)+p1-p4(4) + s4(1)+q1-q4(4) = 22 rh-rows, 8 gap-boundaries.
   //--- Flat: p-block loses one rh-row (p4 becomes gap-only) = 21 rh-rows,
   //--- 8 gap-boundaries.
   const int ROWS = (haveLong || haveShort) ? 22 : 21, GAPS = 8;
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
   PText("t2", x + w - 12, ty + 3, "MSG TRADER", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   bool algo = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED);
   PRow("a0", x, ty, w, "algo trading", algo ? "ON" : "OFF", algo ? 1 : 0);
   ty += rh + 6;

   //--- sessions ------------------------------------------------------
   int hourGMT = HourGMT(TimeCurrent());
   PSection("s1", x, ty, w, rh, "SESSIONS (GMT)"); ty += rh + 6;
   string names[4] = {"MSG1 22-00", "MSG2 00-08", "MSG3 09-12", "MSG4 17-21"};
   for(int i = 0; i < 4; i++)
     {
      bool inWin = g_sesEnable[i] && HourInWindow(hourGMT, g_sesStart[i], g_sesEnd[i]);
      string val = !g_sesEnable[i] ? "off" : (inWin ? "forming" :
                   (!g_sesRangeValid[i] ? "-" : (g_sesRangeTraded[i] ? "traded" : "watching")));
      PRow("g" + IntegerToString(i + 1), x, ty, w, names[i], val, !g_sesEnable[i] ? -1 : (inWin ? 1 : (g_sesBiasDir[i] != 0 ? 1 : -1)));
      ty += rh;
     }
   ty += 6;

   //--- setup -----------------------------------------------------
   PSection("s2", x, ty, w, rh, "SETUP"); ty += rh + 6;
   int watching = -1; string watchTxt = "none";
   for(int i = 0; i < 4; i++)
      if(g_sesEnable[i] && g_sesBiasDir[i] != 0) { watching = i; watchTxt = g_sesTag[i] + (g_sesBiasDir[i] > 0 ? " bull" : " bear"); break; }
   PRow("h1", x, ty, w, "awaiting retracement", watchTxt, watching >= 0 ? 1 : -1); ty += rh;
   PRow("h2", x, ty, w, "zone", DoubleToString(InpZoneTopPct, 1) + "-" + DoubleToString(InpZoneBotPct, 1) + "%", -1); ty += rh;
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   PRow("h3", x, ty, w, "spread", (string)spr, spr <= InpMaxSpreadPoints ? 1 : 0); ty += rh;
   double atrShow; bool haveATR = GetATR(atrShow);
   PRow("h4", x, ty, w, "ATR(14)", haveATR ? DoubleToString(atrShow, 2) : "-", -1); ty += rh;
   bool lossToday = InpOneTradeAfterLoss && LossAlreadyToday();
   PRow("h5", x, ty, w, "one-trade breaker",
        !InpOneTradeAfterLoss ? "off" : (lossToday ? "BLOCKING" : "armed"),
        !InpOneTradeAfterLoss ? -1 : (lossToday ? 0 : 1)); ty += rh + 6;

   //--- position --------------------------------------------------
   PSection("s3", x, ty, w, rh, "POSITION"); ty += rh + 6;
   if(haveLong || haveShort)
     {
      double opx = 0.0, vol = 0.0, prof = 0.0;
      if(g_ticket != 0 && PositionSelectByTicket(g_ticket))
        {
         opx = PositionGetDouble(POSITION_PRICE_OPEN);
         vol = PositionGetDouble(POSITION_VOLUME);
         prof = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
        }
      PRow("p1", x, ty, w, (haveLong ? "LONG " : "SHORT ") + g_posTag, DoubleToString(opx, _Digits), 1); ty += rh;
      PRow("p2", x, ty, w, "volume", DoubleToString(vol, 2), -1); ty += rh;
      PRow("p3", x, ty, w, "floating P/L", StringFormat("%+.2f", prof), prof >= 0 ? 1 : 0); ty += rh;
      string stage = g_posTP2Done ? "TP2 done" : g_posTP1Done ? "TP1 done" : "open";
      PRow("p4", x, ty, w, "scale-out", stage, -1); ty += rh + 6;
     }
   else
     {
      PRow("p1", x, ty, w, "state", "FLAT", -1); ty += rh;
      PRow("p2", x, ty, w, "next lot size", DoubleToString(InpLots, 2), -1); ty += rh;
      PRow("p3", x, ty, w, "", "", -1); ty += rh;
      PRow("p4", x, ty, w, "", "", -1); ty += 6;
     }

   //--- account ------------------------------------------------------
   PSection("s4", x, ty, w, rh, "ACCOUNT"); ty += rh + 6;
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
void OnTimer()
  {
   if(g_skipCosmeticDraws) return;
   bool hl, hs;
   CurrentPositions(hl, hs);
   UpdateLevelLines();
   DrawPanel(hl, hs, false);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
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
int OnInit()
  {
   if(_Period != PERIOD_M5)
     {
      PrintFormat("MSG EA: this system is calibrated for M5 only - attach it to an M5 chart "
                  "(currently on period %d)", _Period);
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   LoadSessionConfig();
   ArrayInitialize(g_sesWasIn, false);
   ArrayInitialize(g_sesRangeValid, false);
   ArrayInitialize(g_sesBiasDir, 0);
   ArrayInitialize(g_sesRangeTraded, false);

   SyncPositionState();
   g_lastBarTime = 0;

   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);
   if(!g_skipCosmeticDraws)
     {
      PTheme();
      PBackground();
      UpdateLevelLines();
      bool hl0, hs0;
      CurrentPositions(hl0, hs0);
      if(InpShowPanel) DrawPanel(hl0, hs0);
      EventSetTimer(1);
     }

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pw);
   ObjectsDeleteAll(0, g_pz);
   ObjectsDeleteAll(0, g_pl);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   if(!IsNewBar()) return;

   datetime barTime = iTime(_Symbol, PERIOD_M5, 1);
   double barHigh = iHigh(_Symbol, PERIOD_M5, 1);
   double barLow  = iLow(_Symbol, PERIOD_M5, 1);

   //--- snapshot which sessions are about to freeze, so their range can
   //--- be archived into the history trail right after
   bool willFreeze[4];
   for(int i = 0; i < 4; i++)
      willFreeze[i] = g_sesEnable[i] && g_sesWasIn[i] && !HourInWindow(HourGMT(barTime), g_sesStart[i], g_sesEnd[i]);

   UpdateSessionRanges(barTime, barHigh, barLow);

   for(int i = 0; i < 4; i++)
      if(willFreeze[i]) ArchiveSessionRange(i);

   if(g_ticket != 0)
      ManageOpenPosition();
   if(g_ticket == 0)
      CheckForEntry();

   if(!g_skipCosmeticDraws)
     {
      UpdateRangeDrawings();
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
      NotifyPush(StringFormat("MSG %s OPEN %.2f lots @ %.2f", side, vol, price));
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
      NotifyPush(StringFormat("MSG %s CLOSE %.2f lots @ %.2f P/L=%.2f", side, vol, price, profit));
     }
  }
//+------------------------------------------------------------------+
