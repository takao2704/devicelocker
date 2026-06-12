#!/bin/sh
set -eu

LABEL="com.devicelocker.agent"
PLIST_TARGET="/Library/LaunchDaemons/$LABEL.plist"

if [ "$(id -u)" -ne 0 ]; then
  echo "This command needs root privileges. Re-run with sudo:" >&2
  echo "  sudo $0" >&2
  exit 1
fi

launchctl bootout system "$PLIST_TARGET" >/dev/null 2>&1 || true
echo "Stopped $LABEL"
