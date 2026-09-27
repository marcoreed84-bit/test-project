"""
Shared, instrument-agnostic machinery for the Silver/Bitcoin native-system
searches in this folder. Everything the individual search scripts need to
obey the project's rigor pipeline lives here ONCE so every construction is
held to the identical standard:

  1. walk-forward split (search on IS only, freeze, evaluate on untouched OOS)
  2. random-timing null with the IDENTICAL exit machinery + real spread cost,
     trade count calibrated to the real OOS count
  3. honest best-of-K correction with K = the literal grid size searched
  4. %PF computed on pnl / entry_price (never raw points)

DATA / POINT SIZE: the point is read from each CSV's own meta header line
(meta_point) and asserted against the known-correct value - SILVER=0.001
(meta_digits=3; hardcoding gold's 0.01 is the 10x spread-overcharge bug that
already burned Aurelius/Silver once), BTCUSD=0.01 (meta_digits=2). Spread is
always converted to PRICE via `spread_points * point` before it touches a
trade; no raw-points spread gate is used anywhere in this folder (BTC's
~6000-point median spread vs gold's ~30 makes any borrowed points threshold
meaningless).

SPLITS (fixed BEFORE any search in this folder was run):
  SILVER: IS 2014-06-12 -> 2021-01-01, OOS 2021-01-01 -> end (same boundary
          as every earlier Silver search in research/aurelius/).
  BTCUSD: IS 2021-01-01 -> 2024-01-01, OOS 2024-01-01 -> end. DELIBERATE
          CHANGE from btc_native_search.py's IS=2017-2022: the broker's own
          recorded BTC spread in 2018Q2-2020Q4 was 0.65-1.6% of price per
          round trip - 3-5x the median range of an entire M15 bar (0.2-0.4%).
          Any intraday system searched on that window is chosen by "which
          config trades least", not by signal quality, and then meets a
          10-20x cheaper cost regime OOS (2024-26 spread ~0.06-0.15%). Bars
          before 2021 are still loaded for indicator warm-up only.

EXECUTION CONVENTION (same as research/aurelius/*_search.py): a signal on
bar i (bar i has closed) fills at close[i] with one spread charge taken at
entry (buy = close + spread[i+1]*point, sell = close - spread[i+1]*point).
Stops/targets are resting orders checked from bar i+1 onward against
high/low; a bar that OPENS through the stop fills at that open (gap-aware -
slightly stricter than the earlier files, which always filled at the stop
price). If stop and target are both inside one bar the STOP is assumed to
have hit first (conservative). Exit-signal / time exits fill at that bar's
close. One position at a time (signals while in a trade are ignored).

Every exit rule used anywhere in this folder is SELF-CONTAINED (stop
distance, R-multiple target, chandelier trail, max hold, or a price-channel
exit array) so random-timing entries can be run through literally the same
function - the random null differs from the real system ONLY in entry
timing/direction. Random entries draw their stop distance (in ATR units)
from the real system's own empirical OOS stop-distance distribution, so the
null has the same risk geometry as the real trades.
"""
import numpy as np
import pandas as pd

try:
    from numba import njit
except ImportError:  # pragma: no cover - slow but correct fallback
    def njit(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
EXPECTED_POINT = {"SILVER": 0.001, "BTCUSD": 0.01, "GOLD": 0.01}
SPLITS = {
    "SILVER": (pd.Timestamp("2014-06-12"), pd.Timestamp("2021-01-01")),
    "BTCUSD": (pd.Timestamp("2021-01-01"), pd.Timestamp("2024-01-01")),
}
N_RANDOM = 1000
N_BOOT = 5000


# ------------------------------------------------------------------ data

def read_meta(path):
    with open(path) as f:
        first = f.readline().strip().split(",")
    return {first[i]: first[i + 1] for i in range(0, len(first) - 1, 2)}


def load_m15(symbol):
    path = f"{DATA_DIR}/{symbol}_M15_native.csv"
    meta = read_meta(path)
    point = float(meta["meta_point"])
    assert abs(point - EXPECTED_POINT[symbol]) < 1e-12, (symbol, point)
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    return df, point


def resample(df, rule):
    """Lossless OHLC aggregation (repo convention): open=first, high=max,
    low=min, close=last, volume=sum, spread=mean."""
    d = df.set_index("time")
    out = pd.DataFrame(dict(
        open=d["open"].resample(rule).first(),
        high=d["high"].resample(rule).max(),
        low=d["low"].resample(rule).min(),
        close=d["close"].resample(rule).last(),
        tick_volume=d["tick_volume"].resample(rule).sum(),
        spread=d["spread"].resample(rule).mean(),
    )).dropna()
    return out.reset_index()


class Bars:
    """Plain container of aligned float arrays + the IS/OOS index bounds."""

    def __init__(self, df, point, symbol):
        self.symbol = symbol
        self.point = point
        self.time = df["time"].values
        self.open = df["open"].values.astype(np.float64)
        self.high = df["high"].values.astype(np.float64)
        self.low = df["low"].values.astype(np.float64)
        self.close = df["close"].values.astype(np.float64)
        self.vol = df["tick_volume"].values.astype(np.float64)
        self.spread_px = df["spread"].values.astype(np.float64) * point
        self.n = len(df)
        self.atr = wilder_atr(self.high, self.low, self.close, 14)
        is_start, is_end = SPLITS[symbol]
        self.is_lo = int(np.searchsorted(self.time, np.datetime64(is_start)))
        self.is_hi = int(np.searchsorted(self.time, np.datetime64(is_end)))
        self.oos_lo, self.oos_hi = self.is_hi, self.n
        self.hour = df["time"].dt.hour.values
        self.minute = df["time"].dt.minute.values
        self.date_id = (df["time"].dt.normalize().values.astype("datetime64[D]").astype(np.int64))

    def describe(self):
        t = pd.to_datetime(self.time)
        return (f"{self.symbol}: n={self.n} bars {t[0]} -> {t[-1]} | IS {t[self.is_lo]} -> {t[self.is_hi - 1]} "
                f"({self.is_hi - self.is_lo} bars) | OOS {t[self.oos_lo]} -> {t[-1]} ({self.n - self.oos_lo} bars, untouched)")


# ------------------------------------------------------------------ indicators

@njit(cache=True)
def wilder_atr(h, l, c, period):
    n = len(c)
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = np.full(n, np.nan)
    if n <= period:
        return out
    s = 0.0
    for i in range(1, period + 1):
        s += tr[i]
    out[period] = s / period
    for i in range(period + 1, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def ema(x, period):
    return pd.Series(x).ewm(alpha=2.0 / (period + 1.0), adjust=False).mean().values


def sma(x, period):
    return pd.Series(x).rolling(period, min_periods=period).mean().values


@njit(cache=True)
def wilder_adx(h, l, c, period):
    """Classic Wilder ADX / +DI / -DI (SMA-seeded Wilder smoothing)."""
    n = len(c)
    pdm = np.zeros(n); mdm = np.zeros(n); tr = np.zeros(n)
    for i in range(1, n):
        up = h[i] - h[i - 1]; dn = l[i - 1] - l[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        mdm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    pdi = np.full(n, np.nan); mdi = np.full(n, np.nan); adx = np.full(n, np.nan)
    if n <= 2 * period + 1:
        return adx, pdi, mdi
    str_ = 0.0; sp = 0.0; sm = 0.0
    for i in range(1, period + 1):
        str_ += tr[i]; sp += pdm[i]; sm += mdm[i]
    dx = np.full(n, np.nan)
    for i in range(period, n):
        if i > period:
            str_ = str_ - str_ / period + tr[i]
            sp = sp - sp / period + pdm[i]
            sm = sm - sm / period + mdm[i]
        if str_ > 0:
            pdi[i] = 100.0 * sp / str_
            mdi[i] = 100.0 * sm / str_
            s = pdi[i] + mdi[i]
            dx[i] = 100.0 * abs(pdi[i] - mdi[i]) / s if s > 0 else 0.0
    s = 0.0
    for i in range(period, 2 * period):
        s += dx[i]
    adx[2 * period - 1] = s / period
    for i in range(2 * period, n):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
    return adx, pdi, mdi


def bollinger(c, period=20, dev=2.0):
    """Same as research/ratchet/bars.py mt5_bands (population std)."""
    mid = sma(c, period)
    sd = pd.Series(c).rolling(period, min_periods=period).std(ddof=0).values
    return mid, mid + dev * sd, mid - dev * sd


@njit(cache=True)
def pivots(h, l, k):
    """N-bar fractal pivots, returned as CONFIRMATION-TIME arrays with no
    lookahead: ph_level[i] is the level of a pivot high whose confirmation
    completes on bar i (i.e. pivot at bar i-k, highest of bars i-2k..i with
    strictly-higher-than-left / >=-than-right tie rule), else NaN."""
    n = len(h)
    ph = np.full(n, np.nan); pl = np.full(n, np.nan)
    for j in range(k, n - k):
        hj = h[j]; lj = l[j]
        okh = True; okl = True
        for m in range(j - k, j):
            if h[m] >= hj:
                okh = False
            if l[m] <= lj:
                okl = False
        for m in range(j + 1, j + k + 1):
            if h[m] > hj:
                okh = False
            if l[m] < lj:
                okl = False
        if okh:
            ph[j + k] = hj
        if okl:
            pl[j + k] = lj
    return ph, pl


# ------------------------------------------------------------------ trade engine

@njit(cache=True)
def _run_one(i, d, dist, o, h, l, c, sp, atr, n, target_r, max_hold, trail_atr, exit_long, exit_short):
    """Simulate one position opened on signal bar i. Returns (exit_bar, pnl_pct)."""
    raw = c[i]
    fill = i + 1
    cost = sp[fill]
    is_buy = d > 0
    entry = raw + cost if is_buy else raw - cost
    sl = raw - dist if is_buy else raw + dist
    tp = np.nan
    if target_r > 0:
        tp = raw + target_r * dist if is_buy else raw - target_r * dist
    best = raw
    last = min(n - 1, i + max_hold)
    exit_bar = last
    exit_px = c[last]
    for k in range(fill, last + 1):
        if is_buy:
            if o[k] <= sl:
                exit_bar = k; exit_px = o[k]; break
            if l[k] <= sl:
                exit_bar = k; exit_px = sl; break
            if target_r > 0:
                if o[k] >= tp:
                    exit_bar = k; exit_px = o[k]; break
                if h[k] >= tp:
                    exit_bar = k; exit_px = tp; break
            if exit_long[k]:
                exit_bar = k; exit_px = c[k]; break
            if trail_atr > 0 and not np.isnan(atr[k]):
                if c[k] > best:
                    best = c[k]
                nsl = best - trail_atr * atr[k]
                if nsl > sl:
                    sl = nsl
        else:
            if o[k] >= sl:
                exit_bar = k; exit_px = o[k]; break
            if h[k] >= sl:
                exit_bar = k; exit_px = sl; break
            if target_r > 0:
                if o[k] <= tp:
                    exit_bar = k; exit_px = o[k]; break
                if l[k] <= tp:
                    exit_bar = k; exit_px = tp; break
            if exit_short[k]:
                exit_bar = k; exit_px = c[k]; break
            if trail_atr > 0 and not np.isnan(atr[k]):
                if c[k] < best:
                    best = c[k]
                nsl = best + trail_atr * atr[k]
                if nsl < sl:
                    sl = nsl
    pnl = (exit_px - entry) if is_buy else (entry - exit_px)
    return exit_bar, pnl / entry


@njit(cache=True)
def sim_signals(sig_bar, sig_dir, sig_dist, o, h, l, c, sp, atr, target_r, max_hold, trail_atr,
                exit_long, exit_short, lo, hi):
    """Run the real system's signals (sorted by bar) whose SIGNAL bar lies in
    [lo, hi). One position at a time. Returns entry_bar, exit_bar, dir,
    pnl_pct, stopdist_atr arrays."""
    n = len(c)
    m = len(sig_bar)
    eb = np.empty(m, np.int64); xb = np.empty(m, np.int64); dd = np.empty(m)
    pp = np.empty(m); sa = np.empty(m)
    cnt = 0
    last_exit = -1
    for s in range(m):
        i = sig_bar[s]
        if i < lo or i >= hi or i <= last_exit or i + 1 >= n:
            continue
        if np.isnan(atr[i]) or atr[i] <= 0 or sig_dist[s] <= 0:
            continue
        xbar, pnl = _run_one(i, sig_dir[s], sig_dist[s], o, h, l, c, sp, atr, n, target_r, max_hold,
                             trail_atr, exit_long, exit_short)
        eb[cnt] = i; xb[cnt] = xbar; dd[cnt] = sig_dir[s]; pp[cnt] = pnl; sa[cnt] = sig_dist[s] / atr[i]
        cnt += 1
        last_exit = xbar
    return eb[:cnt], xb[:cnt], dd[:cnt], pp[:cnt], sa[:cnt]


@njit(cache=True)
def sim_random(seed, p_fire, p_long, dist_atr_pool, o, h, l, c, sp, atr, target_r, max_hold, trail_atr,
               exit_long, exit_short, lo, hi, allowed):
    """Random-timing, random-direction entries through the IDENTICAL exit
    function. Stop distance = a draw from the real system's own stop-distance
    distribution (ATR units) x ATR at the random bar. `allowed` masks bars
    the real system could never trade (e.g. outside a session window) so the
    null is not handed bars the system structurally avoids. Returns pnl_pct
    array."""
    np.random.seed(seed)
    n = len(c)
    out = np.empty(hi - lo)
    cnt = 0
    last_exit = -1
    npool = len(dist_atr_pool)
    for i in range(lo, min(hi, n - 1)):
        if i <= last_exit or not allowed[i]:
            continue
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        if np.random.random() >= p_fire:
            continue
        d = 1.0 if np.random.random() < p_long else -1.0
        dist = dist_atr_pool[np.random.randint(0, npool)] * atr[i]
        xbar, pnl = _run_one(i, d, dist, o, h, l, c, sp, atr, n, target_r, max_hold, trail_atr,
                             exit_long, exit_short)
        out[cnt] = pnl
        cnt += 1
        last_exit = xbar
    return out[:cnt]


def pct_pf(pnl_pct):
    pnl_pct = np.asarray(pnl_pct)
    if len(pnl_pct) == 0:
        return float("nan")
    gw = pnl_pct[pnl_pct > 0].sum()
    gl = -pnl_pct[pnl_pct <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


# ------------------------------------------------------------------ evaluation

def random_pool(bars, dist_pool, target_n, target_r, max_hold, trail_atr, exit_long, exit_short,
                lo, hi, allowed, p_long=0.5, n_draws=N_RANDOM, seed0=0):
    """Calibrate p_fire so the average random trade count matches target_n,
    then draw n_draws %PFs."""
    b = bars
    args = (b.open, b.high, b.low, b.close, b.spread_px, b.atr, target_r, max_hold, trail_atr,
            exit_long, exit_short, lo, hi, allowed)
    p_fire = min(0.5, max(1e-6, target_n / max(1, allowed[lo:hi].sum()) * 3))
    for it in range(8):
        counts = [len(sim_random(seed0 + 10_000 + it * 10 + r, p_fire, p_long, dist_pool, *args)) for r in range(5)]
        m = np.mean(counts)
        if m <= 0:
            p_fire = min(0.5, p_fire * 3)
            continue
        if abs(m - target_n) / target_n < 0.03:
            break
        p_fire = min(0.5, max(1e-7, p_fire * target_n / m))
    pool, ns = [], []
    for r in range(n_draws):
        tr = sim_random(seed0 + r, p_fire, p_long, dist_pool, *args)
        ns.append(len(tr))
        pool.append(pct_pf(tr))
    pool = np.array(pool)
    ok = np.isfinite(pool)
    return pool[ok], p_fire, float(np.mean(ns))


def best_of_k_p(pool, real, K, seed=7):
    rng = np.random.default_rng(seed)
    b = pool[rng.integers(0, len(pool), size=(N_BOOT, K))].max(axis=1)
    return float((b >= real).mean()), float(np.median(b))


def verdict(p):
    return "SURVIVES" if p < 0.05 else ("borderline" if p < 0.15 else "DOES NOT SURVIVE")


def full_evaluation(bars, label, grid, signal_fn, exit_fn, min_is_n=100, allowed=None, log=print):
    """The whole pipeline for one (instrument, construction) search.

    grid      : list of hashable config tuples - its LENGTH is the honest K.
    signal_fn : cfg -> (sig_bar int64[], sig_dir float[], sig_dist float[]) computed on ALL bars
                (causal indicators only), sorted by bar.
    exit_fn   : cfg -> dict(target_r, max_hold, trail_atr, exit_long, exit_short)
    """
    b = bars
    K = len(grid)
    if allowed is None:
        allowed = np.ones(b.n, dtype=np.bool_)
    log(f"\n{'=' * 90}\n{label}\n{b.describe()}\nGRID K={K} (literal grid size); selection = highest IS %PF with IS n>={min_is_n}\n{'=' * 90}")
    rows = []
    cache = {}
    for cfg in grid:
        sb, sd, sdist = signal_fn(cfg)
        ex = exit_fn(cfg)
        cache[cfg] = (sb, sd, sdist, ex)
        r = sim_signals(sb, sd, sdist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                        ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"],
                        b.is_lo, b.is_hi)
        rows.append(dict(cfg=cfg, n=len(r[3]), pf=pct_pf(r[3]), longs=float((r[2] > 0).mean()) if len(r[2]) else np.nan))
    valid = [r for r in rows if r["n"] >= min_is_n and np.isfinite(r["pf"])]
    valid.sort(key=lambda r: r["pf"], reverse=True)
    n_above1 = sum(1 for r in valid if r["pf"] > 1.0)
    log(f"{len(valid)}/{K} combos had IS n>={min_is_n}; {n_above1} of them have IS %PF > 1.0. Top 8 by IS %PF:")
    for r in valid[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}  long%={100 * r['longs']:.0f}")
    if not valid:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE (nothing to freeze).")
        return dict(label=label, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")
    best = valid[0]
    cfg = best["cfg"]
    sb, sd, sdist, ex = cache[cfg]
    exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
    log(f"FROZEN WINNER (IS only): {cfg}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    # --- IS-side selection-bias check: does the IS winner even beat best-of-K random on IS?
    is_r = sim_signals(sb, sd, sdist, b.open, b.high, b.low, b.close, b.spread_px, b.atr, *exargs, b.is_lo, b.is_hi)
    is_pool, _, _ = random_pool(b, is_r[4], len(is_r[3]), *exargs, b.is_lo, b.is_hi, allowed, seed0=500_000)
    p_is_k, med_is_k = best_of_k_p(is_pool, best["pf"], K)
    log(f"IS sanity: random-timing IS pool median={np.median(is_pool):.3f}; IS winner vs best-of-{K} random "
        f"(median {med_is_k:.3f}): p={p_is_k:.4f}")

    # --- OOS
    r = sim_signals(sb, sd, sdist, b.open, b.high, b.low, b.close, b.spread_px, b.atr, *exargs, b.oos_lo, b.oos_hi)
    oos_pnl, oos_dir, oos_dist = r[3], r[2], r[4]
    n_oos = len(oos_pnl)
    oos_pf = pct_pf(oos_pnl)
    res = dict(label=label, K=K, cfg=cfg, is_n=best["n"], is_pf=best["pf"], oos_n=n_oos, oos_pf=oos_pf,
               p_is_k=p_is_k)
    if n_oos == 0:
        log("No OOS trades."); res["verdict"] = "DOES NOT SURVIVE (0 OOS trades)"; return res
    longf = float((oos_dir > 0).mean())
    lp = oos_pnl[oos_dir > 0]; spnl = oos_pnl[oos_dir < 0]
    log(f"OOS (untouched): n={n_oos}  win%={100 * (oos_pnl > 0).mean():.1f}  %PF={oos_pf:.3f}  "
        f"sum%={100 * oos_pnl.sum():.1f}  long%={100 * longf:.0f} "
        f"(long %PF={pct_pf(lp):.3f} n={len(lp)}, short %PF={pct_pf(spnl):.3f} n={len(spnl)})")
    if n_oos < 20:
        log("Too few OOS trades for a meaningful null -> DOES NOT SURVIVE (insufficient evidence).")
        res["verdict"] = "DOES NOT SURVIVE (n<20)"; return res
    pool, p_fire, mean_n = random_pool(b, oos_dist, n_oos, *exargs, b.oos_lo, b.oos_hi, allowed)
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = best_of_k_p(pool, oos_pf, K)
    log(f"random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={mean_n:.0f} vs real {n_oos}): "
        f"median={np.median(pool):.3f}  p95={np.percentile(pool, 95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{verdict(pK)}]")
    # supplementary, stricter null: random timing but direction mix matched to the real system
    dpool, _, _ = random_pool(b, oos_dist, n_oos, *exargs, b.oos_lo, b.oos_hi, allowed, p_long=longf, seed0=900_000)
    p1d = float((dpool >= oos_pf).mean())
    log(f"supplementary direction-matched null (p_long={longf:.2f}): median={np.median(dpool):.3f}  p(K=1)={p1d:.4f}")
    res.update(pctile=pctile, p1=p1, pK=pK, p1_dir=p1d, null_median=float(np.median(pool)),
               verdict=verdict(pK) if p1 < 0.05 else verdict(max(p1, pK)))
    return res
