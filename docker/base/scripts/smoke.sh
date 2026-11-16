#!/usr/bin/env bash
# Mirrors opp_env's smoke tests: Veins (native 802.11p), veins_inet, Simu5G. Starts its own launchd.
set -euo pipefail
set +u; . /opt/vsim/env.sh; set -u
mode_sfx=""; [ "${BUILD_MODE:-release}" = debug ] && mode_sfx="-d"

log=$(mktemp /tmp/smoke_launchd.XXXXXX)
created=()
for d in "$VEINS_ROOT/examples/veins/results" "$VEINS_INET_ROOT/examples/veins_inet/results" "$SIMU5G_ROOT/simulations/lte/demo/results"; do
  [ -e "$d" ] || created+=("$d")
done
veins_launchd -vv -c sumo -L "$log" >/dev/null 2>&1 & lpid=$!
# remove only the result dirs this run created, so a later run as a different uid can write again
trap 'kill $lpid 2>/dev/null || true; rm -rf "${created[@]}" "$log"' EXIT
for _ in $(seq 1 100); do (exec 3<>/dev/tcp/127.0.0.1/9999) 2>/dev/null && break; sleep 0.1; done

echo "== veins native";   (cd "$VEINS_ROOT/examples/veins" && ./run $mode_sfx -u Cmdenv -c Default --sim-time-limit=30s)
echo "== veins_inet";     (cd "$VEINS_INET_ROOT/examples/veins_inet" && ./run $mode_sfx -c plain -u Cmdenv --sim-time-limit=30s \
                            --allow-object-stealing-on-deletion=true)
echo "== simu5g";     (cd "$SIMU5G_ROOT/simulations/lte/demo"
                      opp_run${mode_sfx:+_dbg} -l "$SIMU5G_ROOT/src/simu5g" -l "$INET_ROOT/src/INET" \
                        -n "$SIMU5G_ROOT/simulations:$SIMU5G_ROOT/src:$INET_ROOT/src" \
                        -c VideoStreaming -r 0 -u Cmdenv --sim-time-limit=10s | tail -n 5)
echo "SMOKE OK"
