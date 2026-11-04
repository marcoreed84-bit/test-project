//+------------------------------------------------------------------+
//|                                        Session_News_Overlay.mq5  |
//|  Shades the Asian/London/New York sessions (and their overlap -  |
//|  historically the most-traded window) as light background blocks,|
//|  DST-aware, plus thin markers for scheduled high-impact news     |
//|  events pulled from MT5's own Economic Calendar.                 |
//|                                                                    |
//|  Session hours are the commonly-cited industry-standard local     |
//|  open/close times (Tokyo 00:00-09:00 JST, London 08:00-17:00 UK   |
//|  local, New York 08:00-17:00 US Eastern local) - general market   |
//|  structure, not derived from any backtest in this project.        |
//|                                                                    |
//|  IMPORTANT: InpServerUtcOffsetHours/InpServerFollowsDST are your  |
//|  OWN broker's server-clock settings, not guessed here - confirm   |
//|  them against XM's published server time before trusting the     |
//|  shading's exact edges.                                           |
//|                                                                    |
//|  v1.04 (user report: too dark, overpowers other indicators, news  |
//|  text overlapping):                                               |
//|   - Z-order: blocks/markers are now created once and moved in     |
//|     place, never delete+re-created per bar (that made them the    |
//|     newest background objects, painted over VolumeProfile's).     |
//|     OBJPROP_ZORDER is click priority, NOT paint order - not used. |
//|   - Colours: lighter but desaturated tints (no alpha in MT5 fills).|
//|   - News text: per-event floating OBJ_TEXT labels removed; events |
//|     are listed in a stacked top-right corner panel instead.       |
//+------------------------------------------------------------------+
#property copyright "Internal"
#property version   "1.04"
#property indicator_chart_window
#property indicator_plots 0
#property indicator_buffers 1

#define SN_PFX "SNO_"

input group "=== Sessions ==="
input bool   InpShowSessions         = true;
input bool   InpShowAsian            = true;
//--- v1.04 colour reasoning. OBJ_RECTANGLE + OBJPROP_FILL has NO alpha
//--- channel in MT5 - a filled block is fully opaque, so "light tint" can
//--- only come from the RGB value itself. v1.00 (12,12,30 etc.) was
//--- invisible; v1.01 (35,35,75 / 25,70,25 / 75,30,30 / 80,80,25) read as
//--- heavy solid colour blocks. What made v1.01 heavy was mostly
//--- SATURATION, not brightness: one channel ~2-3x the others (25,70,25)
//--- reads as "a green slab", not "a tinted background". Per the user's
//--- direct follow-up ("make the blocks very light, light colours") these
//--- are LIGHTER than v1.01 (every channel 55-95) but much less saturated
//--- (max-min channel spread ~30-40 instead of ~45-55): a pale, greyish
//--- tint with just enough hue to tell the sessions apart. The other half
//--- of "doesn't overpower" is z-order (see DrawSessionBlock) - once the
//--- blocks stop being re-created every bar they stay underneath other
//--- indicators' background objects instead of painting over them.
input color  InpAsianColor           = C'58,62,95';   // pale slate blue
input bool   InpShowLondon           = true;
input color  InpLondonColor          = C'58,90,64';   // pale sage green
input bool   InpShowNewYork          = true;
input color  InpNewYorkColor         = C'95,62,62';   // pale dusty rose
input bool   InpShowOverlap          = true;      // London/NY overlap - historically the highest-volume window
input color  InpOverlapColor         = C'95,90,58';   // pale sand
input int    InpDaysBack             = 6;         // how many past calendar days to shade
input int    InpDaysForward          = 1;

input group "=== Broker server clock (confirm against your broker) ==="
input int    InpServerUtcOffsetHours = 2;         // broker server's STANDARD (winter) UTC offset, e.g. XM is commonly GMT+2 winter
input bool   InpServerFollowsDST     = true;       // true if your broker shifts +1h with US DST (most do) - check broker's own notice if unsure

input group "=== News (MT5 Economic Calendar) ==="
input bool   InpShowNews             = true;
input string InpNewsCurrencies       = "USD";      // comma-separated, e.g. "USD,EUR"
input int    InpNewsMinImportance    = 2;          // 0=low 1=medium 2=high
input color  InpNewsColor            = clrOrange;
input int    InpNewsRefreshMinutes   = 15;
input int    InpNewsWindowDaysBack   = 1;
input int    InpNewsWindowDaysFwd    = 5;
input int    InpNewsPanelRows        = 8;          // v1.04: max upcoming events listed in the corner panel
input int    InpNewsPanelKeepMins    = 60;         // keep an already-released event listed this many minutes
input int    InpNewsPanelX           = 10;         // panel offset from the top-right corner, pixels
input int    InpNewsPanelY           = 20;
input color  InpNewsPanelColor       = C'200,200,200';

#define SN_PANEL_MAX 20     // hard cap on panel rows (cache size)

double g_dummy[];
datetime g_lastSessionBar = 0;
datetime g_lastNewsRefresh = 0;
bool g_firstCalc = true;
int  g_newsMarkersPrev = 0;   // v1.04: marker count from the last refresh, to prune leftovers
bool   g_panelCreated[SN_PANEL_MAX];   // v1.04: corner-panel row cache (DashLabel idiom)
string g_panelText[SN_PANEL_MAX];
color  g_panelColor[SN_PANEL_MAX];

int OnInit()
  {
   SetIndexBuffer(0, g_dummy, INDICATOR_CALCULATIONS);
   IndicatorSetString(INDICATOR_SHORTNAME, "Session/News Overlay v1.04");
   g_firstCalc = true;
   g_lastSessionBar = 0;
   g_lastNewsRefresh = 0;
   g_newsMarkersPrev = 0;
   //--- globals survive an OnDeinit/OnInit cycle (input change, TF switch)
   //--- while OnDeinit has deleted the objects - reset the panel cache so
   //--- every row is re-created, not skipped as "unchanged".
   for(int i = 0; i < SN_PANEL_MAX; i++) { g_panelCreated[i] = false; g_panelText[i] = ""; g_panelColor[i] = clrNONE; }
   if(InpShowNews)
     {
      EventSetTimer(MathMax(60, InpNewsRefreshMinutes * 60));
      RebuildNews();   // v1.03: don't make the user wait InpNewsRefreshMinutes for the first status
     }
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, SN_PFX);
  }

//--- v1.00: US DST (2nd Sunday March - 1st Sunday November), date-level
//--- approximation (ignores the exact 2am transition hour, fine for
//--- shading purposes). EU/UK DST: last Sunday March - last Sunday Oct.
bool IsUsDst(const datetime t)
  {
   MqlDateTime d; TimeToStruct(t, d);
   int year = d.year;
   datetime marStart = StringToTime(IntegerToString(year) + ".03.01 00:00");
   MqlDateTime m; TimeToStruct(marStart, m);
   int marFirstDow = m.day_of_week;                       // 0=Sun
   int secondSundayMar = 1 + ((7 - marFirstDow) % 7) + 7;
   datetime dstStart = StringToTime(IntegerToString(year) + ".03." + IntegerToString(secondSundayMar) + " 02:00");

   datetime novStart = StringToTime(IntegerToString(year) + ".11.01 00:00");
   MqlDateTime n; TimeToStruct(novStart, n);
   int novFirstDow = n.day_of_week;
   int firstSundayNov = 1 + ((7 - novFirstDow) % 7);
   datetime dstEnd = StringToTime(IntegerToString(year) + ".11." + IntegerToString(firstSundayNov) + " 02:00");

   return(t >= dstStart && t < dstEnd);
  }

bool IsEuDst(const datetime t)
  {
   MqlDateTime d; TimeToStruct(t, d);
   int year = d.year;
   datetime marEnd = StringToTime(IntegerToString(year) + ".03.31 23:59");
   MqlDateTime m; TimeToStruct(marEnd, m);
   int lastSundayMar = 31 - (m.day_of_week);
   datetime dstStart = StringToTime(IntegerToString(year) + ".03." + IntegerToString(lastSundayMar) + " 01:00");

   datetime octEnd = StringToTime(IntegerToString(year) + ".10.31 23:59");
   MqlDateTime o; TimeToStruct(octEnd, o);
   int lastSundayOct = 31 - (o.day_of_week);
   datetime dstEnd = StringToTime(IntegerToString(year) + ".10." + IntegerToString(lastSundayOct) + " 01:00");

   return(t >= dstStart && t < dstEnd);
  }

//--- Converts an hour-of-day in a named local session's own time zone to
//--- UTC, for the calendar day that dayStartUtc (00:00 UTC) falls on.
datetime LocalHourToUtc(const datetime dayStartUtc, const int localHour, const string zone)
  {
   if(zone == "JST") return(dayStartUtc + (datetime)((localHour - 9) * 3600));
   if(zone == "UK")
     {
      bool dst = IsEuDst(dayStartUtc + (datetime)(localHour * 3600));
      int offset = dst ? 1 : 0;   // BST = UTC+1, GMT = UTC+0
      return(dayStartUtc + (datetime)((localHour - offset) * 3600));
     }
   if(zone == "US_EASTERN")
     {
      bool dst = IsUsDst(dayStartUtc + (datetime)(localHour * 3600));
      int offset = dst ? 4 : 5;   // EDT = UTC-4, EST = UTC-5
      return(dayStartUtc + (datetime)((localHour + offset) * 3600));
     }
   return(dayStartUtc + (datetime)(localHour * 3600));
  }

//--- v1.04 Z-ORDER ROOT CAUSE. OBJPROP_BACK=true only puts an object in
//--- the layer behind the price bars; AMONG background objects MT5 paints
//--- in CREATION order (newest on top). OBJPROP_ZORDER does NOT change
//--- that - per the MQL5 reference it is the priority for receiving
//--- CHARTEVENT_CLICK, not a paint order (this repo already established
//--- the same thing the hard way: see the ZORDER notes in Aurelius_EA.mq5
//--- and AuRebound_EA.mq5), so it is deliberately not used here as a fix.
//--- The real bug: v1.00-v1.03 RebuildSessions() did ObjectsDeleteAll on
//--- every block and re-created them on every new bar (and RebuildNews
//--- did the same to the news markers every refresh), which made this
//--- overlay's opaque rectangles the NEWEST background objects on the
//--- chart every bar - i.e. painted over VolumeProfile_Session's BACK
//--- profile rectangles/POC/VA lines. Fix: create each block ONCE and
//--- only move/recolour it in place afterwards, so it keeps its original
//--- (old) creation slot, and anything another indicator (re)creates -
//--- VolumeProfile_Session rebuilds its column on each new source bar -
//--- lands above it. Limit: if this overlay is attached AFTER another
//--- indicator, that indicator's objects sit under the blocks until it
//--- next re-creates them (VP: next bar); removing/re-adding the other
//--- indicator, or attaching this overlay first, fixes it immediately.
//--- Non-BACK objects (S/R HLINEs/text, dashboard labels) are always
//--- painted above every BACK object regardless of order.
void DrawSessionBlock(const string name, const datetime t1, const datetime t2, const color col)
  {
   if(t2 <= t1) { if(ObjectFind(0, name) >= 0) ObjectDelete(0, name); return; }
   double priceMax = ChartGetDouble(0, CHART_PRICE_MAX, 0);
   double priceMin = ChartGetDouble(0, CHART_PRICE_MIN, 0);
   if(priceMax <= priceMin) return;
   double pad = (priceMax - priceMin) * 2.0;   // generous pad so zoom/scroll never exposes a gap

   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, priceMax + pad, t2, priceMin - pad);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
     }
   ObjectSetInteger(0, name, OBJPROP_TIME, 0, t1);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 0, priceMax + pad);
   ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 1, priceMin - pad);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
  }

void RebuildSessions()
  {
   //--- v1.04: no ObjectsDeleteAll here any more (that was the z-order bug,
   //--- see DrawSessionBlock). Names are keyed by day OFFSET, so the same
   //--- InpDaysBack+InpDaysForward+1 sets of objects are simply moved to
   //--- the new days when the date rolls over - nothing new is ever created
   //--- after the first pass.
   if(!InpShowSessions) return;

   datetime todayUtc = (datetime)((TimeGMT() / 86400) * 86400);

   for(int dOff = -InpDaysBack; dOff <= InpDaysForward; dOff++)
     {
      datetime dayStartUtc = todayUtc + (datetime)(dOff * 86400);
      string tag = IntegerToString(dOff);

      datetime asianStart = LocalHourToUtc(dayStartUtc, 0, "JST");
      datetime asianEnd   = LocalHourToUtc(dayStartUtc, 9, "JST");
      datetime londonStart = LocalHourToUtc(dayStartUtc, 8, "UK");
      datetime londonEnd   = LocalHourToUtc(dayStartUtc, 17, "UK");
      datetime nyStart = LocalHourToUtc(dayStartUtc, 8, "US_EASTERN");
      datetime nyEnd   = LocalHourToUtc(dayStartUtc, 17, "US_EASTERN");

      //--- broker server time = UTC + (standard offset, +1 more if the
      //--- broker itself is currently observing DST)
      bool brokerDst = InpServerFollowsDST && IsUsDst(dayStartUtc);
      int brokerOffsetSec = (InpServerUtcOffsetHours + (brokerDst ? 1 : 0)) * 3600;

      if(InpShowAsian)
         DrawSessionBlock(SN_PFX + "sess_asia_" + tag, asianStart + brokerOffsetSec,
                           asianEnd + brokerOffsetSec, InpAsianColor);
      if(InpShowLondon)
         DrawSessionBlock(SN_PFX + "sess_ldn_" + tag, londonStart + brokerOffsetSec,
                           londonEnd + brokerOffsetSec, InpLondonColor);
      if(InpShowNewYork)
         DrawSessionBlock(SN_PFX + "sess_ny_" + tag, nyStart + brokerOffsetSec,
                           nyEnd + brokerOffsetSec, InpNewYorkColor);
      if(InpShowOverlap)
        {
         datetime ovStart = (datetime)MathMax((long)londonStart, (long)nyStart);
         datetime ovEnd   = (datetime)MathMin((long)londonEnd, (long)nyEnd);
         //--- always called (DrawSessionBlock deletes the object itself if
         //--- the range is empty) so no stale in-place block can linger
         DrawSessionBlock(SN_PFX + "sess_ovlp_" + tag, ovStart + brokerOffsetSec,
                           ovEnd + brokerOffsetSec, InpOverlapColor);
        }
     }
  }

bool CurrencyWanted(const string cur)
  {
   string parts[];
   int n = StringSplit(InpNewsCurrencies, ',', parts);
   for(int i = 0; i < n; i++)
     {
      //--- StringTrimLeft/Right trim IN PLACE and return an int (new
      //--- length), not a chainable string - must be two statements.
      StringTrimLeft(parts[i]);
      StringTrimRight(parts[i]);
      if(parts[i] == cur) return(true);
     }
   return(false);
  }

//--- v1.03: visible proof-of-life, per direct question ("will it give
//--- some kind of indication if it's actually seeing news events") -
//--- a silent "0 markers shown" was indistinguishable from "feed not
//--- working" vs. "genuinely nothing high-impact this week". Now both
//--- Prints to the Experts log AND a small on-chart status label.
void SetNewsStatus(const string text, const color col)
  {
   string nm = SN_PFX + "news_status";
   if(ObjectFind(0, nm) < 0)
     {
      ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_LOWER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 8);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 10);
     }
   ObjectSetString(0, nm, OBJPROP_TEXT, text);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
  }

//--- v1.04: one row of the corner news panel. Same idiom as
//--- SuperTrend_MTF.mq5's DashLabel(): pixel-anchored OBJ_LABEL, created
//--- once, and ObjectSet* only touched when the cached text/colour
//--- actually changed. Rows are stacked by a fixed line height, so they
//--- can never overlap each other no matter how close the events are.
void NewsPanelRow(const int idx, const string text, const color col)
  {
   if(idx < 0 || idx >= SN_PANEL_MAX) return;
   string nm = SN_PFX + "npanel_" + IntegerToString(idx);
   const int lineH = 14;
   if(!g_panelCreated[idx] || ObjectFind(0, nm) < 0)
     {
      ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, false);
      ObjectSetString(0, nm, OBJPROP_FONT, "Consolas");   // monospaced so the time/currency columns line up
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 8);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, InpNewsPanelX);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, InpNewsPanelY + idx * lineH);
      g_panelCreated[idx] = true;
      g_panelText[idx] = "";       // never equal to t below (t is never empty) - forces the first write
      g_panelColor[idx] = clrNONE;
     }
   //--- an empty OBJ_LABEL text renders as the literal "Label" - use a space
   string t = (text == "") ? " " : text;
   if(g_panelText[idx] != t)   { ObjectSetString(0, nm, OBJPROP_TEXT, t);    g_panelText[idx] = t; }
   if(g_panelColor[idx] != col) { ObjectSetInteger(0, nm, OBJPROP_COLOR, col); g_panelColor[idx] = col; }
  }

//--- v1.04: deletes only marker slots that the latest refresh no longer
//--- uses (instead of wiping and re-creating every marker every refresh).
void PruneNewsMarkers(const int keep)
  {
   for(int k = keep; k < g_newsMarkersPrev; k++)
      ObjectDelete(0, SN_PFX + "news_" + IntegerToString(k));
   g_newsMarkersPrev = keep;
  }

void RebuildNews()
  {
   //--- v1.04: markers are no longer ObjectsDeleteAll'd + re-created every
   //--- refresh (that put them back on top of other indicators' background
   //--- objects - see DrawSessionBlock). They're updated in place by slot
   //--- index, and only slots beyond this refresh's count are deleted.
   //--- The old per-event OBJ_TEXT labels (news_lbl_*) are gone entirely.
   if(!InpShowNews) return;

   datetime from = TimeCurrent() - (datetime)(InpNewsWindowDaysBack * 86400);
   datetime to   = TimeCurrent() + (datetime)(InpNewsWindowDaysFwd * 86400);

   MqlCalendarValue values[];
   int n = CalendarValueHistory(values, from, to, NULL, NULL);
   if(n <= 0)
     {
      //--- n<0 is a real CalendarValueHistory failure (calendar feed not
      //--- synced/no internet); n==0 means the call worked but found
      //--- literally zero events in the window - different problems.
      string msg = (n < 0) ? StringFormat("News: calendar feed error (GetLastError=%d) - check Toolbox > Calendar tab", GetLastError())
                            : "News: calendar OK, 0 events in window";
      PrintFormat("Session_News_Overlay: %s", msg);
      SetNewsStatus(msg, (n < 0) ? clrRed : clrGray);
      PruneNewsMarkers(0);
      NewsPanelRow(0, "NEWS: none", InpNewsPanelColor);
      for(int r = 1; r < SN_PANEL_MAX; r++) if(g_panelCreated[r]) NewsPanelRow(r, "", InpNewsPanelColor);
      return;
     }

   double priceMax = ChartGetDouble(0, CHART_PRICE_MAX, 0);
   double priceMin = ChartGetDouble(0, CHART_PRICE_MIN, 0);
   if(priceMax <= priceMin) return;
   double pad = (priceMax - priceMin) * 2.0;

   int panelRows = InpNewsPanelRows;                    // row 0 is the header
   if(panelRows < 1) panelRows = 1;
   if(panelRows > SN_PANEL_MAX - 1) panelRows = SN_PANEL_MAX - 1;
   int keepMins = (InpNewsPanelKeepMins > 0) ? InpNewsPanelKeepMins : 0;
   datetime keepFrom = TimeCurrent() - (datetime)(keepMins * 60);
   string dows[7] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
   datetime pTime[];
   string   pText[];
   int      pCount = 0;

   int shown = 0;
   for(int i = 0; i < n && shown < 200; i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev)) continue;
      if((int)ev.importance < InpNewsMinImportance) continue;

      MqlCalendarCountry country;
      if(!CalendarCountryById(ev.country_id, country)) continue;
      if(!CurrencyWanted(country.currency)) continue;

      datetime t1 = values[i].time;
      datetime t2 = t1 + 900;   // a 15-minute-wide marker, not a single line - easier to see at a glance
      string nm = SN_PFX + "news_" + IntegerToString(shown);

      //--- created once per slot, moved in place afterwards (z-order, see above)
      if(ObjectFind(0, nm) < 0)
        {
         ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, priceMax + pad, t2, priceMin - pad);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, nm, OBJPROP_FILL, true);
         ObjectSetInteger(0, nm, OBJPROP_BACK, true);
         ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
        }
      ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t1);
      ObjectSetDouble(0, nm, OBJPROP_PRICE, 0, priceMax + pad);
      ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t2);
      ObjectSetDouble(0, nm, OBJPROP_PRICE, 1, priceMin - pad);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, InpNewsColor);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP, country.currency + " " + ev.name + "  " + TimeToString(t1, TIME_DATE | TIME_MINUTES));
      shown++;

      //--- panel candidates: upcoming (or just-released) events only
      if(t1 >= keepFrom)
        {
         string evName = ev.name;
         if(StringLen(evName) > 38) evName = StringSubstr(evName, 0, 37) + "~";
         MqlDateTime d; TimeToStruct(t1, d);
         ArrayResize(pTime, pCount + 1, 64);
         ArrayResize(pText, pCount + 1, 64);
         pTime[pCount] = t1;
         pText[pCount] = StringFormat("%s %02d:%02d  %s  %s", dows[d.day_of_week], d.hour, d.min, country.currency, evName);
         pCount++;
        }
     }
   PruneNewsMarkers(shown);

   //--- CalendarValueHistory's order isn't documented as time-sorted -
   //--- small insertion sort (at most a few hundred items, once per refresh)
   for(int a = 1; a < pCount; a++)
     {
      datetime kt = pTime[a]; string ks = pText[a];
      int b = a - 1;
      while(b >= 0 && pTime[b] > kt) { pTime[b + 1] = pTime[b]; pText[b + 1] = pText[b]; b--; }
      pTime[b + 1] = kt; pText[b + 1] = ks;
     }

   NewsPanelRow(0, StringFormat("NEWS (%s, server time)%s", InpNewsCurrencies,
                                pCount > panelRows ? StringFormat("  +%d more", pCount - panelRows) : ""),
                InpNewsPanelColor);
   for(int r = 0; r < SN_PANEL_MAX - 1; r++)
     {
      if(r < panelRows && r < pCount)
         NewsPanelRow(r + 1, pText[r], pTime[r] < TimeCurrent() ? clrGray : InpNewsColor);   // released = grey
      else if(g_panelCreated[r + 1])
         NewsPanelRow(r + 1, "", InpNewsPanelColor);   // blank leftover rows, don't leave stale text
     }
   if(pCount == 0) NewsPanelRow(1, "no upcoming events in window", clrGray);

   string msg = StringFormat("News: %d event(s) shown (of %d total in window, currencies=%s, min importance=%d)",
                              shown, n, InpNewsCurrencies, InpNewsMinImportance);
   PrintFormat("Session_News_Overlay: %s", msg);
   SetNewsStatus(msg, shown > 0 ? InpNewsColor : clrGray);
  }

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   if(rates_total < 1) return(0);

   datetime lastBar = time[rates_total - 1];
   if(g_firstCalc || lastBar != g_lastSessionBar)
     {
      RebuildSessions();
      g_lastSessionBar = lastBar;
      g_firstCalc = false;
      ChartRedraw(0);
     }
   return(rates_total);
  }

void OnTimer()
  {
   if(InpShowNews)
     {
      RebuildNews();
      ChartRedraw(0);
     }
  }
