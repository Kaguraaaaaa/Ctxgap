# CTXGAP — a benchmark for task-state recoverability

**CTXGAP** measures a gap that task success does not capture: how much of an agent's
execution-grounded task state a reader can recover from the agent's own report.

- Actor can answer when asked directly: **Acc(Actor) = 93.64%**
- Reader limited to the agent's cumulative report: **Acc(U) = 52.05%**
- Reader with the full execution context: **Acc(T_full) = 92.71%**
- **Context Gap = 40.66 pp** (95% CI [0.373, 0.438])
- The gap persists on tasks the agent objectively fixed: **34.79 pp** at the final checkpoint

## Scale

| | |
|---|---|
| Tasks | 37 |
| Checkpoints (task x turn boundary) | 148 |
| Probes | 4,855 (4,799 valid; 4,573 with published text) |
| Atoms | 6,887 |
| Published report views `U` | 145 (148 units, 3 withheld) |
| Terminal scrollback views `V` | 148 |
| Frozen judgement records | 228,939 |

## Quick start

### A. Reproduce the paper numbers (no model API needed)

```bash
python3 scripts/reproduce_main37.py     # Acc(U), Acc(T_full), Gap
python3 scripts/reproduce_all.py        # + successful-task subset, cross-harness, E2, CIs
```

`reproduce_all.py` also recomputes: Actor accuracy, the 30 successful-task gap,
cross-harness gaps (task-equal aggregation), and the equal-total-length rewrite
experiment with 10,000-draw task-clustered bootstrap CIs.

### B. Evaluate your own model

```bash
export CTXGAP_EVAL_CMD='python3 scripts/my_model_adapter.py'
export CTXGAP_EVAL_MODEL='your-model-name'
python3 scripts/evaluate.py --view U
python3 scripts/evaluate.py --view V
```

You supply an adapter that reads a prompt on stdin and prints the answer to stdout.
CTXGAP supplies the fixed questions, references, published views and the frozen
scoring prompts (`prompts/`, PROMPT_VERSION `v3.2`).

## Important scope limits

- **This is a cached-score reproduction.** `reproduce_*.py` recomputes the paper's
  numbers from the frozen per-probe scores shipped here.
- **`T_public` is not `T_full`.** The published text is redacted and the full-context
  condition (which includes private model reasoning) is not published. Results from
  `evaluate.py` are a **new measurement on published text** and must never be reported
  as the paper's 40.66 pp. See `docs/DISCLOSURES.md`.
- **282 probes and 21 atoms are permanently withheld** (evidence exists only in private
  reasoning, or agent memory). See `docs/PRIVACY_AUDIT.md`.
- **The 14-task split is a predefined evaluation split, not a secret held-out set** —
  all references are published.

## Repository layout

```
data/      probes, atoms, views (U, V), units, frozen judgements, numeric tables
scripts/   reproduce_main37.py, reproduce_all.py, evaluate.py, my_model_adapter.py
prompts/   frozen v3.2 observer/judge prompts + provenance
docs/      protocol, disclosures, privacy audit, limitations
```

## Licence and citation

See `LICENSE.txt` and `CITATION.cff`. The tasks derive from SWE-bench-style instances;
upstream projects (Django, SymPy, pytest) keep their own licences, which continue to
apply to their code fragments appearing here.
