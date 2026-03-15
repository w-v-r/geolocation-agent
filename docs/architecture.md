# Architecture

## Overview

The geolocation agent is a LangGraph-based system that determines where a photograph was taken through iterative hypothesis testing. It combines vision LLM analysis with external tools (web search, reverse image search, maps, places) to progressively narrow down a location.

## Core Design

### State Machine

The agent operates as a state machine with the following nodes:

```
Start → extract_metadata → analyze_image → generate_hypotheses → investigate
                                                ↑                    ↓
                                                └── (not confident) ←┘
                                                         ↓ (confident)
                                                    produce_report → End
```

### Agent State

All data flows through a single `AgentState` that accumulates across iterations:

- `image_path` / `side_info`: Input data
- `clues`: Extracted visual observations
- `hypotheses`: Location hypotheses at various specificity levels
- `candidates`: Specific candidate locations with coordinates
- `evidence_log`: Evidence for/against each hypothesis and candidate
- `eliminated`: Ruled-out candidates with reasons
- `tool_history`: Record of every tool call made across all iterations (tool name, args, result summary, iteration number)
- `confidence`: Current best confidence score
- `iteration` / `max_iterations`: Loop control
- `messages`: LLM conversation history
- `final_answer`: Structured result when investigation concludes

### Reducer Pattern

Lists in the state use a `merge_lists` reducer that merges by ID. This means:
- Adding a new clue with a unique ID appends it
- Adding a clue with an existing ID updates it
- State never grows unboundedly with duplicates

The `tool_history` field uses an `append_lists` reducer (simple concatenation) since tool calls are always unique and should accumulate without deduplication.

## Node Descriptions

### extract_metadata
Runs EXIF extraction on the input image. If GPS coordinates are found, they are recorded as high-confidence clues. Camera model and timestamp are also captured. This is the only deterministic (no LLM) node.

### analyze_image
Sends the image to the vision LLM with the analysis prompt. The LLM can use image tools (crop, zoom, adjust) to inspect details. It records observations as clues via the evidence tracker.

**Minimum clue enforcement**: If the LLM extracts fewer than 3 clues in the initial pass, the node automatically retries with a more directive prompt that lists specific categories to inspect (vegetation, architecture, furniture, terrain, text, etc.). This prevents the "0 clues → garbage hypotheses" failure mode observed in testing.

### generate_hypotheses
The LLM reviews all accumulated clues and evidence to propose or refine hypotheses. Hypotheses are structured with level (country/region/city/venue), confidence, and supporting clue IDs. Sub-hypotheses are encouraged.

**Staleness detection**: Each hypothesis tracks an `iterations_without_evidence` counter. Hypotheses that have persisted for 2+ iterations without new supporting evidence are flagged as STALE in the state summary and the LLM is explicitly told to demote or replace them.

**Diversity enforcement**: If all active hypotheses target the same region and this is not the first iteration, the LLM is prompted to propose at least one alternative from a different country or continent. This prevents the "hypothesis tunneling" failure where the agent locks into one region and never explores alternatives.

### investigate
The core investigation loop. The LLM has access to ALL tools and decides which to use based on current hypotheses and evidence gaps. This includes:
- Web search (Tavily)
- Reverse image search (SerpAPI Google Lens)
- Places lookup (Google Maps Places)
- Satellite imagery (Google Maps Static API)
- Street View (Google Street View)
- Geocoding / reverse geocoding
- Evidence tracking

### should_continue (conditional edge)
Checks whether to loop back or proceed to report:
- If confidence >= threshold (default 0.8): report
- If iterations >= max (default 10): report
- Otherwise: loop back to generate_hypotheses

**Evidence recording enforcement**: After each tool round, if the LLM used search or maps tools but did not call `add_evidence` or `add_candidate`, a reminder message is injected into the conversation prompting it to record results before continuing. This prevents the "0 evidence, 0 candidates" failure mode.

**Tool history tracking**: Every tool call (name, args, result summary, iteration) is recorded in `tool_history` and included in the state summary. This gives the LLM visibility into what has already been tried, preventing repetitive searches.

### produce_report
Generates the final structured answer with best candidate, alternatives, confidence levels, key evidence, and a reasoning narrative.

**Report grounding**: The report prompt includes explicit grounding constraints derived from the actual state: the count of candidates and evidence entries. If there are 0 candidates or 0 evidence, the prompt forbids fabricating venues or claiming tool results that don't exist. This prevents hallucinated reports.

## LLM Provider Architecture

The system supports three LLM providers via a factory pattern:
- **OpenAI** (default): GPT-4o with vision
- **Anthropic**: Claude Sonnet with vision
- **Google**: Gemini 2.0 Flash with vision

Provider selection is controlled by the `LLM_PROVIDER` environment variable. All providers must support multimodal (vision) input since the agent needs to analyze photographs.

## Tool Architecture

Tools are implemented as LangChain `@tool` decorated functions. They are grouped by capability:

1. **Image Tools**: Local image processing (Pillow-based)
2. **Search Tools**: External web/image search APIs
3. **Maps Tools**: Google Maps Platform APIs
4. **Places Tools**: Google Maps Places API
5. **Evidence Tracker**: Pure logic, no external API calls

Tool sets are composed for each node:
- `ANALYSIS_TOOLS`: Image tools + add_clue (for the analyze node)
- `ALL_TOOLS`: Everything (for the investigate node)

### Image Path Injection

Image tools (`crop_image`, `zoom_image`, `adjust_image`, `extract_exif`, `reverse_image_search`, `reverse_image_search_region`) require a local file path. Because the LLM does not reliably produce the correct path, the `_inject_image_path` helper in `nodes.py` intercepts tool calls and overrides the `image_path` argument with the real path from agent state. The path is resolved to an absolute path at the start of the investigation in `run_investigation()`.

## Clue Display in State Summary

The state summary groups clues by investigative role to help the agent use them effectively:

- **Region-narrowing clues** (vegetation, architecture, terrain, weather_lighting, language, metadata, other): Use for narrowing the geographic region and constructing search queries (e.g. "Moreton Bay Fig NSW winery").
- **Venue-comparison clues** (interior, text, signage, furniture, etc.): Use when comparing candidate locations to the photo (e.g. white chairs, lawn style, barrel placement).

Each clue displays: `id` (for hypothesis references), `category`, `description`, `confidence`, `region_hint` (when present), and `raw_value` (when present, e.g. OCR text). This ensures the agent has full access to clue data for search construction and verification.

## Progress Logging

Each node prints timestamped progress messages to stderr so the user can monitor the investigation in real time. Messages include phase transitions, tool calls with their arguments, extracted clues, hypotheses, candidates, evidence, and confidence updates.
