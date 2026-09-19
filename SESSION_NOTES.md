# Session notes — GOLD (XAUUSD, broker symbol "GOLD#", XM Global) MT5/MQL5 EAs

Running record of fixes, findings, and decisions across the live EAs
(Aurelius, Fulcrum, Ratchet, Zenith, Daybreak, AuRebound, Tailwind,
Slipstream, Ichimoku, and any added later). Kept so nothing gets lost
across sessions — read this before starting new work on any of these files.

**Recovered 2026-09-19** from a user-saved copy after this file (and the
Python research engine, and the underlying price data) were lost when the
working container was reclaimed before ever reaching GitHub — see "2026-09-19
incident" at the bottom for what happened and what changed as a result. Items
1–17 below are the original recovered content, preserved exactly.

## 1. Weekend / holiday session-gap bug (fixed, all 5 EAs)

**Root cause**: the original Friday-close logic was bar-gated (only checked
`day_of_week==5` on a new-bar event) with no tick-level backstop and no
holiday awareness. Real M1/M5 data confirmed this broker's GOLD# feed
reopens Monday ~01:00 **every single week** (never Saturday/Sunday), so an
old `IsWeekendCatchup` check for `day_of_week==6||0` was 100% dead code
(caught first in Zenith, then confirmed present identically in
Aurelius/Fulcrum/Ratchet).

**Fix**: `WeekendStillOpen()` (or equivalent name per file) — deadline-based,
not day-of-week-gated. True once `now >= most-recent-Friday's
InpFridayCloseHour:00` AND the position opened before that deadline,
checked on **every tick**, not just new bars. Closes on literally the first
tick available after any gap, regardless of which day that lands on.

**Holiday calendar**: `IsMarketHoliday()` — added per explicit user
constraint: **no hardcoded date table, must self-compute every year**.
Uses the Anonymous Gregorian algorithm (Meeus/Jones/Butcher) for Easter
(→ Good Friday), `NthWeekdayOfMonth`/`LastWeekdayOfMonth` helpers for
floating US holidays (MLK, Presidents, Memorial, Labor, Thanksgiving), and
`ObservedFixedHoliday` (Sat→Fri, Sun→Mon shift) for fixed-date ones (New
Year's, Juneteenth, July 4, Christmas). Blocks new entries on a flagged
holiday.

**Verified working** (2026-09-05, fresh post-fix reports): checked every
trade whose holding period spans a full Saturday calendar date across
Aurelius/Fulcrum/Ratchet's fresh Backtest_1/Forward_1 reports. Found 6,
every one a genuine edge case (Black Friday half-day session, or Good
Friday itself) — all closed at ~01:02, the first tick after reopen, exactly
as designed. Zero trades ever landed on an actual Saturday/Sunday
timestamp.

## 2. DST-gap-week bug (fixed, all 5 EAs)

Discovered from the user's question: "does any of this relate to daylight
saving, there is for certain months an 1 hour difference?" Confirmed
empirically from real M5 data: **this broker's server clock follows EU DST
transition dates, while gold's true session timing follows US DST dates.**
Creates a ~2-week gap every March and a ~1-week gap every Oct/Nov where any
fixed-hour threshold (Friday close hour, no-entry hour, session-open hour)
reads exactly 1 server-clock hour off from the true session boundary.

**Fix**: `DSTGapHourAdjustment()` — returns -1 during a confirmed gap week,
0 otherwise, computed from the permanent US/EU DST transition rules (no
hardcoded dates). Applied to every fixed-hour threshold that matters for
timing, not just the weekend-close logic — e.g. Daybreak's
`InpSessionHour` (its opening-range core signal timing), not just its
Friday-cutoff hours.

## 3. Visual standardization (Aurelius/Fulcrum/Ratchet only — Zenith/Daybreak not in scope for this)

Consistent panel border (`PFrame()` - 4 explicit thin rectangles, since
`OBJ_RECTANGLE_LABEL`'s built-in `BORDER_FLAT` rendered only 2 of 4 sides
live), consistent top-left panel position below MT5's own symbol label,
consistent P&L convention (today/today-other rows), chart-drawn MA/VWAP/
Bollinger Band lines (EAs can't set `PLOT_LINE_COLOR` on a
`ChartIndicatorAdd()`'d built-in, so lines are drawn manually as
per-bar `OBJ_TREND` segments), consistent color palette across
panels/candles/indicators.

**Fulcrum panel-missing bug** (found live, fixed): its "PERFORMANCE FIX
#3" had deliberately removed `EventSetTimer()`, and unlike Aurelius (draws
panel directly in `OnInit`) or Ratchet (`EventSetTimer(1)` fallback redraw),
Fulcrum had neither — its panel depended entirely on the first tick
reaching `OnTick()`. Fixed by adding an immediate `PBackground()` +
`DrawPanel()` + `ChartRedraw(0)` call in `OnInit()`.

## 4. Gold strategy / scalping research (all rejected — real-data tested, not just theorized)

Two rounds of deep research (general, then scalping-specific) surfaced
several ideas. Every one was tested against this project's own real trade
histories and real M5 price data before being trusted, per the standing
rule of this session: **never trust a research idea without testing it on
real data first.**

- Slippage time-of-day clustering (StochSwing): no evidence.
- Overnight-gap reversal: rejected — weak continuation, not reversal.
- Trend-decay-vs-volatility (the "small-tick decay" hypothesis): rejected
  as originally framed — 2 of 3 systems showed *improving*, not declining,
  PF as volatility rose (this became relevant again in item 6 below).
- Gold scalping generally: comprehensively rejected via deep research,
  multiple independent structural arguments.
- News-blackout (entry block): rejected — real data doesn't support it,
  might actively hurt 2 of 3 systems' entry timing.
- News-blackout (force-close on open position): clearly rejected — real
  data strongly shows **holding through news is beneficial**, not harmful.

## 5. Opus statistical review of "improve the losses" filters (all 3 rejected; methodology lessons carried forward)

Real-data testing surfaced two candidate filters for Aurelius/Fulcrum/
Ratchet: an ATR-based volatility floor for Ratchet, and blocking server
hours 8 and 18 for Aurelius/Fulcrum (found by scanning 24 hourly buckets
across systems and chasing the worst-looking cells). A full Opus
statistical review (permutation tests, walk-forward checks, a data-range
bug audit) rejected **all three**:

- **Ratchet ATR<2.0 floor**: revealed to be a disguised date filter, not a
  volatility filter — gold's price/ATR has risen so much since 2023 that an
  absolute ATR threshold just deletes old history. Within-quarter
  randomization test: p=0.435, indistinguishable from chance. Also found:
  it would pass 97.6% of trades in the most recent 12 months, so it'd be
  inert if shipped live today.
- **Aurelius/Fulcrum hour-18 block**: fell apart under scrutiny — 59-73% of
  the "effect" traced to 3-4 trades in a single quarter (2026Q1), and
  Aurelius/Fulcrum aren't independent evidence (99.5% same-M5-bar entries,
  so "confirmed in 2 systems" was nearly the same handful of trades counted
  twice). In R-normalized units, hour 18 wasn't even the worst hour.
- **Fulcrum hour-8**: outright rejected — hurt risk-adjusted (R-unit)
  return despite a nominal dollar gain (a lot-size/volatility-scaling
  artifact); ranking flips entirely once measured in R.
- **Aurelius hour-8** was the one survivor with real (if marginal) legs:
  consistent mean R of -1.06 in both the backtest and forward halves
  independently, negative in all 4 tested years, not outlier-driven
  (worst 3 trades = only 13% of the loss). Selection-corrected p=0.083 —
  suggestive, not proof. **Verdict: watch it with new data, do not build
  it into a live EA yet.**

**Methodology lessons carried forward for all future research on this
project**:
1. **Verify the price-data file's actual date coverage before any
   ATR/indicator-based study** — the M5 file used
   (`fc4f35d6-Bars_GOLD_PERIOD_M5.csv`) only covers 2023-01-03 to
   2026-08-14, while trade histories go back to 2022-09. A silent
   `searchsorted`-based index-out-of-range bug dropped hundreds of trades
   without warning and directly caused the false Ratchet ATR-floor
   "improvement."
2. **Do cross-time-period comparisons in R-multiples (move/entry-ATR), not
   raw dollars**, whenever lot size is fixed — gold's ATR has moved
   roughly 5-6x since 2023, so any fixed-lot dollar comparison across years
   is dominated by that scaling, not by real edge differences.
3. **Never use an absolute ATR threshold on gold** for a volatility filter
   — use ATR/price or a rolling percentile so the rule means the same
   thing at $1,800 and $4,900 gold.
4. **Aurelius and Fulcrum are not independent evidence of anything** — they
   fire on the same M5 bar 99.5% of the time. A pattern confirmed in "both"
   is close to the same observation counted twice.
5. **Pre-register the hypothesis family before scanning** — scanning 24
   hourly buckets and chasing the worst cell needs a permutation test on
   the *max*, not a simple significance test on the winner you already
   picked. Under the correct test, even the best cell in that whole study
   only reached p=0.083.
6. A quick "relabel the same historical trades under a different exit
   rule" test (used for the Fulcrum scale-out/breakeven/smaller-target
   checks below) is a fast, useful **directional** check, but is NOT a full
   re-simulation — it doesn't capture how a changed exit would cascade into
   different subsequent entries via cooldown logic. Treat its results as
   suggestive, not final, the way the original $40/45/50/55 Python
   resimulation (done when Fulcrum was first built) is more rigorous than
   any of this session's quick relabeling checks.

## 6. Fulcrum exit-structure experiments (all 3 rejected, real-data tested)

Tested three proposed changes to Fulcrum's single-fixed-$45-target design,
using real M5 high/low paths to reconstruct each historical trade's
favourable-excursion path:

- **3-leg scale-out** (1/3 @ +$10, 1/3 @ +$20, 1/3 riding to $45): total
  profit **-44%** vs current design (from $1,494 down to $843 across the
  726 in-M5-coverage trades). Win rate improves (19%→31%) and max DD drops
  ($180→$132), but the cost is too high.
- **Breakeven-stop after +$10** (no partial close): **-67%** (down to
  $489) — worse than the scale-out. Real cause found: many of Fulcrum's
  eventual big winners genuinely dip back through the entry price (a
  normal pullback off the 50 EMA) before finally running to $45 — a naive
  breakeven stop kills them before the real payoff.
- **Flat $10 target instead of $45**: **-79%** (down to $308). A full
  target-value sweep ($5 to $120) showed the profit curve is NOT
  monotonic — it dips to a local low around $18-25 before climbing back
  into a $40-50 plateau, matching (and confirming from a different angle)
  the original developer's own more-rigorous Python resimulation
  documented in Fulcrum's header (`$40→PF1.46, $45→PF1.47 best, $50→
  PF1.43, $55→PF1.40`).

**Conclusion**: Fulcrum's entire edge lives in letting rare winners run
the full distance to $45. Any early de-risking (partial close, tighter
stop, or smaller target) trades away exactly the profit source that makes
the system work. None of the three tested ideas should be built.

## 7. Fulcrum vs Aurelius: correlation and final "drop Fulcrum" call

- Aurelius and Fulcrum enter on the same M5 bar 99.5% of the time (from
  the Opus review, item 5). Running both together is not diversification —
  it's the same signal exposed twice with two different exit designs.
- A true continuous full-period ("Forward = No") run for Fulcrum showed it
  is meaningfully **weaker** than Aurelius on every metric once compared
  properly (see item 8 on the MT5 "Forward" split trap): Net $2,004 vs
  Aurelius's $3,763; PF 1.17 vs 1.35; Sharpe 2.95 vs 3.70; **max drawdown
  19.96% vs 15.65%** (worse, not better — this reversed an earlier, wrong
  comparison based on split-half reports); win rate 27.2% vs 48.0%; 26
  consecutive losses seen historically.
- **Decision: drop Fulcrum for live trading. Run Aurelius alone.** Not
  because Fulcrum is broken (it's still a real, profitable system on its
  own — PF 1.17, Sharpe 2.95), but because it doesn't diversify anything
  next to Aurelius, its own numbers are weaker, and all 3 tested "fix
  Fulcrum" ideas (item 6) failed. Ratchet is excluded too (item 5's
  unresolved backtest-half weakness). Zenith/Daybreak were NOT found to
  have Aurelius's 99.5% correlation problem — they remain candidates for
  genuine diversification alongside Aurelius, unlike Fulcrum/Ratchet.

## 8. The MT5 "Forward" split-test trap (a process lesson, not a code fix)

MT5's Strategy Tester has a `Forward` dropdown (`No` / `1/2` / `1/3` /
`1/4` / `Custom`) that **chops one continuous date range into two separate
reports** when set to `1/2` etc. — "Backtest_N" and "Forward_N" filenames
in this project were this split, not two independent test runs, and not
literally "in-sample vs out-of-sample" unless an optimization was actually
run in between (it wasn't, for these fixed-parameter checks). This caused
two real problems before it was caught:
1. Comparing a system's own Backtest-half PF against its Forward-half PF
   looked like a robustness check but was really just "which half of gold's
   price history happened to suit this system more" — the two halves cover
   different, non-overlapping years, not the same period twice.
2. **Max drawdown gets artificially chopped at the split boundary.** A
   drawdown that starts near the end of one half and continues into the
   next resets its peak-to-trough tracking at the boundary in each
   separate report, silently under-reporting the true max DD in both
   pieces. This is exactly what happened with Fulcrum's drawdown comparison
   in item 7 above.

**Rule going forward: always run fresh live-readiness checks with
`Forward = No`** for a single, true, continuous full-period number,
especially for drawdown. Only use a `1/2`+ split deliberately, and only
when parameters are actually being optimized on one half and validated on
the untouched other half.

## 9. Pre-live risk-management pass (position sizing + circuit breakers)

Checked every EA's actual position-sizing and loss-limiting code (not just
assumed from naming) — found real gaps:

- **Aurelius**: already had `InpLotMode`/`InpRiskPct` (LOT_FIXED /
  LOT_RISK_PCT) and `InpMaxDailyLossPct` (off by default) built in. Only
  code change made: default `InpLots` 0.03 → 0.01 (v1.42), to match the
  other two gold EAs and be the safest floor for a small account.
- **Ratchet** (v3.25): had neither. Added the same `InpLotMode`/
  `InpRiskPct` LOT_RISK_PCT option as Aurelius (`InpMaxDailyLossPct`
  already existed, off by default).
- **Fulcrum** (v2.09): had neither, and also had **no daily-loss circuit
  breaker at all**. Added both. One subtlety handled carefully: Fulcrum's
  `InpFixedTargetUSD` was written as a literal *price* distance, correct
  only at exactly 0.01 lots (GOLD#'s 1:1 $-to-price relationship at that
  size) — naively adding variable lot sizing would have silently broken
  the target's real dollar value at any other size. Added
  `TargetDistance()` to recompute the correct price distance for whatever
  lot size is actually traded, so `InpFixedTargetUSD` keeps meaning real
  dollars regardless of position size. At the default `LOT_FIXED` setting
  this is byte-for-byte identical to the old behaviour.
- **Zenith**: checked and found it ALREADY has full risk-based sizing
  (`InpLotSize`/`InpUseRiskPercent`/`InpRiskPercent` — different naming
  than Aurelius but the same mechanism) and a **validated consecutive-loss
  circuit breaker** (pauses new entries after a run of losses; header
  documents it was tested and found to add +6% net profit while halving
  drawdown). No code changes needed — just needs the risk-based mode
  turned on for live use.
- **Daybreak**: checked and found it has neither. `InpMaxRiskUSD` exists
  but is a per-trade *reject* filter ("skip this trade if too risky
  today"), not a sizing mechanism — `InpLots` is purely fixed. No
  daily-loss or consecutive-loss breaker exists. **This is the next
  concrete build**: add risk-based sizing plus a circuit breaker, using
  Zenith's already-validated consecutive-loss design as the template
  rather than the %-daily-loss pattern used elsewhere, since Zenith's
  version has actual validation behind it.

**Why the daily-loss-% breaker works as a *shared* circuit breaker across
multiple EAs on one account**: the check compares against
`AccountInfoDouble(ACCOUNT_EQUITY)` — the whole account's equity, not just
that EA's own P&L. Giving every EA on the account the *same*
`InpMaxDailyLossPct` value makes them act as one coordinated, account-wide
breaker (all stop opening new trades together once the account is down
that % for the day), which matters given item 7's correlation finding.

## 10. Live-account sizing guidance given

- On a **$600 account**: risk-based sizing is largely moot (0.25-0.5% of
  $600 is $1.50-3, below even the tightest realistic stop at the broker's
  0.01-lot minimum) — use `LOT_FIXED` at 0.01 on whichever EA is actually
  run. Real worst-case single-trade losses recorded historically at 0.01
  lots run 9-12% of a $600 account (Aurelius ~$56 scaled, Ratchet $73.84
  actual, Fulcrum $66.65 actual) — size the daily-loss cap accordingly
  (suggested 8-10%, not 2-3%, since a normal single trade can already
  approach a tight cap at this account size).
- On a **$3,000-scale account**: suggested starting `InpRiskPct=0.25%`,
  `InpMaxDailyLossPct=2%` for the first 2 weeks live (to confirm real
  execution matches the 77%-real-tick tester assumptions), then stepping
  up to `0.5%`/`3%`.
- **Current live-launch decision: Aurelius alone**, per item 7.

## 11. Opus audit of Zenith/Daybreak against everything above (2026-09-05)

Ran a second Opus review specifically checking Zenith/Daybreak against every
item above, plus a general code-quality pass. Findings, most important first:

- **False alarm, worth understanding why**: the review flagged Daybreak's
  new item-9 risk-sizing/circuit-breaker code as "half-built - only
  declarations, no implementation." This was a **race condition**: the
  background review agent ran for ~9 minutes overlapping with the live edit
  session that was writing that exact code, and it captured a mid-edit
  snapshot. Verified directly afterward (`git status`, full identifier
  grep) - the committed file has the complete implementation. Lesson for
  next time: don't hand a background review agent a file that's still being
  actively edited in the same window: 1line noted here so it isn't
  mis-remembered as a real defect later.
- **Real bug, fixed**: Daybreak's `OnTradeTransaction` read
  `HistoryDealGetInteger/Double/String` on a fresh deal ticket without
  calling `HistoryDealSelect()` first - so `DEAL_MAGIC` read back as 0,
  failed the magic check, and the handler returned early on **every
  broker-side SL/TP close** (the majority of Daybreak's exits, since it
  always sends real SL/TP with the order). This silently skipped both the
  CSV log and, critically, the brand-new circuit breaker's loss-streak
  bookkeeping for exactly those trades - meaning the breaker just built
  would have been functionally inert for most real closes. Fixed by adding
  `HistoryDealSelect(ticket)`, matching Zenith's already-correct pattern
  (Daybreak v1.15).
- **Real latent bug, fixed in all 5 EAs**: `NthWeekdayOfMonth`/
  `LastWeekdayOfMonth` (the shared DST/holiday-calendar helpers, copied
  identically to all 5 files) built their date at `t.hour=12` (noon), not
  midnight. Since `DSTGapHourAdjustment()`'s gap-boundary arithmetic is
  `NthWeekdayOfMonth(...) + 86400` ("the Monday after"), every gap boundary
  landed at Monday 12:00 instead of Monday 00:00. Harmless at every
  currently-shipped hour threshold (all sit above noon), but would silently
  mis-adjust any hour below 12 on the 4 DST-transition Mondays/year -
  exactly the kind of change Daybreak's own header invites for
  `InpSessionHour`. Fixed: changed both helpers to build at `t.hour=0` in
  all 5 files (Aurelius v1.43, Fulcrum v2.10, Ratchet v3.26, Zenith and
  Daybreak v1.15 - inline comment only for Zenith, matching its
  no-version-bump convention). `ObservedFixedHoliday`'s own `t.hour=12` was
  deliberately left alone - `IsMarketHoliday` only ever compares y/m/d from
  it, so it was never actually affected.
- **CRITICAL, not yet fixed - needs a decision**: Zenith's risk/exit inputs
  (`InpMaxLossUSD=$30`, `InpPullbackUSD=$5`, `InpMinLossUSD=$8`,
  `InpTrailActivateUSD=$60`, `InpTrailUSD=$30`, `InpFixedTargetUSD=$50`) are
  all **absolute dollar amounts on gold**, whose price has moved
  ~$1,940→$4,900 since these were tuned. This is methodology lesson #3 from
  item 5 above, but turned on the EA's own shipped inputs rather than a
  research filter, and nobody had checked before now. Measured directly on
  the real 2026-09-05 continuous run: `InpMaxLossUSD`'s $30 cap fired on
  10% of losing trades in 2023, **92% in 2026** - meaning the ATR/zone stop
  this system was actually validated on is barely ever the real exit
  anymore. Since 2026-03-01: 13 trades, 2 wins, -$198. Documented as a
  caveat directly in Zenith's header (with the corrected real numbers below
  in the next bullet) - **re-tuning or re-expressing these as ATR
  multiples/% of price is still an open task, not yet done.** [Resolved by
  item 12 below.]
- **Zenith's header performance claims were stale**, not matching a fresh
  continuous real-tick run: header claimed FULL net $1,940/PF 3.59/maxDD
  $110/worst streak 5; the real 2026-09-05 `Backtest_1_No_Forward` run
  shows net $868/PF 1.99/maxDD $276 (8.01% equity)/worst streak 11. (This
  session's own report to the user already used the real, correct numbers
  pulled directly from that fresh report - the stale claims were only ever
  in the file's own header comments, not in anything relayed as fact.)
  Corrected directly in Zenith's header now. Also noted: TRAIN/HOLD split
  validation in both Zenith and Daybreak isn't fully clean - HOLD was
  looked at before each design step was adopted, which is a form of the
  same "hold-out contamination" item 8's split-report problem warns about,
  just via a different mechanism (design iteration, not report-splitting).
- **Correlation, actually tested this time** (item 7's claim was previously
  inferred, not measured): extracted entries from the fresh
  Zenith/Daybreak/Aurelius `No_Forward` reports and measured real overlap.
  Confirmed: neither Zenith nor Daybreak has anything close to
  Aurelius/Fulcrum's 99.5% same-bar problem (all three pairwise same-M5-bar
  rates are 1-5%). But two things previously not known: (1) **same-day
  direction agreement is far above chance for every pair** (e.g.
  Zenith↔Aurelius 97.3% vs 64.9% expected from base rates, Daybreak↔Aurelius
  92.8% vs 55.3% expected) - they enter at independent times but
  overwhelmingly take the same side, which matters for tail-risk days (5 of
  44 months had all three losing together) even though same-bar overlap
  looks clean; (2) **Daybreak is more correlated with Aurelius than Zenith
  is** (daily P&L r ≈ +0.21, monthly r ≈ +0.41, 41% of entries within an
  hour of each other, vs Zenith's r ≈ -0.09/-0.03) - Zenith is the genuine
  diversifier of the two, which is awkward given the critical finding above
  means Zenith is currently the weaker, more mis-calibrated system. **The
  "which of these two to run alongside Aurelius" decision should be
  revisited once Zenith's dollar-input recalibration is done**, not decided
  on the pre-recalibration numbers.
- **Verified correct, no action needed**: the DST sign convention itself
  (re-derived independently via the UTC/server-time relationship, not just
  re-checked) confirmed correct in both gap directions, in both files. The
  `InpORBars` hour-rollover concern from earlier this session was confirmed
  real in principle but already fully guarded against by Daybreak's own
  `OnInit()` validation (refuses to start outside 1-11) - no fix needed,
  the earlier "latent bug" framing was itself corrected. Zenith's
  `ComputeLotSize()` was checked against the exact bug classes found in
  Fulcrum/Ratchet (zero/invalid stop distance, volume min/max/step) and has
  neither - it was already done correctly.
- **Minor/cosmetic, fixed**: Daybreak's panel showed the raw
  `InpSessionHour` instead of the DST-adjusted hour actually in effect,
  contradicting the code for ~3 weeks/year (fixed, v1.15). Not fixed (low
  priority, noted for later): Zenith's panel only ever draws from inside
  `OnTick()` (no `OnInit`/timer fallback) - a milder version of Fulcrum's
  missing-panel bug, less severe since it's a single `Comment()` call, not
  chart objects; Daybreak's `g_dayTraded` flag is set after the
  spread/trade-allowed/ATR gates rather than before, a minor divergence
  from the validated Python "first qualifying breakout only" rule; a
  cosmetic float-rounding wart in Zenith's lot-step flooring; and a
  balance-vs-equity inconsistency in what "risk %" is measured against
  across the 5 EAs (Zenith uses `ACCOUNT_EQUITY`, Aurelius/Fulcrum/Ratchet/
  Daybreak's new code uses `ACCOUNT_BALANCE`) - worth a deliberate,
  cross-EA decision rather than a silent fix, since equity is what makes
  item 9's shared daily-loss breaker concept work but balance is more
  stable against open floating P&L for per-trade position sizing.

## 12. Zenith's absolute-dollar inputs converted to H4-ATR multiples

Followed through on item 11's open task. Converted all six of Zenith's
absolute-dollar risk/exit inputs to multiples of H4 ATR(14) - the same
timeframe/basis `watchAtr` (the zone-detection ATR) already uses, so the
entry-side conversion needed no new plumbing:

- `InpPullbackUSD` → `InpPullbackATR` (0.5844), `InpFixedTargetUSD` →
  `InpFixedTargetATR` (5.844), `InpMaxLossUSD` → `InpMaxLossATR` (3.507),
  `InpMinLossUSD` → `InpMinLossATR` (0.935) - all multiply `watchAtr`
  directly at the existing entry-side call site (no new state needed).
- `InpTrailActivateUSD` → `InpTrailActivateATR` (7.013), `InpTrailUSD` →
  `InpTrailATR` (3.507) - these manage an already-OPEN position, where
  `watchAtr` isn't in scope and using the entry-time snapshot would freeze
  the trail at whatever volatility existed when the trade opened. Added
  `CurrentH4ATR()`, a small on-demand helper (reuses the file's own
  `ComputeWilderATR`, deliberately not the built-in `iATR()` - same reason
  Zenith already avoids it for zone detection) that recomputes H4 ATR(14)
  fresh via `CopyRates`, caching the last valid read so a single short
  `CopyRates` call doesn't zero out the trail thresholds mid-trade. The
  trail now reacts to current volatility rather than entry-time volatility
  - arguably the more correct behaviour for a trailing stop regardless of
    the original bug.

**Calibration, not independent re-validation**: multipliers were computed
as `original_dollar_default / 2023's median H4 ATR ($8.556)` - chosen as
the reference year because that's when `InpMaxLossUSD`'s cap was least
often binding (10% of losing trades, vs 92% in 2026), i.e. closest to the
system's original validated behaviour. This means the new ATR-based
inputs reproduce the original 2023-era dollar behaviour almost exactly by
construction, then float with H4 ATR going forward instead of staying
frozen. This was NOT independently re-validated with a full Python
resimulation the way the original $30/$5/$8/$60/$30/$50 defaults were -
**re-run a fresh MT5 backtest after this change** to confirm real
performance, same as every other change this session.

## 13. Standing infrastructure note

`git push -u origin claude/code-review-fqadq0` fails identically every
attempt this entire session with a 403 — Claude's GitHub App lacks access
to `marcoreed84-bit/test-project` for this org. Fix is on the user's side
(org admin installs the app, or reconnect GitHub in claude.ai settings).
All work is committed locally regardless and delivered to the user
directly via file attachments each time.

**UPDATE 2026-09-19**: the 403 finally cleared (see incident note below) —
`git push` now succeeds. This item is resolved, but the "deliver via file
attachment too, don't rely on push alone" habit stays — see the incident
note for why.

## 14. Zenith/Daybreak brought up to the family's visual standard (2026-09-05)

Pure visual/cosmetic pass — no signal, entry, exit, risk-sizing, or
circuit-breaker logic touched in either file. Brings both up to the same
panel/theme standard item 3 already shipped to Aurelius/Fulcrum/Ratchet
(neon-blue/white-on-black chart theme, `C'13,17,28'` panel background,
`C'0,150,255'` neon-blue panel edge, `PFrame()`'s explicit 4-strip border
instead of `OBJ_RECTANGLE_LABEL`'s own unreliable `BORDER_FLAT`, and the
"show something the moment it attaches" `OnInit()` panel draw — the exact
Fulcrum missing-panel-at-attach bug this session already found once).

- **Daybreak_EA.mq5 (v1.15 → v1.16)**: already had the full panel primitive
  system and already matched the chart-theme colours exactly. Two real
  gaps closed: (1) `PFrame()` didn't exist in this file at all — the
  panel's "bg" rect was drawing its own border via `PRect(..., InpPanelEdge,
  2)`, i.e. exactly the unreliable `BORDER_FLAT` pattern already replaced
  everywhere else. Added `PFrame()` (ported verbatim from Aurelius) plus the
  matching opaque "fl" fill rect Aurelius/Fulcrum/Ratchet already draw on
  top of "bg", and wired both into `DrawPanel()` — "bg" itself now only
  supplies the fill, never the border. (2) `InpPanelBg` `C'5,5,14'` →
  `C'13,17,28'` and `InpPanelEdge` `C'0,255,255'` → `C'0,150,255'`, matching
  the shared palette. A side-by-side read of the rest of `DrawPanel()`
  against Aurelius found row spacing, section-header styling, and font
  already consistent — nothing else changed. Daybreak's own
  `g_panelReclaim`-style flash-avoidance was deliberately NOT added: unlike
  Aurelius/Fulcrum/Ratchet, Daybreak's `DrawPanel()` is only ever called
  once per M5 bar (no 1-second timer, no per-tick between-bar refresh), so
  the flashing problem that mechanism exists to solve doesn't occur here —
  adding it would be an unrequested feature, not a fix.

- **Zenith_EA.mq5 (stays "1.00", no version bump — inline dated header note
  instead, per this file's own established convention)**: had NO chart-theme
  inputs and NO positioned panel at all before this — only a single
  `Comment(txt)` line, drawn solely from inside `OnTick()` with no
  `OnInit`/timer fallback (a milder version of the same missing-panel-at-
  attach bug, already flagged as a known-but-unfixed cosmetic item in item
  11 above). Built from scratch, ported from Aurelius: chart theme
  (`InpApplyTheme`/`InpChartBg`/`InpBullCol`/`InpBearCol`, applied via
  `PTheme()` at `OnInit`), the full `PRect`/`PText`/`PSection`/`PRow`/
  `PFrame`/`PBackground` primitive set (object prefix `ZENP_`/`ZENW_` — no
  clash to adapt around, since this file created no chart objects before),
  and a new `DrawPanel()` that restructures the old one-line `Comment(txt)`
  into sectioned rows: SIGNAL (watching/pending-order counts — straight from
  the old Comment() text), CIRCUIT BREAKER (`g_pausedUntil`/`g_consecLosses`
  — already tracked by this session's own circuit-breaker work, just never
  shown on a panel), POSITION (direction, entry, current SL, floating P/L,
  bars held, trailing-armed state — all already-tracked globals, no new
  metrics), and ACCOUNT (balance/equity — no `g_dayStartEquity`-style
  "today's P&L" tracking exists anywhere in this file, unlike
  Aurelius/Fulcrum/Ratchet, so this shows equity/balance instead, per the
  task's own fallback, rather than inventing a feature Zenith doesn't have).
  `DrawPanel()` is now called directly in `OnInit()` (fixes the
  missing-panel-at-attach gap) and uses the same `g_panelReclaim`
  delete-vs-update-in-place mechanism as Aurelius (full reclaim once per new
  M15 bar; in-place update, throttled to once per unique `TimeCurrent()`
  second, for the live between-bar refresh) plus `g_skipCosmeticDraws` to
  skip the panel entirely in a non-visual Strategy Tester pass. This
  throttle/skip pair was added proactively, not explicitly requested: the
  old between-bar call site called the (cheap) `Comment()` on literally
  every tick with no throttle at all, and wiring real chart objects into
  that same call site unthrottled would reproduce the exact multi-hour
  real-tick-backtest slowdown already found and fixed 3 times this session
  in Aurelius (v1.31–v1.33) — carrying that fix forward here at the same
  time as the panel itself, rather than shipping a known-reproducible
  regression and fixing it in a follow-up pass.
  **Deliberately not added** (out of scope per the task, not overlooked):
  `PWatermark()` — the task's port list for Zenith named only
  PRect/PText/PSection/PRow/PFrame/PBackground, not PWatermark, and Zenith
  has no watermark text/asset convention of its own to draw from; a
  background wallpaper image — `InpBackgroundBMP` ships empty (no asset
  exists for Zenith, unlike Aurelius/Fulcrum/Ratchet's `.bmp` files), so
  `PBackground()` is a no-op unless one is supplied later; and the D1 trend
  filter's live pass/fail state — `Comment()` never surfaced it either
  (its true/false lives only inside a local variable in `OnTick()`, not a
  global), so showing it now would be a new metric, not a restructuring of
  what already existed.

## 15. Second Opus review (item 12 + item 14 together) — one real blocker fixed, plus cleanup (2026-09-05)

A third review pass, checking the item-12 ATR conversion and the item-14
visual build together against each other and against the live sibling
files, found one genuine pre-live blocker and several smaller real issues.
All fixed in Zenith_EA.mq5/Daybreak_EA.mq5 before delivery:

- **BLOCKER, fixed**: `CurrentH4ATR()` returns `0.0` until its first
  successful read. None of the three trailing-stop sites added in item 12
  guarded against that. On a restart with an open position,
  `RestoreTrailingState()` runs from `OnInit()` *before* any tick has given
  `CurrentH4ATR()` a chance to succeed — a cold `CopyRates()` there would
  zero out `InpTrailATR`/`InpTrailActivateATR`, unconditionally arm the
  trail, and reconstruct a garbage peak; the live per-tick site would then
  place a new SL at the current market price on the very next tick,
  **closing an open position outright**. This is invisible in a Strategy
  Tester run (H4 history always exists there, and there's never an open
  position at `OnInit`), so a fresh backtest would not have caught it.
  Fixed: all three sites (`OnInit` restore, stale-state resync, and the
  live per-tick update) now treat `atr <= 0.0` as "no information" and
  leave the trail/position untouched for that cycle rather than acting on
  a zero reading.
- **Real accuracy issue, fixed**: four of the six item-12 inputs
  (`InpPullbackATR`/`InpMaxLossATR`/`InpMinLossATR`/`InpFixedTargetATR`)
  were multiplying `watchAtr` — the H4 ATR at the zone's *fractal bar* —
  not current ATR as item 12's own header claimed. A zone can be traded up
  to ~2000 H4 bars (~333 days) after its fractal formed, on a symbol whose
  ATR has moved ~6x in 3 years, so these could carry a stale ATR reading
  into the dominant risk term. Fixed: those four now use a fresh
  `CurrentH4ATR()` reading (with the same cold-start guard — skip the
  candidate rather than trade with a zero ATR). The zone-geometry stop
  itself (`zlo`/`zhi` ± `InpStopBufATR * watchAtr`) is untouched — that one
  is meant to reflect the zone's own formation-time volatility, not
  current conditions, and was never part of the item-12 conversion.
- **Consistency fix**: `CurrentH4ATR()` read from `CopyRates` start_pos
  `0` (the still-forming H4 bar), unlike every other rates read in this
  file, which uses start_pos `1` specifically because using the forming
  bar "was the bug that caused zero trades" (this file's own pre-existing
  comment). With Wilder-14 the forming bar carries ~7% weight, making the
  trail distance wobble intra-bar for no reason. Changed to start_pos `1`.
- **Calibration rounding drift, fixed**: `InpMaxLossATR`/`InpTrailATR`
  (both derived from the same $30.0 default) shipped as `3.507` instead of
  the correctly-rounded `3.506` — an apparent double-rounding artifact.
  Corrected to `3.506`. Economically meaningless at the reference ATR
  ($0.006), fixed for correctness anyway.
- **Daybreak's visual pass was only ~20% complete, now finished**: item 14
  fixed 2 of the 10 panel-palette values that actually differed from
  Aurelius/Fulcrum/Ratchet/Zenith (`InpPanelBg`/`InpPanelEdge`) and left the
  other 8 (`InpPanelY` plus `InpHeaderBg`/`InpTitleCol`/`InpSectionCol`/
  `InpTextCol`/`InpValCol`/`InpOkCol`/`InpNoCol`/`InpShadowCol`) as
  Daybreak's own distinct neon-magenta/yellow/mint scheme — so the panel
  still read visibly different from every sibling despite the changelog
  saying otherwise. All 9 now match (Daybreak v1.17); `InpTitleCol` uses
  the gold Aurelius/Zenith share, since the family was never unified on
  that one specific input either way (Fulcrum/Ratchet use blue).
- **Two incorrect comments, fixed**: Zenith's `PBackground()` header
  claimed a future wallpaper image would get "the same centring/retry
  behaviour" as Aurelius's — false, since Zenith only calls `PBackground()`
  once (from `OnInit`), unlike Aurelius's three call sites (`OnInit`,
  `OnTimer` for retry, chart-resize for re-centring) — Zenith has no
  `OnTimer` at all. Daybreak's new "fl" fill-rect comment claimed the same
  anti-stacking justification Aurelius uses - which depends on `PRect()`
  reclaiming (delete+recreate) every cycle, something Daybreak's `PRect()`
  doesn't do - making "fl" a harmless duplicate here for a different reason
  than stated. Both comments corrected to describe what's actually true in
  each file.
- **Small robustness/cleanup fixes**: Zenith's wrong-timeframe
  `Comment("Zenith_EA requires the M15 chart...")` never got cleared on
  `OnDeinit`, so it could stay stuck on the chart forever after the EA was
  removed — fixed. The same wrong-timeframe branch was calling
  `ObjectsDeleteAll()` on every single tick instead of once — gated behind
  a `static bool`. `OnChartEvent`'s two `DrawPanel(false)` calls weren't
  gated by `g_skipCosmeticDraws` like every other panel call site (harmless
  in practice — a chart event can't fire during a non-visual Tester pass —
  but inconsistent) — fixed for consistency.
- **Everything else from this review was a confirmed false alarm**: the
  `g_watch`-prefix object-name-clash concern, `ArraySetAsSeries(h4, false)`
  being wrong or unnecessary, the cold-start fallback affecting the
  zone-geometry stop (it can't — `watchAtr` is guaranteed positive by
  `BuildH4Events`'s own filter), the panel throttle suppressing the first
  draw after a fill, duplicate default-parameter values, and the `PFrame`/
  "fl" layering hiding the border — all checked directly against the code
  and confirmed not to be real issues.
- **Noted but deliberately not fixed this pass** (documented, not
  overlooked): the trailing stop now ratchets tighter on transient ATR
  dips and never loosens back (a real behavioural nuance of switching from
  a fixed dollar trail to an ATR-based one — worth a deliberate design
  decision, not an accidental bug); Zenith's peak/armed reconstruction on
  restart is now only approximate rather than exact, since the ATR used to
  invert a stored SL back into a peak is "now," not "when that SL was
  set" (low-frequency, restart/resync only); Zenith has no `OnTimer`, so
  its panel freezes at the last tick's values over a weekend or closed
  session (Aurelius/Ratchet both run a 1-second timer specifically to
  avoid this); and a cosmetic-only clock mismatch between Zenith's
  cooldown-row display and its actual cooldown gate. None of these affect
  correctness of a live trade the way the blocker above did.
- **Compile-risk assessment**: no duplicate default parameters, no
  duplicate symbol definitions, and every type-cast/construct checked
  against already-shipping precedent in sibling files. Could not run the
  actual MetaEditor compiler — confidence is high but not certified;
  compile both files before attaching to a live/demo chart.

## 16. Three more EAs join the portfolio: AuRebound, Tailwind, Slipstream — a real cross-EA position bug found and fixed (2026-09-05)

The user brought in three more EAs (all H4/trend-continuation systems, a
different family from the gold-trio + Zenith/Daybreak): AuRebound_EA.mq5,
Tailwind_EA.mq5, Slipstream_EA.mq5. Reported they "took very long on the
tester" and raised a real, concrete concern: at some point running
multiple EAs live, Aurelius (5-min chart) placed a sell while one of these
4-hour EAs placed a buy at the same time, and it seemed like "only one
would have won the trade."

**Account mode confirmed hedging** (user checked directly) — multiple
independent positions per symbol genuinely coexist at the broker, ruling
out netting-mode merging as an explanation.

**Investigated and found a real, separate bug — Tailwind and Slipstream
closed/modified positions by SYMBOL, not by ticket.** Every other EA in
the portfolio (Aurelius, Fulcrum, Ratchet, Zenith, Daybreak, AuRebound)
closes/modifies via a specific ticket (`pos.Ticket()`/`g_ticket`/
`posTicket`). Tailwind and Slipstream instead called
`trade.PositionClose(_Symbol, ...)`, `trade.PositionModify(_Symbol, ...)`,
`trade.PositionClosePartial(_Symbol, ...)` — CTrade's symbol-based
overloads, which resolve to *whatever* position MT5 finds on that symbol,
with no magic-number filter of their own. A magic-number check earlier in
the same function does NOT protect the close/modify call itself — it's a
separate internal position-select. Also found: both files' entry gate
(`if(PositionSelect(_Symbol)) return;`) blocked a new entry whenever *any*
EA held a GOLD# position, not just their own, and their post-fill
entry-price capture could read a *different* EA's entry price if the
timing lined up wrong. **Fixed**: added `FindOwnPosition()` (the same
symbol+magic-scoped pattern AuRebound already used correctly) plus a
`g_ticket` global to both files, and converted every position-close/
-modify/-partial-close call, the entry gate, and the entry-price capture
to use it. Tailwind v1.01→v1.02, Slipstream v1.02→v1.03. No signal/entry
logic touched.

**The specific Aurelius/AuRebound incident itself, however, was
confirmed NOT a bug** — asked the user directly what they actually
observed, and both trades existed as separate, independent tickets; one
was simply profitable and the other wasn't. That's normal and expected
when two systems on different timeframes (5-min vs 4-hour) disagree about
direction in a genuinely hedging account — there's no "winner take all"
mechanism, each position resolves on its own price action. Worth keeping
distinct from the real bug above: the *diagnosis instinct* was right
(something about cross-EA interaction was worth checking), but the
specific incident recalled wasn't actually the manifestation of it —
AuRebound's own code was already correctly ticket/magic-scoped throughout
(`FindOwnPosition()` checks both symbol and magic; every close/modify
call already uses `posTicket`). The bug that WAS found (Tailwind/
Slipstream) is a real, live risk for whenever those two specifically run
alongside anything else — just not the explanation for the one incident
recalled.

**Still open at this point**: the user's other two asks — why these three
took so long on the Strategy Tester, and bringing their visuals up to the
shared standard — are being worked on next (visual pass delegated to a
background agent; performance diagnosis and a full correctness review,
including checking AuRebound for anything analogous to the Tailwind/
Slipstream bug class, still to be done via a follow-up Opus review once
the visual pass lands, matching the sequencing that worked well for
Zenith/Daybreak earlier).

## 17. AuRebound/Tailwind/Slipstream brought up to the family's visual standard (2026-09-05)

Pure visual/cosmetic pass — no signal, entry, exit, risk-sizing, position-
management, or news-filter logic touched in any of the three files (the
item-16 ticket-scoping fix and the Calendar-API Tester-skip fix were left
exactly as they were). All three had the SAME simpler panel system
(direct `PRow`/`PSection`/`DrawPanelBackground` calls building
`OBJ_LABEL`/`OBJ_RECTANGLE_LABEL` objects straight from hardcoded colors),
distinct from — and missing several pieces of — the shared standard
already shipped to Aurelius/Fulcrum/Ratchet/Zenith/Daybreak. All three
needed the same set of fixes, so they were done as one consistent port
rather than three independent passes:

- **No `PFrame()` at all** (the item to check for first, per the task) —
  confirmed absent in all three; ported verbatim from Aurelius_EA.mq5: an
  explicit 4-strip border immune to `OBJ_RECTANGLE_LABEL`'s own unreliable
  `BORDER_FLAT` (only 2 of 4 sides render live). `DrawPanelBackground()` in
  all three now draws shadow → draggable "bg" → opaque "fl" fill reclaim →
  `PFrame()` border, the same 4-layer sequence Aurelius uses, instead of a
  single flat-bordered rectangle.
- **Palette**: none of the three had ANY of the standard's panel-specific
  color inputs (`InpPanelBg`/`InpHeaderBg`/`InpPanelEdge`/`InpTitleCol`/
  `InpSectionCol`/`InpTextCol`/`InpValCol`/`InpOkCol`/`InpNoCol`/
  `InpShadowCol`) — panel colors were hardcoded literals scattered through
  `PRow`/`PSection`/`DrawPanelBackground` (`C'12,12,16'`, `clrDimGray`,
  `clrSilver`, `clrDodgerBlue`/`InpColBuy` for section headers, `clrLime`/
  `clrOrangeRed` or `InpColExitProfit`/`InpColExitBEorLoss` for row state).
  Added all ten standard inputs at the shared default values (neon-blue
  `InpPanelEdge`, matching Fulcrum/Ratchet/Zenith/Daybreak) to all three,
  and rewired every panel primitive to use them. `InpColBuy`/`InpColSell`/
  `InpColExitProfit`/`InpColExitBEorLoss` were left untouched — those are
  chart-marker colors (entry arrows / exit diamonds), a separate concern
  from the panel's own row-state colors, and already matched the shared
  neon-blue/white/green/red-pink family scheme from an earlier pass this
  session.
- **Position**: `InpPanelY` was 45 in all three (`InpPanelX`=12 was
  already correct) — changed to 30, matching every other EA in the
  portfolio (just below MT5's own symbol/OHLC header bar).
- **Dragging**: none of the three had any drag support at all. Added
  `InpPanelDrag`, `g_panX`/`g_panY` globals, and a `CHARTEVENT_OBJECT_DRAG`
  handler in `OnChartEvent()` for all three, matching Aurelius/Zenith.
- **Object stacking / `g_panelReclaim`**: added the same flag/pattern
  Aurelius/Zenith use — `PRect`/`PText` only delete+recreate (to reclaim
  top-of-stack from a newly-drawn trade tag) when told to; a plain value
  refresh updates the same objects in place. This mattered most for
  Tailwind/Slipstream specifically: both call `DrawPanel()` unconditionally
  once per second between bars (see below), and without this flag that
  would have fully deleted and recreated every panel object every second on
  a live/demo chart — a visible flash, the exact failure mode this pattern
  exists to prevent in Aurelius. AuRebound has no per-tick/per-second
  redraw (only once per H4 bar or on a discrete trade event), so this isn't
  a live bug there, but the primitive was ported for consistency and
  because it's the structurally correct fix regardless of call frequency.
- **Performance / Tester throttle — the item the task specifically flagged
  for verification**: Tailwind and Slipstream's headers claimed a
  wallpaper/watermark/panel throttle fix already happened. Checked and
  confirmed it was real but **only half the standard** — both throttle to
  once per second of *simulated* time (`if(TimeCurrent()!=lastDraw)`), but
  neither skips the block entirely in a non-visual Strategy Tester pass
  (`MQL_TESTER && !MQL_VISUAL_MODE`), unlike Aurelius/Fulcrum/Ratchet/
  Zenith/Daybreak's `g_skipCosmeticDraws` pattern — a non-visual run was
  still repainting the whole panel every simulated second for a chart
  nobody can see. Added `g_skipCosmeticDraws` to both, gating that block.
  AuRebound had **no throttle of any kind** — its own header only
  documents the separate Calendar-API caching fix from item 16, not a
  wallpaper/panel one. Added `g_skipCosmeticDraws` there too, gating the
  once-per-bar wallpaper/watermark/panel calls inside `ProcessNewBar()` —
  the one call site that repeats across a whole backtest. Not a reported
  performance problem for AuRebound specifically (H4 bars are far fewer
  than a real-tick run's tick count), but brought in line with the family
  standard rather than left as the one file without it.
- **"Show something the moment it attaches"**: AuRebound already drew its
  panel directly in `OnInit()` — no fix needed. Tailwind and Slipstream's
  `OnInit()` never called `DrawPanel()` at all — the panel only appeared
  once the first tick reached `OnTick()`'s throttle block, a milder version
  of the exact Fulcrum missing-panel-at-attach bug found and fixed earlier
  this session. Added an explicit `DrawPanel()` call to both files'
  `OnInit()`.
- **Chart theme**: all three already had `InpChartBG=clrBlack`,
  `InpCandleUp=C'0,150,255'` (neon blue), `InpCandleDown=clrWhite` — these
  already matched the standard exactly (from an earlier pass this session
  unifying the palette across AuRebound/Tailwind/Slipstream), just under
  file-specific input names (`InpChartBG`/`InpCandleUp`/`InpCandleDown`
  instead of Aurelius's `InpChartBg`/`InpBullCol`/`InpBearCol`) rather than
  a separate `InpApplyTheme` toggle. Left as-is — same values, different
  names, not worth a breaking rename for inputs already live-shipped.
- **Version bumps and changelog**: AuRebound v1.02→v1.03, Tailwind
  v1.03→v1.04, Slipstream v1.04→v1.05 — each file's own header carries a
  dated entry describing exactly what changed, in that file's existing
  changelog style.

**Deliberately not changed** (documented, not overlooked):
- No new panel rows, sections, or metrics were added to any of the three —
  every existing row (BB/Stoch settings, live stats, filters, position
  block, legend) was recolored/reframed in place, not restructured.
- Aurelius's own gold `InpPanelEdge` exception was not propagated here —
  all three use the neon-blue edge, matching Fulcrum/Ratchet/Zenith/
  Daybreak (the majority convention), consistent with how the task framed
  Aurelius's gold edge as an Aurelius-only accepted exception.
- None of the three got the autofit row-height shrink Aurelius uses to
  keep the panel from overflowing a short chart window — that's not one of
  the standard's named palette/position/border/performance items, and
  none of the three had it before, so adding it would be new behavior
  rather than bringing existing visuals into line.
- Compile-risk assessment: brace/paren counts balanced in all three after
  every edit; every new object name checked for collisions with the file's
  own existing prefix scheme (no clashes found). Could not run the actual
  MetaEditor compiler — confidence is high but not certified; compile all
  three before attaching to a live/demo chart, same caveat as every other
  visual pass this session.

**Still open**: the performance diagnosis (why real-tick runs were slow
beyond the Calendar-API fix already made in item 16) and the full
correctness review — including checking AuRebound for anything analogous
to the Tailwind/Slipstream ticket-scoping bug class — are unchanged from
item 16's "still open" note; this pass was visual-only, per its own scope.

## GAP: items 18–23 not recovered

`Aurelius_EA.mq5`'s own header (InpP150/InpM600 comments) references
"SESSION_NOTES.md item 23" for a systematic MA period+method sweep dated
2026-09-07, and the file's changelog continues through v1.46 (2026-09-10)
and an Ichimoku research thread beyond that. This recovered copy of
SESSION_NOTES.md stops at item 17 (2026-09-05) — whatever was written for
items 18–23 (the MA sweep, `InpMinSlopeATR` gate-loosening test, and
whatever came after) was not saved by the user and is genuinely gone, the
same way the Ichimoku Python research was. Not reconstructed here — the EA
header comments for the specific inputs they affected (`InpP150`,
`InpM600`, `InpMinVolRatio`, `InpMinSlopeATR`) are the only surviving
record of those findings' real numbers, and are the source to defer to.

## 2026-09-19 incident: container reclaim, work loss, and recovery

**What happened**: mid-session, the working container was reclaimed
(normal behavior for this environment on inactivity) and replaced with a
fresh one. Nothing had reached GitHub — `git push` had been returning the
same 403 all session (see item 13) — so everything that existed only on
that container's disk was gone: the Ichimoku Python research engine and
every filter-test script, the Aurelius Python research engine, and the
underlying real GOLD H4/M5 price data and MT5 report extractions. This
`SESSION_NOTES.md` file itself was lost the same way and had to be
recovered from a user-saved copy (items 1-17 above).

**Recovered from the user's own saved copies** (uploaded back in): this
file (items 1-17), `Ichimoku_EA.mq5` (v1.04), `Aurelius_EA.mq5` (v1.46),
`Aurelius_M15_EA.mq5`, and fresh MT5 exports of GOLD# H4 (2001-06 to
2026-08, 23,608 bars) and M5 (2023-01 to 2026-08, 256,318 bars) price
data. All four `.mq5`/`.md` files are now committed to git; the two price
CSVs are large data files and live in the container's scratchpad only
(`scratchpad/data/GOLD_H4.csv`, `GOLD_M5.csv`) — not committed, since data
files don't belong in a code repo, but if lost again they need the same
MT5 History Center export the user already knows how to do.

**Not recovered, rebuilding from the real `.mq5` source instead**: the
Ichimoku and Aurelius Python research engines. Rebuilding the Aurelius
engine from `Aurelius_EA.mq5`'s real, versioned MQL5 logic (not from
memory) — see `research/aurelius/engine.py`, in progress. The EA file is
the authoritative spec; anything the Python model computes gets validated
against the CSV's own MT5-computed `chk_*` reference columns before being
trusted (confirmed so far: `EMA(21)` matches `chk_ema21` to rounding
precision; `chk_atr14` matches a plain SMA-of-True-Range, not Wilder,
independently confirming the EA header's own claim that this broker's
built-in `iATR()` is SMA-based, not Wilder-smoothed as MT5's docs claim).

**Root cause, plainly**: relying on ephemeral container disk as the only
copy of anything, while the one durable channel (git push) was silently
broken the whole time. The push 403 itself was already known (item 13)
and the established workaround — deliver files to the user directly, not
just rely on push — is exactly what made recovery possible here. That
workaround should have extended to this file and the Python research too,
not just the `.mq5` EA files.

**What changed as a result**:
1. `git push` is retried every turn regardless (standing instruction) —
   and as of this incident, it now succeeds (see item 13 update). Every
   commit made from here on actually reaches GitHub.
2. This file gets updated and committed immediately after any real
   finding, not batched — same discipline the `.mq5` files' own
   changelog headers already follow, just extended to research notes too.
3. Large Python research files belong in the repo (`research/<system>/`),
   not only in the ephemeral scratchpad, so they survive a reclaim even
   on the rare turn push might fail again.

## Pending / next steps

- [x] Recover GitHub access (was the item-13 403) — resolved 2026-09-19,
      push confirmed working.
- [x] Recover `Ichimoku_EA.mq5`, `Aurelius_EA.mq5`, `Aurelius_M15_EA.mq5`,
      `SESSION_NOTES.md` from user-saved copies.
- [x] Recover real GOLD H4/M5 price data via fresh MT5 export.
- [ ] Finish rebuilding the Aurelius Python engine (`research/aurelius/engine.py`)
      from the real `Aurelius_EA.mq5` v1.46 logic, validate against the
      header's own real MT5 numbers (837 trades/PF 1.51 backtest window,
      136 trades/PF 1.56 real Jan-Aug 2026 window) before trusting any new
      filter test built on top of it.
- [ ] Run the S&R touch-and-reject test on Aurelius's real M5 gate (the
      pending "test it on aurelius aswell" request from the Ichimoku
      thread) once the engine above is validated.
- [ ] Confirm whether the live/demo forward-test of `Ichimoku_EA.mq5` v1.04
      has actually been launched.
