# `main37` — provenance

## 1. Chain of derivation

```
runs/<37 run ids>/measure_v3/k{1..4}/{probes.json, atoms.json, judge/*.json}
        │
        │  work/build_main37_export.py        (read-only, zero API)
        ▼
release/main37/_pre_sanitize/{units,atoms,probes,judgements}.jsonl
   + closeout_verification.json   (4,855 / 4,799 / 0.406581677 — frozen baseline close-out)
   + provenance_files.json        (sha256 of all 7,711 source files)
        │
        ├── work/audit_main37_privacy.py      → release/main37/PRIVACY_AUDIT.json   (FAIL: needs scrub)
        │
        │  work/sanitize_main37.py            (numeric layer full, text layer cleared only)
        ▼
release/public/main37/{units,atoms,probes,judgements}.jsonl + this README
        │
        ├── reproduce_main37.py               → 4,855 / 4,799 / 0.406582  ✅
        └── SANITIZATION_REPORT.json          → post-scrub residual 0 → PASS
```

## 2. The 37 runs

Taken from `reports/e1_semantic/atoms_failure.csv` (column `run`) — the frozen main-measurement
sample. 32 × `p2_` + 5 × `pilot_`; 148 units = 37 runs × 4 checkpoints; no run has more than
one trajectory.

All 37 are already present in the v1.2.0 public package as trajectories — **no new trajectory
data is introduced by this package.**

## 3. Source-file hashes

`release/main37/provenance_files.json` records `path` + `sha256` for **every** source file read:

| kind | count |
|---|---|
| `measure_v3/k*/probes.json` | 148 |
| `measure_v3/k*/atoms.json` | 148 |
| `measure_v3/k*/judge/*.json` | 7,415 |
| **total** | **7,711** |

Every exported row additionally carries a `src` field naming the file it came from.

## 4. Reconciliation against v1.2.0 (`release/main37/reconciliation_v120.json`)

Why the headline was **not** reproducible from v1.2.0:

| | |
|---|---|
| frozen probes | 4,855 |
| present in v1.2.0 | 4,392 |
| **absent from v1.2.0** | **463** ← reconciled probe-by-probe, by ID |
| matches the 463 expectation | ✅ |
| v1.2.0 probes not in the frozen sample | 0 |
| absent probes lacking frozen scores | 0 |
| shared probes whose text differs | 173 |

- The 463 are spread over k1–k4 (79 / 113 / 128 / 143) and 10 categories; each has a
  non-empty reference and full judge coverage, i.e. **they are complete measured probes that
  the v1.2.0 export dropped**, not privacy removals.
- The 173 text differences are **v1.2.0 sanitization artifacts** (e.g.
  `<project_root>/work/django__django-14315` → `<workdir>`, `/home/<user>/.pgpass` → `<home>/.pgpass`),
  not content drift. They confirm that frozen text does contain host paths — which is why this
  package runs its own scrubber rather than trusting v1.2.0.

## 5. What is *not* derivable from this package

- The **text** of `T_full` / `T_plus_Rall` / `R_all` (private reasoning) — excluded by policy.
- Observer/judge **raw answers** — only labels and scores are published.
- Any re-run of the measurement pipeline: this package is a **reproduction artifact**, not a
  re-executable pipeline.

---

## 6. RC2 — U view

**`U` = `runs/<run>/views/k<N>/tier_reports_all.md`** — confirmed from v1.2.0
`normalized/views.jsonl`, which maps `name: U` → `source_path: views/k1/tier_reports_all.md`.
(The file on disk is named `tier_reports_all.md`; v1.2.0 published it as `materials/…__U.md`.)

- 148 units = 37 runs × 4 checkpoints; **148/148 found, 0 missing**.
- Checkpoint alignment preserved: one U per `(run, k)`, keyed `unit_id = <run>::k<k>`.
- **Frozen research inputs are unchanged** — only the public copy is scrubbed;
  `runs/**` is read-only throughout.
- Source hashes appended to `release/main37/provenance_files.json`
  (7,711 measurement files + 148 U files = **7,859**).

## 7. Provenance-leak check

Published fields (`src`, `text`, `question`, `reference`) were scanned for identifying values:
private absolute paths, RFC1918 / CGNAT addresses, internal domains (`*.woa|corp|internal|
intranet|local`). **Result: 0 hits.**

Loopback and bind addresses (`127.0.0.1`, `0.0.0.0`) are **kept deliberately** — they are
dev-server bind addresses with no identifying value and are part of the agent's observable
behaviour. The 7,711 + 148 source-file hashes are retained: they carry no path or machine
identity beyond the relative `runs/…` location.
