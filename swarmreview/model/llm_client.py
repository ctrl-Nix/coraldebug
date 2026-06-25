"""
llm_client.py

Single entry point every agent uses to talk to a model.
Default path: local model via Ollama (no API key, no network call).
Fallback path: Groq cloud API, only if local is unavailable or explicitly forced.

This file is intentionally the FIRST thing built in this project, not the last.
The local-first constraint should shape how prompts are written (shorter context,
fewer tokens, no assumption of a huge context window) rather than being bolted on.
"""

import os
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama3-70b-8192")


@dataclass
class LLMResponse:
    text: str
    source: str          # "local" or "cloud"
    model: str
    latency_s: float


class LLMClient:
    def __init__(self, prefer_local: bool = True):
        self.prefer_local = prefer_local

    # ---- public API -----------------------------------------------------

    def complete(self, system: str, prompt: str, force: Optional[str] = None) -> LLMResponse:
        """
        force: None (auto), "local", or "cloud" -- lets you pin an agent to
        a specific backend for testing/benchmarking.
        """
        if force == "cloud":
            return self._call_groq(system, prompt)
        if force == "local":
            return self._call_ollama(system, prompt)

        if self.prefer_local:
            try:
                return self._call_ollama(system, prompt)
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if GROQ_API_KEY:
                    return self._call_groq(system, prompt)
                raise RuntimeError(
                    "Local Ollama unreachable and no GROQ_API_KEY set for fallback."
                )
        else:
            return self._call_groq(system, prompt)

    # ---- backends ---------------------------------------------------------

    def _call_ollama(self, system: str, prompt: str) -> LLMResponse:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latency = time.time() - t0
        text = data.get("message", {}).get("content", "")
        return LLMResponse(text=text, source="local", model=OLLAMA_MODEL, latency_s=latency)

    def _call_groq(self, system: str, prompt: str) -> LLMResponse:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set.")
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latency = time.time() - t0
        text = data["choices"][0]["message"]["content"]
        return LLMResponse(text=text, source="cloud", model=GROQ_MODEL, latency_s=latency)
