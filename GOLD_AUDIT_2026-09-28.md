# Adversarial Gold-system audit (2026-09-28)

Independent Opus audit, spawned at the user's explicit request after two prior
verdict-reversals (Ratchet's missing trail-runner mechanism, Meridian's
exit-model gap) turned out to be bugs in the TESTING code, not the strategies.
Mandate: re-derive every number from raw code, don't trust cached results,
actively try to break each verdict. Full report below; evidence scripts are in
each system's `audit_2026-09-28/` subfolder.

## Bottom line

- **H&S: BUG FOUND, verdict flips from KEEP to "no demonstrated edge".** The
  research fill model entered trades at the neckline price whenever a bar came
  within 0.75 ATR of it - a price that often never traded, filling one bar
  early. The real EA waits for that bar to close and fills at market on the
  NEXT bar. Refilled with the EA's real timing: untouched-data %PF drops from
  1.628 (100th percentile) to 1.070/1.011 (32nd/36th percentile, p~0.7) -
  not distinguishable from random.
- **Meridian: verdict REFUTED.** The "SURVIVES, %PF 1.215, p~0 at K=50" result
  was measured on `GOLD_M5.csv`, the same 2022-2026 window Meridian was tuned
  on - not the untouched 2014-2022 slice it was claimed to be tested against.
  Run properly on untouched data with the EA-faithful `msim.py`: %PF 0.807 at
  real spread (loses money), 87.8th percentile, p=0.12. Fails in every 2-year
  block. Live MT5 also underperforms the simulator by ~47%, partly unmodeled
  swap (Meridian holds overnight; no simulator here models swap).
- **Aurelius M15: weaker than claimed.** Passes the repo's own random-timing
  test, but that comparison was too lenient (a coin-flip direction that often
  gets closed immediately by the trend-alignment exit). Against a stricter
  "trend-aligned random" comparison, untouched-data result is 88th percentile,
  p=0.12 - not significant.
- **Aurelius M5: CONFIRMED, the one system with a real, reproducible edge.**
  Simulator bar-matches 98.8% of real MT5 entries. Against the SAME stricter
  trend-aligned random comparison, untouched data: 100th percentile, p=0.000.
  Real edge, but nets close to breakeven in low-volatility/high-spread eras
  like 2014-2019 (2-year blocks: 1.05 / 1.17 / 0.69 / 1.00).
- **Ratchet: CONFIRMED NEGATIVE, and robust.** Every claimed number
  reproduces exactly. One bug found in `validate.py`/`noise.py` (comparing a
  real report against the wrong config version) turned out not to matter -
  the CORRECT comparison shows the simulator is actually ~30% OPTIMISTIC
  relative to real fills, meaning real execution is probably worse than the
  already-failing simulated result, not better. Zero-cost (gross signal, no
  spread) still fails to beat random (51.9th percentile) - there is no
  timing edge here at all, before any cost is even applied.

## Ranked recommendation

1. **Aurelius M5 — the only one worth keeping live.** Expect flat stretches
   in low-volatility periods; that's the honest shape of its edge, not a
   malfunction.
2. **Aurelius M15 — pause, or run at minimal size.** Edge on unseen data
   isn't statistically distinguishable from "just follow the trend."
3. **H&S — pause.** Its strong verdict came from a code bug giving it fills
   the real EA can't get. Real MT5 shows mild profitability (%PF 1.23,
   2020-2026) but that isn't evidence of skill once tested fairly.
4. **Meridian — pause or drop.** Loses money on data it wasn't tuned on;
   no better than chance. Real live results run ~47% below simulation.
5. **Ratchet — stop live trading it.** Clearest negative of the five. No
   timing edge even at zero cost, loses in every period tested, and the
   simulator flatters it rather than hurting it.

## Caveats the audit itself flagged

- Swap/overnight cost isn't modeled anywhere in this project. Mainly hurts
  Meridian and H&S (hold overnight); Aurelius and Ratchet flatten before the
  daily break.
- `hs_sim.py`'s trade count runs ~18% higher than the real EA (634 vs 538) -
  the exact H&S numbers above are approximate, though every EA-faithful fill
  model tried agrees on the direction (does not beat random).
- Aurelius M5's untouched-data pass rests on one simulator (98.8% bar-matched
  against real trades, so well-validated, but still one model).
- None of this proves future performance - only that Aurelius M5's entry
  filters carried real, repeatable information on data they never saw, and
  none of the other four did once tested the same way.

Full agent report, evidence scripts, and file-by-file citations: see the
`audit_2026-09-28/` subfolder under each of `research/trendbreaker/`,
`research/aurelius/`, `research/meridian/`, `research/ratchet/`.
