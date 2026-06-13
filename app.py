import gradio as gr
from text_analyzer import analyze_text
from config import GROQ_API_KEY

VERDICT_COLORS = {"FAKE": "#ef4444", "SUSPICIOUS": "#f97316", "REAL": "#22c55e"}
URGENCY_COLORS = {"LOW": "#22c55e", "MEDIUM": "#eab308", "HIGH": "#f97316", "CRITICAL": "#ef4444"}

EXAMPLES = [
    "Hello, this is a call from SBI Bank. Your account has been suspended due to suspicious activity. To reactivate it, please provide your OTP and account number immediately or your account will be permanently blocked within 24 hours.",
    "Congratulations! You have won a lottery prize of 50 lakh rupees. To claim your prize, please share your bank account details and pay a processing fee of 5000 rupees.",
    "This is Officer Sharma from the Cyber Crime Department. We have detected illegal transactions from your number. You will be arrested within 2 hours unless you transfer money to this safe account immediately.",
    "Hi, I'm calling from Amazon customer service regarding your recent order. There seems to be an issue with your delivery address. Can you please confirm your card details to process the reshipment?",
    "Hello, I wanted to confirm our meeting tomorrow at 3pm regarding the project proposal. Please let me know if the time works for you.",
]


def bar(val, color="#6366f1"):
    return (
        f'<div style="background:#0f172a;border-radius:6px;height:8px;width:100%;margin:3px 0;">'
        f'<div style="background:{color};width:{min(val,100):.0f}%;height:100%;border-radius:6px;"></div></div>'
    )


def analyze(transcript):
    if not transcript.strip():
        return "", "", "", ""

    transcript = "".join(c for c in transcript if ord(c) < 128).strip()

    try:
        t = analyze_text(transcript)

        # Ensemble score
        llm_weight = {"FAKE": 90, "SUSPICIOUS": 55, "REAL": 15}.get(t.llm_verdict, 50)
        score = min(100.0, t.text_suspicion_score * 0.7 + llm_weight * 0.3)
        verdict = "FAKE" if score >= 70 else "SUSPICIOUS" if score >= 45 else "REAL"
        color = VERDICT_COLORS.get(verdict, "#94a3b8")
        urgency_color = URGENCY_COLORS.get(t.urgency_level, "#94a3b8")
        verdict_icon = {"FAKE": "🚨", "SUSPICIOUS": "⚠️", "REAL": "✅"}.get(verdict, "❓")

        # Verdict + scores
        verdict_html = f"""
        <div style="background:{color}22;border:2px solid {color};border-radius:12px;padding:20px;text-align:center;">
            <div style="font-size:2.5em;">{verdict_icon}</div>
            <div style="font-size:1.8em;font-weight:700;color:{color};">{verdict}</div>
            <div style="color:#e2e8f0;margin-top:4px;">{score:.0f}% confidence</div>
        </div>
        <div style="background:#1e293b;border-radius:10px;padding:16px;margin-top:10px;">
            <div style="color:#94a3b8;font-size:0.8em;text-transform:uppercase;margin-bottom:8px;">Score Breakdown</div>
            <div style="color:#e2e8f0;font-size:0.9em;margin:5px 0;">📝 Text Analysis: <b>{t.text_suspicion_score:.0f}%</b></div>
            {bar(t.text_suspicion_score, "#6366f1")}
            <div style="color:#e2e8f0;font-size:0.9em;margin:5px 0;">🧠 LLM Analysis: <b>{llm_weight}%</b></div>
            {bar(llm_weight, "#f97316")}
            <div style="color:#e2e8f0;font-size:0.9em;margin:5px 0;">🎯 Final Score: <b>{score:.0f}%</b></div>
            {bar(score, color)}
        </div>
        """

        # Intent
        pii = " ".join(
            f'<span style="background:#7f1d1d;color:#fca5a5;padding:2px 7px;border-radius:8px;font-size:0.8em;">{p}</span>'
            for p in t.pii_requested
        ) or '<span style="color:#64748b">None</span>'

        tactics = " ".join(
            f'<span style="background:#431407;color:#fed7aa;padding:2px 7px;border-radius:8px;font-size:0.8em;">{tc}</span>'
            for tc in t.pressure_tactics[:4]
        ) or '<span style="color:#64748b">None</span>'

        intent_html = f"""
        <div style="background:#1e293b;border-radius:10px;padding:16px;line-height:2;">
            <div style="color:#94a3b8;font-size:0.8em;text-transform:uppercase;margin-bottom:8px;">Call Intelligence</div>
            <div><span style="color:#94a3b8;">📋 Summary: </span><span style="color:#e2e8f0;">{t.call_summary}</span></div>
            <div><span style="color:#94a3b8;">🎯 Intent: </span><span style="color:#f97316;font-weight:600;">{t.primary_intent}</span></div>
            {"<div><span style='color:#94a3b8;'>↳ Secondary: </span><span style='color:#cbd5e1;'>"+t.secondary_intent+"</span></div>" if t.secondary_intent else ""}
            <div><span style="color:#94a3b8;">⚡ Urgency: </span><span style="color:{urgency_color};font-weight:600;">{t.urgency_level}</span></div>
            {"<div><span style='color:#94a3b8;'>🎭 Impersonating: </span><span style='color:#fbbf24;font-weight:600;'>"+t.impersonated_entity+"</span></div>" if t.is_impersonation and t.impersonated_entity else ""}
            <div><span style="color:#94a3b8;">🔐 PII Requested: </span>{pii}</div>
            <div><span style="color:#94a3b8;">😤 Pressure Tactics: </span>{tactics}</div>
        </div>
        """

        # Flags
        flags_items = "".join(
            f'<div style="padding:5px 0;border-bottom:1px solid #0f172a;color:#e2e8f0;">⚠️ {f}</div>'
            for f in t.flags
        ) or '<div style="color:#64748b;">No specific flags raised.</div>'

        flags_html = f"""
        <div style="background:#1e293b;border-radius:10px;padding:16px;">
            <div style="color:#94a3b8;font-size:0.8em;text-transform:uppercase;margin-bottom:8px;">Why It's Flagged</div>
            {flags_items}
        </div>
        <div style="background:#1e293b;border-radius:10px;padding:16px;margin-top:10px;">
            <div style="color:#94a3b8;font-size:0.8em;text-transform:uppercase;margin-bottom:6px;">💡 Explanation</div>
            <div style="color:#cbd5e1;line-height:1.7;">{t.llm_explanation or "Analysis complete."}</div>
        </div>
        """

        sentiment_color = {"NEUTRAL": "#94a3b8", "NEGATIVE": "#f97316", "THREATENING": "#ef4444", "FRIENDLY_SUSPICIOUS": "#eab308"}.get(t.sentiment, "#94a3b8")
        meta_html = f"""
        <div style="background:#1e293b;border-radius:10px;padding:16px;">
            <div style="color:#94a3b8;font-size:0.8em;text-transform:uppercase;margin-bottom:8px;">Call Metadata</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <div style="background:#0f172a;padding:10px;border-radius:8px;text-align:center;">
                    <div style="color:#94a3b8;font-size:0.75em;">Sentiment</div>
                    <div style="color:{sentiment_color};font-weight:700;">{t.sentiment}</div>
                </div>
                <div style="background:#0f172a;padding:10px;border-radius:8px;text-align:center;">
                    <div style="color:#94a3b8;font-size:0.75em;">Impersonation</div>
                    <div style="color:{"#ef4444" if t.is_impersonation else "#22c55e"};font-weight:700;">{"YES" if t.is_impersonation else "NO"}</div>
                </div>
                <div style="background:#0f172a;padding:10px;border-radius:8px;text-align:center;">
                    <div style="color:#94a3b8;font-size:0.75em;">PII Requests</div>
                    <div style="color:{"#ef4444" if t.pii_requested else "#22c55e"};font-weight:700;">{len(t.pii_requested)}</div>
                </div>
                <div style="background:#0f172a;padding:10px;border-radius:8px;text-align:center;">
                    <div style="color:#94a3b8;font-size:0.75em;">LLM Verdict</div>
                    <div style="color:{VERDICT_COLORS.get(t.llm_verdict,"#94a3b8")};font-weight:700;">{t.llm_verdict}</div>
                </div>
            </div>
        </div>
        """

        return verdict_html, intent_html, flags_html, meta_html

    except Exception as e:
        err = f'<div style="color:#ef4444;padding:12px;">Error: {str(e)}</div>'
        return err, "", "", ""


with gr.Blocks(
    title="Fake Call Detector",
    theme=gr.themes.Monochrome(),
    css=".gradio-container{background:#0f172a!important;} footer{display:none!important;}"
) as demo:

    gr.Markdown("""
    # 📞🔍 Fake Call Detector
    AI-powered scam call analysis — paste any call transcript to detect fraud intent, PII requests, impersonation, and urgency patterns using LLM + NLP.
    """)

    with gr.Row():
        with gr.Column(scale=1):
            transcript_input = gr.Textbox(
                label="Call Transcript",
                placeholder="Paste the call transcript here...",
                lines=8,
            )
            analyze_btn = gr.Button("🔍 Analyze Call", variant="primary", size="lg")
            gr.Examples(examples=EXAMPLES, inputs=transcript_input, label="Example calls — click to load")

        with gr.Column(scale=2):
            verdict_out = gr.HTML()
            with gr.Row():
                intent_out = gr.HTML()
                meta_out = gr.HTML()
            flags_out = gr.HTML()

    analyze_btn.click(
        fn=analyze,
        inputs=[transcript_input],
        outputs=[verdict_out, intent_out, flags_out, meta_out],
    )

demo.launch(server_name="0.0.0.0")
