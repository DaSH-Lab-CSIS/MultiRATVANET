#!/usr/bin/env bash
# Build the MultiRATVANET image (and the pinned vsim-base toolchain under it, if missing).
#
#   dash/build-image.sh
#   DOCKER="sudo docker" dash/build-image.sh       # if your user is not in the docker group
#   JOBS=4 dash/build-image.sh                     # limit parallel compile jobs on small machines (INET needs ~1 GB RAM per job)
#
# The first build compiles OMNeT++, INET, Veins, Simu5G and SUMO from pinned sources: expect 1-2 h.
# Tags produced: multiratvanet:<short-commit> and multiratvanet:latest.
set -euo pipefail

DOCKER=${DOCKER:-docker}
BASE=vsim-base:om6.3.0-inet4.6.0-veins5.3.1-s5g1.7.0-dash2-sumo1.22.0
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BASE_DIR=$REPO/docker/base

export DOCKER_BUILDKIT=1   # the vsim-base Dockerfile uses RUN --mount

if $DOCKER image inspect "$BASE" >/dev/null 2>&1; then
    echo "== $BASE already present"
else
    echo "== building $BASE"
    $DOCKER build --build-arg JOBS="${JOBS:-0}" -t "$BASE" "$BASE_DIR"
fi

cd "$REPO"
commit=$(git rev-parse HEAD)
short=$(git rev-parse --short HEAD)
dirty=0; [ -n "$(git status --porcelain --untracked-files=no)" ] && dirty=1

echo "== building multiratvanet:$short (dirty=$dirty)"
$DOCKER build -f dash/Dockerfile \
    --build-arg BASE_IMAGE="$BASE" \
    --build-arg REPO_COMMIT="$commit" \
    --build-arg REPO_DIRTY="$dirty" \
    -t "multiratvanet:$short" -t multiratvanet:latest .

echo "== done: run 'dash/mrv run Sinr --sim-time-limit=30s' to try it"
