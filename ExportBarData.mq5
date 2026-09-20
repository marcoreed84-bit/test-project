//+------------------------------------------------------------------+
//| ExportBarData.mq5                                                  |
//| Exports OHLCV + real spread + MT5-computed reference (chk_*)       |
//| columns to a CSV, in the exact format research/aurelius/engine.py  |
//| and research/ichimoku/engine.py already expect - same two-line     |
//| header, same column names, same chk_ema3/chk_ema21/chk_ema150/     |
//| chk_atr14/chk_macd validation columns used everywhere this project |
//| checks a Python replica against MT5's own real indicator output.   |
//|                                                                    |
//| Run as a SCRIPT (drag onto a chart, or right-click > Scripts),     |
//| not an EA - it exports history and exits, it does not trade.       |
//| Run once per timeframe you want (M5, H4, ...).                     |
//|                                                                    |
//| Output goes to <data folder>\MQL5\Files\<InpFileName> - find it    |
//| via File > Open Data Folder in the terminal, then MQL5\Files\.     |
//+------------------------------------------------------------------+
#property script_show_inputs

input string          InpSymbol    = "";               // Symbol (blank = current chart's symbol)
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_CURRENT;    // Timeframe to export (CURRENT = whatever chart this is attached to)
input int             InpBars      = 300000;            // How many bars back (0 = all available history)
input string          InpFileName  = "";                // Output filename (blank = auto: <symbol>_<period>.csv)

int      g_emaHandle3, g_emaHandle21, g_emaHandle150, g_atrHandle, g_macdHandle;

//+------------------------------------------------------------------+
int OnStart()
  {
   string sym = (InpSymbol == "") ? _Symbol : InpSymbol;
   // Resolve PERIOD_CURRENT to the ACTUAL timeframe up front, once - every
   // MT5 API call below (iMA/iATR/iMACD/CopyRates) treats PERIOD_CURRENT as
   // "whatever timeframe the CHART this script is attached to is showing",
   // not the symbol's own bars in some fixed sense - resolving it into a
   // concrete ENUM_TIMEFRAMES here means the exported filename and the
   // log message both show the real period, instead of the ambiguous
   // literal "PERIOD_CURRENT" string. This is also the actual fix for the
   // bug that shipped in v1: the Timeframe input previously defaulted to
   // the LITERAL constant PERIOD_M5, not PERIOD_CURRENT, so running the
   // script without touching that dropdown silently exported M5 regardless
   // of which chart it was dragged onto - confirmed by a real user-supplied
   // "4H" export that was byte-identical to the M5 one.
   ENUM_TIMEFRAMES tf = (InpTimeframe == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)_Period : InpTimeframe;

   if(!SymbolSelect(sym, true))
     {
      PrintFormat("ExportBarData: symbol \"%s\" not found/not selectable in Market Watch.", sym);
      return(-1);
     }
   PrintFormat("ExportBarData: exporting %s %s (resolved from input=%s, chart period=%s)",
               sym, EnumToString(tf), EnumToString(InpTimeframe), EnumToString((ENUM_TIMEFRAMES)_Period));

   // --- indicator handles for the chk_* reference columns - these are
   // MT5's OWN built-in computations, the same ones every engine.py in
   // this project validates its manual Python port against.
   g_emaHandle3   = iMA(sym, tf, 3,   0, MODE_EMA, PRICE_CLOSE);
   g_emaHandle21  = iMA(sym, tf, 21,  0, MODE_EMA, PRICE_CLOSE);
   g_emaHandle150 = iMA(sym, tf, 150, 0, MODE_EMA, PRICE_CLOSE);
   g_atrHandle    = iATR(sym, tf, 14);
   g_macdHandle   = iMACD(sym, tf, 12, 26, 9, PRICE_CLOSE);
   if(g_emaHandle3 == INVALID_HANDLE || g_emaHandle21 == INVALID_HANDLE ||
      g_emaHandle150 == INVALID_HANDLE || g_atrHandle == INVALID_HANDLE ||
      g_macdHandle == INVALID_HANDLE)
     {
      Print("ExportBarData: failed to create one or more indicator handles.");
      return(-1);
     }

   // --- give the indicators a moment to calculate their buffers on a
   // fresh handle (0 on the first CopyBuffer call right after creation
   // is a known MT5 quirk) - retry a few times rather than fail once.
   for(int tries = 0; tries < 20; tries++)
     {
      if(BarsCalculated(g_atrHandle) > 0) break;
      Sleep(200);
     }

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = (InpBars <= 0)
      ? CopyRates(sym, tf, 0, 100000000, rates)
      : CopyRates(sym, tf, 0, InpBars, rates);
   if(copied <= 0)
     {
      PrintFormat("ExportBarData: CopyRates returned %d bars - error %d. "
                  "Try Tools>Options>Charts 'Max bars in history', or scroll the "
                  "chart far left first to force the terminal to download more history.",
                  copied, GetLastError());
      return(-1);
     }

   double ema3[], ema21[], ema150[], atr[], macdMain[];
   ArraySetAsSeries(ema3, false); ArraySetAsSeries(ema21, false);
   ArraySetAsSeries(ema150, false); ArraySetAsSeries(atr, false); ArraySetAsSeries(macdMain, false);
   if(CopyBuffer(g_emaHandle3,   0, rates[0].time, rates[copied-1].time, ema3)   <= 0 ||
      CopyBuffer(g_emaHandle21,  0, rates[0].time, rates[copied-1].time, ema21)  <= 0 ||
      CopyBuffer(g_emaHandle150, 0, rates[0].time, rates[copied-1].time, ema150) <= 0 ||
      CopyBuffer(g_atrHandle,    0, rates[0].time, rates[copied-1].time, atr)    <= 0 ||
      CopyBuffer(g_macdHandle,   0, rates[0].time, rates[copied-1].time, macdMain) <= 0)
     {
      PrintFormat("ExportBarData: CopyBuffer failed for one or more chk_* series, error %d. "
                  "This usually just means not enough warmup history is loaded - scroll the "
                  "chart far left to force it to download further back, then re-run.",
                  GetLastError());
      return(-1);
     }
   // CopyBuffer by time range can return fewer points than CopyRates if any
   // indicator's own warmup eats into the front of the window - align by
   // time explicitly rather than assuming array positions line up 1:1.
   // Build lookup arrays only if needed (rare on M5/H4 with 14/21/150-period
   // warmups against a few hundred thousand bars); simplest robust approach:
   // require exact length match, else abort with a clear message rather than
   // silently misaligning chk_* columns against the wrong bar.
   if(ArraySize(ema3) != copied || ArraySize(ema21) != copied ||
      ArraySize(ema150) != copied || ArraySize(atr) != copied || ArraySize(macdMain) != copied)
     {
      PrintFormat("ExportBarData: chk_* buffer length mismatch (rates=%d ema3=%d ema21=%d ema150=%d atr=%d macd=%d) - "
                  "not enough warmup history loaded before the export window. Scroll the chart far left "
                  "(or reduce InpBars) so every indicator has its full lookback available, then re-run.",
                  copied, ArraySize(ema3), ArraySize(ema21), ArraySize(ema150), ArraySize(atr), ArraySize(macdMain));
      return(-1);
     }

   string fname = (InpFileName == "")
      ? StringFormat("%s_%s.csv", sym, EnumToString(tf))
      : InpFileName;
   int fh = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
     {
      PrintFormat("ExportBarData: FileOpen(\"%s\") failed, error %d", fname, GetLastError());
      return(-1);
     }

   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);
   double contractSize = SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE);

   FileWrite(fh, StringFormat("meta_symbol,%s,meta_digits,%d,meta_point,%s,meta_contract_size,%s",
             sym, digits, DoubleToString(point, digits), DoubleToString(contractSize, 2)));
   FileWrite(fh, "time,open,high,low,close,tick_volume,real_volume,spread,chk_ema3,chk_ema21,chk_ema150,chk_atr14,chk_macd");

   for(int i = 0; i < copied; i++)
     {
      FileWrite(fh,
         StringFormat("%s,%s,%s,%s,%s,%d,%d,%d,%s,%s,%s,%s,%s",
            TimeToString(rates[i].time, TIME_DATE | TIME_SECONDS),
            DoubleToString(rates[i].open, digits),
            DoubleToString(rates[i].high, digits),
            DoubleToString(rates[i].low, digits),
            DoubleToString(rates[i].close, digits),
            (int)rates[i].tick_volume,
            (int)rates[i].real_volume,
            (int)rates[i].spread,
            DoubleToString(ema3[i], digits + 3),
            DoubleToString(ema21[i], digits + 3),
            DoubleToString(ema150[i], digits + 3),
            DoubleToString(atr[i], digits + 3),
            DoubleToString(macdMain[i], digits + 3)));
     }
   FileClose(fh);

   PrintFormat("ExportBarData: wrote %d bars of %s %s to <data folder>\\MQL5\\Files\\%s",
               copied, sym, EnumToString(tf), fname);
   return(0);
  }
