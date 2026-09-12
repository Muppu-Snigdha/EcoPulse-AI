# IEA and BEE Benchmarks for Campus and Educational Buildings

## Overview

Benchmarking compares a building's energy performance against a reference standard.
EcoPulse AI uses the Energy Use Intensity (EUI) metric — annual electricity consumed
per square metre of gross floor area (kWh/m²/year) — as the primary benchmark indicator.

---

## Energy Use Intensity (EUI) Explained

**Formula:**
  EUI = Annual kWh consumed / Gross floor area (m²)

**Units:** kWh/m²/year

A lower EUI indicates a more energy-efficient building. EUI allows fair comparison
between buildings of different sizes.

**Example:**
  A 3,200 m² CSE block consuming 90,000 kWh/year has EUI = 90,000 / 3,200 = 28.1 kWh/m²

---

## BEE Benchmarks for Educational Buildings in India

The Bureau of Energy Efficiency (BEE), Government of India, has established Energy
Performance Index (EPI) benchmarks under the Energy Conservation Building Code (ECBC).

| Building Type              | BEE Good Practice EUI | BEE Benchmark EUI | EcoPulse Alert Threshold |
|----------------------------|----------------------|-------------------|--------------------------|
| Educational (general)      | < 60 kWh/m²/year     | < 100 kWh/m²/year | > 150 kWh/m²/year        |
| Hostel / Residential       | < 80 kWh/m²/year     | < 120 kWh/m²/year | > 150 kWh/m²/year        |
| Laboratory / Research      | < 120 kWh/m²/year    | < 180 kWh/m²/year | > 250 kWh/m²/year        |
| Library / Data Centre      | < 100 kWh/m²/year    | < 150 kWh/m²/year | > 200 kWh/m²/year        |
| Administrative Office      | < 80 kWh/m²/year     | < 130 kWh/m²/year | > 150 kWh/m²/year        |

- **Good Practice:** Top 25% of building stock — aspirational target.
- **Benchmark:** Median performance — minimum standard.
- **EcoPulse Alert Threshold (150 kWh/m²/year):** Used in EcoPulse anomaly detection.
  Buildings above this are flagged as HIGH severity EUI_BREACH anomalies.

Source: BEE, Energy Performance Index for Buildings; ECBC 2017; BEE Star Rating Programme.

---

## IEA Sustainable Campus Energy Performance Guidelines

The International Energy Agency's Sustainable Buildings Programme identifies the
following targets for university campuses in developing economies:

### Carbon Intensity Target
- **2030 target:** Reduce campus carbon intensity to < 0.10 kg CO2e/kWh effective
  consumption (achieved through renewable generation + efficiency).
- **2050 target:** Net-zero campus energy — all consumption offset by on-site renewables.

### Energy Consumption Benchmarks (IEA, Developing Asia)

| Campus Function         | IEA Reference EUI      |
|-------------------------|------------------------|
| Classroom / Teaching    | 40–80 kWh/m²/year      |
| Laboratory              | 100–200 kWh/m²/year    |
| Residential (hostel)    | 60–120 kWh/m²/year     |
| Administrative          | 60–100 kWh/m²/year     |
| Sports / Recreation     | 30–60 kWh/m²/year      |

Source: IEA, "Sustainable Campus Energy Roadmap," 2022.

---

## GRIHA Rating System (India)

GRIHA (Green Rating for Integrated Habitat Assessment) is India's national green
building rating system. Energy efficiency is evaluated in GRIHA Criterion 10–12.

Key thresholds for energy points:
- Achieve 15% below ECBC baseline energy → 1 star
- Achieve 30% below ECBC baseline → 2 stars
- Achieve 50% below ECBC baseline → 3 stars (net-zero pathway)

GRIHA-rated campuses typically achieve EUI of 40–90 kWh/m²/year.

---

## Typical Campus Energy Breakdown (India, 2022)

Based on energy audits of 50 Indian university campuses (BEE, 2022):

| End Use             | Share of Total Electricity |
|---------------------|---------------------------|
| Air Conditioning    | 38–55%                    |
| Lighting            | 18–28%                    |
| IT & Lab Equipment  | 12–20%                    |
| Pumping & Motors    | 5–10%                     |
| Catering / Kitchen  | 4–8%                      |
| Other               | 3–6%                      |

---

## Carbon Reduction Targets (Paris Agreement Alignment)

For a campus to be on a 1.5°C-aligned trajectory:
- Annual reduction in carbon intensity: ~7% per year until 2030.
- If current campus EUI is 150 kWh/m²/year, the 2030 target is approximately
  83 kWh/m²/year — achieved through a combination of:
  1. Efficiency measures (target: 40% reduction in demand)
  2. Renewable energy (target: 40% of remaining demand from on-site solar)
  3. Grid decarbonisation (expected ~30% improvement in emission factor by 2030)

---

## Interpreting Anomalies in Context

When EcoPulse flags a building as an anomaly, the severity should be interpreted
alongside building type:

- A **canteen** with EUI 180 kWh/m²/year may be acceptable (high equipment load).
- A **classroom block** with EUI 180 kWh/m²/year is a strong signal of waste.
- A **hostel** spike during semester break strongly suggests equipment left running.
- An **administrative block** spike in summer indicates excessive AC use.

Always correlate anomalies with occupancy data and seasonal context before
drawing conclusions or making recommendations.

---

## Reference Standards and Sources

1. BEE, "Energy Conservation Building Code (ECBC) 2017," Ministry of Power, India.
2. BEE, "Energy Performance Index for Commercial Buildings," 2019.
3. IEA, "Sustainable Buildings Programme — Campus Energy Roadmap," 2022.
4. CEA, "CO2 Baseline Database for the Indian Power Sector," Version 18, 2023.
5. GRIHA Council, "GRIHA Rating System Version 2019," TERI, New Delhi.
6. MoEFCC, "India's Long-Term Low Carbon Development Strategy," 2022.
