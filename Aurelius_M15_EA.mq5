//+------------------------------------------------------------------+
//|                    Aurelius_M15_EA.mq5                     |
//|                                                                  |
//|  M15-NATIVE VARIANT of Aurelius_EA.mq5 (2026-09-07) - a separate  |
//|  file, deliberately, so it never overwrites the M5-validated       |
//|  original: different filename, different EA name/magic (750015     |
//|  vs 750004, so the two can run simultaneously on the same account   |
//|  without their position tracking or circuit-breaker state ever      |
//|  mixing), same trading logic otherwise. Everything below this        |
//|  block is Aurelius_EA.mq5's own original header/history, kept         |
//|  verbatim since the underlying logic is identical - only the           |
//|  MOVING AVERAGES section's defaults differ, see their own inline        |
//|  comments (InpP600/InpP2400/InpM600) for the M15-specific rescale         |
//|  and the MA sweep that refined it further.                                 |
//|                                                                              |
//|  WHY THIS EXISTS: real MT5 backtests (same 2023.01-2026.09 window,           |
//|  same everything else) found Aurelius's own logic performs BETTER on          |
//|  M15 than on its originally-validated M5 - net $1,460 PF 1.818 DD 4.05%        |
//|  (M15, raw M5-period numbers) vs net $913 PF 1.235 DD 6.94% (M5) - on           |
//|  every metric, confirmed twice at two different sample sizes (8-month            |
//|  and full 3.75yr windows). A systematic Python sweep (m15_lib.py, logged          |
//|  in SESSION_NOTES.md item 23) then found the raw M5 period numbers               |
//|  weren't even the best M15 config available: rescaling InpP600/InpP2400           |
//|  to their true M15-native equivalents (200/1200, not the raw 600/2400)             |
//|  and switching InpM600 to MODE_SMMA beat every previously-tested M15                |
//|  config on net profit while staying competitive on PF/drawdown - a real,             |
//|  non-obvious finding from systematic search, not a guess.                             |
//|                                                                                          |
//|  v1.45 UPDATE (2026-09-07): the 200/SMMA,1200/EMA config above (call it "D")            |
//|  IS now real MT5 confirmed: net $1,539.18, PF 1.657, Balance DD 5.59%                    |
//|  ($169.53). User then asked Opus for a genuinely broader search (full MA                 |
//|  period+method grid on both M5 and M15, applied-price, and the other entry                |
//|  filters - SESSION_NOTES.md item 23), which found InpP21 21->30 + InpMinSlopeATR           |
//|  0.50->0.20 on top of D as the strongest further M15 candidate. ALSO REAL MT5               |
//|  CONFIRMED: net $1,902.57 (+23.6% vs D), PF basically flat (1.657->1.666), but                |
//|  Balance DD MORE THAN DOUBLED (5.59%->8.21%) - a genuine profit-for-drawdown                   |
//|  trade, not a clean win on every metric (worst losing streak did improve, 19                   |
//|  losses/-$133 -> 10 losses/-$79). Adopted as this file's new default anyway,                    |
//|  because it still beats the equivalent M5 config (Aurelius_EA.mq5 v1.45,                         |
//|  real-tested the same day) on every single metric - see InpP21's own comment                     |
//|  below for the full numbers. If the extra drawdown isn't worth it for your                        |
//|  purposes, D (InpP21=21, InpMinSlopeATR=0.50) is the safer real-confirmed                          |
//|  fallback - both are real, validated configurations now, this just picks the                       |
//|  more aggressive one as the shipped default.                                                        |
//+------------------------------------------------------------------+
//|                                                                  |
//|  Live version of Gold_MTF_Trend_Signals.                         |
//|                                                                  |
//|  align  : 21>50>150>600 with PRICE above/below the 2400          |
//|  entry  : price rejects the 50, 50 sloping >= 0.5 ATR / 20 bars  |
//|  exit   : the alignment breaks                                   |
//|                                                                  |
//|  Backtest on 100,013 M5 bars of Gold (Mar 2025 - Aug 2026),      |
//|  spread deducted, next-open fills, AURELIUS preset:               |
//|     837 trades, +1846 dollars of price movement, PF 1.51,        |
//|     34.3% win rate, max drawdown 183.                            |
//|     avg win 19.14 / avg loss -6.63 (~2.9:1) - the payoff shape    |
//|     this system depends on: losers cut fast on alignment break,   |
//|     winners uncapped. Longest losing streak found: 14 in a row,   |
//|     but only -51.59 total - less than ONE of Ratchet's normal     |
//|     losses, because each loss here stays small by design.         |
//|                                                                  |
//|  REAL RESULT (MT5 Strategy Tester, real-tick execution, random     |
//|  delay, XM Global GOLD# M5, Jan-Aug 2026, InpUseStopLoss=false):    |
//|     combined 136 trades, PF 1.56, net +2043.93, both the Jan-Apr    |
//|     and Apr-Aug halves individually profitable (PF 1.97 / 1.19).    |
//|     avg win:avg loss held at ~2.8:1 in BOTH real halves, matching   |
//|     the backtest's 2.9:1 almost exactly - the best real-execution   |
//|     result of anything tested this session, and the first real      |
//|     confirmation that the payoff-ratio idea survives real costs.    |
//|                                                                  |
//|  BUT: Balance Drawdown Maximal was 9.76% while Equity Drawdown      |
//|  Maximal was 27.69% of the account - a position floated ~$1,184     |
//|  underwater (no price floor existed to stop it) before recovering   |
//|  and eventually closing for far less. It recovered this time. If    |
//|  the trend it was riding simply hadn't come back, that float        |
//|  becomes the realized loss, several times worse than anything in    |
//|  the closed-trade stats. This is the exact risk flagged in an       |
//|  earlier version of this header before that real test ran.          |
//|                                                                  |
//|  RE-TESTED with InpUseStopLoss=true at 4.0 ATR (same real-tick,      |
//|  real-delay method, same two periods): combined 139 trades, PF       |
//|  1.49, net +1889.31 - a real cost of -154.62 (-7.6%) vs the no-SL    |
//|  run above. The stop DID fire as designed (10/60 backtest trades,    |
//|  9/79 forward, worst single loss capped near -136/-88 instead of     |
//|  running further). But the equity drawdown this was meant to fix     |
//|  came back at 27.69% again - identical to the no-SL run, to two      |
//|  decimal places. The single worst floating dip in this data isn't    |
//|  coming from a trade that runs past 4.0 ATR; it recovers or exits    |
//|  via the normal alignment break before ever reaching that distance,  |
//|  so the stop sits unused for exactly the scenario it was added for.  |
//|  Net effect: real (if partial) benefit - bounds the worst-case       |
//|  single loss, which was previously unbounded - at a real cost in     |
//|  expectancy, without moving the 27.69% number at all. Left ON for    |
//|  now since a bounded tail beats an unbounded one even at this cost,  |
//|  but 4.0 ATR is confirmed too wide to address the actual drawdown -  |
//|  a tighter distance (candidate: 2.0-2.5 ATR) is the next real test   |
//|  queued, to see if it can actually clip the 27.69% figure instead    |
//|  of just capping trades that were already going to lose.             |
//|                                                                  |
//|  NEW CANDIDATE (Python model only, NOT yet real-tested): the exit  |
//|  above only fires when the 21 EMA crosses the 50 - much later than |
//|  price itself closing back through the 21. Added InpUsePrice21Exit |
//|  (default ON): closes as soon as price closes InpPrice21BufferATR  |
//|  past the 21 for InpPrice21ConfirmBars closed bars running (0.7    |
//|  ATR / 8 bars tested). Unlike every other early-exit idea tried    |
//|  this session (banking, MACD momentum-fade, 21x50 early-cross,     |
//|  extension-from-21 distance - all four lost to just holding on     |
//|  BOTH train/hold splits), this one WON on both splits at once:     |
//|  TRAIN net 453.9->543.2 (PF 1.24->1.29), HOLD net 1392.3->1424.7   |
//|  (PF 1.79->1.79), AND max drawdown fell 183.4->148.0 (-19%). It    |
//|  is the first idea this session to improve profit and drawdown     |
//|  together, and it targets exactly the give-back pattern being      |
//|  watched live (profit shrinking as price fails to reject the 21    |
//|  and closes through it instead) rather than a blind profit trigger |
//|  or a distance-from-entry stop. Runs alongside the existing stop   |
//|  loss and alignment-break exit, not instead of them - if this      |
//|  never fires, both still apply exactly as before. Needs a real     |
//|  Strategy Tester run before it can be trusted, same as every other |
//|  number in this file.                                              |
//|                                                                  |
//|  InpCloseBeforeBreak now ON by default (was off): InpCloseOnFriday|
//|  already force-flattened before the weekend, but a position could |
//|  sit open straight through the daily Mon-Thu settlement break -   |
//|  inconsistent. Now both closes work the same way, same fix        |
//|  already made to Ratchet_EA.mq5 this session.                     |
//|                                                                  |
//|  CONSOLIDATED (v1.26): the SOLIDUS/AURELIUS/IMPERATOR/TRIUMPHUS/  |
//|  CONFLUENS preset switcher is removed - AURELIUS was the only     |
//|  preset ever real-tested or shipped as default, and every preset  |
//|  was just a fixed combination of the individual inputs below, so  |
//|  nothing is lost: SOLIDUS = turn off InpUseVolume/InpUseSRDist,   |
//|  IMPERATOR = turn on InpUseBank, TRIUMPHUS = turn on InpUseScale, |
//|  CONFLUENS = turn on the new InpUseMomentum. Also tested          |
//|  TRIUMPHUS's actual mechanic (scale-in) for the first time this   |
//|  session: it DOES improve net profit on both train/hold splits at |
//|  every setting tried, sometimes by 70-150% - but it does this by  |
//|  adding size right as a trade "confirms the trend", which is      |
//|  often close to the local top, so it also raises max drawdown     |
//|  1.2-2.4x and cuts win rate from 34% to 23-29% by turning former  |
//|  small winners into larger losers on exactly the trades that give |
//|  back after an add. Left OFF: this whole session has been about   |
//|  taming that give-back pattern, and scale-in trades raw return    |
//|  for more of the exact risk being managed away. Available as an   |
//|  opt-in for anyone who wants to prioritise return over a smoother |
//|  equity curve.                                                    |
//|                                                                  |
//|  One bull market, one instrument. Demo first.                    |
//|                                                                  |
//|  PANEL/LOGGING FIXES (v1.27):                                    |
//|   - Panel width is now self-learning instead of the fixed        |
//|     InpPanelW: each row measures its own text and the panel      |
//|     grows to fit on the next draw cycle, so a long value string   |
//|     can no longer clip past the frame.                            |
//|   - The panel's text objects are deleted and recreated every     |
//|     draw cycle instead of updated in place - MT5 stacks chart     |
//|     objects by creation order, not ZORDER, so a trade arrow/line  |
//|     MT5 draws after the panel already exists was rendering on     |
//|     top of it. Recreating the text each cycle keeps it the        |
//|     newest (topmost) object again every time.                     |
//|   - "today" was always reading the WHOLE account's P&L change     |
//|     since day start (ACCOUNT_EQUITY), silently including any      |
//|     other EA or manual trade sharing the account. Split into      |
//|     "today (mine)" (this magic/symbol only) and "today (other)"   |
//|     so the two are never mixed together again. Also fixed: the    |
//|     day-boundary tracking only ever ran inside DailyLossHit(),    |
//|     which returns immediately when InpMaxDailyLossPct is 0 (its   |
//|     default) - so "today" was always reading 0.00 for anyone on   |
//|     default settings. Now tracked unconditionally every tick.     |
//|   - CSV export (InpLogTrades): added FILE_COMMON, without which   |
//|     a Strategy Tester run wrote the file into that run's own      |
//|     sandboxed agent folder rather than somewhere you'd actually   |
//|     find it - likely why exports "weren't appearing". Also: a     |
//|     broker-side stop-loss fill never went through this EA's own   |
//|     ClosePosition() call, so it never got logged AND never reset  |
//|     the cooldown timer either - roughly 1 in 6-7 real trades (the |
//|     SL hits) were silently missing from the CSV, and cooldown     |
//|     wasn't being respected after one. New OnTradeTransaction()    |
//|     handler catches exactly that case now.                        |
//|                                                                  |
//|  NEW CANDIDATE (v1.28, Python model only, NOT yet real-tested):   |
//|  same buffer+confirm mechanic as the price-21 exit, but anchored  |
//|  to the session VWAP instead - a genuinely different line, so it  |
//|  can fire independently. Validated in the Python model: FULL net  |
//|  1846.2->1990.5, PF 1.51->1.54, both train/hold splits agree, at  |
//|  0.2 ATR buffer / 8-bar confirm. MT5 has no built-in VWAP, so      |
//|  SessionVWAP() computes it directly from closed-bar history back   |
//|  to that bar's day-start (typical price * tick volume, daily      |
//|  reset) - cheap since it's only called from position management,  |
//|  which already runs at most once per bar. Runs ALONGSIDE the       |
//|  price-21 exit, not instead of it - default ON for both, which     |
//|  means the next real test exercises two unproven exits at once.   |
//|  That is a deliberate, informed choice, not an accidental          |
//|  confound: price-21 has never been isolated in a real test either  |
//|  (every real run so far paired it with the stop-loss change), so   |
//|  there is no already-validated baseline this would be muddying -   |
//|  both are equally unproven going in. If the combined result is     |
//|  good, a follow-up test with one of the two switched off is the    |
//|  way to attribute the improvement; if it disappoints, the same     |
//|  follow-up isolates which one to blame.                            |
//|                                                                  |
//|  PERFORMANCE FIX (v1.29): SessionVWAP() was calling iTime/iHigh/   |
//|  iLow/iClose/iTickVolume individually inside its backward walk -   |
//|  up to 400 bars x 5 calls = 2000 individual history lookups every  |
//|  time it ran. It's only called once per bar (not per tick, so not  |
//|  the Slipstream-class bug), but a multi-month M5 backtest still    |
//|  has many thousands of open-position bars, and that added up to a  |
//|  real, avoidable slowdown - not repainting, just needless per-bar  |
//|  API call overhead. Now uses CopyTime/CopyHigh/CopyLow/CopyClose/  |
//|  CopyTickVolume (one bulk array fetch each, as-series so index 0   |
//|  = the requested shift) instead of walking the history one call    |
//|  at a time. Same calculation, same result, just far fewer calls.   |
//|                                                                  |
//|  THEME FIX (v1.30): candle colors (cyan/hot-pink) and chart       |
//|  background didn't match the rest of the family. Every EA has its |
//|  own distinct wallpaper image, yet Ratchet/Slipstream/Tailwind/    |
//|  AuRebound all already share the same neon-blue/white candles on  |
//|  a black background regardless - so there was no real reason for  |
//|  this one to differ, it just slipped through the panel/logging    |
//|  consolidation pass earlier this session. Now matches: InpBullCol |
//|  neon blue, InpBearCol white, InpChartBg black. Same fix applied  |
//|  to Prism_EA.mq5.                                                  |
//|                                                                  |
//|  PERFORMANCE FIX (v1.31): MyRealizedPLToday() was calling          |
//|  HistorySelect() and re-scanning every deal in the day's history   |
//|  from scratch on every call - same class of bug as v1.29's         |
//|  SessionVWAP() fix, but worse here: this one runs from the panel   |
//|  refresh path, which fires on every unique TimeCurrent() second,   |
//|  not once per bar. On a real-tick backtest that's a full-history   |
//|  rescan up to once per simulated second across the whole run -     |
//|  the reported symptom (this EA taking dramatically longer than a   |
//|  comparably-sized EA with no such scan) matches exactly. Fixed the |
//|  same way as v1.29: g_myRealizedToday is now an O(1) running       |
//|  total, updated incrementally in OnTradeTransaction() as each real |
//|  close happens (rare) and reset daily in UpdateDayStamp() -        |
//|  MyRealizedPLToday() is now just a lookup, no history scan at all. |
//|                                                                  |
//|  PERFORMANCE FIX (v1.32): v1.31 removed the most expensive CALL    |
//|  from the panel-refresh path, but not that path's own frequency -  |
//|  it still ran on every unique TimeCurrent() second, not once per   |
//|  bar. The panel itself is 37 rows x 3 chart objects each, and      |
//|  every one of those objects is deleted and recreated on every      |
//|  single redraw (the v1.27 z-order fix) - roughly a thousand MT5    |
//|  object API calls per call, times up to millions of seconds        |
//|  touched by ticks across a multi-year real-tick backtest, with no  |
//|  chart open for any of it to actually be seen. That's what was     |
//|  still costing 8 hours after v1.31. Both the between-bar and       |
//|  per-bar panel redraws are now skipped entirely when running a     |
//|  non-visual Strategy Tester pass (detected once in OnInit() via    |
//|  MQL_TESTER + MQL_VISUAL_MODE) - purely cosmetic, zero effect on   |
//|  any trading decision, and nobody can see it anyway in that mode.  |
//|  Still fully live for real trading, demo, and visual-mode          |
//|  backtests - only non-visual Tester runs skip it.                  |
//|                                                                  |
//|  PERFORMANCE FIX (v1.33): v1.32 gated the panel draws inside       |
//|  OnTick(), but missed a completely separate mechanism -            |
//|  EventSetTimer(1) in OnInit() starts a 1-SECOND TIMER that fires    |
//|  its own OnTimer() handler, which redraws the same 37-row panel     |
//|  independently of anything in OnTick(). Strategy Tester DOES        |
//|  simulate timer events, so this was firing once per simulated       |
//|  second for the whole backtest completely untouched by v1.32 -      |
//|  almost certainly the actual reason that fix showed zero measured   |
//|  improvement. The timer is now not started at all in a non-visual   |
//|  Tester run (g_skipCosmeticDraws), with OnTimer() itself also       |
//|  early-returning as a backstop. Still fully live for real trading,  |
//|  demo, and visual-mode backtests, same as v1.32.                    |
//|                                                                  |
//|  v1.34: added InpUseStaleExit (default off, Python-only so far).    |
//|  Tested non-ATR loss-reduction ideas after this file's own header    |
//|  noted the 4.0 ATR stop's real test left equity DD unchanged -       |
//|  fixed-$ and structural-swing-based stops were tried too (both       |
//|  still distance mechanisms) and hit the same wall: the worst float   |
//|  often happens inside a single bar, faster than any distance stop    |
//|  can react to. A time-based check (still losing after N bars open,   |
//|  regardless of distance) is what actually targets the duration       |
//|  problem this file's own real test diagnosed. Needs a real test      |
//|  before trusting it, same discipline as everything else here.        |
//|                                                                  |
//|  v1.35: added InpUseBreakeven/InpUseTrailAfterBE (both default off,   |
//|  Python-only so far), requested directly after watching a real trade   |
//|  float +$2000 profit then reverse to a loss before ALIGN_BREAK finally  |
//|  fired. Deliberately does NOT close the trade at the trigger - stays    |
//|  in, only moves the stop (never loosens it) once floating profit         |
//|  reaches InpBreakevenATR x entry ATR, first to a small locked-in profit   |
//|  past breakeven, then optionally (InpUseTrailAfterBE, a separate toggle)  |
//|  trailing wide behind the peak by InpTrailGiveBackATR. A real review       |
//|  caught and fixed two bugs before this shipped even as Python-only:         |
//|  g_beDone was set even when every PositionModify() call failed (would       |
//|  have permanently disabled the feature for a trade after one transient       |
//|  rejection - now only marks done once a leg is actually protected, else       |
//|  retries next bar); the trailing step compared an un-normalized stop            |
//|  against the broker's normalized one, which could re-send an unchanged           |
//|  stop and log a fake "failed" line every bar for the life of the trade -          |
//|  fixed by normalizing before comparing. Python read (2023-2026, real M5,           |
//|  70/30 split, on a corrected entry gate + a newly-modeled InpStopATR stop            |
//|  that no earlier Aurelius Python check in this session had modeled at all):           |
//|  on the SAME entries as the no-BE baseline, breakeven-only trades net -199              |
//|  (-13% of baseline net) - negative on BOTH the train and hold split - for a               |
//|  PF improvement (1.43->1.50) and a ~4% drawdown cut, WITHOUT clipping the top-               |
//|  10 winners (byte-identical to baseline). Adding the trail on top DOES clip                  |
//|  the tail (confirmed across 3 parameterizations, -333 to -353 matched net) -                   |
//|  the exact "a few huge winners carry this system's edge" failure this file's                    |
//|  own InpUseBank finding already predicted. Net effect for anyone considering                     |
//|  this: breakeven-only is a real but small consistency/drawdown trade against a                    |
//|  real but small net-profit cost, not a free improvement - and it will NOT                          |
//|  preserve most of a large float like the $2000 example that prompted it (it                         |
//|  exits near breakeven, not near the peak) - only the trail does that, and                             |
//|  the trail is what this data argues against. Single-split Python read only -                           |
//|  needs a walk-forward and a real Strategy Tester run before trusting any                                 |
//|  specific parameter choice, same discipline as InpUseStaleExit/every other                                |
//|  optional exit in this file.                                                                               |
//|                                                                  |
//|  v1.36: ATR is no longer read via the built-in iATR() handle. A real   |
//|  D1 export elsewhere in this repo proved this broker's iATR(14) is       |
//|  actually a plain SMA(14) of True Range, not Wilder smoothing, despite    |
//|  MT5's own docs describing ATR as Wilder-smoothed - already fixed the      |
//|  same way in Zenith_EA.mq5. Every ATR-scaled threshold in this file        |
//|  (slope filter, pullback tolerance, S/R distance, the stop, both early      |
//|  exits, and the new breakeven trigger/lock/trail) was implicitly tuned       |
//|  against genuine Wilder ATR in the Python model, so trusting iATR() here      |
//|  was silently miscalibrating all of them by an amount that grows with,        |
//|  not shrinks with, more bars (not a warm-up artifact). ATR is now computed     |
//|  manually (ComputeWilderATR, ported verbatim from Zenith_EA.mq5) once per       |
//|  new bar into g_atrManual, read through GetATR() everywhere the old              |
//|  MA(hATR,1,atr) pattern was used - a real behavior change (stop distances,        |
//|  filter thresholds etc. now compute off a different ATR value than before),       |
//|  not just a Python-fidelity fix. Needs a real Strategy Tester run before           |
//|  trusting it against any prior "validated" number in this header, all of            |
//|  which predate this fix.                                                              |
//|                                                                  |
//|  v1.37: two real changes, everything else is visual/cosmetic polish -   |
//|  no other entry/exit/stop logic touched.                                 |
//|  (1) InpStopATR default changed 4.0 -> 2.5. Real MT5 Strategy Tester,     |
//|  twice independently confirmed on the v1.36 corrected-ATR baseline:        |
//|  first stop=2.5/BE=false vs stop=4.0/BE=false beat the old default on       |
//|  EVERY measure (backtest net +32.5%, PF better, equity DD -11.4% vs          |
//|  worse under 4.0, worst loss much smaller; forward net -6.1%, DD -17.2%,      |
//|  worst loss -14% - a real but favorable risk/reward). Second, stop=2.5/       |
//|  BE=true vs stop=2.5/BE=false confirmed AGAIN (at this new stop distance)      |
//|  that breakeven increases drawdown (+25.3% BT, +15.8% FWD) rather than          |
//|  reducing it, contradicting its own purpose - so InpUseBreakeven stays           |
//|  default false. Walk-forward Python sweep (aurelius_full_bt.py, 4              |
//|  sequential calendar folds, full exit stack incl. Price21Exit/VwapExit/         |
//|  SessionClose which no earlier Python check in this session had modeled         |
//|  at all) found 2.5 a consistent local-minimum-drawdown candidate before          |
//|  either real test was run. Ship default: InpStopATR=2.5, InpUseBreakeven=false.  |
//|  (2) Full visual/professional overhaul, at the user's explicit request -         |
//|  the moving averages used for the alignment gate (21/50/150/600/2400) are         |
//|  now drawn directly on the chart as their own neon-coloured OBJ_TREND              |
//|  segments (InpShowMAs, InpCol21/50/150/600/2400 - yellow/white/purple/               |
//|  pink/green), one new segment per bar, bounded to a rolling InpMAHistoryBars         |
//|  window (default 300) and purged each bar so a long-running live EA doesn't          |
//|  accumulate objects forever - see DrawMASegment/PurgeOldMALines/UpdateMALines.        |
//|  MT5 renders chart objects in creation order, not z-order, so UpdateMALines()          |
//|  is called before DrawPanel() every cosmetic-draw cycle to keep the panel the           |
//|  topmost (visually "solid") object. Added InpHideTradeMarks (default true),             |
//|  which turns off MT5's own native buy/sell/SL/TP arrows and lines via                    |
//|  ChartSetInteger(CHART_SHOW_TRADE_LEVELS/CHART_SHOW_TRADE_HISTORY, false) -               |
//|  these are a terminal display setting, not real chart objects, so they can't              |
//|  be deleted with ObjectDelete; this is the actual way to suppress them. Also               |
//|  found and fixed a real, pre-existing off-by-one in DrawPanel()'s sizing                    |
//|  constants (ROWS was hardcoded 37, hand-recount of every PRow/PSection call's                |
//|  ty+= sequence proved the true count is 38) that under-sized the panel's own                  |
//|  background rectangle, letting the last section's rows render partly outside                  |
//|  it - exactly the "no overlapping text, all text inside the window" bug the                     |
//|  user asked to have eliminated. Fixed to ROWS=39 (38 corrected + 1 new row: a                    |
//|  breakeven-status line in the STRATEGY section, since every other optional exit                   |
//|  already had one but breakeven never did). Panel autofit (shrinking rh down to                    |
//|  an 11px floor if the panel would run off a short screen) was already present                      |
//|  and is unchanged. Wallpaper/watermark/candle theme/panel solidity were already                     |
//|  implemented pre-v1.37 and are unchanged by this round.                                               |
//|                                                                                                          |
//|  Opus review of the above (before shipping) found the panel genuinely was            |
//|  NOT solid: PRect (frame rects) only recreated an object if it didn't exist            |
//|  yet, so an MA line segment drawn on a later bar ended up newer/stacked on              |
//|  top of the panel body and would show through it - only PText's own delete-             |
//|  and-recreate-every-cycle text was actually staying on top. Fixed: PRect now             |
//|  gets the same delete-and-recreate treatment (except the draggable "bg" rect,             |
//|  which must keep its identity or dragging breaks), plus a new opaque "fl" fill             |
//|  rect drawn on top of "bg" every cycle - that's what actually keeps the panel               |
//|  body solid now. Also: InpCol50 (white) was on top of InpBearCol (also white) -              |
//|  the 50 EMA would vanish into bearish candles - changed to neon orange. Also:                 |
//|  UpdateMALines() only ever draws one new bar's worth of line, so a fresh attach                |
//|  would show five 1-bar stubs and take InpMAHistoryBars bars (~25h on M5 at the                  |
//|  300 default) to fill the window it claims to show - added BackfillMALines(),                    |
//|  called once from OnInit, to draw the whole rolling window immediately. Also:                     |
//|  DrawMASegment's OBJ_TREND objects weren't marked OBJPROP_HIDDEN, so up to 1500                     |
//|  of them (5 lines x 300 bars) would flood the terminal's Object List - fixed.                        |
//|                                                                                                        |
//|  v1.38: the v1.37 solidity fix (PRect/PText deleting-and-recreating every                              |
//|  DrawPanel() call) directly caused a real reported regression - the panel                               |
//|  visibly flashed/repainted on every live-number refresh, since DrawPanel()                               |
//|  runs roughly once a second and that fix meant every one of those calls tore                             |
//|  down and rebuilt a dozen large filled rectangles. Reclaiming top-of-stack                                |
//|  is only actually needed once per new bar, right when UpdateMALines() adds                                 |
//|  the one new object that could bury the panel - added a g_panelReclaim flag,                               |
//|  driven by a new `reclaim` parameter on DrawPanel() (true only for the once-                                |
//|  per-new-bar draw, false everywhere else - OnTimer, the between-bar live-P&L                                 |
//|  refresh, and the drag/resize handlers), that PRect/PText check before                                        |
//|  deleting: false just updates the existing object's properties in place, no                                   |
//|  visual churn. Opus review of this fix (before shipping) also caught: an                                       |
//|  unconditional ChartRedraw() on the between-bar refresh path was fighting the                                   |
//|  same OnTimer guard right next to it - fixed to the same hl||hs guard; the                                       |
//|  new `reclaim = true` default was repeated on both the forward declaration                                       |
//|  and the definition, a hard error in some MQL5/C++-family compilers - moved                                      |
//|  to the declaration only; a real, pre-existing bug where the "adds done" (p5)                                     |
//|  panel row was only ever cleared in the in-position branch, so it survived on                                     |
//|  the chart at a stale y-coordinate after a position closed - fixed to clear                                       |
//|  it in the flat branch too; and OnTradeTransaction never called                                                    |
//|  HistoryDealSelect(ticket) before reading deal properties (Fulcrum_EA.mq5                                          |
//|  already had this fix and said so in its own header, but Aurelius itself                                           |
//|  never got it) - a just-added deal isn't guaranteed to already be in the                                            |
//|  selected history window, and reading an unselected ticket's properties                                             |
//|  silently returns 0/empty, which would skip both the realized-P&L                                                    |
//|  accumulator and the g_barsSinceClose cooldown reset. Fixed identically to                                            |
//|  Fulcrum. No trading-logic changes beyond that last fix restoring intended                                             |
//|  cooldown behavior on the SL-hit path.                                                                                  |
//+------------------------------------------------------------------+
//|  v1.39: visual standardization pass across Aurelius/Fulcrum_EA.mq5/     |
//|  Ratchet_EA.mq5, all three sharing one account, so they should read as   |
//|  one product rather than three different panels. (1) PRect's own          |
//|  OBJ_RECTANGLE_LABEL border rendered unreliably - observed live as only    |
//|  two of the four sides actually drawn - replaced with an explicit 4-strip   |
//|  PFrame() outline, immune to the quirk. (2) InpMAHistoryBars default        |
//|  300->2500 (300 M5 bars is only ~25h - "a short line, not covering the       |
//|  whole chart" on any normal zoomed-out view; 2500 is ~8.7 days). (3) This     |
//|  file already computed SessionVWAP() for its exit logic but never drew it -   |
//|  now drawn as its own neon-aqua line (InpShowVWAP/InpColVWAP), same per-bar    |
//|  segment idiom as the 5 MAs, with its own smaller InpVwapHistoryBars backfill   |
//|  window (VWAP resets every session, and SessionVWAP() re-walks up to 400 bars   |
//|  per call, so backfilling it as far as the MAs would slow OnInit for no visual   |
//|  benefit) and a same-session guard so the line doesn't draw a misleading jump     |
//|  across a day boundary. Panel palette/position (InpPanelX=12/InpPanelY=30) and     |
//|  the "today (mine)"/"today (other)" P&L split were already consistent with the      |
//|  other two - only Fulcrum needed those. No trading-logic changes.                    |
//+------------------------------------------------------------------+
//|  v1.40: same holiday-session-gap fix as Daybreak_EA.mq5 v1.11-1.12/            |
//|  Zenith_EA.mq5, confirmed live in their real Strategy Tester data and found       |
//|  by code inspection to apply identically here: FridayCutoff(false) (the           |
//|  weekend flatten) only ran once per new bar, so a holiday leaving zero              |
//|  ticks/bars near the Friday cutoff hour meant it never fired at all, and              |
//|  nothing then existed to catch a stale position over the following weekend             |
//|  either. Added WeekendStillOpen() (deadline-based - true once now is past               |
//|  the most recent Friday InpFridayCloseHour:00 AND the position opened before              |
//|  it, regardless of which day the first tick back lands on) and HasOwnPosition(),           |
//|  called every tick at the top of OnTick, ahead of the new-bar gate - closes on              |
//|  literally the first tick available after any gap. The old bar-gated                         |
//|  FridayCutoff(false) call site removed (now dead weight, always beaten by the                  |
//|  tick-level check). Also added IsMarketHoliday() (New Year's/MLK/Presidents/                    |
//|  Good Friday/Memorial/Juneteenth/Independence/Labor/Thanksgiving/Christmas,                       |
//|  every date computed from the year - no hardcoded table, no yearly maintenance)                    |
//|  and blocked new entries on a flagged holiday the same place/way as the existing                     |
//|  Friday no-entry rule. The daily Mon-Thu settlement-break flatten (NearSessionClose/                  |
//|  InpCloseBeforeBreak) is untouched - still bar-gated, but a missed daily-break gap                     |
//|  is minutes, not days, so it wasn't the risk this fix targets.                                          |
//+------------------------------------------------------------------+
//|  v1.41: real GOLD# M5 price data (2023-2026) shows this broker's server        |
//|  clock follows EU DST dates while gold's true session timing follows US          |
//|  DST dates - confirmed directly from the daily first-bar-of-day time, which        |
//|  shifts by exactly 60 minutes on the Monday after each transition, twice a           |
//|  year, every year, no exceptions. During the ~2-week March gap and ~1-week             |
//|  Oct/Nov gap this creates, InpFridayCloseHour and InpNoEntryAfterHourFri read            |
//|  1 server-clock hour off from the true session boundary. Added                            |
//|  DSTGapHourAdjustment() (returns -1 during a gap week, 0 otherwise, computed                |
//|  from the permanent US/EU DST transition rules - no hardcoded dates, no                      |
//|  yearly maintenance, same principle as IsMarketHoliday) and applied it to both                 |
//|  hour thresholds. No core-signal timing in this file depends on a fixed server                  |
//|  hour (unlike Daybreak_EA.mq5's InpSessionHour), so this is risk-management only,                |
//|  same scope as the weekend-gap fix above.                                                          |
//+------------------------------------------------------------------+
//|  v1.42: default InpLots changed 0.03 -> 0.01, to match Fulcrum_EA.mq5/     |
//|  Ratchet_EA.mq5's default and be the safest floor for a small live account.  |
//|  This file's LOT_RISK_PCT mode is unaffected either way - InpLots only        |
//|  matters at LOT_FIXED (the shipped default) or as the fallback when a          |
//|  stop distance isn't available. No signal/entry-logic changes.                  |
//+------------------------------------------------------------------+
//|  v1.43: Opus review found NthWeekdayOfMonth/LastWeekdayOfMonth built their |
//|  date at 12:00 noon, not midnight, so the "+86400 -> Monday" arithmetic in    |
//|  DSTGapHourAdjustment() landed each DST-gap boundary at Monday 12:00 rather     |
//|  than Monday 00:00 - harmless at this file's shipped hour thresholds (all       |
//|  above noon) but would silently mis-adjust any lower hour on the 4 transition    |
//|  Mondays/year. Changed both helpers to build at 00:00. No other logic changed.    |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  v1.44 (2026-09-06): indicator-visibility pass, from the Opus deep-dive |
//|  review's third ask ("whatever indicators the EA's use ... i want to     |
//|  see them on the charts"). That review found this file already draws its  |
//|  5 MAs and the session VWAP but that THREE things it genuinely trades on   |
//|  were still invisible on the chart, so nothing added here changes a         |
//|  single decision - it only draws what the existing code already computes:   |
//|  (1) Stop-loss and entry price. InpHideTradeMarks (on by default) switches   |
//|  MT5's own CHART_SHOW_TRADE_LEVELS off, and nothing ever replaced it - the   |
//|  real broker-side stop was simply not on the chart. Now two OBJ_HLINEs      |
//|  while a position is open (entry InpColEntryLine, stop InpColStopLine),     |
//|  deleted the moment the EA is flat. Horizontal rays, not per-bar segments:  |
//|  a stop doesn't move bar to bar, so one object each is both simpler and     |
//|  correct, and they are updated in place rather than recreated so they       |
//|  never re-bury the panel (the same creation-order problem g_panelReclaim    |
//|  exists for). (2) Support/resistance. SRDistanceATR() computes the real     |
//|  prior-InpSRDays D1 high/low but only ever surfaced a derived ATR distance  |
//|  on the panel - the price levels themselves were never drawn. Its D1 loop   |
//|  is now extracted verbatim into SRLevels() (no behaviour change) so the     |
//|  drawn level is provably the same one the filter tests, and both are drawn  |
//|  dashed in InpColSR. (3) The pullback tolerance band. PullbackOK() requires |
//|  a wick into InpPullbackTolATR x ATR of the pullback MA - the MA was drawn, |
//|  the band around it was not, leaving this file's single most-evaluated      |
//|  entry condition with no visible geometry. Now drawn as a dotted            |
//|  InpColPullback envelope through the same DrawMASegment()/PurgeOldMALines() |
//|  machinery the MAs use (DrawMASegment gained an optional `style` argument,  |
//|  defaulting to STYLE_SOLID, so every pre-existing call is unchanged), with  |
//|  a matching BackfillMALines() pass so a fresh attach shows the whole window |
//|  rather than a 2-bar stub. That backfill computes a real per-bar ATR series |
//|  (one CopyRates + ComputeWilderATR, 500 warm-up bars per UpdateATRManual()'s |
//|  own note) instead of painting the whole history with today's ATR, which    |
//|  would have drawn a constant-width band that was never the band tested.     |
//|  New object prefix AURL_ for the horizontal levels (the band belongs to     |
//|  AURM_, since it really is a per-bar segment pair and wants the same purge), |
//|  swept in OnDeinit alongside AURP_/AURW_/AURM_; every new object is         |
//|  OBJPROP_HIDDEN (the v1.38 Object-List-flood lesson) and every new draw     |
//|  sits inside the existing g_skipCosmeticDraws gate, so a non-visual         |
//|  Strategy Tester pass does none of it. No signal, entry, exit, sizing or    |
//|  risk-management logic touched.                                             |
//|                                                                              |
//|  v1.46 (2026-09-09): InpMinSRDistATR default 0.50->1.50, REAL MT5           |
//|  CONFIRMED. Never independently swept on M15 before (inherited unchanged    |
//|  from the M5 original) - a Python sweep found 1.50 a genuine local          |
//|  optimum, and the real backtest confirmed it beating 0.50 on EVERY metric   |
//|  at once: net $1,902.57->$2,404.76 (+26.4%), PF 1.666->2.070, Balance DD    |
//|  8.21%($351.47)->3.31%($149.33) (nearly halved), Equity DD 9.86%->5.78%,    |
//|  on 365 real trades. The real PF (2.070) actually BEAT the Python screen's  |
//|  own prediction (1.960) - unusual, this project's pattern is normally      |
//|  Python overstating results, not understating them. See InpMinSRDistATR's   |
//|  own comment for the full sweep methodology and the separate "distance to   |
//|  the level BEHIND the entry" check that was tried and found unnecessary.    |
//|  No other logic touched - InpStopATR stays at 2.5 (its own real-tested M5   |
//|  history, never independently confirmed on M15 - a separate, still-open     |
//|  question, see InpStopATR's own comment).                                   |
//|                                                                              |
//|  v1.47 (2026-09-09): InpStopATR default 2.5->1.5, CANDIDATE UNDER TEST.     |
//|  Same situation InpMinSRDistATR was in before v1.46 confirmed it: 2.5 was    |
//|  real-tested, but only ever on M5 (v1.36, inherited unchanged into this      |
//|  file). A Python sweep (stop_sweep.py) found tighter stops win on almost     |
//|  every measure on M15's own data - expectancy-in-R falls monotonically as    |
//|  the stop widens, and dollar drawdown gets WORSE with a wider stop, not      |
//|  better. Picked 1.5 over the even-stronger 1.0-1.25 Python range because     |
//|  tight stops are more exposed to real spread/slippage than this screen       |
//|  models - see InpStopATR's own comment for the full numbers. NEEDS A REAL    |
//|  MT5 BACKTEST before trusting this over 2.5 - Python-only so far.            |
//|                                                                              |
//|  v1.48 (2026-09-09): InpStopATR REVERTED 1.5->2.5, real-tested and           |
//|  REJECTED. Unlike InpMinSRDistATR (v1.46), the real backtest did NOT         |
//|  confirm the Python prediction: net $2,404.76->$2,257.05 (-6.1%), Balance    |
//|  DD 3.31%->3.32% (flat, not improved as predicted), win rate 37.81%->        |
//|  30.37% (down hard); PF ticked up marginally (2.070->2.096) and payoff       |
//|  ratio genuinely improved (3.4:1->4.8:1) but not enough to offset the        |
//|  much lower win rate. A real, if modest, net loss for no drawdown benefit -  |
//|  the tight-stop real-spread-exposure risk flagged in v1.47 appears to be     |
//|  exactly what ate the predicted gain. Back to 2.5 - see InpStopATR's own     |
//|  comment for the full numbers.                                              |
//|                                                                              |
//|  v1.49 (2026-09-10): InpMaxSlopeATR default 1.00->1.25, CANDIDATE UNDER      |
//|  TEST. A fresh Python sweep (gate_loosen_test_m15.py, real M15 data, TODAY's  |
//|  v1.48 baseline held fixed) found 1.25 a genuine sweet spot: net +17.7%,      |
//|  PF essentially flat, max drawdown UNCHANGED - a real gain with no measured   |
//|  cost. Pushing to 1.50+ turns bad again (drawdown jumps 40%), matching an      |
//|  EARLIER Opus finding against an older baseline - 1.25 sits between those two   |
//|  results, not a contradiction. Same sweep also confirmed removing the 150/200    |
//|  alignment legs (ALIGN_PRICE) and removing the pullback requirement both hurt     |
//|  badly (matches the equivalent M5 findings, see SESSION_NOTES.md), and found       |
//|  loosening InpMaxSpreadPoints has zero effect (never binds on this data) and         |
//|  loosening InpMinSlopeATR below 0.20 is only marginal, not worth chasing. See          |
//|  InpMaxSlopeATR's own comment for the full numbers. NEEDS A REAL MT5 BACKTEST           |
//|  before trusting this over 1.00 - Python-only so far.                                    |
//|                                                                                            |
//|  v1.50 (2026-09-10): InpPullbackMA default PB_50->PB_21, CANDIDATE UNDER TEST,              |
//|  SHIPPED ALONGSIDE v1.49's InpMaxSlopeATR=1.25 in the same file for one combined              |
//|  real test. Python sweep (pullback_ma_test.py, real M15 data, v1.48 baseline)                  |
//|  found PB_21 a genuine, low-cost win: net essentially flat (+0.9%), PF up                        |
//|  (1.960->1.985), max drawdown down ~19% (145.97->118.47) - same profit engine,                     |
//|  meaningfully tighter risk. M15-specific finding - the equivalent M5 sweep found                     |
//|  the OPPOSITE (PB_50 stays best there), so this is NOT ported to Aurelius_EA.mq5.                      |
//|  Both this and InpMaxSlopeATR=1.25 are independently Python-validated - if the                          |
//|  combined real result is mixed, they'll need testing separately to tell which one                        |
//|  is responsible. See InpPullbackMA's own comment for the full numbers. NEEDS A REAL                       |
//|  MT5 BACKTEST before trusting either change - Python-only so far.                                          |
//+------------------------------------------------------------------+
//|  v1.51 (2026-09-16): added InpUseSlopeSRBlock (default ON, shipped for a real                                |
//|  test), a combined slope x S/R-distance block - steep trend slope AND far from                               |
//|  the nearest prior-3-day S/R level, simultaneously, via the same SlopeATR()/                                  |
//|  SRDistanceATR() this file already computes for its own panel and single-                                      |
//|  threshold filters. Neither InpMaxSlopeATR nor InpMinSRDistATR alone catches                                    |
//|  this - it's specifically the combination that marks a real, distinct bad-signal                                |
//|  class: on the real 369-trade shipped universe, only 53 of 1360 candidates (3.9%)                                |
//|  get blocked, and the 16 that would have become real trades lost badly (12.5% win                                |
//|  rate, net -143.59R). Real Python numbers: net $2,393.26->$2,470.69 (+3.2%), PF                                   |
//|  2.01->2.10, IS PF 1.85->1.94, OOS PF 2.09->2.18 - both splits move the same                                       |
//|  direction, the threshold sweep (SR 4-8 ATR, slope 0.6-1.2) is a real plateau not                                   |
//|  a lucky cell, and a 200-draw permutation control puts the real net/PF at the                                        |
//|  98.5th/99.5th percentile of a matched-count random-removal null - clearly outside                                   |
//|  chance, the strongest statistical result of anything tested on this file this                                        |
//|  round. HONEST CAVEAT: this is a profit/quality improvement, NOT a drawdown fix -                                      |
//|  max drawdown is UNCHANGED ($136.41 either way, same driving OOS episode). If the                                       |
//|  goal is a smaller worst-case drawdown specifically, this does not deliver that -                                        |
//|  every idea tried this round aimed squarely at drawdown/losing-streak reduction                                           |
//|  (a consecutive-loss pause, a volatility-regime filter, an H1/H4 trend confirmation)                                       |
//|  was tested and rejected; the only lever found that moves drawdown at all was partial                                      |
//|  scale-out, and it costs 36-50% of net profit clipping this system's own fat-tail                                           |
//|  winners - not adopted. See InpUseSlopeSRBlock's own comment for the full numbers.                                           |
//|  NEEDS A REAL MT5 BACKTEST before trusting this over InpUseSlopeSRBlock=false -                                               |
//|  Python-only so far, shipped ON specifically so the next real test exercises it.                                               |
//|                                                                                                                                 |
//|  v1.52: adds InpPublishPosition (default on) - broadcasts this EA's real     |
//|  position direction via a terminal global variable ("AURELIUS_POSDIR_M15_"+  |
//|  Symbol), purely so Vanguard_M15_EA.mq5 (a separate EA, its own chart) can    |
//|  optionally skip entering directly against an already-open Aurelius           |
//|  position. Read-only broadcast - has zero effect on Aurelius's own entries,    |
//|  exits, sizing, or risk, whether Vanguard is attached or reading it or not.     |
//|                                                                                  |
//|  RESEARCH NOTE (2026-09-22): real MT5 confirmation, LIVE GOLD account              |
//|  (382043238, NOT GOLD#), 2023.01.01-2026.09.21, 20000 ZAR, today's shipped          |
//|  defaults unchanged, 62% real ticks: 428 trades, net 42,250.37 ZAR, PF                |
//|  1.89025, Balance DD Maximal 7.29%, Equity DD Maximal 9.86% / Relative                  |
//|  13.18% - matches this file's own existing claim that M15 beats M5 on every              |
//|  risk-adjusted metric (Aurelius_EA.mq5's paired same-day M5 confirmation: PF               |
//|  1.573425, worse on every DD figure). See Aurelius_EA.mq5's own 2026-09-22                   |
//|  research note for the full methodology, benchmark comparison and GOLD# data                   |
//|  caveat - not repeated here.                                                                      |
//|                                                                                                      |
//|  ABLATION (research/aurelius/candidate_ablation_test.py, engine.py/sim.py's P15                       |
//|  params): isolates this file's still-unconfirmed candidates. CORRECTION vs how                          |
//|  this ablation was originally scoped: InpStopATR is NOT one of them - v1.48                               |
//|  already real-tested 1.5 and REJECTED it, reverting to today's 2.5 default, so it                          |
//|  is excluded here. The three still genuinely Python-only are InpPullbackMA                                   |
//|  (PB_21, v1.50), InpMaxSlopeATR (1.25, v1.49) and InpUseSlopeSRBlock (on, v1.51).                              |
//|  Same GOLD#-only, price-unit-net caveat as Aurelius_EA.mq5's note applies here too.                             |
//|                                                                                                                    |
//|    baseline (shipped)                       n=401  net=$2722.37  PF 2.1335  closedDD $201.92  floatDD $255.67     |
//|    InpPullbackMA      PB_21->PB_50           n=398  net=$2663.23  PF 2.1325  closedDD $145.81  floatDD $272.85     |
//|    InpMaxSlopeATR     1.25->1.00             n=345  net=$2406.58  PF 2.1332  closedDD $165.22  floatDD $218.97     |
//|    InpUseSlopeSRBlock on->off                n=410  net=$2639.55  PF 2.0597  closedDD $210.05  floatDD $282.73     |
//|    MaxSlopeATR+SlopeSRBlock reverted together n=345 net=$2406.58  PF 2.1332  closedDD $165.22  floatDD $218.97     |
//|      (byte-identical to MaxSlopeATR alone, see below)                                                              |
//|    all three reverted (pre-v1.49 stack)      n=348  net=$2464.49  PF 2.1738  closedDD $145.81  floatDD $272.85     |
//|                                                                                                                    |
//|  CANNOT BE ISOLATED INDEPENDENTLY: InpMaxSlopeATR and InpUseSlopeSRBlock. The                                     |
//|  "both reverted together" row above is byte-identical to "MaxSlopeATR alone"                                       |
//|  because InpUseSlopeSRBlock's own gate (slope>=1.00 AND SR-distance>=6.00) only                                     |
//|  ever evaluates candidates the PRIMARY slope gate already let through, and once                                      |
//|  InpMaxSlopeATR=1.00 that primary gate already excludes everything with slope>=                                       |
//|  1.00 - so the block never has anything left to catch. Confirms exactly the                                            |
//|  interaction this file's own v1.51 comment flagged when InpUseSlopeSRBlock was                                          |
//|  shipped ON "specifically so the next real test exercises it": it can only be                                            |
//|  genuinely tested while InpMaxSlopeATR stays at 1.25.                                                                     |
//|                                                                                                                              |
//|  HONEST DISCREPANCY, not glossed over: this run finds the OPPOSITE drawdown                                                 |
//|  direction from the two earlier Python-only screens that produced these defaults.                                            |
//|  gate_loosen_test_m15.py (v1.49's own comment) claimed InpMaxSlopeATR 1.00->1.25                                               |
//|  left max drawdown "UNCHANGED"; here reverting from the shipped 1.25 back to 1.00                                               |
//|  cuts closedDD 18.2% and floatDD 14.4% - i.e. drawdown IS measurably worse at 1.25,                                              |
//|  not unchanged. pullback_ma_test.py (v1.50's own comment) claimed PB_21 cut                                                        |
//|  drawdown ~19% vs PB_50; here reverting from the shipped PB_21 to PB_50 cuts                                                         |
//|  closedDD 27.8% - PB_50 has the lower drawdown on this construction, the opposite                                                     |
//|  direction from that screen's claim. Different simulator each time (this is the                                                        |
//|  full engine.py/sim.py OnTick port, not those scripts' own simpler construction),                                                        |
//|  same real bar data - reported as an open discrepancy, not resolved here, and it                                                          |
//|  raises the priority of testing both for real rather than lowers it. Separately:                                                           |
//|  the closedDD/floatDD figures for "PB_50 alone" and "all three reverted" match to                                                           |
//|  six decimal places despite different trade sets (398 vs 348 trades, checked                                                                 |
//|  directly, not a rounding artifact) - the single worst drawdown episode in this                                                               |
//|  window is driven by a run of trades neither InpMaxSlopeATR nor InpUseSlopeSRBlock                                                             |
//|  touches, the same "same driving OOS episode" pattern v1.51's own comment already                                                              |
//|  documented for InpUseSlopeSRBlock alone.                                                                                                        |
//|                                                                                                                                                   |
//|  PRIORITIZED REAL MT5 TESTS (symbol GOLD, account 382043238, 2023.01.01-2026.09.21,                                                             |
//|  20000 ZAR, single toggle off from today's shipped defaults):                                                                                    |
//|                                                                                                                                                     |
//|   1. InpMaxSlopeATR=1.00 (largest ablated effect, and the drawdown-direction                                                                      |
//|      discrepancy above makes this the most urgent to resolve for real). Note:                                                                      |
//|      InpUseSlopeSRBlock stays on for this test but will sit mostly dormant per the                                                                  |
//|      interaction above - a real limitation of single-toggle testing here, not an                                                                    |
//|      oversight. PASS (1.25 keeps its default) if real trade count falls by roughly                                                                   |
//|      the ablation's ~14% (<=~368 of 428) AND real PF does not rise more than 2%                                                                       |
//|      above 1.89025. FAIL (reconsider 1.25) if real PF at 1.00 comes back meaningfully                                                                  |
//|      higher than 1.89025, or Balance/Equity DD improves by more than ~15% relative -                                                                    |
//|      matching this ablation's direction rather than v1.49's original "unchanged" claim.                                                                  |
//|                                                                                                                                                            |
//|   2. InpUseSlopeSRBlock=false (leave InpMaxSlopeATR at 1.25 so the block is actually                                                                      |
//|      exercised, per the interaction above). PASS (stays on) if real PF drops at least                                                                     |
//|      2% below 1.89025 with it off, or Balance/Equity DD gets measurably worse. FAIL                                                                        |
//|      if real PF/DD are flat or better with it off - meaning the 98.5th/99.5th-                                                                              |
//|      percentile permutation result behind this default doesn't hold on the live                                                                              |
//|      account.                                                                                                                                                   |
//|                                                                                                                                                                    |
//|   3. InpPullbackMA=PB_50 (lowest ablated net effect, but resolves the closedDD-                                                                                  |
//|      direction discrepancy against pullback_ma_test.py's own earlier claim). PASS                                                                                 |
//|      (PB_21 keeps its default) if real Balance/Equity DD with PB_21 - already                                                                                      |
//|      confirmed today at 7.29%/9.86% - comes back lower than a real PB_50 run with                                                                                   |
//|      everything else identical. FAIL if PB_50's real DD is lower, matching this                                                                                      |
//|      ablation rather than the original screen.                                                                                                                          |
//|                                                                                                                                                                          |
//|  RESEARCH NOTE (2026-09-23): real MT5 result for prioritized test 1 above, live  |
//|  GOLD 382043238, 2023.01.01-2026.09.21, 20000 ZAR, only InpMaxSlopeATR changed   |
//|  (1.25->1.00; InpUseSlopeSRBlock left on but confirmed dormant here per the      |
//|  interaction above, so this is still a clean single-variable test of the slope   |
//|  cap itself): 374 trades (-12.6% vs the 2026-09-22 real baseline's 428, close to |
//|  the ablation's predicted -14%), net 35,228.27 ZAR (-16.6% vs 42,250.37), PF     |
//|  1.823831 (-3.5% vs 1.89025). PASS: trade-count drop is in range and PF at 1.00  |
//|  did NOT come back higher - test 1's criterion is satisfied, InpMaxSlopeATR      |
//|  stays 1.25 and is now real-confirmed (not just Python), see its own comment.    |
//|  Drawdown was NOT the clean win the ablation implied though: Balance DD Maximal  |
//|  actually ROSE 7.29%->8.07% and Equity DD Maximal rose 9.86%->10.94% at 1.00,    |
//|  even though both dropped slightly in raw ZAR (3445.61->3385.48 / 4775.36->      |
//|  4713.86) - the % figures rose because the equity peak itself shrank with fewer, |
//|  smaller-total trades. So on the real account, 1.25 wins on net, PF, AND         |
//|  drawdown-% - a clear result, resolving the earlier gate_loosen_test_m15.py      |
//|  "drawdown unchanged" discrepancy in 1.25's favor.                               |
//|  STILL OPEN: test 2 (InpUseSlopeSRBlock=false with InpMaxSlopeATR held at 1.25,  |
//|  so the block is actually exercised) and test 3 (InpPullbackMA=PB_50) - neither  |
//|  has been real-tested yet, this run only answered test 1.                        |
//|                                                                                    |
//|  RESEARCH NOTE (2026-09-23), Python-only, REJECTED - same regular-divergence     |
//|  EARLY-EXIT idea tested on Aurelius_EA.mq5 (M5, see that file's 2026-09-23 note   |
//|  for the full construction), run here on this file's own M15 baseline via the    |
//|  same script (research/aurelius/divergence_exit_test.py). GOLD# M15 data (405445 |
//|  bars resampled from the M5 export), 401-trade baseline: net=$2722.37 PF=2.1335  |
//|  closedDD=$201.92 floatDD=$255.67. Net/PF got worse with every oscillator - RSI   |
//|  net=$2303.79 (-15.4%) PF=1.9405, MACD net=$2404.33 (-11.7%) PF=1.9959, STOCH     |
//|  net=$2414.17 (-11.3%) PF=2.0151 - but unlike M5, the picture is genuinely mixed: |
//|  MACD/STOCH's drawdown actually IMPROVED (closedDD $178.29 vs $201.92, floatDD    |
//|  ~$206-216 vs $255.67), while RSI got worse on every measure (closedDD $236.75,   |
//|  floatDD $283.94). REJECTED as a default - all three cost real net/PF, which this |
//|  file's own screening bar requires a candidate NOT do - but the MACD/STOCH        |
//|  drawdown improvement is a real, honest finding worth remembering if a future     |
//|  opt-in "smoother equity curve, less net" variant is ever wanted; not pursued      |
//|  further here since nothing asked for that tradeoff. See Aurelius_EA.mq5's own    |
//|  note (M5, a clean reject on every measure, no such tradeoff) and                  |
//|  research/divergence_standalone/ for the separate standalone-system test.          |
//+------------------------------------------------------------------+
#property copyright "Aurelius EA"
#property version   "1.52"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//------------------------------- enums ------------------------------
enum ENUM_ALIGN
  {
   ALIGN_FULL  = 0,   // 21>50>150>600>2400
   ALIGN_MID   = 1,   // 21>50>150>600 + price vs 2400   [tested]
   ALIGN_FAST  = 2,   // 21>50>150 + price vs 2400
   ALIGN_PRICE = 3    // 21>50 + price vs 2400
  };
enum ENUM_PBMA   { PB_21 = 0, PB_50 = 1, PB_150 = 2 };
enum ENUM_SLOPEMA{ SLOPE_21 = 0, SLOPE_50 = 1, SLOPE_150 = 2, SLOPE_600 = 3 };
enum ENUM_LOTMODE{ LOT_FIXED = 0, LOT_RISK_PCT = 1 };

//------------------------------- inputs -----------------------------
input group "=== Position sizing ==="
input ENUM_LOTMODE InpLotMode    = LOT_FIXED;  // How the size is decided
input double  InpLots            = 0.01;       // Fixed lot size
input double  InpRiskPct         = 1.0;        // Risk per trade (% of balance) - needs a stop
input double  InpMaxLots         = 1.0;        // Hard cap on size

input group "=== Moving averages (M15-NATIVE - see header) ==="
input int     InpP21   = 30;                   // MA 21->30 period (2026-09-07, real MT5-confirmed): an
                                                // Opus sweep found this on a broad plateau (28-40 all
                                                // improve, not a single lucky point), paired with
                                                // InpMinSlopeATR's loosened threshold below. Real result:
                                                // net $1,539.18 (200/SMMA,1200/EMA baseline) ->
                                                // $1,902.57 (+23.6%), PF basically flat (1.657->1.666).
                                                // REAL COST: Balance DD more than doubled, $169.53
                                                // ($169.53/5.59%) -> $351.47 (8.21%), Equity DD 7.05%/
                                                // 7.48% -> 9.86%. Worst losing streak actually IMPROVED
                                                // (19 losses/-$133.11 -> 10 losses/-$79.06). This is a
                                                // genuine profit-for-drawdown trade, not a clean win on
                                                // every metric - adopted here because it beats the
                                                // equivalent M5 config (Aurelius_EA.mq5 v1.45) on every
                                                // single metric, but know the drawdown is real before
                                                // running this live.
input int     InpP50   = 50;                   // MA 50 period - unchanged, same reason as InpP21; on M5
                                                // this WAS the fast/medium tier only - on M15 it directly
                                                // IS the "M15-scale" tier Aurelius_EA.mq5's 150 used to
                                                // approximate, so nothing needs rescaling here either
input int     InpP150  = 150;                  // MA 150 period - unchanged: its own distinct, valid M15
                                                // period (not trying to re-encode "M15-equivalent" anymore -
                                                // the chart itself already provides that once run natively
                                                // on M15, per the user's own catch that a naive period
                                                // rescale would have made this redundant with InpP50)
input int     InpP600  = 200;                  // MA 600->200: rescaled from Aurelius_EA.mq5's 600 to
                                                // preserve its ORIGINAL design intent (50-period-on-H1
                                                // equivalent: 600 M5-bars = 3000min = 50 H1-bars; on M15,
                                                // that's 200 M15-bars, not the same 600). Then FURTHER
                                                // refined by the M15 MA sweep below (2026-09-07): SMMA
                                                // beat both EMA and the original SMA at this period, on
                                                // every metric simultaneously - see InpM600 below.
input int     InpP2400 = 1200;                 // MA 2400->1200: NOT the naive 800 (=2400/3, the same H4-
                                                // equivalent rescale InpP600 got). The M15 MA sweep found
                                                // net profit climbs steadily from macro=600 up to a real,
                                                // non-monotonic local peak at 1200 (best combined net+PF
                                                // of the whole sweep - beats both the naive-800 rescale
                                                // AND Aurelius_EA.mq5's own raw-M5-period-on-M15 config),
                                                // then degrades 1400-1600 before partially recovering by
                                                // 2400. Python screen only (see m15_lib.py sweep, logged
                                                // in SESSION_NOTES.md item 23) - NEEDS real MT5 confirmation,
                                                // same caveat as every Python-only finding in this system.
input ENUM_MA_METHOD InpM21   = MODE_EMA;      // MA 21 method - unchanged
input ENUM_MA_METHOD InpM50   = MODE_EMA;      // MA 50 method - unchanged (a single-leg sweep found
                                                // MODE_SMA here roughly doubles risk-adjusted quality -
                                                // PF ~1.95, maxDD roughly halved - at a real cost in trade
                                                // count/net profit; left at EMA as the net-profit-first
                                                // default, worth testing MODE_SMA separately if a more
                                                // conservative profile is ever wanted)
input ENUM_MA_METHOD InpM150  = MODE_EMA;      // MA 150 method - unchanged (the sweep found SMA/SMMA here
                                                // both hurt badly - this leg is sensitive, leave alone)
input ENUM_MA_METHOD InpM600  = MODE_SMMA;     // MA 600 method - MODE_SMMA (2026-09-07 M15 sweep): beat
                                                // both the original MODE_SMA (Aurelius_EA.mq5's inherited
                                                // default) and this file's own interim MODE_EMA on every
                                                // metric simultaneously (net, PF, drawdown, win rate) at a
                                                // similar trade count - the "wins on every measure" bar
                                                // this session uses before taking a finding seriously.
                                                // NOTE: on real M5 data (Aurelius_EA.mq5's own timeframe)
                                                // the SAME sweep also found MODE_SMMA beats both SMA and
                                                // EMA at this leg (net +25% over the shipped SMA default) -
                                                // so this may be a genuine cross-timeframe finding, not an
                                                // M15-only quirk. UPDATE (2026-09-07): SMMA is now real-
                                                // tested too - net $1,539.18/PF 1.657/Balance DD 5.59% -
                                                // beats both SMA ($1460.59/1.818/4.05%) on net profit
                                                // and EMA ($1406.91/1.754/5.39%) on every metric, though
                                                // SMA still has the best PF/DD of the three. Adopted as
                                                // the default here regardless, since it's the base this
                                                // file's other real-tested improvements (InpP21/
                                                // InpMinSlopeATR below) were layered on top of.
input ENUM_MA_METHOD InpM2400 = MODE_EMA;      // MA 2400 method - unchanged
input ENUM_APPLIED_PRICE InpPrice = PRICE_CLOSE; // Applied price (all)

input group "=== Strategy ==="
input ENUM_ALIGN   InpAlignMode  = ALIGN_MID;  // Alignment requirement
input ENUM_PBMA    InpPullbackMA = PB_21;      // Which MA the pullback must reach - CANDIDATE UNDER TEST
                                                // (2026-09-10): was PB_50, never independently swept
                                                // before. A Python sweep (pullback_ma_test.py, real M15
                                                // data, shipped v1.48 config held fixed) found PB_21 a
                                                // genuine, low-cost improvement over PB_50: essentially
                                                // identical net profit ($1,922.57->$1,939.42, +0.9%) and
                                                // trade count (303->298), but PF up (1.960->1.985) and max
                                                // drawdown down nearly 19% ($145.97->$118.47) - same engine,
                                                // meaningfully tighter risk, fold-consistent. (PB_150 was
                                                // also tested - much more restrictive, trade count drops
                                                // 25%, PF/WR still solid but the frequency drop makes it a
                                                // different lower-frequency variant, not adopted here.) On
                                                // M5 (Aurelius_EA.mq5) the equivalent sweep found the
                                                // OPPOSITE - PB_50 stays best there, PB_21 slightly worse
                                                // on every measure - this is an M15-specific finding, not
                                                // ported to the M5 file. SHIPPED TOGETHER WITH
                                                // InpMaxSlopeATR's own 1.00->1.25 candidate (v1.49) in this
                                                // same real MT5 test for efficiency - both are individually
                                                // Python-validated, but if the combined real result is
                                                // mixed, they'll need testing separately to attribute which
                                                // one is responsible. NEEDS A REAL MT5 BACKTEST before
                                                // trusting this over PB_50 - Python-only so far.
input double  InpPullbackTolATR  = 0.25;       // Touch tolerance (x ATR)
input int     InpPullbackBars    = 10;         // Bars allowed from touch to entry
input bool    InpUseSlope        = true;       // Require a minimum slope
input ENUM_SLOPEMA InpSlopeMA    = SLOPE_50;   // Which MA the slope reads
input int     InpSlopeBars       = 20;         // Bars used for the slope
input double  InpMinSlopeATR     = 0.20;       // Minimum slope (x ATR) - 0.50->0.20 (2026-09-07): paired
                                                // with InpP21's 21->30 change above - see that input's
                                                // comment for the combined real MT5 numbers. Checked as
                                                // a plateau, not one lucky value: the Opus sweep found
                                                // every threshold from 0.20-0.30 an improvement over the
                                                // shipped 0.50, not just this exact number.
input double  InpMaxSlopeATR   = 1.25;      // Max slope - blocks over-extended entries (0 = off) -
                                             // CANDIDATE UNDER TEST (2026-09-10): was 1.00. An EARLIER
                                             // Opus sweep (widening up to 1.30) found more net profit but
                                             // much worse drawdown, and was left unchanged at the time -
                                             // but that test predates InpMinSRDistATR's 0.50->1.50
                                             // confirmation (v1.46) and InpStopATR's brief 1.5 detour
                                             // (v1.47, reverted in v1.48), so it wasn't run against
                                             // TODAY's actual shipped baseline. A fresh sweep
                                             // (gate_loosen_test_m15.py) against the CURRENT v1.48
                                             // defaults found something different at 1.25 specifically:
                                             // net $1,922.57->$2,262.41 (+17.7%), PF 1.960->1.946
                                             // (essentially flat), max drawdown $145.97->$145.97
                                             // (UNCHANGED) - a real gain with no measured cost. Pushing
                                             // further to 1.50+ reproduces the earlier Opus finding
                                             // (drawdown jumps to $204.88, PF keeps falling) - 1.25 looks
                                             // like the genuine sweet spot between those two results, not
                                             // a contradiction of the earlier one. REAL-CONFIRMED
                                             // (2026-09-23, live GOLD 382043238, 2023.01.01-2026.09.21,
                                             // 20000 ZAR): reverting to 1.00 gave 374 trades (-12.6%) and
                                             // net 35,228.27 ZAR / PF 1.823831 vs 1.25's own real 428
                                             // trades / 42,250.37 ZAR / PF 1.89025 - both real (not just
                                             // net, PF too) confirm 1.25 over 1.00. See the 2026-09-23
                                             // research note below for the full pass/fail check and an
                                             // open drawdown-direction discrepancy this same run raised.
input bool    InpUseCrossFilter  = true;       // Block after repeated 21/50 crossings
input int     InpCrossWindow     = 10;         // Cross lookback (bars)
input int     InpMaxCrosses      = 1;          // Max crossings allowed
input int     InpCooldownBars    = 5;          // Bars to wait after a close
input bool    InpAllowBuys       = true;       // Allow buys
input bool    InpAllowSells      = true;       // Allow sells

input group "=== Volume filter ==="
input bool    InpUseVolume    = true;      // Require above-average tick volume
input int     InpVolAvgBars   = 100;       // Bars for the volume average
input double  InpMinVolRatio  = 1.30;      // Min volume vs that average

input group "=== S/R proximity filter ==="
input bool    InpUseSRDist    = true;      // Skip entries sitting on a previous-days level
input int     InpSRDays       = 3;         // Previous days used for the level
input double  InpMinSRDistATR = 1.50;      // Min distance from the level (x ATR) - REAL MT5 CONFIRMED
                                            // (2026-09-09): was 0.50, never independently swept before
                                            // 2026-09-08's Python sweep (sr_dist_test.py, shipped M15
                                            // v1.45 config, stop=2.5 held fixed) found 1.50 a genuine
                                            // local optimum - and the real backtest CONFIRMED it, beating
                                            // 0.50 on every single metric at once: net $1,902.57->$2,404.76
                                            // (+26.4%), PF 1.666->2.070, Balance DD 8.21%($351.47)->
                                            // 3.31%($149.33) (nearly halved), Equity DD 9.86%->5.78%, on
                                            // 365 real trades. The real PF (2.070) actually BEAT the
                                            // Python screen's own prediction (1.960) - unusual, this
                                            // project's pattern is normally Python overstating, not
                                            // understating. Pushing further to 2.00 was Python-tested
                                            // WORSE (fewer trades, fold 1 weakens to +0.135) - 1.50 is a
                                            // real peak, not "more filtering is always better", left
                                            // un-swept further for real given this is already a clean win.
                                            // Also checked (2026-09-08): a distance filter on the level
                                            // BEHIND the entry (support under a buy/resistance over a
                                            // sell, i.e. "too close to support" read literally) - found to
                                            // be a structural non-issue for this system: 100% of trades
                                            // already sit >2.5xATR from that level by construction (the
                                            // alignment+slope gate already implies price has run clear of
                                            // it), so that filter was NOT added.

input group "=== Combined slope x S/R block (optional) ==="
input bool    InpUseSlopeSRBlock = true;   // Block entries where the trend is steep AND far from S/R at
                                            // once - a real, permutation-confirmed Python finding (2026-
                                            // 09-16, m15/stoch/s21_slope_sr_filter.py + earlier
                                            // m15/multi/ work), NOT yet real-tested. Neither InpMaxSlopeATR
                                            // nor InpMinSRDistATR alone catches this - it is specifically
                                            // the COMBINATION (steep slope AND already far from the nearest
                                            // level) that marks a real, distinct bad-signal class: only
                                            // 53 of 1360 real candidates (3.9%) get blocked, and the 16 of
                                            // those that would have become real trades lost badly (12.5%
                                            // win rate, net -143.59R combined) - not noise. Real numbers on
                                            // the full 369-trade shipped universe: net $2,393.26->$2,470.69
                                            // (+3.2%), PF 2.01->2.10, IS PF 1.85->1.94, OOS PF 2.09->2.18 -
                                            // both splits move the same direction, and the threshold sweep
                                            // (SR 4-8 ATR, slope 0.6-1.2) is a real plateau, not one lucky
                                            // cell. A 200-draw direction-stratified permutation control
                                            // (matched-count random removal) puts the real net at the
                                            // 98.5th percentile and real PF at the 99.5th - clearly outside
                                            // chance, a meaningfully stronger result than every other real
                                            // finding tested this session (e.g. Ratchet's own wick-reject
                                            // filter only reached the 81st-86th percentile on the same kind
                                            // of control). HONEST CAVEAT: this is a real profit/quality
                                            // improvement, NOT a drawdown fix - maxDD is UNCHANGED
                                            // ($136.41 either way, same driving OOS episode causes it in
                                            // both runs). If what you actually want is a smaller worst-case
                                            // drawdown, this input does not deliver that - it makes the
                                            // system better, not meaningfully less scary in a bad stretch.
                                            // Needs a real MT5 Strategy Tester run before trusting this
                                            // over InpUseSlopeSRBlock=false, same discipline as every other
                                            // number in this file - shipped ON specifically so the next
                                            // real test exercises it.
input double  InpSlopeSRBlockSlope = 1.00; // Slope threshold (x ATR, via the existing SlopeATR()) - only
                                            // blocks when slope is AT OR ABOVE this AND the S/R distance
                                            // below is also at or above its own threshold, simultaneously
input double  InpSlopeSRBlockSR    = 6.00; // S/R distance threshold (x ATR, via the existing
                                            // SRDistanceATR()) - see InpUseSlopeSRBlock's own comment

input group "=== Scale in (optional) ==="
input bool    InpUseScale     = false;     // Add to a position that is winning  [tested in the Python model: net profit improves on BOTH train/hold splits at every setting tried (e.g. +130/+68% at 3.0 ATR) - but every setting also raises max drawdown 1.2-2.4x and cuts win rate from 34% to 23-29%. It does this by adding size right as a trade "confirms the trend" - which is often close to the local top - so it specifically makes the profit-give-back pattern WORSE, not better, on the trades that reverse after the add. Left OFF: this system's give-back problem is the whole reason for this session's testing, and scale-in trades raw return for exactly the risk being managed away.]
input double  InpAdd1ATR      = 3.0;       // First add once profit reaches this (x ATR)
input double  InpAdd2ATR      = 6.0;       // Second add (0 = no second add)
input double  InpAdd3ATR      = 0.0;       // Third add (0 = none)
input double  InpAddLots      = 0.0;       // Lots per add (0 = same as the base size)
input int     InpMaxAdds      = 3;         // Hard cap on how many adds

input group "=== Bank profit early (optional) ==="
input bool    InpUseBank      = false;     // Bank once the trade is far enough in profit  [tested: every banking variant tried this session lost to not banking at all - a handful of huge winners carry this system's edge, and early lock-in clips them more than it saves. Left off.]
input double  InpBankATR      = 4.0;       // Profit needed before banking (x ATR at entry)
input bool    InpBankNeed21   = true;      // Only bank when the 21 has turned against the trade

input group "=== Momentum-shift entry filter (optional) ==="
input bool    InpUseMomentum  = false;     // Require MACD histogram to be turning in the trade's favour right at entry  [validated in the Python model (net/PF improve on both splits) but NOT yet real-tested - queued behind the price-21 exit and VWAP-cross candidates, see header]

input group "=== Protective stop (optional) ==="
input bool    InpUseStopLoss     = true;       // Attach a stop loss  [tested for real: a real Strategy Tester run showed a 27.69% EQUITY drawdown vs only 9.76% BALANCE drawdown - a position floated ~$1,184 underwater with no price floor before recovering. Turned on at the existing wide 4.0 ATR distance specifically to test whether it caps that float without denting real profit - see header]
input double  InpStopATR         = 2.5;        // Stop distance (x ATR at entry) - 1.5 REAL-TESTED AND
                                                // REJECTED (2026-09-09, M15). A Python sweep (stop_sweep.py)
                                                // predicted tighter stops would win on almost every measure,
                                                // including LOWER dollar drawdown - real MT5 disagreed: vs
                                                // this 2.5 default (net $2,404.76, PF 2.070, Balance DD
                                                // 3.31%/$149.33), 1.5 gave net $2,257.05 (-6.1%), PF 2.096
                                                // (marginally better), Balance DD 3.32%/$145.66 (flat, NOT
                                                // improved as predicted), win rate 37.81%->30.37% (down
                                                // hard), on 405 trades. Payoff ratio DID improve as
                                                // predicted (avg win/loss 3.4:1->4.8:1, the tighter stop
                                                // genuinely cuts losers cheaper) but not enough to offset the
                                                // much lower win rate - net effect is a real, if modest, loss
                                                // for no drawdown benefit. Consistent with the exposure-to-
                                                // real-spread risk flagged when this candidate was picked
                                                // over Python's even-tighter 1.0-1.25 range - the Python
                                                // screen doesn't model spread cost realistically, and a
                                                // tighter stop is proportionally more exposed to it. REVERTED
                                                // to 2.5. [Below: the ORIGINAL, real-tested-on-M5, v1.36 note
                                                // this default came from - kept verbatim:] [tested for real,
                                                // v1.36 corrected-ATR baseline: 2.5 beat 4.0 on EVERY measure
                                                // in backtest (net +32.5%, PF better, equity DD -11.4%, worst
                                                // loss -37%) and traded a real but favorable risk/reward on
                                                // forward (net -6.1%, DD -17.2%, worst loss -14%). New default.
input bool    InpUseMaxBars      = false;      // Force close after N bars
input int     InpMaxBars         = 1000;       // N bars

input group "=== Early exit: price closes through the 21 (optional) ==="
input bool    InpUsePrice21Exit     = true;    // Exit as soon as price closes back through the 21, instead of waiting for the slower 21x50 alignment break  [NOT yet real-tested - validated in the Python model only, both train/hold splits agree: net/PF improve AND max drawdown falls ~19-26%. See header before trusting this default.]
input double  InpPrice21BufferATR   = 0.7;     // How far past the 21 counts as "through" (x ATR) - filters normal noise right at the line
input int     InpPrice21ConfirmBars = 8;       // Consecutive closed bars required past the buffer before exiting - filters normal pullback-to-50 wiggles that dip through the 21 and recover

input group "=== Early exit: price closes through session VWAP (optional) ==="
input bool    InpUseVwapExit        = true;    // Exit as soon as price closes back through the session VWAP  [NOT yet real-tested - validated in the Python model only, both train/hold splits agree: FULL net 1846.2->1990.5, PF 1.51->1.54. Independent of the price-21 exit (different line) - running both together is a genuine test of two unproven ideas at once, not a confound of an already-validated one, since NEITHER has real data yet. See header.]
input double  InpVwapBufferATR      = 0.2;     // How far past VWAP counts as "through" (x ATR)
input int     InpVwapConfirmBars    = 8;       // Consecutive closed bars required past the buffer before exiting

input group "=== Early exit: stale losing trade (optional) ==="
input bool    InpUseStaleExit    = false;      // 0 = off (NOT yet real-tested). A genuinely different axis from
                                                // InpStopATR/fixed-distance stops: the EA's own real test found the
                                                // worst equity float ISN'T a trade running past a wide distance -
                                                // it recovers or exits via ALIGN_BREAK before ever reaching one.
                                                // That's a DURATION problem, not a distance one, so a distance
                                                // stop structurally can't fix it. This closes a trade once it has
                                                // been open InpStaleBars bars AND is still losing more than
                                                // InpStaleMinLossATR - regardless of price distance. Python-
                                                // validated (2023-2026, same entry gate/exit stack as shipped):
                                                // at 48 bars (4h) the worst single-trade float fell ~9% (-61.4 ->
                                                // -56.1) at ~0% net cost; at 60 bars (5h) it doesn't touch the
                                                // worst trade at all but net/PF improve on both splits anyway
                                                // (a separate, free finding). Needs a real Strategy Tester run
                                                // before trusting either number, same as everything else in this
                                                // file marked Python-only.
input int     InpStaleBars       = 48;         // Bars open before this exit is even considered (48 = 4h at M5)
input double  InpStaleMinLossATR = 0.5;        // Still-losing threshold, x ATR at entry

input group "=== Breakeven + moderate trail (optional) ==="
input bool    InpUseBreakeven    = false;      // 0 = off (NOT yet real-tested). Requested directly after watching a
                                                // trade float +$2000 profit, then reverse all the way to a loss by
                                                // the time ALIGN_BREAK finally fired - a real gap, since ALIGN_BREAK
                                                // only reacts to the STACK breaking, not to giving back an already-
                                                // large winner. This does NOT close the trade at the trigger - the
                                                // whole point is staying in if it's only a pullback, not guessing
                                                // whether it's a real reversal. It only moves the stop, once, to
                                                // lock in InpBreakevenLockATR beyond entry (never loosens it, never
                                                // moves it back) once floating profit reaches InpBreakevenATR x the
                                                // entry ATR. A moderate move deliberately, not tight: this system's
                                                // own header already found every tested early-profit-lock variant
                                                // (InpUseBank) lost against not banking at all, because a handful
                                                // of huge winners carry the whole edge - the same risk applies here
                                                // if the trigger/trail are set too tight. Needs a real Strategy
                                                // Tester run before trusting the Python numbers below, same as
                                                // every other optional exit in this file.
input double  InpBreakevenATR     = 2.0;       // Floating profit (x entry ATR) that triggers the move to breakeven
input double  InpBreakevenLockATR = 0.10;      // How far past pure entry to lock (x entry ATR) - covers spread/
                                                // commission so it isn't a dead-even exit
input bool    InpUseTrailAfterBE  = false;     // Keep trailing further once breakeven has been locked (independent
                                                // toggle - breakeven-only is a smaller, separable change from also
                                                // trailing after it)
input double  InpTrailGiveBackATR = 3.0;       // Trail distance behind the trade's best price since entry (x entry
                                                // ATR) once past breakeven - wide on purpose, see InpUseBreakeven

input group "=== Safety ==="
input int     InpMagic           = 750015;     // Magic number - DELIBERATELY different from Aurelius_EA.mq5's
                                                // 750004 so the two can run on the same account/symbol at the
                                                // same time without one's position tracking/circuit-breaker
                                                // state ever mixing with the other's
input int     InpMaxSpreadPoints = 60;         // Skip entries above this spread (0 = off)
input int     InpSlippage        = 20;         // Max deviation (points)
input double  InpMaxDailyLossPct = 0.0;        // Stop trading after this daily loss % (0 = off)
input group "=== Session protection ==="
input bool    InpUseSessionCheck = true;       // Respect the symbol's trading session
input int     InpNoEntryMinsBefore = 30;       // No NEW entries within N min of session close
input bool    InpCloseBeforeBreak  = true;     // Flatten before the daily break too  [now on by default - InpCloseOnFriday already worked this way, the daily Mon-Thu break didn't, see header]
input int     InpCloseMinsBefore    = 5;       // Flatten N min before session close
input bool    InpCloseOnFriday      = true;    // Flatten before the weekend
input int     InpFridayCloseHour    = 22;      // Server hour to flatten on Friday
input int     InpNoEntryAfterHourFri= 20;      // No new entries after this hour on Friday
input string  InpComment         = "Aurelius"; // Order comment

input group "=== Dashboard ==="
input bool    InpShowPanel  = true;              // Show the panel
input int     InpPanelDrag  = 1;                 // 0 = locked, 1 = draggable
input int     InpPanelX     = 12;                // X offset
input int     InpPanelY     = 30;                // Y offset (from the anchor edge)
input bool    InpPanelBottom = false;            // Anchor the panel to the BOTTOM left
input int     InpPanelW     = 260;               // Width
input color   InpPanelBg    = C'13,17,28';       // Panel background (solid)
input color   InpHeaderBg   = C'28,36,58';       // Header / section background
input color   InpPanelEdge  = C'255,196,84';      // Border - gold
input color   InpTitleCol   = C'255,196,84';      // Title text - gold
input color   InpSectionCol = C'214,226,238';     // Section headings - silver
input color   InpTextCol    = C'150,166,192';    // Labels
input color   InpValCol     = C'236,242,252';    // Values
input color   InpOkCol      = C'0,230,118';      // Met - neon green
input color   InpNoCol      = C'255,61,90';      // Not met - hot red
input color   InpShadowCol  = C'6,8,14';         // Drop shadow
input string  InpPanelFont  = "Consolas";        // Font
input int     InpPanelSize  = 8;                 // Font size
input string  InpBackgroundBMP = "goldbg_blend.bmp";             // Background image (.bmp in MQL5\Images)
input int     InpBgWidth       = 1290;           // Image width (px) - for centring only
input int     InpBgHeight      = 720;            // Image height (px) - for centring only
input group "=== Chart theme ==="
input bool    InpApplyTheme = true;              // Recolour the chart
input bool    InpHideTradeMarks = true;          // Hide MT5's own buy/sell/SL/TP arrows and lines - the panel
                                                  // and MA lines are meant to be the only things on this chart
input bool    InpShowMAs    = true;              // Draw the moving averages on the chart, each its own neon colour
input int     InpMAHistoryBars = 2500;           // How many recent bars of MA line history to keep drawn (bounded,
                                                  // so a long-running live EA doesn't accumulate objects forever)
input color   InpCol21      = clrYellow;         // MA 21 line colour
input color   InpCol50      = C'255,140,0';      // MA 50 line colour - neon orange (NOT white:
                                                  // InpBearCol/CHART_COLOR_CHART_DOWN are also
                                                  // white, and the 50 hugs price closely enough
                                                  // to vanish into bearish candle bodies/wicks)
input color   InpCol150     = C'191,0,255';      // MA 150 line colour - neon purple
input color   InpCol600     = C'255,20,147';     // MA 600 line colour - neon pink
input color   InpCol2400    = C'57,255,20';      // MA 2400 line colour - neon green
input bool    InpShowVWAP   = true;              // Draw the session VWAP this EA's own exit logic already reads
input color   InpColVWAP    = C'0,255,255';      // VWAP line colour - neon aqua, distinct from the 5 MAs
input int     InpVwapHistoryBars = 400;          // VWAP resets every session, so a long backfill window doesn't
                                                  // add anything - kept separate from InpMAHistoryBars, and
                                                  // small, so the OnInit backfill (SessionVWAP() re-walks up to
                                                  // 400 bars EVERY call - see its own header) stays fast
//--- v1.44 indicator-visibility inputs. Every one of these is cosmetic only:
//--- nothing below is read by any entry, exit, sizing or risk decision, and
//--- every draw they gate sits behind g_skipCosmeticDraws like the MA lines.
input bool    InpShowTradeLevels = true;         // Draw the OPEN position's entry and stop-loss as horizontal
                                                  // lines. InpHideTradeMarks (below, on by default) switches
                                                  // MT5's own CHART_SHOW_TRADE_LEVELS off, which left the real
                                                  // stop invisible with nothing replacing it - these two lines
                                                  // are the replacement, in this file's own palette
input color   InpColEntryLine = C'150,166,192';   // Entry-price line - same silver-grey as InpTextCol (a level,
                                                  // not a state: neither good nor bad news on its own)
input color   InpColStopLine  = C'255,61,90';     // Stop-loss line - same hot red as InpNoCol
input bool    InpShowSR      = true;              // Draw the prior-InpSRDays daily high/low the S/R proximity
                                                  // filter actually measures against. Independent of
                                                  // InpUseSRDist on purpose: the levels are worth seeing even
                                                  // when the filter that reads them is switched off
input color   InpColSR       = C'120,144,176';    // S/R level colour - InpSectionCol's silver, dimmed roughly
                                                  // in half so a static daily level never competes with the
                                                  // live MA lines for attention
input bool    InpShowPullbackBand = true;         // Draw the InpPullbackTolATR envelope around the pullback MA -
                                                  // the actual band PullbackOK() tests price against, and the
                                                  // one entry condition with no visible geometry until now
input color   InpColPullback = C'128,70,0';       // Pullback band colour - InpCol50's neon orange at ~half
                                                  // brightness, so the band reads as a zone belonging to that
                                                  // line rather than as a sixth MA (drawn STYLE_DOT too)
input color   InpChartBg    = clrBlack;           // Chart background - matches Ratchet/Slipstream/Tailwind/AuRebound
input color   InpBullCol    = C'0,150,255';       // Bullish candle - neon blue, same as Ratchet/Slipstream/Tailwind/AuRebound
input color   InpBearCol    = clrWhite;           // Bearish candle - neon white, same as Ratchet/Slipstream/Tailwind/AuRebound
input string  InpWatermark  = "AURELIUS";        // Watermark text (empty = none)
input color   InpWaterCol   = C'46,38,24';        // Watermark colour
input bool    InpWaterBottom = true;             // Watermark bottom-right instead of centred
input int     InpWaterSize  = 42;                // Watermark font size
input string  InpWaterFont  = "Arial Black";     // Watermark font

input group "=== Cross-EA signal (for Vanguard_M15_EA.mq5's optional conflict filter) ==="
input bool    InpPublishPosition = true;       // Publish this EA's real position direction via a terminal
                                                // global variable, so Vanguard_M15_EA.mq5 (attached to its own
                                                // chart) can optionally avoid entering directly against an
                                                // already-open Aurelius position - see Vanguard_M15_EA.mq5's own
                                                // header for the full design. Purely a broadcast: Aurelius's
                                                // own trading is completely unaffected whether this is on or
                                                // off, or whether anything is even reading it.

input group "=== Logging ==="
input bool    InpLogTrades       = true;       // Write closed trades to CSV
input bool    InpVerbose         = false;      // Print decisions to the Experts log

//------------------------------- globals ----------------------------
CTrade        trade;
CPositionInfo pos;

int h21=INVALID_HANDLE, h50=INVALID_HANDLE, h150=INVALID_HANDLE;
int h600=INVALID_HANDLE, h2400=INVALID_HANDLE;
int hMACD=INVALID_HANDLE;
// v1.36: ATR is no longer read via a built-in iATR() handle - see
// ComputeWilderATR()'s header note just above its definition for why.
// g_atrManual is refreshed once per new bar in OnTick(), read through
// GetATR() everywhere the old MA(hATR,1,atr) pattern was used.
double   g_atrManual = 0.0;

datetime g_lastBar   = 0;
datetime g_lastClose = 0;
int      g_barsSinceClose = 9999;
int      g_fh = INVALID_HANDLE;
double   g_dayStartEquity = 0.0;
int      g_dayStamp = -1;
//--- running accumulator for MyRealizedPLToday() - see PERFORMANCE FIX
//--- (v1.31) below. Updated incrementally in OnTradeTransaction(), reset
//--- alongside g_dayStamp in UpdateDayStamp().
double   g_myRealizedToday = 0.0;
//--- PERFORMANCE FIX (v1.32): true when running a non-visual Strategy
//--- Tester pass (no chart anyone is watching) - set once in OnInit().
//--- Gates the between-bar "keep the panel live" redraw in OnTick(),
//--- which is purely cosmetic and has zero effect on any trading
//--- decision. See the OnTick() note for why this mattered.
bool     g_skipCosmeticDraws = false;
ulong    g_ticket = 0;
datetime g_entryTime = 0;
double   g_entryPrice = 0.0, g_entryATR = 0.0;
int      g_entryDir   = 0;
double   g_entryLots  = 0.0;
int      g_entryBarCount = 0;
int      g_addsDone = 0;
int      g_price21Bad = 0;    // consecutive closed bars price has spent through the 21 against the trade
int      g_vwapBad = 0;       // consecutive closed bars price has spent through session VWAP against the trade
bool     g_beDone = false;    // stop already moved to breakeven this trade - see InpUseBreakeven
double   g_peakFavPx = 0.0;   // best closed-bar price seen in the trade's favor - see InpUseTrailAfterBE

#define NEED_BARS 60

//--- forward declaration: OnInit draws the panel before DrawPanel is defined
void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim = true);
void PTheme();
void UpdateMALines();
bool GetATR(double &out);   // OnInit's position-state restore (2026-09-06) needs these two before their definitions
bool HasOwnPosition();
void BackfillMALines();
void UpdateLevelLines();   // v1.44: OnInit draws the price levels at attach time too
void PBackground();
void PWatermark();
double SessionVWAP(const int shift);   // defined later - UpdateMALines/BackfillMALines now call it too
bool SRLevels(double &hi, double &lo); // v1.44: defined next to SRDistanceATR (its only other caller), but
                                        // UpdateLevelLines() sits up with the rest of the drawing code
double PullbackLine(const int shift);  // v1.44: the pullback band is drawn around whichever MA PullbackOK()
                                        // actually tests, so UpdateMALines/BackfillMALines need this early
void ComputeWilderATR(const MqlRates &arr[], double &out[], int period);   // v1.44: BackfillMALines() needs a
                                                                           // per-bar ATR series for the band
string g_pp = "AURP_";
string g_pw = "AURW_";   // wallpaper and watermark, kept out of the panel wipe
string g_pm = "AURM_";   // per-bar MA line segments, purged to a rolling window - see UpdateMALines
//--- v1.44: horizontal price levels (entry, stop, prior-days S/R). Deliberately
//--- NOT g_pm: those are per-bar OBJ_TREND segments swept by PurgeOldMALines on
//--- a rolling window, whereas these are a fixed handful of OBJ_HLINEs that are
//--- updated in place and deleted explicitly the moment they stop applying. The
//--- pullback band is the one new drawing that DOES belong to g_pm - it really
//--- is a per-bar segment pair, so it wants exactly the same purge treatment.
string g_pl = "AURL_";
int    g_panX = -1, g_panY = -1;      // live panel position, updated by dragging
bool   g_bgOK = false;                // background image loaded successfully
int    g_bgTries = 0;

//--- cross-EA signal (see InpPublishPosition) - M15-specific name so
//--- Vanguard_M15_EA.mq5's own M15 reader and Vanguard_EA.mq5's M5
//--- reader (reading Aurelius_EA.mq5's own, separately-named variable)
//--- can never cross-connect to the wrong timeframe pair.
string g_posDirGVarName = "";

//+------------------------------------------------------------------+
int OnInit()
  {
   //--- PERFORMANCE FIX (v1.32): see g_skipCosmeticDraws declaration and
   //--- the OnTick() note below.
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);

   //--- "M15" is literal, not PERIOD_CURRENT-derived: this file always
   //--- runs on M15 (see this EA's own symbol/period conventions), and
   //--- Vanguard_M15_EA.mq5's reader needs a name it can compute
   //--- without ever having queried this chart's actual period.
   g_posDirGVarName = "AURELIUS_POSDIR_M15_" + _Symbol;

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   h21   = iMA(_Symbol, PERIOD_CURRENT, InpP21,   0, InpM21,   InpPrice);
   h50   = iMA(_Symbol, PERIOD_CURRENT, InpP50,   0, InpM50,   InpPrice);
   h150  = iMA(_Symbol, PERIOD_CURRENT, InpP150,  0, InpM150,  InpPrice);
   h600  = iMA(_Symbol, PERIOD_CURRENT, InpP600,  0, InpM600,  InpPrice);
   h2400 = iMA(_Symbol, PERIOD_CURRENT, InpP2400, 0, InpM2400, InpPrice);
   hMACD = iMACD(_Symbol, PERIOD_CURRENT, 12, 26, 9, PRICE_CLOSE);
   PrintFormat("EA init: handles 21=%d 50=%d 150=%d 600=%d 2400=%d MACD=%d (ATR is computed manually, see ComputeWilderATR)",
               h21, h50, h150, h600, h2400, hMACD);
   if(h21==INVALID_HANDLE || h50==INVALID_HANDLE || h150==INVALID_HANDLE ||
      h600==INVALID_HANDLE || h2400==INVALID_HANDLE ||
      hMACD==INVALID_HANDLE)
     {
      Print("EA: failed to create an indicator handle. Error ", GetLastError());
      return(INIT_FAILED);
     }
   PrintFormat("EA init: bars available=%d, needed=%d",
               Bars(_Symbol, PERIOD_CURRENT), InpP2400 + NEED_BARS);
   PrintFormat("EA init: algo trading terminal=%s expert=%s",
               (TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "ON" : "OFF"),
               (MQLInfoInteger(MQL_TRADE_ALLOWED) ? "ON" : "OFF"));

   if(Period() != PERIOD_M15)
      Print("WARNING: this variant (Aurelius_M15_EA) is tuned for M15 - its InpP600/InpP2400/InpM600 "
            "defaults are M15-specific rescales/refinements of Aurelius_EA.mq5's M5 values and are NOT "
            "validated on any other timeframe. Current timeframe is ",
            EnumToString((ENUM_TIMEFRAMES)Period()));

   UpdateATRManual();   // initial seed - also refreshed once per new bar in OnTick()
   g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);

   // 2026-09-06 (Opus deep-dive review): a terminal restart, recompile, or
   // input change while a position is open resets every g_entry*/g_ticket
   // global to its 0/0.0 initializer - MQL5 re-runs OnInit() in all three
   // cases. None of that happens mid-Strategy-Tester-run, which is why four
   // rounds of backtests never surfaced this. Concrete consequence: the
   // weekend/holiday flatten (WeekendStillOpen) fails its own
   // `g_entryTime > 0` guard and goes dead for the rest of that trade,
   // exactly the exposure item 1's original fix exists to prevent - the
   // fix there was correct WITHIN a single continuous run, but was never
   // extended to cover a restart mid-trade. Trailing/breakeven are
   // separately guarded against g_entryATR<=0 (and both default off
   // anyway), so this restore is really about the flatten and the panel/
   // CSV reading real values instead of zeros until the trade closes.
   if(HasOwnPosition())
     {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         if(!pos.SelectByIndex(i)) continue;
         if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
         g_ticket      = pos.Ticket();
         g_entryTime   = (datetime)PositionGetInteger(POSITION_TIME);
         g_entryPrice  = pos.PriceOpen();
         g_entryDir    = (pos.PositionType() == POSITION_TYPE_BUY) ? 1 : -1;
         g_entryLots   = pos.Volume();
         g_peakFavPx   = g_entryPrice;
         //--- 2026-09-20 (Opus drawdown/profit review, ported from Aurelius_EA.mq5):
         //--- the restore above still missed g_entryBarCount/g_addsDone/
         //--- g_price21Bad/g_vwapBad/g_beDone - without these, a restart/
         //--- recompile/input change mid-trade silently restarts the Price21/
         //--- VWAP confirm-bar streaks (delaying both SHIPPED exits by up to
         //--- InpPrice21ConfirmBars/InpVwapConfirmBars bars) and would zero the
         //--- stale/max-bars clock if either were ever enabled. g_addsDone is not
         //--- reconstructable from broker state (which leg is the "base" is
         //--- unknown) - reset to 0, meaning at most one fewer add than intended
         //--- after a restart, not a wrong count.
         g_entryBarCount = (int)((TimeCurrent() - g_entryTime) / PeriodSeconds());
         g_addsDone      = 0;
         g_price21Bad    = 0;
         g_vwapBad       = 0;
         g_beDone        = (pos.StopLoss() != 0.0 &&
                            ((g_entryDir > 0 && pos.StopLoss() >= g_entryPrice) ||
                             (g_entryDir < 0 && pos.StopLoss() <= g_entryPrice)));
         double atrNow;
         g_entryATR    = GetATR(atrNow) ? atrNow : 0.0;   // atr<=0 (cold read) leaves trailing/breakeven disabled, not armed on bad data
         PrintFormat("Aurelius EA: restored open position #%I64u from OnInit (entry %.2f, %s, %.2f lots)",
                     g_ticket, g_entryPrice, (g_entryDir>0?"BUY":"SELL"), g_entryLots);
         break;
        }
     }
   //--- PERFORMANCE FIX (v1.33): this timer is completely independent of
   //--- OnTick() - the v1.32 fix gated OnTick()'s own per-second panel
   //--- draws but never touched this. Strategy Tester DOES simulate
   //--- timer events, so EventSetTimer(1) was firing OnTimer() (which
   //--- redraws the same 37-row panel) once per simulated second for the
   //--- entire backtest regardless of the v1.32 fix - this is almost
   //--- certainly what was still burning hours after that fix showed no
   //--- improvement. Not started at all in a non-visual Tester run;
   //--- OnTimer() also early-returns as a defense-in-depth backstop.
   if(!g_skipCosmeticDraws) EventSetTimer(1);
   PTheme();                       // theme applies even with the panel off
   if(!g_skipCosmeticDraws) BackfillMALines(); // fill in the whole rolling window immediately,
                                                // not just a 1-bar stub per line (see its comment)
   //--- v1.44: same "show something the moment it attaches" reasoning as the
   //--- DrawPanel() call below and as BackfillMALines above - otherwise the
   //--- stop/entry/S-R levels would not appear until the next M5 bar closes,
   //--- and on a restart with a position already open that is exactly the
   //--- moment the stop most needs to be visible.
   if(!g_skipCosmeticDraws) UpdateLevelLines();
   ChartRedraw(0);
   if(InpShowPanel)
     {
      bool hl0 = false, hs0 = false;
      DrawPanel(hl0, hs0);          // show something the moment it attaches
      ChartRedraw(0);
     }
   Print("Aurelius EA started. Magic ", InpMagic,
         "  lots ", InpLots, "  symbol ", _Symbol);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_fh != INVALID_HANDLE) { FileClose(g_fh); g_fh = INVALID_HANDLE; }
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pw);
   ObjectsDeleteAll(0, g_pm);
   ObjectsDeleteAll(0, g_pl);   // v1.44: entry/stop/S-R horizontal levels
   Comment("");
  }
//+------------------------------------------------------------------+
//| Catches closes ClosePosition() never sees: a broker-side stop-loss|
//| fill happens on the broker's own server, not through this EA's    |
//| own trade.PositionClose() call, so nothing in OnTick() ever ran    |
//| LogClosed() - OR reset the cooldown/state tracking - for it.       |
//| Roughly 1 in 6-7 real trades (the SL hits) were silently missing   |
//| from the CSV, and InpCooldownBars was not being respected after    |
//| one either, since g_barsSinceClose never got reset to 0 the way    |
//| ClosePosition() already does for its own closes. This handles      |
//| exactly the SL-hit case and only that case: an EA-initiated close  |
//| already gets logged AND resets state inline via ClosePosition(),   |
//| and that always carries DEAL_REASON_EXPERT, not DEAL_REASON_SL -   |
//| so filtering on SL specifically here means every close is handled  |
//| exactly once, from exactly one place, never both.                  |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Push notification on trade open/close, via MT5's own               |
//| SendNotification() - requires this terminal's MetaQuotes ID under   |
//| Tools>Options>Notifications with "Enable Notifications" checked;     |
//| a silent false return otherwise, and SendNotification() does         |
//| nothing at all inside the Strategy Tester regardless of that          |
//| setting, so it's skipped there rather than logged as a failure.        |
//+------------------------------------------------------------------+
void NotifyPush(const string text)
  {
   if(MQLInfoInteger(MQL_TESTER)) return;
   if(!SendNotification(text))
      PrintFormat("Aurelius_M15_EA: SendNotification failed (err %d) - check Tools>Options>Notifications", GetLastError());
  }
void NotifyTradeOpen(ulong ticket)
  {
   double vol  = HistoryDealGetDouble(ticket, DEAL_VOLUME);
   double px   = HistoryDealGetDouble(ticket, DEAL_PRICE);
   bool isBuy  = (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_BUY;
   NotifyPush(StringFormat("Aurelius M15 OPEN %s %.2f %s @ %.2f", isBuy ? "BUY" : "SELL", vol, _Symbol, px));
  }
void NotifyTradeClose(ulong ticket)
  {
   double px = HistoryDealGetDouble(ticket, DEAL_PRICE);
   double pl = HistoryDealGetDouble(ticket, DEAL_PROFIT)
             + HistoryDealGetDouble(ticket, DEAL_SWAP)
             + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   //--- a CLOSING deal's own DEAL_TYPE is the opposite side of the position
   //--- it closed (closing a BUY position is itself a SELL deal) - invert it
   //--- to report the position's real direction, not the closing action.
   bool wasBuy = (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_SELL;
   NotifyPush(StringFormat("Aurelius M15 CLOSE %s @ %.2f  P/L: %s$%.2f",
              wasBuy ? "BUY" : "SELL", px, pl >= 0 ? "+" : "-", MathAbs(pl)));
  }
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   ulong ticket = trans.deal;
   if(ticket == 0) return;
   //--- a just-added deal isn't guaranteed to already be in the selected
   //--- history window - select it explicitly rather than assume the
   //--- terminal's cache already covers it (the deal-getters below return
   //--- 0/empty on an unselected ticket, which would silently skip both
   //--- the P/L accumulator AND the g_barsSinceClose reset right below it -
   //--- Fulcrum_EA.mq5 already had this fix, ported verbatim; Opus review
   //--- of the panel-flash fix caught that Aurelius itself never got it).
   if(!HistoryDealSelect(ticket)) return;
   if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) return;

   ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
   if(dealEntry == DEAL_ENTRY_IN)
     {
      NotifyTradeOpen(ticket);
      return;
     }
   if(dealEntry != DEAL_ENTRY_OUT) return;
   NotifyTradeClose(ticket);

   //--- every real close (SL or EA-initiated) reaches here exactly once,
   //--- per the comment above - accumulate this EA's own realized P&L
   //--- incrementally here instead of MyRealizedPLToday() re-scanning the
   //--- whole day's deal history from HistorySelect() on every panel draw.
   //--- See PERFORMANCE FIX (v1.31) below.
   g_myRealizedToday += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                       + HistoryDealGetDouble(ticket, DEAL_SWAP)
                       + HistoryDealGetDouble(ticket, DEAL_COMMISSION);

   if((ENUM_DEAL_REASON)HistoryDealGetInteger(ticket, DEAL_REASON) != DEAL_REASON_SL) return;
   double exitPx = HistoryDealGetDouble(ticket, DEAL_PRICE);
   LogClosed("SL", exitPx);
   g_lastClose = TimeCurrent();
   g_barsSinceClose = 0;
   g_ticket = 0;
  }
//+------------------------------------------------------------------+
//| Panel primitives.                                                 |
//| All layout is left-corner based. Right corners invert the X axis   |
//| in MT5, which silently mirrored the whole panel off-screen.        |
//+------------------------------------------------------------------+
//--- rough monospace-ish width estimate, same formula used across the
//--- other EAs' panels (Slipstream/Tailwind) for consistency
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
//--- self-learning minimum panel width: PRow/title updates this as each
//--- row's real text is measured, and the NEXT DrawPanel() call uses it -
//--- lags one draw cycle behind (well under a second in practice) rather
//--- than needing a full two-pass restructure, and means no row can ever
//--- clip regardless of how long a value string gets.
int g_panelMinW = 0;
//--- Controls whether PRect/PText delete-and-recreate (to reclaim top-of-
//--- stack, see their own comments) or just update the existing object's
//--- properties in place. Reclaiming is only NEEDED once per new bar,
//--- right after UpdateMALines() adds the one new object that could bury
//--- the panel - churning it on EVERY draw call (which, between bars, was
//--- happening up to a few times a second between OnTimer's 1s tick and
//--- OnTick's live-P&L refresh) made the whole panel visibly flash/repaint
//--- instead of just its numbers updating, since deleting and recreating a
//--- dozen large filled rectangles is a much bigger visual event than the
//--- text-only churn this pattern originally shipped with. DrawPanel() sets
//--- this at the top of every call from its own `reclaim` parameter -
//--- true only for the once-per-new-bar draw (and the very first draw),
//--- false for every live-number-only refresh in between.
bool g_panelReclaim = true;
void PRect(const string id, const int x, const int y, const int w, const int h,
           const color bg, const color edge, const int border = 1)
  {
   string nm = g_pp + id;
   //--- only the background is grabbable, and it must not be HIDDEN or
   //--- MT5 will not let it be selected, which is what blocked dragging
   bool grab = (InpPanelDrag == 1 && id == "bg");
   bool exists = (ObjectFind(0, nm) >= 0);
   //--- same creation-order reasoning as PText below: everything EXCEPT the
   //--- draggable bg gets deleted and recreated when g_panelReclaim is set,
   //--- so it stays the newest object and can't get buried under an MA line
   //--- segment drawn since the last reclaim. bg keeps its identity so an
   //--- in-progress drag doesn't get reset mid-motion - see the "fl" fill
   //--- rect drawn right after it in DrawPanel(), which reclaims the same
   //--- way and is what actually keeps the panel body opaque.
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
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);       // in front of candles
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, grab);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, !grab);
   //--- ZORDER affects click priority, not visual stacking (see the note
   //--- in PText) - set high anyway in case a future build changes that,
   //--- but the actual fix for the panel showing through trade arrows/MA
   //--- lines is the g_panelReclaim-gated delete-and-recreate above, not this.
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5000);
  }
//+------------------------------------------------------------------+
//| PRect's own OBJ_RECTANGLE_LABEL border (BORDER_FLAT + OBJPROP_COLOR) |
//| renders unreliably in this terminal build - observed live as only     |
//| two of the four sides actually drawn (top + one side), bottom and      |
//| the other side missing. Rather than depend on that object's built-in    |
//| border at all, this draws an explicit 4-strip frame - one thin filled     |
//| rectangle per edge - immune to the quirk since each strip is just an       |
//| ordinary solid-filled OBJ_RECTANGLE_LABEL, the one thing that already       |
//| renders correctly. Same fix, same helper, as Fulcrum_EA.mq5/Ratchet_EA.mq5.|
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
   //--- an OBJ_LABEL with empty text renders MT5's default "Label" - this
   //--- delete is unconditional (not gated by g_panelReclaim) because it's
   //--- not about stacking, it's a row that genuinely no longer has a value
   //--- (e.g. switching from "in position" to flat) and needs to disappear.
   if(txt == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   bool exists = (ObjectFind(0, nm) >= 0);
   //--- MT5 stacks chart objects by CREATION order, not by ZORDER (per the
   //--- note further down) - a trade arrow/line MT5 draws natively when an
   //--- order fills is created AFTER the panel already exists, so left
   //--- alone it renders on top and the text shows through it, and so does
   //--- a new MA line segment. Deleting and recreating this text object
   //--- (instead of just updating it in place) makes it the newest object
   //--- on the chart again, keeping the actual readable content on top of
   //--- anything MT5/UpdateMALines has drawn since the last reclaim -  but
   //--- only actually needed once per new bar (when a new MA segment was
   //--- just drawn), gated by g_panelReclaim; see its own comment for why
   //--- churning this every draw call caused visible flashing.
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
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5001);      // above PRect's 5000
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
                    rightAlign ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
  }
//+------------------------------------------------------------------+
//| A row: status dot, label on the left, value right-aligned.        |
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
   //--- learn the width this row actually needed, for next draw cycle
   int need = 26 + EstimateTextWidth(label, InpPanelSize) + 16
              + EstimateTextWidth(value, InpPanelSize) + 20;
   if(need > g_panelMinW) g_panelMinW = need;
  }
//+------------------------------------------------------------------+
//| Section heading on its own tinted band.                           |
//+------------------------------------------------------------------+
void PSection(const string id, const int x, const int y, const int w,
              const int rh, const string title)
  {
   //--- band created first, label second, or the band hides the label
   PRect(id + "bar", x + 1, y - 3, w - 2, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x + 10, y, title, InpSectionCol, InpPanelSize, false, "Arial Bold");
  }
//+------------------------------------------------------------------+
void PBackground()
  {
   string nm = g_pw + "bmp";
   if(InpBackgroundBMP == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); g_bgOK = true; return; }
   if(g_bgOK) return;                       // already showing, nothing to do
   if(g_bgTries > 40) return;               // give up quietly after ~40 tries

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
   //--- the bitmap is now the newest background object, so rebuild the
   //--- watermark once to put it back on top
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
   //--- the panel/MA lines are meant to be the only things on this chart -
   //--- MT5's own buy/sell arrows and SL/TP lines are a terminal display
   //--- setting, not chart objects, so they can't be deleted via code -
   //--- this is the actual way to turn them off.
   if(InpHideTradeMarks)
     {
      ChartSetInteger(0, CHART_SHOW_TRADE_LEVELS, false);
      ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, false);
     }
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Centred watermark. Drawn BEHIND the candles so it never obscures   |
//| price - it tints the empty space instead.                          |
//+------------------------------------------------------------------+
//| Each MA drawn as its own neon-coloured line. An EA has no plot       |
//| buffers (only an indicator can set PLOT_LINE_COLOR), so the old       |
//| ChartIndicatorAdd() approach could only show MT5's own auto-assigned    |
//| colours, never a specific one per line - this draws one new trend        |
//| segment per MA per new bar instead (bar[shift2]->bar[shift1], same         |
//| idiom this repo already uses for session VWAP dots), and sweeps            |
//| anything older than InpMAHistoryBars so a long-running live EA doesn't      |
//| accumulate objects forever. Called once per new bar (OnTick), gated by       |
//| g_skipCosmeticDraws same as every other cosmetic draw in this file.           |
//+------------------------------------------------------------------+
//| v1.44: `style` added (default STYLE_SOLID, so every existing call      |
//| below is byte-for-byte unchanged) purely so the pullback-tolerance      |
//| band can be drawn dotted through this same function - the band is       |
//| a guide, not an indicator line, and must not read as a sixth MA.        |
//+------------------------------------------------------------------+
void DrawMASegment(const string tag, const datetime tOld, const double vOld,
                    const datetime tNew, const double vNew, const color col,
                    const ENUM_LINE_STYLE style = STYLE_SOLID)
  {
   string nm = g_pm + tag + "_" + IntegerToString((long)tNew);
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_TREND, 0, tOld, vOld, tNew, vNew);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);      // keep it out of the Object List/dialog -
                                                        // up to 5*InpMAHistoryBars of these exist
  }
//+------------------------------------------------------------------+
void PurgeOldMALines(const datetime latestBarTime)
  {
   datetime cutoff = latestBarTime - (datetime)((long)InpMAHistoryBars * PeriodSeconds(PERIOD_CURRENT));
   for(int i = ObjectsTotal(0, 0, OBJ_TREND) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, OBJ_TREND);
      if(StringFind(nm, g_pm) != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < cutoff) ObjectDelete(0, nm);
     }
  }
//+------------------------------------------------------------------+
//| v1.44 - horizontal price levels (entry / stop / prior-days S+R).     |
//|                                                                      |
//| A stop or a daily high doesn't move bar to bar, so these are single   |
//| OBJ_HLINE rays rather than the per-bar OBJ_TREND segments the MAs      |
//| need - one object each, not one per bar, so there is nothing here for  |
//| PurgeOldMALines to sweep and no risk of the 1,500-object flood that     |
//| forced OBJPROP_HIDDEN onto DrawMASegment in v1.38.                      |
//|                                                                         |
//| Created once and then UPDATED IN PLACE (ObjectSetDouble on the existing  |
//| object) rather than deleted and recreated. That matters for exactly the   |
//| reason g_panelReclaim exists: MT5 stacks objects by creation order, so    |
//| recreating a level every bar would keep re-burying the panel under it.    |
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
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);   // same reason as DrawMASegment - these
                                                     // are EA chrome, not user-drawn analysis
  }
//+------------------------------------------------------------------+
//| Called once per new bar from OnTick, immediately after                |
//| UpdateMALines() and BEFORE DrawPanel() - the same creation-order       |
//| reasoning that already puts UpdateMALines there (see that call site).  |
//| Deliberately not folded into DrawPanel()'s own in-position branch,     |
//| even though that branch already has pos.PriceOpen()/pos.StopLoss()     |
//| in scope: anything created from inside DrawPanel() would be created    |
//| AFTER the panel's own background/frame that same cycle and would       |
//| therefore paint over it.                                              |
//|                                                                        |
//| Purely cosmetic - reads position state and daily highs/lows, writes     |
//| nothing but chart objects. It can never affect a trading decision.      |
//+------------------------------------------------------------------+
void UpdateLevelLines()
  {
   //--- open position: entry price and the stop actually sitting at the
   //--- broker. InpHideTradeMarks turns MT5's own SL/TP lines off, so
   //--- without these two the real stop is invisible on a live chart.
   if(InpShowTradeLevels)
     {
      double opx = 0.0, sl = 0.0;
      bool   found = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         if(!pos.SelectByIndex(i)) continue;
         if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
         opx = pos.PriceOpen();
         sl  = pos.StopLoss();     // 0.0 when InpUseStopLoss is off - handled below
         found = true;
         break;                    // this EA runs one position at a time
        }
      if(found)
        {
         DrawLevelLine("entry", opx, InpColEntryLine, STYLE_SOLID, 1);
         //--- sl == 0.0 with a position open is a real, normal state here
         //--- (InpUseStopLoss defaults on, but can be off, and this file's
         //--- own header documents long stretches run without one) - draw
         //--- nothing rather than a line at price 0.
         if(sl > 0.0) DrawLevelLine("sl", sl, InpColStopLine, STYLE_SOLID, 1);
         else         DeleteLevelLine("sl");
        }
      else
        { DeleteLevelLine("entry"); DeleteLevelLine("sl"); }
     }
   else
     { DeleteLevelLine("entry"); DeleteLevelLine("sl"); }

   //--- prior-InpSRDays daily high/low - the exact pair SRDistanceATR()
   //--- measures against (same SRLevels() call, not a re-derivation, so
   //--- the drawn level cannot drift from the tested one). Dashed, because
   //--- these are structural reference levels, not live indicator values.
   if(InpShowSR)
     {
      double hi, lo;
      if(SRLevels(hi, lo))
        {
         DrawLevelLine("srhi", hi, InpColSR, STYLE_DASH, 1);
         DrawLevelLine("srlo", lo, InpColSR, STYLE_DASH, 1);
        }
     }
   else
     { DeleteLevelLine("srhi"); DeleteLevelLine("srlo"); }
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| True when shifts a and b (both closed bars) fall on different       |
//| calendar days - used to skip drawing a VWAP segment across a         |
//| session boundary, where the line would otherwise jump from the        |
//| previous day's final rolling value straight to the next day's fresh    |
//| reset and read as a real move instead of an indicator restart.          |
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
void UpdateMALines()
  {
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, 2);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(tA == 0 || tB == 0) return;
   if(InpShowMAs)
     {
      double m21a, m21b, m50a, m50b, m150a, m150b, m600a, m600b, m2400a, m2400b;
      if(MA(h21,2,m21a) && MA(h21,1,m21b) && MA(h50,2,m50a) && MA(h50,1,m50b) &&
         MA(h150,2,m150a) && MA(h150,1,m150b) && MA(h600,2,m600a) && MA(h600,1,m600b) &&
         MA(h2400,2,m2400a) && MA(h2400,1,m2400b))
        {
         DrawMASegment("21",   tA, m21a,   tB, m21b,   InpCol21);
         DrawMASegment("50",   tA, m50a,   tB, m50b,   InpCol50);
         DrawMASegment("150",  tA, m150a,  tB, m150b,  InpCol150);
         DrawMASegment("600",  tA, m600a,  tB, m600b,  InpCol600);
         DrawMASegment("2400", tA, m2400a, tB, m2400b, InpCol2400);
        }
     }
   if(InpShowVWAP && !DifferentSession(2, 1))
     {
      double vA = SessionVWAP(2), vB = SessionVWAP(1);
      if(vA > 0.0 && vB > 0.0) DrawMASegment("vwap", tA, vA, tB, vB, InpColVWAP);
     }
   //--- v1.44: the pullback tolerance envelope - PullbackOK() requires a wick
   //--- into InpPullbackTolATR x ATR of the pullback MA, which until now was
   //--- the only entry condition in this file with no visible geometry at all
   //--- (the MA it is measured from was drawn, the band around it was not).
   //--- Tracks PullbackLine(), not h50 directly, so it follows InpPullbackMA
   //--- if that input is ever changed off its PB_50 default - the drawn band
   //--- is then still the band actually tested, never a look-alike.
   if(InpShowPullbackBand)
     {
      double atr;
      if(GetATR(atr) && atr > 0.0)
        {
         double lA = PullbackLine(2), lB = PullbackLine(1);
         if(lA > 0.0 && lB > 0.0)
           {
            //--- GetATR() is the last-CLOSED-bar value (g_atrManual, refreshed
            //--- once per new bar right above this call site), i.e. the ATR at
            //--- shift 1 - the same reading PullbackOK() itself uses. Applied
            //--- to both ends of this one-bar segment, which leaves at most a
            //--- sub-pixel step between consecutive segments as ATR drifts.
            double tol = atr * InpPullbackTolATR;
            DrawMASegment("pbhi", tA, lA + tol, tB, lB + tol, InpColPullback, STYLE_DOT);
            DrawMASegment("pblo", tA, lA - tol, tB, lB - tol, InpColPullback, STYLE_DOT);
           }
        }
     }
   //--- purges everything tagged g_pm (MAs, VWAP and the pullback band alike),
   //--- so this must run whenever ANY of them is shown, not nested inside just
   //--- one of them - a band drawn with the MAs switched off would otherwise
   //--- accumulate forever, the exact leak PurgeOldMALines exists to prevent.
   if(InpShowMAs || InpShowVWAP || InpShowPullbackBand) PurgeOldMALines(tB);
  }
//+------------------------------------------------------------------+
//| UpdateMALines() only ever draws ONE new bar's worth of segment per     |
//| call, so a fresh attach would show a single 1-bar stub per line and     |
//| take InpMAHistoryBars bars (300 = ~25h on M5) to fill in the window       |
//| the input claims to be showing. Called once from OnInit instead, this      |
//| walks backward and draws the whole rolling window immediately. Same        |
//| shift-1-minimum, no-lookahead indexing as UpdateMALines - never touches     |
//| bar 0.                                                                        |
//+------------------------------------------------------------------+
void BackfillMALines()
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
         if(MA(h21,  s+1,a) && MA(h21,  s,b)) DrawMASegment("21",  tA,a,tB,b,InpCol21);
         if(MA(h50,  s+1,a) && MA(h50,  s,b)) DrawMASegment("50",  tA,a,tB,b,InpCol50);
         if(MA(h150, s+1,a) && MA(h150, s,b)) DrawMASegment("150", tA,a,tB,b,InpCol150);
         if(MA(h600, s+1,a) && MA(h600, s,b)) DrawMASegment("600", tA,a,tB,b,InpCol600);
         if(MA(h2400,s+1,a) && MA(h2400,s,b)) DrawMASegment("2400",tA,a,tB,b,InpCol2400);
        }
     }
   //--- VWAP gets its own, much smaller backfill window - SessionVWAP()
   //--- re-walks up to 400 bars on EVERY call (see its own header), so
   //--- backfilling it as far back as the MAs would make OnInit slow for
   //--- an indicator that resets every session anyway - see InpVwapHistoryBars.
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
         if(vA > 0.0 && vB > 0.0) DrawMASegment("vwap", tA, vA, tB, vB, InpColVWAP);
        }
     }
   //--- v1.44: the same backfill for the pullback band, so a fresh attach
   //--- shows the whole envelope rather than a 2-bar stub. The band's width
   //--- at bar s has to be the ATR AT bar s - PullbackOK() is evaluated with
   //--- that bar's ATR - so painting all 2500 bars with today's g_atrManual
   //--- would draw a constant-width band that was never the band actually
   //--- tested back there. One CopyRates + one ComputeWilderATR gives the
   //--- whole series in a single pass instead of an ATR read per bar; the
   //--- +500 warm-up bars are for the reason UpdateATRManual()'s own header
   //--- gives (a short window leaves the Wilder SMA seed carrying real
   //--- weight, measured up to +20.8% ATR error).
   if(InpShowPullbackBand)
     {
      int availB = Bars(_Symbol, PERIOD_CURRENT) - 2;
      int nB = MathMin(InpMAHistoryBars, availB);
      MqlRates rr[]; ArraySetAsSeries(rr, false);
      int got = CopyRates(_Symbol, PERIOD_CURRENT, 1, nB + 1 + 500, rr);
      if(got >= 14 + 2)
        {
         double atrSeries[];
         ComputeWilderATR(rr, atrSeries, 14);
         for(int s = nB; s >= 1; s--)
           {
            //--- rr[] is ascending (oldest first) and its LAST element is
            //--- shift 1, so shift s lives at index got - s.
            int iA = got - (s + 1), iB = got - s;
            if(iA < 0 || iB < 0) continue;
            double atrA = atrSeries[iA], atrB = atrSeries[iB];
            if(atrA == EMPTY_VALUE || atrB == EMPTY_VALUE || atrA <= 0.0 || atrB <= 0.0) continue;
            datetime tA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
            datetime tB = iTime(_Symbol, PERIOD_CURRENT, s);
            if(tA == 0 || tB == 0) continue;
            double lA = PullbackLine(s + 1), lB = PullbackLine(s);
            if(lA <= 0.0 || lB <= 0.0) continue;
            double tolA = atrA * InpPullbackTolATR, tolB = atrB * InpPullbackTolATR;
            DrawMASegment("pbhi", tA, lA + tolA, tB, lB + tolB, InpColPullback, STYLE_DOT);
            DrawMASegment("pblo", tA, lA - tolA, tB, lB - tolB, InpColPullback, STYLE_DOT);
           }
        }
     }
  }
//+------------------------------------------------------------------+
void PWatermark()
  {
   string nm = g_pw + "wm";
   if(InpWatermark == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   //--- created once. It is recreated only when the bitmap reloads, so it
   //--- stays layered above the wallpaper without redrawing every tick.
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
//| Buffer helpers. Shift 1 everywhere = the last CLOSED bar, which   |
//| is what the backtest used. Never the forming bar.                 |
//+------------------------------------------------------------------+
bool MA(const int handle, const int shift, double &out)
  {
   double b[];
   ArraySetAsSeries(b, true);
   if(CopyBuffer(handle, 0, shift, 1, b) < 1) return(false);
   out = b[0];
   return(true);
  }
//+------------------------------------------------------------------+
bool BufVal(const int handle, const int bufIdx, const int shift, double &out)
  {
   double b[];
   ArraySetAsSeries(b, true);
   if(CopyBuffer(handle, bufIdx, shift, 1, b) < 1) return(false);
   out = b[0];
   return(true);
  }
//+------------------------------------------------------------------+
//| Manual Wilder ATR, matching the Python atr_wilder() implementation |
//| this whole file's ATR-scaled thresholds were tuned against (SMA    |
//| seed of the first `period` true ranges landing at index `period`,  |
//| then Wilder recursive smoothing). Deliberately NOT the built-in    |
//| iATR() - a real GOLD# D1 export elsewhere in this repo proved this  |
//| broker's iATR is actually a plain SMA(period) of True Range, not    |
//| Wilder smoothing, despite MT5's own docs describing ATR as Wilder-   |
//| smoothed (see Zenith_EA.mq5's identical fix and its header note for  |
//| the verification). arr[] must be ascending (oldest-first), same as    |
//| CopyRates(..., ArraySetAsSeries(..., false)) returns.                  |
//+------------------------------------------------------------------+
void ComputeWilderATR(const MqlRates &arr[], double &out[], int period)
  {
   int n = ArraySize(arr);
   ArrayResize(out, n);
   for(int i = 0; i < n; i++) out[i] = EMPTY_VALUE;
   if(n <= period) return;
   double tr[]; ArrayResize(tr, n);
   tr[0] = arr[0].high - arr[0].low;
   for(int i = 1; i < n; i++)
      tr[i] = MathMax(arr[i].high - arr[i].low,
              MathMax(MathAbs(arr[i].high - arr[i-1].close), MathAbs(arr[i].low - arr[i-1].close)));
   double seed = 0;
   for(int i = 1; i <= period; i++) seed += tr[i];
   out[period] = seed / period;
   for(int i = period + 1; i < n; i++)
      out[i] = (out[i-1] * (period - 1) + tr[i]) / period;
  }
//+------------------------------------------------------------------+
//| Refreshes g_atrManual from the last CLOSED bar - called once at     |
//| OnInit (initial seed) and once per new bar in OnTick(). A real       |
//| Opus review caught that a short window here (originally 14*3=42       |
//| bars) leaves the SMA seed carrying real weight - (13/14)^(42-14) is     |
//| still 13.5%, measured up to +20.8% ATR error when a volatility spike     |
//| (one M5 news candle) sits in the seed slice, which directly mis-sizes     |
//| the stop/lots/breakeven/trail. 500 bars gives (13/14)^(500-14) ~= 0, i.e.  |
//| a genuinely converged Wilder value, not just a seeded one - InpP2400+       |
//| NEED_BARS is already required elsewhere in this file before any trading      |
//| logic runs, which comfortably covers it, and CopyRates(500) is cheap          |
//| either way (once per bar, not per tick).                                       |
//+------------------------------------------------------------------+
void UpdateATRManual()
  {
   MqlRates arr[]; ArraySetAsSeries(arr, false);
   int need = 500;
   int got = CopyRates(_Symbol, PERIOD_CURRENT, 1, need, arr);
   if(got < 14 + 2) return;   // leave g_atrManual at its previous value
   double out[]; ComputeWilderATR(arr, out, 14);
   double last = out[ArraySize(out) - 1];
   if(last != EMPTY_VALUE && last > 0.0) g_atrManual = last;
  }
//+------------------------------------------------------------------+
bool GetATR(double &out)
  {
   out = g_atrManual;
   return(out > 0.0);
  }
//+------------------------------------------------------------------+
bool MAs(const int shift, double &m21, double &m50, double &m150,
         double &m600, double &m2400, double &atr)
  {
   // GetATR() is always the last-closed-bar value (g_atrManual, refreshed
   // once per new bar) regardless of shift - fine everywhere in this file
   // since every call site passes shift=1, same bar GetATR() already means.
   return(MA(h21,shift,m21) && MA(h50,shift,m50) && MA(h150,shift,m150) &&
          MA(h600,shift,m600) && MA(h2400,shift,m2400) && GetATR(atr));
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Early exit candidate: fires once price has closed through the    |
//| 21 (by InpPrice21BufferATR) for InpPrice21ConfirmBars consecutive |
//| closed bars in a row - catching a reversal well before the 21x50  |
//| alignment break would. The counter resets to 0 the moment price   |
//| is back on the trade's side of the buffer, so a single wick/bar   |
//| through the line does not cost the streak - only a sustained move |
//| does. See the input group header - not yet real-tested.           |
//+------------------------------------------------------------------+
bool Price21Exit(const bool isBuy)
  {
   double m21, atr;
   if(!MA(h21, 1, m21) || !GetATR(atr) || atr <= 0.0) { g_price21Bad = 0; return(false); }
   double c = iClose(_Symbol, PERIOD_CURRENT, 1);
   double buf = InpPrice21BufferATR * atr;
   bool bad = isBuy ? (c < m21 - buf) : (c > m21 + buf);
   g_price21Bad = bad ? g_price21Bad + 1 : 0;
   return(g_price21Bad >= InpPrice21ConfirmBars);
  }
//+------------------------------------------------------------------+
//| Session-anchored VWAP as of the given shift, computed from closed |
//| bars back to the start of that bar's calendar day - MT5 has no    |
//| built-in VWAP indicator, so this walks the bar history directly,  |
//| matching the Python model's session_vwap() (typical price *       |
//| tick_volume, daily reset). Only called from position management,  |
//| which already runs at most once per bar, so the backward walk     |
//| (up to ~288 M5 bars/day) is cheap - not a per-tick cost.           |
//+------------------------------------------------------------------+
double SessionVWAP(const int shift)
  {
   datetime barTime = iTime(_Symbol, PERIOD_CURRENT, shift);
   if(barTime == 0) return(0.0);
   MqlDateTime dt; TimeToStruct(barTime, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);

   //--- one bulk copy per array instead of up to 400 individual iTime/
   //--- iHigh/iLow/iClose/iTickVolume calls (2000 individual history
   //--- lookups per invocation) - that was the real cost behind the slow
   //--- test runs, not repainting; this does the identical calculation,
   //--- just via CopyTime/CopyHigh/... in one shot each.
   datetime tArr[]; double hArr[], lArr[], cArr[]; long vArr[];
   //--- as-series so index 0 = shift (the most recent bar in the request),
   //--- matching the walk-backward-toward-day-start direction below -
   //--- CopyTime/CopyHigh/... default to oldest-first otherwise, which
   //--- would break the "stop at day start" loop on its very first bar
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
//| Early exit candidate: same buffer+confirm mechanic as Price21Exit,|
//| anchored to the session VWAP instead of the 21 - a different line |
//| entirely, so this can fire (or not) independently of that one.    |
//| See the input group header - not yet real-tested.                 |
//+------------------------------------------------------------------+
bool VwapExit(const bool isBuy)
  {
   double vw = SessionVWAP(1);
   double atr;
   if(vw <= 0.0 || !GetATR(atr) || atr <= 0.0) { g_vwapBad = 0; return(false); }
   double c = iClose(_Symbol, PERIOD_CURRENT, 1);
   double buf = InpVwapBufferATR * atr;
   bool bad = isBuy ? (c < vw - buf) : (c > vw + buf);
   g_vwapBad = bad ? g_vwapBad + 1 : 0;
   return(g_vwapBad >= InpVwapConfirmBars);
  }
//+------------------------------------------------------------------+
bool Aligned(const int shift, const bool isBuy)
  {
   double m21,m50,m150,m600,m2400,atr;
   if(!MAs(shift,m21,m50,m150,m600,m2400,atr)) return(false);
   double c = iClose(_Symbol, PERIOD_CURRENT, shift);
   if(c <= 0.0) return(false);

   if(isBuy)
     {
      if(InpAlignMode == ALIGN_FULL) { if(!(m600 > m2400)) return(false); }
      else                           { if(!(c > m2400))    return(false); }
      if(!(m21 > m50)) return(false);
      if(InpAlignMode == ALIGN_PRICE) return(true);
      if(!(m50 > m150)) return(false);
      if(InpAlignMode == ALIGN_FAST) return(true);
      return(m150 > m600);
     }
   if(InpAlignMode == ALIGN_FULL) { if(!(m600 < m2400)) return(false); }
   else                           { if(!(c < m2400))    return(false); }
   if(!(m21 < m50)) return(false);
   if(InpAlignMode == ALIGN_PRICE) return(true);
   if(!(m50 < m150)) return(false);
   if(InpAlignMode == ALIGN_FAST) return(true);
   return(m150 < m600);
  }
//+------------------------------------------------------------------+
double PullbackLine(const int shift)
  {
   double v = 0.0;
   if(InpPullbackMA == PB_21)  MA(h21,  shift, v);
   else if(InpPullbackMA == PB_150) MA(h150, shift, v);
   else MA(h50, shift, v);
   return(v);
  }
//+------------------------------------------------------------------+
double SlopeATR(const bool isBuy)
  {
   int hh = h50;
   if(InpSlopeMA == SLOPE_21)  hh = h21;
   if(InpSlopeMA == SLOPE_150) hh = h150;
   if(InpSlopeMA == SLOPE_600) hh = h600;
   double now, then, atr;
   if(!MA(hh, 1, now) || !MA(hh, 1 + InpSlopeBars, then) ||
      !GetATR(atr) || atr <= 0.0) return(0.0);
   double sl = (now - then) / atr;
   return(isBuy ? sl : -sl);
  }
//+------------------------------------------------------------------+
int CrissCross()
  {
   int n = 0;
   for(int j = 1; j <= InpCrossWindow; j++)
     {
      double a1,b1,a2,b2;
      if(!MA(h21,j,a1) || !MA(h50,j,b1) || !MA(h21,j+1,a2) || !MA(h50,j+1,b2))
         return(999);
      if((a1 > b1) != (a2 > b2)) n++;
     }
   return(n);
  }
//+------------------------------------------------------------------+
//| Pullback: price reached the MA within the lookback and the last    |
//| closed bar closed back on the trade side of it.                    |
//+------------------------------------------------------------------+
bool PullbackOK(const bool isBuy)
  {
   double atr;
   if(!GetATR(atr) || atr <= 0.0) return(false);
   double tol = atr * InpPullbackTolATR;
   double ln  = PullbackLine(1);
   double c   = iClose(_Symbol, PERIOD_CURRENT, 1);
   if(isBuy  && c <= ln) return(false);
   if(!isBuy && c >= ln) return(false);
   for(int j = 1; j <= InpPullbackBars; j++)
     {
      double lj = PullbackLine(j);
      if(isBuy  && iLow(_Symbol, PERIOD_CURRENT, j)  <= lj + tol) return(true);
      if(!isBuy && iHigh(_Symbol, PERIOD_CURRENT, j) >= lj - tol) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
//| CONFLUENS: a genuinely independent confirmation - momentum - on  |
//| top of the existing structure/volume/liquidity filters. Tested   |
//| standalone: PF rises from 2.45 to 3.13, win rate 38.6% -> 46.0%, |
//| max drawdown roughly halved, at the cost of about half the total |
//| trade count and profit. Requires the MACD histogram (MACD line   |
//| minus signal line) to have just turned - been falling and is now |
//| rising for buys, or the mirror for sells - confirming momentum   |
//| is shifting in the trade's favour right at entry, not just that  |
//| price and volume look right.                                    |
//+------------------------------------------------------------------+
bool MomentumShiftOK(const bool isBuy)
  {
   double macdNow, macdPrev1, macdPrev2, sigNow, sigPrev1, sigPrev2;
   if(!BufVal(hMACD, 0, 1, macdNow) || !BufVal(hMACD, 0, 2, macdPrev1) || !BufVal(hMACD, 0, 3, macdPrev2))
      return(false);
   if(!BufVal(hMACD, 1, 1, sigNow) || !BufVal(hMACD, 1, 2, sigPrev1) || !BufVal(hMACD, 1, 3, sigPrev2))
      return(false);
   double histNow   = macdNow   - sigNow;
   double histPrev1 = macdPrev1 - sigPrev1;
   double histPrev2 = macdPrev2 - sigPrev2;
   if(isBuy)  return(histNow > histPrev1 && histPrev1 <= histPrev2);
   return(histNow < histPrev1 && histPrev1 >= histPrev2);
  }
//+------------------------------------------------------------------+
double LotSize(const double stopDistance)
  {
   double lots = InpLots;
   if(InpLotMode == LOT_RISK_PCT && stopDistance > 0.0)
     {
      double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickVal > 0.0 && tickSize > 0.0)
        {
         double riskCash = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct / 100.0;
         double lossPerLot = (stopDistance / tickSize) * tickVal;
         if(lossPerLot > 0.0) lots = riskCash / lossPerLot;
        }
     }
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(st > 0.0) lots = MathFloor(lots / st) * st;
   lots = MathMax(mn, MathMin(MathMin(mx, InpMaxLots), lots));
   return(NormalizeDouble(lots, 2));
  }
//+------------------------------------------------------------------+
void LogClosed(const string reason, const double exitPx)
  {
   if(!InpLogTrades) return;
   if(g_fh == INVALID_HANDLE)
     {
      string fn = "Aurelius_EA_" + _Symbol + "_" + (string)InpMagic + ".csv";
      //--- FILE_COMMON is the fix for "I don't see the export": without it,
      //--- a Strategy Tester run writes into that run's own sandboxed agent
      //--- folder (<data>\Tester\<agent-id>\MQL5\Files\), not the normal
      //--- MQL5\Files folder you'd actually go looking in. FILE_COMMON puts
      //--- it in the shared Common\Files folder instead - the same real
      //--- path every time, whether this is a live chart or a tester run:
      //--- %APPDATA%\MetaQuotes\Terminal\Common\Files\<this filename>.
      bool isNew = !FileIsExist(fn, FILE_COMMON);
      g_fh = FileOpen(fn, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON, ',');
      if(g_fh == INVALID_HANDLE) return;
      //--- print the fully resolved path rather than leave it to guesswork -
      //--- AuRebound_EA.mq5 deliberately does NOT use FILE_COMMON, on the
      //--- theory that it doesn't actually escape Strategy Tester
      //--- sandboxing, so this is disputed even within this project. Settle
      //--- it in the log instead of by theory: always shows exactly where
      //--- the file landed for this specific run.
      PrintFormat("Aurelius EA: CSV export -> %s\\Files\\%s",
                  TerminalInfoString(TERMINAL_COMMONDATA_PATH), fn);
      FileSeek(g_fh, 0, SEEK_END);
      if(isNew)
         FileWrite(g_fh, "entry_time","exit_time","dir","entry_px","exit_px",
                         "lots","moved","reason","balance");
     }
   FileWrite(g_fh,
      TimeToString(g_entryTime, TIME_DATE|TIME_MINUTES),
      TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES),
      (g_entryDir > 0 ? "BUY" : "SELL"),
      DoubleToString(g_entryPrice, _Digits),
      DoubleToString(exitPx, _Digits),
      DoubleToString(g_entryLots, 2),
      DoubleToString((exitPx - g_entryPrice) * g_entryDir, _Digits), reason,
      DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2));
   FileFlush(g_fh);
  }
//+------------------------------------------------------------------+
//| Minutes until this symbol's trading session closes.               |
//| Returns -1 when the session cannot be read, which is treated as   |
//| "no restriction" rather than blocking everything.                 |
//+------------------------------------------------------------------+
//| Tick volume of the last closed bar against its recent average.    |
//| Higher volume entries won more often at every threshold tested,   |
//| which is the one filter effect that behaved monotonically.        |
//+------------------------------------------------------------------+
double VolumeRatio()
  {
   long v[];
   ArraySetAsSeries(v, true);
   int need = InpVolAvgBars + 2;
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, 1, need, v) < need) return(-1.0);
   double sum = 0.0;
   for(int i = 1; i <= InpVolAvgBars; i++) sum += (double)v[i];
   double avg = sum / InpVolAvgBars;
   if(avg <= 0.0) return(-1.0);
   return((double)v[0] / avg);
  }
//+------------------------------------------------------------------+
//| The previous N completed days' high / low. v1.44 lifted this loop  |
//| verbatim out of SRDistanceATR() below - no behaviour change, the   |
//| bounds, the shift-1 start and the "any unreadable day fails the    |
//| whole read" rule are all exactly as they were. Extracted rather    |
//| than duplicated on purpose: UpdateLevelLines() now DRAWS these two |
//| levels, and a second copy of the loop could silently drift from    |
//| the one the entry filter is actually tested against.               |
//+------------------------------------------------------------------+
bool SRLevels(double &hi, double &lo)
  {
   int n = MathMax(1, InpSRDays);
   hi = -DBL_MAX; lo = DBL_MAX;
   for(int i = 1; i <= n; i++)
     {
      double dh = iHigh(_Symbol, PERIOD_D1, i);
      double dl = iLow(_Symbol, PERIOD_D1, i);
      if(dh <= 0.0 || dl <= 0.0) return(false);
      if(dh > hi) hi = dh;
      if(dl < lo) lo = dl;
     }
   return(true);
  }
//+------------------------------------------------------------------+
//| Distance from the previous N completed days' high / low, in ATR.  |
//| Uses real D1 bars from shift 1, so today never leaks in.          |
//+------------------------------------------------------------------+
double SRDistanceATR(const bool isBuy, const double atr)
  {
   if(atr <= 0.0) return(-1.0);
   double hi, lo;
   if(!SRLevels(hi, lo)) return(-1.0);
   double c = iClose(_Symbol, PERIOD_CURRENT, 1);
   return((isBuy ? MathAbs(hi - c) : MathAbs(c - lo)) / atr);
  }
//+------------------------------------------------------------------+
int MinutesToSessionClose()
  {
   if(!InpUseSessionCheck) return(-1);
   datetime now = TimeCurrent();
   MqlDateTime t; TimeToStruct(now, t);
   ENUM_DAY_OF_WEEK dow = (ENUM_DAY_OF_WEEK)t.day_of_week;

   datetime from, to;
   int secNow = t.hour * 3600 + t.min * 60 + t.sec;
   for(int i = 0; i < 8; i++)
     {
      if(!SymbolInfoSessionTrade(_Symbol, dow, i, from, to)) break;
      int f = (int)from, o = (int)to;      // seconds from midnight
      if(secNow >= f && secNow < o)
         return((o - secNow) / 60);
     }
   return(-1);                             // outside a session, or unreadable
  }
//+------------------------------------------------------------------+
bool NearSessionClose(const int mins)
  {
   int m = MinutesToSessionClose();
   if(m < 0) return(false);
   return(m <= mins);
  }
//+------------------------------------------------------------------+
int DSTGapHourAdjustment(datetime now);   // forward declaration - defined below, after the holiday-calendar
                                           // date-arithmetic helpers it depends on; see its own header
bool FridayCutoff(const bool forEntry)
  {
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(t.day_of_week != 5) return(false);
   if(forEntry) return(t.hour >= InpNoEntryAfterHourFri + DSTGapHourAdjustment(TimeCurrent()));
   // forEntry=false branch superseded by WeekendStillOpen() below - kept
   // (not deleted) since forEntry=true above still needs this function,
   // and a no-entry-gate check missing its exact hour is harmless (worst
   // case one extra entry near the boundary), unlike the close side, which
   // is what actually rode 56+ hours when it couldn't fire at all - see
   // WeekendStillOpen's own header for why that side needed a real fix.
   return(InpCloseOnFriday && t.hour >= InpFridayCloseHour);
  }
//+------------------------------------------------------------------+
//| Deadline-based replacement for FridayCutoff(false) above, for the     |
//| same reason Zenith_EA.mq5's original day-of-week Friday/weekend check   |
//| turned out to ride 127h in real data: a bar-gated, day-of-week==5        |
//| check can't fire AT ALL if a holiday leaves zero ticks/bars near the      |
//| cutoff hour, however many days that closure ends up running. True once     |
//| 'now' is at or past the most recent Friday InpFridayCloseHour:00            |
//| threshold AND the position opened before that threshold - regardless of     |
//| which day of the week the first tick back happens to land on (Sat, Sun,      |
//| Mon, or later after an extended holiday closure all work the same way).       |
//| Called every tick, ahead of OnTick's new-bar gate - see its call site.         |
//+------------------------------------------------------------------+
bool WeekendStillOpen(datetime now, datetime openTime)
  {
   MqlDateTime t; TimeToStruct(now, t);
   int daysSinceFriday = (t.day_of_week - 5 + 7) % 7;   // Fri=0, Sat=1, Sun=2, Mon=3, Tue=4, Wed=5, Thu=6
   datetime friday = now - (datetime)daysSinceFriday * 86400;
   MqlDateTime f; TimeToStruct(friday, f);
   // DST-gap-week correction (see DSTGapHourAdjustment's own header) -
   // evaluated against `friday`'s own date, not `now`, since that's the
   // date whose true close hour this is meant to represent.
   f.hour = InpFridayCloseHour + DSTGapHourAdjustment(friday); f.min = 0; f.sec = 0;
   datetime deadline = StructToTime(f);
   if(deadline > now) deadline -= 7 * 86400;   // today IS Friday but before the close hour - last week's deadline applies
   return(now >= deadline && openTime > 0 && openTime < deadline);
  }
//+------------------------------------------------------------------+
//| True if any of this EA's own positions (symbol+magic) are currently   |
//| open - a cheap existence check, no position data needed, used to gate   |
//| the tick-level WeekendStillOpen call so it isn't evaluated (and         |
//| ClosePosition() isn't called) on every tick when flat.                    |
//+------------------------------------------------------------------+
bool HasOwnPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() == _Symbol && pos.Magic() == InpMagic) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
//| US market holiday calendar - same mechanism confirmed live in          |
//| Daybreak_EA.mq5/Zenith_EA.mq5's own real Strategy Tester data: a         |
//| position opened on a holiday can find its session closing far earlier     |
//| than usual, with no active management able to react before the market      |
//| genuinely closes. Blocks new entries on a flagged holiday the same way       |
//| FridayCutoff(true) already blocks them late in a normal week. Every date      |
//| is COMPUTED from the current year, not looked up in a hardcoded table - no     |
//| yearly maintenance, works indefinitely.                                          |
//+------------------------------------------------------------------+
void EasterSunday(const int year, int &month, int &day)
  {
   int a = year % 19;
   int b = year / 100;
   int c = year % 100;
   int d = b / 4;
   int e = b % 4;
   int f = (b + 8) / 25;
   int g = (b - f + 1) / 3;
   int h = (19*a + b - d - g + 15) % 30;
   int i = c / 4;
   int k = c % 4;
   int l = (32 + 2*e + 2*i - h - k) % 7;
   int m = (a + 11*h + 22*l) / 451;
   month = (h + l - 7*m + 114) / 31;
   day   = ((h + l - 7*m + 114) % 31) + 1;
  }
//+------------------------------------------------------------------+
//| Both NthWeekdayOfMonth and LastWeekdayOfMonth build their date at         |
//| t.hour=0 (was 12 - fixed after Opus review found this session's own       |
//| DSTGapHourAdjustment() Monday-boundary math, e.g. NthWeekdayOfMonth(...)+   |
//| 86400, landed at Monday 12:00 rather than Monday 00:00 - harmless at the     |
//| gold-trio/Zenith/Daybreak's shipped hour thresholds, which all sit above       |
//| noon, but would silently mis-adjust any hour below 12 on the 4 transition       |
//| Mondays/year if ever configured that low - e.g. exactly the kind of change        |
//| Daybreak_EA.mq5's own header invites for InpSessionHour). ObservedFixedHoliday's   |
//| own t.hour=12 is untouched - IsMarketHoliday only ever compares y/m/d from it,       |
//| so it was never actually affected by this.                                            |
//+------------------------------------------------------------------+
datetime NthWeekdayOfMonth(const int year, const int month, const int weekday, const int n)
  {
   MqlDateTime t; ZeroMemory(t);
   t.year = year; t.mon = month; t.day = 1; t.hour = 0;
   datetime first = StructToTime(t);
   MqlDateTime f; TimeToStruct(first, f);
   int offset = (weekday - f.day_of_week + 7) % 7;
   t.day = 1 + offset + (n - 1) * 7;
   return(StructToTime(t));
  }
//+------------------------------------------------------------------+
datetime LastWeekdayOfMonth(const int year, const int month, const int weekday)
  {
   MqlDateTime t; ZeroMemory(t);
   int nm = month + 1, ny = year;
   if(nm > 12) { nm = 1; ny++; }
   t.year = ny; t.mon = nm; t.day = 1; t.hour = 0;
   datetime lastDay = StructToTime(t) - 86400;   // last day of `month`
   MqlDateTime l; TimeToStruct(lastDay, l);
   int back = (l.day_of_week - weekday + 7) % 7;
   return(lastDay - (datetime)back * 86400);
  }
//+------------------------------------------------------------------+
datetime ObservedFixedHoliday(const int year, const int month, const int day)
  {
   MqlDateTime t; ZeroMemory(t);
   t.year = year; t.mon = month; t.day = day; t.hour = 12;
   datetime d = StructToTime(t);
   MqlDateTime m; TimeToStruct(d, m);
   if(m.day_of_week == 6) return(d - 86400);   // Saturday -> observed Friday
   if(m.day_of_week == 0) return(d + 86400);   // Sunday -> observed Monday
   return(d);
  }
//+------------------------------------------------------------------+
bool IsMarketHoliday(datetime now)
  {
   MqlDateTime m; TimeToStruct(now, m);
   int year = m.year;
   datetime dates[10];
   int n = 0;
   dates[n++] = ObservedFixedHoliday(year, 1, 1);        // New Year's Day
   dates[n++] = NthWeekdayOfMonth(year, 1, 1, 3);         // MLK Day: 3rd Monday of January
   dates[n++] = NthWeekdayOfMonth(year, 2, 1, 3);         // Presidents Day: 3rd Monday of February
   int em, ed; EasterSunday(year, em, ed);
   MqlDateTime e; ZeroMemory(e); e.year = year; e.mon = em; e.day = ed; e.hour = 12;
   dates[n++] = StructToTime(e) - 2 * 86400;              // Good Friday
   dates[n++] = LastWeekdayOfMonth(year, 5, 1);           // Memorial Day: last Monday of May
   dates[n++] = ObservedFixedHoliday(year, 6, 19);        // Juneteenth
   dates[n++] = ObservedFixedHoliday(year, 7, 4);         // Independence Day
   dates[n++] = NthWeekdayOfMonth(year, 9, 1, 1);         // Labor Day: 1st Monday of September
   dates[n++] = NthWeekdayOfMonth(year, 11, 4, 4);        // Thanksgiving: 4th Thursday of November
   dates[n++] = ObservedFixedHoliday(year, 12, 25);       // Christmas Day

   for(int i = 0; i < n; i++)
     {
      MqlDateTime h; TimeToStruct(dates[i], h);
      if(h.year == m.year && h.mon == m.mon && h.day == m.day) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
//| Real GOLD# M5 price data (2023-2026, XM Global) shows this broker's  |
//| server clock follows EU DST dates while gold's true session timing     |
//| follows US DST dates - confirmed directly from the daily first-bar-      |
//| of-day time, which shifts by exactly 60 minutes on the Monday after       |
//| each transition, twice a year, with no exceptions across 4 years:          |
//|   Spring: -60min the Monday after the 2nd Sunday of March (US DST         |
//|   start), +60min back to normal the Monday after the last Sunday of        |
//|   March (EU/broker DST start) - a ~2-week gap.                              |
//|   Autumn: -60min the Monday after the last Sunday of October (EU/broker      |
//|   DST end), +60min back to normal the Monday after the 1st Sunday of          |
//|   November (US DST end) - a ~1-week gap.                                       |
//| During either gap, true session events read 1 SERVER-CLOCK HOUR EARLIER          |
//| than their normal mapping - so a fixed-hour threshold needs to be                  |
//| evaluated 1 hour earlier to actually catch the same real event. Returns             |
//| -1 during a gap week, 0 otherwise - ADD this to a configured hour before             |
//| comparing against the clock. Both the US and EU/UK transition rules are               |
//| permanent, legally fixed rules (not looked up in a table), so - like                   |
//| IsMarketHoliday - this needs no yearly maintenance.                                      |
//+------------------------------------------------------------------+
int DSTGapHourAdjustment(datetime now)
  {
   MqlDateTime t; TimeToStruct(now, t);
   int year = t.year;

   datetime usSpringStart = NthWeekdayOfMonth(year, 3, 0, 2) + 86400;   // Mon after 2nd Sun March (US DST start)
   datetime euSpringStart = LastWeekdayOfMonth(year, 3, 0) + 86400;      // Mon after last Sun March (EU DST start)
   if(now >= usSpringStart && now < euSpringStart) return(-1);

   datetime euAutumnEnd = LastWeekdayOfMonth(year, 10, 0) + 86400;      // Mon after last Sun October (EU DST end)
   datetime usAutumnEnd = NthWeekdayOfMonth(year, 11, 0, 1) + 86400;    // Mon after 1st Sun November (US DST end)
   if(now >= euAutumnEnd && now < usAutumnEnd) return(-1);

   return(0);
  }
//+------------------------------------------------------------------+
//--- always keeps g_dayStartEquity fresh, independent of InpMaxDailyLossPct -
//--- the panel's "today" P&L needs this even when the daily-loss cutoff is off
//--- (its default), which is why "today" used to always read 0.00.
void UpdateDayStamp()
  {
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(t.day != g_dayStamp)
     {
      g_dayStamp = t.day;
      g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_myRealizedToday = 0.0;
     }
  }
bool DailyLossHit()
  {
   UpdateDayStamp();
   if(InpMaxDailyLossPct <= 0.0) return(false);
   if(g_dayStartEquity <= 0.0) return(false);
   double dd = 100.0 * (g_dayStartEquity - AccountInfoDouble(ACCOUNT_EQUITY))
               / g_dayStartEquity;
   return(dd >= InpMaxDailyLossPct);
  }
//--- this EA's own realized P&L today (deals with this magic/symbol closed
//--- since the day started) - deliberately excludes any other EA or manual
//--- trade sharing the account, unlike raw ACCOUNT_EQUITY.
//--- PERFORMANCE FIX (v1.31): this used to call HistorySelect() and
//--- re-scan every deal in the day's history on every call - and it was
//--- being called from the panel refresh path, which runs on every
//--- unique TimeCurrent() second, not just once per bar. On a real-tick
//--- backtest that's potentially hundreds of thousands of full-history
//--- rescans over a multi-year run (the same class of bug as the
//--- SessionVWAP() fix in v1.29, just in the account panel this time).
//--- g_myRealizedToday is now an O(1) running total, updated
//--- incrementally in OnTradeTransaction() as each real close happens
//--- (a rare event, not a per-tick one) and reset daily in
//--- UpdateDayStamp() - this function is now just a lookup.
double MyRealizedPLToday()
  {
   return(g_myRealizedToday);
  }
//--- this EA's own floating P&L right now (open positions with this magic
//--- only) - same "mine, not the whole account" filtering as MyRealizedPLToday.
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
//+------------------------------------------------------------------+
//| Breakeven + moderate trail (optional - InpUseBreakeven/InpUseTrailAfterBE).
//| Moves the stop only - never closes the trade. The whole point is not
//| guessing whether a pullback is a real reversal: stay in, just stop
//| letting a big float give all the way back to a loss. Never loosens
//| an already-more-protective stop (curSL==0.0 counts as "no protection
//| yet", so this can attach a stop even with InpUseStopLoss=false once
//| the trigger is reached). Scale-in (InpUseScale) can open more than
//| one leg under the same magic - every leg gets moved to the FIRST
//| leg's breakeven/trail price (not its own - a deliberate simplification,
//| never a loosening since adds start with SL=0.0). Note: with the
//| shipped defaults InpAdd1ATR(3.0) > InpBreakevenATR(2.0), breakeven
//| locks before the first add opens, so with InpUseTrailAfterBE off an
//| add-on leg never gets touched again after that one bar - it stays at
//| SL=0.0 (unprotected) for the rest of the trade if scale-in is enabled.
//+------------------------------------------------------------------+
void ManageBreakeven(const bool haveLong)
  {
   if(!InpUseBreakeven || g_entryATR <= 0.0) return;
   double px = iClose(_Symbol, PERIOD_CURRENT, 1);
   double prof = (px - g_entryPrice) * (haveLong ? 1 : -1);
   ENUM_POSITION_TYPE wantType = haveLong ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;

   if(!g_beDone)
     {
      if(prof < InpBreakevenATR * g_entryATR) return;
      double lock = InpBreakevenLockATR * g_entryATR;
      double newSL = NormalizeDouble(haveLong ? g_entryPrice + lock : g_entryPrice - lock, _Digits);
      // only mark done once at least one leg is actually protected at/beyond
      // newSL - a modify that fails (requote, off-quotes, invalid stops) must
      // not permanently disable the feature for the rest of this trade; it
      // retries on the next bar instead.
      bool anyProtected = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         if(!pos.SelectByIndex(i)) continue;
         if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic || pos.PositionType() != wantType) continue;
         double curSL = pos.StopLoss();
         if(curSL != 0.0 && ((haveLong && curSL >= newSL) || (!haveLong && curSL <= newSL)))
            { anyProtected = true; continue; }   // already at least as protective - leave it alone
         if(trade.PositionModify(pos.Ticket(), newSL, pos.TakeProfit()))
            anyProtected = true;
         else
            Print("Breakeven modify failed: ", trade.ResultRetcodeDescription());
        }
      if(!anyProtected) return;
      g_beDone = true;
      g_peakFavPx = px;
      if(InpVerbose) Print("Breakeven locked @ ", DoubleToString(newSL, _Digits));
      return;
     }

   if(!InpUseTrailAfterBE) return;
   if((haveLong && px > g_peakFavPx) || (!haveLong && px < g_peakFavPx))
      g_peakFavPx = px;
   double give = InpTrailGiveBackATR * g_entryATR;
   // normalize BEFORE comparing against the broker's already-normalized
   // curSL - comparing raw doubles here meant rounding could go the wrong
   // way on about half of bars, making curSL "less than" trailSL forever
   // and re-sending an unchanged stop every bar (a no-op modify + a failed-
   // looking log line, repeated for the life of the trade).
   double trailSL = NormalizeDouble(haveLong ? g_peakFavPx - give : g_peakFavPx + give, _Digits);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic || pos.PositionType() != wantType) continue;
      double curSL = pos.StopLoss();
      if(curSL != 0.0 && ((haveLong && curSL >= trailSL) || (!haveLong && curSL <= trailSL)))
         continue;
      if(!trade.PositionModify(pos.Ticket(), trailSL, pos.TakeProfit()))
         Print("Trail modify failed: ", trade.ResultRetcodeDescription());
     }
  }
//+------------------------------------------------------------------+
void ClosePosition(const string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      double px = pos.PriceCurrent();
      if(trade.PositionClose(pos.Ticket()))
        {
         if(InpVerbose) Print("Closed: ", reason);
         LogClosed(reason, px);
         g_lastClose = TimeCurrent();
         g_barsSinceClose = 0;
         g_ticket = 0;
        }
      else
         Print("Close failed: ", trade.ResultRetcodeDescription());
     }
  }
//+------------------------------------------------------------------+
//--- default argument lives on the forward declaration only (line 603) -
//--- repeating it here too is a hard error in some MQL5/C++-family
//--- compilers, and this pair is the only default-arg forward declaration
//--- anywhere in this repo, so there's no local precedent to lean on.
void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim)
  {
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }

   //--- see g_panelReclaim's own comment: true only reclaims top-of-stack
   //--- (delete+recreate) once per new bar, right after a new MA line
   //--- segment could have buried the panel - everything in between just
   //--- updates the existing objects' text/values in place, so live P&L
   //--- ticking doesn't visibly flash the whole panel.
   g_panelReclaim = reclaim;

   PBackground();
   PWatermark();

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;   // re-measured fresh this cycle, used by the NEXT one
   int rh = InpPanelSize + 11;
   int hdr = rh + 14;
   //--- Height is computed, not guessed. MT5 renders chart objects in
   //--- CREATION order (ZORDER only affects click priority), so the frame
   //--- must be created BEFORE the text or it paints over everything.
   //--- Re-derived directly against the literal ty+= sequence below (found
   //--- a real, pre-existing off-by-one: this was 37, the actual count is
   //--- 38 - a0(1) + BIAS(1 section+4 rows) + ENTRY CRITERIA(1+9) +
   //--- STRATEGY(1+9) + POSITION(1+5, worst case) + ACCOUNT(1+5) = 38,
   //--- plus +1 for the new breakeven row (d10) = 39. GAPS=10 was already
   //--- correct (a0, s1, b4, s2, c9, s5, d9, s3, p5, s4). 39 is the
   //--- worst-case POSITION-section row count (p1-p5, 5 rows, in position);
   //--- flat only needs 3 rows + a bare ty+=6, i.e. 37 - sized for the
   //--- worst case unconditionally would leave ~2 rows of dead space at
   //--- the bottom while flat, so size to whichever branch is actually
   //--- drawn this cycle instead.
   //--- 2026-09-16: ENTRY CRITERIA gained a 10th row (c10, "slope+SR
   //--- block") - same GAPS (sits before the section's existing single
   //--- gap-point, not a new transition of its own).
   const int ROWS = (haveLong || haveShort) ? 40 : 38, GAPS = 10;
   //--- autofit: shrink the row height until the panel fits the window,
   //--- so it is never cut off on a small screen
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH  = hdr + 10 + ROWS*rh + GAPS*6 + 12;
   int guard  = 0;
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     {
      rh--; guard++;
      hdr   = rh + 14;
      bodyH = hdr + 10 + ROWS*rh + GAPS*6 + 12;
     }
   if(g_panX < 0)                       // first draw: take the inputs
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

   //--- frame first, so everything else draws on top of it
   PRect("sh", x + 4, y + 4, w, bodyH, InpShadowCol, InpShadowCol, 0);
   PRect("bg", x, y, w, bodyH, InpPanelBg, InpPanelBg, 0);
   //--- "bg" is the one rect that keeps its object identity across cycles
   //--- (so dragging works), which means it can't reclaim top-of-stack the
   //--- way everything else here does - an MA line segment drawn on a later
   //--- bar would otherwise end up stacked above it and show through. This
   //--- opaque fill sits exactly on top of "bg" and IS recreated every
   //--- cycle like everything else, so it's what actually keeps the panel
   //--- body solid.
   PRect("fl", x + 2, y + 2, w - 4, bodyH - 4, InpPanelBg, InpPanelBg, 0);
   //--- explicit 4-strip frame, not PRect's own unreliable built-in border -
   //--- see PFrame's own comment for why (same fix as Fulcrum_EA.mq5/
   //--- Ratchet_EA.mq5).
   PFrame("bd", x, y, w, bodyH, InpPanelEdge, 2);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);

   int ty = y + 9;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "AURELIUS", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   bool algo = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) &&
               MQLInfoInteger(MQL_TRADE_ALLOWED);
   PRow("a0", x, ty, w, "algo trading", algo ? "ON" : "OFF", algo ? 1 : 0);
   ty += rh + 6;

   //--- bias -------------------------------------------------------
   double m21,m50,m150,m600,m2400,atr;
   bool ok = MAs(1, m21, m50, m150, m600, m2400, atr);
   double c = iClose(_Symbol, PERIOD_CURRENT, 1);
   PSection("s1", x, ty, w, rh, "BIAS"); ty += rh + 6;
   // labels changed from Aurelius_EA.mq5's "M5 50"/"M15 150"/"H1 600"/"H4 2400"
   // (which described what each period approximates when computed on M5 bars -
   // meaningless here, since this file runs those same periods natively on M15
   // already) to plain tier names + this file's own default period numbers.
   // Same pre-existing limitation as the original: these numbers are the
   // DEFAULTS, not read from the live InpP* inputs, so they go stale if you
   // override a period in the Tester/Inputs tab - cosmetic only, matches
   // Aurelius_EA.mq5's own established behaviour.
   PRow("b1", x, ty, w, "med    50",   !ok ? "-" : (c > m50   ? "UP":"DOWN"), ok ? (c > m50   ?1:0) : -1); ty += rh;
   PRow("b2", x, ty, w, "mid   150",  !ok ? "-" : (c > m150  ? "UP":"DOWN"), ok ? (c > m150  ?1:0) : -1); ty += rh;
   PRow("b3", x, ty, w, "slow  200",  !ok ? "-" : (c > m600  ? "UP":"DOWN"), ok ? (c > m600  ?1:0) : -1); ty += rh;
   PRow("b4", x, ty, w, "macro 1200", !ok ? "-" : (c > m2400 ? "UP":"DOWN"), ok ? (c > m2400 ?1:0) : -1); ty += rh + 6;

   //--- criteria ---------------------------------------------------
   bool aUp = Aligned(1, true), aDn = Aligned(1, false);
   int dir = aUp ? 1 : (aDn ? -1 : 0);
   double sl = (dir != 0) ? SlopeATR(dir > 0) : 0.0;
   int cx = CrissCross();
   bool pb = (dir != 0) && PullbackOK(dir > 0);
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   int mtc = MinutesToSessionClose();
   PSection("s2", x, ty, w, rh, "ENTRY CRITERIA"); ty += rh + 6;
   PRow("c1", x, ty, w, "aligned",
        dir == 1 ? "BUY" : dir == -1 ? "SELL" : "no", dir != 0 ? 1 : 0); ty += rh;
   PRow("c2", x, ty, w, "slope", DoubleToString(sl, 2),
        !InpUseSlope ? -1 : ((sl >= InpMinSlopeATR && (InpMaxSlopeATR <= 0.0 || sl <= InpMaxSlopeATR)) ? 1 : 0)); ty += rh;
   PRow("c3", x, ty, w, "criss-cross", (string)cx,
        !InpUseCrossFilter ? -1 : (cx <= InpMaxCrosses ? 1 : 0)); ty += rh;
   PRow("c4", x, ty, w, "pullback", pb ? "yes" : "no", pb ? 1 : 0); ty += rh;
   PRow("c5", x, ty, w, "spread", (string)spr,
        (InpMaxSpreadPoints > 0 && spr > InpMaxSpreadPoints) ? 0 : 1); ty += rh;
   PRow("c6", x, ty, w, "session closes",
        mtc < 0 ? "n/a" : (string)mtc + " min",
        (mtc >= 0 && mtc <= InpNoEntryMinsBefore) ? 0 : 1); ty += rh;
   PRow("c7", x, ty, w, "ATR(14)", ok ? DoubleToString(atr, 2) : "-", -1); ty += rh;
   double vr = InpUseVolume ? VolumeRatio() : -1.0;
   PRow("c8", x, ty, w, "volume",
        vr < 0.0 ? "off" : DoubleToString(vr, 2),
        !InpUseVolume ? -1 : (vr >= InpMinVolRatio ? 1 : 0)); ty += rh;
   double sd = (InpUseSRDist && ok && dir != 0) ? SRDistanceATR(dir > 0, atr) : -1.0;
   PRow("c9", x, ty, w, "to S/R level",
        sd < 0.0 ? "off" : DoubleToString(sd, 2) + " ATR",
        !InpUseSRDist ? -1 : (sd >= InpMinSRDistATR ? 1 : 0)); ty += rh;
   bool srBlockHit = InpUseSlopeSRBlock && dir != 0 && ok
                     && sl >= InpSlopeSRBlockSlope
                     && SRDistanceATR(dir > 0, atr) >= InpSlopeSRBlockSR;
   PRow("c10", x, ty, w, "slope+SR block",
        !InpUseSlopeSRBlock ? "off" : (srBlockHit ? "BLOCKED" : "clear"),
        !InpUseSlopeSRBlock ? -1 : (srBlockHit ? 0 : 1)); ty += rh + 6;

   //--- strategy --------------------------------------------------
   string alName = (InpAlignMode == ALIGN_FULL) ? "FULL" :
                   (InpAlignMode == ALIGN_MID)  ? "MID"  :
                   (InpAlignMode == ALIGN_FAST) ? "FAST" : "PRICE";
   string pbName = (InpPullbackMA == PB_21) ? "21" :
                   (InpPullbackMA == PB_50) ? "50" : "150";
   PSection("s5", x, ty, w, rh, "STRATEGY"); ty += rh + 6;
   PRow("d1", x, ty, w, "alignment", alName, -1); ty += rh;
   PRow("d2", x, ty, w, "pullback to", pbName, -1); ty += rh;
   PRow("d3", x, ty, w, "exit", "align break", -1); ty += rh;
   PRow("d6", x, ty, w, "scale in",
        InpUseScale ? (StringFormat("%.0f/%.0f ATR", InpAdd1ATR, InpAdd2ATR)) : "off",
        InpUseScale ? 1 : -1); ty += rh;
   PRow("d5", x, ty, w, "bank at",
        InpUseBank ? DoubleToString(InpBankATR,1) + " ATR" : "off",
        InpUseBank ? 1 : -1); ty += rh;
   PRow("d7", x, ty, w, "momentum shift",
        InpUseMomentum ? "on" : "off",
        InpUseMomentum ? 1 : -1); ty += rh;
   PRow("d4", x, ty, w, "stop loss",
        InpUseStopLoss ? DoubleToString(InpStopATR,1) + " ATR" : "none",
        InpUseStopLoss ? 1 : -1); ty += rh;
   PRow("d8", x, ty, w, "price-21 exit",
        InpUsePrice21Exit ? DoubleToString(InpPrice21BufferATR,1) + " ATR / " + (string)InpPrice21ConfirmBars + " bars" : "off",
        InpUsePrice21Exit ? 1 : -1); ty += rh;
   PRow("d10", x, ty, w, "breakeven",
        InpUseBreakeven ? DoubleToString(InpBreakevenATR,1) + " ATR" + (InpUseTrailAfterBE ? " +trail" : "") : "off",
        InpUseBreakeven ? 1 : -1); ty += rh;
   PRow("d9", x, ty, w, "vwap exit",
        InpUseVwapExit ? DoubleToString(InpVwapBufferATR,1) + " ATR / " + (string)InpVwapConfirmBars + " bars" : "off",
        InpUseVwapExit ? 1 : -1); ty += rh + 6;

   //--- position ---------------------------------------------------
   PSection("s3", x, ty, w, rh, "POSITION"); ty += rh + 6;
   if(haveLong || haveShort)
     {
      double prof = 0.0, vol = 0.0, opx = 0.0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         if(!pos.SelectByIndex(i)) continue;
         if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
         prof += pos.Profit() + pos.Swap();
         vol = pos.Volume(); opx = pos.PriceOpen();
        }
      PRow("p1", x, ty, w, haveLong ? "LONG" : "SHORT",
           DoubleToString(opx, _Digits), 1); ty += rh;
      PRow("p2", x, ty, w, "volume", DoubleToString(vol, 2), -1); ty += rh;
      PRow("p3", x, ty, w, "floating P/L", StringFormat("%+.2f", prof),
           prof >= 0 ? 1 : 0); ty += rh;
      PRow("p4", x, ty, w, "bars held", (string)g_entryBarCount, -1); ty += rh;
      PRow("p5", x, ty, w, "adds done", (string)g_addsDone,
           g_addsDone > 0 ? 1 : -1); ty += rh + 6;
     }
   else
     {
      PRow("p1", x, ty, w, "state", "FLAT", -1); ty += rh;
      PRow("p2", x, ty, w, "cooldown",
           (string)MathMax(0, InpCooldownBars - g_barsSinceClose) + " bars", -1); ty += rh;
      PRow("p3", x, ty, w, "lot size", DoubleToString(InpLots, 2), -1); ty += rh;
      PRow("p4", x, ty, w, "", "", -1); ty += 6;
      //--- p5 ("adds done") only ever gets a value in the in-position
      //--- branch above - without this, closing a position left AURP_p5*
      //--- on the chart at a stale y-coordinate (the flat layout is 2 rows
      //--- shorter), landing on top of the ACCOUNT section below. Opus
      //--- review found this while verifying the panel-flash fix.
      PRow("p5", x, ty, w, "", "", -1);
     }

   //--- account ----------------------------------------------------
   //--- "today" is split mine/other because ACCOUNT_EQUITY reflects the
   //--- WHOLE account - if any other EA or a manual trade shares this
   //--- account, its P&L was previously mixed into this EA's own number
   //--- with no way to tell them apart.
   PSection("s4", x, ty, w, rh, "ACCOUNT"); ty += rh + 6;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double dayPL    = (g_dayStartEquity > 0.0) ? eq - g_dayStartEquity : 0.0;
   double myDayPL  = MyRealizedPLToday() + MyFloatingPL();
   double otherPL  = dayPL - myDayPL;
   PRow("q1", x, ty, w, "balance", DoubleToString(bal, 2), -1); ty += rh;
   PRow("q2", x, ty, w, "equity", DoubleToString(eq, 2), eq >= bal ? 1 : 0); ty += rh;
   PRow("q3", x, ty, w, "today (mine)", StringFormat("%+.2f", myDayPL),
        myDayPL >= 0 ? 1 : 0); ty += rh;
   PRow("q5", x, ty, w, "today (other)", StringFormat("%+.2f", otherPL),
        otherPL == 0.0 ? -1 : (otherPL >= 0 ? 1 : 0)); ty += rh;
   PRow("q4", x, ty, w, "magic", (string)InpMagic, -1);
   ty += rh;

   //--- if the row count ever drifts from ROWS, this says so in the log
   //--- instead of silently clipping the panel
   static int warned = 0;
   int used = ty + 12 - y;
   if(used > bodyH && warned < 3)
     { warned++; PrintFormat("Panel: content %d px vs frame %d px", used, bodyH); }
  }

//+------------------------------------------------------------------+
void CurrentPositions(bool &haveLong, bool &haveShort)
  {
   haveLong = false; haveShort = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      if(pos.PositionType() == POSITION_TYPE_BUY) haveLong = true;
      else                                        haveShort = true;
     }
  }
//+------------------------------------------------------------------+
//| Timer: keeps the panel alive when no ticks are arriving, e.g. at   |
//| the weekend or on a closed session.                                |
//+------------------------------------------------------------------+
void OnTimer()
  {
   //--- defense-in-depth backstop for the v1.33 fix at EventSetTimer(1) -
   //--- shouldn't even fire in this mode since the timer isn't started,
   //--- but bail immediately if it somehow does.
   if(g_skipCosmeticDraws) return;
   PBackground();                 // retries until the image loads
   if(!InpShowPanel) return;
   bool hl, hs;
   CurrentPositions(hl, hs);
   //--- reclaim=false: this just ticks the live numbers (P&L etc) - it
   //--- updates every existing object's properties in place rather than
   //--- deleting and recreating them, so it doesn't visibly flash. Actual
   //--- top-of-stack reclaiming only happens once per new bar, in OnTick,
   //--- right after UpdateMALines() - see g_panelReclaim's comment.
   DrawPanel(hl, hs, false);
   //--- calling ChartRedraw() unconditionally every second forces MT5 to
   //--- redraw the whole chart on a fixed clock, which fights the user's
   //--- own scrolling/panning and previously caused visible flicker on its
   //--- own even with no object churn. Only force it when a position is
   //--- open, where the floating P/L genuinely needs to look live;
   //--- otherwise let the terminal's normal tick-driven redraw handle it.
   if(hl || hs) ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Dragging the background moves the whole panel: MT5 reports the    |
//| new position of the grabbed object, and every other element is    |
//| redrawn relative to it.                                           |
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
      DrawPanel(hl, hs, false);   // reposition only - reclaiming mid-drag would be jarring
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
         //--- this block only ran on a genuine resize before, but the
         //--- panel re-anchor below was unguarded and fired on EVERY
         //--- CHARTEVENT_CHART_CHANGE - which MT5 also raises for plain
         //--- scrolling and panning, not just resizing. That forced a
         //--- full panel redraw on every scroll tick, which is what
         //--- caused the flashing when moving the chart. Moved inside
         //--- the same width/height-changed guard so it only fires on
         //--- an actual resize, matching its intent.
         if(InpPanelBottom)
           {
            g_panX = -1;
            bool hl2, hs2;
            CurrentPositions(hl2, hs2);
            DrawPanel(hl2, hs2, false);   // re-anchor only, not a structural reclaim
           }
        }
     }
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- keep the day boundary fresh every tick, regardless of position
   //--- state or InpMaxDailyLossPct - the panel's "today" P&L needs this
   UpdateDayStamp();

   //--- tick-level weekend-flatten backstop, evaluated BEFORE the new-bar
   //--- gate below - a holiday can leave zero ticks/bars near the normal
   //--- Friday cutoff hour, so the bar-gated FridayCutoff(false) check
   //--- further down never gets a chance to fire; this can act on the
   //--- very first tick available, whenever that turns out to be. Same
   //--- fix as Daybreak_EA.mq5 v1.11/Zenith_EA.mq5 for the identical
   //--- holiday-session-gap bug class - see WeekendStillOpen's own header.
   if(InpCloseOnFriday && HasOwnPosition() && WeekendStillOpen(TimeCurrent(), g_entryTime))
      ClosePosition("FRIDAY");

   //--- act once per completed bar, matching the backtest
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(bt == g_lastBar)
     {
      //--- PERFORMANCE FIX (v1.32): keep the live numbers moving between
      //--- bars - but ONLY when a human could actually be watching. This
      //--- panel is 39 rows x 3 objects each (PRow -> PText x3), roughly a
      //--- thousand MT5 object API calls per redraw. Throttled to once per
      //--- unique TimeCurrent() second, that's still up to millions of
      //--- redraws across a multi-year real-tick backtest with no chart
      //--- open to see them - this was the remaining cause of the reported
      //--- multi-hour runtime even after v1.31's HistorySelect fix (that
      //--- fix removed the most expensive CALL from this path, but not the
      //--- path's own frequency). Skipped entirely in a non-visual Tester
      //--- run, where nobody can see the panel anyway and it has zero
      //--- effect on any trading decision - still fully live for real
      //--- trading, demo, and visual-mode backtests.
      if(g_skipCosmeticDraws) return;
      static datetime lastPanel = 0;
      if(InpShowPanel && TimeCurrent() != lastPanel)
        {
         lastPanel = TimeCurrent();
         bool hl = false, hs = false;
         for(int i = PositionsTotal() - 1; i >= 0; i--)
           {
            if(!pos.SelectByIndex(i)) continue;
            if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
            if(pos.PositionType() == POSITION_TYPE_BUY) hl = true; else hs = true;
           }
         //--- reclaim=false: live numbers only, updated in place - see
         //--- g_panelReclaim's comment for why this is what stops the
         //--- panel from visibly flashing on every one-second refresh.
         DrawPanel(hl, hs, false);
         //--- same reasoning as OnTimer's own guard just above: forcing a
         //--- full chart redraw on a fixed clock fights the user's own
         //--- scrolling/panning and can itself look like flicker even with
         //--- no object churn behind it (Opus review caught this call was
         //--- unconditional while OnTimer's twin was already guarded -
         //--- only force it when a position is actually open and the
         //--- floating P/L needs to look live).
         if(hl || hs) ChartRedraw(0);
        }
      return;
     }
   g_lastBar = bt;

   if(Bars(_Symbol, PERIOD_CURRENT) < InpP2400 + NEED_BARS)
     {
      Print("Waiting for history: ", Bars(_Symbol, PERIOD_CURRENT),
            " bars, need ", InpP2400 + NEED_BARS);
      return;
     }
   UpdateATRManual();   // once per new bar - see its own header note
   if(g_barsSinceClose < 100000) g_barsSinceClose++;
   if(PositionsTotal() > 0) g_entryBarCount++;   // once per bar, not per leg

   bool haveLong = false, haveShort = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      if(pos.PositionType() == POSITION_TYPE_BUY) haveLong = true;
      else                                        haveShort = true;
     }

   //--- cross-EA signal (see InpPublishPosition's header) - broadcasts
   //--- this EA's real position direction once per new bar via a
   //--- terminal global variable, for Vanguard_M15_EA.mq5's OWN,
   //--- separate, optional conflict filter to read. Purely a
   //--- broadcast - has no effect on this EA's own trading whatsoever.
   if(InpPublishPosition)
      GlobalVariableSet(g_posDirGVarName, haveLong ? 1.0 : (haveShort ? -1.0 : 0.0));

   //--- same v1.32 reasoning as the between-bar draw above: purely
   //--- cosmetic, skipped in a non-visual Tester run. MA lines drawn
   //--- BEFORE the panel, and DrawPanel's default reclaim=true means this
   //--- (and only this) call deletes-and-recreates every panel object so
   //--- they stay the newest (topmost) ones - the one point per bar where
   //--- that's actually needed, since it's the only point a new MA line
   //--- segment was just drawn. See g_panelReclaim's comment.
   if(!g_skipCosmeticDraws)
     {
      UpdateMALines();
      UpdateLevelLines();   // v1.44: entry/stop/S-R horizontal levels - same
                             // reasoning as UpdateMALines, and for the same
                             // reason it has to come BEFORE DrawPanel()
      DrawPanel(haveLong, haveShort);
      ChartRedraw(0);
     }

   //--- weekend flatten now handled tick-level at the top of OnTick (see
   //--- WeekendStillOpen) - FridayCutoff(false) here would just be dead
   //--- weight by the time a new bar completes, since the tick-level check
   //--- already caught it. Daily-break flatten is unchanged (bar-gated is
   //--- fine there - a missed daily-break gap is minutes, not days).
   if(haveLong || haveShort)
     {
      if(InpCloseBeforeBreak && NearSessionClose(InpCloseMinsBefore))
        { ClosePosition("SESSION_CLOSE"); return; }
     }

   //--- exit: price closed back through the 21 and stayed there - fires
   //--- well before the slower alignment-break check below would
   if(haveLong || haveShort)
     {
      if(InpUsePrice21Exit && Price21Exit(haveLong)) { ClosePosition("PRICE21"); return; }
      if(InpUseVwapExit && VwapExit(haveLong)) { ClosePosition("VWAP"); return; }
     }

   //--- exit: the alignment that justified the trade has broken
   if(haveLong || haveShort)
     {
      bool stillAligned = Aligned(1, haveLong);
      if(!stillAligned) { ClosePosition("ALIGN_BREAK"); return; }

      ManageBreakeven(haveLong);

      //--- scale in: add another unit once the trade has proven itself.
      //--- Losing trades never reach the trigger, so they are unaffected.
      if(InpUseScale && g_entryATR > 0.0 && g_addsDone < InpMaxAdds)
        {
         double pxNow = iClose(_Symbol, PERIOD_CURRENT, 1);
         double prof  = (pxNow - g_entryPrice) * (haveLong ? 1 : -1);
         double lvl   = (g_addsDone == 0) ? InpAdd1ATR
                      : (g_addsDone == 1) ? InpAdd2ATR : InpAdd3ATR;
         if(lvl > 0.0 && prof >= lvl * g_entryATR)
           {
            double addLots = (InpAddLots > 0.0) ? InpAddLots : g_entryLots;
            double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
            double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
            if(st > 0.0) addLots = MathFloor(addLots / st) * st;
            addLots = MathMax(mn, addLots);
            bool okAdd = haveLong
               ? trade.Buy(addLots, _Symbol, 0.0, 0.0, 0.0, InpComment + "-add")
               : trade.Sell(addLots, _Symbol, 0.0, 0.0, 0.0, InpComment + "-add");
            if(okAdd)
              {
               g_addsDone++;
               PrintFormat("Scaled in: add %d, %.2f lots at %.2f profit %.2f",
                           g_addsDone, addLots, trade.ResultPrice(), prof);
              }
            else
               Print("Add failed: ", trade.ResultRetcodeDescription());
           }
        }

      //--- bank a big open profit, optionally only once the 21 has rolled
      //--- over. CORRECTED: re-tested this session and the opposite of
      //--- what this comment used to claim is true - price-only banking
      //--- beats waiting for the 21-turn confirmation at every trigger
      //--- level tried (e.g. at 4.0 ATR: net +847 price-only vs +22
      //--- waiting for the turn - the wait just gives back more profit
      //--- before it fires). Moot either way: EVERY banking variant
      //--- tested lost to not banking at all (best case +1252 vs +1846
      //--- baseline) - a handful of huge winners carry this system's
      //--- edge, and any early lock-in clips them enough to cost more
      //--- than it saves. InpUseBank stays off for that reason, not
      //--- because the confirmation stage helps - it doesn't.
      if(InpUseBank && g_entryATR > 0.0)
        {
         double px   = iClose(_Symbol, PERIOD_CURRENT, 1);
         double prof = (px - g_entryPrice) * (haveLong ? 1 : -1);
         if(prof >= InpBankATR * g_entryATR)
           {
            bool turned = true;
            if(InpBankNeed21)
              {
               double a1, a2;
               if(MA(h21, 1, a1) && MA(h21, 2, a2))
                  turned = haveLong ? (a1 < a2) : (a1 > a2);
               else
                  turned = false;
              }
            if(turned) { ClosePosition("BANK"); return; }
           }
        }
      if(InpUseMaxBars && g_entryBarCount >= InpMaxBars)
        { ClosePosition("MAXBARS"); return; }
      if(InpUseStaleExit && g_entryATR > 0.0 && g_entryBarCount >= InpStaleBars)
        {
         double px2  = iClose(_Symbol, PERIOD_CURRENT, 1);
         double prof2 = (px2 - g_entryPrice) * (haveLong ? 1 : -1);
         if(prof2 < -InpStaleMinLossATR * g_entryATR)
           { ClosePosition("STALE"); return; }
        }
      return;                       // one position at a time
     }

   //--- entry gates
   if(DailyLossHit()) return;
   if(g_barsSinceClose < InpCooldownBars) return;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return;
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) return;

   //--- no new entries into a session close or into the weekend
   if(NearSessionClose(InpNoEntryMinsBefore))
     {
      if(InpVerbose) Print("Skipped: within ", InpNoEntryMinsBefore,
                           " min of session close");
      return;
     }
   if(FridayCutoff(true))
     {
      if(InpVerbose) Print("Skipped: Friday cutoff");
      return;
     }
   if(IsMarketHoliday(TimeCurrent()))
     {
      if(InpVerbose) Print("Skipped: market holiday");
      return;
     }
   if(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL)
     {
      if(InpVerbose) Print("Skipped: symbol not fully tradeable");
      return;
     }

   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && spread > InpMaxSpreadPoints)
     {
      if(InpVerbose) Print("Skipped: spread ", spread);
      return;
     }

   bool up = Aligned(1, true);
   bool dn = Aligned(1, false);
   if(!up && !dn) return;
   if(up && !InpAllowBuys)  return;
   if(dn && !InpAllowSells) return;

   if(InpUseCrossFilter && CrissCross() > InpMaxCrosses) return;
   double slNow2 = SlopeATR(up);
   if(InpUseSlope && slNow2 < InpMinSlopeATR) return;
   //--- block entries where the trend is already running vertically
   if(InpMaxSlopeATR > 0.0 && slNow2 > InpMaxSlopeATR)
     { if(InpVerbose) Print("Skipped: slope too steep ", DoubleToString(slNow2,2)); return; }
   if(!PullbackOK(up)) return;
   if(InpUseMomentum && !MomentumShiftOK(up)) return;

   if(InpUseVolume)
     {
      double vr = VolumeRatio();
      if(vr >= 0.0 && vr < InpMinVolRatio)
        { if(InpVerbose) Print("Skipped: volume ", DoubleToString(vr,2)); return; }
     }
   if(InpUseSRDist)
     {
      double atrTmp;
      if(GetATR(atrTmp))
        {
         double sd = SRDistanceATR(up, atrTmp);
         if(sd >= 0.0 && sd < InpMinSRDistATR)
           { if(InpVerbose) Print("Skipped: on a level, ", DoubleToString(sd,2), " ATR"); return; }
        }
     }
   //--- combined slope x S/R block (2026-09-16, Python-only, see
   //--- InpUseSlopeSRBlock's own comment) - a real, distinct bad-signal
   //--- class neither threshold alone catches: steep slope AND far from
   //--- the nearest S/R level, simultaneously.
   if(InpUseSlopeSRBlock)
     {
      double atrTmp2;
      if(GetATR(atrTmp2))
        {
         double sd2 = SRDistanceATR(up, atrTmp2);
         if(slNow2 >= InpSlopeSRBlockSlope && sd2 >= InpSlopeSRBlockSR)
           {
            if(InpVerbose) Print("Skipped: slope+SR block, slope ", DoubleToString(slNow2,2),
                                 " SR ", DoubleToString(sd2,2));
            return;
           }
        }
     }

   //--- size and stop
   double atr;
   if(!GetATR(atr) || atr <= 0.0) return;
   double stopDist = InpUseStopLoss ? InpStopATR * atr : 0.0;
   double lots = LotSize(stopDist);
   if(lots <= 0.0) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl  = 0.0;
   if(InpUseStopLoss)
      sl = up ? NormalizeDouble(ask - stopDist, _Digits)
              : NormalizeDouble(bid + stopDist, _Digits);

   bool ok = up ? trade.Buy(lots, _Symbol, 0.0, sl, 0.0, InpComment)
                : trade.Sell(lots, _Symbol, 0.0, sl, 0.0, InpComment);
   if(ok)
     {
      g_ticket      = trade.ResultOrder();
      g_entryTime   = TimeCurrent();
      g_entryPrice  = trade.ResultPrice();
      g_entryDir    = up ? 1 : -1;
      g_entryATR    = atr;
      g_entryLots   = lots;
      g_entryBarCount = 0;
      g_addsDone    = 0;
      g_price21Bad  = 0;
      g_vwapBad     = 0;
      g_beDone      = false;
      g_peakFavPx   = g_entryPrice;
      Print(up ? "BUY " : "SELL ", lots, " @ ", g_entryPrice,
            "  slope ", DoubleToString(SlopeATR(up), 2));
     }
   else
      Print("Order failed: ", trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
