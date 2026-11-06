# guardian-ai

The inference service behind Guardian's "Is this safe?" checks. Django calls it over HTTP at `GUARDIAN_AI_URL` and
never talks to a model directly for child or parent inputs. Full design: `../plan.md` §6.

| Mode | Where | Backends | Result label |
|---|---|---|---|
| **Testbed** (default) | GPU machine (WSL), `:8000`, reached through an SSH tunnel on laptop `:8100` | DistilBERT ONNX (classify), phishing-URL ONNX (classify-url), all-MiniLM-L6-v2 (embed): all on CPU. Qwen3-VL-2B-Instruct GGUF Q8_0 + mmproj served by llama-server on the GPU (extract / explain / generate). No Gemini | `live` |
| **Dev** | Laptop, `:8000` | Gemini Flash for classify / extract / explain / generate (synthetic data only) | `cloud-dev` |

When every backend for a capability fails, the reply is `unavailable` and Django uses safety rules only
(`rules-only` on the result page).

Switching modes is configuration only: change the backend chains in `.env` on the service, and `GUARDIAN_AI_URL` in
Django.

> **Dev mode sends redacted text and screenshots to Google's Gemini API.** Use synthetic or team test data only.

## Endpoints

| Method & path | Body | Returns (plus `status` and `meta`) |
|---|---|---|
| `GET /health` | - | readiness of every backend per capability, host, GPU, mode |
| `POST /classify` | `{"text": "..."}` (≤ 5,000 chars) | `spamScore`, `label`, `threshold`, `reasons`, `scoreKind`, `calibrated:false` |
| `POST /extract` | multipart `file` (PNG/JPEG/WebP ≤ 5 MB) | `messages[{sender_role,text}]`, `urls`, `phone_numbers_present`, `claimed_organisation`, `language` |
| `POST /explain` | `{"riskLevel", "signals", "audience": "child"\|"parent", "ageBand"}` | `explanation`, `recommendedActions` |
| `POST /classify-url` | `{"urls": [...]}` (≤ 20) | `results[{url, phishingScore, label}]` (URLs are never visited) |
| `POST /embed` | `{"texts": [...]}` (≤ 64) | `vectors`, `dimensions` |
| `POST /generate` | `{"prompt", "system", "maxTokens", "json"}` | `text`, `data` (parsed JSON when `json:true`). Parent/analyst prompts only |

- `status` is `"ok"` or `"unavailable"` (every backend failed). Unavailable is a normal 200 response; Django then
  falls back to rules and "Unable to verify".
- `meta` = `host`, `gpu`, `backend`, `model`, `cloud`, `mode` (`cloud-dev` / `live` / `unable_to_verify`),
  `latencyMs`, `attempts`.
- When `GUARDIAN_AI_TOKEN` is set, every endpoint except `/health` needs the header `X-Guardian-AI-Key`.
- The service **never decides risk**. `/classify` is one signal for Django's deterministic fusion.
- Images are validated, re-encoded (EXIF dropped, max side 1600 px) and never written to disk.
- Every call appends one content-free line (endpoint, backend, host, GPU, latency, input SHA-256) to
  `logs/inference.jsonl`, which serves as Testbed evidence.

## Dev mode (laptop)

```bash
cd guardian-ai
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # switch to the "Dev mode" chains (gemini), ALLOW_CLOUD=true, set GEMINI_API_KEY
.venv/bin/uvicorn guardian_ai.main:app --port 8000 --reload

curl -s localhost:8000/health
curl -s -X POST localhost:8000/classify -H 'Content-Type: application/json' \
  -d '{"text":"Congratulations! You won UGX 500,000. Send your Mobile Money PIN to claim."}'
curl -s -X POST localhost:8000/extract -F file=@../docs/samples/synthetic_scam_screenshot.png
curl -s -X POST localhost:8000/explain -H 'Content-Type: application/json' \
  -d '{"riskLevel":"high","signals":["Asks for a PIN","Unexpected prize"],"audience":"child","ageBand":"11-13"}'

.venv/bin/python -m pytest -q   # no network; uses fake backends
```

## Testbed mode (GPU machine)

Deployed on the Testbed GPU machine (Windows with WSL Ubuntu 24.04, GTX 1060 6 GB). Docker has no GPU access
there, so Qwen runs in the Hugging Face **Llama** Windows app's `llama.exe serve` (Vulkan) on Windows port 8081,
protected with an API key. guardian-ai runs in WSL and reaches it through the Windows host IP. Details:
`../plan.md` §4 and §4.6.

One-time setup, inside WSL:

```bash
bash ~/models/download.sh                       # ONNX + MiniLM models into ~/models (re-runnable)
python3 -m venv ~/venv
echo /opt/hackathon/venv/lib/python3.12/site-packages > ~/venv/lib/python3.12/site-packages/shared.pth
~/venv/bin/pip install onnxruntime onnx pydantic-settings
cp .env.example .env                            # Testbed block is the default
                                                # set GUARDIAN_AI_TOKEN, QWEN_BASE_URL (Windows host IP) and QWEN_API_KEY
```

Every start:

```bash
# from the laptop (full path: ~ is not expanded when the command passes through Windows)
ssh -i ~/.ssh/<key> <user>@<gpu-host> "wsl -d Ubuntu-24.04 -- bash /home/<user>/guardian-ai/scripts/start_all.sh"
#   starts Qwen (tmux "qwen", :8081) and guardian-ai (tmux "ai", :8000) if not running; add "restart" to restart both

bash guardian-ai/scripts/tunnel.sh              # laptop :8100 -> GPU 127.0.0.1:8000, reconnects by itself
# Django pita/.env: GUARDIAN_AI_URL=http://localhost:8100 and the same GUARDIAN_AI_TOKEN
python manage.py ai_health
```

Use `127.0.0.1`, not `localhost`, in tunnels: WSL forwards IPv4 only. `start_testbed.sh` restarts guardian-ai
alone. `start_llama_server.sh` is for a Linux llama-server build.

Measured (warm): classify ≈ 0.3 s, classify-url ≈ 15 ms, embed ≈ 0.2 s, explain ≈ 6 s, extract ≈ 23 s,
generate ≈ 18 tokens/s for short text (slower for long outputs). See `../docs/testbed-evidence/`.
