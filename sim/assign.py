"""Static traffic assignment (user equilibrium): every trip's route responds to congested travel time until no
driver can switch to a faster route. Link cost = BPR: t = fft * (1 + b * (flow / capacity) ** power).
Solver: conjugate Frank-Wolfe (Mitradjieva & Lindberg 2013), all-or-nothing loads from Dijkstra trees.
Quality is measured by the relative gap (0 = exact equilibrium)."""
import time

import numpy as np
from numba import njit, prange

INF = 1e300


@njit(cache=True)
def link_cost(x, fft, cap, b, power, const, out):
    """Generalized cost drivers react to: congested travel time + fixed toll/distance part."""
    for a in range(x.shape[0]):
        out[a] = fft[a] * (1.0 + b[a] * (x[a] / cap[a]) ** power[a]) + const[a]


def travel_time(x, net):
    """Congested travel time only (what the video's city counter shows)."""
    return net.fft * (1.0 + net.b * (x / net.cap) ** net.power)


@njit(cache=True)
def link_cost_deriv(x, fft, cap, b, power, out):
    for a in range(x.shape[0]):
        if x[a] <= 0.0 and power[a] < 1.0 + 1e-12:
            out[a] = fft[a] * b[a] / cap[a]
        elif x[a] <= 0.0:
            out[a] = 0.0
        else:
            out[a] = fft[a] * b[a] * power[a] * x[a] ** (power[a] - 1.0) / cap[a] ** power[a]


@njit(cache=True)
def _heap_push(hk, hn, size, k, n):
    i = size
    hk[i] = k
    hn[i] = n
    while i > 0:
        p = (i - 1) // 2
        if hk[p] <= hk[i]:
            break
        hk[p], hk[i] = hk[i], hk[p]
        hn[p], hn[i] = hn[i], hn[p]
        i = p
    return size + 1


@njit(cache=True)
def _heap_pop(hk, hn, size):
    k, n = hk[0], hn[0]
    size -= 1
    hk[0], hn[0] = hk[size], hn[size]
    i = 0
    while True:
        l, r, s = 2 * i + 1, 2 * i + 2, i
        if l < size and hk[l] < hk[s]:
            s = l
        if r < size and hk[r] < hk[s]:
            s = r
        if s == i:
            break
        hk[s], hk[i] = hk[i], hk[s]
        hn[s], hn[i] = hn[i], hn[s]
        i = s
    return k, n, size


@njit(cache=True)
def shortest_tree(origin, cost, first_out, out_links, head, closed, first_thru, dist, pred):
    n = dist.shape[0]
    for i in range(n):
        dist[i] = INF
        pred[i] = -1
    dist[origin] = 0.0
    m = out_links.shape[0]
    hk = np.empty(m + n + 1)
    hn = np.empty(m + n + 1, np.int64)
    size = _heap_push(hk, hn, 0, 0.0, origin)
    while size > 0:
        k, u, size = _heap_pop(hk, hn, size)
        if k > dist[u]:
            continue
        if u != origin and u < first_thru:          # zone centroids are not through nodes
            continue
        for idx in range(first_out[u], first_out[u + 1]):
            a = out_links[idx]
            if closed[a]:
                continue
            v = head[a]
            nd = k + cost[a]
            if nd < dist[v]:
                dist[v] = nd
                pred[v] = a
                size = _heap_push(hk, hn, size, nd, v)


@njit(parallel=True, cache=True)
def all_or_nothing(cost, demand, first_out, out_links, tail, head, closed, first_thru, n_nodes):
    """Load every OD pair on its current shortest path. Returns (link loads, shortest-path total, unreachable)."""
    z = demand.shape[0]
    m = cost.shape[0]
    parts = np.zeros((z, m))
    sptt = np.zeros(z)
    bad = np.zeros(z, np.int64)
    for o in prange(z):
        row_total = 0.0
        for d in range(z):
            row_total += demand[o, d]
        if row_total <= 0.0:
            continue
        dist = np.empty(n_nodes)
        pred = np.empty(n_nodes, np.int64)
        shortest_tree(o, cost, first_out, out_links, head, closed, first_thru, dist, pred)
        for d in range(z):
            q = demand[o, d]
            if q <= 0.0 or d == o:
                continue
            if dist[d] >= INF:
                bad[o] += 1
                continue
            sptt[o] += q * dist[d]
            v = d
            while v != o:
                a = pred[v]
                parts[o, a] += q
                v = tail[a]
    y = np.zeros(m)
    for o in range(z):
        for a in range(m):
            y[a] += parts[o, a]
    return y, sptt.sum(), bad.sum()


@njit(cache=True)
def line_search(x, d, fft, cap, b, power, const):
    """Exact step on the Beckmann objective: find lam in [0, 1] where sum t(x + lam d) * d = 0 (bisection)."""
    lo, hi = 0.0, 1.0

    def slope(lam):
        s = 0.0
        for a in range(x.shape[0]):
            if d[a] != 0.0:
                xa = x[a] + lam * d[a]
                s += (fft[a] * (1.0 + b[a] * (xa / cap[a]) ** power[a]) + const[a]) * d[a]
        return s

    if slope(1.0) <= 0.0:
        return 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if slope(mid) > 0.0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


class Result:
    """tstt = total travel time (sum of flow x congested time); tsgc = same with the generalized cost."""
    def __init__(self, x, cost, tstt, tsgc, gap, iters, seconds, reachable):
        self.x, self.cost, self.tstt, self.tsgc = x, cost, tstt, tsgc
        self.gap, self.iters, self.seconds, self.reachable = gap, iters, seconds, reachable


def solve(net, closed=None, gap=1e-6, max_iter=20000, verbose=False, trace=None):
    """User equilibrium on `net` with links in `closed` removed. tstt = total travel time (flow x time summed).
    trace: optional list; each step appends (flows, relative gap) before the convergence test (read-only, for
    visuals; does not change the result)."""
    t0 = time.time()
    m = net.n_links
    closed = np.zeros(m, np.bool_) if closed is None else closed
    args = (net.first_out, net.out_links, net.tail, net.head, closed, net.first_thru, net.n_nodes)
    p = (net.fft, net.cap, net.b, net.power)
    pc = p + (net.const,)
    cost = np.empty(m)
    link_cost(np.zeros(m), *pc, cost)
    x, _, bad = all_or_nothing(cost, net.demand, *args)
    if bad:
        return Result(x, cost, np.inf, np.inf, np.inf, 0, time.time() - t0, False)
    s_prev = None
    hess = np.empty(m)
    rel = np.inf
    k = 0
    for k in range(1, max_iter + 1):
        link_cost(x, *pc, cost)
        y, sptt, _ = all_or_nothing(cost, net.demand, *args)
        tstt = float(cost @ x)
        rel = (tstt - sptt) / tstt
        if trace is not None:
            trace.append((x.copy(), rel))
        if verbose and k % 50 == 0:
            print(f"  iter {k}: gap {rel:.2e}")
        if rel < gap:
            break
        if s_prev is None:
            s = y
        else:
            link_cost_deriv(x, *p, hess)
            dbar = s_prev - x
            num = float((dbar * hess) @ (y - x))
            den = float((dbar * hess) @ (y - s_prev))
            alpha = num / den if den != 0.0 else 0.0
            alpha = min(max(alpha, 0.0), 0.99)
            s = alpha * s_prev + (1 - alpha) * y
        dvec = s - x
        lam = line_search(x, dvec, *pc)
        x = x + lam * dvec
        s_prev = s
    link_cost(x, *pc, cost)
    return Result(x, cost.copy(), float(travel_time(x, net) @ x), float(cost @ x), rel, k, time.time() - t0, True)
