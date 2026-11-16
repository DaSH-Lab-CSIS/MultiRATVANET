# shellcheck shell=bash
# Sourced by the entrypoint, by BASH_ENV (non-interactive bash) and by /etc/profile.d. Idempotent.
[ -n "${VSIM_ENV_LOADED:-}" ] && return 0 2>/dev/null
export VSIM_ENV_LOADED=1   # set first: setenv scripts may spawn bash, which would re-source this via BASH_ENV

export VSIM_ROOT=/opt/vsim
export OMNETPP_ROOT=$VSIM_ROOT/omnetpp
export INET_ROOT=$VSIM_ROOT/inet
export VEINS_ROOT=$VSIM_ROOT/veins
export VEINS_INET_ROOT=$VEINS_ROOT/subprojects/veins_inet
export SIMU5G_ROOT=$VSIM_ROOT/simu5g
export SUMO_HOME=${SUMO_HOME:-/usr/share/sumo}

_vsim_setenv() {  # source a project's own setenv from its directory, quietly
  local d=$1 cur=$PWD; shift
  [ -f "$d/setenv" ] || return 0
  cd "$d" || return 0
  # shellcheck disable=SC1091
  . ./setenv "$@" >/dev/null 2>&1 || true
  cd "$cur" 2>/dev/null || cd /   # cwd may be an unreadable bind mount; never print errors
}
_vsim_setenv "$OMNETPP_ROOT" -f
_vsim_setenv "$INET_ROOT" -f
_vsim_setenv "$VEINS_ROOT"
_vsim_setenv "$VEINS_INET_ROOT"
_vsim_setenv "$SIMU5G_ROOT" -f
unset -f _vsim_setenv

# project setenv scripts may re-point these; pin them back
export OMNETPP_ROOT INET_ROOT VEINS_ROOT VEINS_INET_ROOT SIMU5G_ROOT
export OMNETPP_IMAGE_PATH="${OMNETPP_IMAGE_PATH:+$OMNETPP_IMAGE_PATH:}$VEINS_ROOT/images:$INET_ROOT/images:$SIMU5G_ROOT/images"
