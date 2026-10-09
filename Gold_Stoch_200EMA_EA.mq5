//+------------------------------------------------------------------+
//|                                   Gold_Stoch_200EMA_EA.mq5       |
//|   Fixed/hardened copy of uploaded EA_Script.txt (2026-10-09).   |
//|   NOT YET BACKTESTED AGAINST REAL DATA - see                    |
//|   research/gold_stoch_200ema/stoch_200ema_test.py for the       |
//|   honest real-data verdict before this is ever run live.        |
//|                                                                   |
//|   Fixes applied to the original uploaded script:                |
//|   1. PositionsTotal()>0 entry gate checked EVERY position on the|
//|      WHOLE ACCOUNT, any symbol/magic - on a multi-EA account    |
//|      (this one runs 8+ EAs on one account) that's wrong: it     |
//|      would refuse to enter based on some OTHER EA's open trade. |
//|      Fixed to count only THIS EA's own symbol+magic positions,  |
//|      same pattern ManageBreakeven() already used correctly.     |
//|   2. No spread filter - added InpMaxSpreadPoints (off by        |
//|      default=0, matching the other EAs' pattern of this being   |
//|      an explicit opt-in).                                       |
//|   3. No broker min-stop-distance check - added, else a tight    |
//|      ATR stop can be rejected by the broker silently.           |
//|   4. trade.Buy() return value was never checked - added a       |
//|      Print() on failure so a bad order doesn't fail silently.   |
//|   5. Original is buy-only by design (no sell setup exists) -    |
//|      NOT changed here; adding a short side would be inventing a |
//|      new strategy, not fixing a bug. Flagged to the user         |
//|      separately as a structural limitation, not fixed silently.  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026"
#property link      ""
#property version   "1.05"

#include <Trade\Trade.mqh>
CTrade trade;

// Strategy Inputs
input int      StochK = 21;           // %K Period
input int      StochD = 5;            // %D Period
input int      StochSlowing = 5;      // Slowing
input int      EmaPeriod = 200;       // EMA Trend Period
input int      AtrPeriod = 14;        // Volatility ATR Period
input double   AtrMultiplier = 2.0;   // SL distance multiplier (Lower = tighter risk)
input double   RiskRewardRatio = 2.5; // Target Reward (Increased to out-earn the low win rate)

// Drawdown Defense Inputs
input double   RiskPercent = 1.0;     // % of Account Balance to risk per trade (e.g. 1.0%)
input bool     UseBreakeven = true;   // Move Stop Loss to breakeven when in profit?
input int      InpMaxSpreadPoints = 0;    // Max spread to allow entry, points (0 = off, fix #2)
input int      InpMagic = 123456;         // Magic number (was hardcoded, now configurable)

// Indicator Handles
int stochHandle;
int emaHandle;
int atrHandle;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);

   stochHandle = iStochastic(_Symbol, _Period, StochK, StochD, StochSlowing, MODE_SMA, STO_LOWHIGH);
   emaHandle   = iMA(_Symbol, _Period, EmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   atrHandle   = iATR(_Symbol, _Period, AtrPeriod);

   if(stochHandle == INVALID_HANDLE || emaHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
      return(INIT_FAILED);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| fix #1: count only THIS EA's own open positions (symbol+magic), |
//| not every position on the account like the original did         |
//+------------------------------------------------------------------+
int OwnPositionsCount()
{
   int cnt = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         cnt++;
   }
   return cnt;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Manage active positions first (Run on every tick for real-time breakeven defense)
   if(UseBreakeven && OwnPositionsCount() > 0)
   {
      ManageBreakeven();
   }

   // Entry logic runs strictly on Candle Close to avoid noise
   static datetime lastCandleTime;
   datetime currentCandleTime = iTime(_Symbol, _Period, 0);
   if(currentCandleTime == lastCandleTime) return;
   lastCandleTime = currentCandleTime;

   double kBuffer[], dBuffer[], emaBuffer[], atrBuffer[];
   MqlRates rates[];

   ArraySetAsSeries(rates, true);
   ArraySetAsSeries(kBuffer, true);
   ArraySetAsSeries(dBuffer, true);
   ArraySetAsSeries(emaBuffer, true);
   ArraySetAsSeries(atrBuffer, true);

   if(CopyRates(_Symbol, _Period, 0, 4, rates) < 4) return;
   if(CopyBuffer(stochHandle, 0, 0, 4, kBuffer) < 4) return;
   if(CopyBuffer(stochHandle, 1, 0, 4, dBuffer) < 4) return;
   if(CopyBuffer(emaHandle, 0, 0, 4, emaBuffer) < 4) return;
   if(CopyBuffer(atrHandle, 0, 0, 4, atrBuffer) < 4) return;

   // fix #1: scoped to this EA's own symbol+magic, not the whole account
   if(OwnPositionsCount() > 0) return;

   // fix #2: spread filter (off by default, opt-in like the rest of this project's EAs)
   long spreadPoints = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && spreadPoints > InpMaxSpreadPoints) return;

   double closedPrice = rates[1].close;
   double closedEMA   = emaBuffer[1];
   double currentAtr  = atrBuffer[1];

   double currentK     = kBuffer[1];
   double currentD     = dBuffer[1];
   double prevK        = kBuffer[2];
   double prevD        = dBuffer[2];

   // BUY SETUP (original is buy-only by design - see header note, not changed here)
   if(closedPrice > closedEMA)
   {
      if(prevK <= prevD && currentK > currentD && currentK < 30)
      {
         double askPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double slDistance = currentAtr * AtrMultiplier;

         // fix #3: respect the broker's minimum stop distance
         double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
         if(slDistance < stopsLevel) slDistance = stopsLevel;

         // Calculate dynamic lot size based on account risk rules
         double lotSize = CalculateLotSize(slDistance);
         if(lotSize <= 0) return;

         double slPrice    = askPrice - slDistance;
         double tpPrice    = askPrice + (slDistance * RiskRewardRatio);

         // fix #4: check and log the order result instead of failing silently
         if(!trade.Buy(lotSize, _Symbol, askPrice, slPrice, tpPrice, "Gold Drawdown Shield"))
            PrintFormat("Gold_Stoch_200EMA_EA: Buy() failed, retcode=%d (%s)",
                        trade.ResultRetcode(), trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate institutional lot size based on account balance risk   |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistance)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * (RiskPercent / 100.0);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(slDistance <= 0 || tickValue <= 0 || tickSize <= 0) return 0;

   // Formula to calculate precise lot allocation
   double calculatedLots = riskAmount / ((slDistance / tickSize) * tickValue);

   // Align with broker boundaries
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   calculatedLots = MathFloor(calculatedLots / lotStep) * lotStep;

   if(calculatedLots < minLot) calculatedLots = minLot;
   if(calculatedLots > maxLot) calculatedLots = maxLot;

   return calculatedLots;
}

//+------------------------------------------------------------------+
//| Active Trade Breakeven Protection Engine                         |
//+------------------------------------------------------------------+
void ManageBreakeven()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
      {
         double entryPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double currentSL  = PositionGetDouble(POSITION_SL);
         double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);

         // If current SL is already at or above entry, skip it
         if(currentSL >= entryPrice) continue;

         // Calculate how much the price has moved in our favor
         double priceMove = currentPrice - entryPrice;
         double initialRisk = entryPrice - currentSL;

         // If price has moved 100% of our initial risk distance, lock in breakeven
         if(priceMove >= initialRisk)
         {
            // Move SL to entry price + tiny buffer to cover broker commission structures
            double newSL = entryPrice + (5 * _Point * 10);
            trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
         }
      }
   }
}
