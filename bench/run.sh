#!/usr/bin/env bash
# The test bench: run the five policies and the three one-RAT baselines on the same scenario with
# the same seeds, then put them side by side (bench/compare.py). Run it before and after any change
# to the harness and compare the two.
#
#   bench/run.sh                                  # the standard bench: highway, 120 s, seeds 0 1 2
#   bench/run.sh --against bench/reference        # ... and show the change against the committed reference
#   bench/run.sh --against bench-results/<earlier bench>
#   bench/run.sh --quick                          # 60 s, seed 0 only: a fast sanity check
#   bench/run.sh --save-reference                 # standard bench, then make it the committed reference
#   bench/run.sh --scenarios "highway urbangrid" --seeds "0 1 2 3 4"
#   bench/run.sh --only "sinr only_nr" --set '*.car[*].app[2].probeInterval=200ms'
#
# Options
#   --scenarios "S ..."   scenarios (default "highway"); see dash/run-experiment.sh --help
#   --seeds "N ..."       seed sets (default "0 1 2")
#   --time T              simulated time per run (default 120s)
#   --only "P ..."        run only these policies (default: all eight)
#   --set KEY=VALUE       ini override applied to every run, repeatable (marks the bench non-standard)
#   --jobs N              runs at the same time (default 8)
#   --label NAME          added to the bench folder name
#   --out DIR             where bench folders go (default ./bench-results)
#   --against PATH        compare with an earlier bench folder or a summary.json
#   --image IMG           (default multiratvanet:latest; build it with dash/build-image.sh)
#   --vectors             also record OMNeT++ vectors (time series in report.html; ~300 MB per 120 s
#                         run, so ~7 GB for the standard bench). Off by default: the tables need scalars only.
#   --save-reference      copy summary.md, summary.json and report.html into bench/reference/ (only for
#                         a standard bench that completed every run); commit them with the change
# Writes <out>/<UTC time>[-label]/: one run folder per (scenario, policy, seed), bench.json (the
# settings), summary.md and summary.json (the tables), report.html (the dashboard: the policies
# compared, then every run with its map, decisions and results). Open report.html first.
# Environment: DOCKER (default "docker").
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
POLICIES="coverage_priority sinr latency_qos load ensemble only_dsrc only_wifi only_nr"
STD_SCENARIOS=highway STD_SEEDS="0 1 2" STD_TIME=120s
SCENARIOS=$STD_SCENARIOS SEEDS=$STD_SEEDS SIM_TIME=$STD_TIME ONLY=$POLICIES
VECTORS=0 SAVE_REF=0 JOBS=8 LABEL="" OUT=$PWD/bench-results AGAINST="" IMAGE=multiratvanet:latest
SETS=()

usage() { sed -n '2,31p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
die() { echo "error: $*" >&2; exit 2; }

while [ $# -gt 0 ]; do
    case $1 in
        --quick)     SIM_TIME=60s SEEDS=0; shift; continue ;;
        --vectors)   VECTORS=1; shift; continue ;;
        --save-reference) SAVE_REF=1; shift; continue ;;
        -h|--help)   usage ;;
    esac
    [ $# -ge 2 ] || die "$1 needs a value"
    case $1 in
        --scenarios) SCENARIOS=$2 ;;
        --seeds)     SEEDS=$2 ;;
        --time)      SIM_TIME=$2 ;;
        --only)      ONLY=$2 ;;
        --set)       SETS+=("$2") ;;
        --jobs)      JOBS=$2 ;;
        --label)     LABEL=$2 ;;
        --out)       OUT=$2 ;;
        --against)   AGAINST=$2 ;;
        --image)     IMAGE=$2 ;;
        *) die "unknown option $1 (see --help)" ;;
    esac
    shift 2
done
[ -z "$AGAINST" ] || [ -e "$AGAINST" ] || die "--against: $AGAINST does not exist"

# anything other than the standard settings is written down, so a comparison can say so
extra=()
[ "$SCENARIOS" = "$STD_SCENARIOS" ] || extra+=("scenarios $SCENARIOS")
[ "$SEEDS" = "$STD_SEEDS" ] || extra+=("seeds $SEEDS")
[ "$SIM_TIME" = "$STD_TIME" ] || extra+=("time $SIM_TIME")
[ "$ONLY" = "$POLICIES" ] || extra+=("only $ONLY")
for s in "${SETS[@]}"; do extra+=("set $s"); done

BENCH=$OUT/$(date -u +%Y%m%dT%H%M%SZ)${LABEL:+-$LABEL}
mkdir -p "$BENCH"
OUT_ABS=$(cd "$BENCH" && pwd)

json() { local s=${1//\\/\\\\}; s=${s//\"/\\\"}; printf '"%s"' "$s"; }
jlist() { local first=1; printf '['; for x in "$@"; do [ $first = 1 ] || printf ', '; first=0; json "$x"; done; printf ']'; }
{
    printf '{\n  "scenarios": %s,\n  "seeds": %s,\n  "time": %s,\n  "policies": %s,\n' \
        "$(jlist $SCENARIOS)" "$(jlist $SEEDS)" "$(json "$SIM_TIME")" "$(jlist $ONLY)"
    printf '  "sets": %s,\n  "standard": %s,\n  "extra": %s,\n' \
        "$(jlist "${SETS[@]}")" "$([ ${#extra[@]} = 0 ] && echo true || echo false)" "$(jlist "${extra[@]}")"
    printf '  "image": %s,\n  "repo_commit": %s,\n  "started": %s\n}\n' "$(json "$IMAGE")" \
        "$(json "$(${DOCKER:-docker} image inspect --format '{{index .Config.Labels "dash.repo.commit"}}' "$IMAGE")")" \
        "$(json "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"
} > "$BENCH/bench.json"

# one line per run: scenario policy seed
jobs_file=$BENCH/.jobs
: > "$jobs_file"
for sc in $SCENARIOS; do for p in $ONLY; do for s in $SEEDS; do
    echo "$sc $p $s" >> "$jobs_file"
done; done; done
n=$(wc -l < "$jobs_file")
echo "== bench $BENCH: $n runs, $JOBS at a time, $SIM_TIME each${extra[*]:+ (non-standard: ${extra[*]})}"

set_args=()
[ "$VECTORS" = 1 ] || set_args+=(--set '**.vector-recording=false')
for s in "${SETS[@]}"; do set_args+=(--set "$s"); done
export REPO OUT_ABS SIM_TIME IMAGE
export SET_ARGS="${set_args[*]@Q}"
# each run gets its own log; the console shows one line when it ends
xargs -P "$JOBS" -L 1 bash -c '
    sc=$0 p=$1 s=$2
    eval "extra=($SET_ARGS)"
    if "$REPO/dash/run-experiment.sh" --scenario "$sc" --policy "$p" --seed "$s" --time "$SIM_TIME" \
            --name "s$s" --results "$OUT_ABS" --image "$IMAGE" --no-report "${extra[@]}" \
            > "$OUT_ABS/.log-$sc-$p-s$s" 2>&1; then
        echo "   done   $sc $p seed $s"
    else
        echo "   FAILED $sc $p seed $s (see $OUT_ABS/.log-$sc-$p-s$s)"
    fi
' < "$jobs_file" || true

echo "== summary"
rc=0
python3 "$REPO/bench/compare.py" "$BENCH" ${AGAINST:+--against "$AGAINST"} || rc=$?
if python3 "$REPO/dash/report.py" "$BENCH" >/dev/null; then
    echo "== report: $BENCH/report.html"
else
    echo "!! report.html could not be built (see above)"; rc=1
fi
echo "== tables: $BENCH/summary.md"
if [ "$SAVE_REF" = 1 ]; then
    # only a standard bench in which every run completed becomes the reference
    if [ $rc = 0 ] && python3 - "$BENCH" <<'PY'
import json, sys
b, s = (json.load(open(f"{sys.argv[1]}/{f}")) for f in ("bench.json", "summary.json"))
sys.exit(0 if b.get("standard") and not s.get("failed") else 1)
PY
    then
        cp "$BENCH/summary.md" "$BENCH/summary.json" "$BENCH/report.html" "$REPO/bench/reference/"
        echo "== saved as bench/reference/ (summary.md, summary.json, report.html): commit them with the change"
    else
        echo "!! not saved as the reference: only a standard bench with every run completed is"; rc=1
    fi
fi
exit $rc
