# ScamShield

ScamShield is a local message safety dashboard built with React, Tailwind CSS, and FastAPI. The API stores scan history and feedback in a versioned SQLite database, detects supported languages, applies message warning signals, and can use a local LibreTranslate service before running an English-language classifier.

## Run locally

Use two terminals from this folder.

### FastAPI

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn backend.main:app --reload --reload-dir backend --host 127.0.0.1 --port 8001
```

### React + Tailwind

```powershell
npm install
npm run dev -- --host=127.0.0.1 --strictPort
```

Open `http://localhost:5175`. Vite forwards `/api` requests to FastAPI on port 8001. Interactive API documentation is available at `http://localhost:8001/docs`.

The database is created automatically at `backend/data/scamshield.db` on first startup. It uses SQLite write-ahead logging for reliable local reads and writes; scan results (including any translation) and one feedback response per scan are saved transactionally. Schema migrations preserve existing scan history. Set `SCAMSHIELD_DATABASE_PATH` in `.env` to move the database. Back up the database file when the app is stopped so scan history can be restored.

## API used by the frontend

- `POST /api/scan` — validate, detect/override language, translate when configured, classify or run explicitly marked demo rules, fuse warning signals, and persist the result.
- `GET /api/scans?limit=50` — return recent saved scans.
- `GET /api/insights` — return totals and risk distribution across the local scan database.
- `POST /api/feedback` — save/update optional feedback for a scan.
- `GET /api/health` — report API, model, translation, and database state, including SQLite integrity and schema version.

Scans contain the original message and are saved locally in `backend/data/scamshield.db`. The frontend shows the risk estimate, warning signals, URL findings, localized safety recommendation, and any analysis limitation. Unsupported or uncertain languages and unavailable translation/model steps are reported instead of being represented as a successful model analysis.

## Trained model integration

The supplied model is already in `scamshield_roberta/`; that directory is the backend default. It contains the RoBERTa sequence-classification config, safe-tensors weights, and tokenizer files. The config maps `SCAM` to class 1 and `LEGITIMATE` to class 0, so no label override is needed. Install the model dependencies into the Python environment used to run FastAPI:

```powershell
pip install -r backend\requirements-model.txt
```

Restart FastAPI to load it. The model loads from local files only, on CPU by default (or CUDA when detected). Set `SCAMSHIELD_MODEL_DEVICE=cpu` or `cuda` to override the device; set `SCAMSHIELD_MODEL_DIR` only if you move the directory. The API returns the model label and scam score, stores them in SQLite, and the frontend displays the label and score with the scan result.

If the model cannot load, the API reports a degraded model state. English scans use clearly marked demo rules only when the model is not configured; non-English scans use the English model only after a successful translation.

## Translation services

Hindi uses the local LibreTranslate service. Its self-hosted setup is free and does not require an API key. In a separate terminal, install and run it:

```powershell
python -m venv .lt-venv
.\.lt-venv\Scripts\Activate.ps1
pip install libretranslate
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
.\.lt-venv\Scripts\libretranslate.exe --host 127.0.0.1 --port 5010 --load-only en,hi
```

The backend defaults to `http://127.0.0.1:5010/translate`. Set `TRANSLATION_API_URL` and, if needed, `TRANSLATION_API_KEY` in `.env` to use another LibreTranslate endpoint. LibreTranslate does not currently provide the Marathi-to-English language pair in this local setup, so ScamShield routes Marathi to a local NLLB translation model instead. The NLLB model downloads automatically from Hugging Face on the first Marathi scan and is cached for later scans. It needs internet access and several GB of free disk space on first use; set `SCAMSHIELD_MARATHI_TRANSLATION_MODEL` to a local model directory if you have already downloaded the weights. See the [LibreTranslate supported language models](https://github.com/LibreTranslate/Documentation/blob/main/src/content/docs/guides/supported_languages.md) and [NLLB model card](https://huggingface.co/facebook/nllb-200-distilled-600M), which lists Marathi (`mar_Deva`) and English (`eng_Latn`) among its languages. NLLB is released under CC-BY-NC-4.0, so check that license before any commercial deployment.

For Hindi, ScamShield sends LibreTranslate a JSON request with `q`, `source: "hi"`, and `target: "en"`. For Marathi, it loads NLLB with Marathi (`mar_Deva`) as the source and English (`eng_Latn`) as the target. The English result is passed to the ScamShield classifier, and warning signals are checked against both original and translated text. The frontend displays the translation under the scan result, and SQLite saves it with the scan. URLs are masked during translation and restored in the result. LibreTranslate uses its [documented API format](https://docs.libretranslate.com/guides/api_usage/); the Marathi model runs locally after its initial download, so message text is not sent to a translation provider.

The Hindi and Marathi safety messages in `backend/pipeline.py` are starter copy and should be reviewed by fluent speakers before release. Hindi translation uses the separate LibreTranslate service; the trained ScamShield classifier remains a separate optional integration.
