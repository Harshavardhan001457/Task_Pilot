"""Strict natural-language to structured-goal boundary."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from astra_sentinel.core.planner import Goal, PlanningError

from astra_sentinel.llm.providers import LLMProvider


class LLMOutputError(ValueError):
    """Raised when an LLM response cannot be accepted as structured intent."""


class InterpretationStatus(StrEnum):
    GOAL = "goal"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class GoalInterpretation:
    status: InterpretationStatus
    goal: Goal | None = None
    missing: tuple[str, ...] = ()
    message: str = ""


def _extract_json_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1]).strip()
    if not (cleaned.startswith("{") and cleaned.endswith("}")):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and start < end:
            cleaned = cleaned[start : end + 1]
    return cleaned


class LLMGoalService:
    def __init__(self, provider: LLMProvider, supported_goal_types: tuple[str, ...]) -> None:
        self._provider = provider
        self._supported_goal_types = tuple(supported_goal_types)

    def interpret(self, user_text: str, *, requester: str = "cli") -> GoalInterpretation:
        if not isinstance(user_text, str) or not user_text.strip():
            raise LLMOutputError("natural-language request must be a non-empty string")
        return self.parse_response(self._provider.generate_structured_goal(self._prompt(user_text)), requester=requester)

    def parse_response(self, response: str, *, requester: str = "cli") -> GoalInterpretation:
        if not isinstance(response, str):
            raise LLMOutputError("LLM response must be a string")
        cleaned_json = _extract_json_text(response)
        try:
            document: Any = json.loads(cleaned_json)
        except (TypeError, json.JSONDecodeError) as error:
            raise LLMOutputError("LLM response is not valid JSON") from error
        if not isinstance(document, dict):
            raise LLMOutputError("LLM response must be a JSON object")

        status = document.get("status", InterpretationStatus.GOAL)
        if status == InterpretationStatus.NEEDS_CLARIFICATION:
            missing = document.get("missing")
            if not isinstance(missing, list) or not missing or not all(isinstance(item, str) and item for item in missing):
                raise LLMOutputError("clarification response must include missing fields")
            return GoalInterpretation(InterpretationStatus.NEEDS_CLARIFICATION, missing=tuple(missing))
        if status == InterpretationStatus.UNSUPPORTED:
            message = document.get("message", "Request is unsupported")
            if not isinstance(message, str):
                raise LLMOutputError("unsupported response message must be a string")
            return GoalInterpretation(InterpretationStatus.UNSUPPORTED, message=message)
        if status != InterpretationStatus.GOAL:
            raise LLMOutputError("LLM response has an invalid status")

        try:
            goal = Goal(document["goal"], document.get("parameters", {}), requester=requester)
        except (KeyError, PlanningError) as error:
            raise LLMOutputError("LLM response does not contain a valid goal") from error
        if goal.goal not in self._supported_goal_types:
            return GoalInterpretation(InterpretationStatus.UNSUPPORTED, message=f"Unsupported goal: {goal.goal}")
        return GoalInterpretation(InterpretationStatus.GOAL, goal=goal)

    def _prompt(self, user_text: str) -> str:
        goals = ", ".join(self._supported_goal_types)
        return (
            "Convert the user request into one ASTRA JSON object. "
            f"Allowed goals: {goals}. Return either "
            '{"goal":"<allowed goal>","parameters":{...}}, '
            '{"status":"needs_clarification","missing":["field"]}, or '
            '{"status":"unsupported","message":"reason"}. '
            "Never return shell commands, capabilities, authorization decisions, or executable paths. "
            f"User request: {user_text}"
        )
