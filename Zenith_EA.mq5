//+------------------------------------------------------------------+
//|                                                    Zenith_EA.mq5  |
//|  Live/backtest EA for the multi-timeframe confluence breakout/    |
//|  continuation system validated on GOLD# this session. Same        |
//|  construction as Zenith_Signals.mq5 (its visual companion - run    |
//|  both together, the indicator shows the zones this EA trades):    |
//|                                                                     |
//|  MACRO (D1) + INTERMEDIATE (H4) + EXECUTION (M15): see             |
//|  Zenith_Signals.mq5's header for the full construction writeup     |
//|  and the tested-and-rejected list. Not duplicated here to avoid    |
//|  the two files drifting out of sync on the parts that matter -     |
//|  if you change one, check the other.                               |
//|                                                                      |
//|  VALIDATED RESULT (Jan 2023 - Aug 2026, 70/30 train/hold split,     |
//|  pullback=$5, stop cap=$30, D1 trend filter ON, touch/fill window=  |
//|  24 bars each, MinH4Hits=0, D1/H4 fractal half-window=2/4 (more     |
//|  pivots -> more zones -> +14% more trades than P_D1=3/P_H4=5, with  |
//|  quality/drawdown essentially unchanged), Friday close - no         |
//|  weekend holding, circuit breaker ON (pause new entries after 2     |
//|  losses in a row for 400 M15 bars ~4.2 days), TRAILING EXIT ON      |
//|  (arm at $60 profit, trail $30 behind the peak - beat the flat $50  |
//|  target on EVERY split, not just the favorable one, with the same   |
//|  per-trade downside risk: avg/max loss essentially unchanged, only  |
//|  the upside on trades that keep trending is bigger, up to $180      |
//|  seen vs the old $50 cap):                                          |
//|    FULL  n=105  net=+$1940  win=62.9%  PF=3.59  maxDD=$110          |
//|    TRAIN n=65   net=+$780           PF=2.74                         |
//|    HOLD  n=40   net=+$1160          PF=4.86                         |
//|  CAVEAT (Opus review, 2026-09-05): these are the Python model's       |
//|  numbers, not this file's real behaviour. A fresh real-tick MT5 run    |
//|  over the same window (2023.01-2026.09, InpLotSize=0.01, breaker ON)    |
//|  came back n=89, net=+$868, PF=1.99, maxDD=$276 (11 losses in a row,     |
//|  not the 5 quoted above) - PF and net roughly half the claim, drawdown    |
//|  2.5x worse. Root cause, also from that review: InpMaxLossUSD/InpPullback |
//|  USD/InpMinLossUSD/InpTrailActivateUSD/InpTrailUSD/InpFixedTargetUSD were   |
//|  all fixed dollar amounts on a symbol whose price has gone ~$1,940->$4,900   |
//|  since these were tuned - InpMaxLossUSD=$30 capped 92% of losing trades in    |
//|  2026 (was 10% in 2023), meaning the ATR/zone stop this system was actually     |
//|  validated on was barely ever the real exit anymore. Since 2026-03-01: 13         |
//|  trades, 2 wins, -$198. FIXED below: all six renamed to *ATR and converted          |
//|  to H4-ATR multiples (InpPullbackATR/InpFixedTargetATR/InpTrailActivateATR/           |
//|  InpTrailATR/InpMaxLossATR/InpMinLossATR), calibrated so behaviour at 2023's            |
//|  typical H4 ATR ($8.56) reproduces the original dollar defaults almost exactly,          |
//|  then tracks current ATR going forward instead of staying frozen - the same               |
//|  fix already applied as InpStopATR-style inputs on the gold trio (Aurelius/                 |
//|  Fulcrum/Ratchet). Re-run a fresh backtest after this change before trusting                  |
//|  new numbers - this was calibrated, not independently re-validated end to end.                 |
//|  TRAIN/HOLD's validation is also not fully clean - HOLD was looked at before                    |
//|  each design step above was adopted, so it isn't a truly untouched out-of-                       |
//|  sample check.                                                                                      |
//|  FOLLOW-UP (second Opus review, same day): found a genuine live-trading                              |
//|  blocker in the ATR conversion above - CurrentH4ATR() returns 0.0 until its                          |
//|  first successful read, and none of the three trailing-stop sites guarded                             |
//|  against that. On a restart with an open position (RestoreTrailingState,                               |
//|  called from OnInit before any tick has run), a cold CopyRates() could zero                             |
//|  out InpTrailATR/InpTrailActivateATR, arm the trail unconditionally, and on                              |
//|  the very next tick place a new SL at the current market price - closing a                                |
//|  live position outright. Fixed: all three sites (OnInit restore, stale-state                               |
//|  resync, and the live per-tick update) now treat atr<=0 as "no information"                                 |
//|  and leave the trail/position untouched that cycle, rather than acting on a                                  |
//|  zero reading. Also fixed in the same pass: InpPullbackATR/InpMaxLossATR/                                     |
//|  InpMinLossATR/InpFixedTargetATR were multiplying watchAtr (the ATR at the                                     |
//|  zone's FRACTAL bar, which can be traded up to ~333 days later on a symbol                                     |
//|  whose ATR has moved ~6x in 3 years) rather than current ATR as the header                                      |
//|  above claimed - now use a fresh CurrentH4ATR() reading instead (the zone-                                      |
//|  geometry stop itself, zlo/zhi -+ InpStopBufATR*watchAtr, is untouched -                                        |
//|  that's meant to reflect the zone's own formation-time volatility). And                                         |
//|  CurrentH4ATR() itself now reads from start_pos=1, not 0, matching every                                         |
//|  other rates read in this file (skips the still-forming H4 bar, which was                                        |
//|  making the trail distance wobble intra-bar for no reason). No change to                                         |
//|  the calibration multipliers' meaning - re-run a fresh backtest either way,                                       |
//|  per the note above.                                                                                                |
//|  THIRD review (2026-09-05, fresh full-portfolio Forward=No backtest round): the           |
//|  above two fixes shipped and a new continuous run came back net -$65/PF 0.95/maxDD        |
//|  $577 - a real regression from the pre-conversion +$868. Root cause found and fixed:        |
//|  InpPullbackATR (an ATR multiple) was the wrong conversion for THIS input specifically -     |
//|  H4 ATR/price roughly DOUBLED 2023->2026 while price only ~2.4x'd, so the ATR-multiple         |
//|  pullback offset got proportionally deeper over time and simply stopped filling: 33 real       |
//|  entries worth +$812 vanished vs only 8 new ones (-$302) that exist because of it. The exit-     |
//|  side ATR math (stop/trail/target) is NOT the problem - verified against real H4 ATR history,    |
//|  every large 2026 loss (including the -$254 trade) landed exactly where the geometry says it      |
//|  should, no gaps, no cold-start failures. FIXED: InpPullbackATR -> InpPullbackPct (0.257%, a        |
//|  pure price-percentage offset, calibrated the same way - $5.0 / 2023's real median H4 close).        |
//|  SEPARATELY re-added InpMaxLossCapUSD=30.0, a hard $ ceiling on the ATR-based stop distance -          |
//|  this is exactly the original pre-conversion InpMaxLossUSD=$30 the ATR conversion had removed,         |
//|  restored on top of (not instead of) the ATR-based stop so it only binds in high-ATR periods            |
//|  where fixed-lot dollar risk would otherwise balloon (2026: up to $254/trade at 0.01 lots = 8.5%          |
//|  of a $3,000 account). Also noted, not yet acted on: InpUseRiskPercent=true does NOT fix this on          |
//|  a small account - 1% of $3,000 against a $254 stop needs a 0.0012 lot, which floors to the same           |
//|  0.01 minimum anyway, so risk-percent sizing is inert below roughly $25k equity here; the dollar            |
//|  cap above is the real lever at this account size. NEEDS a fresh backtest to confirm entry               |
//|  frequency is actually restored and the cap doesn't cut too many legitimate wins - not yet run.           |
//|  FOURTH review (2026-09-06, real backtest with the fix above): entry frequency DID restore (74->86           |
//|  trades, gains concentrated in 2025-2026 exactly as predicted) and net swung -$65->+$521. But the             |
//|  $30 cap turned out to bind on 100% of 2026 trades, not just tail cases - reproducing the exact               |
//|  problem the ATR conversion existed to fix in the first place (see the CAVEAT paragraph above: the             |
//|  old flat $30 bound on 92% of 2026 losses pre-conversion). 2026 win rate collapsed to 23.5% and a               |
//|  10-loss/128-calendar-day streak resulted - cheaper in dollars than the pre-fix worst streak, but a              |
//|  real live-trading problem the dollar figure hides (a live operator watching 4 months of straight               |
//|  losses would plausibly have shut the system off). RAISED InpMaxLossCapUSD 30.0->65.0 - high enough              |
//|  to sit above InpMinLossATR's floor in a typical high-ATR year (so the adaptive stop/floor actually              |
//|  do their job again in ordinary conditions) while still bounding a repeat of the 2026-03 spike (which             |
//|  would otherwise cost ~$254/trade) to ~2.2% of a $3,000 account. NEEDS another fresh backtest -                  |
//|  not yet re-validated at the new value.                                                                            |
//|  (superseded, in order: a flat $50 target with P_D1=3/P_H4=5        |
//|  (n=96 net=$1633 PF=3.39), then adding the trailing exit alone      |
//|  (n=91 net=$1774 PF=3.82) - each step validated on train AND hold   |
//|  before being adopted, same discipline as every other change here.  |
//|  A denser round-number grid ($25 instead of $50) was ALSO tested    |
//|  for more trade volume and rejected: it added trades and profit     |
//|  but DOUBLED max drawdown ($102->$200) - not worth it. A weekly     |
//|  (W1) confluence tier was tested too and made the system MORE       |
//|  selective (fewer, higher-quality trades) - the opposite of what    |
//|  was being optimized for here, but worth remembering if you ever    |
//|  want to trade this system less often at higher per-trade quality.) |
//|  The consecutive-loss circuit breaker itself was validated earlier  |
//|  against a REAL 7-loss streak that showed up in the live MT5 real-  |
//|  tick test (late June-July 2026, a choppy decline off gold's        |
//|  ~$4,900 peak) - a response to something actually observed.         |
//|  Also tested and rejected: a breakeven stop move (every threshold   |
//|  tried cut winners short more than it saved losers - net profit     |
//|  fell every time despite raising raw win rate as high as 70%) and   |
//|  several TIGHT trailing variants (activate/trail under ~$30 - same  |
//|  failure mode as breakeven). Only a RELAXED trail (activate >=      |
//|  ~$50) actually helps; tight trailing is worse than no trailing.    |
//|  All $ figures assume InpLotSize=0.01 (1 price unit ~= $1 P&L on    |
//|  XAUUSD) - scale InpLotSize for your actual size; the price         |
//|  DISTANCES (pullback/target/stop) don't change with lot size.       |
//|                                                                      |
//|  ROBUSTNESS ADDITIONS (not part of the backtested P&L above, since  |
//|  they're off by default - real-money hardening, not a return        |
//|  driver):                                                            |
//|   - InpUseRiskPercent: risk a fixed % of current equity per trade   |
//|     instead of a fixed lot, so risk scales with the account instead |
//|     of staying flat forever - same "$ scale drifts as price/equity  |
//|     changes" problem the $8 stop floor solved for Bastion, applied  |
//|     to position sizing instead of stop distance.                    |
//|   - Every order placement checks AutoTrading/terminal trade-allowed |
//|     first, and retries on a transient rejection (requote, price     |
//|     changed, timeout, connection) instead of giving up on attempt   |
//|     one - never comes up in a backtest, will eventually on a real   |
//|     or demo account.                                                |
//|                                                                      |
//|  DESIGN NOTE - live/backtest execution vs. the pure Python replay:  |
//|  the Python backtest and Zenith_Signals.mq5 both replay the ENTIRE  |
//|  history every bar to draw/score every past signal - fine for a     |
//|  once-per-15-min chart redraw, wasteful and pointless for an EA     |
//|  that only needs to know "what's true right now". This EA instead   |
//|  rebuilds the full zone/event list each new M15 bar (cheap, same    |
//|  as the indicator) but only ACTS on confluence events from within   |
//|  the last (TouchWindow+FillWindow) bars, tracking real MT5 pending  |
//|  orders and real position state rather than paper-simulating a      |
//|  trade log. Cooldown is measured from the real last-close time,     |
//|  not a replayed bar counter. Same validated decision logic, a       |
//|  live-appropriate state machine around it.                          |
//|                                                                      |
//|  Only ONE position (or resting pending order) open at a time,       |
//|  matching the validated backtest exactly - if more than one         |
//|  confluence setup is being watched/pending simultaneously and one   |
//|  fills, all the others are cancelled immediately.                   |
//|                                                                       |
//|  KNOWN, DELIBERATE DIVERGENCE FROM THE PYTHON BACKTEST: in the       |
//|  Python code, a confluence event that occurs WHILE a position is     |
//|  open never gets its own touch-window countdown - it only enters     |
//|  the watch list once flat again, at which point it gets a FRESH      |
//|  touch-window measured from "now", however stale the event actually  |
//|  is. That looks like a bookkeeping side-effect of the backtest's     |
//|  index-advancing logic, not a deliberate design choice, so this EA   |
//|  does the more defensible thing instead: an event's touch-window is  |
//|  always measured from its own real H4 touch time, position or no     |
//|  position. This means the EA will let some stale events expire       |
//|  unacted-on that the exact backtest code would have retroactively    |
//|  revived - a small, considered difference, not an oversight.         |
//|                                                                      |
//|  CORRECTNESS PASS (independent review, this session, before any     |
//|  real-money use): found and fixed several real bugs beyond the       |
//|  earlier ATR/dedup/duplicate-order fixes above -                     |
//|   - a SECOND resting order could still be placed on a LATER bar      |
//|     while an earlier one was unfilled (the earlier fix only closed   |
//|     the SAME-bar case) - now blocked explicitly, plus a defensive    |
//|     pending-cancel on the open-position path in case a fill event    |
//|     is ever missed (recompile/restart between fill and event).       |
//|   - the touch window was structurally only ~8 of its 24 validated    |
//|     bars, because it was measured from an H4 bar's OPEN time even    |
//|     though this EA only ever sees that bar once CLOSED, 4h later -   |
//|     now measured from when the event is actually knowable.           |
//|   - circuit-breaker/cooldown/trailing state was RAM-only and reset   |
//|     to zero on any recompile or restart - now reconstructed from     |
//|     real trade history/position data at OnInit.                      |
//|   - no broker fill-mode, stops/freeze-level, or specified-expiration |
//|     support handling at all (every sibling EA in this repo has it) - |
//|     added, so Friday/MaxBars closes, trailing modifies, and order    |
//|     placement don't silently fail on a broker that needs them.       |
//|   - no floor on stop distance - a low-ATR regime could produce a     |
//|     near-zero stop, which with risk-percent sizing would compute a   |
//|     near-max-lot position instead of a skipped trade. InpMinLossUSD  |
//|     added.                                                            |
//|   - same-bar breakout candidates were processed newest-first; now    |
//|     oldest-first, matching Python's actual tie-break exactly.        |
//|   - a `long` funnel counter was printed with %d instead of %I64d.    |
//|  Two things reviewed and deliberately left unchanged: the hi/lo      |
//|  dedup key doesn't also key on atr (harmless - the dropped duplicate |
//|  shares the same union zone, just a different underlying ATR), and   |
//|  cooldown/Friday are still checked at breakout time rather than at   |
//|  fill time (a placed order can very rarely fill just past either     |
//|  cutoff) - both low-stakes relative to everything above.             |
//|                                                                      |
//|  SECOND CORRECTNESS PASS (a fresh independent review verifying the   |
//|  first pass's own fixes, not just re-describing them):               |
//|   - the FIRST pass's D1-trend-filter "fix" in Zenith_Signals.mq5 was |
//|     itself wrong (see that file's header) - reverted.                |
//|   - the duplicate-position path was only closed for the SAME bar;    |
//|     a second order could still be placed on a LATER bar while an     |
//|     earlier one was unfilled. Now blocked via CountOurPendingOrders. |
//|   - InpMinLossUSD was measured from `ref`, not the real entry        |
//|     (`limitPx`) - silently a $3 floor instead of the stated $8.      |
//|   - the circuit breaker reset its loss streak once a pause elapsed - |
//|     the validated Python never does that, only a WIN resets it, so   |
//|     this needed two fresh losses to re-pause instead of one.         |
//|   - InpPauseBars and InpMaxBars were wall-clock seconds, not the bar |
//|     counts they're validated as - both were silently ~30% shorter   |
//|     than intended across any span crossing a weekend. Now driven by  |
//|     g_barCounter (incremented once per real M15 bar, which MT5      |
//|     never generates over a weekend either, so this naturally matches |
//|     Python's bar-index counting) with matching restoration logic.    |
//|   - a broker TIMEOUT/CONNECTION during order placement has an        |
//|     AMBIGUOUS outcome (the order may already be resting) - blindly   |
//|     retrying those two specifically risked a duplicate; now polls    |
//|     for an existing pending before retrying just those two.          |
//|   - a paused-but-would-have-broken-out watch was only counted, not   |
//|     consumed, unlike the indicator - could break out again once the  |
//|     pause ended. An off-by-one in the H4 touch-scan cap (both        |
//|     files). A `long` risked commission being counted on only the     |
//|     exit deal when most brokers charge it on entry. A stops-level    |
//|     check used unsigned distance, unable to tell "too close" from    |
//|     "on the wrong side of market" apart. A `lot > 0` gate made the   |
//|     one risk-percent-sizing warning that mattered most unreachable.  |
//|     Trailing state is a single global, correct for one position but  |
//|     would thrash across two if that invariant were ever broken       |
//|     anyway - now logs loudly and manages only the first rather than  |
//|     corrupting both. InpRoundStep<=0 would hang the terminal in an   |
//|     infinite loop - now refused at OnInit.                           |
//|                                                                      |
//|  THIRD CORRECTNESS PASS (verified the second pass's own bar-counter  |
//|  refactor by hand-tracing the arithmetic, not just re-describing     |
//|  it - genuinely found more):                                        |
//|   - g_barCounter was incremented (++) instead of resynced from       |
//|     iBars() - drifted permanently out of sync after any missed bar   |
//|     (disconnect/stall) with no way to self-correct short of a        |
//|     restart, and was updated AFTER ManageOpenPosition() ran on the   |
//|     first tick of a new bar (MaxBars one bar low for that tick).     |
//|     Now recomputed fresh at the very top of every OnTick.            |
//|   - GetPositionEntryCommission() (added last pass specifically to    |
//|     count entry commission) returned 0.0 EVERY TIME it was actually  |
//|     called live - HistorySelect()/HistoryDealSelect() replace the    |
//|     history cache with only what they were asked for, so a loop      |
//|     right after selecting one deal never sees any other. Switched to |
//|     HistorySelectByPosition(), and re-selected the caller's own      |
//|     range afterward where the caller was itself mid-loop over it     |
//|     (RestoreCircuitBreakerState) - otherwise this call would have    |
//|     silently corrupted THAT loop's indexing on its very next         |
//|     iteration, a new bug worse than the one being fixed.             |
//|   - the touch window, fill window, and cooldown were still wall-     |
//|     clock, missed by the bar-counter refactor - all three are        |
//|     validated in Python as bar counts. Touch window and cooldown now |
//|     use g_barCounter directly; the fill window's real MT5 order      |
//|     expiration (a broker parameter, must stay wall-clock) is now     |
//|     deliberately generous, with the actual bar-count enforcement     |
//|     done manually via iBarShift in CancelInvalidatedOrders.          |
//|   - the stops-level wrong-side check (added last pass) was gated     |
//|     behind stopsLevelPts > 0, which is 0 on XM for GOLD# - the        |
//|     protection it was added for was never actually active. Moved     |
//|     outside that guard.                                              |
//|   - iBarShift() failures in the restoration functions were silent -  |
//|     now logged, since both fail toward trading MORE not less.        |
//|   - MT5's iMA buffer holds 0.0 (not EMPTY_VALUE) before an EMA has    |
//|     enough history - Zenith_Signals.mq5's warm-up guard checked only |
//|     EMPTY_VALUE, so it never actually fired (fixed there too).       |
//|                                                                      |
//|  FOURTH CORRECTNESS PASS - REVERTED the g_barCounter mechanism the   |
//|  second/third passes above introduced (touch/fill/pause/cooldown/    |
//|  MaxBars are back to plain wall-clock, as they were before the       |
//|  second pass). A fourth review found the mechanism's own foundation  |
//|  unsound: iBars() is NOT a safe monotonic "elapsed bars" counter for |
//|  LIVE trading - it can jump forward on a background history re-sync, |
//|  reconnect, or chart-depth change, none of which the Strategy Tester |
//|  can ever exercise (there iBars() only advances one-per-bar). That   |
//|  could reproduce, from a different root cause, the exact same        |
//|  instant-MaxBars-close bug a bar-count-based ticket resync (see       |
//|  below) had just been written to fix - a live-only failure mode no   |
//|  amount of backtesting could ever have caught. Reverting trades a    |
//|  known, accepted ~30% wall-clock-vs-bar-count imprecision across any |
//|  span crossing a weekend for the removal of an unfalsifiable-by-     |
//|  backtest live risk - the same trade-off the pre-second-pass code    |
//|  made originally. This pass ALSO fixed two things found alongside    |
//|  the bar-counter review, kept independent of the revert:              |
//|   - a real live bug, found directly in MT5 Deals-table evidence:      |
//|     g_posOpenBar (now g_posOpenTime) was written only by              |
//|     OnTradeTransaction's DEAL_ENTRY_IN handler, which is not          |
//|     guaranteed to fire before the next ManageOpenPosition() call      |
//|     examines the same new position - on the ticks where it lost that |
//|     race, a stale open time from the PREVIOUS position made MaxBars   |
//|     fire instantly (confirmed live: several positions closed 2-3      |
//|     seconds after entry for a few cents' loss). Fixed with a ticket-  |
//|     keyed self-sync in ManageOpenPosition that resyncs from the       |
//|     position's own real data whenever the ticket doesn't match - and  |
//|     the SAME race, unfixed, was found on g_posPeak/g_posArmed too     |
//|     (read every tick by the trailing-stop logic with no ticket guard  |
//|     at all) - since XM reports a 0 stops level on GOLD#, a stale peak |
//|     there could plant a real, permanent, wrong stop-loss on a brand-  |
//|     new position. Both are now resynced together, keyed on one shared |
//|     g_posStateTicket, so neither can be stale while the other isn't.  |
//|   - circuit-breaker state had no self-sync at all if OnTradeTransaction's |
//|     HistoryDealSelect() ever failed for an exit deal (a documented     |
//|     MT5 timing gap right at TRADE_TRANSACTION_DEAL_ADD) - silently and |
//|     permanently disabling the breaker with nothing to notice. OnTick   |
//|     now detects the open->flat transition itself and calls             |
//|     RestoreCircuitBreakerState() as a backstop, independent of that    |
//|     callback firing or firing in time.                                 |
//|   - this file's D1 EMA warm-up guard was missing the <=0 check          |
//|     Zenith_Signals.mq5 already had (MT5's iMA buffer holds 0.0, not     |
//|     EMPTY_VALUE, before enough history exists) - added here too.        |
//+------------------------------------------------------------------+
//|  VISUAL BUILD (2026-09-05, no trading-logic change - Zenith does not    |
//|  use numbered version bumps this session, per its own established       |
//|  convention; this is an inline note instead): brought up to the same     |
//|  visual standard already shipped to Aurelius_EA.mq5/Fulcrum_EA.mq5/       |
//|  Ratchet_EA.mq5/Daybreak_EA.mq5 this session. Zenith previously had NO     |
//|  chart-theme inputs and NO positioned panel at all - only a single         |
//|  Comment(txt) status line, and only ever drawn from inside OnTick() with     |
//|  no OnInit/timer fallback (a milder version of the exact Fulcrum missing-      |
//|  panel-at-attach bug found and fixed earlier this session - see               |
//|  SESSION_NOTES.md item 3). Added:                                               |
//|   - chart theme (InpApplyTheme/InpChartBg/InpBullCol/InpBearCol), applied         |
//|     via PTheme() at OnInit - same neon-blue/white-on-black palette as the          |
//|     other 4 gold EAs on this account.                                               |
//|   - the full PRect/PText/PSection/PRow/PFrame/PBackground panel primitive             |
//|     set, ported from Aurelius_EA.mq5 (object prefix ZENP_/ZENW_ - this file            |
//|     created no chart objects before, so no clash to adapt around). PFrame()             |
//|     draws the panel's own 4-strip border instead of relying on                          |
//|     OBJ_RECTANGLE_LABEL's own BORDER_FLAT, which this session found renders               |
//|     only 2 of 4 sides live - same fix as the other 4 files.                                |
//|   - DrawPanel() restructures the old one-line Comment(txt) into sectioned                   |
//|     rows: SIGNAL (watching/pending-order counts, straight from the old                        |
//|     Comment() text), CIRCUIT BREAKER (g_pausedUntil/g_consecLosses - already                   |
//|     tracked, just never surfaced on a panel before), POSITION (direction,                        |
//|     entry, current SL, floating P/L, bars held, trailing-armed state - all                        |
//|     already-tracked globals, not new metrics), and ACCOUNT (balance/equity -                       |
//|     no g_dayStartEquity-style "today's P&L" tracking exists anywhere in this                        |
//|     file, unlike Aurelius/Fulcrum/Ratchet, so this shows equity/balance                              |
//|     instead per the task's own fallback rather than inventing a new feature).                         |
//|   - DrawPanel() is now called directly in OnInit() (shows something the                                |
//|     instant the EA attaches) and uses the same g_panelReclaim delete-vs-                                 |
//|     update-in-place mechanism as Aurelius_EA.mq5 (full reclaim once per new                              |
//|     M15 bar; in-place update, throttled to once per unique TimeCurrent()                                  |
//|     second, for the live between-bar refresh) - added proactively here even                               |
//|     though not explicitly requested, because the old between-bar call site                                 |
//|     used to call the (cheap) Comment() on literally every tick with no                                     |
//|     throttle; wiring real chart objects into that exact call site unthrottled                              |
//|     would reproduce the same multi-hour real-tick-backtest slowdown already                                |
//|     found and fixed 3 times this session in Aurelius_EA.mq5 (v1.31-v1.33).                                  |
//|     g_skipCosmeticDraws (same name/purpose as Aurelius_EA.mq5) skips the                                    |
//|     panel entirely in a non-visual Strategy Tester pass.                                                     |
//|   - No signal/entry/exit/risk-sizing/circuit-breaker LOGIC changed anywhere                                  |
//|     in this pass - purely visual/cosmetic, same discipline as every other                                    |
//|     change in this file.                                                                                       |
//+------------------------------------------------------------------+
//|  INDICATOR VISIBILITY (2026-09-06, no trading-logic change - inline note      |
//|  again, not a version bump, same convention as the block above). The Opus     |
//|  deep-dive review (SESSION_NOTES.md item 21) found the same gap across all    |
//|  8 EAs: every one of them computes real indicators/levels internally and      |
//|  draws NOTHING of them on the price chart. The user's requirement is that     |
//|  each EA be self-contained about this - the drawing must work whether or       |
//|  not anything else is ever attached to the chart - so all of it is built       |
//|  natively here rather than delegated to Zenith_Signals.mq5 (that file is       |
//|  untouched and still perfectly usable on its own; this EA simply no longer      |
//|  depends on it being attached for the trader to see what it trades). Added:     |
//|   - the D1 EMA(InpD1EmaPeriod) trend filter - UpdateD1EmaLine(). This is the     |
//|     one hard directional gate on every entry (AdvanceWatchAndOrders' d1Close/    |
//|     d1Ema comparison) and it was invisible everywhere, including in              |
//|     Zenith_Signals.mq5, whose readout only ever printed "UP"/"DOWN" as text.      |
//|     Drawn as one OBJ_TREND segment per D1 bar - the same per-bar-segment          |
//|     technique Aurelius_EA.mq5's DrawMASegment() uses, and for the same reason:     |
//|     an EA has no plot buffers of its own (only an indicator can set                |
//|     PLOT_LINE_COLOR), so ChartIndicatorAdd() could only ever show MT5's own         |
//|     auto-assigned colour, never a chosen one. Adapted to D1-bar granularity        |
//|     rather than the chart's own M15 bars, since that is the timeframe the           |
//|     filter actually reads.                                                          |
//|     NOTE on how the EMA is read: the drawing does its OWN CopyBuffer() rather        |
//|     than widening the existing 2-bar read in OnTick. That read is part of the         |
//|     trading path - a short return from it aborts the whole tick (`if(gotD1Ema         |
//|     < 2) return;`) - and this pass is not allowed to change anything a trading        |
//|     decision depends on, not even its inputs. A separate, failure-tolerant read       |
//|     in the draw function cannot affect an entry no matter what it returns.            |
//|   - the D1 fractal swing zones (BuildD1Zones -> g_d1[]) as OBJ_RECTANGLE boxes,        |
//|     drawn only while a zone is actually live: the box starts at the zone's             |
//|     `known` time (when the fractal was confirmed, i.e. when the EA could first          |
//|     have used it - NOT the pivot bar itself, which would be look-ahead on the           |
//|     chart) and ends at its `bust` time if it has been invalidated, or at the             |
//|     current bar if it is still active. Resistance/support are coloured                   |
//|     separately, matching Zenith_Signals.mq5's own palette so the two files                |
//|     still read identically if a user does happen to run both.                             |
//|   - the H4 confluence zones the EA actually trades (BuildH4Events -> g_ev[]) as           |
//|     OBJ_RECTANGLE boxes over the touch+fill window each one is live for. These             |
//|     are deliberately the UNION zone (H4 zone widened by whatever D1/round-number           |
//|     zone it overlapped), because that union is what the breakout, the limit                |
//|     price and the stop are all computed from - i.e. the geometry actually                  |
//|     traded, not the raw H4 fractal box. BuildH4Events never stores the raw H4              |
//|     zone anywhere (it is a local inside its own loop), and recomputing it here             |
//|     would mean duplicating signal code just to draw it - not worth the drift               |
//|     risk for a strictly less accurate picture.                                              |
//|   - the round-number grid (BuildRoundLevels -> g_rnd[]) as OBJ_HLINEs, one per              |
//|     level midpoint, tooltipped with the level's real half-width band.                       |
//|   - the resting pending entry price (the InpPullbackPct limit) as a dotted                  |
//|     OBJ_TREND plus a small label, read from the live orders themselves                      |
//|     (symbol+magic filtered, exactly like CountOurPendingOrders) rather than from             |
//|     any internal guess - so what is drawn is literally the order the broker is               |
//|     holding. This is the one thing on the chart that answers "why is nothing                 |
//|     happening" when a breakout has fired but price never came back far enough                |
//|     to fill.                                                                                 |
//|   - a "d1 trend" row on the panel (hoisted d1CloseNow/d1EmaNow into                          |
//|     g_d1CloseNow/g_d1EmaNow - a two-line assignment at their existing                        |
//|     computation site, no control flow touched) so the filter's live pass/fail                |
//|     state is readable as text as well as visible as a line.                                  |
//|  All of it is gated behind its own Inp* toggle AND g_skipCosmeticDraws (so a                 |
//|  non-visual Tester pass draws none of it - the same performance discipline as                |
//|  the panel), every new object is OBJPROP_HIDDEN so the Object List stays                     |
//|  usable, and the three new prefixes (ZENL_/ZENZ_/ZENT_) are swept in OnDeinit                |
//|  alongside ZENP_/ZENW_. None of the new prefixes collide with each other, with                |
//|  the panel's, or with Zenith_Signals.mq5's own "ZEN_" (which is ZEN+underscore,               |
//|  a different 4th character from ZENL/ZENZ/ZENT/ZENP/ZENW) - checked directly in                |
//|  both files. Zero signal/entry/exit/risk code touched, same discipline as the                  |
//|  visual build above.                                                                            |
//+------------------------------------------------------------------+
//|  DIAGNOSTIC PASS (2026-09-07): user-reported bug - zones built successfully   |
//|  (Journal confirmed "first confluence event generated ... D1 zones: 798,      |
//|  round levels: 93" - the exact same OnTick block that also draws the panel,   |
//|  which the user confirmed IS rendering) but no S/R blocks visible on the       |
//|  chart. Re-read BuildD1Zones/DrawZoneObjects/the OnTick gating end to end -     |
//|  found no logic bug (defaults all on, InpZoneHistoryDays keeps any live zone    |
//|  visible regardless of formation age, geometry checks are sound). Found ONE     |
//|  real gap instead: ZSegment()/ZZoneBox()/the round-level OBJ_HLINE creation      |
//|  never checked ObjectCreate()'s return value - a silent failure (chart object    |
//|  cap, invalid coordinate, etc.) would let BuildD1Zones/DrawZoneObjects both       |
//|  report success while nothing actually painted, exactly matching what was         |
//|  reported. Added: each now checks ObjectCreate()'s return and logs once per        |
//|  session (PrintFormat with GetLastError()) on failure rather than silently          |
//|  proceeding to call ObjectSetInteger on a name that was never created. This is       |
//|  a diagnostic/defensive addition, not a guessed fix - the next live/visual run        |
//|  will either show zones now (if MT5 was fine and this was a red herring) or log        |
//|  the exact ObjectCreate error code, which pins down the real cause immediately.          |
//+------------------------------------------------------------------+
#property copyright "Zenith"
#property version   "1.00"
#include <Trade/Trade.mqh>

CTrade trade;

//--- construction inputs (must match Zenith_Signals.mq5's validated defaults)
input int    InpP_D1            = 2;      // validated: more D1 pivots -> +14% more trades, similar quality, drawdown barely moves
input int    InpP_H4            = 4;      // validated alongside InpP_D1 - going smaller still (e.g. 2/3) overshoots and hurts quality
input double InpD1BufATR        = 0.5;
input double InpRoundStep       = 50.0;
input double InpRoundHalf       = 2.5;
input int    InpMinH4Hits       = 0;      // validated best: first touch counts, no retest required
input double InpBustMarginATR   = 0.25;
input int    InpTouchGapH4      = 2;
input int    InpTouchWindowBars = 24;
input double InpPullbackPct      = 0.257;  // was InpPullbackUSD=5.0, then briefly InpPullbackATR=0.5844
                                           // (an H4-ATR multiple) - see the 2026-09-05 Opus review
                                           // (SESSION_NOTES.md item 18, Finding A) for why the ATR-multiple
                                           // version was itself wrong: H4 ATR/price roughly DOUBLED
                                           // 2023->2026 while price only ~2.4x'd, so an ATR-multiple offset
                                           // overcorrects and requires an ever-deeper pullback to fill,
                                           // which is exactly what dropped 33 real entries worth +$812 in
                                           // the fresh backtest. A pure price-percentage offset tracks
                                           // price only (not the extra ATR-vs-price divergence), matching
                                           // the original $5 offset's real behaviour more closely across
                                           // the whole period. Calibrated from $5.0 / 2023's real median
                                           // H4 close ($1,945.55) = 0.257%. NEEDS a fresh backtest to
                                           // confirm entry frequency is actually restored - this is a
                                           // calibration, not an independently re-validated result.
input int    InpFillWindowBars  = 24;
input double InpFixedTargetATR  = 5.844;   // was InpFixedTargetUSD=50.0 - same ATR-multiple conversion,
                                           // only used when InpUseTrailingExit = false
input bool   InpUseTrailingExit = true;   // validated best: beats the flat $50 target on FULL/TRAIN/HOLD alike
input double InpTrailActivateATR= 7.013;   // was InpTrailActivateUSD=60.0 - arm the trail once profit
                                           // reaches this many x the CURRENT H4 ATR (CurrentH4ATR(), not
                                           // the entry-time watchAtr - a trail should react to how much
                                           // room the market needs NOW, not whatever it needed at entry)
input double InpTrailATR        = 3.506;   // was InpTrailUSD=30.0 - once armed, stop trails this far (x
                                           // current H4 ATR) behind the peak
input double InpStopBufATR      = 0.3;
input double InpMaxLossATR      = 3.506;   // was InpMaxLossUSD=30.0
input double InpMinLossATR      = 0.935;   // was InpMinLossUSD=8.0 - floor: stop is never closer than this
                                           // many x H4 ATR from entry - a near-zero stop (low-ATR regime)
                                           // would otherwise be near-guaranteed to hit immediately, and
                                           // would blow up the risk-percent lot size (division by a near-
                                           // zero stop distance) into a max-lot position instead of a
                                           // skipped trade
input double InpMaxLossCapUSD   = 65.0;   // hard $ ceiling on the entry-to-stop distance, applied on top of
                                           // InpMaxLossATR/InpMinLossATR above - see the 2026-09-05 Opus
                                           // review comment at its use site for why this was re-added after
                                           // the ATR conversion removed the original flat InpMaxLossUSD=$30
                                           // cap. 0 disables it. Direct price-distance cap, so at fixed
                                           // 0.01 lots (GOLD#'s 100oz contract size) this IS the max-loss-
                                           // per-trade in dollars; scale it up if trading larger fixed lots.
                                           // NOTE (2026-09-06): "USD" here means gold's OWN quote currency
                                           // (gold trades in USD worldwide) - it is not tied to whatever
                                           // currency the trading account itself is funded in, and needs no
                                           // adjustment for that. MT5 converts the real profit/loss into the
                                           // account's own deposit currency automatically at the live
                                           // exchange rate, exactly as it would for any other price-based
                                           // stop distance - this input never touches account currency.
                                           // RAISED 30.0->65.0 (2026-09-06, Opus review of a real backtest
                                           // with the cap at 30.0): at 30.0 the cap bound on 100% of 2026
                                           // trades, not just tail cases - reintroducing the exact problem
                                           // the ATR conversion existed to fix (item 12: the old flat $30
                                           // was binding on 92% of 2026 losses, meaning the "ATR-adaptive"
                                           // stop was barely ever the real exit). 65.0 sits above
                                           // InpMinLossATR's floor requirement in a typical 2026 month
                                           // (~$38 at 0.935x that year's ~$41 median H4 ATR), so the
                                           // ATR-adaptive stop/floor can do their job in ordinary
                                           // conditions again, while still bounding a repeat of the
                                           // 2026-03 volatility spike (ATR ~$87, which would otherwise cost
                                           // ~$254/trade at 0.01 lots) to ~2.2% of a $3,000 account. Needs
                                           // a fresh backtest to confirm - not independently re-validated.
input bool   InpUseD1Trend      = true;
input int    InpD1EmaPeriod     = 50;
input int    InpCooldownBars    = 5;
input int    InpMaxBars         = 400;
input int    InpMaxSpreadPoints = 60;
input bool   InpHoldOverWeekend = false;  // false = close before weekend (the validated/chosen default)
input int    InpMaxConsecLosses = 2;      // pause new entries after this many losses in a row (0 = disabled)
input int    InpPauseBars       = 672;    // M15 bars to pause for once the streak threshold is hit
                                           // VALIDATED (2026-09-06, item 20): 672 bars = 168h = 7 days. Real
                                           // backtest results (all at InpMaxLossCapUSD=65.0, same period):
                                           //   no breaker (400, inert): net ~$617-623, DD ~9.0%, worst
                                           //     streak 5 losses/-$265 (confirmed across 3 separate runs)
                                           //   672 (7 days) -> net $665.88, DD 7.34% ($269), PF 1.535,
                                           //     worst streak 6 losses/-$74 - BEATS the no-breaker baseline
                                           //     on profit, drawdown, AND worst-streak cost simultaneously
                                           //   1344 (14 days) -> net $550.31, DD 7.64% ($238), worst streak
                                           //     6 losses/-$79 - TOO aggressive, costs real profit despite
                                           //     slightly better drawdown than 672
                                           // 672 is the sweet spot found so far: mild enough to avoid the
                                           // path-dependent over-filtering that hurt at 1344 (this system's
                                           // state changes when a trade is skipped, so a longer pause can
                                           // remove more good trades than bad ones - don't assume "more
                                           // pause = more safety", it isn't monotonic here), aggressive
                                           // enough to actually skip the worst clusters. Note: NOT chosen by
                                           // simulation this time - 400, 672, and 1344 were all real MT5
                                           // backtests; this is the best of the three tested, not proven
                                           // optimal among untested values. If exploring further, test real
                                           // values only (e.g. something between 400-672 or 672-1344) -
                                           // don't extrapolate a trend from just these three points.

//--- history depth
input int    InpD1Bars          = 3000;
input int    InpH4Bars          = 8000;

//--- execution
input double InpLotSize         = 0.01;    // used as-is when InpUseRiskPercent = false (the validated backtest's assumption)
input bool   InpUseRiskPercent  = false;   // true = size each trade off account equity instead of a fixed lot
input double InpRiskPercent     = 1.0;     // % of current equity risked per trade, only used when InpUseRiskPercent = true
input ulong  InpMagic           = 750210;
input int    InpSlippagePoints  = 20;
input int    InpOrderRetries    = 3;       // retry an order this many times on a transient rejection (requote/timeout/price changed)
input bool   InpShowPanel       = true;

//--- chart theme - visual build, 2026-09-05. Zenith had no chart-theme inputs
//--- at all before this - matches the other 4 gold EAs (Aurelius/Fulcrum/
//--- Ratchet/Daybreak) exactly, so all 5 read as one product on one account.
input bool   InpApplyTheme      = true;              // Recolour the chart
input color  InpChartBg         = clrBlack;           // Chart background - matches the other 4 gold EAs
input color  InpBullCol         = C'0,150,255';       // Bullish candle - neon blue, same as the other 4
input color  InpBearCol         = clrWhite;           // Bearish candle - neon white, same as the other 4

//--- dashboard (neon panel) - visual build, 2026-09-05. Replaces the old
//--- Comment()-only status line with the same PRect/PText/PSection/PRow/
//--- PFrame panel system Aurelius/Fulcrum/Ratchet/Daybreak already use, so
//--- this EA looks and behaves like the rest of the family instead of
//--- standing out as plain text. See DrawPanel()'s own header for what
//--- moved where.
input int    InpPanelDrag       = 1;                  // 0 = locked, 1 = draggable
input int    InpPanelX          = 12;                 // X offset
input int    InpPanelY          = 30;                 // Y offset - matches Aurelius/Fulcrum/Ratchet (below MT5's own symbol/OHLC header bar)
input int    InpPanelW          = 240;                // Width floor - self-learning, grows to fit long values (see g_panelMinW)
input color  InpPanelBg         = C'13,17,28';        // Panel background - matches Aurelius/Fulcrum/Ratchet/Daybreak
input color  InpHeaderBg        = C'28,36,58';        // Header / section background
input color  InpPanelEdge       = C'0,150,255';       // Border - neon blue, matches the bull candle colour (Fulcrum/Ratchet's
                                                       // convention - see SESSION_NOTES.md item on the panel-colour standard)
input color  InpTitleCol        = C'255,196,84';      // Title text - gold
input color  InpSectionCol      = C'214,226,238';     // Section headings - silver
input color  InpTextCol         = C'150,166,192';     // Labels
input color  InpValCol          = C'236,242,252';     // Values
input color  InpOkCol           = C'0,230,118';       // Met/good - neon green
input color  InpNoCol           = C'255,61,90';       // Not met/bad - hot red
input color  InpShadowCol       = C'6,8,14';          // Drop shadow
input string InpPanelFont       = "Consolas";         // Font
input int    InpPanelSize       = 8;                  // Font size
input string InpBackgroundBMP   = "";                 // Background image (.bmp in MQL5\Images) - optional, off by default (no asset shipped for Zenith)
input int    InpBgWidth         = 1290;               // Image width (px) - for centring only, only matters if InpBackgroundBMP is set
input int    InpBgHeight        = 720;                // Image height (px) - for centring only, only matters if InpBackgroundBMP is set
// WATERMARK (2026-09-06): this file's PBackground() comment used to say
// "no watermark - not part of this file's scope", a deliberate decision at
// the time item 14 built out Zenith's visual standard - Aurelius/Fulcrum/
// Ratchet/Daybreak all have one, Zenith didn't, and the user flagged it as
// a real gap. Text-based, same mechanism as Daybreak_EA.mq5's PWatermark()
// (deliberately subtle/muted, not neon, tinting empty chart space and
// never sitting on top of price action).
input bool   InpShowWatermark   = true;
input string InpWatermarkText   = "ZENITH";
input color  InpWatermarkColor  = C'40,36,26';        // deliberately subtle, not neon - matches the other four's convention
input int    InpWatermarkSize   = 42;
input string InpWatermarkFont   = "Arial Black";

//--- chart drawing of the levels this EA actually trades - indicator-visibility
//--- build, 2026-09-06 (see the header block of the same name). Every toggle
//--- here is cosmetic-only: none of them is read anywhere near a signal, entry,
//--- exit or sizing decision, and all of them are additionally gated behind
//--- g_skipCosmeticDraws so a non-visual Tester pass draws nothing at all. The
//--- colour defaults deliberately match Zenith_Signals.mq5's own, so the chart
//--- reads the same whichever of the two happens to be drawing it.
input bool   InpShowD1Ema        = true;              // Draw the D1 EMA trend-filter line (the hard directional gate on every entry)
input int    InpD1EmaHistoryBars = 200;               // How many D1 bars of that line to keep on the chart (one OBJ_TREND segment per bar)
input color  InpColD1Ema         = C'255,196,84';     // D1 EMA line - gold, matching the panel title
input bool   InpShowD1Zones      = true;              // Draw the D1 fractal swing zones (BuildD1Zones)
input bool   InpShowH4Zones      = true;              // Draw the H4 confluence zones actually traded (BuildH4Events)
input bool   InpShowRoundLevels  = true;              // Draw the round-number grid (BuildRoundLevels)
input bool   InpShowPendingLine  = true;              // Draw the resting limit-order price (the InpPullbackPct offset)
input int    InpZoneHistoryDays  = 120;               // Only draw zones still live, or busted, within this many days - a 3000-bar
                                                       // D1 history builds hundreds of zones and an 8000-bar H4 history thousands
                                                       // of confluence events; drawing all of them would bury the chart AND churn
                                                       // thousands of objects on every M15 bar
input int    InpMaxZoneObjects   = 250;                // Hard per-family object cap on top of InpZoneHistoryDays, so a
                                                       // misconfigured history/step can never flood the chart
input color  InpColD1Res         = C'255,90,90';      // D1 resistance zone - brightened 2026-09-07 (now an
                                                       // outline drawn in FRONT of candles, not a muted BACK
                                                       // fill - see ZZoneBox()'s header for why)
input color  InpColD1Sup         = C'70,160,255';     // D1 support zone - brightened alongside InpColD1Res, same reason
input color  InpColRound         = clrGray;           // Round-number level
input color  InpColConfluence    = C'255,210,60';     // H4 confluence zone (the union zone actually traded) -
                                                       // brightened alongside the two above, same reason
input color  InpColPending       = clrSilver;         // Resting limit-order price

//--- data structs (identical construction to Zenith_Signals.mq5)
struct D1Zone { double hi, lo; bool isRes; datetime known; datetime bust; };
struct RoundLvl { double hi, lo; };
struct ConfEvent { datetime t; int dirn; double hi, lo, atr; };
struct WatchEv { datetime evTime; int dirn; double hi, lo, atr; datetime expire; };
// hi/lo are part of the key, not just evTime+dirn - multiple DIFFERENT
// zones can register a confluence touch at the exact same H4 bar and
// direction (proven against the Python event list: 220 of 558 unique
// timestamp/direction pairs in one test window had 2-4 different zones
// touching simultaneously, each with its own hi/lo/ATR). Python's
// validated run()/run_confirmed() never deduplicates by time+dirn alone -
// every entry in confluence_events becomes its own independently-watched
// setup. Keying only on evTime+dirn here was silently discarding every
// zone but the first at a shared timestamp - the real cause of the live
// EA generating far fewer signals than Python predicted for the same
// window (922 raw events collapse to exactly 558 when deduped by
// time+dirn alone, matching the live shortfall almost exactly).
struct HandledKey { datetime evTime; int dirn; double hi; double lo; };

D1Zone     g_d1[];
RoundLvl   g_rnd[];
ConfEvent  g_ev[];
// Both RAM-only, unlike g_consecLosses/g_pausedUntil/g_lastCloseTime/
// g_posPeak/g_posArmed (see RestoreCircuitBreakerState/RestoreTrailingState)
// - a restart within roughly the last 10.5h (the recency window at the top
// of AdvanceWatchAndOrders) could re-admit an event this run already acted
// on, since g_handled comes back empty. Deliberately not persisted: the
// residual risk is small (the event would still need a genuinely fresh
// price move to break out again, and CountOurPendingOrders()/HasOpenPosition
// still block a second REAL order/position regardless), and correctly
// reconstructing exactly which zones were mid-watch is materially more
// involved than the datetime/double state above - not worth it for what
// it would prevent given everything else already guarding this file.
WatchEv    g_watch[];
HandledKey g_handled[];   // events we've already acted on (placed an order, or let expire) - avoid reprocessing

datetime g_lastBar = 0;
datetime g_lastCloseTime = 0;
int      g_consecLosses = 0;
datetime g_pausedUntil = 0;   // new entries blocked while TimeCurrent() < this
double   g_posPeak = 0;       // best price seen so far on the current open position (trailing exit)
bool     g_posArmed = false;  // has the trail activated yet on the current open position
ulong    g_posStateTicket = 0; // which ticket g_posPeak/g_posArmed/g_posOpenTime were last synced to - see
                                // ManageOpenPosition's self-sync (a real bug found by review: these used to
                                // be written only by OnTradeTransaction's DEAL_ENTRY_IN handler, which can
                                // fire late relative to ManageOpenPosition - on those ticks the PREVIOUS
                                // position's stale peak/armed state could plant a wrong SL on the new one)
datetime g_posOpenTime = 0;    // this position's real open time, kept alongside the ticket above for MaxBars
bool     g_hadPosition = false; // for detecting the open->flat transition in OnTick - see the circuit
                                 // breaker resync there, which no longer depends on OnTradeTransaction
                                 // firing (or firing in time) for the loss-streak tracking to stay correct
int      g_emaD1Handle = INVALID_HANDLE;
//--- last D1 close / D1 EMA the trend filter actually ran on. Hoisted out of
//--- OnTick's new-bar block (2026-09-06) purely so DrawPanel() can show the
//--- filter's live state - the values are still computed in exactly the same
//--- place, from exactly the same data, and are still passed to
//--- AdvanceWatchAndOrders() as arguments; these two globals are written
//--- alongside that and read by nothing except the panel. 0.0 = not yet known
//--- (before the first completed new-bar pass), which the panel shows as "-".
double   g_d1CloseNow = 0.0;
double   g_d1EmaNow   = 0.0;

//--- panel/theme state - visual build, 2026-09-05. See DrawPanel()'s own
//--- header for the primitive system this ports from Aurelius_EA.mq5.
string   g_pp = "ZENP_";    // panel objects - deleted/recreated (reclaim) or updated in place, see g_panelReclaim
string   g_pw = "ZENW_";    // background bitmap AND text watermark (2026-09-06) - both swept together
//--- indicator-visibility build, 2026-09-06. Three separate prefixes rather
//--- than one, because the three families have genuinely different lifecycles:
//--- the EMA line is rebuilt once per D1 bar, the zones/levels once per M15
//--- bar, and the pending line whenever an order appears or fills. Sharing one
//--- prefix would mean wiping and redrawing ~200 EMA segments every M15 bar
//--- just to refresh a zone box. All three are swept in OnDeinit, and none
//--- collides with ZENP_/ZENW_ above or with Zenith_Signals.mq5's "ZEN_"
//--- (different 4th character - checked in both files).
string   g_pl = "ZENL_";    // D1 EMA trend-filter line - one OBJ_TREND per D1 bar
string   g_pz = "ZENZ_";    // D1 zones / H4 confluence zones / round-number levels
string   g_pt = "ZENT_";    // resting pending-order price line + label
int      g_panX = -1, g_panY = -1;   // live panel position, updated by dragging; -1 = not yet placed
int      g_panelMinW = 0;            // self-learning minimum width - see PRow
bool     g_panelReclaim = true;      // true = delete+recreate (reclaim top-of-stack), false = update in place -
                                      // see PRect/PText's own comments; identical mechanism to Aurelius_EA.mq5,
                                      // needed here too since MT5's own trade-fill arrows/lines are created
                                      // AFTER the panel and would otherwise render on top of it
bool     g_bgOK = false;             // background image loaded successfully (or none configured)
int      g_bgTries = 0;
bool     g_skipCosmeticDraws = false; // true only for a non-visual Strategy Tester pass - same PERFORMANCE FIX
                                       // as Aurelius_EA.mq5 v1.32/v1.33: skips the panel entirely there, since
                                       // nobody can see it and a multi-year real-tick backtest would otherwise
                                       // redraw ~20 rows x 3 objects on every unique second AND (worse) every
                                       // single tick while a position sits flat mid-bar - the exact class of
                                       // slowdown already found and fixed 3 times this session in Aurelius.

// diagnostic funnel counters - printed once at OnDeinit so a run's
// signal funnel can be compared directly against the Python prediction
// for the same window (added to chase the Backtest_6/Forward_6 gap:
// real n=44 vs predicted n=63 for the same period)
long g_cntEventsWatched   = 0;   // confluence events added to the watch list
long g_cntWatchExpired    = 0;   // watched events that expired with no breakout
long g_cntBreakouts       = 0;   // breakout confirmations seen (watch -> candidate)
long g_cntSkipPaused      = 0;   // breakout candidates skipped while circuit-breaker paused
long g_cntSkipD1Trend     = 0;   // breakout candidates skipped by the D1 trend filter
long g_cntSkipSpread      = 0;   // breakout candidates skipped by the spread filter
long g_cntSkipCooldown    = 0;   // breakout candidates skipped by cooldown
long g_cntSkipFriday      = 0;   // breakout candidates skipped by the Friday no-entry rule
long g_cntSkipHoliday     = 0;   // breakout candidates skipped by IsMarketHoliday
long g_cntSkipGeometry    = 0;   // breakout candidates skipped: invalid stop >= entry
long g_cntSkipStopsLevel  = 0;   // breakout candidates skipped: inside the broker's min stop/freeze distance
long g_cntSkipLotZero     = 0;   // breakout candidates skipped: computed lot size <= 0
long g_cntSkipNoATR       = 0;   // breakout candidates skipped: CurrentH4ATR() unavailable (cold-start only)
long g_cntOrdersPlaced    = 0;   // orders actually sent to PlaceLimitOrderWithRetry

//--- forward declarations: OnInit draws the panel before these are defined,
//--- same as Aurelius_EA.mq5
void PTheme();
void PBackground();
void PWatermark();
void DrawPanel(const bool reclaim = true);

//+------------------------------------------------------------------+
int OnInit()
  {
   // The one input value that can actually hang the terminal if misconfigured:
   // BuildRoundLevels' `while(lvl <= hiPx + InpRoundStep) lvl += InpRoundStep;`
   // never terminates if InpRoundStep <= 0 (lvl never advances, or runs away
   // in the wrong direction). Everything else non-sensical (P_D1/P_H4 <= 0,
   // negative buffers) degrades to a harmless no-op or nonsense zones rather
   // than a hang or crash, so this is the one case worth failing init over.
   if(InpRoundStep <= 0)
     {
      PrintFormat("Zenith_EA: InpRoundStep must be > 0 (got %.2f) - refusing to start", InpRoundStep);
      return(INIT_PARAMETERS_INCORRECT);
     }
   // Kept in sync with Zenith_Signals.mq5's guard (there it's a genuine
   // array-out-of-range risk; here a negative value would just corrupt
   // the bar-count arithmetic in nonsensical ways, but the same input
   // should be rejected the same way in both files regardless).
   if(InpTouchWindowBars < 0 || InpFillWindowBars < 0 || InpPauseBars < 0)
     {
      PrintFormat("Zenith_EA: InpTouchWindowBars/InpFillWindowBars/InpPauseBars must be >= 0 "
                  "(got %d/%d/%d) - refusing to start", InpTouchWindowBars, InpFillWindowBars, InpPauseBars);
      return(INIT_PARAMETERS_INCORRECT);
     }
   // Not fatal, just a heads-up: RestoreTrailingState() infers whether the
   // trail is armed from whether the position's current SL has moved
   // beyond entry - which only works when an armed trail's SL is
   // guaranteed to be past entry, i.e. InpTrailActivateATR >= InpTrailATR
   // (true for the shipped defaults, 7.013 >= 3.506 - both are x the same
   // ATR reading at any instant, so comparing the multiples directly is
   // equivalent to comparing the dollar amounts they'd produce). With
   // activate < trail, an already-armed position's SL can sit BELOW entry,
   // and a restart would silently read that back as "not armed yet" instead.
   if(InpUseTrailingExit && InpTrailActivateATR < InpTrailATR)
      PrintFormat("Zenith_EA: WARNING - InpTrailActivateATR (%.3f) < InpTrailATR (%.3f). A restart while a "
                  "trade is open and already armed may not correctly restore that armed state.",
                  InpTrailActivateATR, InpTrailATR);
   // 2026-09-06 (Opus deep-dive review): InpMaxLossCapUSD is a raw PRICE
   // distance (see its own declaration comment) with no lot-size guard -
   // the same trap item 19 already found and warned about in Fulcrum's
   // TargetDistance(). Real dollar loss at fixed lots = cap * (InpLotSize/
   // 0.01), and under InpUseRiskPercent it's worse: ComputeLotSize()
   // divides the risk budget by the CAPPED stop distance, so raising
   // InpLotSize or enabling risk-percent sizing doesn't just change
   // position size here, it changes what this "cap" actually bounds - or,
   // under risk-percent, stops bounding dollars at all. Warn rather than
   // let either happen silently.
   if(InpMaxLossCapUSD > 0.0 && (InpUseRiskPercent || MathAbs(InpLotSize - 0.01) > 1e-9))
      PrintFormat("Zenith_EA: WARNING - InpMaxLossCapUSD (%.2f) is a PRICE distance, not an account-currency "
                  "dollar bound. At InpLotSize=%.2f it equals %.2f real dollars of risk, and under "
                  "InpUseRiskPercent it does not bound dollars at all (a wider capped stop just gets a bigger "
                  "computed lot size).", InpMaxLossCapUSD, InpLotSize, InpMaxLossCapUSD * (InpLotSize / 0.01));
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);   // CTrade defaults to FOK, which some brokers/symbols reject outright -
                                             // this reads the symbol's actually-allowed filling mode instead, so
                                             // PositionClose() (Friday/MaxBars exits) doesn't silently fail with
                                             // retcode 10030 on a broker that doesn't support FOK on GOLD#.
   // NOTE: D1/H4 ATR is now computed manually (see ComputeWilderATR) instead
   // of via the built-in iATR() handle - a real GOLD# D1 export (Zenith_
   // ExportD1.mq5) proved this broker's iATR is actually a plain SMA(14) of
   // True Range, not Wilder smoothing, even though MT5's own docs describe
   // ATR as Wilder-smoothed. Every zone width in this system (D1BufATR,
   // BustMarginATR, StopBufATR) was tuned in Python against genuine Wilder
   // ATR, so trusting iATR() here was silently shrinking/widening zones all
   // along and is the leading suspect for the real-vs-Python signal gap.
   g_emaD1Handle  = iMA(_Symbol, PERIOD_D1, InpD1EmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_emaD1Handle == INVALID_HANDLE)
     {
      Print("Zenith_EA: failed to create an indicator handle");
      return(INIT_FAILED);
     }
   // Circuit-breaker/cooldown/trailing state lives only in these globals,
   // which reset to zero on any recompile, input change, or terminal
   // restart - exactly the moments a real account is most likely to be
   // sitting mid-losing-streak or mid-trade. Reconstruct both from real
   // MT5 history/position data so a restart can't silently cancel an
   // active pause or disarm an already-profitable trailing stop.
   RestoreCircuitBreakerState();
   RestoreTrailingState();
   PrintFormat("Zenith_EA ACTUAL RUNNING INPUTS -> P_D1=%d P_H4=%d | Trailing=%s Activate=%.3fxATR Trail=%.3fxATR FixedTarget=%.3fxATR (current H4 ATR=%.2f) | MaxConsecLosses=%d PauseBars=%d | UseRiskPercent=%s RiskPercent=%.2f LotSize=%.2f | MaxSpreadPts=%d HoldOverWeekend=%s",
              InpP_D1, InpP_H4,
              (InpUseTrailingExit ? "true" : "false"), InpTrailActivateATR, InpTrailATR, InpFixedTargetATR, CurrentH4ATR(),
              InpMaxConsecLosses, InpPauseBars,
              (InpUseRiskPercent ? "true" : "false"), InpRiskPercent, InpLotSize,
              InpMaxSpreadPoints, (InpHoldOverWeekend ? "true" : "false"));

   //--- visual build, 2026-09-05: same PERFORMANCE FIX as Aurelius_EA.mq5
   //--- v1.32 - a non-visual Strategy Tester pass has no chart anyone can
   //--- see, so skip every cosmetic draw there entirely rather than churn
   //--- chart objects millions of times across a multi-year real-tick run.
   g_skipCosmeticDraws = MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE);
   PTheme();                          // theme applies even with the panel off
   if(!g_skipCosmeticDraws) { PBackground(); PWatermark(); }
   if(InpShowPanel && !g_skipCosmeticDraws)
     {
      DrawPanel();                    // show something the moment it attaches -
      ChartRedraw(0);                 // the exact fix already applied to Aurelius/Fulcrum/Ratchet's
     }                                // panels this session (see SESSION_NOTES.md item 3)
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_pp);
   ObjectsDeleteAll(0, g_pw);
   //--- indicator-visibility build, 2026-09-06: the three new drawing families
   //--- get swept here too, same as the panel/background above - otherwise
   //--- removing the EA would leave up to InpD1EmaHistoryBars EMA segments plus
   //--- every zone box and level line stranded on the chart with nothing left
   //--- to clean them up.
   ObjectsDeleteAll(0, g_pl);
   ObjectsDeleteAll(0, g_pz);
   ObjectsDeleteAll(0, g_pt);
   // clears the wrong-timeframe Comment() (see OnTick's guard) so it doesn't
   // stay stuck on the chart forever after this EA is removed - found in
   // review.
   Comment("");
   // %I64d, not %d: these counters are `long` (64-bit) - MQL5's PrintFormat
   // requires %I64d for a long argument, %d is for int. These are exactly
   // the numbers used to reconcile the live signal funnel against Python's
   // prediction, so a format mismatch here would corrupt the one
   // diagnostic this whole investigation has depended on.
   PrintFormat("Zenith_EA SIGNAL FUNNEL -> watched=%I64d expired=%I64d breakouts=%I64d "
               "| skipped: paused=%I64d d1trend=%I64d spread=%I64d cooldown=%I64d friday=%I64d holiday=%I64d geometry=%I64d stopslevel=%I64d lotzero=%I64d noatr=%I64d "
               "| ordersPlaced=%I64d",
               g_cntEventsWatched, g_cntWatchExpired, g_cntBreakouts,
               g_cntSkipPaused, g_cntSkipD1Trend, g_cntSkipSpread, g_cntSkipCooldown,
               g_cntSkipFriday, g_cntSkipHoliday, g_cntSkipGeometry, g_cntSkipStopsLevel, g_cntSkipLotZero, g_cntSkipNoATR,
               g_cntOrdersPlaced);
   IndicatorRelease(g_emaD1Handle);
  }

//+------------------------------------------------------------------+
//| Manual Wilder ATR, matching the Python atr_wilder() implementation |
//| this whole system was validated against exactly (SMA seed of the  |
//| first `period` true ranges landing at index `period`, then Wilder |
//| recursive smoothing). Deliberately NOT the built-in iATR() - a    |
//| real GOLD# D1 export (Zenith_ExportD1.mq5) proved this broker's   |
//| iATR is actually a plain SMA(14) of True Range, not Wilder        |
//| smoothing, despite MT5's own docs describing ATR as Wilder-       |
//| smoothed. arr[] must be in ascending (oldest-first) order, same   |
//| as CopyRates(..., ArraySetAsSeries(..., false)) returns.          |
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
//| Live, on-demand H4 ATR(14) for the trailing-exit inputs           |
//| (InpTrailATR/InpTrailActivateATR), which manage an already-OPEN    |
//| position rather than a zone candidate - watchAtr (the H4 ATR         |
//| snapshotted when the zone/event was built) isn't in scope there,       |
//| and using it would freeze the trail at entry-time volatility for an     |
//| exit mechanism that should react to current conditions instead. Same     |
//| ComputeWilderATR() this file already uses for zones (deliberately NOT      |
//| the built-in iATR() - see BuildD1Zones/BuildH4Events' own header note        |
//| on why). Caches the last valid read so a single tick's CopyRates() coming     |
//| back short doesn't zero out the trail thresholds mid-trade.                     |
//+------------------------------------------------------------------+
double g_lastGoodH4ATR = 0.0;
double CurrentH4ATR()
  {
   MqlRates h4[];
   ArraySetAsSeries(h4, false);
   // start_pos=1, not 0 - skips the still-forming H4 bar, matching every
   // other rates read in this file (see AdvanceWatchAndOrders's own header
   // comment on why start_pos=0 "was the bug that caused zero trades").
   // With Wilder-14 the forming bar carries ~7% weight, which would
   // otherwise make the trail distance wobble intra-bar for no reason -
   // found in review.
   int copied = CopyRates(_Symbol, PERIOD_H4, 1, 40, h4);
   if(copied >= 15)
     {
      double atr[];
      ComputeWilderATR(h4, atr, 14);
      int last = ArraySize(atr) - 1;
      if(last >= 0 && atr[last] != EMPTY_VALUE && atr[last] > 0.0)
         g_lastGoodH4ATR = atr[last];
     }
   return(g_lastGoodH4ATR);   // 0.0 if no valid read has ever happened yet
  }

//+------------------------------------------------------------------+
bool IsFractal(const double &arr[], int i, int P, bool wantHigh)
  {
   int n = ArraySize(arr);
   if(i - P < 0 || i + P >= n) return(false);
   double v = arr[i];
   for(int j = i - P; j < i; j++)
     {
      if(wantHigh) { if(arr[j] > v) return(false); }
      else         { if(arr[j] < v) return(false); }
     }
   for(int j = i + 1; j <= i + P; j++)
     {
      if(wantHigh) { if(arr[j] >= v) return(false); }
      else         { if(arr[j] <= v) return(false); }
     }
   return(true);
  }

bool Overlaps(double aHi, double aLo, double bHi, double bLo)
  {
   return(MathMax(aLo, bLo) <= MathMin(aHi, bHi));
  }

void BuildD1Zones(const MqlRates &d1[], const double &d1Atr[])
  {
   int n = ArraySize(d1);
   ArrayResize(g_d1, 0);
   double hiSrc[], loSrc[]; ArrayResize(hiSrc, n); ArrayResize(loSrc, n);
   for(int k = 0; k < n; k++) { hiSrc[k] = d1[k].high; loSrc[k] = d1[k].low; }
   for(int i = 0; i < n; i++)
     {
      double a = d1Atr[i];
      if(a <= 0 || a == EMPTY_VALUE) continue;
      double buf = InpD1BufATR * a;
      for(int side = 0; side < 2; side++)
        {
         bool wantHigh = (side == 0);
         bool isFrac = wantHigh ? IsFractal(hiSrc, i, InpP_D1, true) : IsFractal(loSrc, i, InpP_D1, false);
         if(!isFrac) continue;
         double hi_, lo_;
         if(wantHigh) { hi_ = d1[i].high + buf; lo_ = d1[i].high - buf; }
         else         { hi_ = d1[i].low  + buf; lo_ = d1[i].low  - buf; }
         datetime known = (i + InpP_D1 < n) ? d1[i + InpP_D1].time : 0;
         if(known == 0) continue;
         datetime bust = 0;
         double margin = InpBustMarginATR * a;
         for(int j = i + InpP_D1 + 1; j < n; j++)
           {
            if(wantHigh && d1[j].close > hi_ + margin) { bust = d1[j].time; break; }
            if(!wantHigh && d1[j].close < lo_ - margin) { bust = d1[j].time; break; }
           }
         int cnt = ArraySize(g_d1);
         ArrayResize(g_d1, cnt + 1);
         g_d1[cnt].hi = hi_; g_d1[cnt].lo = lo_; g_d1[cnt].isRes = wantHigh;
         g_d1[cnt].known = known; g_d1[cnt].bust = bust;
        }
     }
  }

void BuildRoundLevels(double loPx, double hiPx)
  {
   ArrayResize(g_rnd, 0);
   double lvl = MathFloor(loPx / InpRoundStep) * InpRoundStep;
   while(lvl <= hiPx + InpRoundStep)
     {
      int cnt = ArraySize(g_rnd);
      ArrayResize(g_rnd, cnt + 1);
      g_rnd[cnt].hi = lvl + InpRoundHalf;
      g_rnd[cnt].lo = lvl - InpRoundHalf;
      lvl += InpRoundStep;
     }
  }

bool D1ActiveOverlap(double hHi, double hLo, datetime t, double &outHi, double &outLo)
  {
   bool found = false; double bestHi = 0, bestLo = 0;
   for(int i = 0; i < ArraySize(g_d1); i++)
     {
      if(g_d1[i].known > t) continue;
      if(g_d1[i].bust != 0 && g_d1[i].bust <= t) continue;
      if(Overlaps(hHi, hLo, g_d1[i].hi, g_d1[i].lo))
        {
         double uh = MathMax(hHi, g_d1[i].hi); double ul = MathMin(hLo, g_d1[i].lo);
         if(!found || (uh - ul) > (bestHi - bestLo)) { bestHi = uh; bestLo = ul; found = true; }
        }
     }
   if(found) { outHi = bestHi; outLo = bestLo; }
   return(found);
  }

bool RoundOverlap(double hHi, double hLo, double &outHi, double &outLo)
  {
   bool found = false; double bestHi = 0, bestLo = 0;
   for(int i = 0; i < ArraySize(g_rnd); i++)
     {
      if(Overlaps(hHi, hLo, g_rnd[i].hi, g_rnd[i].lo))
        {
         double uh = MathMax(hHi, g_rnd[i].hi); double ul = MathMin(hLo, g_rnd[i].lo);
         if(!found || (uh - ul) > (bestHi - bestLo)) { bestHi = uh; bestLo = ul; found = true; }
        }
     }
   if(found) { outHi = bestHi; outLo = bestLo; }
   return(found);
  }

void BuildH4Events(const MqlRates &h4[], const double &h4Atr[])
  {
   int n = ArraySize(h4);
   ArrayResize(g_ev, 0);
   double hiSrc[], loSrc[]; ArrayResize(hiSrc, n); ArrayResize(loSrc, n);
   for(int k = 0; k < n; k++) { hiSrc[k] = h4[k].high; loSrc[k] = h4[k].low; }
   for(int i = 0; i < n; i++)
     {
      double a = h4Atr[i];
      if(a <= 0 || a == EMPTY_VALUE) continue;
      double buf = 0.4 * a;
      for(int side = 0; side < 2; side++)
        {
         bool isRes = (side == 0);
         bool isFrac = isRes ? IsFractal(hiSrc, i, InpP_H4, true) : IsFractal(loSrc, i, InpP_H4, false);
         if(!isFrac) continue;
         double zhi, zlo;
         if(isRes) { zhi = h4[i].high + buf; zlo = h4[i].high - buf; }
         else      { zhi = h4[i].low  + buf; zlo = h4[i].low  - buf; }
         int born = i + InpP_H4;
         if(born >= n) continue;
         int hits = 0; int lastTouch = -999;
         // matches Python's `range(born+1, min(len(h4_c), born+1+2000))`
         // exactly - that range is exclusive of its upper bound, so the
         // last k iterated there is min(len-1, born+2000), not born+2001.
         int endIdx = MathMin(n - 1, born + 2000);
         for(int k = born + 1; k <= endIdx; k++)
           {
            bool touched, busted;
            if(isRes) { touched = h4[k].high >= zlo; busted = h4[k].close > zhi + InpBustMarginATR * a; }
            else      { touched = h4[k].low  <= zhi; busted = h4[k].close < zlo - InpBustMarginATR * a; }
            if(!touched) continue;
            if(k - lastTouch < InpTouchGapH4) continue;
            lastTouch = k;
            if(hits >= InpMinH4Hits)
              {
               double dHi, dLo, rHi, rLo;
               bool haveD1  = D1ActiveOverlap(zhi, zlo, h4[k].time, dHi, dLo);
               bool haveRnd = RoundOverlap(zhi, zlo, rHi, rLo);
               if(haveD1 || haveRnd)
                 {
                  double uHi = zhi, uLo = zlo;
                  if(haveD1)  { uHi = MathMax(uHi, dHi); uLo = MathMin(uLo, dLo); }
                  if(haveRnd) { uHi = MathMax(uHi, rHi); uLo = MathMin(uLo, rLo); }
                  int ec = ArraySize(g_ev);
                  ArrayResize(g_ev, ec + 1);
                  g_ev[ec].t = h4[k].time; g_ev[ec].dirn = isRes ? -1 : 1;
                  g_ev[ec].hi = uHi; g_ev[ec].lo = uLo; g_ev[ec].atr = a;
                 }
              }
            hits++;
            if(busted) break;
           }
        }
     }
   for(int a2 = 1; a2 < ArraySize(g_ev); a2++)
     {
      ConfEvent key = g_ev[a2]; int b2 = a2 - 1;
      while(b2 >= 0 && g_ev[b2].t > key.t) { g_ev[b2+1] = g_ev[b2]; b2--; }
      g_ev[b2+1] = key;
     }
  }

int DSTGapHourAdjustment(datetime now);   // forward declaration - defined below, after the holiday-calendar
                                           // date-arithmetic helpers it depends on; see its own header
bool IsFridayNoEntry(datetime t)
  {
   MqlDateTime m; TimeToStruct(t, m);
   return(m.day_of_week == 5 && m.hour >= 20 + DSTGapHourAdjustment(t));
  }
//+------------------------------------------------------------------+
//| US market holiday calendar - all 5 confirmed real-data culprits for   |
//| the weekend-flatten bug (Juneteenth, MLK, Memorial Day x2, Labor Day)  |
//| were positions OPENED on the holiday itself, whose session then closed  |
//| far earlier than a normal day, the same way a normal Friday does at      |
//| InpFridayNoEntry's hour - so this blocks new entries on a flagged         |
//| holiday exactly like that existing Friday rule blocks them late in a       |
//| normal week. Every date below is COMPUTED from the year, not looked up      |
//| in a hardcoded table - no yearly maintenance, works for any year          |
//| indefinitely: Easter via the standard Gregorian algorithm (Meeus/Jones/    |
//| Butcher), the floating holidays (MLK/Presidents/Memorial/Labor/            |
//| Thanksgiving) via Nth-weekday-of-month rules, and the fixed-date ones       |
//| (New Year's/Juneteenth/Independence Day/Christmas) via the standard          |
//| federal weekend-observed shift (Sat->Fri before, Sun->Mon after).             |
//+------------------------------------------------------------------+
//| Easter Sunday for the given year, Gregorian calendar - the classic     |
//| "Anonymous Gregorian algorithm" (Meeus/Jones/Butcher), integer-only,    |
//| valid for any year >= 1583. Good Friday is 2 days before it.             |
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
//| The n-th occurrence of `weekday` (0=Sun..6=Sat, matching MqlDateTime's |
//| own day_of_week) in the given month/year - e.g. n=3, weekday=1 (Mon)    |
//| for "3rd Monday of January" (MLK Day).                                   |
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
//| The LAST occurrence of `weekday` in the given month/year - e.g.        |
//| weekday=1 (Mon) for "last Monday of May" (Memorial Day), which isn't    |
//| expressible as a fixed n-th-occurrence rule since May can have either     |
//| 4 or 5 Mondays depending on the year.                                       |
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
//| A fixed calendar date (e.g. July 4), shifted per the standard US       |
//| federal "observed" rule when it falls on a weekend: Saturday moves to   |
//| the Friday before, Sunday moves to the Monday after.                      |
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
//| True if 'now' falls on any of the standard US market holidays, all     |
//| computed fresh from now's own year - see the block comment above for    |
//| the full rationale. Same-day comparison only (y/m/d), the hour/min/sec    |
//| of 'now' don't matter.                                                      |
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
//| Both IsFridayClose(day_of_week==5 && hour>=22) and its IsWeekendCatchup |
//| backstop (day_of_week==6||0) were replaced outright by WeekendStillOpen  |
//| below, not left in place - an Opus review of real Strategy Tester data    |
//| (2023.04.04-2023.04.10, Good Friday + the weekend) found IsWeekendCatchup  |
//| was 100% dead code, not a rare edge case: the real M1 export shows GOLD#'s  |
//| broker reopens Monday ~01:00, never Saturday or Sunday, on every single      |
//| weekend in the data - so day_of_week==6||0 could never be true at the         |
//| moment trading actually resumed. The one real case in the reviewed window      |
//| only got closed 27+ hours late (127h vs the 100h InpMaxBars target), by         |
//| that wall-clock cap finally catching up once ticks resumed - not by this         |
//| backstop. Deleting rather than keeping either function around unused             |
//| (MQL5 flags an unused function) - this comment is the only trace left.            |
//+------------------------------------------------------------------+
//| Deadline-based: true once 'now' is at or past the most recent Friday 22:00 |
//| threshold (22 = the hour IsFridayClose used to hardcode) AND the position   |
//| (openTime) predates that threshold - i.e. "this position should already      |
//| have been flattened for the weekend, and it hasn't been". Makes no            |
//| assumption about which day of the week the first tick back happens to         |
//| land on - Sat, Sun, Mon, or later after an extended holiday closure all        |
//| work the same way, since it isn't asking "what day is it", it's asking          |
//| "did we already pass the point where this position should have closed".         |
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
   f.hour = 22 + DSTGapHourAdjustment(friday); f.min = 0; f.sec = 0;
   datetime deadline = StructToTime(f);
   if(deadline > now) deadline -= 7 * 86400;              // today IS Friday but before 22:00 - last week's deadline applies
   return(now >= deadline && openTime < deadline);
  }

// Zone-boundary comparison for the dedup keys below, used instead of a raw
// `==` on doubles. hi/lo are recomputed from scratch every bar from a
// SLIDING CopyRates window (InpD1Bars/InpH4Bars) - once the oldest bar
// drops out of that window, the ATR seed technically changes, and while
// the Wilder recursion converges back to the same bit-exact value in
// practice (verified: it's a contraction), that convergence isn't
// guaranteed the moment history is still growing (early in a fresh
// backtest/account) or under a small InpD1Bars/InpH4Bars. A false
// "unequal" here is the dangerous direction - it would let an already-
// traded zone silently re-enter the watch list and place a second order
// for a setup already acted on. Half a point of tolerance costs nothing
// and removes the dependence on that argument entirely.
bool SameZone(double a, double b) { return(MathAbs(a - b) < _Point * 0.5); }

bool AlreadyHandled(datetime evT, int dirn, double hi, double lo)
  {
   for(int i = 0; i < ArraySize(g_handled); i++)
      if(g_handled[i].evTime == evT && g_handled[i].dirn == dirn
         && SameZone(g_handled[i].hi, hi) && SameZone(g_handled[i].lo, lo)) return(true);
   return(false);
  }
void MarkHandled(datetime evT, int dirn, double hi, double lo)
  {
   int c = ArraySize(g_handled); ArrayResize(g_handled, c + 1);
   g_handled[c].evTime = evT; g_handled[c].dirn = dirn;
   g_handled[c].hi = hi; g_handled[c].lo = lo;
  }
void PruneHandled(datetime cutoff)
  {
   int w = 0;
   for(int i = 0; i < ArraySize(g_handled); i++)
      if(g_handled[i].evTime >= cutoff) { g_handled[w] = g_handled[i]; w++; }
   ArrayResize(g_handled, w);
  }

bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      return(true);
     }
   return(false);
  }

void DeleteAllOurPendingOrders()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      trade.OrderDelete(ticket);
     }
  }

//+------------------------------------------------------------------+
//| Lot size for this trade. Fixed InpLotSize by default (matching     |
//| every backtest's assumption); when InpUseRiskPercent is on,        |
//| instead risks a fixed % of current equity - the stop distance in   |
//| price is converted to $ risk per 1.0 lot via the symbol's own      |
//| tick value/size (correct for any symbol, not just XAUUSD's $1     |
//| per-point convention), then clamped to the broker's allowed        |
//| min/max/step so it's always a placeable volume.                    |
//+------------------------------------------------------------------+
double ComputeLotSize(double entryPx, double invalidPx)
  {
   double lot = InpLotSize;
   if(InpUseRiskPercent)
     {
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double stopDistPx = MathAbs(entryPx - invalidPx);
      if(tickSize > 0 && tickValue > 0 && stopDistPx > 0)
        {
         double riskPerLot = (stopDistPx / tickSize) * tickValue;
         double riskDollars = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPercent / 100.0;
         lot = riskDollars / riskPerLot;
        }
      // else: couldn't compute a risk-based size (missing symbol info or a
      // zero stop distance) - fall back to InpLotSize, still clamped below.
     }

   // Broker volume limits apply regardless of which path set `lot` above -
   // the fixed-lot path previously returned InpLotSize verbatim with no
   // validation at all, so a misconfigured InpLotSize (or one that no
   // longer fits the symbol's current limits) would only be discovered as
   // an order-placement rejection instead of being caught here.
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lotStep > 0) lot = MathFloor(lot / lotStep) * lotStep;
   // No `lot > 0` gate here: the worst case (the risk budget floors all the
   // way down to exactly 0.0, i.e. the stop is so wide relative to equity
   // that even one lot step is more risk than InpRiskPercent allows) is
   // exactly the case that most needs this warning, and a `lot > 0` guard
   // silently skipped it - the one scenario risking noticeably more than
   // InpRiskPercent was also the one raised to minLot with no warning at all.
   if(InpUseRiskPercent && minLot > 0 && lot < minLot)
      PrintFormat("Zenith_EA: risk-percent sizing wanted a %.4f lot below the broker minimum (%.4f) - "
                  "raising to the minimum risks more than InpRiskPercent=%.2f%% on this trade",
                  lot, minLot, InpRiskPercent);
   lot = MathMax(minLot, MathMin(maxLot, lot));
   return(lot);
  }

//+------------------------------------------------------------------+
//| Place a limit order, checking that trading is actually allowed    |
//| first, and retrying on a transient rejection (requote, price      |
//| changed, timeout, server busy) rather than giving up on the very  |
//| first attempt - backtests never hit these, real/demo accounts do. |
//+------------------------------------------------------------------+
// Not every broker/symbol accepts ORDER_TIME_SPECIFIED - placing one where
// it isn't supported fails outright (retcode 10025), which would silently
// mean this EA places zero orders on such a broker (one Journal line the
// only symptom). Fall back to GTC when specified expiration isn't listed
// in the symbol's allowed modes; CancelInvalidatedOrders() enforces the
// fill-window cutoff manually either way, so GTC orders don't rest forever.
ENUM_ORDER_TYPE_TIME PickOrderTypeTime()
  {
   long modes = SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_MODE);
   return((modes & SYMBOL_EXPIRATION_SPECIFIED) != 0 ? ORDER_TIME_SPECIFIED : ORDER_TIME_GTC);
  }

bool PlaceLimitOrderWithRetry(bool isBuy, double lot, double price, double sl, double tp,
                               datetime expiration, string comment)
  {
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      Print("Zenith_EA: trading is not allowed right now (AutoTrading off, or terminal/EA not permitted) - skipping this order");
      return(false);
     }
   ENUM_ORDER_TYPE_TIME typeTime = PickOrderTypeTime();
   datetime effExpiration = (typeTime == ORDER_TIME_SPECIFIED) ? expiration : 0;
   for(int attempt = 1; attempt <= MathMax(1, InpOrderRetries); attempt++)
     {
      bool ok = isBuy
         ? trade.BuyLimit(lot, price, _Symbol, sl, tp, typeTime, effExpiration, comment)
         : trade.SellLimit(lot, price, _Symbol, sl, tp, typeTime, effExpiration, comment);
      if(ok) return(true);
      uint rc = trade.ResultRetcode();
      // REQUOTE/PRICE_CHANGED/PRICE_OFF mean the server definitively
      // rejected the request - safe to retry blind. TIMEOUT/CONNECTION mean
      // the OUTCOME IS UNKNOWN: the order may already be resting on the
      // server even though this client never got the confirmation. Blindly
      // retrying those specifically risks placing a SECOND identical
      // resting order - the exact duplicate-position failure mode this
      // whole file has been hardened against elsewhere (real duplicate
      // deals were observed live earlier this session). Poll for one of
      // our own pending orders before retrying those two specifically, and
      // treat finding one as success rather than firing again.
      bool ambiguousOutcome = (rc == TRADE_RETCODE_TIMEOUT || rc == TRADE_RETCODE_CONNECTION);
      bool transient = (rc == TRADE_RETCODE_REQUOTE || rc == TRADE_RETCODE_PRICE_CHANGED ||
                         rc == TRADE_RETCODE_PRICE_OFF || ambiguousOutcome);
      PrintFormat("Zenith_EA: order attempt %d/%d failed, retcode=%d %s%s",
                  attempt, InpOrderRetries, rc, trade.ResultRetcodeDescription(),
                  transient ? " (transient, retrying)" : " (not transient, giving up)");
      if(!transient) return(false);
      if(ambiguousOutcome)
        {
         Sleep(500);   // give the server time to settle before polling
         if(CountOurPendingOrders() > 0)
           {
            Print("Zenith_EA: order outcome was ambiguous (timeout/connection), but a pending order now "
                  "exists - treating the original attempt as successful instead of risking a duplicate");
            return(true);
           }
        }
      else
         Sleep(200);   // brief pause before retrying a definitive rejection
     }
   return(false);
  }

int CountOurPendingOrders()
  {
   int c = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      c++;
     }
   return(c);
  }

//+------------------------------------------------------------------+
//| Most MT5 brokers charge the round-turn commission on the ENTRY deal, |
//| not the exit one - so summing DEAL_COMMISSION off only the exit deal |
//| (as both the win/loss classification below and OnTradeTransaction    |
//| originally did) silently ignores it, which can misclassify a         |
//| marginal trade as a win when it was actually a small net loss (or    |
//| vice versa) once commission is counted. Looks up the entry deal for  |
//| the same position and adds its commission/swap too.                  |
//+------------------------------------------------------------------+
double GetPositionEntryCommission(long positionId)
  {
   // HistorySelectByPosition(), not HistorySelect() - a caller in
   // OnTradeTransaction has just called HistorySelect(trans.deal) (or
   // nothing at all), and HistorySelect()'s documented behavior is to
   // REPLACE the cached history selection with only what it was asked
   // for - so a loop over HistoryDealsTotal() right after selecting a
   // single deal only ever sees that one deal, never the entry deal for
   // the same position, and this returned 0.0 unconditionally. Selecting
   // by position ID instead loads every deal that belongs to it.
   if(!HistorySelectByPosition(positionId)) return(0.0);
   int total = HistoryDealsTotal();
   for(int i = total - 1; i >= 0; i--)
     {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
      return(HistoryDealGetDouble(deal, DEAL_COMMISSION) + HistoryDealGetDouble(deal, DEAL_SWAP));
     }
   return(0.0);   // entry deal not found (shouldn't happen for our own positions) - assume none
  }

//+------------------------------------------------------------------+
//| Reconstruct the consecutive-loss circuit breaker's state from real |
//| trade history. Called at OnInit, and again mid-run as a self-heal  |
//| backstop from OnTick's open->flat transition detector - it fully   |
//| recomputes from scratch every time, so calling it when the state   |
//| was already correct is a harmless no-op. Walks our own closed      |
//| deals backward from most recent, counting a loss streak exactly    |
//| the way OnTradeTransaction does (profit+swap+commission <= 0),     |
//| stopping at the first win or when the streak has already reached   |
//| the pause threshold. Without this, a recompile or restart mid-     |
//| pause would silently re-enable entries in exactly the losing       |
//| conditions the breaker exists to sit out.                          |
//+------------------------------------------------------------------+
void RestoreCircuitBreakerState()
  {
   g_consecLosses = 0; g_pausedUntil = 0; g_lastCloseTime = 0;
   if(!HistorySelect(0, TimeCurrent())) return;
   int total = HistoryDealsTotal();
   for(int i = total - 1; i >= 0; i--)
     {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0) continue;
      if((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol) continue;
      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY) continue;

      if(g_lastCloseTime == 0)
         g_lastCloseTime = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);

      double profit = HistoryDealGetDouble(deal, DEAL_PROFIT)
                    + HistoryDealGetDouble(deal, DEAL_SWAP)
                    + HistoryDealGetDouble(deal, DEAL_COMMISSION)
                    + GetPositionEntryCommission((long)HistoryDealGetInteger(deal, DEAL_POSITION_ID));
      // GetPositionEntryCommission() calls HistorySelectByPosition()
      // internally, which REPLACES the history cache this loop's own
      // HistoryDealGetTicket(i) indexing depends on (HistorySelect's
      // documented behavior, not an accident) - re-select the original
      // range this loop expects before the next iteration reads it,
      // otherwise i-1 onward would silently read from the wrong,
      // position-restricted set instead of the full deal history.
      HistorySelect(0, TimeCurrent());
      if(profit <= 0)
        {
         g_consecLosses++;
         if(InpMaxConsecLosses > 0 && g_consecLosses >= InpMaxConsecLosses) break;
        }
      else
         break;   // most recent closed trade (working backward) was a win - streak is over
     }
   if(InpMaxConsecLosses > 0 && g_consecLosses >= InpMaxConsecLosses && g_lastCloseTime > 0)
     {
      g_pausedUntil = g_lastCloseTime + InpPauseBars * PeriodSeconds(PERIOD_M15);
      if(g_pausedUntil > TimeCurrent())
         PrintFormat("Zenith_EA: restored circuit breaker - %d losses in a row, paused until %s",
                     g_consecLosses, TimeToString(g_pausedUntil));
      else
         g_pausedUntil = 0;   // the pause window already fully elapsed while the EA was stopped
     }
  }

//+------------------------------------------------------------------+
//| Reconstruct the trailing stop's peak/armed state from an already-  |
//| open position, called once at OnInit. Without this, a recompile or |
//| restart while a trade is open would disarm an already-profitable   |
//| trail and restart the peak from the current price, reverting a     |
//| trade that had already earned trailing protection back to its      |
//| original hard stop.                                                 |
//+------------------------------------------------------------------+
void RestoreTrailingState()
  {
   g_posPeak = 0; g_posArmed = false; g_posOpenTime = 0; g_posStateTicket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      // Needed regardless of InpUseTrailingExit (unlike the peak/armed state
      // below, which only matters when trailing is on) - ManageOpenPosition's
      // wall-clock MaxBars check reads g_posOpenTime directly. Setting
      // g_posStateTicket here too so ManageOpenPosition's own self-sync
      // check doesn't immediately treat this correctly-restored value as
      // stale and recompute it a second time (harmless if it did, since
      // it would resync to the same answer, but pointless).
      g_posOpenTime = (datetime)PositionGetInteger(POSITION_TIME);
      g_posStateTicket = ticket;

      if(!InpUseTrailingExit) return;

      bool isBuy = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL = PositionGetDouble(POSITION_SL);
      double atrNow = CurrentH4ATR();
      // Found in review: a cold-start CurrentH4ATR()==0.0 (CopyRates coming
      // back short right at OnInit, e.g. ERR_HISTORY_NOT_READY on a fresh
      // terminal) used to zero out trailDist/activateDist here, which could
      // arm the trail on ANY profit and reconstruct a garbage peak - and on
      // the live per-tick site below, place a new SL at the current market
      // price on the very next tick, closing the position outright. Treat a
      // non-positive ATR as "no information" instead: leave the trail
      // unarmed with peak at entry, the same safe state used when curSL
      // isn't beyond entry - no different from what a genuinely fresh
      // position with an unmoved SL already looks like.
      double trailDist = InpTrailATR * atrNow, activateDist = InpTrailActivateATR * atrNow;
      // best information available about the peak is the current SL, if the
      // trail has already moved it beyond entry (arithmetic inverse of
      // ManageOpenPosition's own newSL formula) - otherwise fall back to
      // the entry price itself (peak has not moved / trail not yet armed).
      if(atrNow <= 0.0)
        {
         g_posPeak = entryPx;
         g_posArmed = false;
        }
      else if(isBuy)
        {
         g_posPeak = (curSL > entryPx) ? curSL + trailDist : entryPx;
         g_posArmed = (g_posPeak - entryPx) >= activateDist;
        }
      else
        {
         g_posPeak = (curSL > 0 && curSL < entryPx) ? curSL - trailDist : entryPx;
         g_posArmed = (entryPx - g_posPeak) >= activateDist;
        }
      PrintFormat("Zenith_EA: restored trailing state on init - peak=%.2f armed=%s (position ticket %I64u)",
                  g_posPeak, g_posArmed ? "true" : "false", ticket);
      return;   // only one position can exist by design
     }
  }

//+------------------------------------------------------------------+
//| Manage an already-open position: our own MAXBARS timeout and the |
//| Friday close rule (SL/TP are broker-side, handled automatically). |
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   // g_posPeak/g_posArmed are single globals, meant for exactly one
   // position - every other defense in this file (CountOurPendingOrders
   // gate, the per-bar order-placement break, the ambiguous-outcome retry
   // guard) exists specifically to keep that invariant true, but if it
   // were ever violated anyway (the scenario those defenses exist for),
   // sharing one peak/armed pair across positions would thrash between
   // them rather than fail loudly. Only the FIRST matching position gets
   // trailing management from the shared state; a second is still closed
   // on Friday/MaxBars (those use only per-position locals, no shared
   // state to thrash) but its trailing stop is left alone rather than
   // corrupted, and this is logged loudly rather than silently tolerated.
   bool trailingHandled = false;
   int matchCount = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      matchCount++;
      if(matchCount > 1)
         PrintFormat("Zenith_EA: WARNING - %d of our own positions open simultaneously on %s "
                     "(ticket %I64u) - the single-position invariant has been violated. Friday/MaxBars "
                     "closes still apply to every one, but only the first gets trailing-stop management.",
                     matchCount, _Symbol, ticket);

      datetime now = TimeCurrent();
      // Self-correcting, not solely reliant on OnTradeTransaction: this was
      // a REAL live bug - if OnTradeTransaction's DEAL_ENTRY_IN handler
      // (which normally sets g_posOpenTime/g_posPeak/g_posArmed the instant
      // a fill occurs) is ever delayed, skipped, or fires after
      // ManageOpenPosition first examines this ticket, all three would stay
      // stale from whatever the PREVIOUS position was. Confirmed live as a
      // stale open time alone (several positions closed 2-3 seconds after
      // entry for a few cents' loss, no SL comment - MaxBars firing
      // immediately from a huge apparent hold time), and a later review
      // found the identical race, unfixed, on g_posPeak/g_posArmed too -
      // since XM reports a 0 stops level on GOLD#, a stale peak there could
      // plant a real, wrong SL near market on a brand-new position, not
      // just a stale read that self-corrects. Whenever this ticket doesn't
      // match the one all three were last synced to, resync every one of
      // them from the position's own real, authoritative data before
      // trusting any of them - this makes correctness independent of
      // OnTradeTransaction's exact timing rather than merely hoping it
      // always wins the race.
      if(ticket != g_posStateTicket)
        {
         g_posOpenTime = (datetime)PositionGetInteger(POSITION_TIME);
         bool isBuyResync = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
         double entryPxResync = PositionGetDouble(POSITION_PRICE_OPEN);
         double curSLResync = PositionGetDouble(POSITION_SL);
         double atrResync = CurrentH4ATR();
         double trailDistResync = InpTrailATR * atrResync, activateDistResync = InpTrailActivateATR * atrResync;
         // same cold-start guard as RestoreTrailingState() above - see its comment.
         if(atrResync <= 0.0)
           {
            g_posPeak = entryPxResync;
            g_posArmed = false;
           }
         else if(isBuyResync)
           {
            g_posPeak = (curSLResync > entryPxResync) ? curSLResync + trailDistResync : entryPxResync;
            g_posArmed = (g_posPeak - entryPxResync) >= activateDistResync;
           }
         else
           {
            g_posPeak = (curSLResync > 0 && curSLResync < entryPxResync) ? curSLResync - trailDistResync : entryPxResync;
            g_posArmed = (entryPxResync - g_posPeak) >= activateDistResync;
           }
         PrintFormat("Zenith_EA: WARNING - position state was stale for ticket %I64u (resynced open time/"
                     "peak/armed from its own real data) - OnTradeTransaction's DEAL_ENTRY_IN handler did "
                     "not win the race against this ManageOpenPosition call.", ticket);
         g_posStateTicket = ticket;
        }
      // Wall-clock, not bar-count: InpMaxBars is validated in Python as a
      // bar count, but the g_barCounter mechanism that tracked that here
      // was reverted - it depended on iBars(), which is NOT a safe
      // monotonic "elapsed bars" counter for LIVE trading (it can jump
      // forward on a background history re-sync, reconnect, or chart-depth
      // change - a live-only hazard the Strategy Tester can never expose,
      // since there iBars() only ever advances one-per-bar). That flaw could
      // reproduce the exact same instant-close bug the ticket-resync above
      // was written to fix, just from the counter itself going wrong instead
      // of staying stale - undetectable by backtesting. Plain wall-clock is
      // ~30% shorter than the validated bar count across any span crossing
      // a weekend - a known, accepted, low-stakes imprecision, far
      // preferable to a mechanism that can silently misfire live in a way
      // no backtest can ever catch.
      int barsHeld = (int)((now - g_posOpenTime) / PeriodSeconds(PERIOD_M15));

      if(!InpHoldOverWeekend && WeekendStillOpen(now, g_posOpenTime))
        {
         if(!trade.PositionClose(ticket))
            PrintFormat("Zenith_EA: Friday/weekend close FAILED for ticket %I64u, retcode=%d %s - will retry next tick",
                        ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
         continue;
        }
      if(barsHeld >= InpMaxBars)
        {
         if(!trade.PositionClose(ticket))
            PrintFormat("Zenith_EA: MaxBars close FAILED for ticket %I64u, retcode=%d %s - will retry next tick",
                        ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
         continue;
        }

      if(InpUseTrailingExit && !trailingHandled)
        {
         trailingHandled = true;
         bool isBuy = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double curPx = isBuy ? bid : ask;
         double entryPx = PositionGetDouble(POSITION_PRICE_OPEN);

         if(isBuy) { if(curPx > g_posPeak) g_posPeak = curPx; }
         else      { if(g_posPeak == 0 || curPx < g_posPeak) g_posPeak = curPx; }

         double atrTrail = CurrentH4ATR();
         // Found in review: without this guard, a cold-start atrTrail==0.0
         // would arm the trail on any nonzero profit and then set newSL to
         // g_posPeak exactly (InpTrailATR*0), which for a position already
         // in profit equals the current market price - closing the position
         // outright on the very next modify. Skip this tick's trailing
         // update entirely rather than act on a zero ATR reading; the
         // position's existing SL is untouched either way.
         if(atrTrail <= 0.0) continue;

         double prof = isBuy ? (g_posPeak - entryPx) : (entryPx - g_posPeak);
         if(!g_posArmed && prof >= InpTrailActivateATR * atrTrail)
            g_posArmed = true;

         if(g_posArmed)
           {
            double curSL = PositionGetDouble(POSITION_SL);
            double newSL = isBuy ? g_posPeak - InpTrailATR * atrTrail : g_posPeak + InpTrailATR * atrTrail;
            bool improves = isBuy ? (curSL == 0 || newSL > curSL) : (curSL == 0 || newSL < curSL);
            // A broker's minimum stop distance applies to a modify just as
            // much as to a new order - a trail that has run the SL up close
            // to the current price can otherwise be silently rejected
            // (retcode 10016/10024) every tick until price moves enough to
            // satisfy it again, quietly giving back protection the trail
            // was supposed to be locking in.
            long stopsLevelPts = MathMax(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
                                          SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL));
            double minDist = stopsLevelPts * _Point;
            bool respectsStopsLevel = (minDist <= 0) || (MathAbs(curPx - newSL) >= minDist);
            if(improves && respectsStopsLevel)
              {
               int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
               if(!trade.PositionModify(ticket, NormalizeDouble(newSL, digits), 0))
                  PrintFormat("Zenith_EA: trailing stop modify FAILED for ticket %I64u, retcode=%d %s",
                              ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
              }
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Watch/pending state machine - only runs while flat. Adds newly   |
//| relevant confluence events to the watch list, advances watched   |
//| events into real resting limit orders on breakout confirmation,  |
//| and expires/cancels stale watches and orders.                    |
//+------------------------------------------------------------------+
void AdvanceWatchAndOrders(const MqlRates &m15[], double d1Close, double d1Ema)
  {
   int nM = ArraySize(m15);
   if(nM < 2) return;
   MqlRates cur = m15[nM - 1];   // last CLOSED M15 bar
   datetime tI = cur.time;

   // add newly-closed confluence events into the watch list.
   //
   // g_ev[e].t is the H4 bar's OPEN time, but this EA only ever sees a
   // CLOSED H4 bar (CopyRates shift=1) - so a given event is never actually
   // visible/actionable until g_ev[e].t + 4 hours, once its bar has closed.
   // The touch window is meant to give a fresh event a full InpTouchWindowBars
   // (24 M15 bars = 6h) to break out from the moment it's knowable - basing
   // the expiry on the bar's OPEN time instead ate the first ~16 of those 24
   // bars before the EA could ever act, leaving an effective window of only
   // ~8 bars. `knownAt` is the timestamp actually used for all timing below;
   // `evTime` (the identity key for dedup/HandledKey) stays g_ev[e].t
   // unchanged, since that's the event's real, stable identity.
   for(int e = 0; e < ArraySize(g_ev); e++)
     {
      datetime knownAt = g_ev[e].t + PeriodSeconds(PERIOD_H4);
      if(knownAt > tI) continue;
      // Backlog-skip efficiency filter only (avoid rescanning ages-old
      // events every bar) - the actual touch-window enforcement is
      // `expire`, checked once an event is admitted to the watch list below.
      if(knownAt < tI - (InpTouchWindowBars + 2) * PeriodSeconds(PERIOD_M15)) continue; // too old to matter
      if(AlreadyHandled(g_ev[e].t, g_ev[e].dirn, g_ev[e].hi, g_ev[e].lo)) continue;
      bool already = false;
      for(int w = 0; w < ArraySize(g_watch); w++)
         if(g_watch[w].evTime == g_ev[e].t && g_watch[w].dirn == g_ev[e].dirn
            && SameZone(g_watch[w].hi, g_ev[e].hi) && SameZone(g_watch[w].lo, g_ev[e].lo)) { already = true; break; }
      if(already) continue;
      int c = ArraySize(g_watch); ArrayResize(g_watch, c + 1);
      g_watch[c].evTime = g_ev[e].t; g_watch[c].dirn = g_ev[e].dirn;
      g_watch[c].hi = g_ev[e].hi; g_watch[c].lo = g_ev[e].lo; g_watch[c].atr = g_ev[e].atr;
      // Python validates the touch window as a bar count (`expire_i = i +
      // touch_window_bars`), not a calendar duration - a wall-clock window
      // here is ~30% shorter than that across any span crossing a weekend.
      // A bar-count mechanism (g_barCounter, driven by iBars()) was tried
      // and reverted: iBars() isn't a safe monotonic "elapsed bars" counter
      // live (it can jump forward on a background history re-sync,
      // reconnect, or chart-depth change - a live-only hazard no backtest
      // can expose), which risked worse failures than the imprecision it
      // was fixing. Plain wall-clock, known-imprecise but safe, instead.
      g_watch[c].expire = knownAt + InpTouchWindowBars * PeriodSeconds(PERIOD_M15);
      g_cntEventsWatched++;
     }

   if(HasOpenPosition())
     {
      // don't watch for new setups while a position is open - matches the
      // validated backtest (active/pending processing pauses while pos!=0).
      // Defensively clear any stray resting order too: DeleteAllOurPendingOrders()
      // is normally fired from OnTradeTransaction's DEAL_ENTRY_IN handler the
      // instant our own order fills, but if that event was ever missed (a
      // recompile or terminal restart between the fill and the event firing),
      // an orphaned pending could otherwise sit and fill on top of this
      // already-open position later, producing two live positions.
      DeleteAllOurPendingOrders();
      return;
     }
   if(CountOurPendingOrders() > 0)
     {
      // A resting order from an earlier bar's breakout is still unfilled -
      // don't place a second one. The per-bar `break` below only prevents
      // two DIFFERENT zones breaking out on the SAME bar from both getting
      // orders; without this check, a zone breaking out on a LATER bar
      // (while the first order is still waiting to fill) would still place
      // a second live order at a different price. Both could then fill
      // independently, producing two real positions instead of one - the
      // same duplicate-position risk as the same-bar case, just spread
      // across bars instead of within one.
      return;
     }

   // consecutive-loss circuit breaker (validated: +6% net, DD halved, worst
   // streak 8->5 on both train and hold) - only blocks NEW entries, never
   // touches an open position, so it doesn't cut into the recovery trades
   // the edge partly depends on the way an early-exit rule would.
   //
   // Wall-clock: InpPauseBars is validated in Python as a bar count, so
   // this is ~30% shorter than validated across a span crossing a
   // weekend - a known, accepted imprecision (a bar-count version of this
   // was tried and reverted; see g_watch[c].expire's comment above for why).
   if(InpMaxConsecLosses > 0 && tI < g_pausedUntil)
     {
      // Still let watched setups expire normally, and - matching the
      // validated Python exactly (its paused branch drops any active zone
      // that would break out this bar via `if not trig_break1(...):
      // still_active.append(a_)`, i.e. a would-be breakout is consumed,
      // not kept) - consume (mark handled, remove) any watch that would
      // have broken out this bar too, not just count it. Previously this
      // only counted it diagnostically and left it in g_watch, so the same
      // setup could still break out again later in its window once the
      // pause ended - a real divergence from Python, where that setup is
      // gone for good the moment it would have fired during a pause.
      for(int w = ArraySize(g_watch) - 1; w >= 0; w--)
        {
         bool wouldBreak = (g_watch[w].dirn == -1) ? (cur.close > g_watch[w].hi && cur.close > cur.open)
                                                    : (cur.close < g_watch[w].lo && cur.close < cur.open);
         if(wouldBreak)
           {
            g_cntSkipPaused++;
            MarkHandled(g_watch[w].evTime, g_watch[w].dirn, g_watch[w].hi, g_watch[w].lo);
            ArrayRemove(g_watch, w, 1);
            continue;
           }
         if(tI > g_watch[w].expire) { MarkHandled(g_watch[w].evTime, g_watch[w].dirn, g_watch[w].hi, g_watch[w].lo); ArrayRemove(g_watch, w, 1); }
        }
      return;
     }
   // NOTE: g_consecLosses is deliberately NOT reset just because the pause
   // elapsed (TimeCurrent() >= g_pausedUntil is exactly why we reach this
   // point at all, so there's nothing to gate here). The validated Python circuit
   // breaker (test_trailing_fresh.py / test_mtf_circuit_breaker.py) never
   // resets the streak on a pause elapsing either - only an actual WIN
   // resets it (OnTradeTransaction's DEAL_ENTRY_OUT handler). Resetting
   // here would mean needing TWO fresh losses to re-pause after a pause
   // ends, instead of one - a materially weaker breaker than validated,
   // in exactly the choppy-regime scenario it exists to protect against.

   bool spreadOk = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) <= InpMaxSpreadPoints;
   // Wall-clock: Python's cooldown is validated as a bar count
   // (`bars_since_close += 1` each bar), so this is a known, accepted
   // approximation, same reasoning as the pause gate above.
   bool cooldownOk = (tI - g_lastCloseTime) >= InpCooldownBars * PeriodSeconds(PERIOD_M15);
   bool fridayOk = !IsFridayNoEntry(tI);
   bool holidayOk = !IsMarketHoliday(tI);

   // ACTIVE -> ORDER: check each watched event for its breakout confirmation.
   // Iterates OLDEST-first (ascending) and removes in place with `w--` to
   // compensate for the shift - g_watch is populated in ascending evTime
   // order (new events are appended after scanning g_ev, which is itself
   // time-sorted), so this matches Python's own tie-break exactly: when
   // several zones break out on the same bar, Python's fill loop takes the
   // FIRST (oldest) candidate in list order (`if fired is None: fired = p_`
   // over a list built in ascending time order), not the newest.
   for(int w = 0; w < ArraySize(g_watch); w++)
     {
      if(tI > g_watch[w].expire)
        {
         MarkHandled(g_watch[w].evTime, g_watch[w].dirn, g_watch[w].hi, g_watch[w].lo);
         ArrayRemove(g_watch, w, 1);
         g_cntWatchExpired++;
         w--;
         continue;
        }
      int fadeDirn = g_watch[w].dirn;
      double zhi = g_watch[w].hi, zlo = g_watch[w].lo, watchAtr = g_watch[w].atr;
      datetime watchEvTime = g_watch[w].evTime;
      bool broke = (fadeDirn == -1) ? (cur.close > zhi && cur.close > cur.open)
                                     : (cur.close < zlo && cur.close < cur.open);
      if(!broke) continue;

      int bdirn = -fadeDirn;
      MarkHandled(g_watch[w].evTime, g_watch[w].dirn, g_watch[w].hi, g_watch[w].lo);
      ArrayRemove(g_watch, w, 1);
      g_cntBreakouts++;
      w--;   // compensate for the removal - every continue/break below still
             // needs this iteration's index accounted for exactly once

      static bool loggedBreakout = false;
      if(!loggedBreakout) { PrintFormat("Zenith_EA: first breakout confirmation seen at %s, dirn=%d", TimeToString(tI), bdirn); loggedBreakout = true; }

      if(InpUseD1Trend)
        {
         int trend = (d1Close > d1Ema) ? 1 : -1;
         if(trend != bdirn) { g_cntSkipD1Trend++; continue; }
        }
      if(!spreadOk)   { g_cntSkipSpread++;   continue; }
      if(!cooldownOk) { g_cntSkipCooldown++; continue; }
      if(!fridayOk)   { g_cntSkipFriday++;   continue; }
      if(!holidayOk)  { g_cntSkipHoliday++;  continue; }

      static bool loggedOrderAttempt = false;
      if(!loggedOrderAttempt) { PrintFormat("Zenith_EA: first order placement attempt at %s", TimeToString(tI)); loggedOrderAttempt = true; }

      double ref = cur.close;
      // Found in review: watchAtr is the H4 ATR at the ZONE'S FRACTAL BAR,
      // not at entry - BuildH4Events can emit and this loop can still trade
      // an event up to InpTouchGapH4-gated touches over ~2000 H4 bars
      // (~333 days) after that fractal formed, on a symbol whose ATR has
      // moved ~6x in 3 years. That's fine for the STOP GEOMETRY line right
      // below (zlo/zhi - InpStopBufATR*watchAtr - the validated zone shape
      // is meant to reflect the ATR when the zone formed), but wrong for
      // the four practical risk/target guards added on top of it, which
      // should reflect risk conditions NOW, not whenever this particular
      // zone happened to form. Use a fresh ATR reading for those four - the
      // same CurrentH4ATR() the trailing-stop logic already uses - instead
      // of watchAtr.
      double curAtr = CurrentH4ATR();
      if(curAtr <= 0.0) { g_cntSkipNoATR++; continue; }   // same cold-start case as B1 - skip, don't risk a zero-distance trade
      // Price-percentage offset, NOT an ATR multiple - see the InpPullbackPct
      // declaration comment (2026-09-05 Opus review) for why the ATR-multiple
      // version was dropping real entries as ATR grew faster than price.
      double pullbackDist = ref * InpPullbackPct / 100.0;
      double limitPx  = (bdirn == 1) ? ref - pullbackDist : ref + pullbackDist;
      double invalidPx = (bdirn == 1) ? zlo - InpStopBufATR * watchAtr
                                       : zhi + InpStopBufATR * watchAtr;
      if(InpMaxLossATR > 0)
        invalidPx = (bdirn == 1) ? MathMax(invalidPx, ref - InpMaxLossATR * curAtr)
                                  : MathMin(invalidPx, ref + InpMaxLossATR * curAtr);
      // Floor the stop distance too, not just the cap - a low-ATR H4 regime
      // can otherwise produce a stop just a couple dollars away (near-
      // guaranteed to hit on noise alone), and with InpUseRiskPercent on,
      // ComputeLotSize's risk/distance division would size that into a
      // near-max-lot position instead of a naturally small, safe one.
      //
      // Measured from limitPx (the actual entry price), NOT ref - unlike
      // InpMaxLossATR just above (which correctly measures from ref,
      // matching the validated Python's own `max(invalid_px, ref -
      // max_loss_usd)`), InpMinLossATR has no Python equivalent to match;
      // it exists purely for this input's own stated promise ("stop is
      // never closer than this many x ATR from entry"). Measuring it from
      // ref instead of the real entry price would silently shrink the floor
      // by pullbackDist - e.g. the original $8 default was only
      // really a $3 floor from the actual entry, undercutting the whole
      // point of it.
      if(InpMinLossATR > 0)
        invalidPx = (bdirn == 1) ? MathMin(invalidPx, limitPx - InpMinLossATR * curAtr)
                                  : MathMax(invalidPx, limitPx + InpMinLossATR * curAtr);
      // Hard dollar ceiling on top of the ATR-based stop above - re-added
      // 2026-09-05 (Opus review, SESSION_NOTES.md item 18, Finding A). The
      // ORIGINAL pre-ATR-conversion system had exactly this as InpMaxLossUSD
      // =$30 flat; the ATR conversion removed it, on the reasoning that a
      // flat dollar cap goes stale as ATR rises - true, but it also removed
      // the only thing bounding worst-case loss-per-trade on a FIXED lot
      // size (InpUseRiskPercent=false, the common case below ~$25k equity,
      // where risk-percent sizing floors at the broker minimum lot anyway
      // and stops being risk-proportional). Without this, 2026's H4 ATR
      // (~$41 median, spiking to ~$87) let a single stop-out reach $254 at
      // 0.01 lots (8.5% of a $3,000 account) - a real, correctly-placed
      // stop, not a bug, but exactly the tail risk this cap exists to bound.
      // Distance is measured from limitPx (the real entry), matching
      // InpMinLossATR just above and distToStop's own definition further
      // down. At GOLD#'s 100oz contract size, $1 of price distance = $1 of
      // P&L per 0.01 lot, so this dollar figure is a direct price-distance
      // cap when running fixed lots; 0 disables it (e.g. for an account
      // large enough that risk-percent sizing is doing the real bounding).
      if(InpMaxLossCapUSD > 0)
        invalidPx = (bdirn == 1) ? MathMax(invalidPx, limitPx - InpMaxLossCapUSD)
                                  : MathMin(invalidPx, limitPx + InpMaxLossCapUSD);
      // no fixed TP when the trailing exit is active - InpUseTrailingExit
      // manages the exit itself via ManageOpenPosition() once the position
      // is open, letting a trade that keeps trending run past target instead
      // of capping it (validated: beats the flat target on every split).
      double tgt = InpUseTrailingExit ? 0.0
                   : (bdirn == 1 ? limitPx + InpFixedTargetATR * curAtr : limitPx - InpFixedTargetATR * curAtr);
      if(bdirn == 1 && invalidPx >= limitPx) { g_cntSkipGeometry++; continue; }
      if(bdirn == -1 && invalidPx <= limitPx) { g_cntSkipGeometry++; continue; }

      datetime expiration = tI + InpFillWindowBars * PeriodSeconds(PERIOD_M15);
      int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      limitPx = NormalizeDouble(limitPx, digits);
      invalidPx = NormalizeDouble(invalidPx, digits);
      if(tgt != 0.0) tgt = NormalizeDouble(tgt, digits);

      // Broker minimum-distance check: a limit order placed too close to
      // the current market, or with an SL too close to its own entry, is
      // rejected outright (retcode 10016/10024) rather than adjusted - skip
      // it now rather than let PlaceLimitOrderWithRetry burn its retries on
      // a rejection that will never succeed.
      long stopsLevelPts = MathMax(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
                                    SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL));
      double minDist = stopsLevelPts * _Point;
      double curSide = (bdirn == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      // Signed, not MathAbs: a buy limit must sit BELOW Ask (fires as price
      // falls to it) and a sell limit ABOVE Bid. A plain absolute distance
      // can't tell "too close on the correct side" apart from "on the
      // WRONG side entirely" - if price gapped since `ref` was read, a buy
      // limit ending up ABOVE the current Ask would show a large (passing)
      // MathAbs distance despite being invalid, and would be rejected by
      // the broker (10015) with the retry logic treating it as a silent,
      // non-transient give-up.
      //
      // Checked UNCONDITIONALLY (not gated behind stopsLevelPts > 0): a
      // wrong-side limit is invalid regardless of what the broker's
      // minimum distance happens to be - XM commonly reports 0 for both
      // SYMBOL_TRADE_STOPS_LEVEL and SYMBOL_TRADE_FREEZE_LEVEL on GOLD#,
      // which previously skipped this whole block (minDist=0 makes the
      // distance checks below trivially pass too, but distToMarket < 0
      // must still be caught).
      double distToMarket = (bdirn == 1) ? (curSide - limitPx) : (limitPx - curSide);
      double distToStop = MathAbs(limitPx - invalidPx);
      // With minDist=0 (broker reports no stops/freeze level, e.g. XM on
      // GOLD#), `distToMarket < minDist` reduces to exactly `distToMarket
      // < 0` - still correctly catching a wrong-side limit even when the
      // broker's own distance requirement is zero.
      if(distToMarket < minDist || distToStop < minDist) { g_cntSkipStopsLevel++; continue; }

      double lot = ComputeLotSize(limitPx, invalidPx);
      if(lot <= 0) { g_cntSkipLotZero++; continue; }
      g_cntOrdersPlaced++;
      PlaceLimitOrderWithRetry(bdirn == 1, lot, limitPx, invalidPx, tgt, expiration,
                                "Zenith " + TimeToString(watchEvTime));
      // Only ever place ONE order per bar, then stop - matches Python's
      // actual behaviour exactly: run()/run_confirmed() only ever lets the
      // FIRST pending to fire in a given bar become a real trade
      // (`if fired is None: fired = p_`), and once a position opens, all
      // further pending processing freezes until it closes - any other
      // simultaneous candidate is simply abandoned, never revisited.
      // Multiple DIFFERENT zones sharing a timestamp (the fix above this
      // loop) can otherwise break out on the exact same bar and compute
      // the IDENTICAL limit price (same `ref = cur.close`), placing two
      // real resting orders that can both fill on the same tick - before
      // DeleteAllOurPendingOrders() (fired from the first fill) gets a
      // chance to cancel the other - producing two real, duplicate
      // positions instead of one (seen directly in a live test: several
      // pairs of identical buy/sell deals at the same price and second).
      break;
     }
  }

//+------------------------------------------------------------------+
//| Delete any of our own resting pending orders that have (a) moved   |
//| past their own invalidation price without filling - MT5's built-in |
//| order expiration only handles a time-based cutoff, not a price-    |
//| based one, a limit order has no "cancel if price crosses X" -      |
//| (b) outlived the fill window even without broker-side specified-   |
//| expiration support (PickOrderTypeTime's GTC fallback), or          |
//| (c) is still resting once the Friday no-new-entry window begins.   |
//+------------------------------------------------------------------+
void CancelInvalidatedOrders()
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   bool fridayNoEntry = IsFridayNoEntry(TimeCurrent());
   bool holidayNow = IsMarketHoliday(TimeCurrent());
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      ENUM_ORDER_TYPE type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      double sl = OrderGetDouble(ORDER_SL);
      // sl > 0 guard: every order this EA places always carries a real SL,
      // but if that were ever missing/stripped, `ask >= 0` is always true -
      // without the guard that would cancel every resting sell limit
      // unconditionally, every tick.
      if(sl > 0 && type == ORDER_TYPE_BUY_LIMIT && bid <= sl) { trade.OrderDelete(ticket); continue; }
      if(sl > 0 && type == ORDER_TYPE_SELL_LIMIT && ask >= sl) { trade.OrderDelete(ticket); continue; }

      // Manual fill-window cutoff, wall-clock (Python validates this as a
      // bar count, a known, accepted approximation - same reasoning as the
      // pause/cooldown/touch-window checks elsewhere in this file). Backs
      // up PickOrderTypeTime's GTC fallback on a broker that doesn't
      // support specified expiration, and also covers the case where it
      // is supported but set generously.
      datetime setup = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      if(setup > 0 && TimeCurrent() - setup >= InpFillWindowBars * PeriodSeconds(PERIOD_M15))
        { trade.OrderDelete(ticket); continue; }

      // A resting order placed before Friday's no-new-entry cutoff could
      // otherwise sit and fill after it, opening a trade the validated
      // logic would never take (entries are gated by IsFridayNoEntry at
      // placement time, but nothing previously stopped an already-resting
      // order from filling once that window began).
      if(fridayNoEntry || holidayNow) { trade.OrderDelete(ticket); continue; }
     }
  }

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if((ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;

   ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry == DEAL_ENTRY_IN)
     {
      // a pending order just filled - enforce single-position-at-a-time
      DeleteAllOurPendingOrders();
      g_posPeak = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
      g_posArmed = false;
      g_posOpenTime = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
      g_posStateTicket = trans.position;   // marks this as already-correct, so ManageOpenPosition's
                                            // self-sync check doesn't second-guess a value that's
                                            // actually fine - it only needs to fire when this DIDN'T
                                            // run in time, not every single time regardless.
     }
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      g_lastCloseTime = TimeCurrent();   // the real gate for cooldownOk - see AdvanceWatchAndOrders
      double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
                     + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
                     + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION)
                     + GetPositionEntryCommission((long)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID));
      if(InpMaxConsecLosses > 0)
        {
         if(profit <= 0)
           {
            g_consecLosses++;
            if(g_consecLosses >= InpMaxConsecLosses)
              {
               g_pausedUntil = TimeCurrent() + InpPauseBars * PeriodSeconds(PERIOD_M15);
               PrintFormat("Zenith_EA: %d losses in a row - pausing new entries until %s",
                           g_consecLosses, TimeToString(g_pausedUntil));
              }
           }
         else
           {
            g_consecLosses = 0;
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Panel primitives - visual build, 2026-09-05. Ported from             |
//| Aurelius_EA.mq5's DrawPanel()/PRect/PText/PSection/PRow/PFrame/       |
//| PBackground (cross-checked against Fulcrum_EA.mq5/Ratchet_EA.mq5's    |
//| equivalents for what's shared convention vs. incidental) - replaces    |
//| the old plain Comment(txt) status line with the same neon dashboard     |
//| the other 4 gold EAs on this account already use, restructured into      |
//| sections/rows instead of one text blob. All layout is left-corner        |
//| based, same reasoning as Aurelius: right corners invert the X axis in     |
//| MT5, which silently mirrors the whole panel off-screen.                    |
//+------------------------------------------------------------------+
int EstimateTextWidth(const string s, const int fontSize)
  {
   return (int)(StringLen(s) * fontSize * 0.62) + 2;
  }
//--- see g_panelMinW's declaration - one draw cycle's lag between a long
//--- value string being measured and the panel actually growing to fit it.
//+------------------------------------------------------------------+
//| A rectangle - background fill or (via PFrame) a thin frame strip.    |
//| g_panelReclaim-gated delete/recreate: MT5 stacks chart objects by     |
//| CREATION order, not ZORDER, so a trade-fill arrow/line MT5 draws       |
//| AFTER the panel already exists would otherwise render on top of it -   |
//| deleting and recreating makes this the newest object again. Only the    |
//| draggable "bg" rect is exempt (must keep its identity or dragging        |
//| breaks mid-motion) - see the "fl" fill rect in DrawPanel(), which is       |
//| what actually keeps THAT rect's body solid instead.                        |
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
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);       // in front of candles
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, grab);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, !grab);
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5000);
  }
//+------------------------------------------------------------------+
//| PRect's own OBJ_RECTANGLE_LABEL border (BORDER_FLAT + OBJPROP_COLOR) |
//| renders unreliably on a live/demo chart - found this session as only   |
//| two of the four sides actually drawing. This draws an explicit 4-strip  |
//| frame instead - one thin filled rectangle per edge, immune to the        |
//| quirk since each strip is just an ordinary solid-filled                    |
//| OBJ_RECTANGLE_LABEL. Same fix, same helper, as Aurelius_EA.mq5/             |
//| Fulcrum_EA.mq5/Ratchet_EA.mq5/Daybreak_EA.mq5.                                |
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
   ObjectSetInteger(0, nm, OBJPROP_ZORDER, 5001);      // above PRect's 5000
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
                    rightAlign ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
  }
//+------------------------------------------------------------------+
//| A row: status dot, label on the left, value right-aligned. Passing    |
//| label=="" && value=="" clears a row that no longer applies (e.g. a     |
//| POSITION row only meaningful while in a trade) - same convenience as    |
//| Aurelius_EA.mq5's PRow, used below when the panel shrinks from the       |
//| in-position layout back to the flat one.                                  |
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
//| Section heading on its own tinted band.                           |
//+------------------------------------------------------------------+
void PSection(const string id, const int x, const int y, const int w,
              const int rh, const string title)
  {
   PRect(id + "bar", x + 1, y - 3, w - 2, rh + 2, InpHeaderBg, InpHeaderBg, 0);
   PText(id + "t", x + 10, y, title, InpSectionCol, InpPanelSize, false, "Arial Bold");
  }
//+------------------------------------------------------------------+
//| Optional wallpaper - off by default (InpBackgroundBMP == ""), unlike  |
//| Aurelius/Fulcrum/Ratchet which ship a real .bmp asset; no such asset    |
//| exists for Zenith, so this stays a no-op unless one is supplied. Ported  |
//| anyway per the porting instruction. NOTE (corrected in review - the        |
//| original comment here overclaimed): unlike Aurelius, this file only calls    |
//| PBackground() once, from OnInit - Aurelius calls it a further two times        |
//| (from OnTimer, to retry a slow-loading image, and on a chart resize, to         |
//| re-centre it), neither of which exists here since Zenith has no OnTimer.         |
//| The retry-counter/re-centre logic below is real code, but currently unreachable   |
//| past its first attempt - wire in OnTimer or extend OnChartEvent's resize handler    |
//| to give a future Zenith wallpaper the same behaviour Aurelius's actually has.         |
//|                                                                                        |
//| CORRECTION (2026-09-06): this comment previously said Zenith had no        |
//| watermark "not part of this file's scope" - the user asked for it, so it's   |
//| in scope now. See PWatermark() immediately below, ported from                  |
//| Daybreak_EA.mq5's identical mechanism.                                            |
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
     { Print("Zenith_EA: PBackground ObjectCreate failed, error ", GetLastError()); return; }

   string path = "\\Images\\" + InpBackgroundBMP;
   ResetLastError();
   bool okSet = ObjectSetString(0, nm, OBJPROP_BMPFILE, 0, path);
   int err = GetLastError();
   if(!okSet || err != 0)
     {
      if(g_bgTries <= 3)
         PrintFormat("Zenith_EA: PBackground try %d failed to load \"%s\" - error %d "
                     "- file must be at <data folder>\\MQL5\\Images\\%s", g_bgTries, path, err, InpBackgroundBMP);
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
   PrintFormat("Zenith_EA: PBackground loaded \"%s\" on try %d", path, g_bgTries);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| Text watermark (2026-09-06) - ported from Daybreak_EA.mq5's           |
//| PWatermark() verbatim: deliberately subtle/muted, not neon, so it      |
//| tints empty chart space without sitting on top of price action, same    |
//| as the other four gold EAs already have. Shares the g_pw prefix with     |
//| PBackground()'s wallpaper bitmap object above - both are swept by the     |
//| same ObjectsDeleteAll(0, g_pw) call in OnDeinit already.                    |
//+------------------------------------------------------------------+
void PWatermark()
  {
   string nm = g_pw + "wm";
   if(!InpShowWatermark || InpWatermarkText == "")
     { if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm); return; }
   if(ObjectFind(0, nm) >= 0 && (ENUM_OBJECT)ObjectGetInteger(0, nm, OBJPROP_TYPE) != OBJ_LABEL)
      ObjectDelete(0, nm);
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_RIGHT_LOWER);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_RIGHT_LOWER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 18);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 18);
   ObjectSetString (0, nm, OBJPROP_TEXT, InpWatermarkText);
   ObjectSetString (0, nm, OBJPROP_FONT, InpWatermarkFont);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpWatermarkSize);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, InpWatermarkColor);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| Chart theme - matches Aurelius_EA.mq5/Fulcrum_EA.mq5/Ratchet_EA.mq5/  |
//| Daybreak_EA.mq5 exactly (neon-blue/white candles on black), so all 5   |
//| gold EAs on this account read as one product. Zenith had NO chart-      |
//| theme inputs at all before this build.                                    |
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
   ChartSetInteger(0, CHART_SHOW_GRID, false);
   ChartSetInteger(0, CHART_MODE, CHART_CANDLES);
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//| CHART DRAWING OF THE LEVELS THIS EA TRADES (indicator-visibility     |
//| build, 2026-09-06 - see the header block of the same name).          |
//|                                                                      |
//| Everything below is drawing only. Nothing here is called from, or    |
//| reads any state written by, the signal/entry/exit/sizing path - the  |
//| draw functions only ever READ the same globals the panel already     |
//| reads (g_d1/g_rnd/g_ev, plus the live order list), and every call    |
//| site is gated behind g_skipCosmeticDraws exactly like the panel is.  |
//|                                                                      |
//| Shared low-level helpers first. Both mirror the object properties    |
//| Aurelius_EA.mq5's DrawMASegment() and Zenith_Signals.mq5's           |
//| DrawZoneRect()/DrawHLine() already use, so this EA's chart output is |
//| indistinguishable from the rest of the portfolio's.                  |
//+------------------------------------------------------------------+
void ZSegment(const string nm, const datetime t1, const double p1,
              const datetime t2, const double p2, const color col,
              const ENUM_LINE_STYLE style, const int width)
  {
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   if(!ObjectCreate(0, nm, OBJ_TREND, 0, t1, p1, t2, p2))
     {
      //--- diagnostic (2026-09-07): ObjectCreate's return value was never
      //--- checked anywhere in this drawing pass - a silent failure here
      //--- (object cap, invalid coordinate, etc.) would report success on
      //--- the panel/log ("first confluence event generated") while nothing
      //--- actually painted. Throttled to once per session so a persistent
      //--- failure doesn't spam the Journal on every bar.
      static bool logged = false;
      if(!logged) { PrintFormat("Zenith_EA: ObjectCreate FAILED for '%s' (OBJ_TREND), error %d", nm, GetLastError()); logged = true; }
      return;
     }
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);   // keep the Object List usable - up to
                                                     // InpD1EmaHistoryBars of these exist at once
  }
//+------------------------------------------------------------------+
//| Zone box. REVERSED (2026-09-07, same diagnostic pass as the         |
//| ObjectCreate-failure logging above): this used to be FILL=true,      |
//| BACK=true on the theory that a broad filled band tints the price      |
//| region and stays visible even behind candles, unlike a thin unfilled   |
//| outline (Daybreak_EA.mq5's DrawRangeBox() problem). That reasoning      |
//| missed that this file's candles are drawn fully OPAQUE/filled           |
//| (PTheme's InpBullCol/InpBearCol solid bodies, not hollow candles) -      |
//| a BACK-drawn fill only shows through the thin gaps BETWEEN candle        |
//| bodies, which at normal chart density is a few pixels of dark colour      |
//| (C'120,40,40'/C'30,70,110', chosen deliberately muted so the tint          |
//| wouldn't compete with price action) against a black background -           |
//| exactly the "buried behind a dense candle field" failure this function's    |
//| own old comment warned Daybreak's approach would have, just arrived at       |
//| by a different mechanism (opaque fill occlusion instead of stacking            |
//| order). Confirmed via the Journal that BuildD1Zones/ObjectCreate both           |
//| succeed (798 real D1 zones, no ObjectCreate failure logged) - so this was        |
//| a rendering problem, not a data or object-creation one. FIXED: now an             |
//| unfilled, brighter, width-2 BORDER drawn in FRONT (BACK=false) - a thin            |
//| outline in front cannot meaningfully obscure price (unlike a filled front           |
//| box, which was rejected for exactly that reason), and being in front means          |
//| it is never candle-occluded regardless of body opacity or chart density.             |
//+------------------------------------------------------------------+
void ZZoneBox(const string nm, const datetime t1, const double hi,
              const datetime t2, const double lo, const color col)
  {
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   if(!ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, hi, t2, lo))
     {
      //--- same diagnostic as ZSegment() above - a failed ObjectCreate here
      //--- would explain "798 D1 zones generated, none visible" exactly:
      //--- the data pipeline succeeds and logs success, this call silently
      //--- does nothing, and every ObjectSetInteger below it is a no-op on
      //--- a name that doesn't exist.
      static bool logged = false;
      if(!logged) { PrintFormat("Zenith_EA: ObjectCreate FAILED for '%s' (OBJ_RECTANGLE), error %d", nm, GetLastError()); logged = true; }
      return;
     }
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_FILL, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
//| The D1 EMA(InpD1EmaPeriod) trend filter - the single hard            |
//| directional gate on every Zenith entry (AdvanceWatchAndOrders'       |
//| d1Close vs d1Ema comparison), and until now invisible in both this   |
//| file and Zenith_Signals.mq5 (whose readout only ever showed the      |
//| word "UP"/"DOWN", never a line).                                     |
//|                                                                      |
//| One OBJ_TREND segment per D1 bar rather than ChartIndicatorAdd() -   |
//| an EA has no plot buffers of its own, so an added built-in indicator |
//| can only ever render in MT5's own auto-assigned colour. Same         |
//| technique as Aurelius_EA.mq5's DrawMASegment(), adapted to D1        |
//| granularity because that is the timeframe the filter actually reads. |
//|                                                                      |
//| Redrawn in full once per D1 bar (the `lastD1` guard), not once per   |
//| M15 bar: the whole window is only ~InpD1EmaHistoryBars objects and   |
//| it only changes when a D1 bar closes, so a full rebuild is both      |
//| cheaper and simpler than incremental appends plus a separate purge   |
//| sweep (the rebuild IS the purge - old segments are wiped wholesale,  |
//| so the line can never grow past InpD1EmaHistoryBars objects however  |
//| long the chart runs).                                                |
//|                                                                      |
//| This deliberately does its OWN CopyBuffer rather than widening the   |
//| 2-bar read in OnTick: that one is part of the trading path (a short  |
//| return there aborts the entire tick), and a cosmetic draw must not   |
//| be able to influence it even indirectly. A failure here just leaves  |
//| the previous line on the chart and retries next bar.                 |
//+------------------------------------------------------------------+
void UpdateD1EmaLine()
  {
   if(!InpShowD1Ema || InpD1EmaHistoryBars < 2) return;
   if(g_emaD1Handle == INVALID_HANDLE) return;
   //--- ascending order (oldest first), same convention as every other rates
   //--- read in this file - the LAST element is the most recent CLOSED D1 bar.
   double ema[]; ArraySetAsSeries(ema, false);
   int got = CopyBuffer(g_emaD1Handle, 0, 1, InpD1EmaHistoryBars, ema);
   if(got < 2) return;
   //--- copy exactly `got` times, not InpD1EmaHistoryBars: if the EMA buffer
   //--- came back short, indexing the time array past what the value array
   //--- actually holds (or vice versa) would pair a value with the wrong bar.
   datetime tm[]; ArraySetAsSeries(tm, false);
   if(CopyTime(_Symbol, PERIOD_D1, 1, got, tm) < got) return;
   static datetime lastD1 = 0;
   if(tm[got - 1] == lastD1) return;      // same D1 bar as the last rebuild - nothing to redo
   lastD1 = tm[got - 1];
   ObjectsDeleteAll(0, g_pl);
   for(int i = 0; i < got - 1; i++)
     {
      //--- MT5's iMA buffer holds 0.0 (not EMPTY_VALUE) before the EMA has
      //--- enough history - the same broker quirk the trading-path guard in
      //--- OnTick already accounts for, so both checks are needed here too.
      if(ema[i]   <= 0.0 || ema[i]   == EMPTY_VALUE) continue;
      if(ema[i+1] <= 0.0 || ema[i+1] == EMPTY_VALUE) continue;
      ZSegment(g_pl + IntegerToString((long)tm[i+1]), tm[i], ema[i], tm[i+1], ema[i+1],
               InpColD1Ema, STYLE_SOLID, 2);
     }
  }
//+------------------------------------------------------------------+
//| The zones and levels the confluence engine is actually built from,  |
//| straight out of the same arrays it uses: g_d1 (BuildD1Zones),       |
//| g_ev (BuildH4Events) and g_rnd (BuildRoundLevels). Called once per  |
//| new M15 bar, immediately after those three have been rebuilt, so    |
//| what is on the chart is always exactly what the EA is reasoning     |
//| about on this bar - never a stale copy.                             |
//|                                                                     |
//| Full wipe + redraw each time rather than an incremental diff: the    |
//| three arrays are themselves rebuilt from scratch every bar (indices  |
//| are not stable between rebuilds, so an object named after one would  |
//| silently drift onto a different zone), and BuildH4Events already     |
//| walks 8000 H4 bars on that same schedule - a few hundred object      |
//| operations next to that is not the cost worth optimising.            |
//+------------------------------------------------------------------+
void DrawZoneObjects(const datetime tNow)
  {
   ObjectsDeleteAll(0, g_pz);
   if(!InpShowD1Zones && !InpShowH4Zones && !InpShowRoundLevels) return;
   datetime cutoff = tNow - (datetime)((long)MathMax(1, InpZoneHistoryDays) * 86400);

   //--- D1 fractal swing zones. The box starts at `known`, NOT at the pivot
   //--- bar: `known` is the bar the fractal was confirmed on, i.e. the first
   //--- moment this EA could legitimately have used the zone. Starting it at
   //--- the pivot would draw a level the system did not actually know yet -
   //--- look-ahead on the chart, the visual equivalent of the shift-0 bug
   //--- this file's own comments warn about repeatedly.
   if(InpShowD1Zones)
     {
      int drawn = 0;
      //--- newest first (g_d1 is built in ascending bar order), same reasoning
      //--- as the H4 loop below: if the object cap ever binds it should drop
      //--- the oldest zones, never the ones nearest current price.
      for(int i = ArraySize(g_d1) - 1; i >= 0 && drawn < InpMaxZoneObjects; i--)
        {
         if(g_d1[i].known == 0) continue;
         bool busted = (g_d1[i].bust != 0 && g_d1[i].bust <= tNow);
         if(busted && g_d1[i].bust < cutoff) continue;     // died long ago - not worth the clutter
         datetime t1 = (g_d1[i].known > cutoff) ? g_d1[i].known : cutoff;
         datetime t2 = busted ? g_d1[i].bust : tNow;
         if(t2 <= t1) continue;
         ZZoneBox(g_pz + "D1_" + IntegerToString(i), t1, g_d1[i].hi, t2, g_d1[i].lo,
                  g_d1[i].isRes ? InpColD1Res : InpColD1Sup);
         drawn++;
        }
     }

   //--- H4 confluence zones - the UNION zone (H4 zone widened by whatever D1/
   //--- round-number zone it overlapped), because that union is what the
   //--- breakout test, the limit price and the stop are all derived from, i.e.
   //--- the geometry actually traded. Each box spans the window the event is
   //--- genuinely live for (touch window + fill window), which is also why they
   //--- don't smear across the whole chart the way an open-ended box would.
   if(InpShowH4Zones)
     {
      int live = (InpTouchWindowBars + InpFillWindowBars) * PeriodSeconds(PERIOD_M15);
      int drawn = 0;
      //--- newest first: g_ev is sorted ascending by time, so walking backward
      //--- means the object cap (if it ever binds) drops the OLDEST zones
      //--- rather than silently hiding the ones currently being traded.
      for(int i = ArraySize(g_ev) - 1; i >= 0 && drawn < InpMaxZoneObjects; i--)
        {
         if(g_ev[i].t < cutoff) break;
         ZZoneBox(g_pz + "H4_" + IntegerToString(i), g_ev[i].t, g_ev[i].hi,
                  g_ev[i].t + (datetime)live, g_ev[i].lo, InpColConfluence);
         drawn++;
        }
     }

   //--- round-number grid. Drawn as horizontal lines at each level's midpoint
   //--- with the real +/- InpRoundHalf band in the tooltip - a filled band per
   //--- level would be ~70 more rectangles for a grid that is, by construction,
   //--- perfectly regular and needs no per-level shape to be understood.
   if(InpShowRoundLevels)
     {
      int drawn = 0;
      for(int i = 0; i < ArraySize(g_rnd) && drawn < InpMaxZoneObjects; i++)
        {
         string nm = g_pz + "RND_" + IntegerToString(i);
         double mid = (g_rnd[i].hi + g_rnd[i].lo) / 2.0;
         if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
         if(!ObjectCreate(0, nm, OBJ_HLINE, 0, 0, mid))
           {
            static bool logged = false;
            if(!logged) { PrintFormat("Zenith_EA: ObjectCreate FAILED for '%s' (OBJ_HLINE), error %d", nm, GetLastError()); logged = true; }
            continue;
           }
         ObjectSetInteger(0, nm, OBJPROP_COLOR, InpColRound);
         ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, nm, OBJPROP_BACK, true);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
         ObjectSetString (0, nm, OBJPROP_TOOLTIP,
                          StringFormat("round level %.2f (%.2f - %.2f)", mid, g_rnd[i].lo, g_rnd[i].hi));
         drawn++;
        }
     }
  }
//+------------------------------------------------------------------+
//| The resting limit order's own price - the InpPullbackPct offset      |
//| below/above the breakout close. This is the single most useful       |
//| thing on the chart for answering "the zone broke out, so why is      |
//| there no trade": the answer is almost always that price never came   |
//| back this far before the fill window expired, and until now nothing   |
//| showed where "this far" actually was.                                 |
//|                                                                       |
//| Read from the live order list (symbol+magic filtered, exactly like    |
//| CountOurPendingOrders) rather than from any internal copy, so what is  |
//| drawn is literally the order the broker is holding, including any      |
//| broker-side normalisation of the price. The order's own SL/TP stay     |
//| visible through MT5's native trade levels - this file never turns      |
//| those off - so they are deliberately not duplicated here.              |
//+------------------------------------------------------------------+
void DrawPendingLines()
  {
   ObjectsDeleteAll(0, g_pt);      // orders fill/expire/get cancelled - always rebuild from live state
   if(!InpShowPendingLine) return;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      double px = OrderGetDouble(ORDER_PRICE_OPEN);
      if(px <= 0.0) continue;
      datetime t1 = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      //--- ORDER_TIME_EXPIRATION is 0 for a GTC order (PickOrderTypeTime's
      //--- fallback on a broker that won't take a specified expiry) - fall
      //--- back to the fill window this EA would cancel it after anyway, so
      //--- the line always has a real right-hand end instead of collapsing
      //--- to a zero-length segment at 1970.
      datetime t2 = (datetime)OrderGetInteger(ORDER_TIME_EXPIRATION);
      if(t2 <= t1) t2 = t1 + (datetime)(InpFillWindowBars * PeriodSeconds(PERIOD_M15));
      bool isBuy = ((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) == ORDER_TYPE_BUY_LIMIT);
      string base = g_pt + IntegerToString((long)ticket);
      ZSegment(base + "_L", t1, px, t2, px, InpColPending, STYLE_DOT, 1);
      string nm = base + "_T";
      if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
      ObjectCreate(0, nm, OBJ_TEXT, 0, t1, px);
      ObjectSetString (0, nm, OBJPROP_TEXT, StringFormat("%s limit %.2f", isBuy ? "buy" : "sell", px));
      ObjectSetInteger(0, nm, OBJPROP_COLOR, InpColPending);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
     }
  }
//+------------------------------------------------------------------+
//| Finds this EA's own open position (symbol+magic filtered, same as    |
//| HasOpenPosition()) and returns its live detail for the panel - kept    |
//| here rather than folded into HasOpenPosition() since most callers of    |
//| that function only need the bool.                                        |
//+------------------------------------------------------------------+
bool GetOurPosition(int &dir, double &entryPx, double &curSL, double &floatingPL)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      dir        = ((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      entryPx    = PositionGetDouble(POSITION_PRICE_OPEN);
      curSL      = PositionGetDouble(POSITION_SL);
      floatingPL = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
//| Neon dashboard - restructures the old single-line Comment(txt) into   |
//| the same sectioned panel Aurelius/Fulcrum/Ratchet/Daybreak already use. |
//| Shows exactly what the old Comment() surfaced (watch/pending-order       |
//| counts, circuit-breaker pause state) plus the position detail and         |
//| account info the task asked for - no new metrics invented beyond what      |
//| this file already tracks. Self-learning width (g_panelMinW, one draw        |
//| cycle lag - see PRow) and autofit height for a small screen, same           |
//| technique as every other panel in this family.                                |
//+------------------------------------------------------------------+
void DrawPanel(const bool reclaim)
  {
   if(!InpShowPanel) { ObjectsDeleteAll(0, g_pp); return; }
   g_panelReclaim = reclaim;

   bool   hasPos = false;
   int    dir = 0; double entryPx = 0.0, curSL = 0.0, floatingPL = 0.0;
   hasPos = GetOurPosition(dir, entryPx, curSL, floatingPL);
   int nOrders = CountOurPendingOrders();
   bool paused = (InpMaxConsecLosses > 0 && TimeCurrent() < g_pausedUntil);

   int w = MathMax(InpPanelW, g_panelMinW);
   g_panelMinW = 0;   // re-measured fresh this cycle, used by the NEXT one
   int rh  = InpPanelSize + 11;
   int hdr = rh + 14;
   //--- ROWS = section headers + PRow calls (see the header comment above
   //--- for how this was derived - same accounting Aurelius_EA.mq5 uses).
   //--- a0(1) + SIGNAL(1+3) + CIRCUIT BREAKER(1+3) + POSITION(1+5 or 1+3) +
   //--- ACCOUNT(1+2). GAPS = 4 section headers + 4 "last row before the
   //--- next section" transitions (including the standalone a0 row).
   //--- 11 -> 12 (2026-09-06): SIGNAL gained the "d1 trend" row below.
   const int ROWS = 12 + (hasPos ? 6 : 4), GAPS = 8;

   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   int bodyH  = hdr + 10 + ROWS*rh + GAPS*6 + 12;
   int guard  = 0;
   while(bodyH > chartH - InpPanelY - 12 && rh > 11 && guard < 12)
     {
      rh--; guard++;
      hdr   = rh + 14;
      bodyH = hdr + 10 + ROWS*rh + GAPS*6 + 12;
     }
   if(g_panX < 0) { g_panX = InpPanelX; g_panY = InpPanelY; }
   int x = g_panX, y = g_panY;

   //--- frame first (creation order) - everything else draws on top of it
   PRect("sh", x + 4, y + 4, w, bodyH, InpShadowCol, InpShadowCol, 0);
   PRect("bg", x, y, w, bodyH, InpPanelBg, InpPanelBg, 0);
   //--- opaque fill on top of "bg", same reasoning as Aurelius_EA.mq5's "fl" -
   //--- "bg" keeps its identity for dragging, so it can't reclaim top-of-
   //--- stack itself; this fill is what actually keeps the panel body solid.
   PRect("fl", x + 2, y + 2, w - 4, bodyH - 4, InpPanelBg, InpPanelBg, 0);
   PFrame("bd", x, y, w, bodyH, InpPanelEdge, 2);
   PRect("hd", x + 2, y + 2, w - 4, hdr, InpHeaderBg, InpHeaderBg, 0);

   int ty = y + 9;
   PText("t1", x + 12, ty, _Symbol, InpTitleCol, InpPanelSize + 5, false, "Arial Bold");
   PText("t2", x + w - 12, ty + 3, "ZENITH", InpTextCol, InpPanelSize, true);
   ty = y + hdr + 10;

   bool algo = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED);
   PRow("a0", x, ty, w, "algo trading", algo ? "ON" : "OFF", algo ? 1 : 0); ty += rh + 6;

   //--- signal --------------------------------------------------------
   PSection("s1", x, ty, w, rh, "SIGNAL"); ty += rh + 6;
   PRow("r1", x, ty, w, "watching", (string)ArraySize(g_watch), -1); ty += rh;
   PRow("r2", x, ty, w, "pending orders", (string)nOrders, nOrders > 0 ? 1 : -1); ty += rh;
   //--- 2026-09-06: the D1 trend filter's live state. Previously this was the
   //--- one thing the panel could not show (see the visual build's own
   //--- "deliberately not added" note - it lived only in a local inside
   //--- OnTick's new-bar block); g_d1CloseNow/g_d1EmaNow now carry it out.
   //--- The value names the side the filter is currently ALLOWING, which is
   //--- what the gate actually does, rather than just naming the slope: with
   //--- the D1 close above its EMA only longs can be taken, and vice versa.
   //--- Colour-coded by direction, not pass/fail - neither side is "bad",
   //--- and a red "DOWN" would read as an error rather than a short bias.
   bool d1Known = (g_d1CloseNow > 0.0 && g_d1EmaNow > 0.0);
   bool d1Up    = (g_d1CloseNow > g_d1EmaNow);
   PRow("r3", x, ty, w, "d1 trend",
        !InpUseD1Trend ? "off" : (!d1Known ? "-" : (d1Up ? "UP (longs)" : "DOWN (shorts)")),
        (!InpUseD1Trend || !d1Known) ? -1 : (d1Up ? 1 : 0)); ty += rh + 6;

   //--- circuit breaker -------------------------------------------------
   PSection("s2", x, ty, w, rh, "CIRCUIT BREAKER"); ty += rh + 6;
   PRow("c1", x, ty, w, "status",
        InpMaxConsecLosses <= 0 ? "off" : (paused ? "PAUSED" : "clear"),
        InpMaxConsecLosses <= 0 ? -1 : (paused ? 0 : 1)); ty += rh;
   PRow("c2", x, ty, w, "losses in a row",
        InpMaxConsecLosses <= 0 ? "-" : StringFormat("%d / %d", g_consecLosses, InpMaxConsecLosses),
        InpMaxConsecLosses <= 0 ? -1 : (g_consecLosses > 0 ? 0 : 1)); ty += rh;
   PRow("c3", x, ty, w, "resumes", paused ? TimeToString(g_pausedUntil, TIME_DATE|TIME_MINUTES) : "-", -1); ty += rh + 6;

   //--- position ---------------------------------------------------
   PSection("s3", x, ty, w, rh, "POSITION"); ty += rh + 6;
   if(hasPos)
     {
      int barsHeld = (g_posOpenTime > 0) ? (int)((TimeCurrent() - g_posOpenTime) / PeriodSeconds(PERIOD_M15)) : 0;
      PRow("p1", x, ty, w, dir > 0 ? "LONG" : "SHORT", DoubleToString(entryPx, _Digits), 1); ty += rh;
      PRow("p2", x, ty, w, "current SL", curSL > 0 ? DoubleToString(curSL, _Digits) : "-", -1); ty += rh;
      PRow("p3", x, ty, w, "floating P/L", StringFormat("%+.2f", floatingPL), floatingPL >= 0 ? 1 : 0); ty += rh;
      PRow("p4", x, ty, w, "bars held", (string)barsHeld, -1); ty += rh;
      PRow("p5", x, ty, w, "trailing",
           g_posArmed ? "ARMED" : (InpUseTrailingExit ? "waiting" : "off"),
           g_posArmed ? 1 : -1); ty += rh + 6;
     }
   else
     {
      int elapsedBars = (g_lastCloseTime > 0) ? (int)((TimeCurrent() - g_lastCloseTime) / PeriodSeconds(PERIOD_M15)) : InpCooldownBars;
      int cooldownLeft = (int)MathMax(0, InpCooldownBars - elapsedBars);
      PRow("p1", x, ty, w, "state", "FLAT", -1); ty += rh;
      PRow("p2", x, ty, w, "cooldown", (string)cooldownLeft + " bars", -1); ty += rh;
      PRow("p3", x, ty, w, "sizing",
           InpUseRiskPercent ? StringFormat("risk %.2f%%", InpRiskPercent) : ("fixed " + DoubleToString(InpLotSize, 2)),
           -1); ty += rh + 6;
      //--- p4/p5 only exist in the in-position layout above - without this,
      //--- closing a position would leave ZENP_p4*/p5* on the chart at a
      //--- stale y-coordinate (the flat layout is 2 rows shorter), landing
      //--- on top of the ACCOUNT section below. Same fix as Aurelius_EA.mq5's
      //--- identical p5 bug.
      PRow("p4", x, ty, w, "", "", -1);
      PRow("p5", x, ty, w, "", "", -1);
     }

   //--- account ----------------------------------------------------
   PSection("s4", x, ty, w, rh, "ACCOUNT"); ty += rh + 6;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   //--- no g_dayStartEquity-style tracking exists anywhere in this file (checked -
   //--- unlike Aurelius/Fulcrum/Ratchet, Zenith never accumulated a "today's P&L"
   //--- figure) - showing balance/equity instead, per the task's own fallback
   //--- instruction, rather than inventing a new feature this EA doesn't have.
   PRow("q1", x, ty, w, "balance", DoubleToString(bal, 2), -1); ty += rh;
   PRow("q2", x, ty, w, "equity", DoubleToString(eq, 2), eq >= bal ? 1 : 0);
   ty += rh;

   static int warned = 0;
   int used = ty + 12 - y;
   if(used > bodyH && warned < 3)
     { warned++; PrintFormat("Zenith_EA: panel content %d px vs frame %d px - row count drifted from ROWS", used, bodyH); }
  }
//+------------------------------------------------------------------+
//| Dragging the background moves the whole panel; a genuine resize      |
//| (not just scrolling/panning, which also raises CHART_CHANGE) makes    |
//| the panel re-check whether it still fits the window. Same pattern      |
//| as Aurelius_EA.mq5/Daybreak_EA.mq5.                                     |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == g_pp + "bg")
     {
      g_panX = (int)ObjectGetInteger(0, sparam, OBJPROP_XDISTANCE);
      g_panY = (int)ObjectGetInteger(0, sparam, OBJPROP_YDISTANCE);
      // g_skipCosmeticDraws guard added for consistency with the OnTick call
      // sites (found in review) - a chart event can't actually fire during a
      // non-visual Tester pass anyway, so this is a no-op in practice.
      if(InpShowPanel && !g_skipCosmeticDraws) DrawPanel(false);   // reposition only - reclaiming mid-drag would be jarring
      ChartRedraw(0);
     }
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      static int lastW = -1, lastH = -1;
      int nw = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
      int nh = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
      if(nw != lastW || nh != lastH)
        {
         lastW = nw; lastH = nh;
         if(InpShowPanel && !g_skipCosmeticDraws) DrawPanel(false);
         ChartRedraw(0);
        }
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(_Period != PERIOD_M15)
     {
      //--- wrong-timeframe guard fires before any panel data (zones/events/
      //--- watch list) has ever been built - left as a plain Comment(), not
      //--- folded into the styled panel, since there is nothing real to show
      //--- yet. Clears any panel objects from a previous, correctly-attached
      //--- run so the two never show at once - only needs to happen once,
      //--- not on every tick (found in review).
      static bool cleared = false;
      if(!cleared) { ObjectsDeleteAll(0, g_pp); cleared = true; }
      Comment("Zenith_EA requires the M15 chart - attach it to M15.");
      return;
     }

   ManageOpenPosition();
   CancelInvalidatedOrders();

   // Self-healing backstop for the circuit breaker: OnTradeTransaction's
   // DEAL_ENTRY_OUT handler is the normal, fast path for updating
   // g_consecLosses/g_pausedUntil, but MT5 documents a real timing gap
   // where HistoryDealSelect() can fail for a deal at the exact instant
   // TRADE_TRANSACTION_DEAL_ADD fires because it isn't in the history base
   // yet - if that ever happens on an exit deal, the handler above returns
   // early and the loss streak silently, permanently stops updating, with
   // nothing to notice. Detecting the open->flat transition here and fully
   // recomputing from real trade history (RestoreCircuitBreakerState
   // rebuilds everything from scratch every time, so calling it again when
   // OnTradeTransaction already got it right is a harmless no-op) makes
   // this independent of that callback's timing too.
   bool hasPosNow = HasOpenPosition();
   if(g_hadPosition && !hasPosNow)
      RestoreCircuitBreakerState();
   g_hadPosition = hasPosNow;

   // position 0 = the still-forming, incomplete bar; watching it just for the
   // "a new bar has started" edge is fine, but every array used for decisions
   // below must start at position 1 so its LAST element is the last bar that
   // actually finished closing - using the forming bar there was the bug that
   // caused zero trades (its close is essentially always ~= its open at the
   // instant this fires, since the bar has barely begun).
   datetime t0[];
   if(CopyTime(_Symbol, PERIOD_M15, 0, 1, t0) < 1) return;
   if(t0[0] == g_lastBar)
     {
      //--- between-bar live refresh (floating P/L etc.) - throttled to once
      //--- per unique TimeCurrent() second and skipped entirely in a non-
      //--- visual Strategy Tester pass, same PERFORMANCE FIX as
      //--- Aurelius_EA.mq5 v1.32/v1.33: this branch used to call the old
      //--- Comment(txt) (cheap) on every single tick with no throttle at
      //--- all - now that it draws real chart objects, doing that unthrottled
      //--- across a multi-year real-tick backtest would reproduce the exact
      //--- multi-hour slowdown already found and fixed 3 times this session.
      //--- reclaim=false: updates the existing objects' text/values in place
      //--- rather than deleting and recreating them, so it doesn't visibly
      //--- flash - see g_panelReclaim's own comment.
      if(!g_skipCosmeticDraws && InpShowPanel)
        {
         static datetime lastPanel = 0;
         if(TimeCurrent() != lastPanel)
           {
            lastPanel = TimeCurrent();
            DrawPanel(false);
            if(HasOpenPosition()) ChartRedraw(0);
           }
        }
      return;
     }
   g_lastBar = t0[0];

   MqlRates d1[];  ArraySetAsSeries(d1, false);
   int nD1 = CopyRates(_Symbol, PERIOD_D1, 1, InpD1Bars, d1);
   MqlRates h4[];  ArraySetAsSeries(h4, false);
   int nH4 = CopyRates(_Symbol, PERIOD_H4, 1, InpH4Bars, h4);
   MqlRates m15[]; ArraySetAsSeries(m15, false);
   int nM = CopyRates(_Symbol, PERIOD_M15, 1, MathMax(200, (InpTouchWindowBars + InpFillWindowBars) * 3), m15);
   static bool loggedRatesShort = false;
   if(nD1 < 50 || nH4 < 50 || nM < 2)
     {
      if(!loggedRatesShort)
        {
         PrintFormat("Zenith_EA: not enough price history yet (nD1=%d nH4=%d nM=%d) - will keep retrying each new bar", nD1, nH4, nM);
         loggedRatesShort = true;
        }
      return;
     }

   // D1/H4 ATR is computed manually (ComputeWilderATR) directly from the
   // d1[]/h4[] rates arrays above, both already in ascending order - NOT
   // via a CopyBuffer() on an iATR() handle (see ComputeWilderATR's
   // comment for why: this broker's iATR silently isn't Wilder-smoothed,
   // which was quietly shrinking/widening every zone in the system
   // relative to what the Python validation assumed).
   double d1Atr[]; ComputeWilderATR(d1, d1Atr, 14);
   double h4Atr[]; ComputeWilderATR(h4, h4Atr, 14);

   // shift=1 on the EMA buffer read too, so it lines up with d1[] (which
   // starts at the last CLOSED bar, not the still-forming one at shift 0)
   // - otherwise the EMA value paired with a given bar would actually
   // belong to the bar after it. CopyBuffer's return value MUST still be
   // checked here - an auxiliary indicator can legitimately have
   // calculated less history than the raw price series, and indexing past
   // what actually came back is an array-out-of-range runtime error that
   // silently aborts this whole tick's processing, every tick, forever,
   // if it keeps happening. Bail and retry next bar if it's short.
   double d1EmaBuf[]; ArraySetAsSeries(d1EmaBuf, true);
   int gotD1Ema = CopyBuffer(g_emaD1Handle, 0, 1, 2, d1EmaBuf);
   static bool loggedD1EmaShort = false;
   if(gotD1Ema < 2)
     {
      if(!loggedD1EmaShort) { PrintFormat("Zenith_EA: D1 EMA buffer short (got %d, need 2) - retrying each new bar", gotD1Ema); loggedD1EmaShort = true; }
      return;
     }

   // range for the round-number grid: use D1 (the deepest available history),
   // not m15[] - that array is deliberately just a short recent window for
   // the watch/order state machine (a day or two), which would only ever
   // produce two or three round levels for the whole grid.
   double loPx = d1[0].low, hiPx = d1[0].high;
   for(int i = 1; i < nD1; i++) { loPx = MathMin(loPx, d1[i].low); hiPx = MathMax(hiPx, d1[i].high); }

   BuildD1Zones(d1, d1Atr);
   BuildRoundLevels(loPx, hiPx);
   BuildH4Events(h4, h4Atr);

   static bool loggedFirstEvent = false;
   if(!loggedFirstEvent && ArraySize(g_ev) > 0)
     {
      PrintFormat("Zenith_EA: first confluence event generated (total so far: %d, D1 zones: %d, round levels: %d)",
                  ArraySize(g_ev), ArraySize(g_d1), ArraySize(g_rnd));
      loggedFirstEvent = true;
     }

   PruneHandled(t0[0] - (InpTouchWindowBars + InpFillWindowBars + 10) * PeriodSeconds(PERIOD_M15));

   double d1CloseNow = d1[nD1 - 1].close;
   double d1EmaNow = (ArraySize(d1EmaBuf) > 0) ? d1EmaBuf[0] : EMPTY_VALUE;
   // MT5's iMA buffer holds 0.0 (not EMPTY_VALUE) before an EMA has enough
   // history - checking only EMPTY_VALUE never actually fires on this
   // broker. Same fix already applied to Zenith_Signals.mq5's warm-up guard.
   if(d1EmaNow == EMPTY_VALUE || d1EmaNow <= 0) return;

   //--- panel-only mirror of the two values the trend filter is about to be
   //--- run on (2026-09-06). Written here, after every guard above has already
   //--- accepted them, so the panel can never show a value the filter itself
   //--- rejected. Read by DrawPanel() and nothing else - the filter still gets
   //--- its inputs as arguments exactly as before.
   g_d1CloseNow = d1CloseNow;
   g_d1EmaNow   = d1EmaNow;

   AdvanceWatchAndOrders(m15, d1CloseNow, d1EmaNow);
   //--- once-per-new-bar draw: default reclaim=true, the one point where a
   //--- native MT5 trade-fill arrow could have been drawn since the last
   //--- reclaim - see g_panelReclaim's own comment. Skipped in a non-visual
   //--- Tester pass, same as the between-bar refresh above.
   //--- The chart drawing (indicator-visibility build, 2026-09-06) runs from
   //--- this same point for three reasons: g_d1/g_rnd/g_ev have just been
   //--- rebuilt a few lines above, so the zones drawn are exactly the ones
   //--- this bar is reasoning about; AdvanceWatchAndOrders has just run, so a
   //--- pending order placed on this bar is drawn immediately rather than a
   //--- bar late; and g_lastBar starts at 0, so this whole block also runs on
   //--- the very first tick after the EA attaches - which is what gives the
   //--- chart its "show something the moment it attaches" behaviour without
   //--- needing a duplicate draw in OnInit (the zone arrays don't exist yet
   //--- at OnInit time, so there would be nothing to draw there anyway).
   if(!g_skipCosmeticDraws)
     {
      UpdateD1EmaLine();
      DrawZoneObjects(t0[0]);
      DrawPendingLines();
      if(InpShowPanel) DrawPanel();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
