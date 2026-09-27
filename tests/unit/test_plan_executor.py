import pytest
from dataclasses import replace

from astra_sentinel import build_default_runtime
from astra_sentinel.cli import run_cli
from astra_sentinel.config import default_config
from astra_sentinel.core.models import ActionRequest, ResultStatus
from astra_sentinel.core.plan import ActionPlan, ActionPlanItem, PlanExecutor, PlanFailurePolicy, PlanStatus


def test_plan_executor_runs_dependent_actions_and_skips_on_failure(tmp_path, monkeypatch):
    dispatcher, _ = build_default_runtime(default_config())
    executor = PlanExecutor(dispatcher)

    plan = ActionPlan(
        plan_id="plan-1",
        description="Create a project folder and a file",
        requester="cli",
        failure_policy=PlanFailurePolicy.CONTINUE,
        actions=[
            ActionPlanItem(action_id="a1", capability="filesystem.create_dir", parameters={"path": "project"}),
            ActionPlanItem(action_id="a2", capability="filesystem.create_file", parameters={"path": "project/notes.txt"}, depends_on=["a1"]),
            ActionPlanItem(action_id="a3", capability="filesystem.create_dir", parameters={"path": "project"}),
        ],
    )

    result = executor.execute(plan)
    assert result.final_status is PlanStatus.PARTIAL_SUCCESS
    assert result.failed_action_ids == ["a3"]
    assert result.skipped_action_ids == []
    assert (tmp_path / "project").is_dir()
    assert (tmp_path / "project" / "notes.txt").is_file()


def test_plan_executor_rejects_circular_dependencies(tmp_path, monkeypatch):
    dispatcher, _ = build_default_runtime(default_config())
    executor = PlanExecutor(dispatcher)

    plan = ActionPlan(
        plan_id="plan-2",
        description="Circular plan",
        requester="cli",
        failure_policy=PlanFailurePolicy.STOP,
        actions=[
            ActionPlanItem(action_id="a1", capability="filesystem.create_dir", parameters={"path": "one"}, depends_on=["a2"]),
            ActionPlanItem(action_id="a2", capability="filesystem.create_dir", parameters={"path": "two"}, depends_on=["a1"]),
        ],
    )

    with pytest.raises(ValueError):
        executor.validate_plan(plan)


def test_invalid_plan_returns_structured_failure(tmp_path, monkeypatch):
    dispatcher, _ = build_default_runtime(default_config())
    result = PlanExecutor(dispatcher).execute(ActionPlan(
        plan_id="invalid",
        description="Invalid plan",
        requester="cli",
        actions=(ActionPlanItem("a1", "unknown.capability"),),
    ))
    assert result.final_status is PlanStatus.FAILED
    assert result.summary.startswith("Plan validation failed:")


def test_rollback_runs_in_reverse_order_for_created_file_and_directory(tmp_path, monkeypatch):
    dispatcher, _ = build_default_runtime(default_config())
    result = PlanExecutor(dispatcher).execute(ActionPlan(
        plan_id="rollback",
        description="Rollback created resources after failure",
        requester="cli",
        failure_policy=PlanFailurePolicy.CONTINUE,
        rollback_on_failure=True,
        actions=(
            ActionPlanItem("directory", "filesystem.create_dir", {"path": "rollback"}),
            ActionPlanItem("file", "filesystem.create_file", {"path": "rollback/item.txt"}, depends_on=("directory",)),
            ActionPlanItem("failure", "filesystem.create_dir", {"path": "rollback"}),
        ),
    ))
    assert result.final_status is PlanStatus.PARTIAL_SUCCESS
    assert list(result.rollback_results) == ["file", "directory"]
    assert all(item.status is ResultStatus.SUCCESS for item in result.rollback_results.values())
    assert not (tmp_path / "rollback").exists()


def test_cli_returns_to_prompt_after_invalid_plan(tmp_path, monkeypatch):
    dispatcher, _ = build_default_runtime(default_config())
    commands = iter(['plan {"plan_id":"bad","description":"bad","actions":[{"action_id":"a1","capability":"unknown"}]}', "exit"])
    output: list[str] = []
    run_cli(dispatcher, input_fn=lambda _: next(commands), output_fn=output.append)
    assert output == ["[PLAN] FAILED: Plan validation failed: unknown capability in plan: unknown"]


def test_resource_rules_allow_configured_root_and_deny_other_root(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    config = default_config()
    config = replace(config, resource_rules={"cli": (allowed,)})
    dispatcher, _ = build_default_runtime(config)
    allowed_result = dispatcher.dispatch(ActionRequest.create(
        capability="filesystem.create_file", parameters={"path": "allowed/file.txt"}, requester="cli"
    ))
    denied_result = dispatcher.dispatch(ActionRequest.create(
        capability="filesystem.create_file", parameters={"path": "outside.txt"}, requester="cli"
    ))
    assert allowed_result.status is ResultStatus.SUCCESS
    assert denied_result.status is ResultStatus.DENIED

    denied_config = replace(config, policy=replace(config.policy, explicitly_denied_capabilities=frozenset({"filesystem.create_file"})))
    denied_dispatcher, _ = build_default_runtime(denied_config)
    assert denied_dispatcher.dispatch(ActionRequest.create(
        capability="filesystem.create_file", parameters={"path": "allowed/denied.txt"}, requester="cli"
    )).status is ResultStatus.DENIED


def test_plan_and_rollback_audit_include_context(tmp_path, monkeypatch):
    dispatcher, audit = build_default_runtime(default_config())
    result = PlanExecutor(dispatcher).execute(ActionPlan(
        plan_id="audit-plan",
        description="Audit plan",
        requester="cli",
        failure_policy=PlanFailurePolicy.CONTINUE,
        rollback_on_failure=True,
        actions=(
            ActionPlanItem("directory", "filesystem.create_dir", {"path": "audit"}),
            ActionPlanItem("failure", "filesystem.create_dir", {"path": "audit"}),
        ),
    ))
    assert result.rollback_results["directory"].status is ResultStatus.SUCCESS
    assert any(event.plan_id == "audit-plan" and event.action_id == "failure" and event.event_type == "NORMAL_ACTION" for event in audit.events)
    assert any(event.plan_id == "audit-plan" and event.action_id == "directory" and event.event_type == "ROLLBACK_ACTION" and event.rollback_status == "ROLLED_BACK" for event in audit.events)


def test_cli_inspection_commands(tmp_path, monkeypatch):
    dispatcher, _ = build_default_runtime(default_config())
    commands = iter(["help", "show capabilities", "show permissions", "show resources", "show config", "show apps", "exit"])
    output: list[str] = []
    run_cli(dispatcher, input_fn=lambda _: next(commands), output_fn=output.append)
    assert output[0].startswith("Available commands:")
    assert "filesystem.create_dir" in output[1]
    assert "filesystem.write" in output[2]
    assert "Configuration" in output[4]
