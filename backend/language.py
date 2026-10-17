import re

from langdetect import DetectorFactory, LangDetectException, detect_langs


DetectorFactory.seed = 0

# Marathi and Hindi share Devanagari, so generic language detection often
# mistakes short Marathi messages for Hindi. These common Marathi forms give
# the detector a deterministic signal for the phrases it otherwise confuses.
MARATHI_MARKERS = {
    "आहे", "आहेत", "नाही", "माझा", "माझी", "माझे", "तुमचा", "तुमची",
    "तुमचे", "आपला", "आपली", "आपले", "कृपया", "सांगा", "मिळवा",
}


def detect_language(message: str, requested: str) -> tuple[str, float | None]:
    if requested != "auto":
        return requested, 1.0
    words = set(re.findall(r"\w+", message.casefold()))
    if words & MARATHI_MARKERS:
        return "mr", 0.95
    try:
        ranked = detect_langs(message)
    except LangDetectException:
        return "und", 0.0
    if not ranked:
        return "und", 0.0
    best = ranked[0]
    confidence = float(best.prob)
    if confidence < 0.70:
        return "und", confidence
    return str(best.lang), confidence
