# Fixes from the code reviews of `feature/configurable-aws-bucket`

**Started:** 2026-10-15. **Last updated:** 2026-10-16.

## Current status (2026-10-16)
- **Implemented, uncommitted:** item 3, items 6-8, D2, R1, R2, R3, R5, R7 (= items 4, 5), R8, the "untick" hint,
  and B1/B2 (gray-out + "Checking connections..." window). **51/51 storage tests pass**: `py -m unittest dryrun.tests.test_storage_settings dryrun.tests.test_storage_callsites`.
  The full `dryrun/tests` run gives 54 tests with 3 errors, all from numpy/pytz missing on the dev PC
  (`test_fakes`, `test_zstack`, `test_protocol_lookup`), unrelated to this work.
- **Decided:** D1 keep blocking; D2 manual mode runs no connection checks.
- **Deferred by the user:** item 1 / R6 (the GUI stays live during the check), item 2 (overall deadline).
- **Open:** nothing from the reviews. B6 skipped for now.
  B3 and B4: not an issue (user).
- **Equivalence with main:** with the shipped `storage.json`, the `aws s3 cp`, `scp` and `ssh` commands are
  byte-identical to `origin/main` (re-verified after the latest edits by the informed reviewer with
  `figs/review_scratch/compare_commands.py`).
- **Dev PC check:** `aws sts get-caller-identity` (IAM user `data_upload`), `aws s3api head-bucket --bucket
  barseq-acquisition` and the program's own `connection_check.check_aws` pass (1.5 s). Not verified: whether Elm
  uses the same credentials.

## Decisions
- **D1. A failed connection check blocks Create** (decided 2026-10-16). Reason: the way out is to untick the box;
  a ticked AWS box that cannot actually upload would be confusing. The block dialog now says which box to untick.
  Reviewers' counterpoints, recorded: `head-bucket` needs `s3:ListBucket` and `sts` needs the STS endpoint, which
  `aws s3 cp` does not (passes for `data_upload` on the dev PC); the server check has the same question; blocking
  may push operators to untick uploads.
- **D2. Manual mode runs no connection checks** (done). `create_exp_manual` calls
  `_storage_ok(check_connections=False)`: storage.json is still loaded and validated, and a bad file blocks.
  Reason: manual mode never uploads images; the boxes are shared with the auto tab; only the note goes by `scp`,
  from its own button, whatever the boxes say.

## Items from review 1 (2026-10-15)
1. **[DEFERRED by user]** GUI live during the check / double Create. See R6.
2. **[DEFERRED by user: record, do not fix now]** No overall deadline on the wait loop. `subprocess` timeouts do
   not fire if a helper process keeps the pipes open (ssh ProxyCommand, AWS credential_process/SSO helper; none
   known on Elm). Planned fix: stop waiting after 90 s and count it as a failure; abandon the process.
3. **[DONE]** A crashed check or missing results counted as a pass. `run_checks` turns an exception into a failed
   `CheckResult` ("crashed: ..."); a result count different from the checks requested is a failure.
4. **[DONE as R7]** `stdin=subprocess.DEVNULL` in `run_command`.
5. **[DONE as R7]** `encoding="utf-8", errors="replace"` in `run_command`.
6. **[DONE]** `storage.json` read with `encoding="utf-8-sig"` (a Notepad BOM is accepted).
7. **[DONE, extended by R2]** A bad file at startup is reported in the warning panel and the console. At each
   Create, the read-only bucket/folder fields show the loaded file, and the user/host fields are refreshed (R2).
8. **[DONE, final rules after R1/R8]** in `storage_settings.py`:
   bucket `[A-Za-z0-9][A-Za-z0-9._-]*`; storage class one of the 8 in `STORAGE_CLASSES`; user
   `[A-Za-z0-9._][A-Za-z0-9._-]*`; host `[A-Za-z0-9.][A-Za-z0-9.-]*` (no `@`, `:port`, IPv6, leading `-`);
   `server_root` `/(name/)*` (starts and ends with `/`, no spaces, quotes, `;` or `//`); prefix empty or names
   joined by single `/` (trailing `/` allowed); retries 1-10. Values typed in the GUI are not validated.

## Items from review 2 (2026-10-16)
- **R1 [DONE]** Storage-class typo passed until the end-of-run upload. Now an allowlist of the 8 values
  `aws s3 cp --storage-class` lists.
- **R2 [DONE]** User/host went stale when storage.json was edited with the GUI open. `app.storage_shown`
  remembers the settings the fields were last filled from; a field that is empty or still shows that value follows
  the file, a typed value is kept. Known consequences: typing exactly the old value cannot be told from an
  untouched field; typing only the host leaves the user following the file.
- **R3 [DONE]** Manual Create sets `self.app.server` before validation (as main) and again after `_storage_ok`
  (the second line is needed when the fields were refreshed; guarded by `test_manual_uses_the_refreshed_fields`,
  mutation-checked).
- **R4 [DONE via B1]** The GUI is live during the check, so the boxes or user@host can change between check and use.
  Planned fix if wanted: `_storage_ok` returns the values it checked and `create_exp_auto` uses them.
- **R5 [DONE]** `self.app.storage` is assigned only when `_storage_ok` succeeds. A later failure in
  `create_exp_*` (e.g. Micro-Manager not running) still replaces it, as it replaces `pos_path` and `server` on
  main. Known cosmetic effect: after a failed check, the read-only fields already show the new file while an
  earlier experiment still uses the old settings; clears at the next successful Create.
- **R6 [DONE via B2 + modal window, 2026-10-16]** During the wait every button is live (Create on both tabs, Start, Prime, Wash, Fill).
  Worst case: Start/Prime on an earlier experiment, then Create replaces `self.app.fluidics` under the running
  thread. Low likelihood, high impact; did not exist on main. Create itself opens a new Micro-Manager client and
  reads config files only (FluidicSystem opens no serial ports; `move_to_image` is a no-op). Also (same as main)
  `all_autobtn_disable` never disables the manual Create button. Planned fix: disable the action buttons and add a
  reentry flag around the wait (~10 lines).
- **R7 [DONE]** `run_command`: no console input, lenient UTF-8 decoding. Both reproduced first (a child reading
  stdin hung to the timeout; undecodable output raised UnicodeDecodeError, which blocked Create). Note: the stdin
  test only proves the fix when run from a console; with stdin already NUL/closed it passes either way.
- **R8 [DONE]** User, host and bucket may not start with `-` (scp/ssh would read it as an option).
- **Hint [DONE]** The block dialog ends "To create the experiment without this upload, untick ...", naming only the
  box(es) whose check failed (all ticked boxes for a crashed or incomplete test).
- Out of scope, recorded: checks run only at Create (temporary credentials could expire before the end-of-run
  upload; `data_upload` is a long-term IAM user); the note `scp` has no BatchMode and can hang on a password
  prompt (same as main); a lab without AWS still needs a placeholder bucket in storage.json; manual Create during
  an auto run replaces `self.app.storage` without checks (same class of hazard as the shared `pos_path`/`server`).

## Review 3a: blind reviewer (no plan or history given), 2026-10-16
No blocking bug; shipped config matches main. Findings:
- **B1 = R4, B2 = R6** (rediscovered independently and reproduced; recommends fixing both before merging).
  **[DONE 2026-10-16, user's design]** When a check runs (auto Create with a box ticked), `_begin_busy` grays out
  Create on both tabs, both tabs' "upload to AWS" and server boxes, and both tabs' user/host fields (remembering
  each widget's state), and opens a small "Please wait" window "Checking connections..." that the user cannot
  close. On a failed check `_end_busy` restores the widgets and closes the window *before* the error dialog, so the
  box can be unticked. On success the text changes to "Creating experiment..." and `create_exp_auto` (now a
  try/finally wrapper around `_create_exp_auto`) calls `_end_busy` when Create finishes, however it ends.
  User decisions 2026-10-16: the window is **modal** (`grab_set`: nothing else in the program can be clicked,
  Start/Prime/Wash/Fill included, which closes R6; if the window is not viewable, e.g. hidden by the dry-run
  harness, the grab is skipped and it stays non-modal), and it stays up through "Creating experiment..." until
  Create finishes. Manual Create runs no check (D2), so it shows no window.
  Tests: fake-widget tests in `TestExperimentCreationBlock`/`TestCreateExperiment`, and `TestBusyWindowRealTk`
  with real Tk widgets and event loop (a second Create click during the check does nothing; the grab is on the
  window during the check and released after). All three
  mutation-checked (fail when the gray-out is removed).
- **B3 [NOT AN ISSUE, user 2026-10-16]** Reason: a run must first create its experiment folder directly under `server_root`, so `server_root` has to be writable anyway; the probe tests exactly that. Original finding: The server check probes a different folder from the one the upload writes. The probe
  requires `server_root` itself to be writable; the upload runs `mkdir -p <server_root><experiment>_maxprojection`,
  which needs write access only at the first missing level. If `server_root` is root-owned but has writable
  subfolders, Create is blocked although main would upload; the reverse also exists. A restricted login shell
  (scponly/rssh) would fail the probe. Options: probe the deepest existing ancestor of the real target; or check
  login + `test -d` only. Traced, not tested against the real server.
- **B4 [NOT AN ISSUE, user 2026-10-16; = D1 counterpoint]** (AWS check needs more permissions than the upload).
- **B5 [DONE: comment corrected]** see R5 note.
- **B6 [SKIPPED for now, user 2026-10-16]** Validation still accepts `server_root` "/" or "/../", host "...", uppercase/underscore
  buckets (invalid for new S3 buckets), prefix "../x". No shell injection possible.

## Review 3b: informed verifier (full plan and decisions given), 2026-10-16
Verdict: ready to commit after two follow-ups, both now done: (1) a test guarding the second `self.app.server`
line in manual Create (`test_manual_uses_the_refreshed_fields`, shares Tk-like variables, mutation-checked);
(2) this plan file brought up to date. Also done: the hint names only the failed box
(`test_block_hint_names_only_the_failed_upload`); a broken line continuation in the test file fixed.
Verified: R1, R2, R3, R5, R7, R8, item 3, items 6-7, D2, hint; equivalence with main; Python >= 3.9 declared, no
compatibility issue. Mutation results: every fix is caught by a test except `stdin=DEVNULL` (environment-dependent,
see R7). `TestCreateExperiment` stubs scope, fluidics, pandas and Tk and stops manual Create at `write_log`, so it
tests ordering and state, not hardware.

## Remaining test gaps
- A permanent main-vs-branch command regression test (base: `figs/review_scratch/compare_commands.py`).
- A static check that every `self.app.X` used by the panels is set in `Widgets.__init__`.

## Checks on Elm that need no GUI run (a few minutes, as the GUI's user)
```
aws sts get-caller-identity
aws s3api head-bucket --bucket barseq-acquisition
ssh -o BatchMode=yes imagestorage@10.128.30.152 "test -d /mnt/imagestorage/ && test -w /mnt/imagestorage/"
```
The first should show `user/data_upload`. The third must pass: runs create the experiment folder directly under `server_root`. Also open the GUI once to
look at the layout, and check: manual Create with a box ticked runs no checks; editing `storage.json` and
clicking Create updates the fields; a failed check names the box to untick.

## Housekeeping
- `figs/` is untracked and not gitignored; it holds the reviewers' scratch (`review_scratch`,
  `plan_review_scratch`, `blind_review_scratch`, `informed_review_scratch`). Do not commit it.
- `plans/storage_settings_STATUS.md` (committed 2026-10-13) does not yet mention this work; update it at commit.
