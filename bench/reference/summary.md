# Test bench: 20261117T105944Z-standard

Sim time 120s, seeds ['0', '1', '2'], image multiratvanet:latest (commit d55ae08c33).

Numbers in brackets: change against bench `20261117T101058Z-standard` (commit 502870fd64); percentages in points.

Values are the mean over the seeds, ± the standard deviation across seeds. Safety is judged at the server (100 ms deadline), infotainment at the car (1 s from the request). Switch gap: first request sent on the new RAT until the first one that arrives. On DSRC/WiFi/5G: share of the time a car was attached to a RAT, averaged over the cars (a car that never attached counts 0).

## highway

### Traffic

| Policy | Safety delivered | Safety on time | Safety delay ms | Infot. delivered | Infot. on time | Infot. delay ms |
|---|---|---|---|---|---|---|
| CoveragePriority | 93.2 % ±0.2 (+0.0) | 91.8 % ±0.2 (+0.0) | 10.7 ±0.9 (+0.0) | 91.7 % ±0.9 (+0.0) | 91.6 % ±1.0 (+0.0) | 62.6 ±4.0 (+0.0) |
| Sinr | 94.3 % ±0.7 (+0.0) | 93.0 % ±0.8 (+0.0) | 13.0 ±0.7 (+0.0) | 93.0 % ±0.7 (+0.0) | 92.8 % ±0.8 (+0.0) | 62.8 ±1.8 (+0.0) |
| LatencyQos | 93.4 % ±2.3 (+0.0) | 92.3 % ±2.7 (+0.0) | 13.1 ±3.5 (+0.0) | 92.1 % ±2.6 (+0.0) | 92.0 % ±2.6 (+0.0) | 63.4 ±6.3 (+0.0) |
| Load | 94.4 % ±2.4 (+0.0) | 93.4 % ±3.1 (+0.0) | 7.5 ±4.7 (+0.0) | 93.9 % ±2.2 (+0.0) | 93.9 % ±2.2 (+0.0) | 55.4 ±5.7 (+0.0) |
| Ensemble | 92.2 % ±0.5 (+0.0) | 91.0 % ±0.5 (+0.0) | 12.2 ±0.5 (+0.0) | 90.1 % ±1.5 (+0.0) | 90.0 % ±1.5 (+0.0) | 63.1 ±0.8 (+0.0) |
| *baselines* | | | | | | |
| only DSRC | 74.0 % ±4.6 (+0.0) | 74.0 % ±4.6 (+0.0) | 1.1 ±0.1 (+0.0) | 76.3 % ±3.8 (+0.0) | 76.3 % ±3.8 (+0.0) | 49.7 ±2.1 (+0.0) |
| only WiFi | 76.2 % ±0.0 (+0.0) | 75.9 % ±0.1 (+0.0) | 5.7 ±0.7 (+0.0) | 76.8 % ±2.3 (+0.0) | 76.6 % ±2.3 (+0.0) | 54.1 ±4.8 (+0.0) |
| only 5G | 83.7 % ±1.9 (+0.0) | 80.3 % ±2.1 (+0.0) | 38.7 ±1.6 (+0.0) | 81.0 % ±0.7 (+0.0) | 80.6 % ±0.7 (+0.0) | 99.8 ±4.8 (+0.0) |

### Switching and where the cars were

| Policy | Handovers / car | Ping-pongs (all cars) | Switch gap ms | On DSRC | On WiFi | On 5G |
|---|---|---|---|---|---|---|
| CoveragePriority | 2.51 ±0.37 (+0.00) | 3.7 ±2.5 (+0.0) | 25.3 ±22.7 (+0.0) | 73.2 % ±0.6 (+0.0) | 7.7 % ±1.1 (+0.0) | 19.1 % ±1.5 (+0.0) |
| Sinr | 2.69 ±0.22 (+0.00) | 0.0 (+0.0) | 15.2 ±4.6 (+0.0) | 23.4 % ±0.2 (+0.0) | 42.0 % ±0.2 (+0.0) | 34.6 % ±0.2 (+0.0) |
| LatencyQos | 2.29 ±0.06 (+0.00) | 0.3 ±0.6 (+0.0) | 24.7 ±6.9 (+0.0) | 48.7 % ±5.8 (+0.0) | 5.9 % ±1.4 (+0.0) | 45.4 % ±7.3 (+0.0) |
| Load | 2.86 ±1.68 (+0.00) | 8.3 ±13.6 (+0.0) | 33.1 ±33.5 (+0.0) | 43.4 % ±8.1 (+0.0) | 40.3 % ±3.4 (+0.0) | 16.4 % ±6.4 (+0.0) |
| Ensemble | 2.22 ±0.07 (+0.00) | 0.0 (+0.0) | 55.7 ±51.4 (+0.0) | 58.9 % ±4.0 (+0.0) | 7.4 % ±3.9 (+0.0) | 33.8 % ±0.4 (+0.0) |
| *baselines* | | | | | | |
| only DSRC | 0.00 (+0.00) | 0.0 (+0.0) | – | 100.0 % (+0.0) | 0.0 % (+0.0) | 0.0 % (+0.0) |
| only WiFi | 0.00 (+0.00) | 0.0 (+0.0) | – | 0.0 % (+0.0) | 100.0 % (+0.0) | 0.0 % (+0.0) |
| only 5G | 0.00 (+0.00) | 0.0 (+0.0) | – | 0.0 % (+0.0) | 0.0 % (+0.0) | 100.0 % (+0.0) |
