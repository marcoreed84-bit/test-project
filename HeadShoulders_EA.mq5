//+------------------------------------------------------------------+
//|                                            HeadShoulders_EA.mq5  |
//|                                                                  |
//|  WHAT THIS IS: an Expert Advisor (real order execution, runs in   |
//|  the Strategy Tester) that trades the Head & Shoulders / Inverse  |
//|  H&S measured-move target rule, from the Fidelity/Kirkpatrick     |
//|  "Identifying Chart Patterns" deck: "Target is the distance from  |
//|  the head to the neckline projected from the neckline."           |
//|                                                                    |
//|  REAL PYTHON VALIDATION (2026-09-25, research/trendbreaker/, same  |
//|  construction ported here verbatim - swing/BOS detection, 5-swing  |
//|  shape match, neckline break confirmation, measured-move target):  |
//|    M15: 75.2% hit rate (75.5% IS / 74.7% OOS), n=868 confirmed      |
//|    H4:  69.1% hit rate (69.2% IS / 68.8% OOS), n=265 confirmed       |
//|    D1:  74.6% hit rate (73.5% IS / 77.3% OOS), n=71 confirmed         |
//|  All three chronological 70/30 walk-forward splits are stable - the   |
//|  strongest, most cross-validated real finding of this project's        |
//|  research this session. See head_shoulders_target_test.py and            |
//|  m15_head_shoulders_target_test.py for the full methodology and            |
//|  real numbers, including the half-target control used to confirm the       |
//|  SPECIFIC measured distance is doing real work, not just "any target        |
//|  eventually gets hit".                                                       |
//|                                                                    |
//|  WHAT IS NOT VALIDATED - STOP-LOSS PLACEMENT. The source material only |
//|  discusses generic protective-stop TYPES (percent/points/money, or a    |
//|  trend line/support/resistance level with a filter) - it does not give   |
//|  an H&S-specific stop rule, and no research this session tested one.      |
//|  InpStopBufferATR below is this file's own disclosed, standard, NOT-       |
//|  validated choice: beyond the right shoulder's own extreme, buffered        |
//|  by InpStopBufferATR x ATR - the conventional technical placement (a         |
//|  break back past the right shoulder invalidates the pattern's own            |
//|  shape), not a researched number. Change it freely; there is no real           |
//|  evidence behind this specific value the way there is behind the target.        |
//|                                                                    |
//|  ALSO NOT VALIDATED - real MT5 execution. Everything above is a real,    |
//|  strictly-forward, no-lookahead PYTHON replay of real GOLD OHLCV bars -    |
//|  this is its first real MT5 Strategy Tester run. Real spread, slippage,     |
//|  and this platform's own fill behaviour have not yet been measured           |
//|  against it. Run it in the Tester before trusting it further - that is        |
//|  the entire point of building this as an EA rather than a visual-only          |
//|  indicator.                                                                      |
//|                                                                    |
//|  ENTRY: on the bar that confirms a neckline break (InpBreakConfirm    |
//|  closes consecutively beyond the neckline, same convention as the      |
//|  research), enter a market order in the breakout's direction (top =     |
//|  sell, inverse = buy) - ONLY while flat, one position at a time (the      |
//|  same single-slot convention as every other EA in this portfolio).         |
//|  TP is the real measured-move target (broker-side limit); SL is the         |
//|  disclosed right-shoulder-based stop above (broker-side stop). No           |
//|  further management - the position runs to TP or SL, matching exactly       |
//|  what the Python research itself measured (it tested "does price ever         |
//|  reach the target", not a managed exit).                                        |
//|                                                                    |
//|  VISUALS: shoulders/head/troughs (small markers + labels), the neckline   |
//|  (a real trend line, extended forward), the measured-move target level     |
//|  (a labelled horizontal line at the real target price), for BOTH the        |
//|  live/current pattern set AND a bounded historical trail (InpDrawHistory/     |
//|  InpHistoryDays, same idiom as MSG_Trader_EA.mq5's own session-box trail),      |
//|  plus entry/exit arrows on real fills (same OBJ_ARROW/caption idiom as           |
//|  every other EA in this portfolio).                                               |
//|                                                                    |
//|  v1.01 PERFORMANCE FIX (2026-09-25, real backtest report - a multi-year M15  |
//|  Tester run was still taking ~1h even on OHLC modeling). Root cause: Recompute() |
//|  re-scanned the ENTIRE InpLookbackBars swing history from scratch on EVERY new    |
//|  bar (full pivot scan + an ArrayResize per swing found), almost all of it          |
//|  identical to the previous bar's result. Two real fixes, not just "wait longer":     |
//|  InpLookbackBars default cut 3000 -> 800 (real patterns resolve in ~80 bars on         |
//|  average - 800 is generous headroom, not a requirement), and the full rescan is         |
//|  now throttled to every InpRecomputeEveryBars(5) bars rather than every single one -      |
//|  AdvancePending()'s own breakout confirmation (the part that actually has to be exact)      |
//|  still runs every bar regardless, so this only delays noticing a BRAND NEW pattern           |
//|  shape by up to a few bars, immaterial given a pattern takes many dozens of bars to            |
//|  even form.                                                                                      |
//|                                                                                                    |
//|  v1.02: InpUseRSIFilter added (default OFF - see its own input comment for the real         |
//|  Python numbers). This is ONE of several real, Python-validated candidates found            |
//|  2026-09-25 on real GOLD data (this project switched off GOLD# the same day - see            |
//|  research/ratchet/bars.py's header) with properly single-position-sequenced testing            |
//|  (the same discipline this project adopted after a real MT5 test caught a flawed                |
//|  post-hoc-swap methodology elsewhere in the portfolio - see Aurelius_EA.mq5 v1.52).               |
//|                                                                    |
//|  v1.03: InpUsePullbackEntry and InpUseRunner added (both default OFF - see their own      |
//|  input comments). These were the other two "not yet shipped" candidates from v1.02's        |
//|  header; shipping them now so they can actually be run in the Tester, same as v1.02's         |
//|  RSI filter. The remaining two candidates from that list - InpStopBufferATR 0.3->1.0 and        |
//|  InpBreakTolATR 0.10->0.35 - are already plain numeric inputs (not booleans), so there is         |
//|  nothing to toggle; change them directly in the Tester's Inputs tab if you want to try them.        |
//|  Stacked together (pullback 0.75xATR/30bar + break_tol=0.35 + runner 0.5xATR, real GOLD,             |
//|  research/trendbreaker/hs_next_round_test.py "stacked" mode): n=456 net +$4255 (vs this                |
//|  file's real, unimproved 0.3xATR-stop MT5 report: 599 trades, net 13999.4 ZAR, PF 1.161,                 |
//|  NOTE the Python figure is USD price-difference, NOT directly comparable to that ZAR                      |
//|  number without converting - see research/aurelius/giveback_real_mt5_rejection.py's                        |
//|  sibling finding on why that comparison needs care), PF 2.377, win 52.0%, max closed-DD                     |
//|  only 5.4% of net, worst losing streak 7. None of this is real-MT5-confirmed yet - that's               |
//|  the whole point of shipping it as off-by-default toggles rather than changing defaults.               |
//|                                                                    |
//|  v1.04: real bugs in v1.03's own MQL5 port, caught by an Opus review requested BEFORE this   |
//|  file's first real MT5 run (not by a live account result this time - the user asked for the    |
//|  review specifically so these wouldn't have to be found that way). All bugs were in the NEW       |
//|  v1.03 code paths only, not in the Python research those paths port - fixing them makes real        |
//|  MT5 behaviour track the Python-tested strategy MORE faithfully, it does not change what was          |
//|  actually validated. Fixed: (1) InpPullbackWindowBars was counting elapsed wall-clock seconds           |
//|  / period length instead of real bars, silently shrinking the retest window across a weekend             |
//|  gap - now uses iBarShift(); (2) a pattern blocked by an already-open position could still fire            |
//|  on a LATER bar once flat again under InpUsePullbackEntry (its multi-bar trigger window) - a real           |
//|  divergence from this project's own single-position-sequenced methodology (the giveback-exit               |
//|  lesson) - now marked traded=true (permanently skipped) the moment it's blocked, matching                    |
//|  Python's last_exit_bar gating; (3) RSIFilterOk() always read shift=1, which is wrong once                    |
//|  InpUsePullbackEntry can trigger entry several bars after the actual confirmation bar the RSI                  |
//|  filter was validated against - now reads the confirmation bar's own shift via iBarShift();                     |
//|  (4) CheckForEntry() could see a stale g_ticket left over from before this bar's SyncPosition()                   |
//|  call, silently losing an immediate-entry-mode trigger - SyncPosition() now runs first thing in                    |
//|  OnTick(); (5) InpUseRunner's trailing stop could be rejected forever once the trail distance                        |
//|  became tighter than the broker's own SYMBOL_TRADE_STOPS_LEVEL/FREEZE_LEVEL (the gap stays                             |
//|  roughly constant as price and the trail both advance), silently leaving a runner trade                                 |
//|  protected by nothing but its ORIGINAL stop for the rest of the trade - now clamped to the                                |
//|  broker's minimum distance instead; (6) InpUseRunner state (target/ATR/peak/stop) lived only in                            |
//|  RAM, so a terminal restart/recompile mid-trade would silently disarm it on a position with NO                               |
//|  broker-side TP (tp=0.0 by design) - now persisted to terminal GlobalVariables and restored in                                |
//|  OnInit(); (7) ManageRunner() could evaluate the ENTRY bar's own high/low on the same tick as                                  |
//|  arming, before the trade had experienced any bar of its own - now skips exactly one call right                                |
//|  after ArmRunner(). One disclosed, NOT fixed, real precision gap: InpUsePullbackEntry fills at                                  |
//|  market once a retest is detected on a CLOSED bar, not at the exact neckline price the instant it's                             |
//|  touched (which is what the Python research assumed, frictionlessly) - a real pending-order-based                                |
//|  implementation would close this gap but wasn't built here; expect real fills to run somewhat worse                              |
//|  than the Python retest price on this leg specifically, on top of the ordinary spread/slippage gap                               |
//|  every other entry in this file already has.                                                                                       |
//|                                                                    |
//|  v1.05 PERFORMANCE FIX: this file was missing the g_skipCosmeticDraws idiom every OTHER EA   |
//|  in this portfolio already has (Fulcrum_EA.mq5, Aurelius_EA.mq5, etc. - see SESSION_NOTES.md    |
//|  on the original repainting/performance pass those got). v1.01 only fixed the SWING/PATTERN         |
//|  scan cost (InpLookbackBars, InpRecomputeEveryBars); it never touched drawing, which was the           |
//|  actual dominant cost this whole time: RefreshDrawings() re-touched every confirmed pattern's            |
//|  several chart objects (markers, labels, neckline, target/stop lines) on EVERY new bar, and                |
//|  DrawPanel() ~20 more object updates every simulated second, for the ENTIRE backtest, even                   |
//|  though a non-visual Strategy Tester run never shows any of it. g_skipCosmeticDraws is computed                |
//|  once in OnInit() (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) and now gates                |
//|  RefreshDrawings(), DrawEntryArrow(), and both OnTick()/OnTimer()'s panel blocks - a non-visual                  |
//|  run draws none of it. No signal, entry, exit, sizing, or risk-management logic touched.                          |
//+------------------------------------------------------------------+
#property copyright "HeadShoulders_EA"
#property version   "1.05"
#property description "Trades the real-validated H&S/Inverse H&S measured-move target (75%/69%/75% hit rate, M15/H4/D1) - first real MT5 run"
#property strict
#include <Trade\Trade.mqh>
CTrade trade;

//--- Swing / pivot detection (identical construction to the Python research) ---
input group "=== Swing / pivot detection (same construction as research/trendbreaker/) ==="
input int    InpPivotStrength   = 5;       // N bars each side - N-bar fractal pivot
input double InpSwingMinATR     = 1.0;     // ZigZag "deviation": min swing leg, x ATR
input int    InpATRPeriod       = 14;      // SMA-of-true-range (MT5's iATR definition)
input int    InpLookbackBars    = 800;     // Bars of history scanned each recompute (real patterns resolve in ~80 bars on average - this is generous headroom, not a requirement)
input int    InpRecomputeEveryBars = 5;    // Re-scan for NEW pattern shapes every N bars (not every single bar) - AdvancePending()'s breakout confirmation still checks every bar regardless, this only throttles the expensive full swing rescan

input group "=== Head & Shoulders construction (real-validated target, see header) ==="
input double InpShoulderTolATR  = 1.5;     // Shoulders "roughly the same level" - max ATR apart
input double InpBreakTolATR     = 0.10;    // Close beyond the neckline by more than this = a close beyond
input int    InpBreakConfirmCloses = 3;    // Consecutive closes beyond the neckline to confirm the breakout
input double InpMaxHorizonMult  = 4.0;     // Give the target this many x the pattern's own formation length to hit (else the position runs on stop/target as normal - this only bounds how long a NEW pattern is still considered "live" for a fresh entry)

input group "=== Stop-loss (disclosed, NOT real-validated - see header) ==="
input double InpStopBufferATR   = 0.3;     // SL = right shoulder extreme +/- this x ATR - real Python evidence (2026-09-25, real GOLD data, single-position sequenced, research/trendbreaker/hs_stop_loss_test.py) found 1.0 meaningfully better (net +51%, PF 1.252->1.393 on M15) but this default is left at the original disclosed-not-validated 0.3 pending a real MT5 test - change this value yourself in the Tester's Inputs tab to try 1.0.

input group "=== RSI confluence filter (v1.02 candidate, off by default) ==="
input bool   InpUseRSIFilter    = false;   // Only take a trade when RSI is also at an extreme in the pattern's favour (oversold for a bullish Inverse H&S, overbought for a bearish H&S top) - real Python evidence (2026-09-25, real GOLD data, single-position sequenced, research/trendbreaker/hs_confluence_test.py, on top of the already-best pullback+runner construction): win% 52.0->63.4, PF 2.377->2.509, stable IS 65.9%/OOS 57.5% - but trades ~71% less often (n=456->131 over the same real 4.2-year window). Off by default: real, but Python-only, and this file's base construction (market entry, no pullback/runner) hasn't been re-checked with this filter specifically - see header for what HAS and hasn't shipped.
input int    InpRSIPeriod       = 14;      // RSI period - matches the real, native MT5 iRSI() indicator, not a manual port (RSI is standardized enough across platforms that this project's own ATR-mismatch lesson is not expected to apply the same way)
input double InpRSIThreshold    = 30.0;    // Oversold/overbought threshold (30 = the real-tested value; RSI <= this for a buy, >= 100-this for a sell)

input group "=== Pullback / retest entry (v1.03 candidate, off by default) ==="
input bool   InpUsePullbackEntry = false;  // Wait for a throwback/retest of the neckline within InpPullbackWindowBars bars after confirmation, instead of entering at market on the confirming close - real Python evidence (2026-09-25, real GOLD data, single-position sequenced, research/trendbreaker/hs_next_round_test.py): net +28-97% depending on what else is stacked with it. Off by default: real, but Python-only, first real MT5 run. A pattern whose retest never comes within the window is skipped entirely (matches the Python research's own "missed" bucket) - it does NOT fall back to a market entry.
input double InpPullbackTolATR   = 0.75;   // How close price must come back to the neckline to count as a genuine retest, x ATR captured at the breakout confirmation bar (InpUseRunner shares this same captured ATR - see its own comment)
input int    InpPullbackWindowBars = 30;   // Give the retest at most this many bars to happen after confirmation

input group "=== Trailing runner past target (v1.03 candidate, off by default) ==="
input bool   InpUseRunner        = false;  // Once price reaches the measured-move target, don't close 100% there - cancel the fixed broker-side TP and trail a stop InpRunnerTrailATR x ATR behind the best price seen since (ratchets one-way only, same as the Python research), letting the trade run further. Real Python evidence: net +48-51% on top of the base construction. Off by default: real, but Python-only, first real MT5 run. Before the target is first reached the position is unaffected - it can still only close on the original SL, same as with this off.
input double InpRunnerTrailATR   = 0.5;    // Trailing distance once the runner is armed, x ATR - captured ONCE at the breakout confirmation bar, not recomputed per bar (matches the Python research's own convention, same captured value as InpPullbackTolATR)

input group "=== Trade management ==="
input double InpLots             = 0.01;
input int    InpMagic            = 20260925;
input int    InpMaxSpreadPoints  = 60;     // Live-only spread gate (matches this portfolio's own real default)
input int    InpSlippage         = 30;

input group "=== Chart visuals ==="
input bool   InpDrawPatterns     = true;
input bool   InpDrawHistory      = true;
input int    InpHistoryDays      = 60;
input color  InpColTop            = C'255,61,90';    // H&S top - bearish, warm red
input color  InpColInverse         = C'0,230,118';   // Inverse H&S - bullish, green
input color  InpColTarget          = C'255,196,84';  // measured-move target line
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
input color  InpPanelEdge   = C'255,196,84';
input color  InpTitleCol    = C'255,196,84';
input color  InpSectionCol  = C'214,226,238';
input color  InpTextCol     = C'150,166,192';
input color  InpValCol      = C'236,242,252';
input color  InpOkCol       = C'0,230,118';
input color  InpNoCol       = C'255,61,90';
input color  InpShadowCol   = C'6,8,14';
input string InpPanelFont   = "Consolas";
input int    InpPanelSize   = 8;

//+------------------------------------------------------------------+
struct HSPattern
  {
   bool     top;                 // true = H&S top (bearish), false = inverse (bullish)
   int      i_s1, i_t1, i_head, i_t2, i_s2;   // array indices - valid only inside the Recompute() pass that found them, never relied on afterward
   double   p_s1, p_t1, p_head, p_t2, p_s2;
   datetime t_s1, t_t1, t_head, t_t2, t_s2;
   double   neckSlopePerSec;      // price per SECOND, not per bar-index - stays valid across separate CopyRates calls, unlike an index-based slope would
   int      brk_i;                // confirmed breakout bar index, -1 if not yet confirmed
   datetime brk_t;
   double   brk_price;
   double   target;
   double   stop;
   double   atrAtBrk;             // ATR captured at the breakout confirmation bar - shared by InpPullbackTolATR and InpRunnerTrailATR, matching the Python research's own "captured once, not recomputed per bar" convention
   bool     traded;
   int      run;                  // pending-only: consecutive closes beyond the neckline seen so far
  };

datetime g_lastBarTime = 0;
int      g_barCounter = 0;   // counts new bars since attach, for InpRecomputeEveryBars throttling
ulong    g_ticket = 0;
HSPattern g_patterns[];           // confirmed-breakout patterns (kept for drawing/history/entry)
HSPattern g_pending[];             // shapes found, not yet confirmed or expired - advanced one bar at a time
string   g_pz = "HSEA_";

int      g_panX = -1, g_panY = -1;
int      g_panelMinW = 0;
bool     g_panelReclaim = true;
bool     g_skipCosmeticDraws = false;   // PERFORMANCE FIX (see header, and this same idiom in every other EA in this portfolio - Fulcrum_EA.mq5 etc.) - computed once in OnInit, gates every pattern/panel/arrow draw call for the run's lifetime
datetime g_lastPanelDraw = 0;
int      g_statTrades = 0, g_statWins = 0;
int      g_rsiHandle = INVALID_HANDLE;   // InpUseRSIFilter - native iRSI(), not a manual port (see input comment)

//--- InpUseRunner state - single-position EA, so one set of globals is enough (see ArmRunner()/ManageRunner())
bool     g_runnerArmed = false;
bool     g_runnerReachedTarget = false;
double   g_runnerPeak = 0.0;
double   g_runnerTarget = 0.0;
double   g_runnerAtr = 0.0;
bool     g_runnerIsBuy = false;
double   g_runnerStop = 0.0;
bool     g_runnerJustArmed = false;   // ManageRunner() skips exactly one call right after ArmRunner() - see that flag's own comment

//+------------------------------------------------------------------+
int OnInit()
  {
   //--- PERFORMANCE FIX (see header v1.05, and Fulcrum_EA.mq5/Aurelius_EA.mq5/
   //--- etc.'s own identical fix) - a non-visual Strategy Tester run draws
   //--- NONE of the pattern markers/lines or the panel, since nobody can see
   //--- them and they have zero effect on any trading decision. Without this,
   //--- RefreshDrawings() was re-touching every confirmed pattern's several
   //--- chart objects on EVERY new bar, and DrawPanel() ~20 more every
   //--- simulated second, for the entire backtest - by far the dominant cost,
   //--- not the swing/pattern scan (that was already fixed in v1.01).
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);
   EventSetTimer(1);
   if(InpUseRSIFilter)
     {
      g_rsiHandle = iRSI(_Symbol, PERIOD_CURRENT, InpRSIPeriod, PRICE_CLOSE);
      if(g_rsiHandle == INVALID_HANDLE)
        {
         Print("HeadShoulders_EA: iRSI handle creation failed, error ", GetLastError());
         return(INIT_FAILED);
        }
     }
   //--- InpUseRunner restart recovery (Opus review High finding, fixed
   //--- pre-first-MT5-run): a terminal restart/recompile/profile reload
   //--- while a runner trade is open would otherwise reset g_runnerArmed to
   //--- false, leaving a real position with NO broker-side TP (InpUseRunner
   //--- sets tp=0.0) running on nothing but its original SL - the target and
   //--- trailing logic silently gone for the rest of that trade.
   if(InpUseRunner)
     {
      ulong tk;
      if(FindOwnPosition(tk))
        {
         g_ticket = tk;
         if(!RunnerLoadStateIfMatchingTicket(tk))
            PrintFormat("HeadShoulders_EA: found an open position (#%I64u) on init but no saved runner state for it - InpUseRunner will NOT manage this trade, it runs on its original SL only.", tk);
        }
     }
   return(INIT_SUCCEEDED);
  }
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_rsiHandle != INVALID_HANDLE) IndicatorRelease(g_rsiHandle);
   if(reason != REASON_CHARTCHANGE && reason != REASON_PARAMETERS)
      ObjectsDeleteAll(0, g_pz);
   Comment("");
  }
//+------------------------------------------------------------------+
//| InpUseRSIFilter gate - true means "not blocked" (filter off, or RSI   |
//| genuinely at the extreme the pattern's direction needs). Reads shift=1 |
//| (the confirmation bar itself), matching research/trendbreaker/         |
//| hs_confluence_test.py's rsi[b["brk_q"]] convention exactly - CheckFor-  |
//| Entry() only ever acts one bar after P.brk_t, so shift=1 IS the          |
//| confirmation bar at the moment this is called. Takes an explicit shift   |
//| (the confirmation bar's OWN shift, not always 1) because InpUsePullback-  |
//| Entry means CheckForEntry() can now act several bars after P.brk_t, and    |
//| research/trendbreaker/hs_confluence_test.py's RSI filter was validated on   |
//| top of the pullback+runner base reading RSI at rsi[b["brk_q"]] specifically  |
//| - i.e. the ORIGINAL confirmation bar, never the later retest/entry bar        |
//| (caught in Opus review before this file's first real MT5 run).                  |
//+------------------------------------------------------------------+
bool RSIFilterOk(const bool isBuy, const int confirmShift)
  {
   if(!InpUseRSIFilter) return(true);
   if(confirmShift < 0) return(false);
   double buf[];
   if(CopyBuffer(g_rsiHandle, 0, confirmShift, 1, buf) < 1) return(false);   // fail closed on a bad read, not open
   double r = buf[0];
   return(isBuy ? (r <= InpRSIThreshold) : (r >= 100.0 - InpRSIThreshold));
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
//| Price helpers - identical convention to TrendBreaker_MTF_Indicator |
//| (already reviewed there): dir<0 looks at the upper extreme, dir>0   |
//| the lower one; Pen()>0 means "beyond the line".                      |
//+------------------------------------------------------------------+
double ExtPx(const MqlRates &b, const int dir)
  {
   return(dir < 0 ? b.high : b.low);
  }
double Pen(const double px, const double lineVal, const int dir)
  {
   return(dir < 0 ? px - lineVal : lineVal - px);
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
int FindSwings(const MqlRates &r[], const double &atr[], const int n,
               int &zIdx[], int &zType[], double &zPx[])
  {
   int N = InpPivotStrength;
   int lastClosed = n - 2;
   int cnt = 0;
   ArrayResize(zIdx, 0); ArrayResize(zType, 0); ArrayResize(zPx, 0);
   for(int i = N; i <= lastClosed - N; i++)
     {
      double hi = ExtPx(r[i], -1), lo = ExtPx(r[i], 1);
      bool isH = true, isL = true;
      for(int m = 1; m <= N && (isH || isL); m++)
        {
         if(ExtPx(r[i - m], -1) >= hi || ExtPx(r[i + m], -1) > hi) isH = false;
         if(ExtPx(r[i - m],  1) <= lo || ExtPx(r[i + m],  1) < lo) isL = false;
        }
      double minLeg = InpSwingMinATR * atr[i];
      if(isH && isL)
        {
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
//| H&S shape scan - direct port of research/trendbreaker/            |
//| head_shoulders_target_test.py's find_hs_patterns()/run(), same     |
//| level-shoulder tolerance and neckline/target construction.         |
//+------------------------------------------------------------------+
int FindHSPatterns(const MqlRates &r[], const double &atr[], const int n,
                    const int &zIdx[], const int &zType[], const double &zPx[], const int zc,
                    HSPattern &out[])
  {
   int nOut = 0;
   ArrayResize(out, 0);
   for(int m = 0; m <= zc - 5; m++)
     {
      bool top;
      if(zType[m] == 1 && zType[m+1] == -1 && zType[m+2] == 1 && zType[m+3] == -1 && zType[m+4] == 1) top = true;
      else if(zType[m] == -1 && zType[m+1] == 1 && zType[m+2] == -1 && zType[m+3] == 1 && zType[m+4] == -1) top = false;
      else continue;

      double p1 = zPx[m], pt1 = zPx[m+1], phead = zPx[m+2], pt2 = zPx[m+3], p2 = zPx[m+4];
      if(top) { if(!(phead > p1 && phead > p2)) continue; }
      else    { if(!(phead < p1 && phead < p2)) continue; }
      if(MathAbs(p1 - p2) > InpShoulderTolATR * atr[zIdx[m+2]]) continue;

      HSPattern P; ZeroMemory(P);
      P.top = top;
      P.i_s1 = zIdx[m];   P.p_s1 = p1;    P.t_s1 = r[zIdx[m]].time;
      P.i_t1 = zIdx[m+1]; P.p_t1 = pt1;   P.t_t1 = r[zIdx[m+1]].time;
      P.i_head = zIdx[m+2]; P.p_head = phead; P.t_head = r[zIdx[m+2]].time;
      P.i_t2 = zIdx[m+3]; P.p_t2 = pt2;   P.t_t2 = r[zIdx[m+3]].time;
      P.i_s2 = zIdx[m+4]; P.p_s2 = p2;    P.t_s2 = r[zIdx[m+4]].time;
      long dtSec = (long)P.t_t2 - (long)P.t_t1;
      P.neckSlopePerSec = (dtSec != 0) ? (P.p_t2 - P.p_t1) / (double)dtSec : 0.0;
      P.brk_i = -1;
      P.traded = false;
      P.run = 0;
      ArrayResize(out, nOut + 1, 32);
      out[nOut++] = P;
     }
   return(nOut);
  }
double NecklineAtTime(const HSPattern &P, const datetime t)
  {
   return(P.p_t1 + P.neckSlopePerSec * (double)((long)t - (long)P.t_t1));
  }
//+------------------------------------------------------------------+
//| Same pattern (by its 5 anchor bar times) already recorded, either   |
//| confirmed or still pending?                                         |
//+------------------------------------------------------------------+
bool AlreadyKnown(const HSPattern &P)
  {
   for(int i = 0; i < ArraySize(g_patterns); i++)
      if(g_patterns[i].t_s1 == P.t_s1 && g_patterns[i].t_head == P.t_head && g_patterns[i].t_s2 == P.t_s2 && g_patterns[i].top == P.top)
         return(true);
   for(int i = 0; i < ArraySize(g_pending); i++)
      if(g_pending[i].t_s1 == P.t_s1 && g_pending[i].t_head == P.t_head && g_pending[i].t_s2 == P.t_s2 && g_pending[i].top == P.top)
         return(true);
   return(false);
  }
//+------------------------------------------------------------------+
//| Cheap ATR at the latest CLOSED bar (shift=1) - InpATRPeriod bars   |
//| only, not the full InpLookbackBars history, since this runs every   |
//| new bar for every pending candidate.                                 |
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
//| Finds NEW pattern shapes (full swing rescan - O(swings), not O(n)   |
//| per bar) and queues them as pending. Called once per new bar.        |
//+------------------------------------------------------------------+
void Recompute()
  {
   MqlRates r[]; ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpLookbackBars, r);
   if(n <= 4 * InpPivotStrength + InpATRPeriod + 20) return;

   double atr[]; BuildATR(r, n, atr);
   int zIdx[], zType[]; double zPx[];
   int zc = FindSwings(r, atr, n, zIdx, zType, zPx);
   if(zc < 5) return;

   HSPattern found[];
   int nf = FindHSPatterns(r, atr, n, zIdx, zType, zPx, zc, found);
   for(int i = 0; i < nf; i++)
     {
      if(AlreadyKnown(found[i])) continue;
      int k = ArraySize(g_pending);
      ArrayResize(g_pending, k + 1, 32);
      g_pending[k] = found[i];
     }
  }
//+------------------------------------------------------------------+
//| Advances every pending candidate by exactly the ONE newest closed   |
//| bar (O(1) per candidate per bar, not O(bars-since-formed)) - checks  |
//| for a confirmed breakout (InpBreakConfirmCloses consecutive closes    |
//| beyond the neckline) or expiry (InpMaxHorizonMult x its own            |
//| formation length with no breakout - Python's own "no longer live"      |
//| concept). Called once per new bar, after Recompute().                    |
//+------------------------------------------------------------------+
void AdvancePending()
  {
   if(ArraySize(g_pending) == 0) return;
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   if(t1 == 0) return;
   double atrNow = CurrentATR();
   int periodSec = PeriodSeconds(PERIOD_CURRENT);

   for(int i = ArraySize(g_pending) - 1; i >= 0; i--)
     {
      HSPattern P = g_pending[i];
      if(t1 <= P.t_s2) continue;   // this candidate's own formation bar hasn't closed relative to t1 yet (can happen the same bar it formed)

      double nl = NecklineAtTime(P, t1);
      double beyond = P.top ? (nl - c1) : (c1 - nl);
      bool confirmed = false;
      if(beyond > InpBreakTolATR * atrNow)
        {
         g_pending[i].run++;
         if(g_pending[i].run >= InpBreakConfirmCloses)
           {
            double headHeight = MathAbs(P.p_head - NecklineAtTime(P, P.t_head));
            if(headHeight > 0.0)
              {
               P = g_pending[i];
               P.brk_t = t1; P.brk_price = c1;
               P.atrAtBrk = atrNow;
               P.target = P.top ? (P.brk_price - headHeight) : (P.brk_price + headHeight);
               double shoulderExt = P.top ? MathMax(P.p_s1, P.p_s2) : MathMin(P.p_s1, P.p_s2);
               // disclosed NOT-validated stop choice - see header
               P.stop = P.top ? (shoulderExt + InpStopBufferATR * atrNow) : (shoulderExt - InpStopBufferATR * atrNow);
               P.brk_i = 0;   // no longer meaningful once we're off array indices - just marks "confirmed"
               int k = ArraySize(g_patterns);
               ArrayResize(g_patterns, k + 1, 32);
               g_patterns[k] = P;
               confirmed = true;
              }
           }
        }
      else
         g_pending[i].run = 0;

      long patLenSec = ((long)P.t_s2 - (long)P.t_s1);
      long ageSec = (long)t1 - (long)P.t_s2;
      long horizonSec = (long)(MathMax((double)patLenSec, (double)periodSec) * InpMaxHorizonMult);
      bool expired = (!confirmed) && (ageSec > horizonSec);

      if(confirmed || expired)
        {
         int last = ArraySize(g_pending) - 1;
         if(i != last) g_pending[i] = g_pending[last];
         ArrayResize(g_pending, last);
        }
     }
  }
//+------------------------------------------------------------------+
//| Entry. Two trigger modes:                                           |
//|  - InpUsePullbackEntry OFF (default): only acts on a pattern the       |
//|    EXACT bar its breakout is confirmed (P.brk_t == the just-closed      |
//|    bar) - unchanged from v1.02.                                          |
//|  - InpUsePullbackEntry ON: does NOT act on the confirmation bar itself;   |
//|    instead waits for the FIRST later bar (within InpPullbackWindowBars)    |
//|    whose high/low comes back to within InpPullbackTolATR x ATR of the       |
//|    neckline (a real throwback) - matches eval_pullback_entry() in            |
//|    research/trendbreaker/hs_next_round_test.py exactly, including that        |
//|    a retest that never comes within the window is skipped entirely, not        |
//|    a fallback market entry.                                                      |
//| A pattern that was already confirmed/decided is drawn/kept for history but        |
//| never traded late either way. InpMaxHorizonMult bounds how long an                 |
//| UNCONFIRMED candidate is still considered live (AdvancePending()'s own               |
//| expiry) - it does not apply here, since this only ever sees confirmed ones.           |
//+------------------------------------------------------------------+
void CheckForEntry()
  {
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   bool spreadOk = (InpMaxSpreadPoints <= 0 || spr <= InpMaxSpreadPoints);
   //--- NOTE: g_ticket!=0 no longer short-circuits the whole function (Opus
   //--- review finding, fixed pre-first-MT5-run) - a pattern whose trigger
   //--- condition fires a valid bar while a position is already open must be
   //--- marked traded=true (skipped for good) right then, exactly like
   //--- Python's last_exit_bar gating in research/trendbreaker/
   //--- hs_next_round_test.py. Previously it was silently left untraded and
   //--- could still fire on a LATER bar once flat again (InpUsePullbackEntry
   //--- mode only, since its trigger window spans many bars) - a real
   //--- divergence from the single-position-sequenced methodology this whole
   //--- project adopted after the giveback-exit mistake.
   bool canOpen = (g_ticket == 0) && spreadOk;

   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   double h1 = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double l1 = iLow(_Symbol, PERIOD_CURRENT, 1);

   for(int i = ArraySize(g_patterns) - 1; i >= 0; i--)
     {
      HSPattern P = g_patterns[i];
      if(P.traded) continue;

      bool trigger;
      int  confirmShift = 1;   // immediate-entry mode: the confirm bar IS shift=1 whenever this can fire
      if(!InpUsePullbackEntry)
        {
         trigger = (P.brk_t == t1);   // only act the bar immediately after confirmation
        }
      else
        {
         if(t1 <= P.brk_t) continue;   // retest can't happen at/before the confirm bar itself
         //--- bar-COUNT age, not wall-clock seconds / periodSec (Opus review
         //--- finding, fixed pre-first-MT5-run): dividing elapsed real time
         //--- by the period length overcounts "bars" across a weekend/session
         //--- gap (no bars actually form then but real time still passes),
         //--- silently shrinking the real retest window versus what
         //--- InpPullbackWindowBars says and versus what Python tested.
         int brkShift = iBarShift(_Symbol, PERIOD_CURRENT, P.brk_t, false);
         if(brkShift < 0) continue;
         confirmShift = brkShift;
         long ageBars = (long)brkShift - 1;
         if(ageBars > InpPullbackWindowBars) { g_patterns[i].traded = true; continue; }   // missed - matches the Python research's own "missed" bucket, skip entirely
         double nl = NecklineAtTime(P, t1);
         double tol = InpPullbackTolATR * P.atrAtBrk;
         trigger = P.top ? (h1 >= nl - tol) : (l1 <= nl + tol);
        }
      if(!trigger) continue;
      if(!canOpen) { g_patterns[i].traded = true; continue; }   // see the note above CheckForEntry()

      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      bool isBuy = !P.top;
      double entry = isBuy ? ask : bid;
      if(isBuy && P.target <= entry) { g_patterns[i].traded = true; continue; }
      if(!isBuy && P.target >= entry) { g_patterns[i].traded = true; continue; }
      if(isBuy && P.stop >= entry) { g_patterns[i].traded = true; continue; }
      if(!isBuy && P.stop <= entry) { g_patterns[i].traded = true; continue; }
      if(!RSIFilterOk(isBuy, confirmShift)) { g_patterns[i].traded = true; continue; }   // InpUseRSIFilter - see its own input comment; confirmShift tracks P.brk_t's own bar, not always shift=1 under InpUsePullbackEntry

      trade.SetExpertMagicNumber(InpMagic);
      trade.SetDeviationInPoints(InpSlippage);
      trade.SetTypeFillingBySymbol(_Symbol);
      string cmt = P.top ? "H&S top" : "Inverse H&S";
      double tp = InpUseRunner ? 0.0 : P.target;   // InpUseRunner replaces the fixed broker-side TP with ManageRunner()'s trailing stop - see its own input comment
      bool ok = isBuy ? trade.Buy(InpLots, _Symbol, entry, P.stop, tp, cmt)
                       : trade.Sell(InpLots, _Symbol, entry, P.stop, tp, cmt);
      g_patterns[i].traded = true;   // one shot per pattern either way - don't retry a rejected order every tick
      if(ok)
        {
         SyncPosition();
         if(!g_skipCosmeticDraws) DrawEntryArrow(P, entry);
         if(InpUseRunner) ArmRunner(P, isBuy);
        }
      else
         PrintFormat("HeadShoulders_EA: entry FAILED, retcode %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      return;
     }
  }
//+------------------------------------------------------------------+
//| InpUseRunner state persistence (Opus review finding, fixed pre-first-  |
//| MT5-run) - terminal GlobalVariables, keyed by symbol+magic, survive a    |
//| terminal restart/recompile/profile reload live. Without this, restarting  |
//| mid-trade would silently leave the runner permanently disarmed (the         |
//| globals reset to their false/0 defaults) while a real position with NO       |
//| broker-side TP (InpUseRunner sets tp=0.0) keeps running on nothing but the    |
//| original SL - the target/trailing logic would just be gone. OnInit()           |
//| restores it if a matching open position is found; SyncPosition() clears         |
//| it once the position is confirmed closed.                                        |
//+------------------------------------------------------------------+
string RunnerGVPrefix() { return("HSEA_RN_" + _Symbol + "_" + (string)InpMagic + "_"); }
void RunnerSaveState()
  {
   string p = RunnerGVPrefix();
   GlobalVariableSet(p + "ticket", (double)g_ticket);
   GlobalVariableSet(p + "armed", g_runnerArmed ? 1.0 : 0.0);
   GlobalVariableSet(p + "reached", g_runnerReachedTarget ? 1.0 : 0.0);
   GlobalVariableSet(p + "peak", g_runnerPeak);
   GlobalVariableSet(p + "target", g_runnerTarget);
   GlobalVariableSet(p + "atr", g_runnerAtr);
   GlobalVariableSet(p + "isbuy", g_runnerIsBuy ? 1.0 : 0.0);
   GlobalVariableSet(p + "stop", g_runnerStop);
  }
void RunnerClearState()
  {
   string p = RunnerGVPrefix();
   GlobalVariableDel(p + "ticket"); GlobalVariableDel(p + "armed"); GlobalVariableDel(p + "reached");
   GlobalVariableDel(p + "peak"); GlobalVariableDel(p + "target"); GlobalVariableDel(p + "atr");
   GlobalVariableDel(p + "isbuy"); GlobalVariableDel(p + "stop");
  }
bool RunnerLoadStateIfMatchingTicket(const ulong ticket)
  {
   string p = RunnerGVPrefix();
   if(!GlobalVariableCheck(p + "ticket")) return(false);
   if((ulong)GlobalVariableGet(p + "ticket") != ticket) return(false);
   if(GlobalVariableGet(p + "armed") < 0.5) return(false);
   g_runnerArmed = true;
   g_runnerReachedTarget = (GlobalVariableGet(p + "reached") >= 0.5);
   g_runnerPeak = GlobalVariableGet(p + "peak");
   g_runnerTarget = GlobalVariableGet(p + "target");
   g_runnerAtr = GlobalVariableGet(p + "atr");
   g_runnerIsBuy = (GlobalVariableGet(p + "isbuy") >= 0.5);
   g_runnerStop = GlobalVariableGet(p + "stop");
   return(true);
  }
//+------------------------------------------------------------------+
//| InpUseRunner - arm/manage the trailing runner. Single-position EA,   |
//| so global state is enough (ArmRunner() called once right after a       |
//| successful entry when InpUseRunner is on; ManageRunner() called once     |
//| per new bar; SyncPosition() disarms it when the position closes).         |
//| Mirrors eval_pullback_and_runner()'s runner leg in research/trendbreaker/  |
//| hs_next_round_test.py exactly: before the target is first reached, the      |
//| position is untouched (can only close on the original SL); once reached,     |
//| the stop ratchets to InpRunnerTrailATR x ATR behind the best price seen        |
//| since, one-way only, using the SAME ATR captured at the breakout bar.           |
//+------------------------------------------------------------------+
void ArmRunner(const HSPattern &P, const bool isBuy)
  {
   g_runnerArmed = true;
   g_runnerReachedTarget = false;
   g_runnerPeak = 0.0;
   g_runnerTarget = P.target;
   g_runnerAtr = P.atrAtBrk;
   g_runnerIsBuy = isBuy;
   g_runnerStop = P.stop;
   g_runnerJustArmed = true;   // ManageRunner() skips its very next call - see the note on that flag
   RunnerSaveState();
  }
void ManageRunner()
  {
   if(!InpUseRunner || !g_runnerArmed || g_ticket == 0) return;
   if(g_runnerJustArmed)
     {
      //--- skip the call that lands on the SAME bar as entry (Opus review
      //--- finding, fixed pre-first-MT5-run): OnTick's new-bar block calls
      //--- CheckForEntry() then ManageRunner() in the same pass, so without
      //--- this guard the very first check would read the ENTRY bar's own
      //--- high/low - a bar that, in InpUsePullbackEntry mode, by definition
      //--- already touched near the neckline, far from target. Python's own
      //--- loop only ever starts checking from entry_bar+1 onward.
      g_runnerJustArmed = false;
      return;
     }
   double h1 = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double l1 = iLow(_Symbol, PERIOD_CURRENT, 1);

   if(!g_runnerReachedTarget)
     {
      bool hit = g_runnerIsBuy ? (h1 >= g_runnerTarget) : (l1 <= g_runnerTarget);
      if(!hit) return;
      g_runnerReachedTarget = true;
      g_runnerPeak = g_runnerTarget;
     }

   g_runnerPeak = g_runnerIsBuy ? MathMax(g_runnerPeak, h1) : MathMin(g_runnerPeak, l1);
   double newStop = g_runnerIsBuy ? (g_runnerPeak - InpRunnerTrailATR * g_runnerAtr)
                                   : (g_runnerPeak + InpRunnerTrailATR * g_runnerAtr);
   //--- clamp to the broker's own minimum stop distance (Opus review Critical
   //--- finding, fixed pre-first-MT5-run): without this, once price moves far
   //--- enough that the trail distance (InpRunnerTrailATR x ATR) is TIGHTER
   //--- than the broker's SYMBOL_TRADE_STOPS_LEVEL/FREEZE_LEVEL, every single
   //--- PositionModify call below would be rejected as "invalid stops" - not
   //--- just once, but on EVERY future bar too (the gap stays roughly
   //--- constant as price and the trail both advance together), silently
   //--- leaving the position protected by nothing but the ORIGINAL stop for
   //--- the rest of the trade. A real winner could give back everything down
   //--- to that original stop with the runner never actually trailing.
   //--- Clamping to the broker's minimum keeps the trade genuinely protected
   //--- (tightest ALLOWED stop) instead of silently reverting to "no runner".
   long minDistPts = MathMax(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
                              SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL));
   double minDist = (double)minDistPts * _Point;
   if(minDist > 0.0)
     {
      double refPx = g_runnerIsBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      newStop = g_runnerIsBuy ? MathMin(newStop, refPx - minDist) : MathMax(newStop, refPx + minDist);
     }
   newStop = NormalizeDouble(newStop, _Digits);
   bool improves = g_runnerIsBuy ? (newStop > g_runnerStop) : (newStop < g_runnerStop);
   if(!improves) return;
   if(!PositionSelectByTicket(g_ticket)) return;   // position closed between OnTick's SyncPosition() and here - nothing to modify
   if(trade.PositionModify(g_ticket, newStop, 0.0) && trade.ResultRetcode() == TRADE_RETCODE_DONE)
     {
      g_runnerStop = newStop;
      RunnerSaveState();
     }
   else
      PrintFormat("HeadShoulders_EA: runner PositionModify FAILED, retcode %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
//| Own position only - matches THIS symbol AND magic number, so a      |
//| manually-opened or another EA's position on the same symbol is       |
//| never mistaken for this EA's own (same convention as every other      |
//| EA in this portfolio's FindOwnPosition()/SyncPositionState()).         |
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
      // position closed since the last check (TP/SL/manual) - find the closing deal for stats
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
      g_runnerArmed = false;   // InpUseRunner - position closed, disarm so a later position starts clean via ArmRunner()
      RunnerClearState();
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
void DrawEntryArrow(const HSPattern &P, const double px)
  {
   string tag = TimeToString(P.brk_t, TIME_DATE|TIME_MINUTES);
   DrawMarker(g_pz + "en_" + tag, P.brk_t, px, InpColEntryArrow, !P.top);
   DrawLabel(g_pz + "ent_" + tag, P.brk_t, px, (P.top ? "SELL " : "BUY ") + DoubleToString(px, _Digits), InpColEntryArrow);
  }
void DrawPattern(const HSPattern &P)
  {
   string base = g_pz + "p_" + TimeToString(P.t_head, TIME_DATE|TIME_MINUTES) + (P.top ? "T" : "I") + "_";
   color col = P.top ? InpColTop : InpColInverse;
   datetime tEnd = (P.brk_i >= 0) ? P.brk_t : P.t_s2;

   DrawMarker(base + "s1", P.t_s1, P.p_s1, col, !P.top);
   DrawMarker(base + "head", P.t_head, P.p_head, col, !P.top);
   DrawMarker(base + "s2", P.t_s2, P.p_s2, col, !P.top);
   DrawLabel(base + "hl", P.t_head, P.p_head, (P.top ? "  HEAD" : "  HEAD (inv)"), col);

   DrawLine(base + "neck", P.t_t1, P.p_t1, P.t_t2, P.p_t2, col, 2, STYLE_SOLID, true);
   DrawLabel(base + "necklbl", P.t_t2, P.p_t2, "  neckline", col);

   if(P.brk_i >= 0)
     {
      datetime tb0 = iTime(_Symbol, PERIOD_CURRENT, 0);
      datetime rightEdge = (tb0 > P.brk_t) ? tb0 : (datetime)((long)P.brk_t + 20 * PeriodSeconds(PERIOD_CURRENT));
      DrawLine(base + "tgt", P.brk_t, P.target, rightEdge, P.target, InpColTarget, 2, STYLE_DASH, true);
      DrawLabel(base + "tgtlbl", P.brk_t, P.target,
                "  target " + DoubleToString(P.target, _Digits), InpColTarget);
      DrawLine(base + "stop", P.brk_t, P.stop, rightEdge, P.stop, InpColNoStop(), 1, STYLE_DOT, false);
     }
  }
color InpColNoStop() { return(C'255,120,120'); }
void RefreshDrawings()
  {
   if(g_skipCosmeticDraws) return;   // PERFORMANCE FIX - see its own comment in OnInit()
   if(!InpDrawPatterns) { ObjectsDeleteAll(0, g_pz + "p_"); return; }
   datetime cutoff = InpDrawHistory ? (datetime)(TimeCurrent() - (long)InpHistoryDays * 86400) : (datetime)(TimeCurrent() - 5 * (long)PeriodSeconds(PERIOD_CURRENT) * InpLookbackBars);
   for(int i = 0; i < ArraySize(g_patterns); i++)
     {
      if(g_patterns[i].t_s2 < cutoff) continue;
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
//| Panel. ROWS/GAPS hand-counted against the literal PRow/PSection    |
//| sequence below - same discipline as this project's other panels.   |
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
   PText("t2", x + w - 12, ty + 3, "H&S EA", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   bool spreadOK = (InpMaxSpreadPoints <= 0 || spr <= InpMaxSpreadPoints);
   PSection("s1", x, ty, w, rh, "STATUS"); ty += rh + 6;                                          // GAP 1
   PRow("a0", x, ty, w, "timeframe", EnumToString((ENUM_TIMEFRAMES)_Period), 1); ty += rh;
   PRow("a1", x, ty, w, "spread", (string)spr + " / " + (string)InpMaxSpreadPoints, spreadOK ? 1 : 0); ty += rh;
   PRow("a2", x, ty, w, "position", g_ticket != 0 ? "OPEN" : "flat", g_ticket != 0 ? 1 : -1); ty += rh + 6;   // GAP 2

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
   PSection("s2", x, ty, w, rh, "PATTERNS"); ty += rh + 6;                                        // GAP 3
   PRow("b0", x, ty, w, "confirmed / traded", IntegerToString(nConfirmed) + " / " + IntegerToString(nTraded), -1); ty += rh;
   string lastTxt = "none yet"; int lastState = -1;
   if(lastIdx >= 0)
     {
      lastTxt = (g_patterns[lastIdx].top ? "TOP -> " : "INV -> ") + DoubleToString(g_patterns[lastIdx].target, _Digits);
      lastState = g_patterns[lastIdx].top ? 0 : 1;
     }
   PRow("b1", x, ty, w, "last confirmed", lastTxt, lastState); ty += rh;
   double wr = g_statTrades > 0 ? 100.0 * g_statWins / g_statTrades : 0.0;
   PRow("b2", x, ty, w, "session trades", IntegerToString(g_statTrades) + " (" + DoubleToString(wr, 0) + "% win)", -1); ty += rh + 6;   // GAP 4
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- sync FIRST (Opus review finding, fixed pre-first-MT5-run): without
   //--- this, g_ticket could still show the PREVIOUS bar's now-closed
   //--- position (e.g. it hit its SL/TP on this new bar's first tick) while
   //--- CheckForEntry() below reads it - in immediate-entry mode that
   //--- pattern's one and only trigger bar (P.brk_t == t1) has already
   //--- passed, so a real entry would be silently lost for good, not just
   //--- delayed. The call further down still runs every tick as before.
   SyncPosition();
   if(IsNewBar())
     {
      //--- the full swing rescan (Recompute) is the expensive part - O(lookback)
      //--- pivot scan plus an ArrayResize per swing found, redone almost
      //--- identically every bar if run unthrottled. AdvancePending() (breakout
      //--- confirmation, O(1) per pending candidate) still runs every bar - only
      //--- the search for BRAND NEW pattern shapes is throttled, and a pattern
      //--- takes many dozens of bars to even form, so a few bars' detection lag
      //--- here is immaterial.
      g_barCounter++;
      if(InpRecomputeEveryBars <= 1 || g_barCounter % InpRecomputeEveryBars == 0)
         Recompute();
      AdvancePending();
      CheckForEntry();
      ManageRunner();
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
