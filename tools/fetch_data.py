"""Download the road networks used here from Transportation Networks for Research (TNTP) at a pinned commit and
check every file against data/MANIFEST.json (sha256 of the exact files the experiment ran on).
The data is not copied into this repository: its terms say "Data sets are for academic research purposes only."
Usage: python tools/fetch_data.py"""
import hashlib, json, sys, urllib.request
from pathlib import Path

COMMIT = "d1639b4ef218c17928ba573e806ddf8ba5e7ae6d"
BASE = f"https://raw.githubusercontent.com/bstabler/TransportationNetworks/{COMMIT}"
DATA = Path(__file__).resolve().parent.parent / "data"


def main():
    manifest = json.load(open(DATA / "MANIFEST.json"))
    bad = []
    for name, info in manifest.items():
        out = DATA / name
        if not out.exists():
            url = f"{BASE}/{info['folder']}/{name}"
            print("download", url)
            out.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "braess-city"})).read())
        ok = hashlib.sha256(out.read_bytes()).hexdigest() == info["sha256"]
        print(("ok  " if ok else "DIFFERENT  ") + name)
        if not ok:
            bad.append(name)
    if bad:
        sys.exit(f"{len(bad)} file(s) differ from the ones the experiment used: {bad}")
    print("all", len(manifest), "files match")


if __name__ == "__main__":
    main()
