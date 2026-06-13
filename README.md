---
title: Fake Call Detector
emoji: 📞
colorFrom: red
colorTo: orange
sdk: gradio
sdk_version: "4.44.0"
app_file: app.py
pinned: false
---

# Fake Call Detector 📞🔍

An AI-powered scam call detection system combining **audio forensics**, **speech-to-text**, and **LLM-based NLP** to identify fraudulent calls with detailed analysis reports.

**Live Demo:** [huggingface.co/spaces/Riyanshc/fake-call-detector](https://huggingface.co/spaces/Riyanshc/fake-call-detector)

---

## What It Detects

- 🏦 Bank/OTP scams
- 🏆 Lottery/prize scams  
- 👮 Police/legal threat calls
- 🤖 AI-generated / TTS voice calls
- 💻 Technical support scams
- 🎭 Impersonation calls

---

## Output

Every analyzed call produces a full report:

```
VERDICT: 🚨 FAKE  (87% confidence)

📋 Call Summary
   Caller claims to be from SBI bank, urgently requesting OTP 
   and account details, threatening account suspension.

🎯 Intent: Financial Fraud (OTP/Account theft)
⚡ Urgency: CRITICAL
🤖 Voice: Likely AI/TTS Generated (73% synthetic)

📊 Score Breakdown
   Text Analysis:    91% suspicious
   Audio Analysis:   78% suspicious  
   AI Voice Score:   73% synthetic

🔍 Why Flagged
   ⚠️ Multiple urgency/threat phrases detected
   ⚠️ Sensitive data requested: otp, account number
   ⚠️ Impersonating: SBI bank
   ⚠️ Low pitch variation (TTS pattern)
```

---

## Architecture

```
Audio Input
    ↓
Whisper (speech-to-text)
    ↓
Dual-Track Analysis
┌───────────────────┬──────────────────────┐
│   Audio Track     │      Text Track       │
│   (librosa)       │    (Groq LLM + NLP)   │
│                   │                       │
│ MFCC features     │ Intent classification  │
│ Spectral analysis │ Scam keyword detection │
│ Pause patterns    │ PII request detection  │
│ Pitch variation   │ Urgency scoring        │
│ Voice consistency │ Impersonation detect   │
│ Synthetic voice   │ Pressure tactic NER    │
└───────────────────┴──────────────────────┘
    ↓
Ensemble Scorer (text 50% + audio 30% + LLM 20%)
    ↓
Verdict + Confidence + Full Report
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Speech-to-Text | OpenAI Whisper |
| Audio Analysis | librosa (MFCC, spectral, pitch) |
| NLP / Intent | Groq LLM (llama-3.1-8b-instant) |
| Rule-based NLP | regex + keyword patterns |
| UI | Gradio |
| Deployment | HuggingFace Spaces |

---

## Setup

```bash
git clone https://github.com/Riiyansh/fake-call-detector
cd fake-call-detector
pip install -r requirements.txt
cp .env.example .env  # add GROQ_API_KEY
streamlit run app.py
```

---

## Supported Input

- **Audio files**: `.wav`, `.mp3`, `.m4a`, `.ogg`
- **Text only**: paste transcript directly (no audio required)

---

## License

MIT
