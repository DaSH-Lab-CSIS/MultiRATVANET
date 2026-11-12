import re, glob, os
from collections import defaultdict

archive_dir = "simulations/results/archive"
policies = sorted(os.listdir(archive_dir))

print(f"{'Policy':<18} {'Handovers':>10} {'PingPong':>10} {'DSRC%':>8} {'WIFI%':>8} {'LTE%':>8} {'NR%':>8} {'6G%':>6} {'Outage%':>9} {'Connect%':>10}")
print("-" * 110)

for policy in policies:
    sca_files = glob.glob(f"{archive_dir}/{policy}/*.sca")
    if not sca_files:
        continue
    stats = defaultdict(list)
    with open(sca_files[0]) as f:
        for line in f:
            m = re.match(r'scalar \S+\.(\w+)\s+([\w.]+)\s+([-\d.eE]+)$', line.strip())
            if not m:
                continue
            module, stat, val = m.groups()
            stats[stat].append(float(val))

    handovers = sum(stats.get("handoversTotal", [0]))
    pingpong = sum(stats.get("pingPongTotal", [0]))
    dsrc = stats.get("DSRC.selectionShare", [0])
    wifi = stats.get("WIFI.selectionShare", [0])
    lte  = stats.get("LTE.selectionShare", [0])
    nr   = stats.get("NR.selectionShare", [0])
    sixg = stats.get("6G.selectionShare", [0])
    outage = stats.get("outageRatio", [0])
    connect = stats.get("connectivityRatio", [0])

    def avg(lst): return sum(lst)/len(lst) if lst else 0

    print(f"{policy:<18} {handovers:>10.0f} {pingpong:>10.0f} "
          f"{avg(dsrc)*100:>7.1f}% {avg(wifi)*100:>7.1f}% {avg(lte)*100:>7.1f}% "
          f"{avg(nr)*100:>7.1f}% {avg(sixg)*100:>5.1f}% {avg(outage)*100:>8.1f}% {avg(connect)*100:>9.1f}%")
