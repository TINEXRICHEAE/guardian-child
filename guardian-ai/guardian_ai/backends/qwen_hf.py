"""Qwen3-VL-2B-Instruct run in-process with transformers (Testbed mode without llama-server, plan.md §4.6 option B).

GTX 1060 (Pascal): no bfloat16 and no FlashAttention-2, so float16 + sdpa. Only ~4.5 GB VRAM is free, so
`max_memory` keeps part of the weights in CPU RAM (accelerate offload). One request at a time.
"""
import io
import threading
from pathlib import Path

from .. import prompts
from .base import Backend, BackendError, BackendUnavailable, parse_json


class QwenHFBackend(Backend):
    name = 'qwen-hf'
    capabilities = frozenset({'extract', 'explain', 'generate'})

    def __init__(self, settings):
        super().__init__(settings)
        self._lock = threading.Lock()
        self._model = None
        self._processor = None

    @property
    def model(self) -> str:
        return 'Qwen/Qwen3-VL-2B-Instruct'

    @property
    def _dir(self) -> Path:
        return Path(self.settings.qwen_hf_dir).expanduser()

    def check(self, capability: str) -> None:
        super().check(capability)
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError as e:
            raise BackendUnavailable(f'{e.name} is not installed') from e
        if not (self._dir / 'model.safetensors').exists() or not (self._dir / 'config.json').exists():
            raise BackendUnavailable(f'Qwen3-VL weights not found in {self._dir}')

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        dtype = getattr(torch, self.settings.qwen_hf_dtype)
        max_memory = {'cpu': self.settings.qwen_hf_max_cpu_memory}
        if torch.cuda.is_available():
            max_memory[0] = self.settings.qwen_hf_max_gpu_memory
        self._model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(self._dir), dtype=dtype, attn_implementation='sdpa',
            device_map='auto', max_memory=max_memory,
        ).eval()
        self._processor = AutoProcessor.from_pretrained(str(self._dir))

    def _run(self, content: list, max_new_tokens: int, system: str | None = None) -> str:
        import torch

        messages = [{'role': 'user', 'content': content}]
        if system:
            messages.insert(0, {'role': 'system', 'content': [{'type': 'text', 'text': system}]})
        with self._lock:
            try:
                self._load()
                inputs = self._processor.apply_chat_template(
                    messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors='pt',
                ).to(self._model.device)
                with torch.inference_mode():
                    out = self._model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
                new_tokens = out[:, inputs['input_ids'].shape[1]:]
                return self._processor.batch_decode(new_tokens, skip_special_tokens=True)[0].strip()
            except torch.cuda.OutOfMemoryError as e:
                torch.cuda.empty_cache()
                raise BackendError('GPU out of memory') from e
            except BackendError:
                raise
            except Exception as e:
                raise BackendError(f'qwen-hf failed: {type(e).__name__}: {e}') from e

    def extract(self, image: bytes, mime: str) -> dict:
        from PIL import Image

        img = Image.open(io.BytesIO(image)).convert('RGB')
        img.thumbnail((self.settings.qwen_hf_max_image_side, self.settings.qwen_hf_max_image_side))
        return parse_json(self._run([{'type': 'image', 'image': img}, {'type': 'text', 'text': prompts.EXTRACT}], 512))

    def explain(self, prompt: str) -> dict:
        return parse_json(self._run([{'type': 'text', 'text': prompt}], 300))

    def generate(self, prompt: str, *, system: str | None, max_tokens: int) -> str:
        return self._run([{'type': 'text', 'text': prompt}], max_tokens, system=system)
