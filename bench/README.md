# Test bench

One standard way to compare the policies with each other and with single-RAT baselines. Run it
before and after any change to the harness, and compare the two.

## What it runs

| | |
|---|---|
| Policies | `CoveragePriority`, `Sinr`, `LatencyQos`, `Load`, `Ensemble` |
| Baselines | `OnlyDsrc`, `OnlyWifi`, `OnlyNr`: the car uses that one RAT and nothing else |
| Scenario | highway (17 cars, 3 RSUs, 2 APs, 2 gNodeBs), each policy with its highway config from `omnetpp.ini` |
| Time | 120 s per run |
| Seeds | 0, 1, 2 (each policy is run with each seed; the tables show the mean and the spread) |

That is 24 runs. With 8 at a time it takes about 10–15 minutes on the lab machine.

`Ml` is left out: with no controller attached it decides exactly like `CoveragePriority`.
`ExampleSplit` is a template, not a policy being compared. Both can be added with `--only`.

**Baselines.** A baseline asks for its RAT whenever that RAT is usable and never names another.
Once a car is attached it stays on that RAT, and while out of range its traffic still goes out on
it and is lost, as for a car that only has that radio. Probes still run on every RAT, so every
run puts the same probe load on the channels. A car that never comes into range of its RAT
sends everything into nothing (the requests are still counted as sent).

## Commands

```bash
dash/build-image.sh                               # build the image from your working copy first

bench/run.sh                                      # the standard bench
bench/run.sh --against bench/reference            # ... with the change against the committed reference
bench/run.sh --against bench-results/<earlier>    # ... or against any earlier bench

bench/run.sh --quick                              # 60 s, seed 0: just a sanity check, not for comparing
bench/run.sh --scenarios "highway urbangrid"      # more scenarios
bench/run.sh --only "sinr only_nr" --set '*.car[*].app[2].probeInterval=200ms'
bench/run.sh --help

python3 bench/compare.py bench-results/<bench> --against bench-results/<other>   # compare again later
```

Each bench writes `bench-results/<UTC time>[-label]/`:

| File | |
|---|---|
| `summary.md` | the tables (also printed at the end) |
| `summary.json` | the same numbers, for scripts and for `--against` |
| `report.html` | open this first: the **Compare policies** view (a bar chart per metric, policies against baselines, mean and spread over the seeds; time on each RAT; the full table), then every run in detail: per-class results, console log, and the time series if the bench ran with `--vectors` |
| `bench.json` | the settings, the image and the commit it was built from |
| `<run>/` | one folder per run, as written by `dash/run-experiment.sh` |
| `.log-<scenario>-<policy>-s<seed>` | the console of a run, to look at when it fails |

Anything other than the standard settings (other scenarios, seeds, time, policies, or any
`--set`) is written into `bench.json` and shown at the top of `summary.md`, so a non-standard
bench is never mistaken for the standard one.

## The columns

| Column | Meaning |
|---|---|
| Safety delivered / on time | share of safety messages that reached the server / reached it within 100 ms |
| Safety delay ms | mean one-way delay of the safety messages that arrived |
| Infot. delivered / on time | share of infotainment data packets (server to car) that reached the car / within 1 s of the request |
| Infot. delay ms | mean time from the request to each data packet |
| Handovers / car | switches of the default RAT per car |
| Ping-pongs | switches back to the previous RAT within 2 s, all cars together |
| Switch gap ms | after a switch: from the first request sent on the new RAT to the first one that arrives |
| On DSRC / WiFi / 5G | share of a car's attached time on that RAT, averaged over the cars (a car that never attached counts 0) |

Numbers are the mean over the seeds, ± the standard deviation across seeds. With `--against`,
the change is in brackets (percentages in points). A change smaller than the ± is not a change.

## The reference

`bench/reference/` holds the standard bench of the current harness (`summary.md` to read,
`summary.json` for `--against`). When a change to the harness is meant to change the results,
rerun the bench and replace the reference in the same commit, so the next change is compared with
the right numbers:

```bash
bench/run.sh --label new && cp bench-results/<new bench>/summary.{md,json} bench/reference/
```
