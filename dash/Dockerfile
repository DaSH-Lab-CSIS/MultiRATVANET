# syntax=docker/dockerfile:1.7
# MultiRATVANET on vsim-base. Build from the REPO ROOT:
#   docker build -f dash/Dockerfile \
#     --build-arg REPO_COMMIT=$(git rev-parse HEAD) \
#     --build-arg REPO_DIRTY=$(test -n "$(git status --porcelain --untracked-files=no)" && echo yes || echo no) \
#     -t multiratvanet:$(git rev-parse --short HEAD) .
ARG BASE_IMAGE=vsim-base:om6.3.0-inet4.6.0-veins5.3.1-s5g1.7.0-sumo1.22.0
FROM ${BASE_IMAGE}

ARG REPO_COMMIT=unknown
ARG REPO_DIRTY=unknown
# Set to 0 to skip the 5-second smoke run at build time
ARG RUN_SMOKE=1

# tools/build.sh and tools/run.sh read these; defaults in the scripts are the anjuna3 paths
ENV OMNETPP_BIN=/opt/vsim/omnetpp/bin \
    INET_DIR=/opt/vsim/inet \
    VEINS_DIR=/opt/vsim/veins \
    SIMU5G_DIR=/opt/vsim/simu5g \
    RESULTS_ROOT=/results

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

COPY --chown=vsim:vsim . /workspace
WORKDIR /workspace
RUN ./tools/build.sh
COPY --chown=vsim:vsim dash/manifest.yaml /opt/dash/manifest.yaml

# Smoke: start the TraCI broker, run one short scenario into a scratch results dir, clean up
RUN if [ "${RUN_SMOKE}" = 1 ]; then \
      veins_launchd -vv -c sumo -L /tmp/smoke_launchd.log >/dev/null 2>&1 & lp=$!; \
      sleep 2; \
      RESULTS_ROOT=/tmp/smoke-results ./tools/run.sh CoveragePriority --sim-time-limit=5s; \
      ls /tmp/smoke-results/*/*.sca; \
      kill $lp || true; rm -rf /tmp/smoke-results; \
    fi

LABEL dash.adapter.contract="0-draft" \
      dash.repo.name="MultiRATVANET" \
      dash.repo.commit="${REPO_COMMIT}" \
      dash.repo.dirty="${REPO_DIRTY}" \
      dash.manifest="/opt/dash/manifest.yaml"
# Entrypoint (tini -> vsim-entrypoint -> launchd on :9999) and CMD are inherited from vsim-base.
