"""Audit for the video: re-solve each of the 12 Level-4 roads closed ALONE at the verify gap (1e-9), so the
"alone" numbers and their sum come from the same precision as the greedy result (not from the 1e-7 screen).
Output: runs/audit_greedy_singles.json"""
import os
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import network
from tools import scan


def main():
    t0 = time.time()
    g = json.load(open(ROOT / "runs" / "greedy_Anaheim_twoway.json"))
    sc = json.load(open(ROOT / "runs" / "scan_Anaheim_twoway.json"))
    gap = g["rules"]["verify"]
    units = dict(scan.road_units(network.load("Anaheim"), g["mode"]))
    base = g["start_tstt"]                       # full network at the same verify gap (greedy start)
    out = scan.run_pool("Anaheim", 8, [(lab, units[lab], gap) for lab in g["chosen"]])
    screen = {r["road"]: r["change"] for r in sc["results"]}
    rows = []
    for lab in g["chosen"]:
        ok, tstt, gp, it = out[lab]
        rows.append({"road": lab, "change_alone": (tstt - base) / base, "gap": gp, "iters": it,
                     "screen_change": screen[lab]})
        print(f"{lab:>10}  alone {rows[-1]['change_alone'] * 100:+.5f}%  (screen {screen[lab] * 100:+.5f}%)  gap {gp:.1e}")
    total = sum(r["change_alone"] for r in rows)
    json.dump({"gap": gap, "base_tstt": base, "rows": rows, "sum_alone": total,
               "greedy_total": g["final_tstt"] / g["start_tstt"] - 1, "seconds": time.time() - t0},
              open(ROOT / "runs" / "audit_greedy_singles.json", "w"), indent=1)
    print(f"sum alone {total * 100:+.4f}%  vs together {(g['final_tstt'] / g['start_tstt'] - 1) * 100:+.4f}%  "
          f"({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
