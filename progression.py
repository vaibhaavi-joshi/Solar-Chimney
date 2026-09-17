"""Design iterations, all run against the SAME room and weather for a fair comparison."""
import math, statistics
from chimney_model import Design, PCM, Room, Weather, simulate, profile
from design_cases import RURAL, URBAN, make_room
from scenarios import SCENARIOS, weather

p=PCM(); w=weather(SCENARIOS[1])   # hot day, 44/31

VERSIONS=[
 ("V1  first guess",        2.0,0.50,0.20,45,20,0.75),
 ("V2  scaled up",          3.0,1.50,0.25,50,20,0.75),
 ("V3  short + wide",       1.5,2.00,0.25,50,20,0.75),
 ("V4  V3 + cool roof",     1.5,2.00,0.25,50,20,0.25),
]

for case,label in ((RURAL,"RURAL  metal sheet roof"),(URBAN,"URBAN  concrete roof")):
    print(f"\n=== {label} — hot day 44/31 ===")
    base_room=make_room(case)
    b=simulate(Design(use_pcm=False,gap=0.002,room_volume=case["volume"]),p,w,room=base_room)
    xs,ys=profile(b,"T_room")
    bp=max(ys); bn=statistics.mean([y for x,y in zip(xs,ys) if x>=21 or x<=5])
    print(f"    no chimney: peak {bp:.1f} C, night {bn:.1f} C")
    print(f"{'version':<22}{'size':>12}{'area':>7}{'height':>8}{'peak':>8}{'night':>8}"
          f"{'peak drop':>11}{'night drop':>12}")
    for name,L,W,g,t,pcm,absn in VERSIONS:
        kw=dict(case); kw.pop("name"); kw["roof_absorptance"]=absn
        room=Room(**kw)
        d=Design(length=L,width=W,gap=g,tilt_deg=t,pcm_mass=pcm,room_volume=case["volume"])
        r=simulate(d,p,w,room=room)
        xs,ys=profile(r,"T_room")
        pk=max(ys); ni=statistics.mean([y for x,y in zip(xs,ys) if x>=21 or x<=5])
        # baseline for V4 must be the SAME roof it sits on? no - compare to original unfitted dark roof
        print(f"{name:<22}{f'{L}x{W}':>12}{L*W:>7.1f}{L*math.sin(math.radians(t)):>8.2f}"
              f"{pk:>8.1f}{ni:>8.1f}{bp-pk:>11.1f}{bn-ni:>12.1f}")
