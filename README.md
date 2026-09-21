# Freshness-Aware Port Observability

Model, experiments and figures for a temporal-graph approach to the observability of a
port water area that accounts for the freshness of data at the decision point.

**Related manuscript.** *Freshness-aware temporal-graph observability for resilient
environmental monitoring in smart and green ports* (in preparation). A link to the
published version will be added here once available.

---

## What the model does

Environmental monitoring in a port relies on heterogeneous, partly mobile sensing
infrastructure: fixed water-quality buoys, shore gateways, service vessels, unmanned
aerial vehicles, and workers carrying radios and ultra-wideband badges. Classical
observability theory assumes that the set of measurements is given a priori and says
nothing about whether those measurements reach the decision point in time. During an
incident this matters, because the event that causes pollution may simultaneously
disable sensors, gateways or communication links.

The observing infrastructure is represented as a **directed temporal graph with non-zero
link latency**. For every zone and every time step the model determines whether a
measurement has reached the control centre along a **time-respecting path**, how old that
measurement is, and how reliable its source was. From this it derives:

* **Δ-observability** of a zone — the age of the freshest delivered measurement does not
  exceed the admissible information age set for that zone;
* **the observability index O(t)** — the risk-weighted share of zones observed in time and
  with sufficient source reliability;
* **node criticality χ(v)** — the drop in the mean index when a participant is removed.

Three baseline methods are implemented for comparison: instantaneous snapshot
connectivity, a static aggregated graph, and temporal reachability without freshness or
reliability weighting.

## Selected results

Configurations: **A** — fixed infrastructure only; **B** — A plus vessels; **C** — all
participants, including workers and the unmanned aerial vehicle.

| Result | Value |
|---|---|
| Mean index over the accident interval (60–115 min) | 0.192 (A) / 0.280 (B) / 0.398 (C) |
| Time a critical zone is not Δ-observable, control run vs main scenario | 60 / 60 min for A and B; 25 / 45 min for C |
| Overestimate by the static aggregated graph | 0.084 on average, up to 0.215 at 100 min |
| Overestimate when data freshness is ignored | 0.238 |
| Interaction of node failures and link degradation | 0.109 (B), 0.082 (C), exactly zero for A |
| Runtime per step for a 250-node network | 1119 ms, i.e. 0.37 % of the real-time budget |

The static aggregated graph overstates observability because of **islands of observers**:
groups of participants holding fresh measurements that have no time-respecting path to
the control centre.

## Repository layout

```
model/            the model and the computational experiments
  model2.py         directed links, latency, earliest arrival, index, criticality
  experiments.py    regenerates every published table and check
  counterexample.py stationary network where the static graph overstates the index
figures/          generated figures, 600 dpi
  sources/          scripts that build them
results/          generated CSV files behind the published tables
```

## Requirements

* Python 3.9 or newer — the model itself uses the **standard library only**
* Matplotlib (figures only): `pip install matplotlib`

No configuration, no external data files.

## Reproducing the results

```bash
python model/model2.py           # main results, detection delays, criticality
python model/experiments.py      # all result tables and the buffer-size check
python model/counterexample.py   # stationary network counterexample

python figures/sources/fig1.py      # conceptual scheme
python figures/sources/figs.py      # graph snapshots and index dynamics
python figures/sources/figures2.py  # ablation, sensitivity, scalability, criticality
```

`experiments.py` writes ten CSV files to `results/`: ablation of the baseline methods,
separation of the freshness and reliability contributions, the static-graph gap, the
factorial failure analysis, two sensitivity studies, the control run, the buffer-size
statistics, the spatial-quantization check and the scalability test.

### Determinism

The model is fully deterministic: no random number generation, no external data, no
wall-clock dependence. The only random component is the generator of the synthetic
networks used in the scalability test, and it uses a fixed seed of zero. Any run on any
machine yields identical values; only the timings differ.
The file `results/scalability.csv` holds the timings reported in Table 10 of the paper;
re-running `model/experiments.py` overwrites it with timings from your own machine, which
will differ, while all edge counts and every other result stay identical.

### Control run

The control run disables the node failures (gateway R1 and buoy S1) and the link
degradation, while keeping the spill, its spread and the worker evacuation, which are
defined by routes rather than by flags:

```python
from model2 import FLAGS
FLAGS.update(jam=False, destroy=False)
```

With this setting the time during which at least one critical zone (Z1, Z2) is not
Δ-observable over 60–115 min is 60 min for configurations A and B and 25 min for C,
against 60, 60 and 45 min in the main scenario.

### Measured buffer statistics

Maximum size of the pair set for one buffer key: **P = 3**. Maximum number of distinct
departure times per vertex: **D = 6**. Both are taken over all operations of a step, not
only after buffer compaction.

### Environment used for the reported timings

CPython 3.12.3 on an x86-64 Linux host, identified in the virtualised environment as
Intel Xeon Processor @ 2.10 GHz. No parallelisation, no optimisation of data structures.

## The scenario

An accident during a storm at an oil terminal. In the manuscript the parameters are
grouped by origin into technical, operational and conventional; the conventional ones
are covered by the sensitivity analysis.

**Water area.** 2 × 1.5 km, split into 12 zones of 0.5 × 0.5 km. Zones Z1 and Z2 next to
the terminal carry risk weight *w* = 3 and an admissible data age of 10 min; Z5, Z6 and
the fairway zones Z10, Z11 carry *w* = 2 and 20 min; the rest carry *w* = 1 and 30 min.

**Participants (15).** Control centre CC and shore gateways R1, R2 (wired to CC); buoys
S1–S6 with LoRaWAN in zones Z1, Z3, Z6, Z8, Z10, Z12; tanker V1 at the berth, leaving at
120 min and clearing the area at 150 min; port service vessel V2 with an onboard sensor
and a LoRaWAN gateway, heading for the terminal at 70 min and deploying booms from
100 min; unmanned aerial vehicle D1, airborne from 90 to 170 min; workers W1–W3 with
portable radios and visual observation of the nearby zones.

**Events.** At 60 min a pipeline ruptures at the berth and oil enters zone Z1. The
terminal section is de-energised, so gateway R1 goes down; buoy S1 is torn from its
mooring by the storm. The slick advances one zone every 15 min and is contained by booms
two zones out. From 60 to 120 min link conditions are degraded (κ = 0.5). Workers W1 and
W2 are evacuated from 65 min and return at 100 and 105 min.

Time step δ = 5 min, horizon 180 min.

## Licences

The figures and result files are licensed under **CC BY 4.0** (`LICENSE-TEXT`); the
source code is licensed under the **MIT License** (`LICENSE-CODE`).
