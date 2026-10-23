//+------------------------------------------------------------------+
//|                                               TradePanel_EA.mq5  |
//|  Movable on-chart manual trading widget. NOT a strategy - no    |
//|  automated entry/exit logic at all, just buttons that place or  |
//|  close trades on command.                                       |
//|                                                                   |
//|  Run this on its OWN chart window (MT5 allows only one EA per   |
//|  chart) - open a second chart of the same symbol/timeframe next |
//|  to whatever strategy EA is already running, and attach this   |
//|  one there. It manages ONLY positions it opened itself (matched |
//|  by its effective magic number, see InpMagic) - the stats row,  |
//|  CLOSE ALL, 25/50/75% partial                                   |
//|  close, and Set SL/Set TP all act exclusively on this panel's   |
//|  own trades, never on a strategy EA's live position.            |
//|                                                                   |
//|  SAFETY: placing a NEW batch of trades (the "PLACE xN" buttons) |
//|  requires ARM then a second click within InpArmSeconds - a      |
//|  single misclick cannot fire a batch of market orders. Closing  |
//|  (25/50/75%/CLOSE ALL) fires immediately - reducing risk never   |
//|  needs a confirm step.                                           |
//+------------------------------------------------------------------+
#property copyright "Marco"
//+------------------------------------------------------------------+
//| v2.25: LOCKED to M15 - this is the M15-only copy of TradePanel_EA.   |
//| OnInit() below refuses to run (INIT_FAILED, with an Alert()) if   |
//| attached to any chart whose timeframe isn't M15. The TradePanel_EA_M5.mq5 |
//| sibling is identical except for this one constant -               |
//| EXPECTED_PERIOD - and its own symmetric version of this same      |
//| refusal. Rebuilt from the v2.25 base (zones now always drawn on    |
//| formation, spent-zone colour change), so this copy carries that    |
//| too.                                                                |
//+------------------------------------------------------------------+
#define EXPECTED_PERIOD PERIOD_M15
#property version   "2.27"
//--- 2.25: Locked copy (M15 only) - see header block above. Rebuilt from
//--- v2.25 (zones always drawn on formation, spent-zone colour) so this copy carries that too.
//--- 2.24: Per report ("mt5 still hanging... this happened when trying
//--- to size the chart") - two things. (1) Capped the remaining 5
//--- overlays' backfill (EmaCross, Stoch, Engulfing, Rejection,
//--- RejectionM15) the same way FVG/Liquidity (v2.21) and Divergence/BB
//--- (v2.23) already were - these 5 are pre-existing and were tolerably
//--- fast ON THEIR OWN, but stacked with 4 brand-new overlays all doing
//--- their own OnInit-time scans in the same call, the combined
//--- synchronous cost was still enough to hang attach. All 9 overlays
//--- now bound their backfill scan to roughly InpSigDrawDays worth of
//--- bars instead of the entire chart history. (2) Checked the
//--- CHARTEVENT_CHART_CHANGE handler specifically (chart resizing fires
//--- this event too, not just timeframe switches) - MaintainOverlaySync()
//--- is already correctly guarded (confirmed: the full resync path only
//--- runs on an ACTUAL timeframe change, never on resize/scroll/zoom
//--- alone), so a resize does NOT re-trigger the heavy backfill path.
//--- The remaining, most likely explanation for a resize specifically
//--- hanging is MT5's own chart engine having to re-layout every object
//--- on the chart when the window size changes - this EA's MA/VWAP
//--- overlay alone draws ~7,900 hand-drawn OBJ_TREND segments at the
//--- existing InpMAHistoryBars=2500 default (long predates this
//--- session), and this session's new overlays add several hundred more
//--- on top. This is a rendering cost inside MT5 itself, not something
//--- fixable in EA code - the lever is reducing total object count
//--- (InpMAHistoryBars, or how many overlays are left enabled at once).
//--- 2.23: Opus-reviewed again (panel buttons + remaining lag). Real
//--- fixes: (1) Divergence and BB (both new this session) were still
//--- backfilling the ENTIRE chart history on attach, same shape of
//--- problem as the v2.21 FVG/Liquidity hang, just O(n) not O(n^2) -
//--- now capped like every other overlay, shrinking the attach-time
//--- stall that was likely the real reason the panel looked unresponsive
//--- right after attach (the event thread is single-threaded - while
//--- OnInit is busy, clicks queue up or get dropped). (2) FVG/Liquidity
//--- signal object names used the zone's ARRAY INDEX (zi), which
//--- CompactZones() (new in v2.21) reshuffles - a replayed bar could
//--- give the same zone's signal a different id and draw a duplicate
//--- arrow/SL. Now derived from the zone's own stable rectName instead.
//--- (3) The 6 lot/count/delay +/- stepper buttons never reset
//--- OBJPROP_STATE after a click - the action DID fire each time, but
//--- the button stayed drawn pressed until the NEXT click, which reads
//--- exactly like "the +/- buttons aren't working". Fixed to match
//--- every other button on the panel. (4) g_nCtrls/g_ctrls[] and
//--- g_editFocused were never reset in OnInit() - MT5 keeps globals
//--- across a reinit, so BuildPanel() was appending to whatever
//--- g_ctrls[] a PREVIOUS compile left behind rather than starting
//--- clean; after many recompiles this session, DragPanel() would have
//--- been moving each duplicated widget multiple times per drag -
//--- exactly "i can not make changes on the window panel". Also, per
//--- direct request ("can we limit history to a week... oldest days
//--- signals are removed") - InpSigDrawDays was already 7 by default
//--- (nothing to change there), but InpFvgMaxAgeDays/InpLiqMaxAgeDays
//--- (10) now match it for consistency across every overlay.
//--- 2.22: Several changes, all per direct request. (1) Every entry-
//--- arrow's WIDTH reduced from 2 to 1 ("smaller"). (2) Every entry-
//--- arrow's offset-from-candle increased ("spaced away from candles") -
//--- e.g. InpEmaCrossArrowOffsetATR 1.0->1.6, InpStochArrowOffsetATR
//--- 0.5->1.1, the rest (Cdl/Rej/RejM15/Div/BB/Fvg/Liq) 1.3->1.9. (3)
//--- Every one of the 20 entry-arrow buy/sell colours (10 overlay kinds
//--- x buy/sell) regenerated algorithmically (even hue spacing - buys
//--- across the green->violet "cool" arc, sells across the magenta->red
//--- ->yellow "warm" arc) rather than picked by eye - the previous
//--- v2.20 pass eliminated exact duplicates but left several pairs that
//--- were still visually near-identical (e.g. EmaCross Sell vs
//--- Divergence Hidden Sell, Lime vs Chartreuse) - "i see some arrows
//--- for different signals are still the same colours". (4) New
//--- NudgeClearOfMALine() - per "make sure the dont print over of
//--- indicators, like the moving averages" - pushes a marker clear of
//--- the live 21/50 EMA value at that bar, same one-directional-only
//--- convention as the existing NudgeAwayFromLastMarker/
//--- NudgeClearOfOtherOverlays. Wired into the 6 overlays that already
//--- compute e21/e50 locally (EmaCross, Engulfing, Rejection, Rejection
//--- M15, Divergence regular+hidden) - Stoch/BB/FVG/Liquidity don't
//--- currently compute e21/e50 and were left out of this pass, a known
//--- gap. The panel-button-unresponsiveness and remaining-lag reports
//--- are being investigated separately (background Opus review) - not
//--- addressed in this version.
//--- 2.21: Opus-reviewed (per direct request, "i dont want anymore
//--- issues") - found and fixed the ROOT CAUSE of "panel windows are
//--- missing, the moving averages and vwap are also now not visible,
//--- when you remove the EA everything stays behind". ComputeFvgSignals()
//--- and ComputeLiquiditySignals()'s BACKFILL requested the ENTIRE chart
//--- history (`available` - often 100,000+ bars) with no cap, unlike
//--- every other overlay in this file (which all gate their backfill
//--- via InpSigDrawDays). Combined with an O(bars x zones) inner scan
//--- (every bar re-checks every zone ever created) and zero compaction
//--- of spent/invalidated zones, this measured out to ~1.1 BILLION inner
//--- loop iterations on a 100k-bar GOLD M5 history - taking MINUTES
//--- inside OnInit(), which runs BEFORE BuildPanel()/the MA-VWAP
//--- backfill, so neither ever ran. When the user then removed the EA
//--- while it was still stuck, MT5 force-killed it without ever calling
//--- OnDeinit(), so nothing got cleaned up either - explaining all three
//--- symptoms at once. This is also why FVG/Liquidity zones themselves
//--- were never seen - OnInit never got far enough to finish building
//--- them. Fixed at the root: both overlays' backfill SCAN WINDOW is now
//--- capped to roughly InpFvgMaxAgeDays/InpLiqMaxAgeDays worth of bars
//--- (anything older gets pruned within one tick anyway, so scanning
//--- further back was always wasted work), actual object creation is
//--- now gated to InpSigDrawDays (same convention as every other
//--- overlay), and a new CompactZones() reclaims spent/invalidated
//--- zones' array slots immediately instead of leaving them to
//--- accumulate forever during live running. Also fixed, all Opus-found:
//--- (1) Divergence's arrow names ("reg_buy_"/"hid_buy_"/"reg_sell_"/
//--- "hid_sell_") never matched the single "arr_" entry
//--- NudgeClearOfOtherOverlays was checking for, so Divergence arrows
//--- were silently exempt from the cross-overlay collision check the
//--- whole time - fixed, and all four real name patterns added; (2) a
//--- bar that happens to be a confirmed pivot BOTH low and high (a
//--- single wide-range "outside" bar) could collide Divergence's SL line
//--- name (and, before this fix, its arrow name too) between the buy and
//--- sell branches, silently dropping the second one - names are now
//--- fully direction-distinct; (3) InpBBPeriod set to 0 or negative made
//--- SigBollinger() write mid[-1], an out-of-range crash - guarded.
//--- 2.20: Two changes, per direct request. (1) Every overlay's entry-
//--- arrow buy/sell colour audited for duplicates - clrLime was used by
//--- FIVE different overlays' buy signal (EMA Cross, Divergence Regular,
//--- BB, FVG, Liquidity) and clrRed by FOUR different sell signals
//--- (Divergence Regular, BB, FVG, Liquidity), clrDeepSkyBlue by two
//--- (Rejection M15 Buy, Divergence Hidden Buy) - every entry-arrow
//--- colour across all 10 overlay kinds is now distinct (InpDivRegBuyCol,
//--- InpDivRegSellCol, InpDivHidBuyCol, InpBBBuyCol, InpBBSellCol,
//--- InpFvgArrowBuyCol/SellCol, InpLiqArrowBuyCol/SellCol all changed -
//--- SL/TP line colours untouched, those were never the complaint). (2)
//--- REMOVED every overlay's TP (R:R) line - "remove all the RR lines
//--- take profit lines, leave the swing stop loss lines". The SL line
//--- is kept everywhere; the TP distance calculation itself is left in
//--- place (still used nowhere else, genuinely dead now, but removing it
//--- outright risked touching risk/SL logic unnecessarily for a change
//--- that's purely about what gets DRAWN).
//--- 2.19: NEW FVG (Fair Value Gap) and Liquidity (equal highs/lows)
//--- zone overlays, per direct request - "the fvg and liquidity blocks
//--- must also give buy and sell signals when price comes back to those
//--- levels to reject them". Both draw a lightly-shaded (OBJPROP_BACK,
//--- dim colour - not a solid block) zone, and both share one rule via
//--- the new ProcessZoneBar(): price wicking INTO the zone and CLOSING
//--- back out the way it came is the rejection signal (buy for a
//--- support zone, sell for resistance) with the same SL(swing)/TP(RR)
//--- convention as every other overlay; a candle CLOSING fully through
//--- the zone instead invalidates it, no signal. Either way the zone is
//--- removed the moment it's resolved - "when it becomes no longer
//--- valid can be removed". FVG = standard 3-candle imbalance (candle
//--- 3's low clears candle 1's high, or mirror). Liquidity = two
//--- confirmed swing highs (or lows), via the same fractal-window
//--- approach as the Divergence overlay, within InpLiqTolATR of each
//--- other - marks a resting-stops pool. Both capped (InpFvgMaxZones/
//--- InpLiqMaxZones) and age out (InpFvgMaxAgeDays/InpLiqMaxAgeDays) so
//--- the chart can't accumulate zones indefinitely. UNVALIDATED - chart
//--- overlay only, like every other overlay added this session.
//--- 2.18: Three changes, all per direct request. (1) REMOVED the
//--- trend-continuation overlay entirely (InpShowContSignals and
//--- everything under it) - it was already flagged UNVALIDATED/net
//--- loser (p=0.52 vs random) and the request was explicit: "lets remove
//--- the trend continuation signals." (2) Engulfing overlay gets two new
//--- confirmation filters, both default ON: InpCdlRequireTrend (skip an
//--- engulfing candle fighting the 21/50EMA trend - "on the wrong side
//--- of the trend") and InpCdlMinMADistATR (skip one printing within
//--- InpCdlMinMADistATR x ATR of either EMA - "too close to a moving
//--- average"). (3) NEW Bollinger outer-band rejection overlay
//--- (InpShowBBSignals) - per the attached chart examples: a bar closes
//--- BEYOND an outer Bollinger band, a later bar (within
//--- InpBBReentryLookback) closes back INSIDE - sells on re-entry from
//--- above the upper band, buys on re-entry from below the lower band.
//--- InpBBRequireRejection (default off, since "sometimes with a nice
//--- rejection candle" implies not always) optionally requires a
//--- same-direction rejection wick on the re-entry bar itself. Same
//--- SL(swing)/TP(RR), collision-nudging, and cooldown conventions as
//--- every other overlay. UNVALIDATED - chart overlay only.
//--- 2.17: NEW stochastic divergence overlay, per direct request - "can
//--- we include a buy sell signal with sl and tp for divergence,
//--- stochastic divergence". Both kinds: REGULAR divergence (price makes
//--- a new swing extreme the stochastic does NOT confirm - reversal
//--- signal) and HIDDEN divergence (price pulls back LESS than the
//--- stochastic does, during an existing trend - continuation signal,
//--- trend-filtered via 21 vs 50 EMA same as the Continuation overlay).
//--- Confirmed swing pivots found with the same fractal-window approach
//--- used elsewhere in this project (InpDivPivotWindow), each new pivot
//--- compared against the single previous pivot of the same type (no
//--- more state than that is kept) - InpDivMaxPivotGapBars caps how far
//--- apart the two compared pivots can be, so a years-old pivot never
//--- gets compared against today's. Same SL(swing)/TP(RR) exit,
//--- NudgeAwayFromLastMarker/NudgeClearOfOtherOverlays collision
//--- handling, per-kind cooldown (InpDivCooldownBars, same reasoning as
//--- InpContCooldownBars - divergence has no "open position" concept, so
//--- repeat signals of the same kind are expected, just not back-to-back
//--- every bar), and default-OFF alert (InpDivAlert) as every other
//--- overlay added since v2.16/2.17's notification-scoping change.
//--- UNVALIDATED - chart overlay only, like Rejection/Continuation.
//--- 2.16: Per direct request, push notifications are now reserved for
//--- only two things by default: the MA 21/50 gap CLOSING warning
//--- (InpEnableCrossAlert, unchanged - "when the moving averages are
//--- closing the gap") and the EMA21/50 cross itself, entry AND exit
//--- (InpEmaCrossAlert, unchanged - "when they actually cross"). Every
//--- other overlay's alert input now defaults OFF: InpEmaWeakenAlert,
//--- InpStochCrossAlert, InpCdlAlert, InpRejAlert, InpRejM15Alert,
//--- InpContAlert. Nothing about what's DRAWN on the chart changed -
//--- every overlay's arrows/lines still show exactly as before, this
//--- only quiets the push notifications. Any of these can be switched
//--- back on individually from the Inputs dialog if wanted later.
//--- 2.15: Fixed a real repeat-alert bug across 7 of the 8 signal
//--- overlays, per report: "the old trade panel still giving me the
//--- same rejection signal over and over." Every overlay except
//--- Stochastic (which deliberately deletes-and-replaces on a repeat
//--- same-direction signal, by design) used an ObjectFind-guarded draw
//--- function - if the chart object for a given bar already existed,
//--- the draw silently no-op'd - but the FireSigAlert() push
//--- notification right next to it fired UNCONDITIONALLY regardless of
//--- whether anything was actually new. If that bar's signal was ever
//--- reprocessed (a resync, a reinit, any path that re-walks already-
//--- handled history), the exact same alert would fire again, every
//--- time, even though nothing new ever appeared on the chart - which
//--- is exactly what "nothing on the chart" + "same signal over and
//--- over" together describe. Fixed on EMA Cross (entry, exit, AND the
//--- weakening marker - 3 separate spots), Engulfing, Rejection,
//--- Rejection M15, and Continuation: each now captures whether the
//--- object was genuinely new (ObjectFind BEFORE the draw call) and
//--- only alerts when it was.
//--- 2.14: Opus's object-count/rendering-lag audit, dispatched after
//--- repeated reports of signals printing much later than they should
//--- and "rejection signals and nothing on the chart". MEASURED FIRST
//--- (default inputs, real GOLD data, last 52 weeks, 7-day window): each
//--- MA line holds ~1,680 segments (the purge is time-based - 2500 bars
//--- of clock time, minus weekends), so ~5,000 for the 3 MAs; VWAP grows
//--- from 400 at attach to ~1,670 after a week (purged on the MA horizon,
//--- not its own 400 - same as Aurelius); all six signal overlays
//--- together are only ~265 objects on M5 (max ~450) and ~90 on M15.
//--- ~7,000 total on either timeframe - BELOW Aurelius_EA's own ~8,500+,
//--- which runs live fine. So object COUNT is NOT the problem, and
//--- shrinking InpSigDrawDays would remove ~4% of objects for nothing -
//--- left at 7. Nothing does a repeated full wipe+redraw in normal
//--- running either (SyncMAOverlays is one comparison unless the
//--- timeframe really changed). Found two real problems and one cheap
//--- cleanup, fixed here (none of this was the MA-sync bug from
//--- v2.05-2.11 - this was always a separate problem):
//--- (1) CheckNewBar() used to run EVERY overlay's own full-chart purge
//--- scan (~7,000 objects at default settings) right after computing
//--- that overlay, before moving to the next one - so a Rejection or
//--- Continuation signal (computed near the end of that list) sat
//--- behind up to 5 of those scans before its own arrow object even got
//--- created, and behind all 7 before the chart redraw that actually
//--- shows it. Combined into one HousekeepOldObjects() pass, moved to
//--- run AFTER the redraw (so a fresh signal is already visible first),
//--- and throttled to at most once per hour of bar time - the exact
//--- same cutoffs as before, just one scan instead of seven, and never
//--- blocking a signal from appearing.
//--- (2) OnTick() wrote CHART_SHOW_TRADE_LEVELS unconditionally on
//--- EVERY tick, which is itself a chart-property change - MT5 answers
//--- a chart-property change with a CHARTEVENT_CHART_CHANGE event, the
//--- same event this file's MA-sync logic (SyncMAOverlays/
//--- MaintainOverlaySync, v2.09-2.11) reacts to. On an active Gold
//--- chart that's many ticks a second, i.e. a self-inflicted stream of
//--- chart-change events the EA was generating for itself. Now only
//--- writes it when the value actually differs from what's already set.
//--- (The cheap cleanup - its real cost can't be measured without MT5,
//--- so it is NOT claimed as a proven cause of the delay.)
//--- (3) Each overlay's own anti-collision (NudgeAwayFromLastMarker)
//--- only ever checked against that SAME overlay's own previous marker
//--- - two DIFFERENT overlays (e.g. Rejection and Continuation) could
//--- still draw their arrows on top of each other at the same bar/price,
//--- which looks exactly like "I got the alert but nothing's on the
//--- chart" (the arrow IS there, just hidden under another one). New
//--- NudgeClearOfOtherOverlays() checks all 8 entry-marker object names
//--- for that same bar across every overlay and nudges clear of
//--- whichever ones are already there, on top of the existing same-
//--- overlay nudge. Worst case it fixes: on an M15 CHART, Rejection and
//--- Rejection M15 run the identical calculation on identical bars, so
//--- EVERY Rejection arrow was drawn exactly underneath its Rejection
//--- M15 twin - two alerts, one visible arrow, in the M15 colour. (The
//--- two overlays still both fire on an M15 chart - turn
//--- InpShowRejectSignalsM15 off there if one alert is enough.)
//--- NOT changed, on purpose - it is signal logic, not rendering, and it
//--- is most of what "printed much later" feels like: every overlay only
//--- fires once its bar has CLOSED, and its arrow sits on that bar's
//--- OPEN time - on M15 a push can arrive up to 15 min after the setup
//--- started forming, pointing at a candle that is already one back. The
//--- EMA cross also waits InpEmaConfirmBars=2 more closed bars after the
//--- cross itself (10 min on M5, 30 min on M15) - validated, by design.
//--- Rejection M15 on an M5 chart prints at the M15 close but sits on
//--- the M15 bar's open time, i.e. 3 M5 candles back.
//--- Also: the panel's own title now shows which timeframe this
//--- instance is running on (e.g. "TRADE PANEL [M15]"), per direct
//--- request, so two separate panels (one per timeframe - the agreed
//--- setup after this file's timeframe-switch troubles) are obviously
//--- distinguishable at a glance instead of both saying the same
//--- generic "TRADE PANEL".
//--- 2.13: Opus-reviewed fix to v2.12's auto-magic-number feature - a
//--- real bug found before it ever shipped on a live chart. The v2.12
//--- formula used (int)PERIOD_CURRENT, which is the MQL5 SYMBOLIC
//--- constant meaning "the chart's own timeframe" when passed as a
//--- function argument - its actual integer value is always 0, not the
//--- real timeframe. Every panel instance would have silently derived
//--- the SAME magic number regardless of which timeframe it was on,
//--- completely defeating the point and risking two "separate" panels
//--- quietly managing each other's real trades with no warning at all.
//--- Fixed: uses _Period (the correct live value) instead. Also dropped
//--- the old symbol-length term from the formula - PositionMatches()
//--- already filters on POSITION_SYMBOL==_Symbol on its own, so that
//--- term only added collision risk between same-length symbol names
//--- without preventing anything real; timeframe is the only axis this
//--- needs to separate. Also fixed a stale comment near the top of this
//--- file still referencing "InpMagic" directly for position matching.
//--- 2.12: Per direct request, for running two separate panel instances
//--- (one attached to an M5 chart, one to an M15 chart, instead of
//--- switching one chart's own timeframe - the agreed path forward
//--- after repeated trouble with runtime timeframe-switch handling in
//--- this file): InpMagic==0 now means "auto" - OnInit derives a magic
//--- number so the two panels never manage each other's trades. Any
//--- non-zero InpMagic is used exactly as typed, unchanged from every
//--- prior version - an existing single-panel setup on the default
//--- (20261014) is unaffected unless the magic is deliberately set to 0.
//--- (The formula itself had a real bug - see the 2.13 entry above,
//--- which fixes it before this ever reached a live chart.)
//--- 2.11: Opus did one final review of v2.10 before shipping and found
//--- two real gaps, both fixed here. (1) The 15s hard cap gave up
//--- PERMANENTLY - if history only became ready after 15s, the MA lines
//--- stayed incomplete forever until the next actual timeframe switch,
//--- so "guaranteed to converge" only meant guaranteed to stop trying,
//--- not guaranteed to end up correct. (2) The every-~2s retry while
//--- waiting redrew the FULL MA/VWAP history and rebuilt the panel on
//--- every attempt - in the slow-history case that's 7-8 wipe+redraw+
//--- rebuild cycles over 15s, a visible blink roughly every 2 seconds.
//--- Redesigned to draw AT MOST TWICE per switch, never on a repeating
//--- interval: once immediately (so something shows right away instead
//--- of staying blank) and once more the moment MAHistoryReady()
//--- actually turns true, however long that takes - no cap on that
//--- second draw, so it can't give up and stay wrong forever. A 15s
//--- hard cap still exists only as a one-time last-resort SECOND
//--- attempt if the first draw already happened before 15s and nothing
//--- had turned ready yet. Nothing redraws in between - no blinking.
//--- 2.10: Two fixes, per a real Experts-log excerpt the user pasted
//--- after v2.09 still didn't fix the MA staleness.
//--- (1) Found a genuine, longstanding format-string bug while reading
//--- that log: EmaCrossSignal's ENTRY and EXIT Print lines each had 6
//--- %s/%d placeholders but only 5 arguments (the actual price was
//--- missing from both) - MQL5's own fallback for a placeholder with no
//--- matching argument is the literal text "(non-string passed)",
//--- exactly what showed up as "E50=(non-string passed)" in the user's
//--- log. Fixed both lines - price is now included, every other value
//--- shifts back to its correct placeholder. Checked every other
//--- overlay's own Print line (RejectSignal2/RejectSignalM15/ContSignal/
//--- EmaWeakenSignal) - all of those already had the right count.
//--- (2) The real reason the MA lines were still stuck: v2.09's
//--- MAHistoryReady() gate made the post-switch backfill wait for the
//--- new MA handles to report calculated data before drawing anything -
//--- but a real-world MT5 quirk is that BarsCalculated() on a handle for
//--- a timeframe that hasn't been recently viewed can stay stuck at -1
//--- for a long time, sometimes indefinitely, if history for that
//--- symbol/timeframe isn't cached yet. Since step 1 already wipes the
//--- old lines immediately on a switch, a gate that never opens meant
//--- the chart was left with NOTHING drawn, forever - "still doing the
//--- same thing" was this, not the original jagged-old-data symptom.
//--- Fixed: SyncMAOverlays() no longer waits for permission to draw -
//--- it draws on the very next check after a switch, whether or not the
//--- handles are fully ready yet (an early attempt just means a few of
//--- the most recent bars are briefly missing, which is harmless and
//--- self-heals), then keeps retrying every ~2s (throttled, can't flash)
//--- until the handles genuinely do report ready, or 15s pass and it
//--- accepts whatever it has. Guaranteed to converge either way - never
//--- stuck waiting on a condition that might not arrive.
//--- 2.09: Fixed BOTH timeframe-switch bugs reported after v2.06 - "on
//--- the 15min i see the 5min data moving averages, sometimes it flips
//--- correct after a while other times it stays like this", then "now
//--- everything keeps flashing". Both came from the same piece of code:
//--- the CHARTEVENT_CHART_CHANGE handler that v2.05 turned into a full
//--- MA rebuild and v2.06 then put a 2-second debounce on.
//--- WHY THE MAs COULD STAY WRONG FOREVER: (a) the v2.06 debounce didn't
//--- postpone the rebuild, it THREW IT AWAY - inside the 2s window it
//--- just rebuilt the panel and returned, without recreating the MA
//--- handles, without wiping the old timeframe's lines, and without
//--- recording that the switch had been handled. The only thing that
//--- could ever fix it afterwards was some LATER, unrelated chart event
//--- (a scroll, a zoom, an autoscroll shift) arriving after the 2s were
//--- up - "sometimes it flips correct after a while". If none came, it
//--- stayed wrong for good, because nothing else (not OnTimer, not
//--- OnTick) ever checked. Meanwhile every new bar was drawn with the
//--- OLD timeframe's MA handle at the NEW timeframe's bar times, next to
//--- the old lines that were never wiped - the jagged/doubled lines in
//--- the screenshot. (b) It was gated on g_emaxPeriod, a variable that
//--- belongs to the EMA-cross signal overlay and only changes as a side
//--- effect of that overlay's own resync - the MAs had no state of their
//--- own saying which timeframe they were built for. (c) Even the
//--- normal path (OnInit) drew the whole MA history IMMEDIATELY after
//--- creating brand-new iMA handles. A fresh handle usually hasn't
//--- calculated yet (this file's own Stochastic notes say exactly this),
//--- so the history could come up partly or entirely missing, and
//--- nothing ever went back to fill it in - the per-bar update only ever
//--- draws the newest bar.
//--- WHY EVERYTHING KEPT FLASHING: CHARTEVENT_CHART_CHANGE is NOT a
//--- "timeframe changed" event - MT5 fires it for every scroll, zoom,
//--- resize, autoscroll shift on a new bar, price-scale refit as ticks
//--- move the range, and chart property changes made in code (OnTick
//--- re-sets CHART_SHOW_TRADE_LEVELS on EVERY tick). v2.06 wiped and
//--- rebuilt the whole panel on every one of those events while a switch
//--- was still unresolved, and the first one after the 2s window wiped
//--- every MA/VWAP line and all 5 signal overlays and redrew 2500 bars -
//--- all visible on screen, driven by a stream of events that has
//--- nothing to do with timeframes.
//--- THE FIX - one routine, SyncMAOverlays(), is now the ONLY place MA
//--- handles/lines are ever rebuilt, and it's a no-op unless something
//--- really changed: (1) if the chart's timeframe differs from
//--- g_maPeriod (a new variable that belongs to the MAs alone), it
//--- recreates the handles, wipes the old lines at once, resyncs the
//--- signal overlays, records the new timeframe, and marks the history
//--- "backfill pending"; (2) while backfill is pending, it waits until
//--- the new handles have ACTUALLY finished calculating, then wipes and
//--- redraws the history ONCE and clears the flag. Both steps switch
//--- themselves off as they run, so each happens at most once per real
//--- timeframe change - scroll/zoom/ticks can never set them off. It's
//--- called from OnInit, every tick, every 2s OnTimer, and every
//--- CHART_CHANGE event - the 2s timer is the guarantee (the MAs are
//--- correct within ~2s of the new handles being ready, whatever the
//--- terminal does or doesn't send), the rest are just faster paths. The
//--- panel is only rebuilt when that routine actually drew something.
//--- Removed: the g_lastFullResyncMs debounce and the whole old rebuild
//--- block in the CHART_CHANGE handler. Not touched: anything else,
//--- including the Continuation cooldown (v2.07) and arrow sizes (v2.08).
//--- 2.08: Standardized every entry overlay's arrow SIZE, not just its
//--- shape (shape was already unified in v2.06) - per direct request,
//--- "all buy and sell signals all arrows, same size, different
//--- colours." EMA Cross/Stoch/Engulfing defaulted to width 1 (thin
//--- enough to look like a dot rather than a clear arrow, especially
//--- next to the Rejection/Continuation overlays' width-2 arrows) -
//--- all six entry overlays (EMA Cross, Stoch, Engulfing, Rejection,
//--- Rejection M15, Continuation) now default to width 2. Buy/sell
//--- placement was already correct before this (buy arrow below price
//--- pointing up, sell arrow above price pointing down) - confirmed,
//--- not changed.
//--- 2.07: Fixed the REAL reason signals were still missing at the
//--- marked points after the v2.06 direction fix. ComputeContSignals()
//--- had "if(dir == lastDir) continue" - a PERMANENT block on any repeat
//--- same-direction signal. That rule makes sense for the EMA-cross
//--- overlay (which tracks one open "position" until the opposite cross
//--- closes it), but Continuation has no such position - every pullback
//--- in a sustained trend is its OWN legitimate signal, not a duplicate
//--- of the first one. So in a long one-directional trend (exactly the
//--- chart shown - one sustained downtrend, 4 separate rally-and-reject
//--- pullbacks), only the FIRST pullback could ever fire; every
//--- subsequent one in that same trend was silently suppressed forever,
//--- which is why 3 of the 4 marked points never printed even after the
//--- direction logic itself was already correct. Replaced with a
//--- per-direction bar-count cooldown (InpContCooldownBars, default 8) -
//--- repeat same-direction signals can fire again once that many bars
//--- have passed, instead of never again until the opposite direction
//--- interrupts it.
//--- 2.06: Three fixes, per direct request/screenshot.
//--- (1) Every overlay's entry arrow is now the SAME shape
//--- (OBJ_ARROW_UP/DOWN, triangle) - only the Rejection/Rejection M15
//--- overlays were still using a different Wingdings "flag" icon from
//--- v2.02; now all five entry overlays (EMA Cross, Stoch, Engulfing,
//--- Rejection, Rejection M15, Continuation) share one shape, differing
//--- only by colour and tooltip label, per: "the arrows for all signals
//--- must be the same all just different labels and colours."
//--- (2) FIXED a real direction bug in the Continuation overlay (v2.04) -
//--- found by checking it against the user's own annotated chart
//--- (downtrend, price rallying up to the 21/50EMA at each circled point,
//--- then rolling back over - exactly the pattern that should have
//--- fired and didn't). The construction had uptrend+stochCrossDOWN+
//--- reachedOVERBOUGHT firing BUY (a top, not a pullback) and downtrend+
//--- stochCrossUP+reachedOVERSOLD firing SELL (a bottom, not a rally-
//--- rejection) - backwards. Corrected: uptrend (dip to the MA, stoch
//--- toward oversold, crosses UP as the uptrend resumes) -> BUY;
//--- downtrend (rally to the MA, stoch toward overbought, crosses DOWN
//--- as the downtrend resumes) -> SELL - this now matches the chart.
//--- Re-tested with the corrected logic (research/meridian_vwap200/
//--- trend_continuation_stoch_reset_test.py): still does NOT beat
//--- random - in fact worse than most random draws now (p=0.96 M5 /
//--- p=0.84 M15, overall %PF 0.78 M5 / 0.84 M15). Remains UNVALIDATED,
//--- shown as a visual aid only, same as before - now at least firing
//--- at the pattern it was meant to describe.
//--- (3) Fixed a real regression the v2.05 fix itself introduced: on a
//--- terminal that delivers BOTH a full OnInit reinit AND a separate
//--- CHARTEVENT_CHART_CHANGE event for the same timeframe switch, the
//--- v2.05 backstop would redo the whole expensive MA/VWAP rebuild a
//--- second time back-to-back with OnInit's own version - reported as
//--- "even the panel window takes long to show" after flipping
//--- timeframes. Added g_lastFullResyncMs, a 2-second debounce set at
//--- the end of every full resync and checked at the top of the
//--- CHARTEVENT_CHART_CHANGE handler - if OnInit already did the work
//--- for this switch within the last 2s, the backstop now just rebuilds
//--- the panel (cheap) instead of redoing the heavy MA/VWAP work.
//--- 2.05: Robustness fix, per direct request ("when i flip between the
//--- 15min and the 5min the moving averages must show correct for each
//--- time frame, otherwise we need different tradepanels for each
//--- timeframe"). Confirmed the normal path (MT5's automatic full
//--- OnDeinit/OnInit reinit on a timeframe switch) already works
//--- correctly - the few seconds of delay seen after flipping is just
//--- BackfillOverlayLines() walking InpMAHistoryBars (2500) bars to
//--- redraw the whole MA/VWAP history fresh, not a bug. BUT found a real
//--- latent gap: the CHARTEVENT_CHART_CHANGE backstop (for terminals/
//--- builds that don't do the automatic full reinit) only resynced the
//--- signal overlays - the 3 MA handles + the cross-alert ATR handle
//--- (created once in SetupMAs(), fixed to whatever PERIOD_CURRENT was
//--- AT THAT TIME - VWAP has no handle, it reads PERIOD_CURRENT prices
//--- directly every call, so it was already timeframe-correct) and every
//--- hand-drawn MA/VWAP line were never touched there, so on a terminal
//--- relying on that fallback path, the MAs would silently keep showing
//--- the OLD timeframe's values forever after a period switch (VWAP's
//--- own lines would still go stale too, since nothing wiped them).
//--- Fixed: that handler now releases/recreates the 4 handles, wipes
//--- every stale MA/VWAP line, redraws the whole history, and resets
//--- g_lastBarTime - most of the same work OnInit does on a full reinit
//--- (not byte-identical - this runs after the panel already exists and
//--- doesn't touch every OnInit-only step - but functionally equivalent
//--- for what this gap needed), now reachable from the fallback path too.
//--- (Opus-reviewed: confirmed no double-release/ordering bug, flagged
//--- the g_lastBarTime gap and this wording, both fixed here.)
//--- 2.04: New "Continuation" overlay, per direct request - "signals for
//--- trend continuation, example where price is overbought and the
//--- stochastic crosses to go back to oversold near the moving
//--- averages" - buy the pullback while an uptrend continues: trend
//--- (21>50) + price near EITHER the 21 or the 50EMA (not just the 21 -
//--- "should price actually test the 50ema and not just the 21ema") +
//--- stochastic reset from the OPPOSITE extreme (reached overbought then
//--- crossed back down) within a lookback window. Mirror for downtrend/
//--- sell. Tested (research/meridian_vwap200/trend_continuation_stoch_
//--- reset_test.py): net loser on both GOLD M5/M15, p=0.52-0.53 vs
//--- random timing on both - does NOT beat random. Shown anyway,
//--- UNVALIDATED, as a visual aid per direct request ("i still need
//--- signals at those points... so i could also place a trade there if
//--- i know the trend is going to continue") - same precedent as every
//--- other UNVALIDATED overlay already in this panel.
//--- 2.03: Two fixes to the Rejection overlay, per direct request. (1)
//--- SL (N-bar swing high/low, InpRejSwingBars) and TP (R:R example,
//--- InpRejRR) lines added - it only drew the arrow before, every other
//--- overlay in this file already had these. (2) A SEPARATE M15 version
//--- of the Rejection overlay (InpShowRejectSignalsM15, own colours
//--- InpRejM15BuyCol/SellCol, tooltip "Rejection M15 Buy/Sell") that
//--- always reads M15 bars directly (CopyRates with PERIOD_M15, not
//--- PERIOD_CURRENT) - this now shows ALONGSIDE the chart-timeframe
//--- Rejection overlay even when the chart/panel itself is attached to
//--- M5 (or anything else), per: "maybe the 15min should have its own
//--- separate signals, because this setup could happen on the 15min as
//--- well, maybe labelled different and different colour signals." Both
//--- Rejection overlays remain UNVALIDATED (not yet back-tested).
//--- 2.02: Per direct request, put back the Stochastic cross overlay and
//--- the Candlestick engulfing overlay (both removed in v2.0), with
//--- shorter chart-object tooltips across the board ("EMA Cross Buy/Sell",
//--- "Stoch Buy/Sell", "Engulfing Buy/Sell", "Rejection Buy/Sell" - not
//--- the old long validation-status strings). Stochastic overlay is now
//--- fully configurable (InpStochKPeriod/Slowing/DPeriod, a Simple/
//--- Smoothed method switch, a High-Low/Close-Close price-mode switch),
//--- default 14/5/5 Simple High-Low, default zone levels 15/85 (was
//--- 20/80). Added a brand-new "Rejection" overlay, per direct request
//--- and the attached chart screenshot: in a downtrend (21EMA below
//--- 50EMA), price rallying up to reach/reject/break the 50EMA, THEN
//--- breaking back below the 21EMA, closing below the Bollinger mid-band,
//--- WITH a same-direction stochastic %K/%D cross nearby - all required
//--- together, mirrored for the buy case. This construction has NOT been
//--- back-tested yet (flagged UNVALIDATED in its own input-group comment
//--- and every tooltip) - it is coded exactly as described, not assumed
//--- to be a real edge. Works on whatever timeframe the chart is attached
//--- to (M5, M15, or any other) since every overlay here reads
//--- PERIOD_CURRENT, not a hardcoded timeframe.
//--- 2.01: Added InpEmaConfirmBars (default 2) - after the user asked "is
//--- there a way to tell a good cross from a small criss-cross start of a
//--- sideways market", an Opus audit confirmed the EMA21/50 overlay had
//--- ZERO chop filtering (fired on any sign flip, however small). Tested
//--- two candidate filters first (research/meridian_vwap200/
//--- ema21_50_gap_confirm_filter_test.py, 22 configs on GOLD M15 full
//--- history): a minimum-gap-vs-ATR threshold COLLAPSES the trade count to
//--- near zero (or exactly zero above 0.5x ATR) on Gold, so it was
//--- rejected outright; a confirmation-bars delay (wait N bars after the
//--- cross, require price still past EMA50 before entering) gave a small
//--- but walk-forward-STABLE improvement on longs (PF 0.920->0.927 in
//--- 2014-2020, 1.134->1.167 in 2021+), so that's the one implemented.
//--- This is a real but modest improvement, not a general chop solution -
//--- it only screens out immediate one-bar fakeout reversals, not a
//--- genuinely choppy multi-day range. The user's other ideas (cross
//--- angle/steepness, EMAs running parallel before crossing, distance to
//--- the 200EMA/VWAP) are NOT yet implemented - still need the same
//--- honest walk-forward test before going in; flagged to the user as a
//--- separate follow-up, not silently skipped.
//--- 2.00: MAJOR SIMPLIFICATION, per direct request ("remove the stochastic
//--- and engulfing and other completely from tradepanel ea, lets only keep
//--- the buy and sell signals with the crossing of the moving average...").
//--- Completely REMOVED (not just disabled) every signal overlay except the
//--- EMA21/50 crossover: the baseline stochastic overlay, the Trend-Aligned
//--- Stochastic overlay, the candlestick engulfing overlay, and the three
//--- EXPERIMENTAL marker overlays (stack/reject/snapback) plus the separate
//--- midline-cross overlay. That means every function, input group and
//--- global-variable block tied to any of those is gone from the file, not
//--- left in place and switched off - 28 functions, 7 input groups, ~15
//--- global blocks removed in total. The only signal overlay left on the
//--- chart is now EMA21/50 crossover: entry arrow in the direction of the
//--- cross, SL line, TP/RR line, and an exit dot on the next opposite cross.
//--- Added a brand-new "trend weakening" warning marker, per direct request
//--- ("i want a signal printed when...the 21 and 50 pull closer towards
//--- each other...of the 21ema start to loose its angle"): while a position
//--- from an EMA cross is open, the 21/50 gap is tracked bar by bar: if the
//--- gap stops widening and narrows for InpEmaWeakenConfirmBars (default 2)
//--- consecutive bars, a gold diamond-dot marker fires once per open run,
//--- with its own push alert (InpEmaWeakenAlert). This is NOT an exit signal
//--- - just an early caution that the trend may be losing momentum, printed
//--- before the actual opposite cross would occur. MA/VWAP display, the
//--- MA21/50 cross-proximity alert, and the full manual trade panel (buttons,
//--- lot sizing, SL/TP editing, position management) are all untouched.
//--- 1.58: REVERTED the v1.49-1.56 native-ChartIndicatorAdd approach for
//--- MAs/VWAP back to hand-drawn OBJ_TREND segments - per direct request
//--- ("check the aurelius ea, those moving averages and vwap are built
//--- in and it goes way back"). Checked Aurelius_EA.mq5's actual code:
//--- it explicitly REJECTED ChartIndicatorAdd for the exact reason this
//--- project hit (an EA can't recolor a native indicator once added),
//--- and instead uses this same hand-drawn DrawMASegment/PurgeOldMALines
//--- idiom with InpMAHistoryBars=2500 - running LIVE in production with
//--- 5 MAs (up to 12,500 objects) with no reported hang. TradePanel's
//--- earlier "7500 objects caused a hang" conclusion (pre-1.38) was
//--- wrong, or at least not the whole story - this reverts MAs/VWAP to
//--- that exact proven pattern, with InpMAHistoryBars/InpVwapHistoryBars
//--- matching Aurelius's own defaults (2500/400) and InpColVWAP restored
//--- as a plain EA input again. ColoredMA.mq5/SessionVWAP.mq5 (the
//--- custom-indicator files from 1.50/1.56) are no longer required by
//--- this EA - SetupVWAP(), AddNativeIndicatorOnce()/
//--- RemoveNativeIndicatorByName(), and the g_maDisplayHandle*/g_vwapHandle/
//--- g_maName*/g_vwapName globals were all removed as dead code. The
//--- Opus-audit fixes from 1.53/1.54 that were NOT specific to the
//--- native-indicator approach (the iTime()==0 guard in CheckNewBar, the
//--- EMA21-reject cooldown, the closeNLbl dedup) are untouched - those
//--- were real fixes independent of this revert.
//--- 1.57: per direct request, the chart should by default show EXACTLY
//--- three signal overlays - EMA21/50 crossover, candlestick engulfing,
//--- and Trend-Aligned Stochastic - and nothing else. Default-disabled:
//--- InpShowStackSignals, InpShowRejectSignals, InpShowSnapbackSignals
//--- (the three EXPERIMENTAL markers, v1.48) and InpShowMidlineSignals
//--- (the separate midline-cross overlay, backtested net loser). The
//--- original baseline stochastic overlay (InpShowStochSignals) was
//--- already turned off by default in 1.55. None of these overlays were
//--- removed from the file - every one can still be switched back on
//--- individually from the Inputs dialog for comparison.
//--- 1.56: MA colors actually work now, per direct request ("can we set
//--- the colours of the moving averages and the vwap?" - the MAs were
//--- all showing red since 1.50 because the built-in iMA indicator can
//--- never be recolored by an EA, a limitation that was documented but
//--- apparently not obvious enough from the chart alone). New companion
//--- file ColoredMA.mq5 (ships alongside this EA - compile it into your
//--- Indicators folder, same as SessionVWAP.mq5) is a generic colored/
//--- width-configurable MA supporting all 4 standard MT5 methods
//--- (SMA/EMA/SMMA/LWMA); the EA now adds THREE separate instances of
//--- it (21/50/200) via iCustom(), each with its own InpCol21/50/200 +
//--- new InpMALineWidth passed straight through as that instance's own
//--- parameters - real color/width control, same mechanism VWAP already
//--- had. The original g_maHandle21/50/200 built-in iMA handles are kept
//--- separately, used ONLY for the cross-proximity alert's CopyBuffer
//--- reads (that calc doesn't care about color, no reason to duplicate
//--- ColoredMA's own calc a second time just to read values back out).
//--- Defaults per direct request: 21=yellow, 50=WHITE (was orange),
//--- 200=purple, VWAP=aqua (unchanged, already was).
//--- 1.55: InpShowStochSignals default changed to FALSE, per direct
//--- request after a live chart showed the baseline stochastic overlay
//--- firing BUY arrows straight into a clean, established downtrend -
//--- NOT a bug: that overlay has never had any trend filter, by design
//--- (its own rule is only ever the %K/%D zone-cross, never price vs
//--- EMA). The new Trend-Aligned Stochastic overlay
//--- (InpShowTrendStochSignals, lime/red) exists specifically to only
//--- fire in the direction the trend already agrees with - that one
//--- stays default ON. Turn InpShowStochSignals back on only if you
//--- specifically want the two constructions side by side again.
//--- 1.54: cooldown added to the EMA21-reject overlay (InpRejCooldownBars,
//--- default 5 bars) - the single biggest contributor to the ~5,300 live
//--- chart objects the Opus audit found on M1 with every overlay on
//--- (~1,900 of them, from firing on EVERY bar that touches EMA21,
//--- including every bar of a choppy multi-bar consolidation right on
//--- the line). Now only fires once per approach per direction, same
//--- cooldown idiom used elsewhere in this file. Set InpRejCooldownBars=0
//--- to go back to the original every-touch behavior.
//--- 1.53: fixes from an Opus hang-risk audit (requested after all the
//--- signal overlays were added, per direct request to "get opus to
//--- check these, i dont want the chart hanging"). Verdict: no active
//--- hang bug found, but worth being precise about the numbers - M1
//--- with every overlay on at default settings holds ~5,300 live chart
//--- objects (same order of magnitude as the ~7,500 that caused the
//--- ORIGINAL documented hang pre-1.38; M5/M15 are comfortable at
//--- ~1,050/~340). The EMA21-reject marker alone accounts for ~1,900 of
//--- that on M1 (fires on ~28% of M1 candles) - turn it off or lower
//--- InpSigDrawDays if running M1 with everything on.
//--- Two real (bounded, non-hanging) bugs fixed:
//--- (a) CheckNewBar() now refuses to treat iTime()==0 (a brief
//--- reconnect/history-sync hiccup) as a new bar - previously this could
//--- reset g_lastBarTime and make every live Compute*Signals(false) call
//--- replay its full ~500-bar window on the next tick, re-firing every
//--- alert already seen and potentially corrupting open-position state.
//--- (b) AddNativeIndicatorOnce()/RemoveNativeIndicatorByName() replace
//--- the original handle-matching duplicate-guard for the native MA/VWAP
//--- indicators (1.50) - the old approach could match the WRONG
//--- indicator instance (ChartIndicatorGet(name) only ever returns the
//--- FIRST indicator with a given short name), e.g. after manually
//--- recoloring an MA or SessionVWAP from the chart's own indicator
//--- properties, which risked a duplicate MA/VWAP accumulating on every
//--- timeframe switch/reattach. Now remembers the exact chart-indicator
//--- name this EA itself created and only ever looks for that.
//--- Also fixed: a copy/paste duplicate "closeNLbl" label creation that
//--- quietly added an extra 18px gap to the panel's height.
//--- 1.52: %K/%D cross-PROXIMITY push alert, per direct request ("send
//--- the notification before they cross") - new CheckStochCrossProximity(),
//--- same reset-on-divergence/cooldown pattern as the existing 21/50 MA
//--- proximity alert, called once per live bar from BOTH the baseline
//--- stochastic overlay AND the Trend-Aligned Stochastic overlay, each
//--- with its own latch/cooldown state so they never interfere. Fires
//--- while %K/%D are converging and within InpStochProximityPts of each
//--- other - BEFORE the cross confirms, distinct from the existing
//--- zone-entry alert (CheckStochZoneAlert, which fires on %K reaching
//--- 20/80, not on the cross itself) and the "signal printed" alerts
//--- added in 1.51 (which fire AFTER the cross is confirmed).
//--- 1.51: push notifications added for the four new overlays from this
//--- session (EMA21/50 crossover, candlestick engulfing, the three
//--- EXPERIMENTAL markers, and the new Trend-Aligned Stochastic) - same
//--- FireSigAlert() mechanism already used by the baseline stochastic
//--- overlay, each gated by its own input (InpEmaCrossAlert, InpCdlAlert,
//--- InpExpAlert, InpTSAlert). InpExpAlert defaults FALSE (the reject
//--- condition fires often, per the live chart already seen tonight -
//--- turn it on deliberately); everything else defaults true, matching
//--- the baseline overlay's own convention. Candlestick overlay only
//--- alerts on entry (no opposite-signal exit exists for it to wait on).
//--- 1.50: MAs and VWAP switched from hand-drawn OBJ_TREND segments to
//--- NATIVE chart indicators, per direct request ("need them to go back
//--- longer" + "can you not set the EA to add the relevant moving
//--- averages to the chart"). A native indicator (ChartIndicatorAdd)
//--- plots over the WHOLE chart history automatically with ZERO extra
//--- chart objects and no hang risk - the hand-drawn approach was always
//--- bounded by InpMAHistoryBars/InpVwapHistoryBars (object-count risk,
//--- see that input's own comment). MT5 won't let an EA recolor a
//--- built-in indicator once added, so the 21/50/200 MAs now show in
//--- MT5's own default colors (recolor manually from the chart's
//--- indicator list if you want the old yellow/orange/purple scheme).
//--- VWAP has no built-in MT5 equivalent, so a new companion file,
//--- SessionVWAP.mq5 (ships alongside this EA - compile it into your
//--- Indicators folder), implements the exact same session-VWAP
//--- construction as before as a proper custom indicator - and because
//--- it's OUR OWN indicator, it DOES keep full color/width control via
//--- its own InpVWAPColor/InpVWAPWidth inputs (set inside SessionVWAP's
//--- own Properties dialog, not this EA's). The 21/50/200 MAs have NO
//--- line-thickness input any more than color - that's a genuine MT5
//--- limitation on built-in indicators, recolor/re-width them manually
//--- from the chart's indicator list if you want something other than
//--- MT5's own defaults.
//--- InpMAHistoryBars/InpVwapHistoryBars raised to 2000/1000 bars as a
//--- reasonable default even though they're no longer load-bearing for
//--- the native indicators (kept for symmetry/possible future use).
//--- 1.49: NEW Trend-Aligned Stochastic overlay, per direct request - a
//--- fourth distinct signal overlay (alongside the EMA21/50 crossover and
//--- candlestick engulfing overlays from v1.47, each with their own colors
//--- and exit logic, as asked for explicitly). Own full settings
//--- (InpTSKPeriod/Slowing/DPeriod/StochMethod, InpTSEmaFast/Slow/Method),
//--- so it can be tuned independently from the baseline stochastic overlay.
//--- Rule: a %K/%D cross (ANY level, no zone restriction) only fires when
//--- it matches the trend the 2-EMA alignment already shows - BUY only
//--- when close>EMA_fast>EMA_slow and the cross is up; SELL only when
//--- close<EMA_fast<EMA_slow and the cross is down (exact mirror, per
//--- direct request - "obviously vice versa for the sell"). A disagreeing
//--- cross is simply ignored, never flipped into an opposite signal.
//--- UNVALIDATED - the two closest relatives (price-vs-EMA21 alone, and
//--- EMA21-reject alone) were tested as FILTERS on the zone-cross
//--- stochastic earlier tonight and both failed (%PF=0.530 and 0.559
//--- vs baseline 0.701) - this is a different combination (2-EMA
//--- alignment, ANY cross, no zone), not yet separately checked.
//--- 1.48: THREE new EXPERIMENTAL/UNVALIDATED marker-only overlays, per
//--- direct request - "built the signals as i have described all of them
//--- i will check them on the chart". None of these passed tonight's
//--- honest random-timing/net-PF testing as standalone constructions (see
//--- each one's own research script) - they are shown anyway, clearly
//--- labeled EXPERIMENTAL/UNVALIDATED in every tooltip, purely so the
//--- live chart can be eyeballed for whether any of them line up with
//--- the stochastic overlay's real crosses in a way the blunt
//--- statistical test could have missed. Marker-only (no SL/TP lines) -
//--- all three reversible via their own input flag, nothing else changed.
//--- (a) InpShowStackSignals: fresh EMA21/50/200 stack transition
//--- (trend-following) - tested net-losing (ema_stack_pure_entry_test.py:
//--- Gold %PF=0.92, Silver 0.70, BTC 0.70).
//--- (b) InpShowRejectSignals: price's high/low touches EMA21 but the
//--- bar closes back on the same side (a rejection) - not yet separately
//--- null-tested, added purely from the chart annotation showing this.
//--- (c) InpShowSnapbackSignals: price gets InpSnapExtATR ATR away from
//--- EMA21 (fresh extension), marked in the MEAN-REVERSION direction -
//--- the only counter-trend idea on the chart, everything else here is
//--- trend-following. Not yet separately null-tested.
//--- 1.47: TWO new, fully independent signal overlays added, per direct
//--- request ("give them to me in the trade panel aswell, the entry
//--- signals with the same lines as we have now showing RR levels, and
//--- the stop loss line just below or above the cross?"), both reversible
//--- by simply flipping their own input back to false - nothing else in
//--- the file changed, the existing stochastic/midline overlays above are
//--- completely untouched.
//--- (a) EMA21/50 crossover overlay (InpShowEmaCrossSignals, default
//--- true): entry = a fresh EMA21/50 cross (own self-contained SigEMA()
//--- helper, matches InpMA21/InpMA50/InpMAMethod already in the file),
//--- held FLAT until the next opposite cross closes it (exit dot drawn
//--- then) - the exact construction validated tonight in
//--- ema21_50_pure_crossover_test.py (GOLD LONGS ONLY %PF=1.031, net
//--- +19.07%, the one profitable subset of the whole session). A faster
//--- exit on price closing back past EMA21 alone was explicitly requested
//--- and tested (ema21_50_crossover_fast_exit_test.py) - it came back
//--- WORSE on all three instruments, so this overlay deliberately does
//--- NOT offer that as an option; the SL/TP reference lines drawn on
//--- entry are visual reference only, not the validated exit.
//--- (b) Candlestick engulfing-at-extreme overlay (InpShowCandleSignals,
//--- default true): bullish/bearish engulfing where the pattern bar IS
//--- the N-bar swing extreme, no stochastic anywhere - validated on GOLD
//--- ONLY (candlestick_engulfing_null_test.py, p=0.0010); Silver/BTC are
//--- shown too for comparison but are NOT real (p=0.8511/0.5564 - see the
//--- tooltip/log text on every signal). Entry only - this construction
//--- has no opposite-signal exit, just the swing-stop/fixed-1:2RR lines,
//--- which ARE the validated exit here (unlike the EMA overlay above).
//--- 1.46: two changes to the MIDLINE-CROSS overlay, per direct request.
//--- (a) InpMidlineBandLow/High widened from 40/60 to 20/80 - the
//--- zone-cross entry overlay already owns crosses AT the 20/80
//--- extremes themselves, so this widened band now picks up essentially
//--- every OTHER cross (not just ones tight around the 50 midline).
//--- (b) New InpMidlineMarkerSize input (default 1, was hardcoded 3) -
//--- diamond marker made smaller.
//--- 1.45: REVERTED part of 1.43/1.44 - "anchor the exit dot to its own
//--- entry arrow's price" broke badly on any position that ran a real
//--- distance before exiting (normal for a trending move): the dot ended
//--- up pinned near the OLD entry price, floating in empty space far from
//--- the actual exit candle - confirmed from a live chart showing several
//--- dots stranded well above/below the real price action. Removed
//--- g_sigLastEntryPrice and the anchor-to-entry-price logic entirely for
//--- the DIFFERENT-candle case, which is now back to the exit bar's OWN
//--- candle high/low (1.42's approach - same side as the direction being
//--- closed, anchored where the exit actually happens). The SAME-candle
//--- case (1.44, kept - dot follows a same-bar entry arrow's own price)
//--- is unaffected and was never the problem.
//--- 1.44: three changes, per direct request.
//--- (a) Exit dot placement refined further: when a NEW entry arrow lands
//--- on the SAME candle as an exit, the dot now follows THAT arrow's side
//--- (buy arrow -> dot below it; sell arrow -> dot above it), regardless
//--- of which direction is being closed - this is what's actually visible
//--- together and must read cleanly.
//--- (b) New InpSigArrowSize / InpSigDotSize inputs - arrow and dot width
//--- are now user-settable instead of hardcoded (was fixed at 1 and 2
//--- since 1.41).
//--- 1.42: per direct request ("like we said with the buy signal arrow,
//--- the exit dot must be below it") - an exit dot now draws on the SAME
//--- side as the direction it's closing: EXIT-LONG (closing a BUY, which
//--- sits below) now also sits below; EXIT-SHORT (closing a SELL, which
//--- sits above) now also sits above. It was previously the opposite -
//--- which put an exit dot on the same side as the OPPOSITE-direction
//--- entry arrow, directly causing the overlap reported from two separate
//--- live chart screenshots (v1.40's price-level anti-collision was
//--- working correctly the whole time - this was a placement-RULE issue,
//--- not a collision-detection bug).
//--- 1.41: per direct request, entry arrows and exit dots made smaller
//--- (arrow width 2->1, dot width 3->2) - OBJ_ARROW_UP/DOWN were already
//--- solid filled triangles, not outlines, so "solid colour" needed no
//--- further change there. User also reports the v1.40 overlap fix isn't
//--- visibly working on a specific chart - asked to confirm the Experts
//--- log actually shows "v1.40 OnInit" (i.e. the new code is really
//--- loaded) before investigating the nudge logic itself further.
//--- 1.40: two changes, per direct request.
//--- (a) Default inputs changed: entry stoch 14/3/3 -> 21/5/5, exit stoch
//--- 14/3/3 -> 21/5/5, InpSigStochMethod SMOOTHED -> SIG_STOCH_SMA ("Simple"
//--- in MT5's own dropdown terms - plain SMA of %K and %D, not the SUM
//--- variant), InpShowMidlineSignals false -> true (its band was already
//--- 40/60 by default).
//--- (b) Fixed a reported signal-marker overlap (a buy arrow and an
//--- EXIT-SHORT dot sitting on top of each other during a tight, low-range
//--- consolidation). The old anti-collision logic ONLY handled an entry
//--- and exit landing on the exact SAME bar on the SAME side - it had no
//--- answer for two markers on nearby-but-different bars ending up close
//--- in price purely because ATR/range was small. New general
//--- NudgeAwayFromLastMarker(), applied to every entry arrow AND every
//--- exit dot: checks the most recently drawn marker of ANY kind, and if
//--- it's both close in price (< InpSigMinMarkerGapATR x ATR) and close in
//--- time (within InpSigMarkerLookbackBars bars), pushes the new one
//--- further out in its own natural direction instead of letting them
//--- overlap. Markers far apart in time are left alone even if
//--- coincidentally similar in price - not visual clutter, a coincidence.
//--- 1.39: InpSigDrawBars (1.38) replaced with InpSigDrawDays (default 7),
//--- per direct request - "limit it to 1 week". A raw bar count means a
//--- different real-world window on every timeframe (2000 bars was ~20
//--- days on M15 but only ~7 on M5); days converted to bars against
//--- PERIOD_CURRENT fixes that. Purging already ran every new bar (1.38),
//--- which is tighter than a once-a-day sweep - a day's backlog never
//--- gets the chance to build up before being dropped, so no separate
//--- "delete the last day" step was needed, just the unit change.
//--- 1.38: CHART HANG - user reported charts freezing after running a
//--- while. Live per-tick/per-bar path was checked and IS bounded
//--- (minBars+500 window, new-bar guard). The real problem was the
//--- stochastic overlay's object/log volume: backfill drew every signal
//--- across ALL loaded history (Bars()-1, often 100k+ bars at the
//--- terminal's default "Max bars in chart"), ~3-4 objects per entry plus
//--- exit dots, and NOTHING ever deleted them except a full resync - so
//--- the chart started with tens of thousands of objects and gained more
//--- every bar. Every repaint and PurgeOldSegments' per-bar OBJ_TREND scan
//--- (the SL/TP lines are OBJ_TREND too) walked all of them. The 1.36
//--- RAWCROSS line made it worse: its "a handful per day" estimate is
//--- wrong on M5 (K/D cross every few bars), so a reattach printed
//--- thousands-to-tens-of-thousands of journal lines in one go. Fix: new
//--- InpSigDrawBars (default 2000) - backfill still walks full history for
//--- correct state but only draws/logs the last N bars, and a new
//--- PurgeOldSigObjects() drops older signal objects each new bar.
//--- 1.37: new InpSigUseInterpCross input (default TRUE), per direct
//--- request - the zone qualification check now uses the INTERPOLATED
//--- point where the %K/%D line segments actually cross between bar i-1
//--- and bar i (solving for where K-D hits zero), instead of either bar's
//--- raw endpoint value. This matches "where the lines visually meet on
//--- the chart" rather than the bar-close snapshot, which a fast-moving
//--- bar can jump straight past. Does NOT change which bars count as a
//--- cross (still the same k[i-1]<=d[i-1] && k[i]>d[i] / mirror test) -
//--- only changes what value gets compared against the zone threshold.
//--- RAWCROSS diagnostic (v1.36) now also prints this interpolated value.
//--- 1.36: diagnostic only - added StochSignal RAWCROSS log line, printed
//--- for EVERY raw %K/%D cross on the entry stoch (not just ones that
//--- qualify and draw an arrow), showing K/D values, the zone thresholds
//--- actually in effect, and whether it qualified. Confirmed zone/method
//--- inputs ARE correctly wired (30.0/70.0/Smoothed all verified in the
//--- Inputs dialog) and the Experts log showed NO entry fired for a bar
//--- the user's chart clearly showed crossing under 30 - but the old
//--- logging only ever printed QUALIFYING entries, so there was no way to
//--- see the actual K/D the code computed for the disputed bar, only
//--- neighboring bars. This closes that visibility gap for next time.
//--- 1.35: REAL BUG - the ENTRY block set posDir to the NEW direction
//--- before the EXIT block (later in the same per-bar loop) read posDir to
//--- decide whether/which-side to fire an exit. On a bar where both an
//--- opposite-direction entry AND an exit-stoch cross against the OLD
//--- position happened together, the exit check was already looking at the
//--- freshly-flipped posDir and silently never fired - exactly the
//--- symptom the user screenshotted (a sell cross that should have shown
//--- both a new SELL arrow and an EXIT-LONG dot only showed the arrow).
//--- Same root cause also let a fresh entry from flat get spuriously
//--- "exited" on its own entry bar, wiping its own lastArr/Sl/Tp. Fixed by
//--- snapshotting posDir into prevPosDir BEFORE the entry block can change
//--- it, and having the entire exit block (fire condition, alert text,
//--- wasLong label, log line) read prevPosDir instead. The flat/clear
//--- cleanup (posDir=0, lastArr/Sl/Tp="") now only runs when no entry also
//--- fired this bar - if one did, posDir/lastArr/Sl/Tp already correctly
//--- belong to that new entry and must not be wiped. Found, confirmed, and
//--- fixed by an independent Opus audit; diff reviewed and verified
//--- (brace/paren balance) before committing.
//--- 1.34: ROOT CAUSE FOUND for the real/overlay cross-detection dispute -
//--- a screenshot of the user's own native MT5 Stochastic Properties dialog
//--- showed Method: Smoothed, not Simple. Both v1.33 options
//--- (InpSigUseSumSlowing true/false, now replaced) were SMA-family only -
//--- neither could ever have matched Smoothed (SMMA), a different recursive
//--- formula, which is exactly why toggling it produced "nothing changed."
//--- Replaced InpSigUseSumSlowing with a 3-way InpSigStochMethod
//--- (SUM / SMA / SMOOTHED), default SMOOTHED to match the confirmed real
//--- setting, and implemented proper SMMA math for both the %K slowing
//--- step and the %D line (MT5 applies the same Method to both).
//--- 1.33: added InpSigUseSumSlowing (default true = unchanged behavior).
//--- After repeated real, non-sub-pixel disagreement between this overlay
//--- and the user's own same-settings (21,5,5, Low/High, SMA) native MT5
//--- indicator, and two code audits finding no indexing/alignment bug,
//--- the remaining open question is whether MT5's actual compiled
//--- Stochastic really uses "sum numerator/denominator separately over
//--- the slowing window, then divide" (this project's working assumption,
//--- from documented MT5 behavior/the shipped example source - what
//--- InpSigUseSumSlowing=true does, unchanged) or the more common
//--- "textbook" convention of a plain SMA of the raw per-bar %K over the
//--- slowing window (InpSigUseSumSlowing=false, NEW). Both are now
//--- implemented and switchable so this can be settled empirically by
//--- comparing against the real native indicator, instead of asserted
//--- from memory again.
//--- 1.32: diagnostic only - OnInit now prints the ENTRY/EXIT stochastic
//--- settings it actually initialized with (and the show-exit/show-midline
//--- toggles) to the Experts log, so "did my changed input actually take
//--- effect" can be checked directly instead of trusting the Properties
//--- dialog. Confirmed in code: both SigClassicStoch() calls already used
//--- InpSigKPeriod/Slowing/DPeriod and InpExitKPeriod/Slowing/DPeriod (not
//--- hardcoded numbers) - this doesn't change that, it just makes it
//--- provable from the log.
//--- 1.31: diagnostic only - the entry/exit StochSignal LOG lines now print
//--- the full K[i-1]/D[i-1]/K[i]/D[i] (3 decimals) instead of just K, so a
//--- "did this actually cross" dispute can be settled against your own
//--- same-settings native indicator's Data Window values bar-by-bar,
//--- instead of eyeballing the chart. No logic changed - an Opus audit
//--- (prompted by a confirmed visual non-cross on the user's own 21,5,5
//--- native indicator at a bar where a SELL arrow was drawn) checked the
//--- cross-detection indexing, the live-window-vs-backfill bar alignment,
//--- and SigClassicStoch's own internal loop bounds for 21/5/5 - all
//--- correct, no bug found. Likely explanation: a sub-pixel (K/D differ by
//--- hundredths) cross that both the EA and the native indicator would
//--- agree on numerically but can't be seen by eye even zoomed in - this
//--- logging change is how to actually confirm that next time, rather
//--- than guess again.
//--- 1.30: new EXPERIMENTAL midline-cross signal overlay (off by default -
//--- InpShowMidlineSignals), per direct request: a cross back through the
//--- 50 midline (not a deep 20/80 zone extreme) after a genuine pullback
//--- (InpMidlineBandLow/High, InpMidlinePriorLookback). Drawn as a diamond
//--- marker (own colors InpMidlineBuyCol/SellCol, own offset
//--- InpMidlineOffsetATR) so it's never visually confused with the
//--- existing arrows/dots. Fully independent - does not touch posDir,
//--- lastDir, or the entry/exit overlay's state in any way, purely
//--- additive. Backtested separately (research/meridian_vwap200/
//--- classic_stoch_21_5_5_btc_h1_midline_entry_test.py): full-history
//--- %PF~0.65, still a net loser - shown for visual reference only.
//--- 1.29: FIX real bug - orphaned exit dots. The "repeat same-direction
//--- cross REPLACES the previous signal" rule deleted the previous arrow
//--- (and its SL/TP) whenever the new entry matched lastDir - even when
//--- that previous entry had ALREADY been closed by an exit dot in
//--- between. Sequence: BUY arrow -> SELL arrow -> EXIT-SHORT dot (posDir
//--- correctly -1 -> 0) -> another SELL cross: dir==lastDir, so the first
//--- SELL arrow was deleted, leaving BUY arrow -> magenta dot with no sell
//--- arrow visible between them. posDir itself was never wrong; the
//--- arrow that explained it was erased. An exit now clears lastArr/
//--- lastSl/lastTp, so only a still-OPEN same-direction signal is ever
//--- replaced.
//--- 1.28: FIX a real bug introduced by 1.27's performance fix: a LIVE
//--- call always assumed exactly ONE new bar had closed since the last
//--- check (from = n-1). During a stall/hang (or any gap in the EA
//--- actually running), several bars can close before the next check -
//--- any entry/exit inside that gap was silently skipped, leaving
//--- g_sigPosDir stuck on a stale value (e.g. still "long" after a real
//--- live SELL arrow printed), so the exit overlay later closed the
//--- WRONG, invisible position - wrong color, wrong side. Now tracks
//--- g_sigLastProcessedBar and catches up on every bar since, not just
//--- the newest one (bounded to a 500-bar trailing window - still far
//--- short of the whole history, but enough for any realistic gap).
//--- Also added: every entry/exit now prints an unconditional ground-
//--- truth line to the Experts log (both backfill and live, regardless
//--- of the push-alert inputs) - "StochSignal LOG: ..." - so the exact
//--- recognized sequence can be checked directly against what the chart
//--- shows, instead of guessing from a screenshot.
//--- 1.27: FIX real performance bug - "charts hanging". A LIVE call to
//--- ComputeStochSignals() (every new bar, and polled every 2s since
//--- 1.25) was re-copying (CopyRates) and re-computing the stochastic -
//--- TWICE since 1.24 added the exit one - plus a full ATR pass, over
//--- the WHOLE loaded chart history every single time, purely to replay
//--- lastDir/posDir state from scratch. On a full-history low-timeframe
//--- chart (hundreds of thousands of bars) that is real, repeated, heavy
//--- work on the UI thread every time a bar closes. A live call only
//--- ever needs the ONE newest closed bar, so it now copies/computes a
//--- small bounded window (minBars+10) instead, and lastDir/posDir/
//--- lastArr/lastSl/lastTp are persisted across live calls in
//--- g_sigLastDir/g_sigPosDir/g_sigLastArr/g_sigLastSl/g_sigLastTp
//--- (reset to a safe default in ResyncStochSignals(), always correctly
//--- rewritten by the next backfill or live call) instead of being
//--- rebuilt by re-walking the whole history every time. Backfill (on
//--- attach / timeframe switch, runs once) is unchanged - it still needs
//--- the full history, just no longer on every bar close.
//--- 1.26: FIX real bug - a zone-qualified entry cross with no sane stop
//--- (risk<=0.0, close sitting exactly on the swing extreme) still
//--- silently flipped lastDir/posDir even though NO arrow was ever drawn
//--- for it. The exit overlay (added in 1.24) watches posDir, so this
//--- produced a confusing wrong-color/wrong-side exit dot later, closing
//--- a "position" that was never visibly shown opening - exactly the
//--- symptom reported on a live chart. Disqualified crosses now skip
//--- lastDir/posDir too, not just the drawing. Also: when an exit dot and
//--- a brand-new entry arrow land on the exact same bar AND the same side
//--- (e.g. a sell arrow above + an exit-long dot that would also sit
//--- above), the dot now stacks further out starting from the arrow's
//--- own price instead of overlapping it.
//--- 1.25: new-bar work (overlay lines, stoch signals/alerts, panel
//--- rebuild) is now ALSO checked from the existing 2s OnTimer, not just
//--- OnTick - a quiet/illiquid market can go well past a second between
//--- real ticks, so relying on ticks alone meant a signal that closed
//--- mid-quiet-spell could sit undrawn until the next trade printed
//--- somewhere. Factored into CheckNewBar(), called from both; a new
//--- bar is still only ever processed ONCE (g_lastBarTime guards it,
//--- same as before), and it now force-redraws right after, so a
//--- freshly-printed arrow/dot shows immediately instead of waiting on
//--- the terminal's own tick-driven paint cycle. No change to how often
//--- the full per-tick OnTick body runs, and the blanket per-timer
//--- redraw that was deliberately removed earlier for performance is
//--- still not back - only this one new-bar-only redraw was added.
//--- 1.24: (1) new independent EXIT signal overlay - solid dots, own
//--- stochastic settings (InpExitKPeriod/Slowing/DPeriod), own on/off
//--- (InpShowExitSignals), own alert (InpSigExitAlert). Fires on the exit
//--- stochastic's own %K/%D cross AGAINST the currently-shown entry
//--- direction (no zone requirement - plain "exit on opposite cross"),
//--- only while an entry arrow is "open"; (2) entry arrows and exit dots
//--- are now pushed away from the candle by InpSigArrowOffsetATR /
//--- InpSigExitOffsetATR (in ATR(14) multiples, exit further out than
//--- entry by default) instead of sitting right on the candle. Still
//--- visual/alert only - no trading/execution logic touched.
//--- 1.23: two new alert stages for the classic stoch overlay, live only
//--- (never during backfill of old history): (1) InpSigZoneAlert - an
//--- EARLY push+sound the moment %K first enters the oversold/overbought
//--- zone, BEFORE any cross is confirmed or arrow printed; (2)
//--- InpSigCrossAlert - push+sound when the actual cross-in-zone signal
//--- prints. Both use SendNotification() (needs push notifications +
//--- MetaQuotes ID set in the terminal) and PlaySound(InpSigSoundFile).
//--- Still visual/alert only - no trading/execution logic touched.
//--- 1.22: Classic stoch overlay settings (K/slowing/D period, zone levels,
//--- swing-stop bar count, R:R) are now inputs (InpSigKPeriod etc.) instead
//--- of hardcoded #defines, so they can be changed per-chart without
//--- editing code. No default values changed; no trading/execution logic
//--- touched.
//--- 1.21: when %K/%D whipsaws and re-crosses in the SAME direction before
//--- the opposite cross fires, the overlay now REPLACES the previous
//--- arrow/SL/TP with the new one instead of drawing a second one - keeps
//--- the latest/held cross of a run visible, not the earlier premature one
//--- that often goes against price first. Cosmetic only - no change to the
//--- signal rule, stop, or target, and no change to trading/execution.
//--- 1.20: overlay swapped to the CLASSIC textbook rule (single Stochastic
//--- 14,3,3 Low/High+SMA, %K/%D cross inside 80/20, swing stop, 1:2 R:R) so it
//--- can be eyeballed against the researched one. Untested - the 1.19 research
//--- construction it replaces was itself a net loser; neither is an edge.
//--- 1.19: dual-Stochastic(Close/Close, SMMA) cross-in-zone + 200EMA signal
//--- overlay with suggested stop and three tiered TPs - DRAWING ONLY, it never
//--- touches an order. Ported from research/meridian_vwap200/dual_stoch_*.py so
//--- what's on the chart is the exact construction that was backtested, not a
//--- look-alike built on MT5's native iStochastic (whose "slowing" differs).
#property strict
#property indicator_chart_window
#property indicator_plots 0

#include <Trade/Trade.mqh>

input group "=== Trade buttons ==="
input int    InpMagic              = 0;          // THIS LOCKED COPY defaults to 0 ("auto") -
                                                  // not the old fixed 20261014 - so the two locked
                                                  // copies get DIFFERENT magics automatically (derived
                                                  // from _Period, see g_effectiveMagic/OnInit), with no
                                                  // setup needed. Set non-zero only to share a magic
                                                  // with something else on purpose.
input int    InpArmSeconds         = 60;         // ARM auto-expires after this many seconds unused -
                                                  // starting value only, adjustable live from the panel
                                                  // itself now (Arm delay row) via g_armSeconds
input int    InpSlippage           = 30;
input color  InpBgColor            = C'30,30,34';
input color  InpTextColor          = clrWhite;
input color  InpArmedColor         = clrOrangeRed;
input color  InpBuyColor           = C'30,120,60';
input color  InpSellColor          = C'150,40,40';

input group "=== Moving averages (hand-drawn in the project's own colours, same idiom as Aurelius_EA.mq5) ==="
input bool          InpShowMAs     = false;  // v2.27: see main file's own comment
input ENUM_MA_METHOD InpMAMethod   = MODE_EMA;    // MODE_EMA = exponential, MODE_SMA = simple
input int            InpMA21      = 21;
input int            InpMA50      = 50;
input int            InpMA200     = 200;
input color          InpCol21     = clrYellow;
input color          InpCol50     = clrWhite;         // per direct request
input color          InpCol200    = C'191,0,255';     // neon purple
input int            InpMALineWidth = 1;
input int            InpMAHistoryBars = 2500;         // v1.58: REVERTED to hand-drawn OBJ_TREND segments
                                                       // (same DrawMASegment/PurgeOldMALines idiom as
                                                       // Aurelius_EA.mq5, not the v1.49-1.57 native-
                                                       // ChartIndicatorAdd approach) - per direct request,
                                                       // after checking Aurelius_EA.mq5's own actual code:
                                                       // it explicitly rejected ChartIndicatorAdd for
                                                       // exactly this reason ("an EA has no plot buffers,
                                                       // only an indicator can set PLOT_LINE_COLOR... could
                                                       // only show MT5's own auto-assigned colours") and
                                                       // uses this same hand-drawn approach with
                                                       // InpMAHistoryBars=2500 as its own default - running
                                                       // LIVE in production with 5 MAs (up to 12,500
                                                       // objects) with no reported hang. The "7500 objects
                                                       // caused a hang" conclusion from TradePanel's own
                                                       // earlier history was wrong, or at minimum not the
                                                       // whole story - Aurelius proves meaningfully MORE
                                                       // objects than that work fine when properly bounded
                                                       // and purged (OBJPROP_HIDDEN + PurgeOldMALines every
                                                       // new bar, exactly what this file already does).
                                                       // 2500 = ~26 days of M15 history per line, matching
                                                       // Aurelius's own proven default exactly.

input group "=== 21/50 MA cross-proximity push alert (fires on PERIOD_CURRENT - attach this panel to the same chart/timeframe as whichever strategy EA you want warned about) ==="
input bool   InpEnableCrossAlert   = true;
input double InpCrossAlertATRMult  = 0.3;    // "near" threshold: alert once the 21/50 gap closes to
                                              // within this many ATR - smaller = later/tighter warning,
                                              // larger = earlier but noisier
input int    InpCrossATRPeriod     = 14;
input int    InpCrossAlertCooldownMin = 30;  // minimum minutes between alerts for the SAME approach,
                                              // so a gap oscillating right at the threshold doesn't spam

input group "=== Session VWAP (MT5 has no built-in VWAP - hand-drawn, same construction/idiom as Aurelius_EA.mq5) ==="
input bool   InpShowVWAP           = true;
input color  InpColVWAP            = C'0,255,255';    // neon aqua - same family as the other EAs' VWAP
input int    InpVwapHistoryBars    = 400;    // v1.58: REVERTED to hand-drawn (see InpMAHistoryBars'
                                              // own comment for why) - VWAP resets every session, so a
                                              // long backfill window doesn't add anything, same reasoning
                                              // and same default Aurelius_EA.mq5 itself uses
input int    InpVwapLineWidth      = 1;

input group "=== Chart theme (same family-standard blue/white candles as the other EAs) ==="
input bool   InpApplyTheme         = true;
input color  InpChartBg            = clrBlack;
input color  InpBullCol            = C'0,150,255';    // neon blue - family standard
input color  InpBearCol            = clrWhite;        // neon white - family standard
input bool   InpShowTradeLevels     = true;   // show MT5's native open-price/SL/TP lines - the ones you
                                               // drag on the chart to set/move SL and TP. Kept ON by
                                               // default; split out from trade-history so this panel can
                                               // win the fight against a strategy EA on the same chart
                                               // that turns it off for its own solo-chart case.
input bool   InpHideTradeHistory    = true;   // hide MT5's own closed-trade arrows/labels only - applied
                                               // unconditionally (not gated behind InpApplyTheme) since
                                               // those arrows drawing through the panel is exactly what
                                               // this fixes. Independent of InpShowTradeLevels above.

input group "=== Trade condition light (green/red, same traffic-light idiom as the other EAs' panels) ==="
input int    InpMaxSpreadPoints    = 70;      // Silver-specific number from this project's own research
                                               // (research/trendbreaker/hs_silver_spread_threshold_test.py) -
                                               // change this per instrument; light goes RED when live spread exceeds this - this is
                                               // the ONLY thing the light checks (spread only, not a
                                               // trade signal of any kind - this panel has no strategy)

input group "=== Shared signal-marker settings (used by the EMA21/50 crossover overlay's markers/alerts) ==="
input int    InpSigDrawDays         = 2;      // v2.27: see main file's own comment - now genuinely
                                               // calendar-day aligned (today + yesterday)
input double InpSigMinMarkerGapATR = 1.0;     // minimum price gap (in ATR) kept between ANY two signal
                                               // markers that land close together in time
input int    InpSigMarkerLookbackBars = 5;    // only markers within this many bars of each other are
                                               // checked for the above - markers far apart in time are left
                                               // alone even if coincidentally close in price
input string InpSigSoundFile       = "alert.wav";   // must exist in the terminal's Sounds folder - leave
                                                     // blank to disable the sound (push notification still fires)

input group "=== EMA21/50 Crossover signal overlay - the ONLY construction tonight that showed a real, validated edge (Gold longs, hold-to-next-cross, %PF=1.031) - VISUAL ONLY, never places/modifies/closes anything ==="
input bool   InpShowEmaCrossSignals = true;   // per direct request - entry on EMA21/50 cross, held until
                                               // the NEXT opposite EMA21/50 cross (the exact construction
                                               // validated in research tonight - a FASTER exit on EMA21
                                               // alone was tried and tested WORSE, so this overlay does NOT
                                               // offer that as an option)
input int    InpEmaConfirmBars     = 2;       // per direct request, after research confirmed it holds up
                                               // walk-forward (longs %PF 0.920->0.927 IS, 1.134->1.167 OOS):
                                               // after a cross, wait this many bars and require price still
                                               // past EMA50 in the cross direction before the entry fires -
                                               // screens out immediate one-bar fakeout reversals. Set to 0
                                               // to go back to firing on the cross bar itself. A separate
                                               // min-gap-before-ATR filter was also tested and rejected -
                                               // on Gold it collapses the trade count to near zero (or
                                               // exactly zero above 0.5x ATR) with no edge to show for it.
input int    InpEmaCrossSwingBars  = 10;      // stop-loss reference = N-bar swing low/high at the cross bar
input double InpEmaCrossRR         = 2.0;     // R:R convention for the TP reference line - a representative
                                               // example only; the validated exit is the NEXT opposite
                                               // EMA cross, not this target - the TP line is for visual
                                               // reference/context, same as the stochastic overlay's own TP line
input color  InpEmaCrossBuyCol     = C'178,255,25';
input color  InpEmaCrossSellCol    = C'255,12,255';
input color  InpEmaCrossStopCol    = clrRed;
input color  InpEmaCrossTPCol      = clrYellow;
input double InpEmaCrossArrowOffsetATR = 1.6; // own offset so it never sits on top of the stochastic overlay's
input double InpEmaCrossExitOffsetATR  = 1.2; // own markers (independent overlay, never touches posDir/lastArr above)
input int    InpEmaCrossArrowSize  = 1;   // v2.08: standardized to match every other overlay's arrow size -
                                           // per direct request, all entry arrows same shape AND same size,
                                           // colour/label is what tells them apart (at width 1 some arrows
                                           // render small enough to look like a dot rather than a clear arrow)
input int    InpEmaCrossDotSize    = 2;
input int    InpEmaCrossLineBars   = 8;       // stop-line length in bars; the TP line runs 2 bars longer
input bool   InpEmaCrossAlert      = true;    // push notification on entry AND exit (next opposite cross)
input bool   InpShowEmaWeakenSignals = true;  // per direct request: a SEPARATE warning signal, fired
                                               // once per open EMA-cross run, when the 21/50 gap (which
                                               // widens as a healthy trend continues) stops widening and
                                               // starts pulling back together again - i.e. the 21EMA
                                               // losing its angle / momentum fading - BEFORE the actual
                                               // opposite cross that would close the position outright
input int    InpEmaWeakenConfirmBars = 2;     // consecutive bars the gap must shrink (from its run's own
                                               // peak) before this fires - 1 bar is noisy, raise if still
                                               // too trigger-happy
input color  InpEmaWeakenCol        = clrGold;
input double InpEmaWeakenOffsetATR  = 1.6;    // own offset, bigger than entry/exit so it never sits on
                                               // top of either of those markers
input int    InpEmaWeakenSize       = 2;
input bool   InpEmaWeakenAlert      = false;  // v2.16: default OFF per direct request - "only give me
                                               // notification push when the moving averages are closing
                                               // the gap and when they actually cross, no push
                                               // notifications for the other signals" - weakening is
                                               // neither of those (not a gap-closing warning, not a
                                               // cross), so it's chart-only now. Turn back on if wanted.

input group "=== Stochastic cross signal overlay (re-added by request, v2.02) - UNVALIDATED - VISUAL ONLY, never places/modifies/closes anything ==="
input bool   InpShowStochSignals   = true;
input int    InpStochKPeriod       = 14;      // %K period
input int    InpStochSlowing       = 5;       // slowing
input int    InpStochDPeriod       = 5;       // %D period
enum ENUM_SIG_STOCH_METHOD
  {
   SIG_STOCH_SUM      = 0,   // Simple - sum num/den separately over the slowing window then divide
   SIG_STOCH_SMA      = 1,   // Simple - plain SMA of the raw per-bar %K ("textbook" convention)
   SIG_STOCH_SMOOTHED = 2    // Smoothed (SMMA) - matches MT5's native Stochastic "Method: Smoothed"
  };
input ENUM_SIG_STOCH_METHOD InpStochMethod = SIG_STOCH_SMA;   // default "Simple", per direct request
enum ENUM_SIG_STOCH_PRICE
  {
   SIG_STOCH_LOWHIGH   = 0,  // High/Low (the %K range is the bar range) - default, per direct request
   SIG_STOCH_CLOSECLOSE = 1  // Close/Close (the %K range is the range of CLOSES)
  };
input ENUM_SIG_STOCH_PRICE InpStochPriceMode = SIG_STOCH_LOWHIGH;
input double InpStochZoneLow       = 15.0;    // oversold zone (buy cross must be below this) - default 15, per direct request
input double InpStochZoneHigh      = 85.0;    // overbought zone (sell cross must be above this) - default 85, per direct request
input bool   InpStochUseInterpCross = true;   // qualify using the INTERPOLATED point where the %K/%D
                                               // lines actually cross between bar i-1 and bar i, not
                                               // either bar's raw endpoint value
input int    InpStochSwingBars     = 10;      // stop-loss reference = N-bar swing low/high at the cross bar
input double InpStochRR            = 2.0;     // R:R convention for the TP reference line - example only
input color  InpStochBuyCol        = C'93,255,25';
input color  InpStochSellCol       = C'255,12,201';
input color  InpStochStopCol       = clrRed;
input color  InpStochTPCol         = C'0,255,0';
input int    InpStochArrowSize     = 1;   // v2.08: standardized - was 1 (thin enough to look like a dot)
input int    InpStochLineBars      = 8;
input double InpStochArrowOffsetATR = 1.1;
input bool   InpStochCrossAlert    = false;   // v2.16: default OFF per direct request - push notifications
                                               // now reserved for the MA gap-closing warning and the
                                               // EMA21/50 cross itself only. Chart arrows still show.

input group "=== Candlestick engulfing signal overlay (re-added by request, v2.02) - validated on GOLD ONLY (p=0.0010) - Silver/BTC NOT real (p=0.8511/0.5564) - VISUAL ONLY ==="
input bool   InpShowCandleSignals  = true;
input int    InpCdlSwingBars       = 10;      // swing/stop-loss lookback, same N used for the pattern's own
                                               // "is this bar the swing extreme" qualification
input double InpCdlRR              = 2.0;     // fixed 1:2 R:R target - this IS the validated exit (plus the
                                               // swing stop), there is no opposite-pattern exit to wait for
input color  InpCdlBuyCol          = C'25,255,42';
input color  InpCdlSellCol         = C'255,12,147';
input color  InpCdlStopCol         = clrRed;
input color  InpCdlTPCol           = clrYellow;
input double InpCdlArrowOffsetATR  = 1.6;
input int    InpCdlArrowSize       = 1;   // v2.08: standardized - was 1 (thin enough to look like a dot)
input int    InpCdlLineBars        = 8;
input bool   InpCdlAlert           = false;   // v2.16: default OFF per direct request - see InpStochCrossAlert's own comment
input bool   InpCdlRequireTrend    = true;    // v2.18 FIX: extra confirmation, per direct request - a
                                               // bullish engulfing only counts in an uptrend (21EMA>50EMA),
                                               // bearish only in a downtrend - filters out the "wrong side
                                               // of the trend" case described
input double InpCdlMinMADistATR    = 0.5;     // v2.18 FIX: the engulfing candle's close must sit at least
                                               // this many ATR away from BOTH the 21 and 50EMA - filters out
                                               // the "too close to a moving average" case described (that MA
                                               // is right there acting as support/resistance). 0 = disabled

input group "=== Stochastic divergence signal overlay (NEW, v2.17, per direct request) - UNVALIDATED - VISUAL ONLY ==="
input bool   InpShowDivSignals     = true;    // REGULAR divergence (price makes a new high/low that the
                                               // stochastic does NOT confirm - reversal signal) and HIDDEN
                                               // divergence (price pulls back less than the stochastic
                                               // does, in an existing trend - continuation signal), both
                                               // bullish and bearish. See each colour input below for which
                                               // is which.
input int    InpDivPivotWindow     = 5;       // confirmed-swing fractal window (bars closed on each side) -
                                               // same idea as InpRejSwingBars' own window, just applied to
                                               // finding the price pivots divergence is measured between
input int    InpDivMaxPivotGapBars = 60;      // the two swing points being compared can't be more than this
                                               // many bars apart - otherwise it's comparing pivots from
                                               // different market regimes, not a real divergence
input int    InpDivSwingBars       = 10;      // SL reference = N-bar swing low/high at the trigger bar
input double InpDivRR              = 2.0;     // R:R convention for the TP reference line - example only
input color  InpDivRegBuyCol       = C'25,212,255'; // REGULAR bullish divergence (price lower low, stoch
                                                    // higher low) - reversal buy
input color  InpDivRegSellCol      = C'255,39,12';    // REGULAR bearish divergence (price higher high, stoch
                                                    // lower high) - reversal sell
input color  InpDivHidBuyCol       = C'25,127,255';        // HIDDEN bullish divergence (price higher low, stoch
                                                       // lower low, in an uptrend) - continuation buy
input color  InpDivHidSellCol      = C'255,93,12';    // HIDDEN bearish divergence (price lower high, stoch
                                                       // higher high, in a downtrend) - continuation sell
input color  InpDivStopCol         = clrRed;
input color  InpDivTPCol           = C'0,255,0';
input int    InpDivArrowSize       = 1;
input double InpDivArrowOffsetATR  = 1.9;
input int    InpDivLineBars        = 8;
input bool   InpDivAlert           = false;   // default OFF, same convention as every other non-MA overlay
                                               // since v2.16/2.17 - see InpStochCrossAlert's own comment
input int    InpDivCooldownBars    = 8;       // minimum bars between two signals of the SAME kind (regular
                                               // bullish / regular bearish / hidden bullish / hidden
                                               // bearish) - same per-direction-cooldown idea as
                                               // InpContCooldownBars, for the same reason: divergence has
                                               // no "open position" concept, so repeat signals are expected
                                               // and should fire, just not on every single consecutive bar

input group "=== Bollinger outer-band rejection signal overlay (NEW, v2.18, per direct request) - UNVALIDATED - VISUAL ONLY ==="
input bool   InpShowBBSignals      = true;    // per attached chart examples: price closes BEYOND an outer
                                               // Bollinger band (an overextended move), then a later bar
                                               // closes back INSIDE the bands - signals the overextension is
                                               // failing. SELL when price re-enters from above the upper
                                               // band, BUY when it re-enters from below the lower band -
                                               // sometimes with a rejection candle on the re-entry bar, not
                                               // required to fire
input int    InpBBPeriod           = 20;      // Bollinger period (own settings - independent of the
                                               // Rejection overlay's own InpRejBBPeriod mid-band-only usage)
input double InpBBDev              = 2.0;     // Bollinger deviations
input int    InpBBReentryLookback  = 3;       // the "closed beyond" bar and the "closed back inside" bar
                                               // don't have to be adjacent - this is how many bars back to
                                               // look for the most recent close-beyond-the-band bar
input bool   InpBBRequireRejection = false;   // OFF by default (per direct request - "sometimes with a nice
                                               // rejection candle", i.e. not every valid setup has one) -
                                               // turn on to additionally require the re-entry bar to close
                                               // in the signal's direction with a wick on the band side at
                                               // least InpBBRejectionWickRatio of the candle's own range
input double InpBBRejectionWickRatio = 0.35;  // only used when InpBBRequireRejection is on
input int    InpBBSwingBars        = 10;      // SL reference = N-bar swing low/high at the trigger bar
input double InpBBRR               = 2.0;     // R:R convention for the TP reference line - example only
input color  InpBBBuyCol           = C'25,42,255';
input color  InpBBSellCol          = C'255,147,12';
input color  InpBBStopCol          = clrRed;
input color  InpBBTPCol            = C'0,255,0';
input int    InpBBArrowSize        = 1;
input double InpBBArrowOffsetATR   = 1.9;
input int    InpBBLineBars         = 8;
input bool   InpBBAlert            = false;   // default OFF, same convention as every other non-MA overlay
                                               // since v2.16/2.17 - see InpStochCrossAlert's own comment
input int    InpBBCooldownBars     = 8;       // same per-direction-cooldown idea as InpDivCooldownBars

input group "=== Fair Value Gap (FVG) zones + rejection signals (NEW, v2.19, per direct request) - UNVALIDATED - VISUAL ONLY ==="
input bool   InpShowFVG            = true;    // lightly-shaded zone (not a solid block) for each 3-candle
                                               // imbalance (bullish: candle 3's low is above candle 1's
                                               // high; bearish: mirror) - fires a BUY/SELL signal the first
                                               // time price comes back and REJECTS the zone (wicks in,
                                               // closes back out the way it came), and the zone is removed
                                               // the moment it's no longer valid - either because it got
                                               // fully closed through (invalidated) or because it just gave
                                               // its one rejection signal (spent)
input int    InpFvgMaxZones        = 15;      // hard cap on how many FVG zones can be tracked/drawn at once
input int    InpFvgMaxAgeDays      = 7;       // v2.23: matches InpSigDrawDays' default - per direct request
                                               // ("limit history to a week... as it moves to the next day the
                                               // oldest days signals are removed"), every overlay now rolls on
                                               // the same ~weekly window by default. An unfilled, untouched
                                               // zone older than this is dropped too -
                                               // keeps the chart from accumulating zones from weeks ago
input int    InpFvgSwingBars       = 10;      // SL reference = N-bar swing low/high at the trigger bar
input double InpFvgRR              = 2.0;
input color  InpFvgBullCol         = C'0,60,0';    // dim/dark fill, NOT a solid bright block - drawn with
                                                    // OBJPROP_BACK=true so candles render on top of it
input color  InpFvgBearCol         = C'60,0,0';
input color  InpFvgSpentCol        = C'90,90,90';  // v2.25: per direct request - a zone changes to this
                                                    // colour once a signal has actually fired off it
                                                    // (still removed after InpFvgMaxAgeDays like any other
                                                    // zone), so a spent/already-used zone reads differently
                                                    // from one that's still untested
input color  InpFvgArrowBuyCol     = C'93,25,255'; // the REJECTION SIGNAL arrow's own colour - bright,
                                                    // separate from the dim zone fill above
input color  InpFvgArrowSellCol    = C'255,201,12';
input color  InpFvgStopCol         = clrRed;
input color  InpFvgTPCol           = C'0,255,0';
input int    InpFvgArrowSize       = 1;
input double InpFvgArrowOffsetATR  = 1.9;
input int    InpFvgLineBars        = 8;
input bool   InpFvgAlert           = false;   // default OFF, same convention as every other non-MA overlay
input int    InpFvgCooldownBars    = 8;

input group "=== Liquidity (equal highs/lows) zones + rejection signals (NEW, v2.19, per direct request) - UNVALIDATED - VISUAL ONLY ==="
input bool   InpShowLiquidity      = true;    // a thin shaded band wherever two confirmed swing highs (or
                                               // two swing lows) sit within InpLiqTolATR of each other -
                                               // marks resting liquidity (stops) above equal highs / below
                                               // equal lows. Same rejection-signal + auto-remove behaviour
                                               // as the FVG zones above: SELL when price sweeps into an
                                               // equal-highs band and closes back below it, BUY when it
                                               // sweeps an equal-lows band and closes back above it
input int    InpLiqPivotWindow     = 5;       // confirmed-swing fractal window, same idea as the
                                               // Divergence overlay's own InpDivPivotWindow
input double InpLiqTolATR          = 0.15;    // two swing points within this many ATR of each other count
                                               // as "equal" (a liquidity pool), not a wide price range
input int    InpLiqLookbackBars    = 150;     // the two swing points being compared can't be more than
                                               // this many bars apart - otherwise it's not the same pool
input int    InpLiqMaxZones        = 15;
input int    InpLiqMaxAgeDays      = 7;       // v2.23: matches InpSigDrawDays' default - see InpFvgMaxAgeDays' own comment
input int    InpLiqSwingBars       = 10;
input double InpLiqRR              = 2.0;
input color  InpLiqBullCol         = C'0,50,60';   // equal lows (support/buy-side liquidity)
input color  InpLiqBearCol         = C'60,40,0';   // equal highs (resistance/sell-side liquidity)
input color  InpLiqSpentCol        = C'90,90,90';  // v2.25: same idea as InpFvgSpentCol - a zone changes to
                                                    // this colour once a signal has fired off it
input color  InpLiqArrowBuyCol     = C'178,25,255';
input color  InpLiqArrowSellCol    = C'255,255,12';
input color  InpLiqStopCol         = clrRed;
input color  InpLiqTPCol           = C'0,255,0';
input int    InpLiqArrowSize       = 1;
input double InpLiqArrowOffsetATR  = 1.9;
input int    InpLiqLineBars        = 8;
input bool   InpLiqAlert           = false;
input int    InpLiqCooldownBars    = 8;

CTrade trade;
int g_effectiveMagic = 0;   // v2.12: set once in OnInit - see InpMagic's own comment

int g_maHandle21 = INVALID_HANDLE, g_maHandle50 = INVALID_HANDLE, g_maHandle200 = INVALID_HANDLE;
int g_atrHandleCross = INVALID_HANDLE;
bool     g_crossAlerted = false;     // true while the current approach has already fired its one
                                      // alert - cleared once the gap widens back out or the cross
                                      // actually happens, so the NEXT approach can alert again
datetime g_lastCrossAlertAt = 0;     // cooldown - see InpCrossAlertCooldownMin
//--- NOT "TPNL_..." - PFX ("TPNL_") is used with ObjectsDeleteAll(0, PFX) in
//--- RebuildPanel(), which matches by PREFIX. A "TPNL_MA_..." name would
//--- have been swept by that call too, wiping every MA/VWAP line (including
//--- the whole backfilled history) on every single new bar - exactly the
//--- real bug that made them vanish entirely rather than just sit behind
//--- the panel. Keep this prefix namespace-disjoint from PFX.
string g_pm = "TPMA_";
datetime g_lastBarTime = 0;
//--- v2.08: the ONE source of truth for "which timeframe are the MA
//--- handles and MA/VWAP lines currently built for" - owned only by
//--- SyncMAOverlays(), nothing else writes it (v2.05/v2.06 borrowed the
//--- EMA-cross overlay's g_emaxPeriod for this, which only changed as a
//--- side effect of ResyncEmaCrossSignals()). PERIOD_CURRENT (0) = "not
//--- built yet" - _Period is never 0, so that always forces a rebuild.
ENUM_TIMEFRAMES g_maPeriod = PERIOD_CURRENT;
//--- v2.08: true from a timeframe change until the MA/VWAP history has
//--- been backfilled ONCE on handles that have actually finished
//--- calculating (a fresh iMA handle usually hasn't yet - see
//--- MAHistoryReady()). Set true only by SyncMAOverlays()' period-change
//--- step, set false only by its backfill step.
bool     g_maBackfillPending = false;
ulong    g_maPendingSinceMs  = 0;
bool     g_maInitialDrawDone = false;     // v2.11: true once the one-shot immediate attempt below has run
#define SIG_NA EMPTY_VALUE   // stands in for the Python reference's NaN

//--- v1.47: EMA21/50 crossover overlay - own namespace, fully independent of
//--- own namespace, fully independent of the manual panel. Validated construction: entry on a fresh EMA21/50 cross,
//--- held until the NEXT opposite EMA21/50 cross (ema21_50_pure_crossover_test.py,
//--- GOLD longs %PF=1.031) - NOT the faster EMA21-touch exit, which was tested
//--- and found WORSE (ema21_50_crossover_fast_exit_test.py).
string   g_emax = "TPEMX_";
ENUM_TIMEFRAMES g_emaxPeriod = PERIOD_CURRENT;
int      g_emaxLastDir = 0, g_emaxPosDir = 0;
string   g_emaxLastArr = "", g_emaxLastSl = "", g_emaxLastTp = "";
datetime g_emaxLastProcessedBar = 0;
double   g_emaxLastMarkerPrice = 0.0;
datetime g_emaxLastMarkerTime  = 0;
//--- v2.0: "trend weakening" marker state - tracks the 21/50 gap's own
//--- running peak WITHIN the current open run, reset on every fresh entry
double   g_emaxRunMaxGap    = 0.0;
int      g_emaxDeclineCount = 0;
bool     g_emaxWeakenFired  = false;
//--- v2.01: confirmation-bars entry filter state - a cross starts a
//--- "pending" countdown instead of entering immediately; entry only
//--- fires if price is still past EMA50 in that direction once the
//--- countdown reaches InpEmaConfirmBars. Persisted across live calls
//--- since each call typically processes only one freshly-closed bar.
int      g_emaxPendingDir         = 0;
int      g_emaxPendingBarsElapsed = 0;

//--- v2.02: Stochastic cross overlay (re-added) - own namespace
string   g_sig = "TPSIG_";
ENUM_TIMEFRAMES g_sigPeriod = PERIOD_CURRENT;
int      g_sigLastDir = 0, g_sigPosDir = 0;
string   g_sigLastArr = "", g_sigLastSl = "", g_sigLastTp = "";
datetime g_sigLastProcessedBar = 0;
double   g_sigLastMarkerPrice = 0.0;
datetime g_sigLastMarkerTime  = 0;

//--- v2.02: Candlestick engulfing overlay (re-added) - own namespace
string   g_cdl = "TPCDL_";
ENUM_TIMEFRAMES g_cdlPeriod = PERIOD_CURRENT;
datetime g_cdlLastProcessedBar = 0;
double   g_cdlLastMarkerPrice = 0.0;
datetime g_cdlLastMarkerTime  = 0;

//--- v2.17: stochastic divergence overlay (NEW) - own namespace. Tracks
//--- the single most recent CONFIRMED swing low and swing high (price +
//--- the stochastic %K value at that same bar) so each newly confirmed
//--- pivot can be compared against the previous one of the same type -
//--- that comparison IS the divergence check, nothing more is stored.
string   g_div = "TPDIV_";
ENUM_TIMEFRAMES g_divPeriod = PERIOD_CURRENT;
datetime g_divLastProcessedBar = 0;
double   g_divLastMarkerPrice = 0.0;
datetime g_divLastMarkerTime  = 0;
bool     g_divHaveLow  = false;
datetime g_divLowTime  = 0; double g_divLowPrice  = 0.0; double g_divLowK  = 0.0;
bool     g_divHaveHigh = false;
datetime g_divHighTime = 0; double g_divHighPrice = 0.0; double g_divHighK = 0.0;
datetime g_divLastRegBuyAt  = 0;   // regular bullish  (reversal)
datetime g_divLastRegSellAt = 0;   // regular bearish  (reversal)
datetime g_divLastHidBuyAt  = 0;   // hidden bullish   (continuation)
datetime g_divLastHidSellAt = 0;   // hidden bearish   (continuation)

//--- v2.18: Bollinger outer-band rejection overlay (NEW) - own namespace
string   g_bb = "TPBB_";
datetime g_bbLastProcessedBar = 0;
double   g_bbLastMarkerPrice = 0.0;
datetime g_bbLastMarkerTime  = 0;
datetime g_bbLastBuyAt  = 0;
datetime g_bbLastSellAt = 0;

//--- v2.19: shared zone type for FVG + Liquidity overlays - a priced
//--- rectangle that is either "support" (bullish - reject = BUY) or
//--- "resistance" (bearish - reject = SELL), tracked until it's either
//--- invalidated (closed fully through) or spent (gave its one
//--- rejection signal), at which point it's removed, not left stale.
struct SigZone
  {
   double   top;
   double   bottom;
   bool     bullish;
   datetime startTime;
   bool     active;
   string   rectName;
  };

string   g_fvg = "TPFVG_";       // zone RECTANGLES only - lifecycle owned entirely by PruneZones(),
                                  // never touched by HousekeepOldObjects()
string   g_fvgSig = "TPFVGX_";   // this overlay's signal arrows/SL/TP - one-shot markers, cleaned up
                                  // by HousekeepOldObjects() same as every other overlay's signals
SigZone  g_fvgZones[];
datetime g_fvgLastProcessedBar = 0;
double   g_fvgLastMarkerPrice = 0.0;
datetime g_fvgLastMarkerTime  = 0;
datetime g_fvgLastBuyAt = 0, g_fvgLastSellAt = 0;

string   g_liq = "TPLIQ_";       // zone RECTANGLES only - see g_fvg's own comment, same reasoning
string   g_liqSig = "TPLIQX_";   // this overlay's signal arrows/SL/TP
SigZone  g_liqZones[];
datetime g_liqLastProcessedBar = 0;
double   g_liqLastMarkerPrice = 0.0;
datetime g_liqLastMarkerTime  = 0;
datetime g_liqLastBuyAt = 0, g_liqLastSellAt = 0;
//--- single most-recent confirmed swing of each type, same rolling-
//--- previous-pivot pattern as the Divergence overlay's g_divLowTime/
//--- g_divHighTime - a new pivot within tolerance of the stored one
//--- forms a liquidity zone, then REPLACES it (so the next pivot is
//--- compared against this one, not the original)
bool     g_liqHaveLow = false;  datetime g_liqLowTime = 0;  double g_liqLowPrice = 0.0;
bool     g_liqHaveHigh = false; datetime g_liqHighTime = 0; double g_liqHighPrice = 0.0;

string   PFX = "TPNL_";
int      g_panelX = 40, g_panelY = 40;
int      g_panelW = 250;
int      g_panelH = 0;
bool     g_armed = false;
datetime g_armedUntil = 0;
int      g_armSeconds = InpArmSeconds;   // live-adjustable from the panel's Arm delay row

#define PANEL_ZORDER 1000   // keeps every panel widget drawn above freshly-created MA/VWAP
                             // segments AND above MT5's own native trade arrows/levels, which
                             // InpShowTradeLevels/InpHideTradeHistory handle separately (z-order alone
                             // cannot reach those - they are not chart objects)
#define TITLE_BAR_H  24      // drag is restricted to this strip at the top of the panel

bool g_dragging = false;
int  g_dragOffX = 0, g_dragOffY = 0;
ulong g_dragStartMs = 0;   // safety timeout - see OnTimer
ulong g_lastDragUpdateMs = 0;   // throttle - see the mouse-move handler

struct Ctrl { string name; int dx; int dy; };
Ctrl g_ctrls[];
int  g_nCtrls = 0;

//+------------------------------------------------------------------+
//| True while the user is actively typing in any of this panel's     |
//| edit boxes. Previously checked OBJPROP_SELECTED, which depends on |
//| OBJPROP_SELECTABLE being true on the edit object - but SELECTABLE |
//| has to be FALSE for an OBJ_EDIT to enter text-edit mode on click  |
//| at all (true just selects/drags it instead). So this is now a     |
//| plain flag, set true on CHARTEVENT_OBJECT_CLICK for one of these  |
//| boxes and cleared on CHARTEVENT_OBJECT_ENDEDIT - both of which    |
//| fire regardless of SELECTABLE.                                    |
//| v2.23: moved up here (was declared AFTER OnInit(), which needs to  |
//| reset it on reinit - MQL5 requires a global declared before any    |
//| function that references it, textually).                           |
//+------------------------------------------------------------------+
bool g_editFocused = false;

//+------------------------------------------------------------------+
void AddCtrl(string name, int dx, int dy)
  {
   ArrayResize(g_ctrls, g_nCtrls + 1);
   g_ctrls[g_nCtrls].name = name;
   g_ctrls[g_nCtrls].dx = dx;
   g_ctrls[g_nCtrls].dy = dy;
   g_nCtrls++;
  }

//+------------------------------------------------------------------+
void MkLabel(string name, int dx, int dy, string text, color c, int fontsize = 9)
  {
   string full = PFX + name;
   ObjectCreate(0, full, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, full, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, full, OBJPROP_XDISTANCE, g_panelX + dx);
   ObjectSetInteger(0, full, OBJPROP_YDISTANCE, g_panelY + dy);
   ObjectSetString(0, full, OBJPROP_TEXT, text);
   ObjectSetInteger(0, full, OBJPROP_COLOR, c);
   ObjectSetInteger(0, full, OBJPROP_FONTSIZE, fontsize);
   ObjectSetString(0, full, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, full, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, full, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, full, OBJPROP_BACK, false);
   ObjectSetInteger(0, full, OBJPROP_ZORDER, PANEL_ZORDER);
   AddCtrl(full, dx, dy);
  }

//+------------------------------------------------------------------+
void MkEdit(string name, int dx, int dy, int w, int h, string text)
  {
   string full = PFX + name;
   ObjectCreate(0, full, OBJ_EDIT, 0, 0, 0);
   ObjectSetInteger(0, full, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, full, OBJPROP_XDISTANCE, g_panelX + dx);
   ObjectSetInteger(0, full, OBJPROP_YDISTANCE, g_panelY + dy);
   ObjectSetInteger(0, full, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, full, OBJPROP_YSIZE, h);
   ObjectSetString(0, full, OBJPROP_TEXT, text);
   ObjectSetInteger(0, full, OBJPROP_COLOR, clrBlack);
   ObjectSetInteger(0, full, OBJPROP_BGCOLOR, clrWhite);
   ObjectSetInteger(0, full, OBJPROP_ALIGN, ALIGN_CENTER);
   ObjectSetInteger(0, full, OBJPROP_FONTSIZE, 10);
   //--- SELECTABLE=true on an OBJ_EDIT makes a click SELECT the object
   //--- (drag handles, for moving it on the chart) instead of putting it
   //--- into text-edit mode - the real cause of "clicking does nothing,
   //--- no text cursor" on every edit box on this panel. false here
   //--- matches MkButton's own setting below and is what actually lets a
   //--- click (or double-click) focus the box for typing.
   ObjectSetInteger(0, full, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, full, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, full, OBJPROP_ZORDER, PANEL_ZORDER);
   AddCtrl(full, dx, dy);
  }

//+------------------------------------------------------------------+
void MkButton(string name, int dx, int dy, int w, int h, string text, color bg, color fg = clrWhite, int fontsize = 9)
  {
   string full = PFX + name;
   ObjectCreate(0, full, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, full, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, full, OBJPROP_XDISTANCE, g_panelX + dx);
   ObjectSetInteger(0, full, OBJPROP_YDISTANCE, g_panelY + dy);
   ObjectSetInteger(0, full, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, full, OBJPROP_YSIZE, h);
   ObjectSetString(0, full, OBJPROP_TEXT, text);
   ObjectSetInteger(0, full, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, full, OBJPROP_COLOR, fg);
   ObjectSetInteger(0, full, OBJPROP_BORDER_COLOR, clrBlack);
   ObjectSetInteger(0, full, OBJPROP_FONTSIZE, fontsize);
   ObjectSetString(0, full, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, full, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, full, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, full, OBJPROP_STATE, false);
   ObjectSetInteger(0, full, OBJPROP_ZORDER, PANEL_ZORDER);
   AddCtrl(full, dx, dy);
  }

//+------------------------------------------------------------------+
double GetLot()
  {
   double lot = StringToDouble(ObjectGetString(0, PFX + "lotEdit", OBJPROP_TEXT));
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lot < minLot) lot = minLot;
   //--- v2.26 FIX (Opus-flagged zero-divide risk) - see main file's comment.
   if(step <= 0.0) step = 0.01;
   lot = MathRound(lot / step) * step;
   return lot;
  }

//+------------------------------------------------------------------+
int GetCount()
  {
   int n = (int)StringToInteger(ObjectGetString(0, PFX + "cntEdit", OBJPROP_TEXT));
   if(n < 1) n = 1;
   if(n > 50) n = 50;   // hard safety cap regardless of what's typed in - real money, no fat-finger "500"
   return n;
  }

//+------------------------------------------------------------------+
void UpdateExposureLabel()
  {
   double lot = GetLot();
   int n = GetCount();
   string txt = StringFormat("Exposure: %d x %s = %s lot", n, DoubleToString(lot, 2), DoubleToString(lot * n, 2));
   ObjectSetString(0, PFX + "expLbl", OBJPROP_TEXT, txt);
  }

//+------------------------------------------------------------------+
void AdjustLot(double delta)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot = GetLot() + delta;
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;
   if(step <= 0.0) step = 0.01;
   lot = MathRound(lot / step) * step;
   int digits = step >= 0.01 ? 2 : (step >= 0.001 ? 3 : 2);
   ObjectSetString(0, PFX + "lotEdit", OBJPROP_TEXT, DoubleToString(lot, digits));
   UpdateExposureLabel();
  }

//+------------------------------------------------------------------+
void AdjustCount(int delta)
  {
   int n = GetCount() + delta;
   if(n < 1) n = 1;
   if(n > 50) n = 50;
   ObjectSetString(0, PFX + "cntEdit", OBJPROP_TEXT, IntegerToString(n));
   UpdateExposureLabel();
  }

//+------------------------------------------------------------------+
void AdjustArmSeconds(int delta)
  {
   g_armSeconds += delta;
   if(g_armSeconds < 1) g_armSeconds = 1;
   if(g_armSeconds > 60) g_armSeconds = 60;
   ObjectSetString(0, PFX + "delayEdit", OBJPROP_TEXT, IntegerToString(g_armSeconds));
  }

//+------------------------------------------------------------------+
void SyncArmSecondsFromEdit()
  {
   int n = (int)StringToInteger(ObjectGetString(0, PFX + "delayEdit", OBJPROP_TEXT));
   if(n < 1) n = 1;
   if(n > 60) n = 60;
   g_armSeconds = n;
   ObjectSetString(0, PFX + "delayEdit", OBJPROP_TEXT, IntegerToString(g_armSeconds));
  }

//+------------------------------------------------------------------+
void SetArmed(bool on)
  {
   g_armed = on;
   g_armedUntil = on ? TimeCurrent() + g_armSeconds : 0;
   string btn = PFX + "armBtn";
   if(on)
     {
      ObjectSetString(0, btn, OBJPROP_TEXT, "ARMED - click PLACE now");
      ObjectSetInteger(0, btn, OBJPROP_BGCOLOR, InpArmedColor);
     }
   else
     {
      ObjectSetString(0, btn, OBJPROP_TEXT, "ARM (required before PLACE)");
      ObjectSetInteger(0, btn, OBJPROP_BGCOLOR, InpBgColor);
     }
   ObjectSetInteger(0, btn, OBJPROP_STATE, false);
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
void PlaceBatch(bool isBuy)
  {
   if(!g_armed)
     {
      Alert("TradePanel: click ARM first, then PLACE, within ", g_armSeconds, "s.");
      return;
     }
   double lot = GetLot();
   int n = GetCount();
   trade.SetExpertMagicNumber(g_effectiveMagic);
   int placed = 0, failed = 0;
   for(int k = 0; k < n; k++)
     {
      bool ok = isBuy ? trade.Buy(lot, _Symbol, 0.0, 0.0, 0.0, "TradePanel")
                      : trade.Sell(lot, _Symbol, 0.0, 0.0, 0.0, "TradePanel");
      if(ok) placed++; else failed++;
     }
   PrintFormat("TradePanel: requested %d x %s %s lot - placed %d, failed %d.",
               n, isBuy ? "BUY" : "SELL", DoubleToString(lot, 2), placed, failed);
   SetArmed(false);
  }

//+------------------------------------------------------------------+
bool PositionMatches(ulong ticket)
  {
   if(!PositionSelectByTicket(ticket)) return false;
   if(PositionGetString(POSITION_SYMBOL) != _Symbol) return false;
   if(PositionGetInteger(POSITION_MAGIC) != g_effectiveMagic) return false;
   return true;
  }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Closes exactly the N oldest matched positions, in full - avoids the
//| ambiguity of a percentage-based close with several equal-size trades
//| from one PLACE xN batch, where "close 50%" can only ever approximate
//| a whole number of positions anyway. Closes fewer than N without
//| complaint if fewer than N are open.
//+------------------------------------------------------------------+
void ClosePositionCount(int n)
  {
   int total = PositionsTotal();
   ulong  tickets[];
   datetime opens[];
   int m = 0;
   ArrayResize(tickets, total);
   ArrayResize(opens, total);
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      tickets[m] = ticket;
      opens[m]   = (datetime)PositionGetInteger(POSITION_TIME);
      m++;
     }
   if(m == 0) return;

   // oldest-first (ascending open time) - simple insertion sort, m is tiny
   for(int a = 1; a < m; a++)
     {
      ulong tt = tickets[a]; datetime to = opens[a];
      int b = a - 1;
      while(b >= 0 && opens[b] > to)
        {
         tickets[b + 1] = tickets[b]; opens[b + 1] = opens[b];
         b--;
        }
      tickets[b + 1] = tt; opens[b + 1] = to;
     }

   int closeN = MathMin(n, m);
   int closed = 0, failed = 0;
   for(int i = 0; i < closeN; i++)
      if(trade.PositionClose(tickets[i], (ulong)InpSlippage)) closed++; else failed++;
   PrintFormat("TradePanel: close %d position(s) - %d closed, %d failed (%d were open).", n, closed, failed, m);
  }

//+------------------------------------------------------------------+
void CloseAll()
  {
   int total = PositionsTotal();
   int closed = 0, failed = 0;
   for(int i = total - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      if(trade.PositionClose(ticket, (ulong)InpSlippage)) closed++; else failed++;
     }
   PrintFormat("TradePanel: CLOSE ALL - %d closed, %d failed.", closed, failed);
  }

//+------------------------------------------------------------------+
//| Applies a new SL (or TP) to every matched open position, keeping  |
//| that position's OWN current TP (or SL) unchanged - trade.PositionModify()
//| always sets both levels together, so the one not being edited here
//| has to be re-read from the position and re-sent, or it would get
//| wiped to 0 (no stop/target at all) rather than left alone.
//+------------------------------------------------------------------+
void SetSLForAll(double newSL)
  {
   int total = PositionsTotal();
   int done = 0, failed = 0;
   for(int i = total - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      double tp = PositionGetDouble(POSITION_TP);
      if(trade.PositionModify(ticket, newSL, tp)) done++; else failed++;
     }
   PrintFormat("TradePanel: Set SL=%s - %d position(s) updated, %d failed.",
               DoubleToString(newSL, _Digits), done, failed);
   if(failed > 0)
      Alert("TradePanel: Set SL failed on ", failed, " position(s) - check Experts log (common cause: price too close to market, broker's stop level).");
  }

//+------------------------------------------------------------------+
void SetTPForAll(double newTP)
  {
   int total = PositionsTotal();
   int done = 0, failed = 0;
   for(int i = total - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      double sl = PositionGetDouble(POSITION_SL);
      if(trade.PositionModify(ticket, sl, newTP)) done++; else failed++;
     }
   PrintFormat("TradePanel: Set TP=%s - %d position(s) updated, %d failed.",
               DoubleToString(newTP, _Digits), done, failed);
   if(failed > 0)
      Alert("TradePanel: Set TP failed on ", failed, " position(s) - check Experts log (common cause: price too close to market, broker's stop level).");
  }

//+------------------------------------------------------------------+
//| Fills the SL/TP edit fields from the first matched open position -|
//| convenience so you can nudge an existing level instead of typing   |
//| one from scratch. Multiple matched positions only fills from the   |
//| first found; Set SL/Set TP still apply to ALL of them.             |
//+------------------------------------------------------------------+
void FillCurrentSLTP()
  {
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      ObjectSetString(0, PFX + "slEdit", OBJPROP_TEXT, DoubleToString(sl, _Digits));
      ObjectSetString(0, PFX + "tpEdit", OBJPROP_TEXT, DoubleToString(tp, _Digits));
      return;
     }
   Alert("TradePanel: no open position to read SL/TP from.");
  }

//+------------------------------------------------------------------+
void UpdateStats()
  {
   int n = 0; double vol = 0, pl = 0;
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      n++;
      vol += PositionGetDouble(POSITION_VOLUME);
      pl  += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   color plc = pl >= 0 ? clrLimeGreen : clrOrangeRed;
   string txt = StringFormat("Open: %d pos | %s lot | P/L %s", n, DoubleToString(vol, 2), DoubleToString(pl, 2));
   ObjectSetString(0, PFX + "statLbl", OBJPROP_TEXT, txt);
   ObjectSetInteger(0, PFX + "statLbl", OBJPROP_COLOR, plc);
  }

//+------------------------------------------------------------------+
void UpdateMarketLabel()
  {
   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   long vol1 = iVolume(_Symbol, PERIOD_CURRENT, 1);   // last CLOSED bar's tick volume -
                                                       // bar 0 is still forming and understates it
   ObjectSetString(0, PFX + "spreadLbl", OBJPROP_TEXT, StringFormat("Spread: %d points", (int)spreadPts));
   ObjectSetString(0, PFX + "volLbl",    OBJPROP_TEXT, StringFormat("Volume (last bar): %d", (int)vol1));

   bool ok = spreadPts <= InpMaxSpreadPoints;
   ObjectSetInteger(0, PFX + "light", OBJPROP_COLOR, ok ? clrLimeGreen : clrRed);
   ObjectSetString(0, PFX + "lightLbl", OBJPROP_TEXT,
                    ok ? "OK TO TRADE (spread within limit)" : "SPREAD TOO WIDE - WAIT");
   ObjectSetInteger(0, PFX + "lightLbl", OBJPROP_COLOR, ok ? clrLimeGreen : clrRed);
  }

//+------------------------------------------------------------------+
//| Chart theme - identical convention to the other EAs in this     |
//| project (InpBullCol/InpBearCol/InpChartBg, same ChartSetInteger  |
//| set) so a chart running this panel looks consistent with one     |
//| running HeadShoulders/Aurelius/etc.                               |
//+------------------------------------------------------------------+
void ApplyTheme()
  {
   //--- two independent chart properties, two independent inputs - the
   //--- native open/SL/TP drag-lines and the closed-trade history arrows
   //--- are NOT the same setting and shouldn't share one toggle.
   ChartSetInteger(0, CHART_SHOW_TRADE_LEVELS, InpShowTradeLevels);
   if(InpHideTradeHistory) ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, false);
   if(!InpApplyTheme) return;
   ChartSetInteger(0, CHART_COLOR_BACKGROUND,  InpChartBg);
   ChartSetInteger(0, CHART_COLOR_FOREGROUND,  C'138,152,178');
   ChartSetInteger(0, CHART_COLOR_GRID,        C'20,26,40');
   ChartSetInteger(0, CHART_COLOR_CHART_UP,    InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CHART_DOWN,  InpBearCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, InpBearCol);
   ChartSetInteger(0, CHART_COLOR_CHART_LINE,  C'138,152,178');
   ChartSetInteger(0, CHART_SHOW_GRID,   false);
   ChartSetInteger(0, CHART_MODE,        CHART_CANDLES);
  }

//+------------------------------------------------------------------+
//| Session VWAP - MT5 has no built-in VWAP indicator, so this is the|
//| exact same construction already validated in Aurelius_EA.mq5's   |
//| SessionVWAP(): typical-price*volume accumulated from midnight,   |
//| one bulk CopyTime/CopyHigh/.../CopyTickVolume per call rather    |
//| than per-bar iTime/iHigh/... lookups (that was the real slow     |
//| part when this was first built, not "repainting").               |
//+------------------------------------------------------------------+
double SessionVWAP(const int shift)
  {
   datetime barTime = iTime(_Symbol, PERIOD_CURRENT, shift);
   if(barTime == 0) return(0.0);
   MqlDateTime dt; TimeToStruct(barTime, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);

   datetime tArr[]; double hArr[], lArr[], cArr[]; long vArr[];
   ArraySetAsSeries(tArr, true); ArraySetAsSeries(hArr, true);
   ArraySetAsSeries(lArr, true); ArraySetAsSeries(cArr, true);
   ArraySetAsSeries(vArr, true);
   int got = CopyTime(_Symbol, PERIOD_CURRENT, shift, 400, tArr);
   if(got <= 0) return(0.0);
   if(CopyHigh(_Symbol, PERIOD_CURRENT, shift, got, hArr) <= 0) return(0.0);
   if(CopyLow(_Symbol, PERIOD_CURRENT, shift, got, lArr) <= 0) return(0.0);
   if(CopyClose(_Symbol, PERIOD_CURRENT, shift, got, cArr) <= 0) return(0.0);
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, shift, got, vArr) <= 0) return(0.0);

   double cumPV = 0.0, cumV = 0.0;
   for(int s = 0; s < got; s++)
     {
      if(tArr[s] < dayStart) break;
      double typical = (hArr[s] + lArr[s] + cArr[s]) / 3.0;
      cumPV += typical * (double)vArr[s];
      cumV  += (double)vArr[s];
     }
   if(cumV <= 0.0) return(0.0);
   return(cumPV / cumV);
  }

//+------------------------------------------------------------------+
bool DifferentSession(const int shiftA, const int shiftB)
  {
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, shiftA);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, shiftB);
   if(tA == 0 || tB == 0) return(true);
   MqlDateTime dA, dB; TimeToStruct(tA, dA); TimeToStruct(tB, dB);
   return(dA.day != dB.day || dA.mon != dB.mon || dA.year != dB.year);
  }

//+------------------------------------------------------------------+
//| Generic per-bar trend-line segment, same idiom (and reasoning)   |
//| as Aurelius_EA.mq5's DrawMASegment - hand-drawn rather than a     |
//| native ChartIndicatorAdd plot because MT5 doesn't expose a        |
//| per-instance colour override for a chart-added indicator handle,  |
//| and these need the project's own "family standard" colours.      |
//+------------------------------------------------------------------+
void DrawSegment(const string tag, const datetime tOld, const double vOld,
                  const datetime tNew, const double vNew, const color col, const int width = 1)
  {
   string nm = g_pm + tag + "_" + IntegerToString((long)tNew);
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_TREND, 0, tOld, vOld, tNew, vNew);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
//| v2.14: ONE pass over the chart's objects that drops BOTH expired   |
//| MA/VWAP segments AND expired signal-overlay objects. Replaces       |
//| PurgeOldSegments() plus six separate PurgeOld*Objects() functions   |
//| (one per signal overlay) that EACH walked every object on the chart |
//| (~7,000 at default settings) on EVERY new bar - about 55,000        |
//| synchronous ObjectName/ObjectGetInteger calls per bar, each of which|
//| has to wait for the chart's own command queue, all of it sitting    |
//| between a signal's push alert and the ChartRedraw that actually     |
//| shows its arrow. Same cutoffs as before, exactly: MA/VWAP segments  |
//| older than InpMAHistoryBars (or InpVwapHistoryBars if larger) bars  |
//| of chart time, signal objects older than InpSigDrawDays calendar    |
//| days (Rejection M15 measured against the last closed M15 bar, as    |
//| before). Never touches the panel (PFX) or anything this EA didn't   |
//| create. Called from CheckNewBar() AFTER the chart is redrawn, and   |
//| at most once per hour of bar time - see there.                      |
//+------------------------------------------------------------------+
datetime g_lastHousekeepBar = 0;

void HousekeepOldObjects()
  {
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(tB == 0) return;
   int maxHist = InpMAHistoryBars;
   if(InpShowVWAP && InpMAHistoryBars < InpVwapHistoryBars) maxHist = InpVwapHistoryBars;
   datetime segCutoff = tB - (datetime)((long)maxHist * PeriodSeconds(PERIOD_CURRENT));
   //--- v2.27 FIX: calendar-day aligned (see main file's own comment) -
   //--- cutoff = midnight of (InpSigDrawDays-1) days ago.
   MqlDateTime mdt;
   TimeToStruct(TimeCurrent(), mdt);
   mdt.hour = 0; mdt.min = 0; mdt.sec = 0;
   datetime todayStart = StructToTime(mdt);
   datetime sigCutoff = todayStart - (datetime)((long)(InpSigDrawDays - 1) * 86400);
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      datetime cutoff = 0;
      if(StringFind(nm, g_pm) == 0) cutoff = segCutoff;
      else if(StringFind(nm, g_emax) == 0 || StringFind(nm, g_sig) == 0 || StringFind(nm, g_cdl) == 0
              || StringFind(nm, g_div) == 0 || StringFind(nm, g_bb) == 0
              || StringFind(nm, g_fvgSig) == 0 || StringFind(nm, g_liqSig) == 0)
         cutoff = sigCutoff;
      else continue;   // panel widgets, other programs' / the user's own objects - never touched
      if(cutoff <= 0) continue;
      if((datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0) < cutoff) ObjectDelete(0, nm);
     }
  }

//+------------------------------------------------------------------+
bool MAValue(int handle, int shift, double &out)
  {
   if(handle == INVALID_HANDLE) return(false);
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle, 0, shift, 1, buf) < 1) return(false);
   out = buf[0];
   return(true);
  }

//+------------------------------------------------------------------+
//| v1.58: REVERTED to hand-drawn (see InpMAHistoryBars' own comment     |
//| for why) - draws exactly one new segment per line (MAs + VWAP) per   |
//| new bar, same idiom as Aurelius_EA.mq5's own UpdateMALines.          |
//+------------------------------------------------------------------+
void UpdateOverlayLines()
  {
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, 2);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(tA == 0 || tB == 0) return;
   if(InpShowMAs)
     {
      double a21, b21, a50, b50, a200, b200;
      if(MAValue(g_maHandle21, 2, a21) && MAValue(g_maHandle21, 1, b21))
         DrawSegment("21", tA, a21, tB, b21, InpCol21, InpMALineWidth);
      if(MAValue(g_maHandle50, 2, a50) && MAValue(g_maHandle50, 1, b50))
         DrawSegment("50", tA, a50, tB, b50, InpCol50, InpMALineWidth);
      if(MAValue(g_maHandle200, 2, a200) && MAValue(g_maHandle200, 1, b200))
         DrawSegment("200", tA, a200, tB, b200, InpCol200, InpMALineWidth);
     }
   if(InpShowVWAP && !DifferentSession(2, 1))
     {
      double vA = SessionVWAP(2), vB = SessionVWAP(1);
      if(vA > 0.0 && vB > 0.0) DrawSegment("vwap", tA, vA, tB, vB, InpColVWAP, InpVwapLineWidth);
     }
   //--- v2.14: the old-segment purge that used to run here (a full scan of
   //--- every trend object on the chart, every bar, BEFORE any signal was
   //--- computed) now lives in HousekeepOldObjects(), run from
   //--- CheckNewBar() after the chart has already been redrawn.
  }

//+------------------------------------------------------------------+
//| v1.58: REVERTED to hand-drawn - walks backward and draws the whole   |
//| rolling window immediately on attach, same reasoning as              |
//| Aurelius_EA.mq5's own BackfillMALines (otherwise a fresh attach      |
//| shows a 1-bar stub and takes the full history window to fill in).    |
//+------------------------------------------------------------------+
void BackfillOverlayLines()
  {
   if(InpShowMAs)
     {
      int avail = Bars(_Symbol, PERIOD_CURRENT) - 2;
      int n = MathMin(InpMAHistoryBars, avail);
      double a, b;
      for(int s = n; s >= 1; s--)
        {
         datetime tA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
         datetime tB = iTime(_Symbol, PERIOD_CURRENT, s);
         if(tA == 0 || tB == 0) continue;
         if(MAValue(g_maHandle21,  s + 1, a) && MAValue(g_maHandle21,  s, b)) DrawSegment("21",  tA, a, tB, b, InpCol21, InpMALineWidth);
         if(MAValue(g_maHandle50,  s + 1, a) && MAValue(g_maHandle50,  s, b)) DrawSegment("50",  tA, a, tB, b, InpCol50, InpMALineWidth);
         if(MAValue(g_maHandle200, s + 1, a) && MAValue(g_maHandle200, s, b)) DrawSegment("200", tA, a, tB, b, InpCol200, InpMALineWidth);
        }
     }
   if(InpShowVWAP)
     {
      int availV = Bars(_Symbol, PERIOD_CURRENT) - 2;
      int nV = MathMin(InpVwapHistoryBars, availV);
      for(int s = nV; s >= 1; s--)
        {
         if(DifferentSession(s + 1, s)) continue;
         datetime tA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
         datetime tB = iTime(_Symbol, PERIOD_CURRENT, s);
         if(tA == 0 || tB == 0) continue;
         double vA = SessionVWAP(s + 1), vB = SessionVWAP(s);
         if(vA > 0.0 && vB > 0.0) DrawSegment("vwap", tA, vA, tB, vB, InpColVWAP, InpVwapLineWidth);
        }
     }
  }

//+------------------------------------------------------------------+
//| CLASSIC / TEXTBOOK Stochastic signal overlay.                      |
//|                                                                     |
//| This implements the classic rule as described in published retail  |
//| trading sources (OANDA, Investopedia, FBS, VectorVest, LuxAlgo):    |
//| Stochastic(14,3,3) Low/High + SMA, %K crossing %D inside the 80/20 |
//| zone, stop beyond the recent swing, 1:2 R:R target.                 |
//|                                                                     |
//| It is NOT this project's own backtested research. The research     |
//| (research/meridian_vwap200/dual_stoch_*.py) tested a DIFFERENT     |
//| construction (dual Close/Close SMMA stochastics, MA/VWAP stop, ATR |
//| targets) and found it unprofitable / no better than random timing. |
//| THIS rule has not been tested at all - treat it as UNVALIDATED, a  |
//| visual "what the textbook says" reference only.                    |
//|                                                                     |
//| Hand-rolled rather than iStochastic()+CopyBuffer: the backfill runs |
//| from OnInit, where a fresh indicator handle routinely reports       |
//| BarsCalculated() = -1 and CopyBuffer fails, so the history would    |
//| silently come up empty; and a PERIOD_CURRENT handle would also need |
//| re-creating on the no-reinit timeframe-switch path below. The math  |
//| below is MT5's own iStochastic(14,3,3,MODE_SMA,STO_LOWHIGH) formula |
//| (slowing = SMA of numerator and denominator separately, %D = SMA   |
//| of %K). Arrays are chronological (index 0 = oldest), NOT series-   |
//| ordered like the rest of this file.                                 |
//+------------------------------------------------------------------+


//+------------------------------------------------------------------+
void DrawSigLevel(const string nm, const datetime t1, const datetime t2, const double price,
                  const color col, const ENUM_LINE_STYLE style, const string tip)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, tip + " " + DoubleToString(price, _Digits));
  }

//+------------------------------------------------------------------+
//| 1.40: general anti-collision for ANY two signal markers (entry     |
//| arrow or exit dot, any combination), not just the old special case |
//| of an entry+exit landing on the exact same bar. A tight/compressed |
//| consolidation (small ATR, small candle range) can put two markers  |
//| from DIFFERENT nearby bars close enough in price to visually       |
//| overlap even though nothing about the same-bar stacking logic      |
//| applies - reported from a live chart (a buy arrow and an           |
//| EXIT-SHORT dot sitting right on top of each other at the bottom of |
//| a shallow dip). Only nudges when the two markers are BOTH close in |
//| price (< minGap) AND close in time (within InpSigMarkerLookbackBars|
//| bars) - far-apart-in-time markers at a similar price are a         |
//| coincidence, not visual clutter, and must not be pushed around.    |
//+------------------------------------------------------------------+
double NudgeAwayFromLastMarker(double candidatePrice, datetime candidateTime, bool pushUp,
                               double lastMarkerPrice, datetime lastMarkerTime, double minGap)
  {
   if(lastMarkerTime == 0 || minGap <= 0.0) return candidatePrice;
   double barsApart = MathAbs((double)(candidateTime - lastMarkerTime)) / (double)PeriodSeconds(PERIOD_CURRENT);
   if(barsApart > InpSigMarkerLookbackBars) return candidatePrice;
   if(MathAbs(candidatePrice - lastMarkerPrice) >= minGap) return candidatePrice;
   return pushUp ? lastMarkerPrice + minGap : lastMarkerPrice - minGap;
  }

//+------------------------------------------------------------------+
//| v2.22: per direct request - "make sure the dont print over of      |
//| indicators, like the moving averages and so on". A marker placed   |
//| offset from the candle can still land directly ON a live MA line   |
//| if that MA happens to be passing through the same price at that    |
//| bar - this pushes it clear of a single MA value, same convention   |
//| as NudgeAwayFromLastMarker/NudgeClearOfOtherOverlays (only moves   |
//| further in the direction the marker is already being offset, never |
//| back toward the candle). maValue == SIG_NA is a no-op (MA not       |
//| ready yet at this bar).                                            |
//+------------------------------------------------------------------+
double NudgeClearOfMALine(double price, const double maValue, const bool pushUp, const double minGap)
  {
   if(maValue == SIG_NA || minGap <= 0.0) return price;
   if(MathAbs(price - maValue) >= minGap) return price;
   return pushUp ? maValue + minGap : maValue - minGap;
  }

//+------------------------------------------------------------------+
//| v2.14: cross-OVERLAY de-overlap. NudgeAwayFromLastMarker() above   |
//| only ever compares a new marker with the SAME overlay's previous   |
//| marker - two DIFFERENT overlays firing on the same candle, same    |
//| side, at the same ATR offset land on exactly the same pixel, and   |
//| since every entry arrow is now the same shape and size (v2.06/     |
//| v2.08) the later one completely hides the earlier one. Worst case: |
//| on an M15 chart the Rejection and Rejection M15 overlays run the   |
//| identical calculation on identical bars, so EVERY chart-timeframe  |
//| Rejection arrow was painted over by its Rejection M15 twin - the   |
//| alert said "Rejection BUY" and no Rejection-coloured arrow could   |
//| be seen. Rejection/Continuation (both 1.3 ATR) and EMA cross/      |
//| Engulfing (both 1.0 ATR) can collide the same way, less often.     |
//| This checks every other overlay's marker on the SAME candle (by    |
//| name - all overlays use "<prefix><kind>_<bar time>") and pushes    |
//| the new one further out, away from the candle, until it clears    |
//| them all. Marker PRICE only - no effect on any signal, alert, SL   |
//| or TP. selfName is skipped so a marker never collides with itself. |
//+------------------------------------------------------------------+
double NudgeClearOfOtherOverlays(double price, const datetime t, const bool pushUp,
                                 const double minGap, const string selfName)
  {
   if(minGap <= 0.0) return price;
   string id = IntegerToString((long)t);
   //--- v2.21 FIX (Opus-found): Divergence names its arrows
   //--- "reg_buy_"/"hid_buy_"/"reg_sell_"/"hid_sell_", never plain
   //--- "arr_" - the old single g_div+"arr_"+id entry here could never
   //--- actually match anything, so Divergence arrows were silently
   //--- exempt from this de-overlap check the whole time. All four real
   //--- name patterns now included.
   string names[10];
   names[0] = g_emax + "arr_"  + id;
   names[1] = g_emax + "exit_" + id;
   names[2] = g_emax + "weak_" + id;
   names[3] = g_sig  + "arr_"  + id;
   names[4] = g_cdl  + "arr_"  + id;
   names[5] = g_div  + "reg_buy_"  + id;
   names[6] = g_div  + "hid_buy_"  + id;
   names[7] = g_div  + "reg_sell_" + id;
   names[8] = g_div  + "hid_sell_" + id;
   names[9] = g_bb   + "arr_"  + id;
   //--- v2.19: FVG/Liquidity arrow names include a zone-index suffix
   //--- (g_fvgSig + "arr_" + id + "_" + zoneIndex), so an exact-name
   //--- lookup here can't work the way it does for the other overlays -
   //--- intentionally NOT added to this de-overlap check; their own
   //--- NudgeAwayFromLastMarker call (against each other, within the
   //--- same overlay) still applies
   double others[12];
   int m = 0;
   for(int j = 0; j < 12; j++)
     {
      if(names[j] == selfName || ObjectFind(0, names[j]) < 0) continue;
      others[m] = ObjectGetDouble(0, names[j], OBJPROP_PRICE, 0);
      m++;
     }
   //--- every move goes the same way (always up, or always down), so this
   //--- settles in at most m passes - the cap is just a belt-and-braces bound
   for(int pass = 0; pass < 8; pass++)
     {
      bool moved = false;
      for(int j = 0; j < m; j++)
        {
         if(MathAbs(price - others[j]) < minGap)
           {
            price = pushUp ? others[j] + minGap : others[j] - minGap;
            moved = true;
           }
        }
      if(!moved) break;
     }
   return price;
  }


//+------------------------------------------------------------------+
//| v1.47: EMA21/50 crossover overlay's own entry arrow / exit dot -     |
//| deliberately separate from DrawSigArrow/DrawSigDot (which hardcode   |
//| the stochastic overlay's own color inputs) so this independent        |
//| overlay has its own color inputs and tooltip text.                    |
//+------------------------------------------------------------------+
void DrawEmaCrossArrow(const string nm, const datetime t, const double price, const bool isBuy)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, isBuy ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, isBuy ? InpEmaCrossBuyCol : InpEmaCrossSellCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpEmaCrossArrowSize);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, isBuy ? "EMA Cross Buy" : "EMA Cross Sell");
  }

void DrawEmaCrossDot(const string nm, const datetime t, const double price, const bool wasLong)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_ARROWCODE, 159);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, wasLong ? InpEmaCrossBuyCol : InpEmaCrossSellCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpEmaCrossDotSize);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, wasLong ? "EMA Cross Exit (long)" : "EMA Cross Exit (short)");
  }

//+------------------------------------------------------------------+
//| v2.0: "trend weakening" marker - the 21/50 gap stopped widening and  |
//| started pulling back together again WITHIN the current open run,     |
//| before the actual opposite cross that would close the position -     |
//| a distinct shape/color from the entry arrow and exit dot so it's      |
//| never confused with either.                                           |
//+------------------------------------------------------------------+
void DrawEmaWeakenMarker(const string nm, const datetime t, const double price, const bool wasLong)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_ARROWCODE, 108);   // warning-ish diamond-dot shape, distinct from
                                                        // the entry triangle (OBJ_ARROW_UP/DOWN) and
                                                        // exit filled circle (code 159)
   ObjectSetInteger(0, nm, OBJPROP_COLOR, InpEmaWeakenCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpEmaWeakenSize);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, wasLong ? "EMA21/50 WEAKENING - gap narrowing again in the LONG run (21EMA losing its angle) - not an exit, just a caution"
                                                     : "EMA21/50 WEAKENING - gap narrowing again in the SHORT run (21EMA losing its angle) - not an exit, just a caution");
  }


//+------------------------------------------------------------------+
//| Plain Wilder ATR(period), used only to push the arrows/dots a      |
//| sane, instrument-scaled distance away from the candles - has no    |
//| effect on the signal, stop or target math above.                   |
//+------------------------------------------------------------------+
void SigATR(const double &h[], const double &l[], const double &c[], const int n, const int period, double &atr[])
  {
   ArrayResize(atr, n);
   ArrayInitialize(atr, SIG_NA);
   if(n < period + 1) return;
   double sum = 0.0;
   for(int i = 1; i <= period; i++)
      sum += MathMax(h[i] - l[i], MathMax(MathAbs(h[i] - c[i - 1]), MathAbs(l[i] - c[i - 1])));
   atr[period] = sum / period;
   for(int i = period + 1; i < n; i++)
     {
      double tr = MathMax(h[i] - l[i], MathMax(MathAbs(h[i] - c[i - 1]), MathAbs(l[i] - c[i - 1])));
      atr[i] = (atr[i - 1] * (period - 1) + tr) / period;
     }
  }

//+------------------------------------------------------------------+
//| v1.47: self-contained EMA, same style as SigATR() above (computed   |
//| directly off the CopyRates-loaded close array, not an iMA handle -   |
//| avoids any indexing-direction mismatch) - seeded with the SMA of the |
//| first `period` closes, then the standard EMA recursion. Mirrors the  |
//| Python research's own ema() helper exactly (same seed, same alpha).  |
//+------------------------------------------------------------------+
void SigEMA(const double &c[], const int n, const int period, double &ema[])
  {
   ArrayResize(ema, n);
   ArrayInitialize(ema, SIG_NA);
   if(n < period) return;
   double sum = 0.0;
   for(int i = 0; i < period; i++) sum += c[i];
   ema[period - 1] = sum / period;
   double alpha = 2.0 / (period + 1.0);
   for(int i = period; i < n; i++)
      ema[i] = ema[i - 1] + alpha * (c[i] - ema[i - 1]);
  }

//+------------------------------------------------------------------+
//| v2.18: standard Bollinger Bands (SMA mid-band + population stddev   |
//| upper/lower, same convention as MT5's own iBands) - self-contained, |
//| same style as SigATR/SigEMA above, for the new outer-band rejection |
//| overlay below.                                                       |
//+------------------------------------------------------------------+
void SigBollinger(const double &c[], const int n, const int period, const double dev,
                   double &mid[], double &upper[], double &lower[])
  {
   ArrayResize(mid, n);   ArrayInitialize(mid, SIG_NA);
   ArrayResize(upper, n); ArrayInitialize(upper, SIG_NA);
   ArrayResize(lower, n); ArrayInitialize(lower, SIG_NA);
   //--- v2.21 FIX (Opus-found): period<=0 (e.g. InpBBPeriod set to 0 or
   //--- negative) made the loop start at mid[-1] - an out-of-range write
   //--- that crashes the EA. Only reachable if that input is changed from
   //--- its default, but cheap to guard outright.
   if(period <= 0 || n < period) return;
   for(int i = period - 1; i < n; i++)
     {
      double s = 0.0;
      for(int j = i - period + 1; j <= i; j++) s += c[j];
      double m = s / period;
      double ss = 0.0;
      for(int j = i - period + 1; j <= i; j++) ss += (c[j] - m) * (c[j] - m);
      double sd = MathSqrt(ss / period);
      mid[i]   = m;
      upper[i] = m + dev * sd;
      lower[i] = m - dev * sd;
     }
  }

//+------------------------------------------------------------------+
//| v2.19: shared zone-rectangle drawing for FVG + Liquidity. Lightly   |
//| shaded, not a solid block - OBJPROP_BACK=true draws it BEHIND the   |
//| candles (MT5 has no real alpha transparency on a rectangle fill,    |
//| this is the closest native approximation), and the caller passes a |
//| dim/dark colour, never a bright one. Right edge (t2) is updated     |
//| every call while the zone is active, so it visually grows forward   |
//| with time; removed entirely (ObjectDelete, not just hidden) the     |
//| moment the zone is no longer valid - see ProcessZoneBar() below.    |
//+------------------------------------------------------------------+
void DrawZoneRect(const string nm, const datetime t1, const datetime t2, const double top,
                   const double bottom, const color col)
  {
   if(ObjectFind(0, nm) < 0)
     {
      if(!ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, top, t2, bottom))
        {
         PrintFormat("TradePanel_EA: ObjectCreate FAILED for zone %s - error %d", nm, GetLastError());
         return;
        }
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, true);
      ObjectSetInteger(0, nm, OBJPROP_FILL, true);
      ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
     }
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectMove(0, nm, 0, t1, top);
   ObjectMove(0, nm, 1, t2, bottom);
  }

//+------------------------------------------------------------------+
//| v2.19: the one rule both zone overlays share - "price comes back to |
//| those levels to reject them". A zone is only ever touched, then     |
//| resolved ONE of two ways on the very bar that resolves it:          |
//|  - REJECTED: price wicks INTO the zone but CLOSES back out the way  |
//|    it came (support: low dips into the zone, close ends back above  |
//|    it; resistance: mirror) - this IS the buy/sell signal, and the   |
//|    zone is spent (removed) immediately after firing it.             |
//|  - INVALIDATED: price CLOSES fully through the zone (support:       |
//|    close ends below it; resistance: mirror) - no signal, the zone   |
//|    simply no longer means anything and is removed.                  |
//| A bar that only wicks in without closing cleanly either way leaves  |
//| the zone active/untouched-by-this-function - still being tested.    |
//+------------------------------------------------------------------+
void ProcessZoneBar(const SigZone &z, const double cBar, const double hBar, const double lBar,
                     bool &reject, bool &invalidate)
  {
   reject = false; invalidate = false;
   if(!z.active) return;
   if(z.bullish)
     {
      if(lBar > z.top) return;         // hasn't even reached the zone yet
      if(cBar < z.bottom) invalidate = true;
      else if(cBar > z.top) reject = true;
     }
   else
     {
      if(hBar < z.bottom) return;
      if(cBar > z.top) invalidate = true;
      else if(cBar < z.bottom) reject = true;
     }
  }

//+------------------------------------------------------------------+
//| Push notification + Experts-log line + sound, shared by both the   |
//| early zone-entry alert and the confirmed-signal alert below.       |
//| SendNotification() needs push notifications enabled AND a          |
//| MetaQuotes ID set in Tools->Options->Notifications in the terminal |
//| - it fails silently (returns false, logged) otherwise; this does   |
//| NOT retry or warn beyond the one log line, so check that setup if  |
//| no push ever arrives. PlaySound() needs InpSigSoundFile to exist   |
//| in the terminal's Sounds folder (terminal_data_folder\Sounds\).    |
//+------------------------------------------------------------------+
void FireSigAlert(const string msg)
  {
   if(!SendNotification(msg))
      Print("StochSignal: push notification FAILED (check Tools->Options->Notifications has",
            " 'Enable Push Notifications' checked and a MetaQuotes ID set) - ", msg);
   else
      Print("StochSignal: ", msg);
   if(StringLen(InpSigSoundFile) > 0) PlaySound(InpSigSoundFile);
  }


//+------------------------------------------------------------------+
//| v1.47: EMA21/50 crossover overlay. Entry = a fresh EMA21/50 cross,  |
//| only while flat (no new entry until the previous one has closed -   |
//| matches ema21_50_pure_crossover_test.py exactly). Exit = the NEXT    |
//| opposite EMA21/50 cross - NOT a faster EMA21-touch exit, which was   |
//| tested and found WORSE (ema21_50_crossover_fast_exit_test.py). A     |
//| single bar can both close the old position and open the new one     |
//| (the same cross that ends one trend starts the next), same as the   |
//| Python reference. The stop/target lines drawn on entry are visual   |
//| REFERENCE ONLY (per the input comments) - the validated exit is the |
//| next opposite cross, not either of those levels.                    |
//+------------------------------------------------------------------+
void ComputeEmaCrossSignals(const bool backfill)
  {
   int minBars = InpMA50 + InpEmaCrossSwingBars + 5;
   int available = Bars(_Symbol, PERIOD_CURRENT) - 1;
   //--- v2.24 FIX: this overlay (pre-existing before this session) was
   //--- always uncapped on backfill like every overlay here except FVG/
   //--- Liquidity (capped v2.21) and Divergence/BB (capped v2.23) - on
   //--- its own this was apparently tolerable, but stacked together with
   //--- four new overlays all doing their own full/capped scans in the
   //--- same OnInit() call, the combined synchronous cost was still
   //--- enough to hang attach ("mt5 still hanging" after v2.23). Capped
   //--- the same way as the others - the signal/trend state this overlay
   //--- needs only requires a bounded recent window, not the entire
   //--- chart history, to warm up correctly.
   int sigDrawBarsCap = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int total = backfill ? MathMin(available, minBars + sigDrawBarsCap + 200) : MathMin(available, minBars + 500);
   if(total < minBars) return;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 1, total, r);
   if(n < minBars) return;

   double c[], h[], l[];
   ArrayResize(c, n); ArrayResize(h, n); ArrayResize(l, n);
   for(int i = 0; i < n; i++) { c[i] = r[i].close; h[i] = r[i].high; l[i] = r[i].low; }

   double e21[], e50[];
   SigEMA(c, n, InpMA21, e21);
   SigEMA(c, n, InpMA50, e50);
   double atr[];
   SigATR(h, l, c, n, 14, atr);

   int perSec = PeriodSeconds(PERIOD_CURRENT);
   int from = minBars;
   if(!backfill)
     {
      for(int p = n - 1; p >= minBars; p--)
        {
         if(r[p].time <= g_emaxLastProcessedBar) break;
         from = p;
        }
     }
   int sigDrawBars = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int drawFrom = backfill ? MathMax(from, n - sigDrawBars) : from;

   int lastDir, posDir;
   string lastArr, lastSl, lastTp;
   double lastMarkerPrice;
   datetime lastMarkerTime;
   double runMaxGap;
   int    declineCount;
   bool   weakenFired;
   int    pendingDir;
   int    pendingBarsElapsed;
   if(backfill)
     {
      lastDir = 0; posDir = 0; lastArr = ""; lastSl = ""; lastTp = "";
      lastMarkerPrice = 0.0; lastMarkerTime = 0;
      runMaxGap = 0.0; declineCount = 0; weakenFired = false;
      pendingDir = 0; pendingBarsElapsed = 0;
     }
   else
     {
      lastDir = g_emaxLastDir; posDir = g_emaxPosDir;
      lastArr = g_emaxLastArr; lastSl = g_emaxLastSl; lastTp = g_emaxLastTp;
      lastMarkerPrice = g_emaxLastMarkerPrice; lastMarkerTime = g_emaxLastMarkerTime;
      runMaxGap = g_emaxRunMaxGap; declineCount = g_emaxDeclineCount; weakenFired = g_emaxWeakenFired;
      pendingDir = g_emaxPendingDir; pendingBarsElapsed = g_emaxPendingBarsElapsed;
     }

   for(int i = from; i < n; i++)
     {
      if(e21[i] == SIG_NA || e50[i] == SIG_NA || e21[i - 1] == SIG_NA || e50[i - 1] == SIG_NA) continue;
      bool draw = (i >= drawFrom);
      double offEntry = (atr[i] == SIG_NA) ? 0.0 : InpEmaCrossArrowOffsetATR * atr[i];
      double offExit  = (atr[i] == SIG_NA) ? 0.0 : InpEmaCrossExitOffsetATR  * atr[i];

      bool crossUp   = e21[i - 1] <= e50[i - 1] && e21[i] > e50[i];
      bool crossDown = e21[i - 1] >= e50[i - 1] && e21[i] < e50[i];
      int dir = crossUp ? 1 : (crossDown ? -1 : 0);

      int prevPosDir = posDir;
      bool entryFiredThisBar = false;

      //--- EXIT: an opposite cross closes whatever position the ENTRY block
      //--- below opened - the validated exit, held all the way to here.
      if(dir != 0 && prevPosDir != 0 && dir != prevPosDir)
        {
         if(draw)
           {
            datetime t = r[i].time;
            string exId = g_emax + "exit_" + IntegerToString((long)t);
            bool wasLong = prevPosDir > 0;
            double dotPrice = wasLong ? h[i] + offExit : l[i] - offExit;
            double minGapExit = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
            dotPrice = NudgeAwayFromLastMarker(dotPrice, t, !wasLong, lastMarkerPrice, lastMarkerTime, minGapExit);
            dotPrice = NudgeClearOfOtherOverlays(dotPrice, t, !wasLong, minGapExit, exId);
            lastMarkerPrice = dotPrice; lastMarkerTime = t;
            bool exitWasNew = (ObjectFind(0, exId) < 0);   // v2.15 FIX - see Rejection overlay's own comment
            DrawEmaCrossDot(exId, t, dotPrice, wasLong);
            PrintFormat("EmaCrossSignal LOG: %s EXIT-%s @ %s  E21=%s E50=%s (closing posDir %d -> 0)",
                        TimeToString(t, TIME_DATE | TIME_MINUTES), wasLong ? "LONG" : "SHORT",
                        DoubleToString(c[i], _Digits), DoubleToString(e21[i], _Digits),
                        DoubleToString(e50[i], _Digits), prevPosDir);
            if(!backfill && exitWasNew && InpEmaCrossAlert)
              {
               string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
               FireSigAlert(StringFormat("%s %s: EMA21/50 cross EXIT-%s PRINTED (held to this opposite cross) - "
                                          "chart overlay only, does not place/modify/close anything",
                                          _Symbol, tf, wasLong ? "LONG" : "SHORT"));
              }
           }
         posDir = 0; lastArr = ""; lastSl = ""; lastTp = "";
        }

      //--- v2.01: confirmation-bars entry filter. A cross starts a pending
      //--- countdown rather than entering immediately; entryDir only gets
      //--- set once the countdown reaches InpEmaConfirmBars AND price is
      //--- still past EMA50 in the pending direction on that bar (a one-bar
      //--- fakeout reversal cancels it). InpEmaConfirmBars=0 reproduces the
      //--- old immediate-entry behavior exactly.
      int entryDir = 0;
      if(posDir == 0)
        {
         if(pendingDir != 0)
           {
            pendingBarsElapsed++;
            if(pendingBarsElapsed >= InpEmaConfirmBars)
              {
               bool stillOk = (pendingDir > 0) ? (c[i] > e50[i]) : (c[i] < e50[i]);
               if(stillOk) entryDir = pendingDir;
               pendingDir = 0; pendingBarsElapsed = 0;
              }
           }
         if(dir != 0)
           {
            pendingDir = dir; pendingBarsElapsed = 0;
           }
        }

      //--- ENTRY: only while flat - matches the validated construction
      //--- exactly (no new entry until the previous one has closed above),
      //--- gated by the confirmation countdown above (entryDir, not dir)
      if(entryDir != 0 && posDir == 0)
        {
         int dir = entryDir;
         double swing = (dir > 0) ? l[i] : h[i];
         for(int j = i - InpEmaCrossSwingBars + 1; j < i; j++)
            swing = (dir > 0) ? MathMin(swing, l[j]) : MathMax(swing, h[j]);
         double risk = dir * (c[i] - swing);
         if(risk > 0.0)
           {
            posDir = dir;
            lastDir = dir;
            entryFiredThisBar = true;
            if(draw)
              {
               double stop = swing;
               double tp   = c[i] + dir * InpEmaCrossRR * risk;
               datetime t = r[i].time;
               string id = IntegerToString((long)t);
               bool isBuy = dir > 0;
               lastArr = g_emax + "arr_" + id;
               lastSl  = g_emax + "sl_" + id;
               lastTp  = g_emax + "tp_" + id;
               double entryPrice = isBuy ? l[i] - offEntry : h[i] + offEntry;
               double minGap = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
               entryPrice = NudgeAwayFromLastMarker(entryPrice, t, !isBuy, lastMarkerPrice, lastMarkerTime, minGap);
               entryPrice = NudgeClearOfOtherOverlays(entryPrice, t, !isBuy, minGap, lastArr);
               entryPrice = NudgeClearOfMALine(entryPrice, e21[i], !isBuy, minGap);
               entryPrice = NudgeClearOfMALine(entryPrice, e50[i], !isBuy, minGap);
               lastMarkerPrice = entryPrice; lastMarkerTime = t;
               bool entryWasNew = (ObjectFind(0, lastArr) < 0);   // v2.15 FIX
               DrawEmaCrossArrow(lastArr, t, entryPrice, isBuy);
               DrawSigLevel(lastSl, t, t + InpEmaCrossLineBars * perSec, stop, InpEmaCrossStopCol, STYLE_SOLID,
                            "EMA-cross SL: recent " + IntegerToString(InpEmaCrossSwingBars) + "-bar swing (reference only - validated exit is the next opposite EMA cross)");
               //--- v2.20 FIX: TP line removed per direct request ("remove all
               //--- the RR lines take profit lines, leave the swing stop loss
               //--- lines") - SL line above is the one being kept
               PrintFormat("EmaCrossSignal LOG: %s ENTRY %s @ %s  E21=%s E50=%s  posDir->%d",
                           TimeToString(t, TIME_DATE | TIME_MINUTES), isBuy ? "BUY" : "SELL",
                           DoubleToString(c[i], _Digits), DoubleToString(e21[i], _Digits),
                           DoubleToString(e50[i], _Digits), posDir);
               if(!backfill && entryWasNew && InpEmaCrossAlert)
                 {
                  string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
                  FireSigAlert(StringFormat("%s %s: EMA21/50 cross %s PRINTED (validated construction, hold to "
                                             "next opposite cross) - chart overlay only, does not place/modify/close anything",
                                             _Symbol, tf, isBuy ? "BUY" : "SELL"));
                 }
              }
           }
        }

      //--- v2.0: "trend weakening" check - runs on EVERY bar while a
      //--- position from the entry block above is still open (posDir!=0),
      //--- not just on cross bars. Tracks the gap's own running peak
      //--- WITHIN this open run; a fresh entry this bar resets tracking.
      if(posDir != 0)
        {
         double gap = MathAbs(e21[i] - e50[i]);
         if(entryFiredThisBar)
           {
            runMaxGap = gap; declineCount = 0; weakenFired = false;
           }
         else
           {
            if(gap > runMaxGap) { runMaxGap = gap; declineCount = 0; }
            else if(gap < runMaxGap) declineCount++;
            if(!weakenFired && declineCount >= InpEmaWeakenConfirmBars)
              {
               weakenFired = true;
               if(draw && InpShowEmaWeakenSignals)
                 {
                  bool wasLong = posDir > 0;
                  double offWeaken = (atr[i] == SIG_NA) ? 0.0 : InpEmaWeakenOffsetATR * atr[i];
                  datetime t = r[i].time;
                  string wkId = g_emax + "weak_" + IntegerToString((long)t);
                  double wkPrice = wasLong ? h[i] + offWeaken : l[i] - offWeaken;
                  double minGapWk = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
                  wkPrice = NudgeAwayFromLastMarker(wkPrice, t, !wasLong, lastMarkerPrice, lastMarkerTime, minGapWk);
                  wkPrice = NudgeClearOfOtherOverlays(wkPrice, t, !wasLong, minGapWk, wkId);
                  lastMarkerPrice = wkPrice; lastMarkerTime = t;
                  bool weakWasNew = (ObjectFind(0, wkId) < 0);   // v2.15 FIX
                  DrawEmaWeakenMarker(wkId, t, wkPrice, wasLong);
                  PrintFormat("EmaWeakenSignal LOG: %s WEAKENING in %s run @ %s  gap=%s (peak was %s, %d declining bars)",
                              TimeToString(t, TIME_DATE | TIME_MINUTES), wasLong ? "LONG" : "SHORT",
                              DoubleToString(c[i], _Digits), DoubleToString(gap, _Digits),
                              DoubleToString(runMaxGap, _Digits), declineCount);
                  if(!backfill && weakWasNew && InpEmaWeakenAlert)
                    {
                     string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
                     FireSigAlert(StringFormat("%s %s: EMA21/50 gap WEAKENING in the %s run (21EMA losing its "
                                                "angle) - not an exit, just a caution, chart overlay only",
                                                _Symbol, tf, wasLong ? "LONG" : "SHORT"));
                    }
                 }
              }
           }
        }
      else
        {
         runMaxGap = 0.0; declineCount = 0; weakenFired = false;
        }
     }

   g_emaxLastDir = lastDir; g_emaxPosDir = posDir;
   g_emaxLastArr = lastArr; g_emaxLastSl = lastSl; g_emaxLastTp = lastTp;
   g_emaxLastProcessedBar = r[n - 1].time;
   g_emaxLastMarkerPrice = lastMarkerPrice; g_emaxLastMarkerTime = lastMarkerTime;
   g_emaxRunMaxGap = runMaxGap; g_emaxDeclineCount = declineCount; g_emaxWeakenFired = weakenFired;
   g_emaxPendingDir = pendingDir; g_emaxPendingBarsElapsed = pendingBarsElapsed;
  }

//--- v2.14: the EMA-cross overlay's own rolling-cap purge
//--- (PurgeOldEmaCrossObjects) is now part of HousekeepOldObjects().

//+------------------------------------------------------------------+
//| Full wipe + backfill for the EMA-cross overlay - same reasoning as   |
//| ResyncStochSignals() above.                                          |
//+------------------------------------------------------------------+
void ResyncEmaCrossSignals()
  {
   ObjectsDeleteAll(0, g_emax);
   g_emaxPeriod = (ENUM_TIMEFRAMES)_Period;
   g_emaxLastDir = 0; g_emaxPosDir = 0;
   g_emaxLastArr = ""; g_emaxLastSl = ""; g_emaxLastTp = "";
   g_emaxLastProcessedBar = 0;
   g_emaxLastMarkerPrice = 0.0; g_emaxLastMarkerTime = 0;
   g_emaxRunMaxGap = 0.0; g_emaxDeclineCount = 0; g_emaxWeakenFired = false;
   g_emaxPendingDir = 0; g_emaxPendingBarsElapsed = 0;
   if(InpShowEmaCrossSignals) ComputeEmaCrossSignals(true);
  }

//+------------------------------------------------------------------+
//| v2.02: textbook %K/%D stochastic, extended with a price-mode switch |
//| (High/Low range vs Close/Close range) on top of the original three- |
//| way slowing-method switch. Shared by the Stochastic overlay and the |
//| Rejection overlay (each calls this with its own settings).          |
//+------------------------------------------------------------------+
void SigClassicStoch(const double &h[], const double &l[], const double &c[], const int n,
                     const int kp, const int slow, const int dp, double &k[], double &d[],
                     const ENUM_SIG_STOCH_METHOD method, const ENUM_SIG_STOCH_PRICE priceMode)
  {
   ArrayResize(k, n); ArrayInitialize(k, SIG_NA);
   ArrayResize(d, n); ArrayInitialize(d, SIG_NA);
   double num[], den[], rawK[];
   ArrayResize(num, n); ArrayResize(den, n); ArrayResize(rawK, n);
   ArrayInitialize(num, 0.0); ArrayInitialize(den, 0.0); ArrayInitialize(rawK, 0.0);
   for(int i = kp - 1; i < n; i++)
     {
      double lo, hi;
      if(priceMode == SIG_STOCH_CLOSECLOSE)
        {
         lo = c[i]; hi = c[i];
         for(int j = i - kp + 1; j < i; j++) { if(c[j] < lo) lo = c[j]; if(c[j] > hi) hi = c[j]; }
        }
      else
        {
         lo = l[i]; hi = h[i];
         for(int j = i - kp + 1; j < i; j++) { if(l[j] < lo) lo = l[j]; if(h[j] > hi) hi = h[j]; }
        }
      num[i] = c[i] - lo;
      den[i] = hi - lo;
      rawK[i] = (den[i] > 0.0) ? 100.0 * num[i] / den[i] : 100.0;
     }
   int kStart = kp + slow - 2;
   if(method == SIG_STOCH_SUM)
     {
      for(int i = kStart; i < n; i++)
        {
         double sn = 0.0, sd = 0.0;
         for(int j = i - slow + 1; j <= i; j++) { sn += num[j]; sd += den[j]; }
         k[i] = (sd > 0.0) ? 100.0 * sn / sd : 100.0;
        }
     }
   else if(method == SIG_STOCH_SMA)
     {
      for(int i = kStart; i < n; i++)
        {
         double s = 0.0;
         for(int j = i - slow + 1; j <= i; j++) s += rawK[j];
         k[i] = s / slow;
        }
     }
   else // SIG_STOCH_SMOOTHED
     {
      double seed = 0.0;
      for(int j = kStart - slow + 1; j <= kStart; j++) seed += rawK[j];
      k[kStart] = seed / slow;
      for(int i = kStart + 1; i < n; i++)
         k[i] = (k[i - 1] * (slow - 1) + rawK[i]) / slow;
     }
   int dStart = kp + slow + dp - 3;
   if(method == SIG_STOCH_SMOOTHED)
     {
      double seed = 0.0;
      for(int j = dStart - dp + 1; j <= dStart; j++) seed += k[j];
      d[dStart] = seed / dp;
      for(int i = dStart + 1; i < n; i++)
         d[i] = (d[i - 1] * (dp - 1) + k[i]) / dp;
     }
   else
     {
      for(int i = dStart; i < n; i++)
        {
         double s = 0.0;
         for(int j = i - dp + 1; j <= i; j++) s += k[j];
         d[i] = s / dp;
        }
     }
  }

void DrawStochArrow(const string nm, const datetime t, const double price, const bool isBuy)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, isBuy ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, isBuy ? InpStochBuyCol : InpStochSellCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpStochArrowSize);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, isBuy ? "Stoch Buy" : "Stoch Sell");
  }

//+------------------------------------------------------------------+
//| v2.02: Stochastic cross overlay (re-added by request) - %K/%D cross |
//| WITHIN the extreme zone (InpStochZoneLow/High, default 15/85). No   |
//| trend filter by design (same as the original baseline construction |
//| this replaces) - UNVALIDATED, visual only.                          |
//+------------------------------------------------------------------+
void ComputeStochSignals(const bool backfill)
  {
   int minBars = InpStochKPeriod + InpStochSlowing + InpStochDPeriod + InpStochSwingBars;
   int available = Bars(_Symbol, PERIOD_CURRENT) - 1;
   //--- v2.24 FIX: this overlay (pre-existing before this session) was
   //--- always uncapped on backfill like every overlay here except FVG/
   //--- Liquidity (capped v2.21) and Divergence/BB (capped v2.23) - on
   //--- its own this was apparently tolerable, but stacked together with
   //--- four new overlays all doing their own full/capped scans in the
   //--- same OnInit() call, the combined synchronous cost was still
   //--- enough to hang attach ("mt5 still hanging" after v2.23). Capped
   //--- the same way as the others - the signal/trend state this overlay
   //--- needs only requires a bounded recent window, not the entire
   //--- chart history, to warm up correctly.
   int sigDrawBarsCap = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int total = backfill ? MathMin(available, minBars + sigDrawBarsCap + 200) : MathMin(available, minBars + 500);
   if(total < minBars) return;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 1, total, r);
   if(n < minBars) return;

   double c[], h[], l[];
   ArrayResize(c, n); ArrayResize(h, n); ArrayResize(l, n);
   for(int i = 0; i < n; i++) { c[i] = r[i].close; h[i] = r[i].high; l[i] = r[i].low; }

   double k[], d[];
   SigClassicStoch(h, l, c, n, InpStochKPeriod, InpStochSlowing, InpStochDPeriod, k, d, InpStochMethod, InpStochPriceMode);
   double atr[];
   SigATR(h, l, c, n, 14, atr);

   int perSec = PeriodSeconds(PERIOD_CURRENT);
   int from = minBars;
   if(!backfill)
     {
      for(int p = n - 1; p >= minBars; p--)
        {
         if(r[p].time <= g_sigLastProcessedBar) break;
         from = p;
        }
     }
   int sigDrawBars = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int drawFrom = backfill ? MathMax(from, n - sigDrawBars) : from;

   int lastDir;
   string lastArr, lastSl, lastTp;
   double lastMarkerPrice;
   datetime lastMarkerTime;
   if(backfill)
     {
      lastDir = 0; lastArr = ""; lastSl = ""; lastTp = "";
      lastMarkerPrice = 0.0; lastMarkerTime = 0;
     }
   else
     {
      lastDir = g_sigLastDir;
      lastArr = g_sigLastArr; lastSl = g_sigLastSl; lastTp = g_sigLastTp;
      lastMarkerPrice = g_sigLastMarkerPrice; lastMarkerTime = g_sigLastMarkerTime;
     }

   for(int i = from; i < n; i++)
     {
      bool draw = (i >= drawFrom);
      double offEntry = (atr[i] == SIG_NA) ? 0.0 : InpStochArrowOffsetATR * atr[i];
      if(k[i] == SIG_NA || d[i] == SIG_NA || k[i - 1] == SIG_NA || d[i - 1] == SIG_NA) continue;

      bool crossUp   = k[i - 1] <= d[i - 1] && k[i] > d[i];
      bool crossDown = k[i - 1] >= d[i - 1] && k[i] < d[i];

      double zoneTestVal = k[i];
      if(InpStochUseInterpCross && (crossUp || crossDown))
        {
         double diffPrev = k[i - 1] - d[i - 1];
         double diffCur  = k[i] - d[i];
         double denom = diffPrev - diffCur;
         if(MathAbs(denom) > 0.0000001)
           {
            double t = diffPrev / denom;
            if(t < 0.0) t = 0.0;
            if(t > 1.0) t = 1.0;
            zoneTestVal = k[i - 1] + t * (k[i] - k[i - 1]);
           }
        }
      int dir = 0;
      if(crossUp && zoneTestVal < InpStochZoneLow) dir = 1;
      else if(crossDown && zoneTestVal > InpStochZoneHigh) dir = -1;
      if(dir == 0) continue;

      double swing = (dir > 0) ? l[i] : h[i];
      for(int j = i - InpStochSwingBars + 1; j < i; j++)
         swing = (dir > 0) ? MathMin(swing, l[j]) : MathMax(swing, h[j]);
      double risk = dir * (c[i] - swing);
      if(risk <= 0.0) continue;

      if(draw)
        {
         if(!backfill && InpStochCrossAlert)
           {
            string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
            FireSigAlert(StringFormat("%s %s: Stoch cross-in-zone %s PRINTED (K=%.1f) - chart overlay only, "
                                       "UNVALIDATED, does not place/modify/close anything",
                                       _Symbol, tf, (dir > 0 ? "BUY" : "SELL"), k[i]));
           }
         if(dir == lastDir && lastArr != "")
           {
            ObjectDelete(0, lastArr);
            ObjectDelete(0, lastSl);
            ObjectDelete(0, lastTp);
           }
        }
      lastDir = dir;

      if(draw)
        {
         double stop = swing;
         double tp   = c[i] + dir * InpStochRR * risk;
         datetime t = r[i].time;
         string id = IntegerToString((long)t);
         bool isBuy = dir > 0;
         lastArr = g_sig + "arr_" + id;
         lastSl  = g_sig + "sl_" + id;
         lastTp  = g_sig + "tp_" + id;
         double entryPrice = isBuy ? r[i].low - offEntry : r[i].high + offEntry;
         double minGap = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
         entryPrice = NudgeAwayFromLastMarker(entryPrice, t, !isBuy, lastMarkerPrice, lastMarkerTime, minGap);
         entryPrice = NudgeClearOfOtherOverlays(entryPrice, t, !isBuy, minGap, lastArr);
         lastMarkerPrice = entryPrice; lastMarkerTime = t;
         DrawStochArrow(lastArr, t, entryPrice, isBuy);
         DrawSigLevel(lastSl, t, t + InpStochLineBars * perSec, stop, InpStochStopCol, STYLE_SOLID,
                      "Stoch SL: recent " + IntegerToString(InpStochSwingBars) + "-bar swing (unvalidated)");
         //--- v2.20 FIX: TP line removed per direct request - see EmaCross's own comment
        }
     }

   g_sigLastDir = lastDir;
   g_sigLastArr = lastArr; g_sigLastSl = lastSl; g_sigLastTp = lastTp;
   g_sigLastProcessedBar = r[n - 1].time;
   g_sigLastMarkerPrice = lastMarkerPrice; g_sigLastMarkerTime = lastMarkerTime;
  }

void ResyncStochSignals()
  {
   ObjectsDeleteAll(0, g_sig);
   g_sigPeriod = (ENUM_TIMEFRAMES)_Period;
   g_sigLastDir = 0; g_sigPosDir = 0;
   g_sigLastArr = ""; g_sigLastSl = ""; g_sigLastTp = "";
   g_sigLastProcessedBar = 0;
   g_sigLastMarkerPrice = 0.0; g_sigLastMarkerTime = 0;
   if(InpShowStochSignals) ComputeStochSignals(true);
  }

//+------------------------------------------------------------------+
//| v2.02: candlestick engulfing overlay (re-added by request) -        |
//| bullish/bearish engulfing where the pattern bar IS the N-bar swing  |
//| extreme. Validated on GOLD ONLY (p=0.0010) - Silver/BTC are NOT     |
//| real (p=0.8511/0.5564).                                             |
//+------------------------------------------------------------------+
void DrawCandleArrow(const string nm, const datetime t, const double price, const bool isBuy)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, isBuy ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, isBuy ? InpCdlBuyCol : InpCdlSellCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpCdlArrowSize);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, isBuy ? "Engulfing Buy" : "Engulfing Sell");
  }

void ComputeCandleSignals(const bool backfill)
  {
   int minBars = InpCdlSwingBars + 5;
   int available = Bars(_Symbol, PERIOD_CURRENT) - 1;
   //--- v2.24 FIX: this overlay (pre-existing before this session) was
   //--- always uncapped on backfill like every overlay here except FVG/
   //--- Liquidity (capped v2.21) and Divergence/BB (capped v2.23) - on
   //--- its own this was apparently tolerable, but stacked together with
   //--- four new overlays all doing their own full/capped scans in the
   //--- same OnInit() call, the combined synchronous cost was still
   //--- enough to hang attach ("mt5 still hanging" after v2.23). Capped
   //--- the same way as the others - the signal/trend state this overlay
   //--- needs only requires a bounded recent window, not the entire
   //--- chart history, to warm up correctly.
   int sigDrawBarsCap = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int total = backfill ? MathMin(available, minBars + sigDrawBarsCap + 200) : MathMin(available, minBars + 500);
   if(total < minBars) return;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 1, total, r);
   if(n < minBars) return;

   double c[], h[], l[], o[];
   ArrayResize(c, n); ArrayResize(h, n); ArrayResize(l, n); ArrayResize(o, n);
   for(int i = 0; i < n; i++) { c[i] = r[i].close; h[i] = r[i].high; l[i] = r[i].low; o[i] = r[i].open; }
   double atr[];
   SigATR(h, l, c, n, 14, atr);
   //--- v2.18 FIX: extra confirmation, per direct request - "the engulfing
   //--- buy and sell signals need extra confirmation... some are not worth
   //--- it because just after the engulfing candle price does not go in
   //--- that direction, its either too close to a moving average or on the
   //--- wrong side of the trend". Two filters, both default ON:
   //---  (1) InpCdlRequireTrend - a bullish engulfing only counts in an
   //---      uptrend (21EMA>50EMA), bearish only in a downtrend - an
   //---      engulfing candle fighting the prevailing trend is exactly the
   //---      "wrong side of the trend" case described.
   //---  (2) InpCdlMinMADistATR - the engulfing candle's close must sit at
   //---      least this many ATR away from BOTH the 21EMA and the 50EMA -
   //---      a signal printing right on top of a moving average is the
   //---      "too close to a moving average" case: that MA is right there
   //---      acting as support/resistance, which is exactly why price
   //---      stalls instead of continuing in the signalled direction.
   double e21[], e50[];
   SigEMA(c, n, InpMA21, e21);
   SigEMA(c, n, InpMA50, e50);

   int perSec = PeriodSeconds(PERIOD_CURRENT);
   int from = minBars;
   if(!backfill)
     {
      for(int p = n - 1; p >= minBars; p--)
        {
         if(r[p].time <= g_cdlLastProcessedBar) break;
         from = p;
        }
     }
   int sigDrawBars = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int drawFrom = backfill ? MathMax(from, n - sigDrawBars) : from;

   double lastMarkerPrice = backfill ? 0.0 : g_cdlLastMarkerPrice;
   datetime lastMarkerTime = backfill ? 0 : g_cdlLastMarkerTime;

   for(int i = from; i < n; i++)
     {
      if(i < InpCdlSwingBars) continue;
      bool draw = (i >= drawFrom);

      bool bearPrev = c[i - 1] < o[i - 1];
      bool bullCur  = c[i] > o[i];
      bool bullEngulf = bearPrev && bullCur && o[i] <= c[i - 1] && c[i] >= o[i - 1];
      bool bullPrev = c[i - 1] > o[i - 1];
      bool bearCur  = c[i] < o[i];
      bool bearEngulf = bullPrev && bearCur && o[i] >= c[i - 1] && c[i] <= o[i - 1];

      double swingLow = l[i], swingHigh = h[i];
      for(int j = i - InpCdlSwingBars; j < i; j++)
        {
         swingLow  = MathMin(swingLow, l[j]);
         swingHigh = MathMax(swingHigh, h[j]);
        }

      int dir = 0;
      if(bullEngulf && l[i] <= swingLow) dir = 1;
      else if(bearEngulf && h[i] >= swingHigh) dir = -1;
      if(dir == 0) continue;

      if(e21[i] != SIG_NA && e50[i] != SIG_NA)
        {
         if(InpCdlRequireTrend)
           {
            if(dir > 0 && e21[i] <= e50[i]) continue;   // bullish engulfing, but trend is down - skip
            if(dir < 0 && e21[i] >= e50[i]) continue;   // bearish engulfing, but trend is up - skip
           }
         if(InpCdlMinMADistATR > 0.0 && atr[i] != SIG_NA && atr[i] > 0.0)
           {
            double minDist = InpCdlMinMADistATR * atr[i];
            if(MathAbs(c[i] - e21[i]) < minDist || MathAbs(c[i] - e50[i]) < minDist) continue;
           }
        }

      double swing = (dir > 0) ? l[i] : h[i];
      double risk = dir * (c[i] - swing);
      if(risk <= 0.0) continue;

      if(draw)
        {
         double offEntry = (atr[i] == SIG_NA) ? 0.0 : InpCdlArrowOffsetATR * atr[i];
         double stop = swing;
         double tp   = c[i] + dir * InpCdlRR * risk;
         datetime t = r[i].time;
         string id = IntegerToString((long)t);
         bool isBuy = dir > 0;
         string arrNm = g_cdl + "arr_" + id;
         string slNm  = g_cdl + "sl_"  + id;
         string tpNm  = g_cdl + "tp_"  + id;
         double entryPrice = isBuy ? l[i] - offEntry : h[i] + offEntry;
         double minGap = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
         entryPrice = NudgeAwayFromLastMarker(entryPrice, t, !isBuy, lastMarkerPrice, lastMarkerTime, minGap);
         entryPrice = NudgeClearOfOtherOverlays(entryPrice, t, !isBuy, minGap, arrNm);
         entryPrice = NudgeClearOfMALine(entryPrice, e21[i], !isBuy, minGap);
         entryPrice = NudgeClearOfMALine(entryPrice, e50[i], !isBuy, minGap);
         lastMarkerPrice = entryPrice; lastMarkerTime = t;
         bool cdlWasNew = (ObjectFind(0, arrNm) < 0);   // v2.15 FIX
         DrawCandleArrow(arrNm, t, entryPrice, isBuy);
         DrawSigLevel(slNm, t, t + InpCdlLineBars * perSec, stop, InpCdlStopCol, STYLE_SOLID,
                      "Engulfing SL: " + IntegerToString(InpCdlSwingBars) + "-bar swing (validated GOLD only, p=0.0010)");
         //--- v2.20 FIX: TP line removed per direct request - see EmaCross's own comment
         if(!backfill && cdlWasNew && InpCdlAlert)
           {
            string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
            FireSigAlert(StringFormat("%s %s: Engulfing %s PRINTED (validated GOLD only, p=0.0010 - "
                                       "Silver/BTC NOT real) - chart overlay only, does not place/modify/close anything",
                                       _Symbol, tf, isBuy ? "BUY" : "SELL"));
           }
        }
     }

   g_cdlLastProcessedBar = r[n - 1].time;
   g_cdlLastMarkerPrice = lastMarkerPrice; g_cdlLastMarkerTime = lastMarkerTime;
  }

void ResyncCandleSignals()
  {
   ObjectsDeleteAll(0, g_cdl);
   g_cdlPeriod = (ENUM_TIMEFRAMES)_Period;
   g_cdlLastProcessedBar = 0;
   g_cdlLastMarkerPrice = 0.0; g_cdlLastMarkerTime = 0;
   if(InpShowCandleSignals) ComputeCandleSignals(true);
  }

void DrawDivArrow(const string nm, const datetime t, const double price, const bool isBuy, const bool regular)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, isBuy ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, t, price);
   color col = regular ? (isBuy ? InpDivRegBuyCol : InpDivRegSellCol) : (isBuy ? InpDivHidBuyCol : InpDivHidSellCol);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpDivArrowSize);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, (regular ? "Regular " : "Hidden ") + string(isBuy ? "Bullish" : "Bearish") +
                    " Divergence " + (isBuy ? "Buy" : "Sell") + " (unvalidated)");
  }

//+------------------------------------------------------------------+
//| v2.17: stochastic divergence overlay (NEW, per direct request).      |
//| REGULAR divergence = reversal: price makes a new swing extreme the   |
//| stochastic does NOT confirm (lower low in price / higher low in      |
//| stoch = regular bullish; higher high in price / lower high in stoch  |
//| = regular bearish). HIDDEN divergence = trend CONTINUATION: during a |
//| pullback, price moves LESS than the stochastic does (higher low in   |
//| price / lower low in stoch, only in an existing uptrend = hidden     |
//| bullish; lower high in price / higher high in stoch, only in an      |
//| existing downtrend = hidden bearish) - the trend filter (21 vs 50    |
//| EMA) only applies to the HIDDEN cases, since hidden divergence is    |
//| specifically a continuation-of-trend signal, not a standalone        |
//| reversal one like regular divergence is.                             |
//+------------------------------------------------------------------+
void ComputeDivSignals(const bool backfill)
  {
   int w = InpDivPivotWindow;
   int minBars = InpStochKPeriod + InpStochSlowing + InpStochDPeriod + 2 * w + 10;
   int available = Bars(_Symbol, PERIOD_CURRENT) - 1;
   //--- v2.23 FIX (Opus-found): this overlay is new this session and was
   //--- never given the same backfill cap as the older overlays always
   //--- relied on being cheap enough uncapped - unlike those, Divergence
   //--- has no reason to scan the ENTIRE chart history just to find the
   //--- single most recent pivot of each type leading into the draw
   //--- window. Capped to roughly the draw window plus enough warm-up
   //--- for the pivot-gap tolerance, shrinking the attach-time stall.
   int sigDrawBarsCap = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int total = backfill ? MathMin(available, minBars + sigDrawBarsCap + InpDivMaxPivotGapBars + 50)
                        : MathMin(available, minBars + 500);
   if(total < minBars) return;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 1, total, r);
   if(n < minBars) return;

   double c[], h[], l[];
   ArrayResize(c, n); ArrayResize(h, n); ArrayResize(l, n);
   for(int i = 0; i < n; i++) { c[i] = r[i].close; h[i] = r[i].high; l[i] = r[i].low; }

   double atr[];
   SigATR(h, l, c, n, 14, atr);
   double k[], d[];
   SigClassicStoch(h, l, c, n, InpStochKPeriod, InpStochSlowing, InpStochDPeriod, k, d, InpStochMethod, InpStochPriceMode);
   double e21[], e50[];
   SigEMA(c, n, InpMA21, e21);
   SigEMA(c, n, InpMA50, e50);

   int perSec = PeriodSeconds(PERIOD_CURRENT);
   int maxI = n - 1 - w;
   if(maxI < w) return;
   int from = w;
   if(!backfill)
     {
      for(int p = maxI; p >= w; p--)
        {
         if(r[p].time <= g_divLastProcessedBar) break;
         from = p;
        }
     }
   int sigDrawBars = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int drawFrom = backfill ? MathMax(from, n - sigDrawBars) : from;

   bool haveLow = backfill ? false : g_divHaveLow;
   datetime lowT = backfill ? 0 : g_divLowTime;
   double lowP = backfill ? 0.0 : g_divLowPrice, lowK = backfill ? 0.0 : g_divLowK;
   bool haveHigh = backfill ? false : g_divHaveHigh;
   datetime highT = backfill ? 0 : g_divHighTime;
   double highP = backfill ? 0.0 : g_divHighPrice, highK = backfill ? 0.0 : g_divHighK;
   double lastMarkerPrice = backfill ? 0.0 : g_divLastMarkerPrice;
   datetime lastMarkerTime = backfill ? 0 : g_divLastMarkerTime;

   for(int i = from; i <= maxI; i++)
     {
      if(k[i] == SIG_NA || atr[i] == SIG_NA || atr[i] <= 0.0 || e21[i] == SIG_NA || e50[i] == SIG_NA) continue;
      bool draw = (i >= drawFrom);
      datetime t_i = r[i].time;

      bool isPivotLow = true, isPivotHigh = true;
      for(int jx = 1; jx <= w; jx++)
        {
         if(l[i] > l[i - jx] || l[i] >= l[i + jx]) isPivotLow = false;
         if(h[i] < h[i - jx] || h[i] <= h[i + jx]) isPivotHigh = false;
         if(!isPivotLow && !isPivotHigh) break;
        }

      if(isPivotLow)
        {
         if(haveLow && (t_i - lowT) <= (datetime)InpDivMaxPivotGapBars * perSec && k[i] != SIG_NA && lowK != SIG_NA)
           {
            int dir = 0; bool regular = false;
            if(l[i] < lowP && k[i] > lowK) { dir = 1; regular = true; }
            else if(l[i] > lowP && k[i] < lowK && e21[i] > e50[i]) { dir = 1; regular = false; }
            if(dir != 0)
              {
               datetime lastAt = regular ? g_divLastRegBuyAt : g_divLastHidBuyAt;
               if(lastAt == 0 || (t_i - lastAt) >= (datetime)InpDivCooldownBars * perSec)
                 {
                  if(regular) g_divLastRegBuyAt = t_i; else g_divLastHidBuyAt = t_i;
                  if(draw)
                    {
                     string id = IntegerToString((long)t_i);
                     //--- v2.21 FIX (Opus-found): "buy"/"sell" added - a single bar CAN be
                     //--- both a confirmed pivot low and pivot high (an outside bar engulfing
                     //--- its whole fractal window), which would otherwise make this buy
                     //--- branch's name collide with the sell branch's for the same bar/kind
                     string nm = g_div + (regular ? "reg_buy_" : "hid_buy_") + id;
                     double offEntry = InpDivArrowOffsetATR * atr[i];
                     double minGap = InpSigMinMarkerGapATR * atr[i];
                     double entryPrice = l[i] - offEntry;
                     entryPrice = NudgeAwayFromLastMarker(entryPrice, t_i, false, lastMarkerPrice, lastMarkerTime, minGap);
                     entryPrice = NudgeClearOfOtherOverlays(entryPrice, t_i, false, minGap, nm);
                     entryPrice = NudgeClearOfMALine(entryPrice, e21[i], false, minGap);
                     entryPrice = NudgeClearOfMALine(entryPrice, e50[i], false, minGap);
                     lastMarkerPrice = entryPrice; lastMarkerTime = t_i;
                     bool wasNew = (ObjectFind(0, nm) < 0);
                     DrawDivArrow(nm, t_i, entryPrice, true, regular);

                     double swing = l[i];
                     for(int j = i - InpDivSwingBars + 1; j < i; j++)
                        if(j >= 0) swing = MathMin(swing, l[j]);
                     double risk = c[i] - swing;
                     if(risk > 0.0)
                       {
                        double tp = c[i] + InpDivRR * risk;
                        //--- v2.21 FIX (Opus-found): was g_div+"sl_"+id, shared by BOTH the
                        //--- buy and sell branches on the same bar - a bar that happened to
                        //--- be both a confirmed pivot low AND pivot high (rare, but possible
                        //--- on a single very-wide-range bar) would silently have its second
                        //--- SL line skipped (DrawSigLevel no-ops if the name already exists).
                        //--- Now derived from nm (already unique per reg/hid AND per bar).
                        DrawSigLevel(nm + "_sl", t_i, t_i + InpDivLineBars * perSec, swing, InpDivStopCol, STYLE_SOLID,
                                     (regular ? "Regular" : "Hidden") + string(" Div SL: recent ") +
                                     IntegerToString(InpDivSwingBars) + "-bar swing (unvalidated)");
                       }
                     if(!backfill && wasNew && InpDivAlert)
                       {
                        string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
                        FireSigAlert(StringFormat("%s %s: %s Bullish Divergence BUY PRINTED - UNVALIDATED, chart "
                                                   "overlay only", _Symbol, tf, regular ? "Regular" : "Hidden"));
                       }
                    }
                 }
              }
           }
         haveLow = true; lowT = t_i; lowP = l[i]; lowK = k[i];
        }

      if(isPivotHigh)
        {
         if(haveHigh && (t_i - highT) <= (datetime)InpDivMaxPivotGapBars * perSec && k[i] != SIG_NA && highK != SIG_NA)
           {
            int dir = 0; bool regular = false;
            if(h[i] > highP && k[i] < highK) { dir = -1; regular = true; }
            else if(h[i] < highP && k[i] > highK && e21[i] < e50[i]) { dir = -1; regular = false; }
            if(dir != 0)
              {
               datetime lastAt = regular ? g_divLastRegSellAt : g_divLastHidSellAt;
               if(lastAt == 0 || (t_i - lastAt) >= (datetime)InpDivCooldownBars * perSec)
                 {
                  if(regular) g_divLastRegSellAt = t_i; else g_divLastHidSellAt = t_i;
                  if(draw)
                    {
                     string id = IntegerToString((long)t_i);
                     string nm = g_div + (regular ? "reg_sell_" : "hid_sell_") + id;
                     double offEntry = InpDivArrowOffsetATR * atr[i];
                     double minGap = InpSigMinMarkerGapATR * atr[i];
                     double entryPrice = h[i] + offEntry;
                     entryPrice = NudgeAwayFromLastMarker(entryPrice, t_i, true, lastMarkerPrice, lastMarkerTime, minGap);
                     entryPrice = NudgeClearOfOtherOverlays(entryPrice, t_i, true, minGap, nm);
                     entryPrice = NudgeClearOfMALine(entryPrice, e21[i], true, minGap);
                     entryPrice = NudgeClearOfMALine(entryPrice, e50[i], true, minGap);
                     lastMarkerPrice = entryPrice; lastMarkerTime = t_i;
                     bool wasNew = (ObjectFind(0, nm) < 0);
                     DrawDivArrow(nm, t_i, entryPrice, false, regular);

                     double swing = h[i];
                     for(int j = i - InpDivSwingBars + 1; j < i; j++)
                        if(j >= 0) swing = MathMax(swing, h[j]);
                     double risk = swing - c[i];
                     if(risk > 0.0)
                       {
                        double tp = c[i] - InpDivRR * risk;
                        //--- v2.21 FIX (Opus-found): was g_div+"sl_"+id, shared by BOTH the
                        //--- buy and sell branches on the same bar - a bar that happened to
                        //--- be both a confirmed pivot low AND pivot high (rare, but possible
                        //--- on a single very-wide-range bar) would silently have its second
                        //--- SL line skipped (DrawSigLevel no-ops if the name already exists).
                        //--- Now derived from nm (already unique per reg/hid AND per bar).
                        DrawSigLevel(nm + "_sl", t_i, t_i + InpDivLineBars * perSec, swing, InpDivStopCol, STYLE_SOLID,
                                     (regular ? "Regular" : "Hidden") + string(" Div SL: recent ") +
                                     IntegerToString(InpDivSwingBars) + "-bar swing (unvalidated)");
                       }
                     if(!backfill && wasNew && InpDivAlert)
                       {
                        string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
                        FireSigAlert(StringFormat("%s %s: %s Bearish Divergence SELL PRINTED - UNVALIDATED, chart "
                                                   "overlay only", _Symbol, tf, regular ? "Regular" : "Hidden"));
                       }
                    }
                 }
              }
           }
         haveHigh = true; highT = t_i; highP = h[i]; highK = k[i];
        }
     }

   g_divLastProcessedBar = r[maxI].time;
   g_divHaveLow = haveLow; g_divLowTime = lowT; g_divLowPrice = lowP; g_divLowK = lowK;
   g_divHaveHigh = haveHigh; g_divHighTime = highT; g_divHighPrice = highP; g_divHighK = highK;
   g_divLastMarkerPrice = lastMarkerPrice; g_divLastMarkerTime = lastMarkerTime;
  }

void ResyncDivSignals()
  {
   ObjectsDeleteAll(0, g_div);
   g_divPeriod = (ENUM_TIMEFRAMES)_Period;
   g_divLastProcessedBar = 0;
   g_divLastMarkerPrice = 0.0; g_divLastMarkerTime = 0;
   g_divHaveLow = false; g_divLowTime = 0; g_divLowPrice = 0.0; g_divLowK = 0.0;
   g_divHaveHigh = false; g_divHighTime = 0; g_divHighPrice = 0.0; g_divHighK = 0.0;
   g_divLastRegBuyAt = 0; g_divLastRegSellAt = 0; g_divLastHidBuyAt = 0; g_divLastHidSellAt = 0;
   if(InpShowDivSignals) ComputeDivSignals(true);
  }

//+------------------------------------------------------------------+
void DrawBBArrow(const string nm, const datetime t, const double price, const bool isBuy)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, isBuy ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, isBuy ? InpBBBuyCol : InpBBSellCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpBBArrowSize);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, isBuy ? "BB Outer-Band Rejection Buy (unvalidated)" :
                    "BB Outer-Band Rejection Sell (unvalidated)");
  }

//+------------------------------------------------------------------+
//| v2.18: Bollinger outer-band rejection overlay (NEW, per direct       |
//| request + attached chart examples). SELL: a bar within the last      |
//| InpBBReentryLookback bars closed ABOVE the upper band (an             |
//| overextended move), and THIS bar closes back inside (<= upper band)  |
//| - the overextension is failing. BUY: mirror, a bar closed BELOW the  |
//| lower band, this bar closes back inside (>= lower band). Optional   |
//| InpBBRequireRejection additionally requires the re-entry bar itself  |
//| to show a rejection wick on the band side.                           |
//+------------------------------------------------------------------+
void ComputeBBSignals(const bool backfill)
  {
   int minBars = InpBBPeriod + InpBBReentryLookback + InpBBSwingBars + 10;
   int available = Bars(_Symbol, PERIOD_CURRENT) - 1;
   //--- v2.23 FIX (Opus-found): same reasoning as ComputeDivSignals' own
   //--- comment - new this session, never capped, no need to scan the
   //--- entire chart history for a Bollinger re-entry signal
   int sigDrawBarsCap = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int total = backfill ? MathMin(available, minBars + sigDrawBarsCap + 50) : MathMin(available, minBars + 500);
   if(total < minBars) return;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 1, total, r);
   if(n < minBars) return;

   double c[], h[], l[], o[];
   ArrayResize(c, n); ArrayResize(h, n); ArrayResize(l, n); ArrayResize(o, n);
   for(int i = 0; i < n; i++) { c[i] = r[i].close; h[i] = r[i].high; l[i] = r[i].low; o[i] = r[i].open; }
   double atr[];
   SigATR(h, l, c, n, 14, atr);
   double bbMid[], bbUpper[], bbLower[];
   SigBollinger(c, n, InpBBPeriod, InpBBDev, bbMid, bbUpper, bbLower);

   int perSec = PeriodSeconds(PERIOD_CURRENT);
   int from = minBars;
   if(!backfill)
     {
      for(int p = n - 1; p >= minBars; p--)
        {
         if(r[p].time <= g_bbLastProcessedBar) break;
         from = p;
        }
     }
   int sigDrawBars = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int drawFrom = backfill ? MathMax(from, n - sigDrawBars) : from;

   double lastMarkerPrice = backfill ? 0.0 : g_bbLastMarkerPrice;
   datetime lastMarkerTime = backfill ? 0 : g_bbLastMarkerTime;

   for(int i = from; i < n; i++)
     {
      if(bbUpper[i] == SIG_NA || bbLower[i] == SIG_NA) continue;
      bool draw = (i >= drawFrom);
      datetime t_i = r[i].time;

      int dir = 0;
      for(int j = MathMax(0, i - InpBBReentryLookback); j < i; j++)
        {
         if(bbUpper[j] == SIG_NA || bbLower[j] == SIG_NA) continue;
         if(c[j] > bbUpper[j] && c[i] <= bbUpper[i]) { dir = -1; }
         else if(c[j] < bbLower[j] && c[i] >= bbLower[i]) { dir = 1; }
        }
      if(dir == 0) continue;

      if(InpBBRequireRejection)
        {
         double range = h[i] - l[i];
         if(range <= 0.0) continue;
         bool rejOK = false;
         if(dir > 0)
           {
            double lowerWick = MathMin(o[i], c[i]) - l[i];
            rejOK = (c[i] > o[i]) && (lowerWick / range >= InpBBRejectionWickRatio);
           }
         else
           {
            double upperWick = h[i] - MathMax(o[i], c[i]);
            rejOK = (c[i] < o[i]) && (upperWick / range >= InpBBRejectionWickRatio);
           }
         if(!rejOK) continue;
        }

      datetime lastAt = (dir > 0) ? g_bbLastBuyAt : g_bbLastSellAt;
      if(lastAt != 0 && (t_i - lastAt) < (datetime)InpBBCooldownBars * perSec) continue;
      if(dir > 0) g_bbLastBuyAt = t_i; else g_bbLastSellAt = t_i;

      double swing = (dir > 0) ? l[i] : h[i];
      for(int j = i - InpBBSwingBars + 1; j < i; j++)
         if(j >= 0) swing = (dir > 0) ? MathMin(swing, l[j]) : MathMax(swing, h[j]);
      double risk = dir * (c[i] - swing);
      if(risk <= 0.0) continue;

      if(draw)
        {
         bool isBuy = dir > 0;
         double offEntry = (atr[i] == SIG_NA) ? 0.0 : InpBBArrowOffsetATR * atr[i];
         string id = IntegerToString((long)t_i);
         string nm = g_bb + "arr_" + id;
         double entryPrice = isBuy ? l[i] - offEntry : h[i] + offEntry;
         double minGap = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
         entryPrice = NudgeAwayFromLastMarker(entryPrice, t_i, !isBuy, lastMarkerPrice, lastMarkerTime, minGap);
         entryPrice = NudgeClearOfOtherOverlays(entryPrice, t_i, !isBuy, minGap, nm);
         lastMarkerPrice = entryPrice; lastMarkerTime = t_i;
         bool wasNew = (ObjectFind(0, nm) < 0);
         DrawBBArrow(nm, t_i, entryPrice, isBuy);

         double tp = c[i] + dir * InpBBRR * risk;
         DrawSigLevel(g_bb + "sl_" + id, t_i, t_i + InpBBLineBars * perSec, swing, InpBBStopCol, STYLE_SOLID,
                      "BB Outer-Band SL: recent " + IntegerToString(InpBBSwingBars) + "-bar swing (unvalidated)");
         //--- v2.20 FIX: TP line removed per direct request - see EmaCross's own comment
         if(!backfill && wasNew && InpBBAlert)
           {
            string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
            FireSigAlert(StringFormat("%s %s: BB Outer-Band Rejection %s PRINTED - UNVALIDATED, chart overlay only",
                                       _Symbol, tf, isBuy ? "BUY" : "SELL"));
           }
        }
     }

   g_bbLastProcessedBar = r[n - 1].time;
   g_bbLastMarkerPrice = lastMarkerPrice; g_bbLastMarkerTime = lastMarkerTime;
  }

void ResyncBBSignals()
  {
   ObjectsDeleteAll(0, g_bb);
   g_bbLastProcessedBar = 0;
   g_bbLastMarkerPrice = 0.0; g_bbLastMarkerTime = 0;
   g_bbLastBuyAt = 0; g_bbLastSellAt = 0;
   if(InpShowBBSignals) ComputeBBSignals(true);
  }

//+------------------------------------------------------------------+
void DrawZoneSignalArrow(const string nm, const datetime t, const double price, const bool isBuy,
                          const color buyCol, const color sellCol, const int arrowSize, const string tip)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, isBuy ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, isBuy ? buyCol : sellCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, arrowSize);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, tip);
  }

//+------------------------------------------------------------------+
//| v2.19: trims a zone array down to InpXMaxZones (drops the OLDEST    |
//| active zone - by startTime - when over cap) and drops any active    |
//| zone older than maxAgeDays that's never been touched. Keeps the     |
//| chart from accumulating zones indefinitely.                         |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| v2.21 FIX (Opus-found): an invalidated/spent zone was only ever    |
//| marked active=false and left sitting in the array forever - never  |
//| reclaimed, so over weeks of live running the array (and the O(bars |
//| x zones) per-tick scan cost) would grow without bound. Compacts    |
//| dead entries out after every call. Safe to reorder: rectName is    |
//| derived from the zone's own formation time, never from its array   |
//| index, so nothing depends on position staying fixed.               |
//+------------------------------------------------------------------+
void CompactZones(SigZone &zones[])
  {
   int n = ArraySize(zones);
   int w = 0;
   for(int k = 0; k < n; k++)
     {
      if(!zones[k].active) continue;
      if(w != k) zones[w] = zones[k];
      w++;
     }
   if(w != n) ArrayResize(zones, w);
  }

void PruneZones(SigZone &zones[], const int maxZones, const datetime ageCutoff)
  {
   //--- v2.25 FIX: a SPENT zone (reject already fired - see the caller's
   //--- own v2.25 comment) is left deliberately active==false but its
   //--- rectangle is deliberately NOT deleted at that point anymore, so
   //--- it stays visible as a record of what triggered the signal. That
   //--- means this age-cutoff pass has to check EVERY zone regardless of
   //--- active state now, not just active ones - otherwise a spent
   //--- zone's rectangle would never get deleted at all (CompactZones()
   //--- drops its array bookkeeping once inactive, but dropping the
   //--- bookkeeping is not the same as deleting the chart OBJECT) and
   //--- would leak on the chart forever instead of aging out with
   //--- everything else.
   for(int k = ArraySize(zones) - 1; k >= 0; k--)
     {
      if(ageCutoff != 0 && zones[k].startTime < ageCutoff)
        {
         ObjectDelete(0, zones[k].rectName);
         zones[k].active = false;
        }
     }
   while(maxZones > 0)
     {
      int activeCount = 0, oldest = -1;
      for(int k = 0; k < ArraySize(zones); k++)
        {
         if(!zones[k].active) continue;
         activeCount++;
         if(oldest < 0 || zones[k].startTime < zones[oldest].startTime) oldest = k;
        }
      if(activeCount <= maxZones || oldest < 0) break;
      ObjectDelete(0, zones[oldest].rectName);
      zones[oldest].active = false;
     }
  }

//+------------------------------------------------------------------+
//| v2.19: Fair Value Gap zones + rejection signals (NEW, per direct     |
//| request). Standard 3-candle imbalance: bullish if candle i's low is  |
//| above candle i-2's high (a gap price never traded through on the     |
//| way up); bearish mirror. Per direct request, "the fvg and liquidity  |
//| blocks must also give buy and sell signals when price comes back to  |
//| those levels to reject them" - handled generically by                |
//| ProcessZoneBar() above (touch-in, close-back-out = signal; close     |
//| fully through = invalidated), applied to every active zone on every  |
//| new bar BEFORE checking that same bar for a brand-new gap.           |
//+------------------------------------------------------------------+
void ComputeFvgSignals(const bool backfill)
  {
   int minBars = InpFvgSwingBars + 10;
   int available = Bars(_Symbol, PERIOD_CURRENT) - 1;
   //--- v2.21 FIX (Opus-found, CRITICAL): the backfill used to request
   //--- `available` - the ENTIRE chart history (often 100,000+ bars) -
   //--- with no cap, unlike every other overlay in this file (which all
   //--- cap their backfill draw window via InpSigDrawDays). Combined with
   //--- an O(bars x zones) inner scan (every bar re-checks every zone
   //--- ever created) and zero compaction of spent/invalidated zones,
   //--- this measured out to ~1.1 BILLION inner-loop iterations and tens
   //--- of thousands of queued synchronous chart-object calls on a
   //--- 100k-bar GOLD M5 history - taking MINUTES inside OnInit, which
   //--- runs BEFORE BuildPanel()/the MA-VWAP backfill. Net effect: no
   //--- panel, no MAs, no VWAP, and when the user removed the EA while it
   //--- was still stuck, MT5 force-killed it without ever calling
   //--- OnDeinit, leaving every object behind. Fixed at the root: the
   //--- backfill SCAN WINDOW itself is now capped to roughly
   //--- InpFvgMaxAgeDays worth of bars (+ a startup margin) - anything
   //--- older would be pruned by PruneZones() within one tick anyway, so
   //--- scanning further back was always wasted work, not just slow.
   int maxAgeBars = (InpFvgMaxAgeDays > 0)
                     ? (int)((long)InpFvgMaxAgeDays * 86400 / PeriodSeconds(PERIOD_CURRENT)) + minBars + 50
                     : available;
   int total = backfill ? MathMin(available, maxAgeBars) : MathMin(available, minBars + 500);
   if(total < minBars) return;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 1, total, r);
   if(n < minBars) return;

   double c[], h[], l[];
   ArrayResize(c, n); ArrayResize(h, n); ArrayResize(l, n);
   for(int i = 0; i < n; i++) { c[i] = r[i].close; h[i] = r[i].high; l[i] = r[i].low; }
   double atr[];
   SigATR(h, l, c, n, 14, atr);

   int perSec = PeriodSeconds(PERIOD_CURRENT);
   int from = minBars;
   if(!backfill)
     {
      for(int p = n - 1; p >= minBars; p--)
        {
         if(r[p].time <= g_fvgLastProcessedBar) break;
         from = p;
        }
     }
   //--- v2.21 FIX: also gate actual object creation (arrow/SL/alert) to
   //--- the last InpSigDrawDays, same convention as every other overlay -
   //--- the zone itself still forms/tracks across the whole scan window
   //--- above, just doesn't draw/alert for ancient history
   int sigDrawBars = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int drawFrom = backfill ? MathMax(from, n - sigDrawBars) : from;
   double lastMarkerPrice = backfill ? 0.0 : g_fvgLastMarkerPrice;
   datetime lastMarkerTime = backfill ? 0 : g_fvgLastMarkerTime;

   for(int i = MathMax(from, 2); i < n; i++)
     {
      datetime t_i = r[i].time;
      bool draw = (i >= drawFrom);

      //--- process existing zones against THIS bar first - a zone can
      //--- only ever be touched by a bar AFTER it was formed
      for(int zi = 0; zi < ArraySize(g_fvgZones); zi++)
        {
         if(!g_fvgZones[zi].active) continue;
         bool reject, invalidate;
         ProcessZoneBar(g_fvgZones[zi], c[i], h[i], l[i], reject, invalidate);
         if(invalidate)
           {
            ObjectDelete(0, g_fvgZones[zi].rectName);
            g_fvgZones[zi].active = false;
           }
         else if(reject)
           {
            bool isBuy = g_fvgZones[zi].bullish;
            datetime lastAt = isBuy ? g_fvgLastBuyAt : g_fvgLastSellAt;
            if(lastAt == 0 || (t_i - lastAt) >= (datetime)InpFvgCooldownBars * perSec)
              {
               if(isBuy) g_fvgLastBuyAt = t_i; else g_fvgLastSellAt = t_i;
               if(draw)
                 {
                  double offEntry = (atr[i] == SIG_NA) ? 0.0 : InpFvgArrowOffsetATR * atr[i];
                  //--- v2.23 FIX (Opus-found): was id = t_i + "_" + zi (the zone's
                  //--- ARRAY INDEX) - CompactZones() reshuffles indices every call,
                  //--- so the same zone's signal could get a different id on a
                  //--- replay (resync, or the "no new bar found" fallback that
                  //--- reprocesses ~500 bars), producing a duplicate arrow/SL/alert
                  //--- instead of being recognised as already-drawn. g_fvgZones[zi]
                  //--- .rectName is derived from the zone's own formation time, not
                  //--- its position, so it's stable across compaction.
                  string id = g_fvgZones[zi].rectName + "_" + IntegerToString((long)t_i);
                  string nm = g_fvgSig + "arr_" + id;
                  double entryPrice = isBuy ? l[i] - offEntry : h[i] + offEntry;
                  double minGap = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
                  entryPrice = NudgeAwayFromLastMarker(entryPrice, t_i, !isBuy, lastMarkerPrice, lastMarkerTime, minGap);
                  entryPrice = NudgeClearOfOtherOverlays(entryPrice, t_i, !isBuy, minGap, nm);
                  lastMarkerPrice = entryPrice; lastMarkerTime = t_i;
                  bool wasNew = (ObjectFind(0, nm) < 0);
                  DrawZoneSignalArrow(nm, t_i, entryPrice, isBuy, InpFvgArrowBuyCol, InpFvgArrowSellCol,
                                       InpFvgArrowSize, isBuy ? "FVG Rejection Buy (unvalidated)" :
                                       "FVG Rejection Sell (unvalidated)");
                  //--- v2.25: per direct request - "lets have the blocks change
                  //--- colour if a signal is triggered off them" - only recolors
                  //--- when a signal actually drew (not when cooldown silently
                  //--- blocked one), frozen at its current extent since the zone
                  //--- is about to be deactivated right after this.
                  DrawZoneRect(g_fvgZones[zi].rectName, g_fvgZones[zi].startTime, t_i,
                               g_fvgZones[zi].top, g_fvgZones[zi].bottom, InpFvgSpentCol);

                  double swing = isBuy ? l[i] : h[i];
                  for(int j = i - InpFvgSwingBars + 1; j < i; j++)
                     if(j >= 0) swing = isBuy ? MathMin(swing, l[j]) : MathMax(swing, h[j]);
                  double risk = isBuy ? (c[i] - swing) : (swing - c[i]);
                  if(risk > 0.0)
                    {
                     DrawSigLevel(g_fvgSig + "sl_" + id, t_i, t_i + InpFvgLineBars * perSec, swing, InpFvgStopCol, STYLE_SOLID,
                                  "FVG SL: recent " + IntegerToString(InpFvgSwingBars) + "-bar swing (unvalidated)");
                    }
                  if(!backfill && wasNew && InpFvgAlert)
                    {
                     string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
                     FireSigAlert(StringFormat("%s %s: FVG Rejection %s PRINTED - UNVALIDATED, chart overlay only",
                                                _Symbol, tf, isBuy ? "BUY" : "SELL"));
                    }
                 }
              }
            //--- v2.25 FIX - per direct request/report: "i just got a buy
            //--- signal for a fvg, but there was not gap on the chart...
            //--- futher down was one but not near the signal". Root cause:
            //--- this used to ObjectDelete the zone's rectangle in the SAME
            //--- step as drawing the signal arrow - the gap that actually
            //--- justified the signal was always already gone by the time
            //--- anyone looked at the chart, which is exactly backwards.
            //--- Deactivated (stops it being retested/re-signalled - it IS
            //--- "spent") but the rectangle itself is now left on the
            //--- chart as a static record of what triggered the signal -
            //--- it simply stops being extended further right once
            //--- inactive, and still ages out naturally via PruneZones'
            //--- InpFvgMaxAgeDays cutoff like everything else.
            g_fvgZones[zi].active = false;
           }
        }

      //--- NOW check this bar for a brand-new gap (3-candle: i-2, i-1, i)
      bool bullGap = l[i] > h[i - 2];
      bool bearGap = h[i] < l[i - 2];
      if(bullGap || bearGap)
        {
         int zi = ArraySize(g_fvgZones);
         ArrayResize(g_fvgZones, zi + 1);
         g_fvgZones[zi].top       = bullGap ? l[i] : l[i - 2];
         g_fvgZones[zi].bottom    = bullGap ? h[i - 2] : h[i];
         g_fvgZones[zi].bullish   = bullGap;
         g_fvgZones[zi].startTime = r[i - 1].time;
         g_fvgZones[zi].active    = true;
         g_fvgZones[zi].rectName  = g_fvg + (bullGap ? "bull_" : "bear_") + IntegerToString((long)t_i);
         //--- v2.25 FIX - per report: "i was looking at the chart the
         //--- whole time there was not gap printed there". Root cause:
         //--- the rectangle used to only ever get CREATED in the one
         //--- draw-all-active-zones loop that runs ONCE at the end of
         //--- this whole function - so a zone that formed AND got
         //--- touched/rejected/invalidated within the SAME processing
         //--- batch (very possible during backfill, which processes many
         //--- bars in one call) would resolve and become inactive before
         //--- that final loop ever ran, meaning its rectangle was NEVER
         //--- drawn at all - while the signal arrow still fired
         //--- unconditionally, since that draw is inline and doesn't
         //--- depend on the zone still being active later. Now drawn
         //--- immediately on formation instead, so every zone gets a
         //--- rectangle the moment it exists, regardless of how quickly
         //--- it then gets resolved.
         DrawZoneRect(g_fvgZones[zi].rectName, g_fvgZones[zi].startTime, t_i,
                      g_fvgZones[zi].top, g_fvgZones[zi].bottom,
                      g_fvgZones[zi].bullish ? InpFvgBullCol : InpFvgBearCol);
        }
     }

   //--- extend every still-active zone's right edge forward, and prune
   datetime ageCutoff = (InpFvgMaxAgeDays > 0) ? (r[n - 1].time - (datetime)((long)InpFvgMaxAgeDays * 86400)) : 0;
   PruneZones(g_fvgZones, InpFvgMaxZones, ageCutoff);
   CompactZones(g_fvgZones);
   for(int zi = 0; zi < ArraySize(g_fvgZones); zi++)
      if(g_fvgZones[zi].active)
         DrawZoneRect(g_fvgZones[zi].rectName, g_fvgZones[zi].startTime, r[n - 1].time,
                      g_fvgZones[zi].top, g_fvgZones[zi].bottom,
                      g_fvgZones[zi].bullish ? InpFvgBullCol : InpFvgBearCol);

   g_fvgLastProcessedBar = r[n - 1].time;
   g_fvgLastMarkerPrice = lastMarkerPrice; g_fvgLastMarkerTime = lastMarkerTime;
  }

void ResyncFvgSignals()
  {
   ObjectsDeleteAll(0, g_fvg);
   ObjectsDeleteAll(0, g_fvgSig);
   ArrayResize(g_fvgZones, 0);
   g_fvgLastProcessedBar = 0;
   g_fvgLastMarkerPrice = 0.0; g_fvgLastMarkerTime = 0;
   g_fvgLastBuyAt = 0; g_fvgLastSellAt = 0;
   if(InpShowFVG) ComputeFvgSignals(true);
  }

//+------------------------------------------------------------------+
//| v2.19: Liquidity (equal highs/lows) zones + rejection signals (NEW, |
//| per direct request). Confirmed swing pivots via the same fractal    |
//| window approach as the Divergence overlay; a new pivot within       |
//| InpLiqTolATR of the single previously-stored pivot of the same type |
//| (and within InpLiqLookbackBars) forms a thin zone spanning the two  |
//| prices - equal highs = resistance/sell-side liquidity (SELL on      |
//| reject), equal lows = support/buy-side liquidity (BUY on reject).   |
//| Same ProcessZoneBar() touch/reject/invalidate rule as FVG.          |
//+------------------------------------------------------------------+
void ComputeLiquiditySignals(const bool backfill)
  {
   int w = InpLiqPivotWindow;
   int minBars = InpLiqSwingBars + 2 * w + 10;
   int available = Bars(_Symbol, PERIOD_CURRENT) - 1;
   //--- v2.21 FIX (Opus-found, CRITICAL) - same root cause and fix as
   //--- ComputeFvgSignals' own comment: backfill scan window capped to
   //--- roughly InpLiqMaxAgeDays worth of bars instead of the entire
   //--- chart history, since anything older gets pruned within one tick
   //--- anyway.
   int maxAgeBars = (InpLiqMaxAgeDays > 0)
                     ? (int)((long)InpLiqMaxAgeDays * 86400 / PeriodSeconds(PERIOD_CURRENT)) + minBars + 50
                     : available;
   int total = backfill ? MathMin(available, maxAgeBars) : MathMin(available, minBars + 500);
   if(total < minBars) return;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 1, total, r);
   if(n < minBars) return;

   double c[], h[], l[];
   ArrayResize(c, n); ArrayResize(h, n); ArrayResize(l, n);
   for(int i = 0; i < n; i++) { c[i] = r[i].close; h[i] = r[i].high; l[i] = r[i].low; }
   double atr[];
   SigATR(h, l, c, n, 14, atr);

   int perSec = PeriodSeconds(PERIOD_CURRENT);
   int maxI = n - 1 - w;
   if(maxI < w) return;
   int from = w;
   if(!backfill)
     {
      for(int p = maxI; p >= w; p--)
        {
         if(r[p].time <= g_liqLastProcessedBar) break;
         from = p;
        }
     }
   //--- v2.21 FIX: gate object creation to InpSigDrawDays, same
   //--- convention as every other overlay
   int sigDrawBars = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int drawFrom = backfill ? MathMax(from, maxI - sigDrawBars) : from;
   double lastMarkerPrice = backfill ? 0.0 : g_liqLastMarkerPrice;
   datetime lastMarkerTime = backfill ? 0 : g_liqLastMarkerTime;
   bool haveLow = backfill ? false : g_liqHaveLow;
   datetime lowT = backfill ? 0 : g_liqLowTime; double lowP = backfill ? 0.0 : g_liqLowPrice;
   bool haveHigh = backfill ? false : g_liqHaveHigh;
   datetime highT = backfill ? 0 : g_liqHighTime; double highP = backfill ? 0.0 : g_liqHighPrice;

   for(int i = from; i <= maxI; i++)
     {
      datetime t_i = r[i].time;
      bool draw = (i >= drawFrom);

      //--- process existing zones against this bar first
      for(int zi = 0; zi < ArraySize(g_liqZones); zi++)
        {
         if(!g_liqZones[zi].active) continue;
         bool reject, invalidate;
         ProcessZoneBar(g_liqZones[zi], c[i], h[i], l[i], reject, invalidate);
         if(invalidate)
           {
            ObjectDelete(0, g_liqZones[zi].rectName);
            g_liqZones[zi].active = false;
           }
         else if(reject)
           {
            bool isBuy = g_liqZones[zi].bullish;
            datetime lastAt = isBuy ? g_liqLastBuyAt : g_liqLastSellAt;
            if(lastAt == 0 || (t_i - lastAt) >= (datetime)InpLiqCooldownBars * perSec)
              {
               if(isBuy) g_liqLastBuyAt = t_i; else g_liqLastSellAt = t_i;
               if(draw)
                 {
                  double offEntry = (atr[i] == SIG_NA) ? 0.0 : InpLiqArrowOffsetATR * atr[i];
                  //--- v2.23 FIX (Opus-found) - same reasoning as the FVG overlay's
                  //--- own comment: rectName is stable across CompactZones(), the
                  //--- array index zi is not.
                  string id = g_liqZones[zi].rectName + "_" + IntegerToString((long)t_i);
                  string nm = g_liqSig + "arr_" + id;
                  double entryPrice = isBuy ? l[i] - offEntry : h[i] + offEntry;
                  double minGap = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
                  entryPrice = NudgeAwayFromLastMarker(entryPrice, t_i, !isBuy, lastMarkerPrice, lastMarkerTime, minGap);
                  entryPrice = NudgeClearOfOtherOverlays(entryPrice, t_i, !isBuy, minGap, nm);
                  lastMarkerPrice = entryPrice; lastMarkerTime = t_i;
                  bool wasNew = (ObjectFind(0, nm) < 0);
                  DrawZoneSignalArrow(nm, t_i, entryPrice, isBuy, InpLiqArrowBuyCol, InpLiqArrowSellCol,
                                       InpLiqArrowSize, isBuy ? "Liquidity Sweep Buy (unvalidated)" :
                                       "Liquidity Sweep Sell (unvalidated)");
                  //--- v2.25: per direct request - see the FVG overlay's own comment
                  DrawZoneRect(g_liqZones[zi].rectName, g_liqZones[zi].startTime, t_i,
                               g_liqZones[zi].top, g_liqZones[zi].bottom, InpLiqSpentCol);

                  double swing = isBuy ? l[i] : h[i];
                  for(int j = i - InpLiqSwingBars + 1; j < i; j++)
                     if(j >= 0) swing = isBuy ? MathMin(swing, l[j]) : MathMax(swing, h[j]);
                  double risk = isBuy ? (c[i] - swing) : (swing - c[i]);
                  if(risk > 0.0)
                    {
                     DrawSigLevel(g_liqSig + "sl_" + id, t_i, t_i + InpLiqLineBars * perSec, swing, InpLiqStopCol, STYLE_SOLID,
                                  "Liquidity SL: recent " + IntegerToString(InpLiqSwingBars) + "-bar swing (unvalidated)");
                    }
                  if(!backfill && wasNew && InpLiqAlert)
                    {
                     string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
                     FireSigAlert(StringFormat("%s %s: Liquidity Sweep %s PRINTED - UNVALIDATED, chart overlay only",
                                                _Symbol, tf, isBuy ? "BUY" : "SELL"));
                    }
                 }
              }
            //--- v2.25 FIX - same reasoning as the FVG overlay's own
            //--- comment: deactivated (spent, won't be retested) but no
            //--- longer deleted here, so the rectangle stays on the chart
            //--- as a record of what triggered the signal - it ages out
            //--- naturally via PruneZones' InpLiqMaxAgeDays cutoff.
            g_liqZones[zi].active = false;
           }
        }

      //--- confirmed-pivot detection, same fractal window as elsewhere
      if(atr[i] == SIG_NA || atr[i] <= 0.0) { continue; }
      bool isPivotLow = true, isPivotHigh = true;
      for(int jx = 1; jx <= w; jx++)
        {
         if(l[i] > l[i - jx] || l[i] >= l[i + jx]) isPivotLow = false;
         if(h[i] < h[i - jx] || h[i] <= h[i + jx]) isPivotHigh = false;
         if(!isPivotLow && !isPivotHigh) break;
        }

      if(isPivotLow)
        {
         if(haveLow && (t_i - lowT) <= (datetime)InpLiqLookbackBars * perSec &&
            MathAbs(l[i] - lowP) <= InpLiqTolATR * atr[i])
           {
            int zi = ArraySize(g_liqZones);
            ArrayResize(g_liqZones, zi + 1);
            g_liqZones[zi].top       = MathMax(l[i], lowP);
            g_liqZones[zi].bottom    = MathMin(l[i], lowP);
            if(g_liqZones[zi].top <= g_liqZones[zi].bottom) g_liqZones[zi].top = g_liqZones[zi].bottom + 0.05 * atr[i];
            g_liqZones[zi].bullish   = true;
            g_liqZones[zi].startTime = lowT;
            g_liqZones[zi].active    = true;
            g_liqZones[zi].rectName  = g_liq + "bull_" + IntegerToString((long)t_i);
            //--- v2.25 FIX - same reasoning as the FVG overlay's own
            //--- comment: draw the rectangle immediately on formation,
            //--- not only in the end-of-function sweep (which only
            //--- catches zones still active by then)
            DrawZoneRect(g_liqZones[zi].rectName, g_liqZones[zi].startTime, t_i,
                         g_liqZones[zi].top, g_liqZones[zi].bottom, InpLiqBullCol);
           }
         haveLow = true; lowT = t_i; lowP = l[i];
        }
      if(isPivotHigh)
        {
         if(haveHigh && (t_i - highT) <= (datetime)InpLiqLookbackBars * perSec &&
            MathAbs(h[i] - highP) <= InpLiqTolATR * atr[i])
           {
            int zi = ArraySize(g_liqZones);
            ArrayResize(g_liqZones, zi + 1);
            g_liqZones[zi].top       = MathMax(h[i], highP);
            g_liqZones[zi].bottom    = MathMin(h[i], highP);
            if(g_liqZones[zi].top <= g_liqZones[zi].bottom) g_liqZones[zi].top = g_liqZones[zi].bottom + 0.05 * atr[i];
            g_liqZones[zi].bullish   = false;
            g_liqZones[zi].startTime = highT;
            g_liqZones[zi].active    = true;
            g_liqZones[zi].rectName  = g_liq + "bear_" + IntegerToString((long)t_i);
            DrawZoneRect(g_liqZones[zi].rectName, g_liqZones[zi].startTime, t_i,
                         g_liqZones[zi].top, g_liqZones[zi].bottom, InpLiqBearCol);
           }
         haveHigh = true; highT = t_i; highP = h[i];
        }
     }

   datetime ageCutoff = (InpLiqMaxAgeDays > 0) ? (r[maxI].time - (datetime)((long)InpLiqMaxAgeDays * 86400)) : 0;
   PruneZones(g_liqZones, InpLiqMaxZones, ageCutoff);
   CompactZones(g_liqZones);
   for(int zi = 0; zi < ArraySize(g_liqZones); zi++)
      if(g_liqZones[zi].active)
         DrawZoneRect(g_liqZones[zi].rectName, g_liqZones[zi].startTime, r[maxI].time,
                      g_liqZones[zi].top, g_liqZones[zi].bottom,
                      g_liqZones[zi].bullish ? InpLiqBullCol : InpLiqBearCol);

   g_liqLastProcessedBar = r[maxI].time;
   g_liqLastMarkerPrice = lastMarkerPrice; g_liqLastMarkerTime = lastMarkerTime;
   g_liqHaveLow = haveLow; g_liqLowTime = lowT; g_liqLowPrice = lowP;
   g_liqHaveHigh = haveHigh; g_liqHighTime = highT; g_liqHighPrice = highP;
  }

void ResyncLiquiditySignals()
  {
   ObjectsDeleteAll(0, g_liq);
   ObjectsDeleteAll(0, g_liqSig);
   ArrayResize(g_liqZones, 0);
   g_liqLastProcessedBar = 0;
   g_liqLastMarkerPrice = 0.0; g_liqLastMarkerTime = 0;
   g_liqLastBuyAt = 0; g_liqLastSellAt = 0;
   g_liqHaveLow = false; g_liqLowTime = 0; g_liqLowPrice = 0.0;
   g_liqHaveHigh = false; g_liqHighTime = 0; g_liqHighPrice = 0.0;
   if(InpShowLiquidity) ComputeLiquiditySignals(true);
  }

//+------------------------------------------------------------------+
void SetupMAs()
  {
   //--- v1.58: REVERTED to the plain built-in iMA handles only (see
   //--- InpMAHistoryBars' own comment for why) - these handles now serve
   //--- BOTH the hand-drawn lines (UpdateOverlayLines/BackfillOverlayLines)
   //--- AND the cross-proximity alert, exactly as before v1.49.
   if(!InpShowMAs && !InpEnableCrossAlert) return;
   g_maHandle21  = iMA(_Symbol, PERIOD_CURRENT, InpMA21,  0, InpMAMethod, PRICE_CLOSE);
   g_maHandle50  = iMA(_Symbol, PERIOD_CURRENT, InpMA50,  0, InpMAMethod, PRICE_CLOSE);
   g_maHandle200 = iMA(_Symbol, PERIOD_CURRENT, InpMA200, 0, InpMAMethod, PRICE_CLOSE);
   if(InpEnableCrossAlert)
      g_atrHandleCross = iATR(_Symbol, PERIOD_CURRENT, InpCrossATRPeriod);
  }

//+------------------------------------------------------------------+
//| v2.09: release all 4 handles AND mark them INVALID, so a second    |
//| release (e.g. OnDeinit, then the next rebuild) can never hit a     |
//| stale handle number.                                                |
//+------------------------------------------------------------------+
void ReleaseMAHandles()
  {
   if(g_maHandle21     != INVALID_HANDLE) IndicatorRelease(g_maHandle21);
   if(g_maHandle50     != INVALID_HANDLE) IndicatorRelease(g_maHandle50);
   if(g_maHandle200    != INVALID_HANDLE) IndicatorRelease(g_maHandle200);
   if(g_atrHandleCross != INVALID_HANDLE) IndicatorRelease(g_atrHandleCross);
   g_maHandle21 = INVALID_HANDLE; g_maHandle50 = INVALID_HANDLE;
   g_maHandle200 = INVALID_HANDLE; g_atrHandleCross = INVALID_HANDLE;
  }

//+------------------------------------------------------------------+
//| v2.09: true once the MA handles have actually finished calculating |
//| on the current timeframe, so a backfill now draws REAL values for  |
//| every bar. A brand-new iMA handle (OnInit, or right after a        |
//| timeframe switch) usually reports BarsCalculated() = -1 and        |
//| CopyBuffer fails - BackfillOverlayLines() used to run at exactly   |
//| that moment and silently draw little or nothing, with no retry.    |
//| Waits for the timeseries to be synchronized too, but only for up   |
//| to 10s - after that it settles for "every handle has calculated at |
//| least once", so this can never wait forever on a terminal quirk.   |
//+------------------------------------------------------------------+
bool MAHandleReady(const int handle, const int need)
  {
   if(handle == INVALID_HANDLE) return(true);   // disabled/failed - MAValue() skips it anyway
   int bc = BarsCalculated(handle);
   return(bc > 0 && bc >= need);
  }

bool MAHistoryReady()
  {
   int bars = Bars(_Symbol, PERIOD_CURRENT);
   if(bars <= 2) return(false);
   bool waitedLong = (GetTickCount64() - g_maPendingSinceMs >= 10000);
   bool synced = (bool)SeriesInfoInteger(_Symbol, PERIOD_CURRENT, SERIES_SYNCHRONIZED);
   if(!synced && !waitedLong) return(false);
   if(!InpShowMAs) return(true);                // VWAP-only: no handle to wait for
   int need = waitedLong ? 1 : bars - 1;        // -1: tolerate a new bar arriving between the two reads
   return(MAHandleReady(g_maHandle21, need) && MAHandleReady(g_maHandle50, need)
          && MAHandleReady(g_maHandle200, need));
  }

//+------------------------------------------------------------------+
//| v2.09: the ONLY place the MA handles and MA/VWAP lines are ever    |
//| rebuilt. Idempotent - provably a no-op unless something actually   |
//| changed:                                                            |
//|  Step 1 runs only if the chart's timeframe differs from g_maPeriod,|
//|         and sets g_maPeriod to it - so it runs ONCE per real       |
//|         timeframe change, never on scroll/zoom/resize/autoscroll.  |
//|  Step 2 runs only while g_maBackfillPending is true, and clears it |
//|         - so the expensive wipe + 2500-bar redraw happens ONCE per |
//|         timeframe change, as soon as the new handles are ready.    |
//| Safe to call from anywhere, as often as you like (OnInit, every    |
//| OnTick, every 2s OnTimer, every CHARTEVENT_CHART_CHANGE) - when    |
//| nothing changed it costs one comparison and one bool check.        |
//| Returns true if it drew anything (caller should reclaim the        |
//| panel's paint order).                                               |
//+------------------------------------------------------------------+
bool SyncMAOverlays()
  {
   bool changed = false;
   ENUM_TIMEFRAMES cur = (ENUM_TIMEFRAMES)_Period;
   if(g_maPeriod != cur)
     {
      g_maPeriod = cur;
      ReleaseMAHandles();
      SetupMAs();
      ObjectsDeleteAll(0, g_pm);          // old timeframe's lines go NOW, never left behind
      g_maBackfillPending = true;
      g_maPendingSinceMs  = GetTickCount64();
      g_maInitialDrawDone = false;   // v2.11: step 2 below draws once immediately, then once more
                                      // when ready/hard-capped - nothing in between, so no blinking
      g_lastBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
      //--- v2.27: the overlays that read the chart's own timeframe
      //--- (Rejection / Rejection M15 removed entirely per direct request)
      ResyncEmaCrossSignals();
      ResyncStochSignals();
      ResyncCandleSignals();
      ResyncDivSignals();
      ResyncBBSignals();
      ResyncFvgSignals();
      ResyncLiquiditySignals();
      changed = true;
     }
   //--- v2.10: NEVER wait forever on MAHistoryReady(). Real-world MT5 can
   //--- leave a just-created handle's BarsCalculated() stuck at -1 for a
   //--- long time (or permanently) if history for this symbol/timeframe
   //--- hasn't been downloaded/cached yet - the old gate ("backfill runs
   //--- ONLY once MAHistoryReady() is true") could then never fire at
   //--- all, leaving the chart with the old lines already wiped (step 1
   //--- above) and nothing ever drawn to replace them - permanently
   //--- blank/stuck, reported as "still doing the same thing".
   //--- v2.11 (Opus-reviewed, two gaps found in the first v2.10 cut and
   //--- fixed here): draws AT MOST TWICE per timeframe switch, never on
   //--- a repeating interval - (a) one immediate best-effort attempt the
   //--- very first time this runs after the switch, so something shows
   //--- right away instead of staying blank, and (b) exactly one more
   //--- attempt the moment MAHistoryReady() actually turns true - no
   //--- cap on how long that can take, so it can never give up and stay
   //--- wrong forever the way the pre-fix bug did; a 15s hard cap is
   //--- still there only as a last-resort SECOND chance if the first
   //--- immediate draw already happened before 15s and nothing has
   //--- turned ready since. In between those two draws, this is a cheap
   //--- no-redraw check (no wipe, no BackfillOverlayLines, no panel
   //--- rebuild) - so no 2-second blinking during a slow history load.
   if(g_maBackfillPending)
     {
      bool ready = MAHistoryReady();
      if(!g_maInitialDrawDone)
        {
         ObjectsDeleteAll(0, g_pm);
         BackfillOverlayLines();
         g_maInitialDrawDone = true;
         changed = true;
         if(ready) g_maBackfillPending = false;   // already good on the first try - done
        }
      else if(ready)
        {
         ObjectsDeleteAll(0, g_pm);          // replace whatever the first attempt managed
         BackfillOverlayLines();
         g_maBackfillPending = false;
         changed = true;
        }
      else if((GetTickCount64() - g_maPendingSinceMs) >= 15000)
        {
         //--- last-resort second attempt with whatever's available now,
         //--- then stop - MAHistoryReady() keeps getting checked for
         //--- free on every future call (the line above), so if it DOES
         //--- turn true later this branch won't fire again, but nothing
         //--- is drawn again either; the next genuine timeframe switch
         //--- (or CheckNewBar's own per-bar UpdateOverlayLines()) is
         //--- what catches up from there - an edge case, not the common
         //--- path, per Opus's review.
         ObjectsDeleteAll(0, g_pm);
         BackfillOverlayLines();
         g_maBackfillPending = false;
         changed = true;
        }
      //--- else: still waiting on the SECOND draw, handles not ready yet,
      //--- under 15s - deliberately do nothing (no redraw, no flicker)
     }
   return(changed);
  }

//+------------------------------------------------------------------+
//| Push-notification warning that the 21/50 MA gap is closing and a  |
//| cross looks imminent, BEFORE it actually happens - not an alert   |
//| on the cross itself. Checked once per new closed bar (same        |
//| cadence as UpdateOverlayLines - no reason to re-check every tick, |
//| the MA values for a closed bar don't change until the next one).  |
//|                                                                     |
//| Uses shift 1/2 (the last two CLOSED bars) rather than the forming  |
//| bar 0 - same reasoning as this project's standard fix for H4-bar   |
//| lookups elsewhere: an unclosed bar's MA value still moves as price |
//| moves, which would fire (or un-fire) the alert on noise rather    |
//| than a settled reading.                                            |
//|                                                                     |
//| "Likely to cross soon" = the 21/50 gap, measured in ATR, has both  |
//| (a) narrowed versus the prior closed bar and (b) closed to within  |
//| InpCrossAlertATRMult*ATR - not yet crossed (sign unchanged). Fires |
//| once per approach (g_crossAlerted latches), resets once the gap    |
//| widens back out past 1.5x the threshold or the cross actually      |
//| happens, so the next approach can alert again.                     |
//+------------------------------------------------------------------+
void CheckCrossProximity()
  {
   if(!InpEnableCrossAlert) return;
   if(g_maHandle21 == INVALID_HANDLE || g_maHandle50 == INVALID_HANDLE || g_atrHandleCross == INVALID_HANDLE) return;

   double ma21_1, ma21_2, ma50_1, ma50_2, atr_1;
   if(!MAValue(g_maHandle21, 1, ma21_1) || !MAValue(g_maHandle21, 2, ma21_2)) return;
   if(!MAValue(g_maHandle50, 1, ma50_1) || !MAValue(g_maHandle50, 2, ma50_2)) return;
   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(g_atrHandleCross, 0, 1, 1, atrBuf) != 1 || atrBuf[0] <= 0.0) return;
   atr_1 = atrBuf[0];

   double gapNow  = ma21_1 - ma50_1;
   double gapPrev = ma21_2 - ma50_2;
   bool alreadyCrossed = (gapNow >= 0.0) != (gapPrev >= 0.0);
   double threshold = InpCrossAlertATRMult * atr_1;

   if(alreadyCrossed || MathAbs(gapNow) > threshold * 1.5)
     {
      g_crossAlerted = false;   // clear reset - diverged again, or the cross already happened
      return;
     }

   bool narrowing = MathAbs(gapNow) < MathAbs(gapPrev);
   bool near       = MathAbs(gapNow) <= threshold;
   if(!narrowing || !near) return;
   if(g_crossAlerted) return;   // already warned for this approach, waiting for a reset
   if(TimeCurrent() - g_lastCrossAlertAt < InpCrossAlertCooldownMin * 60) return;

   string dir = (gapNow > 0.0) ? "21 crossing DOWN through 50 (bearish)" : "21 crossing UP through 50 (bullish)";
   string tf  = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);   // "PERIOD_M15" -> "M15"
   string msg = StringFormat("%s %s: 21/50 MA gap closing, %s likely soon (gap %.1f%% of threshold)",
                              _Symbol, tf, dir, 100.0 * MathAbs(gapNow) / threshold);
   SendNotification(msg);
   Print("CrossAlert: ", msg);
   g_crossAlerted = true;
   g_lastCrossAlertAt = TimeCurrent();
  }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Builds every panel object fresh. MT5 paints chart objects in      |
//| CREATION ORDER, not by OBJPROP_ZORDER (that property only decides |
//| mouse-click priority, not paint order - a real mistake in v1.03). |
//| The MA/VWAP trend segments get a brand-new object created every   |
//| single new bar (UpdateOverlayLines), so they will always paint on |
//| top of a panel that was only ever built once in OnInit. The only  |
//| real fix is to rebuild the panel (so it becomes the newest set of |
//| objects again) after every new-bar redraw - see RebuildPanel()    |
//| and its call from OnTick. Same reasoning Aurelius_EA.mq5's own    |
//| comments already describe for its UpdateMALines/DrawPanel order.  |
//+------------------------------------------------------------------+
void BuildPanel()
  {
   //--- per direct request: shorter panel, smaller text - traded a bit of
   //--- width (340->370) for a lot less height (rows tightened from
   //--- 28-38px down to 20-26px, fonts from 10 down to 8-9) so nothing
   //--- wraps or crowds at the smaller size.
   g_panelW = 370;
   int w = g_panelW;
   ObjectCreate(0, PFX + "bg", OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XDISTANCE, g_panelX);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YDISTANCE, g_panelY);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XSIZE, w);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, g_panelH);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_BGCOLOR, InpBgColor);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_BACK, false);
   //--- NOT selectable - native rectangle-label dragging is unreliable once
   //--- buttons/edits sit on top of it (they eat the mouse-down before the
   //--- background ever sees it). Dragging is instead handled manually in
   //--- OnChartEvent via CHARTEVENT_MOUSE_MOVE, restricted to the title
   //--- strip (TITLE_BAR_H) - see DragPanel/the mouse-move handler below.
   ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTED, false);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_HIDDEN, false);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_ZORDER, PANEL_ZORDER);

   //--- title strip, visually separated so the drag area is obvious
   ObjectCreate(0, PFX + "titlebar", OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_XDISTANCE, g_panelX);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_YDISTANCE, g_panelY);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_XSIZE, w);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_YSIZE, TITLE_BAR_H);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_BGCOLOR, C'55,55,62');
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_BACK, false);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_HIDDEN, false);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_ZORDER, PANEL_ZORDER);
   AddCtrl(PFX + "titlebar", 0, 0);

   //--- v2.14: show which timeframe this instance is running on, right in
   //--- the title - per direct request, so two separate panels (one per
   //--- timeframe, the agreed setup after this file's timeframe-switch
   //--- troubles) are obviously distinguishable at a glance rather than
   //--- both saying the same generic "TRADE PANEL"
   string panelTf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
   MkLabel("title", 10, 4, "TRADE PANEL [" + panelTf + "]  (drag here to move)", clrWhite, 9);

   int y = TITLE_BAR_H + 10;
   MkLabel("lotLbl", 12, y + 3, "Lot size:", InpTextColor, 9);
   MkEdit("lotEdit", 130, y, 80, 20, "0.01");
   MkButton("lotMinus", 216, y, 22, 20, "-", C'70,70,78', clrWhite, 10);
   MkButton("lotPlus",  242, y, 22, 20, "+", C'70,70,78', clrWhite, 10);

   y += 26;
   MkLabel("cntLbl", 12, y + 3, "Trade count:", InpTextColor, 9);
   MkEdit("cntEdit", 130, y, 80, 20, "3");
   MkButton("cntMinus", 216, y, 22, 20, "-", C'70,70,78', clrWhite, 10);
   MkButton("cntPlus",  242, y, 22, 20, "+", C'70,70,78', clrWhite, 10);

   y += 24;
   MkLabel("expLbl", 12, y, "Exposure: -", clrKhaki, 9);

   y += 22;
   MkLabel("delayLbl", 12, y + 3, "Arm delay (s):", InpTextColor, 9);
   MkEdit("delayEdit", 150, y, 50, 20, IntegerToString(g_armSeconds));
   MkButton("delayMinus", 216, y, 22, 20, "-", C'70,70,78', clrWhite, 10);
   MkButton("delayPlus",  242, y, 22, 20, "+", C'70,70,78', clrWhite, 10);

   y += 26;
   MkButton("armBtn", 12, y, w - 24, 22, "ARM (required before PLACE)", InpBgColor, clrSilver, 9);

   y += 28;
   MkButton("buyBtn", 12, y, (w - 36) / 2, 26, "PLACE BUY xN", InpBuyColor, clrWhite, 9);
   MkButton("sellBtn", 12 + (w - 36) / 2 + 12, y, (w - 36) / 2, 26, "PLACE SELL xN", InpSellColor, clrWhite, 9);

   //--- closes the N OLDEST matched positions exactly - replaced the old
   //--- 25/50/75% buttons entirely per direct request: with several
   //--- equal-size trades from one PLACE xN batch, "close N%" can only
   //--- ever approximate a whole number of positions anyway, so exact
   //--- count is both simpler and more precise.
   //--- v1.52: this used to create "closeNLbl" twice in a row (copy/paste
   //--- slip) - the second call silently re-created/moved the same-named
   //--- object and added a spurious extra 18px gap, which made the panel
   //--- taller than intended and doubled this one label's effective drag
   //--- sensitivity if it was ever dragged by (Opus audit finding).
   y += 34;
   MkLabel("closeNLbl", 12, y, "Close N oldest position(s):", InpTextColor, 9);
   y += 18;
     {
      int ncw = (w - 24 - 8 * 2) / 9;   // 9 buttons, 2px gaps between them
      for(int k = 1; k <= 9; k++)
         MkButton("cN" + IntegerToString(k), 12 + (k - 1) * (ncw + 2), y, ncw, 22,
                  IntegerToString(k), C'70,70,78', clrWhite, 9);
     }

   y += 30;
   MkButton("cAll", 12, y, w - 24, 24, "CLOSE ALL OPEN TRADES", C'150,40,40', clrWhite, 9);

   y += 32;
   MkLabel("sltpLbl", 12, y, "Manual SL / TP for current position(s):", InpTextColor, 9);
   y += 18;
   MkLabel("slLbl", 12, y + 3, "SL:", InpTextColor, 9);
   MkEdit("slEdit", 45, y, 100, 20, "0.00");
   MkButton("setSL", 155, y, 65, 20, "Set SL", C'70,70,78', clrWhite, 9);
   y += 24;
   MkLabel("tpLbl", 12, y + 3, "TP:", InpTextColor, 9);
   MkEdit("tpEdit", 45, y, 100, 20, "0.00");
   MkButton("setTP", 155, y, 65, 20, "Set TP", C'70,70,78', clrWhite, 9);
   y += 24;
   MkButton("fillCur", 12, y, w - 24, 18, "Fill fields with current SL/TP", C'55,55,62', clrSilver, 8);

   y += 28;
   MkLabel("statLbl", 12, y, "Open: 0 pos | 0.00 lot | P/L 0.00", clrSilver, 9);

   y += 20;
   MkLabel("spreadLbl", 12, y, "Spread: -", clrKhaki, 9);
   y += 16;
   MkLabel("volLbl", 12, y, "Volume (last bar): -", clrKhaki, 9);

   y += 22;
   MkLabel("light", 12, y, "l", clrLimeGreen, 12);
   ObjectSetString(0, PFX + "light", OBJPROP_FONT, "Wingdings");
   MkLabel("lightLbl", 30, y + 1, "OK TO TRADE (spread within limit)", clrLimeGreen, 9);

   g_panelH = y + 36;   // extra bottom margin so the last row never sits flush with the edge
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, g_panelH);

   UpdateExposureLabel();
   UpdateStats();
   UpdateMarketLabel();
  }

//+------------------------------------------------------------------+
//| Rebuilds the panel so it becomes the newest (therefore topmost-   |
//| painted) set of objects again - called once per new bar, right    |
//| after UpdateOverlayLines() draws that bar's MA/VWAP segments.      |
//| Preserves the lot/count/delay fields and the panel's current      |
//| dragged-to position; does NOT preserve an in-progress ARM (it      |
//| auto-expires in a few seconds anyway, and resetting it on rebuild  |
//| is a safety positive, not a problem).                              |
//+------------------------------------------------------------------+
void RebuildPanel()
  {
   string lotText = ObjectGetString(0, PFX + "lotEdit", OBJPROP_TEXT);
   string cntText = ObjectGetString(0, PFX + "cntEdit", OBJPROP_TEXT);
   string slText  = ObjectGetString(0, PFX + "slEdit", OBJPROP_TEXT);
   string tpText  = ObjectGetString(0, PFX + "tpEdit", OBJPROP_TEXT);
   ObjectsDeleteAll(0, PFX);
   g_nCtrls = 0;
   BuildPanel();
   ObjectSetString(0, PFX + "lotEdit", OBJPROP_TEXT, lotText);
   ObjectSetString(0, PFX + "cntEdit", OBJPROP_TEXT, cntText);
   ObjectSetString(0, PFX + "slEdit", OBJPROP_TEXT, slText);
   ObjectSetString(0, PFX + "tpEdit", OBJPROP_TEXT, tpText);
   UpdateExposureLabel();
   UpdateMarketLabel();
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   //--- hard refusal - this copy is locked to EXPECTED_PERIOD. Checked
   //--- first, before anything else sets up, so a wrong-chart attach
   //--- never creates handles/objects/a panel at all.
   if((ENUM_TIMEFRAMES)_Period != EXPECTED_PERIOD)
     {
      string wantTf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)EXPECTED_PERIOD), 7);
      string gotTf  = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
      Alert("TradePanel_EA_M15: this copy only runs on " + wantTf + " charts - attached to " + gotTf +
            " instead. Remove it and use TradePanel_EA_M5.mq5 (or plain TradePanel_EA.mq5) on this chart.");
      return(INIT_FAILED);
     }

   ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);   // required for the manual title-bar drag handler

   //--- v2.13 (Opus-reviewed, a real bug found in the first v2.12 cut and
   //--- fixed here): InpMagic==0 means "auto" - derive a magic number
   //--- that's different per TIMEFRAME, so two separate panel instances
   //--- (e.g. one attached to an M5 chart, one to an M15 chart, per
   //--- direct request) never see or manage each other's trades. Any
   //--- non-zero InpMagic is used exactly as typed, unchanged from every
   //--- version before this one - a single-panel setup that already has
   //--- the default (20261014) is completely unaffected.
   //--- The v2.12 formula used (int)PERIOD_CURRENT, which is the MQL5
   //--- SYMBOLIC constant for "the chart's own timeframe" when passed as
   //--- a function argument (like iMA's own timeframe parameter) - its
   //--- actual integer value is always 0, not the real timeframe. Every
   //--- instance would have silently derived the SAME magic number
   //--- regardless of chart timeframe, defeating the entire point and
   //--- risking two "separate" panels on different timeframes managing
   //--- each other's real trades without any warning. Fixed: _Period is
   //--- the correct live value (confirmed elsewhere in this same file,
   //--- e.g. the MA-sync code a few hundred lines below this one, which
   //--- already relies on exactly this distinction). Also dropped the
   //--- old symbol-length term - PositionMatches() already filters on
   //--- POSITION_SYMBOL==_Symbol separately (see its own code), so it
   //--- added collision risk between same-length symbol names without
   //--- actually preventing anything; timeframe is the only axis this
   //--- auto-derivation needs to separate.
   //--- Known, acceptable limitation: if InpMagic is left at 0 AND you
   //--- still switch a single chart's own timeframe at runtime (rather
   //--- than running two separate fixed-timeframe panels, which is the
   //--- intended usage here), the derived magic changes with it, and
   //--- this panel's stats/CLOSE ALL/SL-TP controls will stop seeing
   //--- whatever it already had open under the OLD derived magic (the
   //--- actual broker-side positions and their real SL/TP are
   //--- unaffected - only this panel's own ability to see/manage them).
   g_effectiveMagic = (InpMagic != 0) ? InpMagic : (int)(20260000 + (int)_Period);

   //--- hard proof of what settings this EA instance actually initialized
   //--- with - check this line in the Experts log any time there's doubt
   //--- about whether a changed input actually took effect, rather than
   //--- trusting the Properties dialog alone
   PrintFormat("TradePanel v2.0 OnInit: showEmaCross=%s  magic=%d (InpMagic=%d)",
               InpShowEmaCrossSignals ? "true" : "false", g_effectiveMagic, InpMagic);

   ApplyTheme();
   //--- v2.09: MT5 keeps global variables across a timeframe-switch
   //--- reinit, so force a full rebuild here explicitly rather than
   //--- trusting whatever g_maPeriod the previous instance left behind.
   //--- SyncMAOverlays() creates the handles, resyncs the 5 chart-timeframe
   //--- signal overlays, and backfills the MA/VWAP history right now if
   //--- the new handles are already calculated (then it lands BEFORE the
   //--- panel, so it can't bury it) - otherwise the backfill is left
   //--- pending and OnTick/OnTimer finish it within ~2s, then rebuild the
   //--- panel on top.
   //--- v2.23 FIX (Opus-found): g_nCtrls/g_ctrls[] are never reset here -
   //--- MT5 keeps global variables across a reinit (same reasoning as
   //--- g_maPeriod just above), but BuildPanel() below calls AddCtrl()
   //--- unconditionally, appending to whatever g_ctrls[] the PREVIOUS
   //--- compile left behind rather than starting clean. Every single
   //--- recompile this session has been accumulating stale/duplicate
   //--- control entries - DragPanel()'s loop over g_nCtrls would then
   //--- move each duplicated widget multiple times per drag, which is
   //--- exactly the kind of thing that would make the panel feel broken
   //--- (jumpy or inconsistent dragging) after a lot of testing/recompiling.
   g_nCtrls = 0;
   ArrayResize(g_ctrls, 0);
   //--- v2.23 FIX (Opus-found): same reasoning - if an edit box's
   //--- ENDEDIT event never arrived (EA removed/crashed mid-typing),
   //--- this could stay stuck true across a reinit, silently skipping
   //--- every per-bar panel rebuild from then on (see AnyEditFocused()'s
   //--- own use further down) - as if the panel had frozen.
   g_editFocused = false;
   g_maPeriod = PERIOD_CURRENT;

   //--- v2.26 FIX (Opus-found, see main file's own comment for full
   //--- detail): build + redraw the panel FIRST so it's on screen before
   //--- the heavy overlay/MA sync work, then rebuild it again after so
   //--- it repaints on top of whatever that work just drew.
   BuildPanel();
   ChartRedraw(0);
   SyncMAOverlays();
   BuildPanel();

   g_lastBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   EventSetTimer(2);   // was 1s - halving the poll frequency on top of no
                        // longer force-redrawing every tick (see OnTimer)
   ChartRedraw(0);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
   ObjectsDeleteAll(0, g_pm);
   ObjectsDeleteAll(0, g_emax);
   ObjectsDeleteAll(0, g_sig);
   ObjectsDeleteAll(0, g_cdl);
   ObjectsDeleteAll(0, "TPRJX_");
   ObjectsDeleteAll(0, "TPRJXM_");
   ObjectsDeleteAll(0, g_div);
   ObjectsDeleteAll(0, g_bb);
   ObjectsDeleteAll(0, g_fvg);
   ObjectsDeleteAll(0, g_fvgSig);
   ObjectsDeleteAll(0, g_liq);
   ObjectsDeleteAll(0, g_liqSig);
   ReleaseMAHandles();
   g_maPeriod = PERIOD_CURRENT;      // globals survive a reinit - "nothing built" now
   g_maBackfillPending = false;
   g_maInitialDrawDone = false;
  }

bool AnyEditFocused()
  {
   return g_editFocused;
  }

//+------------------------------------------------------------------+
//| v2.09: SyncMAOverlays() + put the panel back on top, but ONLY when |
//| SyncMAOverlays() actually drew something. A no-op otherwise, so it |
//| is safe on every tick, every timer tick and every chart event.     |
//+------------------------------------------------------------------+
void MaintainOverlaySync()
  {
   if(!SyncMAOverlays()) return;
   if(!g_dragging && !AnyEditFocused()) RebuildPanel();   // RebuildPanel redraws the chart itself
   else ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| New-bar work (overlay lines, stoch signals/alerts, cross-alert,     |
//| panel rebuild) - factored out so BOTH OnTick (driven by real price  |
//| ticks) and OnTimer (every 2s regardless of ticks) can call it. A    |
//| quiet/illiquid market can go well over a second between ticks, so   |
//| relying on OnTick alone means a signal that closed mid-quiet-spell  |
//| would sit undrawn until the NEXT trade prints somewhere - the timer |
//| guarantees it appears within ~2s of the bar actually closing        |
//| instead of waiting on a tick (or a manual chart refresh/scroll).    |
//| Idempotent: g_lastBarTime guards it, so whichever of OnTick/OnTimer |
//| notices the new bar first runs it, and the other is a no-op.        |
//+------------------------------------------------------------------+
void CheckNewBar()
  {
   datetime t0 = iTime(_Symbol, PERIOD_CURRENT, 0);
   //--- v1.52: iTime() briefly returning 0 (a reconnect/history-sync
   //--- hiccup) must NEVER be treated as a new bar - g_lastBarTime would
   //--- otherwise get reset to 0, and the VERY NEXT tick's real t0 would
   //--- then look "new" relative to that reset, firing every live
   //--- Compute*Signals(false) call below with a g_xLastProcessedBar that
   //--- no longer matches anything in the current window - each one's own
   //--- fallback then replays its FULL ~500-bar window, re-printing every
   //--- signal in it and re-firing every alert for signals already seen
   //--- (Opus audit finding - bounded, never hangs, but real alert/log
   //--- spam and can corrupt the open-position state via the "repeat
   //--- same-direction cross replaces the previous signal" delete logic).
   if(t0 == 0) return;
   if(t0 == g_lastBarTime) return;
   g_lastBarTime = t0;
   UpdateOverlayLines();
   //--- v2.14: compute + draw every overlay FIRST, with no purge scans in
   //--- between - each overlay used to be followed by its own full-chart
   //--- purge scan, so a Rejection/Continuation arrow (computed late in
   //--- this list) waited behind ~5 of those scans before it was even
   //--- created, and behind all 7 before the ChartRedraw below showed it.
   //--- Old-object housekeeping now runs at the END of this function,
   //--- after the redraw - see HousekeepOldObjects().
   if(InpShowEmaCrossSignals)  ComputeEmaCrossSignals(false);
   if(InpShowStochSignals)     ComputeStochSignals(false);
   if(InpShowCandleSignals)    ComputeCandleSignals(false);
   if(InpShowDivSignals)       ComputeDivSignals(false);
   if(InpShowBBSignals)        ComputeBBSignals(false);
   if(InpShowFVG)              ComputeFvgSignals(false);
   if(InpShowLiquidity)        ComputeLiquiditySignals(false);
   CheckCrossProximity();
   //--- skip the rebuild while actively dragging - recreating the title
   //--- bar object out from under an in-progress drag is asking for
   //--- trouble. The next new bar after the drag ends reclaims paint
   //--- order instead; one bar's delay is harmless.
   //--- SAME reasoning for an in-progress edit: ObjectsDeleteAll inside
   //--- RebuildPanel() destroys the slEdit/tpEdit/etc. object the user
   //--- is mid-keystroke in, which silently drops keyboard focus (the
   //--- freshly recreated object of the same name does NOT inherit it).
   //--- AnyEditFocused() is tracked via g_editFocused, set/cleared on
   //--- CHARTEVENT_OBJECT_CLICK/ENDEDIT - see its own header for why
   //--- OBJPROP_SELECTED isn't used for this anymore.
   if(!g_dragging && !AnyEditFocused()) RebuildPanel();
   //--- a signal drawn here (arrow/dot/level) is a NEW chart object - MT5
   //--- normally paints that on its own next natural cycle, but that cycle
   //--- is itself tick-driven, so in a quiet market force one redraw right
   //--- here to make a just-printed signal actually visible immediately
   //--- rather than only once the next tick (possibly seconds/minutes
   //--- later) happens to arrive. One redraw per NEW BAR only (not per
   //--- tick, not every 2s) - cheap, not the blanket per-timer redraw
   //--- that was deliberately removed below for performance.
   ChartRedraw(0);
   //--- v2.14: housekeeping LAST, after this bar's arrows are already on
   //--- screen, and at most once per hour of bar time (every 12th bar on
   //--- M5, every 4th on M15, every bar on H1 and above). Effect of the
   //--- throttle on what you see: none - between runs, at most ~11 extra
   //--- MA/VWAP segments per line linger ~8.7 days back on M5 (off the
   //--- left edge) and signal markers can outlive the InpSigDrawDays cutoff
   //--- by under an hour. "t0 < g_lastHousekeepBar" catches a timeframe
   //--- switch to a bigger timeframe, whose bar time can be earlier.
   if(g_lastHousekeepBar == 0 || t0 < g_lastHousekeepBar || t0 - g_lastHousekeepBar >= 3600)
     {
      g_lastHousekeepBar = t0;
      HousekeepOldObjects();
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   //--- CHART_SHOW_TRADE_LEVELS is a per-CHART property, not per-EA - every
   //--- strategy EA in this project (Aurelius/Vanguard/Meridian/etc.) sets
   //--- it FALSE on its own init, by design, for when it runs alone on a
   //--- chart. When TradePanel shares a chart with one of them, whichever
   //--- EA's OnTick/OnInit last touches this property wins, so a one-time
   //--- ChartSetInteger in ApplyTheme() can get silently overwritten back
   //--- to false by the other EA's own tick. Re-asserting it true every
   //--- tick here keeps TradePanel's chart winning that fight regardless
   //--- of EA load order, without having to touch the other EAs (which
   //--- still default it off correctly for their own solo-chart case).
   //--- v2.14: only WRITE it when it actually differs. Writing it
   //--- unconditionally on every tick was itself a chart-property change
   //--- per tick - which (see the v2.09 notes) MT5 answers with a
   //--- CHARTEVENT_CHART_CHANGE event each time, i.e. a stream of
   //--- pointless events/refreshes on a chart holding ~7,000 objects. Still
   //--- re-asserted within one tick if anything else flips it.
   if((bool)ChartGetInteger(0, CHART_SHOW_TRADE_LEVELS) != InpShowTradeLevels)
      ChartSetInteger(0, CHART_SHOW_TRADE_LEVELS, InpShowTradeLevels);
   MaintainOverlaySync();   // v2.09: before CheckNewBar, so a new bar is never drawn with old-timeframe handles
   CheckNewBar();
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   UpdateStats();
   UpdateMarketLabel();
   if(g_armed && TimeCurrent() >= g_armedUntil)
      SetArmed(false);
   //--- safety net: if the mouse button was released outside the chart
   //--- entirely, no further CHARTEVENT_MOUSE_MOVE fires here and the drag
   //--- (and the CHART_MOUSE_SCROLL=false lock) could otherwise get stuck.
   if(g_dragging && GetTickCount64() - g_dragStartMs > 5000)
     {
      g_dragging = false;
      ChartSetInteger(0, CHART_MOUSE_SCROLL, true);
     }
   //--- v2.09: the guaranteed backstop for a timeframe switch - whatever
   //--- the terminal does or doesn't send (reinit, CHART_CHANGE, ticks),
   //--- this checks every 2s and fixes the MAs if they don't match the
   //--- chart. A no-op (one comparison) whenever they already match.
   MaintainOverlaySync();
   //--- catches a bar close during a quiet spell between ticks - see
   //--- CheckNewBar()'s own header. g_lastBarTime guards it so this is a
   //--- cheap no-op on every 2s tick except the one right after a new bar.
   CheckNewBar();
   //--- NOT calling ChartRedraw() unconditionally here otherwise - this ran
   //--- every single second/2s, forcing MT5 to repaint the whole chart
   //--- (including every background MA/VWAP object) regardless of whether
   //--- anything actually changed. ObjectSetString/ObjectSetInteger changes
   //--- still show up on the terminal's own natural paint cycle (driven by
   //--- ticks); an explicit redraw beyond CheckNewBar()'s own is only
   //--- needed right after a batch change the user is actively looking at -
   //--- RebuildPanel(), SetArmed(), and the button click handlers already
   //--- call it where it matters.
  }

//+------------------------------------------------------------------+
void DragPanel(int newX, int newY)
  {
   //--- clamp so the title bar always stays reachable - keeps at least
   //--- TITLE_BAR_H of vertical room and 60px of horizontal room on screen,
   //--- so a drag can never strand the panel somewhere it can't be dragged
   //--- back from.
   int chartW = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   if(newX < 0) newX = 0;
   if(newY < 0) newY = 0;
   if(chartW > 0 && newX > chartW - 60) newX = chartW - 60;
   if(chartH > 0 && newY > chartH - TITLE_BAR_H) newY = chartH - TITLE_BAR_H;

   int dx = newX - g_panelX;
   int dy = newY - g_panelY;
   g_panelX = newX;
   g_panelY = newY;
   long bgX = ObjectGetInteger(0, PFX + "bg", OBJPROP_XDISTANCE);
   long bgY = ObjectGetInteger(0, PFX + "bg", OBJPROP_YDISTANCE);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XDISTANCE, bgX + dx);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YDISTANCE, bgY + dy);
   for(int i = 0; i < g_nCtrls; i++)
     {
      long curX = ObjectGetInteger(0, g_ctrls[i].name, OBJPROP_XDISTANCE);
      long curY = ObjectGetInteger(0, g_ctrls[i].name, OBJPROP_YDISTANCE);
      ObjectSetInteger(0, g_ctrls[i].name, OBJPROP_XDISTANCE, curX + dx);
      ObjectSetInteger(0, g_ctrls[i].name, OBJPROP_YDISTANCE, curY + dy);
     }
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
bool PointOverTitleBar(int mx, int my)
  {
   return(mx >= g_panelX && mx <= g_panelX + g_panelW && my >= g_panelY && my <= g_panelY + TITLE_BAR_H);
  }

//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_MOUSE_MOVE)
     {
      int mx = (int)lparam;
      int my = (int)dparam;
      int flags = (int)StringToInteger(sparam);
      bool leftDown = (flags & 1) != 0;
      if(!g_dragging && leftDown && PointOverTitleBar(mx, my))
        {
         g_dragging = true;
         g_dragOffX = mx - g_panelX;
         g_dragOffY = my - g_panelY;
         //--- MT5's native left-drag-to-scroll is still live underneath this
         //--- handler and would pan the chart at the same time the panel
         //--- moves - suspend it for the duration of the drag, restore on
         //--- release below.
         ChartSetInteger(0, CHART_MOUSE_SCROLL, false);
         g_dragStartMs = GetTickCount64();
        }
      if(g_dragging)
        {
         if(!leftDown)
           {
            g_dragging = false;
            ChartSetInteger(0, CHART_MOUSE_SCROLL, true);
            //--- reclaim top paint order THE MOMENT the drag ends, rather than
            //--- waiting for the next new bar - otherwise, on a slower
            //--- timeframe, the panel can sit buried under any MA/VWAP segment
            //--- drawn in the gap (visibly cutting through it) for however long
            //--- it takes the next bar to arrive.
            RebuildPanel();
           }
         else
           {
            //--- throttled: CHARTEVENT_MOUSE_MOVE fires dozens of times a
            //--- second while dragging, and this used to reposition ~30
            //--- objects and force a full ChartRedraw() on EVERY one of them -
            //--- that was the real cause of the chart hanging during a drag.
            //--- ~30 updates/sec is still visually smooth and far cheaper.
            ulong now = GetTickCount64();
            if(now - g_lastDragUpdateMs >= 33)
              {
               g_lastDragUpdateMs = now;
               DragPanel(mx - g_dragOffX, my - g_dragOffY);
              }
           }
        }
      return;
     }
   if(id == CHARTEVENT_OBJECT_ENDEDIT)
     {
      if(sparam == PFX + "lotEdit" || sparam == PFX + "cntEdit" || sparam == PFX + "delayEdit"
         || sparam == PFX + "slEdit" || sparam == PFX + "tpEdit")
         g_editFocused = false;
      return;
     }
   //--- v2.09: CHARTEVENT_CHART_CHANGE fires for FAR more than a timeframe
   //--- switch - every scroll, zoom, resize, autoscroll shift on a new bar,
   //--- price-scale refit as ticks move the range, and programmatic chart
   //--- property changes. v2.05/v2.06 did a full panel wipe + rebuild (and,
   //--- outside the 2s debounce window, a full MA/VWAP/signal wipe + 2500-bar
   //--- redraw) from inside this handler - the "everything keeps flashing"
   //--- bug. Now it only asks SyncMAOverlays() whether anything ACTUALLY
   //--- changed, which is a single comparison and draws nothing unless the
   //--- timeframe really changed (or a pending post-switch backfill is now
   //--- ready). OnTimer makes the same check every 2s regardless, so this
   //--- is just the fast path - correctness doesn't depend on this event.
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      MaintainOverlaySync();
      return;
     }
   if(id != CHARTEVENT_OBJECT_CLICK) return;

   if(sparam == PFX + "lotEdit" || sparam == PFX + "cntEdit" || sparam == PFX + "delayEdit"
      || sparam == PFX + "slEdit" || sparam == PFX + "tpEdit")
      g_editFocused = true;

   //--- OnTimer no longer force-redraws every second (that was the real
   //--- cause of the general lag, including clicks feeling slow - the chart
   //--- was busy redrawing ~1300 background objects every single second
   //--- regardless of whether anything changed). Every button/edit handler
   //--- below still needs its own immediate visible update though, so
   //--- redraw once here, right after whichever one of them ran.
   if(sparam == PFX + "lotEdit" || sparam == PFX + "cntEdit")
     {
      UpdateExposureLabel();
      ChartRedraw(0);
      return;
     }
   if(sparam == PFX + "delayEdit") { SyncArmSecondsFromEdit(); ChartRedraw(0); return; }
   //--- v2.23 FIX (Opus-found): these 6 stepper buttons never reset
   //--- OBJPROP_STATE after handling the click, unlike every other
   //--- button on the panel - the action DID run each time, but the
   //--- button stayed drawn in its pressed state until the NEXT click
   //--- popped it back up, which reads as "the +/- buttons aren't
   //--- working" even though they were.
   if(sparam == PFX + "lotMinus") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); AdjustLot(-SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)); ChartRedraw(0); return; }
   if(sparam == PFX + "lotPlus")  { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); AdjustLot(+SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)); ChartRedraw(0); return; }
   if(sparam == PFX + "cntMinus") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); AdjustCount(-1); ChartRedraw(0); return; }
   if(sparam == PFX + "cntPlus")  { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); AdjustCount(+1); ChartRedraw(0); return; }
   if(sparam == PFX + "delayMinus") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); AdjustArmSeconds(-1); ChartRedraw(0); return; }
   if(sparam == PFX + "delayPlus")  { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); AdjustArmSeconds(+1); ChartRedraw(0); return; }
   if(sparam == PFX + "armBtn")
     {
      SetArmed(!g_armed);
      return;
     }
   if(sparam == PFX + "buyBtn")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      PlaceBatch(true);
      UpdateStats();
      ChartRedraw(0);
      return;
     }
   if(sparam == PFX + "sellBtn")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      PlaceBatch(false);
      UpdateStats();
      ChartRedraw(0);
      return;
     }
   for(int k = 1; k <= 9; k++)
      if(sparam == PFX + "cN" + IntegerToString(k))
        {
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ClosePositionCount(k);
         UpdateStats();
         ChartRedraw(0);
         return;
        }
   if(sparam == PFX + "cAll") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); CloseAll(); UpdateStats(); ChartRedraw(0); return; }
   if(sparam == PFX + "slEdit" || sparam == PFX + "tpEdit") return;
   if(sparam == PFX + "setSL")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      SetSLForAll(StringToDouble(ObjectGetString(0, PFX + "slEdit", OBJPROP_TEXT)));
      ChartRedraw(0);
      return;
     }
   if(sparam == PFX + "setTP")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      SetTPForAll(StringToDouble(ObjectGetString(0, PFX + "tpEdit", OBJPROP_TEXT)));
      ChartRedraw(0);
      return;
     }
   if(sparam == PFX + "fillCur")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      FillCurrentSLTP();
      ChartRedraw(0);
      return;
     }
  }
//+------------------------------------------------------------------+
