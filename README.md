# AgentOS Doctor

AgentOS Doctor is a report-only Codex skill for checking whether a file-backed
agent operating system still tells one consistent story.

It is deliberately separate from native `codex doctor`:

- `codex doctor` checks the Codex installation, authentication, runtime, and
  connectivity.
- AgentOS Doctor checks the operating files an adopter declares: a live work
  surface, dashboard, structured state, governance gates, and optional
  receipts.

It never changes files. A warning identifies evidence and a minimal repair for
a human to approve.

## Quick start

1. Copy `examples/agentos-doctor.example.json` to your operating-system root
   and replace the sample paths and terms with your own.
2. Keep the skill at `.agents/skills/agentos-doctor/` in the repository that
   contains your configuration, or install it through your Codex skill path.
3. Run:

   ```bash
   python3 .agents/skills/agentos-doctor/scripts/agentos_doctor.py --config agentos-doctor.json
   ```

4. Review warnings; do not let the tool make repairs automatically.

Run the included example from this repository with:

```bash
python3 .agents/skills/agentos-doctor/scripts/agentos_doctor.py --config examples/agentos-doctor.example.json --skip-native
```

## What to configure

Start with the smallest stable set of files:

- required operating-system nucleus;
- live work surface and its freshness date;
- dashboard and JSON state with blockers and next actions;
- approval/source-of-truth terms in governance files.

Receipt recency and native Codex runtime checks are optional. Configuration is
documented in the skill's `references/configuration.md`.

## Boundaries

This is a diagnostic and reporting layer, not an autonomous operating system.
It must not choose priorities, move source-of-truth authority, patch files,
send messages, or change external systems. Keep the policy in the adopter's
own files, not in the tool.

## Sharing

This repository is designed to be a GitHub-friendly starter. Before publishing,
replace the sample configuration with no real paths, secrets, customer data, or
organization-specific policy text. Add a license appropriate for the intended
audience.
