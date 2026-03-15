"""LangGraph agent definition for the geolocation investigation."""

from __future__ import annotations

import os
from typing import Any

from langgraph.graph import END, StateGraph

from geolocation_agent.config import get_settings
from geolocation_agent.nodes import (
    analyze_image,
    extract_metadata,
    generate_hypotheses,
    investigate,
    produce_report,
    should_continue,
)
from geolocation_agent.state import AgentState


def build_graph() -> StateGraph:
    """Build and compile the geolocation agent graph."""
    graph = StateGraph(AgentState)

    graph.add_node("extract_metadata", extract_metadata)
    graph.add_node("analyze_image", analyze_image)
    graph.add_node("generate_hypotheses", generate_hypotheses)
    graph.add_node("investigate", investigate)
    graph.add_node("produce_report", produce_report)

    graph.set_entry_point("extract_metadata")

    graph.add_edge("extract_metadata", "analyze_image")
    graph.add_edge("analyze_image", "generate_hypotheses")
    graph.add_edge("generate_hypotheses", "investigate")

    graph.add_conditional_edges(
        "investigate",
        should_continue,
        {
            "hypothesize": "generate_hypotheses",
            "report": "produce_report",
        },
    )

    graph.add_edge("produce_report", END)

    return graph


def create_agent():
    """Create a compiled geolocation agent ready for invocation."""
    graph = build_graph()
    return graph.compile()


def run_investigation(
    image_path: str,
    side_info: str = "",
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """Run a full geolocation investigation on an image.

    Args:
        image_path: Path to the image to investigate.
        side_info: Optional additional context about the image.
        max_iterations: Maximum investigation iterations (default from settings).

    Returns:
        The final agent state including the final_answer.
    """
    settings = get_settings()

    agent = create_agent()

    initial_state = {
        "image_path": os.path.abspath(image_path),
        "side_info": side_info or "",
        "messages": [],
        "clues": [],
        "hypotheses": [],
        "candidates": [],
        "evidence_log": [],
        "eliminated": [],
        "tool_history": [],
        "iteration": 0,
        "max_iterations": max_iterations or settings.max_iterations,
        "phase": "extract_metadata",
        "confidence": 0.0,
        "final_answer": None,
    }

    final_state = agent.invoke(initial_state)
    return final_state
