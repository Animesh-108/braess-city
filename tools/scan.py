"""Close each road one at a time, re-solve the equilibrium, record the change in total travel time.
Units: --mode directed (one direction of a road segment = "make it one-way") or --mode twoway (whole road, both
directions). Zone connectors are not roads and are skipped; closures that cut off any trip are 'essential'.
Every closure that beats --threshold at the screening gap is re-solved at --verify before it counts.
Usage: python tools/scan.py Anaheim --mode twoway --gap 1e-7 --workers 8"""
import os
os.environ.setdefault("NUMBA_NUM_THREADS", "1")       # one thread per worker process
import argparse, json, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import network, assign

NET = None


def init(prefix):
    global NET
    NET = network.load(prefix)


def solve_closed(job):
    """job = (key, links to close, gap) -> (key, reachable, tstt, gap reached, iterations)."""
    key, links, gap = job
    closed = np.zeros(NET.n_links, bool)
    closed[list(links)] = True
    r = assign.solve(NET, closed, gap=gap, max_iter=200000)
    return key, r.reachable, r.tstt, r.gap, r.iters


def road_units(net, mode):
    """List of (label, [link ids]) for every road (no zone connectors)."""
    if net.n_zones == net.n_nodes:          # every node is a junction and a zone (EMA): no connectors exist
        roads = list(range(net.n_links))
    else:                                   # links touching a zone centroid are connectors, not roads
        roads = [a for a in range(net.n_links) if net.tail[a] >= net.n_zones and net.head[a] >= net.n_zones]
    if mode == "directed":
        return [(f"{net.tail[a] + 1}->{net.head[a] + 1}", [a]) for a in roads]
    groups = {}
    for a in roads:
        u, v = sorted((int(net.tail[a]), int(net.head[a])))
        groups.setdefault((u, v), []).append(a)
    return [(f"{u + 1}<->{v + 1}", links) for (u, v), links in sorted(groups.items())]


def run_pool(prefix, workers, jobs, on_result=None):
    out = {}
    if not jobs:
        return out
    with Pool(workers, initializer=init, initargs=(prefix,)) as pool:
        for i, (key, ok, tstt, gap, iters) in enumerate(pool.imap_unordered(solve_closed, jobs, chunksize=1)):
            out[key] = (ok, tstt, gap, iters)
            if on_result:
                on_result(key, ok, tstt, gap, iters)
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(jobs)}", flush=True)
    return out


class Checkpoint:
    """Append-only log of finished solves (survives power cuts); a rerun skips what is already done."""
    def __init__(self, path):
        self.path = path
        self.done = {}
        if path.exists():
            text = path.read_text()
            if text and not text.endswith("\n"):     # power cut mid-line: start the next record on a new line
                with open(path, "a") as f:
                    f.write("\n")
            for line in text.splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:          # half-written last line from a power cut
                    continue
                self.done[(r["phase"], r["key"])] = (r["ok"], r["tstt"], r["gap"], r["iters"])

    def writer(self, phase):
        def write(key, ok, tstt, gap, iters):
            self.done[(phase, key)] = (ok, tstt, gap, iters)
            with open(self.path, "a") as f:
                f.write(json.dumps({"phase": phase, "key": key, "ok": bool(ok), "tstt": float(tstt), "gap": float(gap),
                                    "iters": int(iters)}) + "\n")
                f.flush()
                os.fsync(f.fileno())
        return write

    def run(self, prefix, workers, phase, jobs):
        todo = [j for j in jobs if (phase, j[0]) not in self.done]
        if len(todo) < len(jobs):
            print(f"  {phase}: {len(jobs) - len(todo)} already done, {len(todo)} to go", flush=True)
        run_pool(prefix, workers, todo, self.writer(phase))
        return {j[0]: self.done[(phase, j[0])] for j in jobs}


def keep_awake():
    """Ask Windows not to sleep while this process runs (released automatically when it exits)."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("net")
    ap.add_argument("--mode", choices=["directed", "twoway"], default="directed")
    ap.add_argument("--gap", type=float, default=1e-7)
    ap.add_argument("--verify", type=float, default=1e-9)
    ap.add_argument("--threshold", type=float, default=1e-4, help="relative drop in total travel time")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    t0 = time.time()
    keep_awake()
    init(args.net)
    net = NET
    ck = Checkpoint(ROOT / "runs" / f"scan_{args.net}_{args.mode}.partial.jsonl")
    units = road_units(net, args.mode)
    print(f"{args.net} [{args.mode}]: {len(units)} roads to test; checkpoint {ck.path.name}", flush=True)
    jobs = [("BASE@screen", [], args.gap), ("BASE@verify", [], args.verify)] + [(lab, l, args.gap) for lab, l in units]
    screen = ck.run(args.net, args.workers, "screen", jobs)
    b_s, b_v = screen.pop("BASE@screen"), screen.pop("BASE@verify")
    base_tstt, base_v_tstt = b_s[1], b_v[1]
    print(f"base total {base_tstt:,.1f} (gap {b_s[2]:.1e}); at gap {b_v[2]:.1e}: {base_v_tstt:,.1f}; "
          f"solver noise ~{abs(base_tstt - base_v_tstt) / base_v_tstt:.1e}", flush=True)
    base_x = assign.solve(net, gap=args.gap, max_iter=200000).x      # flows for the report only
    res = []
    for lab, links in units:
        ok, tstt, gap, iters = screen[lab]
        res.append({"road": lab, "links": [int(a) for a in links], "base_flow": float(base_x[links].sum()),
                    "essential": not ok, "change": (tstt - base_tstt) / base_tstt if ok else None,
                    "gap": gap, "iters": iters})
    cand = [r for r in res if r["change"] is not None and r["change"] < -args.threshold]
    print(f"verify {len(cand)} candidates at gap {args.verify:.0e}", flush=True)
    ver = ck.run(args.net, args.workers, "verify", [(r["road"], r["links"], args.verify) for r in cand])
    for r in cand:
        ok, tstt, gap, _ = ver[r["road"]]
        r["verified_change"], r["verified_gap"] = (tstt - base_v_tstt) / base_v_tstt, gap
    out = ROOT / "runs" / f"scan_{args.net}_{args.mode}.json"
    out.parent.mkdir(exist_ok=True)
    json.dump({"net": args.net, "mode": args.mode, "gap": args.gap, "verify": args.verify,
               "threshold": args.threshold, "base_tstt": base_tstt, "base_tstt_verified": base_v_tstt,
               "seconds": time.time() - t0, "results": res}, open(out, "w"), indent=1)
    valid = [r for r in res if r["change"] is not None]
    real = sorted([r for r in cand if r["verified_change"] < -args.threshold], key=lambda r: r["verified_change"])
    print(f"\n{args.net} [{args.mode}]: {len(valid)} closures solved, {len(res) - len(valid)} essential")
    print(f"closing makes the city FASTER (verified, > {args.threshold:.0e}): {len(real)} "
          f"(screened {len(cand)}, {len(cand) - len(real)} failed verification)")
    for r in real[:12]:
        print(f"  {r['road']:>12}  flow {r['base_flow']:8.0f}  total time {r['verified_change'] * 100:+.4f}%")
    worst = sorted(valid, key=lambda r: -r["change"])[:3]
    print("biggest damage when closed:", ", ".join(f"{r['road']} {r['change'] * 100:+.2f}%" for r in worst))
    print(f"time {time.time() - t0:.0f}s -> {out.name}")


if __name__ == "__main__":
    main()
