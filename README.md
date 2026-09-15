# Manuscript OCR & Translation Backend

A modular FastAPI backend for digitizing historical manuscripts: upload an
image, get back OCR'd text (with per-line confidence), the detected
language/script, and a translation into a language of your choice.

Built for **historical manuscripts specifically** — the pipeline assumes
faded ink, skew, noise, handwriting, and unreliable OCR, and is designed so
every stage (preprocessing, OCR, translation, verification) can be swapped
for a better model without touching the API.

---

## 1. Project Overview

```
Manuscript image + target language
        │
        ▼
  Validate & save upload
        │
        ▼
  Preprocess image (configurable)
        │
        ▼
  OCR (EasyOCR default / Kraken opt-in, swappable)
        │
        ▼
  Language detection (Unicode script heuristic + langdetect)
        │
        ▼
  Text cleaning (conservative normalization)
        │
        ▼
  OCR quality assessment → warnings / needs_review
        │
        ▼
  [LLM verification — placeholder, future]
        │
        ▼
  Translation (NLLB-200, many-to-many, swappable)
        │
        ▼
  Structured JSON response
```

## 2. Architecture

- **API layer** (`app/api/routes`) never talks to OCR/translation libraries
  directly — only to the pipeline orchestrator and service *interfaces*.
- **Services** (`app/services`) each define an abstract base class plus one
  or more concrete implementations, so any stage can be replaced:
  - `OCRService` → `EasyOCRService` (default) / `KrakenOCRService`
    (opt-in, fine-tunable — see `training/README.md`)
  - `TranslationService` → `HuggingFaceTranslationService` /
    `GoogleTranslationService` (stub) / `LLMTranslationService` (stub)
  - `TextVerificationService` → `NoOpTextVerificationService` (LLM slot for later)
- **Pipeline** (`manuscript_pipeline.py`) wires the stages together and is
  the only place that knows the full sequence.
- **No database in the MVP** — everything is processed in memory/temp
  storage per request. Schema is documented below for when persistence is
  added.

## 3. Folder Structure

```
manuscript-backend/
├── app/
│   ├── main.py                     FastAPI app, startup, global error handler
│   ├── api/routes/manuscript.py    /health and /manuscript/process endpoints
│   ├── core/config.py              Settings (env-driven)
│   ├── core/logging_config.py      Structured logging setup
│   ├── models/schemas.py           Pydantic request/response models
│   ├── services/
│   │   ├── image_preprocessing.py  Configurable OpenCV pipeline
│   │   ├── ocr_service.py          OCR abstraction + EasyOCR/Kraken impls
│   │   ├── language_detection.py   Script heuristic + langdetect
│   │   ├── text_cleaning.py        Conservative OCR text normalization
│   │   ├── text_verification.py   Future LLM verification placeholder
│   │   ├── translation_service.py  Translation abstraction + NLLB-200
│   │   └── manuscript_pipeline.py  Orchestrates the full flow
│   └── utils/file_utils.py         Safe upload handling
├── uploads/                        Saved originals (gitignored contents)
├── processed/                      Reserved for persisted preprocessing output
├── training/                       Kraken fine-tuning workflow (optional, see training/README.md)
│   ├── segment_pages.py            Auto-crops pages into line images for transcription
│   ├── validate_dataset.py         Checks a dataset is training-ready
│   ├── manuscript_pages/           Your raw page images go here (gitignored)
│   └── lines/                      Generated line crops + .gt.txt sidecars (gitignored)
├── tests/                          Unit + integration tests
├── requirements.txt
├── requirements-kraken.txt         Optional: install for OCR_ENGINE=kraken
├── .env.example
├── run.py
├── streamlit_app.py            Simple frontend (calls the backend API)
└── README.md
```

## 4. Installation (Windows / VS Code terminal)

See **Section 20 (Exact Commands)** below for the full copy-pasteable list.

## 5. Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

## 6. Dependency Installation

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> Note: `torch`, `easyocr`, and `transformers` are large downloads
> (~1-2 GB combined) and EasyOCR/HuggingFace models are additionally
> downloaded on first use and cached locally.

## 7. Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```bash
copy .env.example .env
```

Key variables:

| Variable | Purpose |
|---|---|
| `MAX_UPLOAD_SIZE_MB` | Reject uploads larger than this |
| `ALLOWED_EXTENSIONS` / `ALLOWED_MIME_TYPES` | Upload allowlist |
| `OCR_ENGINE` | Currently only `easyocr` |
| `OCR_LANGUAGES` | EasyOCR language codes, comma-separated |
| `TRANSLATION_PROVIDER` | `huggingface` (default, local) / `google` / `llm` (stubs) |
| `OCR_LOW_CONFIDENCE_THRESHOLD` | Below this, OCR flagged for review |
| `LANGUAGE_DETECTION_LOW_CONFIDENCE_THRESHOLD` | Below this, detection flagged |

## 8. Running the Server

```bash
python run.py
```

or

```bash
uvicorn app.main:app --reload
```

Server runs at `http://127.0.0.1:8000`.

## 8b. Running the Streamlit Frontend

A minimal Streamlit UI (`streamlit_app.py`) is included so you can try the
backend without curl/Swagger: upload an image, pick a target language, and
see the OCR + translation result rendered.

It is a thin client — it only calls the backend's HTTP API, so the backend
must already be running.

1. Keep the FastAPI backend running in one terminal (`python run.py`).
2. In a **second** terminal (same venv activated):
   ```bash
   streamlit run streamlit_app.py
   ```
3. Streamlit opens at `http://localhost:8501`. If your backend runs on a
   different host/port, change "Backend URL" in the sidebar.

## 9. API Endpoints

### `GET /api/v1/health`
Returns `{"status": "healthy"}`.

### `POST /api/v1/manuscript/process`
`multipart/form-data`:
- `image`: file (jpg/jpeg/png/webp)
- `target_language`: one of `en`, `fr`, `de`, `es`, `hi` (MVP allowlist — see `SUPPORTED_TARGET_LANGUAGES` in `manuscript_pipeline.py`)

## 10. Example curl Request

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/manuscript/process" ^
  -F "image=@manuscript.jpg" ^
  -F "target_language=en"
```

(On macOS/Linux, replace `^` line continuations with `\`.)

## 11. Example Python Request

```python
import requests

with open("manuscript.jpg", "rb") as f:
    response = requests.post(
        "http://127.0.0.1:8000/api/v1/manuscript/process",
        files={"image": f},
        data={"target_language": "en"},
    )

print(response.json())
```

## 12. Example JSON Response

```json
{
  "success": true,
  "request_id": "b3f1c2b0-...",
  "detected_language": {
    "language": "Odia",
    "language_code": "or",
    "confidence": 0.91,
    "is_low_confidence": false
  },
  "target_language": { "language": "English", "language_code": "en" },
  "ocr": {
    "raw_text": "...",
    "cleaned_text": "...",
    "text": "...",
    "confidence": 0.84,
    "lines": [
      { "text": "First line...", "confidence": 0.91, "bbox": [[10,10],[100,10],[100,30],[10,30]] }
    ]
  },
  "translation": {
    "text": "Translated text...",
    "provider": "huggingface",
    "source_language": "or",
    "target_language": "en",
    "reliable": true
  },
  "processing": {
    "preprocessing_applied": ["upscale", "deskew", "grayscale", "denoising", "contrast_enhancement"],
    "processing_time_ms": 1250,
    "ocr_engine": "easyocr",
    "translation_provider": "huggingface"
  },
  "warnings": [],
  "needs_review": false
}
```

## 13. How OCR Works

`OCRService` is an abstract base class with two implementations:

- **`EasyOCRService`** (default): lazily loads an `easyocr.Reader` (once
  per language-set, thread-safely) and returns full text, per-line
  text/confidence/bounding boxes, and an overall confidence. EasyOCR only
  pairs one non-Latin script with English per reader (`['te','en']` works,
  `['te','hi']` doesn't), so the API accepts an optional `source_script`
  hint (e.g. `'te'`, `'hi'`, `'ta'`) to load the right reader for the
  manuscript's actual script — see `SCRIPT_LANGUAGE_GROUPS` in
  `app/services/ocr_service.py`. **EasyOCR has no Odia model at all** —
  Odia can still be a translation target/source once text exists, but an
  Odia-script manuscript image can't be OCR'd by this engine.
- **`KrakenOCRService`** (opt-in via `OCR_ENGINE=kraken`): built for
  fine-tuning on your own manuscripts' handwriting/script. See
  `training/README.md` for the full data-collection-to-fine-tuning
  workflow, including tooling (`training/segment_pages.py`,
  `training/validate_dataset.py`) that turns page images + typed
  transcriptions into a trainable dataset.

**Why EasyOCR as the MVP default:** Tesseract needs heavy tuning for
handwriting/skew; PaddleOCR has heavier install requirements; TrOCR/Donut
need per-script fine-tuning to beat a general-purpose reader out of the
box. EasyOCR gives broad script coverage, bounding boxes, and confidence
scores with no fine-tuning or extra setup required.

## 14. How Language Detection Works

`LanguageDetectionService` combines two strategies:

1. **Unicode script detection** (checked first): scans code points and
   identifies the dominant script. For scripts that map to one practical
   language — Odia, Telugu, Tamil, Kannada, Malayalam, Bengali, Gujarati,
   Gurmukhi — this is used directly. This exists because `langdetect` (see
   below) has **no trained model for Odia at all**; it can never return
   `or`, however clean the input. Script detection is also more robust on
   short/noisy OCR text than a statistical model.
2. **`langdetect`** (fallback): used for scripts shared by multiple
   languages (Latin: en/fr/de/es/...; Devanagari: hi/mr/sa; Arabic:
   ar/ur/fa), where script alone can't determine the language.

Detections below `LANGUAGE_DETECTION_LOW_CONFIDENCE_THRESHOLD` are flagged
via `is_low_confidence` and a warning — never silently presented as
certain. `LanguageDetectionService.detect_script()` exposes the raw script
name for future use, since a script can still be shared by multiple
languages even where the heuristic makes a best-effort single-language
assumption (e.g. Devanagari defaults through `langdetect` rather than
being hard-mapped to one language).

## 15. How Translation Works

`TranslationService` is an abstract interface. The default
`HuggingFaceTranslationService` loads a single shared
**facebook/nllb-200-distilled-600M** model (NLLB-200) rather than a
model per language pair: it's genuinely many-to-many across 200+
languages in one model, including direct translation between Indic
languages that don't have a dedicated `Helsinki-NLP/opus-mt-*` pair (e.g.
Hindi→Telugu, Telugu→Odia). It translates line-by-line to preserve
manuscript structure. If a language isn't in `NLLB_LANGUAGE_CODES`, it
returns the original text plus a warning instead of failing.

## 16. How to Replace the OCR Model

1. Create a new class in `app/services/ocr_service.py` implementing
   `OCRService.extract_text(image) -> OCRResult`.
2. Register it in `get_ocr_service()`.
3. Set `OCR_ENGINE` in `.env` to select it.

No other file needs to change — the pipeline and API only depend on the
abstract interface. (`KrakenOCRService` is a worked example of this —
see `training/README.md` to fine-tune it on your own data.)

## 17. How to Replace the Translation Provider

1. Implement `TranslationService.translate(text, source_language, target_language)`
   in `app/services/translation_service.py` (see `GoogleTranslationService`
   stub for the shape).
2. Register it in `get_translation_service()`.
3. Set `TRANSLATION_PROVIDER` in `.env`.

## 18. How to Add an LLM Later

`TextVerificationService` (`app/services/text_verification.py`) is a ready
slot: implement `verify(text, context)` to call an LLM (Llama/Qwen/Mistral)
that compares OCR text against the manuscript image and proposes
corrections, then wire it into `ManuscriptPipeline` in place of
`NoOpTextVerificationService`. The pipeline already calls this stage
between text cleaning and translation, so no restructuring is needed.

## 19. How to Add RAG / Vector Embeddings Later

Add a new service (e.g. `embedding_service.py`) that turns cleaned OCR
text into vectors, plus a vector store client, and call it after text
cleaning inside `ManuscriptPipeline`. Because the pipeline already isolates
each stage behind a method call, inserting an embeddings → vector DB →
RAG step does not require changing the API contract — only the
`ManuscriptProcessResponse` schema would optionally grow new fields (e.g.
`related_passages`).

## Known Limitations

- MVP only supports translation into `en`, `fr`, `de`, `es`, `hi` (limited
  by which `Helsinki-NLP/opus-mt-*` models are known to exist for a given
  source language — unsupported pairs fall back to returning the original
  text with a warning rather than failing the request).
- No persistent storage/database yet — nothing is retained after the
  response is returned.
- No script detection (only language detection).
- LLM-based OCR correction is a placeholder no-op.
- EasyOCR's general-purpose model is not fine-tuned on historical
  manuscripts; confidence scores should be treated as a heuristic, not
  ground truth — hence the `needs_review` flag and warnings.
