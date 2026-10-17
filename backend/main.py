from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import settings
from backend.language import detect_language
from backend.model_service import ModelLoadError, ScamModel
from backend.pipeline import analyze_message, marathi_translation_state, safe_reply_coach, safety_advice, translate_message
from backend.storage import Database, DatabaseError


database = Database(settings.database_path)


def _translation_health() -> str:
    hindi_state = _hindi_translation_health()
    marathi_state = marathi_translation_state()
    if hindi_state == "available" or marathi_state in {"ready", "on_demand"}:
        return "available"
    return "not_configured" if hindi_state == "not_configured" and marathi_state == "not_configured" else "unavailable"


def _hindi_translation_health() -> str:
    if not settings.translation_url:
        return "not_configured"
    parsed = urlsplit(settings.translation_url)
    path = parsed.path.rsplit("/translate", 1)[0] + "/languages"
    health_url = urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    try:
        response = httpx.get(health_url, timeout=1.5)
        if not response.is_success:
            return "unavailable"
        languages = response.json()
        if not isinstance(languages, list):
            return "unavailable"
        supports_hindi = any(
            isinstance(item, dict)
            and item.get("code") == "hi"
            and any(pair == "en" or (isinstance(pair, dict) and pair.get("target") == "en") for pair in item.get("targets", []))
            for item in languages
        )
        return "available" if supports_hindi else "unsupported"
    except (httpx.HTTPError, ValueError):
        return "unavailable"


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.initialize()
    app.state.model = None
    app.state.model_state = "not_configured"
    app.state.model_error = None
    if settings.model_configured:
        try:
            app.state.model = ScamModel.load(settings.model_path, settings.model_device, settings.scam_label_id)
            app.state.model_state = "ready"
        except ModelLoadError as exc:
            app.state.model_state = "error"
            app.state.model_error = str(exc)
    yield


app = FastAPI(title="ScamShield API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5175", "http://127.0.0.1:5175",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ScanRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    language: Literal["auto", "en", "hi", "mr"] = "auto"


class FeedbackRequest(BaseModel):
    scan_id: str
    helpful: Literal["yes", "somewhat", "no"]


def _result_for_uncertain(message: str, language: str, status: str, notice: str) -> dict:
    signals, urls, _, risk = analyze_message(message)
    return {
        "risk": risk,
        "score": None,
        "signals": signals,
        "urls": urls,
        "mode": "unavailable",
        "analysis_status": status,
        "notice": notice,
        "recommendation": safety_advice(language),
        "translated_message": None,
        "detected_language": language,
        "model_label": None,
        "score_kind": None,
    }


@app.get("/api/health")
def health():
    model_state = getattr(app.state, "model_state", "not_configured")
    try:
        database_health = database.health()
    except DatabaseError:
        database_health = {"status": "unavailable", "engine": "sqlite"}
    api_status = "ok" if model_state != "error" and database_health["status"] == "ok" else "degraded"
    return {
        "status": api_status,
        "service": "ScamShield API",
        "model": model_state,
        "translation": _translation_health(),
        "translation_languages": {
            "hi": _hindi_translation_health(),
            "mr": marathi_translation_state(),
        },
        "database": database_health,
    }


@app.post("/api/scan")
def scan(request: ScanRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be blank.")

    detected, confidence = detect_language(message, request.language)
    model = getattr(app.state, "model", None)
    model_state = getattr(app.state, "model_state", "not_configured")
    translated_text = None
    translation_notice = None

    if detected == "und":
        result = _result_for_uncertain(
            message, detected, "uncertain_language",
            "The language could not be identified reliably. Choose English, Hindi, or Marathi and try again.",
        )
    elif detected not in {"en", "hi", "mr"}:
        result = _result_for_uncertain(
            message, detected, "unsupported_language",
            "This language is not supported yet. Choose English, Hindi, or Marathi to continue.",
        )
    else:
        analysis_text = message
        translation_status = "not_needed"
        if detected != "en":
            if settings.translation_url:
                try:
                    translated_text = translate_message(message, detected)
                    analysis_text = translated_text
                    translation_status = "translated"
                except Exception as exc:
                    translation_status = "failed"
                    translation_notice = (
                        f"{exc} The English classifier was not used; showing warning signals only."
                        if detected == "mr"
                        else "Translation failed, so the English classifier was not used. Showing only warning signals."
                    )
            else:
                translation_status = "not_configured"
                translation_notice = "Translation is not configured. Showing warning signals only; the English model was not used."

        signals, urls, demo_score, _ = analyze_message(message, translated_text)
        model_output = None
        if model_state == "error":
            translation_notice = getattr(app.state, "model_error", None) or "The configured model could not be loaded."
        elif model is not None and (detected == "en" or translated_text is not None):
            try:
                model_output = model.predict(analysis_text)
            except Exception:
                translation_notice = "The model could not analyze this message. Showing warning signals only."

        if model_output:
            score = model_output["scam_score"]
            mode, score_kind, model_label = "model", "model_estimate", model_output["label"]
            notice = translation_notice or "Model score is an estimate, not a calibrated probability. Review the warning signals too."
            risk = _fused_risk(score, signals)
            analysis_status = "analyzed"
        elif model_state == "error":
            score, mode, score_kind, model_label = None, "unavailable", None, None
            notice = translation_notice
            risk, analysis_status = _risk_from_signals(signals), "model_unavailable"
        elif detected != "en" and translation_status != "translated":
            score, mode, score_kind, model_label = None, "signals_only", None, None
            notice = translation_notice or "The model could not analyze this language. Showing warning signals only."
            risk = _risk_from_signals(signals)
            analysis_status = "translation_unavailable" if translation_status == "not_configured" else "translation_failed"
        else:
            score, mode, score_kind, model_label = demo_score, "demo", "rule_based_estimate", None
            notice = "Demo rules only; no trained model is loaded. This score is not a validated probability."
            if translation_notice:
                notice = f"{translation_notice} {notice}"
            risk, analysis_status = _fused_risk(score, signals), "demo"

        result = {
            "risk": risk,
            "score": score,
            "signals": signals,
            "urls": urls,
            "mode": mode,
            "analysis_status": analysis_status,
            "notice": notice,
            "recommendation": safety_advice(detected),
            "translated_message": translated_text,
            "detected_language": detected,
            "model_label": model_label,
            "score_kind": score_kind,
        }

    result["safe_reply_coach"] = safe_reply_coach(detected, result["risk"])
    record = {
        "id": str(uuid4()),
        "message": message,
        "language": detected,
        "requested_language": request.language,
        "risk": result["risk"],
        "score": result["score"],
        "signals": result["signals"],
        "urls": result["urls"],
        "mode": result["mode"],
        "analysis_status": result["analysis_status"],
        "notice": result["notice"],
        "recommendation": result["recommendation"],
        "translated_message": result.get("translated_message"),
        "model_label": result.get("model_label"),
        "score_kind": result.get("score_kind"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "language_confidence": confidence,
    }
    try:
        database.save_scan(record)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return record


def _fused_risk(score: float, signals: list[str]) -> str:
    strong = {"Sensitive information request", "Payment or prize request", "Potentially risky link"}
    strong_count = sum(signal in strong for signal in signals)
    if score >= 0.80 or (score >= 0.55 and strong_count >= 1):
        return "High"
    if score >= 0.38 or signals:
        return "Medium"
    return "Low"


def _risk_from_signals(signals: list[str]) -> str:
    strong = {"Sensitive information request", "Payment or prize request", "Potentially risky link"}
    if sum(signal in strong for signal in signals) >= 2:
        return "High"
    return "Medium" if signals else "Low"


@app.get("/api/scans")
def get_scans(limit: int = Query(default=50, ge=1, le=200)):
    try:
        return {"scans": database.list_scans(limit)}
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/insights")
def get_insights():
    try:
        return database.insights()
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/feedback")
def save_feedback(request: FeedbackRequest):
    try:
        saved = database.save_feedback(request.scan_id, request.helpful)
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not saved:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return {"saved": True, "scan_id": request.scan_id, "helpful": request.helpful}
