# EcoPulse AI — Architecture Plan

## Overview

**Goal:** Build a solo B.Tech student project: an Agentic Campus Energy Intelligence & Carbon Reduction Planner.
**Stack:** Python · Pandas · Streamlit · Plotly · Google Gemini API (free tier) · ChromaDB (local) · RAG
**Budget:** ₹0 — all components run locally or use free API tiers.
**Scope:** Single academic year (12 months) of synthetic campus electricity consumption data,
carbon footprint calculation, anomaly detection, and AI-driven recommendations delivered
through a single Streamlit dashboard with an embedded agent chat interface.

---

## Confirmed Design Decisions

| Decision | Choice |
|---|---|
| LLM / embedding provider | Google Gemini API (free tier) — `gemini-1.5-flash` for chat, `embedding-001` for embeddings |
| Vector store | ChromaDB (local, on-disk persistence) |
| Entry point | Single Streamlit app — agent chat lives inside the dashboard |
| Data scope | Electricity by building/department, 12 months, synthetic/anonymized |
| Recommendation mode | Deterministic rules flag anomalies → LLM explains and expands via RAG |
| Input flexibility | Default: synthetic campus CSV; also supports user-uploaded CSV or manual meter/bill entry for home, college, or small office. No real-time smart-meter/API integration (future scope). |
| Responsible AI depth | Formal — input/output validation, transparency, source attribution, privacy, fairness considerations, and explainability. All numerical results must come from deterministic Python calculations, never from the LLM. |

---

## Project Folder Structure

```
ecopulse-ai/
├── app.py                      # Streamlit entry point
├── requirements.txt
├── .env                        # GEMINI_API_KEY (gitignored)
├── .gitignore
├── README.md
│
├── data/
│   ├── raw/
│   │   └── campus_energy.csv   # Synthetic dataset (generated once)
│   └── processed/              # Cleaned/transformed outputs (auto-generated)
│
├── modules/
│   ├── __init__.py
│   ├── data_loader.py          # Load, validate, clean CSV
│   ├── calculator.py           # Deterministic energy & carbon calculations
│   ├── anomaly.py              # Rule-based anomaly detection
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── ingest.py           # Chunk documents → embed → store in ChromaDB
│   │   ├── retriever.py        # Query ChromaDB, return top-k context chunks
│   │   └── knowledge/          # Static reference documents (plain .txt / .md)
│   │       ├── emission_factors.md
│   │       ├── energy_best_practices.md
│   │       └── iea_campus_guidelines.md
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── tools.py            # Tool definitions callable by Gemini function-calling
│   │   └── agent_core.py       # Gemini agent loop — receives message, calls tools, returns reply
│   └── responsible_ai/
│       ├── __init__.py
│       ├── guardrails.py       # Input/output content filtering and bias checks
│       └── explainability.py   # Attach reasoning traces to agent responses
│
├── dashboard/
│   ├── __init__.py
│   ├── overview.py             # Dashboard page: KPI cards + summary charts
│   ├── trends.py               # Dashboard page: monthly trend charts
│   ├── buildings.py            # Dashboard page: per-building breakdown
│   ├── recommendations.py      # Dashboard page: anomaly flags + action table
│   └── chat.py                 # Dashboard page: agent chat interface
│
├── scripts/
│   └── generate_data.py        # One-time synthetic dataset generator
│
└── tests/
    ├── test_data_loader.py
    ├── test_calculator.py
    ├── test_anomaly.py
    ├── test_guardrails.py
    └── test_rag_retriever.py
```

---

## Module Descriptions

### `data/raw/campus_energy.csv` — Synthetic Dataset
Generated once by `scripts/generate_data.py`. Schema:

| Column | Type | Description |
|---|---|---|
| `month` | `YYYY-MM` | Reporting month |
| `building_id` | string | e.g. `LH-1`, `CSE-Block` |
| `department` | string | e.g. `Hostel`, `Library` |
| `kwh_consumed` | float | Monthly electricity consumption (kWh) |
| `occupancy_rate` | float | 0–1 fraction (simulated) |
| `area_sqm` | float | Floor area (static per building) |

No real data is used. All values are seeded and reproducible.

---

### `modules/data_loader.py` — Load, Validate, Clean

**Responsibilities:**
- Read CSV with Pandas
- Schema validation: check required columns exist, correct dtypes
- Range validation: kWh > 0, occupancy in [0,1], area > 0
- Raise descriptive `ValueError` on bad data (surfaces in UI as a friendly error banner)
- Return a clean `pd.DataFrame` and a validation report dict

**No external dependencies beyond Pandas.**

---

### `modules/calculator.py` — Deterministic Calculations

Pure functions only — no LLM, no I/O.

| Function | Formula | Output |
|---|---|---|
| `calc_carbon(kwh, grid_ef)` | `kwh × grid_emission_factor` | kg CO₂e |
| `calc_eui(kwh, area_sqm)` | `kwh / area_sqm` | kWh/m² (Energy Use Intensity) |
| `calc_monthly_totals(df)` | Pandas groupby aggregation | DataFrame of totals per month |
| `calc_building_totals(df)` | Pandas groupby aggregation | DataFrame of totals per building |
| `calc_carbon_budget_gap(actual, target_kwh)` | `actual - target_kwh` × grid_ef | kg CO₂e gap |

Grid emission factor defaults to India CEA 2023 average (0.716 kg CO₂e/kWh), configurable in a
constants file. All constants live in `modules/calculator.py:CONSTANTS` dict — no magic numbers
scattered through the code.

---

### `modules/anomaly.py` — Rule-Based Anomaly Detection

Deterministic rules; no ML model needed for demo scope.

| Rule | Condition | Severity |
|---|---|---|
| Spike detection | Monthly kWh > mean + 2×std for that building | HIGH |
| Low-occupancy waste | kWh high while occupancy < 0.2 | MEDIUM |
| EUI threshold breach | EUI > 150 kWh/m²/year (campus benchmark) | HIGH |
| Zero/null reading | kWh == 0 for a full month | DATA_ISSUE |

Returns a list of `AnomalyRecord` dataclasses: `{building_id, month, rule, severity, delta_kwh}`.
These records are the primary input fed to the agent for explanation and recommendations.

---

### `modules/rag/` — Retrieval-Augmented Generation Pipeline

#### `ingest.py` — One-Time Knowledge Base Build
1. Read all `.txt` / `.md` files from `modules/rag/knowledge/`
2. Split into ~500-token chunks with 50-token overlap (simple sentence-boundary split)
3. Embed each chunk using `google.generativeai.embed_content(model="models/embedding-001")`
4. Persist to ChromaDB collection `"ecopulse_kb"` in `data/chroma_db/` (local disk)
5. Run this script once at setup; re-run if knowledge docs change

#### `retriever.py` — Query-Time Retrieval
1. Embed the incoming query string with the same model
2. Query ChromaDB for top-k=3 most similar chunks
3. Return chunks as a plain string block (the "context" injected into the LLM prompt)

#### `knowledge/` — Static Reference Documents
Plain text files maintained by hand. Initial content:
- **`emission_factors.md`** — India CEA grid emission factors by state/year
- **`energy_best_practices.md`** — Campus energy efficiency measures (lighting, HVAC, scheduling)
- **`iea_campus_guidelines.md`** — IEA / BEE benchmarks for educational buildings

---

### `modules/agent/` — AI Agent with Tool Calling

#### `tools.py` — Tool Definitions
Each tool is a Python function wrapped with a Gemini function-calling schema.

| Tool Name | What It Does | Returns |
|---|---|---|
| `get_energy_summary` | Calls `calculator.calc_monthly_totals` on the loaded DataFrame | JSON summary |
| `get_anomalies` | Calls `anomaly.detect_all` and returns anomaly list | JSON list |
| `get_carbon_footprint` | Calls `calculator.calc_carbon` for specified scope | JSON value + units |
| `get_building_breakdown` | Returns per-building EUI and kWh totals | JSON table |
| `get_recommendations` | RAG retrieval for a given topic query | Markdown text |
| `compare_to_benchmark` | Compares campus EUI to IEA/BEE benchmark | JSON delta |

Tools never mutate state. All tools read from the already-loaded DataFrame (passed as a module-level
singleton loaded at app startup — not re-read on every tool call).

#### `agent_core.py` — Gemini Agent Loop
1. Receive user message + conversation history
2. Prepend system prompt (role, constraints, Responsible AI instructions)
3. Send to `gemini-1.5-flash` with tool schemas registered
4. If Gemini returns a `function_call`, execute the matching tool, append result
5. Re-submit to Gemini with the tool result
6. Repeat until Gemini returns a `text` response (max 5 iterations to prevent loops)
7. Pass response through `guardrails.py` before returning to UI

**System prompt key elements:**
- Role: "You are EcoPulse, a campus energy analyst assistant."
- Always cite the data source for any number you quote
- Never hallucinate kWh or carbon figures — use tools for all numerical claims
- Refuse off-topic requests politely

---

### `modules/responsible_ai/` — Responsible AI Layer

#### `guardrails.py`
**Input validation:**
- Block PII patterns (email, phone, Aadhaar-format numbers)
- Block prompt-injection attempts (phrases like "ignore previous instructions", "you are now")
- Enforce message length ≤ 1000 characters
- Log all rejected inputs with reason (no personal data logged)

**Output validation:**
- Verify every number in the LLM response is traceable to a tool result in the current turn
- If an ungrounded number is detected, strip it and append a disclaimer: "Numerical claim removed — please use the dashboard for verified figures."
- Ensure response is not empty and does not exceed a reasonable length

**Transparency & source attribution:**
- Every agent response includes a `sources` list: tool names used + RAG chunk IDs referenced
- Displayed in the UI as "Sources used in this answer"

**Fairness:**
- When comparing departments or buildings, prepend a fairness note: "Comparisons are based on synthetic data and should be interpreted in context (building size, usage type, occupancy)."

**Privacy:**
- No user-uploaded data is persisted beyond the session (`st.session_state` only)
- `.env` (API key) is gitignored; `data/chroma_db/` is gitignored
- Uploaded CSV is validated for schema only — no content is logged or stored

#### `explainability.py`
- Attaches a `reasoning_trace` dict to every agent response:
  - `tools_called`: list of tool names and their return values
  - `rag_chunks`: top-k chunk IDs and similarity scores retrieved
  - `guardrail_actions`: any input/output interventions applied
- The Streamlit chat UI renders this as a collapsed "How I answered this" expander
- The trace is always available — users can audit the full reasoning chain

---

### `dashboard/` — Streamlit Multi-Page Dashboard

Streamlit's native multi-page support (`pages/` folder pattern is replaced by manual tab/sidebar
navigation to keep it simple for a solo project).

`app.py` loads data once at startup into `st.session_state` and renders a sidebar with five
navigation choices:

| Page | File | Key Content |
|---|---|---|
| Overview | `overview.py` | Total kWh, total CO₂e, EUI, YoY placeholder — KPI cards + pie chart by building |
| Monthly Trends | `trends.py` | Line chart: monthly kWh + CO₂e overlay; Plotly Express |
| Building Analysis | `buildings.py` | Bar chart: EUI per building; heatmap: building × month |
| Recommendations | `recommendations.py` | Anomaly table with severity badges; static rule-based action list |
| AI Assistant | `chat.py` | Streamlit chat UI → agent_core → streamed response + expandable trace |

All charts use **Plotly Express** for interactivity. Color palette: green-to-red diverging scale
(green = efficient, red = wasteful) to reinforce the sustainability theme.

---

## Data Flow Diagram

```
[generate_data.py] ──► [data/raw/campus_energy.csv]
                                │
                        [data_loader.py]
                         validate + clean
                                │
                    ┌───────────┴──────────────┐
                    │                          │
            [calculator.py]           [anomaly.py]
           kWh totals, EUI,         rule-based flags
           carbon footprint               │
                    │                    │
                    └──────────┬─────────┘
                               │
                    [st.session_state]   ◄── loaded once at app startup
                               │
             ┌─────────────────┼──────────────────┐
             │                 │                  │
       [overview.py]    [trends.py]         [chat.py]
       [buildings.py]   [recommendations.py]     │
       Plotly charts    anomaly table        user message
                                                  │
                                        [guardrails.py] ← input check
                                                  │
                                        [agent_core.py]
                                         Gemini + tools
                                                  │
                                     ┌────────────┤
                                     │            │
                               [tools.py]   [retriever.py]
                              calculator/    ChromaDB query
                              anomaly calls       │
                                     │       [knowledge/]
                                     └────────────┤
                                                  │
                                        [guardrails.py] ← output check
                                        [explainability.py]
                                                  │
                                        response + trace
                                                  │
                                         [chat.py UI]
```

---

## RAG Workflow (Step by Step)

**Setup (once):**
1. `python -m modules.rag.ingest` reads `knowledge/*.md`, splits, embeds via Gemini
   `embedding-001`, stores in ChromaDB at `data/chroma_db/`

**Query-time (every agent turn):**
1. User message → agent extracts the semantic query (or uses the message directly)
2. `retriever.get_context(query, k=3)` → top-3 chunks from ChromaDB
3. Chunks injected into the Gemini prompt as:
   ```
   [CONTEXT FROM KNOWLEDGE BASE]
   {chunk_1}
   {chunk_2}
   {chunk_3}
   [END CONTEXT]
   ```
4. Agent uses context to ground explanations and recommendations
5. If no relevant chunk found (cosine similarity < threshold), agent answers from tool data only
   and notes "no knowledge base match found"

---

## Agent Tool-Calling Flow

```
User: "Which building wasted the most energy last month?"
         │
   agent_core receives message
         │
   Gemini decides → call tool: get_building_breakdown
         │
   tools.py executes → returns JSON {building: "CSE-Block", kwh: 12400, eui: 180}
         │
   Gemini decides → call tool: get_anomalies (to check if flagged)
         │
   tools.py executes → returns [{building: "CSE-Block", rule: "EUI_BREACH", severity: "HIGH"}]
         │
   Gemini composes answer using tool results + RAG context
         │
   guardrails checks output (numbers match tool results ✓)
         │
   explainability attaches trace
         │
   UI renders: answer + collapsible "How I answered this" panel
```

---

## Input Validation Strategy

All validation is **fail-fast at the boundary** — bad data is caught in `data_loader.py` before
it reaches any calculation or agent code.

| Layer | What Is Validated | How |
|---|---|---|
| CSV load | Schema, dtypes, null checks | Pandas + explicit assertions |
| Calculator inputs | Positive kWh, valid area | `assert` with descriptive message |
| Agent input | Message length < 1000 chars; no PII patterns | Regex in guardrails.py |
| API key | Present in `.env` at startup | `os.getenv` check with clear error |
| Gemini responses | Not empty, no fabricated numbers | guardrails.py output scan |

---

## Responsible AI Practices (Formal)

All numerical results **must** originate from deterministic Python calculations in `calculator.py` or `anomaly.py` — never from LLM generation. The Responsible AI layer enforces this programmatically.

| Practice | Implementation |
|---|---|
| **Transparency** | Every response includes an expandable reasoning trace (tools called, RAG chunks used, guardrail actions) |
| **Groundedness** | System prompt instructs agent to call tools for all numbers; `guardrails.py` output scan removes ungrounded numerics |
| **Source attribution** | `sources` list attached to every response; rendered in UI as "Sources used in this answer" |
| **Harm avoidance** | Prompt injection detection blocks adversarial inputs; off-topic refusals built into system prompt |
| **Fairness** | Fairness disclaimer prepended to any cross-building/department comparison |
| **Privacy** | Synthetic default data; uploaded CSVs held in `st.session_state` only (not persisted); `.env` and `data/chroma_db/` gitignored |
| **Explainability** | Full reasoning trace: tool inputs/outputs + RAG chunk IDs + similarity scores + guardrail actions |
| **Input validation** | PII blocking, injection blocking, length cap — at the boundary before the LLM ever sees the message |
| **Output validation** | Ungrounded numbers stripped; empty responses rejected; length sanity check |

---

## Testing Plan

All tests use **pytest**. No mocking of Gemini API in unit tests — agent tests use canned
responses (recorded fixtures) to avoid API costs and flakiness.

| Test File | What It Covers |
|---|---|
| `test_data_loader.py` | Valid CSV loads cleanly; bad schema raises ValueError; null rows rejected |
| `test_calculator.py` | Carbon formula correctness; EUI edge cases (zero area); monthly totals |
| `test_anomaly.py` | Spike rule triggers correctly; low-occupancy rule; zero-reading detection |
| `test_guardrails.py` | Prompt injection blocked; PII pattern detected; clean message passes |
| `test_rag_retriever.py` | Returns k results; handles empty query gracefully |

**Run all tests:** `pytest tests/`
**Run single test:** `pytest tests/test_calculator.py::test_carbon_formula`

---

## Input Flexibility Layer

The data input layer supports three modes, selectable in the Streamlit sidebar:

| Mode | Description | Entry Point |
|---|---|---|
| **Demo (default)** | Load `data/raw/campus_energy.csv` — synthetic campus data, always available | Auto-loaded at startup |
| **Upload CSV** | User uploads a CSV with the same schema (building/home/office data) | `st.file_uploader` in sidebar |
| **Manual entry** | User fills a simple form: building name, month, kWh consumed, area (m²) | `st.form` in sidebar |

All three modes produce the same clean `pd.DataFrame` after passing through `data_loader.py`. The rest of the pipeline (calculator, anomaly, agent) is data-source-agnostic.

Uploaded/entered data is held in `st.session_state` only — never written to disk, never logged.

---

## Sub-Tasks for Implementation

### Sub-Task 1 — Synthetic Data Generator
**Intent:** Create reproducible, realistic campus energy CSV so all other modules have real input.
**Expected Outcomes:** `data/raw/campus_energy.csv` with 12 months × 8 buildings × correct schema.
**Todo:**
- [x] Write `scripts/generate_data.py` using NumPy random seed
- [x] Include seasonal variation (higher AC load in summer months)
- [x] Include one deliberate anomaly building for demo purposes
- [x] Verify output schema matches spec above
**Status:** [x] done — 96 rows (8 buildings x 12 months) generated at data/raw/campus_energy.csv; anomaly injected (EE-Block Jul-2023: 22320 kWh, occupancy 0.08).

---

### Sub-Task 2 — Data Loader + Calculator + Anomaly Modules
**Intent:** Build the deterministic computation core — no LLM dependency.
**Expected Outcomes:** `data_loader`, `calculator`, `anomaly` modules pass all unit tests.
**Todo:**
- [x] Implement `data_loader.py` with schema + range validation
- [x] Implement `calculator.py` with all five pure functions and CONSTANTS dict
- [x] Implement `anomaly.py` with four rules and AnomalyRecord dataclass
- [x] Write and pass `test_data_loader.py`, `test_calculator.py`, `test_anomaly.py`
**Status:** [x] done — 64/64 tests pass. All three modules implemented with no LLM dependency.

---

### Sub-Task 3 — RAG Knowledge Base
**Intent:** Build the local ChromaDB knowledge base from static reference docs.
**Expected Outcomes:** ChromaDB collection populated; `retriever.get_context("HVAC savings")` returns relevant chunks.
**Todo:**
- [x] Write three knowledge `.md` files with real emission factors and best practices
- [x] Implement `ingest.py`
- [x] Implement `retriever.py`
- [x] Write and pass `test_rag_retriever.py`
**Status:** [x] done — 11 chunks in ChromaDB; 16/16 retriever tests pass (including semantic relevance). Migrated to google-genai SDK (google.generativeai deprecated). Model: gemini-embedding-001.

---

### Sub-Task 4 — Responsible AI Layer
**Intent:** Add guardrails and explainability wrappers before wiring the agent.
**Expected Outcomes:** Injection attempts blocked; clean messages pass; output trace attached.
**Todo:**
- [x] Implement `guardrails.py` (input + output checks)
- [x] Implement `explainability.py` (trace builder)
- [x] Write and pass `test_guardrails.py`
**Status:** [x] done — 48/48 tests pass. Guardrails cover: length cap, PII (email/phone/Aadhaar), prompt injection (8 patterns), off-topic flag, empty output, ungrounded-number detection with disclaimer, length truncation, and fairness note on comparisons. Explainability trace covers tools, RAG chunks, guardrail records, and source attribution.

---

### Sub-Task 5 — Gemini Agent Core + Tools
**Intent:** Wire Gemini function-calling with the six tools; implement the agent loop.
**Expected Outcomes:** Agent answers energy questions using tool results, not hallucination.
**Todo:**
- [x] Implement `tools.py` with all six tool schemas
- [x] Implement `agent_core.py` with the 5-iteration loop, system prompt, and tool dispatch
- [x] Manual smoke test: ask "total carbon footprint this year?" and verify grounded answer
**Status:** [x] done — All 6 tools wired. 4 smoke tests pass: carbon footprint (488,558 kg CO2e grounded), anomaly detection (EE-Block July spike found), injection blocked, benchmark comparison (27 kWh/m2 vs 150 benchmark). SDK migrated to google-genai; retry wrapper handles transient 503s. _safe_serialise prevents numpy/pandas type errors in FunctionResponse.

---

### Sub-Task 6 — Streamlit Dashboard
**Intent:** Build the five-page dashboard with Plotly charts and embedded chat.
**Expected Outcomes:** `streamlit run app.py` shows all pages; charts render; chat works end-to-end.
**Todo:**
- [x] Implement `app.py` (data load at startup, sidebar nav, session_state)
- [x] Implement `overview.py`, `trends.py`, `buildings.py`, `recommendations.py`
- [x] Implement `chat.py` with streaming response and collapsible trace
- [x] Final end-to-end smoke test
**Status:** [x] done — All 5 pages implemented. 14 modules import cleanly. All 6 tools verified via startup simulation. Data source switcher supports Demo / Upload CSV / Manual entry. 128/128 tests pass.

---

## Dependencies (`requirements.txt`)

```
streamlit>=1.35
pandas>=2.0
plotly>=5.20
google-generativeai>=0.7
chromadb>=0.5
python-dotenv>=1.0
pytest>=8.0
numpy>=1.26
```

All free. No paid services, no Docker required, runs on a student laptop.
