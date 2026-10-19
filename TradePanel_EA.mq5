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
//|  by InpMagic) - the stats row, CLOSE ALL, 25/50/75% partial     |
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
#property version   "2.01"
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
input int    InpMagic              = 20261014;   // magic tag applied to trades THIS panel opens -
                                                  // stats/close/SL-TP are always scoped to this magic only
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
input bool          InpShowMAs     = true;
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
input int    InpSigDrawDays         = 7;      // only signals from the last N CALENDAR DAYS are
                                               // drawn/logged/kept on the chart - converted to a bar count
                                               // internally per the chart's own timeframe (so "7" means the
                                               // same real time on M5 or M15, unlike a raw bar count), and
                                               // purged continuously every new bar (not just once a day)
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
input color  InpEmaCrossBuyCol     = clrLime;
input color  InpEmaCrossSellCol    = C'255,80,0';
input color  InpEmaCrossStopCol    = clrRed;
input color  InpEmaCrossTPCol      = clrYellow;
input double InpEmaCrossArrowOffsetATR = 1.0; // own offset so it never sits on top of the stochastic overlay's
input double InpEmaCrossExitOffsetATR  = 1.2; // own markers (independent overlay, never touches posDir/lastArr above)
input int    InpEmaCrossArrowSize  = 1;
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
input bool   InpEmaWeakenAlert      = true;   // push notification when this fires


CTrade trade;

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
   trade.SetExpertMagicNumber(InpMagic);
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
   if(PositionGetInteger(POSITION_MAGIC) != InpMagic) return false;
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
void PurgeOldSegments(const datetime latestBarTime, const int historyBars)
  {
   datetime cutoff = latestBarTime - (datetime)((long)historyBars * PeriodSeconds(PERIOD_CURRENT));
   for(int i = ObjectsTotal(0, 0, OBJ_TREND) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, OBJ_TREND);
      if(StringFind(nm, g_pm) != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < cutoff) ObjectDelete(0, nm);
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
   int maxHist = InpMAHistoryBars;
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
      if(InpMAHistoryBars < InpVwapHistoryBars) maxHist = InpVwapHistoryBars;
     }
   if(InpShowMAs || InpShowVWAP) PurgeOldSegments(tB, maxHist);
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
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, isBuy ? "EMA21/50 cross BUY (validated, Gold longs %PF=1.031 - hold to next opposite cross)"
                                                   : "EMA21/50 cross SELL (same construction - validated on Gold LONGS only, shorts not separately confirmed)");
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
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, wasLong ? "EMA21/50 cross EXIT-LONG (next opposite cross - the validated exit)"
                                                     : "EMA21/50 cross EXIT-SHORT (next opposite cross - the validated exit)");
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
   int total = backfill ? available : MathMin(available, minBars + 500);
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
            lastMarkerPrice = dotPrice; lastMarkerTime = t;
            DrawEmaCrossDot(exId, t, dotPrice, wasLong);
            PrintFormat("EmaCrossSignal LOG: %s EXIT-%s @ %s  E21=%s E50=%s (closing posDir %d -> 0)",
                        TimeToString(t, TIME_DATE | TIME_MINUTES), wasLong ? "LONG" : "SHORT",
                        DoubleToString(e21[i], _Digits), DoubleToString(e50[i], _Digits), prevPosDir);
            if(!backfill && InpEmaCrossAlert)
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
               lastMarkerPrice = entryPrice; lastMarkerTime = t;
               DrawEmaCrossArrow(lastArr, t, entryPrice, isBuy);
               DrawSigLevel(lastSl, t, t + InpEmaCrossLineBars * perSec, stop, InpEmaCrossStopCol, STYLE_SOLID,
                            "EMA-cross SL: recent " + IntegerToString(InpEmaCrossSwingBars) + "-bar swing (reference only - validated exit is the next opposite EMA cross)");
               DrawSigLevel(lastTp, t, t + (InpEmaCrossLineBars + 2) * perSec, tp, InpEmaCrossTPCol, STYLE_DASH,
                            "EMA-cross TP: 1:" + DoubleToString(InpEmaCrossRR, 1) + " R:R example (reference only, not the validated exit)");
               PrintFormat("EmaCrossSignal LOG: %s ENTRY %s @ %s  E21=%s E50=%s  posDir->%d",
                           TimeToString(t, TIME_DATE | TIME_MINUTES), isBuy ? "BUY" : "SELL",
                           DoubleToString(e21[i], _Digits), DoubleToString(e50[i], _Digits), posDir);
               if(!backfill && InpEmaCrossAlert)
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
                  lastMarkerPrice = wkPrice; lastMarkerTime = t;
                  DrawEmaWeakenMarker(wkId, t, wkPrice, wasLong);
                  PrintFormat("EmaWeakenSignal LOG: %s WEAKENING in %s run @ %s  gap=%s (peak was %s, %d declining bars)",
                              TimeToString(t, TIME_DATE | TIME_MINUTES), wasLong ? "LONG" : "SHORT",
                              DoubleToString(c[i], _Digits), DoubleToString(gap, _Digits),
                              DoubleToString(runMaxGap, _Digits), declineCount);
                  if(!backfill && InpEmaWeakenAlert)
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

//+------------------------------------------------------------------+
//| v1.47: rolling cap on EMA-cross overlay objects, same idea as        |
//| PurgeOldSigObjects() above.                                          |
//+------------------------------------------------------------------+
void PurgeOldEmaCrossObjects()
  {
   datetime cutoff = iTime(_Symbol, PERIOD_CURRENT, 1) - (datetime)((long)InpSigDrawDays * 86400);
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, g_emax) != 0) continue;
      if((datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0) < cutoff) ObjectDelete(0, nm);
     }
  }

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

   MkLabel("title", 10, 4, "TRADE PANEL  (drag here to move)", clrWhite, 9);

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
   ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);   // required for the manual title-bar drag handler

   //--- hard proof of what settings this EA instance actually initialized
   //--- with - check this line in the Experts log any time there's doubt
   //--- about whether a changed input actually took effect, rather than
   //--- trusting the Properties dialog alone
   PrintFormat("TradePanel v2.0 OnInit: showEmaCross=%s",
               InpShowEmaCrossSignals ? "true" : "false");

   ApplyTheme();
   SetupMAs();
   //--- backfill BEFORE building the panel - otherwise the whole historical
   //--- MA/VWAP backfill gets created AFTER the panel and buries it from the
   //--- moment of attach, not just until the first new bar's RebuildPanel()
   //--- call (same creation-order reasoning as RebuildPanel's own header).
   BackfillOverlayLines();
   ResyncEmaCrossSignals();
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
   if(g_maHandle21 != INVALID_HANDLE) IndicatorRelease(g_maHandle21);
   if(g_maHandle50  != INVALID_HANDLE) IndicatorRelease(g_maHandle50);
   if(g_maHandle200 != INVALID_HANDLE) IndicatorRelease(g_maHandle200);
   if(g_atrHandleCross != INVALID_HANDLE) IndicatorRelease(g_atrHandleCross);
  }

//+------------------------------------------------------------------+
//| True while the user is actively typing in any of this panel's     |
//| edit boxes. Previously checked OBJPROP_SELECTED, which depends on |
//| OBJPROP_SELECTABLE being true on the edit object - but SELECTABLE |
//| has to be FALSE for an OBJ_EDIT to enter text-edit mode on click  |
//| at all (true just selects/drags it instead). So this is now a     |
//| plain flag, set true on CHARTEVENT_OBJECT_CLICK for one of these  |
//| boxes and cleared on CHARTEVENT_OBJECT_ENDEDIT - both of which    |
//| fire regardless of SELECTABLE.                                    |
//+------------------------------------------------------------------+
bool g_editFocused = false;

bool AnyEditFocused()
  {
   return g_editFocused;
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
   if(InpShowEmaCrossSignals)
     {
      ComputeEmaCrossSignals(false);
      PurgeOldEmaCrossObjects();
     }
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
   ChartSetInteger(0, CHART_SHOW_TRADE_LEVELS, InpShowTradeLevels);
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
   //--- MT5 normally re-runs OnDeinit/OnInit on a period switch, which already
   //--- resyncs; this is the backstop for terminals/builds that only raise
   //--- CHART_CHANGE. The period comparison filters out plain scroll/zoom.
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      if(g_emaxPeriod != (ENUM_TIMEFRAMES)_Period)
        {
         ResyncEmaCrossSignals();
         if(!g_dragging && !AnyEditFocused()) RebuildPanel();
        }
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
   if(sparam == PFX + "lotMinus") { AdjustLot(-SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)); ChartRedraw(0); return; }
   if(sparam == PFX + "lotPlus")  { AdjustLot(+SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)); ChartRedraw(0); return; }
   if(sparam == PFX + "cntMinus") { AdjustCount(-1); ChartRedraw(0); return; }
   if(sparam == PFX + "cntPlus")  { AdjustCount(+1); ChartRedraw(0); return; }
   if(sparam == PFX + "delayMinus") { AdjustArmSeconds(-1); ChartRedraw(0); return; }
   if(sparam == PFX + "delayPlus")  { AdjustArmSeconds(+1); ChartRedraw(0); return; }
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
