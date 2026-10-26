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
#property version   "1.24"
//--- 1.24: Per direct request - "give me them all separate, each
//--- previous day's high and low": new InpShowRecentHLPerDay (default
//--- true) draws InpRecentHLDays SEPARATE high/low line pairs, one per
//--- completed day, each individually labeled ("D-1 Hi/Lo", "D-2
//--- Hi/Lo", ...). Replaces the old single combined rolling high/low
//--- (InpShowRecentHL) as the default view, per a direct follow-up
//--- ("you can replace the existing line otherwise we should have
//--- duplicate lines") - InpShowRecentHL defaulted OFF, kept available
//--- if you want the combined line back alongside the per-day ones.
//--- Fixed the caller gate (OnCalculate used to call ScanRecentHL()
//--- only when InpShowRecentHL was on - now runs whenever EITHER
//--- toggle is on, otherwise the new per-day lines would never compute
//--- with the old one defaulted off) and added object cleanup for both
//--- layers when their toggle is off or InpRecentHLDays is lowered, so
//--- no stale lines linger from a config change.
//--- 1.23: Real bug, confirmed from the actual Experts log sent in a
//--- freeze report ("the support and resistance indicator is still
//--- making price freeze") - 3 OnInit events in 2 minutes, each
//--- immediately followed by ALL THREE of H4/daily/weekly doing a full
//--- rescan in the SAME OnCalculate call (g_lastH4BarTime/
//--- g_lastDailyBarTime/g_lastWeeklyBarTime are all reset to 0 together
//--- in OnInit). That's up to ~11,300 bars of fractal+ATR+clustering
//--- work done synchronously in one blocking call - genuinely heavy
//--- enough to freeze the terminal for however long it takes, and it
//--- happens every time OnInit re-fires (attach, any input change, or a
//--- timeframe/symbol switch) - worse with 3 reinits close together, as
//--- the log showed. The steady-state (no fresh backfill needed) case
//--- was always cheap and correctly throttled already - this only ever
//--- hit the three-layers-at-once case right after a reinit, which none
//--- of the prior 14 rounds of freeze fixes (v1.09-v1.22) had covered,
//--- since they were all found by reasoning about per-TICK cost, not
//--- the one-time cost of a reinit itself. Fixed in OnCalculate: a
//--- fresh (lastBarTime==0) layer only gets its backfill if no OTHER
//--- layer has already used this call's one-fresh-backfill budget - the
//--- other(s) simply wait one extra tick and try again, spreading 3
//--- heavy backfills across 3 ticks instead of stacking them in 1. Zero
//--- effect on steady-state behavior.
//--- 1.22: Final Opus audit of today's changes confirmed v1.20's two
//--- freeze fixes are present and correct, the ATR index fixes hand-
//--- trace correctly, and the v1.21 struct-field init is correct. Two
//--- doc-comment corrections made as a result (no functional change):
//--- (1) the Bounce confirmation window's own comment said "the 2nd OR
//--- 3rd bar AFTER" the approach, which (literally read) is off by one
//--- from what the code actually checks (the 1ST or 2ND bar after the
//--- approach = candle 2 or candle 3, counting the approach itself as
//--- candle 1) - reworded for precision, code unchanged (confirmed
//--- correct against the original request by tracing it). (2) noted:
//--- every H4/D1/W1 rescan wipes that layer's level array, so a
//--- proximity-alert latch resets with it - a level can re-alert every
//--- rescan (up to every 4h on H4) bypassing InpProximityAlertCooldownMin.
//--- Minor (alert-frequency annoyance, not a freeze or crash) - not
//--- fixed here, flagged for a future pass if it becomes a real issue.
//--- 1.21: Per direct request - (1) signal arrows now use the same
//--- OBJ_ARROW_UP/DOWN + ANCHOR_TOP/BOTTOM shape TradePanel_EA.mq5
//--- uses for every one of its own signal arrows (was OBJ_ARROW_BUY/
//--- SELL, MT5's own fixed chevron glyphs) - a signal looks the same
//--- regardless of which of the two programs drew it. (2) Bounce
//--- redesigned - "the rejection needs to be more specific, also in
//--- close proximity to the line, but we need to wait for the
//--- rejection of the 2nd or 3rd candle for a valid rejection": a bar
//--- whose range comes within InpBounceProximityATR of a level (not
//--- necessarily a literal touch anymore) arms a pending watch on
//--- whichever side its close ended up; counting the approach bar
//--- itself as candle 1, the signal only fires if candle 2 OR candle 3
//--- confirms by closing back on that same side and clearly clear of
//--- the proximity band again - a held rejection, not a single wick.
//--- No confirmation by candle 3 = dropped, no signal. New SRLevel
//--- fields (rejPendingSide/
//--- rejPendingAge) carry this per-level state, explicitly zeroed on
//--- creation in RegisterTouchG (same lesson as every other per-level
//--- state field this session - a recycled array slot is not
//--- guaranteed zero). BreakBack's own construction is unchanged.
//--- 1.20: Per urgent real report - "the charts are all frozen again"
//--- (across 6 charts this time, which multiplied the effect) - found
//--- and fixed 2 real bugs in v1.18/v1.19's new signal/alert feature,
//--- NOT independently caught by the prior reviews because both are
//--- about WHAT the new code calls, not whether its own math is
//--- correct (which is what got checked):
//--- (1) CheckLevelProximityAlerts called Alert(), which pops a
//--- BLOCKING modal dialog. Right after a fresh attach/recompile,
//--- every level's alert latch starts un-fired - if several of the up
//--- to ~16 shown levels across all 4 layers happened to sit within
//--- the threshold of current price at once (easy in a tight range),
//--- they ALL fired Alert() in the SAME call, stacking multiple
//--- blocking popups - exactly what "frozen" looks like from outside,
//--- and worse across multiple charts since each fires independently.
//--- Replaced with PlaySound() (audible, non-blocking) - SendNotification
//--- (push) and Print (journal) already covered the non-blocking half.
//--- (2) CleanupOldLevelSignals ran every single new chart bar but
//--- scanned ObjectsTotal(0,0,-1) - EVERY object on the WHOLE chart,
//--- not just this indicator's own, including TradePanel_EA's
//--- thousands of objects if it's on the same chart. Now throttled to
//--- once per calendar day (arrows only need cleaning up once every
//--- InpLevelSignalMaxAgeDays/7 days anyway), cutting this cost by
//--- ~96x-288x with no visible difference.
//--- 1.19: Opus audit of v1.18 (new signal/alert logic) found 2 real
//--- bugs, both fixed here: (1) a newly-created level's 6 new fields
//--- (shown/side/breakDir/breakTime/proxAlerted/lastProxAlertAt) were
//--- never initialized - MQL5 only resets string/array struct members
//--- implicitly, not numbers/bools, and the eviction path reuses a
//--- slot that just held ANOTHER level's state - so a brand-new level
//--- could inherit stale break/proximity state and fire a bogus signal
//--- or silently block a real alert the first time it was ever
//--- evaluated. Now explicitly zeroed/false on creation. (2)
//--- CheckLevelSignals reused the STORED levels[k].side as side2
//--- whenever it was already set, instead of recomputing from close2 -
//--- but "side" only updates when a level is actually shown/evaluated,
//--- so a level that flickers out of the nearest-2/2 for a few bars, or
//--- whose price shifts slightly from an intraday merge, compared
//--- against a stale bar/stale price and could arm a fake break the
//--- moment it reappeared - confirmed by simulation. side2 is now
//--- always recomputed from close2 against the level's CURRENT price,
//--- removing the stale-state class of bug entirely. Also: the shared
//--- ATR handle (g_atrHandleSig) is now created whenever EITHER
//--- InpShowLevelSignals or InpEnableProximityAlert is on (was gated on
//--- the alert toggle alone, so signals-only setups silently fell back
//--- to a cruder offset despite the ATR-based comment); added
//--- InpBreakBackMaxBars/InpLevelSignalMaxAgeDays <= 0 validation
//--- (would otherwise silently defeat the whole feature with no
//--- explanation); dropped an unused declared-but-never-used global.
//--- Design limitations noted by the audit but NOT changed (benign,
//--- not bugs): choppy price near a level can repeat BreakBack signals
//--- every couple of bars; Bounce has no rejection-quality filter so it
//--- can fire every bar in a tight consolidation; overlapping levels
//--- from different layers at/near the same price can each signal or
//--- alert separately; a break armed right at an H4/D1/W1 rescan
//--- boundary is lost (array gets wiped); none of these are real
//--- signals and strategies being validated here, just raw reactions -
//--- same as every other overlay already shipped in this project.
//--- 1.18: Per direct request - buy/sell arrows when price reacts to a
//--- currently-shown level, plus a proximity alert. Two signal types
//--- (not just a single rejection candle): BOUNCE (a closed bar's
//--- range touches/crosses a shown level but its close stays on the
//--- same side - signal in the direction price stayed) and BREAK+BACK
//--- (a closed bar's close genuinely flips sides, armed for
//--- InpBreakBackMaxBars bars, then signals if a later bar's close
//--- flips back to the original side - "break through and back up").
//--- Both are close-based so neither can repaint once drawn. New
//--- SRLevel fields (shown/side/breakDir/breakTime/proxAlerted/
//--- lastProxAlertAt) carry this state per level; "shown" is set by
//--- ApplyTopNFilter/the v1.17 nearest-only filter, so signals/alerts
//--- only fire for whichever levels are actually drawn right now.
//--- Proximity alert (InpEnableProximityAlert) fires a push
//--- notification + terminal Alert() once price is within
//--- InpProximityAlertATRMult ATR of a shown level, using the same
//--- hysteresis latch (reset at 1.5x the threshold) already proven in
//--- TradePanel_EA's CheckCrossProximity, plus an explicit per-level
//--- cooldown on top. New dedicated g_atrHandleSig (chart timeframe,
//--- always created when InpEnableProximityAlert is on) so this works
//--- regardless of which level layers/InpShowIntradayLevels are
//--- enabled. Signal arrows are cleaned up after InpLevelSignalMaxAgeDays
//--- (7 by default), same weekly rolling-window convention as every
//--- other overlay in this project.
//--- 1.17: Per direct request - "show the 2 levels above price and 2
//--- below, as price breaks a level only show the 2 above/2 below
//--- again" to simplify the chart further. Replaced ApplyTopNFilter's
//--- touch-count ranking with a distance-to-current-price ranking
//--- (new InpShowNearestOnly, default true, and InpNearestCount,
//--- default 2): of whatever clears InpMinTouchesToShow, only the
//--- nearest N levels above current price and nearest N below are
//--- drawn, re-decided every throttled (~1s) refresh - crossing a level
//--- naturally re-picks both sides with no separate "broke a level"
//--- handling needed. The old InpShowTopN touch-ranked behavior is
//--- still there, selectable via InpShowNearestOnly=false. Also, per a
//--- same-session follow-up question ("high/low are the relevant ones,
//--- not open/close") - InpShowRecentOC now defaults to false; the
//--- recent 3-day high/low lines (unchanged, always shown in full, no
//--- ranking applied to that layer) stay on by default.
//--- 1.16: Opus-audited v1.15 (hand-traced + brute-force simulated).
//--- Fixes 1/2/4/5 confirmed correct, default (intraday-off) config
//--- confirmed unchanged except the intended ATR-alignment correction
//--- in fix 2. Fix 3 (drawInline=false for intraday) was found to cause
//--- a new problem, fixed here: intraday updates INCREMENTALLY (unlike
//--- ScanHigherTF's full wipe-then-rescan), so a level evicted on a
//--- later tick almost always DOES have a real chart line/label drawn
//--- from an earlier tick - skipping its delete purely because
//--- drawInline was false left ghost lines/labels on the chart forever
//--- at a stale price. RegisterTouchG's eviction-delete condition is
//--- now its own thing (objectsMayExist, true only for the intraday
//--- prefix), independent of drawInline, which still only controls
//--- whether a MERGED touch redraws immediately. Also removed the
//--- intraday LogLevelDiagnostics() call (same reasoning as the v1.14
//--- fix that already removed it for H4/daily/weekly: with
//--- drawInline=false nothing is drawn yet at that point, so it always
//--- falsely reported "0 verified"), and reset g_lastUiRefreshMs after
//--- the intraday backfill wipe too, so that layer can't go blank for
//--- up to 1s either. All of this only affects InpShowIntradayLevels
//--- (off by default) - the default config was already correct.
//--- 1.15: Final exhaustive Opus audit of v1.14 (hand-traced + brute-
//--- force simulated, not just read) confirmed both index fixes correct
//--- and the default (intraday-off) config genuinely free of tick-scaled
//--- cost, but found 5 more real items, all fixed here: (1) the v1.14
//--- extraction of ComputeIntradayLevels into its own function made it
//--- void, which lost OnCalculate's "0=not handled yet" signal - every
//--- early return inside it now returned rates_total regardless, so if
//--- the intraday ATR handle wasn't ready on first attach (routine), the
//--- backfill was silently and PERMANENTLY skipped forever, not just
//--- delayed - changed to bool, OnCalculate now returns 0 instead of
//--- rates_total whenever it reports "didn't finish"; (2) the H4/daily/
//--- weekly ATR CopyBuffer passed shift w instead of w+1 - each pivot
//--- was reading the ATR of the bar one newer than itself (confirmed
//--- off-by-exactly-one by brute-force simulation) - fixed to w+1,
//--- matching how rates[maxI] (shift w+1) is actually indexed; (3) the
//--- intraday backfill's two RegisterTouchG calls omitted the
//--- drawInline argument, defaulting to true - meaning every touch
//--- across the FULL backfill history still drew synchronously inline,
//--- the exact blocking pattern already fixed for H4/D1/W1 back in
//--- v1.12, never applied here - explicit false now defers all of it to
//--- ApplyTopNFilter like every other layer (Opus's verdict: without
//--- this the intraday layer, even though off by default, was "not
//--- production-safe" the moment anyone turned it on); (4) a
//--- ScanHigherTF rescan landing on a tick where the 1-second UI-refresh
//--- throttle was still blocking left that layer visually blank for up
//--- to 1s after the wipe - g_lastUiRefreshMs is now reset to 0
//--- immediately after a successful rescan so the redraw isn't delayed;
//--- (5) the intraday ATR handle was being created in OnInit
//--- unconditionally, even with InpShowIntradayLevels off (its default)
//--- - one wasted ATR calculated every tick for nothing, inconsistent
//--- with how the H4/daily/weekly handles are already correctly gated
//--- behind their own toggles - now gated the same way.
//--- 1.14: Opus-audited (exhaustive pass, per direct request - "get
//--- opus to make 100 percent sure this time"). Found v1.13's fix was
//--- actually a NO-OP: it compared iTime(tf, shift 1) against
//--- lastBarTime, but lastBarTime is set from rates[maxI] which, with
//--- InpDWWindow's default of 2, is actually shift (w+1)=3 - never
//--- equal to shift 1, so the gate never returned early and CopyRates
//--- kept running on every tick exactly as before. Fixed: shift is now
//--- w+1, confirmed correct by hand and by simulation. Also fixed,
//--- all Opus-found: (1) a v1.12 regression - InpShowTopN<=0
//--- ("0 = show everything") now drew NOTHING for the H4/daily/weekly
//--- layers, because v1.12 moved all their drawing into ApplyTopNFilter,
//--- which still had its old "return immediately if topN<=0" guard from
//--- when it was just an extra filter on top of inline drawing; (2) the
//--- "N actually verified ON CHART" diagnostic for H4/daily/weekly was
//--- being printed immediately after the layer was wiped and BEFORE
//--- ApplyTopNFilter ever draws anything, so it always claimed "0
//--- verified" regardless of whether anything was actually wrong -
//--- removed from that call site; (3) the intraday scan's own early
//--- returns ("not enough bars", "nothing new this tick") used to exit
//--- the WHOLE OnCalculate function, not just the intraday block - so
//--- whenever InpShowIntradayLevels was on, every tick without a new
//--- CHART bar also silently skipped the independent H4/daily/weekly/
//--- recent-HL scans and all label/TopN refreshes, starving them down
//--- to once-per-chart-bar instead of their own intended cadence -
//--- extracted into its own function (ComputeIntradayLevels) so its
//--- internal returns can never affect anything else; (4) H4/daily/
//--- weekly eviction still called ObjectDelete on every evicted level
//--- even though drawInline=false guarantees those objects were never
//--- created in the first place (the whole layer gets wiped before each
//--- rescan) - hundreds to thousands of guaranteed-no-op synchronous
//--- calls per rescan, now skipped; (5) the intraday layer's own ATR
//--- CopyBuffer call passed a forward chronological array INDEX as
//--- start_pos, which MQL5 expects as a backward SHIFT from the current
//--- bar - reading ATR from entirely the wrong bars whenever intraday
//--- is re-enabled (off by default, but a real correctness bug, not
//--- just the "off by one" the original v1.01 comment claimed) - fixed
//--- to convert index to shift correctly. Also fixed the OnInit journal
//--- line still printing the wrong version.
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
input bool     InpShowNearestOnly  = true;  // v1.17: per direct request - "only show 2 levels above and 2
                                             // below current price, and as price breaks a level, re-pick
                                             // the nearest 2/2 again". Replaces touch-count ranking with
                                             // distance-to-current-price ranking: of whatever clears
                                             // InpMinTouchesToShow, only the InpNearestCount levels whose
                                             // price is closest ABOVE current price, and the InpNearestCount
                                             // closest BELOW, are drawn - everything else clears internally
                                             // but isn't shown, same as the old InpShowTopN cap, just a
                                             // different (and simpler/fewer-objects) selection rule. Set
                                             // false to fall back to the old touch-count-ranked InpShowTopN
                                             // behavior below.
input int      InpNearestCount     = 2;     // v1.17: how many levels to show on EACH side (above/below) of
                                             // current price when InpShowNearestOnly is true.
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
input bool     InpShowRecentHL      = false;     // v1.24: defaulted OFF - per direct follow-up request,
                                                  // the new InpShowRecentHLPerDay below REPLACES this as the
                                                  // default view (each day's own H/L separately) rather than
                                                  // showing both and duplicating/overlapping lines. Turn
                                                  // this back on if you want the single combined rolling
                                                  // high/low ALONGSIDE the per-day lines too.
                                                  // A completely different, much simpler construction, lifted
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
input bool     InpShowRecentHLPerDay = true;     // v1.24 NEW - per direct request ("give me them all
                                                  // separate, each previous day's high and low") - draws
                                                  // InpRecentHLDays SEPARATE high/low line pairs, one per
                                                  // completed day, each individually labeled ("D-1 Hi/Lo",
                                                  // "D-2 Hi/Lo", ...) - IN ADDITION to the single combined
                                                  // rolling high/low above (InpShowRecentHL), not instead of
                                                  // it. Turn InpShowRecentHL off if you only want the
                                                  // per-day lines and not the combined overall one too.
input color    InpRecentHLPerDayColor = C'150,170,190';  // slightly lighter than InpRecentHLColor so the
                                                  // per-day lines are visually distinct from the combined one
input bool     InpShowRecentOC      = false;     // v1.10 NEW - per direct request ("include the 3 days high
                                                  // and low, open and close") - two more lines: the OPEN of
                                                  // the OLDEST of the InpRecentHLDays completed days, and the
                                                  // CLOSE of the most recent completed day - together with
                                                  // the existing Hi/Lo this reads as a single synthetic
                                                  // N-day OHLC bar
                                                  // v1.17: defaulted OFF - per direct follow-up, high/low are
                                                  // the levels price actually reacts to (liquidity/stops),
                                                  // open/close don't carry the same weight as S/R. The toggle
                                                  // is kept (not removed) in case you want it back on.
input color    InpRecentOpenColor   = C'176,144,120';  // dimmed orange-ish, distinct from the Hi/Lo silver
input color    InpRecentCloseColor  = C'144,176,120';  // dimmed green-ish

input group "=== Level reaction signals (buy/sell arrows) ==="
input bool     InpShowLevelSignals   = true;   // v1.18/v1.21: per direct request - arrows when price reacts
                                                // to a currently-SHOWN level (the nearest 2 above/2 below, per
                                                // v1.17), not just a single rejection candle:
                                                //  BOUNCE (redesigned v1.21 - "the rejection needs to be more
                                                //   specific, close proximity to the line, but wait for the
                                                //   rejection of the 2nd or 3rd candle"): a closed bar whose
                                                //   RANGE comes within InpBounceProximityATR of the level
                                                //   (doesn't have to literally touch it) arms a pending
                                                //   watch, on the side its CLOSE ended up. Counting the
                                                //   approach bar itself as candle 1, the signal only fires if
                                                //   candle 2 OR candle 3 (the 1st or 2nd bar AFTER the
                                                //   approach - not the approach bar itself, and not every bar
                                                //   after, just those two chances) closes back on that SAME
                                                //   side AND clearly clear of the proximity band again -
                                                //   confirming the rejection, not just a single wick. No
                                                //   confirmation by candle 3 = no signal, the pending watch
                                                //   is dropped.
                                                //  BREAK+BACK (unchanged): a closed bar's close genuinely
                                                //   flips to the other side of the level (a real break, not
                                                //   just a wick), then a later bar (within InpBreakBackMaxBars)
                                                //   closes back on the ORIGINAL side - reclaimed below after
                                                //   breaking above = SELL (failed breakout), reclaimed above
                                                //   after breaking below = BUY (failed breakdown/reclaim) -
                                                //   the "break through and back up" case.
                                                // Both evaluated once per new CLOSED bar on the CHART's own
                                                // timeframe (not per tick) - a closed bar's high/low/close
                                                // never change, so neither can repaint.
input double   InpBounceProximityATR = 0.3;    // v1.21: how close a bar's range has to come to a level to
                                                // count as "close proximity" and arm a Bounce watch - doesn't
                                                // have to literally touch the level price anymore.
input int      InpBreakBackMaxBars   = 5;      // how many chart bars a break has to reclaim the other side
                                                // within, to still count as "break and back" - older than
                                                // this and the break is just treated as a confirmed move,
                                                // no signal if/when price eventually drifts back later.
input color    InpLevelBuyColor      = clrLime;
input color    InpLevelSellColor     = clrRed;
input int      InpLevelSignalMaxAgeDays = 7;   // matches every other overlay's weekly rolling-window default
                                                // in this project - old arrows are deleted after this many days

input group "=== Proximity alert (push notification + terminal Alert) ==="
input bool     InpEnableProximityAlert   = true;   // v1.18: per direct request - warn BEFORE price actually
                                                     // reaches a currently-shown level, not just when it does
input double   InpProximityAlertATRMult  = 0.5;     // alert once price is within this many ATR (chart
                                                     // timeframe) of a shown level
input int      InpProximityAlertCooldownMin = 15;   // minimum minutes between two alerts for the SAME level,
                                                     // even if price oscillates in and out of range - on top
                                                     // of the hysteresis reset below (same two-part pattern
                                                     // already proven in TradePanel_EA's CheckCrossProximity)

#define PFX   "SRL_"
#define PFX_H4 "SRLH4_"
#define PFX_D "SRLD_"
#define PFX_W "SRLW_"
#define PFX_RHL "SRLRHL_"
#define PFX_SIG "SRLSIG_"

struct SRLevel
  {
   double   price;
   bool     isSupport;
   datetime firstTime;
   datetime lastTime;
   int      touches;
   string   lineName;
   string   labelName;
   //--- v1.18: level-reaction signal state. "shown" is set every
   //--- throttled refresh by ApplyTopNFilter/the nearest-only filter -
   //--- signals and proximity alerts only fire for whichever levels are
   //--- CURRENTLY drawn (the nearest 2 above/2 below), consistent with
   //--- the v1.17 simplification - a hidden level doesn't get arrows or
   //--- alerts just because it's still tracked internally.
   bool     shown;
   int      side;       // 1 = last closed bar's close was above this level, -1 = below, 0 = not yet evaluated
   int      breakDir;    // 0 = no pending break, 1 = broke/closed above, -1 = broke/closed below - armed,
                          // waiting to see if price reclaims the other side within InpBreakBackMaxBars
   datetime breakTime;   // the closed-bar time the break above was recorded, for the max-bars expiry check
   bool     proxAlerted;    // proximity-alert hysteresis latch - see CheckLevelProximityAlerts' own comment
   datetime lastProxAlertAt; // cooldown timestamp, independent of the hysteresis latch above
   //--- v1.21: multi-bar Bounce confirmation state - see CheckLevelSignals'
   //--- own comment. 0 = no pending approach being watched.
   int      rejPendingSide;
   int      rejPendingAge;
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
double   g_perDayHi[];   // v1.24: index 0 = D-1 (most recent completed day), 1 = D-2, ...
double   g_perDayLo[];
bool     g_recentHLReady = false;
int      g_atrHandleSig = INVALID_HANDLE;   // v1.18: dedicated chart-timeframe ATR for signals/proximity -
                                             // independent of g_atrHandle (intraday levels' own ATR, only
                                             // created when InpShowIntradayLevels is on) so signals/alerts
                                             // work regardless of which level layers are enabled.
datetime g_lastSigBarTime = 0;              // last chart bar CheckLevelSignals already evaluated
datetime g_lastSigCleanupDay = 0;           // v1.20: last calendar day CleanupOldLevelSignals ran

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
   //--- v1.19: InpBreakBackMaxBars<=0 would make maxBreakBackSecs<=0, so
   //--- a BreakBack could never fire (every reclaim looks "too late") -
   //--- not a crash, but silently defeats the whole feature with no
   //--- explanation. InpLevelSignalMaxAgeDays<=0 would delete every
   //--- signal arrow immediately after drawing it, same silent-no-op
   //--- problem. Both rejected outright instead, consistent with every
   //--- other "must be >= 1" input in this file.
   if(InpShowLevelSignals && InpBreakBackMaxBars <= 0)
     {
      Print("Important_SR_Levels: InpBreakBackMaxBars must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpShowLevelSignals && InpLevelSignalMaxAgeDays <= 0)
     {
      Print("Important_SR_Levels: InpLevelSignalMaxAgeDays must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpShowIntradayLevels)
     {
      g_atrHandle = iATR(_Symbol, _Period, InpAtrPeriod);
      if(g_atrHandle == INVALID_HANDLE)
        {
         Print("Important_SR_Levels: failed to create ATR handle.");
         return(INIT_FAILED);
        }
     }
   //--- v1.18: dedicated chart-timeframe ATR for signals/proximity -
   //--- created unconditionally (not gated behind InpShowIntradayLevels
   //--- like g_atrHandle above) since both features should work
   //--- regardless of which level layers are on.
   //--- v1.19 FIX (Opus-found): used to gate creation on
   //--- InpEnableProximityAlert alone - with signals on but the
   //--- proximity alert off, DrawLevelSignal's own ATR read silently
   //--- found an INVALID_HANDLE and fell back to the cruder
   //--- 0.25*(high-low) offset, contradicting its own comment that it
   //--- uses ATR. Gated on either toggle now.
   if(InpShowLevelSignals || InpEnableProximityAlert)
     {
      g_atrHandleSig = iATR(_Symbol, _Period, InpAtrPeriod);
      if(g_atrHandleSig == INVALID_HANDLE)
        {
         Print("Important_SR_Levels: failed to create signal/proximity ATR handle.");
         return(INIT_FAILED);
        }
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
   ArrayResize(g_perDayHi, 0);
   ArrayResize(g_perDayLo, 0);
   //--- v1.02: unconditional confirmation line - previously this
   //--- indicator only ever printed on an ERROR, so "nothing in the
   //--- journal" told you nothing about whether it was actually
   //--- running. Now it always confirms attach + settings here.
   PrintFormat("Important_SR_Levels v1.24 OnInit: %s %s  window=%d  minTouches=%d  maxLevels=%d  atrMult=%.2f  "
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
   ObjectsDeleteAll(0, PFX_SIG);
   if(g_atrHandle   != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   if(g_atrHandleH4 != INVALID_HANDLE) IndicatorRelease(g_atrHandleH4);
   if(g_atrHandleD  != INVALID_HANDLE) IndicatorRelease(g_atrHandleD);
   if(g_atrHandleW  != INVALID_HANDLE) IndicatorRelease(g_atrHandleW);
   if(g_atrHandleSig != INVALID_HANDLE) IndicatorRelease(g_atrHandleSig);
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
                      const color supCol, const color resCol, const double currentPrice,
                      const bool nearestOnly, const int nearestCount)
  {
   //--- v1.14 FIX (Opus-found, v1.12 regression): used to `return` here
   //--- when topN<=0 ("0 = show everything"), which was correct back
   //--- when every layer drew itself inline during the scan - this
   //--- function was purely an extra filter on top. Since v1.12 moved
   //--- ALL drawing for the H4/daily/weekly layers into THIS function
   //--- (ScanHigherTF no longer draws inline), an early return here with
   //--- topN<=0 now means those three layers draw NOTHING AT ALL instead
   //--- of "everything" - the intraday layer wasn't affected (it still
   //--- draws inline unconditionally) which is why this went unnoticed.
   //--- Still ranks/sorts below regardless (cheap, small N), just no
   //--- longer skips the draw pass entirely.
   int idx[];
   ArrayResize(idx, 0);
   //--- v1.18: default every level to "not shown" first - levels.shown
   //--- drives CheckLevelSignals/CheckLevelProximityAlerts below, so a
   //--- level that doesn't even clear minTouchesToShow (never reached
   //--- idx[]) must end up false, same as one that clears it but loses
   //--- the nearest-N ranking further down.
   for(int k = 0; k < ArraySize(levels); k++)
     {
      levels[k].shown = false;
      if(levels[k].touches < minTouchesToShow) continue;
      int sz = ArraySize(idx);
      ArrayResize(idx, sz + 1);
      idx[sz] = k;
     }
   int m = ArraySize(idx);

   //--- v1.17: per direct request - "only show 2 levels above price and
   //--- 2 below, and as price breaks a level, re-pick again" - replaces
   //--- the touch-count ranking below with distance-to-current-price
   //--- ranking. A level's drawn/not-drawn status is now re-decided
   //--- every throttled refresh purely from where it sits relative to
   //--- currentPrice, so crossing a level naturally drops it out of one
   //--- side's nearest-N and (if it's now on the other side) potentially
   //--- into the other's - no separate "price broke a level" handling
   //--- needed, this filter already re-runs every ~1s regardless.
   if(nearestOnly)
     {
      bool show[];
      ArrayResize(show, m);
      for(int k = 0; k < m; k++) show[k] = false;

      //--- nearest ABOVE: smallest (price - currentPrice) among price > currentPrice
      for(int pick = 0; pick < nearestCount; pick++)
        {
         int best = -1;
         double bestDist = DBL_MAX;
         for(int a = 0; a < m; a++)
           {
            if(show[a]) continue;
            double p = levels[idx[a]].price;
            if(p <= currentPrice) continue;
            double d = p - currentPrice;
            if(d < bestDist) { bestDist = d; best = a; }
           }
         if(best < 0) break;
         show[best] = true;
        }
      //--- nearest BELOW: smallest (currentPrice - price) among price < currentPrice
      for(int pick = 0; pick < nearestCount; pick++)
        {
         int best = -1;
         double bestDist = DBL_MAX;
         for(int a = 0; a < m; a++)
           {
            if(show[a]) continue;
            double p = levels[idx[a]].price;
            if(p >= currentPrice) continue;
            double d = currentPrice - p;
            if(d < bestDist) { bestDist = d; best = a; }
           }
         if(best < 0) break;
         show[best] = true;
        }

      for(int a = 0; a < m; a++)
        {
         if(show[a])
           {
            RedrawLevelG(levels[idx[a]], minTouchesToShow, supCol, resCol);
            levels[idx[a]].shown = true;
           }
         else
           {
            if(ObjectFind(0, levels[idx[a]].lineName) >= 0)  ObjectDelete(0, levels[idx[a]].lineName);
            if(ObjectFind(0, levels[idx[a]].labelName) >= 0) ObjectDelete(0, levels[idx[a]].labelName);
           }
        }
      return;
     }

   for(int a = 0; a < m; a++)
     {
      int best = a;
      for(int b = a + 1; b < m; b++)
         if(levels[idx[b]].touches > levels[idx[best]].touches) best = b;
      if(best != a) { int tmp = idx[a]; idx[a] = idx[best]; idx[best] = tmp; }
     }
   for(int a = 0; a < m; a++)
     {
      if(topN <= 0 || a < topN)
        {
         RedrawLevelG(levels[idx[a]], minTouchesToShow, supCol, resCol);   // ensure it's drawn (idempotent)
         levels[idx[a]].shown = true;
        }
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
      //--- v1.14 FIX (Opus-found): with drawInline=false during a
      //--- ScanHigherTF H4/daily/weekly scan, NOTHING in this array has
      //--- ever had a chart object created for it during THAT pass - the
      //--- whole layer was wiped via ObjectsDeleteAll() right before the
      //--- scan started, and RedrawLevelG is never called mid-scan
      //--- (see RegisterTouchG's own comment). So deleting there was a
      //--- guaranteed no-op every time - hundreds to thousands of wasted
      //--- synchronous calls across one full rescan.
      //--- v1.16 FIX (Opus-found): v1.15 widened drawInline=false to the
      //--- INTRADAY layer too (to fix its own freeze risk), but intraday
      //--- updates INCREMENTALLY, not via a full wipe-then-rescan like
      //--- ScanHigherTF - a level evicted here on a later tick almost
      //--- always DOES have a real line/label still on the chart from an
      //--- earlier tick's ApplyTopNFilter draw, so skipping the delete
      //--- purely because drawInline is false left ghost lines/labels
      //--- behind at a stale price forever (until deinit or a reload).
      //--- The two cases need different conditions, so they're now
      //--- separate: ScanHigherTF's full-rescan layers never need this
      //--- delete (always skip it, regardless of drawInline), while
      //--- intraday needs it whenever this isn't the very first backfill
      //--- call on a freshly-wiped array (i.e. whenever an object could
      //--- actually exist from a prior tick's draw).
      bool objectsMayExist = (prefix == PFX) ? true : false;
      if(objectsMayExist)
        {
         ObjectDelete(0, levels[weakest].lineName);
         ObjectDelete(0, levels[weakest].labelName);
        }
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
   //--- v1.19 FIX (Opus-found, real bug): number/bool struct fields in a
   //--- newly-grown array slot are NOT guaranteed zero by MQL5 (only
   //--- string/dynamic-array members get reset implicitly) - and the
   //--- eviction path above (levels[weakest]=levels[n-1]; resize down;
   //--- resize up) hands this brand-new slot memory that just held
   //--- ANOTHER level's state. Without this, a freshly-created level
   //--- could inherit a stale side/breakDir/breakTime/lastProxAlertAt
   //--- from whatever used to occupy this slot, firing a bogus
   //--- BreakBack signal (or blocking a real proximity alert) the very
   //--- first time it's ever evaluated.
   levels[n].shown          = false;
   levels[n].side           = 0;
   levels[n].breakDir       = 0;
   levels[n].breakTime      = 0;
   levels[n].proxAlerted    = false;
   levels[n].lastProxAlertAt = 0;
   levels[n].rejPendingSide = 0;
   levels[n].rejPendingAge  = 0;
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

   if(InpShowRecentHL)
     {
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
     }
   else
     {
      //--- v1.24: InpShowRecentHL off (the new default) - make sure no
      //--- stale combined-line objects are left behind from a config
      //--- change (ObjectCreate is idempotent/ObjectFind-guarded above,
      //--- but there's no corresponding cleanup path if the toggle was
      //--- flipped off after lines already existed).
      ObjectDelete(0, PFX_RHL + "hi");
      ObjectDelete(0, PFX_RHL + "lo");
      ObjectDelete(0, PFX_RHL + "lbl_hi");
      ObjectDelete(0, PFX_RHL + "lbl_lo");
     }

   //--- v1.24 NEW: per-day lines, per direct request ("give me them all
   //--- separate, each previous day's high and low") - replaces the
   //--- combined line as the default view (see InpShowRecentHL/
   //--- InpShowRecentHLPerDay's own comments).
   if(InpShowRecentHLPerDay)
     {
      ArrayResize(g_perDayHi, n);
      ArrayResize(g_perDayLo, n);
      for(int dIdx = 1; dIdx <= n; dIdx++)
        {
         double dh = iHigh(_Symbol, PERIOD_D1, dIdx);
         double dl = iLow(_Symbol, PERIOD_D1, dIdx);
         g_perDayHi[dIdx - 1] = dh;
         g_perDayLo[dIdx - 1] = dl;
         string nmDHi = PFX_RHL + "hi" + IntegerToString(dIdx);
         string nmDLo = PFX_RHL + "lo" + IntegerToString(dIdx);
         for(int pass = 0; pass < 2; pass++)
           {
            string nm = (pass == 0) ? nmDHi : nmDLo;
            double price = (pass == 0) ? dh : dl;
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
            ObjectSetInteger(0, nm, OBJPROP_COLOR, InpRecentHLPerDayColor);
            ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DASH);
            ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
            ObjectSetDouble(0, nm, OBJPROP_PRICE, price);
            ObjectSetString(0, nm, OBJPROP_TOOLTIP,
                             "D-" + IntegerToString(dIdx) + " " + (pass == 0 ? "high" : "low") + ": " +
                             DoubleToString(price, _Digits));
           }
        }
      //--- if InpRecentHLDays was lowered since the last run, delete any
      //--- leftover lines from a higher day-count that no longer apply
      for(int dIdx = n + 1; dIdx <= 30; dIdx++)
        {
         string nmDHi = PFX_RHL + "hi" + IntegerToString(dIdx);
         if(ObjectFind(0, nmDHi) < 0) break;
         ObjectDelete(0, nmDHi);
         ObjectDelete(0, PFX_RHL + "lo" + IntegerToString(dIdx));
         ObjectDelete(0, PFX_RHL + "lbl_hi" + IntegerToString(dIdx));
         ObjectDelete(0, PFX_RHL + "lbl_lo" + IntegerToString(dIdx));
        }
     }
   else
     {
      for(int dIdx = 1; dIdx <= 30; dIdx++)
        {
         string nmDHi = PFX_RHL + "hi" + IntegerToString(dIdx);
         if(ObjectFind(0, nmDHi) < 0) break;
         ObjectDelete(0, nmDHi);
         ObjectDelete(0, PFX_RHL + "lo" + IntegerToString(dIdx));
         ObjectDelete(0, PFX_RHL + "lbl_hi" + IntegerToString(dIdx));
         ObjectDelete(0, PFX_RHL + "lbl_lo" + IntegerToString(dIdx));
        }
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
//| v1.24: right-edge labels for the per-day lines - same pattern as   |
//| RefreshRecentHLLabels() above, one "D-N Hi"/"D-N Lo" pair per day.  |
//+------------------------------------------------------------------+
void RefreshRecentHLPerDayLabels(const datetime nowTime)
  {
   if(!InpShowRecentHLPerDay || !InpShowTouchLabels || !g_recentHLReady) return;
   int n = ArraySize(g_perDayHi);
   for(int dIdx = 1; dIdx <= n; dIdx++)
     {
      double hi = g_perDayHi[dIdx - 1];
      double lo = g_perDayLo[dIdx - 1];
      if(hi <= 0.0 || lo <= 0.0) continue;
      string nmHiLbl = PFX_RHL + "lbl_hi" + IntegerToString(dIdx);
      string nmLoLbl = PFX_RHL + "lbl_lo" + IntegerToString(dIdx);
      for(int pass = 0; pass < 2; pass++)
        {
         string nm = (pass == 0) ? nmHiLbl : nmLoLbl;
         double price = (pass == 0) ? hi : lo;
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
         ObjectSetString(0, nm, OBJPROP_TEXT, " D-" + IntegerToString(dIdx) + " " + (pass == 0 ? "Hi" : "Lo"));
         ObjectSetInteger(0, nm, OBJPROP_COLOR, InpRecentHLPerDayColor);
         ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpLabelFontSize);
        }
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
   //--- v1.13/v1.14: CopyRates(0, 5000) below - copying 5000 full MqlRates
   //--- records - must not run on every tick regardless of whether a new
   //--- bar closed on THIS timeframe (that was the root cause of the
   //--- Gold/Silver-specific freeze report - these are far more actively
   //--- quoted than BTC on most CFD feeds, so a per-tick cost there hits
   //--- hardest). Gated with a cheap native iTime() call first instead.
   //--- v1.14 FIX (Opus-found): v1.13 compared iTime(tf, 1) - shift 1,
   //--- the newest closed bar - against lastBarTime, which is actually
   //--- set from rates[maxI].time where maxI = count-2-w. In a NON-series
   //--- CopyRates array (ArraySetAsSeries(rates,false), as used here),
   //--- index count-1 is shift 0, so rates[maxI] is shift (w+1), not
   //--- shift 1 - they're always w bars apart and can never be equal.
   //--- The gate below NEVER returned early, so CopyRates kept running on
   //--- literally every tick exactly as before v1.13 - a pure no-op. Shift
   //--- is now w+1 to match rates[maxI] exactly, confirmed by hand and by
   //--- simulation (both count back from the same "current" bar, so they
   //--- agree by construction regardless of how much history exists).
   datetime newestClosed = iTime(_Symbol, tf, w + 1);
   if(newestClosed == 0 || newestClosed == lastBarTime) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int count = CopyRates(_Symbol, tf, 0, 5000, rates);
   if(count < 2 * w + 2) return;

   //--- newest CLOSED bar is count-2 (count-1 is the currently forming bar)
   int maxI = count - 2 - w;
   if(maxI < w) return;

   //--- defensive: iTime(shift w+1) and CopyRates's own maxI-th bar now
   //--- agree by construction (see the fixed gate's own comment above),
   //--- but if a history reload landed between the two calls, trust the
   //--- actual copied data over the earlier cheap check
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
   //--- v1.15 FIX (Opus-found): start_pos counts shifts back from the
   //--- current/forming bar (0 = most recent). rates[maxI] (the newest
   //--- pivot candidate) is shift w+1, not shift w - passing w here read
   //--- each pivot's ATR from the bar one newer than itself. Corrected to
   //--- w+1 so atrBuf[0] lines up with rates[w] and atrBuf[maxI-w] lines
   //--- up with rates[maxI], exactly as the atrBuf[i-w] indexing below
   //--- already assumes.
   int atrCount = maxI - w + 1;
   if(CopyBuffer(atrHandle, 0, w + 1, atrCount, atrBuf) < atrCount)
     {
      PrintFormat("Important_SR_Levels: %s rescan skipped - ATR not ready yet, will retry next tick.", EnumToString(tf));
      return;
     }

   lastBarTime = rates[maxI].time;
   ObjectsDeleteAll(0, prefix);
   ArrayResize(levels, 0);
   //--- v1.15 FIX (Opus-found): without this, a rescan landing on a tick
   //--- where the 1-second UI-refresh throttle is still blocking left the
   //--- layer visually blank for up to 1s after a wipe, since the actual
   //--- redraw (ApplyTopNFilter) only runs once the throttle opens again.
   g_lastUiRefreshMs = 0;

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
   //--- v1.14 FIX (Opus-found): used to call LogLevelDiagnostics() right
   //--- here, which checks ObjectFind "actually exists on chart" - but
   //--- since v1.12 this layer no longer draws inline during the scan
   //--- (drawInline=false, see RegisterTouchG's own comment); drawing
   //--- only happens later, in ApplyTopNFilter, back in OnCalculate.
   //--- Called here, this diagnostic would ALWAYS report "0 actually
   //--- verified ON CHART" regardless of whether anything was actually
   //--- wrong - identical to the real v1.05 "ObjectCreate silently
   //--- failed" symptom it exists to distinguish from. Removed from this
   //--- call site; the summary line above (bars/levels/visible) already
   //--- covers what this scan itself did, and the chart/label state
   //--- reflects reality correctly once ApplyTopNFilter runs moments
   //--- later.
  }

//+------------------------------------------------------------------+
//| v1.14 FIX (Opus-found): this used to be the top half of OnCalculate
//| itself, wrapped in `if(InpShowIntradayLevels) { ... }` - but its own
//| early `return(0)`/`return(rates_total)` calls (for "not enough bars
//| yet", "nothing new to scan") exited the WHOLE OnCalculate function,
//| not just this block. Since v1.10 made the intraday layer optional
//| and added independent H4/daily/weekly/recent-HL layers below it in
//| the same function, this meant: whenever intraday was switched ON,
//| every tick that didn't have a new CHART bar (the common case) also
//| silently skipped the H4/daily/weekly scans, the recent-HL scan, and
//| every label/TopN refresh - they'd then only ever run once per chart
//| bar instead of their own intended cadence. Extracted into its own
//| void function so its internal returns only exit ITS OWN work -
//| OnCalculate now always falls through to every other layer
//| regardless of what this one does or returns.
//+------------------------------------------------------------------+
//--- v1.15 FIX (Opus-found): changed from void to bool. The v1.14
//--- extraction lost OnCalculate's own "0 = not handled yet, retry full
//--- backfill from scratch" signal - every early return here now returns
//--- rates_total regardless, so if the ATR handle isn't ready yet on
//--- first attach (the routine, common case), the intraday backfill was
//--- silently and PERMANENTLY skipped: prev_calculated becomes
//--- rates_total on the very next call, startI ends up stuck > maxI
//--- forever, and the scan never runs. Returns false on every path that
//--- means "didn't finish handling this history", true otherwise -
//--- OnCalculate below now returns 0 instead of rates_total when this is
//--- false, so MT5 retries properly next tick exactly like every other
//--- "not ready yet" path in this file already does.
bool ComputeIntradayLevels(const int rates_total, const int prev_calculated,
                            const datetime &time[], const double &high[], const double &low[])
  {
   int w = InpLeftRightWindow;
   //--- v1.02 FIX: "not enough bars yet" must return 0, not rates_total -
   //--- returning rates_total claims the whole history is fully handled,
   //--- so if MT5 later loads more history (common right after attach,
   //--- or on a symbol whose history is still downloading), this
   //--- indicator would never go back and actually run the real scan.
   if(rates_total < 2 * w + 2) return(false);

   //--- v1.01 FIX #2: prev_calculated resetting to 0 (a history
   //--- reload/gap-fill, NOT necessarily "freshly attached") must wipe
   //--- the existing level list and chart objects first - otherwise the
   //--- whole history gets re-scanned on top of what's already there,
   //--- roughly doubling every touch count.
   if(prev_calculated <= 0)
     {
      ObjectsDeleteAll(0, PFX);
      ArrayResize(g_levels, 0);
      //--- v1.16: same reasoning as ScanHigherTF's own g_lastUiRefreshMs
      //--- reset - without this, a backfill landing on a tick where the
      //--- throttle is still blocking left this layer blank for up to 1s.
      g_lastUiRefreshMs = 0;
     }

   //--- the newest CLOSED bar is rates_total-2 (rates_total-1 is still
   //--- forming) - a pivot candidate at index i needs w closed bars on
   //--- BOTH sides, so the last checkable candidate is (rates_total-2-w)
   int maxI = rates_total - 2 - w;
   if(maxI < w) return(false);   // v1.02 FIX - same reasoning as above

   //--- v1.01 FIX #1: exactly the candidates that could NOT have been
   //--- fully confirmed last call - no extra margin. A closed bar's
   //--- high/low never changes, so once a candidate has been checked
   //--- with a full w-bar window on both sides, it never needs
   //--- re-checking. The old "-2" margin here re-registered the same
   //--- few newest pivots on every tick with no new bar, which could
   //--- inflate a touch count by one per tick for hours.
   int startI = (prev_calculated <= 0) ? w : MathMax(w, prev_calculated - 1 - w);
   //--- v1.15: this means "nothing new since last call", not "not ready" -
   //--- genuinely fully handled, so true (not a retry case like the ones
   //--- above/below).
   if(startI > maxI) return(true);

   //--- v1.03: lookback cutoff - see InpLookbackDays' own comment
   datetime cutoffTime = (InpLookbackDays > 0) ? (time[maxI] - (datetime)((long)InpLookbackDays * 86400)) : 0;
   datetime recentCutoff = (InpRecentProtectDays > 0) ? (time[maxI] - (datetime)((long)InpRecentProtectDays * 86400)) : 0;

   //--- v1.01 FIX #4: read ATR PER BAR, not one current value applied
   //--- to all of history - only the slice actually needed this call.
   //--- v1.14 FIX (Opus-found): CopyBuffer's start_pos counts SHIFTS
   //--- back from the current/forming bar (0 = most recent), but startI
   //--- is a forward chronological INDEX into the non-series time[]/
   //--- high[]/low[] arrays (0 = oldest) - passing startI directly as
   //--- start_pos read ATR from the wrong bars entirely (off by
   //--- rates_total-1-2*maxI or so, not just "one bar off" as the
   //--- original comment claimed). Converted to the correct shift:
   //--- shift(maxI) = rates_total-1-maxI is the start_pos that, combined
   //--- with ArraySetAsSeries(atrBuf,false), lines up atrBuf[0] with
   //--- time[startI] and atrBuf[atrCount-1] with time[maxI] - exactly
   //--- what the existing `atrBuf[i-startI]` indexing in the loop below
   //--- already assumes.
   int atrCount = maxI - startI + 1;
   double atrBuf[];
   ArraySetAsSeries(atrBuf, false);
   if(CopyBuffer(g_atrHandle, 0, rates_total - 1 - maxI, atrCount, atrBuf) < atrCount)
     {
      //--- v1.01 FIX #3: tell MT5 this call did NOT handle the history
      //--- (don't register anything new) so it retries properly next
      //--- tick instead of silently treating the backfill as done.
      return(false);
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
      //--- v1.15 FIX (Opus-found): these two calls used to omit the 12th
      //--- argument, defaulting to drawInline=true - meaning every touch
      //--- across the FULL backfill history drew synchronously inline,
      //--- the exact same blocking pattern already fixed for H4/D1/W1 in
      //--- v1.12, never applied here. Explicit false now defers all
      //--- drawing to ApplyTopNFilter, same as every other layer.
      if(isPeak)         RegisterTouchG(g_levels, time[i], high[i], false, minDistance, PFX, InpMaxLevels,
                                         InpMinTouchesToShow, InpSupportColor, InpResistanceColor, recentCutoff, false);
      else if(isTrough)  RegisterTouchG(g_levels, time[i], low[i],  true,  minDistance, PFX, InpMaxLevels,
                                         InpMinTouchesToShow, InpSupportColor, InpResistanceColor, recentCutoff, false);
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
      //--- v1.16 FIX (Opus-found): v1.15 made intraday drawInline=false,
      //--- so (same reasoning as the v1.14 fix that already removed this
      //--- call for H4/daily/weekly) nothing has actually been drawn on
      //--- the chart yet at this point - ApplyTopNFilter does that later,
      //--- back in OnCalculate. Calling LogLevelDiagnostics here would
      //--- always report "0 actually verified ON CHART" regardless of
      //--- whether anything is actually wrong. Removed; the summary line
      //--- above already covers what this backfill itself found.
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| v1.18: draws one buy/sell arrow for a level reaction. Named with   |
//| the bar time + a scaled price baked in, so two different signals  |
//| (different layer, different level, different bar) never collide,  |
//| and CleanupOldLevelSignals() below can parse the time back out     |
//| without needing a separate lookup table.                           |
//+------------------------------------------------------------------+
void DrawLevelSignal(const bool isBuy, const double levelPrice, const double barHigh, const double barLow,
                      const datetime barTime, const string layerTag, const string reasonTag)
  {
   if(!InpShowLevelSignals) return;
   //--- small offset so the arrow doesn't sit exactly on the candle wick
   double atrVal = 0.0;
   if(g_atrHandleSig != INVALID_HANDLE)
     {
      double buf[];
      ArraySetAsSeries(buf, true);
      if(CopyBuffer(g_atrHandleSig, 0, 1, 1, buf) == 1) atrVal = buf[0];
     }
   double offset = (atrVal > 0.0) ? atrVal * 0.25 : (barHigh - barLow) * 0.25;
   if(offset <= 0.0) offset = levelPrice * 0.0005;   // last-resort fallback, never zero

   string nm = PFX_SIG + layerTag + "_" + IntegerToString((long)barTime) + "_" +
               IntegerToString((long)MathRound(levelPrice * MathPow(10, _Digits)));
   double arrowPrice = isBuy ? (barLow - offset) : (barHigh + offset);
   //--- v1.21 FIX: per direct request - "the arrows should be the same
   //--- type of arrow used in tradepanel" - was OBJ_ARROW_BUY/SELL
   //--- (MT5's own fixed-size chevron glyphs, not independently
   //--- color/width-styleable the same way). TradePanel_EA.mq5 uses
   //--- OBJ_ARROW_UP/DOWN + ANCHOR_TOP/BOTTOM for every one of its own
   //--- signal arrows (DrawEmaCrossArrow, DrawCandleArrow, etc.) - now
   //--- matched exactly so a signal looks the same regardless of which
   //--- of the two programs drew it.
   if(ObjectFind(0, nm) < 0)
     {
      if(!ObjectCreate(0, nm, isBuy ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, barTime, arrowPrice))
        {
         PrintFormat("Important_SR_Levels: ObjectCreate FAILED for signal %s - error %d", nm, GetLastError());
         return;
        }
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, nm, OBJPROP_COLOR, isBuy ? InpLevelBuyColor : InpLevelSellColor);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 2);
   ObjectSetDouble(0, nm, OBJPROP_PRICE, arrowPrice);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP,
                    StringFormat("%s %s %s level %s @ %s", layerTag, reasonTag, isBuy ? "BUY" : "SELL",
                                 DoubleToString(levelPrice, _Digits), TimeToString(barTime, TIME_DATE | TIME_MINUTES)));
  }

//+------------------------------------------------------------------+
//| v1.18: once-per-new-bar sweep deleting signal arrows older than    |
//| InpLevelSignalMaxAgeDays - same weekly rolling-window convention   |
//| every other overlay in this project already uses. The bar time is  |
//| baked into each object's own name (see DrawLevelSignal), so this   |
//| needs no separate array/lookup, just a string parse per object.    |
//+------------------------------------------------------------------+
void CleanupOldLevelSignals()
  {
   datetime cutoff = TimeCurrent() - (datetime)((long)InpLevelSignalMaxAgeDays * 86400);
   int total = ObjectsTotal(0, 0, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, PFX_SIG) != 0) continue;
      int p1 = StringFind(nm, "_", StringLen(PFX_SIG));     // end of layerTag
      if(p1 < 0) continue;
      int p2 = StringFind(nm, "_", p1 + 1);                 // end of the baked-in bar time
      if(p2 < 0) continue;
      datetime barTime = (datetime)StringToInteger(StringSubstr(nm, p1 + 1, p2 - p1 - 1));
      if(barTime > 0 && barTime < cutoff) ObjectDelete(0, nm);
     }
  }

//+------------------------------------------------------------------+
//| v1.18: per direct request - "add signals specific to these levels |
//| if price bounces off... not necessarily just a rejection candle,   |
//| could break through and back up". Evaluated once per new CLOSED   |
//| chart bar (shift 1), against whichever levels in this layer are    |
//| CURRENTLY shown (nearest 2 above/2 below - see SRLevel.shown).     |
//| Two signal types, see InpShowLevelSignals' own comment for the     |
//| exact definitions: BOUNCE (same-bar rejection, the bar's range      |
//| touches/crosses the level but its close doesn't) and BREAK+BACK    |
//| (close genuinely flips sides, then a later bar within              |
//| InpBreakBackMaxBars flips back) - both close-based, so neither can |
//| repaint once drawn (a closed bar's close never changes).           |
//+------------------------------------------------------------------+
void CheckLevelSignals(SRLevel &levels[], const string layerTag,
                        const double close1, const double close2,
                        const double high1, const double low1, const datetime t1,
                        const double atrVal)
  {
   if(!InpShowLevelSignals) return;
   long maxBreakBackSecs = (long)InpBreakBackMaxBars * (long)PeriodSeconds();
   for(int k = 0; k < ArraySize(levels); k++)
     {
      if(!levels[k].shown) continue;
      double lvl = levels[k].price;
      //--- v1.21: "close proximity" distance for the Bounce redesign -
      //--- same fallback chain DrawLevelSignal already uses elsewhere in
      //--- this file, so it still works on the rare bar where the ATR
      //--- handle isn't ready.
      double proximityDist = (atrVal > 0.0) ? InpBounceProximityATR * atrVal
                                             : (high1 - low1) * InpBounceProximityATR;
      if(proximityDist <= 0.0) proximityDist = lvl * 0.0005;

      int side1 = (close1 > lvl) ? 1 : -1;
      //--- v1.19 FIX (Opus-found, real bug): used to reuse the stored
      //--- levels[k].side instead of recomputing from close2 whenever
      //--- side was already initialized - but "side" is only ever
      //--- updated when this level was SHOWN and evaluated, not every
      //--- bar. A level that drops out of the nearest-2/2 for several
      //--- bars (flicker) or whose price shifts slightly from a new
      //--- merge (intraday layer, RegisterTouchG averages price on
      //--- merge) leaves "side" referring to a stale bar/stale price -
      //--- comparing against it could arm a fake break the moment the
      //--- level reappears or merges, even though price never actually
      //--- crossed it between two CONSECUTIVE evaluations. Always
      //--- recomputing from close2 (the actual previous closed bar,
      //--- against THIS call's current level.price) is exactly what a
      //--- correctly-updated stored side would already equal in the
      //--- normal case, and removes the stale-state class of bug
      //--- entirely - levels[k].side is still recorded below for any
      //--- future/diagnostic use, just no longer trusted as an input here.
      int side2 = (close2 > lvl) ? 1 : -1;
      bool brokeThisBar = (side1 != side2);

      if(brokeThisBar)
        {
         if(levels[k].breakDir != 0 && side1 == -levels[k].breakDir &&
            (long)(t1 - levels[k].breakTime) <= maxBreakBackSecs)
           {
            //--- reclaimed the original side within the allowed window -
            //--- a failed breakout/breakdown, signal in the reclaim's direction
            DrawLevelSignal(side1 > 0, lvl, high1, low1, t1, layerTag, "BreakBack");
            levels[k].breakDir = 0;
           }
         else
           {
            //--- fresh break (first time, or a new break superseding an
            //--- old unresolved one) - just arm it, no signal yet
            levels[k].breakDir = side1;
            levels[k].breakTime = t1;
           }
         //--- v1.21: a genuine break through the level is BreakBack's own
         //--- territory, not a Bounce approach - drop any pending Bounce
         //--- watch rather than let it linger and confirm on a break bar.
         levels[k].rejPendingSide = 0;
        }
      else
        {
         //--- v1.21 REDESIGN (per direct request - "the rejection needs
         //--- to be more specific, also in close proximity to the line,
         //--- but we need to wait for the rejection of the 2nd or 3rd
         //--- candle for a valid rejection"): a single wick touching the
         //--- level and closing away used to fire Bounce immediately -
         //--- now that only ARMS a pending watch; the signal itself only
         //--- fires once a LATER bar (counting the approach bar as
         //--- candle 1, this is candle 2 or candle 3 - i.e. the 1st or
         //--- 2nd bar AFTER the approach, not the approach bar itself)
         //--- confirms by closing back on the same side AND clear of
         //--- the proximity band again - a real, held rejection, not a
         //--- single-bar wick.
         if(levels[k].rejPendingSide != 0)
           {
            levels[k].rejPendingAge++;
            bool sideMatches = (side1 == levels[k].rejPendingSide);
            bool clearedAway = (MathAbs(close1 - lvl) > proximityDist);
            if(levels[k].rejPendingAge == 1 || levels[k].rejPendingAge == 2)
              {
               if(sideMatches && clearedAway)
                 {
                  DrawLevelSignal(levels[k].rejPendingSide > 0, lvl, high1, low1, t1, layerTag, "Bounce");
                  levels[k].rejPendingSide = 0;
                 }
               else if(levels[k].rejPendingAge == 2)
                 {
                  //--- 2nd candle didn't confirm and this (the 3rd) didn't
                  //--- either - give up, no signal for this approach
                  levels[k].rejPendingSide = 0;
                 }
               //--- else: 2nd candle didn't confirm yet, one more chance
               //--- (the 3rd) still coming - keep watching
              }
            else
              {
               //--- already past the 3rd candle with no resolution
               //--- (shouldn't normally happen given the two branches
               //--- above, but a defensive catch-all) - stop watching
               levels[k].rejPendingSide = 0;
              }
           }
         //--- arm a NEW watch only if nothing is already pending on this
         //--- level and this bar's range actually came within the
         //--- proximity band of it - "close proximity to the line"
         if(levels[k].rejPendingSide == 0)
           {
            bool nearLevel = (low1 - proximityDist <= lvl && lvl <= high1 + proximityDist);
            if(nearLevel)
              {
               levels[k].rejPendingSide = side1;
               levels[k].rejPendingAge = 0;
              }
           }
        }

      //--- a pending break that never got reclaimed within the window is
      //--- just a confirmed move now, not a trade setup - stop watching it
      if(levels[k].breakDir != 0 && (long)(t1 - levels[k].breakTime) > maxBreakBackSecs)
         levels[k].breakDir = 0;

      levels[k].side = side1;
     }
  }

//+------------------------------------------------------------------+
//| v1.18: per direct request - "a push notification and alert if     |
//| price is coming close to one of these levels". Same two-part       |
//| hysteresis pattern already proven in TradePanel_EA's                |
//| CheckCrossProximity: latches once fired so it can't repeat every    |
//| tick while price sits near the threshold, only resets once price    |
//| has clearly moved back away (1.5x the threshold) - plus an explicit |
//| per-level cooldown on top, in case price re-enters and leaves the    |
//| 1.5x band repeatedly in a short span.                               |
//+------------------------------------------------------------------+
void CheckLevelProximityAlerts(SRLevel &levels[], const double currentPrice, const string layerLabel)
  {
   if(!InpEnableProximityAlert || g_atrHandleSig == INVALID_HANDLE) return;
   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(g_atrHandleSig, 0, 1, 1, atrBuf) != 1 || atrBuf[0] <= 0.0) return;
   double threshold = InpProximityAlertATRMult * atrBuf[0];
   if(threshold <= 0.0) return;

   for(int k = 0; k < ArraySize(levels); k++)
     {
      if(!levels[k].shown) continue;
      double dist = MathAbs(levels[k].price - currentPrice);
      if(dist <= threshold)
        {
         if(levels[k].proxAlerted) continue;
         if(TimeCurrent() - levels[k].lastProxAlertAt < InpProximityAlertCooldownMin * 60) continue;
         string dir = (currentPrice > levels[k].price) ? "approaching from above" : "approaching from below";
         string msg = StringFormat("%s %s: price %s %s level %s (%s)",
                                    _Symbol, layerLabel, DoubleToString(currentPrice, _Digits), dir,
                                    DoubleToString(levels[k].price, _Digits),
                                    StringFormat("%.2f ATR away", dist / atrBuf[0]));
         //--- v1.20 FIX (real bug, caused an actual freeze report):
         //--- Alert() pops a BLOCKING modal dialog. Right after a fresh
         //--- attach/recompile, every level's latch starts un-fired - if
         //--- several of the up to ~16 shown levels across all 4 layers
         //--- happened to sit within the threshold of current price at
         //--- once (easy in a tight range), they ALL fired Alert() in
         //--- the SAME call, stacking multiple blocking popups - which
         //--- is exactly what "the chart is frozen" looks like from the
         //--- outside. PlaySound() gives an audible cue without
         //--- blocking anything; SendNotification (push) + Print
         //--- (journal) already cover the "tell me" part non-blocking.
         SendNotification(msg);
         PlaySound("alert.wav");
         Print("Important_SR_Levels ProximityAlert: ", msg);
         levels[k].proxAlerted = true;
         levels[k].lastProxAlertAt = TimeCurrent();
        }
      else if(dist > threshold * 1.5)
         levels[k].proxAlerted = false;
     }
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
   //--- v1.10/v1.14: the intraday (chart's own timeframe) fractal scan is
   //--- OFF by default (InpShowIntradayLevels) - per direct request to
   //--- focus on H4 and up instead. It's now a separate function (see
   //--- its own comment) so whatever it does or returns internally can
   //--- never skip the independent H4/daily/weekly/recent-HL layers
   //--- below, regardless of whether intraday is on or off.
   //--- v1.15 FIX (Opus-found): capture the return so a "not handled yet"
   //--- result (ATR not ready on fresh attach, the routine case) makes
   //--- OnCalculate return 0 below instead of rates_total - otherwise
   //--- the intraday backfill was silently and permanently skipped.
   //--- InpShowIntradayLevels off (the default) behaves exactly as
   //--- before: intradayOk stays true, no effect on the return value.
   bool intradayOk = true;
   if(InpShowIntradayLevels)
      intradayOk = ComputeIntradayLevels(rates_total, prev_calculated, time, high, low);

   //--- v1.23 FIX (real bug, confirmed from the actual Experts log - 3
   //--- OnInit events in 2 minutes, each immediately followed by ALL
   //--- THREE of H4/daily/weekly doing a full rescan in the SAME
   //--- OnCalculate call): g_lastH4BarTime/g_lastDailyBarTime/
   //--- g_lastWeeklyBarTime are all reset to 0 together in OnInit, so the
   //--- very next tick sees all three as "needs a fresh backfill" and
   //--- ScanHigherTF() runs full-history (up to 4995 bars each) for all
   //--- three, back to back, in ONE blocking call - ~11,300 bars of
   //--- fractal+ATR+clustering work synchronously, which is genuinely
   //--- heavy enough to freeze the terminal for however long it takes,
   //--- worse every time OnInit re-fires (attach, any input change, or a
   //--- timeframe/symbol switch). A steady-state call (no fresh backfill
   //--- needed) was always cheap - this only ever hit the three-at-once
   //--- case right after a reinit. Fixed: a fresh (lastBarTime==0) layer
   //--- only gets its backfill if no OTHER layer has already used this
   //--- call's one-fresh-backfill budget - the other(s) simply wait one
   //--- extra tick (lastBarTime stays 0, tried again next call), spreading
   //--- 3 heavy backfills across 3 ticks instead of stacking them in 1.
   //--- Zero effect on steady-state behavior (a non-fresh layer is
   //--- unaffected either way).
   bool freshBudgetUsed = false;
   if(InpShowH4Levels)
     {
      bool fresh = (g_lastH4BarTime == 0);
      if(!fresh || !freshBudgetUsed)
        {
         ScanHigherTF(PERIOD_H4, g_levelsH4, PFX_H4, InpH4SupportColor, InpH4ResistanceColor,
                      g_atrHandleH4, g_lastH4BarTime);
         if(fresh) freshBudgetUsed = true;
        }
     }
   if(InpShowDailyLevels)
     {
      bool fresh = (g_lastDailyBarTime == 0);
      if(!fresh || !freshBudgetUsed)
        {
         ScanHigherTF(PERIOD_D1, g_levelsD, PFX_D, InpDailySupportColor, InpDailyResistanceColor,
                      g_atrHandleD, g_lastDailyBarTime);
         if(fresh) freshBudgetUsed = true;
        }
     }
   if(InpShowWeeklyLevels)
     {
      bool fresh = (g_lastWeeklyBarTime == 0);
      if(!fresh || !freshBudgetUsed)
        {
         ScanHigherTF(PERIOD_W1, g_levelsW, PFX_W, InpWeeklySupportColor, InpWeeklyResistanceColor,
                      g_atrHandleW, g_lastWeeklyBarTime);
         if(fresh) freshBudgetUsed = true;
        }
     }
   //--- v1.24 FIX: used to be gated on InpShowRecentHL alone - with that
   //--- now defaulted OFF (per-day replaces it as the default view), the
   //--- new per-day lines need ScanRecentHL() to still run whenever
   //--- EITHER toggle is on, not just the old combined one.
   if(InpShowRecentHL || InpShowRecentHLPerDay)
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
   if(GetTickCount64() - g_lastUiRefreshMs < 1000) return(intradayOk ? rates_total : 0);
   g_lastUiRefreshMs = GetTickCount64();

   //--- v1.09: cap how many levels per layer are actually drawn
   //--- v1.17: current price for the nearest-above/nearest-below filter -
   //--- BID is fine here, this is purely about which lines to show, not
   //--- a trade-execution price.
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   ApplyTopNFilter(g_levels,   InpMinTouchesToShow,   InpShowTopN, InpSupportColor,         InpResistanceColor,
                    currentPrice, InpShowNearestOnly, InpNearestCount);
   ApplyTopNFilter(g_levelsH4, InpDWMinTouchesToShow, InpShowTopN, InpH4SupportColor,       InpH4ResistanceColor,
                    currentPrice, InpShowNearestOnly, InpNearestCount);
   ApplyTopNFilter(g_levelsD,  InpDWMinTouchesToShow, InpShowTopN, InpDailySupportColor,    InpDailyResistanceColor,
                    currentPrice, InpShowNearestOnly, InpNearestCount);
   ApplyTopNFilter(g_levelsW,  InpDWMinTouchesToShow, InpShowTopN, InpWeeklySupportColor,   InpWeeklyResistanceColor,
                    currentPrice, InpShowNearestOnly, InpNearestCount);

   //--- v1.08: refresh every visible label's position to the right edge
   //--- every call, not just when a level is actually touched
   datetime nowTime = TimeCurrent();
   RefreshRightEdgeLabels(g_levels,   InpMinTouchesToShow,   nowTime);
   RefreshRightEdgeLabels(g_levelsH4, InpDWMinTouchesToShow, nowTime);
   RefreshRightEdgeLabels(g_levelsD,  InpDWMinTouchesToShow, nowTime);
   RefreshRightEdgeLabels(g_levelsW,  InpDWMinTouchesToShow, nowTime);
   RefreshRecentHLLabels(nowTime);
   RefreshRecentHLPerDayLabels(nowTime);
   RefreshRecentOCLabels(nowTime);

   //--- v1.18: level-reaction signals, evaluated once per new CLOSED
   //--- chart bar (shift 1) regardless of which layer(s) a level came
   //--- from - price reacting to a line drawn on the chart is a single
   //--- visible event no matter which timeframe produced that line.
   //--- Needs rates_total>=3 (a closed bar at shift 1 plus one more at
   //--- shift 2 to compare sides against). Runs AFTER ApplyTopNFilter
   //--- above so levels[].shown reflects this call's own nearest-N pick,
   //--- not a stale one from the previous refresh.
   if((InpShowLevelSignals || InpEnableProximityAlert) && rates_total >= 3)
     {
      int i1 = rates_total - 2, i2 = rates_total - 3;
      datetime t1 = time[i1];
      if(InpShowLevelSignals && t1 != g_lastSigBarTime)
        {
         double close1 = close[i1], close2 = close[i2], high1 = high[i1], low1 = low[i1];
         //--- v1.21: fetched ONCE per new bar and passed in, rather than
         //--- each of the up to 64 (4 layers x up to 16 shown levels)
         //--- per-level checks re-reading it - same shift-1 CopyBuffer
         //--- pattern DrawLevelSignal/CheckLevelProximityAlerts already use.
         double sigAtr = 0.0;
         if(g_atrHandleSig != INVALID_HANDLE)
           {
            double sigAtrBuf[];
            ArraySetAsSeries(sigAtrBuf, true);
            if(CopyBuffer(g_atrHandleSig, 0, 1, 1, sigAtrBuf) == 1) sigAtr = sigAtrBuf[0];
           }
         CheckLevelSignals(g_levels,   "Intraday", close1, close2, high1, low1, t1, sigAtr);
         CheckLevelSignals(g_levelsH4, "H4",       close1, close2, high1, low1, t1, sigAtr);
         CheckLevelSignals(g_levelsD,  "Daily",    close1, close2, high1, low1, t1, sigAtr);
         CheckLevelSignals(g_levelsW,  "Weekly",   close1, close2, high1, low1, t1, sigAtr);
         //--- v1.20 FIX (real bug, confirmed the likely other cause of
         //--- the freeze report): this used to call CleanupOldLevelSignals
         //--- every single new chart bar - but that function scans
         //--- ObjectsTotal(0,0,-1), which is EVERY object on the WHOLE
         //--- chart, not just this indicator's own - including
         //--- TradePanel_EA's thousands of MA/VWAP/signal objects if it's
         //--- on the same chart. On M5 that's a multi-thousand-object
         //--- synchronous ObjectName() walk every 5 minutes; across 6
         //--- charts, 6x that. Arrows only need cleaning up once every
         //--- InpLevelSignalMaxAgeDays (7 by default) anyway, so once a
         //--- calendar day is plenty - cuts this cost by roughly 96x
         //--- (M15) to 288x (M5) with zero visible difference.
         datetime today = (datetime)((long)(t1 / 86400) * 86400);
         if(today != g_lastSigCleanupDay)
           {
            CleanupOldLevelSignals();
            g_lastSigCleanupDay = today;
           }
         g_lastSigBarTime = t1;
        }
      if(InpEnableProximityAlert)
        {
         CheckLevelProximityAlerts(g_levels,   currentPrice, "Intraday");
         CheckLevelProximityAlerts(g_levelsH4, currentPrice, "H4");
         CheckLevelProximityAlerts(g_levelsD,  currentPrice, "Daily");
         CheckLevelProximityAlerts(g_levelsW,  currentPrice, "Weekly");
        }
     }

   return(intradayOk ? rates_total : 0);
  }
