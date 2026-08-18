# UW Risk Copilot — Commercial Property Underwriting Backend

A FastAPI + LangGraph backend providing deterministic underwriting scoring, Gemini Vision property-image analysis, RAG-grounded underwriting evidence retrieval, and AI-assisted structured underwriting memos for Indian commercial property.

**The React frontend lives in `../propertyRiskAssesment/`.**

---

## Architecture

```
React SPA
  └── POST /underwrite/submit (multipart: form fields + optional image)
       └── LangGraph pipeline:
             intake
             └── Vision (Gemini): image → structured observations
             └── RAG (Chroma + Gemini embedding): guidelines retrieval
             └── Risk scoring (Python): deterministic score + flags
             └── Reference properties: multi-attribute synthetic-reference ranking
             └── AI Memo (Gemini): grounded structured memo
  └── POST /underwrite/preview   (live deterministic preview, no DB write)
  └── GET  /underwrite/history   (portfolio dashboard data)
  └── GET  /underwrite/history/{id}          (submission detail)
  └── GET  /underwrite/history/{id}/report.pdf   (PDF report)
```

**Authoritative decision** is always Python-deterministic:
- 0–30 → Accept
- 31–60 → Refer
- 61–84 → Decline (mitigation possible)
- 85–100 → Auto-Decline

**Gemini** provides: Vision observations, RAG embeddings, structured AI memo (explanation only — cannot override Python decision).

---

## Setup

### 1. Python environment

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS/WSL
# .venv\Scripts\activate        # Windows PowerShell
pip install -r requirements.txt
```

### 2. Gemini API key

```bash
cp .env.example .env
# Edit .env and set:
# GEMINI_API_KEY=your_key_here
```

Free key: https://aistudio.google.com

### 3. Start the backend

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The SQLite schema and reference-property table initialise automatically on first start. The checked-in Chroma vectorstore under `data/vectorstore/` must be present for RAG retrieval.

---

## Data

| Path | Description |
|---|---|
| `data/raw/underwriting_guidelines.pdf` | Source PDF for RAG index |
| `data/raw/properties.csv` | 300 synthetic reference properties for comparables |
| `data/vectorstore/` | Chroma index (auto-built from PDF at startup) |
| `data/db/uw_risk.db` | SQLite: submissions + reference properties |
| `data/raw/images/` | Demo property images (Tidel Park, Chennai) |

> **Note**: The 300 reference properties are synthetic and are **not** verified market comparables. They are labelled "Reference Properties" throughout the application.

### Demo image provenance

| File | Source / usage |
|---|---|
| `Tidel_park,_Chennai.jpg`, `Chennai.tidelpark.jpg` | TIDEL Park demo images retained for the Chennai submission |
| `Bandra-Kurla-Complex-Mumbai.jpg` | [Wikimedia Commons BKC skyline](https://commons.wikimedia.org/wiki/File:Bandra-Kurla-Complex-Mumbai-Maharashtra-India.jpg) |
| `ILFS-Bandra-Kurla-Complex-Mumbai.jpg` | [Wikimedia Commons BKC office building](https://commons.wikimedia.org/wiki/File:IL%26FS_-_Bandra_Kurla_Complex,_Mumbai.jpg), used by the Mumbai Accept demo |
| `Cotton-Green-Mill-Mumbai.jpg` | [Public-domain Wikimedia Commons image](https://commons.wikimedia.org/wiki/File:Cotton_green_mill_mumbai.jpg), “Cotton mill textile mill, Colaba,” dated 1910; used by the Auto-Decline demo |
| `Lulu-Mall-Kochi.jpg` | [Wikimedia Commons LuLu Mall Kochi exterior](https://commons.wikimedia.org/wiki/File:LuLu_Mall_Kochi.jpg), used by the Refer demo |
| `Crawford-Market-Mumbai.jpg` | [Wikimedia Commons Crawford Market image](https://commons.wikimedia.org/wiki/File:Crawford_Market_03.jpg), used by the Decline (mitigation possible) demo |

Submitted images are persisted with the submission, analyzed by Vision, displayed in the result workflow, and embedded in the generated PDF. Image observations remain non-authoritative evidence; manual/scored facts are controlled separately.

---

## Tests

```bash
# Full suite (34 tests)
pytest tests/ -v

# Individual files
pytest tests/test_risk_calculator.py -v     # 13 deterministic scoring tests
pytest tests/test_report_agent.py -v        # 8 AI memo contract tests
pytest tests/test_vision_extract.py -v      # 10 Vision pipeline tests
pytest tests/test_database_lifecycle.py -v  # 3 DB + PDF/image tests
```

---

## Scoring model

All authoritative score weights are defined as named constants in `app/tools/risk_calculator.py`:

| Factor | Points | Condition |
|---|---|---|
| Roof age | +25 / +15 | > 30 yr / > 20 yr |
| Frame construction | +10 | combustible frame |
| No sprinkler (warehouse/industrial) | +10 | high-hazard occupancy |
| CAT zone (Wind/Flood/Wildfire) | +20 | primary CAT perils |
| CAT zone (Hail/Earthquake) | 0 | captured, not scored (no calibrated rule) |
| Seismic zone IV/V | +15 | high-seismic zone |
| Coastal proximity | +15 | < 1 mile to coast |
| Wildland-urban interface | +15 | < 1 mile to fire zone |
| Adverse loss history | +15 | > 2 claims in 5 yr |
| High TIV | +5 | TIV > ₹20M |

> These are **prototype calibrations**, not filed Indian insurance rating rules.

### Product segments (IRDAI-aligned)

| TIV | Segment |
|---|---|
| ≤ ₹50M | Bharat Sookshma Udyam Suraksha |
| ≤ ₹500M | Bharat Laghu Udyam Suraksha |
| > ₹500M | Larger-risk / commercial property segment |

---

## AI memo contract

`report_agent.py` produces a 6-field validated JSON memo:

```
property_summary     list[str]   — grounded property facts
key_risk_factors     list[str]   — deterministic risk flags only
coverage_review      list[str]   — requested coverage review (not exposure)
decision             str         — must equal deterministic decision
rationale            str         — AI explanation
suggested_next_steps list[str]   — actionable items
```

Validation rules (mechanical, not NLP):
- Decision must exactly match `decision_from_score(risk_score)`
- Key risk factors must reference actual `risk_flags`
- Coverage review must not reference unrequested perils
- Coverage review must not contain invented monetary amounts, rates, or regulatory mandates
- Roof age fabrication guard (no invented age claims when `roof_age_years = None`)

---

## Known limitations

- Uses `gemini-3-flash-preview` — preview channel, not GA-pinned
- Gemini requests are bounded to 60 seconds and fail closed; Python decisions remain available if AI is unavailable
- Reference properties are synthetic (Faker-generated US-style addresses)
- Scoring weights are prototype calibrations, not insurer loss-cost data
- RAG grounded to one generic commercial-property guidelines PDF, not carrier-specific documents
- Seismic zone II/III scored equally (0 pts), IV/V scored equally (+15 pts) — prototype 2-tier simplification; BIS IS 1893 defines four distinct zones
- The PoC demonstrates workflow speed, consistency, evidence capture, and decision support. It does not empirically prove loss-ratio reduction or pricing accuracy without longitudinal insurer outcomes
- Real property names, locations, historic years, and image provenance are public-source facts; claims, roof age, insured values, protection controls, and coverage selections used to exercise decision bands are explicit demo assumptions
