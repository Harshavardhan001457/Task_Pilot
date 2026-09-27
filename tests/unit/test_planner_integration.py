from dataclasses import replace

from astra_sentinel import Goal, Planner, build_default_runtime
from astra_sentinel.cli import run_cli
from astra_sentinel.config import default_config
from astra_sentinel.core.models import ResultStatus
from astra_sentinel.core.plan import ActionPlan, ActionPlanItem, PlanExecutor, PlanStatus


def test_generated_plan_is_inspected_then_executed_through_sentinel(tmp_path, monkeypatch):
    dispatcher, audit = build_default_runtime(default_config())
    planner = Planner(dispatcher.registry)
    plan = planner.create_plan(Goal("create_project", {"path": "project", "readme": True}, requester="cli"))

    inspection = planner.inspect_plan(plan)

    assert "Plan ID:" in inspection
    assert "filesystem.create_dir" in inspection
    assert "filesystem.create_file" in inspection
    assert "Execution order: create_directory -> create_readme" in inspection
    assert not (tmp_path / "project").exists()

    result = PlanExecutor(dispatcher).execute(plan)

    assert result.final_status is PlanStatus.SUCCESS
    assert (tmp_path / "project" / "README.md").is_file()
    assert {event.plan_id for event in audit.events} == {plan.plan_id}


def test_generated_plan_is_denied_by_existing_resource_policy(tmp_path, monkeypatch):
    permitted = tmp_path / "permitted"
    permitted.mkdir()
    config = default_config()
    config = replace(config, resource_rules={"cli": (permitted,)})
    dispatcher, _ = build_default_runtime(config)
    plan = Planner(dispatcher.registry).create_plan(Goal("create_directory", {"path": "not-permitted"}, requester="cli"))

    result = PlanExecutor(dispatcher).execute(plan)

    assert result.final_status is PlanStatus.FAILED
    assert result.action_results["create_directory"].status is ResultStatus.DENIED
    assert not (tmp_path / "not-permitted").exists()


def test_generated_plan_obeys_existing_confirmation_requirement(tmp_path, monkeypatch):
    dispatcher, _ = build_default_runtime(default_config())
    capability = dispatcher.registry.get("filesystem.create_dir")
    capability.metadata = replace(capability.metadata, confirmation_required=True)
    plan = Planner(dispatcher.registry).create_plan(Goal("create_directory", {"path": "confirm"}, requester="cli"))

    result = PlanExecutor(dispatcher).execute(plan)

    assert result.action_results["create_directory"].status is ResultStatus.CONFIRMATION_REQUIRED
    assert not (tmp_path / "confirm").exists()


def test_manual_and_generated_plans_use_the_same_executor_pipeline(tmp_path, monkeypatch):
    dispatcher, audit = build_default_runtime(default_config())
    generated = Planner(dispatcher.registry).create_plan(Goal("create_directory", {"path": "generated"}, requester="cli"))
    manual = ActionPlan(
        plan_id="manual-plan",
        description="Create manual directory",
        requester="cli",
        actions=(ActionPlanItem("create_directory", "filesystem.create_dir", {"path": "manual"}),),
    )
    executor = PlanExecutor(dispatcher)

    generated_result = executor.execute(generated)
    manual_result = executor.execute(manual)

    assert generated_result.final_status is manual_result.final_status is PlanStatus.SUCCESS
    assert {event.plan_id for event in audit.events} == {generated.plan_id, manual.plan_id}
    assert all(event.action_id == "create_directory" for event in audit.events)


def test_cli_goal_inspect_execute_flow_is_explicit(tmp_path, monkeypatch):
    config = default_config()
    config = replace(config, policy=replace(config.policy, trusted_requesters=frozenset({"cli"})))
    dispatcher, _ = build_default_runtime(config)
    commands = iter((
        'goal {"goal":"create_directory","parameters":{"path":"cli-project"},"requester":"internal"}',
        "inspect",
        "execute",
        "exit",
    ))
    output: list[str] = []

    run_cli(dispatcher, input_fn=lambda _: next(commands), output_fn=output.append)

    assert output[0] == output[1]
    assert "Plan ID:" in output[0]
    assert output[2].startswith("[PLAN] SUCCESS")
    assert (tmp_path / "cli-project").is_dir()
