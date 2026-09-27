"""
Trade-by-trade validation of the Python H&S-on-Silver construction against
the user's REAL MT5 Strategy Tester run (HeadShoulders_EA.mq5, SILVER, M15,
2023.01.01-2026.09.25, v1.08 defaults, real fills). Same methodology as
every other real-vs-sim check in this project (see research/msg/
validate_all.py / v118_fresh_validate.py): parse the real Deals table into
round trips, restrict the Python construction to the exact same window,
match by entry minute.

Found and fixed a real bug getting here: RETEST_TOL had drifted to 0.50 in
hs_stacked_random_baseline_test.py, but HeadShoulders_EA.mq5's real,
current InpPullbackTolATR default is 0.75 - same stale-config class as the
Ratchet/Aurelius/MSG fixes. Corrected; see that file's own header.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
sys.path.insert(0, "/home/user/test-project/research/msg")
import numpy as np
import pandas as pd
from report import load_deals, round_trips, summary
from hs_next_round_test import find_breakouts_full, STOP_BUFFER
import hs_stacked_random_baseline_test as H

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
REPORT = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/1d437603-20260927_-_ReportTester-382043238_-_HS_-_Backtest_2_-_Silver.xlsx"
START, END = "2023-01-01", "2026-09-25 23:59:59"


def load_m15_silver():
    df = pd.read_csv(f"{DATA_DIR}/SILVER_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True)


def key(t):
    return t.replace(second=0, microsecond=0)


if __name__ == "__main__":
    real_all = round_trips(load_deals(REPORT))
    real = [t for t in real_all if pd.Timestamp(START) <= t["entry_time"] <= pd.Timestamp(END)]
    print(f"Real MT5 report: n={len(real)}  {real[0]['entry_time']} -> {real[-1]['entry_time']}")
    rs = summary([t["pnl_usd"] for t in real])
    print(f"  real (USD-move basis): {rs}")

    m15 = load_m15_silver()
    m15_win = m15[(m15["time"] >= START) & (m15["time"] <= END)].reset_index(drop=True)
    print(f"\nSILVER M15 bars in same window: n={len(m15_win)}")

    breakouts, h, l, c, atr = find_breakouts_full(m15_win, break_tol=0.35)
    n = len(c)
    sim_res, missed = H.eval_pullback_and_runner_pct(breakouts, h, l, c, STOP_BUFFER,
                                                       H.RETEST_TOL, H.RETEST_WINDOW, H.TRAIL_MULT)
    sim_pf = H.pct_pf(sim_res)
    sim_arr = np.array([r["pnl_pct"] for r in sim_res])
    print(f"\nSIM (frozen v1.08, corrected RETEST_TOL=0.75) on same window: "
          f"n={len(sim_res)} (missed {missed})  win%={100*(sim_arr>0).mean():.1f}  %PF={sim_pf:.3f}")

    rk = {key(t["entry_time"]): t for t in real}
    sim_times = {key(m15_win["time"].iloc[r["brk_q"]]): r for r in sim_res}
    both = set(rk) & set(sim_times)
    print(f"\nentry-minute match: {len(both)}/{len(real)} real trades ({100*len(both)/len(real):.0f}%), "
          f"{len(both)}/{len(sim_res)} sim trades ({100*len(both)/len(sim_res):.0f}%)")

    dir_match = sum(1 for t in both if (1 if rk[t]["side"] > 0 else -1) == (1 if not sim_times[t]["top"] else -1))
    print(f"direction agrees on {dir_match}/{len(both)} matched entries")
