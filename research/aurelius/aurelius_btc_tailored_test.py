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

RESULT: see the dated block filled in below after the run, and the full
log in aurelius_btc_tailored_output_2026-09-27.txt.
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
