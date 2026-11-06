"""Qwen3-VL behind llama-server's OpenAI-compatible API (Testbed mode, plan.md §4.6, §6.5)."""
import base64

import httpx

from .. import prompts
from .base import Backend, BackendError, BackendUnavailable, parse_json


class QwenBackend(Backend):
    name = 'qwen'
    capabilities = frozenset({'extract', 'explain', 'generate'})

    def __init__(self, settings):
        super().__init__(settings)
        self._client = None

    @property
    def model(self) -> str:
        return self.settings.qwen_model

    def check(self, capability: str) -> None:
        super().check(capability)
        try:
            import openai  # noqa: F401
        except ImportError as e:
            raise BackendUnavailable('openai is not installed') from e

    def probe(self, capability: str) -> None:
        self.check(capability)
        try:
            headers = {'Authorization': f'Bearer {self.settings.qwen_api_key}'} if self.settings.qwen_api_key else {}
            httpx.get(self.settings.qwen_base_url.rstrip('/') + '/models', headers=headers, timeout=3).raise_for_status()
        except httpx.HTTPError as e:
            raise BackendUnavailable(f'llama-server not reachable at {self.settings.qwen_base_url}') from e

    def _chat(self, content: list, max_tokens: int, *, system: str | None = None, as_json: bool = True):
        from openai import OpenAI, OpenAIError

        if self._client is None:
            self._client = OpenAI(base_url=self.settings.qwen_base_url, api_key=self.settings.qwen_api_key or 'none',
                                  timeout=self.settings.qwen_timeout_s)
        try:
            r = self._client.chat.completions.create(
                model=self.settings.qwen_model, temperature=0.1, max_tokens=max_tokens,
                messages=([{'role': 'system', 'content': system}] if system else [])
                + [{'role': 'user', 'content': content}],
            )
        except OpenAIError as e:
            raise BackendError(f'qwen call failed: {type(e).__name__}') from e
        text = r.choices[0].message.content or ''
        return parse_json(text) if as_json else text.strip()

    def extract(self, image: bytes, mime: str) -> dict:
        b64 = base64.b64encode(image).decode()
        return self._chat([{'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}},
                           {'type': 'text', 'text': prompts.EXTRACT}], 512)

    def explain(self, prompt: str) -> dict:
        return self._chat([{'type': 'text', 'text': prompt}], 300)

    def generate(self, prompt: str, *, system: str | None, max_tokens: int) -> str:
        return self._chat([{'type': 'text', 'text': prompt}], max_tokens, system=system, as_json=False)
