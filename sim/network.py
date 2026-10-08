"""Load a TNTP road network (github.com/bstabler/TransportationNetworks): links, BPR cost parameters, demand."""
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"
# Route choice uses generalized cost = time + toll_w * toll + dist_w * length (each network's README)
GEN_COST = {"ChicagoSketch": (0.02, 0.04)}


@dataclass
class Network:
    name: str
    n_nodes: int
    n_zones: int
    first_thru: int          # 0-based: nodes below this index (zones) cannot be passed through
    tail: np.ndarray         # 0-based node index per link
    head: np.ndarray
    cap: np.ndarray
    fft: np.ndarray          # free-flow time
    b: np.ndarray
    power: np.ndarray
    const: np.ndarray        # toll + distance part of the generalized cost (minutes, fixed per link)
    demand: np.ndarray       # zones x zones
    first_out: np.ndarray    # forward star: links of node u are out_links[first_out[u]:first_out[u+1]]
    out_links: np.ndarray

    @property
    def n_links(self):
        return len(self.tail)


def _meta(text, key):
    m = re.search(r"<" + key + r">\s*([\d.]+)", text)
    return float(m.group(1)) if m else None


def load(prefix, demand_scale=1.0):
    net_txt = (DATA / f"{prefix}_net.tntp").read_text()
    n_nodes = int(_meta(net_txt, "NUMBER OF NODES"))
    n_zones = int(_meta(net_txt, "NUMBER OF ZONES"))
    first_thru = int(_meta(net_txt, "FIRST THRU NODE")) - 1
    rows = []
    for line in net_txt.split("<END OF METADATA>")[1].splitlines():
        line = line.strip().rstrip(";").strip()
        if not line or line.startswith("~"):
            continue
        rows.append([float(v) for v in line.split()[:10]])
    a = np.array(rows)
    tail, head = a[:, 0].astype(np.int64) - 1, a[:, 1].astype(np.int64) - 1
    trips_txt = (DATA / f"{prefix}_trips.tntp").read_text().split("<END OF METADATA>")[1]
    demand = np.zeros((n_zones, n_zones))
    for block in re.split(r"Origin\s+", trips_txt)[1:]:
        parts = block.split(None, 1)
        if len(parts) < 2:
            continue
        o, rest = parts
        for d, q in re.findall(r"(\d+)\s*:\s*([\d.eE+-]+)", rest):
            demand[int(o) - 1, int(d) - 1] = float(q)
    np.fill_diagonal(demand, 0.0)
    order = np.argsort(tail, kind="stable")
    first_out = np.searchsorted(tail[order], np.arange(n_nodes + 1)).astype(np.int64)
    toll_w, dist_w = GEN_COST.get(prefix, (0.0, 0.0))
    const = toll_w * a[:, 8] + dist_w * a[:, 3]
    return Network(prefix, n_nodes, n_zones, first_thru, tail, head, a[:, 2], a[:, 4], a[:, 5], a[:, 6], const,
                   demand * demand_scale, first_out, order.astype(np.int64))


def load_flow(prefix):
    """Published best-known solution: {(tail, head): (volume, cost)} with 0-based nodes."""
    out = {}
    for line in (DATA / f"{prefix}_flow.tntp").read_text().splitlines()[1:]:
        p = line.split()
        if len(p) >= 4:
            out[(int(p[0]) - 1, int(p[1]) - 1)] = (float(p[2]), float(p[3]))
    return out
