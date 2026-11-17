# Test bench: 20261117T101058Z-standard

Sim time 120s, seeds ['0', '1', '2'], image multiratvanet:latest (commit 502870fd64).

Values are the mean over the seeds, ± the standard deviation across seeds. Safety is judged at the server (100 ms deadline), infotainment at the car (1 s from the request). Switch gap: first request sent on the new RAT until the first one that arrives. On DSRC/WiFi/5G: share of the time a car was attached to a RAT, averaged over the cars (a car that never attached counts 0).

## highway

### Traffic

| Policy | Safety delivered | Safety on time | Safety delay ms | Infot. delivered | Infot. on time | Infot. delay ms |
|---|---|---|---|---|---|---|
| CoveragePriority | 93.2 % ±0.2 | 91.8 % ±0.2 | 10.7 ±0.9 | 91.7 % ±0.9 | 91.6 % ±1.0 | 62.6 ±4.0 |
| Sinr | 94.3 % ±0.7 | 93.0 % ±0.8 | 13.0 ±0.7 | 93.0 % ±0.7 | 92.8 % ±0.8 | 62.8 ±1.8 |
| LatencyQos | 93.4 % ±2.3 | 92.3 % ±2.7 | 13.1 ±3.5 | 92.1 % ±2.6 | 92.0 % ±2.6 | 63.4 ±6.3 |
| Load | 94.4 % ±2.4 | 93.4 % ±3.1 | 7.5 ±4.7 | 93.9 % ±2.2 | 93.9 % ±2.2 | 55.4 ±5.7 |
| Ensemble | 92.2 % ±0.5 | 91.0 % ±0.5 | 12.2 ±0.5 | 90.1 % ±1.5 | 90.0 % ±1.5 | 63.1 ±0.8 |
| *baselines* | | | | | | |
| only DSRC | 74.0 % ±4.6 | 74.0 % ±4.6 | 1.1 ±0.1 | 76.3 % ±3.8 | 76.3 % ±3.8 | 49.7 ±2.1 |
| only WiFi | 76.2 % ±0.0 | 75.9 % ±0.1 | 5.7 ±0.7 | 76.8 % ±2.3 | 76.6 % ±2.3 | 54.1 ±4.8 |
| only 5G | 83.7 % ±1.9 | 80.3 % ±2.1 | 38.7 ±1.6 | 81.0 % ±0.7 | 80.6 % ±0.7 | 99.8 ±4.8 |

### Switching and where the cars were

| Policy | Handovers / car | Ping-pongs (all cars) | Switch gap ms | On DSRC | On WiFi | On 5G |
|---|---|---|---|---|---|---|
| CoveragePriority | 2.51 ±0.37 | 3.7 ±2.5 | 25.3 ±22.7 | 73.2 % ±0.6 | 7.7 % ±1.1 | 19.1 % ±1.5 |
| Sinr | 2.69 ±0.22 | 0.0 | 15.2 ±4.6 | 23.4 % ±0.2 | 42.0 % ±0.2 | 34.6 % ±0.2 |
| LatencyQos | 2.29 ±0.06 | 0.3 ±0.6 | 24.7 ±6.9 | 48.7 % ±5.8 | 5.9 % ±1.4 | 45.4 % ±7.3 |
| Load | 2.86 ±1.68 | 8.3 ±13.6 | 33.1 ±33.5 | 43.4 % ±8.1 | 40.3 % ±3.4 | 16.4 % ±6.4 |
| Ensemble | 2.22 ±0.07 | 0.0 | 55.7 ±51.4 | 58.9 % ±4.0 | 7.4 % ±3.9 | 33.8 % ±0.4 |
| *baselines* | | | | | | |
| only DSRC | 0.00 | 0.0 | – | 100.0 % | 0.0 % | 0.0 % |
| only WiFi | 0.00 | 0.0 | – | 0.0 % | 100.0 % | 0.0 % |
| only 5G | 0.00 | 0.0 | – | 0.0 % | 0.0 % | 100.0 % |
