import cv2
import pytesseract
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

IMAGE_PATH = PROJECT_DIR / "roi" / "lap_roi.jpg"

pytesseract.pytesseract.tesseract_cmd = r"D:\Licenta\Tesseract-OCR\tesseract.exe"

img = cv2.imread(str(IMAGE_PATH))

if img is None:
    print("Nu s-a putut citi imaginea.")
    print("IMAGE_PATH =", IMAGE_PATH)
    exit()

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray = cv2.resize(gray, None, fx=2, fy=2)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

text = pytesseract.image_to_string(thresh, config="--psm 6")

print("Text OCR brut:")
print(repr(text))

match = re.search(r'(\d+)\s*/\s*(\d+)', text)

if match:
    current_lap = int(match.group(1))
    total_laps = int(match.group(2))
    print("Lap curent:", current_lap)
    print("Total ture:", total_laps)
else:
    print("Nu s-a gasit formatul lap/total.")

cv2.imwrite(str(PROJECT_DIR / "roi" / "lap_thresh_debug.jpg"), thresh)
