"""LangGraph node functions for each phase of the geolocation investigation."""

from __future__ import annotations

import base64
import json
import os
import sys

from langchain_core.messages import HumanMessage, SystemMessage

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


def _log(message: str) -> None:
    """Print a timestamped progress message to stderr so it appears immediately."""
    print(f"  → {message}", file=sys.stderr, flush=True)


def _inject_image_path(tool_name: str, tool_args: dict, image_path: str) -> dict:
    """Override the image_path argument for image tools with the real path."""
    if tool_name in IMAGE_PATH_TOOLS and "image_path" in tool_args:
        tool_args = {**tool_args, "image_path": image_path}
    return tool_args


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
    if clues:
        parts.append(f"## Extracted Clues ({len(clues)})")
        for c in clues:
            parts.append(f"- [{c.get('category', '?')}] {c.get('description', '?')} "
                         f"(confidence: {c.get('confidence', '?')})")

    hypotheses = state.get("hypotheses", [])
    active = [h for h in hypotheses if h.get("status") == "active"]
    if active:
        parts.append(f"\n## Active Hypotheses ({len(active)})")
        for h in sorted(active, key=lambda x: x.get("confidence", 0), reverse=True):
            parts.append(f"- [{h.get('level', '?')}] {h.get('description', '?')} "
                         f"(confidence: {h.get('confidence', '?')})")

    candidates = state.get("candidates", [])
    active_cands = [c for c in candidates if not c.get("eliminated")]
    if active_cands:
        parts.append(f"\n## Active Candidates ({len(active_cands)})")
        for c in sorted(active_cands, key=lambda x: x.get("confidence", 0), reverse=True):
            parts.append(f"- {c.get('name', '?')} @ ({c.get('latitude', '?')}, "
                         f"{c.get('longitude', '?')}) confidence: {c.get('confidence', '?')}")

    evidence = state.get("evidence_log", [])
    if evidence:
        recent = evidence[-10:]
        parts.append(f"\n## Recent Evidence ({len(evidence)} total, showing last {len(recent)})")
        for e in recent:
            prefix = {"supporting": "+", "contradicting": "-", "neutral": "~"}.get(
                e.get("evidence_type", ""), "?"
            )
            parts.append(f"  {prefix} {e.get('description', '?')} [source: {e.get('source', '?')}]")

    eliminated = state.get("eliminated", [])
    if eliminated:
        parts.append(f"\n## Eliminated Candidates ({len(eliminated)})")
        for e in eliminated:
            parts.append(f"- {e.get('name', '?')}: {e.get('elimination_reason', '?')}")

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
    """LLM inspects the image with vision and extracts visual clues."""
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

    _log("Sending image to vision LLM for analysis...")

    for round_num in range(5):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        new_messages.append(response)

        if not response.tool_calls:
            _log("Analysis complete")
            break

        from langchain_core.messages import ToolMessage

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

    _log(f"Total clues extracted: {len(collected_clues)}")

    return {
        "clues": collected_clues,
        "phase": "hypothesize",
        "messages": new_messages,
    }


def generate_hypotheses(state: dict) -> dict:
    """LLM proposes or refines hypotheses based on accumulated clues and evidence."""
    iteration = state.get("iteration", 0)
    print(f"\n{'='*60}", file=sys.stderr, flush=True)
    print(f"PHASE: Generate Hypotheses (iteration {iteration})", file=sys.stderr, flush=True)
    print(f"{'='*60}", file=sys.stderr, flush=True)

    llm = get_llm()

    from geolocation_agent.tools.evidence_tracker import add_hypothesis as add_hyp_tool

    llm_with_tools = llm.bind_tools([add_hyp_tool])

    state_summary = _get_state_summary(state)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"{HYPOTHESIZE_PROMPT}\n\n{state_summary}\n\n"
                     "Based on the clues and evidence above, propose or refine hypotheses. "
                     "Use the add_hypothesis tool to record each one."),
    ]

    collected_hypotheses = list(state.get("hypotheses", []))
    new_messages = []

    _log("Generating location hypotheses...")

    for _ in range(5):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        new_messages.append(response)

        if not response.tool_calls:
            break

        from langchain_core.messages import ToolMessage

        for tool_call in response.tool_calls:
            if tool_call["name"] == "add_hypothesis":
                tool_result = add_hyp_tool.invoke(tool_call["args"])
                messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))
                try:
                    hyp_data = json.loads(tool_result)
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
    """LLM investigates hypotheses using all available tools."""
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
        "expected value right now. Record all evidence.",
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
    new_messages = []

    max_tool_rounds = 8

    for round_num in range(max_tool_rounds):
        _log(f"Tool round {round_num + 1}/{max_tool_rounds}...")
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        new_messages.append(response)

        if not response.tool_calls:
            _log("No more tool calls — investigation round complete")
            break

        from langchain_core.messages import ToolMessage

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = _inject_image_path(tool_name, tool_call["args"], image_path)

            display_args = {k: v for k, v in tool_args.items() if k != "image_path"}
            display_str = ", ".join(f"{k}={v!r}" for k, v in display_args.items())
            _log(f"Tool call: {tool_name}({display_str})")

            tool_fn = next((t for t in ALL_TOOLS if t.name == tool_name), None)
            if tool_fn:
                try:
                    tool_result = tool_fn.invoke(tool_args)
                except Exception as exc:
                    _log(f"  Tool error: {exc}")
                    tool_result = json.dumps({"error": str(exc)})
                messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))

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
                        _log(f"  Evidence: {result_data.get('description', '?')}")
                    elif result_id.startswith("cand_"):
                        collected_candidates.append(result_data)
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

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"{REPORT_PROMPT}\n\n{state_summary}\n\n"
                     "Produce your final report now."),
    ]

    response = llm.invoke(messages)

    candidates = state.get("candidates", [])
    active_candidates = [c for c in candidates if not c.get("eliminated")]
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
