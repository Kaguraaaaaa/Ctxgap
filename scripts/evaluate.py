#!/usr/bin/env python3
"""CTXGAP evaluator -- run the frozen Observer + Judge on the PUBLISHED text.

Backend-agnostic: this script does NOT depend on any internal CLI or gateway.
You supply your own model call as a command template that reads the prompt on
stdin and writes the answer to stdout:

    export CTXGAP_EVAL_CMD='llm -m {model}'
    export CTXGAP_EVAL_CMD='my_runner --model {model}'
    export CTXGAP_EVAL_MODEL=claude-sonnet-4-5
    python3 evaluate.py --view U --limit 2

The requested model name is ALSO exported as CTXGAP_EVAL_MODEL for every child
process, so adapters that do not use a {model} placeholder still call the model
you asked for (see scripts/my_model_adapter.py).

Prompts are the frozen ones (analysis/prompts_v3.py, PROMPT_VERSION v3.2):
    system : observer_system.txt
    user   : observer_prompt.txt  ({intro}/{material}/{questions})
    judge  : judge_prompt.txt      ({items})

This is a NEW measurement on PUBLISHED text, not a replay of the original run
(T_public != T_full). Its numbers must never be reported as the paper's 0.4066.

Accuracy convention (unified with evaluate_public.py and reproduce_main37.py):
    PRIMARY   probe-weighted mean, w from the frozen rule in analysis/report_v3.py
              w(probe) = #atoms(importance>=2, category c) / #probes(category c)
    SECONDARY unweighted (simple) mean, printed alongside for transparency
A frozen baseline is recomputed on EXACTLY the same probe set that was evaluated,
so `delta_acc_U` compares like with like.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, threading, collections, sys, time, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
PROMPTS = ROOT / "prompts"
SCORE = {"correct": 1.0, "partial": 0.5, "wrong": 0.0, "unknown": 0.0}


def as_bool(v, default=True):
    """`public_text` is a bool in the JSONL; tolerate "false"/None/0 anyway."""
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("", "false", "0", "no")
    return bool(v)


def call(user_prompt, cmd_tpl, model, timeout=1800):
    cmd = [c.format(model=model) for c in cmd_tpl]
    # FIX: also export the model name, so an adapter without a {model} placeholder
    # (e.g. scripts/my_model_adapter.py) cannot silently fall back to a different one.
    env = dict(os.environ)
    env["CTXGAP_EVAL_MODEL"] = model
    try:
        r = subprocess.run(cmd, input=user_prompt, capture_output=True,
                           text=True, timeout=timeout, env=env)
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
    p = DATA / name
    if not p.exists():
        return default
    if name.endswith(".json"):
        return json.loads(p.read_text(encoding="utf-8"))
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def weights(atoms, probes):
    """Frozen probe weight (analysis/report_v3.py L64-86)."""
    n_cat = collections.defaultdict(int)
    for a in atoms:
        if (a.get("importance") or 0) >= 2:
            n_cat[(a["unit_id"], a["category"])] += 1
    p_cat = collections.Counter((p["unit_id"], p["category"]) for p in probes)
    w = {}
    for p in probes:
        k = (p["unit_id"], p["category"])
        w[p["probe_id"]] = n_cat[k] / p_cat[k] if p_cat[k] else 1.0
    return w


def frozen_scores(jud):
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for j in jud:
        per[j["probe_id"]][j["condition"]].append(j["score"])
    return {pid: {k: sum(v) / len(v) for k, v in c.items()} for pid, c in per.items()}


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
    _vi = PROMPTS / "view_intro.json"
    intro = json.loads(_vi.read_text(encoding="utf-8")) if _vi.exists() else {}

    probes_all = load("probes.jsonl", []) or []
    atoms = load("atoms.jsonl", []) or []
    jud = load("judgements.jsonl", []) or []
    views = load("u_views.jsonl" if a.view == "U" else "views_V.jsonl", []) or []
    wmap = weights(atoms, probes_all)

    # ---- input selection: BOTH the probe and the view must be publishable ----
    # A view whose text is null ships the literal string "None" to the model, so
    # "public_text" alone is not enough: require non-empty text as well.
    n_skip_probe = sum(1 for p in probes_all if not as_bool(p.get("public_text"), True))
    byunit = collections.defaultdict(list)
    for p in probes_all:
        if as_bool(p.get("public_text"), True):
            byunit[p["unit_id"]].append(p)

    def usable_view(v):
        return (byunit.get(v["unit_id"])
                and as_bool(v.get("public_text"), True)
                and (v.get("text") or "").strip())

    n_skip_view = sum(1 for v in views if byunit.get(v["unit_id"]) and not usable_view(v))
    units = [v for v in views if usable_view(v)]
    if a.limit:
        units = units[:a.limit]
    asked_ids = [p["probe_id"] for v in units for p in byunit[v["unit_id"]]]
    per_unit = {v["unit_id"]: len(byunit[v["unit_id"]]) for v in units}
    n_asked_total = sum(per_unit.values())          # FIX: denominator fixed BEFORE any call

    print(f"view={a.view} model={a.model} prompt_version=v3.2", flush=True)
    print(f"  probes withheld (not public)      : {n_skip_probe}", flush=True)
    print(f"  units dropped (view not publishable): {n_skip_view}", flush=True)
    print(f"  units={len(units)}  questions_asked={n_asked_total}", flush=True)

    # ---- unique output dir: same second + same model must not reuse a directory ----
    _tag = (f"{a.view}__{a.model.replace('/', '_').replace(' ', '_')}"
            f"__{time.strftime('%Y%m%d-%H%M%S')}__{uuid.uuid4().hex[:8]}")
    outd = ROOT / "evaluation_out" / _tag
    outd.mkdir(parents=True, exist_ok=True)
    print("  output dir:", outd, flush=True)
    lock = threading.Lock(); done = [0]; errs = collections.Counter()

    def write(rec):
        (outd / (rec["unit_id"].replace("::", "__") + f"__{a.view}.json")).write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8")

    def work(v):
        ps = byunit[v["unit_id"]]
        qmap = {p["probe_id"].split(":")[-1]: p for p in ps}
        q2p = {q: p["probe_id"] for q, p in qmap.items()}
        base = {"unit_id": v["unit_id"], "view": a.view, "model": a.model,
                "prompt_version": "v3.2", "n_asked": len(qmap)}
        qs = "\n".join(f"{q}. {p.get('question')}" for q, p in qmap.items())
        # system prompt is prepended to the user message (backend-agnostic)
        user = sys_txt + "\n\n" + tmpl.format(
            intro=intro.get(a.view, ""), material=v.get("text", ""), questions=qs)
        ans, err = call(user, cmd_tpl, a.model)
        if not ans:
            # FIX: a failed unit still counts in the denominator -- record it.
            with lock: errs[err or "unknown"] += 1
            write({**base, "error": err, "n_answered": 0, "n_scored": 0, "scores": {}})
            return
        # FIX: only questions the Observer actually answered may be sent to the Judge.
        answered = {q: t for q, t in ans.items() if q in qmap and str(t).strip()}
        if not answered:
            with lock: errs["observer returned no usable answer"] += 1
            write({**base, "answers": ans, "error": "no usable answer",
                   "n_answered": 0, "n_scored": 0, "scores": {}})
            return
        items = "\n".join(f"{q}. 参考：{qmap[q].get('reference')}\n   回答：{t}"
                          for q, t in answered.items())
        lab, err = call(judge.format(items=items), cmd_tpl, a.model)
        if not lab:
            # FIX: a failed Judge must not silently vanish from the denominator either.
            with lock: errs["judge: " + str(err)] += 1
            write({**base, "answers": ans, "error": "judge: " + str(err),
                   "n_answered": len(answered), "n_scored": 0, "scores": {}})
            return
        scores, ignored = {}, []
        for q, l in lab.items():
            if q not in answered:          # FIX: never score a question that was not asked
                ignored.append(q)
                continue
            ls = str(l).strip().lower()
            if ls not in SCORE:
                ignored.append(q)
                continue
            scores[q2p[q]] = SCORE[ls]
        write({**base, "answers": ans, "labels": lab, "scores": scores,
               "n_answered": len(answered), "n_scored": len(scores),
               "unanswered": sorted(set(qmap) - set(answered)),
               "judge_labels_ignored": sorted(set(ignored))})
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

    # ---- aggregate: every selected unit contributes, record or not ----
    recs = []
    for v in units:
        fp = outd / (v["unit_id"].replace("::", "__") + f"__{a.view}.json")
        if fp.exists():
            recs.append(json.loads(fp.read_text(encoding="utf-8")))
        else:
            recs.append({"unit_id": v["unit_id"], "view": a.view, "error": "no record written",
                         "n_asked": per_unit[v["unit_id"]], "n_answered": 0, "n_scored": 0,
                         "scores": {}})
    n_asked = sum(int(r.get("n_asked", 0)) for r in recs)
    n_answered = sum(int(r.get("n_answered", 0)) for r in recs)
    scored = [(pid, float(s)) for r in recs for pid, s in (r.get("scores") or {}).items()]
    n_scored = len(scored)

    w_asked = sum(wmap.get(i, 1.0) for i in asked_ids)
    w_scored = sum(wmap.get(i, 1.0) for i, _ in scored)
    num_w = sum(wmap.get(i, 1.0) * s for i, s in scored)
    acc_w = num_w / w_scored if w_scored else None
    acc_s = sum(s for _, s in scored) / n_scored if n_scored else None
    cov = (n_scored / n_asked) if n_asked else 0.0
    acc_floor_w = (num_w / w_asked) if w_asked else 0.0
    acc_floor_s = (sum(s for _, s in scored) / n_asked) if n_asked else 0.0

    # ---- frozen baseline on EXACTLY the same probe set ----
    fs = frozen_scores(jud)
    def wacc(ids, key):
        num = den = 0.0
        for i in ids:
            s = (fs.get(i) or {}).get(key)
            if s is None:
                continue
            num += wmap.get(i, 1.0) * s; den += wmap.get(i, 1.0)
        return num / den if den else None
    fU, fT = wacc(asked_ids, "U"), wacc(asked_ids, "T_full")
    valid_ids = [i for i in asked_ids
                 if (fs.get(i) or {}).get("prior") is not None and fs[i]["prior"] < 1
                 and (fs.get(i) or {}).get("T_full") is not None and fs[i]["T_full"] > 0]
    fU_v, fT_v = wacc(valid_ids, "U"), wacc(valid_ids, "T_full")

    print(f"\n=== PUBLIC-TEXT EVALUATION (view={a.view}, model={a.model}) ===")
    print(f"  questions asked              = {n_asked}")
    print(f"  answered                     = {n_answered}")
    print(f"  scored                       = {n_scored}   coverage = {cov:.3f}")
    if acc_w is not None:
        print(f"  Acc({a.view}) weighted, over scored     = {acc_w:.4f}   <- PRIMARY")
        print(f"  Acc({a.view}) unweighted, over scored   = {acc_s:.4f}   (secondary)")
        print(f"  Acc({a.view}) weighted, unanswered=0    = {acc_floor_w:.4f}  (lower bound)")
        print(f"  Acc({a.view}) unweighted, unanswered=0  = {acc_floor_s:.4f}  (lower bound)")
    print(f"  frozen Acc(U) on the same set = {fU:.4f}" if fU is not None else "")
    print(f"  frozen Acc(T_full) same set   = {fT:.4f}" if fT is not None else "")
    print(f"  frozen Gap on the same set    = {fT - fU:.4f}" if (fU is not None and fT is not None) else "")
    if fU_v is not None and fT_v is not None:
        print(f"  frozen on same set, valid only = Acc(U) {fU_v:.4f} / Acc(T_full) {fT_v:.4f} "
              f"/ Gap {fT_v - fU_v:.4f}  (n={len(valid_ids)})")
    if acc_w is not None and fU is not None:
        print(f"  delta Acc(U)  new - frozen    = {acc_w - fU:+.4f}")
    if cov < 0.999:
        print(f"  WARNING: {n_asked - n_scored} question(s) unscored; the over-scored accuracy")
        print("           is inflated -- report coverage and the unanswered-as-zero figure.")
    print("  NEW measurement on published text -- NOT the paper's 0.4066.")
    print("  See DISCLOSURES.md (T_public != T_full).")
    (outd / "summary.json").write_text(json.dumps({
        "view": a.view, "model": a.model, "prompt_version": "v3.2",
        "n_asked": n_asked, "n_answered": n_answered, "n_scored": n_scored,
        "coverage": round(cov, 6),
        "acc_weighted_over_scored": acc_w, "acc_unweighted_over_scored": acc_s,
        "acc_weighted_unanswered_as_zero": acc_floor_w,
        "acc_unweighted_unanswered_as_zero": acc_floor_s,
        "frozen_on_same_set": {"n": len(asked_ids), "acc_U": fU, "acc_T_full": fT,
                               "gap": (fT - fU) if (fU is not None and fT is not None) else None,
                               "n_valid": len(valid_ids), "acc_U_valid": fU_v,
                               "acc_T_full_valid": fT_v,
                               "gap_valid": (fT_v - fU_v) if (fU_v is not None and fT_v is not None) else None},
        "delta_acc_U_vs_frozen": (acc_w - fU) if (acc_w is not None and fU is not None) else None,
        "probes_withheld_not_public": n_skip_probe,
        "units_dropped_view_not_publishable": n_skip_view,
        "errors": dict(errs)}, indent=1), encoding="utf-8")
    if errs:
        print("  errors:", dict(errs))


if __name__ == "__main__":
    main()
