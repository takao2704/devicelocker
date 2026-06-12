#!/bin/sh
set -eu

CONFIG_PATH="/Library/Application Support/DeviceLocker/config.json"
MONITORED_USER_NAME="${1:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "This command needs root privileges. Re-run with sudo:" >&2
  echo "  sudo $0 yuuto" >&2
  exit 1
fi

if [ -z "$MONITORED_USER_NAME" ]; then
  echo "Usage: $0 monitored_user_name" >&2
  exit 2
fi

if [ ! -f "$CONFIG_PATH" ]; then
  echo "Missing config: $CONFIG_PATH" >&2
  exit 1
fi

if plutil -extract monitored_user_name raw "$CONFIG_PATH" >/dev/null 2>&1; then
  plutil -replace monitored_user_name -string "$MONITORED_USER_NAME" "$CONFIG_PATH"
else
  plutil -insert monitored_user_name -string "$MONITORED_USER_NAME" "$CONFIG_PATH"
fi

plutil -convert json -r "$CONFIG_PATH"
chown root:wheel "$CONFIG_PATH"
chmod 600 "$CONFIG_PATH"

echo "Set monitored_user_name=$MONITORED_USER_NAME in $CONFIG_PATH"
