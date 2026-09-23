"""Null test for 'size 0.01 when risk% < TH': is choosing WHICH trades to shrink
by risk% better than shrinking the same number of randomly chosen trades?
Cascade-free (sizing never changes the sequence), so real MT5 trade lists are
used directly; 20,000 random draws each."""
import sys
import numpy as np
sys.path.insert(0, "/home/user/test-project/research/msg")
from real_resize import load, resized, LISTS  # noqa

TH = 0.26
rng = np.random.default_rng(12345)
for label, f in LISTS:
    trips = load(f)
    base = np.array([t["pnl_usd"] for t in trips])
    small = np.array([resized(t, 0.01) for t in trips])
    sel = np.array([t["risk_pct"] < TH for t in trips])
    obs = (small - base)[sel].sum()
    k = sel.sum()
    null = np.array([(small - base)[rng.choice(len(trips), k, replace=False)].sum() for _ in range(20000)])
    print(f"{label:32s} shrink {k:2d}/{len(trips)}  observed delta ${obs:+8.2f}   random-shrink mean ${null.mean():+8.2f}  "
          f"p(random >= observed) = {(null >= obs).mean():.4f}")
