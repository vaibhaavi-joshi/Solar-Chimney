# Solar Chimney

Passive roof-mounted cooling for low-income Indian housing. No grid electricity,
no refrigerant, no pump.

**Live site:** https://vaibhaavi-joshi.github.io/Solar-Chimney/

Built for Imperial College London Schools STEMathon India 2026.

## What this is

A solar chimney uses sunlight to heat an absorber plate behind glazing. The air in
the channel warms, becomes less dense, and rises, pulling hot indoor air out through
the roof and drawing replacement air in through a low vent. The entire driving
pressure is under one pascal, so the design is as much about managing pressure
losses as about collecting heat.

The chimney **does not cool air below outdoor temperature** — it has no cooling
mechanism. It removes trapped heat that makes indoor conditions far worse than
outdoor, which in these homes is a large effect.

## Headline results

Indoor temperature reduction versus the same room with no chimney, at the final
3.0 m² design (1.5 × 2.0 m, 1.15 m above the roofline):

| Scenario | Rural peak | Rural night | Urban peak | Urban night |
|---|---|---|---|---|
| Normal day (39.5/27.5 °C) | 9.0 K | 2.6 K | 3.0 K | 7.0 K |
| Hot day (44/31 °C) | 10.2 K | 2.5 K | 3.2 K | 7.0 K |
| Extreme day (47/35 °C) | 11.5 K | 2.3 K | 3.9 K | 6.7 K |

In the urban extreme case a sealed concrete room sits at 47 °C overnight, above
body temperature. The chimney brings that to 40.3 °C.

## Method

Transient global energy balance with four thermal nodes (glazing, channel air,
absorber, PCM) plus a room node, stepped at 20 s and run to a settled day. Airflow
is solved each step by balancing stack pressure against friction and minor losses,
so the system self-regulates. PCM uses the effective heat capacity method.

### Validation

Run against published experiments before being used for design:

| Source | Measured | Model |
|---|---|---|
| Ong & Chow (2003) | 0.25–0.39 m/s | 0.30 m/s |
| Khedari et al. | 8–15 ACH | 7.1 ACH |
| Mathur et al. | 5.6 ACH | overpredicts |

The overprediction against Mathur is a known limitation and is stated rather than
hidden.

### Inputs

Room size from census data (40% of households have five people in one room; a
10 × 10 ft room matches). Weather from IMD climatology and official heatwave
definitions.

## Findings worth noting

- **Short and wide beats tall.** Friction scales with channel length over hydraulic
  diameter, so widening cuts resistance faster than lowering costs stack pressure.
  The final design is half the height of the earlier version, uses a third less
  material, and performs slightly better.
- **Two housing types need opposite things.** Metal roofs are thin and overheat at
  midday; concrete slabs store heat and release it at night. The same device solves
  a different problem in each.
- **PCM storage underperformed.** Evening airflow improved by only ~6% versus no
  PCM, because the room stays hotter than outdoors overnight so the draft continues
  without it.

## Files

| File | Purpose |
|---|---|
| `chimney_model.py` | Core energy-balance model |
| `design_cases.py` | Rural and urban housing definitions |
| `scenarios.py` | Three IMD-anchored weather scenarios |
| `progression.py` | Design iteration comparison |
| `export_runs.py` | Exports results to JSON for the web pages |
| `run_simulation.py` | Validation and sensitivity runs |
| `simulation_data.json` | Exported results driving the site |

## Running it

```
pip install matplotlib
python run_simulation.py
```

## Status

All figures are modelled predictions, not measurements. A physical prototype and
experimental validation are the next stage.
