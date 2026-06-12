#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


DEFAULT_STATE = {
    "userId": "child-001",
    "deviceId": "macbook-001",
    "remainingSeconds": 0,
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


def main():
    parser = argparse.ArgumentParser(description="Adjust local mock DeviceLocker credit.")
    parser.add_argument("command", help="+minutes, stop, start, or status")
    parser.add_argument("--state", default="tmp/mock-api-state.json")
    args = parser.parse_args()

    state_path = Path(args.state)
    state = read_state(state_path)
    command = args.command.strip().lower()

    if command.startswith("+"):
        minutes = int(command[1:])
        state["remainingSeconds"] = int(state.get("remainingSeconds") or 0) + minutes * 60
        state["isApproved"] = True
    elif command == "stop":
        state["isApproved"] = False
    elif command == "start":
        state["isApproved"] = True
    elif command == "status":
        pass
    else:
        raise SystemExit("command must be +minutes, stop, start, or status")

    if command != "status":
        state["policyVersion"] = int(state.get("policyVersion") or 0) + 1
        write_state(state_path, state)

    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
