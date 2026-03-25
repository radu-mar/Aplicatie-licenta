import cv2
import pytesseract
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

IMAGE_PATH = PROJECT_DIR / "roi" / "gap_roi.jpg"

pytesseract.pytesseract.tesseract_cmd = r"D:\Licenta\Tesseract-OCR\tesseract.exe"


def clean_line(line: str) -> str:
    line = line.strip().upper()
    line = line.replace(",", ".")
    line = re.sub(r"[^A-Z0-9+.\s]", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def parse_gap_value(cleaned_line: str):
    if not cleaned_line:
        return None

    if cleaned_line == "L":
        return {"type": "LEADER", "value": "LEADER"}

    if cleaned_line == "I":
        return {"type": "INTERVAL", "value": "INTERVAL"}

    m = re.search(r"\+?(\d+\.\d{1,3})", cleaned_line)
    if m:
        return {"type": "GAP", "value": float(m.group(1))}

    digits_only = re.sub(r"[^\d]", "", cleaned_line)
    if len(digits_only) >= 4:
        candidate = float(f"{digits_only[:-3]}.{digits_only[-3:]}")
        return {"type": "GAP", "value": candidate}

    return {"type": "UNKNOWN", "value": None}


img = cv2.imread(str(IMAGE_PATH))

if img is None:
    print("Nu s-a putut citi imaginea.")
    print("IMAGE_PATH =", IMAGE_PATH)
    exit()

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray = cv2.resize(gray, None, fx=3, fy=3)
_, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)

debug_path = PROJECT_DIR / "roi" / "gap_thresh_debug.jpg"
cv2.imwrite(str(debug_path), thresh)

custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=LI+0123456789. '

text = pytesseract.image_to_string(thresh, config=custom_config)

print("Text OCR brut:")
print(repr(text))
print("\nLinii detectate:")

lines = text.splitlines()
parsed_results = []

for idx, raw_line in enumerate(lines, start=1):
    if not raw_line.strip():
        continue

    cleaned = clean_line(raw_line)
    parsed = parse_gap_value(cleaned)

    if parsed is None:
        continue

    result = {
        "raw": raw_line,
        "cleaned": cleaned,
        "type": parsed["type"],
        "value": parsed["value"]
    }
    parsed_results.append(result)

    print(
        f"{idx}. raw={raw_line!r} | cleaned={cleaned!r} "
        f"-> type={parsed['type']}, value={parsed['value']}"
    )

print("\nRezultate finale:")
for item in parsed_results:
    print(item)