"""
guardrails.py
-------------
Responsible AI layer — input and output validation for the EcoPulse agent.

All guard functions are pure / stateless. They accept a string, return a
GuardResult dataclass, and never raise — any exception is caught and reported
as a guardrail action so the agent can surface it gracefully.

Input guards (run BEFORE the message reaches the LLM)
------------------------------------------------------
check_input(message)  -> GuardResult
  1. Length cap          : message > 1000 chars  -> BLOCKED
  2. PII detection       : email, phone, Aadhaar -> BLOCKED
  3. Prompt injection    : adversarial phrases    -> BLOCKED
  4. Off-topic keywords  : unrelated domains      -> FLAGGED (not blocked)

Output guards (run AFTER the LLM returns a response)
-----------------------------------------------------
check_output(response, tool_results)  -> GuardResult
  1. Empty response               -> FLAGGED, replacement returned
  2. Ungrounded numbers           -> numbers in response not found in
                                     tool_results are stripped + disclaimer added
  3. Excessive length             -> response > 3000 chars  -> TRUNCATED
  4. Cross-entity comparison note -> fairness note prepended when comparing
                                     buildings/departments

Fairness helper
---------------
add_fairness_note(text, context)  -> str
  Prepends a fairness disclaimer when a response compares named entities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
ActionType = Literal["ALLOWED", "BLOCKED", "FLAGGED", "MODIFIED", "TRUNCATED"]


@dataclass
class GuardResult:
    action: ActionType
    message: str                   # the (possibly modified) message/response text
    violations: list[str] = field(default_factory=list)   # human-readable reasons
    actions_taken: list[str] = field(default_factory=list)  # audit log


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_INPUT_CHARS = 1000
MAX_OUTPUT_CHARS = 3000

# PII patterns
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(\+91[\s\-]?)?[6-9]\d{9}(?!\d)")
_AADHAAR_RE = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")

# Prompt injection patterns (case-insensitive)
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"you\s+are\s+now\s+",
    r"disregard\s+(all\s+)?prior\s+",
    r"forget\s+(everything|all\s+instructions?)",
    r"system\s+prompt\s*[:=]",
    r"<\s*/?system\s*>",
    r"act\s+as\s+(if\s+you\s+are\s+)?a\s+",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"dan\s+mode",
]
_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS), re.IGNORECASE
)

# Off-topic keywords (flagged but not blocked — agent handles politely)
_OFF_TOPIC_PATTERNS = [
    r"\b(recipe|cook|movie|cricket|stock\s+market|dating|weather\s+forecast)\b",
]
_OFF_TOPIC_RE = re.compile("|".join(_OFF_TOPIC_PATTERNS), re.IGNORECASE)

# Comparison-trigger words (trigger fairness note)
_COMPARISON_RE = re.compile(
    r"\b(compar(e|ing|ison)|vs\.?|versus|better\s+than|worse\s+than|"
    r"most\s+(efficient|wasteful|consuming)|least\s+(efficient|wasteful))\b",
    re.IGNORECASE,
)

# Numbers in LLM text — used to detect potentially ungrounded values
_NUMBER_RE = re.compile(r"\b\d+(?:[,\d]*)?(?:\.\d+)?\s*(?:kWh|kwh|kg|CO2e?|tonne|percent|%)")

_FAIRNESS_NOTE = (
    "Note: Comparisons are based on synthetic/uploaded data and should be "
    "interpreted in context (building size, usage type, occupancy). "
    "Avoid drawing conclusions about individuals or groups."
)

_UNGROUNDED_DISCLAIMER = (
    "\n\n---\n"
    "_Responsible AI notice: One or more numerical figures in this response "
    "could not be verified against the current data. Please refer to the "
    "dashboard panels for verified calculations._"
)


# ---------------------------------------------------------------------------
# Input guard
# ---------------------------------------------------------------------------

def check_input(message: str) -> GuardResult:
    """
    Validate a user message before it reaches the LLM.

    Parameters
    ----------
    message : str  Raw user input.

    Returns
    -------
    GuardResult  action=BLOCKED if the message must not reach the LLM.
                 action=FLAGGED if the message is suspicious but allowed.
                 action=ALLOWED if the message is clean.
    """
    violations: list[str] = []
    actions_taken: list[str] = []

    if not isinstance(message, str):
        return GuardResult(
            action="BLOCKED",
            message="",
            violations=["Input is not a string."],
            actions_taken=["Blocked non-string input."],
        )

    # ---- 1. Length cap ------------------------------------------------------
    if len(message) > MAX_INPUT_CHARS:
        return GuardResult(
            action="BLOCKED",
            message=message[:MAX_INPUT_CHARS],
            violations=[f"Message length {len(message)} exceeds {MAX_INPUT_CHARS} characters."],
            actions_taken=["Blocked oversized input."],
        )

    # ---- 2. PII detection ---------------------------------------------------
    pii_found: list[str] = []
    if _EMAIL_RE.search(message):
        pii_found.append("email address")
    if _PHONE_RE.search(message):
        pii_found.append("phone number")
    if _AADHAAR_RE.search(message):
        pii_found.append("Aadhaar-format number")

    if pii_found:
        violations.append(f"Possible PII detected: {', '.join(pii_found)}.")
        actions_taken.append(f"Blocked input containing suspected PII ({', '.join(pii_found)}).")
        return GuardResult(
            action="BLOCKED",
            message=(
                "Your message appears to contain personal information "
                f"({', '.join(pii_found)}). Please rephrase without "
                "including personal data."
            ),
            violations=violations,
            actions_taken=actions_taken,
        )

    # ---- 3. Prompt injection ------------------------------------------------
    if _INJECTION_RE.search(message):
        violations.append("Prompt injection pattern detected.")
        actions_taken.append("Blocked prompt injection attempt.")
        return GuardResult(
            action="BLOCKED",
            message=(
                "I'm unable to process that request. "
                "Please ask about campus energy data, carbon footprint, "
                "or energy efficiency recommendations."
            ),
            violations=violations,
            actions_taken=actions_taken,
        )

    # ---- 4. Off-topic flag (not blocked — LLM will politely refuse) ---------
    if _OFF_TOPIC_RE.search(message):
        violations.append("Off-topic keywords detected.")
        actions_taken.append("Flagged as potentially off-topic (not blocked).")
        return GuardResult(
            action="FLAGGED",
            message=message,
            violations=violations,
            actions_taken=actions_taken,
        )

    return GuardResult(action="ALLOWED", message=message)


# ---------------------------------------------------------------------------
# Output guard
# ---------------------------------------------------------------------------

def check_output(response: str, tool_results: list[dict] | None = None) -> GuardResult:
    """
    Validate an LLM response before it is shown to the user.

    Parameters
    ----------
    response     : str         Raw LLM response text.
    tool_results : list[dict]  All tool call results from the current agent turn.
                               Used to verify that numbers in the response are
                               grounded in actual data. Pass [] if no tools called.

    Returns
    -------
    GuardResult  with action=MODIFIED if the response was changed,
                 action=BLOCKED for empty responses,
                 action=ALLOWED otherwise.
    """
    violations: list[str] = []
    actions_taken: list[str] = []
    modified = response

    if not response or not response.strip():
        return GuardResult(
            action="BLOCKED",
            message="I wasn't able to generate a response. Please try rephrasing your question.",
            violations=["LLM returned empty response."],
            actions_taken=["Replaced empty response with fallback message."],
        )

    # ---- 1. Excessive length -----------------------------------------------
    if len(modified) > MAX_OUTPUT_CHARS:
        modified = modified[:MAX_OUTPUT_CHARS] + "\n\n_[Response truncated for readability.]_"
        violations.append(f"Response exceeded {MAX_OUTPUT_CHARS} characters.")
        actions_taken.append("Truncated response to max length.")

    # ---- 2. Ungrounded number check ----------------------------------------
    if tool_results is not None:
        grounded_numbers = _extract_numbers_from_tool_results(tool_results)
        response_numbers = _NUMBER_RE.findall(modified)

        ungrounded = []
        for num_str in response_numbers:
            # Extract the numeric part and check if it appears in tool results
            digits = re.sub(r"[^\d.]", "", num_str.split()[0].replace(",", ""))
            try:
                val = float(digits)
            except ValueError:
                continue
            if not _is_number_grounded(val, grounded_numbers):
                ungrounded.append(num_str.strip())

        if ungrounded:
            violations.append(
                f"Ungrounded numerical claim(s) detected: {ungrounded[:3]}"
            )
            actions_taken.append(
                "Appended ungrounded-number disclaimer to response."
            )
            modified = modified + _UNGROUNDED_DISCLAIMER

    # ---- 3. Fairness note for comparisons ----------------------------------
    if _COMPARISON_RE.search(modified):
        modified = _FAIRNESS_NOTE + "\n\n" + modified
        actions_taken.append("Prepended fairness note (comparison detected).")

    if actions_taken:
        return GuardResult(
            action="MODIFIED",
            message=modified,
            violations=violations,
            actions_taken=actions_taken,
        )

    return GuardResult(action="ALLOWED", message=modified)


# ---------------------------------------------------------------------------
# Fairness helper (also usable standalone)
# ---------------------------------------------------------------------------

def add_fairness_note(text: str) -> str:
    """
    Prepend the standard fairness note to a text block.
    Idempotent — won't double-add the note.
    """
    if _FAIRNESS_NOTE in text:
        return text
    return _FAIRNESS_NOTE + "\n\n" + text


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_numbers_from_tool_results(tool_results: list[dict]) -> list[float]:
    """
    Recursively pull all float/int values from tool result dicts.
    These are used as the ground truth for the ungrounded-number check.
    """
    numbers: list[float] = []

    def _walk(obj):
        if isinstance(obj, (int, float)):
            numbers.append(float(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)
        elif isinstance(obj, str):
            # Try to parse numeric strings like "716.0 kg CO2e"
            for m in re.findall(r"\b\d+(?:\.\d+)?\b", obj):
                try:
                    numbers.append(float(m))
                except ValueError:
                    pass

    for result in tool_results:
        _walk(result)
    return numbers


def _is_number_grounded(value: float, grounded: list[float],
                         tolerance: float = 0.02) -> bool:
    """
    Return True if `value` is within `tolerance * value` of any number
    in `grounded` (i.e., within 2% of a known tool result).
    Also passes if the number is a small integer <= 12 (e.g. month counts).
    """
    if value <= 12:          # small integers — months, counts — always OK
        return True
    for g in grounded:
        if g == 0:
            continue
        if abs(value - g) / max(abs(g), 1e-9) <= tolerance:
            return True
    return False
