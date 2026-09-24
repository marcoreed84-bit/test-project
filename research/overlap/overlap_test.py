"""
PORTFOLIO OVERLAP: do the six EAs fight each other, and who wins when they do?

User's question, verbatim: "between these we have to check for overlap on
aurelius and vanguard i think, i need to know between them all of any
overlap, example when one is in a buy trade do the others also place buys,
or are they on occasions trades placed in the opposite direction and which
EA usually would win the trade direction" - across all six systems:
Aurelius_EA.mq5 (M5), Aurelius_M15_EA.mq5, Vanguard_EA.mq5 (M5),
Vanguard_M15_EA.mq5, Meridian_EA.mq5, Ratchet_EA.mq5 (M5-only by design, no
M15 variant exists or is expected).

This is a genuinely new, portfolio-level research question - not a fix to
any one EA, and no .mq5 file is touched by this work (or by this whole
research/overlap/ directory).

================================= CONSTRUCTION =================================
Trade lists: research/overlap/trades.py builds each system's REAL trade list
(entry_time, exit_time, dir, pnl) using its OWN current shipped-default
parameters and its OWN existing, already-validated Python simulator (see
that file's own module docstring for exactly which simulator, which
shipped-default values were verified against which .mq5 `input` lines, and
the one disclosed gap: Ratchet's sim.py has no field for v3.30's
InpTrailRunnerATR=6.0/InpTrailRunnerKeep=0.60, so it isn't modeled here -
same known limitation this repo's own divergence_exit_test.py carries).

DATA WINDOW (see trades.py's docstring for the full reasoning): the two
underlying GOLD# M5 exports behind these six simulators cover DIFFERENT
ranges (research/aurelius/engine.py's CSV: 2023-01-03..2026-08-14;
research/ratchet/bars.py's zip: 2022-06-27..2026-09-18 - confirmed to be
the same broker/symbol feed by reading both files' own `meta_symbol,GOLD#`
headers, not the GOLD-vs-GOLD# real-account mismatch flagged in this
repo's 2026-09-23 Meridian full-history note, which is about a different,
real MT5 report on a different account entirely). This study uses the
INTERSECTION: 2023-01-03 01:00 to 2026-08-14 23:55 (broker server time),
256,318 M5 bars - Aurelius/Vanguard's simulators ran over their own full
data range with entries outside this window dropped afterward; Meridian/
Ratchet's simulators took this window as an explicit start/end override
(their own data comfortably covers it with room to spare for every
indicator's warm-up, including the 2400-period MAs, which need only ~8.3
trading days to converge - detailed in trades.py).

VANGUARD'S TRADE LIST is generated WITHOUT its own live InpUseAureliusFilter
(default ON in both Vanguard_EA.mq5 and Vanguard_M15_EA.mq5) as the primary/
default output used in every number below EXCEPT the two dedicated filter-
validation sections - a deliberate choice, not an oversight: this study's
whole point is to measure the portfolio's NATURAL, unmitigated overlap
structure across all 15 pairs, 14 of which have no cross-EA filter at all;
running Vanguard pre-filtered would make Aurelius-vs-Vanguard's opposite-
direction numbers artificially near-zero by construction and say nothing
about whether that filter is earning its keep, which is exactly one of the
questions asked. The two "LIVE FILTER VALIDATION" sections below switch it
back on and measure its real effect directly, reproducing AureliusBlocksEntry()
exactly (dir opposes an ALREADY-OPEN Aurelius position at the exact entry-
decision bar) using this same study's own Python-simulated Aurelius trade
list as the "real position" ground truth - not the real MT5 deals
research/aurelius/vanguard_aurelius_position_filter_test.py used for its
one-account validation, a disclosed method difference chosen so all 15
pairs and both filter checks share one uniform construction.

OVERLAP METHOD: every system's trades are projected onto one shared M5 bar
grid (the master grid = engine.py's own 256,318-bar GOLD# M5 file, i.e. the
finest timeframe in play; M15 trades' exact entry/exit timestamps land on
this grid natively since M15 = 3 M5 bars) as a per-bar position-direction
array (+1/-1/0). For a pair (A,B):
  - TIME overlap = bars where both are open, as a fraction of EACH side's
    own total open time (both directions reported - they differ a lot here,
    since e.g. Vanguard is open ~48-50% of the whole window across a few
    hundred trades while Aurelius M5 is open only ~14% across many fewer,
    shorter-lived ones).
  - TRADE-COUNT overlap = fraction of each side's own trades that touch an
    open opposite-system position AT ANY POINT during their hold (not just
    at entry) - reported alongside, since it answers a related but
    different question than the time-based number.
  - SAME vs OPPOSITE direction = of the overlapping bars, the fraction
    where both sides' sign agrees vs disagrees (these two always sum to
    100% of the overlap, since both are nonzero and ±1 whenever "overlap"
    is true).
  - WHO WINS an opposite-direction disagreement: every maximal contiguous
    run of bars where both are open AND opposite is one "episode" (in
    practice, almost always exactly one specific trade of A against one
    specific trade of B, or occasionally A/B rolling into a new same-
    direction trade mid-episode without the OTHER side's direction
    changing - treated as one continuous episode either way, since the
    disagreement itself didn't change). For each episode, GOLD's own close
    price at the episode's start and end (engine.py's own M5 close series,
    used uniformly for every pair including the ones built from the
    ratchet bars.py data, since the common window is fully covered by
    engine.py's file) gives a real market move; whichever side's direction
    matches the sign of that move is called "right" for that episode.
    STATED PLAINLY, per this task's own instruction: this is NOT each EA's
    own realized trade pnl (a trade might be up big before the episode even
    starts) - it is specifically who read the market correctly DURING the
    disagreement window. It is also mathematically the same thing as mark-
    to-market pnl attribution over that window, since dir_A = -dir_B in
    this bucket by construction (zero-sum: whatever one gains from the
    move, the other loses) - not two independent checks, one metric stated
    two ways. Both a simple EPISODE-COUNT win rate and a DURATION-WEIGHTED
    win rate (some episodes last 5 minutes, others days) are reported,
    since they occasionally disagree and that disagreement is itself
    informative (see Vanguard_M5-vs-Meridian below).

======================================= RESULTS =======================================
Per-system (of the 256,318-bar/3.65y common window):
  System          n_trades  bars_open  %window_open
  Aurelius_M5          885     36,424        14.2%
  Aurelius_M15          401     54,058        21.1%
  Vanguard_M5           732    122,262        47.7%
  Vanguard_M15          633    126,939        49.5%
  Meridian             2252    100,880        39.4%
  Ratchet              2392     20,215         7.9%

All 15 pairs (opp% = fraction of overlapping TIME spent in opposite
directions; winner = duration-weighted, the more meaningful of the two -
see note below where it disagrees with the count-weighted winner):

  pair                          ov_bars  same%  opp%  n_episodes  winner(count)   winner(duration)
  Vanguard_M5 / Meridian          49919  87.9% 12.1%         318   Vanguard_M5         Meridian
  Vanguard_M15 / Meridian         51991  88.4% 11.6%         334   Vanguard_M15        Vanguard_M15
  Aurelius_M15 / Vanguard_M15     26454  92.5%  7.5%          87   Aurelius_M15        Aurelius_M15
  Vanguard_M15 / Ratchet           9615  92.7%  7.3%         130   Vanguard_M15        Ratchet
  Aurelius_M15 / Vanguard_M5      25037  92.8%  7.2%          98   Aurelius_M15        Aurelius_M15
  Vanguard_M5 / Ratchet            9147  94.0%  6.0%         109   Vanguard_M5         Ratchet
  Aurelius_M5 / Vanguard_M15      18212  95.6%  4.4%          55   Vanguard_M15        Vanguard_M15 (49.8/50.2, a coin flip)
  Aurelius_M5 / Vanguard_M5       17662  96.7%  3.3%          51   Aurelius_M5         Aurelius_M5
  Aurelius_M15 / Meridian         30246  98.0%  2.0%          54   Aurelius_M15        Aurelius_M15
  Vanguard_M5 / Vanguard_M15     111703  99.3%  0.7%          48   Vanguard_M15        Vanguard_M15
  Aurelius_M5 / Aurelius_M15      19500 100.0%  0.0%           0   n/a (never disagree)
  Aurelius_M5 / Meridian          22331 100.0%  0.0%           0   n/a (never disagree)
  Aurelius_M5 / Ratchet            6847 100.0%  0.0%           0   n/a (never disagree)
  Aurelius_M15 / Ratchet           8312 100.0%  0.0%           0   n/a (never disagree)
  Meridian / Ratchet              12020 100.0%  0.0%           0   n/a (never disagree)

Headline, all six: bars with 2+ systems simultaneously open = 149,497
(58.3% of the window); of those, ALL currently-open systems agree in
direction 92.8% of the time; mean pairwise same-direction-given-overlap
rate across all 15 pairs = 95.9%; mean number of systems open per bar
(unconditional, including bars where 0 or 1 are open) = 1.80.

Note on count-vs-duration disagreement (Vanguard_M5/Meridian): Vanguard_M5
"wins" more episodes by count (57.9%) but Meridian's wins last longer, so
by duration it is close to even (Vanguard_M5 48.9% / Meridian 51.1%) -
reported both ways rather than picking the more flattering one.

LIVE FILTER VALIDATION (InpUseAureliusFilter, default TRUE on both Vanguard
EAs) - two independent numbers per timeframe: the DIRECT gate-level effect
(of baseline VWAP+S/R-eligible breakout bars, how many does the filter
itself veto) and the NET end-to-end effect on the realized trade list
(cascade included - blocking one entry changes sim_full()'s single-position
sequencing downstream, so trade-count deltas are not 1:1 with the direct
block count; this is the real live-EA comparison, not a simplification):
  M5:  13 of 1593 eligible bars blocked (0.8%) -> net -7 trades, net pnl
       +$8.30 (732 trades/$2924.91 raw -> 725 trades/$2933.21 filtered).
  M15: 89 of 1050 eligible bars blocked (8.5%) -> net -57 trades, net pnl
       +$352.08 (633 trades/$2814.02 raw -> 576 trades/$3166.10 filtered).

============================================ VERDICT ============================================
This portfolio is MOSTLY CORRELATED, not independent, and the correlation
is concentrated in a specific structural pattern rather than spread evenly:
Aurelius, Meridian and Ratchet are all variants of the SAME underlying
construction (a multi-period MA-alignment trend read on GOLD - 21/50/150/
600/2400-family moving averages in a fixed order, just with different
exact periods/methods per file) and, over this entire 3.65-year window,
they have LITERALLY NEVER taken opposite-direction positions against each
other at the same time (0.0% opposite in every one of their four pairwise
combinations except Aurelius_M15/Meridian's razor-thin 2.0%) - despite each
one independently going short thousands of bars on its own. A dedicated
cross-filter among any pair of {Aurelius, Meridian, Ratchet} would have
virtually nothing to block; not warranted.

Vanguard (both timeframes) is the one genuinely different signal in this
portfolio - a diagonal trendline breakout, not an MA-alignment read - and
it is the source of essentially ALL the real directional disagreement seen
above, including a small amount against its own M15 sibling (0.7%, where
M15 tends to be the righter read, 70.8% by count / 75.9% by duration).
Vanguard's disagreement rate with the three trend systems ranges 2.0-12.1%
of overlapping time depending on the pair, and who tends to be right is NOT
uniform across pairs - stated plainly since a single portfolio-wide answer
would be dishonest here:
  - Aurelius M15 is the most reliably "right" side when it disagrees with
    either Vanguard timeframe or with Meridian (56.8-61.6% duration-
    weighted across all three) - the clearest, most consistent signal in
    the whole disagreement set.
  - Aurelius M5 vs Vanguard M5 leans Aurelius (61.7% duration-weighted) but
    Aurelius M5 vs Vanguard M15 is a coin flip (49.8/50.2).
  - Vanguard vs Ratchet (both timeframes) is close to even (48.9-52.9%
    either way) - no reliable edge either direction.
  - Vanguard vs Meridian - the single LARGEST disagreement rate in the
    whole portfolio (11.6-12.1% of overlapping time, 318-334 episodes,
    more than double any other pair) - is ALSO close to even by duration
    (48.9-53.5%), i.e. the pair that disagrees most has no reliable winner.

ON THE SHIPPED AURELIUS FILTER: the numbers support it, more clearly on M15
than M5. On M5 it is real but small (blocks well under 1% of eligible
entries, moves net pnl by +$8.30 on ~$2,925 of baseline net - directionally
consistent with, and similar in scale to, vanguard_aurelius_position_filter_
test.py's own real-MT5-deals-based validation ("barely touches trade
count"), which is reassuring cross-validation from a different data source
and method rather than a contradiction). On M15 it is meaningfully more
material - blocks 8.5% of eligible entries and adds +$352 (a >10% net pnl
uplift on ~$2,814 baseline) - consistent with Aurelius M15 being the single
most reliable "right" side in this whole disagreement analysis. Both
filters are net-positive here and neither looks like it's fixing a large
problem; M15's is the more clearly load-bearing of the two.

FLAGGED, NOT IMPLEMENTED - candidates for an equivalent filter elsewhere,
per this task's explicit instruction to flag but not build:
  - Meridian vs Vanguard (either timeframe) is the strongest CANDIDATE by
    sheer frequency (the largest opposite-direction rate of any pair here)
    but the WEAKEST candidate by evidence of which side to trust - a filter
    modeled on Aurelius's (block Vanguard against an open Meridian
    position, or vice versa) would be blocking a near-coin-flip, not a
    predictable loser, unlike the real pattern the Aurelius filter targets.
    Worth a dedicated real-MT5 test before drawing a conclusion either way,
    but this analysis does NOT predict it would help the way the Aurelius
    filter does.
  - Ratchet vs Vanguard (either timeframe): disagreement is infrequent
    (6.0-7.3%) and close to even when it happens - low priority.
  - No filter is warranted among {Aurelius, Meridian, Ratchet} - they
    don't fight, so there's nothing there to filter.
"""
import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/overlap")
import trades as T


def find_runs(mask):
    """Contiguous [start, end) index ranges where mask is True."""
    if not mask.any():
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    m = mask.astype(np.int8)
    d = np.diff(np.concatenate(([0], m, [0])))
    starts = np.flatnonzero(d == 1)
    ends = np.flatnonzero(d == -1)
    return starts, ends


def build_state(trs, ns, n):
    st = np.zeros(n, dtype=np.int8)
    for t in trs:
        ei = np.searchsorted(ns, t["entry_time"].value, side="left")
        xi = np.searchsorted(ns, t["exit_time"].value, side="left")
        ei = min(ei, n - 1)
        xi = min(max(xi, ei), n)
        st[ei:xi] = t["dir"]
    return st


def frac_trades_overlapping(trs, other_state, ns, n):
    if not trs:
        return 0, 0
    cnt = 0
    for t in trs:
        ei = np.searchsorted(ns, t["entry_time"].value, side="left")
        xi = np.searchsorted(ns, t["exit_time"].value, side="left")
        ei = min(ei, n - 1)
        xi = min(max(xi, ei), n)
        if xi > ei and (other_state[ei:xi] != 0).any():
            cnt += 1
    return cnt, len(trs)


def pairwise_stats(a_name, a_state, a_trades, b_name, b_state, b_trades, close, ns, n):
    overlap = (a_state != 0) & (b_state != 0)
    same = overlap & (a_state == b_state)
    opp = overlap & (a_state == -b_state)
    a_total = int((a_state != 0).sum())
    b_total = int((b_state != 0).sum())
    overlap_bars = int(overlap.sum())
    same_bars = int(same.sum())
    opp_bars = int(opp.sum())

    a_ov_trades, a_n_trades = frac_trades_overlapping(a_trades, b_state, ns, n)
    b_ov_trades, b_n_trades = frac_trades_overlapping(b_trades, a_state, ns, n)

    starts, ends = find_runs(opp)
    a_wins = b_wins = ties = 0
    a_wins_dur = b_wins_dur = ties_dur = 0
    for s, e in zip(starts, ends):
        move = close[min(e, n - 1)] - close[s]
        a_dir = a_state[s]
        dur = int(e - s)
        if move == 0:
            ties += 1
            ties_dur += dur
        elif np.sign(move) == np.sign(a_dir):
            a_wins += 1
            a_wins_dur += dur
        else:
            b_wins += 1
            b_wins_dur += dur

    return dict(
        a=a_name, b=b_name,
        a_total_bars=a_total, b_total_bars=b_total,
        overlap_bars=overlap_bars, same_bars=same_bars, opp_bars=opp_bars,
        a_ov_trade_frac=(a_ov_trades / a_n_trades) if a_n_trades else 0.0,
        b_ov_trade_frac=(b_ov_trades / b_n_trades) if b_n_trades else 0.0,
        a_n_trades=a_n_trades, b_n_trades=b_n_trades,
        n_opp_runs=int(len(starts)), a_wins=a_wins, b_wins=b_wins, ties=ties,
        a_wins_dur=a_wins_dur, b_wins_dur=b_wins_dur, ties_dur=ties_dur,
    )


def headline_stats(states, names, n):
    mat = np.stack([states[nm] for nm in names])
    open_count = (mat != 0).sum(axis=0)
    pos_count = (mat > 0).sum(axis=0)
    neg_count = (mat < 0).sum(axis=0)
    multi = open_count >= 2
    unanimous = multi & ((pos_count == 0) | (neg_count == 0))
    return dict(
        bars_multi_open=int(multi.sum()),
        bars_unanimous=int(unanimous.sum()),
        frac_unanimous=(unanimous.sum() / multi.sum()) if multi.sum() else float("nan"),
        frac_time_any_two_plus=multi.sum() / n,
        mean_open_count=float(open_count.mean()),
    )


def fmt_pct(x):
    return f"{100*x:5.1f}%"


if __name__ == "__main__":
    systems, data = T.build_all_systems()
    names = [nm for nm, _ in systems]
    trade_map = dict(systems)

    master_time = data["df5"]["time"].values.astype("datetime64[ns]")
    master_close = data["df5"]["close"].values.astype(float)
    n = len(master_time)
    ns = master_time.view("int64")

    print(f"master grid: {n} M5 bars, {master_time[0]} .. {master_time[-1]}\n")

    states = {nm: build_state(trade_map[nm], ns, n) for nm in names}

    print("per-system: n_trades, bars open, % of window open")
    for nm in names:
        st = states[nm]
        print(f"  {nm:14s} n={len(trade_map[nm]):5d}  bars_open={int((st!=0).sum()):7d}  "
              f"%window={fmt_pct((st!=0).sum()/n)}")

    print("\n" + "=" * 100)
    print("PAIRWISE (15 pairs)")
    print("=" * 100)
    all_results = []
    for a, b in itertools.combinations(names, 2):
        res = pairwise_stats(a, states[a], trade_map[a], b, states[b], trade_map[b], master_close, ns, n)
        all_results.append(res)
        ov = res["overlap_bars"]
        same_r = res["same_bars"] / ov if ov else float("nan")
        opp_r = res["opp_bars"] / ov if ov else float("nan")
        a_ov_frac_time = ov / res["a_total_bars"] if res["a_total_bars"] else float("nan")
        b_ov_frac_time = ov / res["b_total_bars"] if res["b_total_bars"] else float("nan")
        print(f"\n{a} vs {b}")
        print(f"  time overlap: {a}={fmt_pct(a_ov_frac_time)} of its own open time, "
              f"{b}={fmt_pct(b_ov_frac_time)} of its own open time "
              f"({ov} shared M5 bars = {ov*5/60:.0f}h)")
        print(f"  trade-count overlap: {fmt_pct(res['a_ov_trade_frac'])} of {a}'s {res['a_n_trades']} trades touch "
              f"an open {b} position at some point, {fmt_pct(res['b_ov_trade_frac'])} of {b}'s "
              f"{res['b_n_trades']} trades touch an open {a} position")
        print(f"  of overlapping time: same-direction={fmt_pct(same_r)}  opposite-direction={fmt_pct(opp_r)}")
        if res["n_opp_runs"]:
            tot_dur = res["a_wins_dur"] + res["b_wins_dur"] + res["ties_dur"]
            print(f"  opposite-direction episodes: n={res['n_opp_runs']}  "
                  f"{a} right(count)={res['a_wins']} ({fmt_pct(res['a_wins']/res['n_opp_runs'])})  "
                  f"{b} right(count)={res['b_wins']} ({fmt_pct(res['b_wins']/res['n_opp_runs'])})  "
                  f"ties={res['ties']}")
            if tot_dur:
                print(f"    duration-weighted: {a} right={fmt_pct(res['a_wins_dur']/tot_dur)}  "
                      f"{b} right={fmt_pct(res['b_wins_dur']/tot_dur)}  ties={fmt_pct(res['ties_dur']/tot_dur)}")

    print("\n" + "=" * 100)
    print("SUMMARY TABLE - all 15 pairs (sorted by opposite-direction rate, descending)")
    print("=" * 100)
    print(f"  {'pair':38s} {'ov_bars':>8s} {'same%':>7s} {'opp%':>7s} {'n_opp_ep':>9s} {'winner(count)':>18s} {'winner(dur)':>18s}")
    for res in sorted(all_results, key=lambda r: -(r['opp_bars'] / r['overlap_bars'] if r['overlap_bars'] else -1)):
        ov = res['overlap_bars']
        same_r = res['same_bars'] / ov if ov else float('nan')
        opp_r = res['opp_bars'] / ov if ov else float('nan')
        if res['n_opp_runs']:
            cw = res['a'] if res['a_wins'] > res['b_wins'] else (res['b'] if res['b_wins'] > res['a_wins'] else 'tie')
            tot_dur = res['a_wins_dur'] + res['b_wins_dur'] + res['ties_dur']
            dw = (res['a'] if res['a_wins_dur'] > res['b_wins_dur'] else
                  (res['b'] if res['b_wins_dur'] > res['a_wins_dur'] else 'tie')) if tot_dur else 'n/a'
        else:
            cw, dw = 'n/a', 'n/a'
        print(f"  {res['a']+' / '+res['b']:38s} {ov:8d} {100*same_r:6.1f}% {100*opp_r:6.1f}% "
              f"{res['n_opp_runs']:9d} {cw:>18s} {dw:>18s}")

    print("\n" + "=" * 100)
    print("HEADLINE ALL-SIX")
    print("=" * 100)
    h = headline_stats(states, names, n)
    print(f"bars with >=2 systems open: {h['bars_multi_open']} ({fmt_pct(h['frac_time_any_two_plus'])} of window)")
    print(f"  of those, ALL open systems agree in direction: {fmt_pct(h['frac_unanimous'])}")
    print(f"  mean number of systems open per bar (unconditional): {h['mean_open_count']:.3f}")
    mean_same = np.mean([r["same_bars"] / r["overlap_bars"] for r in all_results if r["overlap_bars"]])
    print(f"  mean pairwise same-direction-given-overlap rate across all 15 pairs: {fmt_pct(mean_same)}")

    print("\n" + "=" * 100)
    print("AURELIUS-M5 vs VANGUARD-M5 LIVE FILTER (InpUseAureliusFilter) VALIDATION")
    print("=" * 100)
    aur_state5 = T.aurelius_m5_position_state(data)
    same_as_built = np.array_equal(aur_state5, states["Aurelius_M5"])
    print(f"  aur_state5 matches the Aurelius_M5 state array built above: {same_as_built}")

    # DIRECT block count, at the entry-gate level - matches the established
    # convention research/aurelius/vanguard_aurelius_position_filter_test.py
    # already reports ("of the N baseline-eligible breakout bars, M were
    # blocked by a real opposing Aurelius position"). This is NOT the same
    # as comparing the two realized trade lists' lengths below, because
    # sim_full()'s single-position sequencing means skipping one entry can
    # let a LATER, different event fire that the raw run's "i < last_exit"
    # cap had suppressed - a genuine cascade, not a bug (the same cascade
    # research/ratchet/sim.py's own docstring insists must never be
    # filtered around). Both numbers are reported, clearly labelled.
    events, base_entry_ok = T._vanguard_entry_gates(data["ctx5"], T.VANGUARD_M5_FRACTAL_K, T.VANGUARD_MIN_SR)
    eligible = blocked = 0
    for i, d in events:
        if base_entry_ok[i]:
            eligible += 1
            a = aur_state5[i]
            if a != 0 and a != d:
                blocked += 1
    print(f"  DIRECT gate-level effect: of {eligible} baseline (VWAP+S/R-eligible) breakout bars, "
          f"{blocked} ({fmt_pct(blocked/eligible)}) are blocked by a real, already-open, opposing "
          f"Aurelius M5 position at that exact entry-decision bar")

    vg_raw = trade_map["Vanguard_M5"]
    vg_filtered = T.vanguard_m5_trades_with_aurelius_filter(data, aur_state5)
    trade_count_delta = len(vg_filtered) - len(vg_raw)
    raw_pnl = np.array([t["pnl"] for t in vg_raw])
    filt_pnl = np.array([t["pnl"] for t in vg_filtered])
    print(f"  NET end-to-end effect (cascade included, the real live-EA comparison): "
          f"raw n={len(vg_raw)} net={raw_pnl.sum():.2f}  ->  filtered n={len(vg_filtered)} "
          f"net={filt_pnl.sum():.2f}  (trade count {trade_count_delta:+d}, net pnl {filt_pnl.sum()-raw_pnl.sum():+.2f})")

    av = next(r for r in all_results if {r["a"], r["b"]} == {"Aurelius_M5", "Vanguard_M5"})
    print(f"\n  (for reference, from the pairwise block above) Aurelius_M5 vs Vanguard_M5 raw opposite-direction "
          f"episodes: n={av['n_opp_runs']}  Aurelius right={av['a_wins'] if av['a']=='Aurelius_M5' else av['b_wins']}"
          f"  Vanguard right={av['b_wins'] if av['a']=='Aurelius_M5' else av['a_wins']}")

    print("\n" + "=" * 100)
    print("AURELIUS-M15 vs VANGUARD-M15 LIVE FILTER (InpUseAureliusFilter) VALIDATION")
    print("=" * 100)
    # NOTE: aur_state15 lives on the M15 bar grid (ctx15's own ~85k bars),
    # NOT the M5 master grid states[...] above uses - a length mismatch, not
    # an equality check, so it isn't compared against states["Aurelius_M15"]
    # here the way aur_state5 was (that one happened to share the M5 master
    # grid exactly).
    aur_state15 = T.aurelius_m15_position_state(data)
    events15, base_entry_ok15 = T._vanguard_entry_gates(data["ctx15"], T.VANGUARD_M15_FRACTAL_K, T.VANGUARD_MIN_SR)
    eligible15 = blocked15 = 0
    for i, d in events15:
        if base_entry_ok15[i]:
            eligible15 += 1
            a = aur_state15[i]
            if a != 0 and a != d:
                blocked15 += 1
    print(f"  DIRECT gate-level effect: of {eligible15} baseline (VWAP+S/R-eligible) breakout bars, "
          f"{blocked15} ({fmt_pct(blocked15/eligible15)}) are blocked by a real, already-open, opposing "
          f"Aurelius M15 position at that exact entry-decision bar")
    vg15_raw = trade_map["Vanguard_M15"]
    vg15_filtered = T.vanguard_m15_trades_with_aurelius_filter(data, aur_state15)
    trade_count_delta15 = len(vg15_filtered) - len(vg15_raw)
    raw_pnl15 = np.array([t["pnl"] for t in vg15_raw])
    filt_pnl15 = np.array([t["pnl"] for t in vg15_filtered])
    print(f"  NET end-to-end effect (cascade included): raw n={len(vg15_raw)} net={raw_pnl15.sum():.2f}  ->  "
          f"filtered n={len(vg15_filtered)} net={filt_pnl15.sum():.2f}  "
          f"(trade count {trade_count_delta15:+d}, net pnl {filt_pnl15.sum()-raw_pnl15.sum():+.2f})")

    av15 = next(r for r in all_results if {r["a"], r["b"]} == {"Aurelius_M15", "Vanguard_M15"})
    print(f"\n  (for reference) Aurelius_M15 vs Vanguard_M15 raw opposite-direction episodes: "
          f"n={av15['n_opp_runs']}  "
          f"Aurelius right={av15['a_wins'] if av15['a']=='Aurelius_M15' else av15['b_wins']}  "
          f"Vanguard right={av15['b_wins'] if av15['a']=='Aurelius_M15' else av15['a_wins']}")
