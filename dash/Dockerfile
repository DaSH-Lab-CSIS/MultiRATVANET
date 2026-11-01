# syntax=docker/dockerfile:1.7
# MultiRATVANET on vsim-base. Easiest: dash/build-image.sh (also builds the base). By hand, from the REPO ROOT:
#   docker build -f dash/Dockerfile \
#     --build-arg REPO_COMMIT=$(git rev-parse HEAD) \
#     --build-arg REPO_DIRTY=$(test -n "$(git status --porcelain --untracked-files=no)" && echo yes || echo no) \
#     -t multiratvanet:$(git rev-parse --short HEAD) .
# dash2 = INET + Simu5G with the DaSH fixes (docker/base/patches); cellular and multi-NIC 802.11 need them
ARG BASE_IMAGE=vsim-base:om6.3.0-inet4.6.0-veins5.3.1-s5g1.7.0-dash2-sumo1.22.0
FROM ${BASE_IMAGE}

ARG REPO_COMMIT=unknown
ARG REPO_DIRTY=unknown
# Set to 0 to skip the 15-second cellular smoke run at build time
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

# Smoke: start the TraCI broker, run one short all-cellular scenario into a scratch results dir,
# and fail the build unless packets reached the server over LTE/NR (0 = broken cellular path)
RUN if [ "${RUN_SMOKE}" = 1 ]; then \
      veins_launchd -vv -c sumo -L /tmp/smoke_launchd.log >/dev/null 2>&1 & lp=$!; \
      sleep 2; \
      RESULTS_ROOT=/tmp/smoke-results ./tools/run.sh Sinr --sim-time-limit=15s; \
      n=$(awk '$1 == "scalar" && $2 ~ /\.server\.app\[0\]$/ && $3 == "packetReceived:count" {print $4}' /tmp/smoke-results/*/*.sca); \
      echo "smoke: server received ${n:-none} packets over cellular"; \
      [ "${n:-0}" -gt 0 ]; \
      kill $lp || true; rm -rf /tmp/smoke-results; \
    fi

LABEL dash.adapter.contract="0-draft" \
      dash.repo.name="MultiRATVANET" \
      dash.repo.commit="${REPO_COMMIT}" \
      dash.repo.dirty="${REPO_DIRTY}" \
      dash.manifest="/opt/dash/manifest.yaml" \
      org.opencontainers.image.title="MultiRATVANET" \
      org.opencontainers.image.description="MultiRATVANET multi-RAT VANET framework on the pinned vsim-base toolchain" \
      org.opencontainers.image.version="${REPO_COMMIT}"
# Entrypoint (tini -> vsim-entrypoint -> launchd on :9999) and CMD are inherited from vsim-base.
