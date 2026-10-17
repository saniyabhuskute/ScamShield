import re
import threading
from urllib.parse import urlparse

import httpx

from backend.config import settings


URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\]\[(){}\"']+")
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "ow.ly"}
TERMS = {
    "Urgency or account threat": ("urgent", "immediately", "blocked", "suspend", "expire", "आज ही", "तुरंत", "बंद", "तात्काळ", "खाते बंद"),
    "Sensitive information request": ("otp", "password", "pin", "cvv", "पासवर्ड", "ओटीपी", "पिन", "गुप्तशब्द"),
    "Payment or prize request": ("payment", "pay now", "won", "prize", "fee", "भुगतान", "इनाम", "पैसे", "पेमेंट", "बक्षीस", "शुल्क"),
}
ADVICE = {
    "en": "Do not reply, open links, or share OTPs, passwords, PINs, or payment details. Contact the organization using its official app or a number you find independently.",
    "hi": "जवाब न दें, लिंक न खोलें और OTP, पासवर्ड, PIN या भुगतान की जानकारी साझा न करें। संस्था से उसके आधिकारिक ऐप या स्वयं खोजे गए नंबर पर संपर्क करें।",
    "mr": "उत्तर देऊ नका, लिंक उघडू नका आणि OTP, पासवर्ड, PIN किंवा पेमेंटची माहिती शेअर करू नका. संस्थेशी तिच्या अधिकृत ॲपवरून किंवा तुम्ही स्वतंत्रपणे शोधलेल्या नंबरवर संपर्क साधा.",
    "und": "Do not reply or share private information. Choose the message language manually and scan again.",
}
SAFE_REPLY_STEPS = {
    "en": [
        "Do not reply, open links, or share OTPs, PINs, passwords, or payment details.",
        "Block the sender. Report the suspicious number or message at cybercrime.gov.in.",
        "If money was lost or a transaction was unauthorized, call 1930 immediately and report it at cybercrime.gov.in.",
    ],
    "hi": [
        "जवाब न दें, लिंक न खोलें और OTP, PIN, पासवर्ड या भुगतान की जानकारी साझा न करें।",
        "भेजने वाले को ब्लॉक करें। संदिग्ध नंबर या संदेश की रिपोर्ट cybercrime.gov.in पर करें।",
        "अगर पैसे कटे हैं या अनधिकृत लेन-देन हुआ है, तो तुरंत 1930 पर कॉल करें और cybercrime.gov.in पर रिपोर्ट करें।",
    ],
    "mr": [
        "उत्तर देऊ नका, लिंक उघडू नका आणि OTP, PIN, पासवर्ड किंवा पेमेंटची माहिती शेअर करू नका.",
        "पाठवणाऱ्याला ब्लॉक करा. संशयास्पद नंबर किंवा संदेशाची तक्रार cybercrime.gov.in वर करा.",
        "पैसे गेले असतील किंवा अनधिकृत व्यवहार झाला असेल, तर त्वरित 1930 वर कॉल करा आणि cybercrime.gov.in वर तक्रार नोंदवा.",
    ],
}

_marathi_model_lock = threading.Lock()
_marathi_tokenizer = None
_marathi_model = None
_marathi_device = None


def safety_advice(language: str) -> str:
    return ADVICE.get(language, ADVICE["en"])


def safe_reply_coach(language: str, risk: str) -> list[str]:
    if risk not in {"High", "Medium"}:
        return []
    return SAFE_REPLY_STEPS.get(language, SAFE_REPLY_STEPS["en"])


def extract_urls(message: str) -> list[str]:
    found = []
    for match in URL_RE.findall(message):
        cleaned = match.rstrip(".,!?;:")
        if cleaned not in found:
            found.append(cleaned)
    return found


def analyze_message(original: str, translated: str | None = None) -> tuple[list[str], list[str], float, str]:
    combined = f"{original}\n{translated or ''}".casefold()
    signals = [name for name, terms in TERMS.items() if any(term in combined for term in terms)]
    urls = extract_urls(original)
    risky_link = False
    for item in urls:
        candidate = item if item.lower().startswith(("http://", "https://")) else f"http://{item}"
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").casefold()
        is_ip = bool(host) and all(part.isdigit() for part in host.split("."))
        if parsed.scheme != "https" or host in SHORTENERS or "xn--" in host or is_ip or "@" in parsed.netloc:
            risky_link = True
    if urls:
        signals.append("Link detected")
    if risky_link:
        signals.append("Potentially risky link")
    strong = {"Sensitive information request", "Payment or prize request", "Potentially risky link"}
    strong_count = sum(signal in strong for signal in signals)
    score = min(0.94, 0.12 + 0.18 * len(signals) + (0.22 if strong_count else 0))
    risk = "High" if strong_count >= 2 else "Medium" if signals else "Low"
    return signals, urls, score, risk


def _mask_urls(message: str) -> tuple[str, list[tuple[str, str]]]:
    protected = []

    def mask_url(match):
        token = f"SCAMSHIELDURLTOKEN{len(protected)}END"
        protected.append((token, match.group(0)))
        return token

    return URL_RE.sub(mask_url, message), protected


def _restore_urls(translated: str, protected: list[tuple[str, str]]) -> str:
    for token, original in protected:
        translated = re.sub(re.escape(token), lambda _: original, translated, flags=re.IGNORECASE)
    if any(token.casefold() in translated.casefold() for token, _ in protected):
        raise ValueError("Translation provider did not preserve a URL marker.")
    return translated.strip()


def _load_marathi_translator():
    global _marathi_tokenizer, _marathi_model, _marathi_device
    if _marathi_model is not None:
        return _marathi_tokenizer, _marathi_model, _marathi_device
    if not settings.marathi_translation_model:
        raise RuntimeError("Marathi translation is not configured.")
    with _marathi_model_lock:
        if _marathi_model is not None:
            return _marathi_tokenizer, _marathi_model, _marathi_device
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            _marathi_device = "cuda" if torch.cuda.is_available() else "cpu"
            _marathi_tokenizer = AutoTokenizer.from_pretrained(settings.marathi_translation_model)
            _marathi_tokenizer.src_lang = "mar_Deva"
            _marathi_model = AutoModelForSeq2SeqLM.from_pretrained(settings.marathi_translation_model)
            _marathi_model.to(_marathi_device)
            _marathi_model.eval()
        except Exception as exc:
            _marathi_tokenizer = _marathi_model = _marathi_device = None
            raise RuntimeError(
                "The local Marathi translation model could not load. On its first use, "
                "ScamShield downloads the model from Hugging Face; check internet access, "
                "available disk space, and the installed PyTorch/Transformers packages."
            ) from exc
    return _marathi_tokenizer, _marathi_model, _marathi_device


def _translate_marathi(message: str) -> str:
    tokenizer, model, device = _load_marathi_translator()
    import torch

    masked, protected = _mask_urls(message)
    try:
        encoded = tokenizer(masked, return_tensors="pt", truncation=True, max_length=512)
        encoded = {key: value.to(device) for key, value in encoded.items()}
        english_token_id = tokenizer.convert_tokens_to_ids("eng_Latn")
        if english_token_id is None or english_token_id == tokenizer.unk_token_id:
            raise ValueError("The Marathi translator tokenizer has no English target token.")
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                forced_bos_token_id=english_token_id,
                max_new_tokens=512,
                num_beams=4,
            )
        translated = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
        if not translated.strip():
            raise ValueError("The Marathi translator returned an empty translation.")
        return _restore_urls(translated, protected)
    except Exception as exc:
        if isinstance(exc, RuntimeError) and "local Marathi translation model" in str(exc):
            raise
        raise RuntimeError("Marathi translation failed while processing this message.") from exc


def marathi_translation_state() -> str:
    if _marathi_model is not None:
        return "ready"
    return "on_demand" if settings.marathi_translation_model else "not_configured"


def translate_message(message: str, source_language: str) -> str:
    if source_language == "mr":
        return _translate_marathi(message)
    if not settings.translation_url:
        raise RuntimeError("Hindi translation is not configured.")
    masked, protected = _mask_urls(message)
    payload = {"q": masked, "source": source_language, "target": "en", "format": "text"}
    if settings.translation_api_key:
        payload["api_key"] = settings.translation_api_key
    response = httpx.post(
        settings.translation_url,
        json=payload,
        timeout=settings.translation_timeout,
    )
    response.raise_for_status()
    result = response.json()
    translated = result.get("translatedText") if isinstance(result, dict) else None
    if not isinstance(translated, str) or not translated.strip():
        raise ValueError("LibreTranslate response must include a non-empty 'translatedText'.")
    return _restore_urls(translated, protected)
