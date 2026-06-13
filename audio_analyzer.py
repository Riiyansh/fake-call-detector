"""
Audio Track Analysis
Extracts acoustic features to detect:
- Synthetic/AI-generated voices (TTS, voice cloning)
- Robocall patterns (unnatural pauses, timing)
- Voice quality anomalies
"""

import numpy as np
import librosa
from dataclasses import dataclass
from typing import List


@dataclass
class AudioAnalysisResult:
    synthetic_voice_probability: float   # 0-1
    unnatural_pause_count: int
    voice_consistency_score: float       # 0-100 (lower = more robotic)
    avg_pause_duration_ms: float
    spectral_flatness_score: float       # higher = more synthetic
    pitch_variation_score: float         # lower = more monotone/TTS
    speaking_rate_wpm_estimate: float
    audio_suspicion_score: float         # 0-100
    flags: List[str]


def analyze_audio(audio_path: str) -> AudioAnalysisResult:
    y, sr = librosa.load(audio_path, sr=16000, mono=True)
    flags = []

    # ── MFCC features ──────────────────────────────────────────────────────
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_var = float(np.mean(np.var(mfccs, axis=1)))

    # ── Spectral features ───────────────────────────────────────────────────
    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_flatness = librosa.feature.spectral_flatness(y=y)[0]
    avg_flatness = float(np.mean(spectral_flatness))

    # ── Pitch (F0) analysis ─────────────────────────────────────────────────
    f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=400, sr=sr)
    f0_clean = f0[voiced_flag & ~np.isnan(f0)] if f0 is not None else np.array([])
    pitch_std = float(np.std(f0_clean)) if len(f0_clean) > 10 else 0.0
    pitch_variation_score = min(100.0, pitch_std * 2)

    # ── Pause detection ─────────────────────────────────────────────────────
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    silence_threshold = np.percentile(rms, 15)
    is_silent = rms < silence_threshold

    pause_count = 0
    pause_durations = []
    in_pause = False
    pause_start = 0
    frame_duration_ms = (hop_length / sr) * 1000

    for i, silent in enumerate(is_silent):
        if silent and not in_pause:
            in_pause = True
            pause_start = i
        elif not silent and in_pause:
            in_pause = False
            duration_ms = (i - pause_start) * frame_duration_ms
            if duration_ms > 300:  # Pauses > 300ms are notable
                pause_count += 1
                pause_durations.append(duration_ms)

    avg_pause_ms = float(np.mean(pause_durations)) if pause_durations else 0.0

    # ── Voice consistency (TTS tends to be very consistent) ─────────────────
    centroid_std = float(np.std(spectral_centroids))
    voice_consistency_score = min(100.0, centroid_std / 50)
    # Invert: very consistent (low std) = low score (more robotic)
    voice_consistency_score = max(0.0, 100.0 - voice_consistency_score * 2)

    # ── Speaking rate estimate ───────────────────────────────────────────────
    duration_s = len(y) / sr
    # Rough estimate: voiced frames → syllables
    voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag is not None else 0.3
    estimated_syllables = voiced_ratio * duration_s * 4
    speaking_rate_wpm = (estimated_syllables / 1.5) / (duration_s / 60) if duration_s > 0 else 0

    # ── Synthetic voice probability ─────────────────────────────────────────
    synth_score = 0.0

    # High spectral flatness = more noise-like / synthetic
    if avg_flatness > 0.01:
        synth_score += 25
        flags.append("High spectral flatness (synthetic voice signal)")

    # Low pitch variation = TTS/monotone
    if pitch_variation_score < 20:
        synth_score += 30
        flags.append("Low pitch variation (monotone/TTS pattern)")
    elif pitch_variation_score < 35:
        synth_score += 15

    # Low MFCC variance = uniform speech = TTS
    if mfcc_var < 20:
        synth_score += 20
        flags.append("Low MFCC variance (uniform speech pattern)")

    # Unnatural pause patterns
    if pause_count > 5:
        synth_score += 15
        flags.append(f"Frequent unnatural pauses ({pause_count} detected)")
    elif pause_count > 3:
        synth_score += 8

    # Robocall speaking rate (too fast or too perfectly paced)
    if speaking_rate_wpm > 180:
        synth_score += 10
        flags.append("Unusually fast speaking rate (robocall pattern)")

    synthetic_voice_probability = min(1.0, synth_score / 100)

    # ── Overall audio suspicion score ────────────────────────────────────────
    audio_suspicion = (
        synthetic_voice_probability * 60 +
        (min(pause_count, 10) / 10) * 20 +
        (1 - min(voice_consistency_score, 100) / 100) * 20
    ) * 100 / 100

    audio_suspicion = min(100.0, audio_suspicion)

    return AudioAnalysisResult(
        synthetic_voice_probability=round(synthetic_voice_probability, 3),
        unnatural_pause_count=pause_count,
        voice_consistency_score=round(voice_consistency_score, 1),
        avg_pause_duration_ms=round(avg_pause_ms, 1),
        spectral_flatness_score=round(avg_flatness * 1000, 3),
        pitch_variation_score=round(pitch_variation_score, 1),
        speaking_rate_wpm_estimate=round(speaking_rate_wpm, 1),
        audio_suspicion_score=round(audio_suspicion, 1),
        flags=flags,
    )
