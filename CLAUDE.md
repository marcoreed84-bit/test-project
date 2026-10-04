# Working standards for this repo (established 2026-09-28/29)

This project tests trading EAs/strategies for real live trading (real money, ZAR account). The standards below exist because they were each learned the hard way in one long session — several verdicts were reported, then reversed, because a simulator didn't actually match the real EA. Follow them before reporting any verdict as final, not after.

## The core rule

**Before telling the user a system "survives" or "does not survive," bar-match its research simulator against real MT5 trade logs, if any exist for that system.** Real reports live under `/root/.claude/uploads/<session-id>/` — search for `ReportTester` xlsx files matching the EA name. A simulator that hasn't been checked against real fills is a hypothesis, not a verdict. State clearly which category any given result is in.

## If a check shows something alarming

Do not report it immediately. A shockingly bad result (e.g. a 0% or single-digit-percent match rate) is more often a bug in the comparison script than a real problem — this happened twice tonight (a Vanguard bar-match off-by-one, an H&S check pointed at the wrong real report). Investigate the check itself first: confirm dates line up, confirm the real report's own Inputs section actually matches the simulator's parameters, confirm the comparison script uses the right bar index (signal bar vs. fill bar are often one apart).

## Known data gotchas

- `GOLD_M15_native.csv` / `GOLD_M15_extended`: real M15 data only starts **2014-06-13**. Before that it's daily/hourly bars mislabeled as M15 — filter it out of any full-history test, or you'll feed pattern-detection code on Gold years of garbage. Silver's equivalent file has no such contamination and needs no trim.
- Point sizes: SILVER = 0.001, GOLD/BTCUSD = 0.01. Always read `meta_point` from each CSV's own header line — never hardcode, this caused a real 10x spread-overcharge bug on Silver earlier in this project.
- `GOLD` vs `GOLD#` are different symbols/feeds in this project's history — confirm which one a script actually loads before trusting a result.
- `%PF` (profit factor) must always be computed on `pnl / entry_price`, never on raw price points — cross-instrument comparisons break otherwise (gold vs silver vs BTC price scales differ by orders of magnitude).

## Statistical discipline

- Walk-forward split: search/tune on an in-sample window, freeze parameters, evaluate on genuinely untouched out-of-sample data only.
- Random-timing null: same exit machinery, same real spread cost, entry count calibrated to match the real system's trade count — never a synthetic/frictionless baseline.
- Multiple-testing correction: K = the literal number of configurations actually searched, not an estimate. A result that only survives at K=1 but fails at the honest K is overfitting, not a bug — a different, more mundane failure mode than a construction defect, and worth naming as such.
- A real MT5 backtest "looking good" (decent PF, real trades, real fills) does not by itself mean the entry timing beats random — those are different questions. Both matter; don't conflate them when reporting to the user.

## Where things stand (as of 2026-09-29 — verify before trusting, don't just cite)

Full detail: `GOLD_AUDIT_2026-09-28.md` (repo root) and the audit trail under `research/*/audit_2026-09-28/`. Live status summary: https://claude.ai/artifact/9VsPFLLJ9bjczcL8UBxYsn

- **Aurelius M5 (Gold)** — keep running. Real edge, bar-matched 98.8% to real trades.
- **H&S (Gold and Silver)** — keep running, both. Full real-history random-timing test survives on both (p=0.01 each).
- **Ratchet (Gold)** — stop. No timing edge even at zero cost, confirmed four independent ways.
- **Meridian (Gold)** — drop. Passes only on the window it was tuned on; loses on untouched data.
- **Vanguard (Gold)** — drop, but for a different reason (overfitting, not a bug): simulator is faithful (96.7% bar-matched), the settings just came from searching ~24 combinations against the same data being judged.
- **Aurelius M15 (Gold)** — weak/pause. Only passes a random-timing comparison that turned out to be too easy to beat.

## 2026-10-04: three failed fix attempts on Vanguard/Meridian, and why the 2014-2022 window is now spent for Vanguard filter selection

Tried three separate ideas to fix Vanguard/Meridian's entry, each looked real on first pass, each failed on audit:

1. **H4 trend-alignment filter** (require last closed H4 bar's close vs its own 50-EMA agree with trade direction). First test: p=0.0000 on all three EAs (Vanguard M5, Vanguard M15, Meridian). Root cause of the "edge": the H4-bar lookup (`searchsorted(h4_time, t, side="left")-1`) picked the H4 candle still FORMING for any bar not exactly on an H4 boundary, leaking up to ~4h of future H4 price into every entry. Corrected alignment (`searchsorted(h4_time, t+bar_len, side="right")-2`) is now the standard pattern in this repo for any H4-bar lookup — but with it, the filter shows NO edge on any of the three EAs (p=0.12-0.44, several worse than no filter). Fully reverted; `InpUseH4TrendFilter` defaults false in all three EAs, code kept for reference.
2. **Low-vol regime restriction** (Vanguard M5 only works when trailing-ATR-percentile is in the bottom tercile). Tried a genuine walk-forward split (characterize threshold on 2014-2018, test on 2018-2022) to avoid circularity. Looked real (p=0.047) until audited: the "regime-matched" random null wasn't actually regime-matched (a real bug in how the null's entry opportunities were restricted), and the LOW tercile had in fact been picked by looking at data including the test half. Corrected: p=0.055, bootstrap CI on real %PF = [0.73, 2.07] (includes breakeven). Not real.
3. **Slow-EMA(2400) filter**, borrowed from Aurelius's own validated construction (Aurelius's "(H4)" label is misleading — `InpP2400` is actually a 2400-period EMA computed directly on M5 close, no cross-timeframe lookup, so no lookahead risk of class (1)'s kind). This one had no code bug, but the apparent edge (p=0.047) was almost entirely explained by simply cutting Vanguard's trade count by ~70% — a random-thinning control matched on trade count alone reproduces p=0.28. Tighter nulls (20,000 draws) put the raw number at p=0.050, indistinguishable from the threshold.

**Honest K across all three: ≥3** (three separate ideas tried against the same Vanguard 2014-06-13→2022-07-04 window in one day). Applying that correction (Šidák/Bonferroni) takes even the best raw p-value (~0.047-0.05) to ~0.14-0.15 — none of them would survive even if individually clean. **Do not re-try any of these three exact constructions, and treat Vanguard's 2014-2022 window as no longer a clean blind test for Vanguard-specific filter ideas** — it's been looked at three times now for this exact purpose. A real next attempt needs either genuinely fresh data (new real trading history accumulating from here forward) or an explicit K-aware significance bar going in, not applied after the fact.

Standing verdict for both Vanguard and Meridian is unchanged by any of this: still drop, for the original reasons already stated above.
