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
//|                                                                    |
//|  v1.06: shortened every input's inline comment (this file was the only one in the portfolio          |
//|  with paragraph-length research citations inline). MT5's Tester Inputs tab shows an input's           |
//|  COMMENT as the row label, not its variable name - v1.02-v1.05's comments were full sentences           |
//|  citing real Python evidence, so that label column showed unreadable truncated prose instead of          |
//|  a short, recognizable field name (confirmed against a real screenshot of the Inputs tab). Every            |
//|  input now has a short, single-clause label matching the rest of this portfolio's own style               |
//|  (Aurelius_EA.mq5 etc.) - the full real-evidence detail these comments used to carry is not lost,             |
//|  it already lives in this header (v1.01-v1.05 above) and nowhere else needed it. No signal, entry,             |
//|  exit, sizing, or risk-management logic touched - purely a readability fix.                                     |
//|                                                                    |
//|  v1.07: brought up to the family visual standard the rest of this portfolio already has (see     |
//|  SESSION_NOTES.md on the original standardization pass - Aurelius_EA.mq5/Fulcrum_EA.mq5/etc.).       |
//|  Ported verbatim: chart theme (InpApplyTheme - neon-blue/white candles, black background,               |
//|  InpHideTradeMarks turns off MT5's own SL/TP lines so this file's own drawings are the only thing         |
//|  on the chart), a background wallpaper image (InpBackgroundBMP, same goldbg_blend.bmp default), and        |
//|  a corner watermark (InpWatermark). Also new: InpDrawPending (on by default) draws un-confirmed             |
//|  shapes - shoulders/head/neckline already found by Recompute() but not yet breakout-confirmed - in            |
//|  a dimmer InpColPending colour with a "(n/InpBreakConfirmCloses closes)" progress label, so a               |
//|  pattern is visible on the chart as it forms rather than only appearing at the moment it's already            |
//|  tradeable. Real limitation, disclosed rather than overclaimed: the underlying swing/pivot detection            |
//|  (FindSwings(), N=InpPivotStrength bars each side) cannot recognise a swing point until N bars AFTER             |
//|  it happened - so what appears is a fully-formed 5-point shape awaiting its neckline break, not a                 |
//|  shoulder still being built candle-by-candle before that point; there is no way to show a pivot the                 |
//|  detection itself hasn't confirmed yet without abandoning the N-bar fractal definition the whole                     |
//|  real-validated construction is built on. Purely visual/cosmetic - no signal, entry, exit, sizing, or                 |
//|  risk-management logic touched.                                                                                         |
//|                                                                    |
//|  v1.08: the stacked combo (InpStopBufferATR 0.3->1.0, InpBreakTolATR 0.10->0.35,               |
//|  InpUsePullbackEntry false->true, InpUseRunner false->true) is now the DEFAULT, not an              |
//|  opt-in toggle - the first change in this file's history to promote a candidate to default            |
//|  rather than ship it off. Real MT5 evidence behind this call (both real GOLD, same account):            |
//|  (1) a 2026-only run (9 months): net 7234.04->18183.37 ZAR (+151%), PF 1.238->1.983, equity DD             |
//|  22.91%->11.26%; (2) a full 2020-2026 run (6.73 years, 538 trades): net +17781.01, PF 1.227 -               |
//|  weaker than the 2026-only figure because 82% of the total came from 2026 alone, and 2025 was a              |
//|  losing year (-2175.46). Investigated rather than waved away: 2025's loss traced to just 2-3 bad               |
//|  months (Feb -1971, Nov -2673, Dec -1672, win% collapsing to 12-27% in those specific months) with              |
//|  7 of 12 months still profitable - the signature of a breakout system hitting a real choppy/false-               |
//|  breakout regime, not a broken mechanism (every 2025 exit closing via a stop-type order, including               |
//|  wins, is InpUseRunner working exactly as designed - no broker-side TP exists once it's on, so a                  |
//|  winning trade also technically exits via its own trailed stop). The 2020-2023 portion of the full                 |
//|  run carries a real, disclosed, and NOT independently fixable caveat: that Strategy Tester run's own                 |
//|  History Quality was only 34% real ticks (vs 100% for the 2026-only run) - this project's own real GOLD              |
//|  bar data doesn't even cover 2020 - mid-2022 (research/aurelius/engine.py's M5 loader starts 2022-07-04),             |
//|  so there is no way to independently re-derive that stretch at higher fidelity than MT5's Tester already              |
//|  gives it. Decision to default this made explicitly by the user after being shown all of the above, not               |
//|  unilaterally - matching this file's own standing rule that a candidate earns default status only once                 |
//|  someone has actually looked at the real evidence and chosen it, not on my say-so alone.                                  |
//|                                                                                                                              |
//|  v1.09: cosmetic only, no logic/input change. DrawPattern() and DrawPendingPattern() previously             |
//|  only drew the 3 pivot markers (shoulders/head) and the neckline - the shoulders and head floated            |
//|  on the chart with nothing connecting them, so the actual zigzag SHAPE of the pattern (left                  |
//|  shoulder -> trough -> head -> trough -> right shoulder) wasn't visible, only its endpoints and the           |
//|  neckline derived from it. Added 4 connecting trend-line segments (S1-T1, T1-Head, Head-T2, T2-S2)            |
//|  tracing the real outline, in both the confirmed (solid, pattern's own top/inverse colour) and                |
//|  pending/forming (dotted, InpColPending) drawing paths. Same object-name prefix as everything else            |
//|  in DrawPattern/DrawPendingPattern, so RemovePatternDrawing()'s existing ObjectsDeleteAll(0, base)             |
//|  already cleans these up too - no new cleanup code needed.                                                    |
//|                                                                                                                              |
//|  v1.10: real bug, found from the user's own live GOLD D1 Journal log (2026-10-02): CheckForEntry()           |
//|  previously marked EVERY rejected order as a permanent skip (traded=true), with no distinction               |
//|  between rejection reasons. The real log showed two orders failing with retcode 10018                        |
//|  (TRADE_RETCODE_MARKET_CLOSED), both timestamped 01:00:0X server time - a pullback-retest trigger             |
//|  landing right at a session boundary. Unlike every other rejection reason handled here (bad                  |
//|  stops, no money), a closed market is TRANSIENT - the same retest condition is very likely still              |
//|  true once the session reopens. D1 has so few real pattern opportunities to begin with (8 real                |
//|  GOLD candidates 2023-2026, confirmed by an independent Python replication of this exact                      |
//|  construction) that losing even one or two to this threw away a real trade, not a bad one - the               |
//|  user's real D1 test showed zero trades for 2023-2026 despite valid patterns genuinely forming.               |
//|  Fix: on MARKET_CLOSED specifically, under InpUsePullbackEntry (the default), leave the pattern               |
//|  untouched so CheckForEntry() re-checks it on the next tick, already bounded by the existing                  |
//|  ageBars > InpPullbackWindowBars expiry - no new unbounded-retry risk. Immediate-entry mode is                |
//|  unaffected (its trigger is an exact P.brk_t==t1 equality with no later re-check possible, so a               |
//|  skip is still the only correct outcome there). Every OTHER rejection reason still permanently                |
//|  skips the pattern exactly as before.                                                                         |
//|                                                                                                                |
//|  v1.11: real-money hardening pass from an Opus audit of v1.10 (findings numbered as in that audit). No pattern-  |
//|  detection math, no input default, no stop/target/runner RULE changed; every change is about orders actually      |
//|  reaching the market, or state surviving real terminal life. (1/2/9) UNIFIED TRANSIENT-ENTRY RETRY: v1.10's        |
//|  MARKET_CLOSED fix never worked as built - "re-check on the next tick" was really NEXT BAR (CheckForEntry() only     |
//|  runs inside IsNewBar()), i.e. on D1 24h later at the same 01:00 session boundary that rejected it, and it needed a   |
//|  second retest bar. Now AttemptEntry() is the one place an entry is sent; a block or rejection that can clear by       |
//|  itself (spread > InpMaxSpreadPoints - finding #2, folded into the same path rather than a separate one; outside the     |
//|  trade session/trade mode; terminal disconnected/AutoTrading off; retcodes 10004/10016*/10018/10020/10021/10024/10027)    |
//|  leaves the pattern untraded with retry state, and RetryTransientEntries() re-attempts on EVERY tick (and the timer),       |
//|  at most one send per HS_RETRY_SEND_GAP_SEC=10s across all patterns, until filled, a permanent reason appears, or the        |
//|  retry expires: new input InpEntryRetryMinutes (60; 0 = off = every failure skips) after the first block, and in immediate-   |
//|  entry mode also the moment the trigger bar closes (that trigger is valid on one bar only); pullback mode stays bounded by     |
//|  InpPullbackWindowBars. On expiry the pattern is skipped - Python takes the FIRST retest or nothing, so this replaces v1.10's     |
//|  open-ended "try a later retest bar" handling. (*10016 only after the EA's own side/stops-level pre-check passed, so a stop that  |
//|  is invalid by the pattern's own numbers is never retried.) Fills are now judged by retcode DONE/DONE_PARTIAL, not CTrade's bool    |
//|  (true whenever the server merely answered). Every permanent skip now Journals its reason (SkipPattern() logged nothing before -     |
//|  exactly what hid the D1 zero-trade problem); deferrals/expiries/fills-after-retry are logged too, throttled. (6) AMBIGUOUS FILL:       |
//|  timeout 10012 / no connection 10031 / placed-not-filled 10008 / no answer are NOT re-sent blind (double-position risk) - all sends      |
//|  hold >= HS_INFLIGHT_HOLD_SEC=60s and while an own order is live; an own position or entry deal appearing within HS_INFLIGHT_ADOPT_SEC     |
//|  =1h is ADOPTED (pattern executed, ArmRunner() - otherwise a tp=0.0 runner position would run unmanaged). Best-effort, limits disclosed     |
//|  at ResolveInflight(); a second own position triggers a loud hourly warning, never an auto-close. (3) MULTI-INSTANCE GUARD: a second chart  |
//|  with the same symbol+InpMagic refuses to start (they adopted each other's positions and fought over one runner stop) - keyed symbol+magic,  |
//|  NOT +period, so a live v1.10 position/runner state is not orphaned by attaching v1.11. (4) RUNNER FALLBACK: price already through the       |
//|  wanted trail -> close at market (a modify there is invalid by definition, and the research runner's stop has been hit); otherwise clamped to    |
//|  stops/freeze level with a one-tick floor, rounded away from price; a refused or clamped trail is re-tried every 10s on ticks instead of next     |
//|  bar (a full day on D1); failures Journal "runner PositionModify FAILED" with prices/levels. Peak/reached-target persisted as they move. (5) The     |
//|  first Recompute() after any (re)start ignores InpRecomputeEveryBars (was up to 4 days blind on D1). (7) DUPLICATE PATTERN - verified, not          |
//|  guessed: AlreadyKnown() needed s1+head+s2 all equal, but AddSwing() merging a later higher high into the right shoulder (or the sliding window        |
//|  moving s1) re-queued the same head as a new pattern - 144/2632 confirmed GOLD M15 heads, 152/2686 SILVER M15, 11/242 GOLD H4 in the EA-faithful      |
//|  hs_sim.py replica; now keyed head+direction (replica trade impact ~1%: GOLD M15 1143->1132 trades, %PF 1.283->1.291; SILVER M15 1092->1088, 1.089->   |
//|  1.099). (8) InpLots must sit on the broker's volume grid and InpATRPeriod >= 1, else the EA refuses to start (no silent clamping - clamping up would    |
//|  raise real exposure); fixed-lot by design, risk-relative sizing deliberately out of scope. Also: NormPrice() on every entry price/SL/TP;                 |
//|  CurrentATR() returns -1 on a short history read (AdvancePending() skips the bar) instead of a silent _Point ATR; a chart symbol/timeframe switch          |
//|  (OnDeinit+OnInit with globals kept) discards the old chart's pattern/runner RAM state; runner state re-saved once a late-visible position's ticket is       |
//|  known; an immediate-mode pattern whose one trigger bar passed unvisited is now skipped (was left untraded forever).                                          |
//|  NOT YET REAL-MT5-CONFIRMED, and hs_sim.py NO LONGER REPLICATES this file exactly - it has no transient failures, skips (not retries) on wide spread,          |
//|  dedups on the old key, and has no intrabar runner close. Update it and re-run the bar-match before trusting any new verdict built on v1.11 trades.         |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  v1.15 (2026-10-09): InpMaxSpreadPoints default 60 -> 50, real-        |
//|  validated. User ran three real MT5 "ideal execution" A/B reports      |
//|  (100% real ticks, no random-delay noise) at 50/55/60 over the same    |
//|  window (2026-01-01 - 2026-10-08): 50 beat both 55 and 60 on EVERY     |
//|  metric - net profit (11892.09 vs 10927.96 vs 10845.89), max drawdown  |
//|  (17.08% vs 19.70% vs 19.69%), PF (1.608 vs 1.512 vs 1.507), win%       |
//|  (47.69 vs 45.59 vs 45.59). Confirmed NOT a short-window artifact: full |
//|  real 2014-2026 GOLD M15 history (research/trendbreaker/                |
//|  hs_max_spread_filter_test.py) shows the same direction OOS - %PF       |
//|  1.428->1.501, net% 38.34->41.46, both the best of the three tested.    |
//|  55 is a near-total wash vs 60 in both tests - not worth using. No      |
//|  other logic changed; purely a default-value update on an existing      |
//|  input. Aurelius M5 was checked with the same 50/55/60 comparison the   |
//|  same night and found the OPPOSITE (60 beats both tighter settings      |
//|  there) - this is EA-specific, not a universal spread rule.             |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  v1.12: AdvancePending() pending-pattern EXPIRY fix - same bug class as   |
//|  v1.04's InpPullbackWindowBars fix, found in a different spot. The expiry  |
//|  check measured a pattern's formation length and age in wall-clock          |
//|  SECONDS (t_s2-t_s1, t1-t_s2), so real time elapsed over a weekend/session   |
//|  gap (no new bars, but ~48-60h of real time still passes) could push a        |
//|  still-forming, still-valid pattern's "age" past InpMaxHorizonMult's horizon   |
//|  purely from dead calendar time - silently deleting it from g_pending (and      |
//|  off the chart) with no real invalidation reason. Found answering a direct       |
//|  user question about patterns vanishing over a weekend - NOT by a dedicated        |
//|  audit, which is itself worth noting (see CLAUDE.md's 2026-10-04 section).           |
//|  Now bar-count based via iBarShift(), matching the v1.04 fix's convention.             |
//|  NOT YET bar-matched against a real run of this exact build.                           |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  v1.13: neckline SLOPE fix - same bug class as v1.04/v1.12, but in  |
//|  the trade-decision path itself. The slope was stored per wall-clock |
//|  SECOND (dt = t_t2-t_t1) and extended by elapsed seconds, so a        |
//|  pattern pending over a weekend had its neckline pushed ~48-60h of     |
//|  dead calendar time (~190 M15 bars' worth of slope) for ~1 real bar -   |
//|  distorting breakout confirmation, head height/target, and the pullback  |
//|  retest level, and making any trough pair that straddled a gap slope     |
//|  differently from what Python tested. Now per BAR, exactly the research's |
//|  construction (head_shoulders_target_test.py:95, hs_next_round_test.py:95):|
//|  slope = (p_t2-p_t1)/(i_t2-i_t1), neckline(t) = p_t1 + slope x bars from   |
//|  t_t1 to t (iBarShift, exact). Also: a pending pattern whose anchor bar     |
//|  left loaded history (iBarShift == -1) was never expired and sat in          |
//|  g_pending forever - it is now dropped (Journaled) the bar that happens.      |
//|  hs_sim.py updated to match this AND v1.12's bar-count expiry. Changes which   |
//|  trades fire - NOT YET bar-matched or random-timing re-tested on this build.     |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  v1.14 (2026-10-04): real bugs from a fresh unprimed audit of v1.13,  |
//|  fixed before any real/further MT5 run. (1) CRITICAL - durable cross-   |
//|  restart duplicate-confirmation record. g_patterns/g_pending only ever    |
//|  lived in RAM, and AlreadyKnown() only ever checked those two in-memory     |
//|  lists - after ANY terminal restart, recompile, or new build attach, the     |
//|  forced first Recompute() (finding #5) re-adds EVERY pattern shape from the    |
//|  last InpLookbackBars bars into g_pending with run=0, including ones already    |
//|  confirmed (and possibly already TRADED) before the restart; if price was        |
//|  still past the neckline it could confirm again InpBreakConfirmCloses closes       |
//|  later and fire a real SECOND entry on an already-traded setup. Measured on         |
//|  real GOLD M15 data: 150 random cold-restart points -> 231 patterns confirmed        |
//|  within 60 bars of restart, 136 (59%) already-confirmed-before-restart                |
//|  duplicates, 18 of those producing a valid pullback-retest entry trigger (~1           |
//|  fake trade per 8 restarts before the single-position gate). Fix: every                 |
//|  confirmed pattern is now also recorded durably in a terminal GlobalVariable               |
//|  (MarkPatternSeen(), same symbol+magic-keyed persistence idiom this file already           |
//|  uses for runner state/the instance lock), keyed on the same head+direction                 |
//|  AlreadyKnown() already used in RAM (v1.11 finding #7) - checked there too, so                |
//|  a pattern ever confirmed before, even across a restart, can never be re-queued                |
//|  as pending again. Bounded: PruneSeenPatterns() (called from the already-                       |
//|  throttled Recompute()) drops any record whose head bar has aged out of                          |
//|  InpLookbackBars - Recompute()'s own swing scan can never rediscover a pattern                    |
//|  that old again, so the durable record can never be needed again either. (2)                       |
//|  AdvancePending() boundary-value fix: an expired candidate dropped from                              |
//|  g_pending could be re-added by the NEXT Recompute() with run reset to 0 (the                         |
//|  swings are still there in price history) - and that bar's confirmation check                          |
//|  used to run BEFORE expiry was re-evaluated, so a revived-but-already-past-its-                          |
//|  horizon candidate could accumulate a confirming close immediately; at                                    |
//|  InpBreakConfirmCloses=1 (not the default 3) that is an instant confirmation one                           |
//|  Recompute() after being correctly expired. Expiry (age/horizon, which depends                              |
//|  only on t_s1/t_s2/t1, never on `run`) is now checked FIRST, before any                                      |
//|  confirmation attempt that bar; a genuinely live, non-revived candidate is                                    |
//|  unaffected (its age is <= horizon regardless of check order), so default                                     |
//|  InpBreakConfirmCloses=3 behaviour is unchanged. (3) ScheduleRetry() fix:                                      |
//|  HS_WHY_THROTTLE (another pattern's send is inside the global 10s send gate -                                  |
//|  AttemptEntry()) is not a failure of THIS pattern's own order, but with                                         |
//|  InpEntryRetryMinutes=0 (retries off) it was treated exactly like a real                                         |
//|  rejection and permanently skipped an otherwise healthy pattern that simply lost                                  |
//|  a 10-second race to a second triggered pattern on the same bar. A throttle-only                                  |
//|  block now still gets one short retry bounded to the send gate itself                                              |
//|  (HS_RETRY_SEND_GAP_SEC) even with retries off; any other (real) failure reason is                                 |
//|  unaffected and still skips immediately as InpEntryRetryMinutes=0 documents. Also:                                  |
//|  research/trendbreaker/hs_sim.py brought back in sync - dedup switched to                                            |
//|  head+direction (was t_s1/t_head/t_s2/top, the pre-v1.11 key) and the retest-window                                   |
//|  age calculation corrected to brkShift-1 = k-brk_i (was k-brk_i-1, one retest bar too                                  |
//|  many versus this file). NOT YET bar-matched or random-timing re-tested on this build -   |
//|  see CLAUDE.md's standing rule before reporting any verdict built on v1.14 trades.           |
//+------------------------------------------------------------------+
#property copyright "HeadShoulders_EA"
#property version   "1.15"
#property description "Trades the real-validated H&S/Inverse H&S measured-move target (75%/69%/75% hit rate, M15/H4/D1) - stacked combo default since v1.08, tick-level transient-entry retry + execution hardening in v1.11"
#property strict
#include <Trade\Trade.mqh>
CTrade trade;

//--- Swing / pivot detection (identical construction to the Python research) ---
input group "=== Swing / pivot detection (same construction as research/trendbreaker/) ==="
input int    InpPivotStrength   = 5;       // Fractal pivot strength, N bars each side
input double InpSwingMinATR     = 1.0;     // Min swing leg (ZigZag deviation), x ATR
input int    InpATRPeriod       = 14;      // ATR period (MT5 iATR)
input int    InpLookbackBars    = 800;     // Bars of history scanned each recompute
input int    InpRecomputeEveryBars = 5;    // Full swing rescan throttle, every N bars

input group "=== Head & Shoulders construction (real-validated target, see header) ==="
input double InpShoulderTolATR  = 1.5;     // Shoulder level tolerance, x ATR
input double InpBreakTolATR     = 0.35;    // Neckline break tolerance, x ATR
input int    InpBreakConfirmCloses = 3;    // Closes to confirm breakout
input double InpMaxHorizonMult  = 4.0;     // Pattern "live" horizon, x formation length

input group "=== Stop-loss (real-MT5-confirmed default since v1.08 - see header) ==="
input double InpStopBufferATR   = 1.0;     // SL buffer beyond right shoulder, x ATR

input group "=== RSI confluence filter (v1.02 candidate, off by default) ==="
input bool   InpUseRSIFilter    = false;   // Require RSI extreme to enter
input int    InpRSIPeriod       = 14;      // RSI period
input double InpRSIThreshold    = 30.0;    // RSI oversold/overbought threshold

input group "=== Pullback / retest entry (real-MT5-confirmed default since v1.08) ==="
input bool   InpUsePullbackEntry = true;   // Wait for neckline retest, not market entry
input double InpPullbackTolATR   = 0.75;   // Retest tolerance, x ATR
input int    InpPullbackWindowBars = 30;   // Retest window, bars

input group "=== Trailing runner past target (real-MT5-confirmed default since v1.08) ==="
input bool   InpUseRunner        = true;   // Trail stop past target, not fixed TP
input double InpRunnerTrailATR   = 0.5;    // Runner trail distance, x ATR

input group "=== Trade management ==="
input double InpLots             = 0.01;
input int    InpMagic            = 20260925;
input int    InpMaxSpreadPoints  = 50;     // Max spread to allow entry, points (v1.15, real-validated:
                                            // was 60, user's own real MT5 "ideal execution" A/B reports
                                            // (2026-01-01 - 2026-10-08, all three of 50/55/60 tested)
                                            // showed 50 beating both 55 and 60 on EVERY metric - net
                                            // profit, max drawdown, PF, win% - confirmed on the full
                                            // 2014-2026 real history too (OOS %PF 1.428->1.501, OOS
                                            // net% 38.34->41.46). 55 is a near wash vs 60, not worth
                                            // using. See research/trendbreaker/hs_max_spread_filter_test.py
input int    InpSlippage         = 30;
input int    InpEntryRetryMinutes = 60;    // Transient-failure entry retry, minutes (0 = off)

input group "=== Chart visuals ==="
input bool   InpDrawPatterns     = true;
input bool   InpDrawPending      = true;   // Draw un-confirmed shapes as they form
input bool   InpDrawHistory      = true;
input int    InpHistoryDays      = 60;
input color  InpColTop            = C'255,61,90';    // H&S top - bearish, warm red
input color  InpColInverse         = C'0,230,118';   // Inverse H&S - bullish, green
input color  InpColPending          = C'150,166,192'; // Un-confirmed shape colour, dimmer
input color  InpColTarget          = C'255,196,84';  // measured-move target line
input color  InpColEntryArrow      = C'255,255,255';
input int    InpLabelSize          = 8;

input group "=== Dashboard ==="
input string InpBackgroundBMP = "goldbg_blend.bmp";   // Background image (.bmp in MQL5\Images)
input int    InpBgWidth       = 1290;      // Image width, px (centring only)
input int    InpBgHeight      = 720;       // Image height, px (centring only)

input group "=== Chart theme ==="
input bool   InpApplyTheme      = true;    // Recolour the chart
input bool   InpHideTradeMarks  = true;    // Hide MT5's own buy/sell/SL/TP arrows
input color  InpChartBg     = clrBlack;           // Chart background
input color  InpBullCol     = C'0,150,255';       // Bullish candle - neon blue, family standard
input color  InpBearCol     = clrWhite;           // Bearish candle - neon white, family standard
input string InpWatermark   = "HEADSHOULDERS";    // Watermark text (empty = none)
input color  InpWaterCol    = C'46,38,24';        // Watermark colour
input bool   InpWaterBottom = true;               // Watermark bottom-right instead of centred
input int    InpWaterSize   = 42;                 // Watermark font size
input string InpWaterFont   = "Arial Black";      // Watermark font

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
   double   neckSlopePerBar;      // v1.13: price per BAR (i_t2 - i_t1 bar count), matching the Python research's neck_slope exactly - a price/bar ratio stays valid across CopyRates calls; only the reference point is re-resolved, via iBarShift() on t_t1 (see NecklineAtTime())
   int      brk_i;                // confirmed breakout bar index, -1 if not yet confirmed
   datetime brk_t;
   double   brk_price;
   double   target;
   double   stop;
   double   atrAtBrk;             // ATR captured at the breakout confirmation bar - shared by InpPullbackTolATR and InpRunnerTrailATR, matching the Python research's own "captured once, not recomputed per bar" convention
   bool     traded;               // true once this pattern is done being tracked, for ANY reason - a real fill OR a skip. See executed below for which one.
   bool     executed;             // true only if a real order was actually sent AND accepted - false for every skip reason (already in a position, spread too wide, retest window expired, invalid target/stop, RSI block, or a rejected order). traded && !executed = skipped, never a real trade.
   int      run;                  // pending-only: consecutive closes beyond the neckline seen so far
   //--- v1.11 transient-entry retry state (see AttemptEntry()/RetryTransientEntries()) - retryUntil == 0 = no retry pending.
   //--- Every append to g_pending/g_patterns assigns a WHOLE element (Recompute(): g_pending[k] = found[i], built from a
   //--- ZeroMemory()'d P in FindHSPatterns(); AdvancePending(): g_patterns[k] = P, a copy of that pending entry, whose
   //--- retry fields nothing ever writes) - so a newly confirmed pattern always starts with these at 0. This does NOT
   //--- rely on ArrayResize() zero-filling new struct elements (MQL5 doesn't promise that); verified at both sites.
   datetime retryBar;             // open time of the bar (shift 0) the retry was first scheduled on - immediate-entry mode expires the retry the moment this bar rolls over (its trigger is P.brk_t == the just-closed bar, valid on ONE bar only); pullback mode may run on into later bars (its own trigger is bar-spanning), bounded by retryUntil and InpPullbackWindowBars
   datetime retryUntil;           // hard stop for the retry: first block + InpEntryRetryMinutes (immediate mode: also capped at the end of retryBar)
   int      retryWhy;             // HS_WHY_* code of the most recent transient block (Journal only)
   uint     retryRetcode;         // last server retcode behind retryWhy (HS_WHY_RETCODE / HS_WHY_INFLIGHT), else 0
   int      retryCount;           // order SENDS so far for this pattern - only used for Journal throttling/summaries
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

//--- v1.11 unified transient-entry retry (findings #1/#2/#9 - see AttemptEntry()) and ambiguous-fill
//--- tracking (finding #6 - see AdoptInflightFill()). Result/reason codes are plain #defines, not an
//--- enum, so HSPattern stays a plain struct that ZeroMemory() resets cleanly.
#define HS_ENTRY_FILLED        0   // order accepted (or a position was found after an ambiguous result)
#define HS_ENTRY_SKIPPED       1   // permanent - SkipPattern() already called
#define HS_ENTRY_RETRY         2   // transient - pattern left untraded, retry state set
#define HS_WHY_NONE            0
#define HS_WHY_SPREAD          1   // spread > InpMaxSpreadPoints (session-open spikes - finding #2)
#define HS_WHY_SESSION         2   // outside the symbol's trade session / trade mode disallows this side
#define HS_WHY_AUTOTRADE       3   // terminal disconnected, or AutoTrading off at terminal/EA level
#define HS_WHY_INFLIGHT        4   // an earlier ambiguous order may still fill - never send a second one blind
#define HS_WHY_RETCODE         5   // server answered with a transient retcode (IsTransientRetcode())
#define HS_WHY_THROTTLE        6   // another entry was sent < HS_RETRY_SEND_GAP_SEC ago (global send gate) - not a failure, just "not yet"
#define HS_RETRY_SEND_GAP_SEC  10  // min seconds between two entry SENDS, any pattern (avoids 10024 too-many-requests); also the runner's re-try gap
#define HS_INFLIGHT_HOLD_SEC   60  // after an ambiguous result, no new send for this long while we look for the fill
#define HS_INFLIGHT_ADOPT_SEC  3600 // a position appearing up to this long after an ambiguous result is adopted (runner armed)
datetime g_lastEntrySend = 0;
int      g_inflightIdx   = -1;     // g_patterns index of the order whose result was ambiguous (g_patterns is append-only, so the index is stable), -1 = none
bool     g_inflightIsBuy = false;
datetime g_inflightTime  = 0;
bool     g_anyRetry      = false;  // true while at least one pattern MAY have a retry pending - lets RetryTransientEntries() skip its g_patterns scan on (almost) every tick
bool     g_forceRecompute = true;  // v1.11 finding #5 - the first Recompute() after OnInit() ignores the InpRecomputeEveryBars throttle
datetime g_runnerLastTry = 0;      // v1.11 finding #4 - last runner modify/close REQUEST sent (tick-level re-try gate)
datetime g_fillUnseenUntil = 0;    // v1.11 - a DONE fill whose position isn't in PositionsTotal() yet counts as "position open" until this time (or until SyncPosition() sees it) - see AttemptEntry()

//--- v1.11 multi-instance guard (finding #3) - see AcquireInstanceLock()
string   g_lockName = "";
//--- v1.11 chart symbol/timeframe change detection (low-priority finding) - MT5 does NOT reset an EA's
//--- globals on a chart symbol/period change (OnDeinit+OnInit run, globals survive), see OnInit()
string   g_stateSymbol = "";
ENUM_TIMEFRAMES g_statePeriod = PERIOD_CURRENT;

//--- wallpaper/watermark/theme - same family idiom as Aurelius_EA.mq5 etc. (see PBackground()/PTheme()/PWatermark())
string   g_pw = "HSW_";   // kept out of the panel wipe (g_pz), matching Aurelius's own g_pw convention
bool     g_bgOK = false;
int      g_bgTries = 0;

void PBackground();
void PTheme();
void PWatermark();

//+------------------------------------------------------------------+
int OnInit()
  {
   //--- v1.11 input validation (low-priority finding + finding #8). InpATRPeriod
   //--- is a divisor in BuildATR()/CurrentATR() and a CopyRates count - 0 or
   //--- negative would divide by zero / request nothing. InpLots is sent as-is
   //--- on every order: a value off the broker's own min/max/step grid makes
   //--- EVERY order fail with "invalid volume" (a permanent reject, so every
   //--- confirmed pattern would be silently skipped) - refuse to start instead,
   //--- loudly, rather than clamp (clamping UP to the minimum would silently
   //--- increase real-money exposure past what the user typed).
   if(InpATRPeriod <= 0)
     {
      PrintFormat("HeadShoulders_EA: InpATRPeriod=%d is invalid (must be >= 1) - EA NOT started.", InpATRPeriod);
      return(INIT_PARAMETERS_INCORRECT);
     }
   double vMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   bool lotsOk = (InpLots > 0.0) && (vMin <= 0.0 || InpLots >= vMin - 1e-9) && (vMax <= 0.0 || InpLots <= vMax + 1e-9);
   if(lotsOk && vStep > 0.0)
     {
      double k = InpLots / vStep;
      if(MathAbs(k - MathRound(k)) > 1e-6) lotsOk = false;
     }
   if(!lotsOk)
     {
      string msg = StringFormat("HeadShoulders_EA: InpLots=%.4f is not tradeable on %s (broker min %.4f / max %.4f / step %.4f) - EA NOT started.",
                                InpLots, _Symbol, vMin, vMax, vStep);
      Print(msg);
      if(!MQLInfoInteger(MQL_TESTER)) Alert(msg);
      return(INIT_PARAMETERS_INCORRECT);
     }
   //--- informational only: the SAME InpLots is a very different real exposure
   //--- per symbol (GOLD contract 100 vs SILVER 5000 at this broker) - printed so
   //--- the Journal shows what 1 trade actually means here. InpLots stays a fixed
   //--- lot by design; equity/risk-relative sizing is a possible FUTURE change
   //--- the user has not asked for, deliberately not implemented in v1.11.
   double cs = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   PrintFormat("HeadShoulders_EA: %s %s, InpLots=%.2f x contract %.0f = %.2f units per trade, magic %d.",
               _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), InpLots, cs, InpLots * cs, InpMagic);

   //--- v1.11 multi-instance guard (finding #3) - see AcquireInstanceLock()'s
   //--- own comment. Must run before the runner restore below, which would
   //--- otherwise adopt another chart's position/runner state as its own.
   if(!AcquireInstanceLock()) return(INIT_FAILED);

   //--- v1.11 chart symbol/timeframe change (low-priority finding): MT5 runs
   //--- OnDeinit()+OnInit() on a chart period/symbol switch but does NOT
   //--- reset this program's globals - g_patterns/g_pending (with ATR captured
   //--- on the OLD timeframe and pullback windows counted in OLD bars) and the
   //--- RAM runner state would silently carry over. Reset them (and their
   //--- drawings) instead; patterns are rediscovered by the first Recompute().
   if(g_stateSymbol != "" && (g_stateSymbol != _Symbol || g_statePeriod != (ENUM_TIMEFRAMES)_Period))
     {
      PrintFormat("HeadShoulders_EA: chart changed %s %s -> %s %s - discarding in-memory pattern/entry state from the old chart.",
                  g_stateSymbol, EnumToString(g_statePeriod), _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period));
      ArrayResize(g_patterns, 0);
      ArrayResize(g_pending, 0);
      g_lastBarTime = 0;
      g_barCounter = 0;
      g_inflightIdx = -1;
      g_anyRetry = false;
      g_fillUnseenUntil = 0;
      ObjectsDeleteAll(0, g_pz + "p_");
      ObjectsDeleteAll(0, g_pz + "pend_");
      if(g_stateSymbol != _Symbol)
        {
         ObjectsDeleteAll(0, g_pz + "en_");    // real-fill arrows are time-anchored, still correct on a TF-only change -
         ObjectsDeleteAll(0, g_pz + "ent_");   // but not on a different symbol's price scale
         //--- old symbol's position/runner belong to the old symbol - drop the RAM
         //--- copy only (NOT RunnerClearState(), whose GV keys are now the NEW symbol's)
         g_ticket = 0;
         g_runnerArmed = false;
         g_runnerJustArmed = false;
        }
     }
   g_stateSymbol = _Symbol;
   g_statePeriod = (ENUM_TIMEFRAMES)_Period;
   //--- v1.11 finding #5: the first Recompute() after ANY (re)start runs on the
   //--- first new bar regardless of InpRecomputeEveryBars - see OnTick().
   g_forceRecompute = true;

   //--- set once here too (not only right before an entry) so a runner close
   //--- or modify issued after a restart - before any new entry has run -
   //--- still carries this EA's magic (SyncPosition()'s stats lookup keys on it)
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);

   //--- PERFORMANCE FIX (see header v1.05, and Fulcrum_EA.mq5/Aurelius_EA.mq5/
   //--- etc.'s own identical fix) - a non-visual Strategy Tester run draws
   //--- NONE of the pattern markers/lines or the panel, since nobody can see
   //--- them and they have zero effect on any trading decision. Without this,
   //--- RefreshDrawings() was re-touching every confirmed pattern's several
   //--- chart objects on EVERY new bar, and DrawPanel() ~20 more every
   //--- simulated second, for the entire backtest - by far the dominant cost,
   //--- not the swing/pattern scan (that was already fixed in v1.01).
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);
   //--- v1.07: timer now gated the same way Aurelius_EA.mq5 learned to gate it
   //--- (its own v1.33 fix) - its only real job here is keeping the panel/
   //--- wallpaper alive between ticks, which is meaningless in a non-visual
   //--- Tester run; OnTick()'s own SyncPosition() calls already cover position
   //--- sync regardless of the timer.
   if(!g_skipCosmeticDraws) EventSetTimer(1);
   PTheme();   // theme applies even with the panel off - cheap, one-time, not gated
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
   ReleaseInstanceLock();   // v1.11 - always; a chart/param change re-acquires it in the following OnInit()
   if(g_rsiHandle != INVALID_HANDLE) { IndicatorRelease(g_rsiHandle); g_rsiHandle = INVALID_HANDLE; }
   if(reason != REASON_CHARTCHANGE && reason != REASON_PARAMETERS)
     {
      ObjectsDeleteAll(0, g_pz);
      ObjectsDeleteAll(0, g_pw);   // wallpaper/watermark - v1.07 gap fix, was never cleaned up
     }
   Comment("");
  }
//+------------------------------------------------------------------+
//| v1.11 multi-instance guard (finding #3). The user runs this EA on     |
//| GOLD and SILVER across several timeframes at once on ONE account.      |
//| Position ownership (FindOwnPosition()) and the runner's saved state     |
//| (RunnerGVPrefix()) are keyed by symbol+magic only - so two charts on     |
//| the SAME symbol with the SAME InpMagic (e.g. GOLD H1 + GOLD D1 both on    |
//| the default 20260925) would (a) adopt each other's open position via       |
//| SyncPosition(), each then skipping its own triggers as "already in a        |
//| position" for a trade that isn't its own, and (b) after a restart both       |
//| load the SAME saved runner state and trail the same position's stop with      |
//| their own peak/target. GOLD vs SILVER never collide (symbol differs).          |
//| Fix chosen: a per-terminal-session lock keyed by symbol+magic (the actual       |
//| collision domain - NOT symbol+magic+period, which would let exactly the          |
//| GOLD H1/GOLD D1 same-magic pair through). A second chart with the same            |
//| symbol+magic refuses to start, loudly, telling the user to give it its own         |
//| InpMagic. Deliberately NOT done: deriving the magic/GV keys from the period         |
//| automatically - that would orphan a live v1.10 position (opened under the            |
//| plain InpMagic) and its saved runner state the moment v1.11 is attached.              |
//| GlobalVariableTemp() = not written to disk, so a terminal crash can't leave a          |
//| stale lock behind; a lock whose chart no longer runs this EA is treated as stale        |
//| anyway. The chart id lives in the GV NAME, not its value - chart ids are ~1e17,          |
//| beyond a double's exact-integer range. Not applied in the Strategy Tester.                |
//+------------------------------------------------------------------+
string InstanceLockPrefix() { return("HSEA_LK_" + _Symbol + "_" + (string)InpMagic + "_"); }
bool ChartRunsThisEA(const long chartId)
  {
   for(long c = ChartFirst(); c >= 0; c = ChartNext(c))
      if(c == chartId)
         return(ChartSymbol(c) == _Symbol && ChartGetString(c, CHART_EXPERT_NAME) == MQLInfoString(MQL_PROGRAM_NAME));
   return(false);
  }
bool AcquireInstanceLock()
  {
   if(MQLInfoInteger(MQL_TESTER)) return(true);
   string prefix = InstanceLockPrefix();
   long me = ChartID();
   for(int g = GlobalVariablesTotal() - 1; g >= 0; g--)
     {
      string nm = GlobalVariableName(g);
      if(StringFind(nm, prefix) != 0) continue;
      long holder = StringToInteger(StringSubstr(nm, StringLen(prefix)));
      if(holder == me) continue;
      if(ChartRunsThisEA(holder))
        {
         string msg = StringFormat("HeadShoulders_EA NOT started on %s %s: chart %I64d already runs this EA on %s with the SAME InpMagic %d. "
                                   "Two instances on one symbol+magic adopt each other's positions and fight over the same runner stop - "
                                   "give every chart of the same symbol its own InpMagic (e.g. per timeframe).",
                                   _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), holder, _Symbol, InpMagic);
         Print(msg);
         Alert(msg);
         return(false);
        }
      GlobalVariableDel(nm);   // stale - that chart is gone or no longer runs this EA
     }
   g_lockName = prefix + (string)me;
   GlobalVariableTemp(g_lockName);
   GlobalVariableSet(g_lockName, (double)TimeLocal());
   return(true);
  }
void ReleaseInstanceLock()
  {
   if(g_lockName == "") return;
   GlobalVariableDel(g_lockName);
   g_lockName = "";
  }
//+------------------------------------------------------------------+
//| Price normalization (v1.11, low-priority finding) - every price that  |
//| goes into a trade request is rounded to the symbol's own tick size,   |
//| then to _Digits. Raw ATR arithmetic (stop = shoulder + k x ATR) gives  |
//| prices like 2351.4873219 that some servers reject as invalid price.     |
//+------------------------------------------------------------------+
double NormPrice(const double px)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double v = (ts > 0.0) ? MathRound(px / ts) * ts : px;
   return(NormalizeDouble(v, _Digits));
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
      //--- v1.13: per-BAR slope, exactly head_shoulders_target_test.py:95 /
      //--- hs_next_round_test.py:95,144: (p_t2 - p_t1) / (i_t2 - i_t1). The
      //--- zIdx values come from ONE CopyRates array, so their difference is
      //--- the real bar count between the troughs (weekend gaps add nothing).
      int dBars = P.i_t2 - P.i_t1;
      P.neckSlopePerBar = (dBars != 0) ? (P.p_t2 - P.p_t1) / (double)dBars : 0.0;
      P.brk_i = -1;
      P.traded = false;
      P.executed = false;
      P.run = 0;
      ArrayResize(out, nOut + 1, 32);
      out[nOut++] = P;
     }
   return(nOut);
  }
//+------------------------------------------------------------------+
//| v1.13: neckline value at bar-open time t = Python's neckline_at(q) |
//| = p_t1 + slope * (q - i_t1), with (q - i_t1) as a BAR COUNT taken   |
//| from iBarShift() (shift(t_t1) - shift(t)), never elapsed seconds.   |
//| exact=true: t_t1 and t are always real bar open times, so a -1 here  |
//| means that bar is genuinely not in loaded history - returns false    |
//| (caller must not trade on it) rather than a silently wrong count.     |
//+------------------------------------------------------------------+
bool NecklineAtTime(const HSPattern &P, const datetime t, double &nl)
  {
   nl = 0.0;
   int shiftRef = iBarShift(_Symbol, PERIOD_CURRENT, P.t_t1, true);
   int shiftT   = iBarShift(_Symbol, PERIOD_CURRENT, t, true);
   if(shiftRef < 0 || shiftT < 0) return(false);
   nl = P.p_t1 + P.neckSlopePerBar * (double)((long)shiftRef - (long)shiftT);
   return(true);
  }
//+------------------------------------------------------------------+
//| v1.14 CRITICAL FIX - durable cross-restart duplicate-confirmation    |
//| record. Found by a fresh audit (2026-10-04): g_patterns/g_pending     |
//| only ever lived in RAM, and AlreadyKnown() (below) only checked those  |
//| two in-memory arrays. After ANY terminal restart, recompile, or new     |
//| build attach, the forced first Recompute() (finding #5) re-scans the    |
//| last InpLookbackBars bars from scratch and re-adds EVERY pattern shape    |
//| it finds into g_pending with run=0 - including ones that were already      |
//| confirmed (g_patterns), and possibly already TRADED, before the restart.     |
//| If price was still past the neckline, the revived candidate can confirm       |
//| again InpBreakConfirmCloses closes later and fire a real SECOND entry on       |
//| a setup that already traded. Measured on real GOLD M15 data: 150 random         |
//| cold-restart points -> 231 patterns confirmed within 60 bars of restart,         |
//| 136 (59%) already-confirmed-before-restart duplicates, 18 of those produced       |
//| a valid pullback-retest entry trigger (~1 fake trade per 8 restarts before          |
//| the single-position gate). Fix: every pattern is recorded durably (terminal           |
//| GlobalVariables, same persistence idiom this file already uses for runner             |
//| state/the instance lock - see RunnerSaveState()/AcquireInstanceLock()) the              |
//| moment it is CONFIRMED (MarkPatternSeen(), called from AdvancePending()), keyed          |
//| on the same head+direction AlreadyKnown() already used in RAM (v1.11 finding              |
//| #7) - so a pattern that was ever confirmed before, even across restarts, can                |
//| never be re-queued as pending again. Bounded growth: PruneSeenPatterns() (called              |
//| from Recompute(), same throttle as the full rescan) drops any record whose head                |
//| bar has aged out of InpLookbackBars - Recompute()'s own swing scan can never                    |
//| structurally rediscover a pattern that old again, so its durable record is safe                  |
//| to drop too.                                                                                       |
//+------------------------------------------------------------------+
string SeenPatternPrefix() { return("HSEA_SEEN_" + _Symbol + "_" + (string)InpMagic + "_"); }
string SeenPatternKey(const bool top, const datetime tHead)
  {
   return(SeenPatternPrefix() + (top ? "T_" : "I_") + (string)(long)tHead);
  }
void MarkPatternSeen(const HSPattern &P)
  {
   GlobalVariableSet(SeenPatternKey(P.top, P.t_head), (double)TimeCurrent());
  }
bool PatternSeenPersisted(const bool top, const datetime tHead)
  {
   return(GlobalVariableCheck(SeenPatternKey(top, tHead)));
  }
//--- cheap, infrequent (called from Recompute(), itself throttled to every
//--- InpRecomputeEveryBars bars): scans only this symbol+magic's own GV
//--- prefix, same scan idiom as AcquireInstanceLock(), and deletes any
//--- "seen" record whose head bar is further back than 2x InpLookbackBars
//--- worth of time - a pattern that old cannot be rediscovered by
//--- FindSwings()/FindHSPatterns() (they only ever see the most recent
//--- InpLookbackBars bars), so its durable record can never be needed again.
void PruneSeenPatterns()
  {
   string prefix = SeenPatternPrefix();
   int pfxLen = StringLen(prefix);
   datetime cutoff = (datetime)((long)TimeCurrent() - 2L * (long)InpLookbackBars * (long)PeriodSeconds(PERIOD_CURRENT));
   for(int g = GlobalVariablesTotal() - 1; g >= 0; g--)
     {
      string nm = GlobalVariableName(g);
      if(StringFind(nm, prefix) != 0) continue;
      long tHead = StringToInteger(StringSubstr(nm, pfxLen + 2));   // +2 skips "T_"/"I_"
      if(tHead > 0 && (datetime)tHead < cutoff) GlobalVariableDel(nm);
     }
  }
//+------------------------------------------------------------------+
//| Same pattern already recorded, either confirmed or still pending?   |
//| v1.11 (finding #7, VERIFIED before fixing): keyed on head bar time + |
//| direction only. Up to v1.10 this required s1+head+s2 to ALL match -   |
//| but AddSwing() merges a later, more extreme same-type pivot INTO the   |
//| last swing (no opposite leg >= InpSwingMinATR x ATR in between), so a   |
//| higher high after the right shoulder moves t_s2 to that later bar, and  |
//| the sliding InpLookbackBars window can likewise move t_s1. Each moved    |
//| variant passed the old check and was queued as a SECOND pattern for the  |
//| same head (same neckline, different stop). Measured with the EA-faithful  |
//| replica research/trendbreaker/hs_sim.py, instrumented (2026-10-02):        |
//| GOLD M15 2014-06-13+ 144 of 2632 confirmed heads confirmed 2+ times,        |
//| SILVER M15 152/2686, GOLD H4 11/242 - often on DIFFERENT bars, i.e. a        |
//| second entry chance on one setup. Variants also share DrawPattern()'s         |
//| object names (keyed on t_head), so skipping one deleted the drawing of the     |
//| one that actually traded. Trade impact of this fix in the same replica:         |
//| GOLD M15 1143 -> 1132 trades (%PF 1.283 -> 1.291), SILVER M15 1092 -> 1088        |
//| (%PF 1.089 -> 1.099) - ~1% of trades, PF unchanged-to-slightly-better. The        |
//| FIRST-discovered variant is kept. NOTE: hs_sim.py itself still dedups on the      |
//| old 4-tuple and must get the same one-line change before the next bar-match.       |
//| v1.14: also checks PatternSeenPersisted() - see that fix's own header comment       |
//| above for why the in-memory-only check above is not enough across a restart.         |
//+------------------------------------------------------------------+
bool AlreadyKnown(const HSPattern &P)
  {
   for(int i = 0; i < ArraySize(g_patterns); i++)
      if(g_patterns[i].t_head == P.t_head && g_patterns[i].top == P.top)
         return(true);
   for(int i = 0; i < ArraySize(g_pending); i++)
      if(g_pending[i].t_head == P.t_head && g_pending[i].top == P.top)
         return(true);
   if(PatternSeenPersisted(P.top, P.t_head)) return(true);
   return(false);
  }
//+------------------------------------------------------------------+
//| Cheap ATR at the latest CLOSED bar (shift=1) - InpATRPeriod bars   |
//| only, not the full InpLookbackBars history, since this runs every   |
//| new bar for every pending candidate.                                 |
//| v1.11 (low-priority finding): returns -1.0 on a failed/short           |
//| CopyRates instead of silently returning _Point. A near-zero ATR there   |
//| made InpBreakTolATR x ATR ~0, so ANY close a hair past the neckline      |
//| counted toward confirmation, and the captured atrAtBrk (stop buffer,      |
//| retest tolerance, runner trail) would be degenerate for that pattern's     |
//| whole life. The caller now skips the bar instead.                           |
//+------------------------------------------------------------------+
double CurrentATR()
  {
   MqlRates r[]; ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, PERIOD_CURRENT, 1, InpATRPeriod + 1, r);
   if(got < InpATRPeriod + 1) return(-1.0);
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
//| v1.11: returns false only when history wasn't readable (too few bars  |
//| - typical right after a terminal start), so OnTick() keeps the forced  |
//| first scan (finding #5) pending until one actually succeeds.            |
//+------------------------------------------------------------------+
bool Recompute()
  {
   MqlRates r[]; ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpLookbackBars, r);
   if(n <= 4 * InpPivotStrength + InpATRPeriod + 20) return(false);

   double atr[]; BuildATR(r, n, atr);
   int zIdx[], zType[]; double zPx[];
   int zc = FindSwings(r, atr, n, zIdx, zType, zPx);
   if(zc < 5) return(true);

   HSPattern found[];
   int nf = FindHSPatterns(r, atr, n, zIdx, zType, zPx, zc, found);
   for(int i = 0; i < nf; i++)
     {
      if(AlreadyKnown(found[i])) continue;
      int k = ArraySize(g_pending);
      ArrayResize(g_pending, k + 1, 32);
      g_pending[k] = found[i];
     }
   PruneSeenPatterns();   // v1.14 - bounds the durable "seen" GV record, see its own header comment
   return(true);
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
   if(atrNow <= 0.0)
     {
      //--- v1.11: history not readable this bar - skip it rather than run on a
      //--- degenerate ATR (see CurrentATR()). Known side effect, disclosed: this
      //--- one bar is neither counted toward nor resets a candidate's consecutive-
      //--- close run - far less harmful than a spurious confirmation.
      PrintFormat("HeadShoulders_EA: CurrentATR() read failed at %s - pending-pattern advance skipped this bar.", TimeToString(t1));
      return;
     }
   for(int i = ArraySize(g_pending) - 1; i >= 0; i--)
     {
      HSPattern P = g_pending[i];
      if(t1 <= P.t_s2) continue;   // this candidate's own formation bar hasn't closed relative to t1 yet (can happen the same bar it formed)

      //--- v1.13: bar-count anchors resolved FIRST. Up to v1.12 a -1 from
      //--- iBarShift() (anchor bar no longer in loaded chart history) left
      //--- `expired` false forever, so the pattern sat in g_pending (and on
      //--- the chart) permanently. Any anchor that can't be resolved now
      //--- drops the pattern immediately - it can never be evaluated again
      //--- (history only loses old bars). exact=true: these are always real
      //--- bar open times, so -1 means genuinely gone, not "nearest bar".
      int shift_s1 = iBarShift(_Symbol, PERIOD_CURRENT, P.t_s1, true);
      int shift_s2 = iBarShift(_Symbol, PERIOD_CURRENT, P.t_s2, true);
      double nl = 0.0;
      bool nlOk = NecklineAtTime(P, t1, nl);
      if(shift_s1 < 0 || shift_s2 < 0 || !nlOk)
        {
         PrintFormat("HeadShoulders_EA: pending %s (head %s) dropped - anchor bar no longer in loaded history (iBarShift s1=%d s2=%d, neckline %s).",
                     P.top ? "H&S top" : "Inverse H&S", TimeToString(P.t_head), shift_s1, shift_s2, nlOk ? "ok" : "unresolved");
         int lastD = ArraySize(g_pending) - 1;
         if(i != lastD) g_pending[i] = g_pending[lastD];
         ArrayResize(g_pending, lastD);
         continue;
        }

      //--- v1.12 FIX: this used to measure patLen/age in wall-clock SECONDS
      //--- (t_s2-t_s1, t1-t_s2) - the exact same class of bug already found
      //--- and fixed for InpPullbackWindowBars in v1.04 (real time keeps
      //--- passing over a weekend/session gap even though no new bars form,
      //--- so wall-clock seconds overcounts "age" there). A pattern still
      //--- forming going into a weekend could have its age jump by ~48-60h
      //--- of dead calendar time and get wrongly marked expired/removed on
      //--- Monday, even though essentially zero real trading bars elapsed.
      //--- Now bar-count based via iBarShift(), same pattern as the v1.04 fix.
      //--- (v1.13: shift_s1/shift_s2 are resolved at the top of the loop, and
      //--- a -1 on either already dropped the pattern there.)
      //--- v1.14 FIX: this expiry check now runs BEFORE any confirmation
      //--- attempt this bar, not after. Bug: once an expired candidate is
      //--- dropped from g_pending here, the NEXT Recompute() can re-add the
      //--- IDENTICAL shape (same s1/t1/head/t2/s2 - the swings are still
      //--- there in price history) with `run` reset to 0, since AlreadyKnown()
      //--- has no reason to reject something that was never confirmed. Age/
      //--- horizon depend only on t_s1/t_s2/t1, not on `run` - so a revived
      //--- candidate that was already past its horizon is STILL past it the
      //--- instant it reappears. Checking confirmation FIRST (the old order)
      //--- let that revived-but-already-expired candidate accumulate a
      //--- confirming close on this very bar - at InpBreakConfirmCloses=1
      //--- that confirms IMMEDIATELY, one Recompute() after being correctly
      //--- expired. Now: already past horizon -> drop it, full stop, before
      //--- it is given any chance at a run++. A genuinely live (non-revived)
      //--- candidate is unaffected either way (its ageBars <= horizonBars
      //--- regardless of ordering), so default InpBreakConfirmCloses=3
      //--- behaviour for normal, non-revived candidates is unchanged.
      long patLenBars = (long)shift_s1 - (long)shift_s2;
      long ageBars = (long)shift_s2 - 1;   // shift 1 = t1, the last closed bar
      long horizonBars = (long)(MathMax((double)patLenBars, 1.0) * InpMaxHorizonMult);
      if(ageBars > horizonBars)
        {
         int lastE = ArraySize(g_pending) - 1;
         if(i != lastE) g_pending[i] = g_pending[lastE];
         ArrayResize(g_pending, lastE);
         continue;
        }

      double beyond = P.top ? (nl - c1) : (c1 - nl);
      bool confirmed = false;
      if(beyond > InpBreakTolATR * atrNow)
        {
         g_pending[i].run++;
         if(g_pending[i].run >= InpBreakConfirmCloses)
           {
            double nlHead = 0.0;
            double headHeight = NecklineAtTime(P, P.t_head, nlHead) ? MathAbs(P.p_head - nlHead) : 0.0;
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
               MarkPatternSeen(P);   // v1.14 - durable cross-restart record, see AlreadyKnown()'s header comment
               confirmed = true;
              }
           }
        }
      else
         g_pending[i].run = 0;

      if(confirmed)
        {
         int last = ArraySize(g_pending) - 1;
         if(i != last) g_pending[i] = g_pending[last];
         ArrayResize(g_pending, last);
        }
     }
  }
//+------------------------------------------------------------------+
//| Entry. Two trigger modes:                                           |
//|  - InpUsePullbackEntry OFF: only acts on a pattern the EXACT bar its    |
//|    breakout is confirmed (P.brk_t == the just-closed bar) - unchanged    |
//|    from v1.02.                                                            |
//|  - InpUsePullbackEntry ON (default since v1.08): does NOT act on the       |
//|    confirmation bar itself; instead waits for the FIRST later bar (within   |
//|    InpPullbackWindowBars) whose high/low comes back to within               |
//|    InpPullbackTolATR x ATR of the neckline (a real throwback) - matches      |
//|    eval_pullback_entry() in research/trendbreaker/hs_next_round_test.py       |
//|    exactly, including that a retest that never comes within the window is     |
//|    skipped entirely, not a fallback market entry.                               |
//| A pattern that was already confirmed/decided is drawn/kept for history but        |
//| never traded late either way. InpMaxHorizonMult bounds how long an                 |
//| UNCONFIRMED candidate is still considered live (AdvancePending()'s own               |
//| expiry) - it does not apply here, since this only ever sees confirmed ones.           |
//|                                                                                        |
//| v1.11: CheckForEntry() now only DETECTS a fresh trigger - still once per new bar,      |
//| still on the bar that just closed, exactly as before - and hands it to AttemptEntry()   |
//| (the one place an entry order is ever sent). A pattern already in a transient retry       |
//| (retryUntil != 0) is skipped here: RetryTransientEntries() owns it, on every tick,          |
//| including its expiry. See AttemptEntry() for why the retry had to move off the bar.         |
//+------------------------------------------------------------------+
void CheckForEntry()
  {
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   double h1 = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double l1 = iLow(_Symbol, PERIOD_CURRENT, 1);
   if(t1 == 0) return;

   for(int i = ArraySize(g_patterns) - 1; i >= 0; i--)
     {
      if(g_patterns[i].traded) continue;
      if(g_patterns[i].retryUntil != 0) continue;   // retry in progress - RetryTransientEntries()'s job
      HSPattern P = g_patterns[i];

      bool trigger;
      int  confirmShift = 1;   // immediate-entry mode: the confirm bar IS shift=1 whenever this can fire
      if(!InpUsePullbackEntry)
        {
         //--- v1.11: an untraded pattern whose ONE trigger bar has already passed
         //--- can never fire again (e.g. an earlier-index pattern filled and
         //--- returned on that bar, so this one was never visited - the Python
         //--- research marks it skipped via its single-position gate). Up to
         //--- v1.10 it stayed traded=false forever, uncounted and still drawn.
         if(P.brk_t < t1) { SkipPattern(i, "immediate-entry bar passed without an attempt (another pattern took that bar)"); continue; }
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
         if(ageBars > InpPullbackWindowBars)   // missed - matches the Python research's own "missed" bucket, skip entirely
           { SkipPattern(i, StringFormat("no neckline retest within InpPullbackWindowBars=%d bars", InpPullbackWindowBars)); continue; }
         double nl = 0.0;
         if(!NecklineAtTime(P, t1, nl))   // v1.13: per-bar neckline needs t_t1 still in loaded history - can't come back, so skip rather than retry every bar
           { SkipPattern(i, "neckline anchor bar (t_t1) no longer in loaded history - retest level can't be computed"); continue; }
         double tol = InpPullbackTolATR * P.atrAtBrk;
         trigger = P.top ? (h1 >= nl - tol) : (l1 <= nl + tol);
        }
      if(!trigger) continue;
      if(AttemptEntry(i, confirmShift) == HS_ENTRY_FILLED) return;   // single position - nothing else can open this bar
     }
  }
//+------------------------------------------------------------------+
//| v1.11 unified transient-entry retry (findings #1/#2/#9).               |
//| WHY: v1.10's MARKET_CLOSED fix left the pattern untraded so that        |
//| "CheckForEntry() re-checks it on the next tick" - but CheckForEntry()     |
//| only ever runs inside OnTick()'s IsNewBar() block, so the re-check was     |
//| really NEXT BAR. On the user's live GOLD D1 that is 24h later at the SAME   |
//| time of day as the original rejection (01:00:0X, the session boundary) -    |
//| very likely the same rejection again - and it also required a SECOND retest  |
//| bar; immediate-entry mode and every other transient cause (requote, price     |
//| off, spread spike at the session open - finding #2) still skipped for good.    |
//| NOW: every cause that can clear by itself within minutes leaves the pattern     |
//| untraded with retry state set (ScheduleRetry()) and RetryTransientEntries()      |
//| re-attempts on EVERY tick, throttled to one send per HS_RETRY_SEND_GAP_SEC        |
//| (any pattern), until it fills, a permanent reason appears, or the retry           |
//| expires: InpEntryRetryMinutes after the first block, or - immediate-entry mode     |
//| only - the moment the trigger bar rolls over (its trigger is valid on ONE bar);     |
//| pullback mode is additionally bounded by InpPullbackWindowBars. On expiry the        |
//| pattern is SKIPPED (logged) - the Python research takes the FIRST retest or never,    |
//| so a later, different retest bar is deliberately NOT a new chance (this replaces       |
//| v1.10's open-ended "leave it for a later bar" MARKET_CLOSED handling).                  |
//| Spread (finding #2) is just another transient reason through the same machinery.         |
//| Ambiguous results (finding #6 - timeout/no connection/placed-not-filled) are NOT           |
//| resent blind: see ResolveInflight().                                                        |
//| Returns HS_ENTRY_FILLED / HS_ENTRY_SKIPPED (permanent, logged) / HS_ENTRY_RETRY.             |
//| Check order: permanent reasons the research also has first, then transient ones              |
//| (nothing sent), then price/stop validity on the LIVE quote (permanent), then the send.        |
//+------------------------------------------------------------------+
int AttemptEntry(const int i, const int confirmShift)
  {
   HSPattern P = g_patterns[i];
   bool isBuy = !P.top;
   datetime now = TimeCurrent();

   //--- permanent: single-position rule (Opus review finding, fixed pre-first-
   //--- MT5-run): a trigger that fires while a position is open is marked done
   //--- right then, exactly like Python's last_exit_bar gating in
   //--- research/trendbreaker/hs_next_round_test.py - never traded later.
   //--- g_fillUnseenUntil: MT5 can report DONE before the new position shows up in
   //--- PositionsTotal(). With retries now on EVERY tick (not once a bar, as up to
   //--- v1.10), another pattern could otherwise send a second order in that gap.
   if(g_ticket != 0 || now < g_fillUnseenUntil) return(SkipPattern(i, "a position is already open (single-position rule)"));
   //--- InpUseRSIFilter - see its own input comment; confirmShift tracks P.brk_t's own bar
   if(!RSIFilterOk(isBuy, confirmShift)) return(SkipPattern(i, "RSI filter blocked it"));

   //--- transient: nothing is sent
   if(g_inflightIdx >= 0 && ((long)now - (long)g_inflightTime < HS_INFLIGHT_HOLD_SEC || HasOwnLiveOrder()))
      return(ScheduleRetry(i, HS_WHY_INFLIGHT, 0));
   if(!TradingEnabledNow()) return(ScheduleRetry(i, HS_WHY_AUTOTRADE, 0));
   if(!SessionTradableNow(isBuy)) return(ScheduleRetry(i, HS_WHY_SESSION, 0));
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && spr > InpMaxSpreadPoints) return(ScheduleRetry(i, HS_WHY_SPREAD, 0));
   if(g_lastEntrySend != 0 && (long)now - (long)g_lastEntrySend < HS_RETRY_SEND_GAP_SEC)
      return(ScheduleRetry(i, HS_WHY_THROTTLE, 0));
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0.0 || bid <= 0.0) return(ScheduleRetry(i, HS_WHY_SESSION, 0));   // no live quote

   //--- permanent: the pattern's own target/stop vs the LIVE price (rechecked on
   //--- every attempt - a retry never sends an order that is invalid by now)
   double entry = NormPrice(isBuy ? ask : bid);
   double stp = NormPrice(P.stop);
   double tgt = NormPrice(P.target);
   if(isBuy ? (tgt <= entry) : (tgt >= entry))
      return(SkipPattern(i, StringFormat("price %s already at/past target %s", DoubleToString(entry, _Digits), DoubleToString(tgt, _Digits))));
   if(isBuy ? (stp >= entry) : (stp <= entry))
      return(SkipPattern(i, StringFormat("price %s already at/past stop %s", DoubleToString(entry, _Digits), DoubleToString(stp, _Digits))));
   //--- broker minimum stop distance (SL/TP trigger on bid for a buy, ask for a sell).
   //--- Checked HERE so that a 10016 the server still returns afterwards can only
   //--- mean the price moved/gapped between this read and execution - which is why
   //--- IsTransientRetcode() may treat 10016 as transient without ever retrying a
   //--- stop that is invalid because of the pattern's own numbers.
   double stopsLvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double ref = isBuy ? bid : ask;
   if(stopsLvl > 0.0 && (MathAbs(ref - stp) < stopsLvl || (!InpUseRunner && MathAbs(tgt - ref) < stopsLvl)))
      return(SkipPattern(i, StringFormat("stop %s / target %s inside the broker's stops level (%s) of price %s",
                                         DoubleToString(stp, _Digits), DoubleToString(tgt, _Digits),
                                         DoubleToString(stopsLvl, _Digits), DoubleToString(ref, _Digits))));

   //--- send
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);
   string cmt = P.top ? "H&S top" : "Inverse H&S";
   double tp = InpUseRunner ? 0.0 : tgt;   // InpUseRunner replaces the fixed broker-side TP with ManageRunner()'s trailing stop - see its own input comment
   g_lastEntrySend = now;
   g_patterns[i].retryCount++;
   int sends = g_patterns[i].retryCount;
   //--- outcome judged by retcode only (below) - CTrade's bool is true whenever the
   //--- server answered at all, and false on paths where the order may still exist
   if(isBuy) trade.Buy(InpLots, _Symbol, entry, stp, tp, cmt);
   else      trade.Sell(InpLots, _Symbol, entry, stp, tp, cmt);
   uint rc = trade.ResultRetcode();
   if(rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL)
     {
      //--- (v1.10 tested only CTrade's bool, which is true whenever the server
      //--- ANSWERED - not necessarily with a fill; the retcode is what counts)
      ClearRetry(i);
      g_patterns[i].traded = true;
      g_patterns[i].executed = true;
      g_inflightIdx = -1;   // a confirmed fill supersedes any unresolved earlier send - see ResolveInflight()'s limitation note
      g_lastEntrySend = 0;  // the send gate exists to space out FAILED sends - never delay the next pattern after a fill
      SyncPosition();
      if(g_ticket == 0) g_fillUnseenUntil = (datetime)((long)now + HS_INFLIGHT_HOLD_SEC);   // filled but not visible yet - see the single-position check above
      double px = (trade.ResultPrice() > 0.0) ? trade.ResultPrice() : entry;
      if(sends > 1)
         PrintFormat("HeadShoulders_EA: %s entry FILLED at %s on send #%d (after transient retries).", cmt, DoubleToString(px, _Digits), sends);
      if(!g_skipCosmeticDraws) DrawEntryArrow(P, px);
      if(InpUseRunner) ArmRunner(P, isBuy);
      return(HS_ENTRY_FILLED);
     }
   if(rc == TRADE_RETCODE_PLACED || IsAmbiguousRetcode(rc))
     {
      //--- finding #6: the order may still fill (or may already have) - a blind
      //--- re-send here risks a DOUBLE position. Hold every new send, watch for
      //--- the fill and adopt it (ResolveInflight()/AdoptInflightFill()).
      g_inflightIdx = i;
      g_inflightIsBuy = isBuy;
      g_inflightTime = now;
      PrintFormat("HeadShoulders_EA: %s entry result AMBIGUOUS, retcode %u (%s) - NOT re-sending for >= %d s; watching for the position (adopting it, runner armed, if it appears within %d s).",
                  cmt, rc, trade.ResultRetcodeDescription(), HS_INFLIGHT_HOLD_SEC, HS_INFLIGHT_ADOPT_SEC);
      return(ScheduleRetry(i, HS_WHY_INFLIGHT, rc));
     }
   if(IsTransientRetcode(rc))
     {
      if(sends <= 3 || sends % 10 == 0)
         PrintFormat("HeadShoulders_EA: %s entry FAILED, retcode %u (%s) - transient, send #%d; will retry.", cmt, rc, trade.ResultRetcodeDescription(), sends);
      return(ScheduleRetry(i, HS_WHY_RETCODE, rc));
     }
   return(SkipPattern(i, StringFormat("entry FAILED, retcode %u (%s) - not a transient reason (send #%d)", rc, trade.ResultRetcodeDescription(), sends)));
  }
//+------------------------------------------------------------------+
//| Server answers that a retry can reasonably outlive within minutes.  |
//| Deliberately NOT here: 10019 no money, 10014 invalid volume, 10013   |
//| invalid request, 10006 reject, 10017/10026 trade disabled (account/   |
//| symbol configuration, not minutes) - those skip permanently, as      |
//| before. 10016 invalid stops is here ONLY because AttemptEntry()        |
//| pre-checks side + SYMBOL_TRADE_STOPS_LEVEL first (see the note there).  |
//| 10012 timeout / 10031 no connection are NOT here: the order may have     |
//| reached the server - see IsAmbiguousRetcode().                            |
//+------------------------------------------------------------------+
bool IsTransientRetcode(const uint rc)
  {
   switch(rc)
     {
      case TRADE_RETCODE_REQUOTE:              // 10004
      case TRADE_RETCODE_INVALID_STOPS:        // 10016 - price moved/gapped after our own pre-check passed
      case TRADE_RETCODE_MARKET_CLOSED:        // 10018 - the real v1.10 GOLD D1 case (01:00:0X server time)
      case TRADE_RETCODE_PRICE_CHANGED:        // 10020
      case TRADE_RETCODE_PRICE_OFF:            // 10021
      case TRADE_RETCODE_TOO_MANY_REQUESTS:    // 10024
      case TRADE_RETCODE_CLIENT_DISABLES_AT:   // 10027 - AutoTrading switched off in the terminal (same as HS_WHY_AUTOTRADE)
         return(true);
     }
   return(false);
  }
bool IsAmbiguousRetcode(const uint rc)
  {
   //--- 0 = no server answer recorded at all - treated as "may have been sent"
   return(rc == 0 || rc == TRADE_RETCODE_TIMEOUT || rc == TRADE_RETCODE_CONNECTION);
  }
string WhyText(const int why, const uint rc)
  {
   switch(why)
     {
      case HS_WHY_SPREAD:    return(StringFormat("spread above InpMaxSpreadPoints=%d", InpMaxSpreadPoints));
      case HS_WHY_SESSION:   return("outside the symbol's trade session / trade mode, or no live quote");
      case HS_WHY_AUTOTRADE: return("terminal disconnected or AutoTrading disabled");
      case HS_WHY_INFLIGHT:  return(rc != 0 ? StringFormat("earlier order unresolved (retcode %u)", rc) : "earlier order still unresolved");
      case HS_WHY_RETCODE:   return(StringFormat("server retcode %u", rc));
      case HS_WHY_THROTTLE:  return("send gap after another entry send");
     }
   return("none");
  }
//+------------------------------------------------------------------+
//| Transient pre-checks (live only - the Strategy Tester models its own  |
//| sessions/connection and has no AutoTrading button).                   |
//+------------------------------------------------------------------+
bool TradingEnabledNow()
  {
   if(MQLInfoInteger(MQL_TESTER)) return(true);
   return(TerminalInfoInteger(TERMINAL_CONNECTED) != 0 && TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) != 0 &&
          MQLInfoInteger(MQL_TRADE_ALLOWED) != 0 && AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) != 0 &&
          AccountInfoInteger(ACCOUNT_TRADE_EXPERT) != 0);
  }
//--- trade mode + today's trade-session table. A day with NO session rows is
//--- not blocked (broker data missing - let the server decide), so this can
//--- only ever save a request the server/terminal would reject anyway.
bool SessionTradableNow(const bool isBuy)
  {
   long tm = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(tm == SYMBOL_TRADE_MODE_DISABLED || tm == SYMBOL_TRADE_MODE_CLOSEONLY) return(false);
   if(tm == SYMBOL_TRADE_MODE_LONGONLY && !isBuy) return(false);
   if(tm == SYMBOL_TRADE_MODE_SHORTONLY && isBuy) return(false);
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   long sec = (long)dt.hour * 3600 + (long)dt.min * 60 + (long)dt.sec;
   datetime from, to;
   bool any = false;
   for(uint s = 0; s < 16; s++)
     {
      if(!SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)dt.day_of_week, s, from, to)) break;
      any = true;
      if(sec >= (long)from && sec < (long)to) return(true);   // from/to are seconds into the day (to may be 86400 = 24:00)
     }
   return(!any);
  }
bool HasOwnLiveOrder()
  {
   for(int k = OrdersTotal() - 1; k >= 0; k--)
     {
      ulong tk = OrderGetTicket(k);
      if(tk == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == (long)InpMagic) return(true);
     }
   return(false);
  }
//--- an entry (DEAL_ENTRY_IN) deal of ours at/after `since` - catches an
//--- ambiguous order that filled AND was already closed again between checks
bool OwnEntryDealSince(const datetime since)
  {
   if(!HistorySelect(since, TimeCurrent() + 3600)) return(false);
   for(int k = HistoryDealsTotal() - 1; k >= 0; k--)
     {
      ulong d = HistoryDealGetTicket(k);
      if(d == 0) continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != (long)InpMagic) continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      if((long)HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
      if((datetime)HistoryDealGetInteger(d, DEAL_TIME) >= since) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
//| Retry bookkeeping                                                    |
//+------------------------------------------------------------------+
void ClearRetry(const int i)
  {
   g_patterns[i].retryBar = 0;
   g_patterns[i].retryUntil = 0;
   g_patterns[i].retryWhy = HS_WHY_NONE;
   g_patterns[i].retryRetcode = 0;
   g_patterns[i].retryCount = 0;
  }
int ScheduleRetry(const int i, const int why, const uint rc)
  {
   //--- v1.14 FIX: HS_WHY_THROTTLE is NOT a failure of this pattern's own order -
   //--- it means a DIFFERENT pattern's send is still inside the global
   //--- HS_RETRY_SEND_GAP_SEC(10s) send gate (AttemptEntry()), so THIS pattern
   //--- never actually got to try. With InpEntryRetryMinutes=0 (retries off,
   //--- documented as "every failure skips") the old code treated that race
   //--- exactly like a real rejection and permanently skipped an otherwise
   //--- perfectly healthy pattern - CheckForEntry() moves on to a second
   //--- triggered pattern on the same bar, which then loses the 10s race and
   //--- was thrown away for good. Fix: a throttle-only block still gets one
   //--- short, bounded retry (until the send gate itself clears, never open-
   //--- ended) even with retries off; any OTHER reason (a real order failure/
   //--- rejection) is unaffected and still skips immediately as documented.
   bool throttleOnly = (why == HS_WHY_THROTTLE);
   if(InpEntryRetryMinutes <= 0 && !throttleOnly)
      return(SkipPattern(i, "transient block (" + WhyText(why, rc) + ") and InpEntryRetryMinutes=0 (retry off)"));
   bool first = (g_patterns[i].retryUntil == 0);
   if(first)
     {
      datetime now = TimeCurrent();
      datetime bar0 = iTime(_Symbol, PERIOD_CURRENT, 0);
      datetime until = (InpEntryRetryMinutes <= 0)
                        ? (datetime)((long)now + HS_RETRY_SEND_GAP_SEC)   // throttle-only, retries off: bounded to the send gate itself
                        : (datetime)((long)now + (long)InpEntryRetryMinutes * 60);
      if(!InpUsePullbackEntry)
        {
         datetime barEnd = (datetime)((long)bar0 + PeriodSeconds(PERIOD_CURRENT));
         if(barEnd < until) until = barEnd;
        }
      g_patterns[i].retryBar = bar0;
      g_patterns[i].retryUntil = until;
     }
   //--- the send gate is "not yet", not a cause - keep the real reason for the Journal
   if(why != HS_WHY_THROTTLE || g_patterns[i].retryWhy == HS_WHY_NONE)
     {
      g_patterns[i].retryWhy = why;
      g_patterns[i].retryRetcode = rc;
     }
   g_anyRetry = true;
   if(first)
      PrintFormat("HeadShoulders_EA: %s entry (head %s, confirmed %s) DEFERRED - %s; retrying on ticks until %s.",
                  g_patterns[i].top ? "H&S top" : "Inverse H&S", TimeToString(g_patterns[i].t_head), TimeToString(g_patterns[i].brk_t),
                  WhyText(why, rc), TimeToString(g_patterns[i].retryUntil, TIME_DATE|TIME_SECONDS));
   return(HS_ENTRY_RETRY);
  }
bool RetryExpired(const int i)
  {
   if(TimeCurrent() >= g_patterns[i].retryUntil) return(true);
   if(!InpUsePullbackEntry)
     {
      datetime b0 = iTime(_Symbol, PERIOD_CURRENT, 0);
      if(b0 != 0 && b0 != g_patterns[i].retryBar) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
//| Tick-level retry - called on EVERY tick (and timer), NOT gated by     |
//| IsNewBar(). Runs BEFORE OnTick()'s new-bar block, so an older pattern  |
//| still owed its entry gets priority over a fresh trigger on that tick.   |
//+------------------------------------------------------------------+
void RetryTransientEntries()
  {
   if(!g_anyRetry) return;
   bool any = false;
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   for(int i = ArraySize(g_patterns) - 1; i >= 0; i--)
     {
      if(g_patterns[i].traded || g_patterns[i].retryUntil == 0) continue;
      string last = WhyText(g_patterns[i].retryWhy, g_patterns[i].retryRetcode);
      if(RetryExpired(i))
        {
         SkipPattern(i, StringFormat("transient-entry retry ran out (%s) - last block: %s, %d send(s)",
                                     InpUsePullbackEntry ? "InpEntryRetryMinutes" : "trigger bar closed / InpEntryRetryMinutes",
                                     last, g_patterns[i].retryCount));
         continue;
        }
      int confirmShift = 1;
      if(!InpUsePullbackEntry)
        {
         if(t1 != 0 && g_patterns[i].brk_t != t1)   // belt-and-braces with RetryExpired()'s bar check
           { SkipPattern(i, "trigger bar passed during the transient-entry retry - last block: " + last); continue; }
        }
      else
        {
         int brkShift = iBarShift(_Symbol, PERIOD_CURRENT, g_patterns[i].brk_t, false);
         if(brkShift < 0) { any = true; continue; }
         if((long)brkShift - 1 > InpPullbackWindowBars)
           { SkipPattern(i, "InpPullbackWindowBars ran out during the transient-entry retry - last block: " + last); continue; }
         confirmShift = brkShift;
        }
      int res = AttemptEntry(i, confirmShift);
      if(res == HS_ENTRY_FILLED) return;   // leave g_anyRetry set - remaining retries get the single-position skip next tick
      if(res == HS_ENTRY_RETRY) any = true;
     }
   g_anyRetry = any;
  }
//+------------------------------------------------------------------+
//| Finding #6 - ambiguous entry result (timeout / no connection / placed  |
//| but not yet filled). Called every tick right after SyncPosition().      |
//| Since an entry is only ever sent while flat (g_ticket == 0), any own     |
//| position, or own entry deal, that appears after the ambiguous send IS    |
//| that order - it is adopted: pattern marked executed, entry arrow drawn,    |
//| and (InpUseRunner) ArmRunner() called - without which a real position       |
//| would run with tp=0.0 and nothing trailing it. Every new send, any pattern,  |
//| is held (HS_WHY_INFLIGHT) for HS_INFLIGHT_HOLD_SEC and for as long as an own   |
//| order is still live in the terminal.                                            |
//| KNOWN LIMITATIONS (best-effort scope, disclosed): (1) after the hold, with no   |
//| live order, no position and no entry deal seen, the first order is presumed NOT   |
//| filled and a re-send is allowed - if the server still fills the first one later,   |
//| two positions can exist; SyncPosition() then manages only one and Journals/alerts   |
//| a loud warning (it does not auto-close anything). (2) A late fill that appears after  |
//| HS_INFLIGHT_ADOPT_SEC is not adopted (no runner) - also caught by that warning only     |
//| if a second position exists; a lone one is picked up by SyncPosition() as the open        |
//| position with the runner NOT armed (same state as v1.10's "no saved runner state" case).   |
//+------------------------------------------------------------------+
void ResolveInflight()
  {
   if(g_inflightIdx < 0) return;
   if(g_inflightIdx >= ArraySize(g_patterns)) { g_inflightIdx = -1; return; }   // arrays reset (chart change)
   if(g_ticket != 0) { AdoptInflightFill(true); return; }
   static datetime lastHist = 0;   // deal-history lookup at most once per server second
   if(TimeCurrent() != lastHist)
     {
      lastHist = TimeCurrent();
      if(OwnEntryDealSince((datetime)((long)g_inflightTime - 5))) { AdoptInflightFill(false); return; }
     }
   if((long)TimeCurrent() - (long)g_inflightTime > HS_INFLIGHT_ADOPT_SEC && !HasOwnLiveOrder())
     {
      PrintFormat("HeadShoulders_EA: no position or fill appeared within %d s of the ambiguous entry sent %s - treated as NOT filled.",
                  HS_INFLIGHT_ADOPT_SEC, TimeToString(g_inflightTime, TIME_DATE|TIME_SECONDS));
      g_inflightIdx = -1;
     }
  }
void AdoptInflightFill(const bool posOpen)
  {
   int i = g_inflightIdx;
   bool isBuy = g_inflightIsBuy;
   double px = 0.0;
   if(posOpen)
     {
      if(!PositionSelectByTicket(g_ticket)) return;   // try again next tick
      bool posBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      g_inflightIdx = -1;
      if(posBuy != isBuy)
        {
         PrintFormat("HeadShoulders_EA: WARNING - own position #%I64u appeared after an ambiguous %s entry but is a %s - NOT adopted, runner NOT armed. Check it manually.",
                     g_ticket, isBuy ? "BUY" : "SELL", posBuy ? "BUY" : "SELL");
         return;
        }
      px = PositionGetDouble(POSITION_PRICE_OPEN);
     }
   else
      g_inflightIdx = -1;
   if(g_patterns[i].executed) return;   // already recorded (e.g. a later send filled) - nothing to adopt
   HSPattern P = g_patterns[i];
   ClearRetry(i);
   g_patterns[i].traded = true;
   g_patterns[i].executed = true;
   if(posOpen)
     {
      if(!g_skipCosmeticDraws) DrawEntryArrow(P, px);
      if(InpUseRunner && !g_runnerArmed) ArmRunner(P, isBuy);
      PrintFormat("HeadShoulders_EA: ambiguous %s entry DID fill - position #%I64u at %s ADOPTED%s.",
                  isBuy ? "BUY" : "SELL", g_ticket, DoubleToString(px, _Digits), InpUseRunner ? ", runner armed" : "");
     }
   else
      PrintFormat("HeadShoulders_EA: ambiguous %s entry DID fill but the position is already closed again - recorded as executed, nothing to manage.",
                  isBuy ? "BUY" : "SELL");
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

   double prevPeak = g_runnerPeak;
   g_runnerPeak = g_runnerIsBuy ? MathMax(g_runnerPeak, h1) : MathMin(g_runnerPeak, l1);
   //--- v1.11: persist peak/reached-target as soon as they move, not only after
   //--- a successful modify - a restart otherwise restored a stale peak (or
   //--- reached=false), delaying the trail until price re-made that ground.
   if(g_runnerPeak != prevPeak) RunnerSaveState();
   RunnerApplyStop();
  }
//--- the research runner's stop: InpRunnerTrailATR x (breakout ATR) behind the best price since target
double RunnerWantedStop()
  {
   return(g_runnerIsBuy ? (g_runnerPeak - InpRunnerTrailATR * g_runnerAtr)
                        : (g_runnerPeak + InpRunnerTrailATR * g_runnerAtr));
  }
//--- round to the symbol's tick, AWAY from price (down for a buy's stop, up for a sell's) - never tighter than asked
double NormPriceDir(const double px, const bool down)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0.0) return(NormalizeDouble(px, _Digits));
   double k = px / ts;
   return(NormalizeDouble((down ? MathFloor(k + 1e-9) : MathCeil(k - 1e-9)) * ts, _Digits));
  }
//+------------------------------------------------------------------+
//| v1.11 finding #4 - applies the runner's wanted stop with a fallback   |
//| for every way the broker can refuse it. Called from ManageRunner()     |
//| (once per new bar, as before) AND from RunnerTick() on every tick,      |
//| gated to one request per HS_RETRY_SEND_GAP_SEC - so a refused or          |
//| clamped trail is re-tried within seconds instead of a whole bar later     |
//| (a full DAY on D1, with the position on its old stop meanwhile).           |
//|  1. price already through the wanted stop -> close at MARKET. A modify    |
//|     there is invalid by definition, and the research runner's own stop     |
//|     has been hit (its replica exits at that stop on the next bar).           |
//|  2. otherwise clamp to max(SYMBOL_TRADE_STOPS_LEVEL, SYMBOL_TRADE_FREEZE_     |
//|     LEVEL) x _Point, and never less than one tick, from the live price - the  |
//|     v1.04 Critical fix, now with the one-tick floor and tick rounding away     |
//|     from price. While clamped, every later attempt tightens toward the wanted   |
//|     stop as price allows.                                                        |
//|  3. any refusal anyway -> Journal "runner PositionModify FAILED" (the string       |
//|     the earlier audit said to search for) with the numbers needed to see why.       |
//+------------------------------------------------------------------+
void RunnerApplyStop()
  {
   if(!InpUseRunner || !g_runnerArmed || !g_runnerReachedTarget || g_ticket == 0) return;
   bool isBuy = g_runnerIsBuy;
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0.0) ts = _Point;
   double want = NormPriceDir(RunnerWantedStop(), isBuy);
   if(isBuy ? (want < g_runnerStop + 0.5 * ts) : (want > g_runnerStop - 0.5 * ts)) return;   // nothing tighter than what's already in place
   if(!PositionSelectByTicket(g_ticket)) return;   // position closed between OnTick's SyncPosition() and here - nothing to modify
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0.0 || ask <= 0.0) return;
   double ref = isBuy ? bid : ask;   // the side a buy's / sell's stop triggers on
   if(isBuy ? (want >= ref) : (want <= ref))
     {
      g_runnerLastTry = TimeCurrent();
      bool okc = trade.PositionClose(g_ticket, (ulong)InpSlippage);
      uint rcc = trade.ResultRetcode();
      if(okc && (rcc == TRADE_RETCODE_DONE || rcc == TRADE_RETCODE_DONE_PARTIAL))
         PrintFormat("HeadShoulders_EA: runner - price %s already through the trailed stop %s, position #%I64u CLOSED at market.",
                     DoubleToString(ref, _Digits), DoubleToString(want, _Digits), g_ticket);
      else
         PrintFormat("HeadShoulders_EA: runner market close FAILED, retcode %u (%s) - price %s is through the trailed stop %s; position still on stop %s, retrying every %d s.",
                     rcc, trade.ResultRetcodeDescription(), DoubleToString(ref, _Digits), DoubleToString(want, _Digits),
                     DoubleToString(g_runnerStop, _Digits), HS_RETRY_SEND_GAP_SEC);
      return;
     }
   long lvlPts = MathMax(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
                         SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL));
   double minDist = MathMax((double)lvlPts * _Point, ts);
   double newStop = isBuy ? MathMin(want, ref - minDist) : MathMax(want, ref + minDist);
   newStop = NormPriceDir(newStop, isBuy);
   if(isBuy ? (newStop < g_runnerStop + 0.5 * ts) : (newStop > g_runnerStop - 0.5 * ts)) return;   // clamp leaves nothing tighter yet
   g_runnerLastTry = TimeCurrent();
   if(trade.PositionModify(g_ticket, newStop, 0.0) && trade.ResultRetcode() == TRADE_RETCODE_DONE)
     {
      g_runnerStop = newStop;
      RunnerSaveState();
     }
   else
      PrintFormat("HeadShoulders_EA: runner PositionModify FAILED, retcode %u (%s) - wanted %s, sent %s, bid %s ask %s, stops/freeze level %d pts; still on stop %s, retrying every %d s.",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription(), DoubleToString(want, _Digits), DoubleToString(newStop, _Digits),
                  DoubleToString(bid, _Digits), DoubleToString(ask, _Digits), (int)lvlPts, DoubleToString(g_runnerStop, _Digits), HS_RETRY_SEND_GAP_SEC);
  }
//--- every tick: re-try a refused/clamped trail, or close if price crosses the wanted stop intrabar
void RunnerTick()
  {
   if(!InpUseRunner || !g_runnerArmed || !g_runnerReachedTarget || g_ticket == 0) return;
   if(g_runnerLastTry != 0 && (long)TimeCurrent() - (long)g_runnerLastTry < HS_RETRY_SEND_GAP_SEC) return;
   RunnerApplyStop();
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
//+------------------------------------------------------------------+
//| v1.11 (finding #6's disclosed limitation) - this EA manages ONE       |
//| position. Two own positions can only mean an ambiguous entry filled    |
//| after a re-send also filled (see ResolveInflight()), a manual trade     |
//| opened under this InpMagic, or two charts sharing symbol+magic despite   |
//| the instance lock. Nothing is closed automatically - it warns, loudly,    |
//| at most once an hour, so a human decides.                                  |
//+------------------------------------------------------------------+
void WarnIfMultipleOwnPositions()
  {
   static datetime lastWarn = 0;
   int cnt = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && (long)PositionGetInteger(POSITION_MAGIC) == (long)InpMagic) cnt++;
     }
   if(cnt <= 1) return;
   if(lastWarn != 0 && (long)TimeCurrent() - (long)lastWarn < 3600) return;
   lastWarn = TimeCurrent();
   string msg = StringFormat("HeadShoulders_EA WARNING: %d open positions on %s with magic %d - this EA manages only #%I64u (runner/stats). Check the others manually.",
                             cnt, _Symbol, InpMagic, g_ticket);
   Print(msg);
   if(!MQLInfoInteger(MQL_TESTER)) Alert(msg);
  }
void SyncPosition()
  {
   ulong tk;
   if(FindOwnPosition(tk))
     {
      if(tk != g_ticket)
        {
         g_ticket = tk;
         //--- v1.11: a fill whose position only became visible AFTER ArmRunner()
         //--- ran saved runner state under ticket 0 - re-save under the real
         //--- ticket, or a restart can't restore the runner (it keys on it).
         if(InpUseRunner && g_runnerArmed) RunnerSaveState();
        }
      g_fillUnseenUntil = 0;
      WarnIfMultipleOwnPositions();
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

   DrawLine(base + "seg1", P.t_s1, P.p_s1, P.t_t1, P.p_t1, col, 1, STYLE_SOLID, false);
   DrawLine(base + "seg2", P.t_t1, P.p_t1, P.t_head, P.p_head, col, 1, STYLE_SOLID, false);
   DrawLine(base + "seg3", P.t_head, P.p_head, P.t_t2, P.p_t2, col, 1, STYLE_SOLID, false);
   DrawLine(base + "seg4", P.t_t2, P.p_t2, P.t_s2, P.p_s2, col, 1, STYLE_SOLID, false);

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
//+------------------------------------------------------------------+
//| Removes a confirmed pattern's drawing by its stable object-name       |
//| prefix (same construction as DrawPattern's own `base`) - used the     |
//| moment a pattern resolves WITHOUT a real trade, so a skipped/expired   |
//| pattern's lines disappear immediately instead of lingering on the       |
//| chart looking identical to one that actually traded (the exact           |
//| confusion this was built to fix - a confirmed pattern the panel            |
//| counted as "traded" that never placed a real order).                         |
//+------------------------------------------------------------------+
void RemovePatternDrawing(const HSPattern &P)
  {
   string base = g_pz + "p_" + TimeToString(P.t_head, TIME_DATE|TIME_MINUTES) + (P.top ? "T" : "I") + "_";
   ObjectsDeleteAll(0, base);
  }
//+------------------------------------------------------------------+
//| Marks a pattern resolved WITHOUT a real trade (any skip reason:       |
//| already in a position, spread too wide, retest window expired,        |
//| invalid target/stop, RSI block, or a rejected order) and removes        |
//| its chart drawing right away. traded=true alone used to mean both         |
//| "really traded" and "gave up on it" - this keeps that flag's existing      |
//| meaning (resolved, don't revisit) but records which one separately.          |
//| v1.11: every permanent skip now Journals its reason - up to v1.10 a skip      |
//| (incl. a rejected order) logged nothing, which is exactly what made the        |
//| D1 "valid patterns, zero trades" failure invisible in the Journal. Also        |
//| clears any transient-retry state; returns HS_ENTRY_SKIPPED for AttemptEntry().   |
//+------------------------------------------------------------------+
int SkipPattern(const int idx, const string why)
  {
   PrintFormat("HeadShoulders_EA: %s (head %s, confirmed %s) SKIPPED - %s",
               g_patterns[idx].top ? "H&S top" : "Inverse H&S", TimeToString(g_patterns[idx].t_head),
               TimeToString(g_patterns[idx].brk_t), why);
   g_patterns[idx].traded = true;
   g_patterns[idx].executed = false;
   ClearRetry(idx);
   if(!g_skipCosmeticDraws) RemovePatternDrawing(g_patterns[idx]);
   return(HS_ENTRY_SKIPPED);
  }
//+------------------------------------------------------------------+
//| Un-confirmed shape - InpDrawPending. Same shoulders/head markers    |
//| and neckline as a confirmed pattern, but no target/stop (there is     |
//| none yet) and in InpColPending, so a shape mid-formation reads          |
//| visibly differently from a real, tradeable, confirmed one. Object        |
//| namespace ("pend_") is fully wiped and redrawn from g_pending every       |
//| call (simpler and provably correct than tracking which entries were        |
//| swap-removed from the array since the last call - RefreshDrawings()         |
//| already only runs once per new bar, gated by g_skipCosmeticDraws, so         |
//| the extra churn is immaterial).                                               |
//+------------------------------------------------------------------+
void DrawPendingPattern(const HSPattern &P)
  {
   string base = g_pz + "pend_" + TimeToString(P.t_head, TIME_DATE|TIME_MINUTES) + (P.top ? "T" : "I") + "_";
   DrawMarker(base + "s1", P.t_s1, P.p_s1, InpColPending, !P.top);
   DrawMarker(base + "head", P.t_head, P.p_head, InpColPending, !P.top);
   DrawMarker(base + "s2", P.t_s2, P.p_s2, InpColPending, !P.top);
   DrawLabel(base + "hl", P.t_head, P.p_head, "  forming...", InpColPending);

   DrawLine(base + "seg1", P.t_s1, P.p_s1, P.t_t1, P.p_t1, InpColPending, 1, STYLE_DOT, false);
   DrawLine(base + "seg2", P.t_t1, P.p_t1, P.t_head, P.p_head, InpColPending, 1, STYLE_DOT, false);
   DrawLine(base + "seg3", P.t_head, P.p_head, P.t_t2, P.p_t2, InpColPending, 1, STYLE_DOT, false);
   DrawLine(base + "seg4", P.t_t2, P.p_t2, P.t_s2, P.p_s2, InpColPending, 1, STYLE_DOT, false);

   DrawLine(base + "neck", P.t_t1, P.p_t1, P.t_t2, P.p_t2, InpColPending, 1, STYLE_DASH, true);
   string runTxt = StringFormat("  awaiting break (%d/%d closes)", P.run, InpBreakConfirmCloses);
   DrawLabel(base + "necklbl", P.t_t2, P.p_t2, runTxt, InpColPending);
  }
void RefreshDrawings()
  {
   if(g_skipCosmeticDraws) return;   // PERFORMANCE FIX - see its own comment in OnInit()
   if(!InpDrawPatterns) { ObjectsDeleteAll(0, g_pz + "p_"); ObjectsDeleteAll(0, g_pz + "pend_"); return; }
   datetime cutoff = InpDrawHistory ? (datetime)(TimeCurrent() - (long)InpHistoryDays * 86400) : (datetime)(TimeCurrent() - 5 * (long)PeriodSeconds(PERIOD_CURRENT) * InpLookbackBars);
   for(int i = 0; i < ArraySize(g_patterns); i++)
     {
      if(g_patterns[i].t_s2 < cutoff) continue;
      if(g_patterns[i].traded && !g_patterns[i].executed) continue;   // skipped, not traded - SkipPattern() already removed its drawing; never redraw it
      DrawPattern(g_patterns[i]);
     }

   ObjectsDeleteAll(0, g_pz + "pend_");
   if(InpDrawPending)
      for(int i = 0; i < ArraySize(g_pending); i++)
         DrawPendingPattern(g_pending[i]);
  }
//+------------------------------------------------------------------+
//| Wallpaper/theme/watermark - ported verbatim from Aurelius_EA.mq5's    |
//| own shared-family idiom (see SESSION_NOTES.md on the visual-           |
//| standardization pass every other EA in this portfolio already got).     |
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
     { Print("RoundingBottom_EA BG: ObjectCreate failed, error ", GetLastError()); return; }

   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0, nm, OBJPROP_BMPFILE, 0, path);
   int err = GetLastError();

   if(!okSet || err != 0)
     {
      if(g_bgTries <= 3)
         PrintFormat("HeadShoulders_EA BG try %d: failed to load \"%s\"  set=%s  error=%d"
                     "  -> file must be at <data folder>\\MQL5\\Images\\%s",
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
   if(ObjectFind(0, g_pw + "wm") >= 0) ObjectDelete(0, g_pw + "wm");
   PWatermark();
   ChartRedraw(0);
  }
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
   //--- background/watermark are independent of the panel (InpShowPanel/
   //--- InpWatermark are separate inputs) - drawn BEFORE the panel's own
   //--- early-return, matching the fix Aurelius_EA.mq5/Vanguard_EA.mq5
   //--- already needed (nesting them after InpShowPanel's check silently
   //--- killed the watermark too whenever the panel was switched off).
   PBackground();
   PWatermark();
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
   int nConfirmed = 0, nExecuted = 0, nSkipped = 0;
   datetime lastBrk = 0; int lastIdx = -1;
   for(int i = 0; i < nPat; i++)
     {
      if(g_patterns[i].brk_i < 0) continue;
      nConfirmed++;
      if(g_patterns[i].traded)
        { if(g_patterns[i].executed) nExecuted++; else nSkipped++; }
      if(g_patterns[i].brk_t >= lastBrk) { lastBrk = g_patterns[i].brk_t; lastIdx = i; }
     }
   PSection("s2", x, ty, w, rh, "PATTERNS"); ty += rh + 6;                                        // GAP 3
   PRow("b0", x, ty, w, "confirmed", IntegerToString(nConfirmed), -1); ty += rh;
   PRow("b0b", x, ty, w, "traded / skipped", IntegerToString(nExecuted) + " / " + IntegerToString(nSkipped), -1); ty += rh;
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
   //--- v1.11: these run on EVERY tick, not inside the bar gate - see their own
   //--- comments. Retries go BEFORE the new-bar block so an older pattern still
   //--- owed its entry gets priority over a fresh trigger on the same tick.
   ResolveInflight();          // finding #6 - adopt a fill that followed an ambiguous send
   RetryTransientEntries();    // findings #1/#2/#9 - tick-level transient-entry retry
   if(IsNewBar())
     {
      //--- the full swing rescan (Recompute) is the expensive part - O(lookback)
      //--- pivot scan plus an ArrayResize per swing found, redone almost
      //--- identically every bar if run unthrottled. AdvancePending() (breakout
      //--- confirmation, O(1) per pending candidate) still runs every bar - only
      //--- the search for BRAND NEW pattern shapes is throttled, and a pattern
      //--- takes many dozens of bars to even form, so a few bars' detection lag
      //--- here is immaterial.
      //--- v1.11 finding #5: ...EXCEPT right after a (re)start, where the
      //--- throttle alone left the EA blind until the InpRecomputeEveryBars-th
      //--- new bar - up to 4 DAYS on D1 at the default 5. The first scan after
      //--- OnInit() now runs unconditionally (and stays forced until one
      //--- actually succeeds - history may not be loaded on the very first tick).
      g_barCounter++;
      if(g_forceRecompute || InpRecomputeEveryBars <= 1 || g_barCounter % InpRecomputeEveryBars == 0)
        {
         if(Recompute()) g_forceRecompute = false;
        }
      AdvancePending();
      CheckForEntry();
      ManageRunner();
      RefreshDrawings();
     }
   RunnerTick();               // finding #4 - tick-level re-try of a refused/clamped trail
   SyncPosition();
   //--- InpShowPanel dropped from this gate (v1.07) - DrawPanel() itself now
   //--- draws the wallpaper/watermark BEFORE its own internal InpShowPanel
   //--- check, so they must still be called even with the panel off, same
   //--- fix Aurelius_EA.mq5/Vanguard_EA.mq5 already needed for the same bug.
   if(!g_skipCosmeticDraws && TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      DrawPanel();
      ChartRedraw(0);
     }
  }
void OnTimer()
  {
   SyncPosition();
   //--- v1.11: same tick-level duties as OnTick(), so a quiet market (few ticks)
   //--- doesn't stall a retry/adoption/trail re-try. Live only - the timer is
   //--- not started in a non-visual Tester run (see OnInit()).
   ResolveInflight();
   RetryTransientEntries();
   RunnerTick();
   if(!g_skipCosmeticDraws && TimeCurrent() != g_lastPanelDraw)
     {
      g_lastPanelDraw = TimeCurrent();
      DrawPanel();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
//| Resize -> the wallpaper needs re-centring (same idiom as             |
//| Aurelius_EA.mq5's own resize handler). Guarded so it only fires on     |
//| an actual width/height change, not every scroll/pan tick (MT5 raises    |
//| CHARTEVENT_CHART_CHANGE for those too).                                  |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(g_skipCosmeticDraws) return;
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      static int lastW = -1, lastH = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lastW || nh != lastH)
        {
         lastW = nw; lastH = nh; g_bgOK = false; g_bgTries = 0; PBackground();
        }
     }
  }
//+------------------------------------------------------------------+
