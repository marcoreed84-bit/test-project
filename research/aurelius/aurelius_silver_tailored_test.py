"""
Aurelius TAILORED to SILVER - a genuine joint per-instrument retune, walk-
forward validated (2026-09-27). See aurelius_tailored_common.py for the
full method, the search space, and the two real bugs found on the way
(silver spread charged at gold's point = 10x overcharge; raw 60-point
spread gate meaningless off gold).

QUESTION: frozen-gold Aurelius failed on SILVER. Two single-dimension
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

RESULT (2026-09-27) - FAILS on M15; M5 "survives" only at K=1 and does
not hold up to scrutiny. Full log: aurelius_silver_tailored_output_2026-09-27.txt,
follow-ups: aurelius_tailored_extra_checks_output_2026-09-27.txt.

M15 (IS 2014-06 -> 2021-10, OOS 2021-10 -> 2026-09, K_search=563):
  IS winner [ma x1.0, slope 0.5-off, S/R>=2.5, vol>=1.3, pb 1.0, stop 2.5,
  vwap 1.0, spread q97 + cost/ATR<=0.4, ssb on]: IS %PF 1.713 (n=94) ->
  OOS %PF 0.740 (n=375), 75.8th pct of random timing, p(K=1)=0.244.
  Even IN-SAMPLE it fails best-of-K from K=30 up. Only 4 of 189 eligible
  stage-1 configs had OOS %PF > 1 (median 0.807); every one-notch OOS
  neighbour of the winner is < 1 (median 0.762). Gross (spread not
  charged) OOS %PF is still only 0.903 - this is not just costs.
M5 (IS 2022-07 -> 2025-01, OOS 2025-01 -> 2026-09, K_search=573):
  IS winner [ma x3.0, slope 0.75-1.25, S/R>=2.5, vol>=1.6, pb 0.25,
  stop 1.5, vwap 0.1, no spread gate, ssb off]: IS %PF 1.443 (n=74) ->
  OOS %PF 1.624 (n=37), 98.0th pct, p(K=1)=0.021, p(K=4, the 4 walk-
  forwards this task ran)=0.080, p(K=10+)>=0.17, p(K=573)=1.0.
  Why it is NOT a survivor: 37 OOS trades in 1.7 yrs; dropping the best 3
  trades takes it to %PF 0.514; the OOS window is Silver's 2025-26
  ~$29->$73 rally (81% of OOS trades long) in which even the frozen gold
  config breaks even (1.002) and the random baseline is cost-crushed
  (median 0.31) - "beats random timing" is a very low bar here.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import aurelius_tailored_common as T

OUT = "/home/user/test-project/research/aurelius/aurelius_silver_tailored_output_2026-09-27.txt"


if __name__ == "__main__":
    tfs = sys.argv[1:] or ["M15", "M5"]
    f = open(OUT, "a")

    def log(s=""):
        print(s, flush=True)
        f.write(s + "\n"); f.flush()

    for tf in tfs:
        r = T.run_walkforward("SILVER", tf, split_frac=0.6, n_stage1=500, seed=2026, n_random=800, log=log)
        oos = r["rt_OOS"]
        pK = [x for x in oos["ladder"] if x[0] == r["K"]][0][2]
        p1 = oos["ladder"][0][2]
        log(f"\nVERDICT SILVER {tf}: IS %PF {r['is_s']['pf']:.3f} (n={r['is_s']['n']}) -> OOS %PF "
            f"{r['oos_s']['pf']:.3f} (n={r['oos_s']['n']}), OOS pct {oos['pctile']:.1f}, "
            f"p(K=1)={p1:.4f} [{T.verdict(p1) if r['oos_s']['pf'] > 1 else 'FAILS: OOS %PF <= 1'}], "
            f"p(K={r['K']})={pK:.4f} [{T.verdict(pK) if r['oos_s']['pf'] > 1 else 'FAILS: OOS %PF <= 1'}]\n")
    f.close()
