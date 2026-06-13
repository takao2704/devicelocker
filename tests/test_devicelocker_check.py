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
            "check_interval_seconds": 60,
            "exhausted_check_interval_seconds": 10,
        }), encoding="utf-8")

    def update_config(self, **updates):
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config.update(updates)
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

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
             mock.patch.object(self.module, "is_screen_locked", return_value=False), \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 0)
        state = self.read_state()
        self.assertEqual(state["last_decision"], "allow")
        self.assertEqual(state["remaining_seconds"], 1200)
        self.assertEqual(state["last_success_at"], 1000)
        self.assertEqual(state["last_success_local_at"], 2000)
        self.assertEqual(state["last_api_check_local_at"], 2000)
        self.assertEqual(state["usage_baseline_local_at"], 2000)

    def test_skips_when_console_user_is_not_monitored_user(self):
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["monitored_user_name"] = "child"
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

        with mock.patch.object(self.module, "get_console_user", return_value="parent-admin"), \
             mock.patch.object(self.module, "post_check") as post_check, \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 0)
        post_check.assert_not_called()
        run.assert_not_called()
        state = self.read_state()
        self.assertEqual(state["last_console_user"], "parent-admin")
        self.assertEqual(state["last_skipped_local_at"], 2000)
        self.assertEqual(state["usage_baseline_local_at"], 2000)

    def test_skips_when_screen_is_locked(self):
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["monitored_user_name"] = "child"
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

        with mock.patch.object(self.module, "get_console_user", return_value="child"), \
             mock.patch.object(self.module, "is_screen_locked", return_value=True), \
             mock.patch.object(self.module, "post_check") as post_check, \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 0)
        post_check.assert_not_called()
        run.assert_not_called()
        state = self.read_state()
        self.assertTrue(state["screen_locked"])
        self.assertEqual(state["last_screen_locked_local_at"], 2000)
        self.assertEqual(state["last_skip_reason"], "screen_locked")
        self.assertEqual(state["usage_baseline_local_at"], 2000)

    def test_is_screen_locked_reads_ioreg(self):
        ioreg_output = b"""<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
  <key>IOConsoleLocked</key>
  <true/>
</dict>
</plist>
"""
        result = mock.Mock(stdout=ioreg_output)

        with mock.patch.object(self.module.subprocess, "run", return_value=result):
            self.assertTrue(self.module.is_screen_locked())

    def test_usage_delta_uses_usage_baseline_after_skip(self):
        config = self.module.load_config(str(self.config_path))
        token = self.module.load_token(str(self.token_path))
        state = {
            "last_success_local_at": 1000,
            "last_usage_reported_local_at": 1000,
            "usage_baseline_local_at": 1990,
        }

        with mock.patch.object(self.module.secrets, "token_urlsafe", return_value="nonce-1"):
            body = self.module.build_request(config, token, state, 2000)

        self.assertEqual(body["usageDeltaSeconds"], 10)

    def test_skips_api_before_normal_check_interval(self):
        self.state_path.write_text(json.dumps({
            "last_decision": "allow",
            "last_success_local_at": 1990,
            "remaining_seconds": 1200,
            "usage_baseline_local_at": 1990,
        }), encoding="utf-8")

        with mock.patch.object(self.module, "post_check") as post_check, \
             mock.patch.object(self.module, "is_screen_locked", return_value=False), \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 0)
        post_check.assert_not_called()
        run.assert_not_called()

    def test_exhausted_state_uses_short_check_interval(self):
        self.state_path.write_text(json.dumps({
            "last_decision": "deny",
            "last_success_local_at": 1990,
            "remaining_seconds": 0,
            "usage_baseline_local_at": 1990,
            "locked_at": 1990,
        }), encoding="utf-8")
        response = {
            "decision": "deny",
            "remainingSeconds": 0,
            "serverTime": 1000,
        }

        with mock.patch.object(self.module, "post_check", return_value=response) as post_check, \
             mock.patch.object(self.module, "is_screen_locked", return_value=False), \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 2)
        post_check.assert_called_once()
        self.assertEqual(post_check.call_args.args[1]["usageDeltaSeconds"], 10)
        run.assert_called_once_with([str(self.lock_path)], check=False)

    def test_deny_runs_lock(self):
        response = {
            "decision": "deny",
            "remainingSeconds": 0,
            "serverTime": 1000,
        }
        with mock.patch.object(self.module, "post_check", return_value=response), \
             mock.patch.object(self.module, "is_screen_locked", return_value=False), \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 2)
        run.assert_called_once_with([str(self.lock_path)], check=False)
        self.assertEqual(self.read_state()["locked_at"], 2000)

    def test_api_failure_within_grace_does_not_lock(self):
        self.update_config(check_interval_seconds=1)
        self.state_path.write_text(json.dumps({"last_success_local_at": 1990}), encoding="utf-8")
        with mock.patch.object(self.module, "post_check", side_effect=self.module.ApiError("offline")), \
             mock.patch.object(self.module, "is_screen_locked", return_value=False), \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 0)
        run.assert_not_called()

    def test_api_failure_after_grace_locks(self):
        self.state_path.write_text(json.dumps({"last_success_local_at": 1000}), encoding="utf-8")
        with mock.patch.object(self.module, "post_check", side_effect=self.module.ApiError("offline")), \
             mock.patch.object(self.module, "is_screen_locked", return_value=False), \
             mock.patch.object(self.module.subprocess, "run") as run, \
             mock.patch.object(self.module.time, "time", return_value=2000):
            code = self.module.main(["devicelocker-check", str(self.config_path)])

        self.assertEqual(code, 2)
        run.assert_called_once_with([str(self.lock_path)], check=False)


if __name__ == "__main__":
    unittest.main()
