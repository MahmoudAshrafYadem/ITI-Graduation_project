"""Orchestrates the RAG pipeline with profiling"""
import time
from typing import Optional
from .embeddings import Embedder
from .retriever import VectorStore
from .llm import OpenRouterLLM
from .reranker import Reranker
from .config import TOP_K, FETCH_MULTIPLIER, DEBUG_MODE
from . import profiler

UNWANTED_KEYWORDS = [
    "cr history", "correction history", "release history",
    "annex", "appendix", "revision table", "change history",
    "asn.1 grammar", "asn1 grammar",
    "editorial correction", "editorial change",
    "miscellaneous rapporteur",
]

class TelecomRAG:
    def __init__(self):
        profiler.stage_start("Init Embedder")
        self.embedder = Embedder()
        profiler.stage_end("Init Embedder")

        profiler.stage_start("Init Qdrant")
        self.store = VectorStore()
        profiler.stage_end("Init Qdrant")

        profiler.stage_start("Init OpenRouter LLM")
        self.llm = OpenRouterLLM()
        profiler.stage_end("Init OpenRouter LLM")

        profiler.stage_start("Init Reranker")
        self.reranker = Reranker()
        profiler.stage_end("Init Reranker")

    def _filter_chunks(self, chunks: list) -> list:
        profiler.stage_start("Filter Chunks")
        original = len(chunks)
        filtered = []
        for c in chunks:
            text_lower = c.get("text", "").lower()
            section = c.get("section", "")
            skip = False
            for keyword in UNWANTED_KEYWORDS:
                if keyword in text_lower and "event" not in text_lower[:200]:
                    skip = True
                    break
            if skip:
                continue
            if section.startswith("Annex") or section.startswith("Appendix"):
                if "event" not in text_lower[:200] and "formula" not in text_lower[:200]:
                    continue
            filtered.append(c)
        profiler.stage_end("Filter Chunks", {"original": original, "filtered": len(filtered), "removed": original - len(filtered)})
        return filtered

    def _apply_context_budget(self, chunks: list, max_tokens: int = 3000) -> list:
        profiler.stage_start("Context Budget")
        total_tokens = 0
        selected = []
        for c in chunks:
            chunk_tokens = c.get("rerank_score", 0)
            text_tokens = len(c.get("text", "")) // 4
            if total_tokens + text_tokens > max_tokens and selected:
                break
            total_tokens += text_tokens
            selected.append(c)
        profiler.stage_end("Context Budget", {"selected": len(selected), "total_tokens": total_tokens})
        return selected

    def ask(self, question: str, top_k: int = TOP_K, ts_filter: Optional[str] = None, release_filter: Optional[str] = None, history: Optional[list] = None) -> dict:
        profiler.pipeline_start()

        profiler.stage_start("Embedding Query")
        query_vec = self.embedder.encode_query(question)
        profiler.stage_end("Embedding Query")

        profiler.stage_start("Qdrant Retrieval")
        fetch_k = top_k * FETCH_MULTIPLIER
        hits = self.store.search(
            query_vector=query_vec, top_k=fetch_k,
            ts_filter=ts_filter, release_filter=release_filter,
            query_text=question,
        )
        profiler.stage_end("Qdrant Retrieval", {"fetched": len(hits)})

        profiler.stage_start("Metadata Boost")
        boosted_hits = self.store.boost_by_section_title(hits, question)
        profiler.stage_end("Metadata Boost")

        if not boosted_hits:
            profiler.stage_end("Total Pipeline")
            if DEBUG_MODE:
                print(profiler.pipeline_report())
            return {
                "answer": "I cannot find this in the supplied specifications.",
                "references": [], "chunks": [],
                "metrics": {},
            }

        retrieved_chunks = [h.payload for h in boosted_hits]
        total_retrieved = len(retrieved_chunks)

        profiler.stage_start("Deduplicate")
        deduped_hits = self.store.remove_duplicates(hits)
        deduped_chunks = [h.payload for h in deduped_hits]
        profiler.stage_end("Deduplicate", {"input": total_retrieved, "output": len(deduped_chunks)})

        profiler.stage_start("Filter Context")
        filtered_chunks = self._filter_chunks(deduped_chunks)
        profiler.stage_end("Filter Context")

        profiler.stage_start("Reranking")
        reranked_chunks = self.reranker.rerank(question, filtered_chunks, top_k=top_k)
        profiler.stage_end("Reranking", {"returned": len(reranked_chunks)})

        profiler.stage_start("Context Budget")
        budgeted_chunks = self._apply_context_budget(reranked_chunks, max_tokens=3000)
        profiler.stage_end("Context Budget")

        references = []
        for c in budgeted_chunks:
            references.append({
                "ts": c["ts_number"], "release": c["release"], "section": c["section"],
                "page": c["page"], "score": c.get("rerank_score", 0.0),
            })

        profiler.stage_start("LLM Generate")
        answer = self.llm.generate(question, budgeted_chunks, history=history)
        profiler.stage_end("LLM Generate")

        profiler.stage_end("Total Pipeline")

        if DEBUG_MODE:
            print(profiler.pipeline_report())

        stats = profiler.prompt_stats(budgeted_chunks)
        metrics = {
            "total_retrieved": total_retrieved,
            "after_dedup": len(deduped_chunks),
            "after_filter": len(filtered_chunks),
            "after_rerank": len(reranked_chunks),
            "final_chunks": len(budgeted_chunks),
            **stats,
        }

        return {
            "answer": answer, "references": references,
            "chunks": [
                {
                    "chunk_id": c["chunk_id"], "section": c["section"],
                    "preview": c["text"][:200] + ("..." if len(c["text"]) > 200 else ""),
                } for c in budgeted_chunks
            ],
            "metrics": metrics,
        }
