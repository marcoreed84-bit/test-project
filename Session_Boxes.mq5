//+------------------------------------------------------------------+
//|                                             Session_Boxes.mq5     |
//|  Standalone indicator - draws one box per calendar day for each   |
//|  of the Asia/London/New York sessions, each its own colour. Pure  |
//|  visual/session-timing overlay - no signals, no implied entries,  |
//|  no "AMD" labelling of which session did what. Per direct         |
//|  discussion: the Accumulation/Manipulation/Distribution story is  |
//|  a narrative applied to these same session boxes after the fact,  |
//|  not something tested or validated in this project - this file    |
//|  only draws the session ranges themselves, nothing more.          |
//|                                                                    |
//|  Session hours are read against each bar's own (broker SERVER)    |
//|  time, exactly like every other time-of-day input in this         |
//|  project - NOT assumed to be UTC. If the boxes don't line up with |
//|  when you actually see each session trading, adjust the hour      |
//|  inputs to match your broker's server-time offset rather than     |
//|  treating the defaults as correct for every broker.                |
//|                                                                    |
//|  Timeframe-flip safety: entirely a function of the CHART's own    |
//|  bars and calendar time (like this project's other new standalone |
//|  indicators, unlike Important_SR_Levels' timeframe-INDEPENDENT     |
//|  H4/D/W layers) - a rescan on a timeframe-switch reinit is         |
//|  correct, bounded by InpDrawDays below.                            |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property link      ""
#property version   "1.01"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "=== General ==="
input int      InpDrawDays   = 10;     // how many calendar days of session boxes to keep on chart - also
                                        // bounds the one-time backfill cost on attach/reinit
input bool     InpShowLabels = true;
input int      InpLabelFontSize = 8;

input group "=== Asia ==="
input bool     InpShowAsia      = true;
input int      InpAsiaStartHour = 0;    // server-time hour, 0-23
input int      InpAsiaEndHour   = 9;    // session runs [start, end) - end hour itself is excluded
input color    InpAsiaColor     = C'25,45,70';

input group "=== London ==="
input bool     InpShowLondon      = true;
input int      InpLondonStartHour = 7;
input int      InpLondonEndHour   = 16;
input color    InpLondonColor     = C'45,65,25';

input group "=== New York ==="
input bool     InpShowNY      = true;
input int      InpNYStartHour = 12;
input int      InpNYEndHour   = 21;
input color    InpNYColor     = C'70,35,45';

//+------------------------------------------------------------------+
struct SessBox
  {
   datetime dayKey;      // the session's own start-of-day anchor, used to find/match this instance
   double   high;
   double   low;
   datetime startTime;
   datetime endTime;
  };

SessBox  g_asia[];
SessBox  g_london[];
SessBox  g_ny[];

string   g_pfx = "SESB_";
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpAsiaStartHour < 0 || InpAsiaStartHour > 23 || InpAsiaEndHour < 0 || InpAsiaEndHour > 24 ||
      InpLondonStartHour < 0 || InpLondonStartHour > 23 || InpLondonEndHour < 0 || InpLondonEndHour > 24 ||
      InpNYStartHour < 0 || InpNYStartHour > 23 || InpNYEndHour < 0 || InpNYEndHour > 24)
     {
      Print("Session_Boxes: hour inputs must be 0-23 (end hour may be 24 for 'through midnight').");
      return(INIT_PARAMETERS_INCORRECT);
     }
   ArrayResize(g_asia, 0);
   ArrayResize(g_london, 0);
   ArrayResize(g_ny, 0);
   g_lastBarTime = 0;
   PrintFormat("Session_Boxes v1.01 OnInit: %s %s  Asia=%02d-%02d  London=%02d-%02d  NY=%02d-%02d  drawDays=%d",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7),
               InpAsiaStartHour, InpAsiaEndHour, InpLondonStartHour, InpLondonEndHour,
               InpNYStartHour, InpNYEndHour, InpDrawDays);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_pfx);
  }

//+------------------------------------------------------------------+
bool InSession(const int hour, const int startHour, const int endHour)
  {
   if(startHour == endHour) return false;
   if(startHour < endHour) return (hour >= startHour && hour < endHour);
   return (hour >= startHour || hour < endHour);   // wraps past midnight
  }

//+------------------------------------------------------------------+
string BoxName(const string tag, const datetime dayKey) { return g_pfx + tag + "_" + IntegerToString((long)dayKey); }

//+------------------------------------------------------------------+
void DrawSessBox(const string tag, const SessBox &b, const color col)
  {
   string nm = BoxName(tag, b.dayKey);
   if(ObjectFind(0, nm) < 0)
     {
      if(!ObjectCreate(0, nm, OBJ_RECTANGLE, 0, b.startTime, b.high, b.endTime, b.low))
        {
         PrintFormat("Session_Boxes: ObjectCreate FAILED for %s - error %d", nm, GetLastError());
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
   ObjectMove(0, nm, 0, b.startTime, b.high);
   ObjectMove(0, nm, 1, b.endTime, b.low);

   if(InpShowLabels)
     {
      string lbl = g_pfx + tag + "lbl_" + IntegerToString((long)b.dayKey);
      if(ObjectFind(0, lbl) < 0)
        {
         ObjectCreate(0, lbl, OBJ_TEXT, 0, b.startTime, b.high);
         ObjectSetInteger(0, lbl, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, lbl, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, lbl, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
         ObjectSetString(0, lbl, OBJPROP_TEXT, " " + tag);
         ObjectSetInteger(0, lbl, OBJPROP_COLOR, col);
         ObjectSetInteger(0, lbl, OBJPROP_FONTSIZE, InpLabelFontSize);
        }
      ObjectSetInteger(0, lbl, OBJPROP_TIME, 0, b.startTime);
      ObjectSetDouble(0, lbl, OBJPROP_PRICE, b.high);
     }
  }

//+------------------------------------------------------------------+
int FindOrCreateBox(SessBox &boxes[], const datetime dayKey, const datetime t)
  {
   for(int k = ArraySize(boxes) - 1; k >= 0; k--)
      if(boxes[k].dayKey == dayKey) return k;
   int n = ArraySize(boxes);
   ArrayResize(boxes, n + 1);
   boxes[n].dayKey    = dayKey;
   boxes[n].high      = -DBL_MAX;
   boxes[n].low       = DBL_MAX;
   boxes[n].startTime = t;
   boxes[n].endTime   = t;
   return n;
  }

//+------------------------------------------------------------------+
void ApplyBar(SessBox &boxes[], const string tag, const color col, const bool enabled,
              const int startHour, const int endHour, const datetime t, const double h, const double l,
              const int hour, const datetime dayStart)
  {
   if(!enabled) return;
   if(!InSession(hour, startHour, endHour)) return;
   //--- a session that wraps past midnight and is currently in the
   //--- "after midnight" half belongs to the PREVIOUS calendar day's
   //--- instance, not today's
   datetime dayKey = (startHour > endHour && hour < endHour) ? dayStart - 86400 : dayStart;
   int idx = FindOrCreateBox(boxes, dayKey, t);
   boxes[idx].high    = MathMax(boxes[idx].high, h);
   boxes[idx].low     = MathMin(boxes[idx].low, l);
   boxes[idx].endTime = t;
   DrawSessBox(tag, boxes[idx], col);
  }

//+------------------------------------------------------------------+
void PruneBoxes(SessBox &boxes[], const string tag, const datetime lastBarTime)
  {
   datetime cutoff = lastBarTime - (datetime)((long)InpDrawDays * 86400);
   for(int k = ArraySize(boxes) - 1; k >= 0; k--)
     {
      if(boxes[k].dayKey < cutoff)
        {
         ObjectDelete(0, BoxName(tag, boxes[k].dayKey));
         ObjectDelete(0, g_pfx + tag + "lbl_" + IntegerToString((long)boxes[k].dayKey));
         boxes[k] = boxes[ArraySize(boxes) - 1];
         ArrayResize(boxes, ArraySize(boxes) - 1);
        }
     }
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   if(rates_total < 2) return(0);

   //--- v1.01 FIX (Opus audit, real bug): `from` used to be a fixed
   //--- "last 3 bars" window regardless of prev_calculated - after any
   //--- gap longer than that (reconnect, missed ticks), bars in between
   //--- were silently never scanned into a session box, with no rescan
   //--- ever triggered. Now derived from prev_calculated itself, so it
   //--- always covers however many bars actually elapsed. Also moved
   //--- g_lastBarTime's commit to after the loop runs (not before) so a
   //--- call that bails out early never falsely marks this bar "done".
   bool freshAttach = (prev_calculated <= 0);
   if(!freshAttach && rates_total <= prev_calculated) return(rates_total);   // nothing new
   int lookbackBars = (int)((long)(InpDrawDays + 1) * 86400 / PeriodSeconds(PERIOD_CURRENT)) + 5;
   int from;
   if(freshAttach)
     {
      ObjectsDeleteAll(0, g_pfx);
      ArrayResize(g_asia, 0);
      ArrayResize(g_london, 0);
      ArrayResize(g_ny, 0);
      from = MathMax(0, rates_total - lookbackBars);
     }
   else
      from = MathMax(0, prev_calculated - 1);

   MqlDateTime dt;
   for(int i = from; i < rates_total - 1; i++)   // rates_total-1 is still forming, process closed bars only
     {
      datetime t = time[i];
      TimeToStruct(t, dt);
      int hour = dt.hour;
      datetime dayStart = t - (datetime)(dt.hour * 3600 + dt.min * 60 + dt.sec);

      ApplyBar(g_asia,   "Asia",   InpAsiaColor,   InpShowAsia,   InpAsiaStartHour,   InpAsiaEndHour,
               t, high[i], low[i], hour, dayStart);
      ApplyBar(g_london, "London", InpLondonColor, InpShowLondon, InpLondonStartHour, InpLondonEndHour,
               t, high[i], low[i], hour, dayStart);
      ApplyBar(g_ny,     "NY",     InpNYColor,     InpShowNY,     InpNYStartHour,     InpNYEndHour,
               t, high[i], low[i], hour, dayStart);
     }

   g_lastBarTime = time[rates_total - 1];
   PruneBoxes(g_asia,   "Asia",   g_lastBarTime);
   PruneBoxes(g_london, "London", g_lastBarTime);
   PruneBoxes(g_ny,     "NY",     g_lastBarTime);

   return(rates_total);
  }
