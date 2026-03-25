import cv2
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

IMAGE_PATH = PROJECT_DIR / "frames" / "frame_42.jpg"
OUTPUT_DIR = PROJECT_DIR / "roi"

os.makedirs(OUTPUT_DIR, exist_ok=True)

img = cv2.imread(str(IMAGE_PATH))

if img is None:
    print("Nu s-a putut citi imaginea.")
    exit()

print("Dimensiune imagine:", img.shape)

sc_roi = img[160:220, 170:320]

cv2.imwrite(str(OUTPUT_DIR / "sc_roi.jpg"), sc_roi)

print("Salvat:", OUTPUT_DIR / "sc_roi.jpg")