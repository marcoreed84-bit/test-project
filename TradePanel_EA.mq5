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
#property version   "1.45"
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

input group "=== Moving averages (hand-drawn in the project's own colours, same idiom as the other EAs) ==="
input bool          InpShowMAs     = true;
input ENUM_MA_METHOD InpMAMethod   = MODE_EMA;    // MODE_EMA = exponential, MODE_SMA = simple
input int            InpMA21      = 21;
input int            InpMA50      = 50;
input int            InpMA200     = 200;
input color          InpCol21     = clrYellow;        // same colour family as the other EAs' MA21
input color          InpCol50     = C'255,140,0';     // neon orange - same family as the other EAs' MA50
input color          InpCol200    = C'191,0,255';     // neon purple
input int            InpMAHistoryBars = 150;          // rolling window of drawn MA history, PER LINE -
                                                       // 2500 (the old default) meant 2500 x 3 lines =
                                                       // 7500 chart objects, which is what was actually
                                                       // behind the general chart hang and the panel taking
                                                       // minutes to reclaim top paint order after a drag -
                                                       // every new bar has to scan/manage all of them.
                                                       // 300 is still ~3 days of M15 history visible; raise
                                                       // it only if you need more and accept the cost.

input group "=== 21/50 MA cross-proximity push alert (fires on PERIOD_CURRENT - attach this panel to the same chart/timeframe as whichever strategy EA you want warned about) ==="
input bool   InpEnableCrossAlert   = true;
input double InpCrossAlertATRMult  = 0.3;    // "near" threshold: alert once the 21/50 gap closes to
                                              // within this many ATR - smaller = later/tighter warning,
                                              // larger = earlier but noisier
input int    InpCrossATRPeriod     = 14;
input int    InpCrossAlertCooldownMin = 30;  // minimum minutes between alerts for the SAME approach,
                                              // so a gap oscillating right at the threshold doesn't spam

input group "=== Session VWAP (MT5 has no built-in VWAP - drawn manually, same construction as Aurelius_EA.mq5) ==="
input bool   InpShowVWAP           = true;
input color  InpColVWAP            = C'0,255,255';    // neon aqua - same family as the other EAs' VWAP
input int    InpVwapHistoryBars    = 400;

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

input group "=== Classic/textbook Stochastic signal overlay - UNVALIDATED (VISUAL ONLY - never places, modifies or closes anything) ==="
input bool   InpShowStochSignals   = true;
input int    InpSigKPeriod         = 21;      // %K period
input int    InpSigSlowing         = 5;       // slowing
input int    InpSigDPeriod         = 5;       // %D period
enum ENUM_SIG_STOCH_METHOD
  {
   SIG_STOCH_SUM      = 0,   // Simple - sum num/den separately over the slowing window then divide
   SIG_STOCH_SMA      = 1,   // Simple - plain SMA of the raw per-bar %K ("textbook" convention)
   SIG_STOCH_SMOOTHED = 2    // Smoothed (SMMA) - matches MT5's native Stochastic "Method: Smoothed"
  };
input ENUM_SIG_STOCH_METHOD InpSigStochMethod = SIG_STOCH_SMA;
                                               // v1.34: confirmed via user's native MT5 Stochastic Properties
                                               // dialog screenshot that their indicator's Method is set to
                                               // "Smoothed", not "Simple" - neither of the two old SMA-family
                                               // options (SIG_STOCH_SUM/SIG_STOCH_SMA, formerly toggled by
                                               // InpSigUseSumSlowing) could ever have matched that, which is
                                               // exactly why that toggle produced "nothing changed." Smoothed
                                               // (SMMA) is a different recursive formula, not an SMA variant -
                                               // this now implements it properly for both the %K slowing step
                                               // and the %D line (MT5 applies the same Method to both).
input double InpSigZoneLow         = 20.0;    // oversold zone (buy cross must be below this)
input double InpSigZoneHigh        = 80.0;    // overbought zone (sell cross must be above this)
input bool   InpSigUseInterpCross  = true;    // TRUE (v1.37, NEW): qualify using the INTERPOLATED point
                                               // where the %K/%D line segments actually cross between
                                               // bar i-1 and bar i (linear interpolation, matching the
                                               // literal "X" where the two lines visually meet on the
                                               // chart) - instead of either bar's raw endpoint value. A
                                               // fast-moving bar can jump from inside the zone to outside
                                               // it between two closes; the endpoint-only check (FALSE)
                                               // can miss that cross entirely even though the lines
                                               // visually crossed well inside the zone. Per direct request
                                               // after a disputed real chart cross: K[i-1]=24.550 (inside
                                               // a 30 zone) -> K[i]=36.706 (not) - the interpolated
                                               // crossing value computed to ~33.3, which does NOT qualify
                                               // even under a 30 zone (still above it) - this mode gets
                                               // closer to "where the lines visually meet" than the old
                                               // endpoint-only check, but it's still a real number from
                                               // the actual bar data, not a guarantee every visually-close
                                               // cross will now qualify.
input int    InpSigSwingBars       = 10;      // "recent swing" = plain N-bar lowest low / highest high
                                               // for the stop, as retail articles typically describe
input double InpSigRR              = 2.0;     // R:R convention - a representative example, not validated
input int    InpSigDrawDays         = 7;      // v1.39: only signals from the last N CALENDAR DAYS are
                                               // drawn/logged/kept on the chart - converted to a bar count
                                               // internally per the chart's own timeframe (so "7" means the
                                               // same real time on M5 or M15, unlike a raw bar count), and
                                               // purged continuously every new bar (not just once a day -
                                               // tighter than a daily sweep, never lets a day's backlog
                                               // build up first) - see 1.39 header note
input int    InpSigLineBars        = 8;      // stop-line length in bars; the TP line runs 2 bars longer
                                               // so the two levels stay readable when they sit close together
input double InpSigMinMarkerGapATR = 1.0;     // v1.40: minimum price gap (in ATR) kept between ANY two
                                               // signal markers that land close together in time - fixes
                                               // a reported buy-arrow/exit-dot overlap during a tight,
                                               // low-range consolidation
input int    InpSigMarkerLookbackBars = 5;    // v1.40: only markers within this many bars of each other are
                                               // checked for the above - markers far apart in time are left
                                               // alone even if coincidentally close in price
input int    InpSigArrowSize        = 1;      // v1.44: entry arrow width/size (MT5 OBJPROP_WIDTH, 1-5)
input int    InpSigDotSize          = 2;      // v1.44: exit dot width/size (MT5 OBJPROP_WIDTH, 1-5)
input color  InpSigBuyCol          = C'0,150,255';
input color  InpSigSellCol         = C'255,0,200';
input color  InpSigStopCol         = clrRed;
input color  InpSigTPCol           = C'0,255,0';
input bool   InpSigZoneAlert       = true;    // EARLY heads-up push+sound when %K first enters the
                                               // oversold/overbought zone - before any cross is confirmed,
                                               // so before an arrow/signal is printed
input bool   InpSigCrossAlert      = true;    // push+sound when the actual cross-in-zone signal prints
input string InpSigSoundFile       = "alert.wav";   // must exist in the terminal's Sounds folder
input double InpSigArrowOffsetATR  = 0.5;     // how far ENTRY arrows sit from the candle, in ATR(14) multiples
                                               // (0 = touching the candle like before)

input group "=== Classic/textbook Stochastic EXIT signal overlay - UNVALIDATED (own settings, independent of entry) ==="
input bool   InpShowExitSignals    = true;    // master on/off for exit dots - entry overlay above is unaffected
input int    InpExitKPeriod        = 21;      // exit stochastic %K period (can differ from the entry one)
input int    InpExitSlowing        = 5;       // exit stochastic slowing
input int    InpExitDPeriod        = 5;       // exit stochastic %D period
input bool   InpSigExitAlert       = true;    // push+sound when an exit dot prints (live only)
input double InpSigExitOffsetATR   = 1.0;     // how far EXIT dots sit from the candle, in ATR(14) multiples -
                                               // bigger than the entry offset so the two never overlap

input group "=== Midline-cross signal overlay - EXPERIMENTAL, UNVALIDATED (separate construction, not combined with the entry/exit above) ==="
input bool   InpShowMidlineSignals = true;    // per direct request, now on by default (was off) - a genuinely different, less-tested idea than
                                               // the zone-cross entry above (backtested full-history %PF~0.65,
                                               // still a net loser - see project research notes)
input double InpMidlineBandLow     = 40.0;    // %K must be inside this band on the cross bar (not a deep
input double InpMidlineBandHigh    = 60.0;    // zone extreme - a cross back through the 50 midline instead)
input int    InpMidlinePriorLookback = 10;    // %K must have dipped (buy) / risen (sell) to 50 within this
                                               // many preceding bars - confirms a genuine pullback, not noise
                                               // sitting near 50
input color  InpMidlineBuyCol      = clrYellow;
input color  InpMidlineSellCol     = clrOrange;
input double InpMidlineOffsetATR   = 0.8;     // own offset so it never sits on top of the entry arrows/exit dots

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
//--- own prefix, disjoint from both PFX and g_pm, for the same reason as above:
//--- neither RebuildPanel()'s sweep nor PurgeOldSegments() may touch these.
string g_sig = "TPSIG_";
//--- an EA's globals SURVIVE a timeframe switch (only OnDeinit/OnInit re-run),
//--- so this is what lets CHARTEVENT_CHART_CHANGE tell a real period change
//--- apart from an ordinary scroll/zoom.
ENUM_TIMEFRAMES g_sigPeriod = PERIOD_CURRENT;
#define SIG_NA EMPTY_VALUE   // stands in for the Python reference's NaN

//--- latches for the two stoch-overlay alert stages, so each only fires
//--- ONCE per excursion/signal rather than spamming every tick it stays
//--- true. Cleared back to false once %K leaves the zone again.
bool g_sigZoneAlertedLong  = false;
bool g_sigZoneAlertedShort = false;
//--- persisted entry/exit overlay state, carried across LIVE calls to
//--- ComputeStochSignals() so a live call only ever needs to look at a
//--- small recent window instead of re-walking the WHOLE loaded chart
//--- history on every new bar - see that function's own header for why
//--- this matters (it was the real cause of charts hanging).
int    g_sigLastDir = 0;
string g_sigLastArr = "", g_sigLastSl = "", g_sigLastTp = "";
int    g_sigPosDir  = 0;
//--- the newest bar a LIVE call has actually processed - lets the next
//--- live call catch up on every bar since, not just assume exactly one
//--- new bar happened (a stall/hang, or the EA being briefly detached,
//--- can let several bars close in between)
datetime g_sigLastProcessedBar = 0;
//--- 1.40: the price/time of the most recently drawn signal marker (entry
//--- arrow OR exit dot), persisted across live calls the same way as the
//--- state above - lets a new marker check for a near-collision against
//--- whatever was drawn just before it, even on a DIFFERENT bar (not just
//--- the same-bar case the old stacking logic handled) - see
//--- NudgeAwayFromLastMarker()'s own header for why this was needed.
double   g_sigLastMarkerPrice = 0.0;
datetime g_sigLastMarkerTime  = 0;

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
                  const datetime tNew, const double vNew, const color col)
  {
   string nm = g_pm + tag + "_" + IntegerToString((long)tNew);
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_TREND, 0, tOld, vOld, tNew, vNew);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
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
//| Called once per new bar - draws exactly one new segment per line |
//| (MAs + VWAP), same as Aurelius's UpdateMALines.                  |
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
         DrawSegment("21", tA, a21, tB, b21, InpCol21);
      if(MAValue(g_maHandle50, 2, a50) && MAValue(g_maHandle50, 1, b50))
         DrawSegment("50", tA, a50, tB, b50, InpCol50);
      if(MAValue(g_maHandle200, 2, a200) && MAValue(g_maHandle200, 1, b200))
         DrawSegment("200", tA, a200, tB, b200, InpCol200);
     }
   if(InpShowVWAP && !DifferentSession(2, 1))
     {
      double vA = SessionVWAP(2), vB = SessionVWAP(1);
      if(vA > 0.0 && vB > 0.0) DrawSegment("vwap", tA, vA, tB, vB, InpColVWAP);
      if(InpMAHistoryBars < InpVwapHistoryBars) maxHist = InpVwapHistoryBars;
     }
   if(InpShowMAs || InpShowVWAP) PurgeOldSegments(tB, maxHist);
  }

//+------------------------------------------------------------------+
//| Called once from OnInit - walks backward and draws the whole      |
//| rolling window immediately, same reasoning as Aurelius's          |
//| BackfillMALines (otherwise a fresh attach shows a 1-bar stub and  |
//| takes the full history window to fill in).                        |
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
         if(MAValue(g_maHandle21,  s + 1, a) && MAValue(g_maHandle21,  s, b)) DrawSegment("21",  tA, a, tB, b, InpCol21);
         if(MAValue(g_maHandle50,  s + 1, a) && MAValue(g_maHandle50,  s, b)) DrawSegment("50",  tA, a, tB, b, InpCol50);
         if(MAValue(g_maHandle200, s + 1, a) && MAValue(g_maHandle200, s, b)) DrawSegment("200", tA, a, tB, b, InpCol200);
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
         if(vA > 0.0 && vB > 0.0) DrawSegment("vwap", tA, vA, tB, vB, InpColVWAP);
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
//| Price field Low/High: lowest LOW / highest HIGH over kp bars.      |
//| Slowing as MT5 does it: sum(close-LL)/sum(HH-LL) over `slow` bars, |
//| i.e. a simple (SMA) smoothing; %D = SMA(dp) of %K.                 |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Three stochastic averaging conventions, selectable via            |
//| InpSigStochMethod:                                                 |
//|  SIG_STOCH_SUM/SIG_STOCH_SMA - both Simple/SMA-family (see enum    |
//|  comments above) - these were the only two options before v1.34.  |
//|  SIG_STOCH_SMOOTHED - MT5 native "Method: Smoothed" (SMMA), a      |
//|  genuinely different recursive formula, applied to BOTH the %K     |
//|  slowing step and the %D line (MT5 applies the same Method to      |
//|  both - confirmed from the user's own Properties dialog showing    |
//|  a single Method dropdown governing the whole indicator).          |
//|  SMMA: seed = SMA of the first `period` values; thereafter         |
//|  smma[i] = (smma[i-1]*(period-1) + value[i]) / period.             |
//+------------------------------------------------------------------+
void SigClassicStoch(const double &h[], const double &l[], const double &c[], const int n,
                     const int kp, const int slow, const int dp, double &k[], double &d[],
                     const ENUM_SIG_STOCH_METHOD method = SIG_STOCH_SMOOTHED)
  {
   ArrayResize(k, n); ArrayInitialize(k, SIG_NA);
   ArrayResize(d, n); ArrayInitialize(d, SIG_NA);
   double num[], den[], rawK[];
   ArrayResize(num, n); ArrayResize(den, n); ArrayResize(rawK, n);
   ArrayInitialize(num, 0.0); ArrayInitialize(den, 0.0); ArrayInitialize(rawK, 0.0);
   for(int i = kp - 1; i < n; i++)
     {
      double lo = l[i], hi = h[i];
      for(int j = i - kp + 1; j < i; j++) { if(l[j] < lo) lo = l[j]; if(h[j] > hi) hi = h[j]; }
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
         k[i] = (sd > 0.0) ? 100.0 * sn / sd : 100.0;   // MT5 returns 100 on a zero range
        }
     }
   else if(method == SIG_STOCH_SMA)
     {
      for(int i = kStart; i < n; i++)
        {
         double s = 0.0;
         for(int j = i - slow + 1; j <= i; j++) s += rawK[j];
         k[i] = s / slow;   // plain SMA of the raw per-bar %K ("textbook" convention)
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
void DrawSigArrow(const string nm, const datetime t, const double price, const bool isBuy)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, isBuy ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, isBuy ? InpSigBuyCol : InpSigSellCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
   //--- 1.44: now user-settable (InpSigArrowSize, was hardcoded 1 in 1.41) -
   //--- OBJ_ARROW_UP/DOWN are already solid filled triangles, not outlines,
   //--- so there's nothing further to do for "solid colour" beyond this
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpSigArrowSize);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, isBuy ? "Classic stoch BUY signal (textbook rule, UNVALIDATED, visual only)" : "Classic stoch SELL signal (textbook rule, UNVALIDATED, visual only)");
  }

//+------------------------------------------------------------------+
//| Solid dot for an EXIT signal - same color family as the position   |
//| being exited, Wingdings code 159 = filled circle.                  |
//+------------------------------------------------------------------+
void DrawSigDot(const string nm, const datetime t, const double price, const bool wasLong)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_ARROWCODE, 159);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, wasLong ? InpSigBuyCol : InpSigSellCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpSigDotSize);   // 1.44: now user-settable (was hardcoded 2 in 1.41)
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, wasLong ? "Classic stoch EXIT-LONG signal (own settings, UNVALIDATED, visual only)"
                                                     : "Classic stoch EXIT-SHORT signal (own settings, UNVALIDATED, visual only)");
  }

//+------------------------------------------------------------------+
//| Diamond marker (Wingdings 117) for a MIDLINE-CROSS signal -           |
//| deliberately a different shape from both the arrows (zone-cross       |
//| entry) and the dots (exit), so this separate/experimental overlay     |
//| can never be visually confused with the main one.                     |
//+------------------------------------------------------------------+
void DrawMidlineMarker(const string nm, const datetime t, const double price, const bool isBuy)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_ARROWCODE, 117);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, isBuy ? InpMidlineBuyCol : InpMidlineSellCol);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 3);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, (isBuy ? "MIDLINE-CROSS BUY" : "MIDLINE-CROSS SELL") +
                   " (experimental, UNVALIDATED - backtested net loser, visual only, not combined with the entry/exit overlay above)");
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
//| EARLY heads-up, fired the moment %K first enters the oversold/     |
//| overbought zone on a newly-closed bar - i.e. BEFORE any cross is   |
//| confirmed and BEFORE ComputeStochSignals() below would print an    |
//| arrow. Latches so it fires once per excursion into the zone, not   |
//| every bar it stays there; clears once %K leaves the zone again so  |
//| the NEXT excursion can alert too.                                  |
//+------------------------------------------------------------------+
void CheckStochZoneAlert(const double kCur)
  {
   if(!InpSigZoneAlert || kCur == SIG_NA) return;
   string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);

   if(kCur <= InpSigZoneLow)
     {
      if(!g_sigZoneAlertedLong)
        {
         FireSigAlert(StringFormat(
            "%s %s: Stochastic %%K=%.1f entered OVERSOLD (<=%.0f) - watch for a BUY cross-in-zone "
            "signal (not printed yet - UNVALIDATED, visual only)", _Symbol, tf, kCur, InpSigZoneLow));
         g_sigZoneAlertedLong = true;
        }
     }
   else g_sigZoneAlertedLong = false;

   if(kCur >= InpSigZoneHigh)
     {
      if(!g_sigZoneAlertedShort)
        {
         FireSigAlert(StringFormat(
            "%s %s: Stochastic %%K=%.1f entered OVERBOUGHT (>=%.0f) - watch for a SELL cross-in-zone "
            "signal (not printed yet - UNVALIDATED, visual only)", _Symbol, tf, kCur, InpSigZoneHigh));
         g_sigZoneAlertedShort = true;
        }
     }
   else g_sigZoneAlertedShort = false;
  }

//+------------------------------------------------------------------+
//| Recomputes the ENTRY stochastic (and, if enabled, a fully           |
//| independent EXIT stochastic with its own K/slowing/D settings)      |
//| over the whole loaded CLOSED history (the forming bar is excluded,  |
//| so nothing here can repaint), then draws either every signal        |
//| (backfill) or only the newest closed bar's.                         |
//|                                                                     |
//| EXIT RULE (own settings, no zone requirement - the usual "textbook" |
//| exit-on-opposite-cross, not restricted to 20/80): fires the first   |
//| time the EXIT stochastic crosses against the currently-shown ENTRY  |
//| direction, i.e. only while an entry arrow is "open" (no entry has   |
//| fired yet in the other direction). A single pass walks the whole    |
//| history in time order so the entry/exit state machine (long / short |
//| / flat) is reconstructed correctly either way - during backfill it  |
//| draws as it goes; for a live single-bar call it replays silently    |
//| up to the last-but-one bar to recover state, then draws only the    |
//| newest bar.                                                         |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| backfill=true (attach / timeframe switch, runs ONCE): walks the      |
//| whole loaded chart history, same as always.                          |
//| backfill=false (every new bar, now also polled every 2s by the       |
//| timer): used to ALSO re-copy and re-compute the stochastic (TWICE,   |
//| since 1.24 added the exit one) plus ATR over that SAME entire        |
//| history, every single call - on a full-history low-timeframe chart   |
//| (hundreds of thousands of bars) that is real, repeated, heavy work   |
//| landing on the UI thread every time a bar closes, and was the real   |
//| cause of charts hanging. A live call only ever needs the ONE newest  |
//| closed bar's cross, so it now copies/computes a small bounded        |
//| window instead, and lastDir/lastArr/lastSl/lastTp/posDir are         |
//| persisted in g_sigLastDir/g_sigLastArr/.../g_sigPosDir ACROSS live   |
//| calls (reset in ResyncStochSignals(), same as the zone-alert         |
//| latches) instead of being reconstructed by re-walking history every  |
//| time.                                                                 |
//+------------------------------------------------------------------+
void ComputeStochSignals(const bool backfill)
  {
   int minBarsEntry = InpSigKPeriod + InpSigSlowing + InpSigDPeriod + InpSigSwingBars;
   int minBarsExit  = InpShowExitSignals ? (InpExitKPeriod + InpExitSlowing + InpExitDPeriod) : 0;
   int minBars = MathMax(minBarsEntry, minBarsExit);
   int available = Bars(_Symbol, PERIOD_CURRENT) - 1;
   //--- live calls need enough trailing bars for k[n-1]/k[n-2] (and the
   //--- exit/ATR equivalents) to be valid, PLUS enough slack to catch up
   //--- on every bar since g_sigLastProcessedBar in one go if several
   //--- closed back-to-back (a stall/hang, or the EA being briefly
   //--- detached, can do that) - NOT the whole multi-year history, but
   //--- comfortably more than "just the one newest bar"
   int total = backfill ? available : MathMin(available, minBars + 500);
   if(total < minBars) return;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 1, total, r);
   if(n < minBars) return;

   double c[], h[], l[];
   ArrayResize(c, n); ArrayResize(h, n); ArrayResize(l, n);
   for(int i = 0; i < n; i++) { c[i] = r[i].close; h[i] = r[i].high; l[i] = r[i].low; }

   double k[], d[];
   SigClassicStoch(h, l, c, n, InpSigKPeriod, InpSigSlowing, InpSigDPeriod, k, d, InpSigStochMethod);
   double kE[], dE[];
   if(InpShowExitSignals) SigClassicStoch(h, l, c, n, InpExitKPeriod, InpExitSlowing, InpExitDPeriod, kE, dE, InpSigStochMethod);
   double atr[];
   SigATR(h, l, c, n, 14, atr);

   //--- early zone-entry alert - live only (not during backfill, which
   //--- would otherwise fire hundreds of alerts for old history on attach)
   if(!backfill) CheckStochZoneAlert(k[n - 1]);

   int perSec = PeriodSeconds(PERIOD_CURRENT);
   //--- backfill draws/alerts for every qualifying bar across the whole
   //--- history. A live call draws/alerts for every bar NEWER than
   //--- g_sigLastProcessedBar - normally just the one newest bar, but
   //--- catches up properly if more than one closed since the last call
   //--- (see g_sigLastProcessedBar's own comment). Falls back to the
   //--- start of this window if nothing's been processed yet, or if the
   //--- gap is bigger than the window itself (a genuinely long stall) -
   //--- bounded by the window size either way, never the whole history.
   int from = minBars;
   if(!backfill)
     {
      for(int p = n - 1; p >= minBars; p--)
        {
         if(r[p].time <= g_sigLastProcessedBar) break;
         from = p;
        }
     }
   //--- 1.38/1.39: backfill still WALKS the whole history (cheap, O(n)
   //--- array math - keeps lastDir/posDir reconstructed correctly), but
   //--- only DRAWS (and logs) the last InpSigDrawDays worth of bars.
   //--- Drawing everything put tens of thousands of permanent objects on
   //--- the chart, plus one log line per historical cross - see the 1.38
   //--- header note. Days converted to bars per THIS chart's own
   //--- PERIOD_CURRENT, so the real time window is the same across
   //--- timeframes (a raw bar count was NOT - 2000 bars is ~20 days on
   //--- M15 but only ~7 on M5).
   int sigDrawBars = (int)MathMax(1.0, (double)InpSigDrawDays * 86400.0 / (double)PeriodSeconds(PERIOD_CURRENT));
   int drawFrom = backfill ? MathMax(from, n - sigDrawBars) : from;

   int lastDir, posDir;
   string lastArr, lastSl, lastTp;
   double lastMarkerPrice;
   datetime lastMarkerTime;
   if(backfill)
     {
      lastDir = 0; posDir = 0; lastArr = ""; lastSl = ""; lastTp = "";
      lastMarkerPrice = 0.0; lastMarkerTime = 0;
     }
   else
     {
      lastDir = g_sigLastDir; posDir = g_sigPosDir;
      lastArr = g_sigLastArr; lastSl = g_sigLastSl; lastTp = g_sigLastTp;
      lastMarkerPrice = g_sigLastMarkerPrice; lastMarkerTime = g_sigLastMarkerTime;
     }

   for(int i = from; i < n; i++)
     {
      bool draw = (i >= drawFrom);
      double offEntry = (atr[i] == SIG_NA) ? 0.0 : InpSigArrowOffsetATR * atr[i];
      double offExit   = (atr[i] == SIG_NA) ? 0.0 : InpSigExitOffsetATR  * atr[i];

      //--- tracked only when an entry ARROW is actually drawn this bar (see
      //--- the risk<=0.0 note below) - lets a same-bar exit stack off the
      //--- arrow instead of colliding with it
      bool entryDrawnThisBar = false;
      double entryDrawnPrice = 0.0;
      bool entryDrawnAbove = false;

      //--- 1.35: snapshot the position held coming INTO this bar, before the
      //--- ENTRY block below can overwrite posDir. The EXIT block must judge
      //--- (and label/color/stack) the exit against the OLD position - not a
      //--- brand-new one opened on this same bar. Before this fix: long, then
      //--- a bar with BOTH a sell cross-in-zone AND an exit-stoch cross down
      //--- flipped posDir to -1 first, so the exit check then demanded a
      //--- cross UP and the exit-long dot silently never drew (user-reported).
      //--- It also let a fresh entry from flat be "exited" on its own entry
      //--- bar by an opposite exit cross, wiping its lastArr/Sl/Tp.
      int  prevPosDir = posDir;
      bool entryFiredThisBar = false;   // qualifying entry (risk>0), drawn or not

      //--- ENTRY: %K/%D cross WITHIN the extreme zone (not a zone-exit rule)
      if(k[i] != SIG_NA && d[i] != SIG_NA && k[i - 1] != SIG_NA && d[i - 1] != SIG_NA)
        {
         bool crossUp   = k[i - 1] <= d[i - 1] && k[i] > d[i];
         bool crossDown = k[i - 1] >= d[i - 1] && k[i] < d[i];

         //--- 1.37: the value actually tested against the zone. Either the
         //--- plain bar-close k[i] (old behavior), or the value at the
         //--- INTERPOLATED point where the K/D line segments cross between
         //--- bar i-1 and bar i - linear interpolation on where (K-D) hits
         //--- zero, matching the literal "X" point where the two lines
         //--- visually meet on the chart, which can sit well inside the
         //--- zone even when the bar-CLOSE value has already moved outside
         //--- it (a fast-moving bar can jump straight through the zone).
         double zoneTestVal = k[i];
         if(InpSigUseInterpCross && (crossUp || crossDown))
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
         if(crossUp && zoneTestVal < InpSigZoneLow) dir = 1;
         else if(crossDown && zoneTestVal > InpSigZoneHigh) dir = -1;

         //--- 1.36: diagnostic only - every raw %K/%D cross on the entry
         //--- stoch gets logged unconditionally (not just ones that qualify
         //--- and draw), so a "the chart clearly crossed under 30 but no
         //--- entry fired" dispute can be settled from real numbers instead
         //--- of a chart screenshot. Separate from the cross+zone-qualifying
         //--- ENTRY log further below, which only prints when dir!=0.
         //--- Runs during backfill too (not just live) - a reattach re-walks
         //--- recent history, so this is the only way to get real numbers
         //--- for a cross that already happened before you went looking for
         //--- it, not just ones from this point forward. Crosses are rare
         //--- enough (a handful per day) that this isn't meaningful spam.
         if(draw && (crossUp || crossDown))
            PrintFormat("StochSignal RAWCROSS: %s %s  K[i-1]=%.3f D[i-1]=%.3f -> K[i]=%.3f D[i]=%.3f  "
                        "interpCrossVal=%.3f (interpUsed=%s)  zoneLow=%.1f zoneHigh=%.1f  qualifies=%s",
                        TimeToString(r[i].time, TIME_DATE | TIME_MINUTES), crossUp ? "crossUp" : "crossDown",
                        k[i - 1], d[i - 1], k[i], d[i], zoneTestVal, InpSigUseInterpCross ? "true" : "false",
                        InpSigZoneLow, InpSigZoneHigh, (dir != 0) ? "YES" : "NO(outside zone)");

         if(dir != 0)
           {
            //--- recent swing = lowest low / highest high of the last
            //--- InpSigSwingBars closed bars, signal bar included
            double swing = (dir > 0) ? l[i] : h[i];
            for(int j = i - InpSigSwingBars + 1; j < i; j++)
               swing = (dir > 0) ? MathMin(swing, l[j]) : MathMax(swing, h[j]);
            double risk = dir * (c[i] - swing);
            //--- risk<=0.0 (close sits exactly on the swing extreme - no sane
            //--- stop) now skips this bar ENTIRELY, not just the drawing: a
            //--- disqualified cross must NOT flip lastDir/posDir either, or
            //--- the exit overlay ends up "watching" a position that was
            //--- never actually shown, and later prints an exit in the
            //--- wrong direction/color with no entry arrow to explain it -
            //--- exactly what was happening before this fix.
            if(risk > 0.0)
              {
               if(draw)
                 {
                  if(!backfill && InpSigCrossAlert)
                    {
                     string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
                     FireSigAlert(StringFormat(
                        "%s %s: Classic stoch cross-in-zone %s signal PRINTED (K=%.1f) - chart overlay only, "
                        "UNVALIDATED, does not place/modify/close anything", _Symbol, tf, (dir > 0 ? "BUY" : "SELL"), k[i]));
                    }
                  //--- a repeat same-direction cross (e.g. %K/%D whipsawing against
                  //--- each other while both still sit inside the zone) REPLACES the
                  //--- previous same-run signal instead of adding a second one - the
                  //--- first one is often a premature whipsaw that goes against price
                  //--- before the real move starts
                  if(dir == lastDir && lastArr != "")
                    {
                     ObjectDelete(0, lastArr);
                     ObjectDelete(0, lastSl);
                     ObjectDelete(0, lastTp);
                    }
                 }
               lastDir = dir;
               posDir  = dir;   // new entry opens/flips the "position" the exit overlay watches
               entryFiredThisBar = true;

               if(draw)
                 {
                  double stop = swing;
                  double tp   = c[i] + dir * InpSigRR * risk;
                  datetime t = r[i].time;
                  string id = IntegerToString((long)t);
                  bool isBuy = dir > 0;
                  lastArr = g_sig + "arr_" + id;
                  lastSl  = g_sig + "sl_" + id;
                  lastTp  = g_sig + "tp_" + id;
                  entryDrawnThisBar = true;
                  entryDrawnAbove   = !isBuy;   // buy arrow sits BELOW, sell arrow ABOVE
                  entryDrawnPrice   = isBuy ? r[i].low - offEntry : r[i].high + offEntry;
                  //--- 1.40: general anti-collision against whatever marker was drawn
                  //--- just before this one (any type, possibly a different bar) - see
                  //--- NudgeAwayFromLastMarker()'s own header
                  double minGap = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
                  entryDrawnPrice = NudgeAwayFromLastMarker(entryDrawnPrice, t, !isBuy,
                                                             lastMarkerPrice, lastMarkerTime, minGap);
                  lastMarkerPrice = entryDrawnPrice; lastMarkerTime = t;
                  DrawSigArrow(lastArr, t, entryDrawnPrice, isBuy);
                  DrawSigLevel(lastSl, t, t + (InpSigLineBars)     * perSec, stop, InpSigStopCol, STYLE_SOLID,
                               "Classic SL: recent " + IntegerToString(InpSigSwingBars) + "-bar swing (unvalidated)");
                  DrawSigLevel(lastTp, t, t + (InpSigLineBars + 2) * perSec, tp,   InpSigTPCol,   STYLE_DASH,
                               "Classic TP: 1:" + DoubleToString(InpSigRR, 1) + " R:R example (unvalidated)");
                  //--- unconditional ground-truth log line (both backfill AND
                  //--- live, independent of InpSigCrossAlert) - scroll the
                  //--- Experts tab to see the EXACT entry/exit sequence the
                  //--- code actually recognized, if the chart's own colors/
                  //--- placement ever look wrong again
                  PrintFormat("StochSignal LOG: %s ENTRY %s @ %s  K[i-1]=%.3f D[i-1]=%.3f -> K[i]=%.3f D[i]=%.3f  posDir->%d",
                               TimeToString(t, TIME_DATE | TIME_MINUTES), isBuy ? "BUY" : "SELL",
                               DoubleToString(c[i], _Digits), k[i - 1], d[i - 1], k[i], d[i], posDir);
                 }
              }
           }
        }

      //--- MIDLINE-CROSS: fully independent experimental overlay - a cross
      //--- back through the 50 midline (not a deep 20/80 zone extreme)
      //--- after a genuine pullback, per direct request. Uses the SAME
      //--- entry stochastic (k/d) but a different trigger condition. Does
      //--- NOT touch posDir/lastDir/lastArr or interact with the entry/
      //--- exit overlay above in any way - purely additive, its own marker
      //--- shape, drawn (or not) independent of everything else in this loop.
      if(InpShowMidlineSignals && draw &&
         k[i] != SIG_NA && d[i] != SIG_NA && k[i - 1] != SIG_NA && d[i - 1] != SIG_NA &&
         k[i] >= InpMidlineBandLow && k[i] <= InpMidlineBandHigh)
        {
         bool mCrossUp   = k[i - 1] <= d[i - 1] && k[i] > d[i];
         bool mCrossDown = k[i - 1] >= d[i - 1] && k[i] < d[i];
         bool mDir = false; bool mFire = false;
         if(mCrossUp)
           {
            double lo = k[i];
            for(int j = MathMax(i - InpMidlinePriorLookback, 0); j < i; j++)
               if(k[j] != SIG_NA && k[j] < lo) lo = k[j];
            if(lo <= 50.0) { mFire = true; mDir = true; }
           }
         else if(mCrossDown)
           {
            double hi = k[i];
            for(int j = MathMax(i - InpMidlinePriorLookback, 0); j < i; j++)
               if(k[j] != SIG_NA && k[j] > hi) hi = k[j];
            if(hi >= 50.0) { mFire = true; mDir = false; }
           }
         if(mFire)
           {
            datetime mt = r[i].time;
            string mid = g_sig + "mid_" + IntegerToString((long)mt);
            double offMid = (atr[i] == SIG_NA) ? 0.0 : InpMidlineOffsetATR * atr[i];
            double mPrice = mDir ? r[i].low - offMid : r[i].high + offMid;
            DrawMidlineMarker(mid, mt, mPrice, mDir);
           }
        }

      //--- EXIT: only while "in position" per the entry overlay above, on
      //--- the EXIT stochastic's own (independently-set) %K/%D cross, in
      //--- the direction that closes that position - no zone requirement
      //--- (1.35: everything below reads prevPosDir - the position held
      //--- coming into this bar - never the possibly-just-flipped posDir)
      if(InpShowExitSignals && prevPosDir != 0 &&
         kE[i] != SIG_NA && dE[i] != SIG_NA && kE[i - 1] != SIG_NA && dE[i - 1] != SIG_NA)
        {
         bool exCrossUp   = kE[i - 1] <= dE[i - 1] && kE[i] > dE[i];
         bool exCrossDown = kE[i - 1] >= dE[i - 1] && kE[i] < dE[i];
         bool exitFires = (prevPosDir > 0 && exCrossDown) || (prevPosDir < 0 && exCrossUp);
         if(exitFires)
           {
            if(draw)
              {
               if(!backfill && InpSigExitAlert)
                 {
                  string tf = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);
                  FireSigAlert(StringFormat(
                     "%s %s: Classic stoch EXIT-%s signal PRINTED (ExitK=%.1f) - chart overlay only, "
                     "UNVALIDATED, does not place/modify/close anything", _Symbol, tf,
                     (prevPosDir > 0 ? "LONG" : "SHORT"), kE[i]));
                 }
               datetime t = r[i].time;
               string exId = g_sig + "exit_" + IntegerToString((long)t);
               bool wasLong = prevPosDir > 0;
               //--- 1.45: REVERTED the 1.43 "always anchor to the entry arrow's
               //--- own price" idea for the DIFFERENT-candle case - it broke
               //--- badly on any position that ran a real distance before
               //--- exiting (completely normal for a trending move): the exit
               //--- dot ended up pinned near the OLD entry price, floating in
               //--- empty space far from the actual exit candle, nowhere near
               //--- where the exit happened - confirmed from a live chart
               //--- showing dots stranded well above/below price action.
               //--- Two rules now:
               //--- (a) SAME-CANDLE case (1.44, kept - "a buy arrow printed,
               //--- and on the same candle an exit signal - the exit dot below
               //--- the buy arrow; same candle sell arrow - dot above the sell
               //--- arrow"): when a NEW entry arrow ALSO lands on this exact
               //--- bar, the dot follows THAT arrow's side and price.
               //--- (b) DIFFERENT-CANDLE case: back to the THIS bar's own
               //--- candle high/low (1.42's approach) - same side as the
               //--- direction being closed, but anchored to where the exit is
               //--- actually happening, not where the entry happened.
               bool dotAbove;
               double dotPrice;
               if(entryDrawnThisBar)
                 {
                  dotAbove = entryDrawnAbove;
                  dotPrice = dotAbove ? entryDrawnPrice + offExit : entryDrawnPrice - offExit;
                 }
               else
                 {
                  dotAbove = !wasLong;
                  dotPrice = dotAbove ? r[i].high + offExit : r[i].low - offExit;
                 }
               //--- 1.40: general anti-collision (covers the case above too, plus
               //--- any other marker combination/different-bar case the same-bar
               //--- stacking above doesn't reach) - see NudgeAwayFromLastMarker()'s
               //--- own header
               double minGapExit = (atr[i] == SIG_NA) ? 0.0 : InpSigMinMarkerGapATR * atr[i];
               dotPrice = NudgeAwayFromLastMarker(dotPrice, t, dotAbove,
                                                   lastMarkerPrice, lastMarkerTime, minGapExit);
               lastMarkerPrice = dotPrice; lastMarkerTime = t;
               DrawSigDot(exId, t, dotPrice, wasLong);
               //--- same unconditional ground-truth log line as the entry side
               PrintFormat("StochSignal LOG: %s EXIT-%s @ %s  ExitK[i-1]=%.3f ExitD[i-1]=%.3f -> ExitK[i]=%.3f ExitD[i]=%.3f  (closing posDir %d -> 0)",
                            TimeToString(t, TIME_DATE | TIME_MINUTES), wasLong ? "LONG" : "SHORT",
                            DoubleToString(c[i], _Digits), kE[i - 1], dE[i - 1], kE[i], dE[i], prevPosDir);
              }
            //--- 1.35: if an entry ALSO fired this bar, this is "exit the old
            //--- position AND open the new one on the same bar" - posDir and
            //--- lastArr/Sl/Tp already belong to that NEW entry (and the old
            //--- run's objects were never put back into lastArr), so leave
            //--- them alone. Only go flat/clear when no entry fired this bar.
            if(!entryFiredThisBar)
              {
               posDir = 0;   // flat again - next entry (either direction) re-arms the exit watch
               //--- 1.29: the previous entry's run is now CLOSED by this exit, so
               //--- its arrow/SL/TP must never again be eligible for the "repeat
               //--- same-direction cross replaces the previous signal" delete -
               //--- otherwise a later same-side entry erases an arrow whose exit
               //--- dot is still on the chart (an orphaned exit dot)
               lastArr = ""; lastSl = ""; lastTp = "";
              }
           }
        }
     }

   //--- always write back (backfill included) - a backfill run freshly
   //--- reconstructs the correct end-of-history state, so the very next
   //--- LIVE call must continue from THAT, not from zero/empty
   g_sigLastDir = lastDir; g_sigPosDir = posDir;
   g_sigLastArr = lastArr; g_sigLastSl = lastSl; g_sigLastTp = lastTp;
   g_sigLastProcessedBar = r[n - 1].time;
   g_sigLastMarkerPrice = lastMarkerPrice; g_sigLastMarkerTime = lastMarkerTime;
  }

//+------------------------------------------------------------------+
//| 1.38: rolling cap on overlay objects, same idea as PurgeOldSegments |
//| for the MA/VWAP lines. Without it every arrow/SL/TP/dot ever drawn  |
//| stayed on the chart until the next full resync, so the object count |
//| only ever grew over a long live session. Uses OBJPROP_TIME (the     |
//| signal bar) - an object whose name is still held in g_sigLastArr    |
//| may get purged here; the later ObjectDelete on it is a harmless     |
//| no-op.                                                               |
//+------------------------------------------------------------------+
void PurgeOldSigObjects()
  {
   //--- 1.39: cutoff is now a straight calendar-time window (InpSigDrawDays),
   //--- not bars*periodSeconds - simpler and timeframe-independent by
   //--- construction, no conversion needed here.
   datetime cutoff = iTime(_Symbol, PERIOD_CURRENT, 1) - (datetime)((long)InpSigDrawDays * 86400);
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, g_sig) != 0) continue;
      if((datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0) < cutoff) ObjectDelete(0, nm);
     }
  }

//+------------------------------------------------------------------+
//| Full wipe + backfill - on attach, and on a timeframe switch, since |
//| every level is timeframe-specific and must not be left stale.      |
//+------------------------------------------------------------------+
void ResyncStochSignals()
  {
   ObjectsDeleteAll(0, g_sig);
   g_sigPeriod = (ENUM_TIMEFRAMES)_Period;
   //--- zone-alert latches are per-timeframe state; a fresh timeframe's
   //--- %K has nothing to do with the old one's zone excursion. The
   //--- persisted entry/exit state (g_sigLastDir/g_sigPosDir/...) doesn't
   //--- need an explicit reset here - ComputeStochSignals(true) right
   //--- below always writes it back, freshly reconstructed for the new
   //--- timeframe's own history, so this is just a safe default in case
   //--- that backfill bails out early (too little history loaded yet).
   g_sigZoneAlertedLong  = false;
   g_sigZoneAlertedShort = false;
   g_sigLastDir = 0; g_sigPosDir = 0;
   g_sigLastArr = ""; g_sigLastSl = ""; g_sigLastTp = "";
   g_sigLastProcessedBar = 0;
   g_sigLastMarkerPrice = 0.0; g_sigLastMarkerTime = 0;
   if(InpShowStochSignals) ComputeStochSignals(true);
  }

//+------------------------------------------------------------------+
void SetupMAs()
  {
   //--- handles are needed for the cross-proximity alert even when the lines
   //--- themselves aren't drawn (InpShowMAs only gates UpdateOverlayLines/
   //--- BackfillOverlayLines, not these handles)
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
   y += 34;
   MkLabel("closeNLbl", 12, y, "Close N oldest position(s):", InpTextColor, 9);
   y += 18;
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
   string methodStr = (InpSigStochMethod == SIG_STOCH_SUM) ? "SUM" :
                      (InpSigStochMethod == SIG_STOCH_SMA) ? "SMA-of-K" : "SMOOTHED(SMMA)";
   PrintFormat("TradePanel v1.45 OnInit: ENTRY stoch=(%d,%d,%d)  EXIT stoch=(%d,%d,%d)  method=%s  zone=(%.1f,%.1f)  interpCross=%s  showExit=%s  showMidline=%s",
               InpSigKPeriod, InpSigSlowing, InpSigDPeriod,
               InpExitKPeriod, InpExitSlowing, InpExitDPeriod,
               methodStr, InpSigZoneLow, InpSigZoneHigh, InpSigUseInterpCross ? "true" : "false",
               InpShowExitSignals ? "true" : "false", InpShowMidlineSignals ? "true" : "false");

   ApplyTheme();
   SetupMAs();
   //--- backfill BEFORE building the panel - otherwise the whole historical
   //--- MA/VWAP backfill gets created AFTER the panel and buries it from the
   //--- moment of attach, not just until the first new bar's RebuildPanel()
   //--- call (same creation-order reasoning as RebuildPanel's own header).
   BackfillOverlayLines();
   ResyncStochSignals();
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
   ObjectsDeleteAll(0, g_sig);
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
   if(t0 == g_lastBarTime) return;
   g_lastBarTime = t0;
   UpdateOverlayLines();
   if(InpShowStochSignals)
     {
      ComputeStochSignals(false);
      PurgeOldSigObjects();
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
      if(g_sigPeriod != (ENUM_TIMEFRAMES)_Period)
        {
         ResyncStochSignals();
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
