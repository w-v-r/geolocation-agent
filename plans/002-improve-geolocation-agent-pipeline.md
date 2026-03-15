# Improve Geolocation Agent Pipeline

## Overview

Address the systematic failures observed across two training runs (TRAINING_DATA/example1) by fixing hypothesis tunneling, evidence tracker non-usage, repetitive tool calls, broken reverse image search, and report hallucination.

## Diagnosis: What Went Wrong

Comparing the two traces against the correct answer (Crooked River Estate, Gerringong, NSW, Australia):

### Trace 1 (5 iterations) -- roughly right region, no venue

- Correctly identified "Moreton Bay Fig" and hypothesized NSW/QLD coast
- But: 0 candidates registered, 0 evidence recorded, same web searches repeated every iteration
- Reverse image search broken throughout (100% failure rate)
- Never identified wine barrels, Adirondack chairs, or estate-style property

### Trace 2 (10 iterations) -- completely wrong

- Analyze phase extracted **0 clues** (only zoomed and ran EXIF)
- With no clues to anchor it, LLM guessed "France" at 0.2 confidence
- Locked into France for all 10 iterations despite finding zero supporting evidence
- Hypotheses duplicated every iteration (3 -> 6 -> 12 -> 18 -> ... -> 49) -- all identical
- Report **hallucinated evidence**: claimed reverse image search matched Chateau de Berne (it didn't -- every reverse search failed)
- Report claimed "Confident" despite 0 candidates and 0 evidence in the tracker

## Root Causes (6 problems)

### P1. Analyze phase can produce 0 clues

In trace 2, the LLM zoomed/cropped but never called `add_clue`. The entire investigation was built on nothing.

**Fix**: Minimum clue threshold check in `analyze_image` with retry and forceful prompt.

### P2. Evidence tracker tools never used during investigation

`add_candidate` and `add_evidence` were never called. Confidence stayed at 0%, report had nothing to reference.

**Fix**: Explicit prompt requirements + post-round reminder injection when search tools used without recording evidence.

### P3. Hypothesis tunneling -- no diversity enforcement

"Provence, France" at 0.2 confidence persisted for 10 iterations with zero supporting evidence.

**Fix**: Staleness detection, diversity enforcement (maintain 2+ competing region hypotheses).

### P4. Repetitive tool calls across iterations

Same searches repeated every iteration. LLM had no memory of past tool calls.

**Fix**: `tool_history` state field + include in state summary.

### P5. Reverse image search 100% broken

SerpAPI rejects data URI fallback. Infrastructure issue.

**Fix**: Error handling so agent doesn't crash; prompt to vary strategy when reverse search fails.

### P6. Report hallucination

Report fabricated evidence and confidence levels despite 0 candidates and 0 evidence.

**Fix**: Grounding constraints in report prompt with actual state counts.

## Implementation Summary

### 1. State ([state.py](src/geolocation_agent/state.py))

- Added `tool_history: list[dict]` with `append_lists` reducer
- Each entry: `{id, tool_name, args_summary, result_summary, iteration}`

### 2. Analyze phase ([nodes.py](src/geolocation_agent/nodes.py))

- After tool loop, check if fewer than 3 clues extracted
- If so, retry with directive prompt listing specific categories to inspect

### 3. Investigate phase ([nodes.py](src/geolocation_agent/nodes.py))

- Track tool calls in `tool_history`
- After each round: if search/maps used but no evidence recorded, inject reminder message
- Wrap tool invocations in try/except so individual failures don't crash the agent

### 4. Hypothesize phase ([nodes.py](src/geolocation_agent/nodes.py))

- Compute `iterations_without_evidence` per hypothesis
- Flag stale hypotheses (2+ iterations) in prompt
- Require at least 2 competing region-level hypotheses when all target same region

### 5. Prompts ([prompts.py](src/geolocation_agent/prompts.py))

- INVESTIGATE: Explicit add_evidence/add_candidate requirements, vary search strategy
- REPORT: Grounding constraints, forbid fabrication when 0 candidates/evidence
- HYPOTHESIZE: Diversity requirement, no duplicate hypotheses
- ANALYZE: Stronger guidance on clue categories

### 6. State summary ([nodes.py](src/geolocation_agent/nodes.py))

- Added "Previous Tool Calls" section
- Enriched clue display: id, region_hint, raw_value, grouped by broad vs specific (region-narrowing vs venue-comparison)

### 7. Documentation

- [architecture.md](docs/architecture.md): Tool history, analyze retry, evidence enforcement, staleness, report grounding
- [limitations.md](docs/limitations.md): Marked fixed/mitigated issues
- [decisions.md](docs/decisions.md): Programmatic enforcement, tool history, minimum clue threshold, report grounding

## Clue Display Enhancement (follow-up)

Enriched the clue section in `_get_state_summary` to:

- Show clue `id` so hypotheses can reference via `supporting_clue_ids`
- Show `region_hint` when present (e.g. "Australia", "subtropical")
- Show `raw_value` when present (OCR text, EXIF values)
- Group clues by role: **Region-narrowing** (vegetation, architecture, terrain) vs **Venue-comparison** (interior, text, signage, furniture)
- Add usage guidance: "Use BROAD clues for region narrowing and search queries. Use SPECIFIC clues for venue comparison and verification."
