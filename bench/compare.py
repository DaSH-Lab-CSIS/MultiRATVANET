#!/usr/bin/env python3
"""Summarise a test-bench run: one row per policy, averaged over the seeds, and (optionally) the
change against an earlier bench run.

    python3 bench/compare.py BENCH_DIR [--against OTHER_BENCH_DIR_OR_SUMMARY_JSON]

BENCH_DIR is a folder written by bench/run.sh: one run folder per (scenario, policy, seed).
Writes BENCH_DIR/summary.json and BENCH_DIR/summary.md and prints the tables.
Standard library only.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dash"))
import report  # noqa: E402  (dash/report.py reads the .sca files)

# rows in this order; the baselines last
POLICIES = ["coverage_priority", "sinr", "latency_qos", "load", "ensemble"]
BASELINES = ["only_dsrc", "only_wifi", "only_nr"]
LABELS = {"coverage_priority": "CoveragePriority", "sinr": "Sinr", "latency_qos": "LatencyQos",
          "load": "Load", "ensemble": "Ensemble", "ml": "Ml", "example_split": "ExampleSplit",
          "only_dsrc": "only DSRC", "only_wifi": "only WiFi", "only_nr": "only 5G"}

# (key, column title, kind, higher is better)
METRICS = [
    ("safety_delivered",  "Safety delivered",       "pct", True),
    ("safety_on_time",    "Safety on time",         "pct", True),
    ("safety_delay_ms",   "Safety delay ms",        "ms",  False),
    ("info_delivered",    "Infot. delivered",       "pct", True),
    ("info_on_time",      "Infot. on time",         "pct", True),
    ("info_delay_ms",     "Infot. delay ms",        "ms",  False),
    ("handovers_per_car", "Handovers / car",        "num", False),
    ("ping_pong",         "Ping-pongs (all cars)",  "cnt", False),
    ("interruption_ms",   "Switch gap ms",          "ms",  False),
    ("share_dsrc",        "On DSRC",                "pct", None),
    ("share_wifi",        "On WiFi",                "pct", None),
    ("share_nr",          "On 5G",                  "pct", None),
]


def run_metrics(run):
    s = run["summary"]
    out = {}
    for c in s["classes"]:
        prefix = {"safety": "safety", "infotainment": "info"}.get(c["name"])
        if prefix:
            out[prefix + "_delivered"] = c["pdr"]
            out[prefix + "_on_time"] = c["within_deadline"]
            out[prefix + "_delay_ms"] = c["delay_mean_ms"]
    out["handovers_per_car"] = s["handovers_per_vehicle"]
    out["ping_pong"] = s["ping_pong"]
    out["interruption_ms"] = s["interruption_mean_ms"]
    shares = s.get("shares") or {}
    out["share_dsrc"] = shares.get("DSRC")
    out["share_wifi"] = shares.get("WiFi")
    out["share_nr"] = shares.get("NR", shares.get("Cellular"))
    return out


def mean_std(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None
    m = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) if len(vals) > 1 else 0.0
    return m, sd


def collect(bench_dir):
    groups, failed, commits = {}, [], set()
    for d in sorted(os.listdir(bench_dir)):
        p = os.path.join(bench_dir, d)
        if not os.path.isdir(p) or d.startswith("."):
            continue
        run = report.load_run(p)
        meta = run.get("meta") or {}
        key = (meta.get("scenario", "?"), meta.get("policy", "?"))
        if meta.get("repo_commit"):
            commits.add(meta["repo_commit"][:10])
        if run["status"] != "ok":
            failed.append(d)
            continue
        groups.setdefault(key, []).append((meta.get("seed"), run_metrics(run)))
    summary = {"bench": os.path.basename(os.path.abspath(bench_dir)), "commits": sorted(commits),
               "failed": failed, "scenarios": {}}
    for (scenario, policy), runs in sorted(groups.items()):
        row = {"seeds": sorted(str(s) for s, _ in runs)}
        for key, *_ in METRICS:
            m, sd = mean_std([r[key] for _, r in runs])
            row[key] = {"mean": m, "std": sd}
        summary["scenarios"].setdefault(scenario, {})[policy] = row
    try:
        with open(os.path.join(bench_dir, "bench.json")) as f:
            summary["settings"] = json.load(f)
    except (OSError, ValueError):
        pass
    return summary


def load_summary(path):
    if os.path.isdir(path):
        sp = os.path.join(path, "summary.json")
        if os.path.exists(sp):
            with open(sp) as f:
                return json.load(f)
        return collect(path)
    with open(path) as f:
        return json.load(f)


def fmt(v, kind, sign=False):
    if v is None:
        return "–"
    if kind == "pct":
        return f"{v * 100:+.1f}" if sign else f"{v * 100:.1f} %"
    if kind in ("ms", "cnt"):
        return f"{v:+.1f}" if sign else f"{v:.1f}"
    return f"{v:+.2f}" if sign else f"{v:.2f}"


def order(policies):
    known = [p for p in POLICIES + BASELINES if p in policies]
    return known + sorted(p for p in policies if p not in known)


def table(rows, cols, against=None):
    head = "| Policy | " + " | ".join(c[1] for c in cols) + " |"
    lines = [head, "|---|" + "---|" * len(cols)]
    for policy in order(rows):
        r = rows[policy]
        if policy == BASELINES[0] and lines[-1] and any(p in rows for p in POLICIES):
            lines.append("| *baselines* |" + " |" * len(cols))
        cells = []
        for key, _, kind, _better in cols:
            m = r[key]["mean"]
            sd = r[key]["std"]
            cell = fmt(m, kind)
            if sd and len(r["seeds"]) > 1:
                cell += " ±" + (f"{sd * 100:.1f}" if kind == "pct" else f"{sd:.1f}" if kind in ("ms", "cnt") else f"{sd:.2f}")
            if against and policy in against and against[policy][key]["mean"] is not None and m is not None:
                cell += f" ({fmt(m - against[policy][key]['mean'], kind, sign=True)})"
            cells.append(cell)
        lines.append(f"| {LABELS.get(policy, policy)} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render(summary, against=None):
    out = [f"# Test bench: {summary['bench']}", ""]
    st = summary.get("settings") or {}
    if st:
        out.append(f"Sim time {st.get('time')}, seeds {st.get('seeds')}, image {st.get('image')}"
                   f" (commit {', '.join(summary['commits']) or '?'})."
                   + ("" if st.get("standard", True) else " **Not the standard bench settings:** "
                      + ", ".join(st.get("extra", []))))
        out.append("")
    if against:
        out.append(f"Numbers in brackets: change against bench `{against['bench']}`"
                   f" (commit {', '.join(against.get('commits', [])) or '?'}); percentages in points.")
        out.append("")
    out.append("Values are the mean over the seeds, ± the standard deviation across seeds. Safety is judged at"
               " the server (100 ms deadline), infotainment at the car (1 s from the request). Switch gap: first"
               " request sent on the new RAT until the first one that arrives. On DSRC/WiFi/5G: share of the time"
               " a car was attached to a RAT, averaged over the cars (a car that never attached counts 0).")
    for scenario, rows in summary["scenarios"].items():
        prev = (against or {}).get("scenarios", {}).get(scenario)
        out += ["", f"## {scenario}", "", "### Traffic", "", table(rows, METRICS[:6], prev),
                "", "### Switching and where the cars were", "", table(rows, METRICS[6:], prev)]
    if summary["failed"]:
        out += ["", "**Failed runs:** " + ", ".join(summary["failed"])]
    return "\n".join(out) + "\n"


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    bench_dir = argv[0]
    against = load_summary(argv[argv.index("--against") + 1]) if "--against" in argv else None
    summary = collect(bench_dir)
    with open(os.path.join(bench_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    text = render(summary, against)
    with open(os.path.join(bench_dir, "summary.md"), "w") as f:
        f.write(text)
    print(text)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
