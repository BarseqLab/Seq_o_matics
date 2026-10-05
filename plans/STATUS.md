# Reference-parity work: status and handoff

**Last updated:** 2026-10-05

Read this first when picking the work up in a new session. The plan itself is `plans/reference_parity_plan.md`.

## Where everything is

| What | Where |
|---|---|
| Repo (private) | `BarseqLab/Seq_o_matic_dev`, branch `reference-parity`. `origin` = this repo; `upstream` = public `BarseqLab/Seq_o_matics`. Never push work-in-progress upstream. |
| Local clone / worktree | `C:\Users\SVC_barseq\Seq_o_matics_github\` / `…\.claude\worktrees\reference-parity\` |
| Elm reference (the spec, read-only) | `C:\Users\SVC_barseq\Seq_o_matics_2.5\`. Elm runs on this today. **Never write to it.** It holds a plaintext AWS password in `front_end/Widgets.py:319`: never copy it anywhere, and it should be rotated. |
| Python env | `C:\Users\SVC_barseq\.conda\envs\seq_o_matic\python.exe` |
| Inventory of differences, with decisions | `docs/parity_inventory.md`, plus per-area evidence in `docs/parity_inventory/` |
| Hard-coded per-microscope values | `docs/hardcoded_values.md` (for a separate session) |
| Dry-run harness | `dryrun/` (how to run: `dryrun/README.md`); scratch output in `C:\Users\SVC_barseq\Seq_o_matics_dryrun\` |
| Checkpoint-2 results (harness on the unchanged branch) | `docs/dryrun_results/checkpoint2_summary.md` |

## Steps

| Step | State |
|---|---|
| 1. Behaviour inventory | **Done.** Reviewed and decided with the user (see "Review decisions" in `docs/parity_inventory.md`). |
| 2. Dry-run harness | **Done.** Checkpoint 2 passed: it caught the known regressions on the unchanged branch. |
| 3. Fix loop | **Code fixes done** (commits below). Remaining: final full dry run, the checkpoint-3 summary, and updating the inventory's status column. |
| 4. Micro-Manager demo run, then Elm water test | **Not started.** |

## Step 3: what was changed (one commit per item, on `reference-parity`)

| Commit | Items |
|---|---|
| `3393477` | P04/P05/P21: all Elm config and data files byte-identical to the reference |
| `77596d4` | P01: fluidics completion events |
| `17e163e` | P02/Q1/D21 (+D03): Cancel sets the event, skips the PBST flush, stops the pump and releases pump/selector/relay/heater (approved deviation) |
| `446773c` | P03/P06/P07/P16/Q3: focus image path, ±30 sweep, pass-2 plane selection, stop_stage_sequence, 4 workers, piezo park at 200 (approved) |
| `e4e112b` | P10/P11/P12/P19/Q5: uploads per checkboxes, AWS upload ported with a missing-folder guard, default server, protocol-load catch |
| `c7b3d3f` | P13: pump 1.5 mL/min on connect |
| `3aaf605` | P08/P09: heater error handler order |
| `7865564` | P14: live-view condition |
| `618593f` | P17/Q2: max-projection cancel stop; tiling and max-projection waits honour Cancel (approved) |
| `9587a2b` | P18: protocol lookup order, plus unit test |
| `e1e1f0f` | P20: note-upload except |
| `22e3c3e` | P15: tissue-scanner stitching as in the reference (keeps `imwrite`, A2) |
| `f665043` | Q4: no duplicate lines in `log.txt`; extra panel messages kept; logger format fix |
| `3488ea6` | GA10/Q8: pump-speed field pre-fill, clean save, prompt when empty (approved) |
| `51fce95` | C02: relay routing calls and relay-group configuration restored |
| `cbd3473` | C04/C05/C06/C08/C09: small restores |
| harness commits | `d700519` and earlier: scenarios for cancel (pump/heat/focus/max-projection/prime), pump-speed field, heater fault, two-channel focus |

**Approved deviations from the reference** (everything else matches it):
- Cancel behaviour (Q1, D21, D03).
- Imaging waits honour Cancel (Q2).
- Piezo park at 200 µm (H3).
- Pump-speed field (GA10/Q8).
- AWS missing-folder guard (Q5).
- Extra GUI panel messages (Q4).
- Kept `main` fixes A1–A6:
  - heater-cancel `=`;
  - `imwrite`;
  - `FileNotFoundError` for unknown protocols;
  - recipe_builder `__init__`;
  - blank AWS password;
  - no `chdir`.

## Remaining work, in order

1. **Final full dry run** of `ref` vs `branch`, all scenarios:
   ```
   python -m dryrun.run --trees ref,branch --scenarios all --jobs 4 --fresh-trees --report docs/dryrun_results/checkpoint3_report.md
   ```
   Then write `docs/dryrun_results/checkpoint3_summary.md`, listing every remaining difference as one of:
   - approved deviation;
   - harness timing noise (heater temperature readings, thread order, the live-view race below);
   - shared bug (D).

   Push.
2. **Update `docs/parity_inventory.md`:** add the commit hash to each decided row. Record two new observations from the dry runs, both present in the reference too:
   - **D22:** the live-view thread can miss its `'end'` signal when the next step replaces `scope`, then loops until the program exits. Seen at 100× speed; unlikely in real time.
   - **D23:** after Cancel during focus with "Skip alignment", mock alignment raises `FileNotFoundError` for the missing `offset<cycle>.csv`, so the automation thread exits with a traceback.
3. **Ask the user** about the remaining D items, especially:
   - **D02:** a failed heat step leaves the run waiting forever. The `heater_fault` dry run shows it in both trees.
   - The `UnboundLocalError` (`name`) in the heater error handler, also in both trees.
4. **Step 4a, Micro-Manager demo:** run the branch with `C:\Program Files\Micro-Manager-2.0\MMConfig_demo.cfg`, the real pycromanager, and fluidics faked. This needs a small runner variant that does not install the pycromanager fake.
5. **Step 4b, Elm water test** (with the user, on the scope):
   - Prime / Wash, including Cancel during Prime.
   - A short automated run with water and no sample, including Cancel mid-pump and Start again.
   - Check that the pump actually stops on Cancel (`I` command).
   - Then a real run.
6. **Separate session:** hard-coded values (`docs/hardcoded_values.md`) and the packaging manifests (C12).
7. **Later:** merging back to upstream. See "Repositories" in `plans/reference_parity_plan.md`. Elm configs are in their own commit, `3393477`.

## Harness quick reference
- **Scenarios:**
  - `auto_full`, `imaging_only`, `imaging_uploads`, `imaging_two_channels`;
  - `prime_wash`, `prime_cancel`;
  - `cancel_restart`, `cancel_heat_restart`, `cancel_focus`, `cancel_maxproj`;
  - `heater_fault`, `pump_speed`.
- **Trees:** `ref`, `branch`, `main`, or any path to a `code` folder. For example, an archive of an older commit:
  ```
  git archive -o x.tar <rev> -- code ":(exclude)code/supplementary"
  ```
- **Rebuild a report without re-running:** add `--report-only`.
- **Unit tests:** `python -m unittest discover -s dryrun/tests -t .` (10 tests).
- **Scratch folder** grows by a few GB per full run; safe to delete.
