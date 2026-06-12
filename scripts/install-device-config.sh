#!/bin/sh
set -eu

CONFIG_DIR="/Library/Application Support/DeviceLocker"
CONFIG_PATH="$CONFIG_DIR/config.json"
TOKEN_PATH="$CONFIG_DIR/device.token"

API_BASE_URL="${API_BASE_URL:-}"
DEVICE_TOKEN="${DEVICE_TOKEN:-}"
USER_ID="${USER_ID:-child-001}"
DEVICE_ID="${DEVICE_ID:-macbook-001}"
MONITORED_USER_NAME="${MONITORED_USER_NAME:-yuuto}"
CHECK_PATH="${CHECK_PATH:-/v1/check}"
GRACE_PERIOD_SECONDS="${GRACE_PERIOD_SECONDS:-60}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-5}"
MAX_USAGE_DELTA_SECONDS="${MAX_USAGE_DELTA_SECONDS:-120}"
LOCK_COMMAND="${LOCK_COMMAND:-/usr/local/sbin/devicelocker-lock}"

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer needs root privileges. Re-run with sudo and env vars:" >&2
  echo "  sudo API_BASE_URL=https://... DEVICE_TOKEN=... $0" >&2
  exit 1
fi

if [ -z "$API_BASE_URL" ]; then
  echo "API_BASE_URL is required." >&2
  exit 2
fi

if [ -z "$DEVICE_TOKEN" ]; then
  echo "DEVICE_TOKEN is required." >&2
  exit 2
fi

mkdir -p "$CONFIG_DIR"

cat > "$TOKEN_PATH" <<TOKEN
$DEVICE_TOKEN
TOKEN

cat > "$CONFIG_PATH" <<JSON
{
  "api_base_url": "$API_BASE_URL",
  "check_path": "$CHECK_PATH",
  "user_id": "$USER_ID",
  "device_id": "$DEVICE_ID",
  "monitored_user_name": "$MONITORED_USER_NAME",
  "token_path": "$TOKEN_PATH",
  "state_path": "/var/db/devicelocker/state.json",
  "lock_command": "$LOCK_COMMAND",
  "grace_period_seconds": $GRACE_PERIOD_SECONDS,
  "timeout_seconds": $TIMEOUT_SECONDS,
  "max_usage_delta_seconds": $MAX_USAGE_DELTA_SECONDS
}
JSON

chown -R root:wheel "$CONFIG_DIR"
chmod 750 "$CONFIG_DIR"
chmod 600 "$TOKEN_PATH"
chmod 600 "$CONFIG_PATH"

echo "Installed $CONFIG_PATH"
echo "Installed $TOKEN_PATH"
ls -l "$CONFIG_PATH" "$TOKEN_PATH"
