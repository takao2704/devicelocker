#!/bin/sh
set -eu

LABEL="com.devicelocker.agent"
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CHECK_SOURCE="$ROOT/bin/devicelocker-check"
PLIST_SOURCE="$ROOT/launchd/$LABEL.plist"
NEWSYSLOG_SOURCE="$ROOT/newsyslog/com.devicelocker.conf"
CHECK_TARGET="/usr/local/sbin/devicelocker-check"
PLIST_TARGET="/Library/LaunchDaemons/$LABEL.plist"
NEWSYSLOG_TARGET="/etc/newsyslog.d/com.devicelocker.conf"
CONFIG_DIR="/Library/Application Support/DeviceLocker"
STATE_DIR="/var/db/devicelocker"
LOG_PATHS="/var/log/devicelocker.log /var/log/devicelocker.err"

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer needs root privileges. Re-run with sudo:" >&2
  echo "  sudo $0" >&2
  exit 1
fi

if [ ! -f "$CHECK_SOURCE" ]; then
  echo "Missing $CHECK_SOURCE" >&2
  exit 1
fi

if [ ! -f "$NEWSYSLOG_SOURCE" ]; then
  echo "Missing $NEWSYSLOG_SOURCE" >&2
  exit 1
fi

mkdir -p /usr/local/sbin /etc/newsyslog.d "$CONFIG_DIR" "$STATE_DIR"
cp "$CHECK_SOURCE" "$CHECK_TARGET"
chown root:wheel "$CHECK_TARGET"
chmod 750 "$CHECK_TARGET"

chown root:wheel "$CONFIG_DIR" "$STATE_DIR"
chmod 750 "$CONFIG_DIR" "$STATE_DIR"

for log_path in $LOG_PATHS; do
  touch "$log_path"
  chown root:wheel "$log_path"
  chmod 640 "$log_path"
done

cp "$PLIST_SOURCE" "$PLIST_TARGET"
chown root:wheel "$PLIST_TARGET"
chmod 644 "$PLIST_TARGET"
plutil -lint "$PLIST_TARGET"

cp "$NEWSYSLOG_SOURCE" "$NEWSYSLOG_TARGET"
chown root:wheel "$NEWSYSLOG_TARGET"
chmod 644 "$NEWSYSLOG_TARGET"
newsyslog -n -f "$NEWSYSLOG_TARGET" >/dev/null

echo "Installed $CHECK_TARGET"
echo "Installed $PLIST_TARGET"
echo "Installed $NEWSYSLOG_TARGET"
echo "Prepared logs: $LOG_PATHS"
echo "Config directory: $CONFIG_DIR"
echo "State directory: $STATE_DIR"
echo "Create config.json and device.token before bootstrapping the daemon."
