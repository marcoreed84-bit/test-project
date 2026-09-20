//+------------------------------------------------------------------+
//|                                                   Ichimoku_EA.mq5 |
//|  H4 Ichimoku Kinko Hyo swing system - v1.00 (first draft, NOT yet |
//|  real-MT5 tested - everything below is the Python replica result) |
//+------------------------------------------------------------------+
//|  WHAT THIS IS                                                     |
//|  ------------                                                     |
//|  The best candidate to come out of an extensive session testing   |
//|  the Ichimoku Cloud on real GOLD H4 bars (2013-01 .. 2026-08,      |
//|  20,571 bars), against two independent public sources (a          |
//|  standard Ichimoku Cloud PDF, and an FXStreet/Ian Coleman video)    |
//|  plus a detailed community "Kumo Breakout" checklist the user       |
//|  provided. Two configurations survived that search and are both     |
//|  shipped here, selectable via InpEntryMode:                          |
//|                                                                       |
//|  PLAIN  (InpEntryMode = ENTRY_PLAIN): Tenkan/Kijun cross while price   |
//|  is already beyond the current cloud (no Chikou requirement - that     |
//|  scored WORSE than leaving it off, counter to Ichimoku orthodoxy but    |
//|  that's what the real data showed). n=318, PF=1.817, IS PF=1.821 /       |
//|  OOS PF=1.784 (unusually close IS/OOS match - the main reason this        |
//|  survived at all), win%=43.4, avg win $43.95 / avg loss -$18.55 (2.37x     |
//|  size ratio - profit comes from asymmetric payoff, not win rate).           |
//|  Permutation-tested at the 78th percentile against a matched-count/          |
//|  direction null (bars with a real TK cross, random ones chosen) - real        |
//|  but short of this project's normal 95th-percentile bar. Top-5 trades         |
//|  are 61.1% of total net profit; 4 of 14 years negative.                        |
//|                                                                                   |
//|  BREAKOUT_FULL (InpEntryMode = ENTRY_BREAKOUT_FULL, the shipped DEFAULT):          |
//|  the user's full "Kumo Breakout" checklist - a FRESH, complete cloud                |
//|  breakout (price crosses fully outside the cloud this bar) + Tenkan/Kijun            |
//|  aligned in that direction + Chikou (today's close) completely clear of               |
//|  BOTH the price range AND the cloud from 26 bars back + the FUTURE                     |
//|  (forward-projected) cloud matching direction, refined with RSI(14)                      |
//|  70/30 exhaustion (InpUseRSI) and CMF(20) money-flow confirmation                          |
//|  (InpUseCMF). n=53, PF=2.474, IS PF=2.736 / OOS PF=2.181, win%=37.7,                          |
//|  90.5th percentile on the same permutation control - the single best                          |
//|  result of the whole search, but only ~4 trades/year (this is a SWING                          |
//|  system, not a frequent-trading one - do not expect daily entries).                              |
//|  Top-5 trades are 129.8% of net profit (more concentrated than PLAIN);                            |
//|  5 of 14 years negative.                                                                            |
//|                                                                                                        |
//|  NEITHER configuration clears this project's normal 95th-percentile                                    |
//|  permutation bar for being called "proven." Both are the best real                                      |
//|  candidates this search produced - genuinely better than a coin flip                                     |
//|  on the evidence, IS/OOS-consistent (the thing that killed nearly                                          |
//|  everything else tried) - but still honestly "probably, not certainly."                                     |
//|  This build exists to find out for real: run it through Strategy Tester                                       |
//|  on real GOLD H4 ticks and compare against the numbers above.                                                   |
//|                                                                                                                     |
//|  EXPLICITLY TESTED AND REJECTED (not included, do not re-add without re-                                          |
//|  testing): ADX(14)>20 filter (catastrophic OOS collapse - PF fell to                                               |
//|  ~0.01-0.1 out-of-sample in every combination, directly contradicting the                                            |
//|  source checklist's own claim); 200 EMA confluence (net negative); cloud-                                             |
//|  rejection/pullback entries (underperformed the plain cross); Senkou Span A/B                                          |
//|  cross used as a standalone leading trigger (only 52.5th percentile - noise);                                           |
//|  Ian Coleman's fixed 2:1/3:1 reward:risk exit with a stop beyond the trigger                                             |
//|  candle (8 of 12 configs outright lost money, best case had negative OOS).                                                |
//|                                                                                                                               |
//|  NO STOP-LOSS BY DEFAULT - this matches exactly what was validated in                                                        |
//|  Python (pure signal-based exit, no price-distance stop at all). This is a                                                     |
//|  REAL, HONEST RISK: a position could sit through a large adverse move                                                            |
//|  before the exit signal fires. InpSafetyStopATR (default 0 = OFF = exact                                                          |
//|  validated behaviour) adds an optional wide ATR-multiple stop purely as a                                                           |
//|  real-money safety net - it was NOT part of the backtest and changes the                                                              |
//|  exit geometry if enabled. Strongly consider turning it on before running                                                                |
//|  this live, but understand doing so makes the real numbers diverge from the                                                                |
//|  numbers quoted above until re-tested.                                                                                                        |
//|                                                                                                                                                    |
//|  Session close / weekend-gap protection included (InpCloseFriday) - this was                                                                      |
//|  NOT part of the Python validation either (H4 Ichimoku trades were simulated                                                                         |
//|  as continuing straight through weekends) but leaving real GOLD positions open                                                                        |
//|  over a weekend gap with no stop-loss is an unnecessary, untested risk this EA                                                                          |
//|  should not take on by default.                                                                                                                           |
//+------------------------------------------------------------------+
//|  v1.01 - fixes from a real MT5 Strategy Tester run (XM Global demo, GOLD#, H4,   |
//|  2022.01-2026.09, both modes) and an Opus-reviewed skeptical audit of the real     |
//|  trade-by-trade deal data. The run itself was NOT independent evidence of edge -    |
//|  it overlaps the 2013-2026 window the configs were selected on, and a same-dates      |
//|  passive-hold benchmark built from the real fills found the excess over just           |
//|  holding gold long/short was statistically indistinguishable from zero (t=0.25,          |
//|  n=15, BREAKOUT_FULL). That is a evaluation-methodology finding, not a code bug -           |
//|  the real next step is a permutation-null control run on real GOLD# H4 bars before            |
//|  trusting the PF at all. What WAS a code problem, fixed here:                                    |
//|                                                                                                     |
//|  1. FRIDAY/WEEKEND FLATTEN WAS DEAD CODE. FridayCutoff() was only ever checked        |
//|     inside the new-bar gate in OnTick, but H4 bars close at 00/04/08/12/16/20 server    |
//|     time - InpFridayCloseHour=21 could NEVER be reached on a new-bar tick. Confirmed      |
//|     directly: all 218 real deals across both test runs filled at hour in {4,8,12,16,20},   |
//|     zero off-bar exits. So every multi-day hold in both real runs (9/15 BREAKOUT_FULL,       |
//|     74/94 PLAIN) sat through weekends completely unprotected despite the header claiming       |
//|     this was covered. Fixed: the Friday-flatten check now runs on EVERY tick, not gated          |
//|     behind the new-bar check (weekend gaps don't wait for a bar close either).                     |
//|                                                                                                        |
//|  2. NO STOP-LOSS BY DEFAULT WAS A REAL, REALIZED COST. PLAIN mode's single worst real       |
//|     trade (long 2026.03.10 -> 2026.04.06, 27 days) lost 9222.19 ZAR - 92% of the entire        |
//|     starting deposit, in one trade. InpSafetyStopATR now DEFAULTS TO 3.5 (was 0.0/off).           |
//|     This is non-binding on the historical BREAKOUT_FULL trade set - the worst realized              |
//|     adverse move among its real losers was $47.73/oz, and 3.5x ATR(14) on H4 gold sits                |
//|     roughly $90-130/oz out, so the backtested trades are unaffected; it only cuts off a                 |
//|     tail that was never actually seen. Re-run both modes after this change to confirm the                |
//|     stop stays non-binding - that confirmation run IS the validation.                                      |
//|                                                                                                                |
//|  3. FIXED 0.01 LOTS LET NOTIONAL LEVERAGE TRIPLE AS GOLD RALLIED (2.9x -> 6.9x account            |
//|     equity across the BREAKOUT_FULL run, purely from gold's price rising - the lot size               |
//|     never adjusted). Added InpLotMode (LOT_FIXED default, or LOT_RISK_PCT) + InpRiskPct +               |
//|     InpMaxLots - risk-based sizing needs InpSafetyStopATR > 0 to have a stop distance to                  |
//|     size against (falls back to InpLots if the stop is off).                                                |
//|                                                                                                                |
//|  4. NO HISTORY-AVAILABILITY GUARD. DonchianHigh/Low call iHigh/iLow with no check - on a          |
//|     freshly attached live chart with thin preloaded history, iHigh/iLow can return 0.0,               |
//|     which would silently make "price above the cloud" trivially true and fire bogus entries.           |
//|     Added HasEnoughHistory(), checked every new bar before any signal logic runs.                        |
//|                                                                                                             |
//|  5. InpMaxSpreadPoints 600 -> 200 (600 = $6.00/oz, roughly 12-15x a normal XM gold spread -   |
//|     it was only ever blocking a catastrophically broken quote, not doing real filtering).       |
//|                                                                                                     |
//|  None of the above touches CheckEntry()/ShouldExit() - the signal logic itself (and thus         |
//|  the trade set the header's PF/win-rate/IS-OOS numbers describe) is byte-for-byte unchanged.    |
//+------------------------------------------------------------------+
//|  v1.02 - two findings from a real-MT5-vs-Python reconciliation and a fresh confluence search,  |
//|  both Opus-reviewed:                                                                             |
//|                                                                                                    |
//|  1. CORRECTED HEADER CLAIMS. The v1.01 Friday flatten (now genuinely live) turned out to be the    |
//|     DOMINANT exit in real trading - 9 of 15 real BREAKOUT_FULL exits and 72 of 109 real PLAIN       |
//|     exits were Friday flattens, not the TK-cross signal exit the top-of-file PF/win-rate numbers     |
//|     describe. Re-tested with the flatten properly modelled in Python: BREAKOUT_FULL's edge, which     |
//|     WAS real at ~95th percentile on the un-flattened signal (its profit lived specifically in multi-   |
//|     day/weekend holds), drops to the 73rd percentile once positions are actually cut every Friday -     |
//|     i.e. fixing the weekend-gap risk bug also cut off where a large share of the return came from.       |
//|     PLAIN survives the flatten with a real case on full history (94-95th percentile) but only the         |
//|     72nd percentile on the real 2022-2026 window, where it also underperformed simply holding gold         |
//|     long over the same dates. Also: "the stop is non-binding" (in the v1.01 note above) is no longer       |
//|     literally true - real batch3 stop-outs did occur (1/15 BREAKOUT_FULL, 13/109 PLAIN). The take-away:      |
//|     if you want BREAKOUT_FULL's real edge back, InpCloseFriday must be turned off (accepting real            |
//|     weekend-gap risk, protected only by the ATR stop) - it cannot have both weekend safety AND its            |
//|     validated edge with the flatten on. This EA still ships InpCloseFriday=true (safety first) with           |
//|     BREAKOUT_FULL no longer recommended as a result - see InpUseADX below for the current best PLAIN           |
//|     candidate instead.                                                                                          |
//|                                                                                                                    |
//|  2. InpUseADX (PLAIN mode only, default OFF - see its own input comment for the full numbers). A               |
//|     confluence search specifically on PLAIN (RSI, CMF, RSI+CMF, a D1-Ichimoku-cloud-alignment filter               |
//|     built by resampling the real H4 series, a tick-volume ratio filter, a minimum Tenkan/Kijun post-cross           |
//|     gap filter, and ADX(14)>20) found ADX>20 is the first config in this ENTIRE session's search - across            |
//|     dozens of ideas on Aurelius, Ichimoku, and everything else - to clear this project's 95th-percentile              |
//|     permutation bar (97.6th/97.3rd), with OOS beating IS and 12 of 14 years positive. RSI/CMF/volume/TK-gap            |
//|     filters were all neutral-to-harmful on PLAIN and are not shipped. NOT YET real-MT5 tested - that is the             |
//|     obvious next step before trusting it any further than "best candidate so far."                                       |
//|                                                                                                                             |
//|  v1.03 - real MT5 confirmed the ADX config is a genuine improvement over the unfiltered baseline (better           |
//|  PF/drawdown/balanced win rates), though tail concentration in that real run was worse than predicted.               |
//|  At the user's request, "stay in trades longer" was tested directly on this config (InpMinHoldBars below,             |
//|  Friday flatten modelled) rather than assumed - every value from 4-24 H4 bars beat the no-minimum baseline              |
//|  on PF, net AND negative-year count, a genuine plateau. Requiring BOTH the TK cross and a cloud-break                     |
//|  together to exit was also tried and rejected (held longer but PF came in worse). NOT yet real-MT5 tested.                |
//|                                                                                                                             |
//|  v1.04 - Opus-verified real trade-by-trade review of the shipped PLAIN+ADX+min-hold config (12 trades since             |
//|  2025-01-01, independently re-derived from the raw H4 data, not just re-run from this file). Two corrections            |
//|  to prior claims in this header: (1) InpSafetyStopATR's "non-binding" claim (v1.01 note above) was scoped to             |
//|  the BREAKOUT_FULL trade set and does NOT hold for PLAIN+ADX - the 3.5x stop actually fires on 5.9% of this               |
//|  config's trades (11/185) and OWNS the single worst loss in the entire 2013-2026 history (-$136.03/oz,                     |
//|  2026-05-05 short, a genuine multi-day adverse move, not a fluke). (2) A sweep of the stop distance (1.0x-5.0x)             |
//|  found tightening it is the FIRST "cut it short" idea this entire session that works without breaking the                    |
//|  edge - unlike trailing stops/breakeven/overextension-exits/early-turn-exits (all rejected, all cut WINNERS                    |
//|  short), a tighter stop protects LOSERS instead, a different mechanism. Net/PF/permutation-percentile are                       |
//|  statistically indistinguishable across 2.0x-3.5x (all still clear the 95th-percentile bar), while worst loss,                    |
//|  max drawdown and negative-year count all improve monotonically as the stop tightens - down to ~1.5x, below                        |
//|  which real winners start getting clipped and net collapses (34 winners clipped, net -22% at 1.0x). InpSafetyStopATR                |
//|  changed 3.5 -> 2.5 (worst loss -29%, maxDD -20%, negative years 1->0 of 14, net within noise at -1.8%, only ONE              |
//|  historical winner clipped for $20 total). NOT yet real-MT5 tested - confirm alongside InpUseADX/InpMinHoldBars.                    |
//|  CAVEAT: under InpLotMode=LOT_RISK_PCT (not the shipped default), a tighter stop means proportionally BIGGER lots               |
//|  and unchanged dollar risk per trade - this stop-loss benefit is specific to LOT_FIXED, the shipped default.                       |
//+------------------------------------------------------------------+
#property copyright "Session build - v1.04"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

enum ENUM_ENTRY_MODE { ENTRY_PLAIN = 0, ENTRY_BREAKOUT_FULL = 1 };
enum ENUM_EXIT_MODE  { EXIT_CROSS = 0, EXIT_CLOUD = 1 };
enum ENUM_LOTMODE    { LOT_FIXED = 0, LOT_RISK_PCT = 1 };

input group "=== Entry mode ==="
input ENUM_ENTRY_MODE InpEntryMode      = ENTRY_PLAIN;  // v1.05: was ENTRY_BREAKOUT_FULL, which combined with the
                                          // shipped InpCloseFriday=true/InpMinHoldBars=8/InpSafetyStopATR=2.5
                                          // below is a config that was NEVER tested anywhere in this file's own
                                          // changelog - an Opus full-sweep review found it loses money OOS
                                          // (PF 1.280 full history, OOS PF 0.700, 2022-26 PF 0.800, negative net
                                          // ex-top-5). BREAKOUT_FULL's PF 2.474/n=53 quoted below requires
                                          // InpCloseFriday=false + InpMinHoldBars=0 + InpSafetyStopATR=0 - it was
                                          // never validated with this file's own session-protection defaults on.
                                          // PLAIN+ADX (see InpUseADX below) is what v1.02-v1.04 actually
                                          // validated as the real, shipped-default-compatible config: n=191,
                                          // PF 1.994, net $1312.93, OOS PF 2.323 (beats IS), 1 losing year of 14.
input ENUM_EXIT_MODE  InpExitMode       = EXIT_CROSS;           // both configs validated best on CROSS, not CLOUD

input group "=== Ichimoku periods (standard) ==="
input int    InpTenkan         = 9;
input int    InpKijun          = 26;
input int    InpSenkouB        = 52;
input int    InpDisplacement   = 26;    // cloud forward-shift / Chikou back-shift, standard = Kijun period

input group "=== PLAIN mode only ==="
input bool   InpRequireChikou  = false;  // validated best OFF - leave false unless deliberately re-testing
input bool   InpUseADX         = true;   // v1.05: default false->true, REQUIRED to reach this file's own
                                          // documented-best config (see InpEntryMode above) - shipping PLAIN
                                          // without ADX is not a validated, tested combination either.
                                          // v1.02: PLAIN+ADX(14)>20, full 2013-2026 history, Friday flatten +
                                          // 3.5xATR stop modelled (the real exit shape this EA actually runs):
                                          // n=190, PF 2.055, net $1262.31, IS PF 1.971/OOS PF 2.181 (OOS beats
                                          // IS - a good sign, not overfit-shaped), 12 of 14 years positive,
                                          // top-5 trades = 55% of net (similar to the unfiltered baseline's
                                          // 51%, not materially more tail-heavy).
                                          // CORRECTED (v1.05, Opus full-sweep review): the "97.6th/97.3rd
                                          // percentile, first config to clear the 95th-percentile bar" claim
                                          // above was measured against a bar-level null that the UNFILTERED
                                          // PLAIN signal also clears at 99.4th - it was measuring the whole
                                          // PLAIN signal's edge, not ADX's incremental contribution. Against
                                          // this project's later, stricter null (random equal-size subsets of
                                          // the base signal's own trades): net 84.6th, PF 89.5th, maxDD 98.3rd,
                                          // best-of-7-thresholds-corrected 64.4th - NOT established as a net/PF
                                          // edge-adder. Threshold-free check (Spearman rho, ADX-at-entry vs
                                          // trade P&L) = +0.013, p=0.86 - essentially zero. HOWEVER it IS a
                                          // real, OOS-consistent DRAWDOWN reducer: maxDD 240->123 (98.3rd
                                          // percentile), negative years 3->1, stop-outs and worst-loss both
                                          // improve (see v1.04 note). Ship this as a risk reducer, not a
                                          // proven profit-adder - v1.03's real MT5 run directionally confirmed
                                          // the drawdown improvement, which is why it's still the shipped
                                          // default over no-ADX.
                                          // On the specific 2022-2026 window the real MT5 runs covered: n=56,
                                          // PF 1.856 (vs the unfiltered baseline's PF 1.543 same window).
                                          // NOTE: this is the opposite finding from BREAKOUT_FULL, where
                                          // ADX>20 was catastrophic (OOS PF collapsed to ~0.01-0.1) - the two
                                          // entry definitions interact with trend-strength filtering in
                                          // opposite ways, which is why this toggle only applies in PLAIN mode.
input int    InpADXPeriod      = 14;
input double InpADXThreshold   = 20.0;

input group "=== Exit timing ==="
input int    InpMinHoldBars    = 8;      // v1.03: block any non-Friday exit until this many H4 bars have
                                          // passed since entry (0 = off = v1.02 behaviour). Tested on the
                                          // validated PLAIN+ADX config with the Friday flatten modelled:
                                          // every value from 4-24 bars (16h-96h) beat the no-minimum
                                          // baseline on PF, net AND negative-year count (2/14 -> 1/14) -
                                          // a genuine plateau, not one lucky value. 8 (32h) picked as a
                                          // robust middle-of-plateau point, not the single best (4/16h,
                                          // PF 2.157 vs this value's 2.068) to avoid shipping a spike.
                                          // NOT yet real-MT5 tested - confirm alongside InpUseADX.
                                          // CLARIFIED (v1.05, Opus full-sweep review): despite the "block...
                                          // until" wording above, this CANCELS an exit cross that falls inside
                                          // the hold window rather than deferring it - ShouldExit()'s
                                          // EXIT_CROSS is a one-bar edge trigger, so a cross seen during the
                                          // hold period is gone by the time the gate opens, not queued. The
                                          // replica models this exactly and reproduces v1.03's real numbers,
                                          // so this IS the tested/shipped behaviour - just be aware 88% of the
                                          // shipped config's real exits are the Friday flatten (66%) or the
                                          // ATR stop (21%), not an Ichimoku signal exit (12%).

input group "=== BREAKOUT_FULL mode only - RSI/CMF refinement ==="
input bool   InpUseRSI         = true;
input int    InpRSIPeriod      = 14;
input double InpRSIHi          = 70.0;   // skip a long breakout if RSI > this (exhaustion)
input double InpRSILo          = 30.0;   // skip a short breakout if RSI < this
input bool   InpUseCMF         = true;
input int    InpCMFPeriod      = 20;     // Chaikin Money Flow, using tick_volume (real_volume is 0 on this broker)

input group "=== Risk ==="
input ENUM_LOTMODE InpLotMode  = LOT_FIXED;   // LOT_RISK_PCT needs InpSafetyStopATR > 0 (a stop distance to size against)
input double InpLots           = 0.01;        // used directly in LOT_FIXED mode; also the fallback if risk-sizing can't compute
input double InpRiskPct        = 1.0;         // LOT_RISK_PCT only: % of equity risked per trade (vs the safety stop distance)
input double InpMaxLots        = 1.0;         // hard cap on any computed lot size
input double InpSafetyStopATR  = 2.5;         // v1.04: tightened from 3.5 after a real trade-by-trade review found the
                                               // stop DOES bind on the shipped PLAIN+ADX config (fires on 5.9% of
                                               // trades at 3.5x, unlike the BREAKOUT_FULL set the old "non-binding"
                                               // claim was actually about). 2.5x cuts the worst historical loss 29%
                                               // (-136.03 -> -97.17/oz) and max drawdown 20%, with net within noise
                                               // (-1.8%) and only one historical winner clipped ($20 total) - see
                                               // header v1.04 note for the full sweep. Do not go below ~1.5x: real
                                               // winners start getting clipped and net collapses. Set to 0.0 to
                                               // restore the original no-stop validated behaviour.
input int    InpMaxSpreadPoints= 200;         // v1.01: was 600 ($6.00/oz, ~12-15x normal XM gold spread)
input int    InpSlippage       = 30;

input group "=== Session protection (not in the Python backtest - see header) ==="
input bool   InpCloseFriday      = true;
input int    InpFridayCloseHour  = 21;   // server hour to flatten on Friday
input int    InpNoEntryAfterHourFri = 19;

input group "=== Identity ==="
input ulong  InpMagic          = 750031;
input string InpComment        = "Ichimoku";

CTrade        trade;
CPositionInfo pos;

datetime g_lastBarTime = 0;
int      g_barsInTrade = 0;   // v1.03: bars elapsed since entry, for InpMinHoldBars
bool     g_exitPending = false;   // v1.05: a close request that failed and must be retried - see ManagePosition

//+------------------------------------------------------------------+
int OnInit()
  {
   if(Period() != PERIOD_H4)
     {
      Print("Ichimoku_EA: this model was validated on H4 bars only - attach it to an H4 chart. Current period: ", EnumToString(Period()));
      return(INIT_FAILED);
     }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(InpSlippage);

   //--- v1.05 (Opus full-sweep review): restore per-trade state. Without this,
   //--- a restart/recompile/input change while a position is open (a) re-arms
   //--- InpMinHoldBars from zero, which - since ShouldExit()'s EXIT_CROSS is a
   //--- one-bar edge trigger, not a latch - can permanently cancel that trade's
   //--- signal exit, and (b) leaves g_lastBarTime at 0, so the first tick after
   //--- restart is treated as a new bar even mid-bar, letting ManagePosition()/
   //--- TryEnter() re-process a bar the EA may already have acted on before the
   //--- restart (e.g. re-entering a signal that was already stopped out).
   g_lastBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   g_barsInTrade = 0;
   g_exitPending = false;
   bool initIsBuy;
   if(HavePosition(initIsBuy))
     {
      datetime openTime = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         if(!pos.SelectByIndex(i)) continue;
         if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
         openTime = pos.Time();
         break;
        }
      if(openTime > 0)
        {
         int barsSince = Bars(_Symbol, PERIOD_CURRENT, openTime, TimeCurrent());
         g_barsInTrade = (barsSince > 0) ? barsSince - 1 : 0;   // 0 on the entry bar, matching live semantics
        }
     }
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {}
//+------------------------------------------------------------------+
//| v1.01: guards against thin/not-yet-loaded history returning 0.0   |
//| from iHigh/iLow, which would silently make "price above the cloud"|
//| trivially true. CloudTop/Bot(1) reaches back to bar 1+2*Displacement|
//| +SenkouB in the worst case (the Chikou-vs-cloud-26-back check).    |
//+------------------------------------------------------------------+
bool HasEnoughHistory()
  {
   //--- v1.05 (Opus full-sweep review): must also cover the manual indicators'
   //--- own warmups, which exceed the Ichimoku lookback - ComputeADX needs
   //--- 2*period + period*8 + 2 (142 bars at period=14), ComputeRSI/ComputeATR
   //--- need period*9 + 1 (127 bars). Without this, a freshly attached chart
   //--- with 124-142 bars passes this guard but ComputeADX/ComputeRSI silently
   //--- return false, so CheckEntry() returns 0 - fails safe (no bogus entries)
   //--- but with no explanation for the extended no-trade window.
   int need    = InpSenkouB + 2 * InpDisplacement + 20;
   int adxNeed = 2 * InpADXPeriod + InpADXPeriod * 8 + 4;
   int oscNeed = MathMax(InpRSIPeriod, 14) * 9 + 4;
   need = MathMax(need, MathMax(adxNeed, oscNeed));
   return(Bars(_Symbol, PERIOD_CURRENT) >= need);
  }
//+------------------------------------------------------------------+
//| Donchian-mid building blocks - matches the Python (hi+lo)/2 over a|
//| rolling window ending at `shift`, i.e. bars [shift, shift+period-1]|
//+------------------------------------------------------------------+
double DonchianHigh(const int shift, const int period)
  {
   double hh = -DBL_MAX;
   for(int k = shift; k < shift + period; k++)
     {
      double v = iHigh(_Symbol, PERIOD_CURRENT, k);
      if(v > hh) hh = v;
     }
   return(hh);
  }
double DonchianLow(const int shift, const int period)
  {
   double ll = DBL_MAX;
   for(int k = shift; k < shift + period; k++)
     {
      double v = iLow(_Symbol, PERIOD_CURRENT, k);
      if(v < ll) ll = v;
     }
   return(ll);
  }
double Tenkan(const int shift)     { return((DonchianHigh(shift, InpTenkan)  + DonchianLow(shift, InpTenkan))  / 2.0); }
double Kijun(const int shift)      { return((DonchianHigh(shift, InpKijun)   + DonchianLow(shift, InpKijun))   / 2.0); }
double SenkouARaw(const int shift) { return((Tenkan(shift) + Kijun(shift)) / 2.0); }
double SenkouBRaw(const int shift) { return((DonchianHigh(shift, InpSenkouB) + DonchianLow(shift, InpSenkouB)) / 2.0); }
//--- the cloud drawn OVER bar `shift` was computed InpDisplacement bars earlier
double CloudTop(const int shift) { return(MathMax(SenkouARaw(shift + InpDisplacement), SenkouBRaw(shift + InpDisplacement))); }
double CloudBot(const int shift) { return(MathMin(SenkouARaw(shift + InpDisplacement), SenkouBRaw(shift + InpDisplacement))); }
//+------------------------------------------------------------------+
//| Manual Wilder RSI at bar `shift` - warmup window of period*8 bars |
//| (Wilder's (n-1)/n decay makes the seed's influence negligible by   |
//| then), recomputed fresh each call rather than kept as running      |
//| state, so it can't drift or desync. Same principle StochSwing_EA's  |
//| ComputeWilderATR uses for the same reason.                          |
//+------------------------------------------------------------------+
bool ComputeRSI(const int shift, const int period, double &out)
  {
   int warm = period * 8;
   int need = period + warm + 1;
   double c[];
   ArraySetAsSeries(c, false);
   if(CopyClose(_Symbol, PERIOD_CURRENT, shift, need, c) < need) return(false);
   double avgGain = 0.0, avgLoss = 0.0;
   for(int i = 1; i <= period; i++)
     {
      double d = c[i] - c[i-1];
      if(d > 0) avgGain += d; else avgLoss += -d;
     }
   avgGain /= period; avgLoss /= period;
   for(int i = period + 1; i < need; i++)
     {
      double d = c[i] - c[i-1];
      double g = d > 0 ? d : 0.0;
      double l = d < 0 ? -d : 0.0;
      avgGain = (avgGain * (period - 1) + g) / period;
      avgLoss = (avgLoss * (period - 1) + l) / period;
     }
   out = (avgLoss <= 0.0) ? 100.0 : 100.0 - 100.0 / (1.0 + avgGain / avgLoss);
   return(true);
  }
//+------------------------------------------------------------------+
//| Chaikin Money Flow at bar `shift`, using tick_volume (real_volume  |
//| is 0 on this broker for GOLD - matches the Python cmf() function). |
//+------------------------------------------------------------------+
bool ComputeCMF(const int shift, const int period, double &out)
  {
   double h[], l[], c[];
   long   v[];
   ArraySetAsSeries(h, false); ArraySetAsSeries(l, false); ArraySetAsSeries(c, false); ArraySetAsSeries(v, false);
   if(CopyHigh(_Symbol, PERIOD_CURRENT, shift, period, h) < period) return(false);
   if(CopyLow(_Symbol, PERIOD_CURRENT, shift, period, l) < period) return(false);
   if(CopyClose(_Symbol, PERIOD_CURRENT, shift, period, c) < period) return(false);
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, shift, period, v) < period) return(false);
   double sumMFV = 0.0, sumVol = 0.0;
   for(int i = 0; i < period; i++)
     {
      double rng = h[i] - l[i];
      double mfm = (rng > 0.0) ? ((c[i] - l[i]) - (h[i] - c[i])) / rng : 0.0;
      double vv  = (double)v[i];
      sumMFV += mfm * vv;
      sumVol += vv;
     }
   if(sumVol <= 0.0) return(false);
   out = sumMFV / sumVol;
   return(true);
  }
//+------------------------------------------------------------------+
//| Manual Wilder ATR - only used for the optional InpSafetyStopATR   |
//| net, same construction as StochSwing_EA's ComputeWilderATR.        |
//+------------------------------------------------------------------+
bool ComputeATR(const int shift, const int period, double &out)
  {
   int warm = period * 8;
   int need = period + warm + 1;
   double h[], l[], c[];
   ArraySetAsSeries(h, false); ArraySetAsSeries(l, false); ArraySetAsSeries(c, false);
   if(CopyHigh(_Symbol, PERIOD_CURRENT, shift, need, h) < need) return(false);
   if(CopyLow(_Symbol, PERIOD_CURRENT, shift, need, l) < need) return(false);
   if(CopyClose(_Symbol, PERIOD_CURRENT, shift, need, c) < need) return(false);
   double tr[]; ArrayResize(tr, need);
   tr[0] = h[0] - l[0];
   for(int i = 1; i < need; i++)
      tr[i] = MathMax(h[i]-l[i], MathMax(MathAbs(h[i]-c[i-1]), MathAbs(l[i]-c[i-1])));
   double seed = 0.0;
   for(int i = 1; i <= period; i++) seed += tr[i];
   seed /= period;
   double atr = seed;
   for(int i = period + 1; i < need; i++) atr = (atr * (period - 1) + tr[i]) / period;
   out = atr;
   return(true);
  }
//+------------------------------------------------------------------+
//| Manual Wilder ADX (v1.02) - ports the same two-stage Wilder        |
//| smoothing (TR/+DM/-DM, then DX->ADX) this project's Python adx_lib |
//| used to find the InpUseADX result. Bounded warmup window (period*8 |
//| bars, same convergence principle as ComputeRSI/ComputeATR above),  |
//| recomputed fresh each call rather than kept as running state.      |
//+------------------------------------------------------------------+
bool ComputeADX(const int shift, const int period, double &out)
  {
   int warm = period * 8;
   int need = 2 * period + warm + 2;
   double h[], l[], c[];
   ArraySetAsSeries(h, false); ArraySetAsSeries(l, false); ArraySetAsSeries(c, false);
   if(CopyHigh(_Symbol, PERIOD_CURRENT, shift, need, h) < need) return(false);
   if(CopyLow(_Symbol, PERIOD_CURRENT, shift, need, l) < need) return(false);
   if(CopyClose(_Symbol, PERIOD_CURRENT, shift, need, c) < need) return(false);

   double tr[], pdm[], mdm[];
   ArrayResize(tr, need); ArrayResize(pdm, need); ArrayResize(mdm, need);
   tr[0] = h[0] - l[0]; pdm[0] = 0.0; mdm[0] = 0.0;
   for(int i = 1; i < need; i++)
     {
      double up = h[i] - h[i-1];
      double dn = l[i-1] - l[i];
      pdm[i] = (up > dn && up > 0.0) ? up : 0.0;
      mdm[i] = (dn > up && dn > 0.0) ? dn : 0.0;
      tr[i] = MathMax(h[i]-l[i], MathMax(MathAbs(h[i]-c[i-1]), MathAbs(l[i]-c[i-1])));
     }

   double smTR = 0.0, smPDM = 0.0, smMDM = 0.0;
   for(int i = 1; i <= period; i++) { smTR += tr[i]; smPDM += pdm[i]; smMDM += mdm[i]; }
   smTR /= period; smPDM /= period; smMDM /= period;

   int dxCount = need - period;
   double dxArr[]; ArrayResize(dxArr, dxCount);
   double plusDI = (smTR > 0.0) ? 100.0*smPDM/smTR : 0.0;
   double minusDI = (smTR > 0.0) ? 100.0*smMDM/smTR : 0.0;
   double diSum = plusDI + minusDI;
   dxArr[0] = (diSum > 0.0) ? 100.0*MathAbs(plusDI-minusDI)/diSum : 0.0;

   for(int i = period + 1; i < need; i++)
     {
      smTR  = (smTR*(period-1)  + tr[i])  / period;
      smPDM = (smPDM*(period-1) + pdm[i]) / period;
      smMDM = (smMDM*(period-1) + mdm[i]) / period;
      plusDI  = (smTR > 0.0) ? 100.0*smPDM/smTR : 0.0;
      minusDI = (smTR > 0.0) ? 100.0*smMDM/smTR : 0.0;
      diSum = plusDI + minusDI;
      dxArr[i-period] = (diSum > 0.0) ? 100.0*MathAbs(plusDI-minusDI)/diSum : 0.0;
     }

   if(dxCount < 2*period) return(false);
   double adx = 0.0;
   for(int k = 0; k < period; k++) adx += dxArr[k];
   adx /= period;
   for(int k = period; k < dxCount; k++) adx = (adx*(period-1) + dxArr[k]) / period;

   out = adx;
   return(true);
  }
//+------------------------------------------------------------------+
//| Entry signal on the just-closed bar (shift=1). Returns 0/1/-1.    |
//+------------------------------------------------------------------+
int CheckEntry()
  {
   int s = 1;
   double tenkanNow = Tenkan(s),  kijunNow = Kijun(s);
   double tenkanPrev = Tenkan(s+1), kijunPrev = Kijun(s+1);
   double cloudTopNow = CloudTop(s), cloudBotNow = CloudBot(s);
   double closeNow = iClose(_Symbol, PERIOD_CURRENT, s);

   if(InpEntryMode == ENTRY_PLAIN)
     {
      bool crossUp = tenkanNow > kijunNow && tenkanPrev <= kijunPrev;
      bool crossDn = tenkanNow < kijunNow && tenkanPrev >= kijunPrev;
      bool aboveCloud = closeNow > cloudTopNow;
      bool belowCloud = closeNow < cloudBotNow;
      bool chikouOkUp = true, chikouOkDn = true;
      if(InpRequireChikou)
        {
         double closeBack = iClose(_Symbol, PERIOD_CURRENT, s + InpDisplacement);
         chikouOkUp = closeNow > closeBack;
         chikouOkDn = closeNow < closeBack;
        }
      bool adxOk = true;
      if(InpUseADX)
        {
         double adxVal;
         if(!ComputeADX(s, InpADXPeriod, adxVal)) return(0);
         adxOk = adxVal > InpADXThreshold;
        }
      if(crossUp && aboveCloud && chikouOkUp && adxOk) return(1);
      if(crossDn && belowCloud && chikouOkDn && adxOk) return(-1);
      return(0);
     }

   // ENTRY_BREAKOUT_FULL
   double cloudTopPrev = CloudTop(s+1), cloudBotPrev = CloudBot(s+1);
   double closePrev = iClose(_Symbol, PERIOD_CURRENT, s+1);
   bool breakoutUp = closeNow > cloudTopNow && closePrev <= cloudTopPrev;
   bool breakoutDn = closeNow < cloudBotNow && closePrev >= cloudBotPrev;
   if(!breakoutUp && !breakoutDn) return(0);

   bool tkOkUp = tenkanNow > kijunNow;
   bool tkOkDn = tenkanNow < kijunNow;

   //--- deliberately the SINGLE bar's high/low at s+InpDisplacement, not a
   //--- range max/min - matches the Python source's c[i] > h[i-26] exactly
   //--- (confirmed against the Python definition during the v1.01 audit,
   //--- not a discrepancy - the trade-count gap between the Python model's
   //--- expected ~18 and the real 15 was checked separately and is within
   //--- normal sampling noise, see the v1.01 audit notes)
   double highBack = iHigh(_Symbol, PERIOD_CURRENT, s + InpDisplacement);
   double lowBack  = iLow(_Symbol,  PERIOD_CURRENT, s + InpDisplacement);
   double cloudTopBack = CloudTop(s + InpDisplacement);
   double cloudBotBack = CloudBot(s + InpDisplacement);
   bool chikouOkUp = closeNow > highBack && closeNow > cloudTopBack;
   bool chikouOkDn = closeNow < lowBack  && closeNow < cloudBotBack;

   double senkouARawNow = SenkouARaw(s), senkouBRawNow = SenkouBRaw(s);
   bool futureOkUp = senkouARawNow > senkouBRawNow;
   bool futureOkDn = senkouARawNow < senkouBRawNow;

   bool rsiOkUp = true, rsiOkDn = true;
   if(InpUseRSI)
     {
      double r;
      if(!ComputeRSI(s, InpRSIPeriod, r)) return(0);
      rsiOkUp = r <= InpRSIHi;
      rsiOkDn = r >= InpRSILo;
     }
   bool cmfOkUp = true, cmfOkDn = true;
   if(InpUseCMF)
     {
      double m;
      if(!ComputeCMF(s, InpCMFPeriod, m)) return(0);
      cmfOkUp = m > 0.0;
      cmfOkDn = m < 0.0;
     }

   if(breakoutUp && tkOkUp && chikouOkUp && futureOkUp && rsiOkUp && cmfOkUp) return(1);
   if(breakoutDn && tkOkDn && chikouOkDn && futureOkDn && rsiOkDn && cmfOkDn) return(-1);
   return(0);
  }
//+------------------------------------------------------------------+
bool ShouldExit(const bool isBuy)
  {
   int s = 1;
   if(InpExitMode == EXIT_CROSS)
     {
      double tenkanNow = Tenkan(s), kijunNow = Kijun(s);
      double tenkanPrev = Tenkan(s+1), kijunPrev = Kijun(s+1);
      if(isBuy)  return(tenkanNow < kijunNow && tenkanPrev >= kijunPrev);
      else       return(tenkanNow > kijunNow && tenkanPrev <= kijunPrev);
     }
   // EXIT_CLOUD
   double closeNow = iClose(_Symbol, PERIOD_CURRENT, s);
   double cloudTopNow = CloudTop(s), cloudBotNow = CloudBot(s);
   if(isBuy)  return(closeNow < cloudBotNow);
   else       return(closeNow > cloudTopNow);
  }
//+------------------------------------------------------------------+
bool FridayCutoff(const bool forEntry)
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   if(t.day_of_week != 5) return(false);
   if(forEntry) return(t.hour >= InpNoEntryAfterHourFri);
   return(InpCloseFriday && t.hour >= InpFridayCloseHour);
  }
//+------------------------------------------------------------------+
bool HavePosition(bool &isBuy)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      isBuy = (pos.PositionType() == POSITION_TYPE_BUY);
      return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
bool ClosePosition(const string reason)
  {
   //--- v1.05 (Opus full-sweep review): now returns whether every leg actually
   //--- closed, so callers can latch-and-retry instead of assuming success.
   bool allClosed = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      if(trade.PositionClose(pos.Ticket()))
         Print("Ichimoku_EA: closed - ", reason);
      else
        {
         Print("Ichimoku_EA: close FAILED (", reason, "), ", trade.ResultRetcodeDescription());
         allClosed = false;
        }
     }
   return(allClosed);
  }
//+------------------------------------------------------------------+
void ManagePosition()
  {
   bool isBuy;
   if(!HavePosition(isBuy)) { g_barsInTrade = 0; g_exitPending = false; return; }
   //--- v1.05 (Opus full-sweep review): ShouldExit()'s EXIT_CROSS is a ONE-BAR
   //--- edge trigger (tenkan/kijun just crossed) - if the close request fails,
   //--- that cross will never be true again, so a failed exit must be LATCHED
   //--- and retried, not silently dropped. g_barsInTrade must also stay
   //--- unchanged (NOT reset) until the position is actually flat, since
   //--- resetting it on a failed close would additionally re-arm
   //--- InpMinHoldBars and delay the retry by that many more bars.
   if(g_exitPending || (g_barsInTrade >= InpMinHoldBars && ShouldExit(isBuy)))
     {
      g_exitPending = true;
      if(ClosePosition(InpExitMode == EXIT_CROSS ? "TK_CROSS" : "CLOUD_BREAK"))
        {
         g_barsInTrade = 0;
         g_exitPending = false;
        }
      return;
     }
   g_barsInTrade++;
  }
//+------------------------------------------------------------------+
//| v1.01: risk-based lot sizing - only used when InpLotMode==        |
//| LOT_RISK_PCT AND a safety stop distance actually exists (falls     |
//| back to InpLots otherwise, e.g. InpSafetyStopATR==0.0).            |
//+------------------------------------------------------------------+
double LotSize(const double entryPrice, const double slPrice)
  {
   if(InpLotMode != LOT_RISK_PCT || InpSafetyStopATR <= 0.0) return(InpLots);
   double riskDistance = MathAbs(entryPrice - slPrice);
   if(riskDistance <= 0.0) return(InpLots);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0) return(InpLots);
   double riskPerLot = (riskDistance / tickSize) * tickValue;
   if(riskPerLot <= 0.0) return(InpLots);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double lots = (equity * (InpRiskPct / 100.0)) / riskPerLot;

   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0.0) lots = MathFloor(lots / step) * step;
   lots = MathMax(minLot, MathMin(MathMin(lots, maxLot), InpMaxLots));
   return(lots);
  }
//+------------------------------------------------------------------+
void TryEnter()
  {
   bool dummy;
   if(HavePosition(dummy)) return;
   if(FridayCutoff(true)) return;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return;
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) return;
   if(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL) return;

   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && spreadPts > InpMaxSpreadPoints) return;

   int dir = CheckEntry();
   if(dir == 0) return;

   double price = (dir == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = 0.0;
   if(InpSafetyStopATR > 0.0)
     {
      double atr;
      //--- v1.05 (Opus full-sweep review): previously, an ATR read failure here
      //--- silently left sl=0.0 and the trade opened with NO stop at all despite
      //--- InpSafetyStopATR>0 asking for one - defeating v1.01's entire safety-
      //--- net purpose. In LOT_RISK_PCT mode it was worse: LotSize(price, 0.0)
      //--- computes riskDistance=price, producing an absurdly undersized lot
      //--- clamped to the minimum. Skip the entry instead of taking it stop-less.
      if(!ComputeATR(1, 14, atr) || atr <= 0.0)
        {
         Print("Ichimoku_EA: entry skipped - InpSafetyStopATR is on but ATR is unavailable");
         return;
        }
      sl = (dir == 1) ? price - InpSafetyStopATR * atr : price + InpSafetyStopATR * atr;
      long stopsPts  = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      long freezePts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
      double minStop = MathMax(MathMax(stopsPts, freezePts) * _Point, _Point);
      double closePx = (dir == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(MathAbs(closePx - sl) < minStop)
         sl = (dir == 1) ? closePx - minStop : closePx + minStop;
      sl = NormalizeDouble(sl, _Digits);
     }

   double lots = LotSize(price, sl);
   bool ok = (dir == 1) ? trade.Buy(lots, _Symbol, 0.0, sl, 0.0, InpComment)
                         : trade.Sell(lots, _Symbol, 0.0, sl, 0.0, InpComment);
   if(ok)
     {
      g_barsInTrade = 0;
      g_exitPending = false;
     }
   else
      Print("Ichimoku_EA: entry failed, ", trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- v1.01: weekend/Friday flatten now runs on EVERY tick, not gated
   //--- behind the new-bar check below - H4 bars land on 00/04/08/12/16/20
   //--- server time and never on InpFridayCloseHour's default of 21, which
   //--- made this dead code in v1.00 (confirmed: 0 off-bar exits across 218
   //--- real deals in the audit that found this). A weekend gap doesn't wait
   //--- for a bar close either.
   if(FridayCutoff(false))
     {
      bool isBuy;
      if(HavePosition(isBuy)) ClosePosition("FRIDAY");
     }

   //--- v1.05 (Opus full-sweep review): retry a latched, previously-failed
   //--- TK-cross/cloud-break exit on every tick rather than waiting for the
   //--- next H4 bar - up to 4 hours is a long time to hold an unwanted
   //--- position on a rejected close (requote, off-quotes, busy trade context).
   if(g_exitPending)
     {
      bool exitIsBuy;
      if(HavePosition(exitIsBuy))
        {
         if(ClosePosition(InpExitMode == EXIT_CROSS ? "TK_CROSS_RETRY" : "CLOUD_BREAK_RETRY"))
           {
            g_barsInTrade = 0;
            g_exitPending = false;
           }
        }
      else
         g_exitPending = false;
     }

   datetime t0 = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t0 == 0) return;
   if(t0 == g_lastBarTime) return;
   g_lastBarTime = t0;

   if(!HasEnoughHistory()) return;

   ManagePosition();
   TryEnter();
  }
//+------------------------------------------------------------------+
