from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def merge_lists(left: list[dict], right: list[dict]) -> list[dict]:
    """Merge two lists of dicts by ID, with right taking precedence for duplicates."""
    merged = {item["id"]: item for item in left}
    for item in right:
        merged[item["id"]] = item
    return list(merged.values())


class AgentState:
    """LangGraph agent state definition.

    Using a class with __annotations__ so LangGraph can pick up the typed fields.
    Each field uses Annotated with a reducer where appropriate.
    """

    image_path: str
    side_info: str
    messages: Annotated[list[BaseMessage], add_messages]
    clues: Annotated[list[dict], merge_lists]
    hypotheses: Annotated[list[dict], merge_lists]
    candidates: Annotated[list[dict], merge_lists]
    evidence_log: Annotated[list[dict], merge_lists]
    eliminated: Annotated[list[dict], merge_lists]
    iteration: int
    max_iterations: int
    phase: str
    confidence: float
    final_answer: dict | None
