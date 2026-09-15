import pytest

from astra_sentinel import Goal, Planner, build_default_runtime
from astra_sentinel.config import default_config
from astra_sentinel.core.plan import ActionPlan, ActionPlanItem, validate_plan_structure
from astra_sentinel.core.planner import PlanningError
from astra_sentinel.core.registry import CapabilityRegistry


def test_planner_creates_directory_plan_without_executing(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRA_WORKSPACE", str(tmp_path))
    dispatcher, _ = build_default_runtime(default_config())

    plan = Planner(dispatcher.registry).create_plan(Goal("create_directory", {"path": "project"}))

    assert [(action.capability, action.parameters, action.depends_on) for action in plan.actions] == [
        ("filesystem.create_dir", {"path": "project"}, ()),
    ]
    assert not (tmp_path / "project").exists()


def test_planner_creates_project_and_readme_with_dependency(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRA_WORKSPACE", str(tmp_path))
    dispatcher, _ = build_default_runtime(default_config())

    plan = Planner(dispatcher.registry).create_plan(Goal("create_project", {"path": "project", "readme": True}))

    assert [action.capability for action in plan.actions] == ["filesystem.create_dir", "filesystem.create_file"]
    assert plan.actions[1].parameters == {"path": "project/README.md"}
    assert plan.actions[1].depends_on == ("create_directory",)
    assert not (tmp_path / "project").exists()


def test_planner_rejects_unknown_goal(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRA_WORKSPACE", str(tmp_path))
    dispatcher, _ = build_default_runtime(default_config())

    with pytest.raises(PlanningError, match="unsupported goal"):
        Planner(dispatcher.registry).create_plan(Goal("unsupported_goal"))


@pytest.mark.parametrize("parameters", [{}, {"path": 1}, {"path": "../outside"}])
def test_planner_rejects_missing_or_invalid_parameters(tmp_path, monkeypatch, parameters):
    monkeypatch.setenv("ASTRA_WORKSPACE", str(tmp_path))
    dispatcher, _ = build_default_runtime(default_config())

    with pytest.raises(PlanningError):
        Planner(dispatcher.registry).create_plan(Goal("create_directory", parameters))


def test_planner_rejects_unavailable_mapped_capability():
    with pytest.raises(PlanningError, match="unknown capability"):
        Planner(CapabilityRegistry()).create_plan(Goal("create_directory", {"path": "project"}))


def test_plan_structure_rejects_invalid_dependencies(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRA_WORKSPACE", str(tmp_path))
    dispatcher, _ = build_default_runtime(default_config())

    for actions, error in (
        (
            (
                ActionPlanItem("a", "filesystem.create_dir", {"path": "a"}, depends_on=("b",)),
                ActionPlanItem("b", "filesystem.create_dir", {"path": "b"}, depends_on=("a",)),
            ),
            "circular dependencies",
        ),
        ((ActionPlanItem("a", "filesystem.create_dir", {"path": "a"}, depends_on=("a",)),), "cannot depend on itself"),
        ((ActionPlanItem("a", "filesystem.create_dir", {"path": "a"}, depends_on=("missing",)),), "unknown dependency"),
    ):
        with pytest.raises(ValueError, match=error):
            validate_plan_structure(ActionPlan("invalid", "Invalid", "internal", actions), dispatcher.registry)


def test_planning_same_goal_is_logically_deterministic(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRA_WORKSPACE", str(tmp_path))
    dispatcher, _ = build_default_runtime(default_config())
    planner = Planner(dispatcher.registry)

    first = planner.create_plan(Goal("create_project", {"path": "project", "readme": True}))
    second = planner.create_plan(Goal("create_project", {"path": "project", "readme": True}))

    assert first.plan_id == second.plan_id
    assert first.description == second.description
    assert first.actions == second.actions
