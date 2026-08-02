---
name: agentos-doctor
description: Audit a configured, file-backed AgentOS or personal operating system without changing it. Use when asked to check operating-file health, source-of-truth drift, dashboard and JSON-state parity, governance gates, receipt recency, or optional Codex or Claude runtime health.
---

# AgentOS Doctor

Run a report-only audit for a configured operating system. Treat the configured
files as authoritative; never infer state from chat history.

## Run

1. Read the repository's `agentos-doctor.json` or another supplied config.
2. Run:

   ```bash
   python3 .agents/skills/agentos-doctor/scripts/agentos_doctor.py --config agentos-doctor.json
   ```

   Add `--json` for machine-readable output. Use `--skip-native` only when the
   environment makes the selected native-runtime check unreliable.

3. Report the overall status first. For each warning or failure, cite the exact
   file or field, the smallest safe repair, and whether a human decision is
   needed.

## Boundaries

- Default to report-only. Do not patch files, create receipts, change routes,
  or touch external systems.
- Keep native `codex doctor` or `claude doctor` findings separate from
  operating-system findings.
- Do not resolve priority conflicts or choose a canonical source when the
  configuration has not already done so.
- Propose a minimal patch only after a human explicitly approves it.

## Configure

Copy `examples/agentos-doctor.example.json` from the repository, then tailor
only the files and parity rules that actually exist in the target system. Set
`native_runtime.provider` to `codex`, `claude`, or `none`; it never guesses
which tool's runtime represents the active environment. Read
`references/configuration.md` when adding optional governance or receipt checks.

## Interpret

- `PASS`: inspected surfaces exist and agree.
- `WARN`: usable but stale, incomplete, or awaiting a human decision.
- `FAIL`: a required file, configuration rule, or required structured state is
  invalid or unavailable.
- `SKIP`: not safely verifiable in the current runtime; do not call it a
  failure.
