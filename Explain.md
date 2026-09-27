# ASTRA V3 and V4 explanation

## V3: structured planning without execution authority

V3 separates intent from execution:

```text
Structured Goal -> Planner -> ActionPlan -> PlanExecutor -> Dispatcher -> Result
```

`Goal` contains a supported goal type and parameters. The `Planner` translates
that goal only into registered, known capabilities. It currently supports
`create_directory` and `create_project`; the latter can add a dependent README
creation action.

The planner reuses existing plan validation for generated action parameters and
dependency structure. It does not dispatch actions, read system state,
authorize requests, or access operating-system APIs.

An `ActionPlan` can be inspected before execution. Inspection displays the plan
identifier, action IDs, capabilities, sanitized parameters, dependencies,
required permissions, risk level, and dependency-respecting execution order.
Inspection does not execute anything.

Manual and planner-generated plans both use `PlanExecutor`. The executor sends
each action to the existing `Dispatcher`, which remains responsible for
validation, policy, resource permissions, risk, confirmation, execution,
verification, audit, and rollback.

The explicit CLI flow is:

```text
goal <structured JSON> -> inspect -> execute
```

## V4.1: natural language as a constrained input

V4.1 adds one boundary before V3:

```text
Natural language
  -> LLM adapter
  -> validated Goal
  -> V3 Planner
  -> ActionPlan
  -> existing Sentinel pipeline
```

The LLM adapter does not plan actions, execute actions, make authorization
decisions, or access the operating system. Its sole responsibility is returning
strict JSON representing a supported `Goal`, an unsupported request, or a
request that needs clarification.

`LLMGoalService` validates provider output before the planner receives it:

- JSON must be an object.
- A goal must use the existing `Goal` model.
- The goal name must be in the planner's supported-goal vocabulary.
- Clarification responses must list missing fields.
- Unsupported, malformed, and provider-failure responses never become plans.

OpenRouter and Groq are isolated behind the same small provider contract. The
selected provider and its API key/model are externally configured with
provider-specific environment settings; secrets are not stored in source code.
The CLI command `ask <natural-language request>` creates and displays a pending
plan only. The user must still use `execute`, after which Sentinel makes all
final security decisions.

## Allowlist configuration

Allowed filesystem roots, application mappings, enabled capabilities, and
permission grants are defined in `astra_sentinel/config/allowlist.py`.
`default_config()` resolves only filesystem roots declared there. If a declared
root is unavailable, filesystem modification is disabled rather than falling
back to another location. Tests temporarily substitute that same allowlist
source; production configuration does not accept an alternate workspace path.
Modification is separately fail-closed and can be explicitly enabled with the
allowlist's modification setting.
