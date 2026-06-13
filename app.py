import gradio as gr
import tempfile
import os
from detector import detect

VERDICT_COLORS = {
    "FAKE": "#ef4444",
    "SUSPICIOUS": "#f97316",
    "REAL": "#22c55e",
}

URGENCY_COLORS = {
    "LOW": "#22c55e",
    "MEDIUM": "#eab308",
    "HIGH": "#f97316",
    "CRITICAL": "#ef4444",
}

SAMPLE_CALLS = {
    "🏦 Bank OTP Scam": "sample_calls/bank_scam.txt",
    "🏆 Lottery Scam": "sample_calls/lottery_scam.txt",
    "👮 Police Threat": "sample_calls/police_threat.txt",
}


def analyze_call(audio_file, text_input):
    if audio_file is None and not text_input.strip():
        return [gr.update(visible=False)] * 10 + ["Please upload an audio file or paste a transcript."]

    try:
        if audio_file is not None:
            result = detect(audio_file)
        else:
            # Text-only mode
            from audio_analyzer import AudioAnalysisResult
            from text_analyzer import analyze_text
            from detector import DetectionResult

            text_result = analyze_text(text_input)
            dummy_audio = AudioAnalysisResult(
                synthetic_voice_probability=0.0,
                unnatural_pause_count=0,
                voice_consistency_score=50.0,
                avg_pause_duration_ms=0.0,
                spectral_flatness_score=0.0,
                pitch_variation_score=50.0,
                speaking_rate_wpm_estimate=0.0,
                audio_suspicion_score=0.0,
                flags=["Audio not provided — text-only analysis"],
            )
            llm_weight = {"FAKE": 90, "SUSPICIOUS": 55, "REAL": 15}.get(text_result.llm_verdict, 50)
            score = min(100.0, text_result.text_suspicion_score * 0.7 + llm_weight * 0.3)
            verdict = "FAKE" if score >= 70 else "SUSPICIOUS" if score >= 45 else "REAL"

            result = DetectionResult(
                verdict=verdict,
                confidence=round(score, 1),
                audio=dummy_audio,
                text=text_result,
                ai_generated_label="🎵 No audio provided",
                final_explanation=text_result.llm_explanation or "Text-only analysis completed.",
            )

        r = result
        t = result.text
        a = result.audio
        color = VERDICT_COLORS.get(r.verdict, "#94a3b8")
        urgency_color = URGENCY_COLORS.get(t.urgency_level, "#94a3b8")

        # ── Verdict banner ───────────────────────────────────────────────────
        verdict_icon = {"FAKE": "🚨", "SUSPICIOUS": "⚠️", "REAL": "✅"}.get(r.verdict, "❓")
        verdict_html = f"""
        <div style="background:{color}22; border:2px solid {color}; border-radius:12px; padding:20px; text-align:center; margin:8px 0;">
            <div style="font-size:2.5em; margin-bottom:4px;">{verdict_icon}</div>
            <div style="font-size:1.8em; font-weight:700; color:{color};">{r.verdict}</div>
            <div style="font-size:1.1em; color:#e2e8f0; margin-top:4px;">{r.confidence:.0f}% confidence</div>
        </div>
        """

        # ── Score breakdown ──────────────────────────────────────────────────
        def bar(val, color="#6366f1"):
            return f"""<div style="background:#1e293b; border-radius:6px; height:10px; width:100%; margin:4px 0;">
                <div style="background:{color}; width:{val:.0f}%; height:100%; border-radius:6px;"></div></div>"""

        scores_html = f"""
        <div style="background:#1e293b; border-radius:10px; padding:16px;">
            <div style="color:#94a3b8; font-size:0.85em; margin-bottom:10px; text-transform:uppercase; letter-spacing:0.05em;">Score Breakdown</div>
            <div style="margin:8px 0;">
                <div style="display:flex; justify-content:space-between; color:#e2e8f0; font-size:0.9em;">
                    <span>📝 Text Analysis</span><span><b>{t.text_suspicion_score:.0f}%</b></span>
                </div>{bar(t.text_suspicion_score, "#6366f1")}
            </div>
            <div style="margin:8px 0;">
                <div style="display:flex; justify-content:space-between; color:#e2e8f0; font-size:0.9em;">
                    <span>🎵 Audio Analysis</span><span><b>{a.audio_suspicion_score:.0f}%</b></span>
                </div>{bar(a.audio_suspicion_score, "#f97316")}
            </div>
            <div style="margin:8px 0;">
                <div style="display:flex; justify-content:space-between; color:#e2e8f0; font-size:0.9em;">
                    <span>🤖 AI Voice Score</span><span><b>{a.synthetic_voice_probability*100:.0f}%</b></span>
                </div>{bar(a.synthetic_voice_probability*100, "#ef4444")}
            </div>
            <div style="margin-top:12px; padding:10px; background:#0f172a; border-radius:8px; color:#a3e635; font-size:0.85em;">
                {r.ai_generated_label}
            </div>
        </div>
        """

        # ── Summary + Intent ─────────────────────────────────────────────────
        pii_badges = "".join(
            f'<span style="background:#7f1d1d; color:#fca5a5; padding:2px 8px; border-radius:8px; margin:2px; font-size:0.8em;">{p}</span>'
            for p in t.pii_requested
        ) if t.pii_requested else '<span style="color:#64748b">None detected</span>'

        tactic_badges = "".join(
            f'<span style="background:#431407; color:#fed7aa; padding:2px 8px; border-radius:8px; margin:2px; font-size:0.8em;">{tac}</span>'
            for tac in t.pressure_tactics[:4]
        ) if t.pressure_tactics else '<span style="color:#64748b">None</span>'

        intent_html = f"""
        <div style="background:#1e293b; border-radius:10px; padding:16px; line-height:1.8;">
            <div style="color:#94a3b8; font-size:0.85em; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:12px;">Call Intelligence</div>
            <div style="margin:8px 0;"><span style="color:#94a3b8;">📋 Summary: </span><span style="color:#e2e8f0;">{t.call_summary}</span></div>
            <div style="margin:8px 0;"><span style="color:#94a3b8;">🎯 Primary Intent: </span><span style="color:#f97316; font-weight:600;">{t.primary_intent}</span></div>
            {"<div style='margin:8px 0;'><span style='color:#94a3b8;'>↳ Secondary: </span><span style='color:#cbd5e1;'>"+t.secondary_intent+"</span></div>" if t.secondary_intent else ""}
            <div style="margin:8px 0;"><span style="color:#94a3b8;">⚡ Urgency: </span>
                <span style="color:{urgency_color}; font-weight:600;">{t.urgency_level}</span>
            </div>
            {"<div style='margin:8px 0;'><span style='color:#94a3b8;'>🎭 Impersonating: </span><span style='color:#fbbf24; font-weight:600;'>"+t.impersonated_entity+"</span></div>" if t.is_impersonation and t.impersonated_entity else ""}
            <div style="margin:8px 0;"><span style="color:#94a3b8;">🔐 PII Requested: </span>{pii_badges}</div>
            <div style="margin:8px 0;"><span style="color:#94a3b8;">😤 Pressure Tactics: </span>{tactic_badges}</div>
        </div>
        """

        # ── Why flagged ──────────────────────────────────────────────────────
        all_flags = t.flags + a.flags
        flags_html = ""
        if all_flags:
            items = "".join(
                f'<div style="padding:6px 0; border-bottom:1px solid #1e293b; color:#e2e8f0;">⚠️ {f}</div>'
                for f in all_flags
            )
            flags_html = f"""
            <div style="background:#1e293b; border-radius:10px; padding:16px;">
                <div style="color:#94a3b8; font-size:0.85em; text-transform:uppercase; margin-bottom:10px;">Why It's Flagged</div>
                {items}
            </div>
            """
        else:
            flags_html = '<div style="color:#64748b; padding:12px;">No specific flags raised.</div>'

        # ── Audio stats ──────────────────────────────────────────────────────
        audio_html = f"""
        <div style="background:#1e293b; border-radius:10px; padding:16px;">
            <div style="color:#94a3b8; font-size:0.85em; text-transform:uppercase; margin-bottom:10px;">Audio Forensics</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                <div style="background:#0f172a; padding:10px; border-radius:8px; text-align:center;">
                    <div style="color:#94a3b8; font-size:0.75em;">Synthetic Voice</div>
                    <div style="color:#ef4444; font-size:1.4em; font-weight:700;">{a.synthetic_voice_probability*100:.0f}%</div>
                </div>
                <div style="background:#0f172a; padding:10px; border-radius:8px; text-align:center;">
                    <div style="color:#94a3b8; font-size:0.75em;">Unnatural Pauses</div>
                    <div style="color:#f97316; font-size:1.4em; font-weight:700;">{a.unnatural_pause_count}</div>
                </div>
                <div style="background:#0f172a; padding:10px; border-radius:8px; text-align:center;">
                    <div style="color:#94a3b8; font-size:0.75em;">Voice Consistency</div>
                    <div style="color:#6366f1; font-size:1.4em; font-weight:700;">{a.voice_consistency_score:.0f}/100</div>
                </div>
                <div style="background:#0f172a; padding:10px; border-radius:8px; text-align:center;">
                    <div style="color:#94a3b8; font-size:0.75em;">Pitch Variation</div>
                    <div style="color:#22c55e; font-size:1.4em; font-weight:700;">{a.pitch_variation_score:.0f}/100</div>
                </div>
            </div>
        </div>
        """

        transcript_out = t.transcript if t.transcript else "No transcript available (text-only mode)"
        explanation_out = r.final_explanation

        return (
            gr.update(visible=True),
            verdict_html,
            scores_html,
            intent_html,
            flags_html,
            audio_html,
            transcript_out,
            explanation_out,
            gr.update(visible=True),
            gr.update(visible=True),
            "",
        )

    except Exception as e:
        return [gr.update(visible=False)] * 9 + [gr.update(visible=False), f"Error: {str(e)}"]


# ── Gradio UI ─────────────────────────────────────────────────────────────────

with gr.Blocks(
    title="Fake Call Detector",
    theme=gr.themes.Base(primary_hue="orange"),
    css="""
    .gradio-container { background: #0f172a !important; }
    .gr-panel { background: #1e293b !important; }
    footer { display: none !important; }
    """
) as demo:

    gr.HTML("""
    <div style="text-align:center; padding:24px 0 12px;">
        <div style="font-size:2.5em; margin-bottom:4px;">📞🔍</div>
        <h1 style="color:white; margin:0; font-size:2em;">Fake Call Detector</h1>
        <p style="color:#94a3b8; margin:8px 0 0;">
            AI-powered scam call analysis — Audio forensics · Intent classification ·
            Synthetic voice detection · LLM-based NLP
        </p>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Input")
            audio_input = gr.Audio(label="Upload Call Recording", type="filepath")
            gr.Markdown("**or paste transcript directly:**")
            text_input = gr.Textbox(
                label="Call Transcript",
                placeholder="Paste call transcript here if you don't have audio...",
                lines=5,
            )
            analyze_btn = gr.Button("🔍 Analyze Call", variant="primary", size="lg")
            error_out = gr.Markdown(visible=True)

            gr.HTML("""
            <div style="background:#1e293b; border-radius:10px; padding:14px; margin-top:12px; font-size:0.85em; color:#94a3b8;">
                <b style="color:#e2e8f0;">How it works:</b><br/>
                1. Whisper transcribes audio speech-to-text<br/>
                2. librosa extracts acoustic features<br/>
                3. LLM analyzes intent & scam patterns<br/>
                4. Ensemble scorer combines all signals
            </div>
            """)

        with gr.Column(scale=2):
            results_col = gr.Column(visible=False)
            with results_col:
                verdict_html = gr.HTML()
                with gr.Row():
                    with gr.Column():
                        scores_html = gr.HTML()
                        audio_html = gr.HTML()
                    with gr.Column():
                        intent_html = gr.HTML()
                flags_html = gr.HTML()

            transcript_col = gr.Column(visible=False)
            with transcript_col:
                with gr.Accordion("📝 Full Transcript", open=False):
                    transcript_out = gr.Textbox(label="", lines=6, interactive=False)
                with gr.Accordion("💡 Explanation", open=True):
                    explanation_out = gr.Markdown()

    analyze_btn.click(
        fn=analyze_call,
        inputs=[audio_input, text_input],
        outputs=[
            results_col, verdict_html, scores_html, intent_html,
            flags_html, audio_html, transcript_out, explanation_out,
            transcript_col, results_col, error_out,
        ],
    )

    gr.HTML("""
    <div style="text-align:center; padding:16px; color:#475569; font-size:0.8em;">
        Techniques: Whisper ASR · librosa acoustics · MFCC/spectral analysis ·
        Groq LLM intent classification · Ensemble scoring
    </div>
    """)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0")
