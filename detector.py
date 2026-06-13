"""
Main detection pipeline — combines audio + text analysis
"""

import whisper
from dataclasses import dataclass
from typing import Optional
from audio_analyzer import analyze_audio, AudioAnalysisResult
from text_analyzer import analyze_text, TextAnalysisResult
from config import WHISPER_MODEL


@dataclass
class DetectionResult:
    verdict: str                    # FAKE / REAL / SUSPICIOUS
    confidence: float               # 0-100
    audio: AudioAnalysisResult
    text: TextAnalysisResult
    ai_generated_label: str         # "Likely AI/TTS Generated" etc.
    final_explanation: str


_whisper_model = None

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model(WHISPER_MODEL)
    return _whisper_model


def transcribe(audio_path: str) -> str:
    model = get_whisper()
    result = model.transcribe(audio_path, language="en", fp16=False)
    return result["text"].strip()


def detect(audio_path: str) -> DetectionResult:
    # Step 1 — Transcribe
    transcript = transcribe(audio_path)

    # Step 2 — Dual analysis
    audio_result = analyze_audio(audio_path)
    text_result = analyze_text(transcript)

    # Step 3 — Ensemble scoring
    # Weights: text (50%) + audio (30%) + LLM verdict (20%)
    llm_weight = {"FAKE": 90, "SUSPICIOUS": 55, "REAL": 15}.get(text_result.llm_verdict, 50)

    final_score = (
        text_result.text_suspicion_score * 0.50 +
        audio_result.audio_suspicion_score * 0.30 +
        llm_weight * 0.20
    )
    final_score = min(100.0, max(0.0, final_score))

    # Step 4 — Verdict
    if final_score >= 70:
        verdict = "FAKE"
    elif final_score >= 45:
        verdict = "SUSPICIOUS"
    else:
        verdict = "REAL"

    # Step 5 — AI voice label
    svp = audio_result.synthetic_voice_probability
    if svp >= 0.70:
        ai_label = "🤖 Very likely AI/TTS generated"
    elif svp >= 0.50:
        ai_label = "⚠️ Possibly AI/voice-cloned"
    elif svp >= 0.30:
        ai_label = "🔍 Some synthetic voice signals"
    else:
        ai_label = "✅ Likely human voice"

    # Step 6 — Explanation
    parts = []
    if text_result.primary_intent not in ["Legitimate Call", "Unknown"]:
        parts.append(f"Intent classified as **{text_result.primary_intent}**.")
    if text_result.is_impersonation and text_result.impersonated_entity:
        parts.append(f"Caller appears to impersonate **{text_result.impersonated_entity}**.")
    if text_result.pii_requested:
        parts.append(f"Sensitive data requested: {', '.join(text_result.pii_requested[:3])}.")
    if audio_result.synthetic_voice_probability >= 0.5:
        parts.append(f"Voice analysis suggests {int(svp*100)}% synthetic/AI-generated voice.")
    if text_result.urgency_level in ["HIGH", "CRITICAL"]:
        parts.append(f"**{text_result.urgency_level}** urgency pressure tactics detected.")
    if text_result.llm_explanation:
        parts.append(text_result.llm_explanation)

    explanation = " ".join(parts) if parts else "Analysis complete. No strong fraud signals detected."

    return DetectionResult(
        verdict=verdict,
        confidence=round(final_score, 1),
        audio=audio_result,
        text=text_result,
        ai_generated_label=ai_label,
        final_explanation=explanation,
    )
