"""Every number the video uses, computed from the run files and data (never typed by hand) -> results/numbers.json.
Each entry: value + display text + source."""
import json, re, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import network, assign

RUNS = ROOT / "runs"
N = {}
# Time unit of each network (from its README). None = not stated -> only percentages may be shown.
MIN_PER_UNIT = {"Anaheim": 1.0, "ChicagoSketch": 1.0, "EMA": 60.0, "Barcelona": None, "Winnipeg": None}


def put(key, value, text, source):
    N[key] = {"value": value, "text": text, "source": source}


def pct(x, nd=3):
    return f"{x * 100:+.{nd}f}%".replace("+-", "-")


def load(name):
    return json.load(open(RUNS / name))


def main():
    # Level 1: textbook Braess network (6 drivers)
    net = network.load("Braess")
    short = [a for a in range(net.n_links) if (net.tail[a], net.head[a]) == (2, 3)][0]
    closed = np.zeros(net.n_links, bool)
    closed[short] = True
    r0, r1 = assign.solve(net, closed, gap=1e-10), assign.solve(net, gap=1e-10)
    put("toy.drivers", 6, "6", "data/Braess_trips.tntp")
    lk = {(int(net.tail[a]) + 1, int(net.head[a]) + 1): a for a in range(net.n_links)}
    narrow, wide, sc = lk[(1, 3)], lk[(1, 4)], lk[(3, 4)]
    per_car = net.fft[narrow] * net.b[narrow] / net.cap[narrow]
    put("toy.narrow_per_car", per_car, f"{per_car:.0f}", "Braess_net.tntp link 1->3: t = 10 x (fft*b/cap)")
    put("toy.wide_base", net.fft[wide], f"{net.fft[wide]:.0f}", "Braess_net.tntp link 1->4: t = 50 + x")
    put("toy.short_base", net.fft[sc], f"{net.fft[sc]:.0f}", "Braess_net.tntp link 3->4: t = 10 + x")
    put("toy.before", r0.tstt / 6, f"{r0.tstt / 6:.0f}", "solver on data/Braess_net.tntp, shortcut closed")
    put("toy.after", r1.tstt / 6, f"{r1.tstt / 6:.0f}", "solver on data/Braess_net.tntp, shortcut open")

    # validation vs published best-known solutions
    for prefix, g in (("Anaheim", 1e-8), ("ChicagoSketch", 1e-6)):
        net = network.load(prefix)
        r = assign.solve(net, gap=g, max_iter=200000)
        pub = network.load_flow(prefix)
        px = np.array([pub[(net.tail[a], net.head[a])][0] for a in range(net.n_links)])
        pt = float(assign.travel_time(px, net) @ px)
        d = abs(r.tstt - pt) / pt
        put(f"valid.{prefix}.diff", d, f"{d * 100:.5f}%", f"solver gap {g:g} vs data/{prefix}_flow.tntp")
        if prefix == "ChicagoSketch":
            x_fixed = r.x

    # Chicago's first validation attempt: route choice by travel time only (generalized cost missing)
    net = network.load("ChicagoSketch")
    net.const[:] = 0.0
    r = assign.solve(net, gap=1e-6, max_iter=200000)
    pub = network.load_flow("ChicagoSketch")
    px = np.array([pub[(net.tail[a], net.head[a])][0] for a in range(net.n_links)])
    pt = float(assign.travel_time(px, net) @ px)
    d = abs(r.tstt - pt) / pt
    put("valid.ChicagoSketch.first_diff", d, f"{d * 100:.3f}%", "same solver WITHOUT tolls/distance in route choice")
    roads = (net.tail >= net.n_zones) & (net.head >= net.n_zones)       # links between road nodes (no zone connectors)
    off1 = int((np.abs(r.x - px)[roads] > 10).sum())
    off2 = int((np.abs(x_fixed - px)[roads] > 10).sum())
    put("valid.ChicagoSketch.roads", int(roads.sum()), f"{int(roads.sum()):,}", "ChicagoSketch links between road nodes")
    put("valid.ChicagoSketch.first_off10", off1, f"{off1:,}", "road links > 10 veh/h from the published flow, first try")
    put("valid.ChicagoSketch.fixed_off10", off2, f"{off2:,}", "road links > 10 veh/h from the published flow, with tolls+distance")

    # numerical noise: the same Anaheim base, solved to two stopping precisions (scan file)
    sc = json.load(open(ROOT / "runs" / "scan_Anaheim_twoway.json"))
    h7, h9 = sc["base_tstt"] / 60, sc["base_tstt_verified"] / 60
    put("noise.base_screen_h", h7, f"{h7:,.3f}", f"Anaheim base, gap {sc['gap']:g} (scan screening precision)")
    put("noise.base_verify_h", h9, f"{h9:,.3f}", f"Anaheim base, gap {sc['verify']:g} (scan verify precision)")
    put("noise.diff", abs(h9 - h7) / h9, f"{abs(h9 - h7) / h9 * 100:.4f}%", "difference between the two precisions")
    put("noise.precision_ratio", sc["gap"] / sc["verify"], f"{sc['gap'] / sc['verify']:.0f}", "screen gap / verify gap")

    # congestion comparison Anaheim vs Chicago (base equilibrium)
    for prefix, g in (("Anaheim", 1e-7), ("ChicagoSketch", 1e-6)):
        net = network.load(prefix)
        r = assign.solve(net, gap=g, max_iter=200000)
        roads = (net.tail >= net.n_zones) & (net.head >= net.n_zones)
        t = assign.travel_time(r.x, net)
        vc = float((r.x[roads] / net.cap[roads]).mean())
        delay = float((r.x * (t - net.fft))[roads].sum() / (r.x * t)[roads].sum())
        put(f"cong.{prefix}.vc", vc, f"{vc * 100:.0f}%", f"mean volume/capacity on roads, base equilibrium gap {g:g}")
        put(f"cong.{prefix}.delay", delay, f"{delay * 100:.1f}%", "congestion delay share of road travel time")

    # per-city scans
    total_solves, total_sec = 0, 0.0
    labels = {"Anaheim": "Anaheim", "Barcelona": "Barcelona", "EMA": "Eastern Massachusetts",
              "ChicagoSketch": "Chicago", "Winnipeg": "Winnipeg"}
    for prefix in labels:
        d = load(f"scan_{prefix}_twoway.json")
        net = network.load(prefix)
        trips = float(net.demand.sum())
        res = d["results"]
        valid = [r for r in res if r["change"] is not None]
        harm = sorted([r for r in res if r.get("verified_change") is not None and r["verified_change"] < -d["threshold"]],
                      key=lambda r: r["verified_change"])
        base = d["base_tstt_verified"]
        k = f"city.{prefix}"
        put(f"{k}.tested", len(valid), f"{len(valid):,}", f"runs/scan_{prefix}_twoway.json")
        put(f"{k}.essential", len(res) - len(valid), f"{len(res) - len(valid)}", f"runs/scan_{prefix}_twoway.json")
        put(f"{k}.harmful", len(harm), f"{len(harm)}", f"runs/scan_{prefix}_twoway.json (verified)")
        share = len(harm) / len(valid)
        put(f"{k}.share", share, f"{share * 100:.1f}%" if share else "0%", "harmful / tested")
        put(f"{k}.trips", trips, f"{trips:,.0f}", f"data/{prefix}_trips.tntp (intrazonal excluded)")
        mpu = MIN_PER_UNIT[prefix]
        if mpu:
            put(f"{k}.avg_trip_min", base * mpu / trips, f"{base * mpu / trips:.1f}", "base total time / trips (min)")
        if harm:
            b = harm[0]
            put(f"{k}.best.road", b["road"], b["road"], "verified best single closure")
            put(f"{k}.best.change", b["verified_change"], pct(b["verified_change"]), "verified at gap 1e-9/1e-7")
            if mpu:
                saved = -b["verified_change"] * base * mpu          # minutes per hour of traffic
                put(f"{k}.best.sec_per_trip", saved / trips * 60, f"{saved / trips * 60:.1f}", "saved min / trips x 60")
                put(f"{k}.best.veh_hours", saved / 60, f"{saved / 60:.0f}", "vehicle-hours saved across all modeled trips (demand period not stated in the data)")
        else:
            c = min(valid, key=lambda r: r["change"])
            put(f"{k}.closest.change", c["change"], pct(c["change"]), "closest to threshold, NOT counted")
        w = max(valid, key=lambda r: r["change"])
        put(f"{k}.worst.road", w["road"], w["road"], "biggest damage when closed")
        put(f"{k}.worst.change", w["change"], pct(w["change"], 1), "screen gap change")
        noise = abs(d["base_tstt"] - base) / base
        put(f"{k}.noise", noise, f"{noise * 100:.4f}%", "base at screen gap vs verify gap")
        put("threshold", d["threshold"], f"{d['threshold'] * 100:.2f}%", "pre-registered threshold (all cities)")
        put(f"{k}.seconds", d["seconds"], f"{d['seconds'] / 3600:.1f}", "scan wall time (hours)")
        total_solves += len(valid) + len(harm) + 2
        total_sec += d["seconds"]

    a = load("scan_Anaheim_twoway.json")
    base = a["base_tstt_verified"]
    best = min((r for r in a["results"] if r.get("verified_change") is not None), key=lambda r: r["verified_change"])
    put("anaheim.base_veh_hours", base / 60, f"{base / 60:,.0f}", "base total travel time / 60, all modeled trips")
    put("anaheim.after_best_veh_hours", base * (1 + best["verified_change"]) / 60,
        f"{base * (1 + best['verified_change']) / 60:,.0f}", "after closing the best single road")
    put("anaheim.roads_total", len(a["results"]), f"{len(a['results'])}", "whole roads incl. essential")

    # Barcelona one-way street
    bar = load("scan_Barcelona_twoway.json")
    street = ["563<->564", "564<->565", "565<->566", "566<->567", "567<->568", "568<->569", "563<->716"]
    sv = [r["verified_change"] for r in bar["results"] if r["road"] in street]
    put("barcelona.street_count", len(sv), f"{len(sv)}", "harmful pieces of one one-way street (log)")

    # Level 4 greedy
    g = load("greedy_Anaheim_twoway.json")
    single = {r["road"]: r["change"] for r in a["results"]}
    put("greedy.roads", len(g["chosen"]), f"{len(g['chosen'])}", "runs/greedy_Anaheim_twoway.json")
    put("greedy.total", g["final_tstt"] / g["start_tstt"] - 1, pct(g["final_tstt"] / g["start_tstt"] - 1),
        "final vs start, gap 1e-9")
    sv_min = (g["start_tstt"] - g["final_tstt"])
    put("greedy.veh_hours", sv_min / 60, f"{sv_min / 60:.0f}", "vehicle-hours saved across all modeled trips (demand period not stated in the data)")
    put("greedy.sec_per_trip", sv_min / N["city.Anaheim.trips"]["value"] * 60,
        f"{sv_min / N['city.Anaheim.trips']['value'] * 60:.1f}", "per trip")
    for st in g["steps"]:
        if "accepted" in st:
            put(f"greedy.step{st['step']}.road", st["accepted"], st["accepted"], "accepted road")
            put(f"greedy.step{st['step']}.cum", st["total_vs_start"], pct(st["total_vs_start"]), "city total vs start")
            put(f"greedy.step{st['step']}.gain", st["change_vs_current"], pct(st["change_vs_current"]), "gain this step")
    # "alone" values from the full-precision audit (runs/audit_greedy_singles.json, gap 1e-9), not the 1e-7 screen
    au = load("audit_greedy_singles.json")
    alone = {r["road"]: r["change_alone"] for r in au["rows"]}
    put("greedy.sum_singles", au["sum_alone"], pct(au["sum_alone"]), "audit: sum of the 12 roads closed alone, gap 1e-9")
    put("greedy.112_196.alone", alone["112<->196"], pct(alone["112<->196"], 4), "audit: closed alone, gap 1e-9")
    put("greedy.193_271.alone", alone["193<->271"], pct(alone["193<->271"]), "audit: closed alone, gap 1e-9")
    ratio5 = N["greedy.step5.gain"]["value"] / alone["112<->196"]
    put("greedy.112_196.ratio", ratio5, f"{ratio5:.0f}", "step-5 gain / alone value")
    total_solves += sum(len(st["screen"]) + len(st["verified"]) for st in g["steps"])

    an = N["city.Anaheim.tested"]["value"] / N["city.Anaheim.harmful"]["value"]
    put("city.Anaheim.one_in", an, f"{an:.0f}", "tested / harmful")
    ratio = N["greedy.total"]["value"] / N["city.Anaheim.best.change"]["value"]
    put("greedy.ratio_vs_best", ratio, f"{ratio:.1f}", "greedy total / best single closure")
    put("compute.solves", total_solves, f"{total_solves:,}", "scans (tested + verified + 2 bases) + greedy tables")
    put("compute.scan_hours", total_sec / 3600, f"{total_sec / 3600:.1f}", "sum of scan wall times (greedy excluded)")
    put("cities.with_effect", sum(1 for p in labels if N[f"city.{p}.harmful"]["value"] > 0), "4", "count")
    out = ROOT / "results" / "numbers.json"
    out.parent.mkdir(exist_ok=True)
    json.dump(N, open(out, "w"), indent=1)
    for k, v in N.items():
        print(f"{k:34} {v['text']:>14}   ({v['source']})")


if __name__ == "__main__":
    main()
