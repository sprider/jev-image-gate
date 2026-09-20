# Jev Image Gate

A small Python service that puts **[TypeSafe Jev](https://docs.typesafe.ai/introduction)** in front of Gemini image generation.

Jev does not paint. It returns typed decisions. Your code decides whether Gemini may run.

```text
prompt + product-still policy
        │
        ▼
Jev (one request, three questions)
  Noul   - does this violate policy?
  Score  - is the prompt specific enough?
  Choice - block | ask_clarify | allow_lite | allow_premium
        │
        ▼
Python guardrails (confidence, unknown enums, outages)
        │
        ├── block / ask_clarify → no image API call
        └── allow_lite / allow_premium → one Gemini image call
```

Demo policy: commercial **product stills** - one product, studio lighting, no third-party marks, no readable slogans, no real people, no medical or financial claims.

## Links

- [TypeSafe introduction](https://docs.typesafe.ai/introduction) - Jev, System One, and the three primitives
- [Create a TypeSafe API key](https://console.typesafe.ai/keys)
- [TypeSafe usage](https://console.typesafe.ai/usage)
- [Google AI Studio API keys](https://aistudio.google.com/apikey) - Gemini, only if you want `/v1/generate` to paint

## Requirements

- Python 3.10+
- A TypeSafe API key from [console.typesafe.ai/keys](https://console.typesafe.ai/keys) for preflight decisions
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) only if you want `/v1/generate` to produce an image

Unit tests run without either key.

## Quick start

```bash
git clone <this-repo>
cd jev-image-gate
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]" --extra-index-url https://pypi.typesafe.ai/
cp .env.example .env
```

Edit `.env` and set `TYPESAFE_API_KEY` from [the TypeSafe console](https://console.typesafe.ai/keys). Set `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey) if you want images.

```bash
python -m image_gen_controller.main
```

- Playground: <http://127.0.0.1:8000/>
- Health: `GET /healthz`
- Decide only: `POST /v1/preflight`
- Decide, then generate if allowed: `POST /v1/generate`

```bash
curl -s http://127.0.0.1:8000/v1/preflight \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"studio photo of a red ceramic mug on a white sweep, no text, no logos"}'
```

Without `TYPESAFE_API_KEY`, preflight still starts and returns `ask_clarify` / `will_spend=false`. Without `GEMINI_API_KEY`, `/v1/generate` returns the decision and `image.skip_reason=image_backend_unavailable`.

## Environment

Copy `.env.example` to `.env`. Do not commit `.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | empty | Jev / System One |
| `JEV_MODEL` | `jev-1.13.0` | Pin the decision model |
| `JEV_TIMEOUT_SECONDS` | `8` | HTTP timeout for Jev |
| `GEMINI_API_KEY` | empty | Image generation |
| `GEMINI_IMAGE_MODEL_LITE` | `gemini-3.1-flash-lite-image` | Used when action is `allow_lite` |
| `GEMINI_IMAGE_MODEL_PREMIUM` | `gemini-3-pro-image-preview` | Used when action is `allow_premium` |
| `REMAINING_BUDGET_USD` | `0.05` | Passed to Jev as budget context |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Bind address |
| `LOG_LEVEL` | `INFO` | Logging |

`typesafe-sdk` is installed from TypeSafe’s package index (`https://pypi.typesafe.ai/`). Spend and request volume show up under [TypeSafe usage](https://console.typesafe.ai/usage).

## Project layout

```text
.
├── src/image_gen_controller/   # application
│   ├── decisions.py            # spend policy (pure functions)
│   ├── questions.py            # Jev question specs
│   ├── jev_gateway.py          # TypeSafe client + fallback
│   ├── preflight.py            # validate prompt → Jev → decide
│   ├── generate.py             # preflight, then one image call
│   ├── image_backend.py        # Gemini IMAGE+TEXT client
│   ├── policy.py               # product-still rules
│   ├── api.py                  # FastAPI
│   └── static/index.html       # playground
├── tests/                      # unit tests (no live keys)
├── scripts/run_preflight_eval.py
├── data/eval_prompts.json      # three sample prompts
├── .env.example
└── pyproject.toml
```

## Guardrails

Code owns spend. Jev cannot invent an action outside this set: `block`, `ask_clarify`, `allow_lite`, `allow_premium`.

- Missing key, timeout, or bad Jev payload → do not spend
- Policy Noul ≥ 0.35 → `block`
- Specificity score ≤ 1 (unusable / vague) → `ask_clarify`
- Action confidence &lt; 0.35 → do not spend
- `allow_premium` with confidence &lt; 0.50 → degraded to `allow_lite`
- Exactly one Gemini call on the authorized tier - no automatic Pro retry

## Tests

```bash
pytest
```

Optional live preflight suite (calls TypeSafe, does **not** call Gemini):

```bash
python scripts/run_preflight_eval.py
```

That writes `data/eval_results.json` locally. Do not commit it.
