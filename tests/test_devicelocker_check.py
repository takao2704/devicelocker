import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from importlib.machinery import SourceFileLoader
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "bin" / "devicelocker-check"


def load_module():
    loader = SourceFileLoader("devicelocker_check", str(MODULE_PATH))
    spec = importlib.util.spec_from_loader("devicelocker_check", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class DeviceLockerCheckTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.state_path = self.base / "state.json"
        self.token_path = self.base / "device.token"
        self.lock_path = self.base / "lock"
        self.config_path = self.base / "config.json"
        self.token_path.write_text("secret-token\n", encoding="utf-8")
        self.lock_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.lock_path.chmod(0o755)
        self.write_config()

    def tearDown(self):
        self.tmp.cleanup()

    def write_config(self):
        self.config_path.write_text(json.dumps({
            "api_base_url": "https://example.invalid",
            "user_id": "child-001",
            "device_id": "macbook-001",
            "token_path": str(self.token_path),
            "state_path": str(self.state_path),
            "lock_command": str(self.lock_path),
            "grace_period_seconds": 60,
            "timeout_seconds": 1,
        }), encoding="utf-8")

    def read_state(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def test_allow_updates_state(self):
        response = {
            "decision": "allow",
            "remainingSeconds": 1200,
            "serverTime": 1000,
            "policyVersion": 2,
        }
        with mock.patch.object(self.module, "post_check", return_value=response), \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 0)
        state = self.read_state()
        self.assertEqual(state["last_decision"], "allow")
        self.assertEqual(state["remaining_seconds"], 1200)
        self.assertEqual(state["last_success_at"], 1000)
        self.assertEqual(state["last_success_local_at"], 2000)

    def test_deny_runs_lock(self):
        response = {
            "decision": "deny",
            "remainingSeconds": 0,
            "serverTime": 1000,
        }
        with mock.patch.object(self.module, "post_check", return_value=response), \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 2)
        run.assert_called_once_with([str(self.lock_path)], check=False)
        self.assertEqual(self.read_state()["locked_at"], 2000)

    def test_api_failure_within_grace_does_not_lock(self):
        self.state_path.write_text(json.dumps({"last_success_local_at": 1990}), encoding="utf-8")
        with mock.patch.object(self.module, "post_check", side_effect=self.module.ApiError("offline")), \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 0)
        run.assert_not_called()

    def test_api_failure_after_grace_locks(self):
        self.state_path.write_text(json.dumps({"last_success_local_at": 1000}), encoding="utf-8")
        with mock.patch.object(self.module, "post_check", side_effect=self.module.ApiError("offline")), \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 2)
        run.assert_called_once_with([str(self.lock_path)], check=False)


if __name__ == "__main__":
    unittest.main()
