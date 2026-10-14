#!/usr/bin/env python3
"""Reproduce every quantitative result of the paper from the anonymous numeric tables.

    python3 reproduce_all.py            (from release/public/main37/)

Inputs  : anon/main37_units.csv, anon/task_success.csv,
          anon/cross_harness_units.csv, anon/e2_units.csv
Outputs : the paper numbers and their 95% CIs, printed and written to reproduced_all.json

Conventions (frozen):
  score   : correct=1, partial=.5, wrong=0, unknown=0 (E2: already averaged per probe)
  valid   : frozen flag shipped in the tables
  weight  : frozen probe weight w
  CI      : TASK-clustered percentile bootstrap, random.Random(0), 10000 draws,
            upper index int(0.975*n)-1, probe-weighted
Nothing here re-measures anything: these are the same frozen per-probe numbers.
"""
from __future__ import annotations
import csv, json, random, collections
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANON = HERE.parent / "data" / "anon"
SEED, NBOOT = 0, 10000


def load(name):
    with open(ANON / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fl(x):
    x = (x or "").strip()
    return None if x == "" else float(x)


def wmean(rows, key):
    n = d = 0.0
    for r in rows:
        v = r.get(key)
        if v is None:
            continue
        n += r["_w"] * v; d += r["_w"]
    return n / d if d else None


def boot(rows, key_a, key_b=None):
    """CI of weighted mean of key_a (or of key_a - key_b) over task clusters."""
    by = defaultdict(list)
    for r in rows:
        by[r["_run"]].append(r)
    keys = sorted(by)
    if len(keys) < 2:
        return None
    rng = random.Random(SEED)
    vals = []
    for _ in range(NBOOT):
        pick = [keys[rng.randrange(len(keys))] for _ in keys]
        sub = [x for k in pick for x in by[k]]
        a = wmean(sub, key_a)
        if a is None:
            continue
        if key_b is not None:
            b = wmean(sub, key_b)
            if b is None:
                continue
            a = a - b
        vals.append(a)
    vals.sort()
    return [round(vals[int(.025 * len(vals))], 6), round(vals[int(.975 * len(vals)) - 1], 6)]


def main():
    out = {}

    # ---------- 1. main 37-task experiment ----------
    rows = []
    for r in load("main37_units.csv"):
        d = {"_run": r["run"], "_w": fl(r["w"]), "k": int(r["k"]),
             "acc_U": fl(r["acc_U"]), "acc_T_full": fl(r["acc_T_full"]),
             "acc_agent": fl(r["acc_agent"]), "acc_prior": fl(r["acc_prior"])}
        if r["valid"] == "1":
            rows.append(d)
    accU = wmean(rows, "acc_U"); accT = wmean(rows, "acc_T_full")
    accA = wmean(rows, "acc_agent")
    gap = accT - accU
    out["main"] = {"n_valid_probes": len(rows), "n_tasks": len({r["_run"] for r in rows}),
                   "acc_U": round(accU, 6), "acc_T_full": round(accT, 6),
                   "acc_actor": round(accA, 6), "gap": round(gap, 6),
                   "gap_ci95": boot(rows, "acc_T_full", "acc_U")}
    print("=== MAIN (37 tasks) ===")
    print(f"  valid probes = {len(rows)}   tasks = {len({r['_run'] for r in rows})}")
    print(f"  Acc(U)     = {accU:.4f}")
    print(f"  Acc(T_full)= {accT:.4f}")
    print(f"  Acc(Actor) = {accA:.4f}")
    print(f"  Gap        = {gap:.4f}   CI95 {out['main']['gap_ci95']}")

    # ---------- 2. successful tasks ----------
    succ = {}
    for r in load("task_success.csv"):
        succ[r["run"]] = r["fixed_k4"]
    fixed = {k for k, v in succ.items() if v == "1"}
    sub = [r for r in rows if r["_run"] in fixed and r["k"] == 4]
    if sub:
        u, t = wmean(sub, "acc_U"), wmean(sub, "acc_T_full")
        out["successful_tasks_k4"] = {"n_tasks": len(fixed), "n_probes": len(sub),
                                      "acc_U": round(u, 6), "acc_T_full": round(t, 6),
                                      "gap": round(t - u, 6),
                                      "gap_ci95": boot(sub, "acc_T_full", "acc_U")}
        print("\n=== SUCCESSFUL TASKS (objective truth, k4) ===")
        print(f"  tasks={len(fixed)} probes={len(sub)}  Acc(U)={u:.4f} Acc(T)={t:.4f} "
              f"Gap={t-u:.4f}  CI95 {out['successful_tasks_k4']['gap_ci95']}")

    # ---------- 3. cross-harness ----------
    ch = []
    for r in load("cross_harness_units.csv"):
        if r["valid"] == "1":
            ch.append({"_run": r["run"], "_task": r["task"], "_w": fl(r["w"]), "harness": r["harness"],
                       "acc_U": fl(r["acc_U"]), "acc_T_full": fl(r["acc_T_full"])})
    out["cross_harness"] = {}
    print("\n=== CROSS-HARNESS (12 tasks x 3 harnesses, TASK-EQUAL aggregation) ===")
    for h in ("ClaudeCode", "Pi", "DSH"):
        s = [r for r in ch if r["harness"] == h]
        if not s:
            continue
        # paper convention: gap per (task, harness), then EQUAL average over the 12 tasks
        pertask = defaultdict(list)
        for r in s:
            pertask[r["_task"]].append(r)
        gaps = {t_: (wmean(v, "acc_T_full") - wmean(v, "acc_U")) for t_, v in pertask.items()}
        gaps = {t_: g for t_, g in gaps.items() if g is not None}
        macro = sum(gaps.values()) / len(gaps)
        u, t = wmean(s, "acc_U"), wmean(s, "acc_T_full")
        # bootstrap: resample tasks, task-equal mean of per-task gaps
        keys = sorted(gaps)
        rng = random.Random(SEED)
        vals = []
        for _ in range(NBOOT):
            pick = [keys[rng.randrange(len(keys))] for _ in keys]
            vals.append(sum(gaps[k] for k in pick) / len(pick))
        vals.sort()
        ci = [round(vals[int(.025 * len(vals))], 6), round(vals[int(.975 * len(vals)) - 1], 6)]
        out["cross_harness"][h] = {"n_probes": len(s), "n_tasks": len(gaps),
                                   "acc_U_pooled": round(u, 6), "acc_T_full_pooled": round(t, 6),
                                   "gap_task_equal": round(macro, 6), "gap_ci95": ci}
        print(f"  {h:12s} n={len(s):5d} tasks={len(gaps)}  Gap(task-equal)={macro:.4f}  CI95 {ci}")

    # ---------- 4. E2 equal-total-length rewrite ----------
    # pivot: per (run, k, qid) gather arm scores
    piv = collections.defaultdict(dict)
    for r in load("e2_units.csv"):
        if r["valid"] == "1":
            piv[(r["run"], r["k"], r["qid"])][r["arm"]] = fl(r["score"])
    arms = {"A": [], "B": [], "C": []}
    wmap = {}
    for r in load("e2_units.csv"):
        if r["valid"] == "1":
            wmap[(r["run"], r["k"], r["qid"])] = fl(r["w"])
    for key, d in piv.items():
        if not {"A", "B", "C"} <= set(d):
            continue
        for a in ("A", "B", "C"):
            arms[a].append({"_run": key[0], "_w": wmap[key], "score": d[a]})
    if arms["A"]:
        acc = {a: wmean(arms[a], "score") for a in ("A", "B", "C")}
        print("\n=== E2 EQUAL-TOTAL-LENGTH REWRITE (129 paired units) ===")
        for a in ("A", "B", "C"):
            print(f"  Acc({a}) = {acc[a]:.4f}   (n={len(arms[a])})")
        out["e2"] = {"n_probes": len(arms["A"]), "acc": {a: round(acc[a], 6) for a in ("A", "B", "C")}}
        # paired bootstrap over runs, aligned by index
        byrun = {a: defaultdict(list) for a in ("A", "B", "C")}
        for a in ("A", "B", "C"):
            for r in arms[a]:
                byrun[a][r["_run"]].append(r)
        keys = sorted(set(byrun["A"]) & set(byrun["B"]) & set(byrun["C"]))
        rng = random.Random(SEED)
        bs = {a: [] for a in ("A", "B", "C")}
        for _ in range(NBOOT):
            pick = [keys[rng.randrange(len(keys))] for _ in keys]
            vals = {}
            ok = True
            for a in ("A", "B", "C"):
                sub = [x for k in pick for x in byrun[a][k]]
                v = wmean(sub, "score")
                if v is None:
                    ok = False; break
                vals[a] = v
            if ok:
                for a in ("A", "B", "C"):
                    bs[a].append(vals[a])
        for x, y in (("B", "A"), ("C", "A"), ("C", "B")):
            d = sorted(a - b for a, b in zip(bs[x], bs[y]))
            ci = [round(d[int(.025 * len(d))], 6), round(d[int(.975 * len(d)) - 1], 6)]
            out["e2"][f"{x}-{y}"] = {"diff": round(acc[x] - acc[y], 6), "ci95": ci}
            print(f"  {x} - {y} = {acc[x]-acc[y]:+.4f}   CI95 {ci}")

    (HERE / "reproduced_all.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\n[w] {HERE/'reproduced_all.json'}")


if __name__ == "__main__":
    main()
