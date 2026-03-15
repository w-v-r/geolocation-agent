# Design Decisions

## 1. LangGraph Over Custom Agent Loop

**Decision**: Use LangGraph as the agent framework.

**Rationale**: The geolocation investigation has a natural state-machine structure (extract -> hypothesize -> investigate -> decide -> report/loop). LangGraph's `StateGraph` maps directly to this. Key benefits:
- Conditional edges make the "should I keep investigating?" decision clean
- State reducers handle merging evidence across iterations
- The graph is inspectable and debuggable
- Built-in support for LangChain tool binding

**Alternative considered**: Custom while loop. Simpler but loses the structured state management and conditional branching that LangGraph provides for free.

## 2. Tavily for Web Search, SerpAPI for Reverse Image Search

**Decision**: Split search across two providers.

**Rationale**: Tavily excels at web search with its "advanced" search depth that provides rich content snippets and relevance scoring. SerpAPI provides reliable programmatic access to Google Lens for reverse image search. But really this is about balancing free queries. Each platform gives a number of queries at the free tier. 

**Trade-off**: Two API keys to manage instead of one.

## 3. Geospatial Verification Inside the Investigation Loop

**Decision**: Maps, satellite, and Street View tools are available during investigation, not as a separate "verification" phase.

**Rationale**: In practice, pulling up Street View to check a hypothesis is just another investigation technique. Separating it into a post-investigation phase would:
- Artificially delay useful verification actions
- Force the agent to reach an arbitrary confidence threshold before it can visually confirm
- Not match how a human would actually investigate (you'd check the map as soon as you have a plausible candidate)

## 4. Evidence Tracker as LangChain Tools

**Decision**: Evidence tracking functions (add_clue, add_hypothesis, etc.) are implemented as `@tool` decorated functions that the LLM calls.

**Rationale**: This lets the LLM decide when and what to record, rather than us parsing its output. The LLM calls `add_clue` when it spots something, `add_hypothesis` when it forms a theory, and `add_evidence` when it gathers information. The tool returns a JSON object with an assigned ID, which gets collected into the agent state.

**Trade-off**: The LLM might not always call the tracking tools consistently. The system prompt strongly encourages recording all observations.

## 5. Multi-Provider LLM Support via Factory Pattern

**Decision**: Support OpenAI, Anthropic, and Google Gemini through a `get_llm()` factory.

**Rationale**: Different providers have different strengths for vision tasks. OpenAI GPT-4o is the default, but users may prefer Claude's reasoning or Gemini's speed. The factory pattern keeps provider-specific code isolated and makes switching a single environment variable change.

## 6. State Reducers with ID-Based Merging

**Decision**: List fields in AgentState use a `merge_lists` reducer that merges by `id` field.

**Rationale**: As the agent loops through investigation iterations, it accumulates clues, hypotheses, and evidence. Simple list append would create duplicates if a node re-records existing items. ID-based merging means:
- New items are appended
- Updated items (same ID) are replaced
- No duplicate data accumulates

## 7. Image Upload for Reverse Image Search

**Decision**: Upload images to a temporary hosting service (imgbb) for reverse image search, with base64 data URI fallback.

**Rationale**: SerpAPI's Google Lens requires a publicly accessible URL. Local file paths don't work. Options considered:
- imgbb anonymous upload (chosen): free, no API key needed, images auto-expire
- Base64 data URI (fallback): works but may hit URL length limits
- S3 or similar (rejected): requires additional AWS setup

## 8. Confidence Thresholds as Configuration

**Decision**: Confidence threshold (0.8) and max iterations (10) are configurable via `Settings`.

**Rationale**: Different use cases need different stopping criteria. A casual investigation might accept 0.6 confidence after 3 iterations. A thorough forensic analysis might require 0.95 and allow 20 iterations. Making these configurable avoids hardcoded assumptions.

## 9. Tools Return JSON Strings

**Decision**: All tools return JSON strings rather than Pydantic models.

**Rationale**: LangChain tools must return strings (or simple types) to be compatible with the LLM tool-calling interface. The LLM receives the JSON string as context and can parse the relevant fields. The Pydantic models exist for documentation and validation, but the tool interface stays simple.

## 10. Programmatic Enforcement Over Prompt-Only Guidance

**Decision**: Use code-level checks (clue count threshold, evidence recording reminders, hypothesis staleness detection) rather than relying solely on prompt instructions.

**Rationale**: Testing revealed that the LLM frequently ignores prompt-level instructions about recording evidence, maintaining hypothesis diversity, and extracting sufficient clues. The system prompt already contained rules like "do not spend more than 2 iterations on a hypothesis with no progress" and "always record evidence in the evidence tracker" -- but the LLM violated both consistently across multiple runs. Programmatic enforcement catches these violations and injects corrective messages. This is a belt-and-suspenders approach: the prompts guide the LLM's intent, and the code enforces the minimum standard when the LLM fails to comply.

**Trade-off**: More complex node code. The investigate node now tracks which tools were used per round and whether evidence was recorded. The hypothesize node computes staleness scores. These add ~50 lines of logic but address failure modes that were 100% reproducible.

## 11. Tool History as Shared State

**Decision**: Track all tool calls (name, args, result summary, iteration) in a `tool_history` state field and include the last 15 entries in every state summary.

**Rationale**: Without tool history, each LLM invocation within a new iteration has no memory of what was tried before. In testing, the exact same web search query ("coastal winery with large tree and outdoor seating Provence") was repeated across 10 iterations. Tool history gives the LLM visibility into past attempts so it can vary its approach. The `append_lists` reducer (not `merge_lists`) is used since tool calls don't have natural IDs to merge on and should always accumulate.

**Trade-off**: Adds tokens to the state summary. Capped at last 15 entries to limit context growth.

## 12. Minimum Clue Threshold with Retry

**Decision**: If the analyze phase extracts fewer than 3 clues, retry with a more directive prompt.

**Rationale**: In one test run, the LLM zoomed and cropped the image but never called `add_clue`, producing 0 clues. The entire downstream investigation was built on ungrounded guesses. The retry prompt lists specific categories to inspect (vegetation species, chair styles, building materials, barrels/equipment, terrain) which gives the LLM concrete targets. Three was chosen as the minimum because any photograph with enough detail to geolocate should yield at least 3 distinct observations.

**Alternative considered**: Making the number configurable. Deferred -- 3 is a safe floor for now.

## 13. Report Grounding Constraints

**Decision**: The report prompt includes explicit counts of candidates and evidence from the actual state, with rules forbidding fabrication when counts are zero.

**Rationale**: In testing, the report phase hallucinated evidence -- claiming "Reverse image searches yielded matches with Chateau de Berne" when every reverse search had failed. The LLM received the state summary (showing 0 candidates, 0 evidence) but ignored it. Adding hard constraints like "You have 0 candidates. Do NOT fabricate a venue name." directly in the prompt reduces (but does not eliminate) hallucination in the report.
