//+------------------------------------------------------------------+
//|                                        VWAP_Bands_Metals.mq5     |
//|  Multi-day anchored VWAP with volume-weighted standard-deviation |
//|  bands, for Gold/Silver. Per direct request.                     |
//|                                                                   |
//|  RESETS DAILY (one VWAP anchor per calendar day - this project's |
//|  established daily boundary, the broker's own settlement break   |
//|  at the 00:00 calendar-day mark - see engine.py's load_m5() area |
//|  comments elsewhere in this project for the same convention),    |
//|  but keeps InpDaysToShow days of these independently-anchored    |
//|  VWAP+band segments all visible at once - so you can see how     |
//|  price reacted to TODAY'S vwap as well as the last few days',    |
//|  not just the current session's.                                 |
//|                                                                   |
//|  Price source: Typical Price (High+Low+Close)/3, the standard    |
//|  VWAP convention. Volume source: tick_volume - this project has  |
//|  already confirmed GOLD's real_volume is 0 on this broker (see   |
//|  CLAUDE.md / battery3.py's own caveat on the same gap) - using   |
//|  real_volume here would silently produce an all-flat/undefined   |
//|  VWAP, so tick_volume (quote count) is the only usable proxy,    |
//|  same caveat as every other volume-based construction in this    |
//|  project. InpUseRealVolume exists in case that ever changes on   |
//|  a different symbol/broker, but defaults OFF.                    |
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
//|  reference only, same as every other level here.                 |
//|                                                                   |
//|  v1.12 (per direct request, 2026-10-26): added Weekly and Monthly|
//|  VWAP lines (InpShowWeeklyVWAP/InpShowMonthlyVWAP, each           |
//|  independently toggleable) - same accumulation logic as the daily|
//|  VWAP above, just reset at the week/month boundary instead of the|
//|  calendar day. No deviation bands on these two - line only, for  |
//|  visually judging multi-timeframe confluence against the daily   |
//|  VWAP/bands. A "daily+weekly+monthly VWAP confluence" touch-     |
//|  reject construction was tested as a TradePanel signal the same  |
//|  day this was added: looked the most internally consistent of    |
//|  any VWAP construction tried this session (every year 2022-2026  |
//|  individually profitable) but did NOT clear significance on its  |
//|  own (p(net)=0.064, p(PF)=0.184 against a random-timing null),   |
//|  and fails outright once honestly corrected for the ~5 VWAP      |
//|  constructions already tried this session (Sidak-corrected       |
//|  p=~0.28) - NOT implemented as a signal; these two lines are a    |
//|  visual reference only, same status as the SD bands above.       |
//|  CAVEAT: the weekly/monthly accumulator only has InpDaysToShow+1  |
//|  days of history to work with (same window the daily VWAP uses) - |
//|  if that's less than a full week/month (the usual case), the      |
//|  OLDEST visible week/month segment starts accumulating from       |
//|  wherever the visible window happens to begin, not from that      |
//|  week/month's own true calendar start - a real, visible           |
//|  understatement of that one segment's early history, same         |
//|  category of edge case as the daily VWAP's own history-available   |
//|  limit (just more likely to matter here, since a week/month is     |
//|  longer than the typical few-day display window). Increase          |
//|  InpDaysToShow to a full week (7+) or month (31+) if you need the     |
//|  weekly/monthly line itself to be clean from its very first visible    |
//|  bar, rather than just "close enough" after the first visible day/week.|
//|                                                                   |
//|  v1.14 (per direct request/observation - "would VWAP not be at the|
//|  same price levels whether I attach it to 5min, 15min, or 1 hour?"|
//|  / "I thought it has to be the same price level on any timeframe"):|
//|  CORRECT in principle - a true VWAP depends only on the underlying |
//|  trades in the period, not on which chart you view it from. v1.13  |
//|  and earlier computed VWAP from whatever bars the CHART ITSELF was  |
//|  on (an M5 bar's own typical price on an M5 chart, an H1 bar's own   |
//|  typical price on an H1 chart) - a cruder approximation the bigger    |
//|  the bars get, which is what caused different timeframes to show       |
//|  visibly different VWAP levels. Fixed: VWAP/bands are now ALWAYS        |
//|  computed from M1 bars internally (via CopyRates(PERIOD_M1), fully       |
//|  independent of whatever timeframe the chart/indicator is actually        |
//|  attached to), then mapped onto whichever chart bars are being drawn -     |
//|  so M5/M15/H1/etc. now converge to the same VWAP at the same moment,       |
//|  matching what VWAP is supposed to mean. InpUseM1Source (default true)      |
//|  is the escape hatch back to the old per-chart-bar behavior if you ever     |
//|  need it (e.g. M1 history unavailable for this symbol/broker). Recomputes    |
//|  at most once per newly CLOSED M1 bar (not per tick, not per chart bar) -     |
//|  so VWAP updates up to once a minute regardless of chart timeframe, which      |
//|  is already far more granular than an H1/H4 chart's own bar closes.             |
//+------------------------------------------------------------------+
#property copyright "Marco"
#property version   "1.14"
#property indicator_chart_window
#property indicator_buffers 19
#property indicator_plots   14

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

#property indicator_label13 "Weekly VWAP"
#property indicator_type13  DRAW_LINE
#property indicator_color13 clrMagenta
#property indicator_width13 2
#property indicator_style13 STYLE_SOLID

#property indicator_label14 "Monthly VWAP"
#property indicator_type14  DRAW_LINE
#property indicator_color14 clrLime
#property indicator_width14 2
#property indicator_style14 STYLE_SOLID

input group "=== VWAP settings ==="
input int    InpDaysToShow      = 31;       // how many calendar days of independently-anchored
                                             // VWAP+band segments to keep visible at once - also
                                             // doubles as the Weekly/Monthly VWAP lines' own history
                                             // window (see their v1.12 note above), so bumped from
                                             // 5 to 31 per direct request: 31 days covers a full
                                             // calendar month cleanly (and a full week several times
                                             // over), so both lines' oldest visible segment now
                                             // starts at that period's own true calendar boundary
                                             // instead of wherever a shorter window happened to begin
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

input group "=== Weekly / Monthly VWAP (per direct request) - confluence reference, no bands ==="
input bool   InpShowWeeklyVWAP  = true;     // resets at the start of each week (Monday 00:00)
input bool   InpShowMonthlyVWAP = true;     // resets at the start of each calendar month

input group "=== VWAP source (v1.14, per direct request) ==="
input bool   InpUseM1Source     = true;     // compute VWAP/bands from M1 bars always, independent of
                                             // the chart's own timeframe, so M5/M15/H1/etc. all show the
                                             // SAME VWAP at the same moment (see file header's v1.14
                                             // note). false = old per-chart-bar behavior (escape hatch -
                                             // only needed if M1 history isn't available for this
                                             // symbol/broker).

//--- fill buffers (indices 0-9, matching plots 1-5 above, 2 buffers each)
double g_fillInnerUp[], g_fillInnerDn[];
double g_fillOuterUpHi[], g_fillOuterUpLo[];
double g_fillOuterDnHi[], g_fillOuterDnLo[];
double g_fillOuter2UpHi[], g_fillOuter2UpLo[];
double g_fillOuter2DnHi[], g_fillOuter2DnLo[];
//--- line buffers (indices 10-16, matching plots 6-12 above)
double g_vwap[], g_u1[], g_l1[], g_u2[], g_l2[], g_u3[], g_l3[];
//--- weekly/monthly VWAP line buffers (indices 17-18, matching plots 13-14)
double g_vwapW[], g_vwapM[];

//--- v1.14: M1-computed source arrays (chronological, index 0 = oldest),
//--- rebuilt at most once per newly closed M1 bar, then mapped onto
//--- whatever chart bars are actually being drawn - see ComputeFromM1()
//--- and MapM1ToChart() below.
datetime g_m1Time[];
double   g_m1Vwap[], g_m1U1[], g_m1L1[], g_m1U2[], g_m1L2[], g_m1U3[], g_m1L3[];
double   g_m1VwapW[], g_m1VwapM[];
datetime g_lastM1Time = 0;

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
   SetIndexBuffer(17, g_vwapW,          INDICATOR_DATA);
   SetIndexBuffer(18, g_vwapM,          INDICATOR_DATA);

   PlotIndexSetString(5, PLOT_LABEL, "VWAP");
   IndicatorSetString(INDICATOR_SHORTNAME, "VWAP Bands (Metals, " + IntegerToString(InpDaysToShow) + "d)");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Calendar-day-aligned cutoff: InpDaysToShow FULL calendar days      |
//| ending on `lastDay`'s own day. Shared by both compute paths.       |
//+------------------------------------------------------------------+
datetime VwapCutoff(const datetime lastBarTime)
  {
   datetime lastDay = lastBarTime - (lastBarTime % 86400);
   return lastDay - (datetime)((long)(InpDaysToShow - 1) * 86400);
  }

//+------------------------------------------------------------------+
//| Fills one bar's worth of VWAP/band/fill output, given that bar's   |
//| running sums - shared by the M1 path and the legacy chart-bar path |
//| so the math can never drift apart between the two.                 |
//+------------------------------------------------------------------+
void VwapBarOutput(const double sumV, const double sumPV, const double sumPV2V,
                    const double sumVW, const double sumPVW, const double sumVM, const double sumPVM,
                    double &vwapOut, double &u1Out, double &l1Out, double &u2Out, double &l2Out,
                    double &u3Out, double &l3Out, double &vwapWOut, double &vwapMOut,
                    double &fillInnerUp, double &fillInnerDn, double &fillOuterUpHi, double &fillOuterUpLo,
                    double &fillOuterDnHi, double &fillOuterDnLo, double &fillOuter2UpHi, double &fillOuter2UpLo,
                    double &fillOuter2DnHi, double &fillOuter2DnLo)
  {
   vwapWOut = (InpShowWeeklyVWAP  && sumVW > 0.0) ? (sumPVW / sumVW) : EMPTY_VALUE;
   vwapMOut = (InpShowMonthlyVWAP && sumVM > 0.0) ? (sumPVM / sumVM) : EMPTY_VALUE;

   if(sumV <= 0.0)
     {
      vwapOut = EMPTY_VALUE; u1Out = EMPTY_VALUE; l1Out = EMPTY_VALUE;
      u2Out = EMPTY_VALUE; l2Out = EMPTY_VALUE; u3Out = EMPTY_VALUE; l3Out = EMPTY_VALUE;
      fillInnerUp = EMPTY_VALUE; fillInnerDn = EMPTY_VALUE;
      fillOuterUpHi = EMPTY_VALUE; fillOuterUpLo = EMPTY_VALUE;
      fillOuterDnHi = EMPTY_VALUE; fillOuterDnLo = EMPTY_VALUE;
      fillOuter2UpHi = EMPTY_VALUE; fillOuter2UpLo = EMPTY_VALUE;
      fillOuter2DnHi = EMPTY_VALUE; fillOuter2DnLo = EMPTY_VALUE;
      return;
     }

   double vwap = sumPV / sumV;
   double variance = sumPV2V / sumV - vwap * vwap;
   if(variance < 0.0) variance = 0.0;
   double sd = MathSqrt(variance);
   double up1 = vwap + sd,       dn1 = vwap - sd;
   double up2 = vwap + 2.0 * sd, dn2 = vwap - 2.0 * sd;
   double up3 = vwap + 3.0 * sd, dn3 = vwap - 3.0 * sd;

   vwapOut = vwap;
   u1Out = InpShowSD1 ? up1 : EMPTY_VALUE;
   l1Out = InpShowSD1 ? dn1 : EMPTY_VALUE;
   u2Out = InpShowSD2 ? up2 : EMPTY_VALUE;
   l2Out = InpShowSD2 ? dn2 : EMPTY_VALUE;
   u3Out = InpShowSD3 ? up3 : EMPTY_VALUE;
   l3Out = InpShowSD3 ? dn3 : EMPTY_VALUE;

   bool doInner  = InpShowShading && !InpShadeOuterOnly && InpShowSD1;
   bool doOuter1 = InpShowShading && !InpShadeInnerOnly && InpShowSD1 && InpShowSD2;
   bool doOuter2 = InpShowShading && !InpShadeInnerOnly && InpShowSD2 && InpShowSD3;

   fillInnerUp = doInner ? up1 : EMPTY_VALUE;
   fillInnerDn = doInner ? dn1 : EMPTY_VALUE;
   fillOuterUpHi = doOuter1 ? up2 : EMPTY_VALUE;
   fillOuterUpLo = doOuter1 ? up1 : EMPTY_VALUE;
   fillOuterDnHi = doOuter1 ? dn1 : EMPTY_VALUE;
   fillOuterDnLo = doOuter1 ? dn2 : EMPTY_VALUE;
   fillOuter2UpHi = doOuter2 ? up3 : EMPTY_VALUE;
   fillOuter2UpLo = doOuter2 ? up2 : EMPTY_VALUE;
   fillOuter2DnHi = doOuter2 ? dn2 : EMPTY_VALUE;
   fillOuter2DnLo = doOuter2 ? dn3 : EMPTY_VALUE;
  }

//+------------------------------------------------------------------+
//| Legacy path (InpUseM1Source=false): VWAP computed from whatever    |
//| bars the CHART ITSELF is on - the pre-v1.14 behavior, kept as an   |
//| escape hatch. Writes directly into the display buffers.            |
//+------------------------------------------------------------------+
void ComputeFromChartBars(const int rates_total, const datetime &time[],
                           const double &high[], const double &low[], const double &close[],
                           const long &tick_volume[], const long &volume[])
  {
   datetime cutoff = VwapCutoff(time[rates_total - 1]);
   int start = 0;
   for(int i = rates_total - 1; i >= 0; i--)
      if(time[i] < cutoff) { start = i + 1; break; }
   if(start < 0) start = 0;

   double sumV = 0.0, sumPV = 0.0, sumPV2V = 0.0;
   datetime curDay = 0;
   double sumVW = 0.0, sumPVW = 0.0; datetime curWeek = 0;
   double sumVM = 0.0, sumPVM = 0.0; datetime curMonth = 0;

   for(int i = start; i < rates_total; i++)
     {
      datetime d = time[i] - (time[i] % 86400);
      if(d != curDay) { curDay = d; sumV = 0.0; sumPV = 0.0; sumPV2V = 0.0; }

      MqlDateTime mdt;
      TimeToStruct(d, mdt);
      int daysSinceMonday = (mdt.day_of_week + 6) % 7;
      datetime weekStart = d - (datetime)daysSinceMonday * 86400;
      if(weekStart != curWeek) { curWeek = weekStart; sumVW = 0.0; sumPVW = 0.0; }

      mdt.day = 1; mdt.hour = 0; mdt.min = 0; mdt.sec = 0;
      datetime monthStart = StructToTime(mdt);
      if(monthStart != curMonth) { curMonth = monthStart; sumVM = 0.0; sumPVM = 0.0; }

      double vol = InpUseRealVolume ? (double)volume[i] : (double)tick_volume[i];
      double tp  = (high[i] + low[i] + close[i]) / 3.0;
      if(vol > 0.0)
        {
         sumV += vol; sumPV += tp * vol; sumPV2V += tp * tp * vol;
         sumVW += vol; sumPVW += tp * vol;
         sumVM += vol; sumPVM += tp * vol;
        }

      VwapBarOutput(sumV, sumPV, sumPV2V, sumVW, sumPVW, sumVM, sumPVM,
                    g_vwap[i], g_u1[i], g_l1[i], g_u2[i], g_l2[i], g_u3[i], g_l3[i], g_vwapW[i], g_vwapM[i],
                    g_fillInnerUp[i], g_fillInnerDn[i], g_fillOuterUpHi[i], g_fillOuterUpLo[i],
                    g_fillOuterDnHi[i], g_fillOuterDnLo[i], g_fillOuter2UpHi[i], g_fillOuter2UpLo[i],
                    g_fillOuter2DnHi[i], g_fillOuter2DnLo[i]);
     }
  }

//+------------------------------------------------------------------+
//| v1.14: rebuilds the M1-sourced g_m1* arrays from scratch - called  |
//| only when a new M1 bar has closed (see OnCalculate), never per      |
//| tick. Same day/week/month accumulation logic as the legacy path,     |
//| just driven by M1 bars instead of whatever the chart is on, so       |
//| EVERY chart timeframe converges on the same VWAP.                     |
//+------------------------------------------------------------------+
bool ComputeFromM1(const datetime cutoff)
  {
   int needed = (int)MathMin(100000, ((long)(InpDaysToShow + 2)) * 1440);
   MqlRates m1[];
   ArraySetAsSeries(m1, false);
   int count = CopyRates(_Symbol, PERIOD_M1, 0, needed, m1);
   if(count < 2) return false;   // M1 history not ready yet - retry next call

   int start = 0;
   for(int i = count - 1; i >= 0; i--)
      if(m1[i].time < cutoff) { start = i + 1; break; }
   if(start < 0) start = 0;

   int n = count - start;
   ArrayResize(g_m1Time, n);
   ArrayResize(g_m1Vwap, n); ArrayResize(g_m1U1, n); ArrayResize(g_m1L1, n);
   ArrayResize(g_m1U2, n); ArrayResize(g_m1L2, n); ArrayResize(g_m1U3, n); ArrayResize(g_m1L3, n);
   ArrayResize(g_m1VwapW, n); ArrayResize(g_m1VwapM, n);

   double sumV = 0.0, sumPV = 0.0, sumPV2V = 0.0; datetime curDay = 0;
   double sumVW = 0.0, sumPVW = 0.0; datetime curWeek = 0;
   double sumVM = 0.0, sumPVM = 0.0; datetime curMonth = 0;
   //--- unused fill outputs for this pass - the M1 arrays only need VWAP/bands,
   //--- fills are derived at display-mapping time for the (far fewer) chart bars
   double fIU, fID, fOUH, fOUL, fODH, fODL, fO2UH, fO2UL, fO2DH, fO2DL;

   for(int j = start; j < count; j++)
     {
      int oi = j - start;
      datetime t = m1[j].time;
      g_m1Time[oi] = t;
      datetime d = t - (t % 86400);
      if(d != curDay) { curDay = d; sumV = 0.0; sumPV = 0.0; sumPV2V = 0.0; }

      MqlDateTime mdt;
      TimeToStruct(d, mdt);
      int daysSinceMonday = (mdt.day_of_week + 6) % 7;
      datetime weekStart = d - (datetime)daysSinceMonday * 86400;
      if(weekStart != curWeek) { curWeek = weekStart; sumVW = 0.0; sumPVW = 0.0; }

      mdt.day = 1; mdt.hour = 0; mdt.min = 0; mdt.sec = 0;
      datetime monthStart = StructToTime(mdt);
      if(monthStart != curMonth) { curMonth = monthStart; sumVM = 0.0; sumPVM = 0.0; }

      double vol = InpUseRealVolume ? (double)m1[j].real_volume : (double)m1[j].tick_volume;
      double tp  = (m1[j].high + m1[j].low + m1[j].close) / 3.0;
      if(vol > 0.0)
        {
         sumV += vol; sumPV += tp * vol; sumPV2V += tp * tp * vol;
         sumVW += vol; sumPVW += tp * vol;
         sumVM += vol; sumPVM += tp * vol;
        }

      VwapBarOutput(sumV, sumPV, sumPV2V, sumVW, sumPVW, sumVM, sumPVM,
                    g_m1Vwap[oi], g_m1U1[oi], g_m1L1[oi], g_m1U2[oi], g_m1L2[oi], g_m1U3[oi], g_m1L3[oi],
                    g_m1VwapW[oi], g_m1VwapM[oi],
                    fIU, fID, fOUH, fOUL, fODH, fODL, fO2UH, fO2UL, fO2DH, fO2DL);
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Maps the M1-sourced arrays onto whatever chart bars are actually   |
//| being drawn - for chart bar i (spanning [time[i], time[i]+perSec)),|
//| uses the M1-computed value as of the LAST M1 bar within that span, |
//| i.e. "VWAP as of the end of this chart bar". Both arrays are        |
//| chronological, so a single forward-advancing pointer is O(n) total. |
//+------------------------------------------------------------------+
void MapM1ToChart(const int rates_total, const datetime &time[], const int start)
  {
   int perSec = PeriodSeconds(PERIOD_CURRENT);
   int m1n = ArraySize(g_m1Time);
   if(m1n == 0) return;
   int m1ptr = 0;

   for(int i = start; i < rates_total; i++)
     {
      datetime spanEnd = time[i] + perSec - 1;
      while(m1ptr + 1 < m1n && g_m1Time[m1ptr + 1] <= spanEnd)
         m1ptr++;
      if(g_m1Time[m1ptr] > spanEnd && m1ptr == 0)
        {
         //--- this chart bar is entirely BEFORE the earliest M1 bar we have
         //--- (can happen right at the edge of the lookback window) - leave blank
         g_vwap[i] = EMPTY_VALUE; g_u1[i] = EMPTY_VALUE; g_l1[i] = EMPTY_VALUE;
         g_u2[i] = EMPTY_VALUE; g_l2[i] = EMPTY_VALUE; g_u3[i] = EMPTY_VALUE; g_l3[i] = EMPTY_VALUE;
         g_vwapW[i] = EMPTY_VALUE; g_vwapM[i] = EMPTY_VALUE;
         g_fillInnerUp[i] = EMPTY_VALUE; g_fillInnerDn[i] = EMPTY_VALUE;
         g_fillOuterUpHi[i] = EMPTY_VALUE; g_fillOuterUpLo[i] = EMPTY_VALUE;
         g_fillOuterDnHi[i] = EMPTY_VALUE; g_fillOuterDnLo[i] = EMPTY_VALUE;
         g_fillOuter2UpHi[i] = EMPTY_VALUE; g_fillOuter2UpLo[i] = EMPTY_VALUE;
         g_fillOuter2DnHi[i] = EMPTY_VALUE; g_fillOuter2DnLo[i] = EMPTY_VALUE;
         continue;
        }

      double vwap = g_m1Vwap[m1ptr], u1 = g_m1U1[m1ptr], l1 = g_m1L1[m1ptr];
      double u2 = g_m1U2[m1ptr], l2 = g_m1L2[m1ptr], u3 = g_m1U3[m1ptr], l3 = g_m1L3[m1ptr];
      g_vwap[i] = vwap; g_u1[i] = u1; g_l1[i] = l1; g_u2[i] = u2; g_l2[i] = l2; g_u3[i] = u3; g_l3[i] = l3;
      g_vwapW[i] = g_m1VwapW[m1ptr]; g_vwapM[i] = g_m1VwapM[m1ptr];

      bool doInner  = InpShowShading && !InpShadeOuterOnly && InpShowSD1 && vwap != EMPTY_VALUE;
      bool doOuter1 = InpShowShading && !InpShadeInnerOnly && InpShowSD1 && InpShowSD2 && vwap != EMPTY_VALUE;
      bool doOuter2 = InpShowShading && !InpShadeInnerOnly && InpShowSD2 && InpShowSD3 && vwap != EMPTY_VALUE;
      g_fillInnerUp[i] = doInner ? u1 : EMPTY_VALUE;
      g_fillInnerDn[i] = doInner ? l1 : EMPTY_VALUE;
      g_fillOuterUpHi[i] = doOuter1 ? u2 : EMPTY_VALUE;
      g_fillOuterUpLo[i] = doOuter1 ? u1 : EMPTY_VALUE;
      g_fillOuterDnHi[i] = doOuter1 ? l1 : EMPTY_VALUE;
      g_fillOuterDnLo[i] = doOuter1 ? l2 : EMPTY_VALUE;
      g_fillOuter2UpHi[i] = doOuter2 ? u3 : EMPTY_VALUE;
      g_fillOuter2UpLo[i] = doOuter2 ? u2 : EMPTY_VALUE;
      g_fillOuter2DnHi[i] = doOuter2 ? l2 : EMPTY_VALUE;
      g_fillOuter2DnLo[i] = doOuter2 ? l3 : EMPTY_VALUE;
     }
  }

//+------------------------------------------------------------------+
//| Volume-weighted VWAP + std-dev bands, reset at every new calendar |
//| day. v1.14: by default (InpUseM1Source=true) always computed from  |
//| M1 bars regardless of the chart's own timeframe, so every timeframe|
//| shows the same VWAP at the same moment - see file header's v1.14   |
//| note. Falls back to the pre-v1.14 per-chart-bar computation if      |
//| InpUseM1Source is turned off.                                       |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(rates_total < 2) return(0);

   if(!InpUseM1Source)
     {
      ComputeFromChartBars(rates_total, time, high, low, close, tick_volume, volume);
      return(rates_total);
     }

   datetime cutoff = VwapCutoff(time[rates_total - 1]);
   int start = 0;
   for(int i = rates_total - 1; i >= 0; i--)
      if(time[i] < cutoff) { start = i + 1; break; }
   if(start < 0) start = 0;

   //--- rebuild the M1 source only when a new M1 bar has actually closed
   //--- (or on the very first call) - NOT per tick, NOT per chart bar.
   datetime m1now = iTime(_Symbol, PERIOD_M1, 0);
   if(m1now != 0 && (m1now != g_lastM1Time || ArraySize(g_m1Time) == 0))
     {
      if(ComputeFromM1(cutoff))
         g_lastM1Time = m1now;
     }

   MapM1ToChart(rates_total, time, start);
   return(rates_total);
  }
