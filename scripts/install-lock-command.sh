#!/bin/sh
set -eu

INSTALL_PATH="/usr/local/sbin/devicelocker-lock"
SPIKE_PATH="/usr/local/sbin/devicelocker-lock-spike"
INSTALL_DIR="$(dirname "$INSTALL_PATH")"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer needs root privileges. Re-run with sudo:" >&2
  echo "  sudo $0" >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR"

cat > "$INSTALL_PATH" <<'SCRIPT'
#!/bin/sh
exec /usr/bin/pmset displaysleepnow
SCRIPT

chown root:wheel "$INSTALL_PATH"
chmod 755 "$INSTALL_PATH"

cp "$SCRIPT_DIR/lock-spike.sh" "$SPIKE_PATH"
chown root:wheel "$SPIKE_PATH"
chmod 755 "$SPIKE_PATH"

echo "Installed $INSTALL_PATH"
ls -l "$INSTALL_PATH"
echo "Installed $SPIKE_PATH"
ls -l "$SPIKE_PATH"
