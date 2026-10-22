//+------------------------------------------------------------------+
//|                                  Cleanup_SR_TradePanel_Objects.mq5 |
//|  One-off SCRIPT (not an indicator or EA) - drag onto a chart once  |
//|  to delete every chart object ever created by TradePanel_EA.mq5    |
//|  (or its M5/M15 locked copies) and/or Important_SR_Levels.mq5,     |
//|  by their known name prefixes. Does NOT touch anything you've      |
//|  drawn yourself, or objects from any other program - only deletes  |
//|  names starting with one of the prefixes listed below. Removes     |
//|  itself from the chart automatically once done (scripts always do |
//|  this in MT5 - it is not left running).                           |
//|                                                                     |
//|  Why this exists: per direct report - "i have now had to remove    |
//|  both the indicator and tradepanel from the charts, what bothers   |
//|  me is when removing you have everything left on the charts as    |
//|  objects". Both programs' own OnDeinit() already delete their own  |
//|  objects by prefix when they get a clean removal - but OnDeinit    |
//|  only runs if the program actually gets a chance to (it can't run  |
//|  if the program is stuck/hung and gets force-killed instead,       |
//|  which is exactly the performance issue being investigated         |
//|  separately). This script cleans up whatever got left behind       |
//|  either way, independent of what caused it.                        |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property version   "1.00"
#property script_show_inputs

//--- every prefix either program has ever used, across every version
//--- shipped this session - kept in one place so a future version can
//--- just add a line here if a program ever adds a new prefix
string g_prefixes[] =
  {
   //--- TradePanel_EA.mq5 / TradePanel_EA_M5.mq5 / TradePanel_EA_M15.mq5
   "TPNL_",    // the panel itself (buttons, labels, edit boxes)
   "TPMA_",    // hand-drawn MA/VWAP line segments
   "TPEMX_",   // EMA21/50 cross overlay
   "TPSIG_",   // Stochastic overlay
   "TPCDL_",   // Engulfing (candlestick) overlay
   "TPRJX_",   // Rejection overlay
   "TPRJXM_",  // Rejection M15 overlay
   "TPDIV_",   // Divergence overlay
   "TPBB_",    // Bollinger outer-band overlay
   "TPFVG_",   // FVG zone rectangles
   "TPFVGX_",  // FVG signal arrows/SL lines
   "TPLIQ_",   // Liquidity zone rectangles
   "TPLIQX_",  // Liquidity signal arrows/SL lines
   //--- Important_SR_Levels.mq5
   "SRL_",     // intraday fractal S/R
   "SRLH4_",   // H4 fractal S/R
   "SRLD_",    // daily fractal S/R
   "SRLW_",    // weekly fractal S/R
   "SRLRHL_"   // recent N-day high/low/open/close
  };

input bool InpDryRun = false;   // true = only COUNT and PRINT what would be deleted, delete nothing -
                                 // run with this on first if you want to see the number before committing

//+------------------------------------------------------------------+
void OnStart()
  {
   int total = ObjectsTotal(0, 0, -1);
   int matched = 0, deleted = 0;
   //--- walk backwards since deleting shifts later indices down
   for(int i = total - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, 0, -1);
      bool hit = false;
      for(int p = 0; p < ArraySize(g_prefixes); p++)
        {
         if(StringFind(nm, g_prefixes[p]) == 0) { hit = true; break; }
        }
      if(!hit) continue;
      matched++;
      if(!InpDryRun)
        {
         if(ObjectDelete(0, nm)) deleted++;
        }
     }
   ChartRedraw(0);
   if(InpDryRun)
      PrintFormat("Cleanup_SR_TradePanel_Objects: DRY RUN - %d of %d chart objects match a known prefix "
                  "and would be deleted. Nothing was actually deleted. Re-run with InpDryRun=false to delete.",
                  matched, total);
   else
      PrintFormat("Cleanup_SR_TradePanel_Objects: deleted %d of %d matching objects (out of %d total chart "
                  "objects). Anything you drew yourself, or that belongs to another program, was left alone.",
                  deleted, matched, total);
  }
