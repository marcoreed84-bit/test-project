//+------------------------------------------------------------------+
//|                                  MarketStructure_Swings.mq5      |
//|  Visual-only market structure overlay - per direct request, auto- |
//|  labels confirmed swing highs/lows as HH/HL/LH/LL (Higher High,    |
//|  Higher Low, Lower High, Lower Low) as price makes them, so trend   |
//|  structure (uptrend = HH+HL, downtrend = LH+LL, a break = the        |
//|  first swing that goes against the run) is readable at a glance.      |
//|  No signal logic, no backtest claim attached - a discretionary read   |
//|  aid, same status as this project's VWAP/volume-profile indicators.    |
//|                                                                   |
//|  SWING DETECTION: the same causal fractal-pivot method already used|
//|  by TradePanel_EA's own Divergence/Liquidity overlays in this       |
//|  project (InpPivotWindow bars on each side) - bar i is a pivot high  |
//|  if its high is the max over [i-W, i+W], a pivot low if its low is    |
//|  the min over that same window. A pivot can only be CONFIRMED at      |
//|  bar i+W (needs W future bars to know it held), so every label here    |
//|  prints no earlier than that - no lookahead, same discipline as every   |
//|  signal overlay in this project.                                        |
//|                                                                   |
//|  CLASSIFICATION: each new confirmed swing high is compared to the  |
//|  PREVIOUS confirmed swing high only (not the low) - higher = HH,    |
//|  not higher = LH. Same logic for lows against the previous low:      |
//|  higher = HL, not higher (i.e. lower or equal) = LL. This is the      |
//|  standard definition - it does NOT itself decide "trend direction",   |
//|  that's left for you to read off the sequence of labels, same as       |
//|  any discretionary market-structure read.                               |
//|                                                                   |
//|  v1.01 (per direct request): added BUY/SELL continuation signal    |
//|  arrows - BUY on the first confirmed HL (Higher Low) immediately    |
//|  after the most recent confirmed swing high was itself an HH        |
//|  (i.e. structure reads HH-then-HL, the classic "pullback in an       |
//|  uptrend" entry); SELL on the first confirmed LH immediately after    |
//|  the most recent swing low was an LL (mirror case, downtrend          |
//|  pullback). Suggested stop = the swing's own extreme, target = fixed   |
//|  R:R off that stop (InpSwingRR) - same convention as every signal       |
//|  overlay in TradePanel_EA.mq5. Arrows use the same solid-fill           |
//|  Wingdings-233/234 technique TradePanel's own arrows use (v2.38 fix      |
//|  there - genuine OBJ_ARROW + explicit ARROWCODE, not OBJ_ARROW_UP/DOWN's  |
//|  hollow default).                                                          |
//|                                                                   |
//|  STATUS: UNVALIDATED - VISUAL ONLY. This construction has NOT been |
//|  through this project's rigor process (random-timing null, walk-    |
//|  forward split, real TP/SL, honest K correction) - it is a           |
//|  completely untested idea, drawn here because it was asked for, not   |
//|  because it has shown any edge. Do not trade this without first        |
//|  running it through the same test every other signal in this project   |
//|  gets (see volume_profile_poc_test.py / avwap_event_anchor_test.py in    |
//|  the scratchpad for the established methodology this project uses).      |
//|  The HH/HL/LH/LL LABELS themselves (no signal attached) are a separate    |
//|  visual-only feature from v1.00 and carry no backtest claim either way.    |
//+------------------------------------------------------------------+
//|  v1.02 (per direct request/observation - "most of the signals on   |
//|  the chart are just noise... we want the bigger moves" and "these   |
//|  levels on the chart are mostly where the stochastic turns"): two    |
//|  new noise filters, both on by default. InpMinMoveATR is a classic    |
//|  "ZigZag deviation" filter - unlike InpPivotWindow (which only         |
//|  filters by bar-COUNT), this filters by actual price MAGNITUDE: a       |
//|  pivot only counts as a real swing if it's at least InpMinMoveATR        |
//|  ATR away from the previous confirmed swing of the OPPOSITE type.         |
//|  InpRequireStochExtreme originally required %K to cross a hard         |
//|  15/85 zone (v1.02/v1.03) - replaced in v1.04 (see its own note        |
//|  below) with a local-turning-point check, since the fixed zone was      |
//|  far stricter than "where the stochastic turns" and over-filtered        |
//|  real swings in a steadily trending market. A pivot that fails either      |
//|  filter is skipped entirely: no label, no zigzag segment, no state         |
//|  update, no signal - as if the minor wiggle never happened, so the          |
//|  next REAL swing compares against the last REAL one, not the noise.          |
//|                                                                   |
//|  v1.04 (real definition fix, not just threshold tuning - per direct  |
//|  report "its still very extreme"): InpRequireStochExtreme now checks  |
//|  whether %K is a LOCAL TURNING POINT (a pivot in %K itself, over        |
//|  InpStochTurnWindow bars each side) instead of crossing a fixed 15/85    |
//|  zone. The old zone check was much stricter than "where the stochastic    |
//|  turns" literally means - in a steady trend with shallow pullbacks, %K     |
//|  often never reaches 15/85 at all, so nearly every swing got rejected       |
//|  regardless of InpMinMoveATR. Also lowered InpMinMoveATR 1.5->0.8 in v1.03.  |
//+------------------------------------------------------------------+
#property copyright "test-project"
#property version   "1.05"
#property indicator_chart_window
#property indicator_plots 0

input group "=== Swing detection ==="
input int    InpPivotWindow      = 5;       // bars on EACH side a pivot high/low must beat to confirm -
                                             // same default as this project's existing Divergence/
                                             // Liquidity overlays (InpDivPivotWindow/InpLiqPivotWindow)
input int    InpDaysToShow       = 10;      // how many calendar days of history to label

input group "=== Noise filters (v1.03) - STACK: a pivot needs BOTH on to pass, not either/or ==="
input double InpMinMoveATR       = 0.8;     // v1.03: lowered from 1.5 - per direct report, 1.5 combined
                                             // WITH InpRequireStochExtreme below was filtering out real
                                             // swings, not just noise (both filters must pass for a pivot
                                             // to count, so they compound - 1.5 ATR was already strict on
                                             // its own). A pivot only counts as a real swing if it's at
                                             // least this many ATR away from the previous CONFIRMED swing
                                             // of the OPPOSITE type (a classic "ZigZag deviation" filter -
                                             // unlike InpPivotWindow, which only filters by bar-count, this
                                             // filters by actual price MAGNITUDE). 0 = disable this filter
                                             // (keep only the Stochastic one below, if that one's on).
input bool   InpRequireStochExtreme = false; // v1.05 FIX (misread the original request, not a threshold
                                             // issue): the direct observation was that the FIRST, UN-
                                             // filtered version's swings already lined up with where the
                                             // stochastic turned - evidence the base swing detection was
                                             // sound, not a request to GATE on a stochastic condition. A
                                             // local price swing and a local %K turn coincide almost by
                                             // definition anyway, so this filter barely discriminates
                                             // anything on its own - InpMinMoveATR above is the real,
                                             // correctly-targeted lever for "fewer, bigger moves only".
                                             // Left in and still usable (now checks %K is a LOCAL TURNING
                                             // POINT, not a hard 15/85 zone crossing - the zone version was
                                             // a separate, real over-filtering bug from v1.02/v1.03, fixed
                                             // in v1.04) but defaulted OFF since it isn't what was asked for.
input int    InpStochKPeriod     = 14;
input int    InpStochSlowing     = 5;
input int    InpStochDPeriod     = 5;
input int    InpStochTurnWindow  = 3;       // v1.04: bars on each side %K must turn against to count as
                                             // a local extreme - smaller than InpPivotWindow on purpose,
                                             // since %K turns faster than price itself

input group "=== Labels ==="
input color  InpHHColor          = clrLime;         // Higher High
input color  InpHLColor          = C'0,180,255';    // Higher Low
input color  InpLHColor          = C'255,140,0';    // Lower High
input color  InpLLColor          = clrRed;          // Lower Low
input int    InpFontSize         = 8;
input double InpLabelOffsetATR   = 0.5;     // vertical clearance between the label and the actual
                                             // swing price, in ATR - keeps text from sitting on the wick

input group "=== Zigzag line (optional) ==="
input bool   InpShowZigzag       = true;    // connects consecutive confirmed swings with a line, same
                                             // visual idea as a standard ZigZag indicator
input color  InpZigzagColor      = C'150,150,150';
input int    InpZigzagWidth      = 1;
input ENUM_LINE_STYLE InpZigzagStyle = STYLE_SOLID;

input group "=== Structure-continuation BUY/SELL signal (NEW, v1.01) - UNVALIDATED, VISUAL ONLY ==="
input bool   InpShowSignals      = true;    // BUY on first HL after an HH; SELL on first LH after an LL
input color  InpBuyColor         = C'25,255,42';
input color  InpSellColor        = C'255,12,147';
input int    InpSigArrowSize     = 1;
input double InpSwingRR          = 2.0;     // R:R convention for the suggested TP reference line
input color  InpSigStopColor     = clrRed;
input color  InpSigTPColor       = clrYellow;
input int    InpSigLineBars      = 8;       // how many bars the SL/TP reference lines extend

#define MSW_PFX "MSW_"
#define SIG_NA EMPTY_VALUE

//+------------------------------------------------------------------+
//| Simple causal ATR over the scanned window - only used for label   |
//| clearance (and risk sizing for the SL/TP reference lines), not     |
//| for any trading decision beyond that.                              |
//+------------------------------------------------------------------+
void ComputeATR(const double &h[], const double &l[], const double &c[], const int n,
                 const int period, double &atr[])
  {
   ArrayResize(atr, n);
   ArrayInitialize(atr, SIG_NA);
   if(n < period + 1) return;
   double sum = 0.0;
   for(int i = 1; i <= period; i++)
      sum += MathMax(h[i] - l[i], MathMax(MathAbs(h[i] - c[i-1]), MathAbs(l[i] - c[i-1])));
   atr[period] = sum / period;
   for(int i = period + 1; i < n; i++)
     {
      double tr = MathMax(h[i] - l[i], MathMax(MathAbs(h[i] - c[i-1]), MathAbs(l[i] - c[i-1])));
      atr[i] = (atr[i-1] * (period - 1) + tr) / period;
     }
  }

//+------------------------------------------------------------------+
//| Classic Stochastic(K,slowing,D), Low/High price mode, SMA method -  |
//| same formula/convention as TradePanel_EA's own Stochastic overlay,  |
//| used here only to gate which pivots count as real swings (v1.02),   |
//| per direct observation that the chart's real turning points line    |
//| up with where %K actually reaches its extreme zone.                  |
//+------------------------------------------------------------------+
void ComputeStoch(const double &h[], const double &l[], const double &c[], const int n,
                   const int kPeriod, const int slowing, const int dPeriod, double &k[])
  {
   ArrayResize(k, n);
   ArrayInitialize(k, SIG_NA);
   int minBars = kPeriod + slowing;
   if(n < minBars) return;
   double rawK[];
   ArrayResize(rawK, n);
   ArrayInitialize(rawK, SIG_NA);
   for(int i = kPeriod - 1; i < n; i++)
     {
      double hh = h[i], ll = l[i];
      for(int j = i - kPeriod + 1; j <= i; j++) { hh = MathMax(hh, h[j]); ll = MathMin(ll, l[j]); }
      double range = hh - ll;
      rawK[i] = (range > 0.0) ? 100.0 * (c[i] - ll) / range : 50.0;
     }
   for(int i = kPeriod - 1 + slowing - 1; i < n; i++)
     {
      double sum = 0.0; int cnt = 0;
      for(int j = i - slowing + 1; j <= i; j++)
         if(rawK[j] != SIG_NA) { sum += rawK[j]; cnt++; }
      if(cnt > 0) k[i] = sum / cnt;
     }
  }

//+------------------------------------------------------------------+
//| v1.04: is stochK[i] a local turning point (min for a swing low,     |
//| max for a swing high) over InpStochTurnWindow bars each side? This  |
//| is what actually matches "where the stochastic turns" - a FIXED     |
//| 15/85 zone (the old v1.02/v1.03 check) is a much stricter, different|
//| condition that a shallow pullback in a strong trend often never     |
//| reaches at all.                                                     |
//+------------------------------------------------------------------+
bool IsStochLocalExtreme(const double &k[], const int n, const int i, const int window, const bool wantMin)
  {
   if(k[i] == SIG_NA) return false;
   int lo = (int)MathMax(0, i - window);
   int hi = (int)MathMin(n - 1, i + window);
   for(int j = lo; j <= hi; j++)
     {
      if(j == i || k[j] == SIG_NA) continue;
      if(wantMin && k[j] < k[i]) return false;
      if(!wantMin && k[j] > k[i]) return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Solid-filled buy/sell arrow - same technique as TradePanel_EA.mq5's|
//| v2.38 fix (generic OBJ_ARROW + explicit Wingdings code 233/234 =   |
//| filled triangle pointer, NOT OBJ_ARROW_UP/DOWN's hollow default).  |
//+------------------------------------------------------------------+
void DrawSigArrow(const string nm, const datetime t, const double price, const bool isBuy, const string tip)
  {
   if(ObjectFind(0, nm) >= 0) return;
   if(!ObjectCreate(0, nm, OBJ_ARROW, 0, t, price)) return;
   ObjectSetInteger(0, nm, OBJPROP_ARROWCODE, isBuy ? 233 : 234);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, isBuy ? InpBuyColor : InpSellColor);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, MathMax(1, InpSigArrowSize));
   ObjectSetInteger(0, nm, OBJPROP_BACK, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, tip);
  }

//+------------------------------------------------------------------+
void DrawSigLevel(const string nm, const datetime t1, const datetime t2, const double price,
                   const color col, const string tip)
  {
   if(ObjectFind(0, nm) >= 0) return;
   ObjectCreate(0, nm, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, tip);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   IndicatorSetString(INDICATOR_SHORTNAME, "Market Structure (HH/HL/LH/LL)");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, MSW_PFX);
  }

//+------------------------------------------------------------------+
//| Full recompute every call over the bounded recent window - same   |
//| cheap-and-simple convention as this project's other indicators    |
//| (InpDaysToShow+margin days only, not the whole chart history).    |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   int minBars = InpPivotWindow * 2 + 20;
   if(rates_total < minBars) return(0);

   datetime lastDay = time[rates_total - 1] - (time[rates_total - 1] % 86400);
   datetime cutoff  = lastDay - (datetime)((long)(InpDaysToShow - 1) * 86400);
   int start = 0;
   for(int i = rates_total - 1; i >= 0; i--)
      if(time[i] < cutoff) { start = i + 1; break; }
   //--- pivots near `start` need InpPivotWindow bars of LEFT context too, so
   //--- back up further for the scan itself (labels still only PRINT from
   //--- `start` onward via the lastLabelTime guard below, if you want - here
   //--- kept simple: every pivot fully inside [start-W, rates_total) prints).
   //--- also needs enough extra room for the Stochastic warm-up period when
   //--- InpRequireStochExtreme is on, so %K is actually defined that far back.
   int margin = (int)MathMax(MathMax(InpPivotWindow, InpStochTurnWindow), InpStochKPeriod + InpStochSlowing + 20);
   int scanStart = (int)MathMax(0, start - margin);

   double h[], l[], c[];
   int n = rates_total - scanStart;
   ArrayResize(h, n); ArrayResize(l, n); ArrayResize(c, n);
   for(int i = 0; i < n; i++) { h[i] = high[scanStart + i]; l[i] = low[scanStart + i]; c[i] = close[scanStart + i]; }
   double atr[];
   ComputeATR(h, l, c, n, 14, atr);
   double stochK[];
   if(InpRequireStochExtreme)
      ComputeStoch(h, l, c, n, InpStochKPeriod, InpStochSlowing, InpStochDPeriod, stochK);

   ObjectsDeleteAll(0, MSW_PFX);   // cheap over a bounded window - simplest way to avoid stale labels
                                   // from a shrinking/shifting window without extra bookkeeping

   bool haveHigh = false, haveLow = false;
   double lastHighPrice = 0.0, lastLowPrice = 0.0;
   datetime lastHighTime = 0, lastLowTime = 0;
   double lastSwingPrice = 0.0; datetime lastSwingTime = 0; bool haveLastSwing = false;
   string lastHighTag = "", lastLowTag = "";
   int perSec = PeriodSeconds(PERIOD_CURRENT);

   for(int i = InpPivotWindow; i < n - InpPivotWindow; i++)
     {
      int gi = scanStart + i;   // global bar index, for ATR offset lookup
      double off = (atr[i] == SIG_NA || atr[i] <= 0.0) ? 0.0 : InpLabelOffsetATR * atr[i];

      bool isPivotHigh = true, isPivotLow = true;
      for(int j = i - InpPivotWindow; j <= i + InpPivotWindow; j++)
        {
         if(j == i) continue;
         if(h[j] > h[i]) isPivotHigh = false;
         if(l[j] < l[i]) isPivotLow = false;
        }

      //--- v1.02 noise filters - per direct request/observation
      if(isPivotHigh)
        {
         if(InpRequireStochExtreme && !IsStochLocalExtreme(stochK, n, i, InpStochTurnWindow, false))
            isPivotHigh = false;
         else if(InpMinMoveATR > 0.0 && haveLow && atr[i] != SIG_NA && atr[i] > 0.0
                 && MathAbs(h[i] - lastLowPrice) < InpMinMoveATR * atr[i])
            isPivotHigh = false;   // too close to the last confirmed swing LOW to count as a real swing
        }
      if(isPivotLow)
        {
         if(InpRequireStochExtreme && !IsStochLocalExtreme(stochK, n, i, InpStochTurnWindow, true))
            isPivotLow = false;
         else if(InpMinMoveATR > 0.0 && haveHigh && atr[i] != SIG_NA && atr[i] > 0.0
                 && MathAbs(lastHighPrice - l[i]) < InpMinMoveATR * atr[i])
            isPivotLow = false;   // too close to the last confirmed swing HIGH to count as a real swing
        }

      if(isPivotHigh)
        {
         string tag = (haveHigh && h[i] > lastHighPrice) ? "HH" : "LH";
         color col  = (tag == "HH") ? InpHHColor : InpLHColor;
         string nm  = MSW_PFX + "lbl_" + IntegerToString((long)time[gi]) + "_H";
         ObjectCreate(0, nm, OBJ_TEXT, 0, time[gi], h[i] + off);
         ObjectSetString(0, nm, OBJPROP_TEXT, tag);
         ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
         ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpFontSize);
         ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_BOTTOM);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);

         if(InpShowZigzag && haveLastSwing)
           {
            string zn = MSW_PFX + "zz_" + IntegerToString((long)time[gi]) + "_H";
            ObjectCreate(0, zn, OBJ_TREND, 0, lastSwingTime, lastSwingPrice, time[gi], h[i]);
            ObjectSetInteger(0, zn, OBJPROP_COLOR, InpZigzagColor);
            ObjectSetInteger(0, zn, OBJPROP_WIDTH, InpZigzagWidth);
            ObjectSetInteger(0, zn, OBJPROP_STYLE, InpZigzagStyle);
            ObjectSetInteger(0, zn, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, zn, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, zn, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, zn, OBJPROP_BACK, true);
           }

         //--- v1.01: SELL continuation signal - fires when this confirmed
         //--- swing high is itself an LH AND the swing low immediately
         //--- before it was an LL (structure reads LL-then-LH, the mirror
         //--- of the BUY case below). UNVALIDATED - see file header.
         if(InpShowSignals && tag == "LH" && lastLowTag == "LL")
           {
            double stop = h[i];
            double entry = c[i];
            double risk = stop - entry;
            if(risk > 0.0)
              {
               double tp = entry - InpSwingRR * risk;
               string id = IntegerToString((long)time[gi]);
               DrawSigArrow(MSW_PFX + "sig_sell_" + id, time[gi], h[i] + off, false,
                            "Structure SELL: LH after LL (unvalidated)");
               DrawSigLevel(MSW_PFX + "sig_sell_sl_" + id, time[gi], time[gi] + InpSigLineBars * perSec,
                            stop, InpSigStopColor, "Structure SELL SL");
               DrawSigLevel(MSW_PFX + "sig_sell_tp_" + id, time[gi], time[gi] + InpSigLineBars * perSec,
                            tp, InpSigTPColor, "Structure SELL TP (" + DoubleToString(InpSwingRR, 1) + "R)");
              }
           }

         haveHigh = true; lastHighPrice = h[i]; lastHighTime = time[gi]; lastHighTag = tag;
         lastSwingPrice = h[i]; lastSwingTime = time[gi]; haveLastSwing = true;
        }

      if(isPivotLow)
        {
         string tag = (haveLow && l[i] > lastLowPrice) ? "HL" : "LL";
         color col  = (tag == "HL") ? InpHLColor : InpLLColor;
         string nm  = MSW_PFX + "lbl_" + IntegerToString((long)time[gi]) + "_L";
         ObjectCreate(0, nm, OBJ_TEXT, 0, time[gi], l[i] - off);
         ObjectSetString(0, nm, OBJPROP_TEXT, tag);
         ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
         ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpFontSize);
         ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_TOP);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);

         //--- v1.01: BUY continuation signal - fires when this confirmed
         //--- swing low is itself an HL AND the swing high immediately
         //--- before it was an HH (structure reads HH-then-HL, the classic
         //--- "pullback in an uptrend" entry). UNVALIDATED - see file header.
         if(InpShowSignals && tag == "HL" && lastHighTag == "HH")
           {
            double stop = l[i];
            double entry = c[i];
            double risk = entry - stop;
            if(risk > 0.0)
              {
               double tp = entry + InpSwingRR * risk;
               string id = IntegerToString((long)time[gi]);
               DrawSigArrow(MSW_PFX + "sig_buy_" + id, time[gi], l[i] - off, true,
                            "Structure BUY: HL after HH (unvalidated)");
               DrawSigLevel(MSW_PFX + "sig_buy_sl_" + id, time[gi], time[gi] + InpSigLineBars * perSec,
                            stop, InpSigStopColor, "Structure BUY SL");
               DrawSigLevel(MSW_PFX + "sig_buy_tp_" + id, time[gi], time[gi] + InpSigLineBars * perSec,
                            tp, InpSigTPColor, "Structure BUY TP (" + DoubleToString(InpSwingRR, 1) + "R)");
              }
           }

         if(InpShowZigzag && haveLastSwing)
           {
            string zn = MSW_PFX + "zz_" + IntegerToString((long)time[gi]) + "_L";
            ObjectCreate(0, zn, OBJ_TREND, 0, lastSwingTime, lastSwingPrice, time[gi], l[i]);
            ObjectSetInteger(0, zn, OBJPROP_COLOR, InpZigzagColor);
            ObjectSetInteger(0, zn, OBJPROP_WIDTH, InpZigzagWidth);
            ObjectSetInteger(0, zn, OBJPROP_STYLE, InpZigzagStyle);
            ObjectSetInteger(0, zn, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, zn, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, zn, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, zn, OBJPROP_BACK, true);
           }

         haveLow = true; lastLowPrice = l[i]; lastLowTime = time[gi]; lastLowTag = tag;
         lastSwingPrice = l[i]; lastSwingTime = time[gi]; haveLastSwing = true;
        }
     }

   ChartRedraw(0);
   return(rates_total);
  }
