"""
agent_core.py
-------------
Gemini function-calling agent loop for EcoPulse AI.

Flow (per user message)
-----------------------
1.  Input guardrail  — blocks PII / injection before anything reaches the LLM
2.  RAG pre-fetch    — retrieve relevant knowledge chunks for the user query
3.  Build contents   — system prompt + conversation history + RAG context + user message
4.  Gemini loop      — up to MAX_ITERATIONS:
      a. Send to gemini-2.5-flash with tool schemas
      b. If response has function_call(s): execute tool(s), append results, repeat
      c. If response is text: exit loop
5.  Output guardrail — verify numbers, fairness note, length check
6.  Build trace      — attach reasoning trace for explainability
7.  Return AgentResponse

Public API
----------
AgentResponse          — typed return value of ask()
ask(message, history)  — main entry point
"""

# NOTE: Transient 503 errors from the Gemini API are retried automatically
# by the google-genai SDK (tenacity). If the model is temporarily unavailable,
# the SDK will retry up to its internal limit before raising.

from __future__ import annotations

import os
import time
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

from modules.agent import tools as tools_module
from modules.rag.retriever import get_context_with_metadata
from modules.responsible_ai.guardrails import check_input, check_output
from modules.responsible_ai.explainability import build_trace, format_trace_markdown

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CHAT_MODEL = "models/gemini-2.5-flash"
MAX_ITERATIONS = 5        # prevent runaway tool loops
MAX_API_RETRIES = 3       # retry on transient 503/429
RETRY_DELAY_SECONDS = 5   # wait between retries

SYSTEM_PROMPT = """You are EcoPulse, a campus energy analyst assistant embedded in the \
EcoPulse AI dashboard.

Your role:
- Help users understand campus electricity consumption, carbon footprint, and Energy Use \
Intensity (EUI).
- Identify anomalous buildings or months and explain what may be causing them.
- Recommend specific, actionable energy efficiency measures grounded in the knowledge base.
- Help users compare their campus (or home/office) data to established benchmarks.

Rules you MUST follow:
1. NEVER state a kWh, CO2e, or EUI figure without calling the appropriate tool first. \
All numerical claims must come from tool results, not your own generation.
2. Always cite the data source for every number you quote (e.g. "According to the tool \
result, EE-Block consumed 22,320 kWh in July 2023").
3. If the user asks about a topic outside campus/home/office energy analysis, politely \
decline and redirect them.
4. If a knowledge-base context block is provided, prefer it for explaining WHY and HOW. \
For raw numbers, always use tools.
5. Keep responses concise but complete. Use bullet points for lists of recommendations.
6. When comparing buildings or departments, always note that comparisons depend on building \
size, usage type, and occupancy.

You have access to these tools:
- get_energy_summary: campus monthly kWh + CO2e totals
- get_building_breakdown: per-building kWh, CO2e, EUI
- get_carbon_footprint: total CO2e with optional budget-gap calculation
- get_anomalies: rule-based anomaly detection results
- get_recommendations: knowledge-base retrieval for efficiency advice
- compare_to_benchmark: building EUI vs BEE/IEA standard
"""


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@dataclass
class AgentResponse:
    """Complete response package returned by ask()."""
    text: str                            # final answer to display
    trace: object                        # ReasoningTrace (from explainability)
    trace_markdown: str                  # pre-formatted markdown for the UI expander
    input_blocked: bool = False          # True if input guardrail blocked the message
    sources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def ask(
    message: str,
    history: list[dict] | None = None,
) -> AgentResponse:
    """
    Process a user message through the full EcoPulse agent pipeline.

    Parameters
    ----------
    message : str
        Raw user message.
    history : list[dict] | None
        Previous turns as list of {"role": "user"|"model", "parts": [str]}.
        Pass None or [] for a fresh conversation.

    Returns
    -------
    AgentResponse
    """
    history = history or []
    tool_call_records: list[dict] = []
    rag_result: dict | None = None

    # ---- 1. Input guardrail ------------------------------------------------
    input_guard = check_input(message)
    if input_guard.action == "BLOCKED":
        trace = build_trace(
            input_guard_result=input_guard,
            iteration_count=0,
        )
        return AgentResponse(
            text=input_guard.message,
            trace=trace,
            trace_markdown=format_trace_markdown(trace),
            input_blocked=True,
        )

    # ---- 2. RAG pre-fetch --------------------------------------------------
    rag_result = get_context_with_metadata(message, k=3)
    rag_context_block = rag_result.get("context_text", "")

    # ---- 3. Build initial contents list ------------------------------------
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set in .env")
    client = genai.Client(api_key=api_key)

    # Prepend RAG context to the user message if relevant chunks were found
    user_content = message
    if rag_context_block:
        user_content = f"{rag_context_block}\n\nUser question: {message}"

    # Build contents: history + current user turn
    contents: list[genai_types.Content] = []
    for turn in history:
        role = turn.get("role", "user")
        parts_data = turn.get("parts", [])
        parts = [genai_types.Part(text=p) if isinstance(p, str) else p for p in parts_data]
        contents.append(genai_types.Content(role=role, parts=parts))

    contents.append(
        genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=user_content)],
        )
    )

    # ---- 4. Gemini agent loop ----------------------------------------------
    final_text = ""
    iteration = 0
    all_tool_results: list[dict] = []   # collected for output guardrail grounding check

    try:
        for iteration in range(1, MAX_ITERATIONS + 1):
            response = _generate_with_retry(client, contents)

            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason

            # Collect all parts from this response
            text_parts: list[str] = []
            function_calls: list[genai_types.FunctionCall] = []

            for part in candidate.content.parts:
                if part.text:
                    text_parts.append(part.text)
                if part.function_call:
                    function_calls.append(part.function_call)

            if not function_calls:
                # No tool calls — final text response
                final_text = "\n".join(text_parts).strip()
                break

            # Append the model's response (with function calls) to contents
            contents.append(candidate.content)

            # Execute each function call and build tool response parts
            tool_response_parts: list[genai_types.Part] = []
            for fc in function_calls:
                tool_name = fc.name
                args = dict(fc.args) if fc.args else {}

                # Execute via dispatch table
                tool_fn = tools_module.TOOL_FUNCTIONS.get(tool_name)
                if tool_fn is None:
                    result = {"error": f"Unknown tool: {tool_name}"}
                else:
                    try:
                        result = tool_fn(**args)
                    except Exception as exc:
                        result = {"error": str(exc)}

                # Record for trace + grounding check
                tool_call_records.append({
                    "tool_name": tool_name,
                    "arguments": args,
                    "result": result,
                    "iteration": iteration,
                })
                all_tool_results.append(result)

                safe_result = _safe_serialise(result)
                tool_response_parts.append(
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name=tool_name,
                            response=safe_result,
                        )
                    )
                )

            # Append tool results as a user turn
            contents.append(
                genai_types.Content(role="user", parts=tool_response_parts)
            )

        else:
            # Loop exhausted without a text response — use whatever text we have
            if not final_text:
                final_text = (
                    "I've gathered all the data but was unable to compose a final answer "
                    "within the iteration limit. Please try a more specific question."
                )

    except QuotaExhaustedError:
        # ---- Quota fallback: use deterministic tools + RAG, no Gemini -------
        final_text = _quota_fallback_response(message, rag_result)
        # Build a minimal trace so the UI audit trail still renders
        output_guard = check_output(final_text, tool_results=[])
        trace = build_trace(
            tool_calls=tool_call_records,
            rag_result=rag_result,
            input_guard_result=input_guard,
            output_guard_result=output_guard,
            iteration_count=0,
        )
        return AgentResponse(
            text=final_text,
            trace=trace,
            trace_markdown=format_trace_markdown(trace),
            input_blocked=False,
            sources=trace.sources,
        )

    # ---- 5. Output guardrail -----------------------------------------------
    output_guard = check_output(final_text, tool_results=all_tool_results)
    final_text = output_guard.message

    # ---- 6. Build trace ----------------------------------------------------
    trace = build_trace(
        tool_calls=tool_call_records,
        rag_result=rag_result,
        input_guard_result=input_guard,
        output_guard_result=output_guard,
        iteration_count=iteration,
    )

    return AgentResponse(
        text=final_text,
        trace=trace,
        trace_markdown=format_trace_markdown(trace),
        input_blocked=False,
        sources=trace.sources,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class QuotaExhaustedError(Exception):
    """Raised when Gemini returns HTTP 429 / RESOURCE_EXHAUSTED."""


def _is_quota_error(exc: Exception) -> bool:
    """Return True if the exception indicates a quota / rate-limit exhaustion."""
    err_str = str(exc).lower()
    return "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str


def _generate_with_retry(
    client: genai.Client,
    contents: list,
) -> object:
    """
    Wrap client.models.generate_content with a simple retry loop for
    transient 503 / temporarily-unavailable errors.

    429 / RESOURCE_EXHAUSTED (quota exhaustion) is NOT retried — it is
    raised immediately as QuotaExhaustedError so the caller can fall back
    without waiting.
    """
    last_exc = None
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            return client.models.generate_content(
                model=CHAT_MODEL,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[tools_module.GEMINI_TOOL_SCHEMAS],
                    temperature=0.2,
                ),
            )
        except Exception as exc:
            last_exc = exc
            # --- Quota exhaustion: do NOT retry, raise a clean typed error ---
            if _is_quota_error(exc):
                raise QuotaExhaustedError(
                    "Gemini free-tier quota exhausted"
                ) from None
            err_str = str(exc).lower()
            # Transient service unavailable — retry with back-off
            if ("503" in err_str or "unavailable" in err_str) and attempt < MAX_API_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
                continue
            raise  # non-retryable error — bubble up immediately
    raise last_exc  # type: ignore[misc]


def _safe_serialise(obj) -> object:
    """
    Recursively convert numpy/pandas types to plain Python so they can be
    passed to Gemini's FunctionResponse (which requires JSON-serialisable values).
    """
    if isinstance(obj, dict):
        return {k: _safe_serialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_serialise(i) for i in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    return obj

def _quota_fallback_response(message: str, rag_result: dict | None) -> str:
    """
    Build a deterministic fallback answer when Gemini quota is exhausted.

    Uses:
    - The RAG knowledge-base context already fetched (no new Gemini call)
    - Deterministic tool data if the tools singleton is initialised
    - A clear user-facing notice that the AI response is unavailable

    Never fabricates numerical values.
    """
    _QUOTA_NOTICE = (
        "⚠️ **Generative AI temporarily unavailable** — the Gemini free-tier quota has been "
        "reached for today. Numerical data below comes exclusively from deterministic "
        "calculations; no values have been estimated or fabricated.\n\n"
        "---\n\n"
    )

    sections: list[str] = [_QUOTA_NOTICE]

    # --- Deterministic data from tools (if initialised) ---
    try:
        energy = tools_module.TOOL_FUNCTIONS["get_energy_summary"]()
        bldg   = tools_module.TOOL_FUNCTIONS["get_building_breakdown"]()
        anom   = tools_module.TOOL_FUNCTIONS["get_anomalies"]()
        bench  = tools_module.TOOL_FUNCTIONS["compare_to_benchmark"]()

        total_kwh  = energy.get("annual_total_kwh", "N/A")
        total_co2e = energy.get("annual_total_co2e_kg", "N/A")
        campus_eui = bench.get("campus_eui_kwh_m2_year", "N/A")
        campus_status = bench.get("campus_status", "")
        high_count = anom.get("high_count", 0)

        sections.append(
            f"**Campus summary (deterministic calculations):**\n"
            f"- Annual electricity: **{total_kwh:,.0f} kWh**\n"
            f"- Carbon footprint: **{total_co2e:,.0f} kg CO₂e**\n"
            f"- Campus EUI: **{campus_eui} kWh/m²/yr** — {campus_status}\n"
            f"- HIGH anomalies detected: **{high_count}**\n\n"
        )
    except Exception:
        # Tools not initialised or data not loaded — skip data section
        pass

    # --- RAG context (already fetched, no new Gemini call) ---
    if rag_result and rag_result.get("found"):
        ctx = rag_result.get("context_text", "").strip()
        if ctx:
            sections.append(
                "**Relevant guidance from knowledge base:**\n\n"
                + ctx
                + "\n\n"
            )

    sections.append(
        "_Generative reasoning is unavailable until the Gemini quota resets (typically midnight "
        "Pacific Time). The dashboard charts, anomaly detection, and all numerical calculations "
        "continue to work normally._"
    )

    return "".join(sections)
