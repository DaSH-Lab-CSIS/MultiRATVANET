#!/usr/bin/env bash
# Run one MultiRATVANET experiment in Docker, with every tunable as a flag, then rebuild the
# HTML report (results/report.html) covering this run and all earlier ones.
#
#   dash/run-experiment.sh --scenario highway --policy ensemble --time 120s --ensemble-weight-sinr 2
#   dash/run-experiment.sh --scenario urbangrid --policy ml --decision-interval 0.2s --name tuned
#   dash/run-experiment.sh --config DsrcLteHandover --set '*.car[*].multiRatAppManager.lteHandoverDelay=60ms'
#
# Experiment
#   --scenario S            highway (default) | highway_dsrc_lte | highway_v2v | highway_cv2x | urbangrid | electroniccity
#   --policy P              coverage_priority (default) | sinr | latency_qos | load | ml | ensemble
#   --config NAME           use this omnetpp.ini config directly (overrides --scenario/--policy mapping)
#   --time T                simulated time, e.g. 120s (default: the scenario's default)
#   --seed N                OMNeT++ seed set (default 0)
#   --name LABEL            label added to the run folder name
# Scenario parameters (sent only when given; otherwise omnetpp.ini applies)
#   --decision-interval T   RAT re-evaluation interval, e.g. 0.5s
#   --dsrc-range D  --wifi-range D  --nr-range D  --lte-range D      coverage radius, e.g. 300m
#   --lte-interface NAME  --nr-interface NAME                         IP interface names (default "cellular")
#   --dsrc-handover-delay T  --lte-handover-delay T                   (highway_dsrc_lte)
# Ensemble policy parameters
#   --ensemble-weight-coverage W  --ensemble-weight-sinr W  --ensemble-weight-latency W
#   --ensemble-weight-load W      --ensemble-stickiness S
# Anything else
#   --set KEY=VALUE         raw ini override, repeatable (string values need their own quotes: KEY='"x"')
# Runner
#   --results DIR           results folder (default ./results)      --image IMG   (default multiratvanet:latest)
#   --no-report             skip the HTML report                     --dry-run     print the docker command only
# Environment: DOCKER (default "docker"; e.g. DOCKER="sudo docker").
set -euo pipefail

DOCKER=${DOCKER:-docker}
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
IMAGE=multiratvanet:latest
RESULTS=$PWD/results
SCENARIO=highway POLICY=coverage_priority CONFIG="" SIM_TIME="" SEED="" NAME=""
REPORT=1 DRY=0
PARAMS=()     # "label=value" for the run record
OVERRIDES=()  # --<ini-key>=<value> passed to the simulation

usage() { sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
die() { echo "error: $*" >&2; exit 2; }

# param FLAG-LABEL INI-KEY TYPE VALUE
param() {
    local v=$4
    [ "$3" = string ] && v="\"$4\""
    PARAMS+=("$1=$4")
    OVERRIDES+=("--$2=$v")
}

M='*.car[*].multiRatAppManager'
C='*.car[*].ratCoverageMonitor'
while [ $# -gt 0 ]; do
    flag=$1
    if [[ $flag == --*=* ]]; then val=${flag#*=}; flag=${flag%%=*}; shift
    elif [[ $flag == --* && $flag != --no-report && $flag != --dry-run && $flag != --help ]]; then
        [ $# -ge 2 ] || die "$flag needs a value"; val=$2; shift 2
    else val=""; shift; fi
    case $flag in
        --scenario) SCENARIO=$val ;;
        --policy)   POLICY=$val ;;
        --config)   CONFIG=$val ;;
        --time)     SIM_TIME=$val ;;
        --seed)     SEED=$val ;;
        --name)     NAME=$val ;;
        --results)  RESULTS=$val ;;
        --image)    IMAGE=$val ;;
        --no-report) REPORT=0 ;;
        --dry-run)  DRY=1 ;;
        -h|--help)  usage ;;
        --decision-interval)        param decision_interval        "$M.decisionInterval"        duration "$val" ;;
        --dsrc-range)               param dsrc_range               "$C.dsrcRange"               distance "$val" ;;
        --wifi-range)               param wifi_range               "$C.wifiRange"               distance "$val" ;;
        --nr-range)                 param nr_range                 "$C.nrRange"                 distance "$val" ;;
        --lte-range)                param lte_range                "$C.lteRange"                distance "$val" ;;
        --lte-interface)            param lte_interface            "$M.lteInterface"            string   "$val" ;;
        --nr-interface)             param nr_interface             "$M.nrInterface"             string   "$val" ;;
        --dsrc-handover-delay)      param dsrc_handover_delay      "$M.dsrcHandoverDelay"       duration "$val" ;;
        --lte-handover-delay)       param lte_handover_delay       "$M.lteHandoverDelay"        duration "$val" ;;
        --ensemble-weight-coverage) param ensemble_weight_coverage "$M.ensembleWeightCoverage"  double   "$val" ;;
        --ensemble-weight-sinr)     param ensemble_weight_sinr     "$M.ensembleWeightSinr"      double   "$val" ;;
        --ensemble-weight-latency)  param ensemble_weight_latency  "$M.ensembleWeightLatency"   double   "$val" ;;
        --ensemble-weight-load)     param ensemble_weight_load     "$M.ensembleWeightLoad"      double   "$val" ;;
        --ensemble-stickiness)      param ensemble_stickiness      "$M.ensembleStickiness"      double   "$val" ;;
        --set) [[ $val == *=* ]] || die "--set wants KEY=VALUE"; PARAMS+=("$val"); OVERRIDES+=("--$val") ;;
        *) die "unknown option $flag (see --help)" ;;
    esac
done

# scenario -> base config, default sim time (from dash/manifest.yaml)
case $SCENARIO in
    highway)          base=MultiRatHighway_Base; deftime=300s ;;
    highway_dsrc_lte) base=DsrcLteHandover;      deftime=300s ;;
    highway_v2v)      base=V2V;                  deftime=300s ;;
    highway_cv2x)     base=CV2X;                 deftime=300s ;;
    urbangrid)        base=UrbanGrid_Base;       deftime=120s ;;
    electroniccity)   base=ElectronicCity_Base;  deftime=1000s ;;
    *) die "unknown scenario $SCENARIO" ;;
esac
case $POLICY in
    coverage_priority) pol=CoveragePriority ;; sinr) pol=Sinr ;; latency_qos) pol=LatencyQos ;;
    load) pol=Load ;; ml) pol=Ml ;; ensemble) pol=Ensemble ;;
    *) die "unknown policy $POLICY" ;;
esac

# (scenario, policy) presets carry per-scenario tuning from omnetpp.ini; other pairs are composed
# from the scenario's base config plus a policy override
if [ -z "$CONFIG" ]; then
    case "$SCENARIO/$POLICY" in
        highway/*)                       CONFIG=$pol ;;
        highway_dsrc_lte/coverage_priority) CONFIG=DsrcLteHandover ;;
        urbangrid/coverage_priority)     CONFIG=UrbanGrid_CoveragePriority ;;
        urbangrid/ensemble)              CONFIG=UrbanGrid_Ensemble ;;
        urbangrid/ml)                    CONFIG=UrbanGrid_ML ;;
        electroniccity/coverage_priority) CONFIG=ElectronicCity_CoveragePriority ;;
        electroniccity/ensemble)         CONFIG=ElectronicCity_Ensemble ;;
        electroniccity/ml)               CONFIG=ElectronicCity_ML ;;
        *) CONFIG=$base; OVERRIDES=("--$M.policy=\"$pol\"" "${OVERRIDES[@]}") ;;
    esac
fi
SIM_TIME=${SIM_TIME:-$deftime}
[ -n "$SEED" ] && OVERRIDES+=("--seed-set=$SEED")

RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)-$SCENARIO-$POLICY${NAME:+-$NAME}
RUN_DIR=$RESULTS/$RUN_ID

cmd=($DOCKER run --rm --name "mrv-$RUN_ID" --user "$(id -u):$(id -g)"
     -v "$RESULTS":/results -e RESULTS_ROOT="/results/$RUN_ID"
     "$IMAGE" ./tools/run.sh "$CONFIG" --sim-time-limit="$SIM_TIME" "${OVERRIDES[@]}")

if [ "$DRY" = 1 ]; then printf '%q ' "${cmd[@]}"; echo; exit 0; fi

json() { local s=${1//\\/\\\\}; s=${s//\"/\\\"}; printf '"%s"' "$s"; }
jlist() { local first=1; printf '['; for x in "$@"; do [ $first = 1 ] || printf ', '; first=0; json "$x"; done; printf ']'; }

mkdir -p "$RUN_DIR"
image_id=$($DOCKER image inspect --format '{{.Id}}' "$IMAGE")
repo_commit=$($DOCKER image inspect --format '{{index .Config.Labels "dash.repo.commit"}}' "$IMAGE")
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "== $RUN_ID: config $CONFIG, $SIM_TIME, ${#OVERRIDES[@]} override(s) -> $RUN_DIR"

set +e
"${cmd[@]}" 2>&1 | tee "$RUN_DIR/console.log"
rc=${PIPESTATUS[0]}
set -e

{
    printf '{\n  "run_id": %s,\n  "scenario": %s,\n  "policy": %s,\n  "config": %s,\n' \
        "$(json "$RUN_ID")" "$(json "$SCENARIO")" "$(json "$POLICY")" "$(json "$CONFIG")"
    printf '  "sim_time": %s,\n  "seed": %s,\n  "name": %s,\n  "params": %s,\n  "overrides": %s,\n' \
        "$(json "$SIM_TIME")" "$(json "${SEED:-0}")" "$(json "$NAME")" "$(jlist "${PARAMS[@]}")" "$(jlist "${OVERRIDES[@]}")"
    printf '  "image": %s,\n  "image_id": %s,\n  "repo_commit": %s,\n' "$(json "$IMAGE")" "$(json "$image_id")" "$(json "$repo_commit")"
    printf '  "who": %s,\n  "host": %s,\n  "started": %s,\n  "finished": %s,\n  "exit_code": %d\n}\n' \
        "$(json "$(id -un)")" "$(json "$(hostname)")" "$(json "$started")" "$(json "$(date -u +%Y-%m-%dT%H:%M:%SZ)")" "$rc"
} > "$RUN_DIR/run.json"

if [ "$REPORT" = 1 ]; then
    $DOCKER run --rm --user "$(id -u):$(id -g)" -e VSIM_LAUNCHD=0 \
        -v "$RESULTS":/results -v "$REPO/dash/report.py":/opt/dash-report.py:ro \
        "$IMAGE" python3 /opt/dash-report.py /results \
        && echo "== report: $RESULTS/report.html"
fi
[ "$rc" = 0 ] || echo "== simulation FAILED (exit $rc); see $RUN_DIR/console.log" >&2
exit "$rc"
