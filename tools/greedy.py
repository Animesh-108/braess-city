"""Level 4: greedy search for a set of roads whose closure lowers total travel time (rules pre-registered in
PRODUCTION_LOG.md). Each step closes every remaining road on top of the closures so far, re-solves the best few at
the verification gap, and accepts the best only if it beats --threshold vs the current state. Greedy: not
guaranteed optimal. Usage: python tools/greedy.py Anaheim --mode twoway"""
import os
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
import argparse, json, sys, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import network, assign
from tools import scan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("net")
    ap.add_argument("--mode", choices=["directed", "twoway"], default="twoway")
    ap.add_argument("--gap", type=float, default=1e-7)
    ap.add_argument("--verify", type=float, default=1e-9)
    ap.add_argument("--threshold", type=float, default=1e-4)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--max-steps", type=int, default=15)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--resume", action="store_true", help="continue from the saved json (same rules)")
    args = ap.parse_args()
    t0 = time.time()
    net = network.load(args.net)
    units = dict(scan.road_units(net, args.mode))
    chosen = []

    def closed_mask(labels):
        m = np.zeros(net.n_links, bool)
        for lab in labels:
            m[units[lab]] = True
        return m

    start_v = assign.solve(net, gap=args.verify, max_iter=200000)
    cur_v = start_v
    steps = []
    out = ROOT / "runs" / f"greedy_{args.net}_{args.mode}.json"
    if args.resume and out.exists():
        saved = json.load(open(out))
        chosen, steps = saved["chosen"], saved["steps"]
        cur_v = assign.solve(net, closed_mask(chosen), gap=args.verify, max_iter=200000)
        print(f"resumed after step {len(steps)}: closed {chosen}, city total "
              f"{(cur_v.tstt - start_v.tstt) / start_v.tstt * 100:+.4f}% vs start", flush=True)
    for step in range(len(steps) + 1, args.max_steps + 1):
        cur_s = assign.solve(net, closed_mask(chosen), gap=args.gap, max_iter=200000)
        links_now = [a for lab in chosen for a in units[lab]]
        jobs = [(lab, links_now + links, args.gap) for lab, links in units.items() if lab not in chosen]
        screen = scan.run_pool(args.net, args.workers, jobs)
        table = {lab: (None if not ok else (tstt - cur_s.tstt) / cur_s.tstt) for lab, (ok, tstt, _, _) in screen.items()}
        best = sorted([(c, lab) for lab, c in table.items() if c is not None])[:args.top]
        ver = scan.run_pool(args.net, args.workers, [(lab, links_now + units[lab], args.verify) for _, lab in best])
        verified = sorted(((tstt - cur_v.tstt) / cur_v.tstt, lab, tstt) for lab, (ok, tstt, _, _) in ver.items() if ok)
        rec = {"step": step, "closed_before": list(chosen), "screen": table,
               "verified": [{"road": lab, "change": c} for c, lab, _ in verified]}
        steps.append(rec)
        if not verified or verified[0][0] >= -args.threshold:
            print(f"step {step}: no road lowers total time by > {args.threshold:.0e} -> stop", flush=True)
            break
        c, lab, tstt = verified[0]
        chosen.append(lab)
        cur_v = assign.solve(net, closed_mask(chosen), gap=args.verify, max_iter=200000)
        rec["accepted"], rec["change_vs_current"] = lab, c
        rec["total_vs_start"] = (cur_v.tstt - start_v.tstt) / start_v.tstt
        print(f"step {step}: close {lab:>12}  {c * 100:+.4f}%  -> city total {rec['total_vs_start'] * 100:+.4f}% "
              f"vs start  ({time.time() - t0:.0f}s)", flush=True)
        json.dump({"net": args.net, "mode": args.mode, "rules": vars(args), "start_tstt": start_v.tstt,
                   "chosen": chosen, "steps": steps}, open(out, "w"), indent=1)
    json.dump({"net": args.net, "mode": args.mode, "rules": vars(args), "start_tstt": start_v.tstt,
               "final_tstt": cur_v.tstt, "chosen": chosen, "steps": steps}, open(out, "w"), indent=1)
    print(f"\nclosed {len(chosen)} roads: {chosen}")
    print(f"total travel time {start_v.tstt:,.1f} -> {cur_v.tstt:,.1f} "
          f"({(cur_v.tstt - start_v.tstt) / start_v.tstt * 100:+.4f}%), {time.time() - t0:.0f}s -> {out.name}")


if __name__ == "__main__":
    main()
