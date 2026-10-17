"""
Extends dual_stoch_feature_exploration.py with CANDLE-PATTERN features
at the exact cross bar, per direct request. Same methodology: IS-only
correlation against each real trade's actual outcome, on the best
construction so far (dual_stoch_atr_target_test.py). Any feature found
here that looks real gets built into an actual filter and confirmed
OOS before being treated as a result, same as the dip_depth/gap_later
filter already tested (which came back flat OOS, %PF=1.011).

New features, all measured at the signal bar i itself (the candle
where the cross happened):
  - rejection_wick: the wick ON THE TRADE'S SIDE (lower wick for a
    buy - "price pushed down into the zone and got rejected", upper
    wick for a sell), as a fraction of the candle's full range - the
    classic hammer/shooting-star rejection shape.
  - opposite_wick: the wick on the OTHER side, for comparison - a
    rejection candle should have a small opposite wick, not just a
    large rejection wick.
  - body_ratio: |close-open| / range - a big-bodied candle vs a
    small-bodied/doji-like one.
  - candle_aligned: whether the signal candle itself closed in the
    trade's direction (bullish candle for a buy, bearish for a sell) -
    1/0, not a continuous feature, reported as a two-group split
    rather than quintiles.
  - candle_range_atr: the signal candle's own high-low range relative
    to ATR - was it an unusually large/volatile bar, or an ordinary
    one.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import load_m15
from vwap_open_scenarios_test import wilder_atr
from dual_stoch_atr_target_test import build_trades_atr_target
from dual_stoch_feature_exploration import report_feature


if __name__ == "__main__":
    df, point = load_m15("GOLD")
    n = len(df)
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    print(f"GOLD M15 IN-SAMPLE only: {df_is['time'].iloc[0]} .. {df_is['time'].iloc[-1]}")

    open_ = df_is["open"].values
    high = df_is["high"].values
    low = df_is["low"].values
    close = df_is["close"].values
    atr = wilder_atr(high, low, close, 14)

    trades = build_trades_atr_target(df_is, point)
    print(f"Total trades: {len(trades)}")
    print(f"Baseline avg pnl%: {100*np.mean([t['pnl_pct'] for t in trades]):.4f}%   "
          f"win rate: {100*np.mean([t['pnl_pct']>0 for t in trades]):.1f}%")

    rows = []
    for t in trades:
        i = t["entry_i"]
        direction = t["dir"]
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        o, h, l, c = open_[i], high[i], low[i], close[i]
        rng = h - l
        if rng <= 0:
            continue
        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)
        body = abs(c - o)
        rejection_wick = (lower_wick if direction > 0 else upper_wick) / rng
        opposite_wick = (upper_wick if direction > 0 else lower_wick) / rng
        body_ratio = body / rng
        candle_aligned = 1 if ((c > o) if direction > 0 else (c < o)) else 0
        candle_range_atr = rng / atr[i]
        rows.append(dict(rejection_wick=rejection_wick, opposite_wick=opposite_wick,
                          body_ratio=body_ratio, candle_aligned=candle_aligned,
                          candle_range_atr=candle_range_atr, pnl_pct=t["pnl_pct"]))

    dfc = pd.DataFrame(rows)
    print(f"\n{'='*100}\nCANDLE-PATTERN FEATURE BREAKDOWN (quintiles, target = realized trade pnl%)\n{'='*100}")
    for feat in ["rejection_wick", "opposite_wick", "body_ratio", "candle_range_atr"]:
        report_feature(dfc, feat)

    print(f"\n{'='*100}\nSIGNAL CANDLE ALIGNED WITH TRADE DIRECTION (binary)\n{'='*100}")
    aligned = dfc[dfc["candle_aligned"] == 1]["pnl_pct"]
    not_aligned = dfc[dfc["candle_aligned"] == 0]["pnl_pct"]
    print(f"  aligned (bullish candle on a buy / bearish on a sell): avg={100*aligned.mean():.3f}%  n={len(aligned)}")
    print(f"  NOT aligned (candle closed against the trade direction): avg={100*not_aligned.mean():.3f}%  n={len(not_aligned)}")
