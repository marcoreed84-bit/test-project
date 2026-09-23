"""Threshold / lot sweep for 'reduced size below a risk-% threshold' vs
'skip below the threshold', both through the full sequential sim."""
import sys
sys.path.insert(0, "/home/user/test-project/research/msg")
from search import *  # noqa


def small_size(th, lots_small):
    return lambda ctx: lots_small if ctx["risk_pct"] < th else 0.03


def skip_small(th):
    return lambda ctx: ctx["risk_pct"] < th


if __name__ == "__main__":
    bars = load_bars()
    for sym in ("GOLD", "GOLD#"):
        print(f"=== {sym}")
        for th in (0.18, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.34):
            show(f"size 0.01 if risk%<{th:.2f}", evaluate(bars, dict(size_fn=small_size(th, 0.01)), sym))
        for th in (0.22, 0.26, 0.30):
            show(f"size 0.02 if risk%<{th:.2f}", evaluate(bars, dict(size_fn=small_size(th, 0.02)), sym))
        for th in (0.22, 0.26, 0.30):
            show(f"SKIP if risk%<{th:.2f}", evaluate(bars, dict(entry_filter=skip_small(th)), sym))
