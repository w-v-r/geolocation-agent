# Tools Reference

## Image Tools (`tools/image_tools.py`)

### crop_image
Crop a rectangular region from the image.
- **Params**: `image_path`, `x`, `y`, `width`, `height` (all int, pixels)
- **Returns**: Path to cropped image file
- **Notes**: Coordinates are clamped to image bounds

### zoom_image
Zoom into a point in the image by cropping around it and upscaling.
- **Params**: `image_path`, `center_x`, `center_y` (int), `zoom_factor` (float, default 2.0)
- **Returns**: Path to zoomed image file (same dimensions as original)

### adjust_image
Adjust brightness, contrast, and sharpness.
- **Params**: `image_path`, `brightness` (float), `contrast` (float), `sharpness` (float)
- **Returns**: Path to adjusted image file
- **Notes**: 1.0 = no change, >1 increases, <1 decreases

### extract_exif
Extract EXIF metadata from an image.
- **Params**: `image_path`
- **Returns**: JSON string with all EXIF tags. Includes `parsed_latitude`/`parsed_longitude` if GPS data exists

## Search Tools (`tools/search_tools.py`)

### web_search
Search the web using Tavily.
- **Params**: `query` (str), `num_results` (int, default 10)
- **Returns**: JSON array of `{title, url, content, score}`
- **API**: Tavily (advanced search depth)

### reverse_image_search
Reverse image search using Google Lens via SerpAPI.
- **Params**: `image_path` (str)
- **Returns**: JSON with `visual_matches` and `knowledge_graph` arrays
- **API**: SerpAPI Google Lens engine
- **Notes**: Uploads image to temporary host first

### reverse_image_search_region
Crop a region and reverse image search just that region.
- **Params**: `image_path`, `x`, `y`, `width`, `height` (int, pixels)
- **Returns**: Same format as reverse_image_search
- **Notes**: Often more effective than full-image search

## Maps Tools (`tools/maps_tools.py`)

### get_satellite_image
Fetch satellite imagery from Google Maps.
- **Params**: `lat`, `lng` (float), `zoom` (int, 1-20, default 18), `size` (str, default "600x400")
- **Returns**: Path to saved satellite image file
- **API**: Google Maps Static API

### get_street_view
Fetch Street View image from a location.
- **Params**: `lat`, `lng` (float), `heading` (float, 0-360), `pitch` (float, -90 to 90), `fov` (int, 10-120), `size` (str)
- **Returns**: Path to saved Street View image, or JSON error if unavailable
- **API**: Google Street View Static API
- **Notes**: Checks metadata endpoint first; returns error if no coverage

### geocode
Convert address to coordinates.
- **Params**: `address` (str)
- **Returns**: JSON with `latitude`, `longitude`, `formatted_address`, `place_id`, `types`
- **API**: Google Maps Geocoding

### reverse_geocode
Convert coordinates to address.
- **Params**: `lat`, `lng` (float)
- **Returns**: JSON array of up to 3 address results
- **API**: Google Maps Geocoding

## Places Tools (`tools/places_tools.py`)

### search_places_nearby
Search for places near a location.
- **Params**: `lat`, `lng` (float), `radius` (int, meters, max 50000), `place_type` (str, optional), `keyword` (str, optional)
- **Returns**: JSON array of up to 20 places with `name`, `place_id`, `address`, `latitude`, `longitude`, `types`, `rating`
- **API**: Google Maps Places Nearby Search

### search_places_text
Search for places using a text query.
- **Params**: `query` (str)
- **Returns**: Same format as search_places_nearby
- **API**: Google Maps Places Text Search

### get_place_details
Get detailed info about a specific place.
- **Params**: `place_id` (str)
- **Returns**: JSON with full details including `phone`, `website`, `opening_hours`, `reviews`, `photos`
- **API**: Google Maps Place Details

## Evidence Tracker (`tools/evidence_tracker.py`)

### add_clue
Record an extracted clue. Returns JSON with assigned ID (prefix: `clue_`).

### add_hypothesis
Record a hypothesis. Returns JSON with assigned ID (prefix: `hyp_`).

### add_candidate
Record a candidate location. Returns JSON with assigned ID (prefix: `cand_`).

### add_evidence
Record evidence for/against a hypothesis. Returns JSON with assigned ID (prefix: `ev_`).

### eliminate_candidate
Mark a candidate as eliminated with reason.

### update_confidence
Update a candidate's confidence score with reason.

### get_investigation_summary
Generate a formatted markdown summary of the current investigation state.
