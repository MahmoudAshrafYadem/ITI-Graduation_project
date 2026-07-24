"""Ollama LLM client"""
from typing import List
from ollama import Client
from .config import OLLAMA_HOST, OLLAMA_MODEL

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


class OllamaLLM:
    def __init__(
        self,
        host: str = OLLAMA_HOST,
        model: str = OLLAMA_MODEL,
    ):
        if not host:
            raise ValueError("OLLAMA_HOST is not set. Put it in .env")
        if not model:
            raise ValueError("OLLAMA_MODEL is not set. Put it in .env")
        self.client = Client(host=host)
        self.model = model

        try:
            models = self.client.list()
        except Exception as e:
            raise RuntimeError(
                "Cannot connect to Ollama.\n\n"
                f"Host:\n{host}\n\n"
                "Please verify:\n"
                "• Ollama is running\n"
                "• The server is reachable\n\n"
                f"Original error:\n{e}"
            ) from e

        model_names = [m.model for m in models.models]
        if self.model not in model_names:
            raise ValueError(
                f'Model "{self.model}" is not installed.\n\n'
                f"Installed models:\n\n"
                + "\n".join(f"• {name}" for name in model_names)
                + "\n\nRun:\n\n"
                f"ollama pull {self.model}"
            )

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
        with open("last_prompt.txt", "w", encoding="utf-8") as f:
            f.write("SYSTEM PROMPT\n")
            f.write("=" * 80 + "\n")
            f.write(SYSTEM_PROMPT)

            f.write("\n\nUSER PROMPT\n")
            f.write("=" * 80 + "\n")
            f.write(prompt)

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                options={
                    "temperature": 0.1,
                    "top_p": 0.9,
                },
            )
        except Exception as e:
            return (
                "Cannot connect to Ollama.\n\n"
                "Please verify:\n"
                "• Ollama is running\n"
                f"• {self.model} is installed\n"
                "• The Ollama server is listening on\n"
                f"{OLLAMA_HOST}\n\n"
                f"Original error:\n{e}"
            )

        return response.message.content or ""

    @staticmethod
    def _format_context(chunks: List[dict]) -> str:
        lines = []
        for i, c in enumerate(chunks, 1):
            lines.append(
                f"[CHUNK {i}] TS {c['ts_number']} | Release {c['release']} | "
                f"Section {c['section']} | Page {c['page']}\n{c['text']}"
            )
        return "\n\n---\n\n".join(lines)
