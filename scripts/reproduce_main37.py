#!/usr/bin/env python3
"""CTXGAP main37 -- reproduce the paper's 37-task headline. Zero API, no network.

    python3 reproduce_main37.py

TWO DIFFERENT THINGS. They are NOT equivalent and must never be presented as one:

  (A) FROZEN-SCORE REPRODUCTION  (what this script computes)
      Recomputes Gap_view from the published NUMERIC layer: frozen observer/judge scores,
      the frozen weight, and the frozen validity flag, on the frozen 37-task sample.
      -> Gap_view = 0.406582  (n_probes 4,855 / n_valid 4,799)
      This validates the ARITHMETIC of the headline number. It does not re-run any model.

  (B) POST-SANITIZATION EVALUATION  (NOT done here, and cannot be claimed equal to (A))
      Re-running an external Observer on the published sanitized inputs. The published
      `U` view is sanitized text, so a re-run measures a DIFFERENT input than the frozen
      one. Any such result must be reported separately, with its own delta.
      The `T_full` condition contains private reasoning: its TEXT is not published, so (B)
      cannot reproduce the T_full condition at all. Only its frozen score is published.

Weight (frozen rule, analysis/report_v3.py L64-86):
    w(probe) = #atoms(importance >= 2, category c) at (run, checkpoint)
               / #probes(category c) at (run, checkpoint)
Validity (frozen rule, analysis/m6_rq1.py L77-78):
    valid  <=>  mean(prior) < 1  AND  mean(T_full) > 0
Accuracy:
    weighted mean  sum(w * score) / sum(w),  score: correct 1.0 / partial 0.5 / wrong 0 / unknown 0
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]      # repository root
DATA = P / "data"
TARGET = {"n_probes": 4855, "n_valid": 4799, "gap_view": 0.406582}


def load(name):
    return [json.loads(l) for l in open(DATA / f"{name}.jsonl", encoding="utf-8") if l.strip()]


def main():
    atoms = load("atoms")
    probes = load("probes")
    jud = load("judgements")

    n_cat = collections.defaultdict(int)
    for a in atoms:
        if (a.get("importance") or 0) >= 2:
            n_cat[(a["unit_id"], a["category"])] += 1
    p_cat = collections.Counter((p["unit_id"], p["category"]) for p in probes)
    w = {}
    for p in probes:
        k = (p["unit_id"], p["category"])
        w[p["probe_id"]] = n_cat[k] / p_cat[k] if p_cat[k] else 1.0

    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for j in jud:
        per[j["probe_id"]][j["condition"]].append(j["score"])

    rows = []
    for p in probes:
        c = per.get(p["probe_id"]) or {}
        sc = {k: sum(v) / len(v) for k, v in c.items()}
        rows.append({"probe_id": p["probe_id"], "unit_id": p["unit_id"],
                     "category": p["category"], "w": w[p["probe_id"]],
                     "public_text": p.get("public_text", False), **sc})
        rows[-1]["valid"] = (sc.get("prior") is not None and sc["prior"] < 1
                             and sc.get("T_full") is not None and sc["T_full"] > 0)

    valid = [r for r in rows if r["valid"]]

    def wmean(rs, key):
        num = den = 0.0
        for r in rs:
            if r.get(key) is None:
                continue
            num += r["w"] * r[key]
            den += r["w"]
        return num / den if den else None

    u, t = wmean(valid, "U"), wmean(valid, "T_full")
    gap = t - u

    # (A) frozen-score reproduction -- all 4,855, numeric layer only
    print("=== (A) FROZEN-SCORE REPRODUCTION ===")
    print(f"  probes          {len(rows):>6}  (target {TARGET['n_probes']})  "
          f"{'OK' if len(rows) == TARGET['n_probes'] else 'MISMATCH'}")
    print(f"  valid probes    {len(valid):>6}  (target {TARGET['n_valid']})  "
          f"{'OK' if len(valid) == TARGET['n_valid'] else 'MISMATCH'}")
    print(f"  Acc(U)          {u:.6f}")
    print(f"  Acc(T_full)     {t:.6f}")
    print(f"  Gap_view        {gap:.6f}  (target {TARGET['gap_view']})  "
          f"{'OK' if abs(gap - TARGET['gap_view']) < 5e-6 else 'MISMATCH'}")

    # cleared (text-publishable) subset, reported separately, NOT a substitute for (A)
    cl = [r for r in valid if r["public_text"]]
    u2, t2 = wmean(cl, "U"), wmean(cl, "T_full")
    print("\n=== text-publishable subset (audit-cleared probes only) ===")
    print(f"  valid probes    {len(cl):>6}")
    print(f"  Acc(U)          {u2:.6f}")
    print(f"  Acc(T_full)     {t2:.6f}")
    print(f"  Gap_view        {t2 - u2:.6f}   <- descriptive only; NOT the headline, "
          f"NOT a substitute for (A)")

    out = {
        "reproduction_kind": "frozen-score reproduction (arithmetic only, no model re-run)",
        "n_probes": len(rows), "n_valid": len(valid),
        "acc_U": u, "acc_T_full": t, "gap_view": gap,
        "target": TARGET,
        "gap_view_matches_target": abs(gap - TARGET["gap_view"]) < 5e-6,
        "text_publishable_subset": {"n_valid": len(cl), "acc_U": u2, "acc_T_full": t2,
                                    "gap_view": t2 - u2},
        "not_claimable": [
            "Equality with a post-sanitization Observer re-run (B): the sanitized U view is a "
            "different input from the frozen one; (B) must be reported with its own delta.",
            "Reproduction of the T_full condition by an external party: T_full contains private "
            "reasoning, its text is not published; only its frozen score is.",
        ],
    }
    (DATA / "reproduced_main37.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    print(f"\n[w] {DATA / 'reproduced_main37.json'}")


if __name__ == "__main__":
    main()
