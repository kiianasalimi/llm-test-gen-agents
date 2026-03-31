"""LLM abstraction layer.

Supported providers (set via LLM_PROVIDER env var):
  - ollama      (default) — local Ollama server
  - groq                  — Groq cloud API (free tier available at groq.com)
  - gemini                — Google Gemini API (free tier at aistudio.google.com)
  - openrouter            — OpenRouter (free models available at openrouter.ai)

Environment variables:
  LLM_PROVIDER        one of: ollama, groq, gemini, openrouter  (default: ollama)

  Ollama:
    OLLAMA_MODEL      model name          (default: qwen2.5-coder:7b)
    OLLAMA_API_URL    server URL          (default: http://localhost:11434/api/generate)

  Groq:
    GROQ_API_KEY      (required)
    GROQ_MODEL        model name          (default: llama-3.3-70b-versatile)

  Gemini:
    GEMINI_API_KEY    (required)
    GEMINI_MODEL      model name          (default: gemini-2.0-flash)

  OpenRouter:
    OPENROUTER_API_KEY   (required)
    OPENROUTER_MODEL     model name       (default: qwen/qwen3-8b:free)
                         Free models end in :free — browse at openrouter.ai/models?q=free
"""

import os
import time
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

_DEFAULT_TIMEOUT_SECONDS = 300
_RATE_LIMIT_RETRIES = 4       # how many times to retry on 429
_RATE_LIMIT_BACKOFF = 15      # seconds to wait between retries


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _call_ollama(
    prompt: str,
    model: Optional[str],
    api_url: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
) -> str:
    if requests is None:
        raise ImportError("requests library is required. Install with: pip install requests")

    model = model or os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    api_url = api_url or os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if max_tokens is not None:
        payload["options"]["num_predict"] = max_tokens

    try:
        response = requests.post(api_url, json=payload, timeout=_DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        result = response.json()
        if "response" in result:
            return result["response"]
        elif "text" in result:
            return result["text"]
        else:
            raise ValueError(f"Unexpected Ollama response format: {list(result.keys())}")
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(
            f"Cannot connect to Ollama at {api_url}. "
            f"Make sure Ollama is running ('ollama serve'). Error: {e}"
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            f"Ollama request timed out after {_DEFAULT_TIMEOUT_SECONDS}s. "
            f"Try a smaller model or set LLM_PROVIDER=openrouter."
        )
    except requests.exceptions.HTTPError as e:
        raise ValueError(f"Ollama returned an error: {e}. Check that model '{model}' is pulled.")


def _call_groq(
    prompt: str,
    model: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
) -> str:
    if requests is None:
        raise ImportError("requests library is required. Install with: pip install requests")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable is not set. "
            "Get a free key at https://console.groq.com"
        )

    model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    api_url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=_DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Groq request timed out after {_DEFAULT_TIMEOUT_SECONDS}s.")
    except requests.exceptions.HTTPError as e:
        raise ValueError(f"Groq API returned an error: {e}. Check your GROQ_API_KEY and model name '{model}'.")


def _call_gemini(
    prompt: str,
    model: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
) -> str:
    if requests is None:
        raise ImportError("requests library is required. Install with: pip install requests")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set. "
            "Get a free key at https://aistudio.google.com"
        )

    model = model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    if max_tokens is not None:
        payload["generationConfig"]["maxOutputTokens"] = max_tokens

    try:
        response = requests.post(api_url, json=payload, timeout=_DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Gemini request timed out after {_DEFAULT_TIMEOUT_SECONDS}s.")
    except requests.exceptions.HTTPError as e:
        raise ValueError(f"Gemini API returned an error: {e}. Check your GEMINI_API_KEY and model name '{model}'.")
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini response format: {e}. Full response: {result}")


def _call_openrouter(
    prompt: str,
    model: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
) -> str:
    if requests is None:
        raise ImportError("requests library is required. Install with: pip install requests")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Get a free key at https://openrouter.ai/keys"
        )

    model = model or os.getenv("OPENROUTER_MODEL", "qwen/qwen3-8b:free")
    api_url = "https://openrouter.ai/api/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=_DEFAULT_TIMEOUT_SECONDS)

            if response.status_code == 429:
                wait = _RATE_LIMIT_BACKOFF * attempt
                print(
                    f"[openrouter] Rate limited (429). "
                    f"Waiting {wait}s before retry {attempt}/{_RATE_LIMIT_RETRIES}..."
                )
                time.sleep(wait)
                continue

            response.raise_for_status()
            result = response.json()

            # OpenRouter wraps errors inside a 200 response in some cases
            if "error" in result:
                raise ValueError(f"OpenRouter error: {result['error']}")

            return result["choices"][0]["message"]["content"]

        except requests.exceptions.Timeout:
            raise TimeoutError(f"OpenRouter request timed out after {_DEFAULT_TIMEOUT_SECONDS}s.")
        except requests.exceptions.HTTPError as e:
            raise ValueError(
                f"OpenRouter API returned an error: {e}. "
                f"Check your OPENROUTER_API_KEY and model name '{model}'. "
                f"Free models end in ':free' — see openrouter.ai/models?q=free"
            )

    raise TimeoutError(
        f"OpenRouter rate limit persisted after {_RATE_LIMIT_RETRIES} retries. "
        f"Wait a minute and try again, or use a different free model."
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def call_local_llm(
    prompt: str,
    model: Optional[str] = None,
    api_url: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Call the configured LLM provider and return the text response.

    The provider is selected via the LLM_PROVIDER environment variable:
      - 'ollama'      (default): local Ollama server
      - 'groq':                  Groq cloud API
      - 'gemini':                Google Gemini API
      - 'openrouter':            OpenRouter (supports free models)

    Args:
        prompt:      The prompt text to send.
        model:       Override the model name (otherwise uses the provider default).
        api_url:     Override the API endpoint (Ollama only).
        temperature: Sampling temperature (0.0–1.0).
        max_tokens:  Maximum tokens to generate (None = provider default).

    Returns:
        The model's text response as a plain string.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower().strip()

    if provider == "ollama":
        return _call_ollama(prompt, model, api_url, temperature, max_tokens)
    elif provider == "groq":
        return _call_groq(prompt, model, temperature, max_tokens)
    elif provider == "gemini":
        return _call_gemini(prompt, model, temperature, max_tokens)
    elif provider == "openrouter":
        return _call_openrouter(prompt, model, temperature, max_tokens)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            f"Must be one of: ollama, groq, gemini, openrouter"
        )
