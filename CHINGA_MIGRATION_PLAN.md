# Chinga on Guardian: Migration & Build Plan (Group 6, Track 4)

> **Superseded (2026-11-06).** This early draft has been merged into [plan.md](plan.md), which is the single
> authoritative plan. The product kept the name **Guardian**, and some details below (machine address, model
> serving) turned out to be wrong. Kept for history only.

> **Goal:** repurpose this Guardian codebase (Django cybersecurity-awareness platform for company staff) into the
> **core backend of Chinga**, a child-focused scam-prevention, awareness and reporting platform for Uganda, 
> for the **UCC Testbed Hackathon 2026 (5–6 Nov 2026), Track 4: AI for Child-Focused Cybersecurity and Online
> Fraud Prevention**.
>
> **Code freeze: Friday 6 Nov 2026, 14:00.** Everything below is ordered so that a demoable system exists at the
> end of every phase.

Related sources (outside this repo):

| Source | Path |
|---|---|
| Chinga prototype (Next.js frontend + Express mock API + PRD) | `/home/tinex/UICT/UCC_TEST_BED_HACKATHON/` |
| Chinga PRD v2 | `UCC_TEST_BED_HACKATHON/docs/Chinga_UCC_PRD_v2_Clean.pdf` |
| Participant Readiness Guide, Testbed docs, Workstation guide, SSH key | `/home/tinex/UICT/Group 6/` |

---

## Table of contents

1. [Context and constraints](#1-context-and-constraints)
2. [Target architecture](#2-target-architecture)
3. [What to keep, adapt and remove in Guardian](#3-what-to-keep-adapt-and-remove-in-guardian)
4. [Phase 0, Testbed (GPU) setup](#4-phase-0-testbed-gpu-setup)
5. [Phase 1, Clean Guardian (remove vignette, rename domain)](#5-phase-1-clean-guardian)
6. [Phase 2, New data model](#6-phase-2-new-data-model)
7. [Phase 3, The `chinga-ai` inference service on the Testbed](#7-phase-3-the-chinga-ai-inference-service)
8. [Phase 4, LLM provider layer (Qwen first, Gemini fallback)](#8-phase-4-llm-provider-layer)
9. [Phase 5, Analysis pipeline](#9-phase-5-analysis-pipeline)
10. [Phase 6, JSON API for the Chinga frontend](#10-phase-6-json-api-for-the-chinga-frontend)
11. [Phase 7, Repurpose awareness content, quizzes, campaigns, analytics](#11-phase-7-repurpose-awareness-features)
12. [Phase 8, Evaluation (mandatory FP/FN reporting)](#12-phase-8-evaluation)
13. [Phase 9, Connect the Chinga frontend](#13-phase-9-connect-the-chinga-frontend)
14. [Safety, privacy and safeguarding rules (non-negotiable)](#14-safety-privacy-and-safeguarding-rules)
15. [Timeline mapped to hackathon sprints](#15-timeline-mapped-to-hackathon-sprints)
16. [Submission checklist and declarations](#16-submission-checklist-and-declarations)
17. [Risks and fallbacks](#17-risks-and-fallbacks)
18. [Appendix, env vars, file tree, demo script](#18-appendix)

---

## 1. Context and constraints

### 1.1 Our assignment

| Item | Value |
|---|---|
| Group | **Group 6** |
| Track | **Track 4, AI for Child-Focused Cybersecurity and Online Fraud Prevention** |
| Workstation | **Microsoft Surface Studio 2**, address `137.63.190.232` |
| OS | Windows 11 Pro + **Ubuntu 24.04 in WSL 2** (run `wsl` after SSH login) |
| CPU / RAM | Intel i7-7820HQ (4 cores / 8 threads), 16 GB (**~10 GB available to Ubuntu**) |
| GPU | **NVIDIA GeForce GTX 10-series** (documented as **GTX 1060, 6 GB VRAM**, Pascal architecture, compute capability 6.1), reachable via SSH for our team |
| Account | `hackathon`, SSH key file `hackathon_ed25519` (password auth over network is disabled) |
| Shared Python env | `/opt/hackathon/venv` (Python 3.12, PyTorch, Transformers, FastAPI, Uvicorn, sentence-transformers, scikit-learn, OpenAI client, HF Hub client, Docker in WSL) |
| Network | Wi-Fi `RENU UCC HACKATHON 2026`, subnet `137.63.190.0/24` |

> Do **not** commit credentials, the SSH key, or the passwords from the Testbed documentation to this repository.

### 1.2 Track 4 recommended resources

- Threat intel / datasets: **PhishTank**, **URLhaus**, **OpenPhish** (access conditions apply), **UCI ML Repository**.
- Models: **Hugging Face phishing detection models**, **Hugging Face spam detection models**.

### 1.3 Our chosen models

| Model | Role in Chinga | Notes |
|---|---|---|
| [`masterburator3301/distilbert-spam-phishing-classification-onnx`](https://huggingface.co/masterburator3301/distilbert-spam-phishing-classification-onnx) | Primary **text classifier** (spam/phishing score) | Labels `0 = Non-Spam`, `1 = Spam`. Files: `text_classifier.onnx` (~267 MB), `tokenizer.json`, `tokenizer_config.json`, `vocab.txt`. Base `distilbert-base-uncased`, trained on Kaggle `zefang-liu/phishing-email-dataset` (**English emails**). Card reports 97% accuracy **on that dataset only**. **No licence stated** → must be declared. |
| [`Qwen/Qwen3-VL-2B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct) | **Vision-language model** for user inputs: screenshot text extraction, sender attribution, child-friendly explanations, later chat | Apache-2.0. ~2B params, `model.safetensors` ≈ 4.26 GB (bf16). Needs a recent `transformers` (card asks for ≥ 4.57 / from source). GGUF builds exist: `ggml-org/Qwen3-VL-2B-Instruct-GGUF`, `unsloth/...`, `bartowski/...`. |
| Google Gemini (already in Guardian, `google-genai`) | **Fallback** LLM, and admin-side content generation | Free tier, **never send raw child submissions or screenshots** (see §14). To be phased out for child-facing paths. |

### 1.4 What the judges score (Readiness Guide §8.1)

| # | Criterion | Weight | How this plan addresses it |
|---|---|---|---|
| 1 | Demonstrated use of the Testbed | 10% | `chinga-ai` service runs on the Surface; every inference logged with host/GPU/latency |
| 2 | Technical quality & completeness | 20% | Working API, failure handling (`unable_to_verify`), evaluation page with FP/FN |
| 3 | Relevance to theme/track | 15% | Phishing/scam detection, awareness, reporting for children |
| 4 | Safety by design, privacy, ethics | 15% | Redaction, no raw child data to cloud, confidential route, human-approved content |
| 5 | Innovation & originality | 10% | Screenshot extraction + classifier + rules fusion; campaign grouping; Guardian awareness engine for kids |
| 6 | Marketability / commercial viability | 20% | (pitch) schools, telcos, UCC; B2G/B2B2C model |
| 7 | Demo & pitch quality | 10% | Five-scene demo script (§18.3), honest limitations |

### 1.5 Mandatory deliverables (Guide §6.5)

Working prototype · source in an accessible repo · brief docs (architecture, setup, **evaluation incl. false
positives and false negatives**, **declarations of third-party assets and AI tools**) · 3-minute demo video · live demo + pitch.

---

## 2. Target architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ Chinga Next.js PWA  (UCC_TEST_BED_HACKATHON/frontend)                │
│   /child  /parent  /admin                                            │
└───────────────┬──────────────────────────────────────────────────────┘
                │ JSON over HTTP, envelope {ok, data, meta} / {ok:false, error}
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Guardian → "Chinga Core" (THIS REPO, Django 6 + DRF + PostgreSQL)    │
│   auth & roles · families / pairing · analysis orchestration         │
│   reports · campaigns · parent alerts · awareness content & quizzes  │
│   admin analytics · exports · audit log · evaluation results         │
│   Runs on: a team laptop (preferred) or the Surface                  │
└───────────────┬───────────────────────────────┬──────────────────────┘
                │ HTTP (event network)           │ fallback only, redacted text
                ▼                                ▼
┌───────────────────────────────────────┐   ┌───────────────────────────┐
│ chinga-ai  (FastAPI, Surface Studio 2, │   │ Gemini API (cloud)        │
│ WSL, GTX 10-series GPU)                │   │ admin content generation  │
│  POST /classify  DistilBERT ONNX (CPU) │   └───────────────────────────┘
│  POST /extract   Qwen3-VL screenshot   │
│  POST /explain   Qwen3-VL explanation  │
│  GET  /health    host, GPU, versions   │
│  Qwen served by llama-server (GGUF)    │
│  or transformers fp16 (fallback)       │
└───────────────────────────────────────┘
```

**Why Django instead of Chinga's Express mock:** Guardian already has PostgreSQL persistence, a custom user model
with roles, permission groups, rate limiting, an LLM wrapper, a human approval workflow, quizzes, analytics and
printable reports. Express has none of that. The Chinga PRD lists "Node.js/Express or NestJS" for the core API, so
this is a deliberate, **documented** deviation, mention it in the README.

**Why a separate AI service:** heavy ML dependencies stay off the web server; it is the clearest possible evidence
of Testbed use; it isolates the 10 GB RAM / 6 GB VRAM machine to inference only.

---

## 3. What to keep, adapt and remove in Guardian

### 3.1 Mapping table

| Guardian component (file) | Chinga equivalent | Action |
|---|---|---|
| `Users.ROLE_CHOICES` = staff / admin / superadmin (`awarenessapp/models.py`) | `child`, `guardian`, `analyst`, `safeguarding`, `superadmin` | **Adapt** |
| `Profile` (full_name, department, position, reports_to, staff_id, staff_category, employment_terms…) | `ChildProfile` (nickname + age band only), `GuardianProfile` (display name, phone) | **Replace**, employee PII conflicts with data minimisation |
| `INSIDER_THREAT_CHOICES` (compromised/negligent/malicious/third_party/all) | `SCAM_CATEGORY_CHOICES` (see §5.3) | **Replace values**, keep the constant name temporarily so the rest of the code keeps working |
| `ContentSource` + `services/ingestion.py` (URL/NVD/CISA, PDF, prompt) | Awareness content sources **and** threat-intel feed ingestion (URLhaus / PhishTank / OpenPhish) into `ThreatIndicator` | **Adapt**. Fetching *trusted feeds* is fine. **Never** call `fetch_url_source` / `requests.get` on links submitted by children |
| `services/transformation.py` (Gemini → title/risk/action/engagement_data, auto-quiz) | Child-friendly awareness lessons and quizzes ("Scam of the week: fake MTN reward") | **Reuse**; rewrite prompts for ages 10–17, Ugandan context; route through the new provider layer |
| `AwarenessContent.status` pending → approved → rejected → sent | Human review of every AI-generated lesson before children see it | **Keep** (pitch it as safety by design) |
| `Quiz`, `QuizQuestion`, `QuizChoice`, `QuizAttempt`, `QuizAttemptAnswer` | Child learning module | **Keep**; attempts linked to `ChildProfile`, not to a named identity |
| `EmailCampaign`, `EmailDelivery`, `services/email_service.py` | Guardian (parent) awareness digests + parent alert delivery channel | **Adapt** |
| `track_email_open` view + tracking pixel (`views.py:1400`, `email_service.py:74`) | - | **Remove**, no covert tracking of families |
| `UserContentInteraction` | Child "lessons read" progress | **Keep**, minimal fields |
| Panel analytics + `analytics_report` (printable) | UCC admin dashboard (overview, threats, campaigns, impersonated orgs) + PDF export | **Adapt** |
| `_rl()` fixed-window rate limiter | Rate-limit `/api/analysis`, pairing, reports | **Reuse** (move to `services/ratelimit.py`) |
| `_generate_with_retry()` (duplicated in `transformation.py` and `vignette/gemini.py`) | Single provider chain (`services/llm.py`) | **Replace** |
| `services/file_validators.py` | Screenshot upload validation | **Reuse** |
| `django-guardian` object permissions | Restrict confidential reports to the safeguarding role | **Reuse** |
| `django-allauth` Google login | Guardians only (optional) | **Keep** for guardians; children never need an email account |
| `vignette` app (clinical HIV case study), `VignetteParticipantMiddleware`, `handler404 = 'vignette.views.handler_404'`, `VIGNETTE_*` settings, `vignette` logger | - | **Remove completely** (§5.1) |
| `vercel.json`, `api/index.py`, `build_files.sh` | - | Keep but unused at the event; we run locally |
| Templates under `templates/staff/`, `templates/panel/` | Admin panel can keep Django templates; child/parent UI is the Chinga Next.js app | **Keep panel**, staff templates become optional |

### 3.2 Guiding rule

Guardian's pipeline was **raw intel → AI transform → human approval → delivery → analytics**.
Chinga adds a second, real-time pipeline: **child input → AI analysis → explanation → minimal evidence → campaign
intelligence → (maybe) parent alert**. Both share models, the LLM layer and the admin panel.

---

## 4. Phase 0: Testbed (GPU) setup

Do this **first** on Day 1; the GPU situation decides how Qwen is served.

### 4.1 SSH access from a laptop

```bash
mkdir -p ~/.ssh
cp "/home/tinex/UICT/Group 6/Surface studio 1/hackathon_ed25519" ~/.ssh/surface2_hackathon
chmod 600 ~/.ssh/surface2_hackathon

cat >> ~/.ssh/config <<'EOF'
Host surface2
    HostName 137.63.190.232
    User hackathon
    IdentityFile ~/.ssh/surface2_hackathon
    IdentitiesOnly yes
EOF

ssh surface2      # lands in a Windows shell
wsl               # enter Ubuntu 24.04, all work happens here
```

VS Code: install **Remote - SSH**, connect to `surface2`, then use the WSL indicator, interpreter
`/opt/hackathon/venv/bin/python` (or `~/venv/bin/python` below).

### 4.2 Personal virtual environment (allowed by the Workstation Guide §3.5)

```bash
python3 -m venv ~/venv
echo /opt/hackathon/venv/lib/python3.12/site-packages > ~/venv/lib/python3.12/site-packages/shared.pth
source ~/venv/bin/activate
pip install onnxruntime "huggingface_hub[cli]" pillow python-multipart
# Only if we must run Qwen via transformers:
# pip install -U "transformers>=4.57" accelerate
```

### 4.3 Verify the GPU properly (important for a GTX 10-series card)

```bash
nvidia-smi                                    # confirm exact model + free VRAM (expect ~6 GB)
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
python -c "import torch; print(torch.cuda.get_device_capability(0))"     # Pascal = (6, 1)
python -c "import torch; x=torch.ones(1024,1024,device='cuda',dtype=torch.float16); print((x@x).sum())"
```

Why the last line matters: recent PyTorch CUDA builds have **dropped Pascal (sm_61) kernels**. `is_available()`
can return `True` while the first real kernel fails with *"no kernel image is available for execution on the
device"*. Record the outcome, it decides §7.3.

| Result | Decision |
|---|---|
| fp16 matmul succeeds | Qwen via transformers fp16 is possible (Option B), but llama.cpp (Option A) is still lighter |
| Kernel error / not available | Use **llama.cpp (Option A)** compiled for the GPU, or CPU fallback |

GTX 10-series facts that shape every decision:
- **No bfloat16**, so ignore the model card's `torch.bfloat16` advice; use `float16`.
- **No FlashAttention-2** (needs Ampere+). Use `attn_implementation="sdpa"` (or `"eager"`).
- **6 GB VRAM**: Qwen3-VL-2B fp16 weights alone are ~4.3 GB; images add tokens → keep images small.
- **~10 GB RAM in WSL**: run only `chinga-ai` here; PostgreSQL + Django run on a laptop.

### 4.4 Ask the Help Desk before installing anything beyond pip

The code of conduct forbids *unauthorised software installation*. Ask on Day 1 morning:
1. May we build **llama.cpp** in our home directory (or run the `ghcr.io/ggml-org/llama.cpp` CUDA server image with
   Docker, which is installed in WSL)?
2. How do we expose a port from WSL to the event LAN (Windows `netsh interface portproxy` needs admin), or should we
   use an SSH tunnel instead?

**SSH tunnel fallback (needs no admin rights):**
```bash
# on the laptop running Django: make Surface's port 8000 (chinga-ai) appear as localhost:8000
ssh -N -L 8000:localhost:8000 surface2
```
(If the Windows OpenSSH session cannot reach WSL's localhost, run `chinga-ai` with `--host 0.0.0.0` inside WSL;
WSL 2 forwards localhost from Windows to WSL by default.)

### 4.5 Download the models (on the Surface, inside WSL)

```bash
source ~/venv/bin/activate
huggingface-cli download masterburator3301/distilbert-spam-phishing-classification-onnx \
  text_classifier.onnx tokenizer.json tokenizer_config.json vocab.txt --local-dir ~/models/distilbert-phish

# Option A (preferred on GTX 10-series): GGUF for llama.cpp: check the repo file list for exact names
huggingface-cli download ggml-org/Qwen3-VL-2B-Instruct-GGUF --local-dir ~/models/qwen3vl-gguf

# Option B (transformers): full weights, ~4.3 GB
# huggingface-cli download Qwen/Qwen3-VL-2B-Instruct --local-dir ~/models/qwen3vl-2b
```

Skip `saved_weights_distilbert4.pt`, the ONNX file is all we need.

---

## 5. Phase 1: Clean Guardian

Work on a branch: `git checkout -b chinga`.

### 5.1 Remove the vignette study completely

| File | Change |
|---|---|
| `pita/pita/settings.py` | Remove `'vignette'` from `INSTALLED_APPS`; remove `'pita.middleware.VignetteParticipantMiddleware'` from `MIDDLEWARE`; delete `VIGNETTE_URL_PREFIX`, `VIGNETTE_DONE_SLUG`, `VIGNETTE_RESEARCH_PREFIX`; delete the `'vignette'` logger and the line `LOGGING['loggers']['vignette']['handlers'].append('file')` |
| `pita/pita/urls.py` | Remove both `vignette` `path(...)` includes; change `handler404` to a new `awarenessapp.views.handler_404` (or delete the line to use Django's default) |
| `pita/pita/middleware.py` | Delete `VignetteParticipantMiddleware`; keep `SecurityHeadersMiddleware` |
| `pita/vignette/` | Delete the directory (its migrations go with it; on a fresh DB nothing else references them) |

Then:
```bash
cd pita
python manage.py check
```

### 5.2 Rename roles

`awarenessapp/models.py`:
```python
ROLE_CHOICES = (
    ('child', 'Child'),
    ('guardian', 'Parent / Guardian'),
    ('analyst', 'UCC Analyst'),          # was 'admin'
    ('safeguarding', 'Safeguarding Reviewer'),
    ('superadmin', 'Super Admin'),
)
```
`awarenessapp/signals.py` → `_ROLE_GROUPS = {'superadmin': 'Superadmins', 'analyst': 'Analysts',
'safeguarding': 'Safeguarding', 'guardian': 'Guardians', 'child': 'Children'}`; give `_ADMIN_CODENAMES` to
Analysts + Superadmins. Search `views.py` for every `role == 'admin'` / `role == 'staff'` check and update
(`grep -n "'admin'\|'staff'" awarenessapp/views.py`). Keep a small helper:

```python
# awarenessapp/permissions.py
PANEL_ROLES = {'analyst', 'superadmin'}
def is_panel_user(user): return user.is_authenticated and user.role in PANEL_ROLES
```

### 5.3 Replace threat categories

```python
SCAM_CATEGORY_CHOICES = [
    ('reward', 'Fake reward / prize'),
    ('advance_fee', 'Scholarship / bursary / advance fee'),
    ('otp_theft', 'OTP / PIN / account takeover'),
    ('phishing_link', 'Phishing link / fake login'),
    ('impersonation', 'Impersonation (school, brand, person)'),
    ('sextortion', 'Sextortion / threats'),           # route to safeguarding, never auto-share
    ('other', 'Other'),
    ('all', 'All Types'),
]
INSIDER_THREAT_CHOICES = SCAM_CATEGORY_CHOICES   # temporary alias so existing code keeps working
```
Update labels inside `transformation._build_prompt` (`threat_labels`) and panel templates that display the old names.

### 5.4 Strip employee PII from `Profile`

For the hackathon the simplest safe path is: **leave `Profile` for guardian/analyst accounts** but stop
collecting department/position/staff_id/reports_to in forms and templates (`navbar_base.html` profile modal,
`analytics_staff.html`). Children get the new `ChildProfile` (§6). If you prefer a clean break, drop the fields
in a migration, either way, no employee-style data about children.

### 5.5 Remove email open tracking

- Delete the `track/` URL include in `awarenessapp/urls.py` and the `track_email_open` view.
- In `email_service.py` stop building `tracking_url`; remove the pixel `<img>` from `templates/emails/awareness_email.html`.
- Delivery status stays (`pending/sent/failed`), that's delivery reliability, not surveillance.

### 5.6 Fresh database + settings

```bash
# laptop
createdb chinga_db                                  # or keep SQLite for speed: DATABASE_URL=sqlite:///db.sqlite3
cp pita/.env.example pita/.env                      # then edit (see §18.1)
cd pita && python manage.py makemigrations && python manage.py migrate
python manage.py createsuperuser
```

Settings additions:
```python
CORS_ALLOWED_ORIGINS += ['http://localhost:3000']   # Chinga Next.js dev server
CHINGA_AI_URL   = os.getenv('CHINGA_AI_URL', 'http://localhost:8000')
QWEN_BASE_URL   = os.getenv('QWEN_BASE_URL', 'http://localhost:8081/v1')
QWEN_MODEL      = os.getenv('QWEN_MODEL', 'qwen3-vl-2b')
CHINGA_DEMO_MODE = os.getenv('CHINGA_DEMO_MODE', 'False') == 'True'
CLASSIFIER_THRESHOLD = float(os.getenv('CLASSIFIER_THRESHOLD', '0.5'))   # tuned in §12
```

**Exit criterion:** `python manage.py check` clean; admin panel loads; no `vignette` references
(`grep -rn vignette pita/` returns nothing but migrations you deleted).

---

## 6. Phase 2: New data model

Create a new app to keep things tidy: `python manage.py startapp chinga` (add to `INSTALLED_APPS`).
Minimum entities (from PRD §18.2), trimmed for the hackathon:

```python
# chinga/models.py
import secrets, hashlib
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from awarenessapp.models import SCAM_CATEGORY_CHOICES

User = settings.AUTH_USER_MODEL
RISK_CHOICES = [('low', 'Low observed risk'), ('suspicious', 'Suspicious'),
                ('high', 'High risk'), ('unable_to_verify', 'Unable to verify')]
CHANNEL_CHOICES = [('app', 'App'), ('telegram', 'Telegram'), ('sms', 'SMS')]
AGE_BANDS = [('10-12', '10–12'), ('13-15', '13–15'), ('16-17', '16–17')]


class ChildProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='child_profile')     # null = guest/anonymous device
    nickname = models.CharField(max_length=40)                    # never a legal name
    age_band = models.CharField(max_length=5, choices=AGE_BANDS)
    district = models.CharField(max_length=60, blank=True)        # district only, for aggregates
    created_at = models.DateTimeField(auto_now_add=True)


class GuardianChildLink(models.Model):
    guardian = models.ForeignKey(User, on_delete=models.CASCADE, related_name='child_links')
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='guardian_links')
    linked_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    class Meta:
        unique_together = ('guardian', 'child')


class PairingCode(models.Model):
    guardian = models.ForeignKey(User, on_delete=models.CASCADE)
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE)   # profile the parent pre-created
    code_hash = models.CharField(max_length=64, unique=True)            # store only a hash
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def hash(code): return hashlib.sha256(code.upper().encode()).hexdigest()

    @classmethod
    def issue(cls, guardian, child, minutes=10):
        code = f"SAFE-{secrets.randbelow(10**4):04d}"
        cls.objects.create(guardian=guardian, child=child, code_hash=cls.hash(code),
                           expires_at=timezone.now() + timedelta(minutes=minutes))
        return code


class ImpersonatedOrganisation(models.Model):
    name = models.CharField(max_length=120, unique=True)
    sector = models.CharField(max_length=60, blank=True)
    official_domains = models.JSONField(default=list)     # e.g. ["mtn.co.ug"] for brand/domain mismatch
    # UI must always label this "alleged impersonation", never institutional fault


class Campaign(models.Model):
    STATUS = [('suspected', 'Suspected'), ('under_review', 'Under review'), ('confirmed', 'Confirmed'), ('closed', 'Closed')]
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=SCAM_CATEGORY_CHOICES)
    organisation = models.ForeignKey(ImpersonatedOrganisation, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS, default='suspected')
    centroid = models.JSONField(null=True, blank=True)    # mean embedding for similarity grouping
    first_observed = models.DateTimeField(auto_now_add=True)
    latest_observed = models.DateTimeField(auto_now=True)
    grouping_method = models.CharField(max_length=40, default='embedding_cosine')


class AnalysisRequest(models.Model):
    """One check by a child. Stores only sanitised scammer-supplied evidence."""
    child = models.ForeignKey(ChildProfile, null=True, blank=True, on_delete=models.SET_NULL)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='app')
    input_kind = models.CharField(max_length=12)                    # text | url | screenshot
    sanitised_text = models.TextField(blank=True)                   # redacted; never PINs/OTPs/names
    urls = models.JSONField(default=list)                           # stored as inert text
    content_hash = models.CharField(max_length=64, db_index=True)   # dedupe forwards
    risk_level = models.CharField(max_length=20, choices=RISK_CHOICES)
    category = models.CharField(max_length=20, choices=SCAM_CATEGORY_CHOICES, default='other')
    signals = models.JSONField(default=list)
    evidence_sources = models.JSONField(default=list)               # ["message-classifier","url-check",...]
    classifier_score = models.FloatField(null=True, blank=True)     # uncalibrated
    explanation = models.TextField(blank=True)
    recommended_actions = models.JSONField(default=list)
    mode = models.CharField(max_length=20, default='live')          # live | demo | unable_to_verify
    providers = models.JSONField(default=dict)                      # {"classifier":"chinga-ai@surface2","llm":"qwen-local"}
    latency_ms = models.IntegerField(null=True, blank=True)
    organisation = models.ForeignKey(ImpersonatedOrganisation, null=True, blank=True, on_delete=models.SET_NULL)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name='submissions')
    review_status = models.CharField(max_length=12, default='new')  # new|reviewing|reviewed|escalated
    district = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ThreatIndicator(models.Model):
    """Rows ingested from URLhaus / PhishTank / OpenPhish dumps. Looked up, never visited."""
    kind = models.CharField(max_length=10)                     # url | domain
    value = models.CharField(max_length=2048, db_index=True)
    source = models.CharField(max_length=30)                   # urlhaus | phishtank | openphish | manual
    first_seen = models.DateTimeField(null=True, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)


class IncidentReport(models.Model):
    STATUS = [('new', 'New'), ('priority_review', 'Priority review'), ('restricted', 'Restricted'), ('reviewed', 'Reviewed')]
    child = models.ForeignKey(ChildProfile, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=30)                 # money_sent | account_access | threat | suspicious_link
    summary = models.TextField()                               # child-reviewed, redacted
    confidential = models.BooleanField(default=False)          # suppresses guardian notification
    status = models.CharField(max_length=20, choices=STATUS, default='new')
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    analysis = models.ForeignKey(AnalysisRequest, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


class ParentAlert(models.Model):
    guardian = models.ForeignKey(User, on_delete=models.CASCADE, related_name='parent_alerts')
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE)
    severity = models.CharField(max_length=10)                 # high | suspicious
    title = models.CharField(max_length=160)                   # threat type only
    safety_action = models.CharField(max_length=300)           # what the parent can do
    delivery_state = models.CharField(max_length=12, default='in_app')   # in_app | emailed | sms_sent | failed
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # deliberately NO message text, NO screenshot, NO conversation


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)                   # inference.call, report.view, export.csv, status.change
    target = models.CharField(max_length=120, blank=True)
    detail = models.JSONField(default=dict)                    # host, gpu, model, latency, Testbed evidence
    at = models.DateTimeField(auto_now_add=True)


class EvaluationRun(models.Model):
    name = models.CharField(max_length=80)                     # classifier_only | rules_only | fused
    dataset = models.CharField(max_length=120)
    threshold = models.FloatField(null=True)
    metrics = models.JSONField()                               # precision, recall, f1, tp, fp, tn, fn, latency
    failure_examples = models.JSONField(default=list)          # synthetic examples only
    host = models.CharField(max_length=80)                     # e.g. surface2 / GTX 10-series
    created_at = models.DateTimeField(auto_now_add=True)
```

Register them in `chinga/admin.py` (Django admin gives you an instant back-office for the demo).

### 6.1 Seed data

Port the Chinga fixtures (`UCC_TEST_BED_HACKATHON/shared/index.js`: organisations, submissions, campaigns,
reports, alerts, parent children) into a management command `python manage.py seed_chinga`, so the dashboard looks
realistic even before live traffic. **All synthetic. Mark seeded rows `mode='demo'`.**

Seed `ImpersonatedOrganisation.official_domains`, e.g.
`MTN Uganda → ["mtn.co.ug"]`, `Airtel Uganda → ["airtel.co.ug"]`, `Makerere University → ["mak.ac.ug"]`,
`Centenary Bank → ["centenarybank.co.ug"]`, `UNICEF Uganda → ["unicef.org"]`. *(Verify each before relying on it.)*

---

## 7. Phase 3: The `chinga-ai` inference service

Create it as a sibling folder in this repo (`/home/tinex/UICT/guardian-main/chinga-ai/`) so it is versioned and
submitted, then `git pull` / `scp` it to the Surface.

```
chinga-ai/
├── app.py              # FastAPI app
├── classifier.py       # DistilBERT ONNX
├── vlm.py              # Qwen3-VL client (llama-server) or local transformers
├── prompts.py
├── requirements.txt    # onnxruntime, fastapi, uvicorn, transformers, huggingface_hub, pillow, python-multipart, openai
└── README.md
```

### 7.1 Classifier (CPU: fast, no GPU needed)

```python
# chinga-ai/classifier.py
import os, numpy as np, onnxruntime as ort
from transformers import AutoTokenizer

MODEL_DIR = os.path.expanduser(os.getenv('CLASSIFIER_DIR', '~/models/distilbert-phish'))
MODEL_ID = 'masterburator3301/distilbert-spam-phishing-classification-onnx'

tok = AutoTokenizer.from_pretrained(MODEL_DIR)
sess = ort.InferenceSession(f'{MODEL_DIR}/text_classifier.onnx', providers=['CPUExecutionProvider'])
INPUTS = {i.name for i in sess.get_inputs()}          # log once at startup; usually input_ids, attention_mask

def classify(text: str) -> dict:
    enc = tok(text, return_tensors='np', truncation=True, max_length=512, padding=True)
    feed = {k: v.astype(np.int64) for k, v in enc.items() if k in INPUTS}
    logits = sess.run(None, feed)[0][0]
    p = np.exp(logits - logits.max()); p /= p.sum()
    return {'spamScore': float(p[1]), 'label': int(p[1] >= 0.5),
            'model': MODEL_ID, 'calibrated': False}
```

At startup, print `sess.get_inputs()` / `sess.get_outputs()` names and shapes once to confirm the output is a
`(batch, 2)` logits tensor. If it is already probabilities, skip the softmax.

### 7.2 Qwen3-VL prompts (structured JSON only)

```python
# chinga-ai/prompts.py
EXTRACT = """You read screenshots of chats/SMS that a child received. Return ONLY JSON:
{"messages":[{"sender_role":"other|child|unclear","text":"..."}],
 "urls":["..."], "phone_numbers_present":true|false,
 "claimed_organisation":"name or null", "language":"en|lg|nyn|other"}
Rules: copy text exactly; do not judge safety; if you cannot tell who sent a message use "unclear";
never describe people's faces or bodies."""

EXPLAIN = """You explain scam-check results to a Ugandan child aged {age_band}.
Use ONLY the evidence below. Do not add new facts. Never say something is 100% safe.
Return ONLY JSON: {{"explanation":"2-3 short sentences","recommendedActions":["...","...","..."]}}
Risk level (already decided, do not change): {risk_level}
Evidence: {signals}"""
```

### 7.3 Serving Qwen on the GTX 10-series: choose one

**Option A, llama.cpp `llama-server` with GGUF (preferred).**
Quantised Q4_K_M weights + `mmproj` vision projector ≈ 2 GB VRAM total; llama.cpp can be compiled for Pascal; it
exposes an **OpenAI-compatible** `/v1/chat/completions`, so both `chinga-ai` *and* Django can call it with the
`openai` client already installed on the Testbed.

```bash
# in tmux on the Surface (after Help Desk approval)
tmux new -s qwen
llama-server -hf ggml-org/Qwen3-VL-2B-Instruct-GGUF:Q4_K_M \
  --host 0.0.0.0 --port 8081 -ngl 99 -c 4096 --alias qwen3-vl-2b
# Ctrl+B then D to detach; tmux attach -t qwen to return
```

```python
# chinga-ai/vlm.py (Option A)
import base64, json, os
from openai import OpenAI
client = OpenAI(base_url=os.getenv('QWEN_BASE_URL', 'http://localhost:8081/v1'), api_key='none')
MODEL = os.getenv('QWEN_MODEL', 'qwen3-vl-2b')

def _chat(content, max_tokens=512):
    r = client.chat.completions.create(model=MODEL, temperature=0.1, max_tokens=max_tokens,
                                       messages=[{'role': 'user', 'content': content}])
    return json.loads(r.choices[0].message.content.strip().removeprefix('```json').removesuffix('```'))

def extract(image_bytes: bytes, mime: str, prompt: str):
    b64 = base64.b64encode(image_bytes).decode()
    return _chat([{'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}},
                  {'type': 'text', 'text': prompt}])

def explain(prompt: str):
    return _chat([{'type': 'text', 'text': prompt}], max_tokens=300)
```

**Option B, transformers fp16 (if llama.cpp is not allowed and the fp16 test in §4.3 passed).**

```python
import torch
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
PATH = os.path.expanduser('~/models/qwen3vl-2b')
model = Qwen3VLForConditionalGeneration.from_pretrained(
    PATH, dtype=torch.float16, attn_implementation='sdpa', device_map='cuda:0')   # NO bf16, NO flash-attn on GTX 10
processor = AutoProcessor.from_pretrained(PATH, min_pixels=256*28*28, max_pixels=768*28*28)  # cap image tokens for 6 GB
# then follow the model card: processor.apply_chat_template(messages, tokenize=True,
#   add_generation_prompt=True, return_dict=True, return_tensors='pt') → model.generate(max_new_tokens=384)
```
Watch `nvtop`; if OOM, lower `max_pixels`, `max_new_tokens`, or drop to CPU (`device_map='cpu'`, fp32) and label
screenshot analysis as slow in the demo.

**Option C, CPU only.** Works, but expect tens of seconds per screenshot on 4 cores. Acceptable for a labelled
demo; text-only checks remain fast because the classifier is CPU anyway.

### 7.4 FastAPI app

```python
# chinga-ai/app.py
import platform, socket, time, subprocess
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import classifier, vlm, prompts

app = FastAPI(title='chinga-ai')
MAX_IMG = 5 * 1024 * 1024
ALLOWED = {'image/png', 'image/jpeg', 'image/webp'}

def _gpu():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.total',
                               '--format=csv,noheader'], capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return 'unavailable'

def _meta(t0):  # attached to every response, this is our Testbed evidence
    return {'host': socket.gethostname(), 'gpu': _gpu(), 'latencyMs': int((time.time() - t0) * 1000)}

class TextIn(BaseModel):
    text: str

class ExplainIn(BaseModel):
    riskLevel: str
    signals: list[str]
    ageBand: str = '13-15'

@app.get('/health')
def health():
    return {'status': 'ready', 'host': socket.gethostname(), 'python': platform.python_version(), 'gpu': _gpu()}

@app.post('/classify')
def classify(body: TextIn):
    t0 = time.time()
    if not body.text.strip():
        raise HTTPException(400, 'empty text')
    return {**classifier.classify(body.text), **_meta(t0)}

@app.post('/extract')
async def extract(file: UploadFile = File(...)):
    t0 = time.time()
    if file.content_type not in ALLOWED:
        raise HTTPException(415, 'PNG, JPEG or WebP only')
    data = await file.read()
    if len(data) > MAX_IMG:
        raise HTTPException(413, 'max 5 MB')
    try:
        result = vlm.extract(data, file.content_type, prompts.EXTRACT)
    except Exception as e:
        return {'status': 'unavailable', 'reason': type(e).__name__, **_meta(t0)}
    return {'status': 'ok', **result, **_meta(t0)}   # image is never written to disk

@app.post('/explain')
def explain(body: ExplainIn):
    t0 = time.time()
    try:
        out = vlm.explain(prompts.EXPLAIN.format(age_band=body.ageBand, risk_level=body.riskLevel,
                                                  signals='; '.join(body.signals)))
    except Exception as e:
        return {'status': 'unavailable', 'reason': type(e).__name__, **_meta(t0)}
    return {'status': 'ok', **out, **_meta(t0)}
```

Run:
```bash
tmux new -s ai
cd ~/chinga-ai && source ~/venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000
# test from laptop (directly or via the SSH tunnel)
curl -s http://137.63.190.232:8000/health
curl -s -X POST http://137.63.190.232:8000/classify -H 'Content-Type: application/json' \
  -d '{"text":"Congratulations! You won UGX 500,000. Send your Mobile Money PIN to claim."}'
```

Save these curl outputs + `nvidia-smi` screenshots into `docs/testbed-evidence/`, judges want *test evidence*.

---

## 8. Phase 4: LLM provider layer

Replace both `_generate_with_retry()` copies with one module. Gemini exposes an OpenAI-compatible endpoint, so a
single client library covers both providers.

```python
# awarenessapp/services/llm.py
import logging, time
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)
GEMINI_OPENAI_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/'
GEMINI_MODELS = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']

def _providers(allow_cloud: bool):
    yield 'qwen-local', OpenAI(base_url=settings.QWEN_BASE_URL, api_key='none', timeout=90), settings.QWEN_MODEL
    if allow_cloud and settings.GEMINI_API_KEY:
        client = OpenAI(base_url=GEMINI_OPENAI_URL, api_key=settings.GEMINI_API_KEY, timeout=60)
        for m in GEMINI_MODELS:
            yield f'gemini:{m}', client, m

def chat(messages, *, allow_cloud=False, **kwargs) -> tuple[str, str, int]:
    """Return (provider_name, text, latency_ms). allow_cloud=False for anything containing child input."""
    last = None
    for name, client, model in _providers(allow_cloud):
        t0 = time.time()
        try:
            r = client.chat.completions.create(model=model, messages=messages, **kwargs)
            return name, r.choices[0].message.content, int((time.time() - t0) * 1000)
        except Exception as e:
            logger.warning('LLM provider %s failed: %s', name, e)
            last = e
    raise last or RuntimeError('no LLM provider configured')
```

Then in `transformation.py`:
- delete `_MODEL`, `_FALLBACKS`, `_generate_with_retry`;
- in `transform_raw_content` replace the Gemini block with
  `provider, text, _ = chat([{'role':'user','content':_build_prompt(raw)}], allow_cloud=True, temperature=0.4)`;
- keep the markdown-fence stripping and `json.loads`;
- store `provider` on `AwarenessContent.admin_notes` (or add a `generated_by` field).

**Rule:** `allow_cloud=True` only for admin-side generation from curated/synthetic sources. Child-facing analysis
calls `chinga-ai` (Qwen local) and, if it is down, falls back to **templated text**, not Gemini (or Gemini on
already-redacted, de-identified text only, decide as a team and document it).

Remove `google-genai` from `requirements.txt` only after nothing imports it.

---

## 9. Phase 5: Analysis pipeline

`chinga/services/analysis.py` orchestrates everything. Pseudocode with the real decisions:

```python
def analyse(*, text=None, image=None, child=None, channel='app') -> AnalysisRequest:
    t0 = time.time(); signals, sources, providers = [], [], {}

    # 1. Screenshot → text (Qwen on Testbed). Image is discarded after this call.
    if image:
        ex = ai_client.extract(image)                      # POST CHINGA_AI_URL/extract
        if ex['status'] != 'ok':
            return _unable(child, 'Screenshot could not be read right now.')
        if any(m['sender_role'] == 'unclear' for m in ex['messages']):
            return _clarify(child, ex)                     # ask child which message they received
        text = '\n'.join(m['text'] for m in ex['messages'] if m['sender_role'] == 'other')
        providers['extract'] = ex['host']; sources.append('screenshot-extraction')

    # 2. Redact before storing or forwarding anywhere
    clean = redact(text)            # mask 4–6 digit codes, PIN/OTP values, phone numbers, emails, names after "Dear"

    # 3. URL checks: parse only, NEVER fetch
    urls = extract_urls(clean)
    for u in urls:
        signals += url_signals(u)   # punycode/xn--, digit-letter swaps (0/o, 1/l), many subdomains, IP host,
                                    # URL shorteners, brand-in-subdomain, TLD oddities
        if ThreatIndicator.objects.filter(value__in=[u, host(u)]).exists():
            signals.append('Known malicious link (threat-intelligence match)'); sources.append('threat-intel')
    org = claimed_org(clean)        # match ImpersonatedOrganisation names/aliases
    if org and urls and not any(host(u).endswith(d) for u in urls for d in org.official_domains):
        signals.append(f'Link does not belong to {org.name}\'s official website'); sources.append('brand-domain-check')

    # 4. Classifier on the Testbed
    cl = ai_client.classify(clean)                          # POST CHINGA_AI_URL/classify
    providers['classifier'] = cl.get('host'); sources.append('message-classifier')

    # 5. Rules (Uganda-specific)
    rule_hits = rules(clean)        # PIN/OTP/password request, advance/processing fee, prize/reward,
                                    # urgency/deadline, "keep this secret", MoMo transfer request, threats

    # 6. Deterministic fusion: the LLM never sets the risk level
    risk = fuse(cl['spamScore'], rule_hits, signals)
    #   known-bad URL OR credential request (PIN/OTP/password)          -> 'high'
    #   score >= THRESHOLD and >=1 rule hit, or brand/domain mismatch   -> 'suspicious' (or 'high' if 2+ strong)
    #   score >= THRESHOLD and no rule/url evidence                     -> 'suspicious' + needsHumanReview
    #   score < THRESHOLD and no evidence                               -> 'low'  ("low observed risk", never "safe")
    #   classifier unavailable and no rule evidence                     -> 'unable_to_verify'
    category = categorise(rule_hits, signals)

    # 7. Explanation (Qwen local), fallback to templates
    exp = ai_client.explain(risk, signals + rule_hits, child.age_band if child else '13-15')
    if exp.get('status') != 'ok':
        exp = TEMPLATES[risk]

    # 8. Persist minimal evidence, dedupe, group into campaign
    rec = AnalysisRequest.objects.create(..., sanitised_text=clean, content_hash=sha256(normalise(clean)), ...)
    if risk in ('suspicious', 'high'):
        assign_campaign(rec)        # sentence-transformers embedding, cosine >= 0.80 to campaign centroid else new
    AuditEvent.objects.create(action='inference.call', detail={'providers': providers, 'latency_ms': ...})

    # 9. Parent alert: only high risk, paired child, NOT from a confidential flow
    if risk == 'high' and child:
        for link in child.guardian_links.filter(active=True):
            ParentAlert.objects.create(guardian=link.guardian, child=child, severity='high',
                                       title=CATEGORY_TITLES[category], safety_action=PARENT_ACTION[category])
    return rec
```

Notes:
- **Campaign grouping:** `sentence-transformers/all-MiniLM-L6-v2` (sentence-transformers is preinstalled; the model
  itself is a small download) on CPU. Same `content_hash` = duplicate forward → count once (PRD §11: distinguish
  submissions from unique incidents). Label the method on the dashboard: *"Suspected campaign, embedding similarity
  ≥ 0.80; not confirmed"*.
- **Ingesting threat intel:** add a management command `python manage.py ingest_threat_feeds` that downloads
  URLhaus's public CSV/text dumps (check its terms), and PhishTank/OpenPhish only per their access conditions. Run it
  on the laptop; store in `ThreatIndicator`. This replaces Guardian's NVD/CISA ingestion for the security path.
- **Self-harm / abuse keywords** in reports or chat → do **not** classify automatically; show the 116 support path
  and route to the safeguarding role (PRD §7.3).

---

## 10. Phase 6: JSON API for the Chinga frontend

Use DRF (already installed). Keep the exact envelope the Next.js app expects:

```python
# chinga/api.py
from rest_framework.response import Response
def ok(data, status=200, **meta):
    return Response({'ok': True, 'data': data, 'meta': {'mode': 'live', **meta}}, status=status)
def fail(code, message, status=400):
    return Response({'ok': False, 'error': {'code': code, 'message': message}}, status=status)
```

Mount under `/api/` in `pita/pita/urls.py`: `path('api/', include('chinga.urls'))`.

### 10.1 Endpoint list

| Method & path | Role | Purpose | Priority |
|---|---|---|---|
| `GET /api/health` | any | Django + DB status + `chinga-ai` `/health` passthrough (host, GPU) | P0 |
| `POST /api/analysis` | guest/child | Body `{content}` (text/URL) → decision contract | **P0** |
| `POST /api/analysis/screenshot` | guest/child | multipart `file` (PNG/JPEG/WebP ≤ 5 MB) → decision contract | **P0** |
| `GET /api/analysis/history` | child | Own recent checks (label + result only) | P1 |
| `POST /api/reports` | guest/child | `{category, summary, confidential, analysisId?}` → saved `IncidentReport`; response says *not* sent to UCC/Police | **P0** |
| `GET /api/reports/<id>` | child (owner) | Status of own report | P1 |
| `GET /api/safety/resources` | any | Sauti 116 + approved helplines (client opens `tel:116`) | **P0** |
| `POST /api/families/children` | guardian | Create `ChildProfile` (nickname, age band) | **P0** |
| `GET /api/families/children` | guardian | Linked children, paired state | **P0** |
| `POST /api/families/pairing-codes` | guardian | `{childId}` → one-time code, 10-min expiry | **P0** |
| `POST /api/children/pair` | child device | `{code}` → validates hash, unused, unexpired → creates `GuardianChildLink` | **P0** |
| `GET /api/children/me/visibility` | child | What the guardian can and cannot see | P1 |
| `GET /api/parent/alerts` | guardian | Own `ParentAlert`s (no message content) | **P0** |
| `PATCH /api/parent/alerts/<id>` | guardian | Mark read | P1 |
| `GET/PUT /api/parent/preferences` | guardian | Notify on high / suspicious, SMS on/off | P1 |
| `POST /api/parent/advisor` | guardian | Parent AI advice chat (Qwen; no access to child data) | P1 |
| `GET /api/admin/overview?days=7` | analyst | KPIs, trend, recent threats, top impersonated orgs | **P0** |
| `GET /api/admin/incidents` (+ `?risk=&channel=&district=&q=`) | analyst | Sanitised `AnalysisRequest`s | **P0** |
| `GET/PATCH /api/admin/incidents/<id>` | analyst | Detail; status `new/reviewing/reviewed/escalated` (audited) | **P0** |
| `GET /api/admin/campaigns`, `GET /api/admin/campaigns/<id>` | analyst | Suspected campaigns + linked evidence | **P0** |
| `GET /api/admin/organisations` | analyst | Alleged impersonations with counts + disclaimer | **P0** |
| `GET /api/admin/reports`, `PATCH /api/admin/reports/<id>` | analyst / safeguarding | Confidential reports show restricted summary unless safeguarding role | **P0** |
| `GET /api/admin/alerts` | analyst | System/campaign/review feed | P1 |
| `GET /api/admin/evaluation` | analyst | Latest `EvaluationRun`s | **P0** |
| `POST /api/admin/exports` | analyst | CSV of sanitised intel; writes `AuditEvent` | P1 |
| `POST /api/integrations/telegram/webhook` | Telegram | Normalise → `analyse(channel='telegram')` | P1/P2 |
| `POST /api/integrations/sms/webhook` | Africa's Talking | Normalise → `analyse(channel='sms')` | P2 |

### 10.2 Decision contract returned by `/api/analysis*`

```json
{
  "ok": true,
  "data": {
    "analysisId": "AR-1042",
    "mode": "live",
    "riskLevel": "high",
    "category": "otp_theft",
    "signals": ["Asks for a one-time security code", "Pretends to be bank support"],
    "evidenceSources": ["message-classifier", "rules", "brand-domain-check"],
    "classifierScore": 0.93,
    "classifierScoreLabel": "uncalibrated model score",
    "explanation": "Be careful. Real bank staff never ask for your code…",
    "recommendedActions": ["Do not share the code.", "Block the sender.", "Tell a trusted adult."],
    "needsHumanReview": false,
    "impersonatedOrganisation": "Centenary Bank",
    "relatedCampaignId": "CMP-7"
  },
  "meta": { "mode": "live", "inference": { "host": "surface2", "gpu": "GeForce GTX 10xx", "latencyMs": 412 } }
}
```

`riskLevel` ∈ `low | suspicious | high | unable_to_verify` (Chinga frontend currently uses `unknown`, map
`unable_to_verify` → show "Unable to verify").

### 10.3 Auth for the demo

- Guardians/analysts: existing session login (`login_user`), for the SPA either use DRF `TokenAuthentication`
  (add `rest_framework.authtoken`) or session + CSRF cookie (`get_csrf_token` view already exists).
- Children: anonymous device token issued on pairing (store a random token on `ChildProfile`, send as
  `Authorization: Bearer …`). Guest checks work without any token.
- Rate-limit `/api/analysis*` per IP/device with the existing `_rl()` helper (e.g. 30/hour) and `/api/children/pair`
  (e.g. 10/hour) to stop code brute-forcing.

---

## 11. Phase 7: Repurpose awareness features

This is Guardian's strength and directly matches Track 4's "awareness" focus.

1. **Sources:** an analyst picks a confirmed/suspected `Campaign` (or uploads a PDF from UCC, or types a prompt)
   → existing `ContentSource` → `RawContent`.
2. **Transform:** rewrite `_build_prompt` for children:
   - audience: Ugandan children 10–12 / 13–15 / 16–17 (store age band on the content);
   - plain English, short sentences, local examples (MoMo, school bursaries, data bundles);
   - engagement types: keep `quiz`, `scenario` ("What would you do?"), `article`; **drop `policy`** (GRC
     frameworks are for employees) or repurpose it into "Family rule of the week" for guardians;
   - `link` engagement must only use pre-approved resources (UCC, Sauti 116), never model-invented URLs.
3. **Review:** keep pending → approved. Nothing AI-generated reaches a child unapproved.
4. **Deliver:**
   - children: approved lessons/quizzes appear in the child app (new endpoints `GET /api/learn`, `GET /api/learn/<id>`,
     `POST /api/learn/quizzes/<id>/attempts`), reuse the existing quiz models/scoring;
   - guardians: weekly email digest via `EmailCampaign` (no tracking pixel).
5. **Analytics:** reuse the panel analytics for quiz performance by age band and category, evidence of awareness
   impact for the pitch.

---

## 12. Phase 8: Evaluation

Mandatory per Guide §6.2: *"detection or classification solutions must define their evaluation method and report
performance metrics, including false positives and false negatives."*

### 12.1 Synthetic Ugandan test set

`chinga-ai/eval/uganda_synthetic_v1.csv` with columns `id,text,label,category,language,source`:
- ~150–300 rows, roughly balanced scam / legitimate;
- scams: MoMo reward, bursary/scholarship fee, OTP/PIN theft, fake Airtel/MTN data promos, impersonated teacher/
  headmaster, fake job, lookalike links (`mtn-ug.example`, `airteI.example` with capital I), sextortion-style threat
  *phrasing only* (no imagery);
- legitimate (crucial for false positives): real-style MTN/Airtel promos with official short codes, school fee
  reminders, parent messages, bank transaction notifications without requests, exam results notices;
- a handful in **Luganda** and **Runyankole** if a teammate can write them, report them separately and honestly;
- **no real messages from minors, no real phone numbers** (Guide §6.3).
- Split: `dev` (threshold tuning) and `test` (reported numbers), never tune on `test`.

### 12.2 Script

```python
# chinga-ai/eval/run_eval.py: run ON THE SURFACE so the evidence shows Testbed use
import csv, json, socket, time, sys
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
sys.path.insert(0, '..'); import classifier

rows = [r for r in csv.DictReader(open('uganda_synthetic_v1.csv')) if r['split'] == 'test']
y = [int(r['label']) for r in rows]
t0 = time.time(); scores = [classifier.classify(r['text'])['spamScore'] for r in rows]
lat = (time.time() - t0) / len(rows) * 1000
for thr in (0.5, float(sys.argv[1]) if len(sys.argv) > 1 else 0.5):
    pred = [int(s >= thr) for s in scores]
    p, r, f, _ = precision_recall_fscore_support(y, pred, average='binary', zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    fails = [{'id': x['id'], 'text': x['text'], 'gold': g, 'score': round(s, 3)}
             for x, g, s, pr in zip(rows, y, scores, pred) if g != pr][:15]
    print(json.dumps({'name': 'classifier_only', 'threshold': thr, 'host': socket.gethostname(),
                      'metrics': {'precision': p, 'recall': r, 'f1': f, 'tp': int(tp), 'fp': int(fp),
                                  'tn': int(tn), 'fn': int(fn), 'avg_latency_ms': lat},
                      'failure_examples': fails}, indent=2))
```

### 12.3 What to report (three configurations)

| Configuration | Why |
|---|---|
| `classifier_only` (DistilBERT ONNX) | Baseline of the pretrained model on *our* domain |
| `rules_only` | Shows what deterministic Uganda-specific rules catch |
| `fused` (full `/api/analysis` pipeline) | The actual product |

For each: precision, recall, F1, TP/FP/TN/FN, per-category and per-language breakdown, average latency, 10–15
failure examples with a one-line reason. Load the JSON into `EvaluationRun` (`python manage.py load_eval file.json`)
and show it on `/api/admin/evaluation` + an admin panel page.

**Expected honest finding to present:** the classifier was trained on English *emails*; short SMS-style Ugandan
scams and legitimate telco promos will cause errors. Show how the rules + URL checks + fusion change FP/FN.
Separately measure Qwen extraction on ~20 synthetic screenshots (did it extract the scam text correctly? sender
attribution correct?). Do **not** invent metrics.

---

## 13. Phase 9: Connect the Chinga frontend

In `/home/tinex/UICT/UCC_TEST_BED_HACKATHON`:

1. `.env`: `NEXT_PUBLIC_API_URL=http://localhost:8001` (run Django on 8001 so it does not clash with `chinga-ai` on
   8000 when tunnelled): `python manage.py runserver 0.0.0.0:8001`.
2. `frontend/components/child/ChildExperience.jsx`: change `/api/demo/analyse` → `/api/analysis`; add screenshot
   upload → `/api/analysis/screenshot` (`FormData`); keep `/api/reports`.
3. `frontend/components/parent/ParentExperience.jsx`: replace `@chinga/demo-data` imports with fetches to
   `/api/families/children`, `/api/parent/alerts`, `/api/families/pairing-codes`.
4. `frontend/components/admin/AdminDashboard.jsx`: replace `@chinga/demo-data` with `/api/admin/*` fetches.
5. Child "Family" screen: `POST /api/children/pair` with the code.
6. The old Express backend (`UCC_TEST_BED_HACKATHON/backend`) can remain as an offline demo fallback; label it.

---

## 14. Safety, privacy and safeguarding rules

These are scored (15%) and required by the Data Protection and Privacy Act Cap. 97, Computer Misuse Act, National
Child Policy, ITU COP Guidelines, UNCRC.

1. **Synthetic data only.** No real children, real child images, real phone numbers or real CSAM, ever.
2. **Never fetch user-submitted URLs** (no previews, no server-side visits). URLs are stored and shown as inert text.
3. **Discard screenshots** after extraction; store only redacted scammer text.
4. **Redact** PINs, OTPs, passwords, phone numbers, names before storage and before any LLM call that leaves the Testbed.
5. **No raw child input to Gemini / any cloud LLM.** Local Qwen on the Testbed for child-facing inference.
6. **The LLM never decides risk.** Deterministic fusion decides; the LLM explains evidence only. Disagreement → `unable_to_verify`.
7. **Never say "100% safe".** Use "Low observed risk".
8. **Parents get minimum context** (threat type, action, time), no message text, no screenshots, no chat logs.
9. **Confidential reports** never notify guardians; visible only to the safeguarding role (django-guardian object permissions).
10. **Self-harm / abuse / imminent danger** → empathetic response, Call 116, safe-adult guidance, human safeguarding
    review. No automated police/helpline contact.
11. **Impersonated organisations** are always labelled *alleged impersonation*, never culprits or breached parties.
12. **Report submissions** must state they were **not** sent to UCC, Police or 116 unless a real integration confirms receipt.
13. **No tracking pixels**, no browsing-history collection, no hidden monitoring.
14. **Human approval** for every AI-generated awareness lesson before children see it.
15. **Audit log** for status changes, restricted-evidence views, exports and every inference call.
16. **Label every result** `live`, `demo` (fixture) or `unable_to_verify`.

---

## 15. Timeline mapped to hackathon sprints

| When | Sprint | Tasks | Exit criterion |
|---|---|---|---|
| **Thu 5 Nov 10:00–14:00** | Sprint 1 | §4 Testbed setup + GPU test + Help Desk questions · download models · `chinga-ai /classify` + `/health` reachable from laptop · §5 Clean Guardian (in parallel by another member) | `curl …/classify` returns a score with `host`; `manage.py check` clean |
| **Thu 14:00–17:00** | Sprint 2 | §6 models + migrations + seed · §9 analysis pipeline (text path) · §10 P0 endpoints (`analysis`, `reports`, `pairing`, `parent/alerts`, `admin/*`) · start synthetic dataset (§12.1) | Chinga child page gets a **live** result from Django → Testbed |
| **Thu 17:30–20:00** | Extended | Qwen via llama-server (or Option B/C) · `/extract`, `/explain` · screenshot endpoint · first `run_eval.py` on Surface | Screenshot of a synthetic scam returns extracted text + risk |
| **Fri 6 Nov 08:30–11:30** | Sprint 3 (integration) | Frontend wired to API (§13) · parent alert end-to-end · campaign grouping · awareness lesson generated + approved (§11) · threat-feed ingestion | Five demo scenes run end-to-end |
| **Fri 11:30–14:00** | Sprint 4 (final) | Evaluation page + numbers in README · testbed evidence folder · declarations · 3-min video · rehearse pitch | **14:00 code freeze**, push repo |

Suggested split for 5 members: **(1)** Testbed + `chinga-ai` + Qwen, **(2)** Django models/pipeline/API,
**(3)** frontend wiring, **(4)** dataset + evaluation + evidence, **(5)** awareness content, docs, video, pitch &
business model (20% of marks!).

---

## 16. Submission checklist and declarations

- [ ] Repo accessible; README with architecture diagram, setup for laptop + Testbed, env vars.
- [ ] `docs/testbed-evidence/`: `nvidia-smi` output, `/health` + `/classify` + `/extract` responses with host and
      latency, `AuditEvent` export showing real inference calls during the demo.
- [ ] `docs/EVALUATION.md`: dataset description, split, three configurations, metrics tables, FP/FN examples,
      per-language notes, Qwen extraction check, limitations.
- [ ] Safety section (copy §14) and privacy notice text shown in the app.
- [ ] Three-minute demo video.
- [ ] **Declarations of third-party assets and AI tools:**

| Asset | Licence / terms | Use |
|---|---|---|
| Guardian codebase (team background IP) | team-owned | Core Django platform |
| Chinga prototype frontend (team background IP) | team-owned | Next.js PWA |
| `masterburator3301/distilbert-spam-phishing-classification-onnx` | **not stated on model card**, declared, used for research/demo | Text classifier |
| `distilbert-base-uncased` (base) | Apache-2.0 | Tokenizer/base |
| Kaggle `zefang-liu/phishing-email-dataset` (training data of the above) | see dataset page | (indirect) |
| `Qwen/Qwen3-VL-2B-Instruct` (+ GGUF conversion by ggml-org if used) | Apache-2.0 | Screenshot extraction, explanations |
| llama.cpp (if used) | MIT | Model serving |
| `sentence-transformers/all-MiniLM-L6-v2` (if used) | Apache-2.0 | Campaign grouping |
| URLhaus / PhishTank / OpenPhish | per provider terms | Threat indicators |
| Google Gemini API | Google API terms | Admin content generation fallback |
| Django, DRF, FastAPI, onnxruntime, Transformers, scikit-learn, Next.js… | respective OSS licences | Frameworks |
| AI coding assistants used by the team (e.g. Claude Code) | - | Code/documentation assistance |

---

## 17. Risks and fallbacks

| Risk | Impact | Mitigation / fallback |
|---|---|---|
| PyTorch build lacks Pascal kernels for the GTX 10-series | Qwen can't run via transformers on GPU | llama.cpp GGUF (Option A); else CPU (Option C) and label as slow |
| llama.cpp install not approved | Option A blocked | Option B fp16 transformers with small `max_pixels`; else CPU |
| 6 GB VRAM OOM | Screenshot calls fail | Q4 GGUF; reduce `max_pixels`/context; one request at a time |
| 10 GB WSL RAM | Swapping, crashes | Only `chinga-ai` + Qwen on Surface; DB + Django on laptop |
| WSL port not reachable on LAN | Django can't reach Testbed | SSH tunnel `ssh -N -L 8000:localhost:8000 -L 8081:localhost:8081 surface2` |
| Classifier domain mismatch (email → SMS) | High FP/FN | Rules + URL checks + fusion; tune threshold on dev split; report honestly |
| No licence on DistilBERT ONNX repo | Compliance question | Declare; ask the AI/ML mentor; alternative HF phishing model as a swap-in behind `/classify` |
| Gemini quota / outage | Awareness generation fails | Qwen local for generation; seed pre-approved lessons |
| Event network down during demo | Live inference fails | `unable_to_verify` path + recorded evidence video; Express demo fallback clearly labelled `SIMULATED` |
| Time | Unfinished features | Ship P0 only; label everything else roadmap |

---

## 18. Appendix

### 18.1 Environment variables

**Django (`pita/.env`)**
```
DATABASE_URL=postgresql://user:password@localhost:5432/chinga_db
DJANGO_SECRET_KEY=change-me
DEBUG=True
SITE_URL=http://localhost:8001
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
GEMINI_API_KEY=                       # admin-side generation only
CHINGA_AI_URL=http://137.63.190.232:8000      # or http://localhost:8000 via SSH tunnel
QWEN_BASE_URL=http://137.63.190.232:8081/v1   # or http://localhost:8081/v1 via SSH tunnel
QWEN_MODEL=qwen3-vl-2b
CLASSIFIER_THRESHOLD=0.5              # replace with tuned value from §12
CHINGA_DEMO_MODE=False
```

**chinga-ai (Surface, `~/chinga-ai/.env` or exported in tmux)**
```
CLASSIFIER_DIR=~/models/distilbert-phish
QWEN_BASE_URL=http://localhost:8081/v1
QWEN_MODEL=qwen3-vl-2b
```

**Chinga frontend (`UCC_TEST_BED_HACKATHON/.env`)**
```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

### 18.2 Resulting repo layout

```
guardian-main/
├── CHINGA_MIGRATION_PLAN.md          ← this file
├── chinga-ai/                        ← NEW: FastAPI inference service (runs on Surface Studio 2)
│   ├── app.py  classifier.py  vlm.py  prompts.py  requirements.txt  README.md
│   └── eval/ uganda_synthetic_v1.csv  run_eval.py  results/
├── docs/
│   ├── EVALUATION.md
│   └── testbed-evidence/
└── pita/
    ├── pita/ settings.py  urls.py  middleware.py          (vignette removed)
    ├── awarenessapp/                                      (roles, categories, llm.py, child-friendly prompts)
    │   └── services/ llm.py  transformation.py  ingestion.py  email_service.py  file_validators.py  ratelimit.py
    └── chinga/                                            ← NEW Django app
        ├── models.py  admin.py  urls.py  views.py  api.py  permissions.py
        ├── services/ analysis.py  ai_client.py  redact.py  url_checks.py  rules.py  campaigns.py  alerts.py
        └── management/commands/ seed_chinga.py  ingest_threat_feeds.py  load_eval.py
```

### 18.3 Five-scene demo script (from PRD §21.4)

1. **Child, Is this safe?** Paste a synthetic fake Makerere scholarship message with a test URL → live result from
   the Testbed: *Suspicious/High*, signals (advance fee, brand/domain mismatch), child-friendly explanation. Show the
   `meta.inference.host` = Surface.
2. **Screenshot.** Upload a synthetic chat screenshot → Qwen extracts only the scammer's message → result.
3. **Parent.** Guardian view shows a minimal alert (threat type + action + time), point out what is *not* shown.
4. **UCC admin.** A second variant of the message appears grouped into the same suspected campaign; sanitised text,
   *alleged* impersonated institution, district trend; open the evaluation page with FP/FN.
5. **Something happened + 116.** Child files a confidential report → no guardian alert; **Call 116** opens the dialer.
   Close with an approved awareness quiz generated from that campaign.

### 18.4 Quick command reference

```bash
# Surface (inside wsl)
source ~/venv/bin/activate
tmux new -s qwen   # llama-server ... --port 8081
tmux new -s ai     # cd ~/chinga-ai && uvicorn app:app --host 0.0.0.0 --port 8000
nvtop              # watch GPU memory

# Laptop
ssh -N -L 8000:localhost:8000 -L 8081:localhost:8081 surface2   # if LAN access to WSL fails
cd pita && python manage.py runserver 0.0.0.0:8001
cd /home/tinex/UICT/UCC_TEST_BED_HACKATHON && npm run dev:frontend
```
