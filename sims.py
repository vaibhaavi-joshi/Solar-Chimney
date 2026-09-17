"""
The five simulation studies for the STEMathon pitch.

All runs use the same validated model, the same design case and the same
weather unless the study is explicitly varying one of those.

Final design (from the earlier sizing work): 1.5 m long x 2.0 m wide,
0.25 m air gap, 50 degrees tilt, 20 kg paraffin PCM.

Outputs sims_data.json for the website.
"""
import json, math, statistics
from chimney_model import Design, PCM, Room, Weather, simulate, profile
from design_cases import RURAL, URBAN, make_room
from scenarios import SCENARIOS, weather

# ----------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------
FINAL = dict(length=1.5, width=2.0, gap=0.25, tilt_deg=50)
HOT = weather(SCENARIOS[1])          # 44 / 31 C, meets IMD heatwave threshold


def room_for(case, roof_absorptance=None, **over):
    kw = {k: v for k, v in case.items() if k != "name"}
    if roof_absorptance is not None:
        kw["roof_absorptance"] = roof_absorptance
    kw.update(over)
    return Room(**kw)


def chimney(case, **over):
    kw = dict(FINAL)
    kw.update(over)
    kw.setdefault("pcm_mass", 20)
    kw["room_volume"] = case["volume"]
    if kw.get("pcm_mass", 0) <= 0:
        kw["use_pcm"] = False
    return Design(**kw)


def unfitted(case):
    return Design(use_pcm=False, gap=0.002, room_volume=case["volume"])


def night_mean(r, key="T_room"):
    xs, ys = profile(r, key)
    vals = [y for x, y in zip(xs, ys) if x >= 21 or x <= 5]
    return statistics.mean(vals) if vals else 0.0


def peak(r, key="T_room"):
    _, ys = profile(r, key)
    return max(ys)


def window_mean(r, a, b, key="Q"):
    xs, ys = profile(r, key)
    vals = [y for x, y in zip(xs, ys) if a <= x <= b]
    return statistics.mean(vals) if vals else 0.0


def curve(r, key, n=97):
    """Resample a day to n points (15 min spacing)."""
    xs, ys = profile(r, key)
    out = []
    for i in range(n):
        t = i * 24 / (n - 1)
        j = min(range(len(xs)), key=lambda k: abs(xs[k] - t))
        out.append(round(ys[j], 2))
    return out


def draft_hours_after_sunset(r, w, floor=15.0):
    """
    Hours after sunset that useful airflow continues.
    Definition fixed in advance: flow stays above `floor` m3/h.
    """
    xs, ys = profile(r, "Q")
    last = w.sunset
    for x, y in zip(xs, ys):
        if x > w.sunset and y >= floor:
            last = x
    return max(0.0, last - w.sunset)


DATA = {"design": FINAL | {"pcm_mass": 20, "area": FINAL["length"] * FINAL["width"]}}


# ----------------------------------------------------------------------
# SIM 1 — PCM vs no PCM, transient 24 h
# ----------------------------------------------------------------------
def sim1():
    print("\n" + "=" * 70)
    print("SIM 1  PCM vs no PCM over 24 h")
    print("=" * 70)
    out = {}
    for case, ck in ((RURAL, "rural"), (URBAN, "urban")):
        room = room_for(case)
        runs = {
            "none": simulate(unfitted(case), PCM(), HOT, room=room),
            "nopcm": simulate(chimney(case, pcm_mass=0), PCM(), HOT, room=room),
            "pcm": simulate(chimney(case, pcm_mass=20), PCM(), HOT, room=room),
        }
        out[ck] = {k: {m: curve(v, m) for m in
                       ("T_room", "T_amb", "T_abs", "T_pcm", "Q", "liquid")}
                   for k, v in runs.items()}
        b = runs["none"]
        print(f"\n{case['name']}   unfitted peak {peak(b):.1f} C, night {night_mean(b):.1f} C")
        print(f"{'variant':<12}{'peak':>8}{'night':>8}{'eve flow':>10}"
              f"{'draft hrs':>11}{'midnight abs':>14}")
        for k in ("nopcm", "pcm"):
            r = runs[k]
            eve = window_mean(r, HOT.sunset, HOT.sunset + 4)
            hrs = draft_hours_after_sunset(r, HOT)
            _, ab = profile(r, "T_abs")
            print(f"{k:<12}{peak(r):>8.1f}{night_mean(r):>8.1f}{eve:>10.0f}"
                  f"{hrs:>11.1f}{ab[len(ab) // 2 * 0 + int(len(ab) * 0.99)]:>14.1f}")
        stats = {}
        for k in ("none", "nopcm", "pcm"):
            r = runs[k]
            stats[k] = dict(
                peak=round(peak(r), 1), night=round(night_mean(r), 1),
                eve_flow=round(window_mean(r, HOT.sunset, HOT.sunset + 4), 0),
                draft_hrs=round(draft_hours_after_sunset(r, HOT), 1),
                peak_drop=round(peak(runs["none"]) - peak(r), 1),
                night_drop=round(night_mean(runs["none"]) - night_mean(r), 1),
            )
        out[ck]["stats"] = stats
        out[ck]["sunset"] = round(HOT.sunset, 2)
        out[ck]["sunrise"] = round(HOT.sunrise, 2)
    DATA["sim1"] = out


# ----------------------------------------------------------------------
# SIM 2 — PCM mass sweep, and the conditions under which PCM matters
# ----------------------------------------------------------------------
def sim2():
    print("\n" + "=" * 70)
    print("SIM 2  PCM mass sweep")
    print("=" * 70)
    masses = [0, 5, 10, 15, 20, 25, 30]
    out = {"masses": masses, "cases": {}}

    for case, ck in ((RURAL, "rural"), (URBAN, "urban")):
        room = room_for(case)
        rows = []
        print(f"\n{case['name']}")
        print(f"{'kg':>5}{'eve flow':>10}{'vs 0 kg':>10}{'draft hrs':>11}"
              f"{'night C':>9}{'roof load kg':>14}")
        base_eve = None
        for m in masses:
            r = simulate(chimney(case, pcm_mass=m), PCM(), HOT, room=room)
            eve = window_mean(r, HOT.sunset, HOT.sunset + 4)
            if base_eve is None:
                base_eve = eve
            gain = (eve - base_eve) / base_eve * 100 if base_eve else 0
            hrs = draft_hours_after_sunset(r, HOT)
            rows.append(dict(mass=m, eve=round(eve, 0), gain=round(gain, 1),
                             hrs=round(hrs, 1), night=round(night_mean(r), 1)))
            print(f"{m:>5}{eve:>10.0f}{gain:>9.1f}%{hrs:>11.1f}"
                  f"{night_mean(r):>9.1f}{m:>14}")
        out["cases"][ck] = rows

    # --- the reframed question: WHEN does storage start to matter? ---
    print("\nWhen does storage actually earn its place?")
    print(f"{'condition':<34}{'eve gain from 20 kg PCM':>26}")
    conds = []
    for label, case, roomkw, w in [
        ("Rural, hot night (31 C)", RURAL, {}, HOT),
        ("Rural, cool night (22 C)", RURAL, {},
         Weather(T_max=38, T_min=22, wind=1.0, cloud=0.0, dni=900, day_of_year=160)),
        ("Rural, insulated roof", RURAL, dict(roof_U=0.8, thermal_mass=0.8e6), HOT),
        ("Rural, insulated + cool night", RURAL, dict(roof_U=0.8, thermal_mass=0.8e6),
         Weather(T_max=38, T_min=22, wind=1.0, cloud=0.0, dni=900, day_of_year=160)),
        ("Rural, sealed tight (0.3 ACH)", RURAL, dict(infiltration=0.3), HOT),
    ]:
        room = room_for(case, **roomkw)
        a = simulate(chimney(case, pcm_mass=0), PCM(), w, room=room)
        b = simulate(chimney(case, pcm_mass=20), PCM(), w, room=room)
        ea = window_mean(a, w.sunset, w.sunset + 4)
        eb = window_mean(b, w.sunset, w.sunset + 4)
        gain = (eb - ea) / ea * 100 if ea else 0
        conds.append(dict(label=label, gain=round(gain, 1),
                          nopcm=round(ea, 0), pcm=round(eb, 0)))
        print(f"{label:<34}{gain:>25.1f}%")
    out["conditions"] = conds
    DATA["sim2"] = out


# ----------------------------------------------------------------------
# SIM 3 — geometry: area, aspect ratio, air gap
# ----------------------------------------------------------------------
def sim3():
    print("\n" + "=" * 70)
    print("SIM 3  Geometry optimisation")
    print("=" * 70)
    case, ck = RURAL, "rural"
    room = room_for(case)
    base = simulate(unfitted(case), PCM(), HOT, room=room)
    bp, bn = peak(base), night_mean(base)

    # --- 3a: collector area at fixed aspect ---
    print("\nCollector area (1.5 m long, width varied)")
    print(f"{'area m2':>9}{'L x W':>12}{'peak drop':>11}{'night drop':>12}{'flow':>8}")
    area_rows = []
    for W in (0.6, 1.0, 1.33, 2.0, 2.67, 3.33, 4.0):
        d = chimney(case, length=1.5, width=W)
        r = simulate(d, PCM(), HOT, room=room)
        area_rows.append(dict(area=round(1.5 * W, 2), L=1.5, W=W,
                              peak=round(bp - peak(r), 1),
                              night=round(bn - night_mean(r), 1),
                              flow=round(peak(r, "Q"), 0)))
        print(f"{1.5 * W:>9.2f}{f'1.5x{W}':>12}{bp - peak(r):>11.1f}"
              f"{bn - night_mean(r):>12.1f}{peak(r, 'Q'):>8.0f}")

    # --- 3b: same area, different shape ---
    print("\nSame 3.0 m2, different shape (this is the key result)")
    print(f"{'L x W':>12}{'height m':>10}{'peak drop':>11}{'night drop':>12}{'flow':>8}")
    shape_rows = []
    for L, W in ((3.0, 1.0), (2.5, 1.2), (2.0, 1.5), (1.5, 2.0), (1.2, 2.5), (1.0, 3.0)):
        d = chimney(case, length=L, width=W)
        r = simulate(d, PCM(), HOT, room=room)
        h = L * math.sin(math.radians(50))
        shape_rows.append(dict(L=L, W=W, height=round(h, 2),
                               peak=round(bp - peak(r), 1),
                               night=round(bn - night_mean(r), 1),
                               flow=round(peak(r, "Q"), 0)))
        print(f"{f'{L}x{W}':>12}{h:>10.2f}{bp - peak(r):>11.1f}"
              f"{bn - night_mean(r):>12.1f}{peak(r, 'Q'):>8.0f}")

    # --- 3c: air gap ---
    print("\nAir gap (1.5 x 2.0 m collector)")
    print(f"{'gap m':>7}{'peak drop':>11}{'night drop':>12}{'flow':>8}{'dP Pa':>8}")
    gap_rows = []
    for g in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50):
        d = chimney(case, gap=g)
        r = simulate(d, PCM(), HOT, room=room)
        gap_rows.append(dict(gap=g, peak=round(bp - peak(r), 1),
                             night=round(bn - night_mean(r), 1),
                             flow=round(peak(r, "Q"), 0),
                             dP=round(peak(r, "dP"), 2)))
        print(f"{g:>7.2f}{bp - peak(r):>11.1f}{bn - night_mean(r):>12.1f}"
              f"{peak(r, 'Q'):>8.0f}{peak(r, 'dP'):>8.2f}")

    DATA["sim3"] = dict(area=area_rows, shape=shape_rows, gap=gap_rows,
                        base_peak=round(bp, 1), base_night=round(bn, 1))


# ----------------------------------------------------------------------
# SIM 4 — tilt angle
# ----------------------------------------------------------------------
def sim4():
    print("\n" + "=" * 70)
    print("SIM 4  Tilt angle")
    print("=" * 70)
    tilts = [20, 30, 40, 50, 60, 70, 80, 90]
    out = {"tilts": tilts, "cases": {}}
    for case, ck in ((RURAL, "rural"), (URBAN, "urban")):
        room = room_for(case)
        base = simulate(unfitted(case), PCM(), HOT, room=room)
        bp, bn = peak(base), night_mean(base)
        rows = []
        print(f"\n{case['name']}")
        print(f"{'tilt':>6}{'solar kWh/m2':>14}{'height m':>10}"
              f"{'peak drop':>11}{'night drop':>12}{'flow':>8}")
        for t in tilts:
            d = chimney(case, tilt_deg=t)
            r = simulate(d, PCM(), HOT, room=room)
            xs, I = profile(r, "I")
            kwh = sum(I) * (24 / len(I)) / 1000
            h = FINAL["length"] * math.sin(math.radians(t))
            rows.append(dict(tilt=t, kwh=round(kwh, 2), height=round(h, 2),
                             peak=round(bp - peak(r), 1),
                             night=round(bn - night_mean(r), 1),
                             flow=round(peak(r, "Q"), 0)))
            print(f"{t:>6}{kwh:>14.2f}{h:>10.2f}{bp - peak(r):>11.1f}"
                  f"{bn - night_mean(r):>12.1f}{peak(r, 'Q'):>8.0f}")
        out["cases"][ck] = rows
    DATA["sim4"] = out


# ----------------------------------------------------------------------
# SIM 5 — six cities, four climate zones
# ----------------------------------------------------------------------
CITIES = [
    dict(key="jaipur", name="Jaipur", zone="Hot-dry", lat=26.9,
         T_max=40.5, T_min=27.5, month="May", doy=135, dni=920, cloud=0.02,
         source="IMD Climate of Jaipur: May normals 40.5 / 27.5 C"),
    dict(key="ahmedabad", name="Ahmedabad", zone="Hot-dry", lat=23.0,
         T_max=42.0, T_min=28.0, month="May", doy=135, dni=920, cloud=0.03,
         source="IMD Climate of Ahmedabad: end-May normal max ~42 C, min ~28 C"),
    dict(key="delhi", name="Delhi", zone="Composite", lat=28.5,
         T_max=39.5, T_min=27.5, month="May", doy=135, dni=900, cloud=0.05,
         source="IMD: May mean max 39.5 C"),
    dict(key="chennai", name="Chennai", zone="Warm-humid", lat=13.1,
         T_max=38.4, T_min=27.5, month="May", doy=135, dni=850, cloud=0.15,
         source="May normals 38.4 / 27.5 C, warmest month"),
    dict(key="mumbai", name="Mumbai", zone="Warm-humid", lat=19.1,
         T_max=34.0, T_min=27.3, month="May", doy=135, dni=820, cloud=0.20,
         source="Mean daily max 34.0 C, min 27.3 C in May"),
    dict(key="bengaluru", name="Bengaluru", zone="Temperate", lat=13.0,
         T_max=34.1, T_min=22.0, month="April", doy=105, dni=870, cloud=0.12,
         source="IMD normal April max 34.1 C, min ~22 C"),
]


def sim5():
    print("\n" + "=" * 70)
    print("SIM 5  Six cities, four climate zones")
    print("=" * 70)
    out = {"cities": [], "note": "Model has no humidity term."}
    for c in CITIES:
        w = Weather(T_max=c["T_max"], T_min=c["T_min"], dni=c["dni"],
                    cloud=c["cloud"], wind=1.2, day_of_year=c["doy"])
        row = dict(c)
        for case, ck in ((RURAL, "rural"), (URBAN, "urban")):
            room = room_for(case)
            b = simulate(unfitted(case), PCM(), w, room=room)
            r = simulate(chimney(case), PCM(), w, room=room)
            row[ck] = dict(
                base_peak=round(peak(b), 1), base_night=round(night_mean(b), 1),
                peak=round(peak(r), 1), night=round(night_mean(r), 1),
                peak_drop=round(peak(b) - peak(r), 1),
                night_drop=round(night_mean(b) - night_mean(r), 1),
                flow=round(peak(r, "Q"), 0),
            )
            row[ck + "_curve"] = curve(r, "T_room")
            row[ck + "_base_curve"] = curve(b, "T_room")
        row["amb_curve"] = curve(simulate(chimney(RURAL), PCM(), w,
                                          room=room_for(RURAL)), "T_amb")
        out["cities"].append(row)

    print(f"{'city':<12}{'zone':<13}{'outdoor':>10}"
          f"{'rural peak':>12}{'rural night':>13}{'urban peak':>12}{'urban night':>13}")
    for r in out["cities"]:
        print(f"{r['name']:<12}{r['zone']:<13}{f'{r[chr(84)+chr(95)+chr(109)+chr(97)+chr(120)]:.0f}/{r[chr(84)+chr(95)+chr(109)+chr(105)+chr(110)]:.0f}':>10}"
              f"{r['rural']['peak_drop']:>12.1f}{r['rural']['night_drop']:>13.1f}"
              f"{r['urban']['peak_drop']:>12.1f}{r['urban']['night_drop']:>13.1f}")
    DATA["sim5"] = out


# ----------------------------------------------------------------------
# SIM 6 — what actually limits performance
# ----------------------------------------------------------------------
def sim6():
    print("\n" + "=" * 70)
    print("SIM 6  What actually limits performance")
    print("=" * 70)
    out = {"saturation": {}, "solar": []}

    # --- 6a: does more airflow keep buying temperature drop? ---
    for case, ck in ((RURAL, "rural"), (URBAN, "urban")):
        room = room_for(case)
        b = peak(simulate(unfitted(case), PCM(), HOT, room=room))
        rows = []
        print(f"\n{case['name']}  unfitted peak {b:.1f} C")
        print(f"{'area m2':>8}{'peak flow':>11}{'ACH':>7}{'peak drop':>11}"
              f"{'K per extra 100 m3/h':>22}")
        prev = None
        for W in (0.4, 0.6, 1.0, 1.33, 2.0, 3.0, 4.0, 6.0, 8.0):
            r = simulate(chimney(case, length=1.5, width=W), PCM(), HOT, room=room)
            q = peak(r, "Q"); dk = b - peak(r)
            marg = None if prev is None else (dk - prev[1]) / ((q - prev[0]) / 100)
            rows.append(dict(area=round(1.5 * W, 1), flow=round(q, 0),
                             ach=round(q / case["volume"], 1), drop=round(dk, 1),
                             marginal=None if marg is None else round(marg, 2)))
            print(f"{1.5 * W:>8.1f}{q:>11.0f}{q / case['volume']:>7.1f}{dk:>11.1f}"
                  f"{'' if marg is None else f'{marg:.2f}':>22}")
            prev = (q, dk)
        out["saturation"][ck] = dict(rows=rows, base=round(b, 1))

    # --- 6b: how much is the solar collector actually contributing? ---
    print("\nSolar collector vs an identical unglazed duct")
    print(f"{'condition':<34}{'vent m3/h':>11}{'solar m3/h':>12}"
          f"{'flow gain':>11}{'vent dK':>9}{'solar dK':>10}")
    conds = [
        ("Rural metal roof, hot day", RURAL, {}, HOT),
        ("Urban concrete, hot day", URBAN, {}, HOT),
        ("Rural insulated roof", RURAL, dict(roof_U=0.8, thermal_mass=0.8e6), HOT),
        ("Rural insulated + cool roof", RURAL,
         dict(roof_U=0.8, roof_absorptance=0.25, thermal_mass=0.8e6), HOT),
        ("Rural, mild day (34 C)", RURAL, {},
         Weather(T_max=34, T_min=22, wind=1.0, cloud=0.0, dni=900, day_of_year=160)),
    ]
    for label, case, rk, w in conds:
        room = room_for(case, **rk)
        b = peak(simulate(unfitted(case), PCM(), w, room=room))
        r = simulate(chimney(case), PCM(), w, room=room)
        d = chimney(case); d.alpha_abs = 0.15; d.tau_glass = 0.0
        v = simulate(d, PCM(), w, room=room)
        gain = (peak(r, "Q") - peak(v, "Q")) / peak(v, "Q") * 100
        out["solar"].append(dict(label=label, vent=round(peak(v, "Q"), 0),
                                 solar=round(peak(r, "Q"), 0), gain=round(gain, 1),
                                 vent_dk=round(b - peak(v), 1),
                                 solar_dk=round(b - peak(r), 1)))
        print(f"{label:<34}{peak(v, 'Q'):>11.0f}{peak(r, 'Q'):>12.0f}"
              f"{gain:>10.1f}%{b - peak(v):>9.1f}{b - peak(r):>10.1f}")
    DATA["sim6"] = out


if __name__ == "__main__":
    sim1(); sim2(); sim3(); sim4(); sim5(); sim6()
    with open("/home/claude/sims_data.json", "w") as f:
        json.dump(DATA, f, separators=(",", ":"))
    print(f"\n\nExported sims_data.json "
          f"({len(json.dumps(DATA)) // 1024} KB)")
