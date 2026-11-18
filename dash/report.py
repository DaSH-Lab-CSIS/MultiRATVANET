#!/usr/bin/env python3
"""Build results/report.html: a dashboard of every run in a results folder.

    python3 dash/report.py RESULTS_DIR [--out FILE]

A run is a folder in RESULTS_DIR holding OMNeT++ output (.sca/.vec), either directly (tools/run.sh
without RESULTS_ROOT) or one level down (dash/run-experiment.sh, which also writes run.json and
console.log). Runs recorded with a decision log (<config>-#<n>.decisions.csv, one row per car
decision) also get measured coverage, car tracks and the decision table. Standard library only, so
it runs inside the image. Per-run results are cached in <run>/.report-cache.json and recomputed when
the result files change.
"""
import base64
import csv
import glob
import gzip
import html
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone

CACHE_VERSION = 12
LOG_TAIL = 200
BIN_STEPS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]
MAX_POINTS = 120
MAX_TABLE_ROWS = 6000     # decision table rows embedded per run
MAX_TRACK_POINTS = 40000  # car positions embedded per run (for the map's time slider)

RAT_SERIES = [("DSRC", "vehiclesDsrc"), ("WiFi", "vehiclesWifi"), ("NR", "vehiclesNr"),
              ("LTE", "vehiclesLte"), ("Unconnected", "vehiclesUnconnected")]
RAT_SHARES = [("DSRC", "DSRC"), ("WiFi", "WIFI"), ("NR", "NR"), ("LTE", "LTE")]
CSV_RAT = {"DSRC": "DSRC", "WIFI": "WiFi", "NR": "NR", "LTE": "LTE"}  # decision log name -> report name
RAT_ORDER = ["DSRC", "WiFi", "NR", "LTE"]

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
# radio, MAC and channel parameters shown in the Network section (first car / first RSU, AP, cell)
RE_NET_PAR = re.compile(r"^[^.]+\.(" + "|".join([
    r"(?:dsrcMedium|wifiMedium)\.(?:pathLoss|backgroundNoise|propagation)",
    r"carrierAggregation\.componentCarrier\[0\]",
    r"(?:dsrcRsu|wifiAp)\[0\]\.wlan\[0\]\.(?:radio\.transmitter|radio\.receiver|mac|mgmt)",
    r"[ge]NodeB\w*\.cellularNic\.(?:phy|mac)",
    r"car\[\d+\]\.(?:wlan\[\d\]\.(?:radio\.transmitter|radio\.receiver|mac|agent)"
    r"|cellularNic\.(?:phy|nrPhy|channelModel\[0\]|nrChannelModel\[0\]))",
    r"veinsManager",
]) + r")$")


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
    """attrs, first-match config (OMNeT++ lists entries in lookup order), scalars, histogram fields,
    per-car module parameters, ini descriptions, network parameters"""
    attrs, config, scalars, stats, pars, descr, npars = {}, {}, [], {}, {}, [], {}
    cur = None
    first_car = None
    header = True
    with open(path, errors="replace") as f:
        for line in f:
            if line.startswith("scalar "):
                header = False
                p = line.split(None, 3)
                if len(p) == 4:
                    scalars.append((p[1], unquote(p[2]), num(p[3])))
            elif line.startswith("statistic "):
                header = False
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
                if len(p) == 3 and header:
                    attrs[p[1]] = unquote(p[2])
            elif line.startswith("config "):
                p = line.split(None, 2)
                if len(p) == 3:
                    if p[1] == "description":
                        descr.append(unquote(p[2]))
                    config.setdefault(p[1], unquote(p[2]))
            elif line.startswith("par "):
                header = False
                p = line.split(None, 3)
                if len(p) == 4:
                    m = RE_CAR_PART.search(p[1])
                    if m:
                        pars.setdefault(m.group(2), {}).setdefault(m.group(1), {})[p[2]] = unquote(p[3])
                        continue
                    m = RE_NET_PAR.match(p[1])
                    if m:
                        mod = m.group(1)
                        cm = re.match(r"car\[(\d+)\]", mod)
                        if cm:
                            first_car = first_car or cm.group(1)
                            if cm.group(1) != first_car:
                                continue
                            mod = "car" + mod[cm.end():]
                        mod = re.sub(r"^([ge]NodeB)\w*", r"\1", mod)
                        npars.setdefault(mod, {}).setdefault(p[2], unquote(p[3]))
    return attrs, config, scalars, stats, pars, descr, npars


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
    rats = []
    for label, key, pre in (("DSRC", "DSRC", "dsrc"), ("WiFi", "WIFI", "wifi"), ("NR", "NR", "nr"), ("LTE", "LTE", "lte")):
        if mon.get("has" + pre.capitalize() if pre != "nr" else "hasNr") == "false":
            continue
        itype = mon.get(pre + "InfraType")
        rats.append({
            "rat": label,
            "towers": (None if itype == "" else infra_count.get(key)),
            "infra_type": itype,
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
        "decision": {k: mgr.get(k) for k in ("policy", "decisionInterval", "handoverExecDelay", "pingPongWindow",
                                              "startTime", "timeToTrigger", "sinrSwitchMargin", "loadSwitchMargin",
                                              "latencyBudget", "ensembleWeightCoverage", "ensembleWeightSinr",
                                              "ensembleWeightLatency", "ensembleWeightLoad", "ensembleStickiness") if k in mgr},
        "traffic": traffic,
        "signal_model": {k: mon.get(k) for k in ("signalSource", "measurementMaxAge", "requireProbeEcho", "probeMaxAge", "nrMinSinr", "lteMinSinr", "useDistance", "useSignal",
                                                  "txPowerDbm", "pathLossExponent", "referenceLossDb", "updateInterval") if k in mon},
        "cellular": pick("*.car[*].cellularNic.rrc.nrHandoverController.dynamicCellAssociation",
                         "*.car[*].cellularNic.rrc.nrHandoverController.enableHandover",
                         "*.gNodeB*.cellularNic.phy.handoverLatency"),
        "config": [[k, v] for k, v in config.items() if k not in ("description", "result-dir")],
    }


# ---------------------------------------------------------------- network (radio) parameters

def quantity(v):
    """'0.02W' -> (0.02, 'W'); '5.9e+09Hz' -> (5.9e9, 'Hz'); '-85dBm' -> (-85, 'dBm')"""
    m = re.fullmatch(r"\s*([-+0-9.eE]+)\s*([A-Za-z%]*)\s*", v or "")
    if not m:
        return None, None
    try:
        return float(m.group(1)), m.group(2)
    except ValueError:
        return None, None


def fmt_num(x, digits=1):
    s = f"{x:.{digits}f}".rstrip("0").rstrip(".")
    return s if s != "-0" else "0"


def fmt_freq(v):
    x, u = quantity(v)
    if x is None or u.lower() not in ("hz", "khz", "mhz", "ghz"):
        return None
    x *= {"hz": 1, "khz": 1e3, "mhz": 1e6, "ghz": 1e9}[u.lower()]
    return f"{fmt_num(x / 1e9, 3)} GHz" if x >= 1e9 else f"{fmt_num(x / 1e6, 2)} MHz"


def fmt_power(v):
    """'0.02W' / '100mw' / '26dBm' -> '20 mW (13 dBm)'"""
    x, u = quantity(v)
    if x is None:
        return v
    u = u.lower()
    if u == "dbm":
        mw = 10 ** (x / 10)
    elif u in ("w", "mw"):
        mw = x * (1000 if u == "w" else 1)
    else:
        return v
    dbm = 10 * math.log10(mw) if mw > 0 else None
    mws = f"{fmt_num(mw / 1000, 1)} W" if mw >= 1000 else f"{fmt_num(mw, 1)} mW"
    return f"{mws} ({fmt_num(dbm, 0)} dBm)" if dbm is not None else mws


def short_type(v):
    return (v or "").rsplit(".", 1)[-1]


def network_info(npars, config, setup, infra, summary, decisions):
    """One card per radio (DSRC, Wi-Fi, cellular): label/value rows in plain words"""
    P = lambda mod, key: npars.get(mod, {}).get(key)
    rats = {x["rat"]: x for x in setup["rats"]}
    count = Counter(p["rat"] for p in infra)
    stats = (decisions or {}).get("rat_stats", {})
    inputs = (summary or {}).get("inputs", {})
    probes = setup.get("signal_model", {}).get("requireProbeEcho") == "true"
    cards = []

    def seen(rat, rows):
        st, inp = stats.get(rat), inputs.get(rat)
        if st:
            rows.append(("Usable in this run", f"{st['usable'] * 100:.0f}% of decisions (all cars)"))
        if inp and inp.get("SinrMargin") is not None:
            bits = [f"{inp['SinrMargin']:.1f} dB above the minimum"]
            if inp.get("Load") is not None:
                bits.append(f"{inp['Load'] * 100:.0f}% busy")
            if inp.get("LinkRate") is not None:
                bits.append(f"link rate {inp['LinkRate']:.1f} Mbit/s")
            elif inp.get("Capacity") is not None:
                bits.append(f"{inp['Capacity']:.1f} Mbit/s free")
            if inp.get("ProbeRtt") is not None:
                bits.append(f"probe round trip {inp['ProbeRtt']:.1f} ms")
            elif inp.get("Latency") is not None:
                bits.append(f"{inp['Latency']:.1f} ms")
            rows.append(("Average while usable", " · ".join(bits)))

    for rat, title, infra_word in (("DSRC", "DSRC", "roadside units (RSUs)"), ("WiFi", "Wi-Fi", "access points")):
        if rat not in rats:
            continue
        iface = rats[rat].get("interface") or ("wlan0" if rat == "DSRC" else "wlan1")
        k = re.sub(r"\D", "", iface) or "0"
        car = f"car.wlan[{k}]"
        node = "dsrcRsu[0].wlan[0]" if rat == "DSRC" else "wifiAp[0].wlan[0]"
        medium = "dsrcMedium" if rat == "DSRC" else "wifiMedium"
        mode = P(car + ".mac", "modeSet") or P(car + ".radio.transmitter", "opMode") or ""
        std = "802.11" + mode.replace("(mixed)", " (mixed mode)") if mode else None
        cf, bw = fmt_freq(P(car + ".radio.transmitter", "centerFrequency")), fmt_freq(P(car + ".radio.transmitter", "bandwidth"))
        rows = [("Standard", std), ("Channel", " · ".join(x for x in (cf, bw and bw + " wide") if x))]
        rate = (stats.get(rat) or {}).get("rate")
        rows.append(("Data rate", "picked by INET from the mode set" + (f" (about {rate:.0f} Mbit/s here)" if rate else "")))
        rows.append(("Transmit power", f"car {fmt_power(P(car + '.radio.transmitter', 'power'))}"
                     + (f" · {'RSU' if rat == 'DSRC' else 'AP'} {fmt_power(P(node + '.radio.transmitter', 'power'))}" if P(node + ".radio.transmitter", "power") else "")))
        sens, snir = P(car + ".radio.receiver", "sensitivity"), P(car + ".radio.receiver", "snirThreshold")
        if sens or snir:
            rows.append(("Receiver", " · ".join(x for x in (f"hears signals above {sens}" if sens else None,
                                                             f"decodes at SNIR ≥ {snir}" if snir else None) if x)))
        pl, alpha = short_type(P(medium + ".pathLoss", "typename")), P(medium + ".pathLoss", "alpha")
        noise = P(medium + ".backgroundNoise", "power")
        if pl:
            pl_words = {"FreeSpacePathLoss": "free space (no buildings, no ground reflection)",
                        "TwoRayGroundReflection": "two-ray ground reflection",
                        "LogNormalShadowing": "log-normal shadowing"}.get(pl, pl)
            rows.append(("Propagation", pl_words + (f", path-loss exponent {alpha}" if alpha else "")
                         + (f", noise floor {noise}" if noise else "")))
        n = count.get(rat, rats[rat].get("towers") or 0)
        beacon = quantity(P(node + ".mgmt", "beaconInterval"))[0]
        ssid = P(car + ".agent", "defaultSsid")
        rows.append(("Infrastructure", f"{int(n)} {infra_word}" + (f", all on one channel, network “{ssid}”" if ssid else "")
                     + (f", beacon every {beacon * 1000:.0f} ms" if beacon else "")))
        if rats[rat].get("min_sinr") is not None:
            rows.append(("Counts as usable when", f"uplink SINR ≥ {rats[rat]['min_sinr']}, the car is associated"
                         + (", and its probes are echoed" if probes else "")))
        seen(rat, rows)
        note = None
        if rat == "DSRC" and mode and "p" not in mode.split("(")[0]:
            note = f"Real DSRC is 802.11p. This setup runs 802.11{mode.split('(')[0]} on DSRC's 5.9 GHz channel."
        cards.append({"rat": rat, "title": title, "rows": [r for r in rows if r[1]], "note": note})

    if "NR" in rats or "LTE" in rats:
        cc = "carrierAggregation.componentCarrier[0]"
        nb, mu = quantity(P(cc, "numBands"))[0], quantity(P(cc, "numerologyIndex"))[0] or 0
        has_nr = count.get("NR", 0) > 0
        has_lte = count.get("LTE", 0) > 0
        phy = "car.cellularNic.nrPhy" if has_nr or not has_lte else "car.cellularNic.phy"
        ch = "car.cellularNic.nrChannelModel[0]" if has_nr or not has_lte else "car.cellularNic.channelModel[0]"
        cells = []
        if count.get("NR"):
            cells.append(f"{count['NR']} × 5G (gNodeB)")
        if count.get("LTE"):
            cells.append(f"{count['LTE']} × LTE (eNodeB)")
        rows = [("Technology", "Simu5G: " + (" and ".join(t for t, h in (("5G NR", has_nr), ("LTE", has_lte)) if h) or "no cells")),
                ("Cells", ", ".join(cells) or "none"),
                ("Carrier", " · ".join(x for x in (fmt_freq(P(cc, "carrierFrequency")),
                                                   f"{int(nb)} resource blocks ({nb * 0.18 * 2 ** mu:.1f} MHz)" if nb else None,
                                                   "TDD" if P(cc, "useTdd") == "true" else "FDD" if P(cc, "useTdd") else None) if x)),
                ("Transmit power", " · ".join(x for x in (f"cell {fmt_power(P(phy, 'eNodeBTxPower'))}" if P(phy, "eNodeBTxPower") else None,
                                                          f"car {fmt_power(P(phy, 'ueTxPower'))}" if P(phy, "ueTxPower") else None) if x))]
        if P(ch, "pathLossType"):
            bits = [f"{P(ch, 'pathLossType')} {(P(ch, 'scenario') or '').replace('_', ' ').lower()}".strip()]
            bits.append("shadowing" if P(ch, "shadowing") == "true" else "no shadowing")
            if P(ch, "fading") == "true":
                bits.append(f"{(P(ch, 'fadingType') or '').title()} fading")
            rows.append(("Channel model", ", ".join(bits)))
        if P(ch, "nodebHeight"):
            rows.append(("Antennas", f"cell gain {P(ch, 'antennGainEnB')}, car gain {P(ch, 'antennaGainUe')}, tower height {P(ch, 'nodebHeight')}"))
        mac = "gNodeB.cellularNic.mac" if "gNodeB.cellularNic.mac" in npars else "eNodeB.cellularNic.mac"
        if P(mac, "schedulingDisciplineUl"):
            rows.append(("Scheduler", f"{P(mac, 'schedulingDisciplineUl')} uplink, {P(mac, 'schedulingDisciplineDl')} downlink"))
        cell = setup.get("cellular", {})
        dyn = cell.get("*.car[*].cellularNic.rrc.nrHandoverController.dynamicCellAssociation")
        ho = cell.get("*.car[*].cellularNic.rrc.nrHandoverController.enableHandover")
        if dyn or ho:
            rows.append(("Moving between cells", ("on" if "true" in (dyn, ho) else "off")
                         + (f", takes {cell['*.gNodeB*.cellularNic.phy.handoverLatency']}" if cell.get("*.gNodeB*.cellularNic.phy.handoverLatency") else "")))
        mins = [f"{'5G' if r == 'NR' else r} uplink SINR ≥ {rats[r]['min_sinr']}" for r in ("NR", "LTE") if r in rats and rats[r].get("min_sinr")]
        if mins:
            rows.append(("Counts as usable when", "; ".join(mins) + (", attached to a cell, and its probes are echoed" if probes else "")))
        for r in ("NR", "LTE"):
            if r in rats:
                sub = []
                seen(r, sub)
                rows += [(f"{'5G' if r == 'NR' else 'LTE'}: {k[0].lower() + k[1:]}", v) for k, v in sub]
        note = "There are no LTE towers in this scenario, so LTE is never usable." if "LTE" in rats and not has_lte else None
        cards.append({"rat": "NR" if has_nr or not has_lte else "LTE", "title": "Cellular", "rows": [r for r in rows if r[1]], "note": note})
    return cards


# ---------------------------------------------------------------- road map and projection

MAPS = {}  # network file -> road map, shared by all runs that use it


def repo_roots():
    here = os.path.dirname(os.path.abspath(__file__))
    return [os.environ.get("MRV_REPO", ""), os.path.dirname(here), "/workspace"]


def simplify(pts, tol):
    """Douglas-Peucker on a polyline [(x, y), ...]"""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = (dx * dx + dy * dy) ** 0.5 or 1e-9
    far, idx = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x2 * y1 - y2 * x1) / norm
        if d > far:
            far, idx = d, i
    if far <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:idx + 1], tol)[:-1] + simplify(pts[idx:], tol)


def utm_to_latlon(e, n, zone, south=False):
    """Inverse transverse Mercator (WGS84), accurate to well under a metre inside the zone"""
    k0, a, f = 0.9996, 6378137.0, 1 / 298.257223563
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x, y = e - 500000.0, n - (10000000.0 if south else 0.0)
    mu = y / k0 / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
          + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    s, c, t = math.sin(p1), math.cos(p1), math.tan(p1)
    n1 = a / math.sqrt(1 - e2 * s * s)
    t1, c1 = t * t, ep2 * c * c
    r1 = a * (1 - e2) / (1 - e2 * s * s) ** 1.5
    d = x / (n1 * k0)
    lat = p1 - (n1 * t / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
                                + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6 + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / c
    return math.degrees(lat), (zone - 1) * 6 - 180 + 3 + math.degrees(lon)


def projector(proj):
    """simulator (x, y) -> the map's coordinate pair: [lat, lon] for geo-referenced networks,
    else [-y, x] (Leaflet's plain CRS, y up)"""
    if not proj:
        return lambda x, y: [round(-y, 1), round(x, 1)]
    bx1, by2, margin = proj["bx1"], proj["by2"], proj["margin"]
    ox, oy, zone, south = proj["ox"], proj["oy"], proj["zone"], proj["south"]
    if zone is None:
        return lambda x, y: [round(-y, 1), round(x, 1)]

    def f(x, y):
        sx, sy = x + bx1 - margin, by2 + margin - y  # Veins: y flipped, plus a margin
        lat, lon = utm_to_latlon(sx - ox, sy - oy, zone, south)
        return [round(lat, 6), round(lon, 6)]
    return f


def scenario_files(config):
    """(repo root, launch file, network file, route files) for the run's SUMO scenario"""
    m = re.search(r'xmldoc\("([^"]+)"\)', config.get("*.veinsManager.launchConfig", "") or "")
    if not m:
        return None
    for root in repo_roots():
        launch = os.path.join(root, "simulations", m.group(1))
        if root and os.path.exists(launch):
            break
    else:
        return None
    text = open(launch).read()
    base = re.search(r'<basedir path="([^"]+)"', text)
    net = re.search(r'<copy file="([^"]+\.net\.xml)"', text)
    if not base or not net:
        return None
    d = os.path.join(root, base.group(1))
    routes = [os.path.join(d, r) for r in re.findall(r'<copy file="([^"]+\.rou\.xml)"', text)]
    return root, launch, os.path.join(d, net.group(1)), routes


def road_map(config):
    """Every drivable lane at its real width plus junction areas, in map coordinates (see
    projector). Returns the MAPS key, or None if the network file cannot be found."""
    files = scenario_files(config)
    if not files:
        return None
    path = files[2]
    if path in MAPS:
        return path
    if not os.path.exists(path):
        return None
    margin = float(re.sub(r"[^0-9.]", "", config.get("*.veinsManager.margin", "25")) or 25)
    lanes, junctions, proj, info = {}, [], None, {"edges": 0, "lanes": 0, "length_m": 0.0}
    sumo_lanes, sumo_junctions = [], []
    for ev, el in ET.iterparse(path, events=("end",)):
        if el.tag == "location":
            bx1, by1, bx2, by2 = (float(v) for v in el.get("convBoundary").split(","))
            ox, oy = (float(v) for v in el.get("netOffset").split(","))
            pp = el.get("projParameter") or "!"
            zm = re.search(r"\+zone=(\d+)", pp)
            proj = {"bx1": bx1, "by1": by1, "bx2": bx2, "by2": by2, "margin": margin, "ox": ox, "oy": oy,
                    "zone": int(zm.group(1)) if zm and "+proj=utm" in pp else None, "south": "+south" in pp}
        elif el.tag == "edge":
            if el.get("function") != "internal":
                drivable = 0
                for lane in el.findall("lane"):
                    allow, disallow = lane.get("allow"), lane.get("disallow") or ""
                    if not ((("passenger" in allow) if allow else ("passenger" not in disallow and disallow != "all"))):
                        continue
                    if lane.get("shape"):
                        drivable += 1
                        info["lanes"] += 1
                        info["length_m"] += float(lane.get("length") or 0)
                        w = float(lane.get("width") or 3.2)
                        sumo_lanes.append((w, [tuple(float(v) for v in p.split(",")[:2]) for p in lane.get("shape").split()]))
                info["edges"] += 1 if drivable else 0
            el.clear()
        elif el.tag == "junction":
            if el.get("type") != "internal" and el.get("shape"):
                sumo_junctions.append([tuple(float(v) for v in p.split(",")[:2]) for p in el.get("shape").split()])
            el.clear()
    if not proj:
        return None
    to_sim = lambda x, y: (x - proj["bx1"] + margin, (proj["by2"] - proj["by1"]) - (y - proj["by1"]) + margin)
    f = projector(proj)
    for w, pts in sumo_lanes:
        flat = []
        for x, y in simplify(pts, 0.2):
            flat += f(*to_sim(x, y))
        lanes.setdefault(f"{w:g}", []).append(flat)
    for pts in sumo_junctions:
        flat = []
        for x, y in simplify(pts + pts[:1], 0.2)[:-1]:
            flat += f(*to_sim(x, y))
        if len(flat) >= 6:
            junctions.append(flat)
    w_m, h_m = proj["bx2"] - proj["bx1"], proj["by2"] - proj["by1"]
    MAPS[path] = {"name": os.path.basename(path), "geo": proj["zone"] is not None, "proj": proj,
                  "lanes": lanes, "junctions": junctions, "width_m": w_m, "height_m": h_m,
                  "edges": info["edges"], "lane_count": info["lanes"], "lane_km": info["length_m"] / 1000}
    return path


def traffic_demand(config):
    """Vehicle types and flows from the SUMO route files, in plain words"""
    files = scenario_files(config)
    if not files:
        return None
    flows, vehicles, speeds = [], 0, []
    for path in files[3]:
        if not os.path.exists(path):
            continue
        for ev, el in ET.iterparse(path, events=("end",)):
            if el.tag == "vType" and el.get("maxSpeed"):
                speeds.append(float(el.get("maxSpeed")))
            elif el.tag == "flow":
                flows.append({k: el.get(k) for k in ("id", "route", "begin", "end", "period", "number", "vehsPerHour", "probability")})
            elif el.tag in ("vehicle", "trip"):
                vehicles += 1
                el.clear()
    out = []
    for fl in flows:
        how = (f"one car every {fl['period']} s" if fl.get("period") else f"{fl['vehsPerHour']} cars/h" if fl.get("vehsPerHour")
               else f"{fl['number']} cars" if fl.get("number") else "random")
        out.append(f"{fl.get('route') or fl.get('id')}: {how}, from {fmt_num(float(fl.get('begin') or 0))} to {fmt_num(float(fl.get('end') or 0))} s")
    return {"flows": out, "vehicles_listed": vehicles, "max_speed": max(speeds) if speeds else None,
            "files": [os.path.basename(p) for p in files[3]]}


INFRA_KINDS = (("dsrcRsu", "DSRC", "RSU"), ("wifiAp", "WiFi", "AP"), ("gNodeB", "NR", "5G"), ("eNodeB", "LTE", "LTE"))


def infra_points(config, scalars):
    """Every RSU / AP / cell tower with a known position (recorded at run end, else the ini),
    with a short label ("RSU 1") used everywhere in the report"""
    pts = {}
    for key, v in config.items():
        m = re.match(r"^\*+\.(\w+?)(?:\[(\d+)\])?\.mobility\.initial([XY])$", key)
        if m:
            name = f"{m.group(1)}[{m.group(2)}]" if m.group(2) else m.group(1)
            try:
                pts.setdefault(name, {})[m.group(3).lower()] = float(re.sub(r"[^0-9.eE\-]", "", v))
            except ValueError:
                pass
    for mod, name, v in scalars:
        m = re.match(r"infra\.(.+)\.([xy])$", name)
        if m and RE_STATS.search(mod) and v is not None:
            pts.setdefault(m.group(1), {})[m.group(2)] = v
    out, count = [], Counter()
    order = lambda n: (n[0].rstrip("[]0123456789"), int((re.findall(r"\d+", n[0]) or [0])[-1]))
    for name, p in sorted(pts.items(), key=order):
        kind = next((k for k in INFRA_KINDS if name.startswith(k[0])), None)
        if kind and "x" in p and "y" in p:
            count[kind[1]] += 1
            out.append({"name": name, "rat": kind[1], "label": f"{kind[2]} {count[kind[1]]}", "x": round(p["x"], 1), "y": round(p["y"], 1)})
    return out


def lte_equipped(config):
    """False when the run switched LTE off (hasLte = false): cellular is then 5G alone"""
    return next((v for key, v in config.items() if key.endswith("ratCoverageMonitor.hasLte")), "true") != "false"


def cellular_merged(config):
    """LTE equipped and lteInterface == nrInterface: the manager cannot tell LTE from NR; report them as one 'Cellular'"""
    get = lambda k: next((v for key, v in config.items() if key.endswith("multiRatAppManager." + k)), None)
    lte, nr = get("lteInterface"), get("nrInterface")
    return lte_equipped(config) and lte is not None and lte == nr


# ---------------------------------------------------------------- decision log

def read_decisions(path, proj, infra, span_m):
    """The per-decision CSV -> branch counts, measured coverage cells, car tracks, decision table"""
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        return None
    head = rows[0]
    col = {h: i for i, h in enumerate(head)}
    rats = [CSV_RAT.get(h[:-3], h[:-3]) for h in head if h.endswith("_ok")]
    measured_rate = any(h.endswith("_rate") for h in head)
    rat_cols = {CSV_RAT.get(h[:-3], h[:-3]): col[h] for h in head if h.endswith("_ok")}
    order = [r for r in RAT_ORDER if r in rats] + [r for r in rats if r not in RAT_ORDER]
    f = projector(proj)
    label = {p["name"]: p["label"] for p in infra}
    fl = lambda s: float(s) if s not in ("", "nan", "-nan") else None

    cell = 10.0 if span_m <= 3000 else 25.0 if span_m <= 10000 else 50.0
    branches = Counter()
    cov = {r: {} for r in order}
    rstat = {r: {"ok": 0, "n": 0, "rate": 0.0} for r in order}
    tracks, table = {}, []
    data = rows[1:]
    data.sort(key=lambda r: (int(r[col["car"]]), float(r[col["t"]])))
    for r in data:
        t, car = float(r[col["t"]]), int(r[col["car"]])
        x, y = fl(r[col["x"]]), fl(r[col["y"]])
        br = r[col["branch"]]
        branches[br] += 1
        cells = []
        for rat in order:
            i = rat_cols[rat]
            ok = r[i] == "1"
            sinr, load, cap, lat, via = fl(r[i + 1]), fl(r[i + 2]), fl(r[i + 3]), fl(r[i + 4]), r[i + 5]
            st = rstat[rat]
            st["n"] += 1
            st["ok"] += ok
            if measured_rate:
                if ok and cap is not None:
                    st["rate"] = max(st["rate"], cap)
            elif ok and cap is not None and load is not None and load < 0.9:
                st["rate"] = max(st["rate"], cap / max(1e-6, 1 - load))
            cells.append([1 if ok else 0, sinr, load, cap, lat, label.get(via, via) if via else ""])
            if x is not None:
                key = (int(x // cell), int(y // cell))
                c = cov[rat].setdefault(key, [0, 0, 0.0, Counter()])
                c[0] += 1
                if ok:
                    c[1] += 1
                    c[3][via] += 1
                if sinr is not None:
                    c[2] += sinr
        cur = CSV_RAT.get(r[col["current"]], r[col["current"]])
        choice = CSV_RAT.get(r[col["choice"]], r[col["choice"]])
        table.append([round(t, 2), car, cur, choice, br, r[col["detail"]], cells])
        if x is not None:
            tracks.setdefault(car, []).append((t, x, y, cur))

    # coverage: share of samples in each cell where the RAT was usable, and who served it
    coverage = {}
    for rat in order:
        out = []
        for (ix, iy), (n, ok, ssum, via) in cov[rat].items():
            a0, b0 = f(ix * cell, iy * cell)
            a1, b1 = f((ix + 1) * cell, (iy + 1) * cell)
            top = via.most_common(1)[0][0] if via else ""
            out.append([min(a0, a1), min(b0, b1), max(a0, a1), max(b0, b1), round(ok / n, 3), n, round(ssum / n, 1),
                        label.get(top, top)])
        coverage[rat] = out

    # tracks: positions over time per car, thinned to fit
    total = sum(len(v) for v in tracks.values())
    step = max(1, math.ceil(total / MAX_TRACK_POINTS))
    rat_idx = {"": 0, "DSRC": 1, "WiFi": 2, "NR": 3, "LTE": 4}
    track_out = {}
    for car, pts in tracks.items():
        flat = []
        for k, (t, x, y, cur) in enumerate(pts):
            if k % step and k != len(pts) - 1:
                continue
            flat += [round(t, 2)] + f(x, y) + [rat_idx.get(cur, 0)]
        track_out[str(car)] = flat

    # decision table: every turn where something happened, plus as many quiet turns as fit
    sampled = False
    if len(table) > MAX_TABLE_ROWS:
        busy = [r for r in table if r[4] != "best"]
        quiet = [r for r in table if r[4] == "best"]
        room = max(0, MAX_TABLE_ROWS - len(busy))
        k = max(1, math.ceil(len(quiet) / room)) if room else 0
        table = busy + (quiet[::k] if k else [])
        table.sort(key=lambda r: (r[1], r[0]))
        table = table[:MAX_TABLE_ROWS]
        sampled = True
    for row in table:
        for c in row[6]:
            c[1:5] = [None if v is None else round(v, 3 if i == 1 else 2) for i, v in enumerate(c[1:5])]
    return {
        "rats": order,
        "inputs": "rate" if measured_rate else "capacity",
        "count": len(data),
        "cars": sorted(tracks),
        "branches": dict(branches),
        "rat_stats": {r: {"usable": s["ok"] / s["n"] if s["n"] else 0, "rate": s["rate"] or None} for r, s in rstat.items()},
        "coverage_cell_m": cell,
        "coverage": coverage,
        "tracks": track_out,
        "table": table,
        "table_sampled": sampled,
    }


# ---------------------------------------------------------------- time series

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


# ---------------------------------------------------------------- runs

def tail(path, n):
    try:
        with open(path, errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None
    return "".join(lines[-n:])


def rerun_command(meta, config_name, sim_time):
    """The command that repeats this run. Newer run.json files carry it; older ones are rebuilt."""
    if meta.get("command"):
        return meta["command"]
    if not meta.get("scenario"):
        return f"./tools/run.sh {config_name} --sim-time-limit={fmt_num(sim_time or 0, 3)}s" if config_name else None
    q = lambda s: s if re.fullmatch(r"[A-Za-z0-9_./=:,+@%-]+", s) else "'" + s.replace("'", "'\\''") + "'"
    out = ["dash/run-experiment.sh", "--scenario", meta["scenario"], "--policy", meta.get("policy", ""),
           "--time", meta.get("sim_time", ""), "--seed", meta.get("seed") or "0"]
    if meta.get("name"):
        out += ["--name", meta["name"]]
    for p in meta.get("params", []):
        k, _, v = p.partition("=")
        if re.fullmatch(r"[a-z_]+", k):
            out += ["--" + k.replace("_", "-"), v]
        else:
            out += ["--set", p]
    return " ".join(q(x) for x in out)


def load_run(run_dir):
    meta = {}
    try:
        with open(os.path.join(run_dir, "run.json")) as f:
            meta = json.load(f)
    except (OSError, ValueError):
        pass
    scas = sorted(glob.glob(os.path.join(run_dir, "*.sca")) + glob.glob(os.path.join(run_dir, "*", "*.sca")))
    vecs = [s[:-4] + ".vec" for s in scas if os.path.exists(s[:-4] + ".vec")]
    logs = [s[:-4] + ".decisions.csv" for s in scas if os.path.exists(s[:-4] + ".decisions.csv")]
    key = [CACHE_VERSION] + [[p, os.path.getsize(p), int(os.path.getmtime(p))] for p in scas + vecs + logs]
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
        attrs, config, scalars, stats, pars, descr, npars = read_sca(scas[0])
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
        setup = scenario_setup(config, pars, scalars, descr)
        summary = summarize(config, scalars, stats, sim_time)
        map_key = road_map(config)
        m = MAPS.get(map_key)
        infra = infra_points(config, scalars)
        decisions = None
        if logs:
            span = max(m["width_m"], m["height_m"]) if m else 2000
            decisions = read_decisions(logs[0], m["proj"] if m else None, infra, span)
        sumo_seed = (npars.get("veinsManager") or {}).get("seed")
        run.update({
            "config": attrs.get("configname"),
            "network": (attrs.get("network") or "").rsplit(".", 1)[-1],
            "started": meta.get("started") or started,  # run.json is UTC; the .sca stamp is the simulator's local time
            "sim_time": sim_time,
            "cellular_merged": merged,
            "summary": summary,
            "setup": setup,
            "seed": {"seedset": attrs.get("seedset", meta.get("seed")), "runnumber": attrs.get("runnumber"),
                     "sumo": attrs.get("runnumber") if sumo_seed in (None, "-1") else sumo_seed,
                     "sumo_from_run": sumo_seed in (None, "-1"), "rng": config.get("rng-class"), "num_rngs": config.get("num-rngs")},
            "map": map_key,
            "infra": [{**p, "pos": projector(m["proj"] if m else None)(p["x"], p["y"])} for p in infra],
            "demand": traffic_demand(config),
            "network_info": network_info(npars, config, setup, infra, summary, decisions),
            "decisions": decisions,
            "command": rerun_command(meta, attrs.get("configname"), sim_time),
            "result_dir": os.path.abspath(run_dir),
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
    bench = None
    try:
        with open(os.path.join(root, "bench.json")) as f:
            bench = json.load(f)
    except (OSError, ValueError):
        pass
    if bench is not None:
        # a test bench (bench/run.sh): the page compares the policies and shows no single run, so
        # only what the comparison reads is kept
        keep = ("id", "meta", "status", "summary", "sim_time", "started", "config", "cellular_merged")
        for r in runs:
            d = r.get("decisions")
            light = {k: d[k] for k in ("count", "branches", "rat_stats") if k in d} if d else None
            dec = (r.get("setup") or {}).get("decision")
            for k in list(r):
                if k not in keep:
                    del r[k]
            r["decisions"], r["decision"] = light, dec
        data = json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "runs": runs,
                           "maps": {}, "bench": bench}, separators=(",", ":")).replace("</", "<\\/")
        page = TEMPLATE.replace("/*DATA*/", data).replace("<!--HEAVY-->", "").replace("{{ROOT}}", html.escape(os.path.abspath(root)))
        with open(out, "w") as f:
            f.write(page)
        print(f"report: test bench, {len(runs)} run(s) -> {out} ({os.path.getsize(out) / 1e6:.1f} MB)")
        return 0
    for r in runs:  # maps live once in MAPS; a cached run may need its map loaded again
        if r.get("map") and r["map"] not in MAPS:
            r["map"] = road_map({"*.veinsManager.launchConfig": r["setup"]["launch"]}) if r.get("setup") else None
    # heavy per-run parts (decision table, tracks, coverage) go in their own blocks, parsed on demand
    heavy = {}
    for r in runs:
        if r.get("decisions"):
            heavy[r["id"]] = r["decisions"]
            r["decisions"] = {k: v for k, v in r["decisions"].items() if k not in ("table", "tracks", "coverage")}
    maps = {k: {kk: vv for kk, vv in v.items() if kk != "proj"} for k, v in MAPS.items() if any(r.get("map") == k for r in runs)}
    enc = lambda obj: json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")
    data = enc({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "runs": runs, "maps": maps})
    # gzip + base64: the decision tables compress about 8x; the page unpacks a run's block when it is opened
    pack = lambda obj: base64.b64encode(gzip.compress(json.dumps(obj, separators=(",", ":")).encode(), 9, mtime=0)).decode()
    blocks = "".join(f'<script type="text/plain" class="heavy" data-run="{html.escape(k)}">{pack(v)}</script>\n'
                     for k, v in heavy.items())
    page = TEMPLATE.replace("/*DATA*/", data).replace("<!--HEAVY-->", blocks).replace("{{ROOT}}", html.escape(os.path.abspath(root)))
    with open(out, "w") as f:
        f.write(page)
    print(f"report: {len(runs)} run(s) -> {out} ({os.path.getsize(out) / 1e6:.1f} MB)")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MultiRATVANET runs</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<style>
:root {
  color-scheme: light;
  --surface-0: #f5f4f1; --surface-1: #fcfcfb; --surface-2: #f0efeb; --border: #e3e1dc; --grid: #ecebe7;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #7b7a75;
  --good: #1a7f37; --bad: #c62828; --accent: #2a78d6;
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100; --s5: #8f8e86;
  --ground: #e6e8e1; --road: #5d6064;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-0: #111110; --surface-1: #1a1a19; --surface-2: #222220; --border: #2e2e2b; --grid: #262624;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8f8e86;
    --good: #4cc26a; --bad: #ff6b6b; --accent: #3987e5;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #8f8e86;
    --ground: #1d201c; --road: #6b6f74;
  }
  :root:not([data-theme="light"]) .leaflet-tile-pane { filter: invert(1) hue-rotate(180deg) brightness(.85) contrast(.9); }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-0: #111110; --surface-1: #1a1a19; --surface-2: #222220; --border: #2e2e2b; --grid: #262624;
  --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8f8e86;
  --good: #4cc26a; --bad: #ff6b6b; --accent: #3987e5;
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #8f8e86;
  --ground: #1d201c; --road: #6b6f74;
}
:root[data-theme="dark"] .leaflet-tile-pane { filter: invert(1) hue-rotate(180deg) brightness(.85) contrast(.9); }
* { box-sizing: border-box; }
html { scroll-padding-top: 110px; }
body { margin: 0; background: var(--surface-0); color: var(--text-primary);
       font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 1180px; margin: 0 auto; padding: 0 16px; }
header.top { position: sticky; top: 0; z-index: 1000; background: color-mix(in srgb, var(--surface-0) 92%, transparent);
             backdrop-filter: blur(6px); border-bottom: 1px solid var(--border); }
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; padding-top: 12px; padding-bottom: 8px; }
.bar h1 { font-size: 17px; margin: 0; white-space: nowrap; }
.picker { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.picker select { flex: 1; min-width: 0; max-width: 560px; }
nav { display: flex; gap: 4px 18px; flex-wrap: wrap; padding-bottom: 8px; font-size: 13px; }
nav a { color: var(--text-secondary); text-decoration: none; }
nav a:hover { color: var(--text-primary); }
main { padding-top: 8px; padding-bottom: 64px; }
h2 { font-size: 16px; margin: 36px 0 2px; }
h3 { font-size: 13px; margin: 0 0 8px; font-weight: 600; }
.sub { color: var(--text-secondary); margin: 0 0 12px; max-width: 80ch; }
.intro { color: var(--text-secondary); margin: 14px 0 0; max-width: 90ch; }
.muted { color: var(--text-muted); }
select, button, input[type=range] { font: inherit; }
select { padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface-1); color: var(--text-primary); }
button { padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface-1); color: var(--text-primary); cursor: pointer; }
button:hover { border-color: var(--text-muted); }
button.on { background: var(--text-primary); color: var(--surface-1); border-color: var(--text-primary); }
.pill { font-size: 12px; padding: 2px 8px; border-radius: 99px; border: 1px solid currentColor; white-space: nowrap; }
.st-ok { color: var(--good); } .st-failed { color: var(--bad); } .st-none { color: var(--text-muted); }
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; min-width: 0; }
.grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 330px), 1fr)); gap: 12px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 480px), 1fr)); gap: 12px; }
.stack > * + * { margin-top: 12px; }
dl.kv { display: grid; grid-template-columns: max-content 1fr; gap: 5px 14px; margin: 0; font-size: 13px; }
dl.kv dt { color: var(--text-secondary); } dl.kv dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
dl.kv dd ul { margin: 0; padding-left: 16px; }
.mono { font-family: var(--mono); font-size: 12px; }
.note { font-size: 12px; color: var(--text-secondary); margin: 10px 0 0; }
details > summary { cursor: pointer; color: var(--text-secondary); font-size: 12px; margin-top: 10px; }
pre.log { font: 12px/1.4 var(--mono); background: var(--surface-0); border: 1px solid var(--border); border-radius: 8px;
          padding: 10px 12px; overflow: auto; max-height: 420px; margin: 8px 0 0; white-space: pre; }
.cmd { display: flex; align-items: stretch; gap: 8px; margin-bottom: 12px; }
.cmd pre { flex: 1; min-width: 0; margin: 0; font: 13px/1.5 var(--mono); padding: 10px 12px; background: var(--surface-1);
           border: 1px solid var(--border); border-radius: 8px; overflow-x: auto; white-space: pre; }
.cmd button { white-space: nowrap; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; vertical-align: top; }
th { color: var(--text-secondary); font-weight: 600; font-size: 12px; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; vertical-align: 0; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 0 0 6px; font-size: 12px; color: var(--text-secondary); align-items: center; }
.key { display: inline-block; width: 14px; height: 2px; border-radius: 1px; vertical-align: middle; margin-right: 6px; }
.key.box { width: 10px; height: 10px; border-radius: 2px; }
/* map */
#map { height: 420px; border-radius: 8px; border: 1px solid var(--border); background: var(--ground); }
.mapbar { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; margin-bottom: 10px; font-size: 13px; }
.seg { display: inline-flex; gap: 4px; flex-wrap: wrap; align-items: center; }
.seg button { padding: 3px 9px; font-size: 12px; }
.timebar { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 240px; }
.timebar input { flex: 1; min-width: 80px; }
.timebar output { font-variant-numeric: tabular-nums; min-width: 72px; color: var(--text-secondary); font-size: 12px; }
.leaflet-tooltip.lbl { background: transparent; border: 0; box-shadow: none; padding: 0; font: 600 11px system-ui, sans-serif;
                       color: var(--text-primary); text-shadow: 0 0 3px var(--surface-1), 0 0 3px var(--surface-1); }
.leaflet-tooltip.lbl::before { display: none; }
.leaflet-container { font: 12px system-ui, sans-serif; }
/* policy tree */
.tree { list-style: none; margin: 0; padding: 0; }
.tree li { display: grid; grid-template-columns: 24px 1fr; gap: 0 10px; }
.tree .num { width: 22px; height: 22px; border-radius: 50%; background: var(--surface-2); border: 1px solid var(--border);
             font-size: 11px; display: grid; place-items: center; color: var(--text-secondary); }
.tree .rail { grid-column: 1; justify-self: center; width: 1px; background: var(--border); min-height: 14px; }
.tree .q { font-weight: 500; padding-top: 1px; }
.tree .cont { grid-column: 2; font-size: 11px; color: var(--text-muted); padding: 2px 0 4px; }
.exit { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; margin: 4px 0 2px; padding: 5px 9px; border-radius: 7px;
        background: var(--surface-2); font-size: 13px; }
.exit .when { font-weight: 600; font-size: 12px; color: var(--text-secondary); }
.exit .cnt { margin-left: auto; font-variant-numeric: tabular-nums; color: var(--text-secondary); font-size: 12px; }
.exit.hot { background: color-mix(in srgb, var(--accent) 14%, var(--surface-2)); }
.toppick { margin: 0 0 12px; padding: 8px 10px; border-left: 3px solid var(--accent); background: var(--surface-2); border-radius: 0 6px 6px 0; font-size: 13px; }
/* decision table */
.tbar { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; margin-bottom: 8px; font-size: 13px; }
#turns td.rat { line-height: 1.25; }
#turns td.rat small, #turns td small { display: block; color: var(--text-muted); font-size: 11px; }
#turns td.off { color: var(--text-muted); }
#turns tbody tr.row { cursor: pointer; }
#turns tbody tr.row:hover { background: color-mix(in srgb, var(--accent) 6%, transparent); }
#turns tr.changed td.pick { font-weight: 600; }
#turns tr.more td { background: var(--surface-2); white-space: normal; }
.why-switch, .why-lost, .why-start { color: var(--accent); font-weight: 500; }
/* results */
.stats { display: flex; flex-wrap: wrap; gap: 14px 28px; }
.stat .v { font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
.stat .v small { font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-left: 2px; }
.stat .l { color: var(--text-secondary); font-size: 12px; }
.stat .d { color: var(--text-muted); font-size: 12px; }
.sharebar { display: flex; height: 14px; border-radius: 4px; overflow: hidden; margin: 6px 0 8px; background: var(--surface-2); }
.sharebar span { height: 100%; }
.chart { position: relative; }
.chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.chart .axis text { fill: var(--text-muted); font-size: 11px; }
.chart .gridline { stroke: var(--grid); stroke-width: 1; }
.chart .baseline { stroke: var(--border); stroke-width: 1; }
.chart .hair { stroke: var(--text-muted); stroke-width: 1; }
.tip { position: absolute; pointer-events: none; background: var(--surface-1); border: 1px solid var(--border);
       border-radius: 8px; padding: 6px 9px; font-size: 12px; box-shadow: 0 2px 10px rgba(0,0,0,.12); white-space: nowrap; z-index: 2; }
.tip .row { display: flex; align-items: center; gap: 6px; }
.tip b { font-variant-numeric: tabular-nums; }
.tip .ts { color: var(--text-muted); margin-bottom: 2px; }
.empty { color: var(--text-muted); padding: 30px 0; text-align: center; }
#history tbody tr { cursor: pointer; }
#history tbody tr:hover { background: color-mix(in srgb, var(--accent) 7%, transparent); }
#history tbody tr.sel { background: color-mix(in srgb, var(--accent) 14%, transparent); }
/* test bench page: the comparison only */
body.bench .picker, body.bench nav, body.bench #s-history, body.bench #run { display: none; }
/* compare */
.hbar .lab { fill: var(--text-secondary); font-size: 12px; }
.hbar .val { fill: var(--text-primary); font-size: 12px; font-variant-numeric: tabular-nums; }
.hbar .whisk { stroke: var(--text-primary); stroke-width: 1.5; }
.hbar .hit { fill: transparent; }
.hbar .hit:hover { fill: color-mix(in srgb, var(--text-muted) 10%, transparent); }
.hbar .sep { stroke: var(--border); stroke-dasharray: 3 3; }
.filters { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin: 0 0 10px; }
.filters select { max-width: 100%; }
td.best { font-weight: 600; }
#cmp-table tbody tr { cursor: pointer; }
#cmp-table tbody tr:hover { background: color-mix(in srgb, var(--accent) 7%, transparent); }
tr.base td:first-child { color: var(--text-secondary); }
@media (max-width: 640px) { #map { height: 340px; } .stat .v { font-size: 19px; } dl.kv { grid-template-columns: 1fr; gap: 0 0; } dl.kv dd { margin-bottom: 6px; } }
</style>
</head>
<body>
<header class="top">
  <div class="wrap bar">
    <h1>MultiRATVANET</h1>
    <div class="picker"><label for="pick" class="muted">Run</label><select id="pick"></select><span id="status" class="pill"></span></div>
  </div>
  <nav class="wrap"><a href="#s-compare" id="nav-compare" hidden>Compare</a><a href="#s-run">Run</a><a href="#s-map">Map</a><a href="#s-policy">Policy</a><a href="#s-network">Network</a><a href="#s-results">Results</a><a href="#s-history">History</a></nav>
</header>
<main class="wrap">
  <section id="s-compare" hidden></section>
  <div id="run"></div>
  <section id="s-history">
    <h2>History</h2>
    <p class="sub">Every run in <code>{{ROOT}}</code>, newest first. Click one to open it. Page built <span id="gen"></span>.</p>
    <div class="card scroll"><table id="history"></table></div>
  </section>
</main>

<script id="data" type="application/json">/*DATA*/</script>
<!--HEAVY-->
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("data").textContent);
const RUNS = DATA.runs;
const HEAVY = {};
const heavy = r => HEAVY[r.id] || null;
async function loadHeavy(r) {
  if (r.id in HEAVY) return;
  const s = [...document.querySelectorAll("script.heavy")].find(x => x.dataset.run === r.id);
  HEAVY[r.id] = null;
  if (!s || !window.DecompressionStream) return;
  try {
    const bytes = Uint8Array.from(atob(s.textContent.trim()), c => c.charCodeAt(0));
    const text = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
    HEAVY[r.id] = JSON.parse(text);
  } catch (e) { console.error("could not unpack run data", e); }
}
let SHOWING = null;
async function showRun(r) {
  SHOWING = r.id;
  await loadHeavy(r);
  if (SHOWING === r.id) renderRun(r);
}
// fixed colour per RAT (Cellular takes 5G's when LTE and 5G share one interface)
const RAT_COLOR = { DSRC: "--s1", WiFi: "--s2", NR: "--s3", Cellular: "--s3", LTE: "--s4", Unconnected: "--s5", "": "--s5" };
const RAT_LABEL = { DSRC: "DSRC", WiFi: "Wi-Fi", NR: "5G", LTE: "LTE", Cellular: "Cellular", Unconnected: "Not connected", "": "none" };
const RAT_BY_IDX = ["", "DSRC", "WiFi", "NR", "LTE"];
const INFRA_LABEL = { DSRC: "DSRC roadside unit", WiFi: "Wi-Fi access point", NR: "5G cell tower", LTE: "LTE cell tower" };
const ratText = s => (s || "").replace(/\bWIFI\b/g, "Wi-Fi").replace(/\bNR\b/g, "5G");
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v);
  }
  for (const k of kids) if (k != null && k !== false) e.append(k);
  return e;
};
const svgEl = (tag, attrs = {}) => {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
};
const fmt = (v, d = 1) => v == null || !isFinite(v) ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: 0 });
const pct = (v, d = 1) => v == null ? "–" : (v * 100).toFixed(d) + "%";
const when = s => s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "–";
const ratDot = rat => el("span", { class: "dot", style: `background:var(${RAT_COLOR[rat] || "--s5"})` });
const ratName = rat => el("span", {}, ratDot(rat), RAT_LABEL[rat] ?? rat);
const label = r => (r.meta && r.meta.scenario ? `${r.meta.scenario} · ${r.meta.policy}` : (r.config || r.id)) + (r.meta && r.meta.name ? ` · ${r.meta.name}` : "");
const className = n => ({ safety: "Safety messages", infotainment: "Infotainment" })[n] || n.charAt(0).toUpperCase() + n.slice(1);

function section(id, title, sub) {
  const s = el("section", { id });
  s.append(el("h2", { text: title }));
  if (sub) s.append(el("p", { class: "sub", text: sub }));
  return s;
}
function kvList(pairs) {
  const dl = el("dl", { class: "kv" });
  for (const [k, v] of pairs) {
    if (v == null || v === "" || (Array.isArray(v) && !v.length)) continue;
    const dd = el("dd");
    if (Array.isArray(v)) dd.append(el("ul", {}, ...v.map(x => el("li", { text: x }))));
    else if (v instanceof Node) dd.append(v); else dd.textContent = String(v);
    dl.append(el("dt", { text: k }), dd);
  }
  return dl;
}
function simpleTable(head, rows, numeric = []) {
  const t = el("table");
  t.append(el("thead", {}, el("tr", {}, ...head.map((h, i) => el("th", { class: numeric.includes(i) ? "n" : null, text: h })))));
  const b = el("tbody");
  for (const row of rows) b.append(el("tr", {}, ...row.map((c, i) => el("td", { class: numeric.includes(i) ? "n" : null, text: c == null || c === "" ? "–" : String(c) }))));
  t.append(b);
  return el("div", { class: "scroll" }, t);
}
function copyText(text, btn) {
  const done = () => { btn.textContent = "Copied"; setTimeout(() => (btn.textContent = "Copy"), 1500); };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, () => fallback());
  else fallback();
  function fallback() {
    const ta = el("textarea", { style: "position:fixed;opacity:0" }); ta.value = text; document.body.append(ta);
    ta.select(); try { document.execCommand("copy"); done(); } catch (e) { btn.textContent = "Select and copy"; } ta.remove();
  }
}

// ------------------------------------------------------------------ run, scenario, seed
function renderRunMeta(r) {
  const m = r.meta || {}, u = r.setup || {}, s = r.summary || {};
  const sec = section("s-run", "Run");
  if (r.command) {
    const btn = el("button", { type: "button", text: "Copy" });
    btn.addEventListener("click", () => copyText(r.command, btn));
    sec.append(el("div", { class: "cmd" }, el("pre", { text: r.command, "aria-label": "Command that repeats this run" }), btn));
  }
  const g = el("div", { class: "grid3" });

  const took = m.started && m.finished ? (new Date(m.finished) - new Date(m.started)) / 1000 : null;
  const runCard = el("div", { class: "card" }, el("h3", { text: "This run" }), kvList([
    ["Started", when(r.started)], ["Took", took != null ? `${fmt(took / 60, 1)} min (wall clock)` : null],
    ["Status", r.status === "ok" ? "completed" : r.status + (m.exit_code ? ` (exit ${m.exit_code})` : "")],
    ["Label", m.name], ["Ran by", m.who && m.host ? `${m.who} on ${m.host}` : m.who],
    ["Image", m.image], ["Code version", m.repo_commit], ["Changed settings", (m.params || []).length ? m.params : "none, all from omnetpp.ini"],
    ["Results folder", el("span", { class: "mono", text: r.result_dir || r.id })]]));
  if (r.log) runCard.append(el("details", r.status === "ok" ? {} : { open: "" }, el("summary", { text: "Console output" }), el("pre", { class: "log", text: r.log })));

  const M = r.map && DATA.maps[r.map], d = r.demand;
  const count = {};
  for (const p of r.infra || []) count[p.rat] = (count[p.rat] || 0) + 1;
  const infraText = ["DSRC", "WiFi", "NR", "LTE"].filter(k => (u.rats || []).some(x => x.rat === k))
    .map(k => `${count[k] || 0} ${{ DSRC: "RSU", WiFi: "Wi-Fi AP", NR: "5G cell", LTE: "LTE cell" }[k]}${(count[k] || 0) === 1 ? "" : "s"}`).join(" · ");
  const traffic = (u.traffic || []).map(t => `${className(t.name)}: ${t.packet} every ${t.interval}` +
    (t.mode === "onoff" ? ` in bursts (on ${t.on}, off ${t.off})` : "") + (t.kbps ? `, ${fmt(t.kbps, 0)} kbit/s while sending` : "") +
    (t.deadline ? `, must arrive within ${t.deadline}` : ""));
  const scen = el("div", { class: "card" }, el("h3", { text: "Scenario" }), kvList([
    ["Name", m.scenario ? `${m.scenario} (config ${r.config})` : r.config],
    ["What it is", u.descriptions && u.descriptions[0]],
    ["Roads", M ? `${M.geo ? "real map data (OpenStreetMap)" : "synthetic road"}, ${fmt(M.width_m / 1000, 1)} × ${fmt(M.height_m / 1000, 1)} km, ${M.lane_count} lanes, ${fmt(M.lane_km, 1)} km of lane` : u.launch],
    ["Cars", [`${fmt(s.vehicles, 0)} cars` + (d && d.max_speed ? `, up to ${fmt(d.max_speed, 0)} m/s (${fmt(d.max_speed * 3.6, 0)} km/h)` : ""),
              ...((d && d.flows) || [])]],
    ["Radio infrastructure", infraText],
    ["Each car sends", traffic.length ? traffic : null],
    ["Simulated time", r.sim_time != null ? `${fmt(r.sim_time, 0)} s` : null]]));
  if (u.config) {
    const overridden = new Set((m.overrides || []).map(o => o.replace(/^--/, "").split("=")[0]));
    const det = el("details", {}, el("summary", { text: `All ${u.config.length} settings from omnetpp.ini` }));
    det.append(el("p", { class: "note", text: "First match wins, as in OMNeT++. Settings changed for this run are marked." }),
               simpleTable(["Key", "Value", ""], u.config.map(([k, v]) => [k, v, overridden.has(k) ? "changed" : ""])));
    scen.append(det);
  }

  const sd = r.seed || {};
  const seed = el("div", { class: "card" }, el("h3", { text: "Seed" }), kvList([
    ["Seed set", sd.seedset ?? m.seed ?? "0"],
    ["Changes with the seed", ["when each car first decides and starts sending", "infotainment burst lengths",
                               "5G fading and shadowing", "Wi-Fi/DSRC backoff timers"]],
    ["Same in every seed", sd.sumo_from_run
      ? `how cars drive. SUMO's seed is ${sd.sumo}, taken from the run number, so --seed does not change traffic.`
      : `how cars drive (SUMO seed fixed at ${sd.sumo}).`],
    ["Random generator", sd.rng ? `${sd.rng.replace(/^c/, "")}${sd.num_rngs ? `, ${sd.num_rngs} streams` : ""}` : "OMNeT++ default (Mersenne Twister)"]]),
    el("p", { class: "note", text: "Same code, settings and seed set give the same results, bit for bit." }));
  g.append(runCard, scen, seed);
  sec.append(g);
  return sec;
}

// ------------------------------------------------------------------ map
let MAP = null, PLAY = null;
function renderMapSection(r) {
  const H = heavy(r), D = r.decisions;
  const sec = section("s-map", "Map", "Where the roads, roadside units, access points and cell towers are, where each radio actually worked, and which radio every car was on.");
  const card = el("div", { class: "card" });
  const bar = el("div", { class: "mapbar" });
  const covRats = D ? D.rats.filter(k => D.rat_stats[k] && D.rat_stats[k].usable > 0) : [];
  const seg = el("div", { class: "seg" }, el("span", { class: "muted", text: "Coverage:" }));
  const covBtns = {};
  for (const k of ["", ...covRats]) {
    const b = el("button", { type: "button", text: k ? RAT_LABEL[k] : "Off", class: k ? null : "on" });
    covBtns[k] = b; seg.append(b);
  }
  if (covRats.length) bar.append(seg);
  const tEnd = r.sim_time || 0;
  const slider = el("input", { type: "range", min: 0, max: tEnd, step: 0.5, value: Math.min(tEnd, 30), "aria-label": "Simulation time" });
  const out = el("output");
  const play = el("button", { type: "button", text: "Play" });
  if (H && H.tracks && Object.keys(H.tracks).length) bar.append(el("div", { class: "timebar" }, el("span", { class: "muted", text: "Cars at" }), slider, out, play));
  card.append(bar);
  const div = el("div", { id: "map" });
  card.append(div);
  const lg = el("div", { class: "legend", style: "margin-top:10px" });
  lg.append(el("span", {}, el("span", { class: "key", style: "background:var(--road);height:5px" }), "road (true lane width)"));
  for (const k of ["DSRC", "WiFi", "NR", "LTE"]) if ((r.infra || []).some(p => p.rat === k))
    lg.append(el("span", {}, el("span", { class: "dot", style: `background:var(${RAT_COLOR[k]});width:11px;height:11px;border:2px solid var(--surface-1);box-shadow:0 0 0 1px var(--border)` }), INFRA_LABEL[k]));
  if (H && H.tracks) lg.append(el("span", {}, el("span", { class: "dot", style: "background:var(--text-secondary);width:7px;height:7px" }), "car, coloured by the radio it is on"));
  card.append(lg);
  const M = r.map && DATA.maps[r.map];
  const notes = [];
  if (M) notes.push(M.geo ? `Roads from ${M.name}, drawn lane by lane over OpenStreetMap.` : `${M.name} is a synthetic road with no real-world location. Lanes are drawn at their true width; zoom in to see them.`);
  else notes.push("Road network file not found next to this report; only the infrastructure is shown.");
  if (D) notes.push(`Coverage is measured, not assumed: each ${fmt(D.coverage_cell_m, 0)} m square is shaded by how often cars there could use that radio. Hover a square for details.`);
  else notes.push("Coverage and cars come from the decision log, which this run predates. Rerun it to see them.");
  card.append(el("p", { class: "note", text: notes.join(" ") }));
  sec.append(card);
  return { sec, init: () => initMap(r, div, { covBtns, slider, out, play }) };
}

function initMap(r, div, ui) {
  if (MAP) { MAP.remove(); MAP = null; }
  if (PLAY) { clearInterval(PLAY); PLAY = null; }
  if (!window.L) { div.replaceChildren(el("div", { class: "empty", text: "The map library could not load (no internet connection?)." })); return; }
  const M = r.map && DATA.maps[r.map], H = heavy(r), geo = !!(M && M.geo);
  const map = L.map(div, { crs: geo ? L.CRS.EPSG3857 : L.CRS.Simple, preferCanvas: true, zoomSnap: 0.25, zoomDelta: 0.5,
                           minZoom: geo ? 9 : -6, maxZoom: geo ? 21 : 6, attributionControl: geo, scrollWheelZoom: true });
  MAP = map;
  if (geo) L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 21, maxNativeZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(map);
  L.control.scale({ imperial: false }).addTo(map);
  const bounds = L.latLngBounds([]);
  const road = css("--road");
  const lanes = [];
  if (M) {
    for (const [w, lines] of Object.entries(M.lanes)) for (const flat of lines) {
      const ll = []; for (let i = 0; i < flat.length; i += 2) ll.push([flat[i], flat[i + 1]]);
      ll.forEach(p => bounds.extend(p));
      lanes.push([+w, L.polyline(ll, { color: road, weight: 1, opacity: geo ? 0.75 : 1, lineCap: "butt", interactive: false }).addTo(map)]);
    }
    for (const flat of M.junctions) {
      const ll = []; for (let i = 0; i < flat.length; i += 2) ll.push([flat[i], flat[i + 1]]);
      L.polygon(ll, { stroke: false, fillColor: road, fillOpacity: geo ? 0.75 : 1, interactive: false }).addTo(map);
    }
  }
  for (const p of r.infra || []) bounds.extend(p.pos);
  const lat0 = geo && bounds.isValid() ? bounds.getCenter().lat : 0;
  const pxPerM = z => geo ? Math.pow(2, z) * 256 / (40075016.686 * Math.cos(lat0 * Math.PI / 180)) : Math.pow(2, z);
  const restyle = () => { const k = pxPerM(map.getZoom()); for (const [w, pl] of lanes) pl.setStyle({ weight: Math.max(1.2, w * k * 0.88) }); };
  map.on("zoomend", restyle);

  // measured coverage, one layer per RAT, built when first shown
  const layers = {};
  let shown = null;
  const coverage = k => {
    if (layers[k]) return layers[k];
    const g = L.layerGroup(), col = css(RAT_COLOR[k]);
    for (const [a0, b0, a1, b1, share, n, margin, via] of (H && H.coverage[k]) || []) {
      L.rectangle([[a0, b0], [a1, b1]], { stroke: false, fillColor: col, fillOpacity: 0.08 + 0.62 * share })
        .bindTooltip(`<b>${RAT_LABEL[k]}</b> usable ${Math.round(share * 100)}% of the time here<br>${n} samples` +
          (share > 0 ? `, signal ${margin > 0 ? "+" : ""}${margin} dB vs minimum` : "") + (via ? `<br>served by ${via}` : ""), { sticky: true })
        .addTo(g);
    }
    return (layers[k] = g);
  };
  for (const [k, b] of Object.entries(ui.covBtns)) b.addEventListener("click", () => {
    if (shown) map.removeLayer(layers[shown]);
    shown = k || null;
    if (shown) coverage(shown).addTo(map);
    for (const [kk, bb] of Object.entries(ui.covBtns)) bb.classList.toggle("on", kk === k);
    carLayer.eachLayer(l => l.bringToFront());
  });

  // infrastructure
  const crowded = (r.infra || []).length > 12;  // many markers: labels on hover only
  for (const p of r.infra || []) {
    L.circleMarker(p.pos, { radius: 8, color: css("--text-primary"), weight: 2, fillColor: css(RAT_COLOR[p.rat]), fillOpacity: 1 })
      .bindTooltip(p.label, { permanent: !crowded, direction: "top", offset: [0, -7], className: crowded ? null : "lbl" })
      .bindPopup(`${INFRA_LABEL[p.rat]}<br><span class="mono">${p.name}</span>`).addTo(map);
  }

  // cars at time t
  const carLayer = L.layerGroup().addTo(map);
  const cars = {};
  const tracks = (H && H.tracks) || {};
  const at = t => {
    ui.out.textContent = `t = ${fmt(t, 1)} s`;
    let n = 0;
    for (const [car, f] of Object.entries(tracks)) {
      let lo = 0, hi = f.length / 4 - 1, i = -1;
      while (lo <= hi) { const mid = (lo + hi) >> 1; if (f[mid * 4] <= t) { i = mid; lo = mid + 1; } else hi = mid - 1; }
      const live = i >= 0 && t - f[i * 4] <= 1.0;
      let mk = cars[car];
      if (!live) { if (mk) carLayer.removeLayer(mk); continue; }
      const rat = RAT_BY_IDX[f[i * 4 + 3]] || "";
      if (!mk) mk = cars[car] = L.circleMarker([0, 0], { radius: 4, weight: 1, color: css("--surface-1"), fillOpacity: 1 }).bindTooltip("");
      mk.setLatLng([f[i * 4 + 1], f[i * 4 + 2]]).setStyle({ fillColor: css(RAT_COLOR[rat]) });
      mk.setTooltipContent(`Car ${car} · on ${RAT_LABEL[rat]}`);
      if (!carLayer.hasLayer(mk)) carLayer.addLayer(mk);
      n++;
    }
  };
  ui.slider.addEventListener("input", () => at(+ui.slider.value));
  ui.play.addEventListener("click", () => {
    if (PLAY) { clearInterval(PLAY); PLAY = null; ui.play.textContent = "Play"; return; }
    if (+ui.slider.value >= +ui.slider.max) ui.slider.value = 0;
    ui.play.textContent = "Pause";
    const step = Math.max(0.5, Math.round((+ui.slider.max / 300) * 2) / 2);
    PLAY = setInterval(() => {
      const v = Math.min(+ui.slider.max, +ui.slider.value + step);
      ui.slider.value = v; at(v);
      if (v >= +ui.slider.max) { clearInterval(PLAY); PLAY = null; ui.play.textContent = "Play"; }
    }, 100);
  });
  if (Object.keys(tracks).length) at(+ui.slider.value);

  // fit: a wide road gets a shorter map
  if (bounds.isValid()) {
    if (!geo && M) div.style.height = Math.round(Math.max(240, Math.min(460, div.clientWidth * Math.max(M.height_m / M.width_m, 0.12) + 120))) + "px";
    map.invalidateSize();
    map.fitBounds(bounds.pad(0.04));
  } else map.setView([0, 0], 0);
  restyle();
}

// ------------------------------------------------------------------ policy
const POLICY = {
  CoveragePriority: { what: "Prefers the short-range radios. Picks the first usable RAT in a fixed order.",
                      top: "the first usable RAT in the order DSRC → Wi-Fi → 5G → LTE", better: null, key: "ok" },
  Sinr: { what: "Picks the RAT with the strongest signal. Signal is compared as dB above the lowest SINR each RAT can still use, since raw SINR means different things for Wi-Fi and 5G.",
          top: "the usable RAT whose signal is furthest above its minimum", better: d => `at least ${d.sinrSwitchMargin || "3dB"} more`, key: "sinr" },
  LatencyQos: { what: "Picks the RAT with the highest link rate among those whose latency (half the round trip of the car's own probes) fits the budget.",
                top: d => `the usable RAT with the highest link rate whose probe latency is within ${d.latencyBudget || "100ms"} (if none fit: the lowest latency)`,
                better: () => "at least 25% more link rate", key: "rate" },
  Load: { what: "Picks the least busy RAT, to spread cars across the networks. Only DSRC and Wi-Fi have a load figure (the car's radio senses how busy the channel is); 5G is the fallback when neither is usable.",
          top: "the usable RAT with the lowest sensed load", better: d => `at least ${Math.round(parseFloat(d.loadSwitchMargin || 0.15) * 100)} points less busy`, key: "load" },
  Ensemble: { what: "Lets the four policies above vote and goes with the most votes.", key: "all" },
  Ml: { what: "Hook for an outside machine-learning agent. Nothing drives it yet, so it behaves like CoveragePriority. It is left out of comparisons.", key: "all" },
  ExampleSplit: { what: "Example of a policy written against the policy interface: sends each traffic class over its own RAT.", key: "all" },
  OnlyDsrc: { what: "Baseline: uses DSRC and nothing else. Shows what one RAT achieves on its own.", rat: "DSRC", key: "ok" },
  OnlyWifi: { what: "Baseline: uses Wi-Fi and nothing else. Shows what one RAT achieves on its own.", rat: "Wi-Fi", key: "ok" },
  OnlyNr: { what: "Baseline: uses 5G and nothing else. Shows what one RAT achieves on its own.", rat: "5G", key: "ok" },
};
const WHY = {
  start: () => "First connection", none: () => "Nothing usable, kept as is", lost: () => "Its RAT stopped working, switched at once",
  best: () => "Already on the top pick", margin: d => `Stayed: ${ratText(d).replace(/^(\S+) /, "$1 only ").replace(/;/g, ",")}`,
  wait: d => `Waiting: ${ratText(d).replace(/ for /, " ahead for ").replace(/;/g, ",")}`, switch: () => "Switched: better for long enough",
  sticky: d => `Stayed: close enough in the vote (${ratText(d).replace(/^votes: /, "").replace(/;/g, ",")})`,
  "": d => d ? ratText(d) : "Policy's choice",
};
const pv = (v, d) => typeof v === "function" ? v(d) : v;

function policySteps(name, d) {
  const P = POLICY[name] || {}, ttt = d.timeToTrigger || "1s";
  if (name === "Ml" || name === "ExampleSplit") return null;
  if (P.rat) return [
    { q: `Is ${P.rat} usable?`, exit: ["No", "none", "Keep things as they are (stay unconnected, or on " + P.rat + " until it works again)"] },
    { q: "Is the car connected yet?", exit: ["No", "start", `Connect to ${P.rat}`], last: ["Yes", "best", "Stay"] },
  ];
  if (name === "Ensemble") {
    const w = [["coverage", d.ensembleWeightCoverage], ["signal", d.ensembleWeightSinr], ["latency", d.ensembleWeightLatency], ["load", d.ensembleWeightLoad]];
    return [
      { q: `Each of the four policies names the RAT it prefers right now, by its own rules. Votes count ${w.map(([k, v]) => `${k} ×${v ?? 1}`).join(", ")}.` },
      { q: "Did any of them name a usable RAT?", exit: ["No", "none", "Keep things as they are"] },
      { q: "Is the car connected yet?", exit: ["No", "start", "Connect to the RAT with the most votes"] },
      { q: "Is the RAT it is on still usable?", exit: ["No", "lost", "Switch to the RAT with the most votes, now"] },
      { q: "Does that RAT have the most votes? (ties go to DSRC, Wi-Fi, 5G, LTE in that order)", exit: ["Yes", "best", "Stay"] },
      { q: `Is it within ${d.ensembleStickiness ?? 1} vote of the leader?`, exit: ["Yes", "sticky", "Stay"] },
      { q: `Has the leader stayed ahead for ${ttt}?`, exit: ["No", "wait", "Stay, check again next time"], last: ["Yes", "switch", "Switch to the leader"] },
    ];
  }
  return [
    { q: "Is any RAT usable?", exit: ["No", "none", "Keep things as they are"] },
    { q: "Is the car connected yet?", exit: ["No", "start", "Connect to the top pick"] },
    { q: "Is the RAT it is on still usable?", exit: ["No", "lost", "Switch to the top pick, now"] },
    { q: "Is it already on the top pick?", exit: ["Yes", "best", "Stay"] },
    P.better ? { q: `Is the top pick better by enough? (needs ${pv(P.better, d)})`, exit: ["No", "margin", "Stay"] } : null,
    { q: `Has the top pick stayed ahead for ${ttt}?`, exit: ["No", "wait", "Stay, check again next time"], last: ["Yes", "switch", "Switch to it"] },
  ].filter(Boolean);
}

function renderPolicySection(r) {
  const u = r.setup || {}, d = u.decision || {}, name = d.policy || "?", P = POLICY[name] || {};
  const D = r.decisions, total = D ? D.count : 0;
  const sec = section("s-policy", `Policy: ${name}`, P.what);
  const g = el("div", { class: "grid2" });

  const treeCard = el("div", { class: "card" }, el("h3", { text: `What each car does every ${d.decisionInterval || "0.5s"}` }));
  if (P.top) treeCard.append(el("div", { class: "toppick" }, el("b", { text: "Top pick" }), ` = ${pv(P.top, d)}.`));
  const steps = policySteps(name, d);
  if (!steps) treeCard.append(el("p", { class: "muted", text: "No decision tree: the choice comes from outside the simulation." }));
  else {
    const ol = el("ol", { class: "tree" });
    const exitEl = ([w, key, text]) => {
      const n = D ? (D.branches[key] || 0) : null;
      return el("div", { class: "exit" + (n && n / total > 0.05 && key !== "best" ? " hot" : "") },
        el("span", { class: "when", text: w + " →" }), el("span", { text }),
        n != null ? el("span", { class: "cnt", text: `${fmt(n, 0)} (${n && n / total < 0.001 ? "<0.1%" : pct(n / total, 1)})` }) : null);
    };
    let i = 0;
    for (const st of steps) {
      i++;
      const body = el("div", {}, el("div", { class: "q", text: st.q }));
      if (st.exit) body.append(exitEl(st.exit));
      if (st.last) body.append(exitEl(st.last));
      ol.append(el("li", {}, el("span", { class: "num", text: i }), body));
      if (i < steps.length) ol.append(el("li", {}, el("span", { class: "rail" }), el("span", { class: "cont", text: st.exit ? (st.exit[0] === "No" ? "Yes ↓" : "No ↓") : "↓" })));
    }
    treeCard.append(ol);
    treeCard.append(el("p", { class: "note", text: D ? `Counts: how often each outcome happened in this run (${fmt(total, 0)} decisions, all cars).`
                                                     : "This run predates the decision log, so there are no counts. Rerun it to see them." }));
  }

  const sm = u.signal_model || {};
  const measured = (sm.signalSource || "proxy") === "measured";
  const set = el("div", { class: "card" }, el("h3", { text: "Settings" }), kvList([
    ["Decides every", d.decisionInterval],
    ["First decision", d.startTime ? `${d.startTime} after the car appears, plus a random offset so cars don't all decide at once` : null],
    ["Waits before switching", P.rat ? null : `${d.timeToTrigger || "1s"} (time-to-trigger: a better RAT must stay ahead this long)` + (name === "Ensemble" ? ", applied to the vote's outcome" : "")],
    ["Switch cost", d.handoverExecDelay && parseFloat(d.handoverExecDelay) > 0 ? `${d.handoverExecDelay} extra, plus what the radios cost` : "only what the simulated radios cost (no extra delay)"],
    ["Inputs come from", measured ? "measurements during the run" : "a distance-based guess (proxy mode, old behaviour)"]]));
  set.append(el("h3", { text: "What the policy reads, per RAT", style: "margin-top:14px" }));
  const H0 = r.decisions || {};
  set.append(kvList(H0.inputs === "capacity" ? [
    ["Usable", "measured in the last 0.5 s, signal above the RAT's minimum, and for Wi-Fi/DSRC connected to an AP/RSU"],
    ["Signal", "estimated uplink SINR, as dB above the lowest SINR the RAT can use"],
    ["Load", "Wi-Fi/DSRC: share of time the channel is busy. 5G: share of the cell's uplink resources in use"],
    ["Capacity", "link rate × the free share"], ["Latency", "estimated delay to get one packet out, longer when busy"]] : [
    ["Usable", `measured in the last ${sm.measurementMaxAge || "0.5s"}, signal above the RAT's minimum, linked (Wi-Fi/DSRC: associated with an AP/RSU; 5G: attached to a cell)` +
               (sm.requireProbeEcho === "true" ? `, and the car's probes over it echoed within ${sm.probeMaxAge || "0.5s"}` : "")],
    ["Signal", "estimated uplink SINR, as dB above the lowest SINR the RAT can use"],
    ["Load", "Wi-Fi/DSRC: share of time the channel is busy, as the car's radio senses it. 5G: none (a car cannot see how busy its cell is)"],
    ["Link rate", "Wi-Fi/DSRC: the rate data frames are sent at. 5G: from the measured SINR and the cell's bandwidth"],
    ["Probe round trip", "mean round trip of the small probes the car sends over every linked RAT and the server echoes, over the last second"]]));
  g.append(treeCard, set);
  sec.append(g);
  sec.append(renderTurns(r, P));
  return sec;
}

function renderTurns(r, P) {
  const H = heavy(r), D = r.decisions;
  const card = el("div", { class: "card", style: "margin-top:12px" }, el("h3", { text: "Decisions, turn by turn" }));
  if (!H || !H.table) { card.append(el("p", { class: "muted", text: "Not recorded for this run (it predates the decision log). Rerun it to see every decision." })); return card; }
  const rats = D.rats;
  const carSel = el("select", { "aria-label": "Car" }, el("option", { value: "", text: "All cars" }), ...D.cars.map(c => el("option", { value: c, text: `Car ${c}` })));
  const onlyBox = el("input", { type: "checkbox", id: "only" }); onlyBox.checked = true;
  const info = el("span", { class: "muted" });
  card.append(el("div", { class: "tbar" }, carSel, el("label", {}, onlyBox, " Only turns where something happened"), info));
  card.append(el("p", { class: "note", style: "margin:0 0 8px", text:
    `Each RAT column shows what this policy compares${P.key === "all" ? (D.inputs === "capacity" ? " (signal · load · free capacity)" : " (signal · load · link rate)") : ""}. Grey = measured but not usable; – = nothing measured. Click a row for every input.` + (D.table_sampled ? " Long run: quiet turns are thinned out." : "") }));
  const t = el("table", { id: "turns" });
  t.append(el("thead", {}, el("tr", {}, el("th", { class: "n", text: "Time" }), el("th", { text: "Car" }), el("th", { text: "On" }),
    ...rats.map(k => el("th", {}, ratName(k))), el("th", { text: "Picked" }), el("th", { text: "Why" }))));
  const body = el("tbody");
  t.append(body);
  card.append(el("div", { class: "scroll", style: "max-height:560px;overflow-y:auto" }, t));
  const more = el("button", { type: "button", text: "Show more", style: "margin-top:8px" });
  card.append(more);

  const val = (c) => {
    const [ok, sinr, load, cap, lat] = c;
    const s = v => v == null ? "–" : (v > 0 ? "+" : "") + fmt(v, 1) + " dB";
    switch (P.key) {
      case "sinr": return s(sinr);
      case "load": return load == null ? "–" : pct(load, 0) + " busy";
      case "cap": return cap == null ? "–" : `${fmt(cap, 1)} Mb/s · ${fmt(lat, 1)} ms`;
      case "rate": return cap == null ? "–" : `${fmt(cap, 1)} Mb/s · ${lat == null ? "no echo" : fmt(lat, 1) + " ms RTT"}`;
      case "ok": return ok ? "usable" : sinr == null ? "–" : "not usable";
      default: return sinr == null ? "–" : [s(sinr), load == null ? null : pct(load, 0), cap == null ? null : fmt(cap, 0) + " Mb/s"].filter(Boolean).join(" · ");
    }
  };
  let rows = [], shown = 0;
  const PAGE = 100;
  const draw = (reset) => {
    if (reset) { body.replaceChildren(); shown = 0; }
    for (const row of rows.slice(shown, shown + PAGE)) {
      const [tt, car, cur, choice, br, detail, cells] = row;
      const tr = el("tr", { class: "row" + (choice && choice !== cur ? " changed" : "") },
        el("td", { class: "n", text: fmt(tt, 1) }), el("td", { text: car }), el("td", {}, cur ? ratName(cur) : "–"),
        ...cells.map(c => el("td", { class: "rat" + (c[0] ? "" : " off") }, val(c), c[0] && c[5] ? el("small", { text: c[5] }) : null)),
        el("td", { class: "pick" }, choice ? ratName(choice) : "–"),
        el("td", { class: "why-" + br, text: (WHY[br] || (() => br))(detail) }));
      tr.addEventListener("click", () => {
        const nx = tr.nextElementSibling;
        if (nx && nx.classList.contains("more")) { nx.remove(); return; }
        const rated = D.inputs !== "capacity";
        const sub = simpleTable(["RAT", "Usable", "Signal (dB above min)", "Load", rated ? "Link rate" : "Free capacity", rated ? "Probe round trip" : "Latency", "Served by"],
          cells.map((c, i) => [RAT_LABEL[rats[i]], c[0] ? "yes" : "no", c[1] == null ? "–" : fmt(c[1], 1), c[2] == null ? "–" : pct(c[2], 1),
                               c[3] == null ? "–" : fmt(c[3], 2) + " Mbit/s", c[4] == null ? "–" : fmt(c[4], 2) + " ms", c[5] || "–"]), [2, 3, 4, 5]);
        tr.after(el("tr", { class: "more" }, el("td", { colspan: 5 + rats.length }, sub)));
      });
      body.append(tr);
    }
    shown = Math.min(rows.length, shown + PAGE);
    info.textContent = `${fmt(shown, 0)} of ${fmt(rows.length, 0)} turns`;
    more.hidden = shown >= rows.length;
  };
  const filter = () => {
    const car = carSel.value, only = onlyBox.checked;
    rows = H.table.filter(x => (car === "" || String(x[1]) === car) && (!only || x[4] !== "best"));
    if (car === "") rows = rows.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    draw(true);
  };
  carSel.addEventListener("change", filter); onlyBox.addEventListener("change", filter); more.addEventListener("click", () => draw(false));
  filter();
  return card;
}

// ------------------------------------------------------------------ network
function renderNetworkSection(r) {
  const sec = section("s-network", "Network", "How each radio is set up in this run, and what cars measured on it.");
  const g = el("div", { class: "grid3" });
  for (const c of r.network_info || []) {
    const card = el("div", { class: "card" }, el("h3", {}, ratDot(c.rat), c.title), kvList(c.rows));
    if (c.note) card.append(el("p", { class: "note", text: c.note }));
    g.append(card);
  }
  if (!(r.network_info || []).length) g.append(el("div", { class: "card muted", text: "No radio parameters recorded for this run." }));
  sec.append(g);
  return sec;
}

// ------------------------------------------------------------------ results
function stat(v, lbl, detail, unit) {
  return el("div", { class: "stat" }, el("div", { class: "v", text: v }, unit && v !== "–" ? el("small", { text: unit }) : null),
            el("div", { class: "l", text: lbl }), detail ? el("div", { class: "d", text: detail }) : null);
}

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
  const avail = document.getElementById("run").clientWidth || 560;
  const W = Math.max(280, Math.min(560, avail >= 1000 ? (avail - 12) / 2 - 34 : avail - 34)), H = 220, m = { l: 44, r: 10, t: 8, b: 24 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const tMax = t[t.length - 1], bin = t.length > 1 ? t[1] - t[0] : t[0];
  let yMax = niceMax(Math.max(...series.flatMap(s => s.values.filter(v => v != null))));
  if (digits === 0) yMax = Math.max(4, Math.ceil(yMax / 4) * 4);
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
      svg.append(svgEl("path", { d, fill: "none", stroke: `var(${s.color})`, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" }));
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
    for (const s of series) tip.append(el("div", { class: "row" }, el("span", { class: "key", style: `background:var(${s.color})` }),
      el("b", { text: s.values[i] == null ? "–" : fmt(s.values[i], digits) + (unit ? " " + unit : "") }), series.length > 1 ? el("span", { class: "muted", text: s.name }) : null));
    tip.hidden = false;
    const rr = svg.getBoundingClientRect(), px = (xx / W) * rr.width;
    tip.style.top = (svg.offsetTop + 8) + "px";
    tip.style.left = Math.min(Math.max(0, px + 12), rr.width - tip.offsetWidth) + "px";
  };
  svg.addEventListener("pointermove", ev => {
    const rr = svg.getBoundingClientRect(), vx = (ev.clientX - rr.left) / rr.width * W;
    show(Math.min(t.length - 1, Math.max(0, Math.round(((vx - m.l) / iw) * tMax / bin - 1))));
  });
  svg.addEventListener("pointerleave", () => { hair.setAttribute("visibility", "hidden"); tip.hidden = true; });
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

function renderResultsSection(r) {
  const s = r.summary, u = r.setup || {};
  const sec = section("s-results", "Results", "How well the traffic got through over the whole run.");
  if (!s) { sec.append(el("div", { class: "card empty", text: "This run produced no result files. See the console output under Run." })); return sec; }
  const g = el("div", { class: "grid3" });
  const classes = s.classes || [];
  for (const c of classes) {
    const tr = (u.traffic || []).find(x => x.name === c.name);
    const card = el("div", { class: "card" }, el("h3", { text: className(c.name) }));
    if (tr || c.direction) card.append(el("p", { class: "note", style: "margin:-4px 0 10px", text: [tr ? `${tr.packet} every ${tr.interval}` + (tr.mode === "onoff" ? " in bursts" : "") : null,
      c.direction === "server to car" ? `judged at the car, on the server's replies, ${fmt(c.deadline_ms, 0)} ms from the request` : c.deadline_ms ? `judged at the server, ${fmt(c.deadline_ms, 0)} ms deadline` : null].filter(Boolean).join(" · ") }));
    const st = el("div", { class: "stats" });
    if (c.within_deadline != null) st.append(stat(pct(c.within_deadline), "arrived on time", `within ${fmt(c.deadline_ms, 0)} ms`));
    st.append(stat(pct(c.pdr), "delivered", `${fmt(c.received, 0)} of ${fmt(c.sent, 0)} packets`));
    st.append(stat(fmt(c.delay_mean_ms, 1), "average delay", c.delay_max_ms != null ? `worst ${fmt(c.delay_max_ms, 0)} ms` : null, "ms"));
    if (c.within_deadline == null) st.append(stat(fmt(c.throughput_mbps, 2), "received", "all cars together", "Mbit/s"));
    card.append(st);
    g.append(card);
  }
  if (!classes.length) g.append(el("div", { class: "card" }, el("h3", { text: "Traffic" }), el("div", { class: "stats" },
    stat(pct(s.pdr), "delivered", `${fmt(s.received, 0)} of ${fmt(s.sent, 0)} packets`), stat(fmt(s.delay_mean_ms, 1), "average delay", null, "ms"))));

  const sw = el("div", { class: "card" }, el("h3", { text: "Switching between RATs" }));
  const sst = el("div", { class: "stats" }, stat(fmt(s.handovers_per_vehicle, 1), "switches per car", `${fmt(s.handovers, 0)} in total`));
  if (s.interruption_count) sst.append(stat(fmt(s.interruption_mean_ms, 0), "gap per switch", `time until the first packet arrives over the new RAT; worst ${fmt(s.interruption_max_ms, 0)} ms`, "ms"),
                                       stat(fmt(s.interruption_lost, 0), "packets lost while switching", null));
  if (s.handovers_failed) sst.append(stat(fmt(s.handovers_failed, 0), "switches that failed", "the target stopped working first"));
  sw.append(sst);
  g.append(sw);

  const cn = el("div", { class: "card" }, el("h3", { text: "Which RAT cars were on" }));
  const bar = el("div", { class: "sharebar", role: "img", "aria-label": "Share of time on each RAT" });
  const lg = el("div", { class: "legend" });
  for (const [k, v] of Object.entries(s.shares)) {
    if (!v) continue;
    bar.append(el("span", { style: `width:${v * 100}%;background:var(${RAT_COLOR[k] || "--s5"})`, title: `${RAT_LABEL[k] || k} ${pct(v)}` }));
    lg.append(el("span", {}, el("span", { class: "key box", style: `background:var(${RAT_COLOR[k] || "--s5"})` }), `${RAT_LABEL[k] || k} ${pct(v, 0)}`));
  }
  cn.append(bar, lg, el("div", { class: "stats", style: "margin-top:8px" },
    stat(pct(s.connectivity), "of the time a car had a usable RAT", `${fmt(s.outage_s, 1)} s without one, all cars together`)));
  if (r.cellular_merged) cn.append(el("p", { class: "note", text: "LTE and 5G share one IP interface in this run, so they are counted together as Cellular." }));
  g.append(cn);
  sec.append(g);

  if (r.series) {
    const S = r.series, t = S.t;
    sec.append(el("p", { class: "sub", style: "margin-top:16px", text: `Over time. Each point is the average over ${fmt(S.bin_s, 1)} s of simulated time.` }));
    const c = el("div", { class: "grid2" });
    c.append(chart({ title: "Cars on each RAT", unit: "", t, digits: 0,
                     series: Object.entries(S.rat).map(([k, v]) => ({ name: RAT_LABEL[k] || k, color: RAT_COLOR[k] || "--s5", values: v })) }));
    c.append(chart({ title: "Data sent and received, Mbit/s", unit: "Mbit/s", t, digits: 3,
                     series: [{ name: "Sent by cars", color: "--s1", values: S.offered_mbps }, { name: "Received by server", color: "--s2", values: S.delivered_mbps }] }));
    const dl = Array.isArray(S.delay_ms) ? { Delay: S.delay_ms } : S.delay_ms;
    c.append(chart({ title: "Average delay, ms", unit: "ms", t, digits: 1,
                     series: Object.entries(dl).map(([k, v], i) => ({ name: className(k), color: `--s${i + 1}`, values: v })) }));
    c.append(chart({ title: S.bin_s === 1 ? "RAT switches per second, all cars" : `RAT switches per ${fmt(S.bin_s, 1)} s, all cars`, unit: "", t, digits: 0, bars: true,
                     series: [{ name: "Switches", color: "--s1", values: S.handovers }], empty: "No switches in this run" }));
    sec.append(c);
  }
  return sec;
}

// ------------------------------------------------------------------ page
function renderRun(r) {
  const root = document.getElementById("run");
  root.replaceChildren();
  const st = document.getElementById("status");
  st.className = "pill " + (r.status === "ok" ? "st-ok" : r.status === "failed" ? "st-failed" : "st-none");
  st.textContent = r.status === "ok" ? "completed" : r.status;
  document.querySelectorAll("#history tbody tr").forEach(tr => tr.classList.toggle("sel", tr.dataset.id === r.id));
  const d = (r.setup && r.setup.decision) || {};
  const radios = ((r.setup && r.setup.rats) || []).map(x => RAT_LABEL[x.rat] || x.rat);
  root.append(el("p", { class: "intro", text: `Cars drive on the road with ${radios.length ? radios.length + " radios each: " + radios.join(", ") : "several radios each"} (each one a RAT, radio access technology). ` +
    `Every ${d.decisionInterval || "0.5s"}, the ${d.policy || "selection"} policy picks which RAT carries the car's traffic to a server on the internet. ` +
    `This page shows one run: how it was set up, where each radio worked, what every car chose and why, and how well the traffic got through.` }));
  if (!r.setup) {
    root.append(el("div", { class: "card empty", style: "margin-top:16px", text: "This run produced no result files." }));
    if (r.log) root.append(el("pre", { class: "log", text: r.log }));
    return;
  }
  root.append(renderRunMeta(r));
  const map = renderMapSection(r);
  root.append(map.sec);
  root.append(renderPolicySection(r), renderNetworkSection(r), renderResultsSection(r));
  map.init();
}

function renderHistory() {
  const tb = document.getElementById("history");
  const cls = (r, name, key) => { const c = r.summary && (r.summary.classes || []).find(x => x.name === name); return c && c[key] != null ? pct(c[key]) : "–"; };
  const cols = [["Started", r => when(r.started)], ["Scenario", r => (r.meta && r.meta.scenario) || r.config || "–"],
    ["Policy", r => (r.setup && r.setup.decision && r.setup.decision.policy) || (r.meta && r.meta.policy) || "–"],
    ["Seed", r => (r.seed && r.seed.seedset) || (r.meta && r.meta.seed) || "0", 1], ["Label", r => (r.meta && r.meta.name) || ""],
    ["Status", r => r.status === "ok" ? "completed" : r.status],
    ["Safety on time", r => cls(r, "safety", "within_deadline"), 1], ["Infotainment delivered", r => cls(r, "infotainment", "pdr"), 1],
    ["Switches per car", r => r.summary ? fmt(r.summary.handovers_per_vehicle, 1) : "–", 1],
    ["Simulated", r => r.sim_time != null ? fmt(r.sim_time, 0) + " s" : "–", 1]];
  tb.append(el("thead", {}, el("tr", {}, ...cols.map(([h, , n]) => el("th", { class: n ? "n" : null, text: h })))));
  const body = el("tbody");
  for (const r of RUNS) {
    const tr = el("tr", { tabindex: "0" }, ...cols.map(([h, f, n]) => {
      const td = el("td", { class: n ? "n" : null, text: f(r) });
      if (h === "Status") td.className = r.status === "ok" ? "st-ok" : r.status === "failed" ? "st-failed" : "st-none";
      return td;
    }));
    tr.dataset.id = r.id;
    const go = () => { pick.value = r.id; history.replaceState(null, "", "#" + r.id); showRun(r); window.scrollTo({ top: 0, behavior: "smooth" }); };
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
// the test bench page shows these too
const BENCH_METRICS = {
  traffic: ["safety_pdr", "safety_on_time", "info_pdr", "info_on_time", "safety_delay", "info_delay", "safety_delay_max", "info_delay_max"],
  coverage: ["conn", "outage"],
  switching: ["ho", "pingpong", "gap", "gap_max", "lost", "failed"],
};
const EXTRA_METRICS = [
  ["safety_delay_max", "Safety worst delay", "ms", "low"],
  ["info_delay_max", "Infotainment worst delay", "ms", "low"],
  ["conn", "Time with a usable RAT", "pct", "high"],
  ["outage", "Time without a usable RAT, per car", "s", "low"],
  ["gap_max", "Worst switch gap", "ms", "low"],
  ["lost", "Packets lost while switching (all cars)", "num", "low"],
  ["failed", "Switches that failed (all cars)", "num", "low"],
];
const METRIC = Object.fromEntries(CMP_METRICS.concat(EXTRA_METRICS).map(m => [m[0], m]));

function runMetrics(r) {
  const s = r.summary, out = {};
  for (const c of s.classes || []) {
    const k = c.name === "safety" ? "safety" : c.name === "infotainment" ? "info" : null;
    if (!k) continue;
    out[k + "_pdr"] = c.pdr; out[k + "_on_time"] = c.within_deadline; out[k + "_delay"] = c.delay_mean_ms;
    out[k + "_delay_max"] = c.delay_max_ms;
  }
  out.ho = s.handovers_per_vehicle; out.pingpong = s.ping_pong; out.gap = s.interruption_mean_ms;
  out.conn = s.connectivity; out.outage = s.vehicles ? s.outage_s / s.vehicles : null;
  out.gap_max = s.interruption_max_ms; out.lost = s.interruption_lost; out.failed = s.handovers_failed;
  const D = r.decisions;
  if (D && D.count) for (const [b, n] of Object.entries(D.branches || {})) out["br_" + (b || "other")] = n / D.count;
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

const cmpFmt = (v, kind) => v == null ? "–" : kind === "pct" ? (v * 100).toFixed(1) + "%" : kind === "ms" ? fmt(v, 1) + " ms" : kind === "s" ? fmt(v, 1) + " s" : fmt(v, 2);

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
  const avail = document.getElementById("s-compare").clientWidth || 560;
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
  const avail = document.getElementById("s-compare").clientWidth || 560;
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

function comparisonTable(rows, clickable = true) {
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
    const go = () => { const run = r.runs[0]; pick.value = run.id; history.replaceState(null, "", "#" + run.id);
                       showRun(run).then(() => document.getElementById("s-run").scrollIntoView({ behavior: "smooth" })); };
    if (clickable) {
      tr.addEventListener("click", go);
      tr.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
    } else { tr.removeAttribute("tabindex"); tr.removeAttribute("title"); tr.style.cursor = "default"; }
    b.append(tr);
  }
  t.append(b);
  return el("div", { class: "scroll" }, t);
}

// Why cars switched or stayed: per policy, the share of decisions that ended in each outcome other
// than "already on the top pick" (from the decision logs). Fixed colour per outcome.
const BRANCHES = [["switch", "Switched: better for long enough", "--s1"], ["lost", "Switched: its RAT stopped working", "--s2"],
                  ["wait", "Waiting out the time-to-trigger", "--s3"], ["margin", "Stayed: top pick not better by enough", "--s4"],
                  ["sticky", "Stayed: close enough in the vote", "--s4"]];
function branchChart(rows) {
  const card = el("div", { class: "card chart hbar" });
  card.append(el("h3", { text: "Why cars switched or stayed (share of all decisions; the rest stayed on the top pick)" }));
  const used = BRANCHES.filter(([b]) => rows.some(r => r["br_" + b] && r["br_" + b].m > 0));
  if (!used.length) { card.append(el("div", { class: "empty", text: "No decision logs in these runs" })); return card; }
  const lg = el("div", { class: "legend" });
  for (const [b, name, c] of used) if (b !== "sticky" || !used.some(x => x[0] === "margin"))
    lg.append(el("span", {}, el("span", { class: "key box", style: `background:var(${c})` }), name + (b === "margin" && used.some(x => x[0] === "sticky") ? " (Ensemble: close enough in the vote)" : "")));
  card.append(lg);
  const avail = document.getElementById("s-compare").clientWidth || 560;
  const W = Math.max(300, Math.min(1100, avail - 34)), rowH = 26, m = { l: 118, r: 60, t: 4, b: 22 };
  const H = m.t + m.b + rowH * rows.length, iw = W - m.l - m.r;
  const tot = r => used.reduce((a, [b]) => a + (r["br_" + b] ? r["br_" + b].m : 0), 0);
  const xMax = niceMax(Math.max(...rows.map(tot), 0.001));
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Decision outcomes per policy" });
  const ax = svgEl("g", { class: "axis" });
  for (let i = 0; i <= 4; i++) {
    const v = xMax * i / 4, xx = m.l + iw * i / 4;
    ax.append(svgEl("line", { class: i ? "gridline" : "baseline", x1: xx, x2: xx, y1: m.t, y2: H - m.b }));
    const tx = svgEl("text", { x: xx, y: H - 6, "text-anchor": i === 0 ? "start" : i === 4 ? "end" : "middle" });
    tx.textContent = (v * 100).toFixed(v < 0.1 ? 1 : 0) + "%"; ax.append(tx);
  }
  svg.append(ax);
  const tip = el("div", { class: "tip", hidden: "" });
  rows.forEach((row, i) => {
    const y0 = m.t + i * rowH, cy = y0 + rowH / 2, bh = 14;
    if (i > 0 && isBaseline(row.policy) && !isBaseline(rows[i - 1].policy))
      svg.append(svgEl("line", { class: "sep", x1: 0, x2: W, y1: y0, y2: y0 }));
    const lab = svgEl("text", { class: "lab", x: m.l - 8, y: cy + 4, "text-anchor": "end" });
    lab.textContent = policyLabel(row.policy); svg.append(lab);
    let xx = m.l;
    const parts = used.map(([b, name, c]) => [name, c, row["br_" + b] ? row["br_" + b].m : 0]).filter(p => p[2] > 0);
    for (const [, c, v] of parts) {
      const w = v / xMax * iw;
      if (w > 2) svg.append(svgEl("rect", { x: xx + 1, y: cy - bh / 2, width: w - 2, height: bh, rx: 2, fill: `var(${c})` }));
      xx += w;
    }
    const val = svgEl("text", { class: "val", x: xx + 6, y: cy + 4 });
    val.textContent = (tot(row) * 100).toFixed(1) + "%"; svg.append(val);
    const hit = svgEl("rect", { class: "hit", x: 0, y: y0, width: W, height: rowH });
    hit.addEventListener("pointerenter", () => {
      tip.replaceChildren(el("div", { class: "ts", text: policyLabel(row.policy) + " · share of all decisions" }),
        ...(parts.length ? parts.map(([name, c, v]) => el("div", { class: "row" }, el("span", { class: "key box", style: `background:var(${c})` }),
                                       el("b", { text: (v * 100).toFixed(2) + "%" }), el("span", { class: "muted", text: name })))
                         : [el("div", { class: "muted", text: "always on the top pick" })]));
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

// Every run of the bench, one row per (policy, seed)
function runsTable(g) {
  const cols = [["safety_pdr", "Safety delivered", "pct"], ["safety_on_time", "Safety on time", "pct"], ["info_pdr", "Infot. delivered", "pct"],
                ["info_on_time", "Infot. on time", "pct"], ["ho", "Handovers / car", "num"], ["pingpong", "Ping-pongs", "num"],
                ["gap", "Switch gap", "ms"], ["conn", "Usable RAT", "pct"], ["share_DSRC", "On DSRC", "pct"], ["share_WiFi", "On WiFi", "pct"], ["share_NR", "On 5G", "pct"]];
  const t = el("table");
  t.append(el("thead", {}, el("tr", {}, el("th", { text: "Policy" }), el("th", { class: "n", text: "Seed" }), ...cols.map(([, h]) => el("th", { class: "n", text: h })))));
  const b = el("tbody");
  for (const p of g.policies)
    for (const r of p.runs.slice().sort((a, c) => (a.meta.seed || "0").localeCompare(c.meta.seed || "0"))) {
      const x = runMetrics(r);
      b.append(el("tr", { class: isBaseline(p.policy) ? "base" : null }, el("td", { text: policyLabel(p.policy) }),
        el("td", { class: "n", text: r.meta.seed || "0" }), ...cols.map(([k, , kind]) => el("td", { class: "n", text: cmpFmt(x[k], kind) }))));
    }
  t.append(b);
  return el("div", { class: "scroll" }, t);
}

function renderBench(groups, g) {
  const B = DATA.bench, root = document.getElementById("s-compare");
  const std = B.standard;
  root.replaceChildren(el("h2", { text: "Test bench" }));
  const rerun = "bench/run.sh" + (std ? "" : " " + (B.extra || []).map(x => {
    const [k, ...v] = x.split(" "); return `--${k === "set" ? "set" : k} '${v.join(" ")}'`; }).join(" "));
  const btn = el("button", { type: "button", text: "Copy" });
  btn.addEventListener("click", () => copyText(rerun, btn));
  root.append(el("p", { class: "sub", text: "Every policy and the one-RAT baselines on the same scenario with the same seeds, side by side. " +
    "Each number is the mean over the seeds; whiskers and ± are the standard deviation across seeds. A difference smaller than that is not a difference." }));
  root.append(el("div", { class: "cmd" }, el("pre", { text: rerun, "aria-label": "Command that repeats this bench" }), btn));
  const seeds = [...new Set(g.policies.flatMap(p => p.seeds))].sort();
  const info = el("div", { class: "grid2" });
  info.append(el("div", { class: "card" }, el("h3", { text: "What ran" }), kvList([
    ["Scenario", g.scenario + (groups.length > 1 ? ` (one of ${groups.length}; pick below)` : "")],
    ["Simulated time", `${fmt(g.simTime, 0)} s per run`], ["Seeds", seeds.join(", ")],
    ["Policies", g.policies.filter(p => !isBaseline(p.policy)).map(p => policyLabel(p.policy)).join(", ")],
    ["Baselines", g.policies.filter(p => isBaseline(p.policy)).map(p => policyLabel(p.policy)).join(", ") || "none"],
    ["Settings", std ? "standard bench" : "NOT the standard bench: " + (B.extra || []).join("; ")],
    ["Image", B.image], ["Code version", B.repo_commit], ["Started", when(B.started)], ["Runs", `${g.runs.length}` + (DATA.runs.some(r => r.status !== "ok") ? `, ${DATA.runs.filter(r => r.status !== "ok").length} failed` : ", all completed")]])));
  info.append(el("div", { class: "card" }, el("h3", { text: "How to read it" }), kvList([
    ["Safety", "small car-to-server messages; on time = arrived at the server within 100 ms"],
    ["Infotainment", "requests the server answers with bigger replies; judged at the car, on time = the reply arrived within 1 s of the request"],
    ["Handover", "the car moved its traffic to another RAT; a ping-pong is a move back within the ping-pong window"],
    ["Switch gap", "from the first packet sent on the new RAT until the first one arrives"],
    ["Usable RAT", "share of the time a car had at least one RAT it could use"],
    ["Baselines", "use one RAT and nothing else: what a policy must beat"]])));
  root.append(info);
  if (groups.length > 1) {
    const sel = el("select", { id: "cmp-pick" });
    for (const x of groups) sel.append(el("option", { value: x.key, text: `${x.scenario}, ${fmt(x.simTime, 0)} s` }));
    sel.value = g.key;
    sel.addEventListener("change", () => renderBench(groups, groups.find(x => x.key === sel.value)));
    root.append(el("div", { class: "filters", style: "margin-top:12px" }, el("label", { for: "cmp-pick", class: "muted", text: "Scenario" }), sel));
  }
  const part = (title, sub, keys) => {
    root.append(el("h2", { text: title }));
    if (sub) root.append(el("p", { class: "sub", text: sub }));
    const grid = el("div", { class: "grid2" });
    for (const k of keys) {
      const [, t, kind, better] = METRIC[k];
      if (g.policies.some(p => p[k])) grid.append(hbarChart(t, better, g.policies, k, kind));
    }
    root.append(grid);
  };
  part("Did the traffic get through", "Policies in blue, one-RAT baselines in grey. Hover a bar for its value and spread.", BENCH_METRICS.traffic);
  part("Coverage", "How often cars had a RAT they could use at all.", BENCH_METRICS.coverage);
  part("Switching", "How often cars changed RAT and what each change cost.", BENCH_METRICS.switching);
  root.append(el("h2", { text: "How the policies chose" }));
  root.append(shareChart(g.policies));
  const bc = branchChart(g.policies); bc.style.marginTop = "12px"; root.append(bc);
  root.append(el("h2", { text: "All numbers" }));
  root.append(el("div", { class: "card" }, el("h3", { text: "Per policy: mean ± standard deviation across seeds (bold: best policy, baselines excluded)" }),
    comparisonTable(g.policies, false)));
  root.append(el("div", { class: "card", style: "margin-top:12px" }, el("h3", { text: "Every run" }), runsTable(g)));
}

function renderCompare(groups, g) {
  const root = document.getElementById("s-compare");
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
  root.append(el("p", { class: "note", style: "margin:0 0 10px", text: "Policies in blue, one-RAT baselines in grey. Hover a bar for its value and spread." }));
  root.append(grid);
  const sh = shareChart(g.policies); sh.style.marginTop = "12px"; root.append(sh);
  root.append(el("div", { class: "card", style: "margin-top:12px" },
    el("h3", { text: "All numbers (mean ± standard deviation across seeds; bold: best policy, baselines excluded; click a row to open its first run below)" }),
    comparisonTable(g.policies)));
}

if (DATA.bench) document.body.classList.add("bench");
document.getElementById("gen").textContent = when(DATA.generated);
const pick = document.getElementById("pick");
for (const r of RUNS) pick.append(el("option", { value: r.id, text: `${when(r.started)} · ${label(r)}` }));
pick.addEventListener("change", () => { history.replaceState(null, "", "#" + pick.value); showRun(RUNS.find(r => r.id === pick.value)); });
const CMP_GROUPS = comparisonGroups();
if (DATA.bench) {
  document.querySelector("header.top h1").textContent = "MultiRATVANET test bench";
  document.title = "MultiRATVANET test bench";
  const sec = document.getElementById("s-compare");
  sec.hidden = false;
  if (CMP_GROUPS.length) renderBench(CMP_GROUPS, CMP_GROUPS[0]);
  else sec.append(el("div", { class: "card empty", text: "No completed runs in this bench." }));
} else renderHistory();
if (!DATA.bench && CMP_GROUPS.length) {
  document.getElementById("s-compare").hidden = false;
  document.getElementById("nav-compare").hidden = false;
  renderCompare(CMP_GROUPS, CMP_GROUPS[0]);
}
const linked = RUNS.find(r => "#" + r.id === decodeURIComponent(location.hash));
if (DATA.bench) { /* the bench page shows no single run */ }
else if (linked) { pick.value = linked.id; showRun(linked); }
else if (RUNS.length) showRun(RUNS[0]);
else document.getElementById("run").append(el("div", { class: "card empty", text: "No runs yet. Start one with dash/run-experiment.sh." }));
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
