from typing import Dict, List, Optional
import time
import logging
import os

logger = logging.getLogger("rag_profiler")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)

_start_times: Dict[str, float] = {}
_completed_stages: Dict[str, Dict] = {}
_pipeline_start: float = 0.0
_pipeline_started: bool = False

def pipeline_start():
    global _pipeline_start, _pipeline_started
    _pipeline_start = time.perf_counter()
    _pipeline_started = True
    _start_times.clear()
    _completed_stages.clear()

def stage_start(name: str):
    _start_times[name] = time.perf_counter()

def stage_end(name: str, metadata: Optional[Dict] = None):
    if name not in _start_times:
        return
    start = _start_times.pop(name)
    elapsed = time.perf_counter() - start
    _completed_stages[name] = {
        "elapsed_s": elapsed,
        "elapsed_ms": elapsed * 1000,
        "metadata": metadata or {},
    }
    detail = ""
    if metadata:
        parts = [f"{k}={v}" for k, v in metadata.items()]
        detail = f" | {', '.join(parts)}"
    logger.info(f"{name} | {elapsed*1000:.1f} ms{detail}")

def get_stage_time(name: str) -> float:
    stage = _completed_stages.get(name)
    if stage is not None:
        return stage["elapsed_s"]
    return 0.0

def get_all_stages() -> Dict[str, float]:
    return {name: stage["elapsed_s"] for name, stage in _completed_stages.items()}

def get_all_stages_ms() -> Dict[str, float]:
    return {name: stage["elapsed_ms"] for name, stage in _completed_stages.items()}

def get_stage_details(name: str) -> Dict:
    stage = _completed_stages.get(name)
    if stage is not None:
        return stage["metadata"]
    return {}

def get_all_details() -> Dict[str, Dict]:
    return {name: stage["metadata"] for name, stage in _completed_stages.items()}

def pipeline_report() -> str:
    lines = [""]
    lines.append("=" * 60)
    lines.append("Pipeline Report")
    lines.append("=" * 60)
    for name, stage in _completed_stages.items():
        meta = stage["metadata"]
        detail = ""
        if meta:
            parts = [f"{k}={v}" for k, v in meta.items()]
            detail = f" ({', '.join(parts)})"
        lines.append(f"  {name:<25s} {stage['elapsed_ms']:>8.1f} ms{detail}")
    total = sum(stage["elapsed_ms"] for stage in _completed_stages.values())
    lines.append(f"  {'Total':<25s} {total:>8.1f} ms")
    lines.append("=" * 60)
    return "\n".join(lines)

def prompt_stats(chunks: List[Dict], system_prompt: str = "", user_prompt: str = "") -> Dict:
    if not chunks:
        return {
            "chunks": 0, "chars": 0, "estimated_tokens": 0,
            "avg_chunk_chars": 0, "max_chunk_chars": 0, "min_chunk_chars": 0,
            "system_prompt_chars": len(system_prompt),
            "user_prompt_chars": len(user_prompt),
            "total_prompt_chars": len(system_prompt) + len(user_prompt),
            "system_prompt_tokens": max(1, len(system_prompt) // 4),
            "user_prompt_tokens": max(1, len(user_prompt) // 4),
            "total_prompt_tokens": max(1, (len(system_prompt) + len(user_prompt)) // 4),
        }
    chunk_sizes = [len(c.get("text", "")) for c in chunks]
    total_chars = sum(chunk_sizes)
    total_tokens = max(1, total_chars // 4)
    sys_chars = len(system_prompt)
    user_chars = len(user_prompt)
    total_prompt_chars = sys_chars + user_chars + total_chars
    total_prompt_tokens = max(1, total_prompt_chars // 4)
    return {
        "chunks": len(chunks),
        "chars": total_chars,
        "estimated_tokens": total_tokens,
        "avg_chunk_chars": sum(chunk_sizes) // len(chunk_sizes),
        "max_chunk_chars": max(chunk_sizes),
        "min_chunk_chars": min(chunk_sizes),
        "system_prompt_chars": sys_chars,
        "user_prompt_chars": user_chars,
        "total_prompt_chars": total_prompt_chars,
        "system_prompt_tokens": max(1, sys_chars // 4),
        "user_prompt_tokens": max(1, user_chars // 4),
        "total_prompt_tokens": total_prompt_tokens,
    }

def resource_stats() -> Dict:
    stats = {}
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        stats["ram_mb"] = round(mem.rss / 1024 / 1024, 1)
        cpu_percent = psutil.cpu_percent(interval=0.1)
        stats["cpu_percent"] = cpu_percent
    except ImportError:
        stats["ram_mb"] = "N/A"
        stats["cpu_percent"] = "N/A"
    return stats