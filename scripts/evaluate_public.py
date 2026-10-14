#!/usr/bin/env python3
"""CTXGAP main37 — (B) PUBLIC-TEXT EVALUATION harness. Zero API by default.

    python3 evaluate_public.py                      # emit observer_inputs.jsonl
    python3 evaluate_public.py --answers obs.json   # score an external Observer run

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

Usage
-----
  answers file format (JSON):  {"<probe_id>": "correct"|"partial"|"wrong"|"unknown", ...}
  Only probes present in the file are scored; coverage is reported.
"""
from __future__ import annotations

import argparse, collections, json
from pathlib import Path

P = Path(__file__).resolve().parent
SCORE = {"correct": 1.0, "partial": 0.5, "wrong": 0.0, "unknown": 0.0}
FROZEN_ACC_U = 0.520500          # frozen, from reproduce_main37.py
FROZEN_GAP_VIEW = 0.406582


def load(name):
    return [json.loads(l) for l in open(P / f"{name}.jsonl", encoding="utf-8") if l.strip()]


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

    available = [x for x in probes
                 if x.get("public_text") and u.get(x["unit_id"], {}).get("public_text")]

    with open(P / "observer_inputs.jsonl", "w", encoding="utf-8") as f:
        for x in available:
            f.write(json.dumps({
                "probe_id": x["probe_id"], "unit_id": x["unit_id"],
                "category": x["category"], "importance": x.get("importance"),
                "weight": round(w[x["probe_id"]], 6),
                "question": x["question"], "reference": x["reference"],
                "u_view_chars": len(u[x["unit_id"]]["text"]),
            }, ensure_ascii=False) + "\n")

    print(f"observer inputs written : {len(available)}  -> observer_inputs.jsonl")
    print(f"(U text is read from u_views.jsonl, keyed by unit_id)")

    if not a.answers:
        print("\nno --answers given: (B) is UNEVALUATED. "
              "Run an Observer on these inputs, then re-run with --answers.")
        return

    ans = json.loads(Path(a.answers).read_text(encoding="utf-8"))
    num = den = 0.0
    scored = 0
    for x in available:
        lab = ans.get(x["probe_id"])
        if lab is None:
            continue
        scored += 1
        num += w[x["probe_id"]] * SCORE.get(lab, 0.0)
        den += w[x["probe_id"]]
    acc = num / den if den else None
    out = {
        "mode": "B_public_text_evaluation",
        "n_inputs": len(available), "n_scored": scored,
        "coverage": scored / len(available) if available else None,
        "acc_U_public": acc,
        "frozen_acc_U": FROZEN_ACC_U,
        "delta_acc_U": (acc - FROZEN_ACC_U) if acc is not None else None,
        "gap_view": None,
        "why_no_gap_view": "T_full contains private reasoning and is not published; (B) cannot "
                           "re-run that condition, so no Gap_view is computable here.",
        "not_equivalent_to": FROZEN_GAP_VIEW,
    }
    (P / "public_text_evaluation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
