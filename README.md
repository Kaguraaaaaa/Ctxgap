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
python3 scripts/reproduce_all.py        # the paper's headline numbers + CIs
python3 scripts/reproduce_main37.py     # headline again, then the public-text subset
```

**`reproduce_all.py` is the one that reproduces the paper's numbers.** From the
frozen per-probe scores it recomputes:

| Result | Value |
|---|---|
| Acc(U) | 52.05% |
| Acc(T_full) | 92.71% |
| Acc(Actor) | 93.64% |
| **Context Gap** | **40.66 pp** (95% CI [0.373, 0.438]) |
| Successful-task gap (30 tasks, final checkpoint) | 34.79 pp |
| Cross-harness gaps (task-equal) | CC 0.4070 / Pi 0.3903 / DSH 0.4898 |
| Equal-total-length rewrite | B-A +8.29 pp, C-A +8.50 pp, C-B +0.20 pp (n.s.) |

**`reproduce_main37.py` prints two things, in this order.** First it recomputes the
*full frozen headline* (4,855 probes / 4,799 valid → Acc(U) 52.05%, Acc(T_full)
92.71%, Gap 40.66 pp — the same headline as `reproduce_all.py`, without the CIs).
Then, as a second and separate block, it recomputes the *text-publishable subset*
(4,526 valid probes; 282 probes withheld as not publishable → Acc(U) 52.68%,
Acc(T_full) 92.95%, Gap 40.27 pp). That second number is **descriptive**: it is not
the headline and must not be substituted for it.

### B. Evaluate your own model

```bash
export CTXGAP_EVAL_CMD='python3 scripts/my_model_adapter.py'
export CTXGAP_EVAL_MODEL='your-model-name'
python3 scripts/evaluate.py --view U
python3 scripts/evaluate.py --view V
```

You supply an adapter that reads a prompt on stdin and prints the answer to stdout.
The requested `--model` is also exported as `CTXGAP_EVAL_MODEL` to every child
process, so an adapter without a `{model}` placeholder still calls the model you
asked for.

Both evaluation entry points use the **same** accuracy convention:
**primary = probe-weighted mean** with the frozen weight
`w(probe) = #atoms(importance ≥ 2, category c) / #probes(category c)`;
the unweighted mean is printed alongside as a secondary figure only. Each also
recomputes the frozen baseline on *exactly the probe set it evaluated*, so the
reported `delta_acc_U` compares like with like.

`evaluate.py` refuses to let failures inflate coverage: the denominator is fixed
before any model call, a unit whose Observer or Judge call fails is still recorded,
and the Judge may only score questions the Observer actually answered.
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

| Material | Licence |
|---|---|
| CTXGAP-original benchmark data, Probes and References | **CC BY 4.0** |
| CTXGAP-original evaluation and reproduction code | **MIT** |
| Third-party code fragments (Django, SymPy, pytest, SWE-bench) | their original licences |

See `LICENSE.txt` for the full text and `CITATION.cff` for how to cite.
