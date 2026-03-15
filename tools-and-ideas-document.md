# Geolocation Agent Tooling Instructions

Use this document as operating instructions for a coding agent that needs to geolocate an image.

## Goal

Given an image, determine its most likely real-world location by extracting visual clues, generating candidate hypotheses, gathering external evidence, and verifying the best candidate.

## Core Principle

Prefer a small, high-value toolset over a large, unfocused toolbox. The agent should work in stages:

1. Extract clues from the image
2. Generate regional and venue-level hypotheses
3. Search for candidate places
4. Compare candidate imagery
5. Verify with maps and ground imagery
6. Rank confidence and explain the reasoning

## Required Tools

These tools are the minimum needed for a capable geolocation agent.

### 1. Image Inspection

The agent must be able to:

* zoom into regions
* crop the image
* adjust contrast / sharpness / brightness
* inspect fine details
* extract metadata if present
* run OCR on small text

Purpose:

* detect signs, logos, text, plates, menus, labels, road markings, furniture, architectural details, vegetation, and terrain features

### 2. Reverse Image Search

The agent must be able to:

* run reverse image search on the full image
* run reverse image search on cropped regions

Purpose:

* match venues, facades, interior views, furniture, distinctive landscaping, barrel placement, vineyard layouts, coastline shapes, and similar public photos

### 3. Web Search

The agent must be able to:

* perform general web search
* search local businesses and attractions
* search with structured query refinement based on extracted clues

Purpose:

* convert hypotheses such as “NSW South Coast winery with picnic lawn” into a concrete candidate list

### 4. Maps and Geospatial Verification

The agent must be able to use:

* interactive maps
* satellite imagery
* terrain view
* Street View or equivalent ground imagery
* distance / bearing measurement tools

Purpose:

* verify candidate locations by matching terrain, building orientation, road approach, vineyard rows, coastline shape, view direction, and nearby structures

### 5. Structured Memory / Evidence Tracker

The agent must keep a persistent investigation log containing:

* extracted clues
* active hypotheses
* candidate locations
* eliminated candidates
* evidence for and against each candidate
* current confidence ranking

Purpose:

* prevent repeated work
* support multi-step reasoning
* make the investigation auditable

## Strongly Recommended Tools

These are not strictly required, but materially improve speed and accuracy.

### 6. Place / POI Database Lookup

Examples:

* wineries
* hotels
* cafes
* lookouts
* beaches
* trailheads
* museums
* landmarks

Purpose:

* turn regional hypotheses into a shortlist filtered by category and attributes

### 7. Historical Weather and Sun Tools

The agent should be able to access:

* historical weather
* cloud / rain conditions
* sun azimuth and elevation
* rough seasonality checks

Purpose:

* use shadows, fog, storm conditions, and vegetation state to validate or eliminate candidates

### 8. File / Image Forensics

The agent should be able to inspect:

* EXIF metadata
* timestamps
* camera model
* GPS metadata if present
* edit / recompression clues

Purpose:

* quickly constrain or solve the search when metadata exists

### 9. Vision-to-Vision Comparison

The agent should be able to:

* compare the query image against candidate photos
* highlight matching elements
* score visual similarity

Useful matching targets:

* window frames
* fence lines
* roof shapes
* barrels, benches, umbrellas, tables
* tree silhouettes
* horizon lines
* vineyard block geometry

Purpose:

* efficiently narrow 5–20 candidates down to the most likely match

### 10. Domain-Specific Recognizers

Useful specialist classifiers include:

* plant / tree identification
* architecture style recognition
* road sign style recognition
* lane marking / guardrail / utility pole classification

Purpose:

* infer region or country from weak but informative visual cues

## Minimum Viable Toolset

If only a small implementation is possible, build these first:

* image zoom / crop
* OCR
* web search
* reverse image search
* maps with satellite and Street View
* evidence tracker

This is the smallest toolset that can still solve many geolocation tasks reliably.

## Recommended Agent Workflow

### Step 1: Extract Visual Evidence

The agent should inspect the image and record:

* text
* visible businesses or brands
* architecture
* vegetation
* road and infrastructure clues
* terrain and land use
* weather and lighting
* interior objects that may indicate venue type

Output:

* a structured clue list

### Step 2: Generate Hypotheses

The agent should propose:

* likely country / state / region
* likely place type
* alternative explanations

Examples:

* coastal winery
* rural hotel
* lookout cafe
* golf club
* national park lodge

Output:

* ranked hypotheses with brief reasons

### Step 3: Search for Candidate Places

The agent should search the web and POI databases using combinations of:

* region
* venue category
* extracted objects
* terrain clues
* architectural clues

Output:

* a candidate shortlist

### Step 4: Compare Candidate Images

For each candidate, compare public images against the query image using:

* landscape shape
* building layout
* furniture
* planting patterns
* view direction
* distinctive objects

Output:

* narrowed shortlist with supporting evidence

### Step 5: Verify Geospatially

Use maps, satellite, terrain, and Street View to test:

* does the building exist?
* does the surrounding land match?
* do the sightlines match?
* do the vine rows / paddocks / coastline / roads align?

Output:

* verified best match or a smaller set of unresolved finalists

### Step 6: Report Confidence

The agent should always report:

* best candidate
* other plausible candidates
* key evidence
* unresolved uncertainties
* confidence level

## Operating Rules

* Do not jump from one clue to a precise location without verification.
* Treat early matches as hypotheses, not conclusions.
* Prefer independent confirmation from at least two different evidence sources.
* Use cropped reverse image search aggressively when the full image is ambiguous.
* Keep eliminated candidates in the evidence log with reasons.
* Make uncertainty explicit.

## Output Format for the Agent

For each investigation cycle, the agent should produce:

### Extracted Clues

* concise bullet list of image-derived facts

### Current Hypotheses

* ranked list with reasons

### Promising Next Steps

* the highest-value actions to take next

### Confidence

* confidence for region, place type, and exact venue separately

## Example High-Level Instruction to the Agent

You are a geolocation agent. Use image inspection, reverse image search, web search, and maps verification to identify where an image was taken. Work iteratively. First extract concrete visual clues. Then generate ranked regional and venue-level hypotheses. Then search for candidate locations. Compare candidate imagery against the query image. Finally verify the best candidates with satellite, terrain, and ground imagery before concluding. Maintain an explicit evidence log, preserve eliminated candidates, and always state confidence and uncertainty.
