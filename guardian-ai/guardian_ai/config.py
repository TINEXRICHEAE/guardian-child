"""Service configuration, read from environment variables or guardian-ai/.env (plan.md §6.2, §19.1)."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent

CAPABILITIES = ('classify', 'classify_url', 'embed', 'extract', 'explain', 'generate')


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(',') if v.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=SERVICE_DIR / '.env', extra='ignore')

    # Backend chains, tried left to right.
    # Dev mode (laptop): gemini. Testbed mode (GPU machine): onnx / qwen.
    classify_backends: str = 'gemini'
    classify_url_backends: str = 'url-onnx'
    embed_backends: str = 'minilm'
    extract_backends: str = 'gemini'
    explain_backends: str = 'gemini'
    generate_backends: str = 'gemini'      # content generation for Django (parent composer, analyst lessons)

    # Cloud switches. ALLOW_CLOUD=false makes every cloud backend unavailable.
    allow_cloud: bool = True
    allow_cloud_images: bool = True      # screenshots cannot be redacted: synthetic test images only

    # Gemini: Flash first, then fallbacks when a model is busy, rate-limited or not found
    gemini_api_key: str = ''
    gemini_models: str = 'gemini-2.5-flash,gemini-2.5-flash-lite,gemini-3-flash-preview'
    gemini_timeout_s: int = 60

    # Local DistilBERT ONNX classifier (GPU machine; runs on CPU)
    classifier_dir: str = '~/models/distilbert-phish'
    classifier_model_id: str = 'masterburator3301/distilbert-spam-phishing-classification-onnx'
    classifier_threshold: float = 0.5

    # URL phishing classifier (pirocheto/phishing-url-detection, ONNX, judges the URL text only)
    url_classifier_dir: str = '~/models/phishing-url'
    url_classifier_model_id: str = 'pirocheto/phishing-url-detection'
    url_classifier_locale: str = 'C.UTF-8'

    # Sentence embeddings for scam-wave grouping
    embed_model_dir: str = '~/models/all-MiniLM-L6-v2'
    embed_model_id: str = 'sentence-transformers/all-MiniLM-L6-v2'
    embed_device: str = 'cpu'

    # Qwen3-VL run directly with transformers (no llama-server). GTX 1060: float16 + sdpa, GPU+CPU offload.
    qwen_hf_dir: str = '~/models/qwen3vl-2b'
    qwen_hf_dtype: str = 'float16'
    qwen_hf_max_gpu_memory: str = '3500MiB'     # the rest of the weights are offloaded to CPU RAM
    qwen_hf_max_cpu_memory: str = '6GiB'
    qwen_hf_max_image_side: int = 896

    # Qwen3-VL behind llama-server (OpenAI-compatible)
    qwen_base_url: str = 'http://localhost:8081/v1'
    qwen_model: str = 'qwen3-vl-2b'
    qwen_timeout_s: int = 120
    qwen_api_key: str = ''          # llama-server --api-key (needed when it listens beyond localhost)

    # Shared secret Django sends as X-Guardian-AI-Key. Empty = no check (laptop dev only).
    guardian_ai_token: str = ''

    max_text_chars: int = 5000
    max_generate_tokens: int = 3000
    max_image_bytes: int = 5 * 1024 * 1024
    max_image_side: int = 1600
    inference_log: str = str(SERVICE_DIR / 'logs' / 'inference.jsonl')

    def chain(self, capability: str) -> list[str]:
        return _csv(getattr(self, f'{capability}_backends'))

    @property
    def gemini_model_list(self) -> list[str]:
        return _csv(self.gemini_models)


@lru_cache
def get_settings() -> Settings:
    return Settings()
