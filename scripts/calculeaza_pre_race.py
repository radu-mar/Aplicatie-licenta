import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "date_f1")

MASTER_PATH = os.path.join(DATA_DIR, "dataset_04_master_live.csv")
RACES_PATH = os.path.join(DATA_DIR, "races.csv")
DRIVERS_PATH = os.path.join(DATA_DIR, "drivers.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "pre_race_lv_2023.csv")

LV_RACE_ID = 1119
LV_YEAR = 2023
LV_ROUND = 21

CURRENT_RACE_COLS = [
    "raceId",
    "driverId",
    "year",
    "grid",
    "started_from_pitlane",
    "gap_to_pole_sec",
]

HISTORICAL_COLS = [
    "raceId",
    "driverId",
    "year",
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

print("MASTER_PATH =", MASTER_PATH)
print("RACES_PATH =", RACES_PATH)
print("DRIVERS_PATH =", DRIVERS_PATH)
print("OUTPUT_CSV =", OUTPUT_CSV)

df = pd.read_csv(MASTER_PATH)
races = pd.read_csv(RACES_PATH)
drivers = pd.read_csv(DRIVERS_PATH)

df = df.merge(
    races[["raceId", "year", "round"]],
    on=["raceId", "year"],
    how="left"
)

current_race = (
    df[df["raceId"] == LV_RACE_ID][CURRENT_RACE_COLS]
    .drop_duplicates(subset=["raceId", "driverId"])
    .sort_values("driverId")
    .reset_index(drop=True)
)

df_hist = df[
    (df["year"] < LV_YEAR) |
    ((df["year"] == LV_YEAR) & (df["round"] < LV_ROUND))
].copy()

drivers_lv = current_race["driverId"].dropna().unique().tolist()

historical_latest = (
    df_hist[df_hist["driverId"].isin(drivers_lv)][HISTORICAL_COLS]
    .drop_duplicates(subset=["raceId", "driverId"])
    .sort_values(["driverId", "year", "raceId"])
    .groupby("driverId", as_index=False)
    .tail(1)
    .sort_values("driverId")
    .reset_index(drop=True)
)

pre_race_lv = current_race.merge(
    historical_latest.drop(columns=["raceId", "year"]),
    on="driverId",
    how="left"
)

pre_race_lv = pre_race_lv.merge(
    drivers[["driverId", "code"]],
    on="driverId",
    how="left"
)

pre_race_lv.to_csv(OUTPUT_CSV, index=False)

print(f"Fisier salvat: {OUTPUT_CSV}")
print("\nPrimele randuri:")
print(pre_race_lv.head(20).to_string(index=False))