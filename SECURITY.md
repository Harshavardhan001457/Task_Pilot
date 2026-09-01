# Security Policy

## Threat model and trust boundaries

Sentinel treats action requests and their parameters as untrusted. The registry, policy configuration, explicitly registered capability code, and trusted confirmation mechanism (not implemented in Phase 1) are trusted boundaries. Callers, including future planners and LLMs, only produce `ActionRequest` data.

## Forbidden operations

Arbitrary command execution, shell command construction, dynamic import based on input, reflection-driven dispatch, `eval`, `exec`, `compile`, and unsafe deserialization of untrusted input are forbidden. Phase 2 launches only executables selected from trusted configuration by an argument-vector call, and opens only canonical sandbox paths through the native Windows file association API.

## Security assumptions

The running Python environment and installed Sentinel code are trusted. The in-memory audit logger is available during process lifetime but is not durable or tamper-resistant. Policy configuration is constructed locally; malformed externally loaded configuration is not accepted by this phase because no config-file loader exists.

## Known limitations

Authentication, authorization administration, persistent/tamper-evident audit storage, UI-mediated confirmation, rate limiting, and platform parity are out of scope. Pure-Python path checks cannot eliminate filesystem races or post-check filesystem changes.

## Reporting vulnerabilities

Use the project’s future private security reporting channel. Do not include exploitable details in public issue trackers until a maintainer has acknowledged the report.
