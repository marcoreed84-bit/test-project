"""
Aurelius TAILORED to BTCUSD - a genuine joint per-instrument retune, walk-
forward validated (2026-09-27). See aurelius_tailored_common.py for the
full method, the search space, and the two real bugs found on the way
(silver spread charged at gold's point = 10x overcharge; raw 60-point
spread gate meaningless off gold).

QUESTION: frozen-gold Aurelius failed on BTCUSD. Two single-dimension
sweeps (stop width, MA timescale) couldn't fix it. Does a JOINT retune of
MA scale + slope min/max + S/R distance + volume ratio + pullback
tolerance + stop + VWAP-exit buffer + an instrument-scaled spread gate
(+ the slope x S/R block on/off) find anything that holds up on data the
search never saw?

METHOD (the project's standard rigor, nothing new invented):
  - chronological 60/40 split of this instrument's own real history,
    per timeframe (M15 priority, M5 too);
  - stage 1: 500 random configs drawn from the 7.4M-point joint grid,
    scored on IS ONLY (max IS %PF, n_IS >= ~12 trades/yr);
  - stage 2: coordinate ascent from the stage-1 winner (every other value
    of every dimension, up to 2 passes), IS ONLY;
  - K_search = every config evaluated on IS (disclosed in the log);
  - the final IS winner is FROZEN and run once on OOS;
  - random-timing baseline (same exits, same spread gate, REAL spread
    charged, calibrated trade count, coin flip calibrated to the real
    long share) + bootstrap best-of-K ladder K = 1/10/30/50/100/K_search,
    on both IS (for contrast) and OOS (the answer);
  - reporting-only diagnostic: every IS-eligible stage-1 config also run
    on OOS, to see whether IS rank predicts OOS rank at all.
  %PF (percent-of-price) throughout, never raw points.

RESULT (2026-09-27) - nothing survives. Full log:
aurelius_btc_tailored_output_2026-09-27.txt, follow-ups:
aurelius_tailored_extra_checks_output_2026-09-27.txt.

M15 (split by bar count: IS 2017-07 -> 2023-08, OOS 2023-08 -> 2026-09;
BTC bars are 24/7 from 2022, so 60% of bars lands later than 60% of
calendar time; K_search=567):
  IS winner [ma x2.0, slope 0.1-0.8, S/R>=2.5, vol>=1.6, pb 0.1, stop 1.5,
  vwap 0.1, cost/ATR<=0.4, ssb off]: IS %PF 2.002 (n=89) -> OOS %PF 1.003
  (n=206), 86.1th pct, p(K=1)=0.145. IS rank barely predicts OOS rank
  (Spearman +0.16). OOS by year 0.68 / 2.89 / 0.72 / 0.77 - one good
  year (2024). Gross 1.325 - costs eat all of it.
M5 (IS 2023-11 -> 2025-08, OOS 2025-08 -> 2026-09, K_search=554):
  IS winner [ma x2.0, slope 0.75-2.0, S/R>=2.5, vol>=1.3, pb 0.1, stop 4.0,
  vwap 0.5, spread q80]: IS %PF 1.540 (n=125) -> OOS %PF 1.305 (n=114),
  93.1th pct, p(K=1)=0.067 (borderline), p(K=4)=0.25, p(K=554)=1.0.
  The most encouraging row of the four: positive in both OOS years
  (1.41 / 1.26), one-notch OOS neighbourhood robust (32 of 36 > 1, median
  1.25). But it is not statistically distinguishable from random timing
  even at K=1, the OOS is only 1.1 years, and without its best 3 trades
  it is 0.795. A candidate for real-MT5 forward testing at most, not a
  finding.
Spread-gate story, checked directly: the FROZEN GOLD config with the gate
simply removed (real spread still charged) is a net loser over BTC's full
M15 history (%PF 0.650, n=1610) - 2019-2020 are 0.09/0.15 when this
broker's recorded BTC spread was ~12,600 points (~1.3-1.6% of price).
Its 2023-2026 slice is 1.134 (n=577, 99.8th pct, p(K=4)=0.012), but that
row was looked at after seeing it (see extra_checks docstring) and the
same config over the whole history loses, so it is a regime, not a
transferable edge.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import aurelius_tailored_common as T

OUT = "/home/user/test-project/research/aurelius/aurelius_btc_tailored_output_2026-09-27.txt"


if __name__ == "__main__":
    tfs = sys.argv[1:] or ["M15", "M5"]
    f = open(OUT, "a")

    def log(s=""):
        print(s, flush=True)
        f.write(s + "\n"); f.flush()

    for tf in tfs:
        r = T.run_walkforward("BTCUSD", tf, split_frac=0.6, n_stage1=500, seed=2026, n_random=800, log=log)
        oos = r["rt_OOS"]
        pK = [x for x in oos["ladder"] if x[0] == r["K"]][0][2]
        p1 = oos["ladder"][0][2]
        log(f"\nVERDICT BTCUSD {tf}: IS %PF {r['is_s']['pf']:.3f} (n={r['is_s']['n']}) -> OOS %PF "
            f"{r['oos_s']['pf']:.3f} (n={r['oos_s']['n']}), OOS pct {oos['pctile']:.1f}, "
            f"p(K=1)={p1:.4f} [{T.verdict(p1) if r['oos_s']['pf'] > 1 else 'FAILS: OOS %PF <= 1'}], "
            f"p(K={r['K']})={pK:.4f} [{T.verdict(pK) if r['oos_s']['pf'] > 1 else 'FAILS: OOS %PF <= 1'}]\n")
    f.close()
