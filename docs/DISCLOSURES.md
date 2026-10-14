# Release disclosures

## 1. T_public != T_full (the 40.7 pp number)

The headline **Gap = 0.4066 (40.7 pp)** comes from the paper's ORIGINAL frozen measurement,
where the full-context condition is `T_full` (the complete execution context, which includes
private model reasoning that is NOT published).

This package publishes `U` (the cumulative agent report) and `V` (terminal scrollback), and
`T_public` where applicable. **The public text is processed (redacted / filtered), so it is not
input-equivalent to the original `T_full`.**

Therefore:
- Recomputing the frozen per-probe scores on this package reproduces the paper's numbers.
  That is a **cached-score reproduction**.
- Running `evaluate.py` on the public text is a **new measurement**. Its result is NOT expected
  to equal 0.4066, and must never be reported as if it were.

These two must always be reported separately, never merged into one number.

## 2. The 23 / 14 task split

The original protocol reserved a 14-task held-out split. Because this release publishes the
Probe questions **and** Reference answers for all tasks, those 14 tasks can no longer function
as a secret held-out test set.

They are therefore described as a **predefined evaluation split**, not a held-out/secret test
set. Any future use of CTXGAP for model selection should state this explicitly.
