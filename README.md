# EcoPulse AI

**Agentic Campus Energy Intelligence & Carbon Reduction Planner**

A solo B.Tech student project built on Python · Pandas · Streamlit · Plotly · Google Gemini API · ChromaDB.

---

## Quick Start

```bash
# 1. Clone and install dependencies
pip install -r requirements.txt

# 2. Copy and fill in your Gemini API key
cp .env.example .env
# edit .env and set GEMINI_API_KEY=...

# 3. (One-time) Generate synthetic campus data
python scripts/generate_data.py

# 4. (One-time) Build the RAG knowledge base
python -m modules.rag.ingest

# 5. Run the app
streamlit run app.py
```

## Project Structure

```
ecopulse-ai/
├── app.py                      # Streamlit entry point
├── requirements.txt
├── .env.example
├── data/
│   └── raw/campus_energy.csv   # Synthetic dataset
├── modules/
│   ├── data_loader.py
│   ├── calculator.py
│   ├── anomaly.py
│   ├── rag/                    # ChromaDB + Gemini embeddings
│   ├── agent/                  # Gemini function-calling agent
│   └── responsible_ai/         # Guardrails + explainability
├── dashboard/                  # Streamlit page modules
├── scripts/
│   └── generate_data.py
└── tests/
```

## Running Tests

```bash
pytest tests/
```

## Architecture

See [ecopulse-architecture-plan.md](ecopulse-architecture-plan.md) for the full design.
