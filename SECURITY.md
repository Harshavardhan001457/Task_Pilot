# Security Policy

## Threat model and trust boundaries

Sentinel treats action requests and their parameters as untrusted. The registry, policy configuration, explicitly registered capability code, and trusted confirmation mechanism (not implemented in Phase 1) are trusted boundaries. Callers, including future planners and LLMs, only produce `ActionRequest` data.

## Forbidden operations

Phase 1 forbids OS interaction, arbitrary command execution, shell/subprocess execution, dynamic import based on input, reflection-driven dispatch, `eval`, `exec`, `compile`, and unsafe deserialization of untrusted input.

## Security assumptions

The running Python environment and installed Sentinel code are trusted. The in-memory audit logger is available during process lifetime but is not durable or tamper-resistant. Policy configuration is constructed locally; malformed externally loaded configuration is not accepted by this phase because no config-file loader exists.

## Known limitations

Authentication, authorization administration, persistent/tamper-evident audit storage, UI-mediated confirmation, rate limiting, and real OS capabilities are intentionally out of scope. The mock capabilities are simulations and make no OS security claims.

## Reporting vulnerabilities

Use the project’s future private security reporting channel. Do not include exploitable details in public issue trackers until a maintainer has acknowledged the report.
