//+------------------------------------------------------------------+
//|                                       MarketStructure_Break.mq5   |
//|  Standalone indicator - Break of (market) Structure only. Per     |
//|  direct request: a short dashed line where structure breaks,      |
//|  drawn only for roughly the last 2 days by default.               |
//|                                                                    |
//|  Deliberately separate from MarketStructure_Swings.mq5 (which      |
//|  already does full HH/HL/LH/LL labelling + its own unvalidated     |
//|  continuation signals) - this file ONLY tracks the two most        |
//|  recent confirmed swing points and draws a line the one time each  |
//|  one is broken. No labels for every minor wiggle, no buy/sell      |
//|  signals.                                                           |
//|                                                                    |
//|  Definition used (standard BOS): track the most recent confirmed   |
//|  swing HIGH and swing LOW (fractal pivots, InpPivotWindow bars on  |
//|  each side). The first CLOSE that breaks back above the tracked    |
//|  swing high = bullish BOS (marks that high "broken", won't refire  |
//|  again until a newer swing high replaces it); the first close      |
//|  below the tracked swing low = bearish BOS, mirror. A closed bar's |
//|  own high/low/close never change, so this cannot repaint.          |
//|                                                                    |
//|  Timeframe-flip safety: structure is entirely a function of the    |
//|  CHART's own bars (like FVG_Liquidity_Zones.mq5, unlike Important_ |
//|  SR_Levels' timeframe-INDEPENDENT H4/D/W layers) - a different      |
//|  timeframe genuinely means different swings/breaks, so a full      |
//|  rescan on the reinit a timeframe switch triggers is correct, not   |
//|  wasted. InpScanLookbackDays bounds that one-time cost so it can    |
//|  never freeze the terminal regardless of how much history exists.  |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property link      ""
#property version   "1.01"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== Structure ==="
input int      InpPivotWindow      = 5;      // fractal window - bars needed on each side for a swing
                                              // high/low to confirm (same convention as every other
                                              // pivot-based overlay in this project)
input double   InpMinMoveATR       = 1.5;    // a pivot only counts as a new swing if it's at least this
                                              // many ATR away from the previous confirmed swing of the
                                              // SAME type - filters minor noise, same ZigZag-deviation
                                              // style filter MarketStructure_Swings.mq5 already uses

input group "=== Drawing ==="
input color    InpBullBosColor     = clrLime;
input color    InpBearBosColor     = clrRed;
input int      InpLineWidth        = 1;
input bool     InpShowLabel        = true;   // small "BOS" text tag at the break point
input color    InpLabelColor       = clrWhite;
input int      InpLabelFontSize    = 8;
input int      InpBosDrawDays      = 2;      // only lines/labels from roughly the last N days are kept
                                              // on the chart - per direct request ("maybe also for the
                                              // 2 days is fine"). The underlying swing-tracking state
                                              // still needs more history than this to know what the
                                              // current swing high/low actually is; this only limits
                                              // what stays DRAWN.

input group "=== General ==="
input int      InpScanLookbackDays = 30;     // how far back the initial backfill scans, in days of the
                                              // CHART's own timeframe - bounds the one-time cost on
                                              // attach/reinit (see this file's own header comment).
input int      InpAtrPeriod        = 14;

//+------------------------------------------------------------------+
string   g_pfx = "MSB_";
int      g_atrHandle = INVALID_HANDLE;
datetime g_lastBarTime = 0;

double   g_swingHighPrice = 0.0;
datetime g_swingHighTime  = 0;
bool     g_swingHighBroken = true;   // true until a real swing high exists to break
double   g_swingLowPrice  = 0.0;
datetime g_swingLowTime   = 0;
bool     g_swingLowBroken  = true;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpPivotWindow <= 0)
     {
      Print("MarketStructure_Break: InpPivotWindow must be >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpAtrPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("MarketStructure_Break: failed to create ATR handle.");
      return(INIT_FAILED);
     }
   g_lastBarTime      = 0;
   g_swingHighPrice   = 0.0;
   g_swingHighTime    = 0;
   g_swingHighBroken  = true;
   g_swingLowPrice    = 0.0;
   g_swingLowTime     = 0;
   g_swingLowBroken   = true;
   PrintFormat("MarketStructure_Break v1.01 OnInit: %s %s  pivotWindow=%d  minMoveATR=%.2f  drawDays=%d",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpPivotWindow, InpMinMoveATR, InpBosDrawDays);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_pfx);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
void DrawBosLine(const bool bullish, const datetime t1, const datetime t2, const double price)
  {
   string id = g_pfx + "ln_" + (bullish ? "up_" : "dn_") + IntegerToString((long)t2);
   color col = bullish ? InpBullBosColor : InpBearBosColor;
   if(ObjectFind(0, id) < 0)
     {
      if(!ObjectCreate(0, id, OBJ_TREND, 0, t1, price, t2, price))
        {
         PrintFormat("MarketStructure_Break: ObjectCreate FAILED for %s - error %d", id, GetLastError());
         return;
        }
      ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, id, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, id, OBJPROP_RAY_RIGHT, false);
     }
   ObjectSetInteger(0, id, OBJPROP_COLOR, col);
   ObjectSetInteger(0, id, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(0, id, OBJPROP_WIDTH, InpLineWidth);
   ObjectSetString(0, id, OBJPROP_TOOLTIP,
                    (bullish ? "Bullish BOS @ " : "Bearish BOS @ ") + DoubleToString(price, _Digits));

   if(InpShowLabel)
     {
      string lbl = g_pfx + "lbl_" + (bullish ? "up_" : "dn_") + IntegerToString((long)t2);
      if(ObjectFind(0, lbl) < 0)
        {
         ObjectCreate(0, lbl, OBJ_TEXT, 0, t2, price);
         ObjectSetInteger(0, lbl, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, lbl, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, lbl, OBJPROP_ANCHOR, bullish ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER);
        }
      ObjectSetString(0, lbl, OBJPROP_TEXT, " BOS");
      ObjectSetInteger(0, lbl, OBJPROP_COLOR, InpLabelColor);
      ObjectSetInteger(0, lbl, OBJPROP_FONTSIZE, InpLabelFontSize);
     }
  }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Object names are always g_pfx + ("ln_"|"lbl_") + ("up_"|"dn_") +  |
//| the break bar's time, baked in as an integer - one of these four   |
//| fixed prefixes always matches exactly, so the time is just         |
//| whatever's left after stripping it off.                            |
//+------------------------------------------------------------------+
void PruneOldBos(const datetime lastBarTime)
  {
   if(InpBosDrawDays <= 0) return;
   datetime cutoff = lastBarTime - (datetime)((long)InpBosDrawDays * 86400);
   string prefixes[4] = { "ln_up_", "ln_dn_", "lbl_up_", "lbl_dn_" };
   int total = ObjectsTotal(0, 0, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, g_pfx) != 0) continue;
      string rest = StringSubstr(nm, StringLen(g_pfx));
      datetime t = 0;
      for(int p = 0; p < 4; p++)
        {
         if(StringFind(rest, prefixes[p]) == 0)
           {
            t = (datetime)StringToInteger(StringSubstr(rest, StringLen(prefixes[p])));
            break;
           }
        }
      if(t > 0 && t < cutoff) ObjectDelete(0, nm);
     }
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   int w = InpPivotWindow;
   int minBars = 2 * w + 10;
   if(rates_total < minBars) return(0);

   //--- v1.00: only do the (cheap, but still real) scan/draw work once
   //--- per new CLOSED bar - a closed bar's high/low/close never
   //--- change, so re-running this on every tick within the same bar
   //--- would just repeat identical work for nothing. Same once-per-bar
   //--- gate used throughout this project (MarketStructure_Swings,
   //--- TradePanel_EA's CheckNewBar, etc).
   //--- v1.01 FIX (Opus audit - real bugs, confirmed by hand-trace):
   //--- (a) g_lastBarTime used to be committed BEFORE the ATR CopyBuffer
   //--- below was confirmed to succeed - a transient "not ready yet" on
   //--- the very first tick after attach/reinit (routine, especially
   //--- right after a timeframe switch) got silently treated as "this
   //--- bar is done", so prev_calculated went non-zero with NOTHING
   //--- ever actually scanned - no historical BOS lines, ever, until the
   //--- next genuinely new bar. Now only committed after a successful
   //--- ATR read.
   //--- (b) `from` used to be a fixed "last 3 bars" window regardless of
   //--- prev_calculated - after any gap longer than that (reconnect,
   //--- missed ticks), bars in between were silently never scanned, with
   //--- no rescan ever triggered. Now derived from prev_calculated
   //--- itself, so it always covers however many bars actually elapsed.
   //--- (c) the pivot loop used to run up to i < rates_total-w, which
   //--- lets i+w reach rates_total-1 - the STILL-FORMING bar, whose
   //--- high/low change every tick. A bar got judged a confirmed pivot
   //--- against a forming neighbor's momentary value, and once accepted
   //--- it was never un-accepted even after that neighbor's real close
   //--- turned out different. Loop now stops one bar earlier so i+w
   //--- can never reach the forming bar.
   //--- (d) the break check used to run ONCE, after the loop, only
   //--- against the single newest closed bar - so a backfill/reinit drew
   //--- NO historical BOS lines at all (every break that happened during
   //--- the scanned window was skipped), and could draw a FALSE break
   //--- on the attach bar for a swing that was actually broken much
   //--- earlier in history. Moved inside the loop so every bar is
   //--- checked against the swing state as it stood at that exact point
   //--- in time, in order - exactly how Fib_Golden_Zone.mq5/
   //--- VolumeProfile_Leg.mq5 already did it correctly.
   bool freshAttach = (prev_calculated <= 0);
   int lookbackBars = (InpScanLookbackDays > 0)
                       ? (int)((long)InpScanLookbackDays * 86400 / PeriodSeconds(PERIOD_CURRENT)) + minBars
                       : rates_total;
   //--- nothing new since the last call (no new bar formed) - the loop
   //--- below would naturally process zero bars anyway, but skip the
   //--- ATR fetch too rather than pay for it on every tick for nothing.
   if(!freshAttach && rates_total <= prev_calculated) return(rates_total);
   int from = freshAttach ? MathMax(w, rates_total - lookbackBars) : MathMax(w, prev_calculated - 1 - w);
   if(freshAttach)
     {
      ObjectsDeleteAll(0, g_pfx);
      g_swingHighPrice = 0.0; g_swingHighTime = 0; g_swingHighBroken = true;
      g_swingLowPrice  = 0.0; g_swingLowTime  = 0; g_swingLowBroken  = true;
     }

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   int atrCount = rates_total - from;
   if(CopyBuffer(g_atrHandle, 0, 0, atrCount, atrBuf) < atrCount)
      return(0);   // ATR not ready yet - retry next tick, prev_calculated stays 0

   for(int i = MathMax(from, w); i < rates_total - 1 - w; i++)
     {
      double atrHere = atrBuf[rates_total - 1 - i];
      if(atrHere == EMPTY_VALUE || atrHere <= 0.0) continue;
      double minMove = InpMinMoveATR * atrHere;

      bool isPeak = true, isTrough = true;
      for(int k = 1; k <= w; k++)
        {
         if(high[i] < high[i - k] || high[i] <= high[i + k]) isPeak = false;
         if(low[i]  > low[i - k]  || low[i]  >= low[i + k])  isTrough = false;
         if(!isPeak && !isTrough) break;
        }

      //--- break check FIRST, against the swing state as it stood going
      //--- into this bar - so a swing that forms and is broken within
      //--- the same handful of bars is still resolved in the right order
      if(!g_swingHighBroken && g_swingHighTime != 0 && close[i] > g_swingHighPrice)
        {
         g_swingHighBroken = true;
         DrawBosLine(true, g_swingHighTime, time[i], g_swingHighPrice);
        }
      if(!g_swingLowBroken && g_swingLowTime != 0 && close[i] < g_swingLowPrice)
        {
         g_swingLowBroken = true;
         DrawBosLine(false, g_swingLowTime, time[i], g_swingLowPrice);
        }

      //--- a new pivot only replaces the tracked swing if it's at least
      //--- minMove away from the CURRENTLY tracked swing of the same
      //--- type - otherwise it's just noise near the same level, not a
      //--- genuinely new swing point (same ZigZag-deviation filter
      //--- MarketStructure_Swings.mq5 already uses). Replacing resets
      //--- "broken" to false since this is a fresh, unbroken level.
      if(isPeak && (g_swingHighTime == 0 || MathAbs(high[i] - g_swingHighPrice) >= minMove))
        {
         g_swingHighPrice  = high[i];
         g_swingHighTime   = time[i];
         g_swingHighBroken = false;
        }
      if(isTrough && (g_swingLowTime == 0 || MathAbs(low[i] - g_swingLowPrice) >= minMove))
        {
         g_swingLowPrice  = low[i];
         g_swingLowTime   = time[i];
         g_swingLowBroken = false;
        }
     }

   g_lastBarTime = time[rates_total - 1];
   PruneOldBos(g_lastBarTime);
   return(rates_total);
  }
