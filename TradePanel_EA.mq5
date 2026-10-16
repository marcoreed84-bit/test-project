//+------------------------------------------------------------------+
//|                                               TradePanel_EA.mq5  |
//|  Movable on-chart manual trading widget. NOT a strategy - no    |
//|  automated entry/exit logic at all, just buttons that place or  |
//|  close trades on command.                                       |
//|                                                                   |
//|  Run this on its OWN chart window (MT5 allows only one EA per   |
//|  chart) - open a second chart of the same symbol/timeframe next |
//|  to whatever strategy EA is already running, and attach this   |
//|  one there. It manages ONLY positions it opened itself (matched |
//|  by InpMagic) - the stats row, CLOSE ALL, 25/50/75% partial     |
//|  close, and Set SL/Set TP all act exclusively on this panel's   |
//|  own trades, never on a strategy EA's live position.            |
//|                                                                   |
//|  SAFETY: placing a NEW batch of trades (the "PLACE xN" buttons) |
//|  requires ARM then a second click within InpArmSeconds - a      |
//|  single misclick cannot fire a batch of market orders. Closing  |
//|  (25/50/75%/CLOSE ALL) fires immediately - reducing risk never   |
//|  needs a confirm step.                                           |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property version   "1.13"
#property strict
#property indicator_chart_window
#property indicator_plots 0

#include <Trade/Trade.mqh>

input group "=== Trade buttons ==="
input int    InpMagic              = 20261014;   // magic tag applied to trades THIS panel opens -
                                                  // stats/close/SL-TP are always scoped to this magic only
input int    InpArmSeconds         = 5;          // ARM auto-expires after this many seconds unused -
                                                  // starting value only, adjustable live from the panel
                                                  // itself now (Arm delay row) via g_armSeconds
input int    InpSlippage           = 30;
input color  InpBgColor            = C'30,30,34';
input color  InpTextColor          = clrWhite;
input color  InpArmedColor         = clrOrangeRed;
input color  InpBuyColor           = C'30,120,60';
input color  InpSellColor          = C'150,40,40';

input group "=== Moving averages (hand-drawn in the project's own colours, same idiom as the other EAs) ==="
input bool          InpShowMAs     = true;
input ENUM_MA_METHOD InpMAMethod   = MODE_EMA;    // MODE_EMA = exponential, MODE_SMA = simple
input int            InpMA21      = 21;
input int            InpMA50      = 50;
input int            InpMA200     = 200;
input color          InpCol21     = clrYellow;        // same colour family as the other EAs' MA21
input color          InpCol50     = C'255,140,0';     // neon orange - same family as the other EAs' MA50
input color          InpCol200    = C'191,0,255';     // neon purple
input int            InpMAHistoryBars = 150;          // rolling window of drawn MA history, PER LINE -
                                                       // 2500 (the old default) meant 2500 x 3 lines =
                                                       // 7500 chart objects, which is what was actually
                                                       // behind the general chart hang and the panel taking
                                                       // minutes to reclaim top paint order after a drag -
                                                       // every new bar has to scan/manage all of them.
                                                       // 300 is still ~3 days of M15 history visible; raise
                                                       // it only if you need more and accept the cost.

input group "=== 21/50 MA cross-proximity push alert (fires on PERIOD_CURRENT - attach this panel to the same chart/timeframe as whichever strategy EA you want warned about) ==="
input bool   InpEnableCrossAlert   = true;
input double InpCrossAlertATRMult  = 0.3;    // "near" threshold: alert once the 21/50 gap closes to
                                              // within this many ATR - smaller = later/tighter warning,
                                              // larger = earlier but noisier
input int    InpCrossATRPeriod     = 14;
input int    InpCrossAlertCooldownMin = 30;  // minimum minutes between alerts for the SAME approach,
                                              // so a gap oscillating right at the threshold doesn't spam

input group "=== Session VWAP (MT5 has no built-in VWAP - drawn manually, same construction as Aurelius_EA.mq5) ==="
input bool   InpShowVWAP           = true;
input color  InpColVWAP            = C'0,255,255';    // neon aqua - same family as the other EAs' VWAP
input int    InpVwapHistoryBars    = 400;

input group "=== Chart theme (same family-standard blue/white candles as the other EAs) ==="
input bool   InpApplyTheme         = true;
input color  InpChartBg            = clrBlack;
input color  InpBullCol            = C'0,150,255';    // neon blue - family standard
input color  InpBearCol            = clrWhite;        // neon white - family standard
input bool   InpHideTradeMarks     = true;    // hide MT5's own open-position lines and historical trade
                                               // arrows - same InpHideTradeMarks idiom as the other EAs,
                                               // applied unconditionally (not gated behind InpApplyTheme)
                                               // since those arrows drawing through the panel is exactly
                                               // what this fixes

input group "=== Trade condition light (green/red, same traffic-light idiom as the other EAs' panels) ==="
input int    InpMaxSpreadPoints    = 70;      // Silver-specific number from this project's own research
                                               // (research/trendbreaker/hs_silver_spread_threshold_test.py) -
                                               // change this per instrument; light goes RED when live spread exceeds this - this is
                                               // the ONLY thing the light checks (spread only, not a
                                               // trade signal of any kind - this panel has no strategy)

CTrade trade;

int g_maHandle21 = INVALID_HANDLE, g_maHandle50 = INVALID_HANDLE, g_maHandle200 = INVALID_HANDLE;
int g_atrHandleCross = INVALID_HANDLE;
bool     g_crossAlerted = false;     // true while the current approach has already fired its one
                                      // alert - cleared once the gap widens back out or the cross
                                      // actually happens, so the NEXT approach can alert again
datetime g_lastCrossAlertAt = 0;     // cooldown - see InpCrossAlertCooldownMin
//--- NOT "TPNL_..." - PFX ("TPNL_") is used with ObjectsDeleteAll(0, PFX) in
//--- RebuildPanel(), which matches by PREFIX. A "TPNL_MA_..." name would
//--- have been swept by that call too, wiping every MA/VWAP line (including
//--- the whole backfilled history) on every single new bar - exactly the
//--- real bug that made them vanish entirely rather than just sit behind
//--- the panel. Keep this prefix namespace-disjoint from PFX.
string g_pm = "TPMA_";
datetime g_lastBarTime = 0;

string   PFX = "TPNL_";
int      g_panelX = 40, g_panelY = 40;
int      g_panelW = 250;
int      g_panelH = 0;
bool     g_armed = false;
datetime g_armedUntil = 0;
int      g_armSeconds = InpArmSeconds;   // live-adjustable from the panel's Arm delay row

#define PANEL_ZORDER 1000   // keeps every panel widget drawn above freshly-created MA/VWAP
                             // segments AND above MT5's own native trade arrows/levels, which
                             // the InpHideTradeMarks toggle handles separately (z-order alone
                             // cannot reach those - they are not chart objects)
#define TITLE_BAR_H  24      // drag is restricted to this strip at the top of the panel

bool g_dragging = false;
int  g_dragOffX = 0, g_dragOffY = 0;
ulong g_dragStartMs = 0;   // safety timeout - see OnTimer
ulong g_lastDragUpdateMs = 0;   // throttle - see the mouse-move handler

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
   ObjectSetInteger(0, full, OBJPROP_ZORDER, PANEL_ZORDER);
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
   ObjectSetInteger(0, full, OBJPROP_FONTSIZE, 10);
   ObjectSetInteger(0, full, OBJPROP_SELECTABLE, true);
   ObjectSetInteger(0, full, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, full, OBJPROP_ZORDER, PANEL_ZORDER);
   AddCtrl(full, dx, dy);
  }

//+------------------------------------------------------------------+
void MkButton(string name, int dx, int dy, int w, int h, string text, color bg, color fg = clrWhite, int fontsize = 9)
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
   ObjectSetInteger(0, full, OBJPROP_FONTSIZE, fontsize);
   ObjectSetString(0, full, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, full, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, full, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, full, OBJPROP_STATE, false);
   ObjectSetInteger(0, full, OBJPROP_ZORDER, PANEL_ZORDER);
   AddCtrl(full, dx, dy);
  }

//+------------------------------------------------------------------+
double GetLot()
  {
   double lot = StringToDouble(ObjectGetString(0, PFX + "lotEdit", OBJPROP_TEXT));
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lot < minLot) lot = minLot;
   lot = MathRound(lot / step) * step;
   return lot;
  }

//+------------------------------------------------------------------+
int GetCount()
  {
   int n = (int)StringToInteger(ObjectGetString(0, PFX + "cntEdit", OBJPROP_TEXT));
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
void AdjustLot(double delta)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot = GetLot() + delta;
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;
   lot = MathRound(lot / step) * step;
   int digits = step >= 0.01 ? 2 : (step >= 0.001 ? 3 : 2);
   ObjectSetString(0, PFX + "lotEdit", OBJPROP_TEXT, DoubleToString(lot, digits));
   UpdateExposureLabel();
  }

//+------------------------------------------------------------------+
void AdjustCount(int delta)
  {
   int n = GetCount() + delta;
   if(n < 1) n = 1;
   if(n > 50) n = 50;
   ObjectSetString(0, PFX + "cntEdit", OBJPROP_TEXT, IntegerToString(n));
   UpdateExposureLabel();
  }

//+------------------------------------------------------------------+
void AdjustArmSeconds(int delta)
  {
   g_armSeconds += delta;
   if(g_armSeconds < 1) g_armSeconds = 1;
   if(g_armSeconds > 60) g_armSeconds = 60;
   ObjectSetString(0, PFX + "delayEdit", OBJPROP_TEXT, IntegerToString(g_armSeconds));
  }

//+------------------------------------------------------------------+
void SyncArmSecondsFromEdit()
  {
   int n = (int)StringToInteger(ObjectGetString(0, PFX + "delayEdit", OBJPROP_TEXT));
   if(n < 1) n = 1;
   if(n > 60) n = 60;
   g_armSeconds = n;
   ObjectSetString(0, PFX + "delayEdit", OBJPROP_TEXT, IntegerToString(g_armSeconds));
  }

//+------------------------------------------------------------------+
void SetArmed(bool on)
  {
   g_armed = on;
   g_armedUntil = on ? TimeCurrent() + g_armSeconds : 0;
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
      Alert("TradePanel: click ARM first, then PLACE, within ", g_armSeconds, "s.");
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
   if(PositionGetInteger(POSITION_MAGIC) != InpMagic) return false;
   return true;
  }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Closes pct of this panel's TOTAL matched volume, not pct of each   |
//| position individually. The per-position approach broke completely |
//| with several small same-size lots (e.g. 3x 0.01): 25% of a single  |
//| 0.01 lot position rounds to 0 at a 0.01 step, which the old code   |
//| then clamped UP to the broker minimum - silently closing that      |
//| position 100% instead of 25%. Below a step's worth of volume can't |
//| be sliced at all, so this closes whole positions, oldest first,    |
//| until the target volume is reached, partial-closing at most the    |
//| LAST one touched if there's enough left to form a valid partial.   |
//| Exact pct isn't always achievable when volumes don't divide evenly |
//| - this gets as close as the broker's own lot step allows, instead  |
//| of the old silent all-or-nothing failure.                          |
//+------------------------------------------------------------------+
void ClosePct(double pct)
  {
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   int total = PositionsTotal();

   ulong  tickets[];
   double vols[];
   datetime opens[];
   int n = 0;
   ArrayResize(tickets, total);
   ArrayResize(vols, total);
   ArrayResize(opens, total);
   double totalVol = 0.0;
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      tickets[n] = ticket;
      vols[n]    = PositionGetDouble(POSITION_VOLUME);
      opens[n]   = (datetime)PositionGetInteger(POSITION_TIME);
      totalVol  += vols[n];
      n++;
     }
   if(n == 0) return;

   // oldest-first (ascending open time) - simple insertion sort, n is tiny
   for(int a = 1; a < n; a++)
     {
      ulong  tt = tickets[a]; double tv = vols[a]; datetime to = opens[a];
      int b = a - 1;
      while(b >= 0 && opens[b] > to)
        {
         tickets[b + 1] = tickets[b]; vols[b + 1] = vols[b]; opens[b + 1] = opens[b];
         b--;
        }
      tickets[b + 1] = tt; vols[b + 1] = tv; opens[b + 1] = to;
     }

   double target = MathRound((totalVol * pct) / step) * step;
   if(target < minLot) target = (pct > 0.0 && totalVol > 0.0) ? minLot : 0.0;
   if(target > totalVol) target = totalVol;

   double remaining = target;
   int closed = 0, failed = 0;
   for(int i = 0; i < n && remaining >= minLot - 1e-8; i++)
     {
      if(remaining >= vols[i] - 1e-8)
        {
         if(trade.PositionClose(tickets[i], (ulong)InpSlippage)) closed++; else failed++;
         remaining -= vols[i];
        }
      else
        {
         double partial = MathRound(remaining / step) * step;
         if(partial < minLot) break;   // what's left can't be sliced at this step
         if(trade.PositionClosePartial(tickets[i], partial, (ulong)InpSlippage)) closed++; else failed++;
         remaining -= partial;
        }
     }
   PrintFormat("TradePanel: close %.0f%% - target %.2f of %.2f total lots, %d position(s) actioned, %d failed.",
               pct * 100, target, totalVol, closed, failed);
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
//| Applies a new SL (or TP) to every matched open position, keeping  |
//| that position's OWN current TP (or SL) unchanged - trade.PositionModify()
//| always sets both levels together, so the one not being edited here
//| has to be re-read from the position and re-sent, or it would get
//| wiped to 0 (no stop/target at all) rather than left alone.
//+------------------------------------------------------------------+
void SetSLForAll(double newSL)
  {
   int total = PositionsTotal();
   int done = 0, failed = 0;
   for(int i = total - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      double tp = PositionGetDouble(POSITION_TP);
      if(trade.PositionModify(ticket, newSL, tp)) done++; else failed++;
     }
   PrintFormat("TradePanel: Set SL=%s - %d position(s) updated, %d failed.",
               DoubleToString(newSL, _Digits), done, failed);
   if(failed > 0)
      Alert("TradePanel: Set SL failed on ", failed, " position(s) - check Experts log (common cause: price too close to market, broker's stop level).");
  }

//+------------------------------------------------------------------+
void SetTPForAll(double newTP)
  {
   int total = PositionsTotal();
   int done = 0, failed = 0;
   for(int i = total - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      double sl = PositionGetDouble(POSITION_SL);
      if(trade.PositionModify(ticket, sl, newTP)) done++; else failed++;
     }
   PrintFormat("TradePanel: Set TP=%s - %d position(s) updated, %d failed.",
               DoubleToString(newTP, _Digits), done, failed);
   if(failed > 0)
      Alert("TradePanel: Set TP failed on ", failed, " position(s) - check Experts log (common cause: price too close to market, broker's stop level).");
  }

//+------------------------------------------------------------------+
//| Fills the SL/TP edit fields from the first matched open position -|
//| convenience so you can nudge an existing level instead of typing   |
//| one from scratch. Multiple matched positions only fills from the   |
//| first found; Set SL/Set TP still apply to ALL of them.             |
//+------------------------------------------------------------------+
void FillCurrentSLTP()
  {
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionMatches(ticket)) continue;
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      ObjectSetString(0, PFX + "slEdit", OBJPROP_TEXT, DoubleToString(sl, _Digits));
      ObjectSetString(0, PFX + "tpEdit", OBJPROP_TEXT, DoubleToString(tp, _Digits));
      return;
     }
   Alert("TradePanel: no open position to read SL/TP from.");
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
void UpdateMarketLabel()
  {
   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   long vol1 = iVolume(_Symbol, PERIOD_CURRENT, 1);   // last CLOSED bar's tick volume -
                                                       // bar 0 is still forming and understates it
   ObjectSetString(0, PFX + "spreadLbl", OBJPROP_TEXT, StringFormat("Spread: %d points", (int)spreadPts));
   ObjectSetString(0, PFX + "volLbl",    OBJPROP_TEXT, StringFormat("Volume (last bar): %d", (int)vol1));

   bool ok = spreadPts <= InpMaxSpreadPoints;
   ObjectSetInteger(0, PFX + "light", OBJPROP_COLOR, ok ? clrLimeGreen : clrRed);
   ObjectSetString(0, PFX + "lightLbl", OBJPROP_TEXT,
                    ok ? "OK TO TRADE (spread within limit)" : "SPREAD TOO WIDE - WAIT");
   ObjectSetInteger(0, PFX + "lightLbl", OBJPROP_COLOR, ok ? clrLimeGreen : clrRed);
  }

//+------------------------------------------------------------------+
//| Chart theme - identical convention to the other EAs in this     |
//| project (InpBullCol/InpBearCol/InpChartBg, same ChartSetInteger  |
//| set) so a chart running this panel looks consistent with one     |
//| running HeadShoulders/Aurelius/etc.                               |
//+------------------------------------------------------------------+
void ApplyTheme()
  {
   if(InpHideTradeMarks)
     {
      //--- CHART_SHOW_TRADE_LEVELS deliberately left ALONE (true, MT5's
      //--- own default) - that's the native open/SL/TP line set you drag
      //--- to set SL/TP, and hiding it here was in direct conflict with
      //--- that workflow. Only trade HISTORY (closed-trade arrows/labels,
      //--- a years-deep clutter concern on a shared symbol chart, not
      //--- something you'd ever drag) stays suppressed.
      ChartSetInteger(0, CHART_SHOW_TRADE_HISTORY, false);
     }
   if(!InpApplyTheme) return;
   ChartSetInteger(0, CHART_COLOR_BACKGROUND,  InpChartBg);
   ChartSetInteger(0, CHART_COLOR_FOREGROUND,  C'138,152,178');
   ChartSetInteger(0, CHART_COLOR_GRID,        C'20,26,40');
   ChartSetInteger(0, CHART_COLOR_CHART_UP,    InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CHART_DOWN,  InpBearCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, InpBullCol);
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, InpBearCol);
   ChartSetInteger(0, CHART_COLOR_CHART_LINE,  C'138,152,178');
   ChartSetInteger(0, CHART_SHOW_GRID,   false);
   ChartSetInteger(0, CHART_MODE,        CHART_CANDLES);
  }

//+------------------------------------------------------------------+
//| Session VWAP - MT5 has no built-in VWAP indicator, so this is the|
//| exact same construction already validated in Aurelius_EA.mq5's   |
//| SessionVWAP(): typical-price*volume accumulated from midnight,   |
//| one bulk CopyTime/CopyHigh/.../CopyTickVolume per call rather    |
//| than per-bar iTime/iHigh/... lookups (that was the real slow     |
//| part when this was first built, not "repainting").               |
//+------------------------------------------------------------------+
double SessionVWAP(const int shift)
  {
   datetime barTime = iTime(_Symbol, PERIOD_CURRENT, shift);
   if(barTime == 0) return(0.0);
   MqlDateTime dt; TimeToStruct(barTime, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);

   datetime tArr[]; double hArr[], lArr[], cArr[]; long vArr[];
   ArraySetAsSeries(tArr, true); ArraySetAsSeries(hArr, true);
   ArraySetAsSeries(lArr, true); ArraySetAsSeries(cArr, true);
   ArraySetAsSeries(vArr, true);
   int got = CopyTime(_Symbol, PERIOD_CURRENT, shift, 400, tArr);
   if(got <= 0) return(0.0);
   if(CopyHigh(_Symbol, PERIOD_CURRENT, shift, got, hArr) <= 0) return(0.0);
   if(CopyLow(_Symbol, PERIOD_CURRENT, shift, got, lArr) <= 0) return(0.0);
   if(CopyClose(_Symbol, PERIOD_CURRENT, shift, got, cArr) <= 0) return(0.0);
   if(CopyTickVolume(_Symbol, PERIOD_CURRENT, shift, got, vArr) <= 0) return(0.0);

   double cumPV = 0.0, cumV = 0.0;
   for(int s = 0; s < got; s++)
     {
      if(tArr[s] < dayStart) break;
      double typical = (hArr[s] + lArr[s] + cArr[s]) / 3.0;
      cumPV += typical * (double)vArr[s];
      cumV  += (double)vArr[s];
     }
   if(cumV <= 0.0) return(0.0);
   return(cumPV / cumV);
  }

//+------------------------------------------------------------------+
bool DifferentSession(const int shiftA, const int shiftB)
  {
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, shiftA);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, shiftB);
   if(tA == 0 || tB == 0) return(true);
   MqlDateTime dA, dB; TimeToStruct(tA, dA); TimeToStruct(tB, dB);
   return(dA.day != dB.day || dA.mon != dB.mon || dA.year != dB.year);
  }

//+------------------------------------------------------------------+
//| Generic per-bar trend-line segment, same idiom (and reasoning)   |
//| as Aurelius_EA.mq5's DrawMASegment - hand-drawn rather than a     |
//| native ChartIndicatorAdd plot because MT5 doesn't expose a        |
//| per-instance colour override for a chart-added indicator handle,  |
//| and these need the project's own "family standard" colours.      |
//+------------------------------------------------------------------+
void DrawSegment(const string tag, const datetime tOld, const double vOld,
                  const datetime tNew, const double vNew, const color col)
  {
   string nm = g_pm + tag + "_" + IntegerToString((long)tNew);
   if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
   ObjectCreate(0, nm, OBJ_TREND, 0, tOld, vOld, tNew, vNew);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
void PurgeOldSegments(const datetime latestBarTime, const int historyBars)
  {
   datetime cutoff = latestBarTime - (datetime)((long)historyBars * PeriodSeconds(PERIOD_CURRENT));
   for(int i = ObjectsTotal(0, 0, OBJ_TREND) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, OBJ_TREND);
      if(StringFind(nm, g_pm) != 0) continue;
      datetime ot = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      if(ot < cutoff) ObjectDelete(0, nm);
     }
  }

//+------------------------------------------------------------------+
bool MAValue(int handle, int shift, double &out)
  {
   if(handle == INVALID_HANDLE) return(false);
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle, 0, shift, 1, buf) < 1) return(false);
   out = buf[0];
   return(true);
  }

//+------------------------------------------------------------------+
//| Called once per new bar - draws exactly one new segment per line |
//| (MAs + VWAP), same as Aurelius's UpdateMALines.                  |
//+------------------------------------------------------------------+
void UpdateOverlayLines()
  {
   datetime tA = iTime(_Symbol, PERIOD_CURRENT, 2);
   datetime tB = iTime(_Symbol, PERIOD_CURRENT, 1);
   if(tA == 0 || tB == 0) return;
   int maxHist = InpMAHistoryBars;
   if(InpShowMAs)
     {
      double a21, b21, a50, b50, a200, b200;
      if(MAValue(g_maHandle21, 2, a21) && MAValue(g_maHandle21, 1, b21))
         DrawSegment("21", tA, a21, tB, b21, InpCol21);
      if(MAValue(g_maHandle50, 2, a50) && MAValue(g_maHandle50, 1, b50))
         DrawSegment("50", tA, a50, tB, b50, InpCol50);
      if(MAValue(g_maHandle200, 2, a200) && MAValue(g_maHandle200, 1, b200))
         DrawSegment("200", tA, a200, tB, b200, InpCol200);
     }
   if(InpShowVWAP && !DifferentSession(2, 1))
     {
      double vA = SessionVWAP(2), vB = SessionVWAP(1);
      if(vA > 0.0 && vB > 0.0) DrawSegment("vwap", tA, vA, tB, vB, InpColVWAP);
      if(InpMAHistoryBars < InpVwapHistoryBars) maxHist = InpVwapHistoryBars;
     }
   if(InpShowMAs || InpShowVWAP) PurgeOldSegments(tB, maxHist);
  }

//+------------------------------------------------------------------+
//| Called once from OnInit - walks backward and draws the whole      |
//| rolling window immediately, same reasoning as Aurelius's          |
//| BackfillMALines (otherwise a fresh attach shows a 1-bar stub and  |
//| takes the full history window to fill in).                        |
//+------------------------------------------------------------------+
void BackfillOverlayLines()
  {
   if(InpShowMAs)
     {
      int avail = Bars(_Symbol, PERIOD_CURRENT) - 2;
      int n = MathMin(InpMAHistoryBars, avail);
      double a, b;
      for(int s = n; s >= 1; s--)
        {
         datetime tA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
         datetime tB = iTime(_Symbol, PERIOD_CURRENT, s);
         if(tA == 0 || tB == 0) continue;
         if(MAValue(g_maHandle21,  s + 1, a) && MAValue(g_maHandle21,  s, b)) DrawSegment("21",  tA, a, tB, b, InpCol21);
         if(MAValue(g_maHandle50,  s + 1, a) && MAValue(g_maHandle50,  s, b)) DrawSegment("50",  tA, a, tB, b, InpCol50);
         if(MAValue(g_maHandle200, s + 1, a) && MAValue(g_maHandle200, s, b)) DrawSegment("200", tA, a, tB, b, InpCol200);
        }
     }
   if(InpShowVWAP)
     {
      int availV = Bars(_Symbol, PERIOD_CURRENT) - 2;
      int nV = MathMin(InpVwapHistoryBars, availV);
      for(int s = nV; s >= 1; s--)
        {
         if(DifferentSession(s + 1, s)) continue;
         datetime tA = iTime(_Symbol, PERIOD_CURRENT, s + 1);
         datetime tB = iTime(_Symbol, PERIOD_CURRENT, s);
         if(tA == 0 || tB == 0) continue;
         double vA = SessionVWAP(s + 1), vB = SessionVWAP(s);
         if(vA > 0.0 && vB > 0.0) DrawSegment("vwap", tA, vA, tB, vB, InpColVWAP);
        }
     }
  }

//+------------------------------------------------------------------+
void SetupMAs()
  {
   //--- handles are needed for the cross-proximity alert even when the lines
   //--- themselves aren't drawn (InpShowMAs only gates UpdateOverlayLines/
   //--- BackfillOverlayLines, not these handles)
   if(!InpShowMAs && !InpEnableCrossAlert) return;
   g_maHandle21  = iMA(_Symbol, PERIOD_CURRENT, InpMA21,  0, InpMAMethod, PRICE_CLOSE);
   g_maHandle50  = iMA(_Symbol, PERIOD_CURRENT, InpMA50,  0, InpMAMethod, PRICE_CLOSE);
   g_maHandle200 = iMA(_Symbol, PERIOD_CURRENT, InpMA200, 0, InpMAMethod, PRICE_CLOSE);
   if(InpEnableCrossAlert)
      g_atrHandleCross = iATR(_Symbol, PERIOD_CURRENT, InpCrossATRPeriod);
  }

//+------------------------------------------------------------------+
//| Push-notification warning that the 21/50 MA gap is closing and a  |
//| cross looks imminent, BEFORE it actually happens - not an alert   |
//| on the cross itself. Checked once per new closed bar (same        |
//| cadence as UpdateOverlayLines - no reason to re-check every tick, |
//| the MA values for a closed bar don't change until the next one).  |
//|                                                                     |
//| Uses shift 1/2 (the last two CLOSED bars) rather than the forming  |
//| bar 0 - same reasoning as this project's standard fix for H4-bar   |
//| lookups elsewhere: an unclosed bar's MA value still moves as price |
//| moves, which would fire (or un-fire) the alert on noise rather    |
//| than a settled reading.                                            |
//|                                                                     |
//| "Likely to cross soon" = the 21/50 gap, measured in ATR, has both  |
//| (a) narrowed versus the prior closed bar and (b) closed to within  |
//| InpCrossAlertATRMult*ATR - not yet crossed (sign unchanged). Fires |
//| once per approach (g_crossAlerted latches), resets once the gap    |
//| widens back out past 1.5x the threshold or the cross actually      |
//| happens, so the next approach can alert again.                     |
//+------------------------------------------------------------------+
void CheckCrossProximity()
  {
   if(!InpEnableCrossAlert) return;
   if(g_maHandle21 == INVALID_HANDLE || g_maHandle50 == INVALID_HANDLE || g_atrHandleCross == INVALID_HANDLE) return;

   double ma21_1, ma21_2, ma50_1, ma50_2, atr_1;
   if(!MAValue(g_maHandle21, 1, ma21_1) || !MAValue(g_maHandle21, 2, ma21_2)) return;
   if(!MAValue(g_maHandle50, 1, ma50_1) || !MAValue(g_maHandle50, 2, ma50_2)) return;
   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(g_atrHandleCross, 0, 1, 1, atrBuf) != 1 || atrBuf[0] <= 0.0) return;
   atr_1 = atrBuf[0];

   double gapNow  = ma21_1 - ma50_1;
   double gapPrev = ma21_2 - ma50_2;
   bool alreadyCrossed = (gapNow >= 0.0) != (gapPrev >= 0.0);
   double threshold = InpCrossAlertATRMult * atr_1;

   if(alreadyCrossed || MathAbs(gapNow) > threshold * 1.5)
     {
      g_crossAlerted = false;   // clear reset - diverged again, or the cross already happened
      return;
     }

   bool narrowing = MathAbs(gapNow) < MathAbs(gapPrev);
   bool near       = MathAbs(gapNow) <= threshold;
   if(!narrowing || !near) return;
   if(g_crossAlerted) return;   // already warned for this approach, waiting for a reset
   if(TimeCurrent() - g_lastCrossAlertAt < InpCrossAlertCooldownMin * 60) return;

   string dir = (gapNow > 0.0) ? "21 crossing DOWN through 50 (bearish)" : "21 crossing UP through 50 (bullish)";
   string tf  = StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7);   // "PERIOD_M15" -> "M15"
   string msg = StringFormat("%s %s: 21/50 MA gap closing, %s likely soon (gap %.1f%% of threshold)",
                              _Symbol, tf, dir, 100.0 * MathAbs(gapNow) / threshold);
   SendNotification(msg);
   Print("CrossAlert: ", msg);
   g_crossAlerted = true;
   g_lastCrossAlertAt = TimeCurrent();
  }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Builds every panel object fresh. MT5 paints chart objects in      |
//| CREATION ORDER, not by OBJPROP_ZORDER (that property only decides |
//| mouse-click priority, not paint order - a real mistake in v1.03). |
//| The MA/VWAP trend segments get a brand-new object created every   |
//| single new bar (UpdateOverlayLines), so they will always paint on |
//| top of a panel that was only ever built once in OnInit. The only  |
//| real fix is to rebuild the panel (so it becomes the newest set of |
//| objects again) after every new-bar redraw - see RebuildPanel()    |
//| and its call from OnTick. Same reasoning Aurelius_EA.mq5's own    |
//| comments already describe for its UpdateMALines/DrawPanel order.  |
//+------------------------------------------------------------------+
void BuildPanel()
  {
   //--- per direct request: shorter panel, smaller text - traded a bit of
   //--- width (340->370) for a lot less height (rows tightened from
   //--- 28-38px down to 20-26px, fonts from 10 down to 8-9) so nothing
   //--- wraps or crowds at the smaller size.
   g_panelW = 370;
   int w = g_panelW;
   ObjectCreate(0, PFX + "bg", OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XDISTANCE, g_panelX);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YDISTANCE, g_panelY);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XSIZE, w);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, g_panelH);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_BGCOLOR, InpBgColor);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_BACK, false);
   //--- NOT selectable - native rectangle-label dragging is unreliable once
   //--- buttons/edits sit on top of it (they eat the mouse-down before the
   //--- background ever sees it). Dragging is instead handled manually in
   //--- OnChartEvent via CHARTEVENT_MOUSE_MOVE, restricted to the title
   //--- strip (TITLE_BAR_H) - see DragPanel/the mouse-move handler below.
   ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_SELECTED, false);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_HIDDEN, false);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_ZORDER, PANEL_ZORDER);

   //--- title strip, visually separated so the drag area is obvious
   ObjectCreate(0, PFX + "titlebar", OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_XDISTANCE, g_panelX);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_YDISTANCE, g_panelY);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_XSIZE, w);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_YSIZE, TITLE_BAR_H);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_BGCOLOR, C'55,55,62');
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_BACK, false);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_HIDDEN, false);
   ObjectSetInteger(0, PFX + "titlebar", OBJPROP_ZORDER, PANEL_ZORDER);
   AddCtrl(PFX + "titlebar", 0, 0);

   MkLabel("title", 10, 4, "TRADE PANEL  (drag here to move)", clrWhite, 9);

   int y = TITLE_BAR_H + 10;
   MkLabel("lotLbl", 12, y + 3, "Lot size:", InpTextColor, 9);
   MkEdit("lotEdit", 130, y, 80, 20, "0.01");
   MkButton("lotMinus", 216, y, 22, 20, "-", C'70,70,78', clrWhite, 10);
   MkButton("lotPlus",  242, y, 22, 20, "+", C'70,70,78', clrWhite, 10);

   y += 26;
   MkLabel("cntLbl", 12, y + 3, "Trade count:", InpTextColor, 9);
   MkEdit("cntEdit", 130, y, 80, 20, "10");
   MkButton("cntMinus", 216, y, 22, 20, "-", C'70,70,78', clrWhite, 10);
   MkButton("cntPlus",  242, y, 22, 20, "+", C'70,70,78', clrWhite, 10);

   y += 24;
   MkLabel("expLbl", 12, y, "Exposure: -", clrKhaki, 9);

   y += 22;
   MkLabel("delayLbl", 12, y + 3, "Arm delay (s):", InpTextColor, 9);
   MkEdit("delayEdit", 150, y, 50, 20, IntegerToString(g_armSeconds));
   MkButton("delayMinus", 216, y, 22, 20, "-", C'70,70,78', clrWhite, 10);
   MkButton("delayPlus",  242, y, 22, 20, "+", C'70,70,78', clrWhite, 10);

   y += 26;
   MkButton("armBtn", 12, y, w - 24, 22, "ARM (required before PLACE)", InpBgColor, clrSilver, 9);

   y += 28;
   MkButton("buyBtn", 12, y, (w - 36) / 2, 26, "PLACE BUY xN", InpBuyColor, clrWhite, 9);
   MkButton("sellBtn", 12 + (w - 36) / 2 + 12, y, (w - 36) / 2, 26, "PLACE SELL xN", InpSellColor, clrWhite, 9);

   y += 34;
   MkLabel("closeLbl", 12, y, "Partial close current position(s):", InpTextColor, 9);
   y += 18;
   int cw = (w - 48) / 3;
   MkButton("c25", 12, y, cw, 22, "25%", C'70,70,78', clrWhite, 9);
   MkButton("c50", 12 + (cw + 12), y, cw, 22, "50%", C'70,70,78', clrWhite, 9);
   MkButton("c75", 12 + 2 * (cw + 12), y, cw, 22, "75%", C'70,70,78', clrWhite, 9);

   y += 30;
   MkButton("cAll", 12, y, w - 24, 24, "CLOSE ALL OPEN TRADES", C'150,40,40', clrWhite, 9);

   y += 32;
   MkLabel("sltpLbl", 12, y, "Manual SL / TP for current position(s):", InpTextColor, 9);
   y += 18;
   MkLabel("slLbl", 12, y + 3, "SL:", InpTextColor, 9);
   MkEdit("slEdit", 45, y, 100, 20, "0.00");
   MkButton("setSL", 155, y, 65, 20, "Set SL", C'70,70,78', clrWhite, 9);
   y += 24;
   MkLabel("tpLbl", 12, y + 3, "TP:", InpTextColor, 9);
   MkEdit("tpEdit", 45, y, 100, 20, "0.00");
   MkButton("setTP", 155, y, 65, 20, "Set TP", C'70,70,78', clrWhite, 9);
   y += 24;
   MkButton("fillCur", 12, y, w - 24, 18, "Fill fields with current SL/TP", C'55,55,62', clrSilver, 8);

   y += 28;
   MkLabel("statLbl", 12, y, "Open: 0 pos | 0.00 lot | P/L 0.00", clrSilver, 9);

   y += 20;
   MkLabel("spreadLbl", 12, y, "Spread: -", clrKhaki, 9);
   y += 16;
   MkLabel("volLbl", 12, y, "Volume (last bar): -", clrKhaki, 9);

   y += 22;
   MkLabel("light", 12, y, "l", clrLimeGreen, 12);
   ObjectSetString(0, PFX + "light", OBJPROP_FONT, "Wingdings");
   MkLabel("lightLbl", 30, y + 1, "OK TO TRADE (spread within limit)", clrLimeGreen, 9);

   g_panelH = y + 36;   // extra bottom margin so the last row never sits flush with the edge
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, g_panelH);

   UpdateExposureLabel();
   UpdateStats();
   UpdateMarketLabel();
  }

//+------------------------------------------------------------------+
//| Rebuilds the panel so it becomes the newest (therefore topmost-   |
//| painted) set of objects again - called once per new bar, right    |
//| after UpdateOverlayLines() draws that bar's MA/VWAP segments.      |
//| Preserves the lot/count/delay fields and the panel's current      |
//| dragged-to position; does NOT preserve an in-progress ARM (it      |
//| auto-expires in a few seconds anyway, and resetting it on rebuild  |
//| is a safety positive, not a problem).                              |
//+------------------------------------------------------------------+
void RebuildPanel()
  {
   string lotText = ObjectGetString(0, PFX + "lotEdit", OBJPROP_TEXT);
   string cntText = ObjectGetString(0, PFX + "cntEdit", OBJPROP_TEXT);
   string slText  = ObjectGetString(0, PFX + "slEdit", OBJPROP_TEXT);
   string tpText  = ObjectGetString(0, PFX + "tpEdit", OBJPROP_TEXT);
   ObjectsDeleteAll(0, PFX);
   g_nCtrls = 0;
   BuildPanel();
   ObjectSetString(0, PFX + "lotEdit", OBJPROP_TEXT, lotText);
   ObjectSetString(0, PFX + "cntEdit", OBJPROP_TEXT, cntText);
   ObjectSetString(0, PFX + "slEdit", OBJPROP_TEXT, slText);
   ObjectSetString(0, PFX + "tpEdit", OBJPROP_TEXT, tpText);
   UpdateExposureLabel();
   UpdateMarketLabel();
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);   // required for the manual title-bar drag handler

   ApplyTheme();
   SetupMAs();
   //--- backfill BEFORE building the panel - otherwise the whole historical
   //--- MA/VWAP backfill gets created AFTER the panel and buries it from the
   //--- moment of attach, not just until the first new bar's RebuildPanel()
   //--- call (same creation-order reasoning as RebuildPanel's own header).
   BackfillOverlayLines();
   BuildPanel();

   g_lastBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   EventSetTimer(2);   // was 1s - halving the poll frequency on top of no
                        // longer force-redrawing every tick (see OnTimer)
   ChartRedraw(0);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
   ObjectsDeleteAll(0, g_pm);
   if(g_maHandle21  != INVALID_HANDLE) IndicatorRelease(g_maHandle21);
   if(g_maHandle50  != INVALID_HANDLE) IndicatorRelease(g_maHandle50);
   if(g_maHandle200 != INVALID_HANDLE) IndicatorRelease(g_maHandle200);
   if(g_atrHandleCross != INVALID_HANDLE) IndicatorRelease(g_atrHandleCross);
  }

//+------------------------------------------------------------------+
//| True while the user is actively typing in any of this panel's     |
//| edit boxes. MT5 sets OBJPROP_SELECTED on an OBJ_EDIT while it has  |
//| keyboard focus/is being edited - checked here instead of guessed  |
//| at, so the new-bar rebuild can defer itself exactly while (and     |
//| only while) it would actually interrupt typing.                   |
//+------------------------------------------------------------------+
bool AnyEditFocused()
  {
   string edits[] = {"lotEdit", "cntEdit", "delayEdit", "slEdit", "tpEdit"};
   for(int i = 0; i < ArraySize(edits); i++)
      if(ObjectGetInteger(0, PFX + edits[i], OBJPROP_SELECTED))
         return true;
   return false;
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   datetime t0 = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t0 != g_lastBarTime)
     {
      g_lastBarTime = t0;
      UpdateOverlayLines();
      CheckCrossProximity();
      //--- skip the rebuild while actively dragging - recreating the title
      //--- bar object out from under an in-progress drag is asking for
      //--- trouble. The next new bar after the drag ends reclaims paint
      //--- order instead; one bar's delay is harmless.
      //--- SAME reasoning for an in-progress edit: ObjectsDeleteAll inside
      //--- RebuildPanel() destroys the slEdit/tpEdit/etc. object the user
      //--- is mid-keystroke in, which silently drops keyboard focus (the
      //--- freshly recreated object of the same name does NOT inherit it)
      //--- - this was the real cause of "I can't type in the SL field",
      //--- not an edit-box property. MT5 marks an OBJ_EDIT OBJPROP_SELECTED
      //--- while it's being edited, which lets this be detected reliably
      //--- rather than guessed at.
      if(!g_dragging && !AnyEditFocused()) RebuildPanel();
     }
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   UpdateStats();
   UpdateMarketLabel();
   if(g_armed && TimeCurrent() >= g_armedUntil)
      SetArmed(false);
   //--- safety net: if the mouse button was released outside the chart
   //--- entirely, no further CHARTEVENT_MOUSE_MOVE fires here and the drag
   //--- (and the CHART_MOUSE_SCROLL=false lock) could otherwise get stuck.
   if(g_dragging && GetTickCount64() - g_dragStartMs > 5000)
     {
      g_dragging = false;
      ChartSetInteger(0, CHART_MOUSE_SCROLL, true);
     }
   //--- NOT calling ChartRedraw() here unconditionally anymore - this ran
   //--- every single second, forcing MT5 to repaint the whole chart
   //--- (including every background MA/VWAP object) regardless of whether
   //--- anything actually changed. ObjectSetString/ObjectSetInteger changes
   //--- still show up on the terminal's own natural paint cycle (driven by
   //--- ticks); an explicit redraw is only needed right after a batch
   //--- change the user is actively looking at - RebuildPanel(), SetArmed(),
   //--- and the button click handlers already call it where it matters.
  }

//+------------------------------------------------------------------+
void DragPanel(int newX, int newY)
  {
   //--- clamp so the title bar always stays reachable - keeps at least
   //--- TITLE_BAR_H of vertical room and 60px of horizontal room on screen,
   //--- so a drag can never strand the panel somewhere it can't be dragged
   //--- back from.
   int chartW = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   if(newX < 0) newX = 0;
   if(newY < 0) newY = 0;
   if(chartW > 0 && newX > chartW - 60) newX = chartW - 60;
   if(chartH > 0 && newY > chartH - TITLE_BAR_H) newY = chartH - TITLE_BAR_H;

   int dx = newX - g_panelX;
   int dy = newY - g_panelY;
   g_panelX = newX;
   g_panelY = newY;
   long bgX = ObjectGetInteger(0, PFX + "bg", OBJPROP_XDISTANCE);
   long bgY = ObjectGetInteger(0, PFX + "bg", OBJPROP_YDISTANCE);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_XDISTANCE, bgX + dx);
   ObjectSetInteger(0, PFX + "bg", OBJPROP_YDISTANCE, bgY + dy);
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
bool PointOverTitleBar(int mx, int my)
  {
   return(mx >= g_panelX && mx <= g_panelX + g_panelW && my >= g_panelY && my <= g_panelY + TITLE_BAR_H);
  }

//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_MOUSE_MOVE)
     {
      int mx = (int)lparam;
      int my = (int)dparam;
      int flags = (int)StringToInteger(sparam);
      bool leftDown = (flags & 1) != 0;
      if(!g_dragging && leftDown && PointOverTitleBar(mx, my))
        {
         g_dragging = true;
         g_dragOffX = mx - g_panelX;
         g_dragOffY = my - g_panelY;
         //--- MT5's native left-drag-to-scroll is still live underneath this
         //--- handler and would pan the chart at the same time the panel
         //--- moves - suspend it for the duration of the drag, restore on
         //--- release below.
         ChartSetInteger(0, CHART_MOUSE_SCROLL, false);
         g_dragStartMs = GetTickCount64();
        }
      if(g_dragging)
        {
         if(!leftDown)
           {
            g_dragging = false;
            ChartSetInteger(0, CHART_MOUSE_SCROLL, true);
            //--- reclaim top paint order THE MOMENT the drag ends, rather than
            //--- waiting for the next new bar - otherwise, on a slower
            //--- timeframe, the panel can sit buried under any MA/VWAP segment
            //--- drawn in the gap (visibly cutting through it) for however long
            //--- it takes the next bar to arrive.
            RebuildPanel();
           }
         else
           {
            //--- throttled: CHARTEVENT_MOUSE_MOVE fires dozens of times a
            //--- second while dragging, and this used to reposition ~30
            //--- objects and force a full ChartRedraw() on EVERY one of them -
            //--- that was the real cause of the chart hanging during a drag.
            //--- ~30 updates/sec is still visually smooth and far cheaper.
            ulong now = GetTickCount64();
            if(now - g_lastDragUpdateMs >= 33)
              {
               g_lastDragUpdateMs = now;
               DragPanel(mx - g_dragOffX, my - g_dragOffY);
              }
           }
        }
      return;
     }
   if(id != CHARTEVENT_OBJECT_CLICK) return;

   //--- OnTimer no longer force-redraws every second (that was the real
   //--- cause of the general lag, including clicks feeling slow - the chart
   //--- was busy redrawing ~1300 background objects every single second
   //--- regardless of whether anything changed). Every button/edit handler
   //--- below still needs its own immediate visible update though, so
   //--- redraw once here, right after whichever one of them ran.
   if(sparam == PFX + "lotEdit" || sparam == PFX + "cntEdit")
     {
      UpdateExposureLabel();
      ChartRedraw(0);
      return;
     }
   if(sparam == PFX + "delayEdit") { SyncArmSecondsFromEdit(); ChartRedraw(0); return; }
   if(sparam == PFX + "lotMinus") { AdjustLot(-SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)); ChartRedraw(0); return; }
   if(sparam == PFX + "lotPlus")  { AdjustLot(+SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)); ChartRedraw(0); return; }
   if(sparam == PFX + "cntMinus") { AdjustCount(-1); ChartRedraw(0); return; }
   if(sparam == PFX + "cntPlus")  { AdjustCount(+1); ChartRedraw(0); return; }
   if(sparam == PFX + "delayMinus") { AdjustArmSeconds(-1); ChartRedraw(0); return; }
   if(sparam == PFX + "delayPlus")  { AdjustArmSeconds(+1); ChartRedraw(0); return; }
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
      ChartRedraw(0);
      return;
     }
   if(sparam == PFX + "sellBtn")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      PlaceBatch(false);
      UpdateStats();
      ChartRedraw(0);
      return;
     }
   if(sparam == PFX + "c25") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); ClosePct(0.25); UpdateStats(); ChartRedraw(0); return; }
   if(sparam == PFX + "c50") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); ClosePct(0.50); UpdateStats(); ChartRedraw(0); return; }
   if(sparam == PFX + "c75") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); ClosePct(0.75); UpdateStats(); ChartRedraw(0); return; }
   if(sparam == PFX + "cAll") { ObjectSetInteger(0, sparam, OBJPROP_STATE, false); CloseAll(); UpdateStats(); ChartRedraw(0); return; }
   if(sparam == PFX + "slEdit" || sparam == PFX + "tpEdit") return;
   if(sparam == PFX + "setSL")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      SetSLForAll(StringToDouble(ObjectGetString(0, PFX + "slEdit", OBJPROP_TEXT)));
      ChartRedraw(0);
      return;
     }
   if(sparam == PFX + "setTP")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      SetTPForAll(StringToDouble(ObjectGetString(0, PFX + "tpEdit", OBJPROP_TEXT)));
      ChartRedraw(0);
      return;
     }
   if(sparam == PFX + "fillCur")
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
      FillCurrentSLTP();
      ChartRedraw(0);
      return;
     }
  }
//+------------------------------------------------------------------+
