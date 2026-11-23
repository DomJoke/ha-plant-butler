"""Build custom_components/plant_butler/data/plants.json from species.tsv."""
import json
import sys
from pathlib import Path

WATER = {"vl": "very_low", "l": "low", "m": "medium", "h": "high", "vh": "very_high"}
LIGHT = {"vd": "very_dark", "d": "dark", "ps": "partial_shade", "bi": "bright_indirect",
         "bs": "bright_some_sun", "fs": "full_sun"}
HUM = {"l": "low", "m": "medium", "h": "high"}

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
species = []
ids = set()
for line in src.read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    c = line.split("\t")
    assert len(c) == 13, (len(c), line)
    sid = c[0]
    assert sid not in ids, sid
    ids.add(sid)
    tmin, tmax = int(c[6]), int(c[7])
    assert tmin < tmax, sid
    species.append({
        "id": sid,
        "name": {"de": c[1], "en": c[2]},
        "latin": c[3],
        "water": WATER[c[4]],
        "light": LIGHT[c[5]],
        "temperature": {"min": tmin, "max": tmax},
        "humidity": HUM[c[8]],
        "fertilizer": {"interval_days": int(c[9]), "winter_interval_days": int(c[10])},
        "toxic_pets": c[11] == "1",
        "icon": "mdi:" + c[12],
    })
species.sort(key=lambda s: s["name"]["de"].lower())
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps({"version": 1, "species": species}, ensure_ascii=False, indent=1) + "\n",
               encoding="utf-8")
print(len(species), "species")
