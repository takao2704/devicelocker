#!/bin/sh
set -eu

INSTALL_PATH="/usr/local/sbin/devicelocker-lock"
INSTALL_DIR="$(dirname "$INSTALL_PATH")"

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

echo "Installed $INSTALL_PATH"
ls -l "$INSTALL_PATH"
