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
//+------------------------------------------------------------------+
#property copyright "Internal"
#property version   "1.02"
#property indicator_chart_window
#property indicator_plots 0
#property indicator_buffers 1

#define SN_PFX "SNO_"

input group "=== Sessions ==="
input bool   InpShowSessions         = true;
input bool   InpShowAsian            = true;
input color  InpAsianColor           = C'35,35,75';   // v1.01: brightened - the old near-black values
                                                        // (12,12,30 etc.) were essentially invisible
                                                        // against a black chart background, not "lightly
                                                        // shaded" at all - real miss, not a deliberate choice
input bool   InpShowLondon           = true;
input color  InpLondonColor          = C'25,70,25';
input bool   InpShowNewYork          = true;
input color  InpNewYorkColor         = C'75,30,30';
input bool   InpShowOverlap          = true;      // London/NY overlap - historically the highest-volume window
input color  InpOverlapColor         = C'80,80,25';
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

double g_dummy[];
datetime g_lastSessionBar = 0;
datetime g_lastNewsRefresh = 0;
bool g_firstCalc = true;

int OnInit()
  {
   SetIndexBuffer(0, g_dummy, INDICATOR_CALCULATIONS);
   IndicatorSetString(INDICATOR_SHORTNAME, "Session/News Overlay v1.00");
   g_firstCalc = true;
   g_lastSessionBar = 0;
   g_lastNewsRefresh = 0;
   if(InpShowNews) EventSetTimer(MathMax(60, InpNewsRefreshMinutes * 60));
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

void DrawSessionBlock(const string name, const datetime t1, const datetime t2, const color col)
  {
   if(t2 <= t1) return;
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
   ObjectsDeleteAll(0, SN_PFX + "sess_");
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
         if(ovEnd > ovStart)
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

void RebuildNews()
  {
   ObjectsDeleteAll(0, SN_PFX + "news_");
   if(!InpShowNews) return;

   datetime from = TimeCurrent() - (datetime)(InpNewsWindowDaysBack * 86400);
   datetime to   = TimeCurrent() + (datetime)(InpNewsWindowDaysFwd * 86400);

   MqlCalendarValue values[];
   int n = CalendarValueHistory(values, from, to, NULL, NULL);
   if(n <= 0) return;

   double priceMax = ChartGetDouble(0, CHART_PRICE_MAX, 0);
   double priceMin = ChartGetDouble(0, CHART_PRICE_MIN, 0);
   if(priceMax <= priceMin) return;
   double pad = (priceMax - priceMin) * 2.0;

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

      ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, priceMax + pad, t2, priceMin - pad);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_FILL, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, true);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, InpNewsColor);
      ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);

      string lblNm = SN_PFX + "news_lbl_" + IntegerToString(shown);
      ObjectCreate(0, lblNm, OBJ_TEXT, 0, t1, priceMax);
      ObjectSetInteger(0, lblNm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, lblNm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, lblNm, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, lblNm, OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(0, lblNm, OBJPROP_COLOR, InpNewsColor);
      ObjectSetString(0, lblNm, OBJPROP_TEXT, " " + country.currency + " " + ev.name);

      shown++;
     }
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
