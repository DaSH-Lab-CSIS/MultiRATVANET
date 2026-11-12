import re, glob, os, csv
from collections import defaultdict

archive_dir = "simulations/results/archive"
out_csv = "all_metrics_summary.csv"

STATS_OF_INTEREST = [
    "handoversTotal", "pingPongTotal", "pingPongRatio",
    "DSRC.selectionShare", "WIFI.selectionShare", "LTE.selectionShare",
    "NR.selectionShare", "6G.selectionShare",
    "outageRatio", "connectivityRatio",
    "coverageCount:timeavg", "coverageCount:max",
    "dsrcInRange:timeavg", "wifiInRange:timeavg", "lteInRange:timeavg", "nrInRange:timeavg",
]

def avg(lst):
    return sum(lst) / len(lst) if lst else None

rows_out = []
for run_dir in sorted(glob.glob(f"{archive_dir}/*")):
    run_name = os.path.basename(run_dir)
    sca_files = glob.glob(f"{run_dir}/*.sca")
    if not sca_files:
        continue
    stats = defaultdict(list)
    with open(sca_files[0]) as f:
        for line in f:
            m = re.match(r'scalar (\S+)\.(\S+)\s+([\w.:]+)\s+([-\d.eE]+)$', line.strip())
            if not m:
                continue
            _, _, stat, val = m.groups()
            stats[stat].append(float(val))

    row = {"run": run_name}
    for stat in STATS_OF_INTEREST:
        vals = stats.get(stat, [])
        row[f"{stat}_sum"] = sum(vals) if vals else ""
        row[f"{stat}_avg"] = avg(vals) if vals else ""
        row[f"{stat}_n"] = len(vals)
    rows_out.append(row)

if rows_out:
    fieldnames = ["run"] + [k for k in rows_out[0].keys() if k != "run"]
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"Wrote {len(rows_out)} rows to {out_csv}")
else:
    print("No archived .sca files found")
