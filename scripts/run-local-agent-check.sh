#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TMP_DIR="$ROOT/tmp/local-agent"
CONFIG_PATH="$TMP_DIR/config.json"
TOKEN_PATH="$TMP_DIR/device.token"
STATE_PATH="$TMP_DIR/state.json"
LOCK_LOG="$TMP_DIR/lock.log"
LOCK_STUB="$TMP_DIR/lock-stub.sh"

mkdir -p "$TMP_DIR"

cat > "$TOKEN_PATH" <<'TOKEN'
local-dev-token
TOKEN
chmod 600 "$TOKEN_PATH"

cat > "$LOCK_STUB" <<SCRIPT
#!/bin/sh
echo "\$(date '+%Y-%m-%dT%H:%M:%S%z') lock requested" >> "$LOCK_LOG"
exit 0
SCRIPT
chmod +x "$LOCK_STUB"

cat > "$CONFIG_PATH" <<JSON
{
  "api_base_url": "http://127.0.0.1:8765",
  "check_path": "/v1/check",
  "user_id": "child-001",
  "device_id": "macbook-001",
  "token_path": "$TOKEN_PATH",
  "state_path": "$STATE_PATH",
  "lock_command": "$LOCK_STUB",
  "grace_period_seconds": 60,
  "timeout_seconds": 2,
  "max_usage_delta_seconds": 120
}
JSON

set +e
DEVICELOCKER_CONFIG="$CONFIG_PATH" "$ROOT/bin/devicelocker-check"
status=$?
set -e

echo "State:"
if [ -f "$STATE_PATH" ]; then
  cat "$STATE_PATH"
else
  echo "(missing)"
fi

echo "Lock log:"
if [ -f "$LOCK_LOG" ]; then
  cat "$LOCK_LOG"
else
  echo "(empty)"
fi

exit "$status"
