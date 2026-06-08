# 🔒 Security Policy — AI-STEAM-Lab

AI-STEAM-Lab is an educational AI system built for students and educators. Security, student privacy, and responsible AI usage are treated as first-class concerns.

---

## 🛡️ Credential & Secret Management

- ❌ **No secrets are committed to version control**
- ✅ `.env` files are rigorously excluded via `.gitignore`
- ✅ PostgreSQL and Supabase credentials are treated as sensitive environment variables
- ✅ Gemini API keys are injected via secure CI/CD pipelines (GitHub Actions)
- ✅ Redis connection strings are securely managed in our deployment environments (e.g., Render)

## 👁️ Data Privacy & Computer Vision

- ✅ **No Video Storage:** The OpenCV engagement tracker processes web-cam frames in real-time. No video feeds, images, or biometric data of students are ever saved to disk, logged, or transmitted to external servers.
- ✅ **Edge Processing:** Engagement states (e.g., `FOCUSED`, `CONFUSED`, `DISENGAGED`) are calculated locally or temporarily in memory, and only anonymized state labels are passed to the AI agent to adjust pedagogy.
- ✅ **Ephemeral Sessions:** Chat sessions are isolated.

## 🤖 AI Safety & Guardrails

- ✅ **Prompt Injection Mitigations:** The AI Tutor is bounded by strict system prompts to maintain a Socratic, educational tone and refuse inappropriate requests.
- ✅ **Anti-Hallucination Thresholds:** Our Reciprocal Rank Fusion (RRF) hybrid search enforces a strict confidence threshold (`>= 0.72`). If the system is unsure, it will politely decline to answer rather than hallucinating facts to a student.
- ✅ **Read-Only RAG:** The LLM only has read access to the verified STEM Knowledge Graph and pgvector database.

## 🐛 Reporting a Vulnerability

If you discover a security vulnerability or a jailbreak exploit within AI-STEAM-Lab, please do not disclose it publicly.

1. Create a private security advisory on this GitHub repository or email the maintainers directly.
2. Provide a detailed description of the issue and steps to reproduce it.
3. We will acknowledge receipt of your vulnerability report within 48 hours and strive to send you regular updates about our patching progress.
