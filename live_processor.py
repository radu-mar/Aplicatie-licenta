import cv2
import joblib
import pandas as pd
import pytesseract
import re
import time
import threading
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR
DATA_DIR = PROJECT_DIR / "date_f1"
VIDEO_DIR = PROJECT_DIR / "videos"

STREAM_URL = "http://localhost:8080/stream.m3u8"
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
    # lap_roi = frame[100:150, 197:280]
    lap_roi = frame[100:150, 150:280]

    gray = cv2.cvtColor(lap_roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    text = pytesseract.image_to_string(thresh, config="--psm 7")
    match = re.search(r"(\d+)\s*/\s*(\d+)", text)

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
        config="--oem 3 --psm 6 -c tessedit_char_whitelist=LI+0123456789. "
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
        config="--oem 3 --psm 6 -c tessedit_char_whitelist=SAFETYCAR "
    )

    text_clean = text.upper().strip().replace("\n", " ")
    return "SAFETY CAR" in text_clean


def build_live_df(lap_current, lap_total, drivers, gaps, pre_race_df, last_gap_to_leader):
    rows = []

    n = min(len(drivers), len(gaps))
    if lap_current is None or lap_total is None or lap_total == 0 or n == 0:
        return pd.DataFrame()

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


class LiveRaceProcessor:
    def __init__(self):
        self.pre_race_df = pd.read_csv(PRE_RACE_CSV)
        self.model = joblib.load(MODEL_PATH)

        self.last_gap_to_leader = {}
        self.last_lap_current = None
        self.last_lap_total = None
        self.last_drivers = []
        self.last_gaps = []

        self.latest_frame = None
        self.latest_payload = {
            "lap_current": None,
            "lap_total": None,
            "safety_car": False,
            "drivers": [],
            "gaps": [],
            "top3": [],
            "standings": []
        }

        self.lock = threading.Lock()
        self.running = False

    def start(self):
        if self.running:
            return

        self.running = True
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()

    def _run_loop(self):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "fflags;nobuffer|flags;low_delay|max_delay;0"
        cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG)

        if not cap.isOpened():
            print("Nu s-a putut deschide stream-ul:", STREAM_URL)
            self.running = False
            return

        last_processed_time = 0

        while self.running:
            grabbed = cap.grab()

            if not grabbed:
                time.sleep(0.2)
                continue

            now = time.time()

            if now - last_processed_time < PROCESS_EVERY_SECONDS:
                continue

            ret, frame = cap.retrieve()

            if not ret:
                continue

            with self.lock:
                self.latest_frame = frame.copy()

            lap_current, lap_total = extract_lap(frame)
            drivers = extract_drivers(frame)
            gaps = extract_gaps(frame)
            safety_car = detect_safety_car(frame)

            if lap_current is not None and lap_total is not None and lap_current > lap_total:
                lap_current, lap_total = self.last_lap_current, self.last_lap_total

            if lap_total is not None and self.last_lap_total is not None and lap_total != self.last_lap_total:
                lap_current, lap_total = self.last_lap_current, self.last_lap_total

            if lap_current is None:
                lap_current = self.last_lap_current
            else:
                self.last_lap_current = lap_current

            if lap_total is None:
                lap_total = self.last_lap_total
            else:
                self.last_lap_total = lap_total

            if not drivers:
                drivers = self.last_drivers
            else:
                self.last_drivers = drivers

            if not gaps:
                gaps = self.last_gaps
            else:
                self.last_gaps = gaps

            live_df = build_live_df(
                lap_current=lap_current,
                lap_total=lap_total,
                drivers=drivers,
                gaps=gaps,
                pre_race_df=self.pre_race_df,
                last_gap_to_leader=self.last_gap_to_leader
            )

            payload = {
                "lap_current": lap_current,
                "lap_total": lap_total,
                "safety_car": safety_car,
                "drivers": drivers,
                "gaps": gaps,
                "top3": [],
                "standings": []
            }

            if not live_df.empty:
                model_input_df = live_df.merge(
                    self.pre_race_df.drop(columns=["grid", "started_from_pitlane"]),
                    on="code",
                    how="left"
                )

                X_live = model_input_df[MODEL_FEATURES].copy()
                pred_proba = self.model.predict_proba(X_live)[:, 1]

                pred_df = model_input_df[["code", "position", "gap_to_leader_sec"]].copy()
                pred_df["prob_winner"] = pred_proba
                pred_df = pred_df.sort_values(
                    by=["prob_winner", "position"],
                    ascending=[False, True]
                ).reset_index(drop=True)

                payload["top3"] = pred_df.head(3).to_dict(orient="records")
                payload["standings"] = pred_df.to_dict(orient="records")

                print("[LIVE SIMULAT]")
                print("Safety Car:", safety_car)
                print("Lap curent:", lap_current)
                print("Total ture:", lap_total)
                print("Piloti detectati:", drivers)
                print("Gap-uri detectate:", gaps)
                print(pred_df.head(3).to_string(index=False))
                print("=" * 80)

            with self.lock:
                self.latest_payload = payload

            last_processed_time = now

        cap.release()


    def get_latest_payload(self):
        with self.lock:
            return dict(self.latest_payload)