# Limitations

Limitations discovered during development, testing, and live API validation, plus broader constraints that affect the agent's effectiveness.

---

## Discovered During Development

### 1. Image Upload for Reverse Image Search Is Fragile

`_upload_image_for_search` attempts to upload to imgbb using a placeholder API key (`00000000000000000000000000000000`). This will fail against the real imgbb API. When it fails, the fallback is a `data:image/jpeg;base64,...` data URI, which may exceed URL length limits that SerpAPI or Google Lens impose. In practice, this means reverse image search on local images may silently degrade or fail unless a real image hosting solution is configured.

**Impact**: `reverse_image_search` and `reverse_image_search_region` may not work reliably on local files.

### 2. Google Lens Rejects Certain Image URLs

During live testing, we found that Wikipedia thumbnail URLs (`upload.wikimedia.org/wikipedia/commons/thumb/...`) return zero results from Google Lens via SerpAPI. The same image served from Unsplash returned 59 visual matches. This appears to be a Google Lens restriction on certain domains or URL redirect patterns.

**Impact**: The agent cannot assume any arbitrary public URL will work for reverse image search. URL source matters.

### 3. SerpAPI Response Structure Is Inconsistent

The Google Lens response schema varies across queries:

- `knowledge_graph` can be a list, a dict, or absent entirely
- `visual_matches` can be empty even when `related_content` correctly identifies the subject
- `related_content` (which provides a direct textual identification like "Sydney Opera House") was not documented prominently and was only discovered during live testing
- `ai_overview` contains an opaque page token that requires a second API call to resolve

We updated `_run_google_lens` to extract `related_content`, but other undocumented fields may exist that we are not capturing.

**Impact**: The reverse image search tool may miss useful information from SerpAPI responses as the schema evolves.

### 4. No OCR Tool Implemented

The system prompt and the `ANALYZE_PROMPT` reference OCR ("Use OCR if you see text that is hard to read"), and the `image_tools.py` module docstring mentions OCR. However, no OCR tool actually exists. The agent relies entirely on the LLM's vision capability to read text in images.

**Impact**: Text that is too small, blurry, or at an oblique angle for the LLM's vision model may go unread. A dedicated OCR tool (e.g. Tesseract, EasyOCR, or a cloud OCR API) would improve text extraction from challenging images.

### 5. ~~Image Path Not Passed to Image Tools~~ (FIXED)

When the LLM called image tools (`crop_image`, `zoom_image`, `adjust_image`, `extract_exif`, `reverse_image_search`, `reverse_image_search_region`), it did not know the actual file path of the image under investigation. It would pass placeholder values like `'image_path'` or `'path_to_image'`, causing `FileNotFoundError` crashes during the analyze and investigate phases.

**Fix applied**: The `_inject_image_path` helper in `nodes.py` now intercepts all tool calls that accept an `image_path` parameter and overrides them with the real path from agent state. The image path is also resolved to an absolute path at the start of the investigation and communicated to the LLM in the prompt text as a belt-and-suspenders measure.

### 6. Evidence Tracker State Integration Is Fragile

The evidence tracker tools (`add_clue`, `add_hypothesis`, etc.) return JSON strings. The node code in `nodes.py` then parses these results and routes them into the correct state field based on ID prefix (`clue_`, `hyp_`, `cand_`, `ev_`). This means:

- If the LLM calls an evidence tracker tool but the node code doesn't match the ID prefix, the data is silently lost
- The `eliminate_candidate` and `update_confidence` tools return action records that must be matched against existing candidates by ID -- if the candidate ID doesn't exist in the current state, the operation is a no-op
- There is no validation that the LLM is providing valid references (e.g. a hypothesis ID that actually exists)

**Impact**: Investigation state can become inconsistent if the LLM produces malformed tool calls or references non-existent IDs.

### 6. Google Maps Places Coverage Is Sparse in Rural/Niche Areas

A live text search for "wineries near Berry NSW Australia" returned only 2 results (Silos Estate and Two Figs Winery), despite there being many more wineries in the Shoalhaven region. The Google Maps Places API has known coverage gaps for niche businesses, especially outside major cities.

**Impact**: The agent may fail to find the correct candidate location when it is a small business, a private property, or in a region with limited Google Maps coverage.

---

## Tool-Level Limitations

### 7. Street View Coverage Gaps

Google Street View is available at major roads and tourist areas, but large parts of the world have no coverage at all. Rural roads, private property, internal paths, and many countries (notably most of Africa, Central Asia, and parts of China) are not covered. Even where coverage exists, it may be years out of date.

**Impact**: The agent cannot use Street View as a verification tool for locations outside covered areas. It currently returns an error message when coverage is unavailable, but does not suggest alternative verification strategies.

### 8. Satellite Imagery Comparison Is Extremely Difficult for LLMs

The `get_satellite_image` tool returns a top-down satellite view. Comparing this to a ground-level photograph requires the LLM to mentally reconstruct the 3D scene from a 2D overhead perspective. Current vision models are not reliably capable of this spatial reasoning.

**Impact**: Satellite imagery is most useful for verifying terrain type, coastline shape, or vegetation patterns at a macro level. It is unreliable for verifying specific buildings or venues from ground-level photos.

### 9. No Image Comparison Tool

The agent can retrieve satellite imagery or Street View images, but has no dedicated tool for side-by-side image comparison. It relies on the LLM holding both images in context and reasoning about their similarity. This is limited by:

- Context window constraints (two large base64 images consume significant tokens)
- LLM spatial reasoning capability
- Loss of detail through JPEG compression and resizing

**Impact**: Visual verification is the most important step in geolocation, and it depends entirely on the LLM's vision capability rather than a structured comparison approach.

### 10. Tavily Search Depth Is Limited

While Tavily's "advanced" search depth provides richer results than basic mode, it still returns relatively short content snippets. For geolocation, we often need to find specific details buried deep in a webpage (e.g. a winery's exact address, a description of their grounds, mentions of nearby landmarks). Tavily may surface the right page but not extract the specific detail needed.

**Impact**: The agent may need multiple follow-up searches to extract details that a human would find by scrolling a single webpage.

---

## Architectural Limitations

### 11. Context Window Accumulation

Each investigation iteration adds messages to the LangGraph state: system prompt, image (as base64), state summary, LLM responses, and tool results. After several iterations, the accumulated context can approach or exceed the LLM's context window. The current architecture does not implement:

- Message pruning or summarisation between iterations
- Selective image re-inclusion (the full image is re-sent every time the `investigate` node runs)
- Token budget tracking

**Impact**: Investigations with many iterations (6+) may hit context limits, causing truncation or API errors, especially with lower-context models.

### 12. Single Image Input Only

The agent is designed to investigate a single photograph. Many real geolocation scenarios involve multiple photos from the same location (different angles, different zoom levels, interior and exterior shots). The current architecture has no mechanism to:

- Accept multiple images as input
- Cross-reference clues across images
- Use one image's clues to guide analysis of another

**Impact**: Users with multiple related photos must run separate investigations and mentally correlate the results.

### 13. No Investigation Persistence or Resume

The investigation state exists only in memory during a single run. If the process is interrupted, all accumulated clues, hypotheses, and evidence are lost. There is no:

- Checkpoint/save mechanism
- Ability to resume from a previous state
- Investigation history across runs

**Impact**: Long investigations (many iterations, expensive API calls) cannot be recovered if interrupted.

### 14. Hard-Coded Tool Round Limits

Each node has a fixed maximum number of tool-calling rounds:

- `analyze_image`: 5 rounds
- `generate_hypotheses`: 5 rounds
- `investigate`: 8 rounds

These limits exist to prevent runaway API costs, but they are not adaptive. A complex image with many details may need more than 5 analysis rounds. A straightforward investigation may waste iterations on the 8-round cap.

**Impact**: The agent may be cut off mid-investigation or waste resources on rounds that add no value. These limits should ideally be configurable or adaptive.

### 15. No Parallel Tool Execution

Within each node, tool calls are executed sequentially. If the LLM requests multiple independent tool calls in a single response (e.g. three different web searches), they are executed one at a time. LangGraph supports parallel tool execution, but the current node implementations do not use it.

**Impact**: Investigation rounds are slower than necessary. Parallel execution could significantly reduce wall-clock time per iteration.

### 16. No Cost Tracking or Budget Control

The agent makes LLM calls (vision model, with large base64 images) and external API calls (Tavily, SerpAPI, Google Maps) with no tracking of:

- Token usage per iteration
- API call counts and associated costs
- Budget limits or spend alerts

**Impact**: A 10-iteration investigation with aggressive tool use could consume significant API credits with no visibility or control mechanism.

---

## Geolocation-Specific Limitations

### 17. EXIF Data Is Almost Always Stripped

Modern social media platforms, messaging apps, and image sharing services strip EXIF metadata (including GPS coordinates) before serving images. The `extract_exif` tool will return useful data only for photos taken directly from a camera or phone and not shared through any platform.

**Impact**: The GPS "shortcut" (finding exact coordinates in EXIF) will rarely work in practice. The agent should not rely on it.

### 18. Night, Indoor, and Featureless Photos

The agent's effectiveness drops substantially for:

- **Night photos**: shadows, sun angle, and vegetation are invisible; only artificial lighting and signage remain useful
- **Indoor photos**: architectural clues are limited to furniture style, decor, and any visible text; vegetation and terrain are absent
- **Featureless landscapes**: desert, open ocean, dense forest, or snow-covered terrain with no distinctive landmarks

**Impact**: Some photos are genuinely ungeolocatable. The agent should recognise this and report low confidence rather than forcing a guess.

### 19. Temporal Mismatch

Google Street View and satellite imagery have capture dates that may differ from the photo being investigated by months or years. Buildings may have been constructed, demolished, or renovated. Vegetation changes seasonally. Signs and businesses change.

**Impact**: The agent may fail to match a location because the reference imagery is outdated, or incorrectly reject a valid candidate because it looks different at a different point in time.

### 20. Language and Script Barriers

The LLM's ability to read text in images varies by script. Latin script text is reliably extracted; Cyrillic, Arabic, CJK, Devanagari, and other scripts may be read with lower accuracy. This affects:

- Sign and menu reading
- License plate identification
- Language-based region narrowing

**Impact**: Geolocation accuracy is likely lower for photos from regions using non-Latin scripts, unless a dedicated OCR tool for that script is added.

### 21. LLM Hallucination and Overconfidence

Vision LLMs can "see" things that are not present, or interpret ambiguous features with false certainty. Common failure modes:

- Confidently identifying a generic building as a specific landmark
- Misreading partial text (e.g. reading "BURG" and concluding "Hamburg")
- Treating a single weak clue as strong evidence (e.g. "palm trees therefore California")
- Generating plausible-sounding but fabricated place names

The system prompt explicitly warns against these behaviours, but the LLM may not always comply.

**Impact**: The confidence levels reported by the agent may not be well-calibrated. External validation of results is advisable.

### 22. No Ground Truth Evaluation Framework

There is no automated way to evaluate the agent's accuracy against a benchmark dataset. Geolocation research commonly uses datasets like GeoGuessr or IM2GPS for evaluation, measuring distance error between predicted and actual coordinates. The current project has:

- No benchmark dataset
- No scoring metric (e.g. median distance error, percentage within 1km/25km/200km)
- No regression testing against known-location images

**Impact**: We cannot systematically measure whether changes to prompts, tools, or architecture improve or degrade accuracy.

---

## API and Cost Constraints

### 23. Rate Limits

| Service | Known Limits |
|---------|-------------|
| SerpAPI | 100 searches/month on free tier |
| Tavily | 1,000 searches/month on free tier |
| Google Maps Platform | $200/month free credit; individual API limits vary |
| OpenAI GPT-4o | Varies by tier; vision requests are token-heavy |

A single investigation with 10 iterations and aggressive tool use could consume 20-50 SerpAPI searches, 10-30 Tavily searches, and 15-40 Google Maps API calls, plus 10-20 LLM calls with images.

**Impact**: The free tiers of these APIs will support only a few investigations per month. Production use requires paid tiers and cost monitoring.

### 24. Google Maps API Billing Complexity

Google Maps Platform bills separately for:

- Static Maps (satellite): $2 per 1,000 requests
- Street View Static: $7 per 1,000 requests
- Geocoding: $5 per 1,000 requests
- Places Text Search: $32 per 1,000 requests
- Place Details: $17 per 1,000 requests

The `investigate` node could potentially make many Google Maps calls per iteration without the agent being aware of the relative cost of each tool.

**Impact**: Places Text Search is 6x more expensive than geocoding. The agent has no awareness of tool cost and cannot make cost-aware decisions.
