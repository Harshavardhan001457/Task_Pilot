from dataclasses import replace
from pathlib import Path

import pytest

from astra_sentinel import build_default_runtime
from astra_sentinel.audit.logger import InMemoryAuditLogger
from astra_sentinel.capabilities.real import CreateDir, FindFile, GetFileInfo, IsAppRunning, OpenApp, OpenFile
from astra_sentinel.config import ApplicationConfig, RuntimeConfig, default_config
from astra_sentinel.core.dispatcher import Dispatcher
from astra_sentinel.core.models import ResultStatus
from astra_sentinel.core.registry import CapabilityRegistry
from astra_sentinel.security.permissions import Permission, PermissionGrants
from astra_sentinel.security.policy import PolicyEngine
from tests.conftest import request


def real_dispatcher(root: Path, *, launcher=None, running=None, opener=None, allow_modify=True):
    executable = root / "registered-test-app.exe"
    executable.write_text("test")
    apps = {"testapp": ApplicationConfig(executable.resolve(), executable.name)}
    grants = PermissionGrants({"cli": frozenset({Permission.SYSTEM_READ, Permission.APPLICATION_LAUNCH, Permission.FILESYSTEM_READ, Permission.FILESYSTEM_WRITE})})
    policy = replace(default_config().policy, permission_grants=grants, allow_modify=allow_modify)
    registry = CapabilityRegistry()
    for capability in (OpenApp(apps, launcher, running), IsAppRunning(apps, running), FindFile((root,)), GetFileInfo((root,)), OpenFile((root,), opener), CreateDir((root,))):
        registry.register(capability)
    audit = InMemoryAuditLogger()
    return Dispatcher(registry, PolicyEngine(policy), audit)


def test_registered_application_opens_and_unknown_is_rejected(tmp_path):
    launched: list[Path] = []
    dispatcher = real_dispatcher(tmp_path, launcher=launched.append, running=lambda _name: True)
    assert dispatcher.dispatch(request("application.open_app", {"app": "testapp"})).status is ResultStatus.SUCCESS
    assert launched == [(tmp_path / "registered-test-app.exe").resolve()]
    assert dispatcher.dispatch(request("application.open_app", {"app": "unknown"})).status is ResultStatus.VALIDATION_ERROR


def test_is_registered_app_running(tmp_path):
    dispatcher = real_dispatcher(tmp_path, running=lambda _name: True)
    result = dispatcher.dispatch(request("application.is_app_running", {"app": "testapp"}))
    assert result.status is ResultStatus.SUCCESS and result.data["running"] is True


def test_safe_file_metadata_open_and_find(tmp_path):
    target = tmp_path / "dbms.pdf"
    target.write_text("content")
    opened: list[str] = []
    dispatcher = real_dispatcher(tmp_path, opener=opened.append)
    info = dispatcher.dispatch(request("filesystem.get_file_info", {"path": "dbms.pdf"}))
    assert info.status is ResultStatus.SUCCESS and info.data["extension"] == ".pdf"
    assert dispatcher.dispatch(request("filesystem.find_file", {"name": "dbms.pdf"})).data["matches"] == [str(target.resolve())]
    assert dispatcher.dispatch(request("filesystem.open_file", {"path": "dbms.pdf"})).status is ResultStatus.SUCCESS
    assert opened == [str(target.resolve())]


@pytest.mark.parametrize("capability, parameters", [
    ("filesystem.get_file_info", {"path": "../outside.txt"}),
    ("filesystem.find_file", {"name": "dbms.pdf", "search_root": "../outside"}),
    ("filesystem.create_dir", {"path": "../outside"}),
])
def test_outside_paths_and_traversal_are_rejected(tmp_path, capability, parameters):
    dispatcher = real_dispatcher(tmp_path)
    assert dispatcher.dispatch(request(capability, parameters)).status is ResultStatus.VALIDATION_ERROR


def test_create_directory_is_sandboxed_and_policy_can_prevent_execution(tmp_path):
    dispatcher = real_dispatcher(tmp_path)
    assert dispatcher.dispatch(request("filesystem.create_dir", {"path": "ASTRA_Test"})).status is ResultStatus.SUCCESS
    assert (tmp_path / "ASTRA_Test").is_dir()
    denied = real_dispatcher(tmp_path, allow_modify=False)
    assert denied.dispatch(request("filesystem.create_dir", {"path": "must-not-exist"})).status is ResultStatus.DENIED
    assert not (tmp_path / "must-not-exist").exists()


def test_default_runtime_allows_sandboxed_file_writes_when_workspace_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRA_WORKSPACE", str(tmp_path))
    config = default_config()
    assert config.policy.allow_modify is True
    dispatcher, _ = build_default_runtime(config)
    assert dispatcher.dispatch(request("filesystem.create_dir", {"path": "nested"})).status is ResultStatus.SUCCESS
    assert (tmp_path / "nested").is_dir()


def test_v2_file_and_application_capabilities_use_registry_and_sandbox(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello")
    executable = tmp_path / "registered-test-app.exe"
    executable.write_text("test")
    apps = {"testapp": ApplicationConfig(executable.resolve(), executable.name)}
    grants = PermissionGrants({
        "cli": frozenset({
            Permission.SYSTEM_READ,
            Permission.APPLICATION_LAUNCH,
            Permission.FILESYSTEM_READ,
            Permission.FILESYSTEM_WRITE,
            Permission.FILESYSTEM_MOVE,
        })
    })
    policy = replace(default_config().policy, permission_grants=grants, allow_modify=True)
    registry = CapabilityRegistry()
    from astra_sentinel.capabilities.real import CopyFile, CreateFile, ListRunningApps, MoveFile, RenameFile, GetProcessInfo
    for capability in (
        MoveFile((tmp_path,), allow_overwrite=True),
        CopyFile((tmp_path,), allow_overwrite=True),
        RenameFile((tmp_path,), allow_overwrite=True),
        CreateFile((tmp_path,), allow_overwrite=True),
        ListRunningApps(apps),
        GetProcessInfo(apps),
    ):
        registry.register(capability)
    dispatcher = Dispatcher(registry, PolicyEngine(policy), InMemoryAuditLogger())

    move_result = dispatcher.dispatch(request("filesystem.move_file", {"source": "source.txt", "destination": "moved.txt"}))
    assert move_result.status is ResultStatus.SUCCESS
    assert not source.exists()
    assert (tmp_path / "moved.txt").exists()

    copy_result = dispatcher.dispatch(request("filesystem.copy_file", {"source": "moved.txt", "destination": "copy.txt"}))
    assert copy_result.status is ResultStatus.SUCCESS
    assert (tmp_path / "copy.txt").exists()

    rename_result = dispatcher.dispatch(request("filesystem.rename_file", {"path": "copy.txt", "new_name": "renamed.txt"}))
    assert rename_result.status is ResultStatus.SUCCESS
    assert not (tmp_path / "copy.txt").exists()
    assert (tmp_path / "renamed.txt").exists()

    create_result = dispatcher.dispatch(request("filesystem.create_file", {"path": "fresh.txt"}))
    assert create_result.status is ResultStatus.SUCCESS
    assert (tmp_path / "fresh.txt").exists()

    process_result = dispatcher.dispatch(request("application.get_process_info", {"app": "testapp"}))
    assert process_result.status is ResultStatus.SUCCESS
    assert process_result.data["app"] == "testapp"

    unknown = dispatcher.dispatch(request("application.get_process_info", {"app": "unknown"}))
    assert unknown.status is ResultStatus.VALIDATION_ERROR
