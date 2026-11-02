//+------------------------------------------------------------------+
//|                                       CheckRealVolume_BTC.mq5    |
//|  One-shot diagnostic script, NOT a standing indicator - run it     |
//|  once (drag onto a BTCUSD chart, or Strategy Tester / Scripts tab) |
//|  to confirm whether this broker's BTCUSD feed actually populates   |
//|  real_volume, the same check already done for GOLD/SILVER earlier  |
//|  this project (confirmed 0 there). Prints the last InpBars bars'    |
//|  real_volume alongside tick_volume so you can read the answer        |
//|  straight off the Experts log - nothing here is assumed.              |
//+------------------------------------------------------------------+
#property copyright "test-project"
#property version   "1.00"
#property script_show_inputs

input int InpBars = 20;

void OnStart()
  {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpBars, rates);
   if(copied <= 0)
     {
      Print("CheckRealVolume_BTC: CopyRates failed, error ", GetLastError());
      return;
     }

   long totalReal = 0;
   PrintFormat("CheckRealVolume_BTC: %s %s - last %d bars (real_volume | tick_volume)",
               _Symbol, StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period), 7), copied);
   for(int i = 0; i < copied; i++)
     {
      PrintFormat("  %s   real=%I64d   tick=%I64d",
                  TimeToString(rates[i].time), rates[i].real_volume, rates[i].tick_volume);
      totalReal += rates[i].real_volume;
     }
   PrintFormat("CheckRealVolume_BTC: sum of real_volume across these %d bars = %I64d - %s",
               copied, totalReal,
               totalReal > 0 ? "NONZERO, real_volume IS populated on this feed"
                             : "ZERO, real_volume is NOT populated (same as GOLD/SILVER) - keep InpUseRealVolume=false");
  }
