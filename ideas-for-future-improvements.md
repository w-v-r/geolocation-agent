# Ideas for Future Improvements

Future enhancements to consider for the geolocation agent. See [limitations.md](docs/limitations.md) for current constraints.

---

## OSINT Geolocation Tools (Tier 1 and Tier 2)

From the OSINT framework geolocation tools, these are the highest-impact additions, prioritized by API accessibility and ability to address known gaps.

### Tier 1: High Impact, API-Accessible

| Tool | Capability | Why It Helps |
|------|------------|--------------|
| **Nominatim (OpenStreetMap)** | Geocoding, reverse geocoding | Free, no API key; alternative when Google fails or for cost control |
| **Bing Maps** | Satellite, Street View (Streetside), Geocoding | Different coverage than Google; useful in regions where Google is weak |
| **Yandex.Maps** | Satellite, Street View (Panoramas) | Strong coverage in Russia, CIS, parts of Eastern Europe |
| **MapQuest** | Geocoding, routing | Free tier; fallback geocoding |

### Tier 2: Addresses Temporal / Coverage Gaps

| Tool | Capability | Why It Helps |
|------|------------|--------------|
| **Historic Aerials** | Historical satellite imagery | Directly addresses temporal mismatch (limitation #23) |
| **Wayback Imagery (ESRI)** | Historical imagery | Same as above; different source |
| **EarthExplorer (USGS)** | Landsat, aerial photos | Free; historical and scientific imagery |
| **OpenStreetCam** | Crowdsourced street-level imagery | Street View alternative where Google has no coverage |

---

## Kaggle Training Dataset

**Dataset**: [GeoLocation - Geoguessr Images (50K)](https://www.kaggle.com/datasets/ubitquitin/geolocation-geoguessr-images-50k)

### Contents

- 50,000 Google Street View images from 124 countries
- Ground truth: country (and likely lat/lng) per image
- Heavily skewed distribution (e.g., US ~12k images, some countries with only 1 image)
- Used for country-level geolocation from visual clues (signs, architecture, vegetation, language markers)

### Relevance

Directly addresses [limitation #26](docs/limitations.md)—no ground truth evaluation framework. This dataset provides labeled examples for benchmarking accuracy and for training/optimizing the agent.

---

## DSPy-Style Training Loop

Use DSPy optimizers to improve prompts and few-shot examples by running the agent on labeled data and tuning based on a metric (e.g., distance error or country match).

### Metric

Define `metric(prediction, ground_truth)` — e.g., negative distance in km (closer = higher score), or binary country match. DSPy optimizers maximize this metric.

### Program Signature

Treat the agent as a DSPy module with inputs (image path, optional side info) and outputs (lat, lng, country, confidence).

### Optimizers

- **BootstrapFewShot**: Run the agent on training images, collect traces where the metric is high; use successful runs as few-shot demos in prompts.
- **MIPROv2**: Jointly optimize instructions (system/investigate prompts) and few-shot examples via bootstrap + Bayesian search over instruction candidates.

### Data Split

Use the Kaggle 50K dataset — e.g., 20% train (10k), 80% validation (40k) to avoid overfitting. Given API cost, start with a smaller subset (500–1000 images) for initial optimization runs.

### Integration Options

1. **Black-box wrapper**: Wrap the LangGraph agent as a callable that returns structured output for DSPy. Use BootstrapFewShot to mine good traces for few-shot injection into the investigate prompt.
2. **Module extraction**: Extract the key prompts (analyze, hypothesize, investigate) into DSPy `Predict`/`ChainOfThought` modules, optimize those, then port improved prompts back into the agent.

### Challenges

The agent is multi-step with tools; DSPy typically optimizes single-module programs. Options: optimize the final "produce_report" step only, or treat the full pipeline as a black box and use BootstrapFewShot to mine traces for few-shot injection.
