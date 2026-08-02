#!/usr/bin/env python3
"""Report-only health checks for configurable file-backed operating systems."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class Check:
    id: str
    category: str
    status: str
    summary: str
    evidence: list[str]
    remediation: Optional[str] = None
    human_decision: bool = False


def rank(status: str) -> int:
    return {"PASS": 0, "SKIP": 0, "WARN": 1, "FAIL": 2}[status]


def add(
    checks: list[Check], check_id: str, category: str, status: str,
    summary: str, evidence: list[str], remediation: Optional[str] = None,
    human_decision: bool = False,
) -> None:
    checks.append(Check(check_id, category, status, summary, evidence, remediation, human_decision))


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def resolve(config_path: Path, root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def json_value(payload: Any, dotted_path: str) -> Any:
    value = payload
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def normalize(value: str) -> str:
    value = re.sub(r"`", "", value)
    value = re.sub(r"\s+", " ", value).strip().rstrip(".;:").casefold()
    return value


def markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].split("\n## ", 1)[0]


def markdown_items(text: str, heading: str, checkbox: bool) -> list[str]:
    section = markdown_section(text, heading)
    pattern = r"\s*- \[ \]\s+(.+)" if checkbox else r"\s*-\s+(.+)"
    return [normalize(match.group(1)) for line in section.splitlines() if (match := re.match(pattern, line))]


def date_from_text(text: str, pattern: str) -> Optional[str]:
    try:
        match = re.search(pattern, text, re.MULTILINE)
    except re.error:
        return None
    return match.group(1) if match else None


def render_action(template: str, item: dict[str, Any]) -> str:
    class Missing(dict[str, Any]):
        def __missing__(self, key: str) -> str:
            return ""
    return normalize(template.format_map(Missing({key: str(value) for key, value in item.items()})))


def validate_config(config: Any, config_path: Path) -> tuple[Optional[dict[str, Any]], Optional[Path], list[Check]]:
    checks: list[Check] = []
    if not isinstance(config, dict):
        add(checks, "config.valid", "configuration", "FAIL", "Configuration must be a JSON object.", [str(config_path)])
        return None, None, checks
    missing = [key for key in ("workspace_name", "root", "required_files") if key not in config]
    if missing or not isinstance(config.get("required_files"), list):
        add(checks, "config.valid", "configuration", "FAIL", "Configuration is missing required fields.", [f"missing or invalid: {', '.join(missing or ['required_files'])}"], "Start from the bundled example configuration.", True)
        return None, None, checks
    root_value = Path(str(config["root"])).expanduser()
    root = root_value.resolve() if root_value.is_absolute() else (config_path.parent / root_value).resolve()
    if not root.is_dir():
        add(checks, "config.valid", "configuration", "FAIL", "Configured workspace root does not exist.", [str(root)], "Correct the root path; do not invent a replacement source.", True)
        return None, None, checks
    add(checks, "config.valid", "configuration", "PASS", "Configuration is structurally valid.", [f"workspace: {config['workspace_name']}", f"root: {root}"])
    return config, root, checks


def check_files(checks: list[Check], config: dict[str, Any], root: Path) -> None:
    paths = [resolve(Path("."), root, str(value)) for value in config["required_files"]]
    bad = [str(path) for path in paths if not path.is_file() or not path.stat().st_size or read_text(path) is None]
    if bad:
        add(checks, "workspace.files", "nucleus", "FAIL", "Required operating-system files are missing, empty, or unreadable.", bad, "Restore or correct only the verified required path before relying on this operating system.", True)
    else:
        add(checks, "workspace.files", "nucleus", "PASS", "Required operating-system files are present and readable.", [str(path) for path in paths])


def check_state_and_parity(checks: list[Check], config: dict[str, Any], root: Path) -> None:
    dashboard = config.get("dashboard")
    state = config.get("state")
    if not isinstance(dashboard, dict) or not isinstance(state, dict):
        return
    dashboard_path = resolve(Path("."), root, str(dashboard.get("path", "")))
    state_path = resolve(Path("."), root, str(state.get("path", "")))
    dashboard_text = read_text(dashboard_path)
    try:
        state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        add(checks, "state.json", "state", "FAIL", "Configured structured state is not valid JSON.", [f"{state_path}: {error}"], "Repair only the invalid JSON or configured path.", True)
        return
    if dashboard_text is None:
        add(checks, "dashboard.readable", "state", "FAIL", "Configured dashboard is unreadable.", [str(dashboard_path)], "Restore the dashboard path before comparing state.", True)
        return
    add(checks, "state.json", "state", "PASS", "Configured structured state is valid JSON.", [str(state_path)])

    live = config.get("live_surface")
    if isinstance(live, dict):
        live_path = resolve(Path("."), root, str(live.get("path", "")))
        live_text = read_text(live_path)
        dashboard_date = date_from_text(dashboard_text, str(dashboard.get("date_pattern", "")))
        state_date = json_value(state_payload, str(state.get("date_field", "date")))
        live_date = date_from_text(live_text or "", str(live.get("date_pattern", "")))
        dates = {"live": live_date, "dashboard": dashboard_date, "state": str(state_date) if state_date else None}
        if any(value is None for value in dates.values()):
            add(checks, "state.freshness", "freshness", "WARN", "One or more configured state surfaces lacks a parseable date.", [f"{key}: {value}" for key, value in dates.items()], "Restore a factual date or remove the unsupported freshness rule.", True)
        elif str(dashboard_date) < str(live_date) or str(state_date) < str(live_date):
            add(checks, "state.freshness", "freshness", "WARN", "Dashboard or structured state predates the configured live surface.", [f"{key}: {value}" for key, value in dates.items()], "Confirm current state, then update only the stale support surface(s).", True)
        else:
            add(checks, "state.freshness", "freshness", "PASS", "Configured dates do not show a stale support surface.", [f"{key}: {value}" for key, value in dates.items()])

    parity = config.get("parity")
    if not isinstance(parity, dict):
        return
    dashboard_blockers = markdown_items(dashboard_text, str(parity.get("blockers_heading", "")), False)
    dashboard_actions = markdown_items(dashboard_text, str(parity.get("actions_heading", "")), True)
    blocker_path = str(parity.get("state_blockers_path", ""))
    action_path = str(parity.get("state_actions_path", ""))
    blockers = json_value(state_payload, blocker_path)
    actions = json_value(state_payload, action_path)
    blocker_field = str(parity.get("blocker_item_field", "item"))
    template = str(parity.get("action_template", "[{domain}] {task} - {outcome}"))
    state_blockers = [normalize(str(item.get(blocker_field, ""))) for item in blockers if isinstance(item, dict)] if isinstance(blockers, list) else []
    state_actions = [render_action(template, item) for item in actions if isinstance(item, dict)] if isinstance(actions, list) else []
    if not isinstance(blockers, list) or not isinstance(actions, list):
        add(checks, "dashboard.state-parity", "freshness", "WARN", "Configured parity paths do not resolve to JSON lists.", [f"blockers path: {blocker_path}", f"actions path: {action_path}"], "Correct the parity paths or omit this optional check.", True)
    elif set(dashboard_blockers) != set(state_blockers) or set(dashboard_actions) != set(state_actions):
        evidence = []
        if set(dashboard_blockers) != set(state_blockers):
            evidence.append("dashboard blockers do not match structured state")
        if set(dashboard_actions) != set(state_actions):
            evidence.append("dashboard actions do not match structured state")
        add(checks, "dashboard.state-parity", "freshness", "WARN", "Dashboard and structured state are not fully aligned.", evidence, "Compare the cited fields and approve only a minimal factual alignment patch.", True)
    else:
        add(checks, "dashboard.state-parity", "freshness", "PASS", "Dashboard and structured state agree on configured blockers and actions.", [f"actions: {len(state_actions)}", f"blockers: {len(state_blockers)}"])


def check_governance(checks: list[Check], config: dict[str, Any], root: Path) -> None:
    rules = config.get("governance")
    if not isinstance(rules, list):
        return
    missing: list[str] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        path = resolve(Path("."), root, str(rule.get("path", "")))
        text = read_text(path) or ""
        for term in rule.get("required_terms", []):
            if str(term).casefold() not in text.casefold():
                missing.append(f"{path}: {term}")
    if missing:
        add(checks, "governance.gates", "governance", "FAIL", "Configured governance terms are absent from controlling files.", missing, "Restore only the missing controlling terms after verifying their policy remains current.", True)
    else:
        add(checks, "governance.gates", "governance", "PASS", "Configured governance terms are present.", [f"rules checked: {len(rules)}"])


def check_receipts(checks: list[Check], config: dict[str, Any], root: Path) -> None:
    receipts = config.get("receipts")
    if not isinstance(receipts, dict):
        return
    directory = resolve(Path("."), root, str(receipts.get("directory", "")))
    files = sorted((path for path in directory.glob("*") if path.is_file()), key=lambda path: path.stat().st_mtime) if directory.is_dir() else []
    if not files:
        add(checks, "receipts.recency", "receipts", "WARN", "No receipt is present in the configured receipt directory.", [str(directory)], "Run a report-only review and record a receipt only if the operating system's policy calls for one.")
        return
    core_paths = [resolve(Path("."), root, str(value)) for value in receipts.get("core_paths", [])]
    newest_core = max((path.stat().st_mtime for path in core_paths if path.exists()), default=0)
    latest = files[-1]
    if newest_core and latest.stat().st_mtime < newest_core:
        add(checks, "receipts.recency", "receipts", "WARN", "Latest receipt predates a configured core surface.", [f"latest receipt: {latest}", f"latest core date: {datetime.fromtimestamp(newest_core, timezone.utc).date().isoformat()}"], "Run a report-only review after confirming the current operating state.")
    else:
        add(checks, "receipts.recency", "receipts", "PASS", "Latest receipt is at least as recent as configured core surfaces.", [str(latest)])


def check_native(checks: list[Check], enabled: bool, skipped: bool) -> None:
    if not enabled:
        return
    if skipped:
        add(checks, "runtime.codex-doctor", "runtime", "SKIP", "Native Codex Doctor was skipped by request.", ["--skip-native"])
        return
    candidates = [shutil.which("codex"), "/Applications/ChatGPT.app/Contents/Resources/codex"]
    executable = next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)
    if not executable:
        add(checks, "runtime.codex-doctor", "runtime", "SKIP", "Native Codex Doctor is unavailable in this environment.", ["codex executable not found"])
        return
    try:
        result = subprocess.run([executable, "doctor", "--json"], text=True, capture_output=True, timeout=45, check=False)
        payload = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        add(checks, "runtime.codex-doctor", "runtime", "SKIP", "Native Codex Doctor could not produce a parseable report.", [str(error)])
        return
    status = str(payload.get("overallStatus", "warning")).upper()
    mapped = {"OK": "PASS", "PASS": "PASS", "WARNING": "WARN", "WARN": "WARN", "FAIL": "FAIL"}.get(status, "WARN")
    raw_checks = payload.get("checks", {})
    evidence = [f"{name}: {item.get('summary', '')}" for name, item in raw_checks.items() if isinstance(item, dict) and item.get("status") in {"warning", "fail"}]
    add(checks, "runtime.codex-doctor", "runtime", mapped, f"Native Codex Doctor reported {status.lower()}.", evidence or ["all native checks reported OK"], "Review runtime remediation separately from operating-system policy." if mapped != "PASS" else None)


def build_report(config_path: Path, skip_native: bool) -> dict[str, Any]:
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        checks = [Check("config.valid", "configuration", "FAIL", "Configuration cannot be read as JSON.", [f"{config_path}: {error}"], "Repair the configuration JSON before running the audit.", True)]
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "workspace_name": config_path.stem, "overall_status": "FAIL", "checks": [asdict(check) for check in checks]}
    config, root, checks = validate_config(raw, config_path)
    if config is None or root is None:
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "workspace_name": raw.get("workspace_name", config_path.stem) if isinstance(raw, dict) else config_path.stem, "overall_status": "FAIL", "checks": [asdict(check) for check in checks]}
    check_files(checks, config, root)
    check_state_and_parity(checks, config, root)
    check_governance(checks, config, root)
    check_receipts(checks, config, root)
    check_native(checks, bool(config.get("native_codex", True)), skip_native)
    overall = {0: "PASS", 1: "WARN", 2: "FAIL"}[max((rank(check.status) for check in checks), default=0)]
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "workspace_name": config["workspace_name"], "overall_status": overall, "checks": [asdict(check) for check in checks]}


def render(report: dict[str, Any]) -> str:
    lines = ["AgentOS Doctor", f"Overall: {report['overall_status']}", f"Workspace: {report['workspace_name']}", ""]
    for check in report["checks"]:
        lines.append(f"[{check['status']}] {check['id']} — {check['summary']}")
        lines.extend(f"  evidence: {item}" for item in check["evidence"])
        if check["remediation"]:
            suffix = " (human decision required)" if check["human_decision"] else ""
            lines.append(f"  next: {check['remediation']}{suffix}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a report-only AgentOS health audit.")
    parser.add_argument("--config", required=True, type=Path, help="Path to agentos-doctor JSON configuration.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output.")
    parser.add_argument("--skip-native", action="store_true", help="Skip native codex doctor.")
    args = parser.parse_args()
    report = build_report(args.config.resolve(), args.skip_native)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0 if report["overall_status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    sys.exit(main())
