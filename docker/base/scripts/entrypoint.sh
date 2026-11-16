#!/usr/bin/env bash
# vsim-base entrypoint contract (v1)
#   env:  VSIM_LAUNCHD=1|0        start veins_launchd (TraCI broker) before the command   [default 1]
#         VSIM_LAUNCHD_BIND       bind address   [default 127.0.0.1 — container-local]
#         VSIM_LAUNCHD_PORT       port           [default 9999]
#         VSIM_LOG_DIR            launchd log dir [default /tmp]
#   argv: any command; run with the full toolchain env. Default CMD is `bash`.
set -e
# shellcheck disable=SC1091
# arbitrary --user uid has no writable HOME
[ -w "${HOME:-/nonexistent}" ] || export HOME=/tmp
. /opt/vsim/env.sh

if [ "${VSIM_LAUNCHD:-1}" = "1" ]; then
  bind=${VSIM_LAUNCHD_BIND:-127.0.0.1}; port=${VSIM_LAUNCHD_PORT:-9999}
  # launchd chatter goes to its log file only: container stdout stays clean for machine-readable output
  veins_launchd -vv -c sumo -b "$bind" -p "$port" -L "${VSIM_LOG_DIR:-/tmp}/veins_launchd.log" >>"${VSIM_LOG_DIR:-/tmp}/veins_launchd.out" 2>&1 &
  probe=$bind; [ "$probe" = 0.0.0.0 ] && probe=127.0.0.1
  for _ in $(seq 1 100); do
    (exec 3<>"/dev/tcp/$probe/$port") 2>/dev/null && break
    sleep 0.1
  done || true
fi
exec "$@"
