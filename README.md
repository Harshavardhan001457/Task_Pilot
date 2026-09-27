# ASTRA Sentinel

ASTRA Sentinel is a local-first runtime for executing a deliberately small set of safe, inspectable operating-system actions. It exists to make local automation predictable: callers request named capabilities, policy decides whether they are permitted, and every execution is verified and audited.

## Architecture

```text
CLI
 ↓
ActionRequest
 ↓
Validator
 ↓
Policy
 ↓
Dispatcher
 ↓
Capability
 ↓
OS
```

Plans use the same path for every individual action. There is no arbitrary command execution, dynamic capability loading, or shell escape hatch.

## Features

### Filesystem

- Find files and inspect metadata inside configured roots
- Open approved file types
- Create directories and empty files
- Move, copy, and rename files within the sandbox

### Applications

- Launch registered applications by ID
- Check registered applications and process information

### System

- Read CPU, memory, disk, battery, and system information when supported
- List running applications where supported

### Action plans

- Group several named actions into one request
- Declare dependencies between actions
- Choose `STOP` or `CONTINUE` failure handling
- Inspect a structured `PlanResult`

### Rollback

`rollback_on_failure` enables explicit compensating actions. Supported actions are `filesystem.create_dir`, `filesystem.create_file`, and `filesystem.move_file`. Compensation runs in reverse execution order, only for successful actions created or changed by the plan. Unsupported actions are left unchanged.

Rollback is not a transaction. The original failure is always retained, and rollback attempts are separately audited.

### Security

- Least-privilege named permissions
- Trusted requester identities
- Canonical filesystem resource boundaries
- Explicit capability allowlists
- Risk-aware policy decisions
- Verification after execution
- Fail-closed behavior when configuration or authorization is uncertain

## Security model

ASTRA Sentinel does not accept an executable path or command from a caller. A caller selects a registered capability and supplies schema-validated parameters. Policy checks requester trust, explicit denials, permissions, risk, and resource rules before execution. Capabilities validate their own operating-system inputs and verify their result afterward.

Filesystem access is restricted to configured roots. Resource rules can further limit a requester to selected roots through `RuntimeConfig.resource_rules`. The runtime never treats a textual path prefix as authorization.

## Using the CLI

Set an existing workspace, then start the local CLI:

```powershell
Configure an existing allowed filesystem root in `astra_sentinel/config/allowlist.py`.
python main.py
```

At the `ASTRA >` prompt, use `help` for the concise command list. Inspection commands include `show config`, `show resources`, `show permissions`, `show capabilities`, and `show apps`.

Execute a plan with one JSON command:

```text
plan {"plan_id":"demo","description":"Create a notes file","failure_policy":"STOP","actions":[{"action_id":"file","capability":"filesystem.create_file","parameters":{"path":"notes.txt"}}]}
```

A plan action may depend on another action:

```text
plan {"plan_id":"demo","description":"Create a folder and file","failure_policy":"CONTINUE","rollback_on_failure":true,"actions":[{"action_id":"folder","capability":"filesystem.create_dir","parameters":{"path":"demo"}},{"action_id":"file","capability":"filesystem.create_file","parameters":{"path":"demo\\notes.txt"},"depends_on":["folder"]}]}
```

## Current capabilities

| Capability | Risk | Permission | Rollback |
| --- | --- | --- | --- |
| `filesystem.find_file` | L0 | `filesystem.read` | No |
| `filesystem.get_file_info` | L0 | `filesystem.read` | No |
| `filesystem.open_file` | L1 | `filesystem.read` | No |
| `filesystem.create_dir` | L2 | `filesystem.write` | Yes |
| `filesystem.create_file` | L2 | `filesystem.write` | Yes |
| `filesystem.move_file` | L2 | `filesystem.move` | Yes |
| `filesystem.copy_file` | L2 | `filesystem.write` | No |
| `filesystem.rename_file` | L2 | `filesystem.write` | No |
| `application.open_app` | L1 | `application.launch` | No |
| `application.is_app_running` | L0 | configured policy | No |
| `system.*` | L0 | `system.read` | No |

## Limitations

- Local-first and single-user; no authentication layer
- In-memory audit storage only
- No delete capability
- Rollback is compensating action behavior, not transactional isolation
- Native application and process features vary by platform
- No arbitrary shell, networking, plugins, browser automation, voice, or remote execution

## Roadmap

Future V3 work may explore durable audit storage, stronger identity and confirmation flows, and additional narrowly scoped capabilities. These are not part of the current runtime.

## Development

Install the package with its test dependencies and run the suite:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

Security behavior is regression-tested with temporary directories and explicit policy configurations. See `Explain.md` for the practical user guide.
