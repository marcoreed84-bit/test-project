//+------------------------------------------------------------------+
//|                                           Important_SR_Levels.mq5 |
//|  Historic support/resistance fractal levels, with a TOUCH COUNT   |
//|  per level so you can actually see whether price has respected    |
//|  it (touches=1 means untested; touches=5 means it's been bounced  |
//|  off repeatedly) - built to answer "did Bitcoin actually respect  |
//|  these levels", not just draw lines.                              |
//|                                                                    |
//|  Per direct request: this shows MAJOR levels only, not minor       |
//|  noise - InpMinTouchesToShow (default 2) hides any level until it |
//|  has actually been touched/respected that many times, and when    |
//|  the chart is full (InpMaxLevels), the LEAST-touched level is     |
//|  dropped first, so what stays on screen is always the most-tested |
//|  levels, not just the newest ones.                                 |
//|                                                                    |
//|  Opus-reviewed before shipping - 4 must-fix bugs found in the      |
//|  first rewrite, all fixed here:                                    |
//|   1. The incremental re-scan window was 2 bars too wide, so the   |
//|      newest 3 confirmed pivots got re-registered (touches++) on   |
//|      every single tick with no new bar - a level could read x200  |
//|      in an hour on fast-moving BTC. Fixed: re-scan window is now  |
//|      exactly the bars that could not have been fully confirmed    |
//|      last call, no extra margin.                                  |
//|   2. If the terminal ever resets prev_calculated to 0 (a history   |
//|      reload/gap-fill), the old scan used to run AGAIN on top of   |
//|      the already-built level list, roughly doubling every count. |
//|      Fixed: a prev_calculated==0 call now clears everything first.|
//|   3. If the ATR indicator wasn't finished calculating yet on the  |
//|      very first call (common right after attaching), the function |
//|      used to silently give up AND tell MT5 the whole history was  |
//|      already handled - so the real backfill scan never happened   |
//|      at all. Fixed: returns 0 on that failure, so MT5 retries the |
//|      full scan on the next tick instead of skipping it forever.   |
//|   4. ONE current ATR value was used to decide which pivots merge  |
//|      together, across the WHOLE of history - on BTC, which has    |
//|      gone from ~$300 to five/six figures, that means old pivots   |
//|      from the $300 era get merged using TODAY's (much bigger)     |
//|      ATR, collapsing genuinely distinct old levels into one.      |
//|      Fixed: each pivot now uses the ATR AS IT WAS AT THAT BAR,    |
//|      not today's value.                                           |
//|  Plus two minor fixes: a flat-top/flat-bottom tie (two neighbour  |
//|  bars with the exact same high/low) could register as two          |
//|  separate pivots instead of one; and InpMaxLevels/                |
//|  InpLeftRightWindow are now validated in OnInit instead of being  |
//|  able to silently misbehave on a bad input value.                  |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property version   "1.03"
//--- 1.03: Fixed the real reason the journal showed "39 visible levels"
//--- but the user still only saw a couple of lines on the actual BTC
//--- chart. Root cause: InpAtrMultiplier x ATR is a DOLLAR distance -
//--- back when BTC traded at a few hundred dollars, ATR was tiny, so
//--- pivots from that era clustered extremely tightly and accumulated
//--- huge touch counts over the years BTC spent in that price range.
//--- Since eviction (when over InpMaxLevels) always drops the
//--- LEAST-touched level, those old high-touch-count clusters from
//--- BTC's early, cheap history were winning every eviction and
//--- crowding out genuinely current, tradeable levels - and since
//--- they're also all priced far below BTC's current price, they'd
//--- render bunched together off-screen from wherever you're actually
//--- looking on the chart. Added InpLookbackDays (default 730, ~2
//--- years) - pivots older than this are no longer even ELIGIBLE to be
//--- registered as a level at all, so the old cheap-era clusters can
//--- never form or compete for the level slots in the first place. Set
//--- to 0 to go back to scanning all available history.
//--- 1.02: Fixed two real "silently never scans" bugs, found while
//--- diagnosing a report of attaching this and seeing no levels at
//--- all. Both early "not enough bars yet" checks in OnCalculate were
//--- returning rates_total (meaning "fully handled") instead of 0 -
//--- if MT5 called this indicator before the symbol's full history had
//--- loaded, it would claim the backfill was already done and NEVER
//--- actually run it once more history arrived. Also added two Print
//--- lines that were missing entirely before: one in OnInit confirming
//--- the indicator actually attached and what settings it's using, and
//--- one after the first full backfill showing how many pivots were
//--- found vs. how many cleared InpMinTouchesToShow and are actually
//--- visible - previously this indicator only ever printed on an
//--- ERROR, so "nothing in the Experts journal" told you nothing about
//--- whether it was running normally or not running at all.
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== Fractal detection ==="
input int      InpLeftRightWindow  = 5;     // Fractal window (candles confirmed closed on each side)
input int      InpAtrPeriod        = 14;    // ATR period used for the volatility filter below

input group "=== Volatility-based level clustering ==="
input double   InpAtrMultiplier    = 1.5;   // Pivots within this many ATR (AS OF THAT PIVOT'S OWN BAR, not
                                             // today's ATR) of an existing level MERGE into it (touch count
                                             // +1) instead of creating a new, separate line - this is what
                                             // keeps BTC's noisy micro-swings from spawning dozens of
                                             // near-duplicate levels
input int      InpMaxLevels        = 40;    // Hard cap on how many levels stay on the chart at once - if
                                             // exceeded, the LEAST-touched level is dropped first (keeps the
                                             // most-respected, most-informative levels, not just the newest)

input group "=== \"Major levels only\" filter ==="
input int      InpMinTouchesToShow = 2;     // Per direct request: a level only gets drawn once it's been
                                             // touched/respected at least this many times - a single
                                             // untested pivot is noise, not a major level. Set to 1 to show
                                             // every pivot immediately (back to the old behavior).
input int      InpLookbackDays     = 730;   // v1.03 FIX: only pivots from the last N calendar days are even
                                             // ELIGIBLE to be registered as a level (0 = no limit, scan
                                             // all available history). Added because the clustering distance
                                             // (InpAtrMultiplier x ATR) was tiny back when BTC traded at a
                                             // few hundred dollars - old pivots from that era cluster into a
                                             // handful of extremely high-touch-count "super levels" that
                                             // then win every eviction and crowd out genuinely current,
                                             // relevant levels. 730 days (~2 years) keeps the level list
                                             // anchored to BTC's current price regime instead of its entire
                                             // multi-order-of-magnitude price history.

input group "=== Display ==="
input color    InpSupportColor     = clrLime;
input color    InpResistanceColor  = clrRed;
input int      InpLineWidth        = 1;
input bool     InpShowTouchLabels  = true;  // small "xN" text label showing each line's touch count - the
                                             // actual answer to "was this respected", placed at the time of
                                             // its most recent touch
input color    InpLabelColor       = clrWhite;
input int      InpLabelFontSize    = 8;

#define PFX "SRL_"

struct SRLevel
  {
   double   price;
   bool     isSupport;
   datetime firstTime;
   datetime lastTime;
   int      touches;
   string   lineName;
   string   labelName;
  };

SRLevel  g_levels[];
int      g_atrHandle = INVALID_HANDLE;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpLeftRightWindow <= 0)
     {
      Print("Important_SR_Levels: InpLeftRightWindow must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpMaxLevels <= 0)
     {
      Print("Important_SR_Levels: InpMaxLevels must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_atrHandle = iATR(_Symbol, _Period, InpAtrPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("Important_SR_Levels: failed to create ATR handle.");
      return(INIT_FAILED);
     }
   ArrayResize(g_levels, 0);
   //--- v1.02: unconditional confirmation line - previously this
   //--- indicator only ever printed on an ERROR, so "nothing in the
   //--- journal" told you nothing about whether it was actually
   //--- running. Now it always confirms attach + settings here.
   PrintFormat("Important_SR_Levels v1.02 OnInit: %s %s  window=%d  minTouches=%d  maxLevels=%d  atrMult=%.2f",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpLeftRightWindow, InpMinTouchesToShow, InpMaxLevels, InpAtrMultiplier);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, PFX);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
//| Draw (or move/update) one level's chart objects. Does nothing if  |
//| it hasn't reached InpMinTouchesToShow yet - that's the "major     |
//| levels only, not minor noise" filter.                             |
//+------------------------------------------------------------------+
void RedrawLevel(SRLevel &lvl)
  {
   if(lvl.touches < InpMinTouchesToShow) return;

   color col = lvl.isSupport ? InpSupportColor : InpResistanceColor;

   if(ObjectFind(0, lvl.lineName) < 0)
     {
      ObjectCreate(0, lvl.lineName, OBJ_HLINE, 0, 0, lvl.price);
      ObjectSetInteger(0, lvl.lineName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, lvl.lineName, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, lvl.lineName, OBJPROP_COLOR, col);
   ObjectSetInteger(0, lvl.lineName, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, lvl.lineName, OBJPROP_WIDTH, InpLineWidth);
   ObjectSetDouble(0, lvl.lineName, OBJPROP_PRICE, lvl.price);
   ObjectSetString(0, lvl.lineName, OBJPROP_TOOLTIP,
                    (lvl.isSupport ? "Support " : "Resistance ") + DoubleToString(lvl.price, _Digits) +
                    "  touches=" + IntegerToString(lvl.touches) +
                    "  first=" + TimeToString(lvl.firstTime, TIME_DATE) +
                    "  last=" + TimeToString(lvl.lastTime, TIME_DATE));

   if(InpShowTouchLabels)
     {
      if(ObjectFind(0, lvl.labelName) < 0)
        {
         ObjectCreate(0, lvl.labelName, OBJ_TEXT, 0, lvl.lastTime, lvl.price);
         ObjectSetInteger(0, lvl.labelName, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, lvl.labelName, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, lvl.labelName, OBJPROP_ANCHOR, ANCHOR_LEFT);
        }
      //--- placed at the time of the level's MOST RECENT touch (not the
      //--- chart's right edge - a level last touched months ago sits
      //--- where it was last actually touched, not dragged to "now")
      ObjectSetInteger(0, lvl.labelName, OBJPROP_TIME, 0, lvl.lastTime);
      ObjectSetDouble(0, lvl.labelName, OBJPROP_PRICE, lvl.price);
      ObjectSetString(0, lvl.labelName, OBJPROP_TEXT, " x" + IntegerToString(lvl.touches));
      ObjectSetInteger(0, lvl.labelName, OBJPROP_COLOR, InpLabelColor);
      ObjectSetInteger(0, lvl.labelName, OBJPROP_FONTSIZE, InpLabelFontSize);
     }
  }

//+------------------------------------------------------------------+
//| Find an existing same-type level within minDistance of price.    |
//| Returns its index in g_levels, or -1 if none is close enough.    |
//+------------------------------------------------------------------+
int FindNearbyLevel(const double price, const bool isSupport, const double minDistance)
  {
   int best = -1;
   double bestDist = DBL_MAX;
   for(int k = 0; k < ArraySize(g_levels); k++)
     {
      if(g_levels[k].isSupport != isSupport) continue;
      double d = MathAbs(g_levels[k].price - price);
      if(d < minDistance && d < bestDist) { best = k; bestDist = d; }
     }
   return best;
  }

//+------------------------------------------------------------------+
//| New pivot confirmed at (t, price, isSupport) - merge into an      |
//| existing nearby level (touch++) or create a brand-new one.        |
//| minDistance is the ATR-based clustering distance AS OF THIS       |
//| PIVOT'S OWN BAR, not today's ATR - critical on an instrument like |
//| BTC whose volatility has grown by orders of magnitude over its    |
//| history.                                                          |
//+------------------------------------------------------------------+
void RegisterTouch(const datetime t, const double price, const bool isSupport, const double minDistance)
  {
   int idx = FindNearbyLevel(price, isSupport, minDistance);
   if(idx >= 0)
     {
      //--- merged into an existing level: nudge its price toward the
      //--- average of all touches so far (keeps the line representative
      //--- of the whole cluster, not stuck on the very first touch) and
      //--- extend its "last touched" time
      g_levels[idx].price = (g_levels[idx].price * g_levels[idx].touches + price) / (g_levels[idx].touches + 1);
      g_levels[idx].touches++;
      g_levels[idx].lastTime = t;
      RedrawLevel(g_levels[idx]);
      return;
     }

   //--- genuinely new level
   int n = ArraySize(g_levels);
   if(n >= InpMaxLevels)
     {
      //--- drop the least-touched existing level to make room - keeps
      //--- the most-respected levels, not just whatever is newest
      int weakest = 0;
      for(int k = 1; k < n; k++)
         if(g_levels[k].touches < g_levels[weakest].touches) weakest = k;
      ObjectDelete(0, g_levels[weakest].lineName);
      ObjectDelete(0, g_levels[weakest].labelName);
      g_levels[weakest] = g_levels[n - 1];
      ArrayResize(g_levels, n - 1);
      n = n - 1;
     }

   ArrayResize(g_levels, n + 1);
   g_levels[n].price     = price;
   g_levels[n].isSupport = isSupport;
   g_levels[n].firstTime = t;
   g_levels[n].lastTime  = t;
   g_levels[n].touches   = 1;
   g_levels[n].lineName  = PFX + (isSupport ? "S_" : "R_") + IntegerToString((long)t);
   g_levels[n].labelName = PFX + "lbl_" + (isSupport ? "S_" : "R_") + IntegerToString((long)t);
   RedrawLevel(g_levels[n]);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                 const int prev_calculated,
                 const datetime &time[],
                 const double &open[],
                 const double &high[],
                 const double &low[],
                 const double &close[],
                 const long &tick_volume[],
                 const long &volume[],
                 const int &spread[])
  {
   int w = InpLeftRightWindow;
   //--- v1.02 FIX: "not enough bars yet" must return 0, not rates_total -
   //--- returning rates_total claims the whole history is fully handled,
   //--- so if MT5 later loads more history (common right after attach,
   //--- or on a symbol whose history is still downloading), this
   //--- indicator would never go back and actually run the real scan.
   if(rates_total < 2 * w + 2) return(0);

   //--- v1.01 FIX #2: prev_calculated resetting to 0 (a history
   //--- reload/gap-fill, NOT necessarily "freshly attached") must wipe
   //--- the existing level list and chart objects first - otherwise the
   //--- whole history gets re-scanned on top of what's already there,
   //--- roughly doubling every touch count.
   if(prev_calculated <= 0)
     {
      ObjectsDeleteAll(0, PFX);
      ArrayResize(g_levels, 0);
     }

   //--- the newest CLOSED bar is rates_total-2 (rates_total-1 is still
   //--- forming) - a pivot candidate at index i needs w closed bars on
   //--- BOTH sides, so the last checkable candidate is (rates_total-2-w)
   int maxI = rates_total - 2 - w;
   if(maxI < w) return(0);   // v1.02 FIX - same reasoning as above

   //--- v1.01 FIX #1: exactly the candidates that could NOT have been
   //--- fully confirmed last call - no extra margin. A closed bar's
   //--- high/low never changes, so once a candidate has been checked
   //--- with a full w-bar window on both sides, it never needs
   //--- re-checking. The old "-2" margin here re-registered the same
   //--- few newest pivots on every tick with no new bar, which could
   //--- inflate a touch count by one per tick for hours.
   int startI = (prev_calculated <= 0) ? w : MathMax(w, prev_calculated - 1 - w);
   if(startI > maxI) return(rates_total);

   //--- v1.03: lookback cutoff - see InpLookbackDays' own comment
   datetime cutoffTime = (InpLookbackDays > 0) ? (time[maxI] - (datetime)((long)InpLookbackDays * 86400)) : 0;

   //--- v1.01 FIX #4: read ATR PER BAR, not one current value applied
   //--- to all of history - only the slice actually needed this call.
   int atrCount = maxI - startI + 1;
   double atrBuf[];
   ArraySetAsSeries(atrBuf, false);
   if(CopyBuffer(g_atrHandle, 0, startI, atrCount, atrBuf) < atrCount)
     {
      //--- v1.01 FIX #3: tell MT5 this call did NOT handle the history
      //--- (return 0, not rates_total) so it retries properly next
      //--- tick instead of silently treating the backfill as done.
      return(0);
     }

   for(int i = startI; i <= maxI; i++)
     {
      if(time[i] < cutoffTime) continue;   // v1.03: outside the lookback window - not eligible at all
      double minDistance = atrBuf[i - startI] * InpAtrMultiplier;
      if(minDistance <= 0.0) continue;

      //--- v1.01 minor fix: a flat-top/flat-bottom tie (two bars with the
      //--- exact same high or low) used to let BOTH register as separate
      //--- pivots. Ties now resolve to the LATER (more recent) bar only -
      //--- a tie with an EARLIER neighbor is allowed, but a tie (or
      //--- worse) against a LATER neighbor disqualifies, so only the
      //--- rightmost bar in a flat top/bottom ever becomes the pivot.
      bool isPeak = true, isTrough = true;
      for(int k = 1; k <= w; k++)
        {
         if(high[i] < high[i - k] || high[i] <= high[i + k]) isPeak = false;
         if(low[i]  > low[i - k]  || low[i]  >= low[i + k])  isTrough = false;
         if(!isPeak && !isTrough) break;
        }
      if(isPeak)         RegisterTouch(time[i], high[i], false, minDistance);
      else if(isTrough)  RegisterTouch(time[i], low[i],  true,  minDistance);
     }

   //--- v1.02: one-time summary once the initial backfill finishes, so
   //--- "I attached it and see nothing" has an actual answer in the
   //--- journal instead of silence either way.
   if(prev_calculated <= 0)
     {
      int visible = 0;
      for(int k = 0; k < ArraySize(g_levels); k++)
         if(g_levels[k].touches >= InpMinTouchesToShow) visible++;
      PrintFormat("Important_SR_Levels: initial scan done - %d bars checked (lookback cutoff: %s), "
                  "%d levels found, %d visible (touches>=%d), %d hidden below the touch threshold",
                  maxI - startI + 1, (InpLookbackDays > 0) ? TimeToString(cutoffTime, TIME_DATE) : "none",
                  ArraySize(g_levels), visible, InpMinTouchesToShow, ArraySize(g_levels) - visible);
     }

   return(rates_total);
  }
