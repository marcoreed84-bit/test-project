"""
Opus's web-review item #3: correlated systems on one instrument/account can
carry more combined risk than any one system's own report shows, since none
of them know the others exist. combine_all7_real.py already assembles real,
MT5-Deals-table-sourced round-trip trades for 7 systems (Aurelius M5/M15,
Vanguard M5/M15, Meridian, Ratchet, MSG) over a real, shared 2026-01-01
onward window - but its own docstring explicitly says "there is NO shared-
margin or shared-exposure modelling across the seven systems trading 'at
once'" (line ~617). This fills that specific, disclosed gap: it does not
touch or modify that file, just imports its already-validated real trade
lists and asks two real questions on top of them.

Q1 CONCURRENT DIRECTIONAL EXPOSURE: at any moment, how many of the 7 systems
are long/short GOLD at the same time? A sweep-line over each trade's own
[entry_time, exit_time) interval, real MT5 fill times.

Q2 DAILY P&L CORRELATION: resampling each system's real trades to daily P&L
(attributed to the trade's own exit day - when it actually realizes into
the account balance), then a pairwise correlation matrix - if the systems
are meaningfully correlated (not the "7 independent bets" an additive
combined-ledger implicitly assumes), the portfolio's real risk is higher
than summing 7 systems' own individual max drawdowns would suggest.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/portfolio")
import numpy as np
import pandas as pd
import combine_all7_real as C

all_systems, validations = C.build_portfolio()


def build_exposure_timeline(all_systems):
    events = []
    for name, trades in all_systems:
        for t in trades:
            events.append((t["entry_time"], 1, t["dir"], name))
            events.append((t["exit_time"], -1, t["dir"], name))
    events.sort(key=lambda e: e[0])

    long_count, short_count = 0, 0
    rows = []
    for time, delta, dirn, name in events:
        if dirn > 0:
            long_count += delta
        else:
            short_count += delta
        rows.append((time, long_count, short_count, long_count + short_count))
    return pd.DataFrame(rows, columns=["time", "n_long", "n_short", "n_total"])


def build_daily_pnl(all_systems):
    frames = {}
    for name, trades in all_systems:
        if not trades:
            continue
        df = pd.DataFrame(trades)
        df["day"] = pd.to_datetime(df["exit_time"]).dt.date
        daily = df.groupby("day")["pnl"].sum()
        frames[name] = daily
    return pd.DataFrame(frames).fillna(0.0)


if __name__ == "__main__":
    print("=" * 90)
    print("Q1: CONCURRENT DIRECTIONAL EXPOSURE (real MT5 fill times, 2026-01-01 onward)")
    print("=" * 90)
    exp = build_exposure_timeline(all_systems)
    print(f"Systems included: {[n for n, _ in all_systems]} (n trades: {[len(t) for _, t in all_systems]})")
    print(f"\nMax concurrent LONG positions:  {exp['n_long'].max()}")
    print(f"Max concurrent SHORT positions: {exp['n_short'].max()}")
    print(f"Max concurrent TOTAL positions: {exp['n_total'].max()}")

    # time-weighted distribution (how long each concurrency level actually persisted)
    exp = exp.sort_values("time").reset_index(drop=True)
    exp["dt_hours"] = (exp["time"].shift(-1) - exp["time"]).dt.total_seconds() / 3600.0
    exp = exp.iloc[:-1]
    total_hours = exp["dt_hours"].sum()
    print(f"\nTime-weighted distribution of concurrent LONG count:")
    for k in range(0, int(exp["n_long"].max()) + 1):
        pct = 100 * exp.loc[exp["n_long"] == k, "dt_hours"].sum() / total_hours
        print(f"  {k} systems long simultaneously: {pct:.1f}% of the time")
    print(f"\nTime-weighted distribution of concurrent SHORT count:")
    for k in range(0, int(exp["n_short"].max()) + 1):
        pct = 100 * exp.loc[exp["n_short"] == k, "dt_hours"].sum() / total_hours
        print(f"  {k} systems short simultaneously: {pct:.1f}% of the time")

    print("\n" + "=" * 90)
    print("Q2: DAILY P&L CORRELATION ACROSS SYSTEMS")
    print("=" * 90)
    daily = build_daily_pnl(all_systems)
    print(f"{len(daily)} trading days with at least one system active\n")
    corr = daily.corr()
    print(corr.round(2).to_string())

    # off-diagonal summary
    vals = corr.values
    n = vals.shape[0]
    offdiag = [vals[i, j] for i in range(n) for j in range(i + 1, n)]
    print(f"\nMean pairwise daily-P&L correlation: {np.mean(offdiag):.3f}  "
          f"(max={np.max(offdiag):.3f}, min={np.min(offdiag):.3f})")

    print("\n" + "=" * 90)
    print("WORST JOINT-LOSS DAYS (most systems net negative on the same real day)")
    print("=" * 90)
    n_losing = (daily < 0).sum(axis=1)
    combined_pnl = daily.sum(axis=1)
    worst = n_losing.sort_values(ascending=False).head(5)
    for day, cnt in worst.items():
        losers = [c for c in daily.columns if daily.loc[day, c] < 0]
        print(f"  {day}: {cnt} systems negative ({losers}), combined day P&L={combined_pnl[day]:.2f}")

    print("\nWorst single combined-P&L days (real joint drawdown days):")
    worst_pnl = combined_pnl.sort_values().head(5)
    for day, pnl in worst_pnl.items():
        losers = [c for c in daily.columns if daily.loc[day, c] < 0]
        print(f"  {day}: combined P&L={pnl:.2f}, systems negative: {losers}")
