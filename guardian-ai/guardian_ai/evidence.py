"""Host/GPU facts attached to every response, and the content-free inference log (Testbed evidence, plan.md §6.7)."""
import json
import logging
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_GPU_TTL_S = 30
_gpu_cache: tuple[float, str] = (0.0, '')


def host() -> str:
    return socket.gethostname()


def gpu() -> str:
    """Name and memory of the first GPU via nvidia-smi, cached; 'none' when there is no NVIDIA GPU."""
    global _gpu_cache
    now = time.monotonic()
    if _gpu_cache[1] and now - _gpu_cache[0] < _GPU_TTL_S:
        return _gpu_cache[1]
    try:
        out = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.used,memory.total', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip().splitlines()
        value = out[0] if out else 'none'
    except (OSError, subprocess.SubprocessError):
        value = 'none'
    _gpu_cache = (now, value)
    return value


def log_inference(path: str, record: dict) -> None:
    """Append one JSON line. Never raises: evidence logging must not break inference."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        record = {'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), **record}
        with p.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
    except OSError as e:
        logger.warning('could not write inference log: %s', e)
