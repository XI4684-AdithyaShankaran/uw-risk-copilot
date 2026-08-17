# UW Risk Copilot

UW Risk Copilot is a local commercial-property underwriting prototype. FastAPI receives multipart property submissions, Streamlit provides the working-user interface, LangGraph coordinates extraction, retrieval, scoring, comparables, and reporting, and Gemini supplies image interpretation and underwriting narrative. The deterministic risk calculator, Chroma retrieval over a locally built underwriting-guidelines PDF index, attached-image feature extraction, and generated referral memo have been exercised locally; this remains a development prototype, not a production underwriting system.

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example env file and set your key:
   ```bash
   cp .env.example .env          # Linux/macOS/WSL
   # Windows PowerShell: Copy-Item .env.example .env
   ```
   Then edit `.env` and set:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```
   You can create a free key at https://aistudio.google.com.
4. Build the Chroma vector store for underwriting guidelines:
   ```bash
   python scripts/build_vectorstore.py
   ```
5. Start the FastAPI backend in one terminal:
   ```bash
   uvicorn app.api.main:app --reload
   ```
6. Start the Streamlit UI in a second terminal:
   ```bash
   streamlit run app/ui/streamlit_app.py
   ```

## Working Flow

- `scripts/build_vectorstore.py` embeds the underwriting-guidelines PDF into Chroma.
- `app/api/main.py` exposes multipart submission and history endpoints.
- `app/ui/streamlit_app.py` submits property data and images, then renders the returned memo and debug response.
- Test images are stored under `data/raw/images/`; local SQLite submission history and the Chroma index remain under `data/`.

## Architecture

Two LangGraph-orchestrated agents:

- **Risk Agent** — intake → (optional) vision feature extraction → guideline retrieval (RAG) →
  deterministic risk scoring → comparable-property lookup → decision synthesis. Comparable
  lookup is skipped on the auto-decline fast path (score ≥ 85) as an automation shortcut.
- **Report Agent** — takes the Risk Agent's output and generates the underwriting memo,
  grounded strictly in the deterministic score/flags/decision and retrieved guideline text —
  it narrates, it doesn't override.

Deterministic risk bands: 0–30 Accept · 31–60 Refer · 61–84 Decline (mitigation possible) · 85–100 Auto-Decline.

## Tests

```bash
python -m pytest tests/test_risk_calculator.py -v
```

Covers the deterministic scoring thresholds with hand-verified expected values.

## Known limitations

- Uses `gemini-3-flash-preview` (preview channel) for vision and reasoning — `gemini-2.5-flash`
  was deprecated for new API keys during development; not GA-pinned, may change without notice.
- Guideline RAG is grounded to a single synthetic underwriting-guidelines PDF, not real carrier
  policy documents.
- Property and claims data are synthetic (Faker-generated), not real underwriting records.

## Notes

- Set `GEMINI_API_KEY` only in `.env`; do not commit it.
- The deterministic risk calculation is intentionally separate from Gemini-generated narrative output.
