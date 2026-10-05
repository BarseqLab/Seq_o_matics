"""Turn traces into comparable channels, run behaviour checks, and write a report.

Channels are compared per device, because the two program versions use threads
differently and a single global interleaving of events is not stable.
Run-specific paths and timestamps are normalised before comparing.
"""

import difflib
import io
import json
import os
import re

import pandas as pd

TS = re.compile(r"\d{4}-\d\d-\d\d[ T]\d\d:\d\d(:\d\d(\.\d+)?)?([+-]\d\d:\d\d)?")
QUERY_CMDS = {"E"}
RUN = re.compile(r"runs/[^/]+__[^/]+/")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _norm_factory(d):
    meta = d.get("meta", {})
    subs = []
    for key, tag in (("exp", "<EXP>"), ("maxdrive", "<MAXDRIVE>"), ("tree", "<TREE>")):
        p = meta.get(key)
        if p:
            subs += [(p, tag), (p.replace("\\", "/"), tag), (p[3:], tag + "[3:]"), (p[3:].replace("\\", "/"), tag + "[3:]")]
    subs.sort(key=lambda s: -len(s[0]))

    def norm(s):
        s = str(s)
        for a, b in subs:
            s = s.replace(a, b)
        s = TS.sub("<T>", s)
        s = RUN.sub("runs/<RUN>/", s.replace("\\", "/"))
        return s
    return norm


def channels(d):
    norm = _norm_factory(d)
    ev = d["events"]
    ch = {}
    ch["status"] = [f"status={d.get('status')}  detail={d.get('detail')}"]
    ch["exceptions"] = [f"{e.get('where')}: {e.get('error') or (e.get('traceback') or '').strip().splitlines()[-1:]}"
                        for e in ev if e["kind"] == "exception"]
    ch["messageboxes"] = [f"{e['box']}: {e.get('title')} / {e.get('message')}" for e in ev if e["kind"] == "messagebox"]
    ch["driver steps"] = [e["step"] for e in ev if e["kind"] == "driver"]
    ch["pump commands"] = [f"{e['cmd']:<10} {e.get('meaning') or ''}" for e in ev
                           if e["kind"] == "pump" and e["cmd"] not in QUERY_CMDS]
    ch["pump dispenses"] = [f"{e['duration_s']:>8.1f} s at {e['rate_ml_min']:.3f} mL/min = {e['volume_ml']:.3f} mL"
                            for e in ev if e["kind"] == "pump_dispense"]
    for dev in ("selector1", "selector2"):
        ch[f"{dev} moves"] = [str(e["position"]) for e in ev if e["kind"] == "selector" and e["dev"] == dev]
    ch["serial ports"] = [f"{e['kind']} {e['port']} {e.get('reason', '')}".strip() for e in ev
                          if e["kind"] in ("serial_open", "serial_close", "serial_close_by_gc", "serial_open_failed")]
    # heater stages run in parallel threads, so DAQ activity is compared per channel
    daq = {}
    for e in ev:
        if e["kind"] in ("daq_add_channel", "daq_write", "daq_error"):
            what = {"daq_add_channel": "open", "daq_write": f"write {e.get('value')}",
                    "daq_error": f"ERROR {e.get('reason')}"}[e["kind"]]
            daq.setdefault(e.get("channel", "?"), []).append(what)
        elif e["kind"] == "daq_task_gc_not_closed":
            daq.setdefault("(tasks)", []).append("task discarded without close")
    ch["DAQ (per channel)"] = [f"{c}: {' | '.join(v)}" for c, v in sorted(daq.items())]
    ch["microscope (Core) calls"] = []
    for e in ev:
        if e["kind"] == "core":
            c = e["call"]
            if c == "set_xy_position":
                ch["microscope (Core) calls"].append(f"set_xy_position {e['x']} {e['y']}")
            elif c == "set_position":
                ch["microscope (Core) calls"].append(f"set_position {e['dev']} {e['value']}")
            else:
                ch["microscope (Core) calls"].append(f"{c} {e.get('dev', '')} {e.get('args', '')}".strip())
        elif e["kind"] == "core_unexpected_call":
            ch["microscope (Core) calls"].append(f"UNEXPECTED {e['call']}")
    ch["acquisitions"] = [f"{norm(e['directory'])}/{e['dataset']}: {e['n_events']} frames, channels={e['channels']}, "
                          f"z {e['z_first']}..{e['z_last']}, exposures={e['exposures']}"
                          for e in ev if e["kind"] == "acquisition"]
    ch["external commands"] = [f"{e['via']}: {norm(e['cmd'])}" for e in ev if e["kind"] == "command"]
    f = d.get("final", {})
    ch["files: experiment folder"] = sorted(_collapse(norm(k)) for k in f.get("files_exp", {}))
    ch["files: experiment folder"] = sorted(set(ch["files: experiment folder"]))
    ch["files: max-projection drive"] = sorted(norm(k) for k in f.get("files_maxdrive", {}))
    ch["files: written into program folder"] = list(f.get("files_in_program_folder", []))
    ch["end state: open ports / reserved DAQ"] = [f"open ports: {f.get('open_ports')}",
                                                  f"reserved DAQ: {f.get('reserved_daq')}"]
    ch["end state: program threads still running"] = [f"{t['name']}: {(t['stack'] or [''])[-1].strip()}"
                                                      for t in f.get("threads", [])]
    log = f.get("exp_text_files", {}).get("log.txt", "")
    # thread pools finish positions in varying order, so text channels are compared as sorted lines
    ch["log.txt (sorted lines)"] = sorted(norm(l) for l in log.splitlines() if l.strip())
    gui_lines = []
    for k, v in sorted(f.get("gui_text", {}).items()):
        for l in v.splitlines():
            if l.strip():
                gui_lines.append(norm(l))
    ch["GUI panel text (sorted lines)"] = sorted(gui_lines)
    ch["pump calibration file"] = [f.get("pump_speed_calibration_bytes", "")]
    return ch


def _collapse(path):
    # one entry per NDTiff dataset folder instead of each file
    m = re.match(r"(.*/[^/]+_\d+)/(NDTiff\.index|[^/]+_NDTiffStack\.tif)$", path)
    return (m.group(1) + "/ [NDTiff dataset]") if m else path


def focus_results(d):
    """Compare the plane each focus run chose with the true best plane of the fake sample."""
    f = d.get("final", {})
    texts = f.get("exp_text_files", {})
    acq = [e for e in d["events"] if e["kind"] == "acquisition" and e.get("true_best_piezo") is not None]
    rows = []
    for e in acq:
        cyc = os.path.basename(e["directory"].replace("\\", "/"))[len("focus"):]
        t = texts.get(f"offset{cyc}.csv")
        if not t:
            rows.append((cyc, e["name"], e["true_best_piezo"], None, "no offset file"))
            continue
        df = pd.read_csv(io.StringIO(t))
        r = df[df["position"] == e["name"]]
        if r.empty:
            rows.append((cyc, e["name"], e["true_best_piezo"], None, "position missing"))
            continue
        r = r.iloc[0]
        # save_offset_and_json: z_shift = (piezo - best)/1.5, so best = piezo - 1.5*z_shift
        chosen = float(r["piezo"]) - 1.5 * float(r["z_shift"])
        rows.append((cyc, e["name"], e["true_best_piezo"], round(chosen, 3), ""))
    return rows


def checks(d, scenario):
    from dryrun.scenarios import SCENARIOS
    sc = SCENARIOS[scenario]
    ev = d["events"]
    f = d.get("final", {})
    steps = [e["step"] for e in ev if e["kind"] == "driver"]
    out = []

    def add(name, ok, detail=""):
        out.append((name, "PASS" if ok else "FAIL", detail))

    add("run did not hang", d.get("status") != "hang", d.get("detail") or "")
    add("no uncaught exceptions", not any(e["kind"] == "exception" for e in ev),
        "; ".join(sorted({str(e.get("error") or e.get("where")) for e in ev if e["kind"] == "exception"}))[:300])
    if sc["steps"] == "auto":
        add("automated run reached 'All rounds finished'", "reached: All rounds finished" in steps)
    if sc["steps"] == "prime_wash":
        add("Prime finished (PBST flush done)", "reached: Prime done" in steps)
        add("Wash finished", "reached: Wash done" in steps)
    if sc["steps"] in ("cancel_restart", "prime_cancel"):
        t_cancel = next((e["t"] for e in ev if e["kind"] == "driver" and e["step"] == "press Cancel"), None)
        t_restart = next((e["t"] for e in ev if e["kind"] == "driver" and " again" in e["step"]), None)
        if t_cancel is not None:
            disp = [e for e in ev if e["kind"] == "pump_dispense" and e["t"] <= t_cancel]
            stops = [e for e in ev if e["kind"] == "pump" and e["cmd"] == "I" and e["t"] >= t_cancel]
            running = bool(disp) and disp[-1]["t"] + disp[-1]["duration_s"] > t_cancel
            add("pump stops when Cancel is pressed",
                not running or (bool(stops) and stops[0]["t"] < disp[-1]["t"] + disp[-1]["duration_s"]),
                f"pump was mid-dispense; no stop sent" if running and not stops else "")
            later = [e for e in ev if e["kind"] == "pump_dispense" and t_cancel < e["t"] < (t_restart or 1e18)]
            add("no further pumping after Cancel (until restarted)", not later,
                "; ".join(f"{e['volume_ml']} mL at t={e['t']:.0f}" for e in later)[:200])
        after = d.get("after_cancel", {})
        add("after Cancel, serial ports released", not after.get("open_ports"), str(after.get("open_ports")))
        add("after Cancel, DAQ channels released", not after.get("reserved_daq"), str(after.get("reserved_daq")))
        if t_restart is not None:
            again = [e for e in ev if e["kind"] == "pump_dispense" and e["t"] > t_restart]
            errs = [e.get("error") for e in ev if e["kind"] == "exception" and e["t"] > t_restart]
            add("pressing Start/Prime again after Cancel runs again", bool(again) and not errs,
                "; ".join(map(str, errs))[:200])
        if sc["steps"] == "prime_cancel":
            add("Prime run after the restart finished (PBST flush done)", "reached: Prime done" in steps)
    restarted = sc["steps"] == "cancel_restart" and sc.get("restart", True)
    if sc["steps"] == "cancel_restart" and not restarted:
        add("no program threads left waiting after Cancel", not f.get("threads"),
            "; ".join(f"{t['name']}: {(t['stack'] or [''])[-1].strip()[:120]}" for t in f.get("threads", [])))
    if not restarted:  # with a restart, the new run is still going when the scenario ends
        add("all serial ports closed at the end", not f.get("open_ports"), str(f.get("open_ports")))
        add("all DAQ channels released at the end", not f.get("reserved_daq"), str(f.get("reserved_daq")))
    cmds = [e["cmd"] for e in ev if e["kind"] == "command"]
    server = any(c.startswith(("ssh", "scp")) for c in cmds)
    aws = any(c.startswith("aws s3 cp") for c in cmds)
    if sc["steps"] == "auto" and "reached: All rounds finished" in steps:
        add("server upload only if 'Send to storage server' is ticked", server == bool(sc["server"]),
            f"ticked={bool(sc['server'])}, uploaded={server}")
        add("AWS upload only if 'upload to AWS' is ticked", aws == bool(sc["aws"]),
            f"ticked={bool(sc['aws'])}, uploaded={aws}")
    files = f.get("files_exp", {})
    cycles = sorted({os.path.basename(e["directory"].replace("\\", "/"))[len("focus"):] for e in ev
                     if e["kind"] == "acquisition" and e.get("true_best_piezo") is not None})
    for cyc in cycles:
        n = sum(1 for k in files if k.startswith(f"dicfocus{cyc}/") and k.endswith(".tif"))
        add(f"dicfocus{cyc}/ holds the 4 best-focus images", n == 4, f"{n} files")
    stray = f.get("files_in_program_folder", [])
    add("no image files written into the program folder", not [s for s in stray if s.endswith(".tif")], str(stray))
    fr = focus_results(d)
    if fr:
        bad = [r for r in fr if r[3] is None or abs(r[3] - r[2]) > 0.76]
        add("focus picks the sharpest plane (within half a step)", not bad,
            "; ".join(f"{c}/{p}: true {t} chose {ch}" for c, p, t, ch, _ in bad)[:300])
    return out


def _diff(a, b, n=30):
    lines = list(difflib.unified_diff(a, b, "reference", "candidate", lineterm="", n=1))
    if len(lines) > n:
        lines = lines[:n] + [f"... ({len(lines) - n} more diff lines)"]
    return lines


def build_report(infos, trees, scenarios, ref="ref"):
    from dryrun.scenarios import SCENARIOS
    by = {(i["tree"], i["scenario"]): i for i in infos}
    out = ["# Dry-run report", "",
           "Generated by `python -m dryrun.run`. Every hardware boundary was faked; see `dryrun/README.md`.", ""]
    for sc in scenarios:
        out += [f"## Scenario `{sc}`", "", SCENARIOS[sc]["description"], ""]
        data = {}
        for t in trees:
            i = by.get((t, sc))
            if i and i.get("trace"):
                data[t] = load(i["trace"])
        # summary table
        out += ["| Tree | Status | Virtual duration | Real seconds |", "|---|---|---|---|"]
        for t in trees:
            i = by.get((t, sc), {})
            d = data.get(t)
            if d is None:
                out.append(f"| {t} | no trace (rc={i.get('returncode')}) | | {i.get('real_seconds')} |")
            else:
                out.append(f"| {t} | {d.get('status')} | {d.get('virtual_end', 0) / 3600:.2f} h | {i.get('real_seconds')} |")
        out.append("")
        # checks
        out += ["### Behaviour checks", "", "| Check | " + " | ".join(trees) + " |",
                "|---|" + "---|" * len(trees)]
        res = {t: {c[0]: c for c in checks(d, sc)} for t, d in data.items()}
        names = []
        for t in trees:
            for c in res.get(t, {}):
                if c not in names:
                    names.append(c)
        for nme in names:
            cells = []
            for t in trees:
                c = res.get(t, {}).get(nme)
                cells.append("—" if c is None else (c[1] + (f" ({c[2]})" if c[1] == "FAIL" and c[2] else "")))
            out.append(f"| {nme} | " + " | ".join(cells) + " |")
        out.append("")
        # channel comparison
        if ref in data:
            cref = channels(data[ref])
            for t in trees:
                if t == ref or t not in data:
                    continue
                ct = channels(data[t])
                out += [f"### `{t}` compared with `{ref}`", "", "| Channel | Result |", "|---|---|"]
                diffs = []
                for k in cref:
                    same = cref[k] == ct.get(k, [])
                    out.append(f"| {k} | {'same' if same else '**different**'} |")
                    if not same:
                        diffs.append(k)
                out.append("")
                for k in diffs:
                    out += [f"<details><summary>{k}: {len(cref[k])} vs {len(ct.get(k, []))} entries</summary>", "",
                            "```diff"] + _diff(cref[k], ct.get(k, [])) + ["```", "</details>", ""]
        # focus table
        for t, d in data.items():
            fr = focus_results(d)
            if fr:
                out += [f"<details><summary>Focus results `{t}` (true best plane vs chosen plane, piezo um)</summary>",
                        "", "| Cycle | Position | True best | Chosen |", "|---|---|---|---|"]
                out += [f"| {c} | {p} | {tb} | {ch} {note} |" for c, p, tb, ch, note in fr]
                out += ["</details>", ""]
        # hang stacks
        for t, d in data.items():
            if d.get("status") == "hang":
                out += [f"<details><summary>`{t}` hang: where program threads were waiting</summary>", "", "```"]
                for th in d.get("final", {}).get("threads", []):
                    out.append(f"--- {th['name']}")
                    out += [s.rstrip() for s in th["stack"]]
                out += ["```", "</details>", ""]
    return "\n".join(out) + "\n"
