"""
NEW CANDIDATE (2026-10-06, user's own idea, from a chart screenshot): a
standalone 21/50 EMA + session VWAP pullback-reclaim construction. Python
research only so far - this is a hypothesis to test, not a built/shipped
.mq5 EA. Nothing here is live or real-MT5-confirmed.

CONSTRUCTION (my best-faith read of the user's description - check this
against what you meant before trusting the numbers):

1. PRIOR SEPARATION ("a nice running distance before they cross"): find
   every 21/50 EMA cross event (21 EMA crossing 50 EMA, either direction).
   Require that at some point in the SEP_LOOKBACK bars before the cross,
   the two EMAs were separated by at least SEP_MIN_ATR x ATR (the MAXIMUM
   separation in that window, not the minimum - by definition the two
   EMAs must converge toward each other right at the cross itself, so
   requiring the separation held all the way up to the cross bar would be
   self-contradictory and reject every single crossover. This instead
   asks: was there a real established trend recently, before the
   convergence began - not two EMAs that were already flat/overlapping.

2. DIRECTION: a bearish cross (21 EMA crosses below 50 EMA, i.e. was
   trending above it) sets up a LONG (buy-the-dip, matching the
   screenshot: correction down, then reclaim, then continuation up).
   A bullish cross mirrors it into a SHORT setup. Both directions tested,
   not just the long side shown in the one screenshot.

3. PULLBACK TO VWAP, THEN RECLAIM: scanning forward from the cross bar,
   within PULLBACK_MAX_BARS bars: for the LONG setup, first find a bar
   where the 21 EMA actually dips below session VWAP (confirms the
   pullback reached VWAP, not just approached it) - then find the next
   bar after that where the 21 EMA crosses back above VWAP. THAT crossing
   bar is the signal; entry fills at the following bar's open, real
   spread charged. Mirror for SHORT (21 EMA rises above VWAP, then
   crosses back below it). If no reclaim happens within the window, no
   trade - the cross is simply skipped, not retried.

4. EXTENSION FILTER (2026-10-06 fix, real bug the user caught by asking
   why trades were stopping out in 10-15 minutes): the trigger above is
   defined purely on the EMA21 LINE crossing VWAP - both smoothed,
   lagging series. Checking real examples directly showed raw PRICE is
   often already 2+ ATR away from the EMAs by the time that lagging cross
   confirms - i.e. the fill was chasing an already-extended move, not
   entering near the reclaim, which is exactly when a quick pullback/
   stop-out is likely. Fixed by rejecting any fill more than
   EXTENSION_MAX_ATR x ATR away from the nearer of the two EMAs at the
   fill bar. This cuts the raw signal count hard (805 -> 216 executed
   trades) - most of the original "signals" were exactly this chasing
   problem, not a small edge case.

SESSION VWAP: identical definition to research/meridian/msim.py's
build_ctx() - cumulative (typical price x tick volume) / cumulative tick
volume, reset at each new calendar day. Not a new VWAP definition.

STOP LOSS (2026-10-06 correction, user's own instruction - the first cut
of this test used an ATR distance from entry and was wrong): the stop is
STRUCTURAL, not ATR-from-entry - it sits SL_BUFFER_ATR x ATR beyond
whichever of the 21/50 EMA is closer to price at the fill bar (below the
lower one for a long, above the higher one for a short). The moving
averages themselves are what this setup trades off of, so the stop
belongs there, not at an arbitrary ATR multiple from the entry price. A
fill where price is already past its own would-be stop (entry beyond the
MA) is skipped as degenerate, not force-placed with a negative-risk stop.

EXIT - five separate, independently-tested options, each run against the
SAME entries and the SAME structural stop above (own K for the entry
construction is 1; comparing 5 exit options against it is an honest K=5
comparison, Sidak-corrected below - not reported as 5 independent
single-shot results):
  TRAIL:     once floating profit reaches TRAIL_TRIGGER_ATR x entry ATR,
             the stop trails behind the peak favorable price by
             TRAIL_GIVEBACK_ATR x entry ATR (only ever tightens, starting
             from the structural stop above). No fixed target - rides
             until trailed out or the time-stop.
  FIXED_PTS: structural stop unchanged throughout, fixed target FIXED_TP
             price units away - a single pre-specified distance, not
             swept.
  EMA_RECROSS: structural stop as a hard backstop only; the live exit is
             the trend structure itself reversing - the 21/50 EMAs
             crossing back against the trade direction (the same
             mechanism that triggered entry, mirrored). A normal retest
             that merely touches or closes slightly past one MA is NOT an
             exit by itself - only an actual EMA21/50 re-cross is. No
             fixed target.
  ATR_STOP:  plain bracket - structural stop, target ATR_STOP_RR x that
             trade's own structural stop DISTANCE (so the target still
             scales with how far price was from the MAs at entry, not a
             fixed ATR multiple).
  MA600_TARGET (2026-10-06, user's own idea from a second, cleaner chart
             example): structural stop as above; target is the 600 EMA
             itself - Aurelius's own next slower moving average above
             (long) / below (short) price, which the user's example
             showed price reacting to/rejecting. Exit fills AT the 600
             EMA's own price the moment it's reached (h[t]>=ema600[t] for
             a long, mirrored for a short) - a dynamic, price-level
             target, not a fixed distance.
All five share MAX_BARS as a final time-stop backstop, real spread on
entry, one trade at a time, and stop-takes-priority-over-target on a
same-bar double-touch (this project's standing convention).

Honest K for this whole test: K=5 (one entry construction, five exit
variants compared against it). Sidak-corrected significance bar for
"best of 5" = 1-(1-0.05)**(1/5) ~= 0.0102, not the usual 0.05 - stated
again next to each result below.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B  # noqa: E402

POINT = B.POINT

SEP_LOOKBACK = 20
SEP_MIN_ATR = 0.50
PULLBACK_MAX_BARS = 24
SL_BUFFER_ATR = 0.15   # small buffer beyond the MA itself, so the stop isn't a dead-exact touch
EXTENSION_MAX_ATR = 1.0   # max allowed price-to-MA distance at fill - reject chasing an already-extended move
MAX_BARS = 288

TRAIL_TRIGGER_ATR = 1.0
TRAIL_GIVEBACK_ATR = 1.5
FIXED_TP = 15.0
ATR_STOP_RR = 2.0

EXIT_MODES = ["TRAIL", "FIXED_PTS", "EMA_RECROSS", "ATR_STOP", "MA600_TARGET"]
SIDAK_K = len(EXIT_MODES)
SIDAK_ALPHA = 1.0 - (1.0 - 0.05) ** (1.0 / SIDAK_K)


def build_vwap(df):
    date = df["time"].dt.date.values
    typ = (df["high"].values + df["low"].values + df["close"].values) / 3.0
    v = df["tick_volume"].values.astype(float)
    vwap = (pd.Series(typ * v).groupby(date).cumsum() / pd.Series(v).groupby(date).cumsum()).values
    return vwap


def find_entries(ema21, ema50, vwap, atr, n):
    sign = np.sign(ema21 - ema50)
    entries = []
    for t in range(SEP_LOOKBACK + 1, n - PULLBACK_MAX_BARS - 2):
        if sign[t] == 0 or sign[t - 1] == 0 or sign[t] == sign[t - 1]:
            continue
        lo, hi = t - SEP_LOOKBACK, t - 1
        win_atr = atr[lo:hi + 1]
        if np.any(np.isnan(win_atr)) or np.any(win_atr <= 0):
            continue
        sep_atr = np.abs(ema21[lo:hi + 1] - ema50[lo:hi + 1]) / win_atr
        if sep_atr.max() < SEP_MIN_ATR:
            continue
        a = atr[t]
        if not (a > 0):
            continue
        d = -1 if sign[t] > 0 else 1   # bullish cross(sign>0)->SHORT setup(-1); bearish cross->LONG setup(+1)
        dipped = False
        signal_i = None
        for i in range(t + 1, min(t + 1 + PULLBACK_MAX_BARS, n - 1)):
            if not dipped:
                if (d > 0 and ema21[i] < vwap[i]) or (d < 0 and ema21[i] > vwap[i]):
                    dipped = True
                continue
            back_above = ema21[i - 1] <= vwap[i - 1] and ema21[i] > vwap[i]
            back_below = ema21[i - 1] >= vwap[i - 1] and ema21[i] < vwap[i]
            if (d > 0 and back_above) or (d < 0 and back_below):
                signal_i = i
                break
        if signal_i is not None:
            entries.append(dict(signal_i=signal_i, dir=d, atr=atr[signal_i]))
    return entries


def simulate(o, h, l, c, sp_pts, ema21, ema50, ema600, entries_by_bar, start_i, end_i, exit_mode):
    trades = []
    pos = None
    for t in range(start_i, end_i):
        sp = sp_pts[t] * POINT
        if pos is not None:
            d, a = pos["dir"], pos["atr"]
            if exit_mode == "TRAIL":
                if d > 0:
                    if h[t] > pos["peak_px"]:
                        pos["peak_px"] = h[t]
                    prof = pos["peak_px"] - pos["entry"]
                    if prof >= TRAIL_TRIGGER_ATR * a:
                        trail_sl = pos["peak_px"] - TRAIL_GIVEBACK_ATR * a
                        if trail_sl > pos["sl"]:
                            pos["sl"] = trail_sl
                else:
                    if l[t] < pos["peak_px"]:
                        pos["peak_px"] = l[t]
                    prof = pos["entry"] - pos["peak_px"]
                    if prof >= TRAIL_TRIGGER_ATR * a:
                        trail_sl = pos["peak_px"] + TRAIL_GIVEBACK_ATR * a
                        if trail_sl < pos["sl"]:
                            pos["sl"] = trail_sl
            hit_sl = (l[t] <= pos["sl"]) if d > 0 else (h[t] + sp >= pos["sl"])
            hit_tp = pos["tp"] is not None and ((h[t] >= pos["tp"]) if d > 0 else (l[t] <= pos["tp"]))
            ema_recross = False
            if exit_mode == "EMA_RECROSS":
                # 2026-10-06 fix (user correction): a normal retest that
                # TOUCHES or closes slightly past one MA is not a reversal -
                # only exit when the 21/50 EMAs actually cross back against
                # the trade (the same mechanism that triggered entry,
                # mirrored). A bounce off either MA keeps the trade open.
                ema_recross = (ema21[t] < ema50[t]) if d > 0 else (ema21[t] > ema50[t])
            ma600_hit = False
            if exit_mode == "MA600_TARGET":
                ma600_hit = (h[t] >= ema600[t]) if d > 0 else (l[t] <= ema600[t])
            timed_out = (t - pos["entry_i"]) >= MAX_BARS
            if hit_sl:
                px, reason = pos["sl"], "SL"
            elif hit_tp:
                px, reason = pos["tp"], "TP"
            elif ema_recross:
                px, reason = c[t], "EMA_RECROSS"
            elif ma600_hit:
                px, reason = ema600[t], "MA600_TARGET"
            elif timed_out:
                px, reason = c[t], "TIMEOUT"
            else:
                continue
            trades.append(dict(entry_i=pos["entry_i"], dir=d, pnl=(px - pos["entry"]) * d, reason=reason,
                                atr=pos["atr"]))
            pos = None
        if pos is None and t in entries_by_bar and start_i <= t < end_i:
            d, a = entries_by_bar[t]
            entry = o[t] + sp if d > 0 else o[t]
            # structural stop: below (long) / above (short) the 21/50 EMAs
            # themselves at the fill bar, not an ATR distance from entry -
            # the MAs ARE the support/resistance this setup trades off of.
            sl = (min(ema21[t], ema50[t]) - SL_BUFFER_ATR * a) if d > 0 else \
                 (max(ema21[t], ema50[t]) + SL_BUFFER_ATR * a)
            if (d > 0 and sl >= entry) or (d < 0 and sl <= entry):
                continue   # degenerate: price already past its own stop at fill - skip
            # 2026-10-06 fix (user-identified bug): the entry trigger only
            # checks the EMA21/VWAP cross - a LAGGING, smoothed condition -
            # with no check on where raw PRICE actually is. By the time the
            # smoothed cross confirms, price can already have run well past
            # the MAs (seen directly in real examples: entries 2+ ATR away
            # from both EMAs at fill), i.e. chasing an already-extended move
            # right before its own pullback, not entering near the reclaim.
            # Reject any fill too far from the MAs to still be "at the
            # retest zone" the construction is supposed to be trading.
            near_ma = min(ema21[t], ema50[t]) if d > 0 else max(ema21[t], ema50[t])
            if abs(entry - near_ma) > EXTENSION_MAX_ATR * a:
                continue
            risk = abs(entry - sl)
            if exit_mode == "ATR_STOP":
                tp = entry + d * ATR_STOP_RR * risk
            elif exit_mode == "FIXED_PTS":
                tp = entry + d * FIXED_TP
            else:
                tp = None
            pos = dict(entry_i=t, dir=d, entry=entry, sl=sl, tp=tp, atr=a, peak_px=entry)
    return trades


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"    {label}: n=0")
        return
    pnl = np.array([t["pnl"] for t in trades])
    print(f"    {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  avg={pnl.mean():7.3f}")
    for r in ("TP", "SL", "EMA_RECROSS", "MA600_TARGET", "TIMEOUT"):
        cnt = sum(1 for t in trades if t["reason"] == r)
        if cnt:
            print(f"        {r}: {cnt} ({100*cnt/n:.1f}%)")


def random_entries_matched(dir_atr_list, start_i, end_i, seed):
    rng = np.random.default_rng(seed)
    eligible = rng.choice(np.arange(start_i + 1, end_i), size=len(dir_atr_list), replace=False)
    order = rng.permutation(len(dir_atr_list))
    out = {}
    for bar, idx in zip(eligible, order):
        out[int(bar)] = dir_atr_list[idx]
    return out


if __name__ == "__main__":
    m5 = B.load_m5()
    o, h, l, c = (m5[k].values for k in ("open", "high", "low", "close"))
    sp_pts = m5["spread"].values
    atr = B.wilder_atr(h, l, c, 14)
    ema21 = B.ema(c, 21)
    ema50 = B.ema(c, 50)
    ema600 = B.ema(c, 600)
    vwap = build_vwap(m5)
    n = len(m5)
    cutoff = int(n * 0.70)
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({n} bars)")
    print(f"Walk-forward cutoff (70%): {m5['time'].iloc[cutoff]}")
    print(f"Entry: 21/50 EMA cross (min {SEP_MIN_ATR}xATR separation held for {SEP_LOOKBACK} bars before "
          f"the cross), then dip-to-VWAP + reclaim within {PULLBACK_MAX_BARS} bars.")
    print(f"Honest K={SIDAK_K} ({SIDAK_K} exit variants vs the same entry) -> "
          f"Sidak-corrected significance bar p<{SIDAK_ALPHA:.4f}, not p<0.05.\n")

    entries = find_entries(ema21, ema50, vwap, atr, n)
    print(f"total triggered entries across full history: {len(entries)}\n")
    entries_by_bar_all = {e["signal_i"] + 1: (e["dir"], e["atr"]) for e in entries}
    is_eb = {k: v for k, v in entries_by_bar_all.items() if k < cutoff}
    oos_eb = {k: v for k, v in entries_by_bar_all.items() if k >= cutoff}

    for mode in EXIT_MODES:
        print(f"{'='*92}\nEXIT MODE: {mode}\n{'='*92}")
        is_trades = simulate(o, h, l, c, sp_pts, ema21, ema50, ema600, is_eb, 60, cutoff, mode)
        print("  IN-SAMPLE (first 70%) - transparency only")
        report(mode, is_trades)

        oos_trades = simulate(o, h, l, c, sp_pts, ema21, ema50, ema600, oos_eb, cutoff, n, mode)
        print("  OUT-OF-SAMPLE (last 30%, untouched) - this is the verdict")
        report(mode, oos_trades)
        n_oos = len(oos_trades)

        if n_oos < 5:
            print(f"    only {n_oos} OOS trades - too few for a meaningful null\n")
            continue

        real_pf = pf([t["pnl"] for t in oos_trades])
        # matched to the trades actually EXECUTED (n_oos), not the raw signal
        # count in oos_eb - some signals get skipped by the one-trade-at-a-
        # time rule, same convention as every other null test this session.
        oos_dl = [(t["dir"], t["atr"]) for t in oos_trades]
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            rb = random_entries_matched(oos_dl, cutoff, n, seed)
            ntrades = simulate(o, h, l, c, sp_pts, ema21, ema50, ema600, rb, cutoff, n, mode)
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"    RANDOM-TIMING NULL (OOS only, {NDRAWS} draws, same dir/ATR distribution, random bars):")
        print(f"    real PF={real_pf:.3f}  null median={np.median(null_pfs):.3f}  "
              f"p05={np.percentile(null_pfs,5):.3f}  p95={np.percentile(null_pfs,95):.3f}")
        print(f"    real PF sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        verdict = "SURVIVES" if p_value < SIDAK_ALPHA else "does not survive"
        print(f"    p-value = {p_value:.4f}  [{verdict} the Sidak-corrected bar p<{SIDAK_ALPHA:.4f}]\n")
