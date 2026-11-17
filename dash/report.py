#!/usr/bin/env python3
"""Build results/report.html: every run in a results folder, its time series and final results.

    python3 dash/report.py RESULTS_DIR [--out FILE]

A run is a folder in RESULTS_DIR holding OMNeT++ output (.sca/.vec), either directly (tools/run.sh
without RESULTS_ROOT) or one level down (dash/run-experiment.sh, which also writes run.json and
console.log). Standard library only, so it runs inside the image. Per-run results are cached in
<run>/.report-cache.json and recomputed when the .sca/.vec change.
"""
import glob
import html
import json
import os
import re
import sys
from datetime import datetime, timezone

CACHE_VERSION = 9
LOG_TAIL = 200
BIN_STEPS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]
MAX_POINTS = 120

RAT_SERIES = [("DSRC", "vehiclesDsrc"), ("WiFi", "vehiclesWifi"), ("NR", "vehiclesNr"),
              ("LTE", "vehiclesLte"), ("Unconnected", "vehiclesUnconnected")]
RAT_SHARES = [("DSRC", "DSRC"), ("WiFi", "WIFI"), ("NR", "NR"), ("LTE", "LTE")]

RE_CAR_APP = re.compile(r"\.car\[\d+\]\.app\[(\d+)\]$")
CAR_REPLY_SCALARS = {"repliesExpected": "replies_expected", "repliesReceived": "replies_received",
                     "repliesWithinDeadline": "replies_within", "replyDeadline": "reply_deadline_s",
                     "replyReceived:sum(packetBytes)": "reply_bytes"}
RE_SERVER_APP = re.compile(r"\.server\.app\[(\d+)\]$")
RE_MANAGER = re.compile(r"\.car\[\d+\]\.multiRatAppManager$")
RE_COVERAGE = re.compile(r"\.car\[\d+\]\.ratCoverageMonitor$")
RE_STATS = re.compile(r"\.ratStatsCollector$")
RE_CAR_PART = re.compile(r"\.car\[(\d+)\]\.(multiRatAppManager|ratCoverageMonitor|app\[\d+\])$")
RE_INFRA_POS = re.compile(r"^\*+\.(\w+)\[(\d+|\*)\]\.mobility\.initial([XY])$")


def num(s):
    try:
        v = float(s)
    except ValueError:
        return None
    return None if v != v else v  # NaN -> None


def parse_time(s):
    """'120s', '500ms', '2min' -> seconds"""
    m = re.fullmatch(r"\s*([0-9.eE+-]+)\s*(s|ms|us|min|h)?\s*", s or "")
    if not m:
        return None
    return float(m.group(1)) * {"s": 1, None: 1, "ms": 1e-3, "us": 1e-6, "min": 60, "h": 3600}[m.group(2)]


def unquote(v):
    v = v.strip()
    while len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        v = v[1:-1].replace('\\"', '"')
    return v


def read_sca(path):
    """attrs, first-match config (OMNeT++ lists entries in lookup order), scalars, histogram fields"""
    attrs, config, scalars, stats, pars, descr = {}, {}, [], {}, {}, []
    cur = None
    with open(path, errors="replace") as f:
        for line in f:
            if line.startswith("scalar "):
                p = line.split(None, 3)
                if len(p) == 4:
                    scalars.append((p[1], unquote(p[2]), num(p[3])))
            elif line.startswith("statistic "):
                p = line.split(None, 2)
                cur = (p[1], unquote(p[2].strip())) if len(p) == 3 else None
                if cur:
                    stats[cur] = {}
            elif line.startswith("field ") and cur:
                p = line.split()
                if len(p) == 3:
                    stats[cur][p[1]] = num(p[2])
            elif line.startswith("attr "):
                p = line.split(None, 2)
                if len(p) == 3:
                    attrs[p[1]] = unquote(p[2])
            elif line.startswith("config "):
                p = line.split(None, 2)
                if len(p) == 3:
                    if p[1] == "description":
                        descr.append(unquote(p[2]))
                    config.setdefault(p[1], unquote(p[2]))
            elif line.startswith("par "):
                p = line.split(None, 3)
                if len(p) == 4:
                    m = RE_CAR_PART.search(p[1])
                    if m:
                        pars.setdefault(m.group(2), {}).setdefault(m.group(1), {})[p[2]] = unquote(p[3])
    return attrs, config, scalars, stats, pars, descr


def class_names(config):
    """server app index -> traffic class name (MultiRatSink), or "app[k]" for anything else"""
    names = {}
    for key, v in config.items():
        m = re.match(r"^\*+\.server\.app\[(\d+)\]\.trafficClass$", key)
        if m:
            names.setdefault(int(m.group(1)), v)
    return names


def summarize(config, scalars, stats, sim_time):
    names = class_names(config)
    cls = {}  # app index -> counters
    per_car = {}
    for mod, name, v in scalars:
        if v is None:
            continue
        m = RE_CAR_APP.search(mod)
        if m and name == "packetSent:count":
            cls.setdefault(int(m.group(1)), {}).setdefault("sent", 0)
            cls[int(m.group(1))]["sent"] += v
            continue
        if m and name in CAR_REPLY_SCALARS:
            # request-and-reply traffic: what came back to the cars (summed over cars)
            c = cls.setdefault(int(m.group(1)), {})
            key = CAR_REPLY_SCALARS[name]
            c[key] = v if key == "reply_deadline_s" else c.get(key, 0) + v
            continue
        m = RE_SERVER_APP.search(mod)
        if m:
            c = cls.setdefault(int(m.group(1)), {})
            if name == "packetReceived:count":
                c["received"] = c.get("received", 0) + v
            elif name == "packetReceived:sum(packetBytes)":
                c["bytes"] = c.get("bytes", 0) + v
            elif name == "packetsWithinDeadline":
                c["within"] = v
            elif name == "deadline":
                c["deadline_s"] = v
        elif RE_MANAGER.search(mod) or RE_COVERAGE.search(mod):
            car = mod.rsplit(".", 1)[0]
            per_car.setdefault(car, {})[name] = v
    managers = [c for c in per_car.values() if "handoversTotal" in c]
    n = len(managers)

    def total(key):
        return sum(c.get(key, 0) for c in per_car.values())

    def mean(key):
        vals = [c[key] for c in per_car.values() if key in c]
        return sum(vals) / len(vals) if vals else None

    interruption = {"count": 0, "sum": 0.0, "max": None, "lost": 0.0}
    for (mod, name), fields in stats.items():
        m = RE_CAR_APP.search(mod)
        if m and name == "replyDelay:histogram" and fields.get("count"):
            d = cls.setdefault(int(m.group(1)), {}).setdefault("reply_delay", {"count": 0, "sum": 0.0, "max": 0.0})
            d["count"] += fields["count"]
            d["sum"] += fields.get("sum") or 0
            d["max"] = max(d["max"], fields.get("max") or 0)
            continue
        m = RE_SERVER_APP.search(mod)
        if not m:
            continue
        c = cls.setdefault(int(m.group(1)), {})
        if name == "endToEndDelay:histogram":
            c["delay"] = fields
        elif name == "switchInterruption:histogram" and fields.get("count"):
            interruption["count"] += fields["count"]
            interruption["sum"] += fields.get("sum") or 0
            if fields.get("max") is not None:
                interruption["max"] = max(interruption["max"] or 0, fields["max"])
        elif name == "switchLoss:histogram" and fields.get("count"):
            interruption["lost"] += fields.get("sum") or 0

    classes = []
    for k in sorted(cls):
        c = cls[k]
        if not c.get("sent") or "received" not in c:
            continue  # e.g. V2V beacons: no server side
        if c.get("reply_deadline_s") and c.get("replies_expected"):
            # the heavy direction is server -> car (infotainment): judged at the car, on the
            # reply packets, each counted from the sending of its request
            d = c.get("reply_delay", {})
            dc, ds = d.get("count"), d.get("sum")
            classes.append({
                "name": names.get(k, f"app[{k}]"),
                "direction": "server to car",
                "sent": c["replies_expected"],
                "received": c.get("replies_received", 0),
                "pdr": c.get("replies_received", 0) / c["replies_expected"],
                "within_deadline": c.get("replies_within", 0) / c["replies_expected"],
                "deadline_ms": c["reply_deadline_s"] * 1e3,
                "throughput_mbps": c.get("reply_bytes", 0) * 8e-6 / sim_time if sim_time else None,
                "delay_mean_ms": ds / dc * 1e3 if dc else None,
                "delay_max_ms": d["max"] * 1e3 if dc else None,
            })
            continue
        d = c.get("delay", {})
        dc, ds = d.get("count"), d.get("sum")
        classes.append({
            "name": names.get(k, f"app[{k}]"),
            "direction": "car to server",
            "sent": c["sent"],
            "received": c["received"],
            "pdr": c["received"] / c["sent"],
            "within_deadline": c["within"] / c["sent"] if "within" in c and c.get("deadline_s") else None,
            "deadline_ms": c["deadline_s"] * 1e3 if c.get("deadline_s") else None,
            "throughput_mbps": c.get("bytes", 0) * 8e-6 / sim_time if sim_time else None,
            "delay_mean_ms": ds / dc * 1e3 if dc else None,
            "delay_max_ms": d["max"] * 1e3 if d.get("max") is not None and dc else None,
        })
    sent = sum(c["sent"] for c in classes)
    rcvd = sum(c["received"] for c in classes)
    dn = sum(c["received"] for c in classes if c["delay_mean_ms"] is not None)
    delay_mean = sum(c["delay_mean_ms"] * c["received"] for c in classes if c["delay_mean_ms"] is not None) / dn if dn else None
    delay_max = max((c["delay_max_ms"] for c in classes if c["delay_max_ms"] is not None), default=None)

    shares = {label: mean(f"{key}.selectionShare") for label, key in RAT_SHARES}
    if cellular_merged(config):
        shares = {"DSRC": shares["DSRC"], "WiFi": shares["WiFi"],
                  "Cellular": (shares["NR"] or 0) + (shares["LTE"] or 0)}
    elif not lte_equipped(config):
        shares.pop("LTE", None)
    inputs = {}
    for label, key in RAT_SHARES:
        vals = {f: mean(f"{key}.inRange{f}") for f in ("SinrMargin", "Load", "Capacity", "LinkRate", "Latency", "ProbeRtt")}
        if any(v is not None for v in vals.values()):
            inputs[label] = vals
    return {
        "vehicles": n,
        "classes": classes,
        "sent": sent,
        "received": rcvd,
        "pdr": rcvd / sent if sent else None,
        "throughput_mbps": sum(c["throughput_mbps"] or 0 for c in classes) if classes else None,
        "delay_mean_ms": delay_mean,
        "delay_max_ms": delay_max,
        "handovers": total("handoversTotal"),
        "handovers_per_vehicle": total("handoversTotal") / n if n else None,
        "handovers_failed": total("handoverFailed:count"),
        "ping_pong": total("pingPongTotal"),
        "connectivity": mean("connectivityRatio"),
        "outage_s": total("outageTimeTotal"),
        "interruption_count": interruption["count"],
        "interruption_mean_ms": interruption["sum"] / interruption["count"] * 1e3 if interruption["count"] else None,
        "interruption_max_ms": interruption["max"] * 1e3 if interruption["max"] is not None else None,
        "interruption_lost": interruption["lost"],
        "shares": shares,
        "inputs": inputs,
    }


def scenario_setup(config, pars, scalars, descr):
    """What the vehicles drove through and how they decided: effective values for the report"""
    one = lambda part: next(iter(pars.get(part, {}).values()), {})  # parameters of the first car seen
    mgr, mon = one("multiRatAppManager"), one("ratCoverageMonitor")
    apps = [one(k) for k in sorted((k for k in pars if k.startswith("app[")), key=lambda k: int(k[4:-1]))]
    infra_count = {}
    for mod, name, v in scalars:
        if RE_COVERAGE.search(mod) and name.endswith(".infraNodes") and v is not None:
            infra_count.setdefault(name.split(".")[0], v)
    pos = {}
    for key, v in config.items():
        m = RE_INFRA_POS.match(key)
        if m and m.group(2) != "*":
            pos.setdefault((m.group(1), int(m.group(2))), {})[m.group(3)] = v
    for mod, name, v in scalars:
        m = re.match(r"infra\.(\w+)(?:\[(\d+)\])?\.([xy])$", name)
        if m and RE_STATS.search(mod) and v is not None:
            kind = re.sub(r"\d+$", "", m.group(1)) if m.group(2) is None else m.group(1)
            idx = int(m.group(2)) if m.group(2) is not None else int(re.search(r"(\d*)$", m.group(1)).group(1) or 0)
            pos.setdefault((kind, idx), {})[m.group(3).upper()] = f"{v:g}m"
    positions = {}
    for (kind, i), xy in sorted(pos.items()):
        positions.setdefault(kind, []).append(f"({xy.get('X', '?')}, {xy.get('Y', '?')})")
    infra_kind = {"DSRC": "dsrcRsu", "WIFI": "wifiAp", "NR": "gNodeB", "LTE": "eNodeB"}
    rats = []
    for label, key, pre in (("DSRC", "DSRC", "dsrc"), ("WiFi", "WIFI", "wifi"), ("NR", "NR", "nr"), ("LTE", "LTE", "lte")):
        if mon.get("has" + pre.capitalize() if pre != "nr" else "hasNr") == "false":
            continue
        itype = mon.get(pre + "InfraType")
        rats.append({
            "rat": label,
            "towers": (None if itype == "" else infra_count.get(key)),
            "infra_type": itype,
            "positions": positions.get(infra_kind[key], []),
            "range": mon.get(pre + "Range"),
            "min_sinr": mon.get(pre + "MinSinr"),
            "rssi_threshold": mon.get(pre + "RssiThreshold"),
            "latency_ms": mon.get(pre + "LatencyMs"),
            "capacity_mbps": mon.get(pre + "CapacityMbps"),
            "interface": mgr.get(pre + "Interface"),
        })
    pick = lambda *keys: {k: config[k] for k in keys if k in config}
    deadlines = {}
    for key, v in config.items():
        m = re.match(r"^\*+\.server\.app\[(\d+)\]\.deadline$", key)
        if m:
            deadlines.setdefault(int(m.group(1)), v)
    traffic = []
    for k, app in enumerate(apps):
        if "messageLength" not in app or "sendInterval" not in app:
            continue
        rate = None
        try:
            rate = float(re.match(r"[0-9.]+", app["messageLength"]).group(0)) * 8 / parse_time(app["sendInterval"]) / 1e3
        except (AttributeError, TypeError, ZeroDivisionError):
            pass
        traffic.append({"name": app.get("trafficClass", f"app[{k}]"), "app": app.get("typename"),
                        "mode": app.get("mode", "cbr"), "packet": app["messageLength"], "interval": app["sendInterval"],
                        "on": app.get("onTime"), "off": app.get("offTime"), "destination": app.get("destAddress", app.get("destAddresses")),
                        "deadline": deadlines.get(k), "kbps": round(rate, 1) if rate else None})
    return {
        "descriptions": list(dict.fromkeys(descr)),
        "launch": config.get("*.veinsManager.launchConfig"),
        "rats": rats,
        "decision": {k: mgr.get(k) for k in ("policy", "decisionInterval", "handoverExecDelay",
                                              "pingPongWindow", "startTime", "timeToTrigger", "ensembleWeightCoverage", "ensembleWeightSinr",
                                              "ensembleWeightLatency", "ensembleWeightLoad", "ensembleStickiness") if k in mgr},
        "traffic": traffic,
        "signal_model": {k: mon.get(k) for k in ("signalSource", "measurementMaxAge", "nrMinSinr", "lteMinSinr", "useDistance", "useSignal",
                                                  "txPowerDbm", "pathLossExponent", "referenceLossDb", "updateInterval") if k in mon},
        "cellular": pick("**.numBands", "**.ueTxPower", "**.eNodeBTxPower",
                         "*.car[*].cellularNic.rrc.nrHandoverController.dynamicCellAssociation",
                         "*.car[*].cellularNic.rrc.nrHandoverController.enableHandover",
                         "*.gNodeB*.cellularNic.phy.handoverLatency", "*.gNodeB*.cellInfo.broadcastMessageInterval"),
        "config": [[k, v] for k, v in config.items() if k not in ("description", "result-dir")],
    }


def lte_equipped(config):
    """False when the run switched LTE off (hasLte = false): cellular is then NR alone"""
    return next((v for key, v in config.items() if key.endswith("ratCoverageMonitor.hasLte")), "true") != "false"


def cellular_merged(config):
    """LTE equipped and lteInterface == nrInterface: the manager cannot tell LTE from NR; report them as one 'Cellular'"""
    get = lambda k: next((v for key, v in config.items() if key.endswith("multiRatAppManager." + k)), None)
    lte, nr = get("lteInterface"), get("nrInterface")
    return lte_equipped(config) and lte is not None and lte == nr


def read_vec(path, merged, names):
    """bin the run's time series; returns (t, series, t_end)"""
    want = {}  # vector id -> (kind, label)
    with open(path, errors="replace") as f:
        for line in f:
            if not line.startswith("vector "):
                continue
            p = line.split()
            if len(p) < 4:
                continue
            vid, mod, name = p[1], p[2], unquote(p[3])
            if RE_STATS.search(mod):
                for label, sig in RAT_SERIES:
                    if name == sig + ":vector":
                        if merged and label in ("NR", "LTE"):
                            label = "Cellular"
                        want[vid] = ("rat", label)
            elif RE_CAR_APP.search(mod) and name == "packetSent:vector(packetBytes)":
                want[vid] = ("offered", None)
            elif RE_SERVER_APP.search(mod) and name == "packetReceived:vector(packetBytes)":
                want[vid] = ("delivered", None)
            elif RE_SERVER_APP.search(mod) and name == "endToEndDelay:vector":
                k = int(RE_SERVER_APP.search(mod).group(1))
                want[vid] = ("delay", names.get(k, f"app[{k}]"))
            elif RE_MANAGER.search(mod) and name == "handoverCount:vector":
                want[vid] = ("handover", None)
    samples = {vid: [] for vid in want}
    t_end = 0.0
    with open(path, errors="replace") as f:
        for line in f:
            c = line[:1]
            if not c.isdigit():
                continue
            vid, _, rest = line.partition("\t")
            if vid not in samples:
                continue
            p = rest.split("\t")  # event, time, value (ETV)
            if len(p) < 3:
                continue
            t, v = float(p[1]), float(p[2])
            samples[vid].append((t, v))
            if t > t_end:
                t_end = t
    return want, samples, t_end


def bin_series(want, samples, t_end):
    width = next((w for w in BIN_STEPS if t_end / w <= MAX_POINTS), BIN_STEPS[-1])
    nb = max(1, int(t_end / width + 0.999999))
    t = [round((i + 1) * width, 6) for i in range(nb)]

    def idx(x):
        return min(nb - 1, int(x / width))

    rat = {}
    rat_counts = {}
    offered, delivered = [0.0] * nb, [0.0] * nb
    dsum, dcnt, ho = {}, {}, [0] * nb
    for vid, (kind, label) in want.items():
        pts = samples[vid]
        if kind == "rat":
            # value held per vector, summed per label (Cellular = NR + LTE)
            last = [None] * nb
            for x, v in pts:
                last[idx(x)] = v
            held, cur = [], None
            for v in last:
                cur = v if v is not None else cur
                held.append(cur)
            acc = rat.setdefault(label, [None] * nb)
            for i, v in enumerate(held):
                if v is not None:
                    acc[i] = (acc[i] or 0) + v
            rat_counts[label] = rat_counts.get(label, 0) + len(pts)
        elif kind == "offered":
            for x, v in pts:
                offered[idx(x)] += v
        elif kind == "delivered":
            for x, v in pts:
                delivered[idx(x)] += v
        elif kind == "delay":
            ds, dc = dsum.setdefault(label, [0.0] * nb), dcnt.setdefault(label, [0] * nb)
            for x, v in pts:
                i = idx(x)
                ds[i] += v
                dc[i] += 1
        elif kind == "handover":
            for x, _ in pts:
                ho[idx(x)] += 1
    scale = 8e-6 / width
    order = [lbl for lbl in ("DSRC", "WiFi", "Cellular", "NR", "LTE", "Unconnected") if lbl in rat]
    return {
        "bin_s": width,
        "t": t,
        "rat": {lbl: rat[lbl] for lbl in order},
        "offered_mbps": [round(v * scale, 6) for v in offered],
        "delivered_mbps": [round(v * scale, 6) for v in delivered],
        "delay_ms": {lbl: [round(s / c * 1e3, 4) if c else None for s, c in zip(dsum[lbl], dcnt[lbl])] for lbl in dsum},
        "handovers": ho,
    }


def tail(path, n):
    try:
        with open(path, errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None
    return "".join(lines[-n:])


def load_run(run_dir):
    meta = {}
    try:
        with open(os.path.join(run_dir, "run.json")) as f:
            meta = json.load(f)
    except (OSError, ValueError):
        pass
    scas = sorted(glob.glob(os.path.join(run_dir, "*.sca")) + glob.glob(os.path.join(run_dir, "*", "*.sca")))
    vecs = [s[:-4] + ".vec" for s in scas if os.path.exists(s[:-4] + ".vec")]
    key = [CACHE_VERSION] + [[p, os.path.getsize(p), int(os.path.getmtime(p))] for p in scas + vecs]
    key += [os.path.getmtime(os.path.join(run_dir, x)) if os.path.exists(os.path.join(run_dir, x)) else 0
            for x in ("run.json", "console.log")]
    cache_path = os.path.join(run_dir, ".report-cache.json")
    try:
        with open(cache_path) as f:
            cached = json.load(f)
        if cached.get("key") == key:
            return cached["run"]
    except (OSError, ValueError):
        pass

    name = os.path.basename(run_dir.rstrip("/"))
    run = {"id": name, "meta": meta, "status": "no results", "summary": None, "series": None}
    if scas:
        attrs, config, scalars, stats, pars, descr = read_sca(scas[0])
        merged = cellular_merged(config)
        t_end = 0.0
        series = None
        if vecs:
            want, samples, t_end = read_vec(vecs[0], merged, class_names(config))
            series = bin_series(want, samples, t_end)
        sim_time = parse_time(meta.get("sim_time")) or parse_time(config.get("sim-time-limit")) or t_end
        try:
            started = datetime.strptime(attrs.get("datetimef", ""), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            started = None
        run.update({
            "config": attrs.get("configname"),
            "network": (attrs.get("network") or "").rsplit(".", 1)[-1],
            "started": meta.get("started") or started,  # run.json is UTC; the .sca stamp is the simulator's local time
            "sim_time": sim_time,
            "cellular_merged": merged,
            "summary": summarize(config, scalars, stats, sim_time),
            "setup": scenario_setup(config, pars, scalars, descr),
            "series": series,
        })
        run["status"] = "ok"
        if meta.get("exit_code", 0) != 0 or not run["summary"]["vehicles"]:
            run["status"] = "failed"
    elif meta.get("exit_code") not in (None, 0):
        run["status"] = "failed"
    run["started"] = run.get("started") or meta.get("started") or \
        datetime.fromtimestamp(os.path.getmtime(run_dir), timezone.utc).isoformat()
    run["log"] = tail(os.path.join(run_dir, "console.log"), LOG_TAIL)
    try:
        with open(cache_path, "w") as f:
            json.dump({"key": key, "run": run}, f)
    except OSError:
        pass
    return run


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    root = argv[0]
    out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(root, "report.html")
    runs = []
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if os.path.isdir(p) and not d.startswith("."):
            run = load_run(p)
            if run["status"] != "no results" or run["meta"] or run["log"]:
                runs.append(run)
    runs.sort(key=lambda r: r["started"] or "", reverse=True)
    data = json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "runs": runs},
                      separators=(",", ":")).replace("</", "<\\/")
    page = TEMPLATE.replace("/*DATA*/", data).replace("{{ROOT}}", html.escape(os.path.abspath(root)))
    with open(out, "w") as f:
        f.write(page)
    print(f"report: {len(runs)} run(s) -> {out}")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MultiRATVANET runs</title>
<style>
:root {
  color-scheme: light;
  --surface-0: #f5f4f1; --surface-1: #fcfcfb; --border: #e3e1dc; --grid: #ecebe7;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #7b7a75;
  --good: #1a7f37; --bad: #c62828;
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100; --s5: #e87ba4;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-0: #111110; --surface-1: #1a1a19; --border: #2e2e2b; --grid: #262624;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8f8e86;
    --good: #4cc26a; --bad: #ff6b6b;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-0: #111110; --surface-1: #1a1a19; --border: #2e2e2b; --grid: #262624;
  --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8f8e86;
  --good: #4cc26a; --bad: #ff6b6b;
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface-0); color: var(--text-primary);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1180px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 20px; margin: 0 0 2px; }
h2 { font-size: 15px; margin: 32px 0 10px; }
h3 { font-size: 13px; margin: 0 0 6px; font-weight: 600; }
.muted { color: var(--text-muted); }
.sub { color: var(--text-secondary); margin: 0 0 18px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin: 0 0 16px; }
select { font: inherit; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px;
         background: var(--surface-1); color: var(--text-primary); max-width: 100%; }
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.tile .v { font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
.tile .v small { font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-left: 3px; }
.tile .l { color: var(--text-secondary); font-size: 12px; }
.tile .d { color: var(--text-muted); font-size: 12px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 520px), 1fr)); gap: 12px; }
.chart { position: relative; }
.chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.chart .axis text { fill: var(--text-muted); font-size: 11px; }
.chart .gridline { stroke: var(--grid); stroke-width: 1; }
.chart .baseline { stroke: var(--border); stroke-width: 1; }
.chart .hair { stroke: var(--text-muted); stroke-width: 1; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 0 0 6px; font-size: 12px; color: var(--text-secondary); }
.key { display: inline-block; width: 14px; height: 2px; border-radius: 1px; vertical-align: middle; margin-right: 6px; }
.key.box { width: 10px; height: 10px; border-radius: 2px; }
.tip { position: absolute; pointer-events: none; background: var(--surface-1); border: 1px solid var(--border);
       border-radius: 8px; padding: 6px 9px; font-size: 12px; box-shadow: 0 2px 10px rgba(0,0,0,.12);
       white-space: nowrap; z-index: 2; }
.tip .row { display: flex; align-items: center; gap: 6px; }
.tip b { font-variant-numeric: tabular-nums; }
.tip .ts { color: var(--text-muted); margin-bottom: 2px; }
.empty { color: var(--text-muted); padding: 40px 0; text-align: center; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
th { color: var(--text-secondary); font-weight: 600; font-size: 12px; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
#history tbody tr { cursor: pointer; }
.lead { margin: 0 0 4px; font-weight: 500; }
#history tbody tr:hover { background: color-mix(in srgb, var(--s1) 7%, transparent); }
tbody tr.sel { background: color-mix(in srgb, var(--s1) 14%, transparent); }
.st-ok { color: var(--good); } .st-failed { color: var(--bad); } .st-none { color: var(--text-muted); }
dl.kv { display: grid; grid-template-columns: max-content 1fr; gap: 3px 14px; margin: 0; font-size: 13px; }
dl.kv dt { color: var(--text-secondary); } dl.kv dd { margin: 0; font-family: var(--mono); font-size: 12px; word-break: break-all; }
pre.log { font: 12px/1.4 var(--mono); background: var(--surface-0); border: 1px solid var(--border); border-radius: 8px;
          padding: 10px 12px; overflow: auto; max-height: 420px; margin: 8px 0 0; white-space: pre; }
details > summary { cursor: pointer; color: var(--text-secondary); font-size: 12px; margin-top: 8px; }
.note { font-size: 12px; color: var(--text-secondary); margin: 8px 0 0; }
.hbar .lab { fill: var(--text-secondary); font-size: 12px; }
.hbar .val { fill: var(--text-primary); font-size: 12px; font-variant-numeric: tabular-nums; }
.hbar .whisk { stroke: var(--text-primary); stroke-width: 1.5; }
.hbar .hit { fill: transparent; }
.hbar .hit:hover { fill: color-mix(in srgb, var(--text-muted) 10%, transparent); }
.hbar .sep { stroke: var(--border); stroke-dasharray: 3 3; }
td.best { font-weight: 600; }
#cmp-table tbody tr { cursor: pointer; }
#cmp-table tbody tr:hover { background: color-mix(in srgb, var(--s1) 7%, transparent); }
tr.base td:first-child { color: var(--text-secondary); }
</style>
</head>
<body>
<main>
  <h1>MultiRATVANET runs</h1>
  <p class="sub">Results in <code>{{ROOT}}</code>, generated <span id="gen"></span>. Rebuilt by <code>dash/run-experiment.sh</code> after every run.</p>

  <div id="compare"></div>

  <h2 id="one-run">One run</h2>
  <div class="filters">
    <label for="pick" class="muted">Run</label>
    <select id="pick"></select>
    <span id="status"></span>
  </div>

  <div id="run"></div>

  <h2>History</h2>
  <div class="card scroll"><table id="history"></table></div>
</main>

<script id="data" type="application/json">/*DATA*/</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("data").textContent);
const RUNS = DATA.runs;
// fixed slot per entity, never by rank (Cellular takes NR's slot when LTE/NR share one interface)
const RAT_COLOR = { DSRC: "--s1", WiFi: "--s2", NR: "--s3", Cellular: "--s3", LTE: "--s4", Unconnected: "--s5" };
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v);
  }
  for (const k of kids) if (k != null) e.append(k);
  return e;
};
const svgEl = (tag, attrs = {}) => {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
};
const fmt = (v, d = 1) => v == null || !isFinite(v) ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: 0 });
const pct = v => v == null ? "–" : (v * 100).toFixed(1) + "%";
const when = s => s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "–";
const label = r => (r.meta && r.meta.scenario ? `${r.meta.scenario} · ${r.meta.policy}` : (r.config || r.id)) + (r.meta && r.meta.name ? ` · ${r.meta.name}` : "");

function niceMax(v) {
  if (!(v > 0)) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v))), m = v / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
}

// Line (or column) chart over a shared time axis, with crosshair + one tooltip for every series.
function chart({ title, unit, t, series, bars = false, digits = 1, empty = "No samples recorded for this run" }) {
  const card = el("div", { class: "card chart" });
  card.append(el("h3", { text: title }));
  const live = series.filter(s => s.values.some(v => v != null && v !== 0));
  if (series.length > 1) {
    const lg = el("div", { class: "legend" });
    for (const s of series) lg.append(el("span", {}, el("span", { class: "key" + (bars ? " box" : ""), style: `background:var(${s.color})` }), s.name));
    card.append(lg);
  }
  if (!t.length || !live.length) { card.append(el("div", { class: "empty", text: empty })); return card; }

  // draw at the card's real width so axis text stays 11px on phones (2 columns above ~1100px)
  const avail = document.getElementById("run").clientWidth || 560;
  const W = Math.max(280, Math.min(560, avail >= 1066 ? (avail - 12) / 2 - 34 : avail - 34)), H = 220, m = { l: 44, r: 10, t: 8, b: 24 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const tMax = t[t.length - 1], bin = t.length > 1 ? t[1] - t[0] : t[0];
  let yMax = niceMax(Math.max(...series.flatMap(s => s.values.filter(v => v != null))));
  if (digits === 0) yMax = Math.max(4, Math.ceil(yMax / 4) * 4);  // whole-number ticks for counts
  const x = v => m.l + (v / tMax) * iw, y = v => m.t + ih - (v / yMax) * ih;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title });
  const ax = svgEl("g", { class: "axis" });
  for (let i = 0; i <= 4; i++) {
    const v = yMax * i / 4;
    ax.append(svgEl("line", { class: i ? "gridline" : "baseline", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }));
    const tx = svgEl("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end" }); tx.textContent = fmt(v, 2); ax.append(tx);
  }
  for (let i = 0; i <= 5; i++) {
    const v = tMax * i / 5, tx = svgEl("text", { x: x(v), y: H - 6, "text-anchor": i === 0 ? "start" : i === 5 ? "end" : "middle" });
    tx.textContent = fmt(v, 0) + " s"; ax.append(tx);
  }
  svg.append(ax);
  if (bars) {
    const s = series[0], bw = Math.max(1, iw / t.length - 2);
    s.values.forEach((v, i) => {
      if (!v) return;
      const h = Math.max(1, ih - (y(v) - m.t)), x0 = x(t[i] - bin) + 1;
      svg.append(svgEl("rect", { x: x0, y: y(v), width: bw, height: h, rx: Math.min(2, bw / 2), fill: `var(${s.color})` }));
    });
  } else {
    for (const s of series) {
      let d = "", pen = false;
      s.values.forEach((v, i) => {
        if (v == null) { pen = false; return; }
        d += (pen ? "L" : "M") + x(t[i]).toFixed(1) + "," + y(v).toFixed(1); pen = true;
      });
      svg.append(svgEl("path", { d, fill: "none", stroke: `var(${s.color})`, "stroke-width": 2,
                                 "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" }));
    }
  }
  const hair = svgEl("line", { class: "hair", y1: m.t, y2: m.t + ih, visibility: "hidden", "vector-effect": "non-scaling-stroke" });
  svg.append(hair);
  card.append(svg);
  const tip = el("div", { class: "tip", hidden: "" });
  card.append(tip);

  const show = i => {
    const xx = x(t[i]);
    hair.setAttribute("x1", xx); hair.setAttribute("x2", xx); hair.setAttribute("visibility", "visible");
    tip.replaceChildren(el("div", { class: "ts", text: `t = ${fmt(t[i] - bin, 1)}–${fmt(t[i], 1)} s` }));
    for (const s of series) {
      tip.append(el("div", { class: "row" }, el("span", { class: "key", style: `background:var(${s.color})` }),
                   el("b", { text: s.values[i] == null ? "–" : fmt(s.values[i], digits) + (unit ? " " + unit : "") }),
                   series.length > 1 ? el("span", { class: "muted", text: s.name }) : null));
    }
    tip.hidden = false;
    const r = svg.getBoundingClientRect(), px = (xx / W) * r.width;
    tip.style.top = (svg.offsetTop + 8) + "px";
    tip.style.left = Math.min(Math.max(0, px + 12), r.width - tip.offsetWidth) + "px";
  };
  const hide = () => { hair.setAttribute("visibility", "hidden"); tip.hidden = true; };
  svg.addEventListener("pointermove", ev => {
    const r = svg.getBoundingClientRect(), vx = (ev.clientX - r.left) / r.width * W;
    const i = Math.min(t.length - 1, Math.max(0, Math.round(((vx - m.l) / iw) * tMax / bin - 1)));
    show(i);
  });
  svg.addEventListener("pointerleave", hide);

  // table view: every value reachable without hovering
  const det = el("details", {}, el("summary", { text: "Data table" }));
  const tb = el("table");
  tb.append(el("thead", {}, el("tr", {}, el("th", { class: "n", text: "t (s)" }), ...series.map(s => el("th", { class: "n", text: s.name + (unit ? ` (${unit})` : "") })))));
  const body = el("tbody");
  t.forEach((tt, i) => body.append(el("tr", {}, el("td", { class: "n", text: fmt(tt, 1) }), ...series.map(s => el("td", { class: "n", text: fmt(s.values[i], digits) })))));
  tb.append(body);
  det.append(el("div", { class: "scroll", style: "max-height:260px" }, tb));
  card.append(det);
  return card;
}

function tile(value, labelText, detail, unit) {
  return el("div", { class: "card tile" }, el("div", { class: "v", text: value }, unit && value !== "–" ? el("small", { text: unit }) : null), el("div", { class: "l", text: labelText }),
            detail ? el("div", { class: "d", text: detail }) : null);
}

function renderRun(r) {
  const root = document.getElementById("run");
  root.replaceChildren();
  const st = document.getElementById("status");
  st.className = r.status === "ok" ? "st-ok" : r.status === "failed" ? "st-failed" : "st-none";
  st.textContent = r.status === "ok" ? "completed" : r.status;
  document.querySelectorAll("#history tbody tr").forEach(tr => tr.classList.toggle("sel", tr.dataset.id === r.id));

  if (r.setup) root.append(...renderSetup(r));
  const s = r.summary;
  root.append(el("h2", { text: "Final results" }));
  if (s) {
    const classes = s.classes || [];
    const tiles = el("div", { class: "tiles" });
    if (classes.length > 1) {
      for (const c of classes) {
        tiles.append(tile(pct(c.pdr), `${c.name}: delivered`, `${fmt(c.received, 0)} of ${fmt(c.sent, 0)} packets` + (c.direction ? `, ${c.direction}` : "")));
        if (c.within_deadline != null)
          tiles.append(tile(pct(c.within_deadline), `${c.name}: on time`, `sent and arrived within ${fmt(c.deadline_ms, 0)} ms`));
        tiles.append(tile(fmt(c.delay_mean_ms, 1), `${c.name}: mean delay`, c.delay_max_ms != null ? `worst ${fmt(c.delay_max_ms, 0)} ms` : null, "ms"));
      }
    } else {
      tiles.append(tile(pct(s.pdr), "Delivery ratio", `${fmt(s.received, 0)} of ${fmt(s.sent, 0)} packets`),
                   tile(fmt(s.delay_mean_ms, 1), "Mean end-to-end delay", s.delay_max_ms != null ? `worst ${fmt(s.delay_max_ms, 0)} ms` : null, "ms"));
    }
    tiles.append(
      tile(fmt(s.throughput_mbps, 3), "Throughput at server", `over ${fmt(r.sim_time, 0)} s`, "Mbit/s"),
      tile(fmt(s.handovers_per_vehicle, 2), "Switches per vehicle", `${fmt(s.handovers, 0)} total, ${fmt(s.ping_pong, 0)} ping-pong`));
    if (s.interruption_count)
      tiles.append(tile(fmt(s.interruption_mean_ms, 1), "Switch interruption (mean)",
                        `worst ${fmt(s.interruption_max_ms, 0)} ms over ${fmt(s.interruption_count, 0)} switches, ${fmt(s.interruption_lost, 0)} packets lost`, "ms"));
    tiles.append(tile(fmt(s.vehicles, 0), "Vehicles", null),
                 tile(pct(s.connectivity), "Connectivity", `${fmt(s.outage_s, 1)} s with no usable RAT in total`));
    root.append(tiles);
    const share = el("div", { class: "card", style: "margin-top:10px" }, el("h3", { text: "Time on each RAT (mean selection share per vehicle)" }));
    const lg = el("div", { class: "legend" });
    for (const [k, v] of Object.entries(s.shares)) {
      if (v == null) continue;
      lg.append(el("span", {}, el("span", { class: "key box", style: `background:var(${RAT_COLOR[k] || "--s5"})` }), `${k} ${pct(v)}`));
    }
    share.append(lg);
    if (r.cellular_merged) share.append(el("p", { class: "note", text: "LTE and NR use the same IP interface in this run, so the manager cannot tell them apart; they are shown together as Cellular." }));
    root.append(share);
    if (s.inputs && Object.keys(s.inputs).length) {
      const inp = el("div", { class: "card", style: "margin-top:10px" }, el("h3", { text: "What the policies saw (average while each RAT was in range)" }));
      inp.append(simpleTable(["RAT", "SINR margin", "Load (sensed)", "Link rate", "Probe round trip"],
        Object.entries(s.inputs).map(([k, v]) => [k, v.SinrMargin != null ? fmt(v.SinrMargin, 1) + " dB" : null, v.Load != null ? pct(v.Load) : null,
                                                 v.LinkRate != null ? fmt(v.LinkRate, 1) + " Mbit/s" : (v.Capacity != null ? fmt(v.Capacity, 1) + " Mbit/s (capacity)" : null), v.ProbeRtt != null ? fmt(v.ProbeRtt, 2) + " ms" : (v.Latency != null ? fmt(v.Latency, 2) + " ms (estimate)" : null)]), [1, 2, 3, 4]));
      root.append(inp);
    }
  } else {
    root.append(el("div", { class: "card empty", text: "This run produced no result files. See the console log below." }));
  }

  if (r.series) {
    const S = r.series, t = S.t;
    root.append(el("h2", { text: "Over time" }));
    root.append(el("p", { class: "sub", text: `Bins of ${S.bin_s} s.` }));
    const g = el("div", { class: "grid2" });
    g.append(chart({ title: "Vehicles on each RAT", unit: "", t, digits: 0,
                     series: Object.entries(S.rat).map(([k, v]) => ({ name: k, color: RAT_COLOR[k] || "--s5", values: v })) }));
    g.append(chart({ title: "Throughput, Mbit/s", unit: "Mbit/s", t, digits: 3,
                     series: [{ name: "Offered (vehicles)", color: "--s1", values: S.offered_mbps },
                              { name: "Delivered (server)", color: "--s2", values: S.delivered_mbps }] }));
    const dl = Array.isArray(S.delay_ms) ? { Delay: S.delay_ms } : S.delay_ms;
    g.append(chart({ title: "Mean end-to-end delay, ms", unit: "ms", t, digits: 1,
                     series: Object.entries(dl).map(([k, v], i) => ({ name: k, color: `--s${i + 1}`, values: v })) }));
    g.append(chart({ title: "Handovers per bin", unit: "", t, digits: 0, bars: true,
                     series: [{ name: "Handovers", color: "--s1", values: S.handovers }], empty: "No handovers in this run" }));
    root.append(g);
  }

  root.append(el("h2", { text: "Run details" }));
  const m = r.meta || {}, kv = el("dl", { class: "kv" });
  const add = (k, v) => { if (v != null && v !== "" && !(Array.isArray(v) && !v.length)) kv.append(el("dt", { text: k }), el("dd", { text: Array.isArray(v) ? v.join("\n") : String(v) })); };
  add("Run", r.id); add("Config", r.config || m.config); add("Network", r.network); add("Started", when(r.started));
  add("Simulated time", r.sim_time != null ? fmt(r.sim_time, 1) + " s" : m.sim_time); add("Seed set", m.seed);
  add("Parameters", m.params); add("Overrides", m.overrides); add("Image", m.image); add("Image id", m.image_id);
  add("Repo commit", m.repo_commit); add("Who", m.who && m.host ? `${m.who}@${m.host}` : m.who); add("Exit code", m.exit_code);
  const det = el("div", { class: "card" }, kv);
  if (r.log) {
    det.append(el("details", r.status === "ok" ? {} : { open: "" }, el("summary", { text: `Console log (last ${r.log.split("\n").length - 1} lines)` }), el("pre", { class: "log", text: r.log })));
  } else {
    det.append(el("p", { class: "note", text: "No console log (run was not started with dash/run-experiment.sh)." }));
  }
  root.append(det);
}

function simpleTable(head, rows, numeric = []) {
  const t = el("table");
  t.append(el("thead", {}, el("tr", {}, ...head.map((h, i) => el("th", { class: numeric.includes(i) ? "n" : "", text: h })))));
  const b = el("tbody", { class: "static" });
  for (const row of rows) b.append(el("tr", {}, ...row.map((c, i) => el("td", { class: numeric.includes(i) ? "n" : "", text: c == null || c === "" ? "–" : String(c) }))));
  t.append(b);
  return el("div", { class: "scroll" }, t);
}

function kvList(pairs) {
  const dl = el("dl", { class: "kv" });
  for (const [k, v] of pairs) if (v != null && v !== "") dl.append(el("dt", { text: k }), el("dd", { text: String(v) }));
  return dl;
}

function renderSetup(r) {
  const u = r.setup, m = r.meta || {}, out = [el("h2", { text: "Scenario and setup" })];
  const veh = r.summary ? r.summary.vehicles : null;
  const top = el("div", { class: "card" });
  for (const d of u.descriptions) top.append(el("p", { class: "lead", text: d }));
  top.append(el("p", { class: "note", text: "These descriptions are the ini's own text. What actually ran: " +
    `${veh != null ? veh + " vehicles" : "vehicle count unknown"} (from the SUMO route file; numCars has no effect), ` +
    `${fmt(r.sim_time, 0)} s simulated, seed set ${m.seed || "0"}.` }));
  top.append(kvList([["Network", r.network], ["Road and traffic", u.launch], ["Config", r.config],
    ["Parameters changed for this run", (m.params || []).join(", ") || "none (ini values)"]]));
  out.push(top);

  const measured = (u.signal_model.signalSource || "proxy") === "measured";
  const infra = el("div", { class: "card", style: "margin-top:12px" }, el("h3", { text: "Radios and infrastructure" }));
  const cell = x => x.rat === "NR" || x.rat === "LTE";
  infra.append(simpleTable(["RAT", "Towers", "Where", measured ? "Range (unused)" : "Range", "In range needs", "Assumed latency", "Assumed capacity", "Interface"],
    u.rats.map(x => [x.rat,
                     x.infra_type === "" ? (measured ? "none" : "none (treated as everywhere)") : (x.towers === 0 && measured ? "0 (never in range)" : x.towers),
                     x.positions.length ? x.positions.join(" ") : (x.infra_type === "" || x.towers === 0 ? "–" : "not recorded"),
                     x.range,
                     measured ? (cell(x) ? `measured SINR ≥ ${x.min_sinr}` : `beacon ≥ ${x.rssi_threshold}`) : `estimate ≥ ${x.rssi_threshold}`,
                     x.latency_ms != null ? x.latency_ms + " ms" : null,
                     x.capacity_mbps != null ? x.capacity_mbps + " Mbit/s" : null, x.interface])));
  infra.append(el("p", { class: "note", text: measured
    ? "Policies are given only what the car itself observes: signal, sensed channel load (DSRC/WiFi), link rate, and the round trip and loss of its own probes."
    : "Latency and capacity are fixed numbers the policies are told, not measured." }));
  out.push(infra);

  const g = el("div", { class: "grid2", style: "margin-top:12px" });
  const right = el("div", { class: "card" });
  right.append(el("h3", { text: "How cars choose" }));
  const d = u.decision, ens = (d.policy || "").includes("Ensemble");
  right.append(kvList([["Policy", d.policy], ["Re-decides every", d.decisionInterval], ["First decision at", d.startTime],
    ["Better RAT must hold for", d.timeToTrigger], ["Extra switch delay", d.handoverExecDelay], ["Ping-pong window", d.pingPongWindow],
    ...(ens ? [["Ensemble weights", `coverage ${d.ensembleWeightCoverage}, signal ${d.ensembleWeightSinr}, latency ${d.ensembleWeightLatency}, load ${d.ensembleWeightLoad}`],
               ["Stickiness", d.ensembleStickiness]] : [])]));
  const sm = u.signal_model;
  const right2 = el("div", { class: "card" });
  g.append(right);
  right2.append(el("h3", { text: measured ? "Signal given to policies: measured" : "Signal given to policies: distance estimate" }));
  right2.append(kvList(measured ? [
      ["DSRC / WiFi", "received power and SNIR of beacons from RSUs / APs (other cars' frames ignored)"],
      ["NR / LTE", "downlink SINR of the serving cell, measured by Simu5G"],
      ["Probes", "the car probes every linked RAT; the server echoes; a RAT is usable only while echoes come back"],
      ["Refreshed every", sm.updateInterval], ["Counts as lost after", sm.measurementMaxAge + " without a measurement"]]
    : [["Model", `distance to nearest tower: ${sm.txPowerDbm} dBm − ${sm.referenceLossDb} dB − 10·${sm.pathLossExponent}·log10(d)`],
       ["Refreshed every", sm.updateInterval], ["In range needs", [sm.useDistance === "true" ? "within range" : null, sm.useSignal === "true" ? "above min RSSI" : null].filter(Boolean).join(" and ")],
       ["Caveat", "a RAT with no towers (LTE here) scores as if the car sat under one"]]));
  right.append(el("h3", { text: "Traffic", style: "margin-top:12px" }));
  right.append(kvList((Array.isArray(u.traffic) ? u.traffic : []).map(t => [t.name,
    `${t.packet} every ${t.interval}` + (t.mode === "onoff" ? ` in bursts (on ${t.on}, off ${t.off})` : "") +
    (t.kbps ? `, ${fmt(t.kbps, 1)} kbit/s while sending` : "") + ` to ${t.destination}` + (t.deadline ? `, deadline ${t.deadline}` : "")])));
  right2.append(el("h3", { text: "Cellular (Simu5G)", style: "margin-top:12px" }));
  right2.append(kvList(Object.entries(u.cellular).map(([k, v]) => [k.replace(/^\*\.car\[\*\]\.|^\*+\./, ""), v])));
  g.append(right2);
  out.push(g);

  const overridden = new Set((m.overrides || []).map(o => o.replace(/^--/, "").split("=")[0]));
  const cfg = el("details", {}, el("summary", { text: `Initial configuration: all ${u.config.length} effective ini entries (first match wins; this run's overrides marked)` }));
  cfg.append(simpleTable(["Key", "Value", ""], u.config.map(([k, v]) => [k, v, overridden.has(k) ? "set for this run" : ""])));
  out.push(el("div", { class: "card", style: "margin-top:12px" }, cfg));
  return out;
}

function renderHistory() {
  const tb = document.getElementById("history");
  const cols = [["Started", r => when(r.started)], ["Run", label], ["Config", r => r.config || (r.meta && r.meta.config) || "–"],
    ["Status", r => r.status], ["Sim time", r => r.sim_time != null ? fmt(r.sim_time, 0) + " s" : "–", 1],
    ["Vehicles", r => r.summary ? fmt(r.summary.vehicles, 0) : "–", 1], ["Delivery", r => r.summary ? pct(r.summary.pdr) : "–", 1],
    ["Safety on time", r => { const c = r.summary && (r.summary.classes || []).find(x => x.within_deadline != null); return c ? pct(c.within_deadline) : "–"; }, 1],
    ["Throughput", r => r.summary && r.summary.throughput_mbps != null ? fmt(r.summary.throughput_mbps, 3) + " Mbit/s" : "–", 1],
    ["Delay", r => r.summary && r.summary.delay_mean_ms != null ? fmt(r.summary.delay_mean_ms, 1) + " ms" : "–", 1],
    ["HO/veh", r => r.summary ? fmt(r.summary.handovers_per_vehicle, 2) : "–", 1]];
  tb.append(el("thead", {}, el("tr", {}, ...cols.map(([h, , n]) => el("th", { class: n ? "n" : "", text: h })))));
  const body = el("tbody");
  for (const r of RUNS) {
    const tr = el("tr", { tabindex: "0" }, ...cols.map(([h, f, n]) => {
      const td = el("td", { class: n ? "n" : "", text: f(r) });
      if (h === "Status") td.className = r.status === "ok" ? "st-ok" : r.status === "failed" ? "st-failed" : "st-none";
      return td;
    }));
    tr.dataset.id = r.id;
    const go = () => { document.getElementById("pick").value = r.id; history.replaceState(null, "", "#" + r.id); renderRun(r); window.scrollTo({ top: 0, behavior: "smooth" }); };
    tr.addEventListener("click", go);
    tr.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
    body.append(tr);
  }
  tb.append(body);
}

// ---------------------------------------------------------------------------------------------
// Compare policies: runs of the same scenario, length, image and parameters, one row per policy,
// averaged over seeds.
const POLICY_ORDER = ["coverage_priority", "sinr", "latency_qos", "load", "ensemble", "ml", "example_split",
                      "only_dsrc", "only_wifi", "only_nr"];
const POLICY_LABEL = { coverage_priority: "CoveragePriority", sinr: "Sinr", latency_qos: "LatencyQos", load: "Load",
  ensemble: "Ensemble", ml: "Ml", example_split: "ExampleSplit", only_dsrc: "only DSRC", only_wifi: "only WiFi", only_nr: "only 5G" };
const isBaseline = p => p.startsWith("only_");
const policyLabel = p => POLICY_LABEL[p] || p;
// [key, title, kind, better]  kind: pct | ms | num
const CMP_METRICS = [
  ["safety_pdr", "Safety delivered", "pct", "high"],
  ["safety_on_time", "Safety on time (100 ms)", "pct", "high"],
  ["info_pdr", "Infotainment delivered", "pct", "high"],
  ["info_on_time", "Infotainment on time (1 s)", "pct", "high"],
  ["safety_delay", "Safety delay", "ms", "low"],
  ["info_delay", "Infotainment delay", "ms", "low"],
  ["ho", "Handovers per car", "num", "low"],
  ["pingpong", "Ping-pongs (all cars)", "num", "low"],
  ["gap", "Switch gap", "ms", "low"],
];

function runMetrics(r) {
  const s = r.summary, out = {};
  for (const c of s.classes || []) {
    const k = c.name === "safety" ? "safety" : c.name === "infotainment" ? "info" : null;
    if (!k) continue;
    out[k + "_pdr"] = c.pdr; out[k + "_on_time"] = c.within_deadline; out[k + "_delay"] = c.delay_mean_ms;
  }
  out.ho = s.handovers_per_vehicle; out.pingpong = s.ping_pong; out.gap = s.interruption_mean_ms;
  for (const [k, v] of Object.entries(s.shares || {})) out["share_" + k] = v;
  return out;
}

function stats(vals) {
  vals = vals.filter(v => v != null && isFinite(v));
  if (!vals.length) return null;
  const m = vals.reduce((a, b) => a + b, 0) / vals.length;
  const sd = vals.length > 1 ? Math.sqrt(vals.reduce((a, b) => a + (b - m) ** 2, 0) / (vals.length - 1)) : 0;
  return { m, sd, n: vals.length };
}

function comparisonGroups() {
  const groups = new Map();
  for (const r of RUNS) {
    const m = r.meta || {};
    if (r.status !== "ok" || !m.scenario || !m.policy || !r.summary) continue;
    const params = (m.params || []).filter(p => !p.includes("vector-recording")).sort();
    const key = [m.scenario, r.sim_time, m.repo_commit || "", params.join(" ")].join("|");
    if (!groups.has(key)) groups.set(key, { key, scenario: m.scenario, simTime: r.sim_time, commit: m.repo_commit || "",
                                             params, runs: [], latest: "" });
    const g = groups.get(key);
    g.runs.push(r);
    if ((r.started || "") > g.latest) g.latest = r.started || "";
  }
  const out = [];
  for (const g of groups.values()) {
    const by = {};
    for (const r of g.runs) (by[r.meta.policy] = by[r.meta.policy] || []).push(r);
    g.policies = Object.keys(by).sort((a, b) => {
      const ia = POLICY_ORDER.indexOf(a), ib = POLICY_ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
    }).map(p => {
      const ms = by[p].map(runMetrics), row = { policy: p, runs: by[p], seeds: by[p].map(r => r.meta.seed || "0").sort() };
      const keys = new Set(ms.flatMap(Object.keys));
      for (const k of keys) row[k] = stats(ms.map(x => x[k]));
      return row;
    });
    if (g.policies.length >= 2) out.push(g);
  }
  return out.sort((a, b) => b.latest.localeCompare(a.latest));
}

const cmpFmt = (v, kind) => v == null ? "–" : kind === "pct" ? (v * 100).toFixed(1) + "%" : kind === "ms" ? fmt(v, 1) + " ms" : fmt(v, 2);

// Horizontal bars, one per policy, with a whisker for the spread across seeds. Policies in the accent
// colour, baselines in neutral grey; a dashed line separates the two.
function hbarChart(title, better, rows, key, kind) {
  const card = el("div", { class: "card chart hbar" });
  card.append(el("h3", {}, title, el("span", { class: "muted", style: "font-weight:400", text: better === "high" ? "  · higher is better" : "  · lower is better" })));
  const lg = el("div", { class: "legend" });
  lg.append(el("span", {}, el("span", { class: "key box", style: "background:var(--s1)" }), "policy"),
            el("span", {}, el("span", { class: "key box", style: "background:var(--text-muted)" }), "baseline (one RAT)"),
            el("span", {}, el("span", { class: "key", style: "background:var(--text-primary);height:1.5px" }), "± spread across seeds"));
  card.append(lg);
  const data = rows.map(r => ({ r, s: r[key] })).filter(d => d.s);
  if (!data.length) { card.append(el("div", { class: "empty", text: "Not recorded in these runs" })); return card; }
  const avail = document.getElementById("compare").clientWidth || 560;
  const W = Math.max(300, Math.min(560, avail >= 1066 ? (avail - 12) / 2 - 34 : avail - 34));
  const rowH = 26, m = { l: 118, r: 70, t: 4, b: 22 }, H = m.t + m.b + rowH * rows.length;
  const iw = W - m.l - m.r;
  const xMax = kind === "pct" ? 1 : niceMax(Math.max(...data.map(d => d.s.m + d.s.sd)));
  const x = v => m.l + Math.max(0, v) / xMax * iw;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title });
  const ax = svgEl("g", { class: "axis" });
  for (let i = 0; i <= 4; i++) {
    const v = xMax * i / 4;
    ax.append(svgEl("line", { class: i ? "gridline" : "baseline", x1: x(v), x2: x(v), y1: m.t, y2: H - m.b }));
    const tx = svgEl("text", { x: x(v), y: H - 6, "text-anchor": i === 0 ? "start" : i === 4 ? "end" : "middle" });
    tx.textContent = kind === "pct" ? (v * 100).toFixed(0) + "%" : fmt(v, 2); ax.append(tx);
  }
  svg.append(ax);
  const tip = el("div", { class: "tip", hidden: "" });
  rows.forEach((row, i) => {
    const y0 = m.t + i * rowH, cy = y0 + rowH / 2, s = row[key], base = isBaseline(row.policy);
    if (i > 0 && base && !isBaseline(rows[i - 1].policy))
      svg.append(svgEl("line", { class: "sep", x1: 0, x2: W, y1: y0, y2: y0 }));
    const lab = svgEl("text", { class: "lab", x: m.l - 8, y: cy + 4, "text-anchor": "end" });
    lab.textContent = policyLabel(row.policy); svg.append(lab);
    if (!s) return;
    const bh = 14, x1 = x(s.m);
    // 4px rounded data end, square at the baseline
    const w = Math.max(1, x1 - m.l), rr = Math.min(4, w);
    svg.append(svgEl("path", { d: `M${m.l},${cy - bh / 2}h${w - rr}a${rr},${rr} 0 0 1 ${rr},${rr}v${bh - 2 * rr}a${rr},${rr} 0 0 1 ${-rr},${rr}h${-(w - rr)}z`,
                               fill: base ? "var(--text-muted)" : "var(--s1)" }));
    if (s.sd > 0) {
      const a = x(s.m - s.sd), b = x(Math.min(kind === "pct" ? 1 : Infinity, s.m + s.sd));
      svg.append(svgEl("line", { class: "whisk", x1: a, x2: b, y1: cy, y2: cy }),
                 svgEl("line", { class: "whisk", x1: a, x2: a, y1: cy - 4, y2: cy + 4 }),
                 svgEl("line", { class: "whisk", x1: b, x2: b, y1: cy - 4, y2: cy + 4 }));
    }
    const val = svgEl("text", { class: "val", x: Math.max(x1, x(s.m + s.sd)) + 6, y: cy + 4 });
    val.textContent = cmpFmt(s.m, kind); svg.append(val);
    const hit = svgEl("rect", { class: "hit", x: 0, y: y0, width: W, height: rowH });
    hit.addEventListener("pointerenter", () => {
      tip.replaceChildren(el("div", { class: "ts", text: policyLabel(row.policy) + (base ? " (baseline)" : "") }),
        el("div", { class: "row" }, el("b", { text: cmpFmt(s.m, kind) }), el("span", { class: "muted", text: `mean of ${s.n} seed${s.n > 1 ? "s" : ""}` })),
        s.n > 1 ? el("div", { class: "row" }, el("span", { class: "muted", text: `± ${kind === "pct" ? (s.sd * 100).toFixed(1) + " points" : fmt(s.sd, 2)} across seeds` })) : null);
      tip.hidden = false;
      const r = svg.getBoundingClientRect();
      tip.style.top = (svg.offsetTop + (cy + rowH / 2) / H * r.height + 4) + "px";
      tip.style.left = Math.min(r.width - tip.offsetWidth, Math.max(0, x1 / W * r.width - tip.offsetWidth / 2)) + "px";
    });
    hit.addEventListener("pointerleave", () => { tip.hidden = true; });
    svg.append(hit);
  });
  card.append(svg, tip);
  return card;
}

// 100% stacked bar per policy: share of attached time on each RAT. 2px surface gap between segments.
function shareChart(rows) {
  const rats = ["DSRC", "WiFi", "NR", "Cellular", "LTE"].filter(k => rows.some(r => r["share_" + k] && r["share_" + k].m > 0));
  const card = el("div", { class: "card chart hbar" });
  card.append(el("h3", { text: "Time on each RAT (share of the time a car was attached, mean over cars and seeds)" }));
  const lg = el("div", { class: "legend" });
  for (const k of rats) lg.append(el("span", {}, el("span", { class: "key box", style: `background:var(${RAT_COLOR[k]})` }), k === "NR" ? "5G-NR" : k));
  card.append(lg);
  const avail = document.getElementById("compare").clientWidth || 560;
  const W = Math.max(300, Math.min(1100, avail - 34)), rowH = 26, m = { l: 118, r: 10, t: 4, b: 22 };
  const H = m.t + m.b + rowH * rows.length, iw = W - m.l - m.r;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Time on each RAT per policy" });
  const ax = svgEl("g", { class: "axis" });
  for (let i = 0; i <= 4; i++) {
    const tx = svgEl("text", { x: m.l + iw * i / 4, y: H - 6, "text-anchor": i === 0 ? "start" : i === 4 ? "end" : "middle" });
    tx.textContent = (25 * i) + "%"; ax.append(tx);
  }
  svg.append(ax);
  const tip = el("div", { class: "tip", hidden: "" });
  rows.forEach((row, i) => {
    const y0 = m.t + i * rowH, cy = y0 + rowH / 2, bh = 14;
    if (i > 0 && isBaseline(row.policy) && !isBaseline(rows[i - 1].policy))
      svg.append(svgEl("line", { class: "sep", x1: 0, x2: W, y1: y0, y2: y0 }));
    const lab = svgEl("text", { class: "lab", x: m.l - 8, y: cy + 4, "text-anchor": "end" });
    lab.textContent = policyLabel(row.policy); svg.append(lab);
    const parts = rats.map(k => [k, row["share_" + k] ? row["share_" + k].m : 0]);
    const tot = parts.reduce((a, [, v]) => a + v, 0) || 1;
    let xx = m.l;
    for (const [k, v] of parts) {
      const w = v / tot * iw;
      if (w > 2) svg.append(svgEl("rect", { x: xx + 1, y: cy - bh / 2, width: w - 2, height: bh, rx: 2, fill: `var(${RAT_COLOR[k]})` }));
      xx += w;
    }
    const hit = svgEl("rect", { class: "hit", x: 0, y: y0, width: W, height: rowH });
    hit.addEventListener("pointerenter", () => {
      tip.replaceChildren(el("div", { class: "ts", text: policyLabel(row.policy) }),
        ...parts.map(([k, v]) => el("div", { class: "row" }, el("span", { class: "key box", style: `background:var(${RAT_COLOR[k]})` }),
                                    el("b", { text: (v * 100).toFixed(1) + "%" }), el("span", { class: "muted", text: k }))));
      tip.hidden = false;
      const r = svg.getBoundingClientRect();
      tip.style.top = (svg.offsetTop + (cy + rowH / 2) / H * r.height + 4) + "px";
      tip.style.left = Math.min(r.width - tip.offsetWidth, m.l / W * r.width) + "px";
    });
    hit.addEventListener("pointerleave", () => { tip.hidden = true; });
    svg.append(hit);
  });
  card.append(svg, tip);
  return card;
}

function comparisonTable(rows) {
  const t = el("table", { id: "cmp-table" });
  const cols = CMP_METRICS.concat([["share_DSRC", "On DSRC", "pct"], ["share_WiFi", "On WiFi", "pct"], ["share_NR", "On 5G", "pct"]]);
  t.append(el("thead", {}, el("tr", {}, el("th", { text: "Policy" }), el("th", { class: "n", text: "Seeds" }),
                                     ...cols.map(([, h]) => el("th", { class: "n", text: h })))));
  // best mean per column, among the policies (not the baselines)
  const best = {};
  for (const [k, , , better] of cols) {
    if (!better) continue;
    const v = rows.filter(r => !isBaseline(r.policy) && r[k]).map(r => r[k].m);
    if (v.length > 1) best[k] = better === "high" ? Math.max(...v) : Math.min(...v);
  }
  const b = el("tbody");
  for (const r of rows) {
    const tr = el("tr", { class: isBaseline(r.policy) ? "base" : "", tabindex: "0", title: "Open this policy's first run below" },
      el("td", { text: policyLabel(r.policy) + (isBaseline(r.policy) ? " (baseline)" : "") }),
      el("td", { class: "n", text: r.seeds.join(", ") }),
      ...cols.map(([k, , kind]) => {
        const s = r[k];
        const td = el("td", { class: "n", text: s ? cmpFmt(s.m, kind) + (s.n > 1 ? ` ±${kind === "pct" ? (s.sd * 100).toFixed(1) : fmt(s.sd, kind === "num" ? 2 : 1)}` : "") : "–" });
        if (s && best[k] != null && !isBaseline(r.policy) && s.m === best[k]) td.classList.add("best");
        return td;
      }));
    const go = () => { const run = r.runs[0]; pick.value = run.id; history.replaceState(null, "", "#" + run.id); renderRun(run);
                       document.getElementById("one-run").scrollIntoView({ behavior: "smooth" }); };
    tr.addEventListener("click", go);
    tr.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
    b.append(tr);
  }
  t.append(b);
  return el("div", { class: "scroll" }, t);
}

function renderCompare(groups, g) {
  const root = document.getElementById("compare");
  root.replaceChildren(el("h2", { text: "Compare policies" }));
  const f = el("div", { class: "filters" });
  const sel = el("select", { id: "cmp-pick" });
  for (const x of groups) sel.append(el("option", { value: x.key,
    text: `${x.scenario}, ${fmt(x.simTime, 0)} s, ${x.policies.length} policies, ${x.runs.length} runs` + (x.commit ? `, commit ${x.commit.slice(0, 7)}` : "") + (x.params.length ? " (changed parameters)" : "") }));
  sel.value = g.key;
  sel.addEventListener("change", () => renderCompare(groups, groups.find(x => x.key === sel.value)));
  f.append(el("label", { for: "cmp-pick", class: "muted", text: "Runs" }), sel);
  root.append(f);
  const seeds = [...new Set(g.policies.flatMap(p => p.seeds))].sort();
  root.append(el("p", { class: "sub", text: `Same scenario, length, image and parameters; each policy averaged over seeds ${seeds.join(", ")} ` +
    `(bars: mean, whisker: ± standard deviation across seeds). A difference smaller than the whiskers is not a difference.` +
    (g.params.length ? ` Parameters changed for these runs: ${g.params.join(", ")}.` : "") }));
  const grid = el("div", { class: "grid2" });
  for (const [k, title, kind, better] of CMP_METRICS)
    if (g.policies.some(p => p[k])) grid.append(hbarChart(title, better, g.policies, k, kind));
  root.append(grid);
  const sh = shareChart(g.policies); sh.style.marginTop = "12px"; root.append(sh);
  root.append(el("div", { class: "card", style: "margin-top:12px" },
    el("h3", { text: "All numbers (mean ± standard deviation across seeds; bold: best policy, baselines excluded; click a row to open its run)" }),
    comparisonTable(g.policies)));
}

document.getElementById("gen").textContent = when(DATA.generated);
const pick = document.getElementById("pick");
for (const r of RUNS) pick.append(el("option", { value: r.id, text: `${when(r.started)} — ${label(r)}` }));
pick.addEventListener("change", () => { history.replaceState(null, "", "#" + pick.value); renderRun(RUNS.find(r => r.id === pick.value)); });
renderHistory();
const CMP_GROUPS = comparisonGroups();
if (CMP_GROUPS.length) renderCompare(CMP_GROUPS, CMP_GROUPS[0]);
const linked = RUNS.find(r => "#" + r.id === decodeURIComponent(location.hash));
if (linked) { pick.value = linked.id; renderRun(linked); }
else if (RUNS.length) renderRun(RUNS[0]);
else document.getElementById("run").append(el("div", { class: "card empty", text: "No runs yet. Start one with dash/run-experiment.sh." }));
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
