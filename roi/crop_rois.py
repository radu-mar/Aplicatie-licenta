import cv2
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

IMAGE_PATH = PROJECT_DIR / "frames" / "frame_8.jpg"
# IMAGE_PATH = PROJECT_DIR / "frames" / "frame_8.jpg"
OUTPUT_DIR = PROJECT_DIR / "roi"

os.makedirs(OUTPUT_DIR, exist_ok=True)

img = cv2.imread(str(IMAGE_PATH))

if img is None:
    print("Nu s-a putut citi imaginea.")
    exit()

print("Dimensiune imagine:", img.shape)

lap_roi = img[100:150, 150:280]
leaderboard_roi = img[160:710, 155:215]
gap_roi = img[160:710, 220:310]

cv2.imwrite(str(OUTPUT_DIR / "lap_roi.jpg"), lap_roi)
cv2.imwrite(str(OUTPUT_DIR / "leaderboard_roi.jpg"), leaderboard_roi)
cv2.imwrite(str(OUTPUT_DIR / "gap_roi.jpg"), gap_roi)

print("Salvat:", OUTPUT_DIR / "lap_roi.jpg")
print("Salvat:", OUTPUT_DIR / "leaderboard_roi.jpg")
print("Salvat:", OUTPUT_DIR / "gap_roi.jpg")