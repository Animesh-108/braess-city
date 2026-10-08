"""Gate 1: the solver must reproduce the textbook Braess numbers and the published best-known solutions."""
import sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim import network, assign

# Level 1 toy: 6 drivers; without the 3->4 shortcut each pays 83, with it each pays 92.
net = network.load("Braess")
short = [a for a in range(net.n_links) if (net.tail[a], net.head[a]) == (2, 3)][0]
closed = np.zeros(net.n_links, bool); closed[short] = True
r0, r1 = assign.solve(net, closed, gap=1e-10), assign.solve(net, gap=1e-10)
print(f"Braess toy: per-driver time without shortcut {r0.tstt / 6:.4f} (expect 83), with {r1.tstt / 6:.4f} (expect 92)")

for prefix, g in [(p, float(v)) for p, v in (a.split(":") for a in (sys.argv[1:] or ["SiouxFalls:1e-8", "Anaheim:1e-8", "ChicagoSketch:1e-6"]))]:
    net = network.load(prefix)
    t = time.time()
    r = assign.solve(net, gap=g)
    pub = network.load_flow(prefix)
    pub_x = np.array([pub[(net.tail[a], net.head[a])][0] for a in range(net.n_links)])
    pub_tstt = float(assign.travel_time(pub_x, net) @ pub_x)
    err = np.abs(r.x - pub_x).max()
    print(f"{prefix}: {net.n_links} links, {net.n_zones} zones, trips {net.demand.sum():,.0f} | gap {r.gap:.1e} in "
          f"{r.iters} iters, {r.seconds:.1f}s | TSTT ours {r.tstt:,.2f} vs published {pub_tstt:,.2f} "
          f"(diff {abs(r.tstt - pub_tstt) / pub_tstt:.1e}) | max link-flow diff {err:.2f}", flush=True)
