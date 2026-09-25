"""
User's sharper, more specific claim (2026-09-25, after Meridian's 5th real
live stop loss in a row): not "protect any profit early" (already tested
today, loses to holding on both EAs) - a NARROWER claim: if a trade was
meaningfully in profit and has since given almost all of it back within a
couple of hours, THAT specific shape is itself diagnostic that the trade
has failed, and should be cut near breakeven instead of being left to ride
to the real stop.

This is a genuinely different, more surgical test than trailing_tp_sweep_
test.py (which protects a floor the MOMENT a trigger is touched, clipping
winners that dip-then-resume). Here the trade is only cut once it has
ALREADY round-tripped almost all the way back to breakeven - much later,
much more conservative - so it should avoid punishing ordinary give-back
that resolves back in the trade's favor.

Method, on Meridian's real, EA-faithful trades (msim.py): walk each real
trade bar-by-bar from entry to its REAL exit, track the running favorable
excursion (peak floating profit). Once a trade has reached at least
MIN_PEAK profit, find the first bar afterward where floating profit has
decayed back to <= GIVEBACK_THRESH (near breakeven) - record that bar and
how many bars/hours after the peak it took. Then ask the real, decisive
question: of trades that DO give back to near-breakeven before their real
exit, what fraction go on to actually WIN anyway (recover past that point)
vs LOSE (continue on to the real stop)? If the vast majority go on to
lose, cutting there saves real money for a small, quantified cost against
the minority that would have recovered.
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "../meridian")
import numpy as np
import msim

np.random.seed(42)

MIN_PEAK = 5.0        # $ favorable excursion required before "gave it back" can even apply
GIVEBACK_THRESH = 1.0  # $ floating profit at/below this counts as "back near breakeven"


def analyze(trades, h, l, c):
    tagged = []
    for t in trades:
        d = t["dir"]
        a, b = t["entry_i"], t["exit_i"]
        entry = t["entry"]
        peak = 0.0
        peak_bar = a
        giveback_bar = None
        peak_bar_at_giveback = None
        for k in range(a, b + 1):
            fav = (h[k] - entry) if d > 0 else (entry - l[k])
            adv = (l[k] - entry) if d > 0 else (entry - h[k])
            if fav > peak:
                peak = fav
                peak_bar = k
            if peak >= MIN_PEAK and giveback_bar is None and adv <= GIVEBACK_THRESH:
                # peak_bar here is frozen at its value AS OF bar k - can only be <= k,
                # so this can never record a giveback before its own triggering peak
                giveback_bar = k
                peak_bar_at_giveback = peak_bar
        real_pnl = t["pnl"]
        tagged.append(dict(entry_i=a, exit_i=b, dir=d, peak=peak, peak_bar=peak_bar_at_giveback,
                            giveback_bar=giveback_bar, real_pnl=real_pnl, reason=t["reason"]))
    return tagged


if __name__ == "__main__":
    mctx = msim.build_ctx()
    win_start = mctx["t64"].min(); win_end = mctx["t64"].max()
    trades, _ = msim.simulate(mctx, start=win_start, end=win_end)
    h, l, c = mctx["h"], mctx["l"], mctx["c"]

    tagged = analyze(trades, h, l, c)
    reached_peak = [t for t in tagged if t["peak"] >= MIN_PEAK]
    gave_back = [t for t in reached_peak if t["giveback_bar"] is not None]
    held = [t for t in reached_peak if t["giveback_bar"] is None]
    never_reached = [t for t in tagged if t["peak"] < MIN_PEAK]

    print(f"Meridian real trades: n={len(tagged)}")
    print(f"  never reached ${MIN_PEAK:.0f} peak profit: {len(never_reached)} "
          f"({100*len(never_reached)/len(tagged):.1f}%)")
    print(f"  reached ${MIN_PEAK:.0f}+ peak: {len(reached_peak)} ({100*len(reached_peak)/len(tagged):.1f}%)")
    print(f"    of those, gave it back to near-breakeven before the real exit: {len(gave_back)} "
          f"({100*len(gave_back)/len(reached_peak):.1f}%)")
    print(f"    of those, held above near-breakeven until the real exit: {len(held)} "
          f"({100*len(held)/len(reached_peak):.1f}%)\n")

    print("=" * 78)
    print("Of the trades that GAVE BACK to near-breakeven before the real exit -")
    print("what actually happened to them afterward?")
    print("=" * 78)
    gb_pnl = np.array([t["real_pnl"] for t in gave_back])
    gb_wins = gb_pnl[gb_pnl > 0]
    gb_losses = gb_pnl[gb_pnl <= 0]
    print(f"  n={len(gave_back)}  went on to WIN anyway: {len(gb_wins)} ({100*len(gb_wins)/len(gave_back):.1f}%)"
          f"  went on to LOSE: {len(gb_losses)} ({100*len(gb_losses)/len(gave_back):.1f}%)")
    print(f"  real net from this whole group: ${gb_pnl.sum():.2f}")
    if len(gb_wins):
        print(f"  avg of the ones that recovered and won: ${gb_wins.mean():.2f} "
              f"(max ${gb_wins.max():.2f}) - this is what a breakeven-cut would sacrifice")
    if len(gb_losses):
        print(f"  avg of the ones that went on to lose: ${gb_losses.mean():.2f} "
              f"(worst ${gb_losses.min():.2f}) - this is what a breakeven-cut would have saved")

    # bars from peak to giveback (time it took to round-trip) - real distribution
    bars_to_gb = np.array([t["giveback_bar"] - t["peak_bar"] for t in gave_back])
    hours = bars_to_gb * 5 / 60.0
    print(f"\n  time from peak to giving it back: median {np.median(hours):.1f}h, "
          f"mean {hours.mean():.1f}h, 75th pct {np.percentile(hours, 75):.1f}h")

    print("\n" + "=" * 78)
    print("What a breakeven-cut-on-giveback rule would have actually done:")
    print("=" * 78)
    # simulate: for gave_back trades, exit AT the giveback bar's price instead of the real exit
    cut_pnls = []
    for t, tr in zip(tagged, trades):
        if t["giveback_bar"] is None or t["peak"] < MIN_PEAK:
            continue
        d = t["dir"]
        entry = tr["entry"]
        gb_i = t["giveback_bar"]
        # exit price at giveback bar: conservatively the WORSE of open/close at that bar (use close)
        exit_px = c[gb_i]
        pnl = (exit_px - entry) * d
        cut_pnls.append(pnl)
    cut_pnls = np.array(cut_pnls)
    real_pnls_same_group = np.array([t["real_pnl"] for t in gave_back])
    print(f"  n={len(cut_pnls)}")
    print(f"  REAL result for this group (held to Meridian's real exit): net=${real_pnls_same_group.sum():.2f}")
    print(f"  CUT-AT-GIVEBACK result for the SAME group: net=${cut_pnls.sum():.2f}")
    print(f"  difference: ${cut_pnls.sum() - real_pnls_same_group.sum():.2f} "
          f"({'better' if cut_pnls.sum() > real_pnls_same_group.sum() else 'worse'} to cut early)")

    # whole-portfolio effect: replace only the gave-back group's outcome, keep everyone else's real result
    all_real = np.array([t["real_pnl"] for t in tagged])
    gb_entry_set = {t["entry_i"] for t in gave_back}
    whole_with_cut = []
    for t, tr in zip(tagged, trades):
        if t["entry_i"] in gb_entry_set:
            d = t["dir"]; entry = tr["entry"]; exit_px = c[t["giveback_bar"]]
            whole_with_cut.append((exit_px - entry) * d)
        else:
            whole_with_cut.append(t["real_pnl"])
    whole_with_cut = np.array(whole_with_cut)
    print(f"\n  WHOLE PORTFOLIO real net (current, no giveback rule): ${all_real.sum():.2f}")
    print(f"  WHOLE PORTFOLIO net WITH the giveback-cut rule applied only to this group: "
          f"${whole_with_cut.sum():.2f}")
    print(f"  net effect of adding this rule: ${whole_with_cut.sum() - all_real.sum():.2f}")
