import cv2
import pytesseract
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

IMAGE_PATH = PROJECT_DIR / "roi" / "leaderboard_roi.jpg"

pytesseract.pytesseract.tesseract_cmd = r"D:\Licenta\Tesseract-OCR\tesseract.exe"

VALID_DRIVERS = {
    "VER", "PER", "HAM", "RUS", "LEC", "SAI", "ALO", "STR",
    "NOR", "PIA", "OCO", "GAS", "ALB", "SAR", "BOT", "ZHO",
    "MAG", "HUL", "TSU", "DEV", "RIC", "LAW"
}

img = cv2.imread(str(IMAGE_PATH))

if img is None:
    print("Nu s-a putut citi imaginea.")
    print("IMAGE_PATH =", IMAGE_PATH)
    exit()

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray = cv2.resize(gray, None, fx=2, fy=2)
_, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

text = pytesseract.image_to_string(thresh, config="--psm 6")

print("Text OCR brut:")
print(text)

lines = text.splitlines()

found_drivers = []

for line in lines:
    tokens = re.findall(r"[A-Z0-9]{3}", line.upper())

    for token in tokens:
        token = token.replace("0", "O")

        if token in VALID_DRIVERS and token not in found_drivers:
            found_drivers.append(token)

print("Piloti detectati:")
print(found_drivers)