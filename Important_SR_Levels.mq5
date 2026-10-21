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
#property version   "1.06"
//--- 1.06: User reported (with a chart screenshot) that levels only ever
//--- appeared well ABOVE and well BELOW the price band the market had
//--- actually been trading in for days, with a visible gap of NO levels
//--- exactly where price currently is. Real design flaw, not a bug in
//--- the strict sense: eviction always drops the least-touched level,
//--- and every brand-new pivot starts at touches=1 - so during an
//--- active chop, each fresh intraday swing creates a new 1-touch level
//--- that is immediately the weakest thing in the array and gets evicted
//--- by older levels elsewhere in the lookback window that already
//--- reached 2+ touches, before the current zone's level ever got a
//--- SECOND touch to clear InpMinTouchesToShow and actually get drawn.
//--- Net effect: only old, already-proven levels survive long-term,
//--- systematically starving out wherever price is RIGHT NOW. Fixed:
//--- new InpRecentProtectDays (default 14) - a level formed within this
//--- many days of the newest bar can never be evicted, however few
//--- touches it has, giving it time to actually prove itself before
//--- being judged against older, more-tested levels. Falls back to
//--- unprotected least-touched eviction only if literally every level in
//--- the array happens to be recent (so the cap still can't be exceeded).
//--- 1.05: User reported "40 levels found" in the journal but still zero
//--- visible lines on the chart, and changing the colour inputs made no
//--- difference at all - a strong sign the lines never actually existed
//--- on the chart in the first place, since a colour change on a line
//--- that was never drawn is naturally invisible too. Root cause found:
//--- ObjectCreate()'s return value was NEVER checked anywhere in this
//--- file. If it silently fails - a name collision with some other
//--- object/indicator on the same chart, an invalid price, anything -
//--- the level stays tracked in the g_levels array exactly as if it had
//--- drawn fine, so the scan summary happily reports "N levels found"
//--- while the chart has nothing on it, with zero way to tell from the
//--- journal. Fixed: ObjectCreate's result is now checked, and a failure
//--- logs the exact object name, price and GetLastError() code. Also
//--- added LogLevelDiagnostics(), printed after every scan (intraday,
//--- daily, weekly): counts how many tracked levels ACTUALLY have a
//--- matching object on the chart right now (via ObjectFind), and prints
//--- the price range those levels span next to the current bid price -
//--- so "found but never drawn" (this bug) and "drawn but off-screen"
//--- (a different, already-considered cause) are told apart by the
//--- journal instead of guessed at.
//--- 1.04: Added a SECOND, independent layer of levels built from DAILY
//--- and WEEKLY bars directly (via CopyRates(_Symbol, PERIOD_D1/W1, ...)),
//--- not just fractals on whatever timeframe the chart happens to be on.
//--- Per direct request: "we would need more recent support and
//--- resistance as well, there should be daily support and resistance
//--- levels, weekly?" - the original scan only ever sees pivots on the
//--- chart's own timeframe, so a daily/weekly swing high or low that
//--- isn't ALSO a fractal on (say) M15 could be missed or show up late.
//--- These two new layers run the exact same fractal-confirm + ATR-
//--- clustering + touch-count logic as the main scan (refactored into
//--- shared helper functions that take the level array/prefix/colors as
//--- parameters instead of hardcoded globals), just fed D1/W1 bars and
//--- drawn in their own colors so you can tell the three layers apart.
//--- Each only re-scans when a NEW daily/weekly bar has actually closed
//--- (checked via the newest closed bar's time), not every tick - D1/W1
//--- history is small enough (a few thousand / a few hundred bars) that
//--- a full re-scan on that rare event is cheap and simpler/safer than
//--- replicating the incremental prev_calculated bookkeeping for a
//--- second and third data source.
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
input int      InpRecentProtectDays = 14;   // v1.06 FIX: a level formed within this many days of the newest
                                             // bar can NEVER be evicted, however few touches it has. Without
                                             // this, every brand-new pivot starts at touches=1 and is
                                             // immediate eviction-bait against older levels elsewhere in the
                                             // lookback window that already reached 2+ touches - so the price
                                             // zone the market is ACTUALLY in right now could be evicted
                                             // before it ever got the chance to accumulate a second touch,
                                             // leaving nothing but old, already-proven levels on screen and a
                                             // visible gap exactly where price has been trading for days. Set
                                             // to 0 to disable (go back to pure least-touched eviction).

input group "=== Display ==="
input color    InpSupportColor     = clrLime;
input color    InpResistanceColor  = clrRed;
input int      InpLineWidth        = 1;
input bool     InpShowTouchLabels  = true;  // small "xN" text label showing each line's touch count - the
                                             // actual answer to "was this respected", placed at the time of
                                             // its most recent touch
input color    InpLabelColor       = clrWhite;
input int      InpLabelFontSize    = 8;

input group "=== Daily / Weekly levels (independent of the chart's own timeframe) ==="
input bool     InpShowDailyLevels    = true;   // scan PERIOD_D1 bars directly for daily S/R, regardless of
                                                // what timeframe this chart is actually showing
input bool     InpShowWeeklyLevels   = true;   // same, for PERIOD_W1
input int      InpDWWindow           = 2;      // fractal window on D1/W1 bars - smaller than the intraday
                                                // one since each bar already represents a full day/week
input int      InpDWMinTouchesToShow = 2;      // "major levels only" filter, same idea as InpMinTouchesToShow
input int      InpDWMaxLevels        = 20;     // cap per layer (daily and weekly each get their own 20)
input int      InpDWLookbackDays     = 1825;   // ~5 years - daily/weekly pivots are rarer and more durable
                                                // than intraday ones, so a longer lookback makes sense here
input color    InpDailySupportColor    = clrAqua;
input color    InpDailyResistanceColor = clrOrange;
input color    InpWeeklySupportColor    = clrDodgerBlue;
input color    InpWeeklyResistanceColor = clrMagenta;

#define PFX   "SRL_"
#define PFX_D "SRLD_"
#define PFX_W "SRLW_"

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
SRLevel  g_levelsD[];
SRLevel  g_levelsW[];
int      g_atrHandle  = INVALID_HANDLE;
int      g_atrHandleD = INVALID_HANDLE;
int      g_atrHandleW = INVALID_HANDLE;
datetime g_lastDailyBarTime  = 0;
datetime g_lastWeeklyBarTime = 0;

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
   if(InpShowDailyLevels)
     {
      g_atrHandleD = iATR(_Symbol, PERIOD_D1, InpAtrPeriod);
      if(g_atrHandleD == INVALID_HANDLE)
        {
         Print("Important_SR_Levels: failed to create daily ATR handle.");
         return(INIT_FAILED);
        }
     }
   if(InpShowWeeklyLevels)
     {
      g_atrHandleW = iATR(_Symbol, PERIOD_W1, InpAtrPeriod);
      if(g_atrHandleW == INVALID_HANDLE)
        {
         Print("Important_SR_Levels: failed to create weekly ATR handle.");
         return(INIT_FAILED);
        }
     }
   ArrayResize(g_levels, 0);
   ArrayResize(g_levelsD, 0);
   ArrayResize(g_levelsW, 0);
   g_lastDailyBarTime  = 0;
   g_lastWeeklyBarTime = 0;
   //--- v1.02: unconditional confirmation line - previously this
   //--- indicator only ever printed on an ERROR, so "nothing in the
   //--- journal" told you nothing about whether it was actually
   //--- running. Now it always confirms attach + settings here.
   PrintFormat("Important_SR_Levels v1.04 OnInit: %s %s  window=%d  minTouches=%d  maxLevels=%d  atrMult=%.2f  "
               "daily=%s  weekly=%s",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpLeftRightWindow, InpMinTouchesToShow, InpMaxLevels, InpAtrMultiplier,
               InpShowDailyLevels ? "on" : "off", InpShowWeeklyLevels ? "on" : "off");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, PFX);
   ObjectsDeleteAll(0, PFX_D);
   ObjectsDeleteAll(0, PFX_W);
   if(g_atrHandle  != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   if(g_atrHandleD != INVALID_HANDLE) IndicatorRelease(g_atrHandleD);
   if(g_atrHandleW != INVALID_HANDLE) IndicatorRelease(g_atrHandleW);
  }

//+------------------------------------------------------------------+
//| Draw (or move/update) one level's chart objects. Does nothing if  |
//| it hasn't reached InpMinTouchesToShow yet - that's the "major     |
//| levels only, not minor noise" filter.                             |
//+------------------------------------------------------------------+
void RedrawLevelG(SRLevel &lvl, const int minTouchesToShow, const color supCol, const color resCol)
  {
   if(lvl.touches < minTouchesToShow) return;

   color col = lvl.isSupport ? supCol : resCol;

   if(ObjectFind(0, lvl.lineName) < 0)
     {
      //--- v1.05 FIX: ObjectCreate's return value was never checked - if
      //--- it silently failed (name collision with another object on
      //--- this chart, invalid price, etc.) the level was still tracked
      //--- in g_levels as if it had drawn fine, so the scan summary could
      //--- say "N levels found" while literally zero lines existed on
      //--- the chart, with no way to tell from the journal. Now logged.
      if(!ObjectCreate(0, lvl.lineName, OBJ_HLINE, 0, 0, lvl.price))
        {
         PrintFormat("Important_SR_Levels: ObjectCreate FAILED for %s at price %s - error %d",
                     lvl.lineName, DoubleToString(lvl.price, _Digits), GetLastError());
         return;
        }
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
//| v1.05: prints exactly what "N levels found" could not tell you -  |
//| how many of the tracked, visible-threshold-clearing levels have   |
//| an object that ACTUALLY EXISTS on the chart (ObjectFind >= 0),    |
//| and the price range they span vs. the current price - so "found  |
//| but not seen" (ObjectCreate silently failed) and "found and drawn |
//| but nowhere near current price" (off-screen) are told apart.      |
//+------------------------------------------------------------------+
void LogLevelDiagnostics(SRLevel &levels[], const int minTouchesToShow, const string label)
  {
   int tracked = 0, verified = 0;
   double minPrice = DBL_MAX, maxPrice = -DBL_MAX;
   for(int k = 0; k < ArraySize(levels); k++)
     {
      if(levels[k].touches < minTouchesToShow) continue;
      tracked++;
      if(ObjectFind(0, levels[k].lineName) >= 0) verified++;
      if(levels[k].price < minPrice) minPrice = levels[k].price;
      if(levels[k].price > maxPrice) maxPrice = levels[k].price;
     }
   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(tracked == 0)
      PrintFormat("Important_SR_Levels [%s]: 0 levels clear the touch threshold - nothing to draw.", label);
   else
      PrintFormat("Important_SR_Levels [%s]: %d tracked, %d actually verified ON CHART (ObjectFind) - "
                  "price range %s .. %s, current price %s",
                  label, tracked, verified, DoubleToString(minPrice, _Digits), DoubleToString(maxPrice, _Digits),
                  DoubleToString(curPrice, _Digits));
  }

//+------------------------------------------------------------------+
//| Find an existing same-type level within minDistance of price.    |
//| Returns its index in g_levels, or -1 if none is close enough.    |
//+------------------------------------------------------------------+
int FindNearbyLevelG(SRLevel &levels[], const double price, const bool isSupport, const double minDistance)
  {
   int best = -1;
   double bestDist = DBL_MAX;
   for(int k = 0; k < ArraySize(levels); k++)
     {
      if(levels[k].isSupport != isSupport) continue;
      double d = MathAbs(levels[k].price - price);
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
void RegisterTouchG(SRLevel &levels[], const datetime t, const double price, const bool isSupport,
                     const double minDistance, const string prefix, const int maxLevels,
                     const int minTouchesToShow, const color supCol, const color resCol,
                     const datetime recentCutoff)
  {
   int idx = FindNearbyLevelG(levels, price, isSupport, minDistance);
   if(idx >= 0)
     {
      //--- merged into an existing level: nudge its price toward the
      //--- average of all touches so far (keeps the line representative
      //--- of the whole cluster, not stuck on the very first touch) and
      //--- extend its "last touched" time
      levels[idx].price = (levels[idx].price * levels[idx].touches + price) / (levels[idx].touches + 1);
      levels[idx].touches++;
      levels[idx].lastTime = t;
      RedrawLevelG(levels[idx], minTouchesToShow, supCol, resCol);
      return;
     }

   //--- genuinely new level
   int n = ArraySize(levels);
   if(n >= maxLevels)
     {
      //--- v1.06 FIX: drop the least-touched level, but NEVER one formed
      //--- within the last InpRecentProtectDays - that's what used to let
      //--- a current price zone get evicted while it still only had 1
      //--- touch, before it ever had a chance to prove itself. Only look
      //--- among levels older than the protection window; if literally
      //--- every level happens to be recent (e.g. indicator just
      //--- attached), fall back to evicting the least-touched regardless,
      //--- so the array can't grow past maxLevels forever.
      int weakest = -1;
      for(int k = 0; k < n; k++)
        {
         if(recentCutoff != 0 && levels[k].firstTime >= recentCutoff) continue;
         if(weakest < 0 || levels[k].touches < levels[weakest].touches) weakest = k;
        }
      if(weakest < 0)
        {
         weakest = 0;
         for(int k = 1; k < n; k++)
            if(levels[k].touches < levels[weakest].touches) weakest = k;
        }
      ObjectDelete(0, levels[weakest].lineName);
      ObjectDelete(0, levels[weakest].labelName);
      levels[weakest] = levels[n - 1];
      ArrayResize(levels, n - 1);
      n = n - 1;
     }

   ArrayResize(levels, n + 1);
   levels[n].price     = price;
   levels[n].isSupport = isSupport;
   levels[n].firstTime = t;
   levels[n].lastTime  = t;
   levels[n].touches   = 1;
   levels[n].lineName  = prefix + (isSupport ? "S_" : "R_") + IntegerToString((long)t);
   levels[n].labelName = prefix + "lbl_" + (isSupport ? "S_" : "R_") + IntegerToString((long)t);
   RedrawLevelG(levels[n], minTouchesToShow, supCol, resCol);
  }

//+------------------------------------------------------------------+
//| Daily/weekly layer: scans a higher timeframe's own bars directly  |
//| via CopyRates, completely independent of the chart's timeframe.   |
//| Only does a full rescan when a NEW bar on that timeframe has      |
//| actually closed (cheap: D1/W1 history is a few thousand bars at   |
//| most, so a full rescan on that rare event is simpler and safer    |
//| than replicating the main scan's incremental bookkeeping twice    |
//| more).                                                             |
//+------------------------------------------------------------------+
void ScanHigherTF(const ENUM_TIMEFRAMES tf, SRLevel &levels[], const string prefix,
                   const color supCol, const color resCol, const int atrHandle, datetime &lastBarTime)
  {
   int w = InpDWWindow;
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int count = CopyRates(_Symbol, tf, 0, 5000, rates);
   if(count < 2 * w + 2) return;

   //--- newest CLOSED bar is count-2 (count-1 is the currently forming bar)
   int maxI = count - 2 - w;
   if(maxI < w) return;

   //--- throttle: only rescan when a new bar has actually closed on this TF
   if(rates[maxI].time == lastBarTime) return;
   lastBarTime = rates[maxI].time;

   ObjectsDeleteAll(0, prefix);
   ArrayResize(levels, 0);

   datetime cutoffTime = (InpDWLookbackDays > 0) ? (rates[maxI].time - (datetime)((long)InpDWLookbackDays * 86400)) : 0;
   datetime recentCutoff = (InpRecentProtectDays > 0) ? (rates[maxI].time - (datetime)((long)InpRecentProtectDays * 86400)) : 0;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, false);
   int atrCount = maxI - w + 1;
   if(CopyBuffer(atrHandle, 0, w, atrCount, atrBuf) < atrCount) return;

   for(int i = w; i <= maxI; i++)
     {
      if(rates[i].time < cutoffTime) continue;
      double minDistance = atrBuf[i - w] * InpAtrMultiplier;
      if(minDistance <= 0.0) continue;

      bool isPeak = true, isTrough = true;
      for(int k = 1; k <= w; k++)
        {
         if(rates[i].high < rates[i - k].high || rates[i].high <= rates[i + k].high) isPeak = false;
         if(rates[i].low  > rates[i - k].low  || rates[i].low  >= rates[i + k].low)  isTrough = false;
         if(!isPeak && !isTrough) break;
        }
      if(isPeak)         RegisterTouchG(levels, rates[i].time, rates[i].high, false, minDistance, prefix,
                                         InpDWMaxLevels, InpDWMinTouchesToShow, supCol, resCol, recentCutoff);
      else if(isTrough)  RegisterTouchG(levels, rates[i].time, rates[i].low,  true,  minDistance, prefix,
                                         InpDWMaxLevels, InpDWMinTouchesToShow, supCol, resCol, recentCutoff);
     }

   int visible = 0;
   for(int k = 0; k < ArraySize(levels); k++)
      if(levels[k].touches >= InpDWMinTouchesToShow) visible++;
   PrintFormat("Important_SR_Levels: %s rescan - %d bars checked, %d levels found, %d visible (touches>=%d)",
               EnumToString(tf), maxI - w + 1, ArraySize(levels), visible, InpDWMinTouchesToShow);
   LogLevelDiagnostics(levels, InpDWMinTouchesToShow, EnumToString(tf));
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
   datetime recentCutoff = (InpRecentProtectDays > 0) ? (time[maxI] - (datetime)((long)InpRecentProtectDays * 86400)) : 0;

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
      if(isPeak)         RegisterTouchG(g_levels, time[i], high[i], false, minDistance, PFX, InpMaxLevels,
                                         InpMinTouchesToShow, InpSupportColor, InpResistanceColor, recentCutoff);
      else if(isTrough)  RegisterTouchG(g_levels, time[i], low[i],  true,  minDistance, PFX, InpMaxLevels,
                                         InpMinTouchesToShow, InpSupportColor, InpResistanceColor, recentCutoff);
     }

   if(InpShowDailyLevels)
      ScanHigherTF(PERIOD_D1, g_levelsD, PFX_D, InpDailySupportColor, InpDailyResistanceColor,
                   g_atrHandleD, g_lastDailyBarTime);
   if(InpShowWeeklyLevels)
      ScanHigherTF(PERIOD_W1, g_levelsW, PFX_W, InpWeeklySupportColor, InpWeeklyResistanceColor,
                   g_atrHandleW, g_lastWeeklyBarTime);

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
      LogLevelDiagnostics(g_levels, InpMinTouchesToShow, "intraday");
     }

   return(rates_total);
  }
