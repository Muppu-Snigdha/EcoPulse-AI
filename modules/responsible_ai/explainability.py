"""
explainability.py
-----------------
Builds and formats reasoning traces for every agent response.

A reasoning trace is a structured record of exactly how the agent produced
its answer — which tools were called, what they returned, which RAG chunks
were retrieved, and what the guardrail layer did to the response.

The trace is attached to every AgentResponse and is rendered in the
Streamlit chat UI as a collapsed "How I answered this" expander.

Public API
----------
build_trace(tool_calls, rag_result, input_guard, output_guard) -> ReasoningTrace
format_trace_markdown(trace)                                   -> str
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ToolCallRecord:
    """Record of a single tool invocation and its result."""
    tool_name: str
    arguments: dict[str, Any]
    result: Any
    iteration: int          # which agent loop iteration called this tool (1-indexed)


@dataclass
class RagChunkRecord:
    """Record of a single RAG chunk retrieved during the agent turn."""
    chunk_id: str
    source_file: str
    relevance_score: float  # cosine similarity (0–1, higher = more relevant)
    text_preview: str       # first 200 characters of the chunk


@dataclass
class GuardrailRecord:
    """Record of a guardrail action (input or output)."""
    stage: str              # "input" or "output"
    action: str             # ALLOWED / BLOCKED / FLAGGED / MODIFIED / TRUNCATED
    violations: list[str]
    actions_taken: list[str]


@dataclass
class ReasoningTrace:
    """
    Complete audit trail for one agent response.

    Fields
    ------
    tools_called   : ordered list of tool calls made during the agent turn
    rag_chunks     : RAG chunks retrieved (may be empty if no RAG query fired)
    guardrail_input  : result of the input guardrail check
    guardrail_output : result of the output guardrail check
    iteration_count  : total number of agent loop iterations used
    sources        : de-duplicated list of source attributions for the UI
    """
    tools_called: list[ToolCallRecord] = field(default_factory=list)
    rag_chunks: list[RagChunkRecord] = field(default_factory=list)
    guardrail_input: GuardrailRecord | None = None
    guardrail_output: GuardrailRecord | None = None
    iteration_count: int = 0
    sources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_trace(
    tool_calls: list[dict] | None = None,
    rag_result: dict | None = None,
    input_guard_result=None,
    output_guard_result=None,
    iteration_count: int = 0,
) -> ReasoningTrace:
    """
    Assemble a ReasoningTrace from the raw data collected during an agent turn.

    Parameters
    ----------
    tool_calls : list[dict]
        Each dict must have keys: tool_name, arguments, result, iteration.
    rag_result : dict | None
        Output of retriever.get_context_with_metadata — has keys: chunks, found.
    input_guard_result : GuardResult | None
        Output of guardrails.check_input.
    output_guard_result : GuardResult | None
        Output of guardrails.check_output.
    iteration_count : int
        Number of agent loop iterations completed.

    Returns
    -------
    ReasoningTrace
    """
    trace = ReasoningTrace(iteration_count=iteration_count)

    # ---- Tool calls --------------------------------------------------------
    for tc in (tool_calls or []):
        trace.tools_called.append(
            ToolCallRecord(
                tool_name=tc.get("tool_name", "unknown"),
                arguments=tc.get("arguments", {}),
                result=tc.get("result"),
                iteration=tc.get("iteration", 0),
            )
        )

    # ---- RAG chunks --------------------------------------------------------
    if rag_result and rag_result.get("found"):
        for chunk in rag_result.get("chunks", []):
            preview = chunk.get("text", "")[:200].replace("\n", " ")
            trace.rag_chunks.append(
                RagChunkRecord(
                    chunk_id=chunk.get("id", ""),
                    source_file=chunk.get("source", ""),
                    relevance_score=chunk.get("score", 0.0),
                    text_preview=preview,
                )
            )

    # ---- Guardrail records -------------------------------------------------
    if input_guard_result is not None:
        trace.guardrail_input = GuardrailRecord(
            stage="input",
            action=input_guard_result.action,
            violations=input_guard_result.violations,
            actions_taken=input_guard_result.actions_taken,
        )

    if output_guard_result is not None:
        trace.guardrail_output = GuardrailRecord(
            stage="output",
            action=output_guard_result.action,
            violations=output_guard_result.violations,
            actions_taken=output_guard_result.actions_taken,
        )

    # ---- Source attribution ------------------------------------------------
    sources: list[str] = []
    tool_names_used = [tc.tool_name for tc in trace.tools_called]
    if tool_names_used:
        sources.append(f"Tools: {', '.join(dict.fromkeys(tool_names_used))}")
    for chunk in trace.rag_chunks:
        src = f"Knowledge base: {chunk.source_file} (score {chunk.relevance_score:.2f})"
        if src not in sources:
            sources.append(src)
    trace.sources = sources

    return trace


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

def format_trace_markdown(trace: ReasoningTrace) -> str:
    """
    Render a ReasoningTrace as a Markdown string suitable for display
    inside a Streamlit expander.

    Returns
    -------
    str  Markdown-formatted trace.
    """
    lines: list[str] = []

    lines.append("### How I answered this")
    lines.append(f"*Agent loop iterations used: {trace.iteration_count}*")
    lines.append("")

    # ---- Sources summary ---------------------------------------------------
    if trace.sources:
        lines.append("**Sources used in this answer:**")
        for src in trace.sources:
            lines.append(f"- {src}")
        lines.append("")

    # ---- Tool calls --------------------------------------------------------
    if trace.tools_called:
        lines.append("**Tool calls:**")
        for tc in trace.tools_called:
            lines.append(f"- **Iteration {tc.iteration}** → `{tc.tool_name}`")
            if tc.arguments:
                args_str = ", ".join(f"{k}={v!r}" for k, v in tc.arguments.items())
                lines.append(f"  - Arguments: `{args_str}`")
            if tc.result is not None:
                result_preview = str(tc.result)[:300]
                lines.append(f"  - Result (preview): `{result_preview}`")
        lines.append("")
    else:
        lines.append("**Tool calls:** _(none — answered from knowledge base or context)_")
        lines.append("")

    # ---- RAG chunks --------------------------------------------------------
    if trace.rag_chunks:
        lines.append("**Knowledge base chunks retrieved:**")
        for chunk in trace.rag_chunks:
            lines.append(
                f"- `{chunk.chunk_id}` from **{chunk.source_file}** "
                f"(relevance: {chunk.relevance_score:.2f})"
            )
            lines.append(f"  > {chunk.text_preview}…")
        lines.append("")
    else:
        lines.append("**Knowledge base:** _(not queried)_")
        lines.append("")

    # ---- Guardrail actions -------------------------------------------------
    lines.append("**Responsible AI checks:**")
    for record in [trace.guardrail_input, trace.guardrail_output]:
        if record is None:
            continue
        stage_label = record.stage.capitalize()
        icon = "✅" if record.action == "ALLOWED" else "⚠️"
        lines.append(f"- {icon} {stage_label} guard: **{record.action}**")
        for v in record.violations:
            lines.append(f"  - Violation: {v}")
        for a in record.actions_taken:
            lines.append(f"  - Action taken: {a}")
    if trace.guardrail_input is None and trace.guardrail_output is None:
        lines.append("- _(no guard records)_")

    return "\n".join(lines)
