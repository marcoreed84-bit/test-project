//+------------------------------------------------------------------+
//|                                        FVG_Liquidity_Zones.mq5    |
//|  Standalone indicator - Fair Value Gaps + equal-high/low          |
//|  liquidity zones. Per direct request: each with its own colour,   |
//|  lightly shaded while unfilled, and a brighter "filled" colour     |
//|  once price comes back and either rejects (bounces off) or        |
//|  invalidates (closes fully through) the zone - either way counts  |
//|  as "filled" here, there is no separate third colour for which    |
//|  of the two happened, just unfilled vs filled.                    |
//|                                                                    |
//|  Deliberately visual-only: no buy/sell arrows, no alerts, no SL/  |
//|  TP lines - that's TradePanel_EA's own FVG/Liquidity overlay       |
//|  (ComputeFvgSignals/ComputeLiquiditySignals), which this does NOT  |
//|  touch or duplicate. This file only draws the zones themselves.   |
//|                                                                    |
//|  Timeframe-flip safety: unlike Important_SR_Levels' H4/Daily/      |
//|  Weekly layers (which scan a FIXED higher timeframe regardless of  |
//|  the chart's own period, and so must NOT rescan on a plain         |
//|  timeframe flip - see that file's own v1.26 fix), FVGs and         |
//|  liquidity pivots are defined entirely in terms of the CHART's own |
//|  bars - a different timeframe genuinely means different zones, so  |
//|  a full rescan on reinit (which MT5 triggers on every timeframe    |
//|  switch) is CORRECT here, not wasted work. What matters is that    |
//|  the rescan itself is cheap and bounded - see InpScanLookbackDays  |
//|  below, and the comment on TradePanel_EA's own v2.21 fix (a real,  |
//|  shipped freeze bug from an unbounded FVG backfill) for exactly    |
//|  the failure mode this is built to avoid from the start.           |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property link      ""
#property version   "1.01"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== Fair Value Gaps ==="
input bool     InpShowFVG          = true;
input color    InpFvgBullCol       = C'25,55,40';    // light-shaded, UNFILLED bullish FVG
input color    InpFvgBearCol       = C'55,25,25';    // light-shaded, UNFILLED bearish FVG
input color    InpFvgBullFilledCol = C'0,120,60';     // FILLED (rejected or invalidated) - brighter
input color    InpFvgBearFilledCol = C'150,40,40';
input int      InpFvgMaxZones      = 150;             // cap on how many FVGs (filled+unfilled) are
                                                       // tracked/drawn at once - oldest FILLED zones are
                                                       // evicted first when over cap; unfilled zones are
                                                       // only evicted if every single tracked zone is
                                                       // unfilled and the cap is still exceeded.
input int      InpFvgMaxAgeDays    = 14;              // FILLED FVGs older than this are pruned from the
                                                       // chart (0 = never prune by age). UNFILLED FVGs are
                                                       // never pruned by age - only by InpFvgMaxZones.

input group "=== Liquidity (equal highs / equal lows) ==="
input bool     InpShowLiquidity    = true;
input int      InpLiqPivotWindow   = 5;               // fractal window - bars needed on each side for a
                                                       // swing high/low to confirm
input double   InpLiqTolATR        = 0.25;            // two pivots within this many ATR of each other
                                                       // count as "equal" (real markets rarely print exact
                                                       // ties)
input double   InpLiqZoneThickATR  = 0.15;            // visual thickness of a liquidity zone (ATR-scaled) -
                                                       // equal highs/lows are a price LEVEL, not a range, so
                                                       // this just makes the zone visible as a thin band
                                                       // around that level rather than a 1px line
input int      InpLiqLookbackBars  = 4000;            // how far back a new pivot can look for a matching
                                                       // partner to pair into a zone - per direct note,
                                                       // liquidity can sit unswept for days before being
                                                       // taken, so this is generous by default
input color    InpLiqBullCol       = C'15,40,65';     // light-shaded, UNSWEPT buy-side (equal lows)
input color    InpLiqBearCol       = C'65,40,15';     // light-shaded, UNSWEPT sell-side (equal highs)
input color    InpLiqBullFilledCol = C'0,100,180';    // SWEPT - brighter
input color    InpLiqBearFilledCol = C'200,120,0';
input int      InpLiqMaxZones      = 150;
input int      InpLiqMaxAgeDays    = 0;               // FILLED (swept) liquidity zones older than this are
                                                       // pruned (0 = never prune by age - a sweep can stay
                                                       // relevant a long time). UNFILLED zones are never
                                                       // pruned by age either way, only by InpLiqMaxZones.

input group "=== General ==="
input int      InpScanLookbackDays = 60;              // how far back the initial backfill scans, in days
                                                       // of the CHART's own timeframe - bounds the one-time
                                                       // cost on attach/reinit so it can never freeze the
                                                       // terminal regardless of how much history exists.
                                                       // TradePanel_EA's own v2.21 fix exists because an
                                                       // earlier FVG overlay in this project skipped exactly
                                                       // this cap and scanned 100,000+ bars unbounded.
input int      InpAtrPeriod        = 14;

//+------------------------------------------------------------------+
struct Zone
  {
   double   top;
   double   bottom;
   bool     bullish;
   bool     filled;
   datetime startTime;
   datetime filledTime;   // 0 while still active/unfilled
   string   rectName;
  };

Zone     g_fvgZones[];
Zone     g_liqZones[];

//--- liquidity pivot store - confirmed swing highs/lows waiting to be
//--- paired with a future equal pivot, or already consumed into a zone
struct LiqPivot
  {
   datetime t;
   double   price;
   bool     isHigh;    // true = swing high (sell-side liquidity candidate), false = swing low
   bool     used;       // already paired into a zone - the LATER pivot in a pair stays reusable
                        // (see FindLiquidityPair's own comment), only the EARLIER one is retired
  };
LiqPivot g_liqPivots[];

string   g_pfxFvg = "FVGZ_";
string   g_pfxLiq = "LIQZ_";

int      g_atrHandle = INVALID_HANDLE;
datetime g_lastBarTime = 0;
ulong    g_lastDrawMs  = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpLiqPivotWindow <= 0)
     {
      Print("FVG_Liquidity_Zones: InpLiqPivotWindow must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpAtrPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("FVG_Liquidity_Zones: failed to create ATR handle.");
      return(INIT_FAILED);
     }
   ArrayResize(g_fvgZones, 0);
   ArrayResize(g_liqZones, 0);
   ArrayResize(g_liqPivots, 0);
   g_lastBarTime = 0;
   g_lastDrawMs  = 0;
   PrintFormat("FVG_Liquidity_Zones v1.01 OnInit: %s %s  FVG=%s  Liquidity=%s  scanLookback=%dd",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpShowFVG ? "on" : "off", InpShowLiquidity ? "on" : "off", InpScanLookbackDays);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_pfxFvg);
   ObjectsDeleteAll(0, g_pfxLiq);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
void DrawZoneRect(const string nm, const datetime t1, const datetime t2, const double top,
                   const double bottom, const color col)
  {
   if(ObjectFind(0, nm) < 0)
     {
      if(!ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, top, t2, bottom))
        {
         PrintFormat("FVG_Liquidity_Zones: ObjectCreate FAILED for %s - error %d", nm, GetLastError());
         return;
        }
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, true);
      ObjectSetInteger(0, nm, OBJPROP_FILL, true);
      ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
     }
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectMove(0, nm, 0, t1, top);
   ObjectMove(0, nm, 1, t2, bottom);
  }

//+------------------------------------------------------------------+
//| Either resolution (bounce back out, or close fully through) marks |
//| the zone FILLED - see this file's own header comment for why both |
//| collapse to one state instead of two different colours.           |
//+------------------------------------------------------------------+
bool ResolveZone(Zone &z, const double cBar, const double hBar, const double lBar)
  {
   if(z.filled) return false;
   if(z.bullish)
     {
      if(lBar > z.top) return false;               // hasn't reached the zone yet
      if(cBar < z.bottom || cBar > z.top) { z.filled = true; return true; }
     }
   else
     {
      if(hBar < z.bottom) return false;
      if(cBar > z.top || cBar < z.bottom) { z.filled = true; return true; }
     }
   return false;   // wicked in, closed still inside - still being tested
  }

//+------------------------------------------------------------------+
void PruneZones(Zone &zones[], const int maxZones, const int maxAgeDays, const datetime lastBarTime)
  {
   //--- age-based prune: FILLED zones only, UNFILLED zones never age out
   if(maxAgeDays > 0)
     {
      datetime cutoff = lastBarTime - (datetime)((long)maxAgeDays * 86400);
      for(int k = ArraySize(zones) - 1; k >= 0; k--)
        {
         if(zones[k].filled && zones[k].filledTime > 0 && zones[k].filledTime < cutoff)
           {
            ObjectDelete(0, zones[k].rectName);
            zones[k] = zones[ArraySize(zones) - 1];
            ArrayResize(zones, ArraySize(zones) - 1);
           }
        }
     }
   //--- count-based prune: evict oldest FILLED first; only touch an
   //--- unfilled zone if literally everything tracked is unfilled and
   //--- still over the cap (better to lose the oldest still-active zone
   //--- than to silently stop tracking new ones forever)
   while(ArraySize(zones) > maxZones)
     {
      int oldest = -1;
      for(int k = 0; k < ArraySize(zones); k++)
         if(zones[k].filled && (oldest < 0 || zones[k].startTime < zones[oldest].startTime)) oldest = k;
      if(oldest < 0)
        {
         for(int k = 0; k < ArraySize(zones); k++)
            if(oldest < 0 || zones[k].startTime < zones[oldest].startTime) oldest = k;
        }
      if(oldest < 0) break;
      ObjectDelete(0, zones[oldest].rectName);
      zones[oldest] = zones[ArraySize(zones) - 1];
      ArrayResize(zones, ArraySize(zones) - 1);
     }
  }

//+------------------------------------------------------------------+
//| Pairs a freshly-confirmed pivot against the nearest unused same-   |
//| type pivot within InpLiqLookbackBars/InpLiqTolATR. Only the        |
//| EARLIER pivot of a pair is retired (used=true) - the later one     |
//| stays available so a third, later equal high/low can still pair   |
//| with it and form its own zone, instead of every pivot only ever    |
//| being usable once.                                                 |
//+------------------------------------------------------------------+
int FindLiquidityPair(const bool isHigh, const double price, const datetime t, const double tolerance)
  {
   int best = -1;
   double bestDist = DBL_MAX;
   for(int k = ArraySize(g_liqPivots) - 1; k >= 0; k--)
     {
      if(g_liqPivots[k].used || g_liqPivots[k].isHigh != isHigh) continue;
      if(g_liqPivots[k].t >= t) continue;
      double d = MathAbs(g_liqPivots[k].price - price);
      if(d <= tolerance && d < bestDist) { bestDist = d; best = k; }
     }
   return best;
  }

//+------------------------------------------------------------------+
//| Main incremental scan - processes bars [from, n-1] against every   |
//| active zone (fill check), then looks for new FVGs/liquidity pairs  |
//| on each bar. Only ever called with a bounded, already-bar-gated    |
//| range (see OnCalculate) - never the whole chart history at once.   |
//+------------------------------------------------------------------+
//--- v1.01 FIX (Opus audit): `atr[]` here is offset-aligned to `from`
//--- (atr[0] == bar `from`), NOT a full rates_total-sized array indexed
//--- by absolute bar number - see the call site's own comment for why.
void ProcessBars(const int from, const int n, const datetime &time[], const double &high[],
                  const double &low[], const double &close[], const double &atr[])
  {
   int w = InpLiqPivotWindow;
   //--- v1.01 FIX (Opus audit - real bugs): this loop used to run up to
   //--- i<n, which lets i reach the STILL-FORMING bar (n-1) - a gap
   //--- could be created from a forming bar's momentary high/low (never
   //--- undone if the bar closed differently), and far worse, the very
   //--- next tick re-checked that SAME zone's fill condition against
   //--- its own creation bar and found `close > top` true almost every
   //--- time (the zone's own top/bottom ARE that bar's low/high), so
   //--- nearly every live FVG flipped to "filled" about one tick after
   //--- appearing. Combined with no bar-change gate at all (this file
   //--- never had one, unlike the other new indicators), the same
   //--- forming bar's gap got re-created as a FRESH duplicate zone on
   //--- every single tick too. Bounding the loop to i<n-1-w (excluding
   //--- the forming bar, with the margin the liquidity side's i+w
   //--- lookahead needs) fixes both: no decision is ever made from an
   //--- unclosed bar, and on a tick where nothing new has closed, `from`
   //--- (computed in OnCalculate from prev_calculated) already equals
   //--- this same upper bound, so the loop naturally runs zero times -
   //--- same self-gating pattern as this project's other new indicators.
   for(int i = MathMax(from, MathMax(2, w)); i < n - 1 - w; i++)
     {
      datetime t_i = time[i];

      if(InpShowFVG)
        {
         for(int zi = 0; zi < ArraySize(g_fvgZones); zi++)
            if(ResolveZone(g_fvgZones[zi], close[i], high[i], low[i]))
              {
               g_fvgZones[zi].filledTime = t_i;
               DrawZoneRect(g_fvgZones[zi].rectName, g_fvgZones[zi].startTime, t_i,
                            g_fvgZones[zi].top, g_fvgZones[zi].bottom,
                            g_fvgZones[zi].bullish ? InpFvgBullFilledCol : InpFvgBearFilledCol);
              }

         bool bullGap = low[i] > high[i - 2];
         bool bearGap = high[i] < low[i - 2];
         if(bullGap || bearGap)
           {
            int zi = ArraySize(g_fvgZones);
            ArrayResize(g_fvgZones, zi + 1);
            g_fvgZones[zi].top        = bullGap ? low[i] : low[i - 2];
            g_fvgZones[zi].bottom     = bullGap ? high[i - 2] : high[i];
            g_fvgZones[zi].bullish    = bullGap;
            g_fvgZones[zi].startTime  = time[i - 1];
            g_fvgZones[zi].filled     = false;
            g_fvgZones[zi].filledTime = 0;
            g_fvgZones[zi].rectName   = g_pfxFvg + (bullGap ? "bull_" : "bear_") + IntegerToString((long)t_i);
            DrawZoneRect(g_fvgZones[zi].rectName, g_fvgZones[zi].startTime, t_i,
                         g_fvgZones[zi].top, g_fvgZones[zi].bottom,
                         bullGap ? InpFvgBullCol : InpFvgBearCol);
            //--- v1.01 FIX (Opus audit, real bug - same shape as
            //--- TradePanel_EA's own v2.21 freeze): pruning used to only
            //--- run once, AFTER this whole function returned - during a
            //--- many-day backfill every FVG ever found stayed in the
            //--- array the whole time, and every later bar's fill-check
            //--- loop scanned all of them, filled ones included. Enforced
            //--- here too so the array can never grow past InpFvgMaxZones
            //--- mid-backfill, bounding the real cost to O(bars x
            //--- InpFvgMaxZones) instead of O(bars x every zone ever seen).
            if(ArraySize(g_fvgZones) > InpFvgMaxZones) PruneZones(g_fvgZones, InpFvgMaxZones, InpFvgMaxAgeDays, t_i);
           }
        }

      if(InpShowLiquidity && i >= w && i < n - w)
        {
         for(int zi = 0; zi < ArraySize(g_liqZones); zi++)
            if(ResolveZone(g_liqZones[zi], close[i], high[i], low[i]))
              {
               g_liqZones[zi].filledTime = t_i;
               DrawZoneRect(g_liqZones[zi].rectName, g_liqZones[zi].startTime, t_i,
                            g_liqZones[zi].top, g_liqZones[zi].bottom,
                            g_liqZones[zi].bullish ? InpLiqBullFilledCol : InpLiqBearFilledCol);
              }

         bool isPeak = true, isTrough = true;
         for(int k = 1; k <= w; k++)
           {
            if(high[i] < high[i - k] || high[i] <= high[i + k]) isPeak = false;
            if(low[i]  > low[i - k]  || low[i]  >= low[i + k])  isTrough = false;
            if(!isPeak && !isTrough) break;
           }
         double atrHere = atr[i - from];
         double tolerance = (atrHere != EMPTY_VALUE && atrHere > 0.0) ? InpLiqTolATR * atrHere : 0.0;
         double thickness = (atrHere != EMPTY_VALUE && atrHere > 0.0) ? InpLiqZoneThickATR * atrHere : 0.0;
         if(tolerance > 0.0 && (isPeak || isTrough))
           {
            datetime pivotTime = time[i];
            double pivotPrice = isPeak ? high[i] : low[i];
            int pair = FindLiquidityPair(isPeak, pivotPrice, pivotTime, tolerance);
            if(pair >= 0)
              {
               g_liqPivots[pair].used = true;
               double top    = MathMax(pivotPrice, g_liqPivots[pair].price) + thickness;
               double bottom = MathMin(pivotPrice, g_liqPivots[pair].price) - thickness;
               int zi = ArraySize(g_liqZones);
               ArrayResize(g_liqZones, zi + 1);
               g_liqZones[zi].top        = top;
               g_liqZones[zi].bottom     = bottom;
               //--- equal HIGHS = resting sell-side liquidity ABOVE price - drawn
               //--- with the "bear"/resistance colour; equal LOWS = buy-side
               //--- liquidity below, "bull"/support colour - matches this
               //--- project's existing support=bull/resistance=bear convention.
               g_liqZones[zi].bullish    = !isPeak;
               g_liqZones[zi].filled     = false;
               g_liqZones[zi].filledTime = 0;
               g_liqZones[zi].rectName   = g_pfxLiq + (isPeak ? "sell_" : "buy_") + IntegerToString((long)pivotTime);
               DrawZoneRect(g_liqZones[zi].rectName, g_liqPivots[pair].t, pivotTime, top, bottom,
                            isPeak ? InpLiqBearCol : InpLiqBullCol);
               //--- v1.01 FIX (Opus audit) - same reasoning as the FVG
               //--- side's own fix just above.
               if(ArraySize(g_liqZones) > InpLiqMaxZones) PruneZones(g_liqZones, InpLiqMaxZones, InpLiqMaxAgeDays, pivotTime);
              }
            int pIdx = ArraySize(g_liqPivots);
            ArrayResize(g_liqPivots, pIdx + 1);
            g_liqPivots[pIdx].t      = pivotTime;
            g_liqPivots[pIdx].price  = pivotPrice;
            g_liqPivots[pIdx].isHigh = isPeak;
            g_liqPivots[pIdx].used   = false;
           }
        }
     }

   //--- trim the pivot store itself so it can't grow forever on a
   //--- chart that's been running for a very long time - lookback
   //--- window plus a safety margin is all that can ever be matched
   //--- against anyway (see FindLiquidityPair's own t < lookback check)
   int pivotFloor = n - InpLiqLookbackBars - 2 * w - 50;
   if(pivotFloor > 0)
     {
      int keepFrom = 0;
      while(keepFrom < ArraySize(g_liqPivots) && g_liqPivots[keepFrom].t < time[MathMax(0, pivotFloor)]) keepFrom++;
      if(keepFrom > 0)
        {
         int remain = ArraySize(g_liqPivots) - keepFrom;
         for(int k = 0; k < remain; k++) g_liqPivots[k] = g_liqPivots[k + keepFrom];
         ArrayResize(g_liqPivots, remain);
        }
     }
  }

//+------------------------------------------------------------------+
//| Extend every still-ACTIVE zone's right edge to the current time -  |
//| throttled to once/sec (same convention as Important_SR_Levels'     |
//| own right-edge refresh) so this never becomes a per-tick cost      |
//| across however many zones happen to be tracked.                    |
//+------------------------------------------------------------------+
void ExtendActiveZones(Zone &zones[], const datetime nowTime)
  {
   for(int k = 0; k < ArraySize(zones); k++)
      if(!zones[k].filled)
         ObjectMove(0, zones[k].rectName, 1, nowTime, zones[k].bottom);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   int w = InpLiqPivotWindow;
   int minBars = 2 * w + 10;
   if(rates_total < minBars) return(0);

   //--- bound the one-time backfill cost on attach/reinit - see
   //--- InpScanLookbackDays' own comment and TradePanel_EA's v2.21 fix
   //--- for exactly why this cap exists.
   int lookbackBars = (InpScanLookbackDays > 0)
                       ? (int)((long)InpScanLookbackDays * 86400 / PeriodSeconds(PERIOD_CURRENT)) + minBars
                       : rates_total;
   int backfillFrom = MathMax(w, rates_total - lookbackBars);

   int from;
   if(prev_calculated <= 0)
     {
      ObjectsDeleteAll(0, g_pfxFvg);
      ObjectsDeleteAll(0, g_pfxLiq);
      ArrayResize(g_fvgZones, 0);
      ArrayResize(g_liqZones, 0);
      ArrayResize(g_liqPivots, 0);
      from = backfillFrom;
     }
   else
      from = MathMax(w, prev_calculated - 1 - w);   // re-check the last few bars a late-confirming pivot needed

   if(from >= rates_total) return(rates_total);

   double atr[];
   ArraySetAsSeries(atr, true);
   int atrCount = rates_total - from;
   if(CopyBuffer(g_atrHandle, 0, 0, atrCount, atr) < atrCount)   // shift 0 = newest bar = rates_total-1
     {
      //--- ATR not ready yet (routine right after attach) - report
      //--- "not handled", MT5 retries with prev_calculated still 0
      return(0);
     }
   //--- atr[] above was copied as series (atr[0]=newest); ProcessBars
   //--- indexes forward like time[]/high[]/low[] (non-series), so build
   //--- a forward-aligned array matching time[from..rates_total-1].
   //--- v1.01 FIX (Opus audit, real bug): this used to then also wrap
   //--- atrFwd into a SEPARATE rates_total-sized array just so ProcessBars
   //--- could index it by absolute bar number - an O(history) allocation
   //--- EVERY call (every tick, since this runs even on a self-gated
   //--- no-op call), the same cost-scaling shape as the old TradePanel
   //--- v2.21 freeze on a large chart history. ProcessBars now indexes
   //--- atrFwd directly as atr[i-from] instead, so only the small,
   //--- bounded atrCount-sized array is ever allocated.
   double atrFwd[];
   ArrayResize(atrFwd, atrCount);
   for(int k = 0; k < atrCount; k++) atrFwd[k] = atr[atrCount - 1 - k];

   ProcessBars(from, rates_total, time, high, low, close, atrFwd);

   //--- v1.00: right-edge extend of active zones, throttled to once/sec -
   //--- same reasoning as Important_SR_Levels' RefreshRightEdgeLabels.
   if(GetTickCount64() - g_lastDrawMs >= 1000)
     {
      g_lastDrawMs = GetTickCount64();
      datetime nowTime = time[rates_total - 1];
      if(InpShowFVG)       ExtendActiveZones(g_fvgZones, nowTime);
      if(InpShowLiquidity) ExtendActiveZones(g_liqZones, nowTime);
      PruneZones(g_fvgZones, InpFvgMaxZones, InpFvgMaxAgeDays, nowTime);
      PruneZones(g_liqZones, InpLiqMaxZones, InpLiqMaxAgeDays, nowTime);
     }

   return(rates_total);
  }
