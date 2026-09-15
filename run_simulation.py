"""
Runs the solar chimney model and produces every number and graph used in
the STEMathon pitch.

Usage:  python3 run_simulation.py
Graphs are written next to this script.
"""

import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from chimney_model import (Design, PCM, Room, Weather, simulate, profile,
                           draft_hours_after_sunset, daytime_average_flow,
                           evening_average_flow, peak, melted_fraction)

OUT = os.environ.get("CHIMNEY_OUT", "/mnt/user-data/outputs")

C_PCM = "#C2410C"
C_CTRL = "#0F766E"
C_NONE = "#94A3B8"
C_AMB = "#1D4ED8"
C_STORE = "#7C3AED"


def night_mean(results, key):
    """Average of a quantity between 20:00 and 05:00."""
    xs, ys = profile(results, key)
    vals = [y for x, y in zip(xs, ys) if x >= 20 or x <= 5]
    return statistics.mean(vals) if vals else 0.0


def banner(text):
    print("\n" + "=" * 68)
    print(text)
    print("=" * 68)


def build(use_pcm=True, **kw):
    return Design(use_pcm=use_pcm, **kw)


NO_CHIMNEY = Design(use_pcm=False, gap=0.002)   # sealed: represents no chimney


# ----------------------------------------------------------------------
def main_result():
    banner("MAIN RESULT  |  clear Delhi summer day, 44 C max / 31 C min")

    w, p = Weather(), PCM()
    cases = {
        "No chimney": simulate(NO_CHIMNEY, p, w),
        "Chimney, no PCM": simulate(build(False), p, w),
        "Chimney + 20 kg PCM": simulate(build(True), p, w),
    }

    print(f"{'':24s}{'peak indoor':>13s}{'night indoor':>14s}"
          f"{'day flow':>11s}{'evening flow':>14s}")
    print(f"{'':24s}{'(C)':>13s}{'(C)':>14s}{'(m3/h)':>11s}{'(m3/h)':>14s}")
    for name, r in cases.items():
        print(f"{name:24s}{peak(r,'T_room'):13.1f}{night_mean(r,'T_room'):14.2f}"
              f"{daytime_average_flow(r,w):11.0f}{evening_average_flow(r,w):14.0f}")

    amb_night = night_mean(cases["No chimney"], "T_amb")
    print(f"\nOutdoor night average: {amb_night:.2f} C")

    base = night_mean(cases["No chimney"], "T_room")
    for name in ["Chimney, no PCM", "Chimney + 20 kg PCM"]:
        drop = base - night_mean(cases[name], "T_room")
        print(f"  {name}: night indoor temperature {drop:.2f} K lower than no chimney")

    r_pcm, r_ctrl = cases["Chimney + 20 kg PCM"], cases["Chimney, no PCM"]
    gain = evening_average_flow(r_pcm, w) / evening_average_flow(r_ctrl, w) - 1
    print(f"\nPCM effect on evening airflow: {gain:+.1%}")
    print(f"PCM melted fraction reached:   {melted_fraction(r_pcm):.0%}")
    print(f"Absorber peak, no PCM:         {peak(r_ctrl,'T_abs'):.1f} C")
    print(f"Absorber peak, with PCM:       {peak(r_pcm,'T_abs'):.1f} C")
    print(f"Absorber at midnight, no PCM:  {value_at(r_ctrl,'T_abs',0):.1f} C")
    print(f"Absorber at midnight, PCM:     {value_at(r_pcm,'T_abs',0):.1f} C")
    print(f"Peak stack pressure:           {peak(r_pcm,'dP'):.2f} Pa")
    print(f"Peak outlet velocity:          {peak(r_pcm,'velocity'):.2f} m/s")
    print(f"Peak air changes per hour:     {peak(r_pcm,'ACH'):.1f}")

    plot_indoor(cases, w)
    plot_flow(cases, w)
    plot_temperatures(r_pcm, w)
    return cases


def value_at(results, key, hour):
    xs, ys = profile(results, key)
    i = min(range(len(xs)), key=lambda k: abs(xs[k] - hour))
    return ys[i]


# ----------------------------------------------------------------------
def plot_indoor(cases, w):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    xs, amb = profile(cases["No chimney"], "T_amb")
    ax.plot(xs, amb, color=C_AMB, lw=1.8, ls="--", label="Outdoor air")
    for (name, r), colour in zip(cases.items(), [C_NONE, C_CTRL, C_PCM]):
        x, y = profile(r, "T_room")
        ax.plot(x, y, color=colour, lw=2.3, label=name)
    ax.axvspan(w.sunset, 24, color="#1E293B", alpha=0.05)
    ax.axvspan(0, w.sunrise, color="#1E293B", alpha=0.05)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Indoor air temperature (C)")
    ax.set_title("Simulated indoor temperature in a 30 m$^3$ room under an uninsulated roof")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(f"{OUT}/01_indoor_temperature.png", dpi=160)
    plt.close(fig)


def plot_flow(cases, w):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for (name, r), colour in zip(list(cases.items())[1:], [C_CTRL, C_PCM]):
        x, y = profile(r, "Q")
        ax.plot(x, y, color=colour, lw=2.3, label=name)
    ax.axvline(w.sunset, color="#111", ls="--", lw=1)
    ax.annotate("sunset", xy=(w.sunset + 0.2, 20), fontsize=9)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Airflow through the chimney (m$^3$/h)")
    ax.set_title("Ventilation rate over 24 hours")
    ax.set_xlim(0, 24)
    ax.set_ylim(bottom=0)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(f"{OUT}/02_airflow.png", dpi=160)
    plt.close(fig)


def plot_temperatures(r, w):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for key, colour, label in [("T_abs", C_PCM, "Absorber plate"),
                               ("T_pcm", C_STORE, "PCM (paraffin)"),
                               ("T_air", "#0891B2", "Channel air"),
                               ("T_room", "#334155", "Indoor air"),
                               ("T_amb", C_AMB, "Outdoor air")]:
        x, y = profile(r, key)
        ax.plot(x, y, color=colour, lw=2, label=label)
    ax.axhline(50, color="#999", ls=":", lw=1.2)
    ax.annotate("PCM melting point", xy=(0.4, 51), fontsize=9, color="#666")
    ax.axvline(w.sunset, color="#111", ls="--", lw=1)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Temperature (C)")
    ax.set_title("Where the heat sits: the PCM holds ~50 C long after the sun goes down")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(frameon=False, fontsize=9, ncol=2)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(f"{OUT}/03_node_temperatures.png", dpi=160)
    plt.close(fig)


# ----------------------------------------------------------------------
def scenarios():
    banner("WEATHER SCENARIOS")
    p = PCM()
    sets = {
        "Normal summer (44/31 C)": Weather(),
        "Heatwave (47/35 C)": Weather(T_max=47, T_min=35),
        "Hazy, dusty day": Weather(cloud=0.35),
        "Monsoon overcast": Weather(dni=700, T_max=36, T_min=29, cloud=0.7),
    }
    print(f"{'Scenario':28s}{'day m3/h':>10s}{'eve m3/h':>10s}"
          f"{'melt':>7s}{'night drop K':>14s}")
    store = {}
    for name, w in sets.items():
        rp = simulate(build(True), p, w)
        rn = simulate(NO_CHIMNEY, p, w)
        drop = night_mean(rn, "T_room") - night_mean(rp, "T_room")
        print(f"{name:28s}{daytime_average_flow(rp,w):10.0f}"
              f"{evening_average_flow(rp,w):10.0f}{melted_fraction(rp):7.0%}"
              f"{drop:14.2f}")
        store[name] = (rp, w)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    for (name, (r, w)), colour in zip(store.items(),
                                      [C_PCM, "#B91C1C", "#CA8A04", "#0F766E"]):
        x, y = profile(r, "Q")
        ax.plot(x, y, lw=2.2, color=colour, label=name)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Airflow (m$^3$/h)")
    ax.set_title("Performance across weather conditions")
    ax.set_xlim(0, 24)
    ax.set_ylim(bottom=0)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(f"{OUT}/04_weather_scenarios.png", dpi=160)
    plt.close(fig)


# ----------------------------------------------------------------------
def sensitivity():
    banner("SENSITIVITY  |  which design choices actually move the needle")
    w, p = Weather(), PCM()

    def run(**kw):
        r = simulate(build(True, **kw), p, w)
        rn = simulate(NO_CHIMNEY, p, w)
        return (daytime_average_flow(r, w), evening_average_flow(r, w),
                night_mean(rn, "T_room") - night_mean(r, "T_room"))

    print("\nTilt angle (south facing, 21 June, Gurgaon 28.5 N)")
    print(f"{'deg':>5s}{'kWh/m2/day':>12s}{'day m3/h':>10s}{'eve m3/h':>10s}{'night drop K':>14s}")
    tilts, tilt_day, tilt_energy = [], [], []
    for tilt in [15, 20, 30, 40, 45, 50, 60, 75, 90]:
        d = build(True, tilt_deg=tilt)
        daily = sum(w.irradiance(t / 20, d.tilt) for t in range(0, 480)) / 20 / 1000
        dayf, evef, drop = run(tilt_deg=tilt)
        print(f"{tilt:5d}{daily:12.2f}{dayf:10.0f}{evef:10.0f}{drop:14.2f}")
        tilts.append(tilt); tilt_day.append(dayf); tilt_energy.append(daily)

    print("\nAir gap")
    print(f"{'m':>6s}{'day m3/h':>10s}{'eve m3/h':>10s}{'night drop K':>14s}")
    gaps, gap_day = [], []
    for gap in [0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]:
        dayf, evef, drop = run(gap=gap)
        print(f"{gap:6.2f}{dayf:10.0f}{evef:10.0f}{drop:14.2f}")
        gaps.append(gap); gap_day.append(dayf)

    print("\nCollector size (gap 0.2 m, tilt 45)")
    print(f"{'m2':>6s}{'day m3/h':>10s}{'eve m3/h':>10s}{'night drop K':>14s}")
    areas, area_drop = [], []
    for L, W in [(1.5, 0.5), (2, 0.5), (2, 1.0), (2, 1.5), (3, 1.0), (3, 1.5)]:
        dayf, evef, drop = run(length=L, width=W)
        print(f"{L*W:6.1f}{dayf:10.0f}{evef:10.0f}{drop:14.2f}")
        areas.append(L * W); area_drop.append(drop)

    print("\nPCM mass (evening flow vs no PCM)")
    base_eve = evening_average_flow(simulate(build(False), p, w), w)
    print(f"{'kg':>5s}{'eve m3/h':>10s}{'vs no PCM':>12s}")
    masses, mass_gain = [], []
    for m in [0, 5, 10, 20, 30, 40, 60]:
        r = simulate(build(m > 0, pcm_mass=m), p, w)
        ev = evening_average_flow(r, w)
        print(f"{m:5d}{ev:10.0f}{(ev/base_eve-1)*100:11.1f}%")
        masses.append(m); mass_gain.append((ev / base_eve - 1) * 100)

    print("\nPCM melting point, 20 kg")
    print(f"{'Tm C':>6s}{'normal night':>14s}{'heatwave night':>16s}   (evening m3/h)")
    w_hot = Weather(T_max=47, T_min=35)
    melts, m_norm, m_hot = [], [], []
    for tm in [32, 38, 44, 50, 56, 62]:
        pm = PCM(T_melt=tm)
        a = evening_average_flow(simulate(build(True), pm, w), w)
        b = evening_average_flow(simulate(build(True), pm, w_hot), w_hot)
        print(f"{tm:6d}{a:14.0f}{b:16.0f}")
        melts.append(tm); m_norm.append(a); m_hot.append(b)

    print("\nFins in the PCM trays and the night cover (20 kg)")
    for label, kw in [("plain trays", {}), ("with fins", {"fins": True}),
                      ("night cover", {"night_cover": True}),
                      ("fins + cover", {"fins": True, "night_cover": True})]:
        dayf, evef, drop = run(**kw)
        print(f"  {label:14s} evening {evef:5.0f} m3/h   night drop {drop:.2f} K")

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.5))
    ax = axes[0][0]
    ax.plot(tilts, tilt_energy, "o-", color=C_PCM)
    ax.set_xlabel("Tilt from horizontal (degrees)")
    ax.set_ylabel("Daily solar energy collected (kWh/m$^2$)")
    ax.set_title("A vertical wall collects almost nothing in June")
    ax.grid(alpha=0.2)

    ax = axes[0][1]
    ax.plot(tilts, tilt_day, "o-", color=C_CTRL)
    ax.set_xlabel("Tilt from horizontal (degrees)")
    ax.set_ylabel("Daytime airflow (m$^3$/h)")
    ax.set_title("Tilt: sunlight gained vs stack height lost")
    ax.grid(alpha=0.2)

    ax = axes[1][0]
    ax.plot(gaps, gap_day, "o-", color=C_PCM)
    ax.set_xlabel("Air gap (m)")
    ax.set_ylabel("Daytime airflow (m$^3$/h)")
    ax.set_title("Air gap width")
    ax.grid(alpha=0.2)

    ax = axes[1][1]
    ax.plot(melts, m_norm, "o-", color=C_PCM, label="Normal night (31 C)")
    ax.plot(melts, m_hot, "o-", color="#B91C1C", label="Heatwave night (35 C)")
    ax.set_xlabel("PCM melting point (C)")
    ax.set_ylabel("Evening airflow (m$^3$/h)")
    ax.set_title("Choosing the melting point")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.2)

    fig.suptitle("Design sensitivity", y=0.995)
    fig.tight_layout()
    fig.savefig(f"{OUT}/05_sensitivity.png", dpi=160)
    plt.close(fig)


# ----------------------------------------------------------------------
def validation():
    banner("VALIDATION against published experiments")
    p = PCM()

    print("Ong & Chow (2003): vertical, 0.3 m gap, up to 650 W/m2")
    print("  measured air velocity 0.25 - 0.39 m/s")
    w = Weather(dni=800, T_max=33, T_min=25, day_of_year=80)
    d = Design(length=2.0, width=0.45, gap=0.3, tilt_deg=90, use_pcm=False)
    r = simulate(d, p, w, fixed_room_offset=0.0)
    print(f"  model peak velocity: {peak(r,'velocity'):.2f} m/s")

    print("\nBansal et al.: small window-sized chimney")
    print("  measured velocity up to 0.24 m/s")
    d = Design(length=1.0, width=0.5, gap=0.1, tilt_deg=90, use_pcm=False)
    r = simulate(d, p, w, fixed_room_offset=0.0)
    print(f"  model peak velocity: {peak(r,'velocity'):.2f} m/s")

    print("\nMathur et al.: 1 m absorber, 27 m3 room, 700 W/m2")
    print("  measured 5.6 air changes per hour")
    d = Design(length=1.0, width=1.0, gap=0.35, tilt_deg=90,
               use_pcm=False, room_volume=27.0)
    r = simulate(d, p, w, fixed_room_offset=0.0)
    print(f"  model peak ACH: {peak(r,'ACH'):.1f}")

    print("\nKhedari et al.: 25 m3 test house, measured 8 - 15 ACH")
    d = Design(length=2.0, width=1.0, gap=0.14, tilt_deg=90,
               use_pcm=False, room_volume=25.0)
    r = simulate(d, p, w, fixed_room_offset=0.0)
    print(f"  model peak ACH: {peak(r,'ACH'):.1f}")

    print("\nThese rigs sat at outdoor temperature, so the room is pinned")
    print("to ambient here (fixed_room_offset=0) to match their conditions.")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    main_result()
    scenarios()
    sensitivity()
    validation()
    print(f"\nGraphs written to {OUT}")
