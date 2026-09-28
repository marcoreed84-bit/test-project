"""Root-cause harness for the H&S Gold 2.2% bar-match finding.
Usage: python hs_gold_rootcause.py <case> [strict]
  case: bt1_defaults | bt1_v100 | bt4_defaults | bt3_defaults | silver_bt2
  strict: use EA-exact FindSwings window bounds (i in [start+N, k-N]) - no look-ahead.
"""
import sys, types, time
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np, pandas as pd, openpyxl, warnings
warnings.filterwarnings("ignore")
import engine as E

UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
DATA = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
REPORTS = dict(
    bt1="b745bb00-20260925_-_ReportTester-382043238_-_HS_-_Backtest_1.xlsx",
    bt3="60ae63d5-20260925_-_ReportTester-382043238_-_HS_-_Backtest_3.xlsx",
    bt4="d2ffdcc0-20260925_-_ReportTester-382043238_-_HS_-_Backtest_4.xlsx",
    silver_bt2="1d437603-20260927_-_ReportTester-382043238_-_HS_-_Backtest_2_-_Silver.xlsx",
)


def load_hs(strict):
    src = open("/home/user/test-project/research/trendbreaker/hs_sim.py").read()
    if strict:
        old = 'zIdx, zType, zPx = find_swings_window(cand_idx, isH, isL, h, l, atr, params["swing_min_atr"], win_start, k)'
        assert old in src
        src = src.replace(old, 'zIdx, zType, zPx = find_swings_window(cand_idx, isH, isL, h, l, atr, params["swing_min_atr"], win_start + N, k - N)')
    m = types.ModuleType("hs_sim_x")
    exec(compile(src, "hs_sim_x", "exec"), m.__dict__)
    return m


def load_real(path, sym):
    wb = openpyxl.load_workbook(path, data_only=True)
    rows = list(wb["Sheet1"].iter_rows(values_only=True))
    start = next(i for i, r in enumerate(rows) if r and r[0] == "Deals")
    header = [v for v in rows[start + 1] if v is not None]
    out = []
    for r in rows[start + 2:]:
        if not r or r[0] is None:
            continue
        d = dict(zip(header, r))
        if d.get("Symbol") == sym and d.get("Direction") == "in":
            out.append(dict(time=pd.Timestamp(d["Time"]), side=1 if d["Type"] == "buy" else -1, price=float(d["Price"])))
    return out


def match(real, sim_t, sim_d, lo, hi):
    rk = {r["time"].floor("15min"): r["side"] for r in real if lo <= r["time"] <= hi}
    sk = {pd.Timestamp(t).floor("15min"): d for t, d in zip(sim_t, sim_d) if lo <= pd.Timestamp(t) <= hi}
    both = set(rk) & set(sk)
    same = sum(rk[k] == sk[k] for k in both)
    st = np.array(sorted(sk), dtype="datetime64[ns]")
    near = {}
    for tol_h in (1, 4, 24):
        cnt = 0
        for k, s in rk.items():
            a = np.searchsorted(st, np.datetime64(k - pd.Timedelta(hours=tol_h)))
            b = np.searchsorted(st, np.datetime64(k + pd.Timedelta(hours=tol_h)), side="right")
            if any(sk[pd.Timestamp(x)] == s for x in st[a:b]):
                cnt += 1
        near[tol_h] = cnt
    return len(rk), len(sk), len(both), same, near


if __name__ == "__main__":
    case = sys.argv[1]
    strict = len(sys.argv) > 2 and sys.argv[2] == "strict"
    HS = load_hs(strict)
    if case == "silver_bt2":
        df = pd.read_csv(f"{DATA}/SILVER_M15_native.csv", skiprows=1)
        df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
        df = df.sort_values("time").reset_index(drop=True)
        point, sym, rep = 0.001, "SILVER", REPORTS["silver_bt2"]
        lo, hi = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-09-25")
    else:
        df = E.load_m15_native()
        point, sym = 0.01, "GOLD"
        rep = REPORTS[case.split("_")[0]]
        lo = {"bt1": "2023-01-01", "bt3": "2026-01-01", "bt4": "2020-01-01"}[case.split("_")[0]]
        lo, hi = pd.Timestamp(lo), pd.Timestamp("2026-09-25")
    params = dict(HS.DEFAULTS, point=point)
    if case == "bt1_v100":
        params.update(lookback_bars=3000, recompute_every_bars=1, break_tol_atr=0.10, stop_buffer_atr=0.3,
                      use_pullback_entry=False, use_runner=False)
    # cold start at the tester start date (MT5 OnInit), warm data before it available to CopyRates
    df = df[(df.time >= lo - pd.Timedelta(days=90)) & (df.time <= hi + pd.Timedelta(days=1))].reset_index(drop=True)
    k0 = int(np.searchsorted(df.time.values, np.datetime64(lo)))
    params["start_k"] = k0
    t0 = time.time()
    tr = HS.simulate(df[["time", "open", "high", "low", "close", "spread"]], params)
    sim_t = [df.time.values[t["entry_i"]] for t in tr]
    sim_d = [t["dir"] for t in tr]
    real = load_real(UP + rep, sym)
    nr, ns, nb, same, near = match(real, sim_t, sim_d, lo, hi)
    print(f"{case:<14} strict={strict!s:<5} real={nr:4d} sim={ns:4d} exact-bar={nb:4d} ({100*nb/nr:5.1f}% of real, "
          f"{100*nb/max(ns,1):5.1f}% of sim) same-dir={same}/{nb} | same-dir within 1h={near[1]} 4h={near[4]} 24h={near[24]} "
          f"({100*near[24]/nr:.0f}%)  [{time.time()-t0:.0f}s]")
