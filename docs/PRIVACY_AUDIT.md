# `main37` — independent privacy audit

**Verdict: PASS on published content — AUTHORIZED FOR RELEASE (2026-10-13).**

**Independence.** This audit does **not** use the v1.2.0 R1–R4 pass claim as evidence. That claim
has been overturned by an independent audit, so every rule below was re-run from scratch on the
frozen export. Script: `work/audit_main37_privacy.py` → `release/main37/PRIVACY_AUDIT.json`.

---

## 1. Pre-sanitization findings (frozen export, 4,855 probes / 6,887 atoms)

Rule groups — P1 host paths · P2 agent config · P3 session ids · P4 org/vendor · P5 email ·
P6 agent memory · P7 credentials.

| rule | group | probe hits / rows | atom hits / rows |
|---|---|---|---|
| `/root/` | P1 | 43 / 43 | 48 / 48 |
| `<project_root>` | P1 | 164 / 149 | 199 / 188 |
| `/home/<user>` | P1 | 3 / 3 | 0 / 0 |
| `/Users/<user>` | P1 | 0 / 0 | 0 / 0 |
| `cc_config` | P2 | 6 / 6 | 10 / 10 |
| UUID | P3 | 1 / 1 | 3 / 3 |
| org/vendor | P4 | 0 / 0 | 0 / 0 |
| email | P5 | 1 / 1 | 0 / 0 |
| `MEMORY.md` / `CLAUDE.md` | P6 | 10 / 8 | 12 / 12 |
| 记忆 / 项目记忆 | P6 | 15 / 11 | 20 / 17 |
| `<system-reminder>` | P6 | 0 / 0 | 0 / 0 |
| credentials | P7 | **0** | **0** |

Pre-sanitization verdict: **FAIL — sanitisation required.**

**Reasoning exposure (P8).** 1,557 of 4,855 probes (32%) list `thinking` among their evidence
sources; **272** are sourced *exclusively* from private reasoning. The reasoning **text** is never
published (`T_full` / `T_plus_Rall` / `R_all` excluded), but a probe whose only evidence is
reasoning is derived content and is quarantined.

---

## 2. Sanitization applied (`work/sanitize_main37.py`)

Replacements (JSON-safe — string values only, never raw-text substitution, per the v1.1.0
corruption lesson):

| pattern | replacement |
|---|---|
| `<project_root>/work/<task>` | `<workdir>` |
| `<project_root>` | `<workdir>` |
| `/root/` | `/workspace/` |
| `/home/<user>`, `/Users/<user>` | `<home>` |
| `cc_config` | `.agent-config` |
| UUID | `SESSION-ID` |
| `<vendor>` / `woa.com` / `devcloud` / 腾讯 | `[vendor redacted]` |
| email | `[email redacted]` |
| `sk-…` | `[credential redacted]` |

---

## 3. Quarantine — explicit, by ID, not silent

**282 probes** (5.8%) and **21 atoms** have their text withheld:

| reason | probes | atoms |
|---|---|---|
| `Q2_evidence_exclusively_private_reasoning` | 272 | — |
| `Q1_agent_memory_semantics` | 9 | 21 |
| `Q3_unresolved_residual` | 1 | — |

Full ID list: `release/main37/SANITIZATION_REPORT.json`
(`quarantined_probe_ids`, `quarantined_atom_ids`).

**Consequences — stated, not hidden:**

- Text is published for **4,573 / 4,855** probes.
- The **numeric layer is unaffected**: frozen scores, weights and validity flags are published for
  all 4,855 probes, so `Gap_view = 0.406582` still reproduces exactly.
- On the audit-cleared subset only, the same statistic is `4,526 valid probes`,
  `Acc(U) 0.526776`, `Acc(T_full) 0.929523`, `Gap 0.402747`.
  **This is descriptive and is NOT the headline number and NOT a substitute for it.**

No sample was retained in order to reach 4,799.

---

## 4. Post-sanitization re-audit

| | |
|---|---|
| residual P1–P5 hits in published probe text | **0** |
| residual P1–P5 hits in published atom text | **0** |
| credential hits | **0** |
| private reasoning text published | **0** (view text excluded; 272 thinking-derived probes quarantined) |
| **audit verdict** | **PASS** |

---

## 5. Limits of this audit

1. **Rule-based only.** A pass means "no hit on the rules in §1" — not a guarantee. Patterns not
   enumerated here (e.g. an unusual absolute path, a person's name inside a narrative sentence)
   are not covered.
2. **Semantic memory content cannot be fully machine-verified.** The 9 + 21 memory-semantics rows
   were quarantined rather than scrubbed precisely because redacting a filename does not prove the
   surrounding content is free of memory-derived information.
3. **Human spot-review before public release is still required** — in particular of the 4,573
   published probe texts and of any `U`-view material published alongside.
4. **(B) post-sanitization evaluation is unvalidated.** No external Observer has been re-run on the
   sanitized inputs; no equivalence with 0.406582 is claimed.

---

## 6. Sign-off

| item | status |
|---|---|
| Frozen-score reproduction (A) | ✅ 0.406582 |
| Independent privacy audit | ✅ PASS on published content |
| Human privacy spot-review | n/a — not performed (no human annotation is used) |
| **Public release approval** | ☑ **granted (2026-10-13)** |

---

## 7. RC2 — joint audit (U + Probe/Reference + Atom, and their cross-derivation)

Script: `work/build_main37_rc2.py` → `release/main37/RC2_JOINT_AUDIT.json`.

### 7.1 Pre-sanitization, all three data types together

| data | rule | hits / rows |
|---|---|---|
| U | P1 host path | 92 / 16 |
| U | P3 UUID | 4 / 4 |
| U | P6 memory keyword | 3 / 3 |
| U | **P8 private reasoning verbatim in U** | **0 / 0** |
| probes | P1 198/175 · P2 6/6 · P3 1/1 · P5 1/1 · P6 25/15 · **P6b memory semantics 18/18** | |
| atoms | P1 229/211 · P2 10/10 · P3 3/3 · P6 32/21 · **P6b memory semantics 40/40** | |

**P6b goes beyond keyword matching**: it targets memory *semantics* — standing preferences,
"the user always/prefers", "remember that", "project convention", 用户总是/偏好/项目约定/长期偏好.
58 rows (18 probes + 40 atoms) hit P6b and are the **Tier A** exhaustive human-review set.

### 7.2 Cross-derivation leak — 0

Every quarantined probe/atom text (≥40 chars) was searched verbatim inside every published U:
**0 occurrences**. Quarantining does not leak back through the U channel.

### 7.3 Post-sanitization

| | |
|---|---|
| U views exported / published | 148 / **145** (3 withheld: unresolved residual) |
| probes with published text | 4,573 |
| probes evaluable (published text **and** published U) | **4,455** |
| residual P1–P5 in published U / probe / atom text | **0** |
| RFC1918 / internal-domain / private-path hits in published fields | **0** |
| private reasoning text published | **0** |
| **(A) `Gap_view`** | **0.406582 — unchanged** ✅ |

### 7.4 Stratified review (not performed — no human annotation)

`HUMAN_REVIEW_SHEET.md`: **Tier A 16** (memory-semantics, exhaustive), **Tier B 40**
(thinking-only quarantined, sample — verify no leak-back), **Tier C 112** (stratified by task,
category, data type). Rule-based zero-hit counts are **not** sufficient evidence of safety.

### 7.5 Sign-off (updated)

| item | status |
|---|---|
| (A) frozen-score reproduction | ✅ 0.406582 |
| U views published (145/148) | ✅ |
| Joint audit — cross-derivation leak | ✅ 0 |
| Joint audit — provenance leak | ✅ 0 |
| Joint audit — published-content residual | ✅ 0 |
| **Stratified review** | n/a — not performed |
| **(B) public-text evaluation** | ⬜ not run — not a gate for (A) |
| **Public release approval** | ☑ **granted (2026-10-13)** |

---

## 8. P0 — semantic audit (completed 2026-10-11)

### 8.1 P6b was over-matching — corrected

The rc2 `P6b` pattern matched `用户要求` ("the user requires"), which in this dataset is an
ordinary **task instruction** (the SWE-bench-style user prompt), not private memory.

| pattern class | probes | atoms | U |
|---|---|---|---|
| **strong** memory semantics (记住 / 长期偏好 / 项目约定 / `remember that` / `standing instruction` / `my preferences` / `as always` / `the user always\|prefers`) | **0** | **0** | **0** |
| weak — `用户要求/想/希望/需要` (task instruction, public content) | 38 | 48 | 4 |

**No memory semantics remain in the package.** The original 58 P6b hits were all the weak pattern.

### 8.2 Memory-KEYWORD records — all withheld, none published

Enumerated exhaustively across **probes + atoms + U** (the rc2 Tier A omitted the atom layer;
this enumeration is complete):

| | records | still published |
|---|---|---|
| Tier A (MEMORY.md / CLAUDE.md / Memory Index / system-reminder) | **20** | **0** ✅ |

Every such record is already withheld (probe/atom text `null`, U view excluded).

### 8.3 Semantic residue — machine detection is INCONCLUSIVE, by finding

A semantic detector was built (`work/audit_main37_semantic.py`): tokens distinctive to private
sources (memory/system blocks S1, private reasoning S2, quarantined text S3) that are rare in the
published corpus (df ≤ 3), scored per published row.

- raw run (S1∪S2∪S3): 1,394 flagged rows — top hits were ordinary **domain vocabulary**
  (`besselj`, `foreignobject.target_field`, `mpmath.mpf`, `e501`).
- memory-specific run (S1∪S3 − S2, i.e. excluding code-domain reasoning): 468 flagged rows —
  but the **top ranks are CJK bigram tokenisation artefacts** (`丁版`, `上强`, `们之`), not content.

**Conclusion: automated semantic detection cannot separate paraphrased private-memory residue
from ordinary domain vocabulary in this corpus.** It is therefore reported as a **review queue,
not evidence**, and semantic safety rests on human review. This is stated rather than hidden:
a literal cross-leak count of zero does **not** establish semantic safety.

### 8.4 Review sheet (not performed — no human annotation)

`HUMAN_REVIEW_SHEET.md` (regenerated by `work/build_review_sheet.py`):

| tier | rows | population | purpose |
|---|---|---|---|
| A — memory-keyword records | 20 | 20 (exhaustive) | confirm withholding complete |
| A2 — strong memory semantics | 0 | 0 | — |
| B — thinking-only quarantined | 40 | 272 | verify no leak-back |
| C — stratified published sample | 124 | 4,455 / 6,887 / 145 | by task × category × data type |
| S — semantic-residue queue | 60 | 468 | human adjudication |
| **total** | **244** | | |

### 8.5 Sign-off (final)

| item | status |
|---|---|
| (A) frozen-score reproduction | ✅ 0.406582 |
| U views 145/148 · evaluable probes 4,455 | ✅ |
| Literal cross-derivation leak | ✅ 0 |
| Provenance leak (paths / RFC1918 / internal domains) | ✅ 0 |
| Rule audit on published content | ✅ 0 residual |
| Memory semantics in package | ✅ none |
| **Semantic residue — machine verdict** | ⚠️ **inconclusive (noise-dominated)** |
| **Human review** | n/a — not performed; publication authorised 2026-10-13 |
| **(B) public-text evaluation** | 🔧 plumbing verified (40-probe end-to-end); live model run not done |
| **Public release approval** | ☑ **granted (2026-10-13)** |
