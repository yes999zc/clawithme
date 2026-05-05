"""Phase 4 — Multi-signal identity association.

signals/avatar.py      — perceptual hash, Hamming distance, compare_avatars
signals/correlation.py — Union-Find clustering engine
signals/extraction.py  — email/phone regex extraction from text
signals/llm_verifier.py — DeepSeek/OpenAI identity verification (Phase 6)

Limitation: llm_verifier requires DEEPSEEK_API_KEY env var;
            falls back to rule-engine results when unavailable.
"""
