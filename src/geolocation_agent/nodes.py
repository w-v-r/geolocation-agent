"""LangGraph node functions for each phase of the geolocation investigation."""

from __future__ import annotations

import base64
import json
import os
import sys
import uuid

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from geolocation_agent.config import get_llm, get_settings
from geolocation_agent.prompts import (
    ANALYZE_PROMPT,
    HYPOTHESIZE_PROMPT,
    INVESTIGATE_PROMPT,
    REPORT_PROMPT,
    SYSTEM_PROMPT,
)
from geolocation_agent.tools import ALL_TOOLS, ANALYSIS_TOOLS

IMAGE_PATH_TOOLS = {
    "crop_image", "zoom_image", "adjust_image", "extract_exif",
    "reverse_image_search", "reverse_image_search_region",
}

SEARCH_TOOLS = {
    "web_search", "reverse_image_search", "reverse_image_search_region",
    "search_places_text", "search_places_nearby", "get_place_details",
    "get_street_view", "get_satellite_image", "geocode", "reverse_geocode",
}

EVIDENCE_TOOLS = {
    "add_evidence", "add_candidate", "add_clue", "add_hypothesis",
    "eliminate_candidate", "update_confidence",
}

MIN_CLUES = 3


def _log(message: str) -> None:
    """Print a progress message to stderr so it appears immediately."""
    print(f"  → {message}", file=sys.stderr, flush=True)


def _inject_image_path(tool_name: str, tool_args: dict, image_path: str) -> dict:
    """Override the image_path argument for image tools with the real path."""
    if tool_name in IMAGE_PATH_TOOLS and "image_path" in tool_args:
        tool_args = {**tool_args, "image_path": image_path}
    return tool_args


def _make_tool_history_entry(
    tool_name: str, tool_args: dict, result_summary: str, iteration: int,
) -> dict:
    """Create a tool history entry for state tracking."""
    display_args = {k: v for k, v in tool_args.items() if k != "image_path"}
    return {
        "id": f"th_{uuid.uuid4().hex[:8]}",
        "tool_name": tool_name,
        "args_summary": ", ".join(f"{k}={v!r}" for k, v in display_args.items()),
        "result_summary": result_summary[:200],
        "iteration": iteration,
    }


def _build_image_message(image_path: str, text: str) -> HumanMessage:
    """Build a multimodal message with an image and text."""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    ext = image_path.rsplit(".", 1)[-1].lower()
    media_type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
    media_type = media_type_map.get(ext, "image/jpeg")

    return HumanMessage(
        content=[
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}"}},
            {"type": "text", "text": text},
        ]
    )


def _get_state_summary(state: dict) -> str:
    """Build a summary of current investigation state for the LLM."""
    parts = []

    if state.get("side_info"):
        parts.append(f"## Side Information\n{state['side_info']}")

    clues = state.get("clues", [])
    BROAD_CLUE_CATEGORIES = {"vegetation", "architecture", "terrain", "weather_lighting", "language", "metadata", "other"}
    if clues:
        parts.append(f"## Extracted Clues ({len(clues)})")
        parts.append(
            "Use BROAD clues (vegetation, architecture, terrain, other) for region narrowing and search queries. "
            "Use SPECIFIC clues (interior, text, signage, furniture) for venue comparison and verification."
        )
        broad_clues = [c for c in clues if (c.get("category") or "").lower() in BROAD_CLUE_CATEGORIES]
        specific_clues = [c for c in clues if c not in broad_clues]
        for label, clue_list in [("Region-narrowing", broad_clues), ("Venue-comparison", specific_clues)]:
            if clue_list:
                parts.append(f"\n### {label} clues")
                for c in clue_list:
                    line = f"- {c.get('id', '?')} [{c.get('category', '?')}] {c.get('description', '?')} (confidence: {c.get('confidence', '?')})"
                    region_hint = (c.get("region_hint") or "").strip()
                    if region_hint:
                        line += f" → region hint: {region_hint}"
                    raw_value = (c.get("raw_value") or "").strip()
                    if raw_value:
                        line += f" | raw: {raw_value}"
                    parts.append(line)
    else:
        parts.append("## Extracted Clues (0)\nNo clues extracted yet.")

    hypotheses = state.get("hypotheses", [])
    active = [h for h in hypotheses if h.get("status") == "active"]
    if active:
        parts.append(f"\n## Active Hypotheses ({len(active)})")
        for h in sorted(active, key=lambda x: x.get("confidence", 0), reverse=True):
            staleness = h.get("iterations_without_evidence", 0)
            stale_tag = f" [STALE: {staleness} iterations without new evidence]" if staleness >= 2 else ""
            parts.append(f"- [{h.get('level', '?')}] {h.get('description', '?')} "
                         f"(confidence: {h.get('confidence', '?')}){stale_tag}")
    else:
        parts.append("\n## Active Hypotheses (0)\nNo hypotheses yet.")

    candidates = state.get("candidates", [])
    active_cands = [c for c in candidates if not c.get("eliminated")]
    if active_cands:
        parts.append(f"\n## Active Candidates ({len(active_cands)})")
        for c in sorted(active_cands, key=lambda x: x.get("confidence", 0), reverse=True):
            parts.append(f"- {c.get('name', '?')} @ ({c.get('latitude', '?')}, "
                         f"{c.get('longitude', '?')}) confidence: {c.get('confidence', '?')}")
    else:
        parts.append("\n## Active Candidates (0)\nNo candidates registered yet. "
                     "Use add_candidate to register locations you want to investigate.")

    evidence = state.get("evidence_log", [])
    if evidence:
        recent = evidence[-10:]
        parts.append(f"\n## Recent Evidence ({len(evidence)} total, showing last {len(recent)})")
        for e in recent:
            prefix = {"supporting": "+", "contradicting": "-", "neutral": "~"}.get(
                e.get("evidence_type", ""), "?"
            )
            parts.append(f"  {prefix} {e.get('description', '?')} [source: {e.get('source', '?')}]")
    else:
        parts.append("\n## Evidence Log (0)\nNo evidence recorded yet. "
                     "Use add_evidence after every search or verification step.")

    eliminated = state.get("eliminated", [])
    if eliminated:
        parts.append(f"\n## Eliminated Candidates ({len(eliminated)})")
        for e in eliminated:
            parts.append(f"- {e.get('name', '?')}: {e.get('elimination_reason', '?')}")

    tool_history = state.get("tool_history", [])
    if tool_history:
        recent_tools = tool_history[-15:]
        parts.append(f"\n## Previous Tool Calls ({len(tool_history)} total, showing last {len(recent_tools)})")
        parts.append("DO NOT repeat these exact searches. Try different queries or tools.")
        for t in recent_tools:
            parts.append(f"- [iter {t.get('iteration', '?')}] {t.get('tool_name', '?')}"
                         f"({t.get('args_summary', '')}) → {t.get('result_summary', '?')}")

    parts.append(f"\n## Iteration: {state.get('iteration', 0)}/{state.get('max_iterations', 10)}")
    parts.append(f"## Current Confidence: {state.get('confidence', 0.0)}")

    return "\n".join(parts)


def extract_metadata(state: dict) -> dict:
    """Extract EXIF metadata from the image as the first step."""
    from geolocation_agent.tools.image_tools import extract_exif

    image_path = os.path.abspath(state["image_path"])
    print(f"\n{'='*60}", file=sys.stderr, flush=True)
    print("PHASE: Extract Metadata", file=sys.stderr, flush=True)
    print(f"{'='*60}", file=sys.stderr, flush=True)
    _log(f"Reading EXIF from: {image_path}")

    exif_result = extract_exif.invoke({"image_path": image_path})
    exif_data = json.loads(exif_result)

    clues = []

    if exif_data.get("parsed_latitude") is not None:
        _log(f"GPS found: ({exif_data['parsed_latitude']}, {exif_data['parsed_longitude']})")
        clues.append({
            "id": "clue_gps",
            "description": f"GPS coordinates found in EXIF: ({exif_data['parsed_latitude']}, "
                           f"{exif_data['parsed_longitude']})",
            "category": "metadata",
            "source": "exif",
            "confidence": 1.0,
            "raw_value": f"{exif_data['parsed_latitude']}, {exif_data['parsed_longitude']}",
            "region_hint": "",
        })

    camera = exif_data.get("Image Model", "")
    if camera:
        _log(f"Camera: {camera}")
        clues.append({
            "id": "clue_camera",
            "description": f"Camera model: {camera}",
            "category": "metadata",
            "source": "exif",
            "confidence": 1.0,
            "raw_value": camera,
            "region_hint": "",
        })

    timestamp = exif_data.get("EXIF DateTimeOriginal", "")
    if timestamp:
        _log(f"Timestamp: {timestamp}")
        clues.append({
            "id": "clue_timestamp",
            "description": f"Photo taken at: {timestamp}",
            "category": "metadata",
            "source": "exif",
            "confidence": 1.0,
            "raw_value": timestamp,
            "region_hint": "",
        })

    if not clues:
        _log("No EXIF metadata found")

    return {
        "clues": clues,
        "image_path": image_path,
        "phase": "analyze",
        "messages": [
            HumanMessage(content=f"EXIF metadata extracted: {exif_result}")
        ],
    }


def analyze_image(state: dict) -> dict:
    """LLM inspects the image with vision and extracts visual clues.

    If the LLM fails to extract at least MIN_CLUES, a retry with a more
    forceful prompt is attempted once.
    """
    print(f"\n{'='*60}", file=sys.stderr, flush=True)
    print("PHASE: Analyze Image (Vision LLM)", file=sys.stderr, flush=True)
    print(f"{'='*60}", file=sys.stderr, flush=True)

    llm = get_llm()
    llm_with_tools = llm.bind_tools(ANALYSIS_TOOLS)

    image_path = state["image_path"]
    state_summary = _get_state_summary(state)

    image_message = _build_image_message(
        image_path,
        f"{ANALYZE_PROMPT}\n\n{state_summary}\n\n"
        f"The image file path is: {image_path}\n"
        "When using image tools (crop_image, zoom_image, adjust_image, extract_exif), "
        f"always pass image_path=\"{image_path}\".\n\n"
        "Inspect this image carefully and extract every visual clue. "
        "Use the crop and zoom tools if you need to inspect details more closely.",
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        image_message,
    ]

    collected_clues = list(state.get("clues", []))
    new_messages = []
    clues_before = len(collected_clues)

    _log("Sending image to vision LLM for analysis...")

    collected_clues, new_messages = _run_analyze_loop(
        llm_with_tools, messages, collected_clues, image_path,
    )

    new_clue_count = len(collected_clues) - clues_before
    if new_clue_count < MIN_CLUES:
        _log(f"Only {new_clue_count} clues extracted — retrying with stronger prompt...")
        retry_message = HumanMessage(
            content=(
                f"You only extracted {new_clue_count} clue(s). This is not enough. "
                f"You MUST extract at least {MIN_CLUES} visual clues by calling add_clue. "
                "Look carefully at:\n"
                "- The large tree: what species? (e.g. Moreton Bay Fig, Oak, Magnolia)\n"
                "- The chairs: what style? (e.g. Adirondack, plastic, wooden)\n"
                "- The building: roof style, materials, veranda type\n"
                "- Any barrels, equipment, or objects that suggest a venue type\n"
                "- The grass/lawn: maintained estate or public park?\n"
                "- Any visible text, signs, or logos\n"
                "- The sky/weather: overcast, sunny, season indicators\n"
                "- Any other distinctive features\n\n"
                "Call add_clue for EACH observation now."
            )
        )
        messages.append(retry_message)
        collected_clues, retry_messages = _run_analyze_loop(
            llm_with_tools, messages, collected_clues, image_path,
        )
        new_messages.extend(retry_messages)

    _log(f"Total clues extracted: {len(collected_clues)}")

    return {
        "clues": collected_clues,
        "phase": "hypothesize",
        "messages": new_messages,
    }


def _run_analyze_loop(
    llm_with_tools, messages: list, collected_clues: list, image_path: str,
) -> tuple[list, list]:
    """Run the analyze tool-calling loop. Returns (clues, new_messages)."""
    new_messages = []

    for _ in range(5):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        new_messages.append(response)

        if not response.tool_calls:
            _log("Analysis round complete")
            break

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = _inject_image_path(tool_name, tool_call["args"], image_path)

            _log(f"Tool call: {tool_name}({', '.join(f'{k}={v!r}' for k, v in tool_args.items() if k != 'image_path')})")

            tool_fn = next((t for t in ANALYSIS_TOOLS if t.name == tool_name), None)
            if tool_fn:
                try:
                    tool_result = tool_fn.invoke(tool_args)
                except Exception as exc:
                    _log(f"  Tool error: {exc}")
                    tool_result = json.dumps({"error": str(exc)})
                messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))

                if tool_name == "add_clue":
                    try:
                        clue_data = json.loads(tool_result)
                        collected_clues.append(clue_data)
                        _log(f"  Clue: [{clue_data.get('category', '?')}] {clue_data.get('description', '?')}")
                    except json.JSONDecodeError:
                        pass

    return collected_clues, new_messages


def generate_hypotheses(state: dict) -> dict:
    """LLM proposes or refines hypotheses based on accumulated clues and evidence.

    Includes staleness detection to demote hypotheses that have persisted
    without new supporting evidence, and enforces geographic diversity.
    """
    iteration = state.get("iteration", 0)
    print(f"\n{'='*60}", file=sys.stderr, flush=True)
    print(f"PHASE: Generate Hypotheses (iteration {iteration})", file=sys.stderr, flush=True)
    print(f"{'='*60}", file=sys.stderr, flush=True)

    llm = get_llm()

    from geolocation_agent.tools.evidence_tracker import add_hypothesis as add_hyp_tool

    llm_with_tools = llm.bind_tools([add_hyp_tool])

    existing_hypotheses = list(state.get("hypotheses", []))
    evidence_log = state.get("evidence_log", [])

    for h in existing_hypotheses:
        if h.get("status") != "active":
            continue
        hyp_id = h.get("id", "")
        has_new_evidence = any(
            e.get("hypothesis_id") == hyp_id and e.get("evidence_type") == "supporting"
            for e in evidence_log
        )
        stale_count = h.get("iterations_without_evidence", 0)
        if has_new_evidence:
            h["iterations_without_evidence"] = 0
        else:
            h["iterations_without_evidence"] = stale_count + 1

    state_summary = _get_state_summary(state)

    staleness_warnings = []
    regions_seen = set()
    for h in existing_hypotheses:
        if h.get("status") != "active":
            continue
        stale = h.get("iterations_without_evidence", 0)
        if stale >= 2:
            staleness_warnings.append(
                f"- \"{h.get('description', '?')}\" has had NO new supporting evidence "
                f"for {stale} iterations. Consider demoting or replacing it."
            )
        region = h.get("region", "").lower().strip()
        if region:
            regions_seen.add(region)

    staleness_text = ""
    if staleness_warnings:
        staleness_text = (
            "\n\n## STALE HYPOTHESES — ACTION REQUIRED\n"
            "The following hypotheses have not gained any new evidence. "
            "You should demote them and explore different regions/venues:\n"
            + "\n".join(staleness_warnings)
        )

    diversity_text = ""
    if len(regions_seen) <= 1 and iteration > 0:
        region_name = next(iter(regions_seen), "unknown")
        diversity_text = (
            f"\n\nWARNING: All current hypotheses target the same region ({region_name}). "
            "You MUST propose at least one hypothesis for a DIFFERENT region. "
            "Consider alternative countries/continents that match the visual clues."
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=(
            f"{HYPOTHESIZE_PROMPT}\n\n{state_summary}"
            f"{staleness_text}{diversity_text}\n\n"
            "Based on the clues and evidence above, propose or refine hypotheses. "
            "Use the add_hypothesis tool to record each one. "
            "Do NOT re-add hypotheses that already appear in the Active Hypotheses list above."
        )),
    ]

    collected_hypotheses = list(existing_hypotheses)
    new_messages = []

    _log("Generating location hypotheses...")

    for _ in range(5):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        new_messages.append(response)

        if not response.tool_calls:
            break

        for tool_call in response.tool_calls:
            if tool_call["name"] == "add_hypothesis":
                tool_result = add_hyp_tool.invoke(tool_call["args"])
                messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))
                try:
                    hyp_data = json.loads(tool_result)
                    hyp_data["iterations_without_evidence"] = 0
                    collected_hypotheses.append(hyp_data)
                    _log(f"  Hypothesis: [{hyp_data.get('level', '?')}] "
                         f"{hyp_data.get('description', '?')} "
                         f"(confidence: {hyp_data.get('confidence', '?')})")
                except json.JSONDecodeError:
                    pass

    _log(f"Total hypotheses: {len(collected_hypotheses)}")

    return {
        "hypotheses": collected_hypotheses,
        "phase": "investigate",
        "messages": new_messages,
    }


def investigate(state: dict) -> dict:
    """LLM investigates hypotheses using all available tools.

    Tracks tool calls in tool_history and injects reminders when the LLM
    uses search/maps tools without recording evidence.
    """
    iteration = state.get("iteration", 0)
    print(f"\n{'='*60}", file=sys.stderr, flush=True)
    print(f"PHASE: Investigate (iteration {iteration})", file=sys.stderr, flush=True)
    print(f"{'='*60}", file=sys.stderr, flush=True)

    llm = get_llm()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    state_summary = _get_state_summary(state)

    image_path = state["image_path"]
    image_message = _build_image_message(
        image_path,
        f"{INVESTIGATE_PROMPT}\n\n{state_summary}\n\n"
        f"The image file path is: {image_path}\n"
        "When using image tools (crop_image, zoom_image, adjust_image, extract_exif, "
        "reverse_image_search, reverse_image_search_region), "
        f"always pass image_path=\"{image_path}\".\n\n"
        "Investigate the current hypotheses. Use whatever tools have the highest "
        "expected value right now. Record all evidence with add_evidence and "
        "register candidate locations with add_candidate.",
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        image_message,
    ]

    collected_evidence = list(state.get("evidence_log", []))
    collected_candidates = list(state.get("candidates", []))
    collected_clues = list(state.get("clues", []))
    collected_hypotheses = list(state.get("hypotheses", []))
    collected_eliminated = list(state.get("eliminated", []))
    new_tool_history = []
    new_messages = []

    max_tool_rounds = 8
    evidence_reminder_sent = False

    for round_num in range(max_tool_rounds):
        _log(f"Tool round {round_num + 1}/{max_tool_rounds}...")
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        new_messages.append(response)

        if not response.tool_calls:
            _log("No more tool calls — investigation round complete")
            break

        round_used_search = False
        round_recorded_evidence = False

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = _inject_image_path(tool_name, tool_call["args"], image_path)

            display_args = {k: v for k, v in tool_args.items() if k != "image_path"}
            display_str = ", ".join(f"{k}={v!r}" for k, v in display_args.items())
            _log(f"Tool call: {tool_name}({display_str})")

            if tool_name in SEARCH_TOOLS:
                round_used_search = True
            if tool_name in EVIDENCE_TOOLS:
                round_recorded_evidence = True

            tool_fn = next((t for t in ALL_TOOLS if t.name == tool_name), None)
            if tool_fn:
                try:
                    tool_result = tool_fn.invoke(tool_args)
                except Exception as exc:
                    _log(f"  Tool error: {exc}")
                    tool_result = json.dumps({"error": str(exc)})
                messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))

                result_summary = tool_result[:200] if isinstance(tool_result, str) else str(tool_result)[:200]
                new_tool_history.append(_make_tool_history_entry(
                    tool_name, tool_args, result_summary, iteration,
                ))

                try:
                    result_data = json.loads(tool_result)
                except (json.JSONDecodeError, TypeError):
                    result_data = None

                if result_data and isinstance(result_data, dict):
                    if result_data.get("error"):
                        _log(f"  Tool returned error: {result_data['error']}")
                        continue

                    result_id = result_data.get("id", "")
                    if result_id.startswith("ev_"):
                        collected_evidence.append(result_data)
                        round_recorded_evidence = True
                        _log(f"  Evidence: {result_data.get('description', '?')}")
                    elif result_id.startswith("cand_"):
                        collected_candidates.append(result_data)
                        round_recorded_evidence = True
                        _log(f"  Candidate: {result_data.get('name', '?')} "
                             f"({result_data.get('latitude', '?')}, {result_data.get('longitude', '?')})")
                    elif result_id.startswith("clue_"):
                        collected_clues.append(result_data)
                        _log(f"  Clue: {result_data.get('description', '?')}")
                    elif result_id.startswith("hyp_"):
                        collected_hypotheses.append(result_data)
                        _log(f"  Hypothesis: {result_data.get('description', '?')}")
                    elif result_data.get("action") == "eliminate_candidate":
                        cand_id = result_data.get("candidate_id")
                        for c in collected_candidates:
                            if c.get("id") == cand_id:
                                c["eliminated"] = True
                                c["elimination_reason"] = result_data.get("elimination_reason")
                                collected_eliminated.append(c)
                                _log(f"  Eliminated: {c.get('name', '?')}")
                    elif result_data.get("action") == "update_confidence":
                        cand_id = result_data.get("candidate_id")
                        for c in collected_candidates:
                            if c.get("id") == cand_id:
                                c["confidence"] = result_data.get("new_confidence", c["confidence"])
                                _log(f"  Updated confidence: {c.get('name', '?')} → {c['confidence']}")

        if round_used_search and not round_recorded_evidence and not evidence_reminder_sent:
            _log("Injecting evidence-recording reminder...")
            reminder = HumanMessage(content=(
                "IMPORTANT: You just used search/maps tools but did NOT record any evidence "
                "or candidates. You MUST:\n"
                "1. Call add_evidence for each search result — even if it was inconclusive "
                "(use evidence_type='neutral').\n"
                "2. Call add_candidate for any location that could plausibly match the photo.\n"
                "3. If a search returned nothing useful, call add_evidence with "
                "evidence_type='neutral' noting the failed search.\n\n"
                "Do this NOW before making any more searches."
            ))
            messages.append(reminder)
            evidence_reminder_sent = True

    best_confidence = 0.0
    for c in collected_candidates:
        if not c.get("eliminated") and c.get("confidence", 0) > best_confidence:
            best_confidence = c["confidence"]

    _log(f"Candidates: {len(collected_candidates)}, "
         f"Evidence: {len(collected_evidence)}, "
         f"Best confidence: {best_confidence:.0%}")

    return {
        "clues": collected_clues,
        "hypotheses": collected_hypotheses,
        "candidates": collected_candidates,
        "evidence_log": collected_evidence,
        "eliminated": collected_eliminated,
        "tool_history": new_tool_history,
        "confidence": best_confidence,
        "iteration": state.get("iteration", 0) + 1,
        "phase": "decide",
        "messages": new_messages,
    }


def should_continue(state: dict) -> str:
    """Conditional edge: decide whether to continue investigating or report."""
    settings = get_settings()
    confidence = state.get("confidence", 0.0)
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", settings.max_iterations)

    if confidence >= settings.confidence_threshold:
        _log(f"Confidence {confidence:.0%} >= threshold {settings.confidence_threshold:.0%} — moving to report")
        return "report"

    if iteration >= max_iterations:
        _log(f"Reached max iterations ({max_iterations}) — moving to report")
        return "report"

    _log(f"Confidence {confidence:.0%} < threshold — continuing investigation (iteration {iteration + 1})")
    return "hypothesize"


def produce_report(state: dict) -> dict:
    """Generate the final investigation report."""
    print(f"\n{'='*60}", file=sys.stderr, flush=True)
    print("PHASE: Produce Report", file=sys.stderr, flush=True)
    print(f"{'='*60}", file=sys.stderr, flush=True)
    _log("Generating final report...")

    llm = get_llm()

    state_summary = _get_state_summary(state)

    candidates = state.get("candidates", [])
    active_candidates = [c for c in candidates if not c.get("eliminated")]
    evidence_count = len(state.get("evidence_log", []))

    grounding_context = (
        f"\n\n## GROUNDING CONSTRAINTS\n"
        f"- You have {len(active_candidates)} active candidate(s) in the tracker.\n"
        f"- You have {evidence_count} evidence entries in the tracker.\n"
    )
    if not active_candidates:
        grounding_context += (
            "- Since you have 0 candidates, you MUST state that no specific venue "
            "was identified. Do NOT fabricate a venue name or claim matches that "
            "don't exist in the evidence log.\n"
        )
    if evidence_count == 0:
        grounding_context += (
            "- Since you have 0 evidence entries, do NOT claim any tool produced "
            "results. State honestly that the investigation did not yield "
            "confirmatory evidence.\n"
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=(
            f"{REPORT_PROMPT}\n\n{state_summary}{grounding_context}\n\n"
            "Produce your final report now."
        )),
    ]

    response = llm.invoke(messages)

    active_candidates.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    best = active_candidates[0] if active_candidates else None

    confidence = state.get("confidence", 0.0)
    if confidence >= 0.9:
        level = "certain"
    elif confidence >= 0.7:
        level = "confident"
    elif confidence >= 0.4:
        level = "plausible"
    else:
        level = "speculative"

    final_answer = {
        "best_candidate": best,
        "alternative_candidates": active_candidates[1:5] if len(active_candidates) > 1 else [],
        "region_confidence": level,
        "place_type_confidence": level,
        "venue_confidence": level,
        "key_evidence": [
            e.get("description", "")
            for e in state.get("evidence_log", [])
            if e.get("evidence_type") == "supporting"
        ][-5:],
        "unresolved_uncertainties": [],
        "reasoning_summary": (
            response.content if isinstance(response.content, str)
            else str(response.content)
        ),
    }

    return {
        "final_answer": final_answer,
        "phase": "complete",
        "messages": [response],
    }
