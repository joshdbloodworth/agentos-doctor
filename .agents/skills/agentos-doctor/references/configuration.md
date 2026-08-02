# Configuration

`agentos-doctor.json` is JSON so the bundled script has no third-party
dependency. Paths are relative to the configuration file unless they are
absolute.

Required keys:

- `workspace_name`: label used in reports.
- `root`: root directory for configured relative paths.
- `required_files`: non-empty files that define the operating-system nucleus.

Optional checks:

- `live_surface`: compare its date with dashboard and state dates.
- `dashboard` and `state`: compare Markdown blockers and tasks with JSON lists.
- `governance`: verify required terms remain in controlling files.
- `receipts`: warn when the newest receipt predates a named core surface.
- `native_runtime`: optionally check the selected host runtime. Set
  `{"provider": "codex"}` for `codex doctor --json`,
  `{"provider": "claude"}` for `claude doctor`, or
  `{"provider": "none"}` to omit runtime checks. Choose explicitly when both
  CLIs are installed; AgentOS Doctor must not guess which one is authoritative.

Use dotted paths for JSON values, such as `planning.next_actions`. The parity
template may reference fields on each action object, for example
`"[{domain}] {task} - {outcome}"`. Keep it identical to the Markdown task
format after the checkbox.

The script treats missing optional sections as intentionally unconfigured, not
as a policy failure. Start small; add checks only after the operating files are
stable enough that a warning will be actionable.
