#!/usr/bin/env python3
"""CTXGAP main37 — (B) PUBLIC-TEXT EVALUATION harness. Zero API by default.

    python3 scripts/evaluate_public.py                      # emit observer_inputs.jsonl
    python3 scripts/evaluate_public.py --answers obs.json   # score an external Observer run

WHAT (B) IS, AND WHAT IT IS NOT
-------------------------------
(B) runs an Observer on the PUBLISHED SANITIZED `U` view and the published probes. It is a
genuinely re-runnable measurement: the inputs are in this package, so an external researcher
can evaluate any model with CTXGAP.

(B) is NOT the same experiment as (A) frozen-score reproduction, and the two must never be
presented as one result:

  * the input text is sanitized, so it differs from the frozen input the cached scores were
    produced on;
  * `T_full` contains private reasoning, is NOT published, and therefore CANNOT be re-run by
    an external party -- so (B) cannot produce `Gap_view` at all.

What (B) CAN measure, and does measure here: **Acc(U) on public inputs**, directly comparable
with the frozen Acc(U) = 0.520500. The delta between them is exactly the quantity that must be
reported before anyone claims that public-text evaluation reproduces the frozen measurement.
That delta is currently UNMEASURED: no external Observer has been run yet.

(B) is NOT an acceptance gate for (A). (A) stands on its own.

Accuracy convention (unified with evaluate.py and reproduce_main37.py):
    PRIMARY   probe-weighted mean, w from the frozen rule in analysis/report_v3.py
    SECONDARY unweighted (simple) mean, printed alongside for transparency
The frozen baseline is recomputed on EXACTLY the same probe set that (B) evaluates, so
`delta_acc_U` compares like with like.

Usage
-----
  answers file format (JSON):  {"<probe_id>": "correct"|"partial"|"wrong"|"unknown", ...}
  Only probes present in the file are scored; coverage is reported.
"""
from __future__ import annotations

import argparse, collections, json
from pathlib import Path

P = Path(__file__).resolve().parents[1]      # repository root
DATA = P / "data"
SCORE = {"correct": 1.0, "partial": 0.5, "wrong": 0.0, "unknown": 0.0}


def load(name):
    return [json.loads(l) for l in open(DATA / f"{name}.jsonl", encoding="utf-8") if l.strip()]


def as_bool(v, default=True):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("", "false", "0", "no")
    return bool(v)


def frozen_scores(jud):
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for j in jud:
        per[j["probe_id"]][j["condition"]].append(j["score"])
    return {pid: {k: sum(v) / len(v) for k, v in c.items()} for pid, c in per.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", default=None, help="JSON map probe_id -> label")
    a = ap.parse_args()

    probes = load("probes")
    atoms = load("atoms")
    u = {r["unit_id"]: r for r in load("u_views")}

    n_cat = collections.defaultdict(int)
    for x in atoms:
        if (x.get("importance") or 0) >= 2:
            n_cat[(x["unit_id"], x["category"])] += 1
    p_cat = collections.Counter((x["unit_id"], x["category"]) for x in probes)
    w = {}
    for x in probes:
        k = (x["unit_id"], x["category"])
        w[x["probe_id"]] = n_cat[k] / p_cat[k] if p_cat[k] else 1.0

    # both the probe AND its U view must be publishable, and the view must carry text
    def ok(x):
        v = u.get(x["unit_id"], {})
        return (as_bool(x.get("public_text"), True) and as_bool(v.get("public_text"), True)
                and (v.get("text") or "").strip())

    available = [x for x in probes if ok(x)]

    with open(DATA / "observer_inputs.jsonl", "w", encoding="utf-8") as f:
        for x in available:
            f.write(json.dumps({
                "probe_id": x["probe_id"], "unit_id": x["unit_id"],
                "category": x["category"], "importance": x.get("importance"),
                "weight": round(w[x["probe_id"]], 6),
                "question": x["question"], "reference": x["reference"],
                "u_view_chars": len(u[x["unit_id"]]["text"]),
            }, ensure_ascii=False) + "\n")

    print(f"observer inputs written : {len(available)}  -> data/observer_inputs.jsonl")
    print("(U text is read from data/u_views.jsonl, keyed by unit_id)")

    # frozen baseline on EXACTLY the same set
    fs = frozen_scores(load("judgements"))
    ids = [x["probe_id"] for x in available]
    def wacc(key, subset=None):
        ss = subset if subset is not None else ids
        num = den = 0.0
        for i in ss:
            s = (fs.get(i) or {}).get(key)
            if s is None:
                continue
            num += w.get(i, 1.0) * s; den += w.get(i, 1.0)
        return num / den if den else None
    valid = [i for i in ids
             if (fs.get(i) or {}).get("prior") is not None and fs[i]["prior"] < 1
             and (fs.get(i) or {}).get("T_full") is not None and fs[i]["T_full"] > 0]
    fU, fT = wacc("U"), wacc("T_full")
    fUv, fTv = wacc("U", valid), wacc("T_full", valid)
    print(f"frozen on the same set  : Acc(U) {fU:.6f}  Acc(T_full) {fT:.6f}  "
          f"Gap {fT - fU:.6f}  (n={len(ids)})")
    print(f"frozen, valid probes only: Acc(U) {fUv:.6f}  Acc(T_full) {fTv:.6f}  "
          f"Gap {fTv - fUv:.6f}  (n={len(valid)})")

    if not a.answers:
        print("\nno --answers given: (B) is UNEVALUATED. "
              "Run an Observer on these inputs, then re-run with --answers.")
        (DATA / "public_text_evaluation.json").write_text(json.dumps({
            "mode": "B_public_text_evaluation", "n_inputs": len(available),
            "n_scored": 0, "coverage": None, "acc_U_public": None,
            "frozen_on_same_set": {"n": len(ids), "acc_U": fU, "acc_T_full": fT,
                                   "gap": (fT - fU) if (fU is not None and fT is not None) else None,
                                   "n_valid": len(valid), "acc_U_valid": fUv,
                                   "acc_T_full_valid": fTv,
                                   "gap_valid": (fTv - fUv) if (fUv is not None and fTv is not None) else None},
            "why_no_gap_view": "T_full contains private reasoning and is not published; (B) cannot "
                               "re-run that condition, so no Gap_view is computable here.",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        return

    ans = json.loads(Path(a.answers).read_text(encoding="utf-8"))
    num = den = 0.0
    simple = 0.0
    scored = 0
    bad = collections.Counter()
    for x in available:
        lab = ans.get(x["probe_id"])
        if lab is None:
            continue
        l = str(lab).strip().lower()
        if l not in SCORE:
            bad[l] += 1
            continue
        scored += 1
        num += w[x["probe_id"]] * SCORE[l]
        den += w[x["probe_id"]]
        simple += SCORE[l]
    acc = num / den if den else None
    acc_simple = simple / scored if scored else None
    out = {
        "mode": "B_public_text_evaluation",
        "n_inputs": len(available), "n_scored": scored,
        "coverage": scored / len(available) if available else None,
        "acc_U_public_weighted": acc,
        "acc_U_public_unweighted": acc_simple,
        "accuracy_convention": "PRIMARY = probe-weighted (frozen rule, analysis/report_v3.py); "
                               "unweighted printed as secondary only",
        "frozen_on_same_set": {"n": len(ids), "acc_U": fU, "acc_T_full": fT,
                               "gap": (fT - fU) if (fU is not None and fT is not None) else None,
                               "n_valid": len(valid), "acc_U_valid": fUv,
                               "acc_T_full_valid": fTv,
                               "gap_valid": (fTv - fUv) if (fUv is not None and fTv is not None) else None},
        "delta_acc_U_vs_frozen": (acc - fU) if (acc is not None and fU is not None) else None,
        "invalid_labels_dropped": dict(bad),
        "gap_view": None,
        "why_no_gap_view": "T_full contains private reasoning and is not published; (B) cannot "
                           "re-run that condition, so no Gap_view is computable here.",
    }
    (DATA / "public_text_evaluation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                      encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
