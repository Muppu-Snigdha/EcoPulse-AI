"""
dashboard/chat.py — Premium ChatGPT-style AI assistant interface.
All agent logic unchanged (modules/agent/agent_core.py).
"""
from __future__ import annotations
import streamlit as st
from modules.agent.agent_core import ask, QuotaExhaustedError

_RAI_NOTICE = (
    "🔒 <strong>Responsible AI:</strong> All numerical figures (kWh, CO₂e, EUI) "
    "come exclusively from deterministic Python calculations — never from the language model. "
    "Every response includes a full audit trace showing which tools were called and which "
    "knowledge-base sources were retrieved."
)

_SUGGESTED_QUESTIONS = [
    "Which building consumed the most electricity this year?",
    "What is the total campus carbon footprint?",
    "Are there any energy anomalies I should investigate?",
    "How can I reduce HVAC energy consumption?",
    "Which buildings are above the BEE benchmark?",
]


def render(df, anomalies):
    st.markdown("""
    <div class="ep-page-header">
        <div class="ep-page-title">🤖 AI Energy Assistant</div>
        <div class="ep-page-subtitle">
            Ask questions about campus energy — powered by Gemini + RAG + deterministic calculations
        </div>
    </div>
    """, unsafe_allow_html=True)

    # RAI notice
    st.markdown(f'<div class="ep-rai-notice">ℹ️ {_RAI_NOTICE}</div>', unsafe_allow_html=True)

    # Initialise session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Top bar: clear button + message count
    col_info, col_btn = st.columns([5, 1])
    with col_info:
        n = len([m for m in st.session_state.messages if m["role"] == "user"])
        if n > 0:
            st.caption(f"💬 {n} question{'s' if n != 1 else ''} in this session")
    with col_btn:
        if st.button("🗑️ Clear", use_container_width=True, key="chat_clear"):
            st.session_state.messages = []
            st.rerun()

    # Suggested questions (show only when no messages yet)
    if not st.session_state.messages:
        st.markdown("""
        <div style="margin:16px 0 8px;">
            <div style="font-size:12px;color:#94a3b8;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;margin-bottom:10px;">
                Suggested Questions
            </div>
        </div>
        """, unsafe_allow_html=True)
        cols = st.columns(len(_SUGGESTED_QUESTIONS))
        for i, (col, q) in enumerate(zip(cols, _SUGGESTED_QUESTIONS)):
            with col:
                if st.button(q, key=f"sugg_{i}", use_container_width=True):
                    _handle_message(q)
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Render existing messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant":
                # Sources panel
                sources = msg.get("sources", [])
                if sources:
                    tags = "".join(f'<span class="ep-source-tag">{s}</span>' for s in sources)
                    st.markdown(
                        f'<div class="ep-sources-panel">'
                        f'<strong>SOURCES &amp; EVIDENCE</strong><br>{tags}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # Reasoning trace expander
                trace_md = msg.get("trace_markdown", "")
                if trace_md:
                    with st.expander("🔍 How I answered this — Reasoning Trace", expanded=False):
                        st.markdown(trace_md)

    # Chat input
    if prompt := st.chat_input("Ask about energy consumption, carbon footprint, anomalies, or efficiency tips…"):
        _handle_message(prompt)
        st.rerun()


def _handle_message(prompt: str) -> None:
    """Process a user message through the agent and append to session history."""
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Build history for the agent (last 10 turns)
    history = []
    for msg in st.session_state.messages[:-1][-10:]:
        history.append({"role": msg["role"], "parts": [msg["content"]]})

    # Call agent
    with st.spinner("EcoPulse is thinking…"):
        try:
            response = ask(prompt, history=history)
            assistant_msg = {
                "role": "assistant",
                "content": response.text,
                "sources": response.sources,
                "trace_markdown": response.trace_markdown,
            }
        except QuotaExhaustedError:
            # Should not normally reach here — agent_core handles it internally,
            # but guard here as a belt-and-braces safety net.
            assistant_msg = {
                "role": "assistant",
                "content": (
                    "⚠️ **Generative AI temporarily unavailable.** The Gemini free-tier "
                    "quota has been reached for today. The dashboard charts, anomaly "
                    "detection, and all numerical calculations continue to work normally. "
                    "Please try again later or check the Overview / Building Analysis pages "
                    "for deterministic data."
                ),
                "sources": [],
                "trace_markdown": "",
            }
        except EnvironmentError:
            assistant_msg = {
                "role": "assistant",
                "content": (
                    "⚠️ **AI Assistant is not configured.** "
                    "The GEMINI_API_KEY is missing from the `.env` file. "
                    "Please add it and restart the app."
                ),
                "sources": [],
                "trace_markdown": "",
            }
        except Exception:
            assistant_msg = {
                "role": "assistant",
                "content": (
                    "⚠️ **An unexpected error occurred.** "
                    "The AI Assistant could not process your request. "
                    "Please try again or rephrase your question."
                ),
                "sources": [],
                "trace_markdown": "",
            }

    st.session_state.messages.append(assistant_msg)
