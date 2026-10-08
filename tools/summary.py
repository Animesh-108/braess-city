"""One table across cities: roads tested, essential, harmful segments and corridors, best and worst closure.
Corridor = maximal chain of roads joined at nodes with exactly 2 neighbours (all links counted)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import network

CITIES = [("Anaheim", "Anaheim"), ("Barcelona", "Barcelona"), ("EMA", "Eastern Massachusetts (highways)"),
          ("ChicagoSketch", "Chicago (sketch)"), ("Winnipeg", "Winnipeg")]


def corridors(net, roads):
    nbr = {}
    for a in range(net.n_links):
        u, v = int(net.tail[a]), int(net.head[a])
        nbr.setdefault(u, set()).add(v)
        nbr.setdefault(v, set()).add(u)
    parent = {r: r for r in roads}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    by_node = {}
    for r in roads:
        u, v = (int(x) - 1 for x in r.split("<->"))
        for n in (u, v):
            by_node.setdefault(n, []).append(r)
    for n, rs in by_node.items():
        if len(nbr[n]) == 2 and len(rs) == 2:
            parent[find(rs[0])] = find(rs[1])
    return {r: find(r) for r in roads}


def main():
    rows = []
    for prefix, label in CITIES:
        d = json.load(open(ROOT / "runs" / f"scan_{prefix}_twoway.json"))
        net = network.load(prefix)
        res = d["results"]
        valid = [r for r in res if r["change"] is not None]
        harm = [r for r in res if r.get("verified_change") is not None and r["verified_change"] < -d["threshold"]]
        corr = corridors(net, [r["road"] for r in res])
        best = min(harm, key=lambda r: r["verified_change"]) if harm else None
        closest = min(valid, key=lambda r: r["change"])
        worst = max(valid, key=lambda r: r["change"])
        rows.append({"city": label, "net": prefix, "tested": len(valid), "essential": len(res) - len(valid),
                     "harmful_segments": len(harm), "harmful_corridors": len({corr[r["road"]] for r in harm}),
                     "corridors_tested": len({corr[r["road"]] for r in valid}),
                     "best": best and (best["road"], best["verified_change"]),
                     "closest_below_threshold": None if best else (closest["road"], closest["change"]),
                     "worst": (worst["road"], worst["change"]), "gap": d["gap"], "verify": d["verify"],
                     "trips": float(net.demand.sum()), "nodes": net.n_nodes, "links": net.n_links,
                     "zones": net.n_zones})
    json.dump(rows, open(ROOT / "runs" / "summary_cities.json", "w"), indent=1)
    print(f"{'city':34} {'tested':>6} {'harmful seg':>11} {'corridors':>13} {'share':>6}  {'best':>9}  {'worst':>8}")
    for r in rows:
        best = f"{r['best'][1] * 100:+.3f}%" if r["best"] else f"({r['closest_below_threshold'][1] * 100:+.4f}%)"
        print(f"{r['city']:34} {r['tested']:6d} {r['harmful_segments']:11d} {r['harmful_corridors']:5d} / {r['corridors_tested']:<5d}"
              f" {r['harmful_segments'] / r['tested'] * 100:5.2f}%  {best:>9}  {r['worst'][1] * 100:+7.2f}%")


if __name__ == "__main__":
    main()
