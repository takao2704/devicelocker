#!/bin/sh
set -eu

LOCK_CMD="/usr/sbin/sysadminctl"
PMSET_CMD="/usr/bin/pmset"

usage() {
  cat <<'EOF'
Usage:
  scripts/lock-spike.sh status
  scripts/lock-spike.sh set-delay-immediate
  scripts/lock-spike.sh display-sleep-now

Commands:
  status    Print local lock-related command availability without locking.
  set-delay-immediate
            Configure screen lock delay to immediate. Prompts for password.
  display-sleep-now
            Put the display to sleep using pmset.

Notes:
  set-delay-immediate is a setup step, not the recurring lock command.
  DeviceLocker will eventually run display-sleep-now via LaunchDaemon.
  display-sleep-now depends on the current screen lock delay setting.
  After running display-sleep-now, verify that unlocking requires the user's password.
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

set_delay_immediate() {
  if [ ! -x "$LOCK_CMD" ]; then
    echo "sysadminctl is not available" >&2
    exit 1
  fi

  exec "$LOCK_CMD" -screenLock immediate -password -
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
  set-delay-immediate)
    set_delay_immediate
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
