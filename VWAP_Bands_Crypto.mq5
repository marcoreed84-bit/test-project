//+------------------------------------------------------------------+
//|                                        VWAP_Bands_Crypto.mq5     |
//|  Multi-day anchored VWAP with volume-weighted standard-deviation |
//|  bands, for Bitcoin/crypto. Per direct request. Same construction|
//|  as VWAP_Bands_Metals.mq5 (not a separate file by accident - kept|
//|  genuinely separate per direct request, so each can be tuned     |
//|  independently without touching the other).                     |
//|                                                                   |
//|  RESETS DAILY at the UTC calendar-day boundary - crypto trades   |
//|  continuously through weekends (unlike Gold/Silver, which has    |
//|  this broker's own settlement gap at the same 00:00 mark), so    |
//|  the reset cadence is uninterrupted - a new day starts every     |
//|  single day with no gap, rather than skipping weekends. The      |
//|  reset MECHANISM is identical either way (new calendar date vs.  |
//|  the previous bar's date) - this file exists separately mainly   |
//|  so BTC's own volume-source question (below) and any future      |
//|  BTC-specific tuning stay independent of the metals file.        |
//|  Keeps InpDaysToShow days of these independently-anchored VWAP+  |
//|  band segments all visible at once - so you can see how price    |
//|  reacted to TODAY'S vwap as well as the last few days', not      |
//|  just the current session's.                                     |
//|                                                                   |
//|  Price source: Typical Price (High+Low+Close)/3, the standard    |
//|  VWAP convention. Volume source: tick_volume by default - this   |
//|  project has confirmed GOLD's real_volume is 0 on this broker,   |
//|  but has NOT separately verified whether BTCUSD's real_volume is |
//|  populated here (no BTC CSV with that column has been checked in |
//|  this project yet). InpUseRealVolume defaults OFF (same safe     |
//|  default as the metals file) - flip it on and compare only if    |
//|  you've confirmed this broker's BTC feed actually reports real   |
//|  traded volume, not just tick/quote count.                       |
//|                                                                   |
//|  Deviation bands (+-1SD, +-2SD, +-3SD) computed the standard      |
//|  volume-weighted way: variance = sum(v*tp^2)/sum(v) - vwap^2,    |
//|  same formula most platforms' own VWAP-band indicators use.      |
//|  Each band level is independently toggleable (InpShowSD1/2/3),   |
//|  with light/shallow shading between VWAP and SD1, SD1 and SD2,   |
//|  and SD2 and SD3 on each side (InpShowShading) - FIVE separate   |
//|  shaded regions (inner, outer1-upper, outer1-lower, outer2-upper,|
//|  outer2-lower), each its own DRAW_FILLING plot pair, since one   |
//|  fill plot can only shade ONE region per bar. Fill plots are     |
//|  declared BEFORE the line plots so MT5 draws them first/behind - |
//|  otherwise the shading would paint over and hide the VWAP/SD     |
//|  lines instead of sitting under them.                            |
//|                                                                   |
//|  NOTE (per direct request, 2026-10-25): a touch-and-reject signal|
//|  at this 3SD band was tested as a TradePanel construction (same  |
//|  2R/10-bar-swing TP/SL rigor as every other signal this project  |
//|  tests) and FAILED - OOS PF 0.803, win% 28.2 (needs >33.3% to    |
//|  break even at 2R), p=0.992 against a random-timing null using   |
//|  the identical TP/SL (worse than the already-failed 2SD version, |
//|  OOS PF 0.895) - worse than random timing. NOT implemented as a  |
//|  signal anywhere - this indicator's 3SD band is a visual         |
//|  reference only, same as every other level here. (Tested on      |
//|  GOLD M5 data - no BTC-specific test has been run, same           |
//|  limitation as every other construction in this project that     |
//|  hasn't had BTC data to test against.)                            |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property version   "1.11"
#property indicator_chart_window
#property indicator_buffers 17
#property indicator_plots   12

//--- fills FIRST (drawn behind the lines)
#property indicator_label1  "Inner band fill"
#property indicator_type1   DRAW_FILLING
#property indicator_color1  C'30,45,70'

#property indicator_label2  "Outer1 band fill (upper, 1SD-2SD)"
#property indicator_type2   DRAW_FILLING
#property indicator_color2  C'45,35,25'

#property indicator_label3  "Outer1 band fill (lower, 1SD-2SD)"
#property indicator_type3   DRAW_FILLING
#property indicator_color3  C'45,35,25'

#property indicator_label4  "Outer2 band fill (upper, 2SD-3SD)"
#property indicator_type4   DRAW_FILLING
#property indicator_color4  C'55,25,20'

#property indicator_label5  "Outer2 band fill (lower, 2SD-3SD)"
#property indicator_type5   DRAW_FILLING
#property indicator_color5  C'55,25,20'

//--- lines AFTER (drawn on top, stay visible over the shading)
#property indicator_label6  "VWAP"
#property indicator_type6   DRAW_LINE
#property indicator_color6  clrYellow
#property indicator_width6  2
#property indicator_style6  STYLE_SOLID

#property indicator_label7  "VWAP +1SD"
#property indicator_type7   DRAW_LINE
#property indicator_color7  clrDodgerBlue
#property indicator_width7  1
#property indicator_style7  STYLE_DOT

#property indicator_label8  "VWAP -1SD"
#property indicator_type8   DRAW_LINE
#property indicator_color8  clrDodgerBlue
#property indicator_width8  1
#property indicator_style8  STYLE_DOT

#property indicator_label9  "VWAP +2SD"
#property indicator_type9   DRAW_LINE
#property indicator_color9  clrOrange
#property indicator_width9  1
#property indicator_style9  STYLE_DOT

#property indicator_label10 "VWAP -2SD"
#property indicator_type10  DRAW_LINE
#property indicator_color10 clrOrange
#property indicator_width10 1
#property indicator_style10 STYLE_DOT

#property indicator_label11 "VWAP +3SD"
#property indicator_type11  DRAW_LINE
#property indicator_color11 clrRed
#property indicator_width11 1
#property indicator_style11 STYLE_DASH

#property indicator_label12 "VWAP -3SD"
#property indicator_type12  DRAW_LINE
#property indicator_color12 clrRed
#property indicator_width12 1
#property indicator_style12 STYLE_DASH

input group "=== VWAP settings ==="
input int    InpDaysToShow      = 5;        // how many calendar days of independently-anchored
                                             // VWAP+band segments to keep visible at once
input bool   InpUseRealVolume   = false;    // GOLD/SILVER real_volume is 0 on this broker's feed
                                             // (confirmed this project) - leave off unless you have
                                             // verified your own symbol/broker actually populates it
input group "=== Deviation bands - each independently toggleable ==="
input bool   InpShowSD1         = true;     // +-1 standard deviation lines
input bool   InpShowSD2         = true;     // +-2 standard deviation lines
input bool   InpShowSD3         = true;     // +-3 standard deviation lines - extreme moves, per
                                             // direct request ("in extreme cases price bounces off
                                             // near the 3rd deviation band") - visual reference only,
                                             // the equivalent signal construction was tested and
                                             // failed (see file header note)
input bool   InpShowShading     = true;     // shallow shading - inner (VWAP<->SD1), outer1
                                             // (SD1<->SD2) and outer2 (SD2<->SD3) regions, each only
                                             // shown if the SD level(s) it needs are themselves on
input bool   InpShadeInnerOnly  = false;    // true: skip BOTH outer (SD1<->SD2, SD2<->SD3) shaded
                                             // regions, keep only the inner VWAP<->SD1 band shaded
input bool   InpShadeOuterOnly  = false;    // true: skip the inner (VWAP<->SD1) shading, keep the
                                             // outer band(s) shaded (lighter-looking around VWAP)

//--- fill buffers (indices 0-9, matching plots 1-5 above, 2 buffers each)
double g_fillInnerUp[], g_fillInnerDn[];
double g_fillOuterUpHi[], g_fillOuterUpLo[];
double g_fillOuterDnHi[], g_fillOuterDnLo[];
double g_fillOuter2UpHi[], g_fillOuter2UpLo[];
double g_fillOuter2DnHi[], g_fillOuter2DnLo[];
//--- line buffers (indices 10-16, matching plots 6-12 above)
double g_vwap[], g_u1[], g_l1[], g_u2[], g_l2[], g_u3[], g_l3[];

int OnInit()
  {
   SetIndexBuffer(0,  g_fillInnerUp,    INDICATOR_DATA);
   SetIndexBuffer(1,  g_fillInnerDn,    INDICATOR_DATA);
   SetIndexBuffer(2,  g_fillOuterUpHi,  INDICATOR_DATA);
   SetIndexBuffer(3,  g_fillOuterUpLo,  INDICATOR_DATA);
   SetIndexBuffer(4,  g_fillOuterDnHi,  INDICATOR_DATA);
   SetIndexBuffer(5,  g_fillOuterDnLo,  INDICATOR_DATA);
   SetIndexBuffer(6,  g_fillOuter2UpHi, INDICATOR_DATA);
   SetIndexBuffer(7,  g_fillOuter2UpLo, INDICATOR_DATA);
   SetIndexBuffer(8,  g_fillOuter2DnHi, INDICATOR_DATA);
   SetIndexBuffer(9,  g_fillOuter2DnLo, INDICATOR_DATA);
   SetIndexBuffer(10, g_vwap,           INDICATOR_DATA);
   SetIndexBuffer(11, g_u1,             INDICATOR_DATA);
   SetIndexBuffer(12, g_l1,             INDICATOR_DATA);
   SetIndexBuffer(13, g_u2,             INDICATOR_DATA);
   SetIndexBuffer(14, g_l2,             INDICATOR_DATA);
   SetIndexBuffer(15, g_u3,             INDICATOR_DATA);
   SetIndexBuffer(16, g_l3,             INDICATOR_DATA);

   PlotIndexSetString(5, PLOT_LABEL, "VWAP");
   IndicatorSetString(INDICATOR_SHORTNAME, "VWAP Bands (Crypto, " + IntegerToString(InpDaysToShow) + "d)");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Volume-weighted VWAP + std-dev bands, reset at every new calendar |
//| day, computed over the last InpDaysToShow days of chart history   |
//| (plus a small margin so the oldest visible day's accumulator      |
//| doesn't start mid-day on a partial recalculation).                |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(rates_total < 2) return(0);

   //--- find how far back to (re)compute: InpDaysToShow FULL calendar days ending today.
   //--- v1.11 FIX (Opus-found): the old cutoff (last bar's time minus N+1 days, no midnight
   //--- alignment) landed mid-day, not on a day boundary - so the oldest shown day's VWAP
   //--- accumulator started partway through that day instead of at its own open, understating
   //--- its early bars' influence, and as `start` drifted forward on later calls, that same
   //--- day's values got silently recomputed from a later starting point, drawing a visible
   //--- step in what should be one continuous segment. Anchoring to the last bar's own
   //--- calendar-day midnight first, then stepping back exactly InpDaysToShow-1 more full days,
   //--- means `cutoff` itself IS a day boundary, so the earliest included day always starts
   //--- cleanly at its own open.
   datetime lastDay = time[rates_total - 1] - (time[rates_total - 1] % 86400);
   datetime cutoff = lastDay - (datetime)((long)(InpDaysToShow - 1) * 86400);
   int start = 0;
   for(int i = rates_total - 1; i >= 0; i--)
     {
      if(time[i] < cutoff) { start = i + 1; break; }
     }
   if(start < 0) start = 0;

   //--- full recompute from `start` every call - cheap (InpDaysToShow+1 days of bars only, not
   //--- the whole chart history) and avoids any incremental-state bugs across new bars/ticks.
   double sumV = 0.0, sumPV = 0.0, sumPV2V = 0.0;
   datetime curDay = 0;

   for(int i = start; i < rates_total; i++)
     {
      datetime d = time[i] - (time[i] % 86400);   // calendar-day floor, UTC/server time
      if(d != curDay)
        {
         curDay = d;
         sumV = 0.0; sumPV = 0.0; sumPV2V = 0.0;
        }

      double vol = InpUseRealVolume ? (double)volume[i] : (double)tick_volume[i];
      double tp  = (high[i] + low[i] + close[i]) / 3.0;

      if(vol > 0.0)
        {
         sumV    += vol;
         sumPV   += tp * vol;
         sumPV2V += tp * tp * vol;
        }
      //--- vol<=0 (shouldn't normally happen): carry the running VWAP/bands forward unchanged
      //--- rather than divide by zero or show a gap.

      if(sumV <= 0.0)
        {
         g_vwap[i] = EMPTY_VALUE; g_u1[i] = EMPTY_VALUE; g_l1[i] = EMPTY_VALUE;
         g_u2[i] = EMPTY_VALUE; g_l2[i] = EMPTY_VALUE; g_u3[i] = EMPTY_VALUE; g_l3[i] = EMPTY_VALUE;
         g_fillInnerUp[i] = EMPTY_VALUE; g_fillInnerDn[i] = EMPTY_VALUE;
         g_fillOuterUpHi[i] = EMPTY_VALUE; g_fillOuterUpLo[i] = EMPTY_VALUE;
         g_fillOuterDnHi[i] = EMPTY_VALUE; g_fillOuterDnLo[i] = EMPTY_VALUE;
         g_fillOuter2UpHi[i] = EMPTY_VALUE; g_fillOuter2UpLo[i] = EMPTY_VALUE;
         g_fillOuter2DnHi[i] = EMPTY_VALUE; g_fillOuter2DnLo[i] = EMPTY_VALUE;
         continue;
        }

      double vwap = sumPV / sumV;
      double variance = sumPV2V / sumV - vwap * vwap;
      if(variance < 0.0) variance = 0.0;   // guards against float rounding on a near-zero-vol bar
      double sd = MathSqrt(variance);
      double up1 = vwap + sd,       dn1 = vwap - sd;
      double up2 = vwap + 2.0 * sd, dn2 = vwap - 2.0 * sd;
      double up3 = vwap + 3.0 * sd, dn3 = vwap - 3.0 * sd;

      g_vwap[i] = vwap;
      g_u1[i] = InpShowSD1 ? up1 : EMPTY_VALUE;
      g_l1[i] = InpShowSD1 ? dn1 : EMPTY_VALUE;
      g_u2[i] = InpShowSD2 ? up2 : EMPTY_VALUE;
      g_l2[i] = InpShowSD2 ? dn2 : EMPTY_VALUE;
      g_u3[i] = InpShowSD3 ? up3 : EMPTY_VALUE;
      g_l3[i] = InpShowSD3 ? dn3 : EMPTY_VALUE;

      bool doInner  = InpShowShading && !InpShadeOuterOnly && InpShowSD1;
      bool doOuter1 = InpShowShading && !InpShadeInnerOnly && InpShowSD1 && InpShowSD2;
      bool doOuter2 = InpShowShading && !InpShadeInnerOnly && InpShowSD2 && InpShowSD3;

      g_fillInnerUp[i] = doInner ? up1 : EMPTY_VALUE;
      g_fillInnerDn[i] = doInner ? dn1 : EMPTY_VALUE;
      g_fillOuterUpHi[i] = doOuter1 ? up2 : EMPTY_VALUE;
      g_fillOuterUpLo[i] = doOuter1 ? up1 : EMPTY_VALUE;
      g_fillOuterDnHi[i] = doOuter1 ? dn1 : EMPTY_VALUE;
      g_fillOuterDnLo[i] = doOuter1 ? dn2 : EMPTY_VALUE;
      g_fillOuter2UpHi[i] = doOuter2 ? up3 : EMPTY_VALUE;
      g_fillOuter2UpLo[i] = doOuter2 ? up2 : EMPTY_VALUE;
      g_fillOuter2DnHi[i] = doOuter2 ? dn2 : EMPTY_VALUE;
      g_fillOuter2DnLo[i] = doOuter2 ? dn3 : EMPTY_VALUE;
     }

   return(rates_total);
  }
