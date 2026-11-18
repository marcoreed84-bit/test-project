//+------------------------------------------------------------------+
//|                                  EMA84_200_Cross_Logger.mq5      |
//|  Forward-tracking logger, NOT a trading EA - places no real       |
//|  orders, risks no money. Tracks EMA(84)/EMA(200) crossovers on    |
//|  the CLOSED bar across up to 4 timeframes from a SINGLE chart     |
//|  attachment, logs every new cross to a shared CSV the moment it   |
//|  happens, and shows a live panel of each timeframe's last cross   |
//|  and the SIMULATED position it implies (entry at the cross, held  |
//|  until the next opposite cross - same exit rule tested in         |
//|  research/silver_btc/ema84_200_crossover_search.py) - so it can   |
//|  be scored later against genuinely unseen future data, settling   |
//|  "does this actually work" the only way a backtest never can.     |
//|                                                                    |
//|  Attach ONCE to any chart (symbol only matters, timeframe of the  |
//|  chart itself is irrelevant - all 4 tracked timeframes are read   |
//|  via their own bounded recompute, same pattern as SuperTrend_MTF's|
//|  dashboard rows). For a second instrument (e.g. Silver/BTC),      |
//|  attach a second instance on that symbol's chart - all instances  |
//|  share the same CSV log file.                                     |
//+------------------------------------------------------------------+
#property copyright "Internal"
#property version   "1.01"
#property indicator_chart_window
#property indicator_plots 0
#property indicator_buffers 1

#define LOG_FILE "EMA84_200_CrossLog.csv"
#define PFX "EMA84200_"

input group "=== EMA periods ==="
input int    InpFastPeriod       = 84;
input int    InpSlowPeriod       = 200;

input group "=== Timeframes tracked ==="
input ENUM_TIMEFRAMES InpTF1     = PERIOD_M15;
input ENUM_TIMEFRAMES InpTF2     = PERIOD_H1;
input ENUM_TIMEFRAMES InpTF3     = PERIOD_H4;
input ENUM_TIMEFRAMES InpTF4     = PERIOD_D1;
input int    InpLookbackBars     = 200;       // v1.01: how many closed bars back each TF scans on every
                                               // check, to backfill any cross missed while MT5 was
                                               // closed. 200 M15 bars = ~2 days, 200 H4 bars = ~33 days,
                                               // 200 D1 bars = ~200 days - raise it if you expect to
                                               // leave the platform closed longer than that on any
                                               // tracked timeframe, or a gap longer than this will
                                               // silently skip the crosses inside it.

input group "=== Panel ==="
input bool   InpShowPanel        = true;
input int    InpPanelX            = 10;
input int    InpPanelY            = 20;
input color  InpPanelHeaderColor  = clrDodgerBlue;
input color  InpPanelTextColor    = clrWhite;
input color  InpPanelUpColor      = clrLime;
input color  InpPanelDownColor    = clrOrangeRed;
input color  InpPanelBgColor      = clrBlack;
input int    InpPanelWidth        = 230;

double g_dummy[];
bool   g_firstCalc = true;
datetime g_lastBarTime = 0;

ENUM_TIMEFRAMES g_tf[4];
int    g_fastHandle[4];
int    g_slowHandle[4];
datetime g_lastTfBarTime[4];
string g_lastDir[4];      // "UP" / "DOWN" / "" (unknown yet)
datetime g_lastCrossTime[4];
double g_lastCrossPrice[4];
bool   g_tfReady[4];

int OnInit()
  {
   SetIndexBuffer(0, g_dummy, INDICATOR_CALCULATIONS);
   IndicatorSetString(INDICATOR_SHORTNAME,
                       StringFormat("EMA%d/%d Cross Logger", InpFastPeriod, InpSlowPeriod));
   g_firstCalc = true;
   g_lastBarTime = 0;

   g_tf[0] = InpTF1; g_tf[1] = InpTF2; g_tf[2] = InpTF3; g_tf[3] = InpTF4;
   for(int k = 0; k < 4; k++)
     {
      g_fastHandle[k] = INVALID_HANDLE;
      g_slowHandle[k] = INVALID_HANDLE;
      g_lastTfBarTime[k] = 0;
      g_lastDir[k] = "";
      g_lastCrossTime[k] = 0;
      g_lastCrossPrice[k] = 0.0;
      g_tfReady[k] = false;
     }

   if(!FileIsExist(LOG_FILE, FILE_COMMON))
     {
      int h = FileOpen(LOG_FILE, FILE_WRITE | FILE_READ | FILE_CSV | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
      if(h != INVALID_HANDLE)
        {
         FileWrite(h, "datetime_utc", "symbol", "period", "direction", "close_price", "fast_ema", "slow_ema");
         FileClose(h);
        }
     }
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   for(int k = 0; k < 4; k++)
     {
      if(g_fastHandle[k] != INVALID_HANDLE) IndicatorRelease(g_fastHandle[k]);
      if(g_slowHandle[k] != INVALID_HANDLE) IndicatorRelease(g_slowHandle[k]);
     }
   ObjectsDeleteAll(0, PFX);
  }

void LogCross(const datetime t, const string sym, const string per,
              const string dir, const double price, const double ef, const double es)
  {
   int h = FileOpen(LOG_FILE, FILE_WRITE | FILE_READ | FILE_CSV | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
   if(h == INVALID_HANDLE) { Print("EMA Cross Logger: FileOpen failed, error ", GetLastError()); return; }
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(t, TIME_DATE | TIME_SECONDS), sym, per, dir,
             DoubleToString(price, _Digits), DoubleToString(ef, _Digits), DoubleToString(es, _Digits));
   FileClose(h);
   PrintFormat("EMA Cross Logger: %s %s %s cross at %s (%.*f)",
               sym, per, dir, TimeToString(t, TIME_DATE | TIME_SECONDS), _Digits, price);
  }

//--- v1.01: BACKFILL-CAPABLE, per direct constraint ("the trading platform
//--- has to be open all the time?" - no, it doesn't, now). Instead of only
//--- comparing the last 2 closed bars (which would silently miss every
//--- cross that happened while MT5 was closed), this scans back over
//--- InpLookbackBars closed bars each time it runs and logs any cross it
//--- hasn't already logged (tracked via g_lastCrossTime[k] as a watermark).
//--- On reopening MT5 after being closed for a while, the terminal
//--- auto-downloads the missed price history from the broker, so this
//--- reconstructs what actually happened from real historical bars -
//--- not a guess - rather than only catching crosses live, tick by tick.
//--- Persistent handles (created once, released once in OnDeinit - the
//--- handle-churn bug this project already fixed elsewhere), only
//--- re-scanned when THAT timeframe's own last bar actually changes.
void CheckTimeframe(const int k)
  {
   ENUM_TIMEFRAMES tf = g_tf[k];
   datetime tfBarTime = iTime(_Symbol, tf, 0);
   if(tfBarTime <= 0) return;
   if(g_tfReady[k] && tfBarTime == g_lastTfBarTime[k]) return;   // no new bar on this TF yet
   bool freshTf = !g_tfReady[k];
   g_lastTfBarTime[k] = tfBarTime;

   if(g_fastHandle[k] == INVALID_HANDLE) g_fastHandle[k] = iMA(_Symbol, tf, InpFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_slowHandle[k] == INVALID_HANDLE) g_slowHandle[k] = iMA(_Symbol, tf, InpSlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_fastHandle[k] == INVALID_HANDLE || g_slowHandle[k] == INVALID_HANDLE) return;

   int need = InpLookbackBars + 2;
   if(BarsCalculated(g_fastHandle[k]) < need || BarsCalculated(g_slowHandle[k]) < need) return;

   double ef[], es[];
   ArraySetAsSeries(ef, true); ArraySetAsSeries(es, true);
   //--- shift 1..InpLookbackBars+1 = CLOSED bars only (shift 0 would still
   //--- be forming) - oldest to newest once reversed below.
   if(CopyBuffer(g_fastHandle[k], 0, 1, need, ef) < need) return;
   if(CopyBuffer(g_slowHandle[k], 0, 1, need, es) < need) return;
   ArraySetAsSeries(ef, false); ArraySetAsSeries(es, false);   // now index 0 = oldest in the window

   if(freshTf)
     {
      //--- first time this TF is checked: just establish the current
      //--- state, don't log a "cross" for state that already existed
      //--- before this indicator was attached.
      g_lastDir[k] = (ef[need - 1] > es[need - 1]) ? "UP" : "DOWN";
      g_tfReady[k] = true;
      return;
     }

   for(int j = 1; j < need; j++)
     {
      bool nowAbove = ef[j] > es[j];
      bool wasAbove = ef[j - 1] > es[j - 1];
      datetime barTime = iTime(_Symbol, tf, need - j);   // closed-bar shift matching ef[j]/es[j]
      if(barTime <= g_lastCrossTime[k]) continue;         // already logged this bar's cross, if any

      if(nowAbove && !wasAbove)
        {
         double px = iClose(_Symbol, tf, need - j);
         LogCross(barTime, _Symbol, EnumToString(tf), "UP", px, ef[j], es[j]);
         g_lastDir[k] = "UP"; g_lastCrossTime[k] = barTime; g_lastCrossPrice[k] = px;
        }
      else if(!nowAbove && wasAbove)
        {
         double px = iClose(_Symbol, tf, need - j);
         LogCross(barTime, _Symbol, EnumToString(tf), "DOWN", px, ef[j], es[j]);
         g_lastDir[k] = "DOWN"; g_lastCrossTime[k] = barTime; g_lastCrossPrice[k] = px;
        }
     }
  }

bool g_panelCreated = false;

void PanelLabel(const string suffix, const int x, const int y, const string text, const color col)
  {
   static string lastName[24]; static string lastText[24]; static color lastColor[24]; static int used = 0;
   string nm = PFX + suffix;
   int slot = -1;
   for(int i = 0; i < used; i++) if(lastName[i] == nm) { slot = i; break; }
   if(slot < 0 && used < 24) { slot = used; lastName[slot] = nm; lastText[slot] = ""; lastColor[slot] = clrNONE; used++; }

   if(!g_panelCreated)
     {
      ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, y);
     }
   if(slot < 0 || lastText[slot] != text || lastColor[slot] != col)
     {
      ObjectSetString(0, nm, OBJPROP_TEXT, text);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
      if(slot >= 0) { lastText[slot] = text; lastColor[slot] = col; }
     }
  }

void UpdatePanel()
  {
   int lineH = 16;
   int x = InpPanelX, y = InpPanelY;
   int totalLines = 2 + 4 * 2;

   if(!g_panelCreated)
     {
      ObjectCreate(0, PFX + "bg", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BACK, false);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BGCOLOR, InpPanelBgColor);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_COLOR, InpPanelHeaderColor);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_XDISTANCE, x - 8);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_YDISTANCE, y - 6);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_XSIZE, InpPanelWidth);
      ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, lineH * totalLines + 12);
     }

   PanelLabel("title", x, y, StringFormat("EMA%d/%d Cross Tracker (sim only)", InpFastPeriod, InpSlowPeriod),
              InpPanelHeaderColor);
   y += lineH;
   PanelLabel("hdr", x, y, "TF    POS   SINCE               HELD", InpPanelHeaderColor);
   y += lineH;

   for(int k = 0; k < 4; k++)
     {
      string tfName = StringSubstr(EnumToString(g_tf[k]), 7);
      string posTxt = "n/a";
      color posCol = InpPanelTextColor;
      string sinceTxt = "-";
      string heldTxt = "-";

      if(g_tfReady[k] && g_lastDir[k] != "")
        {
         bool up = (g_lastDir[k] == "UP");
         posTxt = up ? "LONG" : "SHORT";
         posCol = up ? InpPanelUpColor : InpPanelDownColor;
         if(g_lastCrossTime[k] > 0)
           {
            sinceTxt = TimeToString(g_lastCrossTime[k], TIME_DATE | TIME_MINUTES);
            long heldSec = (long)(TimeCurrent() - g_lastCrossTime[k]);
            long heldH = heldSec / 3600;
            if(heldH < 48) heldTxt = StringFormat("%dh", (int)heldH);
            else           heldTxt = StringFormat("%.1fd", heldH / 24.0);
           }
         else
            sinceTxt = "(pre-existing)";
        }

      PanelLabel("tf" + IntegerToString(k) + "_name", x, y, tfName, InpPanelTextColor);
      PanelLabel("tf" + IntegerToString(k) + "_pos", x + 40, y, posTxt, posCol);
      y += lineH;
      PanelLabel("tf" + IntegerToString(k) + "_info", x + 10, y, sinceTxt + "   held " + heldTxt, InpPanelTextColor);
      y += lineH;
     }

   g_panelCreated = true;
  }

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   if(rates_total < 2) return(0);

   //--- bar-gated on the CHART's own bar for the panel refresh cadence
   //--- (cheap - just label text), but each tracked TF is independently
   //--- gated on ITS OWN bar time inside CheckTimeframe, so a slow TF
   //--- (D1) is never rechecked just because the chart's own TF is fast.
   datetime lastBar = time[rates_total - 1];
   bool newChartBar = (g_firstCalc || lastBar != g_lastBarTime);
   g_lastBarTime = lastBar;
   g_firstCalc = false;

   for(int k = 0; k < 4; k++) CheckTimeframe(k);

   if(InpShowPanel && newChartBar) UpdatePanel();
   if(newChartBar) ChartRedraw(0);

   return(rates_total);
  }
