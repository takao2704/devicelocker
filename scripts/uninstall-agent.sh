#!/bin/sh
set -eu

LABEL="com.devicelocker.agent"
PLIST_TARGET="/Library/LaunchDaemons/$LABEL.plist"
NEWSYSLOG_TARGET="/etc/newsyslog.d/com.devicelocker.conf"

if [ "$(id -u)" -ne 0 ]; then
  echo "This uninstaller needs root privileges. Re-run with sudo:" >&2
  echo "  sudo $0" >&2
  exit 1
fi

launchctl bootout system "$PLIST_TARGET" >/dev/null 2>&1 || true
rm -f "$PLIST_TARGET"
rm -f "$NEWSYSLOG_TARGET"
echo "Removed $PLIST_TARGET"
echo "Removed $NEWSYSLOG_TARGET"
