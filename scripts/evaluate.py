#!/usr/bin/env python3
"""CTXGAP evaluator -- run the frozen Observer + Judge on the PUBLISHED text.

Backend-agnostic: this script does NOT depend on any internal CLI or gateway.
You supply your own model call as a command template that reads the prompt on
stdin and writes the answer to stdout:

    export CTXGAP_EVAL_CMD='llm -m {model}'
    export CTXGAP_EVAL_CMD='my_runner --model {model}'
    export CTXGAP_EVAL_MODEL=claude-sonnet-4-5
    python3 evaluate.py --view U --limit 2

Prompts are the frozen ones (analysis/prompts_v3.py, PROMPT_VERSION v3.2):
    system : observer_system.txt
    user   : observer_prompt.txt  ({intro}/{material}/{questions})
    judge  : judge_prompt.txt      ({items})

This is a NEW measurement on PUBLISHED text, not a replay of the original run
(T_public != T_full). Its numbers must never be reported as the paper's 0.4066.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, threading, collections, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
PROMPTS = ROOT / "prompts"
SCORE = {"correct": 1.0, "partial": 0.5, "wrong": 0.0, "unknown": 0.0}


def call(user_prompt, cmd_tpl, model, system=None, timeout=1800):
    cmd = [c.format(model=model) for c in cmd_tpl]
    if system:
        cmd += ["--system", system] if False else []
    try:
        r = subprocess.run(cmd, input=user_prompt, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None, "command not found: %s" % cmd_tpl
    except subprocess.TimeoutExpired:
        return None, "timeout"
    out = (r.stdout or "").strip()
    if not out:
        return None, "empty output (stderr: %s)" % (r.stderr or "")[:120]
    m = re.search(r"\{[\s\S]*\}", out)
    if not m:
        return None, "no JSON object in output"
    try:
        return json.loads(m.group(0)), None
    except Exception as e:
        return None, "bad JSON: %s" % str(e)[:60]


def load(name, default=None):
    p = HERE / name
    if not p.exists():
        return default
    if name.endswith(".json"):
        return json.loads(p.read_text(encoding="utf-8"))
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", default="U", choices=["U", "V"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=os.environ.get("CTXGAP_EVAL_MODEL", "claude-sonnet-4-5"))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    cmd_tpl = os.environ.get("CTXGAP_EVAL_CMD")
    if not cmd_tpl:
        print("ERROR: set CTXGAP_EVAL_CMD to a command that reads the prompt on stdin, e.g.")
        print("  export CTXGAP_EVAL_CMD='llm -m {model}'")
        print("  export CTXGAP_EVAL_MODEL=claude-sonnet-4-5")
        sys.exit(2)
    cmd_tpl = cmd_tpl.split()

    sys_txt = (PROMPTS / "observer_system.txt").read_text(encoding="utf-8")
    tmpl = (PROMPTS / "observer_prompt.txt").read_text(encoding="utf-8")
    judge = (PROMPTS / "judge_prompt.txt").read_text(encoding="utf-8")
    intro = load(str(PROMPTS / "view_intro.json"), {}) or {}
    views = load(str(DATA / ("u_views.jsonl" if a.view == "U" else "views_V.jsonl")), []) or []
    probes = load(str(DATA / "probes.jsonl"), []) or []

    byunit = collections.defaultdict(list)
    for p in probes:
        if p.get("public_text") is False:
            continue
        byunit[p["unit_id"]].append(p)
    units = [v for v in views if byunit.get(v["unit_id"])]
    if a.limit:
        units = units[:a.limit]
    print(f"units={len(units)} view={a.view} model={a.model} prompt_version=v3.2", flush=True)

    import time as _t
    _tag = f"{a.view}__{a.model.replace('/', '_').replace(' ', '_')}__{_t.strftime('%Y%m%d-%H%M%S')}"
    outd = ROOT / "evaluation_out" / _tag
    outd.mkdir(parents=True, exist_ok=True)
    print("  output dir:", outd, flush=True)
    lock = threading.Lock(); done = [0]; errs = collections.Counter()

    def work(v):
        ps = byunit[v["unit_id"]]
        qmap = {p["probe_id"].split(":")[-1]: p for p in ps}
        qs = "\n".join(f"{q}. {p.get('question')}" for q, p in qmap.items())
        # system prompt is prepended to the user message (backend-agnostic)
        user = sys_txt + "\n\n" + tmpl.format(
            intro=intro.get(a.view, ""), material=v.get("text", ""), questions=qs)
        ans, err = call(user, cmd_tpl, a.model)
        if not ans:
            with lock: errs[err or "unknown"] += 1
            return
        items = "\n".join(f"{q}. 参考：{qmap[q].get('reference') if q in qmap else ''}\n"
                           f"   回答：{t}" for q, t in ans.items() if q in qmap)
        lab, err = call(judge.format(items=items), cmd_tpl, a.model)
        if not lab:
            with lock: errs["judge: " + str(err)] += 1
            return
        _scores = {q: SCORE.get(str(l).strip().lower(), 0.0) for q, l in lab.items()
                   if q in qmap}
        rec = {"unit_id": v["unit_id"], "view": a.view, "model": a.model,
               "prompt_version": "v3.2", "answers": ans, "labels": lab,
               "n_asked": len(qmap), "n_answered": len([q for q in ans if q in qmap]),
               "n_scored": len(_scores), "scores": _scores}
        (outd / (v["unit_id"].replace("::", "__") + f"__{a.view}.json")).write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        with lock:
            done[0] += 1
            if done[0] % 10 == 0:
                print("  done", done[0], flush=True)

    it = iter(units); stop = object()
    def loop():
        while True:
            x = next(it, stop)
            if x is stop:
                return
            work(x)
    ts = [threading.Thread(target=loop) for _ in range(a.workers)]
    [t.start() for t in ts]; [t.join() for t in ts]

    vals = []; n_asked = 0
    for f in sorted(outd.glob("*.json")):
        if f.name == "summary.json":
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if "scores" not in d:
            continue
        vals += list(d["scores"].values())
        n_asked += int(d.get("n_asked", 0))
    if vals:
        acc = sum(vals) / len(vals)
        print(f"\n=== PUBLIC-TEXT EVALUATION (view={a.view}, model={a.model}) ===")
        cov = (len(vals) / n_asked) if n_asked else 0.0
        acc_floor = (sum(vals) / n_asked) if n_asked else 0.0
        print(f"  questions asked   = {n_asked}")
        print(f"  scored (answered) = {len(vals)}   coverage = {cov:.3f}")
        print(f"  Acc({a.view}) over answered      = {acc:.4f}")
        print(f"  Acc({a.view}) unanswered-as-zero = {acc_floor:.4f}  (lower bound)")
        if cov < 0.999:
            print(f"  WARNING: {n_asked - len(vals)} question(s) unanswered; accuracy over")
            print("           answered items is inflated -- report the coverage and the")
            print("           unanswered-as-zero figure, not just the first number.")
        print("  NEW measurement on published text -- NOT the paper's 0.4066.")
        print("  See DISCLOSURES.md (T_public != T_full).")
        (outd / "summary.json").write_text(json.dumps(
            {"view": a.view, "model": a.model, "prompt_version": "v3.2",
             "n_asked": n_asked, "n_scored": len(vals),
             "coverage": round(cov, 6),
             "acc_over_answered": round(acc, 6),
             "acc_unanswered_as_zero": round(acc_floor, 6),
             "errors": dict(errs)}, indent=1), encoding="utf-8")
    if errs:
        print("  errors:", dict(errs))


if __name__ == "__main__":
    main()
