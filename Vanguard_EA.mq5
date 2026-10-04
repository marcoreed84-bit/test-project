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
//|                                                                    |
//|  v1.04 ADDS A STALE EXIT (InpUseStaleExit/InpStaleBars/             |
//|  InpStaleMinProfitATR below): cuts a trade loose early - at         |
//|  whatever it's currently worth - if it's shown no real progress     |
//|  after InpStaleBars, instead of waiting for the full 4.0xATR safety |
//|  stop. Directly answered the user's own question ("is there really  |
//|  no way to cut drawdown") - tested honestly against several ideas   |
//|  that DIDN'T work first (partial profit-taking made concentration   |
//|  worse not better; breakeven stop-move destroyed net AND drawdown   |
//|  both; a joint sweep with a tightened stop added nothing beyond     |
//|  stale-exit alone and either broke top-20 preservation or worsened  |
//|  DD despite better net - see research/aurelius/vanguard_dd_*        |
//|  and vanguard_m5_joint_sweep_test.py). InpStaleBars=225 (~18.75h on  |
//|  M5) is a REAL, INDEPENDENTLY-DERIVED value, not shared with the    |
//|  M15 file's own InpStaleBars=75 (also ~18.75h - the two fresh       |
//|  sweeps landed on the same real-world time window without being     |
//|  assumed to, a reassuring cross-check, not a coincidence forced by   |
//|  a naive bar-count rescale).                                        |
//|                                                                    |
//|  Python-validated (+VWAP+S/R+stale-exit, same k=100/sl=4.0xATR):    |
//|  net=2928.67 (was 2989.87, -2.0%), PF 1.570->1.587, closed DD       |
//|  $383.64->$338.48 (-11.8%), floating DD $459.48->$416.96 (-9.3%),   |
//|  walk-forward 3/5->4/5 blocks, random-direction percentile          |
//|  99.7->100.0. All 20 of the real MT5 trades that carry Vanguard's   |
//|  entire actual profitability are preserved - explicitly checked,    |
//|  not assumed, per the user's own direct requirement. NOT yet run    |
//|  through a real MT5 Strategy Tester - needs that before this        |
//|  specific number is trusted the way v1.00's fixed-lot numbers are.  |
//|                                                                    |
//|  VISUAL AUDIT (2026-09-24), Opus review - CHECKED, NO ISSUE FOUND,   |
//|  #property version stays 1.04. Re-verified by hand: ROWS/GAPS (26     |
//|  in-position / 25 flat, GAPS=10) against the literal ty+= sequence;    |
//|  the chart-height auto-shrink loop; draw order (UpdateSignalLines()/    |
//|  UpdateVWAPLine()/UpdateLevelLines() before DrawPanel(), panel always    |
//|  last); and PBackground()/PWatermark() are already drawn BEFORE the       |
//|  InpShowPanel early-out in this file (this is the already-correct          |
//|  order Aurelius_EA.mq5/Aurelius_M15_EA.mq5/Meridian_EA.mq5/Ratchet_EA.mq5   |
//|  were all found missing today and fixed to match). No indicator label        |
//|  in this file hardcodes a period/method - "descending line"/"ascending        |
//|  line"/"breakout this bar" describe the trendline signal generically,         |
//|  not a tunable MA period, so there is nothing here that can go stale the        |
//|  way Aurelius_EA.mq5's MA-period labels just did.                                |
//+------------------------------------------------------------------+
//|  v1.05: InpUseGivebackExit added (default OFF, Python-only so far -      |
//|  needs a real MT5 Strategy Tester run before being trusted the way the    |
//|  shipped defaults are). Cuts a trade at market once it built a peak        |
//|  floating profit >= InpGivebackMinPeak and has since given it back to      |
//|  <= InpGivebackThreshold, UNLESS that peak was >= InpGivebackPeakCutoff,    |
//|  in which case it is deliberately left alone. Origin: a blanket "cut         |
//|  anything that gives back to near-breakeven" rule was tested first on the     |
//|  sibling Meridian_EA.mq5 and LOST real money (-$2037, -61%) because most       |
//|  of the edge comes from the minority of giveback trades that recover into      |
//|  a large winner, and a blanket rule can't tell those apart from the ones        |
//|  that go on to actually lose. PEAK SIZE turned out to be the real                |
//|  discriminator: small-peak givebacks are heavily net-negative, big-peak           |
//|  givebacks are heavily net-positive (see Meridian_EA.mq5 v1.06 header for          |
//|  the original finding). Re-tested on THIS file's own real construction              |
//|  (research/aurelius/giveback_generalization_test.py - fractal trendline               |
//|  breakout + VWAP + S/R, InpSafetyStopATR=4.0, this file's real shipped                 |
//|  defaults, real GOLD M5, does not include InpUseAureliusFilter which                    |
//|  earlier research already found has zero real drawdown effect): real net                 |
//|  $2990 -> $5428 at peak cutoff $30 (+$2438, +82%), positive at every                       |
//|  cutoff $10-30 tested, positive both in-sample and out-of-sample                            |
//|  throughout - the largest relative improvement of the three systems                          |
//|  checked at the time. Shipped default InpGivebackPeakCutoff=30 matches the                     |
//|  strongest point found in that sweep.                                                            |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  v1.06: InpUseGivebackExit CORRECTED FINDING (same day as v1.05). The     |
//|  Python estimate in v1.05's header (+$2438, +82%) was generated by a post- |
//|  hoc exit swap on a FIXED entry list - it could not see that closing a       |
//|  trade sooner frees the single-position slot for more, later entries. Fixed  |
//|  by wiring the giveback check into the real per-bar exit-priority loop, so it |
//|  can change which later breakout events get taken, and re-running: net          |
//|  2989.87->1162.81 (-61.1%), trades 716->857 (+19.7%), win% 25.8->53.7. The         |
//|  identical corrected method was real-MT5-validated on Aurelius_EA.mq5 (-64.3%       |
//|  real vs -63.9% corrected-Python, near-exact match), so this file's own              |
//|  corrected -61.1% is trusted at that same level even without its own separate          |
//|  real test. REJECTED. Stays false. See Aurelius_EA.mq5 v1.52's header,                  |
//|  research/aurelius/vanguard_giveback_event_driven_test.py.                               |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  v1.07: InpUseH4TrendFilter - REJECTED (2026-10-04), default now false.|
//|  The original "100.0th pctile, p=0.0000, %PF 1.019->1.560" claim was   |
//|  an artifact of a lookahead bug: the H4 bar lookup used `searchsorted  |
//|  (h4_time, t, side="left")-1`, which for any M5 bar not exactly on an  |
//|  H4 boundary picks the H4 bar that is STILL FORMING (e.g. at 09:30 it  |
//|  returns the 08:00 bar, which doesn't close until 12:00) - leaking up  |
//|  to ~4h of future H4 price into every entry decision. The "fix a      |
//|  lookahead bug, result barely moved" note in the ORIGINAL version of   |
//|  this comment only caught the exact-boundary edge case (2.24% of       |
//|  events) - the general mid-interval case, which is nearly everything  |
//|  else, was still leaking. Found via an Opus audit of a real MT5 bar-   |
//|  match mismatch (57/65 trades matched before the real fix, 64/65 after|
//|  - the fix itself is solid, now verified against real fills). With    |
//|  the CORRECTED alignment, same untouched window: baseline 87.8th       |
//|  pctile/p=0.12 -> +H4 filter 83.3th pctile/p=0.17 - WORSE than         |
//|  baseline, no edge in either direction. Input and code kept (fail-     |
//|  closed, same convention as InpUseGivebackExit) in case a future H4    |
//|  construction is worth trying, but OFF by default.                    |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  v1.09: InpUseAureliusFilter now defaults false, and ReadAureliusDir()  |
//|  fixed (heartbeat variable, see g_aurGVarName+"_HB" in its own header)   |
//|  - a live test confirmed GlobalVariableGet() was silently defeating this  |
//|  filter's staleness check entirely (CLAUDE.md's 2026-10-04 section,       |
//|  GlobalVariableStalenessTest.mq5). The fix itself verified clean, but      |
//|  the filter stays off: this mechanism can never be exercised by MT5        |
//|  Strategy Tester (it runs one EA at a time), so it's structurally           |
//|  invisible to this project's own validation method - exactly how the        |
//|  staleness bug hid through a full prior audit. Modest original benefit       |
//|  against a permanently-unverifiable mechanism - not worth the risk.           |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  v1.10: four live-vs-simulator bugs from the 2026-10-04 audit fixed  |
//|  (first three are the same ones found in Vanguard_M15_EA.mq5 v1.11).  |
//|  (1) A failed REVERSAL close was never retried - the breakout is edge-|
//|  triggered, so next bar breakoutDir=0 and the old position stayed open|
//|  until SL/stale/Friday. Now RetryReversalClose() re-sends the close on|
//|  every tick (1 s send gap, 10 s hold after an ambiguous retcode) until|
//|  it succeeds or the position is gone, capped at                       |
//|  InpReversalRetryMinutes; the reversal ENTRY is still taken only if   |
//|  the close lands inside the trigger bar (same bar-1 filters, same bar |
//|  as the Python fill).                                                 |
//|  (2) Stale exit fired one bar early: iBarShift() of the fill bar      |
//|  counts from bar 0, the simulators' kk-fill_i counts from the just-   |
//|  closed bar 1 - now barsHeld-1 >= InpStaleBars, matching              |
//|  kk-fill_i >= stale_bars (vanguard_random_timing_test.py sim_full).   |
//|  (3) VWAP counted bar 1 twice on attach (SeedVWAP() + the first-tick  |
//|  UpdateVWAP()) - g_vwapLastBar now stops the double add, and also     |
//|  lets UpdateVWAP() catch up any same-day bars missed while no ticks   |
//|  arrived (disconnect), which were previously never summed.            |
//|  (4) Swing/trendline state started EMPTY on every attach/restart -    |
//|  no backfill, so after a terminal restart/VPS reboot/recompile no     |
//|  entry (and no REVERSAL exit for a held position) could fire until    |
//|  two NEW swing highs/lows had each been confirmed (InpFractalK bars   |
//|  after each, often days), while the Python model builds swings over   |
//|  full history. WarmUpSwingState() now replays recent history through  |
//|  the identical swing/line/edge rules on the first new bar, so live    |
//|  state matches what a never-restarted EA would hold. Strategy Tester  |
//|  has no requotes, so (1) cannot change a backtest; (2)-(4) bring      |
//|  live (and a backtest's first days) closer to the simulators, not     |
//|  further. Not yet re-run through MT5 Strategy Tester.                 |
//+------------------------------------------------------------------+
//|  v1.11 (2026-10-04 audit, fresh/unprimed): three more live-vs-        |
//|  simulator gaps fixed, one judged acceptable as documented behavior.  |
//|  (1) g_entryATR lives only in memory and v1.10's stale-exit guard     |
//|  (`g_entryATR > 0.0`) was meant only as a divide-by-zero/bad-data     |
//|  safeguard, but because nothing ever recomputed g_entryATR after a    |
//|  restart it stayed 0.0 for a restored position's ENTIRE remaining    |
//|  life, silently and permanently disabling the stale exit for that    |
//|  trade (with the default InpStaleMinProfitATR=0.0 the ATR value      |
//|  doesn't even change the stale decision - only whether the division  |
//|  happens at all). OnInit() now calls RecomputeEntryATR() when a      |
//|  position is already open at attach, using the new ATRAtShift() to   |
//|  read the Wilder ATR as it stood at the entry bar - same general     |
//|  pattern as Aurelius_EA.mq5's own v1.54 ATRAtShift() restart fix,     |
//|  adapted to this file's own ComputeWilderATR() signature (kept       |
//|  separate from g_atrBuf, which the live per-tick GetATR() owns). If  |
//|  history isn't fully synced yet at the moment of attach, the same    |
//|  recompute is retried on every new bar (g_entryATRRestorePending)    |
//|  until it succeeds - the same retry-until-ready shape                |
//|  WarmUpSwingState() already uses below for g_swingWarm.              |
//|  (2) Swing/trendline state could go stale for days if ticks simply   |
//|  stopped arriving for more than one bar WITHOUT a restart (a VPS     |
//|  network blip or broker feed drop) - UpdateSwingsAndCheckBreakout()  |
//|  only ever evaluates the single newly-closed bar, so any swing point |
//|  that would have formed during the skipped bars was lost for good    |
//|  until two fresh swings confirmed natively (InpFractalK bars each,   |
//|  often days). IsNewBar() now detects a >1-bar gap since the last bar |
//|  this EA actually processed (iBarShift of the previous               |
//|  g_lastBarTime) and sets g_swingWarm=false, so OnTick's EXISTING     |
//|  WarmUpSwingState() call rebuilds the whole swing/trendline state     |
//|  from history on the very next bar - the identical mechanism v1.10   |
//|  already uses for a restart, just triggered by a gap instead of an   |
//|  attach. Matches this project's established disconnect-catch-up      |
//|  template (UpdateVWAP()'s own v1.10 "sum every closed same-day bar   |
//|  newer than g_vwapLastBar, not just bar 1" loop above).              |
//|  (3) CONSIDERED, LEFT AS DOCUMENTED BEHAVIOR: the first tick after a |
//|  restart (WarmUpSwingState() + the live bar-1 evaluation right after |
//|  it) re-evaluates the just-closed bar's breakout, which a previous   |
//|  instance may already have acted on (blocked by the spread check,   |
//|  or closed by hand) seconds earlier - a restart within the same     |
//|  5-minute bar can enter that breakout late, partway through the     |
//|  bar. A clean fix needs genuinely new persistent state (e.g.         |
//|  recording which exact breakout bar/price was already acted on,     |
//|  surviving a restart in STORAGE, not just RAM) with real complexity |
//|  and its own new failure modes, for what the 2026-10-04 audit       |
//|  called a minor edge case on the M15 sibling - judged not worth a   |
//|  rushed, possibly-half-correct fix here. Left exactly as-is;        |
//|  flagged so it is never mistaken for an oversight.                  |
//|  (4) The S/R filter's comment claimed missing daily S/R data BLOCKS |
//|  entry (fail-closed), but the code (SRDistance() returning -1.0,    |
//|  which fails the `sr >= 0.0` test in CheckForEntry()) has always    |
//|  let the entry through WITHOUT the S/R check in that case - fail-   |
//|  OPEN. Checked against Meridian_EA.mq5, which this file's           |
//|  SRDistance()/GetSRLevels() is reused verbatim from: Meridian's own |
//|  comment ("not enough D1 history yet - SRDistance fails open here") |
//|  documents this exact behavior as the project's established,       |
//|  already-validated convention for this filter - every real/Python- |
//|  validated number in this file's own header was produced running   |
//|  this fail-open code, unchanged. CODE IS THEREFORE UNCHANGED; the   |
//|  comment was wrong and is now fixed to say so honestly, instead of  |
//|  changing live trading behavior to match a comment that was never   |
//|  actually how this filter ran.                                     |
//+------------------------------------------------------------------+
#property copyright "Vanguard_EA"
#property version   "1.11"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

input group "=== Signal: diagonal trendline breakout ==="
input int    InpFractalK          = 100;     // bars on each side to confirm a swing point
input int    InpSRDays            = 3;       // trailing completed D1 bars checked for the nearest level
input double InpMinSRDistATR      = 0.50;    // reject entries this close (xATR) to that level

input group "=== Entry filter: H4 trend alignment (v1.07) ==="
input bool   InpUseH4TrendFilter  = false;   // REJECTED (2026-10-04) - see header. The original
                                              // Python-validated claim (100.0th pctile, p=0.0000,
                                              // %PF 1.019->1.560) used a buggy H4 alignment that
                                              // leaked up to ~4h of future H4 price into every
                                              // entry. Corrected: 87.8th->83.3th pctile, p=0.12->0.17
                                              // (worse, not better). Stays false.
input int    InpH4EMAPeriod       = 50;      // EMA period on H4 - unused while the filter above is off

input group "=== Exit ==="
input double InpSafetyStopATR     = 4.0;     // validated best cell - see header
input int    InpATRPeriod         = 14;
input bool   InpUseStaleExit      = true;    // cut a non-performing trade loose early - see header (v1.04)
input int    InpStaleBars         = 225;     // ~18.75h on M5 - real, Python-validated optimum, see header
input double InpStaleMinProfitATR = 0.0;     // exit if floating profit (in entry-ATR units) is still below this once InpStaleBars have elapsed.
input int    InpReversalRetryMinutes = 60;   // v1.10: keep re-sending a FAILED reversal close on every tick for up to this long (0 = off = old never-retry behaviour). The reversal entry itself is only taken if the close lands inside the trigger bar.

input group "=== Giveback-to-breakeven exit (v1.05 candidate, Python-only so far) ==="
input bool   InpUseGivebackExit    = false;   // Different from InpUseStaleExit above (which reacts to a trade NEVER making progress): this reacts to a trade that DID make progress, then lost it. REJECTED (2026-09-25): the Python method was fixed (giveback check wired into the real per-bar exit-priority loop, so it can change which later breakout events get taken, instead of a post-hoc swap on a fixed entry list) and re-run - net 2989.87->1162.81 (-61.1%), trades 716->857 (+19.7%), win% 25.8->53.7. Same cascade mechanism confirmed on Aurelius_EA.mq5 against a REAL MT5 A/B test (-64.3% real vs -63.9% corrected-Python, near-exact match) - this file's own corrected result is now trusted at that same level. Stays false. See Aurelius_EA.mq5 v1.52's header and research/aurelius/vanguard_giveback_event_driven_test.py.
input double InpGivebackMinPeak    = 5.0;     // Floating profit (price units, i.e. $ per 0.01 lot) the trade must reach before a giveback can even be checked - below this it's ordinary noise, never cut.
input double InpGivebackPeakCutoff = 30.0;    // If the peak reached was AT OR ABOVE this, do NOT cut on giveback - real data shows these trades recover into a real winner far more often than average, not less. 30 was the strongest point in this file's own real sweep (research/aurelius/giveback_generalization_test.py).
input double InpGivebackThreshold  = 1.0;     // Floating profit (price units) at/below which counts as "given back to near-breakeven".

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

input group "=== Cross-EA signal (v1.03 - optional, Aurelius conflict filter) ==="
input bool   InpUseAureliusFilter = false;     // DEFAULTS OFF (2026-10-04 decision). Skip an entry only if
                                                // Aurelius_EA.mq5 (its own M5 chart) is already holding the
                                                // opposite direction right now - the net $2989.87 -> $3059.94
                                                // figure (research/aurelius/vanguard_aurelius_position_filter_
                                                // test.py) came from a Python simulation of combined trade
                                                // histories, NOT from the real GlobalVariable read/write
                                                // mechanism this flag actually turns on - MT5 Strategy Tester
                                                // runs one EA at a time and can never exercise two EAs reading
                                                // each other's live state, so this mechanism is structurally
                                                // invisible to this project's own backtest/bar-match validation.
                                                // That blind spot is exactly how a real bug (GlobalVariableGet()
                                                // silently refreshing the staleness timestamp it was supposed to
                                                // be checked against, defeating InpAureliusStaleSecs entirely)
                                                // survived undetected through a full prior code audit - see
                                                // CLAUDE.md's 2026-10-04 section and GlobalVariableStalenessTest.
                                                // mq5. That specific bug is now fixed (ReadAureliusDir() checks a
                                                // dedicated heartbeat variable instead), but the original benefit
                                                // was always modest ("barely touches trade count") against a
                                                // mechanism that can never be verified the way everything else in
                                                // this project is - left here, fixed and available, in case it's
                                                // worth revisiting, but off by default. If Aurelius isn't
                                                // attached, or hasn't updated recently, Vanguard trades completely
                                                // normally either way.
input int    InpAureliusStaleSecs = 900;       // Treat the signal as absent if it hasn't updated in this long (15 min default - a few Aurelius M5 bars).
                                                // Covers Aurelius being removed, crashed, or never attached
                                                // in the first place.

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
input string  InpBackgroundBMP = "";              // Optional background image (.bmp in MQL5\Images) - empty by default, no Vanguard-branded image exists yet.
input int     InpBgWidth       = 1290;            // Image width (px) - for centring only
input int     InpBgHeight      = 720;             // Image height (px) - for centring only

input group "=== Chart theme ==="
input bool    InpApplyTheme      = true;          // Recolour the chart
input bool    InpHideTradeMarks  = true;          // Hide MT5's own buy/sell/SL/TP arrows and lines - the panel and signal lines are meant to be the only things on this chart.
input bool    InpShowSignalLine  = true;          // Draw the live descending/ascending trendline as an extending ray
input color   InpColDesc         = C'255,61,90';  // Descending line (resistance / sell-side) - hot red
input color   InpColAsc          = C'0,230,118';  // Ascending line (support / buy-side) - neon green
input bool    InpShowVWAPLine    = true;          // Draw session VWAP (live only from attach time - see header)
input color   InpColVWAP         = C'0,255,255';  // VWAP line colour - neon aqua
input int     InpVwapHistoryBars = 400;           // How many recent bars of VWAP line to keep drawn (bounded, purged the same way as the signal-line history would be).
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

//--- InpUseGivebackExit tracking - which ticket g_gbPeakFav belongs to,
//--- reset whenever g_ticket changes (tickets are unique/monotonic in
//--- MT5, never reused, so a simple != is a safe "new position" test)
ulong    g_gbTicket  = 0;
double   g_gbPeakFav = 0.0;   // best floating profit (price units) seen so far this trade

//--- single-latch new-bar gate (called exactly once per tick)
datetime g_lastBarTime = 0;

//--- session VWAP (cumulative typical-price*volume from each calendar
//--- day's first bar) - identical construction to Meridian_EA.mq5,
//--- reused verbatim since it's already validated there.
datetime g_vwapDay    = 0;
double   g_vwapCumPV  = 0.0;
double   g_vwapCumVol = 0.0;
double   g_vwapValue  = 0.0;
datetime g_vwapLastBar = 0;   // v1.10: open time of the last bar already summed in - stops the first-tick UpdateVWAP() re-adding SeedVWAP()'s bar 1

//--- v1.10 failed-REVERSAL-close retry (see RetryReversalClose()) -
//--- g_revTicket == 0 = no retry pending.
ulong    g_revTicket   = 0;   // position the reversal close is still owed on
int      g_revDir      = 0;   // direction of the reversal breakout (the entry owed if the close lands in-bar)
datetime g_revBar      = 0;   // bar-0 open time when the reversal fired (entry window = this bar only)
datetime g_revUntil    = 0;   // hard stop for close retries
datetime g_revLastSend = 0;   // throttle: last send time
bool     g_revAmbig    = false; // last failure was ambiguous (timeout/no connection) - hold before re-sending
int      g_revSends    = 0;

//--- v1.10 swing-state warm-up (see WarmUpSwingState()) - false until the
//--- trendline state has been rebuilt from history after this attach.
bool     g_swingWarm   = false;

//--- manual Wilder ATR (see header - NOT iATR)
double   g_atrBuf[];

//--- H4 trend-alignment filter (v1.07) - one indicator handle, created in
//--- OnInit(), released in OnDeinit(), same lifecycle as this project's
//--- other EAs' iMA() handles (see Aurelius_EA.mq5).
int      g_h4EmaHandle = INVALID_HANDLE;

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

//--- cross-EA signal reader (v1.03 - see InpUseAureliusFilter). Matches
//--- Aurelius_EA.mq5's own writer-side name exactly - "M5" literal on
//--- both ends, not PERIOD_CURRENT-derived, since both files hard-lock
//--- to M5 anyway (see each OnInit).
string   g_aurGVarName = "";
int      g_lastAurDir = 0;   // cosmetic only - the panel's "Aurelius position" row, refreshed every new bar
double   g_entryATR = 0.0;   // ATR at entry, remembered for the stale-exit profit threshold (v1.04) - matches
                              // the Python validation's exact semantics (profit measured in ENTRY-bar ATR
                              // units, not current ATR, same convention as the safety stop's own distance).
                              // v1.11: this lives only in memory, so OnInit() recomputes it via
                              // RecomputeEntryATR()/ATRAtShift() whenever a position is ALREADY open at
                              // attach (restart/recompile/input change) - see header bug (1).
bool     g_entryATRRestorePending = false;   // v1.11: true after OnInit found an open position but history
                              // wasn't ready to recompute g_entryATR yet - retried each new bar until it
                              // succeeds (same retry-until-ready shape as g_swingWarm below).

//--- forward declarations: OnInit draws the panel before DrawPanel is defined
void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim = true);
void PTheme();
void PBackground();
void PWatermark();
void UpdateSignalLines();
void UpdateVWAPLine();
void UpdateLevelLines();
void CheckForEntry(int breakoutDir);   // v1.10: called from RetryReversalClose(), defined below it
void RecomputeEntryATR();              // v1.11: called from OnInit()/OnTick(), defined after ATRAtShift()

//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, PERIOD_M5, 0);
   if(t == g_lastBarTime) return(false);
   //--- v1.11: detect a gap of more than one bar since the last bar this EA
   //--- actually processed (e.g. ticks stopped for a while - VPS network
   //--- blip, broker feed drop - WITHOUT a restart; see header bug (2)).
   //--- UpdateSwingsAndCheckBreakout() only ever evaluates the single
   //--- newly-closed bar, so any swing point that would have formed during
   //--- the skipped bars is otherwise lost for good. g_swingWarm=false
   //--- makes the existing WarmUpSwingState() call in OnTick rebuild the
   //--- whole swing/trendline state from history on this same new bar -
   //--- the identical mechanism v1.10 already uses after a restart/attach,
   //--- just triggered here by a gap instead. g_lastBarTime==0 is the
   //--- genuine first-ever call (right after OnInit already set
   //--- g_swingWarm=false for the normal attach case) - skip the check
   //--- then, there is nothing to have "skipped" yet.
   if(g_lastBarTime != 0)
     {
      int skipped = iBarShift(_Symbol, PERIOD_M5, g_lastBarTime, false);
      if(skipped > 1)
        {
         PrintFormat("Vanguard EA: detected a %d-bar gap since the last bar this EA processed "
                     "(ticks stopped without a restart) - rebuilding swing/trendline state from history",
                     skipped);
         g_swingWarm = false;
        }
     }
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
//| v1.11 - Wilder ATR as of an arbitrary historical shift, NOT just    |
//| the live shift-1 that ComputeWilderATR()/GetATR() above always      |
//| read. Same construction as ComputeWilderATR(), parameterized by      |
//| the CopyRates starting shift instead of a hardcoded 1, so `out[0]`    |
//| here is the ATR as it stood with THAT shift playing the role of       |
//| "shift 1" (i.e. the last closed bar at that point in time). Returns    |
//| straight to a double rather than touching g_atrBuf, which the live     |
//| per-tick GetATR() owns - this is only ever used to reconstruct a        |
//| historical value (see RecomputeEntryATR() below), never the live one.   |
//| Used for the same restart-ATR-recovery purpose as Aurelius_EA.mq5's      |
//| own v1.54 ATRAtShift(), adapted to this file's own ComputeWilderATR()     |
//| signature (this file computes true range/seed inline rather than off      |
//| a caller-supplied rates array, so the body is reproduced here rather        |
//| than shared).                                                                |
//+------------------------------------------------------------------+
double ATRAtShift(const int shift, const int period)
  {
   if(shift < 0) return(0.0);
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, PERIOD_M5, shift, MathMax(period * 3, 200), r);
   if(got < period + 2) return(0.0);
   double tr[];
   ArrayResize(tr, got);
   for(int i = 0; i < got - 1; i++)
     {
      double hi = r[i].high, lo = r[i].low, pc = r[i + 1].close;
      tr[i] = MathMax(hi - lo, MathMax(MathAbs(hi - pc), MathAbs(lo - pc)));
     }
   int lastIdx = got - period - 1;
   if(lastIdx < 0) return(0.0);
   double seed = 0.0;
   for(int k = lastIdx; k < lastIdx + period; k++) seed += tr[k];
   seed /= period;
   double prev = seed;
   for(int k = lastIdx - 1; k >= 0; k--)
      prev = (prev * (period - 1) + tr[k]) / period;
   return(prev);
  }
//+------------------------------------------------------------------+
//| v1.11 - recomputes g_entryATR for a position that was ALREADY open  |
//| when this EA instance started (terminal/VPS restart, recompile,      |
//| input change) - see header bug (1). Nothing else ever sets           |
//| g_entryATR in that case, so without this it stays at its 0.0          |
//| initializer for that trade's entire remaining life, silently and       |
//| permanently disabling the stale exit (ManageOpenPosition()'s             |
//| `g_entryATR > 0.0` guard exists only to avoid a divide-by-zero on a        |
//| genuinely bad/cold ATR read, not to skip the check forever). The ATR       |
//| that mattered at entry was read with shift=1 relative to the entry          |
//| tick's own "now" - i.e. the bar immediately before the entry bar, which      |
//| is shift (entryShift+1) relative to the current tick, where entryShift       |
//| is the entry bar's own shift now (iBarShift of its POSITION_TIME). If          |
//| history isn't fully synced yet at the moment of attach (CopyRates returns       |
//| too few bars), g_entryATRRestorePending is left true and OnTick retries           |
//| this on every subsequent new bar until it succeeds - the same retry-until-         |
//| ready shape WarmUpSwingState() already uses for g_swingWarm.                        |
//+------------------------------------------------------------------+
void RecomputeEntryATR()
  {
   g_entryATRRestorePending = false;
   if(g_ticket == 0 || !PositionSelectByTicket(g_ticket)) return;
   datetime opTime = (datetime)PositionGetInteger(POSITION_TIME);
   int entryShift = iBarShift(_Symbol, PERIOD_M5, opTime, false);
   if(entryShift < 0) { g_entryATRRestorePending = true; return; }   // history not ready yet - retry next bar
   double atrAtEntry = ATRAtShift(entryShift + 1, InpATRPeriod);
   if(atrAtEntry > 0.0)
     {
      g_entryATR = atrAtEntry;
      PrintFormat("Vanguard EA: restored open position #%I64u on restart - entry-bar ATR recomputed as "
                  "%.5f (opened %s, %d bars ago)",
                  g_ticket, g_entryATR, TimeToString(opTime), entryShift);
     }
   else
      g_entryATRRestorePending = true;   // not enough history yet - retry next bar
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
   g_vwapLastBar = last;   // v1.10: bar 1 is now in the sum - UpdateVWAP() must not add it again
   g_vwapValue = (g_vwapCumVol > 0.0) ? g_vwapCumPV / g_vwapCumVol : iClose(_Symbol, PERIOD_M5, 1);
  }
//+------------------------------------------------------------------+
void UpdateVWAP()
  {
   datetime t1 = iTime(_Symbol, PERIOD_M5, 1);
   if(t1 == 0) return;
   //--- v1.10: OnInit()'s SeedVWAP() already summed bar 1, and g_lastBarTime=0
   //--- makes the very first tick a "new bar" - skip the double add.
   if(t1 <= g_vwapLastBar) return;
   datetime day = DayStart(t1);
   if(day != g_vwapDay)
     {
      SeedVWAP();
      return;
     }
   //--- v1.10: sum EVERY closed same-day bar newer than g_vwapLastBar, not
   //--- just bar 1 - normally that IS just bar 1, but after a stretch with
   //--- no ticks (disconnect) the bars in between were previously skipped
   //--- for the rest of the session.
   for(int shift = 1; shift < 400; shift++)
     {
      datetime t = iTime(_Symbol, PERIOD_M5, shift);
      if(t == 0 || t <= g_vwapLastBar || DayStart(t) != day) break;
      double typical = (iHigh(_Symbol, PERIOD_M5, shift) + iLow(_Symbol, PERIOD_M5, shift) +
                         iClose(_Symbol, PERIOD_M5, shift)) / 3.0;
      double vol = (double)iTickVolume(_Symbol, PERIOD_M5, shift);
      g_vwapCumPV  += typical * vol;
      g_vwapCumVol += vol;
     }
   g_vwapLastBar = t1;
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
//| Meridian_EA.mq5's SRDistance(), reused verbatim. FAILS OPEN: -1.0   |
//| (bad ATR, or GetSRLevels() couldn't get enough D1 history) is a     |
//| sentinel CheckForEntry() treats as "no S/R opinion" and lets the    |
//| entry through WITHOUT this filter, not as a block (v1.11 - checked  |
//| against Meridian_EA.mq5, whose own comment calls this exact case    |
//| "SRDistance fails open here" - an already-established, already-     |
//| validated convention in this project, not something introduced or   |
//| changed here). In practice this is a real condition only in the     |
//| first InpSRDays after a genuinely fresh EA attach, before D1        |
//| history is fully cached - every real/Python-validated number in     |
//| this file's header was produced running this exact fail-open code.  |
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
//| CopyBuffer helper for g_h4EmaHandle - shift 1 = the last CLOSED    |
//| H4 bar, matching this project's MA() convention (Aurelius_EA.mq5). |
//+------------------------------------------------------------------+
bool H4EMA(const int shift, double &out)
  {
   double b[];
   ArraySetAsSeries(b, true);
   if(CopyBuffer(g_h4EmaHandle, 0, shift, 1, b) < 1) return(false);
   out = b[0];
   return(true);
  }
//+------------------------------------------------------------------+
//| True only when the LAST CLOSED H4 bar's close sits on the isBuy    |
//| side of its own InpH4EMAPeriod EMA - see InpUseH4TrendFilter's      |
//| header for what this buys (Python-validated, K=1). Both iClose()   |
//| and the EMA handle use shift 1, so this always reads the most       |
//| recent FULLY FORMED H4 bar, never the one still building - MT5's    |
//| own HTF-alignment handles that for free, so (unlike the Python      |
//| research reproduction, which had to align M5->H4 by hand and had    |
//| a real off-by-one bug there) there's no equivalent lookahead risk    |
//| here. False (blocks entry) if H4 history isn't ready yet - same      |
//| fail-closed convention as GetATR() above (whose own failure also      |
//| blocks entry, via CheckForEntry()'s `if(!GetATR(atr)...) return;`).    |
//| v1.11: GetSRLevels()/SRDistance() are NOT part of that same           |
//| convention - they deliberately FAIL OPEN (see SRDistance()'s own       |
//| comment) - this header previously claimed otherwise, which was wrong    |
//| and is now corrected; nothing about SRDistance()'s actual behavior      |
//| changed.                                                                  |
//+------------------------------------------------------------------+
bool H4TrendAgrees(bool isBuy)
  {
   double ema;
   if(!H4EMA(1, ema)) return(false);
   double h4Close = iClose(_Symbol, PERIOD_H4, 1);
   if(h4Close <= 0.0) return(false);
   bool h4Up = h4Close > ema;
   return isBuy ? h4Up : !h4Up;
  }
//+------------------------------------------------------------------+
//| Reads Aurelius_EA.mq5's real, broadcast position direction (v1.03 |
//| - see InpUseAureliusFilter's header): +1/-1 = Aurelius currently   |
//| holds that side, 0 = flat, absent, or stale (hasn't updated within |
//| InpAureliusStaleSecs - covers Aurelius never attached, removed, or |
//| crashed). Called once per new bar regardless of Vanguard's own     |
//| position state, purely so the panel can always show Aurelius's     |
//| current status, not just at the moments Vanguard is checking for   |
//| a new entry.                                                        |
//+------------------------------------------------------------------+
int ReadAureliusDir()
  {
   if(!InpUseAureliusFilter) return(0);
   //--- v1.XX CORRECTION: staleness is now checked against a DEDICATED
   //--- heartbeat variable (g_aurGVarName+"_HB") that nothing ever reads
   //--- via GlobalVariableGet() - a live test (GlobalVariableStalenessTest.mq5,
   //--- 2026-10-04) confirmed GlobalVariableGet() ITSELF refreshes
   //--- GlobalVariableTime(), so checking staleness against the POSITION
   //--- variable's own time (the old v1.03 design) was self-defeating: the
   //--- very Get() call below, needed to read the value, reset the clock
   //--- the NEXT call's staleness check relied on - once read successfully
   //--- while fresh, a crashed/removed Aurelius looked "fresh" forever.
   //--- Requires an Aurelius_EA.mq5 build that writes the heartbeat (same
   //--- date or later) - an older Aurelius build won't write it, and this
   //--- will then correctly treat it as absent rather than silently
   //--- falling back to the broken old behaviour.
   string hbName = g_aurGVarName + "_HB";
   if(!GlobalVariableCheck(hbName)) return(0);   // Aurelius never attached this session (or a pre-fix build)
   datetime lastSet = (datetime)GlobalVariableTime(hbName);
   //--- TimeLocal(), NOT TimeCurrent() (found in review): global variable
   //--- timestamps are stamped against the terminal's LOCAL clock, not
   //--- the broker's server time - comparing against TimeCurrent() would
   //--- be off by whatever the server/local timezone gap is (can be
   //--- several hours), making this either never trigger (permanently
   //--- "stale") or never expire (a genuinely dead signal treated as
   //--- live forever), depending on which side of the gap the broker
   //--- sits.
   if(TimeLocal() - lastSet > InpAureliusStaleSecs) return(0);   // attached before, not actively updating now
   if(!GlobalVariableCheck(g_aurGVarName)) return(0);
   return (int)GlobalVariableGet(g_aurGVarName);
  }
//+------------------------------------------------------------------+
//| True only when this bar's breakout direction `dir` should be       |
//| BLOCKED because Aurelius is ALREADY holding the opposite side      |
//| right now - Python-validated (research/aurelius/                   |
//| vanguard_aurelius_position_filter_test.py: net $2989.87->$3059.94, |
//| barely touches trade count). Aurelius flat/absent/stale (0) never   |
//| blocks - Vanguard trades completely normally, matching the user's   |
//| explicit requirement.                                               |
//+------------------------------------------------------------------+
bool AureliusBlocksEntry(int dir)
  {
   int aurDir = ReadAureliusDir();
   return(aurDir != 0 && aurDir != dir);
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
//| v1.10 - rebuilds the swing/trendline/edge state from history on    |
//| the first new bar after an attach (see header item 4). Replays     |
//| every closed bar from the oldest usable one down to bar 2, through |
//| the EXACT rules UpdateSwingsAndCheckBreakout() applies live (same  |
//| strict 2K+1 fractal window, same line extrapolation by bar count,  |
//| same descValid/aboveDesc edge flags) - but emits no trades. Bar 1  |
//| is deliberately left out: OnTick() processes it live right after,  |
//| exactly once (replaying it here too would detect a swing confirmed |
//| on bar 1 twice, making prev == cur and invalidating the line).     |
//| Swing detection is local, so any window holding the last two swing |
//| highs and lows gives the same state as the Python model's full-    |
//| history build; WARMUP_BARS (~70 days of M5) is far more than that. |
//| Returns false (retried next new bar) if history isn't loaded yet.  |
//+------------------------------------------------------------------+
bool WarmUpSwingState()
  {
   const int WARMUP_BARS = 20000;
   int K = InpFractalK;
   int avail = Bars(_Symbol, PERIOD_M5);
   if(avail <= 0) return(false);
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, PERIOD_M5, 0, MathMin(avail, WARMUP_BARS), r);
   if(got < 2 * K + 3) return(false);

   int    curHiS = -1, prevHiS = -1, curLoS = -1, prevLoS = -1;   // shift of each swing's formation bar
   double curHiP = 0.0, prevHiP = 0.0, curLoP = 0.0, prevLoP = 0.0;
   bool   prevAboveDesc = false, prevDescValid = false, prevBelowAsc = false, prevAscValid = false;

   for(int b = got - 1 - 2 * K; b >= 2; b--)   // b plays the role of live "bar 1"
     {
      int c = b + K;                             // live centerShift = InpFractalK+1, relative to bar 1
      bool isHi = true, isLo = true;
      for(int s = b; s <= b + 2 * K; s++)
        {
         if(s == c) continue;
         if(r[s].high >= r[c].high) isHi = false;
         if(r[s].low  <= r[c].low)  isLo = false;
         if(!isHi && !isLo) break;
        }
      if(isHi) { prevHiS = curHiS; prevHiP = curHiP; curHiS = c; curHiP = r[c].high; }
      if(isLo) { prevLoS = curLoS; prevLoP = curLoP; curLoS = c; curLoP = r[c].low; }

      bool descValid = (prevHiS > curHiS && curHiS >= 0 && curHiP < prevHiP);
      double descVal = descValid ? curHiP + (curHiP - prevHiP) / (double)(prevHiS - curHiS) * (double)(curHiS - b) : 0.0;
      prevAboveDesc = descValid && (r[b].close > descVal);
      prevDescValid = descValid;

      bool ascValid = (prevLoS > curLoS && curLoS >= 0 && curLoP > prevLoP);
      double ascVal = ascValid ? curLoP + (curLoP - prevLoP) / (double)(prevLoS - curLoS) * (double)(curLoS - b) : 0.0;
      prevBelowAsc = ascValid && (r[b].close < ascVal);
      prevAscValid = ascValid;
     }

   g_curHiTime  = (curHiS  >= 0) ? r[curHiS].time  : 0;  g_curHiPrice  = curHiP;
   g_prevHiTime = (prevHiS >= 0) ? r[prevHiS].time : 0;  g_prevHiPrice = prevHiP;
   g_curLoTime  = (curLoS  >= 0) ? r[curLoS].time  : 0;  g_curLoPrice  = curLoP;
   g_prevLoTime = (prevLoS >= 0) ? r[prevLoS].time : 0;  g_prevLoPrice = prevLoP;
   g_prevAboveDesc = prevAboveDesc; g_prevDescValid = prevDescValid;
   g_prevBelowAsc  = prevBelowAsc;  g_prevAscValid  = prevAscValid;
   PrintFormat("Vanguard EA: swing state rebuilt from %d bars of history - last highs %s/%s, last lows %s/%s",
               got, TimeToString(g_prevHiTime), TimeToString(g_curHiTime),
               TimeToString(g_prevLoTime), TimeToString(g_curLoTime));
   return(true);
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
   //--- further +6 (GAPS). In-position: a0 + s1+g1-g3 + s2+c1-c6 (v1.03
   //--- added c5, Aurelius position; v1.07 added c6, H4 trend) + s3+d1-d4
   //--- + s4+p1-p4 + s5+q1-q4 = 27 rh-rows, 10 gap-boundaries. Flat:
   //--- identical through s4, but p4 there only advances +6 (no rh) - one
   //--- row shorter (26), same 10 gap-boundaries (p4's +6 and s5's own gap
   //--- both still happen).
   const int ROWS = (haveLong || haveShort) ? 27 : 26, GAPS = 10;
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
   PRow("c4", x, ty, w, "ATR(14)", haveATR ? DoubleToString(atr, 2) : "-", -1); ty += rh;
   //--- red ONLY when actively blocking this bar's breakout (found in
   //--- review: previously always showed green whenever Aurelius held
   //--- ANY position, including the exact opposing case
   //--- AureliusBlocksEntry() was blocking on - a trader watching the
   //--- panel had no way to tell the filter was the reason no trade
   //--- fired). Neutral when the filter's off or Aurelius is flat/absent;
   //--- green when present and NOT conflicting (same direction, or no
   //--- breakout to conflict with this bar).
   int aurState = -1;
   if(InpUseAureliusFilter && g_lastAurDir != 0)
      aurState = (g_barLastBreakoutDir != 0 && g_lastAurDir != g_barLastBreakoutDir) ? 0 : 1;
   PRow("c5", x, ty, w, "Aurelius position",
        !InpUseAureliusFilter ? "filter off" : (g_lastAurDir > 0 ? "LONG" : g_lastAurDir < 0 ? "SHORT" : "flat/absent"),
        aurState); ty += rh;
   //--- same "neutral unless a breakout actually fired this bar"
   //--- convention as srState above - shows the raw H4 state always, but
   //--- only colours it against whichever side this bar's breakout is on.
   double h4EmaVal; bool haveH4 = InpUseH4TrendFilter && H4EMA(1, h4EmaVal);
   double h4Close1 = haveH4 ? iClose(_Symbol, PERIOD_H4, 1) : 0.0;
   int h4State = -1;
   if(InpUseH4TrendFilter && haveH4 && g_barLastBreakoutDir != 0)
      h4State = H4TrendAgrees(g_barLastBreakoutDir > 0) ? 1 : 0;
   PRow("c6", x, ty, w, "H4 trend (vs EMA" + (string)InpH4EMAPeriod + ")",
        !InpUseH4TrendFilter ? "filter off" : (haveH4 ? (h4Close1 > h4EmaVal ? "up" : "down") : "-"),
        h4State); ty += rh + 6;

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
bool CloseCurrentPosition(const string reason)
  {
   if(!PositionSelectByTicket(g_ticket)) { g_ticket = 0; g_posDir = 0; return(true); }
   if(trade.PositionClose(g_ticket))
     {
      g_ticket = 0;
      g_posDir = 0;
      return(true);
     }
   //--- v1.10: "next tick" was only ever true for FRIDAY/GIVEBACK (checked
   //--- every tick) and STALE (re-checked next bar). REVERSAL is edge-
   //--- triggered - its retry is RetryReversalClose()'s job.
   PrintFormat("Vanguard EA: %s close FAILED for ticket %I64u, retcode %d (%s) - will retry",
               reason, g_ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
   return(false);
  }
//+------------------------------------------------------------------+
//| v1.10 - failed REVERSAL close retry (header item 1). Identical      |
//| design to Vanguard_M15_EA.mq5 v1.11; same scope as                  |
//| HeadShoulders_EA.mq5's RetryTransientEntries(): run on EVERY tick,  |
//| before OnTick()'s new-bar gate. The CLOSE is owed until it succeeds |
//| or the position is gone (SL, manual, an ambiguous earlier send that |
//| did land), capped at InpReversalRetryMinutes. The reversal ENTRY is |
//| only attempted if the close lands inside the trigger bar -          |
//| CheckForEntry()'s filters all read bar 1, which is unchanged within |
//| that bar, so it is the same decision the Python model makes at that |
//| fill bar; a later entry would be a construction no simulator        |
//| modeled. Known limitation (disclosed, same as Meridian v1.12): the  |
//| pending retry lives in RAM only, so a restart mid-retry drops it.   |
//+------------------------------------------------------------------+
void ClearReversalRetry()
  {
   g_revTicket = 0; g_revDir = 0; g_revBar = 0; g_revUntil = 0;
   g_revLastSend = 0; g_revAmbig = false; g_revSends = 0;
  }
//+------------------------------------------------------------------+
void ScheduleReversalRetry(int breakoutDir)
  {
   if(InpReversalRetryMinutes <= 0) return;
   datetime now = TimeCurrent();
   uint rc = trade.ResultRetcode();
   g_revTicket   = g_ticket;
   g_revDir      = breakoutDir;
   g_revBar      = iTime(_Symbol, PERIOD_M5, 0);
   g_revUntil    = (datetime)((long)now + (long)InpReversalRetryMinutes * 60);
   g_revLastSend = now;
   g_revAmbig    = (rc == 0 || rc == TRADE_RETCODE_TIMEOUT || rc == TRADE_RETCODE_CONNECTION);
   g_revSends    = 1;
   PrintFormat("Vanguard EA: REVERSAL close for ticket %I64u DEFERRED - retrying on ticks until %s "
               "(reversal entry only if the close lands before this bar ends)",
               g_revTicket, TimeToString(g_revUntil, TIME_DATE|TIME_SECONDS));
  }
//+------------------------------------------------------------------+
void RetryReversalClose()
  {
   if(g_revTicket == 0) return;
   datetime now = TimeCurrent();
   bool inBar = (iTime(_Symbol, PERIOD_M5, 0) == g_revBar);

   SyncPositionState();
   if(g_ticket != g_revTicket)
     {
      //--- the owed position is gone (closed by SL/manually, or an ambiguous
      //--- earlier send did land). If we're flat and still in the trigger
      //--- bar, the reversal entry is still owed too.
      int dir = g_revDir;
      ClearReversalRetry();
      if(g_ticket == 0 && inBar) CheckForEntry(dir);
      return;
     }
   if(now >= g_revUntil)
     {
      string msg = StringFormat("Vanguard EA: REVERSAL close retry for ticket %I64u GAVE UP after %d send(s), "
                                "last retcode %d (%s) - position left open under its safety stop",
                                g_revTicket, g_revSends, trade.ResultRetcode(), trade.ResultRetcodeDescription());
      Print(msg);
      NotifyPush(msg);
      ClearReversalRetry();
      return;
     }
   //--- throttle: >= 1 s between sends, >= 10 s after an ambiguous retcode
   //--- (the earlier close may still be landing - don't stack a second one)
   if((long)now - (long)g_revLastSend < (g_revAmbig ? 10 : 1)) return;

   g_revLastSend = now;
   g_revSends++;
   if(trade.PositionClose(g_revTicket))
     {
      PrintFormat("Vanguard EA: REVERSAL close for ticket %I64u succeeded on send #%d%s",
                  g_revTicket, g_revSends, inBar ? "" : " (trigger bar already closed - no reversal entry)");
      int dir = g_revDir;
      ClearReversalRetry();
      SyncPositionState();
      if(g_ticket == 0 && inBar) CheckForEntry(dir);
      return;
     }
   uint rc = trade.ResultRetcode();
   g_revAmbig = (rc == 0 || rc == TRADE_RETCODE_TIMEOUT || rc == TRADE_RETCODE_CONNECTION);
   if(g_revSends <= 3 || g_revSends % 10 == 0)
      PrintFormat("Vanguard EA: REVERSAL close retry FAILED for ticket %I64u, send #%d, retcode %d (%s)",
                  g_revTicket, g_revSends, rc, trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
void ManageOpenPosition(int breakoutDir)
  {
   SyncPositionState();
   if(g_ticket == 0) return;

   if(IsFridayFlattenTime()) { CloseCurrentPosition("FRIDAY"); return; }

   if(breakoutDir != 0 && breakoutDir != g_posDir)
     {
      if(!CloseCurrentPosition("REVERSAL")) ScheduleReversalRetry(breakoutDir);
      return;
     }

   //--- stale exit (v1.04, see header): cut a trade loose - at whatever
   //--- it's currently worth - if it's shown no real progress after
   //--- InpStaleBars, rather than waiting for the full safety stop.
   //--- g_entryATR <= 0.0 is now ONLY a divide-by-zero/bad-data guard, not
   //--- a "restart disables this forever" gap: v1.11 made OnInit() (and,
   //--- if history wasn't synced yet, OnTick's g_entryATRRestorePending
   //--- retry) recompute g_entryATR from history via RecomputeEntryATR()/
   //--- ATRAtShift() whenever a position was ALREADY open at attach - see
   //--- header bug (1). Before that fix, g_entryATR stayed at its 0.0
   //--- initializer for the position's entire remaining life after ANY
   //--- restart/recompile/input change, silently and permanently disabling
   //--- this stale exit for that trade even though the default
   //--- InpStaleMinProfitATR=0.0 means the ATR value itself never actually
   //--- changed the decision below - only whether it got made at all. The
   //--- resting stop-loss order still protects the position regardless of
   //--- this check either way. No PositionSelectByTicket() here -
   //--- SyncPositionState() at the top
   //--- of this function already selected g_ticket, and nothing between
   //--- there and here re-selects anything else (found redundant in
   //--- review).
   //--- NOTE: if a genuinely new breakout fires the SAME bar this stale
   //--- exit closes the position, CheckForEntry() (called right after
   //--- this in OnTick) can re-enter immediately - intentional, and
   //--- consistent with the validated Python model's own event
   //--- sequencing (sim_stale's `i < last_exit` boundary allows exactly
   //--- this: a fresh signal at the exit bar itself is not blocked).
   if(InpUseStaleExit && g_entryATR > 0.0)
     {
      datetime opTime = (datetime)PositionGetInteger(POSITION_TIME);
      int barsHeld = (int)iBarShift(_Symbol, PERIOD_M5, opTime, false);
      //--- v1.10: barsHeld is the fill bar's shift from bar 0, but the bar
      //--- being judged (iClose(...,1) below) is bar 1 - so bars elapsed
      //--- since the fill is barsHeld-1, the simulators' kk-fill_i. Was
      //--- `barsHeld >= InpStaleBars`, which exited one bar early.
      if(barsHeld - 1 >= InpStaleBars)
        {
         double curClose = iClose(_Symbol, PERIOD_M5, 1);
         double openPx = PositionGetDouble(POSITION_PRICE_OPEN);
         double profitATR = (g_posDir > 0 ? (curClose - openPx) : (openPx - curClose)) / g_entryATR;
         if(profitATR < InpStaleMinProfitATR)
            CloseCurrentPosition("STALE");
        }
     }
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
   //--- v1.11: sr<0.0 (missing D1 history) deliberately falls through here
   //--- and lets the entry proceed - fail-OPEN, matching SRDistance()'s own
   //--- header comment and this project's established Meridian_EA.mq5
   //--- convention, not a bug (see that header and v1.11's changelog item 4).
   if(sr >= 0.0 && sr < InpMinSRDistATR) return;

   if(InpUseH4TrendFilter && !H4TrendAgrees(isBuy)) return;

   if(AureliusBlocksEntry(breakoutDir)) return;

   double px = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = isBuy ? px - InpSafetyStopATR * atr : px + InpSafetyStopATR * atr;
   double lots = LotSize(atr);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   bool ok = isBuy ? trade.Buy(lots, _Symbol, px, sl, 0.0, InpTradeComment)
                    : trade.Sell(lots, _Symbol, px, sl, 0.0, InpTradeComment);
   if(ok)
     {
      SyncPositionState();
      g_entryATR = atr;
     }
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

   //--- "M5" literal, matching Aurelius_EA.mq5's own writer-side name -
   //--- see its header note.
   g_aurGVarName = "AURELIUS_POSDIR_M5_" + _Symbol;

   g_h4EmaHandle = iMA(_Symbol, PERIOD_H4, InpH4EMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_h4EmaHandle == INVALID_HANDLE)
     {
      Print("Vanguard EA: failed to create H4 EMA handle. Error ", GetLastError());
      return(INIT_FAILED);
     }

   SeedVWAP();
   SyncPositionState();
   g_lastBarTime = 0;
   g_swingWarm = false;   // v1.10: rebuild swing state from history on the first new bar (WarmUpSwingState())
   ClearReversalRetry();

   //--- v1.11 (header bug 1): a position already open at attach (restart/
   //--- recompile/input change) needs g_entryATR recomputed from history -
   //--- nothing else ever sets it in that case. RecomputeEntryATR() itself
   //--- leaves g_entryATRRestorePending=true (retried from OnTick) if the
   //--- needed history isn't synced yet.
   g_entryATR = 0.0;
   g_entryATRRestorePending = false;
   if(g_ticket != 0) RecomputeEntryATR();

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

   if(g_h4EmaHandle != INVALID_HANDLE) IndicatorRelease(g_h4EmaHandle);
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   if(g_ticket != 0 && IsFridayFlattenTime())
     {
      SyncPositionState();
      if(g_ticket != 0) CloseCurrentPosition("FRIDAY");
     }

   //--- v1.10: a failed REVERSAL close is retried every tick, not left to
   //--- the next (edge-triggered, so usually never-coming) breakout.
   RetryReversalClose();

   //--- tick-level giveback-to-breakeven exit (InpUseGivebackExit, v1.05
   //--- candidate - see header). Checked every tick, not gated on a new
   //--- bar, so the live peak-favorable-excursion tracking matches the
   //--- Python research's intrabar high/low peak at least as closely as
   //--- possible (real ticks are a finer read than Python's per-bar H/L,
   //--- never coarser - conservative direction, catches a giveback at
   //--- least as early as the model that was validated, never later).
   if(InpUseGivebackExit && g_ticket != 0 && PositionSelectByTicket(g_ticket))
     {
      if(g_gbTicket != g_ticket) { g_gbTicket = g_ticket; g_gbPeakFav = 0.0; }
      double entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
      double cur     = (g_posDir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double fav     = (g_posDir > 0) ? (cur - entryPx) : (entryPx - cur);
      if(fav > g_gbPeakFav) g_gbPeakFav = fav;
      if(g_gbPeakFav >= InpGivebackMinPeak && g_gbPeakFav < InpGivebackPeakCutoff && fav <= InpGivebackThreshold)
         CloseCurrentPosition("GIVEBACK");
     }

   if(!IsNewBar()) return;

   double vwapPrev = g_vwapValue;
   UpdateVWAP();
   //--- v1.10: replays bars 2..N first (once per attach, retried each new
   //--- bar until history is available), so bar 1 below is processed
   //--- against the same swing state a never-restarted EA would hold.
   if(!g_swingWarm) g_swingWarm = WarmUpSwingState();
   //--- v1.11: retry the entry-ATR restore (header bug 1) until history was
   //--- ready for it, same retry-until-ready shape as g_swingWarm above.
   if(g_entryATRRestorePending) RecomputeEntryATR();
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
      g_lastAurDir = ReadAureliusDir();
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
