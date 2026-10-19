from dataclasses import replace

import pytest

from astra_sentinel import Planner, build_default_runtime
from astra_sentinel.config import default_config
from astra_sentinel.core.models import ResultStatus
from astra_sentinel.core.plan import PlanExecutor, PlanStatus
from astra_sentinel.llm import (
    InterpretationStatus,
    LLMGoalService,
    LLMOutputError,
    LLMProviderError,
)


class StubProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompt = ""

    def generate_structured_goal(self, prompt: str) -> str:
        self.prompt = prompt
        return self.response


class FailingProvider:
    def generate_structured_goal(self, prompt: str) -> str:
        raise LLMProviderError("provider unavailable")


def service(response: str) -> tuple[LLMGoalService, StubProvider]:
    provider = StubProvider(response)
    return LLMGoalService(provider, Planner.supported_goal_types), provider


def test_natural_language_response_becomes_existing_planner_goal(tmp_path):
    llm, provider = service('{"goal":"create_directory","parameters":{"path":"sample"}}')
    dispatcher, _ = build_default_runtime(default_config())

    interpretation = llm.interpret("Create a folder named sample.")
    plan = Planner(dispatcher.registry).create_plan(interpretation.goal)

    assert interpretation.status is InterpretationStatus.GOAL
    assert plan.actions[0].capability == "filesystem.create_dir"
    assert "create_directory" in provider.prompt
    assert "shell commands" in provider.prompt


def test_multi_step_natural_language_response_uses_existing_project_goal(tmp_path):
    llm, _ = service('{"goal":"create_project","parameters":{"path":"demo","readme":true}}')
    dispatcher, _ = build_default_runtime(default_config())

    interpretation = llm.interpret("Create a project named demo with a README.")
    plan = Planner(dispatcher.registry).create_plan(interpretation.goal)

    assert [action.capability for action in plan.actions] == ["filesystem.create_dir", "filesystem.create_file"]


def test_unsupported_and_ambiguous_responses_do_not_create_goals():
    unsupported, _ = service('{"goal":"run_arbitrary_shell_command","parameters":{}}')
    ambiguous, _ = service('{"status":"needs_clarification","missing":["path"]}')

    assert unsupported.interpret("Run a shell command").status is InterpretationStatus.UNSUPPORTED
    clarification = ambiguous.interpret("Create a folder")
    assert clarification.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert clarification.goal is None


def test_malformed_response_and_provider_failure_are_controlled():
    malformed, _ = service("not json")
    unavailable = LLMGoalService(FailingProvider(), Planner.supported_goal_types)

    with pytest.raises(LLMOutputError):
        malformed.interpret("Create a folder")
    with pytest.raises(LLMProviderError):
        unavailable.interpret("Create a folder")


def test_llm_goal_still_obeys_existing_sentinel_resource_policy(tmp_path):
    permitted = tmp_path / "permitted"
    permitted.mkdir()
    config = replace(default_config(), resource_rules={"cli": (permitted,)})
    dispatcher, _ = build_default_runtime(config)
    llm, _ = service('{"goal":"create_directory","parameters":{"path":"not-permitted"}}')

    interpretation = llm.interpret("Create a folder named not-permitted")
    result = PlanExecutor(dispatcher).execute(Planner(dispatcher.registry).create_plan(interpretation.goal))

    assert result.final_status is PlanStatus.FAILED
    assert result.action_results["create_directory"].status is ResultStatus.DENIED
    assert not (tmp_path / "not-permitted").exists()


def test_markdown_wrapped_response_parses_successfully():
    fenced_response = "```json\n{\"goal\":\"create_directory\",\"parameters\":{\"path\":\"sample\"}}\n```"
    llm, _ = service(fenced_response)
    interpretation = llm.interpret("Create folder sample")
    assert interpretation.status is InterpretationStatus.GOAL
    assert interpretation.goal.goal == "create_directory"
    assert interpretation.goal.parameters == {"path": "sample"}
