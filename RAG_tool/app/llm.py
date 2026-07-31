"""OpenRouter LLM client using its OpenAI-compatible REST endpoint."""
import json
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from abc import ABC, abstractmethod
from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    OPENROUTER_BASE_URL,
    TEMPERATURE,
    MAX_OUTPUT_TOKENS,
)

SYSTEM_PROMPT = """You are a Senior LTE/5G NR RF Optimization Engineer with deep expertise in 3GPP specifications.

RULES:
1. Answer primarily using the provided context chunks. Use your engineering knowledge to fill gaps and connect concepts when the context alone is incomplete — but always be clear about what comes from the spec vs. your expertise.
2. Only respond with "I cannot find this in the supplied specifications." if the topic is genuinely unrelated to telecom/3GPP and you have no relevant knowledge at all.
3. When context chunks are available, always cite:
   - TS Number (e.g., TS 36.331)
   - Release (e.g., Release 17)
   - Section (e.g., 5.5.4.4)
   - Page number when available
4. Reproduce formulas, parameters, and timers EXACTLY as they appear in the spec when present in context.
5. Give COMPLETE answers — do not cut off mid-explanation. Cover all relevant sub-points fully before concluding.
6. Be technical and precise. No marketing language, no fluff.
7. Use Markdown. For formulas use inline code. For multi-step procedures use numbered lists.
8. If the context contains Markdown tables, render them cleanly as Markdown tables in your response.
9. If the question has multiple parts, answer each part clearly and completely.

CONTEXT FORMAT:
Each chunk is provided as:
[CHUNK N] TS xx.xxx | Release xx | Section x.x.x | Page xx
<chunk text>
"""


class BaseLLM(ABC):
    @abstractmethod
    def generate(self, user_question: str, context_chunks: List[dict]) -> str:
        ...


class OpenRouterLLM(BaseLLM):
    def __init__(
        self,
        api_key: str = OPENROUTER_API_KEY,
        model: str = OPENROUTER_MODEL,
        base_url: str = OPENROUTER_BASE_URL,
        temperature: float = TEMPERATURE,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set. Put it in .env")
        if not model:
            raise ValueError("OPENROUTER_MODEL is not set. Put it in .env")
        self.api_key = api_key
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def generate(self, user_question: str, context_chunks: List[dict], history: List[dict] = None) -> str:
        context_text = self._format_context(context_chunks)
        
        user_prompt_content = f"""User question:
{user_question}

---
Context from 3GPP specifications:
{context_text}
---

Now answer the user's question following ALL the rules in your system instructions.
"""
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            for message in history:
                messages.append({"role": message["role"], "content": message["content"]})
        messages.append({"role": "user", "content": user_prompt_content})

        # For debugging, write the final constructed prompt to a file
        with open("last_prompt.txt", "w", encoding="utf-8") as f:
            f.write("SYSTEM PROMPT\n")
            f.write("=" * 80 + "\n")
            f.write(SYSTEM_PROMPT)
            f.write("\n\nCONVERSATION HISTORY (if any)\n")
            f.write("=" * 80 + "\n")
            if history:
                for msg in history:
                    f.write(f"[{msg['role']}]\n{msg['content']}\n\n")
            f.write("\n\nUSER PROMPT (with context)\n")
            f.write("=" * 80 + "\n")
            f.write(user_prompt_content)

        try:
            request_body = json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_output_tokens,
            }).encode("utf-8")
            request = Request(
                self.endpoint,
                data=request_body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=60) as response:
                response_data = json.load(response)
            return response_data["choices"][0]["message"]["content"] or ""
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            return (
                "Cannot connect to OpenRouter.\n\n"
                "Please verify:\n"
                "• your API key is valid\n"
                f"• model {self.model} is available\n\n"
                f"Original error:\n{e}"
            )

    @staticmethod
    def _format_context(chunks: List[dict]) -> str:
        lines = []
        for i, c in enumerate(chunks, 1):
            lines.append(
                f"[CHUNK {i}] TS {c['ts_number']} | Release {c['release']} | "
                f"Section {c['section']} | Page {c['page']}\n{c['text']}"
            )
        return "\n\n---\n\n".join(lines)
