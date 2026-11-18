# Test bench: 20261117T105944Z-standard

Sim time 120s, seeds ['0', '1', '2'], image multiratvanet:latest (commit d55ae08c33).

Values are the mean over the seeds, ± the standard deviation across seeds. Safety is judged at the server (100 ms deadline), infotainment at the car (1 s from the request).

Latency: mean end-to-end delay of the packets that arrived. PDR: share of packets delivered; packet loss = 1 - PDR. Throughput: data delivered per second, all cars together. Handovers / car-min: RAT switches of that traffic per car and minute attached. Interruption: after a switch, first packet sent on the new RAT until the first one arrives. Ping-pong rate: share of switches back to the previous RAT within 2 s. Network availability: share of the time a car had a usable RAT. On DSRC/WiFi/5G: share of the time a car was attached to a RAT, averaged over the cars.

## highway

### Safety

| Policy | Latency ms | PDR | Throughput Mbit/s | Packet loss | Handovers / car-min | Interruption ms | On time |
|---|---|---|---|---|---|---|---|
| CoveragePriority | 10.7 ±0.9 | 93.2 % ±0.2 | 0.190 ±0.000 | 6.8 % ±0.2 | 1.69 ±0.25 | 14.0 ±6.9 | 91.8 % ±0.2 |
| Sinr | 13.0 ±0.7 | 94.3 % ±0.7 | 0.192 ±0.002 | 5.7 % ±0.7 | 1.80 ±0.15 | 12.4 ±4.5 | 93.0 % ±0.8 |
| LatencyQos | 13.1 ±3.5 | 93.4 % ±2.3 | 0.190 ±0.005 | 6.6 % ±2.3 | 1.54 ±0.04 | 35.0 ±10.5 | 92.3 % ±2.7 |
| Load | 7.5 ±4.7 | 94.4 % ±2.4 | 0.192 ±0.005 | 5.6 % ±2.4 | 1.92 ±1.13 | 19.4 ±2.0 | 93.4 % ±3.1 |
| Ensemble | 12.2 ±0.5 | 92.2 % ±0.5 | 0.188 ±0.001 | 7.8 % ±0.5 | 1.49 ±0.04 | 36.1 ±21.9 | 91.0 % ±0.5 |
| *baselines* | | | | | | | |
| only DSRC | 1.1 ±0.1 | 74.0 % ±4.6 | 0.151 ±0.009 | 26.0 % ±4.6 | 0.00 | – | 74.0 % ±4.6 |
| only WiFi | 5.7 ±0.7 | 76.2 % ±0.0 | 0.155 ±0.000 | 23.8 % ±0.0 | 0.00 | – | 75.9 % ±0.1 |
| only 5G | 38.7 ±1.6 | 83.7 % ±1.9 | 0.170 ±0.004 | 16.3 % ±1.9 | 0.00 | – | 80.3 % ±2.1 |

### Infotainment

| Policy | Latency ms | PDR | Throughput Mbit/s | Packet loss | Handovers / car-min | Interruption ms | On time |
|---|---|---|---|---|---|---|---|
| CoveragePriority | 62.6 ±4.0 | 91.7 % ±0.9 | 5.006 ±0.150 | 8.3 % ±0.9 | 1.69 ±0.25 | 38.4 ±48.2 | 91.6 % ±1.0 |
| Sinr | 62.8 ±1.8 | 93.0 % ±0.7 | 4.968 ±0.218 | 7.0 % ±0.7 | 1.80 ±0.15 | 18.1 ±5.7 | 92.8 % ±0.8 |
| LatencyQos | 63.4 ±6.3 | 92.1 % ±2.6 | 4.939 ±0.309 | 7.9 % ±2.6 | 1.54 ±0.04 | 13.4 ±4.3 | 92.0 % ±2.6 |
| Load | 55.4 ±5.7 | 93.9 % ±2.2 | 4.907 ±0.486 | 6.1 % ±2.2 | 1.92 ±1.13 | 49.3 ±74.3 | 93.9 % ±2.2 |
| Ensemble | 63.1 ±0.8 | 90.1 % ±1.5 | 4.798 ±0.110 | 9.9 % ±1.5 | 1.49 ±0.04 | 76.3 ±89.5 | 90.0 % ±1.5 |
| *baselines* | | | | | | | |
| only DSRC | 49.7 ±2.1 | 76.3 % ±3.8 | 4.150 ±0.256 | 23.7 % ±3.8 | 0.00 | – | 76.3 % ±3.8 |
| only WiFi | 54.1 ±4.8 | 76.8 % ±2.3 | 4.204 ±0.133 | 23.2 % ±2.3 | 0.00 | – | 76.6 % ±2.3 |
| only 5G | 99.8 ±4.8 | 81.0 % ±0.7 | 4.512 ±0.202 | 19.0 % ±0.7 | 0.00 | – | 80.6 % ±0.7 |

### Per car: ping-pongs, availability, where the cars were

| Policy | Ping-pong rate | Network availability | Handovers / car | Ping-pongs (all cars) | On DSRC | On WiFi | On 5G |
|---|---|---|---|---|---|---|---|
| CoveragePriority | 8.3 % ±5.0 | 92.8 % ±1.3 | 2.51 ±0.37 | 3.7 ±2.5 | 73.2 % ±0.6 | 7.7 % ±1.1 | 19.1 % ±1.5 |
| Sinr | 0.0 % | 92.2 % ±0.4 | 2.69 ±0.22 | 0.0 | 23.4 % ±0.2 | 42.0 % ±0.2 | 34.6 % ±0.2 |
| LatencyQos | 0.9 % ±1.5 | 93.2 % ±2.4 | 2.29 ±0.06 | 0.3 ±0.6 | 48.7 % ±5.8 | 5.9 % ±1.4 | 45.4 % ±7.3 |
| Load | 10.8 % ±16.4 | 94.2 % ±3.3 | 2.86 ±1.68 | 8.3 ±13.6 | 43.4 % ±8.1 | 40.3 % ±3.4 | 16.4 % ±6.4 |
| Ensemble | 0.0 % | 92.0 % ±0.4 | 2.22 ±0.07 | 0.0 | 58.9 % ±4.0 | 7.4 % ±3.9 | 33.8 % ±0.4 |
| *baselines* | | | | | | | |
| only DSRC | – | 92.9 % ±1.1 | 0.00 | 0.0 | 100.0 % | 0.0 % | 0.0 % |
| only WiFi | – | 93.2 % ±1.9 | 0.00 | 0.0 | 0.0 % | 100.0 % | 0.0 % |
| only 5G | – | 92.7 % ±0.7 | 0.00 | 0.0 | 0.0 % | 0.0 % | 100.0 % |
