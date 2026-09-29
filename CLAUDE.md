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
