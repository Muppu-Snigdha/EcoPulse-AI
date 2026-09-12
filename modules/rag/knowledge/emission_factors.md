# Grid Emission Factors for India

## What is a Grid Emission Factor?

A grid emission factor (also called a CO2 baseline factor) is the average mass of
carbon dioxide equivalent (CO2e) emitted per unit of electricity consumed from the
grid. It is expressed in kg CO2e per kWh.

When a campus consumes electricity from the state grid, it is indirectly responsible
for the emissions produced at power plants. Multiplying monthly kWh consumption by
the emission factor gives the carbon footprint in kg CO2e.

## India National Average (CEA 2023)

The Central Electricity Authority (CEA) publishes annual CO2 baseline databases for
the Indian power sector.

- **National average emission factor (2023): 0.716 kg CO2e / kWh**
- Source: CEA, "CO2 Baseline Database for the Indian Power Sector," Version 18 (2023)
- This is the value used by EcoPulse AI for all carbon calculations.

## State-Level Emission Factors (Selected, CEA 2022-23)

Different Indian states have different grid mixes and therefore different emission factors.
If your campus is in a state with a high renewable share, the actual footprint may be lower.

| State              | Emission Factor (kg CO2e/kWh) | Notes                        |
|--------------------|-------------------------------|------------------------------|
| Andhra Pradesh     | 0.82                          | High coal share              |
| Chhattisgarh       | 1.05                          | Very coal-intensive          |
| Gujarat            | 0.72                          | Mixed — growing solar        |
| Karnataka          | 0.60                          | High hydro + solar share     |
| Kerala             | 0.35                          | Predominantly hydro          |
| Madhya Pradesh     | 0.90                          | High coal                    |
| Maharashtra        | 0.82                          | Mixed urban/industrial       |
| Punjab             | 0.65                          | Significant hydro            |
| Rajasthan          | 0.78                          | Growing solar but coal base  |
| Tamil Nadu         | 0.72                          | Mixed wind + coal            |
| Telangana          | 0.82                          | Coal-dominant                |
| Uttar Pradesh      | 0.90                          | High coal                    |
| West Bengal        | 0.98                          | Coal-dominant                |
| National Average   | 0.716                         | Used when state unknown      |

## How to Use State Factors for More Accurate Reporting

To improve accuracy, replace the national average with your state's factor:
1. Identify which state grid your campus is connected to.
2. Use the corresponding factor from the CEA database.
3. Re-run `calc_carbon(kwh, grid_ef=<state_factor>)` with the correct value.

## Scope of Emissions (GHG Protocol)

- **Scope 2 emissions**: Indirect emissions from purchased electricity — this is
  what EcoPulse AI calculates.
- **Scope 1**: Direct combustion (diesel generators, gas boilers) — not included.
- **Scope 3**: All other indirect emissions (supply chain, commuting) — not included.

Scope 2 (electricity) typically accounts for 60–80% of a campus's total carbon footprint.

## Carbon Reduction from Renewable Energy

If a campus installs solar panels and offsets grid consumption:
- Each kWh generated on-site avoids 0.716 kg CO2e (using national average).
- A 100 kW rooftop solar system generating ~130,000 kWh/year avoids approximately
  93 tonnes CO2e per year.
- This is equivalent to planting roughly 4,200 trees annually.

## Emission Factor Trend (India, Historical)

India's grid is gradually decarbonising due to renewable energy expansion:

| Year | National Average (kg CO2e/kWh) |
|------|-------------------------------|
| 2018 | 0.820                         |
| 2019 | 0.790                         |
| 2020 | 0.760                         |
| 2021 | 0.740                         |
| 2022 | 0.722                         |
| 2023 | 0.716                         |

The downward trend means historical kWh comparisons will slightly overstate
past emissions if recalculated with the current factor.
