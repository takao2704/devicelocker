#!/bin/sh
set -eu

LABEL="com.devicelocker.agent"
PLIST_TARGET="/Library/LaunchDaemons/$LABEL.plist"
CHECK_TARGET="/usr/local/sbin/devicelocker-check"
CONFIG_PATH="/Library/Application Support/DeviceLocker/config.json"
TOKEN_PATH="/Library/Application Support/DeviceLocker/device.token"

if [ "$(id -u)" -ne 0 ]; then
  echo "This command needs root privileges. Re-run with sudo:" >&2
  echo "  sudo $0" >&2
  exit 1
fi

for path in "$PLIST_TARGET" "$CHECK_TARGET" "$CONFIG_PATH" "$TOKEN_PATH"; do
  if [ ! -e "$path" ]; then
    echo "Missing required path: $path" >&2
    exit 1
  fi
done

plutil -lint "$PLIST_TARGET"
launchctl bootout system "$PLIST_TARGET" >/dev/null 2>&1 || true
launchctl bootstrap system "$PLIST_TARGET"
echo "Started $LABEL"
