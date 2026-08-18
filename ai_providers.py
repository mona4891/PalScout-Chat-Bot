"""
ai_providers.py
------------------------------------------------
Handles talking to AI providers with automatic fallback: if one
provider fails or is unavailable, the bot tries the next one, so a
single provider outage or rate limit doesn't take the bot offline.

Order: Groq -> Cerebras -> Mistral -> OpenRouter -> (optional local
Ollama, tried first if enabled, since it's free and has no rate limit)
"""

import time
import logging
from typing import List, Dict, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

# ── Optional SDK imports ──────────────────────────
# Each provider's SDK is optional -- the bot works fine with only
# some of them installed, as long as at least one is available.
try:
    import groq
except ImportError:
    groq = None

try:
    import openai
except ImportError:
    openai = None

try:
    from cerebras.cloud.sdk import Cerebras
except ImportError:
    Cerebras = None

import requests


class AIProviderChain:
    """
    Manages the multi-provider fallback chain. Tracks which providers
    have recently failed so it doesn't keep retrying a broken one on
    every single message.
    """

    def __init__(self, config: dict, local_enabled: bool = False, failure_cooldown_seconds: int = 300):
        self.config = config
        self.local_enabled = local_enabled
        self.failure_cooldown_seconds = failure_cooldown_seconds
        self.provider_fail_time = {}  # provider_name -> timestamp of last failure

        self.chain: List[Tuple[str, Callable, Callable]] = [
            ("groq", self._call_groq, lambda: bool(config.get("GROQ_API_KEY") and groq)),
            ("cerebras", self._call_cerebras, lambda: bool(config.get("CEREBRAS_API_KEY") and Cerebras)),
            ("mistral", self._call_mistral, lambda: bool(config.get("MISTRAL_API_KEY") and openai)),
            ("openrouter", self._call_openrouter, lambda: bool(config.get("OPENROUTER_API_KEY") and openai)),
        ]

    # ── Individual provider calls ────────────────────

    def _call_groq(self, messages: List[Dict]) -> str:
        client = groq.Groq(api_key=self.config.get("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=400,
        )
        return response.choices[0].message.content

    def _call_cerebras(self, messages: List[Dict]) -> str:
        client = Cerebras(api_key=self.config.get("CEREBRAS_API_KEY"))
        response = client.chat.completions.create(
            model="llama3.1-8b",
            messages=messages,
            temperature=0.7,
            max_tokens=400,
        )
        return response.choices[0].message.content

    def _call_mistral(self, messages: List[Dict]) -> str:
        client = openai.OpenAI(
            api_key=self.config.get("MISTRAL_API_KEY"),
            base_url="https://api.mistral.ai/v1",
        )
        response = client.chat.completions.create(
            model="mistral-tiny",
            messages=messages,
            temperature=0.7,
            max_tokens=400,
        )
        return response.choices[0].message.content

    def _call_openrouter(self, messages: List[Dict]) -> str:
        client = openai.OpenAI(
            api_key=self.config.get("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct:free",
            messages=messages,
            temperature=0.7,
            max_tokens=400,
        )
        return response.choices[0].message.content

    def _call_local(self, messages: List[Dict]) -> str:
        """Calls a locally-running Ollama instance, if enabled."""
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": "llama2", "messages": messages},
            timeout=30,
        )
        return response.json().get("message", {}).get("content", "")

    def _is_local_available(self) -> bool:
        try:
            requests.get("http://localhost:11434", timeout=2)
            return True
        except requests.RequestException:
            return False

    # ── Fallback chain logic ─────────────────────────

    def _next_available_provider(self):
        for name, func, is_configured in self.chain:
            if not is_configured():
                continue
            failed_at = self.provider_fail_time.get(name)
            if failed_at is None or (time.time() - failed_at) > self.failure_cooldown_seconds:
                return name, func
        return None, None

    def _mark_failed(self, provider_name: str):
        self.provider_fail_time[provider_name] = time.time()

    def _clear_failed(self, provider_name: str):
        self.provider_fail_time.pop(provider_name, None)

    def ask(self, messages: List[Dict]) -> str:
        """
        Sends a chat completion request through the fallback chain.
        Tries local Ollama first if enabled, then cycles through cloud
        providers in order until one succeeds or all are exhausted.
        """

        def trim(text: str) -> str:
            return text[:397] + "..." if len(text) > 400 else text

        if self.local_enabled and self._is_local_available():
            try:
                return trim(self._call_local(messages))
            except Exception as e:
                logger.info(f"[AI] Local model failed: {e} — falling back to cloud providers...")

        configured_count = len([n for n, _, is_cfg in self.chain if is_cfg()])
        if configured_count == 0:
            return "No AI providers are configured. Please add an API key to config.txt."

        max_attempts = configured_count * 2  # allow a couple retry passes
        attempts = 0

        while attempts < max_attempts:
            provider_name, provider_func = self._next_available_provider()
            if not provider_name:
                break

            try:
                answer = provider_func(messages)
                logger.info(f"[AI] Response from {provider_name.capitalize()}")
                self._clear_failed(provider_name)
                return trim(answer)
            except Exception as e:
                logger.info(f"[AI] {provider_name.capitalize()} failed: {e}")
                self._mark_failed(provider_name)
                attempts += 1

        return "All AI providers are currently unavailable. Try again later."
