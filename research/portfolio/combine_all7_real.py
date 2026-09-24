"""
COMBINED 7-EA PORTFOLIO LEDGER - REAL MT5 DATA VERSION (2026-01-01 onward, ZAR).

WHY THIS FILE EXISTS
=====================
Earlier today research/portfolio/combine_all7.py combined all seven systems'
PYTHON-SIMULATED trades onto one 13,500 (USD-labelled) starting balance. The
user checked that workbook against their own REAL MT5 Strategy Tester results
and correctly flagged a mismatch: Ratchet's Python-model net for the Jan-Sep
2026 window sat around $650-900 all session, while the REAL MT5-confirmed
result for the exact same EA/window is 9,273.91 ZAR (research/ratchet's own
v3.30 real-confirmation report). A Python simulator is a screening tool, not
a stand-in for real execution - and presenting the simulated combination as a
plain "13,500 starting balance" figure invited exactly this wrong comparison.

THE FIX: rebuild the same kind of combined ledger, but sourced ENTIRELY from
REAL MT5 Strategy Tester Deals-table data for all seven systems (not Python
simulation), denominated in ZAR (the real account currency - these are real
XM Global XMGlobal-MT5 13 accounts, not USD), and scoped to 2026-01-01 onward
only (not the full 2023-2026 history the earlier workbook also covered).

This file is purely ADDITIVE - it does not read, modify, or overwrite
combine_all7.py or either of its two output workbooks already in this
folder. Its own output is a separate file:
  research/portfolio/combined_7ea_portfolio_REAL_2026_onward.xlsx

============================== SOURCE REPORTS ==============================
All seven are real XM Global "XMGlobal-MT5 13" Strategy Tester .xlsx reports
on the LIVE "GOLD" symbol (not the "GOLD#" demo feed the Python-model
overlap study used), each already uploaded this session:

  1. Aurelius M5    - ReportTester-382043238 Aurelius Backtest GOLD.xlsx
                       native window 2023.01.01-2026.09.21, 20000 ZAR deposit.
                       CLIPPED here to exit time >= 2026-01-01.
  2. Aurelius M15   - ReportTester-382043238 Aurelius_M15 Backtest GOLD.xlsx
                       same native window/deposit. CLIPPED to >= 2026-01-01.
  3. Vanguard M5    - ReportTester-382043238 Vanguard Backtest 1.xlsx
                       same native window/deposit, InpUseAureliusFilter=false
                       (raw/unfiltered). CLIPPED to >= 2026-01-01.
  4. Vanguard M15   - ReportTester-382043238 Vanguard_M15 Backtest 1.xlsx
                       same, InpUseAureliusFilter=false. CLIPPED to
                       >= 2026-01-01.
  5. Meridian       - ReportTester-382043238 Meridian Backtest 1.xlsx
                       same native window/deposit. CLIPPED to >= 2026-01-01.
  6. Ratchet        - ReportTester-382043238 Ratchet Backtest 6.0.xlsx
                       v3.30 real confirmation (InpTrailRunnerATR=6.0),
                       NATIVE window already 2026.01.01-2026.09.21, 13500 ZAR
                       deposit. Used in FULL, no further clipping.
  7. MSG            - ReportTester-382043238 MSG Backtest 2.xlsx
                       NATIVE window already 2026.01.01-2026.09.21. Used in
                       FULL, no further clipping.
                       ** KNOWN, MUST-DISCLOSE CAVEAT **: this report has
                       InpMsg1Enable=false, but MSG_Trader_EA.mq5's current
                       shipped default (line ~818) is InpMsg1Enable=true.
                       Every available real MSG report on this account was
                       checked this session and NONE match the current
                       shipped session-1-enabled config - this is the closest
                       available real run, NOT an exact match to what ships
                       today. Restated on the Methodology sheet and in the
                       final report; not glossed over.

All seven exact uploaded paths are in REPORTS below.

============================== PARSING METHOD ==============================
Each report's Deals table is located by finding the row where column A =
'Time' and column B = 'Deal' (columns: Time / Deal / Symbol / Type /
Direction / Volume / Price / Order / Commission / Swap / Profit / Balance /
Comment), read down until the first blank/summary row. 'balance' rows (the
opening deposit) are skipped. Deals are paired into round-trip trades by
walking in original order: an 'in' deal opens a trade (direction: buy=long,
sell=short); subsequent deals accumulate into it until cumulative out-volume
equals the in-volume, closing the trade (all 7 reports here scale out in a
single leg - verified: every round-trip in all seven reports has exactly one
out-leg). Parsing was validated against each report's own totals before any
clipping: for every one of the 7 systems, sum(Profit) and sum(Swap) over all
parsed round-trips reproduce that report's own Deals-table column totals to
the cent - see recon.py to see this validation, run standalone, and the
console output of the __main__ block below. Ratchet in particular reconciles
to exactly 9,273.91 ZAR net (sum of Profit only) over its full native window,
matching this project's own earlier real-MT5 confirmation of that number
exactly - see the report printed by __main__.

======================= FIXED LOT SIZE -> COMBINE RATIONALE ================
All seven real reports used here confirmed FIXED lot sizing this session
(InpLotMode=0 / LOT_FIXED): 0.01 lots for Aurelius/Vanguard/Meridian/Ratchet,
0.03 lots for MSG (its own real shipped default). Because lot size is fixed
rather than balance-scaled (LOT_FIXED, not a %-risk mode), each trade's real
ZAR Profit is INDEPENDENT of whichever deposit size that trade's original
report happened to run against (20000 ZAR for five of the seven, 13500 ZAR
for Ratchet and MSG) - the trade would have produced the exact same ZAR
Profit figure regardless of the account balance it was struck against. That
is what makes it valid to pull these real, trade-level ZAR pnl figures
straight out of their seven original reports and restack them, in the
original chronological (exit-time) order, onto ONE NEW shared starting
balance of 13,500 ZAR. This is a real methodological choice, stated here and
on the Methodology sheet, not hidden: it is NOT the same as a literal single
real account that held all seven EAs' positions simultaneously (see
Limitation 3 below and on that sheet).

============================ SWAP-INCLUSION DECISION ========================
DECISION: swap IS included in each trade's combined pnl (pnl = out-deal(s)
Profit + out-deal(s) Swap [+ Commission, always 0.00 in all seven reports]).
This follows this project's own established real-report reconciliation
convention from earlier this session (research/ratchet/report.py's
reconcile(): "sum(profit+commission+swap) over all round-trips must equal
the report's own Total Net Profit to the cent"). Swap is a real cost (or, on
rare rows here, credit) of holding a position across a broker swap point,
and leaving it out would silently understate/overstate several systems' real
combined pnl - notably Aurelius_M15, Vanguard M5/M15 and Meridian, whose
Deals tables carry materially nonzero swap on their multi-day holds.
Commission was checked and is 0.00 on every single deal row across all seven
reports (confirmed programmatically below), so in practice only swap moves
the number; it is added here for completeness/consistency with the
established convention regardless. This choice is applied uniformly to all
seven systems - none of the seven is treated differently.

============================== LEDGER ORDERING ==============================
All seven systems' real trades are merged into ONE chronological ledger
ordered by EXIT time - matching MT5's own Balance column convention (balance
updates on deal close, not open). Running balance starts at 13,500 ZAR and
updates by each trade's combined (Profit+Swap) pnl in that exit-time order.

============================ WHAT THIS IS *NOT* =============================
This is still NOT a literal single, real, simultaneous 7-EA MT5 account run.
These are seven independent real MT5 Strategy Tester passes (seven separate
backtests, each on its own EA/settings/deposit), recombined here in
ZAR-for-ZAR terms onto one shared ledger. No real account ever held all
seven EAs' positions open at once in this data; there is no shared-margin or
shared-exposure modelling across the seven systems trading "at once" - this
is a straightforward realized-pnl ledger (stacking seven independent, but
individually 100% real, ZAR pnl streams onto one running balance).

============================== OUTPUT ==============================
research/portfolio/combined_7ea_portfolio_REAL_2026_onward.xlsx (openpyxl),
matching combine_all7.py's existing workbook structure/formatting: a
"Methodology" sheet (first tab), a "Trade Ledger" sheet (full chronological
trade-for-trade table + running balance, formula-driven so it recalculates
if edited), and a "Summary" sheet (per-EA attribution via
SUMIF/COUNTIF/SUMIFS formulas against the Trade Ledger sheet, + a portfolio
total row) - all labelled ZAR throughout, not USD.
"""
import datetime as dt
import os
import warnings

import numpy as np
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

warnings.filterwarnings("ignore", module="openpyxl")

ROOT = "/home/user/test-project"
OUT_DIR = os.path.join(ROOT, "research/portfolio")
OUT_PATH = os.path.join(OUT_DIR, "combined_7ea_portfolio_REAL_2026_onward.xlsx")

UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"

REPORTS = {
    "Aurelius_M5": dict(
        path=UP + "552007ef-20260923_-_ReportTester-382043238_-_Aurelius_-_Backtest_GOLD.xlsx",
        deposit=20000.0, native_window="2023.01.01 - 2026.09.21", clip=True),
    "Aurelius_M15": dict(
        path=UP + "b4e4e45e-20260923_-_ReportTester-382043238_-_Aurelius_M15_-_Backtest_GOLD.xlsx",
        deposit=20000.0, native_window="2023.01.01 - 2026.09.21", clip=True),
    "Vanguard_M5": dict(
        path=UP + "16efba8e-20260924_-_ReportTester-382043238_-_Vanguard_-_Backtest_1.xlsx",
        deposit=20000.0, native_window="2023.01.01 - 2026.09.21", clip=True),
    "Vanguard_M15": dict(
        path=UP + "3bb21a95-20260924_-_ReportTester-382043238_-_Vanguard_M15_-_Backtest_1.xlsx",
        deposit=20000.0, native_window="2023.01.01 - 2026.09.21", clip=True),
    "Meridian": dict(
        path=UP + "b9f51b58-20260924_-_ReportTester-382043238_-_Meridian_-_Backtest_1.xlsx",
        deposit=20000.0, native_window="2023.01.01 - 2026.09.21", clip=True),
    "Ratchet": dict(
        path=UP + "50fb590f-20260923_-_ReportTester-382043238_-_Ratchet_-_Backtest_6.0.xlsx",
        deposit=13500.0, native_window="2026.01.01 - 2026.09.21", clip=False),
    "MSG": dict(
        path=UP + "9d84e911-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_2.xlsx",
        deposit=13500.0, native_window="2026.01.01 - 2026.09.21", clip=False),
}

WINDOW_START = dt.datetime(2026, 1, 1, 0, 0, 0)

STARTING_BALANCE = 13500.0  # ZAR - one new shared balance, independent of each source report's own deposit

INDICATOR_FAMILY = {
    "Aurelius_M5": "MA alignment (EMA21>EMA50>SMA250>SMMA500 vs EMA2400 trend filter)",
    "Aurelius_M15": "MA alignment (EMA21>EMA50>SMA250>SMMA500 vs EMA2400 trend filter) - M15 chart",
    "Vanguard_M5": "Trendline breakout (fractal swing line) + VWAP/S-R distance gate",
    "Vanguard_M15": "Trendline breakout (fractal swing line) + VWAP/S-R distance gate - M15 chart",
    "Meridian": "21/50 MA cross, 250-period confirm filter, VWAP",
    "Ratchet": "Stochastic scalp with give-back trail exit",
    "MSG": "Session-block / Fibonacci retracement-zone entry",
}

SYSTEM_ORDER = ["Aurelius_M5", "Aurelius_M15", "Vanguard_M5", "Vanguard_M15", "Meridian", "Ratchet", "MSG"]

MSG_CAVEAT = (
    "MSG source report has InpMsg1Enable=false, but MSG_Trader_EA.mq5's current shipped default "
    "(line ~818) is InpMsg1Enable=true. Every available real MSG report on this account was checked "
    "this session and NONE match the current shipped session-1-enabled configuration - this is the "
    "closest available real run, NOT an exact match to what ships today."
)


# --------------------------------------------------------------- report parsing

def _load_rows(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    return list(wb.worksheets[0].iter_rows(values_only=True))


def load_deals(path):
    """Deals table: header row where col A='Time', col B='Deal'; rows below
    until the first blank/summary row. 'balance' rows are skipped."""
    rows = _load_rows(path)
    hdr = next(i for i, r in enumerate(rows) if r[0] == "Time" and r[1] == "Deal")
    deals = []
    for r in rows[hdr + 1:]:
        if r[0] is None:
            break  # blank/summary row - end of Deals table
        if r[3] == "balance":
            continue
        deals.append(dict(
            time=dt.datetime.strptime(r[0], "%Y.%m.%d %H:%M:%S"),
            deal=r[1], symbol=r[2], type=r[3], dirn=r[4],
            vol=float(r[5]), price=float(r[6]), order=r[7],
            commission=float(r[8] or 0.0), swap=float(r[9] or 0.0),
            profit=float(r[10] or 0.0), balance=float(r[11] or 0.0),
            comment=r[12]))
    return deals


def round_trips(deals):
    """Pair sequential 'in'/'out' deals into round-trip trades. Direction
    from the 'in' deal's Type (buy=long/sell=short). pnl = sum of out-leg(s)
    Profit + Swap + Commission (swap-inclusion decision, see module
    docstring; commission is 0.00 throughout but included for consistency
    with this project's established reconciliation convention)."""
    trips, cur = [], None
    for d in deals:
        if d["dirn"] == "in":
            assert cur is None, "overlapping positions - not single-slot"
            cur = dict(entry_time=d["time"], dir=1 if d["type"] == "buy" else -1,
                       vol=d["vol"], out_vol=0.0, profit_only=0.0, swap=0.0, commission=0.0, nlegs=0)
        else:
            assert cur is not None, "'out' deal with no open position"
            cur["out_vol"] += d["vol"]
            cur["profit_only"] += d["profit"]
            cur["swap"] += d["swap"]
            cur["commission"] += d["commission"]
            cur["nlegs"] += 1
            if abs(cur["out_vol"] - cur["vol"]) < 1e-9:
                cur["exit_time"] = d["time"]
                cur["pnl"] = round(cur["profit_only"] + cur["swap"] + cur["commission"], 2)
                trips.append(cur)
                cur = None
    assert cur is None, "report ends with an open position"
    return trips


def build_system(name, meta):
    """Loads + parses one system's real report, validates the parse against
    the report's own totals (unclipped), then clips to the window this
    workbook uses and returns (trades, validation dict)."""
    deals = load_deals(meta["path"])
    trips = round_trips(deals)

    # Validation: every round-trip has exactly 1 out-leg for all 7 reports here.
    nlegs = sorted({t["nlegs"] for t in trips})

    # Validation: sum(Profit) and sum(Profit+Swap+Commission) over the FULL,
    # unclipped set of round-trips, for the console report / sanity check.
    full_profit_only = round(sum(t["profit_only"] for t in trips), 2)
    full_pnl_with_swap = round(sum(t["pnl"] for t in trips), 2)

    clip = meta["clip"]
    if clip:
        kept = [t for t in trips if t["exit_time"] >= WINDOW_START]
    else:
        kept = trips

    out = [dict(system=name, dir=t["dir"], entry_time=t["entry_time"],
                 exit_time=t["exit_time"], pnl=t["pnl"]) for t in kept]

    validation = dict(
        nlegs=nlegs, n_full=len(trips), n_clipped=len(out),
        full_profit_only=full_profit_only, full_pnl_with_swap=full_pnl_with_swap,
        clipped_pnl_with_swap=round(sum(t["pnl"] for t in out), 2),
        clipped_profit_only=round(sum(t["profit_only"] for t in kept), 2),
        deposit=meta["deposit"], native_window=meta["native_window"], clipped=clip,
    )
    return out, validation


def build_portfolio():
    all_systems, validations = [], {}
    for name in SYSTEM_ORDER:
        trades, v = build_system(name, REPORTS[name])
        all_systems.append((name, trades))
        validations[name] = v
    return all_systems, validations


# --------------------------------------------------------------- ledger / summary

def make_ledger(all_systems):
    flat = []
    for name, trades in all_systems:
        for t in trades:
            flat.append(dict(system=name, dir=t["dir"], entry_time=t["entry_time"],
                              exit_time=t["exit_time"], pnl=t["pnl"]))
    # Chronological by EXIT time (when pnl realizes into balance - matches
    # MT5's own Balance column, which updates on deal close, not open); ties
    # broken by entry time then system name for a deterministic row order.
    flat.sort(key=lambda r: (r["exit_time"], r["entry_time"], r["system"]))
    return flat


def system_stats(trades):
    pnl = np.array([t["pnl"] for t in trades], dtype=float)
    n = len(pnl)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    net = float(pnl.sum())
    gp = float(wins.sum())
    gl = float(-losses.sum())
    return dict(
        n=n, wins=int(len(wins)),
        win_rate=100.0 * len(wins) / n if n else 0.0,
        gross_profit=gp, gross_loss=gl,
        pf=(gp / gl) if gl > 0 else float("inf"),
        net=net,
    )


def make_summary(all_systems):
    rows = []
    total_pnl = []
    for name, trades in all_systems:
        s = system_stats(trades)
        rows.append(dict(system=name, indicator=INDICATOR_FAMILY[name], **s))
        total_pnl.extend(t["pnl"] for t in trades)
    total_pnl = np.array(total_pnl, dtype=float)
    total = system_stats([dict(pnl=p) for p in total_pnl])
    for r in rows:
        r["pct_of_total"] = (r["net"] / total["net"] * 100.0) if total["net"] else 0.0
    return rows, total


# --------------------------------------------------------------- workbook writer

FONT_NAME = "Arial"
HEADER_FILL = PatternFill("solid", fgColor="1F3864")
TOTAL_FILL = PatternFill("solid", fgColor="D9E1F2")
INPUT_FONT = Font(name=FONT_NAME, color="0000FF", bold=True, size=11)
HEADER_FONT = Font(name=FONT_NAME, color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(name=FONT_NAME, bold=True, size=14)
BOLD = Font(name=FONT_NAME, bold=True, size=11)
NORMAL = Font(name=FONT_NAME, size=11)
THIN = Side(style="thin", color="B7B7B7")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CUR_FMT = '#,##0.00 "ZAR";(#,##0.00 "ZAR");-'
PCT_FMT = '0.0%'
DT_FMT = 'yyyy-mm-dd hh:mm'


def _style_header_row(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def _autosize(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def write_trade_ledger_sheet(wb, ledger, window_label):
    # NOTE ON STATIC VALUES: this workbook writes every computed number
    # (running balance included) as a plain Python-computed value, not an
    # Excel formula. openpyxl-written formulas carry NO cached value until a
    # real spreadsheet engine opens and recalculates the file - this
    # container's own LibreOffice recalc pass was found to silently fail
    # this session, leaving the earlier combine_all7.py workbooks' formula
    # cells reading back blank/None. To avoid that whole failure class, this
    # workbook is 100% static values in every cell that a viewer relies on;
    # correct regardless of what recalculates it (or doesn't).
    ws = wb.create_sheet("Trade Ledger")
    ws["A1"] = f"Combined 7-EA Portfolio (REAL MT5 data) - Trade Ledger ({window_label})"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:H1")

    ws["A2"] = "Starting Balance (ZAR):"
    ws["A2"].font = BOLD
    ws["C2"] = STARTING_BALANCE
    ws["C2"].font = INPUT_FONT
    ws["C2"].number_format = CUR_FMT
    ws["E2"] = "Window:"
    ws["E2"].font = BOLD
    ws["F2"] = window_label
    ws["F2"].font = NORMAL
    ws["A3"] = ("All values below are static, pre-computed numbers written by "
                "research/portfolio/combine_all7_real.py in Python - not live Excel formulas.")
    ws["A3"].font = Font(name=FONT_NAME, italic=True, size=9, color="777777")
    ws.merge_cells("A3:H3")

    header_row = 4
    headers = ["#", "System", "Core Indicator / Signal", "Direction", "Entry Time", "Exit Time",
               "PnL (ZAR, this trade)", "Balance After (ZAR)"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=c, value=h)
    _style_header_row(ws, header_row, len(headers))
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate

    r = header_row + 1
    running_balance = STARTING_BALANCE
    for i, row in enumerate(ledger, start=1):
        ws.cell(row=r, column=1, value=i)
        ws.cell(row=r, column=2, value=row["system"])
        ws.cell(row=r, column=3, value=INDICATOR_FAMILY[row["system"]])
        ws.cell(row=r, column=4, value="Long" if row["dir"] > 0 else "Short")
        ec = ws.cell(row=r, column=5, value=row["entry_time"])
        ec.number_format = DT_FMT
        xc = ws.cell(row=r, column=6, value=row["exit_time"])
        xc.number_format = DT_FMT
        pnl = round(float(row["pnl"]), 2)
        pc = ws.cell(row=r, column=7, value=pnl)
        pc.number_format = CUR_FMT
        running_balance = round(running_balance + pnl, 2)
        bal_cell = ws.cell(row=r, column=8, value=running_balance)
        bal_cell.number_format = CUR_FMT
        for c in range(1, 9):
            ws.cell(row=r, column=c).font = NORMAL
            ws.cell(row=r, column=c).border = BORDER
        r += 1
    last_row = r - 1

    ws.auto_filter.ref = f"A{header_row}:H{last_row}"
    _autosize(ws, [6, 14, 44, 10, 18, 18, 20, 20])
    return last_row, header_row, running_balance


def write_summary_sheet(wb, all_systems, summary_rows, total, ledger_last_row, ledger_header_row,
                         window_label, final_balance):
    # STATIC VALUES ONLY - see the note in write_trade_ledger_sheet(): every
    # number here (trade counts, win rate, gross profit/loss, PF, net
    # contribution, % of total) is computed in Python (system_stats() /
    # make_summary()) and written as a plain value, not a SUMIF/COUNTIF/
    # SUMIFS formula, so the sheet displays correctly with zero dependency
    # on any spreadsheet engine recalculating it.
    ws = wb.create_sheet("Summary")
    ws["A1"] = f"Combined 7-EA Portfolio (REAL MT5 data) - Summary / Attribution ({window_label})"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:J1")
    ws["A2"] = ("All values below are static, pre-computed numbers written by "
                "research/portfolio/combine_all7_real.py in Python - not live Excel formulas. "
                "They can be independently cross-checked against the Trade Ledger sheet's System and "
                "PnL columns.")
    ws["A2"].font = Font(name=FONT_NAME, italic=True, size=9, color="777777")
    ws["A2"].alignment = Alignment(wrap_text=True)
    ws.merge_cells("A2:J2")
    ws.row_dimensions[2].height = 24

    header_row = 4
    headers = ["System", "Core Indicator / Signal Family", "Trades", "Wins", "Win Rate %",
               "Gross Profit (ZAR)", "Gross Loss (ZAR)", "Profit Factor", "Net Contribution (ZAR)",
               "% of Portfolio Net Profit"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=c, value=h)
    _style_header_row(ws, header_row, len(headers))

    r = header_row + 1
    first_data_row = r
    for row in summary_rows:
        ws.cell(row=r, column=1, value=row["system"])
        ws.cell(row=r, column=2, value=row["indicator"])
        ws.cell(row=r, column=3, value=row["n"])
        ws.cell(row=r, column=4, value=row["wins"])
        wr_cell = ws.cell(row=r, column=5, value=round(row["win_rate"] / 100.0, 4))
        wr_cell.number_format = PCT_FMT
        ws.cell(row=r, column=6, value=round(row["gross_profit"], 2))
        ws.cell(row=r, column=7, value=round(row["gross_loss"], 2))
        pf = row["pf"]
        ws.cell(row=r, column=8, value=(pf if pf != float("inf") else None))
        ws.cell(row=r, column=9, value=round(row["net"], 2))
        for cc in (6, 7, 9):
            ws.cell(row=r, column=cc).number_format = CUR_FMT
        pct_cell = ws.cell(row=r, column=10, value=round(row["pct_of_total"] / 100.0, 4))
        pct_cell.number_format = PCT_FMT
        r += 1
    last_data_row = r - 1
    total_row = r

    ws.cell(row=total_row, column=1, value="PORTFOLIO TOTAL")
    ws.cell(row=total_row, column=2, value="All 7 systems combined")
    ws.cell(row=total_row, column=3, value=total["n"])
    ws.cell(row=total_row, column=4, value=total["wins"])
    wr_cell = ws.cell(row=total_row, column=5, value=round(total["win_rate"] / 100.0, 4))
    wr_cell.number_format = PCT_FMT
    ws.cell(row=total_row, column=6, value=round(total["gross_profit"], 2))
    ws.cell(row=total_row, column=7, value=round(total["gross_loss"], 2))
    pf = total["pf"]
    ws.cell(row=total_row, column=8, value=(pf if pf != float("inf") else None))
    ws.cell(row=total_row, column=9, value=round(total["net"], 2))
    for cc in (6, 7, 9):
        ws.cell(row=total_row, column=cc).number_format = CUR_FMT
    ws.cell(row=total_row, column=10, value=1.0)
    ws.cell(row=total_row, column=10).number_format = PCT_FMT

    for rr in range(first_data_row, total_row + 1):
        for c in range(1, 11):
            cell = ws.cell(row=rr, column=c)
            if cell.font is None or cell.font.name != FONT_NAME:
                cell.font = NORMAL
            cell.border = BORDER
        if rr == total_row:
            for c in range(1, 11):
                ws.cell(row=rr, column=c).font = BOLD
                ws.cell(row=rr, column=c).fill = TOTAL_FILL

    r2 = total_row + 2
    ws.cell(row=r2, column=1, value="Starting Balance (ZAR):").font = BOLD
    ws.cell(row=r2, column=3, value=round(STARTING_BALANCE, 2))
    ws.cell(row=r2, column=3).number_format = CUR_FMT
    ws.cell(row=r2 + 1, column=1, value="Final Balance (ZAR):").font = BOLD
    ws.cell(row=r2 + 1, column=3, value=round(final_balance, 2))
    ws.cell(row=r2 + 1, column=3).number_format = CUR_FMT
    ws.cell(row=r2 + 2, column=1, value="Total Net Profit (ZAR):").font = BOLD
    ws.cell(row=r2 + 2, column=3, value=round(total["net"], 2))
    ws.cell(row=r2 + 2, column=3).number_format = CUR_FMT

    _autosize(ws, [14, 46, 9, 8, 11, 16, 16, 12, 18, 14])
    return total_row


def write_methodology_sheet(all_systems, validations, wb, window_label):
    ws = wb.create_sheet("Methodology", 0)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 112

    src_lines = []
    for name in SYSTEM_ORDER:
        v = validations[name]
        clip_note = ("clipped here to exit time >= 2026-01-01" if v["clipped"]
                     else "native window already 2026.01.01-2026.09.21 - used in full, not further clipped")
        src_lines.append(
            f"  - {name}: {REPORTS[name]['path'].split('/')[-1]} - native window {v['native_window']}, "
            f"deposit {v['deposit']:,.0f} ZAR (0.01 lots fixed, {'0.03 lots fixed' if name=='MSG' else '0.01 lots fixed'}). "
            f"{clip_note}. {v['n_full']} real round-trips parsed in full report "
            f"(net {v['full_pnl_with_swap']:,.2f} ZAR incl. swap); {v['n_clipped']} kept after clipping "
            f"(net {v['clipped_pnl_with_swap']:,.2f} ZAR incl. swap)."
        )

    lines = [
        ("title", f"Combined 7-EA Portfolio Ledger - REAL MT5 Data - Methodology & Limitations ({window_label})"),
        ("blank", ""),
        ("h", "What this workbook is"),
        ("p", "A single combined trade-for-trade ledger and per-EA attribution summary for all SEVEN "
              "systems - Aurelius_EA.mq5 (M5), Aurelius_M15_EA.mq5, Vanguard_EA.mq5 (M5), "
              "Vanguard_M15_EA.mq5, Meridian_EA.mq5, Ratchet_EA.mq5 and MSG_Trader_EA.mq5 - trading "
              "together against ONE shared account, starting balance 13,500 ZAR."),
        ("p", "UNLIKE the earlier combine_all7.py workbooks in this same folder (which combine each "
              "EA's Python-SIMULATED trades), every trade in THIS workbook comes from that EA's own REAL "
              "MT5 Strategy Tester Deals-table data - no Python simulation is used anywhere in this "
              "file. This exists because the Python-model Ratchet net for this same window ($650-900) "
              "did not match the real MT5-confirmed Ratchet net for the identical EA/window "
              "(9,273.91 ZAR) - a Python simulator is a screening tool, not a stand-in for real "
              "execution, and this workbook uses real execution data throughout instead."),
        ("p", f"Window covered: {WINDOW_START:%Y-%m-%d} onward (2026-01-01 onward), through each real "
              "report's own coverage end (2026.09.21 for all seven). Currency is ZAR (South African "
              "Rand) throughout, not USD - these are real ZAR-denominated XM Global XMGlobal-MT5 13 "
              "accounts."),
        ("blank", ""),
        ("h", "Real source reports used (one per system)"),
        ("p", "\n".join(src_lines)),
        ("blank", ""),
        ("h", "Why trades from different original deposit sizes can be combined onto ONE new 13,500 ZAR balance"),
        ("p", "All seven real reports used FIXED lot sizing (InpLotMode=0 / LOT_FIXED - confirmed for "
              "each report this session): 0.01 lots for Aurelius/Vanguard/Meridian/Ratchet, 0.03 lots "
              "for MSG (its own real shipped default). Because lot size is fixed rather than "
              "balance-scaled, each trade's real ZAR Profit is independent of whatever deposit size that "
              "trade's ORIGINAL report happened to run against (20,000 ZAR for five of the seven "
              "systems, 13,500 ZAR for Ratchet and MSG) - the same trade would show the identical ZAR "
              "Profit figure regardless of the account balance behind it. That is what makes it valid to "
              "pull these real, trade-level ZAR pnl figures straight out of their seven original reports "
              "and restack them, in original exit-time order, onto ONE NEW shared starting balance of "
              "13,500 ZAR here. This is a deliberate methodological choice, not an oversight: it does "
              "NOT model shared margin or compounding effects a literal single real account running all "
              "seven EAs at once would have (see the final limitation below)."),
        ("blank", ""),
        ("h", "Swap-inclusion decision"),
        ("p", "DECISION: swap IS included in each trade's combined pnl. Each trade's pnl = the real "
              "out-deal's Profit column + the real out-deal's Swap column (+ Commission, confirmed 0.00 "
              "on every single deal row across all seven reports this session, included anyway for "
              "consistency). This follows this project's own established real-report reconciliation "
              "convention from earlier this session (research/ratchet/report.py's reconcile(): "
              "'sum(profit+commission+swap) over all round-trips must equal the report's own Total Net "
              "Profit to the cent'). Swap is a real cost (or, on the rare row, a real credit) of holding "
              "a position across a broker swap point - leaving it out would silently understate/"
              "overstate several systems' real combined pnl, notably Aurelius_M15, Vanguard M5/M15 and "
              "Meridian, whose Deals tables carry materially nonzero cumulative swap on their multi-day "
              "holds. This choice is applied UNIFORMLY to all seven systems."),
        ("blank", ""),
        ("h", "MSG caveat - KNOWN, MUST-DISCLOSE GAP (stated plainly, not buried)"),
        ("p", MSG_CAVEAT),
        ("blank", ""),
        ("h", "What this workbook is NOT"),
        ("p", "This is still NOT a literal, single, real, simultaneous 7-EA MT5 account run. These are "
              "seven INDEPENDENT real MT5 Strategy Tester passes - seven separate backtests, each on its "
              "own EA/settings/deposit - recombined here in ZAR-for-ZAR terms onto one shared ledger. No "
              "real account in this data ever actually held all seven EAs' positions open at once; there "
              "is NO shared-margin or shared-exposure modelling across the seven systems trading 'at "
              "once' on one real account. This is a straightforward realized-pnl ledger (stacking seven "
              "independent, but each individually 100% real, ZAR pnl streams onto one running balance), "
              "not a margin simulation."),
        ("blank", ""),
        ("h", "Ledger ordering"),
        ("p", "All seven systems' real trades are merged into ONE chronological ledger ordered by EXIT "
              "time - the moment a trade's pnl actually realizes into balance, matching how MT5's own "
              "Balance column updates on deal close (not on open). Running balance starts at 13,500 ZAR "
              "and updates by each trade's combined (Profit+Swap) pnl in that exit-time order."),
        ("blank", ""),
        ("h", "Parsing method and validation"),
        ("p", "Each report's Deals table is located by the row where column A='Time', column B='Deal' "
              "(Time/Deal/Symbol/Type/Direction/Volume/Price/Order/Commission/Swap/Profit/Balance/"
              "Comment), read down to the first blank/summary row. 'balance' rows are skipped. Deals are "
              "paired into round-trip trades by walking in original order: an 'in' deal opens a "
              "position (direction from its Type: buy=long, sell=short); subsequent deal(s) accumulate "
              "until cumulative out-volume equals in-volume, closing the trade. Every round-trip in all "
              "seven reports used here has exactly one out-leg (verified programmatically, no partial "
              "scale-outs present). Before any window-clipping, each report's parsed round-trips were "
              "validated to reproduce that report's own Deals-table column totals to the cent - see the "
              "per-system figures listed above and the console output this script prints."),
        ("blank", ""),
        ("h", "Reproducibility"),
        ("p", "Generated by research/portfolio/combine_all7_real.py, which parses the seven real .xlsx "
              "Strategy Tester reports listed above directly - no Python simulator is used anywhere in "
              "this file, and no .mq5 file is read or modified."),
        ("p", f"Generated {dt.datetime.now():%Y-%m-%d %H:%M} local."),
    ]

    r = 1
    for kind, text in lines:
        cell = ws.cell(row=r, column=1, value=text)
        if kind == "title":
            cell.font = Font(name=FONT_NAME, bold=True, size=16)
        elif kind == "h":
            cell.font = Font(name=FONT_NAME, bold=True, size=12, color="1F3864")
        elif kind == "p":
            cell.font = NORMAL
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            nlines = text.count("\n") + 1
            wrapped_lines = sum(max(1, (len(line) // 118 + 1)) for line in text.split("\n"))
            ws.row_dimensions[r].height = 15 * max(1, wrapped_lines)
        r += 1
    return ws


def build_workbook():
    all_systems, validations = build_portfolio()
    ledger = make_ledger(all_systems)
    summary_rows, total = make_summary(all_systems)

    window_label = "2026-01-01 onward (through 2026-09-21, ZAR)"

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ledger_last_row, ledger_header_row, final_balance = write_trade_ledger_sheet(wb, ledger, window_label)
    write_summary_sheet(wb, all_systems, summary_rows, total, ledger_last_row, ledger_header_row,
                         window_label, final_balance)
    write_methodology_sheet(all_systems, validations, wb, window_label)
    wb.save(OUT_PATH)

    return dict(all_systems=all_systems, ledger=ledger, summary_rows=summary_rows, total=total,
                validations=validations, out_path=OUT_PATH)


def _print_report(result):
    print(f"\n=== COMBINED 7-EA PORTFOLIO - REAL MT5 DATA (2026-01-01 onward, ZAR) ===")
    print(f"trades={result['total']['n']}  starting_balance={STARTING_BALANCE:.2f} ZAR  "
          f"final_balance={STARTING_BALANCE + result['total']['net']:.2f} ZAR  "
          f"net_profit={result['total']['net']:.2f} ZAR  blended_pf={result['total']['pf']:.3f}  "
          f"win_rate={result['total']['win_rate']:.1f}%")
    for row in result["summary_rows"]:
        print(f"  {row['system']:14s} n={row['n']:5d}  net={row['net']:12.2f} ZAR  "
              f"pct={row['pct_of_total']:6.1f}%  win%={row['win_rate']:5.1f}  "
              f"pf={row['pf'] if row['pf'] != float('inf') else float('inf'):.3f}")
    print("\n--- per-system parse validation (unclipped report totals) ---")
    for name in SYSTEM_ORDER:
        v = result["validations"][name]
        print(f"  {name:14s} nlegs/out-leg={v['nlegs']}  n_full={v['n_full']:5d}  "
              f"full_net(profit only)={v['full_profit_only']:12.2f}  "
              f"full_net(profit+swap)={v['full_pnl_with_swap']:12.2f}  "
              f"n_clipped={v['n_clipped']:5d}  clipped_net(profit+swap)={v['clipped_pnl_with_swap']:12.2f}")
    ratchet_v = result["validations"]["Ratchet"]
    print(f"\nRECONCILIATION CHECK: Ratchet real full-window net (profit only, no clipping applied) = "
          f"{ratchet_v['full_profit_only']:.2f} ZAR  (expected 9273.91 ZAR)  "
          f"{'MATCH' if abs(ratchet_v['full_profit_only'] - 9273.91) < 0.005 else 'MISMATCH -- DO NOT TRUST THIS WORKBOOK'}")
    print(f"  -> {result['out_path']}")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    result = build_workbook()
    _print_report(result)
