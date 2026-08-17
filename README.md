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

## Notes

- Set `GEMINI_API_KEY` only in `.env`; do not commit it.
- The deterministic risk calculation is intentionally separate from Gemini-generated narrative output.
