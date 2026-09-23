//+------------------------------------------------------------------+
//|                         Ratchet_EA.mq5                           |
//|                                                                  |
//|  Renamed from Glint - the trailing stop that RATCHETS in behind  |
//|  price, locking in gains instead of waiting for a signal, is now |
//|  the system's defining mechanic, so the name follows it. Same    |
//|  chart palette as AuRebound/Slipstream/Tailwind (neon blue/white |
//|  candles, black background, green/red-pink exit labels) so all   |
//|  six systems read as one visual family.                          |
//|                                                                  |
//|  Short-hold scalp on Gold M5. Separate from Aurelius. This is a   |
//|  VOLUME strategy on purpose: many small trades, cut short fast,   |
//|  compounding into the result - not a few big ones.               |
//|                                                                  |
//|  Entry : 21>50>150>600 with price beyond the 2400, price dips    |
//|          to the 21 and closes back past it, the trigger candle   |
//|          closes with the trade, the 21 slopes with it, price is  |
//|          still inside the Bollinger band                         |
//|  Exit  : a 1.75 ATR stop, a TRAILING stop that ratchets in once   |
//|          0.5 ATR of profit is showing, a breakeven move at 0.3    |
//|          ATR, the stochastic level, or a bar limit                |
//|                                                                  |
//|  IMPORTANT - correction from an earlier version of this file:    |
//|  a real trade export from a live run of the matching indicator    |
//|  (Ratchet_Trades_GOLD.csv, Dec 2025-Aug 2026, 1,712 trades) came  |
//|  back well below what an earlier Python re-implementation had     |
//|  predicted (real PF 1.26 vs a claimed 1.69). Chasing that gap     |
//|  down found a genuine off-by-one-bar timing bug in the Python     |
//|  validation harness (NOT in this file): its stop/trail checks     |
//|  used the wrong bar, giving every trade one bar of unrealistic    |
//|  immunity from being stopped and letting the trail lag by a bar.  |
//|  Fixing that harness brought its numbers to within ~2% of the     |
//|  real export - and revealed that the 0.5 ATR "tight stop" this    |
//|  file previously shipped was actively fighting the trailing       |
//|  stop (cutting trades short before the trail could ever engage).  |
//|  A fresh sweep on the corrected harness found 1.75 ATR - close    |
//|  to the ORIGINAL pre-Glint stop distance - works far better once  |
//|  a trailing stop is also running.                                |
//|                                                                  |
//|  Re-derived on 100,013 M5 bars, spread deducted, next-bar-open    |
//|  fills, 70/30 chronological train/holdout, both splits agreeing:  |
//|     1.75 ATR stop + trail            : 2,613 trades  +2313        |
//|        75.5% win  PF 1.46  max drawdown 105                       |
//|     + breakeven + InpKLevel=95 + InpMaxConsecLosses=5       :      |
//|        2,802 trades  +2624  60.6% win  PF 1.70  max drawdown 101   |
//|     + InpMaxConsecLosses tightened 5->3 (THIS)              :      |
//|        2,703 trades  +2511  60.4% win  PF 1.69  max drawdown  84   |
//|        (maxDD -17% for -4% net, same PF/win rate, both splits      |
//|        agreeing - a real, near-free drawdown cut, so it is now the |
//|        default)                                                    |
//|                                                                  |
//|  The trailing stop is still the single biggest lever found this  |
//|  session on any of the three M5 systems - that conclusion holds.  |
//|  What changed is the initial stop distance it needs to work with. |
//|  A fixed take-profit target was tested and is a clean loser here, |
//|  always worse than letting the trail decide.                     |
//|                                                                  |
//|  ICT/SMC-style filters (Break of Structure, Fibonacci golden      |
//|  pocket, Fair Value Gaps, swing-based S/R, liquidity sweeps),      |
//|  RSI midline, a fresh-MA-cross trigger, VWAP/AVWAP, Supertrend,    |
//|  session kill-zones, and standard candlestick patterns were all   |
//|  tested too (before AND after the harness fix) and every one       |
//|  failed the train/holdout agreement bar for this system - not     |
//|  included. InpMaxDistATR stays available, off by default - a       |
//|  walk-forward audit (Opus review, v3.20) found it's not merely       |
//|  "trades less often": every value 1.0-2.5 ATR lost net on BOTH real    |
//|  splits AND on 6 quarters of unseen 2023-2024 data. Genuinely worse,   |
//|  not just a volume tradeoff - corrected from the original framing.     |
//|                                                                  |
//|  InpUseBreakeven (on by default) - moves the stop to entry once   |
//|  0.3 ATR shows, ahead of where the trail kicks in at 0.5 -         |
//|  costless, small clean win on both splits. InpUseWickReject (ON   |
//|  by default as of v3.21, was off) - requires the trigger candle's |
//|  wick into the 21 to dominate its body, a real rejection not just |
//|  a close-back. This paragraph's "trades far less often and net    |
//|  drops a lot, so opt-in" framing is the OLD read, from before the |
//|  give-back trail existed - every real MT5 confirmation this file  |
//|  has had since (v3.16 onward) was actually run with this ON, so   |
//|  false was never the validated config. See InpUseWickReject's own |
//|  input comment for the full story.                                |
//|                                                                  |
//|  Caution: the trail-distance sweep still kept "improving" with no |
//|  turnover down to unrealistically tight values even after the     |
//|  harness fix (the underlying limit is that a clean-bar backtest   |
//|  can't see intrabar noise, which the timing bug was separate      |
//|  from). The shipped trail (0.5 trigger / 0.3 distance) is the     |
//|  one actually validated against the real trade export above -     |
//|  don't push it tighter without demo-testing first.                |
//|                                                                  |
//|  InpUseMomentumEntry (OFF by default) - answers a real question:  |
//|  on a strong non-retracing trend the pullback entry (touch-and-   |
//|  reclaim the 21) never fires - price above the 21 the whole way   |
//|  just gets skipped. Measured: ~63% of fully-aligned-trend bars    |
//|  are skipped for exactly this reason. Momentum entry ADDS a       |
//|  second trigger alongside the pullback one (does not replace it): |
//|  fire the moment the full stack first aligns, no touch required,  |
//|  gated by InpMomentumRunBars (how many bars back must NOT have    |
//|  been aligned - avoids re-firing deep into an already-running     |
//|  trend). Tested against the shipped defaults above, incl. the     |
//|  tightened InpMaxConsecLosses=3 (InpMomentumRunBars=8, both        |
//|  splits agreeing):                                                 |
//|     pullback only (shipped)  : 2,703 trades  +2511  PF 1.69  maxDD  84 |
//|     + momentum entries (both): 3,146 trades  +2921  PF 1.67  maxDD 131 |
//|  +16% more trades and +16% more net for near-identical win rate   |
//|  and PF - but max drawdown rises ~56% (the tighter loss-breaker    |
//|  shrank the baseline drawdown a lot, so the extra momentum entries |
//|  now stand out more against it in percentage terms; the absolute   |
//|  size of what they add is similar to before). A real, not-free     |
//|  tradeoff, so it ships OFF by default like InpUseWickReject - turn |
//|  it on if you want the extra volume and can carry the larger       |
//|  drawdown.                                                         |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|  InpCloseBeforeBreak now ON by default (was off): Friday already  |
//|  force-flattened before the weekend close, but a position could   |
//|  sit open straight through the daily Mon-Thu settlement break -   |
//|  inconsistent, and not what "we should not be in a trade just     |
//|  before this" calls for. Now both closes flatten an open trade    |
//|  the same way. Note the hour-based inputs (InpFridayCloseHour,    |
//|  InpNoEntryAfterHourFri, InpCloseMinsBefore) all compare against  |
//|  broker SERVER time (TimeCurrent()), not SAST - check your        |
//|  terminal's server clock offset from SAST and set them to match.  |
//|  The daily-break detection itself (InpUseSessionCheck) reads the  |
//|  broker's own published session table, so it's timezone-correct   |
//|  automatically as long as your broker lists that break in the     |
//|  symbol's Sessions tab (Market Watch - Symbols - Sessions).       |
//|                                                                  |
//|  IMPORTANT - the first genuine MT5 Strategy Tester cross-check    |
//|  of this EA (real-tick execution, random execution delay, XM     |
//|  Global GOLD# M5, Jan-Aug 2026) came back meaningfully worse than |
//|  every prior check in this project: PF ~1.05 blended (vs ~1.65-   |
//|  1.70 modeled), and the second half of the period (forward test,  |
//|  Apr27-Aug22) was outright net-negative. This matters: every      |
//|  earlier "real" validation this session (the CSV exports from     |
//|  Ratchet_Signals.mq5) was a bar-close simulation over the chart's  |
//|  stored OHLC/spread data - close to this Python-style model, but  |
//|  NOT actual broker order execution. This Strategy Tester run is   |
//|  the first check against real tick-level fills, and its worse     |
//|  numbers should be trusted more than the earlier ones for what    |
//|  live trading costs actually look like.                           |
//|                                                                  |
//|  One concrete, fixable bug WAS found and fixed from it: TrailStop |
//|  sent trail/breakeven SL modifies with no check against the       |
//|  broker's minimum stop distance (SYMBOL_TRADE_STOPS_LEVEL /       |
//|  SYMBOL_TRADE_FREEZE_LEVEL) - about 1.85% of trades (20 of 1,079) |
//|  had a modify silently rejected ("Invalid stops") because the     |
//|  0.3 ATR trail distance was tighter than the broker allows during |
//|  low-volatility bars, leaving that position's stop un-tightened   |
//|  for that cycle. Now clamped to the broker's actual minimum       |
//|  distance instead of being sent blind. This alone does not        |
//|  explain the full gap above (too small a fraction of trades) -    |
//|  the bulk of it is real execution friction (tick-level fills,     |
//|  delay, imperfect - 63% - historical tick coverage) that no clean |
//|  bar-close model, this project's included, was ever measuring.    |
//|                                                                  |
//|  A second Strategy Tester run (InpTrailATR widened 0.3->0.5,       |
//|  99% real ticks this time) confirmed the picture rather than       |
//|  explaining it away: combined profit factor ~1.04, barely better   |
//|  than the ~1.05 before - the wider trail did not fix it. Both      |
//|  runs show the same pattern: real losses have a fat tail (worst    |
//|  losses roughly 2x the median), the signature of slippage/gaps     |
//|  carrying a fill past the intended stop, not the stop working as   |
//|  designed. InpMaxLossATR (new, default 2.5) is a second, looser    |
//|  backstop behind the broker-side stop for exactly that case - see  |
//|  TailLossHit(). This targets the fat tail specifically; it is NOT  |
//|  expected to turn this system profitable on its own - the honest   |
//|  read after two real tests is that this system's edge, once real   |
//|  execution costs are included, is roughly breakeven as currently   |
//|  built. Treat every profit-factor figure elsewhere in this file    |
//|  as an idealized, no-slippage upper bound, not a live expectation. |
//|                                                                  |
//|  PANEL/LOGGING FIXES (v3.14), same as Aurelius_EA.mq5 this session:|
//|   - Panel width self-learns from measured row text instead of a  |
//|     fixed InpPanelW, so a long value string can't clip past the  |
//|     frame anymore.                                                |
//|   - Panel text is deleted+recreated every draw cycle instead of  |
//|     updated in place - MT5 stacks chart objects by creation       |
//|     order, not ZORDER, so a trade arrow/line MT5 draws after the |
//|     panel already exists was rendering on top of it.              |
//|   - "today" was reading the WHOLE account's P&L change since day |
//|     start, silently including any other EA or manual trade       |
//|     sharing the account. Split into "today (mine)" and            |
//|     "today (other)". Also fixed: day-boundary tracking only ran   |
//|     inside DailyLossHit(), which returns immediately when         |
//|     InpMaxDailyLossPct is 0 (its default) - so "today" always      |
//|     read 0.00 for anyone on default settings.                     |
//|   - CSV export: added FILE_COMMON, without which a Strategy       |
//|     Tester run wrote the file into that run's own sandboxed agent |
//|     folder rather than somewhere you'd actually find it. Also: a  |
//|     broker-side stop-loss fill never went through this EA's own   |
//|     ClosePosition() call, so it was never logged AND never        |
//|     updated the cooldown timer or the consecutive-loss breaker    |
//|     either - roughly 1 in 6-7 real trades (the SL hits) were       |
//|     silently missing from the CSV. New OnTradeTransaction()        |
//|     handler catches exactly that case now.                        |
//|                                                                    |
//|  v3.15: this file never got the performance fixes its siblings     |
//|  (Aurelius/Fulcrum) already have - which is why real-tick          |
//|  backtests here were taking hours. Two compounding bugs, fixed:     |
//|  (1) EventSetTimer(1) ran unconditionally in OnInit, and Strategy   |
//|  Tester DOES simulate timer events regardless of visual mode - so    |
//|  OnTimer() was firing a full DrawPanel() once per simulated second    |
//|  for the ENTIRE backtest with no chart open to see it. Now gated       |
//|  behind a new g_skipCosmeticDraws flag (set once in OnInit from         |
//|  MQLInfoInteger(MQL_TESTER/MQL_VISUAL_MODE)), same as every sibling      |
//|  file; OnTimer() also early-returns as a defense-in-depth backstop;      |
//|  OnTick()'s own once-per-bar DrawPanel()/ChartRedraw() pair is now        |
//|  gated the same way. (2) MyRealizedPLToday() called HistorySelect()       |
//|  and re-scanned the WHOLE day's deal history from scratch on every         |
//|  call - and with bug (1) unfixed, that was up to once per simulated         |
//|  second too. On a multi-year real-tick run that's potentially hundreds       |
//|  of thousands of full-history rescans - almost certainly the dominant         |
//|  cost, on top of the timer itself. Fixed the same way Aurelius/Fulcrum         |
//|  already did: g_myRealizedToday is now an O(1) running total, updated           |
//|  incrementally in OnTradeTransaction() as each real close happens (a             |
//|  rare event, not a per-tick one) and reset daily in UpdateDayStamp().             |
//|  Also added the same HistoryDealSelect(ticket) call before reading                 |
//|  deal properties that Aurelius/Fulcrum already have - a just-added                  |
//|  deal isn't guaranteed to already be in the selected history window,                 |
//|  and reading an unselected ticket silently returns 0/empty, which                     |
//|  would have skipped both the new P&L accumulator and the                                |
//|  g_barsSinceClose cooldown reset. No trading-logic changes - every                        |
//|  fix here is either purely cosmetic-path gating or an O(1) rewrite of                      |
//|  a function that returns the exact same number as before, just without                      |
//|  re-deriving it from scratch every call.                                                      |
//|                                                                                                 |
//|  v3.16: at the user's request, a real strategy-improvement pass (not a                          |
//|  bug fix) - two real MT5 runs on shipped v3.15 defaults (backtest net                            |
//|  -100.82 PF 0.866, forward net +442.38 PF 1.267) plus their full trade                            |
//|  blotters were analyzed (Opus review). Central finding: 98.1% (BT) /                               |
//|  98.6% (FW) of ALL trades close via the broker-side SL order firing -                               |
//|  meaning essentially 100% of this system's real behavior is governed by                             |
//|  wherever the stop/trail/breakeven sits, not by the Stochastic signal                                |
//|  exit this file is themed around (fired 6/575 and 3/592 times), MAXBARS                              |
//|  (0/0 times - max hold observed was 50/51 bars against an 80-bar cap),                                |
//|  or TAILCAP (0/0 times - structurally unreachable, sitting 2.5 ATR behind                             |
//|  a 1.75 ATR stop). None of those three were touched - they were already                               |
//|  provably inert, changing them would have changed nothing. What WAS                                    |
//|  changed, both in the stop-management geometry the data says is actually                               |
//|  running this system:                                                                                   |
//|   - InpTrailATR (fixed 0.3 ATR distance behind current price) replaced                                  |
//|     with InpTrailKeepFrac (0.30): winners were realizing only ~49% of                                    |
//|     their own best favorable excursion before getting trailed out, and                                   |
//|     the old fixed 0.3 ATR distance was INSIDE ordinary M5 bar noise                                       |
//|     (99.7% of bars have more range than that) - so a still-developing                                     |
//|     trend was getting chopped by noise rather than ridden. The new rule                                   |
//|     scales the give-back with the size of the move instead of a flat                                      |
//|     distance: tighter than the old trail on a small move, much looser on                                   |
//|     a large one. See InpTrailKeepFrac's own comment for the full case and                                  |
//|     what real-tester confirmation this still needs.                                                        |
//|   - InpBreakevenBufferATR 0.0 -> 0.20: 21% (BT) / 13.5% (FW) of ALL                                         |
//|     trades - not just losers, trades that had moved a median 0.76-0.89                                     |
//|     ATR in profit first - finished within +/-$0.30 of exact breakeven,                                      |
//|     handing back the entire favorable move to a stop parked exactly at                                      |
//|     entry. A small buffer keeps a sliver of that instead. See its own                                        |
//|     comment for the real-tick clamping risk to watch for.                                                     |
//|  Explicitly NOT changed on this evidence: the entry gate (every filter                                        |
//|  dimension checked - EMA distance, slope, Bollinger position, Stochastic                                       |
//|  level, day-of-week, hour, long-vs-short - flipped sign between the                                             |
//|  backtest and forward halves, meaning any entry-side tightening would be                                        |
//|  overfitting to whichever half produced it); TrailStop()'s once-per-bar                                          |
//|  cadence (moving it to per-tick was checked and rejected - the once-per-                                         |
//|  bar gap turns out to be load-bearing for a trail this tight, and the                                             |
//|  real effect of tightening the cadence can't be determined from bar data                                          |
//|  at all, only from a real tester run, and only paired with a trail                                                 |
//|  distance safely outside one bar of noise). Also fixed two stale header                                            |
//|  comments claiming TailLossHit()/TrailStop() run "every tick" - they run                                            |
//|  once per bar, like everything else OnTick() manages (OnTick() returns                                              |
//|  immediately on a same-bar tick).                                                                                     |
//|                                                                                                                        |
//|  NONE OF THIS IS CONFIRMED YET. Every number above comes from a Python                                                |
//|  replay of two real MT5 trade blotters over real M5 bars (validated                                                   |
//|  within 5% against the actual forward result, but ~70 optimistic on the                                               |
//|  actual backtest result - real execution friction this replay doesn't                                                 |
//|  model). Needs the SAME real MT5 Strategy Tester run (99% real ticks,                                                  |
//|  same GOLD# M5 2024.08-2026.08 window, same Backtest/Forward split) as                                                 |
//|  the two runs this analysis is based on, before trusting the new                                                       |
//|  defaults over the old ones - and also caution: 1,167 real trades across                                                |
//|  two years of a single, historically extreme gold uptrend is a real but                                                 |
//|  narrow sample; a clean win here says "this geometry suits trending                                                     |
//|  gold", not "this is a validated edge".                                                                                  |
//|                                                                                                                            |
//|  Opus review of the above (before shipping) confirmed the core                                                             |
//|  mechanism correct (peak tracking, give-back arithmetic, monotonicity,                                                      |
//|  trail/breakeven interaction) and found six things, applied here: a                                                          |
//|  g_entryPrice<=0.0 guard in TrailStop() (a phantom-fill degenerate case                                                       |
//|  that could otherwise send a wildly wrong stop); InpTrailKeepFrac now                                                          |
//|  clamped to [0,1] locally (unlike this file's other ATR-multiplier                                                              |
//|  inputs, an out-of-range value here doesn't just get bigger/smaller, it                                                          |
//|  flips the trail's meaning entirely); the broker-minimum-distance clamp                                                          |
//|  is now unconditional instead of only applying when minDist>0.0 (closes                                                          |
//|  a path where an above-price stop could get sent, always rejected by the                                                          |
//|  broker in practice but no reason to allow it); the InpBreakevenBufferATR                                                          |
//|  comment now flags that the new 0.20 default sits 3x closer to price than                                                          |
//|  the old 0.0 default, more likely to hit the broker's freeze-level skip                                                            |
//|  (which silently skips ALL stop management that bar, not just the                                                                   |
//|  breakeven move) - worth watching in the tester journal; and a stale                                                                 |
//|  comment claiming the unconditional peak-tracking exists to survive                                                                   |
//|  InpUseTrail being "toggled mid-run" was corrected (MT5 re-inits on any                                                               |
//|  parameter change, so that can't actually happen - the real reason is so                                                              |
//|  the peak stays accurate on a bar where the modify itself gets skipped).                                                               |
//|  Also: Ratchet_Signals.mq5 (the bar-close validation harness that                                                                       |
//|  produces this file's own "real trade export" evidence) still had the                                                                   |
//|  OLD fixed-distance trail and OLD 0.0 breakeven buffer - silently                                                                        |
//|  modeling a different strategy than this file now runs. Ported the same                                                                  |
//|  two changes there (its own v3.12) so the two stay in sync.                                                                               |
//|                                                                                                                                            |
//|  v3.17: real MT5 Strategy Tester confirmation of the above (2024.08-                                                                        |
//|  2026.08 GOLD# M5, same Backtest/Forward split as every number cited                                                                         |
//|  above). InpTrailKeepFrac=0.30 CONFIRMED - a real, meaningful win on                                                                          |
//|  both splits: backtest net -100.82 -> +58.76 (PF 0.866 -> 1.084),                                                                              |
//|  forward net +442.38 -> +930.99 (PF 1.267 -> 1.600), avg win/avg loss                                                                          |
//|  both closer to parity, largest win roughly doubled on both splits -                                                                           |
//|  exactly the "let a developing trend breathe instead of getting                                                                                 |
//|  chopped by noise" mechanism this was built for. Real cost that came                                                                            |
//|  with it, worth knowing rather than hiding: avg hold time roughly                                                                                |
//|  doubled (21-25min -> 45-47min), and broken down by exit reason, trades                                                                          |
//|  that close via the plain SL order are now a NET LOSER as a group in                                                                             |
//|  both runs (-421.52 BT / -644.91 FW) - essentially all the net profit                                                                            |
//|  now comes from the ~6-9% of trades that reach a different exit                                                                                  |
//|  (session/Friday close, the Stochastic signal, or MAXBARS). Forward's                                                                            |
//|  equity drawdown also more than doubled (3.62% -> 7.86%) even though                                                                             |
//|  balance drawdown didn't - bigger floating swings before a trade                                                                                 |
//|  resolves, the real-money face of "more room to breathe". A more                                                                                 |
//|  concentrated, higher-swing system than before - keep this in mind.                                                                              |
//|                                                                                                                                                  |
//|  InpBreakevenBufferATR REVERTED 0.20 -> 0.0. Isolated with a second                                                                              |
//|  real run (same window/split, InpTrailKeepFrac=0.30 held constant,                                                                               |
//|  only the buffer changed): buffer=0.20 turned more trades into                                                                                    |
//|  technical wins (win rate 52.6%->65.0% BT, 58.4%->68.4% FW) by                                                                                    |
//|  shrinking the average win and growing the average loss - net profit                                                                              |
//|  DROPPED 66% on backtest (58.76 -> 17.23) and was flat on forward                                                                                  |
//|  (930.99 -> 943.33) with worse drawdown on both. Same shape of result                                                                              |
//|  as Aurelius_EA.mq5's own breakeven feature this session: better win                                                                              |
//|  rate, worse or flat bottom line. Reverted rather than shipped - see                                                                              |
//|  InpBreakevenBufferATR's own comment.                                                                                                             |
//|                                                                                                                                                    |
//|  v3.18: user asked what else could be tested to improve profit and cut                                                                             |
//|  drawdown given the v3.17 real numbers. Two candidates checked, Python-                                                                             |
//|  only (real trade entries + real M5 bars, both real Backtest/Forward                                                                                |
//|  sets), Opus unavailable for this round (session rate limit) so this is                                                                              |
//|  a Sonnet-only analysis, flagged as such - extra reason to insist on a                                                                                |
//|  real Strategy Tester run before trusting it, same as everything else                                                                                 |
//|  in this file that hasn't cleared one yet:                                                                                                             |
//|   - Capping the give-back trail's max distance (a InpTrailMaxGiveBackATR-                                                                              |
//|     style ceiling) - REJECTED. Swept 0.6-2.0 ATR x InpMaxBars 40/60/80                                                                                  |
//|     jointly: every cap cost real net on both splits (as steep as -177%                                                                                  |
//|     BT, -46% FW at the tightest), and drawdown did NOT reliably improve -                                                                               |
//|     it got WORSE than uncapped at several cap values on the backtest                                                                                    |
//|     split. Capping trades away the exact "let a developing trend                                                                                        |
//|     breathe" mechanism the whole point of v3.16 was to add. Separately                                                                                  |
//|     lowering InpMaxBars alone was also net-negative on both splits                                                                                      |
//|     without reliably improving drawdown either. Nothing changed here.                                                                                   |
//|   - Re-sweeping InpStopATR under the CURRENT trail (v3.16 never re-                                                                                     |
//|     tuned it) - ADOPTED, see InpStopATR's own comment: 1.35-1.65 is a                                                                                    |
//|     broad plateau that beats 1.75 on every measure on both splits;                                                                                      |
//|     1.40 won on both net and drawdown on both splits and held up across                                                                                 |
//|     chronological half-splits of each.                                                                                                                  |
//|                                                                                                                                                    |
//|  v3.19: v3.18's InpStopATR=1.40 REVERTED to 1.75, real testing overruled                                                                            |
//|  the Python-only sweep behind it. Two real Strategy Tester runs (2024.08-                                                                            |
//|  2026.08 GOLD# M5, same Backtest/Forward split) - first still carried a                                                                              |
//|  stale InpBreakevenBufferATR=0.2 from the saved .set file and looked                                                                                 |
//|  encouraging by coincidence; second, clean at the real shipped buffer=0.0,                                                                           |
//|  told the truth: 1.40 IS lower drawdown (BT -36%, FW -4%) but at a real                                                                              |
//|  net-profit cost bigger than the drawdown gain (BT -40%, FW -17.5%) - a                                                                              |
//|  genuine trade-off, not the free win the sweep predicted. Back to 1.75,                                                                              |
//|  the only value with two full real-tick confirmations. See InpStopATR's                                                                             |
//|  own comment for the real numbers.                                                                                                                   |
//|                                                                                                                                                    |
//|  v3.20: Opus walk-forward audit of the Bollinger/Stochastic filters and                                                                             |
//|  whether RSI is worth adding, at the user's request. Full findings in                                                                              |
//|  the session record; summary here.                                                                                                                   |
//|                                                                                                                                                    |
//|  CONFIG-INTEGRITY FLAG (highest-value finding, not a tuning result):                                                                                 |
//|  the real MT5 runs this file's own v3.16-v3.19 numbers are based on show                                                                            |
//|  signs of having run with InpUseWickReject=true (99.8% of real entries'                                                                             |
//|  wick/body ratio sits above the 1.5 threshold - not plausible by chance)                                                                            |
//|  despite the shipped default being false. Every "confirmed" figure in                                                                               |
//|  this header may describe a wick-reject-ON system, not the one that ships                                                                          |
//|  by default. Needs the actual .set file used for those runs checked                                                                                 |
//|  before trusting anything's default value against them - flagged to the                                                                            |
//|  user, not yet resolved either way.                                                                                                                  |
//|                                                                                                                                                    |
//|  High-confidence, no MT5 run needed: do NOT add RSI (every real entry's                                                                             |
//|  direction-adjusted RSI(14) falls in a narrow 53-76 band - the existing                                                                             |
//|  MA/slope/pullback gate already guarantees it, so an RSI filter would be                                                                            |
//|  a redundant copy of filters already in place, adding a new indicator                                                                               |
//|  for zero new information). Do NOT move Stochastic to be an entry filter                                                                            |
//|  (tested directly - actively harmful, removes exactly the trades that                                                                               |
//|  made the backtest period profitable while the forward period wants the                                                                             |
//|  opposite, the same cross-split sign-flip already documented elsewhere                                                                              |
//|  in this file). Current InpBBPeriod/InpBBDev/InpStochK-D-Slow-Meth-Price/                                                                           |
//|  InpKLevel are each already the best of everything tried against a fresh                                                                            |
//|  walk-forward - no change. InpMaxDistATR and InpMaxBars header comments                                                                             |
//|  corrected - see their own input comments.                                                                                                          |
//|                                                                                                                                                    |
//|  One low-confidence candidate NOT shipped: InpBBMaxPos 1.00->0.95 was the                                                                           |
//|  only change tested that didn't lose money in any of 3 time regimes, but                                                                            |
//|  a bootstrap check gives only 57-61% confidence on 2 of 3 regimes and a                                                                             |
//|  confidence interval spanning zero on the third - the same shape of weak                                                                            |
//|  signal that misled the v3.18 InpStopATR sweep. Not adopted. If ever          |
//|  tested for real: forward net must clear +1,000, backtest net must not        |
//|  drop below +58.76, and profit factor must rise on both splits - anything      |
//|  short of all three means it didn't survive real fills.                          |
//|                                                                                                                                                    |
//|  Meta-finding worth remembering for any future Python-based tuning of          |
//|  this file: profit is extremely concentrated (the top 10 trades were            |
//|  98-589% of total net across the periods checked) - a sweep on this              |
//|  system is largely measuring which few trades happened to survive, not            |
//|  a real edge. Treat any future single-split "wins on every measure" claim          |
//|  on this file with active suspicion until a real MT5 run says otherwise.             |
//|                                                                                                                                                    |
//|  v3.21: the v3.20 config-integrity flag resolved. The user checked their              |
//|  actual Strategy Tester setup and confirmed InpUseWickReject=true /                     |
//|  InpWickRejectRatio=1.5 - exactly what Opus inferred from the fill data.                 |
//|  InpUseWickReject default flipped false -> true to match: every real MT5                 |
//|  confirmation this file has had since the give-back trail (v3.16 onward)                  |
//|  was run with it on, so false was never actually the validated config -                    |
//|  true is. The old "trades far less often, net drops a lot, stays opt-in"                    |
//|  framing predates the give-back trail and was never re-verified against                     |
//|  it as an isolated on/off test - it's being kept as the default because it's                 |
//|  what every real number in this header already describes, not because it's                   |
//|  been freshly re-proven better in isolation. See InpUseWickReject's own                        |
//|  comment.                                                                                        |
//+------------------------------------------------------------------+
//|  v3.22: visual standardization pass across Aurelius_EA.mq5/Fulcrum_EA.mq5/ |
//|  Ratchet, all three sharing one account, so they should read as one          |
//|  product rather than three different panels (this file was carrying its       |
//|  own older "H4 family" palette, distinct from the other two). (1) Panel        |
//|  colours (InpPanelBg/InpHeaderBg/InpPanelEdge/InpSectionCol/InpTextCol/          |
//|  InpValCol/InpOkCol/InpNoCol) and chart colours (InpChartBg/InpBullCol/           |
//|  InpBearCol) now match Aurelius/Fulcrum exactly. (2) The 5 MAs were attached       |
//|  via ChartIndicatorAdd - full chart-history coverage for free, but an EA can't      |
//|  set a built-in indicator's PLOT_LINE_COLOR, so they rendered in MT5's own           |
//|  default colours, not this EA's palette. Switched to the same per-bar coloured        |
//|  trend-segment drawing Aurelius/Fulcrum already use (new InpCol21/50/150/600/          |
//|  2400 + InpMAHistoryBars=2500, ~8.7 days), so all three EAs' MAs now look identical.     |
//|  This file's own Bollinger Bands (a real, load-bearing exit filter, not decoration)       |
//|  get the same treatment (InpShowBB/InpColBB) - previously not drawn on the chart at all.   |
//|  Stochastic is an oscillator, not a price series, so it can't use the same trick -          |
//|  attached instead via ChartIndicatorAdd into its own subwindow (native colours,               |
//|  acceptable there since a subwindow is already visually separate from the panel/               |
//|  candle/MA scheme). (3) PRect never reclaimed top-of-stack (fine when this file drew           |
//|  no chart objects of its own - now that it draws MA/BB trend segments, a bug: a new              |
//|  segment could bury the panel). Fixed the same way this whole codebase already treats             |
//|  PText - unconditional delete-and-recreate every cycle except the draggable "bg" - plus            |
//|  a new "fl" opaque fill (Fulcrum's own trick) so the row background actually stays solid.            |
//|  (4) Same PRect border-rendering quirk as Aurelius/Fulcrum (only 2 of 4 sides actually                |
//|  drawn) - same explicit 4-strip PFrame() fix. Position (12/30) and the "today (mine)"/                 |
//|  "today (other)" P&L split were already consistent with the other two. No trading-logic                 |
//|  changes.                                                                                                  |
//+------------------------------------------------------------------+
//|  v3.23: same holiday-session-gap fix as Daybreak_EA.mq5 v1.11-1.12/Zenith_EA.mq5/ |
//|  Aurelius_EA.mq5 v1.40/Fulcrum_EA.mq5 v2.06, confirmed live in real Strategy         |
//|  Tester data and found by code inspection to apply identically here:                   |
//|  FridayCutoff(false) (the weekend flatten) only ran once per new bar, so a               |
//|  holiday leaving zero ticks/bars near the Friday cutoff hour meant it never                |
//|  fired at all, and nothing then existed to catch a stale position over the                   |
//|  following weekend either. Added WeekendStillOpen() (deadline-based - true once                |
//|  now is past the most recent Friday InpFridayCloseHour:00 AND the position opened                |
//|  before it, regardless of which day the first tick back lands on) and                              |
//|  HasOwnPosition(), called every tick at the top of OnTick, ahead of the new-bar                       |
//|  gate - closes on literally the first tick available after any gap. The old bar-                       |
//|  gated FridayCutoff(false) call site removed (now dead weight, always beaten by                          |
//|  the tick-level check). Also added IsMarketHoliday() (New Year's/MLK/Presidents/                           |
//|  Good Friday/Memorial/Juneteenth/Independence/Labor/Thanksgiving/Christmas, every                            |
//|  date computed from the year - no hardcoded table, no yearly maintenance) and                                  |
//|  blocked new entries on a flagged holiday the same place/way as the existing Friday                              |
//|  no-entry rule. The daily settlement-break flatten (NearSessionClose/InpCloseBeforeBreak)                          |
//|  is untouched - still bar-gated, but a missed daily-break gap is minutes, not days,                                  |
//|  so it wasn't the risk this fix targets.                                                                                |
//+------------------------------------------------------------------+
//|  v3.24: real GOLD# M5 price data (2023-2026) shows this broker's server        |
//|  clock follows EU DST dates while gold's true session timing follows US          |
//|  DST dates - confirmed directly from the daily first-bar-of-day time, which        |
//|  shifts by exactly 60 minutes on the Monday after each transition, twice a           |
//|  year, every year, no exceptions. During the ~2-week March gap and ~1-week             |
//|  Oct/Nov gap this creates, InpFridayCloseHour and InpNoEntryAfterHourFri read            |
//|  1 server-clock hour off from the true session boundary. Added                            |
//|  DSTGapHourAdjustment() (returns -1 during a gap week, 0 otherwise, computed                |
//|  from the permanent US/EU DST transition rules - no hardcoded dates, no                      |
//|  yearly maintenance, same principle as IsMarketHoliday) and applied it to both                 |
//|  hour thresholds. The daily settlement-break flatten (NearSessionClose, which                    |
//|  reads the broker's own live session table via SymbolInfoSessionTrade rather than                 |
//|  a fixed hour) is unaffected either way.                                                             |
//+------------------------------------------------------------------+
//|  v3.25: pre-live risk-sizing pass. This file only ever supported a fixed         |
//|  InpLots - fine when it was tuned, but gold's ATR has moved roughly 5-6x            |
//|  since 2023 while InpLots never did, so a fixed lot now risks far more per            |
//|  trade in dollar terms than it did historically. Added the same InpLotMode/             |
//|  InpRiskPct LOT_RISK_PCT option Aurelius_EA.mq5 already had (LotSize() sizes               |
//|  to InpRiskPct% of balance against the actual stop distance instead of a flat                |
//|  lot count) - LOT_FIXED stays the default, so nothing changes unless it's                       |
//|  deliberately switched on. No signal/entry-logic changes.                                          |
//+------------------------------------------------------------------+
//|  v3.26: Opus review found NthWeekdayOfMonth/LastWeekdayOfMonth built their |
//|  date at 12:00 noon, not midnight, so the "+86400 -> Monday" arithmetic in    |
//|  DSTGapHourAdjustment() landed each DST-gap boundary at Monday 12:00 rather     |
//|  than Monday 00:00 - harmless at this file's shipped hour thresholds (all       |
//|  above noon) but would silently mis-adjust any lower hour on the 4 transition    |
//|  Mondays/year. Changed both helpers to build at 00:00. No other logic changed.    |
//+------------------------------------------------------------------+
//|  v3.27 (2026-09-06): indicator-visibility pass, from the Opus deep-dive review's |
//|  third ask ("whatever indicators the EA's use ... i want to see them on the       |
//|  charts"). That review rated this file the most complete of the gold trio - it     |
//|  already draws its 5 MAs, both Bollinger Bands and a Stochastic subwindow - and     |
//|  found one clear gap plus one cosmetic loose end. Nothing here changes a decision;   |
//|  it only draws what the existing code already computes:                              |
//|  (1) The 21-EMA touch band. Touched21() requires a wick into InpTouchATR x ATR of    |
//|  the 21 EMA, and that is this system's single highest-frequency entry trigger -      |
//|  yet the trigger ZONE had no visible form at all, only the 21 itself. Now drawn as   |
//|  a dotted InpColTouch envelope at m21 +/- InpTouchATR * ATR through the same         |
//|  DrawMASegment()/PurgeOldMALines() machinery the MAs and BBs already use             |
//|  (DrawMASegment gained an optional `style` argument, defaulting to STYLE_SOLID, so   |
//|  every pre-existing call is unchanged), and mirrored in BackfillMALines() so a       |
//|  fresh attach shows the whole rolling window rather than a 2-bar stub. The band's    |
//|  half-width at bar s is read from hATR at bar s (MA(hATR, s, ...) - the same handle  |
//|  Touched21() itself reads), not from one current ATR smeared across 2500 bars, so    |
//|  the drawn zone is the zone that was actually being tested on that bar.              |
//|  (2) The Bollinger MIDDLE band (hBB buffer 0) - available from the same handle       |
//|  already open for the upper/lower bands, and without it the "bands" render as two    |
//|  unrelated lines rather than one envelope around its basis. Drawn in a dimmed        |
//|  InpColBBMid under the existing InpShowBB toggle (it is part of the same indicator,  |
//|  not a separate one, so it deliberately did not get an input of its own).            |
//|  No new object prefix was needed: both additions are per-bar OBJ_TREND segments      |
//|  that belong to RATEM_ and want exactly the same rolling purge, which OnDeinit       |
//|  already sweeps. Every new object is OBJPROP_HIDDEN and every new draw sits inside   |
//|  the existing g_skipCosmeticDraws gate, so a non-visual Strategy Tester pass does    |
//|  none of it. No signal, entry, exit, sizing or risk-management logic touched.        |
//+------------------------------------------------------------------+
//|  v3.28 (2026-09-16): InpUseMomentumEntry default false -> true, at the user's       |
//|  request for a real test of the one candidate this file still had sitting            |
//|  Python-only (see its own v-numbered header paragraph above for the full case         |
//|  and mechanism). Found and fixed a real bug while touching it: the input's own         |
//|  inline tooltip said "+17% trades, +19% net, same PF, +17% maxDD", but the SAME          |
//|  header's own absolute numbers (2,703->3,146 trades, +2511->+2921 net, maxDD           |
//|  84->131) work out to +16% / +16% / +56% - the tooltip understated the real             |
//|  modeled drawdown cost by more than 3x and was the only place most people would          |
//|  actually see this trade-off (the Inputs tab shows the inline comment, not the            |
//|  full file header). Corrected to match the header's own numbers. Nothing about             |
//|  the entry/exit logic itself changed - FreshAligned()/the OnTick() trigger check              |
//|  were already fully wired in, just shipping off. IMPORTANT: this file's own v3.18-              |
//|  v3.20 meta-finding is that Python-only results have repeatedly NOT survived real                |
//|  MT5 fills here (profit is extremely concentrated in a handful of trades, and this                |
//|  file's real execution gap has been larger than every sibling EA's) - so turning this              |
//|  on is shipping it FOR that real test, not because it's already trusted. Needs a real                |
//|  Strategy Tester run before this default should be trusted over false.                                |
//+------------------------------------------------------------------+
#property copyright "Ratchet EA"
#property version   "3.28"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

enum ENUM_LOTMODE{ LOT_FIXED = 0, LOT_RISK_PCT = 1 };

input group "=== Position sizing ==="
input ENUM_LOTMODE InpLotMode = LOT_FIXED;  // How the size is decided
input double InpLots         = 0.01;       // Fixed lot size
input double InpRiskPct      = 1.0;        // Risk per trade (% of balance) - needs a stop
input double InpMaxLots      = 1.0;        // Hard cap on size

input group "=== Moving averages ==="
input int    InpP21   = 21;                // MA 21 period
input int    InpP50   = 50;                // MA 50 period
input int    InpP150  = 150;               // MA 150 period (M15)
input int    InpP600  = 600;               // MA 600 period (H1)
input int    InpP2400 = 2400;              // MA 2400 period (H4)

input group "=== Entry ==="
input double InpTouchATR   = 0.20;         // How close to the 21 counts as a touch (x ATR)
input int    InpTouchBars  = 4;            // Bars to look back for that touch
input bool   InpNeedCandle = true;         // Trigger candle must close in the trade direction
input bool   InpNeedSlope  = true;         // The 21 must be sloping with the trade
input double InpMinSlope   = 0.05;         // Minimum 21 slope (x ATR per bar)
input bool   InpUseBands   = true;         // Block entries already outside the Bollinger band
input int    InpBBPeriod   = 20;           // Bollinger period
input double InpBBDev      = 2.0;          // Bollinger deviations
input double InpBBMaxPos   = 1.00;         // Max band position at entry
input double InpMaxDistATR = 0.0;          // Max distance from the 21 at entry (x ATR, 0 = off)  [tested: real, but trades LESS often - off by default]
input bool   InpUseWickReject = true;      // Require the trigger candle's wick into the 21 to dominate its body (a real rejection)
                                            // [changed from false, v3.21: every real MT5 confirmation this file's
                                            // header cites (v3.16 onward - the give-back trail, the stop-distance
                                            // work, all of it) was actually run with this on, per the user's own
                                            // Strategy Tester screenshot and independently confirmed by Opus from
                                            // the fill data itself (99.8% of real entries clear this ratio, not
                                            // plausible by chance). The shipped default of false was NEVER the
                                            // config under real test this whole time - true is. Old "off by
                                            // default" framing predates the give-back trail and was never
                                            // re-verified against it; flipped to match validated reality instead.]
input double InpWickRejectRatio = 1.5;     // Wick must be at least this many times the body  [tested: real edge -
                                            // PF 1.69->2.26, maxDD -59% - but trades LESS than half as often, an
                                            // old finding from before the give-back trail existed. Now the default,
                                            // see InpUseWickReject's own comment - not re-verified against the
                                            // CURRENT trail as an isolated on/off test, only confirmed as "this is
                                            // what every real run already had turned on".]
input bool   InpUseMomentumEntry = true;   // ALSO fire on fresh full-stack alignment, no pullback required  [v3.28: Python-only so far (+16% trades, +16% net, same PF, +56% maxDD - the old inline comment here said +17% maxDD, which was stale/wrong against the header's own absolute numbers; corrected). Turned ON as the shipped default specifically so the next real MT5 Strategy Tester run tests it - this file's own header meta-finding is that Python-only results here have repeatedly NOT held up against real fills, so this needs a real confirmation before trusting it, same as every other unconfirmed number in this file. See header.]
input int    InpMomentumRunBars  = 8;      // Bars back that must NOT have been aligned, for a momentum entry to count as "fresh"
input int    InpCooldown   = 1;            // Bars to wait after an exit

input group "=== Loss control ==="
input int    InpMaxConsecLosses     = 3;   // Pause new entries after this many losses in a row (0 = off)  [tested: tightened from 5->3, cuts maxDD another 17% for -4% net, same PF - both splits agree, see header]
input int    InpBreakerCooldownBars = 24;  // Bars to sit out once the pause triggers

input group "=== Exit ==="
input int    InpStochK     = 5;            // Stochastic %K period
input int    InpStochSlow  = 3;            // %K smoothing
input int    InpStochD     = 3;            // %D period
input ENUM_MA_METHOD   InpStochMeth  = MODE_SMA;    // Stochastic method
input ENUM_STO_PRICE   InpStochPrice = STO_LOWHIGH; // Stochastic price mode
input bool   InpUseSignal  = true;         // Read the signal line, not the main line
input double InpKLevel     = 95.0;         // Exit level (100-x is used for sells)  [tested best now the trail does most of the work]
input bool   InpUseStop    = true;         // Attach a stop at the broker
input double InpStopATR    = 1.75;         // Stop distance (x ATR at entry)  [v3.18 tried 1.40, a Python-only
                                            // sweep suggested it won on both net AND drawdown on both real splits -
                                            // REVERTED after real testing showed that was wrong: two real Strategy
                                            // Tester runs (2024.08-2026.08 GOLD# M5, same Backtest/Forward split,
                                            // one contaminated by a stale InpBreakevenBufferATR=0.2 that looked
                                            // encouraging, one clean at the real shipped buffer=0.0 that told the
                                            // truth) showed 1.40 IS lower drawdown (BT -36%, FW -4%) but at a real
                                            // net-profit cost bigger than the drawdown gain (BT -40%, FW -17.5%) -
                                            // a genuine risk/reward trade-off, not the free win the Python sweep
                                            // predicted. Back to 1.75, the only value with two full real-tick
                                            // confirmations (v3.17: BT net +58.76 PF 1.084, FW net +930.99 PF
                                            // 1.600). 1.40 remains available if lower drawdown is ever preferred
                                            // over the extra profit - see the git history for the real numbers.
input bool   InpUseTrail   = true;         // Trail the stop once the trade is in profit  [the single biggest lever tested this session]
input double InpTrailTriggerATR = 0.5;     // Profit needed before the trail starts (x ATR)
input double InpTrailKeepFrac = 0.30;      // Give-back trail: once triggered, lock in this fraction of the BEST
                                            // favorable move seen so far (not a fixed ATR distance behind current
                                            // price - see TrailStop()). Replaces the old InpTrailATR fixed-distance
                                            // trail: real trade data (Opus review, v3.16) showed that trail parking
                                            // the stop a fixed 0.3 ATR behind price was inside normal M5 bar noise
                                            // (99.7% of bars exceed 0.3 ATR of range) and was capping winners at
                                            // ~49% of their own peak - this scales the give-back with how far the
                                            // trade has actually run, so a small move keeps a tight leash (tighter
                                            // than the old fixed trail early) while a large move gets much more
                                            // room to keep developing. Python replay of both real MT5 test periods
                                            // (2024.08-2026.08, GOLD# M5) improved net/PF on both halves at every
                                            // value tried from 0.25-0.35 - 0.30 was the middle of that range, NOT
                                            // yet confirmed by a real Strategy Tester run - sweep this in the
                                            // tester before trusting the exact number, same discipline as every
                                            // other untested default in this file.
input bool   InpUseBreakeven = true;       // Move the stop to entry once InpBreakevenTriggerATR of profit shows  [tested: costless, small clean win on both splits]
input double InpBreakevenTriggerATR = 0.3; // Profit needed before the breakeven move (x ATR) - fires BEFORE the trail
input double InpBreakevenBufferATR  = 0.0;  // Buffer past entry (x ATR, 0 = exact breakeven)  [tried 0.20 in v3.16
                                            // (Opus review reasoned it should help, since 21% (BT) / 13.5% (FW) of
                                            // ALL trades were finishing within +/-$0.30 of exact breakeven after
                                            // moving favorably first) - REVERTED after two real Strategy Tester
                                            // runs (2024.08-2026.08 GOLD# M5, same Backtest/Forward split, with
                                            // InpTrailKeepFrac=0.30 held constant) both came back negative-to-flat:
                                            // buffer=0.20 turned more trades into technical wins (win rate 52.6%->
                                            // 65.0% BT, 58.4%->68.4% FW) by shrinking the average win and growing
                                            // the average loss - net profit dropped 66% on backtest (58.76->17.23)
                                            // and was flat on forward (930.99->943.33) with worse drawdown on both.
                                            // Same shape of result as Aurelius_EA.mq5's own breakeven feature this
                                            // session: better win rate, worse or flat bottom line. Back to 0.0.
input int    InpMaxBars    = 80;           // Bar limit on any trade  [reaches ~2-3% of trades under the v3.16
                                            // give-back trail (corrected, v3.20 - previously documented as
                                            // "rarely reached"/"structurally unreachable", which was true of the
                                            // OLD fixed-distance trail but not this one) - and per a walk-forward
                                            // exit-reason breakdown, that ~2-3% of trades reaching this cap carries
                                            // the MAJORITY of this system's real net profit. Not dead weight.]

input group "=== Safety ==="
input int    InpMagic           = 750005;  // Magic number
input int    InpMaxSpreadPoints = 60;      // Skip entries above this spread (0 = off)
input int    InpSlippage        = 20;      // Max deviation (points)
input double InpMaxDailyLossPct = 0.0;     // Stop trading after this daily loss % (0 = off)
input double InpMaxLossATR      = 2.5;     // Tail-loss safety net: force-close if floating loss exceeds this many ATR (0 = off)  [added after a real Strategy Tester run showed a fat loss tail beyond what InpStopATR should ever produce - see header]
input string InpComment         = "Ratchet"; // Order comment

input group "=== Session protection ==="
input bool   InpUseSessionCheck   = true;  // Respect the symbol's trading session
input int    InpNoEntryMinsBefore = 30;    // No new entries within N min of session close
input bool   InpCloseBeforeBreak  = true;  // Flatten before the daily break too  [now on by default - Friday already worked this way, the daily Mon-Thu break didn't, see header]
input int    InpCloseMinsBefore   = 5;     // Flatten N min before session close
input bool   InpCloseOnFriday     = true;  // Flatten before the weekend
input int    InpFridayCloseHour   = 22;    // Server hour to flatten on Friday
input int    InpNoEntryAfterHourFri = 20;  // No new entries after this hour on Friday

input group "=== Dashboard ==="
input bool   InpShowPanel  = true;                // Show the panel
input int    InpPanelDrag  = 1;                   // 0 = locked, 1 = draggable
input int    InpPanelX     = 12;                  // X offset
input int    InpPanelY     = 30;                  // Y offset
input bool   InpPanelBottom= false;               // Anchor to the bottom
input int    InpPanelW     = 260;                 // Width
// Unified across Aurelius/Fulcrum/Ratchet - one shared visual standard, not
// three different palettes ("H4 family" vs the newer Aurelius/Fulcrum one) -
// so all three read as one product when run together on the same account.
input color  InpPanelBg    = C'13,17,28';         // Panel background - matches Aurelius/Fulcrum
input color  InpHeaderBg   = C'28,36,58';         // Header band
input color  InpPanelEdge  = C'0,150,255';        // Border - neon blue, matches Aurelius/Fulcrum
input color  InpTitleCol   = C'0,150,255';        // Title - neon blue
input color  InpSectionCol = C'214,226,238';      // Section headings
input color  InpTextCol    = C'150,166,192';      // Labels
input color  InpValCol     = C'236,242,252';      // Values
input color  InpOkCol      = C'0,230,118';        // Met - neon green
input color  InpNoCol      = C'255,61,90';        // Not met - hot red
input color  InpShadowCol  = C'6,8,14';           // Drop shadow
input string InpPanelFont  = "Consolas";          // Font
input int    InpPanelSize  = 8;                   // Font size

input group "=== Chart theme and background ==="
input bool   InpApplyTheme = true;                // Recolour the chart
input bool   InpShowMAs    = true;                // Draw the moving averages
input bool   InpShowBB     = true;                // Draw the Bollinger Bands this EA's exit already reads
input int    InpMAHistoryBars = 2500;             // How many recent bars of MA/BB line history to keep drawn
                                                   // (bounded, so a long-running live EA doesn't accumulate
                                                   // objects forever - 2500 M5 bars is ~8.7 days, comfortably
                                                   // spanning a normal chart view, not the old 300-bar/~25h stub)
input color  InpCol21      = clrYellow;           // MA 21 line colour
input color  InpCol50      = C'255,140,0';        // MA 50 line colour - neon orange
input color  InpCol150     = C'191,0,255';        // MA 150 line colour - neon purple
input color  InpCol600     = C'255,20,147';       // MA 600 line colour - neon pink
input color  InpCol2400    = C'57,255,20';        // MA 2400 line colour - neon green
input color  InpColBB      = C'80,180,220';       // Bollinger Band colour - steel blue, distinct from the MAs
//--- v3.27 indicator-visibility inputs. Both cosmetic: nothing below is read by
//--- any entry, exit, sizing or risk decision, and every draw they gate sits
//--- behind g_skipCosmeticDraws exactly like the MA/BB lines above.
input bool   InpShowTouchBand = true;             // Draw the InpTouchATR envelope around the 21 EMA - the
                                                   // actual zone Touched21() tests a wick against, and this
                                                   // EA's highest-frequency entry trigger. The 21 itself was
                                                   // already drawn; the tolerance around it was not
input color  InpColTouch   = C'128,128,0';        // Touch-band colour - InpCol21's yellow at ~half brightness,
                                                   // so the band reads as a zone belonging to the 21 rather
                                                   // than as a sixth MA (drawn STYLE_DOT too)
input color  InpColBBMid   = C'40,90,110';        // Bollinger MIDDLE band (hBB buffer 0) - InpColBB dimmed,
                                                   // drawn under the same InpShowBB toggle since it is part
                                                   // of the same indicator, not a separate one. Without it
                                                   // the upper/lower pair reads as two unrelated lines
                                                   // instead of one envelope around its own basis
input color  InpChartBg    = clrBlack;            // Chart background - matches Aurelius/Fulcrum
input color  InpBullCol    = C'0,150,255';        // Bullish candle - neon blue, same as Aurelius/Fulcrum
input color  InpBearCol    = clrWhite;            // Bearish candle - neon white, same as Aurelius/Fulcrum
input string InpBackgroundBMP = "Ratchet_Wallpaper.bmp"; // Background image (.bmp in MQL5\\Images)
input int    InpBgWidth    = 1290;                // Image width (for centring)
input int    InpBgHeight   = 720;                 // Image height (for centring)
input string InpWatermark  = "RATCHET";           // Watermark text
input bool   InpWaterBottom= true;                // Watermark bottom-right
input color  InpWaterCol   = C'46,38,24';         // Watermark colour - matches the H4 family
input int    InpWaterSize  = 42;                  // Watermark font size
input string InpWaterFont  = "Arial Black";       // Watermark font

input group "=== Logging ==="
input bool   InpLogTrades  = true;         // Write closed trades to CSV
input bool   InpVerbose    = false;        // Print skipped entries to the log

//------------------------------- globals ----------------------------
CTrade        trade;
CPositionInfo pos;

int h21=INVALID_HANDLE, h50=INVALID_HANDLE, h150=INVALID_HANDLE;
int h600=INVALID_HANDLE, h2400=INVALID_HANDLE, hATR=INVALID_HANDLE;
int hSto=INVALID_HANDLE, hBB=INVALID_HANDLE;

datetime g_lastBar = 0;
int      g_barsSinceClose = 9999;
datetime g_lastClose = 0;
int      g_entryBarCount  = 0;
int      g_fh = INVALID_HANDLE;
double   g_dayStartEquity = 0.0;
int      g_dayStamp = -1;
datetime g_entryTime = 0;
double   g_entryPrice = 0.0, g_entryLots = 0.0, g_entryATR = 0.0;
double   g_peakFavPx = 0.0;   // best price seen in the trade's favor - see TrailStop()/InpTrailKeepFrac
int      g_entryDir = 0;
ulong    g_ticket = 0;
string   g_pp = "RATEP_";
string   g_pw = "RATEW_";
string   g_pm = "RATEM_";    // per-bar MA/BB line segments, purged to a rolling window - see UpdateMALines
int      g_panX = -1, g_panY = -1;
// 2026-09-06 (Opus deep-dive review): this file never got the
// g_panelReclaim mechanism the rest of the portfolio uses (Aurelius v1.38,
// then Fulcrum/Zenith/Daybreak/AuRebound/Tailwind/Slipstream) - PRect/PText
// below unconditionally deleted and recreated every object on EVERY call,
// including from OnTimer's once-per-second refresh, which is exactly the
// "visibly flashes/repaints on every live-number refresh" regression that
// mechanism exists to prevent (roughly 3 rects + 3 text objects x 33 rows
// torn down and rebuilt every second on any live/demo/visual-mode chart).
// See PRect/PText's own comments below for the gating logic.
bool     g_panelReclaim = true;
bool     g_bgOK = false;
int      g_bgTries = 0;
int      g_consecLosses = 0;
int      g_breakerBarsLeft = 0;
int      g_blkSpread = 0, g_blkDist = 0, g_blkBreaker = 0, g_blkWick = 0;
double   g_lastMoved = 0.0;
string   g_lastReason = "";
double   g_myRealizedToday = 0.0;
//--- PERFORMANCE FIX: true when running a non-visual Strategy Tester pass
//--- (no chart anyone is watching) - set once in OnInit(). Gates the timer
//--- and the per-bar panel redraw, both purely cosmetic and with zero
//--- effect on any trading decision. See OnInit/OnTimer/OnTick for why
//--- this mattered - this file never had it, unlike its siblings
//--- (Aurelius/Fulcrum already got this fix), which is why
//--- backtests here were taking hours: EventSetTimer(1) ran unconditionally,
//--- and Strategy Tester DOES simulate timer events regardless of visual
//--- mode, so OnTimer() was firing a full DrawPanel() once per simulated
//--- second for the entire backtest with nobody able to see it.
bool     g_skipCosmeticDraws = false;

#define NEED_BARS 60
void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim);
void CurrentPositions(bool &haveLong, bool &haveShort);
bool MA(const int handle, const int shift, double &out);   // OnInit's position-state restore (2026-09-06) needs this
void PTheme();
void AttachMAs();
void PBackground();
void PWatermark();
void UpdateMALines();
void BackfillMALines();

//+------------------------------------------------------------------+
int OnInit()
  {
   //--- PERFORMANCE FIX: see g_skipCosmeticDraws declaration.
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   h21   = iMA(_Symbol, PERIOD_CURRENT, InpP21,   0, MODE_EMA, PRICE_CLOSE);
   h50   = iMA(_Symbol, PERIOD_CURRENT, InpP50,   0, MODE_EMA, PRICE_CLOSE);
   h150  = iMA(_Symbol, PERIOD_CURRENT, InpP150,  0, MODE_EMA, PRICE_CLOSE);
   h600  = iMA(_Symbol, PERIOD_CURRENT, InpP600,  0, MODE_SMA, PRICE_CLOSE);
   h2400 = iMA(_Symbol, PERIOD_CURRENT, InpP2400, 0, MODE_EMA, PRICE_CLOSE);
   hATR  = iATR(_Symbol, PERIOD_CURRENT, 14);
   hSto  = iStochastic(_Symbol, PERIOD_CURRENT, InpStochK, InpStochD,
                       InpStochSlow, InpStochMeth, InpStochPrice);
   hBB   = iBands(_Symbol, PERIOD_CURRENT, MathMax(2,InpBBPeriod), 0,
                  InpBBDev, PRICE_CLOSE);
   if(h21==INVALID_HANDLE || h50==INVALID_HANDLE || h150==INVALID_HANDLE ||
      h600==INVALID_HANDLE || h2400==INVALID_HANDLE || hATR==INVALID_HANDLE ||
      hSto==INVALID_HANDLE || hBB==INVALID_HANDLE)
     { Print("Ratchet EA: handle creation failed, error ", GetLastError());
       return(INIT_FAILED); }

   // 2026-09-06 (Opus deep-dive review): a terminal restart, recompile, or
   // input change while a position is open resets every g_entry*/g_ticket
   // global to its 0/0.0 initializer (MQL5 re-runs OnInit() in all three
   // cases) - none of which happens mid-Strategy-Tester-run, which is why
   // this was never caught in a backtest. Concrete consequences without
   // this restore: the weekend/holiday flatten (WeekendStillOpen) fails
   // its own `g_entryTime > 0` guard and goes dead for the rest of that
   // trade (the exact exposure item 1's original fix exists to prevent);
   // TrailStop()/InpUseTrail (on by default here, unlike Aurelius/Fulcrum)
   // stays disabled via its own g_entryATR<=0 guard; TailLossHit() and the
   // panel/CSV all read stale zeros until the trade closes.
   if(PositionsTotal() > 0)
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
         double atrNow;
         g_entryATR    = MA(hATR, 1, atrNow) ? atrNow : 0.0;   // atr<=0 (cold read) leaves trail/breakeven disabled, not armed on bad data
         PrintFormat("Ratchet EA: restored open position #%I64u from OnInit (entry %.2f, %s, %.2f lots)",
                     g_ticket, g_entryPrice, (g_entryDir>0?"BUY":"SELL"), g_entryLots);
         break;
        }
     }

   if(Period() != PERIOD_M5)
      Print("WARNING: tested on M5. Current timeframe is ",
            EnumToString((ENUM_TIMEFRAMES)Period()));

   g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   //--- PERFORMANCE FIX: not started at all in a non-visual Tester run -
   //--- Strategy Tester still simulates timer events regardless of OnTick
   //--- throttling, so this was firing a full DrawPanel() once per
   //--- simulated second for the entire backtest with no chart open to see
   //--- it. OnTimer() also early-returns as a defense-in-depth backstop.
   if(!g_skipCosmeticDraws) EventSetTimer(1);
   PTheme();
   if(!g_skipCosmeticDraws)
     {
      AttachMAs(); BackfillMALines();
      // 2026-09-06 (Opus deep-dive review): every other EA in the portfolio
      // draws the panel immediately in OnInit rather than depending on the
      // 1-second EventSetTimer to show something first - Ratchet was the
      // one file still left on the timer-only path, a sub-second gap
      // between attach and first paint rather than the Fulcrum-class
      // missing-panel-at-attach bug, but worth closing for consistency.
      bool hl, hs; CurrentPositions(hl, hs); DrawPanel(hl, hs);
      ChartRedraw(0);
     }
   PrintFormat("Ratchet EA started. Magic %d  lots %.2f  bars %d (need %d)",
               InpMagic, InpLots, Bars(_Symbol, PERIOD_CURRENT), InpP2400 + NEED_BARS);
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
   Comment("");
  }
//+------------------------------------------------------------------+
//| Catches closes ClosePosition() never sees: a broker-side stop-loss|
//| fill happens on the broker's own server, not through this EA's    |
//| own trade.PositionClose() call, so nothing in OnTick() ever ran    |
//| LogClosed() - OR the consecutive-loss breaker / cooldown reset -   |
//| for it. Roughly 1 in 6-7 real trades (the SL hits) were silently   |
//| missing from the CSV, and both InpCooldownBars and the loss-streak |
//| breaker were not being tracked correctly after one either, since   |
//| none of that state got updated the way ClosePosition() already     |
//| does for its own closes. This handles exactly the SL-hit case and  |
//| only that case: an EA-initiated close already gets logged AND       |
//| updates this same state inline via ClosePosition(), and that       |
//| always carries DEAL_REASON_EXPERT, not DEAL_REASON_SL - so          |
//| filtering on SL specifically here means every close is handled      |
//| exactly once, from exactly one place, never both.                  |
//+------------------------------------------------------------------+
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
   //--- 0/empty on an unselected ticket, which would silently skip the
   //--- P/L accumulator below AND the g_barsSinceClose reset further down -
   //--- Aurelius_EA.mq5/Fulcrum_EA.mq5 already had this fix; Ratchet never did).
   if(!HistoryDealSelect(ticket)) return;
   if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) return;
   if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;

   //--- every real close (SL or EA-initiated) reaches here exactly once -
   //--- accumulate this EA's own realized P&L incrementally, same fix as
   //--- Aurelius_EA.mq5/Fulcrum_EA.mq5, instead of MyRealizedPLToday()
   //--- re-scanning the whole day's deal history on every panel draw. This
   //--- must happen BEFORE the DEAL_REASON_SL filter below, since an
   //--- EA-initiated close (DEAL_REASON_EXPERT) still needs to be counted
   //--- here even though its OWN SL-hit-specific logic (LogClosed etc.,
   //--- already handled inline by ClosePosition()) is skipped.
   g_myRealizedToday += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                       + HistoryDealGetDouble(ticket, DEAL_SWAP)
                       + HistoryDealGetDouble(ticket, DEAL_COMMISSION);

   if((ENUM_DEAL_REASON)HistoryDealGetInteger(ticket, DEAL_REASON) != DEAL_REASON_SL) return;
   double exitPx = HistoryDealGetDouble(ticket, DEAL_PRICE);
   LogClosed("SL", exitPx);
   // 2026-09-06 (Opus deep-dive review): this used to classify win/loss by
   // raw PRICE movement ((exitPx-g_entryPrice)*g_entryDir >= 0.0), not real
   // P&L - a trade that moved a few cents in its favor but lost money after
   // spread/commission/swap counted as a "win" and wrongly reset the
   // loss-streak counter. The real deal P&L is already fetched above for
   // g_myRealizedToday - reuse it here instead of re-deriving from price.
   double dealPL = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                 + HistoryDealGetDouble(ticket, DEAL_SWAP)
                 + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   g_lastMoved = dealPL; g_lastReason = "SL";
   if(dealPL >= 0.0) g_consecLosses = 0;
   else
     {
      g_consecLosses++;
      if(InpMaxConsecLosses > 0 && g_consecLosses >= InpMaxConsecLosses)
        { g_breakerBarsLeft = InpBreakerCooldownBars; g_consecLosses = 0; }
     }
   g_lastClose = TimeCurrent();
   g_barsSinceClose = 0;
   g_ticket = 0;
  }
//+------------------------------------------------------------------+
//| Buffer helpers. Shift 1 is the last CLOSED bar, matching the      |
//| backtest. Nothing reads the forming bar.                          |
//+------------------------------------------------------------------+
bool BufVal(const int handle, const int idx, const int shift, double &out)
  {
   double b[];
   ArraySetAsSeries(b, true);
   if(CopyBuffer(handle, idx, shift, 1, b) < 1) return(false);
   out = b[0];
   return(true);
  }
bool MA(const int handle, const int shift, double &out)
  { return(BufVal(handle, 0, shift, out)); }
//+------------------------------------------------------------------+
bool MAs(const int shift, double &m21, double &m50, double &m150,
         double &m600, double &m2400, double &atr)
  {
   return(MA(h21,shift,m21) && MA(h50,shift,m50) && MA(h150,shift,m150) &&
          MA(h600,shift,m600) && MA(h2400,shift,m2400) && MA(hATR,shift,atr));
  }
//+------------------------------------------------------------------+
bool Aligned(const int shift, const bool isBuy)
  {
   double m21,m50,m150,m600,m2400,atr;
   if(!MAs(shift,m21,m50,m150,m600,m2400,atr)) return(false);
   double c = iClose(_Symbol, PERIOD_CURRENT, shift);
   if(c <= 0.0) return(false);
   if(isBuy)
      return(c > m2400 && m21 > m50 && m50 > m150 && m150 > m600);
   return(c < m2400 && m21 < m50 && m50 < m150 && m150 < m600);
  }
//+------------------------------------------------------------------+
bool Touched21(const bool isBuy)
  {
   double m21, atr;
   if(!MA(h21,1,m21) || !MA(hATR,1,atr) || atr <= 0.0) return(false);
   double c = iClose(_Symbol, PERIOD_CURRENT, 1);
   if(isBuy  && c <= m21) return(false);
   if(!isBuy && c >= m21) return(false);
   for(int j = 1; j <= InpTouchBars; j++)
     {
      double mj;
      if(!MA(h21,j,mj)) return(false);
      double tol = atr * InpTouchATR;
      if(isBuy  && iLow(_Symbol, PERIOD_CURRENT, j)  <= mj + tol) return(true);
      if(!isBuy && iHigh(_Symbol, PERIOD_CURRENT, j) >= mj - tol) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
//| Momentum entry (InpUseMomentumEntry): the given shift is aligned  |
//| AND the alignment is fresh - InpMomentumRunBars further back the   |
//| stack was NOT aligned this direction. Catches a runaway trend the |
//| moment it first stacks up, with no pullback required.             |
//+------------------------------------------------------------------+
bool FreshAligned(const int shift, const bool isBuy)
  {
   if(!Aligned(shift, isBuy)) return(false);
   return(!Aligned(shift + InpMomentumRunBars, isBuy));
  }
//+------------------------------------------------------------------+
double BandPos(const bool isBuy)
  {
   double up, lo;
   if(!BufVal(hBB,1,1,up) || !BufVal(hBB,2,1,lo)) return(-1.0);
   if(up - lo <= 0.0) return(-1.0);
   double p = (iClose(_Symbol, PERIOD_CURRENT, 1) - lo) / (up - lo);
   return(isBuy ? p : 1.0 - p);
  }
//+------------------------------------------------------------------+
double StoVal(const int shift)
  {
   double v;
   if(!BufVal(hSto, (InpUseSignal ? 1 : 0), shift, v)) return(-1.0);
   return(v);
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
void PRect(const string id, const int x, const int y, const int w, const int h,
           const color bg, const color edge, const int border = 1)
  {
   string nm = g_pp + id;
   //--- only the draggable background keeps its object identity across
   //--- draws (recreating it would break an in-progress drag) - everything
   //--- else is deleted and recreated only when g_panelReclaim is set (once
   //--- per new bar, when a new MA/BB line segment was actually drawn - see
   //--- UpdateMALines), same as PText below, so a chart object drawn since
   //--- the last cycle can never end up stacked above the panel and show
   //--- through it. Every other call (OnTimer's once-per-second refresh,
   //--- the drag handler) just updates the existing object's properties in
   //--- place instead of tearing it down - see g_panelReclaim's own comment
   //--- for why churning this every draw call caused visible flashing.
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
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);       // in front of candles
   //--- only the background is grabbable, and it must not be HIDDEN or
   //--- MT5 will not let it be selected, which is what blocked dragging
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, grab);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, !grab);
   //--- ZORDER affects click priority, not visual stacking (see the note
   //--- in PText) - set high anyway in case a future build changes that,
   //--- but the actual fix for the panel showing through trade arrows is
   //--- the g_panelReclaim-gated delete-and-recreate above/in PText, not this.
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5000);
  }
//+------------------------------------------------------------------+
//| PRect's own OBJ_RECTANGLE_LABEL border (BORDER_FLAT + OBJPROP_COLOR) |
//| renders unreliably in this terminal build - observed live as only     |
//| two of the four sides actually drawn (top + one side), bottom and      |
//| the other side missing. Rather than depend on that object's built-in    |
//| border at all, this draws an explicit 4-strip frame - one thin filled     |
//| rectangle per edge - which is immune to the quirk since each strip is       |
//| just an ordinary solid-filled OBJ_RECTANGLE_LABEL, the one thing that        |
//| already renders correctly. Call this INSTEAD of relying on PRect's own        |
//| border for anything the user actually needs to see as a complete outline.      |
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
   //--- an OBJ_LABEL with empty text renders MT5's default "Label"
   if(txt == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   //--- MT5 stacks chart objects by CREATION order, not by ZORDER (per the
   //--- note further down) - a trade arrow/line MT5 draws natively when an
   //--- order fills is created AFTER the panel already exists, so left
   //--- alone it renders on top and the text shows through it. Deleting
   //--- and recreating this text object (instead of just updating it in
   //--- place) makes it the newest object on the chart again - but that's
   //--- only actually needed once per new bar (when a new MA/BB line
   //--- segment was just drawn), gated by g_panelReclaim; see its own
   //--- comment for why churning this every draw call (e.g. OnTimer's
   //--- once-per-second refresh) caused visible flashing. The frame rects
   //--- (PRect) get the identical gated treatment; only the draggable
   //--- background rect is fully exempt, since it needs to keep its object
   //--- identity or an in-progress drag gets reset mid-motion.
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
//+------------------------------------------------------------------+
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
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Centred watermark. Drawn BEHIND the candles so it never obscures   |
//| price - it tints the empty space instead.                          |
//+------------------------------------------------------------------+
//| Centred watermark. Drawn BEHIND the candles so it never obscures   |
//| price - it tints the empty space instead.                          |
//+------------------------------------------------------------------+
//| Stochastic is an oscillator (0-100), not a price series - it can't  |
//| be drawn on the main price panel the way the MAs/BB are (their       |
//| values ARE prices; Stochastic's aren't). ChartIndicatorAdd into its   |
//| own subwindow is the correct, low-risk way to show it: an EA has no    |
//| plot buffers of its own, so this is native MT5 rendering with the       |
//| indicator's own default colours (an EA cannot set PLOT_LINE_COLOR on     |
//| a built-in indicator it didn't author) - acceptable here since an        |
//| oscillator subwindow is already visually separate from the panel/         |
//| candle/MA colour scheme, unlike an MA line drawn directly on price.        |
//| The 21/50/150/600/2400 MAs and the Bollinger Bands, by contrast, DO get     |
//| this EA's own custom colours - see UpdateMALines()/BackfillMALines()         |
//| below, same drawing convention as Aurelius_EA.mq5/Fulcrum_EA.mq5.              |
//+------------------------------------------------------------------+
void AttachMAs()
  {
   if(ChartIndicatorsTotal(0, 1) > 0) return;   // subwindow 1 already has something - already attached
   ChartIndicatorAdd(0, 1, hSto);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Each MA/BB line drawn as its own coloured trend segment, one new    |
//| bar[shift2]->bar[shift1] segment per new bar - same idiom as          |
//| Aurelius_EA.mq5/Fulcrum_EA.mq5's UpdateMALines/DrawMASegment, ported    |
//| here verbatim so all three EAs render their charts identically.         |
//+------------------------------------------------------------------+
//| v3.27: `style` added (default STYLE_SOLID, so every existing call     |
//| below is byte-for-byte unchanged) purely so the 21-EMA touch band can  |
//| be drawn dotted through this same function - the band is a trigger     |
//| zone, not an indicator line, and must not read as a sixth MA.          |
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
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);      // keep it out of the Object List/dialog
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
void UpdateMALines()
  {
   if(!InpShowMAs && !InpShowBB && !InpShowTouchBand) return;
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, 2);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(tA == 0 || tB == 0) return;
   if(InpShowMAs)
     {
      double m21a, m21b, m50a, m50b, m150a, m150b, m600a, m600b, m2400a, m2400b;
      if(MA(h21,2,m21a)   && MA(h21,1,m21b))   DrawMASegment("21",   tA, m21a,   tB, m21b,   InpCol21);
      if(MA(h50,2,m50a)   && MA(h50,1,m50b))   DrawMASegment("50",   tA, m50a,   tB, m50b,   InpCol50);
      if(MA(h150,2,m150a) && MA(h150,1,m150b)) DrawMASegment("150",  tA, m150a,  tB, m150b,  InpCol150);
      if(MA(h600,2,m600a) && MA(h600,1,m600b)) DrawMASegment("600",  tA, m600a,  tB, m600b,  InpCol600);
      if(MA(h2400,2,m2400a) && MA(h2400,1,m2400b)) DrawMASegment("2400", tA, m2400a, tB, m2400b, InpCol2400);
     }
   if(InpShowBB)
     {
      double bua, bub, bla, blb;
      if(BufVal(hBB,1,2,bua) && BufVal(hBB,1,1,bub)) DrawMASegment("bbu", tA, bua, tB, bub, InpColBB);
      if(BufVal(hBB,2,2,bla) && BufVal(hBB,2,1,blb)) DrawMASegment("bbl", tA, bla, tB, blb, InpColBB);
      //--- v3.27: the middle band (buffer 0), from the same hBB handle already
      //--- open for the two above. Dimmed rather than InpColBB so the outer
      //--- pair still reads as "the bands" and this reads as their basis.
      double bma, bmb;
      if(BufVal(hBB,0,2,bma) && BufVal(hBB,0,1,bmb)) DrawMASegment("bbm", tA, bma, tB, bmb, InpColBBMid);
     }
   //--- v3.27: the 21-EMA touch band - Touched21()'s InpTouchATR x ATR
   //--- tolerance, i.e. the actual zone a wick has to reach for this EA's
   //--- most-fired entry trigger. Drawn from the same h21/hATR handles
   //--- Touched21() itself reads, so it is the tested zone, not a look-alike.
   if(InpShowTouchBand)
     {
      double t21a, t21b, atrA, atrB;
      if(MA(h21,2,t21a) && MA(h21,1,t21b) &&
         MA(hATR,2,atrA) && MA(hATR,1,atrB) && atrA > 0.0 && atrB > 0.0)
        {
         //--- each endpoint gets its OWN bar's ATR (Touched21 evaluates with
         //--- the then-current shift-1 ATR), so consecutive segments join
         //--- continuously instead of stepping as volatility drifts.
         double tolA = atrA * InpTouchATR, tolB = atrB * InpTouchATR;
         DrawMASegment("t21hi", tA, t21a + tolA, tB, t21b + tolB, InpColTouch, STYLE_DOT);
         DrawMASegment("t21lo", tA, t21a - tolA, tB, t21b - tolB, InpColTouch, STYLE_DOT);
        }
     }
   PurgeOldMALines(tB);
  }
//+------------------------------------------------------------------+
//| UpdateMALines() only ever draws ONE new bar's worth of segment per   |
//| call, so a fresh attach would show a single 1-bar stub per line and    |
//| take InpMAHistoryBars bars to fill the window it claims to show -        |
//| called once from OnInit instead, this walks backward and draws the        |
//| whole rolling window immediately. Same shift-1-minimum, no-lookahead       |
//| indexing as UpdateMALines - never touches bar 0.                             |
//+------------------------------------------------------------------+
void BackfillMALines()
  {
   if(!InpShowMAs && !InpShowBB && !InpShowTouchBand) return;
   int avail = Bars(_Symbol, PERIOD_CURRENT) - 2;
   int n = MathMin(InpMAHistoryBars, avail);
   double a, b;
   for(int s = n; s >= 1; s--)
     {
      datetime tA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
      datetime tB = iTime(_Symbol, PERIOD_CURRENT, s);
      if(tA == 0 || tB == 0) continue;
      if(InpShowMAs)
        {
         if(MA(h21,  s+1,a) && MA(h21,  s,b)) DrawMASegment("21",  tA,a,tB,b,InpCol21);
         if(MA(h50,  s+1,a) && MA(h50,  s,b)) DrawMASegment("50",  tA,a,tB,b,InpCol50);
         if(MA(h150, s+1,a) && MA(h150, s,b)) DrawMASegment("150", tA,a,tB,b,InpCol150);
         if(MA(h600, s+1,a) && MA(h600, s,b)) DrawMASegment("600", tA,a,tB,b,InpCol600);
         if(MA(h2400,s+1,a) && MA(h2400,s,b)) DrawMASegment("2400",tA,a,tB,b,InpCol2400);
        }
      if(InpShowBB)
        {
         if(BufVal(hBB,1,s+1,a) && BufVal(hBB,1,s,b)) DrawMASegment("bbu", tA,a,tB,b,InpColBB);
         if(BufVal(hBB,2,s+1,a) && BufVal(hBB,2,s,b)) DrawMASegment("bbl", tA,a,tB,b,InpColBB);
         //--- v3.27: middle band, mirroring UpdateMALines' own new draw
         if(BufVal(hBB,0,s+1,a) && BufVal(hBB,0,s,b)) DrawMASegment("bbm", tA,a,tB,b,InpColBBMid);
        }
      //--- v3.27: the 21-EMA touch band, mirroring UpdateMALines so a fresh
      //--- attach shows the whole trigger zone rather than a 2-bar stub. The
      //--- half-width at each end is that bar's OWN hATR reading - the same
      //--- handle Touched21() reads - not one current ATR smeared across the
      //--- whole 2500-bar window, which would draw a zone that never existed.
      if(InpShowTouchBand)
        {
         double e21a, e21b, atrA, atrB;
         if(MA(h21,s+1,e21a) && MA(h21,s,e21b) &&
            MA(hATR,s+1,atrA) && MA(hATR,s,atrB) && atrA > 0.0 && atrB > 0.0)
           {
            double tolA = atrA * InpTouchATR, tolB = atrB * InpTouchATR;
            DrawMASegment("t21hi", tA, e21a + tolA, tB, e21b + tolB, InpColTouch, STYLE_DOT);
            DrawMASegment("t21lo", tA, e21a - tolA, tB, e21b - tolB, InpColTouch, STYLE_DOT);
           }
        }
     }
  }
//+------------------------------------------------------------------+
//| An EA has no plot buffers, so the averages it calculates are      |
//| invisible by default. ChartIndicatorAdd attaches the existing     |
//| handles to the chart as real indicator lines - no object overhead |
//| and they scroll and scale with price properly.                    |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Minutes until this symbol's trading session closes.               |
//| Returns -1 when the session cannot be read, which is treated as   |
//| "no restriction" rather than blocking everything.                 |
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
   // (not deleted) since forEntry=true above still needs this function.
   // See WeekendStillOpen's own header for why the close side needed a
   // real fix and the entry side didn't.
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
//| which day of the week the first tick back happens to land on. Called         |
//| every tick, ahead of OnTick's new-bar gate - see its call site.                |
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
//| open - a cheap existence check used to gate the tick-level              |
//| WeekendStillOpen call so it isn't evaluated on every tick when flat.     |
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
//--- PERFORMANCE FIX: this used to call HistorySelect() and re-scan every
//--- deal in the day's history on every call - and it was being called
//--- from the panel refresh path, which (via the timer bug just fixed in
//--- OnInit) was running up to once per simulated second. On a real-tick
//--- backtest that's potentially hundreds of thousands of full-history
//--- rescans over a multi-year run - almost certainly the dominant cause
//--- of the reported multi-hour runtime, on top of the timer itself
//--- (same class of bug Aurelius/Fulcrum already found and fixed in their
//--- own panel P&L). g_myRealizedToday is now an O(1) running total,
//--- updated incrementally in OnTradeTransaction() as each real close
//--- happens (a rare event, not a per-tick one) and reset daily in
//--- UpdateDayStamp() above - this function is now just a lookup.
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
//--- same LOT_RISK_PCT sizing as Aurelius_EA.mq5's LotSize() - gold's ATR
//--- (and therefore this system's own stop distance in price terms) has
//--- moved roughly 5-6x since 2023 while InpLots stayed fixed, so a fixed
//--- lot size now risks far more per trade than it did when this system
//--- was last validated against its early history. LOT_FIXED (the
//--- existing default) is unchanged for anyone not opting in.
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
      string fn = "Ratchet_EA_" + _Symbol + "_" + (string)InpMagic + ".csv";
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
      PrintFormat("Ratchet EA: CSV export -> %s\\Files\\%s",
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
void ClosePosition(const string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      double px = pos.PriceCurrent();
      // 2026-09-06 (Opus deep-dive review): captured BEFORE the close, same
      // reasoning as the OnTradeTransaction fix above - floating P&L
      // (profit+swap) is the real outcome, not raw price movement, which
      // could classify a small-but-losing-after-spread trade as a "win"
      // and wrongly reset the loss-streak counter. Commission isn't
      // visible on POSITION_* properties (it's a deal-level field), but is
      // already folded into g_myRealizedToday via OnTradeTransaction's own
      // deal read - this dealPL is for streak classification only.
      double dealPL = pos.Profit() + pos.Swap();
      if(trade.PositionClose(pos.Ticket()))
        {
         if(InpVerbose) Print("Closed: ", reason);
         LogClosed(reason, px);
         g_lastMoved = dealPL; g_lastReason = reason;
         if(dealPL >= 0.0) g_consecLosses = 0;
         else
           {
            g_consecLosses++;
            if(InpMaxConsecLosses > 0 && g_consecLosses >= InpMaxConsecLosses)
              { g_breakerBarsLeft = InpBreakerCooldownBars; g_consecLosses = 0; }
           }
         g_lastClose = TimeCurrent();
         g_barsSinceClose = 0;
         g_ticket = 0;
        }
      else
         Print("Close failed: ", trade.ResultRetcodeDescription());
     }
  }
//+------------------------------------------------------------------+
//| Ratchets the stop in once the trade has moved InpTrailTriggerATR  |
//| in its favour, then (v3.16) locks in InpTrailKeepFrac of the best  |
//| favorable excursion seen so far - never loosens. Tested as the      |
//| single biggest lever on this system: the ORIGINAL fixed-distance     |
//| version of this is what took the win rate from 16.6% to 45.3% by      |
//| locking in a partial win on trades that used to round-trip into a      |
//| loss; see InpTrailKeepFrac's own comment for why the fixed-distance     |
//| version was replaced.                                                    |
//+------------------------------------------------------------------+
//| Tail-loss safety net (InpMaxLossATR). A SECOND, looser backstop    |
//| behind the broker-side stop order - checked once per bar, same as  |
//| TrailStop() (OnTick() returns immediately on a same-bar tick, see  |
//| its own comment - this does NOT run every tick despite the claim   |
//| this comment block used to make; corrected here). Added after a    |
//| real MT5 Strategy Tester run (real-tick fills,                     |
//| random execution delay) showed a fat tail in real losses - the     |
//| worst losses ran to roughly 2x the median, well beyond what a      |
//| cleanly-executing InpStopATR=1.75 stop should ever produce on its  |
//| own. That pattern is the signature of slippage/gaps carrying a     |
//| fill past the intended stop level, not the stop working as         |
//| designed. Deliberately looser than InpStopATR (default 2.5 vs      |
//| 1.75) so it never fires on a stop that's executing normally - only |
//| on genuine overshoot. Cannot make a trade worse - it only ever     |
//| tightens the worst case.                                           |
//+------------------------------------------------------------------+
bool TailLossHit()
  {
   if(InpMaxLossATR <= 0.0 || g_entryATR <= 0.0) return(false);
   // 2026-09-06 (Opus deep-dive review): this used to `return` inside the
   // loop on the first matching position regardless of the adverse-move
   // check's result, so any position after it (if the one-at-a-time
   // invariant this file otherwise enforces ever changed) would never be
   // evaluated. Correct under today's design (only one position ever
   // exists), but the wrong keyword for a loop written to iterate - fixed
   // to `continue` so the intent matches what the code actually does.
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      bool isLong = (pos.PositionType() == POSITION_TYPE_BUY);
      double cur = isLong ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                           : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double adverse = isLong ? (g_entryPrice - cur) : (cur - g_entryPrice);
      if(adverse >= InpMaxLossATR * g_entryATR) return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
void TrailStop()
  {
   //--- g_entryPrice<=0.0 is a degenerate case (trade.Buy/Sell returned
   //--- true but ResultPrice() came back 0, e.g. accepted-but-not-yet-
   //--- filled) - without this guard, fav/peakFav below would be computed
   //--- from a phantom entry near price 0, which for a long can pass every
   //--- gate and (if InpUseStop is off, so curSl==0.0 never blocks it) send
   //--- a stop near ~InpTrailKeepFrac of the raw GOLD price. Opus review
   //--- found this while verifying the v3.16 give-back trail.
   if(g_entryATR <= 0.0 || g_entryPrice <= 0.0) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;
      bool isLong = (pos.PositionType() == POSITION_TYPE_BUY);
      double cur   = isLong ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                             : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double fav   = isLong ? (cur - g_entryPrice) : (g_entryPrice - cur);
      double curSl = pos.StopLoss();
      double bestSl = curSl;
      bool have = false;

      //--- track the best price this trade has ever seen in its favor -
      //--- updated unconditionally (not gated on InpUseTrail) so it stays
      //--- accurate even on a bar where the modify further down gets
      //--- skipped by the freeze-level/better-check continues, not just
      //--- when a modify actually goes out. (MT5 can't toggle an input
      //--- mid-run anyway - a parameter change re-runs OnInit and this
      //--- global gets reset with everything else - so that's not the
      //--- reason this needs to be unconditional; this is.)
      if(isLong) { if(cur > g_peakFavPx) g_peakFavPx = cur; }
      else       { if(cur < g_peakFavPx) g_peakFavPx = cur; }

      //--- trail: locks in InpTrailKeepFrac of the peak favorable move,
      //--- not a fixed distance behind current price - see its own input
      //--- comment for why. Still monotonic (the "better" check below is
      //--- unchanged) and still gated by InpTrailTriggerATR. Clamped to
      //--- [0,1] here - unlike this file's other ATR-multiplier inputs,
      //--- a KeepFrac outside that range doesn't just get bigger/smaller,
      //--- it flips from "trail behind price" to "target above price for
      //--- a long" (>1) or "no-op, always beaten by breakeven" (<0), which
      //--- Opus review flagged as a real correctness boundary worth a
      //--- guard rather than trusting the input like everything else here.
      if(InpUseTrail && fav >= InpTrailTriggerATR * g_entryATR)
        {
         double keep = MathMax(0.0, MathMin(1.0, InpTrailKeepFrac));
         double peakFav = isLong ? (g_peakFavPx - g_entryPrice) : (g_entryPrice - g_peakFavPx);
         double cand = isLong ? g_entryPrice + keep * peakFav
                               : g_entryPrice - keep * peakFav;
         if(!have || (isLong ? cand > bestSl : cand < bestSl)) { bestSl = cand; have = true; }
        }
      //--- breakeven: one-time move to entry (+/- buffer), triggers ahead of
      //--- the trail so it protects the early part of a move the trail
      //--- doesn't reach yet
      if(InpUseBreakeven && fav >= InpBreakevenTriggerATR * g_entryATR)
        {
         double cand = isLong ? g_entryPrice + InpBreakevenBufferATR * g_entryATR
                               : g_entryPrice - InpBreakevenBufferATR * g_entryATR;
         if(!have || (isLong ? cand > bestSl : cand < bestSl)) { bestSl = cand; have = true; }
        }
      if(!have) continue;

      //--- clamp to the broker's minimum stop distance - found via a real
      //--- Strategy Tester run that a chunk of trail/breakeven modifies
      //--- were being silently rejected ("Invalid stops") because the
      //--- ATR-based trail distance can be tighter than what the broker
      //--- allows, especially in low-volatility bars. Sending a clamped,
      //--- still-favorable value beats sending one guaranteed to fail.
      long stopsLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      long freezeLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
      double minDist = MathMax(stopsLevelPts, freezeLevelPts) * _Point;
      //--- unconditional (not just "if minDist>0.0"): with InpTrailKeepFrac
      //--- possible to misconfigure toward >1.0 (see its own guard above),
      //--- or on a broker reporting 0 for both levels, bestSl could
      //--- otherwise land ON THE WRONG SIDE of cur (above price for a long)
      //--- and get sent to the broker anyway - always rejected in practice
      //--- (a self-limiting failure, not a loss-causing one - it just means
      //--- the stop doesn't move that bar) but there's no reason to allow
      //--- it when a same-cost floor call removes the possibility entirely.
      //--- Opus review flagged this while verifying the v3.16 give-back
      //--- trail; the underlying clamp itself predates this file's own
      //--- InpMaxLossATR-tail-loss investigation this session.
      bestSl = isLong ? MathMin(bestSl, cur - MathMax(minDist, _Point))
                       : MathMax(bestSl, cur + MathMax(minDist, _Point));
      //--- freeze level also blocks modifying a stop already this close to
      //--- price, regardless of the new value - skip the request entirely
      //--- rather than send one certain to be rejected. When it does, this
      //--- skips ALL stop management for that bar, trail included, not
      //--- just the breakeven move - relevant if InpBreakevenBufferATR is
      //--- ever raised again (tried at 0.20 in v3.16, reverted to 0.0
      //--- after real testing - see its own input comment), since a
      //--- smaller buffer means the breakeven stop lands closer to price
      //--- and is more likely to hit this.
      if(freezeLevelPts > 0 && curSl != 0.0 &&
         MathAbs(cur - curSl) <= freezeLevelPts * _Point)
         continue;

      bestSl = NormalizeDouble(bestSl, _Digits);
      bool better = isLong ? (curSl == 0.0 || bestSl > curSl)
                            : (curSl == 0.0 || bestSl < curSl);
      if(!better) continue;

      if(!trade.PositionModify(pos.Ticket(), bestSl, pos.TakeProfit()))
        { if(InpVerbose) Print("Trail failed: ", trade.ResultRetcodeDescription()); }
     }
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
void DrawPanel(const bool haveLong, const bool haveShort, const bool reclaim = true)
  {
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }
   // See g_panelReclaim's own comment: true only reclaims top-of-stack
   // (once per new bar, when a new MA/BB line segment was actually drawn);
   // every other caller (OnTimer's once-per-second refresh, the drag
   // handler) passes false so PRect/PText update objects in place instead
   // of tearing them down every cycle.
   g_panelReclaim = reclaim;
   PBackground();
   PWatermark();

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;   // re-measured fresh this cycle, used by the NEXT one
   int rh = InpPanelSize + 11;
   int hdr = rh + 14;
   // 2026-09-06 (Opus deep-dive review): GAPS was 8, but hand-counting the
   // literal `ty += rh + 6` sequence in this function (after a0, s1, b4,
   // s2, c8, s3, p5, s4, q4, s5) gives 10. The 2 missing gaps (12px) had
   // been exactly cancelling the formula's intended 12px bottom padding -
   // nothing clips TODAY only because that cancellation happens to be
   // exact, and it will break the moment a row/section is added or
   // removed. Fixed to the real count; the drift-warning added below this
   // function (matching Aurelius's own) catches any future mismatch
   // instead of silently clipping.
   const int ROWS = 33, GAPS = 10;
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH  = hdr + 10 + ROWS*rh + GAPS*6 + 12;
   int guard  = 0;
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     { rh--; guard++; hdr = rh + 14; bodyH = hdr + 10 + ROWS*rh + GAPS*6 + 12; }
   if(g_panX < 0)
     {
      g_panX = InpPanelX;
      g_panY = InpPanelBottom ? MathMax(2, chartH - bodyH - InpPanelY) : InpPanelY;
     }
   int x = g_panX, y = g_panY;

   PRect("sh", x + 4, y + 4, w, bodyH, InpShadowCol, InpShadowCol, 0);
   PRect("bg", x, y, w, bodyH, InpPanelBg, InpPanelBg, 0);
   //--- "bg" keeps its object identity across cycles so dragging works,
   //--- which means it can't be recreated to reclaim top-of-stack - an MA/
   //--- BB line segment drawn on a later bar would otherwise end up stacked
   //--- above it and show through the row background. "fl" sits right on
   //--- top of "bg", covers the same area, and IS recreated every cycle
   //--- (see PRect), so it's what actually keeps the panel body solid -
   //--- same trick as Fulcrum_EA.mq5's "fl" fill, needed here for the first
   //--- time now this file draws chart-object trend segments too.
   PRect("fl", x + 2, y + 2, w - 4, bodyH - 4, InpPanelBg, InpPanelBg, 0);
   //--- explicit 4-strip frame, not PRect's own unreliable built-in border -
   //--- see PFrame's own comment for why.
   PFrame("bd", x, y, w, bodyH, InpPanelEdge, 2);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);

   int ty = y + 9;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "RATCHET", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   bool algo = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) &&
               MQLInfoInteger(MQL_TRADE_ALLOWED);
   PRow("a0", x, ty, w, "algo trading", algo ? "ON" : "OFF", algo ? 1 : 0);
   ty += rh + 6;

   double m21,m50,m150,m600,m2400,atr;
   bool ok = MAs(1,m21,m50,m150,m600,m2400,atr);
   double c = iClose(_Symbol, PERIOD_CURRENT, 1);
   PSection("s1", x, ty, w, rh, "BIAS"); ty += rh + 6;
   PRow("b1", x, ty, w, "M5    50",   !ok?"-":(c>m50  ?"UP":"DOWN"), ok?(c>m50  ?1:0):-1); ty += rh;
   PRow("b2", x, ty, w, "M15   150",  !ok?"-":(c>m150 ?"UP":"DOWN"), ok?(c>m150 ?1:0):-1); ty += rh;
   PRow("b3", x, ty, w, "H1    600",  !ok?"-":(c>m600 ?"UP":"DOWN"), ok?(c>m600 ?1:0):-1); ty += rh;
   PRow("b4", x, ty, w, "H4    2400", !ok?"-":(c>m2400?"UP":"DOWN"), ok?(c>m2400?1:0):-1); ty += rh + 6;

   bool aU = Aligned(1,true), aD = Aligned(1,false);
   int dir = aU ? 1 : (aD ? -1 : 0);
   double slope = 0.0;
   if(dir != 0 && ok && atr > 0.0)
     { double a1,a2; if(MA(h21,1,a1) && MA(h21,2,a2)) slope = ((a1-a2)*dir)/atr; }
   double bp  = (dir != 0) ? BandPos(dir > 0) : -1.0;
   double sv  = StoVal(1);
   long spr   = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   int mtc    = MinutesToSessionClose();
   PSection("s2", x, ty, w, rh, "ENTRY CRITERIA"); ty += rh + 6;
   PRow("c1", x, ty, w, "aligned", dir==1?"BUY":dir==-1?"SELL":"no", dir!=0?1:0); ty += rh;
   bool freshNow = InpUseMomentumEntry && dir != 0 && FreshAligned(1, dir==1);
   PRow("c1b", x, ty, w, "momentum entry",
        !InpUseMomentumEntry ? "off" : (freshNow ? "fresh" : "no"),
        !InpUseMomentumEntry ? -1 : (freshNow ? 1 : 0)); ty += rh;
   PRow("c2", x, ty, w, "21 slope", DoubleToString(slope,3),
        !InpNeedSlope ? -1 : (slope >= InpMinSlope ? 1 : 0)); ty += rh;
   PRow("c3", x, ty, w, "band pos", bp < 0.0 ? "-" : DoubleToString(bp,2),
        !InpUseBands ? -1 : (bp >= 0.0 && bp <= InpBBMaxPos ? 1 : 0)); ty += rh;
   PRow("c4", x, ty, w, "stochastic", sv < 0.0 ? "-" : DoubleToString(sv,1), -1); ty += rh;
   double distNow = (dir != 0 && ok && atr > 0.0) ? MathAbs(c-m21)/atr : -1.0;
   PRow("c5", x, ty, w, "dist from 21",
        distNow < 0.0 ? "-" : DoubleToString(distNow,2) + " ATR",
        InpMaxDistATR <= 0.0 ? -1 : (distNow >= 0.0 && distNow <= InpMaxDistATR ? 1 : 0)); ty += rh;
   PRow("c6", x, ty, w, "loss pause",
        (InpMaxConsecLosses > 0 && g_breakerBarsLeft > 0)
           ? (string)g_breakerBarsLeft + " bars" : "no",
        InpMaxConsecLosses <= 0 ? -1 : (g_breakerBarsLeft > 0 ? 0 : 1)); ty += rh;
   PRow("c7", x, ty, w, "spread", (string)spr,
        (InpMaxSpreadPoints > 0 && spr > InpMaxSpreadPoints) ? 0 : 1); ty += rh;
   PRow("c8", x, ty, w, "session closes",
        mtc < 0 ? "n/a" : (string)mtc + " min",
        (mtc >= 0 && mtc <= InpNoEntryMinsBefore) ? 0 : 1); ty += rh + 6;

   PSection("s3", x, ty, w, rh, "POSITION"); ty += rh + 6;
   if(haveLong || haveShort)
     {
      double prof=0.0, vol=0.0, opx=0.0, slNow=0.0;
      for(int i = PositionsTotal()-1; i >= 0; i--)
        {
         if(!pos.SelectByIndex(i)) continue;
         if(pos.Symbol()!=_Symbol || pos.Magic()!=InpMagic) continue;
         prof += pos.Profit()+pos.Swap(); vol=pos.Volume(); opx=pos.PriceOpen(); slNow=pos.StopLoss();
        }
      bool trailed = InpUseTrail && slNow != 0.0 &&
                     slNow != (haveLong ? NormalizeDouble(g_entryPrice - InpStopATR*g_entryATR, _Digits)
                                        : NormalizeDouble(g_entryPrice + InpStopATR*g_entryATR, _Digits));
      PRow("p1", x, ty, w, haveLong?"LONG":"SHORT", DoubleToString(opx,_Digits), 1); ty += rh;
      PRow("p2", x, ty, w, "volume", DoubleToString(vol,2), -1); ty += rh;
      PRow("p3", x, ty, w, "floating P/L", StringFormat("%+.2f", prof), prof>=0?1:0); ty += rh;
      PRow("p4", x, ty, w, "bars held", (string)g_entryBarCount, -1); ty += rh;
      PRow("p5", x, ty, w, trailed ? "trailing" : "stop",
           slNow != 0.0 ? DoubleToString(slNow,_Digits) : "-", trailed ? 1 : -1); ty += rh + 6;
     }
   else
     {
      PRow("p1", x, ty, w, "state", "FLAT", -1); ty += rh;
      PRow("p2", x, ty, w, "cooldown",
           (string)MathMax(0, InpCooldown - g_barsSinceClose) + " bars", -1); ty += rh;
      PRow("p3", x, ty, w, "lot size", DoubleToString(InpLots,2), -1); ty += rh;
      PRow("p4", x, ty, w, "stop", InpUseStop ?
           DoubleToString(InpStopATR,1) + " ATR" : "none", InpUseStop?1:-1); ty += rh;
      PRow("p5", x, ty, w, "trail", InpUseTrail ?
           "keep " + DoubleToString(InpTrailKeepFrac*100.0,0) + "%" : "off", InpUseTrail?1:-1); ty += rh + 6;
     }

   //--- "today" is split mine/other because ACCOUNT_EQUITY reflects the
   //--- WHOLE account - if any other EA or a manual trade shares this
   //--- account, its P&L was previously mixed into this EA's own number
   //--- with no way to tell them apart.
   PSection("s4", x, ty, w, rh, "ACCOUNT"); ty += rh + 6;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double dpl = (g_dayStartEquity > 0.0) ? eq - g_dayStartEquity : 0.0;
   double myDayPL = MyRealizedPLToday() + MyFloatingPL();
   double otherPL = dpl - myDayPL;
   PRow("q1", x, ty, w, "balance", DoubleToString(bal,2), -1); ty += rh;
   PRow("q2", x, ty, w, "equity", DoubleToString(eq,2), eq>=bal?1:0); ty += rh;
   PRow("q3", x, ty, w, "today (mine)", StringFormat("%+.2f", myDayPL), myDayPL>=0?1:0); ty += rh;
   PRow("q5", x, ty, w, "today (other)", StringFormat("%+.2f", otherPL),
        otherPL == 0.0 ? -1 : (otherPL >= 0 ? 1 : 0)); ty += rh;
   PRow("q4", x, ty, w, "last trade",
        g_lastReason == "" ? "-" : StringFormat("%+.2f (%s)", g_lastMoved, g_lastReason),
        g_lastReason == "" ? -1 : (g_lastMoved >= 0 ? 1 : 0)); ty += rh + 6;

   //--- entries that never happened, and why
   PSection("s5", x, ty, w, rh, "REJECTED (this session)"); ty += rh + 6;
   PRow("y1", x, ty, w, "spread too wide", (string)g_blkSpread, -1); ty += rh;
   PRow("y2", x, ty, w, "too far from 21", (string)g_blkDist, -1); ty += rh;
   PRow("y3", x, ty, w, "loss-streak pause", (string)g_blkBreaker, -1); ty += rh;
   PRow("y4", x, ty, w, "weak wick reject", (string)g_blkWick, -1);
   ty += rh;

   // 2026-09-06 (Opus deep-dive review): ported from Aurelius_EA.mq5 - if
   // the row/section count above ever drifts from ROWS/GAPS again, say so
   // in the log instead of silently clipping the panel.
   static int warned = 0;
   int used = ty + 12 - y;
   if(used > bodyH && warned < 3)
     { warned++; PrintFormat("Ratchet_EA: panel content %d px vs frame %d px", used, bodyH); }
  }
//+------------------------------------------------------------------+
void OnTimer()
  {
   //--- defense-in-depth backstop for the EventSetTimer(1) fix in OnInit -
   //--- shouldn't even fire in this mode since the timer isn't started,
   //--- but bail immediately if it somehow does.
   if(g_skipCosmeticDraws) return;
   if(!InpShowPanel) return;
   bool hl, hs;
   CurrentPositions(hl, hs);
   DrawPanel(hl, hs, false);   // per-second refresh - update in place, don't reclaim top-of-stack
   //--- only force a redraw when a position is open and the floating
   //--- P/L genuinely needs to look live - forcing it unconditionally
   //--- every second fought the user's own scrolling/panning.
   if(hl || hs) ChartRedraw(0);
  }
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam,
                  const string &sparam)
  {
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_pp + "bg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      bool hl, hs; CurrentPositions(hl, hs); DrawPanel(hl, hs, false); ChartRedraw(0);   // drag - update in place
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      static int lw = -1, lh = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lw || nh != lh)
        { lw = nw; lh = nh; g_bgOK = false; g_bgTries = 0;
          PBackground(); PWatermark();
          if(InpPanelBottom) g_panX = -1; }
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
   //--- Friday cutoff hour, so a bar-gated check never gets a chance to
   //--- fire; this can act on the very first tick available, whenever that
   //--- turns out to be. Same fix as Daybreak_EA.mq5 v1.11/Zenith_EA.mq5/
   //--- Aurelius_EA.mq5/Fulcrum_EA.mq5 for the identical holiday-session-
   //--- gap bug class - see WeekendStillOpen's own header.
   if(InpCloseOnFriday && HasOwnPosition() && WeekendStillOpen(TimeCurrent(), g_entryTime))
      ClosePosition("FRIDAY");

   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(bt == g_lastBar) return;
   g_lastBar = bt;

   if(Bars(_Symbol, PERIOD_CURRENT) < InpP2400 + NEED_BARS)
     { Print("Waiting for history: ", Bars(_Symbol, PERIOD_CURRENT)); return; }
   if(g_barsSinceClose < 100000) g_barsSinceClose++;
   if(g_breakerBarsLeft > 0) g_breakerBarsLeft--;
   if(PositionsTotal() > 0) g_entryBarCount++;

   bool haveLong, haveShort;
   CurrentPositions(haveLong, haveShort);
   //--- PERFORMANCE FIX: purely cosmetic, skipped entirely in a non-visual
   //--- Tester run, where nobody can see the panel anyway and it has zero
   //--- effect on any trading decision below - still fully live for real
   //--- trading, demo, and visual-mode backtests.
   if(!g_skipCosmeticDraws)
     {
      UpdateMALines();
      DrawPanel(haveLong, haveShort);
      ChartRedraw(0);
     }

   //--- manage an open trade -------------------------------------
   //--- weekend flatten now handled tick-level at the top of OnTick (see
   //--- WeekendStillOpen) - FridayCutoff(false) here would just be dead
   //--- weight by the time a new bar completes, since the tick-level check
   //--- already caught it.
   if(haveLong || haveShort)
     {
      if(InpCloseBeforeBreak && NearSessionClose(InpCloseMinsBefore))
        { ClosePosition("SESSION_CLOSE"); return; }
      if(TailLossHit()) { ClosePosition("TAILCAP"); return; }

      if(InpUseTrail || InpUseBreakeven) TrailStop();

      double sv = StoVal(1);
      if(sv >= 0.0)
        {
         double hi = InpKLevel, lo = 100.0 - InpKLevel;
         if((haveLong && sv >= hi) || (haveShort && sv <= lo))
           { ClosePosition("STOCH"); return; }
        }
      if(g_entryBarCount >= InpMaxBars) { ClosePosition("MAXBARS"); return; }
      return;                                  // one position at a time
     }

   //--- entry gates ----------------------------------------------
   if(DailyLossHit()) return;
   if(g_barsSinceClose < InpCooldown) return;
   if(InpMaxConsecLosses > 0 && g_breakerBarsLeft > 0) { g_blkBreaker++; return; }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return;
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) return;
   if(NearSessionClose(InpNoEntryMinsBefore)) return;
   if(FridayCutoff(true)) return;
   if(IsMarketHoliday(TimeCurrent())) return;
   if(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL) return;

   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && spread > InpMaxSpreadPoints)
     { g_blkSpread++; if(InpVerbose) Print("Skipped: spread ", spread); return; }

   bool up = Aligned(1, true);
   bool dn = Aligned(1, false);
   if(!up && !dn) return;
   bool triggered = Touched21(up);
   if(!triggered && InpUseMomentumEntry) triggered = FreshAligned(1, up);
   if(!triggered) return;

   double atr;
   if(!MA(hATR, 1, atr) || atr <= 0.0) return;
   int dir = up ? 1 : -1;

   double o1 = iOpen(_Symbol, PERIOD_CURRENT, 1);
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   if(InpNeedCandle && (c1 - o1) * dir <= 0.0)
     { if(InpVerbose) Print("Skipped: candle against the trade"); return; }

   if(InpNeedSlope)
     {
      double a1, a2;
      if(!MA(h21,1,a1) || !MA(h21,2,a2)) return;
      if(((a1 - a2) * dir) / atr < InpMinSlope)
        { if(InpVerbose) Print("Skipped: 21 slope"); return; }
     }
   if(InpUseBands)
     {
      double bp = BandPos(up);
      if(bp >= 0.0 && bp > InpBBMaxPos)
        { if(InpVerbose) Print("Skipped: outside the band"); return; }
     }
   //--- price already too far from the 21 has made most of its move - the
   //--- single biggest loss-reduction filter tested, blocks chasing entries
   //--- into an already-extended run.
   if(InpMaxDistATR > 0.0)
     {
      double m21;
      if(!MA(h21, 1, m21)) return;
      double dist = MathAbs(c1 - m21) / atr;
      if(dist > InpMaxDistATR)
        { g_blkDist++; if(InpVerbose) Print("Skipped: too far from the 21, ", DoubleToString(dist,2), " ATR"); return; }
     }
   //--- the trigger candle's wick INTO the 21 must dominate its body - a real
   //--- rejection, not just a close back past the line. Tested: real edge
   //--- (PF 1.69->2.26, maxDD -59%) but trades less than half as often - a
   //--- genuine volume-vs-quality tradeoff. CORRECTED (2026-09-06, Opus
   //--- deep-dive review): this comment used to say "off by default", which
   //--- contradicted the input's own default below and its v3.21 changelog
   //--- (flipped to true after the quality tradeoff was judged worth it) -
   //--- this is ON by default, not off.
   if(InpUseWickReject)
     {
      double h1 = iHigh(_Symbol, PERIOD_CURRENT, 1), l1 = iLow(_Symbol, PERIOD_CURRENT, 1);
      double body = MathAbs(c1 - o1);
      double wick = up ? (MathMin(o1, c1) - l1) : (h1 - MathMax(o1, c1));
      if(body <= 0.0 || wick < InpWickRejectRatio * body)
        { g_blkWick++; if(InpVerbose) Print("Skipped: weak wick rejection"); return; }
     }

   double stopDist = InpUseStop ? InpStopATR * atr : 0.0;
   double lots = LotSize(stopDist);
   if(lots <= 0.0) return;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = 0.0;
   if(InpUseStop)
      sl = up ? NormalizeDouble(ask - stopDist, _Digits)
              : NormalizeDouble(bid + stopDist, _Digits);

   bool ok = up ? trade.Buy(lots, _Symbol, 0.0, sl, 0.0, InpComment)
                : trade.Sell(lots, _Symbol, 0.0, sl, 0.0, InpComment);
   if(ok)
     {
      g_ticket=trade.ResultOrder(); g_entryTime=TimeCurrent();
      g_entryPrice=trade.ResultPrice(); g_entryDir=dir;
      g_entryLots=lots; g_entryATR=atr; g_entryBarCount=0;
      g_peakFavPx=g_entryPrice;   // reset - see TrailStop()/InpTrailKeepFrac
      PrintFormat("%s %.2f @ %.2f  sto %.1f", (up?"BUY":"SELL"), lots,
                  g_entryPrice, StoVal(1));
     }
   else
      Print("Order failed: ", trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
