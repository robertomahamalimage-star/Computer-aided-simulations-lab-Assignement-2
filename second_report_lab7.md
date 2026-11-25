# Lab 7 second report – Event scheduling and capacity in the mall simulator

Which expansion helps most on a busy Saturday depends on what the mall wants to improve. In the simulation, adding parking admitted the most visitors. Adding dining tables shortened visits the most because every diner who found a seat also freed an ordering counter.

## I. How the simulator works

The mall opens empty at noon. One visitor arrives in one vehicle and holds a parking stall until payment at the exit. The hourly Poisson arrival rates from noon to 18:00 are 35, 60, 90, 105, 75 and 45 vehicles per hour. Visitors go first to the supermarket (40%), specialty shops (35%) or food court (25%). Shoppers can eat afterward. A gallery visitor can visit both shops, which increases the chance of dining.

| Data structure | What it represents |
| --- | --- |
| `Visit` and `Stop` | An immutable plan records arrival time, a sequence of destinations, walking and service durations for each stop, and meal duration. Generating plans before the run lets all scenarios face the same visitors. |
| `_Visitor` | Each run creates a fresh record for each visitor. It points to the plan, tracks the current stop and records when the current wait began. |
| `_Resource` | A dictionary maps each area to its capacity, occupied count, first-in, first-out (FIFO) queue and accumulated busy and full minutes. A Python `deque` serves the oldest waiting visitor first. The parking queue holds vehicles outside. The table queue holds diners who still occupy counters. |
| Future event set (FES) | A `heapq` min-heap stores pending events. Each entry contains the event time, an external-arrival flag, an insertion number, the handler to call and the visitor involved. |

**Event scheduling.** The run begins with all external arrivals on the FES. The scheduler removes the earliest event, advances the clock to its time and executes its handler. When a walk ends, a visitor can start service immediately or wait in the resource's queue. A queued visitor's service completion is scheduled only when a server becomes available and service begins. If timestamps coincide, internal events run before external arrivals, then insertion order breaks ties within each group. A payment completion can therefore release a stall in time for a vehicle arriving at that same instant. [Simulator implementation](lab6/model.py)

**How blocking propagates.** Consider three diners arriving together at one counter and one table. Orders take one minute and meals take five. The first diner sits at minute 1. The second finishes ordering at minute 2 and holds the counter until minute 6. At minute 6 a single meal-completion event seats the second diner, releases the counter and starts the third order. The third diner has waited six minutes for one minute of preparation. The regression suite checks this sequence and the resulting waiting times. [Executable blocking example](lab6/test_model.py)

**Measurement.** Before each event changes the state, the simulator multiplies the previous occupancy by the elapsed time. Dividing accumulated occupied minutes by installed capacity × 360 minutes gives opening-hours utilization. Dividing minutes spent at capacity by 360 gives the fraction of opening time full. External arrivals stop at 18:00, and the scheduler continues until everyone waiting or inside has left. Total sojourn covers exterior arrival through gate completion, including visits that finish after closing.

## II. Scenario results and interpretation

The baseline has 72 parking stalls, 12 exterior waiting places, four ordering counters and 12 tables. A vehicle leaves if the lot and exterior queue are both full. Each alternative changes one capacity. The experiment uses 60 independently generated days, replays each day under all four configurations and gives each day equal weight. Brackets show pointwise 95% confidence intervals from 2,000 bootstrap resamples of whole days. For comparisons, each day's baseline is subtracted before resampling. [Experiment and interval calculation](lab6/__main__.py)

| Daily metric | Baseline | 108 parking stalls | 6 ordering counters | 24 dining tables |
| --- | ---: | ---: | ---: | ---: |
| Completed visits per day | 379.92 [375.65, 384.07] | 410.93 [406.55, 415.48] | 380.47 [376.30, 384.55] | 405.42 [401.70, 409.20] |
| Turned away (% of arrivals) | 7.66 [6.59, 8.78] | 0.23 [0.05, 0.46] | 7.53 [6.47, 8.63] | 1.53 [1.07, 2.03] |
| Total sojourn (min/visitor) | 60.59 [59.50, 61.60] | 64.92 [63.24, 66.58] | 60.33 [59.21, 61.41] | 46.33 [45.98, 46.67] |
| Queue before ordering (min/diner) | 24.17 [22.87, 25.37] | 37.44 [34.65, 40.29] | 20.66 [19.32, 21.89] | 0.66 [0.57, 0.78] |
| Parking full (% of open time) | 40.29 [38.18, 42.31] | 4.76 [2.41, 7.26] | 39.96 [37.72, 42.21] | 19.20 [16.87, 21.61] |
| Tables full (% of open time) | 64.68 [63.50, 65.83] | 64.77 [63.56, 65.93] | 67.44 [66.25, 68.60] | 1.28 [0.89, 1.69] |

**Baseline.** Counters were occupied for 76.18% of available counter-minutes. Waiting for tables accounted for 30.97% of all available counter-minutes, leaving about 45.21% for preparing orders. This distinction explains how the queue before ordering could average 24.17 minutes per diner even with spare counter capacity at quieter times.

**More parking.** The larger lot nearly eliminated turnaways. With more people inside and the same food court, the wait before ordering grew by 13.27 minutes per diner [11.48, 15.02]. Mean time from exterior arrival to exit increased by 4.33 minutes [3.52, 5.16] across completed visits. The two scenarios admitted different sets of visitors, so this difference describes the experience of those admitted under each policy.

**More counters.** The pre-order wait fell by 3.51 minutes per diner [3.21, 3.82], and diners spent 3.00 additional minutes holding a counter after ordering [2.94, 3.05]. Extra counters moved much of the wait to the other side of order completion. The paired change in turnaways was −0.13 percentage points [−0.27, 0.01], an interval that includes zero.

**More tables.** Doubling seating reduced blocked counter time to 0.16% of available counter-minutes. With faster access to both a counter and a table, the mean visit shortened by 14.26 minutes [13.32, 15.10]. Earlier departures also released parking stalls sooner, reducing turnaways by 6.13 percentage points [5.25, 6.99]. These estimates use illustrative Saturday demand, one visitor per car and one table per diner. The intervals describe simulation variability under those assumptions. [All 19 metrics and paired changes](lab6/results.md) · [Scenario comparison figure](lab6/scenario-comparison.png)

To reproduce the estimates and run the mall validation tests from the repository root, use Python 3.10 or newer.

```sh
python3 -B -m lab6 --days 60 --seed 2026
python3 -B -m unittest -v lab6.test_model
```
