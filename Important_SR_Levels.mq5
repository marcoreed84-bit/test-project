//+------------------------------------------------------------------+
//|                                           Important_SR_Levels.mq5 |
//|  Historic support/resistance fractal levels, with a TOUCH COUNT   |
//|  per level so you can actually see whether price has respected    |
//|  it (touches=1 means untested; touches=5 means it's been bounced  |
//|  off repeatedly) - built to answer "did Bitcoin actually respect  |
//|  these levels", not just draw lines.                              |
//|                                                                    |
//|  Per direct request: this shows MAJOR levels only, not minor       |
//|  noise - InpMinTouchesToShow (default 2) hides any level until it |
//|  has actually been touched/respected that many times, and when    |
//|  the chart is full (InpMaxLevels), the LEAST-touched level is     |
//|  dropped first, so what stays on screen is always the most-tested |
//|  levels, not just the newest ones.                                 |
//|                                                                    |
//|  Opus-reviewed before shipping - 4 must-fix bugs found in the      |
//|  first rewrite, all fixed here:                                    |
//|   1. The incremental re-scan window was 2 bars too wide, so the   |
//|      newest 3 confirmed pivots got re-registered (touches++) on   |
//|      every single tick with no new bar - a level could read x200  |
//|      in an hour on fast-moving BTC. Fixed: re-scan window is now  |
//|      exactly the bars that could not have been fully confirmed    |
//|      last call, no extra margin.                                  |
//|   2. If the terminal ever resets prev_calculated to 0 (a history   |
//|      reload/gap-fill), the old scan used to run AGAIN on top of   |
//|      the already-built level list, roughly doubling every count. |
//|      Fixed: a prev_calculated==0 call now clears everything first.|
//|   3. If the ATR indicator wasn't finished calculating yet on the  |
//|      very first call (common right after attaching), the function |
//|      used to silently give up AND tell MT5 the whole history was  |
//|      already handled - so the real backfill scan never happened   |
//|      at all. Fixed: returns 0 on that failure, so MT5 retries the |
//|      full scan on the next tick instead of skipping it forever.   |
//|   4. ONE current ATR value was used to decide which pivots merge  |
//|      together, across the WHOLE of history - on BTC, which has    |
//|      gone from ~$300 to five/six figures, that means old pivots   |
//|      from the $300 era get merged using TODAY's (much bigger)     |
//|      ATR, collapsing genuinely distinct old levels into one.      |
//|      Fixed: each pivot now uses the ATR AS IT WAS AT THAT BAR,    |
//|      not today's value.                                           |
//|  Plus two minor fixes: a flat-top/flat-bottom tie (two neighbour  |
//|  bars with the exact same high/low) could register as two          |
//|  separate pivots instead of one; and InpMaxLevels/                |
//|  InpLeftRightWindow are now validated in OnInit instead of being  |
//|  able to silently misbehave on a bad input value.                  |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property version   "1.13"
//--- 1.13: Per report, with the key clue - "gold is specific, maybe its
//--- [p]aused, bitcoin is working fine... silver is also [p]aused".
//--- Found the real per-tick cost the v1.11/v1.12 fixes hadn't touched:
//--- ScanHigherTF() called CopyRates(0, 5000) - a genuinely expensive
//--- copy of 5000 full rate records - UNCONDITIONALLY on every single
//--- tick, for each of the three higher-timeframe layers (H4/D1/W1),
//--- with the "has a new bar actually closed" check only happening
//--- AFTER that copy already ran. This cost scales directly with tick
//--- frequency, and Gold/Silver are far more actively quoted (many more
//--- ticks/second in active sessions) than BTC typically is on a CFD
//--- feed - explaining exactly the reported split. Fixed: gated with a
//--- single cheap iTime() call FIRST, same pattern ScanRecentHL already
//--- used for its own D1 check - CopyRates now only runs on the rare
//--- tick where a new H4/D1/W1 bar has actually just closed.
//--- 1.12: Opus-reviewed. Confirmed v1.11's per-second throttle is safe
//--- (no scan/registration work can be skipped by it - verified every
//--- early-return in the intraday scan and all three ScanHigherTF calls
//--- happen before the throttle check, and the one-shot diagnostic
//--- prints all happen before it too), but found a BIGGER, more direct
//--- freeze cause the throttle didn't touch: ScanHigherTF() drew every
//--- single level INLINE during the scan itself (RegisterTouchG ->
//--- RedrawLevelG on every touch) - a full H4/D1/W1 rescan (which
//--- happens from scratch every time a new bar closes on that
//--- timeframe, not incrementally) can process thousands of pivots,
//--- each one doing its own synchronous ObjectFind+7 setters DURING the
//--- scan - roughly 4000 synchronous chart calls in one blocking
//--- OnCalculate call at every H4 close. Fixed: RegisterTouchG() gained
//--- a drawInline parameter (default true, so the intraday layer's
//--- behaviour is unchanged); ScanHigherTF passes false - the level
//--- array is still built/merged/evicted exactly the same, drawing is
//--- simply deferred to ApplyTopNFilter (already called once per
//--- OnCalculate, already throttled), which only ever needs to draw the
//--- InpShowTopN survivors per layer instead of every intermediate
//--- pivot. Also fixed two silent-failure bugs: ScanHigherTF() and
//--- ScanRecentHL() both used to mark themselves "done" (updating the
//--- last-bar-time tracker, and in ScanHigherTF's case also wiping
//--- existing objects) BEFORE confirming the data they needed had
//--- actually loaded - a transient "not ready yet" failure (routine
//--- right after attach) left that layer blank with no retry until the
//--- next bar closed on that timeframe (up to a week for weekly), with
//--- nothing printed to explain why. Both now validate first, commit
//--- state only on success, and print on failure. Also added input
//--- validation for InpDWWindow/InpDWMaxLevels (previously only the
//--- intraday layer's equivalents were validated - a 0 or negative
//--- value here could crash the indicator), and fixed the OnInit
//--- journal line still hardcoding "v1.10" regardless of the actual
//--- running version.
//--- 1.11: Per report - "the support and resistance line indicator are
//--- making the charts freeze". Found it: the TopN filter and every
//--- label refresh (4 level layers x ObjectFind/ObjectCreate/ObjectSet
//--- each) ran UNCONDITIONALLY on every single OnCalculate call - MT5
//--- calls that on every new TICK, not just every new bar, so on a
//--- fast-ticking symbol this was dozens of synchronous chart-object
//--- calls potentially several times a second, forever - same class of
//--- bug already found/fixed in TradePanel_EA this session. Throttled
//--- to once per second (GetTickCount64-based) - labels only need to
//--- track "now" roughly, not tick-exactly.
//--- 1.10: Per direct request - "maybe just change the support and
//--- resistance indicator... focus to show the support and resistance
//--- levels according to the 4 hour timeframe and up, and maybe include
//--- the 3 days high and low, open and close". Two changes:
//--- (1) The intraday (chart's own timeframe) fractal layer is now OFF
//--- by default (InpShowIntradayLevels) - noisy/minor on a fast chart
//--- timeframe compared to H4+. New H4 layer added (InpShowH4Levels,
//--- on by default), reusing the exact same ScanHigherTF() construction
//--- already used for daily/weekly, so the indicator now defaults to
//--- showing H4 + daily + weekly fractal S/R, with intraday available
//--- as an opt-in. (2) The existing Aurelius-style recent-N-day
//--- high/low layer (already defaulting to 3 days) now optionally also
//--- draws the OPEN of the oldest of those days and the CLOSE of the
//--- most recent completed day (InpShowRecentOC, on by default) -
//--- together with the existing high/low this reads as a single
//--- synthetic N-day OHLC bar, each with its own colour and right-edge
//--- label, same pattern as everything else in this file.
//--- 1.09: Per direct request - "we need to filter the important ones
//--- somehow, this is too many" - a screenshot showed 10+ overlapping
//--- S/R lines crowding a single BTC trading range. InpMinTouchesToShow
//--- was only ever a FLOOR (show nothing below N touches), never a CAP -
//--- a busy range can produce a dozen+ levels that all individually
//--- clear it. New InpShowTopN (default 6) adds a hard cap: only the
//--- top N levels BY TOUCH COUNT, per layer (intraday/daily/weekly each
//--- capped independently), are actually drawn on the chart - everything
//--- else that clears the touch threshold keeps accumulating touches
//--- internally and can rank back into the top N later, it's just not
//--- drawn while it's outside it. New ApplyTopNFilter(), called every
//--- OnCalculate right before the label refresh.
//--- 1.08: Per direct request - "can we label the lines at the end" -
//--- the touch-count label (InpShowTouchLabels) used to sit at the
//--- level's last-touch time, which could be buried mid-chart, easy to
//--- miss. Moved to the chart's RIGHT EDGE instead, and now includes
//--- the S/R letter (" S x3" / " R x5"), not just the touch count.
//--- New RefreshRightEdgeLabels(), called every OnCalculate (not just
//--- when a level is actually touched) so the label keeps tracking
//--- forward with "now" instead of going stale between touches. Also
//--- added matching right-edge labels ("3D Hi"/"3D Lo") to the recent-HL
//--- lines from v1.07, which previously had no visible label at all -
//--- only a tooltip on hover.
//--- 1.07: Added a second, completely independent construction per
//--- direct request - "the levels you have in the aurelius ea for
//--- support and resistance, the grey dashed lines, gold seems to
//--- respect these levels." Checked Aurelius_EA.mq5's SRLevels()/
//--- SRDistanceATR() (lines ~2846-2871): it is NOT a fractal/touch-count
//--- system at all - just the max high / min low of the prior
//--- InpSRDays (default 3) COMPLETED daily bars, recomputed fresh every
//--- day, drawn dashed in a dimmed silver (InpColSR). This is a real,
//--- live-confirmed construction on gold (the combined slope x S/R
//--- block, REAL-CONFIRMED 2026-09-24) - NOT independently validated on
//--- BTC, just offered here because it structurally sidesteps every
//--- problem the fractal layers above have been hitting: no old-era
//--- levels (nothing to look back further than InpRecentHLDays days),
//--- no eviction competition (only ever 2 lines total), no chop-
//--- starvation (always anchored to the last few days by construction).
//--- New ScanRecentHL() function, InpShowRecentHL/InpRecentHLDays/
//--- InpRecentHLColor inputs, redraws once per new completed daily bar.
//--- 1.06: User reported (with a chart screenshot) that levels only ever
//--- appeared well ABOVE and well BELOW the price band the market had
//--- actually been trading in for days, with a visible gap of NO levels
//--- exactly where price currently is. Real design flaw, not a bug in
//--- the strict sense: eviction always drops the least-touched level,
//--- and every brand-new pivot starts at touches=1 - so during an
//--- active chop, each fresh intraday swing creates a new 1-touch level
//--- that is immediately the weakest thing in the array and gets evicted
//--- by older levels elsewhere in the lookback window that already
//--- reached 2+ touches, before the current zone's level ever got a
//--- SECOND touch to clear InpMinTouchesToShow and actually get drawn.
//--- Net effect: only old, already-proven levels survive long-term,
//--- systematically starving out wherever price is RIGHT NOW. Fixed:
//--- new InpRecentProtectDays (default 14) - a level formed within this
//--- many days of the newest bar can never be evicted, however few
//--- touches it has, giving it time to actually prove itself before
//--- being judged against older, more-tested levels. Falls back to
//--- unprotected least-touched eviction only if literally every level in
//--- the array happens to be recent (so the cap still can't be exceeded).
//--- 1.05: User reported "40 levels found" in the journal but still zero
//--- visible lines on the chart, and changing the colour inputs made no
//--- difference at all - a strong sign the lines never actually existed
//--- on the chart in the first place, since a colour change on a line
//--- that was never drawn is naturally invisible too. Root cause found:
//--- ObjectCreate()'s return value was NEVER checked anywhere in this
//--- file. If it silently fails - a name collision with some other
//--- object/indicator on the same chart, an invalid price, anything -
//--- the level stays tracked in the g_levels array exactly as if it had
//--- drawn fine, so the scan summary happily reports "N levels found"
//--- while the chart has nothing on it, with zero way to tell from the
//--- journal. Fixed: ObjectCreate's result is now checked, and a failure
//--- logs the exact object name, price and GetLastError() code. Also
//--- added LogLevelDiagnostics(), printed after every scan (intraday,
//--- daily, weekly): counts how many tracked levels ACTUALLY have a
//--- matching object on the chart right now (via ObjectFind), and prints
//--- the price range those levels span next to the current bid price -
//--- so "found but never drawn" (this bug) and "drawn but off-screen"
//--- (a different, already-considered cause) are told apart by the
//--- journal instead of guessed at.
//--- 1.04: Added a SECOND, independent layer of levels built from DAILY
//--- and WEEKLY bars directly (via CopyRates(_Symbol, PERIOD_D1/W1, ...)),
//--- not just fractals on whatever timeframe the chart happens to be on.
//--- Per direct request: "we would need more recent support and
//--- resistance as well, there should be daily support and resistance
//--- levels, weekly?" - the original scan only ever sees pivots on the
//--- chart's own timeframe, so a daily/weekly swing high or low that
//--- isn't ALSO a fractal on (say) M15 could be missed or show up late.
//--- These two new layers run the exact same fractal-confirm + ATR-
//--- clustering + touch-count logic as the main scan (refactored into
//--- shared helper functions that take the level array/prefix/colors as
//--- parameters instead of hardcoded globals), just fed D1/W1 bars and
//--- drawn in their own colors so you can tell the three layers apart.
//--- Each only re-scans when a NEW daily/weekly bar has actually closed
//--- (checked via the newest closed bar's time), not every tick - D1/W1
//--- history is small enough (a few thousand / a few hundred bars) that
//--- a full re-scan on that rare event is cheap and simpler/safer than
//--- replicating the incremental prev_calculated bookkeeping for a
//--- second and third data source.
//--- 1.03: Fixed the real reason the journal showed "39 visible levels"
//--- but the user still only saw a couple of lines on the actual BTC
//--- chart. Root cause: InpAtrMultiplier x ATR is a DOLLAR distance -
//--- back when BTC traded at a few hundred dollars, ATR was tiny, so
//--- pivots from that era clustered extremely tightly and accumulated
//--- huge touch counts over the years BTC spent in that price range.
//--- Since eviction (when over InpMaxLevels) always drops the
//--- LEAST-touched level, those old high-touch-count clusters from
//--- BTC's early, cheap history were winning every eviction and
//--- crowding out genuinely current, tradeable levels - and since
//--- they're also all priced far below BTC's current price, they'd
//--- render bunched together off-screen from wherever you're actually
//--- looking on the chart. Added InpLookbackDays (default 730, ~2
//--- years) - pivots older than this are no longer even ELIGIBLE to be
//--- registered as a level at all, so the old cheap-era clusters can
//--- never form or compete for the level slots in the first place. Set
//--- to 0 to go back to scanning all available history.
//--- 1.02: Fixed two real "silently never scans" bugs, found while
//--- diagnosing a report of attaching this and seeing no levels at
//--- all. Both early "not enough bars yet" checks in OnCalculate were
//--- returning rates_total (meaning "fully handled") instead of 0 -
//--- if MT5 called this indicator before the symbol's full history had
//--- loaded, it would claim the backfill was already done and NEVER
//--- actually run it once more history arrived. Also added two Print
//--- lines that were missing entirely before: one in OnInit confirming
//--- the indicator actually attached and what settings it's using, and
//--- one after the first full backfill showing how many pivots were
//--- found vs. how many cleared InpMinTouchesToShow and are actually
//--- visible - previously this indicator only ever printed on an
//--- ERROR, so "nothing in the Experts journal" told you nothing about
//--- whether it was running normally or not running at all.
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== Fractal detection ==="
input int      InpLeftRightWindow  = 5;     // Fractal window (candles confirmed closed on each side)
input int      InpAtrPeriod        = 14;    // ATR period used for the volatility filter below

input group "=== Volatility-based level clustering ==="
input double   InpAtrMultiplier    = 1.5;   // Pivots within this many ATR (AS OF THAT PIVOT'S OWN BAR, not
                                             // today's ATR) of an existing level MERGE into it (touch count
                                             // +1) instead of creating a new, separate line - this is what
                                             // keeps BTC's noisy micro-swings from spawning dozens of
                                             // near-duplicate levels
input int      InpMaxLevels        = 40;    // Hard cap on how many levels stay on the chart at once - if
                                             // exceeded, the LEAST-touched level is dropped first (keeps the
                                             // most-respected, most-informative levels, not just the newest)

input group "=== \"Major levels only\" filter ==="
input int      InpMinTouchesToShow = 2;     // Per direct request: a level only gets drawn once it's been
                                             // touched/respected at least this many times - a single
                                             // untested pivot is noise, not a major level. Set to 1 to show
                                             // every pivot immediately (back to the old behavior).
input int      InpShowTopN         = 6;     // v1.09 FIX: "we need to filter the important ones somehow,
                                             // this is too many" - InpMinTouchesToShow alone could still
                                             // let a dozen+ levels all clear the bar and flood the chart
                                             // (reported: a 1-hour BTC range showing 10+ overlapping S/R
                                             // lines). This caps it HARD: only the top N levels BY TOUCH
                                             // COUNT, per layer (intraday/daily/weekly each get their own
                                             // top N), are actually drawn - everything else that clears
                                             // InpMinTouchesToShow still counts toward touches internally,
                                             // it just isn't shown until it ranks back into the top N. Set
                                             // to 0 to disable (show everything that clears the touch
                                             // threshold, the old behavior).
input int      InpLookbackDays     = 730;   // v1.03 FIX: only pivots from the last N calendar days are even
                                             // ELIGIBLE to be registered as a level (0 = no limit, scan
                                             // all available history). Added because the clustering distance
                                             // (InpAtrMultiplier x ATR) was tiny back when BTC traded at a
                                             // few hundred dollars - old pivots from that era cluster into a
                                             // handful of extremely high-touch-count "super levels" that
                                             // then win every eviction and crowd out genuinely current,
                                             // relevant levels. 730 days (~2 years) keeps the level list
                                             // anchored to BTC's current price regime instead of its entire
                                             // multi-order-of-magnitude price history.
input int      InpRecentProtectDays = 14;   // v1.06 FIX: a level formed within this many days of the newest
                                             // bar can NEVER be evicted, however few touches it has. Without
                                             // this, every brand-new pivot starts at touches=1 and is
                                             // immediate eviction-bait against older levels elsewhere in the
                                             // lookback window that already reached 2+ touches - so the price
                                             // zone the market is ACTUALLY in right now could be evicted
                                             // before it ever got the chance to accumulate a second touch,
                                             // leaving nothing but old, already-proven levels on screen and a
                                             // visible gap exactly where price has been trading for days. Set
                                             // to 0 to disable (go back to pure least-touched eviction).

input group "=== Display ==="
input color    InpSupportColor     = clrLime;
input color    InpResistanceColor  = clrRed;
input int      InpLineWidth        = 1;
input bool     InpShowTouchLabels  = true;  // small "xN" text label showing each line's touch count - the
                                             // actual answer to "was this respected", placed at the time of
                                             // its most recent touch
input color    InpLabelColor       = clrWhite;
input int      InpLabelFontSize    = 8;

input group "=== Intraday levels (the chart's own timeframe) ==="
input bool     InpShowIntradayLevels = false;  // v1.10: default OFF - per direct request ("maybe just change
                                                // the support and resistance indicator... focus to show the
                                                // support and resistance levels according to the 4 hour
                                                // timeframe and up") - fractal pivots on a fast intraday
                                                // chart timeframe are noisy/minor compared to H4+; the
                                                // InpLeftRightWindow/InpAtrMultiplier/InpMaxLevels/
                                                // InpLookbackDays/InpRecentProtectDays inputs above still
                                                // configure this layer whenever it's switched back on

input group "=== H4 / Daily / Weekly levels (independent of the chart's own timeframe) ==="
input bool     InpShowH4Levels       = true;   // v1.10 NEW - per direct request, "4 hour timeframe and up" -
                                                // scans PERIOD_H4 bars directly, same construction as the
                                                // daily/weekly layers below
input bool     InpShowDailyLevels    = true;   // scan PERIOD_D1 bars directly for daily S/R, regardless of
                                                // what timeframe this chart is actually showing
input bool     InpShowWeeklyLevels   = true;   // same, for PERIOD_W1
input int      InpDWWindow           = 2;      // fractal window on H4/D1/W1 bars - smaller than the intraday
                                                // one since each bar already represents a large chunk of time
input int      InpDWMinTouchesToShow = 2;      // "major levels only" filter, same idea as InpMinTouchesToShow
input int      InpDWMaxLevels        = 20;     // cap per layer (H4/daily/weekly each get their own 20)
input int      InpDWLookbackDays     = 1825;   // ~5 years - H4/daily/weekly pivots are rarer and more durable
                                                // than intraday ones, so a longer lookback makes sense here
input color    InpH4SupportColor       = clrYellowGreen;
input color    InpH4ResistanceColor    = clrTomato;
input color    InpDailySupportColor    = clrAqua;
input color    InpDailyResistanceColor = clrOrange;
input color    InpWeeklySupportColor    = clrDodgerBlue;
input color    InpWeeklyResistanceColor = clrMagenta;

input group "=== Recent N-day high/low (Aurelius-style rolling channel) ==="
input bool     InpShowRecentHL      = true;      // A completely different, much simpler construction, lifted
                                                  // from Aurelius_EA's own SRLevels()/SRDistanceATR() - just the
                                                  // max high / min low of the prior InpRecentHLDays COMPLETED
                                                  // daily bars, recomputed fresh every day. No fractal
                                                  // detection, no touch accumulation, no eviction competition -
                                                  // always anchored to the last few days by construction, so it
                                                  // can never be crowded out by old levels or starved during
                                                  // chop the way the fractal layers above can. This exact
                                                  // construction is REAL-CONFIRMED on live GOLD (2026-09-24,
                                                  // the combined slope x S/R block) - NOT independently
                                                  // validated on BTC, just offered here since it structurally
                                                  // sidesteps the problems the fractal layers have been hitting.
input int      InpRecentHLDays      = 3;         // Matches Aurelius's own InpSRDays default
input color    InpRecentHLColor     = C'120,144,176';  // same dimmed silver Aurelius uses, so a static recent
                                                  // level never competes for attention with the live chart
input bool     InpShowRecentOC      = true;      // v1.10 NEW - per direct request ("include the 3 days high
                                                  // and low, open and close") - two more lines: the OPEN of
                                                  // the OLDEST of the InpRecentHLDays completed days, and the
                                                  // CLOSE of the most recent completed day - together with
                                                  // the existing Hi/Lo this reads as a single synthetic
                                                  // N-day OHLC bar
input color    InpRecentOpenColor   = C'176,144,120';  // dimmed orange-ish, distinct from the Hi/Lo silver
input color    InpRecentCloseColor  = C'144,176,120';  // dimmed green-ish

#define PFX   "SRL_"
#define PFX_H4 "SRLH4_"
#define PFX_D "SRLD_"
#define PFX_W "SRLW_"
#define PFX_RHL "SRLRHL_"

struct SRLevel
  {
   double   price;
   bool     isSupport;
   datetime firstTime;
   datetime lastTime;
   int      touches;
   string   lineName;
   string   labelName;
  };

SRLevel  g_levels[];
SRLevel  g_levelsH4[];
SRLevel  g_levelsD[];
SRLevel  g_levelsW[];
int      g_atrHandle   = INVALID_HANDLE;
int      g_atrHandleH4 = INVALID_HANDLE;
int      g_atrHandleD  = INVALID_HANDLE;
int      g_atrHandleW  = INVALID_HANDLE;
datetime g_lastH4BarTime     = 0;
datetime g_lastDailyBarTime  = 0;
datetime g_lastWeeklyBarTime = 0;
datetime g_lastRecentHLBarTime = 0;
ulong    g_lastUiRefreshMs = 0;   // v1.11 FIX - see its own use in OnCalculate
double   g_recentHLHi = 0.0;
double   g_recentHLLo = 0.0;
double   g_recentOpen  = 0.0;
double   g_recentClose = 0.0;
bool     g_recentHLReady = false;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpLeftRightWindow <= 0)
     {
      Print("Important_SR_Levels: InpLeftRightWindow must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpMaxLevels <= 0)
     {
      Print("Important_SR_Levels: InpMaxLevels must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   //--- v1.12 FIX (Opus-found): the H4/daily/weekly layer's own window/
   //--- cap inputs were never validated the way the intraday ones above
   //--- are - InpDWWindow<=0 makes every bar register as a pivot (0) or
   //--- indexes rates[] with a negative offset and crashes (negative);
   //--- InpDWMaxLevels<=0 lets RegisterTouchG's eviction logic access
   //--- levels[0] on an empty array (array-out-of-range, indicator
   //--- removed).
   if(InpDWWindow <= 0)
     {
      Print("Important_SR_Levels: InpDWWindow must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpDWMaxLevels <= 0)
     {
      Print("Important_SR_Levels: InpDWMaxLevels must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_atrHandle = iATR(_Symbol, _Period, InpAtrPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("Important_SR_Levels: failed to create ATR handle.");
      return(INIT_FAILED);
     }
   if(InpShowH4Levels)
     {
      g_atrHandleH4 = iATR(_Symbol, PERIOD_H4, InpAtrPeriod);
      if(g_atrHandleH4 == INVALID_HANDLE)
        {
         Print("Important_SR_Levels: failed to create H4 ATR handle.");
         return(INIT_FAILED);
        }
     }
   if(InpShowDailyLevels)
     {
      g_atrHandleD = iATR(_Symbol, PERIOD_D1, InpAtrPeriod);
      if(g_atrHandleD == INVALID_HANDLE)
        {
         Print("Important_SR_Levels: failed to create daily ATR handle.");
         return(INIT_FAILED);
        }
     }
   if(InpShowWeeklyLevels)
     {
      g_atrHandleW = iATR(_Symbol, PERIOD_W1, InpAtrPeriod);
      if(g_atrHandleW == INVALID_HANDLE)
        {
         Print("Important_SR_Levels: failed to create weekly ATR handle.");
         return(INIT_FAILED);
        }
     }
   ArrayResize(g_levels, 0);
   ArrayResize(g_levelsH4, 0);
   ArrayResize(g_levelsD, 0);
   ArrayResize(g_levelsW, 0);
   g_lastH4BarTime     = 0;
   g_lastDailyBarTime  = 0;
   g_lastWeeklyBarTime = 0;
   g_lastRecentHLBarTime = 0;
   g_recentHLReady = false;
   //--- v1.02: unconditional confirmation line - previously this
   //--- indicator only ever printed on an ERROR, so "nothing in the
   //--- journal" told you nothing about whether it was actually
   //--- running. Now it always confirms attach + settings here.
   PrintFormat("Important_SR_Levels v1.12 OnInit: %s %s  window=%d  minTouches=%d  maxLevels=%d  atrMult=%.2f  "
               "intraday=%s  H4=%s  daily=%s  weekly=%s",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpLeftRightWindow, InpMinTouchesToShow, InpMaxLevels, InpAtrMultiplier,
               InpShowIntradayLevels ? "on" : "off", InpShowH4Levels ? "on" : "off",
               InpShowDailyLevels ? "on" : "off", InpShowWeeklyLevels ? "on" : "off");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, PFX);
   ObjectsDeleteAll(0, PFX_H4);
   ObjectsDeleteAll(0, PFX_D);
   ObjectsDeleteAll(0, PFX_W);
   ObjectsDeleteAll(0, PFX_RHL);
   if(g_atrHandle   != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   if(g_atrHandleH4 != INVALID_HANDLE) IndicatorRelease(g_atrHandleH4);
   if(g_atrHandleD  != INVALID_HANDLE) IndicatorRelease(g_atrHandleD);
   if(g_atrHandleW  != INVALID_HANDLE) IndicatorRelease(g_atrHandleW);
  }

//+------------------------------------------------------------------+
//| Draw (or move/update) one level's chart objects. Does nothing if  |
//| it hasn't reached InpMinTouchesToShow yet - that's the "major     |
//| levels only, not minor noise" filter.                             |
//+------------------------------------------------------------------+
void RedrawLevelG(SRLevel &lvl, const int minTouchesToShow, const color supCol, const color resCol)
  {
   if(lvl.touches < minTouchesToShow) return;

   color col = lvl.isSupport ? supCol : resCol;

   if(ObjectFind(0, lvl.lineName) < 0)
     {
      //--- v1.05 FIX: ObjectCreate's return value was never checked - if
      //--- it silently failed (name collision with another object on
      //--- this chart, invalid price, etc.) the level was still tracked
      //--- in g_levels as if it had drawn fine, so the scan summary could
      //--- say "N levels found" while literally zero lines existed on
      //--- the chart, with no way to tell from the journal. Now logged.
      if(!ObjectCreate(0, lvl.lineName, OBJ_HLINE, 0, 0, lvl.price))
        {
         PrintFormat("Important_SR_Levels: ObjectCreate FAILED for %s at price %s - error %d",
                     lvl.lineName, DoubleToString(lvl.price, _Digits), GetLastError());
         return;
        }
      ObjectSetInteger(0, lvl.lineName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, lvl.lineName, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, lvl.lineName, OBJPROP_COLOR, col);
   ObjectSetInteger(0, lvl.lineName, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, lvl.lineName, OBJPROP_WIDTH, InpLineWidth);
   ObjectSetDouble(0, lvl.lineName, OBJPROP_PRICE, lvl.price);
   ObjectSetString(0, lvl.lineName, OBJPROP_TOOLTIP,
                    (lvl.isSupport ? "Support " : "Resistance ") + DoubleToString(lvl.price, _Digits) +
                    "  touches=" + IntegerToString(lvl.touches) +
                    "  first=" + TimeToString(lvl.firstTime, TIME_DATE) +
                    "  last=" + TimeToString(lvl.lastTime, TIME_DATE));

   if(InpShowTouchLabels)
     {
      //--- v1.08: label moved to the chart's RIGHT EDGE (per direct
      //--- request - "can we label the lines at the end"), instead of
      //--- sitting at the level's last-touch time where it could be
      //--- buried mid-chart. Created here with a placeholder position;
      //--- RefreshRightEdgeLabels() (called every OnCalculate, not just
      //--- when a level is touched) keeps it pinned to "now" so it tracks
      //--- forward with price instead of going stale between touches.
      if(ObjectFind(0, lvl.labelName) < 0)
        {
         ObjectCreate(0, lvl.labelName, OBJ_TEXT, 0, lvl.lastTime, lvl.price);
         ObjectSetInteger(0, lvl.labelName, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, lvl.labelName, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, lvl.labelName, OBJPROP_ANCHOR, ANCHOR_LEFT);
        }
      ObjectSetInteger(0, lvl.labelName, OBJPROP_COLOR, InpLabelColor);
      ObjectSetInteger(0, lvl.labelName, OBJPROP_FONTSIZE, InpLabelFontSize);
     }
  }

//+------------------------------------------------------------------+
//| v1.08: pins every visible level's label to the chart's right edge |
//| ("nowTime"), called every OnCalculate regardless of whether any   |
//| level was actually touched this tick - otherwise a label would    |
//| only move when its level got a new touch, and sit stale (at the   |
//| OLD nowTime from whenever that last happened) in between.         |
//+------------------------------------------------------------------+
void RefreshRightEdgeLabels(SRLevel &levels[], const int minTouchesToShow, const datetime nowTime)
  {
   if(!InpShowTouchLabels) return;
   for(int k = 0; k < ArraySize(levels); k++)
     {
      if(levels[k].touches < minTouchesToShow) continue;
      if(ObjectFind(0, levels[k].labelName) < 0) continue;
      ObjectSetInteger(0, levels[k].labelName, OBJPROP_TIME, 0, nowTime);
      ObjectSetDouble(0, levels[k].labelName, OBJPROP_PRICE, levels[k].price);
      ObjectSetString(0, levels[k].labelName, OBJPROP_TEXT,
                       (levels[k].isSupport ? " S x" : " R x") + IntegerToString(levels[k].touches));
     }
  }

//+------------------------------------------------------------------+
//| v1.09: hard cap on how many levels in one layer are ACTUALLY DRAWN |
//| at once - per direct request ("we need to filter the important    |
//| ones somehow, this is too many"). InpMinTouchesToShow alone is a   |
//| floor, not a cap - a busy range can produce a dozen+ levels that   |
//| all clear it. Ranks the levels that clear the touch threshold by   |
//| touch count (descending) and only keeps the top InpShowTopN drawn  |
//| on the chart; the rest stay fully tracked internally (so they can  |
//| still accumulate touches and re-enter the top N later) but their   |
//| chart objects are removed. Simple selection sort - array is capped |
//| at InpMaxLevels (default 40) so this is cheap even every tick.     |
//+------------------------------------------------------------------+
void ApplyTopNFilter(SRLevel &levels[], const int minTouchesToShow, const int topN,
                      const color supCol, const color resCol)
  {
   if(topN <= 0) return;   // 0 = disabled, old "show everything that clears the threshold" behavior
   int idx[];
   ArrayResize(idx, 0);
   for(int k = 0; k < ArraySize(levels); k++)
     {
      if(levels[k].touches < minTouchesToShow) continue;
      int sz = ArraySize(idx);
      ArrayResize(idx, sz + 1);
      idx[sz] = k;
     }
   int m = ArraySize(idx);
   for(int a = 0; a < m; a++)
     {
      int best = a;
      for(int b = a + 1; b < m; b++)
         if(levels[idx[b]].touches > levels[idx[best]].touches) best = b;
      if(best != a) { int tmp = idx[a]; idx[a] = idx[best]; idx[best] = tmp; }
     }
   for(int a = 0; a < m; a++)
     {
      if(a < topN)
         RedrawLevelG(levels[idx[a]], minTouchesToShow, supCol, resCol);   // ensure it's drawn (idempotent)
      else
        {
         if(ObjectFind(0, levels[idx[a]].lineName) >= 0)  ObjectDelete(0, levels[idx[a]].lineName);
         if(ObjectFind(0, levels[idx[a]].labelName) >= 0) ObjectDelete(0, levels[idx[a]].labelName);
        }
     }
  }

//+------------------------------------------------------------------+
//| v1.05: prints exactly what "N levels found" could not tell you -  |
//| how many of the tracked, visible-threshold-clearing levels have   |
//| an object that ACTUALLY EXISTS on the chart (ObjectFind >= 0),    |
//| and the price range they span vs. the current price - so "found  |
//| but not seen" (ObjectCreate silently failed) and "found and drawn |
//| but nowhere near current price" (off-screen) are told apart.      |
//+------------------------------------------------------------------+
void LogLevelDiagnostics(SRLevel &levels[], const int minTouchesToShow, const string label)
  {
   int tracked = 0, verified = 0;
   double minPrice = DBL_MAX, maxPrice = -DBL_MAX;
   for(int k = 0; k < ArraySize(levels); k++)
     {
      if(levels[k].touches < minTouchesToShow) continue;
      tracked++;
      if(ObjectFind(0, levels[k].lineName) >= 0) verified++;
      if(levels[k].price < minPrice) minPrice = levels[k].price;
      if(levels[k].price > maxPrice) maxPrice = levels[k].price;
     }
   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(tracked == 0)
      PrintFormat("Important_SR_Levels [%s]: 0 levels clear the touch threshold - nothing to draw.", label);
   else
      PrintFormat("Important_SR_Levels [%s]: %d tracked, %d actually verified ON CHART (ObjectFind) - "
                  "price range %s .. %s, current price %s",
                  label, tracked, verified, DoubleToString(minPrice, _Digits), DoubleToString(maxPrice, _Digits),
                  DoubleToString(curPrice, _Digits));
  }

//+------------------------------------------------------------------+
//| Find an existing same-type level within minDistance of price.    |
//| Returns its index in g_levels, or -1 if none is close enough.    |
//+------------------------------------------------------------------+
int FindNearbyLevelG(SRLevel &levels[], const double price, const bool isSupport, const double minDistance)
  {
   int best = -1;
   double bestDist = DBL_MAX;
   for(int k = 0; k < ArraySize(levels); k++)
     {
      if(levels[k].isSupport != isSupport) continue;
      double d = MathAbs(levels[k].price - price);
      if(d < minDistance && d < bestDist) { best = k; bestDist = d; }
     }
   return best;
  }

//+------------------------------------------------------------------+
//| New pivot confirmed at (t, price, isSupport) - merge into an      |
//| existing nearby level (touch++) or create a brand-new one.        |
//| minDistance is the ATR-based clustering distance AS OF THIS       |
//| PIVOT'S OWN BAR, not today's ATR - critical on an instrument like |
//| BTC whose volatility has grown by orders of magnitude over its    |
//| history.                                                          |
//+------------------------------------------------------------------+
void RegisterTouchG(SRLevel &levels[], const datetime t, const double price, const bool isSupport,
                     const double minDistance, const string prefix, const int maxLevels,
                     const int minTouchesToShow, const color supCol, const color resCol,
                     const datetime recentCutoff, const bool drawInline = true)
  {
   //--- v1.12 FIX (Opus-found): drawInline=false (used by ScanHigherTF's
   //--- full-history rescans) skips RedrawLevelG on every single touch -
   //--- a full H4/D1/W1 rescan can process thousands of pivots, each
   //--- previously doing its own ObjectFind+7 setters synchronously
   //--- DURING the scan (~4000 chart calls in one blocking OnCalculate
   //--- call at every H4 close) - this is the real, bigger freeze cause
   //--- the v1.11 per-tick throttle didn't touch. The level array is
   //--- still built/merged/evicted exactly the same either way; only the
   //--- chart drawing is skipped here, since ApplyTopNFilter (called
   //--- once per OnCalculate, already throttled) draws the surviving top
   //--- N for this layer moments later anyway - drawing every single
   //--- intermediate pivot mid-scan, most of which get evicted or never
   //--- rank into the top N, was always wasted synchronous work.
   int idx = FindNearbyLevelG(levels, price, isSupport, minDistance);
   if(idx >= 0)
     {
      //--- merged into an existing level: nudge its price toward the
      //--- average of all touches so far (keeps the line representative
      //--- of the whole cluster, not stuck on the very first touch) and
      //--- extend its "last touched" time
      levels[idx].price = (levels[idx].price * levels[idx].touches + price) / (levels[idx].touches + 1);
      levels[idx].touches++;
      levels[idx].lastTime = t;
      if(drawInline) RedrawLevelG(levels[idx], minTouchesToShow, supCol, resCol);
      return;
     }

   //--- genuinely new level
   int n = ArraySize(levels);
   if(n >= maxLevels)
     {
      //--- v1.06 FIX: drop the least-touched level, but NEVER one formed
      //--- within the last InpRecentProtectDays - that's what used to let
      //--- a current price zone get evicted while it still only had 1
      //--- touch, before it ever had a chance to prove itself. Only look
      //--- among levels older than the protection window; if literally
      //--- every level happens to be recent (e.g. indicator just
      //--- attached), fall back to evicting the least-touched regardless,
      //--- so the array can't grow past maxLevels forever.
      int weakest = -1;
      for(int k = 0; k < n; k++)
        {
         if(recentCutoff != 0 && levels[k].firstTime >= recentCutoff) continue;
         if(weakest < 0 || levels[k].touches < levels[weakest].touches) weakest = k;
        }
      if(weakest < 0)
        {
         weakest = 0;
         for(int k = 1; k < n; k++)
            if(levels[k].touches < levels[weakest].touches) weakest = k;
        }
      ObjectDelete(0, levels[weakest].lineName);
      ObjectDelete(0, levels[weakest].labelName);
      levels[weakest] = levels[n - 1];
      ArrayResize(levels, n - 1);
      n = n - 1;
     }

   ArrayResize(levels, n + 1);
   levels[n].price     = price;
   levels[n].isSupport = isSupport;
   levels[n].firstTime = t;
   levels[n].lastTime  = t;
   levels[n].touches   = 1;
   levels[n].lineName  = prefix + (isSupport ? "S_" : "R_") + IntegerToString((long)t);
   levels[n].labelName = prefix + "lbl_" + (isSupport ? "S_" : "R_") + IntegerToString((long)t);
   if(drawInline) RedrawLevelG(levels[n], minTouchesToShow, supCol, resCol);
  }

//+------------------------------------------------------------------+
//| Daily/weekly layer: scans a higher timeframe's own bars directly  |
//| via CopyRates, completely independent of the chart's timeframe.   |
//| Only does a full rescan when a NEW bar on that timeframe has      |
//| actually closed (cheap: D1/W1 history is a few thousand bars at   |
//| most, so a full rescan on that rare event is simpler and safer    |
//| than replicating the main scan's incremental bookkeeping twice    |
//| more).                                                             |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Aurelius-style recent N-day high/low - lifted directly from that  |
//| EA's own SRLevels()/UpdateLevelLines() pattern: just the max high |
//| / min low of the prior InpRecentHLDays COMPLETED D1 bars (shift 1 |
//| onward, so today never leaks in), redrawn whenever that window    |
//| actually changes (a new day closes). No fractal confirmation, no  |
//| touch count, no eviction - this is deliberately the simplest      |
//| possible construction, matching what's REAL-CONFIRMED on gold.    |
//+------------------------------------------------------------------+
void ScanRecentHL()
  {
   int n = MathMax(1, InpRecentHLDays);
   datetime d0 = iTime(_Symbol, PERIOD_D1, 0);
   if(d0 == g_lastRecentHLBarTime) return;   // only recompute once per new daily bar

   //--- v1.12 FIX (Opus-found): g_lastRecentHLBarTime used to be
   //--- committed BEFORE the "D1 history ready" check below - a "not
   //--- ready yet" skip (routine right after attach) left this marked
   //--- done for the rest of the day, with no retry until the next
   //--- daily bar. Now only committed once the data is confirmed ready.
   double hi = -DBL_MAX, lo = DBL_MAX;
   for(int i = 1; i <= n; i++)
     {
      double dh = iHigh(_Symbol, PERIOD_D1, i);
      double dl = iLow(_Symbol, PERIOD_D1, i);
      if(dh <= 0.0 || dl <= 0.0)
        {
         Print("Important_SR_Levels: recent-HL skipped - D1 history not ready yet, will retry next tick.");
         return;
        }
      if(dh > hi) hi = dh;
      if(dl < lo) lo = dl;
     }
   g_lastRecentHLBarTime = d0;
   g_recentHLHi = hi;
   g_recentHLLo = lo;
   //--- v1.10: Open = the OPEN of the OLDEST of the n completed days
   //--- (shift n), Close = the CLOSE of the most recent completed day
   //--- (shift 1) - together with hi/lo above this reads as a single
   //--- synthetic n-day OHLC bar, per direct request ("include the 3
   //--- days high and low, open and close")
   g_recentOpen  = iOpen(_Symbol, PERIOD_D1, n);
   g_recentClose = iClose(_Symbol, PERIOD_D1, 1);
   g_recentHLReady = true;

   string nmHi = PFX_RHL + "hi", nmLo = PFX_RHL + "lo";
   for(int pass = 0; pass < 2; pass++)
     {
      string nm = (pass == 0) ? nmHi : nmLo;
      double price = (pass == 0) ? hi : lo;
      if(ObjectFind(0, nm) < 0)
        {
         if(!ObjectCreate(0, nm, OBJ_HLINE, 0, 0, price))
           {
            PrintFormat("Important_SR_Levels: ObjectCreate FAILED for %s at price %s - error %d",
                        nm, DoubleToString(price, _Digits), GetLastError());
            continue;
           }
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
        }
      ObjectSetInteger(0, nm, OBJPROP_COLOR, InpRecentHLColor);
      ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
      ObjectSetDouble(0, nm, OBJPROP_PRICE, price);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP,
                       "Recent " + IntegerToString(n) + "-day " + (pass == 0 ? "high" : "low") + ": " +
                       DoubleToString(price, _Digits) + " (Aurelius-style rolling S/R)");
     }

   if(InpShowRecentOC && g_recentOpen > 0.0 && g_recentClose > 0.0)
     {
      string nmOp = PFX_RHL + "op", nmCl = PFX_RHL + "cl";
      for(int pass = 0; pass < 2; pass++)
        {
         string nm = (pass == 0) ? nmOp : nmCl;
         double price = (pass == 0) ? g_recentOpen : g_recentClose;
         color col = (pass == 0) ? InpRecentOpenColor : InpRecentCloseColor;
         if(ObjectFind(0, nm) < 0)
           {
            if(!ObjectCreate(0, nm, OBJ_HLINE, 0, 0, price))
              {
               PrintFormat("Important_SR_Levels: ObjectCreate FAILED for %s at price %s - error %d",
                           nm, DoubleToString(price, _Digits), GetLastError());
               continue;
              }
            ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
           }
         ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
         ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
         ObjectSetDouble(0, nm, OBJPROP_PRICE, price);
         ObjectSetString(0, nm, OBJPROP_TOOLTIP,
                          IntegerToString(n) + "-day " + (pass == 0 ? "Open" : "Close") + ": " +
                          DoubleToString(price, _Digits));
        }
     }
   PrintFormat("Important_SR_Levels: recent-HL updated - last %d completed D1 bars, hi=%s lo=%s open=%s close=%s",
               n, DoubleToString(hi, _Digits), DoubleToString(lo, _Digits),
               DoubleToString(g_recentOpen, _Digits), DoubleToString(g_recentClose, _Digits));
  }

//+------------------------------------------------------------------+
//| v1.08: right-edge labels for the recent-HL lines (these had NO    |
//| label of any kind before - price-only tooltip on hover), called   |
//| every OnCalculate alongside the fractal layers' own label refresh.|
//+------------------------------------------------------------------+
void RefreshRecentHLLabels(const datetime nowTime)
  {
   if(!InpShowRecentHL || !InpShowTouchLabels || !g_recentHLReady) return;
   string nmHiLbl = PFX_RHL + "lbl_hi", nmLoLbl = PFX_RHL + "lbl_lo";
   for(int pass = 0; pass < 2; pass++)
     {
      string nm = (pass == 0) ? nmHiLbl : nmLoLbl;
      double price = (pass == 0) ? g_recentHLHi : g_recentHLLo;
      if(ObjectFind(0, nm) < 0)
        {
         if(!ObjectCreate(0, nm, OBJ_TEXT, 0, nowTime, price))
           {
            PrintFormat("Important_SR_Levels: ObjectCreate FAILED for %s at price %s - error %d",
                        nm, DoubleToString(price, _Digits), GetLastError());
            continue;
           }
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_LEFT);
        }
      ObjectSetInteger(0, nm, OBJPROP_TIME, 0, nowTime);
      ObjectSetDouble(0, nm, OBJPROP_PRICE, price);
      ObjectSetString(0, nm, OBJPROP_TEXT, (pass == 0 ? " " : " ") + IntegerToString(InpRecentHLDays) +
                       "D " + (pass == 0 ? "Hi" : "Lo"));
      ObjectSetInteger(0, nm, OBJPROP_COLOR, InpRecentHLColor);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpLabelFontSize);
     }
  }

//+------------------------------------------------------------------+
//| v1.10: right-edge labels for the Open/Close lines, same pattern as |
//| RefreshRecentHLLabels() above.                                     |
//+------------------------------------------------------------------+
void RefreshRecentOCLabels(const datetime nowTime)
  {
   if(!InpShowRecentHL || !InpShowRecentOC || !InpShowTouchLabels || !g_recentHLReady) return;
   if(g_recentOpen <= 0.0 || g_recentClose <= 0.0) return;
   string nmOpLbl = PFX_RHL + "lbl_op", nmClLbl = PFX_RHL + "lbl_cl";
   for(int pass = 0; pass < 2; pass++)
     {
      string nm = (pass == 0) ? nmOpLbl : nmClLbl;
      double price = (pass == 0) ? g_recentOpen : g_recentClose;
      color col = (pass == 0) ? InpRecentOpenColor : InpRecentCloseColor;
      if(ObjectFind(0, nm) < 0)
        {
         if(!ObjectCreate(0, nm, OBJ_TEXT, 0, nowTime, price))
           {
            PrintFormat("Important_SR_Levels: ObjectCreate FAILED for %s at price %s - error %d",
                        nm, DoubleToString(price, _Digits), GetLastError());
            continue;
           }
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_LEFT);
        }
      ObjectSetInteger(0, nm, OBJPROP_TIME, 0, nowTime);
      ObjectSetDouble(0, nm, OBJPROP_PRICE, price);
      ObjectSetString(0, nm, OBJPROP_TEXT, " " + IntegerToString(InpRecentHLDays) +
                       "D " + (pass == 0 ? "Open" : "Close"));
      ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpLabelFontSize);
     }
  }

//+------------------------------------------------------------------+
void ScanHigherTF(const ENUM_TIMEFRAMES tf, SRLevel &levels[], const string prefix,
                   const color supCol, const color resCol, const int atrHandle, datetime &lastBarTime)
  {
   int w = InpDWWindow;
   //--- v1.13 FIX - per report: "the support and resistance line
   //--- indicator are making the charts freeze... gold is specific...
   //--- silver is also [p]aused, bitcoin is working fine". Root cause:
   //--- CopyRates(0, 5000) below - copying 5000 full MqlRates records -
   //--- used to run UNCONDITIONALLY on every single tick, for all THREE
   //--- higher-timeframe layers (H4/D1/W1), with the "do we even need to
   //--- rescan" check only happening AFTER that expensive copy. Gold and
   //--- Silver are far more actively quoted (many more ticks/second
   //--- during active sessions) than BTC typically is on a CFD feed, so
   //--- this cost scaled directly with tick frequency and hit metals
   //--- hardest - matching exactly what was reported. Fixed by gating
   //--- with a single cheap native iTime() call FIRST (the same pattern
   //--- ScanRecentHL already used for its own D1 check) - CopyRates is
   //--- now only ever called on the rare tick where a new bar on THIS
   //--- timeframe actually just closed, not on every tick regardless.
   datetime newestClosed = iTime(_Symbol, tf, 1);
   if(newestClosed == 0 || newestClosed == lastBarTime) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int count = CopyRates(_Symbol, tf, 0, 5000, rates);
   if(count < 2 * w + 2) return;

   //--- newest CLOSED bar is count-2 (count-1 is the currently forming bar)
   int maxI = count - 2 - w;
   if(maxI < w) return;

   //--- defensive: iTime(shift 1) and CopyRates's own maxI-th bar should
   //--- always agree, but if a history reload landed between the two
   //--- calls above, trust the actual copied data, not the earlier check
   if(rates[maxI].time == lastBarTime) return;

   //--- v1.12 FIX (Opus-found): lastBarTime used to be committed (and the
   //--- existing objects wiped) BEFORE confirming the ATR CopyBuffer
   //--- below actually succeeded - a handle that isn't calculated yet
   //--- (routine right after attach, exactly when this is most likely)
   //--- made this return with the layer wiped-but-empty AND marked
   //--- "done", so it wouldn't even retry until the NEXT new bar closes
   //--- on this timeframe - up to 4h for H4, a day for D1, a week for
   //--- W1 - with nothing printed to explain the empty layer. Now the
   //--- ATR copy is validated FIRST, before touching lastBarTime or any
   //--- existing object/array state, so a transient failure leaves
   //--- everything untouched and retries on the very next tick instead.
   datetime cutoffTime = (InpDWLookbackDays > 0) ? (rates[maxI].time - (datetime)((long)InpDWLookbackDays * 86400)) : 0;
   datetime recentCutoff = (InpRecentProtectDays > 0) ? (rates[maxI].time - (datetime)((long)InpRecentProtectDays * 86400)) : 0;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, false);
   int atrCount = maxI - w + 1;
   if(CopyBuffer(atrHandle, 0, w, atrCount, atrBuf) < atrCount)
     {
      PrintFormat("Important_SR_Levels: %s rescan skipped - ATR not ready yet, will retry next tick.", EnumToString(tf));
      return;
     }

   lastBarTime = rates[maxI].time;
   ObjectsDeleteAll(0, prefix);
   ArrayResize(levels, 0);

   for(int i = w; i <= maxI; i++)
     {
      if(rates[i].time < cutoffTime) continue;
      double minDistance = atrBuf[i - w] * InpAtrMultiplier;
      if(minDistance <= 0.0) continue;

      bool isPeak = true, isTrough = true;
      for(int k = 1; k <= w; k++)
        {
         if(rates[i].high < rates[i - k].high || rates[i].high <= rates[i + k].high) isPeak = false;
         if(rates[i].low  > rates[i - k].low  || rates[i].low  >= rates[i + k].low)  isTrough = false;
         if(!isPeak && !isTrough) break;
        }
      if(isPeak)         RegisterTouchG(levels, rates[i].time, rates[i].high, false, minDistance, prefix,
                                         InpDWMaxLevels, InpDWMinTouchesToShow, supCol, resCol, recentCutoff, false);
      else if(isTrough)  RegisterTouchG(levels, rates[i].time, rates[i].low,  true,  minDistance, prefix,
                                         InpDWMaxLevels, InpDWMinTouchesToShow, supCol, resCol, recentCutoff, false);
     }

   int visible = 0;
   for(int k = 0; k < ArraySize(levels); k++)
      if(levels[k].touches >= InpDWMinTouchesToShow) visible++;
   PrintFormat("Important_SR_Levels: %s rescan - %d bars checked, %d levels found, %d visible (touches>=%d)",
               EnumToString(tf), maxI - w + 1, ArraySize(levels), visible, InpDWMinTouchesToShow);
   LogLevelDiagnostics(levels, InpDWMinTouchesToShow, EnumToString(tf));
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                 const int prev_calculated,
                 const datetime &time[],
                 const double &open[],
                 const double &high[],
                 const double &low[],
                 const double &close[],
                 const long &tick_volume[],
                 const long &volume[],
                 const int &spread[])
  {
   int w = InpLeftRightWindow;
   //--- v1.10: the whole intraday (chart's own timeframe) fractal scan is
   //--- now OFF by default and gated behind InpShowIntradayLevels - per
   //--- direct request to focus on H4 and up instead. When it's off,
   //--- none of this block's early-returns apply (they're specific to
   //--- the intraday scan's own incremental bookkeeping) - execution
   //--- falls straight through to the H4/daily/weekly/recent-HL layers
   //--- below, which have always had their own independent re-scan-on-
   //--- new-bar logic, not tied to this function's return value.
   if(InpShowIntradayLevels)
     {
      //--- v1.02 FIX: "not enough bars yet" must return 0, not rates_total -
      //--- returning rates_total claims the whole history is fully handled,
      //--- so if MT5 later loads more history (common right after attach,
      //--- or on a symbol whose history is still downloading), this
      //--- indicator would never go back and actually run the real scan.
      if(rates_total < 2 * w + 2) return(0);

      //--- v1.01 FIX #2: prev_calculated resetting to 0 (a history
      //--- reload/gap-fill, NOT necessarily "freshly attached") must wipe
      //--- the existing level list and chart objects first - otherwise the
      //--- whole history gets re-scanned on top of what's already there,
      //--- roughly doubling every touch count.
      if(prev_calculated <= 0)
        {
         ObjectsDeleteAll(0, PFX);
         ArrayResize(g_levels, 0);
        }

      //--- the newest CLOSED bar is rates_total-2 (rates_total-1 is still
      //--- forming) - a pivot candidate at index i needs w closed bars on
      //--- BOTH sides, so the last checkable candidate is (rates_total-2-w)
      int maxI = rates_total - 2 - w;
      if(maxI < w) return(0);   // v1.02 FIX - same reasoning as above

      //--- v1.01 FIX #1: exactly the candidates that could NOT have been
      //--- fully confirmed last call - no extra margin. A closed bar's
      //--- high/low never changes, so once a candidate has been checked
      //--- with a full w-bar window on both sides, it never needs
      //--- re-checking. The old "-2" margin here re-registered the same
      //--- few newest pivots on every tick with no new bar, which could
      //--- inflate a touch count by one per tick for hours.
      int startI = (prev_calculated <= 0) ? w : MathMax(w, prev_calculated - 1 - w);
      if(startI > maxI) return(rates_total);

      //--- v1.03: lookback cutoff - see InpLookbackDays' own comment
      datetime cutoffTime = (InpLookbackDays > 0) ? (time[maxI] - (datetime)((long)InpLookbackDays * 86400)) : 0;
      datetime recentCutoff = (InpRecentProtectDays > 0) ? (time[maxI] - (datetime)((long)InpRecentProtectDays * 86400)) : 0;

      //--- v1.01 FIX #4: read ATR PER BAR, not one current value applied
      //--- to all of history - only the slice actually needed this call.
      int atrCount = maxI - startI + 1;
      double atrBuf[];
      ArraySetAsSeries(atrBuf, false);
      if(CopyBuffer(g_atrHandle, 0, startI, atrCount, atrBuf) < atrCount)
        {
         //--- v1.01 FIX #3: tell MT5 this call did NOT handle the history
         //--- (return 0, not rates_total) so it retries properly next
         //--- tick instead of silently treating the backfill as done.
         return(0);
        }

      for(int i = startI; i <= maxI; i++)
        {
         if(time[i] < cutoffTime) continue;   // v1.03: outside the lookback window - not eligible at all
         double minDistance = atrBuf[i - startI] * InpAtrMultiplier;
         if(minDistance <= 0.0) continue;

         //--- v1.01 minor fix: a flat-top/flat-bottom tie (two bars with the
         //--- exact same high or low) used to let BOTH register as separate
         //--- pivots. Ties now resolve to the LATER (more recent) bar only -
         //--- a tie with an EARLIER neighbor is allowed, but a tie (or
         //--- worse) against a LATER neighbor disqualifies, so only the
         //--- rightmost bar in a flat top/bottom ever becomes the pivot.
         bool isPeak = true, isTrough = true;
         for(int k = 1; k <= w; k++)
           {
            if(high[i] < high[i - k] || high[i] <= high[i + k]) isPeak = false;
            if(low[i]  > low[i - k]  || low[i]  >= low[i + k])  isTrough = false;
            if(!isPeak && !isTrough) break;
           }
         if(isPeak)         RegisterTouchG(g_levels, time[i], high[i], false, minDistance, PFX, InpMaxLevels,
                                            InpMinTouchesToShow, InpSupportColor, InpResistanceColor, recentCutoff);
         else if(isTrough)  RegisterTouchG(g_levels, time[i], low[i],  true,  minDistance, PFX, InpMaxLevels,
                                            InpMinTouchesToShow, InpSupportColor, InpResistanceColor, recentCutoff);
        }

      //--- v1.02: one-time summary once the initial backfill finishes, so
      //--- "I attached it and see nothing" has an actual answer in the
      //--- journal instead of silence either way.
      if(prev_calculated <= 0)
        {
         int visible = 0;
         for(int k = 0; k < ArraySize(g_levels); k++)
            if(g_levels[k].touches >= InpMinTouchesToShow) visible++;
         PrintFormat("Important_SR_Levels: initial scan done - %d bars checked (lookback cutoff: %s), "
                     "%d levels found, %d visible (touches>=%d), %d hidden below the touch threshold",
                     maxI - startI + 1, (InpLookbackDays > 0) ? TimeToString(cutoffTime, TIME_DATE) : "none",
                     ArraySize(g_levels), visible, InpMinTouchesToShow, ArraySize(g_levels) - visible);
         LogLevelDiagnostics(g_levels, InpMinTouchesToShow, "intraday");
        }
     }

   if(InpShowH4Levels)
      ScanHigherTF(PERIOD_H4, g_levelsH4, PFX_H4, InpH4SupportColor, InpH4ResistanceColor,
                   g_atrHandleH4, g_lastH4BarTime);
   if(InpShowDailyLevels)
      ScanHigherTF(PERIOD_D1, g_levelsD, PFX_D, InpDailySupportColor, InpDailyResistanceColor,
                   g_atrHandleD, g_lastDailyBarTime);
   if(InpShowWeeklyLevels)
      ScanHigherTF(PERIOD_W1, g_levelsW, PFX_W, InpWeeklySupportColor, InpWeeklyResistanceColor,
                   g_atrHandleW, g_lastWeeklyBarTime);
   if(InpShowRecentHL)
      ScanRecentHL();

   //--- v1.11 FIX: everything below this point (TopN filter + every
   //--- label refresh) used to run UNCONDITIONALLY on every single
   //--- OnCalculate call - MT5 calls an indicator's OnCalculate on every
   //--- new TICK, not just every new bar, so on a fast-ticking symbol
   //--- (reported: "the support and resistance line indicator are
   //--- making the charts freeze") this meant dozens of synchronous
   //--- ObjectFind/ObjectCreate/ObjectSet calls across 4 level layers,
   //--- potentially many times per SECOND, forever - the same class of
   //--- bug already found and fixed in TradePanel_EA this session.
   //--- Labels only need to track "now" roughly (they're just moving a
   //--- text position to the right edge), not tick-exactly, so this is
   //--- now throttled to once per second - still updates live, just not
   //--- on every single tick.
   if(GetTickCount64() - g_lastUiRefreshMs < 1000) return(rates_total);
   g_lastUiRefreshMs = GetTickCount64();

   //--- v1.09: cap how many levels per layer are actually drawn
   ApplyTopNFilter(g_levels,   InpMinTouchesToShow,   InpShowTopN, InpSupportColor,         InpResistanceColor);
   ApplyTopNFilter(g_levelsH4, InpDWMinTouchesToShow, InpShowTopN, InpH4SupportColor,       InpH4ResistanceColor);
   ApplyTopNFilter(g_levelsD,  InpDWMinTouchesToShow, InpShowTopN, InpDailySupportColor,    InpDailyResistanceColor);
   ApplyTopNFilter(g_levelsW,  InpDWMinTouchesToShow, InpShowTopN, InpWeeklySupportColor,   InpWeeklyResistanceColor);

   //--- v1.08: refresh every visible label's position to the right edge
   //--- every call, not just when a level is actually touched
   datetime nowTime = TimeCurrent();
   RefreshRightEdgeLabels(g_levels,   InpMinTouchesToShow,   nowTime);
   RefreshRightEdgeLabels(g_levelsH4, InpDWMinTouchesToShow, nowTime);
   RefreshRightEdgeLabels(g_levelsD,  InpDWMinTouchesToShow, nowTime);
   RefreshRightEdgeLabels(g_levelsW,  InpDWMinTouchesToShow, nowTime);
   RefreshRecentHLLabels(nowTime);
   RefreshRecentOCLabels(nowTime);

   return(rates_total);
  }
