#!/usr/bin/env python3
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_STATE = {
    "userId": "child-001",
    "deviceId": "macbook-001",
    "remainingSeconds": 600,
    "isApproved": True,
    "policyVersion": 1,
}


def read_state(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return dict(DEFAULT_STATE)


def write_state(path, state):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(target)


def decide(state, request_body, now):
    usage_delta = int(request_body.get("usageDeltaSeconds") or 0)
    usage_delta = max(0, min(usage_delta, 120))

    if state.get("deviceId") != request_body.get("deviceId"):
        return "deny", "device_disabled"

    remaining = int(state.get("remainingSeconds") or 0)
    remaining = max(0, remaining - usage_delta)
    state["remainingSeconds"] = remaining
    state["lastUsageDeltaSeconds"] = usage_delta
    state["lastUsageReportedAt"] = now

    if not state.get("isApproved", True):
        return "deny", "not_approved"
    if remaining <= 0:
        return "deny", "time_exhausted"
    return "allow", "remaining_time_available"


def make_handler(state_path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DeviceLockerMock/0.1"

        def do_POST(self):
            if self.path != "/v1/check":
                self.send_error(404)
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                self.send_error(400)
                return

            now = int(time.time())
            state = read_state(state_path)
            decision, reason = decide(state, body, now)
            state["policyVersion"] = int(state.get("policyVersion") or 0) + 1
            write_state(state_path, state)

            response = {
                "decision": decision,
                "remainingSeconds": int(state.get("remainingSeconds") or 0),
                "serverTime": now,
                "reason": reason,
                "retryAfterSeconds": 60,
                "policyVersion": state["policyVersion"],
            }
            payload = json.dumps(response, separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            print(f"{self.address_string()} - {fmt % args}")

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Run a local DeviceLocker CheckMacStatus mock API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--state", default="tmp/mock-api-state.json")
    args = parser.parse_args()

    state_path = Path(args.state)
    if not state_path.exists():
        write_state(state_path, dict(DEFAULT_STATE))

    server = ThreadingHTTPServer((args.host, args.port), make_handler(state_path))
    print(f"Mock API listening on http://{args.host}:{args.port}")
    print(f"State file: {state_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
