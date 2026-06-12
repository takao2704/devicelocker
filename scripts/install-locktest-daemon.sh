#!/bin/sh
set -eu

LABEL="com.devicelocker.locktest"
PLIST_NAME="$LABEL.plist"
SOURCE_PLIST="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/launchd/$PLIST_NAME"
TARGET_PLIST="/Library/LaunchDaemons/$PLIST_NAME"
LOCK_CMD="/usr/local/sbin/devicelocker-lock"

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer needs root privileges. Re-run with sudo:" >&2
  echo "  sudo $0" >&2
  exit 1
fi

if [ ! -x "$LOCK_CMD" ]; then
  echo "$LOCK_CMD is missing or not executable." >&2
  echo "Run this first:" >&2
  echo "  sudo scripts/install-lock-command.sh" >&2
  exit 1
fi

if [ ! -f "$SOURCE_PLIST" ]; then
  echo "Missing source plist: $SOURCE_PLIST" >&2
  exit 1
fi

cp "$SOURCE_PLIST" "$TARGET_PLIST"
chown root:wheel "$TARGET_PLIST"
chmod 644 "$TARGET_PLIST"
plutil -lint "$TARGET_PLIST"

launchctl bootout system "$TARGET_PLIST" >/dev/null 2>&1 || true
echo "Bootstrapping $LABEL. This should trigger a lock if LaunchDaemon execution works."
launchctl bootstrap system "$TARGET_PLIST"
