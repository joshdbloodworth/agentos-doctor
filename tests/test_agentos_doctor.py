import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / ".agents/skills/agentos-doctor/scripts/agentos_doctor.py"
CONFIG = REPO / "examples/agentos-doctor.example.json"


class AgentOSDoctorTests(unittest.TestCase):
    def test_sample_workspace_passes_without_native_runtime_check(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--config", str(CONFIG), "--skip-native", "--json"],
            text=True,
            capture_output=True,
            check=False,
        )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["overall_status"], "PASS")
        statuses = {check["id"]: check["status"] for check in report["checks"]}
        self.assertEqual(statuses["workspace.files"], "PASS")
        self.assertEqual(statuses["dashboard.state-parity"], "PASS")
        self.assertEqual(statuses["governance.gates"], "PASS")
        self.assertNotIn("runtime.codex-doctor", statuses)
        self.assertNotIn("runtime.claude-doctor", statuses)

    def test_invalid_runtime_provider_fails_configuration(self):
        config = json.loads(CONFIG.read_text())
        config["root"] = str(REPO / "examples/sample-workspace")
        config["native_runtime"] = {"provider": "unknown"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agentos-doctor.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--config", str(path), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["overall_status"], "FAIL")
        self.assertEqual(report["checks"][0]["id"], "config.valid")

    def test_claude_discovery_path_points_to_canonical_skill(self):
        claude_skill = REPO / ".claude/skills/agentos-doctor"
        self.assertTrue(claude_skill.is_symlink())
        self.assertEqual(claude_skill.resolve(), (REPO / ".agents/skills/agentos-doctor").resolve())


if __name__ == "__main__":
    unittest.main()
