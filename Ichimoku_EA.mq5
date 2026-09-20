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
//|  v1.06 - PURELY VISUAL. No trading logic touched: CheckEntry(), ShouldExit(),        |
//|  ManagePosition(), TryEnter(), LotSize(), FridayCutoff(), HasEnoughHistory(), the     |
//|  Tenkan/Kijun/Senkou/Donchian math and ComputeADX/RSI/CMF/ATR are byte-for-byte        |
//|  unchanged, and OnTick()'s decision order is unchanged (the two additions there are     |
//|  a between-bar panel refresh that returns exactly where the old early-return did, and    |
//|  a draw call after ManagePosition/TryEnter). The trade set every number above describes  |
//|  is therefore untouched. This brings the file up to the same visual standard as          |
//|  Aurelius/Zenith/Daybreak/AuRebound/Tailwind/Slipstream, which it had none of - it was   |
//|  a headless EA with no panel, no OnTimer, no OnChartEvent and nothing drawn on the       |
//|  chart at all.                                                                            |
//|                                                                                            |
//|  WHAT WAS ADDED                                                                            |
//|  - The Ichimoku itself, drawn as real chart objects: Tenkan-sen, Kijun-sen, the Kumo       |
//|    (Senkou A/B edges plus a filled cloud, forward-displaced InpDisplacement bars,          |
//|    including the leading projection past the current bar) and the Chikou span. The cloud   |
//|    fill uses paired OBJ_TRIANGLEs with OBJPROP_FILL: an EA has no plot buffers, so         |
//|    DRAW_FILLING is unavailable, OBJ_RECTANGLE would fill a bounding box rather than a      |
//|    sloping envelope, and OBJ_CHANNEL only fills between PARALLEL lines - see               |
//|    DrawCloudQuad's own header for the full reasoning, including why MQL5's lack of an      |
//|    alpha channel forces the fill behind the candles in a dark tint.                        |
//|  - Everything drawn reuses the EA's OWN Tenkan/Kijun/SenkouARaw/SenkouBRaw functions,      |
//|    so the drawn cloud cannot drift from the traded cloud.                                   |
//|  - Entry and stop-loss lines while a position is open. The stop is read from the broker,    |
//|    not recomputed, and no line is drawn when InpSafetyStopATR is 0 (still a valid setting). |
//|  - A sectioned, draggable panel: SIGNAL (entry mode, ADX filter state, Tenkan/Kijun,        |
//|    fresh cross, price vs cloud, cloud thickness, future-cloud direction, Chikou, live       |
//|    ADX vs InpADXThreshold, and CheckEntry()'s real current verdict), STRATEGY (exit mode,   |
//|    min hold, safety stop, sizing, spread, Friday-cutoff state), POSITION (direction,        |
//|    entry, volume, floating P/L, bars held vs InpMinHoldBars, the real stop, whether         |
//|    ShouldExit() is true right now, and whether g_exitPending is retrying a failed close)    |
//|    and ACCOUNT (balance/equity/this EA's own floating P/L/magic).                           |
//|  - Family chart theme (neon-blue/white candles on black), an "ICHIMOKU" watermark, and      |
//|    an InpBackgroundBMP input that ships EMPTY: no wallpaper asset exists for this EA, the   |
//|    same situation Zenith was in, so the input is present and inert rather than pointing at  |
//|    an invented file.                                                                        |
//|                                                                                             |
//|  ADX IS A PANEL READOUT, NOT A SUB-WINDOW PLOT - deliberately. An EA cannot create plot     |
//|  buffers, so a sub-window ADX would have to be a ChartIndicatorAdd() of MT5's BUILT-IN      |
//|  iADX, which is not the series this EA filters on (ComputeADX is a manual Wilder port       |
//|  written to match the Python model that selected InpUseADX, and this broker's built-ins     |
//|  have already been caught differing from the textbook definition - see Aurelius v1.36 on    |
//|  iATR). Plotting one number while trading another is the exact drift this visual pass is    |
//|  meant to avoid, so the panel shows the real ComputeADX value against the real threshold.   |
//|                                                                                             |
//|  PERFORMANCE - the traps this portfolio has already paid for, all avoided here:             |
//|  g_skipCosmeticDraws (set once in OnInit from MQL_TESTER && !MQL_VISUAL_MODE) gates every   |
//|  draw INCLUDING EventSetTimer, which is not even started in a non-visual Tester pass; the   |
//|  between-bar panel refresh is throttled to one unique second; the panel updates in place    |
//|  and only reclaims top-of-stack once per new bar (g_panelReclaim); the indicator objects    |
//|  are bounded to InpIchiHistoryBars and purged every bar; and every expensive read the       |
//|  panel displays (ComputeADX, CheckEntry, ShouldExit) is snapshotted ONCE per H4 bar         |
//|  rather than recomputed per refresh. No new per-tick history walk exists anywhere.          |
//|                                                                                             |
//|  NOT COMPILED. MQL5 cannot be compiled in the environment this was written in - the checks  |
//|  run were manual (brace/paren balance, object-prefix collisions, no default arguments on    |
//|  any declaration, a line-by-line diff of the trading functions). Treat as compile-risk,     |
//|  not compile-certified, the same caveat every visual pass in this project ships with.       |
//+------------------------------------------------------------------+
#property copyright "Session build - v1.06"
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

//--- v1.06 VISUAL INPUTS. Every input from here to the end of the input list
//--- is cosmetic only: nothing below is read by CheckEntry/ShouldExit/
//--- ManagePosition/TryEnter/LotSize or by any Ichimoku/ADX/RSI/CMF/ATR
//--- calculation, and every draw they gate sits behind g_skipCosmeticDraws.
input group "=== Dashboard ==="
input bool   InpShowPanel      = true;            // Show the panel
input int    InpPanelDrag      = 1;               // 0 = locked, 1 = draggable
input int    InpPanelX         = 12;              // X offset - family standard
input int    InpPanelY         = 30;              // Y offset - family standard (just below MT5's own symbol header)
input bool   InpPanelBottom    = false;           // Anchor the panel to the BOTTOM left
input int    InpPanelW         = 268;             // Width (grows on its own if a row needs more - see g_panelMinW)
input color  InpPanelBg        = C'13,17,28';     // Panel background (solid) - family standard
input color  InpHeaderBg       = C'28,36,58';     // Header / section background - family standard
input color  InpPanelEdge      = C'0,150,255';    // Border - neon blue, matching Fulcrum/Ratchet/Zenith/Daybreak
input color  InpTitleCol       = C'255,196,84';   // Title text - gold
input color  InpSectionCol     = C'214,226,238';  // Section headings - silver
input color  InpTextCol        = C'150,166,192';  // Labels
input color  InpValCol         = C'236,242,252';  // Values
input color  InpOkCol          = C'0,230,118';    // Met - neon green
input color  InpNoCol          = C'255,61,90';    // Not met - hot red
input color  InpShadowCol      = C'6,8,14';       // Drop shadow
input string InpPanelFont      = "Consolas";      // Font
input int    InpPanelSize      = 8;               // Font size
input string InpBackgroundBMP  = "";              // Background image (.bmp in MQL5\Images). Ships EMPTY: no wallpaper
                                                   // asset exists for Ichimoku (same situation as Zenith_EA.mq5 when
                                                   // it got this treatment) - PBackground() is a clean no-op while
                                                   // this is blank, and no image is invented to fill the gap.
input int    InpBgWidth        = 1290;            // Image width (px) - for centring only
input int    InpBgHeight       = 720;             // Image height (px) - for centring only

input group "=== Chart theme ==="
input bool   InpApplyTheme     = true;            // Recolour the chart to the family scheme
input bool   InpHideTradeMarks = true;            // Hide MT5's own buy/sell/SL/TP arrows and lines (a terminal
                                                   // display setting, not chart objects - ChartSetInteger is the
                                                   // only way to suppress them). The entry/stop lines this EA
                                                   // draws itself replace them.
input color  InpChartBg        = clrBlack;        // Chart background - family standard
input color  InpBullCol        = C'0,150,255';    // Bullish candle - neon blue, family standard
input color  InpBearCol        = clrWhite;        // Bearish candle - white, family standard
input string InpWatermark      = "ICHIMOKU";      // Watermark text (empty = none)
input color  InpWaterCol       = C'18,28,46';     // Watermark colour - dark blue, a tint of the black background
input bool   InpWaterBottom    = true;            // Watermark bottom-right instead of centred
input int    InpWaterSize      = 42;              // Watermark font size
input string InpWaterFont      = "Arial Black";   // Watermark font

input group "=== Ichimoku chart drawing ==="
input bool   InpShowIchimoku   = true;            // Draw Tenkan/Kijun/the cloud/Chikou as chart objects
input int    InpIchiHistoryBars= 400;             // Rolling window of drawn history, in H4 bars (400 = ~66 trading
                                                   // days). Bounded and purged every bar so a long-running live EA
                                                   // never accumulates objects. Deliberately far smaller than
                                                   // Aurelius's 2500: that file is M5 (2500 bars = ~8.7 days),
                                                   // this one is H4, where 400 bars is already ~2.2 months of
                                                   // chart - and each drawn bar here costs more objects (the
                                                   // cloud alone is 4 per bar, see DrawCloudQuad).
input color  InpColTenkan      = clrYellow;       // Tenkan-sen (9) - yellow
input color  InpColKijun       = C'255,20,147';   // Kijun-sen (26) - neon pink
input bool   InpShowChikou     = true;            // Draw the Chikou span (close displaced InpDisplacement back)
input color  InpColChikou      = C'0,255,255';    // Chikou span - neon aqua
input bool   InpShowCloudFill  = true;            // Fill between Senkou A and B (off = edge lines only)
input color  InpColSpanA       = C'0,230,118';    // Senkou Span A edge - neon green
input color  InpColSpanB       = C'255,61,90';    // Senkou Span B edge - hot red
input color  InpColCloudUp     = C'0,58,38';      // Cloud fill when A > B. Deliberately DARK: MQL5 chart objects
                                                   // have no alpha channel, so a filled object is opaque. The fill
                                                   // is drawn with OBJPROP_BACK (behind the candles) in a colour
                                                   // close to InpChartBg, which is what makes it read as a tinted
                                                   // cloud instead of a solid block hiding price. See DrawCloudQuad.
input color  InpColCloudDn     = C'74,12,26';     // Cloud fill when B > A - same dark-tint reasoning
input bool   InpShowTradeLevels= true;            // Draw the OPEN position's entry price and its real stop as
                                                   // horizontal lines (InpHideTradeMarks turns MT5's own off)
input color  InpColEntryLine   = C'150,166,192';  // Entry-price line - silver-grey
input color  InpColStopLine    = C'255,61,90';    // Stop-loss line - hot red

CTrade        trade;
CPositionInfo pos;

datetime g_lastBarTime = 0;
int      g_barsInTrade = 0;   // v1.03: bars elapsed since entry, for InpMinHoldBars
bool     g_exitPending = false;   // v1.05: a close request that failed and must be retried - see ManagePosition

//--- v1.06 cosmetic globals. None of these is read by any trading decision.
//--- Object-name prefixes: this file created NO chart objects before v1.06,
//--- so there is nothing existing to collide with, and "ICH" is unused by
//--- every sibling EA (AUR/FUL/RAT/ZEN/DAY/TWD/SLP).
string   g_pp = "ICHP_";      // panel
string   g_pw = "ICHW_";      // wallpaper + watermark (kept out of the panel wipe)
string   g_pm = "ICHM_";      // per-bar indicator segments, purged to a rolling window
string   g_pl = "ICHL_";      // horizontal price levels (entry / stop) - updated in place, never purged
//--- true for a non-visual Strategy Tester pass (nobody is watching a chart).
//--- Gates EVERY cosmetic draw in this file, including the 1-second timer,
//--- which is what made the same fix take three attempts in Aurelius
//--- (v1.31/v1.32/v1.33) - OnTick gating alone was not enough there because
//--- Strategy Tester also simulates timer events.
bool     g_skipCosmeticDraws = false;
//--- see PRect/PText: reclaim top-of-stack (delete+recreate) only once per
//--- new bar, when a freshly drawn indicator segment could have buried the
//--- panel. Every other refresh updates in place, or the panel visibly
//--- flashes on each live-number update (Aurelius v1.38).
bool     g_panelReclaim = true;
int      g_panelMinW = 0;     // self-learning panel width, applied on the NEXT draw
int      g_panX = -1, g_panY = -1;
bool     g_bgOK = false;
int      g_bgTries = 0;
//--- once-per-bar snapshot of everything the panel displays. The panel is
//--- refreshed up to once per second; ComputeADX alone copies 3 x 144 bars
//--- and runs two Wilder passes, and CheckEntry() can add RSI/CMF on top,
//--- so calling any of them from the draw path would be exactly the
//--- per-second history rescan this project has already had to fix twice
//--- (Aurelius v1.29/v1.31). They are computed ONCE per new bar, into these,
//--- and the panel only ever reads them.
bool     g_snapOK      = false;
bool     g_snapHistOK  = false;
bool     g_snapADXOK   = false;
double   g_snapTenkan  = 0.0, g_snapKijun = 0.0;
double   g_snapSpanA   = 0.0, g_snapSpanB = 0.0;
double   g_snapCloudTop= 0.0, g_snapCloudBot = 0.0;
double   g_snapClose   = 0.0;
double   g_snapADX     = 0.0;
int      g_snapSignal  = 0;   // CheckEntry()'s real result on the last closed bar
int      g_snapCross   = 0;   // raw Tenkan/Kijun cross, before any filter
int      g_snapChikou  = 0;   // +1 clear up, -1 clear down, 0 neither
bool     g_snapExitSig = false;

//--- forward declarations: OnInit() sets the theme and draws the panel,
//--- the indicator lines and the price levels the moment the EA attaches
//--- (the "missing panel until the first tick" bug this project has already
//--- found twice, in Fulcrum and again in Tailwind/Slipstream). No default
//--- argument is used anywhere in this file's visual code - repeating a
//--- default on both a declaration and its definition is a hard error in
//--- some MQL5/C++-family compilers, and Aurelius v1.38 had to fix exactly
//--- that, so the risk is simply avoided here rather than managed.
void   PTheme();
void   PBackground();
void   PWatermark();
void   DrawPanel(const bool reclaim);
void   BackfillIchiLines();
void   UpdateIchiLines();
void   UpdateLevelLines();
void   RefreshPanelSnapshot();
void   CosmeticNewBar();

//+------------------------------------------------------------------+
int OnInit()
  {
   //--- v1.06: decided once, here, and checked by every cosmetic draw in the
   //--- file. A non-visual Strategy Tester pass has no chart anyone can see,
   //--- so every panel/watermark/indicator-object draw is skipped outright -
   //--- the fix this portfolio has had to make (and re-make) three times.
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);

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

   //--- v1.06 visual init. The theme is applied even with the panel switched
   //--- off. Everything else is skipped outright in a non-visual Tester pass.
   PTheme();
   if(!g_skipCosmeticDraws)
     {
      EventSetTimer(1);
      //--- draw the whole rolling window now rather than a one-bar stub per
      //--- line, and show the panel/levels the moment the EA attaches instead
      //--- of waiting for the first tick (the missing-panel-at-attach bug this
      //--- project has already found in Fulcrum, Tailwind and Slipstream).
      RefreshPanelSnapshot();
      //--- PBackground() must run BEFORE any cloud/line object is created:
      //--- MT5 stacks same-layer (OBJPROP_BACK) objects by CREATION ORDER,
      //--- not z-order, so a wallpaper bitmap created AFTER the cloud would
      //--- become the newest back-object and render on top of it, blotting
      //--- the fill out everywhere the bitmap covers - exactly the bug a
      //--- real screenshot caught (cloud only visible at the far edges,
      //--- outside the bitmap's width). DrawPanel() also calls PBackground()
      //--- internally, but only reaches it AFTER BackfillIchiLines() ran -
      //--- too late for the very first draw. Calling it explicitly here
      //--- first is a safe no-op on every call after this one (PBackground()
      //--- returns immediately once g_bgOK is true).
      PBackground();
      BackfillIchiLines();
      UpdateLevelLines();
      DrawPanel(true);
      ChartRedraw(0);
     }
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_pp);   // panel
   ObjectsDeleteAll(0, g_pw);   // wallpaper + watermark
   ObjectsDeleteAll(0, g_pm);   // Ichimoku line/cloud segments
   ObjectsDeleteAll(0, g_pl);   // entry/stop levels
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Push notification on trade open/close, via MT5's own               |
//| SendNotification() - requires this terminal's MetaQuotes ID under   |
//| Tools>Options>Notifications with "Enable Notifications" checked;     |
//| a silent false return otherwise, and SendNotification() does         |
//| nothing at all inside the Strategy Tester regardless of that          |
//| setting, so it's skipped there rather than logged as a failure.        |
//| Purely a notification hook - reads closed deal history only, never    |
//| touches CheckEntry/ShouldExit/ManagePosition/TryEnter or any of the    |
//| g_snap*/g_exitPending/g_barsInTrade state those functions depend on.    |
//+------------------------------------------------------------------+
void NotifyPush(const string text)
  {
   if(MQLInfoInteger(MQL_TESTER)) return;
   if(!SendNotification(text))
      PrintFormat("Ichimoku_EA: SendNotification failed (err %d) - check Tools>Options>Notifications", GetLastError());
  }
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   ulong ticket = trans.deal;
   if(ticket == 0) return;
   if(!HistoryDealSelect(ticket)) return;
   if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != (long)InpMagic) return;
   if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) return;

   ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
   double px = HistoryDealGetDouble(ticket, DEAL_PRICE);
   if(dealEntry == DEAL_ENTRY_IN)
     {
      bool isBuy = (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_BUY;
      NotifyPush(StringFormat("Ichimoku OPEN %s %.2f %s @ %.2f",
                 isBuy ? "BUY" : "SELL", HistoryDealGetDouble(ticket, DEAL_VOLUME), _Symbol, px));
      return;
     }
   if(dealEntry != DEAL_ENTRY_OUT && dealEntry != DEAL_ENTRY_OUT_BY) return;
   double pl = HistoryDealGetDouble(ticket, DEAL_PROFIT)
             + HistoryDealGetDouble(ticket, DEAL_SWAP)
             + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   //--- a CLOSING deal's own DEAL_TYPE is the opposite side of the position
   //--- it closed (closing a BUY position is itself a SELL deal) - invert it
   //--- to report the position's real direction, not the closing action.
   bool wasBuy = (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_SELL;
   NotifyPush(StringFormat("Ichimoku CLOSE %s @ %.2f  P/L: %s$%.2f",
              wasBuy ? "BUY" : "SELL", px, pl >= 0 ? "+" : "-", MathAbs(pl)));
  }
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
//+==================================================================+
//|                                                                  |
//|  v1.06 VISUAL LAYER - everything below this line is cosmetic.     |
//|                                                                  |
//|  Nothing here writes a global the trading logic reads, places or  |
//|  modifies an order, or changes when any signal function is        |
//|  called. The only contact with the strategy code is READ-ONLY:    |
//|  RefreshPanelSnapshot() calls Tenkan/Kijun/SenkouARaw/SenkouBRaw/ |
//|  CloudTop/CloudBot/ComputeADX/CheckEntry/ShouldExit purely to     |
//|  display what they currently return. Drawing the SAME functions   |
//|  the EA trades on (rather than re-deriving the lines from a       |
//|  private copy of the formula) is deliberate: it makes it          |
//|  impossible for the drawn cloud to drift away from the traded     |
//|  cloud, the same reasoning Aurelius's UpdateLevelLines() gives    |
//|  for reusing SRLevels() instead of recomputing the levels.        |
//|                                                                  |
//+==================================================================+
//--- rough monospace-ish width estimate, same formula the rest of the
//--- family's panels use, so row widths stay visually consistent
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
//+------------------------------------------------------------------+
//| Panel primitives. Layout is left-corner based throughout: right    |
//| corners invert the X axis in MT5, which mirrors the whole panel    |
//| off-screen.                                                        |
//+------------------------------------------------------------------+
void PRect(const string id, const int x, const int y, const int w, const int h,
           const color bg, const color edge, const int border)
  {
   string nm = g_pp + id;
   //--- only the background is grabbable, and it must NOT be HIDDEN or MT5
   //--- will not let it be selected, which is what blocks dragging
   bool grab = (InpPanelDrag == 1 && id == "bg");
   bool exists = (ObjectFind(0, nm) >= 0);
   //--- MT5 stacks chart objects by CREATION order, not by ZORDER. An
   //--- indicator segment drawn on a later bar would otherwise end up newer
   //--- than the panel and show through it. Delete-and-recreate makes the
   //--- panel the newest object again - but only when asked (once per new
   //--- bar), since doing it on every live refresh is what made the panel
   //--- visibly flash in Aurelius v1.38. "bg" keeps its identity always, or
   //--- an in-progress drag would be reset mid-motion; the opaque "fl" rect
   //--- drawn straight on top of it is what actually keeps the body solid.
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
//| OBJ_RECTANGLE_LABEL's own BORDER_FLAT border renders unreliably in |
//| this terminal build (observed live across the family as only two   |
//| of four sides drawn), so the panel border is four thin solid-fill  |
//| strips instead - each one an ordinary filled rectangle, the thing  |
//| that does render correctly. Ported from Aurelius_EA.mq5.           |
//+------------------------------------------------------------------+
void PFrame(const string id, const int x, const int y, const int w, const int h,
            const color edge, const int thick)
  {
   PRect(id + "ft", x,             y,             w,     thick, edge, edge, 0);   // top
   PRect(id + "fb", x,             y + h - thick, w,     thick, edge, edge, 0);   // bottom
   PRect(id + "fl", x,             y,             thick, h,     edge, edge, 0);   // left
   PRect(id + "fr", x + w - thick, y,             thick, h,     edge, edge, 0);   // right
  }
//+------------------------------------------------------------------+
void PText(const string id, const int x, const int y, const string txt,
           const color col, const int size, const bool rightAlign,
           const string font)
  {
   string nm = g_pp + id;
   //--- an OBJ_LABEL with empty text renders MT5's default "Label" string.
   //--- This delete is unconditional (not gated by g_panelReclaim) because
   //--- it isn't about stacking - it's a row that genuinely no longer has a
   //--- value (e.g. switching from in-position to flat) and must disappear.
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
//| A row: status dot, label on the left, value right-aligned.         |
//| state: 1 = met (green), 0 = not met (red), -1 = neutral/n-a.       |
//+------------------------------------------------------------------+
void PRow(const string id, const int x, const int y, const int w,
          const string label, const string value, const int state)
  {
   if(label == "" && value == "")
     {
      PText(id + "d", x, y, "", InpTextCol, 0, false, "");
      PText(id + "l", x, y, "", InpTextCol, 0, false, "");
      PText(id + "v", x, y, "", InpTextCol, 0, false, "");
      return;
     }
   color dot = (state == 1) ? InpOkCol : (state == 0) ? InpNoCol : InpTextCol;
   PText(id + "d", x + 10, y, CharToString(108), dot, InpPanelSize + 1, false, "Wingdings");
   PText(id + "l", x + 26, y, label, InpTextCol, 0, false, "");
   PText(id + "v", x + w - 12, y, value, InpValCol, 0, true, "");
   int need = 26 + EstimateTextWidth(label, InpPanelSize) + 16
              + EstimateTextWidth(value, InpPanelSize) + 20;
   if(need > g_panelMinW) g_panelMinW = need;
  }
//+------------------------------------------------------------------+
void PSection(const string id, const int x, const int y, const int w,
              const int rh, const string title)
  {
   //--- band created first, label second, or the band hides the label
   PRect(id + "bar", x + 1, y - 3, w - 2, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x + 10, y, title, InpSectionCol, InpPanelSize, false, "Arial Bold");
  }
//+------------------------------------------------------------------+
//| Wallpaper. InpBackgroundBMP ships EMPTY for this EA - no image     |
//| asset exists for Ichimoku - so this is a clean no-op by default    |
//| and only does anything if someone drops a .bmp into MQL5\Images    |
//| and names it here. The retry counter exists because the terminal   |
//| can refuse the load while the chart is still initialising; it is   |
//| retried from OnTimer(), which (unlike Zenith) this file has.       |
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
     { Print("Ichimoku_EA BG: ObjectCreate failed, error ", GetLastError()); return; }

   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0, nm, OBJPROP_BMPFILE, 0, path);
   int err = GetLastError();
   if(!okSet || err != 0)
     {
      if(g_bgTries <= 3)
         PrintFormat("Ichimoku_EA BG try %d: failed to load \"%s\" set=%s error=%d"
                     " -> file must be at <data folder>\\MQL5\\Images\\%s",
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
   //--- the bitmap is now the newest background object - rebuild the
   //--- watermark once so it sits back on top of it
   if(ObjectFind(0, g_pw + "wm") >= 0) ObjectDelete(0, g_pw + "wm");
   PWatermark();
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Watermark, drawn BEHIND the candles so it tints the empty space    |
//| rather than obscuring price.                                       |
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
void PTheme()
  {
   if(!InpApplyTheme) return;
   ChartSetInteger(0, CHART_COLOR_BACKGROUND,  InpChartBg);
   ChartSetInteger(0, CHART_COLOR_FOREGROUND,  C'138,152,178');
   ChartSetInteger(0, CHART_COLOR_GRID,        C'20,26,40');
   //--- wick colours match the bodies so candles read as one solid shape
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
//+==================================================================+
//|  THE CLOUD                                                        |
//|                                                                   |
//|  "Slot" indexing. A slot is a bar position on the time axis that   |
//|  may be in the FUTURE: slot j >= 0 is the ordinary bar shift j,    |
//|  and slot j < 0 is |j| bar-widths to the right of the forming bar. |
//|  That is what makes the forward-displaced cloud drawable at all -  |
//|  the Kumo that belongs over slot j was computed InpDisplacement    |
//|  bars earlier, exactly as CloudTop()/CloudBot() already define it  |
//|  for the trading logic (max/min of SenkouARaw/SenkouBRaw at        |
//|  shift + InpDisplacement). Re-using those same two functions here  |
//|  means the drawn cloud IS the traded cloud, not a look-alike.      |
//|                                                                   |
//|  The furthest slot that can be drawn from closed-bar data alone is |
//|  j = 1 - InpDisplacement (the spans of the last CLOSED bar), which |
//|  is the standard 25-bars-ahead leading edge. Nothing here ever     |
//|  reads the forming bar's own spans.                               |
//|                                                                   |
//|  A useful property of this indexing: the cloud value at a given    |
//|  absolute TIME does not change as bars advance (slot j at bar N is |
//|  slot j+1 at bar N+1, and SenkouARaw(j+1+disp) at bar N+1 is the   |
//|  same reading as SenkouARaw(j+disp) at bar N). So the forward      |
//|  cloud never has to be redrawn - each new bar only appends ONE new |
//|  leading segment, which is why UpdateIchiLines() is ~7 object      |
//|  creations per bar rather than a full 26-bar repaint.              |
//+==================================================================+
datetime SlotTime(const int j)
  {
   if(j >= 0) return(iTime(_Symbol, PERIOD_CURRENT, j));
   datetime t0 = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t0 == 0) return(0);
   return(t0 + (datetime)((long)(-j) * PeriodSeconds(PERIOD_CURRENT)));
  }
//--- Senkou A/B as they appear OVER slot j (i.e. already displaced).
//--- Same expressions CloudTop()/CloudBot() use, just kept separate
//--- instead of collapsed to max/min, because the fill needs to know
//--- WHICH span is on top (that is what colours a bull vs bear Kumo).
double SlotSpanA(const int j) { return(SenkouARaw(j + InpDisplacement)); }
double SlotSpanB(const int j) { return(SenkouBRaw(j + InpDisplacement)); }
//+------------------------------------------------------------------+
void DrawIchiSeg(const string tag, const datetime tA, const double vA,
                 const datetime tB, const double vB, const color col,
                 const int width, const ENUM_LINE_STYLE style)
  {
   if(tA == 0 || tB == 0) return;
   string nm = g_pm + tag + "_" + IntegerToString((long)tB);
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   if(!ObjectCreate(0, nm, OBJ_TREND, 0, tA, vA, tB, vB)) return;
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_RAY_LEFT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   //--- hidden from the terminal's Object List: there are thousands of
   //--- these, and flooding that dialog is a real usability bug the family
   //--- already hit once (Aurelius v1.38)
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| One bar-width of filled cloud, as a pair of filled triangles.      |
//|                                                                    |
//| WHY TRIANGLES. MQL5 gives an EA no plot buffers, so there is no     |
//| DRAW_FILLING plot available (only a real indicator can declare one) |
//| and no ChartIndicatorAdd() path that lets an EA colour anything.    |
//| Of the chart objects that DO support OBJPROP_FILL - OBJ_RECTANGLE,  |
//| OBJ_TRIANGLE, OBJ_ELLIPSE, OBJ_CHANNEL - only the triangle can fill |
//| a sloping quadrilateral exactly:                                    |
//|   - OBJ_RECTANGLE per bar fills its bounding BOX, so on any sloping |
//|     stretch (which is most of the Kumo) it paints well outside the  |
//|     real span envelope - a visibly fat, stepped cloud.              |
//|   - OBJ_CHANNEL fills between two PARALLEL lines. Senkou A and B    |
//|     are not parallel, so it is simply the wrong primitive.          |
//| So each bar's cloud quad (spanA/spanB at the two ends) is split     |
//| into two triangles that tile it exactly, with no gap or overlap.    |
//|                                                                    |
//| NO ALPHA. MQL5 chart objects have no transparency, so a filled      |
//| object is opaque. Two things make this read as a cloud rather than  |
//| a wall: the fill is drawn with OBJPROP_BACK = true (behind candles, |
//| behind every line drawn here), and InpColCloudUp/Dn default to very |
//| dark tints of the black InpChartBg. The bright Span A/B edge lines  |
//| drawn on top are what actually define the cloud's shape.            |
//|                                                                    |
//| TWIST BARS. Each triangle is coloured by the A-vs-B relationship at |
//| its own bar end, so the colour flips on the correct side of a Kumo  |
//| twist. On the single bar where the spans actually cross, the quad   |
//| is a bow-tie and the two triangles overlap slightly around the      |
//| crossing point - a one-bar artifact a few pixels wide, accepted in  |
//| exchange for not needing to solve for the intersection.             |
//+------------------------------------------------------------------+
void DrawCloudQuad(const datetime tA, const double a0, const double b0,
                   const datetime tB, const double a1, const double b1)
  {
   if(tA == 0 || tB == 0) return;
   string key = IntegerToString((long)tB);
   string n1 = g_pm + "kq1_" + key;
   string n2 = g_pm + "kq2_" + key;
   if(ObjectFind(0, n1) >= 0) ObjectDelete(0, n1);
   if(ObjectFind(0, n2) >= 0) ObjectDelete(0, n2);
   color cRight = (a1 >= b1) ? InpColCloudUp : InpColCloudDn;
   color cLeft  = (a0 >= b0) ? InpColCloudUp : InpColCloudDn;
   if(ObjectCreate(0, n1, OBJ_TRIANGLE, 0, tA, a0, tB, a1, tB, b1))
     {
      ObjectSetInteger(0, n1, OBJPROP_COLOR, cRight);
      ObjectSetInteger(0, n1, OBJPROP_FILL, true);
      ObjectSetInteger(0, n1, OBJPROP_BACK, true);
      ObjectSetInteger(0, n1, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, n1, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, n1, OBJPROP_HIDDEN, true);
     }
   if(ObjectCreate(0, n2, OBJ_TRIANGLE, 0, tA, a0, tB, b1, tA, b0))
     {
      ObjectSetInteger(0, n2, OBJPROP_COLOR, cLeft);
      ObjectSetInteger(0, n2, OBJPROP_FILL, true);
      ObjectSetInteger(0, n2, OBJPROP_BACK, true);
      ObjectSetInteger(0, n2, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, n2, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, n2, OBJPROP_HIDDEN, true);
     }
  }
//+------------------------------------------------------------------+
//| One slot's worth of cloud: the two edge lines plus (optionally)    |
//| the fill between them.                                             |
//+------------------------------------------------------------------+
void DrawCloudSlot(const int jOld, const int jNew)
  {
   datetime tA = SlotTime(jOld), tB = SlotTime(jNew);
   if(tA == 0 || tB == 0) return;
   double a0 = SlotSpanA(jOld), b0 = SlotSpanB(jOld);
   double a1 = SlotSpanA(jNew), b1 = SlotSpanB(jNew);
   if(InpShowCloudFill) DrawCloudQuad(tA, a0, b0, tB, a1, b1);
   //--- edges last, so they are created AFTER the fill and therefore
   //--- render on top of it (creation order, not ZORDER - see PRect)
   DrawIchiSeg("sa", tA, a0, tB, a1, InpColSpanA, 1, STYLE_SOLID);
   DrawIchiSeg("sb", tA, b0, tB, b1, InpColSpanB, 1, STYLE_SOLID);
  }
//+------------------------------------------------------------------+
//| Sweeps every indicator object older than the rolling window, so a  |
//| long-running live EA cannot accumulate chart objects forever. Both |
//| object types this file creates under g_pm are checked. Objects in  |
//| the forward cloud carry FUTURE anchor times, which are always      |
//| newer than the cutoff, so they are never swept early - they simply |
//| age into the historical window as bars arrive.                     |
//+------------------------------------------------------------------+
void PurgeOldIchiLines(const datetime latestBarTime)
  {
   if(latestBarTime == 0) return;
   datetime cutoff = latestBarTime
                     - (datetime)((long)InpIchiHistoryBars * PeriodSeconds(PERIOD_CURRENT));
   int types[2]; types[0] = (int)OBJ_TREND; types[1] = (int)OBJ_TRIANGLE;
   for(int t = 0; t < 2; t++)
     {
      int ot = types[t];
      for(int i = ObjectsTotal(0, 0, ot) - 1; i >= 0; i--)
        {
         string nm = ObjectName(0, i, 0, ot);
         if(StringFind(nm, g_pm) != 0) continue;
         datetime at = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
         if(at != 0 && at < cutoff) ObjectDelete(0, nm);
        }
     }
  }
//+------------------------------------------------------------------+
//| Called once per new bar. Only the newest segment of each line is   |
//| drawn - the rest of the window is already on the chart from        |
//| BackfillIchiLines() or from previous bars.                         |
//+------------------------------------------------------------------+
void UpdateIchiLines()
  {
   if(!InpShowIchimoku) return;
   if(!HasEnoughHistory()) return;
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, 2);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(tA == 0 || tB == 0) return;

   //--- Tenkan / Kijun: plain, undisplaced, closed bars only
   DrawIchiSeg("tk", tA, Tenkan(2), tB, Tenkan(1), InpColTenkan, 2, STYLE_SOLID);
   DrawIchiSeg("kj", tA, Kijun(2),  tB, Kijun(1),  InpColKijun,  2, STYLE_SOLID);

   //--- the cloud's new LEADING edge, InpDisplacement-1 bars to the right of
   //--- the forming bar. Everything behind it was drawn on an earlier bar and
   //--- is still correct (see the slot-indexing note above).
   DrawCloudSlot(2 - InpDisplacement, 1 - InpDisplacement);

   //--- Chikou: the close displaced InpDisplacement bars BACK, so the newest
   //--- point it can have sits at shift InpDisplacement+1 and plots the close
   //--- of shift 1. This is the same comparison the BREAKOUT_FULL entry and
   //--- InpRequireChikou make (close now vs the bar InpDisplacement back),
   //--- just drawn instead of tested.
   if(InpShowChikou)
     {
      int sOld = InpDisplacement + 2, sNew = InpDisplacement + 1;
      datetime cA = iTime(_Symbol, PERIOD_CURRENT, sOld);
      datetime cB = iTime(_Symbol, PERIOD_CURRENT, sNew);
      double vA = iClose(_Symbol, PERIOD_CURRENT, sOld - InpDisplacement);
      double vB = iClose(_Symbol, PERIOD_CURRENT, sNew - InpDisplacement);
      if(vA > 0.0 && vB > 0.0)
         DrawIchiSeg("ch", cA, vA, cB, vB, InpColChikou, 1, STYLE_SOLID);
     }
   PurgeOldIchiLines(tB);
  }
//+------------------------------------------------------------------+
//| Called ONCE from OnInit. UpdateIchiLines() only ever appends one   |
//| bar, so without this a fresh attach would show four one-bar stubs  |
//| and take InpIchiHistoryBars H4 bars (~66 days) to fill the window  |
//| the input claims to show - the exact gap Aurelius v1.38 had to add |
//| BackfillMALines() for.                                             |
//|                                                                    |
//| The Tenkan/Kijun pass carries each bar's value into the next       |
//| iteration instead of recomputing it for both ends of every         |
//| segment, halving that loop's Donchian work. The cloud pass does    |
//| NOT - it goes through DrawCloudSlot() so that the backfilled cloud |
//| and the per-bar cloud are produced by exactly the same code path,  |
//| at the cost of evaluating each slot's spans twice. That is a       |
//| deliberate trade: this runs once, at attach, only when a human is  |
//| actually looking at a chart (never in a non-visual Tester pass),   |
//| and a second code path for the same geometry is how a drawn cloud  |
//| starts quietly disagreeing with the traded one.                    |
//+------------------------------------------------------------------+
void BackfillIchiLines()
  {
   if(!InpShowIchimoku) return;
   if(!HasEnoughHistory()) return;
   int avail = Bars(_Symbol, PERIOD_CURRENT);
   //--- deepest history any drawn value reaches: a cloud slot at shift s
   //--- reads spans at s + InpDisplacement, and SenkouBRaw walks another
   //--- InpSenkouB bars back from there
   int n = MathMin(InpIchiHistoryBars, avail - (InpDisplacement + InpSenkouB + 4));
   if(n < 2) return;

   //--- Tenkan / Kijun
   double tPrev = Tenkan(n + 1), kPrev = Kijun(n + 1);
   for(int s = n; s >= 1; s--)
     {
      datetime tA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
      datetime tB = iTime(_Symbol, PERIOD_CURRENT, s);
      double tNow = Tenkan(s), kNow = Kijun(s);
      if(tA != 0 && tB != 0)
        {
         DrawIchiSeg("tk", tA, tPrev, tB, tNow, InpColTenkan, 2, STYLE_SOLID);
         DrawIchiSeg("kj", tA, kPrev, tB, kNow, InpColKijun,  2, STYLE_SOLID);
        }
      tPrev = tNow; kPrev = kNow;
     }

   //--- the cloud, from the oldest drawn slot all the way out to the
   //--- forward-projected leading edge at slot 1 - InpDisplacement
   for(int j = n; j >= 1 - InpDisplacement; j--)
      DrawCloudSlot(j + 1, j);

   //--- Chikou
   if(InpShowChikou)
     {
      for(int s = n; s >= InpDisplacement + 1; s--)
        {
         datetime cA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
         datetime cB = iTime(_Symbol, PERIOD_CURRENT, s);
         if(cA == 0 || cB == 0) continue;
         double vA = iClose(_Symbol, PERIOD_CURRENT, s + 1 - InpDisplacement);
         double vB = iClose(_Symbol, PERIOD_CURRENT, s - InpDisplacement);
         if(vA <= 0.0 || vB <= 0.0) continue;
         DrawIchiSeg("ch", cA, vA, cB, vB, InpColChikou, 1, STYLE_SOLID);
        }
     }
  }
//+------------------------------------------------------------------+
//| Entry / stop horizontal lines for an OPEN position.                |
//|                                                                    |
//| A stop doesn't move bar to bar, so these are a fixed pair of        |
//| OBJ_HLINEs updated IN PLACE, not per-bar segments - there is        |
//| nothing here for PurgeOldIchiLines to sweep, and updating rather    |
//| than recreating keeps them from re-burying the panel every bar.     |
//|                                                                    |
//| The stop is read from the BROKER (pos.StopLoss()), not recomputed   |
//| from InpSafetyStopATR, so the line is the stop that actually        |
//| exists. With InpSafetyStopATR = 0.0 (the original validated         |
//| no-stop behaviour, still a supported setting) there IS no stop and  |
//| no line is drawn - never a line at price 0.                         |
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
void UpdateLevelLines()
  {
   if(!InpShowTradeLevels)
     { DeleteLevelLine("entry"); DeleteLevelLine("sl"); return; }
   double opx = 0.0, sl = 0.0;
   bool found = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      opx = pos.PriceOpen();
      sl  = pos.StopLoss();      // 0.0 when InpSafetyStopATR is off
      found = true;
      break;                     // this EA runs one position at a time
     }
   if(!found)
     { DeleteLevelLine("entry"); DeleteLevelLine("sl"); return; }
   DrawLevelLine("entry", opx, InpColEntryLine, STYLE_SOLID, 1);
   if(sl > 0.0) DrawLevelLine("sl", sl, InpColStopLine, STYLE_DASH, 1);
   else         DeleteLevelLine("sl");
  }
//+------------------------------------------------------------------+
//| This EA's own floating P/L (its magic/symbol only), so the panel   |
//| never mixes in another EA sharing the same account. Bounded by     |
//| PositionsTotal() - no history scan, unlike the per-second deal     |
//| rescan this project had to remove from Aurelius's panel (v1.31).   |
//+------------------------------------------------------------------+
double MyFloatingPL()
  {
   double sum = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      sum += pos.Profit() + pos.Swap();
     }
   return(sum);
  }
//+------------------------------------------------------------------+
//| Once per new bar: capture everything the panel shows.              |
//|                                                                    |
//| Strictly read-only. CheckEntry() and ShouldExit() are both pure    |
//| functions of price history (verified: neither writes a global nor  |
//| touches an order), so calling them here to DISPLAY the live signal |
//| cannot change what the EA trades - and displaying their real       |
//| return value, rather than a re-implementation of the conditions,   |
//| means the panel can never disagree with the EA about whether a     |
//| signal exists.                                                     |
//|                                                                    |
//| Called only from CosmeticNewBar(), i.e. never in a non-visual      |
//| Tester pass, and never more than once per H4 bar.                  |
//+------------------------------------------------------------------+
void RefreshPanelSnapshot()
  {
   g_snapOK = false; g_snapADXOK = false;
   g_snapSignal = 0; g_snapCross = 0; g_snapChikou = 0; g_snapExitSig = false;
   g_snapHistOK = HasEnoughHistory();
   if(!g_snapHistOK) return;

   double tNow = Tenkan(1),  kNow = Kijun(1);
   double tPrv = Tenkan(2),  kPrv = Kijun(2);
   g_snapTenkan   = tNow;
   g_snapKijun    = kNow;
   g_snapSpanA    = SenkouARaw(1);
   g_snapSpanB    = SenkouBRaw(1);
   g_snapCloudTop = CloudTop(1);
   g_snapCloudBot = CloudBot(1);
   g_snapClose    = iClose(_Symbol, PERIOD_CURRENT, 1);
   g_snapOK       = true;

   if(tNow > kNow && tPrv <= kPrv)      g_snapCross =  1;
   else if(tNow < kNow && tPrv >= kPrv) g_snapCross = -1;

   double closeBack = iClose(_Symbol, PERIOD_CURRENT, 1 + InpDisplacement);
   if(closeBack > 0.0)
      g_snapChikou = (g_snapClose > closeBack) ? 1 : ((g_snapClose < closeBack) ? -1 : 0);

   double adxVal;
   g_snapADXOK = ComputeADX(1, InpADXPeriod, adxVal);
   g_snapADX   = g_snapADXOK ? adxVal : 0.0;

   g_snapSignal = CheckEntry();

   bool isBuy;
   if(HavePosition(isBuy)) g_snapExitSig = ShouldExit(isBuy);
  }
//+------------------------------------------------------------------+
//| The panel.                                                         |
//|                                                                    |
//| Row set is built for what THIS EA actually does - an H4 swing      |
//| system that trades every few days - not for a per-second scalper:  |
//| the SIGNAL block is the Ichimoku state that decides an entry, the  |
//| POSITION block leans on hold-time and exit state rather than tick  |
//| P&L churn, and there is no "today's realized P&L" row because this |
//| file tracks no such figure (inventing one would be a new feature,  |
//| not a visual pass - the same call made for Zenith).                |
//+------------------------------------------------------------------+
void DrawPanel(const bool reclaim)
  {
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }
   g_panelReclaim = reclaim;

   PBackground();
   PWatermark();

   bool isBuy = false;
   bool inPos = HavePosition(isBuy);

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;                 // re-measured this cycle, used by the NEXT one
   int rh  = InpPanelSize + 11;
   int hdr = rh + 14;
   //--- Height is computed, not guessed, and re-derived directly against the
   //--- literal ty += sequence below:
   //---   a0                                    =  1
   //---   SIGNAL   : 1 section + 10 rows (g1-g10) = 11
   //---   STRATEGY : 1 section +  6 rows (d1-d6)  =  7
   //---   POSITION : 1 section +  7 rows (p1-p7)  =  8   (in position)
   //---              1 section +  4 rows (p1-p4)  =  5   (flat; p5-p7 are
   //---                                                   blanked, not laid out)
   //---   ACCOUNT  : 1 section +  4 rows (q1-q4)  =  5
   //---   => 32 in position, 29 flat. (Hand-recounted against the literal
   //--- ty += sequence: a first pass of this file had 31/28, which under-sized
   //--- the frame by one row and let the last ACCOUNT row render outside it -
   //--- the identical off-by-one Aurelius v1.37 found in its own ROWS constant.)
   //--- GAPS is the number of "+ 6" extras: after a0, after each of the four
   //--- section headings, and after the last row of the first three sections
   //--- = 8. Sized to whichever branch is actually drawn, so the flat panel
   //--- doesn't carry three rows of dead space.
   const int ROWS = inPos ? 32 : 29;
   const int GAPS = 8;
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH  = hdr + 10 + ROWS*rh + GAPS*6 + 12;
   int guard  = 0;
   //--- autofit: shrink the row height (to an 11px floor) rather than let the
   //--- panel run off the bottom of a short window
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     {
      rh--; guard++;
      hdr   = rh + 14;
      bodyH = hdr + 10 + ROWS*rh + GAPS*6 + 12;
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

   //--- shadow -> draggable body -> opaque fill -> border -> header band.
   //--- The "fl" fill is what keeps the body solid: "bg" cannot reclaim
   //--- top-of-stack without breaking dragging (see PRect).
   PRect("sh", x + 4, y + 4, w, bodyH, InpShadowCol, InpShadowCol, 0);
   PRect("bg", x, y, w, bodyH, InpPanelBg, InpPanelBg, 0);
   PRect("fl", x + 2, y + 2, w - 4, bodyH - 4, InpPanelBg, InpPanelBg, 0);
   PFrame("bd", x, y, w, bodyH, InpPanelEdge, 2);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);

   int ty = y + 9;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "ICHIMOKU", InpTextCol, InpPanelSize, true, "");
   ty = y + hdr + 10;

   bool algo = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) &&
               MQLInfoInteger(MQL_TRADE_ALLOWED);
   PRow("a0", x, ty, w, "algo trading", algo ? "ON" : "OFF", algo ? 1 : 0);
   ty += rh + 6;

   //--- signal ------------------------------------------------------
   bool plain = (InpEntryMode == ENTRY_PLAIN);
   PSection("s1", x, ty, w, rh, "SIGNAL"); ty += rh + 6;
   PRow("g1", x, ty, w, "entry mode", plain ? "PLAIN" : "BREAKOUT", -1); ty += rh;
   PRow("g2", x, ty, w, "ADX filter",
        !plain ? "n/a (breakout)" : (InpUseADX ? "> " + DoubleToString(InpADXThreshold, 1) : "off"),
        (plain && InpUseADX) ? 1 : -1); ty += rh;
   PRow("g3", x, ty, w, "tenkan vs kijun",
        !g_snapOK ? "-" : (g_snapTenkan > g_snapKijun ? "T > K" :
                          (g_snapTenkan < g_snapKijun ? "T < K" : "T = K")), -1); ty += rh;
   PRow("g4", x, ty, w, "fresh TK cross",
        !g_snapOK ? "-" : (g_snapCross == 1 ? "UP" : (g_snapCross == -1 ? "DOWN" : "no")),
        !g_snapOK ? -1 : (g_snapCross != 0 ? 1 : 0)); ty += rh;
   //--- both PLAIN and BREAKOUT_FULL require price to be clear of the cloud,
   //--- so "inside" is a genuine no-trade state worth flagging red
   string pvc = "-";
   int    pvcState = -1;
   if(g_snapOK)
     {
      if(g_snapClose > g_snapCloudTop)      { pvc = "ABOVE";  pvcState = 1; }
      else if(g_snapClose < g_snapCloudBot) { pvc = "BELOW";  pvcState = 1; }
      else                                  { pvc = "INSIDE"; pvcState = 0; }
     }
   PRow("g5", x, ty, w, "price vs cloud", pvc, pvcState); ty += rh;
   PRow("g6", x, ty, w, "cloud thickness",
        !g_snapOK ? "-" : DoubleToString(g_snapCloudTop - g_snapCloudBot, 2), -1); ty += rh;
   //--- the FORWARD cloud's direction (Senkou A vs B as computed on the last
   //--- closed bar) - BREAKOUT_FULL requires it to match the trade direction
   PRow("g7", x, ty, w, "future cloud",
        !g_snapOK ? "-" : (g_snapSpanA > g_snapSpanB ? "BULL" : "BEAR"), -1); ty += rh;
   PRow("g8", x, ty, w, "chikou vs " + IntegerToString(InpDisplacement) + " back",
        !g_snapOK ? "-" : (g_snapChikou == 1 ? "clear up" :
                          (g_snapChikou == -1 ? "clear down" : "level")),
        (plain && !InpRequireChikou) ? -1 : (g_snapChikou != 0 ? 1 : 0)); ty += rh;
   //--- ADX(14) on the last closed bar, from this EA's OWN ComputeADX - not
   //--- MT5's iADX. That distinction matters: this file computes ADX manually
   //--- specifically to match the Python model that selected InpUseADX, and
   //--- this broker's built-in indicators have already been proven to differ
   //--- from the textbook Wilder definition elsewhere in this portfolio
   //--- (Aurelius v1.36, iATR turned out to be an SMA of True Range). Showing
   //--- the built-in here would display a number the EA does not filter on.
   //--- Same reasoning rules out a sub-window ADX plot: an EA has no plot
   //--- buffers, so a sub-window would have to be a ChartIndicatorAdd() of
   //--- the BUILT-IN iADX - a different series from the one being tested
   //--- against InpADXThreshold. A panel readout of the real value, with the
   //--- pass/fail dot against the real threshold, is the honest version.
   string adxTxt = "-";
   int    adxState = -1;
   if(!plain)                 adxTxt = "n/a";
   else if(!InpUseADX)        adxTxt = "off";
   else if(!g_snapADXOK)      { adxTxt = "unavailable"; adxState = 0; }
   else
     {
      adxTxt   = DoubleToString(g_snapADX, 1) + " / " + DoubleToString(InpADXThreshold, 1);
      adxState = (g_snapADX > InpADXThreshold) ? 1 : 0;
     }
   PRow("g9", x, ty, w, "ADX(" + IntegerToString(InpADXPeriod) + ")", adxTxt, adxState); ty += rh;
   PRow("g10", x, ty, w, "signal now",
        !g_snapOK ? "-" : (g_snapSignal == 1 ? "BUY" : (g_snapSignal == -1 ? "SELL" : "none")),
        !g_snapOK ? -1 : (g_snapSignal != 0 ? 1 : 0)); ty += rh + 6;

   //--- strategy ----------------------------------------------------
   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   PSection("s2", x, ty, w, rh, "STRATEGY"); ty += rh + 6;
   PRow("d1", x, ty, w, "exit on",
        InpExitMode == EXIT_CROSS ? "TK cross" : "cloud break", -1); ty += rh;
   PRow("d2", x, ty, w, "min hold",
        InpMinHoldBars > 0 ? IntegerToString(InpMinHoldBars) + " bars" : "off",
        InpMinHoldBars > 0 ? 1 : -1); ty += rh;
   PRow("d3", x, ty, w, "safety stop",
        InpSafetyStopATR > 0.0 ? DoubleToString(InpSafetyStopATR, 1) + " ATR" : "none",
        InpSafetyStopATR > 0.0 ? 1 : 0); ty += rh;
   PRow("d4", x, ty, w, "sizing",
        InpLotMode == LOT_FIXED ? DoubleToString(InpLots, 2) + " fixed"
                                : DoubleToString(InpRiskPct, 1) + "% risk", -1); ty += rh;
   PRow("d5", x, ty, w, "spread", IntegerToString((int)spreadPts),
        (InpMaxSpreadPoints > 0 && spreadPts > InpMaxSpreadPoints) ? 0 : 1); ty += rh;
   //--- the Friday flatten is this config's DOMINANT exit (about two thirds of
   //--- real exits per the v1.02 header note), so its live state earns a row
   bool friFlat  = FridayCutoff(false);
   bool friNoNew = FridayCutoff(true);
   PRow("d6", x, ty, w, "friday cutoff",
        !InpCloseFriday ? "off" :
        (friFlat ? "FLATTEN NOW" :
        (friNoNew ? "no new entries" : IntegerToString(InpFridayCloseHour) + ":00 fri")),
        !InpCloseFriday ? -1 : ((friFlat || friNoNew) ? 0 : 1)); ty += rh + 6;

   //--- position ----------------------------------------------------
   PSection("s3", x, ty, w, rh, "POSITION"); ty += rh + 6;
   if(inPos)
     {
      double prof = 0.0, vol = 0.0, opx = 0.0, sl = 0.0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         if(!pos.SelectByIndex(i)) continue;
         if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
         prof += pos.Profit() + pos.Swap();
         vol = pos.Volume(); opx = pos.PriceOpen(); sl = pos.StopLoss();
        }
      PRow("p1", x, ty, w, isBuy ? "LONG" : "SHORT",
           DoubleToString(opx, _Digits), 1); ty += rh;
      PRow("p2", x, ty, w, "volume", DoubleToString(vol, 2), -1); ty += rh;
      PRow("p3", x, ty, w, "floating P/L", StringFormat("%+.2f", prof),
           prof >= 0 ? 1 : 0); ty += rh;
      //--- bars held vs the minimum hold gate. Amber-free palette, so the
      //--- dot is simply "gate open" (green) or "still blocked" (red).
      PRow("p4", x, ty, w, "bars held",
           IntegerToString(g_barsInTrade) + " / " + IntegerToString(InpMinHoldBars),
           (g_barsInTrade >= InpMinHoldBars) ? 1 : 0); ty += rh;
      PRow("p5", x, ty, w, "stop",
           sl > 0.0 ? DoubleToString(sl, _Digits) : "none", sl > 0.0 ? 1 : 0); ty += rh;
      //--- "exit signal" is ShouldExit()'s real current value. Combined with
      //--- the row above it this explains the one genuinely confusing state
      //--- this EA can be in: an exit cross that fires inside the min-hold
      //--- window is CANCELLED, not deferred (see InpMinHoldBars).
      PRow("p6", x, ty, w, "exit signal",
           g_snapExitSig ? "YES" : "no", g_snapExitSig ? 0 : 1); ty += rh;
      //--- g_exitPending means a close request FAILED and is being retried on
      //--- every tick - the position is meant to be gone. Worth its own row.
      PRow("p7", x, ty, w, "exit retry",
           g_exitPending ? "RETRYING" : "no", g_exitPending ? 0 : 1); ty += rh + 6;
     }
   else
     {
      PRow("p1", x, ty, w, "state", "FLAT", -1); ty += rh;
      PRow("p2", x, ty, w, "waiting for",
           plain ? "TK cross + cloud" : "kumo breakout", -1); ty += rh;
      PRow("p3", x, ty, w, "next lot", DoubleToString(InpLots, 2), -1); ty += rh;
      PRow("p4", x, ty, w, "history",
           g_snapHistOK ? "ready" : "warming up", g_snapHistOK ? 1 : 0); ty += rh + 6;
      //--- the in-position branch is three rows taller; without clearing these
      //--- explicitly they would survive on the chart at stale y-coordinates
      //--- after a close and land on top of the ACCOUNT section (the exact
      //--- stale-row bug found in Aurelius's own panel during its v1.38 review)
      PRow("p5", x, ty, w, "", "", -1);
      PRow("p6", x, ty, w, "", "", -1);
      PRow("p7", x, ty, w, "", "", -1);
     }

   //--- account -----------------------------------------------------
   PSection("s4", x, ty, w, rh, "ACCOUNT"); ty += rh + 6;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double myFloat = MyFloatingPL();
   PRow("q1", x, ty, w, "balance", DoubleToString(bal, 2), -1); ty += rh;
   PRow("q2", x, ty, w, "equity", DoubleToString(eq, 2), eq >= bal ? 1 : 0); ty += rh;
   PRow("q3", x, ty, w, "floating (mine)", StringFormat("%+.2f", myFloat),
        myFloat == 0.0 ? -1 : (myFloat > 0.0 ? 1 : 0)); ty += rh;
   PRow("q4", x, ty, w, "magic", IntegerToString((long)InpMagic), -1); ty += rh;

   //--- if the row count ever drifts from ROWS, say so in the log instead of
   //--- silently clipping the panel
   static int warned = 0;
   int used = ty + 12 - y;
   if(used > bodyH && warned < 3)
     { warned++; PrintFormat("Ichimoku_EA panel: content %d px vs frame %d px", used, bodyH); }
  }
//+------------------------------------------------------------------+
//| The once-per-new-bar cosmetic pass. Indicator lines and price      |
//| levels are drawn BEFORE the panel: MT5 stacks by creation order,   |
//| so the panel has to be the last thing created to stay on top, and  |
//| reclaim = true here is the one draw per bar that re-creates its    |
//| objects to achieve that.                                           |
//+------------------------------------------------------------------+
void CosmeticNewBar()
  {
   if(g_skipCosmeticDraws) return;
   RefreshPanelSnapshot();
   UpdateIchiLines();
   UpdateLevelLines();
   DrawPanel(true);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Timer: keeps the panel's live numbers moving when ticks are thin   |
//| (an H4 gold system spends most of its life between bars). Never    |
//| started at all in a non-visual Tester pass - Strategy Tester DOES  |
//| simulate timer events, and a timer-driven panel redraw is exactly  |
//| what was still costing hours of backtest time in Aurelius after    |
//| two earlier attempts at this same fix (v1.31/v1.32) had only       |
//| gated OnTick. OnTimer() early-returns as a second line of defence. |
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(g_skipCosmeticDraws) return;
   PBackground();                  // retries until the image loads, if one is set
   if(!InpShowPanel) return;
   //--- reclaim = false: update the existing objects' values in place. A full
   //--- delete-and-recreate once a second is what made the panel visibly
   //--- flash in Aurelius v1.38.
   DrawPanel(false);
   //--- forcing a chart redraw on a fixed clock fights the user's own
   //--- scrolling and reads as flicker on its own, so only do it when a
   //--- position is open and the floating P/L genuinely needs to look live
   bool isBuy;
   if(HavePosition(isBuy)) ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Dragging the panel background moves the whole panel.               |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam,
                  const string &sparam)
  {
   if(g_skipCosmeticDraws) return;
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_pp + "bg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      DrawPanel(false);            // reposition only - reclaiming mid-drag is jarring
      ChartRedraw(0);
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      //--- MT5 raises CHART_CHANGE for plain scrolling and panning too, not
      //--- just resizing - redrawing on every one of those is what caused
      //--- flashing-while-scrolling elsewhere in the family. Guarded on an
      //--- actual width/height change.
      static int lastW = -1, lastH = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lastW || nh != lastH)
        {
         lastW = nw; lastH = nh;
         g_bgOK = false; g_bgTries = 0;
         PBackground();
         PWatermark();
         if(InpPanelBottom)
           {
            g_panX = -1;           // re-anchor against the new height
            DrawPanel(false);
           }
         ChartRedraw(0);
        }
     }
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
   if(t0 == g_lastBarTime)
     {
      //--- v1.06 (cosmetic only - every path here still returns exactly where
      //--- the old `if(t0 == g_lastBarTime) return;` did, so no trading
      //--- decision is reached any earlier or later than before). Keeps the
      //--- panel's live numbers moving between H4 bars, throttled to once per
      //--- unique second and skipped entirely when nobody is watching: an
      //--- unthrottled per-tick panel redraw is precisely the bug that cost
      //--- this project multi-hour real-tick backtests three times over.
      if(g_skipCosmeticDraws) return;
      static datetime lastPanel = 0;
      if(InpShowPanel && TimeCurrent() != lastPanel)
        {
         lastPanel = TimeCurrent();
         //--- reclaim = false: values updated in place, no delete-and-recreate,
         //--- so the panel does not flash on every refresh. No snapshot refresh
         //--- either - the Ichimoku/ADX readings only change on a new bar, and
         //--- recomputing them per second would be a per-second history rescan.
         DrawPanel(false);
         bool isBuyNow;
         if(HavePosition(isBuyNow)) ChartRedraw(0);
        }
      return;
     }
   g_lastBarTime = t0;

   if(!HasEnoughHistory()) { CosmeticNewBar(); return; }

   ManagePosition();
   TryEnter();

   //--- v1.06: drawn AFTER the trading decisions, so a position opened or
   //--- closed on this bar is already reflected in the panel and in the
   //--- entry/stop lines rather than showing a bar-old state.
   CosmeticNewBar();
  }
//+------------------------------------------------------------------+
