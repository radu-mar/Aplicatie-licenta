import cv2
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

VIDEO_PATH = PROJECT_DIR / "videos" / "cursa.mp4"
OUTPUT_FOLDER = PROJECT_DIR / "frames"
FRAME_EVERY_SECONDS = 2

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

cap = cv2.VideoCapture(str(VIDEO_PATH))

if not cap.isOpened():
    print("Nu s-a putut deschide video-ul.")
    print("VIDEO_PATH =", VIDEO_PATH)
    exit()

fps = cap.get(cv2.CAP_PROP_FPS)
frame_interval = int(fps * FRAME_EVERY_SECONDS)

frame_count = 0
saved_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if frame_count % frame_interval == 0:
        timestamp_sec = int(frame_count / fps)
        output_path = OUTPUT_FOLDER / f"frame_{timestamp_sec}.jpg"
        cv2.imwrite(str(output_path), frame)
        print(f"Salvat: {output_path}")
        saved_count += 1

    frame_count += 1

cap.release()
print(f"Gata. Au fost salvate {saved_count} frame-uri.")