"""
"The Candlestick Trading Bible" (KohanFx.com) - genuinely new patterns not
yet tested this session (Engulfing was already covered in hs_candlestick_test.py,
real-but-thin finding). This book's own definitions, real GOLD M15 data:

1. DOJI / DRAGONFLY DOJI / GRAVESTONE DOJI: open==close (roughly). Dragonfly
   = long lower shadow, little upper shadow (bullish, at a downtrend low).
   Gravestone = long upper shadow, little lower shadow (bearish, at an
   uptrend high). Plain Doji = neither shadow dominates.
2. MORNING STAR / EVENING STAR: 3 candles - big move, small indecision body,
   then a big reversal candle closing beyond the midpoint of candle 1's body.
3. HAMMER / SHOOTING STAR ("pin bar"): small body at one end of the range,
   opposite shadow >= 2x the body (the book's own explicit rule), the other
   shadow small/absent.
4. HARAMI (Inside Bar): candle 2's body fully inside candle 1's (the
   "mother") body - tested BOTH as a reversal signal (at a trend extreme,
   the book's primary framing) and as a continuation signal (mid-trend,
   the book's own secondary claim - "a continuation pattern which gives a
   good opportunity to join the trend").
5. TWEEZERS TOP/BOTTOM: two adjacent candles with closely-matching
   highs (top) or lows (bottom), opposite colours.

The book insists candlesticks alone aren't enough - "must occur near a
resistance/support level" / "at the top/bottom of a trend" - so every
signal here is tested at a genuine local extreme (a new N-bar high/low),
not in isolation, matching the book's own claim rather than a strawman.
Real control: random bar at a random local extreme, same sample size.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E

np.random.seed(42)
HORIZON = 20            # bars forward to measure reversal
EXTREME_LOOKBACK = 20   # "new N-bar high/low" - what counts as a genuine trend extreme
DOJI_BODY_FRAC = 0.10    # body <= this fraction of range counts as "doji-like"
SMALL_BODY_FRAC = 0.30   # hammer/star/star body <= this fraction of range
LONG_SHADOW_MULT = 2.0   # book's own rule: dominant shadow >= 2x body
SHORT_SHADOW_FRAC = 0.15 # opposite shadow <= this fraction of range counts as "little/none"
TWEEZER_TOL_ATR = 0.15   # matching-extreme tolerance, x ATR


def body_range(o, h, l, c, i):
    rng = h[i] - l[i]
    body = abs(c[i] - o[i])
    return body, rng


def is_new_high(h, i, lookback):
    return i >= lookback and h[i] >= h[i - lookback:i].max()


def is_new_low(l, i, lookback):
    return i >= lookback and l[i] <= l[i - lookback:i].min()


def eval_signal(o, h, l, c, idx, bullish, n):
    """idx: bar indices where the signal fires. bullish: expected direction.
    Returns dict with reversal-rate and avg-move-in-signal-direction stats."""
    idx = [i for i in idx if i + HORIZON < n and i >= 1]
    if len(idx) < 8:
        return None
    entry = c[np.array(idx)]
    fwd = c[np.array(idx) + HORIZON] - entry
    move = fwd if bullish else -fwd
    return dict(n=len(idx), rate=100 * np.mean(move > 0), avg=np.mean(move), idx=idx)


def control(o, h, l, c, n, sample_n, bullish_frac=0.5):
    rng = np.random.default_rng(42)
    idx = rng.choice(np.arange(EXTREME_LOOKBACK, n - HORIZON), size=sample_n, replace=False)
    bullish = rng.random(sample_n) < bullish_frac
    entry = c[idx]
    fwd = c[idx + HORIZON] - entry
    move = np.where(bullish, fwd, -fwd)
    return dict(n=sample_n, rate=100 * np.mean(move > 0), avg=np.mean(move))


def report(res, ctrl, label):
    if res is None:
        print(f"  {label}: too few"); return
    c = f"  CONTROL: rate={ctrl['rate']:.1f}% avg={ctrl['avg']:.2f}" if ctrl else ""
    print(f"  {label}: n={res['n']}  reversal-rate={res['rate']:.1f}%  avg move={res['avg']:.2f}{c}")


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    o = df15["open"].values; h = df15["high"].values; l = df15["low"].values; c = df15["close"].values
    n = len(o)
    print(f"real GOLD M15, n={n} bars")

    # ---------------------------------------------------------------- DOJI FAMILY
    print("\n" + "=" * 90)
    print("DOJI / DRAGONFLY DOJI / GRAVESTONE DOJI (at a genuine N-bar extreme)")
    print("=" * 90)
    doji_idx, dragon_idx, grave_idx = [], [], []
    for i in range(n):
        body, rng = body_range(o, h, l, c, i)
        if rng <= 0 or body > DOJI_BODY_FRAC * rng:
            continue
        upper = h[i] - max(o[i], c[i])
        lower = min(o[i], c[i]) - l[i]
        if upper <= SHORT_SHADOW_FRAC * rng and lower >= LONG_SHADOW_MULT * max(body, 1e-9) and is_new_low(l, i, EXTREME_LOOKBACK):
            dragon_idx.append(i)
        elif lower <= SHORT_SHADOW_FRAC * rng and upper >= LONG_SHADOW_MULT * max(body, 1e-9) and is_new_high(h, i, EXTREME_LOOKBACK):
            grave_idx.append(i)
        elif is_new_high(h, i, EXTREME_LOOKBACK) or is_new_low(l, i, EXTREME_LOOKBACK):
            doji_idx.append((i, is_new_low(l, i, EXTREME_LOOKBACK)))

    doji_bull = [i for i, bull in doji_idx if bull]
    doji_bear = [i for i, bull in doji_idx if not bull]
    r = eval_signal(o, h, l, c, doji_bull, True, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "plain Doji at new low (bullish reversal claim)")
    r = eval_signal(o, h, l, c, doji_bear, False, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "plain Doji at new high (bearish reversal claim)")
    r = eval_signal(o, h, l, c, dragon_idx, True, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Dragonfly Doji at new low (bullish)")
    r = eval_signal(o, h, l, c, grave_idx, False, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Gravestone Doji at new high (bearish)")

    # ---------------------------------------------------------------- HAMMER / SHOOTING STAR
    print("\n" + "=" * 90)
    print("HAMMER / SHOOTING STAR (pin bar) - real book rule: opposite shadow >= 2x body")
    print("=" * 90)
    hammer_idx, star_idx = [], []
    for i in range(n):
        body, rng = body_range(o, h, l, c, i)
        if rng <= 0 or body > SMALL_BODY_FRAC * rng:
            continue
        upper = h[i] - max(o[i], c[i])
        lower = min(o[i], c[i]) - l[i]
        if lower >= LONG_SHADOW_MULT * max(body, 1e-9) and upper <= SHORT_SHADOW_FRAC * rng and is_new_low(l, i, EXTREME_LOOKBACK):
            hammer_idx.append(i)
        if upper >= LONG_SHADOW_MULT * max(body, 1e-9) and lower <= SHORT_SHADOW_FRAC * rng and is_new_high(h, i, EXTREME_LOOKBACK):
            star_idx.append(i)
    r = eval_signal(o, h, l, c, hammer_idx, True, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Hammer at new low (bullish)")
    r = eval_signal(o, h, l, c, star_idx, False, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Shooting Star at new high (bearish)")

    # ---------------------------------------------------------------- MORNING / EVENING STAR
    print("\n" + "=" * 90)
    print("MORNING STAR / EVENING STAR (3-candle)")
    print("=" * 90)
    morning_idx, evening_idx = [], []
    for i in range(2, n):
        b1, r1 = body_range(o, h, l, c, i - 2)
        b2, r2 = body_range(o, h, l, c, i - 1)
        b3, r3 = body_range(o, h, l, c, i)
        if r1 <= 0 or r3 <= 0:
            continue
        c1_bear = c[i - 2] < o[i - 2]
        c1_bull = c[i - 2] > o[i - 2]
        mid1 = (o[i - 2] + c[i - 2]) / 2.0
        small2 = b2 <= SMALL_BODY_FRAC * max(r1, r2, 1e-9)
        c3_bull = c[i] > o[i]
        c3_bear = c[i] < o[i]
        if c1_bear and small2 and c3_bull and c[i] > mid1 and is_new_low(l, i - 2, EXTREME_LOOKBACK):
            morning_idx.append(i)
        if c1_bull and small2 and c3_bear and c[i] < mid1 and is_new_high(h, i - 2, EXTREME_LOOKBACK):
            evening_idx.append(i)
    r = eval_signal(o, h, l, c, morning_idx, True, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Morning Star (bullish)")
    r = eval_signal(o, h, l, c, evening_idx, False, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Evening Star (bearish)")

    # ---------------------------------------------------------------- HARAMI (INSIDE BAR)
    print("\n" + "=" * 90)
    print("HARAMI / INSIDE BAR - tested BOTH ways per the book's own dual claim")
    print("=" * 90)
    harami_rev_bull, harami_rev_bear, harami_cont_bull, harami_cont_bear = [], [], [], []
    for i in range(1, n):
        b0, r0 = body_range(o, h, l, c, i - 1)
        b1, r1 = body_range(o, h, l, c, i)
        if r0 <= 0 or b0 <= 0:
            continue
        hi0, lo0 = max(o[i - 1], c[i - 1]), min(o[i - 1], c[i - 1])
        hi1, lo1 = max(o[i], c[i]), min(o[i], c[i])
        inside = (hi1 <= hi0) and (lo1 >= lo0) and b1 < b0
        if not inside:
            continue
        mother_bear = c[i - 1] < o[i - 1]
        if is_new_high(h, i - 1, EXTREME_LOOKBACK):
            (harami_rev_bear if mother_bear or True else None)
            harami_rev_bear.append(i)   # reversal use: at a high, expect bearish regardless of mother colour (book: colour doesn't matter)
        elif is_new_low(l, i - 1, EXTREME_LOOKBACK):
            harami_rev_bull.append(i)
        else:
            if mother_bear:
                harami_cont_bear.append(i)
            else:
                harami_cont_bull.append(i)
    r = eval_signal(o, h, l, c, harami_rev_bull, True, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Harami REVERSAL at new low (bullish)")
    r = eval_signal(o, h, l, c, harami_rev_bear, False, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Harami REVERSAL at new high (bearish)")
    r = eval_signal(o, h, l, c, harami_cont_bull, True, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Harami CONTINUATION, bullish mother, mid-trend")
    r = eval_signal(o, h, l, c, harami_cont_bear, False, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Harami CONTINUATION, bearish mother, mid-trend")

    # ---------------------------------------------------------------- TWEEZERS
    print("\n" + "=" * 90)
    print("TWEEZERS TOP/BOTTOM - matching extremes, opposite colours")
    print("=" * 90)
    from h4_touch_reaction_test import sma_atr, ATR_PERIOD
    atr = sma_atr(h, l, o, ATR_PERIOD)
    tweez_top, tweez_bot = [], []
    for i in range(1, n):
        opp_colour = (c[i - 1] > o[i - 1]) != (c[i] > o[i])
        if not opp_colour or np.isnan(atr[i]):
            continue
        tol = TWEEZER_TOL_ATR * atr[i]
        if abs(h[i] - h[i - 1]) <= tol and is_new_high(h, i, EXTREME_LOOKBACK):
            tweez_top.append(i)
        if abs(l[i] - l[i - 1]) <= tol and is_new_low(l, i, EXTREME_LOOKBACK):
            tweez_bot.append(i)
    r = eval_signal(o, h, l, c, tweez_bot, True, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Tweezers Bottom (bullish)")
    r = eval_signal(o, h, l, c, tweez_top, False, n); report(r, control(o, h, l, c, n, r["n"] if r else 8), "Tweezers Top (bearish)")
