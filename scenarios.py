"""Three weather scenarios, anchored to IMD climatology, run on both housing types."""
from chimney_model import Design, PCM, Room, Weather, simulate, profile
from design_cases import RURAL, URBAN, make_room
import statistics

SCENARIOS = [
    dict(key="normal",  name="Normal summer day",
         T_max=39.5, T_min=27.5, wind=1.5, cloud=0.05, dni=900,
         note="IMD climatological mean max for May/June"),
    dict(key="hot",     name="Hot day (heatwave)",
         T_max=44.0, T_min=31.0, wind=1.0, cloud=0.0, dni=930,
         note="Meets IMD heatwave threshold, ~4.5 K above normal"),
    dict(key="extreme", name="Extreme day (severe heatwave)",
         T_max=47.0, T_min=35.0, wind=0.5, cloud=0.0, dni=950,
         note="Severe heatwave; night matches Delhi record 35.2 C"),
]

def weather(s):
    return Weather(T_max=s["T_max"], T_min=s["T_min"], wind=s["wind"],
                   cloud=s["cloud"], dni=s["dni"], day_of_year=160)

# chosen design from step 1: 4.5 m2, modular 4-panel unit
def chimney(vol):
    return Design(length=1.5, width=2.0, gap=0.25, tilt_deg=50,
                  pcm_mass=20, room_volume=vol)

def sealed(vol):
    return Design(use_pcm=False, gap=0.002, room_volume=vol)

def stats(r):
    xs, ys = profile(r, "T_room")
    peak = max(ys)
    night = statistics.mean([y for x, y in zip(xs, ys) if x >= 21 or x <= 5])
    _, q = profile(r, "Q")
    return peak, night, max(q)

if __name__ == "__main__":
    p = PCM()
    for case in (RURAL, URBAN):
        room = make_room(case)
        print(f"\n=== {case['name']} ===")
        print(f"{'scenario':<24}{'outdoor':>10}{'no chimney':>22}{'with chimney':>22}{'drop':>16}")
        print(f"{'':<24}{'max/min':>10}{'peak':>11}{'night':>11}{'peak':>11}{'night':>11}"
              f"{'peak':>8}{'night':>8}")
        for s in SCENARIOS:
            w = weather(s)
            b = stats(simulate(sealed(case["volume"]), p, w, room=room))
            c = stats(simulate(chimney(case["volume"]), p, w, room=room))
            print(f"{s['name']:<24}{f'{s[chr(84)+chr(95)+chr(109)+chr(97)+chr(120)]:.0f}/{s[chr(84)+chr(95)+chr(109)+chr(105)+chr(110)]:.0f}':>10}"
                  f"{b[0]:>11.1f}{b[1]:>11.1f}{c[0]:>11.1f}{c[1]:>11.1f}"
                  f"{b[0]-c[0]:>8.1f}{b[1]-c[1]:>8.1f}")
