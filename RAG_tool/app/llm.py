"""Gemini LLM client"""
from typing import List
from google import genai
from google.genai import types
from .config import GEMINI_API_KEY, GEMINI_MODEL

SYSTEM_PROMPT = """You are a Senior LTE/5G NR RF Optimization Engineer with deep expertise in 3GPP specifications.

STRICT RULES:
1. Answer ONLY using the provided context chunks. Do NOT use outside knowledge.
2. If the answer is not present in the context, respond exactly:
   "I cannot find this in the supplied specifications."
3. Always cite:
   - TS Number (e.g., TS 36.331)
   - Release (e.g., Release 17)
   - Section (e.g., 5.5.4.4)
   - Page number when available
4. Reproduce formulas, parameters, and timers EXACTLY as they appear in the spec.
5. Be concise, technical, and precise. No marketing language, no fluff.
6. Use Markdown. For formulas use inline code. For multi-step procedures use numbered lists.
7. If the context contains Markdown tables, render them cleanly as Markdown tables in your response.

CONTEXT FORMAT:
Each chunk is provided as:
[CHUNK N] TS xx.xxx | Release xx | Section x.x.x | Page xx
<chunk text>
"""

class GeminiLLM:
    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set. Put it in .env")
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, user_question: str, context_chunks: List[dict]) -> str:
        context_text = self._format_context(context_chunks)
        prompt = f"""User question:
{user_question}

---
Context from 3GPP specifications:
{context_text}
---

Now answer the user's question following ALL the rules in your system instructions.
"""
        response = self.client.models.generate_content(
            model=self.model, contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, temperature=0.1,
                top_p=0.9, max_output_tokens=2048,
            ),
        )
        return response.text

    @staticmethod
    def _format_context(chunks: List[dict]) -> str:
        lines = []
        for i, c in enumerate(chunks, 1):
            lines.append(
                f"[CHUNK {i}] TS {c['ts_number']} | Release {c['release']} | "
                f"Section {c['section']} | Page {c['page']}\n{c['text']}"
            )
        return "\n\n---\n\n".join(lines)