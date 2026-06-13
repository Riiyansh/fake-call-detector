"""
Text Track Analysis
Uses Groq LLM + rule-based patterns to detect:
- Scam intent classification
- Urgency / threat language
- PII requests (OTP, card, SSN, etc.)
- Impersonation patterns
- Call summary generation
"""

import re
import json
import requests
from dataclasses import dataclass, field
from typing import List, Optional
from config import GROQ_API_KEY, GROQ_MODEL

# ── Keyword patterns ──────────────────────────────────────────────────────────

URGENCY_PATTERNS = [
    r"\b(urgent|immediately|right now|act now|within \d+ hours?|last chance|deadline|expire[sd]?)\b",
    r"\b(suspended?|blocked?|frozen|deactivated?|terminated?)\b",
    r"\b(arrest|police|lawsuit|legal action|court|jail|prison)\b",
    r"\b(final notice|last warning|immediately contact)\b",
]

PII_PATTERNS = [
    r"\b(otp|one.?time.?password|verification code|pin)\b",
    r"\b(credit card|debit card|card number|cvv|expiry)\b",
    r"\b(social security|ssn|aadhar|pan card|passport)\b",
    r"\b(bank account|account number|ifsc|routing number)\b",
    r"\b(password|login|credentials|username)\b",
]

IMPERSONATION_PATTERNS = [
    r"\b(sbi|hdfc|icici|axis|rbi|reserve bank|central bank)\b",
    r"\b(irs|income tax|it department|tax department)\b",
    r"\b(police|cbi|ed|enforcement directorate|cyber crime)\b",
    r"\b(amazon|flipkart|microsoft|google|apple|paypal)\b",
    r"\b(insurance|policy|claim|beneficiary)\b",
    r"\b(calling from|representative of|officer from|department of)\b",
]

REWARD_SCAM_PATTERNS = [
    r"\b(won|winner|lottery|prize|reward|gift|free|congratulations)\b",
    r"\b(refund|cashback|compensation|claim your)\b",
    r"\b(investment|returns|profit|double your money|crypto)\b",
]


def _score_patterns(text: str, patterns: List[str]) -> tuple[int, List[str]]:
    text_lower = text.lower()
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text_lower)
        matches.extend(found)
    return len(matches), list(set(matches))


# ── LLM analysis ─────────────────────────────────────────────────────────────

def _groq(prompt: str, system: str, max_tokens: int = 800) -> str:
    if not GROQ_API_KEY:
        return ""
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.1,
            },
            timeout=20,
        )
        r = resp.json()
        return r["choices"][0]["message"]["content"].strip() if "choices" in r else ""
    except Exception:
        return ""


@dataclass
class TextAnalysisResult:
    transcript: str
    call_summary: str
    primary_intent: str
    secondary_intent: str
    urgency_level: str           # LOW / MEDIUM / HIGH / CRITICAL
    is_impersonation: bool
    impersonated_entity: str
    pii_requested: List[str]
    urgency_keywords: List[str]
    reward_scam_signals: List[str]
    sentiment: str               # NEUTRAL / NEGATIVE / THREATENING
    pressure_tactics: List[str]
    text_suspicion_score: float  # 0-100
    flags: List[str]
    llm_verdict: str
    llm_explanation: str


def analyze_text(transcript: str) -> TextAnalysisResult:
    flags = []
    text_lower = transcript.lower()

    # ── Rule-based scoring ────────────────────────────────────────────────────
    urgency_count, urgency_kws = _score_patterns(transcript, URGENCY_PATTERNS)
    pii_count, pii_items = _score_patterns(transcript, PII_PATTERNS)
    impersonation_count, impersonated = _score_patterns(transcript, IMPERSONATION_PATTERNS)
    reward_count, reward_signals = _score_patterns(transcript, REWARD_SCAM_PATTERNS)

    # Flag based on rules
    if urgency_count >= 2:
        flags.append("Multiple urgency/threat phrases detected")
    if pii_count >= 1:
        flags.append(f"Sensitive information requested: {', '.join(pii_items[:3])}")
    if impersonation_count >= 1:
        flags.append(f"Possible impersonation: {', '.join(impersonated[:2])}")
    if reward_count >= 2:
        flags.append("Reward/prize scam pattern detected")

    # ── LLM deep analysis ────────────────────────────────────────────────────
    system_prompt = (
        "You are a fraud detection expert analyzing call transcripts. "
        "Analyze the transcript and return a JSON object with these exact keys:\n"
        "- summary: 2-3 sentence plain English summary of what the caller is trying to do\n"
        "- primary_intent: one of [Financial Fraud, Impersonation Scam, Threat/Extortion, "
        "Reward Scam, Technical Support Scam, Romance Scam, Political Scam, Legitimate Call, Unknown]\n"
        "- secondary_intent: brief secondary intent or empty string\n"
        "- urgency_level: one of [LOW, MEDIUM, HIGH, CRITICAL]\n"
        "- is_impersonation: true/false\n"
        "- impersonated_entity: name of entity being impersonated or empty string\n"
        "- sentiment: one of [NEUTRAL, NEGATIVE, THREATENING, FRIENDLY_SUSPICIOUS]\n"
        "- pressure_tactics: list of specific pressure tactics used\n"
        "- fake_probability: 0-100 integer\n"
        "- explanation: 2-3 sentences explaining why this is or isn't a scam call\n"
        "Return ONLY valid JSON, no other text."
    )

    llm_raw = _groq(
        f"Analyze this call transcript:\n\n{transcript[:3000]}",
        system_prompt,
        max_tokens=600,
    )

    # Parse LLM response
    llm_data = {}
    try:
        match = re.search(r"\{.*\}", llm_raw, re.DOTALL)
        if match:
            llm_data = json.loads(match.group())
    except Exception:
        pass

    call_summary = llm_data.get("summary", _fallback_summary(transcript))
    primary_intent = llm_data.get("primary_intent", _classify_intent_fallback(text_lower))
    secondary_intent = llm_data.get("secondary_intent", "")
    urgency_level = llm_data.get("urgency_level", _urgency_fallback(urgency_count))
    is_impersonation = llm_data.get("is_impersonation", impersonation_count > 0)
    impersonated_entity = llm_data.get("impersonated_entity", ", ".join(impersonated[:2]))
    sentiment = llm_data.get("sentiment", "NEUTRAL")
    pressure_tactics = llm_data.get("pressure_tactics", [])
    llm_fake_prob = llm_data.get("fake_probability", 50)
    llm_explanation = llm_data.get("explanation", "")
    llm_verdict = "FAKE" if llm_fake_prob >= 60 else "REAL" if llm_fake_prob <= 30 else "SUSPICIOUS"

    # ── Combined suspicion score ─────────────────────────────────────────────
    rule_score = (
        min(urgency_count * 10, 30) +
        min(pii_count * 15, 35) +
        min(impersonation_count * 10, 20) +
        min(reward_count * 8, 15)
    )
    text_suspicion = (rule_score * 0.4 + llm_fake_prob * 0.6)
    text_suspicion = min(100.0, text_suspicion)

    return TextAnalysisResult(
        transcript=transcript,
        call_summary=call_summary,
        primary_intent=primary_intent,
        secondary_intent=secondary_intent,
        urgency_level=urgency_level,
        is_impersonation=bool(is_impersonation),
        impersonated_entity=str(impersonated_entity),
        pii_requested=pii_items[:5],
        urgency_keywords=urgency_kws[:5],
        reward_scam_signals=reward_signals[:3],
        sentiment=sentiment,
        pressure_tactics=pressure_tactics[:5],
        text_suspicion_score=round(text_suspicion, 1),
        flags=flags,
        llm_verdict=llm_verdict,
        llm_explanation=llm_explanation,
    )


def _fallback_summary(text: str) -> str:
    return text[:200] + "..." if len(text) > 200 else text


def _classify_intent_fallback(text: str) -> str:
    if any(w in text for w in ["otp", "account", "bank", "card"]):
        return "Financial Fraud"
    if any(w in text for w in ["won", "prize", "lottery", "reward"]):
        return "Reward Scam"
    if any(w in text for w in ["arrest", "police", "legal"]):
        return "Threat/Extortion"
    if any(w in text for w in ["microsoft", "apple", "virus", "computer"]):
        return "Technical Support Scam"
    return "Unknown"


def _urgency_fallback(urgency_count: int) -> str:
    if urgency_count >= 4:
        return "CRITICAL"
    if urgency_count >= 2:
        return "HIGH"
    if urgency_count >= 1:
        return "MEDIUM"
    return "LOW"
