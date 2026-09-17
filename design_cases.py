"""Design cases and chimney sizing sweep for both housing types."""
from chimney_model import Design, PCM, Room, Weather, simulate, profile
import statistics

# ---------------- Housing cases ----------------
# Census: avg rural dwelling ~430-494 sq ft; 40% of households = 5 people in ONE room.
# 10x10 ft room = 100 sq ft = 9.3 m2. Ceiling 2.8 m -> ~25 m3.

RURAL = dict(
    name="Rural: metal sheet roof",
    volume=25.0, roof_area=9.0,
    roof_U=5.0,            # uninsulated corrugated metal, very high
    roof_absorptance=0.75, # weathered galvanised / painted metal
    wall_UA=28.0,          # mud or brick walls, 9 m2 floor
    thermal_mass=0.55e6,   # lightweight: metal roof + thin walls
    internal_gain=250.0,   # 5 occupants at rest
    infiltration=1.5,      # leaky: gaps at eaves and door
)

URBAN = dict(
    name="Urban informal: RCC concrete roof",
    volume=25.0, roof_area=9.0,
    roof_U=2.8,            # 100-125 mm RCC slab
    roof_absorptance=0.65, # grey concrete
    wall_UA=32.0,          # brick, shared walls, urban heat island
    thermal_mass=1.8e6,    # heavy: concrete slab stores heat
    internal_gain=250.0,
    infiltration=1.0,      # tighter construction, fewer openings
)

def make_room(c):
    return Room(volume=c["volume"], roof_area=c["roof_area"], roof_U=c["roof_U"],
                roof_absorptance=c["roof_absorptance"], wall_UA=c["wall_UA"],
                thermal_mass=c["thermal_mass"], internal_gain=c["internal_gain"],
                infiltration=c["infiltration"])

def stats(r):
    xs, ys = profile(r, "T_room")
    peak = max(ys)
    night = statistics.mean([y for x, y in zip(xs, ys) if x >= 21 or x <= 5])
    _, q = profile(r, "Q")
    return peak, night, max(q)

if __name__ == "__main__":
    w, p = Weather(), PCM()
    for case in (RURAL, URBAN):
        room = make_room(case)
        sealed = simulate(Design(use_pcm=False, gap=0.002, room_volume=case["volume"]),
                          p, w, room=room)
        bp, bn, _ = stats(sealed)
        print(f"\n{case['name']}   (no chimney: peak {bp:.1f} C, night {bn:.1f} C)")
        print(f"{'collector':>10}{'L x W':>12}{'peak drop':>11}{'night drop':>12}{'peak flow':>11}{'ACH':>7}")
        for L, W in [(1.5,0.6),(2,0.75),(2,1.0),(2.5,1.0),(3,1.0),(3,1.25),(3,1.5),(3.5,1.5),(4,1.5),(4,2.0)]:
            d = Design(length=L, width=W, gap=0.25, tilt_deg=50,
                       pcm_mass=20, room_volume=case["volume"])
            r = simulate(d, p, w, room=room)
            pk, ng, q = stats(r)
            print(f"{L*W:>10.2f}{f'{L}x{W}':>12}{bp-pk:>11.1f}{bn-ng:>12.1f}"
                  f"{q:>11.0f}{q/case['volume']:>7.1f}")
