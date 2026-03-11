import re
from paddleocr import PaddleOCR

_ocr = None


def get_ocr():
    """Lazy-initialize PaddleOCR (downloads models on first run)."""
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(
            text_detection_model_name="PP-OCRv4_mobile_det",
            text_recognition_model_name="PP-OCRv4_mobile_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
        )
    return _ocr


def extract_text(image_path):
    """Run OCR on an image and return a list of recognized text lines."""
    ocr = get_ocr()
    results = ocr.predict(input=image_path)

    text_lines = []
    for result in results:
        # PaddleOCR result is dict-like with 'rec_texts' key
        rec_texts = result.get("rec_texts", [])
        text_lines.extend(rec_texts)

    return text_lines


# Patterns to strip from OCR text
_DOSAGE_RE = re.compile(
    r"\b\d+\s*(mg|ml|mcg|g|iu|units?|tablets?|caps?|capsules?|%)\b",
    re.IGNORECASE,
)
_FREQUENCY_RE = re.compile(
    r"\b(od|bd|bid|tid|tds|qid|qds|prn|sos|hs|stat|daily|weekly|"
    r"once|twice|thrice|morning|evening|night|before|after|meals?|"
    r"breakfast|lunch|dinner|hours?|days?|weeks?)\b",
    re.IGNORECASE,
)
_ROUTE_RE = re.compile(
    r"\b(po|iv|im|sc|sl|pr|topical|oral|inhalation|nasal|tab|cap)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\b\d+[.\d]*\b")
# OCR sometimes reads 't' as '+' - clean that up
_OCR_PLUS_RE = re.compile(r"\+(?=\w)")

_NOISE_WORDS = {
    "dr", "doctor", "patient", "name", "age", "date", "rx", "sig",
    "refill", "refills", "qty", "quantity", "disp", "dispense",
    "take", "apply", "use", "inject", "supply",
    "pharmacy", "prescription", "diagnosis", "address", "phone",
    "tel", "dob", "sex", "male", "female", "weight", "height",
    "hospital", "clinic", "medical", "center", "centre", "dept", "department",
    "reg", "registration", "license", "signature", "stamp", "label",
    "mr", "mrs", "ms", "no", "number", "the", "for", "and", "with",
    "street", "city", "state", "usa", "york", "new", "newyork",
    "riverside", "riversidemedicalcentre", "dreamstime", "com",
}

# Patterns that indicate a line is NOT a medicine (addresses, names, headers)
_SKIP_PATTERNS = [
    re.compile(r"\b\d{2,5}\s*(street|st|ave|road|rd|blvd)\b", re.IGNORECASE),
    re.compile(r"\b(dr\.|dr\s)\s*\w+\s+\w+", re.IGNORECASE),  # Doctor names
    re.compile(r"\b\d{2}[-/]\d{2}[-/]\d{2,4}\b"),  # Dates
    re.compile(r"\b[A-Z]{2}\s*\d{5}\b"),  # ZIP codes
    re.compile(r"\w+\.(com|org|net)\b", re.IGNORECASE),  # URLs
    re.compile(r"^(NAME|AGE|DATE|ADDRESS|LABEL|REFILL|ID)\b", re.IGNORECASE),  # Field labels
]


def _looks_like_prescription_line(line):
    """Check if a line looks like a prescription entry."""
    indicators = [
        r"\d+\s*(mg|ml|mcg|g|iu)\b",
        r"(od|bd|bid|tid|tds|qid|qds|prn)",
        r"(tab|cap|tabs|caps)",
        r"[A-Za-z]{4,}\s+\d+",  # Word followed by number (e.g. "Cimetidine 50")
    ]
    for pattern in indicators:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def extract_medicine_candidates(text_lines):
    """
    From raw OCR text lines, extract substrings likely to be medicine names.
    Only processes lines that look like prescription entries (contain dosage/frequency).
    """
    candidates = []

    for line in text_lines:
        # Skip lines that match noise patterns
        if any(p.search(line) for p in _SKIP_PATTERNS):
            continue

        # Skip very short lines
        if len(line.strip()) < 4:
            continue

        # Only process lines that look like prescriptions
        if not _looks_like_prescription_line(line):
            continue

        # Fix OCR artifact: '+' often misread for 't'
        line = _OCR_PLUS_RE.sub("t", line)

        # Insert spaces at letter-digit and digit-letter boundaries
        # "Betaloc100mg" -> "Betaloc 100mg", "2tabsBID" -> "2 tabs BID"
        line = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", line)
        line = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", line)

        # Split on common delimiters
        parts = re.split(r"[,;\t\n|]|\d+[.)]\s*", line)
        for part in parts:
            cleaned = part.strip()
            # Remove dosage, frequency, route, numbers
            cleaned = _DOSAGE_RE.sub("", cleaned)
            cleaned = _FREQUENCY_RE.sub("", cleaned)
            cleaned = _ROUTE_RE.sub("", cleaned)
            cleaned = _NUMBER_RE.sub("", cleaned)
            # Remove stray punctuation and non-alpha junk
            cleaned = re.sub(r"[/\-]+", " ", cleaned)
            # Collapse whitespace
            cleaned = " ".join(cleaned.split()).strip()

            # Strip known medical abbreviations that OCR glues together
            # e.g. "tabBID" -> "", "tabsTD" -> ""
            cleaned = re.sub(
                r"(tabs?|caps?)(BID|TID|TDS|QID|QDS|OD|BD|QD|PRN)\b",
                "", cleaned, flags=re.IGNORECASE
            )
            # Strip trailing frequency/route words
            cleaned = re.sub(
                r"\s+(BID|TID|TDS|QID|QDS|OD|BD|QD|PRN|tabs?|caps?)\s*$",
                "", cleaned, flags=re.IGNORECASE
            )
            cleaned = " ".join(cleaned.split()).strip()

            # Extract just the leading alphabetic word(s) as the medicine name
            match = re.match(r"^([A-Za-z][A-Za-z\s/]*[A-Za-z])", cleaned)
            if match:
                name = match.group(1).strip()
                if len(name) >= 3 and name.lower() not in _NOISE_WORDS:
                    candidates.append(name)

    return candidates
