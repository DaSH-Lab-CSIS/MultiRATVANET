# syntax=docker/dockerfile:1.7
#
# vsim-base — pinned vehicular-network-simulation toolchain (DaSH lab)
#   OMNeT++ 6.3.0 · INET 4.6.0 · Veins 5.3.1 (+veins_inet) · Simu5G 1.7.0 · SUMO 1.22.0
# Mirrors the opp_env install proven on anjuna3 (Ubuntu 22.04.5), but without Nix.
# Contains NO research repo. Derive with `FROM vsim-base:<tag>` or bind-mount a repo at /workspace.
#
# Build:  docker build -t vsim-base:om6.3.0-inet4.6.0-veins5.3.1-s5g1.7.0-sumo1.22.0 .

ARG UBUNTU_VERSION=22.04
# base pinned by digest (multi-arch index) for reproducibility; override with --build-arg UBUNTU_DIGEST=...
ARG UBUNTU_DIGEST=sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b
FROM ubuntu:${UBUNTU_VERSION}@${UBUNTU_DIGEST}

ARG DEBIAN_FRONTEND=noninteractive
ARG OMNETPP_VERSION=6.3.0
ARG INET_VERSION=4.6.0
ARG VEINS_VERSION=5.3.1
ARG SIMU5G_VERSION=1.7.0
ARG SUMO_VERSION=1.22.0
ARG BUILD_MODE=release
# 0 = use all cores (INET needs ~1 GB RAM per job with clang; lower this on small Docker VMs)
ARG JOBS=0
# Extra INET features. VoipStream / Z3 need extra apt packages: set INET_EXTRA_APT accordingly.
ARG INET_FEATURES="TcpLwip"
ARG INET_EXTRA_APT=""
# Delete *.o after linking (saves ~GBs; shared libs are what dependents use)
ARG KEEP_OBJECTS=0
# Run the Veins / veins_inet / Simu5G smoke scenarios at build time (fails the build if SUMO<->Veins is broken)
ARG RUN_SMOKE=1
# Opt-in Veins patch for SUMO newer than Veins 5.3.1 supports (see Veins block). Default off.
ARG VEINS_TRACI_CLAMP=0
ARG VSIM_UID=1000

ARG UBUNTU_VERSION
ENV LANG=C.UTF-8 TZ=UTC

# ---------------------------------------------------------------- system packages
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    rm -f /etc/apt/apt.conf.d/docker-clean; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg software-properties-common tini \
        build-essential clang lld gdb bison flex perl pkg-config xdg-utils \
        python3 python3-dev python3-pip python3-setuptools \
        python3-numpy python3-scipy python3-pandas python3-matplotlib \
        libxml2-dev zlib1g-dev libdw-dev \
        ${INET_EXTRA_APT}

# ---------------------------------------------------------------- SUMO (same version on every arch)
# SUMO_INSTALL=source (default): build the tagged source -> identical SUMO on every arch. auto/ppa: see below.
# SUMO_INSTALL=auto  : PPA package if that exact version resolves for this arch (amd64 = what anjuna3 uses), else build the tagged source
#              ppa   : PPA only (fail if missing)      source: always build from the tag (identical bits on amd64 and arm64)
# Both paths install to /usr, so SUMO_HOME=/usr/share/sumo everywhere.
ARG SUMO_INSTALL=source
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    use_ppa=0; \
    if [ "${SUMO_INSTALL}" != source ]; then \
      add-apt-repository -y ppa:sumo/stable; apt-get update; \
      if apt-cache madison sumo | grep -q " ${SUMO_VERSION}"; then use_ppa=1; \
      elif [ "${SUMO_INSTALL}" = ppa ]; then echo "SUMO ${SUMO_VERSION} not in PPA for $(dpkg --print-architecture)" >&2; exit 1; fi; \
    fi; \
    if [ "$use_ppa" = 1 ]; then \
      apt-get install -y "sumo=${SUMO_VERSION}*" "sumo-tools=${SUMO_VERSION}*"; \
      apt-mark hold sumo sumo-tools; \
    else \
      apt-get install -y --no-install-recommends cmake ninja-build libxerces-c-dev libproj-dev libgdal-dev libeigen3-dev; \
      tag="v$(echo "${SUMO_VERSION}" | tr . _)"; \
      mkdir /tmp/sumo-src; \
      curl -fsSL "https://github.com/eclipse-sumo/sumo/archive/refs/tags/${tag}.tar.gz" | tar -xz --strip-components=1 -C /tmp/sumo-src; \
      cmake -S /tmp/sumo-src -B /tmp/sumo-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr; \
      cmake --build /tmp/sumo-build -j"$(JOBS=${JOBS} sh -c 'if [ "${JOBS:-0}" -gt 0 ]; then echo $JOBS; else nproc; fi')"; \
      cmake --install /tmp/sumo-build; \
      rm -rf /tmp/sumo-src /tmp/sumo-build; \
    fi; \
    sumo --version | head -n1 | grep -F "${SUMO_VERSION}"; \
    test -f /usr/share/sumo/tools/traci/__init__.py

# ---------------------------------------------------------------- unprivileged build/run user
RUN set -eux; \
    useradd -m -u "${VSIM_UID}" -s /bin/bash vsim; \
    install -d -o vsim -g vsim /opt/vsim /opt/vsim/bin; \
    install -d -m 1777 /workspace /results

# Static env so derived-image RUN lines work without the entrypoint. env.sh adds the rest (OMNeT++/INET/Veins/Simu5G setenv).
ENV SUMO_HOME=/usr/share/sumo \
    VSIM_ROOT=/opt/vsim \
    OMNETPP_ROOT=/opt/vsim/omnetpp \
    INET_ROOT=/opt/vsim/inet \
    VEINS_ROOT=/opt/vsim/veins \
    VEINS_INET_ROOT=/opt/vsim/veins/subprojects/veins_inet \
    SIMU5G_ROOT=/opt/vsim/simu5g \
    BUILD_MODE=${BUILD_MODE} \
    PATH=/opt/vsim/bin:/opt/vsim/omnetpp/bin:/opt/vsim/veins/bin:${PATH} \
    LD_LIBRARY_PATH=/opt/vsim/omnetpp/lib \
    BASH_ENV=/opt/vsim/env.sh

USER vsim
WORKDIR /opt/vsim
# OMNeT++/INET/Veins setenv scripts are bash-only
SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# helper: resolve JOBS=0 -> nproc
COPY --chown=vsim:vsim --chmod=0755 scripts/jobs.sh /opt/vsim/bin/vsim-jobs
COPY --chown=vsim:vsim --chmod=0755 scripts/fetch.sh /opt/vsim/bin/vsim-fetch
COPY --chown=vsim:vsim --chmod=0644 scripts/checksums.txt /opt/vsim/checksums.txt
# optional pre-downloaded tarballs: dl/ is bind-mounted only during the fetch RUNs (never stored in a layer)

# ---------------------------------------------------------------- OMNeT++ (Cmdenv only; no IDE, no Qtenv, no OSG)
RUN --mount=type=bind,source=dl,target=/opt/vsim/dl set -ex; \
    case "$(dpkg --print-architecture)" in amd64) a=x86_64;; arm64) a=aarch64;; *) echo "unsupported arch" >&2; exit 1;; esac; \
    vsim-fetch "https://github.com/omnetpp/omnetpp/releases/download/omnetpp-${OMNETPP_VERSION}/omnetpp-${OMNETPP_VERSION}-linux-${a}.tgz" omnetpp; \
    cd omnetpp; \
    rm -rf ide tools/macos* tools/win*; \
    [ -f configure.user ] || cp configure.user.dist configure.user; \
    sed -i \
      -e 's|^WITH_QTENV=yes|WITH_QTENV=no|' \
      -e 's|^WITH_OSG=yes|WITH_OSG=no|' \
      -e 's|^WITH_OSGEARTH=yes|WITH_OSGEARTH=no|' \
      -e 's|^WITH_PARSIM=no|WITH_PARSIM=yes|' \
      configure.user; \
    grep -E '^(WITH_QTENV|WITH_OSG|WITH_OSGEARTH|WITH_PARSIM)=' configure.user; \
    set +e; . ./setenv -f; set -e; \
    ./configure; \
    make -j"$(vsim-jobs)" MODE="${BUILD_MODE}"; \
    if [ "${KEEP_OBJECTS}" = 0 ]; then find out -name '*.o' -delete; fi; \
    chmod -R a+rwX /opt/vsim/omnetpp

# ---------------------------------------------------------------- INET
RUN --mount=type=bind,source=dl,target=/opt/vsim/dl set -ex; \
    vsim-fetch "https://github.com/inet-framework/inet/releases/download/v${INET_VERSION}/inet-${INET_VERSION}-src.tgz" inet; \
    cd inet; \
    set +e; . /opt/vsim/omnetpp/setenv -f; set -e; \
    for f in ${INET_FEATURES}; do opp_featuretool -v enable "$f"; done; \
    rm -rf examples/voipstream/osudp; \
    (grep -Rls 'defined(linux)' . || true) | xargs -r sed -i 's|defined(linux)|defined(__linux__)|g'; \
    make makefiles; \
    make -j"$(vsim-jobs)" MODE="${BUILD_MODE}"; \
    if [ "${KEEP_OBJECTS}" = 0 ]; then find out -name '*.o' -delete; fi; \
    chmod -R a+rwX /opt/vsim/inet

# ---------------------------------------------------------------- Veins + veins_inet  (patches = opp_env's veins recipe, for INET 4.6.0)
RUN --mount=type=bind,source=dl,target=/opt/vsim/dl set -ex; \
    vsim-fetch "https://github.com/sommer/veins/archive/refs/tags/veins-${VEINS_VERSION}.tar.gz" veins; \
    cd veins; \
    sed -i "s|'--no-deep-includes', ||" configure subprojects/veins_inet/configure; \
    sed -i 's|inet/transportlayer/contract/udp/UdpControlInfo_m.h|inet/transportlayer/udp/Udp.h|g' \
        subprojects/veins_inet/src/veins_inet/VeinsInetApplicationBase.cc \
        subprojects/veins_inet/src/veins_inet/VeinsInetSampleApplication.cc; \
    sed -i 's|@labels(UdpControlInfo/|@labels(UdpCommand/|g' subprojects/veins_inet/src/veins_inet/VeinsInetApplicationBase.ned; \
    sed -i 's/(INET_VERSION == 0x405)/(INET_VERSION == 0x405) || (INET_VERSION == 0x406)/g' subprojects/veins_inet/src/veins_inet/veins_inet.h; \
    sed -i 's|\.radio\.typename = "Ieee80211DimensionalRadio"|.radio.typename = "Ieee80211DimensionalRadio"\n*.node[*].wlan[0].radio.signalAnalogRepresentation = "dimensional"|g' \
        subprojects/veins_inet/examples/veins_inet/omnetpp.ini; \
    # Veins 5.3.1 only knows TraCI API <=21. SUMO 1.22.0 (the version proven with it on anjuna3 via opp_env) is fine unpatched.
    # Only if you build with a newer SUMO: --build-arg VEINS_TRACI_CLAMP=1 mirrors v21 for higher API versions (unverified assumption).
    if [ "${VEINS_TRACI_CLAMP}" = 1 ]; then \
      sed -i 's|versionConfig = versionConfigs.at(apiVersion);|versionConfig = versionConfigs.at(apiVersion > 21 ? 21 : apiVersion);|' \
        src/veins/modules/mobility/traci/TraCICommandInterface.cc; \
      grep -q 'apiVersion > 21 ? 21' src/veins/modules/mobility/traci/TraCICommandInterface.cc; \
    fi; \
    set +e; . /opt/vsim/omnetpp/setenv -f; set -e; \
    export INET_ROOT=/opt/vsim/inet VEINS_ROOT=/opt/vsim/veins; \
    ./configure; \
    make -j"$(vsim-jobs)" MODE="${BUILD_MODE}"; \
    (cd subprojects/veins_inet && ./configure --with-inet="$INET_ROOT" --with-veins="$VEINS_ROOT" \
       && make -j"$(vsim-jobs)" MODE="${BUILD_MODE}"); \
    if [ "${KEEP_OBJECTS}" = 0 ]; then find . -path '*/out/*' -name '*.o' -delete; fi; \
    chmod -R a+rwX /opt/vsim/veins

# ---------------------------------------------------------------- Simu5G
RUN --mount=type=bind,source=dl,target=/opt/vsim/dl set -ex; \
    vsim-fetch "https://github.com/Unipisa/Simu5G/releases/download/v${SIMU5G_VERSION}/simu5g-${SIMU5G_VERSION}-src.tgz" simu5g \
      "https://github.com/Unipisa/Simu5G/archive/refs/tags/v${SIMU5G_VERSION}.tar.gz"; \
    cd simu5g; \
    sed -i -E 's|-KINET_PROJ=[^ ]+|-KINET_PROJ=$(INET_ROOT)|' Makefile; \
    find . -name omnetpp.ini | xargs -r sed -i -E 's|^image-path|#image-path|'; \
    set +e; . /opt/vsim/omnetpp/setenv -f; set -e; \
    export INET_ROOT=/opt/vsim/inet; \
    set +e; . ./setenv -f; set -e; \
    make makefiles; \
    make -j"$(vsim-jobs)" MODE="${BUILD_MODE}"; \
    if [ "${KEEP_OBJECTS}" = 0 ]; then find . -path '*/out/*' -name '*.o' -delete; fi; \
    chmod -R a+rwX /opt/vsim/simu5g

# ---------------------------------------------------------------- contract files
COPY --chown=vsim:vsim --chmod=0644 scripts/env.sh /opt/vsim/env.sh
COPY --chown=vsim:vsim --chmod=0755 scripts/entrypoint.sh /opt/vsim/bin/vsim-entrypoint
COPY --chown=vsim:vsim --chmod=0755 scripts/versions.sh   /opt/vsim/bin/vsim-versions
COPY --chown=vsim:vsim --chmod=0755 scripts/smoke.sh      /opt/vsim/bin/vsim-smoke

# Lock file other images / the dashboard adapter layer can read: /opt/vsim/toolchain.json
RUN set -ex; \
    printf '{\n  "omnetpp": "%s",\n  "inet": "%s",\n  "veins": "%s",\n  "simu5g": "%s",\n  "sumo": "%s",\n  "sumo_reported": "%s",\n  "ubuntu": "%s",\n  "arch": "%s",\n  "build_mode": "%s",\n  "inet_features_extra": "%s",\n  "traci_clamp": "%s",\n  "traci": {"launchd": "veins_launchd", "host": "127.0.0.1", "port": 9999}\n}\n' \
      "${OMNETPP_VERSION}" "${INET_VERSION}" "${VEINS_VERSION}" "${SIMU5G_VERSION}" "${SUMO_VERSION}" \
      "$(sumo --version | head -n1 | tr -d '\"')" "${UBUNTU_VERSION}" "$(dpkg --print-architecture)" "${BUILD_MODE}" "${INET_FEATURES}" "${VEINS_TRACI_CLAMP}" \
      > /opt/vsim/toolchain.json

# Smoke test twice: as an arbitrary uid with no passwd entry (what `docker run --user $(id -u)` does), then as vsim.
USER 54321:54321
RUN if [ "${RUN_SMOKE}" = 1 ]; then vsim-smoke; fi
USER vsim
RUN if [ "${RUN_SMOKE}" = 1 ]; then vsim-smoke; fi

LABEL org.opencontainers.image.title="vsim-base" \
      org.opencontainers.image.description="Pinned OMNeT++/INET/Veins/Simu5G/SUMO toolchain (no research repo)" \
      dash.vsim.omnetpp="${OMNETPP_VERSION}" dash.vsim.inet="${INET_VERSION}" \
      dash.vsim.veins="${VEINS_VERSION}" dash.vsim.simu5g="${SIMU5G_VERSION}" \
      dash.vsim.sumo="${SUMO_VERSION}" dash.vsim.contract="1"

WORKDIR /workspace
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/vsim/bin/vsim-entrypoint"]
CMD ["bash"]
