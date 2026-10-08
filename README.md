# Braess City

Can closing a road make a whole city faster? This repository holds the traffic model, the code that closed every
road in five research road networks one at a time, the search that closed several together, and **every run log**.

It is the experiment behind the Tensor108 video *I Tried to Speed Up a City by Closing Its Roads*.

- Model: static user equilibrium (every driver takes a fastest route; BPR travel times), solved with conjugate
  Frank-Wolfe, written from scratch in Python + numba (`sim/`). Checked against the published solutions:
  Anaheim total travel time within 0.00005 %, Chicago-Sketch within 0.00031 % (`tools/validate.py`).
- 11,960 traffic equilibria were computed, about 5.4 hours of scanning on one PC (Ryzen 7 5700G).
- The rule for counting a road was written down **before** the runs (`docs/EXPERIMENT_LOG.md`, 2026-10-06):
  a road counts only if closing it lowers the total travel time of all modelled trips by more than 0.01 %, and it
  still does when re-solved 100 times more precisely (relative gap 1e-7, then 1e-9). No run was dropped.

## Results

From `runs/summary_cities.txt` and `results/numbers.json`:

| Network | Roads tested | Closing it helps | Share | Best closure | Worst closure |
|---|---|---|---|---|---|
| Anaheim (1992) | 542 | 21 | 3.87 % | −0.210 % | +21.87 % |
| Barcelona | 1,498 | 16 | 1.07 % | −0.109 % | +99.71 % |
| Eastern Massachusetts (highways) | 121 | 1 | 0.83 % | −0.485 % | +12.35 % |
| Chicago (sketch) | 1,076 | 1 | 0.09 % | −0.020 % | +3.80 % |
| Winnipeg | 1,303 | 0 | 0 % | (−0.008 %, below the rule) | +10.03 % |

- The paradox shows up in 4 of 5 networks, never in more than 3.9 % of the roads, and the effects are small: the
  best single closure in Anaheim saves each trip about 1.7 seconds.
- Closing roads together (Anaheim, greedy: close the road that helps most, re-solve the city, repeat) stopped after
  12 roads at −0.601 % (about 4.9 seconds per trip, 2.9 times the best single road). Closed one at a time, the same
  12 roads add up to −0.671 %: they affect each other. Road 112↔196 saves 0.00117 % alone but 0.0421 % after four
  other closures (36 times as much). The greedy search is not guaranteed to find the best set.
- The power cut on 2026-10-06 stopped the greedy run during step 4; it resumed from the saved step 3 with the
  same total (`runs/greedy_Anaheim_twoway_log_part1.txt`, `_part2.txt`, `runs/power_cut_receipt.txt`).

## Limits

- A model of average traffic (fixed demand, static equilibrium), not real drivers. The networks are research test
  networks (Anaheim is from 1992), not a sample of the world's cities.
- Driving time is the only thing measured here. A road that slows the model down may still be needed for
  emergencies, buses or access.
- Chicago-Sketch's own notes say its demand gives unrealistically low congestion; it was used as published (no
  demand was scaled or tuned anywhere).

## Run it

```
pip install -r requirements.txt
python tools/fetch_data.py                    # downloads the networks (pinned commit) and checks their sha256
python tools/validate.py                      # solver vs the published solutions
python tools/scan.py Anaheim --mode twoway --gap 1e-7 --workers 8     # one network (Anaheim: ~9 min on 8 cores)
python tools/greedy.py Anaheim --mode twoway  # closing roads together (resumable, about 1 h)
python tools/audit_singles.py && python tools/summary.py
python tools/video_numbers.py                 # recomputes results/numbers.json (every number in the video)
```

Running `scan.py` or `greedy.py` writes into `runs/`; move `runs/` aside first to keep these logs. Recomputing
`results/numbers.json` from these logs and freshly downloaded data reproduces all 137 entries exactly (checked
2026-10-08).

## Files

```
sim/        network loader (TNTP format) and the equilibrium solver
tools/      scan, greedy search, audit, summary, validation, the video's numbers, data download
runs/       every scan and search log (JSON + the console logs as they were written)
results/    numbers.json: every number the video uses, each with its source
docs/       EXPERIMENT_LOG.md: the experiment log, including the rules frozen before the runs
data/       MANIFEST.json (file list + sha256); the network files are downloaded, not stored here
```

## Data and licence

Road networks: Transportation Networks for Research Core Team, *Transportation Networks for Research*,
https://github.com/bstabler/TransportationNetworks (Anaheim 1992 data by Jeff Ban and Ray Jayakrishnan; Chicago-Sketch
by the Chicago Area Transportation Study). Their terms: "Data sets are for academic research purposes only." They
are therefore not copied here; `tools/fetch_data.py` downloads them.

Code: MIT (see `LICENSE`). The run logs and results may be reused with attribution to Tensor108.
