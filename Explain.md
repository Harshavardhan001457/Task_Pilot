# ASTRA Sentinel Project Explanation

This repository contains a small secure runtime called ASTRA Sentinel. Its purpose is to allow only a tightly controlled set of actions: opening registered applications, checking whether an application is running, searching for files inside a configured sandbox, retrieving file metadata, opening approved files, and creating directories only when policy allows it.

The project follows a strict pattern:

- Untrusted input is treated as potentially hostile.
- The dispatcher validates requests before they are executed.
- Policy checks permissions and risk before allowing a capability.
- Each capability performs its own validation and verification.
- All actions are audited in memory.

---

## 1. How the project is organized

### Top-level files

- `main.py` – the script entry point for the local CLI. It creates the default runtime and then enters the interactive shell.
- `pyproject.toml` – package metadata and test configuration.
- `README.md` – project overview, architecture notes, and example usage.
- `SECURITY.md` – security model, restrictions, and trust boundaries.

### The runtime package: `astra_sentinel/`

- `__init__.py` – exposes the public runtime API such as `ActionRequest`, `ActionResult`, and `build_default_runtime`.
- `cli.py` – interprets terminal commands and converts them into `ActionRequest` objects.
- `runtime.py` – assembles the default dispatcher, capability registry, and policy engine.

### Audit and security layers

- `astra_sentinel/audit/logger.py` – in-memory audit event recorder used for structured logs.
- `astra_sentinel/security/permissions.py` – defines permissions and per-requester grants.
- `astra_sentinel/security/policy.py` – evaluates whether a capability is allowed for a requester.
- `astra_sentinel/security/risk.py` – defines the risk levels used by policy.
- `astra_sentinel/security/__init__.py` – namespace package for security-related code.

### Capability layer

- `astra_sentinel/capabilities/base.py` – the common `Capability` contract and metadata definition.
- `astra_sentinel/capabilities/real/__init__.py` – publicly exports the real runtime capabilities.
- `astra_sentinel/capabilities/real/applications.py` – application launching and process-checking functionality.
- `astra_sentinel/capabilities/real/filesystem.py` – filesystem operations inside a sandbox.
- `astra_sentinel/capabilities/mock/capabilities.py` – mock capabilities intended for testing the boundary and validation flow.

### Configuration and runtime core

- `astra_sentinel/config/__init__.py` – runtime configuration, root directory policy, and trusted app registry.
- `astra_sentinel/core/dispatcher.py` – central execution boundary; dispatches validated requests to registered capabilities.
- `astra_sentinel/core/errors.py` – stable error codes and request-validation exceptions.
- `astra_sentinel/core/models.py` – request and result models, including trusted metadata generation.
- `astra_sentinel/core/registry.py` – explicit, name-based capability registration.
- `astra_sentinel/core/validator.py` – strict argument-type and shape validation before a request reaches policy evaluation.

### Test suite

- `tests/conftest.py` – shared test fixtures.
- `tests/integration/test_dispatcher.py` – verifies the dispatcher end-to-end behavior.
- `tests/integration/test_real_capabilities.py` – tests real filesystem and app capabilities in realistic conditions.
- `tests/security/test_policy.py` – checks when policy allows or denies actions.
- `tests/security/test_validation.py` – verifies validation and request-shape rules.
- `tests/unit/test_registry.py` – validates registry behaviors.

---

## 2. How the runtime works

The execution flow is:

1. A caller creates an `ActionRequest`.
2. The request is validated against a capability schema.
3. Policy checks the requester identity and required permissions.
4. If allowed, the capability executes.
5. The capability verifies that the result is still safe and valid.
6. The result is recorded in the in-memory audit log.

The runtime intentionally only allows a fixed list of capabilities and does not allow dynamic imports, shell execution, `eval`, `exec`, or arbitrary command building.

---

## 3. Allowed directories for finding/opening files

The filesystem sandbox is configured by the environment variable `ASTRA_WORKSPACE`.

### Rules

- If `ASTRA_WORKSPACE` is set and points to an existing directory, that directory becomes the only allowed filesystem root.
- The code resolves the path to a canonical form using `Path.resolve()` and then checks that the final path is within the configured root using `relative_to()`.
- If the workspace is missing, invalid, or not a directory, the sandbox is treated as empty and file access fails closed.
- Any path outside the configured workspace is denied.
- The `find file` command searches only within the allowed workspace root.
- `open file` only succeeds if the file is inside the workspace and has an approved extension.

### Default behavior

The default config is created in `astra_sentinel/config/__init__.py` and only builds roots from:

```python
workspace = os.environ.get("ASTRA_WORKSPACE")
```

If `ASTRA_WORKSPACE` is not present, filesystem operations will not find any usable directory.

### Approved extensions for opening files

The following file types are allowed to be opened by the built-in file-opening capability:

- `.avi`
- `.bmp`
- `.csv`
- `.doc`
- `.docx`
- `.gif`
- `.jpeg`
- `.jpg`
- `.json`
- `.md`
- `.mp3`
- `.mp4`
- `.pdf`
- `.png`
- `.ppt`
- `.pptx`
- `.txt`
- `.wav`
- `.webp`
- `.xls`
- `.xlsx`
- `.xml`

Files with other extensions are rejected by validation.

---

## 4. Allowed applications to open

Applications are not arbitrary executables. The runtime uses a trusted registry of allowed apps.

### Trusted application registry

The registry is configured in `astra_sentinel/config/__init__.py`.

#### Windows `notepad`

- If running on Windows and `%WINDIR%\System32\notepad.exe` exists, it is registered as `notepad`.

#### VS Code

- If the environment variable `ASTRA_VSCODE_EXECUTABLE` is set and points to a valid file, it is registered as `vscode`.

Example:

```powershell
$env:ASTRA_VSCODE_EXECUTABLE = "C:\Program Files\Microsoft VS Code\Code.exe"
```

Only those app IDs are accepted. The caller never passes the raw executable path to the runtime. It passes the registry key such as `vscode` or `notepad`.

### Application capabilities

The runtime exposes:

- `application.open_app` – launches a registered app.
- `application.is_app_running` – checks whether a registered app is running.

No unregistered executable can be opened.

---

## 5. Allowed permissions

The available permissions are defined in `astra_sentinel/security/permissions.py`:

- `system.read`
- `filesystem.read`
- `filesystem.write`
- `filesystem.delete`
- `application.launch`
- `application.control`

### Default grant model

In `default_config()`, the runtime grants the following to both `cli` and `internal`:

- `system.read`
- `application.launch`
- `filesystem.read`

It does not grant:

- `filesystem.write`
- `filesystem.delete`
- `application.control`

This matters because:

- `filesystem.open_file` requires `filesystem.read` and is allowed.
- `filesystem.find_file` requires `filesystem.read` and is allowed.
- `filesystem.get_file_info` requires `filesystem.read` and is allowed.
- `filesystem.create_dir` requires `filesystem.write` and is denied by default because modify operations are disabled.

### Risk behavior

The project uses the risk enum in `astra_sentinel/security/risk.py`:

- `READ_ONLY` = 0
- `LOW` = 1
- `MODIFY` = 2
- `DESTRUCTIVE` = 3
- `RESTRICTED` = 4

And the policy engine denies destructive or restricted actions and disables modification unless configured with `allow_modify=True`.

---

## 6. How to use the commands

The interactive CLI is in `astra_sentinel/cli.py`.

### Launch the CLI

From the project root:

```powershell
python main.py
```

Then you will see a prompt like:

```text
ASTRA >
```

### Supported commands

The CLI accepts these exact action patterns:

```text
open app <app>
```

Example:

```text
open app vscode
```

```text
is app running <app>
```

Example:

```text
is app running vscode
```

```text
find file <filename>
```

Example:

```text
find file notes.pdf
```

```text
get file info <path>
```

Example:

```text
get file info reports\summary.pdf
```

```text
open file <path>
```

Example:

```text
open file docs\budget.pdf
```

```text
create dir <path>
```

Example:

```text
create dir test_folder
```

### Exit commands

```text
exit
```

or

```text
quit
```

---

## 7. Example Python usage

You can also build the runtime programmatically:

```python
from astra_sentinel import ActionRequest, build_default_runtime

# This runtime honors ASTRA_WORKSPACE and the trusted app registry
# when present.
dispatcher, audit = build_default_runtime()

request = ActionRequest.create(
    capability="application.open_app",
    parameters={"app": "vscode"},
    requester="cli",
)

result = dispatcher.dispatch(request)
print(result.status)
print(result.data)
```

A valid runtime request must include:

- `capability`: the name of the registered capability
- `parameters`: a dictionary of arguments
- `requester`: the requester identity such as `cli` or `internal`

The `ActionRequest.from_untrusted()` helper is used only for the local CLI and allows a limited payload with only `capability` and `parameters`.

---

## 8. Security limits and constraints

The project is intentionally conservative.

- It supports only a small set of capabilities.
- It uses a sandboxed filesystem root.
- It rejects unknown app names.
- It rejects file types outside the approved list.
- It denies modification by default.
- It blocks unknown requesters.
- It records actions in memory, not to a persistent secure log.
- It does not support arbitrary shell commands, delete/rename operations, or dynamic loading of new capabilities.

This means the runtime is safe by design for a narrow local automation workflow, not a general-purpose OS shell.

---

## 9. Effective summary

In practical terms, the project allows:

- Opening only registered applications (`vscode` and `notepad` when configured)
- Finding files only under the `ASTRA_WORKSPACE` directory
- Getting metadata for files within the allowed workspace
- Opening only safe, approved file types from the sandbox
- Creating directories only when write policies are explicitly enabled

It does not allow:

- Arbitrary file access outside the workspace
- Arbitrary executable launching
- Shell command execution
- Unapproved file extensions
- Destructive or unrestricted operations by default

---

## 10. File-by-file summary table

| File / folder | Purpose |
| --- | --- |
| `main.py` | Bootstraps the default runtime and starts the CLI. |
| `pyproject.toml` | Packaging and test configuration. |
| `README.md` | Human-facing overview and usage notes. |
| `SECURITY.md` | Security model and threat assumptions. |
| `astra_sentinel/__init__.py` | Public API exports. |
| `astra_sentinel/cli.py` | Terminal command parsing and result formatting. |
| `astra_sentinel/runtime.py` | Creates the configured runtime and registry. |
| `astra_sentinel/audit/logger.py` | In-memory event logger. |
| `astra_sentinel/capabilities/base.py` | Capability protocol and metadata. |
| `astra_sentinel/capabilities/real/applications.py` | Launch and query trusted apps. |
| `astra_sentinel/capabilities/real/filesystem.py` | Sandbox checks, file search, info retrieval, open, and directory creation. |
| `astra_sentinel/capabilities/real/__init__.py` | Re-export real capabilities. |
| `astra_sentinel/capabilities/mock/capabilities.py` | Simulated capabilities used in tests and boundary checks. |
| `astra_sentinel/config/__init__.py` | Runtime, workspace, and app configuration. |
| `astra_sentinel/core/dispatcher.py` | Orchestrates request validation, policy, execution, and verification. |
| `astra_sentinel/core/errors.py` | Error codes and validation exceptions. |
| `astra_sentinel/core/models.py` | Typed request/result data structures. |
| `astra_sentinel/core/registry.py` | Capability registry. |
| `astra_sentinel/core/validator.py` | Schema validation of action parameters. |
| `astra_sentinel/security/permissions.py` | Permission definitions and grants. |
| `astra_sentinel/security/policy.py` | Policy engine performing allow/deny decisions. |
| `astra_sentinel/security/risk.py` | Risk classifications. |
| `tests/**` | Regression and integration tests for validation, policy, and capabilities. |

---

## 11. Quick start checklist

1. Set the workspace root:

   ```powershell
   $env:ASTRA_WORKSPACE = "C:\path\to\workspace"
   ```

2. Optionally register VS Code:

   ```powershell
   $env:ASTRA_VSCODE_EXECUTABLE = "C:\Program Files\Microsoft VS Code\Code.exe"
   ```

3. Run the CLI:

   ```powershell
   python main.py
   ```

4. Use commands such as:

   ```text
   open app vscode
   find file notes.pdf
   open file docs\notes.pdf
   ```

5. Keep all files inside the configured workspace; anything outside it is denied.

---

This project is designed as a narrow, fail-closed local automation environment: constrained permissions, trust in a small registry, and safe, explicit filesystem access only.

---

## 12. Phase 2 plan upgrade: exact syntax and examples

The latest upgrade adds programmatic and CLI planning support without bypassing the existing security pipeline. The JSON CLI syntax is documented in the Phase 3 section below; the Python API is shown here.

### Import and setup

```python
from astra_sentinel import (
    ActionPlan,
    ActionPlanItem,
    PlanExecutor,
    PlanFailurePolicy,
    build_default_runtime,
)

# Optional: only where filesystem writes are allowed
# $env:ASTRA_WORKSPACE = "C:\\path\\to\\workspace"

dispatcher, _ = build_default_runtime()
executor = PlanExecutor(dispatcher)
```

### Basic plan: dependency + execution

```python
plan = ActionPlan(
    plan_id="plan-demo",
    description="Create a folder and a file inside it",
    requester="cli",
    failure_policy=PlanFailurePolicy.CONTINUE,
    actions=(
        ActionPlanItem(
            action_id="mkdir",
            capability="filesystem.create_dir",
            parameters={"path": "demo"},
        ),
        ActionPlanItem(
            action_id="write",
            capability="filesystem.create_file",
            parameters={"path": "demo/notes.txt"},
            depends_on=("mkdir",),
        ),
    ),
)

result = executor.execute(plan)
print(result.final_status)          # PlanStatus.SUCCESS / PARTIAL_SUCCESS / FAILED
print(result.summary)              # human-readable plan summary
print(result.failed_action_ids)    # list of failed action ids
print(result.skipped_action_ids)   # list of skipped action ids
```

Example output:

```python
PlanStatus.SUCCESS
Plan completed successfully.
[]
[]
```

### STOP behavior

```python
stop_plan = ActionPlan(
    plan_id="stop-demo",
    description="Stop after the first failed action",
    requester="cli",
    failure_policy=PlanFailurePolicy.STOP,
    actions=(
        ActionPlanItem("a1", "filesystem.create_dir", {"path": "alpha"}),
        ActionPlanItem("a2", "filesystem.create_dir", {"path": "alpha"}),
    ),
)

result = executor.execute(stop_plan)
print(result.final_status)
print(result.failed_action_ids)
print(result.skipped_action_ids)
```

Example output:

```python
PlanStatus.FAILED
['a2']
['a2']
```

In STOP mode, the executor stops once an action fails and marks later pending actions as skipped.

### CONTINUE behavior

```python
continue_plan = ActionPlan(
    plan_id="continue-demo",
    description="Keep executing after a failed action",
    requester="cli",
    failure_policy=PlanFailurePolicy.CONTINUE,
    actions=(
        ActionPlanItem("a1", "filesystem.create_dir", {"path": "alpha"}),
        ActionPlanItem("a2", "filesystem.create_dir", {"path": "alpha"}),
        ActionPlanItem("a3", "filesystem.create_dir", {"path": "omega"}),
    ),
)

result = executor.execute(continue_plan)
print(result.final_status)
print(result.failed_action_ids)
print(result.skipped_action_ids)
```

Example output:

```python
PlanStatus.PARTIAL_SUCCESS
['a2']
[]
```

### Dependency validation

```python
bad_plan = ActionPlan(
    plan_id="bad-plan",
    description="Circular dependency example",
    requester="cli",
    failure_policy=PlanFailurePolicy.STOP,
    actions=(
        ActionPlanItem("a1", "filesystem.create_dir", {"path": "one"}, depends_on=("a2",)),
        ActionPlanItem("a2", "filesystem.create_dir", {"path": "two"}, depends_on=("a1",)),
    ),
)

executor.validate_plan(bad_plan)
```

This raises `ValueError` because circular dependencies are rejected before execution.

### Testing commands

From the project root in PowerShell:

```powershell
python -m pytest tests/unit/test_plan_executor.py -q
python -m pytest -q
```

The first command checks the plan executor regression tests; the second runs the full project suite.

## Phase 4 inspection commands

These commands inspect the active runtime. They do not change permissions or configuration.

### Show help

Syntax:

```text
help
```

Expected behavior: displays the concise list of action, plan, inspection, and exit commands.

### Show configuration summary

Syntax:

```text
show config
```

Expected behavior: displays enabled capability count, whether a workspace is configured, resource-policy mode, modify-policy state, and registered application count. Sensitive executable paths are not displayed.

### Show resources

Syntax:

```text
show resources
```

Expected behavior: displays configured resource names for each requester. Resource paths are reduced to directory names in the CLI output.

### Show permissions

Syntax:

```text
show permissions
```

Expected behavior: displays the configured permission grants by requester.

### Show capabilities

Syntax:

```text
show capabilities
```

Expected behavior: displays each enabled capability's name, category, required permission, risk level, and rollback support using capability metadata.

### Show registered applications

Syntax:

```text
show apps
```

Expected behavior: displays registered application IDs only, such as `notepad` or `vscode`; executable paths are not exposed.

### CLI error behavior

Unknown commands display an error and suggest `help`. Expected action and plan failures display concise safe messages. Unexpected failures are logged internally and reported as a safe action failure. The CLI remains at the prompt after errors.

### Audit context

Normal plan actions are audited with `plan_id`, `action_id`, and `event_type=NORMAL_ACTION`. Compensating actions are audited with `event_type=ROLLBACK_ACTION`, the triggering action ID, the compensating capability, and `ROLLED_BACK` or `FAILED` status. Existing per-action audit records remain in place.

## 13. Allowed CLI commands and examples

The CLI currently supports the following command patterns. All requested actions still pass through the dispatcher, validator, policy, and audit flow before being executed.

### Application commands

#### Open a trusted application

Syntax:

```text
open app <app_id>
```

Example:

```text
open app vscode
```

#### Check if a trusted application is running

Syntax:

```text
is app running <app_id>
```

Example:

```text
is app running vscode
```

#### Get process info for a registered application

Syntax:

```text
process info <app_id>
```

Example:

```text
process info vscode
```

### Filesystem commands

#### Find a file within the configured sandbox

Syntax:

```text
find file <filename>
```

Example:

```text
find file notes.pdf
```

#### Get metadata for a file

Syntax:

```text
get file info <path>
```

Example:

```text
get file info docs\notes.pdf
```

#### Open an approved file

Syntax:

```text
open file <path>
```

Example:

```text
open file docs\budget.pdf
```

#### Create a directory inside the allowed sandbox

Syntax:

```text
create dir <path>
```

Example:

```text
create dir test_folder
```

#### Create an empty file inside the allowed sandbox

Syntax:

```text
create file <path>
```

Example:

```text
create file docs\new_report.txt
```

#### Move a file within the allowed sandbox

Syntax:

```text
move file <source_path> <destination_path>
```

Example:

```text
move file docs\old.txt docs\moved.txt
```

#### Copy a file within the allowed sandbox

Syntax:

```text
copy file <source_path> <destination_path>
```

Example:

```text
copy file docs\draft.txt docs\draft_copy.txt
```

#### Rename a file inside the same allowed resource boundary

Syntax:

```text
rename file <path> <new_name>
```

Example:

```text
rename file docs\draft_copy.txt final_draft.txt
```

### System commands

#### List running application names

Syntax:

```text
list running apps
```

Example:

```text
list running apps
```

#### Get CPU usage info

Syntax:

```text
cpu usage
```

Example:

```text
cpu usage
```

#### Get memory usage info

Syntax:

```text
memory usage
```

Example:

```text
memory usage
```

#### Get disk usage info

Syntax:

```text
disk usage
```

Example:

```text
disk usage
```

#### Get battery status

Syntax:

```text
battery status
```

Example:

```text
battery status
```

#### Get minimal system information

Syntax:

```text
system info
```

Example:

```text
system info
```

### Exit commands

```text
exit
```

or

```text
quit
```

---

These are the commands currently available in the ASTRA Sentinel CLI. Any command not listed here is rejected as an invalid or unknown action.

---

## 14. Phase 3 rollback and resource permissions

### Execute a JSON plan

Syntax:

```text
plan <json_object>
```

Example:

```text
plan {"plan_id":"demo","description":"Create a folder and file","failure_policy":"CONTINUE","rollback_on_failure":true,"actions":[{"action_id":"mkdir","capability":"filesystem.create_dir","parameters":{"path":"demo"}},{"action_id":"file","capability":"filesystem.create_file","parameters":{"path":"demo\\notes.txt"},"depends_on":["mkdir"]}]}
```

The CLI always sets the requester to `cli`. Each action must contain a unique `action_id` and a registered capability. The optional `depends_on` list controls execution order. `failure_policy` accepts `STOP` or `CONTINUE`; `rollback_on_failure` defaults to `false`.

### Successful rollback example

```text
plan {"plan_id":"rollback-demo","description":"Create resources then trigger a failure","failure_policy":"CONTINUE","rollback_on_failure":true,"actions":[{"action_id":"dir","capability":"filesystem.create_dir","parameters":{"path":"rollback-demo"}},{"action_id":"file","capability":"filesystem.create_file","parameters":{"path":"rollback-demo\\item.txt"},"depends_on":["dir"]},{"action_id":"fail","capability":"filesystem.create_dir","parameters":{"path":"rollback-demo"}}]}
```

The response reports the original failed action and a `Rollback:` section. The file is removed before the directory, demonstrating reverse-order compensation.

### Rollback failure example

If a created directory is no longer empty, its rollback is refused and the response reports a failed rollback result. The original action failure remains unchanged; rollback does not conceal it.

### Resource permissions

Resource authorization is configured, not hardcoded in capabilities. `RuntimeConfig.resource_rules` maps a requester to allowed canonical directory roots:

```python
RuntimeConfig(
    policy=policy,
    enabled_capabilities=enabled,
    allowed_filesystem_roots=(workspace,),
    resource_rules={"cli": (workspace,)},
)
```

Every filesystem resource is checked against these roots after capability and permission policy checks. Paths outside configured roots, missing requester rules, and uncertain path resolution fail closed. Explicit capability denial still takes precedence.

### Phase 3 testing

```powershell
python -m pytest tests/unit/test_plan_executor.py -q
python -m pytest -q
```
