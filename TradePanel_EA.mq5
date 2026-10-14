//+------------------------------------------------------------------+
//|                                               TradePanel_EA.mq5  |
//|  Movable on-chart manual trading widget. NOT a strategy - no    |
//|  automated entry/exit logic at all, just buttons that place or  |
//|  close trades on command.                                       |
//|                                                                   |
//|  Run this on its OWN chart window (MT5 allows only one EA per   |
//|  chart) - open a second chart of the same symbol/timeframe next |
//|  to whatever strategy EA is already running, and attach this   |
//|  one there. It manages positions by SYMBOL (see                 |
//|  InpManageOnlyOwnMagic below), so it can partial-close a trade  |
//|  opened by a different EA on the same chart/symbol.             |
//|                                                                   |
//|  SAFETY: placing a NEW batch of trades (the "PLACE xN" buttons) |
//|  requires ARM then a second click within InpArmSeconds - a      |
//|  single misclick cannot fire a batch of market orders. Closing  |
//|  (25/50/75%/CLOSE ALL) fires immediately - reducing risk never   |
//|  needs a confirm step.                                           |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_plots 0

#include <Trade/Trade.mqh>

input int    InpMagic              = 20261014;   // magic tag applied to trades THIS panel opens
input bool   InpManageOnlyOwnMagic = false;      // false: close-buttons act on ALL open positions for
                                                  // this symbol (e.g. your strategy EA's own trade too).
                                                  // true: close-buttons only touch trades this panel opened.
input int    InpArmSeconds         = 5;          // ARM auto-expires after this many seconds unused
input int    InpSlippage           = 30;
input color  InpBgColor            = C'30,30,34';
input color  InpTextColor          = clrWhite;
input color  InpArmedColor         = clrOrangeRed;
input color  InpBuyColor           = C'30,120,60';
input color  InpSellColor          = C'150,40,40';

CTrade trade;

string   PFX = "TPNL_";
int      g_panelX = 40, g_panelY = 40;
int      g_panelW = 250;
bool     g_armed = false;
datetime g_armedUntil = 0;

struct Ctrl { string name; int dx; int dy; };
Ctrl g_ctrls[];
int  g_nCtrls = 0;

//+------------------------------------------------------------------+
void AddCtrl(string name, int dx, int dy)
  {
   ArrayResize(g_ctrls, g_nCtrls + 1);
   g_ctrls[g_nCtrls].name = name;
   g_ctrls[g_nCtrls].dx = dx;
   g_ctrls[g_nCtrls].dy = dy;
   g_nCtrls++;
  }

//+------------------------------------------------------------------+
void MkLabel(string name, int dx, int dy, string text, color c, int fontsize = 9)
  {
   string full = PFX + name;
   ObjectCreate(0, full, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, full, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, full, OBJPROP_XDISTANCE, g_panelX + dx);
   ObjectSetInteger(0, full, OBJPROP_YDISTANCE, g_panelY + dy);
   ObjectSetString(0, full, OBJPROP_TEXT, text);
   ObjectSetInteger(0, full, OBJPROP_COLOR, c);
   ObjectSetInteger(0, full, OBJPROP_FONTSIZE, fontsize);
   ObjectSetString(0, full, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, full, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, full, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, full, OBJPROP_BACK, false);
   AddCtrl(full, dx, dy);
  }

//+------------------------------------------------------------------+
void MkEdit(string name, int dx, int dy, int w, int h, string text)
  {
   string full = PFX + name;
   ObjectCreate(0, full, OBJ_EDIT, 0, 0, 0);
   ObjectSetInteger(0, full, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, full, OBJPROP_XDISTANCE, g_panelX + dx);
   ObjectSetInteger(0, full, OBJPROP_YDISTANCE, g_panelY + dy);
   ObjectSetInteger(0, full, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, full, OBJPROP_YSIZE, h);
   ObjectSetString(0, full, OBJPROP_TEXT, text);
   ObjectSetInteger(0, full, OBJPROP_COLOR, clrBlack);
   ObjectSetInteger(0, full, OBJPROP_BGCOLOR, clrWhite);
   ObjectSetInteger(0, full, OBJPROP_ALIGN, ALIGN_CENTER);
   ObjectSetInteger(0, full, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, full, OBJPROP_SELECTABLE, true);
   ObjectSetInteger(0, full, OBJPROP_HIDDEN, true);
   AddCtrl(full, dx, dy);
  }

//+------------------------------------------------------------------+
void MkButton(string name, int dx, int dy, int w, int h, string text, color bg, color fg = clrWhite)
  {
   string full = PFX + name;
   ObjectCreate(0, full, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, full, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, full, OBJPROP_XDISTANCE, g_panelX + dx);
   ObjectSetInteger(0, full, OBJPROP_YDISTANCE, g_panelY + dy);
   ObjectSetInteger(0, full, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, full, OBJPROP_YSIZE, h);
   ObjectSetString(0, full, OBJPROP_TEXT, text);
   ObjectSetInteger(0, full, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, full, OBJPROP_COLOR, fg);
   ObjectSetInteger(0, full, OBJPROP_BORDER_COLOR, clrBlack);
   ObjectSetInteger(0, full, OBJPROP_FONTSIZE, 9);
   ObjectSetString(0, full, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, full, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, full, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, full, OBJPROP_STATE, false);
   AddCtrl(full, dx, dy);
  }

//+------------------------------------------------------------------+
double GetLot()
  {
   double lot = StringToDouble(ObjectGetString(0, PFX + "lotEdit", 0));
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lot < minLot) lot = minLot;
   lot = MathRound(lot / step) * step;
   return lot;
  }

//+------------------------------------------------------------------+
int GetCount()
  {
   int n = (int)StringToInteger(ObjectGetString(0, PFX + "cntEdit", 0));
   if(n < 1) n = 1;
   if(n > 50) n = 50;   // hard safety cap regardless of what's typed in - real money, no fat-finger "500"
   return n;
  }

//+------------------------------------------------------------------+
void UpdateExposureLabel()
  {
   double lot = GetLot();
   int n = GetCount();
   string txt = StringFormat("Exposure: %d x %s = %s lot", n, DoubleToString(lot, 2), DoubleToString(lot * n, 2));
   ObjectSetString(0, PFX + "expLbl", OBJPROP_TEXT, txt);
  }

//+------------------------------------------------------------------+
void SetArmed(bool on)
  {
   g_armed = on;
   g_armedUntil = on ? TimeCurrent() + InpArmSeconds : 0;
   string btn = PFX + "armBtn";
   if(on)
     {
      ObjectSetString(0, btn, OBJPROP_TEXT, "ARMED - click PLACE now");
      ObjectSetInteger(0, btn, OBJPROP_BGCOLOR, InpArmedColor);
     }
   else
     {
      ObjectSetString(0, btn, OBJPROP_TEXT, "ARM (required before PLACE)");
      ObjectSetInteger(0, btn, OBJPROP_BGCOLOR, InpBgColor);
     }
   ObjectSetInteger(0, btn, OBJPROP_STATE, false);
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
void PlaceBatch(bool isBuy)
  {
   if(!g_armed)
     {
      Alert("TradePanel: click ARM first, then PLACE, within ", InpArmSeconds, "s.");
      return;
     }
   double lot = GetLot();
   int n = GetCount();
   trade.SetExpertMagicNumber(InpMagic);
   int placed = 0, failed = 0;
   for(int k = 0; k < n; k++)
     {
      bool ok = isBuy ? trade.Buy(lot, _Symbol, 0.0, 0.0, 0.0, "TradePanel")
                      : trade.Sell(lot, _Symbol, 0.0, 0.0, 0.0, "TradePanel");
      if(ok) placed++; else failed++;
     }
   PrintFormat("TradePanel: requested %d x %s %s lot - placed %d, failed %d.",
               n, isBuy ? "BUY" : "SELL", DoubleToString(lot, 2), placed, failed);
   SetArmed(false);
  }

//+------------------------------------------------------------------+
bool PositionMatches(ulong ticket)
  {
   if(!PositionSelectByTicket(ticket)) return false;
   if(PositionGetString(POSITION_SYMBOL) != _Symbol) return false;
   if(InpManageOnlyOwnMagic && PositionGetInteger(POSITION_MAGIC) != InpMagic) return false;
   return true;
  }

//+------------------------------------------------------------------+
void ClosePct(double pct)
  {
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   int total = PositionsTotal();
   int closed = 0, failed = 0;
   for(int i = total - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      double vol = PositionGetDouble(POSITION_VOLUME);
      double closeVol = MathRound((vol * pct) / step) * step;
      if(closeVol < minLot) closeVol = minLot;
      if(closeVol >= vol - 1e-8)
        {
         if(trade.PositionClose(ticket, (ulong)InpSlippage)) closed++; else failed++;
        }
      else
        {
         if(trade.PositionClosePartial(ticket, closeVol, (ulong)InpSlippage)) closed++; else failed++;
        }
     }
   PrintFormat("TradePanel: close %.0f%% - %d position(s) actioned, %d failed.", pct * 100, closed, failed);
  }

//+------------------------------------------------------------------+
void CloseAll()
  {
   int total = PositionsTotal();
   int closed = 0, failed = 0;
   for(int i = total - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      if(trade.PositionClose(ticket, (ulong)InpSlippage)) closed++; else failed++;
     }
   PrintFormat("TradePanel: CLOSE ALL - %d closed, %d failed.", closed, failed);
  }

//+------------------------------------------------------------------+
void UpdateStats()
  {
   int n = 0; double vol = 0, pl = 0;
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      n++;
      vol += PositionGetDouble(POSITION_VOLUME);
      pl  += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   color plc = pl >= 0 ? clrLimeGreen : clrOrangeRed;
   string txt = StringFormat("Open: %d pos | %s lot | P/L %s", n, DoubleToString(vol, 2), DoubleToString(pl, 2));
   ObjectSetString(0, PFX + "statLbl", OBJPROP_TEXT, txt);
   ObjectSetInteger(0, PFX + "statLbl", OBJPROP_COLOR, plc);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   int w = g_panelW;
   ObjectCreate(0, PFX + "bg", OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XDISTANCE, g_panelX);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YDISTANCE, g_panelY);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XSIZE, w);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, 292);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_BGCOLOR, InpBgColor);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_BACK, false);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTABLE, true);   // drag handle
   ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTED, false);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_HIDDEN, false);

   MkLabel("title", 10, 8, "TRADE PANEL - drag this bar to move", clrSilver, 9);

   MkLabel("lotLbl", 10, 32, "Lot size:", InpTextColor);
   MkEdit("lotEdit", 110, 28, 90, 20, "0.01");

   MkLabel("cntLbl", 10, 58, "Trade count:", InpTextColor);
   MkEdit("cntEdit", 110, 54, 90, 20, "10");

   MkLabel("expLbl", 10, 82, "Exposure: -", clrKhaki);

   MkButton("armBtn", 10, 106, w - 20, 24, "ARM (required before PLACE)", InpBgColor, clrSilver);

   MkButton("buyBtn", 10, 136, (w - 30) / 2, 30, "PLACE BUY xN", InpBuyColor);
   MkButton("sellBtn", 10 + (w - 30) / 2 + 10, 136, (w - 30) / 2, 30, "PLACE SELL xN", InpSellColor);

   MkLabel("closeLbl", 10, 176, "Partial close current position(s):", InpTextColor);
   int cw = (w - 40) / 3;
   MkButton("c25", 10, 198, cw, 24, "25%", C'70,70,78');
   MkButton("c50", 10 + (cw + 10), 198, cw, 24, "50%", C'70,70,78');
   MkButton("c75", 10 + 2 * (cw + 10), 198, cw, 24, "75%", C'70,70,78');

   MkButton("cAll", 10, 228, w - 20, 26, "CLOSE ALL OPEN TRADES", C'150,40,40');

   MkLabel("statLbl", 10, 262, "Open: 0 pos | 0.00 lot | P/L 0.00", clrSilver);

   UpdateExposureLabel();
   UpdateStats();
   EventSetTimer(1);
   ChartRedraw(0);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   UpdateStats();
   if(g_armed && TimeCurrent() >= g_armedUntil)
      SetArmed(false);
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
void DragPanel(int newX, int newY)
  {
   int dx = newX - g_panelX;
   int dy = newY - g_panelY;
   g_panelX = newX;
   g_panelY = newY;
   for(int i = 0; i < g_nCtrls; i++)
     {
      long curX = ObjectGetInteger(0, g_ctrls[i].name, OBJPROP_XDISTANCE);
      long curY = ObjectGetInteger(0, g_ctrls[i].name, OBJPROP_YDISTANCE);
      ObjectSetInteger(0, g_ctrls[i].name, OBJPROP_XDISTANCE, curX + dx);
      ObjectSetInteger(0, g_ctrls[i].name, OBJPROP_YDISTANCE, curY + dy);
     }
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_OBJECT_DRAG && sparam == PFX + "bg")
     {
      int newX = (int)ObjectGetInteger(0, PFX + "bg", OBJPROP_XDISTANCE);
      int newY = (int)ObjectGetInteger(0, PFX + "bg", OBJPROP_YDISTANCE);
      DragPanel(newX, newY);
      return;
     }
   if(id != CHARTEVENT_OBJECT_CLICK) return;

   if(sparam == PFX + "lotEdit" || sparam == PFX + "cntEdit")
     {
      UpdateExposureLabel();
      return;
     }
   if(sparam == PFX + "armBtn")
     {
      SetArmed(!g_armed);
      return;
     }
   if(sparam == PFX + "buyBtn")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      PlaceBatch(true);
      UpdateStats();
      return;
     }
   if(sparam == PFX + "sellBtn")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      PlaceBatch(false);
      UpdateStats();
      return;
     }
   if(sparam == PFX + "c25") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); ClosePct(0.25); UpdateStats(); return; }
   if(sparam == PFX + "c50") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); ClosePct(0.50); UpdateStats(); return; }
   if(sparam == PFX + "c75") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); ClosePct(0.75); UpdateStats(); return; }
   if(sparam == PFX + "cAll") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); CloseAll(); UpdateStats(); return; }
  }
//+------------------------------------------------------------------+
