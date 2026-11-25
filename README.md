# AEMS - Automated Effort Estimation API

REST API that reads a software use case (name, description, actors, basic flow, alternate flow)
and returns Function Point Analysis (FPA) metrics: complexity, record/data element types for
internal files (ILF), inputs (EI) and inquiries (EQ), plus the derived counts.

## Problem

Counting function points by hand from requirement documents is slow and inconsistent between
estimators. This service produces a first-draft FPA breakdown in one API call. A human reviews it.

## How it works

1. **Model:** Phi-3.5-mini-instruct fine-tuned with QLoRA (LoRA rank 32) on ~290 use cases
   (real project data plus synthetic examples), then exported to a 4-bit GGUF file for CPU inference.
2. **Output design:** the model lists the data fields it finds (`IlfDataElements`, `EiDataElements`,
   `EqDataElements`) instead of guessing counts. The API computes `IlfDet`, `EiDet`, `EqDet`
   as list lengths, and `Multiplier`/`Result` from `Complexity` (Simple 5, Average 10, Complex 15).
3. **Service:** FastAPI + llama-cpp-python, packaged in Docker, deployed on Google Cloud Run.

```
Client -> HTTPS (Cloud Run) -> Docker container [ FastAPI -> llama.cpp + GGUF model -> post-processing ] -> JSON
```

## Repo layout

```
app.py                 FastAPI service
Dockerfile             container recipe
requirements.txt       runtime dependencies
tests/test_api.py      tests (use a fake model, no weights needed)
sample_request.json    example input
Export_to_GGUF.ipynb   Colab notebook: trained adapter -> models/aems-q4.gguf
models/                put aems-q4.gguf here (NOT in git, ~2.4 GB)
.gcloudignore          makes sure the model file IS uploaded to Cloud Build
```

## Get the model file

The weights are not in this repo (too large for GitHub).
Run `Export_to_GGUF.ipynb` in Colab, download `aems-q4.gguf` from Google Drive and place it at
`models/aems-q4.gguf`. <!-- add your own download link here if you host the file -->

## Run locally with Docker

```bash
docker build -t aems-api .
docker run --rm -p 8080:8080 aems-api
```

Open http://localhost:8080/docs and use **Try it out** on `POST /analyze`, or:

```bash
curl -X POST http://localhost:8080/analyze -H "Content-Type: application/json" -d @sample_request.json
```

(Windows PowerShell: use `curl.exe`.) Give Docker Desktop at least 6 GB of memory.

## API

`GET /health` - returns `{"status": "ok", "model_loaded": true}`

`POST /analyze` - body fields: `use_case_name`, `operation`, `description`, `actors`,
`basic_flow`, `alternate_flow` (may be empty), optional `fpid`. Add `?debug=true` to also get the raw model text.

Response: `metrics` (all FPA fields + computed counts), `review_notes`, `inference_seconds`.

Errors: `422` missing field, `413` input too long, `502` model output unreadable, `503` model still loading.

## Deploy to Google Cloud Run

```bash
gcloud run deploy aems-api --source . --region us-central1 \
  --memory 8Gi --cpu 4 --concurrency 1 --timeout 900 --max-instances 2 \
  --allow-unauthenticated
```

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

## Measured accuracy (29 held-out use cases)

| Output | Result |
|---|---|
| Valid JSON | 29 / 29 |
| Complexity | 90% correct |
| OS Operation | 100% correct |
| IlfRet / EiRet / EqRet exact | 83% / 59% / 86% |
| Avg error in field count (ILF / EI / EQ) | 1.69 / 1.38 / 4.69 |

Small evaluation set: treat these as indicative, not final. EQ is the weakest part.

## Limitations

- Draft output only; review the field lists, especially EQ.
- CPU inference is slow (expect on the order of a minute per request; measure and record yours).
- First request after idle time is slower (cold start: the container loads the model).
- Do not send confidential documents to a public endpoint.
