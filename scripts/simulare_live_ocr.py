import joblib
import pandas as pd
import cv2
import pytesseract
import re
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "date_f1"
VIDEO_DIR = PROJECT_DIR / "videos"

VIDEO_PATH = VIDEO_DIR / "cursa.mp4"
PRE_RACE_CSV = DATA_DIR / "pre_race_lv_2023.csv"
MODEL_PATH = DATA_DIR / "f1_live_model.pkl"

TESSERACT_PATH = r"D:\Licenta\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

PROCESS_EVERY_SECONDS = 2

VALID_DRIVERS = {
    "VER", "PER", "HAM", "RUS", "LEC", "SAI", "ALO", "STR",
    "NOR", "PIA", "OCO", "GAS", "ALB", "SAR", "BOT", "ZHO",
    "MAG", "HUL", "TSU", "DEV", "RIC", "LAW"
}

MODEL_FEATURES = [
    "lap",
    "position",
    "grid",
    "positions_gained",
    "race_progress",
    "started_from_pitlane",
    "gap_to_leader_sec",
    "gap_trend",
    "gap_to_pole_sec",
    "istoric_pit_echipa_sec",
    "rata_accidente_pilot",
    "rata_defectiuni_echipa",
    "rata_accidente_circuit",
    "pilot_momentum_3",
    "pilot_momentum_6",
    "team_momentum_3",
    "team_momentum_6",
    "driver_gap_lider_campionat",
    "echipa_gap_lider_campionat",
    "driver_top3_campionat",
    "echipa_top3_campionat",
]

def extract_lap(frame):
    lap_roi = frame[100:150, 197:280]

    gray = cv2.cvtColor(lap_roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    text = pytesseract.image_to_string(thresh, config="--psm 7")
    match = re.search(r'(\d+)\s*/\s*(\d+)', text)

    if match:
        current_lap = int(match.group(1))
        total_laps = int(match.group(2))

        if total_laps >= 100:
            total_laps = int(str(total_laps)[1:])
        return current_lap, total_laps

    return None, None

def extract_drivers(frame):
    drivers_roi = frame[160:710, 155:215]

    gray = cv2.cvtColor(drivers_roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    text = pytesseract.image_to_string(thresh, config="--psm 6")
    lines = text.splitlines()

    found_drivers = []

    for line in lines:
        line = line.upper().replace("0", "O")
        tokens = re.findall(r"[A-Z]{3}", line)

        for token in tokens:
            if token in VALID_DRIVERS and token not in found_drivers:
                found_drivers.append(token)

    return found_drivers


def clean_gap_line(line: str) -> str:
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

    match = re.search(r"\+?(\d+\.\d{1,3})", cleaned_line)
    if match:
        return {"type": "GAP", "value": float(match.group(1))}

    digits_only = re.sub(r"[^\d]", "", cleaned_line)
    if len(digits_only) >= 4:
        candidate = float(f"{digits_only[:-3]}.{digits_only[-3:]}")
        return {"type": "GAP", "value": candidate}

    return {"type": "UNKNOWN", "value": None}


def extract_gaps(frame):
    gap_roi = frame[160:710, 220:310]

    gray = cv2.cvtColor(gap_roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3)
    _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)

    text = pytesseract.image_to_string(
        thresh,
        config='--oem 3 --psm 6 -c tessedit_char_whitelist=LI+0123456789. '
    )

    lines = text.splitlines()
    found_gaps = []

    for raw_line in lines:
        if not raw_line.strip():
            continue

        cleaned = clean_gap_line(raw_line)
        parsed = parse_gap_value(cleaned)

        if parsed is None:
            continue

        if parsed["type"] != "UNKNOWN":
            found_gaps.append(parsed)

    return found_gaps


def detect_safety_car(img):
    sc_roi = img[160:220, 170:320]

    gray = cv2.cvtColor(sc_roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh = 255 - thresh

    text = pytesseract.image_to_string(
        thresh,
        config='--oem 3 --psm 6 -c tessedit_char_whitelist=SAFETYCAR '
    )

    text_clean = text.upper().strip().replace("\n", " ")

    return "SAFETY CAR" in text_clean


pre_race_df = pd.read_csv(PRE_RACE_CSV)
last_gap_to_leader = {}


def build_live_df(lap_current, lap_total, drivers, gaps, pre_race_df, last_gap_to_leader):
    rows = []

    n = min(len(drivers), len(gaps))
    if lap_current is None or lap_total is None or lap_total == 0 or n == 0:
        return pd.DataFrame()

    # regula simpla stabilita:
    # daca primul gap este LEADER -> valorile numerice se iau ca atare
    # daca primul gap este INTERVAL -> valorile numerice se cumuleaza
    first_gap_type = gaps[0]["type"]
    interval_mode = (first_gap_type == "INTERVAL")

    cumulative_gap = 0.0

    for i in range(n):
        code = drivers[i]
        gap_info = gaps[i]
        position = i + 1

        match = pre_race_df[pre_race_df["code"] == code]
        if match.empty:
            continue

        prerace_row = match.iloc[0]

        grid = int(prerace_row["grid"]) if pd.notna(prerace_row["grid"]) else 0
        started_from_pitlane = int(prerace_row["started_from_pitlane"]) if pd.notna(prerace_row["started_from_pitlane"]) else 0

        positions_gained = (grid - position) if grid > 0 else 0
        race_progress = lap_current / lap_total

        if position == 1:
            gap_to_leader_sec = 0.0
            cumulative_gap = 0.0
        else:
            if gap_info["type"] == "GAP" and gap_info["value"] is not None:
                val = float(gap_info["value"])

                if interval_mode:
                    cumulative_gap += val
                    gap_to_leader_sec = cumulative_gap
                else:
                    gap_to_leader_sec = val
                    cumulative_gap = val

            else:
                # fallback simplu
                gap_to_leader_sec = last_gap_to_leader.get(code, 0.0)

        prev_gap = last_gap_to_leader.get(code, None)
        gap_trend = 0.0 if prev_gap is None else (prev_gap - gap_to_leader_sec)
        last_gap_to_leader[code] = gap_to_leader_sec

        rows.append({
            "code": code,
            "lap": lap_current,
            "position": position,
            "grid": grid,
            "positions_gained": positions_gained,
            "race_progress": race_progress,
            "started_from_pitlane": started_from_pitlane,
            "gap_to_leader_sec": gap_to_leader_sec,
            "gap_trend": gap_trend,
        })

    return pd.DataFrame(rows)


model = joblib.load(MODEL_PATH)
print(f"Model incarcat din: {MODEL_PATH}")


cap = cv2.VideoCapture(str(VIDEO_PATH))

if not cap.isOpened():
    print("Nu s-a putut deschide video-ul.")
    print("VIDEO_PATH =", VIDEO_PATH)
    exit()

fps = cap.get(cv2.CAP_PROP_FPS)
if not fps or fps <= 0:
    fps = 30.0

frame_delay = 1.0 / fps

last_lap_current = None
last_lap_total = None
last_drivers = []
last_gaps = []
last_safety_car = False
last_processed_time = 0

print("Porneste OCR din videos/cursa.mp4, simuland live-ul...\n")

while True:
    ret, frame = cap.read()

    if not ret:
        print("Video terminat.")
        break

    now = time.time()

    if now - last_processed_time >= PROCESS_EVERY_SECONDS:
        lap_current, lap_total = extract_lap(frame)
        drivers = extract_drivers(frame)
        gaps = extract_gaps(frame)
        safety_car = detect_safety_car(frame)

        if lap_current is None:
            lap_current = last_lap_current
        else:
            last_lap_current = lap_current

        if lap_current == 35:
            lap_current = 3

        if lap_total is None:
            lap_total = last_lap_total
        else:
            last_lap_total = lap_total

        if not drivers:
            drivers = last_drivers
        else:
            last_drivers = drivers

        if not gaps:
            gaps = last_gaps
        else:
            last_gaps = gaps

        live_df = build_live_df(
            lap_current=lap_current,
            lap_total=lap_total,
            drivers=drivers,
            gaps=gaps,
            pre_race_df=pre_race_df,
            last_gap_to_leader=last_gap_to_leader
        )


        if not live_df.empty:
            model_input_df = live_df.merge(
                pre_race_df.drop(columns=["grid", "started_from_pitlane"]),
                on="code",
                how="left"
            )

            display_cols = ["code"] + MODEL_FEATURES
            display_cols = [c for c in display_cols if c in model_input_df.columns]

            X_live = model_input_df[MODEL_FEATURES].copy()

            pred_proba = model.predict_proba(X_live)[:, 1]
            pred_df = model_input_df[["code", "position"]].copy()
            pred_df["prob_winner"] = pred_proba
            pred_df = pred_df.sort_values(
                by=["prob_winner", "position"],
                ascending=[False, True]
            ).reset_index(drop=True)


            print("[LIVE SIMULAT]")
            print("Safety Car:", safety_car)
            print("Lap curent:", lap_current)
            print("Total ture:", lap_total)
            print("Piloti detectati:", drivers)
            print("Gap-uri detectate:", gaps)
            print("-" * 60)

            print("DATASET FINAL CARE INTRA IN MODEL:")
            print(model_input_df[display_cols].to_string(index=False))
            print("-" * 60)
            print("Shape X_live:", X_live.shape)
            print("=" * 80)

            #VERIFICARE UPDATARE POZTII CE TRIMIT MODELULUI!!!!!

            print("TOP 3 PILOTI DUPA PROBABILITATEA MODELULUI:")
            print(pred_df.head(3).to_string(index=False))
            print("=" * 80)
        else:
            print("[LIVE SIMULAT]")
            print("Nu s-a putut construi live_df pentru snapshot-ul curent.")
            print("-" * 60)

        last_processed_time = now

    time.sleep(frame_delay)

cap.release()
print("Proces terminat.")