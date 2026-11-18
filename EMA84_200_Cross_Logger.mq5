//+------------------------------------------------------------------+
//|                                  EMA84_200_Cross_Logger.mq5      |
//|  Forward-tracking logger, NOT a trading EA - places no orders,   |
//|  risks no money. Logs every real EMA(84)/EMA(200) crossover, on  |
//|  the CLOSED bar, to a shared CSV the moment it happens - so it   |
//|  can be scored later against genuinely unseen future data,       |
//|  settling the "does this actually work" question the only way a |
//|  backtest never can.                                             |
//|                                                                    |
//|  Attach this to EVERY chart/timeframe you want tracked (e.g.      |
//|  GOLD M15, GOLD H1, GOLD H4, GOLD D1, and the same for Silver/    |
//|  BTC if wanted) - each instance logs its own symbol+period rows   |
//|  into ONE shared file in the terminal's Common\Files folder, so   |
//|  everything lands in one place regardless of which chart logged  |
//|  it.                                                               |
//+------------------------------------------------------------------+
#property copyright "Internal"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0
#property indicator_buffers 1

#define LOG_FILE "EMA84_200_CrossLog.csv"

input int InpFastPeriod = 84;
input int InpSlowPeriod = 200;

double g_dummy[];
bool   g_firstCalc = true;

int OnInit()
  {
   SetIndexBuffer(0, g_dummy, INDICATOR_CALCULATIONS);
   IndicatorSetString(INDICATOR_SHORTNAME,
                       StringFormat("EMA%d/%d Cross Logger", InpFastPeriod, InpSlowPeriod));
   g_firstCalc = true;

   //--- create the file with a header row if it doesn't exist yet (shared,
   //--- FILE_COMMON = terminal's Common\Files, same file across all
   //--- terminals/charts on this machine)
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

void OnDeinit(const int reason) {}

//--- appends one row; opens/writes/closes quickly each call since crosses
//--- are rare (not a per-tick cost) - safe for several chart instances to
//--- share the same file this way.
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

int g_fastHandle = INVALID_HANDLE;
int g_slowHandle = INVALID_HANDLE;
datetime g_lastBarTime = 0;

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[],
                 const double &close[], const long &tick_volume[], const long &volume[],
                 const int &spread[])
  {
   if(rates_total < InpSlowPeriod + 2) return(0);

   //--- bar-gated: only recompute/check on a genuinely new closed bar, not
   //--- per tick - same freeze-safety discipline as every other indicator
   //--- in this repo.
   datetime lastBar = time[rates_total - 1];
   if(!g_firstCalc && lastBar == g_lastBarTime) return(rates_total);
   g_lastBarTime = lastBar;
   bool freshAttach = g_firstCalc;
   g_firstCalc = false;

   if(g_fastHandle == INVALID_HANDLE) g_fastHandle = iMA(_Symbol, PERIOD_CURRENT, InpFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_slowHandle == INVALID_HANDLE) g_slowHandle = iMA(_Symbol, PERIOD_CURRENT, InpSlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(g_fastHandle == INVALID_HANDLE || g_slowHandle == INVALID_HANDLE) return(0);
   if(BarsCalculated(g_fastHandle) < 2 || BarsCalculated(g_slowHandle) < 2) return(freshAttach ? 0 : prev_calculated);

   double ef[], es[];
   ArraySetAsSeries(ef, true); ArraySetAsSeries(es, true);
   if(CopyBuffer(g_fastHandle, 0, 0, 2, ef) < 2) return(freshAttach ? 0 : prev_calculated);
   if(CopyBuffer(g_slowHandle, 0, 0, 2, es) < 2) return(freshAttach ? 0 : prev_calculated);

   //--- ef[0]/es[0] = last CLOSED bar (shift 0 on an already-closed-bar
   //--- gated call), ef[1]/es[1] = the bar before it - a genuine cross on
   //--- the bar that just closed, not the still-forming one.
   if(!freshAttach)
     {
      bool nowAbove = ef[0] > es[0];
      bool wasAbove = ef[1] > es[1];
      if(nowAbove && !wasAbove)
         LogCross(lastBar, _Symbol, EnumToString(PERIOD_CURRENT), "UP", close[rates_total - 1], ef[0], es[0]);
      else if(!nowAbove && wasAbove)
         LogCross(lastBar, _Symbol, EnumToString(PERIOD_CURRENT), "DOWN", close[rates_total - 1], ef[0], es[0]);
     }

   return(rates_total);
  }
