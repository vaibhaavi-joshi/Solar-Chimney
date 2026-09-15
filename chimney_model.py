"""
Transient global energy balance (GEB) model of a roof-mounted solar chimney
with a phase change material (PCM) heat store.

Nodes: glass  ->  air channel  ->  absorber  ->  PCM  ->  insulation  ->  room

Method
------
- Glass, absorber and PCM are solved by explicit time stepping.
- The channel air has almost no thermal mass, so it is solved quasi-steadily
  (algebraically) each step. This is more accurate and numerically stable,
  and it is what published GEB models do.
- The PCM uses the effective heat capacity method: latent heat is smeared
  across the melting range so it appears as a spike in specific heat.
- Airflow comes from balancing stack (buoyancy) pressure against friction
  and minor losses, solved by iteration together with the air temperature.

All units are SI unless the variable name says otherwise.
"""

import math

# ----------------------------------------------------------------------
# PHYSICAL CONSTANTS
# ----------------------------------------------------------------------
SIGMA = 5.67e-8       # Stefan-Boltzmann constant, W/m^2K^4
G = 9.81              # gravity, m/s^2
CP_AIR = 1005.0       # specific heat of air, J/kgK
R_AIR = 287.0         # gas constant for air, J/kgK
K_AIR = 0.0263        # thermal conductivity of air, W/mK
NU_AIR = 1.8e-5       # kinematic viscosity of air, m^2/s
PR_AIR = 0.71         # Prandtl number of air
P_ATM = 101325.0      # atmospheric pressure, Pa

LATITUDE = 28.5       # Gurgaon, degrees north


def air_density(T_celsius):
    """Ideal gas law rearranged for density: rho = P / (R T)."""
    return P_ATM / (R_AIR * (T_celsius + 273.15))


# ----------------------------------------------------------------------
# SOLAR GEOMETRY
# ----------------------------------------------------------------------
def solar_position(t_hours, day_of_year=172):
    """
    Returns (solar altitude, azimuth measured from south) in radians.
    day_of_year 172 = 21 June, when the sun is highest over north India.
    """
    decl = math.radians(23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365)))
    lat = math.radians(LATITUDE)
    hour_angle = math.radians(15 * (t_hours - 12))

    sin_alt = (math.sin(lat) * math.sin(decl) +
               math.cos(lat) * math.cos(decl) * math.cos(hour_angle))
    sin_alt = max(-1.0, min(1.0, sin_alt))
    altitude = math.asin(sin_alt)

    if math.cos(altitude) < 1e-6:
        return altitude, 0.0
    cos_az = ((math.sin(altitude) * math.sin(lat) - math.sin(decl)) /
              (math.cos(altitude) * math.cos(lat)))
    cos_az = max(-1.0, min(1.0, cos_az))
    azimuth = math.acos(cos_az)
    if hour_angle < 0:
        azimuth = -azimuth
    return altitude, azimuth


def incidence_factor(t_hours, tilt_rad, day_of_year=172):
    """
    cos(theta) for a south-facing surface tilted from horizontal: the
    fraction of the direct beam the surface actually catches. A vertical
    wall scores badly in June because the sun is almost overhead.
    """
    altitude, azimuth = solar_position(t_hours, day_of_year)
    if altitude <= 0:
        return 0.0
    cos_theta = (math.cos(altitude) * math.sin(tilt_rad) * math.cos(azimuth) +
                 math.sin(altitude) * math.cos(tilt_rad))
    return max(0.0, cos_theta)


# ----------------------------------------------------------------------
# DESIGN
# ----------------------------------------------------------------------
class Design:
    """Everything about how the chimney is built."""

    def __init__(self,
                 length=2.0,          # along-slope length, m
                 width=0.5,           # width, m
                 gap=0.2,             # air gap between glass and absorber, m
                 tilt_deg=45.0,       # tilt from horizontal, degrees
                 pcm_mass=20.0,       # kg of PCM
                 use_pcm=True,
                 fins=False,          # aluminium fins inside the PCM trays
                 night_cover=False,   # insulated cover over the glass at night
                 tau_glass=0.85,      # solar transmittance of the glass
                 alpha_abs=0.92,      # absorptance of the black absorber
                 eps_abs=0.90,        # emissivity of the absorber
                 eps_glass=0.88,      # longwave emissivity of the glass
                 K_minor=6.0,         # inlet 0.5 + exit 1.0 + 2 bends 2.4 + mesh 1.5 + cap 0.6
                 insul_U=0.7,         # U-value, chimney back to room, W/m^2K
                 room_volume=30.0):   # notional room served, m^3

        if not use_pcm:
            pcm_mass = 0.0

        self.length = length
        self.width = width
        self.gap = gap
        self.tilt = math.radians(tilt_deg)
        self.tilt_deg = tilt_deg
        self.pcm_mass = pcm_mass
        self.use_pcm = use_pcm and pcm_mass > 0
        self.fins = fins
        self.night_cover = night_cover
        self.tau_glass = tau_glass
        self.alpha_abs = alpha_abs
        self.eps_abs = eps_abs
        self.eps_glass = eps_glass
        self.K_minor = K_minor
        self.insul_U = insul_U
        self.room_volume = room_volume

        self.area = length * width                   # collector area, m^2
        self.opening = gap * width                   # flow cross-section, m^2
        self.height = length * math.sin(self.tilt)   # VERTICAL height, m
        self.Dh = 2 * gap * width / (gap + width)    # hydraulic diameter, m

        self.C_glass = 0.004 * self.area * 2500 * 840    # 4 mm glass, J/K
        self.C_abs = 0.001 * self.area * 2700 * 900      # 1 mm aluminium, J/K

    def pcm_thickness(self, density=850.0):
        if self.pcm_mass <= 0:
            return 0.0
        return (self.pcm_mass / density) / self.area


# ----------------------------------------------------------------------
# PCM
# ----------------------------------------------------------------------
class PCM:
    def __init__(self,
                 name="Paraffin",
                 T_melt=50.0,      # melting point, C
                 glide=4.0,        # melts across this range, C
                 latent=200e3,     # latent heat, J/kg
                 cp_solid=2000.0,
                 cp_liquid=2200.0,
                 k=0.2,            # thermal conductivity, W/mK
                 density=850.0):
        self.name = name
        self.T_melt = T_melt
        self.glide = glide
        self.latent = latent
        self.cp_solid = cp_solid
        self.cp_liquid = cp_liquid
        self.k = k
        self.density = density

    def effective_cp(self, T):
        lo = self.T_melt - self.glide / 2
        hi = self.T_melt + self.glide / 2
        if T < lo:
            return self.cp_solid
        if T > hi:
            return self.cp_liquid
        return 0.5 * (self.cp_solid + self.cp_liquid) + self.latent / self.glide

    def liquid_fraction(self, T):
        lo = self.T_melt - self.glide / 2
        hi = self.T_melt + self.glide / 2
        return min(1.0, max(0.0, (T - lo) / (hi - lo)))


# ----------------------------------------------------------------------
# WEATHER
# ----------------------------------------------------------------------
class Weather:
    """Clear-sky Delhi summer day, with optional cloud and dust."""

    def __init__(self,
                 dni=900.0,        # peak direct normal irradiance, W/m^2
                 diffuse=110.0,    # diffuse sky radiation, W/m^2
                 T_max=44.0,       # daily maximum air temperature, C
                 T_min=31.0,       # night minimum, C
                 cloud=0.0,        # 0 = clear, 1 = fully overcast
                 wind=1.0,         # m/s at the outlet
                 day_of_year=172):
        self.dni = dni
        self.diffuse = diffuse
        self.T_max = T_max
        self.T_min = T_min
        self.cloud = cloud
        self.wind = wind
        self.day_of_year = day_of_year

        decl = math.radians(23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365)))
        lat = math.radians(LATITUDE)
        cos_hs = max(-1.0, min(1.0, -math.tan(lat) * math.tan(decl)))
        half_day = math.degrees(math.acos(cos_hs)) / 15.0
        self.sunrise = 12 - half_day
        self.sunset = 12 + half_day

    def irradiance(self, t_hours, tilt_rad):
        """Total radiation striking the tilted glass, W/m^2."""
        t = t_hours % 24
        altitude, _ = solar_position(t, self.day_of_year)
        if altitude <= 0:
            return 0.0
        air_mass = 1.0 / max(math.sin(altitude), 0.05)
        beam = self.dni * (0.7 ** (air_mass ** 0.678)) * (1 - 0.85 * self.cloud)
        diff = self.diffuse * (1 + 0.4 * self.cloud) * (1 + math.cos(tilt_rad)) / 2
        return beam * incidence_factor(t, tilt_rad, self.day_of_year) + diff

    def T_ambient(self, t_hours):
        t = t_hours % 24
        mean = (self.T_max + self.T_min) / 2
        amp = (self.T_max - self.T_min) / 2
        return mean - amp * math.cos(2 * math.pi * (t - 3) / 24)

    def T_sky(self, t_hours):
        """The clear night sky behaves like a very cold surface."""
        Ta = self.T_ambient(t_hours)
        clear = 0.0552 * (Ta + 273.15) ** 1.5 - 273.15
        return clear + self.cloud * (Ta - clear)


# ----------------------------------------------------------------------
# HEAT TRANSFER
# ----------------------------------------------------------------------
def h_wind(wind_speed):
    return 5.7 + 3.8 * wind_speed


def h_channel(T_surface, T_air, design, velocity):
    """
    Convection inside the channel. Forced convection when air is moving,
    natural convection as a floor. This coefficient is only a few W/m^2K,
    which is the main bottleneck on getting heat into the air.
    """
    T_film = 0.5 * (T_surface + T_air) + 273.15
    Re = max(velocity, 1e-6) * design.Dh / NU_AIR

    if Re > 2300:
        Nu = 0.023 * Re ** 0.8 * PR_AIR ** 0.4
    else:
        gz = Re * PR_AIR * design.Dh / design.length
        Nu = 5.4 + (0.025 * gz ** 1.4) / (1 + 0.0012 * gz ** 0.8)
    h_forced = Nu * K_AIR / design.Dh

    dT = abs(T_surface - T_air)
    if dT > 0.01:
        Ra = (G * dT * design.gap ** 3 * PR_AIR) / (T_film * NU_AIR ** 2)
        Ra *= math.sin(design.tilt)
        Nu_nat = 0.68 + 0.67 * max(Ra, 1.0) ** 0.25 / \
            (1 + (0.492 / PR_AIR) ** (9 / 16)) ** (4 / 9)
        h_nat = max(1.0, Nu_nat) * K_AIR / design.gap
    else:
        h_nat = 1.5

    return max(h_forced, h_nat, 1.5)


def h_radiation(T1, T2, eps1, eps2):
    T1k, T2k = T1 + 273.15, T2 + 273.15
    denom = 1 / eps1 + 1 / eps2 - 1
    return SIGMA * (T1k ** 2 + T2k ** 2) * (T1k + T2k) / denom


def h_pcm_to_absorber(pcm, design, liquid_frac):
    """
    Conductance between PCM and absorber. At night a solid crust grows
    against the plate and insulates the liquid behind it, so this gets
    worse as the PCM discharges. Fins short-circuit that path.
    """
    if design.pcm_mass <= 0:
        return 0.0
    thickness = design.pcm_thickness(pcm.density)
    solid_path = max(thickness * (1 - liquid_frac) * 0.5, 0.0015)
    h = pcm.k / solid_path
    if design.fins:
        h *= 4.0
    return min(h, 400.0)


def friction_factor(Re):
    if Re < 1e-6:
        return 1.0
    if Re < 2300:
        return 64.0 / Re
    return 0.316 * Re ** -0.25


# ----------------------------------------------------------------------
# AIRFLOW
# ----------------------------------------------------------------------
def solve_flow(T_channel, T_ambient, design, weather):
    """
    Finds the velocity where buoyancy balances friction and minor losses.
    Returns (volume flow m^3/s, velocity m/s, stack pressure Pa).
    """
    dT = T_channel - T_ambient
    if dT <= 0.02 or design.height <= 0.01:
        return 0.0, 0.0, 0.0

    T_mean = 0.5 * (T_channel + T_ambient)
    rho = air_density(T_mean)
    dP = rho * G * design.height * (dT / (T_mean + 273.15))
    dP += 0.3 * 0.5 * air_density(T_ambient) * weather.wind ** 2

    v = 0.3
    for _ in range(40):
        Re = v * design.Dh / NU_AIR
        K_total = friction_factor(Re) * design.length / design.Dh + design.K_minor
        v_new = math.sqrt(2 * dP / (rho * K_total))
        if abs(v_new - v) < 1e-5:
            v = v_new
            break
        v = 0.5 * v + 0.5 * v_new

    return v * design.opening, v, dP


def channel_air_temperature(T_abs, T_glass, T_room, design, mdot, h_pa, h_ga):
    """
    Quasi-steady balance on the channel air: heat picked up from both
    surfaces equals heat carried away by the flow.
    """
    num = h_pa * design.area * T_abs + h_ga * design.area * T_glass + mdot * CP_AIR * T_room
    den = h_pa * design.area + h_ga * design.area + mdot * CP_AIR
    if den <= 0:
        return T_room
    return num / den


# ----------------------------------------------------------------------
# SIMULATION
# ----------------------------------------------------------------------
class Room:
    """
    The dwelling the chimney serves: a single hot room under a metal or
    concrete roof. Modelled as one air+fabric node so indoor temperature
    becomes a RESULT of the simulation rather than an assumption.
    """

    def __init__(self,
                 volume=30.0,          # m^3
                 roof_area=10.0,       # m^2 of sun-exposed roof
                 roof_U=3.5,           # W/m^2K, uninsulated tin or concrete
                 roof_absorptance=0.7, # dark roof soaks up sunlight
                 wall_UA=40.0,         # W/K through the rest of the envelope
                 thermal_mass=1.0e6,   # J/K, fabric plus contents
                 internal_gain=180.0,  # W from people, lamps, cooking
                 infiltration=1.0):    # background air changes per hour
        # Calibrated so the unventilated night-time indoor temperature sits
        # about 3 K above outdoor, matching field measurements reported for
        # Ahmedabad and Hyderabad low-income housing (2-5 K).
        self.volume = volume
        self.roof_area = roof_area
        self.roof_U = roof_U
        self.roof_absorptance = roof_absorptance
        self.wall_UA = wall_UA
        self.thermal_mass = thermal_mass
        self.internal_gain = internal_gain
        self.infiltration = infiltration


def simulate(design, pcm, weather, days=3, dt=20.0, room=None,
             fixed_room_offset=None):
    """
    fixed_room_offset: if given, the room is held this many kelvin above
    outdoor temperature instead of being simulated. Use 0.0 to reproduce
    published lab rigs, where the test box sat at ambient.
    """
    if room is None:
        room = Room(volume=design.room_volume)

    n_steps = int(days * 24 * 3600 / dt)

    T_g = weather.T_ambient(0)
    T_p = weather.T_ambient(0)
    T_pcm = weather.T_ambient(0)
    T_a = weather.T_ambient(0)
    T_room = weather.T_ambient(0) + (2.0 if fixed_room_offset is None else fixed_room_offset)

    keys = ["t", "I", "T_amb", "T_glass", "T_air", "T_abs", "T_pcm", "T_room",
            "liquid", "Q", "velocity", "dP", "ACH", "efficiency", "h_air"]
    out = {k: [] for k in keys}

    for step in range(n_steps):
        t = step * dt / 3600.0
        I = weather.irradiance(t, design.tilt)
        I_horiz = weather.irradiance(t, 0.0)
        T_amb = weather.T_ambient(t)
        T_sky = weather.T_sky(t)

        # Solve air temperature and flow together
        for _ in range(6):
            Q, velocity, dP = solve_flow(T_a, T_amb, design, weather)
            mdot = Q * air_density(T_a)
            h_pa = h_channel(T_p, T_a, design, velocity)
            h_ga = h_channel(T_g, T_a, design, velocity)
            T_a_new = channel_air_temperature(T_p, T_g, T_room, design, mdot, h_pa, h_ga)
            if abs(T_a_new - T_a) < 0.01:
                T_a = T_a_new
                break
            T_a = 0.5 * T_a + 0.5 * T_a_new

        Q, velocity, dP = solve_flow(T_a, T_amb, design, weather)
        mdot = Q * air_density(T_a)
        h_pa = h_channel(T_p, T_a, design, velocity)
        h_ga = h_channel(T_g, T_a, design, velocity)
        h_rpg = h_radiation(T_p, T_g, design.eps_abs, design.eps_glass)

        cover_on = design.night_cover and I < 20
        sky_factor = 0.15 if cover_on else 1.0
        h_out = h_wind(weather.wind) * (0.3 if cover_on else 1.0)

        # glass node
        q_solar_g = I * (1 - design.tau_glass) * 0.45 * design.area
        q_sky = design.eps_glass * SIGMA * design.area * sky_factor * \
            ((T_g + 273.15) ** 4 - (T_sky + 273.15) ** 4)
        q_out = h_out * design.area * (T_g - T_amb)
        q_from_abs = h_rpg * design.area * (T_p - T_g)
        q_from_air = h_ga * design.area * (T_a - T_g)
        T_g += (q_solar_g + q_from_abs + q_from_air - q_sky - q_out) * dt / design.C_glass

        lf = pcm.liquid_fraction(T_pcm)
        h_pcm = h_pcm_to_absorber(pcm, design, lf)

        # absorber node
        q_solar_p = I * design.tau_glass * design.alpha_abs * design.area
        q_air = h_pa * design.area * (T_p - T_a)
        q_glass = h_rpg * design.area * (T_p - T_g)
        q_room = design.insul_U * design.area * (T_p - T_room)
        q_pcm = h_pcm * design.area * (T_p - T_pcm) if design.use_pcm else 0.0
        T_p += (q_solar_p - q_air - q_glass - q_room - q_pcm) * dt / design.C_abs

        # PCM node
        if design.use_pcm:
            C_pcm = design.pcm_mass * pcm.effective_cp(T_pcm)
            T_pcm += q_pcm * dt / C_pcm

        # --- room node ---
        # Gains: sun on the roof, conduction from hot outdoor air, people and lamps
        # Sol-air approach: solar gain and longwave loss to the sky both act
        # on the outside of the roof, then conduct inwards.
        h_roof_out = 10.0 + 4.0 * weather.wind
        coupling = room.roof_U / (room.roof_U + h_roof_out)
        q_roof_solar = I_horiz * room.roof_absorptance * room.roof_area * coupling
        q_roof_sky = 0.9 * SIGMA * room.roof_area * coupling * \
            ((T_amb + 273.15) ** 4 - (T_sky + 273.15) ** 4)
        q_roof_solar -= q_roof_sky
        q_fabric = (room.roof_U * room.roof_area + room.wall_UA) * (T_amb - T_room)
        q_internal = room.internal_gain
        q_back = design.insul_U * design.area * (T_p - T_room)
        # Losses: air pulled out by the chimney, plus background leakage
        mdot_infil = room.infiltration * room.volume / 3600.0 * air_density(T_room)
        q_vent = (mdot + mdot_infil) * CP_AIR * (T_amb - T_room)
        if fixed_room_offset is None:
            T_room += (q_roof_solar + q_fabric + q_internal + q_back + q_vent) * dt / room.thermal_mass
        else:
            T_room = T_amb + fixed_room_offset

        eff = (mdot * CP_AIR * max(T_a - T_room, 0.0)) / (I * design.area) if I > 20 else 0.0
        out["T_room"].append(T_room)
        out["t"].append(t)
        out["I"].append(I)
        out["T_amb"].append(T_amb)
        out["T_glass"].append(T_g)
        out["T_air"].append(T_a)
        out["T_abs"].append(T_p)
        out["T_pcm"].append(T_pcm)
        out["liquid"].append(lf)
        out["Q"].append(Q * 3600.0)
        out["velocity"].append(velocity)
        out["dP"].append(dP)
        out["ACH"].append(Q * 3600.0 / design.room_volume)
        out["efficiency"].append(eff)
        out["h_air"].append(h_pa)

    out["_days"] = days
    return out


# ----------------------------------------------------------------------
# ANALYSIS HELPERS (read the last settled day by default)
# ----------------------------------------------------------------------
def _day_slice(results, key, day=None):
    day = results["_days"] - 2 if day is None else day
    xs, ys = [], []
    for t, v in zip(results["t"], results[key]):
        if 24 * day <= t < 24 * (day + 1):
            xs.append(t - 24 * day)
            ys.append(v)
    return xs, ys


def profile(results, key, day=None):
    return _day_slice(results, key, day)


def draft_hours_after_sunset(results, weather, threshold=20.0, day=None):
    """Hours of useful airflow after sunset. Needs a following day simulated."""
    day = results["_days"] - 2 if day is None else day
    sunset = weather.sunset + 24 * day
    last = sunset
    for t, Q in zip(results["t"], results["Q"]):
        if sunset <= t <= sunset + 14 and Q >= threshold:
            last = t
    return last - sunset


def average_flow(results, start, end, day=None):
    day = results["_days"] - 2 if day is None else day
    lo, hi = start + 24 * day, end + 24 * day
    vals = [Q for t, Q in zip(results["t"], results["Q"]) if lo <= t <= hi]
    return sum(vals) / len(vals) if vals else 0.0


def daytime_average_flow(results, weather, day=None):
    return average_flow(results, weather.sunrise, weather.sunset, day)


def evening_average_flow(results, weather, window=4.0, day=None):
    return average_flow(results, weather.sunset, weather.sunset + window, day)


def peak(results, key, day=None):
    _, ys = _day_slice(results, key, day)
    return max(ys) if ys else 0.0


def melted_fraction(results, day=None):
    return peak(results, "liquid", day)
