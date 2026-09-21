"""
Correction to vanguard_aurelius_bias_test.py's approach, per direct
user feedback: that test required Aurelius's underlying TECHNICAL
condition (Aligned() - the 21>50>150>600+price/2400 alignment) to be
true, which is a continuously-computed condition regardless of whether
Aurelius is actually holding a position - it blocked Vanguard entries
even during long stretches where Aurelius itself wasn't trading at
all (flat), which is not what "overlapping trades" means and cut 80%
of Vanguard's trades for a real but modest quality gain.

What the user actually wants: use Aurelius's REAL, ACTUAL open
position (not its underlying technical bias) - if Aurelius is flat,
Vanguard trades completely normally (baseline +VWAP+S/R, unfiltered);
only intervene when Aurelius currently has a real trade open, and
specifically avoid entering AGAINST it if that trade is in the
opposite direction (the one bucket the real MT5 deals showed was a
net loser for Vanguard: -$1,112.59 across 48 trades, see
vanguard_aurelius_bias_test.py's header).

Ground truth: Aurelius_EA.mq5's REAL MT5 Strategy Tester deals
(56c08ddf-...-Aurelius_M5.xlsx, same account/symbol/period as
Vanguard's own real report) - not a Python re-simulation of Aurelius's
full entry/exit logic (stop/price21-exit/vwap-exit/alignment-break/
etc are numerous and easy to get subtly wrong; the real deals ARE
the ground truth, and are causally valid to use here since a trade
already opened by Aurelius at bar i is real information available at
that exact moment - nothing forward-looking about checking "is
Aurelius already in a position right now").

IMPORTANT: unlike the hindsight comparison, direction is checked
ONLY at the exact bar Vanguard's breakout fires (the entry decision
point), not "at any point during the whole subsequent hold" - the
only version that could actually gate a live trade.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import openpyxl
from datetime import datetime
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered
from meridian_dd_confluence_test import drawdown_stats

N_RANDOM_SEEDS = 300
FRACTAL_K = 100
SAFETY_SL = 4.0
MIN_SR = 0.50
AURELIUS_XLSX = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/56c08ddf-20260910_-_ReportTester-1301959345_-_Aurelius_M5.xlsx"


def load_aurelius_real_trades(path):
    """Real MT5 deals -> list of (open_time, close_time, direction) for
    closed round-trip trades. direction: +1 buy, -1 sell."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]
    start = None
    for r in range(1, ws.max_row + 1):
        if ws.cell(row=r, column=1).value == "Deals":
            start = r + 2
            break
    open_stack = []
    trades = []
    for r in range(start, ws.max_row + 1):
        time = ws.cell(row=r, column=1).value
        if time is None:
            continue
        dtype = ws.cell(row=r, column=4).value
        direction = ws.cell(row=r, column=5).value
        if dtype not in ("buy", "sell"):
            continue
        t = datetime.strptime(time, "%Y.%m.%d %H:%M:%S")
        if direction == "in":
            open_stack.append((t, 1 if dtype == "buy" else -1))
        elif direction == "out":
            if open_stack:
                ot, odir = open_stack.pop(0)
                trades.append((ot, t, odir))
    return trades


def aurelius_position_at(bar_times, aurelius_trades):
    """For each bar time, +1/-1/0 = Aurelius's real, already-open
    position direction at that exact moment (0 = flat). O(n*m) is fine
    here (n~256k bars, m~1100 trades) - a one-off research pass, not
    something that needs to be fast."""
    aurelius_trades = sorted(aurelius_trades, key=lambda t: t[0])
    n = len(bar_times)
    state = np.zeros(n, dtype=int)
    j = 0
    active = []  # trades currently open, as (close_time, dir)
    ti = 0
    for i in range(n):
        t = bar_times[i]
        while ti < len(aurelius_trades) and aurelius_trades[ti][0] <= t:
            ot, ct, d = aurelius_trades[ti]
            active.append((ct, d))
            ti += 1
        active = [(ct, d) for ct, d in active if ct > t]
        if active:
            # single-position EA in practice, but be defensive: most
            # recently opened still-active trade wins if somehow >1
            state[i] = active[-1][1]
    return state


def evaluate(label, events, entry_ok, close, high, low, spread, atr, n, run_control=False):
    print(f"\n--- {label} ---")
    trades, skipped = sim_trendline_filtered(events, entry_ok, close, high, low, spread, atr, n)
    if not trades:
        print("  0 trades"); return None
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
    print(f"  n={len(trades)} net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f}")
    if net > 0:
        print(f"  closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")
    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        if m.sum() == 0: continue
        if pnls[m].sum() > 0: pos += 1
    print(f"  walk-forward: {pos}/5 blocks positive")
    if run_control:
        rng = np.random.default_rng(0)
        random_nets = []
        for s in range(N_RANDOM_SEEDS):
            rdirs = rng.choice([1.0, -1.0], size=len(events))
            rev = [(i, d) for (i, _), d in zip(events, rdirs)]
            rev.sort(key=lambda e: e[0])
            trades_r, _ = sim_trendline_filtered(rev, entry_ok, close, high, low, spread, atr, n)
            random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
        random_nets = np.array(random_nets)
        pct = 100 * (random_nets < net).mean()
        print(f"  random-direction percentile={pct:.1f} (null mean={random_nets.mean():.2f})")
    return dict(label=label, n=len(trades), net=net, pf=pf)


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    bar_times = pd.to_datetime(df5["time"].values).to_pydatetime()

    aurelius_trades = load_aurelius_real_trades(AURELIUS_XLSX)
    print(f"loaded {len(aurelius_trades)} real Aurelius trades from its own MT5 backtest\n")
    aur_state = aurelius_position_at(bar_times, aurelius_trades)
    print(f"Aurelius flat {100*np.mean(aur_state==0):.1f}% of bars, "
          f"long {100*np.mean(aur_state>0):.1f}%, short {100*np.mean(aur_state<0):.1f}%\n")

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)

    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < MIN_SR)
    vwap_sr_ok = vwap_ok & sr_ok

    print("=" * 70)
    evaluate("VALIDATED BASELINE (+VWAP+S/R, already shipped in v1.01/v1.02)",
              events, vwap_sr_ok, close, high, low, spread, atr, n, run_control=True)

    # the actual rule requested: only BLOCK when Aurelius is open AGAINST
    # this direction at the exact entry bar; flat or same-direction -> allow
    no_conflict_ok = np.ones(n, dtype=bool)
    for i, d in events:
        a = aur_state[i]
        no_conflict_ok[i] = not (a != 0 and a != d)
    combo_ok = vwap_sr_ok & no_conflict_ok
    evaluate("+VWAP+S/R, skip only if Aurelius open AGAINST us at entry",
              events, combo_ok, close, high, low, spread, atr, n, run_control=True)

    n_blocked = sum(1 for i, d in events if vwap_sr_ok[i] and not no_conflict_ok[i])
    print(f"\n(of the {int(vwap_sr_ok.sum())} baseline-eligible breakout bars, "
          f"{n_blocked} were blocked by a real opposing Aurelius position)")
