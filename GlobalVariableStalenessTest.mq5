//+------------------------------------------------------------------+
//|                                   GlobalVariableStalenessTest.mq5 |
//|                                                                    |
//|  ONE-OFF DIAGNOSTIC SCRIPT - not an EA, does not trade, deletes     |
//|  its own test global variable when done. Answers a question three    |
//|  independent Opus code audits (2026-10-04) could not confirm from      |
//|  docs alone (mql5.com was unreachable from the audit environment):       |
//|                                                                            |
//|  Do GlobalVariableCheck() and/or GlobalVariableGet() themselves REFRESH    |
//|  a global variable's own last-modified time (what GlobalVariableTime()      |
//|  returns)? If either does, then every cross-EA "staleness" filter in this    |
//|  project (Vanguard_EA.mq5/Vanguard_M15_EA.mq5's InpUseAureliusFilter/         |
//|  InpUseMeridianFilter, reading Aurelius_EA.mq5/Aurelius_M15_EA.mq5/            |
//|  Meridian_EA.mq5's broadcast position - see each ReadAureliusDir()/            |
//|  ReadMeridianDir()-style function) NEVER actually goes stale, because          |
//|  the read call that's SUPPOSED to check staleness would itself keep            |
//|  resetting the clock it's checking - silently defeating the whole point         |
//|  of InpAureliusStaleSecs/InpMeridianStaleSecs (if the writer EA crashes or       |
//|  is removed while holding a position, the sibling EA could then block           |
//|  itself against that side INDEFINITELY instead of for the intended ~15-45         |
//|  minutes).                                                                         |
//|                                                                                      |
//|  METHOD: set a test global variable once (this alone legitimately updates            |
//|  its time - that's documented, expected behavior). Then read its time at              |
//|  several points, calling ONLY GlobalVariableCheck() or ONLY                            |
//|  GlobalVariableGet() between reads (never GlobalVariableSet() again) - if              |
//|  the reported time jumps forward anyway, that read call is the cause.                   |
//|  5-second gaps between probes give enough separation at GlobalVariableTime()'s            |
//|  1-second resolution to see clearly which call (if any) moves it.                          |
//|                                                                                               |
//|  Drag onto any chart once, read the Experts/Journal log for the verdict,                      |
//|  done - this is not meant to be left running.                                                  |
//+------------------------------------------------------------------+
#property copyright "Diagnostic - test-project"
#property version   "1.00"
#property script_show_inputs

input string InpVarName = "GVSTALE_PROBE_DELETE_ME";

void OnStart()
  {
   string nm = InpVarName;
   if(GlobalVariableCheck(nm)) GlobalVariableDel(nm);   // clean slate, in case a prior run didn't clean up

   Print("================================================================");
   Print("GlobalVariable staleness probe starting. Local time now: ", TimeToString(TimeLocal(), TIME_DATE|TIME_SECONDS));
   Print("================================================================");

   //--- baseline: Set() legitimately stamps "now" - expected, not the question
   GlobalVariableSet(nm, 1.0);
   datetime t1 = GlobalVariableTime(nm);
   Print("[1] after GlobalVariableSet():            GlobalVariableTime() = ", TimeToString(t1, TIME_SECONDS),
         "  (this one SHOULD be ~now - that's documented and expected)");

   Print("Sleeping 5s, touching nothing...");
   Sleep(5000);
   datetime t2 = GlobalVariableTime(nm);
   Print("[2] 5s later, before any Check()/Get():   GlobalVariableTime() = ", TimeToString(t2, TIME_SECONDS),
         "  delta vs [1] = ", (long)(t2 - t1), "s  (expect 0 - nothing has touched it)");

   //--- the actual test #1: does Check() alone bump the time?
   bool exists = GlobalVariableCheck(nm);
   datetime t3 = GlobalVariableTime(nm);
   Print("[3] immediately after ONE GlobalVariableCheck() call (exists=", exists, "): GlobalVariableTime() = ",
         TimeToString(t3, TIME_SECONDS), "  delta vs [2] = ", (long)(t3 - t2), "s");

   Print("Sleeping 5s again, touching nothing...");
   Sleep(5000);
   datetime t4 = GlobalVariableTime(nm);
   Print("[4] 5s later, before any further call:    GlobalVariableTime() = ", TimeToString(t4, TIME_SECONDS),
         "  delta vs [3] = ", (long)(t4 - t3), "s  (expect 0 if Check() in step 3 did NOT bump it)");

   //--- the actual test #2: does Get() alone bump the time?
   double val = GlobalVariableGet(nm);
   datetime t5 = GlobalVariableTime(nm);
   Print("[5] immediately after ONE GlobalVariableGet() call (val=", val, "): GlobalVariableTime() = ",
         TimeToString(t5, TIME_SECONDS), "  delta vs [4] = ", (long)(t5 - t4), "s");

   Print("================================================================");
   bool checkRefreshes = ((long)(t3 - t2) > 0);
   bool getRefreshes    = ((long)(t5 - t4) > 0);
   if(checkRefreshes || getRefreshes)
     {
      Print("VERDICT: CONFIRMED BUG. GlobalVariableCheck() refreshes time = ", checkRefreshes,
            " ; GlobalVariableGet() refreshes time = ", getRefreshes);
      Print("  -> Every InpUseAureliusFilter/InpUseMeridianFilter staleness check in this project");
      Print("     is silently defeated: the read call that's supposed to check staleness resets");
      Print("     the very clock it's checking. A crashed/removed writer EA's position would then");
      Print("     block the sibling EA against that side INDEFINITELY, not for InpXStaleSecs.");
      Print("     This needs a real fix: a SEPARATE timestamp the writer updates (e.g. a second");
      Print("     '<name>_LASTWRITE' global variable set only by Set(), never touched by a reader),");
      Print("     with readers comparing against THAT instead of GlobalVariableTime().");
     }
   else
     {
      Print("VERDICT: NOT a bug. Neither GlobalVariableCheck() nor GlobalVariableGet() refreshes");
      Print("  GlobalVariableTime(). The existing InpUseAureliusFilter/InpUseMeridianFilter staleness");
      Print("  checks work as designed - this was a false alarm from the audits, now ruled out.");
     }
   Print("================================================================");

   GlobalVariableDel(nm);   // leave no trace on the real account
   Print("Test global variable deleted. Done.");
  }
//+------------------------------------------------------------------+
