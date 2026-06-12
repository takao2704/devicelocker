#!/bin/sh
set -eu

LABEL="com.devicelocker.agent"
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CHECK_SOURCE="$ROOT/bin/devicelocker-check"
PLIST_SOURCE="$ROOT/launchd/$LABEL.plist"
CHECK_TARGET="/usr/local/sbin/devicelocker-check"
PLIST_TARGET="/Library/LaunchDaemons/$LABEL.plist"
CONFIG_DIR="/Library/Application Support/DeviceLocker"
STATE_DIR="/var/db/devicelocker"

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer needs root privileges. Re-run with sudo:" >&2
  echo "  sudo $0" >&2
  exit 1
fi

if [ ! -f "$CHECK_SOURCE" ]; then
  echo "Missing $CHECK_SOURCE" >&2
  exit 1
fi

mkdir -p /usr/local/sbin "$CONFIG_DIR" "$STATE_DIR"
cp "$CHECK_SOURCE" "$CHECK_TARGET"
chown root:wheel "$CHECK_TARGET"
chmod 750 "$CHECK_TARGET"

chown root:wheel "$CONFIG_DIR" "$STATE_DIR"
chmod 750 "$CONFIG_DIR" "$STATE_DIR"

cp "$PLIST_SOURCE" "$PLIST_TARGET"
chown root:wheel "$PLIST_TARGET"
chmod 644 "$PLIST_TARGET"
plutil -lint "$PLIST_TARGET"

echo "Installed $CHECK_TARGET"
echo "Installed $PLIST_TARGET"
echo "Config directory: $CONFIG_DIR"
echo "State directory: $STATE_DIR"
echo "Create config.json and device.token before bootstrapping the daemon."
