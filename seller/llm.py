"""Tiny client for any OpenAI-compatible chat endpoint (Ollama, OpenAI, Groq, vLLM...).

Used only for (a) optional friendlier wording in the seller (every rewrite is
truth-checked, see writer.py) and (b) the LLM buyer bots in harness/llm_buyer.py.

    export LLM_BASE_URL=http://localhost:11434/v1   # Ollama
    export LLM_MODEL=llama3.2:latest
    export LLM_API_KEY=ollama                         # any string for Ollama
"""
from __future__ import annotations

import os

import requests


def chat(messages, model=None, base_url=None, api_key=None, temperature=0.7, timeout=60) -> str:
    base_url = (base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")).rstrip("/")
    model = model or os.getenv("LLM_MODEL", "llama3.2:latest")
    api_key = api_key or os.getenv("LLM_API_KEY", "ollama")
    r = requests.post(f"{base_url}/chat/completions",
                      headers={"Authorization": f"Bearer {api_key}"},
                      json={"model": model, "messages": messages, "temperature": temperature},
                      timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def rewriter(**kw):
    """Callable for SellerAgent(llm=...): rewrites template text, numbers untouched."""
    def _fn(prompt: str) -> str:
        return chat([{"role": "user", "content": prompt}], temperature=0.3, **kw)
    return _fn


def extractor(**kw):
    """Callable for SellerAgent(llm_parse=...): reads free text into {intent, items, price}.

    The agent only uses it to FILL missing fields, validates every SKU against
    the catalog, and never lets it touch budgets or competitor quotes.
    """
    import json
    import re

    def _fn(text, catalog):
        names = "; ".join(f"{p.sku}={p.name}" for p in catalog.products.values())
        prompt = ("Extract the buyer's message into JSON with keys intent (offer|accept|walk_away|question), "
                  "items (list of {sku, qty}) and price (total number the buyer offers, or null). "
                  f"Use only these SKUs: {names}\nMessage: {text}\nJSON:")
        raw = chat([{"role": "user", "content": prompt}], temperature=0, **kw)
        m = re.search(r"\{.*\}", raw, re.S)
        return json.loads(m.group(0)) if m else {}
    return _fn
