# uw-risk-copilot — Copilot instructions

## Project

AI-assisted commercial property underwriting prototype.

The system combines:
- deterministic underwriting rules
- guideline retrieval using Chroma/RAG
- Gemini-based report generation
- Gemini vision extraction for property images
- FastAPI backend
- Streamlit frontend
- SQLite persistence

All underwriting/property data in this repository is synthetic.

## Stack

- Python 3.13
- FastAPI
- Streamlit
- LangGraph
- Chroma
- google-genai
- SQLite
- pytest

## Repository structure

- `app/api/` — FastAPI endpoints
- `app/agents/` — LangGraph orchestration and report generation
- `app/tools/` — underwriting, RAG, vision, and supporting tools
- `app/ui/` — Streamlit application
- `app/config.py` — environment-dependent configuration
- `tests/` — automated tests
- `scripts/` — data/setup utilities
- `data/` — local synthetic data and development artifacts

Inspect the existing implementation before changing behavior.

## Development commands

Backend:

```bash
uvicorn app.api.main:app --reload
```
Streamlit:

```bash
streamlit run app/ui/streamlit_app.py
```

Tests:

```bash
python -m pytest tests/ -v
```

Compile check:

```bash
python -m py_compile <changed_python_files>
```

## Engineering rules

- Prefer small, localized changes.
- Preserve existing behavior unless the task explicitly requires a behavior change.
- Do not rewrite working components merely to simplify implementation.
- Do not replace a real integration with a mock, keyword match, or fallback without explicitly stating the architecture change.
- Keep business rules deterministic and testable.
- Keep model/API configuration centralized in app/config.py.
- Never hardcode API keys or credentials.
- Use environment variables for secrets.
- Add or update tests for behavior changes.
- Avoid speculative abstractions and unnecessary dependencies.
- Do not silently swallow exceptions that materially affect an underwriting result.
- Distinguish deterministic underwriting output from AI-generated output.

## AI / model usage

- Use the configured Gemini model from app/config.py.
- Do not hardcode model identifiers in application modules.
- Use the repository's established google-genai request patterns.
- Preserve existing RAG/vectorstore behavior unless the task explicitly changes retrieval architecture.
- Preserve existing vision architecture unless the task explicitly changes image processing.

## Validation

After making changes:

- run the narrowest relevant automated tests;
- run additional integration checks when the change crosses API/UI/model boundaries;
- report failed validation explicitly;
- do not claim a change is verified unless the relevant validation actually passed.

## Data and security boundaries

- Use synthetic property/claims data only.
- Do not access or introduce real policyholder data.
- Do not access corporate cloud credentials, corporate databases, or unrelated company resources.
- Never commit secrets, API keys, tokens, or credential files.
