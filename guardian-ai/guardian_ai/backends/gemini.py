"""Gemini Flash backend (dev mode) (plan.md §6.2, §6.5)."""
import logging

from .. import prompts
from ..redact import redact
from .base import Backend, BackendError, BackendUnavailable, parse_json

logger = logging.getLogger(__name__)

# Move on to the next model on these; anything else is a real error for this request.
_RETRYABLE = {404, 429, 500, 503}


class GeminiBackend(Backend):
    name = 'gemini'
    cloud = True
    capabilities = frozenset({'classify', 'extract', 'explain', 'generate'})

    def __init__(self, settings):
        super().__init__(settings)
        self._client = None
        self._last_model = ''

    @property
    def model(self) -> str:
        return self._last_model or (self.settings.gemini_model_list or [''])[0]

    def check(self, capability: str) -> None:
        super().check(capability)
        if not self.settings.allow_cloud:
            raise BackendUnavailable('cloud backends disabled (ALLOW_CLOUD=false)')
        if capability == 'extract' and not self.settings.allow_cloud_images:
            raise BackendUnavailable('cloud image processing disabled (ALLOW_CLOUD_IMAGES=false)')
        if not self.settings.gemini_api_key:
            raise BackendUnavailable('GEMINI_API_KEY is not set')
        if not self.settings.gemini_model_list:
            raise BackendUnavailable('GEMINI_MODELS is empty')

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                from google.genai import types
            except ImportError as e:
                raise BackendUnavailable('google-genai is not installed') from e
            self._client = genai.Client(
                api_key=self.settings.gemini_api_key,
                http_options=types.HttpOptions(timeout=self.settings.gemini_timeout_s * 1000),
            )
        return self._client

    def _generate(self, contents, *, as_json=True, system=None, max_tokens=None, temperature=0.1):
        from google.genai import errors, types

        client = self._get_client()
        config = types.GenerateContentConfig(
            response_mime_type='application/json' if as_json else None, temperature=temperature,
            system_instruction=system, max_output_tokens=max_tokens,
        )
        last = None
        for model in self.settings.gemini_model_list:
            try:
                response = client.models.generate_content(model=model, contents=contents, config=config)
            except errors.APIError as e:
                if e.code in _RETRYABLE:
                    logger.warning('Gemini %s from %s, trying next model', e.code, model)
                    last = e
                    continue
                raise BackendError(f'Gemini {e.code} from {model}') from e
            except Exception as e:      # network errors, timeouts
                logger.warning('Gemini call to %s failed: %s', model, e)
                last = e
                continue
            self._last_model = model
            return parse_json(response.text) if as_json else (response.text or '')
        raise BackendError(f'all Gemini models failed (last: {type(last).__name__ if last else "none"})')

    def classify(self, text: str) -> dict:
        data = self._generate(prompts.classify_prompt(redact(text)))
        return {**data, 'scoreKind': 'llm-judgement'}

    def extract(self, image: bytes, mime: str) -> dict:
        from google.genai import types

        return self._generate([types.Part.from_bytes(data=image, mime_type=mime), prompts.EXTRACT])

    def explain(self, prompt: str) -> dict:
        return self._generate(redact(prompt))

    def generate(self, prompt: str, *, system: str | None, max_tokens: int) -> str:
        # Content generation from parent/analyst prompts; redacted in case personal details were typed in
        return self._generate(redact(prompt), as_json=False, system=system, max_tokens=max_tokens, temperature=0.4)
