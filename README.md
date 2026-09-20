# Big OCR

Big OCR is an experimental insurance-document AI pipeline that turns multi-page PDFs into schema-shaped insurance fields with page references, cached intermediate results, and an interactive Streamlit review interface.

> **Status:** Experimental research/prototype. The repository has working pipeline entry points and a UI, but no automated test suite, pinned deployment configuration, or verified hosted demo. Review provider settings and credential handling before using it with sensitive documents.

## What it does

- Accepts **PDF documents**. The Streamlit frontend currently restricts uploads to `.pdf` files.
- Converts pages to OCR text and identifies pages relevant to the insurance schema.
- Classifies relevant pages by insurance type, adds optional neighboring “padding” pages, and extracts type-specific fields.
- Supports text-first, vision-first, and image-assisted extraction paths.
- Caches OCR, vision, extracted-field, and rendered-page artifacts under `json/` and `pdf_images/` for repeat runs.
- Presents the uploaded PDF, page navigation, confidence-colored field values, source-page links, and raw JSON in Streamlit.
- Tracks token usage and prints an estimated run cost for the configured models.

## Architecture

```text
PDF
 │
 ├─ OCR-based (`main.py`)
 │    Google Cloud Vision OCR → page relevance → insurance categorization → field extraction
 │
 ├─ Vision-based (`main_vision.py`)
 │    OpenAI vision OCR + relevance → insurance categorization → field extraction
 │
 └─ Image-based (`main_image.py`)
      Google Cloud Vision OCR → page relevance → PDF page images → image field extraction

All paths use the shared schema utilities and write JSON results consumed by the Streamlit UI.
```

The default Streamlit app (`streamlit-frontend.py`) lets a user select the pipeline, enable/disable cache reuse, optionally add context pages, and inspect the resulting fields by insurance type.

## Provider and model integrations

| Area | Integration found in the codebase | Primary entry point |
| --- | --- | --- |
| OCR | Google Cloud Vision asynchronous PDF OCR through temporary Google Cloud Storage buckets | `modules/google_pdf_ocr.py` / `main_image.py` |
| Vision OCR | OpenAI vision requests over rendered PDF pages | `modules/pdf_vision_ocr.py` / `main_vision.py` |
| Page relevance and field extraction | OpenAI structured/JSON chat completions | `modules/check_page_relevance.py`, `modules/analyse_insurance_type.py`, `modules/get_fields_ai.py` |
| Alternate vision helper | Google Gemini image generation/content API | `modules/vision_ocr.py`, `utils/gemini.py` |
| Alternate OCR helper | Mistral OCR (`mistral-ocr-latest`) | `utils/mistral_ocr.py` |

The main pipelines currently reference `gpt-4.1-nano`, `gpt-4.1-mini`, and `gemini-2.5-flash-lite-preview-06-17`. The dependency manifest also includes several OCR/table-extraction packages, but their presence should not be interpreted as a fully wired production backend.

## Outputs

The runtime primarily writes JSON:

- `json/ocr_results.json` — normalized page text and word counts.
- `json/vision_results.json` — cached vision responses.
- `json/extracted_insurance_fields.json` — fields from the text/OCR and vision paths.
- `json/extracted_insurance_fields_image.json` — fields from the image-assisted path.
- `pdf_images/` — rendered page-image cache used by the UI and image-assisted pipeline.

The checked-in JSON/PDF/image files are sample or cache artifacts, not a stable public API. `schema.json` is the extraction schema source used to derive field prompts.

## Local setup

The project declares Python `>=3.13` and a full dependency set in `pyproject.toml`/`uv.lock`. `requirements.txt` is a smaller legacy Streamlit list and does not cover every import used by the main pipelines.

```bash
git clone https://github.com/TDVamit/big_ocr.git
cd big_ocr

# Recommended when using uv
uv sync
source .venv/bin/activate

# Or install the declared project dependencies with pip
python -m pip install -e .
```

The image-assisted Google Vision path also relies on Poppler through `pdf2image`; install the platform package if PDF rendering cannot find `pdftoppm`.

## Credential configuration

Keep credentials outside the repository. Use a local, ignored `.env` file or your secret manager and export only placeholders in documentation and shell history:

```bash
export OPENAI_API_KEY="<your-openai-api-key>"
export GEMINI_API_KEY="<your-gemini-api-key>"
export MISTRAL_API_KEY="<your-mistral-api-key>"
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/google-service-account.json"
```

For Google Cloud Vision, the service account must have the permissions required to use Vision and create/read/delete the temporary Cloud Storage buckets used by `modules/google_pdf_ocr.py`. Do not commit the JSON key file. The current helper code still contains legacy credential assumptions, so verify the environment and remove any embedded or hard-coded credential fallback before production use; rotate any credential that may have been exposed in repository history.

## Usage

### Streamlit review app

```bash
streamlit run streamlit-frontend.py
# or use the launcher (it starts Streamlit on port 8501)
python run_streamlit.py
```

In the sidebar, upload a PDF, choose one of `OCR-based`, `Vision-based`, or `Image-based`, choose cache reuse, and click **Start Processing**. The UI runs the selected async pipeline and displays the generated JSON-backed results.

### Command line pipelines

```bash
python main.py path/to/document.pdf --no-cache
python main_vision.py path/to/document.pdf --no-cache
python main_image.py path/to/document.pdf --no-cache
```

The scripts also expose async `main_async(...)` functions for programmatic use. Cache behavior and padding-page behavior can be controlled through those function arguments; command-line parsing currently supports a PDF path and `--no-cache`.

## Repository map

```text
main.py                 OCR/relevance/categorization/field-extraction pipeline
main_vision.py          OpenAI vision-first pipeline
main_image.py           OCR plus rendered-image extraction pipeline
streamlit-frontend.py   Interactive upload and results UI
modules/                Provider calls and extraction stages
utils/                  Provider, schema, image, and page helpers
schema.json             Insurance field schema
json/                   Runtime caches and sample result artifacts
```

## Limitations and next steps

- No automated tests are present; verification is currently manual and provider-dependent.
- The supported UI input is PDF only; general image/document uploads are not exposed by the frontend.
- Provider calls are networked and can incur usage charges; the displayed estimate is model- and path-specific.
- The Google Cloud path creates temporary buckets and requires cleanup permissions.
- Several dependency and launcher references are legacy or incomplete (for example, the launcher checks for a `streamlit_requirements.txt` file that is not present in the repository). Treat `pyproject.toml` as the authoritative dependency declaration and validate the selected path in a clean environment.
- There is no verified deployment URL or hosted demo in the repository metadata.

## License

No license file is currently present. Confirm the intended license before distributing or using this project as a dependency.
