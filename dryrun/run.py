"""Prepare scratch copies of program trees, run scenarios, and compare the traces.

    python -m dryrun.run --trees ref,branch --scenarios imaging_only,prime_wash
    python -m dryrun.run --trees ref,branch,main --scenarios all --report docs/dryrun_results/report.md

Trees:
  ref     the Elm reference folder (copied, never modified)
  branch  this worktree's code/ folder
  main    upstream main (git archive of upstream/main:code)
  <path>  any other code folder

Only these test-only config changes are applied, identically to every tree:
  scope.json imwidth -> --imwidth (smaller synthetic images)
  scope.json maxproject_drive "D:\\" -> a scratch folder (any other drive is left as is)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.dirname(HERE)
REF_DIR = r"C:\Users\SVC_barseq\Seq_o_matics_2.5"
DEFAULT_SCRATCH = r"C:\Users\SVC_barseq\Seq_o_matics_dryrun"
PYTHON = sys.executable

IGNORE = shutil.ignore_patterns("supplementary", "__pycache__", ".ipynb_checkpoints", ".idea", "Saved Games",
                                "Searches", "*.ipynb", "aixintest.csv", "*.pyc")


def prepare_tree(name, scratch):
    dst = os.path.join(scratch, "trees", name)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    if name == "ref":
        shutil.copytree(REF_DIR, dst, ignore=IGNORE)
    elif name == "branch":
        shutil.copytree(os.path.join(WORKTREE, "code"), dst, ignore=IGNORE)
    elif name == "main":
        tmp = os.path.join(scratch, "trees", "_main_archive.tar")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        subprocess.run(["git", "-C", WORKTREE, "archive", "-o", tmp, "upstream/main", "--", "code",
                        ":(exclude)code/supplementary"], check=True)
        ex = os.path.join(scratch, "trees", "_main_extract")
        if os.path.exists(ex):
            shutil.rmtree(ex)
        with tarfile.open(tmp) as t:
            t.extractall(ex)
        shutil.copytree(os.path.join(ex, "code"), dst, ignore=IGNORE)
        shutil.rmtree(ex)
        os.remove(tmp)
    else:
        shutil.copytree(name, dst, ignore=IGNORE)
    return dst


def apply_test_config(tree, maxdrive, imwidth, extra=None):
    p = os.path.join(tree, "config_file", "scope.json")
    with open(p, encoding="utf-8") as f:
        cfg = json.load(f)
    orig = dict(cfg[0])
    cfg[0]["imwidth"] = imwidth
    cfg[0].update(extra or {})  # scenario-specific scope.json values, applied to every tree alike
    if cfg[0].get("maxproject_drive", "").upper() in ("D:\\", "D:/", "D:"):
        cfg[0]["maxproject_drive"] = maxdrive.rstrip("\\") + "\\"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)
    changed = {"imwidth": [orig.get("imwidth"), imwidth],
               "maxproject_drive": [orig.get("maxproject_drive"), cfg[0]["maxproject_drive"]]}
    for k, v in (extra or {}).items():
        changed[k] = [orig.get(k), v]
    return changed


def run_one(tree_name, scenario, scratch, args):
    from dryrun import scenarios
    run_dir = os.path.join(scratch, "runs", f"{tree_name}__{scenario}{args.run_suffix}")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir)
    tree = prepare_tree_cached(tree_name, scratch, run_dir)
    maxdrive = os.path.join(run_dir, "maxdrive")
    os.makedirs(maxdrive)
    overrides = apply_test_config(tree, maxdrive, args.imwidth, scenarios.SCENARIOS[scenario].get("config"))
    exp = os.path.join(run_dir, "exp")
    scenarios.setup_experiment(exp, scenario)
    os.makedirs(os.path.join(maxdrive, os.path.dirname(exp[3:])), exist_ok=True)
    out = os.path.join(run_dir, "trace.json")
    cmd = [PYTHON, "-m", "dryrun.runner", "--tree", tree, "--scenario", scenario, "--exp", exp,
           "--maxdrive", maxdrive, "--out", out, "--speed", str(args.speed), "--imwidth", str(args.imwidth)]
    if args.mm_config:
        cmd += ["--mm-config", args.mm_config]
    if args.stall:
        cmd += ["--stall", str(args.stall)]
    t0 = time.time()
    with open(os.path.join(run_dir, "console.log"), "w", encoding="utf-8", errors="replace") as log:
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONPATH=WORKTREE)
        try:
            p = subprocess.run(cmd, cwd=WORKTREE, stdout=log, stderr=subprocess.STDOUT, env=env,
                               timeout=args.real_timeout)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = "real-time timeout"
    info = {"tree": tree_name, "scenario": scenario, "returncode": rc, "real_seconds": round(time.time() - t0),
            "trace": out if os.path.exists(out) else None, "test_config": overrides, "run_dir": run_dir}
    with open(os.path.join(run_dir, "run_info.json"), "w") as f:
        json.dump(info, f, indent=1)
    print(f"[{tree_name} / {scenario}] rc={rc} in {info['real_seconds']} s", flush=True)
    return info


def prepare_tree_cached(tree_name, scratch, run_dir):
    base = os.path.join(scratch, "trees", tree_name)
    if not os.path.exists(base):
        prepare_tree(tree_name, scratch)
    dst = os.path.join(run_dir, "tree")
    shutil.copytree(base, dst)
    return dst


def main():
    from dryrun import scenarios, compare
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", default="ref,branch")
    ap.add_argument("--scenarios", default="imaging_only")
    ap.add_argument("--scratch", default=DEFAULT_SCRATCH)
    ap.add_argument("--speed", type=float, default=100.0)
    ap.add_argument("--imwidth", type=int, default=1024)
    ap.add_argument("--real-timeout", type=float, default=3600)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--report", default=None)
    ap.add_argument("--fresh-trees", action="store_true")
    ap.add_argument("--report-only", action="store_true", help="rebuild the report from existing runs")
    ap.add_argument("--mm-config", default=None,
                    help="Micro-Manager demo run: real pycromanager + headless Micro-Manager on this config "
                         "(runs one at a time; use --speed 1)")
    ap.add_argument("--run-suffix", default="", help="added to run folder names, e.g. __mmdemo")
    ap.add_argument("--stall", type=float, default=None, help="virtual seconds without progress = hang")
    args = ap.parse_args()

    trees = args.trees.split(",")
    scen = list(scenarios.SCENARIOS) if args.scenarios == "all" else args.scenarios.split(",")
    os.makedirs(args.scratch, exist_ok=True)
    jobs = [(t, s) for s in scen for t in trees]
    if args.report_only:
        infos = []
        for t, s in jobs:
            p = os.path.join(args.scratch, "runs", f"{t}__{s}{args.run_suffix}", "run_info.json")
            if os.path.exists(p):
                with open(p) as f:
                    infos.append(json.load(f))
    else:
        for t in trees:
            if args.fresh_trees or not os.path.exists(os.path.join(args.scratch, "trees", t)):
                prepare_tree(t, args.scratch)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            infos = list(ex.map(lambda ts: run_one(ts[0], ts[1], args.scratch, args), jobs))

    report = compare.build_report(infos, trees, scen)
    path = args.report or os.path.join(args.scratch, "report.md")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"report: {path}")


if __name__ == "__main__":
    main()
