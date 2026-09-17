"""Run every locked case once and export curves for the 3D visual."""
import json, statistics
from chimney_model import Design, PCM, Room, Weather, simulate, profile
from design_cases import RURAL, URBAN, make_room
from scenarios import SCENARIOS, weather

p = PCM()
KEYS = ["T_room","T_amb","T_abs","T_pcm","T_air","Q","velocity","dP","liquid","I","T_glass"]

def curve(r, key, n=97):           # 97 points = every 15 min
    xs, ys = profile(r, key)
    out=[]
    for i in range(n):
        t = i*24/(n-1)
        j = min(range(len(xs)), key=lambda k: abs(xs[k]-t))
        out.append(round(ys[j],2))
    return out

def run(case, scen, roof_abs=None, use_chimney=True, pcm=20):
    room_kw = dict(case)
    room_kw.pop("name")
    if roof_abs is not None:
        room_kw["roof_absorptance"] = roof_abs
    room = Room(**{k:v for k,v in room_kw.items()})
    w = weather(scen)
    if use_chimney:
        d = Design(length=1.5, width=2.0, gap=0.25, tilt_deg=50,
                   pcm_mass=pcm, use_pcm=pcm>0, room_volume=case["volume"])
    else:
        d = Design(use_pcm=False, gap=0.002, room_volume=case["volume"])
    return simulate(d, p, w, room=room)

data = {"scenarios":[{k:s[k] for k in ("key","name","T_max","T_min","note")} for s in SCENARIOS],
        "cases":{}, "design":{"length":1.5,"width":2.0,"area":3.0,"gap":0.25,
                              "tilt":50,"pcm_kg":20,"panels":4},
        "runs":{}}

for case,ckey in ((RURAL,"rural"),(URBAN,"urban")):
    data["cases"][ckey] = {k:v for k,v in case.items()}
    for s in SCENARIOS:
        for variant,kw in (("none",dict(use_chimney=False)),
                           ("chimney",dict(use_chimney=True)),
                           ("chimney_nopcm",dict(use_chimney=True,pcm=0)),
                           ("chimney_coolroof",dict(use_chimney=True,roof_abs=0.25)),
                           ("coolroof_only",dict(use_chimney=False,roof_abs=0.25))):
            r = run(case, s, **kw)
            data["runs"][f"{ckey}|{s['key']}|{variant}"] = {k:curve(r,k) for k in KEYS}
    print("done", ckey)

with open("/mnt/user-data/outputs/simulation_data.json","w") as f:
    json.dump(data,f,separators=(",",":"))
print("exported", len(data["runs"]), "runs")

# summary table
print(f"\n{'case':<8}{'scenario':<10}{'variant':<18}{'peak':>8}{'night':>8}{'flow':>8}")
for k,v in data["runs"].items():
    c,s,var = k.split("|")
    tr=v["T_room"]; ni=[y for i,y in enumerate(tr) if i*0.25>=21 or i*0.25<=5]
    print(f"{c:<8}{s:<10}{var:<18}{max(tr):>8.1f}{statistics.mean(ni):>8.1f}{max(v['Q']):>8.0f}")
