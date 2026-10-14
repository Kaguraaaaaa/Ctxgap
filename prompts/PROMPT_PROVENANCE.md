# Observer / Judge prompt provenance

- **PROMPT_VERSION = v3.2**
- Source module: `analysis/prompts_v3.py`, imported by `analysis/measure_v3.py`,
  which produced the frozen main-measurement scores.
- `observer_system.txt` = `OBS_SYSTEM`
- `observer_prompt.txt` = `OBS_PROBES` (template; fields `{intro}`, `{material}`, `{questions}`)
- `judge_prompt.txt` = `JUDGE_ANSWERS`
- `view_intro.json` = `VIEW_INTRO` (per-view intro text)

Earlier drafts mistakenly shipped a fragment taken from `analysis/a2v2_build.py`
(the A2 v2 experiment), which is NOT the main-measurement prompt. Replaced.
