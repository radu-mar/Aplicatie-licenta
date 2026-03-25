import cv2
import pytesseract
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

IMAGE_PATH = PROJECT_DIR / "roi" / "sc_roi.jpg"

pytesseract.pytesseract.tesseract_cmd = r"D:\Licenta\Tesseract-OCR\tesseract.exe"

img = cv2.imread(str(IMAGE_PATH))

if img is None:
    print("Nu s-a putut citi imaginea.")
    print("IMAGE_PATH =", IMAGE_PATH)
    exit()

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# mai multa marire
gray = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
# blur mai mic
gray = cv2.GaussianBlur(gray, (3, 3), 0)
# otsu in loc de threshold fix
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
# litere negre pe fndal alb
thresh = 255 - thresh

text = pytesseract.image_to_string(
    thresh,
    config='--oem 3 --psm 6 -c tessedit_char_whitelist=SAFETYCAR '
)

print("Text OCR brut:")
print(repr(text))

text_clean = text.upper().strip().replace("\n", " ")

if "SAFETY CAR" in text_clean:
    print("Status: SAFETY CAR")
else:
    print("Status: nimic detectat")

cv2.imwrite(str(PROJECT_DIR / "roi" / "safety_car_thresh_debug.jpg"), thresh)