//+------------------------------------------------------------------+
//|                                   VolumeProfile_Session.mq5      |
//|  Session (daily) volume profile - per direct request, as its own |
//|  standalone indicator. v1.07: InpDaysToShow default changed 3->1  |
//|  - a multi-day blended window was NOT what other traders mean by  |
//|  "session volume profile" (e.g. TradingView's own Session Volume  |
//|  Profile tool, and standard retail/prop usage generally): one      |
//|  profile per SESSION, building live from that session's own open,  |
//|  not several calendar days blended into one POC/VA.                 |
//|                                                                   |
//|  v1.08: per direct request/screenshot - shows BOTH the current,     |
//|  still-live session AND the previous, fully completed session at    |
//|  once, as two separate profiles drawn side by side in two distinct   |
//|  colour families so they're never confused for one blended window.   |
//|  The "today" column is live (today's bars so far); the "previous     |
//|  day" column is a genuinely FROZEN snapshot of yesterday's full,      |
//|  completed session - it never changes once today starts, which is     |
//|  exactly what makes it useful as a fixed reference level.              |
//|  InpDaysToShow still controls how many days feed the TODAY column      |
//|  (default 1 = just today) - raise it only if you deliberately want      |
//|  several days blended into that one live column; the previous-day       |
//|  column is always exactly one full completed calendar day, separately.  |
//|                                                                   |
//|  Both profiles drawn entirely in the BLANK SPACE to the right of    |
//|  the most recent candle - per direct request/screenshot, must sit   |
//|  there, not overlap any candles. Anchored at (last bar time + 1     |
//|  bar) for today, and one column further right (InpMaxBarWidthBars + |
//|  InpColumnGapBars bars) for the previous day - scroll/zoom moves     |
//|  both exactly like any other chart object anchored by time, same     |
//|  as everything else in this project's indicators.                    |
//|                                                                   |
//|  Buckets: each window's own [low, high] range split into InpBuckets |
//|  equal-width price buckets; each bar's volume is split evenly       |
//|  across the buckets its own [low, high] touches (same distribution   |
//|  method already used and tested in this project's                    |
//|  volume_profile_poc_test.py research script). One horizontal         |
//|  OBJ_RECTANGLE per non-empty bucket, width proportional to that       |
//|  bucket's volume share of that window's own busiest bucket (POC -      |
//|  Point of Control), drawn in its own distinct colour. An optional       |
//|  dotted/dashed line extends each level price back across the visible    |
//|  chart (InpShowPocLine/InpShowValueArea) so it is easy to read against   |
//|  the actual candles despite the profiles themselves sitting off to the   |
//|  side.                                                                    |
//|                                                                   |
//|  CAVEAT (same as every other volume-based construction in this   |
//|  project - see CLAUDE.md and volume_profile_poc_test.py's own     |
//|  header): this broker's GOLD/SILVER real_volume is confirmed 0,   |
//|  so tick_volume (a trade-COUNT proxy, not real traded volume) is   |
//|  the only usable source - a materially weaker signal of where real |
//|  volume actually sat than a real exchange instrument's own volume   |
//|  profile would be. InpUseRealVolume exists in case that ever        |
//|  changes on a different symbol/broker, defaults OFF.                 |
//|                                                                   |
//|  STATUS: visual reference only. "Prior-day volume-profile POC      |
//|  touch-reject" was tested as a TradePanel signal (2026-10-26, GOLD |
//|  M5, real TP/SL, walk-forward split, random-timing null) and        |
//|  FAILED: OOS PF 0.969, net -379.9, p(PF)=0.52, p(net)=0.58 -         |
//|  indistinguishable from random entry timing. NOT implemented as a    |
//|  signal here or anywhere - this indicator draws the profiles for      |
//|  discretionary/visual judgement only, it does not claim the levels     |
//|  it shows have any backtested predictive edge.                          |
//+------------------------------------------------------------------+
#property copyright "test-project"
#property version   "1.12"
#property indicator_chart_window
#property indicator_plots 0

input group "=== Today (live session) ==="
input int    InpDaysToShow       = 1;       // how many days feed the TODAY column (1 = just today,
                                             // live from this session's own open - the standard
                                             // construction). Raise only if you deliberately want
                                             // several days blended into THIS column.
input color  InpBarColor         = C'10,80,140';     // dim neon blue (same family as InpThemeBullCol
                                             // in TradePanel_EA.mq5) - blends with the blue/white theme.
input color  InpPocColor         = clrWhite;         // bright white - today's most important level
                                             // reads as the brightest thing in this column.
input color  InpPocLineColor     = C'0,150,255';     // exact neon blue (InpThemeBullCol).
input color  InpVahValColor      = C'120,200,255';   // v1.09 FIX (Opus audit, real compile error): this
                                             // input was referenced by the today DrawProfile() call but
                                             // never declared after the v1.08 refactor split the colour
                                             // inputs into today/prev groups - "undeclared identifier",
                                             // would not compile. Light neon blue/cyan, same family as
                                             // the Leg file's own InpVahValColor.

input group "=== Previous day (frozen, completed session) ==="
input bool   InpShowPrevDay      = true;    // v1.08: a second, independent profile for the full,
                                             // already-completed previous calendar day - frozen, never
                                             // changes once today starts, unlike the live today column.
input int    InpColumnGapBars    = 2;       // blank bars between the two columns so they never touch
input color  InpPrevBarColor     = C'140,70,10';     // dim neon amber/orange - a distinct colour family
                                             // from today's blue, so the two sessions are never confused.
input color  InpPrevPocColor     = C'255,160,60';    // bright neon orange - previous day's POC.
input color  InpPrevPocLineColor = C'255,140,0';     // exact neon orange.
input color  InpPrevVahValColor  = C'255,190,130';   // light neon amber - previous day's VAH/VAL.

input group "=== Volume profile settings (shared by both columns) ==="
input ENUM_TIMEFRAMES InpSourceTF = PERIOD_M1;   // v1.11: the profile's own high/low/volume data is
                                             // ALWAYS pulled from this ONE fixed timeframe, independent
                                             // of whatever timeframe the chart itself is on - per direct
                                             // report ("whether M5 or M15, the POC should be at the same
                                             // level"), building from the chart's own (coarser) bars let
                                             // the POC genuinely shift depending on which chart you
                                             // viewed it from. M1 gives the finest practical attribution
                                             // of volume to price without needing tick data.
input int    InpBuckets          = 30;      // price buckets - more buckets = finer resolution,
                                             // noisier-looking histogram
input bool   InpUseRealVolume    = false;   // GOLD/SILVER real_volume is 0 on this broker's feed
                                             // (confirmed this project) - leave off unless you have
                                             // verified your own symbol/broker actually populates it
input int    InpMaxBarWidthBars  = 10;      // the busiest bucket's rectangle extends this many bars
                                             // rightward from its own column's anchor; every other
                                             // bucket scales proportionally to its own volume share.
input int    InpLeadingGapBars   = 10;      // v1.10: blank bars of empty space between the last live
                                             // candle and the start of the today column - per direct
                                             // request, so the profiles don't sit flush against price
                                             // action. The previous-day column is offset relative to
                                             // today's own anchor, so it moves with this automatically.
input bool   InpAutoRightMargin  = true;    // MT5 clips any object past the chart's own right-margin
                                             // ("shift") space, a SEPARATE setting from anything this
                                             // indicator draws. When true, claims enough room for BOTH
                                             // columns automatically (only ever INCREASES the margin,
                                             // never shrinks a larger one you already have set).
input double InpBucketGapFrac    = 0.25;    // each bucket's rectangle only fills this fraction of its
                                             // own vertical slot (centered) - 0 = no gap (solid look)
input bool   InpShowPocLine      = true;    // a line at each column's own POC price, extended across
                                             // the chart so you can see the level against price history
input bool   InpPocLineRayLeft   = true;    // extend POC/VA lines ALL the way across the visible chart
                                             // to the left (MT5's own OBJPROP_RAY_LEFT) instead of
                                             // stopping InpPocLineBackBars bars behind the last candle.
input int    InpPocLineBackBars  = 150;     // only used when InpPocLineRayLeft is false

input group "=== Value Area (POC +/- the price range holding InpVAPercent of each column's volume) ==="
input bool   InpShowValueArea    = true;
input double InpVAPercent        = 70.0;    // standard volume-profile convention

#define VP_PFX "VPS_"

//+------------------------------------------------------------------+
//| claims enough right-margin ("shift") chart space for both profile  |
//| columns to actually fit without MT5 clipping them behind the price  |
//| column - a SEPARATE chart setting from anything drawn here.          |
//| CHART_SHIFT_SIZE is a PERCENTAGE of the chart's own width, so there   |
//| is no exact bar->percent conversion - uses a generous fixed value      |
//| instead and only ever INCREASES the margin, never shrinks one you       |
//| already had set bigger for your own reasons.                             |
//+------------------------------------------------------------------+
void EnsureRightMargin()
  {
   if(!InpAutoRightMargin) return;
   if(!(bool)ChartGetInteger(0, CHART_SHIFT))
      ChartSetInteger(0, CHART_SHIFT, true);
   double cur = ChartGetDouble(0, CHART_SHIFT_SIZE);
   //--- v1.10: base percentage (two columns need materially more room than
   //--- one) plus a rough per-gap-bar allowance for InpLeadingGapBars -
   //--- still just a generous estimate, same as the base values always
   //--- were, not an exact bar->percent conversion.
   double want = (InpShowPrevDay ? 45.0 : 25.0) + InpLeadingGapBars * 0.5;
   if(cur < want)
      ChartSetDouble(0, CHART_SHIFT_SIZE, want);
  }

//+------------------------------------------------------------------+
//| Deletes every object belonging to one profile column (used both to |
//| clean up a column that's been toggled off, and as the early-return  |
//| path when a window has no valid range/volume - so a stale profile    |
//| never sits on screen with no indication it's out of date).            |
//+------------------------------------------------------------------+
void DeleteProfileObjects(const string prefix)
  {
   for(int b = 0; b < 200; b++)
     {
      string nm = prefix + "bucket_" + IntegerToString(b);
      if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
     }
   ObjectDelete(0, prefix + "pocline");
   ObjectDelete(0, prefix + "vah");
   ObjectDelete(0, prefix + "val");
  }

//+------------------------------------------------------------------+
//| Builds and draws ONE profile column over [start,end], anchored at  |
//| anchorTime. Used for both the live "today" column and the frozen    |
//| "previous day" column - identical bucket/POC/VA math, only the       |
//| bar range, anchor position, and colours differ between calls.         |
//+------------------------------------------------------------------+
//--- v1.11 FIX (real design bug - "whether M5 or M15, the POC should be
//--- at the same level"): the old version built the profile from the
//--- CHART'S OWN bars - on M15, each bar's volume gets smeared evenly
//--- across that bar's own (3x wider than M5) high-low range before being
//--- bucketed, which can genuinely shift which bucket ends up busiest
//--- compared to the finer M5 attribution of the exact same underlying
//--- trading. The true POC shouldn't depend on which chart you're
//--- viewing it from. Fixed by always sourcing the profile's own high/
//--- low/volume data from ONE FIXED timeframe (InpSourceTF, default M1)
//--- via Copy*() by time range, completely independent of whatever
//--- timeframe the chart itself is on - same POC/VAH/VAL regardless of
//--- chart period, only the drawing position (anchorTime/perSec, still
//--- tied to the chart's own bars) changes.
void DrawProfile(const string prefix, const datetime startTime, const datetime endTime,
                  const datetime anchorTime, const datetime &chartTime[], const int chartEnd, const int perSec,
                  const color barColor, const color pocColor, const color pocLineColor, const color vaColor)
  {
   if(endTime <= startTime) { DeleteProfileObjects(prefix); return; }

   //--- v1.12 FIX (Opus audit): separate CopyHigh/CopyLow/CopyTickVolume/
   //--- CopyRealVolume calls each independently request the same
   //--- (startTime,endTime) range - not actually bounded by each other's
   //--- result count, so a history sync landing between calls could in
   //--- principle misalign them. One CopyRates() call gives a single
   //--- atomic snapshot (guaranteed-aligned high/low/tick_volume/
   //--- real_volume together) and also removes any question about the
   //--- ternary below ever touching an unfilled array.
   MqlRates r[];
   int n = CopyRates(_Symbol, InpSourceTF, startTime, endTime, r);
   if(n <= 0) { DeleteProfileObjects(prefix); return; }
   int start = 0, end = n - 1;

   double lo = r[start].low, hi = r[start].high;
   for(int i = start; i <= end; i++)
     {
      lo = MathMin(lo, r[i].low);
      hi = MathMax(hi, r[i].high);
     }
   if(hi <= lo) { DeleteProfileObjects(prefix); return; }

   double bw = (hi - lo) / InpBuckets;
   double vol[];
   ArrayResize(vol, InpBuckets);
   ArrayInitialize(vol, 0.0);

   for(int i = start; i <= end; i++)
     {
      double v = InpUseRealVolume ? (double)r[i].real_volume : (double)r[i].tick_volume;
      if(v <= 0.0) continue;
      int b0 = (int)((r[i].low  - lo) / bw);
      int b1 = (int)((r[i].high - lo) / bw);
      b0 = (int)MathMax(0, MathMin(InpBuckets - 1, b0));
      b1 = (int)MathMax(0, MathMin(InpBuckets - 1, b1));
      if(b1 < b0) { int t = b0; b0 = b1; b1 = t; }
      int span = b1 - b0 + 1;
      double share = v / span;
      for(int b = b0; b <= b1; b++)
         vol[b] += share;
     }

   int pocBucket = 0;
   double pocVol = vol[0];
   for(int b = 1; b < InpBuckets; b++)
      if(vol[b] > pocVol) { pocVol = vol[b]; pocBucket = b; }
   if(pocVol <= 0.0) { DeleteProfileObjects(prefix); return; }

   for(int b = 0; b < InpBuckets; b++)
     {
      string nm = prefix + "bucket_" + IntegerToString(b);
      if(vol[b] <= 0.0)
        {
         ObjectDelete(0, nm);
         continue;
        }
      double gap = bw * InpBucketGapFrac * 0.5;
      double bucketLo = lo + b * bw + gap;
      double bucketHi = bucketLo + bw - 2.0 * gap;
      int widthBars = (int)MathRound(InpMaxBarWidthBars * (vol[b] / pocVol));
      if(widthBars < 1) widthBars = 1;
      datetime t1 = anchorTime;
      datetime t2 = anchorTime + (datetime)(widthBars * perSec);

      bool isPoc = (b == pocBucket);
      if(ObjectFind(0, nm) < 0)
        {
         if(!ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, bucketLo, t2, bucketHi)) continue;
         ObjectSetInteger(0, nm, OBJPROP_FILL, true);
         ObjectSetInteger(0, nm, OBJPROP_BACK, true);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
         ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
        }
      else
        {
         ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t1);
         ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, bucketLo);
         ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t2);
         ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, bucketHi);
        }
      ObjectSetInteger(0, nm, OBJPROP_COLOR, isPoc ? pocColor : barColor);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP,
                       (isPoc ? "POC " : "") + "vol=" + DoubleToString(vol[b], 0) +
                       "  [" + DoubleToString(bucketLo, _Digits) + " - " + DoubleToString(bucketHi, _Digits) + "]");
     }
   //--- clean up any leftover buckets from a previous call with more buckets than now
   for(int b = InpBuckets; b < 200; b++)
     {
      string nm = prefix + "bucket_" + IntegerToString(b);
      if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
      else break;
     }

   if(InpShowPocLine)
     {
      string pocNm = prefix + "pocline";
      double pocPrice = lo + (pocBucket + 0.5) * bw;
      datetime lineStart = InpPocLineRayLeft ? anchorTime : chartTime[(int)MathMax(0, chartEnd - InpPocLineBackBars)];
      datetime lineEnd   = anchorTime + (datetime)(InpMaxBarWidthBars * perSec);
      if(ObjectFind(0, pocNm) < 0)
        {
         ObjectCreate(0, pocNm, OBJ_TREND, 0, lineStart, pocPrice, lineEnd, pocPrice);
         ObjectSetInteger(0, pocNm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, pocNm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, pocNm, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, pocNm, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, pocNm, OBJPROP_BACK, true);
        }
      else
        {
         ObjectSetInteger(0, pocNm, OBJPROP_TIME, 0, lineStart);
         ObjectSetDouble (0, pocNm, OBJPROP_PRICE, 0, pocPrice);
         ObjectSetInteger(0, pocNm, OBJPROP_TIME, 1, lineEnd);
         ObjectSetDouble (0, pocNm, OBJPROP_PRICE, 1, pocPrice);
        }
      ObjectSetInteger(0, pocNm, OBJPROP_RAY_LEFT, InpPocLineRayLeft);
      ObjectSetInteger(0, pocNm, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, pocNm, OBJPROP_COLOR, pocLineColor);
     }
   else
      ObjectDelete(0, prefix + "pocline");

   if(InpShowValueArea)
     {
      double totalVol = 0.0;
      for(int b = 0; b < InpBuckets; b++) totalVol += vol[b];
      double target = totalVol * (InpVAPercent / 100.0);
      int vaLo = pocBucket, vaHi = pocBucket;
      double included = vol[pocBucket];
      while(included < target && (vaLo > 0 || vaHi < InpBuckets - 1))
        {
         double leftVol  = (vaLo > 0) ? vol[vaLo - 1] : -1.0;
         double rightVol = (vaHi < InpBuckets - 1) ? vol[vaHi + 1] : -1.0;
         if(rightVol >= leftVol) { vaHi++; included += vol[vaHi]; }
         else                    { vaLo--; included += vol[vaLo]; }
        }
      double vahPrice = lo + (vaHi + 1) * bw;
      double valPrice = lo + vaLo * bw;
      datetime vaLineStart = InpPocLineRayLeft ? anchorTime : chartTime[(int)MathMax(0, chartEnd - InpPocLineBackBars)];
      datetime vaLineEnd   = anchorTime + (datetime)(InpMaxBarWidthBars * perSec);

      string vahNm = prefix + "vah";
      if(ObjectFind(0, vahNm) < 0)
        {
         ObjectCreate(0, vahNm, OBJ_TREND, 0, vaLineStart, vahPrice, vaLineEnd, vahPrice);
         ObjectSetInteger(0, vahNm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, vahNm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, vahNm, OBJPROP_STYLE, STYLE_DASH);
         ObjectSetInteger(0, vahNm, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, vahNm, OBJPROP_BACK, true);
        }
      else
        {
         ObjectSetInteger(0, vahNm, OBJPROP_TIME, 0, vaLineStart);
         ObjectSetDouble (0, vahNm, OBJPROP_PRICE, 0, vahPrice);
         ObjectSetInteger(0, vahNm, OBJPROP_TIME, 1, vaLineEnd);
         ObjectSetDouble (0, vahNm, OBJPROP_PRICE, 1, vahPrice);
        }
      ObjectSetInteger(0, vahNm, OBJPROP_RAY_LEFT, InpPocLineRayLeft);
      ObjectSetInteger(0, vahNm, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, vahNm, OBJPROP_COLOR, vaColor);

      string valNm = prefix + "val";
      if(ObjectFind(0, valNm) < 0)
        {
         ObjectCreate(0, valNm, OBJ_TREND, 0, vaLineStart, valPrice, vaLineEnd, valPrice);
         ObjectSetInteger(0, valNm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, valNm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, valNm, OBJPROP_STYLE, STYLE_DASH);
         ObjectSetInteger(0, valNm, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, valNm, OBJPROP_BACK, true);
        }
      else
        {
         ObjectSetInteger(0, valNm, OBJPROP_TIME, 0, vaLineStart);
         ObjectSetDouble (0, valNm, OBJPROP_PRICE, 0, valPrice);
         ObjectSetInteger(0, valNm, OBJPROP_TIME, 1, vaLineEnd);
         ObjectSetDouble (0, valNm, OBJPROP_PRICE, 1, valPrice);
        }
      ObjectSetInteger(0, valNm, OBJPROP_RAY_LEFT, InpPocLineRayLeft);
      ObjectSetInteger(0, valNm, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, valNm, OBJPROP_COLOR, vaColor);
     }
   else
     {
      ObjectDelete(0, prefix + "vah");
      ObjectDelete(0, prefix + "val");
     }
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpBuckets <= 0 || InpDaysToShow <= 0)
     {
      Print("VolumeProfile_Session: InpBuckets and InpDaysToShow must both be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   //--- v1.12 FIX (Opus audit, real gap): InpSourceTF=PERIOD_CURRENT would
   //--- silently bring back the exact chart-timeframe-dependent POC bug
   //--- this version was built to fix. Anything coarser than D1 also
   //--- breaks the day-boundary math below. Reject both explicitly rather
   //--- than let either one quietly reintroduce an already-fixed bug.
   if(InpSourceTF == PERIOD_CURRENT || PeriodSeconds(InpSourceTF) > PeriodSeconds(PERIOD_D1))
     {
      Print("VolumeProfile_Session: InpSourceTF must be a specific, fixed timeframe (not PERIOD_CURRENT) "
            "no coarser than D1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpPocLineBackBars < 0)
     {
      Print("VolumeProfile_Session: InpPocLineBackBars must be >= 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   IndicatorSetString(INDICATOR_SHORTNAME, "Session Volume Profile v1.12 (today" +
                       (InpShowPrevDay ? "+prev day)" : ")"));
   EnsureRightMargin();
   //--- v1.12 FIX (Opus audit, real usability gap): OnCalculate only ever
   //--- runs on a new tick/bar - on a closed market (weekend) or if
   //--- InpSourceTF's history wasn't ready yet on attach, the profile
   //--- could sit blank with nothing to trigger a retry. A low-frequency
   //--- timer forcing a recalc is cheap (DrawProfile's per-call cost is
   //--- already bounded, confirmed in the v1.11 audit) and guarantees it
   //--- eventually catches up without needing a real tick first.
   EventSetTimer(3);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, VP_PFX);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   ChartSetSymbolPeriod(0, _Symbol, _Period);   // forces OnCalculate to re-run even with no new tick
  }

//+------------------------------------------------------------------+
//| Full recompute every call - cheap (at most InpDaysToShow+1 days of |
//| bars for "today" plus one more day for "previous day"). Draws TWO  |
//| independent profile columns side by side in the chart's own blank/  |
//| empty space to the right of the last candle - never over any         |
//| candle, per direct request.                                           |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(rates_total < 2) return(0);
   EnsureRightMargin();   // cheap (SetIfDiff-style guard inside) - re-asserted here in case another
                          // EA/indicator on the same chart changed CHART_SHIFT_SIZE back since OnInit
   int perSec = PeriodSeconds(PERIOD_CURRENT);
   if(perSec <= 0) return(rates_total);

   //--- v1.12 FIX (Opus audit, real bug): session boundaries used to be
   //--- derived from the CHART's own time[] array (time[rates_total-1]
   //--- rounded to a calendar day) - correct on M1-D1 charts, but wrong on
   //--- W1/MN charts, where the last bar's own day-of-week means "today"
   //--- could resolve to the wrong calendar day entirely (e.g. a W1 bar
   //--- opens on Sunday). D1's own bar 0/1 are always the right session
   //--- boundaries regardless of what timeframe the chart itself is on -
   //--- bar 1 is by definition the last fully completed session, which
   //--- also replaces the old manual backward-scan-for-a-gap logic
   //--- entirely (handles Mondays/holidays for free, same as before, just
   //--- without scanning).
   datetime todayStart = iTime(_Symbol, PERIOD_D1, 0);
   datetime prevDayStart = iTime(_Symbol, PERIOD_D1, 1);
   if(todayStart <= 0) return(rates_total);   // D1 history not ready yet - retry next tick

   datetime todayCutoff = todayStart - (datetime)((long)(InpDaysToShow - 1) * 86400);
   int endToday = rates_total - 1;

   datetime todayAnchor = time[endToday] + (datetime)((1 + InpLeadingGapBars) * perSec);
   DrawProfile(VP_PFX + "today_", todayCutoff, TimeCurrent(), todayAnchor,
               time, endToday, perSec,
               InpBarColor, InpPocColor, InpPocLineColor, InpVahValColor);

   //--- PREVIOUS DAY column: exactly D1 bar 1's own session - the last
   //--- fully completed one, whatever calendar day that actually was.
   //--- Frozen, independent of InpDaysToShow, independent of how far
   //--- today has progressed.
   if(InpShowPrevDay && prevDayStart > 0)
     {
      datetime prevAnchor = todayAnchor + (datetime)((InpMaxBarWidthBars + InpColumnGapBars) * perSec);
      DrawProfile(VP_PFX + "prev_", prevDayStart, todayStart - 1, prevAnchor,
                  time, endToday, perSec,
                  InpPrevBarColor, InpPrevPocColor, InpPrevPocLineColor, InpPrevVahValColor);
     }
   else
      DeleteProfileObjects(VP_PFX + "prev_");

   ChartRedraw(0);
   return(rates_total);
  }
