# Session Notes — Ichimoku / Aurelius GOLD Research

Running log, committed after every meaningful step. Purpose: this container
is disposable and gets reclaimed on inactivity; `git push` to GitHub has been
returning 403 all session (Claude GitHub App not authorized on this org/repo
— needs an org admin to install/reconnect it, see error text from `git push`).
Until that's fixed, a **local commit** is the only thing that survives a
container reclaim — so every commit here is is made immediately, not batched,
even though it can't reach GitHub yet.

## Status as of 2026-09-19

**What survived:** `Ichimoku_EA.mq5` v1.04, recovered from the user's own
saved copy (re-uploaded) and committed to this repo (commit `3cf9462`,
not yet pushed — see 403 above). Full changelog v1.00–v1.04 is in the file's
own header comment — that is the authoritative record of what was tested,
what shipped, and why.

**What was lost (container reclaim before anything was pushed):**
- All Python research scripts (`plain_confluence_search.py`,
  `adx_hold_longer.py`, every filter-test script, the Aurelius
  `engine.py`, the MACD-on-Aurelius test, etc.)
- The underlying real GOLD H4/M5 price history the tests ran on.
- All MT5 `.xlsx` report extractions.
- The `sr_rejection.py` result that was mid-flight when the container cycled
  — never read, no longer exists.

**Root cause:** nothing above was ever committed to git (data files
wouldn't belong in git anyway) or saved outside the container, and the one
thing that *should* have gone to GitHub (code) couldn't, because of the
push 403. A container reclaim is normal/expected behavior for this
environment — the actual failure was relying on ephemeral disk as the only
copy of anything.

**Going forward — the fix:**
1. Every finding, config, or result worth keeping gets written into this
   file (or a versioned code file) and **committed immediately**, not at
   the end of a task.
2. `git push` is retried every turn per standing instruction; the moment
   the 403 clears, everything committed so far lands on GitHub in one go.
3. Real market data (H4/M5 GOLD price history) still needs to be re-sourced
   — waiting on the user for where the original CSVs came from (MT5 export,
   saved local copy, or a fetchable API) before any new Python testing can
   start. Nothing will be fabricated/synthesized to fill that gap.
4. Large research scripts should be written to this repo (or committed
   subdirectories), not left only in the scratchpad, even in draft form.

## Pending / next steps
- [ ] User to confirm source of original H4/M5 GOLD price data so real
      testing can resume (MT5 export vs. saved CSVs vs. re-fetchable API).
- [ ] Once data is back: rebuild Aurelius engine, re-run S&R touch-and-reject
      test on Aurelius's real M5 gate (the pending "test it on aurelius
      aswell" request).
- [ ] Resolve GitHub push 403 (org admin action, outside this session).
- [ ] Confirm whether the live/demo forward-test of `Ichimoku_EA.mq5` v1.04
      has actually been launched.
