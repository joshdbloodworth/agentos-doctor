import json
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
