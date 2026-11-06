# Guardian: online safety for Ugandan children and families

Guardian helps children (about 10 to 15) and their parents spot scams, phishing and other online risks, practise on
safe made-up examples, and learn what to do. It was built for the **UCC Testbed Hackathon 2026, Track 4: AI for
Child-Focused Cybersecurity and Online Fraud Prevention**, on top of an earlier Django awareness platform.

Detection runs on **local models on the Testbed GPU machine**. Cloud AI is never needed, and child data never leaves
the system unless an operator explicitly turns on a declared fallback.

The full design, decisions and build status are in [plan.md](plan.md).

---

## What it does

### 1. "Is this safe?" checks (children and parents)

Paste a message, a link or a screenshot and Guardian answers with one of four results: **high risk**, **some warning
signs**, **low observed risk** or **unable to verify**. Each result comes with plain-language reasons and next steps.

- Text is **redacted** before storage (PINs, OTPs, passwords, phone numbers, emails, names).
- Links are **analysed, never visited**.
- Screenshots are read in memory and **never stored**.
- The risk level comes from **deterministic fusion** in Django of a text classifier, a URL model, safety rules and
  known practice messages. The language model only reads screenshots and writes explanations. It never decides risk.
- If the AI service is down, Guardian falls back to **safety rules only** and says so on the result.
- When a child checks something high risk, linked parents get an **alert with the scam type and what to do**, never
  the message itself.

### 2. Safe practice messages and lessons

- An **analyst** writes or approves an awareness topic. Guardian AI then writes, in one step, a **parent version**, a
  **child-language lesson** in the same format, a **3-question quiz** and a **safe practice message** with marked red
  flags.
- Every generated pack passes a safety screen before it can be published: no real brands, no threats or fear, no
  requests for codes, and a valid link.
- **Parents** see the topic in *News for families*. They can send the practice message to chosen children with one tap
  or turn on **automatic drills**.
- **Children** get the practice email. Tapping its link **signs them straight into their own lesson and quiz**. It
  needs no app and no password, and Guardian records who opened it, read the lesson and took the quiz.
- Every child first receives a welcome note with a "this isn't me" stop link. Messages are capped per month, and
  parents can turn practice off at any time.
- Lessons stay available in the child's and parent's libraries whether or not a practice message was sent.

### Roles

| Role | Who | Main pages |
|---|---|---|
| **Child** | A learner, linked to one or more parents | `/me/`: check, history, report, lessons, my family (what a parent can and cannot see) |
| **Parent** | A parent or carer | `/family/`: children, family codes, consent, alerts, checks, News for families, settings |
| **Analyst** | Authorised analysts, such as UCC, the Ministry of Gender or the Police Child and Family Protection Unit, plus the team publishing content | Analyst workspace: sources, AI content pipeline, family versions, campaigns, analytics, printable reports |

Children can connect a device to a parent with a one-time **family code** (`/pair/`). Practice emails and lessons
also work without that step.

---

## Architecture

```
 Browser / phone ──► Django (pita/)  ── HTTP + X-Guardian-AI-Key ──►  guardian-ai (FastAPI)
                       │                                                │
                       │ PostgreSQL                                      ├─ DistilBERT ONNX      text scam score     (CPU)
                       │ SMTP (practice + notices)                       ├─ phishing-URL ONNX    link score          (CPU)
                       │                                                 ├─ all-MiniLM-L6-v2     embeddings          (CPU)
                       └ deterministic fusion, rules,                    └─ Qwen3-VL-2B GGUF     screenshots,
                         redaction, alerts, tracking                        (llama-server, GPU)  explanations, content
```

| Part | Folder | What it is |
|---|---|---|
| Web app | [pita/](pita/) | Django 6, PostgreSQL, Tailwind (CDN, no build step), django-allauth (optional Google sign-in) |
| `awarenessapp` | [pita/awarenessapp/](pita/awarenessapp/) | Users and roles, analyst content pipeline, campaigns, library, quizzes, analytics, AI client |
| `safety` | [pita/safety/](pita/safety/) | Children, parent links, family codes, consent, checks, redaction, rules, fusion, reports, alerts |
| `phishsim` | [pita/phishsim/](pita/phishsim/) | Topic packs (parent/child/quiz/practice), practice deliveries, link sign-in, stop links |
| Inference service | [guardian-ai/](guardian-ai/) | FastAPI with backend chains per capability and a content-free inference log ([README](guardian-ai/README.md)) |
| Evidence | [docs/testbed-evidence/](docs/testbed-evidence/) | Health and timing captures from the GPU machine |

---

## Running it locally

Requires Python 3.12+ and PostgreSQL (SQLite also works for quick tries).

### 1. Web app

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cp pita/.env.example pita/.env        # then edit: database, secret key, email, GUARDIAN_AI_URL/TOKEN
cd pita
python manage.py migrate
python manage.py createsuperuser      # becomes an analyst with full access
python manage.py runserver 0.0.0.0:8001
```

Open `http://localhost:8001`. Sign up there to create a parent account. Children join through a family code or a
practice link.

With the default console email backend, practice emails print to the terminal. Set SMTP in `pita/.env` to really
send them.

### 2. AI service

There are two ways to run it.

- **Testbed (GPU machine, the default).** Start everything on the GPU machine, then keep a tunnel open from the laptop:

  ```bash
  ssh -i ~/.ssh/<key> <user>@<gpu-host> "wsl -d Ubuntu-24.04 -- bash /home/<user>/guardian-ai/scripts/start_all.sh"
  bash guardian-ai/scripts/tunnel.sh    # laptop: localhost:8100 -> GPU guardian-ai:8000, reconnects by itself
  ```

  In `pita/.env` set `GUARDIAN_AI_URL=http://localhost:8100` and the same `GUARDIAN_AI_TOKEN` as the service.
- **Laptop dev mode.** Run guardian-ai locally with Gemini backends, using synthetic data only. See
  [guardian-ai/README.md](guardian-ai/README.md).

Check the connection with:

```bash
python manage.py ai_health
```

If the service is unreachable, checks still work in rules-only mode. Generating family versions needs the service.

### Tests

```bash
cd pita && python manage.py test safety phishsim awarenessapp
cd guardian-ai && .venv/bin/python -m pytest -q      # fake backends, no network
```

---

## Configuration (`pita/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL URL (or `sqlite:///db.sqlite3`) | `sqlite:///db.sqlite3` |
| `DJANGO_SECRET_KEY`, `DEBUG` | Django basics | `DEBUG=False` |
| `SITE_URL` | Public base URL used in email links | `http://localhost:8000` |
| `GUARDIAN_AI_URL`, `GUARDIAN_AI_TOKEN` | Where guardian-ai is, and its shared key | `http://localhost:8000` |
| `GUARDIAN_AI_TIMEOUT`, `GUARDIAN_AI_EXTRACT_TIMEOUT`, `GUARDIAN_AI_GENERATE_TIMEOUT` | Seconds per call type | `30`, `120`, `600` |
| `CLASSIFIER_THRESHOLD` | Text classifier cut-off used in fusion | `0.5` |
| `GUARDIAN_GEMINI_FALLBACK` | Allow Gemini when local models fail (declared fallback, off for the Testbed) | `False` |
| `GEMINI_API_KEY` | Only used when the fallback above is on | |
| `GUARDIAN_SIM_MAX_PER_MONTH` | Practice messages per child per month | `2` |
| `GUARDIAN_MAX_CHILD_EMAILS_PER_PARENT` | Child email addresses a parent may add | `5` |
| `GUARDIAN_LEARNER_SESSION_DAYS` | How long a practice-link sign-in lasts | `7` |
| `GUARDIAN_ANDROID_APP_URL` | Optional Android download link shown on the home page | |
| `GUARDIAN_PARENT_PREFIX`, `GUARDIAN_CHILD_PREFIX` | URL prefixes for the parent and child spaces | `family`, `me` |
| `AWARENESS_AUTH_PREFIX`, `AWARENESS_STAFF_PREFIX`, `AWARENESS_PANEL_PREFIX` | Obscured prefixes for auth, library and analyst workspace | random strings |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Optional Google sign-in (button hidden when unset) | |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_TIMEOUT`, `EMAIL_FROM_NAME` | Outgoing email | console backend |

Never commit `.env` files, SSH keys or Testbed passwords.

---

## Safety rules (summary)

- Practice messages use made-up organisations and `.example` addresses. They never use threats, fear, sexual themes
  or requests for codes, and they are sent from Guardian's own address with an `X-Guardian-Simulation` header.
- Parents see scam types and lesson progress, never the content their child checked or reported.
- Practice-link sign-ins are scoped to one child, expire, and cannot change account details or family links.
- Generated text is cleaned before it is stored or shown.
- Help is always one tap away: Sauti child helpline **116**.

The full list is in [plan.md §13](plan.md).

---

## Status and roadmap

Built so far: checks (text, links, screenshots), parent alerts, families and family codes, consent, the content flow
from analyst to family to lesson, practice emails with link sign-in, and the GPU deployment with local models.

Next:
- a live model evaluation page with model cards
- families and children analytics for analysts
- PDF and `.eml` uploads
- scam-wave detection
- SMS and WhatsApp practice channels
- a mobile app wrapper

See [plan.md §15](plan.md).

## License

MIT
