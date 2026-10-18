"""Baseline: classic 'retrieve once, answer once' RAG - the thing most demos build.

It uses the SAME retriever and the SAME model as the agent. The only difference
is the architecture, so the comparison is fair: any gap in quality comes from
the agent loop, the tools and the diary, not from a bigger model.
"""

from __future__ import annotations

import time

from agent import llm
from agent.prompts import BASELINE_SYSTEM, TASK
from rag.retriever import get_retriever

TOP_K = 8


def run_baseline(case_id: str, question: str = TASK, effort: str = llm.DEFAULT_EFFORT) -> dict:
    t0 = time.time()
    hits = get_retriever().search(question, k=TOP_K, case_id=case_id)  # one search, user's words, this case only
    context = "\n\n".join(f"[{h['cite']}] ({h['title']})\n{h['text']}" for h in hits)
    usage = llm.Usage()
    resp = llm.create(
        llm.get_client(),
        max_tokens=8000,
        system=BASELINE_SYSTEM,
        messages=[{"role": "user", "content": f"Excerpts:\n\n{context}\n\nQuestion about case {case_id}: {question}"}],
        output_config={"effort": effort},
    )
    usage.add(resp.usage)
    answer = "".join(b.text for b in resp.content if b.type == "text")
    return {"question": question, "retrieved": hits, "answer": answer,
            "stats": {**usage.as_dict(), "seconds": round(time.time() - t0, 1)}}
