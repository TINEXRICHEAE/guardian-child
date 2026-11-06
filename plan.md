# Guardian: Child Safety Build Plan

> **What this is:** the working plan for turning Guardian (a Django awareness platform for company staff) into a
> **child-focused scam detection, phishing-practice and threat-intelligence platform** for families in Uganda
> (UCC Testbed Hackathon 2026, Track 4).
>
> **The two headline features, in order:**
> 1. **Check it (detection):** children *and* parents upload artefacts (text, links, screenshots, files, emails) and
>    get an evidence-based risk result.
> 2. **Practice it (phishing simulation):** Guardian sends safe, consented, simulated phishing/spam emails to children.
>    Every link leads to a curated **awareness library** lesson on that email's topic. Parents can create these emails
>    themselves from an existing guideline or a prompt topic. Parents enter children's emails directly, so lessons
>    reach a child **even if they never installed, or later uninstalled, the app**.
>
> Guardian's awareness library and quizzes stay, **with their view tracking, scores and reporting**, now split across
> analyst, parent and child (§10.2).
>
> **Fixed decisions**
> - The product is still called **Guardian**. "Chinga" was only the working name in the proposal and prototype. Do not
>   use it in code, templates, env vars or the UI.
> - The web app stays **full-stack Django with server-rendered templates** (Tailwind via CDN, as today). The Next.js
>   repo (`/home/tinex/UICT/UCC_TEST_BED_HACKATHON`) remains a **prototyping and idea-framing tool**. We borrow
>   screens and flows from it from time to time (see §14). We do not deploy it, call it, or wire it to this backend.
> - Roles are renamed, not added: **employee → child**, **admin → parent**, **superadmin → authorised UCC/admin analyst**.
> - AI runs behind one FastAPI service, `guardian-ai`: **Gemini Flash on the laptop now (dev mode)**, the **GPU
>   machine later (Testbed mode)**. Switching is configuration only (§6).
>
> **Sources this plan draws on**
>
> | Source | Path | How it is used |
> |---|---|---|
> | PRD v2 (proposal) | `/home/tinex/UICT/Chinga_UCC_PRD_v2_Clean.pdf` | Roles, flows, safeguarding rules, MVP scope (P0/P1/P2) |
> | Next.js prototype | `/home/tinex/UICT/UCC_TEST_BED_HACKATHON/` | Screen designs, copy and synthetic fixtures to port into templates |
> | Migration recommendations | `CHINGA_MIGRATION_PLAN.md` (this repo) | **Merged into this file** (Testbed setup, AI service, data model, pipeline, evaluation, safety, declarations). That file is superseded; follow this one |
> | GPU Testbed machine | `ssh -i ~/.ssh/hackathon_ed25519 hackathon@137.63.190.11` | Resources verified 2026-11-05 (§0.1) |
>
> **Code freeze: Friday 6 Nov 2026, 14:00.**

---

## Contents

0. [Context, constraints and resources](#0-context-constraints-and-resources)
1. [Roles and what each one can see](#1-roles-and-what-each-one-can-see)
2. [Decisions log](#2-decisions-log)
3. [Target architecture](#3-target-architecture)
4. [Phase 0: GPU machine (Testbed) setup](#4-phase-0-gpu-machine-testbed-setup)
5. [Phase 1: Foundation (cleanup, roles, families)](#5-phase-1-foundation)
6. [Phase 1b: The guardian-ai inference service (FastAPI)](#6-phase-1b-the-guardian-ai-inference-service-fastapi)
7. [Phase 2: Feature 1, artefact upload and detection](#7-phase-2-feature-1-artefact-upload-and-detection)
8. [Phase 3: Feature 2, phishing/spam simulation](#8-phase-3-feature-2-phishingspam-simulation)
9. [Phase 4: Analyst workspace](#9-phase-4-analyst-workspace)
10. [Phase 5: Awareness library, quizzes and their tracking](#10-phase-5-awareness-library-quizzes-and-their-tracking)
11. [Phase 6: Evaluation and Testbed evidence](#11-phase-6-evaluation-and-testbed-evidence)
12. [Template and URL map](#12-template-and-url-map)
13. [Safety and safeguarding rules](#13-safety-and-safeguarding-rules)
14. [Porting ideas from the Next.js prototype](#14-porting-ideas-from-the-nextjs-prototype)
15. [Priorities, timeline and team split](#15-priorities-timeline-and-team-split)
16. [Acceptance tests and demo script](#16-acceptance-tests)
17. [Submission checklist and declarations](#17-submission-checklist-and-declarations)
18. [Risks and open questions](#18-risks-and-open-questions)
19. [Appendix: env vars, repo layout, commands](#19-appendix)

---

## 0. Context, constraints and resources

### 0.1 Our assignment and the GPU machine (verified 2026-11-05 ~16:30 over SSH)

| Item | Verified value | Consequence |
|---|---|---|
| Group / track | **Group 6**, **Track 4: AI for Child-Focused Cybersecurity and Online Fraud Prevention** | - |
| Access | `ssh -i ~/.ssh/hackathon_ed25519 hackathon@137.63.190.11` (key auth works; key file is `600`) | The migration plan's `137.63.190.232` / "Surface Studio 2" was **wrong or outdated**. Confirm with the organisers that `.11` is Group 6's machine |
| Host | `DESKTOP-3CGBSSB`, Windows (build 10.0.26200). SSH lands in **`cmd.exe`**, not bash | `;` and `\|` are not bash there. Run Linux work through `wsl` (interactive) or `ssh … "wsl -d Ubuntu-24.04 -- bash -s" < script.sh` |
| Linux | **WSL 2, Ubuntu 24.04.5 LTS**, kernel 6.18, systemd on, default user `hackathon` | - |
| CPU / RAM | Intel i7-7820HQ. WSL gets **6 logical CPUs** and **9.7 GiB RAM** (`.wslconfig memory=10GB`) + 3 GiB swap | Run only `guardian-ai` (+ llama-server) there; Django + PostgreSQL stay on the laptop |
| Disk | ~**942 GB free** in WSL | Model downloads are not a problem |
| GPU | **NVIDIA GeForce GTX 1060, 6 GB**, compute capability **6.1 (Pascal)**, driver 582.66 (CUDA 13.0). **~1.5 GB already used** by the Windows desktop | Only **~4.5 GB VRAM** is realistically free. Qwen3-VL-2B fp16 weights (~4.3 GB) will not fit with images. Use a 4-bit GGUF (§4.6) |
| PyTorch | `/opt/hackathon/venv` (Python 3.12.3): **torch 2.14.1+cu126**, arch list includes **`sm_60`**, `cuda.is_available()=True`, **fp16 matmul ran on the GPU** | Pascal works. No bf16 and no FlashAttention-2 on Pascal: use `float16` + `attn_implementation="sdpa"` |
| Preinstalled Python packages | transformers 5.22.1, accelerate 1.15, sentence-transformers 6.2, tokenizers 0.23.3, fastapi 0.162, uvicorn 0.54, openai 3.45, scikit-learn 1.9.1, pillow 12.3, python-multipart, httpx, pydantic 2.14, numpy 2.5.4 | Most of `guardian-ai` already runs |
| **Missing** packages | `onnxruntime`, `google-genai`, `pydantic-settings` | `pip install` into a personal venv (§4.3); PyPI is reachable |
| Tools | `docker` (user is in the docker group), `tmux`, `git`, `gcc`, `curl`; `hf` CLI in the shared venv | **Docker has no NVIDIA runtime** (`runc` only, no container toolkit, needs root to add), so containers cannot use the GPU (verified 18:50) |
| Missing tools | `nvtop`, `cmake`, `nvcc`, `llama-server`, `ollama`, locale `en_US.UTF-8`; **no sudo** | No apt installs and no native llama.cpp CUDA build. Qwen therefore runs in-process with `transformers` (§4.6) |
| Network out | huggingface.co ✅, pypi.org ✅, generativelanguage.googleapis.com ✅ (from WSL) | Models download directly; Gemini usable from the machine too |
| Network in | WSL is NAT'd (`172.21.249.126`); no `netsh portproxy` rules; Windows firewall (public profile) is **off** | The LAN cannot reach WSL ports directly. Use an **SSH tunnel** (§4.7) or ask for a portproxy (needs Windows admin) |
| Already on the machine | `~/chinga-ai/` with empty folders (`evaluation, inference, phishing, scam_messages, scam_waves, urls`) and `inference/health.py`, served by a uvicorn process on **127.0.0.1:18765** (running since ~12:30, not started by us in this session) | **Do not kill it or reuse its port.** Ask the team/organisers who owns it. We deploy to `~/guardian-ai/` on port **8000** |
| Models downloaded | none (only a 3.8 GB pip cache) | Phase 0 downloads them (§4.5) |

### 0.2 Track 4 recommended resources

- Threat intelligence / datasets: **PhishTank**, **URLhaus**, **OpenPhish** (access conditions apply), **UCI ML Repository**.
- Models: **Hugging Face phishing detection models**, **Hugging Face spam detection models**.

### 0.3 Models and AI providers

| Model / provider | Role in Guardian | Where it runs | Notes |
|---|---|---|---|
| **Google Gemini Flash** (`gemini-2.5-flash`, fallbacks `gemini-2.5-flash-lite`, `gemini-3-flash-preview`; the code already lists `gemini-3.1-flash-lite`) | **Now:** every `guardian-ai` capability in dev mode (classify, screenshot extract, explain) **and** content generation (parent composer, analyst pipeline). **Later:** content generation + optional fallback | Cloud, called from the laptop (or from WSL) | Key in `.env` only. Child inputs only on synthetic/team test data while in dev mode (§6.2). Score is an **LLM judgement**, labelled as such |
| [`masterburator3301/distilbert-spam-phishing-classification-onnx`](https://huggingface.co/masterburator3301/distilbert-spam-phishing-classification-onnx) | Text classifier in Testbed mode (`0 = Non-Spam`, `1 = Spam`) | GPU machine, **CPU** via onnxruntime | Files `text_classifier.onnx` (~267 MB), `tokenizer.json`, `tokenizer_config.json`, `vocab.txt`. Base `distilbert-base-uncased`, trained on Kaggle `zefang-liu/phishing-email-dataset` (**English emails**). 97% accuracy is on that dataset only. **No licence stated** → declare it |
| [`Qwen/Qwen3-VL-2B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct) | Vision-language model in Testbed mode: screenshot extraction, sender attribution, child-friendly explanations | GPU machine | Apache-2.0. ~4.26 GB bf16 safetensors. GGUF builds: `ggml-org/Qwen3-VL-2B-Instruct-GGUF` (preferred here), `unsloth/…`, `bartowski/…` |
| `sentence-transformers/all-MiniLM-L6-v2` | Scam-wave grouping (`/embed`) | GPU machine, CPU | Apache-2.0, 90 MB. Verified: scam variants 0.70 similar, scam vs school notice 0.20 |
| [`pirocheto/phishing-url-detection`](https://huggingface.co/pirocheto/phishing-url-detection) | URL phishing score (`/classify-url`) from the URL text only, never visiting it | GPU machine, CPU | MIT, 23.5 MB ONNX (TF-IDF + linear SVM, ROC-AUC 0.987 on its own dataset). Needs `locale=C.UTF-8` set at load (§4.6) |
| ~~`LinksGPT/AI-URL-Expander`~~ | **Rejected** | - | The repo has a README only, **no weights**; and its approach (follow short links to the destination) breaks §13.1 rule 2 |

### 0.4 What the judges score (Readiness Guide §8.1)

| # | Criterion | Weight | How this plan addresses it |
|---|---|---|---|
| 1 | Demonstrated use of the Testbed | 10% | `guardian-ai` in Testbed mode on the GPU machine; every inference logged with host/GPU/latency (§6.7) |
| 2 | Technical quality & completeness | 20% | Working Django app, `unable_to_verify` handling, evaluation page with FP/FN |
| 3 | Relevance to theme/track | 15% | Scam/phishing detection, practice emails, awareness library for children |
| 4 | Safety by design, privacy, ethics | 15% | Redaction, consent + notice, no raw child data to cloud in production, confidential route, human-reviewed content |
| 5 | Innovation & originality | 10% | Artefact detection (text/screenshot/PDF/email) + rules fusion; practice emails that land on topic lessons and work without the app; scam waves |
| 6 | Marketability / commercial viability | 20% | Pitch: families, schools, telcos, UCC; B2G/B2B2C |
| 7 | Demo & pitch quality | 10% | Demo script (§16), honest labels (`live`/`demo`/`cloud-dev`) |

### 0.5 Mandatory deliverables (Readiness Guide §6.5)

Working prototype · source in an accessible repo · brief docs (architecture, setup, **evaluation incl. false
positives and false negatives**, **declarations of third-party assets and AI tools**) · 3-minute demo video · live
demo + pitch. Checklist in §17.

---

## 1. Roles and what each one can see

### 1.1 Role mapping

| Old Guardian role | New role (`Users.role`) | Display name | Purpose |
|---|---|---|---|
| `staff` | `child` | Child | Check content, report incidents, receive practice phishing emails, use the library and quizzes. Needs no app or account to receive practice emails and lessons |
| `admin` | `parent` | Parent / Guardian | Add children (including by email only), check content, see minimal safety alerts, **create and send practice emails** (from a guideline or a prompt topic), see own children's library/quiz progress and practice outcomes |
| `superadmin` | `analyst` | Authorised analyst: **regulators and child-protection bodies** (UCC, Ministry of Gender, Labour and Social Development, Police Child and Family Protection Unit) | The technical side: publish awareness content (the latest scam trends and required topics), review AI output, run programme-wide practice drills, de-identified threat intelligence, scam waves, analytics on families and children, model evaluation, exports |

Notes:
- **The old admin panel goes to the analyst. The parent inherits a family-scoped slice of it.** Guardian's `admin`
  ran the organisation-wide content pipeline. The full `/panel/` (sources → AI transform → approve → campaigns →
  analytics) becomes the **analyst workspace**. The parent gets a **family portal** that reuses the same machinery,
  scoped to their own children: prompt-to-content generation, review and approval, email sending, and analytics for
  their children only.
- **Safeguarding reviewer** (PRD §4) is not a fourth role. It is a Django permission group inside `analyst`
  (`Safeguarding`, holding `view_confidential_reports`). Only analysts in that group can open confidential reports.
- **System operator** (PRD §4) is the Django `createsuperuser` account: `role='analyst'` plus `is_superuser=True`,
  with `/admin/` access. Day-to-day analysts have `is_superuser=False`.
- **Guests** (not logged in) may use "Is this safe?" for text and links only. They get no history, cannot upload files
  and trigger no alerts. This is a P1 item.

### 1.2 Visibility matrix (enforced in views and querysets, not only hidden in templates)

| Data | Child | Parent | Analyst |
|---|---|---|---|
| Child's own check results (full explanation) | ✅ own | ❌. Only a **minimal alert** for high-risk results (threat type, action, time) | Sanitised, de-identified evidence only |
| Parent's own check results | - | ✅ own | Sanitised, de-identified evidence only |
| Uploaded file itself | Deleted after extraction | Deleted after extraction | ❌ never |
| Incident report ("Something happened") | ✅ own | ❌ if confidential. Minimal alert otherwise, only if the child chose to notify | Sanitised summary. Confidential reports only for the `Safeguarding` group |
| Practice-email results | ✅ own (if signed in: history, badges) | ✅ own children, per email (sent / clicked / lesson viewed / quiz score / reported) | Per pseudonymous child + aggregates (groups under 5 suppressed) |
| Library views, quiz attempts and scores | ✅ own progress | ✅ own children (per lesson and quiz, with answers reviewable) | Per pseudonymous child + aggregates, as Guardian's analytics do today |
| Child's email address | - | ✅ own children (entered by the parent) | ❌ never |
| Child identity (nickname, age band) | ✅ own | ✅ own children | ❌. Pseudonymous ID (`C-7F3A`) plus age band and district |
| Child's chat, browsing or other private content | - | ❌ never | ❌ never |

At pairing, or in the welcome notice email for children without the app (§8.1), the child sees a plain-language "What your guardian can and cannot see" screen generated from this table.

---

## 2. Decisions log

This file is the **single plan**. Everything still used from `CHINGA_MIGRATION_PLAN.md` has been merged in here and
renamed for Guardian. That file is superseded: keep it for history or delete it, but do not follow it.

| Earlier recommendation (migration plan / prototype) | Decision in this plan | Why |
|---|---|---|
| Product/app named **Chinga** (`chinga` app, `chinga-ai`, `CHINGA_*` env vars, `seed_chinga`) | **Guardian** everywhere: Django apps `safety` + `phishsim`, service `guardian-ai/`, env `GUARDIAN_*`, command `seed_guardian` | Name stays Guardian |
| Roles `child / guardian / analyst / safeguarding / superadmin` | Three roles, `child / parent / analyst`. Safeguarding is a permission group. Superuser is a flag | Role mapping employee→child, admin→parent, superadmin→analyst |
| Build a DRF JSON API and connect the Next.js frontend | **Django views and templates** for child, parent and analyst. DRF only for `/api/health` and future Telegram/SMS webhooks | Frontend stays Django templates; Next.js is only a prototype (§14) |
| Inference only on the Testbed; Gemini only for admin content | **Two modes behind one FastAPI service** (§6): *dev mode* on the laptop with **Gemini Flash** now, *Testbed mode* on the GPU machine (ONNX classifier + Qwen3-VL) when reachable. Django always calls `GUARDIAN_AI_URL`; switching is a config change | Gemini is available now; GPU access comes later |
| Testbed = Surface Studio 2 at `137.63.190.232` | Verified machine is **`137.63.190.11`** (`DESKTOP-3CGBSSB`, GTX 1060 6 GB) (§0.1) | Probed over SSH on 2026-11-05 |
| PyTorch may lack Pascal kernels | **Verified working**: torch 2.14.1+cu126 includes `sm_60`; an fp16 matmul ran on the GPU (§0.1) | Probe result |
| Model name `Campaign` for suspected scam groupings | **`ScamWave`** | `EmailCampaign` and `SimulationCampaign` already exist |
| `AnalysisRequest.child` only | `Submission` with `submitted_by` (child **or** parent) and `submitter_role` | Feature 1 covers parent uploads |
| Input kinds `text / url / screenshot` | `text / url / image / pdf / email (.eml) / txt` | Feature 1 covers files and emails |
| "Reuse the existing `_rl()` rate limiter in views" | `_rl()` exists only inside `services/transformation.py`. **Move it** to `awarenessapp/services/ratelimit.py` and reuse it everywhere | Verified against the code |
| Drop all click/open tracking | Drop **open** tracking (pixel). Keep **simulation click/report tracking** plus the existing **library view and quiz score tracking**, all disclosed | Feature 2 and the library need learning outcomes |
| Awareness pipeline is admin-only; attempts tied to `user` | Parents also use it, scoped to their family. Tracking keyed on `ChildProfile` | Parent composer; no-app delivery |
| Not covered | **Phishing simulation** (§8) | New requirement |

---

## 3. Target architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Guardian (Django 6, server-rendered templates, PostgreSQL), laptop :8001 │
│                                                                          │
│  Child portal          Parent portal            Analyst workspace        │
│  check · report · 116  family · check ·         overview · threats ·     │
│  practice · progress   practice composer ·      scam waves · orgs ·      │
│  (signed-in only)      alerts · child progress  reports · simulations ·  │
│                                                 library + eval analytics │
│  Public learn/ pages (token, no app needed) ← practice email links       │
│                                                                          │
│  apps: awarenessapp · safety · phishsim                                  │
│  services: extract · redact · url/email checks · rules · fuse ·          │
│            ai_client · llm (content generation) · email_service ·        │
│            ratelimit                                                     │
└──────┬──────────────────────────────┬─────────────────────────┬──────────┘
       │ GUARDIAN_AI_URL              │ llm.py (content gen)    │ SMTP
       ▼                              ▼                         ▼
┌──────────────────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ guardian-ai (FastAPI)         │  │ Gemini Flash     │  │ children's and   │
│ /health /classify /extract    │  │ (now); Qwen via  │  │ parents' inboxes │
│ /explain                      │  │ tunnel (later)   │  └──────────────────┘
│                               │  └──────────────────┘
│ DEV MODE (now): laptop :8000  │
│   all backends = Gemini Flash │
│ TESTBED MODE (later):         │
│   GPU machine 137.63.190.11,  │
│   WSL, GTX 1060 → tunnel :8100│
│   classify = DistilBERT ONNX  │
│   extract/explain = Qwen3-VL  │
│   (llama.cpp Docker :8081)    │
└──────────────────────────────┘
```

Two pipelines share the models, the LLM layer and the analyst workspace:

- **Detection (real time):** upload → extract → redact → signals → classifier → fuse → explain → store minimal evidence →
  group into a scam wave → maybe alert the parent.
- **Practice (scheduled):** guideline or prompt topic → email + linked library lesson + quiz → parent/analyst review →
  consented child's inbox → click → **library lesson on that topic** (no app or login needed) → quiz → progress for the
  child, parent and analyst.

The two meet in one place. When a child uploads a practice email to "Is this safe?", Guardian recognises it, records a
**report**, and congratulates the child (§8.7).

---

## 4. Phase 0: GPU machine (Testbed) setup

The laptop can work without this phase (dev mode, §6.2). Do it as soon as someone is free, because it gates the
10% "Testbed use" score and decides how Qwen is served.

### 4.1 SSH access from the laptop

```bash
chmod 600 ~/.ssh/hackathon_ed25519          # already correct
cat >> ~/.ssh/config <<'EOF'
Host guardian-gpu
    HostName 137.63.190.11
    User hackathon
    IdentityFile ~/.ssh/hackathon_ed25519
    IdentitiesOnly yes
EOF

ssh guardian-gpu          # lands in Windows cmd.exe
wsl                       # enter Ubuntu 24.04; all work happens here
```

Non-interactive commands (cmd.exe does not understand bash pipes):
```bash
ssh guardian-gpu "wsl -d Ubuntu-24.04 -- bash -s" < some_script.sh
```

VS Code: install **Remote - SSH**, connect to `guardian-gpu`, then reopen in WSL; interpreter `~/venv/bin/python`.
Never commit the key or any Testbed password to the repo.

### 4.2 Status checklist

- [x] SSH key login works (2026-11-05)
- [x] WSL Ubuntu 24.04 running, 6 CPUs / 9.7 GiB / 942 GB free
- [x] GPU visible in WSL; torch sees CUDA; fp16 matmul runs (Pascal OK)
- [x] Outbound HF, PyPI, Gemini reachable
- [ ] Confirm with organisers that `137.63.190.11` is Group 6's machine and who runs `~/chinga-ai` on `:18765`
- [ ] Help Desk answers (§4.4): only needed now if we want llama.cpp (§4.6 option A′)
- [x] Personal venv `~/venv` (+ `onnxruntime`, `onnx`, `pydantic-settings`) (§4.3)
- [x] Models downloaded to `~/models` by `~/models/download.sh` in tmux `downloads` (§4.5): `distilbert-phish`, `phishing-url`, `all-MiniLM-L6-v2`, `qwen3vl-2b` (safetensors), `qwen3vl-gguf` (Q8_0 + mmproj, for a future llama.cpp)
- [x] Qwen serving: official GGUF via the Hugging Face Llama app on Windows (Vulkan), `Start Guardian Qwen.bat`; `guardian-ai` in tmux `ai` (§4.6)
- [x] Tunnel from laptop works: `ssh -N -L 8100:127.0.0.1:8000 guardian-gpu`; Django `ai_health` passes through it (§4.7)

### 4.3 Personal virtual environment (allowed by the Workstation Guide §3.5)

Reuse the shared packages and add only what is missing:
```bash
python3 -m venv ~/venv
echo /opt/hackathon/venv/lib/python3.12/site-packages > ~/venv/lib/python3.12/site-packages/shared.pth
source ~/venv/bin/activate
pip install onnxruntime google-genai pydantic-settings "huggingface_hub[cli]"
python -c "import torch, transformers, onnxruntime, fastapi; print('ok', torch.cuda.is_available())"
```

### 4.4 Questions for the Help Desk (the code of conduct forbids unauthorised software installation)

1. May we run the **`ghcr.io/ggml-org/llama.cpp:server-cuda`** Docker image (Docker is installed and our user is in
   the `docker` group)? Native build is impossible: no `cmake`/`nvcc`, no sudo.
2. Can someone with Windows admin add a `netsh interface portproxy` rule for port 8000 → WSL, or should we keep using
   an SSH tunnel?
3. Is `137.63.190.11` ours, and who owns `~/chinga-ai` / the uvicorn process on `127.0.0.1:18765`?

### 4.5 Download the models (on the GPU machine, inside WSL)

```bash
source ~/venv/bin/activate
huggingface-cli download masterburator3301/distilbert-spam-phishing-classification-onnx \
  text_classifier.onnx tokenizer.json tokenizer_config.json vocab.txt --local-dir ~/models/distilbert-phish

# Option A (preferred): GGUF for llama.cpp: check the repo file list for the exact Q4_K_M + mmproj names
huggingface-cli download ggml-org/Qwen3-VL-2B-Instruct-GGUF --local-dir ~/models/qwen3vl-gguf

# Option B only if A is refused: full weights, ~4.3 GB
# huggingface-cli download Qwen/Qwen3-VL-2B-Instruct --local-dir ~/models/qwen3vl-2b
```
Skip `saved_weights_distilbert4.pt`; the ONNX file is all we need.

### 4.6 Serving Qwen3-VL on the GTX 1060

**In use (2026-11-05 20:05): official `Qwen/Qwen3-VL-2B-Instruct-GGUF` (Q8_0 LLM + F16 `mmproj`) served by the
Hugging Face "Llama" Windows app (`llama.exe serve`, llama.cpp build 12110, Vulkan on the GTX 1060).** It handles text
(`/explain`, `/generate`) and uploaded images (`/extract`) through `guardian-ai`'s `qwen` backend.

| Item | Value |
|---|---|
| Start it (GUI) | Double-click **`Start Guardian Qwen.bat`** on the Windows desktop (also `C:\Users\hackathon\guardian-llama\start-qwen.bat`). Keep the window open |
| What it runs | `llama.exe serve -m %USERPROFILE%\models\qwen3vl-2b-gguf\Qwen3VL-2B-Instruct-Q8_0.gguf -mm ...\mmproj-Qwen3VL-2B-Instruct-F16.gguf --host 0.0.0.0 --port 8081 -ngl 99 -c 8192 --alias qwen3-vl-2b --api-key-file ...\api-key.txt` |
| Why `0.0.0.0` + API key | `guardian-ai` runs in WSL (NAT) and reaches Windows at the gateway IP (`ip route show default` → `172.21.240.1`), not `127.0.0.1`. The key (`QWEN_API_KEY` in `~/guardian-ai/.env`) keeps the LAN out |
| `guardian-ai` settings | `EXTRACT/EXPLAIN/GENERATE_BACKENDS=qwen`, `QWEN_BASE_URL=http://172.21.240.1:8081/v1`, `QWEN_API_KEY=…` |
| Measured (warm) | `/explain` 1.2–2.5 s · `/extract` 8.5 s (sender roles correct) · generation ≈ 67 tokens/s · analyst lesson (JSON, ~3k tokens) 38 s · GPU ≈ 5.5 / 6.1 GB |
| Load time | ≈ 6 s after double-click |

Alternatives kept for fallback: `qwen-hf` (transformers fp16 + CPU offload; ~4–5× slower, needs `~/models/qwen3vl-2b`),
and a no-root CUDA toolkit in `~/cuda-12.6` (NVIDIA redist + PyTorch's cuBLAS; tested with a kernel) in case a native
WSL llama.cpp build is approved. Docker cannot use the GPU (no NVIDIA runtime).

Quality notes (Qwen3-VL-2B vs Gemini Flash): explanations are good; screenshot sender roles needed the layout-aware
EXTRACT prompt; generated quizzes can repeat questions or mark wrong answers, so **human review (§13.1 rule 14) is
essential**, and the lesson prompt must be rewritten for children (§10.1), it still produces employee content.

Fixes found on the machine: DistilBERT ONNX needs padding to 512; the URL model's `StringNormalizer` needs an explicit
`C.UTF-8` locale; `uvicorn` must run as `~/venv/bin/python -m uvicorn` (`scripts/start_testbed.sh`).

### 4.7 Reaching `guardian-ai` from the laptop

WSL is NAT'd, so use an SSH tunnel through the Windows host (WSL 2 forwards Windows `127.0.0.1` to services that WSL
binds on `0.0.0.0`). **Use `127.0.0.1`, not `localhost`**: on the Windows side `localhost` resolves to IPv6 `::1`, which WSL does not forward, and the tunnel returns empty replies:
```bash
# laptop: GPU machine's guardian-ai :8000 → laptop localhost:8100 (and llama-server :8081 → :8181 for debugging)
ssh -N -L 8100:127.0.0.1:8000 -L 8181:127.0.0.1:8081 guardian-gpu
curl -s localhost:8100/health
```
Then set Django's `GUARDIAN_AI_URL=http://localhost:8100` (§6.9). Ports are chosen so the laptop's own dev
`guardian-ai` (:8000) and Django (:8001) never clash with the tunnel.

**Exit criterion:** `curl localhost:8100/health` from the laptop returns the GPU machine's hostname and GPU name.

---

## 5. Phase 1: Foundation

### 5.1 Cleanup

**Remove the vignette study completely**

| File | Change |
|---|---|
| `pita/pita/settings.py` | Remove `'vignette'` from `INSTALLED_APPS`; remove `'pita.middleware.VignetteParticipantMiddleware'` from `MIDDLEWARE`; delete `VIGNETTE_URL_PREFIX`, `VIGNETTE_DONE_SLUG`, `VIGNETTE_RESEARCH_PREFIX`; delete the `'vignette'` logger and `LOGGING['loggers']['vignette']['handlers'].append('file')` |
| `pita/pita/urls.py` | Remove both `vignette` `path(...)` includes; point `handler404` at a new `awarenessapp.views.handler_404` (or delete the line) |
| `pita/pita/middleware.py` | Delete `VignetteParticipantMiddleware`; keep `SecurityHeadersMiddleware` |
| `pita/vignette/` | Delete the directory (its migrations go with it; on a fresh DB nothing references them) |

**Remove open tracking**: delete `track_email_open`, the `track/` URL include and `AWARENESS_TRACK_PREFIX`; stop
building `tracking_url` in `services/email_service.py`; remove the pixel `<img>` from
`templates/emails/awareness_email.html`. Delivery status (`pending/sent/failed`) stays.

**Other**
- [ ] Fresh database (`createdb guardian_db`, or `DATABASE_URL=sqlite:///db.sqlite3` for speed). Existing staff data
      is not migrated. `python manage.py makemigrations && migrate && createsuperuser`.
- [ ] Move `_rl()` from `services/transformation.py` into `awarenessapp/services/ratelimit.py` and add a decorator
      `@rate_limit('check', 30, 3600)` keyed on user ID or IP.
- [ ] Replace insider-threat categories (keep the old constant name as a temporary alias so existing code runs):
```python
SCAM_CATEGORY_CHOICES = [
    ('reward', 'Fake reward / prize'),
    ('advance_fee', 'Scholarship / bursary / advance fee'),
    ('otp_theft', 'OTP / PIN / account takeover'),
    ('phishing_link', 'Phishing link / fake login'),
    ('impersonation', 'Impersonation (school, brand, person)'),
    ('sextortion', 'Sextortion / threats'),      # route to safeguarding, never auto-share; never a simulation theme
    ('other', 'Other'),
    ('all', 'All Types'),
]
INSIDER_THREAT_CHOICES = SCAM_CATEGORY_CHOICES   # temporary alias
```
  Update `threat_labels` in `transformation._build_prompt` and the panel templates that show the old names.
- [ ] Settings additions (values in §19.1): `CORS` unchanged (no SPA), `GUARDIAN_AI_URL`, `GUARDIAN_AI_TOKEN`,
      `GUARDIAN_AI_TIMEOUT`, `GUARDIAN_DEMO_MODE`, `CLASSIFIER_THRESHOLD`, `QWEN_BASE_URL`, `QWEN_MODEL`, the
      `GUARDIAN_SIM_*` settings (§8.5) and the new URL prefixes (§12).

**Exit criterion for 5.1:** `python manage.py check` is clean; the panel loads; `grep -rn vignette pita/` returns
nothing.

### 5.2 Roles

- [ ] `Users.ROLE_CHOICES = (('child','Child'), ('parent','Parent / Guardian'), ('analyst','UCC Analyst'))`.
- [ ] `UsersManager.create_user`: default role `parent` (public sign-up creates parents only). `analyst` gets
      `is_staff=True, is_superuser=False`. `create_superuser` gets `role='analyst'`.
- [ ] `create_anonymous_user`: `role='child'`, inactive.
- [ ] `signals.py`: `_ROLE_GROUPS = {'analyst': 'Analysts', 'parent': 'Parents', 'child': 'Children'}`. Give
      `_ADMIN_CODENAMES` (plus the new `view_intel`, `manage_simulations`, `export_intel`) to **Analysts**. Create the
      extra `Safeguarding` group with `view_confidential_reports`. Do **not** let `sync_user_group` strip it, because
      it is not a role group.
- [ ] `Group` model: `admin`/`superadmin` FKs → `limit_choices_to={'role': 'analyst'}`. Or drop the custom fields if unused.
- [ ] Every `role='staff'` filter in `views.py` (≈ lines 474, 789, 837, 935, 954, 1301) and `email_service.py:50`:
      decide case by case whether it means "children" or "recipients". Do not search-and-replace blindly.
- [ ] Add `awarenessapp/permissions.py` with decorators `child_required`, `parent_required`, `analyst_required`
      (mirroring `_require_perm`) and a `post_login_redirect(user)` that sends each role to its home.

### 5.3 Profiles (no employee PII about children)

- [ ] `Profile`: keep `full_name`, picture. Drop `department, position, reports_to, unit, staff_category,
      employment_terms, staff_id, date_left` (fresh migration). Update the `navbar_base.html` profile modal and
      `static/js/navbar.js` to match.
- [ ] New `safety` app models (full field list in §7.3):

```python
AGE_BANDS = [('8-10', '8–10'), ('11-13', '11–13'), ('14-17', '14–17')]

class ChildProfile(models.Model):
    user = OneToOneField(Users, null=True, blank=True, related_name='child_profile')  # null until the child signs in
    nickname = CharField(max_length=40)        # never a legal name
    age_band = CharField(choices=AGE_BANDS)
    district = CharField(blank=True)           # aggregate-level only
    pseudonym = CharField(unique=True)         # "C-7F3A", shown to analysts instead of the nickname
    email = EmailField(blank=True)             # entered by the parent; used for notices, practice emails and lessons
    email_blocked = BooleanField(default=False)  # set by "This isn't me / stop" in the welcome notice
    created_by = ForeignKey(Users)             # the parent who created it

class GuardianChildLink(models.Model):         # parent ↔ child, unique_together, active flag
class PairingCode(models.Model):               # store a SHA-256 hash only, 10-minute expiry, single use
class ConsentRecord(models.Model):
    parent, child, kind = 'phishing_simulation' | 'parent_alerts' | 'data_notice'
    granted_at, revoked_at, notice_version
```

### 5.4 Family onboarding (PRD §6)

1. **Parent** signs up (email/password or Google via allauth) → `role='parent'`.
2. Parent → **Add child**: nickname, age band, district (optional) and **child's email**. This alone is enough for
   practice emails and library lessons. **The child never needs to install the app or create an account.**
3. Parent → **Practice emails** consent per child (§8.1) → `ConsentRecord`, then Guardian sends the welcome notice to
   the child's address.
4. *Optional, for in-app features (checks history, reports, "My practice"):* Guardian issues a **one-time pairing
   code** (`SAFE-4821`, 10 minutes, hashed, rate-limited to 10 attempts per hour). The **child** opens Guardian → "I
   have a family code" → enters the code → sets a password → a `role='child'` account bound to the existing
   `ChildProfile` → "What your guardian can and cannot see" → the child home. Earlier library views and quiz scores
   collected through email links are already attached to that `ChildProfile`, so they appear in the child's progress.
5. If the child later uninstalls the app or stops signing in, practice emails and lessons keep working by email.

A child **without** a parent link can still use "Is this safe?", "Something happened" and "Call 116" (PRD §6.2). They
are excluded from practice emails and parent alerts.

**Exit criterion:** a parent creates a child with only an email and the welcome notice is sent. A second child
pairs from another browser, and each user lands on their own role home. An analyst lands on the workspace. Each role gets 403/redirect on the other roles' URLs.

---

## 6. Phase 1b: The `guardian-ai` inference service (FastAPI)

### 6.1 Why a separate service

- Heavy ML dependencies stay off the Django web server.
- It is the clearest evidence of Testbed use: the same service runs on the GPU machine and reports host, GPU and
  latency on every call.
- **Django never talks to a model directly for child/parent inputs.** It only calls `GUARDIAN_AI_URL`, so moving from
  Gemini to the GPU machine is a configuration change, not a code change.

Content generation (parent composer, analyst pipeline) is different: it stays in Django's provider layer
(`awarenessapp/services/llm.py`, §6.8) because it is admin/parent text, not child input.

### 6.2 Two modes, one contract

| | **Dev mode (now)** | **Testbed mode (when the GPU machine is set up)** |
|---|---|---|
| Runs on | This laptop, `uvicorn` on `:8000` | GPU machine WSL, `~/guardian-ai`, `uvicorn` on `:8000`, reached via tunnel on laptop `:8100` |
| `CLASSIFY_BACKENDS` | `gemini` | `onnx` |
| `CLASSIFY_URL_BACKENDS` | `url-onnx` (needs the model locally) | `url-onnx` |
| `EMBED_BACKENDS` | `minilm` (needs the model locally) | `minilm` |
| `EXTRACT_BACKENDS` | `gemini` | `qwen` (llama-server on Windows, §4.6; fallback `qwen-hf`) |
| `EXPLAIN_BACKENDS` | `gemini` | `qwen` |
| `GENERATE_BACKENDS` | `gemini` | `qwen` (content generation for Django; replaces Gemini, §6.8) |
| `ALLOW_CLOUD` / `ALLOW_CLOUD_IMAGES` | `true` / `true` | **`false` / `false`** (as deployed: no Gemini at all) |
| Django `GUARDIAN_AI_URL` | `http://localhost:8000` | `http://localhost:8100` |
| Result label (`mode`) | `cloud-dev` → UI: "Checked with cloud AI (development)" | `live` → UI: "Live check on Guardian AI" |
| Data allowed | **Synthetic / team test data only.** Text is redacted before it leaves; screenshots cannot be redacted | Anything the product allows (§13) |

Backends are tried **left to right**; the first success wins, and every attempt is recorded in the response
(`attempts`). If all fail, the endpoint returns `status: "unavailable"` and Django falls back to rules +
`unable_to_verify` (§7.4).

### 6.3 API contract

All endpoints require header `X-Guardian-AI-Key: <GUARDIAN_AI_TOKEN>` when the token is set (always set on the GPU
machine, because it listens on the event network). Every response carries `meta`:
`{host, gpu, backend, model, cloud, latencyMs, attempts:[{backend, ok, error?}]}`.

| Method & path | Request | Response (besides `meta`) |
|---|---|---|
| `GET /health` | - | `{status, service:"guardian-ai", version, host, gpu, mode, backends:{classify:[{name, ready, reason?}], extract:[…], explain:[…]}}` |
| `POST /classify` | `{text}` (≤ 5,000 chars) | `{status, spamScore, label (0/1), reasons[], scoreKind: "uncalibrated-model-score" \| "llm-judgement", calibrated:false, threshold}` |
| `POST /extract` | multipart `file` (PNG/JPEG/WebP ≤ 5 MB, magic bytes checked, re-encoded, max side 1600 px) | `{status, messages:[{sender_role, text}], urls[], phone_numbers_present, claimed_organisation, language}` |
| `POST /explain` | `{riskLevel, signals[], audience: "child"\|"parent", ageBand}` | `{status, explanation, recommendedActions[]}` |
| `POST /classify-url` | `{urls: [...]}` (≤ 20) | `{status, results:[{url, phishingScore, label}], scoreKind, calibrated:false}`. URLs are never fetched |
| `POST /embed` | `{texts: [...]}` (≤ 64) | `{status, vectors, dimensions}` (normalised; cosine = dot product) |
| `POST /generate` | `{prompt, system?, maxTokens, json}` | `{status, text, data?}` (`data` = parsed JSON when `json:true`; invalid JSON counts as failure). Parent/analyst prompts only, never child input |

The image is never written to disk. The LLM never decides risk: `/classify` is one signal, Django's `fuse()`
decides (§7.4).

### 6.4 Folder layout (in this repo, deployed by `git pull`/`scp` to `~/guardian-ai` on the GPU machine)

```
guardian-ai/
├── README.md                 # both modes, setup, curl examples
├── requirements.txt          # fastapi, uvicorn, pydantic-settings, python-multipart, pillow, google-genai, httpx, pytest
├── requirements-gpu.txt      # onnxruntime, tokenizers, openai (+ transformers/torch already on the Testbed)
├── .env.example              # §19.1
├── guardian_ai/
│   ├── main.py               # FastAPI app + routes + auth dependency
│   ├── config.py             # pydantic-settings: backend chains, cloud switches, model paths, limits
│   ├── chain.py              # run a capability through its backend chain, collect attempts
│   ├── redact.py             # mask PIN/OTP/codes, phone numbers, emails before any cloud call
│   ├── images.py             # validate magic bytes, size; re-encode with Pillow (drops EXIF), downscale
│   ├── prompts.py            # CLASSIFY, EXTRACT, EXPLAIN (§6.6)
│   ├── evidence.py           # host, cached nvidia-smi query, latency; JSONL inference log (§6.7)
│   └── backends/
│       ├── base.py           # Backend, BackendError, BackendUnavailable
│       ├── gemini.py         # google-genai, Flash first, fallbacks on 429/503, JSON response mode
│       ├── onnx_classifier.py# DistilBERT ONNX via onnxruntime + tokenizers (lazy load)
│       └── qwen.py           # OpenAI-compatible client to llama-server (option A) or transformers (B/C)
└── tests/                    # pytest + FastAPI TestClient with fake backends; no network
```

### 6.5 Backends

**Gemini (dev mode, now)**
- `google-genai` client, `GEMINI_MODELS` tried in order; on HTTP 429/503 move to the next model (same pattern as
  `_generate_with_retry` in `services/transformation.py`).
- `response_mime_type="application/json"`, `temperature=0.1`.
- Text is passed through `redact()` first. Images are sent only if `ALLOW_CLOUD_IMAGES=true`.
- `classify` returns `scoreKind="llm-judgement"` so Django and the UI never present it as a trained-model score.

**ONNX classifier (Testbed mode)**
```python
# backends/onnx_classifier.py (sketch)
from tokenizers import Tokenizer
import numpy as np, onnxruntime as ort
tok = Tokenizer.from_file(f'{MODEL_DIR}/tokenizer.json'); tok.enable_truncation(512)
sess = ort.InferenceSession(f'{MODEL_DIR}/text_classifier.onnx', providers=['CPUExecutionProvider'])
INPUTS = {i.name for i in sess.get_inputs()}           # log once: usually input_ids, attention_mask

def classify(text):
    enc = tok.encode(text)
    feed = {'input_ids': np.array([enc.ids], np.int64), 'attention_mask': np.array([enc.attention_mask], np.int64)}
    logits = sess.run(None, {k: v for k, v in feed.items() if k in INPUTS})[0][0]
    p = np.exp(logits - logits.max()); p /= p.sum()    # skip if the output is already probabilities
    return {'spamScore': float(p[1]), 'label': int(p[1] >= THRESHOLD), 'scoreKind': 'uncalibrated-model-score'}
```
At startup, log `sess.get_inputs()`/`get_outputs()` once to confirm a `(batch, 2)` logits output.

**Qwen3-VL (Testbed mode)**
```python
# backends/qwen.py, option A (llama-server, OpenAI-compatible)
client = OpenAI(base_url=QWEN_BASE_URL, api_key='none', timeout=QWEN_TIMEOUT_S)
def _chat(content, max_tokens):
    r = client.chat.completions.create(model=QWEN_MODEL, temperature=0.1, max_tokens=max_tokens,
                                       messages=[{'role': 'user', 'content': content}])
    return parse_json(r.choices[0].message.content)
def extract(image_bytes, mime):
    b64 = base64.b64encode(image_bytes).decode()
    return _chat([{'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}},
                  {'type': 'text', 'text': prompts.EXTRACT}], 512)
def explain(prompt):
    return _chat([{'type': 'text', 'text': prompt}], 300)
```
Option B/C (transformers) follows the model card: `processor.apply_chat_template(messages, tokenize=True,
add_generation_prompt=True, return_dict=True, return_tensors='pt')` → `model.generate(max_new_tokens=384)`, with the
§4.6 dtype/attention/pixel limits.

### 6.6 Prompts (JSON only)

```text
CLASSIFY  You are a scam and phishing detector for messages received by children and families in Uganda
          (SMS, WhatsApp, email, social media). Some values are masked as [PHONE], [EMAIL], [CODE], [SECRET].
          Return ONLY JSON: {"spamScore": 0-1, "label": "scam"|"not_scam", "reasons": ["max 5 short phrases"]}

EXTRACT   You read screenshots of chats/SMS/emails that a child received. Return ONLY JSON:
          {"messages":[{"sender_role":"other|child|unclear","text":"..."}], "urls":["..."],
           "phone_numbers_present":true|false, "claimed_organisation":"name or null", "language":"en|lg|nyn|other"}
          Rules: copy text exactly; do not judge safety; if you cannot tell who sent a message use "unclear";
          never describe people's faces or bodies.

EXPLAIN   You explain scam-check results to {a Ugandan child aged <band>: short, kind, simple sentences |
          a Ugandan parent: calm, practical, one tip for talking to their child}.
          Use ONLY the evidence below. Do not add new facts. Never say something is 100% safe.
          Return ONLY JSON: {"explanation":"2-3 short sentences","recommendedActions":["...","...","..."]}
          Risk level (already decided, do not change it): {risk_level}   Evidence: {signals}
```

### 6.7 Inference log (Testbed evidence)

Each call appends one JSON line to `guardian-ai/logs/inference.jsonl`: timestamp, endpoint, backend, model, host, GPU,
latency, input length and SHA-256, status. **No content.** Django also writes `AuditEvent('inference.call', …)` with
the returned `meta`. Copy samples plus `nvidia-smi` output into `docs/testbed-evidence/`.

### 6.8 Django side

- `awarenessapp/services/ai_client.py` (later `safety/services/ai_client.py`): `health()`, `classify(text)`,
  `extract(bytes, mime)`, `explain(risk, signals, audience, age_band)` with `requests`, timeouts
  (`GUARDIAN_AI_TIMEOUT=30`, 120 for extract), the `X-Guardian-AI-Key` header, and `status:"unavailable"` on any
  connection error.
- Settings: `GUARDIAN_AI_URL`, `GUARDIAN_AI_TOKEN`, `GUARDIAN_AI_TIMEOUT`, `CLASSIFIER_THRESHOLD`.
- Management command `python manage.py ai_health`: prints `/health`, then runs one synthetic `/classify`.
- **Provider layer for content generation**: `awarenessapp/services/llm.py` replaces the two copies of
  `_generate_with_retry()` (`transformation.py`, `vignette/gemini.py`). One `chat(messages, *, allow_cloud)` function
  with an ordered provider list: **now** `gemini:<flash models>`; **later** `qwen-local` (llama-server via the tunnel)
  first, Gemini second. Gemini exposes an OpenAI-compatible endpoint
  (`https://generativelanguage.googleapis.com/v1beta/openai/`), so one `openai` client can cover both, or keep
  `google-genai`. `allow_cloud=True` only for parent prompt topics and analyst sources, never for raw child content.
  Record the provider on the generated content (`generated_by`).
- Remove `google-genai` from Django's `requirements.txt` only if nothing imports it any more.

### 6.9 Setup and build steps

**A. Dev mode on this laptop (do first)**

> **Status 2026-11-05:** built. `guardian-ai/` service, 30 passing tests (`pytest`, no network), Django
> `awarenessapp/services/ai_client.py`, `GUARDIAN_AI_*` settings and `manage.py ai_health`. Verified end to end
> Django → service → backend chain, plus the "unreachable" path. **Waiting on `GEMINI_API_KEY` in `guardian-ai/.env`**
> for the live Gemini smoke tests. Until the vignette app is removed (§5.1), Django commands need a non-empty
> `GEMINI_API_KEY` or `--skip-checks`, because `vignette/gemini.py` builds a Gemini client at import time.
> Local venvs: `guardian-ai/.venv` (service) and `.venv` (Django), both gitignored.
1. `cd guardian-ai && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
2. `cp .env.example .env`; set `GEMINI_API_KEY`, keep chains = `gemini` (§19.1).
3. `uvicorn guardian_ai.main:app --port 8000 --reload`
4. Smoke tests:
   ```bash
   curl -s localhost:8000/health
   curl -s -X POST localhost:8000/classify -H 'Content-Type: application/json' \
     -d '{"text":"Congratulations! You won UGX 500,000. Send your Mobile Money PIN to claim."}'
   curl -s -X POST localhost:8000/extract -F file=@docs/samples/synthetic_scam_screenshot.png
   curl -s -X POST localhost:8000/explain -H 'Content-Type: application/json' \
     -d '{"riskLevel":"high","signals":["Asks for a PIN","Unexpected prize"],"audience":"child","ageBand":"11-13"}'
   ```
5. `pytest` (fake backends: redaction, chain fallback, cloud switch off, image validation, auth).
6. Django: set `GUARDIAN_AI_URL=http://localhost:8000`, run `python manage.py ai_health`.

**B. Testbed mode on the GPU machine (when Phase 0 is done)**
1. Copy the folder: `scp -r guardian-ai guardian-gpu:` lands in Windows; prefer `git clone`/`git pull` inside WSL,
   or `tar c guardian-ai | ssh guardian-gpu "wsl -d Ubuntu-24.04 -- tar x -C ~"`.
2. In WSL: `source ~/venv/bin/activate && pip install -r ~/guardian-ai/requirements-gpu.txt`.
3. `.env`: `CLASSIFY_BACKENDS=onnx`, `EXTRACT_BACKENDS=qwen`, `EXPLAIN_BACKENDS=qwen,gemini`,
   `CLASSIFIER_DIR=~/models/distilbert-phish`, `QWEN_BASE_URL=http://localhost:8081/v1`, `GUARDIAN_AI_TOKEN=<random>`.
4. `tmux new -s qwen` → llama-server (§4.6), detach. `tmux new -s ai` →
   `uvicorn guardian_ai.main:app --host 0.0.0.0 --port 8000`, detach.
5. Laptop: tunnel (§4.7), then Django `GUARDIAN_AI_URL=http://localhost:8100`, same token → `ai_health` shows the
   GPU host.
6. Save `/health`, `/classify`, `/extract` responses and `nvidia-smi` into `docs/testbed-evidence/`.

**Switching back** (network down during the demo): stop the tunnel, set `GUARDIAN_AI_URL=http://localhost:8000`,
and results are labelled `cloud-dev` again.

**Exit criteria:** dev mode: all four smoke tests return `status:"ok"` with `backend:"gemini"`; `pytest` green;
`ai_health` passes from Django. Testbed mode: the same tests via `:8100` return `backend:"onnx"`/`"qwen"` and the GPU
host.

---

## 7. Phase 2: Feature 1: Artefact upload and detection

### 7.1 What can be submitted

| Input | How it is accepted | How text and evidence are extracted | Limits |
|---|---|---|---|
| Typed/pasted **text** (SMS, WhatsApp, chat) | Textarea | As-is | 5,000 chars |
| **Link** | Text field (or found inside text) | Parsed with `urllib.parse`/`tldextract`. **Never fetched, previewed or visited** | 20 URLs per submission |
| **Screenshot** (PNG/JPEG/WebP) | File upload, with camera capture on mobile (`accept="image/*" capture`) | `guardian-ai /extract` (Qwen3-VL on the Testbed): messages with sender role, URLs, claimed organisation | 5 MB, magic-byte check, re-encoded with Pillow to strip EXIF |
| **PDF** | File upload | `pdfplumber` (already a dependency): text plus link annotations. Encrypted PDFs or more than 10 pages → "unable to verify" | 10 MB |
| **Email** (`.eml`) | File upload, or "paste raw email source" | Python `email` stdlib: `From` display name/address, `Reply-To`, `Return-Path`, `Authentication-Results` (SPF/DKIM/DMARC), subject, text body, HTML links (`href` vs visible text). Attachments are listed by name/type only and never opened | 10 MB |
| `.txt` | File upload | As-is | 1 MB |
| Anything else (`.apk`, `.exe`, `.zip`, `.docx`, …) | **Rejected** in MVP with a friendly message ("Don't open it. Ask an adult."). P2: SHA-256 lookup against a malware-hash feed, never executed | - |, |

Extend `services/file_validators.py` with `validate_artifact_upload(f)` (extension whitelist plus magic bytes:
`%PDF`, PNG `\x89PNG`, JPEG `\xFF\xD8\xFF`, WebP `RIFF....WEBP`, and an `.eml` header sanity check).

### 7.2 File handling rules

- Uploads are read **in memory** (or into a temp file under `/tmp/guardian-uploads/`, outside `MEDIA_ROOT`). After
  extraction they are **deleted**. Only the SHA-256 hash, size, MIME type and sanitised extracted text are kept.
- **Never** send uploads to Cloudinary (it is configured in `settings.py` for profile pictures). Never put them under
  `MEDIA_ROOT`, because `pita/urls.py` serves `MEDIA_URL` publicly when `DEBUG=True`.
- Screenshots go only to `guardian-ai`. In **Testbed mode** they stay on the GPU machine and never reach a cloud LLM.
  In **dev mode** `guardian-ai` forwards them to Gemini Flash, so use **synthetic screenshots only** (§6.2, §13.1).

### 7.3 Data model (`safety/models.py`)

```python
INPUT_KINDS = ['text', 'url', 'image', 'pdf', 'email', 'txt']
RISK = ['low', 'suspicious', 'high', 'unable_to_verify']      # never "safe"

class Submission(models.Model):
    submitted_by = ForeignKey(Users, null=True)                # null = guest
    submitter_role = CharField()                               # child | parent | guest
    child = ForeignKey(ChildProfile, null=True)                # set when the submitter is a child
    input_kind = CharField(choices=INPUT_KINDS)
    file_sha256 = CharField(blank=True); file_mime = CharField(blank=True); file_size = IntegerField(null=True)
    sanitised_text = TextField()                               # redacted scammer-supplied content only
    urls = JSONField(default=list)                             # inert text
    email_headers = JSONField(default=dict)                    # from / reply_to / auth results; recipient address removed
    content_hash = CharField(db_index=True)                    # duplicate forwards are counted once
    risk_level, category, signals, evidence_sources, classifier_score, explanation, recommended_actions,
    needs_human_review, mode ('live'|'cloud-dev'|'demo'|'unable_to_verify'), providers, latency_ms
    organisation = ForeignKey(ImpersonatedOrganisation, null=True)   # "alleged impersonation"
    scam_wave = ForeignKey(ScamWave, null=True)
    simulation_delivery = ForeignKey('phishsim.SimulationDelivery', null=True)   # §8.7
    review_status = CharField(default='new')                   # new | reviewing | reviewed | escalated
    district = CharField(blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

The other `safety` models (adapted from the migration plan):

```python
RISK_CHOICES = [('low', 'Low observed risk'), ('suspicious', 'Suspicious'),
                ('high', 'High risk'), ('unable_to_verify', 'Unable to verify')]
CHANNEL_CHOICES = [('app', 'App'), ('telegram', 'Telegram'), ('sms', 'SMS')]

class ImpersonatedOrganisation(models.Model):
    name = CharField(max_length=120, unique=True)
    sector = CharField(max_length=60, blank=True)
    official_domains = JSONField(default=list)     # ["mtn.co.ug"]; used for brand/domain mismatch
    aliases = JSONField(default=list)              # "MTN", "MoMo"
    # UI always says "alleged impersonation", never institutional fault

class ScamWave(models.Model):
    STATUS = [('suspected', 'Suspected'), ('under_review', 'Under review'), ('confirmed', 'Confirmed'), ('closed', 'Closed')]
    title = CharField(max_length=200)
    category = CharField(max_length=20, choices=SCAM_CATEGORY_CHOICES)
    organisation = ForeignKey(ImpersonatedOrganisation, null=True, blank=True, on_delete=SET_NULL)
    status = CharField(max_length=20, choices=STATUS, default='suspected')
    centroid = JSONField(null=True, blank=True)    # mean embedding
    grouping_method = CharField(max_length=40, default='embedding_cosine')
    first_observed = DateTimeField(auto_now_add=True); latest_observed = DateTimeField(auto_now=True)

class ThreatIndicator(models.Model):               # URLhaus / PhishTank / OpenPhish rows: looked up, never visited
    kind = CharField(max_length=10)                # url | domain
    value = CharField(max_length=2048, db_index=True)
    source = CharField(max_length=30)              # urlhaus | phishtank | openphish | manual
    first_seen = DateTimeField(null=True, blank=True); ingested_at = DateTimeField(auto_now_add=True)

class IncidentReport(models.Model):
    STATUS = [('new', 'New'), ('priority_review', 'Priority review'), ('restricted', 'Restricted'), ('reviewed', 'Reviewed')]
    child = ForeignKey(ChildProfile, null=True, blank=True, on_delete=SET_NULL)
    category = CharField(max_length=30)            # money_sent | account_access | threat | suspicious_link | other
    summary = TextField()                          # child-reviewed, redacted
    confidential = BooleanField(default=False)     # suppresses parent notification; Safeguarding group only
    notify_parent = BooleanField(default=False)    # child's explicit choice for non-confidential reports
    status = CharField(max_length=20, choices=STATUS, default='new')
    assigned_to = ForeignKey(Users, null=True, blank=True, on_delete=SET_NULL)
    submission = ForeignKey(Submission, null=True, blank=True, on_delete=SET_NULL)
    created_at = DateTimeField(auto_now_add=True)

class ParentAlert(models.Model):                   # deliberately NO message text, NO screenshot, NO conversation
    parent = ForeignKey(Users, on_delete=CASCADE, related_name='parent_alerts')
    child = ForeignKey(ChildProfile, on_delete=CASCADE)
    severity = CharField(max_length=10)            # high | suspicious
    title = CharField(max_length=160)              # threat type only
    safety_action = CharField(max_length=300)
    delivery_state = CharField(max_length=12, default='in_app')   # in_app | emailed | failed
    read_at = DateTimeField(null=True, blank=True); created_at = DateTimeField(auto_now_add=True)

class AuditEvent(models.Model):
    actor = ForeignKey(Users, null=True, blank=True, on_delete=SET_NULL)
    action = CharField(max_length=60)              # inference.call, report.view, export.csv, status.change, consent.change …
    target = CharField(max_length=120, blank=True)
    detail = JSONField(default=dict)               # host, gpu, model, backend, latency = Testbed evidence
    at = DateTimeField(auto_now_add=True)

class EvaluationRun(models.Model):
    name = CharField(max_length=80)                # classifier_only | llm_only | rules_only | fused
    dataset = CharField(max_length=120); threshold = FloatField(null=True)
    metrics = JSONField()                          # precision, recall, f1, tp, fp, tn, fn, latency, per-category/language
    failure_examples = JSONField(default=list)     # synthetic only
    host = CharField(max_length=80); backend = CharField(max_length=40)
    created_at = DateTimeField(auto_now_add=True)
```

Register all models in `safety/admin.py` (instant back-office for the demo).

**Seed data** (`python manage.py seed_guardian`): port the prototype fixtures (`UCC_TEST_BED_HACKATHON/shared/index.js`:
organisations, submissions, campaigns → scam waves, reports, alerts, parent children), a starter set of approved
child lessons + quizzes per simulation topic, and matching shared `SimulationTemplate`s. **All synthetic, all
`mode='demo'`.** Seed `official_domains`, e.g. MTN Uganda → `mtn.co.ug`, Airtel Uganda → `airtel.co.ug`, Makerere
University → `mak.ac.ug`, Centenary Bank → `centenarybank.co.ug`, UNICEF Uganda → `unicef.org` (verify each).


### 7.4 Pipeline (`safety/services/`)

The orchestration pseudocode is in §7.4.1. The services it calls:

1. **`extract.py`**: one entry point, `extract(kind, payload) -> ExtractResult(text, urls, email_headers, notes)`,
   dispatching to text / image (`ai_client.extract`) / pdf / eml / txt.
   - Screenshot sender attribution is `unclear` → show "Which message did you receive?" with the extracted messages as
     radio options, instead of guessing (PRD §9.1).
2. **`redact.py`**: mask OTP/PIN-like digit runs, passwords, phone numbers, email addresses (including the child's own
   address in `.eml` `To:`), and names after greetings.
3. **`url_checks.py`**: punycode/`xn--`, confusables (0/o, 1/l/I), brand-in-subdomain, IP hosts, shorteners, odd TLDs,
   `ThreatIndicator` match, claimed-organisation vs `official_domains` mismatch.
4. **`email_checks.py`** (new, for `.eml`): display-name brand vs sender domain mismatch, `Reply-To` ≠ `From` domain,
   SPF/DKIM/DMARC `fail` in `Authentication-Results`, link text ≠ `href` host, risky attachment types listed.
5. **`rules.py`**: Ugandan scam patterns (MoMo PIN/OTP request, processing/bursary fee, prize/reward, urgency,
   "keep it secret", threats).
6. **`fuse.py`**: deterministic risk decision (§7.4.1 step 6). **The LLM never sets the risk level.**
7. **`ai_client.py`**: `classify`, `extract` and `explain` calls to `GUARDIAN_AI_URL`, with timeouts. If the service
   is down: no classifier and no strong rule evidence → `unable_to_verify`. Explanation falls back to templated text.
8. **Audience-specific explanations**: `explain(..., audience='child', age_band=...)` gives short, kind sentences.
   `audience='parent'` adds "how to talk to your child about this".
9. **After the decision:**
   - Child has already clicked, paid or shared a code ("I already did something" checkbox) → offer the
     **Something happened** flow pre-filled (PRD §7.1).
   - `high` risk + child with an active parent link + `parent_alerts` consent → create a `ParentAlert` with **no
     content**, only the category title, the safety action and the time. In-app alert, plus email if the parent opted in.
   - `suspicious`/`high` → `assign_scam_wave()` (content-hash dedupe, then embedding similarity ≥ 0.80, labelled
     "suspected").
   - `AuditEvent('inference.call', host/gpu/latency)` is the Testbed evidence.

#### 7.4.1 Orchestration (`safety/services/analysis.py`)

```python
def analyse(*, kind, payload, submitted_by=None, child=None, channel='app') -> Submission:
    signals, sources, meta = [], [], {}

    # 1. Extract text/URLs/headers. Screenshots → guardian-ai /extract; the image is discarded after this call.
    ex = extract(kind, payload)                       # §7.4 item 1
    if ex.status == 'unavailable':
        return _unable(..., 'We could not read this right now. Please paste the text instead.')
    if ex.needs_sender_choice:                        # some messages have sender_role == 'unclear'
        return _clarify(..., ex.messages)             # ask the child which message they received

    # 2. Redact before storing or sending anywhere
    clean = redact(ex.text)

    # 3. URL and email-header checks: parse only, NEVER fetch
    for u in ex.urls:
        signals += url_signals(u)
        if ThreatIndicator.objects.filter(value__in=[u, host(u)]).exists():
            signals.append('Known malicious link (threat-intelligence match)'); sources.append('threat-intel')
    signals += email_signals(ex.email_headers, ex.links)       # .eml only
    org = claimed_org(clean, ex.claimed_organisation)
    if org and ex.urls and not any(host(u).endswith(d) for u in ex.urls for d in org.official_domains):
        signals.append(f"Link does not belong to {org.name}'s official website"); sources.append('brand-domain-check')

    # 4. Classifier via guardian-ai (Gemini in dev mode, ONNX on the Testbed)
    cl = ai_client.classify(clean); meta['classify'] = cl.meta
    if cl.status == 'ok': sources.append('llm-classifier' if cl.score_kind == 'llm-judgement' else 'message-classifier')

    # 5. Uganda-specific rules
    rule_hits = rules(clean)          # PIN/OTP/password request, processing fee, prize, urgency, secrecy, MoMo transfer, threats

    # 6. Deterministic fusion: the LLM never sets the risk level
    risk = fuse(cl, rule_hits, signals)
    #   known-bad URL OR credential request (PIN/OTP/password)          -> 'high'
    #   score >= THRESHOLD and >=1 rule hit, or brand/domain mismatch   -> 'suspicious' ('high' if 2+ strong)
    #   score >= THRESHOLD and no rule/url evidence                     -> 'suspicious' + needs_human_review
    #   score < THRESHOLD and no evidence                               -> 'low' ("low observed risk", never "safe")
    #   classifier unavailable and no rule evidence                     -> 'unable_to_verify'
    category = categorise(rule_hits, signals)

    # 7. Explanation via guardian-ai; template fallback
    exp = ai_client.explain(risk, signals + rule_hits, audience, age_band)
    if exp.status != 'ok': exp = TEMPLATES[audience][risk]

    # 8. Persist minimal evidence, dedupe, simulation match, scam wave
    sub = Submission.objects.create(..., sanitised_text=clean, content_hash=sha256(normalise(clean)),
                                    mode='cloud-dev' if cl.meta.get('cloud') else 'live', ...)
    if phishsim.match_submission(sub): pass                  # §8.7, excluded from intel
    elif risk in ('suspicious', 'high'): assign_scam_wave(sub)
    AuditEvent.objects.create(action='inference.call', detail=meta)

    # 9. Parent alert: high risk, child with active link + parent_alerts consent; never content
    if risk == 'high' and child:
        for link in child.guardian_links.filter(active=True):
            ParentAlert.objects.create(parent=link.guardian, child=child, severity='high',
                                       title=CATEGORY_TITLES[category], safety_action=PARENT_ACTION[category])
    return sub
```

#### 7.4.2 Scam waves, threat feeds and sensitive reports

- **Scam-wave grouping:** same `content_hash` = duplicate forward, counted once (PRD §11: submissions ≠ unique
  incidents). Otherwise `all-MiniLM-L6-v2` embedding (CPU), cosine ≥ 0.80 to a wave centroid, else a new wave.
  Label on the dashboard: *"Suspected scam wave, grouped by similarity ≥ 0.80; not confirmed"*.
- **Threat intelligence ingestion:** `python manage.py ingest_threat_feeds` downloads URLhaus public dumps (check
  terms), and PhishTank/OpenPhish only per their access conditions, into `ThreatIndicator`. Runs on the laptop.
  This replaces Guardian's NVD/CISA ingestion for the security path. **Never** call `fetch_url_source` or
  `requests.get` on links submitted by children or parents.
- **Self-harm / abuse / imminent danger** wording in reports or checks → do not classify automatically; show the 116
  support path and route to the `Safeguarding` group (PRD §7.3).

### 7.5 Screens

**Child, "Is this safe?"** (`/child/check/`, ported from the prototype's check screen)
- One input card with tabs: **Paste text or link** · **Upload screenshot** · **Upload file/email**.
- A "Did you already click, pay or share a code?" toggle.
- Result page: risk badge (Low observed risk / Suspicious / High risk / Unable to verify), "What we noticed" (signals),
  "What to do now" (actions), the source label (`Live check on Guardian AI` / `Demo` / `Unable to verify`), and buttons
  **Something happened** and **Call 116** (`tel:116`).
- History (`/child/history/`): label + result only.

**Parent, "Check something"** (`/parent/check/`): same form and partials. The result page adds "Talking to your child
about this". Parent history is separate from children's.

Shared partials: `templates/safety/_check_form.html`, `_result_card.html`, `_risk_badge.html`, `_call_116.html`.

### 7.6 "Something happened" (incident report, PRD §7.2/§13)

- Category (money sent / shared a code / threatened / clicked a link / other), a short guided summary that the child
  can edit, optional link to a prior `Submission`, and a **Keep this private from my guardian** checkbox
  (`confidential=True`).
- The confirmation page states that the report is saved in Guardian and **was not sent to UCC, Police or 116**.
- Self-harm, abuse or danger keywords → supportive message, prominent **Call 116**, route to the `Safeguarding` group.
  No automatic outside contact and no parent alert.

**Exit criterion:** child and parent can each submit text, a link, a screenshot, a PDF and an `.eml`. Each returns a
labelled result. The file is gone from disk afterwards. A high-risk child check creates a content-free parent alert.
Analysts see the sanitised submission with a pseudonym.

---

## 8. Phase 3: Feature 2: Phishing/spam simulation

**Core idea:** a practice email is the hook, and the **awareness library is the lesson**. Every link in a practice
email leads to a curated library page about that email's topic. For example, a "click to win UGX 500,000" email
opens the library lesson on prize/reward scams, with the email's red flags highlighted and a short quiz. Delivery is
by email, and lessons are plain web pages opened by token, so this **works even if the child never installed the
Guardian app or has since uninstalled it**.

### 8.0 Content flow: regulators → parents → children (decision 2026-11-06)

The technical work stays with the analysts; parents and children only ever see plain, friendly screens.

```
Analyst (UCC / Ministry / Police CFPU)            Parent                                   Child
publishes a topic (source → AI → review → ──►  "News for families" feed + email   ──►  practice message (email; later SMS /
approve); Guardian prepares ALL versions         digest: what's trending, how to         WhatsApp) → tap → topic lesson or
automatically                                    talk about it; one tap: "Send a        quiz on Guardian web (or the app if
                                                 practice message to my children"       installed), already signed in
                                                 or "Automate drills"
```

1. **One publish, every version.** When an analyst approves a topic, Guardian generates and stores, from the same source:
   - the **parent version** (plain explanation + "how to talk with your child");
   - the **child version** in child language, per age band, keeping the analyst's chosen format (article, quiz or
     scenario): the parent never chooses between quiz/article/scenario;
   - the **captivating practice message** (email now; SMS and WhatsApp text later) that leads to that child version;
   - the quiz, if the format has one.
   All AI output goes through the analyst's review before parents see it (§13.1 rule 14).
2. **Parents act in one tap.** "Send to my children now", or "Automate drills" (Guardian schedules future topics for
   their children within the §8.1 limits). The prompt-topic composer (§8.3) stays as an advanced option.
3. **Always available.** Every approved lesson and quiz stays in the library on each side: the parent library shows
   parent versions, the child library shows child versions. Practice messages are a way in, not the only way.
4. **Practice links never show a login page** (§8.6): the link itself carries a signed, single-use-per-delivery
   token derived from the parent's setup, so the child lands directly on the lesson. Lesson and quiz pages accept
   either a signed-in child or a valid practice token, so they work like public pages while every open, lesson view
   and quiz score is still attributed to that child.
5. **Channels.** The parent can add, per child: email (now), phone number for SMS, and WhatsApp number. SMS
   (Africa's Talking) and WhatsApp (official Business API) send the same practice text with the same token link,
   behind the same consent, notice and rate limits. Model fields can be added now; the senders arrive later.

### 8.1 Principles (non-negotiable for children)

1. **Parent consent plus a notice to the child's address.** The parent enters the child's email on the parent side.
   They then confirm consent (`ConsentRecord(kind='phishing_simulation')`) and tick "I have told my child Guardian may
   send practice messages". Guardian immediately sends a short **welcome notice** to that address: what Guardian is,
   that practice messages may arrive, and a "This isn't me / stop" link that blocks the address. This is how the child
   is informed when they have no app. It also stops anyone using Guardian to send fake phishing to strangers.
   Practice emails start only after the notice was delivered and not blocked. Timing and content are never disclosed
   in advance.
2. **Teach, never shame or scare.** No themes about threats, sextortion, violence, self-harm, family emergencies,
   exam failure or police. Allowed themes: fake rewards/prizes, scholarship/bursary fees, free data bundles, game
   currency, "verify your account" and fake school notices. This is enforced for parent prompts too (§8.3, step 4).
3. **No real brand impersonation by default.** Templates use fictional organisations and `.example`-style domains
   ("MoMoPay Rewards", "Kampala Scholars Fund", `airtime-bonus.example`). Real institutions are P2, with analyst
   approval.
4. **Honest sending.** Emails come from Guardian's own sending domain (a deceptive *display name* is allowed, spoofing
   another domain is not), with the header `X-Guardian-Simulation: <delivery-id>`.
5. **No credential capture, ever.** Linked pages contain no input that submits secrets. Quiz answers are the only
   thing a child submits.
6. **Tracking is for learning only.** Guardian records the link click, library pages viewed, quiz attempts/scores and
   reports. It records no open pixels and no IP/geo/device data.
7. **Rate limits.** At most 2 practice emails per child per month (analyst and parent sends combined), no sends
   between 21:00 and 07:00 EAT, and at most 5 child email addresses per parent account.
8. **A human reviews everything before it reaches a child.** Analyst templates are approved by an analyst.
   Parent-generated emails and lessons are reviewed by **that parent** in the preview step, after an automatic safety
   screen. Analysts can see and retire any parent-created template/lesson; this is content only, never child data.

### 8.2 Who does what

| Actor | Can |
|---|---|
| Analyst | Create/AI-draft/approve **shared** templates and their linked library lessons; run programme-wide simulation campaigns to consenting children (by age band/district); moderate parent-created content; see simulation + library analytics (pseudonymous, §10.2) |
| Parent | Add children by **nickname + age band + email** (no app needed); consent/revoke per child; **create practice emails on the simulation composer page** (§8.3) from an existing guideline **or** a prompt topic; schedule them; see per-child outcomes, lessons viewed and quiz scores |
| Child | Receive emails in their normal inbox; on click, land on the related library lesson + quiz (no login or install); report suspected emails via "Is this safe?" if they use the app (§8.7); see "My practice" and progress if they sign in |

### 8.3 Parent simulation composer (the parent's extra input page)

The parent has two input pages:
- **Check something** (`/parent/check/`, §7.5), the same inquiry/detection page the child has;
- **Create a practice email** (`/parent/practice/new/`), a parent-only wizard:

| Step | What the parent does | Built on |
|---|---|---|
| 1. Who | Select one or more of their own children (only those with an email, consent, and a delivered notice) | `ChildProfile`, `ConsentRecord` |
| 2. Source | **(a) Use an existing guideline:** pick from approved library lessons and shared simulation templates, filtered by the child's age band and topic (reward, bursary, data bundle, game currency…). **(b) Write a prompt topic**, as the panel does today with `ContentSource(source_type='prompt')`, e.g. *"someone on WhatsApp promising free airtime if you click a link"* | Existing `ContentSource` → `RawContent` → `transform_raw_content` pipeline |
| 3. Generate | For (b), one LLM call returns **both** the practice email (sender display name, subject, body with `{{ link }}`, red flags) **and** the linked library lesson (title, risk, action, article) plus a 3-question quiz. For (a), the stored template/lesson is loaded | `transformation.py` with a new `simulation` prompt; `services/llm.py` with `allow_cloud=True` only after redaction (the prompt is the parent's text, not child content) |
| 4. Safety screen | Automatic checks: banned themes (§8.1.2), real brand names/domains from `ImpersonatedOrganisation`, no credential fields, link text uses `.example`, and no personal data beyond the child's nickname. A failure shows the reason and blocks the next step | `phishsim/services/safety_screen.py` |
| 5. Preview and edit | The parent sees the email as the child will, the red flags, and **the library page the link leads to**. All fields are editable. "Approve for my family" | Same templates as the real send |
| 6. Schedule | "Send now" or a window (randomised time inside it) | `SimulationCampaign(created_by_role='parent')` |

Content the parent creates is stored as `AwarenessContent(audience='child', owner=parent, visibility='family')` plus
a `SimulationTemplate(owner=parent)`. Their family can use it right away. It enters the **shared** library only if an
analyst promotes it.

### 8.4 Data model (`phishsim/models.py`, plus awareness changes in §10.1)

```python
class SimulationTemplate(models.Model):
    name, category                      # reward | scholarship_fee | data_bundle | game_currency | account_verify | school_notice
    age_bands = JSONField()
    difficulty = CharField()            # easy | medium | hard
    sender_display_name, sender_local_part     # → rewards@<GUARDIAN_SIM_DOMAIN>
    subject, body_html                  # contains {{ link }}; visible link text may show a fake .example URL
    red_flags = JSONField()             # [{"label": "Promises money for a click", "excerpt": "..."}]
    lesson = ForeignKey(AwarenessContent)      # REQUIRED: the library page every link in the email leads to
    owner = ForeignKey(Users, null=True)       # null = shared/analyst template; set = a parent's family template
    visibility = CharField()            # shared | family
    status = pending | approved | retired; created_by, reviewed_by, reviewed_at

class SimulationCampaign(models.Model):
    template, created_by, created_by_role (analyst|parent)
    target_children = ManyToManyField(ChildProfile)    # consent and notice re-checked at send time
    send_window_start, send_window_end
    status = draft | scheduled | sending | completed | cancelled

class SimulationDelivery(models.Model):
    campaign, child (ChildProfile)
    token = CharField(unique=True)      # secrets.token_urlsafe(24)
    email_sent_to = CharField()
    status = pending | sent | failed | skipped_no_consent | skipped_blocked
    sent_at, clicked_at, click_count, lesson_viewed_at, quiz_attempt (FK QuizAttempt, null), reported_at,
    report_source (check_upload | in_app_button)

class EmailAddressNotice(models.Model): # the welcome notice from §8.1.1
    child, email, sent_at, delivered (bool), blocked_at, block_token
```

### 8.5 Sending

- Refactor `awarenessapp/services/email_service.py`: extract `_send_to` into
  `send_html_email(to, subject, html, from_email, headers=None)`. Awareness campaigns, notices, parent alerts and
  simulations all use it.
- `phishsim/services/sender.py` → `send_due_deliveries()`: re-checks consent, notice status, block list and rate
  limits **at send time**, renders `link = SITE_URL + reverse('sim_open', args=[token])` into the template, sends, and
  sets `sent`/`failed`. It is triggered by `python manage.py send_simulations` (cron or by hand) or by the "Send now"
  button.
- Dev uses `EMAIL_BACKEND=console`. The demo uses the existing Gmail SMTP settings with team-controlled test inboxes.
- Settings: `GUARDIAN_SIM_DOMAIN`, `GUARDIAN_SIM_MAX_PER_MONTH=2`, `GUARDIAN_SIM_QUIET_HOURS=21-7`,
  `GUARDIAN_MAX_CHILD_EMAILS_PER_PARENT=5`, `GUARDIAN_LEARNER_SESSION_DAYS=7`.
- **P1:** an in-app practice inbox for signed-in children, as a fallback if SMTP fails.

### 8.6 Link → library lesson (no app, no login)

1. The child clicks any link in the practice email → `/s/<token>/` (`sim_open`).
2. Guardian records `clicked_at`/`click_count` and **signs the child straight in** (no password, no app needed), then
   redirects to the template's lesson: `/learn/<content_id>/?via=practice`. Decision 2026-11-06: children are
   auto-logged in from the parent's practice message to remove friction on the library pages.
   - If the child has an account, the token logs into it; if not, Guardian creates a passwordless child account bound
     to the parent's `ChildProfile` (the parent-entered email), so lessons and quiz scores land in the same progress.
   - The session is marked `via_practice_link` and expires after `GUARDIAN_LEARNER_SESSION_DAYS`; tokens are single
     delivery, random (`token_urlsafe(24)`), and stop working when consent is revoked or the address is blocked.
   - A link-signed session can use the child space and library, but not change the email/password or family links;
     those still need a normal sign-in.
3. The library page (the existing `content_view`, moved to a public `learn/` area) shows:
   - a friendly banner: "**This was a practice message from Guardian, set up by your parent. No harm done.**";
   - the email again with its **red flags highlighted** (from `template.red_flags`);
   - the lesson itself (risk → what to do);
   - the linked **quiz**, scored and saved against the `ChildProfile` and the delivery;
   - "More lessons like this" (same category and age band), Call 116, and an optional "Get the Guardian app" link.
4. Works whether or not the Android app is installed (the email link opens the web version), so practice emails keep
   reaching children who uninstall the app. iPhone, Mac and desktop users always use the web version.
5. An unknown, expired or blocked token shows a generic public library page with no tracking.

This is why practice emails stay effective after an uninstall: nothing depends on the app. The email arrives in the
normal inbox and the lesson is a web page.

### 8.7 Reporting a practice email (where Feature 1 and Feature 2 meet)

- A child who suspects an email pastes it, or uploads the `.eml`, into **Is this safe?**.
- After normal detection, `phishsim.match_submission(submission)` checks the `X-Guardian-Simulation` header, a token in
  any URL, or a `content_hash` match with the child's recent deliveries.
- On a match it sets `delivery.reported_at` and links the submission to the delivery. The submission is **excluded from
  threat intelligence and scam waves**. The child sees the normal result, then: "**Great catch, this was a practice
  message!**" plus a link to the same lesson.
- Key metric: **report rate** (reported before or without clicking) versus **click rate**.

### 8.8 Screens

| Role | Screen | Content |
|---|---|---|
| Parent | `parent/practice/` | Per child: email, notice status, consent toggle; list of sent practice emails with outcome (clicked? lesson read? quiz score? reported?) and "how to talk about it" tips |
| Parent | `parent/practice/new/` | The composer wizard (§8.3) |
| Analyst | `panel/simulations/templates/` | Shared templates + their lessons: create, AI draft, preview, approve, retire; moderation queue of parent-created family content |
| Analyst | `panel/simulations/campaigns/` | Programme-wide campaigns (template + age bands + districts + window); eligible-children count only |
| Analyst | `panel/simulations/analytics/` | Click, report, lesson and quiz-completion rates by template, category, age band, district, analyst- vs parent-created; pseudonymous rows; groups under 5 suppressed |
| Child (signed in) | `child/practice/` | "My practice": emails received, caught/clicked, lessons and quiz scores, badges |
| Public (token) | `s/<token>/` → `learn/<id>/?via=practice` | §8.6 |

**Exit criterion:** a parent adds a child by email (no app) → the notice is delivered → the parent creates a practice
email from a **prompt topic** and reviews email + lesson → it is sent → the child clicks in their inbox → lands on the
related library lesson with highlighted red flags → takes the quiz → the parent sees click + lesson + score → the
analyst sees it in pseudonymous analytics. A second email reported via "Is this safe?" shows "Great catch". Revoking
consent or "This isn't me" stops further sends.

---

## 9. Phase 4: Analyst workspace

Reuse `templates/panel/base_panel.html` and add sections to its nav. Screens come from the prototype's admin dashboard
(`frontend/components/admin/AdminDashboard.jsx`) and PRD §12.

| Nav item | Content | Priority |
|---|---|---|
| **Overview** | Checks analysed, suspicious/high, incident reports, active scam waves, practice report-rate; 7/30-day trend; recent sanitised threats; most-impersonated organisations | P0 |
| **Threat intelligence** | Search/filter `Submission`s (risk, category, channel, input kind, district, status, child vs parent). Detail shows sanitised evidence, signals, evidence sources, model/host and review status (audited) | P0 |
| **Scam waves** | Suspected `ScamWave`s with techniques, districts, trend and linked evidence. Labelled "suspected, grouped by similarity, not confirmed" | P0 |
| **Organisations** | Alleged impersonations with counts and the standard disclaimer | P0 |
| **Incident reports** | Non-confidential summaries. Confidential ones show "Restricted" unless the user is in the `Safeguarding` group (each view audited) | P0 |
| **Simulations** | §8.8: shared templates + lessons, programme campaigns, moderation of parent content, analytics | P0 |
| **Content pipeline / library** | Existing sources → raw → transform → approve → campaigns, retargeted at children/parents (§10.1) | P0 (the library is the practice landing page) |
| **Learning analytics** | Existing content/quiz/email analytics, pseudonymised (§10.2) | P0 |
| **Families and children** | Families, children by age band and district, consent rates (alerts / practice), devices connected, checks by children vs parents, practice click vs report rate, lessons opened and quiz scores per topic, parent follow-through (topics forwarded, drills automated), alerts raised; groups under 5 suppressed, pseudonyms only | P0 |
| **Model evaluation** | Live, re-runnable evaluation page for every model (§11.5) | P0 |
| **Evaluation** | `EvaluationRun`s: precision/recall/F1, TP/FP/TN/FN, failure examples, host | P0 |
| **Exports** | CSV of sanitised intel and simulation aggregates, with an `AuditEvent` per export | P1 |
| **Alerts and activity** | `AuditEvent` feed (review changes, exports, inference calls) | P1 |

Replace `analytics_staff` with `analytics_children` (§10.2): pseudonymous rows, never nicknames or emails.

---

## 10. Phase 5: Awareness library, quizzes and their tracking

Guardian's library and quizzes **stay**, together with their tracking (views, quiz attempts, scores, per-question
answers) and reporting (analytics pages, printable report). What changes is who sees which slice, and that a child no
longer needs an account to be tracked.

### 10.1 Content and model changes

- `ContentSource` → `RawContent` → `transform_raw_content` → `AwarenessContent` (pending → approved) stays. Rewrite
  `_build_prompt` for **children by age band** and **parents** ("Family rule of the week" replaces `policy`).
- New `AwarenessContent` fields: `audience` (`child|parent`), `age_bands`, `topic` (same vocabulary as simulation
  categories, so emails map to lessons), `owner` (null = shared library; set = a parent's family content) and
  `visibility` (`shared|family`).
- `ContentSource` gets `owner`/`scope` so a **parent's prompt topic** (§8.3) runs through the same pipeline, scoped to
  their family. New transformation mode `simulation`: one LLM call returns the practice email, the lesson and the quiz.
- New source type **from a scam wave**: an analyst turns a real `ScamWave` into a lesson ("Scam of the week: fake data
  bundle") and, optionally, a matching shared simulation template.
- **Tracking keyed on the child, not the login:**
  - `UserContentInteraction` → add `child = FK(ChildProfile)`, make `user` nullable, unique on `(child, content)`.
    Add `via` (`library|practice|email_campaign`) and `delivery = FK(SimulationDelivery, null)`.
  - `QuizAttempt` → add `child = FK(ChildProfile)`, make `user` nullable, add `delivery = FK(SimulationDelivery, null)`.
    `QuizAttemptAnswer` stays as is.
  - Signed-in children and token learners (§8.6) write to the same rows, so progress is continuous whether or not the
    app is installed.
- The staff portal (`templates/staff/library.html`, `content_view.html`, `quizzes.html`, `take_quiz.html`,
  `quiz_result.html`, `quiz_review.html`, `progress.html`) moves to a **`learn/`** area. It is open to signed-in
  children **and** to token learner sessions, filtered to `audience='child'`, the child's age band, and shared + own-
  family content.
- `EmailCampaign` (awareness emails) targets **parents** (weekly digest) or **children** (lesson by email, to the
  parent-entered address). `target_all_staff` → `target_audience` (`parents|children`). Lesson links in these emails use
  the same per-recipient token → learner session, so children without the app can read and do the quiz. No open pixel.

### 10.2 Tracking and reporting, redistributed

| Report | Child | Parent (own children only) | Analyst |
|---|---|---|---|
| Lessons viewed (what, when, via library/practice/email) | ✅ "My progress" (`progress.html`) | ✅ per child | ✅ per pseudonymous child + per content (`analytics_content*`) |
| Quiz attempts, scores, per-question review | ✅ own (`quiz_result`, `quiz_review`) | ✅ per child, with the review view | ✅ `analytics_quizzes`, pseudonymous, plus by age band/topic |
| Practice outcomes (sent, clicked, lesson viewed, quiz score, reported) | ✅ "My practice" | ✅ per email per child | ✅ simulation analytics (§8.8) |
| Awareness email delivery (sent/failed) | - | ✅ own family's emails | ✅ `analytics_campaigns`, `analytics_emails`, recipients pseudonymised |
| Printable report (`analytics_report`) | - | ✅ **family report**: per child, lessons, scores, practice outcomes, tips | ✅ programme report, de-identified |

Implementation notes:
- Reuse the existing analytics views and queries. Wrap them in a `scope` helper: `analyst` → all rows, with
  `ChildProfile.pseudonym` displayed and never nickname or email; `parent` → rows where
  `child__guardian_links__guardian=request.user`; `child` → own `ChildProfile`.
- `analytics_staff` (per-employee profiles) becomes `analytics_children`: pseudonym, age band, district, lessons,
  quiz average, practice report/click rate. The parent equivalent is `parent/children/<id>/progress/`, showing nickname
  and full detail for their own child.

## 11. Phase 6: Evaluation and Testbed evidence

Mandatory per Readiness Guide §6.2: *"detection or classification solutions must define their evaluation method and
report performance metrics, including false positives and false negatives."*

### 11.1 Synthetic Ugandan test set

`guardian-ai/eval/uganda_synthetic_v1.csv` with columns `id,text,label,category,language,split,source`:
- ~150–300 rows, roughly balanced scam / legitimate;
- scams: MoMo reward, bursary/scholarship fee, OTP/PIN theft, fake Airtel/MTN data promos, impersonated teacher/
  headmaster, fake job, lookalike links (`mtn-ug.example`, `airteI.example` with a capital I), sextortion-style
  threat *phrasing only* (no imagery);
- legitimate (crucial for false positives): real-style MTN/Airtel promos with official short codes, school fee
  reminders, parent messages, bank notifications without requests, exam results notices;
- a handful in **Luganda** and **Runyankole** if a teammate can write them; report them separately and honestly;
- **no real messages from minors, no real phone numbers** (Readiness Guide §6.3);
- split `dev` (threshold tuning) and `test` (reported numbers). Never tune on `test`.

### 11.2 Script (`guardian-ai/eval/run_eval.py`)

Calls the running service's `/classify` for every `test` row, so the **same script evaluates both modes**: run it on
the laptop for `backend=gemini` and on the GPU machine for `backend=onnx`.
```python
rows = [r for r in csv.DictReader(open('uganda_synthetic_v1.csv')) if r['split'] == 'test']
y = [int(r['label']) for r in rows]
t0 = time.time(); scores = [post('/classify', {'text': r['text']})['spamScore'] for r in rows]
lat = (time.time() - t0) / len(rows) * 1000
for thr in (0.5, TUNED_THRESHOLD):
    pred = [int(s >= thr) for s in scores]
    p, r, f, _ = precision_recall_fscore_support(y, pred, average='binary', zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    fails = [...first 15 misclassified rows with gold, score...]
    print(json.dumps({'name': NAME, 'backend': BACKEND, 'threshold': thr, 'host': HOST,
                      'metrics': {'precision': p, 'recall': r, 'f1': f, 'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
                                  'avg_latency_ms': lat}, 'failure_examples': fails}))
```
Load results with `python manage.py load_eval results.json` into `EvaluationRun`; show them on the analyst Evaluation
page and in `docs/EVALUATION.md`.

### 11.3 What to report

| Configuration | Why |
|---|---|
| `classifier_only` (DistilBERT ONNX, Testbed) | Baseline of the pretrained model on *our* domain |
| `llm_only` (Gemini Flash, dev mode) | What the dev-mode judgement does alone; declared as a cloud LLM |
| `rules_only` | What deterministic Uganda-specific rules catch |
| `fused` (full Django pipeline, each backend) | The actual product |

For each: precision, recall, F1, TP/FP/TN/FN, per-category and per-language breakdown, average latency, 10–15
failure examples with a one-line reason. **Expected honest finding:** the classifier was trained on English *emails*;
short SMS-style Ugandan scams and legitimate telco promos will cause errors. Show how rules + URL/email checks +
fusion change FP/FN. Separately measure screenshot extraction on ~20 synthetic screenshots (scam text extracted
correctly? sender attribution correct?). **Do not invent metrics.**

### 11.5 Model cards and the live evaluation page (decision 2026-11-06)

Every model Guardian uses gets a documented model card **and** a live, re-runnable evaluation on an analyst page
(`/<panel>/evaluation/`). Results are stored as `EvaluationRun` rows, so the history of every run stays visible.

| Model | Use case in Guardian | Runs on | Fallback when unavailable |
|---|---|---|---|
| DistilBERT phishing/spam (ONNX) | Message scam score (`/classify`), one signal for fusion | GPU machine CPU | Deterministic rules decide alone; result labelled "safety rules only" |
| pirocheto phishing-URL (ONNX, TF-IDF + linear SVM) | Link phishing score (`/classify-url`) | GPU machine CPU | Lexical URL checks + brand/official-domain mismatch |
| all-MiniLM-L6-v2 | Embeddings for grouping similar scams into scam waves (`/embed`) | GPU machine CPU | Exact duplicate grouping by content hash |
| Qwen3-VL-2B-Instruct (official GGUF Q8_0 + F16 vision) | Screenshot reading, child/parent explanations, lesson + practice-message generation | GPU (Vulkan, llama.cpp) | Screenshots: "paste the text instead"; explanations: fixed templates; generation: retry later (Gemini only if explicitly allowed) |
| Deterministic rules + fusion | Final risk decision for every check | Django | Always available; the safety net |

**Each model card records:** model id and licence; version/file hash; task and labels; input limits (sequence length,
image size); runtime (device, precision/quantisation, context size, GPU memory); decision threshold and why; how it is
called and by which endpoint; known weaknesses; the fallback above.

**Each evaluation run reports the conventional metrics** on the synthetic Ugandan test set (§11.1), split by category
and language: accuracy, precision, recall, F1, ROC-AUC (score models), the confusion matrix (TP/FP/TN/FN), false
positive and false negative examples, threshold sweep, mean and p95 latency, host and backend. Extra per model:
- URL model: the same metrics on a labelled URL list (official vs lookalike domains);
- MiniLM: pair similarity on same-wave vs different-wave messages (separation, best threshold);
- Qwen extraction: text accuracy and sender-role accuracy on synthetic screenshots; explanation checks (no "safe"
  claims, no em dashes, reading level); generation checks (valid JSON, correct quiz answers marked, no duplicates);
- rules-only and fused pipeline: the same classification metrics, so the value of each layer is visible.

The page has a **Run evaluation** button per model (and "run all"), shows the latest results with the run history,
and states the dataset version and the exact model/backend that answered. Nothing is invented: if a model is
unreachable, the run is recorded as unavailable.

### 11.4 Additional slices and evidence


- Add **artefact-type slices**: text, URL, screenshot (extraction accuracy and sender attribution on about 20
  synthetic screenshots), PDF, `.eml` (header checks on synthetic emails, including Guardian's own simulation
  templates as positives).
- Run the classifier evaluation on the GPU machine (Testbed evidence) and the Gemini baseline on the laptop. Store JSON results in `EvaluationRun` (`manage.py load_eval`) and evidence in
  `docs/testbed-evidence/`.
- Simulation and library metrics are **product metrics, not model metrics**. Report them separately and only from the demo run.
  Do not invent numbers.

---

## 12. Template and URL map

Keep the existing obfuscated-prefix pattern in `settings.py` (`AWARENESS_*_PREFIX`). Add `GUARDIAN_CHILD_PREFIX`,
`GUARDIAN_PARENT_PREFIX` and `GUARDIAN_SIM_PREFIX` (the landing path should stay short, for example `s`). The panel
keeps `AWARENESS_PANEL_PREFIX`. Routes are shown with readable names below.

```
templates/
├── base.html, navbar_base.html          # role-aware nav; "Guardian" branding
├── home.html                            # entry: "I'm a parent" · "I have a family code" · "Get help now" (+ Call 116)
├── safety/_check_form.html, _result_card.html, _risk_badge.html, _call_116.html, _alert_item.html
├── child/
│   ├── base_child.html                  # mobile-first, large touch targets, bottom nav (Home · Check · Practice · Learn · Family)
│   ├── home.html                        # Is this safe? · Something happened · Talk to someone / Call 116
│   ├── check.html, result.html, history.html
│   ├── report.html, report_done.html
│   ├── practice.html, practice_inbox.html (P1)
│   ├── family.html                      # pair with code; "what your guardian can see"
│   └── progress.html                    # my lessons, quiz scores (moved from staff/progress.html)
├── learn/                               # moved from staff/; signed-in children AND token learner sessions
│   ├── base_learn.html                  # no app chrome needed; "practice message" banner slot
│   ├── library.html, content_view.html  # content_view shows highlighted red flags when ?via=practice
│   └── quizzes.html, take_quiz.html, quiz_result.html, quiz_review.html
├── parent/
│   ├── base_parent.html
│   ├── dashboard.html                   # Your family: children, paired state, recent alerts
│   ├── child_add.html, pairing_code.html
│   ├── check.html, result.html, history.html
│   ├── alerts.html, preferences.html
│   ├── practice.html                    # child emails, consent, notice status, per-email outcomes
│   ├── practice_new.html                # simulation composer wizard: guideline OR prompt topic → preview → schedule (§8.3)
│   ├── child_progress.html              # lessons, quiz scores/review, practice outcomes for one child
│   └── family_report.html               # printable (reuses analytics_report layout)
│   └── advisor.html (P1)                # parent AI advice, no access to child data
├── panel/                               # analyst workspace (existing + new)
│   ├── overview.html, threats.html, threat_detail.html, scam_waves.html, scam_wave_detail.html,
│   ├── organisations.html, reports.html, report_detail.html, evaluation.html, exports.html, activity.html
│   ├── simulations/ templates.html, template_form.html, campaigns.html, campaign_form.html, analytics.html, moderation.html
│   ├── analytics_children.html          # replaces analytics_staff.html (pseudonymous)
│   └── (existing sources/content/campaigns/analytics templates, retargeted)
└── emails/ awareness_email.html (no pixel, tokenised lesson links), child_notice.html, parent_alert.html, simulation_base.html
```

| Route | View | Role |
|---|---|---|
| `/` | home / role redirect | any |
| `/child/`, `/child/check/`, `/child/check/<id>/`, `/child/history/` | child home and check | child (check: also guest, P1) |
| `/child/report/` | incident report | child, guest |
| `/child/practice/`, `/child/family/`, `/child/progress/` | | child |
| `/learn/`, `/learn/<id>/`, `/learn/quizzes/<id>/`, `/learn/quizzes/result/<id>/` | library + quizzes | child, or token learner session |
| `/parent/`, `/parent/children/add/`, `/parent/children/<id>/code/` | family | parent |
| `/parent/check/`, `/parent/alerts/`, `/parent/preferences/` | | parent |
| `/parent/practice/`, `/parent/practice/new/` | practice settings + **simulation composer** | parent |
| `/parent/children/<id>/progress/`, `/parent/report/` | child progress, family report | parent |
| `/pair/` | redeem pairing code → child sign-up | public, rate-limited |
| `/s/<token>/` | record click → learner session → redirect to the linked `/learn/<id>/?via=practice` | public (token) |
| `/n/<block_token>/stop/` | "This isn't me / stop" from the welcome notice | public (token) |
| `/<panel>/overview/ … /simulations/ … /evaluation/` | analyst workspace | analyst |
| `/api/health` | Django + DB + `guardian-ai /health` | public |

---

## 13. Safety and safeguarding rules

These are scored (15%) and required by the Data Protection and Privacy Act Cap. 97, Computer Misuse Act, National
Child Policy, ITU COP Guidelines and UNCRC.

### 13.1 Core rules

1. **Synthetic data only** at the event. No real children, real child images, real phone numbers or real CSAM, ever.
2. **Never fetch user-submitted URLs** (no previews, no server-side visits). URLs are stored and shown as inert text.
3. **Discard screenshots and files** after extraction; store only redacted scammer text, hashes and metadata.
4. **Redact** PINs, OTPs, passwords, phone numbers, emails and names before storage and before any call that leaves
   our machines.
5. **Cloud LLMs and child input:** in **Testbed mode** no raw child input goes to Gemini or any cloud LLM. In **dev
   mode** (§6.2) Gemini Flash receives redacted text and screenshots **only for synthetic/team test data**; results
   are labelled `cloud-dev`. Switch to Testbed mode (or set `ALLOW_CLOUD=false`) before any real user.
6. **The LLM never decides risk.** Deterministic fusion decides; the LLM classifies as one signal and explains.
   Disagreement → `unable_to_verify`.
7. **Never say "100% safe".** Use "Low observed risk".
8. **Parents get minimum context** for checks (threat type, action, time): no message text, screenshots or chat logs.
9. **Confidential reports** never notify parents; visible only to the `Safeguarding` group (django-guardian object
   permissions).
10. **Self-harm / abuse / imminent danger** → empathetic response, Call 116, safe-adult guidance, human safeguarding
    review. No automated police/helpline contact.
11. **Impersonated organisations** are always labelled *alleged impersonation*, never culprits or breached parties.
12. **Report submissions** state they were **not** sent to UCC, Police or 116 unless a real integration confirms it.
13. **No open-tracking pixels**, no browsing-history collection, no hidden monitoring.
14. **Human review** of every AI-generated lesson, quiz and practice email before a child sees it.
15. **Audit log** for status changes, restricted-evidence views, exports and every inference call.
16. **Label every result** `live`, `cloud-dev`, `demo` (fixture) or `unable_to_verify`.

### 13.2 Additional rules for this plan's features


1. Uploaded files are **never stored long-term, executed or opened by an external viewer**, and in Testbed mode never
   sent to a cloud LLM (dev-mode exception: §13.1 rule 5). Only the hash and sanitised text remain.
2. **Links are never fetched** by Guardian or `guardian-ai`, including links inside PDFs and emails.
3. **Parent uploads** about a child are still subject to redaction. A parent cannot use Guardian to read a child's
   private content: there is no feature to pull it, and analysts never see child-identifying data.
4. Practice emails follow §8.1 completely: parent consent + child notice, safe themes (also enforced on parent
   prompts), fictional brands, honest sending, no credential capture, learning-only tracking, frequency caps, and
   human-reviewed content.
5. Parent-entered child emails: at most 5 per parent, a welcome notice with a "This isn't me / stop" link before any
   practice email, and blocked addresses are never emailed again. This stops Guardian being used to phish strangers.
6. Practice-link sign-ins are scoped to one child, expire, cannot change account email/password or family links, and
   stop when consent is revoked or the address blocked. Child emails are never shown to analysts.
7. Simulation submissions are **excluded** from threat intelligence, scam waves and model evaluation positives drawn
   from "real" traffic.
8. Analyst aggregate analytics use **minimum cell size 5**. Smaller groups show "fewer than 5".
9. Every result shows its source label (`live`, `cloud-dev`, `demo`, `unable_to_verify`) in the UI as well as the DB.
10. Impersonated institutions are always labelled **alleged impersonation**.
11. Report confirmations say the report was **not** sent to UCC, Police or 116.
12. Audit log entries: inference calls, review status changes, confidential-report views, exports, simulation
    campaign creation/sends, parent-generated content approvals, consent changes, address blocks.

---

## 14. Porting ideas from the Next.js prototype

The prototype in `/home/tinex/UICT/UCC_TEST_BED_HACKATHON` keeps evolving. We **port ideas, copy and layout, not
code**: React components become Django templates with Tailwind and a little vanilla JS.

### 14.1 Current mapping

| Prototype (Next.js) | Guardian template | Notes |
|---|---|---|
| `app/page.jsx` (role chooser + hero) | `home.html` | Keep "screen size never grants a role". Roles come from login |
| `components/child/ChildExperience.jsx` → home, check, result ("What we noticed" / "What to do now"), report ("Thank you for telling us"), history ("My recent checks"), family ("Connect with a trusted guardian") | `child/*.html` | Includes the share-target idea (`?text=&url=` prefill on `/child/check/`) |
| `components/parent/ParentExperience.jsx` → "Your family", "Connect a child device", "How pairing works", "Choose useful alerts" (high-risk / suspicious / SMS fallback) | `parent/dashboard.html`, `pairing_code.html`, `preferences.html` | SMS fallback toggle shown as "coming soon" until a provider exists |
| `components/admin/AdminDashboard.jsx` → Overview, Threat intelligence, Scam waves, Organisations, Incident reports, Alerts and activity; detail drawer (sanitised evidence, signals, context, review action) | `panel/overview.html` … `panel/report_detail.html` | Drawer becomes a detail page (or an Alpine-free `<dialog>`). Charts: Chart.js from cdnjs, or simple CSS bars |
| `shared/index.js` (organisations, submissions, campaigns, reports, alerts, childHistory, parentChildren) | `safety/management/commands/seed_guardian.py` | All rows `mode='demo'`. Campaigns become `ScamWave` |
| `docs/DESIGN_SYSTEM.md`, `app/globals.css` tokens | **Not ported** | Guardian keeps its own teal "Deep Intel" design (`design.md`, `base.html`) for every role; prototype colours (blue/navy) are never used |
| `public/manifest.webmanifest`, `sw.js` | P2: manifest + install prompt for the child portal | Never cache role pages |
| `app/page.jsx` landing v2 (hero photo, confidence strip, install steps, access cards) | `home.html` | Android download shown only if `GUARDIAN_ANDROID_APP_URL` is set (the prototype APK is Chinga-branded) |
| `mobile/App.js` welcome / sign-in / help / guidance / privacy / settings, `src/ChildHome.js`, `src/FamilyHub.js` | `app/help.html` (help + safety steps), `app/privacy.html`, `parent/settings.html` (alerts + protection preferences), `parent/dashboard.html` (summary cards, children with remove, flagged counts), `child/home.html` | Phone + OTP sign-up not ported (email/Google accounts instead); protection preferences are stored but not enforced |

### 14.2 Sync routine

- When the prototype gains a screen worth having, add a row to the table above and a line to the log below, then
  build it as a template. One prototype screen = one PR.
- **Port content and flows, never visuals.** Existing Guardian pages stay; new pages are added. Everything uses
  Guardian's teal design and keeps the three roles visibly separate: child space (own sub-nav, "Child space"
  label), parent space (own sub-nav, "Parent space" label) and the analyst panel (`panel/base_panel.html`).
- Ported copy must still meet §13 (for example, no "100% safe", "alleged impersonation" wording).
- Prototype-only features (the Express mock API, the demo role switcher) are **not** ported.

### 14.3 Sync log

| Date | Prototype change | Guardian change | By |
|---|---|---|---|
| 2026-11-05 | Initial survey (child/parent/admin screens, fixtures) | This plan | - |
| 2026-11-05 (prototype `9a39e49`) | Landing (hero photo, "how it helps", install, role cards); child home/check/result/report/history/family; help ("Talk to someone") + safety steps; privacy; protection preferences; parent overview cards, multi-child list with remove, alerts with "what you can see", pairing steps, notification switches; Expo Android app (`mobile/`) **Added** in Guardian's design (all existing pages kept): child space `app/child_base.html` + `child/*`, `app/help.html`, `app/privacy.html`; parent space `app/parent_base.html` + `parent/{alerts,settings,check,result}.html`, new features added to `parent/dashboard.html`; "How Guardian helps" and "Keep Guardian on your phone" sections added to `home.html`; navbar role groups extended. **Wired to real data**: checks run the §7.4 pipeline on the GPU models, reports are saved, parent alerts are created; prototype demo-only parts replaced (fixed verdicts, OTP `123456`, Redis pairing). Admin screens unchanged in the prototype → still §9 | Claude Code |


### 14.4 Taking Guardian back to the prototype repo (for the mobile app): proposal, not yet done

The React Native app cannot render Django templates, so "taking the templates back" needs one of two routes:

| Route | How | Effort | Stays in sync? |
|---|---|---|---|
| **A. Live web shell (recommended for the hackathon)** | The Expo app opens Guardian's Django pages in a WebView (or the site ships as a PWA / Trusted Web Activity). Native bits stay native: 116 dialler, screenshot picker/share target, back button | Small | **Yes, automatically**: every Django template change is live in the app |
| B. Native screens on a Django API | Add DRF JSON endpoints (`/api/check`, `/api/report`, `/api/family/…`) that wrap the same services; the RN screens call them | Larger | Needs code on both sides for each change |

For both routes, a **`guardian-live/` folder in `UCC_TEST_BED_HACKATHON`** carries a read-only snapshot of
`pita/templates/{app,child,parent,safety}`, `home.html`, `base.html` + `navbar_base.html` (Guardian design), and a `SCREENS.md`
mapping each Django URL to its prototype screen. A script (`scripts/sync_to_prototype.sh`) refreshes it from this repo
and records the source commit; prototype ideas keep flowing back here through §14.2. Not written into that repo yet,
pending the team's choice of route and permission to commit there.

---

## 15. Priorities, timeline and team split

### 15.1 Priorities

| Priority | Items |
|---|---|
| **P0 (must demo)** | Phase 1 foundation (roles, add child by email, consent + notice; pairing) · Feature 1 for text, link, screenshot, `.eml` (child + parent) · live classifier on the Testbed · parent minimal alert · Something happened + Call 116 · **parent simulation composer** (existing guideline **and** prompt topic) · Feature 2 end-to-end: email → token → **topic library lesson** + quiz without app/login · report-by-upload · library/quiz tracking keyed on `ChildProfile` and redistributed (child progress, parent child-progress, analyst pseudonymous analytics) · analyst Overview / Threats / Scam waves / Organisations / Reports / Simulations / Evaluation · seed data incl. a starter set of approved lessons + matching templates per topic · evaluation with FP/FN |
| **P0 (added 2026-11-06)** | §8.0 content flow (one publish → parent + child versions + practice message) · §8.6 practice-link sign-in · §11.5 model cards + live evaluation page · analyst families/children analytics |
| **P1** | PDF + `.txt` uploads · guest checks · in-app practice inbox · "Report a suspicious email" button · analyst programme-wide campaigns · scam-wave → lesson source · family printable report · awareness lesson emails to children · CSV exports · activity feed · parent AI advisor |
| **P2 (roadmap, label as such)** | SMS (Africa's Talking) and WhatsApp (Business API) practice messages using the same token links (§8.0 item 5) · Malware-hash lookup for other file types · real-brand simulation templates under approval · PWA install · Telegram/SMS adapters (DRF webhooks) · Luganda/Runyankole · Android companion |

### 15.1a Build status (updated Fri 6 Nov, morning)

| Item | Status |
|---|---|
| §6.9 A `guardian-ai` dev mode (Gemini Flash): `/health /classify /extract /explain`, backend chains, redaction, image checks, inference log | ✅ live-tested on synthetic text + screenshot; 30 pytest tests |
| Django `ai_client` + `manage.py ai_health` | ✅ |
| §5.1 vignette removed (archived to `/home/tinex/UICT/guardian-archive/`), open tracking removed, `ratelimit.py`, scam categories | ✅ |
| §5.2 roles `child / parent / analyst`, groups incl. `Safeguarding`, role redirects, `permissions.py` | ✅ |
| §5.3 Profile without employee fields; `safety` app: `ChildProfile`, `GuardianChildLink`, `PairingCode`, `ConsentRecord` | ✅ migrated (database moved from Render to local PostgreSQL `guardian_local` on 6 Nov) |
| §5.4 family portal: add child by email, consent toggles, pairing code, `/pair/`, child "what my parent can see" | ✅ 17 Django tests |
| Google sign-in | Configured by `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`; button hidden when not set |
| Old panel analytics/campaign templates still show blank employee columns | ⏳ rewritten in Phase 4/5 |
| §4 GPU machine: venv, all models downloaded, `guardian-ai` Testbed mode running in tmux `ai`, token-protected, tunnel `:8100` | ✅ all six capabilities on local models; evidence in `docs/testbed-evidence/` |
| Gemini removed from defaults: `/generate` (Qwen) serves `transformation.py`; Gemini only if `GUARDIAN_GEMINI_FALLBACK=True` | ✅ analyst lesson generated in 38 s with GGUF Qwen; **lesson prompt still employee-themed** (rewrite in §10.1) |
| Prototype merge (2026-11-05 evening): child app, parent app, landing, help, privacy, preferences in the prototype design | ✅ 37 Django tests; live E2E through the GPU models (prize scam → high 11 s; school notice → low 2.4 s; fake Airtel link → suspicious 2.3 s; bursary screenshot → high 6.4 s; content-free parent alerts) |
| §7 v1 detection: `safety/services/{checks,analysis}.py`, `Submission`, `IncidentReport`, `ParentAlert`, `GuardianPreference` (migrated to Render) | ✅ text, links, screenshots; rules-only fallback labelled; low risk uses fixed wording (Qwen over-reassured) |
| §8.0 content flow + §8.6 practice-link sign-in (2026-11-06): `phishsim` app (`TopicPack`, `PracticeDelivery`), analyst "Family versions" page (generate with Qwen → safety screen → edit → publish), parent News for families + one-tap send + automatic drills, child My lessons + lesson/quiz, welcome notice with stop link, token links that sign the child in without a login page (passwordless account created if needed), practice reports recognised in checks, phone/WhatsApp fields | ✅ 49 tests; live generation 23 s on the GPU machine |
| §11.5 model cards + live evaluation page (6 Nov): `evaluation` app (`EvaluationRun`), analyst **Model evaluation** tab with a card per model (use, licence, files, limits, runtime, threshold, weaknesses, fallback, live readiness), Run / Run all in the background, run history and detail pages, `manage.py run_eval [--out]`; synthetic data in `pita/evaluation/data/`; results in `docs/EVALUATION.md` and `docs/testbed-evidence/2026-11-06_evaluation.json` | ✅ 8 runs on the GPU machine, 57 Django + 40 guardian-ai tests. Found and fixed: Qwen sender-role swaps (64.7% to 100% via bubble side), invented practice links and give-away practice text (link repair + safety note). Open: false alarms on genuine OTP/telco/bank notices (23 of 38 legitimate test messages) |
| Family library (6 Nov): News for families lists every approved topic (new vs already read), each topic page has the parent version, steps, full article, an in-page quiz, the child lesson preview and "Send to my children"; awareness emails, the old library, quiz and progress URLs lead parents there (children to their lessons); content prompt and email rewritten for families with regulator reporting (Police CFPU, UCC, Sauti 116); actions shown as steps, never as raw lists | ✅ 61 Django tests. Existing topic #1 still has workplace text from the old prompt (regenerate or reject) |
| Accounts (6 Nov): Password and sign-in page (add a password to a Google-only account, change it with the current one, connect or disconnect Google, never leaving an account without a way in), "Forgot password?" email reset that also works for Google-only accounts (rate-limited, never reveals whether an address exists, links built from SITE_URL), security email after every password change; Google joins an existing account with the same verified email instead of creating a second one; times labelled EAT (server already Africa/Kampala); approving a topic starts preparing its family versions in the background (analyst still reviews and publishes) | ✅ 70 Django tests |
| Child versions owned by analysts, adapted by parents (6 Nov): approving a topic prepares the child lesson, quiz and practice message; sending the parents' campaign publishes them together (unless safety notes need a look); parents see the child version on the topic page, can reword the lesson and practice message for their own children (same safety screen, `ParentLessonEdit`), and analysts see every edit on Family versions and can undo it; children get the practice email and the lesson in My lessons, in their parent's wording when edited; a topic without a child version shows "Ask for the child version" beside sending (`ChildVersionRequest`, starts preparation, parent emailed when published); the email no longer carries a send button | ✅ 75 Django tests |
| Child version worked on inside the campaign (6 Nov): the campaign page shows the child lesson, quiz list and practice message with safety notes, inline editing, Regenerate and the parents' requests for that topic; creating a campaign (like approving) starts preparing the child version; "Send" waits until it exists (or "send without"), needs a tick when safety notes remain, then sends the parents' email and publishes the child version together; generator drops sentences that give the exercise away and unquoted red-flag excerpts, and keeps the SMS link | ✅ 79 Django tests |
| Dark-mode hover states (6 Nov) | ✅ no white hover fills in dark mode; active tabs keep white text on hover |
| Next | analyst families/children analytics · seed data (starter lessons) · §10.1 child lesson prompt · PDF/`.eml` uploads (§7.1) · scam waves + analyst workspace (§9) · reduce false alarms on official notices · §14.4 route choice for the mobile app |

### 15.2 Timeline from now (Thu 5 Nov ~16:30 → Fri 6 Nov 14:00)

| When | Focus (‖ = in parallel) | Exit criterion |
|---|---|---|
| Thu 17:00–19:00 | `guardian-ai` dev mode (Gemini Flash) + Django `ai_client`/`ai_health` (§6.9 A) ‖ Phase 1 cleanup, roles, models, migrations (§5) ‖ GPU machine: personal venv, model downloads, Help Desk questions (§4) | Smoke tests return `backend:"gemini"`; `manage.py check` clean; three roles log in |
| Thu 19:00–22:00 | Feature 1 pipeline (text/link/eml, then screenshot) + child/parent check screens ‖ seed data ‖ Feature 2 models, sender, token → learner session → `learn/` ‖ GPU machine: ONNX classifier + Qwen in Docker, tunnel (§6.9 B) | Child check returns a `cloud-dev` result; practice email → click → topic lesson + quiz recorded; `/classify` via tunnel shows the GPU host |
| Fri 08:30–11:30 | Switch Django to Testbed mode · parent composer (guideline + prompt topic) · report-by-upload match · analyst workspace + analytics · parent child-progress · eval runs on both backends | Full demo script (§16) runs end-to-end on Testbed mode, and still runs in dev mode as the fallback |
| Fri 11:30–14:00 | Evaluation page + `EVALUATION.md` + README + declarations + testbed evidence + video + pitch rehearsal | **14:00 code freeze** |

### 15.3 Team split (5 people)

1. **`guardian-ai` + GPU machine**: service in dev mode first, then Phase 0 and Testbed mode, evidence, `run_eval.py`.
2. **Detection in Django**: `safety` models, extract/redact/url/email checks, rules, fusion, scam waves, `ai_client`.
3. **Templates**: child + parent portals, porting from the prototype, accessibility on phones.
4. **Phishing simulation + library**: `phishsim` models, parent composer (`llm.py` with Gemini), sender, token learner
   sessions, `learn/` pages, tracking on `ChildProfile`, report matching, parent/analyst screens.
5. **Analyst workspace + evaluation + docs/pitch**: overview/threats/reports/evaluation, synthetic dataset,
   declarations, video, business model (20% of marks).

---

## 16. Acceptance tests

| # | Scenario | Expected |
|---|---|---|
| 1 | Child pastes a fake bursary-fee SMS with a lookalike link | High/Suspicious; signals include advance fee + brand/domain mismatch; source label "Live"; parent gets an alert with **no message text** |
| 2 | Parent uploads the same SMS | Parent-worded result; no child alert; analyst sees one sanitised record marked `parent` |
| 3 | Child uploads a screenshot mixing their own and the scammer's messages | Only the scammer text is analysed, or the child is asked which message they received |
| 4 | Child uploads an `.eml` with `Reply-To` mismatch and DMARC fail | Header signals shown in plain language; attachments listed, not opened |
| 5 | Upload of `.exe`/`.apk`/`.zip` or a renamed file with wrong magic bytes | Rejected with a friendly message; nothing stored |
| 6 | Genuine official-domain message | No unsupported high-risk claim; "Low observed risk", never "safe" |
| 7 | `guardian-ai` is down | "Unable to verify" plus safe advice; nothing fabricated |
| 7a | Django switched from dev mode (`:8000`, Gemini) to Testbed mode (tunnel `:8100`) and back | Same flows work; source label changes `cloud-dev` ↔ `live`; `meta.host`/`gpu` show the GPU machine in Testbed mode; `AuditEvent` records each call |
| 8 | After any upload | File absent from disk/media; only hash + sanitised text in DB |
| 9 | Pairing code reused, expired, or brute-forced | Rejected; rate limit hits after 10 attempts/hour |
| 10 | Parent consents → practice "win money" email sent → child clicks (not signed in, no app) | Redirects to the **prize/reward scams** library lesson with the practice banner and highlighted red flags; `clicked_at` + lesson view recorded against the `ChildProfile`; no credentials can be submitted |
| 10a | Child takes the linked quiz from the email link | Attempt and score saved on the `ChildProfile` + delivery; visible to the parent and in analyst analytics (pseudonymous); appears in the child's progress if they pair later |
| 10b | Parent writes a prompt topic in the composer | Email + lesson + quiz generated; parent previews the email and the linked lesson; sends to own child only |
| 10c | Parent prompt asks for a banned theme (threat, sextortion) or a real brand domain | Blocked at the safety screen with the reason |
| 10d | Child opens a practice link without the app or a password | Signed straight into their own child space and the topic lesson; cannot change email/password or open parent pages |
| 10e | Recipient clicks "This isn't me / stop" in the welcome notice | Address blocked; no practice emails are ever sent; the parent sees "blocked" |
| 11 | Child uploads the practice email to "Is this safe?" | Normal result + "Great catch" banner; `reported_at` set; excluded from threat intel |
| 12 | Parent revokes consent before the scheduled send | Delivery is `skipped_no_consent`; no email sent |
| 13 | Analyst opens simulation and learning analytics | Pseudonyms only, no nicknames or emails; aggregate groups under 5 suppressed |
| 14 | Child files a confidential report | No parent alert; analysts outside `Safeguarding` see "Restricted"; the view is audited |
| 15 | Child selects "Something happened" and mentions danger | Supportive message, Call 116 prominent, routed to Safeguarding; no automatic outside contact |
| 16 | Child/parent opens analyst URLs (or vice versa) | 403/redirect |

**Five-minute demo script:** (1) parent adds a child **by email only** → welcome notice arrives; (2) parent opens
**Create a practice email**, types the prompt topic "free airtime if you click this link", and previews the email and
the generated lesson → sends; (3) in the child's inbox (no app), click → the airtime/reward-scam library lesson with red
flags → quiz; (4) parent's child-progress shows the click, the lesson and the quiz score; (5) a second, paired child
checks a fake scholarship SMS → live Testbed result → parent alert; that child uploads another practice email → "Great
catch"; (6) analyst: scam wave, alleged impersonation, simulation + learning analytics (pseudonymous), evaluation with
FP/FN; (7) child "Something happened" → confidential → Call 116.

---

## 17. Submission checklist and declarations

- [ ] Repo accessible; README with architecture diagram, setup for laptop (dev mode) and GPU machine (Testbed mode),
      env vars, and the deviation note: Django instead of the PRD's Node/Express core API (Guardian already had
      PostgreSQL persistence, roles, permissions, an LLM wrapper, human approval, quizzes, analytics and reports).
- [ ] `docs/testbed-evidence/`: `nvidia-smi` output, `/health` + `/classify` + `/extract` responses with host, GPU and
      latency, `inference.jsonl` sample, `AuditEvent` export showing real inference calls during the demo.
- [ ] `docs/EVALUATION.md`: dataset, split, configurations (§11.3), metric tables, FP/FN examples, per-language
      notes, screenshot extraction check, limitations.
- [ ] Safety section (copy §13) and the privacy notice text shown in the app and in the welcome notice email.
- [ ] Three-minute demo video.
- [ ] **Declarations of third-party assets and AI tools:**

| Asset | Licence / terms | Use |
|---|---|---|
| Guardian codebase (team background IP) | team-owned | Core Django platform |
| Next.js prototype (team background IP) | team-owned | Design reference only, not deployed |
| Google Gemini API (Flash models) | Google API terms | Dev-mode inference (classify/extract/explain) on synthetic data; parent/analyst content generation |
| `masterburator3301/distilbert-spam-phishing-classification-onnx` | **not stated on model card**, declared, used for research/demo | Text classifier (Testbed) |
| `distilbert-base-uncased` (base) | Apache-2.0 | Tokenizer/base |
| Kaggle `zefang-liu/phishing-email-dataset` (training data of the above) | see dataset page | (indirect) |
| `Qwen/Qwen3-VL-2B-Instruct` (+ GGUF by ggml-org if used) | Apache-2.0 | Screenshot extraction, explanations (Testbed) |
| llama.cpp (Docker image, if used) | MIT | Model serving |
| `sentence-transformers/all-MiniLM-L6-v2` | Apache-2.0 | Scam-wave grouping |
| `pirocheto/phishing-url-detection` (dataset `pirocheto/phishing-url`) | MIT | URL phishing score |
| URLhaus / PhishTank / OpenPhish | per provider terms | Threat indicators |
| Django, DRF, FastAPI, onnxruntime, Transformers, scikit-learn, Tailwind… | respective OSS licences | Frameworks |
| AI coding assistants used by the team (e.g. Claude Code) | - | Code/documentation assistance |

---

## 18. Risks and open questions

| Risk / question | Response |
|---|---|
| Children need an email address for practice emails | The parent supplies it at "Add child". Children without one can still pair and use the in-app practice inbox (P1) |
| A parent enters someone else's email to send them fake phishing | Welcome notice with "This isn't me / stop", 5-address cap, monthly send cap, audit log |
| Parent-generated content reaches children with only the parent's review | Automatic safety screen + parent preview; analyst moderation queue can retire it; it stays family-only unless promoted |
| A child who never installed the app never saw the pairing "what your guardian can see" screen | The welcome notice and every practice-landing banner explain it in plain language |
| Gmail SMTP may flag deceptive display names or throttle | Demo with the console backend or a few test inboxes. In-app inbox as fallback. Keep volume tiny |
| Ethics review of simulating phishing to minors | §8.1 safeguards; state them in the pitch; mentor sign-off before any real-inbox send |
| Classifier trained on English emails, not Ugandan SMS | Rules + URL/email checks + fusion; report FP/FN honestly (§11.3) |
| Qwen on the GTX 1060 (Pascal: no bf16, no FlashAttention-2) | Verified fp16 works; use `float16` + `sdpa`; prefer llama.cpp GGUF via Docker (§4.6) |
| Scope: two features + three portals in two days | P0 list in §15.1 is the cut line. Everything else is labelled roadmap |
| Machine IP/name differs from the docs (`.11`, not `.232` Surface Studio 2) | Confirm with organisers before relying on it (§4.4) |
| Someone else's `~/chinga-ai` service runs on `127.0.0.1:18765` | Leave it alone; deploy to `~/guardian-ai` on `:8000`; ask who owns it |
| No sudo, no cmake/nvcc, no Docker GPU runtime on the GPU machine | pip into `~/venv`; Qwen via transformers (§4.6 B). llama.cpp only as a Windows binary after Help Desk approval |
| Only ~4.5 GB VRAM free (Windows desktop uses ~1.5 GB); apps opened on that desktop can push Qwen into OOM | `QWEN_HF_MAX_GPU_MEMORY` (4400MiB now; lower if OOM); images capped at 896 px; one request at a time; OOM returns `unavailable`, not a crash |
| Qwen3-VL-2B quality below Gemini (wrong quiz answers, weaker attribution) | Deterministic fusion decides risk; human review of all generated content; layout-aware extract prompt; evaluate it honestly (§11) |
| WSL port not reachable on the LAN | SSH tunnel `-L 8100:localhost:8000` (§4.7) |
| SSH lands in `cmd.exe` | Use `wsl` interactively or `ssh … "wsl -d Ubuntu-24.04 -- bash -s" < script` |
| Gemini quota / outage | Flash model fallbacks (429/503); Testbed backends; templated explanations; seeded pre-approved lessons |
| Cloud processing of child-like content in dev mode | Synthetic data only, redaction, `cloud-dev` label, switch before real users (§13.1 rule 5) |
| Event network down during the demo | Switch `GUARDIAN_AI_URL` back to the laptop's dev service; `unable_to_verify` path; recorded evidence video |
| No licence on the DistilBERT ONNX repo | Declare; ask the AI/ML mentor; any HF phishing model can be swapped in behind `/classify` |

**Open questions for the team**
1. Will real children's inboxes be used at the event, or only team-controlled test inboxes? Recommended: test
   inboxes only.
2. Should parent-generated lessons ever go into the shared library automatically? Recommended: no, analysts promote them
   by hand.
3. Should guest (logged-out) checks ship in P0? Recommended: P1.

---

## 19. Appendix

### 19.1 Environment variables

**Django (`pita/.env`)**
```
DATABASE_URL=postgresql://user:password@localhost:5432/guardian_db   # or sqlite:///db.sqlite3
DJANGO_SECRET_KEY=change-me
DEBUG=True
SITE_URL=http://localhost:8001
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
GUARDIAN_AI_URL=http://localhost:8100            # Testbed via tunnel (guardian-ai/scripts/tunnel.sh); :8000 for laptop dev mode
GUARDIAN_AI_TOKEN=                               # must match guardian-ai's GUARDIAN_AI_TOKEN
GUARDIAN_AI_TIMEOUT=30
GUARDIAN_AI_EXTRACT_TIMEOUT=120
GUARDIAN_AI_GENERATE_TIMEOUT=600                 # family versions are one long Qwen call
CLASSIFIER_THRESHOLD=0.5                         # replace with the tuned value (§11)
GUARDIAN_GEMINI_FALLBACK=False                   # declared cloud fallback only; off on the Testbed
GEMINI_API_KEY=                                  # used only when the fallback is on
GOOGLE_CLIENT_ID=                                # optional Google sign-in
GOOGLE_CLIENT_SECRET=
GUARDIAN_ANDROID_APP_URL=
GUARDIAN_SIM_DOMAIN=practice.guardian.local
GUARDIAN_SIM_MAX_PER_MONTH=2
GUARDIAN_SIM_QUIET_HOURS=21-7
GUARDIAN_MAX_CHILD_EMAILS_PER_PARENT=5
GUARDIAN_LEARNER_SESSION_DAYS=7
```

**guardian-ai, dev mode (laptop, `guardian-ai/.env`)**
```
CLASSIFY_BACKENDS=gemini
EXTRACT_BACKENDS=gemini
EXPLAIN_BACKENDS=gemini
ALLOW_CLOUD=true
ALLOW_CLOUD_IMAGES=true            # synthetic screenshots only
GEMINI_API_KEY=
GEMINI_MODELS=gemini-2.5-flash,gemini-2.5-flash-lite,gemini-3-flash-preview
GUARDIAN_AI_TOKEN=                 # optional on the laptop
```

**guardian-ai, Testbed mode (GPU machine, `~/guardian-ai/.env`)**
```
CLASSIFY_BACKENDS=onnx
CLASSIFY_URL_BACKENDS=url-onnx
EMBED_BACKENDS=minilm
EXTRACT_BACKENDS=qwen
EXPLAIN_BACKENDS=qwen
GENERATE_BACKENDS=qwen
ALLOW_CLOUD=false                  # true only if a declared Gemini fallback is wanted
CLASSIFIER_DIR=~/models/distilbert-phish
URL_CLASSIFIER_DIR=~/models/phishing-url
EMBED_MODEL_DIR=~/models/all-MiniLM-L6-v2
QWEN_BASE_URL=http://<windows-host-ip>:8081/v1   # llama.exe serve on Windows; ip route show default
QWEN_MODEL=qwen3-vl-2b
QWEN_API_KEY=<same key llama.exe was started with>
GUARDIAN_AI_TOKEN=<random, required>
```

### 19.2 Resulting repo layout

```
guardian-main/
├── plan.md                           ← this file (single plan)
├── guardian-ai/                      ← FastAPI inference service (laptop dev mode / GPU machine Testbed mode), §6
│   ├── guardian_ai/ main.py config.py chain.py redact.py images.py prompts.py evidence.py backends/
│   ├── eval/ uganda_synthetic_v1.csv run_eval.py results/
│   ├── tests/  requirements.txt  requirements-gpu.txt  .env.example  README.md
├── docs/ EVALUATION.md  testbed-evidence/  samples/ (synthetic screenshots and .eml files)
└── pita/
    ├── pita/ settings.py urls.py middleware.py              (vignette removed)
    ├── awarenessapp/                                        (roles, categories, library/quizzes, email)
    │   └── services/ llm.py transformation.py ingestion.py email_service.py file_validators.py ratelimit.py ai_client.py
    ├── safety/                                              (families, submissions, detection, reports, alerts, scam waves)
    │   ├── services/ analysis.py extract.py redact.py url_checks.py email_checks.py rules.py fuse.py campaigns.py alerts.py
    │   └── management/commands/ seed_guardian.py ingest_threat_feeds.py load_eval.py ai_health.py
    ├── phishsim/                                            (templates, campaigns, deliveries, composer, sender, matching)
    │   └── management/commands/ send_simulations.py
    └── templates/ child/ parent/ learn/ panel/ safety/ emails/
```

### 19.3 Command reference

```bash
# Laptop: dev mode
cd guardian-ai && . .venv/bin/activate && uvicorn guardian_ai.main:app --port 8000 --reload
cd pita && python manage.py runserver 0.0.0.0:8001
python manage.py ai_health

# Laptop: Testbed mode
ssh -i ~/.ssh/hackathon_ed25519 hackathon@137.63.190.11 \
    "wsl -d Ubuntu-24.04 -- bash /home/hackathon/guardian-ai/scripts/start_all.sh"   # add "restart" to restart both
bash guardian-ai/scripts/tunnel.sh       # localhost:8100 -> GPU 127.0.0.1:8000; GUARDIAN_AI_URL=http://localhost:8100
cd pita && python manage.py ai_health

# GPU machine (inside WSL)
tmux attach -t qwen   # llama.exe serve (Windows, Vulkan, :8081), started by start_all.sh (§4.6)
tmux attach -t ai     # guardian-ai uvicorn :8000
bash ~/guardian-ai/scripts/start_testbed.sh   # restart guardian-ai alone
/mnt/c/Windows/System32/nvidia-smi.exe
```
