#!/bin/sh
set -eu

LABEL="com.devicelocker.locktest"
TARGET_PLIST="/Library/LaunchDaemons/$LABEL.plist"

if [ "$(id -u)" -ne 0 ]; then
  echo "This uninstaller needs root privileges. Re-run with sudo:" >&2
  echo "  sudo $0" >&2
  exit 1
fi

launchctl bootout system "$TARGET_PLIST" >/dev/null 2>&1 || true
rm -f "$TARGET_PLIST"
echo "Removed $TARGET_PLIST"
