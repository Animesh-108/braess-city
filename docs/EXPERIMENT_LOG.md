# Braess City: production log

Working title: "I Tried to Speed Up a City by Closing Its Roads" (title follows the results).
Question: how common is the Braess paradox in real road networks, and can my PC find the roads whose closure makes
the whole city faster? Seoul (2003 highway removal) is a mention only, not the proof.

## Frozen rules (2026-10-06, from user's relayed review + Claude)
- Level 1: toy Braess network, exact known answer (validation).
- Levels 2-3: public research networks with published demand and a published best-known solution to match.
- Level 5 (optional finale): OpenStreetMap roads + estimated demand, labeled "model experiment", never a
  prediction or a recommendation for a real city.
- On screen: "a standard traffic model where route choices respond to travel time"; exact model in description.
- Counters show only numbers from our own runs.
- Solver precision: a closure counts only if its improvement is far above solver noise and survives a re-solve
  at 100x tighter gap.
- Headline metric: total travel time (vehicle-hours, congested time only). Route choice uses each network's
  generalized cost (Chicago: time + 0.02 min/cent toll + 0.04 min/mile, from its README).

## Phase 0: pilot (2026-10-06)
Data: `data/` from github.com/bstabler/TransportationNetworks (Braess-Example, SiouxFalls, Anaheim,
Chicago-Sketch, Eastern-Massachusetts). Sioux Falls README: "not considered as a realistic one" → debugging only.
Code: `sim/network.py` (TNTP loader), `sim/assign.py` (user equilibrium, conjugate Frank-Wolfe, numba),
`tools/validate.py`, `tools/scan.py`.

Validation (gate 1) ✅
- Braess toy: 83.0000 per driver without the shortcut, 92.0000 with it (textbook 83 → 92).
- Anaheim (914 links, 38 zones, 1992 data): gap 9.4e-9 in 6 s; total travel time within 4.8e-7 of published.
- Chicago-Sketch (2,950 links, 387 zones): gap 1e-6 in 16 s; within 3.1e-6 of published, every link flow within
  2.6 vehicles. (First mismatch of 3.4e-4 was the missing generalized cost, fixed.)
- Sioux Falls: conjugate Frank-Wolfe stalls at gap ~1.7e-6 (known hard case); not used for results.
- Chicago demand: 1,260,907 trips in file, 123,414 are intrazonal (never use a road) → 1,137,493 assigned.

Pilot scan (gate 2) ✅ `runs/scan_Anaheim_directed_pilot.json` (+ `_log.txt`) (626 s, 8 workers)
- Anaheim: 796 road segments (directed links, 118 zone connectors skipped); 37 essential (closing cuts off
  trips); 759 solved at gap 1e-7. Solver noise ~4e-6. 31 closures cut total travel time by > 0.01% and all 31
  held when re-solved at gap 1e-9: **about 1 road segment in 25 makes Anaheim slower by existing**.
- Best: 71→255 (flow 2,420 veh/h) −0.210% ≈ 50 vehicle-hours across all modeled trips ≈ 1.7 s per trip.
  Effects are real but small; worst closures cost +21.9% (91→90) — the red/green contrast for the map.

## Pre-registered before running (2026-10-06): two-way scan + Level 4 search
Rule from the user: nothing false or fake. Data used as published; no demand or parameter tuning.
- **Two-way scan (Anaheim):** unit = a whole road = every directed link between the same two nodes (both
  directions). Same gaps (screen 1e-7, verify 1e-9) and threshold (counted only if total travel time drops by
  > 0.01% and still does at gap 1e-9). Directed results stay as a separate finding ("make it one-way").
- **Level 4 greedy search (Anaheim, whole roads):** start from the full network. Each step: close every
  remaining road one at a time on top of the closures so far (screen at 1e-7 vs the current state at 1e-7),
  re-solve the 5 best at 1e-9, accept the best only if it lowers total travel time by > 0.01% vs the current
  state at 1e-9. Stop when no road passes, or after 15 steps. Every step's full screening table is saved.
  Greedy = not guaranteed optimal; reported as "a greedy search found", never "the best possible".
- Chicago scan: same rules, run overnight (not started yet).

## Results: two-way scan + Level 4 (2026-10-06)
**Two-way scan ✅** `runs/scan_Anaheim_twoway.json` (+ `_log.txt`, 517 s): 568 whole roads; 26 essential; 542
solved. **21 roads make Anaheim slower by existing** (all 21 survived re-solve at gap 1e-9, 0 failed). That is
about 1 road in 26. Best 71↔255 −0.210%, then 193↔271 −0.145%, 200↔335 −0.106%. Worst closure +21.9% (90↔91).

**Level 4 greedy (whole roads)** `runs/greedy_Anaheim_twoway.json`
- Step 1: 71↔255 → −0.2100% vs start. Step 2: 200↔335 → −0.2974%. Step 3: 204↔376 → −0.3666%.
- Interaction seen already: 193↔271 (−0.145% alone, 2nd best) was NOT picked at step 2 — after 71↔255 closed,
  another road helped more. Closures are not independent.
- The run was cut during step 4 when the Claude session ended (13:09). Resumed with `--resume` (same rules,
  deterministic solver: recomputes the state after step 3 and continues). Logs: `_log_part1.txt`, `_log_part2.txt`.
- **Finished** (part 2: 2,643 s): steps 4-12 closed 193↔271, 112↔196, 59↔103, 108↔289, 129↔324, 367↔368,
  113↔183, 211↔408, 168↔409. Step 13: best remaining road −0.008% (54↔230) < 0.01% threshold → stop.
- **Result: a greedy search closed 12 of Anaheim's roads and total travel time fell 1,419,913.8 → 1,411,379.8
  (−0.601%)** ≈ 142 vehicle-hours across all modeled trips ≈ 4.9 s per trip (avg trip 13.6 min). 2.9x the best
  single closure (−0.210%).
- Not additive: the 12 roads' single-closure effects sum to −0.667% (computed by tools/video_numbers.py; −0.668% was my hand sum), together −0.601%.
- 2 of the 12 were NOT harmful alone: 112↔196 (−0.0008% alone, −0.042% at step 5) and 168↔409 (−0.0069% alone)
  became harmful only after other roads closed.
- Smaller gains below the pre-registered 0.01% threshold still exist; not counted.

## Pre-registered: Chicago-Sketch scan (Level 3), 2026-10-06 ~14:30
- Unit: whole roads (two-way), 1,088 roads (zone connectors skipped). Demand exactly as published (README calls it
  low congestion; NOT scaled).
- Gaps differ from Anaheim because of size (one solve at gap 1e-6 = 56 s on one core): screen 1e-6, verify 1e-7.
  Threshold unchanged: counted only if total travel time drops > 0.01% at screen AND at the verify gap. Solver
  noise measured from the base pair (1e-6 vs 1e-7) and reported next to the result.
- Power-cut safe: every finished solve is appended to `runs/scan_ChicagoSketch_twoway.partial.jsonl` (fsync); a
  rerun skips finished work (deterministic solver → identical numbers). Restart: double-click
  `run_chicago_scan.bat`. Windows sleep is blocked while it runs. Estimated 3-4 h on 8 cores.
- Launched 14:15 (first launch 14:14 died on a syntax error in the new checkpoint code before any solve; fixed,
  re-tested on the toy network incl. a simulated half-written line). First road solved and checkpointed.

## Result: Chicago-Sketch scan (Level 3) ✅ `runs/scan_ChicagoSketch_twoway.json` (+ `_log.txt`, `.partial.jsonl`)
- 10,678 s (14:15-17:12), no interruptions. 1,088 roads: 12 essential, 1,076 solved.
- Solver noise (base at gap 1e-6 vs 1e-7): 2.9e-6.
- **1 road makes Chicago slower by existing: 543↔903, −0.0199%** (screen −0.0197%, verify −0.0199%; ~70x noise).
  ≈ 61 vehicle-hours across all modeled trips ≈ 0.2 s per trip (avg trip 16.2 min). Next best −0.002% (not counted).
- Worst closure +3.80% (551↔563) — Chicago is far less fragile than Anaheim (+21.9%).
- **Anaheim 21 of 542 roads (3.9%) vs Chicago 1 of 1,076 (0.09%).**
- Correction of my provisional explanation ("Chicago has little congestion"): measured on the base equilibrium,
  Chicago is NOT less congested — mean volume/capacity on roads 0.54 vs Anaheim 0.33; roads above 0.9: 20.4% vs
  10.8%; congestion delay share of road time 11.0% vs 11.3%. So congestion level does not explain the difference.
  Cause unknown. Untested hypothesis: Chicago-Sketch is an aggregated "sketch" network (few small parallel
  streets), which may remove the shortcuts where the paradox lives. Needs its own pre-registered test.

## Pre-registered: more cities (2026-10-06 ~17:40), before any scan
Question: how common is the paradox across real networks? Same rules as Chicago: whole roads (two-way), demand
as published, screen gap 1e-6, verify gap 1e-7, threshold > 0.01% at both. Order: EMA, Barcelona, Winnipeg.
Checkpointed; restart with `run_more_cities.bat`.
- **EMA** (Eastern Massachusetts highway subnetwork, PM Apr 2012): 74 nodes = 74 zones, 258 links, no connectors
  → every link is a road (rule added to `road_units`; Anaheim/Chicago unaffected: they have centroid nodes).
  Uses the BPR cost in the published file; the README says the authors' fitted cost function (degree-8
  polynomial) differs and BPR is "for testing purposes" → label it so. No published solution → validated by
  convergence only (noise 6e-7 at gap 1e-6).
- **Barcelona** (110 zones, 1,020 nodes, 2,522 links, 1,509 roads): our total within 6.9e-6 of published.
- **Winnipeg** (147 zones, 1,052 nodes, 2,836 links, 1,315 roads): total within 4.4e-6 of published, but one
  link's flow differs by ~1,220 — being checked (non-unique flows on constant-cost links, or convergence)
  before results are used.
- The "network detail" idea from Chicago is NOT tested formally here (n = 5 networks is not a test); per-city
  network stats are reported next to the counts as description only.
- Winnipeg/Barcelona check ✅ (gap 9.4e-9): totals within 3.9e-8 (Winnipeg) and 6.7e-8 (Barcelona) of published;
  every link's travel TIME within 4.2e-6 / 6.6e-6. The big flow differences (1,221 on Winnipeg 865→866, 134 on
  Barcelona 92→1006) sit on constant-time links (b = 0: 1,176 of 2,836 Winnipeg links, 565 of 2,522 Barcelona):
  there the equilibrium flow split is not unique, while times and the total are. → validated. Per-road
  "base_flow" on such links is one valid split, not a unique number (don't show it as exact on screen).
- Scans launched ~18:25 (EMA → Barcelona → Winnipeg).

## Results: more cities ✅
- EMA: 129 roads, 8 essential, 121 solved; noise 6.0e-7; **1 harmful: 32↔60 −0.485%** (verified). Worst +12.35%.
  (BPR cost from the file = README's "testing" option; label on screen.)
- Barcelona: 1,509 roads, 11 essential, 1,498 solved; 2,370 s; **16 harmful segments** (all verified), best
  942↔944 −0.109%. Worst closure 250↔1009 +99.71% (nearly doubles total travel time).
- Winnipeg: 1,315 roads, 12 essential, 1,303 solved; 6,042 s; noise 4.1e-6; **0 harmful** (0 screened).
  Worst +10.03% (413↔415).

## Reporting refinement (added AFTER seeing Barcelona; changes no result, only how they are counted)
Barcelona's 16 include consecutive pieces of one street (563↔564↔565↔566↔567, identical −0.0176%). To avoid
double counting, every city also gets a **corridor** count, defined before computing it: build the undirected
graph of all links (connectors included, so a node where a zone attaches counts as a junction); a corridor is a
maximal chain of roads joined at nodes with exactly 2 neighbours; a corridor is harmful if it contains at least
one verified harmful road. Both counts (segments, corridors) are reported.

## Summary across 5 networks ✅ `runs/summary_cities.json` / `.txt` (`tools/summary.py`)
| network | roads solved | harmful segments | harmful corridors | share | best single | worst closure |
|---|---|---|---|---|---|---|
| Anaheim | 542 | 21 | 20 / 489 | 3.87% | −0.210% | +21.87% |
| Barcelona | 1,498 | 16 | 16 / 1,477 | 1.07% | −0.109% | +99.71% |
| Eastern Massachusetts (highways, BPR "testing" cost) | 121 | 1 | 1 / 116 | 0.83% | −0.485% | +12.35% |
| Chicago (sketch) | 1,076 | 1 | 1 / 1,070 | 0.09% | −0.020% | +3.80% |
| Winnipeg | 1,303 | 0 | 0 / 1,208 | 0% | (closest −0.008%) | +10.03% |
- Correction of my Barcelona remark: 563↔564↔…↔567 (+563↔716, 568↔569) are pieces of ONE one-way street, but
  every node on it is a junction with side streets, so by the rule they are separate corridors (16 stays 16).
  The same 312 vehicles drive the whole stretch; closing any piece diverts that one stream, hence near-identical
  effects (−0.0160% … −0.0176%). On screen: "7 of Barcelona's 16 lie along one one-way street".
- Answer to "how common?": in 4 of 5 real networks at least one road makes the network slower by existing;
  0-3.9% of roads; best single closures 0.02-0.49% of total travel time. Rare and small, but real.

## Decision (2026-10-06, user's relayed review, checked by Claude): data collection is locked
- Video = Levels 1-4 only. Level 5 (OSM + estimated demand) dropped from this video (different class of evidence);
  possible follow-up video.
- Wording rules added: "appeared in 4 of the 5 published transportation networks I tested"; "under my
  pre-registered threshold, 0-3.9% of the tested roads…"; on screen: "benchmark networks, not a random sample of
  cities". Winnipeg's −0.008% is "closest, below the threshold (not counted)", never a "best closure".
  Same threshold and unit everywhere, but Anaheim was solved tighter (1e-7/1e-9) than the others (1e-6/1e-7).
- Other caveats to show somewhere: Chicago is an aggregated "sketch" network whose drivers also weigh tolls and
  distance; EMA uses the dataset's "testing" BPR cost; data years (Anaheim 1992, Chicago trip table 1999, EMA
  2012); static model = rush-hour averages, not individual cars.
- Map data: Anaheim has real coordinates (`data/anaheim_nodes.geojson`, `anaheim.geojson`, 416 nodes / 914 links,
  lat/long) → real map. Chicago has `ChicagoSketch_node.tntp` (state-plane feet). Barcelona, Winnipeg, EMA have
  no coordinates in the dataset → show as numbers / clearly labeled schematic layouts, never as fake maps.

