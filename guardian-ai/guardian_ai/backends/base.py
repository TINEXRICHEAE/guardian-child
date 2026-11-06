"""Backend contract (plan.md §6.5). Each backend implements the capabilities it supports and raises on failure."""
import json
import re

from ..config import Settings


class BackendError(Exception):
    """The backend was tried and failed (network, quota, bad output)."""


class BackendUnavailable(BackendError):
    """The backend cannot run here (not installed, not configured, cloud disabled)."""


class Backend:
    name = 'base'
    cloud = False
    capabilities: frozenset[str] = frozenset()

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def model(self) -> str:
        return ''

    def check(self, capability: str) -> None:
        """Raise BackendUnavailable if this backend cannot serve `capability`. Must be cheap."""
        if capability not in self.capabilities:
            raise BackendUnavailable(f'{self.name} does not support {capability}')

    def probe(self, capability: str) -> None:
        """Deeper readiness check for /health (may touch the network). Defaults to check()."""
        self.check(capability)

    def classify(self, text: str) -> dict:
        """Return {"spamScore": float, "reasons": [...], "scoreKind": str}."""
        raise BackendUnavailable(f'{self.name} cannot classify')

    def classify_urls(self, urls: list[str]) -> list[dict]:
        """Return [{"url": str, "phishingScore": float}] in input order."""
        raise BackendUnavailable(f'{self.name} cannot classify URLs')

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one normalised vector per text."""
        raise BackendUnavailable(f'{self.name} cannot embed')

    def generate(self, prompt: str, *, system: str | None, max_tokens: int) -> str:
        """Return generated text."""
        raise BackendUnavailable(f'{self.name} cannot generate')

    def extract(self, image: bytes, mime: str) -> dict:
        """Return the EXTRACT prompt's JSON shape."""
        raise BackendUnavailable(f'{self.name} cannot extract')

    def explain(self, prompt: str) -> dict:
        """Return {"explanation": str, "recommendedActions": [...]}."""
        raise BackendUnavailable(f'{self.name} cannot explain')


_FENCE = re.compile(r'^```[a-zA-Z]*\s*|\s*```$')


def parse_json(text: str | None) -> dict:
    """Parse a model's JSON reply, tolerating markdown fences and text around the object."""
    cleaned = _FENCE.sub('', (text or '').strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        start, end = cleaned.find('{'), cleaned.rfind('}')
        try:
            data = json.loads(cleaned[start:end + 1]) if 0 <= start < end else None
        except json.JSONDecodeError:
            data = None
        if data is None:
            raise BackendError(f'model returned invalid JSON: {e.msg}') from e
    if not isinstance(data, dict):
        raise BackendError('model returned JSON that is not an object')
    return data
