#!/bin/sh
set -eu

LOCK_CMD="/usr/sbin/sysadminctl"
PMSET_CMD="/usr/bin/pmset"

usage() {
  cat <<'EOF'
Usage:
  scripts/lock-spike.sh status
  scripts/lock-spike.sh lock-now
  scripts/lock-spike.sh set-delay-zero
  scripts/lock-spike.sh display-sleep-now

Commands:
  status    Print local lock-related command availability without locking.
  lock-now  Attempt immediate screen lock using sysadminctl.
  set-delay-zero
            Configure screen lock delay to 0 seconds. Prompts for password.
  display-sleep-now
            Put the display to sleep using pmset.

Notes:
  lock-now may interrupt the current desktop session.
  When run as a normal user, sysadminctl may require a password.
  DeviceLocker will eventually run the lock command as root via LaunchDaemon.
  After running lock-now, verify that unlocking requires the user's password.
  display-sleep-now depends on the current screen lock delay setting.
EOF
}

status() {
  sw_vers
  uname -m

  if [ -x "$LOCK_CMD" ]; then
    echo "sysadminctl: $LOCK_CMD"
    "$LOCK_CMD" -screenLock status 2>&1 || true
  else
    echo "sysadminctl: missing"
  fi

  if [ -x "$PMSET_CMD" ]; then
    echo "pmset: $PMSET_CMD"
  else
    echo "pmset: missing"
  fi

  if [ -x "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession" ]; then
    echo "CGSession: present"
  else
    echo "CGSession: missing"
  fi
}

lock_now() {
  if [ ! -x "$LOCK_CMD" ]; then
    echo "sysadminctl is not available" >&2
    exit 1
  fi

  if [ "$(id -u)" -ne 0 ]; then
    echo "warning: running as non-root; sysadminctl may require a password" >&2
  fi

  exec "$LOCK_CMD" -screenLock immediate
}

set_delay_zero() {
  if [ ! -x "$LOCK_CMD" ]; then
    echo "sysadminctl is not available" >&2
    exit 1
  fi

  exec "$LOCK_CMD" -screenLock 0 -password -
}

display_sleep_now() {
  if [ ! -x "$PMSET_CMD" ]; then
    echo "pmset is not available" >&2
    exit 1
  fi

  exec "$PMSET_CMD" displaysleepnow
}

case "${1:-}" in
  status)
    status
    ;;
  lock-now)
    lock_now
    ;;
  set-delay-zero)
    set_delay_zero
    ;;
  display-sleep-now)
    display_sleep_now
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
